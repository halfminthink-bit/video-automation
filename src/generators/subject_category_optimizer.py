"""
偉人カテゴリ別最適化システム

偉人のカテゴリに応じてテキストを最適化し、
カテゴリ特有のキーワードとアプローチを適用
"""

import logging
from typing import Dict, Any, List, Optional


class SubjectCategoryOptimizer:
    """偉人のカテゴリに応じた最適化を行うクラス"""

    # カテゴリ定義とキーワード・アプローチのマッピング
    CATEGORIES = {
        "科学者": {
            "keywords": ["発見", "革命", "常識を覆した", "真理", "実験", "理論"],
            "approach": "discovery_focus",
            "emotion": "dramatic",
            "description": "科学的発見や革新に焦点を当てる"
        },
        "武将・軍人": {
            "keywords": ["戦い", "勝利", "敗北", "裏切り", "策略", "征服"],
            "approach": "battle_drama",
            "emotion": "command",
            "description": "戦闘や戦略のドラマに焦点を当てる"
        },
        "芸術家": {
            "keywords": ["狂気", "天才", "作品に隠された", "苦悩", "創造", "情熱"],
            "approach": "artistic_mystery",
            "emotion": "mystery",
            "description": "芸術的創造と内面の葛藤に焦点を当てる"
        },
        "政治家": {
            "keywords": ["陰謀", "改革", "失脚", "権力", "演説", "決断"],
            "approach": "political_intrigue",
            "emotion": "contrast",
            "description": "政治的駆け引きと権力闘争に焦点を当てる"
        },
        "発明家": {
            "keywords": ["失敗", "成功", "盗まれた", "発明", "試行錯誤", "革新"],
            "approach": "innovation_story",
            "emotion": "dramatic",
            "description": "発明のプロセスと困難に焦点を当てる"
        },
        "思想家": {
            "keywords": ["禁じられた", "革命的", "危険な思想", "哲学", "真理", "疑問"],
            "approach": "philosophical_impact",
            "emotion": "mystery",
            "description": "思想の革新性と影響に焦点を当てる"
        },
        "医師・医学者": {
            "keywords": ["命を救った", "病を治した", "医療革命", "献身", "犠牲", "治療"],
            "approach": "medical_sacrifice",
            "emotion": "dramatic",
            "description": "医療の進歩と人命への貢献に焦点を当てる"
        },
        "探検家": {
            "keywords": ["未知", "冒険", "発見", "危険", "到達", "航海"],
            "approach": "adventure_risk",
            "emotion": "command",
            "description": "冒険と発見のドラマに焦点を当てる"
        },
        "作家・詩人": {
            "keywords": ["言葉", "物語", "禁書", "苦悩", "執筆", "表現"],
            "approach": "literary_impact",
            "emotion": "mystery",
            "description": "文学的創造と社会的影響に焦点を当てる"
        },
        "宗教家": {
            "keywords": ["信仰", "奇跡", "迫害", "改革", "布教", "犠牲"],
            "approach": "spiritual_journey",
            "emotion": "contrast",
            "description": "信仰と精神的旅路に焦点を当てる"
        },
        "その他": {
            "keywords": ["真実", "秘密", "運命", "人生", "遺産", "影響"],
            "approach": "general_impact",
            "emotion": "dramatic",
            "description": "一般的なインパクトに焦点を当てる"
        }
    }

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化

        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)

    def detect_category(
        self,
        subject: str,
        analysis: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        偉人のカテゴリを検出

        Args:
            subject: 偉人の名前
            analysis: 分析結果（オプション）

        Returns:
            検出されたカテゴリ名
        """
        # 分析結果にカテゴリが含まれている場合
        if analysis and "category" in analysis:
            detected = analysis["category"]
            # カテゴリが存在するか確認
            if detected in self.CATEGORIES:
                self.logger.info(f"Category detected from analysis: {detected}")
                return detected

        # 名前や業績からカテゴリを推測
        category = self._infer_category_from_context(subject, analysis)
        self.logger.info(f"Category inferred for {subject}: {category}")

        return category

    def _infer_category_from_context(
        self,
        subject: str,
        analysis: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        コンテキストからカテゴリを推測

        Args:
            subject: 偉人の名前
            analysis: 分析結果

        Returns:
            推測されたカテゴリ名
        """
        # 分析結果の功績や時代背景から推測
        if analysis:
            achievement = analysis.get("achievement", "").lower()
            dramatic = analysis.get("dramatic_element", "").lower()

            # キーワードマッチング
            for category, info in self.CATEGORIES.items():
                keywords = [kw.lower() for kw in info["keywords"]]
                for keyword in keywords:
                    if keyword in achievement or keyword in dramatic:
                        return category

        # デフォルトは「その他」
        return "その他"

    def optimize_for_category(
        self,
        subject: str,
        text_variations: List[Dict[str, Any]],
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        カテゴリに応じてテキストを最適化

        Args:
            subject: 偉人の名前
            text_variations: テキストバリエーション
            category: カテゴリ（Noneの場合は自動検出）

        Returns:
            最適化されたテキストバリエーション
        """
        if not category:
            category = self.detect_category(subject)

        self.logger.info(f"Optimizing text for category: {category}")

        category_info = self.CATEGORIES.get(category, self.CATEGORIES["その他"])
        keywords = category_info["keywords"]

        optimized_variations = []

        for variation in text_variations:
            optimized = variation.copy()

            # カテゴリ情報を追加
            optimized["category"] = category
            optimized["category_approach"] = category_info["approach"]
            optimized["recommended_emotion"] = category_info["emotion"]

            # キーワードマッチングによるスコア調整
            keyword_score = self._calculate_keyword_score(
                variation.get("main", ""),
                variation.get("sub", ""),
                keywords
            )
            optimized["keyword_match_score"] = keyword_score

            # 既存のeffectiveness_scoreと組み合わせて総合スコアを計算
            base_score = variation.get("effectiveness_score", 5)
            optimized["total_score"] = (base_score + keyword_score) / 2

            optimized_variations.append(optimized)

        # 総合スコアでソート
        optimized_variations.sort(key=lambda x: x.get("total_score", 0), reverse=True)

        self.logger.info(
            f"Optimized {len(optimized_variations)} variations for category: {category}"
        )

        return optimized_variations

    def _calculate_keyword_score(
        self,
        main_text: str,
        sub_text: str,
        keywords: List[str]
    ) -> float:
        """
        キーワードマッチングスコアを計算

        Args:
            main_text: 上部テキスト
            sub_text: 下部テキスト
            keywords: カテゴリキーワードリスト

        Returns:
            スコア（0-10）
        """
        score = 0.0
        combined_text = main_text + sub_text

        for keyword in keywords:
            if keyword in combined_text:
                # メインテキストに含まれる場合はより高いスコア
                if keyword in main_text:
                    score += 2.0
                else:
                    score += 1.0

        # 最大10点に正規化
        max_possible_score = len(keywords) * 2.0
        normalized_score = min(10.0, (score / max_possible_score) * 10.0) if max_possible_score > 0 else 0.0

        return normalized_score

    def get_category_info(self, category: str) -> Dict[str, Any]:
        """
        カテゴリ情報を取得

        Args:
            category: カテゴリ名

        Returns:
            カテゴリ情報の辞書
        """
        return self.CATEGORIES.get(category, self.CATEGORIES["その他"])

    def apply_category_style(
        self,
        text_pair: Dict[str, str],
        category: str
    ) -> Dict[str, str]:
        """
        カテゴリスタイルを適用（将来の拡張用）

        Args:
            text_pair: テキストペア
            category: カテゴリ

        Returns:
            スタイル適用後のテキストペア
        """
        # 現在はそのまま返すが、将来的にカテゴリ固有の
        # スタイル調整を追加可能
        styled_pair = text_pair.copy()
        styled_pair["applied_category"] = category

        return styled_pair

    def get_all_categories(self) -> List[str]:
        """
        すべてのカテゴリ名を取得

        Returns:
            カテゴリ名のリスト
        """
        return list(self.CATEGORIES.keys())

    def get_category_description(self, category: str) -> str:
        """
        カテゴリの説明を取得

        Args:
            category: カテゴリ名

        Returns:
            カテゴリの説明
        """
        category_info = self.CATEGORIES.get(category, self.CATEGORIES["その他"])
        return category_info.get("description", "")


def create_subject_category_optimizer(
    logger: Optional[logging.Logger] = None
) -> SubjectCategoryOptimizer:
    """
    SubjectCategoryOptimizerのファクトリー関数

    Args:
        logger: ロガー

    Returns:
        SubjectCategoryOptimizer インスタンス
    """
    return SubjectCategoryOptimizer(logger=logger)
