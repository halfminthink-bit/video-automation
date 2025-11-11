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
        上部テキストをレンダリング（金色、固定フレーズ、読みやすいサイズ）

        Args:
            text: テキスト（固定フレーズ）

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.debug(f"Rendering top text: '{text}'")

        # フォントサイズ（105px - よりインパクトを持たせる）
        font_size = 105
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

        # 1. シャドウ効果（控えめ）
        shadow_layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)

        # シャドウ
        for offset in range(10, 0, -2):
            shadow_opacity = int(180 * (offset / 10))
            shadow_draw.text(
                (text_x + offset, text_y + offset),
                text,
                font=font,
                fill=(0, 0, 0, shadow_opacity)
            )

        layer = Image.alpha_composite(layer, shadow_layer)

        # 2. 黒縁（20px - 適切なサイズ）
        draw = ImageDraw.Draw(layer)
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=self.TOP_TEXT_COLOR,
            stroke_width=20,  # 35 → 20pxに変更
            stroke_fill=self.STROKE_COLOR
        )

        self.logger.debug(f"✅ Top text rendered: {layer.size}")

        return layer

    def render_bottom_text(
        self,
        text: Optional[str] = None,
        line1: Optional[str] = None,
        line2: Optional[str] = None,
        with_background: bool = False
    ) -> Image.Image:
        """
        下部テキストをレンダリング（白文字、2行構成、読みやすいサイズ）

        Args:
            text: レガシー互換性のための単一テキスト（非推奨）
            line1: 1行目テキスト（10-15文字、衝撃的な事実）
            line2: 2行目テキスト（10-15文字、詳細説明）
            with_background: 半透明背景を追加するか（非推奨、デフォルトFalse）

        Returns:
            テキストレイヤー（RGBA）
        """
        # レガシー互換性: textが指定されている場合は改行で分割
        if text and not line1 and not line2:
            self.logger.debug(f"Rendering bottom text (legacy): '{text}'")
            lines_text = text.split('\n') if '\n' in text else [text]
            line1 = lines_text[0] if len(lines_text) > 0 else ""
            line2 = lines_text[1] if len(lines_text) > 1 else ""

        # デフォルト値
        line1 = line1 or ""
        line2 = line2 or ""

        self.logger.debug(f"Rendering bottom text: Line1='{line1}', Line2='{line2}'")

        # レイヤーサイズ（行間調整に合わせて高さを拡大）
        layer_width = self.width
        layer_height = 330  # 行間調整後も十分な余白を確保
        layer = Image.new('RGBA', (layer_width, layer_height), (0, 0, 0, 0))

        # 1. 半透明黒背景（オプション）
        if with_background:
            draw = ImageDraw.Draw(layer)
            draw.rectangle(
                [(0, 0), (layer_width, layer_height)],
                fill=(0, 0, 0, 140)
            )

        draw = ImageDraw.Draw(layer)

        # フォントサイズ（2行とも76pxで統一）
        font_size_line1 = 76
        font_size_line2 = 76

        font1 = ImageFont.truetype(self.font_path, font_size_line1)
        font2 = ImageFont.truetype(self.font_path, font_size_line2)

        # 行間とベースライン設定（縁取りを考慮して十分な間隔を確保）
        line_spacing = 110  # よりタイトな行間
        base_y = 140  # わずかに上げてバランスを調整

        # 1行目を描画
        if line1:
            # テキストサイズを取得
            dummy_img = Image.new('RGBA', (1, 1))
            dummy_draw = ImageDraw.Draw(dummy_img)
            bbox1 = dummy_draw.textbbox((0, 0), line1, font=font1)
            text_width1 = bbox1[2] - bbox1[0]

            # X座標（中央揃え）
            text_x1 = (layer_width - text_width1) // 2
            text_y1 = base_y

            # シャドウ効果
            for offset in range(10, 0, -2):
                shadow_opacity = int(180 * (offset / 10))
                draw.text(
                    (text_x1 + offset, text_y1 + offset),
                    line1,
                    font=font1,
                    fill=(0, 0, 0, shadow_opacity)
                )

            # メインテキスト（白文字・黒縁: 20px）
            draw.text(
                (text_x1, text_y1),
                line1,
                font=font1,
                fill=self.BOTTOM_TEXT_COLOR,
                stroke_width=20,  # 35 → 20pxに変更
                stroke_fill=self.STROKE_COLOR
            )

        # 2行目を描画
        if line2:
            # テキストサイズを取得
            dummy_img = Image.new('RGBA', (1, 1))
            dummy_draw = ImageDraw.Draw(dummy_img)
            bbox2 = dummy_draw.textbbox((0, 0), line2, font=font2)
            text_width2 = bbox2[2] - bbox2[0]

            # X座標（中央揃え）
            text_x2 = (layer_width - text_width2) // 2
            text_y2 = base_y + line_spacing

            # シャドウ効果
            for offset in range(10, 0, -2):
                shadow_opacity = int(180 * (offset / 10))
                draw.text(
                    (text_x2 + offset, text_y2 + offset),
                    line2,
                    font=font2,
                    fill=(0, 0, 0, shadow_opacity)
                )

            # メインテキスト（白文字・黒縁: 20px）
            draw.text(
                (text_x2, text_y2),
                line2,
                font=font2,
                fill=self.BOTTOM_TEXT_COLOR,
                stroke_width=20,  # 35 → 20pxに変更
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

    def render_vertical_text_right(self, text: str) -> Image.Image:
        """
        右側縦書きテキストをレンダリング（赤文字＋黒縁）

        改行（\n）で区切ると横に複数列を並べることができます。
        例: "革命か\n破壊か" → 2列表示

        Args:
            text: 縦書きテキスト（\nで列を区切る）

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.debug(f"Rendering vertical right text: '{text}'")

        # フォントサイズ: 100px（5文字用）
        font_size = 100
        font = ImageFont.truetype(self.font_path, font_size)

        # レイヤーサイズ
        layer = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        # 赤色設定（画像2のような赤）
        text_color = (220, 20, 60)  # Crimson #DC143C
        stroke_color = (0, 0, 0)     # 黒
        stroke_width = 18            # 縁の太さ

        # 開始Y座標（上部マージン）
        y_start = 100

        # 文字間隔
        char_spacing = font_size + 10  # 100 + 10 = 110px

        # 改行で列を分割
        columns = text.split('\n')

        # 列間隔
        column_spacing = 120  # 列と列の間隔

        # 右端からの開始位置（X座標）- 列数に応じて調整
        total_width = len(columns) * column_spacing
        x_start = self.width - 120  # 右端から120px内側

        # 各列を描画（右から左へ）
        for col_index, column_text in enumerate(columns):
            # 列のX座標（右から左へ配置）
            x_position = x_start - (col_index * column_spacing)

            # 1文字ずつ縦に描画
            for char_index, char in enumerate(column_text):
                y_position = y_start + (char_index * char_spacing)

                # シャドウ効果（控えめ）
                for offset in range(8, 0, -2):
                    shadow_opacity = int(150 * (offset / 8))
                    draw.text(
                        (x_position + offset, y_position + offset),
                        char,
                        font=font,
                        fill=(0, 0, 0, shadow_opacity)
                    )

                # メインテキスト（赤文字＋黒縁）
                draw.text(
                    (x_position, y_position),
                    char,
                    font=font,
                    fill=text_color,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_color
                )

        self.logger.debug(f"✅ Vertical right text rendered: {layer.size}, {len(columns)} columns")

        return layer

    def render_vertical_text_left(self, text: str) -> Image.Image:
        """
        左側縦書きテキストをレンダリング（白文字＋黒縁）

        改行（\n）で区切ると横に複数列を並べることができます。
        例: "戦国の\n常識を\n覆した男" → 3列表示

        Args:
            text: 縦書きテキスト（\nで列を区切る）

        Returns:
            テキストレイヤー（RGBA）
        """
        self.logger.debug(f"Rendering vertical left text: '{text}'")

        # フォントサイズ: 80px（より大きく）
        font_size = 80
        font = ImageFont.truetype(self.font_path, font_size)

        # レイヤーサイズ
        layer = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        # 白色設定
        text_color = (255, 255, 255)  # 白
        stroke_color = (0, 0, 0)       # 黒
        stroke_width = 15              # 縁の太さ

        # 開始Y座標（上部マージン）
        y_start = 100

        # 文字間隔（文字同士の縦の間隔を広げる）
        char_spacing = font_size + 15  # 80 + 15 = 95px

        # 改行で列を分割
        columns = text.split('\n')

        # 列間隔
        column_spacing = 100  # 列と列の間隔

        # 左端からの開始位置（X座標）
        x_start = 100  # 左端から100px内側

        # 各列を描画（右から左へ - 最初の列が右側）
        for col_index, column_text in enumerate(columns):
            # 列のX座標（右から左へ配置）
            # 最初の列（index=0）が一番右、最後の列が一番左
            x_position = x_start + ((len(columns) - 1 - col_index) * column_spacing)

            # 1文字ずつ縦に描画
            for char_index, char in enumerate(column_text):
                y_position = y_start + (char_index * char_spacing)

                # シャドウ効果（控えめ）
                for offset in range(8, 0, -2):
                    shadow_opacity = int(150 * (offset / 8))
                    draw.text(
                        (x_position + offset, y_position + offset),
                        char,
                        font=font,
                        fill=(0, 0, 0, shadow_opacity)
                    )

                # メインテキスト（白文字＋黒縁）
                draw.text(
                    (x_position, y_position),
                    char,
                    font=font,
                    fill=text_color,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_color
                )

        self.logger.debug(f"✅ Vertical left text rendered: {layer.size}, {len(columns)} columns")

        return layer

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
