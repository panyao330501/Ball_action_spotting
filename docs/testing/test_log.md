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
- 远端首次上游导入检查失败：上游 `src.frame_fetchers` 包会无条件导入未安装的 `PyNvCodec`。适配器随后改为项目内的连续 OpenCV 灰度解码，不修改上游检出，仍复用上游 `MultiDimStackerPredictor` 与模型帧处理器；该修复待远端复测。
- 后续动作：在 chiron 安装配置中固定的 PyYAML，并进行不占用 GPU 的上游导入检查；GPU 冒烟仅通过 Slurm 提交。

## 2026-09-01——T-ADAPTER-002 Slurm 端到端冒烟与可复现性

- 状态：通过（附两次已解决的比较命令语法失败）
- 端点和环境：`chiron` Slurm 节点 `gtr`；作业 `6835524`、`6835525`；每次 1 张 NVIDIA RTX A6000；`ballspot-infer`
- 输入和配置：25 FPS 代理视频；0.0～90.0 秒；7 个 `ball_finetune_long_004` fold；水平翻转 TTA
- 观察结果：
  - 两次作业均完成并写入独立的 `artifacts/inference/smoke_<job_id>/` 目录；运行时间分别为约 285.0 秒和 279.5 秒。
  - 每次导出 2,217 个有序预测帧（1.320～89.960 秒），`fold_scores=(2217, 7, 2)`、`ensemble_scores=(2217, 2)`，类别为 `PASS`、`DRIVE`。
  - 两种分数均无 NaN/Inf；集成分数范围为 0.0051905～0.8897791。
  - 两次比较的全部数组逐元素相同，最大绝对差为 0；两个 `scores.npz` 的 SHA-256 均为 `bf9aed0f7bda660ca70d4c3c1c94583d2dd3f082945a50508b2d3c218789da46`。
  - 首两次比较命令各因少写右括号而报 `SyntaxError`；未修改或损坏产物，随后使用简化的比较表达式成功完成验证。
- 证据和产物：`artifacts/inference/smoke_6835524/`、`artifacts/inference/smoke_6835525/`（Git 忽略）
- 后续动作：步骤 04 对完整 566.5 秒提交同一推理入口，只生成一次全程原始分数，再离线执行后处理。

## 2026-09-01——T-INFER-001 全程推理、后处理和本地传输

- 状态：通过（附本地 CPU 环境缺少 SciPy 的非阻塞检查限制）
- 端点和环境：chiron Slurm 节点 `gtr`，作业 `6835526`，单张 RTX A6000；远端 `ballspot-infer`；本地 `ballspot-viz`
- 输入和配置：完整 25 FPS 推理代理；0.0～566.5 秒；7-fold、水平翻转 TTA；Gaussian `sigma=3.0`、峰值高度 `0.2`、间距 15 帧
- 观察结果：
  - 作业耗时 1,742.97 秒，生成 14,097 帧的 `(14097, 7, 2)` fold 分数与 `(14097, 2)` 集成分数，时间为 1.320～565.160 秒；所有分数有限且时间严格递增。
  - `scores.npz` SHA-256 为 `3afc57f2d3f692146f9ccea2ad994d0fd8810b60ea870c3d5272383a48653f56`。
  - 后处理生成 58 个候选（Pass 34、Drive 24）；JSON/CSV 的事件 ID 一致、时间有序、标签和置信度均符合契约。
  - 本地 `ballspot-viz` 缺少 SciPy，无法本地运行后处理帮助入口；实际远端环境中 SciPy 已固定且后处理通过，因此不阻塞本地可视化。
  - 5 个非媒体结果文件已取回本地，所有 SHA-256 与远端一致；本地事件契约复查通过。
- 证据和产物：远端及本地 `artifacts/inference/full_6835526/`（Git 忽略）
- 后续动作：步骤 05 在本地源视频上渲染完整事件叠加视频与事件集锦。

## 2026-09-01——T-VIZ-001 初始集锦烟雾渲染

- 状态：失败
- Git 提交：`0333fc7b3025e5277a834813496b6fd381e5aae9` 加未提交渲染器实现
- 端点和环境：本地 `ballspot-viz`；FFmpeg 7.1.1
- 输入和配置：源视频 0～26 秒；前 4 个候选；运行 `smoke_20260901_step05`
- 观察结果：
  - 完整叠加视频成功生成 780 帧并保留音频。
  - 集锦滤镜在初始化时失败；`drawbox` 的宽度表达式错误引用自身 `w`，而不是输入宽度 `iw`。
  - 失败运行保存 `render_manifest.json` 和 FFmpeg 日志，没有覆盖或损坏源视频及事件文件。
- 证据和产物：`artifacts/visualization/smoke_20260901_step05/`；`outputs/smoke_20260901_step05/`
- 后续动作：修正输入宽高变量并使用新运行 ID 重跑。

## 2026-09-01——T-VIZ-002 重叠区间直接 concat 检查

- 状态：失败
- Git 提交：`0333fc7b3025e5277a834813496b6fd381e5aae9` 加未提交渲染器实现
- 端点和环境：本地 `ballspot-viz`；FFmpeg 7.1.1
- 输入和配置：源视频 0～26 秒；4 个候选各 7 秒；运行 `smoke_20260901_step05_r2`
- 观察结果：
  - 脚本进程完成，但集锦视频只有 22.692 秒，短于期望的 28.000 秒。
  - 日志出现重复读取同一 MP4 重叠区间引起的 DTS 回退；因此该实现不能保证每个候选各保留一份完整上下文。
- 证据和产物：`artifacts/visualization/smoke_20260901_step05_r2/`；`outputs/smoke_20260901_step05_r2/`
- 后续动作：改为每个候选独立精确编码，再用 concat demuxer 拼接独立片段。

