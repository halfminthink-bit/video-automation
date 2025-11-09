"""
汎用偉人サムネイル生成システム

UniversalImpactTextGenerator、SubjectCategoryOptimizer、
EffectivenessPredictor、RealisticImagePromptGeneratorを統合し、
完全自動でサムネイルテキストと画像プロンプトを生成
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

from .universal_impact_text_generator import UniversalImpactTextGenerator
from .subject_category_optimizer import SubjectCategoryOptimizer
from .effectiveness_predictor import EffectivenessPredictor
from .realistic_image_prompt_generator import RealisticImagePromptGenerator


class UniversalThumbnailGenerator:
    """汎用偉人サムネイル生成システム"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            model: テキスト生成に使用するモデル
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)

        # コンポーネントを初期化
        self.text_generator = UniversalImpactTextGenerator(
            model=model,
            logger=self.logger
        )
        self.category_optimizer = SubjectCategoryOptimizer(logger=self.logger)
        self.predictor = EffectivenessPredictor(logger=self.logger)
        self.image_generator = RealisticImagePromptGenerator(logger=self.logger)

        self.logger.info("UniversalThumbnailGenerator initialized")

    def generate_complete_package(
        self,
        subject: str,
        context: Optional[str] = None,
        top_n: int = 5
    ) -> Dict[str, Any]:
        """
        完全自動サムネイルパッケージ生成

        Args:
            subject: 偉人の名前
            context: 追加コンテキスト（台本など）
            top_n: 選択する上位N個のテキスト

        Returns:
            生成結果の辞書
        """
        self.logger.info(f"=== Starting complete package generation for: {subject} ===")

        # 1. 偉人分析
        self.logger.info("Step 1: Analyzing subject...")
        analysis = self.text_generator.analyze_subject(subject, context)

        # 2. カテゴリ検出
        self.logger.info("Step 2: Detecting category...")
        category = self.category_optimizer.detect_category(subject, analysis)

        # 3. テキスト生成（複数パターン）
        self.logger.info("Step 3: Generating text variations...")
        text_variations = self.text_generator.generate_text_variations(
            subject,
            analysis
        )

        # 4. 効果予測を追加
        self.logger.info("Step 4: Predicting effectiveness...")
        for variation in text_variations:
            if "effectiveness_score" not in variation:
                score = self.predictor.predict_impact_score(variation, detailed=True)
                variation["effectiveness_score"] = score

        # 5. カテゴリ最適化
        self.logger.info("Step 5: Optimizing for category...")
        optimized_texts = self.category_optimizer.optimize_for_category(
            subject,
            text_variations,
            category
        )

        # 6. 上位N個を選択
        top_texts = optimized_texts[:top_n]

        # 7. 画像プロンプト生成
        self.logger.info("Step 6: Generating image prompts...")
        era = analysis.get("era", "不明")
        category_info = self.category_optimizer.get_category_info(category)
        recommended_mood = category_info.get("emotion", "dramatic")

        image_prompt = self.image_generator.generate_dalle_prompt(
            subject,
            era=era,
            mood=recommended_mood,
            category=category
        )

        # 結果をパッケージ化
        result = {
            "subject": subject,
            "analysis": analysis,
            "category": category,
            "category_info": category_info,
            "text_variations": {
                "top_selections": top_texts,
                "all_variations": optimized_texts
            },
            "image_prompt": image_prompt,
            "metadata": {
                "era": era,
                "recommended_mood": recommended_mood,
                "total_variations_generated": len(text_variations),
                "selected_count": len(top_texts)
            }
        }

        self.logger.info(f"✅ Complete package generated successfully!")
        self.logger.info(f"   - Category: {category}")
        self.logger.info(f"   - Era: {era}")
        self.logger.info(f"   - Top selections: {len(top_texts)}")

        return result

    def generate_text_only(
        self,
        subject: str,
        context: Optional[str] = None,
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        テキストのみを生成（画像プロンプトなし）

        Args:
            subject: 偉人の名前
            context: 追加コンテキスト
            top_n: 選択する上位N個

        Returns:
            テキストバリエーションのリスト
        """
        self.logger.info(f"Generating text only for: {subject}")

        # 分析
        analysis = self.text_generator.analyze_subject(subject, context)

        # テキスト生成
        variations = self.text_generator.generate_text_variations(subject, analysis)

        # 効果予測
        for variation in variations:
            if "effectiveness_score" not in variation:
                score = self.predictor.predict_impact_score(variation)
                variation["effectiveness_score"] = score

        # カテゴリ最適化
        category = self.category_optimizer.detect_category(subject, analysis)
        optimized = self.category_optimizer.optimize_for_category(
            subject,
            variations,
            category
        )

        return optimized[:top_n]

    def generate_image_prompt_only(
        self,
        subject: str,
        era: Optional[str] = None,
        category: Optional[str] = None,
        mood: str = "dramatic"
    ) -> str:
        """
        画像プロンプトのみを生成

        Args:
            subject: 偉人の名前
            era: 時代
            category: カテゴリ
            mood: ムード

        Returns:
            画像生成プロンプト
        """
        self.logger.info(f"Generating image prompt for: {subject}")

        prompt = self.image_generator.generate_dalle_prompt(
            subject,
            era=era,
            mood=mood,
            category=category
        )

        return prompt

    def save_results_to_json(
        self,
        result: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        結果をJSONファイルに保存

        Args:
            result: 生成結果
            output_path: 出力パス
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Results saved to: {output_path}")

    def print_top_selections(
        self,
        result: Dict[str, Any],
        detailed: bool = False
    ) -> None:
        """
        上位選択結果を表示

        Args:
            result: 生成結果
            detailed: 詳細表示するか
        """
        print("\n" + "=" * 60)
        print(f"📊 Top Thumbnail Text Selections for: {result['subject']}")
        print("=" * 60)
        print(f"Category: {result['category']}")
        print(f"Era: {result['metadata']['era']}")
        print(f"Recommended Mood: {result['metadata']['recommended_mood']}")
        print("=" * 60)

        top_selections = result['text_variations']['top_selections']

        for i, selection in enumerate(top_selections, 1):
            print(f"\n🏆 Rank {i}")
            print(f"   Main Text: {selection.get('main', 'N/A')}")
            print(f"   Sub Text:  {selection.get('sub', 'N/A')}")
            print(f"   Score: {selection.get('total_score', selection.get('effectiveness_score', 0)):.2f}/10")
            print(f"   Type: {selection.get('impact_type', 'N/A')}")

            if detailed:
                print(f"   Approach: {selection.get('approach', 'N/A')}")
                print(f"   Category Match: {selection.get('keyword_match_score', 0):.2f}")
                if 'reasoning' in selection:
                    print(f"   Reasoning: {selection['reasoning']}")

        print("\n" + "=" * 60)

    def batch_generate(
        self,
        subjects: List[str],
        output_dir: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        複数の偉人を一括生成

        Args:
            subjects: 偉人リスト
            output_dir: 出力ディレクトリ（Noneの場合は保存しない）

        Returns:
            偉人名をキーとした結果の辞書
        """
        self.logger.info(f"Starting batch generation for {len(subjects)} subjects")

        results = {}

        for i, subject in enumerate(subjects, 1):
            self.logger.info(f"Processing {i}/{len(subjects)}: {subject}")

            try:
                result = self.generate_complete_package(subject)
                results[subject] = result

                # 出力ディレクトリが指定されている場合は保存
                if output_dir:
                    output_path = Path(output_dir) / f"{subject}_thumbnail_package.json"
                    self.save_results_to_json(result, str(output_path))

            except Exception as e:
                self.logger.error(f"Failed to generate for {subject}: {e}", exc_info=True)
                results[subject] = {"error": str(e)}

        self.logger.info(f"✅ Batch generation completed: {len(results)} results")

        return results


def create_universal_thumbnail_generator(
    model: str = "gpt-4o-mini",
    logger: Optional[logging.Logger] = None
) -> UniversalThumbnailGenerator:
    """
    UniversalThumbnailGeneratorのファクトリー関数

    Args:
        model: 使用するモデル
        logger: ロガー

    Returns:
        UniversalThumbnailGenerator インスタンス
    """
    return UniversalThumbnailGenerator(model=model, logger=logger)
