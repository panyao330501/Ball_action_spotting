"""Export manually chosen U18 source frames and portable review metadata."""

from __future__ import annotations

import argparse
import csv
import json
import math
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import yaml

from curate_u18_candidate_frames import mask_frame, read_csv, read_frame, sha256_file


FIELDS = (
    "candidate_id", "event_id", "video_id", "match_id", "half", "action",
    "bepro_code", "source_time_sec", "source_timecode", "match_time_sec",
    "match_timecode", "frame_index", "frame_number", "chosen_frame_index",
    "chosen_frame_number", "chosen_source_time_sec", "chosen_source_timecode",
    "chosen_match_time_sec", "chosen_match_timecode", "team", "x", "y",
    "distance_band", "field_zone", "time_bin", "review_note",
    "source_video_basename", "selected_frame_image", "image_sha256",
)


def timecode(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, fraction = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{fraction:03d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--config", default=Path("configs/u18_gt.yaml"), type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-count", default=100, type=int)
    return parser.parse_args()


def validated_rows(
    selected: list[dict[str, str]], candidates: list[dict[str, str]],
    videos: dict[str, dict], expected_count: int,
) -> list[tuple[dict[str, str], dict[str, str], int]]:
    if len(selected) != expected_count:
        raise ValueError(f"expected {expected_count} selected rows, found {len(selected)}")
    by_id = {row["candidate_id"]: row for row in candidates}
    if len(by_id) != len(candidates):
        raise ValueError("duplicate candidate IDs in candidate CSV")
    used_ids: set[str] = set()
    used_frames: set[tuple[str, int]] = set()
    result = []
    for row in selected:
        candidate_id = row["candidate_id"]
        if candidate_id in used_ids or candidate_id not in by_id:
            raise ValueError(f"duplicate or unknown candidate: {candidate_id}")
        source = by_id[candidate_id]
        for field in ("event_id", "video_id", "match_id", "half", "action", "frame_index"):
            if row[field] != source[field]:
                raise ValueError(f"{candidate_id}: {field} differs from original candidate")
        video_id = row["video_id"]
        if video_id not in videos:
            raise ValueError(f"{candidate_id}: unknown video ID {video_id}")
        frame = int(row["chosen_frame_index"])
        if not 0 <= frame < videos[video_id]["frame_count"]:
            raise ValueError(f"{candidate_id}: chosen frame outside source video")
        if (video_id, frame) in used_frames:
            raise ValueError(f"{candidate_id}: duplicate selected source frame")
        if int(row["chosen_frame_number"]) != frame + 1:
            raise ValueError(f"{candidate_id}: inconsistent one-based frame number")
        offset = 2700 if int(row["half"]) == 2 else 0
        for field, expected in (
            ("chosen_source_time_sec", frame / 30),
            ("chosen_match_time_sec", frame / 30 + offset),
        ):
            if not math.isclose(float(row[field]), expected, abs_tol=0.000001):
                raise ValueError(f"{candidate_id}: inconsistent {field}")
        video_path = Path(row["source_video"])
        if video_path.name != videos[video_id]["video_basename"] or not video_path.is_file():
            raise ValueError(f"{candidate_id}: source video identity/path mismatch")
        if video_path.stat().st_size != videos[video_id]["video_size_bytes"]:
            raise ValueError(f"{candidate_id}: source video size mismatch")
        used_ids.add(candidate_id)
        used_frames.add((video_id, frame))
        result.append((row, source, frame))
    return result


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"output already exists: {args.output_dir}")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    videos = {video["video_id"]: video for video in config["videos"]}
    selected = read_csv(args.selection)
    candidate_csv = args.candidate_dir / "review.csv"
    candidates = read_csv(candidate_csv)
    rows = validated_rows(selected, candidates, videos, args.expected_count)
    mask_rect = config["inference_proxy"]["mask_source_rect_px"]
    args.output_dir.mkdir(parents=True)
    image_dir = args.output_dir / "frames"
    image_dir.mkdir()
    output_rows = []
    captures: dict[str, cv2.VideoCapture] = {}
    try:
        for row, source, frame in rows:
            video_id = row["video_id"]
            if video_id not in captures:
                capture = cv2.VideoCapture(row["source_video"])
                if not capture.isOpened():
                    raise RuntimeError(f"cannot open source video: {video_id}")
                if abs(capture.get(cv2.CAP_PROP_FPS) - 30) > 0.01:
                    raise RuntimeError(f"unexpected source FPS: {video_id}")
                if round(capture.get(cv2.CAP_PROP_FRAME_COUNT)) != videos[video_id]["frame_count"]:
                    raise RuntimeError(f"unexpected source frame count: {video_id}")
                captures[video_id] = capture
            image = mask_frame(read_frame(captures[video_id], frame), mask_rect)
            filename = f"{row['candidate_id']}_{video_id}_f{frame:06d}.jpg"
            image_path = image_dir / filename
            if not cv2.imwrite(str(image_path), image, [cv2.IMWRITE_JPEG_QUALITY, 92]):
                raise OSError(f"cannot write {image_path}")
            checked = cv2.imread(str(image_path))
            if checked is None or checked.shape != image.shape:
                raise RuntimeError(f"written image cannot be decoded: {image_path}")
            output_rows.append({
                **{key: row[key] for key in (
                    "candidate_id", "event_id", "video_id", "match_id", "half", "action",
                    "source_time_sec", "source_timecode", "match_time_sec", "match_timecode",
                    "frame_index", "frame_number", "chosen_frame_index", "chosen_frame_number",
                    "chosen_source_time_sec", "chosen_match_time_sec", "review_note",
                )},
                **{key: source[key] for key in (
                    "bepro_code", "team", "x", "y", "distance_band", "field_zone", "time_bin",
                )},
                "chosen_source_timecode": timecode(frame / 30),
                "chosen_match_timecode": timecode(frame / 30 + (2700 if int(row["half"]) == 2 else 0)),
                "source_video_basename": Path(row["source_video"]).name,
                "selected_frame_image": f"frames/{filename}",
                "image_sha256": sha256_file(image_path),
            })
    finally:
        for capture in captures.values():
            capture.release()

    csv_path = args.output_dir / "selected_frames.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    counts = {
        "match": dict(Counter(row["match_id"] for row in output_rows)),
        "half": dict(Counter(row["half"] for row in output_rows)),
        "action": dict(Counter(row["action"] for row in output_rows)),
        "field_zone": dict(Counter(row["field_zone"] for row in output_rows)),
    }
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_count": len(output_rows),
        "source_selection_sha256": sha256_file(args.selection),
        "source_candidates_sha256": sha256_file(candidate_csv),
        "source_video_sha256": {
            video_id: videos[video_id]["video_sha256"] for video_id in captures
        },
        "source_fps": 30,
        "frame_index_base": 0,
        "frame_number_base": 1,
        "mask_source_rect_px": mask_rect,
        "selected_frames_csv_sha256": sha256_file(csv_path),
        "counts": counts,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "README.md").write_text(
        "# U18 Manually Selected Frames\n\n"
        f"This package contains {len(output_rows)} selected JPEG frames in `frames/`, "
        "a matching `selected_frames.csv`, and a provenance `manifest.json`. "
        "Each image was extracted from the original 30 FPS video at its "
        "`chosen_frame_index`. The lower-left Bepro text overlay has been masked. "
        "The original videos and review clips are not included.\n\n"
        "The CSV separates Bepro's suggested event from the manually chosen frame. "
        "`frame_index`, `source_time_sec`, and `match_time_sec` describe the "
        "suggested event. Fields beginning with `chosen_` describe the selected "
        "frame and its calculated time. Frame indices are zero-based; frame "
        "numbers are one-based. For the second half, match time is 2,700 seconds "
        "later than time within the half video. `selected_frame_image` is the "
        "relative path to the JPEG for that CSV row.\n\n"
        "`Reception candidate` denotes an event drawn from Bepro's receiver-pass "
        "code; this label alone does not independently verify first touch. "
        "`field_zone` and `x/y` come from the original Bepro event and are not "
        "newly annotated locations for the selected image. Original Japanese "
        "source filenames and Bepro codes are retained as identifiers.\n",
        encoding="utf-8",
    )
    zip_path = args.output_dir / "u18_selected_frames_100.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(args.output_dir.rglob("*")):
            if path.is_file() and path != zip_path:
                archive.write(path, path.relative_to(args.output_dir).as_posix())
    print(json.dumps({"output_dir": str(args.output_dir), "zip": str(zip_path),
                      "zip_sha256": sha256_file(zip_path), "counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
