"""Evaluate timestamped Pass/Drive predictions against evaluable U18 GT."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


LABELS = ("Pass", "Drive")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--predictions-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--tolerances", default="0.5,1.0,2.0")
    parser.add_argument("--operating-threshold", type=float, default=0.2)
    return parser.parse_args()


def load_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"JSON 顶层必须为列表：{path}")
    return data


def validate_gt(events: list[dict[str, Any]]) -> None:
    ids: set[str] = set()
    for event in events:
        if event.get("evaluation_status") != "evaluable":
            raise ValueError("正式评估输入只能包含 evaluation_status=evaluable 的 GT")
        if event.get("label") not in LABELS or not math.isfinite(float(event["source_time_sec"])):
            raise ValueError(f"GT 事件不合法：{event}")
        if event["event_id"] in ids:
            raise ValueError(f"GT event_id 重复：{event['event_id']}")
        ids.add(event["event_id"])


def load_predictions(root: Path, video_ids: Iterable[str]) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    for video_id in sorted(set(video_ids)):
        path = root / video_id / "events.json"
        if not path.is_file():
            raise FileNotFoundError(f"缺少预测：{path}")
        for raw in load_json_list(path):
            label = raw.get("label")
            confidence = float(raw.get("confidence"))
            time_sec = float(raw.get("time_sec"))
            if label not in LABELS or not math.isfinite(confidence) or not math.isfinite(time_sec):
                raise ValueError(f"预测事件不合法：{raw}")
            predictions.append(
                {
                    "video_id": video_id,
                    "event_id": raw.get("event_id", ""),
                    "label": label,
                    "time_sec": time_sec,
                    "confidence": confidence,
                }
            )
    return predictions


def ranked_matches(
    gt_events: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    label: str,
    tolerance: float,
) -> tuple[list[int], list[dict[str, Any] | None]]:
    gt_by_video: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in gt_events:
        if event["label"] == label:
            gt_by_video[event["video_id"]].append(event)
    unmatched = {video_id: set(range(len(items))) for video_id, items in gt_by_video.items()}
    ranked = sorted(
        (prediction for prediction in predictions if prediction["label"] == label),
        key=lambda prediction: (-prediction["confidence"], prediction["video_id"], prediction["time_sec"]),
    )
    true_positive: list[int] = []
    matched_gt: list[dict[str, Any] | None] = []
    for prediction in ranked:
        video_id = prediction["video_id"]
        candidates = [
            (abs(prediction["time_sec"] - gt_by_video[video_id][index]["source_time_sec"]), index)
            for index in unmatched.get(video_id, set())
        ]
        candidates = [candidate for candidate in candidates if candidate[0] <= tolerance]
        if not candidates:
            true_positive.append(0)
            matched_gt.append(None)
            continue
        _, gt_index = min(candidates)
        unmatched[video_id].remove(gt_index)
        true_positive.append(1)
        matched_gt.append(gt_by_video[video_id][gt_index])
    return true_positive, matched_gt


def average_precision(true_positive: list[int], num_gt: int) -> float:
    if num_gt == 0:
        return float("nan")
    if not true_positive:
        return 0.0
    cumulative_tp: list[int] = []
    running = 0
    for value in true_positive:
        running += value
        cumulative_tp.append(running)
    precision = [tp / rank for rank, tp in enumerate(cumulative_tp, start=1)]
    recall = [tp / num_gt for tp in cumulative_tp]
    envelope = precision[:]
    for index in range(len(envelope) - 2, -1, -1):
        envelope[index] = max(envelope[index], envelope[index + 1])
    ap = 0.0
    previous_recall = 0.0
    for current_recall, current_precision in zip(recall, envelope):
        if current_recall > previous_recall:
            ap += (current_recall - previous_recall) * current_precision
            previous_recall = current_recall
    return ap


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = quantile * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def recall_by_gt_distance_band(
    gt_events: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    tolerance: float,
    threshold: float,
) -> dict[str, dict[str, dict[str, float | int]]]:
    result: dict[str, dict[str, dict[str, float | int]]] = {}
    for label in LABELS:
        operating = [
            event
            for event in predictions
            if event["label"] == label and event["confidence"] >= threshold
        ]
        _, matches = ranked_matches(gt_events, operating, label, tolerance)
        matched_ids = {match["event_id"] for match in matches if match is not None}
        result[label] = {}
        for band in ("near", "mid", "far"):
            band_gt = [
                event
                for event in gt_events
                if event["label"] == label and event.get("distance_band") == band
            ]
            true_positive = sum(event["event_id"] in matched_ids for event in band_gt)
            result[label][band] = {
                "gt": len(band_gt),
                "tp": true_positive,
                "recall": true_positive / len(band_gt) if band_gt else 0.0,
            }
    return result


def evaluate_group(
    gt_events: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    tolerances: list[float],
    threshold: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {"gt_count": len(gt_events), "prediction_count": len(predictions), "tolerances": {}}
    for tolerance in tolerances:
        tolerance_result: dict[str, Any] = {"classes": {}}
        aps: list[float] = []
        for label in LABELS:
            class_gt = [event for event in gt_events if event["label"] == label]
            class_predictions = [event for event in predictions if event["label"] == label]
            ranked_tp, _ = ranked_matches(gt_events, predictions, label, tolerance)
            ap = average_precision(ranked_tp, len(class_gt))
            operating = [event for event in class_predictions if event["confidence"] >= threshold]
            operating_tp, operating_matches = ranked_matches(gt_events, operating, label, tolerance)
            tp = sum(operating_tp)
            fp = len(operating_tp) - tp
            fn = len(class_gt) - tp
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / len(class_gt) if class_gt else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            errors = [
                abs(prediction["time_sec"] - match["source_time_sec"])
                for prediction, match in zip(
                    sorted(operating, key=lambda item: (-item["confidence"], item["video_id"], item["time_sec"])),
                    operating_matches,
                )
                if match is not None
            ]
            tolerance_result["classes"][label] = {
                "gt": len(class_gt),
                "predictions_all": len(class_predictions),
                "ap": ap,
                "operating_threshold": threshold,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "median_abs_time_error_sec": percentile(errors, 0.5),
                "p90_abs_time_error_sec": percentile(errors, 0.9),
            }
            if not math.isnan(ap):
                aps.append(ap)
        tolerance_result["map"] = sum(aps) / len(aps) if aps else None
        tolerance_result["recall_by_gt_distance_band"] = recall_by_gt_distance_band(
            gt_events, predictions, tolerance, threshold
        )
        result["tolerances"][f"{tolerance:g}"] = tolerance_result
    return result


def operating_matches_rows(
    gt_events: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    tolerance: float,
    threshold: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in LABELS:
        operating = [event for event in predictions if event["label"] == label and event["confidence"] >= threshold]
        ranked = sorted(operating, key=lambda item: (-item["confidence"], item["video_id"], item["time_sec"]))
        tp, matches = ranked_matches(gt_events, operating, label, tolerance)
        matched_ids: set[str] = set()
        for prediction, is_tp, match in zip(ranked, tp, matches):
            if match is not None:
                matched_ids.add(match["event_id"])
            rows.append(
                {
                    "status": "TP" if is_tp else "FP",
                    "video_id": prediction["video_id"],
                    "label": label,
                    "prediction_time_sec": prediction["time_sec"],
                    "confidence": prediction["confidence"],
                    "gt_event_id": match["event_id"] if match else "",
                    "gt_time_sec": match["source_time_sec"] if match else "",
                    "abs_time_error_sec": abs(prediction["time_sec"] - match["source_time_sec"]) if match else "",
                }
            )
        for event in gt_events:
            if event["label"] == label and event["event_id"] not in matched_ids:
                rows.append(
                    {
                        "status": "FN",
                        "video_id": event["video_id"],
                        "label": label,
                        "prediction_time_sec": "",
                        "confidence": "",
                        "gt_event_id": event["event_id"],
                        "gt_time_sec": event["source_time_sec"],
                        "abs_time_error_sec": "",
                    }
                )
    rows.sort(key=lambda row: (row["video_id"], row["label"], float(row["gt_time_sec"] or row["prediction_time_sec"])))
    return rows


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖既有输出目录：{args.output_dir}")
    tolerances = sorted({float(value) for value in args.tolerances.split(",")})
    if not tolerances or any(value <= 0 for value in tolerances):
        raise ValueError("--tolerances 必须是正数列表")
    if not 0 <= args.operating_threshold <= 1:
        raise ValueError("--operating-threshold 必须位于 [0, 1]")

    gt_events = load_json_list(args.ground_truth)
    validate_gt(gt_events)
    predictions = load_predictions(args.predictions_root, (event["video_id"] for event in gt_events))
    video_ids = sorted({event["video_id"] for event in gt_events})
    metrics = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "metric_definition": "confidence-ranked one-to-one event AP with precision envelope; not claimed byte-identical to SoccerNet toolkit",
        "ground_truth": str(args.ground_truth.resolve()),
        "predictions_root": str(args.predictions_root.resolve()),
        "aggregate": evaluate_group(gt_events, predictions, tolerances, args.operating_threshold),
        "per_video": {
            video_id: evaluate_group(
                [event for event in gt_events if event["video_id"] == video_id],
                [event for event in predictions if event["video_id"] == video_id],
                tolerances,
                args.operating_threshold,
            )
            for video_id in video_ids
        },
    }
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = operating_matches_rows(gt_events, predictions, 1.0, args.operating_threshold)
    with (args.output_dir / "matches_at_1s.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(metrics["aggregate"], ensure_ascii=False))


if __name__ == "__main__":
    main()
