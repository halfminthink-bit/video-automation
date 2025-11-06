# phase 2
"""
Phase 2: 音声生成

Phase 1で生成された台本からElevenLabs APIを使用してナレーション音声を生成。
タイムスタンプ機能を使用して、文字レベルのタイミング情報も同時に取得。
"""

import json
import sys
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

# プロジェクトルートをパスに追加
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.core.phase_base import PhaseBase
from src.core.models import AudioGeneration, AudioSegment, VideoScript, ScriptSection
from src.core.config_manager import ConfigManager
from src.core.exceptions import (
    PhaseExecutionError,
    PhaseValidationError,
    PhaseInputMissingError
)
from src.generators.audio_generator import create_audio_generator
from src.processors.audio_processor import AudioProcessor
from src.processors.text_optimizer import TextOptimizer


class Phase02Audio(PhaseBase):
    """Phase 2: 音声生成フェーズ"""
    
    def get_phase_number(self) -> int:
        return 2
    
    def get_phase_name(self) -> str:
        return "Audio Generation"
    
    def check_inputs_exist(self) -> bool:
        """Phase 1の台本が存在するかチェック"""
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        exists = script_path.exists()
        
        if not exists:
            self.logger.warning(f"Script not found: {script_path}")
        
        return exists
    
    def check_outputs_exist(self) -> bool:
        """narration_full.mp3が存在するかチェック"""
        audio_path = self.phase_dir / "narration_full.mp3"
        analysis_path = self.phase_dir / "audio_analysis.json"
        
        exists = audio_path.exists() and analysis_path.exists()
        
        if exists:
            self.logger.info(f"Output already exists: {audio_path}")
        
        return exists
    
    def get_output_paths(self) -> List[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / "narration_full.mp3",
            self.phase_dir / "audio_analysis.json",
            self.phase_dir / "metadata.json"
        ]
    
    def execute_phase(self) -> AudioGeneration:
        """
        音声生成の実行（タイムスタンプ付き）

        Returns:
            AudioGeneration: 生成結果

        Raises:
            PhaseExecutionError: 実行エラー
        """
        self.logger.info(f"Generating audio with timestamps for: {self.subject}")

        try:
            # 1. Phase 1の台本を読み込み
            script = self._load_script()
            self.logger.info(
                f"Loaded script: {len(script.sections)} sections, "
                f"estimated {script.total_estimated_duration:.0f}s"
            )

            # 2. 音声生成器を作成
            generator = self._create_audio_generator()

            # 3. with_timestamps が有効かチェック
            use_timestamps = self.phase_config.get("with_timestamps", True)

            if use_timestamps and hasattr(generator, 'generate_with_timestamps'):
                # タイムスタンプ付きで生成
                self.logger.info("Generating audio with timestamps for each section...")
                segments, timing_data = self._generate_all_sections_with_timestamps(
                    script, generator
                )

                # タイミング情報を保存
                self._save_audio_timing(timing_data)
            else:
                # 通常の生成（タイムスタンプなし）
                self.logger.warning(
                    "Timestamps not supported by generator, using standard generation"
                )
                segments = self._generate_all_sections(script, generator)

            # 4. 音声を結合
            self.logger.info("Combining audio segments...")
            full_audio_path = self._combine_audio_segments(segments)

            # 5. 音声解析
            self.logger.info("Analyzing generated audio...")
            analysis = self._analyze_audio(full_audio_path)

            # 6. 結果をモデルに変換
            audio_gen = AudioGeneration(
                subject=self.subject,
                full_audio_path=str(full_audio_path),
                segments=segments,
                total_duration=analysis["duration"]
            )

            # 7. メタデータ保存
            self._save_generation_metadata(audio_gen, analysis)

            self.logger.info(
                f"Audio generation complete: "
                f"{audio_gen.total_duration:.1f}s, "
                f"{len(audio_gen.segments)} segments"
            )

            return audio_gen

        except Exception as e:
            self.logger.error(f"Audio generation failed: {e}", exc_info=True)
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Audio generation failed: {e}"
            ) from e
    
    def validate_output(self, output: AudioGeneration) -> bool:
        """
        生成された音声をバリデーション
        
        Args:
            output: AudioGeneration モデル
            
        Returns:
            バリデーション成功なら True
            
        Raises:
            PhaseValidationError: バリデーション失敗時
        """
        self.logger.info("Validating audio output...")
        
        # ファイルが存在するか
        full_audio_path = Path(output.full_audio_path)
        if not full_audio_path.exists():
            raise PhaseValidationError(
                self.get_phase_number(),
                f"Audio file not found: {output.full_audio_path}"
            )
        
        # 長さが妥当か（5分〜25分）
        min_duration = 300  # 5分
        max_duration = 1500  # 25分
        
        if not (min_duration <= output.total_duration <= max_duration):
            self.logger.warning(
                f"Audio duration {output.total_duration:.1f}s is outside "
                f"expected range ({min_duration}-{max_duration}s)"
            )
            # 警告のみ、エラーにはしない
        
        # 全セグメントが存在するか
        for segment in output.segments:
            segment_path = Path(segment.audio_path)
            if not segment_path.exists():
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Segment file not found: {segment.audio_path}"
                )
        
        # セグメント数が妥当か
        if len(output.segments) == 0:
            raise PhaseValidationError(
                self.get_phase_number(),
                "No audio segments generated"
            )
        
        self.logger.info("Audio validation passed ✓")
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
        sections = [
            ScriptSection(**section_data)
            for section_data in script_data.get("sections", [])
        ]
        
        script = VideoScript(
            subject=script_data["subject"],
            title=script_data["title"],
            description=script_data["description"],
            sections=sections,
            total_estimated_duration=script_data["total_estimated_duration"],
            model_version=script_data.get("model_version", "unknown")
        )
        
        return script
    
    def _create_audio_generator(self):
        """
        音声生成器を作成
        
        Returns:
            AudioGenerator または DummyAudioGenerator
        """
        # APIキーを取得
        try:
            api_key = self.config.get_api_key("ELEVENLABS_API_KEY")
            self.logger.info("ElevenLabs API key found")
        except Exception as e:
            self.logger.warning(f"Failed to get ElevenLabs API key: {e}")
            self.logger.warning("Using dummy generator")
            api_key = None
        
        # 生成器を作成
        generator = create_audio_generator(
            api_key=api_key,
            config=self.phase_config,
            use_dummy=not api_key,
            logger=self.logger
        )
        
        return generator
    
    def _generate_all_sections(
        self,
        script: VideoScript,
        generator
    ) -> List[AudioSegment]:
        """
        全セクションの音声を生成
        
        Args:
            script: 台本
            generator: 音声生成器
            
        Returns:
            AudioSegmentのリスト
        """
        segments = []
        sections_dir = self.phase_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        
        total_sections = len(script.sections)
        
        for i, section in enumerate(script.sections, start=1):
            self.logger.info(
                f"Generating audio for section {i}/{total_sections}: "
                f"{section.title}"
            )
            
            # 音声ファイルパス
            audio_path = sections_dir / f"section_{section.section_id:02d}.mp3"
            
            # 音声生成
            try:
                duration = generator.generate_to_file(
                    text=section.narration,
                    output_path=audio_path,
                    max_retries=self.phase_config.get("retry", {}).get("max_attempts", 5)
                )
                
                # セグメント情報を記録
                segment = AudioSegment(
                    section_id=section.section_id,
                    audio_path=str(audio_path),
                    duration=duration
                )
                segments.append(segment)
                
                self.logger.info(
                    f"✓ Section {i}/{total_sections} generated "
                    f"({duration:.1f}s)"
                )
                
            except Exception as e:
                self.logger.error(
                    f"Failed to generate audio for section {section.section_id}: {e}"
                )
                raise
        
        return segments

    def _generate_all_sections_with_timestamps(
        self,
        script: VideoScript,
        generator
    ) -> tuple[List[AudioSegment], List[Dict[str, Any]]]:
        """
        全セクションの音声をタイムスタンプ付きで生成

        各セクションのテキストを最適化し、前後のセクションを
        文脈として渡すことで自然なイントネーションを実現。

        Args:
            script: 台本
            generator: 音声生成器（generate_with_timestampsメソッド対応）

        Returns:
            (AudioSegmentのリスト, タイミング情報のリスト)
        """
        # テキスト最適化が有効かチェック
        text_opt_config = self.phase_config.get("text_optimization", {})
        use_optimization = text_opt_config.get("enabled", False)

        # テキストオプティマイザーの初期化
        optimizer = None
        if use_optimization:
            try:
                api_key = self.config.get_api_key("CLAUDE_API_KEY")
                optimizer = TextOptimizer(
                    api_key=api_key,
                    model=text_opt_config.get("model", "claude-sonnet-4-20250514"),
                    logger=self.logger
                )
                self.logger.info("TextOptimizer initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize TextOptimizer: {e}")
                self.logger.warning("Proceeding without text optimization")

        # 全体の文脈情報
        overall_context = None
        if use_optimization and text_opt_config.get("use_context", True):
            overall_context = f"""偉人: {script.subject}
時代背景: {script.description}
動画のテーマ: {script.title}
"""

        # 文脈制御の設定
        context_config = self.phase_config.get("context_awareness", {})
        use_previous = context_config.get("use_previous_text", True)
        use_next = context_config.get("use_next_text", True)

        segments = []
        timing_data = []
        sections_dir = self.phase_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)

        total_sections = len(script.sections)
        cumulative_offset = 0.0  # 累積時間オフセット
        silence_duration = self.phase_config.get("inter_section_silence", 0.5)

        for i, section in enumerate(script.sections, start=1):
            self.logger.info(
                f"Processing section {i}/{total_sections}: {section.section_id}"
            )

            # テキストの最適化
            text_to_generate = section.narration
            if optimizer:
                try:
                    optimized = optimizer.optimize_for_tts(
                        text=section.narration,
                        context=overall_context
                    )
                    self.logger.info(f"Original: {section.narration[:50]}...")
                    self.logger.info(f"Optimized: {optimized[:50]}...")
                    text_to_generate = optimized
                except Exception as e:
                    self.logger.warning(f"Text optimization failed: {e}")
                    self.logger.warning("Using original text")

            # 前後のテキストを取得（文脈用）
            previous_text = None
            next_text = None

            if use_previous and i > 1:
                previous_text = script.sections[i-2].narration

            if use_next and i < total_sections:
                next_text = script.sections[i].narration

            # 音声ファイルパス
            audio_path = sections_dir / f"section_{section.section_id:02d}.mp3"

            # タイムスタンプ付きで音声生成（文脈対応）
            try:
                result = generator.generate_with_timestamps(
                    text=text_to_generate,
                    previous_text=previous_text,
                    next_text=next_text
                )

                # Base64エンコードされた音声データをデコード
                audio_data = base64.b64decode(result['audio_base64'])

                # ファイルに保存
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                with open(audio_path, 'wb') as f:
                    f.write(audio_data)

                # タイミング情報を取得
                alignment = result.get('alignment', {})

                # 音声の長さを取得（タイムスタンプから計算）
                char_end_times = alignment.get('character_end_times_seconds', [])
                if char_end_times:
                    # 最後の文字の終了時間が音声の長さ
                    duration = char_end_times[-1]
                    self.logger.debug(f"Duration from timestamps: {duration:.2f}s")
                else:
                    # フォールバック: ffprobeを使用
                    try:
                        duration = generator._get_audio_duration(audio_path)
                        self.logger.debug(f"Duration from ffprobe: {duration:.2f}s")
                    except Exception as e:
                        # ffprobeも失敗した場合は推定値を使用
                        self.logger.warning(f"Could not get duration from ffprobe: {e}")
                        # 文字数から推定（1文字あたり約0.2秒と仮定）
                        duration = len(section.narration) * 0.2
                        self.logger.warning(f"Using estimated duration: {duration:.2f}s")
                timing_info = {
                    'section_id': section.section_id,
                    'text': section.narration,
                    'audio_path': str(audio_path),
                    'characters': alignment.get('characters', []),
                    'char_start_times': alignment.get('character_start_times_seconds', []),
                    'char_end_times': alignment.get('character_end_times_seconds', []),
                    'offset': cumulative_offset,
                    'duration': duration
                }
                timing_data.append(timing_info)

                # セグメント情報を記録
                segment = AudioSegment(
                    section_id=section.section_id,
                    audio_path=str(audio_path),
                    duration=duration
                )
                segments.append(segment)

                self.logger.info(
                    f"✓ Section {i}/{total_sections} generated with timestamps "
                    f"({duration:.1f}s, {len(alignment.get('characters', []))} chars)"
                )

                # 累積オフセットを更新
                cumulative_offset += duration + silence_duration

            except Exception as e:
                self.logger.error(
                    f"Failed to generate audio with timestamps for "
                    f"section {section.section_id}: {e}"
                )
                raise

        return segments, timing_data

    def _save_audio_timing(self, timing_data: List[Dict[str, Any]]):
        """
        音声タイミング情報をJSONファイルに保存

        Args:
            timing_data: タイミング情報のリスト
        """
        timing_path = self.phase_dir / "audio_timing.json"

        with open(timing_path, 'w', encoding='utf-8') as f:
            json.dump(timing_data, f, indent=2, ensure_ascii=False)

        self.logger.info(
            f"Audio timing data saved: {timing_path} "
            f"({len(timing_data)} sections)"
        )

    def _combine_audio_segments(self, segments: List[AudioSegment]) -> Path:
        """
        音声セグメントを結合

        Args:
            segments: AudioSegmentのリスト

        Returns:
            統合音声ファイルのPath
        """
        processor = AudioProcessor(logger=self.logger)

        # セグメントのパスリスト
        audio_paths = [Path(seg.audio_path) for seg in segments]

        # 出力パス
        output_path = self.phase_dir / "narration_full.mp3"

        # セクション間の無音時間
        silence_duration = self.phase_config.get("inter_section_silence", 0.5)

        self.logger.info(
            f"Combining {len(audio_paths)} segments "
            f"(silence between: {silence_duration}s)"
        )

        # 結合前に各セグメントの開始時間を計算して設定
        current_time = 0.0
        for segment in segments:
            segment.start_time = current_time
            current_time += segment.duration + silence_duration

        self.logger.debug("Calculated segment start times:")
        for seg in segments:
            self.logger.debug(
                f"  Section {seg.section_id}: "
                f"start={seg.start_time:.2f}s, duration={seg.duration:.2f}s"
            )

        # 結合
        total_duration = processor.combine_audio_files(
            audio_paths=audio_paths,
            output_path=output_path,
            silence_duration=silence_duration
        )

        self.logger.info(
            f"Combined audio created: {output_path} ({total_duration:.1f}s)"
        )

        return output_path
    
    def _analyze_audio(self, audio_path: Path) -> dict:
        """
        音声ファイルを解析
        
        Args:
            audio_path: 音声ファイルパス
            
        Returns:
            解析結果の辞書
        """
        processor = AudioProcessor(logger=self.logger)
        analysis = processor.analyze_audio(audio_path)
        
        # 解析結果を保存
        analysis_path = self.phase_dir / "audio_analysis.json"
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Audio analysis saved: {analysis_path}")
        
        return analysis
    
    def _save_generation_metadata(
        self,
        audio_gen: AudioGeneration,
        analysis: dict
    ):
        """
        生成メタデータを保存
        
        Args:
            audio_gen: AudioGeneration モデル
            analysis: 音声解析結果
        """
        metadata = {
            "subject": self.subject,
            "phase": self.get_phase_number(),
            "phase_name": self.get_phase_name(),
            "generated_at": audio_gen.generated_at.isoformat(),
            "total_sections": len(audio_gen.segments),
            "total_duration": audio_gen.total_duration,
            "total_duration_minutes": audio_gen.total_duration / 60,
            "file_size_mb": analysis.get("file_size_mb", 0),
            "sample_rate": analysis.get("sample_rate", 0),
            "channels": analysis.get("channels", 0),
            "nonsilent_ranges_count": analysis.get("nonsilent_count", 0),
            "config_used": {
                "service": self.phase_config.get("service"),
                "voice_id": self.phase_config.get("voice_id"),
                "model": self.phase_config.get("model"),
                "settings": self.phase_config.get("settings"),
                "inter_section_silence": self.phase_config.get("inter_section_silence")
            },
            "segments": [
                {
                    "section_id": seg.section_id,
                    "audio_path": seg.audio_path,
                    "duration": seg.duration
                }
                for seg in audio_gen.segments
            ]
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
        name="phase_02_test",
        log_dir=config.get_path("logs_dir"),
        level="INFO"
    )
    
    # テスト対象の偉人
    subject = "織田信長"
    
    logger.info(f"{'='*60}")
    logger.info(f"Phase 2: Audio Generation Test")
    logger.info(f"Subject: {subject}")
    logger.info(f"{'='*60}")
    
    # Phase 2を実行
    phase = Phase02Audio(
        subject=subject,
        config=config,
        logger=logger
    )
    
    # 実行（既存出力は上書き）
    execution = phase.run(skip_if_exists=False)
    
    # 結果表示
    print(f"\n{'='*60}")
    print(f"Phase 2 Execution Result")
    print(f"{'='*60}")
    print(f"Status: {execution.status.value}")
    
    if execution.duration_seconds:
        print(f"Duration: {execution.duration_seconds:.2f}s")
    
    if execution.status.value == "completed":
        print(f"\n✓ Phase 2 completed successfully!")
        print(f"\nOutput files:")
        for path in execution.output_paths:
            print(f"  - {path}")
        
        # 音声ファイルの情報を表示
        audio_path = Path(execution.output_paths[0])
        if audio_path.exists():
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            print(f"\nGenerated audio:")
            print(f"  Path: {audio_path}")
            print(f"  Size: {file_size_mb:.2f} MB")
            
    elif execution.status.value == "skipped":
        print(f"\n⊘ Phase 2 was skipped (outputs already exist)")
        
    else:
        print(f"\n✗ Phase 2 failed!")
        print(f"Error: {execution.error_message}")


if __name__ == "__main__":
    main()