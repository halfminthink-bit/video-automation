"""
サムネイル生成ジェネレーター（改善版）

超インパクトのあるグラデーション＋立体感テキストを実装
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import logging
import numpy as np


class ThumbnailGenerator:
    """YouTubeサムネイル生成クラス（改善版）"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Args:
            config: thumbnail_generation.yamlの設定
            logger: ロガー
        """
        self.config = config
        self.logger = logger
        
        # 設定を読み込み
        self.output_config = config.get("output", {})
        self.resolution = tuple(self.output_config.get("resolution", [1280, 720]))
        self.format = self.output_config.get("format", "png")
        self.quality = self.output_config.get("quality", 95)
        self.num_patterns = self.output_config.get("patterns", 5)
        
        self.image_selection_config = config.get("image_selection", {})
        self.text_config = config.get("text_generation", {})
        self.font_config = config.get("fonts", {})
        self.text_style_config = config.get("text_style", {})
        self.layout_config = config.get("layout", {})
        self.image_processing_config = config.get("image_processing", {})
        
        self.logger.info(f"ThumbnailGenerator initialized: {self.resolution[0]}x{self.resolution[1]}, {self.num_patterns} patterns")
    
    # ============================================
    # 既存のメソッド（select_best_image, generate_titles など）
    # ここは元のコードと同じなので省略
    # ============================================
    
    def _load_japanese_font(self, size: int) -> ImageFont.FreeTypeFont:
        """
        YouTubeサムネイルに最適な日本語フォントを読み込む
        
        優先順位:
        1. assets/fonts/内のインパクトフォント
        2. システムフォント（Noto Sans CJK JP Black/Bold）
        3. デフォルトフォント
        
        Args:
            size: フォントサイズ
            
        Returns:
            フォントオブジェクト
        """
        # YouTubeサムネイル向けフォントの優先順位リスト
        font_candidates = [
            # assets/fonts/内のインパクトフォント
            "assets/fonts/GenEiKiwamiGothic-EB.ttf",  # 源暎きわみゴ ⭐最優先
            "assets/fonts/GN-KillGothic-U-KanaNB.ttf",  # キルゴU ⭐超人気
            "assets/fonts/Corporate-Logo-ver3.otf",  # コーポレートロゴ
            "assets/fonts/DelaGothicOne-Regular.ttf",  # デラゴシック
            "assets/fonts/NotoSansJP-Black.otf",  # Noto Sans JP Black
            
            # システムフォント（Black > Bold の順）
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansJP-Black.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansJP-Black.otf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansJP-Bold.ttf",
        ]
        
        # プロジェクトルートからの相対パスを解決
        project_root = Path(__file__).parent.parent.parent
        
        for font_path_str in font_candidates:
            font_path = Path(font_path_str)
            
            # 相対パスの場合はプロジェクトルートから解決
            if not font_path.is_absolute():
                font_path = project_root / font_path
            
            if font_path.exists():
                try:
                    font = ImageFont.truetype(str(font_path), size)
                    self.logger.info(f"✓ Loaded impact font: {font_path.name}")
                    return font
                except Exception as e:
                    self.logger.debug(f"Failed to load font {font_path}: {e}")
                    continue
        
        # すべて失敗した場合はデフォルトフォント
        self.logger.warning("⚠ Impact font not found, using default font")
        return ImageFont.load_default()
    
    def _create_gradient_text_mask(
        self,
        img_size: Tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        position: Tuple[int, int],
        gradient_colors: List[Tuple[int, int, int]],
        vertical: bool = True
    ) -> Image.Image:
        """
        グラデーション文字のマスクを作成
        
        Args:
            img_size: 画像サイズ (width, height)
            text: テキスト
            font: フォント
            position: テキスト位置 (x, y)
            gradient_colors: グラデーション色のリスト [(R,G,B), ...]
            vertical: 縦方向のグラデーション（True）か横方向（False）
            
        Returns:
            グラデーション適用後の画像
        """
        width, height = img_size
        
        # テキストマスクを作成（白黒）
        mask = Image.new('L', (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.text(position, text, font=font, fill=255)
        
        # グラデーション画像を作成
        gradient = Image.new('RGB', (width, height))
        gradient_draw = ImageDraw.Draw(gradient)
        
        # テキストの境界を取得
        bbox = draw.textbbox(position, text, font=font)
        text_height = bbox[3] - bbox[1]
        text_width = bbox[2] - bbox[0]
        
        if vertical:
            # 縦方向のグラデーション
            for y in range(height):
                # テキスト範囲内のみグラデーション
                if bbox[1] <= y <= bbox[3]:
                    # テキスト内での相対位置（0.0〜1.0）
                    ratio = (y - bbox[1]) / max(text_height, 1)
                    
                    # グラデーション色を補間
                    if len(gradient_colors) == 2:
                        # 2色の場合
                        color = self._interpolate_color(gradient_colors[0], gradient_colors[1], ratio)
                    else:
                        # 3色以上の場合
                        color = self._interpolate_multi_color(gradient_colors, ratio)
                    
                    gradient_draw.line([(0, y), (width, y)], fill=color)
        else:
            # 横方向のグラデーション
            for x in range(width):
                if bbox[0] <= x <= bbox[2]:
                    ratio = (x - bbox[0]) / max(text_width, 1)
                    color = self._interpolate_multi_color(gradient_colors, ratio)
                    gradient_draw.line([(x, 0), (x, height)], fill=color)
        
        # マスクを使ってグラデーションを適用
        result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        result.paste(gradient, (0, 0), mask)
        
        return result
    
    def _interpolate_color(
        self,
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
        ratio: float
    ) -> Tuple[int, int, int]:
        """
        2色を補間
        
        Args:
            color1: 開始色 (R, G, B)
            color2: 終了色 (R, G, B)
            ratio: 補間比率（0.0〜1.0）
            
        Returns:
            補間された色 (R, G, B)
        """
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        return (r, g, b)
    
    def _interpolate_multi_color(
        self,
        colors: List[Tuple[int, int, int]],
        ratio: float
    ) -> Tuple[int, int, int]:
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

        return self._interpolate_color(colors[segment], colors[segment + 1], local_ratio)

    def _apply_vignette(self, img: Image.Image, strength: float = 0.6) -> Image.Image:
        """
        ビネット効果（周辺減光）を適用

        Args:
            img: 元画像
            strength: ビネットの強さ（0.0〜1.0）

        Returns:
            ビネット効果適用後の画像
        """
        width, height = img.size

        # 楕円形のマスクを作成
        mask = Image.new('L', (width, height), 255)
        mask_draw = ImageDraw.Draw(mask)

        # 中心から周辺に向かって暗くなるグラデーション
        for i in range(100):
            # 中心から外側へ
            ratio = i / 100.0
            alpha = int(255 * (1 - strength * ratio))

            # 楕円のサイズを計算
            margin_x = int(width * ratio * 0.4)
            margin_y = int(height * ratio * 0.4)

            bbox = [
                margin_x,
                margin_y,
                width - margin_x,
                height - margin_y
            ]

            mask_draw.ellipse(bbox, fill=alpha)

        # 元画像にマスクを適用
        if img.mode == 'RGB':
            img = img.convert('RGBA')

        # 黒い背景を作成
        black_bg = Image.new('RGBA', (width, height), (0, 0, 0, 255))

        # ビネット効果を合成
        result = Image.composite(img, black_bg, mask)

        return result
    
    def _add_text_to_image_impact(
        self,
        img: Image.Image,
        title: str,
        pattern_index: int
    ) -> Image.Image:
        """
        超インパクトのあるグラデーションテキストを追加

        Args:
            img: ベース画像
            title: タイトルテキスト
            pattern_index: パターンインデックス

        Returns:
            テキスト追加後の画像
        """
        # =========================================
        # 背景処理の改善（文字を際立たせる）
        # =========================================
        # 1. 彩度を下げる（0.7倍）
        enhancer_saturation = ImageEnhance.Color(img)
        img = enhancer_saturation.enhance(0.7)

        # 2. 明度を下げる（0.6倍）
        enhancer_brightness = ImageEnhance.Brightness(img)
        img = enhancer_brightness.enhance(0.6)

        # 3. ビネット効果の強化（周辺減光）
        img = self._apply_vignette(img, strength=0.6)

        # RGBA変換（透明度を扱うため）
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # フォントサイズを文字数に応じて動的に決定
        # 超インパクト重視：5文字以下=180px, 6-10文字=150px, 11文字以上=120px
        title_length = len(title)
        if title_length <= 5:
            font_size = 180
        elif title_length <= 10:
            font_size = 150
        else:
            font_size = 120

        self.logger.info(f"Title length: {title_length} chars, Font size: {font_size}px")

        # インパクトフォントを読み込み
        font = self._load_japanese_font(font_size)
        
        # テキスト位置を計算
        text_positions = self.layout_config.get("text_positions", ["bottom_center"])
        position_type = text_positions[pattern_index % len(text_positions)]
        
        # テキストサイズを取得
        temp_draw = ImageDraw.Draw(img)
        bbox = temp_draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 位置を計算
        width, height = img.size
        margins = self.layout_config.get("margins", {})
        
        if position_type == "top_center":
            x = (width - text_width) // 2
            y = margins.get("top", 60)
        elif position_type == "center_center":
            x = (width - text_width) // 2
            y = (height - text_height) // 2
        elif position_type == "bottom_center":
            x = (width - text_width) // 2
            y = height - text_height - margins.get("bottom", 60)
        elif position_type == "top_left":
            x = margins.get("left", 60)
            y = margins.get("top", 60)
        elif position_type == "bottom_right":
            x = width - text_width - margins.get("right", 60)
            y = height - text_height - margins.get("bottom", 60)
        else:
            x = (width - text_width) // 2
            y = height - text_height - margins.get("bottom", 60)
        
        # パターン別のグラデーション色を定義（指示書準拠）
        gradient_patterns = [
            # パターン1: 白→赤→黄（ホットな印象）
            [(255, 255, 255), (255, 0, 0), (255, 255, 0)],
            # パターン2: 赤→橙→黄（エネルギッシュ）
            [(255, 0, 0), (255, 127, 0), (255, 255, 0)],
            # パターン3: シアン→青（クール）
            [(0, 255, 255), (0, 128, 255), (0, 0, 255)],
            # パターン4: 白→ピンク→紫（ドラマチック）
            [(255, 255, 255), (255, 20, 147), (148, 0, 211)],
            # パターン5: 緑→黄→赤（フレッシュ）
            [(0, 255, 0), (255, 255, 0), (255, 0, 0)],
        ]
        
        gradient_colors = gradient_patterns[pattern_index % len(gradient_patterns)]
        
        # レイヤーを作成
        text_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)
        
        # =========================================
        # 1. 外側の大きなグロー（黒）- 最も外側
        # =========================================
        for offset in range(20, 0, -3):
            alpha = int(120 * (offset / 20))
            glow_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            glow_draw.text(
                (x, y),
                title,
                font=font,
                fill=(0, 0, 0, alpha),
                stroke_width=offset,
                stroke_fill=(0, 0, 0, alpha)
            )
            # ぼかしを適用
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=3))
            text_layer = Image.alpha_composite(text_layer, glow_layer)
        
        # =========================================
        # 2. 立体感を出す影（複数レイヤー）
        # =========================================
        # 深い影（下＋右方向）
        for i in range(8, 0, -1):
            shadow_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            shadow_alpha = int(180 * (i / 8))
            shadow_draw.text(
                (x + i, y + i),
                title,
                font=font,
                fill=(0, 0, 0, shadow_alpha),
                stroke_width=10,
                stroke_fill=(0, 0, 0, shadow_alpha // 2)
            )
            text_layer = Image.alpha_composite(text_layer, shadow_draw._image)
        
        # =========================================
        # 3. 黒い太縁（最も重要な輪郭）- 25px
        # =========================================
        draw.text(
            (x, y),
            title,
            font=font,
            fill=(255, 255, 255, 0),  # 透明
            stroke_width=25,
            stroke_fill=(0, 0, 0, 255)
        )

        # =========================================
        # 4. 白い縁（黒縁の内側）- 15px
        # =========================================
        draw.text(
            (x, y),
            title,
            font=font,
            fill=(255, 255, 255, 0),  # 透明
            stroke_width=15,
            stroke_fill=(255, 255, 255, 255)
        )

        # =========================================
        # 5. カラー縁（グラデーションと調和）- 8px
        # =========================================
        # グラデーションの開始色を使用
        accent_color = gradient_colors[0]
        draw.text(
            (x, y),
            title,
            font=font,
            fill=(255, 255, 255, 0),  # 透明
            stroke_width=8,
            stroke_fill=accent_color + (255,)
        )
        
        # =========================================
        # 6. グラデーション文字本体
        # =========================================
        gradient_layer = self._create_gradient_text_mask(
            img.size,
            title,
            font,
            (x, y),
            gradient_colors,
            vertical=True
        )
        
        # グラデーションレイヤーを合成
        text_layer = Image.alpha_composite(text_layer, gradient_layer)
        
        # =========================================
        # 7. ハイライト（上部に白い光沢）
        # =========================================
        highlight_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight_layer)
        highlight_draw.text(
            (x, y - 3),
            title,
            font=font,
            fill=(255, 255, 255, 80),  # 半透明の白
            stroke_width=2,
            stroke_fill=(255, 255, 255, 60)
        )
        text_layer = Image.alpha_composite(text_layer, highlight_layer)
        
        # =========================================
        # 最終合成
        # =========================================
        result = Image.alpha_composite(img, text_layer)
        
        # RGB変換（保存用）
        result = result.convert('RGB')
        
        self.logger.info(f"✨ Impact gradient text added: '{title}' with pattern {pattern_index + 1}")
        
        return result
    
    # _add_text_to_imageを新しい実装に置き換え
    _add_text_to_image = _add_text_to_image_impact


def create_thumbnail_generator(config: Dict[str, Any], logger: logging.Logger) -> ThumbnailGenerator:
    """
    ThumbnailGeneratorのファクトリー関数
    
    Args:
        config: 設定辞書
        logger: ロガー
        
    Returns:
        ThumbnailGenerator インスタンス
    """
    return ThumbnailGenerator(config, logger)