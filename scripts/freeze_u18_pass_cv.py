"""Freeze match-held-out Pass folds and recalculate their zero-shot baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluate_u18_predictions import evaluate_group, load_json_list, load_predictions, validate_gt


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected.lower():
        raise ValueError(f"SHA-256 不一致：{path}: {actual} != {expected}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/u18_pass_match_cv.json"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖已冻结输出：{args.output_dir}")

    config = json.loads(args.config.read_text(encoding="utf-8"))
    gt_path = Path(config["ground_truth_path"])
    proxy_path = Path(config["proxy_manifest_path"])
    baseline_path = Path(config["baseline_metrics_path"])
    for path, field in (
        (gt_path, "ground_truth_sha256"),
        (proxy_path, "proxy_manifest_sha256"),
        (baseline_path, "baseline_metrics_sha256"),
    ):
        require_hash(path, config[field])

    gt = load_json_list(gt_path)
    validate_gt(gt)
    pass_gt = [event for event in gt if event["label"] == "Pass"]
    proxy = json.loads(proxy_path.read_text(encoding="utf-8"))
    proxy_by_id = {item["video_id"]: item for item in proxy["videos"]}
    matches = config["matches"]
    all_ids = [video_id for item in matches.values() for video_id in item["video_ids"]]
    if len(all_ids) != len(set(all_ids)) or set(all_ids) != set(proxy_by_id):
        raise ValueError("比赛视频集合重复或与代理清单不一致")
    if {event["video_id"] for event in pass_gt} != set(all_ids):
        raise ValueError("Pass GT 视频集合与分组不一致")
    for key, item in matches.items():
        count = sum(event["video_id"] in item["video_ids"] for event in pass_gt)
        if count != item["evaluable_pass_gt"]:
            raise ValueError(f"比赛 {key} 的 Pass GT 数量不符：{count}")
        for video_id in item["video_ids"]:
            video = proxy_by_id[video_id]
            local_proxy = proxy_path.parent / video["proxy_basename"]
            if not local_proxy.is_file() or local_proxy.stat().st_size != video["proxy_info"]["size_bytes"]:
                raise ValueError(f"代理视频缺失或大小不符：{local_proxy}")

    output_folds = []
    for fold in config["folds"]:
        train = set(matches[fold["train_match"]]["video_ids"])
        test = set(matches[fold["test_match"]]["video_ids"])
        if not train or not test or train & test or train | test != set(all_ids):
            raise ValueError(f"训练/测试视频分组不合法：{fold['fold_id']}")
        train_gt = [event for event in pass_gt if event["video_id"] in train]
        test_gt = [event for event in pass_gt if event["video_id"] in test]
        predictions = [
            item for item in load_predictions(Path(config["baseline_predictions_root"]), test)
            if item["label"] == "Pass"
        ]
        result = evaluate_group(
            test_gt, predictions, config["tolerances_sec"], config["baseline_operating_threshold"]
        )
        baseline = {
            "fold_id": fold["fold_id"],
            "train_match": fold["train_match"],
            "test_match": fold["test_match"],
            "test_video_ids": sorted(test),
            "gt_pass": len(test_gt),
            "prediction_pass_all": len(predictions),
            "tolerances": {
                key: {
                    **value["classes"]["Pass"],
                    "recall_by_gt_distance_band": value["recall_by_gt_distance_band"]["Pass"],
                }
                for key, value in result["tolerances"].items()
            },
        }
        fold_dir = args.output_dir / fold["fold_id"]
        fold_dir.mkdir(parents=True)
        for name, items in (("train_gt_pass.json", train_gt), ("test_gt_pass.json", test_gt)):
            (fold_dir / name).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        (fold_dir / "baseline_pass_metrics.json").write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        output_folds.append({
            "fold_id": fold["fold_id"],
            "train_video_ids": sorted(train),
            "test_video_ids": sorted(test),
            "train_gt_pass": len(train_gt),
            "test_gt_pass": len(test_gt),
            "train_gt_sha256": sha256(fold_dir / "train_gt_pass.json"),
            "test_gt_sha256": sha256(fold_dir / "test_gt_pass.json"),
            "baseline_sha256": sha256(fold_dir / "baseline_pass_metrics.json"),
        })

    manifest = {
        "schema_version": 1,
        "config_sha256": sha256(args.config),
        "ground_truth_sha256": config["ground_truth_sha256"],
        "proxy_manifest_sha256": config["proxy_manifest_sha256"],
        "baseline_metrics_sha256": config["baseline_metrics_sha256"],
        "status": "frozen",
        "interpretation": config["interpretation"],
        "folds": output_folds,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(output_folds, ensure_ascii=False))


if __name__ == "__main__":
    main()
