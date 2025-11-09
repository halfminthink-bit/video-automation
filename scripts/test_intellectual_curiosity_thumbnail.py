#!/usr/bin/env python3
"""
知的好奇心サムネイル自動生成システムのテスト

使用例:
    python scripts/test_intellectual_curiosity_thumbnail.py --subject "イグナーツ・ゼンメルワイス"
    python scripts/test_intellectual_curiosity_thumbnail.py --subject "織田信長"
    python scripts/test_intellectual_curiosity_thumbnail.py --run-examples
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.intellectual_curiosity_generator import create_intellectual_curiosity_generator
import yaml
from dotenv import load_dotenv

# 環境変数を読み込み（プロジェクトの優先順位で）
env_files = [
    project_root / ".env",
    project_root / "config" / ".env",
]

loaded_env = False
for env_path in env_files:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        loaded_env = True

if not loaded_env:
    load_dotenv(override=True)


def setup_logger(debug: bool = False) -> logging.Logger:
    """ロガーをセットアップ"""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def load_config() -> dict:
    """設定ファイルを読み込み"""
    config_path = project_root / "config" / "intellectual_curiosity_thumbnail.yaml"

    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    else:
        # デフォルト設定
        return {
            "output": {"resolution": [1280, 720]},
            "text_generation": {"model": "gpt-4o-mini"},
            "dalle": {"size": "1792x1024", "quality": "standard"},
            "background": {
                "darkness": 0.7,
                "vignette": 0.6,
                "edge_shadow": True
            },
            "image_style": {
                "type": "dramatic",
                "mood": "mysterious"
            }
        }


def test_single_subject(
    subject: str,
    output_dir: Path,
    logger: logging.Logger,
    num_variations: int = 5
):
    """単一主題のテスト"""
    logger.info("=" * 60)
    logger.info(f"🧪 Testing intellectual curiosity thumbnail for: {subject}")
    logger.info("=" * 60)

    # 設定を読み込み
    config = load_config()

    # ジェネレーターを作成
    generator = create_intellectual_curiosity_generator(config=config, logger=logger)

    # 出力ディレクトリを作成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_output_dir = output_dir / f"test_{subject}_{timestamp}"
    test_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Output directory: {test_output_dir}")

    # サムネイルを生成
    thumbnail_paths = generator.generate_thumbnails(
        subject=subject,
        output_dir=test_output_dir,
        num_variations=num_variations
    )

    # 結果を表示
    logger.info("=" * 60)
    logger.info("✅ Test completed!")
    logger.info(f"Generated {len(thumbnail_paths)} thumbnails:")
    for i, path in enumerate(thumbnail_paths, 1):
        logger.info(f"  {i}. {path.name}")
    logger.info(f"Output directory: {test_output_dir}")
    logger.info("=" * 60)


def run_example_tests(output_dir: Path, logger: logging.Logger):
    """設定ファイルのexamplesを実行"""
    logger.info("=" * 60)
    logger.info("🧪 Running example tests from config")
    logger.info("=" * 60)

    config = load_config()
    examples = config.get("examples", [])

    if not examples:
        logger.warning("No examples found in config")
        return

    for i, example in enumerate(examples, 1):
        subject = example.get("subject")

        logger.info(f"\nExample {i}: {subject}")

        test_single_subject(
            subject=subject,
            output_dir=output_dir,
            logger=logger,
            num_variations=3  # 例は3パターンで
        )


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="知的好奇心サムネイル自動生成システムのテスト"
    )
    parser.add_argument(
        "--subject",
        type=str,
        help="対象人物・テーマ（例: 'イグナーツ・ゼンメルワイス'）"
    )
    parser.add_argument(
        "--num-variations",
        type=int,
        default=5,
        help="生成するバリエーション数（デフォルト: 5）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="test_output/intellectual_curiosity",
        help="出力ディレクトリ"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモード"
    )
    parser.add_argument(
        "--run-examples",
        action="store_true",
        help="設定ファイルのexamplesを実行"
    )

    args = parser.parse_args()

    # ロガーをセットアップ
    logger = setup_logger(debug=args.debug)

    # 出力ディレクトリを作成
    output_dir = project_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.run_examples:
            # 例を実行
            run_example_tests(output_dir, logger)

        elif args.subject:
            # 指定された主題でテスト
            test_single_subject(
                subject=args.subject,
                output_dir=output_dir,
                logger=logger,
                num_variations=args.num_variations
            )

        else:
            # デフォルト: イグナーツ・ゼンメルワイスでテスト
            logger.info("No subject specified, using default: イグナーツ・ゼンメルワイス")
            test_single_subject(
                subject="イグナーツ・ゼンメルワイス",
                output_dir=output_dir,
                logger=logger,
                num_variations=args.num_variations
            )

    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
