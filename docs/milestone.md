# 里程碑和重大变更

本文件采用追加式记录。只记录已完成的步骤、已交付产物或重大变化；计划和未完成工作写入当前步骤计划。

## 2026-08-31——项目计划基线

- 明确 PoC 目标：对开球后约 10 分钟的视频检测 Pass/Drive，并在没有 GT 的情况下进行主观视频审查。
- 确定远端推理、本地可视化的架构。
- 识别视频限制：清晰度较低、摄像机跟随滞后或静止、动作可能发生在画外、全程单机位无切换。
- 确定画外动作应标为不可观测，而不是自动视为模型漏检。

## 2026-08-31——基础设施和文档检查

- 确认本地输入视频位于 `C:\Code\Ball_action_spotting\vs_飛鳥FC_20260704_trimmed_0930.mp4`。
- 定位本地 Conda 25.11.1：`C:\ProgramData\miniconda3`。
- 验证通过密钥连接 `y_pan@chiron`。
- 确认远端目录 `/work7/y_pan/Code_repo/Ball_action_spotting/` 存在且为空。
- 确认 `chiron` 有 8 张 NVIDIA RTX A6000。
- 确认远端 FFmpeg 6.1.1 和 Git 2.43.0 可用。
- 创建项目指令、总体计划、活动步骤计划、测试文档、命令手册、决策日志、数据契约和 Git 忽略规则。

## 2026-08-31——项目文档中文化

- 将当前全部 Markdown 工作文档改为中文。
- 保留路径、命令、环境名、字段名和标准标签的英文精确拼写。
- 在 `AGENTS.md` 中新增“工作文档正文使用中文”的持续维护规则。

## 2026-08-31——建立 GitHub 双端同步

- 将 GitHub 远端确定为 `https://github.com/panyao330501/Ball_action_spotting.git`。
- 在本地初始化 `main` 分支并验证源 MP4 与 `.obsidian/` 均未进入版本控制。
- 创建并推送首次文档提交 `ebf1e17`。
- 在 `chiron` 的 `/work7/y_pan/Code_repo/Ball_action_spotting/` 完成克隆。
- 验证本地与远端首次检出均指向提交 `ebf1e17`，且 `origin` 地址一致。
