#!/usr/bin/env python3
"""
汎用偉人サムネイル生成システムのユニットテスト

APIキー不要で各コンポーネントの基本機能をテスト
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.subject_category_optimizer import SubjectCategoryOptimizer
from src.generators.effectiveness_predictor import EffectivenessPredictor
from src.generators.realistic_image_prompt_generator import RealisticImagePromptGenerator


# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_category_optimizer():
    """SubjectCategoryOptimizerのテスト"""
    print("\n" + "=" * 80)
    print("🧪 Testing SubjectCategoryOptimizer")
    print("=" * 80)

    optimizer = SubjectCategoryOptimizer(logger=logger)

    # テストケース
    test_cases = [
        ("織田信長", {"achievement": "戦国時代の統一", "category": "武将・軍人"}),
        ("アインシュタイン", {"achievement": "相対性理論", "category": "科学者"}),
        ("ゴッホ", {"achievement": "印象派絵画", "category": "芸術家"}),
        ("ソクラテス", {"achievement": "哲学の祖", "category": "思想家"}),
    ]

    for subject, analysis in test_cases:
        category = optimizer.detect_category(subject, analysis)
        category_info = optimizer.get_category_info(category)

        print(f"\n📌 {subject}")
        print(f"   Detected Category: {category}")
        print(f"   Keywords: {', '.join(category_info['keywords'][:3])}")
        print(f"   Approach: {category_info['approach']}")
        print(f"   Emotion: {category_info['emotion']}")

    print("\n✅ SubjectCategoryOptimizer test passed!")


def test_effectiveness_predictor():
    """EffectivenessPredictorのテスト"""
    print("\n" + "=" * 80)
    print("🧪 Testing EffectivenessPredictor")
    print("=" * 80)

    predictor = EffectivenessPredictor(logger=logger)

    # テストテキストペア
    test_pairs = [
        {
            "main": "なぜ殺された？",
            "sub": "天下統一を目指した男の悲劇的な最期",
            "name": "疑問形 + ドラマ"
        },
        {
            "main": "99%知らない",
            "sub": "科学者が発見した驚くべき真実",
            "name": "数字 + 意外性"
        },
        {
            "main": "天才か狂人か",
            "sub": "革命的な作品に隠された苦悩",
            "name": "対比 + 謎"
        },
        {
            "main": "信じられない",
            "sub": "世界を変えた一つの決断",
            "name": "衝撃 + インパクト"
        },
    ]

    for pair in test_pairs:
        score = predictor.predict_impact_score(pair, detailed=True)
        suggestions = predictor.get_improvement_suggestions(pair)

        print(f"\n📝 {pair['name']}")
        print(f"   Main: {pair['main']}")
        print(f"   Sub:  {pair['sub']}")
        print(f"   Score: {score:.2f}/10")

        if suggestions:
            print(f"   Suggestions: {', '.join(suggestions[:2])}")

    print("\n✅ EffectivenessPredictor test passed!")


def test_image_prompt_generator():
    """RealisticImagePromptGeneratorのテスト"""
    print("\n" + "=" * 80)
    print("🧪 Testing RealisticImagePromptGenerator")
    print("=" * 80)

    generator = RealisticImagePromptGenerator(logger=logger)

    # テストケース
    test_cases = [
        ("織田信長", "戦国時代", "heroic", "武将・軍人"),
        ("アインシュタイン", "近代", "wise", "科学者"),
        ("ゴッホ", "近代", "tragic", "芸術家"),
    ]

    for subject, era, mood, category in test_cases:
        prompt = generator.generate_dalle_prompt(subject, era, mood, category)

        print(f"\n🎨 {subject} ({era}, {mood})")
        print(f"   Category: {category}")
        print(f"   Prompt Preview (first 200 chars):")
        print(f"   {prompt[:200]}...")

    # 時代スタイルテスト
    print("\n📅 Era Styles Test:")
    test_eras = ["古代", "中世", "戦国時代", "産業革命期"]
    for era in test_eras:
        style = generator.get_era_specific_style(era)
        print(f"   {era}: {style[:50]}...")

    print("\n✅ RealisticImagePromptGenerator test passed!")


def test_integration():
    """統合テスト"""
    print("\n" + "=" * 80)
    print("🧪 Integration Test")
    print("=" * 80)

    optimizer = SubjectCategoryOptimizer(logger=logger)
    predictor = EffectivenessPredictor(logger=logger)
    image_gen = RealisticImagePromptGenerator(logger=logger)

    subject = "織田信長"
    analysis = {
        "era": "戦国時代",
        "achievement": "天下統一への道を開いた",
        "category": "武将・軍人",
        "unexpected_aspect": "茶道を愛した文化人",
        "dramatic_element": "本能寺の変での最期"
    }

    # カテゴリ検出
    category = optimizer.detect_category(subject, analysis)
    print(f"\n✓ Category detected: {category}")

    # テキストバリエーション（手動作成）
    text_variations = [
        {"main": "なぜ殺された？", "sub": "天下統一を目指した男の悲劇的な最期"},
        {"main": "99%知らない", "sub": "戦国最強の武将が持っていた意外な一面"},
        {"main": "天才か暴君か", "sub": "革命を起こした男の知られざる真実"},
    ]

    # 効果予測
    for var in text_variations:
        score = predictor.predict_impact_score(var)
        var["effectiveness_score"] = score

    print(f"✓ Effectiveness scores calculated")

    # カテゴリ最適化
    optimized = optimizer.optimize_for_category(subject, text_variations, category)
    print(f"✓ Optimized for category: {category}")

    # トップ選択を表示
    print(f"\n🏆 Top Selection:")
    top = optimized[0]
    print(f"   Main: {top['main']}")
    print(f"   Sub:  {top['sub']}")
    print(f"   Total Score: {top.get('total_score', 0):.2f}/10")

    # 画像プロンプト生成
    era = analysis.get("era", "不明")
    category_info = optimizer.get_category_info(category)
    mood = category_info.get("emotion", "dramatic")

    image_prompt = image_gen.generate_dalle_prompt(subject, era, mood, category)
    print(f"\n📷 Image Prompt Generated ({len(image_prompt)} chars)")

    print("\n✅ Integration test passed!")


def main():
    """メイン関数"""
    print("\n" + "=" * 80)
    print("🎨 汎用偉人サムネイル生成システム - ユニットテスト")
    print("=" * 80)

    try:
        # 各コンポーネントをテスト
        test_category_optimizer()
        test_effectiveness_predictor()
        test_image_prompt_generator()
        test_integration()

        print("\n" + "=" * 80)
        print("✅ All tests passed successfully!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
