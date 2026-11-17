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
- 只读日志聚合命令也曾因双引号中的远端循环变量 `$j` 被 PowerShell 预展开为空而未找到日志；随后改用三个明确日志路径检查，均已完成模型加载且没有 stderr 错误。

## 2026-10-01——T-U18-014 完整推理前 90 秒确定性对比与首场后处理

- 状态：通过（记录一次检查命令键名错误）
- 首次检查失败：比较脚本误用不存在的 NPZ 键 `times_sec`；实际键为 `time_sec`。该错误只中止只读比较，未修改分数或产物。
- 确定性结果：作业 `6857091` 的 2,217 个冒烟时间点与完整作业 `6857094` 的前 2,217 个时间点，在 `frame_indexes`、`time_sec`、`fold_ids`、全部 `fold_scores` 和 `ensemble_scores` 上逐值完全一致；分数最大绝对差为 0，最后时间均为 89.96 秒。
- 后处理：以 `gauss_sigma=3`、`min_height=0`、`min_distance_frames=15` 处理 FC Tokyo/Aomori H1 完整分数，输出 `artifacts/u18_predictions/20261001_u18_zero_shot_masked_v1/fc_tokyo_aomori_h1/`。
- 结果：保留 2,910 个局部峰供 AP 排序，其中 Pass 1,479、Drive 1,431；输入原始分数 SHA-256 为 `e08b899c4cdf1a119610c47cd72aea9a94d8afeaadfd2d5d0f1de01e5cac9bf7`。

## 2026-10-01——T-U18-015 首个半场评估管线诊断

- 状态：通过；仅为单半场临时诊断，不作为四半场正式结论
- 输入：FC Tokyo/Aomori H1 的 GT 907 条（Pass 498、Drive proxy 409）及 `min_height=0` 的 2,910 个候选；固定操作阈值 0.2。
- mAP：`±0.5s=0.1922`、`±1s=0.4321`、`±2s=0.6768`。
- `±1s`：Pass Precision/Recall/F1=`0.5387/0.3635/0.4341`；Drive proxy=`0.4831/0.3496/0.4057`。
- `±1s` 距离分带 Recall：Pass near/mid/far=`0.4706/0.3825/0.2626`；Drive proxy=`0.4196/0.4067/0.2381`。
- 观察：单半场中两类的 far Recall 均明显低于 near/mid，符合本步骤要验证的远侧失败假设；仍需四半场汇总及 Drive proxy 人工语义审查后才能形成正式结论。

## 2026-10-02——T-U18-016 Pass / reception 候选选帧与产物核验

- 状态：通过。
- 端点和环境：本地 Windows `ballspot-viz`；OpenCV 4.12.0；四段原始 30 FPS Veo 视频与 `20260930_u18_bepro_gt_spatial_v2` GT。
- 单元测试：`conda run -n ballspot-viz python -m pytest -q tests/test_curate_u18_candidate_frames.py`，3 项通过，覆盖两场/类别/后半场配额、原始 Bepro 接球语义、既有审查时刻排除及 30 FPS 帧索引定义。
- 生成命令：`conda run -n ballspot-viz python scripts/curate_u18_candidate_frames.py --output-dir artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1`，退出码 0。源视频大小与 SHA-256 均按配置再次校验。产生 120 张原尺寸遮挡帧、120 张三联预览和 120 行 `review.csv`，两场各 60、Pass/Reception 各 60、后半场 96；画面指纹额外跳过 3 个近似场景。
- 核验命令：`conda run -n ballspot-viz python scripts/verify_u18_candidate_frames.py artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1`，退出码 0；图片数量/尺寸/解码与遮挡区域、GT 对应关系、既有 50 条审查样本的 5 秒排除窗、帧号与事件时间均通过。最小同视频选中事件间隔 15.072 秒，最大帧时间偏差 0.016333 秒；3×3 球场分区计数为 12～14/区。
- 人工查看四个代表性三联预览（两场、前后半场），源画面、遮挡和前后顺序正常。球和触球是否清楚尚未逐张人工确认；候选不能直接当最终 100 帧。
- `node -e` 读取 `index.html` 的 `<script>` 并用 `vm.Script` 做语法解析，退出码 0；此项仅验证脚本语法，未代替浏览器交互检查。
- 图集随后增加勾选、确认帧号和备注的本地状态保存以及带两种时间码的 CSV 导出；从不变的 120 行 `review.csv` 重新生成 `index.html`。更新后再次运行完整 pytest：32 项通过；Node 脚本解析仍以退出码 0 通过。
- 尝试在 Codex 内置浏览器打开本地 `file://` 图集时，被 Browser Use URL 安全策略拒绝（只允许 `http:`/`https:`），未执行点击/导出交互。没有绕过限制；交互效果目前只经源码和语法检查，需用户在本机浏览器打开 HTML 后确认。

## 2026-10-02——T-U18-017 全量回归与并行 Conda 运行冲突

- 初次状态：运行环境失败。并行启动产物核验与 `conda run -n ballspot-viz python -m pytest -q` 时，后者报 Temp 下 `__conda_tmp_5152.txt` 被占用或未找到，未执行测试；前者独立以退出码 0 完成。
- 串行重试：再次单独运行 `conda run -n ballspot-viz python -m pytest -q`，退出码 0，32 项全部通过，耗时 5.38 秒。
- 结论：此环境下后续 `conda run` 串行执行；初次失败保留在测试记录中，不视为代码回归失败。

## 2026-10-02——T-U18-018 加长 U18 选帧片段和大画面图集

