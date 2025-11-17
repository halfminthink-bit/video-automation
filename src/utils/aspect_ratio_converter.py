"""
アスペクト比変換ユーティリティ

横型動画を縦型(9:16)に変換し、Phase 07のエラーハンドリングを踏襲。
"""

import subprocess
import platform
from pathlib import Path
from typing import Optional
import logging


class AspectRatioConverter:
    """アスペクト比変換クラス"""

    def __init__(self, logger: Optional[logging.Logger] = None):
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
        横型を縦型に変換（Phase 07のffmpegパターン使用）

        Args:
            input_path: 入力動画
            output_path: 出力動画
            target_width: 出力幅（デフォルト1080）
            target_height: 出力高さ（デフォルト1920）
            crop_mode: クロップモード（center/top/bottom）

        Returns:
            変換後の動画パス

        変換方式: 中央クロップ（動画の中央部分を切り出す）

        ffmpegコマンド:
            ffmpeg -i input.mp4 \
                   -vf "scale=1080:1920:force_original_aspect_ratio=increase,
                        crop=1080:1920" \
                   -c:a copy output.mp4
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Windowsパス対応（Phase 07パターン）
        input_str = str(input_path)
        output_str = str(output_path)
        if platform.system() == 'Windows':
            input_str = input_str.replace('\\', '/')
            output_str = output_str.replace('\\', '/')

        # スケール + クロップ（中央）
        vf = f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase,crop={target_width}:{target_height}"

        cmd = [
            'ffmpeg', '-y',
            '-i', input_str,
            '-vf', vf,
            '-c:a', 'copy',
            output_str
        ]

        self.logger.info(f"Converting to vertical ({target_width}x{target_height})...")
        self.logger.debug(f"Command: {' '.join(cmd)}")

        try:
            # Phase 07のエラーハンドリングパターン
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=False,  # バイナリモードで
                encoding=None
            )

            self.logger.info(f"✓ Converted: {output_path.name}")
            return output_path

        except subprocess.CalledProcessError as e:
            # Phase 07のエラーメッセージパターン
            try:
                stderr_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''
            except:
                stderr_msg = '<decode failed>'

            self.logger.error(f"ffmpeg conversion failed: {stderr_msg}")
            raise
