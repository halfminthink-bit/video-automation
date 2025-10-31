# AI image generation
"""
AI画像生成器（DALL-E 3 / Stable Diffusion対応）

歴史上の人物や特定の建造物など、無料素材サイトでは
見つからない画像をAI生成する。
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
from ..core.exceptions import APIError
from PIL import Image
import requests


class ImageGenerator:
    """
    AI画像生成器
    
    使用例:
        generator = ImageGenerator(api_key="...")
        image = generator.generate_image(
            keyword="Oda Nobunaga portrait",
            atmosphere="壮大",
            section_context="尾張の大うつけ"
        )
    """
    
    def __init__(
        self,
        api_key: str,
        service: str = "dall-e-3",
        output_dir: Path = None,
        cache_dir: Path = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            api_key: OpenAI APIキー
            service: "dall-e-3" or "stable-diffusion"
            output_dir: 画像保存先
            cache_dir: キャッシュディレクトリ
            logger: ロガー
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is required. Install with: pip install openai")
        
        self.api_key = api_key
        self.service = service
        self.output_dir = output_dir or Path("data/working/generated_images")
        self.cache_dir = cache_dir or Path("data/cache/generated_images")
        self.logger = logger or logging.getLogger(__name__)
        
        # ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # OpenAIクライアント
        self.client = OpenAI(api_key=api_key)
        
        # コスト追跡
        self.total_cost_usd = 0.0
    
    def generate_image(
        self,
        keyword: str,
        atmosphere: str = "壮大",
        section_context: str = "",
        size: str = "1792x1024",
        quality: str = "standard",
        section_id: Optional[int] = None
    ) -> CollectedImage:
        """
        画像を生成
        
        Args:
            keyword: 検索キーワード（例: "samurai warlord portrait"）
            atmosphere: 雰囲気（壮大、静か、希望、劇的、悲劇的）
            section_context: セクションのタイトル（プロンプト強化用）
            size: 画像サイズ（"1024x1024", "1792x1024", "1024x1792"）
            quality: "standard" or "hd"
            section_id: セクションID（ファイル名用）
            
        Returns:
            CollectedImage: 生成された画像情報
        """
        # キャッシュチェック
        cache_key = self._get_cache_key(keyword, size, quality)
        cached_image = self._load_from_cache(cache_key)
        if cached_image:
            self.logger.info(f"Using cached image for '{keyword}'")
            return cached_image
        
        # プロンプトを構築
        prompt = self._build_prompt(keyword, atmosphere, section_context)
        self.logger.info(f"Generating image with prompt: {prompt[:100]}...")
        
        try:
            # DALL-E 3で生成
            response = self.client.images.generate(
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
            filename = f"{section_prefix}{cache_key[:8]}_{timestamp}.png"
            file_path = self.output_dir / filename
            
            # 保存
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            self.logger.info(f"Image generated and saved: {file_path}")
            
            # 解像度を取得
            with Image.open(file_path) as img:
                width, height = img.size
            
            # コスト計算（DALL-E 3の料金）
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
                quality_score=0.9  # AI生成は高品質
            )
            
            # キャッシュに保存
            self._save_to_cache(cache_key, image)
            
            return image
            
        except Exception as e:
            self.logger.error(f"Failed to generate image: {e}")
            raise APIError("DALL-E", str(e))
    
    def _build_prompt(
        self,
        keyword: str,
        atmosphere: str,
        section_context: str
    ) -> str:
        """
        生成プロンプトを構築
        
        Args:
            keyword: 基本キーワード
            atmosphere: 雰囲気
            section_context: セクションコンテキスト
            
        Returns:
            最適化されたプロンプト
        """
        # 雰囲気を英語に変換
        atmosphere_map = {
            "壮大": "epic and grand",
            "静か": "calm and serene",
            "希望": "hopeful and bright",
            "劇的": "dramatic and intense",
            "悲劇的": "tragic and somber"
        }
        atmosphere_en = atmosphere_map.get(atmosphere, "neutral")
        
        # プロンプトテンプレート
        prompt = f"""A {atmosphere_en} historical documentary-style image: {keyword}

Context: {section_context}

Style requirements:
- Photorealistic, cinematic lighting
- 16:9 aspect ratio composition
- Professional documentary quality
- Rich in historical detail
- Suitable for educational content
- No text, watermarks, or modern elements
- Atmospheric and evocative"""
        
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
        
        if "portrait" in keyword_lower or "warlord" in keyword_lower:
            return ImageClassification.PORTRAIT
        elif "castle" in keyword_lower or "architecture" in keyword_lower:
            return ImageClassification.ARCHITECTURE
        elif "battle" in keyword_lower or "war" in keyword_lower:
            return ImageClassification.BATTLE
        elif "landscape" in keyword_lower or "mountain" in keyword_lower:
            return ImageClassification.LANDSCAPE
        elif "temple" in keyword_lower or "monastery" in keyword_lower:
            return ImageClassification.ARCHITECTURE
        else:
            return ImageClassification.DAILY_LIFE
    
    def _get_cache_key(self, keyword: str, size: str, quality: str) -> str:
        """キャッシュキーを生成"""
        content = f"{keyword}_{size}_{quality}"
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
                return CollectedImage(**data)
            else:
                # キャッシュファイルはあるが実体がない場合は削除
                cache_file.unlink()
                return None
                
        except Exception as e:
            self.logger.warning(f"Failed to load cache: {e}")
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