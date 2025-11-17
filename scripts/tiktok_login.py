#!/usr/bin/env python3
"""
TikTokログインスクリプト

初回のみ実行して、手動ログイン後にCookieを保存する。
保存したCookieはPhase 11で自動的に使用される。
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.tiktok_uploader import TikTokUploader


def main():
    """TikTokログインスクリプトのメイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="TikTok Login Script - Save cookies for automated uploads"
    )
    parser.add_argument(
        "--cookies",
        required=True,
        help="Path to save cookies file (e.g., config/.tiktok_cookies_ijin.pkl)"
    )
    parser.add_argument(
        "--profile-url",
        default="https://www.tiktok.com/@labyrinthofevidence",
        help="URL of the profile page to navigate to after login (default: %(default)s)"
    )
    parser.add_argument(
        "--wait-time",
        type=int,
        default=300,
        help="Maximum time to wait for login (seconds, default: 300)"
    )
    
    args = parser.parse_args()
    
    # ロガー設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    cookies_file = Path(args.cookies)
    
    logger.info("=" * 60)
    logger.info("TikTok Login Script")
    logger.info("=" * 60)
    logger.info(f"Cookies will be saved to: {cookies_file}")
    logger.info(f"Maximum wait time: {args.wait_time} seconds")
    logger.info(f"Profile URL for detection: {args.profile_url}")
    logger.info("")
    
    try:
        # TikTokUploaderを初期化（ヘッドレスモードOFF）
        with TikTokUploader(
            cookies_file=cookies_file,
            headless=False,
            logger=logger,
            profile_url=args.profile_url
        ) as uploader:
            
            logger.info("Opening TikTok login page...")
            logger.info("")
            logger.info("=" * 60)
            logger.info("PLEASE LOGIN MANUALLY IN THE BROWSER WINDOW")
            logger.info("=" * 60)
            logger.info("1. Enter your email and password")
            logger.info("2. Complete any verification steps (CAPTCHA, 2FA, etc.)")
            logger.info("3. Wait until you see your profile icon in the top right")
            logger.info("4. The script will automatically detect login completion")
            logger.info("=" * 60)
            logger.info("")
            
            # ログインしてCookieを保存
            uploader.login_and_save_cookies(wait_time=args.wait_time)
            
            logger.info("")
            logger.info("=" * 60)
            logger.info("✅ LOGIN SUCCESSFUL!")
            logger.info("=" * 60)
            logger.info(f"Cookies saved to: {cookies_file}")
            logger.info("")
            logger.info("You can now use Phase 11 to upload videos automatically:")
            logger.info(f"  python -m src.phases.phase_11_tiktok <subject> --genre ijin")
            logger.info("=" * 60)
            
    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error("❌ LOGIN FAILED")
        logger.error("=" * 60)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("Please try again:")
        logger.error(f"  python scripts/tiktok_login.py --cookies {cookies_file}")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
