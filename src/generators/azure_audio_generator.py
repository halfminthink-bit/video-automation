"""
Azure AI Speech音声生成器

Azure AI Speech APIを使用してテキストから音声を生成。
高品質で日本語の漢字読みが正確なニューラル音声を提供。
"""

import base64
import json
import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import html

try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

from src.utils.whisper_timing import WhisperTimingExtractor, WHISPER_AVAILABLE
from src.utils.elevenlabs_forced_alignment import (
    create_elevenlabs_aligner,
    ELEVENLABS_FA_AVAILABLE
)


class AzureAudioGenerator:
    """
    Azure AI Speechを使用した音声生成クラス

    高品質なニューラル音声で、日本語の漢字読みが正確。
    Kokoro TTSと同じインターフェースを提供。
    """

    def __init__(
        self,
        api_key: str,
        region: str = "japaneast",
        voice_name: str = "ja-JP-NanamiNeural",
        style: Optional[str] = None,
        speed: float = 1.0,
        pitch: str = "+0%",
        logger: Optional[logging.Logger] = None,
        whisper_config: Optional[Dict[str, Any]] = None,
        punctuation_pause_config: Optional[Dict[str, Any]] = None,
        use_elevenlabs_fa: bool = True,
        elevenlabs_api_key: Optional[str] = None
    ):
        """
        初期化

        Args:
            api_key: Azure Speech APIキー
            region: Azureリージョン（japaneast推奨）
            voice_name: 使用する音声名（ja-JP-NanamiNeural等）
            style: 感情スタイル（cheerful, sad, angry等、オプション）
            speed: 速度（0.5-2.0）
            pitch: ピッチ（-50%～+50%）
            logger: ロガー
            whisper_config: Whisper設定 {"enabled": bool, "model": str, "language": str}
            punctuation_pause_config: 句点での間隔制御設定（未実装）
            use_elevenlabs_fa: ElevenLabs Forced Alignmentを使用するか
            elevenlabs_api_key: ElevenLabs API Key

        Raises:
            ImportError: Azure SDKがインストールされていない場合
        """
        if not AZURE_AVAILABLE:
            raise ImportError(
                "Azure Cognitive Services Speech SDK is not installed. "
                "Install with: pip install azure-cognitiveservices-speech"
            )

        self.api_key = api_key
        self.region = region
        self.voice_name = voice_name
        self.style = style
        self.speed = speed
        self.pitch = pitch
        self.logger = logger or logging.getLogger(__name__)

        # Azure Speech設定
        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.api_key,
            region=self.region
        )
        self.speech_config.speech_synthesis_voice_name = self.voice_name
        # MP3 16kHz 32kbps形式を使用
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

        # タイムスタンプ抽出用（Kokoroと同じ仕組み）
        self.whisper_config = whisper_config or {"enabled": True, "model": "base", "language": "ja"}
        self.punctuation_pause_config = punctuation_pause_config or {"enabled": False}
        self.use_elevenlabs_fa = use_elevenlabs_fa
        self.elevenlabs_api_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
        self.elevenlabs_aligner = None

        # ElevenLabs Forced Alignment設定
        if self.use_elevenlabs_fa:
            if not self.elevenlabs_api_key:
                self.logger.warning(
                    "use_elevenlabs_fa is True but elevenlabs_api_key is not set. "
                    "Falling back to Whisper."
                )
                self.use_elevenlabs_fa = False
            elif not ELEVENLABS_FA_AVAILABLE:
                self.logger.warning(
                    "ElevenLabs Forced Alignment is not available (requests library missing). "
                    "Falling back to Whisper."
                )
                self.use_elevenlabs_fa = False
            else:
                self.elevenlabs_aligner = create_elevenlabs_aligner(
                    api_key=self.elevenlabs_api_key,
                    logger=self.logger
                )
                if self.elevenlabs_aligner:
                    self.logger.info("✓ ElevenLabs Forced Alignment enabled")
                else:
                    self.logger.warning("Failed to create ElevenLabs aligner. Falling back to Whisper.")
                    self.use_elevenlabs_fa = False

        # Whisperが利用可能かチェック（フォールバック用）
        if self.whisper_config.get("enabled", True) and WHISPER_AVAILABLE:
            self.logger.info("Whisper is available (will initialize per section as fallback)")
        else:
            self.logger.warning("Whisper not available. Timestamps will not be available if ElevenLabs FA fails.")

        self.logger.info(
            f"Azure Speech initialized: voice={voice_name}, region={region}, "
            f"style={style}, speed={speed}, pitch={pitch}"
        )

    def _build_ssml(self, text: str, style: Optional[str] = None) -> str:
        """
        SSML文字列を構築

        Args:
            text: 音声化するテキスト
            style: 感情スタイル（cheerful, sad等）

        Returns:
            SSML形式の文字列
        """
        # XML特殊文字をエスケープ
        escaped_text = html.escape(text)

        # 感情スタイル付きSSML
        if style:
            ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
       xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='ja-JP'>
    <voice name='{self.voice_name}'>
        <prosody rate='{self.speed}' pitch='{self.pitch}'>
            <mstts:express-as style='{style}'>
                {escaped_text}
            </mstts:express-as>
        </prosody>
    </voice>
