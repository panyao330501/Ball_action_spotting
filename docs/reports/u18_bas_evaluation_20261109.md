# U18 BAS 零样本评估报告（基线 2026-11-09，人工审查至 2026-11-12）

## 范围与口径

- 两场 U18 比赛、四个半场；Bepro `*_イベント.xml` 共 8 份。可评估 GT：`Pass=1651`，`Drive proxy=1191`。
- 使用固定的 2023 SoccerNet BAS 7-fold 权重与水平翻转 TTA；输入为遮挡 Bepro 动作文字的 25 FPS 视频。未使用 U18 GT 训练或调整本轮模型、遮罩、峰值参数或操作阈值。
- 稠密集成分数经 `gauss_sigma=3`、`min_height=0`、`min_distance_frames=15` 生成全部局部峰；AP 使用置信度排序和同视频、同类别的一对一时间匹配。操作点为 `confidence>=0.2`。
- `±0.5/1/2s` 容差以预测和 GT 动作时间差定义。结果是本项目评估器的事件 AP，不宣称与 SoccerNet 官方工具逐字节相同。
- `パス(受け手)`→`Drive` 是原始 receiver proxy 假设。2026-11-12 核验用户完成的 50 条审查后，该整体映射未获支持；以下 Drive 数字仅保留为接球代理的历史诊断，不能解释为真正 Drive 能力。原片有动作文字，遮罩会损失左下方视野；当前结果仅属于 masked 基准。

## 四半场汇总

| 类别 | GT | 全部峰值 | AP ±0.5s | AP ±1s | AP ±2s | ±1s Precision | ±1s Recall | ±1s F1 | ±1s TP/FP/FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pass | 1651 | 6188 | 0.151 | 0.340 | 0.538 | 0.462 | 0.195 | 0.274 | 322/375/1329 |
| Drive receiver proxy（历史诊断） | 1191 | 5872 | 0.113 | 0.289 | 0.440 | 0.434 | 0.184 | 0.258 | 219/286/972 |

Pass 的 ±1s TP 绝对时间误差中位数为 0.384s、P90 为 0.835s。Drive receiver proxy 分别为 0.439s、0.831s。原计算还给出两类平均 mAP 0.132、0.315、0.489（依次对应 ±0.5/1/2s）；因 Drive GT 映射未获支持，这些 mAP 不应作为 BAS 的正式综合表现引用。

## 2026-11-12 Drive 接球映射人工审查

- 用户导出的 `C:\Users\logan\Downloads\drive_mapping_audit_reviewed.csv` 与项目内 `artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_exports/drive_review_20261111T071120Z_762f04b5.csv` SHA-256 完全相同：`9dfa2862b93918c8c16ba7dfc009d0d4166e817bbe14e315274827f6ab41726a`。50 行事件 ID 唯一且与原审查表完全一致；非人工字段逐格一致；50 行均有观察和映射判断。
- 判断为 `accept` 23/50（46%）、`reject` 20/50（40%）、`unclear` 7/50（14%）。在 43 条明确可判的样本中，23 条接受（53.5%）。观察分布为接球后带球 23、仅停球/控球 4、直接传出/解围 16、看不清 7。四个半场各有 accept 与 reject。
- 抽样器按半场分配数量，再按 Bepro Y 坐标排序等距选取；这是覆盖近远侧的系统抽样，不能把 46% 当作 1191 条总体的精确比例，也不能计算无偏总体准确率。人工审查的是 Bepro 接球标签与 BAS Drive 的**语义映射**，不是逐条给模型预测打对错。
- 14 条有备注；其中 7 条给出数值时间偏移，5 条 `accept` 的偏移绝对值超过 1 秒（-1.50、+1.75、+1.88、-1.26、-1.06 秒），另 2 条 `reject` 为 +1.07、+0.89 秒。用户确认这些是人工观察的动作时间偏移；它们提示接球代理即便语义可用，也可能不满足 ±1 秒时间匹配，但备注未经过逐帧时间校准，不直接改写 GT。两条 `unclear` 备注写“根本没有接球动作”及“不存在传球和drive”，宜回看后确认是否改为 `reject`；在用户复核前保留原判断。
- 结论：整体 `パス(受け手)`→`Drive` 映射不能作为可信 GT。历史 receiver proxy 数值和原始输入均保留，不回写或删改；若要报告正式 Drive 指标，需要另建覆盖完整评估范围且经语义/时间复核的 Drive GT。仅使用这 50 条中的 23 条 accept 会造成选择偏差，不能代表全体 Drive 性能。

## 2026-11-12 Pass 代表错例人工审查

