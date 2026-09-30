# 步骤 06——可见性和主观审查

状态：保留进行中（人工审查未完成；当前优先执行步骤 07 的 U18 GT 评估）
开始日期：2026-09-01
前置步骤：`05_local_visualization_pipeline` 已完成
后续步骤：`07_u18_ground_truth_evaluation`（已因取得外部 U18/Bepro GT 而启动）

## 目标

逐一审查 58 个 Pass / Drive 候选，并连续观看完整 566.5 秒区间，将模型预测行为与画面不可观测问题分开记录。该步骤是无 GT 的主观 PoC 审查，不计算或暗示正式准确率、召回率或 mAP。

## 固定输入

- 事件：`artifacts/inference/full_6835526/events.json`，Pass 34、Drive 24。
- 完整审查视频：`outputs/20260902_151709_978ded7_poc-video-global-timeline-2px/ball_action_spotting_with_global_ bar.mp4`（由原 `annotated_full.mp4` 重命名；SHA-256 不变）。
- 事件集锦：`outputs/20260902_151709_978ded7_poc-video-global-timeline-2px/event_highlights.mp4`。
- 渲染清单：`artifacts/visualization/20260902_151709_978ded7_poc-video-global-timeline-2px/render_manifest.json`。
- 用户粗略审查记录：`BAS漏检.xlsx`，共 11 个较确定的远侧漏检种子（Pass 10、Drive 1）；文件被 Git 忽略且不视为穷举 GT。
- BAS-only 漏检候选：`artifacts/candidate_mining/20260929_153408_ee66a96_bas-miss-candidates-v2/`，199 个候选、36 个审查窗口。
- 漏检候选集锦：`outputs/20260930_141315_ee66a96_bas-miss-review-timecode-v2/miss_candidate_highlights.mp4`，436.3 秒；右上角动态显示当前源视频比赛时间。
- 可见性和审查枚举遵循 `docs/data/label_and_artifact_contract.md`。

## 工作包

### 1. 审查记录初始化

- [ ] 从事件 JSON 生成 `artifacts/visualization/20260902_151709_978ded7_poc-video-global-timeline-2px/review_notes.csv`，保留事件 ID、源时间、标签、置信度并增加人工可见性、审查状态和备注字段。
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

### 4. BAS-only 漏检候选和 tracking 预留接口

- [x] 从既有 `scores.npz` 联合 `ensemble_scores` 的低阈值局部峰值与 7-fold 分歧生成候选，不重新运行 GPU 推理。
- [x] 排除相同类别正式事件前后 1 秒内的候选，合并重叠上下文并按高、中、低优先级排序。
- [x] 将 `BAS漏检.xlsx` 规范化为 11 个种子时间点，只计算候选覆盖率，不把有限种子误称为 GT 或正式 Recall。
- [x] 预留标准化 tracking CSV/JSON 接口；tracking 缺失时 BAS-only 路径独立运行，当前运行清单明确记录 `tracking_status=not_provided`。
- [x] 生成正式候选 CSV/JSON、审查窗口 CSV/JSON、种子覆盖报告和 36 窗口审查集锦。
- [ ] 人工观看 36 个候选窗口，将真正漏检、非动作和歧义情况回填到候选表。

验收：候选可追溯到原始稠密分数与正式事件；tracking 缺失不阻塞；种子覆盖率只用于检查候选规则；候选集锦可定位回源时间。

完成记录：

- 正式候选运行生成 199 个候选（Pass 81、Drive 118），其中高优先级 76、中优先级 123；按上下文合并为 36 个窗口，预计审查时长 436.32 秒。
- 11 个远侧漏检种子中 6 个在同类前后 1 秒内得到候选覆盖，覆盖率为 54.5%；未覆盖的 5 个种子附近 BAS 分数很低，支持未来再引入改进后的 tracking 或模型特征。
- 正式修订集锦为 H.264 1280×720、30 FPS、13,089 帧/436.300 秒，含 AAC 音轨；每个窗口右上角逐帧显示 `SOURCE HH:MM:SS.mmm`，可直接与候选行固定 `event` 时间对照；36 个中间片段和完整解码均通过。

### 5. 主观汇总与步骤退出

- [ ] 汇总候选审查数量、可见性分布和各主观状态，但明确标注为无 GT 的样本内观察。
- [ ] 总结领域差异、足球过小、画外动作、标签定义和阈值造成的主要失败模式。
- [ ] 形成进入步骤 07 的事实依据：接受 PoC、调整后处理、申请 GT、微调或更换模型。

验收：审查记录完整，代表性样例和失败模式可由源时间复查，结论不超出当前无 GT 证据。

## 当前 tracking 状态

- 2026-09-29：现有 tracking 效果较差，当前不作为候选来源。Martin 计划先微调 tracking 模型后重新生成数据，预计需要较长时间。
- 候选生成器接受可选的标准化 tracking CSV/JSON；未提供文件时不会伪造 tracking 分数、远侧位置或空间能力。

## 对外共享材料

- 2026-09-16：已根据教授要求整理 `docs/reports/ikoma_bas_share_summary_20260916.md`，并按用户反馈精简为英文共享稿，供 Martin 和根木了解当前 IKOMA BAS 预测结果、模型及关键推理设置；可视化视频和预测标签保留 Google Drive URL 占位。
- 共享稿明确区分“模型候选”和“人工确认事件”，并注明 confidence 不是校准概率；在 GT 和逐事件主观审查完成前不报告 accuracy、precision、recall 或 mAP。
