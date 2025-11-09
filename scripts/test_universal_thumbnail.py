#!/usr/bin/env python3
"""
汎用偉人サムネイル生成システムのテストスクリプト

様々な偉人でシステムをテストし、生成結果を確認
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.universal_thumbnail_generator import UniversalThumbnailGenerator


# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# テスト偉人リスト（要件書から）
TEST_SUBJECTS = [
    # 科学者
    "アインシュタイン",
    "マリー・キュリー",
    "ニュートン",

    # 武将・軍人
    "織田信長",
    "ナポレオン",
    "アレクサンダー大王",

    # 芸術家
    "ゴッホ",
    "ベートーヴェン",
    "レオナルド・ダ・ヴィンチ",

    # 発明家
    "エジソン",
    "テスラ",

    # 政治家
    "リンカーン",
    "チャーチル",

    # 思想家
    "ソクラテス",
    "孔子"
]


def test_single_subject(generator: UniversalThumbnailGenerator, subject: str):
    """
    単一の偉人でテスト

    Args:
        generator: UniversalThumbnailGenerator インスタンス
        subject: 偉人の名前
    """
    print("\n" + "=" * 80)
    print(f"🎯 Testing: {subject}")
    print("=" * 80)

    try:
        # 完全パッケージ生成
        result = generator.generate_complete_package(subject, top_n=5)

        # 結果を表示
        generator.print_top_selections(result, detailed=False)

        # 画像プロンプトを表示
        print("\n📷 Image Generation Prompt (first 500 chars):")
        print("-" * 80)
        image_prompt = result['image_prompt']
        print(image_prompt[:500] + "..." if len(image_prompt) > 500 else image_prompt)
        print("-" * 80)

        return result

    except Exception as e:
        logger.error(f"❌ Failed to test {subject}: {e}", exc_info=True)
        return None


def test_batch(generator: UniversalThumbnailGenerator, subjects: list, output_dir: str = None):
    """
    一括テスト

    Args:
        generator: UniversalThumbnailGenerator インスタンス
        subjects: 偉人リスト
        output_dir: 出力ディレクトリ
    """
    print("\n" + "=" * 80)
    print(f"🚀 Batch Test: {len(subjects)} subjects")
    print("=" * 80)

    results = generator.batch_generate(subjects, output_dir)

    # サマリーを表示
    print("\n" + "=" * 80)
    print("📊 Batch Test Summary")
    print("=" * 80)

    success_count = 0
    error_count = 0

    for subject, result in results.items():
        if "error" in result:
            print(f"❌ {subject}: FAILED - {result['error']}")
            error_count += 1
        else:
            category = result.get('category', 'Unknown')
            top_score = result['text_variations']['top_selections'][0].get('total_score', 0)
            print(f"✅ {subject}: SUCCESS - Category: {category}, Top Score: {top_score:.2f}")
            success_count += 1

    print("\n" + "-" * 80)
    print(f"Total: {len(subjects)} | Success: {success_count} | Failed: {error_count}")
    print("=" * 80)

    return results


def test_text_only(generator: UniversalThumbnailGenerator, subject: str):
    """
    テキストのみ生成テスト

    Args:
        generator: UniversalThumbnailGenerator インスタンス
        subject: 偉人の名前
    """
    print(f"\n🔤 Text-Only Test: {subject}")

    variations = generator.generate_text_only(subject, top_n=3)

    for i, var in enumerate(variations, 1):
        print(f"\n{i}. Main: {var.get('main')} | Sub: {var.get('sub')}")
        print(f"   Score: {var.get('total_score', 0):.2f}, Type: {var.get('impact_type')}")


def test_image_only(generator: UniversalThumbnailGenerator, subject: str):
    """
    画像プロンプトのみ生成テスト

    Args:
        generator: UniversalThumbnailGenerator インスタンス
        subject: 偉人の名前
    """
    print(f"\n📷 Image-Only Test: {subject}")

    prompt = generator.generate_image_prompt_only(subject, era="戦国時代", mood="heroic")

    print(f"\nGenerated prompt:\n{prompt[:300]}...")


def main():
    """メイン関数"""
    print("\n" + "=" * 80)
    print("🎨 汎用偉人サムネイル生成システム - テストスクリプト")
    print("=" * 80)

    # ジェネレーターを初期化
    generator = UniversalThumbnailGenerator(
        model="gpt-4o-mini",
        logger=logger
    )

    # テストモードを選択
    import sys
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "single"

    if mode == "single":
        # 単一テスト（織田信長）
        test_single_subject(generator, "織田信長")

    elif mode == "text":
        # テキストのみテスト
        test_text_only(generator, "ナポレオン")

    elif mode == "image":
        # 画像のみテスト
        test_image_only(generator, "織田信長")

    elif mode == "batch":
        # 一括テスト
        output_dir = project_root / "output" / "universal_thumbnails"
        test_batch(generator, TEST_SUBJECTS[:5], str(output_dir))  # 最初の5人

    elif mode == "full_batch":
        # 全偉人一括テスト
        output_dir = project_root / "output" / "universal_thumbnails"
        test_batch(generator, TEST_SUBJECTS, str(output_dir))

    else:
        print(f"Unknown mode: {mode}")
        print("\nUsage:")
        print("  python test_universal_thumbnail.py [mode]")
        print("\nModes:")
        print("  single      - Test single subject (織田信長)")
        print("  text        - Test text-only generation")
        print("  image       - Test image-only generation")
        print("  batch       - Test batch generation (first 5)")
        print("  full_batch  - Test all subjects")
        print("\nDefault: single")

    print("\n✅ Test completed!")


if __name__ == "__main__":
    main()
