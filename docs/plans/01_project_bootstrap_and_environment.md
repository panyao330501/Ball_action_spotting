# 步骤 01——项目、仓库和环境准备

状态：进行中  
开始日期：2026-08-31  
涉及范围：本地工作站和 `chiron` 基础设施  
完成后的下一步骤：`02_video_audit_and_inference_contract`

## 目标

在引入模型代码前建立安全、可复现的双机工作流。GitHub 传递代码和文档；Conda 隔离本地可视化与远端推理依赖；大文件单独传输并验证校验和。

## 已验证的初始状态

### 本地

- 工作区位于 `C:\Code\Ball_action_spotting`。
- 输入视频存在，大小约 560 MB。
- 工作区已初始化为 Git 仓库，默认分支为 `main`。
- Conda 25.11.1 安装在 `C:\ProgramData\miniconda3`，但当前 PowerShell 的 `PATH` 中没有 `conda`。
- Git、Docker 和 WSL 可用。
- 当前主机 PowerShell 无法使用 `nvidia-smi`；本地可视化方案不依赖本地 GPU。

### 远端

- `ssh chiron` 可通过已配置的密钥连接。
- 远端身份为 `y_pan@chiron`。
- `/work7/y_pan/Code_repo/Ball_action_spotting/` 已从 GitHub 检出，并配置了相同的 `origin`。
- 可见 8 张 NVIDIA RTX A6000，每张约 49,140 MiB。
- FFmpeg 6.1.1 和 Git 2.43.0 可用。
- Conda 位于 `/work7/y_pan/anaconda3/bin/conda`，但没有加入已测试 Shell 的 `PATH`；其实际环境根目录解析为 `/home/y_pan/workspace7/anaconda3/envs/`。

## 工作包

### 1. 仓库和 GitHub 准备

- [x] 为媒体、权重、产物、环境和密钥创建 Git 忽略规则。
- [x] 创建项目文档和状态维护规范。
- [x] 获取 GitHub 仓库 URL：`https://github.com/panyao330501/Ball_action_spotting.git`。
- [x] 使用默认分支 `main` 初始化本地仓库。
- [x] 添加 GitHub 远端并验证其可访问。
- [x] 检查忽略规则，确认 MP4 被排除。
- [x] 提交并推送文档基线。
- [x] 将 GitHub 仓库克隆到现有空远端目录。
- [x] 验证本地和远端检出相同提交 SHA。

不得使用普通 Git 或 Git LFS 添加源视频，除非后续决策明确批准；不得保存凭证；GitHub 是代码、配置和文档同步的事实来源。

### 2. 本地可视化 Conda 环境

目标环境：`ballspot-viz`

- [x] 确定依赖后创建并提交 `environment-viz.yml`。
- [x] 固定 Python 版本和 Conda 频道。
- [x] 加入 FFmpeg、OpenCV、NumPy、pandas、Pillow、PyYAML、绘图和测试工具。
- [x] 通过 `C:\ProgramData\miniconda3\Scripts\conda.exe` 创建环境。
- [x] 验证 Python、FFmpeg、OpenCV 解码和日文文件名路径访问。
- [ ] 导出诊断用环境快照，但不替换人工维护的环境文件。

禁止把项目依赖安装到 `base`。

### 3. 远端推理 Conda 环境

目标环境：`ballspot-infer`

- [x] 在不暴露敏感信息的前提下检查常见用户级 Conda 位置和 Shell 初始化文件。
- [x] 发现并复用 `/work7/y_pan/anaconda3`，无需重复安装 Miniconda。
- [ ] 获取候选上游模型源码并检查真实 Python、PyTorch 和 CUDA 要求。
- [x] 根据上游依赖和当前兼容性创建 `environment-infer.yml`。
- [x] 安装 PyTorch 2.0.1、CUDA 11.8 和上游固定 Python 依赖。
- [x] 验证 `torch.cuda.is_available()`、GPU 数量、设备和小型张量运算。
- [x] 验证 Conda 推理流程能够调用 FFmpeg 7.1.1。

首次冒烟只使用一张 A6000，不假设八卡并行对 10 分钟视频有收益。

### 4. 目录和产物布局

```text
data/
  raw/                 # 源视频或本地链接
  metadata/            # 生成元数据
weights/               # 预训练权重
artifacts/
  inference/<run_id>/  # 分数、事件、清单和日志
  visualization/<run_id>/
outputs/               # 面向用户的视频和报告
third_party/           # 固定的上游检出
```

- [ ] 按需要在两端创建运行目录。
- [ ] 决定根目录 MP4 是直接引用还是链接/复制到 `data/raw/`。
- [ ] 每次早期提交前确认没有被忽略的大文件进入暂存区。

### 5. 大文件传输和完整性

- [ ] 计算源视频本地 SHA-256。
- [ ] 通过 `scp` 或 `rsync` 单独传输到 `chiron`。
- [ ] 计算远端 SHA-256 并精确比对。
- [ ] 在步骤 02 的元数据中记录哈希、字节数、路径和传输日期。
- [ ] 确定预测和渲染产物的反向传输方式。

### 6. 端到端基础设施冒烟测试

- [x] 从本地向 GitHub 推送小型文档修改。
- [x] 在 `chiron` 拉取并比较提交 SHA。
- [x] 使用 `conda run -n ballspot-viz` 执行本地命令。
- [x] 使用 `conda run -n ballspot-infer` 执行远端 CUDA 冒烟命令。
- [ ] 在两端分别读取一段短视频。
- [x] 将环境创建和冒烟测试证据写入 `docs/testing/test_log.md`。

## 退出标准

1. 本地和远端使用相同 GitHub 仓库及提交。
2. 源 MP4 被忽略，且两端 SHA-256 一致。
3. `ballspot-viz` 通过本地解码和渲染检查。
4. `ballspot-infer` 通过远端 PyTorch/CUDA 和解码检查。
5. 已验证命令写入命令手册。
6. 测试证据追加到测试日志。
7. `AGENTS.md` 指向步骤 02 并列出遗留事项。
8. `docs/milestone.md` 追加完成记录。

## 当前阻塞和待决定事项

- 上游模型源码和权重尚未获取，精确提交仍需在步骤 03 固定。
- 上游 NVIDIA VideoProcessingFramework 未放入当前 Conda 环境；初始 PoC 使用 FFmpeg/OpenCV 解码，步骤 03 再决定是否接入 VPF。