- 状态：媒体与静态页面检查通过；浏览器内播放/点击交互尚未由自动化执行。
- 烟雾命令：`conda run -n ballspot-viz python scripts/render_u18_frame_review.py --candidate-dir artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1 --limit 1`，退出码 0，首片段为 301 帧、30 FPS；片段中间帧与原候选帧缩放后的平均绝对像素差 1.805。
- 正式命令：同上但不传 `--limit`，退出码 0，120 个片段逐一通过 FFprobe 帧数、帧率、尺寸和时长检查。随后用修订后的页面代码复跑同命令，跳过并核验既有片段，更新 `clip_manifest.json` 和 `index.html`，原小图页面保存为 `index_small_v1.html`。片段总字节数 453,956,553，尺寸 1600×900，30 FPS，前后各 5 秒。
- 产物核验：`conda run -n ballspot-viz python scripts/verify_u18_frame_review.py artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1`，退出码 0；120 个片段和 SHA-256 对齐，跨四半场抽样 8 段的首/中/末共 24 帧与原视频对应帧比较，最大平均绝对像素差 2.351。
- 回归：`conda run -n ballspot-viz python -m pytest -q`，34 项通过。
- 首次 Node 页面检查命令中的正则表达式被 PowerShell 引号截断，`node -e` 在执行页面脚本解析前报 `Unterminated regexp literal`；改为独立的 `vm.Script` 解析和 PowerShell `Select-String` 卡片计数，均退出码 0，页面脚本语法通过且有 120 个片段按钮。此项不等同于浏览器内视频操作检查。
- 页面后来明确区分 GT 建议帧图片与人工确认帧号，增加确认帧范围验证和 `--gallery-only` 无媒体重编刷新；该命令退出码 0。刷新后的页面脚本再次通过 Node 解析，仍有 120 个片段按钮；完整 pytest 再跑为 34 项通过。

## 2026-10-06——T-U18-019 人工确认帧共享包

- 输入检查：最新人工导出 100 行，旧导出 23 行；100 个候选 ID、100 个“视频＋确认帧号”均唯一，100 个确认帧号非空，原视频路径全部存在。确认帧相对 GT 建议帧最大移动 126 帧（4.2 秒），因此必须重新提取图片。
- 生成：`conda run -n ballspot-viz python scripts/package_u18_selected_frames.py --selection 'C:\Users\logan\Downloads\u18_selected_frames (1).csv' --candidate-dir artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1 --output-dir artifacts/u18_selected_frames/20261006_u18_selected_frames_v1`，退出码 0，生成 100 张图片及 CSV/manifest/README/ZIP。
- 首次逐图核验失败于遮挡区最外边界的 JPEG 振铃：一张图片区域最大像素值 13，但区域均值 0.018、99 百分位 0、内部最大值 0。核验器改为检查遮挡内部后重跑，不改变任何图片。
- 最终核验：`conda run -n ballspot-viz python scripts/verify_u18_selected_frames.py artifacts/u18_selected_frames/20261006_u18_selected_frames_v1 artifacts/u18_frame_candidates/20261002_u18_frame_candidates_v1`，退出码 0；100 张图片哈希/解码/1920×1080/遮挡均通过，与对应审查片段所选帧的平均像素差均值 2.120、最大 2.614；ZIP 103 个成员 CRC 全部通过，大小 32,429,957 字节，SHA-256 `a2b8f899877b8da4611c5610744903b6e1717206fe8390ddffd68de27696fb70`。
- 回归：`conda run -n ballspot-viz python -m pytest -q` 退出码 0，34 项全部通过。三个 `conda run` 命令均出现本机 OpenCL `temp.txt` 清理提示，但 Python 主程序和返回码正常。
- 源视频复核：首次 PowerShell `foreach` 后直接接管道的哈希命令因语法错误退出 1，未执行哈希。改为按 CSV 中四个唯一视频文件名筛选 `U18/` 后运行 `Get-FileHash -Algorithm SHA256`，退出码 0；四段实际 SHA-256 与 `configs/u18_gt.yaml` 及 ZIP manifest 的对应值全部一致。

## 2026-10-06——T-U18-020 英文说明共享包重打包

- 生成脚本 README 模板及产物 `README.md` 改为英语。第一次尝试用 `conda run ... python -c` 执行多行重打包脚本时 Conda 参数包装报错，退出码 1；原 ZIP 未改变，也未产生临时包。改用同一 `ballspot-viz` 环境的 Python 可执行文件，以先写临时 ZIP 再替换正式 ZIP 的方式完成重打包，退出码 0。
- 检查：ZIP 内 README 与磁盘 README 字节一致，README 全部为 ASCII 英文；ZIP 共 103 个成员，`testzip()` 无 CRC 错误。`scripts/verify_u18_selected_frames.py` 再次退出码 0：100 行/100 张图片的哈希、尺寸、遮挡与审查片段对应关系均通过，最大平均像素差仍为 2.614。
- 新版 ZIP 大小 32,430,074 字节，SHA-256 为 `473562ced04cd66d5254d9e7607b186fef0caa98c415da82d8b2038fbd3eb387`；`selected_frames.csv` 与 100 张图片内容未改变。原日文视频文件名和 Bepro 代码保留为原始数据标识。
- 静态检查：`conda run -n ballspot-viz python -m py_compile scripts/package_u18_selected_frames.py` 退出码 0；`git diff --check` 退出码 0，仅提示 Git 将在下次处理时按配置转换行尾。

## 2026-11-09——T-U18-021 远端四半场状态与原始分数回收

