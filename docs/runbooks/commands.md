# 命令手册

状态标记：

- **已验证**：已在本项目环境中成功使用。
- **模板**：仍含占位符，或尚未进行端到端执行。

禁止把密钥或令牌写入本文档。执行可能覆盖文件或改变状态的命令前必须再次检查。

## 1. 本地 Conda

### 定位 Conda——已验证

```powershell
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' --version
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' info --base
```

### 创建可视化环境——已验证

在提交 `environment-viz.yml` 后执行：

```powershell
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' env create --file environment-viz.yml
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' run -n ballspot-viz python --version
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' run -n ballspot-viz ffmpeg -version
```

非交互命令优先使用 `conda run`。需要交互激活时：

```powershell
& 'C:\ProgramData\miniconda3\shell\condabin\conda-hook.ps1'
conda activate ballspot-viz
```

## 2. SSH 和远端检查

### 连接推理主机——已验证

```powershell
ssh chiron
```

### 验证身份和 GPU——已验证

```powershell
ssh chiron "hostname; whoami; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"
```

### 远端项目目录——已验证

```bash
cd /work7/y_pan/Code_repo/Ball_action_spotting/
```

## 3. GitHub 仓库准备

已确认 GitHub 远端为 `https://github.com/panyao330501/Ball_action_spotting.git`。

### 初始化本地仓库——已验证

```powershell
git init -b main
git remote add origin https://github.com/panyao330501/Ball_action_spotting.git
git status --short --ignored
```

首次提交前确认 MP4 显示为已忽略，而不是已暂存。

### 克隆到现有空远端目录——已验证

```powershell
ssh chiron "git clone https://github.com/panyao330501/Ball_action_spotting.git /work7/y_pan/Code_repo/Ball_action_spotting"
```

如果现有目录导致克隆失败，先检查目录内容。未经确认不得删除或覆盖。

### 日常同步——模板

本地修改端：

```powershell
git status --short
git add <明确路径>
git commit -m "<提交信息>"
git push origin main
```

远端推理端：

```powershell
ssh chiron "git -C /work7/y_pan/Code_repo/Ball_action_spotting pull --ff-only origin main"
```

比较版本：

```powershell
git rev-parse HEAD
ssh chiron "git -C /work7/y_pan/Code_repo/Ball_action_spotting rev-parse HEAD"
```

## 4. 大文件传输

视频、权重、原始分数和渲染视频不通过 GitHub 传输。

