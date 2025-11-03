"""
Phase 6: 字幕生成（Subtitle Generation）

台本と音声解析データから字幕を生成し、SRT形式で出力する。
"""

import json
import sys
from pathlib import Path
from typing import List, Optional, Any
import logging

# プロジェクトルートをパスに追加
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.core.phase_base import PhaseBase
from src.core.models import (
    SubtitleGeneration,
    SubtitleEntry,
    VideoScript,
    ScriptSection,
    AudioGeneration,
    AudioSegment
)
from src.core.config_manager import ConfigManager
from src.core.exceptions import (
    PhaseExecutionError,
    PhaseValidationError,
    PhaseInputMissingError
)
from src.generators.subtitle_generator import create_subtitle_generator


class Phase06Subtitles(PhaseBase):
    """Phase 6: 字幕生成"""
    
    def get_phase_number(self) -> int:
        return 6
    
    def get_phase_name(self) -> str:
        return "Subtitle Generation"
    
    def check_inputs_exist(self) -> bool:
        """Phase 1（台本）とPhase 2（音声解析）の出力を確認"""
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        audio_analysis_path = self.config.get_phase_dir(self.subject, 2) / "audio_analysis.json"
        metadata_path = self.config.get_phase_dir(self.subject, 2) / "metadata.json"
        
        if not script_path.exists():
            self.logger.error(f"Script not found: {script_path}")
            return False
        
        if not audio_analysis_path.exists():
            self.logger.error(f"Audio analysis not found: {audio_analysis_path}")
            return False
        
        # metadata.jsonも確認（segments情報がある場合）
        if not metadata_path.exists():
            self.logger.warning(f"Audio metadata not found: {metadata_path}")
        
        return True
    
    def check_outputs_exist(self) -> bool:
        """字幕ファイルが存在するかチェック"""
        srt_path = self.phase_dir / "subtitles.srt"
        json_path = self.phase_dir / "subtitle_timing.json"
        
        exists = srt_path.exists() and json_path.exists()
        
        if exists:
            self.logger.info(f"Subtitles already exist: {srt_path}")
        
        return exists
    
    def get_output_paths(self) -> List[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / "subtitles.srt",
            self.phase_dir / "subtitle_timing.json",
            self.phase_dir / "metadata.json"
        ]
    
    def execute_phase(self) -> SubtitleGeneration:
        """
        字幕生成の実行
        
        Returns:
            SubtitleGeneration: 生成された字幕
            
        Raises:
            PhaseExecutionError: 実行エラー
        """
        self.logger.info(f"Generating subtitles for: {self.subject}")
        
        try:
            # 1. 台本を読み込み
            script = self._load_script()
            self.logger.info(
                f"Loaded script: {len(script.sections)} sections, "
                f"estimated {script.total_estimated_duration:.0f}s"
            )
            
            # 2. 音声情報を読み込み
            audio_segments = self._load_audio_segments()
            self.logger.info(f"Loaded audio segments: {len(audio_segments)}")
            
            # 3. 字幕生成器を作成
            generator = create_subtitle_generator(
                config=self.phase_config,
                logger=self.logger
            )
            
            # 4. 字幕を生成
            self.logger.info("Generating subtitles...")
            subtitles = generator.generate_subtitles(
                script=script,
                audio_segments=audio_segments,
                config=self.phase_config
            )
            
            # 5. SRTファイルを保存
            srt_path = self._save_srt_file(subtitles)
            
            # 6. タイミングJSONを保存
            timing_path = self._save_timing_json(subtitles)
            
            # 7. 結果をモデルに変換
            subtitle_gen = SubtitleGeneration(
                subject=self.subject,
                subtitles=subtitles,
                srt_path=str(srt_path),
            )
            
            # 8. メタデータを保存
            self._save_generation_metadata(subtitle_gen)
            
            self.logger.info(
                f"Subtitle generation complete: "
                f"{len(subtitles)} entries, "
                f"SRT: {srt_path}"
            )
            
            return subtitle_gen
            
        except Exception as e:
            self.logger.error(f"Subtitle generation failed: {e}", exc_info=True)
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Subtitle generation failed: {e}"
            ) from e
    
    def validate_output(self, output: SubtitleGeneration) -> bool:
        """
        生成された字幕をバリデーション
        
        Args:
            output: SubtitleGeneration モデル
            
        Returns:
            バリデーション成功なら True
            
        Raises:
            PhaseValidationError: バリデーション失敗時
        """
        self.logger.info("Validating subtitle output...")
        
        # SRTファイルが存在するか
        srt_path = Path(output.srt_path)
        if not srt_path.exists():
            raise PhaseValidationError(
                self.get_phase_number(),
                f"SRT file not found: {output.srt_path}"
            )
        
        # 字幕エントリ数チェック
        if len(output.subtitles) == 0:
            raise PhaseValidationError(
                self.get_phase_number(),
                "No subtitles generated"
            )
        
        # 各字幕エントリのバリデーション
        for i, subtitle in enumerate(output.subtitles):
            if subtitle.start_time < 0:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Subtitle {i} has negative start_time: {subtitle.start_time}"
                )
            
            if subtitle.end_time <= subtitle.start_time:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Subtitle {i} has invalid time range: "
                    f"{subtitle.start_time} - {subtitle.end_time}"
                )
            
            if not subtitle.text_line1.strip():
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Subtitle {i} has empty text_line1"
                )
        
        self.logger.info("Subtitle validation passed ✓")
        return True
    
    # ========================================
    # 内部メソッド
    # ========================================
    
    def _load_script(self) -> VideoScript:
        """
        Phase 1の台本を読み込み
        
        Returns:
            VideoScript モデル
            
        Raises:
            PhaseInputMissingError: 台本ファイルが見つからない場合
        """
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        
        if not script_path.exists():
            raise PhaseInputMissingError(
                self.get_phase_number(),
                [str(script_path)]
            )
        
        self.logger.debug(f"Loading script from: {script_path}")
        
        with open(script_path, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
        
        # Pydanticモデルに変換
        script = VideoScript(**script_data)
        
        return script
    
    def _load_audio_segments(self) -> List[AudioSegment]:
        """
        Phase 2の音声セグメント情報を読み込み
        
        Returns:
            AudioSegmentのリスト
            
        Note:
            metadata.jsonからsegments情報を取得。
            存在しない場合は、audio_analysis.jsonから基本情報を取得し、
            推定タイミングを計算する。
        """
        metadata_path = self.config.get_phase_dir(self.subject, 2) / "metadata.json"
        audio_analysis_path = self.config.get_phase_dir(self.subject, 2) / "audio_analysis.json"
        
        # metadata.jsonからsegmentsを取得を試みる
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            segments_data = metadata.get("segments", [])
            if segments_data:
                self.logger.info(f"Loaded {len(segments_data)} segments from metadata")
                return [AudioSegment(**seg) for seg in segments_data]
        
        # metadata.jsonにsegmentsがない場合、audio_analysis.jsonから推定
        self.logger.warning(
            "Segments not found in metadata.json. "
            "Estimating timing from audio_analysis.json"
        )
        
        if not audio_analysis_path.exists():
            raise PhaseInputMissingError(
                self.get_phase_number(),
                [str(audio_analysis_path)]
            )
        
        with open(audio_analysis_path, 'r', encoding='utf-8') as f:
            audio_analysis = json.load(f)
        
        # 台本から各セクションの推定時間を使用
        script = self._load_script()
        segments = []
        current_time = 0.0
        
        for section in script.sections:
            # 推定時間を使用（実際の音声時間がわからないため）
            duration = section.estimated_duration
            
            segment = AudioSegment(
                section_id=section.section_id,
                audio_path="",  # 不明
                duration=duration,
                start_time=current_time
            )
            segments.append(segment)
            current_time += duration
        
        self.logger.info(f"Estimated {len(segments)} segments from script")
        return segments
    
    def _save_srt_file(self, subtitles: List[SubtitleEntry]) -> Path:
        """
        SRTファイルを保存
        
        Args:
            subtitles: 字幕エントリのリスト
            
        Returns:
            保存されたSRTファイルのPath
        """
        srt_path = self.phase_dir / "subtitles.srt"
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            for subtitle in subtitles:
                # インデックス
                f.write(f"{subtitle.index}\n")
                
                # タイムコード（HH:MM:SS,mmm形式）
                start_str = self._format_srt_time(subtitle.start_time)
                end_str = self._format_srt_time(subtitle.end_time)
                f.write(f"{start_str} --> {end_str}\n")
                
                # テキスト（2行まで）
                if subtitle.text_line2:
                    f.write(f"{subtitle.text_line1}\n{subtitle.text_line2}\n")
                else:
                    f.write(f"{subtitle.text_line1}\n")
                
                # 空行
                f.write("\n")
        
        self.logger.info(f"SRT file saved: {srt_path}")
        return srt_path
    
    def _format_srt_time(self, seconds: float) -> str:
        """
        秒数をSRT形式（HH:MM:SS,mmm）に変換
        
        Args:
            seconds: 秒数
            
        Returns:
            SRT形式のタイムコード文字列
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _save_timing_json(self, subtitles: List[SubtitleEntry]) -> Path:
        """
        タイミングJSONを保存
        
        Args:
            subtitles: 字幕エントリのリスト
            
        Returns:
            保存されたJSONファイルのPath
        """
        timing_path = self.phase_dir / "subtitle_timing.json"
        
        timing_data = {
            "subject": self.subject,
            "subtitle_count": len(subtitles),
            "total_duration": max([s.end_time for s in subtitles]) if subtitles else 0,
            "subtitles": [
                {
                    "index": s.index,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.end_time - s.start_time,
                    "text_line1": s.text_line1,
                    "text_line2": s.text_line2
                }
                for s in subtitles
            ]
        }
        
        with open(timing_path, 'w', encoding='utf-8') as f:
            json.dump(timing_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Timing JSON saved: {timing_path}")
        return timing_path
    
    def _save_generation_metadata(self, subtitle_gen: SubtitleGeneration):
        """
        生成メタデータを保存
        
        Args:
            subtitle_gen: SubtitleGeneration モデル
        """
        metadata = {
            "subject": self.subject,
            "phase": self.get_phase_number(),
            "phase_name": self.get_phase_name(),
            "generated_at": subtitle_gen.generated_at.isoformat(),
            "subtitle_count": len(subtitle_gen.subtitles),
            "srt_path": subtitle_gen.srt_path,
            "total_duration": max([s.end_time for s in subtitle_gen.subtitles]) if subtitle_gen.subtitles else 0,
            "config_used": {
                "max_lines": self.phase_config.get("max_lines", 2),
                "max_chars_per_line": self.phase_config.get("max_chars_per_line", 20),
                "min_display_duration": self.phase_config.get("timing", {}).get("min_display_duration", 4.0),
                "max_display_duration": self.phase_config.get("timing", {}).get("max_display_duration", 6.0),
                "use_mecab": self.phase_config.get("morphological_analysis", {}).get("use_mecab", False)
            }
        }
        
        self.save_metadata(metadata, "metadata.json")
        self.logger.info("Generation metadata saved")


# ========================================
# スタンドアロン実行用
# ========================================

def main():
    """テスト実行"""
    from src.utils.logger import setup_logger
    
    # 設定とロガーを初期化
    config = ConfigManager()
    logger = setup_logger(
        name="phase_06_test",
        log_dir=config.get_path("logs_dir"),
        level="DEBUG"
    )
    
    # Phase 6を実行
    subject = "織田信長"
    
    phase = Phase06Subtitles(
        subject=subject,
        config=config,
        logger=logger
    )
    
    # 実行
    execution = phase.run(skip_if_exists=False)
    
    # 結果表示
    print(f"\n{'='*60}")
    print(f"Phase 6 Execution Result")
    print(f"{'='*60}")
    print(f"Status: {execution.status}")
    print(f"Duration: {execution.duration_seconds:.2f}s")
    
    if execution.status.value == "completed":
        print(f"\nOutput files:")
        for path in execution.output_paths:
            print(f"  - {path}")
        
        # 字幕を読み込んで表示
        srt_path = Path(execution.output_paths[0])
        if srt_path.exists():
            print(f"\nFirst 3 subtitles from SRT:")
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                entries = content.split('\n\n')[:3]
                for entry in entries:
                    print(f"\n---")
                    print(entry)
    else:
        print(f"\nError: {execution.error_message}")


if __name__ == "__main__":
    main()
