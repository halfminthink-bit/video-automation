# config manager
"""
設定管理システム

YAMLファイルと環境変数から設定を読み込み、
プロジェクト全体で一元管理する。

更新点（2025-10）:
- .env読込の堅牢化（config/.env 優先、無ければ find_dotenv）
- override オプションで「.env が OS 環境変数を上書き」可（開発向け）
- get_api_key() に default 引数を追加、require_env() を新設
- フェーズ設定・パス取得の既存APIは変更なし
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv, find_dotenv
from jinja2 import Environment, FileSystemLoader

from .exceptions import (
    ConfigurationError,
    MissingAPIKeyError,
    InvalidConfigError,
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
        project_root: Optional[Path] = None,
        *,
        env_override: bool = False,
    ):
        """
        初期化

        Args:
            main_config_path: メイン設定ファイルのパス（デフォルト: <root>/config/settings.yaml）
            env_path: .envファイルのパス（デフォルト: <root>/config/.env）
            project_root: プロジェクトルート（デフォルト: 自動検出）
            env_override: True の場合、.env の値で既存のプロセス環境変数を上書き（開発用）
        """
        # プロジェクトルートの決定
        if project_root is None:
            project_root = self._find_project_root()
        self.project_root = Path(project_root)

        # .env 読み込み（config/.env を最優先、無ければ find_dotenv で探索）
        if env_path is None:
            env_path = self.project_root / "config" / ".env"
        dotenv_path: Optional[str | Path] = env_path
        if not Path(env_path).exists():
            found = find_dotenv(usecwd=True)
            dotenv_path = found if found else None

        if dotenv_path:
            # override=False が既定: OS/User 環境変数 > .env
            load_dotenv(dotenv_path, override=env_override)

        # メイン設定読み込み
        if main_config_path is None:
            main_config_path = self.project_root / "config" / "settings.yaml"

        try:
            with open(main_config_path, "r", encoding="utf-8") as f:
                self.main_config: Dict[str, Any] = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise ConfigurationError(f"Main config file not found: {main_config_path}")
        except yaml.YAMLError as e:
            raise InvalidConfigError(str(main_config_path), str(e))

        # 各フェーズの設定を読み込み
        self.phase_configs: Dict[str, Dict[str, Any]] = {}
        self._load_phase_configs()

        # Jinja2環境の初期化
        prompts_dir = self.project_root / "config" / "prompts"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(prompts_dir))
        )

        # メモ: デバッグ用に .env の由来を残したい場合はここにロガーを挿入
        # ただしキー値そのものは絶対にログ出力しないこと。

    # -----------------------------
    # 内部ユーティリティ
    # -----------------------------
    def _find_project_root(self) -> Path:
        """プロジェクトルートを自動検出"""
        current = Path.cwd()

        # 上位ディレクトリを探索（最大5階層）
        for _ in range(5):
            if (current / "config" / "settings.yaml").exists():
                return current
            if (current / "src" / "core" / "config_manager.py").exists():
                return current
            current = current.parent

        # 見つからなければカレントディレクトリ
        return Path.cwd()

    def _load_phase_configs(self) -> None:
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
                with open(full_path, "r", encoding="utf-8") as f:
                    self.phase_configs[phase_key] = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise InvalidConfigError(str(full_path), str(e))

    # -----------------------------
    # 公開API
    # -----------------------------
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        ドット記法で設定値を取得

        例:
            config.get("execution.skip_existing_outputs")  # True
            config.get("logging.level")  # "INFO"
        """
        keys = key_path.split(".")
        value: Any = self.main_config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_api_key(self, env_var_name: str, *, default: Optional[str] = None) -> str:
        """
        環境変数から API キーを取得（単一の窓口）

        Args:
            env_var_name: 環境変数名（例: "CLAUDE_API_KEY"）
            default: 未設定時のデフォルト（None の場合は例外）

        Returns:
            APIキー文字列

        Raises:
            MissingAPIKeyError: 見つからない場合（default が None のとき）
        """
        val = os.getenv(env_var_name, default)
        if val is None or val == "":
            raise MissingAPIKeyError(env_var_name)
        return val

    def require_env(self, *names: str) -> Dict[str, str]:
        """
        複数の環境変数が揃っていることを検証して取得する

        Returns:
            {name: value} の辞書。1つでも欠けていれば例外。
        """
        missing = []
        out: Dict[str, str] = {}
        for n in names:
            v = os.getenv(n)
            if v:
                out[n] = v
            else:
                missing.append(n)
        if missing:
            raise MissingAPIKeyError(", ".join(missing))
        return out

    def get_phase_config(self, phase_number: int) -> Dict[str, Any]:
        """
        フェーズの設定を取得（例: 1 -> "01_script"）
        """
        for key, config in self.phase_configs.items():
            if key.startswith(f"{phase_number:02d}_"):
                return config

        raise InvalidConfigError("phases", f"Phase {phase_number} config not found")

    def get_path(self, key: str) -> Path:
        """
        パス設定を絶対パスの Path で取得（相対なら root 基準で解決）
        """
        path_value = self.get(f"paths.{key}")
        if path_value is None:
            raise InvalidConfigError("paths", f"Path '{key}' not found")

        path = Path(path_value)
        if not path.is_absolute():
            path = self.project_root / path
        return path

    def ensure_directories(self) -> None:
        """
        settings.yaml の paths セクションに定義されたディレクトリを作成
        """
        paths = self.main_config.get("paths", {})
        for _, _path in paths.items():
            resolved = Path(_path)
            if not resolved.is_absolute():
                resolved = self.project_root / resolved
            resolved.mkdir(parents=True, exist_ok=True)

    def update_phase_config(
        self,
        phase_number: int,
        key_path: str,
        value: Any,
        save: bool = False,
    ) -> None:
        """
        フェーズ設定を動的に更新（save=True の場合は永続化フックを追加予定）
        """
        config = self.get_phase_config(phase_number)

        keys = key_path.split(".")
        target = config

        for key in keys[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]

        target[keys[-1]] = value

        if save:
            # TODO: フェーズYAMLへの書き戻し（必要になったら実装）
            pass

    def get_working_dir(self, subject: str) -> Path:
        """
        特定の偉人のワーキングディレクトリを取得
        """
        working_root = self.get_path("working_dir")
        return working_root / subject

    def get_phase_dir(self, subject: str, phase_number: int) -> Path:
        """
        特定のフェーズのディレクトリを取得
        """
        phase_names = {
            1: "01_script",
            2: "02_audio",
            3: "03_images",
            4: "04_animated",
            5: "05_bgm",
            6: "06_subtitles",
            7: "07_composition",
            8: "08_thumbnail",
            9: "09_youtube",
            10: "10_shorts",
            11: "11_tiktok",
        }

        phase_name = phase_names.get(phase_number)
        if not phase_name:
            raise ValueError(f"Invalid phase number: {phase_number}")

        return self.get_working_dir(subject) / phase_name

    def get_genre_config(self, genre_name: str) -> Dict[str, Any]:
        """
        ジャンル設定を読み込み

        Args:
            genre_name: ジャンル名（例: "ijin"）

        Returns:
            ジャンル設定の辞書

        Raises:
            InvalidConfigError: ファイルが見つからない
        """
        genre_path = self.project_root / "config" / "genres" / f"{genre_name}.yaml"

        if not genre_path.exists():
            raise InvalidConfigError(
                "genres",
                f"Genre config not found: {genre_name}"
            )

        with open(genre_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def get_variation_config(self, variation_type: str) -> Dict[str, Any]:
        """
        バリエーション設定を読み込み

        Args:
            variation_type: バリエーション種類（例: "audio", "thumbnail_text"）

        Returns:
            バリエーション設定の辞書

        Raises:
            InvalidConfigError: ファイルが見つからない
        """
        variation_path = self.project_root / "config" / "variations" / f"{variation_type}.yaml"

        if not variation_path.exists():
            raise InvalidConfigError(
                "variations",
                f"Variation config not found: {variation_type}"
            )

        with open(variation_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def load_prompt_template(self, template_path: str):
        """
        Jinja2プロンプトテンプレートを読み込んでレンダリング

        Args:
            template_path: テンプレートの相対パス（例: "script/ijin.j2"）

        Returns:
            レンダリング済みテンプレート（変数は未展開）
        """
        try:
            template = self.jinja_env.get_template(template_path)
            return template
        except Exception as e:
            raise InvalidConfigError(
                "prompts",
                f"Failed to load template: {template_path}, {e}"
            )

    def __repr__(self) -> str:
        return f"ConfigManager(root={self.project_root})"


# ========================================
# グローバルインスタンス（シングルトン的に使用可能）
# ========================================

_global_config: Optional[ConfigManager] = None


def get_config(*, env_override: bool = False) -> ConfigManager:
    """
    グローバル設定インスタンスを取得

    初回呼び出し時に ConfigManager を初期化し、
    以降は同じインスタンスを返す。
    """
    global _global_config

    if _global_config is None:
        _global_config = ConfigManager(env_override=env_override)

    return _global_config


def reset_config() -> None:
    """グローバル設定をリセット（テスト用）"""
    global _global_config
    _global_config = None
