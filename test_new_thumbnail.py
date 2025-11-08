"""
新しいサムネイル生成パイプラインのテスト

gpt-image-1 + Pillow + Claude
"""
import sys
from pathlib import Path
import logging

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.generators.catchcopy_generator import CatchcopyGenerator
from src.generators.gptimage_thumbnail_generator import GPTImageThumbnailGenerator

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_catchcopy_generation():
    """キャッチコピー生成のテスト"""
    logger.info("=" * 60)
    logger.info("テスト1: キャッチコピー生成")
    logger.info("=" * 60)
    
    # テスト用の台本データ
    script_data = {
        "subject": "イグナーツ・ゼンメルワイス",
        "sections": [
            {
                "title": "手洗いの発見",
                "content": "19世紀、ウィーンの産科病棟で多くの女性が産褥熱で亡くなっていた。ゼンメルワイスは手洗いが命を救うことを発見した。"
            },
            {
                "title": "医学界の反発",
                "content": "ゼンメルワイスの発見は医学界から激しく批判された。彼の理論は受け入れられず、最終的には精神病院で亡くなった。"
            }
        ]
    }
    
    # キャッチコピージェネレーターを作成
    generator = CatchcopyGenerator(logger=logger)
    
    # キャッチコピーを生成
    candidates = generator.generate_catchcopy(
        subject="イグナーツ・ゼンメルワイス",
        script_data=script_data,
        tone="dramatic",
        target_audience="一般",
        main_length=20,
        sub_length=10,
        num_candidates=5
    )
    
    # 結果を表示
    logger.info(f"\n生成された候補数: {len(candidates)}\n")
    for i, candidate in enumerate(candidates, 1):
        logger.info(f"候補 {i}:")
        logger.info(f"  メインタイトル: {candidate.get('main_title')}")
        logger.info(f"  サブタイトル: {candidate.get('sub_title')}")
        logger.info(f"  理由: {candidate.get('reasoning')}\n")
    
    return candidates[0] if candidates else None


def test_gptimage_generation(title: str, subtitle: str):
    """gpt-image-1 + Pillowサムネイル生成のテスト"""
    logger.info("=" * 60)
    logger.info("テスト2: gpt-image-1 + Pillow サムネイル生成")
    logger.info("=" * 60)
    
    # GPTImageThumbnailGeneratorを作成
    generator = GPTImageThumbnailGenerator(
        width=1280,
        height=720,
        logger=logger
    )
    
    # サムネイルを生成
    output_path = "/home/ubuntu/test_gptimage_thumbnail.png"
    
    logger.info(f"タイトル: {title}")
    logger.info(f"サブタイトル: {subtitle}")
    logger.info("背景画像を生成中... (約2分かかります)")
    
    thumbnail_path = generator.generate_thumbnail(
        title=title,
        subject="イグナーツ・ゼンメルワイス",
        subtitle=subtitle,
        style="dramatic",
        quality="medium",
        layout="center",
        output_path=output_path
    )
    
    if thumbnail_path:
        logger.info(f"✅ サムネイル生成成功: {thumbnail_path}")
    else:
        logger.error("❌ サムネイル生成失敗")
    
    return thumbnail_path


def main():
    """メインテスト"""
    logger.info("🚀 新しいサムネイル生成パイプラインのテスト開始\n")
    
    try:
        # テスト1: キャッチコピー生成
        selected = test_catchcopy_generation()
        
        if not selected:
            logger.error("キャッチコピー生成に失敗しました")
            return
        
        # テスト2: gpt-image-1 + Pillow サムネイル生成
        title = selected.get("main_title", "イグナーツ・ゼンメルワイス")
        subtitle = selected.get("sub_title")
        
        thumbnail_path = test_gptimage_generation(title, subtitle)
        
        if thumbnail_path:
            logger.info("\n" + "=" * 60)
            logger.info("✅ すべてのテストが完了しました")
            logger.info("=" * 60)
            logger.info(f"生成されたサムネイル: {thumbnail_path}")
        else:
            logger.error("\n❌ サムネイル生成に失敗しました")
    
    except Exception as e:
        logger.error(f"テスト中にエラーが発生: {e}", exc_info=True)


if __name__ == "__main__":
    main()
