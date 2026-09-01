from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_visualization.py"
SPEC = importlib.util.spec_from_file_location("render_visualization", SCRIPT)
assert SPEC and SPEC.loader
render = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render)


def event(event_id: str, time_sec: float, label: str = "Pass") -> dict:
    return {
        "event_id": event_id,
        "time_sec": time_sec,
        "timecode": render.format_timecode(time_sec),
        "label": label,
        "confidence": 0.75,
        "visibility": "VISIBLE",
        "review_status": "unreviewed",
        "comment": "",
    }


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0.0, "00:00:00.000"), (17.04, "00:00:17.040"), (3661.9996, "01:01:02.000")],
)
def test_format_timecode(seconds: float, expected: str) -> None:
    assert render.format_timecode(seconds) == expected


def test_load_events_rejects_invalid_confidence(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    invalid = event("event-000001", 1.0)
    invalid["confidence"] = 1.1
    path.write_text(__import__("json").dumps([invalid]), encoding="utf-8")
    with pytest.raises(ValueError, match="confidence"):
        render.load_events(path, 10.0)


def test_cluster_rows_preserve_chronological_order() -> None:
    events = [event(f"event-{index:06d}", time_sec) for index, time_sec in enumerate([1.0, 2.0, 4.49, 4.6], 1)]
    assert render.assign_cluster_rows(events, 0.5, 2.0) == [0, 1, 2, 3]


def test_cluster_rows_reset_after_gap() -> None:
    events = [event("event-000001", 1.0), event("event-000002", 4.0)]
    assert render.assign_cluster_rows(events, 0.5, 2.0) == [0, 0]


def test_highlight_segments_clip_source_boundaries() -> None:
    events = [event("event-000001", 1.0), event("event-000002", 9.0, "Drive")]
    segments = render.highlight_segments(events, 10.0, 3.0, 4.0)
    assert segments[0]["source_start_sec"] == 0.0
    assert segments[0]["source_end_sec"] == 5.0
    assert segments[1]["source_start_sec"] == 6.0
    assert segments[1]["source_end_sec"] == 10.0
    assert segments[1]["highlight_start_sec"] == 5.0
    assert segments[1]["highlight_end_sec"] == 9.0


def test_filters_explicitly_use_temporal_overlays_only() -> None:
    events = [event("event-000001", 2.0)]
    annotated = render.build_annotated_filter(events, 10.0, 0.5, 2.0)
    segment = render.highlight_segments(events, 10.0, 3.0, 4.0)[0]
    highlights = render.build_highlight_clip_filter(segment, 1)
    assert "SOURCE %{pts\\:hms}" in annotated
    assert "Pass" in annotated
    assert "drawbox" in annotated and "drawtext" in annotated
    assert "EVENT 01/01" in highlights
    assert "drawbox" in highlights and "drawtext" in highlights
