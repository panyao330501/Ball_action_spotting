"""Generate reviewable BAS miss candidates from saved dense scores.

The CPU-only generator keeps the official event export unchanged. It mines
sub-threshold ensemble peaks and fold disagreements, optionally unions a
normalized tracking-candidate file, and reports how many user-provided seed
misses are recovered. Candidate records are review prompts, never GT.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks


DISPLAY_LABELS = {"PASS": "Pass", "DRIVE": "Drive"}
ALLOWED_TRACKING_LABELS = {"Pass", "Drive", "Unknown"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", required=True, type=Path)
    parser.add_argument("--inference-manifest", required=True, type=Path)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--artifact-root", type=Path, default=Path("artifacts/candidate_mining")
    )
    parser.add_argument("--seed-misses", type=Path)
    parser.add_argument("--tracking-candidates", type=Path)
    parser.add_argument("--gauss-sigma", type=float, default=3.0)
    parser.add_argument("--min-ensemble-height", type=float, default=0.05)
    parser.add_argument("--high-ensemble-height", type=float, default=0.12)
    parser.add_argument("--official-height", type=float, default=0.2)
    parser.add_argument("--fold-peak-height", type=float, default=0.2)
    parser.add_argument("--min-distance-frames", type=int, default=15)
    parser.add_argument("--official-match-sec", type=float, default=1.0)
    parser.add_argument("--proposal-dedupe-sec", type=float, default=0.3)
    parser.add_argument("--tracking-match-sec", type=float, default=1.0)
    parser.add_argument("--seed-match-sec", type=float, default=1.0)
    parser.add_argument("--review-pre-sec", type=float, default=3.0)
    parser.add_argument("--review-post-sec", type=float, default=4.0)
    parser.add_argument("--window-merge-gap-sec", type=float, default=2.0)
    parser.add_argument("--max-window-duration-sec", type=float, default=15.0)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def format_timecode(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"Invalid non-negative time: {seconds}")
    milliseconds = int(round(seconds * 1000))
    total_seconds, millis = divmod(milliseconds, 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def require_probability(value: Any, field: str, allow_blank: bool = False) -> float | None:
    if allow_blank and (value is None or str(value).strip() == "" or pd.isna(value)):
        return None
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"{field} must be a finite value in [0, 1]")
    return number


def load_score_arrays(
    path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[str, ...]]:
    with np.load(path) as data:
        frame_indexes = data["frame_indexes"].astype(np.int64)
        ensemble_scores = data["ensemble_scores"].astype(np.float64)
        fold_scores = data["fold_scores"].astype(np.float64)
        labels = tuple(str(label) for label in data["class_names"].tolist())
    if frame_indexes.ndim != 1 or ensemble_scores.shape != (len(frame_indexes), len(labels)):
        raise ValueError("scores.npz has invalid frame_indexes or ensemble_scores")
    expected_fold_shape = (len(frame_indexes), fold_scores.shape[1], len(labels))
    if fold_scores.ndim != 3 or fold_scores.shape != expected_fold_shape:
        raise ValueError("scores.npz has invalid fold_scores")
    if set(labels) != set(DISPLAY_LABELS):
        raise ValueError(f"Unsupported classes: {labels}")
    if not np.all(np.diff(frame_indexes) > 0):
        raise ValueError("frame_indexes must be strictly increasing")
    if not np.isfinite(ensemble_scores).all() or not np.isfinite(fold_scores).all():
        raise ValueError("scores.npz contains non-finite scores")
    return frame_indexes, ensemble_scores, fold_scores, labels


def load_official_events(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("events JSON must contain a list")
    events: list[dict[str, Any]] = []
    for event in raw:
        label = str(event["label"])
        time_sec = float(event["time_sec"])
        if label not in DISPLAY_LABELS.values() or not math.isfinite(time_sec):
            raise ValueError("events JSON contains an invalid event")
        events.append({"event_id": str(event["event_id"]), "label": label, "time_sec": time_sec})
    return events


def nearest_official(
    events: Iterable[dict[str, Any]], time_sec: float, label: str
) -> tuple[dict[str, Any] | None, float | None]:
    if label == "Unknown":
        matches = list(events)
    else:
        matches = [event for event in events if event["label"] == label]
    if not matches:
        return None, None
    nearest = min(matches, key=lambda event: abs(event["time_sec"] - time_sec))
    return nearest, float(nearest["time_sec"] - time_sec)


def smooth_score_arrays(
    ensemble_scores: np.ndarray, fold_scores: np.ndarray, sigma: float
) -> tuple[np.ndarray, np.ndarray]:
    ensemble_smoothed = np.column_stack(
        [gaussian_filter1d(ensemble_scores[:, index], sigma=sigma) for index in range(ensemble_scores.shape[1])]
    )
    fold_smoothed = np.empty_like(fold_scores)
    for fold_index in range(fold_scores.shape[1]):
        for class_index in range(fold_scores.shape[2]):
            fold_smoothed[:, fold_index, class_index] = gaussian_filter1d(
                fold_scores[:, fold_index, class_index], sigma=sigma
            )
    return ensemble_smoothed, fold_smoothed


def score_features(
    local_index: int,
    class_index: int,
    ensemble_smoothed: np.ndarray,
    fold_smoothed: np.ndarray,
    official_height: float,
) -> dict[str, Any]:
    fold_values = fold_smoothed[local_index, :, class_index]
    return {
        "ensemble_score": float(ensemble_smoothed[local_index, class_index]),
        "fold_mean_score": float(np.mean(fold_values)),
        "fold_max_score": float(np.max(fold_values)),
        "fold_std_score": float(np.std(fold_values)),
        "folds_above_official": int(np.sum(fold_values >= official_height)),
    }


def proposal_at(
    local_index: int,
    class_index: int,
    source: str,
    frame_indexes: np.ndarray,
    fps: float,
    labels: tuple[str, ...],
    ensemble_smoothed: np.ndarray,
    fold_smoothed: np.ndarray,
    official_height: float,
) -> dict[str, Any]:
    time_sec = float(frame_indexes[local_index] / fps)
    label = DISPLAY_LABELS[labels[class_index]]
    proposal = {
        "time_sec": time_sec,
        "timecode": format_timecode(time_sec),
        "frame_index": int(frame_indexes[local_index]),
        "label": label,
        "evidence_sources": [source],
        "tracking_score": None,
        "far_side_score": None,
        "tracking_confidence": None,
        "tracking_reason": "",
    }
    proposal.update(
        score_features(
            local_index,
            class_index,
            ensemble_smoothed,
            fold_smoothed,
            official_height,
        )
    )
    return proposal


def mine_bas_proposals(
    frame_indexes: np.ndarray,
    fps: float,
    labels: tuple[str, ...],
    ensemble_smoothed: np.ndarray,
    fold_smoothed: np.ndarray,
    min_ensemble_height: float,
    official_height: float,
    fold_peak_height: float,
    min_distance_frames: int,
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for class_index in range(len(labels)):
        ensemble_peaks, properties = find_peaks(
            ensemble_smoothed[:, class_index],
            height=min_ensemble_height,
            distance=min_distance_frames,
        )
        for local_index, height in zip(ensemble_peaks.tolist(), properties["peak_heights"].tolist()):
            if float(height) < official_height:
                proposals.append(
                    proposal_at(
                        local_index,
                        class_index,
                        "ensemble_low_peak",
                        frame_indexes,
                        fps,
                        labels,
                        ensemble_smoothed,
                        fold_smoothed,
                        official_height,
                    )
                )
        for fold_index in range(fold_smoothed.shape[1]):
            fold_peaks, _ = find_peaks(
                fold_smoothed[:, fold_index, class_index],
                height=fold_peak_height,
                distance=min_distance_frames,
            )
            for local_index in fold_peaks.tolist():
                if ensemble_smoothed[local_index, class_index] < official_height:
                    proposals.append(
                        proposal_at(
                            local_index,
                            class_index,
                            "fold_disagreement",
                            frame_indexes,
                            fps,
                            labels,
                            ensemble_smoothed,
                            fold_smoothed,
                            official_height,
                        )
                    )
    return proposals


def merge_candidate_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["evidence_sources"] = sorted(
        set(target.get("evidence_sources", [])) | set(source.get("evidence_sources", []))
    )
    if source.get("tracking_score") is not None:
        target["tracking_score"] = max(
            float(source["tracking_score"]), float(target.get("tracking_score") or 0.0)
        )
        target["far_side_score"] = source.get("far_side_score")
        target["tracking_confidence"] = source.get("tracking_confidence")
        target["tracking_reason"] = source.get("tracking_reason", "")


def dedupe_proposals(
    proposals: list[dict[str, Any]], dedupe_sec: float
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for proposal in sorted(proposals, key=lambda item: (item["label"], item["time_sec"])):
        matching = next(
            (
                candidate
                for candidate in reversed(merged)
                if candidate["label"] == proposal["label"]
                and abs(candidate["time_sec"] - proposal["time_sec"]) <= dedupe_sec
            ),
            None,
        )
        if matching is None:
            merged.append(dict(proposal))
            continue
        preferred = proposal if proposal["ensemble_score"] > matching["ensemble_score"] else matching
        other = matching if preferred is proposal else proposal
        if preferred is proposal:
            index = merged.index(matching)
            merged[index] = dict(proposal)
            matching = merged[index]
        merge_candidate_fields(matching, other)
    return sorted(merged, key=lambda item: (item["time_sec"], item["label"]))


def normalize_label(value: Any, allow_unknown: bool) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)) or str(value).strip() == "":
        if allow_unknown:
            return "Unknown"
        raise ValueError("label/action is blank")
    label = str(value).strip().lower()
    mapping = {"pass": "Pass", "drive": "Drive", "unknown": "Unknown"}
    if label not in mapping or (mapping[label] == "Unknown" and not allow_unknown):
        raise ValueError(f"Unsupported label/action: {value!r}")
    return mapping[label]


def load_tracking_candidates(path: Path | None, interval_end_sec: float) -> list[dict[str, Any]]:
    if path is None:
        return []
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        frame = pd.DataFrame(raw)
    elif path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    else:
        raise ValueError("tracking candidates must be CSV or JSON")
    if "time_sec" not in frame.columns:
        raise ValueError("tracking candidates require time_sec")
    results: list[dict[str, Any]] = []
    for row_number, row in frame.iterrows():
        time_sec = float(row["time_sec"])
        if not math.isfinite(time_sec) or not 0 <= time_sec <= interval_end_sec:
            raise ValueError(f"tracking row {row_number + 2} has invalid time_sec")
        label = normalize_label(row.get("label"), allow_unknown=True)
        record = {
            "time_sec": time_sec,
            "label": label,
            "tracking_score": require_probability(row.get("tracking_score", 0.0), "tracking_score"),
            "far_side_score": require_probability(
                row.get("far_side_score"), "far_side_score", allow_blank=True
            ),
            "tracking_confidence": require_probability(
                row.get("tracking_confidence"), "tracking_confidence", allow_blank=True
            ),
            "tracking_reason": str(row.get("reason", "")).strip(),
        }
        results.append(record)
    return results


def add_tracking_proposals(
    candidates: list[dict[str, Any]],
    tracking_rows: list[dict[str, Any]],
    frame_indexes: np.ndarray,
    fps: float,
    labels: tuple[str, ...],
    ensemble_smoothed: np.ndarray,
    fold_smoothed: np.ndarray,
    official_height: float,
    official_events: list[dict[str, Any]],
    official_match_sec: float,
    tracking_match_sec: float,
) -> None:
    times = frame_indexes / fps
    for tracking in tracking_rows:
        nearest, delta = nearest_official(official_events, tracking["time_sec"], tracking["label"])
        if nearest is not None and abs(float(delta)) <= official_match_sec:
            continue
        matching = min(
            (
                candidate
                for candidate in candidates
                if tracking["label"] == "Unknown" or candidate["label"] == tracking["label"]
            ),
            key=lambda candidate: abs(candidate["time_sec"] - tracking["time_sec"]),
            default=None,
        )
        if matching is not None and abs(matching["time_sec"] - tracking["time_sec"]) <= tracking_match_sec:
            merge_candidate_fields(
                matching,
                dict(tracking, evidence_sources=["tracking_change"]),
            )
            continue
        local_index = int(np.argmin(np.abs(times - tracking["time_sec"])))
        if tracking["label"] == "Unknown":
            class_index = int(np.argmax(ensemble_smoothed[local_index]))
            label = "Unknown"
        else:
            stored_label = next(key for key, value in DISPLAY_LABELS.items() if value == tracking["label"])
            class_index = labels.index(stored_label)
            label = tracking["label"]
        proposal = proposal_at(
            local_index,
            class_index,
            "tracking_change",
            frame_indexes,
            fps,
            labels,
            ensemble_smoothed,
            fold_smoothed,
            official_height,
        )
        proposal.update(tracking)
        proposal["label"] = label
        proposal["suggested_label"] = DISPLAY_LABELS[labels[class_index]]
        candidates.append(proposal)


def load_seed_misses(path: Path | None, interval_end_sec: float) -> list[dict[str, Any]]:
    if path is None:
        return []
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        frame = pd.read_excel(path)
    elif suffix == ".csv":
        frame = pd.read_csv(path)
    else:
        raise ValueError("seed misses must be XLSX or CSV")
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    required = {"hour", "min", "sec", "action", "side"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"seed misses are missing columns: {sorted(missing)}")
    hours = pd.to_numeric(frame["hour"], errors="coerce").ffill()
    minutes = pd.to_numeric(frame["min"], errors="coerce").ffill()
    seconds = pd.to_numeric(frame["sec"], errors="coerce")
    if hours.isna().any() or minutes.isna().any() or seconds.isna().any():
        raise ValueError("seed miss hour/min/sec values cannot be resolved")
    seeds: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        time_sec = float(hours.iloc[index] * 3600 + minutes.iloc[index] * 60 + seconds.iloc[index])
        if not 0 <= time_sec <= interval_end_sec:
            raise ValueError(f"seed miss row {index + 2} is outside the source interval")
        side = str(row["side"]).strip().lower()
        if side not in {"far", "near", "unknown"}:
            raise ValueError(f"seed miss row {index + 2} has unsupported side: {side!r}")
        seeds.append(
            {
                "seed_id": f"seed-{index + 1:06d}",
                "time_sec": time_sec,
                "timecode": format_timecode(time_sec),
                "label": normalize_label(row["action"], allow_unknown=False),
                "side": side,
            }
        )
    return seeds


def assign_priority(
    candidate: dict[str, Any],
    min_ensemble_height: float,
    high_ensemble_height: float,
    official_height: float,
) -> str:
    tracking_score = float(candidate.get("tracking_score") or 0.0)
    far_side_score = float(candidate.get("far_side_score") or 0.0)
    if (
        candidate["ensemble_score"] >= high_ensemble_height
        or candidate["folds_above_official"] >= 2
        or (tracking_score >= 0.7 and far_side_score >= 0.5)
    ):
        return "high"
    if (
        candidate["ensemble_score"] >= min_ensemble_height
        or candidate["fold_max_score"] >= official_height
        or tracking_score >= 0.4
    ):
        return "medium"
    return "low"


def finalize_candidates(
    candidates: list[dict[str, Any]],
    official_events: list[dict[str, Any]],
    official_match_sec: float,
    min_ensemble_height: float,
    high_ensemble_height: float,
    official_height: float,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: (item["time_sec"], item["label"])):
        nearest, delta = nearest_official(
            official_events, candidate["time_sec"], candidate["label"]
        )
        if nearest is not None and abs(float(delta)) <= official_match_sec:
            continue
        candidate = dict(candidate)
        candidate["nearest_official_event_id"] = nearest["event_id"] if nearest else ""
        candidate["nearest_official_delta_sec"] = delta
        candidate["priority"] = assign_priority(
            candidate, min_ensemble_height, high_ensemble_height, official_height
        )
        candidate["review_status"] = "unreviewed"
        candidate["human_label"] = ""
        candidate["corrected_time_sec"] = None
        candidate["visibility"] = ""
        candidate["comment"] = ""
        filtered.append(candidate)
    for index, candidate in enumerate(filtered, start=1):
        candidate["candidate_id"] = f"candidate-{index:06d}"
        candidate.setdefault("suggested_label", candidate["label"])
        candidate["evidence_sources"] = sorted(set(candidate["evidence_sources"]))
    return filtered


def build_review_windows(
    candidates: list[dict[str, Any]],
    interval_end_sec: float,
    pre_sec: float,
    post_sec: float,
    merge_gap_sec: float,
    max_duration_sec: float,
) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: item["time_sec"]):
        proposed = current + [candidate]
        start = max(0.0, proposed[0]["time_sec"] - pre_sec)
        end = min(interval_end_sec, proposed[-1]["time_sec"] + post_sec)
        current_end = (
            min(interval_end_sec, current[-1]["time_sec"] + post_sec)
            if current
            else -math.inf
        )
        candidate_start = max(0.0, candidate["time_sec"] - pre_sec)
        close_enough = not current or candidate_start - current_end <= merge_gap_sec
        if current and (not close_enough or end - start > max_duration_sec):
            groups.append(current)
            current = [candidate]
        else:
            current = proposed
    if current:
        groups.append(current)

    windows: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        source_start = max(0.0, group[0]["time_sec"] - pre_sec)
        source_end = min(interval_end_sec, group[-1]["time_sec"] + post_sec)
        priority = min((candidate["priority"] for candidate in group), key=PRIORITY_ORDER.get)
        windows.append(
            {
                "window_id": f"window-{index:06d}",
                "source_start_sec": source_start,
                "source_end_sec": source_end,
                "source_start_timecode": format_timecode(source_start),
                "source_end_timecode": format_timecode(source_end),
                "duration_sec": source_end - source_start,
                "priority": priority,
                "candidate_ids": [candidate["candidate_id"] for candidate in group],
            }
        )
    ordered = sorted(windows, key=lambda item: (PRIORITY_ORDER[item["priority"]], item["source_start_sec"]))
    for review_order, window in enumerate(ordered, start=1):
        window["review_order"] = review_order
    review_order_by_candidate = {
        candidate_id: window["review_order"]
        for window in windows
        for candidate_id in window["candidate_ids"]
    }
    for candidate in candidates:
        candidate["review_order"] = review_order_by_candidate[candidate["candidate_id"]]
    return windows


def seed_coverage(
    seeds: list[dict[str, Any]], candidates: list[dict[str, Any]], match_sec: float
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for seed in seeds:
        same_label = [candidate for candidate in candidates if candidate["label"] == seed["label"]]
        nearest = min(
            same_label,
            key=lambda candidate: abs(candidate["time_sec"] - seed["time_sec"]),
            default=None,
        )
        delta = None if nearest is None else float(nearest["time_sec"] - seed["time_sec"])
        entries.append(
            {
                **seed,
                "covered": nearest is not None and abs(float(delta)) <= match_sec,
                "nearest_candidate_id": nearest["candidate_id"] if nearest else "",
                "nearest_candidate_delta_sec": delta,
                "nearest_candidate_ensemble_score": nearest["ensemble_score"] if nearest else None,
            }
        )
    covered = sum(entry["covered"] for entry in entries)
    return {
        "description": "Seed coverage is a workflow check, not formal recall.",
        "match_tolerance_sec": match_sec,
        "num_seeds": len(entries),
        "num_covered": covered,
        "coverage_rate": covered / len(entries) if entries else None,
        "entries": entries,
    }


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return value


def write_csv(path: Path, records: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({field: csv_value(record.get(field)) for field in fields})


def validate_args(args: argparse.Namespace) -> None:
    probabilities = [
        args.min_ensemble_height,
        args.high_ensemble_height,
        args.official_height,
        args.fold_peak_height,
    ]
    if not all(0 <= value <= 1 for value in probabilities):
        raise ValueError("score thresholds must be in [0, 1]")
    if not args.min_ensemble_height <= args.high_ensemble_height < args.official_height:
        raise ValueError("expected min_ensemble_height <= high_ensemble_height < official_height")
    positive = [
        args.gauss_sigma,
        args.min_distance_frames,
        args.official_match_sec,
        args.proposal_dedupe_sec,
        args.tracking_match_sec,
        args.seed_match_sec,
        args.max_window_duration_sec,
    ]
    if any(value <= 0 for value in positive):
        raise ValueError("sigma, distances, and tolerances must be positive")
    if args.review_pre_sec < 0 or args.review_post_sec < 0 or args.window_merge_gap_sec < 0:
        raise ValueError("review context and window merge gap must be non-negative")


def main() -> None:
    args = parse_args()
    validate_args(args)
    inputs = [args.scores, args.inference_manifest, args.events]
    optional_inputs = [path for path in (args.seed_misses, args.tracking_candidates) if path]
    for path in inputs + optional_inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir = (args.artifact_root / args.run_id).resolve()
    if output_dir.exists():
        raise FileExistsError(f"candidate run directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    inference_manifest = json.loads(args.inference_manifest.read_text(encoding="utf-8"))
    fps = float(inference_manifest["input"]["fps"])
    interval_end_sec = float(inference_manifest["input"]["requested_interval_sec"][1])
    frame_indexes, ensemble_scores, fold_scores, labels = load_score_arrays(args.scores)
    ensemble_smoothed, fold_smoothed = smooth_score_arrays(
        ensemble_scores, fold_scores, args.gauss_sigma
    )
    official_events = load_official_events(args.events)
    proposals = mine_bas_proposals(
        frame_indexes,
        fps,
        labels,
        ensemble_smoothed,
        fold_smoothed,
        args.min_ensemble_height,
        args.official_height,
        args.fold_peak_height,
        args.min_distance_frames,
    )
    candidates = dedupe_proposals(proposals, args.proposal_dedupe_sec)
    tracking_rows = load_tracking_candidates(args.tracking_candidates, interval_end_sec)
    add_tracking_proposals(
        candidates,
        tracking_rows,
        frame_indexes,
        fps,
        labels,
        ensemble_smoothed,
        fold_smoothed,
        args.official_height,
        official_events,
        args.official_match_sec,
        args.tracking_match_sec,
    )
    candidates = dedupe_proposals(candidates, args.proposal_dedupe_sec)
    candidates = finalize_candidates(
        candidates,
        official_events,
        args.official_match_sec,
        args.min_ensemble_height,
        args.high_ensemble_height,
        args.official_height,
    )
    windows = build_review_windows(
        candidates,
        interval_end_sec,
        args.review_pre_sec,
        args.review_post_sec,
        args.window_merge_gap_sec,
        args.max_window_duration_sec,
    )
    seeds = load_seed_misses(args.seed_misses, interval_end_sec)
    coverage = seed_coverage(seeds, candidates, args.seed_match_sec)

    candidate_fields = [
        "candidate_id",
        "review_order",
        "time_sec",
        "timecode",
        "frame_index",
        "label",
        "suggested_label",
        "priority",
        "ensemble_score",
        "fold_mean_score",
        "fold_max_score",
        "fold_std_score",
        "folds_above_official",
        "evidence_sources",
        "tracking_score",
        "far_side_score",
        "tracking_confidence",
        "tracking_reason",
        "nearest_official_event_id",
        "nearest_official_delta_sec",
        "review_status",
        "human_label",
        "corrected_time_sec",
        "visibility",
        "comment",
    ]
    window_fields = [
        "window_id",
        "review_order",
        "priority",
        "source_start_sec",
        "source_end_sec",
        "source_start_timecode",
        "source_end_timecode",
        "duration_sec",
        "candidate_ids",
    ]
    (output_dir / "candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(output_dir / "candidates.csv", candidates, candidate_fields)
    (output_dir / "review_windows.json").write_text(
        json.dumps(windows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(output_dir / "review_windows.csv", windows, window_fields)
    (output_dir / "seed_coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    parameters = {
        "gauss_sigma": args.gauss_sigma,
        "min_ensemble_height": args.min_ensemble_height,
        "high_ensemble_height": args.high_ensemble_height,
        "official_height": args.official_height,
        "fold_peak_height": args.fold_peak_height,
        "min_distance_frames": args.min_distance_frames,
        "official_match_sec": args.official_match_sec,
        "proposal_dedupe_sec": args.proposal_dedupe_sec,
        "tracking_match_sec": args.tracking_match_sec,
        "seed_match_sec": args.seed_match_sec,
        "review_context_sec": {"pre": args.review_pre_sec, "post": args.review_post_sec},
        "window_merge_gap_sec": args.window_merge_gap_sec,
        "max_window_duration_sec": args.max_window_duration_sec,
    }
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "run_id": args.run_id,
        "candidate_semantics": "review prompts only; not predictions and not GT",
        "inputs": {
            "scores": str(args.scores.resolve()),
            "scores_sha256": sha256_file(args.scores),
            "inference_manifest": str(args.inference_manifest.resolve()),
            "inference_manifest_sha256": sha256_file(args.inference_manifest),
            "official_events": str(args.events.resolve()),
            "official_events_sha256": sha256_file(args.events),
            "seed_misses": str(args.seed_misses.resolve()) if args.seed_misses else None,
            "seed_misses_sha256": sha256_file(args.seed_misses) if args.seed_misses else None,
            "tracking_candidates": str(args.tracking_candidates.resolve()) if args.tracking_candidates else None,
            "tracking_candidates_sha256": sha256_file(args.tracking_candidates) if args.tracking_candidates else None,
            "tracking_status": "provided" if args.tracking_candidates else "not_provided",
        },
        "parameters": parameters,
        "results": {
            "num_candidates": len(candidates),
            "candidates_by_label": dict(Counter(candidate["label"] for candidate in candidates)),
            "candidates_by_priority": dict(Counter(candidate["priority"] for candidate in candidates)),
            "candidates_by_evidence": dict(
                Counter(source for candidate in candidates for source in candidate["evidence_sources"])
            ),
            "num_review_windows": len(windows),
            "review_duration_sec": sum(window["duration_sec"] for window in windows),
            "seed_coverage": {key: coverage[key] for key in ("num_seeds", "num_covered", "coverage_rate")},
        },
        "outputs": {
            "candidates_json": "candidates.json",
            "candidates_csv": "candidates.csv",
            "review_windows_json": "review_windows.json",
            "review_windows_csv": "review_windows.csv",
            "seed_coverage_json": "seed_coverage.json",
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"output_dir": str(output_dir), **manifest["results"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
