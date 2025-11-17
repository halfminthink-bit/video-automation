"""
タイミング調整ロジック

字幕の表示時間を調整する。
重なり防止、句点での延長、ギャップ最適化など。
"""

from typing import List, Dict, Any, Optional
import logging

from src.core.models import SubtitleEntry


class TimingProcessor:
    """
    タイミング調整（言語非依存）

    責任:
    - セクションタイミングの正規化（無音除去）
    - 最小/最大表示時間の適用
    - 重なり防止
    - 句点での延長
    - ギャップ最適化

    変更頻度: 低
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

        # タイミング設定
        timing = config.get("timing", {})
        self.min_display_duration = timing.get("min_display_duration", 1.0)
        self.max_display_duration = timing.get("max_display_duration", 6.0)
        self.prevent_overlap = timing.get("prevent_overlap", True)
        self.overlap_priority = timing.get("overlap_priority", "next_subtitle")

        # 句点延長設定
        sentence_end = config.get("sentence_end_extension", {})
        self.sentence_end_enabled = sentence_end.get("enabled", True)
        self.next_start_margin = sentence_end.get("next_start_margin", 0.3)

        # FPS設定（ギャップ計算用）
        self.fps = config.get("video", {}).get("fps") or config.get("fps", 30)
        self.frame_duration = 1.0 / self.fps

    def normalize_section_timing(
        self,
        section_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        セクションのタイミングを正規化（無音除去）

        最初の文字の開始時刻が0秒より大きい場合、
        全てのタイミングをシフトして0秒から始まるようにする。

        Args:
            section_data: セクションのタイミング情報

        Returns:
            正規化されたセクションデータ
        """
        char_start_times = section_data.get('char_start_times', [])
        char_end_times = section_data.get('char_end_times', [])

        if not char_start_times:
            return section_data

        # 最初の文字の開始時間（無音部分）
        first_char_start = min(char_start_times)

        if first_char_start > 0.1:  # 0.1秒以上の無音がある場合
            self.logger.info(
                f"Section {section_data.get('section_id')}: "
                f"Removing {first_char_start:.2f}s leading silence"
            )

            # タイミングを正規化
            normalized_data = section_data.copy()
            normalized_data['char_start_times'] = [
                t - first_char_start for t in char_start_times
            ]
            normalized_data['char_end_times'] = [
                t - first_char_start for t in char_end_times
            ]
            normalized_data['duration'] = (
                section_data.get('duration', 0) - first_char_start
            )

            return normalized_data

        return section_data

    def extend_sentence_endings(
        self,
        subtitles: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        句点で終わる字幕を延長

        ルール:
        - 句点（。！？）で終わる: 次の字幕開始の next_start_margin 秒前まで延長
        - 句点以外: 次の字幕開始の minimal_gap 秒前まで延長

        Args:
            subtitles: 字幕リスト

        Returns:
            調整済み字幕リスト
        """
        if not self.sentence_end_enabled:
            self.logger.info("Sentence end extension is disabled")
            return subtitles

        minimal_gap = self.frame_duration  # 句点以外は「次字幕の1フレーム前」まで表示

        self.logger.info(
            f"Adjusting subtitle timing (punctuation margin={self.next_start_margin}s, "
            f"minimal gap=1frame={minimal_gap:.3f}s @ {self.fps}fps)"
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

            # テキスト末尾と句点判定
            trimmed = full_text.rstrip()
            end_snippet = trimmed[-5:] if len(trimmed) >= 5 else trimmed
            ends_with_punct = trimmed.endswith(('。', '！', '？'))
            self.logger.debug(
                f"字幕 {sub.index}: 末尾='{end_snippet}' (句点判定: {ends_with_punct})"
            )

            # 次の字幕が存在する場合は延長/縮小を検討
            if i < len(subtitles) - 1:
                next_start = subtitles[i + 1].start_time
                margin = self.next_start_margin if ends_with_punct else minimal_gap
                candidate_end = next_start - margin

                # 安全下限: 開始より僅かに後ろ（半フレーム）
                safe_min = max(1e-3, self.frame_duration * 0.5)
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

    def optimize_gaps(
        self,
        subtitles: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        字幕間のギャップを最適化

        0.5~1.5秒のギャップがある場合、0.3秒になるように
        前の字幕を延長する。

        Args:
            subtitles: 字幕リスト

        Returns:
            調整済み字幕リスト
        """
        optimized_subtitles = []
        adjusted_count = 0

        for i in range(len(subtitles)):
            current = subtitles[i]

            # 最後の字幕以外
            if i < len(subtitles) - 1:
                next_subtitle = subtitles[i + 1]

                # ギャップを計算
                gap = next_subtitle.start_time - current.end_time

                # ギャップが0.5~1.5秒の範囲内なら調整
                if 0.5 <= gap <= 1.5:
                    old_end = current.end_time
                    new_end = next_subtitle.start_time - 0.3

                    # 新しい字幕エントリを作成
                    current = SubtitleEntry(
                        index=current.index,
                        start_time=current.start_time,
                        end_time=new_end,
                        text_line1=current.text_line1,
                        text_line2=current.text_line2
                    )

                    adjusted_count += 1
                    self.logger.debug(
                        f"字幕 {current.index}: ギャップ調整 "
                        f"{old_end:.3f}秒 → {new_end:.3f}秒 "
                        f"(gap: {gap:.3f}秒 → 0.3秒, +{new_end - old_end:.3f}秒延長)"
                    )

            optimized_subtitles.append(current)

        self.logger.info(
            f"Subtitle gap optimization complete: {adjusted_count}/{len(subtitles)} subtitles adjusted "
            f"(gaps 0.5-1.5s reduced to 0.3s)"
        )
        return optimized_subtitles