### 计算本地视频校验和——已验证

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\Code\Ball_action_spotting\vs_飛鳥FC_20260704_trimmed_0930.mp4'
```

### 传输源视频——已验证

仓库准备完成后创建远端运行目录：

```powershell
ssh chiron "mkdir -p /work7/y_pan/Code_repo/Ball_action_spotting/data/raw"
scp 'C:\Code\Ball_action_spotting\vs_飛鳥FC_20260704_trimmed_0930.mp4' 'chiron:/work7/y_pan/Code_repo/Ball_action_spotting/data/raw/'
```

验证远端校验和：

```powershell
ssh chiron "sha256sum '/work7/y_pan/Code_repo/Ball_action_spotting/data/raw/vs_飛鳥FC_20260704_trimmed_0930.mp4'"
```

### 取回推理产物——模板

```powershell
scp -r 'chiron:/work7/y_pan/Code_repo/Ball_action_spotting/artifacts/inference/<RUN_ID>' 'C:\Code\Ball_action_spotting\artifacts\inference\'
```

## 5. 远端 Conda 和 GPU 检查

远端 Conda 位于 `/work7/y_pan/anaconda3/bin/conda`。由于该安装的部分插件存在 OpenSSL 兼容警告，命令显式设置 `CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1`，环境求解使用 libmamba。

### 创建推理环境——已验证

```powershell
ssh chiron 'export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1; /work7/y_pan/anaconda3/bin/conda env create --solver libmamba --file /work7/y_pan/Code_repo/Ball_action_spotting/environment-infer.yml'
```

### 环境冒烟检查——已验证

```powershell
ssh chiron 'export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1; export CUDA_VISIBLE_DEVICES=0; /work7/y_pan/anaconda3/bin/conda run -n ballspot-infer python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"'
```

### 导出环境快照——模板

```powershell
ssh chiron 'export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1; /work7/y_pan/anaconda3/bin/conda env export -n ballspot-infer --no-builds'
```

## 6. 视频检查和 25 FPS 推理代理

### 本地检查——已验证

```powershell
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' run -n ballspot-viz ffprobe -v error -show_format -show_streams -of json 'C:\Code\Ball_action_spotting\vs_飛鳥FC_20260704_trimmed_0930.mp4'
```

### 远端检查——模板

```powershell
ssh chiron "ffprobe -v error -show_format -show_streams -of json '/work7/y_pan/Code_repo/Ball_action_spotting/data/raw/vs_飛鳥FC_20260704_trimmed_0930.mp4'"
```

### 生成全时长 25 FPS 推理代理——已验证

该命令不裁剪规范源；输出仅保留视频流，因为最终可视化仍使用原始带音频 MP4。先确认目标文件不存在，避免意外覆盖。

```powershell
ssh chiron 'source="/work7/y_pan/Code_repo/Ball_action_spotting/data/raw/vs_飛鳥FC_20260704_trimmed_0930.mp4"; proxy="/work7/y_pan/Code_repo/Ball_action_spotting/data/raw/vs_飛鳥FC_20260704_trimmed_0930_25fps_infer.mp4"; test ! -e "$proxy" && /work7/y_pan/anaconda3/bin/conda run -n ballspot-infer ffmpeg -i "$source" -map 0:v:0 -an -vf fps=25 -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p "$proxy"'
```

已验证代理的 FPS、时长和帧数：25 FPS、1280×720、14,163 帧、566.520 秒。模型内部再补边至 1280×736。

## 7. 推理、后处理和可视化

### 验证手动下载的最终模型权重——已验证

权重必须在 `chiron` 项目根目录的 `ball_action/` 下，且不能通过 Git 提交。完整权重清单和 SHA-256 见 `docs/model_sources/lromul_ball_action_2023.md`。

```powershell
ssh chiron 'repo=/work7/y_pan/Code_repo/Ball_action_spotting; find "$repo/ball_action/experiments/ball_finetune_long_004" -type f -name "*.pth" -print0 | sort -z | xargs -0 sha256sum'
```

### 加载 fold 0 检查模型参数——已验证

该命令只加载权重，不执行视频推理。预期为 2 类、33 帧、步长 2、`pad_normalize`。

```powershell
ssh chiron 'export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1; export CUDA_VISIBLE_DEVICES=0; repo=/work7/y_pan/Code_repo/Ball_action_spotting; export PYTHONPATH="$repo/third_party/ball-action-spotting"; /work7/y_pan/anaconda3/bin/conda run -n ballspot-infer python -c "import argus, src.argus_models; m=argus.load_model(\"/work7/y_pan/Code_repo/Ball_action_spotting/ball_action/experiments/ball_finetune_long_004/fold_0/model-006-0.864002.pth\", device=\"cuda:0\", optimizer=None, loss=None); print(m.params[\"nn_module\"]); print(m.params[\"frame_stack_size\"]); print(m.params[\"frame_stack_step\"]); print(m.params[\"frames_processor\"])"'
```

### 提交 90 秒 Slurm 冒烟推理——已验证

执行前先同步最新代码并创建 Slurm 输出目录。该命令提交作业，不在 SSH 登录 Shell 直接运行 GPU 推理。

```powershell
ssh chiron 'mkdir -p /work7/y_pan/Code_repo/Ball_action_spotting/artifacts/inference && cd /work7/y_pan/Code_repo/Ball_action_spotting && sbatch scripts/slurm/smoke_inference.sh'
```

查询作业：

```powershell
ssh chiron 'squeue -u "$USER"'
```

已验证作业为 `6835524`、`6835525`；两次原始分数完全一致。作业完成后，检查 `artifacts/inference/smoke_<job_id>/manifest.json`、`scores.npz` 和对应的 Slurm `.out` / `.err` 日志。

以下接口是占位模板，实际模块在对应实施步骤中确定。

### 远端推理——模板

```powershell
ssh chiron "cd /work7/y_pan/Code_repo/Ball_action_spotting && conda run -n ballspot-infer python -m ballspot.infer --config configs/poc.yaml"
```

### 本地可视化烟雾渲染——已验证

```powershell
& 'C:\Users\logan\.conda\envs\ballspot-viz\python.exe' scripts/render_visualization.py `
  --run-id smoke_20260901_step05_r5 `
  --render-end-sec 26 `
  --preset ultrafast `
  --crf 23 `
  --ffmpeg 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffmpeg.exe' `
  --ffprobe 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffprobe.exe'
