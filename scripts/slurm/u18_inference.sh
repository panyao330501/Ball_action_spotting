#!/usr/bin/env bash
#SBATCH --job-name=ballspot-u18
#SBATCH --partition=ubuntu
#SBATCH --gres=gpu:rtx_a6000:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=artifacts/inference/%x-%j.out
#SBATCH --error=artifacts/inference/%x-%j.err

set -euo pipefail

if [[ "$#" -ne 4 ]]; then
  echo "usage: sbatch scripts/slurm/u18_inference.sh <video> <config> <end-sec> <output-dir>" >&2
  exit 2
fi

repo_root="/work7/y_pan/Code_repo/Ball_action_spotting"
video="$1"
config="$2"
end_sec="$3"
output_dir="$4"

cd "$repo_root"
mkdir -p "$repo_root/artifacts/inference"
export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1
export PYTHONPATH="$repo_root/third_party/ball-action-spotting${PYTHONPATH:+:$PYTHONPATH}"

/work7/y_pan/anaconda3/envs/ballspot-infer/bin/python scripts/run_custom_inference.py \
  --video "$video" \
  --config "$config" \
  --weights-root "$repo_root/ball_action/experiments" \
  --start-sec 0.0 \
  --end-sec "$end_sec" \
  --output-dir "$output_dir"
