# 标签和产物契约

版本：0.4 草案
破坏性变更必须升级版本，并在决策日志中记录。

## 1. 标签

初始 PoC 允许的模型事件标签：

- `Pass`
- `Drive`

显示文本可以增加中文解释，但存储标签必须保留标准拼写。

`Drive` 不自动等同于所有接球。在正式 GT 规则确定前，审查备注可以写“接球/控球定义有歧义”，但不得修改存储标签。

## 2. 时间基准

每个事件必须保留：

- `time_sec`：相对于原始源视频时间轴的浮点秒数。
- `timecode`：相对于源视频的 `HH:MM:SS.mmm` 格式时间。
- `frame_index`：可选；存在时指向已声明分析帧率的帧号。
- `inference_time_sec`：可选；相对于提取推理区间的时间。
- `kickoff_offset_sec`：保存在运行清单中，不允许每个事件重复保存不同值。

所有转换使用运行清单声明的时间基准。不得根据四舍五入后的显示字符串反推时间戳。

### 本次 PoC 的固定时间和帧率契约

- 源视频零点就是开球：`kickoff_offset_sec = 0.0`。
- 源区间为 `[0.0, 566.5]` 秒，含首帧、不再剪辑。
- 规范源为 30 FPS MP4；模型输入为全时长 25 FPS CFR 代理视频。
- 推理帧 `i` 的时间为 `i / 25.0` 秒，相对于源视频零点；渲染器直接使用该秒数定位原始视频。
- 代理视频保持 1280×720。模型内部居中补黑至 1280×736；该补边不改变时间轴。

## 3. 可见性状态

- `VISIBLE`：足球和相关动作证据充分出现在画面中。
- `PARTIAL`：证据位于画面边缘、被遮挡、过小或短暂消失。
- `OFFSCREEN`：动作可能发生在画面外，无法可靠判断。

`OFFSCREEN` 不表示模型预测正确，只表示视频不足以支持可靠判断。

## 4. 人工审查状态

- `unreviewed`：未审查
- `correct`：正确
- `wrong_label`：标签错误
- `timing_error`：时间误差
- `duplicate`：重复
- `false_positive`：误检
- `visible_miss`：可见漏检
- `offscreen_unobservable`：画外不可观测
- `ambiguous`：存在歧义

## 5. 事件记录

必填字段示例：

```json
{
  "event_id": "event-000001",
  "time_sec": 12.345,
  "timecode": "00:00:12.345",
  "label": "Pass",
  "confidence": 0.91,
  "visibility": "VISIBLE",
  "review_status": "unreviewed",
  "comment": ""
}
```

验证规则：

- `event_id` 在一次运行内唯一。
- `time_sec` 为有限非负数，按升序排列且位于配置区间内。
- `label` 只能取允许的标准标签。
- 概率转换后的 `confidence` 为 `[0, 1]` 内的有限数。
- `visibility` 和 `review_status` 只能使用声明值。
- JSON 和 CSV 必须描述同一组事件。

## 6. 稠密分数产物

远端推理结果必须保留足够信息，以便本地重复执行后处理：

- 源视频身份和 SHA-256
- 源视频及推理区间的时间基准
- 有序时间戳或帧号
- 两个标签的原始或校准分数
- 模型、权重、源代码提交和配置身份
- 预处理设置
- 软件环境和 GPU 身份

首选格式为压缩 NumPy 或 Parquet，并配套可读的 JSON 清单。最终格式在实现阶段确定并更新本文档。

## 7. 运行标识和目录

运行 ID 格式：

```text
YYYYMMDD_HHMMSS_<short-git-sha>_<config-name>
```

运行目录：

```text
artifacts/inference/<run_id>/
  manifest.json
  scores.<format>
  events.json
  events.csv
  inference.log

artifacts/visualization/<run_id>/
  render_manifest.json
  review_notes.csv
  visualization.log

outputs/<run_id>/
  annotated_full.mp4
  event_highlights.mp4
  poc_report.md
```