```

入口验证源视频和事件契约、拒绝覆盖既有运行目录，并同时生成完整叠加视频、逐事件片段、事件集锦、渲染清单与日志。

### 本地全程可视化——已验证

当前审查版本的正式运行 ID 为 `20260902_151709_978ded7_poc-video-global-timeline-2px`；该版本在事件置信度后显示固定事件时间码，并在源画面下方显示完整 566.5 秒的 2 像素红蓝事件时间轴和白色动态播放指针。执行前已确认同名产物目录不存在。

```powershell
& 'C:\Users\logan\.conda\envs\ballspot-viz\python.exe' scripts/render_visualization.py `
  --run-id 20260902_151709_978ded7_poc-video-global-timeline-2px `
  --ffmpeg 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffmpeg.exe' `
  --ffprobe 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffprobe.exe'
```

### 本地测试——模板

```powershell
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' run -n ballspot-viz pytest -q
```

该命令同时生成完整叠加视频、58 个精确片段、事件集锦、清单和日志。重复运行必须使用新运行 ID，不能覆盖本次已验证产物。

### 全局时间轴烟雾渲染——已验证

该版本在 1280×720 源画面下方增加 120 像素全局时间轴；短片只显示前 26 秒的当前事件，但时间轴仍包含完整 566.5 秒中的全部 58 个候选。

```powershell
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' run -n ballspot-viz python scripts/render_visualization.py `
  --run-id smoke_20260902_global_timeline_v1 `
  --render-end-sec 26 `
  --preset ultrafast `
  --crf 23
```

### 本地生成 BAS-only 漏检候选——已验证

以下命令读取既有全程分数、正式事件和用户记录的漏检种子，不重新运行 GPU 推理；`BAS漏检.xlsx` 只读且被 Git 忽略。当前未传入 tracking 文件，运行清单记录 `tracking_status=not_provided`。

```powershell
& 'C:\Users\logan\.conda\envs\ballspot-viz\python.exe' scripts/generate_miss_candidates.py `
  --scores 'artifacts/inference/full_6835526/scores.npz' `
  --inference-manifest 'artifacts/inference/full_6835526/manifest.json' `
  --events 'artifacts/inference/full_6835526/events.json' `
  --seed-misses 'BAS漏检.xlsx' `
  --run-id '20260929_153408_ee66a96_bas-miss-candidates-v2'
```

标准化 tracking 候选可在未来通过 `--tracking-candidates <CSV-or-JSON>` 加入；字段契约见 `docs/data/label_and_artifact_contract.md`。

### 本地渲染漏检候选集锦——已验证

```powershell
& 'C:\Users\logan\.conda\envs\ballspot-viz\python.exe' scripts/render_miss_candidate_highlights.py `
  --candidate-dir 'artifacts/candidate_mining/20260929_153408_ee66a96_bas-miss-candidates-v2' `
  --run-id '20260930_141315_ee66a96_bas-miss-review-timecode-v2' `
  --preset fast `
  --crf 18 `
  --ffmpeg 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffmpeg.exe' `
  --ffprobe 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffprobe.exe'
```

该命令按高、中优先级生成 36 个合并窗口和一份 436.3 秒集锦；右上角动态 `SOURCE HH:MM:SS.mmm` 由窗口源视频起点加当前片段 PTS 计算，可与候选行固定 `event` 时间直接对照。不会绘制空间框或声称 tracking 已接入。

## 8. U18 Veo/Bepro GT 评估

### 转换正式 GT——已验证

```powershell
& 'C:\Users\logan\.conda\envs\ballspot-viz\python.exe' scripts/prepare_u18_ground_truth.py `
  --config configs/u18_gt.yaml `
  --source-root U18 `
  --output-dir artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2
```

