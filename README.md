# Ball Action Spotting 概念验证

本仓库用于建立一套可复现的足球 `Pass` / `Drive` 动作定位概念验证流程。

计算任务分工如下：

- `chiron`：GPU 模型推理和原始分数生成。
- 本地 Windows 工作站：可视化、事件集锦生成和主观审查。
- GitHub：仅同步源代码、配置、测试和文档。

开始工作前依次阅读：

1. `AGENTS.md`：当前状态和工作规则。
2. `docs/plans/overall_plan.md`：稳定的总体实施计划。
3. `docs/plans/08_u18_match_heldout_pass_improvement.md`：当前活动步骤；已完成的零样本基线见步骤 07。
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
- `scripts/freeze_u18_pass_cv.py`：冻结两场比赛互换训练/测试角色的 Pass GT 与零样本基线；`scripts/train_u18_pass_reranker.py` 在本地对现有 Pass 峰值做探索性分数重排，`scripts/verify_u18_pass_cv.py` 复算留出比较。该重排不改变原 BAS 网络权重。
- `scripts/curate_u18_eval_review.py`：从固定阈值的一对一匹配表中选出分半场的 Pass FP、far FN 与 TP 参照，生成待人工复核的时间窗口清单。
- `scripts/curate_u18_pass_training_review.py`：避开已有 28 条审查，每半场另选 4 条高分未匹配 Pass 预测及 4 条远侧漏检，生成只供训练标签核对的 32 条清单。新判断只允许进入该场担任训练集的那轮实验，不改冻结测试 GT。
- `scripts/prepare_u18_pass_training_labels.py`：把完成的人工审查转换为按整场隔离的 Pass 训练标签、时间校正和接球代理负例避让；`scripts/train_u18_pass_head.py` 经 Slurm 只更新原 fold 0 的 Pass 分类行。`scripts/verify_u18_pass_head_training.py`、`scripts/verify_u18_pass_head_inference.py` 核查训练样本和留出原始分数，`scripts/compare_u18_pass_head.py` 生成同容量比较与逐事件匹配表。
- `scripts/render_u18_eval_review.py`：把 28 条 Pass 错例和 50 条接球语义样本生成为两个可切换的本地审查页面；`scripts/serve_u18_eval_review.py` 提供支持视频快进的回环地址服务。
- `scripts/curate_u18_candidate_frames.py`：从两场比赛的 Bepro Pass/接球事件生成以后半场为主的多样化候选帧、三联预览、时间/帧号 CSV 和可勾选的本地图集；`scripts/verify_u18_candidate_frames.py` 验证生成产物。
- `scripts/render_u18_frame_review.py`：为既有候选生成前后各 5 秒的遮挡片段，并把图集升级成单列大画面、可逐帧确认源帧号的审查页面；`scripts/verify_u18_frame_review.py` 检查片段和源视频帧对齐。
- `scripts/package_u18_selected_frames.py`：把人工导出的确认帧号重新对应到原始视频，生成 100 张图片与便携 CSV 的共享 ZIP；`scripts/verify_u18_selected_frames.py` 逐图与审查片段核对并检查 ZIP。

50 条人工语义审查已否定全量 `パス(受け手)` 到 `Drive` 的无条件映射，因此原 Drive proxy 指标仅作历史诊断。原 Veo 视频包含动作文字叠加，masked 代理只用于防泄漏回退基准；无叠加的干净 Veo 原片仍是首选。

四半场固定零样本 masked 基线的数值结果和待审入口见 `docs/reports/u18_bas_evaluation_20261109.md`。原始分数、预测和指标都位于被 Git 忽略的 `artifacts/`；人工复核前，匹配表中的 FP/FN 不能视为已确认的视觉错误。

在本机双击 `review_u18_pass.cmd` 即可打开审查网页，顶部可在 28 条 Pass 错例和 50 条接球→Drive 语义样本间切换。两项任务分别自动保存选择到当前浏览器；点击「保存到项目」会在 `artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_exports/` 写入带时间戳的新 CSV，不覆盖旧审查结果。也可下载 CSV 备份并在下次导入续审。浏览器关闭后在命令窗口按 `Ctrl+C` 停止本地服务。所有视频与审查状态留在本机，不上传到外部网站。

32 条新训练标签样本已由用户审完。版本化结果与旧 28 条审核合并为 `artifacts/u18_pass_cv/20261117_training_labels_v2/`，按整场比赛分别提供训练 Pass、暂排除事件、时间校正、待核补标及接球代理负例避让时间。17 条视觉确认有 Pass 的程序 FP 仍需精确定位，不自动加标；冻结测试 GT 不变。首版 v1 的负例未避开接球代理，只保留诊断。原审查网页 `review_u18_pass_training.cmd` 可供复查。

双向单 fold 分类头适配和同片段复评已完成：浦和测试 AP@1s 0.185→0.192、Recall 0.013→0.120；FC 东京测试 AP 0.451→0.453、Recall 0.674→0.836，但 Precision 0.439→0.325。结果主要表现为固定阈值下检出数增加，AP 改变很小；完整样本数、容差、近远侧和代表错例见 `docs/reports/u18_pass_head_comparison_20261117.md`。两场都已被查看，故仅作探索性验证。

下一轮只需先核对 5 条高优先级视觉 Pass FP 的事件身份和准确帧：双击 `review_u18_pass_identity.cmd` 打开本地遮挡片段页面。页面也可切换到全部 17 条，并导出 `u18_pass_identity_reviewed.csv`。最近 Bepro 事件只是时间提示，不能据此自动补标。

Conda 环境定义：

- `environment-viz.yml`：本地视频检查、可视化和测试环境。
- `environment-infer.yml`：`chiron` 上的 GPU 推理环境。
