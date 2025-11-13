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

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        output_format: str = "JPEG",
        jpeg_quality: int = 90
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.target_size = (1920, 1080)
        self.output_format = output_format.upper()  # "JPEG" or "PNG"
        self.jpeg_quality = jpeg_quality  # JPEG品質（1-100）

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

            # デバッグ: 元のサイズを出力
            self.logger.info(f"📐 Resizing: {input_path.name} from {original_size[0]}x{original_size[1]} → {self.target_size[0]}x{self.target_size[1]}")

            # 既に目標サイズの場合はスキップ
            if original_size == self.target_size:
                self.logger.info(f"✓ Already target size, skipping: {input_path.name}")
                return input_path

            # LANCZOS補間で高品質リサイズ（新しいPIL構文を使用）
            img_resized = img.resize(self.target_size, Image.Resampling.LANCZOS)

            # 出力パスの決定
            if output_path is None:
                if overwrite:
                    output_path = input_path
                else:
                    output_path = input_path.parent / f"{input_path.stem}_resized{input_path.suffix}"

            # 出力形式に応じて拡張子を変更
            if self.output_format == "JPEG":
                output_path = output_path.with_suffix('.jpg')
            elif self.output_format == "PNG":
                output_path = output_path.with_suffix('.png')

            # JPEG保存の場合、RGBA/LA/Pモードを変換
            if self.output_format == "JPEG":
                if img_resized.mode in ('RGBA', 'LA', 'P'):
                    # 透明度を削除してRGBに変換
                    img_resized = img_resized.convert('RGB')
                    self.logger.debug(f"Converted {input_path.name} from {img.mode} to RGB for JPEG")

                # JPEG保存（圧縮）
                img_resized.save(
                    output_path,
                    'JPEG',
                    quality=self.jpeg_quality,
                    optimize=True
                )
                self.logger.info(f"✓ Saved as JPEG with quality={self.jpeg_quality}: {output_path.name}")
            else:
                # PNG保存（従来通り）
                img_resized.save(output_path, 'PNG', quality=95, optimize=True)
                self.logger.info(f"✓ Saved as PNG: {output_path.name}")

            # 保存後のサイズを確認
            with Image.open(output_path) as saved_img:
                saved_size = saved_img.size
                self.logger.info(
                    f"✅ Resize complete: {output_path.name} "
                    f"({original_size[0]}x{original_size[1]} → {saved_size[0]}x{saved_size[1]})"
                )

                # サイズが正しいか検証
                if saved_size != self.target_size:
                    self.logger.error(
                        f"❌ Resize failed! Expected {self.target_size[0]}x{self.target_size[1]}, "
                        f"got {saved_size[0]}x{saved_size[1]}"
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
            self.logger.error(f"❌ Input directory not found: {input_dir}")
            return []

        # 出力ディレクトリの作成
        if output_dir and output_dir != input_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"📁 Output directory: {output_dir}")

        # 対象ファイルを収集
        image_files = []
        for ext in extensions:
            image_files.extend(input_dir.glob(f"*{ext}"))
            image_files.extend(input_dir.glob(f"*{ext.upper()}"))

        if not image_files:
            self.logger.warning(f"⚠️ No images found in: {input_dir}")
            return []

        self.logger.info(f"🔍 Found {len(image_files)} images to resize")
        self.logger.info(f"🎯 Target size: {self.target_size[0]}x{self.target_size[1]}")
        self.logger.info(f"📄 Output format: {self.output_format}")

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

        self.logger.info("=" * 60)
        self.logger.info(
            f"✅ Resize summary: {success_count}/{len(image_files)} images resized to "
            f"{self.target_size[0]}x{self.target_size[1]} ({self.output_format})"
        )
        if success_count < len(image_files):
            self.logger.warning(
                f"⚠️ {len(image_files) - success_count} images failed to resize"
            )
        self.logger.info("=" * 60)

        return resized_files


def resize_images_to_1920x1080(
    input_dir: Path,
    output_dir: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
    output_format: str = "JPEG",
    jpeg_quality: int = 90
) -> List[Path]:
    """
    便利関数: ディレクトリ内の画像を1920x1080にリサイズ

    Args:
        input_dir: 入力ディレクトリ
        output_dir: 出力ディレクトリ（Noneの場合は上書き）
        logger: ロガー
        output_format: 出力形式（"JPEG" or "PNG"）- デフォルトはJPEG
        jpeg_quality: JPEG品質（1-100）- デフォルトは90

    Returns:
        リサイズされたファイルパスのリスト
    """
    resizer = ImageResizer(
        logger=logger,
        output_format=output_format,
        jpeg_quality=jpeg_quality
    )
    return resizer.resize_directory(input_dir, output_dir, overwrite=(output_dir is None))
