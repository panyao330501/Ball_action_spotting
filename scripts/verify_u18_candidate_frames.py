"""Verify the U18 frame shortlist and its source-frame time contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


def rows_from(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(directory: Path) -> dict[str, object]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for input_key, hash_key in (
        ("ground_truth", "ground_truth_sha256"),
        ("known_review", "known_review_sha256"),
    ):
        if sha256_file(Path(manifest[input_key])) != manifest[hash_key]:
            raise ValueError(f"input hash mismatch: {input_key}")
    if manifest.get("extra_exclusions") and sha256_file(Path(manifest["extra_exclusions"])) != manifest["extra_exclusions_sha256"]:
        raise ValueError("extra exclusion hash mismatch")
    if sha256_file(directory / "review.csv") != manifest["review_csv_sha256"]:
        raise ValueError("review.csv hash mismatch")
    rows = rows_from(directory / "review.csv")
    if not rows or len(rows) != len({row["event_id"] for row in rows}):
        raise ValueError("empty or duplicate event selection")
    if len(rows) != len(list((directory / "frames").glob("*.jpg"))) or len(rows) != len(list((directory / "previews").glob("*.jpg"))):
        raise ValueError("image count mismatch")
    gt = {row["event_id"]: row for row in rows_from(Path(manifest["ground_truth"]))}
    known = rows_from(Path(manifest["known_review"]))
    if manifest.get("extra_exclusions"):
        known += rows_from(Path(manifest["extra_exclusions"]))
    known_ids = {row.get("event_id") for row in known if row.get("event_id")}
    known_times: dict[str, list[float]] = {}
    for row in known:
        known_times.setdefault(row["video_id"], []).append(float(row["source_time_sec"]))
    video_times: dict[str, list[float]] = {}
    for row in rows:
        event = gt[row["event_id"]]
        action = {"パス": "Pass", "パス(受け手)": "Reception candidate"}[event["bepro_code"]]
        if row["action"] != action or row["video_id"] != event["video_id"]:
            raise ValueError(f"event mapping mismatch: {row['event_id']}")
        if row["event_id"] in known_ids:
            raise ValueError(f"overlaps known event ID: {row['event_id']}")
        fps = float(row["source_fps"])
        index = int(row["frame_index"])
        time = float(row["source_time_sec"])
        if index != round(time * fps) or int(row["frame_number"]) != index + 1:
            raise ValueError(f"frame number mismatch: {row['event_id']}")
        if abs(index / fps - time) > 0.5 / fps + 1e-6:
            raise ValueError(f"time alignment mismatch: {row['event_id']}")
        if any(abs(time - old) < float(manifest["known_gap_sec"]) for old in known_times.get(row["video_id"], [])):
            raise ValueError(f"overlaps known review: {row['event_id']}")
        video_times.setdefault(row["video_id"], []).append(time)
        frame = cv2.imread(str(directory / row["frame_image"]))
        preview = cv2.imread(str(directory / row["preview_image"]))
        if frame is None or frame.shape != (1080, 1920, 3) or preview is None or preview.shape != (270, 1440, 3):
            raise ValueError(f"image decode/size mismatch: {row['event_id']}")
        if float(np.mean(frame[930:1075, 5:915])) > 2.5:
            raise ValueError(f"Bepro text mask is not opaque: {row['event_id']}")
    gaps = [b - a for times in video_times.values() for a, b in zip(sorted(times), sorted(times)[1:])]
    minimum_gap = min(gaps)
    if minimum_gap + 1e-6 < float(manifest["min_gap_sec"]):
        raise ValueError(f"minimum selected gap is {minimum_gap}")
    counts = Counter((row["match_id"], row["half"], row["action"]) for row in rows)
    return {
        "candidate_count": len(rows),
        "image_pairs": len(rows),
        "minimum_gap_sec": round(minimum_gap, 3),
        "maximum_frame_offset_sec": round(max(abs(float(row["frame_offset_from_event_sec"])) for row in rows), 6),
        "counts": {"/".join(key): value for key, value in sorted(counts.items())},
        "field_zones": dict(Counter(row["field_zone"] for row in rows)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.candidate_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
