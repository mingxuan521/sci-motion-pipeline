# 贡献指南

欢迎提 PR。几条约定，让改动更容易被接受：

## 提交前

```bash
pip install pytest
python -m pytest tests -q
```

`tests/test_smoke.py` 不需要网络，只依赖 ffmpeg，跑通过基本能说明组装链路没坏。

## 代码风格

- Python 3.10+，类型注解能写就写；
- 注释和文档用中文，变量名用英文；
- 新配置字段必须在 `sci_motion/config.py` 的 `DEFAULTS` 里给默认值，并在 README 的配置表补一行；
- 不要引入重型依赖（torch 之类），核心路径保持"装完就能跑"。

## 加一个新的出图 provider

在 `sci_motion/stills.py` 里加一个分支，并在 README 的 provider 表格补一行即可。
要求：幂等（产物存在就直接返回）、失败时抛带命令/响应的异常。

## 加一个新的运动方式

在 `sci_motion/motion.py` 里加 filter 表达式，接口保持
`build_clip(still, dest, *, duration, width, height, fps, ffmpeg, ...)`。
凡是 ffmpeg 之外的方案（I2V 模型等），请在 `docs/` 说明，不要塞进核心依赖。

## 关于示例内容

`examples/narration.example.json` 里的解说词是中文科普案例，欢迎替换为更优质的内容，
但请保持 3 句/主题的结构，好让新用户复制就能跑。
