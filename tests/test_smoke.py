"""冒烟测试：不需要网络，只用 ffmpeg 造素材，验证组装链路可用。

    python -m pytest tests -q
    # 或不用 pytest：
    python tests/test_smoke.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sci_motion.assemble import assemble_final, assemble_theme  # noqa: E402
from sci_motion.config import get_ffmpeg  # noqa: E402
from sci_motion.motion import build_clip, zoom_expr  # noqa: E402
from sci_motion.stills import ensure_still  # noqa: E402
from sci_motion.tts import split_sentences  # noqa: E402


def test_split_sentences():
    parts = split_sentences("第一句。第二句。第三句。", "。")
    assert parts == ["第一句。", "第二句。", "第三句。"]


def test_zoom_expr():
    assert "min(" in zoom_expr("zoom_in", 0.12)
    assert "max(" in zoom_expr("zoom_out", 0.12)
    assert zoom_expr("pan", 0.12).startswith("1.1")
    try:
        zoom_expr("bogus", 0.1)
    except ValueError:
        pass
    else:
        raise AssertionError("未知模式应抛错")


def test_end_to_end_two_shots():
    """两张静帧 -> 两段片段 -> 一个主题 -> 成片（含音频轨道）。"""
    ff = get_ffmpeg()
    tmp = Path(tempfile.mkdtemp(prefix="scimp_"))
    try:
        audio = tmp / "a.m4a"
        subprocess.run(  # 用 ffmpeg 造一段静音，模拟已存在的配音
            [ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
             "-t", "3", "-c:a", "aac", str(audio)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
        )
        shots = []
        for i in (1, 2):
            still = ensure_still(
                "synthetic", tmp / f"demo_s{i}.png", index=i - 1, theme="demo",
                prompt="", width=640, height=360, ffmpeg=ff, log=lambda m: None,
            )
            clip = build_clip(
                still, tmp / f"demo_s{i}.mp4", duration=3.0, width=640, height=360,
                fps=25, ffmpeg=ff, log=lambda m: None,
            )
            shots.append(clip)

        theme = tmp / "demo.mp4"
        dur = assemble_theme(
            "demo", shots, [audio, audio], theme, ffmpeg=ff,
            xfade=0.4, crf=28, abitrate="96k", log=lambda m: None,
        )
        assert 5.0 < dur < 6.5, f"两段 3s 交叉 0.4s 后应约 5.6s，实得 {dur}"

        final = tmp / "final.mp4"
        total = assemble_final(
            [theme], {"demo": dur}, final, ffmpeg=ff,
            xfade=0.4, crf=28, abitrate="96k", log=lambda m: None,
        )
        assert final.exists() and final.stat().st_size > 1000
        assert 5.0 < total < 6.5
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_split_sentences()
    test_zoom_expr()
    test_end_to_end_two_shots()
    print("smoke ok")