上述运行目录均被 Git 忽略，除非后续决策明确把小型、非敏感样例提升为测试夹具。

## 8. 漏检候选记录

漏检候选用于安排人工审查，不是模型正式预测，也不是 GT。候选可以由以下证据产生：

- `ensemble_low_peak`：集成分数低于正式阈值但形成局部峰值。
- `fold_disagreement`：至少一个 fold 形成较强峰值，但集成平均未形成正式事件。
- `tracking_change`：可选的标准化 tracking 候选。当前 tracking 不可用时不得填充或推测该证据。

候选至少保留：

- `candidate_id`、`time_sec`、`timecode`、`frame_index`
- `label` 和 `suggested_label`；只有 tracking 无类别候选可使用 `Unknown`，正式模型事件标签仍只能是 `Pass` / `Drive`
- `ensemble_score`、`fold_mean_score`、`fold_max_score`、`fold_std_score`、`folds_above_official`
- `evidence_sources`、`priority`、最近正式事件及时间差
- 可选 `tracking_score`、`far_side_score`、`tracking_confidence`、`tracking_reason`
- `review_status`、`human_label`、`corrected_time_sec`、`visibility` 和 `comment`

候选未审查时，`review_status=unreviewed`，`human_label`、`corrected_time_sec` 和 `visibility` 留空；不得自动写成 `VISIBLE`。人工审查后，`human_label` 可取 `Pass`、`Drive`、`No action` 或 `Ambiguous`。

### 标准化 tracking 候选接口

候选生成器接受可选 CSV 或 JSON 列表，字段如下：

| 字段 | 要求 |
| --- | --- |
| `time_sec` | 必填；与规范源视频零点一致 |
| `label` | 可空；允许 `Pass`、`Drive`、`Unknown`，空值按 `Unknown` |
| `tracking_score` | 必填；`[0, 1]` |
| `far_side_score` | 可空；`[0, 1]` |
| `tracking_confidence` | 可空；`[0, 1]` |
| `reason` | 可空；保留触发原因 |

该接口是 Martin 原始 tracking 输出之后的适配边界。原始 tracking 数据不得在字段语义未确认时直接接入。

### 候选运行目录

```text
artifacts/candidate_mining/<run_id>/
  manifest.json
  candidates.json
  candidates.csv
  review_windows.json
  review_windows.csv
  seed_coverage.json

artifacts/candidate_review/<run_id>/
  candidate_review_manifest.json
  candidate_review.log
  candidate_clips/

outputs/<run_id>/
  miss_candidate_highlights.mp4
```

候选集锦必须同时显示窗口源时间范围、逐帧变化的 `SOURCE HH:MM:SS.mmm` 和每条候选的固定 `event HH:MM:SS.mmm`。动态 `SOURCE` 时间按“窗口 `source_start_sec` + 当前片段 PTS”计算；集锦拼接后的累计播放时间不得冒充源视频时间。

## 9. U18 Bepro Ground Truth

U18 正式评估只读取每支球队、每个半场的一份 `*_イベント.xml`。`*_チーム.xml` 与 `*_選手.xml` 是相同事件的重排，禁止作为额外 GT 重复计数。

时间与边界：

- 动作时刻来自标签 `MATCH TIME`，不得使用 XML `start/end`；后者是约十秒审查窗口。
- 前半场 `source_time_sec = MATCH TIME`；后半场 `source_time_sec = MATCH TIME - 2700`。
- 视频外事件保留在全量 GT，但 `evaluation_status=excluded`，不得截到视频边界。
- 33 帧、步长 2、25 FPS 模型在首尾各使用 `1.32` 秒上下文 guard；guard 内 GT 不进入正式评估分母。

标签映射：

