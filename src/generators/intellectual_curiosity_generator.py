"""
知的好奇心サムネイル自動生成システム

全てのコンポーネントを統合して、「えっ！？」と驚くサムネイルを完全自動生成
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image
from openai import OpenAI
import requests
from io import BytesIO

from .intellectual_curiosity_text_generator import IntellectualCuriosityTextGenerator
from .intellectual_curiosity_text_renderer import IntellectualCuriosityTextRenderer
from .dark_vignette_processor import DarkVignetteProcessor


class IntellectualCuriosityGenerator:
    """知的好奇心サムネイル自動生成システム"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            config: 設定辞書
            logger: ロガー
        """
        self.config = config or self._get_default_config()
        self.logger = logger or logging.getLogger(__name__)

        # キャンバスサイズ
        self.canvas_size = tuple(
            self.config.get("output", {}).get("resolution", [1280, 720])
        )

        # 各コンポーネントを初期化
        self.text_generator = IntellectualCuriosityTextGenerator(
            model=self.config.get("text_generation", {}).get("model", "gpt-4o-mini"),
            logger=self.logger
        )

        self.text_renderer = IntellectualCuriosityTextRenderer(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        self.background_processor = DarkVignetteProcessor(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        # OpenAI クライアント
        self.openai_client = OpenAI()

        self.logger.info(
            f"IntellectualCuriosityGenerator initialized: {self.canvas_size}"
        )

    def generate_thumbnails(
        self,
        subject: str,
        output_dir: Path,
        context: Optional[Dict[str, Any]] = None,
        num_variations: int = 5
    ) -> List[Path]:
        """
        サムネイルを生成

        Args:
            subject: 対象人物・テーマ
            output_dir: 出力ディレクトリ
            context: 追加コンテキスト（台本など）
            num_variations: 生成するバリエーション数

        Returns:
            生成されたサムネイルのパスリスト
        """
        self.logger.info(
            f"Generating {num_variations} thumbnail variations for: {subject}"
        )

        # 1. 驚きのテキストペアを生成
        surprise_texts = self.text_generator.generate_surprise_texts(
            subject=subject,
            context=context,
            num_candidates=num_variations
        )

        if not surprise_texts:
            self.logger.error("No surprise texts generated")
            return []

        # 2. 背景画像を生成（DALL-E 3）
        background = self._generate_background_image(subject, context)

        if background is None:
            self.logger.error("Failed to generate background image")
            return []

        # 3. 背景画像をリサイズ（1792x1024 → 1280x720）
        background = background.resize(self.canvas_size, Image.Resampling.LANCZOS)
        self.logger.info(f"Background resized to: {background.size}")

        # 4. 背景を処理（暗く、ビネット）
        bg_config = self.config.get("background", {})
        processed_background = self.background_processor.process_background(
            image=background,
            darkness_factor=bg_config.get("darkness", 0.7),
            vignette_strength=bg_config.get("vignette", 0.6),
            edge_shadow=bg_config.get("edge_shadow", True)
        )

        # 5. 各テキストペアでサムネイルを生成
        output_paths = []
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, text_pair in enumerate(surprise_texts, 1):
            try:
                thumbnail_path = self._generate_single_thumbnail(
                    background=processed_background,
                    top_text=text_pair.get("top", ""),
                    bottom_text=text_pair.get("bottom", ""),
                    output_dir=output_dir,
                    index=i,
                    subject=subject
                )

                if thumbnail_path:
                    output_paths.append(thumbnail_path)
                    self.logger.info(
                        f"✅ Thumbnail {i}/{num_variations} generated: "
                        f"{thumbnail_path.name}"
                    )

            except Exception as e:
                self.logger.error(
                    f"Failed to generate thumbnail {i}: {e}",
                    exc_info=True
                )

        self.logger.info(f"Generated {len(output_paths)} thumbnails successfully")

        return output_paths

    def _generate_background_image(
        self,
        subject: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[Image.Image]:
        """
        DALL-E 3で背景画像を生成

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト

        Returns:
            生成された画像（Pillowオブジェクト）
        """
        self.logger.info(f"Generating background image with DALL-E 3 for: {subject}")

        # プロンプトを構築
        prompt = self._build_dalle_prompt(subject, context)

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
            self.logger.error(
                f"Failed to generate background image: {e}",
                exc_info=True
            )
            return None

    def _build_dalle_prompt(
        self,
        subject: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        DALL-E用のプロンプトを構築

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト

        Returns:
            プロンプト文字列
        """
        # コンテキストから情報を抽出
        context_info = ""
        if context and "sections" in context:
            sections = context.get("sections", [])
            if sections:
                first_section = sections[0]
                content = first_section.get("content", "")[:150]
                context_info = f"Context: {content}"

        # 画像スタイル設定
        image_style = self.config.get("image_style", {})
        style_type = image_style.get("type", "dramatic")
        mood = image_style.get("mood", "mysterious")

        prompt = f"""Portrait or dramatic scene of {subject} for YouTube thumbnail.

{context_info}

Style:
- Dramatic, eye-catching, YouTube-optimized
- {style_type} style
- {mood} mood
- High contrast, bold colors

Composition:
- Center-focused for text overlay space
- Clear subject in middle area
- Top and bottom areas can be darker for text
- Face or key element clearly visible

Lighting:
- Dramatic but not too dark
- Subject well-lit and prominent
- Cinematic quality

Technical:
- NO text, NO UI elements
- High quality, detailed
- Horizontal 16:9 format

Size: 1792x1024 (landscape)
Purpose: YouTube thumbnail optimized for text overlay"""

        return prompt

    def _generate_single_thumbnail(
        self,
        background: Image.Image,
        top_text: str,
        bottom_text: str,
        output_dir: Path,
        index: int,
        subject: str
    ) -> Optional[Path]:
        """
        単一のサムネイルを生成

        Args:
            background: 処理済み背景画像
            top_text: 上部テキスト
            bottom_text: 下部テキスト
            output_dir: 出力ディレクトリ
            index: インデックス番号
            subject: テーマ

        Returns:
            生成されたサムネイルのパス
        """
        self.logger.debug(
            f"Generating thumbnail {index}: Top='{top_text}', Bottom='{bottom_text}'"
        )

        # キャンバスを作成（背景をコピー）
        canvas = background.copy()

        # 上部テキストレイヤーを生成（黄色/金色）
        top_layer = self.text_renderer.render_top_text(top_text)

        # 下部テキストレイヤーを生成（白）
        bottom_layer = self.text_renderer.render_bottom_text(
            text=bottom_text,
            with_background=True
        )

        # レイアウトゾーンを取得
        zones = self.text_renderer.get_layout_zones()

        # 上部テキストレイヤーを配置
        canvas.paste(top_layer, (0, 0), top_layer)

        # 下部テキストレイヤーを配置
        canvas.paste(
            bottom_layer,
            (0, zones["bottom"]["start"]),
            bottom_layer
        )

        # ファイル名を生成
        safe_top = "".join(c for c in top_text if c.isalnum() or c in (' ', '_'))[:10]
        filename = f"curiosity_{subject}_{safe_top}_v{index}.png"
        # ファイル名をクリーンアップ
        filename = filename.replace(" ", "_").replace("　", "_")
        output_path = output_dir / filename

        # 保存
        canvas.convert('RGB').save(output_path, 'PNG', quality=95)

        return output_path

    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を取得"""
        return {
            "output": {
                "resolution": [1280, 720]
            },
            "text_generation": {
                "model": "gpt-4o-mini"
            },
            "dalle": {
                "size": "1792x1024",
                "quality": "standard"
            },
            "background": {
                "darkness": 0.7,
                "vignette": 0.6,
                "edge_shadow": True
            },
            "image_style": {
                "type": "dramatic",
                "mood": "mysterious"
            }
        }


def create_intellectual_curiosity_generator(
    config: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None
) -> IntellectualCuriosityGenerator:
    """
    IntellectualCuriosityGeneratorのファクトリー関数

    Args:
        config: 設定辞書
        logger: ロガー

    Returns:
        IntellectualCuriosityGenerator インスタンス
    """
    return IntellectualCuriosityGenerator(config=config, logger=logger)
