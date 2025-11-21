"""ASS字幕を生成するユーティリティ"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
        
        # デバッグ: 使用されているフォント名をログ出力
        if self.logger:
            for impact_level, style_config in all_styles.items():
                font_config = style_config.get('font', {})
                font_family = font_config.get('family', self.style_converter.default_font_name)
                font_size = font_config.get('size', 60)
                self.logger.info(f"📝 ASS字幕スタイル '{impact_level}': フォント='{font_family}', サイズ={font_size}px")
        
        header += style_section + "\n\n[Events]\n"
        header += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        
        return header
    
    def _parse_srt_timing(self, timing_str: str) -> Optional[Tuple[str, str]]:
        """
        SRTタイミング文字列をASS形式に変換
        
        Args:
            timing_str: SRT形式のタイミング（例: "00:00:01,234 --> 00:00:03,456"）
        
        Returns:
            (start, end) タプル、パース失敗時はNone
        """
        match = re.match(
            r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})',
            timing_str
        )
        if not match:
            return None
        
        start = f"{match.group(1)}:{match.group(2)}:{match.group(3)}.{match.group(4)[:2]}"
        end = f"{match.group(5)}:{match.group(6)}:{match.group(7)}.{match.group(8)[:2]}"
        return start, end
    
    def _parse_srt_block(self, block: str) -> Optional[Tuple[int, str, str]]:
        """
        SRTブロックをパース
        
        Args:
            block: SRTブロック文字列
        
        Returns:
            (index, timing, text) タプル、パース失敗時はNone
        """
        lines = block.split('\n')
        if len(lines) < 3:
            return None
        
        try:
            index = int(lines[0])
            timing = lines[1]
            text = '\\N'.join(lines[2:])
            return index, timing, text
        except (ValueError, IndexError):
            return None
    
    def _build_dialogue_line(
        self,
        index: int,
        start: str,
        end: str,
        text: str,
        timing_data: Dict
    ) -> str:
        """
        Dialogue行を構築
        
        Args:
            index: 字幕インデックス
            start: 開始時間（ASS形式）
            end: 終了時間（ASS形式）
            text: 字幕テキスト
            timing_data: subtitle_timing.json のデータ
        
        Returns:
            ASS形式のDialogue行
        """
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
        
        return f"Dialogue: 0,{start},{end},{style_name},,0,0,0,,{formatted_text}"
    
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
            parsed = self._parse_srt_block(block)
            if not parsed:
                continue
            
            index, timing, text = parsed
            
            # タイミングをASS形式に変換
            timing_result = self._parse_srt_timing(timing)
            if not timing_result:
                continue
            
            start, end = timing_result
            
            # Dialogue行を構築
            dialogue_line = self._build_dialogue_line(index, start, end, text, timing_data)
            ass_events.append(dialogue_line)
        
        # ASSファイルに書き込み
        header = self.create_ass_header()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(header)
            f.write('\n'.join(ass_events))
        
        if self.logger:
            self.logger.info(f"ASS subtitle file created: {output_path}")
            # デバッグ: ASSファイル内のフォント名を確認
            import re
            font_matches = re.findall(r'Style:.*?,(.*?),', header)
            if font_matches:
                unique_fonts = set(font_matches)
                self.logger.info(f"📝 ASSファイル内のフォント名: {', '.join(unique_fonts)}")
        
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