- SSH `hostname; whoami; pwd` 退出码 0，身份为 `y_pan@chiron`。`sacct -j 6857094,6857206,6857207,6857208` 退出码 1，服务器返回 `Slurm accounting storage is disabled`；改查 `squeue` 和四份 `manifest.json`，旧作业均不在队列，四份清单均为 `completed` 且各有 `scores.npz`。
- `scp -r` 从 `/work7/y_pan/Code_repo/Ball_action_spotting/artifacts/inference/` 取回 FC 东京/青森山田 H2、浦和/流经大柏 H1/H2 三个目录，退出码 0；原 H1 保持不变。
- 远端与本地 SHA-256 逐文件一致。H2 东京：manifest `093a1e38288e0a9cb51b140285cebd76030c77de093a73eb3fdf18b8ba030c29`、scores `49eb65982dbdd256b455325ae69088a7aed6020b4b9cb7333ac72c24ffda0fae`；浦和 H1：`bfd84e55fa791ea7aeb5120b9c4ce13240a7bae16c5cfbb96d838fc5041c56cf`、`f9b787ed029040e187d6ce85103dbd926870a5ad6bff8e3c0cea40c1a963fcb6`；浦和 H2：`7b0517f6006a7198786ba670422fb8ee5c78116c96cead800aaca15571dcb47e`、`fbb41d12c6c58f7ec576e1c71b4cf2dbb936628ca36578e13da43c1ee8f807b7`。
- 使用本地 `ballspot-viz` Python 核验四份 manifest 的输入哈希/帧数与代理清单一致，`fold_scores` 形状分别为 `[69090,7,2]`、`[75880,7,2]`、`[67858,7,2]`、`[77287,7,2]`；全部分数有限，帧号连续，`time_sec=frame_indexes/25`，集成分数等于 fold 均值，退出码 0。

## 2026-11-09——T-U18-022 四半场后处理与 GT 评估

- 三个新半场依次运行 `conda run -n ballspot-viz python scripts/postprocess_scores.py`，参数 `--gauss-sigma 3 --min-height 0 --min-distance-frames 15`，每次退出码 0；产生 3132、2822、3196 个峰值，加原 H1 的 2910，共 12060。三个新运行的后处理清单均保存 manifest/原始分数 SHA-256。
- `conda run -n ballspot-viz python scripts/evaluate_u18_predictions.py --ground-truth artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/gt_events_evaluable.json --predictions-root artifacts/u18_predictions/20261001_u18_zero_shot_masked_v1 --output-dir artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1 --tolerances 0.5,1.0,2.0 --operating-threshold 0.2`，退出码 0。GT 2842、全部峰值 12060；Pass ±1s TP/FP/FN=322/375/1329，AP=0.339785；Drive proxy=219/286/972，AP=0.289323。首半场 Pass Recall=0.3635，与 2026-10-01 临时诊断一致。
- `conda run -n ballspot-viz python -m pytest -q tests/test_evaluate_u18_predictions.py`，3 项通过，退出码 0。上述 `conda run` 仍出现本机 OpenCL `temp.txt` 清理提示，但 Python 任务和退出码正常。
- 指标文件 SHA-256 `65923549b4b9079614df33d801202e289a28c72891472d06d1b3fe4e4e3b4a30`；完整匹配表 SHA-256 `702e33703f42e5320162becbc8ca49a4340c0de2b1a27d53d35fea9084ca7d02`。

## 2026-11-09——T-U18-023 Pass 代表样本审查表

- `conda run -n ballspot-viz python scripts/curate_u18_eval_review.py` 读取本轮 ±1 秒匹配表、可评估 GT 和代理清单，退出码 0，输出 `pass_review_cases.csv` 28 行；每个半场均为 FP 3、far FN 3、TP 1。
- PowerShell 逐行核验 28 个源视频路径存在，前后 5 秒审查窗口包含事件时间；分组计数符合预期，退出码 0。CSV SHA-256 `c85a66b1537d3735693e06775271df7a9bb81937d4b1f6d026f205bba06c53fe`。这些是待审时间匹配样本，未宣称视觉判断已通过。

## 2026-11-09——T-U18-024 最终静态与匹配一致性检查

- `conda run -n ballspot-viz python -m py_compile scripts/curate_u18_eval_review.py` 退出码 0；仅有本机 OpenCL `temp.txt` 清理提示。
- `git diff --check` 退出码 0，仅有 Git 现有 CRLF 转换提示；`git check-ignore` 确认正式指标 JSON 与原始 `scores.npz` 均被忽略。
- PowerShell 从 `metrics.json` 与 `matches_at_1s.csv` 独立核对 Pass TP=322、Drive proxy FN=972，退出码 0。

## 2026-11-11——T-U18-025 U18 审查网页输入与片段生成

- 开始前检查 `pass_review_cases.csv`：仍为 28 行、人工列全空，但 2026-11-10 被表格软件重存，显示时间码缩短到约 0.1 秒；`source_time_sec` 保留毫秒值。当前 CSV SHA-256 为 `a19392b0772d7d82f27c6f81600e70dc77d0a2b5f62aa0133598387371304aa4`，不同于 2026-11-09 的历史哈希；生成器以数值秒重新计算页面时间码，保留原文件不覆盖。
- `conda run -n ballspot-viz python scripts/render_u18_eval_review.py --review-csv artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/pass_review_cases.csv --proxy-manifest data/u18_inference_20260930_masked_v1/proxy_manifest.json --output-dir artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_site`，退出码 0；生成并逐段 FFprobe 验证 28 个 1280×720、25 FPS 片段，合计约 67.0 MB。先用独立 `review_site_smoke/` 的 `--limit 1` 运行，亦退出 0。
- 同生成器以 `--mode drive`、`--review-csv artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/drive_mapping_audit.csv`、`--output-dir artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/drive_review_site` 运行，退出码 0；生成并逐段验证 50 个片段，合计约 112.4 MB；独立 `drive_review_site_smoke/` 的首条烟雾亦退出 0。两轮均核对四段代理文件大小与 SHA-256。
- 使用 OpenCV 对两类样本各跨四半场抽一条，比对片段中心帧和 masked 代理对应帧：Pass MAE=1.637/1.306/1.568/1.442；Drive MAE=1.570/1.345/1.733/1.412，全部低于预设阈值 5。未更改输入代理和正式指标。

## 2026-11-11——T-U18-026 浏览器播放、导航和人工字段

