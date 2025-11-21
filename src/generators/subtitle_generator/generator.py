"""
字幕生成のメインロジック

全体フローの制御、各コンポーネントの組み合わせを行う。
"""

from typing import List, Dict, Any, Optional, Tuple
import logging

from src.core.models import SubtitleEntry
from src.utils.whisper_timing import create_whisper_extractor
from .text_splitter import TextSplitter
from .timing_processor import TimingProcessor
from .formatter import SubtitleFormatter


class SubtitleGenerator:
    """
    字幕生成のメインクラス（オーケストレーター）

    責任:
    - 全体フローの制御
    - TextSplitter, TimingProcessor, SubtitleFormatter の組み合わせ
    - audio_timing.json からの字幕生成

    変更頻度: 低（フローの変更時のみ）
    """

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

        # 各コンポーネントを初期化
        self.splitter = TextSplitter(config, logger=logger)
        self.timing = TimingProcessor(config, logger=logger)
        self.formatter = SubtitleFormatter(config, logger=logger)

        # 設定値の取得（互換性のため保持）
        self.max_lines = max(1, config.get("max_lines", 2))
        self.max_chars_per_line = config.get("max_chars_per_line", 20)

        timing_config = config.get("timing", {})
        self.min_display_duration = timing_config.get("min_display_duration", 4.0)
        self.max_display_duration = timing_config.get("max_display_duration", 6.0)
        self.lead_time = timing_config.get("lead_time", 0.2)
        self.subtitle_gap = timing_config.get("subtitle_gap", 0.1)
        self.prevent_overlap = timing_config.get("prevent_overlap", True)
        self.overlap_priority = timing_config.get("overlap_priority", "next_subtitle")

        morphological = config.get("morphological_analysis", {})
        self.use_mecab = morphological.get("use_mecab", False)
        self.break_on = morphological.get("break_on", ["。", "、", "！", "？"])

        # 分割戦略の設定（互換性のため保持）
        splitting = config.get("splitting", {})
        self.window_size = splitting.get("window_size", 3)
        self.priority_scores = splitting.get("priority_scores", {
            "punctuation": 120,
            "morpheme_boundary": 150,
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
            "splits_verb_adjective": 500
        })
        self.particles = splitting.get("particles", [
            "は", "が", "を", "に", "で", "と", "も", "や", "から", "まで", "より"
        ])
        self.balance_lines = splitting.get("balance_lines", True)
        self.min_line_length = splitting.get("min_line_length", 3)

        # 句読点表示設定
        self.remove_punctuation = config.get("remove_punctuation_in_display", False)

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

                if self.splitter.remove_punctuation_in_display:
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

                if self.splitter.remove_punctuation_in_display:
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
                boundaries=self.splitter._detect_character_boundaries(remaining_chars),
                morpheme_info=remaining_morpheme_info
            )

            # この行のテキストを取得
            line_chars = remaining_chars[:split_pos]
            line_text = "".join(line_chars)

            if self.splitter.remove_punctuation_in_display:
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
            offset = section.get("offset", 0.0)

            # 🆕 タイトル字幕を追加（section_titleがある場合）
            title_timing = section.get("title_timing")
            if title_timing:
                title_text = title_timing.get("text", "")
                title_start = offset + title_timing.get("start_time", 0.0)
                title_end = offset + title_timing.get("end_time", 0.0)

                # タイトル字幕を一時保存（special_typeマーカー付き）
                temp_subtitles.append({
                    "start": title_start,
                    "end": title_end,
                    "original_duration": title_end - title_start,
                    "lines": [title_text, "", ""],
                    "special_type": "section_title"  # マーカー
                })

                self.logger.debug(f"Added title subtitle: {title_text} ({title_start:.2f}s - {title_end:.2f}s)")

            # 🆕 narration_timingから文字とタイミング情報を取得
            narration_timing = section.get("narration_timing", {})
            if not narration_timing:
                self.logger.warning(f"Section {section.get('section_id')} has no narration_timing")
                continue
            
            text = narration_timing.get("text", section.get("text", ""))
            characters = narration_timing.get("characters", [])
            char_start_times = narration_timing.get("char_start_times", [])
            char_end_times = narration_timing.get("char_end_times", [])
            
            # 🆕 タイミング情報の開始時刻をoffsetに加算
            narration_start = narration_timing.get("start_time", 0.0)
            if char_start_times:
                # 相対時刻を絶対時刻に変換（offset + narration_startを加算）
                char_start_times = [offset + narration_start + t for t in char_start_times]
            if char_end_times:
                char_end_times = [offset + narration_start + t for t in char_end_times]

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
                boundaries = self.splitter._detect_character_boundaries(subsection_chars)

                # ステップ2: 句読点で大まかに分割
                # 🆕 offsetは既にchar_start_times/char_end_timesに加算済みなので、0を渡す
                chunks = self._split_by_punctuation(
                    subsection_chars,
                    punctuation_positions,
                    subsection_start_times,
                    subsection_end_times,
                    0.0  # 既に絶対時刻に変換済み
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
                        sub_boundaries = self.splitter._detect_character_boundaries(sub_chars)

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
                            "lines": lines,
                            "special_type": None  # 通常の字幕
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

                # 🔥 NEW: 句点で終わる場合は延長を試みる
                last_char = ""
                for line in reversed(lines):
                    if line:
                        last_char = line[-1]
                        break

                if last_char in ["。", "！", "？", "!", "?"]:
                    # 句点で終わる字幕 → 延長を検討
                    if self.prevent_overlap and next_start is not None:
                        max_allowed_end = next_start - MIN_GAP
                        available_time = max_allowed_end - subtitle_end

                        # 余裕が0.5秒以上あれば60%延長
                        if available_time >= 0.5:
                            extension = available_time * 0.6
                            subtitle_end = subtitle_end + extension

                            self.logger.debug(
                                f"Subtitle {subtitle_index}: Extended end_time by {extension:.3f}s "
                                f"for punctuation (available: {available_time:.3f}s, "
                                f"new end: {subtitle_end:.3f}s)"
                            )
                        elif available_time > 0:
                            # 余裕は少ないが、次の字幕とは重ならないように調整
                            if subtitle_end > max_allowed_end:
                                subtitle_end = max_allowed_end
                    elif next_start is None:
                        # 最後の字幕（次の字幕がない）の場合は一律0.5秒延長
                        extension = 0.5
                        subtitle_end = subtitle_end + extension

                        self.logger.debug(
                            f"Subtitle {subtitle_index} (LAST): Extended end_time by {extension:.3f}s "
                            f"for punctuation (new end: {subtitle_end:.3f}s)"
                        )
                else:
                    # 句点以外 → 通常の重複チェックのみ
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
                special_type=temp_sub.get("special_type")  # special_typeを取得
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
        
        ただし、鍵かっこ内の改行は無視する。

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
        # 🔥 NEW: 鍵かっこ内の改行を削除（常に実行）
        cleaned_characters = []
        cleaned_start_times = []
        cleaned_end_times = []
        in_quotation = False

        for i, char in enumerate(characters):
            if char == '「':
                in_quotation = True
                cleaned_characters.append(char)
                cleaned_start_times.append(start_times[i])
                cleaned_end_times.append(end_times[i])
            elif char == '」':
                in_quotation = False
                cleaned_characters.append(char)
                cleaned_start_times.append(start_times[i])
                cleaned_end_times.append(end_times[i])
            elif char == '\n' and in_quotation:
                # 鍵かっこ内の改行はスキップ（タイミングも削除）
                continue
            else:
                cleaned_characters.append(char)
                cleaned_start_times.append(start_times[i])
                cleaned_end_times.append(end_times[i])

        # 以降、cleaned_* を使用
        characters = cleaned_characters
        start_times = cleaned_start_times
        end_times = cleaned_end_times

        if '\n' not in text:
            # \n がない場合はそのまま返す（改行削除後）
            return [{
                "characters": characters,
                "start_times": start_times,
                "end_times": end_times
            }]

        # 鍵かっこ内の改行を無視して分割
        text_parts = []
        current_part = ""
        in_quotation = False
        
        for char in text:
            if char == '「':
                in_quotation = True
                current_part += char
            elif char == '」':
                in_quotation = False
                current_part += char
            elif char == '\n' and not in_quotation:
                # 鍵かっこ外の改行でのみ分割
                if current_part.strip():
                    text_parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
        
        # 最後の部分を追加
        if current_part.strip():
            text_parts.append(current_part.strip())

        if len(text_parts) <= 1:
            # 分割の必要がない（改行削除済み）
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
        
        ただし、鍵かっこ内の句読点では分割しない。

        Returns:
            チャンクのリスト（各チャンクは characters, start_times, end_times を持つ）
        """
        chunks = []
        current_chars = []
        current_starts = []
        current_ends = []
        in_quotation = False  # 鍵かっこ内フラグ

        for i, char in enumerate(characters):
            # 改行・空白はチャンクに含めない（タイミングのズレを防ぐ）
            if char in ['\n', '\r', ' ', '\t']:
                continue

            current_chars.append(char)
            current_starts.append(start_times[i] + offset)
            current_ends.append(end_times[i] + offset)

            # 鍵かっこの開閉を追跡
            if char == '「':
                in_quotation = True
            elif char == '」':
                in_quotation = False

            # 「。」「！」「？」の文字を含めて分割
            # 鍵かっこ内でも、30文字超えた場合は「、」で分割
            current_punct = punctuation_positions.get(i)
            should_split = (
                # 通常の句点では分割（鍵かっこ外のみ）
                (current_punct in ["。", "！", "？"] and not in_quotation)
                # 最後の文字は必ず分割
                or i == len(characters) - 1
                # 🔥 NEW: 鍵かっこ内でも30文字超えたら「、」で分割
                or (in_quotation and current_punct == "、" and len(current_chars) > 30)
            )

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
                sub_boundaries = self.splitter._detect_character_boundaries(remaining_chars)
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

