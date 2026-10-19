"""命令行入口。

    python -m sci_motion doctor                      # 环境自检
    python -m sci_motion all      -c config.json     # 一条龙
    python -m sci_motion synth    -c config.json [--force]
    python -m sci_motion stills   -c config.json
    python -m sci_motion motion   -c config.json
    python -m sci_motion assemble -c config.json --only t1_immune,t2_yeast
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import load_config
from .pipeline import run

STEPS = ("synth", "stills", "motion", "assemble")


def _doctor() -> int:
    from .config import FFmpegNotFound, get_ffmpeg

    print(f"sci-motion-pipeline {__version__}")
    try:
        print("ffmpeg  :", get_ffmpeg())
    except FFmpegNotFound as e:
        print("ffmpeg  : 缺失 ->", e)
    for mod, pip_name in (("edge_tts", "edge-tts"), ("aiohttp", "aiohttp")):
        try:
            __import__(mod)
            print(f"{mod:8}: OK")
        except ImportError:
            print(f"{mod:8}: 缺失 -> pip install {pip_name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="sci-motion",
        description="中文科学可视化视频流水线：解说词 -> 配音 -> 画面 -> 成片",
    )
    ap.add_argument("step", choices=[*STEPS, "all", "doctor"])
    ap.add_argument("-c", "--config", default="config.json", help="JSON 配置文件路径")
    ap.add_argument("--only", default="", help="只处理指定主题，逗号分隔")
    ap.add_argument("--force", action="store_true", help="忽略已有产物，强制重跑")
    args = ap.parse_args(argv)

    if args.step == "doctor":
        return _doctor()

    steps = STEPS if args.step == "all" else (args.step,)
    cfg = load_config(args.config)
    only = {s.strip() for s in args.only.split(",") if s.strip()} or None
    run(cfg, steps=steps, force=args.force, only=only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
