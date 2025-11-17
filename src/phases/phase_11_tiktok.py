"""
Phase 11: TikTok 自動投稿

Phase 10で生成された縦型動画をTikTokに投稿する。
Selenium + Cookie認証方式でBot検知を回避。
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from src.core.phase_base import PhaseBase
from src.core.config_manager import ConfigManager
from src.core.exceptions import PhaseExecutionError
from src.utils.tiktok_uploader import TikTokUploader


class Phase11TikTok(PhaseBase):
    """Phase 11: TikTok自動投稿"""

    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger: logging.Logger,
        genre: Optional[str] = None
    ):
        super().__init__(subject, config, logger)
        self.genre = genre

    def get_phase_number(self) -> int:
        return 11

    def get_phase_name(self) -> str:
        return "TikTok Upload"

    def check_inputs_exist(self) -> bool:
        """Phase 10のverticalディレクトリを確認"""
        # Phase 10のverticalディレクトリ
        phase10_dir = self.config.get_phase_dir(self.subject, 10)
        vertical_dir = phase10_dir / "vertical"

        if not vertical_dir.exists():
            self.logger.error(f"Phase 10 vertical directory not found: {vertical_dir}")
            self.logger.error("Please run Phase 10 first to generate vertical videos")
            return False

        # 動画ファイルの存在確認
        video_files = list(vertical_dir.glob("vertical_*.mp4"))
        if not video_files:
            self.logger.error(f"No vertical videos found in: {vertical_dir}")
            return False

        self.logger.info(f"Found {len(video_files)} vertical videos")
        return True

    def check_outputs_exist(self) -> bool:
        """アップロード済みかチェック"""
        upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get("upload_log", "tiktok_upload_log.json")

        if upload_log_path.exists():
            self.logger.info("TikTok videos already uploaded")
            return True

        return False

    def get_output_paths(self) -> List[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / self.phase_config.get("output", {}).get("upload_log", "tiktok_upload_log.json")
        ]

    def execute_phase(self) -> Dict[str, Any]:
        """
        TikTok投稿の実行フロー

        1. Phase 10のvertical動画を取得
        2. ジャンル別のCookie認証を取得
        3. メタデータを生成（ジャンル別ハッシュタグ）
        4. 各クリップを連続投稿
        5. 結果をログに保存
        """
        self.logger.info(f"Starting TikTok upload for: {self.subject}")

        try:
            # 1. Phase 10のvertical動画を取得
            phase10_dir = self.config.get_phase_dir(self.subject, 10)
            vertical_dir = phase10_dir / "vertical"
            video_files = sorted(vertical_dir.glob("vertical_*.mp4"))

            # 最大クリップ数を取得
            upload_config = self.phase_config.get("upload", {})
            max_clips = upload_config.get("max_clips", 5)
            video_files = video_files[:max_clips]

            if not video_files:
                raise PhaseExecutionError(11, "No vertical videos found")

            self.logger.info(f"Will upload {len(video_files)} clips to TikTok")

            # 2. ジャンル別のCookieファイルを取得
            cookies_file = self._get_cookies_file()

            # 3. メタデータ設定を取得（ジャンル別）
            metadata_config = self._get_metadata_config()

            # 4. ヘッドレスモード設定
            headless = upload_config.get("headless", False)
            self.logger.info(f"Headless mode: {headless}")

            # 5. 各クリップを投稿
            upload_results = []

            # TikTokUploaderを初期化
            with TikTokUploader(
                cookies_file=cookies_file,
                headless=headless,
                logger=self.logger
            ) as uploader:
                
                for i, video_file in enumerate(video_files, start=1):
                    self.logger.info(f"Uploading TikTok clip #{i}/{len(video_files)}...")

                    # メタデータ生成
                    metadata = self._generate_metadata(
                        clip_number=i,
                        total_clips=len(video_files),
                        config=metadata_config
                    )

                    # TikTok投稿
                    try:
                        result = uploader.upload_video(
                            video_path=video_file,
                            caption=metadata["caption"],
                            wait_after_upload=upload_config.get("wait_after_upload", 10)
                        )

                        upload_result = {
                            "clip_number": i,
                            "video_file": video_file.name,
                            "caption": metadata["caption"],
                            "status": "success",
                            "uploaded_at": datetime.now().isoformat()
                        }

                        self.logger.info(f"✓ Clip #{i} uploaded successfully")

                    except Exception as e:
                        self.logger.error(f"✗ Failed to upload clip #{i}: {e}")
                        upload_result = {
                            "clip_number": i,
                            "video_file": video_file.name,
                            "status": "failed",
                            "error": str(e)
                        }

                    upload_results.append(upload_result)
                    
                    # クリップ間の待機時間
                    if i < len(video_files):
                        wait_between = upload_config.get("wait_between_uploads", 30)
                        self.logger.info(f"Waiting {wait_between} seconds before next upload...")
                        import time
                        time.sleep(wait_between)

            # 6. 結果をログに保存
            upload_log = {
                "subject": self.subject,
                "genre": self.genre,
                "uploaded_at": datetime.now().isoformat(),
                "total_clips": len(video_files),
                "clips": upload_results
            }

            self._save_upload_log(upload_log)

            # 成功数をカウント
            success_count = sum(1 for r in upload_results if r.get("status") == "success")

            self.logger.info(f"✅ TikTok upload completed: {success_count}/{len(video_files)} successful")

            return upload_log

        except Exception as e:
            self.logger.error(f"TikTok upload failed: {e}", exc_info=True)
            raise PhaseExecutionError(11, f"TikTok upload failed: {e}") from e

    def _get_cookies_file(self) -> Path:
        """
        ジャンル別のCookieファイルを取得

        Returns:
            Cookieファイルのパス
        """
        auth_config = self.phase_config.get("authentication", {})

        # ジャンル別のCookieファイルを取得
        if self.genre:
            try:
                genre_config = self.config.get_genre_config(self.genre)
                tiktok_config = genre_config.get("tiktok", {})

                if tiktok_config and "cookies_file" in tiktok_config:
                    self.logger.info(f"Using genre-specific TikTok cookies: {self.genre}")
                    cookies_file = self.config.project_root / tiktok_config.get("cookies_file")
                else:
                    self.logger.warning(f"Genre '{self.genre}' has no tiktok config, using default")
                    cookies_file = self.config.project_root / auth_config.get("cookies_file")

            except Exception as e:
                self.logger.warning(f"Failed to load genre config for '{self.genre}': {e}, using default")
                cookies_file = self.config.project_root / auth_config.get("cookies_file")
        else:
            # デフォルトのCookieファイル
            cookies_file = self.config.project_root / auth_config.get("cookies_file")

        if not cookies_file.exists():
            raise PhaseExecutionError(
                11,
                f"TikTok cookies file not found: {cookies_file}\n"
                f"Please run the login script first:\n"
                f"python -m src.utils.tiktok_uploader --login --cookies {cookies_file}"
            )

        self.logger.info(f"Using cookies file: {cookies_file}")

        return cookies_file

    def _get_metadata_config(self) -> Dict[str, Any]:
        """
        ジャンル別のメタデータ設定を取得

        Returns:
            メタデータ設定（ハッシュタグなど）
        """
        metadata_config = self.phase_config.get("metadata_generation", {})

        # ジャンル別のハッシュタグを取得
        if self.genre:
            try:
                genre_config = self.config.get_genre_config(self.genre)
                tiktok_config = genre_config.get("tiktok", {})

                if tiktok_config and "hashtags" in tiktok_config:
                    # ジャンル別のハッシュタグで上書き
                    metadata_config["hashtags"] = tiktok_config["hashtags"]
                    self.logger.info(f"Using genre-specific hashtags: {tiktok_config['hashtags']}")

            except Exception as e:
                self.logger.warning(f"Failed to load genre-specific hashtags: {e}")

        return metadata_config

    def _generate_metadata(
        self,
        clip_number: int,
        total_clips: int,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        TikTok用メタデータを生成

        Args:
            clip_number: クリップ番号
            total_clips: 総クリップ数
            config: メタデータ設定

        Returns:
            {
                "caption": "説明文 #hashtag1 #hashtag2"
            }
        """
        # タイトルテンプレート
        title_template = config.get("title_template", "{subject} #{clip_number}")
        title = title_template.format(
            subject=self.subject,
            clip_number=clip_number
        )

        # ハッシュタグ
        hashtags = config.get("hashtags", ["歴史", "解説"])
        hashtag_str = " ".join([f"#{tag}" for tag in hashtags])

        # キャプション（TikTokではタイトルと説明文が統合）
        caption = f"{title} {hashtag_str}"

        return {
            "caption": caption
        }

    def _save_upload_log(self, upload_log: Dict[str, Any]) -> None:
        """アップロードログを保存"""
        upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get("upload_log", "tiktok_upload_log.json")

        with open(upload_log_path, 'w', encoding='utf-8') as f:
            json.dump(upload_log, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Upload log saved: {upload_log_path}")

    def validate_output(self, output: Dict[str, Any]) -> bool:
        """アップロード結果をバリデーション"""
        self.logger.info("Validating TikTok upload output...")

        clips = output.get("clips", [])
        if not clips:
            raise ValueError("No clips in output")

        success_count = sum(1 for c in clips if c.get("status") == "success")

        if success_count > 0:
            self.logger.info(f"Upload validation passed ✓ ({success_count}/{len(clips)} successful)")
            return True
        else:
            self.logger.error("All uploads failed")
            return False


def main():
    """Phase 11を単体で実行するためのエントリーポイント"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Phase 11: TikTok Upload")
    parser.add_argument("subject", help="Subject name")
    parser.add_argument("--genre", help="Genre (ijin/urban)")
    parser.add_argument("--force", action="store_true", help="Force re-upload")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # ロガー設定
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # 設定マネージャーを作成
    config = ConfigManager(env_override=True)

    # Phase 11を実行
    phase = Phase11TikTok(
        subject=args.subject,
        config=config,
        logger=logger,
        genre=args.genre
    )

    try:
        result = phase.run(skip_if_exists=not args.force)
        logger.info("Phase 11 completed successfully")

        if result.status.value == "completed":
            logger.info("Upload status: Success")

    except Exception as e:
        logger.error(f"Phase 11 failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
