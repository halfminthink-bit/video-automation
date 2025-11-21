"""字幕スタイル設定の読み込み"""

from pathlib import Path
from typing import Dict
import yaml


class StyleLoader:
    """subtitle_generation.yamlから字幕スタイル設定を読み込む"""
    
    def __init__(self, config_path: Path):
        """
        Args:
            config_path: subtitle_generation.yamlのパス
        """
        self.config_path = config_path
        self.config = self._load_yaml()
    
    def _load_yaml(self) -> dict:
        """YAMLファイルを読み込み"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get_style(self, impact_level: str) -> Dict:
        """
        impact_levelに応じたスタイル設定を取得
        
        Args:
            impact_level: "none", "normal", "mega"
        
        Returns:
            スタイル設定の辞書
        """
        styles = self.config.get('styles', {})
        return styles.get(impact_level, styles.get('none', {}))
    
    def get_all_styles(self) -> Dict:
        """
        全スタイル設定を取得
        
        Returns:
            全スタイルの辞書
        """
        return self.config.get('styles', {})

