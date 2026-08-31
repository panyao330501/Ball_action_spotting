# 步骤 03——模型获取和自定义视频适配器

状态：进行中
开始日期：2026-08-31
前置步骤：`02_video_audit_and_inference_contract` 已完成
后续步骤：`04_full_remote_inference_and_postprocessing`

## 目标

使用已固定提交的 2023 SoccerNet Ball Action Spotting 冠军方案，在 `chiron` 的 `ballspot-infer` Conda 环境中加载经过校验的预训练权重，为本项目的单段 MP4 建立可复现的 25 FPS 推理入口，并在 60～90 秒输入上完成端到端冒烟测试。

## 固定输入和边界

- 上游源码目录：`/work7/y_pan/Code_repo/Ball_action_spotting/third_party/ball-action-spotting`
- 上游源码提交：`9c471531c62b51bd0cfe6170b74d035da44c88ed`
- 模型标签：`PASS`、`DRIVE`；本项目对外显示为 `Pass`、`Drive`。
- 推理输入：完整 25 FPS 代理视频，身份见 `configs/poc_video.yaml`。
- 初次冒烟只取代理的 `0.000`～`90.000` 秒作为程序运行范围；这是推理窗口范围，不创建新的媒体剪辑。

## 工作包

### 1. 权重与许可证

- [ ] 从上游发布页或作者指定位置获取官方预训练权重，不使用无法追溯的镜像。
- [ ] 记录下载 URL、发布日期/版本、文件大小、SHA-256、许可证和获取日期；权重存入远端 Git 忽略的 `weights/`。
- [ ] 读取权重内的 `argus` 模型参数，确认 `multidim_stacker`、2 类、15 帧、步长 2、`pad_normalize` 与固定源码一致。

验收：可追溯且已哈希的权重能被 `argus.load_model` 成功载入，不含缺失键、NaN 或不匹配参数。

### 2. 自定义视频推理入口

- [ ] 在本仓库实现独立入口，不修改 `third_party/` 上游检出。
- [ ] 读取 `configs/poc_video.yaml`，验证源/代理身份和输入为 25 FPS。
- [ ] 复用上游的 `MultiDimStackerPredictor`、`pad_normalize`、15 帧、步长 2 和原始后处理参数；优先使用 OpenCV 解码适配器，GPU 仅用于模型计算。
- [ ] 以连续帧解码覆盖指定时间范围，正确处理 28 帧上下文边界并记录有效预测帧范围。
- [ ] 导出不可变原始分数、帧号、`frame_index / 25.0` 秒和运行清单；不得在本步骤先丢弃低分。

验收：入口无需 SoccerNet 的比赛目录结构；可从配置运行；输出符合 `docs/data/label_and_artifact_contract.md`。

### 3. 60～90 秒端到端冒烟

- [ ] 在单张指定 A6000 上执行 0～90 秒范围。
- [ ] 保存命令、日志、环境、模型/权重/源码/本仓库提交、输入哈希和 GPU 信息。
- [ ] 检查分数数组长度、时间升序、有限值、两类列名、边界行为和无意外全零输出。
- [ ] 使用相同输入和配置重复一次；比较原始分数以确认确定性或记录可接受差异。

验收：两次运行能成功产生结构合规的原始分数，无 NaN/Inf；时间可映射回源视频，且日志足以复现。

## 风险和处理

- 权重链接失效或需要权限：停止在权重获取，记录可复现的阻塞信息，不以随机权重代替。
- 上游 `argus` 序列化和当前 Python/PyTorch 不兼容：优先在隔离 Conda 环境中作最小兼容修补，并记录变更；不升级核心依赖后继续假定权重可用。
- OpenCV 解码吞吐不足：先完成正确性测试，再评估 NVIDIA VPF；不能为了提速改变 25 FPS 时间契约。
- 低清晰度与画外动作影响的是模型效果，不是本步骤的输入完整性错误；在后续主观审查中标注可见性。
