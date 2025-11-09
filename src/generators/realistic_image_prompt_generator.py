"""
実写系画像プロンプト生成器

DALL-E等のAI画像生成用に、実写系・フォトリアリスティックな
人物画像プロンプトを生成
"""

import logging
from typing import Dict, Any, Optional


class RealisticImagePromptGenerator:
    """実写系・リアル感重視の画像プロンプト生成クラス"""

    # 時代別スタイル定義
    ERA_STYLES = {
        "古代": {
            "period": "ancient",
            "style": "Ancient Greek/Roman setting, marble textures, classical architecture hints",
            "clothing": "period-accurate ancient robes, toga, or classical attire",
            "atmosphere": "historical, classical, timeless"
        },
        "中世": {
            "period": "medieval",
            "style": "Medieval atmosphere, castle/stone backgrounds, period lighting",
            "clothing": "medieval armor, noble clothing, or peasant attire",
            "atmosphere": "dark ages, feudal, atmospheric"
        },
        "ルネサンス": {
            "period": "renaissance",
            "style": "Renaissance painting quality, rich fabrics, artistic lighting",
            "clothing": "renaissance noble attire, rich fabrics, period-accurate",
            "atmosphere": "artistic, cultured, enlightened"
        },
        "近世": {
            "period": "early_modern",
            "style": "17th-18th century setting, baroque/rococo elements",
            "clothing": "period-accurate historical clothing, wigs if appropriate",
            "atmosphere": "age of enlightenment, refined, scholarly"
        },
        "産業革命期": {
            "period": "industrial",
            "style": "19th century photography style, sepia undertones, Victorian era",
            "clothing": "Victorian-era clothing, industrial age attire",
            "atmosphere": "industrial, progressive, transformative"
        },
        "近代": {
            "period": "modern",
            "style": "20th century photograph style, historical photo quality",
            "clothing": "early 20th century clothing, period-accurate",
            "atmosphere": "modern era, documentary style"
        },
        "現代": {
            "period": "contemporary",
            "style": "Modern high-resolution photography, current day setting",
            "clothing": "contemporary clothing",
            "atmosphere": "present day, crisp, clear"
        },
        "戦国時代": {
            "period": "sengoku",
            "style": "Japanese Sengoku period (1467-1615), samurai era atmosphere",
            "clothing": "samurai armor or traditional Japanese clothing",
            "atmosphere": "warring states period, dramatic, historical Japan"
        },
        "江戸時代": {
            "period": "edo",
            "style": "Edo period Japan (1603-1868), traditional Japanese setting",
            "clothing": "kimono, hakama, or samurai attire",
            "atmosphere": "peaceful Edo era, traditional Japanese culture"
        },
        "不明": {
            "period": "timeless",
            "style": "Timeless, universal setting with neutral background",
            "clothing": "appropriate period clothing based on historical context",
            "atmosphere": "classic, neutral, universal"
        }
    }

    # 表情・ムード定義
    EMOTION_MOODS = {
        "dramatic": "intense, serious expression, dramatic lighting",
        "mystery": "enigmatic, mysterious gaze, contemplative",
        "heroic": "confident, determined expression, strong presence",
        "tragic": "melancholic, sorrowful expression, emotional depth",
        "wise": "thoughtful, intelligent expression, calm demeanor",
        "revolutionary": "passionate, determined, visionary gaze",
        "neutral": "neutral expression, professional portrait"
    }

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化

        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)

    def generate_dalle_prompt(
        self,
        subject: str,
        era: Optional[str] = None,
        mood: str = "dramatic",
        category: Optional[str] = None
    ) -> str:
        """
        DALL-E用の実写系人物画像プロンプトを生成

        Args:
            subject: 偉人の名前
            era: 時代（例：古代、中世、戦国時代など）
            mood: ムード・表情（dramatic, mystery, heroicなど）
            category: カテゴリ（科学者、武将など）

        Returns:
            DALL-E用プロンプト
        """
        self.logger.info(f"Generating DALL-E prompt for: {subject}")

        # 時代情報を取得
        era_info = self._get_era_info(era)

        # ムード情報を取得
        mood_description = self.EMOTION_MOODS.get(mood, self.EMOTION_MOODS["dramatic"])

        # カテゴリ固有の要素を追加
        category_elements = self._get_category_elements(category)

        # プロンプトを構築
        prompt = f"""Photorealistic portrait of {subject} for YouTube thumbnail.

Style requirements:
- Hyperrealistic or high-quality photograph style
- NOT anime, NOT cartoon, NOT illustration
- Natural human features and expressions
- Cinematic lighting (dramatic but natural)
- Professional photography quality

Subject details:
- Era: {era_info['period']}
- Clothing: {era_info['clothing']}
- Expression: {mood_description}
{category_elements}

Composition:
- Face centered, taking up 40-50% of frame
- Direct gaze or 3/4 profile for maximum impact
- Clear facial features, emotional expression visible
- Strong presence, commanding attention

Technical specifications:
- Sharp focus on face, soft background bokeh
- Natural skin tones and textures
- High-quality DSLR photograph aesthetic
- No artificial effects or heavy filters
- Professional portrait photography

Background:
- Simple, non-distracting
- Slightly out of focus (shallow depth of field)
- Atmospheric, matching the era: {era_info['atmosphere']}
- {era_info['style']}

Lighting:
- Cinematic, dramatic but natural
- Highlights facial features
- Creates depth and dimension
- Appropriate for the historical period

Size: 1792x1024 pixels
Format: Horizontal orientation
Quality: Maximum detail, photorealistic"""

        self.logger.debug(f"Generated prompt length: {len(prompt)} characters")

        return prompt

    def _get_era_info(self, era: Optional[str]) -> Dict[str, str]:
        """
        時代情報を取得

        Args:
            era: 時代名

        Returns:
            時代情報の辞書
        """
        if not era:
            return self.ERA_STYLES["不明"]

        # 部分一致で検索
        for era_key, era_data in self.ERA_STYLES.items():
            if era_key in era or era in era_key:
                self.logger.debug(f"Matched era: {era_key}")
                return era_data

        # マッチしない場合はデフォルト
        self.logger.warning(f"Era '{era}' not found, using default")
        return self.ERA_STYLES["不明"]

    def _get_category_elements(self, category: Optional[str]) -> str:
        """
        カテゴリ固有の要素を取得

        Args:
            category: カテゴリ名

        Returns:
            カテゴリ固有の説明文
        """
        category_descriptions = {
            "科学者": "- Props: Subtle scientific elements (books, instruments) in background if appropriate",
            "武将・軍人": "- Props: Military elements, armor details, commanding presence",
            "芸術家": "- Props: Artistic atmosphere, creative environment hints",
            "政治家": "- Props: Formal, authoritative setting, dignified presence",
            "発明家": "- Props: Workshop or laboratory hints in background",
            "思想家": "- Props: Scholarly atmosphere, contemplative setting",
            "医師・医学者": "- Props: Medical/scholarly setting, dedicated expression",
            "探検家": "- Props: Adventurous elements, determined expression",
            "作家・詩人": "- Props: Literary atmosphere, thoughtful expression",
            "宗教家": "- Props: Spiritual atmosphere, serene or passionate expression"
        }

        if category and category in category_descriptions:
            return category_descriptions[category]

        return "- Props: Appropriate period elements in background"

    def generate_image_variations(
        self,
        subject: str,
        era: Optional[str] = None,
        num_variations: int = 3
    ) -> list[Dict[str, str]]:
        """
        複数のムードバリエーションを生成

        Args:
            subject: 偉人の名前
            era: 時代
            num_variations: 生成する数

        Returns:
            プロンプトバリエーションのリスト
        """
        moods = ["dramatic", "mystery", "heroic", "wise", "tragic"][:num_variations]

        variations = []
        for mood in moods:
            prompt = self.generate_dalle_prompt(subject, era, mood)
            variations.append({
                "mood": mood,
                "prompt": prompt,
                "description": f"{mood.capitalize()} mood portrait of {subject}"
            })

        self.logger.info(f"Generated {len(variations)} image prompt variations")

        return variations

    def get_era_specific_style(self, era: str) -> str:
        """
        時代別のスタイル説明を取得（互換性のため）

        Args:
            era: 時代名

        Returns:
            スタイル説明
        """
        era_info = self._get_era_info(era)
        return era_info.get("style", "")

    def optimize_for_thumbnail(
        self,
        base_prompt: str,
        emphasis: str = "impact"
    ) -> str:
        """
        サムネイル用に最適化

        Args:
            base_prompt: ベースプロンプト
            emphasis: 強調ポイント（impact, clarity, emotionなど）

        Returns:
            最適化されたプロンプト
        """
        optimization_additions = {
            "impact": "\n\nExtra emphasis: Maximum visual impact, bold presence, eye-catching composition",
            "clarity": "\n\nExtra emphasis: Crystal clear details, perfect focus, professional quality",
            "emotion": "\n\nExtra emphasis: Strong emotional expression, captivating gaze, deep feeling"
        }

        addition = optimization_additions.get(emphasis, "")
        optimized = base_prompt + addition

        return optimized


def create_realistic_image_prompt_generator(
    logger: Optional[logging.Logger] = None
) -> RealisticImagePromptGenerator:
    """
    RealisticImagePromptGeneratorのファクトリー関数

    Args:
        logger: ロガー

    Returns:
        RealisticImagePromptGenerator インスタンス
    """
    return RealisticImagePromptGenerator(logger=logger)
