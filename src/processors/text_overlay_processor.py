"""
テキストオーバーレイプロセッサー

Stable Diffusionで生成した画像にV3.0レイアウトのテキストをオーバーレイする。

使用クラス:
- V3TextRenderer: 赤グラデーション + 白黒縁のテキスト描画
"""

from PIL import Image
from pathlib import Path
from typing import Optional
import logging

from ..generators.v3_text_renderer import V3TextRenderer


class TextOverlayProcessor:
    """
    SD生成画像にテキストをオーバーレイ

    V3.0レイアウト（25/50/25）:
    - 上部25%: 赤グラデーションの大きい文字（5-8文字）
    - 中央50%: 人物画像（SD生成）
    - 下部25%: 白文字+黒縁（15-25文字）
    """

    def __init__(
        self,
        phase_config: dict,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            phase_config: Phase 8設定
            logger: ロガー
        """
        self.phase_config = phase_config
        self.logger = logger or logging.getLogger(__name__)

        # V3テキストレンダラーを初期化
        self.text_renderer = V3TextRenderer(
            canvas_size=(1280, 720),
            logger=self.logger
        )

        self.logger.info("TextOverlayProcessor initialized")

    def add_v3_text(
        self,
        image_path: str,
        main_title: str,
        sub_title: str,
        output_path: str
    ) -> str:
        """
        V3.0レイアウトのテキストをオーバーレイ

        Args:
            image_path: SD生成画像のパス
            main_title: メインタイトル（上部、5-8文字）
            sub_title: サブタイトル（下部、15-25文字）
            output_path: 出力パス

        Returns:
            保存された画像のパス
        """
        self.logger.info(f"Adding V3 text overlay to: {image_path}")
        self.logger.debug(f"Main: '{main_title}', Sub: '{sub_title}'")

        # 背景画像を読み込み
        bg_image = Image.open(image_path).convert('RGBA')

        # リサイズ（1280x720に統一）
        if bg_image.size != (1280, 720):
            self.logger.info(f"Resizing image from {bg_image.size} to (1280, 720)")
            bg_image = bg_image.resize((1280, 720), Image.Resampling.LANCZOS)

        # 1. メインテキストを描画（上部25%）
        main_text_y = int(720 * 0.125)  # 上部25%の中央
        main_text_layer = self.text_renderer.render_main_text(
            text=main_title,
            position=(640, main_text_y)  # 中央
        )

        # メインテキストをオーバーレイ
        # レイヤーの位置を計算（中央揃え）
        main_layer_x = (1280 - main_text_layer.width) // 2
        main_layer_y = int(720 * 0.125) - (main_text_layer.height // 2)
        bg_image.paste(main_text_layer, (main_layer_x, main_layer_y), main_text_layer)

        # 2. サブテキストを描画（下部25%）
        sub_text_layer = self.text_renderer.render_sub_text(
            text=sub_title,
            position=(640, int(720 * 0.875)),  # 下部25%の中央
            with_background=True
        )

        # サブテキストをオーバーレイ
        # レイヤーは下部25%（y = 720 * 0.75 から 720）
        sub_layer_y = int(720 * 0.75)
        bg_image.paste(sub_text_layer, (0, sub_layer_y), sub_text_layer)

        # 3. RGB形式に変換して保存
        final_image = bg_image.convert('RGB')
        final_image.save(output_path, 'PNG', quality=95)

        self.logger.info(f"✅ V3 text overlay complete: {output_path}")

        return str(output_path)
