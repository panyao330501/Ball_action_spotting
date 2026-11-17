"""Select new Pass training-label review cases without changing frozen test GT."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def timecode(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, remainder = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{remainder:03d}"


def choose(candidates: list[dict], used_times: list[float], count: int) -> list[dict]:
    chosen = []
    for candidate in candidates:
        if all(abs(candidate["time"] - value) >= 10 for value in used_times):
            chosen.append(candidate)
            used_times.append(candidate["time"])
            if len(chosen) == count:
                break
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--prior-review", type=Path, required=True)
    parser.add_argument("--proxy-manifest", type=Path, required=True)
    parser.add_argument("--predictions-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖现有审查目录：{args.output_dir}")

    matches = [row for row in read_csv(args.matches) if row["label"] == "Pass"]
    gt = [row for row in json.loads(args.ground_truth.read_text(encoding="utf-8")) if row["label"] == "Pass"]
    proxy = {row["video_id"]: row for row in json.loads(args.proxy_manifest.read_text(encoding="utf-8"))["videos"]}
    reviewed = read_csv(args.prior_review)
    gt_by_video = defaultdict(list)
    matches_by_video = defaultdict(list)
    old_times = defaultdict(list)
    for event in gt:
        gt_by_video[event["video_id"]].append(event)
    for row in matches:
        matches_by_video[row["video_id"]].append(row)
    for row in reviewed:
        old_times[row["video_id"]].append(float(row["source_time_sec"]))

    if set(proxy) != set(gt_by_video) or set(proxy) != set(matches_by_video):
        raise ValueError("四个半场的视频集合不一致")
    selected = []
    prediction_hashes = {}
    for video_id in sorted(proxy):
        prediction_path = args.predictions_root / video_id / "events.json"
        prediction_hashes[video_id] = sha256(prediction_path)
        peaks = [row for row in json.loads(prediction_path.read_text(encoding="utf-8")) if row["label"] == "Pass"]
        peak_times = [(float(row["time_sec"]), float(row["confidence"])) for row in peaks]
        used = list(old_times[video_id])
        gt_video = gt_by_video[video_id]
        fp_candidates = []
        for row in matches_by_video[video_id]:
            if row["status"] != "FP":
                continue
            moment = float(row["prediction_time_sec"])
            nearest = min(gt_video, key=lambda event: abs(moment - float(event["source_time_sec"])))
            gap = abs(moment - float(nearest["source_time_sec"]))
            fp_candidates.append({"time": moment, "row": row, "gap": gap, "near_gt": nearest})
        fp_candidates.sort(key=lambda item: (-float(item["row"]["confidence"]), item["time"]))
        close = [item for item in fp_candidates if 1 < item["gap"] <= 3]
        distant = [item for item in fp_candidates if item["gap"] > 3]
        fp_chosen = choose(close, used, 2) + choose(distant, used, 2)
        if len(fp_chosen) < 4:
            fp_chosen += choose(fp_candidates, used, 4 - len(fp_chosen))

        fn_candidates = []
        gt_by_id = {event["event_id"]: event for event in gt_video}
        for row in matches_by_video[video_id]:
            if row["status"] != "FN":
                continue
            event = gt_by_id[row["gt_event_id"]]
            if event["distance_band"] != "far":
                continue
            moment = float(row["gt_time_sec"])
            nearby = [score for peak_time, score in peak_times if abs(peak_time - moment) <= 2]
            fn_candidates.append({"time": moment, "row": row, "signal": max(nearby, default=0.0)})
        fn_candidates.sort(key=lambda item: (-item["signal"], item["time"]))
        fn_chosen = choose(fn_candidates, used, 2)
        fn_chosen += choose(list(reversed(fn_candidates)), used, 2)
        if len(fn_chosen) < 4:
            fn_chosen += choose(fn_candidates, used, 4 - len(fn_chosen))
        if len(fp_chosen) != 4 or len(fn_chosen) != 4:
            raise ValueError(f"半场无法找到 4 FP + 4 far FN 且与旧样本相隔 10 秒：{video_id}")

        for item in [*fp_chosen, *fn_chosen]:
            row = item["row"]
            moment = item["time"]
            status = row["status"]
            reason = ("高分未匹配：核对实际动作及 Bepro 时间/漏标" if status == "FP"
                      else "远侧漏检：核对动作可见性和实际时刻")
            selected.append({
                "review_id": f"u18-train-{len(selected) + 1:03d}",
                "video_id": video_id,
                "label": "Pass",
                "algorithmic_status": status,
                "source_time_sec": f"{moment:.3f}",
                "source_timecode": timecode(moment),
                "confidence": row["confidence"],
                "gt_event_id": row["gt_event_id"],
                "distance_band": "far" if status == "FN" else "",
                "source_video": proxy[video_id]["source_path"],
                "review_start_sec": f"{max(0.0, moment - 5):.3f}",
                "review_end_sec": f"{min(float(proxy[video_id]['inference_end_sec']), moment + 5):.3f}",
                "review_reason": reason,
                "nearest_gt_gap_sec": f"{item['gap']:.3f}" if status == "FP" else "",
                "nearby_peak_confidence": f"{item['signal']:.6f}" if status == "FN" else "",
                "human_visibility": "",
                "human_judgment": "",
                "human_comment": "",
            })

    args.output_dir.mkdir(parents=True)
    review_path = args.output_dir / "training_review.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    manifest = {
        "schema_version": 1,
        "purpose": "training-label audit only; frozen test GT and baseline metrics remain unchanged",
        "selection": "per half: 4 high-confidence FP and 4 far-side FN; at least 10s from prior/current review cases",
        "input_sha256": {
            "matches": sha256(args.matches),
            "ground_truth": sha256(args.ground_truth),
            "prior_review": sha256(args.prior_review),
            "proxy_manifest": sha256(args.proxy_manifest),
            "predictions": prediction_hashes,
        },
        "review_csv_sha256": sha256(review_path),
        "counts": {video_id: sum(row["video_id"] == video_id for row in selected) for video_id in sorted(proxy)},
    }
    (args.output_dir / "selection_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
