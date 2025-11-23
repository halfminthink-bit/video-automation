"""
グラデーション処理

動画にグラデーション効果を適用する専門クラス
"""

import subprocess
from pathlib import Path
from typing import Optional

from PIL import Image


class GradientProcessor:
    """
    グラデーション処理

    責任:
    - グラデーション画像の生成（Pillow使用、キャッシュ機能付き）
    - 動画へのグラデーション適用（FFmpeg使用）
    """

    def __init__(
        self,
        logger,
        working_dir: Optional[Path] = None
    ):
        """
        初期化

        Args:
            logger: ロガー
            working_dir: 作業ディレクトリ（キャッシュ保存用）
        """
        self.logger = logger
        self.working_dir = working_dir

    def create_gradient_image(
        self,
        width: int = 1920,
        height: int = 1080,
        gradient_ratio: float = 0.35,
        cache_dir: Optional[Path] = None
    ) -> Path:
        """
        グラデーション画像を生成（Pillow使用）

        上部が透明で、下部が黒になるグラデーション画像を作成します。
        キャッシュ機能付きで、同じパラメータの場合は再利用します。

        Args:
            width: 画像幅
            height: 画像高さ
            gradient_ratio: グラデーションの高さ比率（0.0-1.0）
            cache_dir: キャッシュディレクトリ（指定しない場合はworking_dir配下）

        Returns:
            生成されたグラデーション画像のパス
        """
        # キャッシュディレクトリ
        if cache_dir is None:
            if self.working_dir:
                cache_dir = self.working_dir / "04_processed" / ".gradient_cache"
            else:
                cache_dir = Path.cwd() / ".gradient_cache"

        cache_dir.mkdir(parents=True, exist_ok=True)

        # キャッシュファイル名（パラメータに基づく）
        cache_filename = f"gradient_{width}x{height}_ratio{gradient_ratio:.2f}.png"
        cache_path = cache_dir / cache_filename

        # キャッシュが存在する場合は再利用
        if cache_path.exists():
            self.logger.debug(f"Using cached gradient image: {cache_path.name}")
            return cache_path

        # グラデーション画像を生成
        self.logger.debug(f"Creating gradient image: {width}x{height}, ratio={gradient_ratio:.2f}")

        # RGBA画像を作成（完全に透明から開始）
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))

        # グラデーションの開始位置と終了位置
        gradient_height = int(height * gradient_ratio)
        start_y = height - gradient_height

        # ピクセルデータを取得
        pixels = img.load()

        # 下部からグラデーションを描画
        for y in range(start_y, height):
            # アルファ値の計算（0 = 完全透明、255 = 完全不透明）
            alpha = int(255 * (y - start_y) / gradient_height)

            # 黒色（R=0, G=0, B=0）にアルファを適用
            for x in range(width):
                pixels[x, y] = (0, 0, 0, alpha)

        # 画像を保存
        img.save(cache_path, 'PNG')
        self.logger.debug(f"Saved gradient image: {cache_path}")

        return cache_path

    def apply_to_video(
        self,
        video_path: Path,
        gradient_path: Path,
        timeout: int = 120
    ) -> bool:
        """
        動画にグラデーションを上書き合成

        Args:
            video_path: 動画ファイルのパス（上書きされます）
            gradient_path: グラデーション画像のパス
            timeout: タイムアウト（秒）

        Returns:
            成功した場合 True
        """
        # ファイル存在確認
        if not video_path.exists():
            self.logger.error(f"❌ Video not found: {video_path}")
            return False

        if not gradient_path.exists():
            self.logger.error(f"❌ Gradient not found: {gradient_path}")
            return False

        self.logger.info(f"  📦 Video: {video_path.name} ({video_path.stat().st_size / 1024:.1f}KB)")
        self.logger.info(f"  🎨 Gradient: {gradient_path.name}")

        temp_path = video_path.with_name(f"temp_{video_path.name}")

        try:
            video_path.rename(temp_path)
            self.logger.debug(f"  ✓ Renamed to temp: {temp_path.name}")
        except OSError as e:
            self.logger.error(f"❌ Failed to rename: {e}")
            return False

        cmd = [
            'ffmpeg', '-y',
            '-i', str(temp_path),
            '-loop', '1', '-i', str(gradient_path),
            '-filter_complex', "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[out]",
            '-map', '[out]',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18',
            '-pix_fmt', 'yuv420p', '-r', '30',
            str(video_path)
        ]

        # コマンドをログ出力
        self.logger.debug(f"  Running: {' '.join(cmd)}")

        # デッドロック対策: stdout/stderrをDEVNULLに設定
        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                timeout=timeout
            )

            # 成功
            if temp_path.exists():
                temp_path.unlink()
            self.logger.info("  ✅ Gradient applied successfully")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ Gradient overlay timed out ({timeout}s)")
            # 元に戻す
            if temp_path.exists():
                if video_path.exists():
                    video_path.unlink()
                temp_path.rename(video_path)
            return False

        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ FFmpeg failed: {e.returncode}")
            self.logger.error(f"STDERR: {e.stderr}")
            # 元に戻す
            if temp_path.exists():
                if video_path.exists():
                    video_path.unlink()
                temp_path.rename(video_path)
            return False

    def run_ffmpeg_safe(self, cmd: list, timeout: int = 600) -> bool:
        """
        安全なFFmpeg実行ヘルパー（デッドロック防止・タイムアウト付き）

        Args:
            cmd: FFmpegコマンド（リスト形式）
            timeout: タイムアウト（秒）

        Returns:
            成功した場合 True
        """
        try:
            # stdin, stdout, stderr 全てを DEVNULL にしてブロッキングを防ぐ
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                timeout=timeout
            )
            return True
        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ FFmpeg timed out after {timeout}s")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ FFmpeg execution failed with code {e.returncode}")
            return False
