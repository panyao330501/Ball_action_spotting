"""Build an offline browser reviewer from masked U18 Pass evaluation clips."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


PASS_REQUIRED_COLUMNS = {
    "review_id", "video_id", "label", "algorithmic_status", "source_time_sec",
    "source_video", "human_visibility", "human_judgment", "human_comment",
}
DRIVE_REQUIRED_COLUMNS = {
    "event_id", "video_id", "label", "source_time_sec", "mapping_status",
    "review_mapping", "review_observation", "review_comment",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--mode", choices=("pass", "drive"), default="pass")
    parser.add_argument("--proxy-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--context-sec", type=float, default=5.0)
    parser.add_argument("--ffmpeg", type=Path, default=Path(shutil.which("ffmpeg") or "ffmpeg"))
    parser.add_argument("--ffprobe", type=Path, default=Path(shutil.which("ffprobe") or "ffprobe"))
    parser.add_argument("--limit", type=int, help="Render only the first N rows for a separate smoke output")
    parser.add_argument("--page-only", action="store_true", help="Refresh page assets from verified existing clips")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timecode(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def read_rows(path: Path, mode: str = "pass") -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fields = list(reader.fieldnames or [])
        required = PASS_REQUIRED_COLUMNS if mode == "pass" else DRIVE_REQUIRED_COLUMNS
        if not required.issubset(fields):
            raise ValueError(f"review CSV is missing columns: {sorted(required - set(fields))}")
        rows = list(reader)
    if mode == "drive":
        for row in rows:
            row["review_id"] = row["event_id"]
            row["algorithmic_status"] = "AUDIT"
    if not rows or len({row["review_id"] for row in rows}) != len(rows):
        raise ValueError("review CSV is empty or has duplicate review IDs")
    for row in rows:
        if mode == "pass" and (row["label"] != "Pass" or row["algorithmic_status"] not in {"FP", "FN", "TP"}):
            raise ValueError(f"unsupported review row: {row['review_id']}")
        if mode == "drive" and (row["label"] != "Drive" or row["mapping_status"] != "provisional_receiver_proxy"):
            raise ValueError(f"unsupported review row: {row['review_id']}")
        # Spreadsheet applications may shorten the displayed timecode. Seconds are authoritative.
        row["source_timecode"] = timecode(float(row["source_time_sec"]))
    return fields, rows


def clip_contract(row: dict[str, str], proxy: dict[str, Any], context_sec: float) -> dict[str, Any]:
    fps = 25
    total_frames = int(proxy["proxy_info"]["frame_count"])
    center = round(float(row["source_time_sec"]) * fps)
    if not 0 <= center < total_frames:
        raise ValueError(f"review time outside proxy: {row['review_id']}")
    radius = round(context_sec * fps)
    start = max(0, center - radius)
    end = min(total_frames - 1, center + radius)
    return {
        "review_id": row["review_id"],
        "video_id": row["video_id"],
        "path": f"clips/{row['review_id']}.mp4",
        "start_frame": start,
        "end_frame": end,
        "frame_count": end - start + 1,
        "center_relative_frame": center - start,
        "start_sec": start / fps,
        "center_offset_sec": (center - start) / fps,
        "fps": fps,
    }


def probe_clip(ffprobe: Path, path: Path) -> dict[str, Any]:
    command = [str(ffprobe), "-v", "error", "-count_frames", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames,duration",
               "-of", "json", str(path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)["streams"][0]


def verify_clip(ffprobe: Path, path: Path, contract: dict[str, Any]) -> None:
    stream = probe_clip(ffprobe, path)
    if (int(stream["width"]), int(stream["height"])) != (1280, 720):
        raise ValueError(f"unexpected clip dimensions: {path}")
    if stream["r_frame_rate"] != "25/1" or int(stream["nb_read_frames"]) != contract["frame_count"]:
        raise ValueError(f"clip FPS or frame count mismatch: {path}")
    if abs(float(stream["duration"]) - contract["frame_count"] / 25) > 0.002:
        raise ValueError(f"clip duration mismatch: {path}")


def render_clip(ffmpeg: Path, ffprobe: Path, source: Path, target: Path, contract: dict[str, Any]) -> None:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-ss", f"{contract['start_sec']:.6f}", "-i", str(source),
        "-map", "0:v:0", "-an", "-frames:v", str(contract["frame_count"]),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-g", "25", "-keyint_min", "25", "-sc_threshold", "0",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target),
    ]
    subprocess.run(command, check=True)
    verify_clip(ffprobe, target, contract)


def write_page(
    output_dir: Path, fields: list[str], rows: list[dict[str, str]],
    clips: list[dict[str, Any]], review_sha256: str, mode: str,
) -> None:
    template_dir = Path(__file__).resolve().parents[1] / "web" / "u18_eval_review"
    by_id = {clip["review_id"]: clip for clip in clips}
    page_rows = [{**row, "clip": by_id[row["review_id"]]} for row in rows]
    payload = json.dumps(
        {"fields": fields, "rows": page_rows, "review_sha256": review_sha256, "mode": mode},
        ensure_ascii=False, separators=(",", ":"),
    ).replace("<", "\\u003c")
    template = (template_dir / "index.html").read_text(encoding="utf-8")
    (output_dir / "index.html").write_text(
        template.replace("__REVIEW_DATA__", payload), encoding="utf-8"
    )
    for name in ("app.js", "style.css"):
        shutil.copyfile(template_dir / name, output_dir / name)


def main() -> None:
    args = parse_args()
    if args.context_sec <= 0 or (args.limit is not None and args.limit < 1):
        raise ValueError("context-sec and limit must be positive")
    if args.page_only and args.limit:
        raise ValueError("page-only cannot be combined with limit")
    if args.page_only:
        manifest = json.loads((args.output_dir / "manifest.json").read_text(encoding="utf-8"))
        fields, rows = read_rows(args.review_csv, args.mode)
        if (manifest.get("mode", "pass") != args.mode or
                manifest["review_csv_sha256"] != sha256_file(args.review_csv) or
                len(manifest["clips"]) != len(rows)):
            raise ValueError("existing review site does not match CSV or mode")
        for clip in manifest["clips"]:
            path = args.output_dir / clip["path"]
            verify_clip(args.ffprobe, path, clip)
            if sha256_file(path) != clip["sha256"]:
                raise ValueError(f"clip hash mismatch: {path}")
        if "mode" not in manifest:
            manifest["mode"] = args.mode
            (args.output_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        write_page(args.output_dir, fields, rows, manifest["clips"], manifest["review_csv_sha256"], args.mode)
        print(f"offline review page refreshed: {args.output_dir / 'index.html'}")
        return
    if (args.output_dir / "index.html").exists() or (args.output_dir / "manifest.json").exists():
        raise FileExistsError(f"refusing to overwrite completed review site: {args.output_dir}")
    if not args.ffmpeg.is_file() or not args.ffprobe.is_file():
        raise FileNotFoundError("ffmpeg/ffprobe not found in the active environment")
    fields, all_rows = read_rows(args.review_csv, args.mode)
    rows = all_rows[:args.limit] if args.limit else all_rows
    proxy_manifest = json.loads(args.proxy_manifest.read_text(encoding="utf-8"))
    proxies = {video["video_id"]: video for video in proxy_manifest["videos"]}
    sources: dict[str, Path] = {}
    for row in rows:
        proxy = proxies[row["video_id"]]
        source = Path(proxy["proxy_path"])
        if not source.is_file() or source.stat().st_size != proxy["proxy_info"]["size_bytes"]:
            raise ValueError(f"masked proxy identity mismatch: {row['video_id']}")
        sources[row["video_id"]] = source
    hashes = {video_id: sha256_file(path) for video_id, path in sources.items()}
    for video_id, value in hashes.items():
        if value != proxies[video_id]["proxy_sha256"]:
            raise ValueError(f"masked proxy SHA-256 mismatch: {video_id}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "clips").mkdir(exist_ok=True)
    contracts = [clip_contract(row, proxies[row["video_id"]], args.context_sec) for row in rows]
    for index, contract in enumerate(contracts, start=1):
        target = args.output_dir / contract["path"]
        if target.exists():
            verify_clip(args.ffprobe, target, contract)
        else:
            render_clip(args.ffmpeg, args.ffprobe, sources[contract["video_id"]], target, contract)
        contract["sha256"] = sha256_file(target)
        print(f"verified clip {index}/{len(contracts)}: {contract['review_id']}", flush=True)
    review_sha256 = sha256_file(args.review_csv)
    manifest = {
        "schema_version": 1,
        "mode": args.mode,
        "review_csv": str(args.review_csv.resolve()),
        "review_csv_sha256": review_sha256,
        "proxy_manifest": str(args.proxy_manifest.resolve()),
        "proxy_manifest_sha256": sha256_file(args.proxy_manifest),
        "masked_proxy_sha256": hashes,
        "context_sec": args.context_sec,
        "clips": contracts,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_page(args.output_dir, fields, rows, contracts, review_sha256, args.mode)
    print(f"offline review site ready: {args.output_dir / 'index.html'}")


if __name__ == "__main__":
    main()
