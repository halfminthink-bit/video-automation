"""
字幕生成器

台本と音声セグメント情報から字幕を生成する。
日本語テキストの適切な分割、タイミング計算を行う。
"""

from typing import List, Dict, Any, Optional
import logging
from pathlib import Path

from ..core.models import (
    VideoScript,
    ScriptSection,
    AudioSegment,
    SubtitleEntry
)
from ..utils.whisper_timing import create_whisper_extractor


class SubtitleGenerator:
    """字幕生成器"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            config: 字幕生成設定
            logger: ロガー
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # 設定値の取得
        self.max_lines = max(1, config.get("max_lines", 2))
        self.max_chars_per_line = config.get("max_chars_per_line", 20)
        
        timing = config.get("timing", {})
        self.min_display_duration = timing.get("min_display_duration", 4.0)
        self.max_display_duration = timing.get("max_display_duration", 6.0)
        self.lead_time = timing.get("lead_time", 0.2)
        
        morphological = config.get("morphological_analysis", {})
        self.use_mecab = morphological.get("use_mecab", False)
        self.break_on = morphological.get("break_on", ["。", "、", "！", "？"])
        
        # MeCabの初期化（使用する場合）
        self.mecab = None
        if self.use_mecab:
            self._init_mecab()
        
        # Whisperの設定（タイミング情報取得用）
        whisper_config = config.get("whisper", {})
        self.use_whisper = whisper_config.get("enabled", True)
        self.whisper_model = whisper_config.get("model", "base")
        self.whisper_extractor = None
        if self.use_whisper:
            self.whisper_extractor = create_whisper_extractor(
                model_name=self.whisper_model,
                logger=self.logger,
                language="ja"
            )
            if self.whisper_extractor is None:
                self.logger.warning(
                    "Whisper is enabled but not available. "
                    "Falling back to character-based timing."
                )
                self.use_whisper = False
    
    def _init_mecab(self):
        """MeCabを初期化（オプション）"""
        try:
            import MeCab
            self.mecab = MeCab.Tagger()
            self.logger.info("MeCab initialized")
        except ImportError:
            self.logger.warning(
                "MeCab not available. Install with: pip install python-mecab"
            )
            self.use_mecab = False
        except Exception as e:
            self.logger.warning(f"Failed to initialize MeCab: {e}")
            self.use_mecab = False
    
    def generate_subtitles(
        self,
        script: VideoScript,
        audio_segments: List[AudioSegment],
        config: Dict[str, Any],
        audio_path: Optional[Path] = None
    ) -> List[SubtitleEntry]:
        """
        字幕を生成
        
        Args:
            script: 台本
            audio_segments: 音声セグメント情報
            config: 設定（self.configと重複するが、明示的に渡す）
            audio_path: 音声ファイルのパス（Whisperを使用する場合）
            
        Returns:
            字幕エントリのリスト
        """
        self.logger.info(
            f"Generating subtitles from {len(script.sections)} sections"
        )
        
        # Whisperを使用する場合、音声からタイミング情報を取得
        sentence_timings_map = {}
        if self.use_whisper and audio_path and audio_path.exists():
            self.logger.info("Using Whisper to extract accurate timing information")
            try:
                # 全セクションのナレーションを結合
                all_narrations = []
                for section in script.sections:
                    sentences = self._split_into_sentences(section.narration)
                    all_narrations.extend(sentences)
                
                # Whisperでタイミング情報を取得
                sentence_timings = self.whisper_extractor.extract_sentence_timings(
                    audio_path=audio_path,
                    sentences=all_narrations
                )

                # セクションごとにマッピング（時間範囲でフィルタリング）
                # Whisperは全音声ファイルの絶対時間を返すため、
                # 各セクションの開始・終了時間の範囲内にある文をマッピングする
                for i, section in enumerate(script.sections):
                    # 対応する音声セグメントを取得
                    segment = None
                    for seg in audio_segments:
                        if seg.section_id == section.section_id:
                            segment = seg
                            break

                    if segment is None:
                        self.logger.warning(
                            f"No audio segment found for section {section.section_id}"
                        )
                        continue

                    # このセクションの時間範囲
                    section_start = segment.start_time
                    section_end = segment.start_time + segment.duration

                    # このセクションに対応する文のタイミングを抽出
                    section_sentences = self._split_into_sentences(section.narration)
                    section_timings = []

                    # Whisperのタイミングから、このセクションの範囲内のものを取得
                    # 期待される文の数と一致するものを探す
                    available_timings = [
                        t for t in sentence_timings
                        if section_start <= t.get("start", 0) < section_end
                    ]

                    # 文の数が一致しない場合は警告
                    if len(available_timings) != len(section_sentences):
                        self.logger.warning(
                            f"Section {section.section_id}: "
                            f"Expected {len(section_sentences)} sentences, "
                            f"but found {len(available_timings)} timings in range "
                            f"[{section_start:.2f}s - {section_end:.2f}s]"
                        )

                    # 利用可能なタイミングを使用（数が合わない場合は部分的に使用）
                    for j in range(min(len(section_sentences), len(available_timings))):
                        section_timings.append(available_timings[j])

                    sentence_timings_map[section.section_id] = section_timings
                
                self.logger.info(
                    f"Extracted timing information for {len(sentence_timings)} sentences"
                )
            except Exception as e:
                self.logger.warning(
                    f"Failed to extract Whisper timings: {e}. "
                    "Falling back to character-based timing."
                )
                sentence_timings_map = {}
        
        all_subtitles: List[SubtitleEntry] = []
        subtitle_index = 1
        current_time = 0.0
        
        # セグメントごとに字幕を生成
        for i, section in enumerate(script.sections):
            # 対応する音声セグメントを取得
            segment = None
            for seg in audio_segments:
                if seg.section_id == section.section_id:
                    segment = seg
                    break
            
            if segment is None:
                self.logger.warning(
                    f"No audio segment found for section {section.section_id}. "
                    "Using estimated duration."
                )
                # 推定時間を使用
                segment_duration = section.estimated_duration
                segment_start = current_time
            else:
                segment_duration = segment.duration
                segment_start = segment.start_time
                current_time = segment_start + segment_duration
            
            # セクションのタイミング情報を取得
            section_timings = sentence_timings_map.get(section.section_id, [])
            
            # セクションのナレーションを字幕に分割
            section_subtitles = self._split_section_to_subtitles(
                narration=section.narration,
                start_time=segment_start,
                duration=segment_duration,
                sentence_timings=section_timings
            )
            
            # インデックスを割り当て
            for subtitle in section_subtitles:
                subtitle.index = subtitle_index
                subtitle_index += 1
                all_subtitles.append(subtitle)
        
        self.logger.info(
            f"Generated {len(all_subtitles)} subtitle entries"
        )
        
        return all_subtitles
    
    def _split_section_to_subtitles(
        self,
        narration: str,
        start_time: float,
        duration: float,
        sentence_timings: Optional[List[Dict[str, Any]]] = None
    ) -> List[SubtitleEntry]:
        """
        セクションのナレーションを字幕エントリに分割
        
        Args:
            narration: ナレーション原稿
            start_time: セクションの開始時間
            duration: セクションの長さ
            sentence_timings: Whisperから取得した文のタイミング情報（オプション）
            
        Returns:
            字幕エントリのリスト
        """
        # 文に分割
        sentences = self._split_into_sentences(narration)
        
        if not sentences:
            return []
        
        subtitles: List[SubtitleEntry] = []
        
        # Whisperのタイミング情報を使用する場合
        if sentence_timings and len(sentence_timings) == len(sentences):
            self.logger.debug(f"Using Whisper timing for {len(sentences)} sentences")

            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue

                timing_info = sentence_timings[i]
                # Whisperのタイミングは既に全音声ファイルの絶対時間なので、
                # そのまま使用する（セクションごとのマッピングで既にフィルタリング済み）
                sentence_start = timing_info.get("start", start_time)
                sentence_end = timing_info.get("end", start_time + duration)
                
                # 最小・最大表示時間の制約を適用
                sentence_duration = sentence_end - sentence_start
                sentence_duration = max(
                    self.min_display_duration,
                    min(sentence_duration, self.max_display_duration)
                )
                sentence_end = sentence_start + sentence_duration
                
                # リードタイムを適用
                subtitle_start = max(0, sentence_start - self.lead_time)
                
                # 文を2行に分割
                lines = self._split_text_to_lines(sentence)
                
                # 字幕エントリを作成
                subtitle = SubtitleEntry(
                    index=0,  # 後で割り当て
                    start_time=subtitle_start,
                    end_time=sentence_end,
                    text_line1=lines[0] if len(lines) > 0 else "",
                    text_line2=lines[1] if len(lines) > 1 else "",
                    text_line3=lines[2] if len(lines) > 2 else "",
                )
                subtitles.append(subtitle)
        else:
            # 従来の方法：文字数比率で計算（フォールバック）
            self.logger.debug("Using character-based timing (fallback)")
            sentence_chars = [len(s) for s in sentences]
            total_chars = sum(sentence_chars)
            
            current_time = start_time - self.lead_time
            current_time = max(0, current_time)
            
            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue
                
                # この文までの累積文字数から時間を計算
                sentence_chars_count = len(sentence)
                char_ratio = sentence_chars_count / total_chars if total_chars > 0 else 0
                sentence_duration = duration * char_ratio
                
                # 最小・最大表示時間の制約を適用
                sentence_duration = max(
                    self.min_display_duration,
                    min(sentence_duration, self.max_display_duration)
                )
                
                # 文を2行に分割
                lines = self._split_text_to_lines(sentence)
                
                # 字幕エントリを作成
                subtitle = SubtitleEntry(
                    index=0,  # 後で割り当て
                    start_time=current_time,
                    end_time=current_time + sentence_duration,
                    text_line1=lines[0] if len(lines) > 0 else "",
                    text_line2=lines[1] if len(lines) > 1 else "",
                    text_line3=lines[2] if len(lines) > 2 else "",
                )
                subtitles.append(subtitle)
                
                current_time += sentence_duration
        
        return subtitles
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        テキストを文に分割
        
        Args:
            text: 入力テキスト
            
        Returns:
            文のリスト
        """
        if not text.strip():
            return []
        
        # まず、句点で分割
        sentences = []
        current = ""
        
        for char in text:
            current += char
            if char in self.break_on:
                if current.strip():
                    sentences.append(current.strip())
                current = ""
        
        # 残りを追加
        if current.strip():
            sentences.append(current.strip())
        
        # 空の文を除去
        sentences = [s for s in sentences if s]
        
        return sentences if sentences else [text]
    
    def _split_text_to_lines(self, text: str) -> List[str]:
        """
        テキストを行ごとに分割（最大 self.max_lines 行）
        
        Args:
            text: 入力テキスト
            
        Returns:
            行のリスト（最大 self.max_lines 行）
        """
        text = text.strip()
        if not text:
            return [""]

        remaining = text
        lines: List[str] = []

        # 単行で収まる場合
        if len(remaining) <= self.max_chars_per_line or self.max_lines == 1:
            return [remaining[: self.max_chars_per_line]]

        while remaining and len(lines) < self.max_lines:
            # 最終行は残りをそのまま（必要であれば切り詰め）入れる
            if len(lines) == self.max_lines - 1:
                lines.append(remaining[: self.max_chars_per_line].strip())
                remaining = remaining[self.max_chars_per_line:].strip()
                break

            # ベストな分割位置を探す
            split_pos = self._find_best_split_position(remaining)
            if split_pos <= 0 or split_pos > self.max_chars_per_line:
                split_pos = min(self.max_chars_per_line, len(remaining))

            chunk = remaining[:split_pos].strip()
            lines.append(chunk)
            remaining = remaining[split_pos:].strip()

        # 残りがあり3行目を超える場合は最後の行に収まる範囲のみ残す
        if remaining and lines:
            lines[-1] = (lines[-1] + remaining)[: self.max_chars_per_line].strip()

        # 空行を除外し、最大行数に揃える
        lines = [line for line in lines if line]
        if not lines:
            lines = [text[: self.max_chars_per_line]]

        return lines[: self.max_lines]
    
    def _find_best_split_position(self, text: str) -> int:
        """
        テキストを分割する最適な位置を見つける
        
        Args:
            text: 入力テキスト
            
        Returns:
            分割位置（0の場合は見つからない）
        """
        target_pos = self.max_chars_per_line
        
        # 目標位置付近で読点や句点を探す
        # 前後20文字以内で探す
        search_range = 20
        start_pos = max(0, target_pos - search_range)
        end_pos = min(len(text), target_pos + search_range)
        
        search_text = text[start_pos:end_pos]
        
        # 優先順位：読点 > 句点 > 空白
        for char in ["、", "。", " ", "　"]:
            pos = search_text.find(char, target_pos - start_pos)
            if pos > 0:
                return start_pos + pos + 1  # 読点の後
        
        # 見つからない場合は0を返す
        return 0

    def generate_subtitles_from_char_timings(
        self,
        audio_timing_data: List[Dict[str, Any]]
    ) -> List[SubtitleEntry]:
        """
        文字レベルのタイミング情報から字幕を生成

        Args:
            audio_timing_data: audio_timing.jsonの内容

        Returns:
            字幕リスト
        """
        max_chars = self.max_chars_per_line * 2  # 2行分
        max_duration = self.max_display_duration
        min_duration = self.min_display_duration
        break_chars = self.break_on

        subtitles = []
        subtitle_index = 1

        for section in audio_timing_data:
            characters = section.get("characters", [])
            char_start_times = section.get("char_start_times", [])
            char_end_times = section.get("char_end_times", [])
            offset = section.get("offset", 0.0)

            if not characters or len(characters) != len(char_start_times):
                self.logger.warning(f"Section {section.get('section_id')} has invalid timing data")
                continue

            current_text = []
            subtitle_start = None

            for i, char in enumerate(characters):
                char_start = char_start_times[i] + offset
                char_end = char_end_times[i] + offset

                # 字幕開始時刻を設定
                if subtitle_start is None:
                    subtitle_start = char_start

                # 文字を追加
                current_text.append(char)

                # 現在の字幕の長さ
                current_duration = char_end - subtitle_start
                current_length = len(current_text)

                # 次の文字との間隔をチェック
                next_gap = 0.0
                if i + 1 < len(characters):
                    next_gap = char_start_times[i + 1] - char_end

                # 区切り条件
                should_break = (
                    # 句読点
                    char in break_chars or

                    # 最大表示時間超過
                    current_duration >= max_duration or

                    # 最大文字数超過
                    current_length >= max_chars or

                    # 次の文字との間に大きな間がある（0.5秒以上）
                    next_gap >= 0.5 or

                    # 最後の文字
                    i == len(characters) - 1
                )

                if should_break and current_text:
                    # 最低表示時間を満たさない場合はスキップ
                    if current_duration < min_duration and i < len(characters) - 1:
                        continue

                    # テキストを結合
                    subtitle_text = "".join(current_text).strip()

                    if not subtitle_text:
                        current_text = []
                        subtitle_start = None
                        continue

                    # 2行に分割
                    line1, line2 = self._split_subtitle_into_lines(
                        subtitle_text
                    )

                    subtitles.append(SubtitleEntry(
                        index=subtitle_index,
                        start_time=subtitle_start,
                        end_time=char_end,
                        text_line1=line1,
                        text_line2=line2,
                        text_line3=""  # 3行目は使わない
                    ))

                    subtitle_index += 1

                    # リセット
                    current_text = []
                    subtitle_start = None

        self.logger.info(f"Generated {len(subtitles)} subtitles from character timings")
        return subtitles

    def _split_subtitle_into_lines(
        self,
        text: str
    ) -> tuple[str, str]:
        """
        テキストを2行に分割

        Args:
            text: 分割するテキスト

        Returns:
            (1行目, 2行目)
        """
        # 句読点や助詞の直後で区切るのが理想的
        break_points = ["。", "、", "！", "？", "は", "が", "を", "に", "で", "と"]

        if len(text) <= self.max_chars_per_line:
            return (text, "")

        # 中間点付近で良い区切り位置を探す
        mid_point = len(text) // 2
        best_break = mid_point
        best_distance = len(text)

        for i, char in enumerate(text):
            if char in break_points:
                distance = abs(i - mid_point)
                if distance < best_distance and i > 0:
                    best_distance = distance
                    best_break = i + 1

        # 最大文字数を超えないように調整
        if best_break > self.max_chars_per_line:
            best_break = self.max_chars_per_line

        line1 = text[:best_break].strip()
        line2 = text[best_break:].strip()

        # 2行目が長すぎる場合は強制分割
        if len(line2) > self.max_chars_per_line:
            line2 = line2[:self.max_chars_per_line]

        return (line1, line2)


def create_subtitle_generator(
    config: Dict[str, Any],
    logger: Optional[logging.Logger] = None
) -> SubtitleGenerator:
    """
    字幕生成器を作成

    Args:
        config: 字幕生成設定
        logger: ロガー

    Returns:
        SubtitleGenerator
    """
    return SubtitleGenerator(config=config, logger=logger)
