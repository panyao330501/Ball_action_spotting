"""Check a shared U18 frame package against its CSV and review clips."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import cv2

from curate_u18_candidate_frames import read_csv, read_frame, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("candidate_dir", type=Path)
    args = parser.parse_args()
    package = args.package_dir
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    csv_path = package / "selected_frames.csv"
    if sha256_file(csv_path) != manifest["selected_frames_csv_sha256"]:
        raise ValueError("selected CSV hash mismatch")
    rows = read_csv(csv_path)
    if len(rows) != manifest["selected_count"]:
        raise ValueError("selected count mismatch")
    clip_manifest = json.loads((args.candidate_dir / "clip_manifest.json").read_text(encoding="utf-8"))
    clips = {item["candidate_id"]: item for item in clip_manifest["clips"]}
    differences = []
    names = set()
    for row in rows:
        filename = row["selected_frame_image"]
        if filename in names:
            raise ValueError(f"duplicate image name: {filename}")
        names.add(filename)
        image_path = package / filename
        if sha256_file(image_path) != row["image_sha256"]:
            raise ValueError(f"image hash mismatch: {filename}")
        image = cv2.imread(str(image_path))
        if image is None or image.shape != (1080, 1920, 3):
            raise ValueError(f"image decode/dimensions mismatch: {filename}")
        # JPEG ringing can affect the mask boundary; the interior must stay black.
        if image[933:1072, 8:912].max() > 8:
            raise ValueError(f"Bepro text mask missing: {filename}")
        clip = clips[row["candidate_id"]]
        relative_frame = int(row["chosen_frame_index"]) - clip["source_start_frame"]
        if not 0 <= relative_frame < clip["frame_count"]:
            raise ValueError(f"selected frame outside review clip: {filename}")
        capture = cv2.VideoCapture(str(args.candidate_dir / clip["path"]))
        if not capture.isOpened():
            raise RuntimeError(f"cannot open review clip: {clip['path']}")
        try:
            clip_image = read_frame(capture, relative_frame)
        finally:
            capture.release()
        resized = cv2.resize(image, (1600, 900), interpolation=cv2.INTER_AREA)
        difference = cv2.absdiff(resized, clip_image).mean()
        differences.append(float(difference))
        if difference > 12:
            raise ValueError(f"selected image differs from corresponding review clip: {filename}: {difference:.3f}")
    archive_path = package / "u18_selected_frames_100.zip"
    with zipfile.ZipFile(archive_path) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError(f"ZIP CRC failure: {corrupt}")
        expected = names | {"selected_frames.csv", "manifest.json", "README.md"}
        if set(archive.namelist()) != expected:
            raise ValueError("ZIP member list mismatch")
    print(json.dumps({
        "selected_rows": len(rows), "distinct_images": len(names),
        "zip_members": len(expected), "zip_bytes": archive_path.stat().st_size,
        "max_mean_pixel_difference_to_review_clip": round(max(differences), 3),
        "mean_pixel_difference_to_review_clip": round(sum(differences) / len(differences), 3),
        "zip_sha256": sha256_file(archive_path),
    }, indent=2))


if __name__ == "__main__":
    main()
