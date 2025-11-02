"""
プロンプト最適化器

Claude APIを使用して、簡単なキーワードを
Stable Diffusion向けの詳細なプロンプトに最適化する。

例:
  "本能寺の変" 
  → "A dramatic historical scene of Honnō-ji Incident in 1582, 
     burning temple at night, samurai warriors..."
"""

import logging
from typing import Optional, Dict
from anthropic import Anthropic


class PromptOptimizer:
    """
    プロンプト最適化器
    
    使用例:
        optimizer = PromptOptimizer(api_key="...")
        prompt = optimizer.optimize(
            keyword="本能寺の変",
            atmosphere="劇的",
            context="織田信長の最期",
            image_type="battle"
        )
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            api_key: Anthropic APIキー
            model: 使用するClaudeモデル
            logger: ロガー
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.logger = logger or logging.getLogger(__name__)
        
        # キャッシュ（同じキーワードの再計算を避ける）
        self.cache: Dict[str, str] = {}
    
    def optimize(
        self,
        keyword: str,
        atmosphere: str = "壮大",
        context: str = "",
        image_type: str = "general",
        style: str = "photorealistic"
    ) -> str:
        """
        プロンプトを最適化
        
        Args:
            keyword: 基本キーワード（日本語OK）
            atmosphere: 雰囲気（壮大、静か、希望、劇的、悲劇的）
            context: セクションのコンテキスト
            image_type: 画像タイプ（portrait, battle, landscape, architecture等）
            style: 画風（photorealistic, oil_painting, ukiyo-e等）
            
        Returns:
            最適化されたプロンプト（英語、詳細）
        """
        # キャッシュチェック
        cache_key = f"{keyword}_{atmosphere}_{image_type}_{style}"
        if cache_key in self.cache:
            self.logger.info(f"Using cached prompt for '{keyword}'")
            return self.cache[cache_key]
        
        self.logger.info(f"Optimizing prompt for '{keyword}'...")
        
        # Claude APIで最適化
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                system=self._get_system_prompt(),
                messages=[{
                    "role": "user",
                    "content": self._build_user_prompt(
                        keyword, atmosphere, context, image_type, style
                    )
                }]
            )
            
            optimized_prompt = response.content[0].text.strip()
            
            # キャッシュに保存
            self.cache[cache_key] = optimized_prompt
            
            self.logger.info(f"Optimized prompt: {optimized_prompt[:100]}...")
            
            return optimized_prompt
            
        except Exception as e:
            self.logger.error(f"Failed to optimize prompt: {e}")
            # フォールバック: 簡単な英訳
            return self._fallback_prompt(keyword, atmosphere, style)
    
    def _get_system_prompt(self) -> str:
        """システムプロンプト"""
        return """You are an expert prompt engineer for Stable Diffusion image generation.

Your task is to convert simple Japanese keywords into detailed, effective English prompts for historical documentary-style images.

Requirements:
1. Create detailed, vivid descriptions
2. Include historical context and accuracy
3. Specify composition, lighting, and atmosphere
4. Use Stable Diffusion-friendly terminology
5. Add style modifiers (photorealistic, cinematic, etc.)
6. Keep it under 200 words
7. NO explanations, ONLY the prompt

Output format: Just the optimized prompt, nothing else."""
    
    def _build_user_prompt(
        self,
        keyword: str,
        atmosphere: str,
        context: str,
        image_type: str,
        style: str
    ) -> str:
        """ユーザープロンプトを構築"""
        atmosphere_map = {
            "壮大": "epic and grand",
            "静か": "calm and serene",
            "希望": "hopeful and bright",
            "劇的": "dramatic and intense",
            "悲劇的": "tragic and somber"
        }
        atmosphere_en = atmosphere_map.get(atmosphere, "neutral")
        
        image_type_hints = {
            "portrait": "Focus on character details, facial expressions, period-accurate clothing",
            "battle": "Dynamic action, multiple figures, dramatic lighting, historically accurate weapons and armor",
            "landscape": "Wide composition, natural scenery, atmospheric perspective",
            "architecture": "Architectural details, historical accuracy, sense of scale",
            "document": "Ancient manuscript, aged paper, historical text details"
        }
        type_hint = image_type_hints.get(image_type, "")
        
        style_map = {
            "photorealistic": "photorealistic, high detail, documentary photography style",
            "oil_painting": "oil painting, classical art style, brushstroke texture",
            "ukiyo-e": "Japanese ukiyo-e woodblock print style, traditional Japanese art",
            "watercolor": "watercolor painting, soft colors, artistic interpretation"
        }
        style_desc = style_map.get(style, "photorealistic")
        
        prompt = f"""Convert this keyword into a detailed Stable Diffusion prompt:

Keyword: {keyword}
Context: {context}
Atmosphere: {atmosphere_en}
Image Type: {image_type} ({type_hint})
Style: {style_desc}

Create a prompt that will generate a high-quality historical documentary image.
Include:
- Detailed scene description
- Historical context
- Lighting and composition
- Atmosphere and mood
- Style modifiers
- Quality tags (masterpiece, best quality, highly detailed, etc.)

Remember: This is for a Japanese historical documentary video about {keyword}."""
        
        return prompt
    
    def _fallback_prompt(
        self,
        keyword: str,
        atmosphere: str,
        style: str
    ) -> str:
        """
        Claude API失敗時のフォールバック
        
        簡単な英訳プロンプトを生成
        """
        atmosphere_map = {
            "壮大": "epic and grand",
            "静か": "calm and serene",
            "希望": "hopeful and bright",
            "劇的": "dramatic and intense",
            "悲劇的": "tragic and somber"
        }
        atmosphere_en = atmosphere_map.get(atmosphere, "neutral")
        
        return f"""A {atmosphere_en} historical documentary-style image: {keyword}
        
Style: {style}, cinematic lighting, high detail, masterpiece, best quality
Composition: 16:9 aspect ratio, professional documentary photography
Atmosphere: {atmosphere_en}, historically accurate, rich in detail
Quality: 8k, highly detailed, photorealistic rendering"""
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self.cache.clear()
        self.logger.info("Prompt cache cleared")