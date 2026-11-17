"""Verify sampled Pass windows never overlap known training-match events."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-root", required=True, type=Path)
    parser.add_argument("--models-root", required=True, type=Path)
    args = parser.parse_args()
    labels_manifest_path = args.labels_root / "manifest.json"
    labels_manifest = read(labels_manifest_path)
    for fold in labels_manifest["folds"]:
        fold_id = fold["fold_id"]
        label_dir = args.labels_root / fold_id
        model_dir = args.models_root / fold_id
        model = read(model_dir / "manifest.json")
        examples_path = model_dir / "training_examples.json"
        examples = read(examples_path)
        assert model["fold_id"] == fold_id
        assert model["labels_manifest_sha256"] == sha256(labels_manifest_path)
        assert model["training_examples_sha256"] == sha256(examples_path)
        assert model["max_per_half"] is None
        train_ids, test_ids = set(fold["train_video_ids"]), set(fold["test_video_ids"])
        assert train_ids.isdisjoint(test_ids)
        assert {row["video_id"] for row in examples} == train_ids
        labels = read(label_dir / "train_pass_events.json")
        excluded = read(label_dir / "excluded_bepro_pass.json")
        pending = read(label_dir / "pending_pass_additions.json")
        receivers = read(label_dir / "drive_proxy_events.json")
        positives = [row for row in examples if row["target_pass"] == 1]
        negatives = [row for row in examples if row["target_pass"] == 0]
        label_by_id = {row["event_id"]: row for row in labels}
        assert len(positives) == len(labels) == model["positives"]
        assert len(negatives) == len(positives) == model["negatives"]
        assert {row["positive_event_id"] for row in positives} == set(label_by_id)
        for item in positives:
            label = label_by_id[item["positive_event_id"]]
            assert item["video_id"] == label["video_id"]
            assert item["frame_index_25fps"] == label["training_frame_index_25fps"]
        forbidden = {}
        for video_id in train_ids:
            forbidden[video_id] = [row["training_time_sec"] for row in labels if row["video_id"] == video_id]
            forbidden[video_id] += [row["bepro_time_sec"] for row in excluded if row["video_id"] == video_id]
            forbidden[video_id] += [row["prediction_time_sec"] for row in pending if row["video_id"] == video_id]
            forbidden[video_id] += [row["source_time_sec"] for row in receivers if row["video_id"] == video_id]
        minimum = min(abs(item["frame_index_25fps"] / 25.0 - time)
                      for item in negatives for time in forbidden[item["video_id"]])
        assert minimum > 3.0, (fold_id, minimum)
        print(f"{fold_id}: {len(positives)} positive, {len(negatives)} negative, "
              f"nearest known event {minimum:.3f}s; isolation OK")


if __name__ == "__main__":
    main()
