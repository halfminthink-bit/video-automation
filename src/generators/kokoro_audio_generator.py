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
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.utils.whisper_timing import WhisperTimingExtractor, WHISPER_AVAILABLE



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
        whisper_config: Optional[Dict[str, Any]] = None
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

        Raises:
            ConnectionError: APIサーバーに接続できない場合
        """
        # 環境変数からURLを取得（オーバーライド優先）
        self.api_url = os.getenv("KOKORO_API_URL", api_url or "http://localhost:8880")
        self.voice = voice
        self.speed = speed
        self.response_format = response_format
        self.logger = logger or logging.getLogger(__name__)

        # Whisper設定
        self.whisper_config = whisper_config or {"enabled": True, "model": "base", "language": "ja"}
        self.whisper_extractor = None

        # Whisperが有効かつ利用可能な場合、初期化
        if self.whisper_config.get("enabled", True) and WHISPER_AVAILABLE:
            try:
                self.whisper_extractor = WhisperTimingExtractor(
                    model_name=self.whisper_config.get("model", "base"),
                    logger=self.logger,
                    language=self.whisper_config.get("language", "ja")
                )
                self.logger.info("Whisper timing extractor initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Whisper: {e}. Timestamps will not be available.")
                self.whisper_extractor = None

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

        # Step 1: Kokoro APIで音声のみ生成
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
            self.logger.debug(f"Response content-type: {content_type}")

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

            self.logger.info(f"Audio generated successfully from Kokoro API ({len(audio_base64)} bytes base64)")

            # Step 2: Whisperでタイムスタンプ取得
            alignment = self._extract_timestamps_with_whisper(audio_base64, text)

            return {
                'audio_base64': audio_base64,
                'alignment': alignment
            }

        except Exception as e:
            self.logger.error(f"Error generating audio: {e}", exc_info=True)
            raise

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
        Whisperを使用して音声からタイムスタンプを取得

        Args:
            audio_base64: Base64エンコードされた音声データ
            text: 元のテキスト（精度向上のため）

        Returns:
            alignment形式のタイムスタンプ情報
        """
        # Whisperが利用不可の場合は空のalignmentを返す
        if not self.whisper_extractor:
            self.logger.warning("Whisper not available, returning empty alignment")
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

            # Whisperでタイミング取得
            word_timings = self.whisper_extractor.extract_word_timings(
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
                from pydub import AudioSegment
                audio_seg = AudioSegment.from_file(tmp_file)
                duration = len(audio_seg) / 1000.0  # ミリ秒を秒に変換

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
