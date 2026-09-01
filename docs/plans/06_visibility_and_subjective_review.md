# 步骤 06——可见性和主观审查

状态：进行中
开始日期：2026-09-01
前置步骤：`05_local_visualization_pipeline` 已完成
后续步骤：`07_conclusion_and_optional_gt`

## 目标

逐一审查 58 个 Pass / Drive 候选，并连续观看完整 566.5 秒区间，将模型预测行为与画面不可观测问题分开记录。该步骤是无 GT 的主观 PoC 审查，不计算或暗示正式准确率、召回率或 mAP。

## 固定输入

- 事件：`artifacts/inference/full_6835526/events.json`，Pass 34、Drive 24。
- 完整审查视频：`outputs/20260901_151037_2b29422_poc-video/annotated_full.mp4`。
- 事件集锦：`outputs/20260901_151037_2b29422_poc-video/event_highlights.mp4`。
- 渲染清单：`artifacts/visualization/20260901_151037_2b29422_poc-video/render_manifest.json`。
- 可见性和审查枚举遵循 `docs/data/label_and_artifact_contract.md`。

## 工作包

### 1. 审查记录初始化

- [ ] 从事件 JSON 生成 `artifacts/visualization/20260901_151037_2b29422_poc-video/review_notes.csv`，保留事件 ID、源时间、标签、置信度并增加人工可见性、审查状态和备注字段。
- [ ] 保证事件顺序、数量和身份与固定输入一致；未经人工检查不得自动把 `VISIBLE` 当作已确认值。
- [ ] 为连续观看发现的非候选问题建立独立记录，避免把可见漏检伪装成模型候选。

验收：审查表可追溯到 58 个输入候选，状态枚举合法，尚未审查的条目明确标记为 `unreviewed`。

### 2. 逐候选可见性与主观判定

- [ ] 观看每个事件前 3 秒、后 4 秒上下文，标记 `VISIBLE`、`PARTIAL` 或 `OFFSCREEN`。
- [ ] 对每个候选选择 `correct`、`wrong_label`、`timing_error`、`duplicate`、`false_positive`、`offscreen_unobservable` 或 `ambiguous`，必要时记录时间误差方向和定义歧义。
- [ ] 对 Pass 和 Drive 各保留代表性成功、失败与不可观测样例时间。

验收：58 个候选全部得到人工可见性和审查状态，不以低置信度自动代替人工结论。

### 3. 连续观看与明显漏检检查

- [ ] 连续观看完整区间，记录明显可见但没有相邻候选的 Pass / Drive，以及相机滞后、画面外或证据过小的区间。
- [ ] 将明显可见漏检与 `OFFSCREEN` 不可观测分开；无法可靠判断时使用歧义备注，不强行定性。
- [ ] 核对高置信度事件、成片误检、重复触发和系统性时间偏移是否存在。

验收：完成全程连续检查，并记录可复核的源时间码；主观遗漏记录不冒充完整 GT。

### 4. 主观汇总与步骤退出

- [ ] 汇总候选审查数量、可见性分布和各主观状态，但明确标注为无 GT 的样本内观察。
- [ ] 总结领域差异、足球过小、画外动作、标签定义和阈值造成的主要失败模式。
- [ ] 形成进入步骤 07 的事实依据：接受 PoC、调整后处理、申请 GT、微调或更换模型。

验收：审查记录完整，代表性样例和失败模式可由源时间复查，结论不超出当前无 GT 证据。
