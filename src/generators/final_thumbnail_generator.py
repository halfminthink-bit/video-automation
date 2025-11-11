"""
最終版サムネイル生成器（V3.0）

25/50/25レイアウト:
- 上部25%: 赤グラデーション疑問形テキスト
- 中央50%: 人物の顔画像（明るいまま）
- 下部25%: 白文字＋黒縁説明文
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
from openai import OpenAI
import requests
from io import BytesIO

from .impact_text_generator import ImpactTextGenerator
from .simple_background_processor import SimpleBackgroundProcessor
from .v3_text_renderer import V3TextRenderer


class FinalThumbnailGenerator:
    """
    V3.0最終版サムネイル生成器

    - 上部25%: メインキャッチ（5-8文字、赤グラデーション）
    - 中央50%: 人物画像（DALL-E 3、明るいまま）
    - 下部25%: サブ説明文（15-25文字、白＋黒縁）
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
        self.text_generator = ImpactTextGenerator(
            model=config.get("catchcopy", {}).get("model", "gpt-4.1-mini"),
            logger=self.logger
        )

        self.background_processor = SimpleBackgroundProcessor(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        self.text_renderer = V3TextRenderer(
            canvas_size=self.canvas_size,
            logger=self.logger
        )

        # OpenAI クライアント
        self.openai_client = OpenAI()

        # レイアウト設定（25/50/25）
        self.layout = {
            "main_text_zone": 0.30,   # 上部30%
            "person_zone": 0.40,      # 中央40%
            "sub_text_zone": 0.30,    # 下部30%
        }

        self.logger.info(f"FinalThumbnailGenerator initialized: {self.canvas_size}")

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
        text_pairs = self.text_generator.generate_text_pairs(
            subject=subject,
            script_data=script_data,
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

        # 3. 背景画像をリサイズ（1792x1024 → 1280x720）
        background = background.resize(self.canvas_size, Image.Resampling.LANCZOS)
        self.logger.info(f"Background resized to: {background.size}")

        # 4. 背景を処理（軽いビネットのみ、暗くしない）
        vignette_strength = self.config.get("image_generation", {}).get("vignette_strength", 0.2)
        processed_background = self.background_processor.process_background(
            image=background,
            vignette_strength=vignette_strength
        )

        # 5. 各テキストペアでサムネイルを生成
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
        DALL-E 3で背景画像を生成（人物の顔を中央に）

        Args:
            subject: 動画のテーマ
            script_data: 台本データ

        Returns:
            生成された画像（Pillowオブジェクト）
        """
        self.logger.info("Generating background image with DALL-E 3 (person-centered)")

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
        DALL-E用のプロンプトを構築（人物の顔を中央に配置）

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
            content = first_section.get("content", "")[:150]
            context = f"Context: {content}"

        # 人物の顔を中央に配置するプロンプト
        dalle_style = self.config.get("dalle", {}).get("style", "dramatic")

        style_descriptions = {
            "dramatic": "dramatic lighting, cinematic composition",
            "professional": "professional photography, studio lighting",
            "historical": "historical setting, authentic period details",
            "artistic": "artistic illustration, painterly style"
        }

        style_desc = style_descriptions.get(dalle_style, "professional photography")

        prompt = f"""Professional portrait photograph of a person related to '{subject}'.

{context}

Requirements:
- Face clearly visible in the CENTER of the frame
- Looking at camera or slightly to side
- Dramatic but BRIGHT lighting (not dark!)
- Head and shoulders visible
- Simple background, minimal clutter
- NO text, NO YouTube UI elements, NO play buttons
- Photorealistic or high-quality illustration
- {style_desc}

Style: YouTube thumbnail optimized
Orientation: Horizontal (landscape 16:9)
Lighting: Bright and clear, face well-lit"""

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
            text_pair: テキストペア {"main": "...", "sub": "..."}
            output_dir: 出力ディレクトリ
            index: インデックス番号
            subject: テーマ

        Returns:
            生成されたサムネイルのパス
        """
        main_text = self._wrap_text(text_pair.get("main", ""), max_chars_per_line=4)
        sub_text = self._wrap_text(text_pair.get("sub", ""), max_chars_per_line=6)

        self.logger.debug(f"Generating thumbnail {index}: Main='{main_text}', Sub='{sub_text}'")

        # キャンバスを作成（背景をコピー）
        canvas = background.copy()

        # 上部ゾーンにメインテキストを配置
        main_zone_height = int(self.canvas_size[1] * self.layout["main_text_zone"])

        # メインテキストを描画（赤グラデーション）
        main_layer = self.text_renderer.render_main_text(
            text=main_text,
            zone_height=main_zone_height
        )

        # 下部ゾーンにサブテキストを配置
        sub_zone_height = int(self.canvas_size[1] * self.layout["sub_text_zone"])

        # サブテキストを描画（白＋黒縁、半透明背景付き）
        sub_layer = self.text_renderer.render_sub_text(
            text=sub_text,
            zone_height=sub_zone_height,
            with_background=True
        )

        # レイヤーを合成
        # メインテキストレイヤーを上部に配置
        canvas.paste(main_layer, (0, 0), main_layer)

        # サブテキストレイヤーを下部に配置
        sub_layer_y = int(self.canvas_size[1] * (1 - self.layout["sub_text_zone"]))
        canvas.paste(sub_layer, (0, sub_layer_y), sub_layer)

        # ファイル名を生成
        safe_main = "".join(c for c in main_text if c.isalnum() or c in (' ', '_'))[:20]
        filename = f"{subject}_{safe_main}_v{index}.png"
        output_path = output_dir / filename

        # 保存
        canvas.convert('RGB').save(output_path, 'PNG', quality=95)

        return output_path

    def _wrap_text(self, text: str, max_chars_per_line: int) -> str:
        """
        指定した文字数で自動改行

        Args:
            text: 元のテキスト
            max_chars_per_line: 1行あたりの最大文字数

        Returns:
            改行後のテキスト
        """
        if not text:
            return text

        wrapped_lines = []
        for raw_line in text.splitlines():
            segment = raw_line.strip()
            if not segment:
                continue

            if len(segment) <= max_chars_per_line:
                wrapped_lines.append(segment)
                continue

            buffer = ""
            for char in segment:
                buffer += char
                if len(buffer) >= max_chars_per_line:
                    wrapped_lines.append(buffer)
                    buffer = ""

            if buffer:
                wrapped_lines.append(buffer)

        # テキストが全く追加されなかった場合は元のテキストを返す
        if not wrapped_lines:
            return text

        return "\n".join(wrapped_lines)