## 2026-09-01——T-VIZ-003 最终短片渲染和视觉质检

- 状态：通过（包含已解决的时长和叠加位置迭代）
- Git 提交：`0333fc7b3025e5277a834813496b6fd381e5aae9` 加未提交渲染器实现
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1
- 命令或命令手册章节：`docs/runbooks/commands.md` 的“本地可视化烟雾渲染”
- 输入和配置：源视频 SHA-256 `08c487dad084dbc12fbcf760d0ac3d7865fb0092cea767010c75a4b8a6f511be`；事件 SHA-256 `9a44494fc190fff1eef479ddd91bd7aa617ccc3613689f761d340b6dd4a11ec4`；0～26 秒；4 个候选；最终运行 `smoke_20260901_step05_r5`
- 观察结果：
  - 8 个时间、事件、显示行和边界单测全部通过。
  - `annotated_full.mp4` 为 H.264 1280×720、30 FPS、780 帧、26.000 秒视频流；AAC 48 kHz 双声道保留；完整解码无错误。
  - 4 个中间集锦片段均为 210 帧/7.000 秒；`event_highlights.mp4` 为 840 帧/28.000 秒视频流和 28.000 秒 AAC 音频；完整解码无错误。容器因 AAC priming 的视频起点为 0.021029 秒，小于一帧。
  - 抽帧确认源时间码可读，Pass/Drive 分别使用绿色/橙色，同窗事件按时间排列；事件前 0.5 秒出现，结束后消失；集锦标题正确。
  - `smoke_20260901_step05_r3` 解决了候选丢时长问题；`r4` 固定了逐片段帧数和最终总时长；`r5` 将时间码移出原计分牌并压缩密集事件行，作为最终通过运行。
- 证据和产物：`artifacts/visualization/smoke_20260901_step05_r5/render_manifest.json`、`qa_frames/`；`outputs/smoke_20260901_step05_r5/`
- 后续动作：以相同入口和正式 `fast` / CRF 18 参数生成完整 566.5 秒视频及 58 事件集锦。

## 2026-09-01——T-VIZ-004 全程可视化和技术质检

- 状态：通过（附一次不影响产物的抽帧哈希命令失败）
- Git 提交：`2b29422a2d79f680d2eb153cc6ff5ff1943b95e0`
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1
- 命令或命令手册章节：`docs/runbooks/commands.md` 的“本地全程可视化”
- 输入和配置：规范源 SHA-256 `08c487dad084dbc12fbcf760d0ac3d7865fb0092cea767010c75a4b8a6f511be`；事件 SHA-256 `9a44494fc190fff1eef479ddd91bd7aa617ccc3613689f761d340b6dd4a11ec4`；58 个候选；`libx264 fast` / CRF 18；运行 `20260901_151037_2b29422_poc-video`
- 观察结果：
  - 渲染清单状态为 `completed`，记录 Pass 34、Drive 24，且明确 `spatial_boxes=false`。
  - `annotated_full.mp4` 为 H.264 1280×720、30 FPS、16,995 帧、566.500 秒；AAC 48 kHz 双声道、26,557 帧、566.493 秒，与规范源一致。完整解码通过。
  - `event_highlights.mp4` 为 H.264 1280×720、30 FPS、12,180 帧、406.000 秒视频流；AAC 为 406.000 秒。容器因 0.021029 秒 AAC priming 为 406.021029 秒，偏差小于一帧。完整解码通过。
  - 58 个中间片段数量、文件顺序、视频/音频流逐一检查通过；每段为 210 帧/7.000 秒，无边界截断。
  - 源音轨和完整视频音轨的解码 framemd5 文件 SHA-256 均为 `6777E7139976AEBBC0FB297FD32BC2249EF90E3474E5197366C35DC58AAFC46B`。
  - 人工查看 18.000、312.600、548.000 秒抽帧：时间码准确，颜色和按时间排序正确；后段 7 事件密集簇仍在画面上半部内。检查集锦第 1、29、58 个事件标题，序号、ID、标签、置信度和源时间正确。
  - 首次尝试用 `Get-FileHash -LiteralPath '*.jpg'` 计算抽帧哈希因 `LiteralPath` 不展开通配符而失败；随后改用 `Get-ChildItem | Get-FileHash` 成功。该辅助命令未修改任何媒体产物。
- 证据和产物：`artifacts/visualization/20260901_151037_2b29422_poc-video/render_manifest.json`、`visualization.log`、`qa_frames/`；`outputs/20260901_151037_2b29422_poc-video/`
- 输出 SHA-256：`annotated_full.mp4` 为 `8debb7951d0be1a09f4c4e28482f672ced45c12bfb2bb523a808a5e8fa480609`；`event_highlights.mp4` 为 `7411b90692de5f348c8e2c98a115580640188b39714491c712a33cd07b3f4006`。
- 后续动作：步骤 06 逐一审查 58 个候选并连续观看全程，区分模型失败与画面不可观测。

## 2026-09-01——T-VIZ-005 事件固定时间码显示烟雾测试

- 状态：通过
- Git 提交：`adca843` 加未提交的事件时间码显示修订
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1
- 输入和配置：规范源 0～26 秒；前 4 个候选；`ultrafast` / CRF 23；运行 `smoke_20260901_event_timecode`
- 观察结果：
  - 8 个自动化测试全部通过；滤镜测试明确检查事件行包含毫秒级固定时间码。
  - 每条事件在置信度后显示 `event HH:MM:SS.mmm`，可与顶部动态 `SOURCE HH:MM:SS.mmm` 直接比较。
  - 18.000 和 21.600 秒抽帧确认 Pass/Drive 颜色、事件时间、显示顺序均正确，背景条加宽后没有文字截断。
  - 烟雾完整视频为 780 帧/26.000 秒；4 个集锦片段各 210 帧/7.000 秒，最终集锦视频流为 840 帧/28.000 秒。
