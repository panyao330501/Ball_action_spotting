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

### 传输源视频——模板

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

### 生成全时长 25 FPS 推理代理——模板

该命令不裁剪规范源；输出仅保留视频流，因为最终可视化仍使用原始带音频 MP4。先确认目标文件不存在，避免意外覆盖。

```powershell
ssh chiron 'source="/work7/y_pan/Code_repo/Ball_action_spotting/data/raw/vs_飛鳥FC_20260704_trimmed_0930.mp4"; proxy="/work7/y_pan/Code_repo/Ball_action_spotting/data/raw/vs_飛鳥FC_20260704_trimmed_0930_25fps_infer.mp4"; test ! -e "$proxy" && /work7/y_pan/anaconda3/bin/conda run -n ballspot-infer ffmpeg -i "$source" -map 0:v:0 -an -vf fps=25 -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p "$proxy"'
```

生成后验证其 FPS、时长和帧数；预期为 25 FPS、1280×720、约 566.5 秒。模型内部再补边至 1280×736。

## 7. 推理、后处理和可视化

以下接口是占位模板，实际模块在对应实施步骤中确定。

### 远端推理——模板

```powershell
ssh chiron "cd /work7/y_pan/Code_repo/Ball_action_spotting && conda run -n ballspot-infer python -m ballspot.infer --config configs/poc.yaml"
```

### 本地可视化——模板

```powershell
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' run -n ballspot-viz python -m ballspot.visualize --config configs/poc.yaml --run-id <RUN_ID>
```

### 本地测试——模板

```powershell
& 'C:\ProgramData\miniconda3\Scripts\conda.exe' run -n ballspot-viz pytest -q
```

实际入口创建后，将模板替换为已验证命令；只有仍受支持的旧命令才保留。
