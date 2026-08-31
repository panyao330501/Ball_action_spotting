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
