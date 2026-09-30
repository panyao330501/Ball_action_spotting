from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_u18_ground_truth.py"
SPEC = importlib.util.spec_from_file_location("prepare_u18_ground_truth", SCRIPT)
assert SPEC and SPEC.loader
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def test_second_half_match_time_is_converted_to_video_time(tmp_path: Path) -> None:
    xml = tmp_path / "events.xml"
    xml.write_text(
        """<file><ALL_INSTANCES><instance><ID>7</ID><start>29.715</start><end>39.715</end><code>パス</code><label><group>MATCH TIME</group><text>2734.715</text></label><label><group>TEAM</group><text>A</text></label><label><group>パス 結果</group><text>失敗</text></label></instance></ALL_INSTANCES></file>""",
        encoding="utf-8",
    )
    video = {
        "video_id": "match_h2",
        "match_id": "match",
        "half": 2,
        "match_time_offset_sec": 2700.0,
        "duration_sec": 100.0,
    }
    events = converter.parse_event_xml(
        xml,
        tmp_path,
        video,
        {"パス": {"label": "Pass", "status": "direct"}},
        {"near_max_exclusive": 1 / 3, "far_min_inclusive": 2 / 3},
        1.32,
    )
    assert len(events) == 1
    assert events[0]["source_time_sec"] == 34.715
    assert events[0]["match_time_sec"] == 2734.715
    assert events[0]["pass_result"] == "失敗"
    assert events[0]["evaluation_status"] == "evaluable"


def test_context_guard_and_outside_video_are_excluded() -> None:
    assert converter.evaluation_status(0.441, 100.0, 1.32) == (
        "excluded",
        "model_context_guard_start",
    )
    assert converter.evaluation_status(99.0, 100.0, 1.32) == (
        "excluded",
        "model_context_guard_end",
    )
    assert converter.evaluation_status(101.0, 100.0, 1.32) == (
        "excluded",
        "outside_video",
    )


def test_drive_audit_sample_is_balanced_by_video() -> None:
    events = [
        {"video_id": video_id, "source_time_sec": float(index), "label": "Drive", "y": index / 20}
        for video_id in ("a", "b", "c", "d")
        for index in range(20)
    ]
    sample = converter.drive_audit_sample(events, 50)
    counts = {video_id: sum(row["video_id"] == video_id for row in sample) for video_id in "abcd"}
    assert counts == {"a": 13, "b": 13, "c": 12, "d": 12}
    assert all(row["review_mapping"] == "unreviewed" for row in sample)


def test_distance_band_uses_camera_side_verified_bepro_y() -> None:
    spatial = {"near_max_exclusive": 1 / 3, "far_min_inclusive": 2 / 3}
    assert converter.distance_band(0.0, spatial) == "near"
    assert converter.distance_band(0.5, spatial) == "mid"
    assert converter.distance_band(1.0, spatial) == "far"
    assert converter.distance_band(None, spatial) == "unknown"
