"""
暗めの背景処理プロセッサー

「教科書には載せてくれない」シリーズ用の暗い雰囲気を作る
- 全体的に暗くする
- 強いビネット効果
- 上下端に影を追加
"""

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from typing import Tuple, Optional
import logging
import numpy as np


class DarkVignetteProcessor:
    """暗めの背景処理プロセッサー"""

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

        self.logger.info(f"DarkVignetteProcessor initialized: {canvas_size}")

    def process_background(
        self,
        image: Image.Image,
        darkness_factor: float = 0.7,
        vignette_strength: float = 0.6,
        edge_shadow: bool = True
    ) -> Image.Image:
        """
        背景を暗く処理してテキストを際立たせる

        Args:
            image: 元画像
            darkness_factor: 暗さの係数（0.0-1.0、低いほど暗い）
            vignette_strength: ビネット効果の強さ（0.0-1.0）
            edge_shadow: 上下端に影を追加するか

        Returns:
            処理済み画像
        """
        self.logger.info(
            f"Processing background: darkness={darkness_factor}, "
            f"vignette={vignette_strength}, edge_shadow={edge_shadow}"
        )

        # RGBAに変換
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # 1. 全体的に暗くする
        darkened = self._darken_image(image, darkness_factor)

        # 2. 強いビネット効果を追加
        vignette = self._create_strong_vignette(
            vignette_strength,
            center_preserve_ratio=0.5  # 中央50%は少し明るめに保つ
        )
        result = Image.alpha_composite(darkened, vignette)

        # 3. 上下端に強い影を追加
        if edge_shadow:
            edge_shadow_layer = self._create_edge_shadows()
            result = Image.alpha_composite(result, edge_shadow_layer)

        self.logger.info("✅ Background processed")

        return result

    def _darken_image(
        self,
        image: Image.Image,
        factor: float
    ) -> Image.Image:
        """
        画像全体を暗くする

        Args:
            image: 元画像
            factor: 明るさの係数（0.0-1.0、低いほど暗い）

        Returns:
            暗くした画像
        """
        # 明るさを調整
        enhancer = ImageEnhance.Brightness(image)
        darkened = enhancer.enhance(factor)

        # コントラストを少し上げる（暗くしても顔がはっきり見えるように）
        contrast_enhancer = ImageEnhance.Contrast(darkened)
        darkened = contrast_enhancer.enhance(1.1)

        return darkened

    def _create_strong_vignette(
        self,
        strength: float,
        center_preserve_ratio: float = 0.5
    ) -> Image.Image:
        """
        強いビネット効果レイヤーを作成

        Args:
            strength: ビネット効果の強さ（0.0-1.0）
            center_preserve_ratio: 中央を保つ比率（0.0-1.0）

        Returns:
            ビネットレイヤー（RGBA）
        """
        # ビネットマスクを作成
        vignette = Image.new('L', (self.width, self.height), 0)

        # NumPy配列として操作
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

                # ビネット係数（中央は明るく、端は暗く）
                if normalized_distance < center_preserve_ratio:
                    # 中央エリア（明るく保つ）
                    vignette_value = 1.0 - (normalized_distance / center_preserve_ratio) * strength * 0.3
                else:
                    # 外側エリア（強く暗くする）
                    outer_ratio = (normalized_distance - center_preserve_ratio) / (1.0 - center_preserve_ratio)
                    vignette_value = 1.0 - strength * (0.3 + outer_ratio * 0.7)

                vignette_array[y, x] = max(0, vignette_value)

        # 0-255の範囲に変換
        vignette_array = (vignette_array * 255).astype(np.uint8)

        # PIL Imageに変換
        vignette = Image.fromarray(vignette_array, mode='L')

        # ぼかしを適用してスムーズに
        vignette = vignette.filter(ImageFilter.GaussianBlur(50))

        # RGBAレイヤーを作成（黒でマスク）
        vignette_layer = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))

        # 黒をビネットマスクで合成
        black_layer = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        vignette_layer.paste(black_layer, (0, 0))

        # アルファチャンネルを設定（ビネットを反転）
        vignette_inverted = Image.eval(vignette, lambda x: 255 - x)
        vignette_layer.putalpha(vignette_inverted)

        return vignette_layer

    def _create_edge_shadows(self) -> Image.Image:
        """
        上下端に強い影を追加

        Returns:
            影レイヤー（RGBA）
        """
        shadow = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shadow)

        # 上部グラデーション影（150px）
        shadow_height = 150
        for y in range(shadow_height):
            # 不透明度を計算（上端ほど暗い）
            opacity = int(180 * (1 - y / shadow_height))
            draw.rectangle(
                [(0, y), (self.width, y + 1)],
                fill=(0, 0, 0, opacity)
            )

        # 下部グラデーション影（150px）
        for y in range(shadow_height):
            # 不透明度を計算（下端ほど暗い）
            opacity = int(180 * (1 - y / shadow_height))
            actual_y = self.height - y - 1
            draw.rectangle(
                [(0, actual_y), (self.width, actual_y + 1)],
                fill=(0, 0, 0, opacity)
            )

        # ぼかしを適用
        shadow = shadow.filter(ImageFilter.GaussianBlur(15))

        return shadow

    def add_texture_overlay(
        self,
        image: Image.Image,
        texture_type: str = "parchment"
    ) -> Image.Image:
        """
        歴史的な質感オーバーレイを追加（オプション）

        Args:
            image: 元画像
            texture_type: テクスチャの種類（"parchment", "grain", "noise"）

        Returns:
            テクスチャ追加済み画像
        """
        self.logger.debug(f"Adding texture overlay: {texture_type}")

        if texture_type == "grain":
            # フィルムグレイン風のノイズ
            overlay = self._create_grain_texture()
        elif texture_type == "noise":
            # 軽いノイズ
            overlay = self._create_noise_texture()
        else:
            # パーチメント（羊皮紙）風
            overlay = self._create_parchment_texture()

        # 画像に合成
        result = Image.alpha_composite(image.convert('RGBA'), overlay)

        return result

    def _create_grain_texture(self) -> Image.Image:
        """フィルムグレイン風テクスチャ"""
        # ランダムノイズを生成
        noise_array = np.random.randint(0, 50, (self.height, self.width), dtype=np.uint8)
        noise_layer = Image.fromarray(noise_array, mode='L')

        # ぼかしを少し追加
        noise_layer = noise_layer.filter(ImageFilter.GaussianBlur(0.5))

        # RGBAレイヤーに変換（低い不透明度）
        rgba_layer = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        rgba_layer.putalpha(noise_layer)

        return rgba_layer

    def _create_noise_texture(self) -> Image.Image:
        """軽いノイズテクスチャ"""
        # 軽いランダムノイズ
        noise_array = np.random.randint(0, 30, (self.height, self.width), dtype=np.uint8)
        noise_layer = Image.fromarray(noise_array, mode='L')

        # RGBAレイヤーに変換（非常に低い不透明度）
        rgba_layer = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        rgba_layer.putalpha(noise_layer)

        return rgba_layer

    def _create_parchment_texture(self) -> Image.Image:
        """パーチメント（羊皮紙）風テクスチャ"""
        # セピア調のオーバーレイ
        parchment = Image.new('RGBA', (self.width, self.height), (101, 67, 33, 15))

        # 軽いノイズを追加
        noise_array = np.random.randint(0, 20, (self.height, self.width), dtype=np.uint8)
        noise_layer = Image.fromarray(noise_array, mode='L')
        noise_layer = noise_layer.filter(ImageFilter.GaussianBlur(1))

        # ノイズをアルファチャンネルに適用
        parchment.putalpha(noise_layer)

        return parchment
