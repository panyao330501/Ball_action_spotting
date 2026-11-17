"""Fine-tune only the Pass classifier row of BAS fold 0 on one U18 match.

Run through Slurm on a GPU node. The paired match is never opened here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import cv2
import numpy as np
import torch


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def select_examples(labels, excluded, pending, drive_proxies, proxy_by_id, seed: int, max_per_half: int | None):
    rng = random.Random(seed)
    examples = []
    for video_id in sorted({row["video_id"] for row in labels}):
        positives = sorted((row for row in labels if row["video_id"] == video_id),
                           key=lambda row: row["training_time_sec"])
        if max_per_half is not None:
            positives = positives[:max_per_half]
        frame_count = proxy_by_id[video_id]["proxy_info"]["frame_count"]
        forbidden = [row["training_time_sec"] for row in labels if row["video_id"] == video_id]
        forbidden += [row["bepro_time_sec"] for row in excluded if row["video_id"] == video_id]
        forbidden += [row["prediction_time_sec"] for row in pending if row["video_id"] == video_id]
        forbidden += [row["source_time_sec"] for row in drive_proxies if row["video_id"] == video_id]
        negatives = []
        attempts = 0
        while len(negatives) < len(positives):
            attempts += 1
            if attempts > 100000:
                raise RuntimeError(f"无法采样足够的非事件窗口：{video_id}")
            index = rng.randrange(34, frame_count - 34)
            time_sec = index / 25.0
            if any(abs(time_sec - value) <= 3.0 for value in forbidden):
                continue
            if any(abs(time_sec - value) <= 1.0 for value in negatives):
                continue
            negatives.append(time_sec)
        examples += [(video_id, round(row["training_time_sec"] * 25), 1, row["event_id"])
                     for row in positives]
        examples += [(video_id, round(value * 25), 0, "") for value in negatives]
    return examples


@torch.no_grad()
def extract_features(model, processor, proxy_root: Path, proxy_by_id, examples):
    features = []
    for video_id in sorted({item[0] for item in examples}):
        meta = proxy_by_id[video_id]
        path = proxy_root / meta["proxy_basename"]
        if sha256(path) != meta["proxy_sha256"]:
            raise ValueError(f"代理哈希不符：{video_id}")
        capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
        if not capture.isOpened() or int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) != meta["proxy_info"]["frame_count"]:
            raise RuntimeError(f"无法读取代理或帧数不符：{video_id}")
        try:
            video_examples = (item for item in examples if item[0] == video_id)
            for count, (_, center, _, _) in enumerate(video_examples, 1):
                if not 33 <= center < meta["proxy_info"]["frame_count"] - 33:
                    raise ValueError(f"模型窗口越界：{video_id}/{center}")
                if not capture.set(cv2.CAP_PROP_POS_FRAMES, center - 32):
                    raise RuntimeError(f"无法定位视频帧：{video_id}/{center}")
                stack = []
                for offset in range(65):
                    ok, bgr = capture.read()
                    if not ok:
                        raise RuntimeError(f"无法解码视频帧：{video_id}/{center - 32 + offset}")
                    if offset % 2 == 0:
                        stack.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
                frames = torch.from_numpy(np.stack(stack)).unsqueeze(0).to(model.device)
                frames = processor(frames)
                with torch.cuda.amp.autocast():
                    encoded = model.nn_module.forward_2d(frames)
                    encoded = model.nn_module.forward_3d(encoded)
                    pooled = model.nn_module.global_pool(encoded)
                features.append(pooled.squeeze(0).float().cpu())
                if count % 100 == 0:
                    print(f"{video_id}: extracted {count}", flush=True)
        finally:
            capture.release()
    # Extraction is grouped by video; return the same ordering for targets.
    ordered = [item for video_id in sorted({item[0] for item in examples})
               for item in examples if item[0] == video_id]
    return torch.stack(features), ordered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fold-id", required=True, choices=["A_train_B_test", "B_train_A_test"])
    parser.add_argument("--labels-root", required=True, type=Path)
    parser.add_argument("--proxy-root", required=True, type=Path)
    parser.add_argument("--proxy-manifest", required=True, type=Path)
    parser.add_argument("--initial-checkpoint", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-per-half", type=int, default=None, help="Smoke test only")
    parser.add_argument("--seed", type=int, default=20261117)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖已有训练产物：{args.output_dir}")
    if not torch.cuda.is_available() or args.max_per_half is not None and args.max_per_half < 1:
        raise RuntimeError("需要 Slurm GPU，且 max-per-half 必须为正数")
    import argus
    import src.argus_models  # noqa: F401
    from src.frames import get_frames_processor

    root_manifest = read(args.labels_root / "manifest.json")
    fold = next(item for item in root_manifest["folds"] if item["fold_id"] == args.fold_id)
    folder = args.labels_root / args.fold_id
    for name, expected in fold["output_sha256"].items():
        if sha256(folder / name) != expected:
            raise ValueError(f"训练标签哈希不符：{name}")
    labels = read(folder / "train_pass_events.json")
    excluded = read(folder / "excluded_bepro_pass.json")
    pending = read(folder / "pending_pass_additions.json")
    drive_proxies = read(folder / "drive_proxy_events.json")
    train_ids = set(fold["train_video_ids"])
    test_ids = set(fold["test_video_ids"])
    if train_ids & test_ids or {row["video_id"] for row in labels + excluded + pending + drive_proxies} != train_ids:
        raise ValueError("训练/测试比赛隔离失败")
    proxy_manifest = read(args.proxy_manifest)
    proxy_by_id = {row["video_id"]: row for row in proxy_manifest["videos"] if row["video_id"] in train_ids}
    if set(proxy_by_id) != train_ids:
        raise ValueError("缺少训练比赛代理")
    examples = select_examples(labels, excluded, pending, drive_proxies, proxy_by_id, args.seed, args.max_per_half)
    print(f"fold={args.fold_id} examples={len(examples)} positives={sum(x[2] for x in examples)}", flush=True)
    checkpoint_sha256 = sha256(args.initial_checkpoint)
    model = argus.load_model(args.initial_checkpoint, device="cuda:0", optimizer=None, loss=None)
    model.eval()
    processor = get_frames_processor(*model.params["frames_processor"])
    if model.params["frame_stack_size"] != 33 or model.params["frame_stack_step"] != 2:
        raise ValueError("初始权重的时间窗口与训练入口不一致")
    features, ordered = extract_features(model, processor, args.proxy_root, proxy_by_id, examples)
    targets = torch.tensor([row[2] for row in ordered], dtype=torch.float32, device="cuda:0")
    features = features.to("cuda:0")
    torch.manual_seed(args.seed)
    head = torch.nn.Linear(features.shape[1], 1, device="cuda:0")
    with torch.no_grad():
        head.weight.copy_(model.nn_module.classifier.weight[:1])
        head.bias.copy_(model.nn_module.classifier.bias[:1])
    optimizer = torch.optim.AdamW(head.parameters(), lr=1e-4, weight_decay=1e-3)
    for epoch in range(30):
        optimizer.zero_grad()
        logits = head(features).squeeze(1)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, targets)
        loss.backward()
        optimizer.step()
        if epoch in {0, 9, 19, 29}:
            print(f"epoch={epoch + 1} train_loss={loss.item():.6f}", flush=True)
    # Argus expects both state dicts; keep the Drive row and all feature layers fixed.
    checkpoint = torch.load(args.initial_checkpoint, map_location="cpu")
    for state_key in ("nn_state_dict", "no_ema_nn_state_dict"):
        state = checkpoint[state_key]
        state["classifier.weight"][0].copy_(head.weight[0].detach().cpu())
        state["classifier.bias"][0].copy_(head.bias[0].detach().cpu())
    fold_dir = args.output_dir / "fold_0"
    fold_dir.mkdir(parents=True)
    examples_path = args.output_dir / "training_examples.json"
    examples_path.write_text(json.dumps([
        {"video_id": video_id, "frame_index_25fps": center, "target_pass": target,
         "positive_event_id": event_id}
        for video_id, center, target, event_id in ordered
    ], indent=2) + "\n", encoding="utf-8")
    output_path = fold_dir / "model-001-u18-pass-head.pth"
    torch.save(checkpoint, output_path)
    metadata = {
        "schema_version": 1, "method": "fold_0_pass_classifier_head_only",
        "fold_id": args.fold_id, "train_video_ids": sorted(train_ids), "test_video_ids": sorted(test_ids),
        "seed": args.seed, "epochs": 30, "learning_rate": 1e-4, "weight_decay": 1e-3,
        "max_per_half": args.max_per_half, "positives": int(targets.sum().item()),
        "negatives": int(len(targets) - targets.sum().item()),
        "drive_proxy_events_avoided": len(drive_proxies),
        "labels_manifest_sha256": sha256(args.labels_root / "manifest.json"),
        "proxy_manifest_sha256": sha256(args.proxy_manifest),
        "initial_checkpoint_sha256": checkpoint_sha256,
        "output_checkpoint_sha256": sha256(output_path),
        "training_examples_sha256": sha256(examples_path),
        "training_loss_final": float(loss.item()),
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata), flush=True)


if __name__ == "__main__":
    main()
