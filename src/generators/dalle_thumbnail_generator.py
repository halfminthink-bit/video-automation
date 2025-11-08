"""
DALL-E 3を使用したYouTubeサムネイル生成

OpenAI DALL-E 3 APIを使用して、文字入りの高品質なYouTubeサムネイルを生成します。
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
import requests
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)


class DallEThumbnailGenerator:
    """DALL-E 3を使用したサムネイル生成クラス"""
    
    def __init__(
        self,
        output_dir: Path,
        size: str = "1024x1024",
        quality: str = "standard",
    ):
        """
        初期化
        
        Args:
            output_dir: 出力ディレクトリ
            size: 画像サイズ（"1024x1024", "1024x1792", "1792x1024"）
            quality: 画質（"standard" or "hd"）
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.size = size
        self.quality = quality
        
        # OpenAI APIキーの確認
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        logger.info(f"DallEThumbnailGenerator initialized: {size}, {quality}")
    
    def _create_prompt(
        self,
        title: str,
        subject: str,
        style: str = "dramatic",
    ) -> str:
        """
        サムネイル生成用のプロンプトを作成
        
        Args:
            title: サムネイルに表示するタイトル（日本語）
            subject: 動画の主題
            style: スタイル（"dramatic", "elegant", "energetic", "mysterious"）
            
        Returns:
            DALL-E 3用のプロンプト
        """
        style_descriptions = {
            "dramatic": "dramatic lighting, high contrast, cinematic atmosphere",
            "elegant": "elegant design, sophisticated colors, refined composition",
            "energetic": "vibrant colors, dynamic composition, energetic atmosphere",
            "mysterious": "mysterious atmosphere, dark tones, intriguing composition",
        }
        
        style_desc = style_descriptions.get(style, style_descriptions["dramatic"])
        
        prompt = f"""
Create a professional YouTube thumbnail image with the following specifications:

TITLE TEXT (MUST BE CLEARLY VISIBLE):
"{title}"

SUBJECT:
{subject}

DESIGN REQUIREMENTS:
- The title text MUST be in large, bold Japanese characters
- Text should be prominently displayed in the upper-center or center area
- Use high contrast colors for maximum readability
- Add text outline/stroke (white or black) for visibility
- Add subtle shadow effect to the text
- {style_desc}
- Background should be visually striking and related to the subject
- Overall composition should be eye-catching and professional
- Optimized for YouTube thumbnail (16:9 aspect ratio feel)

STYLE:
- Professional, attention-grabbing
- Suitable for educational/historical content
- Clean, modern design
- High visual impact

The Japanese text "{title}" must be clearly readable and professionally integrated into the design.
"""
        return prompt
    
    def generate_thumbnail(
        self,
        title: str,
        subject: str,
        base_filename: str,
        style: str = "dramatic",
    ) -> Optional[Path]:
        """
        サムネイルを生成
        
        Args:
            title: サムネイルに表示するタイトル
            subject: 動画の主題
            base_filename: ベースファイル名
            style: スタイル
            
        Returns:
            生成された画像のパス（失敗時はNone）
        """
        try:
            # OpenAI clientのインポート（ここでインポートすることで、インストールされていない場合のエラーを遅延させる）
            from openai import OpenAI
            
            client = OpenAI()  # 環境変数OPENAI_API_KEYを自動使用
            
            # プロンプトを作成
            prompt = self._create_prompt(title, subject, style)
            
            logger.info(f"Generating thumbnail with DALL-E 3: {title}")
            logger.debug(f"Prompt: {prompt[:200]}...")
            
            # DALL-E 3で画像を生成
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=self.size,
                quality=self.quality,
                n=1,
            )
            
            # 画像URLを取得
            image_url = response.data[0].url
            logger.info(f"Image generated successfully: {image_url}")
            
            # 画像をダウンロード
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()
            
            # 画像を開く
            image = Image.open(BytesIO(image_response.content))
            
            # YouTubeサムネイル推奨サイズ（1280x720）にリサイズ
            if self.size == "1024x1024":
                # 1024x1024 → 1280x720にクロップ
                # 中央部分を16:9でクロップ
                width, height = image.size
                target_ratio = 16 / 9
                current_ratio = width / height
                
                if current_ratio > target_ratio:
                    # 横長すぎる場合、左右をクロップ
                    new_width = int(height * target_ratio)
                    left = (width - new_width) // 2
                    image = image.crop((left, 0, left + new_width, height))
                else:
                    # 縦長すぎる場合、上下をクロップ
                    new_height = int(width / target_ratio)
                    top = (height - new_height) // 2
                    image = image.crop((0, top, width, top + new_height))
                
                # 1280x720にリサイズ
                image = image.resize((1280, 720), Image.Resampling.LANCZOS)
            
            # ファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{base_filename}_dalle_{timestamp}.png"
            output_path = self.output_dir / filename
            
            # 保存
            image.save(output_path, "PNG", optimize=True)
            logger.info(f"✓ Thumbnail saved: {output_path}")
            
            return output_path
            
        except ImportError as e:
            logger.error(f"OpenAI package is not installed: {e}")
            logger.error("Please install it with: pip install openai")
            return None
        except Exception as e:
            logger.error(f"Failed to generate thumbnail with DALL-E 3: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}", exc_info=True)
            return None
    
    def generate_multiple_styles(
        self,
        title: str,
        subject: str,
        base_filename: str,
        styles: list[str] = None,
    ) -> list[Path]:
        """
        複数のスタイルでサムネイルを生成
        
        Args:
            title: サムネイルに表示するタイトル
            subject: 動画の主題
            base_filename: ベースファイル名
            styles: スタイルのリスト（デフォルト: ["dramatic", "elegant", "energetic"]）
            
        Returns:
            生成された画像のパスのリスト
        """
        if styles is None:
            styles = ["dramatic", "elegant", "energetic"]
        
        results = []
        for i, style in enumerate(styles, 1):
            logger.info(f"Generating thumbnail {i}/{len(styles)}: {style} style")
            path = self.generate_thumbnail(
                title=title,
                subject=subject,
                base_filename=f"{base_filename}_{i}",
                style=style,
            )
            if path:
                results.append(path)
        
        return results
