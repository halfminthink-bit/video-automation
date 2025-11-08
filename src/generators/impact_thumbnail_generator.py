"""
超インパクトサムネイル生成器

GradientTextGenerator、MultiStrokeRenderer、EffectCompositorを統合し、
YouTubeで圧倒的に目立つサムネイルを生成
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import logging
import os

from .gradient_text_generator import GradientTextGenerator
from .multi_stroke_renderer import MultiStrokeRenderer
from .effect_compositor import EffectCompositor


class ImpactThumbnailGenerator:
    """超インパクトサムネイル生成器"""

    # フォントサイズマッピング（文字数 → フォントサイズ）
    FONT_SIZE_MAP = {
        1: 200,
        2: 180,
        3: 160,
        4: 150,
        5: 140,
        6: 130,
        7: 120,
        8: 110,
    }

    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            config: 設定辞書
            logger: ロガー
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # コンポーネントを初期化
        self.gradient_gen = GradientTextGenerator(logger=self.logger)
        self.stroke_renderer = MultiStrokeRenderer(logger=self.logger)
        self.effect_comp = EffectCompositor(logger=self.logger)

        # フォントパスを設定
        self.font_path = self._get_font_path()

        self.logger.info(f"ImpactThumbnailGenerator initialized with font: {self.font_path}")

    def _get_font_path(self) -> str:
        """
        フォントパスを取得（Windows/Linux対応）

        Returns:
            フォントパス
        """
        # 設定ファイルからフォントパスを取得
        font_config = self.config.get("font", {})
        configured_path = font_config.get("path")

        if configured_path and os.path.exists(configured_path):
            return configured_path

        # プロジェクトルート
        project_root = Path(__file__).parent.parent.parent

        # フォント候補（優先順）
        font_candidates = [
            # プロジェクト内のフォント
            project_root / "assets" / "fonts" / "NotoSansJP-Bold.ttf",
            project_root / "assets" / "fonts" / "GenEiKiwamiGothic-EB.ttf",
            project_root / "assets" / "fonts" / "GN-KillGothic-U-KanaNB.ttf",

            # Windows
            r"C:\Users\hyokaimen\kyota\video-automation\assets\fonts\NotoSansJP-Bold.ttf",
            r"C:\Windows\Fonts\msgothic.ttc",
            r"C:\Windows\Fonts\meiryo.ttc",

            # Linux
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansJP-Bold.ttf",
        ]

        for font_path in font_candidates:
            font_path = Path(font_path)
            if font_path.exists():
                self.logger.info(f"Found font: {font_path}")
                return str(font_path)

        # フォントが見つからない場合
        self.logger.error("No suitable font found!")
        raise FileNotFoundError("日本語フォントが見つかりません。fonts/ディレクトリにフォントを配置してください。")

    def calculate_optimal_font_size(
        self,
        text: str,
        target_coverage: float = 0.7
    ) -> int:
        """
        文字数に応じて最適なフォントサイズを計算

        Args:
            text: テキスト
            target_coverage: 目標画面占有率（0.0〜1.0）

        Returns:
            フォントサイズ（ピクセル）
        """
        char_count = len(text)
        base_size = self.FONT_SIZE_MAP.get(min(char_count, 8), 100)

        # target_coverageに基づいて調整
        # 0.7 (70%) が基準で、それより大きければフォントサイズを増やす
        adjustment = target_coverage / 0.7
        adjusted_size = int(base_size * adjustment)

        self.logger.info(
            f"Font size calculated: {char_count} chars → {adjusted_size}px "
            f"(base={base_size}, coverage={target_coverage})"
        )

        return adjusted_size

    def select_gradient_pattern(self, emotion: str = "dramatic") -> str:
        """
        感情に応じたグラデーションパターンを選択

        Args:
            emotion: 感情タイプ（dramatic, command, mystery, fact, contrast）

        Returns:
            グラデーションパターン名
        """
        emotion_mapping = {
            "dramatic": "fire",       # 劇的 → 白→赤→黄
            "command": "energy",      # 命令 → 緑→黄→赤
            "mystery": "neon",        # 謎 → 白→ピンク→紫
            "fact": "ocean",          # 事実 → 白→シアン→青
            "contrast": "sunset",     # 対立 → 赤→オレンジ→黄
        }

        pattern = emotion_mapping.get(emotion, "fire")
        self.logger.debug(f"Gradient pattern selected: {emotion} → {pattern}")

        return pattern

    def generate_thumbnail(
        self,
        background: Image.Image,
        text: str,
        emotion: str = "dramatic",
        output_path: Optional[str] = None
    ) -> Image.Image:
        """
        サムネイルを生成

        Args:
            background: 背景画像（1280x720推奨）
            text: キャッチコピー
            emotion: 感情タイプ
            output_path: 出力パス（Noneの場合は保存しない）

        Returns:
            生成されたサムネイル画像
        """
        self.logger.info(f"Generating impact thumbnail: '{text}' ({emotion})")

        # 背景サイズを確認・調整
        if background.size != (1280, 720):
            self.logger.warning(
                f"Background size is {background.size}, resizing to 1280x720"
            )
            background = background.resize((1280, 720), Image.Resampling.LANCZOS)

        # 1. 背景を暗くして文字を際立たせる
        background = self.effect_comp.darken_background(
            background,
            saturation_factor=0.7,
            brightness_factor=0.6
        )

        # 2. ビネット効果を適用
        background = self.effect_comp.add_vignette(background, strength=0.6)

        # RGBA変換
        if background.mode != 'RGBA':
            background = background.convert('RGBA')

        # 3. 最適なフォントサイズを計算
        target_coverage = self.config.get("font", {}).get("target_coverage", 0.7)
        font_size = self.calculate_optimal_font_size(text, target_coverage)

        # 4. フォントを読み込み
        try:
            # .ttc ファイルの場合は index=0 を指定
            if self.font_path.endswith('.ttc'):
                font = ImageFont.truetype(self.font_path, font_size, index=0)
            else:
                font = ImageFont.truetype(self.font_path, font_size)
        except Exception as e:
            self.logger.error(f"Failed to load font: {e}")
            raise

        # 5. テキスト位置を計算（中央配置）
        temp_draw = ImageDraw.Draw(background)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        width, height = background.size
        x = (width - text_width) // 2
        y = (height - text_height) // 2  # 中央配置

        position = (x, y)

        self.logger.info(f"Text position: {position}, size: {text_width}x{text_height}px")

        # 6. グラデーションパターンを選択
        gradient_pattern = self.select_gradient_pattern(emotion)

        # 7. ドロップシャドウを追加
        shadow_layer = self.effect_comp.add_drop_shadow(
            size=background.size,
            text=text,
            position=position,
            font=font,
            layers=10,
            max_offset=20,
            blur_radius=5
        )

        # 8. グローエフェクトを追加
        glow_layer = self.effect_comp.add_glow_effect(
            size=background.size,
            text=text,
            position=position,
            font=font,
            radius=30,
            intensity=0.7,
            glow_color=(0, 0, 0)
        )

        # 9. 多重縁取りを適用
        # グラデーション開始色を取得
        gradient_colors = GradientTextGenerator.GRADIENT_PATTERNS.get(
            gradient_pattern,
            GradientTextGenerator.GRADIENT_PATTERNS["fire"]
        )
        gradient_start_color = gradient_colors[0]

        stroke_layer = self.stroke_renderer.apply_multi_stroke(
            size=background.size,
            text=text,
            position=position,
            font=font,
            gradient_start_color=gradient_start_color
        )

        # 10. グラデーションテキストを生成
        gradient_text = self.gradient_gen.create_gradient_text(
            text=text,
            font=font,
            size=background.size,
            position=position,
            gradient_type=gradient_pattern,
            direction="vertical"
        )

        # 11. すべてのレイヤーを合成
        # 合成順序: 背景 → シャドウ → グロー → 縁取り → グラデーションテキスト
        result = background
        result = Image.alpha_composite(result, shadow_layer)
        result = Image.alpha_composite(result, glow_layer)
        result = Image.alpha_composite(result, stroke_layer)
        result = Image.alpha_composite(result, gradient_text)

        # RGB変換（保存用）
        result = result.convert('RGB')

        # 12. 保存
        if output_path:
            result.save(output_path, quality=95)
            self.logger.info(f"Thumbnail saved: {output_path}")

        self.logger.info("✨ Impact thumbnail generated successfully!")

        return result


def create_impact_thumbnail_generator(
    config: Dict[str, Any],
    logger: logging.Logger
) -> ImpactThumbnailGenerator:
    """
    ImpactThumbnailGeneratorのファクトリー関数

    Args:
        config: 設定辞書
        logger: ロガー

    Returns:
        ImpactThumbnailGenerator インスタンス
    """
    return ImpactThumbnailGenerator(config, logger)
