"""管线阶段枚举 — 所有工作流的构建块。"""

from enum import Enum


class Stage(Enum):
    """各管线阶段。可按任意顺序组合运行。"""

    COMPILE = "compile"  # 编译叙事内核
    GENERATE = "generate"  # 四阶段小说生成（起承转合）
    TTS = "tts"  # 文本转语音合成
    MIX_BGM = "mix-bgm"  # 语音 + 背景音乐混音
    TRANSCRIBE = "transcribe"  # TurboScribe 字幕转录
    MAKE_VIDEO = "make-video"  # 背景视频拼接
    SUBTITLE = "subtitle"  # 字幕叠加
    WATERMARK = "watermark"  # FFmpeg 文字水印叠加

    @classmethod
    def full_pipeline(cls) -> list["Stage"]:
        """返回默认全流程阶段顺序。"""
        return list(cls)
