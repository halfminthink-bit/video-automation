"""
知的好奇心サムネイル専用テキストレンダラー

上部: 黄色/金色、10文字以内、超インパクト
下部: 白文字、10-20文字、1-2行、詳細説明
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Tuple, Optional
import logging
from pathlib import Path


class IntellectualCuriosityTextRenderer:
    """知的好奇心サムネイル専用テキストレンダラー"""

    # カラーパレット
    TOP_TEXT_COLOR = (255, 215, 0)  # #FFD700 - 金色/黄色
    BOTTOM_TEXT_COLOR = (255, 255, 255)  # #FFFFFF - 白
    STROKE_COLOR = (0, 0, 0)  # #000000 - 黒

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

        # レイアウト設定
        self.layout = {
            "top_area_height": 200,    # 上部エリア
            "middle_area_height": 340,  # 中央エリア（画像用）
            "bottom_area_height": 180,  # 下部エリア
        }

        # フォントパスを検索
        self.font_path = self._find_font()

        self.logger.info(
            f"IntellectualCuriosityTextRenderer initialized: {canvas_size}, "
            f"font={self.font_path}"
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

    def render_top_text(self, text: str) -> Image.Image:
        """
        上部テキストをレンダリング（黄色/金色、10文字以内、超インパクト）

        Args:
            text: テキスト（10文字以内）

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.debug(f"Rendering top text: '{text}'")

        # 文字数確認
        char_count = len(text)
        if char_count > 10:
            self.logger.warning(f"Top text exceeds 10 chars: {char_count}")

        # フォントサイズ（超大きく）
        font_size = 90
        font = ImageFont.truetype(self.font_path, font_size)

        # テキストサイズを取得
        dummy_img = Image.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # レイヤーサイズ
        layer_width = self.width
        layer_height = self.layout["top_area_height"]
        layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))

        # テキスト位置（中央配置）
        text_x = (layer_width - text_width) // 2
        text_y = (layer_height - text_height) // 2

        # 1. 強力なグロー効果（黄金色）
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

        # 多重シャドウ
        for offset in range(12, 0, -2):
            shadow_opacity = int(200 * (offset / 12))
            shadow_draw.text(
                (text_x + offset, text_y + offset),
                text,
                font=font,
                fill=(0, 0, 0, shadow_opacity)
            )

        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(8))
        layer = Image.alpha_composite(layer, shadow_layer)

        # 3. 極太黒縁（35px）
        draw = ImageDraw.Draw(layer)
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=self.STROKE_COLOR,
            stroke_width=35,  # 30 → 35pxに強化
            stroke_fill=self.STROKE_COLOR
        )

        # 4. 金色テキスト
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
        with_background: bool = False  # デフォルトをFalseに変更
    ) -> Image.Image:
        """
        下部テキストをレンダリング（白文字、大きく、半透明背景なし）

        Args:
            text: テキスト（10-20文字、改行可）
            with_background: 半透明背景を追加するか（非推奨、デフォルトFalse）

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.debug(f"Rendering bottom text: '{text}'")

        # 改行で分割
        lines = text.split('\n') if '\n' in text else [text]

        # 1行が長すぎる場合は自動改行
        processed_lines = []
        for line in lines:
            if len(line) > 20:
                # 20文字で分割
                processed_lines.append(line[:20])
                if len(line) > 20:
                    processed_lines.append(line[20:])
            else:
                processed_lines.append(line)

        lines = processed_lines[:2]  # 最大2行

        # フォントサイズ（大きく統一: 90px）
        font_size = 90

        font = ImageFont.truetype(self.font_path, font_size)

        # レイヤーサイズ
        layer_width = self.width
        layer_height = self.layout["bottom_area_height"]
        layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))

        # 1. 半透明黒背景を削除（with_backgroundがTrueの場合のみ追加）
        if with_background:
            draw = ImageDraw.Draw(layer)
            draw.rectangle(
                [(0, 0), (layer_width, layer_height)],
                fill=(0, 0, 0, 140)
            )

        # 2. 各行を描画
        draw = ImageDraw.Draw(layer)

        # Y座標の計算（中央揃え）
        # フォントサイズが大きくなったので行間を調整
        line_spacing = font_size * 1.1  # 行間を少し狭く
        total_text_height = len(lines) * line_spacing
        y_offset = (layer_height - total_text_height) // 2

        for i, line in enumerate(lines):
            # テキストサイズを取得
            dummy_img = Image.new('RGBA', (1, 1))
            dummy_draw = ImageDraw.Draw(dummy_img)
            bbox = dummy_draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]

            # X座標（中央揃え）
            text_x = (layer_width - text_width) // 2
            text_y = y_offset + (i * line_spacing)

            # 強化されたシャドウ効果（可読性確保）
            for offset in range(12, 0, -2):
                shadow_opacity = int(200 * (offset / 12))
                draw.text(
                    (text_x + offset, text_y + offset),
                    line,
                    font=font,
                    fill=(0, 0, 0, shadow_opacity)
                )

            # メインテキスト（白文字・太い黒縁: 35px）
            draw.text(
                (text_x, text_y),
                line,
                font=font,
                fill=self.BOTTOM_TEXT_COLOR,
                stroke_width=35,  # 20 → 35pxに強化
                stroke_fill=self.STROKE_COLOR
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

        # グラデーション的なグロー（複数回描画）
        for glow_size in range(25, 0, -5):
            glow_opacity = int(120 * (glow_size / 25))
            glow_draw.text(
                position,
                text,
                font=font,
                fill=(*self.TOP_TEXT_COLOR, glow_opacity),
                stroke_width=glow_size + 30,
                stroke_fill=(0, 0, 0, glow_opacity)
            )

        # ぼかしを適用
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(20))

        return glow_layer

    def get_layout_zones(self) -> dict:
        """
        レイアウトゾーンの情報を取得

        Returns:
            各ゾーンの開始・終了Y座標
        """
        top_height = self.layout["top_area_height"]
        middle_height = self.layout["middle_area_height"]
        bottom_height = self.layout["bottom_area_height"]

        return {
            "top": {
                "start": 0,
                "end": top_height,
                "height": top_height
            },
            "middle": {
                "start": top_height,
                "end": top_height + middle_height,
                "height": middle_height
            },
            "bottom": {
                "start": top_height + middle_height,
                "end": top_height + middle_height + bottom_height,
                "height": bottom_height
            }
        }