该命令验证四段视频 SHA-256，只读取 8 份 `*_イベント.xml`，并拒绝覆盖已有输出目录。

### 四段 12 秒 masked 代理烟雾——已验证

```powershell
& 'C:\Users\logan\.conda\envs\ballspot-viz\python.exe' scripts/prepare_u18_inference_proxies.py `
  --config configs/u18_gt.yaml `
  --source-root U18 `
  --output-root data/u18_inference_smoke_20260930_v2 `
  --ffmpeg 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffmpeg.exe' `
  --ffprobe 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffprobe.exe' `
  --end-sec 12
```

### 生成四个完整 masked 代理——已验证

```powershell
& 'C:\Users\logan\.conda\envs\ballspot-viz\python.exe' scripts/prepare_u18_inference_proxies.py `
  --config configs/u18_gt.yaml `
  --source-root U18 `
  --output-root data/u18_inference_20260930_masked_v1 `
  --ffmpeg 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffmpeg.exe' `
  --ffprobe 'C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffprobe.exe'
```

正式运行 `data/u18_inference_20260930_masked_v1/` 生成四段 1280×720、25 FPS、无音频代理；四段均通过 FFprobe、帧数清单和完整解码检查。传输到 `chiron` 后须以 `sha256sum` 对照本地 manifest，不能仅以文件大小判断传输完成。

### 提交单个 U18 半场推理——模板

以下四个参数依次为远端代理、远端逐视频配置、结束秒和新输出目录。GPU 推理只能通过 Slurm 提交。

```powershell
ssh chiron 'cd /work7/y_pan/Code_repo/Ball_action_spotting && sbatch scripts/slurm/u18_inference.sh <REMOTE_ABSOLUTE_VIDEO> <REMOTE_ABSOLUTE_CONFIG> <END_SEC> <REMOTE_ABSOLUTE_OUTPUT_DIR>'
```

在 Windows PowerShell 中不要把远端路径写成双引号字符串里的 `$PWD/...`；PowerShell 会先把 `$PWD` 展开成本地 Windows 路径。应直接填写 `/work7/y_pan/Code_repo/Ball_action_spotting/...` 绝对路径。

### U18 正式评估——模板

每个 `<PREDICTIONS_ROOT>/<video_id>/events.json` 应由对应半场原始分数以 `min_height=0` 生成，评估器再独立使用 `0.2` 操作阈值。

```powershell
& 'C:\Users\logan\.conda\envs\ballspot-viz\python.exe' scripts/evaluate_u18_predictions.py `
  --ground-truth artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/gt_events_evaluable.json `
  --predictions-root artifacts/u18_predictions/<RUN_ID> `
  --output-dir artifacts/u18_evaluation/<RUN_ID> `
  --tolerances 0.5,1.0,2.0 `
  --operating-threshold 0.2
```

### U18 四半场 masked 基线后处理与评估——已验证（2026-11-09）

三个后补半场的 `manifest.json` 与 `scores.npz` 已从 `chiron` 的 `artifacts/inference/u18_<video_id>_masked_v1/` 取回本地同名目录，并逐文件比对 SHA-256；原 FC 东京/青森山田 H1 目录已存在。确认目标输出目录尚不存在后，在本地 PowerShell 顺序运行：

```powershell
$items = @(
  @('fc_tokyo_aomori_h2', 'u18_fc_tokyo_aomori_h2_masked_v1'),
  @('urawa_ryutsu_h1', 'u18_urawa_ryutsu_h1_masked_v1'),
  @('urawa_ryutsu_h2', 'u18_urawa_ryutsu_h2_masked_v1')
)
foreach ($item in $items) {
  $src = Join-Path 'artifacts/inference' $item[1]
  $dst = Join-Path 'artifacts/u18_predictions/20261001_u18_zero_shot_masked_v1' $item[0]
  conda run -n ballspot-viz python scripts/postprocess_scores.py `
    --scores (Join-Path $src 'scores.npz') `
    --inference-manifest (Join-Path $src 'manifest.json') `
    --output-dir $dst --gauss-sigma 3 --min-height 0 --min-distance-frames 15
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
conda run -n ballspot-viz python scripts/evaluate_u18_predictions.py `
  --ground-truth artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/gt_events_evaluable.json `
  --predictions-root artifacts/u18_predictions/20261001_u18_zero_shot_masked_v1 `
  --output-dir artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1 `
  --tolerances 0.5,1.0,2.0 --operating-threshold 0.2