- 证据和产物：`artifacts/visualization/smoke_20260901_event_timecode/render_manifest.json`、`qa_frames/`；`outputs/smoke_20260901_event_timecode/`
- 后续动作：以新运行 ID 和正式 `fast` / CRF 18 参数重新生成全程审查视频与事件集锦，不覆盖原运行。

## 2026-09-01——T-VIZ-006 带事件时间码的全程修订渲染

- 状态：通过
- Git 提交：`1b5f2bf8b0d886269cef4ee5eaa1f57e6658e08a`
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1
- 命令或命令手册章节：`docs/runbooks/commands.md` 的“本地全程可视化”
- 输入和配置：规范源及原 58 个候选；`libx264 fast` / CRF 18；运行 `20260901_154013_1b5f2bf_poc-video-timecode`
- 观察结果：
  - 渲染清单状态为 `completed`，记录 Pass 34、Drive 24；事件行在置信度后显示毫秒级固定事件时间码。
  - `annotated_full.mp4` 为 89,140,776 字节，H.264 1280×720、30 FPS、16,995 帧、566.500 秒；AAC 为 566.493 秒。完整解码通过。
  - `event_highlights.mp4` 为 82,586,202 字节，视频流为 12,180 帧/406.000 秒，AAC 为 406.000 秒；完整解码通过。
  - 58 个中间片段逐一检查，全部为 210 帧/7.000 秒，顺序和流结构正确。
  - 源音轨与完整修订视频的解码 framemd5 文件 SHA-256 均为 `6777E7139976AEBBC0FB297FD32BC2249EF90E3474E5197366C35DC58AAFC46B`。
  - 人工查看 18.000、312.600、548.000 秒抽帧，确认事件固定时间码与动态源时间码可直接对比，文字无截断，Pass/Drive 颜色和密集行顺序正确。
- 证据和产物：`artifacts/visualization/20260901_154013_1b5f2bf_poc-video-timecode/render_manifest.json`、`visualization.log`、`qa_frames/`；`outputs/20260901_154013_1b5f2bf_poc-video-timecode/`
- 输出 SHA-256：`annotated_full.mp4` 为 `30cc1c4f7a50f222ea1cc501d11cfd56111b7a6f3fcdb1f11dd6a002eef71f88`；`event_highlights.mp4` 为 `f03ebe0999e313777a14f6411748727705ca8bfe6455ac713e8b75ac79906d61`。
- 后续动作：步骤 06 使用修订视频逐一审查 58 个候选。

## 2026-09-01——T-VIZ-007 播放卡顿逐帧诊断

- 状态：通过（未发现渲染器新增掉帧；具体主观卡顿时间点仍待用户提供）
- Git 提交：`663f9f3`
- 端点和环境：本地 `ballspot-viz`；OpenCV 4.12.0；FFmpeg/FFprobe 7.1.1
- 输入和配置：规范源视频与修订版 `outputs/20260901_154013_1b5f2bf_poc-video-timecode/annotated_full.mp4`；逐帧比较画面下半部以排除动态文字叠加影响。
- 观察结果：
  - 源和输出均为严格 30 FPS、16,995 帧、566.500 秒；输出完整解码已通过。
  - 渲染日志完成于第 16,995 帧，所有进度记录中非零 `dup_frames` 和 `drop_frames` 数量均为 0。
  - 两份视频共比较 16,995 个对齐帧；无未配对尾帧。
  - 相邻帧画面运动量的源/输出相关系数为 `0.9985396687`，两者运动分布高度一致。
  - 未发现输出运动量低于 `0.15`、同时源运动量高于 `0.75` 的帧，即没有“输出静止而同一源帧明显运动”的证据。
  - 源视频为 H.264 Main、无 B 帧、约 7.71 Mbps；输出为 H.264 High、2 个 B 帧、约 1.06 Mbps。两者均为 Level 3.1、1280×720、30 FPS；输出解码负载很低，但不同播放软件或硬件解码路径仍可能呈现不同观感。
- 结论：现有证据排除渲染时丢帧或时间轴异常。主观卡顿更可能来自源内容本身的低运动/近重复画面，或特定播放器的 H.264 High/B-frame 播放路径；需要 2～3 个具体源时间点才能进一步区分。
- 后续动作：取得用户观察到的具体 `SOURCE` 时间后，对相同区间的源视频和输出视频做并排检查；如仅输出复现，再测试 Main Profile、无 B 帧的兼容编码。

## 2026-09-02——T-VIZ-008 全局事件时间轴烟雾渲染

- 状态：通过
- Git 提交：`9bbd08a` 加未提交的全局时间轴实现
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1
- 输入和配置：规范源 0～26 秒；前 4 个候选作为当前事件叠加；全部 58 个候选作为完整 566.5 秒时间轴标记；`ultrafast` / CRF 23；运行 `smoke_20260902_global_timeline_v1`
- 观察结果：
  - 静态编译及 10 个单元测试通过；测试覆盖完整时间映射、端点像素、区间外拒绝、红蓝类别颜色、动态播放指针和集锦标题位置。
  - `annotated_full.mp4` 为 H.264 1280×840、30 FPS、780 帧/26.000 秒，含 AAC 音频；渲染清单记录当前叠加 4 个事件、全局标记 58 个、源画布 1280×720 和底栏 120 像素。
  - 4 个中间片段各 210 帧/7.000 秒，`event_highlights.mp4` 为 840 帧/28.000 秒；两份输出完整解码无错误。
  - 人工查看 0.2、18、25 秒完整视频抽帧，确认源画面未缩放或遮挡，Pass 蓝线位于轨道上方、Drive 红线位于下方，白色指针随源时间向右移动；集锦抽帧确认标题位于新增底栏顶部且时间轴仍可见。
  - Conda 包装器在命令结束时输出 OpenCL `temp.txt` 访问警告，但相关命令退出码均为 0，媒体和测试结果不受影响。
