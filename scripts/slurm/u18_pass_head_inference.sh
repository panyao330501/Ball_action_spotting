#!/usr/bin/env bash
#SBATCH --job-name=ballspot-pass-eval
#SBATCH --partition=ubuntu
#SBATCH --gres=gpu:rtx_a6000:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=artifacts/inference/%x-%j.out
#SBATCH --error=artifacts/inference/%x-%j.err

set -euo pipefail
if [[ "$#" -ne 5 ]]; then
  echo "usage: sbatch scripts/slurm/u18_pass_head_inference.sh <video> <config> <end-sec> <experiment> <output-dir>" >&2
  exit 2
fi
repo_root="/work7/y_pan/Code_repo/Ball_action_spotting"
cd "$repo_root"
mkdir -p artifacts/inference
export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1
export PYTHONPATH="$repo_root/third_party/ball-action-spotting${PYTHONPATH:+:$PYTHONPATH}"
/work7/y_pan/anaconda3/envs/ballspot-infer/bin/python scripts/run_custom_inference.py \
  --video "$1" --config "$2" --end-sec "$3" --experiment "$4" --output-dir "$5" \
  --weights-root "$repo_root/ball_action/experiments" --folds 0 --start-sec 0.0
