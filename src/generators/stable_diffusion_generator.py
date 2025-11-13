"""
Stable Diffusion画像生成器

Stability AI APIを使用して高品質な歴史画像を生成する。
DALL-E 3より柔軟なスタイル制御が可能。

特徴:
- スタイル指定（写実、油絵、浮世絵等）
- ネガティブプロンプト対応
- LoRAモデル対応（将来）
- コスト効率良好（$0.040/image）
"""

import os
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import requests
from PIL import Image

from ..core.models import CollectedImage, ImageClassification
from ..core.exceptions import APIError


class StableDiffusionGenerator:
    """
    Stable Diffusion画像生成器
    
    使用例:
        generator = StableDiffusionGenerator(api_key="...")
        image = generator.generate(
            prompt="A dramatic scene of samurai battle...",
            negative_prompt="modern, text, watermark",
            style="photorealistic"
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
        self.output_dir = output_dir or Path("data/working/generated_images")
        self.cache_dir = cache_dir or Path("data/cache/generated_images")
        self.logger = logger or logging.getLogger(__name__)
        
        # ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # コスト追跡
        self.total_cost_usd = 0.0
        
        # 利用可能なモデル
        self.available_models = {
            "sd3": "stable-diffusion-v3-large",  # 最新、高品質
            "sdxl": "stable-diffusion-xl-1024-v1-0",  # 高速
            "sd15": "stable-diffusion-v1-5"  # 互換性重視
        }
    
    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        style: str = "photorealistic",
        width: int = 1344,
        height: int = 768,  # 16:9 (SDXL compatible)
        cfg_scale: float = 7.0,
        steps: int = 30,
        model: str = "sdxl",
        section_id: Optional[int] = None,
        keyword: str = "",
        output_format: str = "jpeg"  # "jpeg" or "png" - JPEG for smaller file size
    ) -> CollectedImage:
        """
        画像を生成

        Args:
            prompt: メインプロンプト（詳細な説明）
            negative_prompt: ネガティブプロンプト（除外したい要素）
            style: 画風プリセット
            width: 幅（64の倍数）
            height: 高さ（64の倍数）
            cfg_scale: CFGスケール（7.0-15.0推奨）
            steps: ステップ数（30-50推奨）
            model: 使用モデル（sd3, sdxl, sd15）
            section_id: セクションID（ファイル名用）
            keyword: 元のキーワード（キャッシュ用）
            output_format: 出力形式（"jpeg" or "png"）- JPEGはファイルサイズが小さい

        Returns:
            CollectedImage: 生成された画像情報
        """
        # キャッシュチェック
        cache_key = self._get_cache_key(prompt, width, height, model)
        cached_image = self._load_from_cache(cache_key)
        if cached_image:
            self.logger.info(f"Using cached SD image")
            return cached_image
        
        # スタイルプリセットを適用
        full_prompt, full_negative = self._apply_style_preset(
            prompt, negative_prompt, style
        )

        self.logger.info(f"🎨 Generating image with Stable Diffusion...")
        self.logger.info(f"📏 SD API Request: {width}x{height}, model={model}, steps={steps}")
        self.logger.debug(f"Prompt: {full_prompt[:100]}...")
        
        try:
            # APIリクエスト
            response = self._call_api(
                prompt=full_prompt,
                negative_prompt=full_negative,
                width=width,
                height=height,
                cfg_scale=cfg_scale,
                steps=steps,
                model=model,
                output_format=output_format
            )
            
            # 画像データを取得
            image_data = self._extract_image_data(response)
            
            # ファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # section_idがNoneの場合は1をデフォルトとする
            section_id_value = section_id if section_id is not None else 1
            section_prefix = f"section_{section_id_value:02d}_"
            # 出力形式に応じて拡張子を決定
            file_ext = "jpg" if output_format.lower() == "jpeg" else "png"
            filename = f"{section_prefix}sd_{cache_key[:8]}_{timestamp}.{file_ext}"
            file_path = self.output_dir / filename
            
            self.logger.debug(f"Generating filename with section_id={section_id_value}: {filename}")
            
            # 保存
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            self.logger.info(f"💾 SD image saved: {file_path}")

            # 解像度確認
            with Image.open(file_path) as img:
                actual_width, actual_height = img.size

            self.logger.info(f"📐 SD image size verification: {actual_width}x{actual_height} ({file_ext.upper()})")
            
            # コスト計算（Stability AI料金）
            cost_usd = self._calculate_cost(width, height, steps)
            self.total_cost_usd += cost_usd
            
            # CollectedImageモデルを作成
            image = CollectedImage(
                image_id=cache_key,
                file_path=str(file_path),
                source_url="https://api.stability.ai",
                source="stable-diffusion",
                classification=self._infer_classification(keyword or prompt),
                keywords=[keyword] if keyword else [prompt[:50]],
                resolution=(actual_width, actual_height),
                aspect_ratio=actual_width / actual_height,
                quality_score=0.95  # SDは高品質
            )
            
            # キャッシュに保存
            self._save_to_cache(cache_key, image)
            
            return image
            
        except Exception as e:
            self.logger.error(f"Failed to generate SD image: {e}")
            raise APIError("StabilityAI", str(e))
    
    def _call_api(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        cfg_scale: float,
        steps: int,
        model: str,
        output_format: str = "jpeg"
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
            output_format: 出力形式（"jpeg" or "png"）

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

        # 出力形式を指定（一部のAPIバージョンのみサポート）
        # サポートしていない場合は無視される
        if output_format.lower() == "jpeg":
            payload["output_format"] = "jpeg"

        # ネガティブプロンプトがあれば追加
        if negative_prompt:
            payload["text_prompts"].append({
                "text": negative_prompt,
                "weight": -1.0
            })
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            error_msg = f"API returned {response.status_code}: {response.text}"
            raise APIError("StabilityAI", error_msg)
        
        return response
    
    def _extract_image_data(self, response: requests.Response) -> bytes:
        """
        APIレスポンスから画像データを抽出
        
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
    
    def _apply_style_preset(
        self,
        prompt: str,
        negative_prompt: str,
        style: str
    ) -> tuple[str, str]:
        """
        スタイルプリセットを適用
        
        Args:
            prompt: 元のプロンプト
            negative_prompt: 元のネガティブプロンプト
            style: スタイル名
            
        Returns:
            (拡張プロンプト, 拡張ネガティブプロンプト)
        """
        style_presets = {
            "photorealistic": {
                "positive": ", photorealistic, 8k uhd, high quality, highly detailed, professional photography, cinematic lighting",
                "negative": "anime, cartoon, painting, illustration, drawing, art, sketch"
            },
            "oil_painting": {
                "positive": ", oil painting, classical art style, masterpiece, brushstroke texture, fine art",
                "negative": "photograph, 3d render, digital art, low quality"
            },
            "ukiyo-e": {
                "positive": ", ukiyo-e style, Japanese woodblock print, traditional Japanese art, Edo period, flat colors",
                "negative": "photograph, 3d, realistic, modern"
            },
            "watercolor": {
                "positive": ", watercolor painting, soft colors, artistic, flowing brushstrokes",
                "negative": "photograph, digital art, sharp edges"
            },
            "documentary": {
                "positive": ", documentary photography, historical accuracy, natural lighting, authentic",
                "negative": "fantasy, fictional, stylized, artistic interpretation"
            }
        }
        
        preset = style_presets.get(style, style_presets["photorealistic"])
        
        # 共通ネガティブプロンプト
        common_negative = "text, watermark, signature, logo, blurry, low quality, distorted, deformed"
        
        full_prompt = prompt + preset["positive"]
        full_negative = ", ".join(filter(None, [
            negative_prompt,
            preset["negative"],
            common_negative
        ]))
        
        return full_prompt, full_negative
    
    def _calculate_cost(self, width: int, height: int, steps: int) -> float:
        """
        生成コストを計算
        
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
    
    def _infer_classification(self, text: str) -> ImageClassification:
        """
        テキストから画像分類を推測
        
        Args:
            text: プロンプトまたはキーワード
            
        Returns:
            推測された分類
        """
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["portrait", "warlord", "person", "face"]):
            return ImageClassification.PORTRAIT
        elif any(word in text_lower for word in ["battle", "war", "fight", "combat"]):
            return ImageClassification.BATTLE
        elif any(word in text_lower for word in ["castle", "temple", "architecture", "building"]):
            return ImageClassification.ARCHITECTURE
        elif any(word in text_lower for word in ["landscape", "mountain", "river", "scenery"]):
            return ImageClassification.LANDSCAPE
        elif any(word in text_lower for word in ["document", "manuscript", "scroll"]):
            return ImageClassification.DOCUMENT
        else:
            return ImageClassification.DAILY_LIFE
    
    def _get_cache_key(
        self,
        prompt: str,
        width: int,
        height: int,
        model: str
    ) -> str:
        """キャッシュキーを生成"""
        content = f"{prompt}_{width}x{height}_{model}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[CollectedImage]:
        """キャッシュから読み込み"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            import json
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # ファイルが実際に存在するか確認
            if Path(data['file_path']).exists():
                # CollectedImageの現在のフィールドのみを抽出（古いフィールドを除外）
                valid_fields = {
                    'image_id', 'file_path', 'source_url', 'source',
                    'classification', 'keywords', 'resolution',
                    'aspect_ratio', 'quality_score'
                }
                filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                return CollectedImage(**filtered_data)
            else:
                cache_file.unlink()
                return None
                
        except Exception as e:
            self.logger.warning(f"Failed to load cache: {e}")
            # キャッシュが破損している場合は削除
            if cache_file.exists():
                cache_file.unlink()
            return None
    
    def _save_to_cache(self, cache_key: str, image: CollectedImage):
        """キャッシュに保存"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            import json
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(
                    image.model_dump(mode='json'),
                    f,
                    indent=2,
                    default=str
                )
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")
    
    def get_total_cost(self) -> float:
        """総コスト（USD）を取得"""
        return self.total_cost_usd