#!/usr/bin/env python3
"""
「教科書には載せてくれない」シリーズサムネイル生成テスト

使用例:
    python scripts/test_textbook_series_thumbnail.py --subject "織田信長"
    python scripts/test_textbook_series_thumbnail.py --subjects "織田信長" "豊臣秀吉" "徳川家康"
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.textbook_series_generator import create_textbook_series_generator
import yaml
from dotenv import load_dotenv

# 環境変数を読み込み
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
    config_path = project_root / "config" / "textbook_series_thumbnail.yaml"

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
                "type": "historical",
                "mood": "mysterious"
            }
        }


def test_single_subject(
    subject: str,
    output_dir: Path,
    logger: logging.Logger,
    num_variations: int = 5
):
    """単一人物のテスト"""
    logger.info("=" * 60)
    logger.info(f"🧪 Testing single subject: {subject}")
    logger.info("=" * 60)

    # 設定を読み込み
    config = load_config()

    # ジェネレーターを作成
    generator = create_textbook_series_generator(config=config, logger=logger)

    # 出力ディレクトリを作成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_output_dir = output_dir / f"test_{subject}_{timestamp}"
    test_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Output directory: {test_output_dir}")

    # サムネイルを生成
    thumbnail_paths = generator.generate_thumbnails(
        subjects=subject,
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


def test_multiple_subjects(
    subjects: list,
    output_dir: Path,
    logger: logging.Logger,
    num_variations: int = 5
):
    """複数人物のテスト"""
    subjects_str = "、".join(subjects)
    logger.info("=" * 60)
    logger.info(f"🧪 Testing multiple subjects: {subjects_str}")
    logger.info("=" * 60)

    # 設定を読み込み
    config = load_config()

    # ジェネレーターを作成
    generator = create_textbook_series_generator(config=config, logger=logger)

    # 出力ディレクトリを作成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "_".join(subjects[:2])  # 最初の2人の名前を使用
    test_output_dir = output_dir / f"test_{safe_name}_{timestamp}"
    test_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Output directory: {test_output_dir}")

    # サムネイルを生成
    thumbnail_paths = generator.generate_thumbnails(
        subjects=subjects,
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
        subjects = example.get("subjects")
        bottom_text = example.get("bottom_text", "")

        logger.info(f"\nExample {i}: {subjects} - '{bottom_text}'")

        if isinstance(subjects, list):
            test_multiple_subjects(
                subjects=subjects,
                output_dir=output_dir,
                logger=logger,
                num_variations=3  # 例は3パターンで
            )
        else:
            test_single_subject(
                subject=subjects,
                output_dir=output_dir,
                logger=logger,
                num_variations=3
            )


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="「教科書には載せてくれない」シリーズサムネイル生成テスト"
    )
    parser.add_argument(
        "--subject",
        type=str,
        help="単一人物（例: '織田信長'）"
    )
    parser.add_argument(
        "--subjects",
        type=str,
        nargs="+",
        help="複数人物（例: '織田信長' '豊臣秀吉' '徳川家康'）"
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
        default="test_output/textbook_series",
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

        elif args.subjects:
            # 複数人物のテスト
            test_multiple_subjects(
                subjects=args.subjects,
                output_dir=output_dir,
                logger=logger,
                num_variations=args.num_variations
            )

        elif args.subject:
            # 単一人物のテスト
            test_single_subject(
                subject=args.subject,
                output_dir=output_dir,
                logger=logger,
                num_variations=args.num_variations
            )

        else:
            # デフォルト: 織田信長でテスト
            logger.info("No subject specified, using default: 織田信長")
            test_single_subject(
                subject="織田信長",
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
