"""Edge TTS 语音合成服务 — 文本 → 音频 + SRT 字幕"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import edge_tts

from app.core.config import settings
from app.core.constants import OUTPUT_URL_PREFIX
from app.core.paths import PathConfig

logger = logging.getLogger(__name__)

os.environ.setdefault("NO_PROXY", "speech.platform.bing.com,*.bing.com")
os.environ.setdefault("no_proxy", "speech.platform.bing.com,*.bing.com")

TICKS_PER_SEC = 10_000_000


# ── 公开 API ──────────────────────────────────────────

class TTSService:
    """Edge TTS 语音合成服务。"""

    @staticmethod
    def output_url(rel_path: str) -> str:
        """output 目录下的文件 → 前端可访问 URL"""
        return f"{OUTPUT_URL_PREFIX}/tts/{rel_path}"

    @staticmethod
    async def synthesize(task_id: str, text: str, voice: str, rate: str) -> dict:
        """edge-tts 流式合成 → 写音频 + SRT，返回结果 dict。"""
        paths = PathConfig.from_settings(settings, theme="")
        audio_path = paths.tts_voice_file(task_id)
        srt_path = paths.tts_subtitle_file(task_id)

        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        audio_bytes = bytearray()
        boundaries: list[dict] = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.extend(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                boundaries.append({
                    "offset": chunk["offset"],
                    "duration": chunk["duration"],
                    "text": chunk["text"],
                })

        if not audio_bytes:
            raise RuntimeError("TTS 未返回音频数据")

        audio_path.write_bytes(audio_bytes)
        duration_sec = _write_srt(boundaries, srt_path)

        logger.info(
            "TTS 完成 task=%s duration=%.1fs path=%s",
            task_id, duration_sec, audio_path,
        )
        return {
            "audio_url": TTSService.output_url(f"{task_id}/{audio_path.name}"),
            "srt_url": TTSService.output_url(f"{task_id}/{srt_path.name}"),
            "duration_sec": round(duration_sec, 1),
        }


# ── SRT 生成 ─────────────────────────────────────────────────

# 断句标点（遇到就切）
_BREAK_CHARS = {"。", "！", "？", "!", "?", "，", ",", "：", "；"}

# 从句标点（切句后优先向前合并）
_OPEN_BREAKS = {"，", ","}

# 从句标点（强制分句，不合并）
_CLOSED_BREAKS = {"。", "！", "？", "!", "?"}

# 显示时删除的字符（句末标点 + 装饰符）
_STRIP_CHARS = {"。", "！", "？", "!", "?", "、", "：", "；", ".", "~", "～", "…"}

_MAX_CHARS = 14
_MERGE_MAX_CHARS = 14


def _write_srt(boundaries: list[dict], output_path: Path) -> float:
    """SentenceBoundary → 逐字均分时间 → 按标点切句 → 写 SRT 文件。"""
    if not boundaries:
        return 0.0

    # 逐字均分
    words: list[dict] = []
    for segment in boundaries:
        chars = list(segment["text"])
        if not chars:
            continue
        per_char = segment["duration"] / len(chars)
        for i, char in enumerate(chars):
            start = int(segment["offset"] + i * per_char)
            duration = int(segment["offset"] + segment["duration"] - start) if i == len(chars) - 1 else int(per_char)
            words.append({"start": start, "dur": max(duration, 1), "char": char})

    # 按标点断句
    chunks: list[dict] = []
    buffer: list[dict] = []
    for word in words:
        buffer.append(word)
        stripped = sum(1 for x in buffer if x["char"] not in _STRIP_CHARS)
        if word["char"] in _BREAK_CHARS or stripped >= _MAX_CHARS:
            break_char = word["char"] if word["char"] in _BREAK_CHARS else None
            chunks.append(_flush(buffer, break_char))
            buffer = []
    if buffer:
        chunks.append(_flush(buffer, None))

    # 逗号结尾向前合并
    merged: list[dict] = []
    for chunk in chunks:
        if (
            merged
            and chunk.get("break_char") in _OPEN_BREAKS
            and merged[-1].get("break_char") not in _CLOSED_BREAKS
            and len(merged[-1]["text"]) + len(chunk["text"]) <= _MERGE_MAX_CHARS
        ):
            merged[-1]["end"] = chunk["end"]
            merged[-1]["text"] += chunk["text"]
            merged[-1]["break_char"] = chunk.get("break_char")
        else:
            merged.append(chunk)

    # 写 SRT
    lines: list[str] = []
    for i, entry in enumerate(merged, 1):
        if not entry["text"]:
            continue
        start = entry["start"] / TICKS_PER_SEC
        end = entry["end"] / TICKS_PER_SEC
        lines.append(str(i))
        lines.append(f"{_format_srt(start)} --> {_format_srt(end)}")
        lines.append(entry["text"])
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("SRT 已生成: %s (%d 条)", output_path, len(lines) // 4)

    last = merged[-1]
    return last["end"] / TICKS_PER_SEC


def _flush(buffer: list[dict], break_char: Optional[str]) -> dict:
    start = buffer[0]["start"]
    last = buffer[-1]
    end = last["start"] + last["dur"]
    text = "".join(word["char"] for word in buffer if word["char"] not in _STRIP_CHARS)
    text = text.strip("，,")
    return {"start": start, "end": end, "text": text, "break_char": break_char}


def _format_srt(seconds: float) -> str:
    """秒 → SRT 时间戳 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
