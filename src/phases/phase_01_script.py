"""
Phase 1: Script Generation - 台本生成フェーズ

Claude APIを使用して構造化された台本を生成する。
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional
import logging

# プロジェクトルートをパスに追加
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.core.phase_base import PhaseBase
from src.core.models import VideoScript, ScriptSection, BGMType
from src.core.config_manager import ConfigManager
from src.core.exceptions import (
    PhaseExecutionError,
    PhaseValidationError,
    ClaudeAPIError
)
from src.generators.script_generator import create_script_generator


class Phase01Script(PhaseBase):
    """
    Phase 1: 台本生成
    
    Claude APIを使用して、偉人についての
    構造化された動画台本を生成する。
    """
    
    def get_phase_number(self) -> int:
        return 1
    
    def get_phase_name(self) -> str:
        return "Script Generation"
    
    def check_inputs_exist(self) -> bool:
        """
        Phase 1は最初のフェーズなので、
        特別な入力ファイルは不要。
        偉人名（subject）があればOK。
        """
        return bool(self.subject)
    
    def check_outputs_exist(self) -> bool:
        """台本ファイルが存在するかチェック"""
        script_path = self.phase_dir / "script.json"
        return script_path.exists()
    
    def get_output_paths(self) -> list[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / "script.json",
            self.phase_dir / "metadata.json"
        ]
    
    def execute_phase(self) -> VideoScript:
        """
        台本生成の実行

        Returns:
            VideoScript: 生成された台本

        Raises:
            PhaseExecutionError: 生成失敗時
        """
        # === manual_overrides をチェック ===
        manual_script = self._load_manual_script()
        if manual_script:
            self.logger.info(f"✅ Using manual script from manual_overrides")
            self._save_script(manual_script)
            self._save_generation_metadata(manual_script)
            return manual_script

        # === 自動生成処理 ===
        self.logger.info(f"Generating script via API for: {self.subject}")

        try:
            # APIキーを取得
            api_key = self._get_api_key()
            
            # 台本生成器を作成
            generator = create_script_generator(
                api_key=api_key,
                config=self.phase_config,
                use_dummy=not api_key,  # APIキーがなければダミー使用
                logger=self.logger
            )
            
            # 台本を生成
            script_data = generator.generate(
                subject=self.subject,
                config=self.phase_config
            )
            
            # Pydanticモデルに変換
            script = self._convert_to_model(script_data)
            
            # ファイルに保存
            self._save_script(script)
            
            # メタデータを保存
            self._save_generation_metadata(script)
            
            return script
            
        except Exception as e:
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Script generation failed: {e}"
            ) from e
    
    def validate_output(self, output: VideoScript) -> bool:
        """
        生成された台本をバリデーション
        
        Args:
            output: 生成された台本
            
        Returns:
            バリデーション成功なら True
            
        Raises:
            PhaseValidationError: バリデーション失敗時
        """
        validation_config = self.phase_config.get("validation", {})
        
        # セクション数のチェック
        min_sections = validation_config.get("min_sections", 4)
        max_sections = validation_config.get("max_sections", 8)
        
        if not (min_sections <= len(output.sections) <= max_sections):
            raise PhaseValidationError(
                self.get_phase_number(),
                f"Invalid section count: {len(output.sections)} "
                f"(expected {min_sections}-{max_sections})"
            )
        
        # 各セクションの時間チェック
        min_duration = validation_config.get("min_section_duration", 60)
        max_duration = validation_config.get("max_section_duration", 240)
        
        for section in output.sections:
            if not (min_duration <= section.estimated_duration <= max_duration):
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Invalid section duration: {section.estimated_duration}s "
                    f"for section {section.section_id}"
                )
        
        # 総時間のチェック
        min_total = validation_config.get("min_total_duration", 600)
        max_total = validation_config.get("max_total_duration", 1200)
        
        if not (min_total <= output.total_estimated_duration <= max_total):
            raise PhaseValidationError(
                self.get_phase_number(),
                f"Invalid total duration: {output.total_estimated_duration}s "
                f"(expected {min_total}-{max_total}s)"
            )
        
        # BGM切り替え回数のチェック
        self._validate_bgm_suggestions(output, validation_config)
        
        self.logger.info("Script validation passed")
        return True
    
    def _validate_bgm_suggestions(
        self,
        script: VideoScript,
        validation_config: dict
    ):
        """
        BGM配置をバリデーション
        
        Args:
            script: 台本
            validation_config: バリデーション設定
            
        Raises:
            PhaseValidationError: BGM配置が不適切な場合
        """
        bgm_sequence = [section.bgm_suggestion for section in script.sections]
        
        # BGM切り替え回数を数える
        switches = 0
        for i in range(1, len(bgm_sequence)):
            if bgm_sequence[i] != bgm_sequence[i-1]:
                switches += 1
        
        max_switches = validation_config.get("max_bgm_switches", 2)
        if switches > max_switches:
            self.logger.warning(
                f"BGM switches: {switches} (max: {max_switches}). "
                f"Sequence: {[b.value for b in bgm_sequence]}"
            )
            # 警告のみで続行（厳密にしすぎない）
        
        # 最初と最後のBGMチェック（推奨）
        if validation_config.get("require_opening_at_start", True):
            if bgm_sequence[0] != BGMType.OPENING:
                self.logger.warning(
                    f"First section should use 'opening' BGM, "
                    f"but got '{bgm_sequence[0].value}'"
                )
        
        if validation_config.get("require_ending_at_end", True):
            if bgm_sequence[-1] != BGMType.ENDING:
                self.logger.warning(
                    f"Last section should use 'ending' BGM, "
                    f"but got '{bgm_sequence[-1].value}'"
                )
        
        self.logger.info(
            f"BGM validation: {switches} switches, "
            f"sequence: {' → '.join(b.value for b in bgm_sequence)}"
        )
    
    # ========================================
    # 内部メソッド
    # ========================================

    def _load_manual_script(self) -> Optional[VideoScript]:
        """
        manual_overrides から手動台本を読み込み

        Returns:
            VideoScript または None
        """
        # manual_overrides ディレクトリを確認
        input_dir = self.config.get_path("input_dir")
        manual_path = input_dir / "manual_overrides" / f"{self.subject}_script.json"

        if not manual_path.exists():
            self.logger.debug(f"No manual script found: {manual_path}")
            return None

        try:
            with open(manual_path, 'r', encoding='utf-8') as f:
                script_data = json.load(f)

            # Pydanticモデルに変換
            script = self._convert_to_model(script_data)

            self.logger.info(f"Manual script loaded: {manual_path}")
            return script

        except Exception as e:
            self.logger.error(f"Failed to load manual script: {e}")
            return None

    def _get_api_key(self) -> Optional[str]:
        """Claude APIキーを取得"""
        try:
            return self.config.get_api_key("CLAUDE_API_KEY")
        except Exception as e:
            self.logger.warning(f"Failed to get API key: {e}")
            self.logger.warning("Using dummy generator")
            return None
    
    def _convert_to_model(self, script_data: dict) -> VideoScript:
        """
        辞書データをPydanticモデルに変換
        
        Args:
            script_data: 台本データ（辞書）
            
        Returns:
            VideoScript モデル
        """
        # セクションを変換
        sections = [
            ScriptSection(**section_data)
            for section_data in script_data.get("sections", [])
        ]
        
        # VideoScriptを作成
        script = VideoScript(
            subject=script_data["subject"],
            title=script_data["title"],
            description=script_data["description"],
            sections=sections,
            total_estimated_duration=script_data["total_estimated_duration"],
            model_version=script_data.get("model_version", "unknown")
        )
        
        return script
    
    def _save_script(self, script: VideoScript):
        """
        台本をJSONファイルに保存
        
        Args:
            script: 台本モデル
        """
        output_path = self.phase_dir / "script.json"
        
        # Pydanticモデルを辞書に変換
        script_dict = script.model_dump(mode='json')
        
        # JSONファイルとして保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(script_dict, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Script saved: {output_path}")
    
    def _save_generation_metadata(self, script: VideoScript):
        """
        生成メタデータを保存
        
        Args:
            script: 台本モデル
        """
        metadata = {
            "subject": self.subject,
            "phase": self.get_phase_number(),
            "phase_name": self.get_phase_name(),
            "generated_at": script.generated_at.isoformat(),
            "model_version": script.model_version,
            "total_sections": len(script.sections),
            "total_duration": script.total_estimated_duration,
            "ai_video_sections": sum(
                1 for s in script.sections if s.requires_ai_video
            ),
            "atmosphere_distribution": self._get_atmosphere_distribution(script),
            "config_used": {
                "model": self.phase_config.get("model"),
                "temperature": self.phase_config.get("temperature"),
                "max_tokens": self.phase_config.get("max_tokens")
            }
        }
        
        self.save_metadata(metadata, "metadata.json")
    
    def _get_atmosphere_distribution(self, script: VideoScript) -> dict:
        """
        雰囲気の分布を集計
        
        Args:
            script: 台本モデル
            
        Returns:
            雰囲気ごとのカウント
        """
        distribution = {}
        for section in script.sections:
            atmosphere = section.atmosphere
            distribution[atmosphere] = distribution.get(atmosphere, 0) + 1
        
        return distribution
    
    def load_script(self) -> Optional[VideoScript]:
        """
        保存済みの台本を読み込み
        
        Returns:
            VideoScript または None（存在しない場合）
        """
        script_path = self.phase_dir / "script.json"
        
        if not script_path.exists():
            return None
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
            
            # Pydanticモデルに変換
            script = self._convert_to_model(script_data)
            
            self.logger.info(f"Script loaded: {script_path}")
            return script
            
        except Exception as e:
            self.logger.error(f"Failed to load script: {e}")
            return None


# ========================================
# スタンドアロン実行用
# ========================================

def main():
    """テスト実行"""
    from src.utils.logger import setup_logger
    
    # 設定とロガーを初期化
    config = ConfigManager()
    logger = setup_logger(
        name="phase_01_test",
        log_dir=config.get_path("logs_dir"),
        level="DEBUG"
    )
    
    # Phase 1を実行
    subject = "織田信長"
    
    phase = Phase01Script(
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
    print(f"Duration: {execution.duration_seconds:.2f}s")
    
    if execution.status.value == "completed":
        print(f"\nOutput files:")
        for path in execution.output_paths:
            print(f"  - {path}")
        
        # 台本を読み込んで表示
        script = phase.load_script()
        if script:
            print(f"\nGenerated Script:")
            print(f"  Title: {script.title}")
            print(f"  Sections: {len(script.sections)}")
            print(f"  Total Duration: {script.total_estimated_duration:.0f}s")
    else:
        print(f"\nError: {execution.error_message}")


if __name__ == "__main__":
    main()