"""腾讯云 TTS 引擎 — 合成、合并、BGM 混音。"""

from __future__ import annotations

import base64
import logging
import math
import re
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from pydub import AudioSegment
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tts.v20190823 import models, tts_client

from .splitter import TextSegmenter

if TYPE_CHECKING:
    from ..core.config import Settings
    from ..core.paths import PathConfig

logger = logging.getLogger(__name__)


class TTSEngine:
    """基于腾讯云 TTS 的文字转语音合成。

    用法::

        engine = TTSEngine(settings, paths)
        client = engine.init_client()
        segments = engine.split(novel_text)
        engine.save_preview(segments)

        for seg in segments:
            engine.synthesize(client, seg["text"], seg["segment_id"])

        engine.merge(paths.merged_audio)
        engine.mix_bgm(paths.merged_audio, paths.bgm_path, paths.final_mixed_audio)
    """

    def __init__(self, settings: "Settings", paths: "PathConfig"):
        self.settings = settings
        self.paths = paths
        self._splitter = TextSegmenter(
            max_length=settings.MAX_SEGMENT_LENGTH,
            min_hope=settings.MIN_HOPE_LENGTH,
            min_force_merge=settings.MIN_FORCE_MERGE_LENGTH,
            strong_end=settings.STRONG_END,
            medium_split=settings.MEDIUM_SPLIT,
            weak_split=settings.WEAK_SPLIT,
        )

    # ── TTS 客户端 ──────────────────────────────────────

    def init_client(self) -> tts_client.TtsClient:
        http = HttpProfile(endpoint="tts.tencentcloudapi.com", reqTimeout=30)
        cp = ClientProfile(httpProfile=http)
        cred = credential.Credential(
            self.settings.TENCENT_SECRET_ID, self.settings.TENCENT_SECRET_KEY
        )
        client = tts_client.TtsClient(cred, self.settings.TENCENT_REGION, cp)
        logger.info("TTS 客户端就绪")
        return client

    # ── 文件读写 ────────────────────────────────────────

    @staticmethod
    def load_novel(path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(f"小说文件未找到: {path}")
        return path.read_text(encoding="utf-8").strip()

    # ── 文本分割 ────────────────────────────────────────

    def split(self, content: str) -> list[dict]:
        return self._splitter.segment(content)

    def save_preview(self, segments: list[dict]) -> Path:
        preview = self.paths.preview_file
        with open(preview, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"[{seg['segment_id']}]\n{seg['text']}\n\n")
        logger.info("预览已保存 → %s", preview)
        return preview

    # ── 逐段合成 ────────────────────────────────────────

    def synthesize(
        self, client: tts_client.TtsClient, text: str, segment_id: int
    ) -> Path | None:
        file_path = self.paths.tts_seg_list_dir / f"segment_{segment_id:03d}.mp3"
        # 确保 segments 目录存在（可能尚未创建）
        self.paths.tts_seg_list_dir.mkdir(parents=True, exist_ok=True)
        if file_path.exists():
            logger.info("片段 %d 已存在 — 跳过", segment_id)
            return file_path

        req = models.TextToVoiceRequest()
        req.Text = text
        req.VoiceType = self.settings.TTS_VOICE_ID
        req.Speed = self.settings.TTS_SPEED
        req.Volume = self.settings.TTS_VOLUME
        req.SampleRate = self.settings.TTS_SAMPLE_RATE
        req.Codec = self.settings.TTS_CODEC
        req.SessionId = f"seg_{segment_id}_{uuid.uuid4().hex[:8]}"

        for attempt in range(1, 4):
            try:
                resp = client.TextToVoice(req)
                if not resp.Audio:
                    raise RuntimeError("Empty audio response")
                file_path.write_bytes(base64.b64decode(resp.Audio))
                logger.info("片段 %d 合成完成 (第 %d 次)", segment_id, attempt)
                # 成功合成后限速
                time.sleep(self.settings.SLEEP_BETWEEN_REQUESTS)
                return file_path
            except TencentCloudSDKException as e:
                if "InvalidParameter" in str(e):
                    logger.error("片段 %d — 参数无效，终止: %s", segment_id, e)
                    break
                logger.warning("片段 %d 第 %d 次失败: %s", segment_id, attempt, e)
                time.sleep(1.5 * attempt)

        logger.error("片段 %d 3 次尝试后仍失败", segment_id)
        return None

    # ── 合并 ───────────────────────────────────────────

    def merge(self, output_path: Path) -> None:
        entries = []
        for fp in self.paths.tts_seg_list_dir.iterdir():
            if not (fp.name.startswith("segment_") and fp.suffix == ".mp3"):
                continue
            m = re.search(r"segment_(\d+)", fp.name)
            if m:
                entries.append((int(m.group(1)), fp))

        if not entries:
            raise FileNotFoundError("未找到 segment_*.mp3 文件")

        entries.sort(key=lambda x: x[0])
        expected = set(range(1, entries[-1][0] + 1))
        found = {idx for idx, _ in entries}
        missing = expected - found
        if missing:
            raise FileNotFoundError(f"缺少片段: {sorted(missing)}")

        logger.info("正在合并 %d 个片段 …", len(entries))
        combined = AudioSegment.empty()
        for _, fp in entries:
            combined += AudioSegment.from_file(fp, format="mp3")

        combined.export(output_path, format="mp3")
        logger.info("已合并 → %s", output_path)

    # ── BGM 混音 ───────────────────────────────────────

    def mix_bgm(
        self, voice_path: Path, bgm_path: Path, output_path: Path
    ) -> Path | None:
        try:
            if not voice_path.exists():
                raise FileNotFoundError(f"语音文件未找到: {voice_path}")
            if not bgm_path.exists():
                raise FileNotFoundError(f"BGM 文件未找到: {bgm_path}")

            logger.info("正在加载音频 …")
            voice = AudioSegment.from_file(voice_path)
            bgm = AudioSegment.from_file(bgm_path)
            logger.info(
                "语音: %.1fs  BGM: %.1fs",
                len(voice) / 1000,
                len(bgm) / 1000,
            )

            # 正确的 dB 衰减
            db_change = 20 * math.log10(self.settings.BGM_VOLUME_RATIO)
            bgm = bgm + db_change
            logger.info("BGM 已调整 %.1f dB", db_change)

            voice_dur = len(voice)
            if len(bgm) < voice_dur:
                loops = math.ceil(voice_dur / len(bgm))
                bgm = (bgm * loops)[:voice_dur]
                logger.info("BGM 已循环 ×%d", loops)
            else:
                bgm = bgm[:voice_dur]
                logger.info("BGM 已裁剪")

            mixed = voice.overlay(bgm)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mixed.export(output_path, format="mp3", bitrate="320k")
            logger.info("混音完成 → %s", output_path)
            return output_path

        except Exception:
            logger.exception("BGM 混音失败")
            if output_path.exists() and output_path.stat().st_size < 1024:
                output_path.unlink()
            return None
