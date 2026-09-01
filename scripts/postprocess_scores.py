"""Convert saved ensemble frame scores into Pass/Drive event candidates.

This is a CPU-only, repeatable postprocessing step. It never changes the raw
scores archive and refuses to overwrite an existing event export.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks


DISPLAY_LABELS = {"PASS": "Pass", "DRIVE": "Drive"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def format_timecode(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    value = timedelta(milliseconds=milliseconds)
    total_seconds, millisecond = divmod(value.days * 86400000 + value.seconds * 1000 + value.microseconds // 1000, 1000)
    hours, remaining = divmod(total_seconds, 3600)
    minutes, secs = divmod(remaining, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecond:03d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", required=True, type=Path)
    parser.add_argument("--inference-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--gauss-sigma", type=float, default=3.0)
    parser.add_argument("--min-height", type=float, default=0.2)
    parser.add_argument("--min-distance-frames", type=int, default=15)
    return parser.parse_args()


def load_arrays(path: Path) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    with np.load(path) as data:
        frame_indexes = data["frame_indexes"]
        scores = data["ensemble_scores"]
        labels = tuple(str(label) for label in data["class_names"].tolist())
    if frame_indexes.ndim != 1 or scores.ndim != 2 or scores.shape[0] != len(frame_indexes):
        raise ValueError("scores.npz 的帧索引或集成分数形状不合法")
    if scores.shape[1] != len(labels) or set(labels) != set(DISPLAY_LABELS):
        raise ValueError(f"不支持的类别：{labels}")
    if not np.all(np.diff(frame_indexes) > 0) or not np.isfinite(scores).all():
        raise ValueError("分数帧号非递增或含有非有限值")
    return frame_indexes, scores, labels


def main() -> None:
    args = parse_args()
    if args.gauss_sigma <= 0 or args.min_height < 0 or args.min_distance_frames < 1:
        raise ValueError("后处理参数必须为正数，min-height 可为 0")
    if not args.scores.is_file() or not args.inference_manifest.is_file():
        raise FileNotFoundError("scores 或推理 manifest 不存在")

    output_paths = [
        args.output_dir / "events.json",
        args.output_dir / "events.csv",
        args.output_dir / "postprocess_manifest.json",
    ]
    if any(path.exists() for path in output_paths):
        raise FileExistsError("后处理输出已存在；拒绝覆盖，请使用新的目录")

    inference_manifest = json.loads(args.inference_manifest.read_text(encoding="utf-8"))
    fps = float(inference_manifest["input"]["fps"])
    if fps <= 0:
        raise ValueError("推理 manifest 的 FPS 不合法")
    frame_indexes, scores, labels = load_arrays(args.scores)
    parameters = {
        "gauss_sigma": args.gauss_sigma,
        "min_height": args.min_height,
        "min_distance_frames": args.min_distance_frames,
        "input_score": "ensemble_scores",
    }

    unsorted_events: list[dict[str, Any]] = []
    for class_index, stored_label in enumerate(labels):
        smoothed = gaussian_filter1d(scores[:, class_index], sigma=args.gauss_sigma)
        peak_indexes, properties = find_peaks(
            smoothed,
            height=args.min_height,
            distance=args.min_distance_frames,
        )
        for local_index, confidence in zip(peak_indexes.tolist(), properties["peak_heights"].tolist()):
            frame_index = int(frame_indexes[local_index])
            time_sec = frame_index / fps
            unsorted_events.append(
                {
                    "frame_index": frame_index,
                    "time_sec": time_sec,
                    "timecode": format_timecode(time_sec),
                    "label": DISPLAY_LABELS[stored_label],
                    "confidence": float(confidence),
                    "visibility": "VISIBLE",
                    "review_status": "unreviewed",
                    "comment": "",
                }
            )

    events = sorted(unsorted_events, key=lambda event: (event["time_sec"], event["label"]))
    for event_index, event in enumerate(events, start=1):
        event["event_id"] = f"event-{event_index:06d}"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with output_paths[0].open("w", encoding="utf-8") as file:
        json.dump(events, file, ensure_ascii=False, indent=2)
    fields = ["event_id", "time_sec", "timecode", "frame_index", "label", "confidence", "visibility", "review_status", "comment"]
    with output_paths[1].open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(events)
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "inference_manifest": str(args.inference_manifest.resolve()),
        "inference_manifest_sha256": sha256_file(args.inference_manifest),
        "scores_path": str(args.scores.resolve()),
        "scores_sha256": sha256_file(args.scores),
        "parameters": parameters,
        "num_events": len(events),
        "events_by_label": {label: sum(event["label"] == label for event in events) for label in DISPLAY_LABELS.values()},
    }
    output_paths[2].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
