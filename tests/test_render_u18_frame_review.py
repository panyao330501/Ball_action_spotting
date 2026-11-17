from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_u18_frame_review.py"
SPEC = importlib.util.spec_from_file_location("render_u18_frame_review", SCRIPT)
assert SPEC and SPEC.loader
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


def test_context_clip_preserves_source_frame_identity() -> None:
    row = {"candidate_id": "u18-frame-001", "event_id": "u18-gt-000003",
           "video_id": "h1", "source_fps": "30", "frame_index": "177"}
    clip = review.clip_contract(row, {"frame_count": 82987}, 5.0)
    assert clip["source_start_frame"] == 27
    assert clip["source_end_frame"] == 327
    assert clip["frame_count"] == 301
    assert clip["center_relative_frame"] == 150
    assert clip["source_start_sec"] == 0.9


def test_context_clip_clamps_to_video_boundary() -> None:
    row = {"candidate_id": "sample", "event_id": "event", "video_id": "h1",
           "source_fps": "30", "frame_index": "98"}
    clip = review.clip_contract(row, {"frame_count": 100}, 5.0)
    assert clip["source_start_frame"] == 0
    assert clip["source_end_frame"] == 99
    assert clip["frame_count"] == 100
    assert clip["center_relative_frame"] == 98
