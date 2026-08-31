# 标签和产物契约

版本：0.1 草案  
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

