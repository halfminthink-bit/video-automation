"""
エフェクトコンポジター

シャドウ、グロー、ビネット効果を適用して、サムネイルのインパクトを強化
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import Tuple, Optional
import logging


class EffectCompositor:
    """複数のエフェクトを合成するクラス"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化

        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)

    def add_drop_shadow(
        self,
        size: Tuple[int, int],
        text: str,
        position: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        layers: int = 10,
        max_offset: int = 20,
        blur_radius: int = 5
    ) -> Image.Image:
        """
        ドロップシャドウを追加

        Args:
            size: 画像サイズ (width, height)
            text: テキスト
            position: テキスト位置 (x, y)
            font: フォント
            layers: シャドウのレイヤー数
            max_offset: 最大オフセット（ピクセル）
            blur_radius: ぼかし半径

        Returns:
            シャドウが適用されたRGBA画像
        """
        width, height = size
        shadow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))

        self.logger.info(f"Adding drop shadow: {layers} layers, max_offset={max_offset}px")

        # 外側から内側へ、段階的にシャドウを描画
        for i in range(layers, 0, -1):
            # オフセットと透明度を計算
            offset = int((i / layers) * max_offset)
            alpha = int(180 * (i / layers))

            # シャドウレイヤーを作成
            temp_shadow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(temp_shadow)

            x, y = position
            shadow_pos = (x + offset, y + offset)

            # シャドウを描画
            draw.text(
                shadow_pos,
                text,
                font=font,
                fill=(0, 0, 0, alpha),
                stroke_width=10,
                stroke_fill=(0, 0, 0, alpha // 2)
            )

            # ぼかしを適用
            temp_shadow = temp_shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            # メインのシャドウレイヤーに合成
            shadow_layer = Image.alpha_composite(shadow_layer, temp_shadow)

        self.logger.info("✅ Drop shadow added")

        return shadow_layer

    def add_glow_effect(
        self,
        size: Tuple[int, int],
        text: str,
        position: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        radius: int = 30,
        intensity: float = 0.7,
        glow_color: Optional[Tuple[int, int, int]] = None
    ) -> Image.Image:
        """
        グロー効果を追加

        Args:
            size: 画像サイズ (width, height)
            text: テキスト
            position: テキスト位置 (x, y)
            font: フォント
            radius: グローの範囲（ピクセル）
            intensity: グローの強度（0.0〜1.0）
            glow_color: グローの色（Noneの場合は黒）

        Returns:
            グロー効果が適用されたRGBA画像
        """
        width, height = size
        glow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))

        if glow_color is None:
            glow_color = (0, 0, 0)

        self.logger.info(f"Adding glow effect: radius={radius}px, intensity={intensity}")

        # グローの重ね回数を計算
        iterations = min(radius // 3, 10)

        for i in range(iterations, 0, -1):
            # アルファ値を計算
            alpha = int(120 * intensity * (i / iterations))

            # グローレイヤーを作成
            temp_glow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(temp_glow)

            # グローを描画
            draw.text(
                position,
                text,
                font=font,
                fill=glow_color + (alpha,),
                stroke_width=radius - (i * 3),
                stroke_fill=glow_color + (alpha,)
            )

            # ぼかしを適用
            temp_glow = temp_glow.filter(ImageFilter.GaussianBlur(radius=3))

            # メインのグローレイヤーに合成
            glow_layer = Image.alpha_composite(glow_layer, temp_glow)

        self.logger.info("✅ Glow effect added")

        return glow_layer

    def add_vignette(
        self,
        img: Image.Image,
        strength: float = 0.6
    ) -> Image.Image:
        """
        ビネット効果（周辺減光）を適用

        Args:
            img: 元画像
            strength: ビネットの強さ（0.0〜1.0）

        Returns:
            ビネット効果が適用された画像
        """
        width, height = img.size

        self.logger.info(f"Adding vignette effect: strength={strength}")

        # 楕円形のマスクを作成
        mask = Image.new('L', (width, height), 255)
        mask_draw = ImageDraw.Draw(mask)

        # 中心から周辺に向かって暗くなるグラデーション
        for i in range(100):
            # 中心から外側へ
            ratio = i / 100.0
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

            mask_draw.ellipse(bbox, fill=alpha)

        # 元画像にマスクを適用
        if img.mode == 'RGB':
            img = img.convert('RGBA')

        # 黒い背景を作成
        black_bg = Image.new('RGBA', (width, height), (0, 0, 0, 255))

        # ビネット効果を合成
        result = Image.composite(img, black_bg, mask)

        self.logger.info("✅ Vignette effect added")

        return result

    def darken_background(
        self,
        img: Image.Image,
        saturation_factor: float = 0.7,
        brightness_factor: float = 0.6
    ) -> Image.Image:
        """
        背景を暗くして文字を際立たせる

        Args:
            img: 元画像
            saturation_factor: 彩度係数（0.0〜1.0）
            brightness_factor: 明度係数（0.0〜1.0）

        Returns:
            暗くなった画像
        """
        self.logger.info(
            f"Darkening background: saturation={saturation_factor}, "
            f"brightness={brightness_factor}"
        )

        # 1. 彩度を下げる
        enhancer_saturation = ImageEnhance.Color(img)
        img = enhancer_saturation.enhance(saturation_factor)

        # 2. 明度を下げる
        enhancer_brightness = ImageEnhance.Brightness(img)
        img = enhancer_brightness.enhance(brightness_factor)

        self.logger.info("✅ Background darkened")

        return img
