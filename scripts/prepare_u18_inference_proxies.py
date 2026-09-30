"""Create leakage-masked 25 FPS U18 inference proxies and exact configs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/u18_gt.yaml"))
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ffmpeg", required=True, type=Path)
    parser.add_argument("--ffprobe", required=True, type=Path)
    parser.add_argument("--video-id", action="append", help="Process one video_id; repeatable")
    parser.add_argument("--end-sec", type=float, help="Smoke-only exclusive end time in seconds")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("U18 配置缺失或 schema_version 不受支持")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exactly_one(paths: list[Path], description: str) -> Path:
    if len(paths) != 1:
        raise FileNotFoundError(f"{description} 应恰好匹配一个路径，实际为 {len(paths)}：{paths}")
    return paths[0]


def build_video_filter(proxy: dict[str, Any]) -> str:
    x, y, width, height = [int(value) for value in proxy["mask_source_rect_px"]]
    return (
        f"drawbox=x={x}:y={y}:w={width}:h={height}:color=black:t=fill,"
        f"scale={int(proxy['width'])}:{int(proxy['height'])}:flags={proxy['scale_filter']},"
        f"fps={float(proxy['fps']):g}"
    )


def build_ffmpeg_command(
    ffmpeg: Path,
    source: Path,
    destination: Path,
    proxy: dict[str, Any],
    end_sec: float | None,
) -> list[str]:
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "warning", "-stats"]
    if end_sec is not None:
        command.extend(["-t", f"{end_sec:.6f}"])
    command.extend(
        [
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-vf",
            build_video_filter(proxy),
            "-an",
            "-c:v",
            str(proxy["video_codec"]),
            "-preset",
            str(proxy["preset"]),
            "-crf",
            str(proxy["crf"]),
            "-pix_fmt",
            str(proxy["pixel_format"]),
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )
    return command


def probe_video(ffprobe: Path, path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,avg_frame_rate,nb_frames,duration",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    data = json.loads(completed.stdout)
    stream = data["streams"][0]
    return {
        "codec_name": stream["codec_name"],
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": stream["avg_frame_rate"],
        "frame_count": int(stream["nb_frames"]),
        "duration_sec": float(stream["duration"]),
        "size_bytes": int(data["format"]["size"]),
    }


def inference_config(video: dict[str, Any], output: Path, info: dict[str, Any], sha256: str, proxy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": {
            "basename": video["video_basename"],
            "sha256": video["video_sha256"],
            "duration_sec": float(video["duration_sec"]),
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "kickoff_offset_sec": 0.0,
            "interval_sec": [0.0, float(video["duration_sec"])],
        },
        "inference_input": {
            "basename": output.name,
            "sha256": sha256,
            "duration_sec": info["duration_sec"],
            "fps": float(proxy["fps"]),
            "width": int(proxy["width"]),
            "height": int(proxy["height"]),
            "audio": False,
            "generation": "25 FPS CFR; Bepro bottom event overlay masked before 1280x720 scaling",
            "mask_source_rect_px": list(proxy["mask_source_rect_px"]),
        },
        "model_preprocess": {
            "color": "grayscale",
            "padded_width": 1280,
            "padded_height": 736,
            "padding": "constant_black_centered",
            "frame_stack_size": 33,
            "frame_stack_step": 2,
        },
        "time_mapping": {
            "inference_frame_to_source_sec": "frame_index / 25.0",
            "max_round_trip_error_sec": 0.04,
        },
    }


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"拒绝覆盖既有输出目录：{args.output_root}")
    if not args.ffmpeg.is_file() or not args.ffprobe.is_file():
        raise FileNotFoundError("ffmpeg 或 ffprobe 不存在")
    if args.end_sec is not None and args.end_sec <= 0:
        raise ValueError("--end-sec 必须大于 0")

    config = load_config(args.config)
    source_root = (args.source_root or Path(config["source_root"])).resolve()
    selected = set(args.video_id or [])
    available = {video["video_id"] for video in config["videos"]}
    unknown = selected - available
    if unknown:
        raise ValueError(f"未知 video_id：{sorted(unknown)}")
    videos = [video for video in config["videos"] if not selected or video["video_id"] in selected]

    args.output_root.mkdir(parents=True)
    entries: list[dict[str, Any]] = []
    proxy = config["inference_proxy"]
    for video in videos:
        source = exactly_one(list(source_root.glob(video["video_glob"])), video["video_id"] + " 视频")
        if source.stat().st_size != int(video["video_size_bytes"]) or sha256_file(source) != video["video_sha256"]:
            raise ValueError(f"源视频身份不匹配：{source}")
        suffix = "_smoke" if args.end_sec is not None else ""
        output = args.output_root / (Path(video["proxy_basename"]).stem + suffix + ".mp4")
        partial = output.with_name(output.stem + ".partial.mp4")
        log_path = args.output_root / f"{video['video_id']}.ffmpeg.log"
        command = build_ffmpeg_command(args.ffmpeg, source, partial, proxy, args.end_sec)
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if completed.returncode != 0:
            raise RuntimeError(f"FFmpeg 失败，详见 {log_path}")
        partial.replace(output)
        info = probe_video(args.ffprobe, output)
        if info["width"] != int(proxy["width"]) or info["height"] != int(proxy["height"]) or info["fps"] != "25/1":
            raise ValueError(f"代理视频契约不匹配：{output}: {info}")
        output_hash = sha256_file(output)
        per_video_config = inference_config(video, output, info, output_hash, proxy)
        config_path = args.output_root / f"{video['video_id']}.yaml"
        config_path.write_text(
            yaml.safe_dump(per_video_config, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        entries.append(
            {
                "video_id": video["video_id"],
                "match_id": video["match_id"],
                "half": video["half"],
                "source_path": str(source),
                "source_sha256": video["video_sha256"],
                "proxy_path": str(output.resolve()),
                "proxy_basename": output.name,
                "proxy_sha256": output_hash,
                "proxy_info": info,
                "inference_config": str(config_path.resolve()),
                "inference_end_sec": min(float(video["duration_sec"]), info["duration_sec"]),
                "ffmpeg_log": str(log_path.resolve()),
            }
        )

    manifest = {
        "schema_version": 1,
        "dataset_id": config["dataset_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "smoke" if args.end_sec is not None else "completed",
        "gt_config": str(args.config.resolve()),
        "leakage_control": {
            "method": "opaque_black_mask",
            "mask_source_rect_px": list(proxy["mask_source_rect_px"]),
            "clean_source_preferred": True,
        },
        "videos": entries,
    }
    (args.output_root / "proxy_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"status": manifest["status"], "video_count": len(entries)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
