"""
動画分割ユーティリティ

ffmpegを使用して動画を指定秒数ごとに分割し、
指定した数のクリップのみを返す。
"""

from pathlib import Path
from typing import List, Optional
import subprocess
import logging


class VideoSplitter:
    """動画分割クラス"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化

        Args:
            logger: ロガー（Noneの場合は自動作成）
        """
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
        動画を分割

        Args:
            input_path: 入力動画パス
            output_dir: 出力ディレクトリ
            segment_duration: 分割秒数（デフォルト60秒）
            max_segments: 最大クリップ数（デフォルト5）
            prefix: 出力ファイル名のプレフィックス

        Returns:
            分割された動画ファイルのパスリスト（最大max_segments個）

        Raises:
            FileNotFoundError: 入力ファイルが存在しない
            RuntimeError: ffmpegコマンドが失敗した
        """
        # 入力ファイルのチェック
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        # 出力ディレクトリを作成
        output_dir.mkdir(parents=True, exist_ok=True)

        # 出力ファイルパターン
        output_pattern = output_dir / f"{prefix}_%03d.mp4"

        self.logger.info(f"Splitting video: {input_path}")
        self.logger.info(f"Segment duration: {segment_duration}s, Max segments: {max_segments}")

        # ffmpegコマンドを構築
        # -f segment: セグメント分割モード
        # -segment_time: 分割秒数
        # -reset_timestamps 1: 各クリップのタイムスタンプをリセット
        # -c copy: ストリームをコピー（再エンコードなし = 高速）
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-f", "segment",
            "-segment_time", str(segment_duration),
            "-reset_timestamps", "1",
            "-c", "copy",
            "-avoid_negative_ts", "1",  # 負のタイムスタンプを回避
            str(output_pattern)
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

        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg failed: {e.stderr}")
            raise RuntimeError(f"Video splitting failed: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg not found. Please install ffmpeg: "
                "https://ffmpeg.org/download.html"
            )

        # 生成されたファイルを取得（番号順にソート）
        all_clips = sorted(output_dir.glob(f"{prefix}_*.mp4"))

        if not all_clips:
            raise RuntimeError(f"No clips generated in {output_dir}")

        # 最初のmax_segments個のみ返す
        selected_clips = all_clips[:max_segments]

        self.logger.info(f"Generated {len(all_clips)} clips, selected first {len(selected_clips)}")
        for i, clip in enumerate(selected_clips, 1):
            self.logger.info(f"  Clip {i}: {clip.name}")

        return selected_clips