- Bepro `パス` 映射为 `Pass`，成功与失败均计入。
- Bepro `パス(受け手)` 在 2026-09-30 原版 GT 中暂映射为 `Drive`，`mapping_status=provisional_receiver_proxy`。2026-11-12 的 50 条人工审查（23 accept、20 reject、7 unclear）未支持全量映射；历史字段和指标只用于接球代理诊断，不得称为已验证的 `Drive` GT 或正式 Drive 性能。未来正式 Drive GT 应另建版本，不覆盖原始转换。
- `ドリブル突破`、`スペースへのドリブル` 不直接映射为本模型的 `Drive`。

每条 U18 GT 至少保留：`event_id`、`video_id`、`match_id`、`half`、`source_time_sec`、`match_time_sec`、`label`、`mapping_status`、原始 Bepro code、team/player、`x/y/to_x/to_y`、`distance_band`、pass result、`evaluation_status`、排除原因及源 XML/事件 ID。

2026-09-30 人工检查四个半场各一组 `Y≈0/Y≈1` 的极端事件后，确认 Bepro `Y≈0` 对应摄像机近侧、`Y≈1` 对应远侧。GT 使用 `[0, 1/3)`=`near`、`[1/3, 2/3)`=`mid`、`[2/3, 1]`=`far`。BAS 预测没有空间坐标，因此只允许按 GT band 报告 Recall；不得把无空间归属的误检用于伪造分带 Precision 或 AP。

原始 Veo 视频底部含 Bepro 动作标签，会向模型泄漏答案。推理输入必须使用无叠加原片，或在重采样前用不透明遮罩完整覆盖事件/球员标签区；masked 结果必须明确标记其视野损失，不得与 clean-video 基准混称。

U18 产物目录：

```text
artifacts/u18_ground_truth/<run_id>/
  manifest.json
  gt_events_all.json
  gt_events_all.csv
  gt_events_evaluable.json
  gt_events_evaluable.csv
  drive_mapping_audit.csv

artifacts/u18_evaluation/<run_id>/
  metrics.json
  matches_at_1s.csv
  pass_review_cases.csv
  review_site/
    index.html
    app.js
    style.css
    manifest.json
    clips/<review_id>.mp4
  drive_review_site/
    index.html
    app.js
    style.css
    manifest.json
    clips/<event_id>.mp4
  review_exports/
    pass_review_<utc_timestamp>_<id>.csv
    drive_review_<utc_timestamp>_<id>.csv
```

`pass_review_cases.csv` 是按 `matches_at_1s.csv` 选出的人工复核入口：每半场 3 条高置信度 Pass FP、3 条分散时间的 far Pass FN 和 1 条 TP 参照。`algorithmic_status` 只表示固定 ±1 秒、阈值 0.2 的时间匹配结果，不是已确认的视觉真假；人工可见性、判定和备注列必须保持空白直至审查。

新增的 `artifacts/u18_pass_cv/<run_id>/training_review.csv` 只用于训练标签核对，不能作为新的 GT 或模型性能统计。它沿用 Pass 审查页的必要字段，并增加 `review_reason`、`nearest_gt_gap_sec`、`nearby_peak_confidence`；后两者只是候选选择依据，不是人工判断。`selection_manifest.json` 固定匹配表、GT、旧人工审查、代理清单及原始预测的 SHA-256。`review_site/` 保留与既有审查页相同的遮挡片段及哈希契约，独立 `review_exports/` 保存人工版本。每轮训练只能读取该轮训练比赛的人工修订，另一比赛的测试 GT、预测与原基线不得改写；人工未确认的候选不自动进入训练。

`artifacts/u18_pass_cv/20261117_training_labels_v1/` 是独立训练产物，顶层 `manifest.json` 固定输入文件、冻结分组和各输出 SHA-256。每个 `<fold_id>/` 包含 `train_pass_events.json`（`event_id`、`video_id`、`bepro_time_sec`、`training_time_sec`、`training_frame_index_25fps`、人工来源）、`excluded_bepro_pass.json`（排除原因及审查 ID）、`time_corrections.json`（带符号秒数与原备注）、`pending_pass_additions.json`（视觉 Pass 但事件身份及精确时刻未核）和 `ignore_intervals.json`（负例采样避让区间）。`training_frame_index_25fps` 为四舍五入后的零起始索引。各轮文件只含其训练比赛；排除及校正不改写 `test_gt_pass.json`。待核补标不可当作已确认 GT，也不可作为训练负例。