- 证据和产物：`artifacts/visualization/smoke_20260902_global_timeline_v1/render_manifest.json`、`qa_frames/`；`outputs/smoke_20260902_global_timeline_v1/`
- 输出 SHA-256：`annotated_full.mp4` 为 `dfcabedaa7541f4cb43bd3abb6c57803c83d5051d4c5525cd90c0fbe6a46e309`；`event_highlights.mp4` 为 `7f7851ca98987cc789cd12cdf82fe635be15b9e8d209b533dd93b166555f4ad4`。
- 后续动作：提交实现后，以正式 `fast` / CRF 18 参数生成不覆盖旧版本的全程审查视频和 58 事件集锦。

## 2026-09-02——T-VIZ-009 带全局事件时间轴的全程渲染

- 状态：通过
- Git 提交：`20ae1e5e1e336cd95740568360455d631331f8ac`
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1
- 命令或命令手册章节：`docs/runbooks/commands.md` 的“本地全程可视化”
- 输入和配置：规范源及原 58 个候选；完整 `0.000`～`566.500` 秒全局时间轴；`libx264 fast` / CRF 18；运行 `20260902_144310_20ae1e5_poc-video-global-timeline`
- 观察结果：
  - 渲染清单状态为 `completed`，记录 Pass 34、Drive 24、时间轴标记 58 个、源画布 1280×720、输出画布 1280×840、底栏高度 120 像素。
  - `annotated_full.mp4` 为 92,974,502 字节，H.264 1280×840、30 FPS、16,995 帧/566.500 秒；AAC 为 26,557 帧/566.493 秒。完整解码无错误。
  - `event_highlights.mp4` 为 86,606,943 字节，H.264 1280×840、12,180 帧/406.000 秒；AAC 为 19,083 帧/406.000 秒。完整解码无错误。
  - 58 个中间片段按序逐一检查，全部为 1280×840、30 FPS、210 帧/7.000 秒，无异常片段。
  - 源音轨和完整视频音轨的解码 framemd5 文件 SHA-256 均为 `6777E7139976AEBBC0FB297FD32BC2249EF90E3474E5197366C35DC58AAFC46B`；渲染日志中非零 `dup_frames` 和 `drop_frames` 记录均为 0。
  - 人工查看 0.2、18、312.6、548、566.2 秒完整视频抽帧，确认源画面没有缩放或被底栏覆盖，全部事件位置固定，白色指针从轨道起点移动至终点；查看第 1、29、58 个集锦事件，确认标题、固定源时间和全局位置一致。
  - FFmpeg 日志出现 301 行 `Fontconfig error: No writable cache directories`，原因是受限环境不能写用户字体缓存；Arial 字体仍正常解析并出现在全部抽帧中，渲染退出码为 0，因此这是非阻塞环境警告而不是媒体失败。
- 证据和产物：`artifacts/visualization/20260902_144310_20ae1e5_poc-video-global-timeline/render_manifest.json`、`visualization.log`、`qa_frames/`、两份音轨 framemd5；`outputs/20260902_144310_20ae1e5_poc-video-global-timeline/`
- 输出 SHA-256：`annotated_full.mp4` 为 `0c375856f5c7afa5631acce05187189808675e996c626024ce04daba7ea11b8c`；`event_highlights.mp4` 为 `f91ec0c4c117bdd27152a2c5b44d1203ea2a5e00b2f7a36de539dbd94f755264`。
- 后续动作：步骤 06 使用该运行逐一审查 58 个候选，并连续观看全片记录明显漏检、画外区间和主要失败模式。

## 2026-09-02——T-VIZ-010 两像素事件标记预览

- 状态：通过；待用户确认视觉方案
- Git 提交：`5dc972b` 加未提交的标记宽度调整
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1
- 输入和配置：规范源 0～26 秒；全片 58 个时间轴标记；红蓝事件竖线由 3 像素缩至 2 像素；`ultrafast` / CRF 23；运行 `smoke_20260902_timeline_2px_v1`
- 观察结果：
  - 静态编译和 10 个自动化测试通过；测试明确断言时间轴标记宽度为 2 像素，清单同时记录 `marker_width_px=2`。
  - `annotated_full.mp4` 与 `event_highlights.mp4` 均完整解码无错误，输出画布仍为 1280×840；动态指针、轨道、颜色、事件位置和其他布局均未改变。
  - 人工查看 0.2 和 18 秒抽帧，确认红蓝线比 3 像素正式版本更细，密集事件簇仍清晰可辨。
- 证据和产物：`artifacts/visualization/smoke_20260902_timeline_2px_v1/render_manifest.json`、`qa_frames/`；`outputs/smoke_20260902_timeline_2px_v1/`
- 输出 SHA-256：`annotated_full.mp4` 为 `dc5df727c04eace7f8e8054b398236c92de34cf6f1c5d1f900682845db4ec437`；`event_highlights.mp4` 为 `613dc9937027e75a9535afcd1dccc40da7acf87776c830895c0a50572915e982`。
- 后续动作：用户确认 2 像素观感后，再提交正式参数的全程渲染并切换步骤 06 固定输入；确认前保留现有 3 像素正式版本。

## 2026-09-02——T-VIZ-011 两像素事件标记全程渲染

