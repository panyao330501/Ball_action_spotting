"""Train a Pass-only score reranker on one match and test on the other."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from evaluate_u18_predictions import evaluate_group, load_json_list, load_predictions, ranked_matches


FEATURE_NAMES = ("smoothed_pass_logit", "raw_pass_logit", "drive_logit", "pass_fold_std")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def features_for_video(video_id: str, predictions: list[dict], scores_root: Path) -> tuple[np.ndarray, str]:
    path = scores_root / f"u18_{video_id}_masked_v1" / "scores.npz"
    with np.load(path) as data:
        frame_indexes = data["frame_indexes"]
        fold_scores = data["fold_scores"]
        ensemble = data["ensemble_scores"]
        classes = list(data["class_names"])
    if classes != ["PASS", "DRIVE"] or fold_scores.shape != (len(frame_indexes), 7, 2):
        raise ValueError(f"原始分数契约不符：{path}")
    frame_to_offset = {int(frame): index for index, frame in enumerate(frame_indexes)}
    offsets = [frame_to_offset[round(item["time_sec"] * 25)] for item in predictions]
    pass_score = np.clip(ensemble[offsets, 0].astype(np.float64), 1e-6, 1 - 1e-6)
    drive_score = np.clip(ensemble[offsets, 1].astype(np.float64), 1e-6, 1 - 1e-6)
    # Candidate confidence is Gaussian-smoothed, while the NPZ stores raw scores.
    candidate_scores = np.clip(np.array([item.get("original_confidence", item["confidence"]) for item in predictions]), 1e-6, 1 - 1e-6)
    matrix = np.column_stack((
        np.log(candidate_scores / (1 - candidate_scores)),
        np.log(pass_score / (1 - pass_score)),
        np.log(drive_score / (1 - drive_score)),
        fold_scores[offsets, :, 0].std(axis=1).astype(np.float64),
    ))
    return matrix, sha256(path)


def build_features(predictions: list[dict], scores_root: Path) -> tuple[np.ndarray, dict[str, str]]:
    matrix = np.empty((len(predictions), len(FEATURE_NAMES)), dtype=np.float64)
    hashes = {}
    for video_id in sorted({item["video_id"] for item in predictions}):
        positions = [index for index, item in enumerate(predictions) if item["video_id"] == video_id]
        selected = [predictions[index] for index in positions]
        matrix[positions], hashes[video_id] = features_for_video(video_id, selected, scores_root)
    if not np.isfinite(matrix).all():
        raise ValueError("特征包含非有限值")
    return matrix, hashes


def fit_logistic(features: np.ndarray, targets: np.ndarray) -> dict:
    mean = features.mean(axis=0)
    scale = features.std(axis=0)
    scale[scale < 1e-8] = 1.0
    x = (features - mean) / scale
    # Equal total class weight; fixed L2 strength, with no held-out tuning.
    positives = int(targets.sum())
    negatives = len(targets) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("训练匹配没有同时包含正负候选")
    weights = np.where(targets == 1, len(targets) / (2 * positives), len(targets) / (2 * negatives))

    def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        logits = x @ parameters[:-1] + parameters[-1]
        probabilities = expit(logits)
        loss = (weights * (np.logaddexp(0.0, logits) - targets * logits)).mean()
        loss += 0.5 * float((parameters[:-1] ** 2).sum()) / len(targets)
        error = weights * (probabilities - targets) / len(targets)
        gradient = np.r_[x.T @ error + parameters[:-1] / len(targets), error.sum()]
        return float(loss), gradient

    fitted = minimize(objective, np.zeros(x.shape[1] + 1), jac=True, method="L-BFGS-B")
    if not fitted.success:
        raise RuntimeError(f"优化未收敛：{fitted.message}")
    return {
        "feature_names": FEATURE_NAMES,
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "coefficients": fitted.x[:-1].tolist(),
        "intercept": float(fitted.x[-1]),
        "positive_candidates": positives,
        "negative_candidates": negatives,
        "optimization_loss": float(fitted.fun),
    }


def predict(features: np.ndarray, model: dict) -> np.ndarray:
    x = (features - np.array(model["mean"])) / np.array(model["scale"])
    return expit(x @ np.array(model["coefficients"]) + model["intercept"])


def with_scores(predictions: list[dict], scores: np.ndarray) -> list[dict]:
    return [
        {**item, "original_confidence": item["confidence"], "confidence": float(score)}
        for item, score in zip(predictions, scores)
    ]


def train_threshold(scores: np.ndarray, original_scores: np.ndarray, baseline_threshold: float) -> float:
    # Match the baseline's training-match prediction budget without reading test labels.
    budget = int((original_scores >= baseline_threshold).sum())
    if budget <= 0 or budget >= len(scores):
        raise ValueError("训练集的操作预测数量不合理")
    descending = np.sort(scores)[::-1]
    return float((descending[budget - 1] + descending[budget]) / 2)


def pass_metrics(gt: list[dict], predictions: list[dict], tolerances: list[float], threshold: float) -> dict:
    evaluation = evaluate_group(gt, predictions, tolerances, threshold)
    return {
        tolerance: {
            **values["classes"]["Pass"],
            "recall_by_gt_distance_band": values["recall_by_gt_distance_band"]["Pass"],
        }
        for tolerance, values in evaluation["tolerances"].items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/u18_pass_match_cv.json"))
    parser.add_argument("--frozen-dir", type=Path, required=True)
    parser.add_argument("--scores-root", type=Path, default=Path("artifacts/inference"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖结果：{args.output_dir}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    frozen_manifest = json.loads((args.frozen_dir / "manifest.json").read_text(encoding="utf-8"))
    if frozen_manifest["config_sha256"] != sha256(args.config):
        raise ValueError("冻结分组与当前配置不一致")
    root = Path(config["baseline_predictions_root"])
    results = []
    for fold in config["folds"]:
        fold_id = fold["fold_id"]
        frozen_fold = args.frozen_dir / fold_id
        frozen_entry = next(item for item in frozen_manifest["folds"] if item["fold_id"] == fold_id)
        if (sha256(frozen_fold / "train_gt_pass.json") != frozen_entry["train_gt_sha256"]
                or sha256(frozen_fold / "test_gt_pass.json") != frozen_entry["test_gt_sha256"]
                or sha256(frozen_fold / "baseline_pass_metrics.json") != frozen_entry["baseline_sha256"]):
            raise ValueError(f"冻结数据哈希不一致：{fold_id}")
        train_gt = load_json_list(frozen_fold / "train_gt_pass.json")
        test_gt = load_json_list(frozen_fold / "test_gt_pass.json")
        train_ids = set(config["matches"][fold["train_match"]]["video_ids"])
        test_ids = set(config["matches"][fold["test_match"]]["video_ids"])
        if train_ids & test_ids or {item["video_id"] for item in train_gt} != train_ids or {item["video_id"] for item in test_gt} != test_ids:
            raise ValueError(f"分组泄漏：{fold_id}")
        train_predictions = [item for item in load_predictions(root, train_ids) if item["label"] == "Pass"]
        train_features, train_score_hashes = build_features(train_predictions, args.scores_root)
        ranked = sorted(range(len(train_predictions)), key=lambda i: (-train_predictions[i]["confidence"], train_predictions[i]["video_id"], train_predictions[i]["time_sec"]))
        matched, _ = ranked_matches(train_gt, train_predictions, "Pass", 1.0)
        targets = np.zeros(len(train_predictions), dtype=np.float64)
        targets[ranked] = matched
        model = fit_logistic(train_features, targets)
        trained_scores = predict(train_features, model)
        threshold = train_threshold(trained_scores, np.array([item["confidence"] for item in train_predictions]), config["baseline_operating_threshold"])
        test_predictions = [item for item in load_predictions(root, test_ids) if item["label"] == "Pass"]
        test_features, test_score_hashes = build_features(test_predictions, args.scores_root)
        reranked = with_scores(test_predictions, predict(test_features, model))
        metrics = pass_metrics(test_gt, reranked, config["tolerances_sec"], threshold)
        baseline = json.loads((frozen_fold / "baseline_pass_metrics.json").read_text(encoding="utf-8"))
        result = {
            "fold_id": fold_id,
            "train_video_ids": sorted(train_ids),
            "test_video_ids": sorted(test_ids),
            "train_gt_pass": len(train_gt),
            "test_gt_pass": len(test_gt),
            "train_scores_sha256": train_score_hashes,
            "test_scores_sha256": test_score_hashes,
            "train_threshold": threshold,
            "baseline": baseline["tolerances"],
            "reranked": metrics,
            "model": model,
        }
        fold_output = args.output_dir / fold_id
        fold_output.mkdir(parents=True)
        predictions_path = fold_output / "reranked_pass_events.json"
        predictions_path.write_text(json.dumps(reranked, ensure_ascii=False, indent=2), encoding="utf-8")
        result["reranked_predictions_sha256"] = sha256(predictions_path)
        results.append(result)
    (args.output_dir / "comparison.json").write_text(json.dumps({
        "schema_version": 1,
        "method": "Pass-only logistic reranking of frozen candidate peaks; train labels are Bepro one-to-one matches at ±1s",
        "threshold_rule": "match baseline count above 0.2 on the training match, then apply fixed threshold to test match",
        "config_sha256": sha256(args.config),
        "frozen_manifest_sha256": sha256(args.frozen_dir / "manifest.json"),
        "folds": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        baseline = result["baseline"]["1"]
        improved = result["reranked"]["1"]
        print(f'{result["fold_id"]}: baseline AP={baseline["ap"]:.3f} P={baseline["precision"]:.3f} R={baseline["recall"]:.3f}; reranked AP={improved["ap"]:.3f} P={improved["precision"]:.3f} R={improved["recall"]:.3f}')


if __name__ == "__main__":
    main()
