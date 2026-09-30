from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_u18_inference_proxies.py"
SPEC = importlib.util.spec_from_file_location("prepare_u18_inference_proxies", SCRIPT)
assert SPEC and SPEC.loader
proxy_builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proxy_builder)


def proxy_config() -> dict:
    return {
        "mask_source_rect_px": [0, 925, 920, 155],
        "width": 1280,
        "height": 720,
        "scale_filter": "lanczos",
        "fps": 25.0,
        "video_codec": "libx264",
        "preset": "fast",
        "crf": 18,
        "pixel_format": "yuv420p",
    }


def test_video_filter_masks_before_scaling_and_resampling() -> None:
    assert proxy_builder.build_video_filter(proxy_config()) == (
        "drawbox=x=0:y=925:w=920:h=155:color=black:t=fill,"
        "scale=1280:720:flags=lanczos,fps=25"
    )


def test_ffmpeg_command_is_video_only_and_refuses_implicit_audio() -> None:
    command = proxy_builder.build_ffmpeg_command(
        Path("ffmpeg"), Path("source.mp4"), Path("output.partial.mp4"), proxy_config(), 12.0
    )
    assert command[command.index("-vf") + 1].startswith("drawbox=")
    assert "-an" in command
    assert command[command.index("-t") + 1] == "12.000000"
    assert command[-1] == "output.partial.mp4"
