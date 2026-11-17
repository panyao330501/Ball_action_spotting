"""Independently verify match isolation and provenance of Pass training labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-dir", required=True, type=Path)
    parser.add_argument("--frozen-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest = read(args.training_dir / "manifest.json")
    frozen_manifest = read(args.frozen_dir / "manifest.json")
    assert digest(args.frozen_dir / "manifest.json") == manifest["frozen_manifest_sha256"]
    assert {fold["fold_id"] for fold in manifest["folds"]} == {
        fold["fold_id"] for fold in frozen_manifest["folds"]
    }
    for fold in manifest["folds"]:
        folder = args.training_dir / fold["fold_id"]
        frozen_folder = args.frozen_dir / fold["fold_id"]
        train = read(frozen_folder / "train_gt_pass.json")
        test = read(frozen_folder / "test_gt_pass.json")
        labels = read(folder / "train_pass_events.json")
        excluded = read(folder / "excluded_bepro_pass.json")
        pending = read(folder / "pending_pass_additions.json")
        ignore = read(folder / "ignore_intervals.json")
        corrections = read(folder / "time_corrections.json")
        drive_proxies = read(folder / "drive_proxy_events.json") if "drive_proxy_events.json" in fold["output_sha256"] else []
        for filename, expected in fold["output_sha256"].items():
            assert digest(folder / filename) == expected, filename
        assert digest(frozen_folder / "train_gt_pass.json") == fold["frozen_train_gt_sha256"]
        assert digest(frozen_folder / "test_gt_pass.json") == fold["frozen_test_gt_sha256"]
        train_ids = set(fold["train_video_ids"])
        test_ids = set(fold["test_video_ids"])
        assert train_ids.isdisjoint(test_ids)
        assert {event["video_id"] for event in train} == train_ids
        assert {event["video_id"] for event in test} == test_ids
        assert {event["video_id"] for event in labels + excluded + pending + ignore + drive_proxies} <= train_ids
        assert all(event["mapping_status"] == "provisional_receiver_proxy" for event in drive_proxies)
        original_ids = {event["event_id"] for event in train}
        output_ids = [event["event_id"] for event in labels + excluded]
        assert len(output_ids) == len(set(output_ids)) and set(output_ids) == original_ids
        assert {event["event_id"] for event in corrections} <= {event["event_id"] for event in labels}
        for key, items in (
            ("original_bepro_pass", train), ("training_pass", labels),
            ("excluded_bepro_pass", excluded), ("pending_pass_additions", pending),
            ("time_corrections", corrections),
            ("drive_proxy_events", drive_proxies),
        ):
            assert fold[key] == len(items), (fold["fold_id"], key)
        print(f"{fold['fold_id']}: {len(labels)} labels, {len(excluded)} excluded, "
              f"{len(corrections)} corrections, {len(pending)} pending; isolation OK")


if __name__ == "__main__":
    main()
