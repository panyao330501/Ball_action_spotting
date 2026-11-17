from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "curate_u18_candidate_frames.py"
SPEC = importlib.util.spec_from_file_location("curate_u18_candidate_frames", SCRIPT)
assert SPEC and SPEC.loader
curator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(curator)


def test_allocation_keeps_two_matches_balanced_and_most_frames_in_h2() -> None:
    quotas = curator.allocation(60, 0.8)
    assert quotas == {
        (1, "Pass"): 6,
        (1, "Reception candidate"): 6,
        (2, "Pass"): 24,
        (2, "Reception candidate"): 24,
    }


def test_raw_bepro_code_keeps_reception_semantics_and_known_review_gap() -> None:
    event = {
        "event_id": "test-42", "video_id": "match_h2", "source_time_sec": "120.0",
        "bepro_code": "パス(受け手)", "label": "Drive", "x": "0.9", "y": "0.05",
    }
    assert curator.action_for(event) == "Reception candidate"
    assert curator.field_zone(event) == "x2_y0"
    ids, times = curator.exclusion_index([
        {"event_id": "test-41", "video_id": "match_h2", "source_time_sec": "116.0"}
    ])
    assert curator.is_near_exclusion(event, ids, times, 5.0)
    assert not curator.is_near_exclusion(event, ids, times, 3.0)


def test_frame_number_is_one_based_while_frame_index_is_zero_based() -> None:
    fps = 30.0
    event_time = 2734.715 - 2700
    frame_index = round(event_time * fps)
    assert frame_index == 1041
    assert frame_index + 1 == 1042
    assert abs(frame_index / fps - event_time) < 1 / (2 * fps)
