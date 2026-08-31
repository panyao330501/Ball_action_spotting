# Ball Action Spotting 项目指令

## 项目目标

建立一套可复现的概念验证（PoC）流程：针对首次开球后约 10 分钟的视频检测 `Pass` 和 `Drive`，模型推理在 `chiron` 服务器执行，可视化视频在本地 Windows 机器生成。本阶段主要进行无 GT 的主观审查，判断模型在目标视频上的实际效果并识别明显失败模式。

## 项目拓扑

- 本地工作区：`C:\Code\Ball_action_spotting`
- 本地输入视频：`C:\Code\Ball_action_spotting\vs_飛鳥FC_20260704_trimmed_0930.mp4`
- 本地环境管理器：位于 `C:\ProgramData\miniconda3` 的 Conda
- 本地职责：视频检查、适合在本机执行的事件后处理、叠加渲染、集锦生成和主观质检
- 推理主机：SSH 别名 `chiron`
- 已验证的远端身份：`y_pan@chiron`
- 远端工作区：`/work7/y_pan/Code_repo/Ball_action_spotting/`
- 已验证的远端算力：8 张 NVIDIA RTX A6000，每张约 48 GB
- 远端职责：模型环境、权重保存、GPU 推理和原始预测生成
- 源代码同步：GitHub 仅同步代码、配置和文档
- GitHub 远端：`https://github.com/panyao330501/Ball_action_spotting.git`
- 大文件：视频、权重、特征和生成产物不得提交到 GitHub，必须单独传输并校验哈希

严禁打印、复制或提交 SSH 私钥、访问令牌、密码或仓库凭证。

## 当前执行状态

- 当前步骤：`01_project_bootstrap_and_environment`
- 当前步骤计划：`docs/plans/01_project_bootstrap_and_environment.md`
- 已完成部分：
  - 已创建项目文档结构。
  - 已确认本地输入视频存在。
  - 已定位本地 Conda 安装位置。
  - 已验证到 `chiron` 的 SSH 连接。
  - 已验证远端项目目录和 GPU 清单。
  - 已创建适合 GitHub 的忽略规则。
  - 已将现有项目文档统一为中文。
  - 已初始化本地 Git 仓库并绑定 GitHub 远端。
  - 已验证源 MP4 被 `.gitignore` 排除。
- 未完成部分：
  - 远端目录已存在但为空，尚未成为 Git 仓库。
  - 尚未完成文档基线的首次提交、推送和远端检出验证。
  - 尚未创建和测试本地可视化 Conda 环境。
  - 远端非交互和登录 Shell 尚未发现 Conda，需要定位或安装。
  - 尚未完成视频的本地到远端传输和校验和比对。
  - 尚未获取模型代码和预训练权重。

当前步骤发生变化，或未完成事项被完成、新增、删除时，必须更新本节。

## 工作规则

1. 开始任务前，必须阅读本文件、当前步骤计划、总体计划，以及 `docs/milestone.md` 和 `docs/testing/test_log.md` 的最新记录。
2. 遵循 `docs/plans/overall_plan.md`。只有项目范围、架构、阶段顺序、交付物或验收标准发生实质变化时才修改总体计划。
3. 详细执行状态写入当前步骤计划，不写入总体计划。
4. 每个新实施步骤都在 `docs/plans/` 下建立编号文件，命名格式为 `<NN>_<step_name>.md`。
5. 完成一个步骤后，在 `docs/milestone.md` 追加事实记录，更新本文件的当前状态，并创建或激活下一步骤计划。
6. 每次有意义的测试都必须追加到 `docs/testing/test_log.md`，失败测试也不能省略。没有命令输出或人工检查证据，不得声称测试通过。
7. 只有检查过路径和参数后，才把可复用命令写入 `docs/runbooks/commands.md`。尚未执行的命令必须明确标记为“模板”。
8. 影响架构、数据契约、模型选择或评估方式的决定必须记录到 `docs/decisions/decision_log.md`。
9. 标签、时间戳、预测结构和产物目录必须符合 `docs/data/label_and_artifact_contract.md`。
10. 两端可复现的 Python 环境均使用 Conda 管理。禁止把项目依赖安装到 Conda `base` 环境。
11. 脚本和非交互命令优先使用 `conda run -n <env>`。默认本地环境名为 `ballspot-viz`，远端环境名为 `ballspot-infer`，除非决策日志明确变更。
12. GitHub 仅同步代码、配置和文档。输入 MP4、权重、抽帧、预测或渲染视频不得通过 Git 传输。
13. 不允许本地和远端独立修改同一个源文件。应在修改端提交并推送，再在另一端拉取。
14. 阈值处理前必须保留原始模型分数，以便调整可视化阈值时无需重新执行推理。
15. `OFFSCREEN` 区间属于输入不可观测，不自动视为模型漏检。除非确实加入空间模型，否则不得暗示空间定位能力或绘制检测框。
16. 保留原始视频不变。派生媒体必须写入被 Git 忽略的产物或输出目录。
17. 工作文档正文使用中文；命令、路径、代码标识、标准标签和字段名保留其原始精确拼写。

## 文档地图

| 路径 | 内容 | 维护要求 |
| --- | --- | --- |
| `AGENTS.md` | 项目拓扑、工作规则、文档地图、当前步骤和未完成工作 | 项目拓扑、规则、当前步骤或待办状态变化时维护 |
| `README.md` | 面向项目成员的入口和工作流摘要 | 设置方式、入口或交付物变化时维护 |
| `docs/plans/overall_plan.md` | 稳定的端到端实施计划和阶段退出标准 | 仅在计划发生实质变化时修改，不作为进度日志 |
| `docs/plans/01_project_bootstrap_and_environment.md` | 仓库、Conda、SSH 和资产准备的详细计划与清单 | 步骤 01 活动期间持续维护；完成后冻结，事实纠错除外 |
| `docs/milestone.md` | 已完成工作和重大项目变化的追加式记录 | 完成步骤、重要交付物或重大变化后追加 |
| `docs/testing/test_strategy.md` | 测试层级、质量门槛、验收标准和证据要求 | 架构、接口或验收标准变化时维护 |
| `docs/testing/test_log.md` | 测试命令、环境、结果和产物引用的时间顺序记录 | 每次有意义的测试后追加，不得静默改写历史结果 |
| `docs/runbooks/commands.md` | 本地、SSH、GitHub 同步、传输、推理、可视化和验证命令 | 命令或路径变化时维护；必须区分模板与已验证命令 |
| `docs/decisions/decision_log.md` | 架构和工作流决策、理由及影响 | 形成或推翻重要决策时追加或声明替代关系 |
| `docs/data/label_and_artifact_contract.md` | 标签语义、时间基准、可见性、事件结构和产物布局 | 结构或标签定义变化时维护；破坏性变化必须升级版本 |
| `.gitignore` | 防止大媒体、权重、输出、环境和密钥进入 Git | 新增生成文件或敏感路径时维护 |

新增工作文档时，必须在同一次修改中把它加入本地图。
