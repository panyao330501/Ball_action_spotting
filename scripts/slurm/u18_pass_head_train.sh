#!/usr/bin/env bash
#SBATCH --job-name=ballspot-pass-head
#SBATCH --partition=ubuntu
#SBATCH --gres=gpu:rtx_a6000:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=artifacts/inference/%x-%j.out
#SBATCH --error=artifacts/inference/%x-%j.err

set -euo pipefail
if [[ "$#" -lt 3 || "$#" -gt 4 ]]; then
  echo "usage: sbatch scripts/slurm/u18_pass_head_train.sh <fold-id> <labels-root> <output-dir> [max-per-half]" >&2
  exit 2
fi
repo_root="/work7/y_pan/Code_repo/Ball_action_spotting"
cd "$repo_root"
mkdir -p artifacts/inference
export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1
export PYTHONPATH="$repo_root/third_party/ball-action-spotting${PYTHONPATH:+:$PYTHONPATH}"
args=(--fold-id "$1" --labels-root "$2" --output-dir "$3"
  --proxy-root "$repo_root/data/u18_inference_20260930_masked_v1"
  --proxy-manifest "$repo_root/data/u18_inference_20260930_masked_v1/proxy_manifest.json"
  --initial-checkpoint "$repo_root/ball_action/experiments/ball_finetune_long_004/fold_0/model-006-0.864002.pth")
if [[ "$#" -eq 4 ]]; then args+=(--max-per-half "$4"); fi
/work7/y_pan/anaconda3/envs/ballspot-infer/bin/python scripts/train_u18_pass_head.py "${args[@]}"