- 状态：通过
- Git 提交：`978ded71fac1ace3372db3915d72f942a9e896ef`
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1
- 命令或命令手册章节：`docs/runbooks/commands.md` 的“本地全程可视化”
- 输入和配置：规范源及 58 个候选；全片时间轴标记宽度 2 像素；`libx264 fast` / CRF 18；运行 `20260902_151709_978ded7_poc-video-global-timeline-2px`
- 观察结果：
  - 渲染清单状态为 `completed`，记录 Pass 34、Drive 24、事件标记 58 个、`marker_width_px=2`、输出画布 1280×840。
  - `annotated_full.mp4` 为 92,965,399 字节，H.264 1280×840、30 FPS、16,995 帧/566.500 秒；AAC 为 26,557 帧/566.493 秒。完整解码无错误。
  - `event_highlights.mp4` 为 86,378,507 字节，H.264 1280×840、12,180 帧/406.000 秒；AAC 为 19,083 帧/406.000 秒。完整解码无错误。
  - 58 个中间片段逐一检查，全部为 1280×840、30 FPS、210 帧/7.000 秒，无异常片段。
  - 源音轨和完整视频音轨的解码 framemd5 文件 SHA-256 均为 `6777E7139976AEBBC0FB297FD32BC2249EF90E3474E5197366C35DC58AAFC46B`；日志中非零 `dup_frames`、`drop_frames` 和 Fontconfig 之外错误均为 0。
  - 人工查看 0.2、18、312.6、548、566.2 秒完整视频及第 1、29、58 个集锦抽帧，确认 2 像素红蓝线、白色指针、固定源时间和标题均正确。
- 证据和产物：`artifacts/visualization/20260902_151709_978ded7_poc-video-global-timeline-2px/render_manifest.json`、`visualization.log`、`qa_frames/`、两份音轨 framemd5；`outputs/20260902_151709_978ded7_poc-video-global-timeline-2px/`
- 输出 SHA-256：`annotated_full.mp4` 为 `373e4e70419bb72846cdadac9865878a14a1541660e0c1ee6ee36b432cbde42e`；`event_highlights.mp4` 为 `b2e3e770f72c25a016ac44c1c1f11aad4cb728d340bb0c33de97a063f1100cd6`。
- 后续动作：步骤 06 使用该 2 像素正式运行进行 58 个候选和全片主观审查。

## 2026-09-16——T-DOC-001 IKOMA BAS 共享稿事实核对

- 状态：通过（附一次因正式视频被重命名而触发的路径检查失败）
- 端点和环境：本地 PowerShell；仓库工作区与正式推理/可视化产物
- 检查内容：共享稿中的事件总数、分类数量、7-fold、TTA、有效预测帧数、后处理清单及可共享视频文件是否与实际 JSON/CSV/manifest 一致。
- 观察结果：
  - `events.csv`、推理清单和后处理清单交叉检查通过：共 58 个候选，Pass 34、Drive 24；fold 数为 7，horizontal flip TTA 为启用，有效预测为 14,097 帧。
  - 首次文件存在性检查按生成时名称 `annotated_full.mp4` 查找而失败。检查目录后确认用户已将其重命名为 `ball_action_spotting_with_global_ bar.mp4`；文件大小仍为 92,965,399 字节。
  - 重命名后完整视频 SHA-256 为 `373e4e70419bb72846cdadac9865878a14a1541660e0c1ee6ee36b432cbde42e`，与 T-VIZ-011 和渲染清单完全一致；事件集锦 SHA-256 亦保持 `b2e3e770f72c25a016ac44c1c1f11aad4cb728d340bb0c33de97a063f1100cd6`。
  - 已将共享稿和步骤 06 固定输入改为当前实际文件名，历史渲染清单保持生成时记录不变。
- 结论：共享稿中的数值、方法与当前可用成果物均可追溯；不把无 GT 候选误述为精度结果。

## 2026-09-16——T-DOC-002 IKOMA BAS 英文共享稿精简检查

- 状态：通过
- 端点和环境：本地工作区
- 检查内容：按用户反馈检查共享稿语言、篇幅、必要技术信息和外部链接占位。
- 观察结果：共享稿已改为英文，保留 58 个候选（Pass 34、Drive 24）、模型、7-fold/TTA、输入及时序后处理设置；可视化视频和预测标签各有一个未填写的 Google Drive URL 占位；无本地绝对路径或内部运行清单。
- 结论：共享稿可在用户补充两个 Google Drive URL 后直接发送。

## 2026-09-29——T-CAND-001 漏检候选与 tracking 接口单元测试

- 状态：通过
- Git 提交：`ee66a96` 加未提交候选生成、渲染和测试实现
- 端点和环境：本地 `ballspot-viz`；Python 3.11；SciPy 1.17.1；openpyxl 3.1.5
- 检查内容：静态编译及完整 pytest；覆盖低阈值峰值、fold 分歧、正式事件排除、重叠窗口合并、Excel 前向填充、种子覆盖、tracking `Unknown` 标签接口和候选渲染文字。
- 观察结果：初版 17 项测试通过；窗口合并逻辑细化为“上下文窗口重叠”并增加 tracking 解析与 tracking-only 并集测试后，最终 20 项测试全部通过。
- 结论：候选生成核心规则和可选 tracking 边界通过本地单元测试。

## 2026-09-29——T-CAND-002 全程 BAS-only 候选生成

