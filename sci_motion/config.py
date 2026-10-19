"""配置加载、路径管理与 ffmpeg 自动发现。

配置是一个 JSON 文件（见 examples/config.example.json），缺失字段自动回填默认值，
因此最小可用配置只需要写 narration_file 和出图 provider。
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["Config", "load_config", "get_ffmpeg", "FFmpegNotFound"]

DEFAULTS: dict[str, Any] = {
    "project_dir": ".",          # 数据根目录，所有中间产物放这里
    "work_dir": "work",          # 相对于 project_dir
    "out_file": "out/final.mp4",  # 相对于 project_dir
    "narration_file": "examples/narration.example.json",
    "width": 1280,
    "height": 720,
    "fps": 25,
    "crf": 18,
    "abitrate": "192k",
    "voice": "zh-CN-XiaoxiaoNeural",
    "rate": "+8%",
    "sentence_sep": "。",         # 按此符号把解说词拆句，一句对应一段画面
    "sentences_per_theme": 3,      # 每个主题期望的句子数，不符则跳过并告警
    "xfade": 0.4,                 # 视频/音频交叉淡化时长（秒）
    "motion": {
        "mode": "auto",           # auto | zoom_in | zoom_out | pan
        "zoom": 0.12,             # 推拉幅度（相对倍数）
        "min_clip": 0.0,          # 每段画面最短时长，不足则补齐（秒）
    },
    "stills": {
        "provider": "synthetic",   # synthetic | local | command
        "options": {},
    },
}


class FFmpegNotFound(RuntimeError):
    """找不到可用的 ffmpeg 可执行文件。"""


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class Config:
    """强类型配置视图，同时保留原始 dict。"""

    raw: dict
    project_dir: Path

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    # ---------- 路径 ----------
    @property
    def work_dir(self) -> Path:
        return self.project_dir / self.raw["work_dir"]

    @property
    def audio_dir(self) -> Path:
        return self.work_dir / "audio"

    @property
    def stills_dir(self) -> Path:
        return self.work_dir / "stills"

    @property
    def clips_dir(self) -> Path:
        return self.work_dir / "clips"

    @property
    def themes_dir(self) -> Path:
        return self.work_dir / "themes"

    @property
    def out_file(self) -> Path:
        return self.project_dir / self.raw["out_file"]

    def ensure_dirs(self) -> None:
        for d in (self.audio_dir, self.stills_dir, self.clips_dir, self.themes_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.out_file.parent.mkdir(parents=True, exist_ok=True)


def load_config(path: str | os.PathLike) -> Config:
    """读取 JSON 配置并与默认值深度合并。"""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"配置文件不存在：{p}")
    user_cfg = json.loads(p.read_text(encoding="utf-8"))
    merged = _deep_merge(DEFAULTS, user_cfg)
    project_dir = Path(merged.get("project_dir", ".")).resolve()
    merged["project_dir"] = str(project_dir)
    return Config(raw=merged, project_dir=project_dir)


def get_ffmpeg() -> str:
    """按优先级返回可用的 ffmpeg：imageio-ffmpeg 静态包 > PATH > Windows 常见安装位置。"""
    try:
        import imageio_ffmpeg  # noqa: PLC0415

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    found = shutil.which("ffmpeg")
    if found:
        return found

    for cand in (
        r"C:/Program Files/ffmpeg/bin/ffmpeg.exe",
        r"C:/ffmpeg/bin/ffmpeg.exe",
    ):
        if os.path.exists(cand):
            return cand

    raise FFmpegNotFound(
        "未找到 ffmpeg：请执行 pip install imageio-ffmpeg，或把 ffmpeg 放进 PATH"
    )
