"""静帧（每段画面的底图）获取。

三种 provider，覆盖从"零成本试跑"到"接自己的出图服务"：

- synthetic：ffmpeg 生成渐变色块，用于冒烟测试和占位，不需要 API key
- local   ：从本地目录按命名规则拷贝已有图片
- command ：调用外部命令/脚本出图（Agnes、SD、ComfyUI 等），最灵活

命名规则统一为 {theme}_s{i}.png。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

__all__ = ["ensure_still", "ensure_stills"]

FALLBACK_COLORS = [
    "#1b3a5c", "#123b32", "#4a2340", "#3d3314",
    "#4a1620", "#20264a", "#16323f", "#3a2a12",
]


def _render_synthetic(dest: Path, index: int, width: int, height: int, ffmpeg: str) -> None:
    """用 ffmpeg lavfi 画一张柔和渐变图，作为占位底图。"""
    import random  # noqa: PLC0415

    rnd = random.Random(index)
    c0 = FALLBACK_COLORS[index % len(FALLBACK_COLORS)]
    c1 = "#0a1018"
    x1, y1 = rnd.choice([(width, height), (width, 0), (0, height)])
    # 先用 gradients 画渐变；老版本 ffmpeg 没有该滤镜时退化为纯色 + 噪点
    vf = f"gradients=s={width}x{height}:c0={c0}:c1={c1}:x0=0:y0=0:x1={x1}:y1={y1},gblur=sigma=18"
    cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", f"color=c={c0}:s={width}x{height}:d=1",
           "-vf", vf, "-frames:v", "1", str(dest)]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0 or not dest.exists():
        cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", f"color=c={c0}:s={width}x{height}:d=1",
               "-frames:v", "1", str(dest)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def ensure_still(
    provider: str,
    dest: str | Path,
    *,
    index: int,
    theme: str,
    prompt: str,
    width: int,
    height: int,
    options: dict | None = None,
    ffmpeg: str | None = None,
    log: Callable[[str], None] = print,
) -> Path:
    """确保目标静帧存在，返回其路径。已存在则直接返回（幂等）。"""
    options = options or {}
    ctx = {**options, "theme": theme, "i": index + 1}
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    if provider == "synthetic":
        if not dest.exists():
            if not ffmpeg:
                raise ValueError("synthetic provider 需要传入 ffmpeg 路径")
            _render_synthetic(dest, index, width, height, ffmpeg)
    elif provider == "local":
        src_dir = Path(options["dir"])
        pattern = options.get("pattern", "{theme}_s{i}.*")
        matches = sorted(src_dir.glob(pattern.format(**ctx)))
        if not matches:
            raise FileNotFoundError(
                f"local provider 未找到匹配图片：{src_dir / pattern.format(**ctx)}"
            )
        shutil.copyfile(matches[0], dest)
    elif provider == "command":
        tmpl = options["template"]
        cmd = tmpl.format(
            output=str(dest), prompt=prompt, index=index,
            width=width, height=height, theme=theme, i=index + 1,
        )
        env = os.environ.copy()
        env.update(options.get("env", {}))
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
        if r.returncode != 0:
            raise RuntimeError(f"出图命令失败：{cmd}\n{r.stderr[-800:]}")
    else:
        raise ValueError(f"未知 provider：{provider}")

    log(f"  静帧就绪 {dest.name}")
    return dest


def ensure_stills(
    provider: str,
    jobs: list[dict],
    *,
    width: int,
    height: int,
    options: dict | None = None,
    ffmpeg: str | None = None,
) -> list[Path]:
    """批量准备静帧。jobs 需含 name / theme / dest / prompt 四个键。"""
    return [
        ensure_still(
            provider, job["dest"], index=i, theme=job["theme"],
            prompt=job["prompt"],
            width=width, height=height, options=options, ffmpeg=ffmpeg,
        )
        for i, job in enumerate(jobs)
    ]
