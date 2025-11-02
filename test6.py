#!/usr/bin/env python3
"""
Phase 6 (BGM選択) のテストスクリプト

実行方法:
    python test_phase06.py

前提条件:
    - data/working/織田信長/01_script/script.json が存在
    - data/working/織田信長/02_audio/audio_analysis.json が存在
    - assets/bgm/ にBGMファイルが配置されている
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from phase_06_bgm import Phase06BGM


def setup_logging():
    """ロギング設定"""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(asctime)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/test_phase06.log", encoding="utf-8"),
        ],
    )
    return logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger = setup_logging()
    logger.info("Starting Phase 6 test (Fixed 3 Tracks)")
    
    # 設定（3曲固定）
    config = {
        "bgm_library_path": "assets/bgm",
        "fixed_bgm_structure": {
            "enabled": True,
            "tracks": {
                "opening": {
                    "file": "opening/古の街道.mp3",
                    "title": "古の街道",
                    "description": "ぼんやりはじまる曲",
                },
                "main": {
                    "file": "main/SPQR-メメントモリ-.mp3",
                    "title": "SPQR-メメントモリ-",
                    "description": "基本メインの曲",
                },
                "ending": {
                    "file": "ending/朝の訪れ.mp3",
                    "title": "朝の訪れ",
                    "description": "しっとりとした曲",
                },
            },
        },
        "timing": {
            "opening_ratio": 0.15,
            "main_ratio": 0.70,
            "ending_ratio": 0.15,
        },
        "default_settings": {
            "volume": 0.3,
            "fade_in_duration": 2.0,
            "fade_out_duration": 2.0,
        },
    }
    
    # Phase 6 実行
    try:
        phase = Phase06BGM(
            subject="織田信長",
            working_dir=Path("data/working"),
            config=config,
            logger=logger,
        )
        
        logger.info("Executing Phase 6...")
        result = phase.execute()
        
        # 結果を表示
        print("\n" + "=" * 60)
        print("Phase 6: BGM Selection - COMPLETED")
        print("=" * 60)
        print(f"Subject: {result.subject}")
        print(f"Total segments: {len(result.segments)}")
        print(f"Tracks used: {len(result.tracks_used)}")
        print()
        
        # BGMタイムラインを表示
        print("BGM Timeline:")
        print("-" * 60)
        for i, segment in enumerate(result.segments, 1):
            track = next(
                (t for t in result.tracks_used if t.track_id == segment.track_id),
                None,
            )
            track_name = track.title if track else segment.track_id
            
            print(f"{i}. {track_name}")
            print(f"   Category: {track.category if track else 'unknown'}")
            print(f"   Time: {segment.start_time:.1f}s - "
                  f"{segment.start_time + segment.duration:.1f}s "
                  f"({segment.duration:.1f}s)")
            print(f"   Volume: {segment.volume:.1%}, "
                  f"Fade in/out: {segment.fade_in:.1f}s / {segment.fade_out:.1f}s")
            print()
        
        # 出力ファイル
        print("Output files:")
        print(f"  - {phase.phase_dir / 'bgm_timeline.json'}")
        print(f"  - {phase.phase_dir / 'selected_tracks.json'}")
        print()
        
        logger.info("Phase 6 test completed successfully")
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"Required input not found: {e}")
        print("\nError: Required input files are missing.")
        print("Please ensure Phase 1 and Phase 2 have been completed.")
        return 1
        
    except Exception as e:
        logger.error(f"Phase 6 failed: {e}", exc_info=True)
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())