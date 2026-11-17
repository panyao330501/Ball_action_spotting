"""Select reproducible Pass examples for manual U18 evaluation review."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--proxy-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def timecode(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def separated(rows: list[dict[str, str]], count: int, gap_sec: float = 10.0) -> list[dict[str, str]]:
    chosen: list[dict[str, str]] = []
    for row in rows:
        value = float(row["prediction_time_sec"] or row["gt_time_sec"])
        if all(abs(value - float(item["prediction_time_sec"] or item["gt_time_sec"])) >= gap_sec for item in chosen):
            chosen.append(row)
            if len(chosen) == count:
                break
    return chosen


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"拒绝覆盖既有审查表：{args.output}")
    with args.matches.open(encoding="utf-8-sig", newline="") as file:
        matches = list(csv.DictReader(file))
    gt = {
        item["event_id"]: item
        for item in json.loads(args.ground_truth.read_text(encoding="utf-8"))
    }
    proxy = {
        item["video_id"]: item
        for item in json.loads(args.proxy_manifest.read_text(encoding="utf-8"))["videos"]
    }
    selected: list[dict[str, str]] = []
    for video_id in sorted(proxy):
        rows = [row for row in matches if row["video_id"] == video_id and row["label"] == "Pass"]
        fp = separated(
            sorted((row for row in rows if row["status"] == "FP"), key=lambda row: -float(row["confidence"])),
            3,
        )
        far_fn = sorted(
            (
                row for row in rows
                if row["status"] == "FN" and gt[row["gt_event_id"]]["distance_band"] == "far"
            ),
            key=lambda row: float(row["gt_time_sec"]),
        )
        # Spread far-side misses across the half, then preserve chronological order.
        targets = [0.2, 0.5, 0.8]
        fn: list[dict[str, str]] = []
        for fraction in targets:
            if not far_fn:
                break
            anchor = float(far_fn[round((len(far_fn) - 1) * fraction)]["gt_time_sec"])
            candidates = sorted(far_fn, key=lambda row: abs(float(row["gt_time_sec"]) - anchor))
            next_row = next(
                (
                    row for row in candidates
                    if all(abs(float(row["gt_time_sec"]) - float(item["gt_time_sec"])) >= 10 for item in fn)
                ),
                None,
            )
            if next_row is not None:
                fn.append(next_row)
        tp = separated(
            sorted((row for row in rows if row["status"] == "TP"), key=lambda row: -float(row["confidence"])),
            1,
        )
        for row in [*fp, *fn, *tp]:
            event = gt.get(row["gt_event_id"])
            seconds = float(row["prediction_time_sec"] or row["gt_time_sec"])
            selected.append(
                {
                    "review_id": f"u18-review-{len(selected) + 1:03d}",
                    "video_id": video_id,
                    "label": "Pass",
                    "algorithmic_status": row["status"],
                    "source_time_sec": f"{seconds:.3f}",
                    "source_timecode": timecode(seconds),
                    "confidence": row["confidence"],
                    "gt_event_id": row["gt_event_id"],
                    "distance_band": event["distance_band"] if event else "",
                    "source_video": proxy[video_id]["source_path"],
                    "review_start_sec": f"{max(0.0, seconds - 5.0):.3f}",
                    "review_end_sec": f"{min(float(proxy[video_id]['inference_end_sec']), seconds + 5.0):.3f}",
                    "human_visibility": "",
                    "human_judgment": "",
                    "human_comment": "",
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    print(f"wrote {len(selected)} Pass review rows to {args.output}")


if __name__ == "__main__":
    main()
