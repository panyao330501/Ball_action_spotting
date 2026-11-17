"""Queue visually confirmed Pass FP cases for Bepro identity and time review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def csv_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-review", required=True, type=Path)
    parser.add_argument("--new-review", required=True, type=Path)
    parser.add_argument("--frozen-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--page-template", type=Path,
                        default=Path("web/u18_pass_identity_review/index.html"))
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖待核清单：{args.output_dir}")
    frozen = json.loads((args.frozen_dir / "manifest.json").read_text(encoding="utf-8"))
    gt = []
    for fold in frozen["folds"][:1]:
        for name, expected in (("train_gt_pass.json", fold["train_gt_sha256"]),
                               ("test_gt_pass.json", fold["test_gt_sha256"])):
            path = args.frozen_dir / fold["fold_id"] / name
            if sha256(path) != expected:
                raise ValueError(f"冻结 GT 哈希不符：{path}")
            gt.extend(json.loads(path.read_text(encoding="utf-8")))
    if len(gt) != 1651:
        raise ValueError("冻结 Pass GT 总数不符")
    by_video = {}
    for event in gt:
        by_video.setdefault(event["video_id"], []).append(event)
    rows = []
    for source, path, clip_dir, site_manifest in (
        ("prior_28", args.prior_review,
         "artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_site/clips",
         "artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_site/manifest.json"),
        ("new_32", args.new_review,
         "artifacts/u18_pass_cv/20261116_training_review_v1/review_site/clips",
         "artifacts/u18_pass_cv/20261116_training_review_v1/review_site/manifest.json"),
    ):
        clip_by_id = {item["review_id"]: item for item in json.loads(
            Path(site_manifest).read_text(encoding="utf-8"))["clips"]}
        for review in csv_rows(path):
            if review["algorithmic_status"] != "FP" or review["human_judgment"] != "确有 Pass":
                continue
            video_id = review["video_id"]
            moment = float(review["source_time_sec"])
            nearest = min(by_video[video_id],
                          key=lambda item: abs(float(item["source_time_sec"]) - moment))
            gap = abs(float(nearest["source_time_sec"]) - moment)
            clip = clip_by_id[review["review_id"]]
            clip_path = Path(clip_dir) / f"{review['review_id']}.mp4"
            if sha256(clip_path) != clip["sha256"]:
                raise ValueError(f"片段哈希不符：{clip_path}")
            rows.append({
                "review_id": review["review_id"], "source_review": source,
                "video_id": video_id, "prediction_time_sec": f"{moment:.3f}",
                "nearest_bepro_event_id": nearest["event_id"],
                "nearest_bepro_time_sec": f"{float(nearest['source_time_sec']):.3f}",
                "nearest_gap_sec": f"{gap:.3f}",
                "priority": "P1_check_missing_event" if gap > 3.0 else "P2_check_same_action_or_offset",
                "human_prior_comment": review["human_comment"],
                "clip_path": clip_path.as_posix(), "clip_start_sec": f"{clip['start_sec']:.3f}",
                "clip_sha256": clip["sha256"],
                "identity_decision": "", "confirmed_pass_time_sec": "",
                "confirmed_frame_index_25fps": "", "new_comment": "",
            })
    if len(rows) != 17 or len({row["review_id"] for row in rows}) != 17:
        raise ValueError("视觉 Pass FP 应恰有 17 个唯一 ID")
    rows.sort(key=lambda row: (row["priority"], row["video_id"], float(row["prediction_time_sec"])))
    args.output_dir.mkdir(parents=True)
    output_path = args.output_dir / "identity_review.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    data_path = args.output_dir / "review_data.json"
    data_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    page_path = args.output_dir / "index.html"
    shutil.copyfile(args.page_template, page_path)
    manifest = {
        "schema_version": 1, "status": "awaiting_human_identity_review",
        "prior_review_sha256": sha256(args.prior_review),
        "new_review_sha256": sha256(args.new_review),
        "frozen_manifest_sha256": sha256(args.frozen_dir / "manifest.json"),
        "identity_review_sha256": sha256(output_path),
        "review_data_sha256": sha256(data_path), "page_sha256": sha256(page_path),
        "count": len(rows), "priority_1_count": sum(row["priority"].startswith("P1") for row in rows),
        "note": "Nearest GT is a time hint only, never proof of the same action; do not add labels automatically.",
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
