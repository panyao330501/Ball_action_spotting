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
