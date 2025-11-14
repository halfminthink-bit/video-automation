"""
Phase 01: 自動台本生成

責務: Claude APIで台本を自動生成し、JSON形式で保存
"""

import json
import yaml
import re
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
import sys

# ScriptNormalizerをimport
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from scripts.convert_manual_script import ScriptNormalizer
except ImportError:
    # フォールバック: 簡易版のnormalizer
    class ScriptNormalizer:
        @staticmethod
        def normalize(data: dict) -> dict:
            return data

from src.core.phase_base import PhaseBase
from src.core.models import VideoScript, ScriptSection, PhaseStatus
from src.core.config_manager import ConfigManager
from src.core.exceptions import PhaseExecutionError, PhaseValidationError
from src.generators.script_prompt_builder import ScriptPromptBuilder

try:
    import anthropic
except ImportError:
    anthropic = None


class Phase01AutoScript(PhaseBase):
    """Phase 01: 自動台本生成"""

    def __init__(self, subject: str, config: ConfigManager, logger):
        super().__init__(subject, config, logger)

        # 設定ファイルのパスを取得
        auto_script_config_path = self.config.project_root / "config" / "phases" / "auto_script_generation.yaml"

        # 設定読み込み
        if auto_script_config_path.exists():
            with open(auto_script_config_path, 'r', encoding='utf-8') as f:
                self.auto_config = yaml.safe_load(f) or {}
        else:
            raise FileNotFoundError(f"Auto script config not found: {auto_script_config_path}")

        # Claude APIクライアント
        if anthropic is None:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")

        try:
            api_key = config.get_api_key("CLAUDE_API_KEY")
        except Exception as e:
            raise ValueError(f"CLAUDE_API_KEY not found in environment: {e}")

        self.claude_client = anthropic.Anthropic(api_key=api_key)

        # プロンプトビルダー
        template_path = self.config.project_root / self.auto_config["prompt"]["template_path"]
        self.prompt_builder = ScriptPromptBuilder(template_path)

    def get_phase_number(self) -> int:
        return 1

    def get_phase_name(self) -> str:
        return "Auto Script Generation"

    def check_inputs_exist(self) -> bool:
        """Phase 1は最初のフェーズなので、偉人名があればOK"""
        return bool(self.subject)

    def check_outputs_exist(self) -> bool:
        """台本ファイルが存在するかチェック"""
        json_path = self.phase_dir / self.auto_config["output"]["final_json_filename"]
        return json_path.exists()

    def get_output_paths(self) -> list[Path]:
        """出力ファイルのパスリスト"""
        paths = [
            self.phase_dir / self.auto_config["output"]["final_json_filename"]
        ]
        if self.auto_config["output"]["save_raw_yaml"]:
            paths.append(self.phase_dir / "api_generated_script.yaml")
            paths.append(self.phase_dir / self.auto_config["output"]["raw_yaml_filename"])
        return paths

    def execute_phase(self) -> VideoScript:
        """
        Phase 01の実装

        Returns:
            VideoScript: 生成された台本
        """
        self.logger.info(f"=== Phase 01: Auto Script Generation for {self.subject} ===")

        # 1. プロンプト構築
        self.logger.info("Building prompt...")
        prompt = self._build_prompt()

        # 2. Claude API呼び出し
        self.logger.info("Calling Claude API...")
        raw_yaml_text = self._call_claude_api(prompt)

        # 3. YAMLパース
        self.logger.info("Parsing YAML...")
        script_dict = yaml.safe_load(raw_yaml_text)

        # 3.5. API生成YAMLを保存（デバッグ用）
        api_yaml_path = self._save_api_yaml(script_dict)

        # 4. 正規化
        self.logger.info("Normalizing script...")
        script_dict = self._normalize_script(script_dict)

        # 5. バリデーション
        self.logger.info("Validating script...")
        self._validate_script(script_dict)

        # 6. 正規化後YAMLを保存（デバッグ用）
        normalized_yaml_path = self._save_yaml(script_dict)

        # 7. JSON変換・保存
        json_path = self._save_json(script_dict)

        # 8. Pydanticモデルに変換
        script = self._convert_to_model(script_dict)

        self.logger.info(f"✅ Script generated successfully")
        self.logger.info(f"  - API YAML (raw): {api_yaml_path}")
        self.logger.info(f"  - Normalized YAML: {normalized_yaml_path}")
        self.logger.info(f"  - JSON: {json_path}")

        return script

    def validate_output(self, output: VideoScript) -> bool:
        """
        生成された台本をバリデーション

        Args:
            output: 生成された台本

        Returns:
            バリデーション成功なら True
        """
        # セクションが存在することを確認
        if len(output.sections) == 0:
            raise PhaseValidationError(
                self.get_phase_number(),
                "No sections found in script"
            )

        self.logger.info(f"Script validation passed: {len(output.sections)} sections")
        return True

    def _build_prompt(self) -> str:
        """プロンプト構築"""
        variables = self.auto_config.get("prompt", {}).get("variables", {})
        return self.prompt_builder.build(self.subject, variables)

    def _call_claude_api(self, prompt: str, attempt: int = 1) -> str:
        """Claude APIを呼び出してYAML台本を生成"""

        max_attempts = self.auto_config["retry"]["max_attempts"]
        delay = self.auto_config["retry"]["delay_seconds"]

        try:
            response = self.claude_client.messages.create(
                model=self.auto_config["claude_api"]["model"],
                max_tokens=self.auto_config["claude_api"]["max_tokens"],
                temperature=self.auto_config["claude_api"].get("temperature", 1.0),
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # レスポンスからテキスト抽出
            yaml_text = response.content[0].text

            # ```yaml ``` で囲まれている場合は除去
            if "```yaml" in yaml_text:
                yaml_text = yaml_text.split("```yaml")[1].split("```")[0].strip()
            elif "```" in yaml_text:
                yaml_text = yaml_text.split("```")[1].split("```")[0].strip()

            return yaml_text

        except Exception as e:
            self.logger.error(f"Claude API call failed (attempt {attempt}/{max_attempts}): {e}")

            if attempt < max_attempts:
                import time
                self.logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                return self._call_claude_api(prompt, attempt + 1)
            else:
                raise PhaseExecutionError(
                    self.get_phase_number(),
                    f"Claude API call failed after {max_attempts} attempts: {e}"
                ) from e

    def _normalize_script(self, script_dict: dict) -> dict:
        """台本を正規化（ScriptNormalizerを使用）"""
        return ScriptNormalizer.normalize(script_dict)

    def _validate_script(self, script_dict: dict):
        """台本をバリデーション"""

        if not self.auto_config["validation"]["strict_mode"]:
            return

        # 必須フィールドチェック
        required = self.auto_config["validation"]["required_fields"]
        for field in required:
            if field not in script_dict:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Required field missing: {field}"
                )

        # セクションごとの必須フィールド
        section_required = self.auto_config["validation"]["section_required_fields"]
        for i, section in enumerate(script_dict["sections"], 1):
            for field in section_required:
                if field not in section:
                    raise PhaseValidationError(
                        self.get_phase_number(),
                        f"Section {i}: Required field missing: {field}"
                    )

    def _save_api_yaml(self, script_dict: dict) -> Optional[Path]:
        """API生成直後のYAMLを保存（デバッグ用・正規化前）"""

        if not self.auto_config["output"]["save_raw_yaml"]:
            return None

        filename = "api_generated_script.yaml"
        yaml_path = self.phase_dir / filename

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(script_dict, f, allow_unicode=True, sort_keys=False)

        return yaml_path

    def _save_yaml(self, script_dict: dict) -> Optional[Path]:
        """正規化後のYAMLを保存（デバッグ用）"""

        if not self.auto_config["output"]["save_raw_yaml"]:
            return None

        filename = self.auto_config["output"]["raw_yaml_filename"]
        yaml_path = self.phase_dir / filename

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(script_dict, f, allow_unicode=True, sort_keys=False)

        return yaml_path

    def _save_json(self, script_dict: dict) -> Path:
        """JSONを保存"""

        filename = self.auto_config["output"]["final_json_filename"]
        json_path = self.phase_dir / filename

        # サムネイル情報の取得（convert_manual_script.pyと同じロジック）
        thumbnail_data = script_dict.get("thumbnail")
        if thumbnail_data is None:
            self.logger.warning("thumbnail field not found, using fallback")
            thumbnail = {
                "upper_text": script_dict["subject"],
                "lower_text": ""
            }
        else:
            thumbnail = {
                "upper_text": thumbnail_data.get("upper_text", script_dict["subject"]),
                "lower_text": thumbnail_data.get("lower_text", "")
            }

        # JSON形式に変換（convert_manual_script.pyと同じ形式）
        script_json = {
            "subject": script_dict["subject"],
            "title": script_dict["title"],
            "description": script_dict["description"],
            "thumbnail": thumbnail,
            "sections": [],
            "total_estimated_duration": 0,
            "generated_at": self._get_timestamp(),
            "model_version": "auto_v1"
        }

        # セクションを変換（正規化済みデータから）
        for section in script_dict["sections"]:
            # narrationは既に正規化済み（ScriptNormalizerで処理済み）
            narration_text = section.get("narration", "")

            script_json["sections"].append({
                "section_id": section.get("section_id", 0),
                "title": section.get("title", ""),
                "narration": narration_text,
                "estimated_duration": float(section.get("duration", 0)),
                "image_keywords": section.get("keywords", []),
                "atmosphere": section.get("atmosphere", ""),
                "requires_ai_video": False,
                "ai_video_prompt": None,
                "bgm_suggestion": section.get("bgm", "")
            })

            script_json["total_estimated_duration"] += section.get("duration", 0)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(script_json, f, indent=2, ensure_ascii=False)

        return json_path

    def _convert_to_model(self, script_dict: dict) -> VideoScript:
        """
        辞書データをPydanticモデルに変換

        Args:
            script_dict: 台本データ（辞書）

        Returns:
            VideoScript モデル
        """
        # セクションを変換（フィールド名をマッピング）
        sections = [
            ScriptSection(
                section_id=section.get("section_id", 0),
                title=section.get("title", ""),
                narration=section.get("narration", ""),
                estimated_duration=float(section.get("duration", 0)),
                image_keywords=section.get("keywords", []),
                atmosphere=section.get("atmosphere", ""),
                requires_ai_video=section.get("requires_ai_video", False),
                ai_video_prompt=section.get("ai_video_prompt"),
                bgm_suggestion=section.get("bgm", "main")
            )
            for section in script_dict.get("sections", [])
        ]

        # VideoScriptを作成
        script = VideoScript(
            subject=script_dict["subject"],
            title=script_dict["title"],
            description=script_dict["description"],
            sections=sections,
            total_estimated_duration=script_dict["total_estimated_duration"],
            model_version=script_dict.get("model_version", "auto_v1"),
            thumbnail=script_dict.get("thumbnail")
        )

        return script

    def _get_timestamp(self) -> str:
        """現在時刻のISO形式文字列"""
        return datetime.now().isoformat()


# ========================================
# スタンドアロン実行用
# ========================================

def main():
    """テスト実行"""
    from src.utils.logger import setup_logger

    # 設定とロガーを初期化
    config = ConfigManager()
    logger = setup_logger(
        name="phase_01_auto_test",
        log_dir=config.get_path("logs_dir"),
        level="DEBUG"
    )

    # Phase 1を実行
    subject = "織田信長"

    phase = Phase01AutoScript(
        subject=subject,
        config=config,
        logger=logger
    )

    # 実行
    execution = phase.run(skip_if_exists=False)

    # 結果表示
    print(f"\n{'='*60}")
    print(f"Phase 1 Execution Result")
    print(f"{'='*60}")
    print(f"Status: {execution.status}")
    if execution.duration_seconds:
        print(f"Duration: {execution.duration_seconds:.2f}s")

    if execution.status == PhaseStatus.COMPLETED:
        print(f"\nOutput files:")
        for path in execution.output_paths:
            print(f"  - {path}")
    else:
        print(f"\nError: {execution.error_message}")


if __name__ == "__main__":
    main()
