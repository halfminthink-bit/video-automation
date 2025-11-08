"""
グラデーションテキスト生成クラス

NumPyを使用した高速グラデーションテキスト生成を実現
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Optional
import logging
from pathlib import Path


class GradientTextGenerator:
    """NumPyを使用した高速グラデーションテキスト生成"""

    # グラデーションパターン定義
    GRADIENT_PATTERNS = {
        "fire": [(255, 255, 255), (255, 0, 0), (255, 255, 0)],      # 白→赤→黄
        "ocean": [(255, 255, 255), (0, 255, 255), (0, 128, 255)],   # 白→シアン→青
        "sunset": [(255, 0, 0), (255, 127, 0), (255, 255, 0)],      # 赤→オレンジ→黄
        "neon": [(255, 255, 255), (255, 20, 147), (148, 0, 211)],   # 白→ピンク→紫
        "energy": [(0, 255, 0), (255, 255, 0), (255, 0, 0)],        # 緑→黄→赤
    }

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化

        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)

    def create_gradient_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        size: Tuple[int, int],
        position: Tuple[int, int],
        gradient_type: str = "fire",
        direction: str = "vertical"
    ) -> Image.Image:
        """
        グラデーションテキストを生成

        Args:
            text: テキスト
            font: フォント
            size: 画像サイズ (width, height)
            position: テキスト位置 (x, y)
            gradient_type: グラデーションパターン（fire, ocean, sunset, neon, energy）
            direction: グラデーション方向（vertical, horizontal, diagonal）

        Returns:
            グラデーションテキストのRGBA画像
        """
        width, height = size

        # グラデーション色を取得
        colors = self.GRADIENT_PATTERNS.get(gradient_type, self.GRADIENT_PATTERNS["fire"])

        # テキストマスクを作成
        mask = Image.new('L', (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.text(position, text, font=font, fill=255)

        # テキストの境界を取得
        bbox = draw.textbbox(position, text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        self.logger.debug(f"Text bbox: {bbox}, size: {text_width}x{text_height}")

        # グラデーション画像をNumPyで生成
        if direction == "vertical":
            gradient_img = self._create_vertical_gradient(width, height, bbox, colors)
        elif direction == "horizontal":
            gradient_img = self._create_horizontal_gradient(width, height, bbox, colors)
        elif direction == "diagonal":
            gradient_img = self._create_diagonal_gradient(width, height, bbox, colors)
        else:
            gradient_img = self._create_vertical_gradient(width, height, bbox, colors)

        # PIL Imageに変換
        gradient_pil = Image.fromarray(gradient_img.astype('uint8'), 'RGB')

        # マスクを適用してRGBA画像を作成
        result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        result.paste(gradient_pil, (0, 0), mask)

        self.logger.info(f"✨ Gradient text created: '{text}' ({gradient_type}, {direction})")

        return result

    def _create_vertical_gradient(
        self,
        width: int,
        height: int,
        bbox: Tuple[int, int, int, int],
        colors: List[Tuple[int, int, int]]
    ) -> np.ndarray:
        """
        縦方向のグラデーションを生成

        Args:
            width: 画像幅
            height: 画像高さ
            bbox: テキストのバウンディングボックス (left, top, right, bottom)
            colors: 色のリスト [(R,G,B), ...]

        Returns:
            グラデーション画像（NumPy配列）
        """
        # RGB配列を作成
        img_array = np.zeros((height, width, 3), dtype=np.float32)

        text_top = bbox[1]
        text_bottom = bbox[3]
        text_height = text_bottom - text_top

        if text_height <= 0:
            return img_array

        # 各行について色を計算
        for y in range(height):
            if text_top <= y <= text_bottom:
                # テキスト内での相対位置（0.0〜1.0）
                ratio = (y - text_top) / max(text_height, 1)
                color = self._interpolate_multi_color(colors, ratio)
                img_array[y, :] = color

        return img_array

    def _create_horizontal_gradient(
        self,
        width: int,
        height: int,
        bbox: Tuple[int, int, int, int],
        colors: List[Tuple[int, int, int]]
    ) -> np.ndarray:
        """
        横方向のグラデーションを生成

        Args:
            width: 画像幅
            height: 画像高さ
            bbox: テキストのバウンディングボックス
            colors: 色のリスト

        Returns:
            グラデーション画像（NumPy配列）
        """
        img_array = np.zeros((height, width, 3), dtype=np.float32)

        text_left = bbox[0]
        text_right = bbox[2]
        text_width = text_right - text_left

        if text_width <= 0:
            return img_array

        # 各列について色を計算
        for x in range(width):
            if text_left <= x <= text_right:
                ratio = (x - text_left) / max(text_width, 1)
                color = self._interpolate_multi_color(colors, ratio)
                img_array[:, x] = color

        return img_array

    def _create_diagonal_gradient(
        self,
        width: int,
        height: int,
        bbox: Tuple[int, int, int, int],
        colors: List[Tuple[int, int, int]]
    ) -> np.ndarray:
        """
        斜め方向のグラデーションを生成

        Args:
            width: 画像幅
            height: 画像高さ
            bbox: テキストのバウンディングボックス
            colors: 色のリスト

        Returns:
            グラデーション画像（NumPy配列）
        """
        img_array = np.zeros((height, width, 3), dtype=np.float32)

        # 対角線の最大距離を計算
        max_distance = np.sqrt(width**2 + height**2)

        # 各ピクセルについて色を計算
        for y in range(height):
            for x in range(width):
                # 左上からの距離を計算
                distance = np.sqrt(x**2 + y**2)
                ratio = distance / max_distance
                color = self._interpolate_multi_color(colors, ratio)
                img_array[y, x] = color

        return img_array

    def _interpolate_multi_color(
        self,
        colors: List[Tuple[int, int, int]],
        ratio: float
    ) -> Tuple[float, float, float]:
        """
        複数色を補間

        Args:
            colors: 色のリスト [(R,G,B), ...]
            ratio: 補間比率（0.0〜1.0）

        Returns:
            補間された色 (R, G, B)
        """
        if len(colors) < 2:
            return colors[0] if colors else (255, 255, 255)

        # どの2色の間にあるかを計算
        segment_count = len(colors) - 1
        segment = min(int(ratio * segment_count), segment_count - 1)
        local_ratio = (ratio * segment_count) - segment

        # 2色を補間
        color1 = colors[segment]
        color2 = colors[segment + 1]

        r = color1[0] + (color2[0] - color1[0]) * local_ratio
        g = color1[1] + (color2[1] - color1[1]) * local_ratio
        b = color1[2] + (color2[2] - color1[2]) * local_ratio

        return (r, g, b)
