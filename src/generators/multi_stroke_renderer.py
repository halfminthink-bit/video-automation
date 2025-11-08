"""
多重縁取りレンダラー

3層以上の縁取りを実現し、テキストに存在感を与える
"""

from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Tuple, Optional, Any
import logging


class MultiStrokeRenderer:
    """3層以上の縁取りを実現するレンダラー"""

    # デフォルトの縁取り設定
    DEFAULT_STROKES = [
        {"width": 30, "color": (0, 0, 0), "opacity": 255},      # 外側: 黒 30px
        {"width": 18, "color": (255, 255, 255), "opacity": 255}, # 中間: 白 18px
        {"width": 8,  "color": "gradient_start", "opacity": 255} # 内側: グラデーション開始色 8px
    ]

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化

        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)

    def apply_multi_stroke(
        self,
        size: Tuple[int, int],
        text: str,
        position: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        strokes: Optional[List[Dict[str, Any]]] = None,
        gradient_start_color: Optional[Tuple[int, int, int]] = None
    ) -> Image.Image:
        """
        多重縁取りを適用

        Args:
            size: 画像サイズ (width, height)
            text: テキスト
            position: テキスト位置 (x, y)
            font: フォント
            strokes: 縁取り設定のリスト（Noneの場合はデフォルトを使用）
            gradient_start_color: グラデーション開始色（"gradient_start"用）

        Returns:
            多重縁取りが適用されたRGBA画像
        """
        width, height = size

        # 縁取り設定を取得
        if strokes is None:
            strokes = self.DEFAULT_STROKES.copy()

        self.logger.info(f"Applying multi-stroke: {len(strokes)} layers")

        # RGBA画像を作成
        stroke_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(stroke_layer)

        # 外側から順に縁取りを描画
        for i, stroke in enumerate(strokes):
            stroke_width = stroke.get("width", 10)
            stroke_color = stroke.get("color")
            stroke_opacity = stroke.get("opacity", 255)

            # "gradient_start"の場合は、グラデーション開始色を使用
            if stroke_color == "gradient_start" and gradient_start_color:
                color_rgb = gradient_start_color
            elif isinstance(stroke_color, str) and stroke_color.startswith("#"):
                # 16進数カラーコードをRGBに変換
                color_rgb = self._hex_to_rgb(stroke_color)
            elif isinstance(stroke_color, (tuple, list)):
                color_rgb = stroke_color
            else:
                color_rgb = (0, 0, 0)

            # RGBAカラーを作成
            color_rgba = color_rgb + (stroke_opacity,)

            self.logger.debug(
                f"Stroke layer {i+1}/{len(strokes)}: "
                f"width={stroke_width}px, color={color_rgba}"
            )

            # 縁取りを描画
            draw.text(
                position,
                text,
                font=font,
                fill=(0, 0, 0, 0),  # 透明（縁取りのみ）
                stroke_width=stroke_width,
                stroke_fill=color_rgba
            )

        self.logger.info("✅ Multi-stroke applied successfully")

        return stroke_layer

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """
        16進数カラーコードをRGBに変換

        Args:
            hex_color: "#RRGGBB"形式のカラーコード

        Returns:
            (R, G, B) タプル
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
