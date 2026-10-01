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
