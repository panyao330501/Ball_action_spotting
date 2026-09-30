"""Render merged miss-candidate review windows from the canonical source video."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import render_visualization as base


LABEL_COLORS = {"Pass": "0x00E676", "Drive": "0xFF9800", "Unknown": "0xBDBDBD"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/poc_video.yaml"))
    parser.add_argument("--source-video", type=Path)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--artifact-root", type=Path, default=Path("artifacts/candidate_review")
    )
    parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--priorities", nargs="+", choices=sorted(PRIORITY_ORDER), default=["high", "medium"]
    )
    parser.add_argument("--max-windows", type=int)
    parser.add_argument("--preset", default="fast")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    return parser.parse_args()


def load_candidate_artifacts(
    candidate_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates_path = candidate_dir / "candidates.json"
    windows_path = candidate_dir / "review_windows.json"
    if not candidates_path.is_file() or not windows_path.is_file():
        raise FileNotFoundError("candidate-dir must contain candidates.json and review_windows.json")
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    windows = json.loads(windows_path.read_text(encoding="utf-8"))
    if not isinstance(candidates, list) or not isinstance(windows, list):
        raise ValueError("candidate artifacts must contain JSON lists")
    candidate_ids: set[str] = set()
    previous_time = -1.0
    for candidate in candidates:
        required = {
            "candidate_id",
            "time_sec",
            "timecode",
            "label",
            "priority",
            "ensemble_score",
            "fold_max_score",
            "evidence_sources",
        }
        if required.difference(candidate):
            raise ValueError("candidate record is missing required fields")
        if candidate["candidate_id"] in candidate_ids:
            raise ValueError("duplicate candidate_id")
        candidate_ids.add(candidate["candidate_id"])
        if candidate["label"] not in LABEL_COLORS or candidate["priority"] not in PRIORITY_ORDER:
            raise ValueError("candidate contains unsupported label or priority")
        if float(candidate["time_sec"]) < previous_time:
            raise ValueError("candidates must be ordered by time_sec")
        previous_time = float(candidate["time_sec"])
    window_ids: set[str] = set()
    for window in windows:
        required = {
            "window_id",
            "review_order",
            "priority",
            "source_start_sec",
            "source_end_sec",
            "candidate_ids",
        }
        if required.difference(window):
            raise ValueError("review window is missing required fields")
        if window["window_id"] in window_ids:
            raise ValueError("duplicate window_id")
        window_ids.add(window["window_id"])
        if not set(window["candidate_ids"]).issubset(candidate_ids):
            raise ValueError("review window references an unknown candidate")
        if float(window["source_end_sec"]) <= float(window["source_start_sec"]):
            raise ValueError("review window has invalid bounds")
    return candidates, windows


def compact_sources(sources: list[str]) -> str:
    mapping = {
        "ensemble_low_peak": "low-peak",
        "fold_disagreement": "fold",
        "tracking_change": "tracking",
    }
    return "+".join(mapping.get(source, source) for source in sources)


def build_window_filter(
    window: dict[str, Any],
    candidates: list[dict[str, Any]],
    sequence: int,
    total: int,
) -> str:
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    members = [by_id[candidate_id] for candidate_id in window["candidate_ids"]]
    start = base.format_timecode(float(window["source_start_sec"]))
    end = base.format_timecode(float(window["source_end_sec"]))
    title = base.ffmpeg_escape_text(
        f"MISS WINDOW {sequence:03d}/{total:03d}  {window['priority'].upper()}  source {start} - {end}"
    )
    source_start = float(window["source_start_sec"])
    dynamic_source_time = f"SOURCE %{{pts\\:hms\\:{source_start:.6f}}}"
    filters = [
        "setpts=PTS-STARTPTS",
        "drawbox=x=16:y=16:w=870:h=42:color=black@0.82:t=fill",
        f"drawtext=font=Arial:text='{title}':fontcolor=white:fontsize=22:"
        "x=28:y=24:shadowcolor=black:shadowx=2:shadowy=2",
        "drawbox=x=900:y=16:w=364:h=42:color=black@0.82:t=fill",
        f"drawtext=font=Arial:text='{dynamic_source_time}':fontcolor=white:fontsize=22:"
        "x=914:y=24:shadowcolor=black:shadowx=2:shadowy=2",
    ]
    shown = members[:6]
    for row, candidate in enumerate(shown):
        text = base.ffmpeg_escape_text(
            f"{candidate['candidate_id']}  {candidate['label']}  "
            f"BAS {float(candidate['ensemble_score']):.3f}  fold-max {float(candidate['fold_max_score']):.3f}  "
            f"{compact_sources(candidate['evidence_sources'])}  event {candidate['timecode']}"
        )
        y = 68 + row * 34
        filters.extend(
            [
                f"drawbox=x=16:y={y}:w=1248:h=30:color=black@0.66:t=fill",
                f"drawtext=font=Arial:text='{text}':fontcolor={LABEL_COLORS[candidate['label']]}:"
                f"fontsize=19:x=28:y={y + 4}:shadowcolor=black:shadowx=2:shadowy=2",
            ]
        )
    if len(members) > len(shown):
        more = base.ffmpeg_escape_text(f"+{len(members) - len(shown)} more candidates in this window")
        y = 68 + len(shown) * 34
        filters.append(
            f"drawtext=font=Arial:text='{more}':fontcolor=white:fontsize=18:x=28:y={y + 4}"
        )
    filters.append("format=yuv420p")
    return ",".join(filters)


def select_windows(
    windows: list[dict[str, Any]], priorities: set[str], max_windows: int | None
) -> list[dict[str, Any]]:
    selected = sorted(
        (window for window in windows if window["priority"] in priorities),
        key=lambda window: int(window["review_order"]),
    )
    if max_windows is not None:
        if max_windows < 1:
            raise ValueError("--max-windows must be positive")
        selected = selected[:max_windows]
    if not selected:
        raise ValueError("no review windows match the requested priorities")
    return selected


def main() -> None:
    args = parse_args()
    if not 0 <= args.crf <= 51:
        raise ValueError("--crf must be in [0, 51]")
    repo_root = Path(__file__).resolve().parents[1]
    config = base.load_yaml(args.config)
    source = (args.source_video or (repo_root / config["source"]["basename"])).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    candidates, windows = load_candidate_artifacts(args.candidate_dir)
    selected = select_windows(windows, set(args.priorities), args.max_windows)
    ffmpeg = base.find_tool(args.ffmpeg, "ffmpeg")
    ffprobe = base.find_tool(args.ffprobe, "ffprobe")

    artifact_dir = (args.artifact_root / args.run_id).resolve()
    output_dir = (args.output_root / args.run_id).resolve()
    output_path = output_dir / "miss_candidate_highlights.mp4"
    manifest_path = artifact_dir / "candidate_review_manifest.json"
    log_path = artifact_dir / "candidate_review.log"
    if artifact_dir.exists() or output_dir.exists():
        raise FileExistsError("candidate review run already exists; choose a new --run-id")
    artifact_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    status: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "run_id": args.run_id,
        "repository_commit": base.git_revision(repo_root),
    }
    try:
        source_sha256 = base.sha256_file(source)
        source_probe = base.probe_media(ffprobe, source)
        source_info = base.assert_source_contract(config, source, source_probe, source_sha256)
        by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
        clip_dir = artifact_dir / "candidate_clips"
        clip_dir.mkdir()
        clip_paths: list[Path] = []
        filters: list[str] = []
        rendered_windows: list[dict[str, Any]] = []
        for sequence, window in enumerate(selected, start=1):
            duration = float(window["source_end_sec"]) - float(window["source_start_sec"])
            clip_filter = build_window_filter(window, candidates, sequence, len(selected))
            filters.append(clip_filter)
            clip_path = clip_dir / f"{sequence:04d}_{window['window_id']}.mp4"
            command = [
                str(ffmpeg),
                "-hide_banner",
                "-n",
                "-ss",
                f"{float(window['source_start_sec']):.6f}",
                "-t",
                f"{duration:.6f}",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                clip_filter,
                "-af",
                f"aresample=async=1:first_pts=0,atrim=duration={duration:.6f},asetpts=PTS-STARTPTS",
                "-c:v",
                "libx264",
                "-preset",
                args.preset,
                "-crf",
                str(args.crf),
                "-pix_fmt",
                "yuv420p",
                "-r",
                f"{source_info['fps']:.6f}",
                "-fps_mode",
                "cfr",
                "-frames:v",
                str(max(1, round(duration * source_info["fps"]))),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-progress",
                "pipe:1",
                "-nostats",
                str(clip_path),
            ]
            base.run_ffmpeg(command, log_path, f"candidate_window_{sequence:04d}_of_{len(selected):04d}")
            clip_paths.append(clip_path)
            rendered_windows.append(
                {
                    **window,
                    "sequence": sequence,
                    "candidate_details": [by_id[candidate_id] for candidate_id in window["candidate_ids"]],
                }
            )
        (artifact_dir / "candidate_filters.txt").write_text(
            "\n".join(filters) + "\n", encoding="utf-8"
        )
        concat_path = artifact_dir / "candidate_windows.ffconcat"
        concat_path.write_text(base.build_highlight_concat(clip_paths), encoding="utf-8")
        total_duration = sum(float(window["duration_sec"]) for window in selected)
        concat_command = [
            str(ffmpeg),
            "-hide_banner",
            "-n",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-af",
            f"atrim=duration={total_duration:.6f},asetpts=PTS-STARTPTS",
            "-t",
            f"{total_duration:.6f}",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(output_path),
        ]
        base.run_ffmpeg(concat_command, log_path, "miss_candidate_highlights_concat")
        status.update(
            {
                "status": "completed",
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "tools": {"ffmpeg": base.ffmpeg_version(ffmpeg), "ffprobe": str(ffprobe)},
                "input": {
                    "source_video": str(source),
                    "source_sha256": source_sha256,
                    "candidate_dir": str(args.candidate_dir.resolve()),
                    "candidates_sha256": base.sha256_file(args.candidate_dir / "candidates.json"),
                    "review_windows_sha256": base.sha256_file(
                        args.candidate_dir / "review_windows.json"
                    ),
                    "requested_priorities": args.priorities,
                    "num_windows_available": len(windows),
                    "num_windows_rendered": len(selected),
                    "windows_by_priority": dict(Counter(window["priority"] for window in selected)),
                },
                "render": {
                    "temporal_only": True,
                    "spatial_boxes": False,
                    "tracking_overlay": False,
                    "video_encoder": {"codec": "libx264", "preset": args.preset, "crf": args.crf},
                    "audio": "AAC 192 kb/s",
                    "duration_sec": total_duration,
                    "windows": rendered_windows,
                },
                "output": base.output_record(ffprobe, output_path),
            }
        )
        manifest_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"manifest": str(manifest_path), "status": "completed"}, ensure_ascii=False))
    except Exception:
        status.update(
            {
                "status": "failed",
                "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": repr(sys.exc_info()[1]),
            }
        )
        manifest_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