- 状态：通过
- 端点和环境：本地 `ballspot-viz`；输入为 `artifacts/inference/full_6835526/scores.npz`、正式事件和只读 `BAS漏检.xlsx`；未提供 tracking。
- 参数：Gaussian `sigma=3.0`；集成最低峰值 `0.05`；高优先级峰值 `0.12`；正式阈值/fold 峰值 `0.2`；同类正式事件排除窗口 `±1.0` 秒；峰值间距 15 帧。
- 观察结果：初版运行产生相同 199 个候选，但按候选时间差合并为 59 个窗口/514.64 秒；改为合并重叠上下文且限制单窗最长 15 秒后，正式运行 `20260929_153408_ee66a96_bas-miss-candidates-v2` 生成 199 个候选（Pass 81、Drive 118；高 76、中 123）、36 个窗口/436.32 秒。
- 种子检查：11 个用户确认的远侧漏检中 6 个在同类 `±1.0` 秒内被覆盖，覆盖率 54.5%；报告明确该数值不是正式 Recall。
- 证据：`artifacts/candidate_mining/20260929_153408_ee66a96_bas-miss-candidates-v2/`。

## 2026-09-29——T-CAND-003 候选集锦烟雾渲染

- 状态：通过
- 端点和环境：本地 `ballspot-viz`；FFmpeg/FFprobe 7.1.1；`ultrafast` / CRF 23。
- 输入：候选初版前 3 个高优先级窗口；运行 `smoke_20260929_153122_candidate-review-v1`。
- 观察结果：3 个窗口分别精确编码并拼接为 29.600 秒、888 帧、1280×720、30 FPS H.264 视频，含 AAC 48 kHz 双声道音轨。抽查三段画面确认窗口优先级、源时间、候选 ID、类别、BAS 分数、fold 最高分和证据来源可读；无空间框。
- 输出 SHA-256：`e716139700d70ca7d10a59ddd8197c614425213d7dc078887510e1fe09209c1d`。

## 2026-09-29——T-CAND-004 正式漏检候选集锦和技术质检

- 状态：通过
- 端点和环境：本地 `ballspot-viz`；FFmpeg/FFprobe 7.1.1；`libx264 fast` / CRF 18。
- 输入：正式候选运行 `20260929_153408_ee66a96_bas-miss-candidates-v2` 的全部 36 个高/中优先级窗口；运行 `20260929_153438_ee66a96_bas-miss-review-v1`。
- 观察结果：36 个中间片段全部生成；最终视频为 H.264 1280×720、30 FPS、13,089 帧/436.300 秒，AAC 48 kHz 双声道约 436.293 秒。预期帧数与实际帧数均为 13,089，完整视频解码无错误。
- 人工抽查：查看开头、高优先级第 16 窗、中优先级开头、用户 120.300 秒漏检附近及结尾画面；标题、类别颜色、分数、证据和固定源时间均清晰，密集窗口使用 `+N more` 避免文字溢出。
- 证据：`artifacts/candidate_review/20260929_153438_ee66a96_bas-miss-review-v1/` 及其 `qa_frames/`；`outputs/20260929_153438_ee66a96_bas-miss-review-v1/miss_candidate_highlights.mp4`。
- 输出 SHA-256：`b37f8e8e6c2cc378ce771462a0097e2a5286dd9413b6e0b21bbc72b34e2d1342`。

## 2026-09-30——T-CAND-005 候选集锦动态源时间修订

- 状态：通过
- 端点和环境：本地 `ballspot-viz`；Python 3.11；FFmpeg/FFprobe 7.1.1；`libx264 fast` / CRF 18。
- 自动化检查：静态编译通过，完整 pytest 为 20 项全部通过；滤镜测试明确断言窗口源起点被写入 `SOURCE %{pts:hms:offset}` 动态时间表达式。
- 烟雾检查：运行 `smoke_20260930_dynamic-source-time-v1` 生成首个窗口 384 帧/12.800 秒视频；窗口源起点为 `00:00:10.800`，片段 0.5、5.5、11.5 秒处分别显示 `00:00:11.300`、`00:00:16.300`、`00:00:22.300`。
- 正式输入：候选运行 `20260929_153408_ee66a96_bas-miss-candidates-v2` 的 36 个高/中优先级窗口；正式渲染运行 `20260930_141315_ee66a96_bas-miss-review-timecode-v2`。
- 技术检查：最终视频为 H.264 1280×720、30 FPS、13,089 帧/436.300 秒，AAC 48 kHz 双声道 436.305 秒；容器时长 436.321 秒。完整音视频解码无错误，36 个中间片段全部存在，逐片检查分辨率、帧率、音轨和预期帧数均无失败；滤镜清单包含 36 个动态 `SOURCE` 时间表达式。
- 人工抽查：检查第 1、16、26、29、36 窗，覆盖高优先级、中优先级、用户 `00:02:00.300` 漏检附近和结尾。右上角当前源时间均落在窗口范围内并与固定 `event` 时间可直接对照；因 30 FPS 帧边界产生的最大显示差不超过一帧。
- 证据：`artifacts/candidate_review/20260930_141315_ee66a96_bas-miss-review-timecode-v2/` 及其 `qa_frames/`；`outputs/20260930_141315_ee66a96_bas-miss-review-timecode-v2/miss_candidate_highlights.mp4`。
- 输出 SHA-256：`dab3bb245b1d948975945dc4e4d31b463989c57ace4daf173e682b276a52ded2`。

## 2026-09-30——T-U18-001 U18 GT/代理/评估单元测试

- 状态：通过（修复两项首轮失败后）
- 端点和环境：本地 `ballspot-viz`；Python 3.11；pytest。
- 首轮失败 1：后半场 `2734.715 - 2700` 产生 `34.715000000000146` 浮点尾差；转换器改为写出前保留 6 位小数。
- 首轮失败 2：代理生成器把未传 `--video-id` 的空选择误判为未知 ID；修正为空时处理全部四个视频。该次失败发生在编码前，只创建空运行目录，没有生成媒体。
- 最终结果：`python -m pytest -q` 为 28 项全部通过；新增测试覆盖半场时间换算、guard/视频外排除、50 条平衡审查抽样、遮罩先于缩放和 25 FPS 重采样、一对一匹配与 AP。

