"""
明るい背景処理プロセッサー

人物写真を暗くせず、顔がよく見えるようにする
- 軽いビネット効果のみ
- 明るさを保つ
- エッジに軽い影（テキストを際立たせる程度）
"""

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from typing import Tuple, Optional
import logging
import numpy as np


class BrightBackgroundProcessor:
    """明るい背景処理プロセッサー（顔がよく見える）"""

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

        self.logger.info(f"BrightBackgroundProcessor initialized: {canvas_size}")

    def process_background(
        self,
        image: Image.Image,
        vignette_strength: float = 0.2,
        edge_shadow: bool = True,
        enhance_brightness: bool = True
    ) -> Image.Image:
        """
        背景を明るく処理してテキストが読めるようにする

        Args:
            image: 元画像
            vignette_strength: ビネット効果の強さ（0.0-1.0、軽めに）
            edge_shadow: 上下端に軽い影を追加するか
            enhance_brightness: 明るさを少し上げるか

        Returns:
            処理済み画像
        """
        self.logger.info(
            f"Processing background (bright mode): "
            f"vignette={vignette_strength}, edge_shadow={edge_shadow}, "
            f"enhance_brightness={enhance_brightness}"
        )

        # RGBAに変換
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        result = image.copy()

        # 1. 明るさを少し上げる（オプション）
        if enhance_brightness:
            result = self._enhance_brightness(result, factor=1.1)

        # 2. コントラストを少し上げる（顔をはっきりさせる）
        result = self._enhance_contrast(result, factor=1.1)

        # 3. 軽いビネット効果を追加（中央を明るく保つ）
        if vignette_strength > 0:
            vignette = self._create_light_vignette(
                vignette_strength,
                center_preserve_ratio=0.7  # 中央70%は明るく保つ
            )
            result = Image.alpha_composite(result, vignette)

        # 4. 上下端に軽い影を追加（テキストエリアのみ）
        if edge_shadow:
            edge_shadow_layer = self._create_text_area_shadows()
            result = Image.alpha_composite(result, edge_shadow_layer)

        self.logger.info("✅ Background processed (bright mode)")

        return result

    def _enhance_brightness(
        self,
        image: Image.Image,
        factor: float = 1.1
    ) -> Image.Image:
        """
        明るさを上げる

        Args:
            image: 元画像
            factor: 明るさ係数（1.0より大きい）

        Returns:
            明るくした画像
        """
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(factor)

    def _enhance_contrast(
        self,
        image: Image.Image,
        factor: float = 1.1
    ) -> Image.Image:
        """
        コントラストを上げる

        Args:
            image: 元画像
            factor: コントラスト係数

        Returns:
            コントラストを上げた画像
        """
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)

    def _create_light_vignette(
        self,
        strength: float,
        center_preserve_ratio: float = 0.7
    ) -> Image.Image:
        """
        軽いビネット効果レイヤーを作成

        Args:
            strength: ビネット効果の強さ（0.0-1.0）
            center_preserve_ratio: 中央を保つ比率（0.0-1.0）

        Returns:
            ビネットレイヤー（RGBA）
        """
        # ビネットマスクを作成
        vignette_array = np.zeros((self.height, self.width), dtype=np.float32)

        # 中心座標
        center_x = self.width / 2
        center_y = self.height / 2

        # 最大距離（対角線の半分）
        max_distance = np.sqrt(center_x ** 2 + center_y ** 2)

        # 各ピクセルの距離に基づいてビネットを計算
        for y in range(self.height):
            for x in range(self.width):
                # 中心からの距離
                dx = x - center_x
                dy = y - center_y
                distance = np.sqrt(dx ** 2 + dy ** 2)

                # 正規化距離（0.0-1.0）
                normalized_distance = distance / max_distance

                # ビネット係数（中央は明るく、端は少し暗く）
                if normalized_distance < center_preserve_ratio:
                    # 中央エリア（ほぼ暗くしない）
                    vignette_value = 1.0 - (normalized_distance / center_preserve_ratio) * strength * 0.1
                else:
                    # 外側エリア（軽く暗くする）
                    outer_ratio = (normalized_distance - center_preserve_ratio) / (1.0 - center_preserve_ratio)
                    vignette_value = 1.0 - strength * (0.1 + outer_ratio * 0.2)

                vignette_array[y, x] = max(0, vignette_value)

        # 0-255の範囲に変換
        vignette_array = (vignette_array * 255).astype(np.uint8)

        # PIL Imageに変換
        vignette = Image.fromarray(vignette_array, mode='L')

        # ぼかしを適用してスムーズに
        vignette = vignette.filter(ImageFilter.GaussianBlur(30))

        # RGBAレイヤーを作成（黒でマスク）
        vignette_layer = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))

        # 黒をビネットマスクで合成
        black_layer = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        vignette_layer.paste(black_layer, (0, 0))

        # アルファチャンネルを設定（ビネットを反転）
        vignette_inverted = Image.eval(vignette, lambda x: 255 - x)
        vignette_layer.putalpha(vignette_inverted)

        return vignette_layer

    def _create_text_area_shadows(self) -> Image.Image:
        """
        上下のテキストエリアにのみ軽い影を追加

        Returns:
            影レイヤー（RGBA）
        """
        shadow = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shadow)

        # 上部グラデーション影（100px、軽め）
        shadow_height = 100
        for y in range(shadow_height):
            # 不透明度を計算（軽め）
            opacity = int(80 * (1 - y / shadow_height))  # 最大80（軽い）
            draw.rectangle(
                [(0, y), (self.width, y + 1)],
                fill=(0, 0, 0, opacity)
            )

        # 下部グラデーション影（100px、軽め）
        for y in range(shadow_height):
            # 不透明度を計算（軽め）
            opacity = int(80 * (1 - y / shadow_height))  # 最大80（軽い）
            actual_y = self.height - y - 1
            draw.rectangle(
                [(0, actual_y), (self.width, actual_y + 1)],
                fill=(0, 0, 0, opacity)
            )

        # ぼかしを適用
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))

        return shadow
