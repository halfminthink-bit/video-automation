"""
GPT Image サムネイル生成器

OpenAI gpt-image-1で背景画像を生成し、Pillowで日本語テキストをオーバーレイします。
"""

import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont


# Ensure .env values override existing environment variables
load_dotenv(override=True)


class GPTImageThumbnailGenerator:
    """DALL-E 3 / gpt-image-1 + Pillowでサムネイルを生成"""
    
    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        model: str = "dall-e-3",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            width: サムネイルの幅（デフォルト: 1280）
            height: サムネイルの高さ（デフォルト: 720）
            model: 画像生成モデル（dall-e-3 または gpt-image-1）
            logger: ロガー
        """
        self.width = width
        self.height = height
        self.model = model
        self.client = OpenAI()
        self.logger = logger or logging.getLogger(__name__)
    
    def generate_thumbnail(
        self,
        title: str,
        subject: str,
        output_path: str,
        subtitle: Optional[str] = None,
        style: str = "dramatic",
        quality: str = "medium",
        layout: str = "center"
    ) -> Optional[str]:
        """
        サムネイルを生成
        
        Args:
            title: メインタイトル
            subject: 動画のテーマ
            output_path: 出力パス
            subtitle: サブタイトル（オプション）
            style: 画像のスタイル（dramatic, professional, minimalist）
            quality: 画像品質（low, medium, high）
            layout: テキストレイアウト（center, left, right）
            
        Returns:
            生成されたサムネイルのパス（失敗時はNone）
        """
        self.logger.info(f"Generating thumbnail for: {subject}")
        self.logger.info(f"Title: {title}")
        self.logger.info(f"Style: {style}, Quality: {quality}")
        
        try:
            # 1. gpt-image-1で背景画像を生成
            background_path = self._generate_background(subject, style, quality)
            
            if not background_path:
                self.logger.error("Failed to generate background image")
                return None
            
            # 2. Pillowでテキストをオーバーレイ
            final_path = self._overlay_text(
                background_path=background_path,
                title=title,
                subtitle=subtitle,
                output_path=output_path,
                layout=layout
            )
            
            self.logger.info(f"✓ Thumbnail generated: {final_path}")
            
            return final_path
            
        except Exception as e:
            self.logger.error(f"Failed to generate thumbnail: {e}", exc_info=True)
            return None
    
    def _generate_background(
        self,
        subject: str,
        style: str,
        quality: str
    ) -> Optional[str]:
        """
        gpt-image-1で背景画像を生成
        
        Args:
            subject: 動画のテーマ
            style: 画像のスタイル
            quality: 画像品質
            
        Returns:
            生成された背景画像のパス（失敗時はNone）
        """
        self.logger.info(f"Generating background image with {self.model}...")
        
        # プロンプトを構築
        prompt = self._build_image_prompt(subject, style)
        self.logger.debug(f"Image prompt: {prompt}")
        
        try:
            # 画像を生成
            if self.model == "dall-e-3":
                # DALL-E 3は quality パラメータをサポート
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard" if quality == "low" or quality == "medium" else "hd",
                    n=1
                )
            else:
                # gpt-image-1
                response = self.client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size="1024x1024",
                    quality=quality,
                    n=1
                )
            
            # 画像URLを取得
            image_url = response.data[0].url
            self.logger.info(f"Image generated: {image_url}")
            
            # 画像をダウンロード
            background_path = "/tmp/thumbnail_background.png"
            self._download_image(image_url, background_path)
            
            return background_path
            
        except Exception as e:
            self.logger.error(f"Failed to generate background: {e}", exc_info=True)
            return None
    
    def _build_image_prompt(self, subject: str, style: str) -> str:
        """
        画像生成プロンプトを構築
        
        Args:
            subject: 動画のテーマ
            style: 画像のスタイル
            
        Returns:
            画像生成プロンプト
        """
        # スタイル別のプロンプトテンプレート
        style_templates = {
            "dramatic": (
                "A dramatic and cinematic background image for a YouTube thumbnail about {subject}. "
                "Use bold colors, dramatic lighting, and high contrast. "
                "The image should be visually striking and attention-grabbing. "
                "No text, clean composition, suitable for overlay text."
            ),
            "professional": (
                "A professional and clean background image for a YouTube thumbnail about {subject}. "
                "Use a modern color palette, soft lighting, and balanced composition. "
                "The image should look polished and trustworthy. "
                "No text, minimalist design, suitable for overlay text."
            ),
            "minimalist": (
                "A minimalist and elegant background image for a YouTube thumbnail about {subject}. "
                "Use simple shapes, muted colors, and lots of negative space. "
                "The image should be clean and uncluttered. "
                "No text, abstract design, suitable for overlay text."
            ),
            "vibrant": (
                "A vibrant and colorful background image for a YouTube thumbnail about {subject}. "
                "Use bright colors, energetic composition, and dynamic elements. "
                "The image should be eye-catching and exciting. "
                "No text, bold design, suitable for overlay text."
            )
        }
        
        template = style_templates.get(style, style_templates["dramatic"])
        
        return template.format(subject=subject)
    
    def _download_image(self, url: str, output_path: str) -> None:
        """
        画像をダウンロード
        
        Args:
            url: 画像URL
            output_path: 出力パス
        """
        self.logger.debug(f"Downloading image from: {url}")
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        self.logger.debug(f"Image downloaded: {output_path}")
    
    def _overlay_text(
        self,
        background_path: str,
        title: str,
        subtitle: Optional[str],
        output_path: str,
        layout: str
    ) -> str:
        """
        Pillowでテキストをオーバーレイ
        
        Args:
            background_path: 背景画像のパス
            title: メインタイトル
            subtitle: サブタイトル
            output_path: 出力パス
            layout: テキストレイアウト
            
        Returns:
            生成されたサムネイルのパス
        """
        self.logger.info("Overlaying text with Pillow...")
        
        # 背景画像を読み込み
        img = Image.open(background_path)
        
        # 1024x1024 -> 1280x720にリサイズ（中央クロップ）
        img = self._resize_and_crop(img, self.width, self.height)
        
        # 半透明の黒いオーバーレイを追加（テキストの可読性向上）
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 100))
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        
        # 描画オブジェクトを作成
        draw = ImageDraw.Draw(img, 'RGBA')
        
        # フォントを読み込み
        try:
            # Noto Sans CJK JP Bold（TrueType Collection形式）
            title_font = ImageFont.truetype(
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 80, index=0
            )
            subtitle_font = ImageFont.truetype(
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 40, index=0
            )
            self.logger.info("日本語フォント（Noto Sans CJK Bold）を読み込みました")
        except Exception as e:
            self.logger.warning(f"日本語フォントの読み込みに失敗: {e}")
            self.logger.warning("デフォルトフォントを使用します")
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
        
        # テキストを描画
        if layout == "center":
            self._draw_text_center(draw, title, subtitle, title_font, subtitle_font)
        elif layout == "left":
            self._draw_text_left(draw, title, subtitle, title_font, subtitle_font)
        elif layout == "right":
            self._draw_text_right(draw, title, subtitle, title_font, subtitle_font)
        else:
            self._draw_text_center(draw, title, subtitle, title_font, subtitle_font)
        
        # RGBに変換して保存
        img_rgb = img.convert('RGB')
        img_rgb.save(output_path)
        
        self.logger.info(f"Text overlay completed: {output_path}")
        
        return output_path
    
    def _resize_and_crop(self, img: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """
        画像をリサイズして中央クロップ
        
        Args:
            img: 元画像
            target_width: 目標の幅
            target_height: 目標の高さ
            
        Returns:
            リサイズ・クロップされた画像
        """
        # アスペクト比を計算
        img_ratio = img.width / img.height
        target_ratio = target_width / target_height
        
        if img_ratio > target_ratio:
            # 幅が広すぎる場合
            new_height = target_height
            new_width = int(new_height * img_ratio)
        else:
            # 高さが高すぎる場合
            new_width = target_width
            new_height = int(new_width / img_ratio)
        
        # リサイズ
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 中央クロップ
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        right = left + target_width
        bottom = top + target_height
        
        img = img.crop((left, top, right, bottom))
        
        return img
    
    def _draw_text_center(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        subtitle: Optional[str],
        title_font: ImageFont.FreeTypeFont,
        subtitle_font: ImageFont.FreeTypeFont
    ) -> None:
        """中央配置でテキストを描画"""
        # タイトルのバウンディングボックスを取得
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        
        # タイトルの位置を計算
        title_x = (self.width - title_width) // 2
        title_y = (self.height - title_height) // 2
        
        # サブタイトルがある場合は上にずらす
        if subtitle:
            title_y -= 30
        
        # 影付きテキストを描画
        self._add_text_with_shadow(draw, title, (title_x, title_y), title_font, (255, 255, 255, 255))
        
        # サブタイトルを描画
        if subtitle:
            subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            subtitle_x = (self.width - subtitle_width) // 2
            subtitle_y = title_y + title_height + 20
            
            self._add_text_with_shadow(draw, subtitle, (subtitle_x, subtitle_y), subtitle_font, (200, 200, 200, 255))
    
    def _draw_text_left(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        subtitle: Optional[str],
        title_font: ImageFont.FreeTypeFont,
        subtitle_font: ImageFont.FreeTypeFont
    ) -> None:
        """左寄せでテキストを描画"""
        margin = 80
        
        # タイトルのバウンディングボックスを取得
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_height = title_bbox[3] - title_bbox[1]
        
        # タイトルの位置を計算
        title_x = margin
        title_y = (self.height - title_height) // 2
        
        # サブタイトルがある場合は上にずらす
        if subtitle:
            title_y -= 30
        
        # 影付きテキストを描画
        self._add_text_with_shadow(draw, title, (title_x, title_y), title_font, (255, 255, 255, 255))
        
        # サブタイトルを描画
        if subtitle:
            subtitle_x = margin
            subtitle_y = title_y + title_height + 20
            
            self._add_text_with_shadow(draw, subtitle, (subtitle_x, subtitle_y), subtitle_font, (200, 200, 200, 255))
    
    def _draw_text_right(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        subtitle: Optional[str],
        title_font: ImageFont.FreeTypeFont,
        subtitle_font: ImageFont.FreeTypeFont
    ) -> None:
        """右寄せでテキストを描画"""
        margin = 80
        
        # タイトルのバウンディングボックスを取得
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        
        # タイトルの位置を計算
        title_x = self.width - title_width - margin
        title_y = (self.height - title_height) // 2
        
        # サブタイトルがある場合は上にずらす
        if subtitle:
            title_y -= 30
        
        # 影付きテキストを描画
        self._add_text_with_shadow(draw, title, (title_x, title_y), title_font, (255, 255, 255, 255))
        
        # サブタイトルを描画
        if subtitle:
            subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            subtitle_x = self.width - subtitle_width - margin
            subtitle_y = title_y + title_height + 20
            
            self._add_text_with_shadow(draw, subtitle, (subtitle_x, subtitle_y), subtitle_font, (200, 200, 200, 255))
    
    def _add_text_with_shadow(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple,
        font: ImageFont.FreeTypeFont,
        fill: tuple,
        shadow_offset: int = 4
    ) -> None:
        """
        影付きテキストを描画
        
        Args:
            draw: 描画オブジェクト
            text: テキスト
            position: 位置 (x, y)
            font: フォント
            fill: テキストの色
            shadow_offset: 影のオフセット
        """
        x, y = position
        
        # 影（半透明の黒）
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text,
            font=font,
            fill=(0, 0, 0, 200)
        )
        
        # メインテキスト
        draw.text((x, y), text, font=font, fill=fill)
