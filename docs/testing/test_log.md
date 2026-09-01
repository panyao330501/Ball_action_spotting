# 测试日志

按时间顺序追加测试。失败记录不得删除，只能在后续添加新的替代测试。

## 记录模板

```text
日期和时间：
测试 ID：
状态：通过 | 失败 | 阻塞
Git 提交：
端点和环境：
命令或命令手册章节：
输入和配置：
观察结果：
证据和产物：
后续动作：
```

## 2026-08-31——本地基础设施检查

- 状态：检查通过，但仍有待设置事项
- 端点和环境：本地 Windows PowerShell
- 观察结果：
  - 输入 MP4 存在，大小为 560,273,283 字节。
  - Git 可用，但工作区尚不是 Git 仓库。
  - Conda 25.11.1 安装在 `C:\ProgramData\miniconda3`。
  - 当前 PowerShell 的 `PATH` 中没有 `conda`。
  - 主机无法使用 `nvidia-smi`；当前架构不要求本地 GPU。
- 后续动作：创建 `ballspot-viz`，获得 GitHub URL 后初始化 Git，并记录正式测试 ID。

## 2026-08-31——chiron 基础设施检查

- 状态：检查通过，但远端 Conda 阻塞
- 端点和环境：`y_pan@chiron`，非交互 SSH Shell
- 观察结果：
  - SSH 密钥连接成功。
  - `/work7/y_pan/Code_repo/Ball_action_spotting/` 存在且为空，目前不是 Git 仓库。
  - 可见 8 张 NVIDIA RTX A6000，每张约 49,140 MiB。
  - FFmpeg 6.1.1 和 Git 2.43.0 可用。
  - 已测试的 Shell 中没有发现 Conda 和 Python。
- 后续动作：定位或安装用户级 Conda，创建 `ballspot-infer`，并克隆 GitHub 仓库。

## 2026-08-31——T-INFRA-001 GitHub 首次同步

- 状态：通过
- Git 提交：`ebf1e177bf094477d1e2e3f032726b678c136742`
- 端点和环境：本地 Windows 与 `y_pan@chiron`
- 命令或命令手册章节：`docs/runbooks/commands.md` 的 GitHub 仓库准备章节
- 观察结果：
  - 空 GitHub 仓库成功接收本地 `main` 分支。
  - 远端目录成功克隆同一仓库。
  - 两端首次检出的完整提交 SHA 一致。
  - 两端 `origin` 均为 `https://github.com/panyao330501/Ball_action_spotting.git`。
  - 源 MP4 和 `.obsidian/` 未进入提交。
- 后续动作：推送本次状态文档更新，并在 `chiron` 使用 `pull --ff-only` 验证日常同步流程。

## 2026-08-31——T-INFRA-002 本地 Conda 和视频解码

- 状态：通过
- 端点和环境：本地 `C:\Users\logan\.conda\envs\ballspot-viz`
- 输入和配置：`environment-viz.yml`；源 MP4
- 观察结果：
  - Python 3.11 环境创建成功。
  - OpenCV 4.12.0、NumPy 2.4.6 及可视化依赖导入成功。
  - 日文路径视频可打开，首帧形状为 `720 x 1280 x 3`。
  - 视频为 H.264、1280×720、30 FPS、16,995 帧、566.5 秒；AAC 音轨存在。
  - 环境内 FFprobe 完成元数据读取。
- 后续动作：步骤 02 将这些信息写入正式视频元数据产物，并人工确认开球偏移。

## 2026-08-31——T-INFRA-003 远端 Conda 和 CUDA

- 状态：通过
- 端点和环境：`chiron`，`/home/y_pan/workspace7/anaconda3/envs/ballspot-infer`
- 输入和配置：`environment-infer.yml`；`CUDA_VISIBLE_DEVICES=0`
- 观察结果：
  - PyTorch 2.0.1、PyTorch CUDA 11.8、OpenCV 4.7.0、NumPy 1.24.3 及上游 Python 依赖导入成功。
  - `torch.cuda.is_available()` 为真。
  - 隔离后可见一张 NVIDIA RTX A6000。
  - GPU 矩阵运算返回预期结果 `[[5.0, 14.0], [14.0, 50.0]]`。
  - 环境内 FFmpeg 7.1.1 可执行。
- 后续动作：获取模型源码和权重后执行 60～90 秒模型推理冒烟测试。

## 2026-08-31——T-VIDEO-001 源视频技术审计与抽帧

