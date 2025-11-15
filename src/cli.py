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
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config_manager import ConfigManager
from src.utils.logger import setup_logger
from src.core.models import PhaseStatus
from src.core.orchestrator import PhaseOrchestrator

# 全フェーズをインポート
from src.phases.phase_01_script import Phase01Script
from src.phases.phase_01_auto_script import Phase01AutoScript
from src.phases.phase_02_audio import Phase02Audio
from src.phases.phase_03_images import Phase03Images
from src.phases.phase_04_animation import Phase04Animation
from src.phases.phase_05_bgm import Phase05BGM
from src.phases.phase_06_subtitles import Phase06Subtitles
from src.phases.phase_07_composition import Phase07Composition
from src.phases.phase_08_thumbnail import Phase08Thumbnail
from src.phases.phase_09_youtube import Phase09YouTube


def write_error_log(config: ConfigManager, subject: str, phase_number: int, error: Exception) -> Path:
    """
    エラーログをファイルに書き込む

    Args:
        config: ConfigManager インスタンス
        subject: 偉人名
        phase_number: フェーズ番号
        error: 発生した例外

    Returns:
        エラーログファイルのパス
    """
    # ログディレクトリを取得
    log_dir = config.get_path("logs_dir")
    log_dir.mkdir(parents=True, exist_ok=True)

    # タイムスタンプ付きのエラーログファイル名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    error_log_filename = f"error_phase{phase_number}_{subject}_{timestamp}.txt"
    error_log_path = log_dir / error_log_filename

    # エラー情報を収集
    error_info = []
    error_info.append("=" * 80)
    error_info.append("ERROR LOG - Video Automation CLI")
    error_info.append("=" * 80)
    error_info.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    error_info.append(f"Subject: {subject}")
    error_info.append(f"Phase: {phase_number}")
    error_info.append(f"Error Type: {type(error).__name__}")
    error_info.append(f"Error Message: {str(error)}")
    error_info.append("")
    error_info.append("-" * 80)
    error_info.append("FULL TRACEBACK:")
    error_info.append("-" * 80)
    error_info.append(traceback.format_exc())
    error_info.append("=" * 80)

    # ファイルに書き込み
    with open(error_log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(error_info))

    return error_log_path


