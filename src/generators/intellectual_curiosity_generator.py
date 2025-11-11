"""
知的好奇心サムネイル自動生成システム

全てのコンポーネントを統合して、「えっ！？」と驚くサムネイルを完全自動生成
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
from anthropic import Anthropic
import requests
from io import BytesIO
import json

from .intellectual_curiosity_text_renderer import IntellectualCuriosityTextRenderer
from .bright_background_processor import BrightBackgroundProcessor
from .image_generator import ImageGenerator


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
        self.text_renderer = IntellectualCuriosityTextRenderer(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        self.background_processor = BrightBackgroundProcessor(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        # 背景生成方法の選択
        self.use_stable_diffusion = self.config.get("use_stable_diffusion", False)

        # OpenAI クライアント（DALL-E 用）
        if not self.use_stable_diffusion:
            self.openai_client = OpenAI()
            self.logger.info("Background generation: DALL-E 3")
        else:
            self.openai_client = None
            # ImageGenerator を初期化（SD 用）
            self.image_generator = self._create_image_generator()
            self.logger.info("Background generation: Stable Diffusion")

        # Anthropic Claude クライアント（プロンプト生成用）
        claude_api_key = os.getenv("CLAUDE_API_KEY")
        if claude_api_key:
            self.anthropic_client = Anthropic(api_key=claude_api_key)
            self.logger.info("Claude API available for prompt generation")
        else:
            self.anthropic_client = None
            self.logger.warning("Claude API key not found, using fallback prompt generation")

        self.logger.info(
            f"IntellectualCuriosityGenerator initialized: {self.canvas_size}"
        )

    def _create_image_generator(self) -> ImageGenerator:
        """
        ImageGenerator を作成（Stable Diffusion用）

        Returns:
            ImageGenerator インスタンス

        Raises:
            ValueError: API キーが見つからない場合
        """
        # Stability API キーを取得
        sd_config = self.config.get("stable_diffusion", {})
        api_key_env = sd_config.get("api_key_env", "STABILITY_API_KEY")
        api_key = os.getenv(api_key_env)

        if not api_key:
            raise ValueError(f"Stability API key not found: {api_key_env}")

        # Claude API キー（プロンプト最適化用）
        claude_key = os.getenv("CLAUDE_API_KEY")
        if not claude_key:
            self.logger.warning("Claude API key not found, prompt optimization disabled")

        # 出力ディレクトリ
        output_dir = Path("data/working/thumbnails/sd_backgrounds")
        cache_dir = Path("data/cache/sd_thumbnails")

        return ImageGenerator(
            api_key=api_key,
            service="stable-diffusion",
            claude_api_key=claude_key,  # プロンプト最適化を有効化
            output_dir=output_dir,
            cache_dir=cache_dir,
            logger=self.logger
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
            num_variations: 生成するバリエーション数（使用されない - 常に1つ生成）

        Returns:
            生成されたサムネイルのパスリスト
        """
        self.logger.info(f"Generating thumbnail for: {subject}")

        # 1. contextからthumbnailフィールドを取得
        thumbnail_data = context.get("thumbnail", {}) if context else {}
        upper_text = thumbnail_data.get("upper_text", subject)  # フォールバック: 人物名
        lower_text = thumbnail_data.get("lower_text", "")       # フォールバック: 空文字列

        self.logger.info(f"Thumbnail text - Upper: '{upper_text}', Lower: '{lower_text}'")

        # 2. 背景画像を生成（DALL-E または SD）
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

        # 5. サムネイルを生成（1つのみ）
        output_paths = []
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            thumbnail_path = self._generate_single_thumbnail(
                background=processed_background,
                top_text=upper_text,      # script.jsonから取得
                line1=lower_text,         # script.jsonから取得（1行のみ）
                line2="",                 # 空文字列（2行目は使わない）
                output_dir=output_dir,
                index=1,
                subject=subject
            )

            if thumbnail_path:
                output_paths.append(thumbnail_path)
                self.logger.info(f"✅ Thumbnail generated: {thumbnail_path.name}")

        except Exception as e:
            self.logger.error(f"Failed to generate thumbnail: {e}", exc_info=True)

        self.logger.info(f"Generated {len(output_paths)} thumbnail successfully")

        return output_paths

    def _generate_background_image(
        self,
        subject: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[Image.Image]:
        """
        背景画像を生成（DALL-E または SD）

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト（台本）

        Returns:
            生成された画像（Pillowオブジェクト）
        """
        if self.use_stable_diffusion:
            return self._generate_background_image_sd(subject, context)
        else:
            return self._generate_background_image_dalle(subject, context)

    def _generate_background_image_dalle(
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

    def _generate_background_image_sd(
        self,
        subject: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[Image.Image]:
        """
        Stable Diffusion で背景画像を生成

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト（台本）

        Returns:
            生成された画像（Pillowオブジェクト）

        Raises:
            Exception: 生成失敗時（フォールバックなし）
        """
        self.logger.info(f"Generating background with Stable Diffusion for: {subject}")

        # SD 用のプロンプトを構築
        prompt = self._build_sd_prompt(subject, context)

        self.logger.info(f"SD prompt: {prompt[:200]}...")  # 最初の200文字のみログ

        # SD 設定を取得
        sd_config = self.config.get("stable_diffusion", {})
        width = sd_config.get("width", 1344)
        height = sd_config.get("height", 768)

        try:
            # ImageGenerator で生成
            collected_image = self.image_generator.generate_image(
                keyword=subject,
                atmosphere="dramatic",
                section_context=self._extract_key_scenes(context),
                image_type="portrait",  # 人物中心
                style="photorealistic",
                width=width,
                height=height,
                is_first_image=True  # 重要な画像として扱う
            )

            # PIL Image として読み込み
            image = Image.open(collected_image.file_path)
            self.logger.info(f"SD background generated: {image.size}")

            return image

        except Exception as e:
            self.logger.error(
                f"Stable Diffusion generation failed: {e}",
                exc_info=True
            )
            # フォールバックなし、エラーを返す
            raise Exception(f"Failed to generate background with Stable Diffusion: {e}")

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

    def _build_sd_prompt(
        self,
        subject: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Stable Diffusion 用のプロンプト（Claudeで生成）

        Claudeに台本全体を渡して、印象的な背景と人物を抽出し、
        写実的で中央配置のSDプロンプトを生成させる。

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト（台本全体）

        Returns:
            SD 用プロンプト
        """
        # Claude APIが利用可能な場合、AIでプロンプト生成
        if self.anthropic_client and context:
            try:
                return self._generate_sd_prompt_with_claude(subject, context)
            except Exception as e:
                self.logger.warning(
                    f"Failed to generate prompt with Claude: {e}. "
                    "Falling back to template-based prompt."
                )

        # フォールバック: テンプレートベースのプロンプト
        return self._build_fallback_sd_prompt(subject, context)

    def _generate_sd_prompt_with_claude(
        self,
        subject: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Claude APIを使ってSD用プロンプトを生成

        Args:
            subject: 対象人物・テーマ
            context: 台本全体

        Returns:
            Claude が生成した SD プロンプト
        """
        # 台本の全セクションを取得
        sections = context.get("sections", [])
        script_text = ""

        if sections:
            for i, section in enumerate(sections):
                title = section.get("title", f"Section {i+1}")
                content = section.get("content", "")
                narration = section.get("narration", "")

                script_text += f"## {title}\n"
                if content:
                    script_text += f"{content}\n"
                if narration:
                    script_text += f"ナレーション: {narration}\n"
                script_text += "\n"

        # Claude にプロンプト生成を依頼
        claude_request = f"""あなたはStable Diffusion用のプロンプトを生成する専門家です。

以下の台本から、YouTubeサムネイル用の印象的な背景画像を生成するためのプロンプトを作成してください。

【台本】
テーマ: {subject}

{script_text}

【要件】
1. **人物**: 台本の主人公（{subject}）を中央に配置
2. **背景**: 台本から最も印象的で視覚的にインパクトのある場面を選択
   - 具体的な場所や状況を含める（例：戦場、城、研究室など）
   - 時代背景を反映した要素を含める
3. **スタイル**: 写実的（photorealistic）
4. **構図**:
   - 人物を画面中央に配置
   - 上部25%と下部25%はテキストオーバーレイ用の空間を確保
   - 中央50%に人物と背景を配置

【出力形式】
以下のJSON形式で出力してください：

```json
{{
  "main_subject": "中央に配置する人物の説明（英語で簡潔に）",
  "background_scene": "背景の場面の説明（英語で具体的に）",
  "atmosphere": "雰囲気・感情（英語で）",
  "stable_diffusion_prompt": "Stable Diffusion用の完全なプロンプト（英語、200-300語）"
}}
```

**重要**: `stable_diffusion_prompt`は英語で、写実的（photorealistic）、中央配置、16:9フォーマット、YouTubeサムネイル用であることを明記してください。"""

        self.logger.info("Requesting SD prompt generation from Claude...")

        # Claude API呼び出し
        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": claude_request
            }]
        )

        response_text = response.content[0].text.strip()
        self.logger.debug(f"Claude response: {response_text[:200]}...")

        # JSONを抽出
        try:
            # マークダウンコードブロックを除去
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_text = response_text

            prompt_data = json.loads(json_text)
            sd_prompt = prompt_data.get("stable_diffusion_prompt", "")

            if sd_prompt:
                self.logger.info("✅ Claude generated SD prompt successfully")
                self.logger.info(f"Subject: {prompt_data.get('main_subject', 'N/A')}")
                self.logger.info(f"Background: {prompt_data.get('background_scene', 'N/A')[:100]}...")
                return sd_prompt
            else:
                raise ValueError("No stable_diffusion_prompt in response")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning(f"Failed to parse Claude response: {e}")
            raise

    def _build_fallback_sd_prompt(
        self,
        subject: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        フォールバック用のテンプレートベースSDプロンプト

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト（台本）

        Returns:
            テンプレートベースの SD プロンプト
        """
        # 台本から重要なシーン・状況を抽出
        key_scenes = self._extract_key_scenes(context)

        prompt = f"""Photorealistic portrait of {subject}, centered composition, dramatic historical scene.

SCENE CONTEXT:
{key_scenes}

COMPOSITION REQUIREMENTS (CRITICAL):
- Main subject ({subject}) positioned in CENTER of frame
- Subject fills center 50-60% of image
- Medium shot showing face and upper body clearly
- Cinematic perspective with period-accurate background
- 16:9 horizontal landscape format

VISUAL STYLE:
- Photorealistic, documentary-style photography
- Professional quality, sharp focus on subject
- Dramatic natural lighting highlighting the subject
- Rich, historically accurate colors
- High detail and texture

BACKGROUND:
- Relevant historical setting from the person's life
- Period-appropriate architecture, environment, or dramatic scene
- Contextually meaningful backdrop that tells a story
- Clear but not distracting from the main subject

LAYOUT FOR TEXT OVERLAY (IMPORTANT):
- Clear empty space at TOP 25% for text overlay
- Clear empty space at BOTTOM 25% for text overlay
- Main subject in MIDDLE 50%
- Subject centered, not extending to frame edges

ATMOSPHERE:
- Impactful, attention-grabbing
- Historically accurate period details
- Emotional intensity and human drama
- Cinematic quality suitable for YouTube thumbnail

TECHNICAL REQUIREMENTS:
- NO text, NO watermarks, NO UI elements
- NO modern elements or anachronisms
- Single main subject clearly visible
- Professional photographic quality
- Subject well-lit and prominent

NEGATIVE ELEMENTS TO AVOID:
- Multiple subjects competing for attention
- Overly cluttered background
- Dark or underexposed subject
- Subject at edges or corners
- Modern or anachronistic elements
- Cartoon, illustration, or artistic styles

Purpose: YouTube thumbnail background - photorealistic, impactful, historically accurate, with clear space for text overlay."""

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

        # 右側縦書きテキストレイヤーを生成（赤文字＋黒縁）
        right_layer = self.text_renderer.render_vertical_text_right(top_text)

        # 左側縦書きテキストレイヤーを生成（白文字＋黒縁）
        left_layer = self.text_renderer.render_vertical_text_left(line1)

        # 右側テキストレイヤーを配置
        canvas.paste(right_layer, (0, 0), right_layer)

        # 左側テキストレイヤーを配置
        canvas.paste(left_layer, (0, 0), left_layer)

        # ファイル名を生成（安全な文字のみ使用）
        safe_line1 = "".join(c for c in line1 if c.isalnum() or c in (' ', '_'))[:20]
        filename = f"thumbnail_{subject}_{safe_line1}_v{index}.png"
        # ファイル名をクリーンアップ
        filename = filename.replace(" ", "_").replace("　", "_")
        output_path = output_dir / filename

        # 保存
        canvas.convert('RGB').save(output_path, 'PNG', quality=95)

        return output_path

    def _add_text_overlay(
        self,
        image: Image.Image,
        upper_text: str,
        lower_text: str
    ) -> Image.Image:
        """
        3分割レイアウトでテキストを配置

        配置:
        - 上部25%: upper_text（黄色、90px、中央揃え）
        - 中央50%: 画像のみ
        - 下部25%: lower_text（白色、70px、中央揃え）

        Args:
            image: 背景画像
            upper_text: 上部テキスト
            lower_text: 下部テキスト

        Returns:
            テキスト配置済みの画像
        """
        width, height = image.size
        draw = ImageDraw.Draw(image)

        # ========================================
        # 上部テキスト（黄色、90px、中央揃え）
        # ========================================
        if upper_text:
            # フォント設定
            upper_font_size = 90
            upper_font = self._load_font(upper_font_size)

            # 色設定
            upper_color = (255, 215, 0)      # 黄色（ゴールド）
            upper_shadow_color = (0, 0, 0)   # 黒影

            # テキスト位置（上部25%の中央）
            upper_y_position = int(height * 0.125)  # 12.5% = 25%の中央

            # テキストを中央揃えで配置
            self._draw_text_with_shadow(
                draw=draw,
                text=upper_text,
                font=upper_font,
                position=(width // 2, upper_y_position),
                color=upper_color,
                shadow_color=upper_shadow_color,
                shadow_offset=5
            )

        # ========================================
        # 下部テキスト（白色、70px、中央揃え）
        # ========================================
        if lower_text:
            # フォント設定
            lower_font_size = 70
            lower_font = self._load_font(lower_font_size)

            # 色設定
            lower_color = (255, 255, 255)    # 白色
            lower_shadow_color = (0, 0, 0)   # 黒影

            # テキスト位置（下部25%の中央）
            lower_y_position = int(height * 0.875)  # 87.5% = 75% + 12.5%

            # テキストを中央揃えで配置
            self._draw_text_with_shadow(
                draw=draw,
                text=lower_text,
                font=lower_font,
                position=(width // 2, lower_y_position),
                color=lower_color,
                shadow_color=lower_shadow_color,
                shadow_offset=4
            )

        return image

    def _draw_text_with_shadow(
        self,
        draw: ImageDraw.Draw,
        text: str,
        font: ImageFont.FreeTypeFont,
        position: tuple,
        color: tuple,
        shadow_color: tuple,
        shadow_offset: int
    ):
        """
        影付きテキストを描画（中央揃え）

        Args:
            draw: ImageDrawオブジェクト
            text: 描画するテキスト
            font: フォント
            position: (x, y) - 中央の座標
            color: テキスト色
            shadow_color: 影の色
            shadow_offset: 影のオフセット（ピクセル）
        """
        x, y = position

        # テキストのバウンディングボックスを取得
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 中央揃えのため、左上座標を計算
        text_x = x - text_width // 2
        text_y = y - text_height // 2

        # 影を描画（4方向）
        for dx in [-shadow_offset, shadow_offset]:
            for dy in [-shadow_offset, shadow_offset]:
                draw.text(
                    (text_x + dx, text_y + dy),
                    text,
                    font=font,
                    fill=shadow_color
                )

        # メインテキストを描画
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=color
        )

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """
        フォントを読み込み

        Args:
            size: フォントサイズ

        Returns:
            フォントオブジェクト
        """
        # フォントパスのリスト（優先順位順）
        # Windows, Linux, Macの順で探索
        font_paths = [
            # Windows
            "C:/Windows/Fonts/msgothic.ttc",           # MSゴシック
            "C:/Windows/Fonts/meiryo.ttc",             # メイリオ
            "C:/Windows/Fonts/YuGothB.ttc",            # 游ゴシック Bold
            "C:/Windows/Fonts/msmincho.ttc",           # MS明朝
            # Linux
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
            # Mac
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
            "/Library/Fonts/ヒラギノ角ゴ ProN W6.otf",
        ]

        # 利用可能なフォントを探す
        for font_path in font_paths:
            try:
                if Path(font_path).exists():
                    self.logger.debug(f"Using font: {font_path}")
                    return ImageFont.truetype(font_path, size)
            except Exception as e:
                self.logger.debug(f"Could not load font {font_path}: {e}")

        # フォールバック: エラーを発生させる
        self.logger.error("No Japanese font found! Please install a Japanese font.")
        self.logger.error("Windows: Fonts should be in C:/Windows/Fonts/")
        self.logger.error("Recommended: msgothic.ttc, meiryo.ttc, or YuGothB.ttc")
        raise FileNotFoundError(
            "No Japanese font found. Please install MS Gothic, Meiryo, or Yu Gothic font."
        )

    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を取得"""
        return {
            "use_stable_diffusion": False,  # デフォルトは DALL-E

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
            "stable_diffusion": {
                "api_key_env": "STABILITY_API_KEY",
                "width": 1344,
                "height": 768,
                "model": "sdxl",
                "style": "photorealistic",
                "steps": 30,
                "cfg_scale": 7.5
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
