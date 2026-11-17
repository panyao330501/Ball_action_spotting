"""Verify frozen match splits and recompute Pass reranker test metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate_u18_predictions import load_json_list
from train_u18_pass_reranker import build_features, pass_metrics, predict, sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-dir", required=True, type=Path)
    parser.add_argument("--reranker-dir", required=True, type=Path)
    args = parser.parse_args()
    frozen = json.loads((args.frozen_dir / "manifest.json").read_text(encoding="utf-8"))
    comparison_path = args.reranker_dir / "comparison.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    if comparison["frozen_manifest_sha256"] != sha256(args.frozen_dir / "manifest.json"):
        raise ValueError("冻结清单哈希不一致")
    if len(comparison["folds"]) != 2:
        raise ValueError("预期两个留出方向")
    for result in comparison["folds"]:
        fold_id = result["fold_id"]
        frozen_entry = next(item for item in frozen["folds"] if item["fold_id"] == fold_id)
        train_ids = set(result["train_video_ids"])
        test_ids = set(result["test_video_ids"])
        if train_ids & test_ids or train_ids != set(frozen_entry["train_video_ids"]) or test_ids != set(frozen_entry["test_video_ids"]):
            raise ValueError(f"训练/测试隔离失败：{fold_id}")
        fold_dir = args.frozen_dir / fold_id
        for name, key in (("train_gt_pass.json", "train_gt_sha256"), ("test_gt_pass.json", "test_gt_sha256"), ("baseline_pass_metrics.json", "baseline_sha256")):
            if sha256(fold_dir / name) != frozen_entry[key]:
                raise ValueError(f"冻结文件哈希不一致：{name}")
        events_path = args.reranker_dir / fold_id / "reranked_pass_events.json"
        if sha256(events_path) != result["reranked_predictions_sha256"]:
            raise ValueError(f"重排预测哈希不一致：{fold_id}")
        events = load_json_list(events_path)
        gt = load_json_list(fold_dir / "test_gt_pass.json")
        if {item["video_id"] for item in events} != test_ids or len(gt) != result["test_gt_pass"]:
            raise ValueError(f"测试输出视频或 GT 数量不一致：{fold_id}")
        if result["train_scores_sha256"].keys() != train_ids or result["test_scores_sha256"].keys() != test_ids:
            raise ValueError(f"特征来源比赛不一致：{fold_id}")
        feature_matrix, hashes = build_features(events, Path("artifacts/inference"))
        if hashes != result["test_scores_sha256"]:
            raise ValueError(f"原始分数哈希不一致：{fold_id}")
        calculated = predict(feature_matrix, result["model"])
        if any(abs(score - item["confidence"]) > 1e-12 for score, item in zip(calculated, events)):
            raise ValueError(f"模型系数无法复现测试分数：{fold_id}")
        values = pass_metrics(gt, events, [0.5, 1.0, 2.0], result["train_threshold"])
        for tolerance, metrics in values.items():
            expected = result["reranked"][tolerance]
            for key in ("gt", "predictions_all", "tp", "fp", "fn"):
                if metrics[key] != expected[key]:
                    raise ValueError(f"指标复算不一致：{fold_id}/{tolerance}/{key}")
            for key in ("ap", "precision", "recall", "f1"):
                if abs(metrics[key] - expected[key]) > 1e-12:
                    raise ValueError(f"指标复算不一致：{fold_id}/{tolerance}/{key}")
        print(f"{fold_id}: 隔离、哈希、峰值数量及三档容差指标通过")


if __name__ == "__main__":
    main()
