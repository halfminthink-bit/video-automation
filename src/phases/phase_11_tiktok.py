"""
Phase 11: TikTok自動投稿

Phase 10で生成された縦長動画をTikTokに自動投稿する。
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
from src.utils.tiktok_uploader import (
    TikTokUploader,
    TikTokUIChangedError,
    TikTokUploadError
)


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
        """
        Phase 10の縦長動画の存在を確認
        - phase_10/vertical/*.mp4
        - phase_1/script.json（subjectとtitle取得用）
        """
        # Phase 10の縦長動画ディレクトリ
        phase10_dir = self.config.get_phase_dir(self.subject, 10)
        vertical_dir = phase10_dir / "vertical"
        
        if not vertical_dir.exists():
            self.logger.error(f"Phase 10 vertical directory not found: {vertical_dir}")
            return False
        
        # 縦長動画ファイルを検索
        vertical_videos = list(vertical_dir.glob("*.mp4"))
        if not vertical_videos:
            self.logger.error(f"No vertical videos found in: {vertical_dir}")
            return False
        
        self.logger.info(f"Found {len(vertical_videos)} vertical videos")
        
        # Phase 1のscript.json（オプショナル、subjectとtitle取得用）
        phase1_dir = self.config.get_phase_dir(self.subject, 1)
        script_path = phase1_dir / "script.json"
        if not script_path.exists():
            self.logger.warning(f"Script file not found: {script_path} (optional)")
        
        return True
    
    def check_outputs_exist(self) -> bool:
        """
        投稿済みかチェック
        - tiktok_upload_log.json の存在確認
        """
        upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get(
            "upload_log", "tiktok_upload_log.json"
        )
        
        if upload_log_path.exists():
            # ログファイルを読み込んで、全てのクリップが投稿済みか確認
            try:
                with open(upload_log_path, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                
                clips = log_data.get("clips", [])
                if clips:
                    successful_clips = [c for c in clips if c.get("status") == "success"]
                    if len(successful_clips) > 0:
                        self.logger.info(
                            f"TikTok upload already completed: "
                            f"{len(successful_clips)}/{len(clips)} clips uploaded"
                        )
                        return True
            except Exception as e:
                self.logger.warning(f"Failed to read upload log: {e}")
        
        return False
    
    def get_output_paths(self) -> List[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / self.phase_config.get("output", {}).get(
                "upload_log", "tiktok_upload_log.json"
            )
        ]
    
    def execute_phase(self) -> Dict[str, Any]:
        """
        TikTok投稿の実行
        
        処理フロー:
        1. Phase 10の縦長動画を読み込み
        2. ジャンル設定からTikTok設定を取得
        3. Phase 1のscript.jsonからsubjectとtitleを取得
        4. 各クリップについて:
           - キャプション生成（テンプレート置換）
           - TikTokUploaderで投稿
           - 投稿結果をログに記録
        5. 全体の投稿結果を保存
        """
        self.logger.info(f"Starting TikTok upload for: {self.subject}")
        
        try:
            # 1. Phase 10の縦長動画を取得
            phase10_dir = self.config.get_phase_dir(self.subject, 10)
            vertical_dir = phase10_dir / "vertical"
            vertical_videos = sorted(vertical_dir.glob("*.mp4"))
            
            if not vertical_videos:
                raise PhaseExecutionError(
                    self.get_phase_number(),
                    f"No vertical videos found in: {vertical_dir}"
                )
            
            self.logger.info(f"Found {len(vertical_videos)} vertical videos to upload")
            
            # 2. ジャンル設定からTikTok設定を取得
            if not self.genre:
                raise PhaseExecutionError(
                    self.get_phase_number(),
                    "Genre is required for TikTok upload"
                )
            
            genre_config = self.config.get_genre_config(self.genre)
            tiktok_config = genre_config.get("tiktok", {})
            
            if not tiktok_config:
                raise PhaseExecutionError(
                    self.get_phase_number(),
                    f"TikTok config not found in genre: {self.genre}"
                )
            
            profile_name = tiktok_config.get("profile_name")
            caption_template = tiktok_config.get("caption_template", "{subject} ({clip_number}/{total_clips})")
            hashtags = tiktok_config.get("hashtags", [])
            
            if not profile_name:
                raise PhaseExecutionError(
                    self.get_phase_number(),
                    f"profile_name not found in TikTok config for genre: {self.genre}"
                )
            
            # 3. Phase 1のscript.jsonからsubjectとtitleを取得
            subject_name = self.subject
            title = self.subject  # デフォルトはsubject名
            
            phase1_dir = self.config.get_phase_dir(self.subject, 1)
            script_path = phase1_dir / "script.json"
            if script_path.exists():
                try:
                    with open(script_path, 'r', encoding='utf-8') as f:
                        script_data = json.load(f)
                    subject_name = script_data.get("subject", self.subject)
                    title = script_data.get("title", self.subject)
                except Exception as e:
                    self.logger.warning(f"Failed to read script.json: {e}, using defaults")
            
            # 4. TikTokUploaderを作成（全クリップで1つのドライバーを再利用）
            uploader = TikTokUploader(
                config=self.phase_config,
                logger=self.logger,
                genre=self.genre
            )
            
            # 5. ブラウザを最初に1回だけ作成
            self.logger.info(f"Initializing browser with profile: {profile_name}")
            try:
                uploader._ensure_browser(profile_name)
                self.logger.info("Browser initialized successfully")
            except TikTokUploadError as e:
                self.logger.error(f"Failed to initialize browser: {e}")
                raise PhaseExecutionError(
                    self.get_phase_number(),
                    f"Failed to initialize browser. "
                    f"Please check the configuration and ensure {profile_name} is available. Error: {e}"
                )
            except Exception as e:
                self.logger.error(f"Unexpected error initializing browser: {e}", exc_info=True)
                raise PhaseExecutionError(
                    self.get_phase_number(),
                    f"Unexpected error initializing browser: {e}"
                ) from e
            
            # 6. 既存のログを読み込み（再実行時のスキップ判定用）
            upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get(
                "upload_log", "tiktok_upload_log.json"
            )
            uploaded_clips = {}
            if upload_log_path.exists():
                try:
                    with open(upload_log_path, 'r', encoding='utf-8') as f:
                        existing_log = json.load(f)
                    clips = existing_log.get("clips", [])
                    for clip in clips:
                        if clip.get("status") == "success":
                            filename = clip.get("filename")
                            if filename:
                                uploaded_clips[filename] = clip
                except Exception as e:
                    self.logger.warning(f"Failed to read existing log: {e}")
            
            # 7. 各クリップをアップロード
            upload_config = self.phase_config.get("upload", {})
            interval = upload_config.get("interval_between_clips", 10)
            privacy_status = upload_config.get("privacy_status", "public")
            
            upload_results = []
            total_clips = len(vertical_videos)
            
            for i, video_path in enumerate(vertical_videos, 1):
                filename = video_path.name
                
                # 既に投稿済みの場合はスキップ
                if filename in uploaded_clips:
                    self.logger.info(f"Skipping already uploaded clip: {filename}")
                    upload_results.append(uploaded_clips[filename])
                    continue
                
                try:
                    self.logger.info(f"Uploading clip {i}/{total_clips}: {filename}")
                    
                    # キャプションを生成
                    caption = self._generate_caption(
                        caption_template=caption_template,
                        subject=subject_name,
                        clip_number=i,
                        total_clips=total_clips,
                        hashtags=hashtags
                    )
                    
                    # アップロード（ドライバーは既に作成済みなので再利用）
                    upload_url = uploader.upload_video(
                        video_path=video_path,
                        caption=caption,
                        profile_name=profile_name,  # 既存のドライバーを使うだけ
                        privacy_status=privacy_status
                    )
                    
                    # 結果を記録
                    upload_results.append({
                        "filename": filename,
                        "status": "success",
                        "url": upload_url,
                        "caption": caption,
                        "uploaded_at": datetime.now().isoformat()
                    })
                    
                    self.logger.info(f"Clip {i} uploaded successfully: {upload_url}")
                    
                    # 投稿間隔を空ける
                    if i < total_clips:
                        self.logger.info(f"Waiting {interval} seconds before next upload...")
                        time.sleep(interval)
                
                except TikTokUIChangedError as e:
                    # UI変更エラーは即座に停止
                    self.logger.error(f"TikTok UI changed: {e}")
                    upload_results.append({
                        "filename": filename,
                        "status": "failed",
                        "error": str(e),
                        "error_type": "ui_changed"
                    })
                    raise  # UI変更は致命的なので停止
                
                except Exception as e:
                    # その他のエラーは記録して続行
                    self.logger.error(f"Failed to upload clip {i}: {e}")
                    upload_results.append({
                        "filename": filename,
                        "status": "failed",
                        "error": str(e),
                        "error_type": type(e).__name__
                    })
                    # エラーでも次のクリップを試す（UI変更以外）
                    continue
            
            # 8. ドライバーを閉じる
            try:
                uploader.close()
            except Exception as e:
                self.logger.warning(f"Failed to close uploader: {e}")
            
            # 9. 結果を保存
            result = {
                "subject": self.subject,
                "genre": self.genre,
                "uploaded_at": datetime.now().isoformat(),
                "clips": upload_results,
                "summary": {
                    "total_clips": total_clips,
                    "success": len([c for c in upload_results if c.get("status") == "success"]),
                    "failed": len([c for c in upload_results if c.get("status") == "failed"])
                }
            }
            
            self._save_upload_log(result)
            
            self.logger.info(
                f"TikTok upload completed! "
                f"{result['summary']['success']}/{total_clips} clips uploaded"
            )
            
            return result
        
        except Exception as e:
            # エラーが発生してもドライバーを閉じる
            try:
                if 'uploader' in locals():
                    uploader.close()
            except Exception as close_error:
                self.logger.warning(f"Failed to close uploader on error: {close_error}")
            
            self.logger.error(f"TikTok upload failed: {e}", exc_info=True)
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"TikTok upload failed: {e}"
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
        self.logger.info("Validating TikTok upload output...")
        
        summary = output.get("summary", {})
        total_clips = summary.get("total_clips", 0)
        success_count = summary.get("success", 0)
        failed_count = summary.get("failed", 0)
        
        # 少なくとも1つ以上のクリップが成功していればOK
        if success_count == 0:
            raise PhaseValidationError(
                self.get_phase_number(),
                "No clips uploaded successfully"
            )
        
        # 失敗したクリップがある場合は警告
        if failed_count > 0:
            self.logger.warning(
                f"Some clips failed to upload: {failed_count}/{total_clips}. "
                f"Successful: {success_count}/{total_clips}"
            )
        
        self.logger.info(
            f"Upload validation passed ✓ "
            f"({success_count}/{total_clips} clips successful)"
        )
        return True
    
    # ========================================
    # 内部メソッド
    # ========================================
    
    def _generate_caption(
        self,
        caption_template: str,
        subject: str,
        clip_number: int,
        total_clips: int,
        hashtags: List[str]
    ) -> str:
        """
        キャプションを生成（テンプレート置換）
        
        Args:
            caption_template: キャプションテンプレート
            subject: 偉人名
            clip_number: クリップ番号
            total_clips: 総クリップ数
            hashtags: ハッシュタグリスト
            
        Returns:
            生成されたキャプション
        """
        # テンプレート置換
        caption = caption_template.format(
            subject=subject,
            clip_number=clip_number,
            total_clips=total_clips
        )
        
        # ハッシュタグを追加（テンプレートに含まれていない場合）
        if hashtags:
            hashtag_str = " " + " ".join([f"#{tag}" for tag in hashtags])
            if hashtag_str not in caption:
                caption += hashtag_str
        
        return caption
    
    def _save_upload_log(self, result: Dict[str, Any]) -> None:
        """アップロードログを保存"""
        upload_log_path = self.phase_dir / self.phase_config.get("output", {}).get(
            "upload_log", "tiktok_upload_log.json"
        )
        
        with open(upload_log_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Upload log saved: {upload_log_path}")


def main():
    """Phase 11を単体で実行するためのエントリーポイント"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 11: TikTok Upload")
    parser.add_argument("subject", help="Subject name")
    parser.add_argument("--genre", required=True, help="Genre name (e.g., ijin, history_mystery)")
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
        logger.info(f"Phase 11 completed successfully")
        
        if result.status.value == "completed":
            logger.info("TikTok upload status: Success")
            summary = result.output_paths[0] if result.output_paths else None
            if summary:
                logger.info(f"Upload log: {summary}")
    
    except Exception as e:
        logger.error(f"Phase 11 failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
