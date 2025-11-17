"""
字幕生成モジュール

台本と音声タイミング情報から字幕を生成する。
"""

from typing import Dict, Any, Optional
import logging

from .text_splitter import TextSplitter
from .timing_processor import TimingProcessor
from .formatter import SubtitleFormatter
from .generator import SubtitleGenerator


def create_subtitle_generator(
    config: Dict[str, Any],
    logger: Optional[logging.Logger] = None
) -> SubtitleGenerator:
    """
    字幕生成器を作成（互換性維持用のファクトリー関数）

    Args:
        config: 字幕生成設定
        logger: ロガー

    Returns:
        SubtitleGenerator インスタンス

    Example:
        >>> from src.generators.subtitle_generator import create_subtitle_generator
        >>> generator = create_subtitle_generator(config, logger)
        >>> subtitles = generator.generate_subtitles_from_char_timings(audio_data)
    """
    return SubtitleGenerator(config=config, logger=logger)


# 公開API
__all__ = [
    "TextSplitter",
    "TimingProcessor",
    "SubtitleFormatter",
    "SubtitleGenerator",
    "create_subtitle_generator",
]
