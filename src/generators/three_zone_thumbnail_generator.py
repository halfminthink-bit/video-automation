"""
3ゾーンサムネイル生成器

人物中央配置 + 2段テキスト（上下）の新レイアウトシステム
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw
from openai import OpenAI
import requests
from io import BytesIO

from .dual_text_system import DualTextSystem
from .three_zone_layout_manager import ThreeZoneLayoutManager
from .person_focused_background import PersonFocusedBackground
from .enhanced_text_renderer import EnhancedTextRenderer


class ThreeZoneThumbnailGenerator:
    """
    3ゾーンレイアウトのサムネイル生成器

    - 上部30%: メインキャッチ（5-7文字）
    - 中央40%: 人物画像（明るさ維持）
    - 下部30%: サブ説明文（15-20文字）
    """

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

        # キャンバスサイズ
        self.canvas_size = tuple(config.get("output", {}).get("resolution", [1280, 720]))

        # 各コンポーネントを初期化
        self.text_system = DualTextSystem(
            model=config.get("catchcopy", {}).get("model", "gpt-4.1-mini"),
            logger=self.logger
        )

        self.layout_manager = ThreeZoneLayoutManager(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        self.background_processor = PersonFocusedBackground(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        self.text_renderer = EnhancedTextRenderer(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        # OpenAI クライアント
        self.openai_client = OpenAI()

        self.logger.info(f"ThreeZoneThumbnailGenerator initialized: {self.canvas_size}")

    def generate_thumbnails(
        self,
        subject: str,
        script_data: Dict[str, Any],
        output_dir: Path,
        num_variations: int = 5
    ) -> List[Path]:
        """
        サムネイルを生成

        Args:
            subject: 動画のテーマ
            script_data: 台本データ
            output_dir: 出力ディレクトリ
            num_variations: 生成するバリエーション数

        Returns:
            生成されたサムネイルのパスリスト
        """
        self.logger.info(f"Generating {num_variations} thumbnail variations for: {subject}")

        # 1. テキストペアを生成
        tone = self.config.get("catchcopy", {}).get("tone", "dramatic")
        text_pairs = self.text_system.generate_text_pairs(
            subject=subject,
            script_data=script_data,
            tone=tone,
            num_candidates=num_variations
        )

        if not text_pairs:
            self.logger.error("No text pairs generated")
            return []

        # 2. 背景画像を生成（DALL-E 3）
        background = self._generate_background_image(subject, script_data)

        if background is None:
            self.logger.error("Failed to generate background image")
            return []

        # 3. 背景画像をリサイズ
        background = background.resize(self.canvas_size, Image.Resampling.LANCZOS)
        self.logger.info(f"Background resized to: {background.size}")

        # 4. ゾーンマスクを作成
        zone_mask = self.layout_manager.create_zone_gradient_mask()

        # 5. 背景を処理（人物エリアを保護）
        processed_background = self.background_processor.process_background(
            image=background,
            zone_mask=zone_mask,
            darken_strength=0.7
        )

        # 6. 各テキストペアでサムネイルを生成
        output_paths = []
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, pair in enumerate(text_pairs, 1):
            try:
                thumbnail_path = self._generate_single_thumbnail(
                    background=processed_background,
                    text_pair=pair,
                    output_dir=output_dir,
                    index=i,
                    subject=subject
                )

                if thumbnail_path:
                    output_paths.append(thumbnail_path)
                    self.logger.info(f"✅ Thumbnail {i}/{num_variations} generated: {thumbnail_path.name}")

            except Exception as e:
                self.logger.error(f"Failed to generate thumbnail {i}: {e}", exc_info=True)

        self.logger.info(f"Generated {len(output_paths)} thumbnails successfully")

        return output_paths

    def _generate_background_image(
        self,
        subject: str,
        script_data: Dict[str, Any]
    ) -> Optional[Image.Image]:
        """
        DALL-E 3で背景画像を生成

        Args:
            subject: 動画のテーマ
            script_data: 台本データ

        Returns:
            生成された画像（Pillowオブジェクト）
        """
        self.logger.info("Generating background image with DALL-E 3")

        # プロンプトを構築
        prompt = self._build_dalle_prompt(subject, script_data)

        self.logger.info(f"DALL-E prompt: {prompt}")

        try:
            # DALL-E 3を呼び出し
            dalle_config = self.config.get("dalle", {})
            size = dalle_config.get("size", "1792x1024")
            quality = dalle_config.get("quality", "standard")

            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=1
            )

            # 画像URLを取得
            image_url = response.data[0].url
            self.logger.info(f"Image generated: {image_url}")

            # 画像をダウンロード
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()

            image = Image.open(BytesIO(image_response.content))
            self.logger.info(f"Background image loaded: {image.size}")

            return image

        except Exception as e:
            self.logger.error(f"Failed to generate background image: {e}", exc_info=True)
            return None

    def _build_dalle_prompt(
        self,
        subject: str,
        script_data: Dict[str, Any]
    ) -> str:
        """
        DALL-E用のプロンプトを構築

        Args:
            subject: 動画のテーマ
            script_data: 台本データ

        Returns:
            プロンプト文字列
        """
        # 台本から重要な要素を抽出
        sections = script_data.get("sections", [])
        context = ""

        if sections:
            # 最初のセクションの内容を使用
            first_section = sections[0]
            content = first_section.get("content", "")[:200]
            context = f"Context: {content}"

        # 人物中心のプロンプト
        dalle_style = self.config.get("dalle", {}).get("style", "dramatic")

        style_descriptions = {
            "dramatic": "dramatic lighting, cinematic composition, emotional atmosphere",
            "elegant": "elegant style, refined aesthetics, sophisticated mood",
            "energetic": "vibrant colors, dynamic composition, energetic feeling",
            "mysterious": "mysterious atmosphere, moody lighting, enigmatic style"
        }

        style_desc = style_descriptions.get(dalle_style, "cinematic style")

        prompt = f"""A {style_desc} portrait photograph centered on a person related to '{subject}'.

