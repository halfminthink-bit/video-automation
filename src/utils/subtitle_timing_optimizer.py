"""
字幕タイミング最適化ユーティリティ

Phase06から分離された字幕タイミング調整ロジック。
"""

import logging
from typing import List, Dict, Any

from src.core.models import SubtitleEntry


class SubtitleTimingOptimizer:
    """字幕タイミング最適化クラス

    責務:
    - 句点での表示延長
    - 字幕の表示時間を延長（次の字幕の直前まで）
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Args:
            config: 字幕設定（phase_config相当）
            logger: ロガー
        """
        self.config = config
        self.logger = logger

    def adjust_subtitle_timing_with_sentence_end(
        self,
        subtitles: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        全ての字幕を次の字幕直前まで延長して黒画面時間を最小化する

        ルール:
        1. 字幕の開始時刻は絶対に変更しない（ElevenLabs FA通り）
        2. 句点（。！？）で終わる場合は次の字幕開始の next_start_margin 秒前まで延長
        3. 句点で終わらない場合は次の字幕開始の minimal_gap 秒前まで延長

        Args:
            subtitles: 調整前の字幕リスト

        Returns:
            調整後の字幕リスト
        """
        # 設定を取得
        extension_config = self.config.get("sentence_end_extension", {})
        enabled = extension_config.get("enabled", True)
        next_start_margin = extension_config.get("next_start_margin", 0.3)
        # 1フレーム分の時間を算出（デフォルト30fps）
        fps = (
            self.config.get("output", {}).get("fps")
            or self.config.get("fps")
            or 30
        )
        frame_duration = 1.0 / float(fps)
        minimal_gap = frame_duration  # 句点以外は「次字幕の1フレーム前」まで表示

        if not enabled:
            self.logger.info("Sentence end extension is disabled")
            return subtitles

        self.logger.info(
            f"Adjusting subtitle timing (punctuation margin={next_start_margin}s, minimal gap=1frame={minimal_gap:.3f}s @ {fps}fps)"
        )

        adjusted = []
        extended_count = 0

        for i, sub in enumerate(subtitles):
            # 全行のテキストを結合して句点判定
            full_text = sub.text_line1
            if sub.text_line2:
                full_text += sub.text_line2

            # デフォルトは元の終了時刻
            new_end = sub.end_time

            # 🔍 デバッグログ: テキスト末尾と句点判定
            trimmed = full_text.rstrip()
            end_snippet = trimmed[-5:] if len(trimmed) >= 5 else trimmed
            ends_with_punct = trimmed.endswith(('。', '！', '？'))
            self.logger.debug(
                f"字幕 {sub.index}: 末尾='{end_snippet}' (句点判定: {ends_with_punct})"
            )

            # 次の字幕が存在する場合は延長/縮小を検討
            if i < len(subtitles) - 1:
                next_start = subtitles[i + 1].start_time
                margin = next_start_margin if ends_with_punct else minimal_gap
                candidate_end = next_start - margin

                # 安全下限: 開始より僅かに後ろ（半フレーム）
                safe_min = max(1e-3, frame_duration * 0.5)
                min_end = sub.start_time + safe_min
                # 上限: 次字幕の直前（1フレーム or 指定マージン）
                max_end = candidate_end

                # new_end を [min_end, max_end] に収める
                proposed = max(min_end, min(max_end, sub.end_time if sub.end_time > min_end else min_end))

                # もし元の end が範囲外なら調整・カウント
                if abs(proposed - sub.end_time) > 1e-6:
                    old_end = sub.end_time
                    new_end = proposed
                    # 延長 or 縮小のラベル
                    action = "延長" if new_end > old_end else "縮小"
                    extended_count += 1 if new_end > old_end else 0
                    self.logger.debug(
                        f"字幕 {sub.index}: {'句点' if ends_with_punct else '通常'}{action} "
                        f"{old_end:.3f}秒 → {new_end:.3f}秒 "
                        f"({('+' if new_end-old_end>=0 else '')}{new_end - old_end:.3f}秒, margin={margin:.3f}s)"
                    )
            else:
                # 最後の字幕：句点で終わる場合は少し延長（任意）
                if ends_with_punct:
                    extension = 0.5
                    new_end = sub.end_time + extension
                    extended_count += 1
                    self.logger.debug(f"字幕 {sub.index} (最終): 句点延長 +{extension:.2f}秒")

            # 新しい字幕エントリを作成
            adjusted_sub = SubtitleEntry(
                index=sub.index,
                start_time=sub.start_time,  # 開始は絶対に変更しない
                end_time=new_end,           # ルールに応じて延長/調整
                text_line1=sub.text_line1,
                text_line2=sub.text_line2
            )
            adjusted.append(adjusted_sub)

        self.logger.info(
            f"Subtitle timing adjustment complete: {extended_count}/{len(subtitles)} subtitles extended"
        )
        return adjusted

    def extend_subtitle_display(self, subtitles: List[SubtitleEntry]) -> List[SubtitleEntry]:
        """
        字幕の表示時間を延長（次の字幕の0.2秒前まで）

        Args:
            subtitles: 字幕エントリのリスト

        Returns:
            調整済み字幕エントリのリスト
        """
        adjusted_subtitles = []
        extended_count = 0

        for i, subtitle in enumerate(subtitles):
            # 最後の字幕以外
            if i < len(subtitles) - 1:
                next_subtitle = subtitles[i + 1]

                # 次の字幕開始の0.2秒前まで延長可能
                max_end_time = next_subtitle.start_time - 0.2

                # 現在の終了時間と比較して長い方を採用
                if subtitle.end_time < max_end_time:
                    old_end = subtitle.end_time
                    subtitle = SubtitleEntry(
                        index=subtitle.index,
                        start_time=subtitle.start_time,
                        end_time=max_end_time,
                        text_line1=subtitle.text_line1,
                        text_line2=subtitle.text_line2
                    )
                    extended_count += 1
                    self.logger.debug(
                        f"Extended subtitle {i+1}: "
                        f"{subtitle.start_time:.2f}s - {old_end:.2f}s -> {subtitle.end_time:.2f}s "
                        f"(extended by {max_end_time - old_end:.2f}s)"
                    )

            adjusted_subtitles.append(subtitle)

        self.logger.info(
            f"Extended subtitle display times: {extended_count}/{len(subtitles)} subtitles extended "
            f"(0.2s margin before next)"
        )
        return adjusted_subtitles
