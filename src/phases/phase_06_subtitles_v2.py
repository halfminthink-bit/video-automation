"""
Phase 6: 字幕生成（Subtitle Generation）

台本と音声解析データから字幕を生成し、SRT形式で出力する。
"""

import json
import sys
from pathlib import Path
from typing import List, Optional, Any, Dict
import logging

# プロジェクトルートをパスに追加
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.core.phase_base import PhaseBase
from src.core.models import (
    SubtitleGeneration,
    SubtitleEntry
)
from src.core.config_manager import ConfigManager
from src.core.exceptions import (
    PhaseExecutionError,
    PhaseValidationError,
    PhaseInputMissingError
)
from src.generators.subtitle_generator import create_subtitle_generator


class Phase06SubtitlesV2(PhaseBase):
    """Phase 6: 字幕生成 V2（インパクト字幕対応）"""
    
    def get_phase_number(self) -> int:
        return 6
    
    def get_phase_name(self) -> str:
        return "Subtitle Generation"
    
    def check_inputs_exist(self) -> bool:
        """Phase 1（台本）とPhase 2（音声タイミング）の出力を確認"""
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        audio_timing_path = self.config.get_phase_dir(self.subject, 2) / "audio_timing.json"

        if not script_path.exists():
            self.logger.error(f"Script not found: {script_path}")
            return False

        # audio_timing.json が存在する場合は優先的に使用
        if audio_timing_path.exists():
            self.logger.info(f"Found audio timing data: {audio_timing_path}")
            return True

        # フォールバック：audio_analysis.json と metadata.json
        audio_analysis_path = self.config.get_phase_dir(self.subject, 2) / "audio_analysis.json"
        if not audio_analysis_path.exists():
            self.logger.error(
                f"Neither audio_timing.json nor audio_analysis.json found. "
                "Please run Phase 2 with with_timestamps enabled."
            )
            return False

        self.logger.warning(
            "Using fallback mode without timing data. "
            "For better subtitle sync, enable with_timestamps in Phase 2."
        )
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
        字幕生成の実行（シンプルなフロー制御のみ）

        Returns:
            SubtitleGeneration: 生成された字幕

        Raises:
            PhaseExecutionError: 実行エラー
        """
        self.logger.info(f"Generating subtitles for: {self.subject}")

        try:
            # 1. audio_timing.json を読み込み
            audio_timing_path = self.config.get_phase_dir(self.subject, 2) / "audio_timing.json"

            if not audio_timing_path.exists():
                raise PhaseInputMissingError(
                    self.get_phase_number(),
                    [str(audio_timing_path)]
                )

            with open(audio_timing_path, 'r', encoding='utf-8') as f:
                audio_timing_data = json.load(f)

            # 2. 字幕生成（generator に委譲）
            generator = create_subtitle_generator(
                config=self.phase_config,
                logger=self.logger
            )

            subtitles = generator.generate_subtitles_from_char_timings(
                audio_timing_data=audio_timing_data
            )

            # 3. 3行字幕修正（鍵かっこの場合のみ）
            subtitles = self._fix_three_line_quotations(subtitles)

            # 4. 句読点削除（分割後に実行）
            self.logger.info("Removing punctuation from subtitles...")
            subtitles = generator.splitter.remove_punctuation(subtitles)

            # 5. 句点での延長
            self.logger.info("Adjusting subtitle timing for sentence endings...")
            subtitles = generator.timing.extend_sentence_endings(subtitles)

            # 6. ギャップ最適化
            self.logger.info("Optimizing subtitle gaps...")
            subtitles = generator.timing.optimize_gaps(subtitles)

            # 7. SRT・JSONを保存
            srt_path = self._save_srt_file(subtitles)
            timing_path = self._save_timing_json(subtitles)

            # 8. 結果をモデルに変換
            subtitle_gen = SubtitleGeneration(
                subject=self.subject,
                subtitles=subtitles,
                srt_path=str(srt_path),
            )

            # 9. メタデータを保存
            self._save_generation_metadata(subtitle_gen)

            self.logger.info(
                f"Subtitle generation complete: {len(subtitles)} entries, "
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
                f.write(f"{subtitle.text_line1}\n")
                if subtitle.text_line2:
                    f.write(f"{subtitle.text_line2}\n")

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
        タイミングJSONを保存（impact_level付き）

        Args:
            subtitles: 字幕エントリのリスト

        Returns:
            保存されたJSONファイルのPath
        """
        timing_path = self.phase_dir / "subtitle_timing.json"
        
        # 台本からimpact_sentencesを読み込み
        impact_sentences = self._load_impact_sentences_from_script()

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
                    "text_line2": s.text_line2,
                    "impact_level": self._get_impact_level(s, impact_sentences)
                }
                for s in subtitles
            ]
        }

        with open(timing_path, 'w', encoding='utf-8') as f:
            json.dump(timing_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Timing JSON saved: {timing_path}")
        return timing_path

    def _load_impact_sentences_from_script(self) -> Dict[str, List[str]]:
        """
        台本(script.json)からimpact_sentencesを読み込み
        
        Note:
            - raw_script.yamlではなくscript.jsonから読み込む
            - convert_manual_script.pyで@@マーカー@@を検出してJSONに保存済み
        
        Returns:
            {'normal': ['sentence1', ...], 'mega': ['sentence2', ...]}
        """
        script_path = self.working_dir / "01_script" / "script.json"
        
        if not script_path.exists():
            self.logger.debug(f"script.json not found: {script_path}")
            return {'normal': [], 'mega': []}
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                script = json.load(f)
            
            impact_sentences = {'normal': [], 'mega': []}
            
            # 各セクションのimpact_sentencesを集約
            for section in script.get('sections', []):
                if 'impact_sentences' in section:
                    impact_sentences['normal'].extend(
                        section['impact_sentences'].get('normal', [])
                    )
                    impact_sentences['mega'].extend(
                        section['impact_sentences'].get('mega', [])
                    )
            
            self.logger.info(
                f"Loaded impact sentences: {len(impact_sentences['normal'])} normal, "
                f"{len(impact_sentences['mega'])} mega"
            )
            return impact_sentences
            
        except Exception as e:
            self.logger.warning(f"Failed to load impact sentences: {e}")
            return {'normal': [], 'mega': []}
    
    def _get_impact_level(
        self, 
        subtitle: SubtitleEntry, 
        impact_sentences: Dict[str, List[str]]
    ) -> str:
        """
        字幕のimpact_levelを判定（完全一致）
        
        変更点:
        - 部分一致（キーワードマッチ）→ 完全一致に変更
        - より正確に1文だけを指定できる
        
        Args:
            subtitle: 字幕エントリ
            impact_sentences: {'normal': [...], 'mega': [...]}
        
        Returns:
            "none" | "normal" | "mega"
        
        Example:
            字幕: "誰もが侮った男が、革命児となった。"
            impact_sentences: {
                "normal": ["誰もが侮った男が、革命児となった。"]
            }
            → return "normal"
        """
        # 字幕のテキスト全体を結合
        text = subtitle.text_line1 + (subtitle.text_line2 if subtitle.text_line2 else "")
        text = text.strip()
        
        # mega判定（完全一致）
        for sentence in impact_sentences.get('mega', []):
            if text == sentence.strip():
                return 'mega'
        
        # normal判定（完全一致）
        for sentence in impact_sentences.get('normal', []):
            if text == sentence.strip():
                return 'normal'
        
        return 'none'

    def _fix_three_line_quotations(
        self,
        subtitles: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        鍵かっこ内で3行になっている字幕を修正
        
        3行目がある場合:
        - 3行目を次の字幕の1行目に移動
        - 鍵かっこの場合のみ適用
        
        Args:
            subtitles: 字幕リスト
        
        Returns:
            修正後の字幕リスト
        """
        fixed_subtitles = []
        carry_over_text = ""  # 次の字幕に繰り越すテキスト
        
        for i, subtitle in enumerate(subtitles):
            # 前の字幕からの繰り越しがある場合
            if carry_over_text:
                # 現在の字幕の1行目に追加
                subtitle.text_line1 = carry_over_text + subtitle.text_line1
                carry_over_text = ""
            
            # 3行目があるかチェック
            if subtitle.text_line3:
                # 鍵かっこがある場合のみ処理
                full_text = subtitle.text_line1 + subtitle.text_line2 + subtitle.text_line3
                
                if '「' in full_text or '」' in full_text:
                    self.logger.debug(
                        f"Found 3-line quotation at subtitle {subtitle.index}, "
                        f"moving line3 to next subtitle"
                    )
                    
                    # 3行目を次の字幕に繰り越し
                    carry_over_text = subtitle.text_line3
                    
                    # 現在の字幕は2行に修正
                    new_subtitle = SubtitleEntry(
                        index=subtitle.index,
                        start_time=subtitle.start_time,
                        end_time=subtitle.end_time,
                        text_line1=subtitle.text_line1,
                        text_line2=subtitle.text_line2
                    )
                    fixed_subtitles.append(new_subtitle)
                else:
                    # 鍵かっこがない場合はそのまま
                    fixed_subtitles.append(subtitle)
            else:
                # 3行目がない場合はそのまま
                fixed_subtitles.append(subtitle)
        
        # 最後に繰り越しが残っている場合（通常はありえない）
        if carry_over_text:
            self.logger.warning(f"Carry-over text remains: {carry_over_text}")
            # 最後の字幕に追加
            if fixed_subtitles:
                last_subtitle = fixed_subtitles[-1]
                fixed_subtitles[-1] = SubtitleEntry(
                    index=last_subtitle.index,
                    start_time=last_subtitle.start_time,
                    end_time=last_subtitle.end_time,
                    text_line1=last_subtitle.text_line1 + carry_over_text,
                    text_line2=last_subtitle.text_line2
                )
        
        return fixed_subtitles

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
    
    phase = Phase06SubtitlesV2(
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