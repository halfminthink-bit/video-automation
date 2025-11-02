"""
Phase 4: Replicate版のテストスクリプト
使用方法:
1. phase_04_animation_replicate.py を src/phases/phase_04_animation.py にコピー
2. config/.env に REPLICATE_API_TOKEN を追加済みであること確認
3. このスクリプトを実行: python test4_replicate.py
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# .envファイルを読み込み
env_path = Path("config/.env")
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✓ Loaded .env from {env_path}")
else:
    print(f"⚠ .env file not found at {env_path}")
    sys.exit(1)

# Replicate APIトークンの確認
import os
replicate_token = os.getenv("REPLICATE_API_TOKEN")
if replicate_token:
    print(f"✓ REPLICATE_API_TOKEN found (starts with: {replicate_token[:10]}...)")
else:
    print("✗ REPLICATE_API_TOKEN not found in .env")
    print("\n対処方法:")
    print("  1. https://replicate.com/account/api-tokens でトークンを作成")
    print("  2. config/.env に追加: REPLICATE_API_TOKEN=r8_your_token")
    sys.exit(1)

from src.core.config_manager import ConfigManager
from src.phases.phase_04_animation import Phase04Animation
from src.utils.logger import setup_logger


def test_phase_04_replicate():
    """Phase 4をReplicate版でテスト実行"""
    
    # 設定
    subject = "織田信長"
    
    # ConfigManager初期化
    config = ConfigManager("config/settings.yaml")
    
    # Logger設定
    logger = setup_logger(
        name="phase_04_replicate_test",
        log_dir=Path("logs"),
        level="INFO"
    )
    
    logger.info("=" * 60)
    logger.info("Phase 4: Image Animation (Replicate版) - Test")
    logger.info("=" * 60)
    
    # Phase 4初期化
    phase = Phase04Animation(
        subject=subject,
        config=config,
        logger=logger
    )
    
    # AI動画の有効状態を確認
    logger.info(f"\nAI Video Generation: {'✓ Enabled' if phase.use_ai_video else '✗ Disabled'}")
    if phase.use_ai_video:
        logger.info("Replicate API will be used for AI videos")
    else:
        logger.info("Only simple pan animations will be used")
    
    # 入力チェック
    logger.info("\n[Step 1] Checking inputs...")
    if not phase.check_inputs_exist():
        logger.error("Required inputs not found!")
        logger.error("Please run Phase 3 first.")
        return False
    logger.info("✓ All inputs exist")
    
    # 既存出力チェック
    logger.info("\n[Step 2] Checking existing outputs...")
    if phase.check_outputs_exist():
        logger.warning("Outputs already exist.")
        user_input = input("Delete and regenerate? (y/n): ")
        if user_input.lower() != 'y':
            logger.info("Skipping regeneration.")
            return True
        
        # 出力ディレクトリをクリア
        import shutil
        if phase.output_dir.exists():
            shutil.rmtree(phase.output_dir)
            phase.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info("✓ Cleared existing outputs")
    
    # Phase 4実行
    logger.info("\n[Step 3] Running Phase 4...")
    logger.info("⚠ This may take several minutes if AI video generation is enabled")
    
    try:
        result = phase.execute_phase()
        
        logger.info("\n" + "=" * 60)
        logger.info("Phase 4 Completed Successfully!")
        logger.info("=" * 60)
        logger.info(f"Subject: {result.subject}")
        logger.info(f"Total clips: {len(result.animated_clips)}")
        
        # クリップの内訳
        ai_count = sum(1 for c in result.animated_clips if c.clip_id.startswith('ai_'))
        simple_count = len(result.animated_clips) - ai_count
        
        logger.info(f"\nBreakdown:")
        logger.info(f"  ✓ AI videos (via Replicate): {ai_count}")
        logger.info(f"  ✓ Simple animations (pan): {simple_count}")
        
        # AI動画の詳細
        if ai_count > 0:
            logger.info(f"\nAI Videos created:")
            for clip in result.animated_clips:
                if clip.clip_id.startswith('ai_'):
                    logger.info(f"  - {Path(clip.output_path).name} ({clip.duration}s)")
        
        # アニメーションタイプの統計
        from collections import Counter
        type_counts = Counter(c.animation_type.value for c in result.animated_clips if c.clip_id.startswith('simple_'))
        
        if simple_count > 0:
            logger.info(f"\nAnimation types:")
            for anim_type, count in type_counts.items():
                logger.info(f"  - {anim_type}: {count} clips")
        
        # 出力ファイル一覧
        logger.info(f"\nOutput directory: {phase.output_dir}")
        logger.info(f"Animation plan: animation_plan.json")
        
        # バリデーション
        logger.info("\n[Step 4] Validating output...")
        if phase.validate_output(result):
            logger.info("✓ Output validation passed")
            return True
        else:
            logger.error("✗ Output validation failed")
            return False
            
    except Exception as e:
        logger.error(f"Phase 4 failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_phase_04_replicate()
    
    if success:
        print("\n" + "=" * 60)
        print("✓ Phase 4 test completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Check output: data/working/織田信長/04_animated/")
        print("  2. Review animation_plan.json")
        print("  3. Play video clips to verify quality")
        print("\nNote: AI videos use Replicate's Kling AI API")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ Phase 4 test failed!")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("  1. Check logs/ directory for details")
        print("  2. Verify REPLICATE_API_TOKEN in config/.env")
        print("  3. Check Replicate account has credits")
        print("  4. Review error messages above")
        sys.exit(1)