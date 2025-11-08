"""
2段テキスト用の強化レンダラー

メインキャッチ（巨大）とサブ説明文（中サイズ）を異なるスタイルで描画
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import logging
import os


# 配色スキーム定義
COLOR_SCHEMES = {
    "fire": {
        "main_gradient": [(255, 255, 255), (255, 255, 0), (255, 0, 0)],  # 白→黄→赤
        "sub_gradient": [(255, 255, 255), (255, 215, 0)],                 # 白→金
        "description": "炎・情熱系"
    },
    "ocean": {
        "main_gradient": [(255, 255, 255), (0, 255, 255), (0, 128, 255)],  # 白→シアン→青
        "sub_gradient": [(255, 255, 255), (0, 206, 209)],                   # 白→ターコイズ
        "description": "海・清潔系"
    },
    "royal": {
        "main_gradient": [(255, 215, 0), (255, 99, 71), (139, 0, 139)],  # 金→赤→紫
        "sub_gradient": [(255, 215, 0), (255, 165, 0)],                   # 金→オレンジ
        "description": "王室・高貴系"
    },
    "nature": {
        "main_gradient": [(144, 238, 144), (255, 255, 0), (255, 99, 71)],  # 緑→黄→赤
        "sub_gradient": [(255, 255, 255), (144, 238, 144)],                 # 白→緑
        "description": "自然・生命系"
    },
    "electric": {
        "main_gradient": [(255, 255, 255), (255, 20, 147), (0, 255, 255)],  # 白→ピンク→シアン
        "sub_gradient": [(255, 255, 255), (255, 182, 193)],                  # 白→ライトピンク
        "description": "電気・未来系"
    }
}


class EnhancedTextRenderer:
    """2段テキスト用の強化レンダラー"""

    def __init__(
        self,
        canvas_size: Tuple[int, int] = (1280, 720),
        font_path: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            canvas_size: キャンバスサイズ
            font_path: フォントパス
            logger: ロガー
        """
        self.width, self.height = canvas_size
        self.font_path = font_path or self._find_font()
        self.logger = logger or logging.getLogger(__name__)

        self.logger.info(f"EnhancedTextRenderer initialized with font: {self.font_path}")

    def _find_font(self) -> str:
        """フォントを検索"""
        project_root = Path(__file__).parent.parent.parent

        font_candidates = [
            project_root / "assets" / "fonts" / "NotoSansJP-Bold.ttf",
            project_root / "assets" / "fonts" / "GenEiKiwamiGothic-EB.ttf",
            r"C:\Windows\Fonts\msgothic.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        ]

        for font_path in font_candidates:
            font_path = Path(font_path)
            if font_path.exists():
                return str(font_path)

        raise FileNotFoundError("フォントが見つかりません")

    def render_main_text(
        self,
        text: str,
        position: Dict[str, int],
        color_scheme: str = "fire"
    ) -> Image.Image:
        """
        メインキャッチのレンダリング

        Args:
            text: テキスト
            position: 位置情報
            color_scheme: 配色スキーム

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.info(f"Rendering main text: '{text}' (scheme={color_scheme})")

        # フォントサイズ（文字数で自動調整）
        char_count = len(text)
        if char_count <= 5:
            font_size = 180
        elif char_count <= 7:
            font_size = 150
        else:
            font_size = 120

        # フォント読み込み
        font = self._load_font(font_size)

        # レイヤー作成
        layer = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        x, y = position["x"], position["y"]

        # 配色を取得
        scheme = COLOR_SCHEMES.get(color_scheme, COLOR_SCHEMES["fire"])
        gradient_colors = scheme["main_gradient"]

        # 1. 外側の黒縁（35px）
        draw.text((x, y), text, font=font, fill=(0, 0, 0, 0),
                  stroke_width=35, stroke_fill=(0, 0, 0, 255), anchor="mm")

        # 2. 白縁（20px）
        draw.text((x, y), text, font=font, fill=(0, 0, 0, 0),
                  stroke_width=20, stroke_fill=(255, 255, 255, 255), anchor="mm")

        # 3. グラデーション本体（簡易版）
        # 最も濃い色を使用
        main_color = gradient_colors[-1] if gradient_colors else (255, 0, 0)
        draw.text((x, y), text, font=font, fill=main_color + (255,), anchor="mm")

        self.logger.info("Main text rendered")

        return layer

    def render_sub_text(
        self,
        text: str,
        position: Dict[str, int],
        color_scheme: str = "fire",
        with_background_band: bool = True
    ) -> Image.Image:
        """
        サブ説明文のレンダリング

        Args:
            text: テキスト
            position: 位置情報
            color_scheme: 配色スキーム
            with_background_band: 背景帯を追加するか

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.info(f"Rendering sub text: '{text}' (scheme={color_scheme})")

        # フォントサイズ（中サイズ）
        font_size = 50
        font = self._load_font(font_size)

        # レイヤー作成
        layer = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        x, y = position["x"], position["y"]

        # 背景帯を追加
        if with_background_band:
            layer = self._add_background_band(layer, text, font, x, y)
            draw = ImageDraw.Draw(layer)

        # 配色を取得
        scheme = COLOR_SCHEMES.get(color_scheme, COLOR_SCHEMES["fire"])
        sub_colors = scheme["sub_gradient"]

        # 1. 黒縁（12px）
        draw.text((x, y), text, font=font, fill=(0, 0, 0, 0),
                  stroke_width=12, stroke_fill=(0, 0, 0, 255), anchor="mm")

        # 2. 白縁（6px）
        draw.text((x, y), text, font=font, fill=(0, 0, 0, 0),
                  stroke_width=6, stroke_fill=(255, 255, 255, 255), anchor="mm")

        # 3. テキスト本体（白または金色）
        text_color = sub_colors[-1] if len(sub_colors) > 1 else (255, 255, 255)
        draw.text((x, y), text, font=font, fill=text_color + (255,), anchor="mm")

        self.logger.info("Sub text rendered")

        return layer

    def _add_background_band(
        self,
        layer: Image.Image,
        text: str,
        font: ImageFont.FreeTypeFont,
        x: int,
        y: int
    ) -> Image.Image:
        """
        テキストの背景に半透明の黒帯を追加

        Args:
            layer: レイヤー
            text: テキスト
            font: フォント
            x: X座標
            y: Y座標

        Returns:
            背景帯追加後のレイヤー
        """
        # テキストのバウンディングボックスを取得
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 帯のサイズ
        band_width = text_width + 100  # 左右50pxずつ余白
        band_height = text_height + 30  # 上下15pxずつ余白

        # 帯を作成
        band = Image.new("RGBA", (band_width, band_height), (0, 0, 0, 180))

        # 端をぼかす
        band = band.filter(ImageFilter.GaussianBlur(3))

        # レイヤーに貼り付け
        band_x = x - (band_width // 2)
        band_y = y - (band_height // 2)
        layer.paste(band, (band_x, band_y), band)

        return layer

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """フォントを読み込み"""
        try:
            if self.font_path.endswith('.ttc'):
                return ImageFont.truetype(self.font_path, size, index=0)
            else:
                return ImageFont.truetype(self.font_path, size)
        except Exception as e:
            self.logger.error(f"Failed to load font: {e}")
            return ImageFont.load_default()
