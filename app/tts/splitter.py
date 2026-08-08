"""TTS 中文智能文本分割器 — 引号感知、三级切割规则。

逐字符遍历文本，跟踪中文引号（""），按三个优先级分割：

1. **强终止** — ``。？！…～``（引号外始终分割）
2. **中分割** — ``；：—━``（缓冲区足够长时分割）
3. **弱分割** — ``，、``（舒适阅读长度时分割）

短片段（< ``min_force_merge_length``）合并回相邻段。
"""

import re


class TextSegmenter:
    """将中文散文分割为适合 TTS 的片段。"""

    def __init__(
        self,
        max_length: int = 140,
        min_hope: int = 55,
        min_force_merge: int = 35,
        strong_end: str = r"[。？！…～]",
        medium_split: str = r"[；：—━]",
        weak_split: str = r"[，、]",
    ):
        self.max_length = max_length
        self.min_hope = min_hope
        self.min_force_merge = min_force_merge
        self.strong_end = strong_end
        self.medium_split = medium_split
        self.weak_split = weak_split

    # ── 公开 API ────────────────────────────────────────

    def segment(self, text: str) -> list[dict]:
        """将 *text* 分割为带顺序 ID 的片段。

        Returns:
            ``[{"segment_id": 1, "text": "..."}, ...]``
        """
        if not text.strip():
            return []

        raw = self._split(text)
        merged = self._merge_short(raw)
        return [
            {"segment_id": i, "text": t} for i, t in enumerate(merged, 1)
        ]

    # ── 核心分割逻辑 ────────────────────────────────────

    def _split(self, text: str) -> list[str]:

        segments: list[str] = []
        buffer = ""
        in_quote = False

        for idx, char in enumerate(text):
            buffer += char

            if char == "“":  # "
                in_quote = True
            elif char == "”":  # "
                in_quote = False

            next_char = text[idx + 1] if idx + 1 < len(text) else ""

            # 第 1 级：强终止（引号外始终分割）
            if len(buffer) >= self.max_length:
                should_split = True
            elif (
                not in_quote
                and re.match(self.strong_end, char)
                and next_char not in "”）)]"
            ):
                should_split = True
            elif (
                not in_quote
                and re.match(self.medium_split, char)
                and len(buffer) >= self.min_hope * 0.8
            ):
                should_split = True
            elif (
                not in_quote
                and re.match(self.weak_split, char)
                and len(buffer) >= self.min_hope
            ):
                should_split = True
            elif char == "”" and len(buffer) >= self.min_hope:
                should_split = True
            else:
                should_split = False

            if should_split:
                segments.append(buffer.strip())
                buffer = ""

        if buffer.strip():
            segments.append(buffer.strip())

        return segments

    # ── 短片段合并 ──────────────────────────────────────

    def _merge_short(self, segments: list[str]) -> list[str]:
        merged: list[str] = []
        current = ""

        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            if not current:
                current = seg
                continue

            if len(seg) < self.min_force_merge:
                if len(current) + len(seg) <= self.max_length:
                    current += seg
                else:
                    merged.append(current)
                    current = seg
                continue

            if len(current) + len(seg) <= self.max_length:
                if current.endswith(("。", "！", "？", "”")):
                    merged.append(current)
                    current = seg
                else:
                    current += seg
            else:
                merged.append(current)
                current = seg

        if current:
            merged.append(current)

        return merged
