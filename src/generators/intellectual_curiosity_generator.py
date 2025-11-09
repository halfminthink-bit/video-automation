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
from .bright_background_processor import BrightBackgroundProcessor
from .fixed_top_text_patterns import FixedTopTextPatterns


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

        self.background_processor = BrightBackgroundProcessor(
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

        # 1. 2行構成の下部テキストを生成
        bottom_texts = self.text_generator.generate_surprise_texts(
            subject=subject,
            context=context,
            num_candidates=num_variations
        )

        if not bottom_texts:
            self.logger.error("No bottom texts generated")
            return []

        # 2. 背景画像を生成（DALL-E 3）
        background = self._generate_background_image(subject, context)

        if background is None:
            self.logger.error("Failed to generate background image")
            return []

        # 3. 背景画像をリサイズ（1792x1024 → 1280x720）
        background = background.resize(self.canvas_size, Image.Resampling.LANCZOS)
        self.logger.info(f"Background resized to: {background.size}")

        # 4. 背景を処理（明るく保つ、軽いビネット）
        bg_config = self.config.get("background", {})
        processed_background = self.background_processor.process_background(
            image=background,
            vignette_strength=bg_config.get("vignette", 0.2),
            edge_shadow=bg_config.get("edge_shadow", True),
            enhance_brightness=bg_config.get("enhance_brightness", True)
        )

        # 5. 各テキストペアでサムネイルを生成
        output_paths = []
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, text_data in enumerate(bottom_texts, 1):
            try:
                # 固定フレーズを取得（インデックスで循環）
                top_text = FixedTopTextPatterns.get_pattern_by_index(i - 1)

                thumbnail_path = self._generate_single_thumbnail(
                    background=processed_background,
                    top_text=top_text,
                    line1=text_data.get("line1", ""),
                    line2=text_data.get("line2", ""),
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

    def _extract_key_scenes(
        self,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        台本から重要なシーン・状況を抽出

        Args:
            context: 台本データ

        Returns:
            重要なシーンの説明文
        """
        if not context or "sections" not in context:
            return "No specific context available. Create a dramatic historical scene."

        sections = context.get("sections", [])
        if not sections:
            return "No specific context available. Create a dramatic historical scene."

        # 最初の2-3セクションから重要な内容を抽出
        key_content = []

        for i, section in enumerate(sections[:3]):  # 最初の3セクション
            title = section.get("title", "")
            content = section.get("content", "")

            # 各セクションから最初の150-200文字を抽出
            content_preview = content[:200] if content else ""

            if title and content_preview:
                key_content.append(f"{i+1}. {title}: {content_preview}...")
            elif content_preview:
                key_content.append(f"{i+1}. {content_preview}...")

        if not key_content:
            return "No specific context available. Create a dramatic historical scene."

        # セクション内容を結合
        scenes_text = "\n".join(key_content)

        return f"""Based on the script:
{scenes_text}

Focus on the most DRAMATIC and VISUALLY COMPELLING moment from these scenes.
Show the ACTION, CONFLICT, or KEY TURNING POINT."""

    def _build_dalle_prompt(
        self,
        subject: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        DALL-E用のプロンプトを構築（歴史的状況を描く）

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト（台本）

        Returns:
            プロンプト文字列
        """
        # 台本から重要なシーン・状況を抽出
        key_scenes = self._extract_key_scenes(context)

        # 画像スタイル設定
        image_style = self.config.get("image_style", {})
        style_type = image_style.get("type", "dramatic")

        prompt = f"""A dramatic historical scene depicting a key moment in the story of {subject}.

KEY SCENES FROM THE STORY:
{key_scenes}

VISUAL REQUIREMENTS:
- Show the SITUATION or DRAMATIC MOMENT from {subject}'s life, NOT just a portrait
- Include PERIOD-APPROPRIATE details (historical clothing, architecture, environment)
- Convey the EMOTION and HISTORICAL SIGNIFICANCE of the scene
- Create VISUAL IMPACT through dramatic composition and lighting
- Make it CLEAR this is a historical figure/event with period details

SCENE ELEMENTS:
- Historical setting with period-accurate details
- Dramatic composition showing action or a key moment
- Rich, atmospheric lighting (can be dramatic but still visible)
- Clear time period indicators (clothing, architecture, tools)
- Emotional intensity and human drama
- Environmental context that tells the story

STYLE:
- Cinematic, {style_type} style
- Historically accurate but visually engaging
- Professional quality, like a movie poster
- Emotional and impactful

COMPOSITION:
- Horizontal 16:9 format
- Space at top and bottom for text overlay
- Main focus in center area
- Dynamic, not static
- Clear storytelling through visuals

TECHNICAL:
- NO text, NO UI elements, NO watermarks
- High resolution, sharp focus
- NO modern elements
- Size: 1792x1024 (landscape)

CRITICAL: Show a SITUATION, ACTION, or DRAMATIC SCENE from their life.
NOT a simple portrait. The image should tell a story and convey historical context.

Purpose: YouTube thumbnail that captures viewers' attention and curiosity about this historical moment."""

        return prompt

    def _generate_single_thumbnail(
        self,
        background: Image.Image,
        top_text: str,
        line1: str,
        line2: str,
        output_dir: Path,
        index: int,
        subject: str
    ) -> Optional[Path]:
        """
        単一のサムネイルを生成

        Args:
            background: 処理済み背景画像
            top_text: 上部テキスト（固定フレーズ）
            line1: 下部1行目（衝撃的な事実）
            line2: 下部2行目（詳細説明）
            output_dir: 出力ディレクトリ
            index: インデックス番号
            subject: テーマ

        Returns:
            生成されたサムネイルのパス
        """
        self.logger.debug(
            f"Generating thumbnail {index}: Top='{top_text}', "
            f"Line1='{line1}', Line2='{line2}'"
        )

        # キャンバスを作成（背景をコピー）
        canvas = background.copy()

        # 上部テキストレイヤーを生成（金色、固定フレーズ）
        top_layer = self.text_renderer.render_top_text(top_text)

        # 下部テキストレイヤーを生成（白、2行構成）
        bottom_layer = self.text_renderer.render_bottom_text(
            line1=line1,
            line2=line2
        )

        # 上部テキストレイヤーを配置
        canvas.paste(top_layer, (0, 0), top_layer)

        # 下部テキストレイヤーを配置（見切れ防止のため画面下端から配置）
        bottom_layer_height = 300  # レイヤー高さ（intellectual_curiosity_text_renderer.pyと一致）
        canvas.paste(
            bottom_layer,
            (0, canvas.size[1] - bottom_layer_height),  # = (0, 720 - 300) = (0, 420)
            bottom_layer
        )

        # ファイル名を生成
        safe_line1 = "".join(c for c in line1 if c.isalnum() or c in (' ', '_'))[:10]
        filename = f"curiosity_{subject}_{safe_line1}_v{index}.png"
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
                "vignette": 0.2,  # 軽いビネット
                "edge_shadow": True,
                "enhance_brightness": True  # 明るさを少し上げる
            },
            "image_style": {
                "type": "professional",  # プロフェッショナルな写真
                "mood": "bright"  # 明るいムード
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