conda run -n ballspot-viz python scripts/curate_u18_eval_review.py `
  --matches artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/matches_at_1s.csv `
  --ground-truth artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/gt_events_evaluable.json `
  --proxy-manifest data/u18_inference_20260930_masked_v1/proxy_manifest.json `
  --output artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/pass_review_cases.csv
```

上述脚本均拒绝覆盖现有输出；重跑必须使用新的输出目录，不能删除或覆盖已验证的基线。`pass_review_cases.csv` 的 FP/FN 仍需人工核查。

### U18 Pass 错例与 Drive 语义本地审查网页——已验证（2026-11-11）

在本机双击 `C:\Code\Ball_action_spotting\review_u18_pass.cmd`，或在项目根目录运行：

```powershell
cmd /c review_u18_pass.cmd
```

该脚本在 `127.0.0.1:8765` 启动本地服务并打开 Pass 页面；顶部「Drive 语义」切到 50 条接球样本。页面选择自动保存在当前浏览器；点击「保存到项目」在 `artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_exports/` 创建新的完整 CSV（Pass 28 行或 Drive 50 行）。「下载 CSV」是备用出口；下次可在各自页面「导入之前导出的审查 CSV」续审。审查结束后在命令窗口按 `Ctrl+C` 关闭服务。

生成器 `scripts/render_u18_eval_review.py` 已用 `--mode pass` 和 `--mode drive` 分别完成 28/50 条片段生成；现有 `review_site/` 与 `drive_review_site/` 均已生成，无需再次运行。网页代码更新而片段未变时，已验证 `--page-only` 可核验全部片段哈希后刷新页面资产；使用前确认 `--review-csv`、`--mode`、`--output-dir` 与原 `manifest.json` 相符，避免覆盖人工修改的页面。

### U18 Pass / reception 候选帧图集——已验证

```powershell
conda run -n ballspot-viz python scripts/curate_u18_candidate_frames.py `
  --output-dir artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1

conda run -n ballspot-viz python scripts/verify_u18_candidate_frames.py `
  artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1
```

生成器拒绝覆盖已有运行目录。首版有 120 条候选，图集位于该目录的 `index.html`；可在本机浏览器勾选、填写确认帧号和备注并导出名单。源时间、比赛时间、原视频零起始帧索引和一起始帧编号均在 `review.csv`。如需重新生成，改用新的输出目录；额外已用事件/时刻清单可通过 `--extra-exclusions <CSV>` 提供，CSV 至少包含 `event_id` 或 `video_id,source_time_sec`。同一 Windows 会话中的多条 `conda run` 建议串行执行，以避免临时激活文件竞争。

### U18 大画面、前后各 5 秒逐帧审查——已验证

```powershell
conda run -n ballspot-viz python scripts/render_u18_frame_review.py `
  --candidate-dir artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1

conda run -n ballspot-viz python scripts/verify_u18_frame_review.py `
  artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1
```

首次命令在既有运行目录的 `clips/` 生成 120 个遮挡片段，并把同一 `index.html` 升级为单列大图和逐帧看片界面；旧页面复制到 `index_small_v1.html`，既有 `review.csv` 保持不变。页面沿用原路径，因此浏览器内已保存的勾选与备注可继续使用。刷新页面后打开任一候选的片段，按左右方向键逐帧、按 Shift+左右方向键跳 1 秒；确认帧号后勾选并导出 CSV。片段编码前遮挡 Bepro 文字；未提供干净 Veo 原片时，请勿将片段当成无损源视频。

若仅修改页面布局或交互，且已有 `clip_manifest.json`，可运行已验证的 `conda run -n ballspot-viz python scripts/render_u18_frame_review.py --candidate-dir artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1 --gallery-only`，无需重编 120 个片段。导出中的 `suggested_frame_image` 是 GT 建议图；人工选定的实际帧由 `source_video` 和 `chosen_frame_index` 确定。

### U18 人工确认帧共享包——已验证

以下路径和参数对应 2026-10-06 已验证的 100 行用户导出；生成器拒绝覆盖已有输出目录。再次制作时应使用新运行目录，不要直接覆盖本次 ZIP。

```powershell
conda run -n ballspot-viz python scripts/package_u18_selected_frames.py `
  --selection 'C:\Users\logan\Downloads\u18_selected_frames (1).csv' `
  --candidate-dir artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1 `
  --output-dir artifacts/u18_selected_frames/20261006_u18_selected_frames_v1

conda run -n ballspot-viz python scripts/verify_u18_selected_frames.py `
  artifacts/u18_selected_frames/20261006_u18_selected_frames_v1 `
  artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1
```