## 2026-09-30——T-U18-002 正式 Bepro GT 转换

- 状态：通过
- 端点和环境：本地 `ballspot-viz`；输入为 U18 四段视频和 8 份 `*_イベント.xml`。
- 输出：`artifacts/u18_ground_truth/20260930_u18_bepro_gt_v1/`。
- 结果：全量 Pass 1654、Drive proxy 1192；可评估 Pass 1651、Drive proxy 1191。排除项为 guard 起点 2 条、guard 终点 1 条、视频外 1 条；没有截断或移动 GT 时间。
- Drive 审查表共 50 条，四个半场分别为 13、13、12、12 条，初始状态全部为 `unreviewed`。

## 2026-09-30——T-U18-003 防标签泄漏代理烟雾测试

- 状态：通过
- 端点和环境：本地 `ballspot-viz`；FFmpeg/FFprobe 7.1.1。
- 输入：四个 U18 半场各自开头 12 秒；遮罩源坐标 `[0,925,920,155]` 后缩放至 1280×720，再重采样为 25 FPS CFR，无音频。
- 输出：`data/u18_inference_smoke_20260930_v2/`。
- 结果：四段代理均为 H.264 1280×720、25 FPS、300 帧/12.000 秒，逐段完整解码无错误；人工查看约 10 秒帧，确认底部事件/球员标签完全不可见，顶部比分和比赛时间保留，时间零点未裁剪。
- 限制：遮罩同时损失左下部分比赛画面，因此结果必须标记为 masked-video benchmark；仍应优先申请无叠加的干净 Veo 原片。

## 2026-09-30——T-U18-004 Windows CLI 帮助编码检查

- 状态：通过（记录一次修复前失败）
- 端点和环境：本地 Windows PowerShell；终端代码页 CP932。
- 首次结果：GT 与评估脚本 `--help` 正常，代理脚本的两条中文参数说明触发 `UnicodeEncodeError`；不影响实际代理生成。
- 修复：把 `--video-id` 与 `--end-sec` 的帮助文本改为 ASCII 英文；三个新脚本随后均能以退出码 0 打印帮助。

## 2026-09-30——T-U18-005 Slurm 脚本静态语法检查

- 状态：通过（附一次本地 WSL 环境失败）
- 首次结果：Windows 系统 `bash.exe` 因 `Bash/Service/CreateInstance/E_ACCESSDENIED` 无法启动，未执行到脚本解析，属于本机 WSL 环境失败。
- 替代检查：使用 `C:\Program Files\Git\bin\bash.exe -n scripts/slurm/u18_inference.sh`，退出码为 0。
- 后续动作：代码同步到 `chiron` 后再用远端 Bash 复核，并以实际 `sbatch` 冒烟作业作为最终运行证据。

## 2026-09-30——T-U18-006 最终本地静态与回归检查

- 状态：通过（记录一次命令写法失败）
- 首次静态命令：`python -m py_compile scripts/*.py`；PowerShell 未展开通配符，Python 报 `[Errno 22] Invalid argument: 'scripts/*.py'`，未形成源码失败结论。
- 替代静态命令：`python -m compileall -q scripts tests`，退出码 0。
- 回归结果：`python -m pytest -q` 为 28 项全部通过；完整代理编码并行占用 CPU 时耗时约 57 秒。

## 2026-09-30——T-U18-007 首次远端 Slurm 冒烟启动

- 状态：失败；已定位并修复入口，待替代作业验证
- Git 提交：`a654379e6918ec39e1a85406b24d6594844368b9`
- 作业：`6857087`，`ballspot-u18`，90 秒、7-fold/TTA；分配到计算节点 `nevera`。
- 输入：`fc_tokyo_aomori_h1_25fps_masked.mp4`；本地/远端 SHA-256 均为 `4ac0f31b783d05194c8a57bfdc07172e8332f83c66bd5f75c0334fc3bc303c22`。
- 结果：作业 1 秒内 `FAILED`，`ExitCode=127:0`；stderr 为 `/work7/y_pan/anaconda3/bin/conda: cannot execute: required file not found`。模型、视频和 CUDA 尚未启动。
- 原因：该 `conda` 包装器 shebang 指向计算节点不可见的 `/home/y_pan/workspace7/anaconda3/bin/python`。
- 修复：U18 Slurm 入口改为直接调用同一环境的 `/work7/y_pan/anaconda3/envs/ballspot-infer/bin/python`；失败日志保留，不删除原作业记录。

## 2026-09-30——T-U18-008 Bepro Y 与摄像机距离方向检查

- 状态：通过
- 方法：从四个半场分别选取一条 `Y≈0` 和一条 `Y≈1` 的 Pass，共人工查看 8 个原视频动作时刻，并结合球/执行者所在触线侧判断。
- 结果：四段视频均一致显示 `Y≈0` 位于摄像机近侧、`Y≈1` 位于画面远侧；前后半场方向不翻转。
- 实现：GT 新增 `distance_band`，按 Y 三等分为 near/mid/far；评估器新增按类别和 GT band 的 Recall。预测没有空间坐标，因此不计算分带 Precision/AP。

## 2026-09-30——T-U18-009 空间版正式 GT 转换

- 状态：通过
- 输出：`artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/`。
- 结果：总量和排除项与 v1 完全一致；可评估 Pass 1651、Drive proxy 1191。分带为 Pass near/mid/far=`513/504/634`，Drive proxy near/mid/far=`358/342/491`，合计分别回到 1651/1191。
- 自动化回归：新增距离方向和 far Recall 断言后，完整 pytest 为 29 项全部通过。

