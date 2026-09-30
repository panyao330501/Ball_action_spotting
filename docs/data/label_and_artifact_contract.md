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
- Bepro `パス(受け手)` 暂映射为 `Drive`，`mapping_status=provisional_receiver_proxy`；完成人工语义审查前，不得省略 proxy/provisional 限定。
- `ドリブル突破`、`スペースへのドリブル` 不直接映射为本模型的 `Drive`。

每条 U18 GT 至少保留：`event_id`、`video_id`、`match_id`、`half`、`source_time_sec`、`match_time_sec`、`label`、`mapping_status`、原始 Bepro code、team/player、`x/y/to_x/to_y`、pass result、`evaluation_status`、排除原因及源 XML/事件 ID。

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
```
