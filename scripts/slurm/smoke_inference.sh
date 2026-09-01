#!/usr/bin/env bash
#SBATCH --job-name=ballspot-smoke
#SBATCH --partition=ubuntu
#SBATCH --gres=gpu:rtx_a6000:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=artifacts/inference/%x-%j.out
#SBATCH --error=artifacts/inference/%x-%j.err

set -euo pipefail

repo_root="/work7/y_pan/Code_repo/Ball_action_spotting"
run_id="smoke_${SLURM_JOB_ID}"

cd "$repo_root"
export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1
export PYTHONPATH="$repo_root/third_party/ball-action-spotting${PYTHONPATH:+:$PYTHONPATH}"

/work7/y_pan/anaconda3/bin/conda run -n ballspot-infer python scripts/run_custom_inference.py \
  --video "$repo_root/data/raw/vs_飛鳥FC_20260704_trimmed_0930_25fps_infer.mp4" \
  --config configs/poc_video.yaml \
  --weights-root "$repo_root/ball_action/experiments" \
  --start-sec 0.0 \
  --end-sec 90.0 \
  --output-dir "$repo_root/artifacts/inference/$run_id"
