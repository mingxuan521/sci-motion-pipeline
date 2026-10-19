# 架构说明

## 数据流

```
narration.json
   │  按句号拆句
   ▼
Shot 列表（theme, index, text, prompt）
   │
   ├─► tts.synth_file()      → work/audio/{theme}_s{i}.mp3
   ├─► stills.ensure_still() → work/stills/{theme}_s{i}.png
   ├─► motion.build_clip()   → work/clips/{theme}_s{i}.mp4   （时长 = 配音时长）
   └─► assemble              → work/themes/{theme}.mp4 → out/final.mp4
```

每个 Shot 是流水线的最小单位：**一句解说词 = 一段配音 = 一张静帧 = 一段画面**。
这样做的好处是任一步失败都可精确定位，且天然支持按分辨率、按主题并行/补跑。

## 幂等设计

| 步骤 | 跳过条件 |
|---|---|
| 配音 | 文件存在且 > 3KB（小于这个值通常是空音频或错误页） |
| 静帧 | 文件存在且非空 |
| 运动片段 | 无（时长依赖配音，配音变了画面要重出） |
| 组装 | 无 |

`--force` 只作用于配音步骤，因为静帧/画面重出成本高且通常没必要。

## 声画对齐的关键

- 每段画面按时长 = 该句配音时长生成，从源头避免不对齐；
- 画面短于配音时用 `tpad=stop_mode=add` 补最后一帧；
- 音频用 `apad=whole_dur=` 铺满整段，避免拼接时静音漂移；
- 两级拼接都用 `-t` 强制正确时长：`xfade` 会把首个输入的时长写进 mp4 头，
  不强制会出现"播放器显示 5 小时"的经典坑；
- `acrossfade` 只接受 `d=` 参数（不接受 `transition=`）。

## 为什么默认用 zoompan

`zoompan` 是纯 CPU 滤镜，任何机器都能跑，成本为零。
缺点是运动是"假"的——推拉/横移，不是物体自身在动。
真实运动需要 I2V 模型（Wan2.2 等），参见 [gpu-upgrade.md](gpu-upgrade.md)。

本项目把两者设计成同一接口：**只要 `work/clips/` 下有同名 mp4，组装环节不关心它是怎么来的。**
