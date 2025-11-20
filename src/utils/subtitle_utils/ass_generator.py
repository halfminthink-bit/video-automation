"""ASS字幕を生成するユーティリティ"""

import re
from pathlib import Path
from typing import Dict, List, Optional


class ASSGenerator:
    """
    ASS形式の字幕を生成
    
    Phase 6とPhase 7で共通利用
    """
    
    def __init__(self, font_name: str = "Arial", logger=None):
        """
        Args:
            font_name: フォント名
            logger: ロガー
        """
        self.font_name = font_name
        self.logger = logger
    
    def create_ass_header(
        self,
        resolution: tuple = (1920, 1080)
    ) -> str:
        """
        ASSヘッダーを作成
        
        スタイル定義:
        - Normal: 白・60px・下部中央
        - ImpactNormal: 赤・70px・下部中央（普通インパクト）
        - ImpactMega: 白・100px・中央（特大インパクト、Phase 2で実装予定）
        
        Args:
            resolution: 解像度 (width, height)
        
        Returns:
            ASSヘッダー文字列
        """
        width, height = resolution
        
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Normal,{self.font_name},60,&HFFFFFF,&HFFFFFF,&H000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,70,1
Style: ImpactNormal,{self.font_name},70,&H0000FF,&H0000FF,&H000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,2,10,10,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
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
            
            # スタイルを決定
            style = 'ImpactNormal' if impact_level == 'normal' else 'Normal'
            
            ass_events.append(f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}")
        
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