- 状态：通过
- 端点和环境：本地 `ballspot-viz`
- 输入和配置：`vs_飛鳥FC_20260704_trimmed_0930.mp4`；抽帧时刻为 0、60、180、300、480、560 秒
- 观察结果：
  - SHA-256 为 `08c487dad084dbc12fbcf760d0ac3d7865fb0092cea767010c75a4b8a6f511be`，大小为 560,273,283 字节。
  - H.264 视频流为 1280×720、30 FPS CFR、16,995 帧、566.500 秒；AAC 音轨存在。
  - 0 秒画面显示场地中线和比赛开始状态，符合“文件从开球后开始”的用户确认。
  - 代表性抽帧显示全场远景，足球在不少帧中仅占少量像素；后续人工审查必须使用 `PARTIAL` / `OFFSCREEN` 区分不可观测情形。
- 证据和产物：`data/metadata/video_metadata.json`；`artifacts/video_audit/frames/`（Git 忽略）
- 后续动作：传输规范源并在远端生成 25 FPS 代理视频，再做模型冒烟推理。

## 2026-08-31——T-MODEL-001 冠军方案输入契约检查

- 状态：通过
- 端点和环境：`chiron`；上游检出 `third_party/ball-action-spotting`，提交 `9c471531c62b51bd0cfe6170b74d035da44c88ed`
- 观察结果：
  - `scripts/ball_action/predict.py` 对输入 FPS 执行 `== 25.0` 断言。
  - 配置使用 15 帧、步长 2、1280×736；运行时 `pad_normalize` 对 1280×720 输入仅上下补边各 8 像素并归一化。
  - 因此 30 FPS 源不可直接送入原预测入口；需先生成全时长 25 FPS CFR 推理代理，且无需拉伸画面。
- 后续动作：在自定义适配器中保留上述模型预处理和时间映射，并以 60～90 秒样本做端到端验证。

## 2026-08-31——T-VIDEO-002 远端媒体传输与推理代理

- 状态：通过
- 端点和环境：本地 Windows 与 `chiron` 的 `ballspot-infer`
- 输入和配置：规范源 MP4；全时长 `fps=25`、H.264、无音频代理
- 观察结果：
  - 远端源文件 SHA-256 为 `08c487dad084dbc12fbcf760d0ac3d7865fb0092cea767010c75a4b8a6f511be`，与本地逐字符相同。
  - 代理视频为 1280×720、25 FPS CFR、14,163 帧、566.520 秒、无音频，SHA-256 为 `b40d98c19f3d4dc172ab91a4e5900921ef8e9982c7d59efd0630d745c47e3356`。
  - 源与代理的时长差为 0.020 秒，小于一个 25 FPS 帧的 0.040 秒时间容差。
- 后续动作：步骤 03 获取权重，实施 25 FPS 自定义视频适配器，并执行 60～90 秒冒烟推理。

## 2026-09-01——T-MODEL-002 官方权重清单与加载兼容性

- 状态：通过
- 端点和环境：`chiron`，`ballspot-infer`，`CUDA_VISIBLE_DEVICES=0`
- 输入和配置：用户手动从作者 README 指定的公开 Google Drive 下载并放置在项目根目录的 `action/`、`ball_action/`；上游源码提交 `9c471531c62b51bd0cfe6170b74d035da44c88ed`
- 观察结果：
  - `ball_action/experiments/ball_finetune_long_004/` 包含 7 个 fold 权重，每个大小为 55,081,387 字节；SHA-256 已写入 `docs/model_sources/lromul_ball_action_2023.md`。
  - 在固定上游代码和单张 A6000 上，`argus.load_model` 成功加载 fold 0，无缺失键或参数错误。
  - 实际权重参数为 `multidim_stacker`、2 类、33 帧、步长 2、`pad_normalize(size=(1280, 736))`；因此替代先前对 15 帧初始模型的实现假设。
- 后续动作：实现独立 25 FPS 自定义视频适配器，并以 0～90 秒范围完成两次可复现的冒烟推理。

## 2026-09-01——T-ADAPTER-001 推理入口静态检查

- 状态：通过（附一次已解决的本地命令包装器失败）
- 端点和环境：本地 `ballspot-viz`
- 输入和配置：`scripts/run_custom_inference.py`、`scripts/slurm/smoke_inference.sh`、`configs/poc_video.yaml`
- 观察结果：
  - `python -m py_compile scripts/run_custom_inference.py` 通过；配置的 `frame_stack_size` 为已验证的 33。
  - 首次经 `conda run ... --help` 调用失败，原因是 Windows CP932 控制台无法编码脚本当时的中文帮助文本；这不是模型或脚本逻辑错误。
  - 将 CLI 帮助文本改为 ASCII 英文后，直接使用 `ballspot-viz` 解释器执行 `--help` 成功，静态编译和配置检查再次通过。
- 后续动作：在 chiron 安装配置中固定的 PyYAML，并进行不占用 GPU 的上游导入检查；GPU 冒烟仅通过 Slurm 提交。
