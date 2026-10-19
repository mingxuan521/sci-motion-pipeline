# 更新日志

本项目所有值得记录的变更都会写在这里，格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [0.1.0] - 2026-10-19

### 新增

- 端到端流水线：解说词 → edge-tts 配音 → 静帧 → zoompan 运动画面 → 声画组装 → 成片
- 三种出图 provider：`synthetic`（占位）/ `local`（本地目录）/ `command`（外部命令）
- 命令行 `synth` / `stills` / `motion` / `assemble` / `all` / `doctor`，支持 `--only` 按主题筛选
- 每步幂等，中断后可原地续跑
- edge-tts 双主机容错，兼容微软 2026 年端点迁移
- 附带 8 个微观生命主题的中文解说词与提示词示例
- 冒烟测试与 GitHub Actions CI