`20261117_training_labels_v2/` 保留上述 Pass 标签、排除与修订，另从已哈希冻结的全量可评估 GT 中按训练比赛筛选 `パス(受け手)`，写入各轮 `drive_proxy_events.json`（原事件 ID、视频、半场时间与 `mapping_status=provisional_receiver_proxy`）。该文件只用于随机负例时间避让，**不**赋予接球事件可信 Drive GT 身份。模型训练生成 `training_examples.json` 保存逐条正负例视频、25 FPS 零起始帧、Pass 目标和正例事件 ID，以核查避让规则；模型清单含其 SHA-256。

`artifacts/u18_pass_cv/20261117_pending_pass_identity_v2/` 是后续人工身份核对入口，不是训练标签：`identity_review.csv`、`review_data.json`、`index.html`、`manifest.json`。每行保留旧审查 `review_id`、预测半场时间和用户已确认视觉 Pass 的来源，列最近同视频可评估 Bepro Pass 的 ID、时间和差值、原遮挡片段相对路径与起始秒数。`nearest_bepro_event_id` 只是时间最近邻，**不**证明同一动作。人工另填 `identity_decision`（`same_nearest_gt`、`separate_pass`、`unclear`）、`confirmed_pass_time_sec`、`confirmed_frame_index_25fps` 和 `new_comment`；确认帧号为 25 FPS 零起始源视频帧。页面浏览器存储是草稿，正式结果须导出新的 CSV。清单初始 17 行全部空白，5 行 `P1_check_missing_event` 仅为超过 3 秒的先看提示；无人工确认前不得把它们自动加入训练或改写测试 GT。

`20261119_training_labels_v3/` 使用完成的身份审核。`identity_updates.json` 保存旧事件人工校正前后时刻，`identity_additions.json` 保存独立 Pass（ID 为 `human-pass-<review_id>`，`bepro_time_sec=null`）；用户判为非 Pass 的相邻 Bepro 事件记入 `excluded_bepro_pass.json`，不重写冻结 GT。各轮仅含训练比赛审核，manifest 固定来源与输出 SHA-256。

`review_site/` 是本地浏览器审查产物。片段从已遮挡 Bepro 动作文字的 25 FPS 推理代理截取，以 `source_time_sec` 为中心，前后各约 5 秒；页面显示的毫秒时间码由该数值重新计算，不依赖表格软件可能改写的 `source_timecode` 字符串。`manifest.json` 记录输入 CSV/代理哈希、源帧区间和片段哈希。页面的浏览器存储只是草稿；最终人工结果应导出为新的 `pass_review_cases_reviewed.csv`，保留原字段与 `algorithmic_status`，仅填写 `human_visibility`、`human_judgment`、`human_comment`。导出的结果不得反写原始 GT、模型预测或指标。

`drive_review_site/` 使用同样的遮挡片段与页面交互，但输入为原始 50 行 `drive_mapping_audit.csv`，不改变 `event_id`、Bepro 代码或 GT 字段。页面的 `review_observation` 记录接球后画面动作类别，`review_mapping` 取 `accept`、`reject`、`unclear` 或尚未审查的 `unreviewed`，`review_comment` 可补充时间/遮挡原因；导出为独立的 `drive_mapping_audit_reviewed.csv`。这些是人工语义判断，不自动重算已报告的 provisional Drive 指标。

本地服务仅监听 `127.0.0.1`，网页的「保存到项目」将当前完整 CSV 写入 `review_exports/` 的全新时间戳文件；服务验证来源哈希、样本 ID 集合、行数和人工选项后才保存。浏览器下载 CSV 是备用出口。浏览器本地存储只是草稿，正式人工结果以 `review_exports/` 中用户确认的文件或手工下载的 CSV 为准；自动保存和页面测试不得冒充人工审查已完成。