## 2026-09-30——T-U18-010 修复后的远端 90 秒 7-fold 冒烟

- 状态：通过；替代失败作业 `6857087`
- Git 提交：`e857287cb4649db2006789e3737320474ccbda05`
- 作业：`6857091`，节点 `nevera`，RTX A6000，运行 5 分 47 秒，`COMPLETED`、`ExitCode=0:0`。
- 输入：`fc_tokyo_aomori_h1_25fps_masked.mp4`，SHA-256 `4ac0f31b783d05194c8a57bfdc07172e8332f83c66bd5f75c0334fc3bc303c22`，请求 0～90 秒。
- 输出：`scores.npz` 为 137,803 字节、SHA-256 `2fa9c3323a86b5af0680294773ac012741f209229683422b82ce4dcf4e67b14e`；shape 为 `[2217,7,2]`，集成 shape `[2217,2]`，预测覆盖 1.32～89.96 秒，7 folds 与 horizontal flip TTA 均启用。
- 后续动作：已提交同一代理的完整半场作业 `6857094`；完成后将前 90 秒原始分数与本冒烟逐值比较，作为确定性和区间一致性检查。

## 2026-10-01——T-U18-011 四个完整 masked 推理代理

- 状态：通过
- 端点和环境：本地 `ballspot-viz`；FFmpeg/FFprobe 7.1.1；输出 `data/u18_inference_20260930_masked_v1/`。
- 结果：四段代理均为 H.264、1280×720、25 FPS CFR、无音频，并逐段完成从首帧到末帧的全片解码，四个 FFmpeg 进程退出码均为 0。
- FC Tokyo/Aomori H1：69,156 帧、2766.24 秒、1,425,564,262 字节，SHA-256 `4ac0f31b783d05194c8a57bfdc07172e8332f83c66bd5f75c0334fc3bc303c22`。
- FC Tokyo/Aomori H2：75,946 帧、3037.84 秒、1,467,274,970 字节，SHA-256 `0fc3fcd7b5cf735af02148f0e6e3f0734e8dbc3103e0c5b5ad12cd6673998b73`。
- Urawa/Ryutsu H1：67,924 帧、2716.96 秒、1,164,835,724 字节，SHA-256 `b3b7b89720024d9fca7a43de92f0c423db2c2ce865e161f59385fb564ed3bee2`。
- Urawa/Ryutsu H2：77,353 帧、3094.12 秒、1,053,342,825 字节，SHA-256 `ce431fa12ea7fbd91f410c44884542fb151899056963241326b9dfa6e02030cf`。
- 远端传输：四段视频及逐视频 YAML 已传到 `chiron`，远端 `sha256sum` 与上述本地 manifest 全部一致。

## 2026-10-01——T-U18-012 首个完整半场远端推理

- 状态：通过
- Git 提交：`e857287cb4649db2006789e3737320474ccbda05`
- 作业：`6857094`，节点 `nevera`，RTX A6000，manifest 状态 `completed`，模型计时 8529.67 秒。
- 输入：FC Tokyo/Aomori H1 完整 masked 代理，SHA-256 `4ac0f31b783d05194c8a57bfdc07172e8332f83c66bd5f75c0334fc3bc303c22`，请求 0～2766.233333 秒。
- 输出：`scores.npz` 为 69,090×7×2 fold 分数和 69,090×2 集成分数，预测覆盖 1.32～2764.88 秒；7 folds、水平翻转 TTA 和模型权重哈希均写入 manifest。
- 待补检查：全部推理结束并取回分数后，将本完整运行前 90 秒与作业 `6857091` 逐值比较。

## 2026-10-01——T-U18-013 其余完整半场 Slurm 提交

- 状态：一次失败后已纠正；替代任务运行中
- 失败作业：`6857205`。Windows PowerShell 在发送 SSH 命令前把双引号中的 `$PWD` 展开为本地 `C:\Code\Ball_action_spotting`，远端收到无效路径后以 `ExitCode=2:0`、0 秒失败；模型和视频未启动，也未生成正式输出。
- 修复：改用显式 `/work7/y_pan/Code_repo/Ball_action_spotting/...` 绝对路径；runbook 已增加 PowerShell 防误用说明。
- 替代作业：FC Tokyo/Aomori H2=`6857206`、Urawa/Ryutsu H1=`6857207`、Urawa/Ryutsu H2=`6857208`；提交后均进入 `RUNNING`，分别使用已核验哈希的完整代理。

## 2026-10-01——T-U18-014 完整推理前 90 秒确定性对比与首场后处理

- 状态：通过（记录一次检查命令键名错误）
- 首次检查失败：比较脚本误用不存在的 NPZ 键 `times_sec`；实际键为 `time_sec`。该错误只中止只读比较，未修改分数或产物。
- 确定性结果：作业 `6857091` 的 2,217 个冒烟时间点与完整作业 `6857094` 的前 2,217 个时间点，在 `frame_indexes`、`time_sec`、`fold_ids`、全部 `fold_scores` 和 `ensemble_scores` 上逐值完全一致；分数最大绝对差为 0，最后时间均为 89.96 秒。
- 后处理：以 `gauss_sigma=3`、`min_height=0`、`min_distance_frames=15` 处理 FC Tokyo/Aomori H1 完整分数，输出 `artifacts/u18_predictions/20261001_u18_zero_shot_masked_v1/fc_tokyo_aomori_h1/`。
- 结果：保留 2,910 个局部峰供 AP 排序，其中 Pass 1,479、Drive 1,431；输入原始分数 SHA-256 为 `e08b899c4cdf1a119610c47cd72aea9a94d8afeaadfd2d5d0f1de01e5cac9bf7`。
