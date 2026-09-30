from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "render_miss_candidate_highlights.py"
SPEC = importlib.util.spec_from_file_location("render_miss_candidate_highlights", SCRIPT)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def test_window_filter_lists_candidate_scores_and_timecodes() -> None:
    candidates = [
        {
            "candidate_id": "candidate-000001",
            "label": "Pass",
            "ensemble_score": 0.123,
            "fold_max_score": 0.321,
            "evidence_sources": ["ensemble_low_peak", "fold_disagreement"],
            "timecode": "00:02:00.300",
        }
    ]
    window = {
        "priority": "high",
        "source_start_sec": 117.3,
        "source_end_sec": 124.3,
        "candidate_ids": ["candidate-000001"],
    }
    filter_text = renderer.build_window_filter(window, candidates, 1, 1)
    assert "MISS WINDOW 001/001" in filter_text
    assert "BAS 0.123" in filter_text
    assert "fold-max 0.321" in filter_text
    assert "low-peak+fold" in filter_text
    assert "event 00\\:02\\:00.300" in filter_text
    assert "SOURCE %{pts\\:hms\\:117.300000}" in filter_text
    assert "drawbox" in filter_text and "drawtext" in filter_text


def test_select_windows_uses_priority_review_order() -> None:
    windows = [
        {"priority": "medium", "review_order": 2},
        {"priority": "high", "review_order": 1},
        {"priority": "low", "review_order": 3},
    ]
    selected = renderer.select_windows(windows, {"high", "medium"}, None)
    assert [window["review_order"] for window in selected] == [1, 2]
