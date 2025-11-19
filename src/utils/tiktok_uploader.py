"""
TikTok投稿ユーティリティ（Selenium操作）

Chromeプロファイルを使用してTikTokに動画を投稿する。
"""

import time
import subprocess
import random
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import logging

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

from ..core.exceptions import VideoAutomationError


class TikTokUIChangedError(VideoAutomationError):
    """TikTokのUIが変更されて要素が見つからない"""
    pass


class TikTokUploadError(VideoAutomationError):
    """TikTok投稿の一般的なエラー"""
    pass


class TikTokUploader:
    """TikTok投稿を行うクラス（Selenium操作）"""
    
    def __init__(self, config: dict, logger: logging.Logger, genre: Optional[str] = None):
        """
        Args:
            config: tiktok_upload.yamlの内容
            logger: ロガー
            genre: ジャンル名（エラーメッセージ用）
        """
        self.config = config
        self.logger = logger
        self.genre = genre
        
        # Selenium設定
        selenium_config = config.get("selenium", {})
        self.headless = selenium_config.get("headless", False)
        self.window_size = selenium_config.get("window_size", "1920x1080")
        self.wait_timeout = selenium_config.get("wait_timeout", 10)
        self.chrome_profile_path = Path(selenium_config.get(
            "chrome_profile_path",
            "C:\\Users\\hyokaimen\\AppData\\Local\\Google\\Chrome\\User Data"
        ))
        self.account_page_url = selenium_config.get("account_page_url", "")
        
        # セレクタ設定
        self.selectors = config.get("selectors", {})
        
        # 出力設定
        output_config = config.get("output", {})
        self.screenshots_dir = Path(output_config.get("screenshots_dir", "screenshots"))
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        self.driver: Optional[webdriver.Chrome] = None
        self.profile_name: Optional[str] = None
        self._initialized = False  # ドライバーが初期化済みかどうか
    
    def _ensure_driver(self, profile_name: str) -> webdriver.Chrome:
        """
        ドライバーが存在しない場合のみ作成（再利用可能）
        
        Args:
            profile_name: Chromeプロファイル名
            
        Returns:
            Chrome WebDriver
            
        Raises:
            TikTokUploadError: ドライバー作成失敗時
        """
        self.logger.info("=== _ensure_driver called ===")
        self.logger.info(f"Driver exists: {self.driver is not None}")
        self.logger.info(f"Initialized: {self._initialized}")
        self.logger.info(f"Profile name: {profile_name}")
        
        if self.driver is None or not self._initialized:
            self.logger.info("Driver not initialized, creating new driver...")
            try:
                self.driver = self._create_driver(profile_name)
                self.profile_name = profile_name
                self._initialized = True
                self.logger.info("Driver created successfully")
                
                # 初回のみTikTokのURLに移動
                self.logger.info("Navigating to upload page (first time)...")
                self._navigate_to_upload_page()
            except Exception as e:
                # エラーが出たらクリーンアップ
                self.logger.error(f"Failed to create driver: {e}", exc_info=True)
                self.driver = None
                self._initialized = False
                self.profile_name = None
                raise  # エラーを再スロー
        else:
            self.logger.info("Driver already exists, reusing...")
            self.logger.info(f"Current URL: {self.driver.current_url}")
        
        self.logger.info("=== _ensure_driver completed ===")
        return self.driver
    
    def _close_chrome_processes(self) -> bool:
        """
        Chromeプロセスを終了する
        
        Chromeが起動中だとCookiesデータベースがロックされて不完全なコピーになるため、
        先にChromeを閉じる。
        
        Returns:
            Chromeプロセスがあった場合True、なかった場合False
        """
        self.logger.info("Checking for running Chrome processes...")
        
        try:
            # Chromeプロセスをチェック
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if 'chrome.exe' in result.stdout:
                self.logger.warning("Chrome is running. Closing all Chrome processes...")
                
                # Chromeを終了
                subprocess.run(
                    ['taskkill', '/F', '/IM', 'chrome.exe'],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                # ChromeDriverも終了
                subprocess.run(
                    ['taskkill', '/F', '/IM', 'chromedriver.exe'],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                # プロセス終了を待つ
                time.sleep(2)
                
                self.logger.info("Chrome processes closed successfully")
                return True
            else:
                self.logger.debug("No Chrome processes found")
                return False
                
        except Exception as e:
            self.logger.warning(f"Failed to check/close Chrome processes: {e}")
            return False
    
    def _cleanup_chrome_and_locks(self, profile_name: str):
        """
        Chromeプロセスを終了し、ロックファイルを削除
        
        Args:
            profile_name: Chromeプロファイル名
        """
        self.logger.info("Cleaning up Chrome processes and lock files...")
        
        # 1. Chromeプロセスを終了
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', 'chrome.exe', '/T'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            subprocess.run(
                ['taskkill', '/F', '/IM', 'chromedriver.exe', '/T'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            time.sleep(2)  # プロセス終了を待つ
            self.logger.debug("Chrome processes terminated")
        except Exception as e:
            self.logger.warning(f"Failed to kill Chrome processes: {e}")
        
        # 2. ロックファイルを削除
        profile_path = self.chrome_profile_path / profile_name
        lock_files = [
            'Singleton Lock',
            'lockfile',
            'LOCK'
        ]
        
        for lock_file in lock_files:
            lock_path = profile_path / lock_file
            if lock_path.exists():
                try:
                    lock_path.unlink()
                    self.logger.debug(f"Deleted lock file: {lock_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete {lock_file}: {e}")
    
    def _navigate_to_upload_page(self):
        """
        TikTokアップロードページに移動（初回のみ実行）
        """
        self.logger.info("=== Starting _navigate_to_upload_page ===")
        
        # TikTok Studioのアップロードページに直接移動
        upload_url = "https://www.tiktok.com/tiktokstudio/upload"
        self.logger.info(f"Navigating to TikTok Studio upload page: {upload_url}")
        
        try:
            self.driver.get(upload_url)
            self.logger.info(f"Successfully called driver.get('{upload_url}')")
            
            # ページ読み込み待機（TikTokは読み込みが遅いので少し長めに待つ）
            time.sleep(5)
            
            # URLが正しく遷移したか確認
            current_url = self.driver.current_url
            self.logger.info(f"Current URL after navigation: {current_url}")
            self.logger.info(f"Page title: {self.driver.title}")
            
            if "tiktokstudio" not in current_url and "upload" not in current_url:
                self.logger.warning(f"Expected upload page, but got: {current_url}")
                self._save_screenshot("unexpected_page")
        except Exception as e:
            self.logger.error(f"Error navigating to upload page: {e}", exc_info=True)
            self._save_screenshot("navigate_error")
            raise
        
        self.logger.info("=== Completed _navigate_to_upload_page ===")
    
    def _create_driver(self, profile_name: str) -> webdriver.Chrome:
        """
        Chromeドライバーを作成（指定プロファイルを使用）
        
        Args:
            profile_name: Chromeプロファイル名（例: "Profile 6"）
            
        Returns:
            Chrome WebDriver
            
        Raises:
            TikTokUploadError: プロファイルが使用中または作成失敗
        """
        # 実行前にクリーンアップ
        self._cleanup_chrome_and_locks(profile_name)
        
        try:
            chrome_options = Options()
            
            # プロファイルパスを設定
            profile_path = self.chrome_profile_path / profile_name
            
            # プロファイルの存在確認（より詳細なエラーメッセージ）
            if not self.chrome_profile_path.exists():
                raise TikTokUploadError(
                    f"Chrome user data directory not found: {self.chrome_profile_path}. "
                    f"Please check the path in config/phases/tiktok_upload.yaml"
                )
            
            if not profile_path.exists():
                # 利用可能なプロファイルをリストアップ
                available_profiles = []
                if self.chrome_profile_path.exists():
                    for item in self.chrome_profile_path.iterdir():
                        if item.is_dir() and (item.name.startswith("Profile") or item.name == "Default"):
                            available_profiles.append(item.name)
                
                available_str = ", ".join(available_profiles) if available_profiles else "none found"
                genre_hint = f"config/genres/{self.genre}.yaml" if self.genre else "your genre config file"
                raise TikTokUploadError(
                    f"Chrome profile '{profile_name}' not found at: {profile_path}\n"
                    f"Available profiles: {available_str}\n"
                    f"Please create the profile in Chrome or update the profile_name in {genre_hint}"
                )
            
            # 元のプロファイルを直接使用（コピーしない）
            # これによりTikTokのセッションが維持される
            self.logger.info(f"Using Chrome profile directly: {self.chrome_profile_path / profile_name}")
            
            chrome_options.add_argument(f"--user-data-dir={self.chrome_profile_path}")
            chrome_options.add_argument(f"--profile-directory={profile_name}")
            
            # ヘッドレスモード
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # ウィンドウサイズ
            width, height = map(int, self.window_size.split("x"))
            chrome_options.add_argument(f"--window-size={width},{height}")
            
            # その他のオプション
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # プロファイルロック問題の回避
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # リモートデバッグポートを動的に割り当て（衝突を避ける）
            debug_port = random.randint(9222, 9999)
            chrome_options.add_argument(f"--remote-debugging-port={debug_port}")
            self.logger.debug(f"Using remote debugging port: {debug_port}")
            chrome_options.add_argument("--disable-gpu")
            
            # ドライバーを作成
            self.logger.info("Installing/checking ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            self.logger.info("Creating Chrome WebDriver instance...")
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            self.logger.info(f"Chrome driver created successfully with profile: {profile_name}")
            self.logger.info(f"Driver session ID: {driver.session_id}")
            self.logger.info(f"Initial URL: {driver.current_url}")
            return driver
            
        except WebDriverException as e:
            error_msg = str(e)
            if ("profile" in error_msg.lower() or 
                "already in use" in error_msg.lower() or 
                "instance exited" in error_msg.lower() or
                "session not created" in error_msg.lower()):
                raise TikTokUploadError(
                    f"Failed to create Chrome driver. Profile '{profile_name}' is already in use.\n"
                    f"\n"
                    f"This usually means:\n"
                    f"1. Another Chrome window is using Profile {profile_name}\n"
                    f"2. Chrome did not close properly\n"
                    f"\n"
                    f"Solutions:\n"
                    f"1. Close any Chrome windows using Profile {profile_name}\n"
                    f"2. Run: taskkill /F /IM chrome.exe\n"
                    f"3. Wait a few seconds and try again\n"
                    f"\n"
                    f"Note: Profile {profile_name} should be dedicated to TikTok automation.\n"
                    f"Original error: {error_msg}"
                ) from e
            else:
                raise TikTokUploadError(
                    f"Failed to create Chrome driver: {error_msg}\n"
                    f"Please check:\n"
                    f"1. Chrome is installed\n"
                    f"2. ChromeDriver is compatible with your Chrome version\n"
                    f"3. Profile path is correct: {profile_path}"
                ) from e
    
    def _find_element_with_fallback(
        self,
        selectors: List[str],
        timeout: Optional[int] = None
    ):
        """
        複数のセレクタ候補を試して要素を見つける
        
        Args:
            selectors: セレクタのリスト（XPathまたはCSSセレクタ）
            timeout: タイムアウト（秒）
            
        Returns:
            見つかった要素
            
        Raises:
            TikTokUIChangedError: どのセレクタでも要素が見つからない
        """
        if self.driver is None:
            raise TikTokUIChangedError("Driver is not initialized")
        
        if timeout is None:
            timeout = self.wait_timeout
        
        wait = WebDriverWait(self.driver, timeout)
        
        for selector in selectors:
            try:
                # XPathかCSSセレクタかを判定
                if selector.startswith("//") or selector.startswith("(//"):
                    # XPath
                    element = wait.until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                else:
                    # CSSセレクタ
                    element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                
                self.logger.debug(f"Element found with selector: {selector}")
                return element
                
            except TimeoutException:
                continue
        
        # 全てのセレクタで失敗
        self._save_screenshot("element_not_found")
        raise TikTokUIChangedError(
            f"Could not find element with any selector: {selectors}. "
            f"TikTok UI may have changed. Screenshot saved."
        )
    
    def _save_screenshot(self, prefix: str = "error") -> Path:
        """
        スクリーンショットを保存
        
        Args:
            prefix: ファイル名のプレフィックス
            
        Returns:
            保存されたファイルのパス
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = self.screenshots_dir / f"{prefix}_{timestamp}.png"
        
        if self.driver is None:
            self.logger.warning(f"Cannot save screenshot: driver is not initialized")
            return screenshot_path
        
        try:
            self.driver.save_screenshot(str(screenshot_path))
            self.logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            self.logger.error(f"Failed to save screenshot: {e}")
            return screenshot_path
    
    def upload_video(
        self,
        video_path: Path,
        caption: str,
        profile_name: str,
        privacy_status: str = "public"
    ) -> str:
        """
        動画を1本投稿
        
        Args:
            video_path: 動画ファイルパス
            caption: キャプション
            profile_name: Chromeプロファイル名
            privacy_status: 公開設定
            
        Returns:
            投稿URL（成功時）
            
        Raises:
            TikTokUIChangedError: UI要素が見つからない
            TikTokUploadError: その他のエラー
        """
        if not video_path.exists():
            raise TikTokUploadError(f"Video file not found: {video_path}")
        
        try:
            self.logger.info("=== Starting upload_video ===")
            self.logger.info(f"Video path: {video_path}")
            self.logger.info(f"Caption: {caption[:50]}..." if len(caption) > 50 else f"Caption: {caption}")
            self.logger.info(f"Profile name: {profile_name}")
            self.logger.info(f"Privacy status: {privacy_status}")
            
            # ドライバーを確保（既に存在する場合は再利用、作成済みの場合は再作成しない）
            if self.driver is None or not self._initialized:
                self.logger.warning("Driver not initialized in upload_video, this should not happen!")
                self.logger.info("Attempting to create driver...")
                self._ensure_driver(profile_name)
            else:
                self.logger.info("Driver already initialized, reusing existing driver...")
            
            self.logger.info(f"Driver is ready. Current URL: {self.driver.current_url}")
            
            # アップロードページに移動（2回目以降のクリップの場合）
            current_url = self.driver.current_url
            self.logger.info(f"Current URL before check: {current_url}")
            if "/upload" not in current_url:
                self.logger.info("Not on upload page, navigating to upload page...")
                self.driver.get("https://www.tiktok.com/upload")
                time.sleep(3)
                self.logger.info(f"After navigation, URL: {self.driver.current_url}")
            
            # 1. ファイル選択ボタンを探してクリック
            self.logger.info("Looking for file input...")
            file_input_selectors = self.selectors.get("file_input", ["input[type='file']"])
            self.logger.debug(f"Trying file input selectors: {file_input_selectors}")
            file_input = self._find_element_with_fallback(file_input_selectors)
            self.logger.info(f"Found file input: {file_input}")
            
            # ファイルをアップロード
            video_abs_path = str(video_path.absolute())
            self.logger.info(f"Uploading file: {video_abs_path}")
            self.logger.info(f"File exists: {video_path.exists()}")
            self.logger.info(f"File size: {video_path.stat().st_size / (1024*1024):.2f} MB")
            
            try:
                file_input.send_keys(video_abs_path)
                self.logger.info("Successfully sent file path to input")
            except Exception as e:
                self.logger.error(f"Failed to send file path: {e}", exc_info=True)
                self._save_screenshot("file_input_error")
                raise TikTokUploadError(f"Failed to select file: {e}") from e
            
            # アップロード完了待機（動画がアップロードされるまで待つ）
            self.logger.info("Waiting for video upload to complete...")
            # 動画のアップロード進捗を待機（最大60秒）
            max_wait = 60
            wait_interval = 2
            waited = 0
            while waited < max_wait:
                try:
                    # アップロード完了のサインを探す（例: キャプション入力欄が有効になる）
                    # 実際のTikTokのUIに応じて調整が必要
                    time.sleep(wait_interval)
                    waited += wait_interval
                    self.logger.debug(f"Waiting for upload... ({waited}/{max_wait} seconds)")
                    # 簡易的な待機（実際の実装では、アップロード進捗バーなどを確認）
                    if waited >= 10:  # 最低10秒は待つ
                        self.logger.info(f"Minimum wait time reached ({waited} seconds)")
                        break
                except Exception as e:
                    self.logger.warning(f"Error during wait: {e}")
                    break
            
            # 2. キャプション入力
            self.logger.info("Entering caption...")
            caption_selectors = self.selectors.get("caption_input", ["div[contenteditable='true']"])
            self.logger.debug(f"Trying caption selectors: {caption_selectors}")
            caption_input = self._find_element_with_fallback(caption_selectors)
            self.logger.info(f"Found caption input: {caption_input}")
            
            # contenteditable divの場合、JavaScriptでテキストを設定
            try:
                self.logger.debug("Clearing existing text...")
                # 既存のテキストをクリア
                self.driver.execute_script(
                    "arguments[0].innerText = ''; arguments[0].textContent = '';",
                    caption_input
                )
                self.logger.debug("Setting caption text...")
                # テキストを入力
                self.driver.execute_script(
                    "arguments[0].innerText = arguments[1];",
                    caption_input, caption
                )
                self.logger.debug("Dispatching input event...")
                # 入力イベントを発火
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                    caption_input
                )
                self.logger.info("Caption entered successfully using JavaScript")
            except Exception as e:
                self.logger.warning(f"JavaScript method failed: {e}, trying send_keys...")
                # フォールバック: 通常のsend_keys
                try:
                    caption_input.clear()
                    caption_input.send_keys(caption)
                    self.logger.info("Caption entered successfully using send_keys")
                except Exception as e2:
                    self.logger.error(f"Both methods failed: {e2}", exc_info=True)
                    self._save_screenshot("caption_input_error")
                    raise TikTokUploadError(f"Failed to enter caption: {e2}") from e2
            
            # 3. 公開設定（必要に応じて）
            # 注意: TikTokのUIは複雑で、公開設定のセレクタは環境によって異なる可能性がある
            # ここでは基本的な実装のみ
            
            # 4. 投稿ボタンをクリック
            self.logger.info("Looking for post button...")
            post_button_selectors = self.selectors.get("post_button", [
                "//button[contains(text(), '投稿')]",
                "//button[contains(text(), 'Post')]"
            ])
            self.logger.debug(f"Trying post button selectors: {post_button_selectors}")
            post_button = self._find_element_with_fallback(post_button_selectors)
            self.logger.info(f"Found post button: {post_button}")
            
            # 投稿ボタンをクリック
            self.logger.info("Clicking post button...")
            try:
                post_button.click()
                self.logger.info("Post button clicked successfully")
            except Exception as e:
                self.logger.error(f"Failed to click post button: {e}", exc_info=True)
                self._save_screenshot("post_button_error")
                raise TikTokUploadError(f"Failed to click post button: {e}") from e
            
            # 投稿完了待機
            self.logger.info("Waiting for upload to complete...")
            time.sleep(5)
            self.logger.info(f"After 5 second wait, URL: {self.driver.current_url}")
            
            # 投稿URLを取得（現在のURLから）
            current_url = self.driver.current_url
            self.logger.info(f"Upload completed. Current URL: {current_url}")
            self.logger.info(f"Page title: {self.driver.title}")
            
            # 投稿成功を確認（URLが変わったか、成功メッセージが表示されたか）
            # 注意: TikTokの実際の動作に応じて調整が必要
            
            self.logger.info("=== Completed upload_video ===")
            return current_url
            
        except TikTokUIChangedError:
            # UI変更エラーはそのまま再スロー
            raise
        except Exception as e:
            self._save_screenshot("upload_error")
            raise TikTokUploadError(f"Failed to upload video: {e}") from e
    
    def close(self):
        """
        ドライバーを閉じる（すべてのアップロードが終わったら呼ぶ）
        """
        if self.driver:
            try:
                self.logger.info("Closing Chrome driver...")
                self.driver.quit()
            except Exception as e:
                self.logger.warning(f"Failed to close driver: {e}")
            finally:
                self.driver = None
                self._initialized = False
                self.profile_name = None
    
    def __enter__(self):
        """コンテキストマネージャー対応"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー対応"""
        self.close()

