# Ball Action Spotting 概念验证

本仓库用于建立一套可复现的足球 `Pass` / `Drive` 动作定位概念验证流程。

计算任务分工如下：

- `chiron`：GPU 模型推理和原始分数生成。
- 本地 Windows 工作站：可视化、事件集锦生成和主观审查。
- GitHub：仅同步源代码、配置、测试和文档。

开始工作前依次阅读：

1. `AGENTS.md`：当前状态和工作规则。
2. `docs/plans/overall_plan.md`：稳定的总体实施计划。
3. `docs/plans/07_u18_ground_truth_evaluation.md`：当前活动步骤。
4. `docs/runbooks/commands.md`：可使用的命令模式。

输入视频、模型权重、预测结果和生成视频均被有意排除在 Git 之外。

当前步骤还提供两项本地 CPU 工具：

- `scripts/generate_miss_candidates.py`：从保留的全程稠密分数生成低阈值/fold 分歧漏检候选，可选融合标准化 tracking 候选。
- `scripts/render_miss_candidate_highlights.py`：把候选合并为按优先级排列的人工审查集锦，并在右上角显示可与候选 `event` 时间直接对照的动态源视频时间。

候选仅用于安排人工确认，不是 GT 或正式 Recall 结果。

U18 有 GT 评估新增以下入口：

- `scripts/prepare_u18_ground_truth.py`：只读取 Bepro `*_イベント.xml`，按半场时间基准导出全量/可评估 GT 和 Drive 映射审查表。
- `scripts/prepare_u18_inference_proxies.py`：在拿到干净 Veo 原片前，遮住原视频底部 Bepro 动作标签，并生成 25 FPS 推理代理与逐视频配置。
- `scripts/slurm/u18_inference.sh`：在 `chiron` 上提交单个 U18 半场的 7-fold/TTA GPU 推理。
- `scripts/evaluate_u18_predictions.py`：按视频、类别和时间容差进行一对一匹配，输出 AP、Recall、Precision、F1 和错例表。

`パス(受け手)` 到 `Drive` 的映射仍需人工语义审查，因此当前 Drive GT 及其指标必须标为 provisional proxy。原 Veo 视频包含动作文字叠加，masked 代理只用于防泄漏回退基准；无叠加的干净 Veo 原片仍是首选。

Conda 环境定义：

- `environment-viz.yml`：本地视频检查、可视化和测试环境。
- `environment-infer.yml`：`chiron` 上的 GPU 推理环境。
