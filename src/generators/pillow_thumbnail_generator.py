"""
Pillow Thumbnail Generator
Pillowを使用してプロフェッショナルなYouTubeサムネイルを生成
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import logging


class PillowThumbnailGenerator:
    """Pillowを使用してプロフェッショナルなサムネイルを生成"""
    
    def __init__(self, width=1280, height=720):
        """
        初期化
        
        Args:
            width: サムネイルの幅（デフォルト: 1280px）
            height: サムネイルの高さ（デフォルト: 720px）
        """
        self.width = width
        self.height = height
        self.logger = logging.getLogger(__name__)
    
    def create_gradient_background(self, color1, color2):
        """
        グラデーション背景を作成
        
        Args:
            color1: 開始色（RGB tuple）
            color2: 終了色（RGB tuple）
            
        Returns:
            PIL.Image: グラデーション背景画像
        """
        base = Image.new('RGB', (self.width, self.height), color1)
        top = Image.new('RGB', (self.width, self.height), color2)
        mask = Image.new('L', (self.width, self.height))
        mask_data = []
        for y in range(self.height):
            mask_data.extend([int(255 * (y / self.height))] * self.width)
        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)
        return base
    
    def add_text_with_shadow(self, draw, text, position, font, fill, shadow_offset=3):
        """
        影付きテキストを追加
        
        Args:
            draw: ImageDraw.Draw オブジェクト
            text: 表示するテキスト
            position: テキストの位置（x, y）
            font: フォントオブジェクト
            fill: テキストの色
            shadow_offset: 影のオフセット（ピクセル）
        """
        x, y = position
        # 影（半透明の黒）
        draw.text((x + shadow_offset, y + shadow_offset), text, 
                 font=font, fill=(0, 0, 0, 180))
        # メインテキスト
        draw.text((x, y), text, font=font, fill=fill)
    
    def add_background_image(self, background_image_path, overlay_alpha=0.5):
        """
        背景画像を追加（暗いオーバーレイ付き）
        
        Args:
            background_image_path: 背景画像のパス
            overlay_alpha: オーバーレイの透明度（0.0-1.0）
            
        Returns:
            PIL.Image: 背景画像（オーバーレイ付き）
        """
        bg_img = Image.open(background_image_path)
        bg_img = bg_img.resize((self.width, self.height), Image.Resampling.LANCZOS)
        
        # 暗いオーバーレイを追加
        overlay = Image.new('RGBA', (self.width, self.height), 
                          (0, 0, 0, int(255 * overlay_alpha)))
        bg_img = bg_img.convert('RGBA')
        bg_img = Image.alpha_composite(bg_img, overlay)
        
        return bg_img
    
    def generate_thumbnail(self, title, subtitle=None, background_image=None, 
                          layout="center", output_path="thumbnail.png"):
        """
        サムネイルを生成
        
        Args:
            title: メインタイトル
            subtitle: サブタイトル（オプション）
            background_image: 背景画像のパス（オプション）
            layout: レイアウトパターン（"center", "left", "background"）
            output_path: 出力パス
            
        Returns:
            str: 生成されたサムネイルのパス
        """
        self.logger.info(f"サムネイル生成開始: {title}")
        
        # 背景を作成
        if background_image and layout == "background":
            self.logger.info(f"背景画像を使用: {background_image}")
            img = self.add_background_image(background_image, overlay_alpha=0.6)
        else:
            # グラデーション背景
            self.logger.info("グラデーション背景を作成")
            img = self.create_gradient_background(
                color1=(30, 30, 60),   # 濃い青
                color2=(60, 30, 90)    # 濃い紫
            )
            img = img.convert('RGBA')
        
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
        
        # レイアウトに応じてテキストを配置
        if layout == "center":
            self.logger.info("レイアウト: 中央配置")
            # 中央配置
            bbox = draw.textbbox((0, 0), title, font=title_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (self.width - text_width) // 2
            y = (self.height - text_height) // 2
            
            if subtitle:
                y -= 40  # サブタイトルのスペースを確保
            
            self.add_text_with_shadow(draw, title, (x, y), title_font, 
                                     (255, 255, 255, 255))
            
            if subtitle:
                bbox_sub = draw.textbbox((0, 0), subtitle, font=subtitle_font)
                sub_width = bbox_sub[2] - bbox_sub[0]
                x_sub = (self.width - sub_width) // 2
                y_sub = y + text_height + 20
                self.add_text_with_shadow(draw, subtitle, (x_sub, y_sub), 
                                         subtitle_font, (200, 200, 200, 255))
        
        elif layout == "left":
            self.logger.info("レイアウト: 左寄せ")
            # 左寄せ
            x = 80
            y = self.height // 2 - 60
            
            self.add_text_with_shadow(draw, title, (x, y), title_font, 
                                     (255, 255, 255, 255))
            
            if subtitle:
                y_sub = y + 100
                self.add_text_with_shadow(draw, subtitle, (x, y_sub), 
                                         subtitle_font, (200, 200, 200, 255))
        
        elif layout == "background":
            self.logger.info("レイアウト: 背景画像 + テキストオーバーレイ")
            # 背景画像 + 下部にテキスト
            x = 80
            y = self.height - 200
            
            self.add_text_with_shadow(draw, title, (x, y), title_font, 
                                     (255, 255, 255, 255), shadow_offset=4)
            
            if subtitle:
                y_sub = y + 100
                self.add_text_with_shadow(draw, subtitle, (x, y_sub), 
                                         subtitle_font, (200, 200, 200, 255), 
                                         shadow_offset=3)
        
        # RGB形式に変換して保存
        img = img.convert('RGB')
        img.save(output_path, quality=95)
        self.logger.info(f"サムネイルを生成しました: {output_path}")
        
        return output_path
