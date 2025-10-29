# config manager
"""
設定管理システム

YAMLファイルと環境変数から設定を読み込み、
プロジェクト全体で一元管理する。
"""

import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from .exceptions import (
    ConfigurationError,
    MissingAPIKeyError,
    InvalidConfigError
)


class ConfigManager:
    """
    設定ファイルを階層的に管理するクラス
    
    使用例:
        config = ConfigManager()
        claude_key = config.get_api_key("CLAUDE_API_KEY")
        script_config = config.get_phase_config(1)
        output_dir = config.get("paths.output_dir")
    """
    
    def __init__(
        self,
        main_config_path: Optional[str] = None,
        env_path: Optional[str] = None,
        project_root: Optional[Path] = None
    ):
        """
        初期化
        
        Args:
            main_config_path: メイン設定ファイルのパス（デフォルト: config/settings.yaml）
            env_path: .envファイルのパス（デフォルト: config/.env）
            project_root: プロジェクトルートディレクトリ（デフォルト: 自動検出）
        """
        # プロジェクトルートの決定
        if project_root is None:
            project_root = self._find_project_root()
        self.project_root = Path(project_root)
        
        # .envファイル読み込み
        if env_path is None:
            env_path = self.project_root / "config" / ".env"
        if Path(env_path).exists():
            load_dotenv(env_path)
        
        # メイン設定読み込み
        if main_config_path is None:
            main_config_path = self.project_root / "config" / "settings.yaml"
        
        try:
            with open(main_config_path, 'r', encoding='utf-8') as f:
                self.main_config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise ConfigurationError(
                f"Main config file not found: {main_config_path}"
            )
        except yaml.YAMLError as e:
            raise InvalidConfigError(str(main_config_path), str(e))
        
        # 各フェーズの設定を読み込み
        self.phase_configs = {}
        self._load_phase_configs()
    
    def _find_project_root(self) -> Path:
        """プロジェクトルートを自動検出"""
        current = Path.cwd()
        
        # 上位ディレクトリを探索
        for _ in range(5):  # 最大5階層上まで
            if (current / "config" / "settings.yaml").exists():
                return current
            if (current / "src" / "core" / "config_manager.py").exists():
                return current
            current = current.parent
        
        # 見つからなければカレントディレクトリ
        return Path.cwd()
    
    def _load_phase_configs(self):
        """各フェーズの設定ファイルを読み込み"""
        phases_config = self.main_config.get("phases", {})
        
        for phase_key, config_path in phases_config.items():
            full_path = self.project_root / config_path
            
            if not full_path.exists():
                # 設定ファイルが存在しない場合は警告して空辞書
                print(f"Warning: Phase config not found: {full_path}")
                self.phase_configs[phase_key] = {}
                continue
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    self.phase_configs[phase_key] = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise InvalidConfigError(str(full_path), str(e))
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        ドット記法で設定値を取得
        
        Args:
            key_path: "execution.skip_existing_outputs"のような形式
            default: キーが存在しない場合のデフォルト値
            
        Returns:
            設定値
            
        例:
            config.get("execution.skip_existing_outputs")  # True
            config.get("logging.level")  # "INFO"
        """
        keys = key_path.split('.')
        value = self.main_config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_api_key(self, env_var_name: str) -> str:
        """
        環境変数からAPIキーを取得
        
        Args:
            env_var_name: 環境変数名（例: "CLAUDE_API_KEY"）
            
        Returns:
            APIキー
            
        Raises:
            MissingAPIKeyError: キーが設定されていない場合
        """
        key = os.getenv(env_var_name)
        if not key:
            raise MissingAPIKeyError(env_var_name)
        return key
    
    def get_phase_config(self, phase_number: int) -> Dict[str, Any]:
        """
        フェーズの設定を取得
        
        Args:
            phase_number: フェーズ番号（1-8）
            
        Returns:
            フェーズの設定辞書
            
        Raises:
            InvalidConfigError: フェーズ設定が見つからない場合
        """
        # フェーズ番号をキーに変換（例: 1 → "01_script"）
        for key, config in self.phase_configs.items():
            if key.startswith(f"{phase_number:02d}_"):
                return config
        
        raise InvalidConfigError(
            "phases",
            f"Phase {phase_number} config not found"
        )
    
    def get_path(self, key: str) -> Path:
        """
        パス設定を絶対パスのPathオブジェクトとして取得
        
        Args:
            key: パスのキー（例: "working_dir", "output_dir"）
            
        Returns:
            絶対パスのPathオブジェクト
        """
        path_value = self.get(f"paths.{key}")
        if path_value is None:
            raise InvalidConfigError("paths", f"Path '{key}' not found")
        
        path = Path(path_value)
        
        # 相対パスの場合はプロジェクトルートからの相対パスとして解決
        if not path.is_absolute():
            path = self.project_root / path
        
        return path
    
    def ensure_directories(self):
        """
        必要なディレクトリを全て作成
        
        settings.yamlのpathsセクションに定義されている
        全てのディレクトリを作成する。
        """
        paths = self.main_config.get("paths", {})
        
        for key, path_str in paths.items():
            path = self.get_path(key)
            path.mkdir(parents=True, exist_ok=True)
    
    def update_phase_config(
        self,
        phase_number: int,
        key_path: str,
        value: Any,
        save: bool = False
    ):
        """
        フェーズ設定を動的に更新
        
        Args:
            phase_number: フェーズ番号
            key_path: "settings.stability"のような形式
            value: 新しい値
            save: Trueの場合、ファイルに保存
        """
        config = self.get_phase_config(phase_number)
        
        keys = key_path.split('.')
        target = config
        
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        target[keys[-1]] = value
        
        if save:
            # ファイルに保存（実装省略）
            pass
    
    def get_working_dir(self, subject: str) -> Path:
        """
        特定の偉人のワーキングディレクトリを取得
        
        Args:
            subject: 偉人名
            
        Returns:
            ワーキングディレクトリのPath
        """
        working_root = self.get_path("working_dir")
        return working_root / subject
    
    def get_phase_dir(self, subject: str, phase_number: int) -> Path:
        """
        特定のフェーズのディレクトリを取得
        
        Args:
            subject: 偉人名
            phase_number: フェーズ番号
            
        Returns:
            フェーズディレクトリのPath
        """
        phase_names = {
            1: "01_script",
            2: "02_audio",
            3: "03_images",
            4: "04_animated",
            5: "05_ai_videos",
            6: "06_bgm",
            7: "07_subtitles",
            8: "08_composition"
        }
        
        phase_name = phase_names.get(phase_number)
        if not phase_name:
            raise ValueError(f"Invalid phase number: {phase_number}")
        
        return self.get_working_dir(subject) / phase_name
    
    def __repr__(self) -> str:
        return f"ConfigManager(root={self.project_root})"


# ========================================
# グローバルインスタンス（シングルトン的に使用可能）
# ========================================

_global_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """
    グローバル設定インスタンスを取得
    
    初回呼び出し時にConfigManagerを初期化し、
    以降は同じインスタンスを返す。
    
    Returns:
        ConfigManagerインスタンス
    """
    global _global_config
    
    if _global_config is None:
        _global_config = ConfigManager()
    
    return _global_config


def reset_config():
    """グローバル設定をリセット（テスト用）"""
    global _global_config
    _global_config = None