共享 `u18_selected_frames_100.zip`；解压后 `selected_frames.csv` 的 `selected_frame_image` 相对路径与 100 张确认帧一一对应。不要把候选目录 `frames/` 中的 GT 建议图当成最终图片。

### U18 Pass 双向整场留出基线和分数重排——已验证

在仓库根目录依次运行；三个脚本均拒绝覆盖既有输出目录，再次运行应换新目录名。结果位于被 Git 忽略的 `artifacts/`，不可提交到 GitHub。

```powershell
conda run -n ballspot-viz python scripts/freeze_u18_pass_cv.py `
  --output-dir artifacts/u18_pass_cv/20261112_frozen_v1

conda run -n ballspot-viz python scripts/train_u18_pass_reranker.py `
  --frozen-dir artifacts/u18_pass_cv/20261112_frozen_v1 `
  --output-dir artifacts/u18_pass_cv/20261112_reranker_v3

conda run -n ballspot-viz python scripts/verify_u18_pass_cv.py `
  --frozen-dir artifacts/u18_pass_cv/20261112_frozen_v1 `
  --reranker-dir artifacts/u18_pass_cv/20261112_reranker_v3
```

Windows 控制台若因中文异常文本触发 `conda run` 的 cp932 输出错误，可先在当前 PowerShell 会话设置 `$env:PYTHONIOENCODING='utf-8'` 后重试。分数重排只用本地现有原始分数，不是网络权重训练；网络训练仍须在 `chiron` 经 Slurm 运行。

### U18 Pass 训练标签定向审查——已验证的生成与服务参数

以下生成命令对应已核对的 2026-11-16 输入，产物目录已有内容；再次运行须使用全新的 `--output-dir`，不得覆盖用户审查结果。`--page-only` 已验证可在不重编视频的情况下刷新网页，并逐片核对哈希。

```powershell
conda run -n ballspot-viz python scripts/curate_u18_pass_training_review.py `
  --matches artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/matches_at_1s.csv `
  --ground-truth artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/gt_events_evaluable.json `
  --prior-review artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_exports/pass_review_20261112T054717Z_028_corrected.csv `
  --proxy-manifest data/u18_inference_20260930_masked_v1/proxy_manifest.json `
  --predictions-root artifacts/u18_predictions/20261001_u18_zero_shot_masked_v1 `
  --output-dir artifacts/u18_pass_cv/20261116_training_review_v1

conda run -n ballspot-viz python scripts/render_u18_eval_review.py `
  --review-csv artifacts/u18_pass_cv/20261116_training_review_v1/training_review.csv `
  --mode pass `
  --proxy-manifest data/u18_inference_20260930_masked_v1/proxy_manifest.json `
  --output-dir artifacts/u18_pass_cv/20261116_training_review_v1/review_site
```

审查时在本机双击 `review_u18_pass_training.cmd`；它使用已通过 HTTP 200/206 检查的本地回环服务及端口 8766。32 条人工判断已完成，网页可用于复核；版本化结果位于 `artifacts/u18_pass_cv/20261116_training_review_v1/review_exports/`。不回写冻结 GT。

### U18 Pass 人工审查转训练标签——已验证

以下命令已在本机 `ballspot-viz` 环境执行，输出目录为已生成版本，不可再次覆盖；重做须使用新目录并重新核对所有输入哈希。

```powershell
conda run -n ballspot-viz python scripts/prepare_u18_pass_training_labels.py `
  --frozen-dir artifacts/u18_pass_cv/20261112_frozen_v1 `
  --prior-source artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/pass_review_cases.csv `
  --prior-reviewed artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_exports/pass_review_20261112T054717Z_028_corrected.csv `
  --new-source artifacts/u18_pass_cv/20261116_training_review_v1/training_review.csv `
  --new-reviewed artifacts/u18_pass_cv/20261116_training_review_v1/review_exports/pass_review_20261117T071006Z_ccd3a14b.csv `
  --output-dir artifacts/u18_pass_cv/20261117_training_labels_v1

