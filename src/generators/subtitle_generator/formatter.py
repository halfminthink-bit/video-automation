"""
字幕フォーマット出力

SRT形式、JSON形式などへの変換を行う。
"""

from typing import List, Dict, Any, Optional
import logging

from ..core.models import SubtitleEntry


class SubtitleFormatter:
    """
    字幕フォーマット出力

    責任:
    - SRT形式への変換
    - ASS形式への変換（将来）
    - タイミングJSONの生成

    変更頻度: 中（新しいフォーマット追加時）
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            config: subtitle_generation.yamlの設定
            logger: ロガー
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def to_srt(self, subtitles: List[SubtitleEntry]) -> str:
        """
        SRT形式の文字列を生成

        Args:
            subtitles: 字幕リスト

        Returns:
            SRT形式の文字列
        """
        srt_lines = []

        for subtitle in subtitles:
            # インデックス
            srt_lines.append(f"{subtitle.index}\n")

            # タイムコード（HH:MM:SS,mmm形式）
            start_str = self._format_srt_time(subtitle.start_time)
            end_str = self._format_srt_time(subtitle.end_time)
            srt_lines.append(f"{start_str} --> {end_str}\n")

            # テキスト（2行まで）
            srt_lines.append(f"{subtitle.text_line1}\n")
            if subtitle.text_line2:
                srt_lines.append(f"{subtitle.text_line2}\n")

            # 空行
            srt_lines.append("\n")

        return ''.join(srt_lines)

    def _format_srt_time(self, seconds: float) -> str:
        """秒数をSRT形式（HH:MM:SS,mmm）に変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def to_timing_json(
        self,
        subtitles: List[SubtitleEntry],
        subject: str
    ) -> Dict[str, Any]:
        """
        タイミングJSON形式のデータを生成

        Args:
            subtitles: 字幕リスト
            subject: 対象人物名

        Returns:
            タイミングJSONデータ
        """
        timing_data = {
            "subject": subject,
            "subtitle_count": len(subtitles),
            "total_duration": max([s.end_time for s in subtitles]) if subtitles else 0,
            "subtitles": [
                {
                    "index": s.index,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.end_time - s.start_time,
                    "text_line1": s.text_line1,
                    "text_line2": s.text_line2
                }
                for s in subtitles
            ]
        }

        return timing_data
