# Ball Action Spotting 概念验证

本仓库用于建立一套可复现的足球 `Pass` / `Drive` 动作定位概念验证流程。

计算任务分工如下：

- `chiron`：GPU 模型推理和原始分数生成。
- 本地 Windows 工作站：可视化、事件集锦生成和主观审查。
- GitHub：仅同步源代码、配置、测试和文档。

开始工作前依次阅读：

1. `AGENTS.md`：当前状态和工作规则。
2. `docs/plans/overall_plan.md`：稳定的总体实施计划。
3. `docs/plans/01_project_bootstrap_and_environment.md`：当前活动步骤。
4. `docs/runbooks/commands.md`：可使用的命令模式。

输入视频、模型权重、预测结果和生成视频均被有意排除在 Git 之外。

Conda 环境定义：

- `environment-viz.yml`：本地视频检查、可视化和测试环境。
- `environment-infer.yml`：`chiron` 上的 GPU 推理环境。