- 本地服务先用普通 `python -m http.server` 预览，页面 HTTP 200，但浏览器报告视频 `seekable=[0,0]`，事件按钮无法真正跳帧；改用 `scripts/serve_u18_eval_review.py` 支持字节范围后，视频请求为 HTTP 206，`seekable=[0,10.04]`，事件附近实际播放位置约 5.001 秒。该失败与修复均在浏览器中观察，旧的临时服务已停止。
- 浏览器检查 Pass 页 28 行、初始进度 0/28、初始浦和样本和毫秒时间码；点击可见性/判断、填写备注后进度为 1/28，重新加载仍保留；导出 CSV 在本机下载目录得到 28 行，选中行值与页面一致；导入该 CSV 后恢复 1/28。随后通过页面清空测试判断，重载确认 0/28；测试导出经内容核对后非破坏性移入 `review_site_smoke/ui_test_export.csv`。
- 浏览器检查 Drive 页 50 行、初始进度 0/50、事件视频位置约 5.001 秒、顶部任务切换与接球观察/映射选项；填写测试判断后为 1/50，清空后重载为 0/50。Drive 的浏览器「下载 CSV」按钮曾显示已导出提示，但本机下载目录没有观察到对应文件；因此增加更可靠的本地版本化保存入口，未把该次点击记作下载成功。

## 2026-11-11——T-U18-027 本地保存、测试与启动入口

- `review_u18_pass.cmd` 实际启动两页本地服务；Pass 与 Drive 页面均返回 HTTP 200，Drive 视频 `Range: bytes=0-1023` 返回 206 和 1024 字节。服务只绑定 `127.0.0.1`，测试结束后 `Ctrl+C` 退出并确认端口不可访问。
- 浏览器分别点击两页「保存到项目」，服务返回两个不同的 `review_exports/` 版本化路径；磁盘读取确认 Pass 28 行、Drive 50 行且全为未审状态。两份空白测试文件随后移动到各自 smoke 目录，正式 `review_exports/` 不含测试提交。
- 新增单元测试覆盖 25 FPS 片段边界、表格软件缩短时间码后的恢复、Drive 字段保留、视频 HTTP 206/416 和 Pass/Drive 本地版本化保存。首次 `conda run ... pytest` 遇到 Windows `cp932` 无法输出失败报告而退出 1；直接调用同一 `ballspot-viz` 环境 Python 显示一项测试因 `Path.read_text` 自动换行转换而失败，该测试已改用原始字节比较并在 `finally` 关闭测试服务。最终 `conda run -n ballspot-viz python -m pytest -q tests/test_render_u18_eval_review.py tests/test_serve_u18_eval_review.py` 为 6 项通过、退出码 0。

## 2026-11-12——T-U18-028 用户 Drive 审查导出身份与完整性检查

- PowerShell `Get-FileHash -Algorithm SHA256`：用户 `C:\Users\logan\Downloads\drive_mapping_audit_reviewed.csv` 与项目 `artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_exports/drive_review_20261111T071120Z_762f04b5.csv` 哈希同为 `9DFA2862B93918C8C16BA7DFC009D0D4166E817BBE14E315274827F6AB41726A`。
- 首次 PowerShell `Import-Csv` 比对命令因输入笔误 `$_ .review_comment` 解析失败，退出码 1，未执行数据比较；更正为 `$_.review_comment` 后退出码 0。导出与原 `drive_mapping_audit.csv` 均为 50 行，导出 50 个 `event_id` 唯一且集合相同，所有非人工字段逐格相同，观察与映射列均无空值。
- `Import-Csv | Group-Object`：`review_mapping` 为 accept 23、reject 20、unclear 7；`review_observation` 为 carry_after_receive 23、control_only 4、one_touch_release 16、unclear 7；交叉表一一对应。14 条带备注，四个半场均出现 accept 与 reject；两个项目 Pass 保存版本均只有 14/28 条 `human_judgment` 已填。核验只读，未更改原 GT、预测或数值指标。
- 补充 PowerShell 核对：50 行审查字段全部非空；5 条 accept 的数值时间偏移备注均超过 1 秒；下载文件与项目保存文件哈希再次相同。`git diff --check` 退出码 0，仅有仓库已有的 CRLF 转换提示。

## 2026-11-12——T-U18-029 用户 Pass 审查导出身份、完整性和时间核对

- `Get-FileHash -Algorithm SHA256`：用户 `C:\Users\logan\Downloads\pass_review_cases_reviewed.csv` 与项目两份 `pass_review_20261112T052707Z_08fc5c65.csv`、`pass_review_20261112T052719Z_d989054d.csv` 均为 `2F751C94E13DA9EB8ADF55DBE8F3A37ED40BD29DF3C75B0B078B6A78788A8E33`；两份项目文件与下载文件均为 7861 字节。
- PowerShell `Import-Csv` 比对原 `pass_review_cases.csv`：28 行、28 个唯一 `review_id`，ID 集合完全相同；`human_visibility` 与 `human_judgment` 28 行均非空。非人工字段仅 `source_timecode` 有 28 处显示精度差异，其余逐格一致；导出时间码解析为秒后与未变的 `source_time_sec` 全部在 0.001 秒内一致。
- `Group-Object algorithmic_status,human_judgment`：FP 7“确有 Pass”/5“类别不符”；FN 9“确有 Pass”/3“时间偏移”；TP 3“确有 Pass”/1“类别不符”。`human_visibility` 为 VISIBLE 26、UNCLEAR 2。备注中 FP 类别不符为射门 1、解围 1、角球 3；TP 类别不符为角球 1；3 条 FN 时间偏移备注为 +1.60、+0.56、-0.55 秒。
- 首次用于找 7 条视觉 Pass FP 最近 GT 的 PowerShell `foreach` 管道命令因尾部空管道元素解析失败，退出码 1，未执行查询；改为先收集到 `$out` 后退出码 0。7 条各自最近的同半场可评估 Bepro Pass 时间差为 1.23、1.70、1.22、25.54、1.79、2.62、1.43 秒。该最近邻查询不验证是否同一次动作，仅供后续定向复核。全程未更改原 GT、预测和固定协议指标。
- 更新项目状态及报告后执行 `git diff --check`，退出码 0，仅有既有 LF→CRLF 提示。

## 2026-11-12——T-U18-030 低可见性与偏移备注只读复核

