"""中文配音（edge-tts）。

微软在 2026-10 前后迁移了端点，这里做双主机容错：
首选 api.msedgeservices.com，握手失败回退 speech.platform.bing.com。
"""
from __future__ import annotations

import asyncio
from typing import Iterable

__all__ = ["synth_file", "synthesize_all", "split_sentences", "TTSError"]


class TTSError(RuntimeError):
    """所有可用主机都合成失败。"""


_NEW_HOST_TMPL = (
    "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
    "?Ocp-Apim-Subscription-Key={token}"
)
_LEGACY_HOST_TMPL = (
    "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1"
    "?TrustedClientToken={token}"
)


def _hosts():
    import edge_tts.communicate as cm  # noqa: PLC0415
    from aiohttp import WSServerHandshakeError  # noqa: PLC0415
    from edge_tts.constants import TRUSTED_CLIENT_TOKEN  # noqa: PLC0415

    return cm, WSServerHandshakeError, [
        _NEW_HOST_TMPL.format(token=TRUSTED_CLIENT_TOKEN),
        _LEGACY_HOST_TMPL.format(token=TRUSTED_CLIENT_TOKEN),
    ]


async def synth_file(text: str, voice: str, rate: str, dest: str) -> str:
    """合成单句到 mp3，返回实际使用的主机（便于排查网络问题）。"""
    import edge_tts  # noqa: PLC0415

    cm, handshake_err, hosts = _hosts()
    last: Exception | None = None
    for url in hosts:
        cm.WSS_URL = url
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(dest)
            return url.split("?")[0]
        except handshake_err as e:  # 端点不可达，换下一个
            last = e
    raise TTSError(f"配音失败（已尝试 {len(hosts)} 个主机）：{last}")


def split_sentences(text: str, sep: str = "。") -> list[str]:
    """按句号拆句，末尾补回句号，保证朗读停顿自然。"""
    parts = [p.strip() for p in text.split(sep) if p.strip()]
    return [p + sep for p in parts]


async def _worker(items, voice: str, rate: str, force: bool, limit: int):
    import os

    for name, sentence, dest in items:
        if (
            not force
            and os.path.exists(dest)
            and os.path.getsize(dest) > 3000  # 小于 3KB 基本是空音频或错误页
        ):
            yield name, dest, "skip"
            continue
        sem = asyncio.Semaphore(limit)
        async with sem:
            host = await synth_file(sentence, voice, rate, dest)
            yield name, dest, host


async def _run(items, voice: str, rate: str, force: bool, limit: int):
    results = []
    async for r in _worker(items, voice, rate, force, limit):
        results.append(r)
    return results


def synthesize_all(
    items: Iterable[tuple[str, str, str]],
    voice: str,
    rate: str,
    force: bool = False,
    concurrency: int = 4,
) -> list[tuple[str, str, str]]:
    """批量合成。

    items: [(展示名, 句子文本, 输出路径)]
    返回 [(展示名, 输出路径, 结果)]，结果为 'skip' 或实际主机名。
    """
    return asyncio.run(_run(list(items), voice, rate, force, concurrency))
