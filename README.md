# sci-motion-pipeline

把一段**中文科学解说词**，自动做成一条**带配音、有运动感的成品视频**。

解说词 → 配音 → 静帧 → 运动画面 → 成片，一条命令跑完，**不需要显卡**。

```bash
python -m sci_motion all -c config.json
```

---

## 为什么会有这个项目

做科普视频最耗时间的不是创意，而是重复劳动：写词、配音、找图、做运动、对齐声画、导出。
这套流水线把这些步骤固化成可复跑的脚本：

- **纯 CPU 可跑**：画面运动用 ffmpeg 的 `zoompan` 做肯·伯恩斯式推拉，集成显卡甚至没有显卡的机器都能出片，成本几乎只剩电费；
- **中文原生**：edge-tts 中文配音（含 2026 年微软端点迁移后的双主机容错），解说词按句号自动拆句，一句对应一段画面；
- **幂等续跑**：每一步都跳过已存在且正常的产物，中途断网/断电后原地继续，不用从头开始；
- **渐进升级**：有显卡时可以跳过内置运动模块，直接用自己的 I2V 视频（如 Wan2.2）替换 `work/clips/`，组装环节完全通用；
- **出图不绑定厂商**：内置占位图、本地目录、外部命令三种 provider，Agnes / SD / ComfyUI / 任何 API 都能接。

## 快速开始

### 1. 安装

```bash
git clone https://github.com/mingxuan521/sci-motion-pipeline.git
cd sci-motion-pipeline
pip install -r requirements.txt
```

ffmpeg 二选一：`pip install imageio-ffmpeg`（推荐，自带静态二进制），或自己安装并放进 PATH。

### 2. 环境自检

```bash
python -m sci_motion doctor
```

### 3. 跑一条完整视频

```bash
cp examples/config.example.json config.json
python -m sci_motion all -c config.json
```

默认配置下会读取 `examples/narration.example.json` 里的 8 个微观生命主题
（免疫细胞、酵母、有丝分裂、乳酸菌、心脏、神经元、药物、凝血），
生成约 2 分钟的 16:9 视频，输出到 `out/final.mp4`。

想先看看效果再决定要不要跑全片：

```bash
python -m sci_motion all -c config.json --only t1_immune   # 只跑一个主题
```

### 4. 换成自己的内容

编辑 `narration.json`，每个主题写 **恰好 3 句**（句号结尾，一句一段画面）：

```json
{
  "voice": "zh-CN-XiaoxiaoNeural",
  "rate": "+8%",
  "scripts": {
    "t1_immune": "第一句。第二句。第三句。"
  },
  "prompts": {
    "t1_immune_s1": "可选：为每段单独指定出图提示词"
  }
}
```

句子数与 `sentences_per_theme` 不符的主题会被跳过并打印告警——这是刻意的，防止半截内容的主题混进成片。

## 出图的三种 provider

| provider | 用途 | 配置 |
|---|---|---|
| `synthetic` | 零成本试跑、占位底图，ffmpeg 生成渐变色块 | `"provider": "synthetic"` |
| `local` | 复用你已有的图片，按命名规则匹配 | `{"dir": "my_images", "pattern": "{theme}_s{i}.*"}` |
| `command` | 调外部脚本/API 出图，最灵活 | `{"template": "python gen.py --prompt \"{prompt}\" --out \"{output}\""}` |

`command` 模板里可用占位符：`{prompt}` `{output}` `{theme}` `{i}` `{width}` `{height}`。
API key 写在 `options.env` 里会注入子进程环境变量，**记得把 `config.json` 加进 .gitignore**（已默认忽略）。

## 配置字段

| 字段 | 默认 | 说明 |
|---|---|---|
| `project_dir` | `.` | 数据根目录 |
| `work_dir` | `work` | 中间产物（audio / stills / clips / themes） |
| `out_file` | `out/final.mp4` | 成片路径 |
| `narration_file` | — | 解说词 JSON |
| `width` / `height` / `fps` | 1280 / 720 / 25 | 画面规格 |
| `crf` | 18 | 编码质量，越小画质越好体积越大 |
| `voice` / `rate` | zh-CN-XiaoxiaoNeural / +8% | 配音音色与语速 |
| `sentence_sep` | `。` | 拆句符号 |
| `sentences_per_theme` | 3 | 每主题期望句数 |
| `xfade` | 0.4 | 视频/音频交叉淡化时长（秒） |
| `motion.mode` | auto | auto / zoom_in / zoom_out / pan |
| `motion.zoom` | 0.12 | 推拉幅度 |
| `stills.provider` | synthetic | 出图方式 |

完整示例见 [`examples/config.example.json`](examples/config.example.json) 与
[`examples/config.command-provider.json`](examples/config.command-provider.json)。

## 目录结构

```
sci-motion-pipeline/
├── sci_motion/           # 核心包
│   ├── config.py         # 配置加载 + ffmpeg 自动发现
│   ├── tts.py            # edge-tts 配音（双主机容错）
│   ├── stills.py         # 静帧获取（三种 provider）
│   ├── motion.py         # zoompan 运动画面（CPU 方案）
│   ├── assemble.py       # 声画拼接：句 → 主题 → 成片
│   ├── pipeline.py       # 端到端编排
│   └── cli.py            # 命令行
├── examples/             # 配置与解说词样例
├── docs/                 # 架构说明、GPU 升级指南
└── tests/                # 冒烟测试
```

## 有显卡之后

有 GPU 时，把 `work/clips/{theme}_s{i}.mp4` 换成 I2V 模型生成的真实运动视频即可，
命名保持一致，然后只跑组装这一步：

```bash
python -m sci_motion assemble -c config.json
```

声画对齐、补尾帧、交叉淡化的逻辑都已按"画面时长可能短于配音"处理过（见 `assemble.py` 的 `tpad`）。
详细工作流参考 [docs/gpu-upgrade.md](docs/gpu-upgrade.md)。

## 常见问题

**edge-tts 连接失败？**
微软在 2026 年前后迁移过端点，`tts.py` 已做新旧双主机自动容错。仍失败通常是网络不通，检查代理。

**画面某段比配音短？**
组装时会自动用 `tpad` 补最后一帧到配音长度，不会出现画面走完了旁白还在念的黑屏。

**想换分辨率/画幅？**
改 `width` / `height` 即可。竖屏短视频交换这两个值（例如 720 / 1280），
但记得同步改掉出图提示词里的构图描述（16:9 → 9:16）。

## 路线图

- [x] CPU 兜底链路（zoompan + xfade 声画对齐）
- [x] 多 provider 出图接口
- [x] 幂等续跑与按主题筛选
- [ ] 字幕烧录（ASS/SRT）
- [ ] 背景音乐自动避让（ducking）
- [ ] ComfyUI Wan2.2 I2V 直连适配器

## License

[MIT](LICENSE)