- PowerShell `Import-Csv` 重新读取用户导出的 Pass/Drive 文件：`u18-review-025` 与 `u18-review-026` 均为程序 FN、`human_visibility=UNCLEAR`、`human_judgment=确有 Pass`；`u18-review-028` 为程序 TP、人工“类别不符”、备注“角球”。用户口头确认 025 的 Pass 确实存在但画面极模糊，没有修改审查 CSV。
- Drive 文件中以“正负号＋带两位小数的秒数”形式筛出的数值偏移备注共 7 条：accept 5（-1.50、+1.75、+1.88、-1.26、-1.06 秒），reject 2（+1.07、+0.89 秒）。本次只核对备注和更新解释，不改动原 Bepro GT、模型分数或固定协议指标。

## 2026-11-12——T-U18-031 Pass 人工判断修订版验证

- 修订前用 PowerShell `Get-FileHash -Algorithm SHA256` 核对项目源审查版本与用户下载导出哈希完全相同；确认 28 行且唯一目标 `u18-review-028` 的原值为程序 TP、人工“类别不符”、备注“角球”。在 `review_exports/` 新建版本化 CSV，不覆盖原文件或下载导出。
- PowerShell `Import-Csv` 对比修订前后两版：均为 28 行，完整人工判断 28/28；差异严格为 `u18-review-028:human_judgment` 从“类别不符”到“确有 Pass”和 `human_comment` 从“角球”到“角球后的一次传球（用户复核）”，共 2 个单元格。新文件 SHA-256 为 `1520550C1F14C9C468A7678D5C901933BAF4DC4669181B0A09A9BCF1F9BD87EF`；交叉表为 FN 时间偏移 3/FN 确有 Pass 9/FP 确有 Pass 7/FP 类别不符 5/TP 确有 Pass 4。
- `git check-ignore -v` 确认修订 CSV 被 `/artifacts/` 排除；`git diff --check` 退出码 0，只有现有 LF→CRLF 提示。

## 2026-11-12——T-U18-032 双向整场留出冻结与 Pass 分数重排

- `conda run -n ballspot-viz python scripts/freeze_u18_pass_cv.py --output-dir artifacts/u18_pass_cv/20261112_frozen_v1` 退出 0：先核对 GT、代理清单和原基线 SHA-256，再检验四个代理文件大小与两场互斥分组；输出 A→B 训练/测试 GT 874/777 和 B→A 777/874，以及每轮 JSON 哈希。重算 ±1s 零样本基线：A→B AP 0.256107、TP/FP/FN 31/74/746；B→A AP 0.407898、291/301/583。
- 首次运行 `train_u18_pass_reranker.py` 退出 1：将平滑后的候选置信度误认为 NPZ 原始逐帧分数。检查后明确分别使用平滑候选分数与原始帧分数两个特征；固定四特征、训练比赛专用标签与阈值规则。`20261112_reranker_v1` 和 `v2` 为开发产物，正式探索结果为 `v3`。
- `conda run -n ballspot-viz python scripts/train_u18_pass_reranker.py --frozen-dir artifacts/u18_pass_cv/20261112_frozen_v1 --output-dir artifacts/u18_pass_cv/20261112_reranker_v3` 退出 0：A→B AP/P/R 0.258/0.389/0.036；B→A 0.420/0.526/0.372。测试事件保存原平滑分数和重排分数，`comparison.json` 保存两轮模型系数、原始 NPZ 哈希和分组。
- 首次 `conda run ... verify_u18_pass_cv.py` 因 Windows cp932 无法打印中文输出而退出 1，没有得到验证结论；设置 `PYTHONIOENCODING=utf-8` 后相同验证命令退出 0。两轮均通过训练/测试视频隔离、冻结 GT 和结果哈希、模型系数复算测试分数、三档容差 AP/P/R/F1 和 TP/FP/FN 复算。Conda 激活期间另有 `Access is denied`/OpenCL 临时文件提示，但运行退出码为 0，且已检查上述输出。直接调用环境 Python 的一次验证会话长时间无输出，经 Ctrl+C 停止，未计为通过。
- 同一 `ballspot-viz` 环境 Python 对三个新增脚本执行 `-m py_compile`，退出 0；`git diff --check` 退出 0，仅有既有 LF→CRLF 警告；`git check-ignore -v` 确认冻结分组与重排模型结果被 `/artifacts/` 排除，不会作为代码提交。
- 更新步骤、决策、报告和 README 后再次执行 `git diff --check`，退出 0；只报告既有 LF→CRLF 提示。读取 `comparison.json` 确认两个 fold 各只用一场训练、另一场测试，GT 分别 777/874。

## 2026-11-16——T-U18-033 Pass 训练标签定向审查清单与本地网页

