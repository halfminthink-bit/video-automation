"""
TikTok自動投稿ユーティリティ

Seleniumを使用してTikTokに動画を自動投稿する。
Cookie認証方式でBot検知を回避。
"""

import time
import pickle
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class TikTokUploader:
    """TikTok自動投稿クラス"""
    
    TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload"
    TIKTOK_LOGIN_URL = "https://www.tiktok.com/login"
    
    def __init__(
        self,
        cookies_file: Optional[Path] = None,
        headless: bool = False,
        logger: Optional[logging.Logger] = None,
        profile_url: Optional[str] = None # ログイン後の遷移先URL
    ):
        """
        初期化
        
        Args:
            cookies_file: Cookieファイルのパス（pickle形式）
            headless: ヘッドレスモードで実行するか
            logger: ロガー
            profile_url: ログイン後の遷移先URL（ログイン検出の補助）
        """
        self.cookies_file = cookies_file
        self.headless = headless
        self.logger = logger or logging.getLogger(__name__)
        self.driver: Optional[webdriver.Chrome] = None
        self.profile_url = profile_url
        """
        初期化
        
        Args:
            cookies_file: Cookieファイルのパス（pickle形式）
            headless: ヘッドレスモードで実行するか
            logger: ロガー
        """
        self.cookies_file = cookies_file
        self.headless = headless
        self.logger = logger or logging.getLogger(__name__)
        self.driver: Optional[webdriver.Chrome] = None
        self.profile_url: Optional[str] = None # ログイン後の遷移先URL
        
    def __enter__(self):
        """コンテキストマネージャーのエントリ"""
        self._init_driver()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャーの終了"""
        self.close()
        
    def _init_driver(self) -> None:
        """Seleniumドライバーを初期化"""
        self.logger.info("Initializing Chrome driver...")
        
        chrome_options = Options()
        
        # ヘッドレスモード設定
        if self.headless:
            chrome_options.add_argument("--headless=new")
            self.logger.info("Running in headless mode")
        
        # Bot検知回避のための設定
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # その他の設定
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # User-Agentを設定（通常のブラウザに偽装）
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        # ChromeDriverを自動インストール
        service = Service(ChromeDriverManager().install())
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # WebDriver検知を回避するスクリプトを実行
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            }
        )
        
        self.logger.info("Chrome driver initialized successfully")
        
    def login_and_save_cookies(self, wait_time: int = 300) -> None:
        """
        手動ログイン後にCookieを保存
        
        Args:
            wait_time: ログイン完了を待つ最大時間（秒）
        """
        if not self.driver:
            self._init_driver()
            
        self.logger.info("Opening TikTok login page...")
        self.driver.get(self.TIKTOK_LOGIN_URL)
        
        # ユーザーが指定したプロフィールページに遷移
        if self.profile_url:
            self.logger.info(f"Navigating to profile page: {self.profile_url}")
            self.driver.get(self.profile_url)
            time.sleep(3) # ページロードを待つ
        
        # ユーザーが指定したプロフィールページに遷移
        if self.profile_url:
            self.logger.info(f"Navigating to profile page: {self.profile_url}")
            self.driver.get(self.profile_url)
            time.sleep(3) # ページロードを待つ
        
        self.logger.info(f"Please login manually within {wait_time} seconds...")
        self.logger.info("Waiting for login completion...")
        
        # ログイン完了を待つ（アップロードページへのリダイレクトを検知）
        start_time = time.time()
        logged_in = False
        
        while time.time() - start_time < wait_time:
            try:
                # ログイン後に表示される要素（プロフィールアイコン、アップロードボタンなど）を検出
                # 複数のセレクタを試す
                login_indicators = [
                    "[data-e2e='profile-icon']",  # プロフィールアイコン
                    "[data-e2e='upload-icon']",   # アップロードアイコン
                    "a[href*='/upload']",         # アップロードページへのリンク
                ]
                
                found = False
                for selector in login_indicators:
                    try:
                        self.driver.find_element(By.CSS_SELECTOR, selector)
                        found = True
                        break
                    except NoSuchElementException:
                        continue
                
                if found:
                    logged_in = True
                    break
            except NoSuchElementException:
                time.sleep(2)
                
        if not logged_in:
            raise TimeoutException("Login timeout. Please try again.")
            
        self.logger.info("Login successful!")
        
        # Cookieを保存
        if self.cookies_file:
            self._save_cookies()
            self.logger.info(f"Cookies saved to: {self.cookies_file}")
        else:
            self.logger.warning("No cookies_file specified, cookies not saved")
            
    def _save_cookies(self) -> None:
        """現在のCookieをファイルに保存"""
        if not self.driver:
            raise RuntimeError("Driver not initialized")
            
        cookies = self.driver.get_cookies()
        
        # Cookieファイルのディレクトリを作成
        self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.cookies_file, 'wb') as f:
            pickle.dump(cookies, f)
            
    def _load_cookies(self) -> None:
        """保存されたCookieを読み込み"""
        if not self.cookies_file or not self.cookies_file.exists():
            raise FileNotFoundError(
                f"Cookies file not found: {self.cookies_file}\n"
                "Please run login_and_save_cookies() first"
            )
            
        self.logger.info(f"Loading cookies from: {self.cookies_file}")
        
        with open(self.cookies_file, 'rb') as f:
            cookies = pickle.load(f)
            
        # TikTokのドメインにアクセスしてからCookieを設定
        self.driver.get("https://www.tiktok.com")
        time.sleep(2)
        
        for cookie in cookies:
            try:
                self.driver.add_cookie(cookie)
            except Exception as e:
                self.logger.warning(f"Failed to add cookie: {e}")
                
        self.logger.info("Cookies loaded successfully")
        
    def upload_video(
        self,
        video_path: Path,
        caption: str,
        wait_after_upload: int = 10
    ) -> Dict[str, Any]:
        """
        動画をTikTokにアップロード
        
        Args:
            video_path: 動画ファイルのパス
            caption: キャプション（説明文）
            wait_after_upload: アップロード後の待機時間（秒）
            
        Returns:
            アップロード結果
        """
        if not self.driver:
            self._init_driver()
            
        try:
            # Cookieを読み込んで認証
            self._load_cookies()
            
            # アップロードページに遷移
            self.logger.info("Navigating to upload page...")
            self.driver.get(self.TIKTOK_UPLOAD_URL)
            time.sleep(3)
            
            # 動画ファイルを選択
            self.logger.info(f"Uploading video: {video_path}")
            self._select_video_file(video_path)
            
            # アップロード完了を待つ
            self.logger.info("Waiting for video upload...")
            self._wait_for_upload_complete()
            
            # キャプションを入力
            self.logger.info("Entering caption...")
            self._enter_caption(caption)
            
            # 投稿ボタンをクリック
            self.logger.info("Clicking post button...")
            self._click_post_button()
            
            # 投稿完了を待つ
            self.logger.info("Waiting for post completion...")
            time.sleep(wait_after_upload)
            
            self.logger.info("Video uploaded successfully!")
            
            return {
                "status": "success",
                "video_path": str(video_path),
                "caption": caption
            }
            
        except Exception as e:
            self.logger.error(f"Upload failed: {e}", exc_info=True)
            raise
            
    def _select_video_file(self, video_path: Path) -> None:
        """動画ファイルを選択"""
        try:
            # ファイル入力要素を探す
            file_input = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            
            # ファイルパスを送信
            file_input.send_keys(str(video_path.absolute()))
            
            self.logger.info("Video file selected")
            
        except TimeoutException:
            raise TimeoutException("Failed to find file input element")
            
    def _wait_for_upload_complete(self, timeout: int = 300) -> None:
        """動画のアップロード完了を待つ"""
        self.logger.info("Waiting for video processing...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # アップロード進行中のインジケーターを確認
                # TikTokのUIは頻繁に変更されるため、複数のセレクタを試す
                
                # 方法1: プログレスバーが消えるのを待つ
                progress_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[class*='progress'], [class*='loading'], [class*='uploading']"
                )
                
                if not progress_elements:
                    # プログレスバーが見つからない = アップロード完了
                    self.logger.info("Upload complete (no progress indicator found)")
                    time.sleep(5)  # 念のため追加待機
                    return
                    
                time.sleep(2)
                
            except Exception as e:
                self.logger.warning(f"Error checking upload status: {e}")
                time.sleep(2)
                
        raise TimeoutException("Video upload timeout")
        
    def _enter_caption(self, caption: str) -> None:
        """キャプションを入力"""
        try:
            # キャプション入力欄を探す
            # TikTokは contenteditable の div を使用
            caption_input = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "div[contenteditable='true'], textarea[placeholder*='caption'], textarea[placeholder*='キャプション']"
                ))
            )
            
            # キャプションを入力
            caption_input.click()
            time.sleep(1)
            caption_input.send_keys(caption)
            
            self.logger.info("Caption entered")
            
        except TimeoutException:
            raise TimeoutException("Failed to find caption input element")
            
    def _click_post_button(self) -> None:
        """投稿ボタンをクリック"""
        try:
            # 投稿ボタンを探す
            # 複数のセレクタを試す
            post_button_selectors = [
                "button[data-e2e='post-button']",
                "button:contains('Post')",
                "button:contains('投稿')",
                "//button[contains(text(), 'Post')]",
                "//button[contains(text(), '投稿')]"
            ]
            
            post_button = None
            
            for selector in post_button_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath
                        post_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        # CSS Selector
                        post_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    break
                except TimeoutException:
                    continue
                    
            if not post_button:
                raise TimeoutException("Failed to find post button")
                
            # ボタンをクリック
            post_button.click()
            
            self.logger.info("Post button clicked")
            
        except TimeoutException:
            raise TimeoutException("Failed to click post button")
            
    def close(self) -> None:
        """ブラウザを閉じる"""
        if self.driver:
            self.logger.info("Closing browser...")
            self.driver.quit()
            self.driver = None


def main():
    """テスト用のエントリーポイント"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTok Uploader")
    parser.add_argument("--login", action="store_true", help="Login and save cookies")
    parser.add_argument("--upload", help="Video file to upload")
    parser.add_argument("--caption", default="Test upload", help="Video caption")
    parser.add_argument("--cookies", required=True, help="Cookies file path")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    
    args = parser.parse_args()
    
    # ロガー設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    cookies_file = Path(args.cookies)
    
    with TikTokUploader(cookies_file=cookies_file, headless=args.headless, logger=logger) as uploader:
        if args.login:
            # ログインしてCookieを保存
            uploader.login_and_save_cookies()
            logger.info("Login completed. Cookies saved.")
            
        elif args.upload:
            # 動画をアップロード
            video_path = Path(args.upload)
            if not video_path.exists():
                logger.error(f"Video file not found: {video_path}")
                return
                
            result = uploader.upload_video(
                video_path=video_path,
                caption=args.caption
            )
            logger.info(f"Upload result: {result}")
            
        else:
            logger.error("Please specify --login or --upload")


if __name__ == "__main__":
    main()
