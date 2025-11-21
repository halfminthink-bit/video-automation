"""
TikTok実アップロードテスト

Usage:
  python test_tiktok_upload.py "data\working\レオナルドダヴィンチ\10_shorts\vertical\vertical_001.mp4" "config/.tiktok_cookies_ijin.txt" --no-headless
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

def test_upload(video_path: Path, cookie_file: Path, headless: bool = True):
    """TikTokへの実アップロードテスト"""
    
    print("=" * 60)
    print("TikTok Upload Test")
    print("=" * 60)
    
    # インポート
    try:
        from tiktok_uploader.upload import upload_video
    except ImportError:
        print("✗ tiktok-uploader not installed")
        print("Install with: pip install tiktok-uploader")
        sys.exit(1)
    
    # ファイル確認
    if not video_path.exists():
        print(f"✗ Video file not found: {video_path}")
        sys.exit(1)
    
    if not cookie_file.exists():
        print(f"✗ Cookie file not found: {cookie_file}")
        sys.exit(1)
    
    print(f"\nVideo: {video_path}")
    print(f"Size: {video_path.stat().st_size / (1024*1024):.2f} MB")
    print(f"Cookie: {cookie_file}")
    print(f"Headless: {headless}")
    
    # テスト用の説明文
    test_description = f"テスト投稿 {datetime.now().strftime('%Y%m%d_%H%M%S')} #test"
    
    print(f"\nDescription: {test_description}")
    print("\n" + "=" * 60)
    print("Starting upload...")
    print("=" * 60)
    
    try:
        # アップロード実行
        result = upload_video(
            filename=str(video_path),
            description=test_description,
            cookies=str(cookie_file),
            browser="chrome",
            headless=headless
        )
        
        print("\n" + "=" * 60)
        print("Upload completed!")
        print("=" * 60)
        print(f"\nResult: {result}")
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("Upload failed!")
        print("=" * 60)
        print(f"\nError: {e}")
        print(f"\nError type: {type(e).__name__}")
        
        # 詳細なエラー情報
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        
        return False


def main():
    parser = argparse.ArgumentParser(description="Test TikTok upload")
    parser.add_argument("video_path", help="Path to video file")
    parser.add_argument("cookie_file", help="Path to cookie file")
    parser.add_argument("--no-headless", action="store_true", 
                       help="Show browser window (default: headless)")
    
    args = parser.parse_args()
    
    video_path = Path(args.video_path)
    cookie_file = Path(args.cookie_file)
    headless = not args.no_headless
    
    success = test_upload(video_path, cookie_file, headless)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
