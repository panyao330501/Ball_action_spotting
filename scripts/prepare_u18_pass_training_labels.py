"""Build match-isolated Pass training labels from frozen Bepro GT and human review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path


REVIEW_FIELDS = {"human_visibility", "human_judgment", "human_comment"}
OFFSET = re.compile(r"^\s*([+-]\d+(?:\.\d+)?)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def check_review(source: Path, reviewed: Path) -> list[dict[str, str]]:
    fields, source_rows = read_csv(source)
    reviewed_fields, reviewed_rows = read_csv(reviewed)
    if fields != reviewed_fields or len(source_rows) != len(reviewed_rows):
        raise ValueError(f"审查字段或行数与原清单不符：{reviewed}")
    source_by_id = {row["review_id"]: row for row in source_rows}
    reviewed_by_id = {row["review_id"]: row for row in reviewed_rows}
    if (len(source_by_id) != len(source_rows) or len(reviewed_by_id) != len(reviewed_rows)
            or set(source_by_id) != set(reviewed_by_id)):
        raise ValueError(f"审查 ID 不完整或重复：{reviewed}")
    for review_id, row in reviewed_by_id.items():
        original = source_by_id[review_id]
        for field in fields:
            if field not in REVIEW_FIELDS and field != "source_timecode" and row[field] != original[field]:
                raise ValueError(f"非人工字段被修改：{review_id}/{field}")
        if (row["human_visibility"] not in {"VISIBLE", "PARTIAL", "OFFSCREEN", "UNCLEAR"}
                or row["human_judgment"] not in {"确有 Pass", "无 Pass", "时间偏移", "类别不符", "无法判断"}):
            raise ValueError(f"人工判断不完整或不合法：{review_id}")
    return reviewed_rows


def save_json(path: Path, value: object) -> str:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sha256(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/u18_pass_match_cv.json"))
    parser.add_argument("--frozen-dir", required=True, type=Path)
    parser.add_argument("--prior-source", required=True, type=Path)
    parser.add_argument("--prior-reviewed", required=True, type=Path)
    parser.add_argument("--new-source", required=True, type=Path)
    parser.add_argument("--new-reviewed", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖训练标签版本：{args.output_dir}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    ground_truth_path = Path(config["ground_truth_path"])
    if sha256(ground_truth_path) != config["ground_truth_sha256"]:
        raise ValueError("原始可评估 GT 哈希与冻结配置不一致")
    all_gt = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    frozen = json.loads((args.frozen_dir / "manifest.json").read_text(encoding="utf-8"))
    if frozen["config_sha256"] != sha256(args.config):
        raise ValueError("冻结分组与当前配置哈希不一致")
    reviews = check_review(args.prior_source, args.prior_reviewed) + check_review(args.new_source, args.new_reviewed)
    seen = set()
    for row in reviews:
        if row["review_id"] in seen:
            raise ValueError(f"跨表审查 ID 重复：{row['review_id']}")
        seen.add(row["review_id"])
    results = []
    for fold in config["folds"]:
        fold_id = fold["fold_id"]
        frozen_fold = next(item for item in frozen["folds"] if item["fold_id"] == fold_id)
        train_ids = set(frozen_fold["train_video_ids"])
        test_ids = set(frozen_fold["test_video_ids"])
        if train_ids & test_ids or len(train_ids) != 2 or len(test_ids) != 2:
            raise ValueError(f"比赛隔离失败：{fold_id}")
        frozen_dir = args.frozen_dir / fold_id
        train_path = frozen_dir / "train_gt_pass.json"
        test_path = frozen_dir / "test_gt_pass.json"
        if sha256(train_path) != frozen_fold["train_gt_sha256"] or sha256(test_path) != frozen_fold["test_gt_sha256"]:
            raise ValueError(f"冻结 GT 哈希不一致：{fold_id}")
        train_gt = json.loads(train_path.read_text(encoding="utf-8"))
        drive_proxies = [
            {"event_id": item["event_id"], "video_id": item["video_id"],
             "source_time_sec": item["source_time_sec"], "mapping_status": item["mapping_status"]}
            for item in all_gt if item["video_id"] in train_ids and item["label"] == "Drive"
        ]
        if {item["video_id"] for item in train_gt} != train_ids:
            raise ValueError(f"训练 GT 含测试视频：{fold_id}")
        train_reviews = [row for row in reviews if row["video_id"] in train_ids]
        gt_by_id = {item["event_id"]: item for item in train_gt}
        reviewed_gt = {}
        pending_additions = []
        for row in train_reviews:
            if row["algorithmic_status"] == "FN":
                gt_id = row["gt_event_id"]
                if gt_id not in gt_by_id or gt_id in reviewed_gt:
                    raise ValueError(f"FN 缺 GT 或重复复核：{row['review_id']}")
                reviewed_gt[gt_id] = row
            elif row["algorithmic_status"] == "FP" and row["human_judgment"] == "确有 Pass":
                pending_additions.append({
                    "review_id": row["review_id"],
                    "video_id": row["video_id"],
                    "prediction_time_sec": float(row["source_time_sec"]),
                    "visibility": row["human_visibility"],
                    "comment": row["human_comment"],
                    "status": "pending_event_identity_and_exact_time",
                })

        labels = []
        excluded = []
        ignore = []
        corrections = []
        for event in train_gt:
            review = reviewed_gt.get(event["event_id"])
            original_time = float(event["source_time_sec"])
            reason = None
            if review:
                if review["human_visibility"] in {"OFFSCREEN", "UNCLEAR"} or review["human_judgment"] == "无法判断":
                    reason = "unobservable_or_uncertain"
                elif review["human_judgment"] in {"无 Pass", "类别不符"}:
                    reason = "human_rejected_bepro_pass"
            if reason:
                excluded.append({
                    "event_id": event["event_id"], "video_id": event["video_id"],
                    "bepro_time_sec": original_time, "reason": reason,
                    "review_id": review["review_id"], "comment": review["human_comment"],
                })
                ignore.append({"video_id": event["video_id"], "start_sec": max(0, original_time - 3),
                               "end_sec": original_time + 3, "reason": reason, "review_id": review["review_id"]})
                continue
            offset = None
            if review:
                match = OFFSET.match(review["human_comment"])
                if match:
                    offset = float(match.group(1))
                elif review["human_judgment"] == "时间偏移":
                    raise ValueError(f"标为时间偏移但没有数值备注：{review['review_id']}")
            training_time = original_time + (offset or 0.0)
            if not math.isfinite(training_time) or training_time < 1.32:
                raise ValueError(f"训练时间越界：{event['event_id']}")
            label = {
                "event_id": event["event_id"], "video_id": event["video_id"], "label": "Pass",
                "bepro_time_sec": original_time, "training_time_sec": round(training_time, 3),
                "training_frame_index_25fps": round(training_time * 25),
                "source": "human_time_correction" if offset is not None else "bepro_pass",
                "review_id": review["review_id"] if review else "",
                "visibility": review["human_visibility"] if review else "unreviewed",
            }
            labels.append(label)
            if offset is not None:
                corrections.append({**label, "offset_sec": offset, "comment": review["human_comment"]})
        for item in pending_additions:
            moment = item["prediction_time_sec"]
            ignore.append({"video_id": item["video_id"], "start_sec": max(0, moment - 3),
                           "end_sec": moment + 3, "reason": "confirmed_pass_pending_exact_label",
                           "review_id": item["review_id"]})
        if len(labels) + len(excluded) != len(train_gt):
            raise ValueError(f"训练 GT 计数不守恒：{fold_id}")
        if {item["video_id"] for item in labels + excluded + pending_additions + ignore} - train_ids:
            raise ValueError(f"训练产物包含测试视频：{fold_id}")
        if {item["video_id"] for item in drive_proxies} - train_ids:
            raise ValueError(f"接球避让清单包含测试视频：{fold_id}")
        fold_dir = args.output_dir / fold_id
        fold_dir.mkdir(parents=True)
        hashes = {}
        for name, items in (
            ("train_pass_events.json", labels), ("excluded_bepro_pass.json", excluded),
            ("pending_pass_additions.json", pending_additions), ("ignore_intervals.json", ignore),
            ("time_corrections.json", corrections), ("drive_proxy_events.json", drive_proxies),
        ):
            hashes[name] = save_json(fold_dir / name, items)
        results.append({
            "fold_id": fold_id, "train_video_ids": sorted(train_ids), "test_video_ids": sorted(test_ids),
            "frozen_train_gt_sha256": frozen_fold["train_gt_sha256"],
            "frozen_test_gt_sha256": frozen_fold["test_gt_sha256"],
            "train_review_count": len(train_reviews), "original_bepro_pass": len(train_gt),
            "training_pass": len(labels), "excluded_bepro_pass": len(excluded),
            "time_corrections": len(corrections), "pending_pass_additions": len(pending_additions),
            "drive_proxy_events": len(drive_proxies),
            "output_sha256": hashes,
        })
    manifest = {
        "schema_version": 1,
        "purpose": "match-isolated Pass training labels; forbidden as test GT",
        "config_sha256": sha256(args.config),
        "frozen_manifest_sha256": sha256(args.frozen_dir / "manifest.json"),
        "source_sha256": {
            "prior_source": sha256(args.prior_source), "prior_reviewed": sha256(args.prior_reviewed),
            "new_source": sha256(args.new_source), "new_reviewed": sha256(args.new_reviewed),
        },
        "folds": results,
    }
    save_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
