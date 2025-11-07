# AI image generation
"""
AI画像生成器（DALL-E 3 / Stable Diffusion対応）

歴史上の人物や特定の建造物など、無料素材サイトでは
見つからない画像をAI生成する。

v2.0の改善点:
- Stable Diffusion統合（Stability AI API）
- Claudeによるプロンプト最適化
- スタイル指定対応（写実、油絵、浮世絵等）
"""

import os
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..core.models import CollectedImage, ImageClassification
from ..core.exceptions import APIError, MissingAPIKeyError
from .prompt_optimizer import PromptOptimizer
from .stable_diffusion_generator import StableDiffusionGenerator
from PIL import Image
import requests


class ImageGenerator:
    """
    AI画像生成器（マルチサービス対応）
    
    サポートするサービス:
    - Stable Diffusion (Stability AI) - 推奨
    - DALL-E 3 (OpenAI) - フォールバック
    
    使用例:
        generator = ImageGenerator(
            service="stable-diffusion",
            api_key="...",
            claude_api_key="..."  # プロンプト最適化用
        )
        image = generator.generate_image(
            keyword="織田信長の肖像",
            atmosphere="壮大",
            section_context="尾張の大うつけ",
            style="photorealistic"
        )
    """
    
    def __init__(
        self,
        api_key: str,
        service: str = "stable-diffusion",
        claude_api_key: Optional[str] = None,
        output_dir: Path = None,
        cache_dir: Path = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            api_key: Stability AI または OpenAI APIキー
            service: "stable-diffusion" or "dall-e-3"
            claude_api_key: Claude APIキー（プロンプト最適化用、オプション）
            output_dir: 画像保存先
            cache_dir: キャッシュディレクトリ
            logger: ロガー
        """
        self.service = service
        self.api_key = api_key
        self.claude_api_key = claude_api_key  # 重要度判定用
        self.output_dir = output_dir or Path("data/working/generated_images")
        self.cache_dir = cache_dir or Path("data/cache/generated_images")
        self.logger = logger or logging.getLogger(__name__)
        
        # ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # プロンプト最適化器（オプション）
        self.prompt_optimizer = None
        if claude_api_key:
            try:
                self.prompt_optimizer = PromptOptimizer(
                    api_key=claude_api_key,
                    logger=self.logger
                )
                self.logger.info("Prompt optimizer enabled (Claude API)")
            except Exception as e:
                self.logger.warning(f"Failed to initialize prompt optimizer: {e}")
        
        # サービス別の生成器
        if self.service == "stable-diffusion":
            self.sd_generator = StableDiffusionGenerator(
                api_key=api_key,
                output_dir=output_dir,
                cache_dir=cache_dir,
                logger=logger
            )
            self.logger.info("Using Stable Diffusion (Stability AI)")
        elif self.service == "dall-e-3":
            if not OPENAI_AVAILABLE:
                raise ImportError("openai package required for DALL-E 3")
            self.openai_client = OpenAI(api_key=api_key)
            self.logger.info("Using DALL-E 3 (OpenAI)")
        else:
            raise ValueError(f"Unknown service: {service}")
        
        # コスト追跡
        self.total_cost_usd = 0.0
    
    def generate_image(
        self,
        keyword: str,
        atmosphere: str = "壮大",
        section_context: str = "",
        image_type: str = "general",
        style: str = "photorealistic",
        section_id: Optional[int] = None,
        is_first_image: bool = False,
        width: int = 1344,
        height: int = 768
    ) -> CollectedImage:
        """
        画像を生成（統一インターフェース）
        
        Args:
            keyword: 検索キーワード（日本語OK）
            atmosphere: 雰囲気（壮大、静か、希望、劇的、悲劇的）
            section_context: セクションのタイトル
            image_type: 画像タイプ（portrait, battle, landscape等）
            style: 画風（photorealistic, oil_painting, ukiyo-e等）
            section_id: セクションID
            is_first_image: 最初の画像かどうか（必ずcriticalにする）
            width: 幅
            height: 高さ
            
        Returns:
            CollectedImage: 生成された画像情報
        """
        self.logger.info(f"Generating image for '{keyword}' using {self.service}")
        
        # Step 1: プロンプト最適化（Claudeが利用可能な場合）
        if self.prompt_optimizer:
            try:
                optimized_prompt = self.prompt_optimizer.optimize(
                    keyword=keyword,
                    atmosphere=atmosphere,
                    context=section_context,
                    image_type=image_type,
                    style=style
                )
                self.logger.info("Using optimized prompt from Claude")
            except Exception as e:
                self.logger.warning(f"Prompt optimization failed, using fallback: {e}")
                optimized_prompt = self._create_fallback_prompt(
                    keyword, atmosphere, style
                )
        else:
            # Claude APIなしの場合はシンプルなプロンプト
            optimized_prompt = self._create_fallback_prompt(
                keyword, atmosphere, style
            )
        
        # Step 2: サービス別に画像生成
        if self.service == "stable-diffusion":
            image = self._generate_with_sd(
                prompt=optimized_prompt,
                keyword=keyword,
                style=style,
                width=width,
                height=height,
                section_id=section_id
            )
        elif self.service == "dall-e-3":
            image = self._generate_with_dalle(
                prompt=optimized_prompt,
                keyword=keyword,
                section_id=section_id
            )
        else:
            raise ValueError(f"Unknown service: {self.service}")
        
        return image
    
    def _generate_with_sd(
        self,
        prompt: str,
        keyword: str,
        style: str,
        width: int,
        height: int,
        section_id: Optional[int]
    ) -> CollectedImage:
        """Stable Diffusionで生成"""
        # ネガティブプロンプト（歴史的正確性のため）
        negative_prompt = "modern clothing, contemporary, anachronistic, fantasy elements"
        
        image = self.sd_generator.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            style=style,
            width=width,
            height=height,
            section_id=section_id,
            keyword=keyword
        )
        
        # コスト追跡
        self.total_cost_usd += self.sd_generator.get_total_cost()
        
        return image
    
    def _generate_with_dalle(
        self,
        prompt: str,
        keyword: str,
        section_id: Optional[int],
        size: str = "1792x1024",
        quality: str = "standard"
    ) -> CollectedImage:
        """DALL-E 3で生成"""
        self.logger.info(f"Generating with DALL-E 3...")
        
        try:
            # DALL-E 3で生成
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=1
            )
            
            # 画像URLを取得
            image_url = response.data[0].url
            
            # 画像をダウンロード
            image_data = requests.get(image_url).content
            
            # ファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            section_prefix = f"section_{section_id:02d}_" if section_id else ""
            cache_key = hashlib.md5(prompt.encode()).hexdigest()
            filename = f"{section_prefix}dalle_{cache_key[:8]}_{timestamp}.png"
            file_path = self.output_dir / filename
            
            # 保存
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            self.logger.info(f"DALL-E image saved: {file_path}")
            
            # 解像度を取得
            with Image.open(file_path) as img:
                width, height = img.size
            
            # コスト計算
            cost_usd = 0.04 if quality == "standard" else 0.08
            self.total_cost_usd += cost_usd
            
            # CollectedImageモデルを作成
            image = CollectedImage(
                image_id=cache_key,
                file_path=str(file_path),
                source_url=image_url,
                source="dall-e-3",
                classification=self._infer_classification(keyword),
                keywords=[keyword],
                resolution=(width, height),
                aspect_ratio=width / height,
                quality_score=0.9
            )
            
            return image
            
        except Exception as e:
            self.logger.error(f"DALL-E generation failed: {e}")
            raise APIError("OpenAI", str(e))
    
    def _create_fallback_prompt(
        self,
        keyword: str,
        atmosphere: str,
        style: str
    ) -> str:
        """
        Claude API なしの場合のシンプルなプロンプト
        
        Args:
            keyword: キーワード
            atmosphere: 雰囲気
            style: スタイル
            
        Returns:
            プロンプト
        """
        atmosphere_map = {
            "壮大": "epic and grand",
            "静か": "calm and serene",
            "希望": "hopeful and bright",
            "劇的": "dramatic and intense",
            "悲劇的": "tragic and somber"
        }
        atmosphere_en = atmosphere_map.get(atmosphere, "neutral")
        
        prompt = f"""A {atmosphere_en} historical documentary-style image: {keyword}

Style: {style}, cinematic lighting, high detail, masterpiece
Composition: 16:9 aspect ratio, professional documentary quality
Atmosphere: historically accurate, rich in detail
Quality: highly detailed, photorealistic"""
        
        return prompt
    
    def _infer_classification(self, keyword: str) -> ImageClassification:
        """
        キーワードから画像分類を推測
        
        Args:
            keyword: キーワード
            
        Returns:
            推測された分類
        """
        keyword_lower = keyword.lower()
        
        if any(word in keyword_lower for word in ["portrait", "肖像", "人物", "warlord"]):
            return ImageClassification.PORTRAIT
        elif any(word in keyword_lower for word in ["battle", "戦い", "合戦", "war"]):
            return ImageClassification.BATTLE
        elif any(word in keyword_lower for word in ["castle", "城", "temple", "寺", "architecture"]):
            return ImageClassification.ARCHITECTURE
        elif any(word in keyword_lower for word in ["landscape", "風景", "mountain", "山"]):
            return ImageClassification.LANDSCAPE
        elif any(word in keyword_lower for word in ["document", "古文書", "manuscript"]):
            return ImageClassification.DOCUMENT
        else:
            return ImageClassification.DAILY_LIFE
    

    
    def get_total_cost(self) -> float:
        """総コスト（USD）を取得"""
        return self.total_cost_usd