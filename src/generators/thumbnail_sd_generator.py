"""
Thumbnail用Stable Diffusion画像生成器

Phase 8専用: サムネイル生成のための最適化されたSD生成器
- 1344x768サイズ（YouTube推奨サムネイルサイズ）
- JPEG形式（2MB制限対応）
- Phase 3とコードを共有しない独立実装
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

from ..core.models import CollectedImage, ImageClassification
from ..core.exceptions import APIError


class ThumbnailSDGenerator:
    """
    サムネイル用Stable Diffusion画像生成器

    Phase 3のSD生成器とは独立した実装。
    サムネイル用に1344x768・JPEG形式に最適化。

    使用例:
        generator = ThumbnailSDGenerator(api_key="...")
        image = generator.generate_thumbnail_image(
            prompt="A dramatic scene of...",
            subject="偉人名"
        )
    """

    def __init__(
        self,
        api_key: str,
        output_dir: Path = None,
        cache_dir: Path = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            api_key: Stability AI APIキー
            output_dir: 画像保存先
            cache_dir: キャッシュディレクトリ
            logger: ロガー
        """
        self.api_key = api_key
        self.base_url = "https://api.stability.ai/v1/generation"
        self.output_dir = output_dir or Path("data/working/thumbnail_images")
        self.cache_dir = cache_dir or Path("data/cache/thumbnail_images")
        self.logger = logger or logging.getLogger(__name__)

        # ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # サムネイル専用設定
        self.thumbnail_width = 1344
        self.thumbnail_height = 768
        self.output_format = "jpeg"  # 2MB制限対応
        self.jpeg_quality = 90

        # コスト追跡
        self.total_cost_usd = 0.0

        # 利用可能なモデル
        self.available_models = {
            "sd3": "stable-diffusion-v3-large",
            "sdxl": "stable-diffusion-xl-1024-v1-0",
            "sd15": "stable-diffusion-v1-5"
        }

    def generate_thumbnail_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        subject: str = "",
        cfg_scale: float = 7.0,
        steps: int = 30,
        model: str = "sdxl"
    ) -> CollectedImage:
        """
        サムネイル用画像を生成（1344x768, JPEG）

        Args:
            prompt: メインプロンプト
            negative_prompt: ネガティブプロンプト
            subject: 偉人名
            cfg_scale: CFGスケール
            steps: ステップ数
            model: 使用モデル

        Returns:
            CollectedImage: 生成された画像情報
        """
        self.logger.info(f"Generating thumbnail image with Stable Diffusion...")
        self.logger.info(f"Size: {self.thumbnail_width}x{self.thumbnail_height}, Format: JPEG")

        # サムネイル用の最適化されたプロンプト
        optimized_prompt = self._optimize_thumbnail_prompt(prompt, subject)
        optimized_negative = self._get_thumbnail_negative_prompt(negative_prompt)

        self.logger.debug(f"Optimized prompt: {optimized_prompt[:100]}...")

        try:
            # APIリクエスト
            response = self._call_api(
                prompt=optimized_prompt,
                negative_prompt=optimized_negative,
                width=self.thumbnail_width,
                height=self.thumbnail_height,
                cfg_scale=cfg_scale,
                steps=steps,
                model=model
            )

            # 画像データを取得
            image_data = self._extract_image_data(response)

            # ファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cache_key = hashlib.md5(optimized_prompt.encode()).hexdigest()
            filename = f"thumbnail_sd_{cache_key[:8]}_{timestamp}.jpg"
            file_path = self.output_dir / filename

            self.logger.debug(f"Saving thumbnail to: {file_path}")

            # 画像を保存
            image = Image.open(image_data)

            # JPEG用に色モード変換
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
                self.logger.debug(f"Converted image mode to RGB for JPEG")

            # JPEG保存（圧縮）
            image.save(
                file_path,
                'JPEG',
                quality=self.jpeg_quality,
                optimize=True
            )

            # ファイルサイズチェック
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"Thumbnail saved: {file_size_mb:.2f} MB")

            if file_size_mb > 2.0:
                self.logger.warning(
                    f"⚠️  Thumbnail size ({file_size_mb:.2f} MB) exceeds YouTube 2MB limit!"
                )

            # コスト計算（SDXL: $0.040/image）
            cost = 0.040
            self.total_cost_usd += cost

            # CollectedImageモデルを作成
            result_image = CollectedImage(
                image_id=cache_key,
                file_path=str(file_path),
                source_url="",
                source="stable-diffusion-thumbnail",
                classification=ImageClassification.DAILY_LIFE,
                keywords=[subject] if subject else [],
                resolution=(self.thumbnail_width, self.thumbnail_height),
                aspect_ratio=self.thumbnail_width / self.thumbnail_height,
                quality_score=0.9
            )

            self.logger.info(f"✓ Thumbnail generated successfully (cost: ${cost:.3f})")

            return result_image

        except Exception as e:
            self.logger.error(f"Failed to generate thumbnail: {e}")
            raise APIError("Stability AI", str(e))

    def _optimize_thumbnail_prompt(self, prompt: str, subject: str) -> str:
        """
        サムネイル用にプロンプトを最適化

        Args:
            prompt: 元のプロンプト
            subject: 偉人名

        Returns:
            最適化されたプロンプト
        """
        # サムネイル用の視覚的インパクト強化
        optimized = f"""A visually striking thumbnail image: {prompt}

Style: dramatic, high contrast, eye-catching
Composition: centered, bold, attention-grabbing
Subject: {subject}
Quality: cinematic, professional, high detail
Lighting: dramatic lighting, vivid colors
Purpose: YouTube thumbnail, must stand out"""

        return optimized

    def _get_thumbnail_negative_prompt(self, base_negative: str) -> str:
        """
        サムネイル用のネガティブプロンプト

        Args:
            base_negative: 基本ネガティブプロンプト

        Returns:
            サムネイル用ネガティブプロンプト
        """
        thumbnail_negative = """text, watermark, logo, copyright, signature,
blurry, low quality, pixelated, ugly, deformed,
boring, dull, low contrast, washed out colors,
cluttered, busy, confusing composition"""

        if base_negative:
            return f"{base_negative}, {thumbnail_negative}"
        else:
            return thumbnail_negative

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
        Stability AI APIを呼び出し

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
        # エンジンIDの取得
        engine_id = self.available_models.get(model, self.available_models["sdxl"])
        url = f"{self.base_url}/{engine_id}/text-to-image"

        # ヘッダー
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # ペイロード
        payload = {
            "text_prompts": [
                {
                    "text": prompt,
                    "weight": 1.0
                }
            ],
            "cfg_scale": cfg_scale,
            "width": width,
            "height": height,
            "samples": 1,
            "steps": steps
        }

        # 出力形式をJPEGに指定
        payload["output_format"] = "jpeg"

        # ネガティブプロンプトがあれば追加
        if negative_prompt:
            payload["text_prompts"].append({
                "text": negative_prompt,
                "weight": -1.0
            })

        # APIリクエスト
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            raise APIError(
                "Stability AI",
                f"API returned {response.status_code}: {response.text}"
            )

        return response

    def _extract_image_data(self, response: requests.Response):
        """
        APIレスポンスから画像データを抽出

        Args:
            response: APIレスポンス

        Returns:
            画像データ（BytesIO）
        """
        import base64
        from io import BytesIO

        data = response.json()

        if "artifacts" not in data or len(data["artifacts"]) == 0:
            raise APIError("Stability AI", "No image artifacts in response")

        # 最初の画像を取得
        image_b64 = data["artifacts"][0]["base64"]
        image_bytes = base64.b64decode(image_b64)

        return BytesIO(image_bytes)

    def get_total_cost(self) -> float:
        """総コスト（USD）を取得"""
        return self.total_cost_usd
