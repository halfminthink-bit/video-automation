"""ASS字幕を生成するユーティリティ"""

import re
from pathlib import Path
from typing import Dict, List, Optional

from .style_loader import StyleLoader
from .style_converter import StyleConverter
from .animation_tags import AnimationTagBuilder


class ASSGenerator:
    """
    ASS形式の字幕を生成
    
    Phase 6とPhase 7で共通利用
    """
    
    def __init__(self, config_path: Path, font_name: str = "Arial", logger=None):
        """
        Args:
            config_path: subtitle_generation.yamlのパス
            font_name: フォント名
            logger: ロガー
        """
        self.style_loader = StyleLoader(config_path)
        self.style_converter = StyleConverter(font_name)
        self.animation_builder = AnimationTagBuilder()
        self.logger = logger
    
    def create_ass_header(
        self,
        resolution: tuple = (1920, 1080)
    ) -> str:
        """
        ASSヘッダーを作成
        
        Args:
            resolution: 解像度 (width, height)
        
        Returns:
            ASSヘッダー文字列
        """
        width, height = resolution
        
        # 基本ヘッダー
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""
        
        # スタイル定義を追加
        all_styles = self.style_loader.get_all_styles()
        style_section = self.style_converter.build_all_styles(all_styles, resolution)
        
        header += style_section + "\n\n[Events]\n"
        header += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        
        return header
    
    def create_ass_file(
        self,
        srt_path: Path,
        timing_data: Dict,
        output_path: Path
    ) -> Path:
        """
        SRTファイルをASS形式に変換（impact対応）
        
        Args:
            srt_path: SRTファイルのパス
            timing_data: subtitle_timing.json のデータ
            output_path: 出力先
        
        Returns:
            生成されたASSファイルのパス
        """
        # SRTを読み込んで各字幕にスタイルを適用
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        srt_blocks = srt_content.strip().split('\n\n')
        
        ass_events = []
        for block in srt_blocks:
            lines = block.split('\n')
            if len(lines) < 3:
                continue
            
            index = int(lines[0])
            timing = lines[1]
            text = '\\N'.join(lines[2:])
            
            # タイミングをASS形式に変換
            match = re.match(
                r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})',
                timing
            )
            if not match:
                continue
            
            start = f"{match.group(1)}:{match.group(2)}:{match.group(3)}.{match.group(4)[:2]}"
            end = f"{match.group(5)}:{match.group(6)}:{match.group(7)}.{match.group(8)[:2]}"
            
            # impact_levelを取得
            impact_level = 'none'
            if index <= len(timing_data.get('subtitles', [])):
                impact_level = timing_data['subtitles'][index - 1].get('impact_level', 'none')
            
            # スタイル設定を取得
            style_config = self.style_loader.get_style(impact_level)
            style_name = style_config.get('name', 'Normal')
            
            # アニメーションタグを生成
            animation_tags = self.animation_builder.build_all_tags(
                style_config.get('animations', [])
            )
            
            # テキストにアニメーションタグを追加
            formatted_text = f"{animation_tags}{text}" if animation_tags else text
            
            ass_events.append(f"Dialogue: 0,{start},{end},{style_name},,0,0,0,,{formatted_text}")
        
        # ASSファイルに書き込み
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.create_ass_header())
            f.write('\n'.join(ass_events))
        
        if self.logger:
            self.logger.info(f"ASS subtitle file created: {output_path}")
        
        return output_path
    
    def format_ass_time(self, seconds: float) -> str:
        """
        時間をASS形式にフォーマット
        
        Args:
            seconds: 秒数
        
        Returns:
            "0:00:00.00" 形式の文字列
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        # センチ秒を四捨五入し、99でクリップ
        centisecs = round((seconds % 1) * 100)
        if centisecs >= 100:
            centisecs = 99
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

