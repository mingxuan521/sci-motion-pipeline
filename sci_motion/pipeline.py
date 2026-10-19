"""端到端编排：解说词 -> 配音 -> 静帧 -> 运动片段 -> 成片。

每一步都是幂等的（产物已存在且大小合理就跳过），所以中断后可以原地续跑。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import assemble as asm
from .config import Config, FFmpegNotFound, get_ffmpeg
from .ffmpeg import probe_duration
from . import motion as mtn
from . import stills as stl
from .tts import split_sentences, synthesize_all

__all__ = ["Shot", "load_narration", "run"]

DEFAULT_PROMPT_PREFIX = (
    "科学可视化风格，超写实微观摄影感，柔和冷色环境光，浅景深，"
    "干净的深色背景，无文字，16:9 构图："
)


@dataclass
class Shot:
    """一个句子对应的一段：一句配音 + 一张静帧 + 一段运动画面。"""

    theme: str
    index: int
    text: str
    audio: Path
    still: Path
    clip: Path
    prompt: str = ""
    duration: float = 0.0
    meta: dict = field(default_factory=dict)


def load_narration(path: str | Path, *, voice: str, rate: str, sep: str = "。"):
    """读取解说词配置，返回 (voice, rate, {theme: [句子...]})。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    voice = data.get("voice", voice)
    rate = data.get("rate", rate)
    scripts = {k: split_sentences(v, sep) for k, v in data["scripts"].items()}
    prompts = data.get("prompts", {})
    return voice, rate, scripts, prompts


def build_shots(cfg: Config, scripts: dict, prompts: dict, expected: int) -> list[Shot]:
    """把解说词展开成 Shot 列表，句子数不符的整主题跳过并告警。"""
    prefix = cfg.get("prompt_prefix", DEFAULT_PROMPT_PREFIX)
    shots: list[Shot] = []
    for theme, sentences in scripts.items():
        theme_prompts = prompts.get(theme, [])
        if expected and len(sentences) != expected:
            print(f"!! {theme} 句子数={len(sentences)}（期望 {expected}），跳过该主题")
            continue
        for i, text in enumerate(sentences, 1):
            prompt = theme_prompts[i - 1] if i <= len(theme_prompts) else prefix + text
            shots.append(Shot(
                theme=theme, index=i, text=text,
                audio=cfg.audio_dir / f"{theme}_s{i}.mp3",
                still=cfg.stills_dir / f"{theme}_s{i}.png",
                clip=cfg.clips_dir / f"{theme}_s{i}.mp4",
                prompt=prompt,
            ))
    return shots


def run(
    cfg: Config,
    *,
    steps: tuple[str, ...] = ("synth", "stills", "motion", "assemble"),
    force: bool = False,
    only: set[str] | None = None,
    log: Callable[[str], None] = print,
) -> Path:
    """执行流水线，返回成片路径。"""
    try:
        ffmpeg = get_ffmpeg()
    except FFmpegNotFound as e:
        raise SystemExit(str(e))

    cfg.ensure_dirs()
    log(f"ffmpeg : {ffmpeg}")
    log(f"工程目录: {cfg.project_dir}")

    voice, rate, scripts, prompts = load_narration(
        cfg["narration_file"], voice=cfg["voice"], rate=cfg["rate"],
        sep=cfg["sentence_sep"],
    )
    shots = build_shots(cfg, scripts, prompts, cfg["sentences_per_theme"])
    if only:
        shots = [s for s in shots if s.theme in only]
    if not shots:
        raise SystemExit("没有可处理的镜头，请检查 narration_file 或 --only 参数")

    # ---------- ① 配音 ----------
    if "synth" in steps:
        log(f">> ① 配音（{len(shots)} 段，voice={voice} rate={rate}）")
        results = synthesize_all(
            [(f"{s.theme}_s{s.index}", s.text, str(s.audio)) for s in shots],
            voice, rate, force=force,
        )
        for name, dest, host in results:
            if host != "skip":
                log(f"  {name} <- {host}")

    # ---------- ② 静帧 ----------
    if "stills" in steps:
        log(f">> ② 静帧（provider={cfg['stills']['provider']}）")
        stl.ensure_stills(
            cfg["stills"]["provider"],
            [{"theme": s.theme, "dest": s.still, "prompt": s.prompt} for s in shots],
            width=cfg["width"], height=cfg["height"],
            options=cfg["stills"].get("options"), ffmpeg=ffmpeg,
        )

    # ---------- ③ 运动片段 ----------
    if "motion" in steps:
        log(">> ③ 运动片段（ffmpeg zoompan，纯 CPU）")
        for s in shots:
            if not s.audio.exists():
                raise SystemExit(f"缺少配音，请先跑配音步骤：{s.audio}")
            s.duration = probe_duration(s.audio, ffmpeg)
            dur = max(s.duration, cfg["motion"].get("min_clip", 0.0))
            mtn.build_clip(
                s.still, s.clip, duration=dur,
                width=cfg["width"], height=cfg["height"], fps=cfg["fps"],
                ffmpeg=ffmpeg, mode=cfg["motion"].get("mode", "auto"),
                zoom_total=cfg["motion"].get("zoom", 0.12),
            )

    # ---------- ④ 组装 ----------
    if "assemble" not in steps:
        return cfg.out_file

    log(">> ④ 组装成片")
    themes: list[str] = []
    for s in shots:
        if s.theme not in themes:
            themes.append(s.theme)

    theme_durs: dict[str, float] = {}
    theme_files: list[Path] = []
    for theme in themes:
        group = sorted(
            [s for s in shots if s.theme == theme], key=lambda x: x.index
        )
        # I2V 模式下可直接跳过 ③，这里容忍 clip 由用户提供
        missing = [s.clip for s in group if not s.clip.exists()]
        if missing:
            raise SystemExit(f"缺少画面片段：{missing[0]}（先跑 motion 步骤或自备 clips）")
        if not all(s.audio.exists() for s in group):
            raise SystemExit(f"缺少配音：{theme}")
        dest = cfg.themes_dir / f"{theme}.mp4"
        theme_durs[theme] = asm.assemble_theme(
            theme, [s.clip for s in group], [s.audio for s in group], dest,
            ffmpeg=ffmpeg, xfade=cfg["xfade"], crf=cfg["crf"],
            abitrate=cfg["abitrate"],
        )
        theme_files.append(dest)

    total = asm.assemble_final(
        theme_files, theme_durs, cfg.out_file,
        ffmpeg=ffmpeg, xfade=cfg["xfade"], crf=cfg["crf"],
        abitrate=cfg["abitrate"],
    )
    log(f">> 完成 {cfg.out_file}（{total}s）")
    return cfg.out_file
