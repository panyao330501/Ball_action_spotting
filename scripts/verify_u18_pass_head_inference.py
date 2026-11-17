"""Verify held-out single-fold inference scores, video identity, and model hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


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
    parser.add_argument("--inference-root", required=True, type=Path)
    parser.add_argument("--models-root", required=True, type=Path)
    parser.add_argument("--proxy-manifest", required=True, type=Path)
    parser.add_argument("--experiment-suffix", default="v2")
    args = parser.parse_args()
    proxy = read(args.proxy_manifest)
    by_id = {row["video_id"]: row for row in proxy["videos"]}
    for fold_id in ("A_train_B_test", "B_train_A_test"):
        model = read(args.models_root / fold_id / "manifest.json")
        for video_id in model["test_video_ids"]:
            folder = args.inference_root / fold_id / video_id / "inference"
            manifest = read(folder / "manifest.json")
            scores_path = folder / "scores.npz"
            assert manifest["status"] == "completed"
            assert manifest["input"]["sha256"] == by_id[video_id]["proxy_sha256"]
            assert manifest["input"]["frame_count"] == by_id[video_id]["proxy_info"]["frame_count"]
            assert manifest["input"]["fps"] == 25.0
            assert manifest["model"]["experiment"] == f"u18_pass_head_{fold_id}_{args.experiment_suffix}"
            assert manifest["model"]["checkpoint_sha256"] == [model["output_checkpoint_sha256"]]
            assert manifest["model"]["fold_ids"] == [0]
            assert manifest["model"]["tta_horizontal_flip"] is True
            with np.load(scores_path) as data:
                frames = data["frame_indexes"]
                times = data["time_sec"]
                folds = data["fold_scores"]
                ensemble = data["ensemble_scores"]
                names = data["class_names"].tolist()
                assert frames.ndim == 1 and len(frames) > 1
                assert np.all(np.diff(frames) == 1)
                assert np.allclose(times, frames / 25.0, rtol=0, atol=1e-10)
                assert folds.shape == (len(frames), 1, 2)
                assert ensemble.shape == (len(frames), 2)
                assert np.array_equal(ensemble, folds[:, 0, :])
                assert np.isfinite(folds).all() and ((folds >= 0) & (folds <= 1)).all()
                assert names == ["PASS", "DRIVE"]
                assert manifest["output"]["num_prediction_frames"] == len(frames)
                assert manifest["output"]["fold_scores_shape"] == list(folds.shape)
            print(f"{fold_id}/{video_id}: {len(frames)} frames, "
                  f"scores SHA-256 {sha256(scores_path)}; verified")


if __name__ == "__main__":
    main()