## 10. U18 Pass / reception 人工选帧候选

`パス` 对应 `Pass`；`パス(受け手)` 在本选帧任务中写为 `Reception candidate`。这只是人工查看首次触球的提示，不使用评估器中暂定的 `Drive` 名称，也不自动确认 trap 是否可见。

候选采用原始 Veo 半场视频的 30 FPS，而不是 25 FPS 推理代理。`frame_index` 从 0 开始，`frame_number = frame_index + 1`，`frame_time_sec = frame_index / source_fps`。事件 `source_time_sec` 使用半场视频零点；`match_time_sec` 为完整比赛时间，后半场比前者多 2700 秒。两种时间与帧时间都保留，不得混为同一值。

```text
artifacts/u18_frame_candidates/<run_id>/
  manifest.json
  review.csv
  index.html
  index_small_v1.html
  clip_manifest.json
  frames/<event_id>.jpg
  previews/<event_id>.jpg
  clips/<event_id>.mp4
```

`review.csv` 保留原 GT `event_id`、`video_id`、`match_id`、`half`、`bepro_code`、动作类别、两种时间及时间码、原视频帧号、空间坐标、球场区域、源媒体路径、图片路径和空白人工审查字段。输出图片在生成前遮挡原视频左下方 Bepro 动作文字；预览展示事件前 0.3 秒、事件帧及事件后 0.3 秒。自动结果的 `review_status` 一律为 `unreviewed`，人工导出的选中清单是单独产物，不得反写原始 GT 或当成已确认的首次触球标签。运行清单记录源视频和输入 GT 的哈希、时间间隔及排重设置。

大画面审查版本保留首版图片并为每条候选生成原视频时间轴前后各约 5 秒的 30 FPS、1600×900、无音轨 MP4。编码前遮挡 Bepro 动作文字。`clip_manifest.json` 声明每段 `source_start_frame`、`source_end_frame`、`frame_count`、`center_relative_frame` 和片段哈希；源视频哈希仍在原 `manifest.json`。片段相对帧 `j` 映射到原视频零起始帧 `source_start_frame + j`。页面显示源帧号、半场时间和比赛时间，人工确认帧可不同于 Bepro GT 时间对应帧。导出的 `chosen_frame_index` 与所算两种确认时间是人工选择，须与原始 `frame_index` 和 GT 时间分开保存。导出字段 `suggested_frame_image` 仅指 GT 建议帧；确认帧须根据 `source_video` 与 `chosen_frame_index` 提取，不得将建议帧图片冒充确认帧。

人工选定帧的共享包使用独立目录，不回写候选 `review.csv`：

```text
artifacts/u18_selected_frames/<run_id>/
  selected_frames.csv
  manifest.json
  README.md
  frames/<candidate_id>_<video_id>_f<chosen_frame_index>.jpg
  u18_selected_frames_100.zip
```

`selected_frames.csv` 中 `source_time_sec`、`match_time_sec` 和 `frame_index` 仍是 Bepro 建议事件信息；`chosen_*` 是人工确认的帧号与时间，`selected_frame_image` 指向对应的实际提取图片。共享 CSV 只保留原视频文件名，不依赖本机绝对路径。图片在原始 30 FPS、1920×1080 视频中按零起始帧号提取，左下方 Bepro 文字区域已遮挡。`field_zone`、`x/y` 是原 Bepro 事件坐标，并非对人工选定图片重新定位；`Reception candidate` 也不自动升级为已独立验证的 trap 标签。ZIP 包含 CSV、manifest、README 与全部图片，不包含原始视频或审查片段。

供教授共享的 ZIP 内 `README.md` 使用英语；CSV 字段名和说明性类别使用英语，原始日文视频文件名及 Bepro 代码作为数据标识保留。