- 用户原导出 `C:\Users\logan\Downloads\pass_review_cases_reviewed.csv` 与项目内 `review_exports/pass_review_20261112T052707Z_08fc5c65.csv`、`pass_review_20261112T052719Z_d989054d.csv` SHA-256 相同：`2f751c94e13da9eb8adf55dbe8f3a37ed40bd29df3c75b0b078b6a78788a8e33`。用户随后更正 `u18-review-028` 为角球后的一次 Pass，当前修订版为 `review_exports/pass_review_20261112T054717Z_028_corrected.csv`，SHA-256 `1520550c1f14c9c468a7678d5c901933baf4dcc4669181b0a09a9bcf1f9bd87ef`。两版均保留；修订版相对原导出只改 `human_judgment` 与 `human_comment` 两格。28 行 `review_id` 唯一且与原表完全一致，人工可见性与判断均已填写。非人工字段除 `source_timecode` 外逐格一致；网页将原表被表格软件缩短的 28 个显示时间码恢复为毫秒精度，均与未变的 `source_time_sec` 相符。
- 按当前修订版：程序 `FP` 12 条，人工“确有 Pass”7、“类别不符”5（射门 1、解围 1、角球 3）；程序 `FN` 12 条，人工“确有 Pass”9、“时间偏移”3，偏移备注为 +1.60、+0.56、-0.55 秒；程序 `TP` 4 条均为人工“确有 Pass”。可见性为 `VISIBLE` 26、`UNCLEAR` 2。用户补充说明 `u18-review-025` 虽画面极模糊，但仔细观察可确认 Pass：低可见性与确认动作存在可以并存；不把它计为清晰可见漏检。`u18-review-026` 也属低可见性，尚无类似补充说明。
- 7 条“FP 但画面确有 Pass”均标 `VISIBLE`。在同半场可评估 Bepro Pass 中寻找最近 GT，6 条时间差为 1.22～2.62 秒，另一条为 25.54 秒；这仅提示需核查标注时间或缺失事件，不证明最近 GT 就是画面里的同一次传球。程序 FP 表示固定阈值 0.2、±1 秒一对一匹配失败；人工确认某处有 Pass 也不自动把它变成 TP。
- 样本是每半场 3 条最高分 FP、3 条分散的远侧 FN 与 1 条 TP 参照，经过特意挑选；这些 28 条的人工比例不能外推为全部 1651 条 Pass GT 或全部模型预测的视觉错误率，也不据此重算 AP、Precision、Recall。浦和两个半场抽样出现类别不符（尤其角球/解围），但样本还不足以解释全半场低召回的主因。
- 后续只有在需要严格可见漏检计数时才补看 `u18-review-026`；`u18-review-025` 与 `u18-review-028` 已由用户澄清。3 条 Pass 时间偏移可在下一轮标注规则核对中处理；用户若修订，应另存新版本。原始预测、Bepro GT 和既有固定协议指标不回写。

## 分半场与距离

下表均为 Pass，操作阈值 0.2、容差 ±1s。far Recall 的分母仅由 GT 的 Bepro Y 坐标确定；预测没有空间位置，因此没有分带 Precision/AP。

| 半场 | Pass GT | 全部峰值 | AP | Precision | Recall | far Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FC 东京/青森山田 H1 | 498 | 1479 | 0.446 | 0.539 | 0.363 | 0.263 |
| FC 东京/青森山田 H2 | 376 | 1593 | 0.362 | 0.430 | 0.293 | 0.262 |
| 浦和/流经大柏 H1 | 417 | 1439 | 0.327 | 0.391 | 0.065 | 0.038 |
| 浦和/流经大柏 H2 | 360 | 1677 | 0.201 | 0.111 | 0.011 | 0.000 |

全四半场的 Pass near/mid/far GT 为 513/504/634，±1s Recall 为 0.222/0.240/0.137。浦和两个半场在阈值 0.2 以上的 Pass 峰值仅有 69 和 36 个，对应 FC 东京两个半场的 336 和 256 个。四段推理的输入哈希均与 masked 代理清单一致，原始分数形状、时间轴、7-fold 集成及后处理参数已核验；代表样本中有角球、解围及可见 Pass，但尚不能将全半场差异归因于镜头、可见性、事件时间或模型泛化中的任何单一因素。不要据此直接调阈值并在同一比赛上报告独立测试结果。

## 人工复核与下一步

