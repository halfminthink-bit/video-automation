"""
テキスト分割ロジック

日本語テキストの適切な分割を行う。
改行位置の決定、鍵かっこの処理、句読点の削除など。
"""

from typing import List, Dict, Any, Optional
import logging

from ..core.models import SubtitleEntry


class TextSplitter:
    """
    テキスト分割ロジック（言語依存部分）

    責任:
    - 句点での文分割（鍵かっこ考慮）
    - 長文の適切な分割（36文字制限）
    - 2行への分割（18文字×2行）
    - 分割位置のスコアリング
    - 句読点削除

    変更頻度: 高（改行ロジックの調整が頻繁）
    """

    def __init__(
        self,
        config: Dict[str, Any],
        language: str = "ja",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            config: subtitle_generation.yamlの設定
            language: 言語コード（将来の英語対応用）
            logger: ロガー
        """
        self.config = config
        self.language = language
        self.logger = logger or logging.getLogger(__name__)

        # 設定値を取得
        self.max_lines = config.get("max_lines", 2)
        self.max_chars_per_line = config.get("max_chars_per_line", 18)

        # 分割設定
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
            "splits_verb_adjective": 500,
            "min_chunk_length": 200,
            "balance": 100
        })
        self.particles = splitting.get("particles", [
            "は", "が", "を", "に", "で", "と", "も", "や", "から", "まで", "より"
        ])
        self.balance_lines = splitting.get("balance_lines", True)
        self.min_line_length = splitting.get("min_line_length", 3)

        # 句読点設定
        morphological = config.get("morphological_analysis", {})
        self.break_on = morphological.get("break_on", ["。", "！", "？"])

        # 句読点表示設定
        # 注意: メソッド名 remove_punctuation と衝突しないようにフィールド名を変更
        self.remove_punctuation_in_display = config.get("remove_punctuation_in_display", False)

        # MeCab設定（未使用だが互換性のため保持）
        self.use_mecab = morphological.get("use_mecab", False)
        self.mecab = None

    def _get_char_type(self, char: str) -> str:
        """
        文字の種類を判定

        Returns:
            'hiragana', 'katakana', 'kanji', 'other'
        """
        code = ord(char)

        # ひらがな: U+3040 - U+309F
        if 0x3040 <= code <= 0x309F:
            return 'hiragana'

        # カタカナ: U+30A0 - U+30FF
        if 0x30A0 <= code <= 0x30FF:
            return 'katakana'

        # 漢字: U+4E00 - U+9FFF
        if 0x4E00 <= code <= 0x9FFF:
            return 'kanji'

        return 'other'

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

    def _detect_character_boundaries(
        self,
        characters: List[str]
    ) -> Dict[str, List[int]]:
        """
        文字種の境界を検出

        Returns:
            {
                'punctuation': [3, 7, ...],         # 句読点位置
                'particles': [5, 10, ...],          # 助詞の後
                'hiragana_to_kanji': [2, 8, ...],   # ひらがな→漢字
                'kanji_to_hiragana': [4, 12, ...],  # 漢字→ひらがな
                'katakana_boundary': [6, 14, ...]   # カタカナ境界
            }
        """
        boundaries = {
            'punctuation': [],
            'particles': [],
            'hiragana_to_kanji': [],
            'kanji_to_hiragana': [],
            'katakana_boundary': []
        }

        # 句読点位置
        for i, char in enumerate(characters):
            if char in ["。", "、", "！", "？", "…"]:
                boundaries['punctuation'].append(i)

        # 助詞の位置
        for i, char in enumerate(characters):
            if char in self.particles:
                # 助詞の直後の位置
                if i + 1 < len(characters):
                    boundaries['particles'].append(i + 1)

        # 文字種境界
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

        return boundaries

    def remove_punctuation(
        self,
        subtitles: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        字幕から句読点を削除（鍵かっこ内は保持）

        Args:
            subtitles: 句読点を含む字幕リスト

        Returns:
            句読点を削除した字幕リスト
        """
        # 削除対象の句読点
        punctuation_to_remove = ['。', '！', '？', '，', '．']

        cleaned_subtitles = []

        for subtitle in subtitles:
            # 2行にまたがる鍵かっこに対応するため、結合してから処理
            combined_text = subtitle.text_line1
            if subtitle.text_line2:
                combined_text += subtitle.text_line2

            # 結合テキストから句読点を削除（鍵かっこ内は残す）
            cleaned_combined, char_mapping = self._remove_punctuation_except_in_quotation_with_mapping(
                combined_text,
                punctuation_to_remove
            )

            # 元の行1の最後の文字が処理後のどの位置に対応するかを取得
            original_line1_len = len(subtitle.text_line1)
            split_pos = len(cleaned_combined)
            if original_line1_len > 0 and original_line1_len - 1 < len(char_mapping):
                # 行1の最後の文字の位置を取得（削除された文字の場合は前の有効な文字を探す）
                for i in range(original_line1_len - 1, -1, -1):
                    if i < len(char_mapping) and char_mapping[i] != -1:
                        split_pos = char_mapping[i] + 1
                        break

            # 分割
            line1 = cleaned_combined[:split_pos] if split_pos > 0 else ""
            line2 = cleaned_combined[split_pos:] if subtitle.text_line2 else ""

            # 空の字幕をスキップ（句読点のみの行が削除されて空になった場合）
            if not line1.strip() and not line2.strip():
                self.logger.debug(f"Skipping empty subtitle at index {subtitle.index}")
                continue

            # 新しいSubtitleEntryを作成
            cleaned_subtitle = SubtitleEntry(
                index=subtitle.index,
                start_time=subtitle.start_time,
                end_time=subtitle.end_time,
                text_line1=line1,
                text_line2=line2
            )

            cleaned_subtitles.append(cleaned_subtitle)

        # インデックスを再割り当て（空の字幕をスキップした場合に連番にする）
        for i, subtitle in enumerate(cleaned_subtitles, start=1):
            subtitle.index = i

        self.logger.info(f"Removed punctuation from {len(cleaned_subtitles)} subtitles")
        return cleaned_subtitles

    def _remove_punctuation_except_in_quotation_with_mapping(
        self,
        text: str,
        punctuation_to_remove: List[str]
    ) -> tuple:
        """
        鍵かっこ内の句読点は残して削除（文字位置のマッピングも返す）

        Args:
            text: 処理対象テキスト
            punctuation_to_remove: 削除対象の句読点リスト

        Returns:
            (処理後のテキスト, 元の位置→処理後位置のマッピング)
        """
        result = []
        char_mapping = []  # 元の位置 -> 処理後の位置
        in_quotation = False
        result_pos = 0

        for i, char in enumerate(text):
            if char == '「' or char == '『':
                in_quotation = True
                result.append(char)
                char_mapping.append(result_pos)
                result_pos += 1
            elif char == '」' or char == '』':
                in_quotation = False
                result.append(char)
                char_mapping.append(result_pos)
                result_pos += 1
            elif char in punctuation_to_remove and not in_quotation:
                # 鍵かっこ外の句読点のみ削除（マッピングには含めない）
                char_mapping.append(-1)  # 削除された文字
            else:
                result.append(char)
                char_mapping.append(result_pos)
                result_pos += 1

        return ''.join(result), char_mapping
