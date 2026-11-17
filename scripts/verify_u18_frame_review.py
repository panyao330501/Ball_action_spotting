"""Verify masked U18 context clips and their source-frame alignment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import yaml


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_frame(capture: cv2.VideoCapture, index: int) -> np.ndarray:
    if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
        raise RuntimeError(f"cannot seek to {index}")
    okay, frame = capture.read()
    if not okay or frame is None or abs(capture.get(cv2.CAP_PROP_POS_FRAMES) - (index + 1)) > 0.5:
        raise RuntimeError(f"cannot decode frame {index}")
    return frame


def verify(directory: Path, config_path: Path, sample_count: int) -> dict[str, object]:
    with (directory / "review.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    manifest = json.loads((directory / "clip_manifest.json").read_text(encoding="utf-8"))
    if manifest["review_csv_sha256"] != sha256_file(directory / "review.csv"):
        raise ValueError("review CSV hash mismatch")
    contracts = manifest["clips"]
    if len(rows) != len(contracts) or len(rows) != len(list((directory / "clips").glob("*.mp4"))):
        raise ValueError("clip count mismatch")
    by_id = {row["candidate_id"]: row for row in rows}
    for contract in contracts:
        row = by_id[contract["candidate_id"]]
        path = directory / contract["path"]
        if row["event_id"] != contract["event_id"] or sha256_file(path) != contract["sha256"]:
            raise ValueError(f"clip hash/identity mismatch: {path}")
        if int(row["frame_index"]) != contract["source_start_frame"] + contract["center_relative_frame"]:
            raise ValueError(f"center-frame mapping mismatch: {path}")
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened() or round(capture.get(cv2.CAP_PROP_FRAME_COUNT)) != contract["frame_count"]:
                raise ValueError(f"clip frame count mismatch: {path}")
            if abs(capture.get(cv2.CAP_PROP_FPS) - 30) > 0.001:
                raise ValueError(f"clip FPS mismatch: {path}")
        finally:
            capture.release()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    rect = config["inference_proxy"]["mask_source_rect_px"]
    sample_indexes = sorted({round(i * (len(contracts) - 1) / max(1, sample_count - 1)) for i in range(sample_count)})
    comparisons: list[dict[str, object]] = []
    for selected_index in sample_indexes:
        contract = contracts[selected_index]
        row = by_id[contract["candidate_id"]]
        source = cv2.VideoCapture(row["source_video"])
        clip = cv2.VideoCapture(str(directory / contract["path"]))
        try:
            positions = sorted({0, contract["center_relative_frame"], contract["frame_count"] - 1})
            for relative in positions:
                original = read_frame(source, contract["source_start_frame"] + relative)
                x, y, width, height = rect
                original[y:y + height, x:x + width] = 0
                expected = cv2.resize(original, (manifest["width"], manifest["height"]), interpolation=cv2.INTER_LINEAR)
                actual = read_frame(clip, relative)
                error = float(np.mean(np.abs(actual.astype(np.int16) - expected.astype(np.int16))))
                if error > 5:
                    raise ValueError(f"source-frame alignment mismatch: {row['event_id']} rel={relative} MAE={error:.3f}")
                comparisons.append({"event_id": row["event_id"], "relative_frame": relative, "mae": round(error, 3)})
        finally:
            source.release()
            clip.release()
    return {
        "clip_count": len(contracts),
        "sampled_clips": len(sample_indexes),
        "sampled_frame_comparisons": len(comparisons),
        "maximum_sample_mae": max(item["mae"] for item in comparisons),
        "clip_width": manifest["width"],
        "clip_height": manifest["height"],
        "fps": manifest["fps"],
        "context_sec": manifest["context_sec"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/u18_gt.yaml"))
    parser.add_argument("--samples", type=int, default=8)
    args = parser.parse_args()
    if args.samples < 1:
        raise ValueError("--samples must be positive")
    print(json.dumps(verify(args.candidate_dir, args.config, args.samples), indent=2))


if __name__ == "__main__":
    main()
