#!/usr/bin/env python3
"""
CLI entrypoint for video automation system

Usage:
    python -m src.cli run-phase <subject> --phase <phase_number>

Examples:
    python -m src.cli run-phase "織田信長" --phase 1
    python -m src.cli run-phase "織田信長" --phase 2
    python -m src.cli run-phase "織田信長" --phase 6
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config_manager import ConfigManager
from src.utils.logger import setup_logger
from src.core.models import PhaseStatus

# 全フェーズをインポート
from src.phases.phase_01_script import Phase01Script
from src.phases.phase_02_audio import Phase02Audio
from src.phases.phase_03_images import Phase03Images
from src.phases.phase_04_animation import Phase04Animation
from src.phases.phase_05_bgm import Phase05BGM
from src.phases.phase_06_subtitles import Phase06Subtitles
from src.phases.phase_07_composition import Phase07Composition


def run_phase(subject: str, phase_number: int, skip_if_exists: bool = False) -> int:
    """
    指定されたフェーズを実行

    Args:
        subject: 偉人名
        phase_number: フェーズ番号 (1-7)
        skip_if_exists: 既に出力が存在する場合はスキップ

    Returns:
        終了コード (0: 成功, 1: 失敗)
    """
    # 設定を読み込み
    config = ConfigManager()

    # ロガーを設定
    logger = setup_logger(
        name=f"cli_phase{phase_number}_{subject}",
        log_dir=config.get_path("logs_dir"),
        level="INFO"
    )

    # フェーズクラスのマッピング
    phase_classes = {
        1: Phase01Script,
        2: Phase02Audio,
        3: Phase03Images,
        4: Phase04Animation,
        5: Phase05BGM,
        6: Phase06Subtitles,
        7: Phase07Composition,
    }

    if phase_number not in phase_classes:
        logger.error(f"Invalid phase number: {phase_number}. Must be 1-7.")
        return 1

    # フェーズを実行
    try:
        logger.info("="*60)
        logger.info(f"Running Phase {phase_number} for: {subject}")
        logger.info("="*60)

        # フェーズインスタンスを作成
        phase_class = phase_classes[phase_number]
        phase = phase_class(
            subject=subject,
            config=config,
            logger=logger
        )

        # 実行
        execution = phase.run(skip_if_exists=skip_if_exists)

        # 結果を表示
        logger.info("")
        logger.info("="*60)
        logger.info("Execution Result")
        logger.info("="*60)
        logger.info(f"Status: {execution.status.value}")
        logger.info(f"Duration: {execution.duration_seconds:.2f}s")

        if execution.status == PhaseStatus.COMPLETED:
            logger.info("")
            logger.info("Output files:")
            for path in execution.output_paths:
                logger.info(f"  ✓ {path}")

            # Phase 2の場合、audio_timing.jsonの生成を確認
            if phase_number == 2:
                audio_timing_path = phase.phase_dir / "audio_timing.json"
                if audio_timing_path.exists():
                    logger.info("")
                    logger.info(f"✓ audio_timing.json generated: {audio_timing_path}")
                else:
                    logger.warning("⚠ audio_timing.json was not generated")

            # Phase 6の場合、字幕ファイルの生成を確認
            if phase_number == 6:
                subtitles_path = phase.phase_dir / "subtitles.srt"
                if subtitles_path.exists():
                    logger.info("")
                    logger.info(f"✓ subtitles.srt generated: {subtitles_path}")

            return 0
        elif execution.status == PhaseStatus.SKIPPED:
            logger.info("Phase was skipped (outputs already exist)")
            return 0
        else:
            logger.error(f"Error: {execution.error_message}")
            return 1

    except Exception as e:
        logger.error(f"Execution error: {e}", exc_info=True)
        return 1


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="Video automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate script (Phase 1)
  python -m src.cli run-phase "織田信長" --phase 1

  # Generate audio with timestamps (Phase 2)
  python -m src.cli run-phase "織田信長" --phase 2

  # Generate images (Phase 3)
  python -m src.cli run-phase "織田信長" --phase 3

  # Generate animations (Phase 4)
  python -m src.cli run-phase "織田信長" --phase 4

  # Select BGM (Phase 5)
  python -m src.cli run-phase "織田信長" --phase 5

  # Generate subtitles (Phase 6)
  python -m src.cli run-phase "織田信長" --phase 6

  # Compose final video (Phase 7)
  python -m src.cli run-phase "織田信長" --phase 7

  # Skip if outputs exist
  python -m src.cli run-phase "織田信長" --phase 2 --skip-if-exists
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # run-phase コマンド
    run_parser = subparsers.add_parser(
        "run-phase",
        help="Run a specific phase"
    )
    run_parser.add_argument(
        "subject",
        type=str,
        help="Subject name (e.g., '織田信長')"
    )
    run_parser.add_argument(
        "--phase",
        type=int,
        required=True,
        choices=[1, 2, 3, 4, 5, 6, 7],
        help="Phase number (1-7)"
    )
    run_parser.add_argument(
        "--skip-if-exists",
        action="store_true",
        help="Skip if outputs already exist"
    )

    # 引数をパース
    args = parser.parse_args()

    # コマンドが指定されていない場合
    if not args.command:
        parser.print_help()
        return 1

    # run-phase コマンド
    if args.command == "run-phase":
        return run_phase(
            subject=args.subject,
            phase_number=args.phase,
            skip_if_exists=args.skip_if_exists
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
