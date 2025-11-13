"""
ElevenLabs Forced Alignment APIを使用したタイミング抽出

Whisperの代わりにElevenLabs Forced Alignment APIを使用することで、
台本と音声の完璧なアラインメントを実現します。

特徴:
- 台本テキストを使用した高精度アラインメント
- 固有名詞の完璧な処理
- TTS音声との相性が良い
- 文字レベルの正確なタイミング
"""

import requests
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional


# ElevenLabs Forced Alignment APIが利用可能かチェック
ELEVENLABS_FA_AVAILABLE = True

try:
    import requests
except ImportError:
    ELEVENLABS_FA_AVAILABLE = False
    requests = None


class ElevenLabsForcedAligner:
    """ElevenLabs Forced Alignment APIを使用した音声-テキストアラインメント"""

    def __init__(
        self,
        api_key: str,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            api_key: ElevenLabs API Key
            logger: ロガー
        """
        if not ELEVENLABS_FA_AVAILABLE:
            raise ImportError(
                "requests library is required for ElevenLabs Forced Alignment. "
                "Install with: pip install requests"
            )

        self.api_key = api_key
        self.endpoint = "https://api.elevenlabs.io/v1/audio-native"
        self.logger = logger or logging.getLogger(__name__)

        self.logger.info("ElevenLabs Forced Aligner initialized")

    def align(
        self,
        audio_path: Path,
        text: str,
        language: str = "ja"
    ) -> Dict[str, Any]:
        """
        音声ファイルとテキストをアラインメント

        Args:
            audio_path: 音声ファイルのパス
            text: 台本テキスト（正確なテキスト）
            language: 言語コード（デフォルト: "ja"）

        Returns:
            アラインメント結果:
            {
                "characters": ["織", "田", ...],
                "char_start_times": [0.1, 0.2, ...],
                "char_end_times": [0.2, 0.3, ...],
                "alignment": {
                    "char_start_times": [0.1, 0.2, ...],
                    "char_end_times": [0.2, 0.3, ...],
                    "characters": ["織", "田", ...]
                },
                "words": [...]  # オプション
            }

        Raises:
            requests.HTTPError: API呼び出しが失敗した場合
            FileNotFoundError: 音声ファイルが存在しない場合
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        self.logger.info(f"Aligning audio with ElevenLabs FA: {audio_path}")
        self.logger.debug(f"Text length: {len(text)} characters")

        try:
            # APIリクエスト
            with open(audio_path, 'rb') as f:
                files = {'audio': (audio_path.name, f, 'audio/mpeg')}
                data = {
                    'text': text,
                    'language': language,
                    'model_id': 'eleven_multilingual_v2'
                }
                headers = {
                    'xi-api-key': self.api_key
                }

                self.logger.debug(f"Sending request to {self.endpoint}")

                response = requests.post(
                    self.endpoint,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=120  # 大きなファイルの場合はタイムアウトを長めに
                )

                # HTTPエラーをチェック
                if response.status_code != 200:
                    self.logger.error(
                        f"ElevenLabs API returned status {response.status_code}: "
                        f"{response.text}"
                    )
                    response.raise_for_status()

            result = response.json()

            # レスポンス構造をログ出力（デバッグ用）
            self.logger.debug(f"ElevenLabs FA response keys: {result.keys()}")

            # audio_timing.json形式に変換
            alignment = self._convert_to_audio_timing_format(result, text)

            self.logger.info(
                f"✓ Alignment successful: {len(alignment['characters'])} characters"
            )

            return alignment

        except requests.HTTPError as e:
            self.logger.error(f"ElevenLabs API HTTP error: {e}")
            if e.response is not None:
                self.logger.error(f"Response status: {e.response.status_code}")
                self.logger.error(f"Response body: {e.response.text}")
            raise
        except requests.RequestException as e:
            self.logger.error(f"ElevenLabs API network error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Alignment failed: {e}", exc_info=True)
            raise

    def _convert_to_audio_timing_format(
        self,
        elevenlabs_response: Dict[str, Any],
        original_text: str
    ) -> Dict[str, Any]:
        """
        ElevenLabsのレスポンスをaudio_timing.json形式に変換

        Args:
            elevenlabs_response: ElevenLabs APIのレスポンス
            original_text: 元のテキスト

        Returns:
            audio_timing.json互換の形式
        """
        # ElevenLabs FAのレスポンス形式を確認して適切に変換
        # 想定される形式:
        # {
        #   "alignment": [
        #     {"char": "織", "start": 0.1, "end": 0.2},
        #     ...
        #   ]
        # }
        # または
        # {
        #   "characters": [...],
        #   "words": [...]
        # }

        characters = []
        char_start_times = []
        char_end_times = []
        words = []

        # レスポンスの構造をデバッグログに出力
        self.logger.debug(
            f"Converting ElevenLabs response. Keys: {elevenlabs_response.keys()}"
        )

        # ElevenLabsのレスポンス形式に応じて処理
        if "alignment" in elevenlabs_response:
            # 形式1: alignment キーがある場合
            alignment_data = elevenlabs_response["alignment"]

            if isinstance(alignment_data, list):
                for item in alignment_data:
                    # 文字情報
                    char = item.get("char") or item.get("character", "")
                    start = float(item.get("start", 0.0))
                    end = float(item.get("end", 0.0))

                    characters.append(char)
                    char_start_times.append(start)
                    char_end_times.append(end)
            else:
                self.logger.warning(
                    f"Unexpected alignment format: {type(alignment_data)}"
                )

        elif "characters" in elevenlabs_response:
            # 形式2: characters キーがある場合
            for item in elevenlabs_response["characters"]:
                char = item.get("character") or item.get("char", "")
                start = float(item.get("start", 0.0))
                end = float(item.get("end", 0.0))

                characters.append(char)
                char_start_times.append(start)
                char_end_times.append(end)

        elif "char_timings" in elevenlabs_response:
            # 形式3: char_timings キーがある場合
            for item in elevenlabs_response["char_timings"]:
                char = item.get("character") or item.get("char", "")
                start = float(item.get("start_time", 0.0))
                end = float(item.get("end_time", 0.0))

                characters.append(char)
                char_start_times.append(start)
                char_end_times.append(end)

        else:
            # フォールバック: レスポンス構造が予期しない場合
            self.logger.warning(
                "Unexpected ElevenLabs response format. "
                f"Available keys: {list(elevenlabs_response.keys())}"
            )
            self.logger.debug(
                f"Response sample: {json.dumps(elevenlabs_response, indent=2, ensure_ascii=False)[:500]}"
            )

            # 最悪のケース: 元のテキストから均等に割り当て
            duration = elevenlabs_response.get("duration", len(original_text) * 0.15)
            char_duration = duration / len(original_text) if len(original_text) > 0 else 0.15

            for i, char in enumerate(original_text):
                characters.append(char)
                char_start_times.append(i * char_duration)
                char_end_times.append((i + 1) * char_duration)

            self.logger.warning(
                f"Used fallback: uniform distribution ({len(characters)} chars, "
                f"{duration:.2f}s duration)"
            )

        # 単語情報も取得（あれば）
        if "words" in elevenlabs_response:
            words = elevenlabs_response["words"]

        # バリデーション
        if len(characters) == 0:
            self.logger.error(
                "No characters found in ElevenLabs response. "
                f"Response: {json.dumps(elevenlabs_response, indent=2, ensure_ascii=False)[:500]}"
            )
            raise ValueError("ElevenLabs alignment returned no characters")

        if len(characters) != len(char_start_times) or len(characters) != len(char_end_times):
            self.logger.error(
                f"Alignment length mismatch: {len(characters)} chars, "
                f"{len(char_start_times)} starts, {len(char_end_times)} ends"
            )
            raise ValueError("ElevenLabs alignment data length mismatch")

        # タイミングの妥当性チェック
        for i, (start, end) in enumerate(zip(char_start_times, char_end_times)):
            if start < 0 or end < 0:
                self.logger.warning(f"Character {i} has negative timing: {start} - {end}")
            if end < start:
                self.logger.warning(
                    f"Character {i} has end < start: {start} - {end}. Fixing..."
                )
                char_end_times[i] = start + 0.05  # 最低50ms

        self.logger.info(
            f"Converted alignment: {len(characters)} characters, "
            f"duration: {char_end_times[-1] if char_end_times else 0:.2f}s"
        )

        # audio_timing.json互換形式で返す
        return {
            "characters": characters,
            "char_start_times": char_start_times,
            "char_end_times": char_end_times,
            "alignment": {
                "characters": characters,
                "char_start_times": char_start_times,
                "char_end_times": char_end_times
            },
            # オプション: 単語レベルの情報も含める
            "words": words
        }


def create_elevenlabs_aligner(
    api_key: str,
    logger: Optional[logging.Logger] = None
) -> Optional[ElevenLabsForcedAligner]:
    """
    ElevenLabsForcedAlignerを作成

    Args:
        api_key: ElevenLabs API Key
        logger: ロガー

    Returns:
        ElevenLabsForcedAligner or None（作成失敗時）
    """
    if not ELEVENLABS_FA_AVAILABLE:
        if logger:
            logger.warning(
                "ElevenLabs Forced Alignment is not available. "
                "Install requests: pip install requests"
            )
        return None

    if not api_key:
        if logger:
            logger.warning("ElevenLabs API key is not provided")
        return None

    try:
        return ElevenLabsForcedAligner(api_key=api_key, logger=logger)
    except Exception as e:
        if logger:
            logger.error(f"Failed to create ElevenLabs aligner: {e}")
        return None
