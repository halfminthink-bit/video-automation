"""
V3テキストレンダラー

上部: 赤グラデーション（疑問形・衝撃系）
下部: 白文字＋黒縁（説明文）
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Tuple, Optional, List
import logging
import numpy as np
from pathlib import Path


class V3TextRenderer:
    """V3.0仕様のテキストレンダラー"""

    # 赤グラデーション配色
    RED_GRADIENT_COLORS = [
        (255, 0, 0),      # #FF0000 - 濃い赤
        (255, 107, 107),  # #FF6B6B - 中間赤
        (255, 170, 170),  # #FFAAAA - 薄い赤
    ]

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

        # フォントパスを検索
        self.font_path = self._find_font()

        self.logger.info(f"V3TextRenderer initialized: {canvas_size}, font={self.font_path}")

    def _find_font(self) -> str:
        """フォントファイルを検索"""
        font_candidates = [
            # プロジェクト内のフォント
            Path("assets/fonts/NotoSansJP-Bold.ttf"),
            Path("assets/fonts/SourceHanSansJP-Bold.otf"),
            Path("assets/fonts/GenEiKyuhikiGothic-Bold.ttf"),
            # Windowsフォント
            Path("C:/Windows/Fonts/msgothic.ttc"),
            Path("C:/Windows/Fonts/meiryo.ttc"),
            # Linuxフォント
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        ]

        for font_path in font_candidates:
            if font_path.exists():
                self.logger.info(f"Found font: {font_path}")
                return str(font_path)

        # デフォルト
        self.logger.warning("No font found, using default")
        return "arial.ttf"

    def render_main_text(
        self,
        text: str,
        zone_height: int
    ) -> Image.Image:
        """
        上部メインテキストをレンダリング（赤グラデーション）

        Args:
            text: テキスト（5-8文字）
            position: 中心位置 (x, y)

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.debug(f"Rendering main text: '{text}'")

        # フォントサイズを動的に計算
        max_width = int(self.width * 0.9)
        max_height = max(zone_height - 40, 100)
        font, font_size, line_spacing = self._get_fitting_font(
            text=text,
            max_width=max_width,
            max_height=max_height,
            initial_size=int(zone_height * 1.4),
            min_size=120,
            stroke_ratio=0.16,
            line_spacing_ratio=0.12
        )

        stroke_black = max(28, int(font_size * 0.16))
        stroke_white = max(14, int(font_size * 0.08))
        shadow_offset = max(10, int(font_size * 0.05))
        shadow_blur = max(12, int(font_size * 0.05))

        # テキストサイズ（ストローク込み）を取得
        dummy_img = Image.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=stroke_black,
            spacing=line_spacing
        )
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        layer = Image.new('RGBA', (self.width, zone_height), (0, 0, 0, 0))
        text_x = (self.width - text_width) // 2
        text_y = max((zone_height - text_height) // 2, 0)

        # 1. シャドウを追加
        shadow_layer = Image.new('RGBA', (self.width, zone_height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.text(
            (text_x + shadow_offset, text_y + shadow_offset),
            text,
            font=font,
            fill=(0, 0, 0, 180),
            stroke_width=stroke_black,
            stroke_fill=(0, 0, 0, 180),
            spacing=line_spacing
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur))
        layer = Image.alpha_composite(layer, shadow_layer)

        # 2. 黒縁
        draw = ImageDraw.Draw(layer)
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=(0, 0, 0, 255),
            stroke_width=stroke_black,
            stroke_fill=(0, 0, 0, 255),
            spacing=line_spacing
        )

        # 3. 白縁
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke_white,
            stroke_fill=(255, 255, 255, 255),
            spacing=line_spacing
        )

        # 4. 赤グラデーションテキスト
        gradient_text = self._create_vertical_gradient_text(
            text,
            font,
            (text_x, text_y),
            (self.width, zone_height),
            self.RED_GRADIENT_COLORS,
            spacing=line_spacing
        )
        layer = Image.alpha_composite(layer, gradient_text)

        self.logger.debug(
            f"✅ Main text rendered: {layer.size}, font={font_size}, spacing={line_spacing}"
        )

        return layer

    def render_sub_text(
        self,
        text: str,
        zone_height: int,
        with_background: bool = True
    ) -> Image.Image:
        """
        下部サブテキストをレンダリング（白＋黒縁）

        Args:
            text: テキスト（15-25文字）
            position: 中心位置 (x, y)
            with_background: 半透明背景を追加するか

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.debug(f"Rendering sub text: '{text}'")

        max_width = int(self.width * 0.92)
        max_height = max(zone_height - 40, 120)
        font, font_size, line_spacing = self._get_fitting_font(
            text=text,
            max_width=max_width,
            max_height=max_height,
            initial_size=int(zone_height * 0.9),
            min_size=60,
            stroke_ratio=0.12,
            line_spacing_ratio=0.10
        )

        stroke_width = max(12, int(font_size * 0.12))

        dummy_img = Image.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=stroke_width,
            spacing=line_spacing
        )
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        layer_width = self.width
        layer_height = zone_height
        layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))

        # 1. 半透明黒背景を追加（オプション）
        if with_background:
            bg_layer = self._create_text_background(
                text,
                font,
                (layer_width, layer_height),
                stroke_width=stroke_width,
                spacing=line_spacing
            )
            layer = Image.alpha_composite(layer, bg_layer)

        # 2. テキスト位置（中央）
        text_x = (layer_width - text_width) // 2
        text_y = (layer_height - text_height) // 2

        # 3. 白文字＋黒縁（10px）
        draw = ImageDraw.Draw(layer)
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, 255),
            spacing=line_spacing
        )

        self.logger.debug(
            f"✅ Sub text rendered: {layer.size}, font={font_size}, spacing={line_spacing}"
        )

        return layer

    def _create_vertical_gradient_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        position: Tuple[int, int],
        size: Tuple[int, int],
        colors: List[Tuple[int, int, int]],
        spacing: int
    ) -> Image.Image:
        """
        縦方向のグラデーションテキストを作成

        Args:
            text: テキスト
            font: フォント
            position: テキスト位置 (x, y)
            size: レイヤーサイズ (width, height)
            colors: グラデーション色リスト

        Returns:
            グラデーションテキストレイヤー
        """
        # テキストサイズを取得
        dummy_img = Image.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), text, font=font, spacing=spacing)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # グラデーションマスクを作成
        gradient_mask = Image.new('L', (text_width, text_height))
        gradient_array = np.zeros((text_height, text_width), dtype=np.uint8)

        # 縦方向グラデーション（上から下へ）
        for y in range(text_height):
            ratio = y / max(text_height - 1, 1)

            # 色を補間
            if len(colors) == 3:
                if ratio < 0.5:
                    # 1色目から2色目へ
                    local_ratio = ratio * 2
                    r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * local_ratio)
                    g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * local_ratio)
                    b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * local_ratio)
                else:
                    # 2色目から3色目へ
                    local_ratio = (ratio - 0.5) * 2
                    r = int(colors[1][0] + (colors[2][0] - colors[1][0]) * local_ratio)
                    g = int(colors[1][1] + (colors[2][1] - colors[1][1]) * local_ratio)
                    b = int(colors[1][2] + (colors[2][2] - colors[1][2]) * local_ratio)
            else:
                # 2色の場合
                r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * ratio)
                g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * ratio)
                b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * ratio)

            gradient_array[y, :] = int(0.299 * r + 0.587 * g + 0.114 * b)

        gradient_mask = Image.fromarray(gradient_array, mode='L')

        # グラデーション画像を作成
        gradient_img = Image.new('RGBA', (text_width, text_height))
        gradient_array_rgb = np.zeros((text_height, text_width, 4), dtype=np.uint8)

        for y in range(text_height):
            ratio = y / max(text_height - 1, 1)

            # 色を補間
            if len(colors) == 3:
                if ratio < 0.5:
                    local_ratio = ratio * 2
                    r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * local_ratio)
                    g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * local_ratio)
                    b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * local_ratio)
                else:
                    local_ratio = (ratio - 0.5) * 2
                    r = int(colors[1][0] + (colors[2][0] - colors[1][0]) * local_ratio)
                    g = int(colors[1][1] + (colors[2][1] - colors[1][1]) * local_ratio)
                    b = int(colors[1][2] + (colors[2][2] - colors[1][2]) * local_ratio)
            else:
                r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * ratio)
                g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * ratio)
                b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * ratio)

            gradient_array_rgb[y, :] = [r, g, b, 255]

        gradient_img = Image.fromarray(gradient_array_rgb, mode='RGBA')

        # テキストマスクを作成
        text_mask = Image.new('L', (text_width, text_height), 0)
        text_mask_draw = ImageDraw.Draw(text_mask)
        text_mask_draw.text((0, 0), text, font=font, fill=255, spacing=spacing)

        # グラデーションをテキスト形状でマスク
        gradient_text = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
        gradient_text.paste(gradient_img, (0, 0), text_mask)

        # レイヤーに配置
        result = Image.new('RGBA', size, (0, 0, 0, 0))
        result.paste(gradient_text, position, gradient_text)

        return result

    def _create_text_background(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        size: Tuple[int, int],
        stroke_width: int,
        spacing: int
    ) -> Image.Image:
        """
        テキスト用の半透明黒背景を作成

        Args:
            text: テキスト
            font: フォント
            size: レイヤーサイズ (width, height)

        Returns:
            背景レイヤー
        """
        # テキストサイズを取得
        dummy_img = Image.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=stroke_width,
            spacing=spacing
        )
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 背景レイヤーを作成
        bg_layer = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(bg_layer)

        # 背景矩形の位置とサイズ（パディング20px）
        padding = max(24, int(font.size * 0.25))
        bg_x1 = (size[0] - text_width) // 2 - padding
        bg_y1 = (size[1] - text_height) // 2 - padding
        bg_x2 = bg_x1 + text_width + padding * 2
        bg_y2 = bg_y1 + text_height + padding * 2

        # 半透明黒矩形
        draw.rectangle(
            [bg_x1, bg_y1, bg_x2, bg_y2],
            fill=(0, 0, 0, 150)
        )

        # ぼかしを適用
        bg_layer = bg_layer.filter(ImageFilter.GaussianBlur(6))

        return bg_layer

    def _get_fitting_font(
        self,
        text: str,
        max_width: int,
        max_height: int,
        initial_size: int,
        min_size: int,
        stroke_ratio: float,
        line_spacing_ratio: float
    ) -> Tuple[ImageFont.FreeTypeFont, int, int]:
        """
        指定範囲内に収まるフォントを取得

        Args:
            text: テキスト
            max_width: 最大幅
            max_height: 最大高さ
            initial_size: 探索開始フォントサイズ
            min_size: 最小フォントサイズ
            stroke_ratio: フォントサイズに対するストローク割合
            line_spacing_ratio: フォントサイズに対する行間割合

        Returns:
            (フォント, サイズ, 行間)
        """
        size = initial_size
        dummy_img = Image.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)

        while size >= min_size:
            font = ImageFont.truetype(self.font_path, size)
            stroke_width = max(1, int(size * stroke_ratio))
            spacing = max(0, int(size * line_spacing_ratio))

            bbox = dummy_draw.textbbox(
                (0, 0),
                text,
                font=font,
                stroke_width=stroke_width,
                spacing=spacing
            )

            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            if text_width <= max_width and text_height <= max_height:
                return font, size, spacing

            size -= 4

        self.logger.warning(
            "Falling back to minimum font size for text '%s'", text
        )
        font = ImageFont.truetype(self.font_path, min_size)
        spacing = max(0, int(min_size * line_spacing_ratio))
        return font, min_size, spacing
