"""
シンプル背景プロセッサー

背景を暗くせず、軽いビネット効果のみを適用
"""

from PIL import Image, ImageDraw, ImageFilter
from typing import Tuple, Optional
import logging


class SimpleBackgroundProcessor:
    """シンプルな背景処理クラス（暗くしない）"""

    def __init__(
        self,
        canvas_size: Tuple[int, int] = (1280, 720),
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            canvas_size: キャンバスサイズ (width, height)
            logger: ロガー
        """
        self.width, self.height = canvas_size
        self.logger = logger or logging.getLogger(__name__)

        self.logger.info(f"SimpleBackgroundProcessor initialized: {canvas_size}")

    def process_background(
        self,
        image: Image.Image,
        vignette_strength: float = 0.2
    ) -> Image.Image:
        """
        背景を処理（暗くせず、軽いビネットのみ）

        Args:
            image: 元画像
            vignette_strength: ビネットの強さ（0.0〜1.0、デフォルト0.2）

        Returns:
            処理済み画像
        """
        self.logger.info("Processing background (simple mode - no darkening)")

        # 画像サイズを確認
        if image.size != (self.width, self.height):
            self.logger.warning(
                f"Image size mismatch: {image.size} != {(self.width, self.height)}, resizing"
            )
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)

        # RGBA変換
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # 軽いビネット効果を適用（周辺をわずかに暗く）
        if vignette_strength > 0:
            image = self._apply_light_vignette(image, strength=vignette_strength)

        self.logger.info("✅ Background processed (minimal processing)")

        return image

    def _apply_light_vignette(
        self,
        image: Image.Image,
        strength: float = 0.2
    ) -> Image.Image:
        """
        軽いビネット効果を適用

        Args:
            image: 元画像
            strength: ビネットの強さ（0.0〜1.0）

        Returns:
            ビネット効果が適用された画像
        """
        self.logger.debug(f"Applying light vignette: strength={strength}")

        width, height = image.size

        # 楕円形のマスクを作成
        mask = Image.new('L', (width, height), 255)
        draw = ImageDraw.Draw(mask)

        # 中心から周辺に向かってグラデーション
        steps = 50
        for i in range(steps):
            # 中心から外側へ
            ratio = i / steps
            # 強度を調整（strengthが0.2なら、最大でも51の暗さ）
            alpha = int(255 * (1 - strength * ratio))

            # 楕円のサイズを計算
            margin_x = int(width * ratio * 0.4)
            margin_y = int(height * ratio * 0.4)

            bbox = [
                margin_x,
                margin_y,
                width - margin_x,
                height - margin_y
            ]

            draw.ellipse(bbox, fill=alpha)

        # 元画像にマスクを適用
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # 黒い背景を作成
        black_bg = Image.new('RGBA', (width, height), (0, 0, 0, 255))

        # ビネット効果を合成
        result = Image.composite(image, black_bg, mask)

        return result

    def add_text_zone_overlay(
        self,
        image: Image.Image,
        top_height_percent: float = 0.25,
        bottom_height_percent: float = 0.25,
        overlay_opacity: int = 30
    ) -> Image.Image:
        """
        テキストゾーンに軽いオーバーレイを追加（オプション）

        Args:
            image: 元画像
            top_height_percent: 上部オーバーレイの高さ（0.0〜1.0）
            bottom_height_percent: 下部オーバーレイの高さ（0.0〜1.0）
            overlay_opacity: オーバーレイの不透明度（0〜255）

        Returns:
            オーバーレイが適用された画像
        """
        self.logger.debug("Adding text zone overlay")

        width, height = image.size

        # オーバーレイレイヤーを作成
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 上部オーバーレイ（グラデーション）
        top_height = int(height * top_height_percent)
        for y in range(top_height):
            # 上から下へ減少
            ratio = 1 - (y / top_height)
            alpha = int(overlay_opacity * ratio)
            draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

        # 下部オーバーレイ（グラデーション）
        bottom_start = int(height * (1 - bottom_height_percent))
        for y in range(bottom_start, height):
            # 上から下へ増加
            ratio = (y - bottom_start) / (height - bottom_start)
            alpha = int(overlay_opacity * ratio)
            draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

        # 元画像に合成
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        result = Image.alpha_composite(image, overlay)

        self.logger.debug("✅ Text zone overlay added")

        return result

    def resize_image(
        self,
        image: Image.Image,
        target_size: Optional[Tuple[int, int]] = None
    ) -> Image.Image:
        """
        画像をリサイズ

        Args:
            image: 元画像
            target_size: ターゲットサイズ（指定しない場合はself.canvas_size）

        Returns:
            リサイズされた画像
        """
        if target_size is None:
            target_size = (self.width, self.height)

        if image.size == target_size:
            self.logger.debug(f"Image already at target size: {target_size}")
            return image

        self.logger.debug(f"Resizing image from {image.size} to {target_size}")

        resized = image.resize(target_size, Image.Resampling.LANCZOS)

        return resized
