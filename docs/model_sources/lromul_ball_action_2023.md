# lRomul 2023 Ball Action Spotting 冠军模型来源记录

状态：已验证
最后核验日期：2026-09-01

## 官方来源

- 代码仓库：`https://github.com/lRomul/ball-action-spotting`
- 固定源码提交：`9c471531c62b51bd0cfe6170b74d035da44c88ed`
- 作者 README 的训练产物下载目录：`https://drive.google.com/drive/folders/1mIu62cIdsRn3W4o1E5vRR8V5Q1B6HHoz?usp=sharing`
- 代码许可证：MIT（上游 `LICENSE`）。
- 参考发布信息：上游 `CITATION.cff` 标注版本 `v23.06.19`、发布日期 `2023-06-19`。

## 本项目下载记录

- 获取方式：用户于 2026-09-01 从上述官方公开目录手动下载。
- 放置端：`chiron`。
- 放置路径：`/work7/y_pan/Code_repo/Ball_action_spotting/action/` 与 `/work7/y_pan/Code_repo/Ball_action_spotting/ball_action/`。
- Git 状态：这两个根目录及所有 `.pth` 文件均被 `.gitignore` 排除；不得提交或通过 GitHub 传输。
- 内容规模：`action/` 约 223 MB，`ball_action/` 约 1.3 GB；其中包含模型训练记录和上游预测文件。PoC 推理实际使用下面列出的最终 7 个权重。

## 最终推理权重

实验：`ball_finetune_long_004`。各 fold 的文件大小均为 55,081,387 字节。

| Fold | 相对路径 | SHA-256 |
| --- | --- | --- |
| 0 | `ball_action/experiments/ball_finetune_long_004/fold_0/model-006-0.864002.pth` | `544440209aa8cfbfc0859f37756a3e753b0acf0adb78a63609e4d8f6a588eaa4` |
| 1 | `ball_action/experiments/ball_finetune_long_004/fold_1/model-006-0.862339.pth` | `848279f64b01d93353660de30360ec3cb584b873af02e1645cdbcd6f499056b7` |
| 2 | `ball_action/experiments/ball_finetune_long_004/fold_2/model-006-0.758246.pth` | `5d55367337104c2decd71948e06a32ca5d176e00d63076b383abdab76f2d5fbe` |
| 3 | `ball_action/experiments/ball_finetune_long_004/fold_3/model-006-0.887217.pth` | `0437d799901d26a402b8351b6e3dec3e6d24d6876b18a968494beddef0dec8c2` |
| 4 | `ball_action/experiments/ball_finetune_long_004/fold_4/model-006-0.869269.pth` | `73d09ddde07c372d45732dbe5233f37e8f1257c2ded3330e0385e61db3942890` |
| 5 | `ball_action/experiments/ball_finetune_long_004/fold_5/model-006-0.901643.pth` | `cd8ec6db936fe774584e91f7858425e6a4b94648776bcd1e4c08dd7e957a98b9` |
| 6 | `ball_action/experiments/ball_finetune_long_004/fold_6/model-006-0.897602.pth` | `c47e00c099e26830addb58f4c4a7c218d1afdd3448ae9f74b3c9f5b1ef196027` |

## 兼容性证据

在 `ballspot-infer` 中设置 `PYTHONPATH` 为固定上游源码路径并使用 `argus.load_model` 加载 fold 0，结果如下：

- 成功加载至 `cuda:0`；
- `nn_module`：`multidim_stacker`，`num_classes=2`；
- `num_frames=33`、`frame_stack_size=33`、`frame_stack_step=2`；
- `frames_processor`：`pad_normalize(size=(1280, 736), pad_mode="constant", fill_value=0)`。

后续自定义适配器必须把这 7 个 fold 的原始预测逐帧平均；不得仅选取单个 fold 作为最终 PoC 结果。
