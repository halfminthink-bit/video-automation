"""
アスペクト比変換ユーティリティ

横型動画を縦型(9:16)に変換し、YouTube Shorts向けに最適化する。
"""

from pathlib import Path
import subprocess
import logging
from typing import Optional


class AspectRatioConverter:
    """アスペクト比変換クラス"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化

        Args:
            logger: ロガー（Noneの場合は自動作成）
        """
        self.logger = logger or logging.getLogger(__name__)

    def convert_to_vertical(
        self,
        input_path: Path,
        output_path: Path,
        target_width: int = 1080,
        target_height: int = 1920,
        crop_mode: str = "center"
    ) -> Path:
        """
        横型を縦型に変換

        Args:
            input_path: 入力動画
            output_path: 出力動画
            target_width: 出力幅（デフォルト1080）
            target_height: 出力高さ（デフォルト1920）
            crop_mode: クロップモード（center/top/bottom）

        Returns:
            変換後の動画パス

        Raises:
            FileNotFoundError: 入力ファイルが存在しない
            RuntimeError: ffmpegコマンドが失敗した
        """
        # 入力ファイルのチェック
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        # 出力ディレクトリを作成
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Converting to vertical: {input_path.name}")
        self.logger.info(f"Target resolution: {target_width}x{target_height}")

        # ffmpegコマンドを構築
        # 変換方式: スケール + クロップ
        # 1. scale=1080:1920:force_original_aspect_ratio=increase
        #    -> 1080x1920に収まるように拡大（アスペクト比維持）
        # 2. crop=1080:1920
        #    -> 中央から1080x1920を切り出し

        if crop_mode == "center":
            # 中央クロップ
            vf_filter = (
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
                f"crop={target_width}:{target_height}"
            )
        elif crop_mode == "top":
            # 上部クロップ
            vf_filter = (
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
                f"crop={target_width}:{target_height}:0:0"
            )
        elif crop_mode == "bottom":
            # 下部クロップ
            vf_filter = (
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
                f"crop={target_width}:{target_height}:0:(in_h-{target_height})"
            )
        else:
            raise ValueError(f"Invalid crop_mode: {crop_mode}")

        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-vf", vf_filter,
            "-c:a", "copy",  # 音声はそのままコピー
            "-y",  # 上書き確認なし
            str(output_path)
        ]

        try:
            # ffmpegを実行
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )

            self.logger.debug(f"ffmpeg output: {result.stderr}")
            self.logger.info(f"Conversion complete: {output_path.name}")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg failed: {e.stderr}")
            raise RuntimeError(f"Aspect ratio conversion failed: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg not found. Please install ffmpeg: "
                "https://ffmpeg.org/download.html"
            )

        return output_path