def run_phase(
    subject: str,
    phase_number: int,
    skip_if_exists: bool = False,
    use_auto_script: bool = False,
    verbose: bool = False,
    genre: Optional[str] = None,
    audio_var: Optional[str] = None,
    text_layout: Optional[str] = None,
    thumbnail_style: Optional[str] = None,
    use_legacy: bool = False,
    use_legacy02: bool = False
) -> int:
    """
    指定されたフェーズを実行

    Args:
        subject: 偉人名
        phase_number: フェーズ番号 (1-9)
        skip_if_exists: 既に出力が存在する場合はスキップ
        use_auto_script: Phase 1で自動台本生成を使用（--auto）
        genre: ジャンル名
        audio_var: 音声バリエーションID
        text_layout: テキストレイアウトID
        thumbnail_style: サムネイルスタイルID
        use_legacy: Phase 7でlegacy (moviepy) 版を使用 (Phase04の動画)
        use_legacy02: Phase 7でlegacy02 (moviepy) 版を使用 (Phase03の画像)

    Returns:
        終了コード (0: 成功, 1: 失敗)
    """
    # 設定を読み込み
    config = ConfigManager()

    # ロガーを設定
    log_level = "DEBUG" if verbose else "INFO"
    logger = setup_logger(
        name=f"cli_phase{phase_number}_{subject}",
        log_dir=config.get_path("logs_dir"),
        level=log_level
    )

    # フェーズクラスのマッピング
    phase_classes = {
        1: Phase01AutoScript if use_auto_script else Phase01Script,
        2: Phase02Audio,
        3: Phase03Images,
        4: Phase04Animation,
        5: Phase05BGM,
        6: Phase06Subtitles,
        7: Phase07Composition,
        8: Phase08Thumbnail,
        9: Phase09YouTube,
    }

    if phase_number not in phase_classes:
        logger.error(f"Invalid phase number: {phase_number}. Must be 1-9.")
        return 1

    # フェーズを実行
    try:
        logger.info("="*60)
        logger.info(f"Running Phase {phase_number} for: {subject}")
        logger.info("="*60)

        # フェーズインスタンスを作成
        phase_class = phase_classes[phase_number]

        # 各フェーズに応じたパラメータを渡す
        if phase_number == 1:
            phase = phase_class(
                subject=subject,
                config=config,
                logger=logger,
                genre=genre
            )
        elif phase_number == 2:
            phase = phase_class(
                subject=subject,
                config=config,
                logger=logger,
                audio_var=audio_var
            )
        elif phase_number == 3:
            phase = phase_class(
                subject=subject,
                config=config,
                logger=logger,
                genre=genre
            )
        elif phase_number == 7:
            # Phase 7: 動画統合（--legacy / --legacy02 オプション対応）
            if use_legacy02:
                # Legacy02版を使用（Phase03の画像）
                from src.phases.phase_07_composition_legacy02 import Phase07CompositionLegacy02
                phase = Phase07CompositionLegacy02(
                    subject=subject,
                    config=config,
                    logger=logger
                )
            else:
                # 通常版またはLegacy版（Phase04の動画）
                phase = phase_class(
                    subject=subject,
                    config=config,
                    logger=logger,
                    use_legacy=use_legacy
                )
        elif phase_number == 8:
            phase = phase_class(
                subject=subject,
                config=config,
                logger=logger,
                genre=genre,
                text_layout=text_layout,
                style=thumbnail_style
            )
        else:
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
        if execution.duration_seconds is not None:
            logger.info(f"Duration: {execution.duration_seconds:.2f}s")
        else:
            logger.info("Duration: N/A")

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

            # Phase 9の場合、アップロード結果を確認
            if phase_number == 9:
                upload_log_path = phase.phase_dir / "upload_log.json"
                if upload_log_path.exists():
                    import json
                    with open(upload_log_path, 'r', encoding='utf-8') as f:
                        upload_log = json.load(f)

                    logger.info("")
                    logger.info("=" * 60)
                    logger.info("YouTube Upload Complete!")
                    logger.info("=" * 60)
                    if upload_log.get("status") == "success":
                        logger.info(f"✓ Video ID: {upload_log.get('video_id')}")
                        logger.info(f"✓ URL: {upload_log.get('url')}")
                        logger.info(f"✓ Privacy: {upload_log.get('privacy_status')}")
                    else:
                        logger.info(f"Status: {upload_log.get('status')}")

            return 0
        elif execution.status == PhaseStatus.SKIPPED:
            logger.info("Phase was skipped (outputs already exist)")
            return 0
        else:
            logger.error(f"Error: {execution.error_message}")

            # エラーログをファイルに出力
            if execution.error_message:
                try:
                    error_log_path = write_error_log(config, subject, phase_number, Exception(execution.error_message))
                    logger.error(f"Error log saved to: {error_log_path}")
                    print(f"\n❌ Error log saved to: {error_log_path}")
                except Exception as log_error:
                    logger.error(f"Failed to write error log: {log_error}")

            return 1

    except Exception as e:
        logger.error(f"Execution error: {e}", exc_info=True)

        # エラーログをファイルに出力
        try:
            error_log_path = write_error_log(config, subject, phase_number, e)
            logger.error(f"Error log saved to: {error_log_path}")
            print(f"\n❌ Error occurred during Phase {phase_number} execution")
            print(f"❌ Error log saved to: {error_log_path}")
            print(f"❌ Error: {type(e).__name__}: {str(e)}")
        except Exception as log_error:
            logger.error(f"Failed to write error log: {log_error}")
            print(f"\n❌ Error occurred but failed to save error log: {log_error}")

        return 1


