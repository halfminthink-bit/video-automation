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
        self.subtitle_gap = timing.get("subtitle_gap", 0.1)
        self.prevent_overlap = timing.get("prevent_overlap", True)
        self.overlap_priority = timing.get("overlap_priority", "next_subtitle")
        
        morphological = config.get("morphological_analysis", {})
        self.use_mecab = morphological.get("use_mecab", False)
        self.break_on = morphological.get("break_on", ["。", "、", "！", "？"])

        # 分割戦略の設定
        splitting = config.get("splitting", {})
        self.window_size = splitting.get("window_size", 3)
        self.priority_scores = splitting.get("priority_scores", {
            "punctuation": 120,
            "morpheme_boundary": 150,  # 形態素境界（最優先）
            "particle": 100,
            "hiragana_to_kanji": 80,
            "kanji_to_hiragana": 60,
            "katakana_boundary": 40
        })
        self.penalties = splitting.get("penalties", {
            "distance_from_ideal": 5,
            "ends_with_n_tsu": 20,
            "splits_number": 50,
            "splits_alphabet": 50,
            "splits_verb_adjective": 500  # 動詞・形容詞の途中で分割するペナルティ
        })
        self.particles = splitting.get("particles", [
            "は", "が", "を", "に", "で", "と", "も", "や", "から", "まで", "より"
        ])
        self.balance_lines = splitting.get("balance_lines", True)
        self.min_line_length = splitting.get("min_line_length", 3)

        # 句読点表示設定
        self.remove_punctuation = config.get("remove_punctuation_in_display", True)

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

    def _is_hiragana(self, char: str) -> bool:
        """ひらがなかどうか判定"""
        return '\u3040' <= char <= '\u309F'

    def _is_katakana(self, char: str) -> bool:
        """カタカナかどうか判定"""
        return '\u30A0' <= char <= '\u30FF'

    def _is_kanji(self, char: str) -> bool:
        """漢字かどうか判定"""
        return '\u4E00' <= char <= '\u9FFF'

    def _is_number(self, char: str) -> bool:
        """数字かどうか判定"""
        return char.isdigit() or '\uFF10' <= char <= '\uFF19'

    def _is_alphabet(self, char: str) -> bool:
        """英字かどうか判定"""
        return char.isalpha() and ord(char) < 128

    def _find_punctuation_positions(
        self,
        text: str,
        characters: List[str]
    ) -> Dict[int, str]:
        """
        textフィールドから句読点位置を抽出し、charactersのインデックスにマッピング

        Args:
            text: 句読点ありの元テキスト（例: "戦国時代、うつけ者と..."）
            characters: 句読点なしの文字配列（例: ["戦", "国", "時", "代", "う", ...]）

        Returns:
            {4: "、", 20: "。", ...}  # charactersのインデックス → 句読点
        """
        punctuation_marks = set(["。", "、", "！", "？", "…"])
        ignore_chars = set(["「", "」", "『", "』", "（", "）", " ", "　"])

        # textから記号を除去しつつ、句読点の位置を記録
        text_chars = []
        punctuation_positions_in_text = {}

        for i, char in enumerate(text):
            if char in punctuation_marks:
                # 句読点の位置を記録（除去後の位置）
                punctuation_positions_in_text[len(text_chars)] = char
            elif char not in ignore_chars:
                text_chars.append(char)

        # charactersと照合
        characters_str = "".join(characters)
        text_chars_str = "".join(text_chars)

        if characters_str != text_chars_str:
            self.logger.warning(
                f"Text mismatch: characters='{characters_str[:50]}...' vs "
                f"text_chars='{text_chars_str[:50]}...'"
            )
            # 一致しない場合は空の辞書を返す
            return {}

        return punctuation_positions_in_text

    def _find_punctuation_positions_from_characters(
        self,
        characters: List[str]
    ) -> Dict[int, str]:
        """
        charactersから直接句読点位置を検出

        修正後のwhisper_timing.pyでは、charactersに句読点が含まれるようになったため、
        このメソッドを使用する。

        Args:
            characters: 文字配列（句読点を含む）

        Returns:
            {インデックス: 句読点, ...}  # charactersのインデックス → 句読点
            例: {4: "、", 24: "。", ...}
        """
        punctuation_marks = set(["。", "、", "！", "？", "…"])
        positions = {}

        for i, char in enumerate(characters):
            if char in punctuation_marks:
                positions[i] = char

        return positions

    def _detect_character_boundaries(
        self,
        characters: List[str]
    ) -> Dict[str, List[int]]:
        """
        文字種の境界を検出

        Returns:
            {
                'hiragana_to_kanji': [5, 12, 23, ...],
                'kanji_to_hiragana': [8, 15, 26, ...],
                'katakana_boundary': [10, 20, ...],
                'particles': [4, 11, 19, ...]
            }
        """
        boundaries = {
            'hiragana_to_kanji': [],
            'kanji_to_hiragana': [],
            'katakana_boundary': [],
            'particles': []
        }

        for i in range(len(characters) - 1):
            curr_char = characters[i]
            next_char = characters[i + 1]

            # ひらがな→漢字
            if self._is_hiragana(curr_char) and self._is_kanji(next_char):
                boundaries['hiragana_to_kanji'].append(i + 1)

            # 漢字→ひらがな
            if self._is_kanji(curr_char) and self._is_hiragana(next_char):
                boundaries['kanji_to_hiragana'].append(i + 1)

            # カタカナ境界
            if self._is_katakana(curr_char) and not self._is_katakana(next_char):
                boundaries['katakana_boundary'].append(i + 1)
            elif not self._is_katakana(curr_char) and self._is_katakana(next_char):
                boundaries['katakana_boundary'].append(i + 1)

        # 助詞の位置を検出
        for i, char in enumerate(characters):
            if char in self.particles:
                # 助詞の直後の位置
                if i + 1 < len(characters):
                    boundaries['particles'].append(i + 1)

        return boundaries

    def _detect_morpheme_boundaries(
        self,
        characters: List[str]
    ) -> Dict[str, Any]:
        """
        MeCabを使って形態素境界を検出

        Returns:
            {
                'boundaries': [3, 7, 12, ...],  # 形態素の境界位置
                'morphemes': [
                    {'surface': '戦国', 'pos': '名詞', 'start': 0, 'end': 2},
                    {'surface': '時代', 'pos': '名詞', 'start': 2, 'end': 4},
                    ...
                ],
                'verb_adjective_positions': set([5, 6, 7, ...])  # 動詞・形容詞の内部位置
            }
        """
        if not self.use_mecab or self.mecab is None:
            # MeCabが利用できない場合は空の結果を返す
            return {
                'boundaries': [],
                'morphemes': [],
                'verb_adjective_positions': set()
            }

        try:
            text = "".join(characters)

            # MeCabで解析
            node = self.mecab.parseToNode(text)

            morphemes = []
            boundaries = []
            verb_adjective_positions = set()
            current_pos = 0

            while node:
                surface = node.surface
                features = node.feature.split(',')
                pos = features[0] if features else "未知語"

                if surface:  # 空文字列でない場合
                    morpheme_len = len(surface)
                    morpheme_end = current_pos + morpheme_len

                    morphemes.append({
                        'surface': surface,
                        'pos': pos,
                        'start': current_pos,
                        'end': morpheme_end
                    })

                    # 形態素の終わり位置を境界として記録
                    if morpheme_end < len(characters):
                        boundaries.append(morpheme_end)

                    # 動詞・形容詞の内部位置を記録（境界以外の位置）
                    if pos in ['動詞', '形容詞']:
                        for i in range(current_pos + 1, morpheme_end):
                            verb_adjective_positions.add(i)

                    current_pos = morpheme_end

                node = node.next

            self.logger.debug(
                f"MeCab detected {len(morphemes)} morphemes, "
                f"{len(boundaries)} boundaries, "
                f"{len(verb_adjective_positions)} verb/adj internal positions"
            )

            return {
                'boundaries': boundaries,
                'morphemes': morphemes,
                'verb_adjective_positions': verb_adjective_positions
            }

        except Exception as e:
            self.logger.warning(f"MeCab analysis failed: {e}")
            return {
                'boundaries': [],
                'morphemes': [],
                'verb_adjective_positions': set()
            }

    def _find_split_position_with_score(
        self,
        text: str,
        characters: List[str],
        max_chars: int,
        punctuation_positions: Dict[int, str],
        boundaries: Dict[str, List[int]],
        morpheme_info: Optional[Dict[str, Any]] = None
    ) -> tuple[int, str]:
        """
        最適な分割位置をスコアリング方式で決定

        優先順位:
        1. 句読点（スコア: 120）
        2. 形態素境界（スコア: 150） ← NEW
        3. 助詞の後（スコア: 100）
        4. ひらがな→漢字（スコア: 80）
        5. 漢字→ひらがな（スコア: 60）
        6. カタカナ境界（スコア: 40）

        ペナルティ:
        - 理想位置から離れるごとに -5点/文字
        - 「ん」「っ」で終わる: -20点
        - 数字・英字を分割: -50点
        - 分割後の断片が短すぎる: -200点
        - 分割バランスが悪い: 最大-50点
        - 動詞・形容詞の途中で分割: -500点 ← NEW

        Returns:
            (分割位置, 分割理由)
        """
        if len(characters) <= max_chars:
            return (len(characters), "no_split_needed")

        # 最小断片長（これより短い断片を作らない）
        MIN_CHUNK_LENGTH = 10

        # 理想位置（max_charsに近い位置）
        ideal_pos = max_chars

        # 探索範囲
        search_start = max(1, ideal_pos - self.window_size)
        search_end = min(len(characters), ideal_pos + self.window_size + 1)

        best_score = -99999
        best_pos = ideal_pos
        best_reason = "forced"

        # 形態素情報の取得
        morpheme_boundaries = []
        verb_adjective_positions = set()
        if morpheme_info:
            morpheme_boundaries = morpheme_info.get('boundaries', [])
            verb_adjective_positions = morpheme_info.get('verb_adjective_positions', set())

        for pos in range(search_start, search_end):
            score = 0
            reason = ""

            # 分割後の長さをチェック
            first_part_len = pos
            second_part_len = len(characters) - pos

            # 最小長ペナルティ（断片が短すぎる場合は大きなペナルティ）
            if first_part_len < MIN_CHUNK_LENGTH:
                score -= 200
            if second_part_len < MIN_CHUNK_LENGTH:
                score -= 200

            # バランスペナルティ（なるべく均等に分割）
            # 理想比率は50:50、そこから離れるほどペナルティ
            ideal_ratio = 0.5
            actual_ratio = first_part_len / len(characters)
            balance_penalty = abs(ideal_ratio - actual_ratio) * 100
            score -= balance_penalty

            # 句読点の処理
            # 「、」の場合は直後で分割（「、」を含める）
            # 「。」「！」「？」の場合は直後で分割（これらも含める）
            if pos > 0 and (pos - 1) in punctuation_positions:
                punct = punctuation_positions[pos - 1]
                if punct == "、":
                    # 「、」の直後で分割
                    score += self.priority_scores.get("punctuation", 120)
                    reason = "punctuation_after_comma"

            # その他の句読点（「。」など）も直後で分割
            if pos in punctuation_positions:
                punct = punctuation_positions[pos]
                if punct in ["。", "！", "？", "…"]:
                    score += self.priority_scores.get("punctuation", 120)
                    reason = f"punctuation_{punct}"

            # 形態素境界（句読点の次に優先）
            if pos in morpheme_boundaries:
                score += self.priority_scores.get("morpheme_boundary", 150)
                if not reason:  # 句読点がない場合のみ理由を設定
                    reason = "morpheme_boundary"

            # 助詞の後
            if pos in boundaries.get("particles", []):
                score += self.priority_scores.get("particle", 100)
                if not reason:
                    reason = "particle"

            # ひらがな→漢字
            elif pos in boundaries.get("hiragana_to_kanji", []):
                score += self.priority_scores.get("hiragana_to_kanji", 80)
                if not reason:
                    reason = "hiragana_to_kanji"

            # 漢字→ひらがな
            elif pos in boundaries.get("kanji_to_hiragana", []):
                score += self.priority_scores.get("kanji_to_hiragana", 60)
                if not reason:
                    reason = "kanji_to_hiragana"

            # カタカナ境界
            elif pos in boundaries.get("katakana_boundary", []):
                score += self.priority_scores.get("katakana_boundary", 40)
                if not reason:
                    reason = "katakana_boundary"

            # 動詞・形容詞の途中で分割するペナルティ
            if pos in verb_adjective_positions:
                score -= self.penalties.get("splits_verb_adjective", 500)
                self.logger.debug(f"Position {pos} splits verb/adjective, penalty applied")

            # 距離ペナルティ
            distance = abs(pos - ideal_pos)
            score -= distance * self.penalties.get("distance_from_ideal", 5)

            # 「ん」「っ」で終わるペナルティ
            if pos > 0 and characters[pos - 1] in ["ん", "っ"]:
                score -= self.penalties.get("ends_with_n_tsu", 20)

            # 数字を分割するペナルティ
            if pos > 0 and pos < len(characters):
                if self._is_number(characters[pos - 1]) and self._is_number(characters[pos]):
                    score -= self.penalties.get("splits_number", 50)

            # 英字を分割するペナルティ
            if pos > 0 and pos < len(characters):
                if self._is_alphabet(characters[pos - 1]) and self._is_alphabet(characters[pos]):
                    score -= self.penalties.get("splits_alphabet", 50)

            if score > best_score:
                best_score = score
                best_pos = pos
                best_reason = reason if reason else "best_available"

        # スコアが低すぎる場合は強制分割
        if best_score < -100:
            best_pos = ideal_pos
            best_reason = "forced"

        return (best_pos, best_reason)

    def _split_into_balanced_lines(
        self,
        text: str,
        characters: List[str],
        max_chars_per_line: int,
        max_lines: int,
        punctuation_positions: Dict[int, str],
        boundaries: Dict[str, List[int]]
    ) -> List[str]:
        """
        テキストを複数行に分割（なるべく均等に）

        Args:
            text: 元のテキスト（句読点あり）
            characters: 文字配列（句読点なし）
            max_chars_per_line: 1行あたりの最大文字数
            max_lines: 最大行数
            punctuation_positions: 句読点位置のマップ
            boundaries: 文字種境界のマップ

        Returns:
            行のリスト（句読点を除去済み）
        """
        if len(characters) <= max_chars_per_line:
            return ["".join(characters)]

        # 36文字以内（max_chars_per_line * max_lines）の場合、段階的フォールバック
        if len(characters) <= max_chars_per_line * max_lines:
            MIN_LINE_LENGTH = 3  # 最低3文字
            split_pos = None
            split_reason = None

            # 優先順位1: 読点（「、」）で分割 - 両方が18文字以内の場合
            for i in range(len(characters) - 1, -1, -1):
                if characters[i] == '、':
                    first_part_len = i + 1  # 「、」を含む
                    second_part_len = len(characters) - (i + 1)

                    # 両方が18文字以内で、最低文字数以上
                    if (first_part_len <= max_chars_per_line and
                        second_part_len <= max_chars_per_line and
                        first_part_len >= MIN_LINE_LENGTH and
                        second_part_len >= MIN_LINE_LENGTH):
                        split_pos = i + 1
                        split_reason = "comma"
                        break

            # 優先順位2: 助詞の後
            if split_pos is None:
                for i in range(len(characters) - 1, -1, -1):
                    if characters[i] in self.particles:
                        first_part_len = i + 1
                        second_part_len = len(characters) - (i + 1)

                        if (first_part_len <= max_chars_per_line and
                            second_part_len <= max_chars_per_line and
                            first_part_len >= MIN_LINE_LENGTH and
                            second_part_len >= MIN_LINE_LENGTH):
                            split_pos = i + 1
                            split_reason = "particle"
                            break

            # 優先順位3: ひらがな→漢字の境界
            if split_pos is None:
                for i in range(len(characters) - 1, -1, -1):
                    if i + 1 < len(characters):
                        if self._is_hiragana(characters[i]) and self._is_kanji(characters[i + 1]):
                            first_part_len = i + 1
                            second_part_len = len(characters) - (i + 1)

                            if (first_part_len <= max_chars_per_line and
                                second_part_len <= max_chars_per_line and
                                first_part_len >= MIN_LINE_LENGTH and
                                second_part_len >= MIN_LINE_LENGTH):
                                split_pos = i + 1
                                split_reason = "hiragana_to_kanji"
                                break

            # 優先順位4: 漢字→ひらがなの境界
            if split_pos is None:
                for i in range(len(characters) - 1, -1, -1):
                    if i + 1 < len(characters):
                        if self._is_kanji(characters[i]) and self._is_hiragana(characters[i + 1]):
                            first_part_len = i + 1
                            second_part_len = len(characters) - (i + 1)

                            if (first_part_len <= max_chars_per_line and
                                second_part_len <= max_chars_per_line and
                                first_part_len >= MIN_LINE_LENGTH and
                                second_part_len >= MIN_LINE_LENGTH):
                                split_pos = i + 1
                                split_reason = "kanji_to_hiragana"
                                break

            # 優先順位5: カタカナ境界
            if split_pos is None:
                for i in range(len(characters) - 1, -1, -1):
                    if i + 1 < len(characters):
                        curr_is_katakana = self._is_katakana(characters[i])
                        next_is_katakana = self._is_katakana(characters[i + 1])

                        # カタカナ→非カタカナ または 非カタカナ→カタカナ
                        if curr_is_katakana != next_is_katakana:
                            first_part_len = i + 1
                            second_part_len = len(characters) - (i + 1)

                            if (first_part_len <= max_chars_per_line and
                                second_part_len <= max_chars_per_line and
                                first_part_len >= MIN_LINE_LENGTH and
                                second_part_len >= MIN_LINE_LENGTH):
                                split_pos = i + 1
                                split_reason = "katakana_boundary"
                                break

            # 適切な分割位置が見つかった場合
            if split_pos:
                line1_chars = characters[:split_pos]
                line2_chars = characters[split_pos:]

                line1 = "".join(line1_chars)
                line2 = "".join(line2_chars)

                if self.remove_punctuation:
                    # 句読点を除去（「、」は残す）
                    line1 = "".join([c for c in line1 if c not in ["。", "！", "？", "…"]])
                    line2 = "".join([c for c in line2 if c not in ["。", "！", "？", "…"]])

                self.logger.debug(
                    f"Split at {split_reason} (36-char mode): '{line1}' / '{line2}' "
                    f"({len(line1_chars)} + {len(line2_chars)} = {len(characters)} chars)"
                )

                return [line1, line2]

            # すべての方法で分割できない場合は既存のロジックにフォールバック
            self.logger.debug(
                f"No suitable split point found for 36-char text, falling back to scoring method"
            )

        lines = []
        remaining_chars = characters.copy()
        remaining_punct = punctuation_positions.copy()

        # 形態素境界を検出（全体で一度だけ）
        morpheme_info = self._detect_morpheme_boundaries(characters)

        while remaining_chars and len(lines) < max_lines:
            # 最終行の処理
            if len(lines) == max_lines - 1:
                line_text = "".join(remaining_chars)

                # 最終行が長すぎる場合は警告を出す
                if len(remaining_chars) > max_chars_per_line * 1.5:
                    self.logger.warning(
                        f"Last line is too long ({len(remaining_chars)} chars). "
                        f"Text may be truncated or split improperly. "
                        f"Consider using longer max_chars or multiple subtitles."
                    )

                if self.remove_punctuation:
                    # 句読点を除去（「、」と「」は残す）
                    line_text = "".join([c for c in line_text if c not in ["。", "！", "？", "…"]])
                lines.append(line_text)
                break

            # 残りのテキストに対する形態素情報を更新
            offset = len(characters) - len(remaining_chars)
            remaining_morpheme_info = {
                'boundaries': [b - offset for b in morpheme_info.get('boundaries', []) if b >= offset],
                'verb_adjective_positions': set([p - offset for p in morpheme_info.get('verb_adjective_positions', set()) if p >= offset])
            }

            # 分割位置を決定
            split_pos, reason = self._find_split_position_with_score(
                text="".join(remaining_chars),
                characters=remaining_chars,
                max_chars=max_chars_per_line,
                punctuation_positions=remaining_punct,
                boundaries=self._detect_character_boundaries(remaining_chars),
                morpheme_info=remaining_morpheme_info
            )

            # この行のテキストを取得
            line_chars = remaining_chars[:split_pos]
            line_text = "".join(line_chars)

            if self.remove_punctuation:
                # 句読点を除去（「、」と「」は残す）
                line_text = "".join([c for c in line_text if c not in ["。", "！", "？", "…"]])

            # 行を追加（スコアリングで最小長を保証しているため、スキップしない）
            # 以前の min_line_length チェックはテキスト欠落の原因となるため削除
            lines.append(line_text)

            # 残りを更新
            remaining_chars = remaining_chars[split_pos:]
            # 句読点位置を更新（インデックスをずらす）
            new_punct = {}
            for pos, punct in remaining_punct.items():
                if pos >= split_pos:
                    new_punct[pos - split_pos] = punct
            remaining_punct = new_punct

        # 空行を除外
        lines = [line for line in lines if line.strip()]

        return lines[:max_lines]

    def generate_subtitles_from_char_timings(
        self,
        audio_timing_data: List[Dict[str, Any]]
    ) -> List[SubtitleEntry]:
        """
        文字レベルのタイミング情報から字幕を生成（改良版）

        Args:
            audio_timing_data: audio_timing.jsonの内容

        Returns:
            字幕リスト
        """
        max_chars = self.max_chars_per_line * self.max_lines
        max_duration = self.max_display_duration
        min_duration = self.min_display_duration

        # 一時的に全字幕候補を保存（終了時刻調整前）
        temp_subtitles = []

        for section in audio_timing_data:
            text = section.get("text", "")
            characters = section.get("characters", [])
            char_start_times = section.get("char_start_times", [])
            char_end_times = section.get("char_end_times", [])
            offset = section.get("offset", 0.0)

            if not characters or len(characters) != len(char_start_times):
                self.logger.warning(f"Section {section.get('section_id')} has invalid timing data")
                continue

            # ステップ1: まず \n で分割（明示的な改行を優先）
            subsections = self._split_section_by_newline(
                text,
                characters,
                char_start_times,
                char_end_times
            )

            # 各サブセクションを処理
            for subsection in subsections:
                subsection_chars = subsection["characters"]
                subsection_start_times = subsection["start_times"]
                subsection_end_times = subsection["end_times"]

                if not subsection_chars:
                    continue

                # 句読点位置をマッピング
                # 修正後: charactersに句読点が含まれるため、直接検出
                punctuation_positions = self._find_punctuation_positions_from_characters(subsection_chars)

                # 文字種境界を検出
                boundaries = self._detect_character_boundaries(subsection_chars)

                # ステップ2: 句読点で大まかに分割
                chunks = self._split_by_punctuation(
                    subsection_chars,
                    punctuation_positions,
                    subsection_start_times,
                    subsection_end_times,
                    offset
                )

                # 各チャンクを処理
                for chunk in chunks:
                    chunk_chars = chunk["characters"]
                    chunk_start_times = chunk["start_times"]
                    chunk_end_times = chunk["end_times"]

                    if not chunk_chars:
                        continue

                    # チャンクがmax_charsを超える場合は再分割
                    if len(chunk_chars) > max_chars:
                        sub_chunks = self._split_large_chunk(
                            chunk_chars,
                            chunk_start_times,
                            chunk_end_times,
                            max_chars,
                            boundaries
                        )
                    else:
                        sub_chunks = [chunk]

                    # 各サブチャンクを字幕エントリに変換（一時保存）
                    for sub_chunk in sub_chunks:
                        sub_chars = sub_chunk["characters"]
                        sub_start_times = sub_chunk["start_times"]
                        sub_end_times = sub_chunk["end_times"]

                        if not sub_chars:
                            continue

                        # 開始・終了時刻
                        subtitle_start = sub_start_times[0]
                        subtitle_end = sub_end_times[-1]
                        original_duration = subtitle_end - subtitle_start

                        # 句読点位置と境界を再計算（サブチャンク用）
                        # 修正後: charactersに句読点が含まれるため、直接検出
                        sub_punct = self._find_punctuation_positions_from_characters(sub_chars)
                        sub_boundaries = self._detect_character_boundaries(sub_chars)

                        # 複数行に分割
                        lines = self._split_into_balanced_lines(
                            text="".join(sub_chars),
                            characters=sub_chars,
                            max_chars_per_line=self.max_chars_per_line,
                            max_lines=self.max_lines,
                            punctuation_positions=sub_punct,
                            boundaries=sub_boundaries
                        )

                        # 空行を埋める
                        while len(lines) < 3:
                            lines.append("")

                        # 一時的に保存（調整前）
                        temp_subtitles.append({
                            "start": subtitle_start,
                            "end": subtitle_end,
                            "original_duration": original_duration,
                            "lines": lines
                        })

        # 全字幕の終了時刻を調整（重なり防止）
        subtitles = []
        subtitle_index = 1

        for i, temp_sub in enumerate(temp_subtitles):
            subtitle_start = temp_sub["start"]
            subtitle_end = temp_sub["end"]
            original_duration = temp_sub["original_duration"]
            lines = temp_sub["lines"]

            # 次の字幕があるか確認
            next_start = None
            if i + 1 < len(temp_subtitles):
                next_start = temp_subtitles[i + 1]["start"]

            # 🔥 修正: 文字レベルタイミング使用時は subtitle_gap を適用しない
            # 理由: audio_timing.json から取得した文字レベルのタイミングは既に正確なため
            # 最小ギャップはフレームレート基準で計算（フレーム境界でのレンダリングを考慮）
            # config から fps を取得 (デフォルト: 30fps)
            fps = self.config.get("video", {}).get("fps") or self.config.get("fps", 30)
            frame_duration = 1.0 / fps  # 30fps なら 0.033秒
            # 最小ギャップは 3フレーム分を確保（視覚的に余裕を持たせる）
            MIN_GAP = frame_duration * 3  # 30fps なら 0.1秒

            # 表示時間の制約を適用（次の字幕を考慮）
            # 音声の実際の長さを基本とし、必要に応じて調整する
            duration = subtitle_end - subtitle_start

            if duration < min_duration:
                # min_display_duration を適用（短すぎる場合）
                ideal_end = subtitle_start + min_duration

                if self.prevent_overlap and next_start is not None:
                    # 次の字幕との重なりを防ぐ（最小ギャップのみ）
                    max_allowed_end = next_start - MIN_GAP

                    if self.overlap_priority == "next_subtitle":
                        # 次の字幕を優先（重ならないように調整）
                        subtitle_end = min(ideal_end, max_allowed_end)
                    else:
                        # min_duration を優先（重なっても延長）
                        subtitle_end = ideal_end
                else:
                    subtitle_end = ideal_end

            elif duration > max_duration:
                # 音声が長い場合の処理
                # 原則: 音声の実際の長さを尊重（次の字幕と重ならない限り）
                if self.prevent_overlap and next_start is not None:
                    max_allowed_end = next_start - MIN_GAP

                    if subtitle_end <= max_allowed_end:
                        # 音声の実際の長さを維持（次の字幕と重ならない）
                        pass
                    else:
                        # 次の字幕と重なるので調整
                        subtitle_end = max_allowed_end
                else:
                    # 次の字幕がない場合は max_duration で制限
                    ideal_end = subtitle_start + max_duration
                    subtitle_end = min(subtitle_end, ideal_end)

            else:
                # duration が min と max の範囲内にある場合
                # 音声の実際の長さを維持
                if self.prevent_overlap and next_start is not None:
                    max_allowed_end = next_start - MIN_GAP
                    if subtitle_end > max_allowed_end:
                        subtitle_end = max_allowed_end

            # 最終チェック: subtitle_end が subtitle_start より小さくならないようにする
            # （次の字幕の開始時刻が現在の字幕より前にある異常ケース対策）
            MIN_SUBTITLE_DURATION = 0.1  # 最低0.1秒
            if subtitle_end <= subtitle_start:
                self.logger.warning(
                    f"Subtitle {subtitle_index}: end_time ({subtitle_end:.3f}s) <= start_time ({subtitle_start:.3f}s). "
                    f"Adjusting to minimum duration ({MIN_SUBTITLE_DURATION}s)."
                )
                subtitle_end = subtitle_start + MIN_SUBTITLE_DURATION

            # 最終的な字幕を作成
            subtitles.append(SubtitleEntry(
                index=subtitle_index,
                start_time=subtitle_start,
                end_time=subtitle_end,
                text_line1=lines[0] if len(lines) > 0 else "",
                text_line2=lines[1] if len(lines) > 1 else "",
                text_line3=lines[2] if len(lines) > 2 else ""
            ))
            subtitle_index += 1

        self.logger.info(f"Generated {len(subtitles)} subtitles from character timings")
        return subtitles

    def _split_section_by_newline(
        self,
        text: str,
        characters: List[str],
        start_times: List[float],
        end_times: List[float]
    ) -> List[Dict[str, Any]]:
        """
        テキストを \n で分割（明示的な改行を優先）

        文字列マッチングで text と characters の対応を取る。
        記号（カッコ類、空白）は除外してマッチング。句読点は含める。

        Args:
            text: 元のテキスト（\n を含む可能性がある）
            characters: 文字配列
            start_times: 各文字の開始時間
            end_times: 各文字の終了時間

        Returns:
            サブセクションのリスト（各サブセクションは characters, start_times, end_times を持つ）
        """
        if '\n' not in text:
            # \n がない場合はそのまま返す
            return [{
                "characters": characters,
                "start_times": start_times,
                "end_times": end_times
            }]

        # text を \n で分割
        text_parts = [part.strip() for part in text.split('\n') if part.strip()]

        if len(text_parts) <= 1:
            # 分割の必要がない
            return [{
                "characters": characters,
                "start_times": start_times,
                "end_times": end_times
            }]

        # characters を文字列に変換
        chars_str = ''.join(characters)

        # 除外する記号（カッコ類、空白のみ。句読点は含める）
        exclude_symbols = set([' ', '　', '「', '」', '『', '』', '（', '）', '(', ')'])

        subsections = []
        search_start = 0
        match_failed = False

        for part in text_parts:
            # part から記号を除外
            part_clean = ''.join([c for c in part if c not in exclude_symbols])

            if not part_clean:
                continue

            # chars_str から part_clean を探す（search_start から）
            pos = chars_str.find(part_clean, search_start)

            if pos == -1:
                # 見つからない場合は警告を出して、分割を諦める
                self.logger.warning(
                    f"Could not match newline-separated part: '{part[:30]}...' "
                    f"(cleaned: '{part_clean[:30]}...'). "
                    f"Skipping newline split for this section."
                )
                match_failed = True
                break

            end_pos = pos + len(part_clean)

            subsections.append({
                "characters": characters[pos:end_pos],
                "start_times": start_times[pos:end_pos],
                "end_times": end_times[pos:end_pos]
            })

            search_start = end_pos

        # マッチングに失敗した場合は、分割を諦めて全体を返す
        if match_failed or not subsections:
            return [{
                "characters": characters,
                "start_times": start_times,
                "end_times": end_times
            }]

        return subsections

    def _split_by_punctuation(
        self,
        characters: List[str],
        punctuation_positions: Dict[int, str],
        start_times: List[float],
        end_times: List[float],
        offset: float
    ) -> List[Dict[str, Any]]:
        """
        句読点で大まかに分割（「。」のみで分割、「、」では分割しない）

        Returns:
            チャンクのリスト（各チャンクは characters, start_times, end_times を持つ）
        """
        chunks = []
        current_chars = []
        current_starts = []
        current_ends = []

        for i, char in enumerate(characters):
            current_chars.append(char)
            current_starts.append(start_times[i] + offset)
            current_ends.append(end_times[i] + offset)

            # 「。」「！」「？」の文字を含めて分割（「、」では分割しない）
            current_punct = punctuation_positions.get(i)
            should_split = (current_punct in ["。", "！", "？"]) or i == len(characters) - 1

            if should_split:
                if current_chars:
                    chunks.append({
                        "characters": current_chars.copy(),
                        "start_times": current_starts.copy(),
                        "end_times": current_ends.copy()
                    })
                    current_chars = []
                    current_starts = []
                    current_ends = []

        # 残りがあれば追加
        if current_chars:
            chunks.append({
                "characters": current_chars,
                "start_times": current_starts,
                "end_times": current_ends
            })

        return chunks

    def _split_large_chunk(
        self,
        characters: List[str],
        start_times: List[float],
        end_times: List[float],
        max_chars: int,
        boundaries: Dict[str, List[int]]
    ) -> List[Dict[str, Any]]:
        """
        大きなチャンクをスコアリング方式で分割

        残りが10文字未満にならないように調整する。
        """
        MIN_CHUNK_LENGTH = 10  # 最小チャンク長

        chunks = []
        remaining_chars = characters.copy()
        remaining_starts = start_times.copy()
        remaining_ends = end_times.copy()

        # 形態素境界を検出（全体で一度だけ）
        morpheme_info = self._detect_morpheme_boundaries(characters)

        while remaining_chars:
            if len(remaining_chars) <= max_chars:
                # 残りをそのまま追加
                chunks.append({
                    "characters": remaining_chars,
                    "start_times": remaining_starts,
                    "end_times": remaining_ends
                })
                break

            # 分割位置の上限を計算（残りが10文字未満にならないように）
            # 例: 40文字なら、max_split_pos = 40 - 10 = 30
            max_split_pos = len(remaining_chars) - MIN_CHUNK_LENGTH

            # 調整された max_chars（通常は36だが、残りが短くなりすぎる場合は小さくする）
            adjusted_max_chars = min(max_chars, max_split_pos)

            # adjusted_max_chars が MIN_CHUNK_LENGTH より小さい場合は、分割せずに全体を1つに
            if adjusted_max_chars < MIN_CHUNK_LENGTH:
                chunks.append({
                    "characters": remaining_chars,
                    "start_times": remaining_starts,
                    "end_times": remaining_ends
                })
                break

            # 優先順位1: 36文字（max_chars）より前で最も後ろの「、」を探す
            comma_positions = [i for i, c in enumerate(remaining_chars) if c == '、' and i < max_chars]

            split_pos = None
            reason = ""

            if comma_positions:
                # 最も後ろの「、」で分割（「、」を含める）
                split_pos = comma_positions[-1] + 1
                reason = "comma_split_priority"

                self.logger.debug(
                    f"Found comma at position {comma_positions[-1]} "
                    f"(text length: {len(remaining_chars)}, max_chars: {max_chars})"
                )
            else:
                # 優先順位2: 「、」がない場合は既存のスコアリングロジックを使用
                # 残りのテキストに対する形態素情報を更新
                offset = len(characters) - len(remaining_chars)
                remaining_morpheme_info = {
                    'boundaries': [b - offset for b in morpheme_info.get('boundaries', []) if b >= offset],
                    'verb_adjective_positions': set([p - offset for p in morpheme_info.get('verb_adjective_positions', set()) if p >= offset])
                }

                # 分割位置を決定
                sub_boundaries = self._detect_character_boundaries(remaining_chars)
                split_pos, reason = self._find_split_position_with_score(
                    text="".join(remaining_chars),
                    characters=remaining_chars,
                    max_chars=adjusted_max_chars,
                    punctuation_positions={},  # 句読点は既に処理済み
                    boundaries=sub_boundaries,
                    morpheme_info=remaining_morpheme_info
                )

            # チャンクを追加
            chunks.append({
                "characters": remaining_chars[:split_pos],
                "start_times": remaining_starts[:split_pos],
                "end_times": remaining_ends[:split_pos]
            })

            # 残りを更新
            remaining_chars = remaining_chars[split_pos:]
            remaining_starts = remaining_starts[split_pos:]
            remaining_ends = remaining_ends[split_pos:]

        return chunks

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
