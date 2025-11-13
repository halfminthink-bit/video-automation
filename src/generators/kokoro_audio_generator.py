"""
Kokoro TTS音声生成器

Kokoro TTS FastAPIを使用してテキストから音声を生成。
完全無料で、単語レベルのタイムスタンプを直接取得できる。
"""

import requests
import base64
import json
import os
import logging
import tempfile
import re
import io
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.utils.whisper_timing import WhisperTimingExtractor, WHISPER_AVAILABLE
from src.utils.elevenlabs_forced_alignment import (
    create_elevenlabs_aligner,
    ELEVENLABS_FA_AVAILABLE
)



class KokoroAudioGenerator:
    """
    Kokoro TTS FastAPIを使用した音声生成クラス

    完全無料のTTSシステムで、単語レベルのタイムスタンプを直接取得できる。
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        voice: str = "jf_alpha",
        speed: float = 1.0,
        response_format: str = "mp3",
        logger: Optional[logging.Logger] = None,
        whisper_config: Optional[Dict[str, Any]] = None,
        punctuation_pause_config: Optional[Dict[str, Any]] = None,
        use_elevenlabs_fa: bool = True,
        elevenlabs_api_key: Optional[str] = None
    ):
        """
        初期化

        Args:
            api_url: Kokoro FastAPI のベースURL（環境変数 KOKORO_API_URL を優先）
            voice: 使用する音声名（af_bella, af_sarah, af_sky等）
            speed: 速度（0.5-2.0）
            response_format: 出力形式（mp3, wav, opus, flac）
            logger: ロガー
            whisper_config: Whisper設定 {"enabled": bool, "model": str, "language": str}
            punctuation_pause_config: 句点での間隔制御設定
            use_elevenlabs_fa: ElevenLabs Forced Alignmentを使用するか（デフォルト: True）
            elevenlabs_api_key: ElevenLabs API Key（環境変数 ELEVENLABS_API_KEY を優先）

        Raises:
            ConnectionError: APIサーバーに接続できない場合
        """
        # 環境変数からURLを取得（オーバーライド優先）
        self.api_url = os.getenv("KOKORO_API_URL", api_url or "http://localhost:8880")
        self.voice = voice
        self.speed = speed
        self.response_format = response_format
        self.logger = logger or logging.getLogger(__name__)

        # Whisper設定（初期化はしない）
        self.whisper_config = whisper_config or {"enabled": True, "model": "base", "language": "ja"}

        # 句点での間隔制御設定
        self.punctuation_pause_config = punctuation_pause_config or {"enabled": False}

        # 🔥 新規追加: ElevenLabs Forced Alignment設定
        self.use_elevenlabs_fa = use_elevenlabs_fa
        # 環境変数からAPI Keyを取得（引数を優先）
        self.elevenlabs_api_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
        self.elevenlabs_aligner = None

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

        # 🔥 変更：__init__での初期化は不要（各セクションで都度初期化）
        # Whisperが利用可能かだけチェック（フォールバック用）
        if self.whisper_config.get("enabled", True) and WHISPER_AVAILABLE:
            self.logger.info("Whisper is available (will initialize per section as fallback)")
        else:
            self.logger.warning("Whisper not available. Timestamps will not be available if ElevenLabs FA fails.")

        # APIが利用可能かチェック
        self._verify_api_connection()

    def _verify_api_connection(self):
        """APIサーバーが起動しているか確認"""
        try:
            response = requests.get(f"{self.api_url}/v1/audio/voices", timeout=5)
            response.raise_for_status()
            voices = response.json()["voices"]
            self.logger.info(f"Kokoro API接続成功。利用可能な音声: {len(voices)}個")

            # 選択した音声が利用可能かチェック
            if self.voice not in voices:
                self.logger.warning(
                    f"指定された音声 '{self.voice}' は利用可能リストにありません。"
                    f"利用可能な音声: {voices[:10]}..."
                )
        except requests.exceptions.ConnectionError:
            error_msg = (
                f"Kokoro FastAPI サーバーに接続できません: {self.api_url}\n"
                f"以下のコマンドで起動してください:\n"
                f"  docker-compose -f docker-compose-kokoro.yml up -d"
            )
            self.logger.error(error_msg)
            raise ConnectionError(error_msg)
        except Exception as e:
            self.logger.error(f"Kokoro API接続失敗: {e}")
            raise ConnectionError(f"Kokoro API接続失敗: {e}")

    def _split_by_punctuation(self, text: str) -> List[str]:
        """
        句点で文を分割

        Args:
            text: 分割対象のテキスト

        Returns:
            句点で分割された文のリスト
        """
        # 「。」「！」「？」で分割し、区切り文字を保持
        segments = re.split(r'([。！？])', text)

        # 区切り文字を前の文に結合
        result = []
        for i in range(0, len(segments) - 1, 2):
            if segments[i]:
                result.append(segments[i] + segments[i + 1])

        # 最後の文（区切り文字がない場合）
        if len(segments) % 2 == 1 and segments[-1]:
            result.append(segments[-1])

        return result

    def _generate_single_audio(self, text: str) -> str:
        """
        単一のテキストに対して音声を生成（Base64を返す）

        Args:
            text: 生成するテキスト

        Returns:
            Base64エンコードされた音声データ
        """
        url = f"{self.api_url}/v1/audio/speech"

        payload = {
            "model": "kokoro",
            "input": text,
            "voice": self.voice,
            "speed": self.speed,
            "response_format": self.response_format
        }

        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            # レスポンスタイプを確認
            content_type = response.headers.get('content-type', '')

            # 音声データを取得
            if 'application/json' in content_type:
                # JSONレスポンスの場合（Base64エンコード済み）
                result = response.json()
                audio_base64 = result.get("audio", "")
                if not audio_base64:
                    raise ValueError("API returned empty audio field")
            else:
                # バイナリレスポンスの場合（OpenAI互換API）
                audio_bytes = response.content
                if not audio_bytes:
                    raise ValueError("API returned empty audio data")
                # Base64エンコード
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

            return audio_base64

        except Exception as e:
            self.logger.error(f"Error generating audio: {e}", exc_info=True)
            raise

    def _create_silence_file(self, duration: float, output_path: Path):
        """
        ffmpegを使用して無音ファイルを生成

        Args:
            duration: 無音の長さ（秒）
            output_path: 出力ファイルパス
        """
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=mono',
            '-t', str(duration),
            '-acodec', 'libmp3lame',
            '-b:a', '128k',
            '-y',
            str(output_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            self.logger.debug(f"Created silence file: {output_path} ({duration}s)")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create silence: {e.stderr}")
            raise

    def _combine_audio_files_with_ffmpeg(self, file_list: List[Path], output_path: Path):
        """
        ffmpegを使用して複数の音声ファイルを結合

        Args:
            file_list: 結合する音声ファイルのリスト
            output_path: 出力ファイルパス
        """
        # concat用のファイルリストを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for file_path in file_list:
                # ffmpegのconcatはファイルパスをエスケープする必要がある
                escaped_path = str(file_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
            concat_list_path = f.name

        try:
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list_path,
                '-c', 'copy',
                '-y',
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            self.logger.debug(f"Combined {len(file_list)} files to {output_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to combine audio files: {e.stderr}")
            raise
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(concat_list_path)
            except Exception:
                pass

    def _generate_with_punctuation_pause(self, text: str) -> Dict[str, Any]:
        """
        句点での間隔制御を使用して音声を生成

        Args:
            text: 生成するテキスト

        Returns:
            {
                'audio_base64': str,
                'alignment': {...}
            }
        """
        # 設定を取得
        pause_duration = self.punctuation_pause_config.get("pause_duration", {})
        skip_section_end = self.punctuation_pause_config.get("skip_section_end", True)

        period_pause = pause_duration.get("period", 0.8)
        exclamation_pause = pause_duration.get("exclamation", 0.9)
        question_pause = pause_duration.get("question", 0.9)

        self.logger.info(
            f"Punctuation pause enabled: period={period_pause}s, "
            f"exclamation={exclamation_pause}s, question={question_pause}s"
        )

        # 句点で分割
        segments = self._split_by_punctuation(text)

        if not segments:
            # 分割できなかった場合は、通常の処理
            self.logger.warning("No punctuation found, using normal generation")
            segments = [text]

        self.logger.info(f"Splitting text by punctuation: {len(segments)} segments")

        # 一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp(prefix='kokoro_punct_')
        temp_files = []

        try:
            # 各セグメントを生成
            for i, segment in enumerate(segments):
                if not segment.strip():
                    continue

                self.logger.info(f"Segment {i + 1}/{len(segments)}: {segment[:50]}...")

                # 音声生成
                audio_base64 = self._generate_single_audio(segment)
                audio_bytes = base64.b64decode(audio_base64)

                # 一時ファイルに保存
                segment_file = Path(temp_dir) / f"segment_{i:03d}.{self.response_format}"
                with open(segment_file, 'wb') as f:
                    f.write(audio_bytes)
                temp_files.append(segment_file)

                # 無音を挿入（最後のセグメント以外、またはskip_section_end=falseの場合）
                is_last = (i == len(segments) - 1)
                should_add_pause = not (is_last and skip_section_end)

                if should_add_pause:
                    # 句読点に応じた無音時間を決定
                    if segment.endswith('。'):
                        silence_duration = period_pause
                    elif segment.endswith('！'):
                        silence_duration = exclamation_pause
                    elif segment.endswith('？'):
                        silence_duration = question_pause
                    else:
                        silence_duration = 0.0

                    if silence_duration > 0:
                        silence_file = Path(temp_dir) / f"silence_{i:03d}.{self.response_format}"
                        self._create_silence_file(silence_duration, silence_file)
                        temp_files.append(silence_file)
                        self.logger.info(f"  + silence {silence_duration}s")

            # 全てのファイルを結合
            if not temp_files:
                raise ValueError("No audio segments generated")

            combined_file = Path(temp_dir) / f"combined.{self.response_format}"
            self._combine_audio_files_with_ffmpeg(temp_files, combined_file)

            self.logger.info(f"Combined {len(temp_files)} files")

            # 結合したファイルをBase64に変換
            with open(combined_file, 'rb') as f:
                combined_audio_base64 = base64.b64encode(f.read()).decode('utf-8')

            # Whisperでタイムスタンプ取得
            alignment = self._extract_timestamps_with_whisper(combined_audio_base64, text)

            return {
                'audio_base64': combined_audio_base64,
                'alignment': alignment
            }

        finally:
            # 一時ファイルをクリーンアップ
            try:
                import shutil
                shutil.rmtree(temp_dir)
                self.logger.debug(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")

    def generate_with_timestamps(
        self,
        text: str,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Kokoro TTS + Whisperを使用してタイムスタンプ付き音声を生成

        処理フロー:
        1. Kokoro APIで音声生成（タイムスタンプなし）
        2. 生成した音声をWhisperで解析してタイムスタンプ取得

        Args:
            text: 生成するテキスト
            previous_text: 前のテキスト（未使用）
            next_text: 次のテキスト（未使用）

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

        # 句点での間隔制御が有効な場合は専用の処理を使用
        if self.punctuation_pause_config.get("enabled", False):
            return self._generate_with_punctuation_pause(text)

        # 従来の処理（句点制御なし）
        # Step 1: Kokoro APIで音声のみ生成
        audio_base64 = self._generate_single_audio(text)

        self.logger.info(f"Audio generated successfully from Kokoro API ({len(audio_base64)} bytes base64)")

        # Step 2: Whisperでタイムスタンプ取得
        alignment = self._extract_timestamps_with_whisper(audio_base64, text)

        return {
            'audio_base64': audio_base64,
            'alignment': alignment
        }

    def _estimate_char_timings_from_duration(
        self,
        text: str,
        duration: float
    ) -> Dict[str, List]:
        """
        Whisper失敗時のフォールバック: 文字数比率でタイミングを推定

        Args:
            text: 元のテキスト
            duration: 音声の長さ（秒）

        Returns:
            文字レベルのタイムスタンプ
        """
        characters = list(text)
        char_count = len(characters)

        if char_count == 0:
            return {
                'characters': [],
                'character_start_times_seconds': [],
                'character_end_times_seconds': []
            }

        # 各文字の時間を均等分割
        char_duration = duration / char_count

        start_times = []
        end_times = []

        for i in range(char_count):
            start_times.append(i * char_duration)
            end_times.append((i + 1) * char_duration)

        return {
            'characters': characters,
            'character_start_times_seconds': start_times,
            'character_end_times_seconds': end_times
        }

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

    def _extract_timestamps_with_whisper(
        self,
        audio_base64: str,
        text: str
    ) -> Dict[str, List]:
        """
        音声からタイムスタンプを取得

        🔥 変更点: ElevenLabs Forced Alignmentを優先し、失敗時はWhisperにフォールバック

        Args:
            audio_base64: Base64エンコードされた音声データ
            text: 元のテキスト（正確なテキスト）

        Returns:
            alignment形式のタイムスタンプ情報
        """
        # 🔥 新規追加: ElevenLabs Forced Alignmentを試す
        if self.use_elevenlabs_fa and self.elevenlabs_aligner:
            try:
                self.logger.info("Extracting timing with ElevenLabs Forced Alignment...")

                # 音声をデコード
                audio_bytes = base64.b64decode(audio_base64)

                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(suffix=f".{self.response_format}", delete=False) as tmp:
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

        # 🔥 Whisperフォールバック
        # Whisperが利用不可の場合は空のalignmentを返す
        if not (self.whisper_config.get("enabled", True) and WHISPER_AVAILABLE):
            self.logger.warning("Whisper not available, returning empty alignment")
            return {
                'characters': [],
                'character_start_times_seconds': [],
                'character_end_times_seconds': []
            }

        # 🔥 追加：毎回Whisperを初期化（前のセグメントの影響を完全排除）
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
            with tempfile.NamedTemporaryFile(suffix=f".{self.response_format}", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()  # バッファをフラッシュ
                os.fsync(tmp.fileno())  # ディスクに強制書き込み
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

            # 🔥 変更：whisper_extractorを使用（self.whisper_extractorではない）
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

            # フォールバック: 音声の長さから推定
            try:
                # ffprobeで音声の長さを取得
                cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    str(tmp_file)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                duration = float(result.stdout.strip())

                self.logger.warning(
                    f"Using fallback: estimating timing from duration ({duration:.2f}s) "
                    f"and character count ({len(text)})"
                )

                return self._estimate_char_timings_from_duration(text, duration)
            except Exception as fallback_error:
                self.logger.error(f"Fallback also failed: {fallback_error}")
                # 空のalignmentを返す（音声は生成済み）
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

    def generate_sections(
        self,
        sections: List[Dict[str, Any]],
        output_dir: Path,
        speed: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        複数セクションの音声を生成

        Args:
            sections: セクションリスト [{"section_id": int, "narration": str}]
            output_dir: 出力ディレクトリ
            speed: 速度（0.5-2.0）

        Returns:
            [
                {
                    "section_id": int,
                    "audio_path": str,
                    "duration": float,
                    "timestamps": List[Dict],
                }
            ]
        """
        results = []

        for section in sections:
            section_id = section["section_id"]
            narration = section["narration"]

            # 出力パス
            output_path = output_dir / f"section_{section_id:02d}.mp3"

            # 音声生成
            self.logger.info(
                f"セクション {section_id} を生成中: {narration[:50]}..."
            )

            result = self.generate_with_timestamps(text=narration)

            # 音声ファイルを保存
            audio_bytes = base64.b64decode(result["audio_base64"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            self.logger.info(f"音声ファイルを保存: {output_path}")

            # 音声の長さを取得
            alignment = result["alignment"]
            char_end_times = alignment.get("character_end_times_seconds", [])
            duration = char_end_times[-1] if char_end_times else 0.0

            results.append({
                "section_id": section_id,
                "audio_path": str(output_path),
                "duration": duration,
                "alignment": alignment,
            })

        self.logger.info(f"{len(results)} セクションの音声生成が完了しました")
        return results


# ========================================
# テスト用関数
# ========================================

def test_kokoro_generator():
    """Kokoro音声生成器の動作テスト"""
    import tempfile

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        generator = KokoroAudioGenerator(
            voice="af_bella",
            logger=logger
        )

        test_text = "こんにちは、これはKokoro TTSのテストです。"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.mp3"

            result = generator.generate_with_timestamps(text=test_text)

            # 音声ファイルを保存
            audio_bytes = base64.b64decode(result["audio_base64"])
            with open(output_path, "wb") as f:
                f.write(audio_bytes)

            print("\n" + "="*60)
            print("✓ テスト成功")
            print("="*60)
            print(f"ファイル: {output_path}")
            end_times = result['alignment']['character_end_times_seconds']
            print(f"音声長: {end_times[-1] if end_times else 0:.2f}秒")
            print(f"単語数: {len(result['alignment']['characters'])}")
            print(f"サイズ: {output_path.stat().st_size / 1024:.1f}KB")

    except Exception as e:
        print(f"\n✗ テスト失敗: {e}")
        raise


if __name__ == "__main__":
    test_kokoro_generator()