def generate_video(
    subject: str,
    force: bool = False,
    from_phase: int = 1,
    until_phase: int = 9,
    verbose: bool = False,
    auto: bool = False,
    manual: bool = False,
    genre: Optional[str] = None,
    audio_var: Optional[str] = None,
    text_layout: Optional[str] = None,
    thumbnail_style: Optional[str] = None,
    skip_phase04: bool = False,
    skip_bgm: bool = False
) -> int:
    """
    動画を生成（全フェーズ一括実行）

    Args:
        subject: 偉人名
        force: 既存出力を無視して強制再実行
        from_phase: 指定フェーズから実行（1-9）
        until_phase: 指定フェーズまで実行（1-9）
        verbose: 詳細ログ出力
        auto: 自動台本生成を使用（--auto）
        manual: 手動台本を使用（--manual）
        genre: ジャンル名
        audio_var: 音声バリエーションID
        text_layout: テキストレイアウトID
        thumbnail_style: サムネイルスタイルID
        skip_phase04: Phase 04をスキップ
        skip_bgm: Phase 05をスキップ

    Returns:
        終了コード (0: 成功, 1: 失敗)
    """
    # 設定を読み込み
    config = ConfigManager()

    # --manual と --auto の同時指定チェック
    if manual and auto:
        print("❌ Error: --manual と --auto は同時に指定できません")
        return 1

    # --manual の場合、手動台本変換を実行
    if manual:
        logger = setup_logger(
            name="manual_script_conversion",
            log_dir=config.get_path("logs_dir"),
            level="INFO"
        )
        logger.info(f"Converting manual script for: {subject}")

        # scripts/convert_manual_script.py を実行
        try:
            import subprocess
            result = subprocess.run(
                ["python", "scripts/convert_manual_script.py", subject],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                logger.error(f"Manual script conversion failed: {result.stderr}")
                return 1
            logger.info("Manual script converted successfully")
        except Exception as e:
            logger.error(f"Failed to convert manual script: {e}")
            return 1

    # ロガーを初期化
    log_level = "DEBUG" if verbose else "INFO"
    logger = setup_logger(
        name="video_generation",
        log_dir=config.get_path("logs_dir"),
        level=log_level
    )

    # --auto の場合、Phase 1で自動台本生成を使用
    if auto and from_phase == 1:
        logger.info("Using automatic script generation (Phase01AutoScript)")
        try:
            # Phase 1を個別に実行
            result = run_phase(
                subject=subject,
                phase_number=1,
                skip_if_exists=not force,
                use_auto_script=True,
                genre=genre
            )
            if result != 0:
                logger.error("Auto script generation failed")
                return 1

            # Phase 1のみの実行の場合はここで終了
            if until_phase == 1:
                return 0

            # Phase 2以降を実行
            from_phase = 2
        except Exception as e:
            logger.error(f"Auto script generation failed: {e}")
            return 1

    # スキップするフェーズのリストを作成
    skip_phases = []
    if skip_phase04:
        skip_phases.append(4)
        logger.info("⏭️  Phase 04 (image animation) will be skipped")
    if skip_bgm:
        skip_phases.append(5)
        logger.info("⏭️  Phase 05 (BGM selection) will be skipped")

    # Orchestratorを作成
    orchestrator = PhaseOrchestrator(
        config=config,
        logger=logger,
        genre=genre,
        audio_var=audio_var,
        text_layout=text_layout,
        thumbnail_style=thumbnail_style
    )

    # 実行
    try:
        project_status = orchestrator.run_all_phases(
            subject=subject,
            skip_if_exists=not force,
            from_phase=from_phase,
            until_phase=until_phase,
            skip_phases=skip_phases
        )

        # 終了コード
        if project_status.overall_status.value == "completed":
            return 0
        else:
            return 1

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="Video automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate entire video (Phase 1-9)
  python -m src.cli generate "織田信長"

  # Generate with automatic script generation
  python -m src.cli generate "織田信長" --auto

  # Generate auto script only (Phase 1)
  python -m src.cli generate "織田信長" --auto --until-phase 1

  # Convert manual script and generate
  python -m src.cli generate "織田信長" --manual

  # Generate script (Phase 1)
  python -m src.cli run-phase "織田信長" --phase 1

  # Generate auto script (Phase 1)
  python -m src.cli run-phase "織田信長" --phase 1 --auto

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

  # Generate thumbnails (Phase 8)
  python -m src.cli run-phase "織田信長" --phase 8

  # Upload to YouTube (Phase 9)
  python -m src.cli run-phase "織田信長" --phase 9

  # Skip if outputs exist
  python -m src.cli run-phase "織田信長" --phase 2 --skip-if-exists

  # Run from Phase 3 to Phase 7
  python -m src.cli generate "織田信長" --from-phase 3 --until-phase 7
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # generate コマンド（全フェーズ一括実行）
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate video (run all phases)"
    )
    generate_parser.add_argument(
        "subject",
        type=str,
        help="Subject name (e.g., 'グリゴリー・ラスプーチン')"
    )
    generate_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-execution even if outputs exist"
    )
    generate_parser.add_argument(
        "--from-phase",
        type=int,
        default=1,
        choices=[1, 2, 3, 4, 5, 6, 7, 8, 9],
        help="Start from specified phase (1-9)"
    )
    generate_parser.add_argument(
        "--until-phase",
        type=int,
        default=9,
        choices=[1, 2, 3, 4, 5, 6, 7, 8, 9],
        help="Run until specified phase (1-9)"
    )
    generate_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    generate_parser.add_argument(
        "--auto",
        action="store_true",
        help="Use automatic script generation (Phase 1)"
    )
    generate_parser.add_argument(
        "--manual",
        action="store_true",
        help="Convert manual script before generation"
    )
    generate_parser.add_argument(
        "--genre",
        type=str,
        default=None,
        help="Genre name (e.g., 'ijin')"
    )
    generate_parser.add_argument(
        "--audio-var",
        type=str,
        default=None,
        help="Audio variation ID (e.g., 'kokoro_standard')"
    )
    generate_parser.add_argument(
        "--text-layout",
        type=str,
        default=None,
        help="Thumbnail text layout ID (e.g., 'two_line_red_white')"
    )
    generate_parser.add_argument(
        "--thumbnail-style",
        type=str,
        default=None,
        help="Thumbnail style ID (e.g., 'dramatic_side')"
    )
    generate_parser.add_argument(
        "--skip-phase04",
        action="store_true",
        help="Skip Phase 04 (image animation)"
    )
    generate_parser.add_argument(
        "--skip-bgm",
        action="store_true",
        help="Skip Phase 05 (BGM selection)"
    )

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
        choices=[1, 2, 3, 4, 5, 6, 7, 8, 9],
        help="Phase number (1-9)"
    )
    run_parser.add_argument(
        "--skip-if-exists",
        action="store_true",
        help="Skip if outputs already exist"
    )
    run_parser.add_argument(
        "--auto",
        action="store_true",
        help="Use automatic script generation (Phase 1 only)"
    )
    run_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging"
    )
    run_parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy (moviepy) implementation for Phase 7 with Phase04 videos"
    )
    run_parser.add_argument(
        "--legacy02",
        action="store_true",
        help="Use legacy02 (moviepy) implementation for Phase 7 with Phase03 images"
    )

    # 引数をパース
    args = parser.parse_args()

    # コマンドが指定されていない場合
    if not args.command:
        parser.print_help()
        return 1

    # generate コマンド
    if args.command == "generate":
        return generate_video(
            subject=args.subject,
            force=args.force,
            from_phase=args.from_phase,
            until_phase=args.until_phase,
            verbose=args.verbose,
            auto=args.auto,
            manual=args.manual,
            genre=args.genre,
            audio_var=args.audio_var,
            text_layout=args.text_layout,
            thumbnail_style=args.thumbnail_style,
            skip_phase04=args.skip_phase04,
            skip_bgm=args.skip_bgm
        )

    # run-phase コマンド
    if args.command == "run-phase":
        return run_phase(
            subject=args.subject,
            phase_number=args.phase,
            skip_if_exists=args.skip_if_exists,
            use_auto_script=args.auto,
            verbose=args.verbose,
            genre=getattr(args, 'genre', None),
            audio_var=getattr(args, 'audio_var', None),
            text_layout=getattr(args, 'text_layout', None),
            thumbnail_style=getattr(args, 'thumbnail_style', None),
            use_legacy=args.legacy,
            use_legacy02=getattr(args, 'legacy02', False)
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