</speak>"""
        else:
            # 通常のSSML（感情スタイルなし）
            ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='ja-JP'>
    <voice name='{self.voice_name}'>
        <prosody rate='{self.speed}' pitch='{self.pitch}'>
            {escaped_text}
        </prosody>
    </voice>
</speak>"""

        return ssml.strip()

    def _generate_single_audio(self, text: str, style: Optional[str] = None) -> bytes:
        """
        単一テキストの音声生成

        Args:
            text: 生成するテキスト
            style: 感情スタイル（オプション）

        Returns:
            音声データ（バイナリ）

        Raises:
            Exception: Azure Speech API呼び出し失敗時
        """
        # SSML構築
        ssml = self._build_ssml(text, style or self.style)

        # Azure Speech Synthesizer作成（メモリに出力）
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=None  # メモリに出力
        )

        # 音声生成
        result = synthesizer.speak_ssml_async(ssml).get()

        # エラーチェック
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            self.logger.debug(f"Audio generated: {len(result.audio_data)} bytes")
            return result.audio_data
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            self.logger.error(f"Speech synthesis canceled: {cancellation.reason}")
            if cancellation.reason == speechsdk.CancellationReason.Error:
                self.logger.error(f"Error details: {cancellation.error_details}")
            raise Exception(f"Azure Speech synthesis failed: {cancellation.reason}")
        else:
            raise Exception(f"Unexpected result reason: {result.reason}")

    def _extract_timestamps_with_whisper(
        self,
        audio_base64: str,
        text: str
    ) -> Dict[str, List]:
        """
        音声からタイムスタンプを取得

        ElevenLabs Forced Alignmentを優先し、失敗時はWhisperにフォールバック

        Args:
            audio_base64: Base64エンコードされた音声データ
            text: 元のテキスト（正確なテキスト）

        Returns:
            alignment形式のタイムスタンプ情報
        """
        # ElevenLabs Forced Alignmentを試す
        if self.use_elevenlabs_fa and self.elevenlabs_aligner:
            try:
                self.logger.info("Extracting timing with ElevenLabs Forced Alignment...")

                # 音声をデコード
                audio_bytes = base64.b64decode(audio_base64)

                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                    tmp_file_path = Path(tmp.name)

                try:
                    # ElevenLabs FAでアラインメント
                    alignment_result = self.elevenlabs_aligner.align(
                        audio_path=tmp_file_path,
                        text=text,
                        language="ja"
                    )

                    # 成功したら結果を返す
                    characters = alignment_result['characters']
                    char_start_times = alignment_result['char_start_times']
                    char_end_times = alignment_result['char_end_times']

                    self.logger.info(
                        f"✓ ElevenLabs FA successful: {len(characters)} characters, "
                        f"duration: {char_end_times[-1] if char_end_times else 0:.2f}s"
                    )

                    return {
                        'characters': characters,
                        'character_start_times_seconds': char_start_times,
                        'character_end_times_seconds': char_end_times
                    }

                finally:
                    # 一時ファイルを削除
                    if tmp_file_path.exists():
                        tmp_file_path.unlink()

            except Exception as e:
                self.logger.warning(
                    f"ElevenLabs Forced Alignment failed: {e}. "
                    "Falling back to Whisper..."
                )
                # フォールバックに進む

        # Whisperフォールバック
        if not (self.whisper_config.get("enabled", True) and WHISPER_AVAILABLE):
            self.logger.warning("Whisper not available, returning empty alignment")
            return {
                'characters': [],
                'character_start_times_seconds': [],
                'character_end_times_seconds': []
            }

        # Whisperを初期化（前のセグメントの影響を排除）
        try:
            self.logger.info("Initializing fresh Whisper model for this section...")
            whisper_extractor = WhisperTimingExtractor(
                model_name=self.whisper_config.get("model", "base"),
                logger=self.logger,
                language=self.whisper_config.get("language", "ja"),
                use_stable_ts=self.whisper_config.get("use_stable_ts", True),
                suppress_silence=self.whisper_config.get("suppress_silence", True),
                vad=self.whisper_config.get("vad", True),
                vad_threshold=self.whisper_config.get("vad_threshold", 0.35)
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize Whisper: {e}")
            return {
                'characters': [],
                'character_start_times_seconds': [],
                'character_end_times_seconds': []
            }

        # 音声をデコード
        audio_bytes = base64.b64decode(audio_base64)

        # 一時ファイルに保存
        tmp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_file = tmp.name

            # ファイルサイズ確認
            file_size = os.path.getsize(tmp_file)
            expected_size = len(audio_bytes)
            if file_size != expected_size:
                raise IOError(
                    f"Temporary file incomplete: {file_size} bytes written, "
                    f"expected {expected_size} bytes"
                )

            self.logger.info(
                f"Extracting timestamps with Whisper from {tmp_file} "
                f"({file_size} bytes)"
            )

            # Whisperで単語タイミング抽出
            word_timings = whisper_extractor.extract_word_timings(
                audio_path=Path(tmp_file),
                text=text
            )

            # 認識率の診断
            recognized_text = ''.join([w.get('word', '') for w in word_timings])
            expected_chars = len(text)
            recognized_chars = len(recognized_text)
            recognition_rate = recognized_chars / expected_chars if expected_chars > 0 else 0

            self.logger.info(
                f"Recognition rate: {recognition_rate:.1%} "
                f"({recognized_chars}/{expected_chars} chars)"
            )

            # 認識率が50%未満の場合は警告
            if recognition_rate < 0.5:
                self.logger.warning(
                    f"Low recognition rate detected! Whisper may have failed. "
                    f"Expected text: {text[:50]}..."
                )
                self.logger.warning(
                    f"Recognized text: {recognized_text[:50]}..."
                )

            # 単語レベルのタイムスタンプを文字レベルに展開
            expanded = self._expand_word_timings_to_chars(word_timings)
            characters = expanded['characters']
            start_times = expanded['character_start_times_seconds']
            end_times = expanded['character_end_times_seconds']

            self.logger.info(
                f"✓ Extracted {len(word_timings)} words with Whisper, "
                f"expanded to {len(characters)} characters, "
                f"duration: {end_times[-1] if end_times else 0:.2f}s"
            )

            return {
                'characters': characters,
                'character_start_times_seconds': start_times,
                'character_end_times_seconds': end_times
            }

        except Exception as e:
            self.logger.warning(f"Failed to extract timestamps with Whisper: {e}")
            # フォールバック: 空のalignmentを返す
            return {
                'characters': [],
                'character_start_times_seconds': [],
                'character_end_times_seconds': []
            }

        finally:
            # 一時ファイルを削除
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except Exception as e:
                    self.logger.warning(f"Failed to delete temporary file {tmp_file}: {e}")

    def _expand_word_timings_to_chars(
        self,
        word_timings: List[Dict[str, Any]]
    ) -> Dict[str, List]:
        """
        単語レベルのタイムスタンプを文字レベルに展開

        各単語内で文字を均等に配分してタイミングを推定

        Args:
            word_timings: Whisperから取得した単語タイミング

        Returns:
            {
                'characters': List[str],
                'character_start_times_seconds': List[float],
                'character_end_times_seconds': List[float]
            }
        """
        characters = []
        start_times = []
        end_times = []

        for timing in word_timings:
            word = timing.get("word", "").strip()
            word_start = float(timing.get("start", 0.0))
            word_end = float(timing.get("end", 0.0))

            if not word:
                continue

            # 単語の長さ（文字数）
            word_length = len(word)

            if word_length == 0:
                continue

            # 各文字の時間幅を計算（均等分割）
            word_duration = word_end - word_start
            char_duration = word_duration / word_length

            # 各文字のタイミングを計算
            for i, char in enumerate(word):
                char_start = word_start + (i * char_duration)
                char_end = char_start + char_duration

                characters.append(char)
                start_times.append(char_start)
                end_times.append(char_end)

        return {
            'characters': characters,
            'character_start_times_seconds': start_times,
            'character_end_times_seconds': end_times
        }

    def generate_with_timestamps(
        self,
        text: str,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Azure Speech + Whisperを使用してタイムスタンプ付き音声を生成

        処理フロー:
        1. Azure Speechで音声生成
        2. 生成した音声をWhisper（またはElevenLabs FA）で解析してタイムスタンプ取得

        Args:
            text: 生成するテキスト
            previous_text: 前のテキスト（未使用、Azureは文脈不要）
            next_text: 次のテキスト（未使用、Azureは文脈不要）

        Returns:
            {
                'audio_base64': str,
                'alignment': {
                    'characters': List[str],
                    'character_start_times_seconds': List[float],
                    'character_end_times_seconds': List[float]
                }
            }
        """
        self.logger.info(f"Generating audio with timestamps: {text[:50]}...")

        # Step 1: Azure Speechで音声のみ生成
        audio_bytes = self._generate_single_audio(text)

        # Base64エンコード
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        self.logger.info(f"Audio generated successfully from Azure Speech ({len(audio_base64)} bytes base64)")

        # Step 2: Whisperでタイムスタンプ取得
        alignment = self._extract_timestamps_with_whisper(audio_base64, text)

        return {
            'audio_base64': audio_base64,
            'alignment': alignment
        }
