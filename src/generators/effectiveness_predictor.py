"""
テキスト効果予測システム

生成されたサムネイルテキストの効果を予測し、
インパクトスコアを計算
"""

import logging
import re
from typing import Dict, Any, List, Optional


class EffectivenessPredictor:
    """生成テキストの効果を予測するクラス"""

    # 感情トリガーワードと重み
    EMOTION_TRIGGERS = {
        "死": 2.0,
        "殺": 2.0,
        "裏切": 1.8,
        "秘密": 1.5,
        "衝撃": 1.5,
        "真実": 1.3,
        "謎": 1.5,
        "驚": 1.3,
        "信じ": 1.2,
        "まさか": 1.5,
        "本当": 1.2,
        "実は": 1.3,
        "隠": 1.4,
        "知ら": 1.3,
        "運命": 1.2,
        "悲劇": 1.4,
        "奇跡": 1.3,
        "禁": 1.4,
        "危険": 1.3,
        "革命": 1.2,
    }

    # 対比表現ワード
    CONTRAST_WORDS = [
        "実は", "本当は", "隠された", "知られざる", "裏の", "真の",
        "なぜ", "どうして", "本当に", "まさか", "意外", "驚き"
    ]

    # 疑問形パターン
    QUESTION_PATTERNS = [
        r"なぜ.+？",
        r"どうして.+？",
        r"本当に.+？",
        r".+か？",
        r"誰.+？",
        r"何.+？",
    ]

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化

        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)

    def predict_impact_score(
        self,
        text_pair: Dict[str, str],
        detailed: bool = False
    ) -> float:
        """
        インパクトスコアを予測（1-10）

        Args:
            text_pair: テキストペア（main, sub）
            detailed: 詳細スコアを計算するか

        Returns:
            インパクトスコア（1-10）
        """
        main_text = text_pair.get("main", "")
        sub_text = text_pair.get("sub", "")

        scores = {
            "emotion": self._score_emotion_triggers(main_text, sub_text),
            "question": self._score_question_form(main_text),
            "number": self._score_number_usage(main_text),
            "contrast": self._score_contrast_expression(main_text, sub_text),
            "length": self._score_text_length(main_text, sub_text),
            "curiosity": self._score_curiosity_factor(sub_text),
        }

        # 総合スコアを計算（重み付け平均）
        weights = {
            "emotion": 0.25,
            "question": 0.20,
            "number": 0.15,
            "contrast": 0.15,
            "length": 0.10,
            "curiosity": 0.15,
        }

        total_score = sum(scores[key] * weights[key] for key in scores)

        # 1-10の範囲に正規化
        final_score = max(1.0, min(10.0, total_score))

        if detailed:
            self.logger.debug(f"Detailed scores: {scores}")
            self.logger.debug(f"Final score: {final_score:.2f}")

        return round(final_score, 2)

    def _score_emotion_triggers(self, main_text: str, sub_text: str) -> float:
        """
        感情トリガーワードのスコアを計算

        Args:
            main_text: 上部テキスト
            sub_text: 下部テキスト

        Returns:
            スコア（0-10）
        """
        score = 0.0
        combined_text = main_text + sub_text

        for trigger, weight in self.EMOTION_TRIGGERS.items():
            if trigger in combined_text:
                # メインテキストに含まれる場合は重みを1.5倍
                if trigger in main_text:
                    score += weight * 1.5
                else:
                    score += weight

        # 最大10点に正規化
        max_score = 10.0
        normalized_score = min(max_score, score)

        return normalized_score

    def _score_question_form(self, main_text: str) -> float:
        """
        疑問形のスコアを計算

        Args:
            main_text: 上部テキスト

        Returns:
            スコア（0-10）
        """
        # 疑問符があれば基本スコア
        if "？" in main_text:
            base_score = 8.0

            # パターンマッチングで追加スコア
            for pattern in self.QUESTION_PATTERNS:
                if re.search(pattern, main_text):
                    return 10.0

            return base_score

        # 疑問形でない場合
        return 3.0

    def _score_number_usage(self, main_text: str) -> float:
        """
        数字の使用スコアを計算

        Args:
            main_text: 上部テキスト

        Returns:
            スコア（0-10）
        """
        # 数字を抽出
        numbers = re.findall(r'\d+', main_text)

        if not numbers:
            return 3.0

        # 数字があれば高スコア
        score = 8.0

        # パーセンテージ表記は特に効果的
        if "%" in main_text or "％" in main_text:
            score = 10.0

        return score

    def _score_contrast_expression(self, main_text: str, sub_text: str) -> float:
        """
        対比表現のスコアを計算

        Args:
            main_text: 上部テキスト
            sub_text: 下部テキスト

        Returns:
            スコア（0-10）
        """
        score = 0.0
        combined_text = main_text + sub_text

        for word in self.CONTRAST_WORDS:
            if word in combined_text:
                score += 1.5
                # メインテキストに含まれる場合は追加ボーナス
                if word in main_text:
                    score += 0.5

        # "〜か〜か" のような対比パターン
        if re.search(r'.+か.+か', main_text):
            score += 3.0

        # 最大10点に正規化
        return min(10.0, score)

    def _score_text_length(self, main_text: str, sub_text: str) -> float:
        """
        テキスト長のスコアを計算（適切な長さか）

        Args:
            main_text: 上部テキスト
            sub_text: 下部テキスト

        Returns:
            スコア（0-10）
        """
        main_len = len(main_text)
        sub_len = len(sub_text)

        # メインテキスト：5-10文字が理想
        if 5 <= main_len <= 10:
            main_score = 10.0
        elif 3 <= main_len <= 12:
            main_score = 7.0
        else:
            main_score = 4.0

        # サブテキスト：20-30文字が理想
        if 20 <= sub_len <= 30:
            sub_score = 10.0
        elif 15 <= sub_len <= 35:
            sub_score = 7.0
        else:
            sub_score = 4.0

        # 平均スコア
        return (main_score + sub_score) / 2

    def _score_curiosity_factor(self, sub_text: str) -> float:
        """
        好奇心誘発度のスコアを計算

        Args:
            sub_text: 下部テキスト

        Returns:
            スコア（0-10）
        """
        score = 5.0  # 基本スコア

        # 好奇心を刺激するフレーズ
        curiosity_phrases = [
            "真実", "秘密", "理由", "本当", "実は", "知られざる",
            "隠された", "真相", "謎", "裏", "意外", "驚き",
            "運命", "招いた", "迎えた", "明らかに"
        ]

        for phrase in curiosity_phrases:
            if phrase in sub_text:
                score += 1.0

        # "〜の真実" "〜の秘密" "〜の理由" などのパターン
        if re.search(r'.+(の|な)(真実|秘密|理由|真相|謎)', sub_text):
            score += 2.0

        # 最大10点に正規化
        return min(10.0, score)

    def rank_variations(
        self,
        variations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        バリエーションをスコアでランク付け

        Args:
            variations: テキストバリエーションのリスト

        Returns:
            スコア順にソートされたリスト
        """
        # 各バリエーションにスコアを追加
        for variation in variations:
            if "effectiveness_score" not in variation:
                score = self.predict_impact_score(variation, detailed=True)
                variation["effectiveness_score"] = score

        # スコアでソート
        ranked = sorted(
            variations,
            key=lambda x: x.get("effectiveness_score", 0),
            reverse=True
        )

        self.logger.info(f"Ranked {len(ranked)} variations by effectiveness score")

        return ranked

    def get_improvement_suggestions(
        self,
        text_pair: Dict[str, str]
    ) -> List[str]:
        """
        改善提案を取得

        Args:
            text_pair: テキストペア

        Returns:
            改善提案のリスト
        """
        suggestions = []
        main_text = text_pair.get("main", "")
        sub_text = text_pair.get("sub", "")

        # メインテキストの長さチェック
        main_len = len(main_text)
        if main_len < 5:
            suggestions.append("メインテキストが短すぎます（推奨：5-10文字）")
        elif main_len > 10:
            suggestions.append("メインテキストが長すぎます（推奨：5-10文字）")

        # サブテキストの長さチェック
        sub_len = len(sub_text)
        if sub_len < 20:
            suggestions.append("サブテキストが短すぎます（推奨：20-30文字）")
        elif sub_len > 30:
            suggestions.append("サブテキストが長すぎます（推奨：20-30文字）")

        # 疑問形の推奨
        if "？" not in main_text:
            suggestions.append("疑問形を使うとより効果的です")

        # 感情トリガーの推奨
        has_emotion = any(trigger in main_text + sub_text for trigger in self.EMOTION_TRIGGERS)
        if not has_emotion:
            suggestions.append("感情に訴える言葉（死、裏切り、秘密など）を含めると効果的です")

        return suggestions


def create_effectiveness_predictor(
    logger: Optional[logging.Logger] = None
) -> EffectivenessPredictor:
    """
    EffectivenessPredictorのファクトリー関数

    Args:
        logger: ロガー

    Returns:
        EffectivenessPredictor インスタンス
    """
    return EffectivenessPredictor(logger=logger)
