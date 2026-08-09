"""Edge TTS 语音合成服务 — 文本 → 音频 + SRT 字幕"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import edge_tts

logger = logging.getLogger(__name__)

# Edge TTS WebSocket 服务不走代理
os.environ.setdefault("NO_PROXY", "speech.platform.bing.com,*.bing.com")
os.environ.setdefault("no_proxy", "speech.platform.bing.com,*.bing.com")

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
DEFAULT_RATE = "+0%"

TICKS_PER_SEC = 10_000_000

# ── 输出目录 ─────────────────────────────────────────────────

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "tts"


def output_url(rel_path: str) -> str:
    """output 目录下的文件 → 前端可访问 URL"""
    return f"/output/tts/{rel_path}"


async def _synthesize(task_id: str, text: str, voice: str, rate: str) -> dict:
    """edge-tts 流式合成 → 写音频 + SRT，返回结果 dict。"""
    task_dir = OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    audio_path = task_dir / "voice.mp3"
    srt_path = task_dir / "subtitle.srt"

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

    # 生成 SRT
    duration_sec = _write_srt(boundaries, srt_path)

    logger.info(
        "TTS 完成 task=%s duration=%.1fs path=%s",
        task_id, duration_sec, audio_path,
    )
    return {
        "audio_url": output_url(f"{task_id}/voice.mp3"),
        "srt_url": output_url(f"{task_id}/subtitle.srt"),
        "duration_sec": round(duration_sec, 1),
    }


# ── SRT 生成 ─────────────────────────────────────────────────

_PUNCTUATION = {"。", "！", "？", "!", "?", "，", ",", "、", "：", "；", ".", "~", "～", "…"}
_MAX_CHARS = 12
_CLOSED_BREAKS = {"。", "！", "？", "!", "?"}
_OPEN_BREAKS = {"，", ","}
_BREAKS = _CLOSED_BREAKS | _OPEN_BREAKS


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
        stripped = sum(1 for x in buffer if x["char"] not in _PUNCTUATION)
        if word["char"] in _BREAKS or stripped >= _MAX_CHARS:
            break_char = word["char"] if word["char"] in _BREAKS else None
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
            and len(merged[-1]["text"]) + len(chunk["text"]) <= _MAX_CHARS
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
    text = "".join(word["char"] for word in buffer if word["char"] not in _PUNCTUATION)
    return {"start": start, "end": end, "text": text, "break_char": break_char}


def _format_srt(seconds: float) -> str:
    """秒 → SRT 时间戳 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
