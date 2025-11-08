"""
人物中心の背景処理

人物を中央に配置し、上下のテキストエリアを暗くする
"""

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from typing import Tuple, Optional
import logging


class PersonFocusedBackground:
    """人物中心の背景処理クラス"""

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

    def process_background(
        self,
        image: Image.Image,
        zone_mask: Image.Image,
        darken_strength: float = 0.7
    ) -> Image.Image:
        """
        背景を処理：上下のテキストエリアを暗くし、中央の人物エリアは明るさを維持

        Args:
            image: 元画像
            zone_mask: ゾーンマスク（Lモード、0=明るい、255=暗い）
            darken_strength: 暗くする強度（0.0〜1.0）

        Returns:
            処理後の画像
        """
        self.logger.info("Processing background with person-focused approach")

        # 画像サイズを確認
        if image.size != (self.width, self.height):
            self.logger.warning(
                f"Image size mismatch: {image.size} != {(self.width, self.height)}, resizing"
            )
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)

        # RGBA変換
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # 1. 全体の彩度を少し下げる
        enhancer_saturation = ImageEnhance.Color(image)
        image = enhancer_saturation.enhance(0.85)

        # 2. ゾーンマスクを使って選択的に暗くする
        image = self._apply_selective_darkening(image, zone_mask, darken_strength)

        # 3. 軽いビネット効果（周辺減光）
        image = self._apply_subtle_vignette(image, strength=0.3)

        self.logger.info("Background processing completed")

        return image

    def _apply_selective_darkening(
        self,
        image: Image.Image,
        zone_mask: Image.Image,
        strength: float
    ) -> Image.Image:
        """
        ゾーンマスクを使って選択的に暗くする

        Args:
            image: 元画像
            zone_mask: ゾーンマスク（Lモード）
            strength: 暗くする強度

        Returns:
            処理後の画像
        """
        self.logger.debug(f"Applying selective darkening (strength={strength})")

        # 暗い版の画像を作成
        darkened = image.copy()
        enhancer_brightness = ImageEnhance.Brightness(darkened)
        darkened = enhancer_brightness.enhance(0.4)  # 40%の明るさ

        # マスクの強度を調整
        adjusted_mask = zone_mask.copy()
        adjusted_mask = Image.eval(adjusted_mask, lambda x: int(x * strength))

        # 元画像と暗い画像を合成
        result = Image.composite(darkened, image, adjusted_mask)

        return result

    def _apply_subtle_vignette(
        self,
        image: Image.Image,
        strength: float = 0.3
    ) -> Image.Image:
        """
        軽いビネット効果を適用

        Args:
            image: 元画像
            strength: ビネットの強さ（0.0〜1.0）

        Returns:
            ビネット効果適用後の画像
        """
        self.logger.debug(f"Applying subtle vignette (strength={strength})")

        width, height = image.size

        # 楕円形のマスクを作成
        mask = Image.new('L', (width, height), 255)
        mask_draw = ImageDraw.Draw(mask)

        # 中心から周辺に向かって暗くなるグラデーション
        steps = 50
        for i in range(steps):
            # 中心から外側へ
            ratio = i / steps
            alpha = int(255 * (1 - strength * ratio))

            # 楕円のサイズを計算
            margin_x = int(width * ratio * 0.3)
            margin_y = int(height * ratio * 0.3)

            bbox = [
                margin_x,
                margin_y,
                width - margin_x,
                height - margin_y
            ]

            mask_draw.ellipse(bbox, fill=alpha)

        # 元画像にマスクを適用
        if image.mode == 'RGB':
            image = image.convert('RGBA')

        # 黒い背景を作成
        black_bg = Image.new('RGBA', (width, height), (0, 0, 0, 255))

        # ビネット効果を合成
        result = Image.composite(image, black_bg, mask)

        return result

    def add_gradient_overlay(
        self,
        image: Image.Image,
        top_color: Tuple[int, int, int, int] = (0, 0, 0, 100),
        bottom_color: Tuple[int, int, int, int] = (0, 0, 0, 100)
    ) -> Image.Image:
        """
        上下にグラデーションオーバーレイを追加

        Args:
            image: 元画像
            top_color: 上部の色（RGBA）
            bottom_color: 下部の色（RGBA）

        Returns:
            オーバーレイ適用後の画像
        """
        self.logger.debug("Adding gradient overlay")

        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # オーバーレイレイヤーを作成
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 上部グラデーション（上30%）
        top_height = int(self.height * 0.30)
        for y in range(top_height):
            ratio = 1 - (y / top_height)
            alpha = int(top_color[3] * ratio)
            color = top_color[:3] + (alpha,)
            draw.line([(0, y), (self.width, y)], fill=color)

        # 下部グラデーション（下30%）
        bottom_start = int(self.height * 0.70)
        for y in range(bottom_start, self.height):
            ratio = (y - bottom_start) / (self.height - bottom_start)
            alpha = int(bottom_color[3] * ratio)
            color = bottom_color[:3] + (alpha,)
            draw.line([(0, y), (self.width, y)], fill=color)

        # オーバーレイを合成
        result = Image.alpha_composite(image, overlay)

        return result
