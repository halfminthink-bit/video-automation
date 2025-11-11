"""
画像リサイズユーティリティ
収集した画像を1920x1080に高品質リサイズする
"""

from pathlib import Path
from typing import List, Optional
from PIL import Image
import logging


class ImageResizer:
    """画像リサイズクラス（画質優先）"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.target_size = (1920, 1080)

    def resize_image(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        overwrite: bool = True
    ) -> Path:
        """
        単一画像を1920x1080にリサイズ

        Args:
            input_path: 入力画像パス
            output_path: 出力パス（Noneの場合は上書き）
            overwrite: 上書きするか

        Returns:
            出力ファイルパス
        """
        try:
            # 画像を開く
            img = Image.open(input_path)
            original_size = img.size

            # 既に目標サイズの場合はスキップ
            if original_size == self.target_size:
                self.logger.debug(f"Already target size, skipping: {input_path.name}")
                return input_path

            # LANCZOS補間で高品質リサイズ
            img_resized = img.resize(self.target_size, Image.LANCZOS)

            # 出力パスの決定
            if output_path is None:
                if overwrite:
                    output_path = input_path
                else:
                    output_path = input_path.parent / f"{input_path.stem}_resized{input_path.suffix}"

            # 保存（高品質設定）
            img_resized.save(output_path, quality=95, optimize=True)

            self.logger.debug(
                f"Resized: {input_path.name} "
                f"({original_size[0]}x{original_size[1]} → {self.target_size[0]}x{self.target_size[1]})"
            )

            return output_path

        except Exception as e:
            self.logger.error(f"Failed to resize {input_path.name}: {e}")
            raise

    def resize_directory(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        overwrite: bool = True,
        extensions: List[str] = None
    ) -> List[Path]:
        """
        ディレクトリ内の全画像をリサイズ

        Args:
            input_dir: 入力ディレクトリ
            output_dir: 出力ディレクトリ（Noneの場合は上書き）
            overwrite: 上書きするか
            extensions: 対象拡張子リスト（デフォルト: ['.jpg', '.jpeg', '.png']）

        Returns:
            リサイズされたファイルパスのリスト
        """
        if extensions is None:
            extensions = ['.jpg', '.jpeg', '.png']

        if not input_dir.exists():
            self.logger.warning(f"Input directory not found: {input_dir}")
            return []

        # 出力ディレクトリの作成
        if output_dir and output_dir != input_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

        # 対象ファイルを収集
        image_files = []
        for ext in extensions:
            image_files.extend(input_dir.glob(f"*{ext}"))
            image_files.extend(input_dir.glob(f"*{ext.upper()}"))

        if not image_files:
            self.logger.info(f"No images found in: {input_dir}")
            return []

        self.logger.info(f"Found {len(image_files)} images to resize")

        # リサイズ実行
        resized_files = []
        success_count = 0

        for img_path in image_files:
            try:
                # 出力パスの決定
                if output_dir and output_dir != input_dir:
                    output_path = output_dir / img_path.name
                else:
                    output_path = None  # 上書き

                resized_path = self.resize_image(img_path, output_path, overwrite)
                resized_files.append(resized_path)
                success_count += 1

            except Exception as e:
                self.logger.warning(f"Skipping {img_path.name}: {e}")
                continue

        self.logger.info(
            f"✓ Resized {success_count}/{len(image_files)} images to 1920x1080"
        )

        return resized_files


def resize_images_to_1920x1080(
    input_dir: Path,
    output_dir: Optional[Path] = None,
    logger: Optional[logging.Logger] = None
) -> List[Path]:
    """
    便利関数: ディレクトリ内の画像を1920x1080にリサイズ

    Args:
        input_dir: 入力ディレクトリ
        output_dir: 出力ディレクトリ（Noneの場合は上書き）
        logger: ロガー

    Returns:
        リサイズされたファイルパスのリスト
    """
    resizer = ImageResizer(logger)
    return resizer.resize_directory(input_dir, output_dir, overwrite=(output_dir is None))
