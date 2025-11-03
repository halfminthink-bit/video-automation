#!/usr/bin/env python3
"""
Phase 7: 動画統合のテストスクリプト

使用方法:
    python test_phase07.py

必要な入力:
    - Phase 1: data/working/{subject}/01_script/script.json
    - Phase 2: data/working/{subject}/02_audio/narration_full.mp3
    - Phase 4: data/working/{subject}/04_animated/*.mp4
    - Phase 6: data/working/{subject}/06_subtitles/subtitle_timing.json

出力:
    - data/output/videos/{subject}.mp4
    - data/output/thumbnails/{subject}_thumbnail.jpg
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.config_manager import ConfigManager
from src.phases.phase_07_composition import Phase07Composition
from src.utils.logger import setup_logger


def check_moviepy():
    """MoviePyがインストールされているか確認"""
    try:
        import moviepy
        from moviepy import VideoFileClip
        print("✓ MoviePy is installed")
        print(f"  Version: {moviepy.__version__ if hasattr(moviepy, '__version__') else 'unknown'}")
        return True
    except ImportError as e:
        print("✗ MoviePy is not installed")
        print(f"\nImport error: {e}")
        print("\nInstall with:")
        print("  pip install moviepy")
        return False


def main():
    """Phase 7のテスト実行"""
    
    # MoviePyチェック
    if not check_moviepy():
        return 1
    
    # 設定
    subject = "織田信長"  # テスト対象
    working_dir = Path("data/working")
    config_path = "config/settings.yaml"
    
    print("=" * 70)
    print(" Phase 7: Video Composition Test")
    print("=" * 70)
    print()
    
    # ロガーセットアップ
    logger = setup_logger(
        name="phase07_test",
        log_dir=Path("logs"),
        level="DEBUG",  # DEBUGに変更して詳細表示
        to_console=True,
        to_file=True
    )
    
    try:
        # ConfigManager初期化
        logger.info(f"Loading config: {config_path}")
        config = ConfigManager(config_path)
        
        # Phase 7インスタンス作成
        phase = Phase07Composition(
            subject=subject,
            config=config,
            logger=logger
        )
        
        # 入力ファイルチェック
        print("\n[Step 1] Checking input files...")
        if not phase.check_inputs_exist():
            print("\n✗ Required input files are missing!")
            print("\nRequired files:")
            print(f"  - {working_dir}/{subject}/01_script/script.json")
            print(f"  - {working_dir}/{subject}/02_audio/narration_full.mp3")
            print(f"  - {working_dir}/{subject}/04_animated/*.mp4")
            print(f"  - {working_dir}/{subject}/06_subtitles/subtitle_timing.json")
            print("\nPlease complete Phase 1, 2, 4, and 6 first.")
            return 1
        
        print("✓ All required input files found")
        
        # 既存出力チェック
        print("\n[Step 2] Checking for existing output...")
        if phase.check_outputs_exist():
            print("⚠  Output video already exists")
            response = input("\nRegenerate video? This will take several minutes. (y/n): ")
            if response.lower() != 'y':
                print("Skipped.")
                return 0
        
        # 実行確認
        print("\n[Step 3] Ready to start video composition")
        print("\nThis process will:")
        print("  1. Load all animated clips")
        print("  2. Loop clips to match audio duration")
        print("  3. Add narration audio")
        print("  4. Add BGM (if available)")
        print("  5. Burn in subtitles")
        print("  6. Render final video")
        print("\n⏱  Estimated time: 5-15 minutes (depending on video length)")
        
        response = input("\nStart video composition? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 0
        
        # Phase 7実行
        print("\n" + "=" * 70)
        print(" Starting Video Composition")
        print("=" * 70)
        print()
        
        result = phase.run(skip_if_exists=False)
        
        # 結果表示
        print("\n" + "=" * 70)
        if result.status.value == "completed":
            print(" ✓ Video Composition Completed Successfully!")
            print("=" * 70)
            print()
            print(f"Duration: {result.duration_seconds:.1f} seconds")
            
            # 出力ファイル情報
            output_dir = config.get("paths", {}).get("output_dir", "data/output")
            video_path = Path(output_dir) / "videos" / f"{subject}.mp4"
            thumbnail_path = Path(output_dir) / "thumbnails" / f"{subject}_thumbnail.jpg"
            
            print("\n📁 Output Files:")
            print(f"  Video:     {video_path}")
            if video_path.exists():
                size_mb = video_path.stat().st_size / (1024 * 1024)
                print(f"             ({size_mb:.1f} MB)")
            
            print(f"  Thumbnail: {thumbnail_path}")
            
            metadata_path = phase.phase_dir / "metadata.json"
            print(f"  Metadata:  {metadata_path}")
            
            print("\n✓ All done! You can now view your video.")
            return 0
            
        else:
            print(" ✗ Video Composition Failed")
            print("=" * 70)
            print()
            print(f"Error: {result.error_message}")
            print()
            print("Check the log file for details:")
            print(f"  logs/")
            return 1
    
    except KeyboardInterrupt:
        print("\n\n⚠  Interrupted by user")
        return 1
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        print("\nCheck the log file for details:")
        print("  logs/")
        return 1


if __name__ == "__main__":
    sys.exit(main())