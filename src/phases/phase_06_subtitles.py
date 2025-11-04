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
        字幕生成の実行（audio_timing.json からタイミング情報を使用）

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

            # 2. audio_timing.json を読み込み（存在する場合）
            audio_timing_path = self.config.get_phase_dir(self.subject, 2) / "audio_timing.json"

            if audio_timing_path.exists():
                # タイムスタンプ付き音声データを使用
                self.logger.info("Using audio timing data from ElevenLabs")
                subtitles = self._generate_from_audio_timing(audio_timing_path)
            else:
                # フォールバック：Whisperまたは文字数比率を使用
                self.logger.warning("Audio timing data not found, using fallback method")
                audio_segments = self._load_audio_segments()
                self.logger.info(f"Loaded audio segments: {len(audio_segments)}")

                # 字幕生成器を作成
                generator = create_subtitle_generator(
                    config=self.phase_config,
                    logger=self.logger
                )

                # 音声ファイルのパスを取得（Whisper使用のため）
                audio_path = self.config.get_phase_dir(self.subject, 2) / "narration_full.mp3"

                # 字幕を生成
                self.logger.info("Generating subtitles...")
                subtitles = generator.generate_subtitles(
                    script=script,
                    audio_segments=audio_segments,
                    config=self.phase_config,
                    audio_path=audio_path if audio_path.exists() else None
                )

            # 6. SRTファイルを保存
            srt_path = self._save_srt_file(subtitles)

            # 7. タイミングJSONを保存
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
    
    def _generate_from_audio_timing(self, timing_path: Path) -> List[SubtitleEntry]:
        """
        audio_timing.json から字幕を生成

        Args:
            timing_path: audio_timing.json のパス

        Returns:
            字幕エントリのリスト
        """
        self.logger.info(f"Loading audio timing data from: {timing_path}")

        with open(timing_path, 'r', encoding='utf-8') as f:
            timing_data = json.load(f)

        subtitles = []
        subtitle_index = 1

        # 設定を取得
        max_words_per_subtitle = self.phase_config.get("max_words_per_subtitle", 5)
        max_duration = self.phase_config.get("timing", {}).get("max_display_duration", 3.0)
        min_display_duration = self.phase_config.get("timing", {}).get("min_display_duration", 1.0)

        for section_data in timing_data:
            section_id = section_data.get('section_id', 0)
            characters = section_data.get('characters', [])
            char_start_times = section_data.get('char_start_times', [])
            char_end_times = section_data.get('char_end_times', [])
            offset = section_data.get('offset', 0.0)
            text = section_data.get('text', '')

            self.logger.debug(
                f"Processing section {section_id}: {len(characters)} characters"
            )

            # 文字レベル → 単語レベル に変換
            words = self._group_characters_into_words(
                text, characters, char_start_times, char_end_times, offset
            )

            # 単語 → 字幕グループ に変換
            subtitle_groups = self._create_subtitle_groups(
                words, max_words_per_subtitle, max_duration
            )

            # 字幕エントリを作成
            for group in subtitle_groups:
                # 表示時間が短すぎる場合は調整
                duration = group['end_time'] - group['start_time']
                if duration < min_display_duration:
                    group['end_time'] = group['start_time'] + min_display_duration

                subtitle = SubtitleEntry(
                    index=subtitle_index,
                    start_time=group['start_time'],
                    end_time=group['end_time'],
                    text_line1=group['text'],
                    text_line2=""  # 単一行で表示
                )
                subtitles.append(subtitle)
                subtitle_index += 1

        self.logger.info(f"Generated {len(subtitles)} subtitles from timing data")
        return subtitles

    def _group_characters_into_words(
        self,
        text: str,
        characters: List[str],
        start_times: List[float],
        end_times: List[float],
        offset: float
    ) -> List[Dict[str, Any]]:
        """
        文字レベルのタイミング情報を単語レベルに変換

        Args:
            text: 元のテキスト
            characters: 文字のリスト
            start_times: 各文字の開始時間
            end_times: 各文字の終了時間
            offset: 累積時間オフセット

        Returns:
            単語情報のリスト [{'text': str, 'start': float, 'end': float}, ...]
        """
        words = []
        current_word = ""
        word_start = None

        for i, char in enumerate(characters):
            if i >= len(start_times) or i >= len(end_times):
                break

            # オフセットを適用
            char_start = start_times[i] + offset
            char_end = end_times[i] + offset

            # 空白または句読点で単語を区切る
            if char in [' ', '　', '、', '。', '！', '？', '\n']:
                if current_word:
                    words.append({
                        'text': current_word,
                        'start': word_start,
                        'end': char_start
                    })
                    current_word = ""
                    word_start = None

                # 句読点も独立した"単語"として追加
                if char not in [' ', '　', '\n']:
                    words.append({
                        'text': char,
                        'start': char_start,
                        'end': char_end
                    })
            else:
                if word_start is None:
                    word_start = char_start
                current_word += char

        # 最後の単語を追加
        if current_word and word_start is not None:
            words.append({
                'text': current_word,
                'start': word_start,
                'end': end_times[-1] + offset if end_times else word_start
            })

        return words

    def _create_subtitle_groups(
        self,
        words: List[Dict[str, Any]],
        max_words: int = 5,
        max_duration: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        単語を字幕グループにまとめる

        Args:
            words: 単語情報のリスト
            max_words: 1つの字幕に含める最大単語数
            max_duration: 1つの字幕の最大表示時間（秒）

        Returns:
            字幕グループのリスト [{'text': str, 'start_time': float, 'end_time': float}, ...]
        """
        groups = []
        current_group = []
        group_start = None

        for word in words:
            if not current_group:
                # 新しいグループを開始
                current_group = [word]
                group_start = word['start']
            else:
                # グループに追加するか判定
                group_duration = word['end'] - group_start
                should_split = (
                    len(current_group) >= max_words or
                    group_duration >= max_duration or
                    word['text'] in ['。', '！', '？']  # 句点で区切る
                )

                if should_split:
                    # 現在のグループを完了
                    groups.append({
                        'text': ''.join([w['text'] for w in current_group]),
                        'start_time': group_start,
                        'end_time': current_group[-1]['end']
                    })
                    # 新しいグループを開始
                    current_group = [word]
                    group_start = word['start']
                else:
                    # グループに追加
                    current_group.append(word)

        # 最後のグループを追加
        if current_group:
            groups.append({
                'text': ''.join([w['text'] for w in current_group]),
                'start_time': group_start,
                'end_time': current_group[-1]['end']
            })

        return groups

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