- 首次本机默认沙箱的 `exec_command` 连续报 `registered runtime ownership is missing`，未改文件；按运行时规则改用受审的 `require_escalated` 后只读检查成功。仓库根目录无 `.codegraph/`，因此直接读取相关脚本和计划。
- `conda run -n ballspot-viz python scripts/curate_u18_pass_training_review.py` 按运行手册所列输入正式运行，退出 0；四半场各 8 条。PowerShell `Import-Csv` 独立核验总计 32 条、每半场 FP 4/FN 4、review_id 无重复、与已审 28 条及本批同半场样本都相隔至少 10 秒，32 条人工判断均为空。新 CSV SHA-256 为 `43af659d3347dd7148d2d1b56a8a12ff4411569e0cc6ee9f21042106459600d9`；选择清单记录匹配表、GT、旧审查、代理清单与四段原始预测的哈希。
- `render_u18_eval_review.py` 运行退出 0，逐条打印 `verified clip 1/32` 至 `32/32`；独立网页和 32 条片段位于 `artifacts/u18_pass_cv/20261116_training_review_v1/review_site/`。生成器先核对四段 masked 代理 SHA-256，再检查每段 25 FPS/帧数并保存片段哈希。页面前端更新后运行 `--page-only` 退出 0，逐片重验哈希并刷新复制的 JS，未重编视频。
- 临时启动 `serve_u18_eval_review.py --site-dir artifacts/u18_pass_cv/20261116_training_review_v1 --page review_site/index.html --port 8766`；`Invoke-WebRequest` 得页面 HTTP 200，页面含 `u18-train-001` 和 `u18-train-032`；首段视频 `Range: bytes=0-1023` 返回 HTTP 206、1024 字节及正确的 `Content-Range`。以 Ctrl+C 停止后访问端口失败，确认测试服务已关闭。尚未把网页人工填写或实际视觉判断记为完成。
- 新 Python 脚本的 `py_compile`、`node --check web/u18_eval_review/app.js` 和 `git diff --check` 均退出 0；`git check-ignore -v` 确认 CSV 与网页产物被 `/artifacts/` 排除。首次定向 pytest 因 Conda 的 cp932 输出错误退出 1；设置 UTF-8 后显示 1 项通过、5 项在默认 `C:\Users\logan\AppData\Local\Temp\pytest-of-logan` 因 `WinError 5` 权限错误而未执行。先确认项目内新 `pytest_tmp_first` 目录不存在，再用 `-p no:cacheprovider --basetemp artifacts/u18_pass_cv/20261116_training_review_v1/pytest_tmp_first` 重跑，6 项通过、退出 0。
- 文档更新后最终 `git diff --check` 退出 0，仅有既有 LF→CRLF 提示。PowerShell `Get-FileHash` 确认生成网页中的 `app.js` 与源码完全一致，并读到新的 `u18_pass_training_reviewed.csv` 下载名；一键启动脚本存在，审查 CSV 仍为 32 行。工作树原有多项未提交改动均保留，未提交或覆盖其他文件。

## 2026-11-16——T-U18-034 Pass 与 Receive 代理指标 Excel 导出

- 从已冻结的 `artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/metrics.json` 提取 Pass 与历史 `Drive` 接球代理的 GT 数、全部峰值、±0.5/1/2 秒 AP，以及 ±1 秒阈值 0.2 的 P/R/F1 和 TP/FP/FN；构建器断言 Pass 1651/322/375/1329、接球代理 1191/219/286/972。Artifact Tool 表格检查显示两行与原 JSON 完全一致，公式错误扫描为 0 条。
- `workbook.render` 生成预览，人工检查标题、数字和“Receive 仅是代理”说明均完整可读。首次构建命令虽显示文件已保存但进程退出码为 1；随后用 bundled Python 的 `openpyxl` 只读加载并以 `zipfile.testzip()` 验证 XLSX 完整性，核对两行关键单元格及代理限制说明，退出码 0。首次只读检查因 Windows cp932 中文输出失败，设置 `PYTHONIOENCODING=utf-8` 后重试通过。
- 交付文件为 `outputs/01a1bf4b-2962-7880-a996-887db6fc8189/u18_bas_pass_receive_summary.xlsx`，SHA-256 为 `39B067D5B45B95E53222D975EF09C35A8E282C756292A587A40EB986FB3D4B92`；`/outputs/` 已被 `.gitignore` 排除。

## 2026-11-17——T-U18-035 32 条人工审查及隔离训练标签

- `Get-FileHash -Algorithm SHA256`：用户下载 `C:\Users\logan\Downloads\u18_pass_training_reviewed.csv` 与项目 `review_exports/pass_review_20261117T071006Z_ccd3a14b.csv`、`pass_review_20261117T071007Z_e59265ea.csv` 完全相同，均为 `ECAA945DCCA36665A2FE9DB87B8C0998AFCCB71303CDA7F7477F4904EE6BF07F`。逐行核对原 `training_review.csv`：32 个唯一 ID 全部匹配，非人工字段相同，可见性与人工判断 32/32 非空。
- `conda run -n ballspot-viz python scripts/prepare_u18_pass_training_labels.py ... --output-dir artifacts/u18_pass_cv/20261117_training_labels_v1` 退出 0：A→B 原训练 GT 874、保留 872、排除 2、校正 8、待核补标 13；B→A 777、773、4、5、4。输出清单固定输入/输出哈希。
- `conda run -n ballspot-viz python scripts/verify_u18_pass_training_labels.py --training-dir artifacts/u18_pass_cv/20261117_training_labels_v1 --frozen-dir artifacts/u18_pass_cv/20261112_frozen_v1` 退出 0：重算冻结及输出哈希、训练/测试视频互斥、原 GT ID 守恒，两个方向均打印 `isolation OK`。Conda 伴随已有 OpenCL 临时文件提示，但脚本退出码为 0。
- 首次 `py_compile` 对新训练脚本退出 1，原因为 `enumerate` 的生成器表达式未加括号；修复后相同 `py_compile` 对四个脚本退出 0。`git diff --cached --check` 退出 0。

## 2026-11-17——T-U18-036 Slurm Pass 分类头冒烟及远端传输

- 代码提交 `d7e6f0e` 经 GitHub 推送，并在 `chiron` 干净工作区 `git pull --ff-only` 到同一提交；只有代码进 Git。训练标签 JSON 通过 `scp -r` 独立传输，远端 Python 重算两轮所有输出 SHA-256 与本地 `manifest.json` 一致，远端训练/推理脚本 `py_compile` 退出 0。
- 首个 Slurm 冒烟 `6930736` 失败：远端已有四段代理视频，但缺 `proxy_manifest.json`。通过 `scp` 单独传清单，远端 `sha256sum` 为 `e78853cf46c3e7455bc402f674206a991adf2e7ea4423df0c3b07e1aec1962b3`，与冻结配置一致。
- 重试 Slurm `6930737` 输出 4 正/4 负、30 epoch，最终训练损失 0.654141，生成权重 SHA-256 `cfeb7c6077a73419fa4bdf66a0805045d4be5140d222950f93f0d3ea8b73387b`。远端 CPU `torch.load` 比较初始与新权重：`nn_state_dict` 和 `no_ema_nn_state_dict` 均仅 `classifier.weight`、`classifier.bias` 字段变化，其中 Drive 行逐元素相同，Pass 行不同；退出 0。`sacct` 因集群关闭 accounting storage 而退出 1，故本条以完整作业日志、产物和权重读回为证据。
- 两轮完整训练经 Slurm 提交为 `6930738`、`6930739`，提交时均显示 `RUNNING`，不可在完成前报告训练或测试性能。
- 既有四段原始七折分数以新增 `--fold-index 0` 和固定 `sigma=3`、`min-height=0`、最短峰距 15 帧另生成单 fold 对照峰值。四段后处理退出 0，Pass 峰值分别 1545、1605、1548、1696；输入 NPZ 哈希及所用 `fold_scores[:, 0, :]` 已记录在各 `postprocess_manifest.json`。尚待与完整训练模型作同片段指标对照。

