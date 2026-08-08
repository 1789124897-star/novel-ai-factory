"""时间戳文本 → SRT 转换器。

将 TurboScribe 风格原始转录::

    (0:03) 我推开那扇沉重的橡木门。
    (0:45) 空气中弥漫着霉味和铁锈的气息。

转换为标准 SRT 字幕文件，并智能分句。
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class TxtToSrt:
    """将带时间戳的转录文本转为 SRT 格式。"""

    def __init__(self, max_len: int = 15, min_duration: float = 1.0):
        self.max_len = max_len
        self.min_duration = min_duration

    # ── 时间格式化 ──────────────────────────────────────

    @staticmethod
    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d},000"

    # ── 文本分割 ────────────────────────────────────────

    def _split_text(self, text: str) -> list[str]:
        """按中文标点分割，再按 *max_len* 截断。"""
        parts = re.split(r"[，。！？]", text)
        result = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if len(p) <= self.max_len:
                result.append(p)
            else:
                for i in range(0, len(p), self.max_len):
                    result.append(p[i : i + self.max_len])
        return result

    # ── 解析 ────────────────────────────────────────────

    def parse(self, text: str) -> list[tuple[float, str]]:
        """解析 ``(min:sec) 内容`` 行为 ``(秒数, 文本)`` 对。"""
        # 在每个时间戳前强制换行
        text = re.sub(r"\((\d+:\d+)\)", r"\n(\1)", text)

        pattern = re.compile(r"\((\d+):(\d+)\)\s*(.*)")
        data = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = pattern.match(line)
            if not m:
                continue
            minute, second, content = int(m.group(1)), int(m.group(2)), m.group(3)
            data.append((minute * 60 + second, content))

        return data

    # ── 转换 ────────────────────────────────────────────

    def convert(self, text: str) -> str:
        """将原始转录文本转为 SRT 格式字符串。"""
        entries = self.parse(text)
        srt_lines = []
        idx = 1

        for i, (start_sec, content) in enumerate(entries):
            end_sec = entries[i + 1][0] if i < len(entries) - 1 else start_sec + 4

            sentences = self._split_text(content)
            duration = (end_sec - start_sec) / len(sentences)
            if duration < self.min_duration:
                duration = self.min_duration

            for j, sentence in enumerate(sentences):
                s = start_sec + j * duration
                e = s + duration
                srt_lines.append(str(idx))
                srt_lines.append(f"{self._format_time(s)} --> {self._format_time(e)}")
                srt_lines.append(sentence)
                srt_lines.append("")
                idx += 1

        return "\n".join(srt_lines)

    def convert_file(self, input_path: Path, output_path: Path) -> Path:
        raw = input_path.read_text(encoding="utf-8")
        srt = self.convert(raw)
        output_path.write_text(srt, encoding="utf-8")
        logger.info("SRT 已保存 → %s", output_path)
        return output_path
