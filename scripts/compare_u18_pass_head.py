"""Compare a Pass-only BAS head with its same-fold zero-shot baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluate_u18_predictions import evaluate_group, load_predictions


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-dir", required=True, type=Path)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--improved-root", required=True, type=Path)
    parser.add_argument("--model-manifests-root", required=True, type=Path)
    parser.add_argument("--proxy-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖比较结果：{args.output_dir}")
    frozen = read(args.frozen_dir / "manifest.json")
    proxy = read(args.proxy_manifest)
    if sha256(args.proxy_manifest) != frozen["proxy_manifest_sha256"]:
        raise ValueError("代理清单与冻结协议不符")
    proxy_by_id = {row["video_id"]: row for row in proxy["videos"]}
    results = []
    for fold in frozen["folds"]:
        fold_id = fold["fold_id"]
        test_ids = fold["test_video_ids"]
        gt_path = args.frozen_dir / fold_id / "test_gt_pass.json"
        if sha256(gt_path) != fold["test_gt_sha256"]:
            raise ValueError(f"冻结测试 GT 哈希不符：{fold_id}")
        gt = read(gt_path)
        model_path = args.model_manifests_root / fold_id / "manifest.json"
        model = read(model_path)
        if model["fold_id"] != fold_id or model["test_video_ids"] != test_ids or model["max_per_half"] is not None:
            raise ValueError(f"模型清单与正式留出分组不符：{fold_id}")
        hashes = {"model_manifest": sha256(model_path), "test_gt": sha256(gt_path)}
        for video_id in test_ids:
            base_dir = args.baseline_root / video_id
            improved_dir = args.improved_root / fold_id / video_id
            base_post = read(base_dir / "postprocess_manifest.json")
            new_post = read(improved_dir / "postprocess_manifest.json")
            infer = read(improved_dir / "inference" / "manifest.json")
            if base_post["parameters"] != {
                "gauss_sigma": 3.0, "min_height": 0.0, "min_distance_frames": 15,
                "input_score": "fold_scores[:, 0, :]",
            }:
                raise ValueError(f"基线不是原 fold 0：{video_id}")
            if new_post["parameters"] != {
                "gauss_sigma": 3.0, "min_height": 0.0, "min_distance_frames": 15,
                "input_score": "ensemble_scores",
            }:
                raise ValueError(f"改进模型后处理参数不一致：{video_id}")
            if infer["input"]["sha256"] != proxy_by_id[video_id]["proxy_sha256"]:
                raise ValueError(f"改进模型输入视频不一致：{video_id}")
            if new_post["scores_sha256"] != sha256(improved_dir / "inference" / "scores.npz"):
                raise ValueError(f"改进模型原始分数哈希不符：{video_id}")
            if infer["model"]["experiment"] != f"u18_pass_head_{fold_id}_v1":
                raise ValueError(f"改进模型实验名不符：{video_id}")
            if infer["model"]["fold_ids"] != [0] or infer["model"]["checkpoint_sha256"] != [model["output_checkpoint_sha256"]]:
                raise ValueError(f"改进权重与训练清单不一致：{video_id}")
            if sha256(base_dir / "events.json") == sha256(improved_dir / "events.json"):
                raise ValueError(f"两组事件完全相同，需核查：{video_id}")
            hashes[video_id] = {
                "baseline_events": sha256(base_dir / "events.json"),
                "improved_events": sha256(improved_dir / "events.json"),
                "improved_raw_scores": sha256(improved_dir / "inference" / "scores.npz"),
            }
        baselines = [row for row in load_predictions(args.baseline_root, test_ids) if row["label"] == "Pass"]
        # The improved events are one level below the fold directory.
        improved = [row for row in load_predictions(args.improved_root / fold_id, test_ids)
                    if row["label"] == "Pass"]
        result = {
            "fold_id": fold_id, "test_video_ids": test_ids, "gt_pass": len(gt),
            "method": "original fold 0 vs same fold Pass classifier head adapted on other match",
            "operating_threshold": 0.2, "tolerances_sec": [0.5, 1.0, 2.0],
            "baseline": evaluate_group(gt, baselines, [0.5, 1.0, 2.0], 0.2),
            "improved": evaluate_group(gt, improved, [0.5, 1.0, 2.0], 0.2),
            "input_sha256": hashes,
        }
        results.append(result)
    args.output_dir.mkdir(parents=True)
    output = {
        "schema_version": 1,
        "interpretation": "Exploratory match-held-out comparison on two previously inspected U18 matches",
        "frozen_manifest_sha256": sha256(args.frozen_dir / "manifest.json"),
        "folds": results,
    }
    (args.output_dir / "comparison.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in results:
        base = item["baseline"]["tolerances"]["1"]["classes"]["Pass"]
        new = item["improved"]["tolerances"]["1"]["classes"]["Pass"]
        print(f"{item['fold_id']} AP {base['ap']:.3f}->{new['ap']:.3f}, "
              f"P {base['precision']:.3f}->{new['precision']:.3f}, "
              f"R {base['recall']:.3f}->{new['recall']:.3f}")


if __name__ == "__main__":
    main()
