"""Render the local Pass/Drive review video and per-event highlights.

The renderer is CPU-only. It validates the source video and event contract,
draws temporal annotations with FFmpeg, preserves the source audio in the full
video, and refuses to overwrite any existing output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

import yaml


ALLOWED_LABELS = {"Pass", "Drive"}
ALLOWED_VISIBILITY = {"VISIBLE", "PARTIAL", "OFFSCREEN"}
ALLOWED_REVIEW_STATUS = {
    "unreviewed",
    "correct",
    "wrong_label",
    "timing_error",
    "duplicate",
    "false_positive",
    "visible_miss",
    "offscreen_unobservable",
    "ambiguous",
}
LABEL_COLORS = {"Pass": "0x00E676", "Drive": "0xFF9800"}
TIMELINE_COLORS = {"Pass": "0x2196F3", "Drive": "0xF44336"}
TIMELINE_FOOTER_HEIGHT = 120
TIMELINE_X = 40
TIMELINE_WIDTH = 1200
TIMELINE_MARKER_WIDTH = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/poc_video.yaml"))
    parser.add_argument("--source-video", type=Path)
    parser.add_argument(
        "--events",
        type=Path,
        default=Path("artifacts/inference/full_6835526/events.json"),
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/visualization"))
    parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--render-end-sec",
        type=float,
        help="Exclusive source time used for a short smoke render; default is the configured interval end.",
    )
    parser.add_argument("--display-pre-sec", type=float, default=0.5)
    parser.add_argument("--display-post-sec", type=float, default=2.0)
    parser.add_argument("--highlight-pre-sec", type=float, default=3.0)
    parser.add_argument("--highlight-post-sec", type=float, default=4.0)
    parser.add_argument("--preset", default="fast")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
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


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Config must contain an object: {path}")
    return data


def load_events(path: Path, interval_end_sec: float) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("events.json must contain a non-empty list")

    events: list[dict[str, Any]] = []
    previous_time = -math.inf
    event_ids: set[str] = set()
    for index, event in enumerate(raw, start=1):
        if not isinstance(event, dict):
            raise ValueError(f"Event {index} is not an object")
        required = {
            "event_id",
            "time_sec",
            "timecode",
            "label",
            "confidence",
            "visibility",
            "review_status",
            "comment",
        }
        missing = required.difference(event)
        if missing:
            raise ValueError(f"Event {index} is missing fields: {sorted(missing)}")
        event_id = event["event_id"]
        if not isinstance(event_id, str) or not event_id or event_id in event_ids:
            raise ValueError(f"Invalid or duplicate event_id: {event_id!r}")
        event_ids.add(event_id)
        time_sec = float(event["time_sec"])
        confidence = float(event["confidence"])
        if not math.isfinite(time_sec) or not 0 <= time_sec <= interval_end_sec:
            raise ValueError(f"Event {event_id} time_sec is outside the source interval")
        if time_sec < previous_time:
            raise ValueError("Events must be ordered by time_sec")
        previous_time = time_sec
        if event["timecode"] != format_timecode(time_sec):
            raise ValueError(f"Event {event_id} timecode does not match time_sec")
        if event["label"] not in ALLOWED_LABELS:
            raise ValueError(f"Event {event_id} has unsupported label: {event['label']}")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"Event {event_id} confidence is outside [0, 1]")
        if event["visibility"] not in ALLOWED_VISIBILITY:
            raise ValueError(f"Event {event_id} has unsupported visibility")
        if event["review_status"] not in ALLOWED_REVIEW_STATUS:
            raise ValueError(f"Event {event_id} has unsupported review_status")
        events.append(dict(event, time_sec=time_sec, confidence=confidence))
    return events


def find_tool(explicit: Path | None, name: str) -> Path:
    if explicit is not None:
        path = explicit.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"{name} does not exist: {path}")
        return path
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"{name} is not available on PATH")
    return Path(found).resolve()


def probe_media(ffprobe: Path, path: Path) -> dict[str, Any]:
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,sample_rate,channels,start_time,duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(result.stdout)


def one_stream(probe: dict[str, Any], codec_type: str) -> dict[str, Any] | None:
    matches = [stream for stream in probe.get("streams", []) if stream.get("codec_type") == codec_type]
    if len(matches) > 1:
        raise ValueError(f"Expected at most one {codec_type} stream, found {len(matches)}")
    return matches[0] if matches else None


def fraction_value(raw: str) -> float:
    return float(Fraction(raw))


def assert_source_contract(
    config: dict[str, Any], source: Path, probe: dict[str, Any], actual_sha256: str
) -> dict[str, Any]:
    expected = config["source"]
    video = one_stream(probe, "video")
    audio = one_stream(probe, "audio")
    if video is None or audio is None:
        raise ValueError("The source must contain one video stream and one audio stream")
    if source.name != expected["basename"]:
        raise ValueError(f"Source basename mismatch: {source.name} != {expected['basename']}")
    if actual_sha256 != expected["sha256"]:
        raise ValueError("Source SHA-256 mismatch; rendering is refused")
    for field in ("width", "height"):
        if int(video[field]) != int(expected[field]):
            raise ValueError(f"Source {field} mismatch: {video[field]} != {expected[field]}")
    fps = fraction_value(video["avg_frame_rate"])
    if not math.isclose(fps, float(expected["fps"]), abs_tol=1e-6):
        raise ValueError(f"Source FPS mismatch: {fps} != {expected['fps']}")
    duration = float(probe["format"]["duration"])
    frame_duration = 1.0 / fps
    if abs(duration - float(expected["duration_sec"])) > frame_duration:
        raise ValueError(f"Source duration mismatch: {duration} != {expected['duration_sec']}")
    if float(expected["kickoff_offset_sec"]) != 0.0:
        raise ValueError("This renderer requires kickoff_offset_sec = 0.0")
    return {"fps": fps, "duration": duration, "video": video, "audio": audio}


def assign_cluster_rows(
    events: Iterable[dict[str, Any]], pre_sec: float, post_sec: float
) -> list[int]:
    """Assign monotonically increasing rows inside each overlap-connected cluster."""
    rows: list[int] = []
    cluster_row = 0
    cluster_end = -math.inf
    for event in events:
        start = event["time_sec"] - pre_sec
        end = event["time_sec"] + post_sec
        if start > cluster_end:
            cluster_row = 0
            cluster_end = end
        else:
            cluster_row += 1
            cluster_end = max(cluster_end, end)
        rows.append(cluster_row)
    return rows


def ffmpeg_escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
    )


def timeline_marker_x(time_sec: float, timeline_end_sec: float) -> int:
    if not 0 <= time_sec <= timeline_end_sec:
        raise ValueError("Timeline marker time is outside the global interval")
    return min(
        TIMELINE_X + TIMELINE_WIDTH - 1,
        round(TIMELINE_X + time_sec / timeline_end_sec * TIMELINE_WIDTH),
    )


def build_global_timeline_filters(
    events: list[dict[str, Any]], timeline_end_sec: float
) -> list[str]:
    """Build a fixed global timeline below the unchanged source canvas."""
    if timeline_end_sec <= 0:
        raise ValueError("Timeline duration must be positive")
    total_timecode = ffmpeg_escape_text(format_timecode(timeline_end_sec))
    filters = [
        f"pad=iw:ih+{TIMELINE_FOOTER_HEIGHT}:0:0:color=black",
        f"drawbox=x=0:y=ih-{TIMELINE_FOOTER_HEIGHT}:w=iw:h={TIMELINE_FOOTER_HEIGHT}:"
        "color=black:t=fill",
        f"drawtext=font=Arial:text='GLOBAL  %{{pts\\:hms}} / {total_timecode}':"
        "fontcolor=white:fontsize=22:x=40:y=h-110",
        f"drawbox=x=970:y=729:w=14:h=14:color={TIMELINE_COLORS['Pass']}:t=fill",
        "drawtext=font=Arial:text='Pass':fontcolor=white:fontsize=20:x=992:y=726",
        f"drawbox=x=1080:y=729:w=14:h=14:color={TIMELINE_COLORS['Drive']}:t=fill",
        "drawtext=font=Arial:text='Drive':fontcolor=white:fontsize=20:x=1102:y=726",
    ]
    for event in events:
        x = timeline_marker_x(event["time_sec"], timeline_end_sec)
        if event["label"] == "Pass":
            y = "ih-74"
        else:
            y = "ih-50"
        filters.append(
            f"drawbox=x={x}:y={y}:w={TIMELINE_MARKER_WIDTH}:h=30:"
            f"color={TIMELINE_COLORS[event['label']]}:t=fill"
        )
    filters.extend(
        [
            f"drawbox=x={TIMELINE_X}:y=ih-50:w={TIMELINE_WIDTH}:h=6:color=0x808080:t=fill",
            f"drawtext=font=Arial:text='|':fontcolor=white:fontsize=62:"
            f"x='{TIMELINE_X - 5}+t/{timeline_end_sec:.6f}*{TIMELINE_WIDTH}':y=h-91:"
            "shadowcolor=black:shadowx=1:shadowy=1",
        ]
    )
    return filters


def build_annotated_filter(
    display_events: list[dict[str, Any]],
    timeline_events: list[dict[str, Any]],
    render_end_sec: float,
    timeline_end_sec: float,
    pre_sec: float,
    post_sec: float,
) -> str:
    filters = [
        "drawbox=x=iw-700:y=20:w=360:h=48:color=black@0.78:t=fill",
        "drawtext=font=Arial:text='SOURCE %{pts\\:hms}':fontcolor=white:fontsize=28:"
        "x=w-685:y=29:shadowcolor=black:shadowx=2:shadowy=2",
    ]
    rows = assign_cluster_rows(display_events, pre_sec, post_sec)
    for sequence, (event, row) in enumerate(zip(display_events, rows), start=1):
        start = max(0.0, event["time_sec"] - pre_sec)
        end = min(render_end_sec, event["time_sec"] + post_sec)
        if start >= end:
            continue
        y = 82 + row * 40
        enable = f"between(t,{start:.3f},{end:.3f})"
        text = ffmpeg_escape_text(
            f"{sequence:02d}  {event['event_id']}  {event['label']}  confidence {event['confidence']:.3f}  "
            f"event {event['timecode']}"
        )
        filters.extend(
            [
                f"drawbox=x=20:y={y}:w=800:h=36:color=black@0.62:t=fill:enable='{enable}'",
                f"drawtext=font=Arial:text='{text}':fontcolor={LABEL_COLORS[event['label']]}:"
                f"fontsize=22:x=32:y={y + 6}:shadowcolor=black:shadowx=2:shadowy=2:enable='{enable}'",
            ]
        )
    filters.extend(build_global_timeline_filters(timeline_events, timeline_end_sec))
    filters.append("format=yuv420p")
    return ",".join(filters)


def highlight_segments(
    events: list[dict[str, Any]], source_end_sec: float, pre_sec: float, post_sec: float
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    output_cursor = 0.0
    for sequence, event in enumerate(events, start=1):
        source_start = max(0.0, event["time_sec"] - pre_sec)
        source_end = min(source_end_sec, event["time_sec"] + post_sec)
        duration = source_end - source_start
        if duration <= 0:
            raise ValueError(f"Event {event['event_id']} produces an empty highlight")
        segments.append(
            {
                "sequence": sequence,
                "event_id": event["event_id"],
                "label": event["label"],
                "confidence": event["confidence"],
                "event_time_sec": event["time_sec"],
                "event_timecode": event["timecode"],
                "source_start_sec": source_start,
                "source_end_sec": source_end,
                "duration_sec": duration,
                "highlight_start_sec": output_cursor,
                "highlight_end_sec": output_cursor + duration,
            }
        )
        output_cursor += duration
    return segments


def ffconcat_quote(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "'\\''")


def build_highlight_concat(clips: list[Path]) -> str:
    lines = ["ffconcat version 1.0"]
    for clip in clips:
        lines.append(f"file '{ffconcat_quote(clip)}'")
    return "\n".join(lines) + "\n"


def build_highlight_clip_filter(segment: dict[str, Any], total: int) -> str:
    label = segment["label"]
    title = ffmpeg_escape_text(
        f"EVENT {segment['sequence']:02d}/{total:02d}  {segment['event_id']}  {label}  "
        f"confidence {segment['confidence']:.3f}  source {segment['event_timecode']}"
    )
    return ",".join(
        [
            "setpts=PTS-STARTPTS",
            "drawbox=x=20:y=ih-116:w=iw-40:h=38:color=black@0.82:t=fill",
            f"drawtext=font=Arial:text='{title}':fontcolor={LABEL_COLORS[label]}:fontsize=22:"
            "x=34:y=h-109:shadowcolor=black:shadowx=2:shadowy=2",
            "format=yuv420p",
        ]
    )


def command_for_log(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def run_ffmpeg(command: list[str], log_path: Path, stage: str) -> None:
    with log_path.open("a", encoding="utf-8", newline="\n") as log:
        log.write(f"\n[{datetime.now(timezone.utc).isoformat()}] {stage}\n")
        log.write(command_for_log(command) + "\n")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        last_report = 0.0
        progress: dict[str, str] = {}
        for line in process.stdout:
            log.write(line)
            line = line.rstrip("\r\n")
            if "=" in line:
                key, value = line.split("=", 1)
                progress[key] = value
            now = time.monotonic()
            if line.startswith("progress=") and (now - last_report >= 10 or value == "end"):
                print(
                    f"{stage}: out_time={progress.get('out_time', '?')} "
                    f"speed={progress.get('speed', '?')} progress={value}",
                    flush=True,
                )
                last_report = now
        return_code = process.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, command)


def git_revision(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def ffmpeg_version(ffmpeg: Path) -> str:
    result = subprocess.run(
        [str(ffmpeg), "-version"], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.splitlines()[0]


def output_record(ffprobe: Path, path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "ffprobe": probe_media(ffprobe, path),
    }


def main() -> None:
    args = parse_args()
    if any(value < 0 for value in (args.display_pre_sec, args.display_post_sec, args.highlight_pre_sec, args.highlight_post_sec)):
        raise ValueError("Display and highlight context values must be non-negative")
    if args.crf < 0 or args.crf > 51:
        raise ValueError("--crf must be in [0, 51]")
    for path in (args.config, args.events):
        if not path.is_file():
            raise FileNotFoundError(path)

    repo_root = Path(__file__).resolve().parents[1]
    config = load_yaml(args.config)
    source = (args.source_video or (repo_root / config["source"]["basename"])).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    ffmpeg = find_tool(args.ffmpeg, "ffmpeg")
    ffprobe = find_tool(args.ffprobe, "ffprobe")

    artifact_dir = (args.artifact_root / args.run_id).resolve()
    output_dir = (args.output_root / args.run_id).resolve()
    annotated_path = output_dir / "annotated_full.mp4"
    highlights_path = output_dir / "event_highlights.mp4"
    manifest_path = artifact_dir / "render_manifest.json"
    log_path = artifact_dir / "visualization.log"
    claimed_outputs = [annotated_path, highlights_path, manifest_path, log_path]
    if artifact_dir.exists() or output_dir.exists() or any(path.exists() for path in claimed_outputs):
        raise FileExistsError("Run artifact/output directory already exists; choose a new --run-id")
    artifact_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    status: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "run_id": args.run_id,
        "repository_commit": git_revision(repo_root),
    }
    try:
        source_sha256 = sha256_file(source)
        source_probe = probe_media(ffprobe, source)
        source_info = assert_source_contract(config, source, source_probe, source_sha256)
        configured_end = float(config["source"]["interval_sec"][1])
        render_end = args.render_end_sec if args.render_end_sec is not None else configured_end
        if not 0 < render_end <= configured_end:
            raise ValueError(f"--render-end-sec must be in (0, {configured_end}]")
        all_events = load_events(args.events, configured_end)
        events = [event for event in all_events if event["time_sec"] < render_end]
        if not events:
            raise ValueError("The render interval contains no events")

        annotated_filter = build_annotated_filter(
            events,
            all_events,
            render_end,
            configured_end,
            args.display_pre_sec,
            args.display_post_sec,
        )
        (artifact_dir / "annotated_filter.txt").write_text(annotated_filter + "\n", encoding="utf-8")
        annotated_command = [
            str(ffmpeg),
            "-hide_banner",
            "-n",
            "-i",
            str(source),
            "-t",
            f"{render_end:.6f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            annotated_filter,
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
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(annotated_path),
        ]
        run_ffmpeg(annotated_command, log_path, "annotated_full")

        segments = highlight_segments(
            events, render_end, args.highlight_pre_sec, args.highlight_post_sec
        )
        clip_dir = artifact_dir / "highlight_clips"
        clip_dir.mkdir()
        clip_paths: list[Path] = []
        clip_filters: list[str] = []
        for segment in segments:
            clip_path = clip_dir / f"{segment['sequence']:04d}_{segment['event_id']}.mp4"
            clip_filter = build_highlight_clip_filter(segment, len(segments))
            clip_filters.append(clip_filter)
            clip_command = [
                str(ffmpeg),
                "-hide_banner",
                "-n",
                "-ss",
                f"{segment['source_start_sec']:.6f}",
                "-t",
                f"{segment['duration_sec']:.6f}",
                "-i",
                str(annotated_path),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                clip_filter,
                "-af",
                f"aresample=async=1:first_pts=0,atrim=duration={segment['duration_sec']:.6f},asetpts=PTS-STARTPTS",
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
                str(max(1, round(segment["duration_sec"] * source_info["fps"]))),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-progress",
                "pipe:1",
                "-nostats",
                str(clip_path),
            ]
            run_ffmpeg(
                clip_command,
                log_path,
                f"highlight_clip_{segment['sequence']:04d}_of_{len(segments):04d}",
            )
            clip_paths.append(clip_path)
        (artifact_dir / "highlight_filters.txt").write_text(
            "\n".join(clip_filters) + "\n", encoding="utf-8"
        )

        concat_path = artifact_dir / "highlight_segments.ffconcat"
        concat_path.write_text(build_highlight_concat(clip_paths), encoding="utf-8")
        highlight_duration = sum(segment["duration_sec"] for segment in segments)
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
            f"atrim=duration={highlight_duration:.6f},asetpts=PTS-STARTPTS",
            "-t",
            f"{highlight_duration:.6f}",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(highlights_path),
        ]
        run_ffmpeg(concat_command, log_path, "event_highlights_concat")

        status.update(
            {
                "status": "completed",
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "tools": {"ffmpeg": ffmpeg_version(ffmpeg), "ffprobe": str(ffprobe)},
                "input": {
                    "source_video": str(source),
                    "source_sha256": source_sha256,
                    "source_ffprobe": source_probe,
                    "events_path": str(args.events.resolve()),
                    "events_sha256": sha256_file(args.events),
                    "num_events_total": len(all_events),
                    "num_events_rendered": len(events),
                    "events_by_label": dict(Counter(event["label"] for event in events)),
                    "render_interval_sec": [0.0, render_end],
                },
                "render": {
                    "temporal_only": True,
                    "spatial_boxes": False,
                    "display_window_sec": {
                        "pre": args.display_pre_sec,
                        "post": args.display_post_sec,
                    },
                    "highlight_context_sec": {
                        "pre": args.highlight_pre_sec,
                        "post": args.highlight_post_sec,
                    },
                    "label_colors": LABEL_COLORS,
                    "global_timeline": {
                        "source_canvas_px": [
                            int(source_info["video"]["width"]),
                            int(source_info["video"]["height"]),
                        ],
                        "output_canvas_px": [
                            int(source_info["video"]["width"]),
                            int(source_info["video"]["height"]) + TIMELINE_FOOTER_HEIGHT,
                        ],
                        "interval_sec": [0.0, configured_end],
                        "footer_height_px": TIMELINE_FOOTER_HEIGHT,
                        "track_x_px": TIMELINE_X,
                        "track_width_px": TIMELINE_WIDTH,
                        "marker_width_px": TIMELINE_MARKER_WIDTH,
                        "marker_colors": TIMELINE_COLORS,
                        "marker_lanes": {"Pass": "above", "Drive": "below"},
                        "playhead_color": "white",
                        "marker_count": len(all_events),
                    },
                    "video_encoder": {"codec": "libx264", "preset": args.preset, "crf": args.crf},
                    "full_audio": "copied from source without re-encoding",
                    "highlight_audio": "AAC 192 kb/s",
                    "intermediate_clip_dir": str(clip_dir),
                    "intermediate_clip_count": len(clip_paths),
                    "highlight_segments": segments,
                },
                "outputs": {
                    "annotated_full": output_record(ffprobe, annotated_path),
                    "event_highlights": output_record(ffprobe, highlights_path),
                },
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