## 2026-11-17——T-U18-037 接球代理避让与第二版 Slurm 训练

- 首版正式训练作业 `6930738`、`6930739` 各生成一份模型，正负例分别 872/872 和 773/773；远端 CPU 逐项对比仅 Pass 分类头一行变化，权重 SHA-256 分别 `b6846068feb11ea2199a3b27bbbd62a39598e94b19eedaf58b93ba041104a1d7`、`a246dca24672be492dc9d2194f42616287cb81f59032b5842114668cfd514f93`。后续发现首版负例未避开接球代理，首版模型降为诊断，不据此声称改善。
- `conda run -n ballspot-viz python scripts/prepare_u18_pass_training_labels.py ... --output-dir artifacts/u18_pass_cv/20261117_training_labels_v2` 退出 0；保留 v1 相同的 872/773 Pass 和 2/4 排除、8/5 校正、13/4 待核补标，另逐训练比赛输出 656/535 条接球代理避让记录。`verify_u18_pass_training_labels.py` 对 v2 退出 0，原冻结 GT 哈希、文件哈希、比赛隔离及计数均通过。远端单独传输后重算 v2 所有输出 SHA-256 与清单一致。
- 修订脚本 `py_compile` 退出 0；经 GitHub 提交 `15325f4`、`694a831` 同步到远端。第二版 Slurm 冒烟 `6930747` 生成 4 正/4 负权重，日志显示 `drive_proxy_events_avoided=656`；第二版正式训练作业 `6930748`、`6930749` 已提交，待结果验证。
- 远端登录节点仅用 CPU 调用新版 `select_examples`，按固定种子重建两个方向的 1744/1546 个窗口，分别包含 872/773 个负例；逐负例与该轮所有已知训练 Pass、排除 Bepro Pass、待核补标预测及接球代理时间求最近距离，最小为 3.003/3.001 秒，均严格大于 3 秒，退出 0。此检查不保证未标注的 Drive 不落在负例里。
- 从四段原始七折 NPZ 重算 fold 0 单模型固定阈值 0.2、±1 秒基线：浦和留出 777 GT、3244 峰，AP 0.184671、P 0.227273、R 0.012870、TP/FP/FN 10/34/767；FC 东京留出 874 GT、3150 峰，AP 0.450637、P 0.438570、R 0.673913、TP/FP/FN 589/754/285。此值是与分类头微调同容量的原模型对照，不替代七折基线。

## 2026-11-17——T-U18-038 第二版训练权重与采样窗口验证

- Slurm `6930748`/`6930749` 日志均完整输出 30 epoch 与模型清单，正式正负例 872/872、773/773，最终训练损失分别 0.647237、1.082724。远端 CPU `torch.load` 与原 fold 0 权重逐张量比较：两个模型的 `nn_state_dict` 和 `no_ema_nn_state_dict` 均只有 `classifier.weight`、`classifier.bias` 字段变化，Drive 行逐元素一致；新权重 SHA-256 分别 `d1e79c0a5f1dddd7a77add589bf013ddf6386d30ad7adab9ade3758e691f6740`、`0f8ed23dea7c7edc8a02df802f65d507c51214e78f108157fe18fd75d60486fb`，与模型清单一致，退出 0。
- 通过 `scp` 单独取回两个正式模型 `manifest.json` 与 `training_examples.json`；`conda run -n ballspot-viz python scripts/verify_u18_pass_head_training.py --labels-root artifacts/u18_pass_cv/20261117_training_labels_v2 --models-root artifacts/u18_pass_cv/20261117_pass_head_models_v2` 退出 0，验证清单哈希、所有正例 ID/25 FPS 帧号、训练测试视频互斥及负例与所有训练比赛已知 Pass/待核 Pass/接球代理的最短间距 3.003/3.001 秒。Conda 的既有 OpenCL 临时文件提示不影响退出码。
- 四段第二版留出推理通过 Slurm 作业 `6930750`～`6930753` 提交，提交后均为 `RUNNING`；结果尚待完整分数/代理 SHA-256 及本地复评。

## 2026-11-17——T-U18-039 首版诊断推理与本地比较流水线冒烟

- 首版四段 Slurm 推理 `6930743`～`6930746` 均生成 `completed` 原始分数与清单；通过 `scp -r` 单独取回。`verify_u18_pass_head_inference.py --experiment-suffix v1` 退出 0：四段分别 67858、77287、69090、75880 帧，连续 25 FPS 时间轴、单 fold 两类分数、masked 视频哈希、模型权重哈希和 TTA 均正确；原始 NPZ SHA-256 分别 `1909d4e089193340f8e796ec0118648ee7d9e85e26e63d4ffe3bef358799bb93`、`8a8ce9c981c606ae68f9112f23486a98b71e250338345c28e9dfaa81397b006e`、`7069205af0414c29c4bb48abf1dd6dac4b21ea249679c8a902cc72b4b911dd44`、`e0fff444e2d9f9077e583ea00ae59c9bd13f25b766ad813a35d51695c879a2b7`。
- 四段 `postprocess_scores.py --min-height 0.0` 均退出 0，得到 Pass 峰值 1587、1738、1568、1640。`compare_u18_pass_head.py --experiment-suffix v1` 退出 0，验证两轮测试比赛、原始分数哈希、同样后处理与模型清单并生成逐事件匹配表；首版 AP@1s 为 0.185→0.192、0.451→0.453，P/R 分别 0.227/0.013→0.252/0.120 和 0.439/0.674→0.325/0.836。**首版采样未避开接球代理，只作为流水线诊断和误差来源记录，不作为最终模型效果。**第二版结果仍待完成。

