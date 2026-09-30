from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_miss_candidates.py"
SPEC = importlib.util.spec_from_file_location("generate_miss_candidates", SCRIPT)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


def candidate(time_sec: float, label: str = "Pass", score: float = 0.08) -> dict:
    return {
        "time_sec": time_sec,
        "timecode": generator.format_timecode(time_sec),
        "frame_index": round(time_sec * 25),
        "label": label,
        "suggested_label": label,
        "ensemble_score": score,
        "fold_mean_score": score,
        "fold_max_score": score,
        "fold_std_score": 0.0,
        "folds_above_official": 0,
        "evidence_sources": ["ensemble_low_peak"],
        "tracking_score": None,
        "far_side_score": None,
        "tracking_confidence": None,
        "tracking_reason": "",
        "priority": "medium",
        "candidate_id": "",
    }


def test_mine_bas_proposals_keeps_low_peak_and_fold_disagreement() -> None:
    frame_indexes = np.arange(120)
    ensemble = np.zeros((120, 2), dtype=float)
    folds = np.zeros((120, 3, 2), dtype=float)
    ensemble[40, 0] = 0.15
    folds[80, 0, 1] = 0.9
    smoothed, fold_smoothed = generator.smooth_score_arrays(ensemble, folds, 1.0)
    proposals = generator.mine_bas_proposals(
        frame_indexes,
        25.0,
        ("PASS", "DRIVE"),
        smoothed,
        fold_smoothed,
        0.03,
        0.2,
        0.1,
        10,
    )
    sources = {source for proposal in proposals for source in proposal["evidence_sources"]}
    assert "ensemble_low_peak" in sources
    assert "fold_disagreement" in sources


def test_finalize_excludes_existing_same_label_event() -> None:
    candidates = [candidate(10.0), candidate(20.0, "Drive")]
    official = [{"event_id": "event-1", "time_sec": 10.4, "label": "Pass"}]
    result = generator.finalize_candidates(candidates, official, 1.0, 0.05, 0.12, 0.2)
    assert [item["label"] for item in result] == ["Drive"]


def test_review_windows_merge_nearby_candidates_but_keep_distant_ones() -> None:
    candidates = [candidate(10.0), candidate(11.5, "Drive"), candidate(30.0)]
    for index, item in enumerate(candidates, start=1):
        item["candidate_id"] = f"candidate-{index:06d}"
    windows = generator.build_review_windows(candidates, 40.0, 3.0, 4.0, 2.0, 15.0)
    assert len(windows) == 2
    assert windows[0]["candidate_ids"] == ["candidate-000001", "candidate-000002"]
    assert windows[0]["source_start_sec"] == 7.0
    assert windows[0]["source_end_sec"] == 15.5


def test_review_windows_merge_overlapping_context() -> None:
    candidates = [candidate(10.0), candidate(16.0, "Drive")]
    for index, item in enumerate(candidates, start=1):
        item["candidate_id"] = f"candidate-{index:06d}"
    windows = generator.build_review_windows(candidates, 30.0, 3.0, 4.0, 0.0, 15.0)
    assert len(windows) == 1
    assert windows[0]["duration_sec"] == 13.0


def test_seed_xlsx_forward_fills_hour_and_minute(tmp_path: Path) -> None:
    path = tmp_path / "seeds.xlsx"
    pd.DataFrame(
        {
            "hour": [0, None, None],
            "min": [2, None, 5],
            "sec": [0.3, 56.433, 48.767],
            "action": ["pass", "pass", "drive"],
            "side": ["far", "far", "far"],
        }
    ).to_excel(path, index=False)
    seeds = generator.load_seed_misses(path, 600.0)
    assert [seed["time_sec"] for seed in seeds] == [120.3, 176.433, 348.767]
    assert [seed["label"] for seed in seeds] == ["Pass", "Pass", "Drive"]


def test_seed_coverage_is_not_named_formal_recall() -> None:
    candidates = [candidate(10.4)]
    candidates[0]["candidate_id"] = "candidate-000001"
    seeds = [
        {
            "seed_id": "seed-000001",
            "time_sec": 10.0,
            "timecode": "00:00:10.000",
            "label": "Pass",
            "side": "far",
        }
    ]
    result = generator.seed_coverage(seeds, candidates, 1.0)
    assert result["num_covered"] == 1
    assert "not formal recall" in result["description"]


def test_tracking_interface_accepts_unknown_label(tmp_path: Path) -> None:
    path = tmp_path / "tracking.csv"
    pd.DataFrame(
        {
            "time_sec": [42.0],
            "label": [""],
            "tracking_score": [0.8],
            "far_side_score": [0.9],
            "tracking_confidence": [0.4],
            "reason": ["possession_change"],
        }
    ).to_csv(path, index=False)
    rows = generator.load_tracking_candidates(path, 100.0)
    assert rows[0]["label"] == "Unknown"
    assert rows[0]["tracking_reason"] == "possession_change"


def test_tracking_only_candidate_can_join_without_bas_peak() -> None:
    frame_indexes = np.arange(100)
    ensemble = np.full((100, 2), 0.01, dtype=float)
    folds = np.full((100, 3, 2), 0.01, dtype=float)
    candidates: list[dict] = []
    generator.add_tracking_proposals(
        candidates,
        [
            {
                "time_sec": 2.0,
                "label": "Unknown",
                "tracking_score": 0.8,
                "far_side_score": 0.9,
                "tracking_confidence": 0.4,
                "tracking_reason": "possession_change",
            }
        ],
        frame_indexes,
        25.0,
        ("PASS", "DRIVE"),
        ensemble,
        folds,
        0.2,
        [],
        1.0,
        1.0,
    )
    assert len(candidates) == 1
    assert candidates[0]["label"] == "Unknown"
    assert candidates[0]["evidence_sources"] == ["tracking_change"]
    assert candidates[0]["tracking_score"] == 0.8