- 完整一对一匹配结果：`artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/matches_at_1s.csv`。其中 `FP/FN` 是本评估协议下的匹配状态，尚不是人工确认的视觉错误。
- 精简 Pass 审查表：同目录 `pass_review_cases.csv`，每半场含 3 个高置信度 FP、3 个分散时段的远侧 FN、1 个 TP 参照，共 28 行；原表人工列保留空白，用户完成的独立导出见上节。
- 推荐本机双击仓库根目录 `review_u18_pass.cmd`：网页直接播放 28 条 Pass 遮挡视频，打开时定位到事件附近；可筛选浦和半场、逐帧看、自动保存草稿，完成后导出新的审查 CSV。顶部可切换到 50 条接球→Drive 语义审查页面，两项任务分别导出 CSV。网页是本地工具，不改变本轮指标。
- 审查时优先点击网页右上角「保存到项目」：两项任务各在 `artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/review_exports/` 生成版本化 CSV，浏览器「下载 CSV」作为备份。只有人工完成填写的版本才可用于后续分析。
- 审查时在 `human_visibility` 填 `VISIBLE`、`PARTIAL`、`OFFSCREEN` 或 `UNCLEAR`；在 `human_judgment` 简记“确有 Pass”“无 Pass”“时间偏移”“类别不符”或“无法判断”，并在 `human_comment` 写清实际动作时刻或遮挡原因。`algorithmic_status` 保留原值，不把人工判断反写为模型结果。
- Drive 语义审查已完成，详见上节。对外可报告 Pass 的固定协议零样本结果；Drive receiver proxy 的旧数值必须明确标为未验证 GT 的历史诊断，不作为正式 Drive 性能。
- Pass 28 条与 Drive 50 条代表样本均已审完，用户目前无需继续批量看视频。下一步先向教授报告固定协议 Pass 结果、代表错例的多种失败模式及 Drive 接球代理不能充当正式 GT 的结论；再把更广的浦和错例与 IKOMA 可见漏检对照，决定是否补标或以按比赛划分的 dev/test 设计做改进实验。若取得无 Bepro 文字的原始 Veo 视频，应新增 clean 基准，不覆盖本 masked 结果。

## 可复现产物

- 原始分数及推理清单：`artifacts/inference/u18_<video_id>_masked_v1/`，四半场均为 `completed`；三个新取回半场的远端和本地 SHA-256 完全一致。
- 零阈值事件：`artifacts/u18_predictions/20261001_u18_zero_shot_masked_v1/<video_id>/`，四半场合计 12060 个峰值。
- 指标与匹配表：`artifacts/u18_evaluation/20261109_u18_zero_shot_masked_v1/`；配置和时间/标签契约见 `configs/u18_gt.yaml` 与 `docs/data/label_and_artifact_contract.md`。
- 测试、命令和传输哈希记录见 `docs/testing/test_log.md` 与 `docs/runbooks/commands.md`。

## 2026-11-12 可向教授报告的 Pass 基线

当前应把 2023 SoccerNet BAS 七折权重在 U18 上的结果称为**零样本 Pass 基线**。两场比赛四个半场、1651 条可评估 Bepro Pass，25 FPS Bepro 文字遮挡输入，7-fold/水平翻转 TTA；全局同类同视频一对一时间匹配。在 `±1s` 和原先固定的 `confidence>=0.2` 下，697 个操作点 Pass 预测中 TP 322、FP 375，FN 1329；Precision 0.462、Recall 0.195、F1 0.274。使用全部 6188 个 Pass 峰值排序计算的 AP@1s 为 0.340，AP@0.5s 为 0.151，AP@2s 为 0.538。按 Bepro Y 定义的近/中/远侧 GT 数为 513/504/634，Recall 为 0.222/0.240/0.137；预测无空间坐标，不能报告各侧 Precision。上述是自动时间匹配指标，28 条人工审查样本揭示了时间偏移、缺标或类别混淆的可能，但不能直接修正全量数值。

由于没有新增比赛，后续改善实验将两场互换训练和测试角色，见 `docs/plans/08_u18_match_heldout_pass_improvement.md`。冻结基线在浦和作为留出测试时为 777 GT、AP@1s 0.256、P 0.295、R 0.040；FC 东京作为留出测试时为 874 GT、AP 0.408、P 0.492、R 0.333。训练、测试视频均为原来四个 masked 代理；两场此前都已在基线诊断中查看，因此这不是全新盲测。

第一轮 Pass 分数重排仅改候选排序和操作分数，未微调 BAS 网络；A→B 的 AP 0.258、P 0.389、R 0.036，B→A 的 AP 0.420、P 0.526、R 0.372。第一轮对浦和低召回没有改善，不能声称已解决项目问题。完整模型系数、阈值、两轮测试峰值、哈希和结果在 `artifacts/u18_pass_cv/20261112_reranker_v3/comparison.json`；该产物是探索性比较，不替代原零样本基线。
