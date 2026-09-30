from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_u18_predictions.py"
SPEC = importlib.util.spec_from_file_location("evaluate_u18_predictions", SCRIPT)
assert SPEC and SPEC.loader
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


def gt(event_id: str, time_sec: float, label: str = "Pass", video_id: str = "v1") -> dict:
    return {
        "event_id": event_id,
        "video_id": video_id,
        "label": label,
        "source_time_sec": time_sec,
        "evaluation_status": "evaluable",
    }


def prediction(time_sec: float, confidence: float, label: str = "Pass", video_id: str = "v1") -> dict:
    return {
        "event_id": "",
        "video_id": video_id,
        "label": label,
        "time_sec": time_sec,
        "confidence": confidence,
    }


def test_ranked_matching_is_one_to_one() -> None:
    truth = [gt("a", 10.0)]
    predictions = [prediction(10.1, 0.9), prediction(10.2, 0.8)]
    true_positive, matches = evaluator.ranked_matches(truth, predictions, "Pass", 1.0)
    assert true_positive == [1, 0]
    assert matches[0]["event_id"] == "a"
    assert matches[1] is None


def test_average_precision_penalizes_high_confidence_false_positive() -> None:
    assert evaluator.average_precision([0, 1], 1) == 0.5
    assert evaluator.average_precision([1, 0], 1) == 1.0


def test_evaluate_group_reports_recall_and_map() -> None:
    truth = [gt("a", 10.0, "Pass"), gt("b", 20.0, "Drive")]
    truth[0]["distance_band"] = "far"
    truth[1]["distance_band"] = "near"
    predictions = [prediction(10.4, 0.9, "Pass"), prediction(20.2, 0.8, "Drive")]
    metrics = evaluator.evaluate_group(truth, predictions, [0.5, 1.0], 0.2)
    assert metrics["tolerances"]["0.5"]["map"] == 1.0
    assert metrics["tolerances"]["1"]["classes"]["Drive"]["recall"] == 1.0
    assert metrics["tolerances"]["1"]["recall_by_gt_distance_band"]["Pass"]["far"]["recall"] == 1.0
