"""
動画分割ユーティリティ

ffmpegを使用して動画を指定秒数ごとに分割し、
Phase 07のエラーハンドリングパターンを踏襲。
"""

import subprocess
import platform
from pathlib import Path
from typing import List, Optional
import logging


class VideoSplitter:
    """動画分割クラス"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def split_video(
        self,
        input_path: Path,
        output_dir: Path,
        segment_duration: int = 60,
        max_segments: int = 5,
        prefix: str = "clip"
    ) -> List[Path]:
        """
        動画を分割（Phase 07のffmpegパターンを使用）

        Args:
            input_path: 入力動画パス
            output_dir: 出力ディレクトリ
            segment_duration: 分割秒数（デフォルト60秒）
            max_segments: 最大クリップ数（デフォルト5）
            prefix: 出力ファイル名のプレフィックス

        Returns:
            分割された動画ファイルのパスリスト（最大max_segments個）

        使用するffmpegコマンド:
            ffmpeg -i input.mp4 -f segment -segment_time 60 \
                   -reset_timestamps 1 -c copy -map 0 \
                   output_%03d.mp4
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # 出力パスパターン
        output_pattern = output_dir / f"{prefix}_%03d.mp4"

        # Windowsパス対応（Phase 07パターン）
        input_str = str(input_path)
        output_str = str(output_pattern)
        if platform.system() == 'Windows':
            input_str = input_str.replace('\\', '/')
            output_str = output_str.replace('\\', '/')

        cmd = [
            'ffmpeg', '-y',
            '-i', input_str,
            '-f', 'segment',
            '-segment_time', str(segment_duration),
            '-reset_timestamps', '1',
            '-c', 'copy',
            '-map', '0',
            output_str
        ]

        self.logger.info(f"Splitting video into {segment_duration}s segments...")
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

            # 生成されたファイルを取得（最大max_segments個）
            clips = sorted(output_dir.glob(f"{prefix}_*.mp4"))[:max_segments]

            self.logger.info(f"✓ Created {len(clips)} clips (max: {max_segments})")
            return clips

        except subprocess.CalledProcessError as e:
            # Phase 07のエラーメッセージパターン
            try:
                stderr_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''
            except:
                stderr_msg = '<decode failed>'

            self.logger.error(f"ffmpeg split failed: {stderr_msg}")
            raise