conda run -n ballspot-viz python scripts/verify_u18_pass_training_labels.py `
  --training-dir artifacts/u18_pass_cv/20261117_training_labels_v1 `
  --frozen-dir artifacts/u18_pass_cv/20261112_frozen_v1
```

远端训练标签和 `proxy_manifest.json` 已通过 `scp` 单独传输并核对 SHA-256。Slurm 冒烟命令已验证，作业 `6930737` 完成，**正式训练命令已执行但模型结果未完成验证**：

```bash
sbatch scripts/slurm/u18_pass_head_train.sh A_train_B_test artifacts/u18_pass_cv/20261117_training_labels_v1 artifacts/u18_pass_cv/20261117_head_smoke_A 2
sbatch scripts/slurm/u18_pass_head_train.sh A_train_B_test artifacts/u18_pass_cv/20261117_training_labels_v1 ball_action/experiments/u18_pass_head_A_train_B_test_v1
sbatch scripts/slurm/u18_pass_head_train.sh B_train_A_test artifacts/u18_pass_cv/20261117_training_labels_v1 ball_action/experiments/u18_pass_head_B_train_A_test_v1
```

原始七折 NPZ 的 `fold_scores[:, 0, :]` 单模型基线另行后处理，四段均已验证。下例为 FC 东京 H1；其余三个半场使用相同参数和各自路径。

```powershell
conda run -n ballspot-viz python scripts/postprocess_scores.py `
  --scores artifacts/inference/u18_fc_tokyo_aomori_h1_masked_v1/scores.npz `
  --inference-manifest artifacts/inference/u18_fc_tokyo_aomori_h1_masked_v1/manifest.json `
  --output-dir artifacts/u18_pass_cv/20261117_fold0_baseline_v1/fc_tokyo_aomori_h1 `
  --fold-index 0 --min-height 0.0
```

留出视频上的分类头模型 Slurm 推理通用模板如下；具体 v2 参数已经执行并列在下节：

```bash
sbatch scripts/slurm/u18_pass_head_inference.sh <masked_proxy_mp4> <per_video_config_yaml> <inference_end_sec> <experiment_name> <new_output_dir>
```

### U18 Pass 接球代理负例避让修订——已验证的训练命令

`20261117_training_labels_v2` 的生成命令与上节 v1 完全相同，仅将新的 `--output-dir` 设为 `artifacts/u18_pass_cv/20261117_training_labels_v2`；本机生成、独立验证、远端 SHA-256 核对均已执行。正式训练作业以下列命令提交并完成：

```bash
sbatch scripts/slurm/u18_pass_head_train.sh A_train_B_test artifacts/u18_pass_cv/20261117_training_labels_v2 ball_action/experiments/u18_pass_head_A_train_B_test_v2
sbatch scripts/slurm/u18_pass_head_train.sh B_train_A_test artifacts/u18_pass_cv/20261117_training_labels_v2 ball_action/experiments/u18_pass_head_B_train_A_test_v2
```

前述 v1 留出推理模板已实际用于四段首版测试视频，作业 `6930743`～`6930746` 均已完成；首版仍仅供诊断，正式比较使用 v2。

### U18 Pass 分类头第二版同片段复评——已验证

以下四段 Slurm 推理已分别以作业 `6930750`～`6930753` 执行完成；再次运行须使用新的输出目录，不可覆盖原始分数。远端原始 NPZ 已单独取回并逐个对比 SHA-256。示例为浦和 H1，其余三段分别替换视频、逐视频 YAML、结束秒数、训练轮实验名和新目录：

```bash
sbatch scripts/slurm/u18_pass_head_inference.sh \
  data/u18_inference_20260930_masked_v1/urawa_ryutsu_h1_25fps_masked.mp4 \
  data/u18_inference_20260930_masked_v1/urawa_ryutsu_h1.yaml \
  2716.96 u18_pass_head_A_train_B_test_v2 \
  artifacts/u18_pass_cv/20261117_pass_head_inference_v2/A_train_B_test/urawa_ryutsu_h1/inference