{context}

The person should be:
- Positioned in the CENTER of the frame
- Well-lit with clear facial features
- Shown from chest up or waist up
- Against a simple but visually interesting background
- The composition should leave space at TOP and BOTTOM for text overlay

Style: Professional, high-quality, YouTube thumbnail optimized
Mood: {dalle_style.capitalize()}
Orientation: Horizontal (landscape)

NO text, NO words, NO letters in the image."""

        return prompt

    def _generate_single_thumbnail(
        self,
        background: Image.Image,
        text_pair: Dict[str, str],
        output_dir: Path,
        index: int,
        subject: str
    ) -> Optional[Path]:
        """
        単一のサムネイルを生成

        Args:
            background: 処理済み背景画像
            text_pair: テキストペア {"main": "...", "sub": "...", "color_scheme": "..."}
            output_dir: 出力ディレクトリ
            index: インデックス番号
            subject: テーマ

        Returns:
            生成されたサムネイルのパス
        """
        main_text = text_pair.get("main", "")
        sub_text = text_pair.get("sub", "")
        color_scheme = text_pair.get("color_scheme", "fire")

        self.logger.debug(
            f"Generating thumbnail {index}: Main='{main_text}', Sub='{sub_text}', Scheme={color_scheme}"
        )

        # キャンバスを作成（背景をコピー）
        canvas = background.copy()

        # メインテキストの位置を取得
        main_position = self.layout_manager.get_main_text_position(text_size=(0, 0))

        # サブテキストの位置を取得
        sub_position = self.layout_manager.get_sub_text_position(text_size=(0, 0))

        # メインテキストを描画
        main_layer = self.text_renderer.render_main_text(
            text=main_text,
            position=main_position,
            color_scheme=color_scheme
        )

        # サブテキストを描画
        sub_layer = self.text_renderer.render_sub_text(
            text=sub_text,
            position=sub_position,
            color_scheme=color_scheme,
            with_background_band=True
        )

        # レイヤーを合成
        canvas = Image.alpha_composite(canvas.convert('RGBA'), main_layer)
        canvas = Image.alpha_composite(canvas, sub_layer)

        # ファイル名を生成
        safe_main = "".join(c for c in main_text if c.isalnum() or c in (' ', '_'))[:20]
        filename = f"{subject}_{safe_main}_v{index}.png"
        output_path = output_dir / filename

        # 保存
        canvas.convert('RGB').save(output_path, 'PNG', quality=95)

        return output_path

    def visualize_layout(self, output_path: Path) -> Path:
        """
        レイアウトを可視化（デバッグ用）

        Args:
            output_path: 保存先パス

        Returns:
            保存されたパス
        """
        self.logger.info("Visualizing 3-zone layout")

        img = self.layout_manager.visualize_zones()
        img.save(output_path)

        self.logger.info(f"Layout visualization saved: {output_path}")

        return output_path
