"""把静帧变成会"动"的画面。

CPU 方案用 ffmpeg 的 zoompan 做肯·伯恩斯式推拉/横移，这是本项目能在没有显卡的
机器上跑通的关键。有显卡时跳过本模块，直接用 I2V 模型出真实运动视频即可，
组装环节（assemble.py）两者通用。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .ffmpeg import probe_duration, run

__all__ = ["build_clip", "zoom_expr"]

# 推拉速度（每帧倍数变化量），按 25fps 换算约每秒 0.0375 倍，肉眼最舒服
_ZOOM_RATE = 0.0015


def zoom_expr(mode: str, zoom_total: float) -> str:
    """生成 zoompan 的 z 表达式。

    mode: zoom_in（缓慢推近）/ zoom_out（缓慢拉远）/ pan（固定倍率，靠位移运动）
    """
    z = 1.0 + zoom_total
    if mode == "zoom_in":
        return f"min({z:.4f},max(1.001,1+{_ZOOM_RATE}*on))"
    if mode == "zoom_out":
        return f"max(1.001,{z:.4f}-{_ZOOM_RATE}*on)"
    if mode == "pan":
        return f"{z:.4f}"
    raise ValueError(f"未知运动模式：{mode}（可选 auto/zoom_in/zoom_out/pan）")


def build_clip(
    still: str | Path,
    dest: str | Path,
    *,
    duration: float,
    width: int,
    height: int,
    fps: int,
    ffmpeg: str,
    mode: str = "auto",
    zoom_total: float = 0.12,
    log: Callable[[str], None] = print,
) -> Path:
    """单张静帧 -> 一段带推拉的 h264 视频。

    auto 模式按段序偶奇偶轮换取 zoom_in / zoom_out，避免整片运动方向单调。
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if mode == "auto":
        # 用文件名里的段号做奇偶判断，稳定可复现
        stem = Path(still).stem
        n = int(stem[-1]) if stem[-1].isdigit() else 1
        mode = "zoom_in" if n % 2 else "zoom_out"

    # 先放大再推拉，避免边缘露出黑边（-2 保证偶数尺寸）
    sw, sh = int(width * 1.25) // 2 * 2, int(height * 1.25) // 2 * 2
    vf = (
        f"scale={sw}:{sh}:flags=lanczos,"
        f"zoompan=z='{zoom_expr(mode, zoom_total)}'"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d=1:s={width}x{height}:fps={fps},"
        f"format=yuv420p"
    )

    cmd = [
        ffmpeg, "-y",
        "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}",
        "-i", str(still),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(dest),
    ]
    run(cmd)

    real = probe_duration(dest, ffmpeg)
    if abs(real - duration) > 0.5:
        log(f"  !! 时长偏差较大：期望 {duration:.2f}s 实得 {real:.2f}s（{dest.name}）")
    return dest


def extend_clip(
    clip: str | Path,
    dest: str | Path,
    *,
    target: float,
    ffmpeg: str,
) -> Path:
    """把视频补尾帧延到 target 秒（配音比画面长时用）。"""
    dest = Path(dest)
    dur = probe_duration(clip, ffmpeg)
    extra = round(target - dur, 4)
    if extra <= 0.001:
        os.replace(clip, dest)
        return dest
    run([
        ffmpeg, "-y", "-i", str(clip),
        "-vf", f"tpad=stop_mode=add:stop_duration={extra}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(dest),
    ])
    return dest
