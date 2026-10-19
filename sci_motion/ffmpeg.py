"""ffmpeg 调用封装：时长探测、命令执行、滤镜辅助。"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

__all__ = ["run", "probe_duration", "FFmpegError"]


class FFmpegError(RuntimeError):
    """ffmpeg 返回非零退出码。"""


def run(cmd: list[str], quiet: bool = True) -> str:
    """执行 ffmpeg 命令，失败时抛出带尾部日志的异常。"""
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode != 0:
        tail = r.stdout[-2000:]
        raise FFmpegError(f"ffmpeg 执行失败：{' '.join(cmd[:6])} ...\n{tail}")
    if not quiet:
        print(r.stdout)
    return r.stdout


def probe_duration(path: str | Path, ffmpeg: str) -> float:
    """读取媒体时长（秒）。

    注意：`ffmpeg -i xxx` 不带输出文件时返回码非零但照样打印头部信息，
    所以这里单独处理返回码，不走 run()。
    """
    r = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stdout)
    if not m:
        raise FFmpegError(f"无法解析时长：{path}\n{r.stdout[-800:]}")
    h, mm, ss = m.groups()
    return float(h) * 3600 + float(mm) * 60 + float(ss)


def dump_json(obj: dict, path: str | Path) -> None:
    """写 JSON 中间产物，统一缩进与中文可读。"""
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