## 2026-11-17——T-U18-040 第二版原始分数、同片段评估与错例核对

- 第二版 Slurm 推理 `6930750`～`6930753` 四段完整完成；`scp -r` 单独取回原始 NPZ 与 manifest。远端 `sha256sum` 与本地 `Get-FileHash` 四段逐个一致：浦和 H1 `61f94b08aa08545bd0b9926b749a15dd2bf6fe701933f5f6712f565d4962f526`、H2 `3e1cc0b9b66e3b0638fe8a42b0b763ce7bcea84750ee8c0802bd760b2be8f736`，FC 东京 H1 `1ddda8384f1e00bba5401a3cdaca7175ec6be688fd1071ac8edb47255d6bc94b`、H2 `e298f65f1e81dbec5500a28ab064c311117e9e2ec47f3b0630cce85abb5ebee9`。
- `conda run -n ballspot-viz python scripts/verify_u18_pass_head_inference.py --inference-root artifacts/u18_pass_cv/20261117_pass_head_inference_v2 --models-root artifacts/u18_pass_cv/20261117_pass_head_models_v2 --proxy-manifest data/u18_inference_20260930_masked_v1/proxy_manifest.json --experiment-suffix v2` 退出 0：四段分别 67858、77287、69090、75880 个连续 25 FPS 预测帧；验证 masked 代理哈希、1 fold×2 类原始分数、有限概率、集成等于单 fold、TTA 和权重哈希。
- 四段 `postprocess_scores.py --min-height 0.0` 退出 0，使用与基线相同 `sigma=3`、最短峰距 15 帧，得到 Pass 峰值 1587、1738、1568、1640。`compare_u18_pass_head.py --experiment-suffix v2` 退出 0，重新核对冻结测试 GT、模型清单、代理和分数 SHA-256，并输出 `20261117_head_comparison_v2/comparison.json` 及两轮基线/适配逐事件匹配 CSV。独立 PowerShell `Import-Csv` 对每轮 TP/FP/FN 计数与 JSON 一致，四个匹配 CSV SHA-256 均与比较清单一致。
- ±1 秒、阈值 0.2：浦和留出 777 GT、原 fold 0 3244 峰/44 个操作预测、AP 0.184671、TP/FP/FN 10/34/767、P/R 0.227273/0.012870；适配 3325 峰/369 预测、AP 0.192281、93/276/684、P/R 0.252033/0.119691，near 6/253→52/253、far 2/325→25/325。FC 东京留出 874 GT、原 fold 0 3150 峰/1343 预测、AP 0.450637、589/754/285、P/R 0.438570/0.673913；适配 3208 峰/2252 预测、AP 0.453014、731/1521/143、P/R 0.324600/0.836384，near 182/260→224/260、far 222/309→268/309。±0.5/2 秒 AP 和完整指标见比较 JSON。Conda 的既有 OpenCL 临时文件提示没有改变退出码。
- 用固定种子在远端 CPU 复算 v1/v2 负例：FC 东京训练轮替换 195 个负例，其中 v1 有 54 个处于接球代理 ±3 秒；浦和训练轮替换 148 个，其中 v1 有 56 个处于接球代理 ±3 秒。v1/v2 的 ±1 秒 TP/FP/FN 相同、AP 仅在小数后多位有差异；第二版仍是语义上更保守的正式输入。人工已审 `u18-train-013` 为改进后 TP，`u18-train-031` 仍 FN；`u18-train-027` 的人工“角球”附近 0.04 秒有适配 Pass 峰约 0.855。后者是时间邻近观察，不能证明同一脚动作。

## 2026-11-17——T-U18-041 待补 Pass 身份复核页面与片段验证

- 首次 `prepare_u18_pass_identity_queue.py` 输出 `20261117_pending_pass_identity_v1` 的 17 行 CSV，5 条最近 Bepro Pass 时间差超过 3 秒；随后扩充片段起始时间、哈希、逐帧页面和 JSON，另建 v2，不覆盖 v1。`conda run -n ballspot-viz python -m py_compile scripts/prepare_u18_pass_identity_queue.py` 与 v2 生成命令均退出 0；输入旧/新审查和冻结 GT SHA-256 在 manifest 固定，v2 CSV SHA-256 `7a0314ae65dc9201ef1c6389afda9103df7d802f9436fe2ef171f073c9dd83a7`。
- 独立 PowerShell 核验 v2 的 CSV/JSON 各 17 行、5 条 P1、17 条人工输出字段均为空，17 个原遮挡片段均存在且生成器重算 SHA-256 与原片段清单一致；`identity_review.csv`、`review_data.json`、`index.html` 的 SHA-256 均与新 manifest 一致。提取网页内 JavaScript 后 `node --check` 退出 0。
- 用 `serve_u18_eval_review.py --site-dir . --page artifacts/u18_pass_cv/20261117_pending_pass_identity_v2/index.html --port 8767` 临时启动本地服务，`Invoke-WebRequest` 页面 HTTP 200、JSON HTTP 200、片段 `Range: bytes=0-1023` HTTP 206 且恰 1024 字节。实际 IAB 浏览器显示默认 5 条、首条最近 GT 信息、视频与半场秒/帧号；点击“下一条”后 ID 与最近 GT 更新到下一条。测试后 Ctrl+C 停服务；一次 2 秒超时的 HTTP 结束检查因异常类型不匹配退出 1，随后 `Get-NetTCPConnection -LocalPort 8767 -State Listen` 显示 0 个监听，确认已停止。未填写任何用户审核答案。
