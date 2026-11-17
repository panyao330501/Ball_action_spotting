from __future__ import annotations

import csv
import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_u18_eval_review.py"
SPEC = importlib.util.spec_from_file_location("render_u18_eval_review", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_clip_contract_keeps_event_on_proxy_frame_and_clamps_edges():
    proxy = {"proxy_info": {"frame_count": 300}}
    early = MODULE.clip_contract(
        {"review_id": "first", "video_id": "video", "source_time_sec": "0.020"}, proxy, 5.0
    )
    late = MODULE.clip_contract(
        {"review_id": "last", "video_id": "video", "source_time_sec": "11.900"}, proxy, 5.0
    )
    assert (early["start_frame"], early["center_relative_frame"]) == (0, 0)
    assert (late["end_frame"], late["start_frame"] + late["center_relative_frame"]) == (299, 298)
    assert late["fps"] == 25


def test_read_rows_restores_milliseconds_after_spreadsheet_save(tmp_path):
    path = tmp_path / "review.csv"
    fields = [
        "review_id", "video_id", "label", "algorithmic_status", "source_time_sec",
        "source_timecode", "source_video", "human_visibility", "human_judgment", "human_comment",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "review_id": "case-1", "video_id": "video", "label": "Pass", "algorithmic_status": "FN",
            "source_time_sec": "384.843", "source_timecode": "06:24.8", "source_video": "source.mp4",
        })
    returned_fields, rows = MODULE.read_rows(path)
    assert returned_fields == fields
    assert rows[0]["source_timecode"] == "00:06:24.843"


def test_drive_audit_rows_keep_original_export_columns(tmp_path):
    path = tmp_path / "drive.csv"
    fields = [
        "event_id", "video_id", "label", "source_time_sec", "source_timecode",
        "mapping_status", "review_mapping", "review_observation", "review_comment",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "event_id": "u18-gt-1", "video_id": "video", "label": "Drive",
            "source_time_sec": "185.637", "mapping_status": "provisional_receiver_proxy",
            "review_mapping": "unreviewed",
        })
    returned_fields, rows = MODULE.read_rows(path, "drive")
    assert returned_fields == fields
    assert rows[0]["review_id"] == "u18-gt-1"
    assert rows[0]["algorithmic_status"] == "AUDIT"
    assert rows[0]["source_timecode"] == "00:03:05.637"
