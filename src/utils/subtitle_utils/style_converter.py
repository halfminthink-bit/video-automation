"""YAML設定をASS形式に変換"""

from typing import Dict


class StyleConverter:
    """字幕スタイル設定をASS形式に変換"""
    
    def __init__(self, font_name: str = "Arial"):
        """
        Args:
            font_name: デフォルトフォント名（YAML設定で上書き可能）
        """
        self.default_font_name = font_name
    
    def color_to_ass(self, hex_color: str) -> str:
        """
        HEXカラーコードをASS形式に変換
        
        Args:
            hex_color: "#FFFFFF" 形式
        
        Returns:
            "&HFFFFFF" 形式
        """
        hex_color = hex_color.lstrip('#')
        # ASS形式はBGR順（RGB逆順）
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H{b.upper()}{g.upper()}{r.upper()}"
        return "&HFFFFFF"  # デフォルトは白
    
    def build_style_line(self, style_config: Dict, resolution: tuple = (1920, 1080)) -> str:
        """
        スタイル設定からASSのStyle行を生成
        
        Args:
            style_config: YAMLから読み込んだスタイル設定
            resolution: 動画解像度
        
        Returns:
            ASS形式のStyle行
        """
        name = style_config.get('name', 'Normal')
        font = style_config.get('font', {})
        position = style_config.get('position', {})
        
        # フォント設定
        font_family = font.get('family', self.default_font_name)
        font_size = font.get('size', 60)
        
        # カラー設定
        primary_color = self.color_to_ass(font.get('color', '#FFFFFF'))
        outline_color = self.color_to_ass(font.get('stroke_color', '#000000'))
        
        # アウトライン・シャドウ
        outline_width = font.get('stroke_width', 2)
        shadow = 2 if font.get('shadow_enabled', True) else 0
        
        # 位置設定
        alignment = position.get('alignment', 2)
        margin_v = position.get('margin_v', 70)
        
        # ASS Style行を生成
        return (
            f"Style: {name},{font_family},{font_size},{primary_color},{primary_color},"
            f"{outline_color},&H80000000,1,0,0,0,100,100,0,0,1,{outline_width},{shadow},"
            f"{alignment},10,10,{margin_v},1"
        )
    
    def build_all_styles(self, styles: Dict, resolution: tuple = (1920, 1080)) -> str:
        """
        全スタイル定義をASS形式で生成
        
        Args:
            styles: 全スタイル設定の辞書
            resolution: 動画解像度
        
        Returns:
            ASS形式の全スタイル定義
        """
        style_lines = []
        for impact_level, style_config in styles.items():
            style_line = self.build_style_line(style_config, resolution)
            style_lines.append(style_line)
        
        return '\n'.join(style_lines)

