"""
「教科書には載せてくれない」シリーズサムネイル生成器

全てのコンポーネントを統合して、完全自動でサムネイルを生成
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from PIL import Image
from openai import OpenAI
import requests
from io import BytesIO

from .textbook_text_generator import TextbookTextGenerator
from .textbook_text_renderer import TextbookTextRenderer
from .dark_vignette_processor import DarkVignetteProcessor


class TextbookSeriesGenerator:
    """「教科書には載せてくれない」シリーズサムネイル生成器"""

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
        self.text_generator = TextbookTextGenerator(
            model=self.config.get("text_generation", {}).get("model", "gpt-4o-mini"),
            logger=self.logger
        )

        self.text_renderer = TextbookTextRenderer(
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
            f"TextbookSeriesGenerator initialized: {self.canvas_size}"
        )

    def generate_thumbnails(
        self,
        subjects: Union[str, List[str]],
        output_dir: Path,
        context: Optional[Dict[str, Any]] = None,
        num_variations: int = 5
    ) -> List[Path]:
        """
        サムネイルを生成

        Args:
            subjects: 人物名（単一または複数）
            output_dir: 出力ディレクトリ
            context: 追加コンテキスト（台本など）
            num_variations: 生成するバリエーション数

        Returns:
            生成されたサムネイルのパスリスト
        """
        # 人物名を文字列化
        if isinstance(subjects, list):
            subject_str = "、".join(subjects)
        else:
            subject_str = subjects
            subjects = [subjects]

        self.logger.info(
            f"Generating {num_variations} thumbnail variations for: {subject_str}"
        )

        # 1. 下部テキストを生成
        bottom_texts = self.text_generator.generate_bottom_texts(
            subject=subject_str,
            context=context,
            num_candidates=num_variations
        )

        if not bottom_texts:
            self.logger.error("No bottom texts generated")
            return []

        # 2. 背景画像を生成（DALL-E 3）
        background = self._generate_background_image(subjects, context)

        if background is None:
            self.logger.error("Failed to generate background image")
            return []

        # 3. 背景画像をリサイズ（1792x1024 → 1280x720）
        background = background.resize(self.canvas_size, Image.Resampling.LANCZOS)
        self.logger.info(f"Background resized to: {background.size}")

        # 4. 背景を処理（暗く、ビネット強め）
        bg_config = self.config.get("background", {})
        processed_background = self.background_processor.process_background(
            image=background,
            darkness_factor=bg_config.get("darkness", 0.7),
            vignette_strength=bg_config.get("vignette", 0.6),
            edge_shadow=bg_config.get("edge_shadow", True)
        )

        # 5. 各テキストパターンでサムネイルを生成
        output_paths = []
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, bottom_text_data in enumerate(bottom_texts, 1):
            try:
                thumbnail_path = self._generate_single_thumbnail(
                    background=processed_background,
                    bottom_text=bottom_text_data.get("text", ""),
                    output_dir=output_dir,
                    index=i,
                    subject=subject_str
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
        subjects: List[str],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Image.Image]:
        """
        DALL-E 3で背景画像を生成（歴史的人物）

        Args:
            subjects: 人物名のリスト
            context: 追加コンテキスト

        Returns:
            生成された画像（Pillowオブジェクト）
        """
        self.logger.info(
            f"Generating background image with DALL-E 3 for: {', '.join(subjects)}"
        )

        # プロンプトを構築
        prompt = self._build_dalle_prompt(subjects, context)

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
        subjects: List[str],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        DALL-E用のプロンプトを構築

        Args:
            subjects: 人物名のリスト
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
        style_type = image_style.get("type", "historical")
        mood = image_style.get("mood", "mysterious")

        if len(subjects) > 1:
            # 複数人物の場合
            prompt = f"""Historical figures montage for educational thumbnail.

Featuring: {', '.join(subjects)}

{context_info}

Composition:
- {len(subjects)} portraits side by side or arranged artistically
- Each person clearly visible
- Period-accurate appearance and clothing
- Serious, contemplative expressions
- Dramatic but not too dark lighting

Style:
- Historical painting or aged photograph aesthetic
- Sepia or muted color tones with subtle color accents
- Atmospheric, mysterious, educational mood
- Some texture for authenticity (canvas, old paper feel)
- NOT too dark - faces must be clearly visible

Background:
- Dark textured background (parchment, old book texture)
- Historical atmosphere
- No modern elements
- No text, no UI elements

Lighting:
- Dramatic side lighting
- Faces well-lit and clear
- Mysterious shadows but not overly dark

Size: 1792x1024 (landscape)
Mood: {mood}
Style: {style_type}"""

        else:
            # 単一人物の場合
            subject = subjects[0]
            prompt = f"""Historical portrait of {subject} for educational thumbnail.

{context_info}

Style:
- Classical portrait painting or aged photograph style
- Dramatic but BRIGHT lighting from side
- Serious, contemplative, or intense expression
- Historical accuracy in clothing and appearance

Composition:
- Center positioned, head and shoulders visible
- 3/4 view or slight profile preferred
- Face clearly visible and well-lit
- Period-accurate clothing and details
- Clear facial features and expression

Atmosphere:
- Dark, moody textured background (parchment, canvas, old paper)
- Historical and mysterious tone
- Educational documentary feel
- NOT too dark overall - subject must be clearly visible

Technical:
- NO text, NO YouTube UI elements, NO play buttons
- High quality, detailed rendering
- Some grain/texture for historical authenticity

Size: 1792x1024 (landscape)
Orientation: Horizontal 16:9
Mood: {mood}
Style: {style_type}"""

        return prompt

    def _generate_single_thumbnail(
        self,
        background: Image.Image,
        bottom_text: str,
        output_dir: Path,
        index: int,
        subject: str
    ) -> Optional[Path]:
        """
        単一のサムネイルを生成

        Args:
            background: 処理済み背景画像
            bottom_text: 下部テキスト
            output_dir: 出力ディレクトリ
            index: インデックス番号
            subject: テーマ

        Returns:
            生成されたサムネイルのパス
        """
        self.logger.debug(f"Generating thumbnail {index}: Bottom='{bottom_text}'")

        # キャンバスを作成（背景をコピー）
        canvas = background.copy()

        # 上部テキストレイヤーを生成（固定）
        top_layer = self.text_renderer.render_top_text()

        # 下部テキストレイヤーを生成（可変）
        bottom_layer = self.text_renderer.render_bottom_text(
            text=bottom_text,
            with_glow=True
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
        safe_text = "".join(c for c in bottom_text if c.isalnum() or c in (' ', '_'))[:15]
        filename = f"textbook_{subject}_{safe_text}_v{index}.png"
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
                "type": "historical",
                "mood": "mysterious"
            }
        }


def create_textbook_series_generator(
    config: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None
) -> TextbookSeriesGenerator:
    """
    TextbookSeriesGeneratorのファクトリー関数

    Args:
        config: 設定辞書
        logger: ロガー

    Returns:
        TextbookSeriesGenerator インスタンス
    """
    return TextbookSeriesGenerator(config=config, logger=logger)