```

本机完整验证、单段后处理和双向比较均已执行并退出 0。后处理四段用相同 `--min-height 0.0`、默认 `sigma=3`/最短峰距 15 帧；下例为浦和 H1。命令中的目录已存在，重做必须换新运行版本。

```powershell
conda run -n ballspot-viz python scripts/verify_u18_pass_head_training.py `
  --labels-root artifacts/u18_pass_cv/20261117_training_labels_v2 `
  --models-root artifacts/u18_pass_cv/20261117_pass_head_models_v2

conda run -n ballspot-viz python scripts/verify_u18_pass_head_inference.py `
  --inference-root artifacts/u18_pass_cv/20261117_pass_head_inference_v2 `
  --models-root artifacts/u18_pass_cv/20261117_pass_head_models_v2 `
  --proxy-manifest data/u18_inference_20260930_masked_v1/proxy_manifest.json `
  --experiment-suffix v2

conda run -n ballspot-viz python scripts/postprocess_scores.py `
  --scores artifacts/u18_pass_cv/20261117_pass_head_inference_v2/A_train_B_test/urawa_ryutsu_h1/inference/scores.npz `
  --inference-manifest artifacts/u18_pass_cv/20261117_pass_head_inference_v2/A_train_B_test/urawa_ryutsu_h1/inference/manifest.json `
  --output-dir artifacts/u18_pass_cv/20261117_pass_head_inference_v2/A_train_B_test/urawa_ryutsu_h1 `
  --min-height 0.0

conda run -n ballspot-viz python scripts/compare_u18_pass_head.py `
  --frozen-dir artifacts/u18_pass_cv/20261112_frozen_v1 `
  --baseline-root artifacts/u18_pass_cv/20261117_fold0_baseline_v1 `
  --improved-root artifacts/u18_pass_cv/20261117_pass_head_inference_v2 `
  --model-manifests-root artifacts/u18_pass_cv/20261117_pass_head_models_v2 `
  --proxy-manifest data/u18_inference_20260930_masked_v1/proxy_manifest.json `
  --experiment-suffix v2 `
  --output-dir artifacts/u18_pass_cv/20261117_head_comparison_v2
```

完整结果及代表错例见 `docs/reports/u18_pass_head_comparison_20261117.md`。`Drive` 输出行保留原权重，不能据此报告正式 Drive 或 Receive 性能。

### U18 Pass 视觉 FP 身份与准确帧复核——已验证的生成与页面入口

下列命令已生成 `20261117_pending_pass_identity_v2` 并验证 17 个遮挡片段哈希、5 条高优先级、网页数据与浏览器切换。该目录已存在，重建须使用新输出目录；人工结果尚为空。

```powershell
conda run -n ballspot-viz python scripts/prepare_u18_pass_identity_queue.py `
  --prior-review artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_exports/pass_review_20261112T054717Z_028_corrected.csv `
  --new-review artifacts/u18_pass_cv/20261116_training_review_v1/review_exports/pass_review_20261117T071006Z_ccd3a14b.csv `
  --frozen-dir artifacts/u18_pass_cv/20261112_frozen_v1 `
  --output-dir artifacts/u18_pass_cv/20261117_pending_pass_identity_v2
```

本机双击 `review_u18_pass_identity.cmd`，页面默认先看 5 条，支持切换全部 17 条、逐帧取半场秒数与 25 FPS 零起始帧号、浏览器草稿及下载 CSV。页面只监听 `127.0.0.1:8767`，结束后关闭命令窗口或按 Ctrl+C。最近 Bepro Pass 仅为时间提示；先判事件是否相同，再记录准确时间。人工导出 `u18_pass_identity_reviewed.csv` 后另存版本，不覆盖空白清单或冻结测试 GT。
