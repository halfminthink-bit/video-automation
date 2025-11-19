"""
Phase 9: YouTube自動投稿（YouTube Upload）

YouTube Data API v3を使用して動画をアップロードし、
Claude APIで生成したメタデータを設定する
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import os

# プロジェクトルートをパスに追加
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.core.phase_base import PhaseBase
from src.core.config_manager import ConfigManager
from src.core.exceptions import (
    PhaseExecutionError,
    PhaseValidationError,
    PhaseInputMissingError
)
from src.utils.youtube_metadata_generator import YouTubeMetadataGenerator

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


class Phase09YouTube(PhaseBase):
    """Phase 9: YouTube自動投稿"""

    def __init__(self, subject: str, config: ConfigManager, logger: logging.Logger, genre: Optional[str] = None):
        super().__init__(subject, config, logger)
        self.genre = genre

    def get_phase_number(self) -> int:
        return 9

    def get_phase_name(self) -> str:
        return "YouTube Upload"

    def check_inputs_exist(self) -> bool:
        """Phase 7（動画）とPhase 1（台本）の出力を確認"""
        # 最終動画ファイル
        output_dir = self.config.get_path("output_dir")
        video_path = output_dir / "videos" / f"{self.subject}.mp4"

        if not video_path.exists():
            self.logger.error(f"Video file not found: {video_path}")
            return False

        # 台本ファイル
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        if not script_path.exists():
            self.logger.error(f"Script not found: {script_path}")
            return False

        return True

    def check_outputs_exist(self) -> bool:
        """アップロード済みかチェック"""
        upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get("upload_log", "upload_log.json")

        if upload_log_path.exists():
            self.logger.info("Video already uploaded")
            return True

        return False

    def get_output_paths(self) -> list[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / self.phase_config.get("output", {}).get("metadata_file", "metadata.json"),
            self.phase_dir / self.phase_config.get("output", {}).get("upload_log", "upload_log.json")
        ]

    def execute_phase(self) -> Dict[str, Any]:
        """
        YouTube投稿の実行

        Returns:
            投稿結果

        Raises:
            PhaseExecutionError: 実行エラー
        """
        self.logger.info(f"Starting YouTube upload for: {self.subject}")

        try:
            # 1. 入力データを収集
            video_path, script_data, duration = self._load_input_data()

            # 2. メタデータを生成
            metadata = self._generate_metadata(script_data, duration)

            # 3. メタデータを保存
            self._save_metadata(metadata)

            # 4. 手動承認モードの場合、確認を求める
            mode = self.phase_config.get("upload", {}).get("mode", "manual_approval")
            if mode == "manual_approval":
                self.logger.info("Manual approval mode: Please review metadata before upload")
                self.logger.info(f"Title: {metadata['title']}")
                self.logger.info(f"Tags: {', '.join(metadata['tags'])}")

                # メタデータファイルのパスを表示
                metadata_path = self.phase_dir / "metadata.json"
                self.logger.info(f"Metadata saved to: {metadata_path}")
                self.logger.info("To upload, set mode to 'auto' or 'draft' in config and re-run")

                return {
                    "status": "pending_approval",
                    "metadata": metadata,
                    "video_path": str(video_path)
                }

            # 5. YouTube認証
            youtube = self._authenticate_youtube()

            # 6. 動画をアップロード
            video_id = self._upload_video(youtube, video_path, metadata)

            # 7. サムネイルを設定
            thumbnail_path = self._get_thumbnail_path()
            if thumbnail_path:
                self._upload_thumbnail(youtube, video_id, thumbnail_path)

            # 8. 結果を保存
            upload_result = {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "uploaded_at": datetime.now().isoformat(),
                "metadata": metadata,
                "status": "success",
                "privacy_status": metadata.get("privacy_status", "private")
            }

            self._save_upload_log(upload_result)

            self.logger.info(f"Upload successful! Video ID: {video_id}")
            self.logger.info(f"URL: {upload_result['url']}")

            return upload_result

        except Exception as e:
            self.logger.error(f"YouTube upload failed: {e}", exc_info=True)
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"YouTube upload failed: {e}"
            ) from e

    def validate_output(self, output: Dict[str, Any]) -> bool:
        """
        アップロード結果をバリデーション

        Args:
            output: 出力データ

        Returns:
            バリデーション成功なら True

        Raises:
            PhaseValidationError: バリデーション失敗時
        """
        self.logger.info("Validating YouTube upload output...")

        status = output.get("status")

        # 承認待ちの場合は成功とみなす
        if status == "pending_approval":
            self.logger.info("Pending manual approval")
            return True

        # アップロード成功の場合、video_idをチェック
        if status == "success":
            video_id = output.get("video_id")
            if not video_id:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    "Video ID not found in upload result"
                )

            self.logger.info(f"Upload validation passed ✓ (Video ID: {video_id})")
            return True

        raise PhaseValidationError(
            self.get_phase_number(),
            f"Unknown upload status: {status}"
        )

    # ========================================
    # 内部メソッド
    # ========================================

    def _load_input_data(self) -> tuple[Path, Dict[str, Any], float]:
        """
        入力データを読み込み

        Returns:
            (video_path, script_data, duration)
        """
        # 動画ファイル
        output_dir = self.config.get_path("output_dir")
        video_path = output_dir / "videos" / f"{self.subject}.mp4"

        # 台本データ
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        with open(script_path, 'r', encoding='utf-8') as f:
            script_data = json.load(f)

        # 動画の長さを取得（Phase 7のメタデータから）
        phase7_metadata_path = self.config.get_phase_dir(self.subject, 7) / "metadata.json"
        duration = 0.0
        if phase7_metadata_path.exists():
            with open(phase7_metadata_path, 'r', encoding='utf-8') as f:
                phase7_metadata = json.load(f)
                duration = phase7_metadata.get("total_duration", 0.0)

        return video_path, script_data, duration

    def _generate_metadata(
        self,
        script_data: Dict[str, Any],
        duration: float
    ) -> Dict[str, Any]:
        """
        メタデータを生成

        Args:
            script_data: 台本データ
            duration: 動画の長さ

        Returns:
            メタデータ
        """
        metadata_config = self.phase_config.get("metadata_generation", {})

        if not metadata_config.get("enabled", True):
            self.logger.info("Metadata generation disabled, using fallback")
            return self._create_simple_metadata(duration)

        # スクリプト内容を抽出
        script_content = self._extract_script_content(script_data)

        # 画像テーマを抽出（Phase 3から）
        image_themes = self._extract_image_themes()

        # メタデータジェネレーターを作成
        generator = YouTubeMetadataGenerator(
            config=metadata_config,
            logger=self.logger
        )

        # メタデータを生成
        target_audience = metadata_config.get("target_audience", "一般")
        tag_strategy = metadata_config.get("tag_strategy", {})

        metadata = generator.generate_metadata(
            subject=self.subject,
            script_content=script_content,
            image_themes=image_themes,
            duration=duration,
            target_audience=target_audience,
            tag_strategy=tag_strategy
        )

        # 設定ファイルの値で上書き（privacy_status, category_idなど）
        upload_config = self.phase_config.get("upload", {})
        metadata["privacy_status"] = upload_config.get("privacy_status", metadata.get("privacy_status", "private"))
        metadata["category_id"] = upload_config.get("category_id", metadata.get("category_id", "22"))

        return metadata

    def _extract_script_content(self, script_data: Dict[str, Any]) -> str:
        """台本データからテキストを抽出"""
        sections = script_data.get("sections", [])
        content_parts = []

        for section in sections:
            narration = section.get("narration", "")
            content_parts.append(narration)

        return "\n\n".join(content_parts)

    def _extract_image_themes(self) -> str:
        """Phase 3の画像プロンプトを抽出"""
        phase3_metadata_path = self.config.get_phase_dir(self.subject, 3) / "metadata.json"

        if not phase3_metadata_path.exists():
            return "画像テーマ情報なし"

        try:
            with open(phase3_metadata_path, 'r', encoding='utf-8') as f:
                phase3_data = json.load(f)

            images = phase3_data.get("images", [])
            prompts = [img.get("prompt", "") for img in images if img.get("prompt")]

            return "\n".join(prompts[:5])  # 最初の5個まで

        except Exception as e:
            self.logger.warning(f"Failed to extract image themes: {e}")
            return "画像テーマ情報なし"

    def _create_simple_metadata(self, duration: float) -> Dict[str, Any]:
        """シンプルなメタデータを作成"""
        minutes = int(duration / 60)

        upload_config = self.phase_config.get("upload", {})

        return {
            "title": f"{self.subject}の物語【歴史解説】",
            "description": f"{self.subject}について詳しく解説します。\n\n#歴史 #{self.subject}",
            "tags": ["歴史", "偉人", self.subject],
            "category_id": upload_config.get("category_id", "22"),
            "privacy_status": upload_config.get("privacy_status", "private")
        }

    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """メタデータを保存"""
        metadata_path = self.phase_dir / self.phase_config.get("output", {}).get("metadata_file", "metadata.json")

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Metadata saved: {metadata_path}")

    def _authenticate_youtube(self):
        """YouTube認証"""
        # ジャンル指定がある場合はジャンル設定から認証情報を取得
        if self.genre:
            try:
                genre_config = self.config.get_genre_config(self.genre)
                youtube_config = genre_config.get("youtube", {})
                if youtube_config:
                    self.logger.info(f"Using genre-specific YouTube credentials: {self.genre}")
                    credentials_file = self.config.project_root / youtube_config.get("credentials_file")
                    token_file = self.config.project_root / youtube_config.get("token_file")
                    # スコープはフェーズ設定から取得
                    auth_config = self.phase_config.get("authentication", {})
                    scopes = auth_config.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"])
                else:
                    # ジャンル設定にyoutubeセクションがない場合はフォールバック
                    self.logger.warning(f"Genre '{self.genre}' has no youtube config, using default")
                    auth_config = self.phase_config.get("authentication", {})
                    credentials_file = self.config.project_root / auth_config.get("credentials_file")
                    token_file = self.config.project_root / auth_config.get("token_file")
                    scopes = auth_config.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"])
            except Exception as e:
                self.logger.warning(f"Failed to load genre config for '{self.genre}': {e}, using default")
                auth_config = self.phase_config.get("authentication", {})
                credentials_file = self.config.project_root / auth_config.get("credentials_file")
                token_file = self.config.project_root / auth_config.get("token_file")
                scopes = auth_config.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"])
        else:
            # ジャンル指定がない場合はフェーズ設定から取得
            auth_config = self.phase_config.get("authentication", {})
            credentials_file = self.config.project_root / auth_config.get("credentials_file")
            token_file = self.config.project_root / auth_config.get("token_file")
            scopes = auth_config.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"])

        creds = None

        # トークンファイルが存在する場合は読み込み
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), scopes)

        # 認証情報が無効または存在しない場合は再認証
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_file), scopes
                )
                creds = flow.run_local_server(port=0)

            # トークンを保存
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, 'w') as f:
                f.write(creds.to_json())

        # YouTube APIクライアントを作成
        youtube = build('youtube', 'v3', credentials=creds)

        return youtube

    def _upload_video(
        self,
        youtube,
        video_path: Path,
        metadata: Dict[str, Any]
    ) -> str:
        """
        動画をアップロード

        Args:
            youtube: YouTube APIクライアント
            video_path: 動画ファイルのパス
            metadata: メタデータ

        Returns:
            video_id
        """
        self.logger.info(f"Uploading video: {video_path}")

        # リクエストボディを作成
        body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata["tags"],
                "categoryId": metadata["category_id"]
            },
            "status": {
                "privacyStatus": metadata["privacy_status"],
                "selfDeclaredMadeForKids": False
            }
        }

        # メディアファイルを作成
        media = MediaFileUpload(
            str(video_path),
            mimetype='video/mp4',
            resumable=True,
            chunksize=1024*1024  # 1MB
        )

        # アップロードリクエストを実行
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        retry_count = 0
        max_retries = self.phase_config.get("retry", {}).get("max_attempts", 3)

        while response is None and retry_count < max_retries:
            try:
                self.logger.info(f"Upload attempt {retry_count + 1}/{max_retries}")
                status, response = request.next_chunk()

                if status:
                    progress = int(status.progress() * 100)
                    self.logger.info(f"Upload progress: {progress}%")

            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    retry_count += 1
                    self.logger.warning(f"HTTP error {e.resp.status}, retrying...")
                else:
                    raise

        if response is None:
            raise PhaseExecutionError(
                self.get_phase_number(),
                "Upload failed after retries"
            )

        video_id = response['id']
        self.logger.info(f"Upload complete! Video ID: {video_id}")

        return video_id

    def _get_thumbnail_path(self) -> Optional[Path]:
        """サムネイルパスを取得"""
        thumbnail_config = self.phase_config.get("upload", {}).get("thumbnail", {})
        source = thumbnail_config.get("source", "phase8_first")

        # Phase 8のサムネイル
        if source in ["phase8_first", "phase8_best"]:
            phase8_thumbnail_dir = self.config.get_phase_dir(self.subject, 8) / "thumbnails"

            if phase8_thumbnail_dir.exists():
                # PNG、JPG、JPEG すべてを検索
                thumbnails = sorted(
                    list(phase8_thumbnail_dir.glob("*.png")) +
                    list(phase8_thumbnail_dir.glob("*.jpg")) +
                    list(phase8_thumbnail_dir.glob("*.jpeg"))
                )
                if thumbnails:
                    self.logger.info(f"Found thumbnail in phase8/thumbnails: {thumbnails[0].name}")
                    return thumbnails[0]  # 最初のサムネイル

        # Phase 7のサムネイル（フォールバック）
        if thumbnail_config.get("fallback_to_phase7", True):
            phase7_thumbnail = self.config.get_phase_dir(self.subject, 7) / f"{self.subject}_thumbnail.jpg"
            if phase7_thumbnail.exists():
                self.logger.info(f"Using fallback thumbnail from phase7: {phase7_thumbnail.name}")
                return phase7_thumbnail

        self.logger.warning("No thumbnail found")
        return None

    def _upload_thumbnail(
        self,
        youtube,
        video_id: str,
        thumbnail_path: Path
    ) -> None:
        """サムネイルをアップロード"""
        self.logger.info(f"Uploading thumbnail: {thumbnail_path}")

        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path))
            ).execute()

            self.logger.info("Thumbnail upload complete")

        except Exception as e:
            self.logger.error(f"Thumbnail upload failed: {e}")
            # サムネイルのアップロード失敗は致命的ではないので続行

    def _save_upload_log(self, upload_result: Dict[str, Any]) -> None:
        """アップロードログを保存"""
        upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get("upload_log", "upload_log.json")

        with open(upload_log_path, 'w', encoding='utf-8') as f:
            json.dump(upload_result, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Upload log saved: {upload_log_path}")


def main():
    """Phase 9を単体で実行するためのエントリーポイント"""
    import argparse

    parser = argparse.ArgumentParser(description="Phase 9: YouTube Upload")
    parser.add_argument("subject", help="Subject name")
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

    # Phase 9を実行
    phase = Phase09YouTube(
        subject=args.subject,
        config=config,
        logger=logger
    )

    try:
        result = phase.run(skip_if_exists=not args.force)
        logger.info(f"Phase 9 completed successfully")

        if result.status.value == "completed":
            logger.info("Upload status: Success")

    except Exception as e:
        logger.error(f"Phase 9 failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
