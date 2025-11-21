# phase 2
"""
Phase 2: 音声生成

Phase 1で生成された台本からElevenLabs APIを使用してナレーション音声を生成。
タイムスタンプ機能を使用して、文字レベルのタイミング情報も同時に取得。
"""

import json
import sys
import base64
import os
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
from src.generators.kokoro_audio_generator import KokoroAudioGenerator
from src.processors.audio_processor import AudioProcessor
from src.processors.text_optimizer import TextOptimizer


class Phase02Audio(PhaseBase):
    """Phase 2: 音声生成フェーズ"""

    def __init__(self, subject: str, config: ConfigManager, logger: logging.Logger, audio_var: str = None):
        super().__init__(subject, config, logger)
        self.audio_var = audio_var

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

            # 2.5. ElevenLabs使用時はひらがな変換
            service = self.phase_config.get("service", "elevenlabs").lower()
            if service == "elevenlabs":
                self.logger.info("ElevenLabs detected - converting script to hiragana...")
                script = self._convert_script_to_hiragana(script)

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

    def _find_audio_variation(self, audio_config: Dict[str, Any], variation_id: str) -> Dict[str, Any]:
        """
        音声バリエーションIDから設定を検索

        Args:
            audio_config: audio.yamlから読み込んだ設定
            variation_id: バリエーションID

        Returns:
            バリエーション設定の辞書

        Raises:
            PhaseExecutionError: バリエーションが見つからない場合
        """
        variations = audio_config.get("audio_variations", [])
        for var in variations:
            if var["id"] == variation_id:
                return var

        raise PhaseExecutionError(
            self.get_phase_number(),
            f"Audio variation not found: {variation_id}"
        )

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

        設定の "service" フィールドに基づいて、適切な生成器を選択:
        - "kokoro": Kokoro TTS FastAPI（完全無料、タイムスタンプ対応）
        - "elevenlabs": ElevenLabs API（従来の方法）

        Returns:
            AudioGenerator, KokoroAudioGenerator, または DummyAudioGenerator
        """
        # バリエーション指定があれば上書き
        if self.audio_var:
            audio_config = self.config.get_variation_config("audio")
            var_settings = self._find_audio_variation(audio_config, self.audio_var)

            # 設定を上書き
            self.phase_config["service"] = var_settings["service"]
            if var_settings["service"] == "kokoro":
                if "kokoro" not in self.phase_config:
                    self.phase_config["kokoro"] = {}
                self.phase_config["kokoro"]["voice"] = var_settings.get("voice", "jf_alpha")
                self.phase_config["kokoro"]["speed"] = var_settings.get("speed", 1.0)
            elif var_settings["service"] == "azure":
                if "azure" not in self.phase_config:
                    self.phase_config["azure"] = {}
                self.phase_config["azure"]["voice_name"] = var_settings.get("voice_name", "ja-JP-NanamiNeural")
                self.phase_config["azure"]["speed"] = var_settings.get("speed", 1.0)
                self.phase_config["azure"]["pitch"] = var_settings.get("pitch", "+0%")
                self.phase_config["azure"]["style"] = var_settings.get("style")
            else:
                self.phase_config["voice_id"] = var_settings.get("voice_id")
                self.phase_config["model"] = var_settings.get("model", "eleven_turbo_v2_5")
                self.phase_config["stability"] = var_settings.get("stability", 0.7)
                self.phase_config["similarity_boost"] = var_settings.get("similarity_boost", 0.75)

        service = self.phase_config.get("service", "elevenlabs").lower()

        if service == "azure":
            # Azure AI Speech を使用
            self.logger.info("Using Azure AI Speech for audio generation")

            try:
                from src.generators.azure_audio_generator import AzureAudioGenerator

                azure_config = self.phase_config.get("azure", {})
                whisper_config = self.phase_config.get("whisper", {})
                punctuation_pause_config = self.phase_config.get("punctuation_pause", {})

                # APIキー取得（環境変数から）
                api_key = self.config.get_api_key("AZURE_SPEECH_KEY")

                # リージョン取得（環境変数または設定から）
                region = os.getenv("AZURE_SPEECH_REGION", azure_config.get("region", "japaneast"))

                # ElevenLabs FA設定
                use_elevenlabs_fa = self.phase_config.get("use_elevenlabs_fa", True)
                elevenlabs_api_key = self.phase_config.get("elevenlabs_api_key")

                generator = AzureAudioGenerator(
                    api_key=api_key,
                    region=region,
                    voice_name=azure_config.get("voice_name", "ja-JP-NanamiNeural"),
                    style=azure_config.get("style"),
                    speed=azure_config.get("speed", 1.0),
                    pitch=azure_config.get("pitch", "+0%"),
                    logger=self.logger,
                    whisper_config=whisper_config,
                    punctuation_pause_config=punctuation_pause_config,
                    use_elevenlabs_fa=use_elevenlabs_fa,
                    elevenlabs_api_key=elevenlabs_api_key
                )

                self.logger.info(
                    f"Azure Speech initialized: "
                    f"voice={azure_config.get('voice_name', 'ja-JP-NanamiNeural')}, "
                    f"region={region}, "
                    f"style={azure_config.get('style')}, "
                    f"whisper_enabled={whisper_config.get('enabled', True)}, "
                    f"elevenlabs_fa_enabled={use_elevenlabs_fa}"
                )
                return generator

            except Exception as e:
                self.logger.error(f"Failed to initialize Azure Speech: {e}")
                raise

        elif service == "kokoro":
            # Kokoro TTS を使用
            self.logger.info("Using Kokoro TTS for audio generation")

            try:
                kokoro_config = self.phase_config.get("kokoro", {})
                whisper_config = self.phase_config.get("whisper", {})
                punctuation_pause_config = self.phase_config.get("punctuation_pause", {})

                # 🔥 新規追加: ElevenLabs Forced Alignment設定
                use_elevenlabs_fa = self.phase_config.get("use_elevenlabs_fa", True)
                elevenlabs_api_key = self.phase_config.get("elevenlabs_api_key")  # nullの場合はNone

                generator = KokoroAudioGenerator(
                    api_url=kokoro_config.get("api_url"),
                    voice=kokoro_config.get("voice", "jf_alpha"),
                    speed=kokoro_config.get("speed", 1.0),
                    response_format=kokoro_config.get("response_format", "mp3"),
                    logger=self.logger,
                    whisper_config=whisper_config,
                    punctuation_pause_config=punctuation_pause_config,
                    use_elevenlabs_fa=use_elevenlabs_fa,
                    elevenlabs_api_key=elevenlabs_api_key
                )
                self.logger.info(
                    f"Kokoro TTS initialized: voice={kokoro_config.get('voice', 'jf_alpha')}, "
                    f"whisper_enabled={whisper_config.get('enabled', True)}, "
                    f"punctuation_pause_enabled={punctuation_pause_config.get('enabled', False)}, "
                    f"elevenlabs_fa_enabled={use_elevenlabs_fa}"
                )
                return generator
            except Exception as e:
                self.logger.error(f"Failed to initialize Kokoro TTS: {e}")
                raise

        else:
            # ElevenLabs を使用（従来の方法）
            self.logger.info("Using ElevenLabs API for audio generation")

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

        🆕 セクションタイトル機能:
        - 各セクションの冒頭でタイトルを0.8倍速で読み上げ
        - タイトル後に2秒の無音を挿入
        - タイミング情報に title_timing, silence_after_title を追加

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

        # 🆕 セクションタイトル設定を読み込み
        section_title_config = self.phase_config.get("section_title", {})
        section_title_enabled = section_title_config.get("enabled", True)
        title_speed = section_title_config.get("speed", 0.8)
        title_silence_after = section_title_config.get("silence_after", 2.0)

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
            display_text = section.narration  # デフォルトは元のテキスト

            if optimizer:
                try:
                    optimized = optimizer.optimize_for_tts(
                        text=section.narration,
                        context=overall_context
                    )
                    # 最適化結果が辞書の場合
                    if isinstance(optimized, dict):
                        text_to_generate = optimized.get("tts_text", section.narration)
                        display_text = optimized.get("display_text", section.narration)
                        self.logger.info(f"Original: {section.narration[:50]}...")
                        self.logger.info(f"TTS text: {text_to_generate[:50]}...")
                        self.logger.info(f"Display text: {display_text[:50]}...")
                    else:
                        # 後方互換性: 文字列が返された場合
                        text_to_generate = optimized
                        display_text = optimized
                        self.logger.info(f"Original: {section.narration[:50]}...")
                        self.logger.info(f"Optimized: {optimized[:50]}...")
                except Exception as e:
                    self.logger.warning(f"Text optimization failed: {e}")
                    self.logger.warning("Using original text")

            # 前後のテキストを取得（文脈用）
            previous_text = ""  # 空文字列で初期化
            next_text = ""      # 同様に空文字列で初期化

            if use_previous:
                if i > 1:
                    # Section 2以降: 前のセクションのナレーションを使用
                    previous_text = script.sections[i-2].narration
                    self.logger.debug(f"Section {i}: Using previous_text from section {i-1}")
                elif i == 1:
                    # Section 1: ダミーの文脈を追加して音声の一貫性を保つ
                    previous_text = f"これから{script.subject}についてお話しします。"
                    self.logger.info(f"Section 1: Using dummy context: {previous_text}")

            if use_next and i < total_sections:
                next_text = script.sections[i].narration
                self.logger.debug(f"Section {i}: Using next_text from section {i+1}")

            # デバッグログ: セクションごとのパラメータを確認
            self.logger.info(
                f"Section {i} generation params: "
                f"has_previous={previous_text is not None}, "
                f"has_next={next_text is not None}"
            )

            # 🆕 タイトル音声とナレーション音声を別々に生成
            title_audio_data = None
            title_duration = 0.0
            title_alignment = {}

            # 音声ファイルパス
            audio_path = sections_dir / f"section_{section.section_id:02d}.mp3"
            title_audio_path = sections_dir / f"section_{section.section_id:02d}_title.mp3"
            narration_audio_path = sections_dir / f"section_{section.section_id:02d}_narration.mp3"

            # タイムスタンプ付きで音声生成（文脈対応）
            try:
                # 🆕 1. タイトル音声を生成（0.8倍速）
                if section_title_enabled and section.title:
                    self.logger.info(f"Generating title audio: {section.title}")

                    # 元の速度を保存
                    original_speed = generator.speed

                    # 速度を変更
                    generator.speed = title_speed

                    try:
                        title_result = generator.generate_with_timestamps(
                            text=section.title,
                            previous_text=None,
                            next_text=None
                        )

                        # タイトル音声データをデコード
                        title_audio_data = base64.b64decode(title_result['audio_base64'])

                        # タイトル音声を一時ファイルに保存
                        title_audio_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(title_audio_path, 'wb') as f:
                            f.write(title_audio_data)

                        # タイトルのタイミング情報を取得
                        title_alignment = title_result.get('alignment', {})
                        title_char_end_times = title_alignment.get('character_end_times_seconds', [])

                        if title_char_end_times:
                            title_duration = title_char_end_times[-1]
                        else:
                            # フォールバック
                            title_duration = generator._get_audio_duration(title_audio_path)

                        self.logger.info(f"✓ Title audio generated ({title_duration:.2f}s)")

                    finally:
                        # 速度を元に戻す
                        generator.speed = original_speed

                # 🆕 2. 本文音声を生成（通常速度）
                result = generator.generate_with_timestamps(
                    text=text_to_generate,
                    previous_text=previous_text,
                    next_text=next_text
                )

                # Base64エンコードされた音声データをデコード
                narration_audio_data = base64.b64decode(result['audio_base64'])

                # ナレーション音声を一時ファイルに保存
                narration_audio_path.parent.mkdir(parents=True, exist_ok=True)
                with open(narration_audio_path, 'wb') as f:
                    f.write(narration_audio_data)

                # タイミング情報を取得
                narration_alignment = result.get('alignment', {})

                # 音声の長さを取得（タイムスタンプから計算）
                char_end_times = narration_alignment.get('character_end_times_seconds', [])
                if char_end_times:
                    # 最後の文字の終了時間が音声の長さ
                    narration_duration = char_end_times[-1]
                    self.logger.debug(f"Narration duration from timestamps: {narration_duration:.2f}s")
                else:
                    # フォールバック: ffprobeを使用
                    try:
                        narration_duration = generator._get_audio_duration(narration_audio_path)
                        self.logger.debug(f"Narration duration from ffprobe: {narration_duration:.2f}s")
                    except Exception as e:
                        # ffprobeも失敗した場合は推定値を使用
                        self.logger.warning(f"Could not get duration from ffprobe: {e}")
                        # 文字数から推定（1文字あたり約0.2秒と仮定）
                        narration_duration = len(section.narration) * 0.2
                        self.logger.warning(f"Using estimated narration duration: {narration_duration:.2f}s")

                # 🆕 3. 音声を結合（タイトル + 無音 + ナレーション）
                if section_title_enabled and title_audio_data:
                    # AudioProcessorを使用して結合（Python 3.13対応）
                    audio_processor = AudioProcessor(logger=self.logger)
                    
                    # タイトルとナレーションを結合（間に無音を挿入）
                    audio_files = [Path(title_audio_path), Path(narration_audio_path)]
                    total_duration = audio_processor.combine_audio_files(
                        audio_paths=audio_files,
                        output_path=Path(audio_path),
                        silence_duration=title_silence_after
                    )

                    self.logger.info(
                        f"✓ Combined audio: title({title_duration:.1f}s) + "
                        f"silence({title_silence_after:.1f}s) + "
                        f"narration({narration_duration:.1f}s) = {total_duration:.1f}s"
                    )
                else:
                    # タイトルなしの場合は、ナレーションのみ
                    import shutil
                    shutil.copy(narration_audio_path, audio_path)
                    total_duration = narration_duration

                # 🆕 4. タイミング情報を構築
                timing_info = {
                    'section_id': section.section_id,
                    'section_title': section.title,  # 🆕 タイトル追加
                    'text': section.narration,  # 元のテキスト（後方互換性のため）
                    'tts_text': text_to_generate,  # 音声用テキスト
                    'display_text': display_text,  # 字幕用テキスト
                    'audio_path': str(audio_path),
                    'offset': cumulative_offset,
                    'total_duration': total_duration
                }

                # 🆕 タイトルのタイミング情報を追加
                if section_title_enabled and title_audio_data:
                    timing_info['title_timing'] = {
                        'text': section.title,
                        'start_time': 0.0,  # セクション内の相対時間
                        'end_time': title_duration,
                        'speed': title_speed,
                        'special_type': 'section_title',
                        'characters': title_alignment.get('characters', []),
                        'char_start_times': title_alignment.get('character_start_times_seconds', []),
                        'char_end_times': title_alignment.get('character_end_times_seconds', [])
                    }

                    # 🆕 無音のタイミング情報を追加
                    timing_info['silence_after_title'] = {
                        'start_time': title_duration,
                        'end_time': title_duration + title_silence_after,
                        'duration': title_silence_after
                    }

                    # 🆕 ナレーションのタイミング情報（オフセット調整済み）
                    narration_start = title_duration + title_silence_after
                    timing_info['narration_timing'] = {
                        'text': section.narration,
                        'start_time': narration_start,
                        'end_time': narration_start + narration_duration,
                        'characters': narration_alignment.get('characters', []),
                        'char_start_times': narration_alignment.get('character_start_times_seconds', []),
                        'char_end_times': narration_alignment.get('character_end_times_seconds', [])
                    }
                else:
                    # タイトルなしの場合は、従来通り
                    timing_info['characters'] = narration_alignment.get('characters', [])
                    timing_info['char_start_times'] = narration_alignment.get('character_start_times_seconds', [])
                    timing_info['char_end_times'] = narration_alignment.get('character_end_times_seconds', [])
                    timing_info['duration'] = narration_duration

                timing_data.append(timing_info)

                # セグメント情報を記録
                segment = AudioSegment(
                    section_id=section.section_id,
                    audio_path=str(audio_path),
                    duration=total_duration
                )
                segments.append(segment)

                self.logger.info(
                    f"✓ Section {i}/{total_sections} generated with timestamps "
                    f"(total: {total_duration:.1f}s)"
                )

                # 累積オフセットを更新
                cumulative_offset += total_duration + silence_duration

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

    def _convert_script_to_hiragana(self, script: VideoScript) -> VideoScript:
        """
        台本全体をひらがなに変換（ElevenLabs用）

        Args:
            script: 元の台本

        Returns:
            ひらがな変換後の台本

        Raises:
            PhaseExecutionError: 変換失敗時
        """
        self.logger.info("Converting script to hiragana for ElevenLabs...")

        try:
            # Claude APIキーを取得
            claude_api_key = self.config.get_api_key("CLAUDE_API_KEY")

            # 台本全体のナレーションを結合
            all_narrations = []
            for section in script.sections:
                all_narrations.append(f"[Section {section.section_id}]\n{section.narration}")

            full_text = "\n\n".join(all_narrations)

            # Claude APIでひらがな変換
            hiragana_text = self._convert_to_hiragana_via_claude(
                full_text,
                claude_api_key
            )

            # セクションごとに分割して台本に戻す
            hiragana_sections = hiragana_text.split("[Section")

            for i, section in enumerate(script.sections):
                if i + 1 < len(hiragana_sections):
                    # セクション番号を除去してナレーションを取得
                    section_text = hiragana_sections[i + 1]
                    # "]" の後のテキストを取得（section_id部分をスキップ）
                    if "]" in section_text:
                        section_text = section_text.split("]", 1)[1].strip()
                        section.narration = section_text
                    else:
                        self.logger.warning(f"Failed to parse hiragana text for section {section.section_id}")

            self.logger.info("✓ Hiragana conversion completed")
            return script

        except Exception as e:
            self.logger.error(f"Hiragana conversion failed: {e}")
            self.logger.warning("Using original text without conversion")
            # エラー時は元のscriptを返す
            return script

    def _convert_to_hiragana_via_claude(
        self,
        text: str,
        api_key: str
    ) -> str:
        """
        Claude APIでひらがな変換

        Args:
            text: 元のテキスト
            api_key: Claude APIキー

        Returns:
            ひらがな変換後のテキスト

        Raises:
            Exception: API呼び出し失敗時
        """
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""以下の日本語テキストを、すべてひらがなに変換してください。

【変換ルール】
1. 漢字、カタカナをすべてひらがなに変換
2. 句読点（。、！？）はそのまま保持
3. 改行もそのまま保持
4. [Section N] のようなマーカーもそのまま保持
5. 数字は「いち」「に」「さん」などひらがなに変換
6. 英数字が含まれる場合は、読み方をひらがなに変換

【入力テキスト】
\"\"\"
{text}
\"\"\"

【出力】
変換後のひらがなテキストのみを出力してください。
説明や前置きは一切不要です。
マーカー [Section N] は必ず保持してください。
"""

        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                temperature=0,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            hiragana_text = message.content[0].text.strip()

            # 不要な装飾を除去
            hiragana_text = hiragana_text.replace('```', '').replace('"""', '').strip()

            self.logger.info("✓ Hiragana conversion completed")
            self.logger.debug(f"Original length: {len(text)} chars")
            self.logger.debug(f"Converted length: {len(hiragana_text)} chars")

            return hiragana_text

        except Exception as e:
            self.logger.error(f"Hiragana conversion API call failed: {e}")
            raise


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