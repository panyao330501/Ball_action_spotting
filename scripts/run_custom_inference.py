"""Run lRomul 2023 Ball Action Spotting checkpoints on a 25 FPS video.

This program exports only frame-level raw scores. Peak detection and event
generation belong to a later project step. Run it from a Slurm GPU job with
the upstream repository available through PYTHONPATH.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml


CLASS_NAMES = ("PASS", "DRIVE")
FINAL_EXPERIMENT = "ball_finetune_long_004"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_revision(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def parse_folds(raw_value: str) -> list[int]:
    folds = [int(value) for value in raw_value.split(",")]
    if not folds or len(set(folds)) != len(folds) or any(fold < 0 or fold > 6 for fold in folds):
        raise ValueError("--folds 必须是不重复的 0～6 整数，例如 0,1,2,3,4,5,6")
    return folds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path, help="25 FPS CFR inference proxy")
    parser.add_argument("--config", required=True, type=Path, help="Path to configs/poc_video.yaml")
    parser.add_argument("--weights-root", required=True, type=Path, help="Path to ball_action/experiments")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--start-sec", type=float, default=0.0)
    parser.add_argument("--end-sec", type=float, required=True, help="Exclusive end time in seconds")
    parser.add_argument("--folds", default="0,1,2,3,4,5,6")
    parser.add_argument("--device", default="cuda:0")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"配置不是对象：{path}")
    return data


def video_info(path: Path) -> dict[str, int | float]:
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    if not capture.isOpened():
        raise RuntimeError(f"无法打开视频：{path}")
    try:
        return {
            "frame_count": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
            "fps": float(capture.get(cv2.CAP_PROP_FPS)),
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
    finally:
        capture.release()


def assert_input_contract(
    config: dict[str, Any], video: Path, actual_info: dict[str, int | float]
) -> None:
    expected = config["inference_input"]
    if video.name != expected["basename"]:
        raise ValueError(f"视频文件名不匹配：{video.name} != {expected['basename']}")
    for field in ("width", "height"):
        if actual_info[field] != expected[field]:
            raise ValueError(f"视频 {field} 不匹配：{actual_info[field]} != {expected[field]}")
    if not np.isclose(actual_info["fps"], expected["fps"], atol=1e-6):
        raise ValueError(f"视频 FPS 不匹配：{actual_info['fps']} != {expected['fps']}")
    actual_sha256 = sha256_file(video)
    if actual_sha256 != expected["sha256"]:
        raise ValueError("视频 SHA-256 不匹配，拒绝推理")


def checkpoint_path(weights_root: Path, fold: int) -> Path:
    fold_dir = weights_root / FINAL_EXPERIMENT / f"fold_{fold}"
    candidates = sorted(fold_dir.glob("*.pth"))
    if len(candidates) != 1:
        raise FileNotFoundError(f"fold {fold} 应恰有一个 .pth 文件，实际为 {len(candidates)}：{fold_dir}")
    return candidates[0]


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def main() -> None:
    args = parse_args()
    if args.start_sec < 0 or args.end_sec <= args.start_sec:
        raise ValueError("必须满足 0 <= --start-sec < --end-sec")
    if not args.video.is_file() or not args.config.is_file():
        raise FileNotFoundError("视频或配置文件不存在")

    # 上游模块在运行期导入，使本文件能在本地执行静态检查。
    import argus
    import torch
    import src.argus_models  # noqa: F401  注册 Argus 自定义模块。
    from src.predictors import MultiDimStackerPredictor

    if not torch.cuda.is_available():
        raise RuntimeError("未检测到 CUDA；此入口必须在 Slurm GPU 作业中运行")
    if not args.device.startswith("cuda"):
        raise ValueError("本 PoC 只允许 CUDA 推理设备")

    config = load_config(args.config)
    actual_info = video_info(args.video)
    assert_input_contract(config, args.video, actual_info)
    fps = float(actual_info["fps"])
    frame_count = int(actual_info["frame_count"])
    folds = parse_folds(args.folds)
    requested_start = round(args.start_sec * fps)
    requested_end = min(frame_count, round(args.end_sec * fps))
    if requested_end <= requested_start:
        raise ValueError("请求区间没有可用帧")

    checkpoint_paths = [checkpoint_path(args.weights_root, fold) for fold in folds]
    predictors = [
        MultiDimStackerPredictor(path, device=args.device, tta=True)
        for path in checkpoint_paths
    ]
    reference = predictors[0]
    if reference.frame_stack_size != int(config["model_preprocess"]["frame_stack_size"]):
        raise ValueError("配置与权重的 frame_stack_size 不一致")
    if reference.frame_stack_step != 2:
        raise ValueError("权重的 frame_stack_step 必须为 2")
    if any(
        predictor.frame_stack_size != reference.frame_stack_size
        or predictor.frame_stack_step != reference.frame_stack_step
        for predictor in predictors[1:]
    ):
        raise ValueError("所选 fold 的时间模型参数不一致")

    indexer = reference.indexes_generator
    min_prediction = indexer.clip_index(requested_start, frame_count, save_zone=1)
    max_prediction = indexer.clip_index(requested_end - 1, frame_count, save_zone=1)
    if max_prediction < min_prediction:
        raise ValueError("请求区间不足以形成完整的模型时间窗口")
    decode_start = min_prediction - reference._predict_offset
    decode_end = max_prediction + reference._predict_offset
    if decode_start < 0 or decode_end >= frame_count:
        raise RuntimeError("内部上下文边界计算错误")

    capture = cv2.VideoCapture(str(args.video), cv2.CAP_FFMPEG)
    if not capture.isOpened():
        raise RuntimeError(f"无法打开视频：{args.video}")
    capture.set(cv2.CAP_PROP_POS_FRAMES, decode_start)
    frame_indexes: list[int] = []
    fold_scores: list[np.ndarray] = []
    started_at = time.monotonic()

    try:
        for frame_index in range(decode_start, decode_end + 1):
            success, bgr_frame = capture.read()
            if not success or bgr_frame is None:
                raise RuntimeError(f"无法连续解码推理帧 {frame_index}")
            grayscale_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
            frame = torch.from_numpy(grayscale_frame).to(device=args.device)
            predictions = [predictor.predict(frame, frame_index) for predictor in predictors]
            prediction_indexes = {prediction_index for _, prediction_index in predictions}
            if len(prediction_indexes) != 1:
                raise RuntimeError("各 fold 的预测帧索引不一致")
            prediction_index = prediction_indexes.pop()
            if not min_prediction <= prediction_index <= max_prediction:
                continue
            if any(prediction is None for prediction, _ in predictions):
                raise RuntimeError(f"帧 {prediction_index} 未生成完整预测")
            scores = np.stack(
                [prediction.detach().float().cpu().numpy() for prediction, _ in predictions], axis=0
            )
            if scores.shape != (len(folds), len(CLASS_NAMES)):
                raise RuntimeError(f"意外分数形状：{scores.shape}")
            frame_indexes.append(prediction_index)
            fold_scores.append(scores)
    finally:
        capture.release()
        for predictor in predictors:
            predictor.reset_buffers()

    if not frame_indexes:
        raise RuntimeError("没有导出任何有效预测")
    frame_indexes_array = np.asarray(frame_indexes, dtype=np.int64)
    fold_scores_array = np.stack(fold_scores, axis=0).astype(np.float32)
    ensemble_scores = fold_scores_array.mean(axis=1)
    if not np.isfinite(fold_scores_array).all():
        raise RuntimeError("模型分数包含 NaN 或 Inf")

    args.output_dir.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(
        args.output_dir / "scores.npz",
        frame_indexes=frame_indexes_array,
        time_sec=frame_indexes_array.astype(np.float64) / fps,
        fold_ids=np.asarray(folds, dtype=np.int64),
        fold_scores=fold_scores_array,
        ensemble_scores=ensemble_scores,
        class_names=np.asarray(CLASS_NAMES),
    )
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "repository_commit": git_revision(Path.cwd()),
        "host": platform.node(),
        "python": sys.version,
        "opencv": cv2.__version__,
        "torch": torch.__version__,
        "cuda_device": torch.cuda.get_device_name(torch.device(args.device)),
        "input": {
            "path": str(args.video.resolve()),
            "sha256": sha256_file(args.video),
            **actual_info,
            "requested_interval_sec": [args.start_sec, args.end_sec],
            "prediction_interval_sec": [
                float(frame_indexes_array[0] / fps),
                float(frame_indexes_array[-1] / fps),
            ],
        },
        "model": {
            "experiment": FINAL_EXPERIMENT,
            "fold_ids": folds,
            "checkpoint_paths": [str(path.resolve()) for path in checkpoint_paths],
            "checkpoint_sha256": [sha256_file(path) for path in checkpoint_paths],
            "tta_horizontal_flip": True,
            "params": json_safe(reference.model.params),
        },
        "output": {
            "scores_file": "scores.npz",
            "class_names": list(CLASS_NAMES),
            "fold_scores_shape": list(fold_scores_array.shape),
            "ensemble_scores_shape": list(ensemble_scores.shape),
            "num_prediction_frames": int(len(frame_indexes_array)),
            "elapsed_sec": time.monotonic() - started_at,
        },
    }
    with (args.output_dir / "manifest.json").open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
    print(json.dumps(manifest["output"], ensure_ascii=False))


if __name__ == "__main__":
    main()
