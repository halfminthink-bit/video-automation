"""
「教科書には載せてくれない」シリーズ専用テキストレンダラー

上部20%: 固定テキスト「教科書には載せてくれない」（白文字、黒縁）
下部20%: 可変テキスト（金色/黄色、極太黒縁）
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Tuple, Optional, List
import logging
from pathlib import Path


class TextbookTextRenderer:
    """「教科書には載せてくれない」シリーズ専用テキストレンダラー"""

    # 固定テキスト
    FIXED_TOP_TEXT = "教科書には載せてくれない"

    # カラーパレット
    TOP_TEXT_COLOR = (255, 255, 255)  # #FFFFFF - 白
    BOTTOM_TEXT_COLOR = (255, 215, 0)  # #FFD700 - 金色
    PRIMARY_STROKE_COLOR = (0, 0, 0)   # #000000 - 黒
    SECONDARY_STROKE_COLOR = (75, 0, 0)  # #4B0000 - 暗赤

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

        # レイアウト設定（20/60/20）
        self.layout = {
            "top_zone": 0.20,     # 上部20%
            "middle_zone": 0.60,  # 中央60%（人物画像エリア）
            "bottom_zone": 0.20,  # 下部20%
        }

        # フォントパスを検索
        self.font_path = self._find_font()

        self.logger.info(
            f"TextbookTextRenderer initialized: {canvas_size}, font={self.font_path}"
        )

    def _find_font(self) -> str:
        """日本語対応の太字フォントを検索"""
        font_candidates = [
            # プロジェクト内のフォント
            Path("assets/fonts/GenEiKiwamiGothic-EB.ttf"),
            Path("assets/fonts/NotoSansJP-Bold.ttf"),
            Path("assets/fonts/SourceHanSansJP-Bold.otf"),
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

    def render_top_text(self) -> Image.Image:
        """
        上部固定テキスト「教科書には載せてくれない」をレンダリング

        Returns:
            テキストレイヤー（RGBA）
        """
        text = self.FIXED_TOP_TEXT
        self.logger.debug(f"Rendering top text: '{text}'")

        # フォントサイズ
        font_size = 65
        font = ImageFont.truetype(self.font_path, font_size)

        # テキストサイズを取得
        dummy_img = Image.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # レイヤーサイズ（上部20%）
        layer_width = self.width
        layer_height = int(self.height * self.layout["top_zone"])
        layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))

        # テキスト位置（中央配置）
        text_x = (layer_width - text_width) // 2
        text_y = (layer_height - text_height) // 2

        # 1. シャドウを追加
        shadow_layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.text(
            (text_x + 5, text_y + 5),
            text,
            font=font,
            fill=(0, 0, 0, 200)  # #000000CC
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(8))
        layer = Image.alpha_composite(layer, shadow_layer)

        # 2. 太い黒縁（25px）
        draw = ImageDraw.Draw(layer)
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=self.PRIMARY_STROKE_COLOR,
            stroke_width=25,
            stroke_fill=self.PRIMARY_STROKE_COLOR
        )

        # 3. グレー縁（12px）- 立体感
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=(51, 51, 51),  # #333333
            stroke_width=12,
            stroke_fill=(51, 51, 51)
        )

        # 4. 白文字
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=self.TOP_TEXT_COLOR
        )

        self.logger.debug(f"✅ Top text rendered: {layer.size}")

        return layer

    def render_bottom_text(
        self,
        text: str,
        with_glow: bool = True
    ) -> Image.Image:
        """
        下部可変テキストをレンダリング（金色、極太黒縁）

        Args:
            text: テキスト（10-15文字推奨）
            with_glow: グロー効果を追加するか

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.debug(f"Rendering bottom text: '{text}'")

        # フォントサイズ（文字数で調整）
        char_count = len(text)
        if char_count <= 8:
            font_size = 80
        elif char_count <= 10:
            font_size = 75
        elif char_count <= 12:
            font_size = 70
        else:
            font_size = 65

        font = ImageFont.truetype(self.font_path, font_size)

        # テキストサイズを取得
        dummy_img = Image.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # レイヤーサイズ（下部20%）
        layer_width = self.width
        layer_height = int(self.height * self.layout["bottom_zone"])
        layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))

        # テキスト位置（中央配置）
        text_x = (layer_width - text_width) // 2
        text_y = (layer_height - text_height) // 2

        # 1. グロー効果（オプション）
        if with_glow:
            glow_layer = self._create_glow_effect(
                text,
                font,
                (text_x, text_y),
                (layer_width, layer_height)
            )
            layer = Image.alpha_composite(layer, glow_layer)

        # 2. 強いシャドウ
        shadow_layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.text(
            (text_x + 6, text_y + 6),
            text,
            font=font,
            fill=(0, 0, 0, 230)  # #000000E6
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(10))
        layer = Image.alpha_composite(layer, shadow_layer)

        # 3. 極太黒縁（30px）
        draw = ImageDraw.Draw(layer)
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=self.PRIMARY_STROKE_COLOR,
            stroke_width=30,
            stroke_fill=self.PRIMARY_STROKE_COLOR
        )

        # 4. 暗赤縁（15px）- 立体感と重厚感
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=self.SECONDARY_STROKE_COLOR,
            stroke_width=15,
            stroke_fill=self.SECONDARY_STROKE_COLOR
        )

        # 5. 金色テキスト
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=self.BOTTOM_TEXT_COLOR
        )

        self.logger.debug(f"✅ Bottom text rendered: {layer.size}")

        return layer

    def _create_glow_effect(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        position: Tuple[int, int],
        size: Tuple[int, int]
    ) -> Image.Image:
        """
        金色のグロー効果を作成

        Args:
            text: テキスト
            font: フォント
            position: テキスト位置 (x, y)
            size: レイヤーサイズ (width, height)

        Returns:
            グローレイヤー
        """
        glow_layer = Image.new('RGBA', size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)

        # 複数回描画してグローを強化
        for i in range(3):
            glow_draw.text(
                position,
                text,
                font=font,
                fill=(*self.BOTTOM_TEXT_COLOR, 76)  # 30%の不透明度
            )

        # ぼかしを適用
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(15))

        return glow_layer

    def get_layout_zones(self) -> dict:
        """
        レイアウトゾーンの情報を取得

        Returns:
            各ゾーンの開始・終了Y座標
        """
        return {
            "top": {
                "start": 0,
                "end": int(self.height * self.layout["top_zone"]),
                "height": int(self.height * self.layout["top_zone"])
            },
            "middle": {
                "start": int(self.height * self.layout["top_zone"]),
                "end": int(self.height * (1 - self.layout["bottom_zone"])),
                "height": int(self.height * self.layout["middle_zone"])
            },
            "bottom": {
                "start": int(self.height * (1 - self.layout["bottom_zone"])),
                "end": self.height,
                "height": int(self.height * self.layout["bottom_zone"])
            }
        }
