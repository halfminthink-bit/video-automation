"""
Stable Diffusion サムネイル生成器

Stability AI APIを使用してYouTubeサムネイル背景画像を生成する。
Phase 3と同じSD APIを使用し、視覚的な一貫性を確保。

特徴:
- Phase 3と同じStability AI APIエンドポイント
- Phase 3と同じモデル（sdxl）
- サムネイル専用プロンプト（V3.0レイアウト対応）
- テキストオーバーレイ用の空間確保
"""

import os
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import requests
from PIL import Image

from ..core.exceptions import APIError


class SDThumbnailGenerator:
    """
    Stable Diffusion サムネイル生成器

    Phase 3と同じSD APIを使用してサムネイル背景を生成。

    使用例:
        generator = SDThumbnailGenerator(
            api_key="...",
            logger=logger
        )
        image_path = generator.generate_thumbnail(
            subject="織田信長",
            catchcopy_main="なぜ死んだ？",
            catchcopy_sub="天下統一を目前に倒れた男",
            style="dramatic"
        )
    """

    def __init__(
        self,
        api_config: dict,
        output_dir: Path = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            api_config: SD API設定（yamlから読み込み）
            output_dir: 画像保存先
            logger: ロガー
        """
        # API設定を取得（環境変数から）
        api_key_env = api_config.get("api_key_env", "STABILITY_API_KEY")
        self.api_key = os.environ.get(api_key_env)
        if not self.api_key:
            raise ValueError(f"API key not found in environment: {api_key_env}")

        # Phase 3と同じAPI設定
        self.base_url = "https://api.stability.ai/v1/generation"
        self.model = api_config.get("model", "sdxl")

        # サムネイル生成パラメータ
        self.width = api_config.get("width", 1280)
        self.height = api_config.get("height", 720)
        self.cfg_scale = api_config.get("cfg_scale", 7.5)
        self.steps = api_config.get("steps", 30)
        self.sampler = api_config.get("sampler", "DPM++ 2M Karras")
        self.style = api_config.get("style", "dramatic")

        # プロンプトテンプレート
        self.prompt_template = api_config.get("prompt_template", "")
        self.negative_prompt = api_config.get("negative_prompt", "")

        self.output_dir = output_dir or Path("data/working/thumbnails/sd_backgrounds")
        self.logger = logger or logging.getLogger(__name__)

        # ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # コスト追跡
        self.total_cost_usd = 0.0

        # 利用可能なモデル（Phase 3と同じ）
        self.available_models = {
            "sd3": "stable-diffusion-v3-large",
            "sdxl": "stable-diffusion-xl-1024-v1-0",
            "sd15": "stable-diffusion-v1-5"
        }

        self.logger.info(f"SD Thumbnail Generator initialized (model: {self.model}, {self.width}x{self.height})")

    def generate_thumbnail(
        self,
        subject: str,
        catchcopy_main: str = "",
        catchcopy_sub: str = "",
        style: Optional[str] = None
    ) -> str:
        """
        サムネイル背景画像を生成

        Args:
            subject: 偉人名
            catchcopy_main: メインキャッチコピー（上部テキスト、5-8文字）
            catchcopy_sub: サブキャッチコピー（下部テキスト、15-25文字）
            style: スタイル（dramatic, professional, minimalist等）

        Returns:
            生成された画像のパス
        """
        style = style or self.style

        self.logger.info(f"Generating SD thumbnail for: {subject} (style: {style})")

        # プロンプトを生成（V3.0レイアウト対応）
        prompt = self._create_thumbnail_prompt(
            subject=subject,
            style=style
        )

        # ネガティブプロンプト
        negative_prompt = self._get_negative_prompt()

        self.logger.debug(f"Prompt: {prompt[:150]}...")

        try:
            # APIリクエスト（Phase 3と同じ方法）
            response = self._call_api(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=self.width,
                height=self.height,
                cfg_scale=self.cfg_scale,
                steps=self.steps,
                model=self.model
            )

            # 画像データを取得
            image_data = self._extract_image_data(response)

            # ファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cache_key = hashlib.md5(prompt.encode()).hexdigest()
            filename = f"{subject}_sd_bg_{cache_key[:8]}_{timestamp}.png"
            file_path = self.output_dir / filename

            # 保存
            with open(file_path, 'wb') as f:
                f.write(image_data)

            self.logger.info(f"SD thumbnail background saved: {file_path}")

            # コスト計算
            cost_usd = self._calculate_cost(self.width, self.height, self.steps)
            self.total_cost_usd += cost_usd
            self.logger.debug(f"Cost: ${cost_usd:.4f}")

            return str(file_path)

        except Exception as e:
            self.logger.error(f"Failed to generate SD thumbnail: {e}")
            raise APIError("StabilityAI", str(e))

    def _create_thumbnail_prompt(
        self,
        subject: str,
        style: str
    ) -> str:
        """
        サムネイル用プロンプトを作成（V3.0レイアウト対応）

        重要: テキストオーバーレイ用の空間を確保
        - 上部25%: メインキャッチ用空間
        - 中央50%: 人物の顔（明るく、中央に配置）
        - 下部25%: サブテキスト用空間

        Args:
            subject: 偉人名
            style: スタイル

        Returns:
            プロンプト
        """
        # スタイル別のキーワード
        style_keywords = {
            "dramatic": "dramatic lighting, intense atmosphere, cinematic",
            "professional": "professional photography, clean composition, elegant",
            "minimalist": "minimalist, simple background, focused",
            "vibrant": "vibrant colors, energetic, bold",
            "mysterious": "mysterious atmosphere, dramatic shadows, enigmatic"
        }

        additional_keywords = style_keywords.get(style, style_keywords["dramatic"])

        # テンプレートがある場合は使用
        if self.prompt_template:
            prompt = self.prompt_template.format(
                subject=subject,
                style=style,
                additional_style_keywords=additional_keywords
            )
        else:
            # デフォルトプロンプト（V3.0レイアウト）
            prompt = f"""A {style} portrait of {subject}, historical figure,
centered composition, bright lighting on face, professional photography,

IMPORTANT LAYOUT for text overlay (25/50/25):
- Top 25% area: Empty space for title text overlay
- Center 50% area: Person's face, well-lit, clearly visible, centered
- Bottom 25% area: Empty space for subtitle text overlay

Face should be centered and bright, not in shadows.
Background can be darker for contrast.

High quality, cinematic, 1280x720, YouTube thumbnail optimized,
{additional_keywords}, photorealistic, 8k uhd, highly detailed"""

        return prompt

    def _get_negative_prompt(self) -> str:
        """
        ネガティブプロンプトを取得

        Returns:
            ネガティブプロンプト
        """
        if self.negative_prompt:
            return self.negative_prompt

        # デフォルト（サムネイル用）
        return """text, watermark, signature, logo, blurry, low quality,
dark face, underexposed face, face in shadow,
cluttered background, busy composition,
anime, cartoon, illustration, painting"""

    def _call_api(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        cfg_scale: float,
        steps: int,
        model: str
    ) -> requests.Response:
        """
        Stability AI APIを呼び出し（Phase 3と同じ実装）

        Args:
            prompt: プロンプト
            negative_prompt: ネガティブプロンプト
            width: 幅
            height: 高さ
            cfg_scale: CFGスケール
            steps: ステップ数
            model: モデル名

        Returns:
            APIレスポンス
        """
        model_id = self.available_models.get(model, self.available_models["sdxl"])
        url = f"{self.base_url}/{model_id}/text-to-image"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "text_prompts": [
                {
                    "text": prompt,
                    "weight": 1.0
                }
            ],
            "cfg_scale": cfg_scale,
            "height": height,
            "width": width,
            "samples": 1,
            "steps": steps
        }

        # ネガティブプロンプトがあれば追加
        if negative_prompt:
            payload["text_prompts"].append({
                "text": negative_prompt,
                "weight": -1.0
            })

        self.logger.debug(f"Calling SD API: {url}")
        response = requests.post(url, headers=headers, json=payload, timeout=120)

        if response.status_code != 200:
            error_msg = f"API returned {response.status_code}: {response.text}"
            raise APIError("StabilityAI", error_msg)

        return response

    def _extract_image_data(self, response: requests.Response) -> bytes:
        """
        APIレスポンスから画像データを抽出（Phase 3と同じ実装）

        Args:
            response: APIレスポンス

        Returns:
            画像バイナリデータ
        """
        import base64

        data = response.json()

        # artifactsから最初の画像を取得
        if "artifacts" in data and len(data["artifacts"]) > 0:
            image_b64 = data["artifacts"][0]["base64"]
            return base64.b64decode(image_b64)
        else:
            raise ValueError("No image data in response")

    def _calculate_cost(self, width: int, height: int, steps: int) -> float:
        """
        生成コストを計算（Phase 3と同じ実装）

        Stability AI料金:
        - 1024x1024以下: $0.040
        - それ以上: 解像度に応じて増加

        Args:
            width: 幅
            height: 高さ
            steps: ステップ数

        Returns:
            コスト（USD）
        """
        # 基本料金
        base_cost = 0.040

        # 解像度による補正
        pixels = width * height
        if pixels > 1024 * 1024:
            multiplier = pixels / (1024 * 1024)
            base_cost *= multiplier

        # ステップ数による補正（50ステップを基準）
        if steps > 50:
            base_cost *= (steps / 50)

        return round(base_cost, 4)

    def get_total_cost(self) -> float:
        """総コスト（USD）を取得"""
        return self.total_cost_usd
