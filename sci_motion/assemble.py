"""声画组装：句子片段 -> 主题片段 -> 成片。

两级 xfade（视频）+ acrossfade（音频）拼接，逐严格对齐到每句配音的时长。
踩过的两个坑，这里已固化处理：
1. xfade 会把首个输入的时长写进 mp4 头（曾误标成 5 小时），必须用 -t 强制正确时长；
2. acrossfade 只接受 d= 参数，本版本滤镜不接受 transition=。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Sequence

from .ffmpeg import dump_json, probe_duration, run

__all__ = ["assemble_theme", "assemble_final"]


def _theme_pairs(videos: Sequence[Path], audios: Sequence[Path]) -> list[tuple[Path, Path]]:
    if len(videos) != len(audios):
        raise ValueError(f"声画数量不一致：{len(videos)} 视频 vs {len(audios)} 音频")
    return list(zip(videos, audios))


def assemble_theme(
    name: str,
    videos: Sequence[Path],
    audios: Sequence[Path],
    dest: str | Path,
    *,
    ffmpeg: str,
    xfade: float,
    crf: int,
    abitrate: str,
    log: Callable[[str], None] = print,
) -> float:
    """把同一主题的若干段（画面 + 对应配音）拼成一个主题片段，返回时长（秒）。"""
    pairs = _theme_pairs(videos, audios)
    n = len(pairs)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    adurs = [probe_duration(a, ffmpeg) for a in audios]
    vdurs = [probe_duration(v, ffmpeg) for v in videos]
    sdurs = [max(v, a) for v, a in zip(vdurs, adurs)]  # 画面不够长就补尾帧

    chain: list[str] = []
    inputs: list[str] = []
    for i, (v, a) in enumerate(pairs):
        inputs += ["-i", str(v), "-i", str(a)]
        chain.append(f"[{2 * i}]scale=1280:-2[v{i}]")
        ext = round(sdurs[i] - vdurs[i], 4)
        if ext > 0.001:
            chain.append(f"[v{i}]tpad=stop_mode=add:stop_duration={ext}[vt{i}]")
        else:
            chain.append(f"[v{i}]copy[vt{i}]")
        chain.append(
            f"[{2 * i + 1}]apad=whole_dur={int(round(sdurs[i] * 1000))}[at{i}]"
        )

    prev = "vt0"
    total = sdurs[0]
    for k in range(1, n):
        off = total - xfade
        tag = f"vx{k}"
        chain.append(
            f"[{prev}][vt{k}]xfade=transition=fade:duration={xfade}"
            f":offset={off:.4f}[{tag}]"
        )
        prev = tag
        total = total + sdurs[k] - xfade

    aprev = "at0"
    for k in range(1, n):
        tag = f"ax{k}"
        chain.append(f"[{aprev}][at{k}]acrossfade=d={xfade}[{tag}]")
        aprev = tag

    cmd = [ffmpeg, "-y", *inputs,
           "-filter_complex", ";".join(chain),
           "-t", f"{total:.3f}",
           "-map", f"[{prev}]", "-map", f"[{aprev}]",
           "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", abitrate, "-movflags", "+faststart",
           str(dest)]
    run(cmd)
    real = probe_duration(dest, ffmpeg)
    log(f"  主题 {name}：{real:.2f}s -> {dest.name}")
    return round(real, 4)


def assemble_final(
    theme_files: Sequence[Path],
    theme_durs: dict[str, float],
    dest: str | Path,
    *,
    ffmpeg: str,
    xfade: float,
    crf: int,
    abitrate: str,
    log: Callable[[str], None] = print,
) -> float:
    """把多个主题片段拼成最终成片，返回总时长（秒）。"""
    n = len(theme_files)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if n == 1:  # 只有一个主题时无需拼接，直接封装
        if Path(theme_files[0]).resolve() != dest.resolve():
            run([ffmpeg, "-y", "-i", str(theme_files[0]), "-c", "copy",
                 "-movflags", "+faststart", str(dest)])
        _sum = sum(theme_durs.values())
        return round(probe_duration(dest, ffmpeg), 2) if _sum else 0.0

    inputs: list[str] = []
    for f in theme_files:
        inputs += ["-i", str(f)]

    chain: list[str] = []
    prev_v, prev_a = "0:v", "0:a"
    acc = theme_durs[Path(theme_files[0]).stem]
    for k in range(1, n):
        off = acc - xfade
        v_tag, a_tag = f"vx{k}", f"ax{k}"
        chain.append(
            f"[{prev_v}][{k}:v]xfade=transition=fade:duration={xfade}"
            f":offset={off:.4f}[{v_tag}]"
        )
        chain.append(f"[{prev_a}][{k}:a]acrossfade=d={xfade}[{a_tag}]")
        prev_v, prev_a = v_tag, a_tag
        acc = acc + theme_durs[Path(theme_files[k]).stem] - xfade

    cmd = [ffmpeg, "-y", *inputs,
           "-filter_complex", ";".join(chain),
           "-t", f"{acc:.3f}",
           "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
           "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", abitrate, "-movflags", "+faststart",
           str(dest)]
    run(cmd)

    total = round(probe_duration(dest, ffmpeg), 2)
    dump_json(theme_durs, dest.parent / "_theme_durs.json")
    log(f"成片完成：{dest}  {total}s")
    return total
