# GPU 升级：把假运动换成真运动

内置运动是 ffmpeg 推拉，CPU 就能跑但运动是"假的"。
有显卡（实测 RTX 2080 Super 8GB / 云端 4090 24GB 可用）后可以换成 I2V 模型生成的真实运动视频。

## 思路

组装环节只认文件名 `work/clips/{theme}_s{i}.mp4`，不关心来源。所以升级=替换 clips：

1. 照常跑配音：`python -m sci_motion synth -c config.json`
2. 照常出静帧：`python -m sci_motion stills -c config.json`（provider 换成你的出图 API）
3. **跳过 motion 步骤**，用自己的 I2V 流程把每张静帧变成一段视频，存到同样的文件名
4. 只跑组装：`python -m sci_motion assemble -c config.json`

## 参考参数（Wan2.2 I2V 14B + Lightx2v 4-step LoRA，ComfyUI）

| 参数 | 值 | 备注 |
|---|---|---|
| 分辨率 | 1280 × 720 | 与 config 保持一致 |
| 帧数 | 81 帧 @ 16fps | ≈ 5.06 秒/段 |
| 采样步数 | 4 | 配 Lightx2v LoRA 才能这么低 |
| 显存 | ≥ 24GB | 8GB 卡建议走 TI2V-5B FP8 量化版 |

时长不足的部分不用担心——`assemble.py` 会自动 `tpad` 补到配音长度。

## 模型下载

国内建议用 ModelScope，实测约 11 MB/s，明显快于 hf-mirror（约 2.5 MB/s）。

## 踩坑记录

- ComfyUI 的 `SaveVideo` 节点不把结果登记进 `/history` 的输出，
  需要从 output 目录按文件名前缀自己收片；
- ComfyUI 从不同盘符启动时写盘位置会变，收片路径要准备兜底目录；
- 8GB 显存跑 14B 会 OOM，别硬扛，用 FP8 的 5B 或用云端按量机器。

> 如果你已经有一套 ComfyUI 工作流，欢迎提 PR 把它封装成 `stills`/`motion` 之外的
> 第四个 provider，让没显卡和有显卡的人用同一份配置。
