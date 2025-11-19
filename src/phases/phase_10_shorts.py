"""
Phase 10: YouTube Shorts 自動投稿

Phase 7で生成された動画を60秒ごとに分割し、
縦型に変換してYouTube Shortsとして投稿する。
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time

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
from src.utils.video_splitter import VideoSplitter
from src.utils.aspect_ratio_converter import AspectRatioConverter
from src.generators.shorts_metadata_generator import ShortsMetadataGenerator

# YouTube API関連（Phase 9から流用）
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


class Phase10Shorts(PhaseBase):
    """Phase 10: YouTube Shorts自動投稿"""

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
        return 10

    def get_phase_name(self) -> str:
        return "YouTube Shorts Upload"

    def check_inputs_exist(self) -> bool:
        """Phase 7の動画とPhase 9のアップロードログを確認"""
        # Phase 7の動画ファイル
        output_dir = self.config.get_path("output_dir")
        video_path = output_dir / "videos" / f"{self.subject}.mp4"

        if not video_path.exists():
            self.logger.error(f"Video file not found: {video_path}")
            return False

        # Phase 9のアップロードログ
        phase9_upload_log = self.config.get_phase_dir(self.subject, 9) / "upload_log.json"
        if not phase9_upload_log.exists():
            self.logger.error(f"Phase 9 upload log not found: {phase9_upload_log}")
            return False

        return True

    def check_outputs_exist(self) -> bool:
        """アップロード済みかチェック"""
        upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get(
            "upload_log", "shorts_upload_log.json"
        )

        if upload_log_path.exists():
            self.logger.info("Shorts already uploaded")
            return True

        return False

    def get_output_paths(self) -> List[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / self.phase_config.get("output", {}).get(
                "upload_log", "shorts_upload_log.json"
            )
        ]

    def execute_phase(self) -> Dict[str, Any]:
        """
        Shorts投稿の実行フロー:

        1. Phase 7の動画を取得
        2. VideoSplitterで60秒ごとに分割（最初の5個）
        3. AspectRatioConverterで各クリップを縦型に変換
        4. Phase 9のログから本編URLを取得
        5. ShortsMetadataGeneratorでメタデータ生成
        6. YouTube APIで各クリップを連続投稿
        7. 結果をログに保存
        """
        self.logger.info(f"Starting YouTube Shorts upload for: {self.subject}")

        try:
            # 1. Phase 7の動画を取得
            output_dir = self.config.get_path("output_dir")
            video_path = output_dir / "videos" / f"{self.subject}.mp4"

            # 2. 動画を分割
            clips = self._split_video(video_path)

            # 3. 各クリップを縦型に変換
            vertical_clips = self._convert_to_vertical(clips)

            # 4. Phase 9のログから本編URLと本編メタデータを取得
            main_video_url, original_metadata = self._get_main_video_info()

            # 5. 手動承認モードの場合、確認を求める
            mode = self.phase_config.get("upload", {}).get("mode", "auto")
            if mode == "manual_approval":
                self.logger.info("Manual approval mode: Please review before upload")
                self.logger.info(f"Main video URL: {main_video_url}")
                self.logger.info(f"Clips to upload: {len(vertical_clips)}")

                return {
                    "status": "pending_approval",
                    "clips_count": len(vertical_clips),
                    "main_video_url": main_video_url
                }

            # 6. YouTube認証
            youtube = self._authenticate_youtube()

            # 7. 各クリップをアップロード
            upload_results = self._upload_all_clips(
                youtube=youtube,
                clips=vertical_clips,
                main_video_url=main_video_url,
                original_metadata=original_metadata
            )

            # 8. 結果を保存
            result = {
                "subject": self.subject,
                "uploaded_at": datetime.now().isoformat(),
                "main_video_url": main_video_url,
                "clips": upload_results,
                "status": "success"
            }

            self._save_upload_log(result)

            self.logger.info(f"Shorts upload completed! {len(upload_results)} clips uploaded")
            for clip_result in upload_results:
                self.logger.info(f"  - {clip_result['title']}: {clip_result['url']}")

            return result

        except Exception as e:
            self.logger.error(f"Shorts upload failed: {e}", exc_info=True)
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Shorts upload failed: {e}"
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
        self.logger.info("Validating Shorts upload output...")

        status = output.get("status")

        # 承認待ちの場合は成功とみなす
        if status == "pending_approval":
            self.logger.info("Pending manual approval")
            return True

        # アップロード成功の場合、clipsをチェック
        if status == "success":
            clips = output.get("clips", [])
            if not clips:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    "No clips uploaded"
                )

            # 成功したクリップをカウント
            successful_clips = [clip for clip in clips if clip.get("video_id")]
            failed_clips = [clip for clip in clips if not clip.get("video_id")]

            # 少なくとも1つ以上のクリップが成功していればOK
            if len(successful_clips) == 0:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    "No clips uploaded successfully"
                )

            # 失敗したクリップがある場合は警告
            if failed_clips:
                failed_numbers = [c.get("clip_number") for c in failed_clips]
                self.logger.warning(
                    f"Some clips failed to upload: {failed_numbers}. "
                    f"Successful: {len(successful_clips)}/{len(clips)}"
                )

            self.logger.info(
                f"Upload validation passed ✓ "
                f"({len(successful_clips)}/{len(clips)} clips successful)"
            )
            return True

        raise PhaseValidationError(
            self.get_phase_number(),
            f"Unknown upload status: {status}"
        )

    # ========================================
    # 内部メソッド
    # ========================================

    def _split_video(self, video_path: Path) -> List[Path]:
        """
        動画を60秒ごとに分割

        Args:
            video_path: 入力動画のパス

        Returns:
            分割されたクリップのパスリスト
        """
        split_config = self.phase_config.get("video_split", {})
        segment_duration = split_config.get("segment_duration", 60)
        max_clips = split_config.get("max_clips", 5)
        prefix = split_config.get("output_prefix", "short")

        # 出力ディレクトリ
        output_config = self.phase_config.get("output", {})
        clips_dir = self.phase_dir / output_config.get("clips_dir", "clips")

        # VideoSplitterで分割
        splitter = VideoSplitter(logger=self.logger)
        clips = splitter.split_video(
            input_path=video_path,
            output_dir=clips_dir,
            segment_duration=segment_duration,
            max_segments=max_clips,
            prefix=prefix
        )

        return clips

    def _convert_to_vertical(self, clips: List[Path]) -> List[Path]:
        """
        各クリップを縦型に変換

        Args:
            clips: 横型クリップのパスリスト

        Returns:
            縦型クリップのパスリスト
        """
        aspect_config = self.phase_config.get("aspect_ratio", {})
        target_width = aspect_config.get("target_width", 1080)
        target_height = aspect_config.get("target_height", 1920)
        # modeパラメータを取得（デフォルト: blur_bg）
        # crop_modeは後方互換性のため残すが、非推奨
        mode = aspect_config.get("mode", aspect_config.get("crop_mode", "blur_bg"))
        if aspect_config.get("crop_mode") and not aspect_config.get("mode"):
            self.logger.warning("aspect_ratio.crop_mode is deprecated, use aspect_ratio.mode instead")
            # crop_modeが指定されていて、modeが指定されていない場合はcropに変換
            if aspect_config.get("crop_mode") in ["center", "top", "bottom"]:
                mode = "crop"

        # 出力ディレクトリ
        output_config = self.phase_config.get("output", {})
        vertical_dir = self.phase_dir / output_config.get("vertical_dir", "vertical")

        # AspectRatioConverterで変換
        converter = AspectRatioConverter(logger=self.logger)
        vertical_clips = []

        for i, clip in enumerate(clips, 1):
            output_path = vertical_dir / f"vertical_{i:03d}.mp4"

            self.logger.info(f"Converting clip {i}/{len(clips)} to vertical (mode={mode})...")

            converted = converter.convert_to_vertical(
                input_path=clip,
                output_path=output_path,
                target_width=target_width,
                target_height=target_height,
                mode=mode
            )

            vertical_clips.append(converted)

        return vertical_clips

    def _get_main_video_info(self) -> tuple[str, Dict[str, Any]]:
        """
        Phase 9のログから本編URLと本編メタデータを取得

        Returns:
            (main_video_url, original_metadata)
        """
        phase9_upload_log = self.config.get_phase_dir(self.subject, 9) / "upload_log.json"

        with open(phase9_upload_log, 'r', encoding='utf-8') as f:
            phase9_data = json.load(f)

        main_video_url = phase9_data.get("url", "")
        original_metadata = phase9_data.get("metadata", {})

        self.logger.info(f"Main video URL: {main_video_url}")

        return main_video_url, original_metadata

    def _authenticate_youtube(self):
        """YouTube認証（Phase 9から流用）"""
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

    def _upload_all_clips(
        self,
        youtube,
        clips: List[Path],
        main_video_url: str,
        original_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        全クリップをアップロード

        Args:
            youtube: YouTube APIクライアント
            clips: 縦型クリップのパスリスト
            main_video_url: 本編URL
            original_metadata: 本編のメタデータ

        Returns:
            アップロード結果のリスト
        """
        metadata_config = self.phase_config.get("metadata_generation", {})
        upload_config = self.phase_config.get("upload", {})

        # Claude APIキーを取得
        try:
            api_key = self.config.get_api_key("CLAUDE_API_KEY")
        except Exception as e:
            self.logger.error(f"Failed to get Claude API key: {e}")
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Claude API key is required for metadata generation"
            ) from e

        # メタデータジェネレーターを作成
        generator = ShortsMetadataGenerator(
            api_key=api_key,
            model=metadata_config.get("model", "claude-haiku-4-5"),
            logger=self.logger
        )

        upload_results = []
        total_clips = len(clips)

        for i, clip_path in enumerate(clips, 1):
            try:
                self.logger.info(f"Uploading clip {i}/{total_clips}...")

                # メタデータを生成（configにmax_tokensとtemperatureを含める）
                metadata = generator.generate_metadata(
                    subject=self.subject,
                    original_title=original_metadata.get("title", f"{self.subject}の物語"),
                    original_description=original_metadata.get("description", ""),
                    clip_number=i,
                    total_clips=total_clips,
                    main_video_url=main_video_url,
                    config={
                        **metadata_config,
                        "max_tokens": metadata_config.get("max_tokens", 2000),
                        "temperature": metadata_config.get("temperature", 0.7)
                    }
                )

                # アップロード
                video_id = self._upload_single_clip(
                    youtube=youtube,
                    clip_path=clip_path,
                    metadata=metadata,
                    privacy_status=upload_config.get("privacy_status", "public"),
                    category_id=upload_config.get("category_id", "22")
                )

                # 結果を記録
                upload_results.append({
                    "clip_number": i,
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/shorts/{video_id}",
                    "title": metadata["title"],
                    "status": "success"
                })

                self.logger.info(f"Clip {i} uploaded successfully: {video_id}")

                # API制限を考慮して少し待機
                if i < total_clips:
                    time.sleep(2)

            except Exception as e:
                self.logger.error(f"Failed to upload clip {i}: {e}")
                # エラーでも可能な限り続行
                upload_results.append({
                    "clip_number": i,
                    "video_id": None,
                    "url": None,
                    "title": f"Clip {i}",
                    "status": "failed",
                    "error": str(e)
                })

        return upload_results

    def _upload_single_clip(
        self,
        youtube,
        clip_path: Path,
        metadata: Dict[str, Any],
        privacy_status: str,
        category_id: str
    ) -> str:
        """
        1つのクリップをアップロード

        Args:
            youtube: YouTube APIクライアント
            clip_path: クリップのパス
            metadata: メタデータ
            privacy_status: 公開設定
            category_id: カテゴリID

        Returns:
            video_id
        """
        # リクエストボディを作成
        body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata["tags"],
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        # メディアファイルを作成
        media = MediaFileUpload(
            str(clip_path),
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
                status, response = request.next_chunk()

                if status:
                    progress = int(status.progress() * 100)
                    self.logger.debug(f"Upload progress: {progress}%")

            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    retry_count += 1
                    self.logger.warning(f"HTTP error {e.resp.status}, retrying...")
                    time.sleep(5)
                else:
                    raise

        if response is None:
            raise PhaseExecutionError(
                self.get_phase_number(),
                "Upload failed after retries"
            )

        video_id = response['id']
        return video_id

    def _save_upload_log(self, result: Dict[str, Any]) -> None:
        """アップロードログを保存"""
        upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get(
            "upload_log", "shorts_upload_log.json"
        )

        with open(upload_log_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Upload log saved: {upload_log_path}")


def main():
    """Phase 10を単体で実行するためのエントリーポイント"""
    import argparse

    parser = argparse.ArgumentParser(description="Phase 10: YouTube Shorts Upload")
    parser.add_argument("subject", help="Subject name")
    parser.add_argument("--force", action="store_true", help="Force re-upload")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--genre", help="Genre name (optional)")

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

    # Phase 10を実行
    phase = Phase10Shorts(
        subject=args.subject,
        config=config,
        logger=logger,
        genre=args.genre
    )

    try:
        result = phase.run(skip_if_exists=not args.force)
        logger.info(f"Phase 10 completed successfully")

        if result.status.value == "completed":
            logger.info("Shorts upload status: Success")

    except Exception as e:
        logger.error(f"Phase 10 failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
