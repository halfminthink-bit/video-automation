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
        # ✅ 正しいエンドポイント: /v1/forced-alignment
        self.endpoint = "https://api.elevenlabs.io/v1/forced-alignment"
        self.logger = logger or logging.getLogger(__name__)

        self.logger.info("ElevenLabs Forced Aligner initialized")

    def align(
        self,
        audio_path: Path,
        text: str,
        language: str = "ja"  # 互換性のため残すが、APIでは使用されない（自動検出）
    ) -> Dict[str, Any]:
        """
        音声ファイルとテキストをアラインメント

        Args:
            audio_path: 音声ファイルのパス（最大3GB、最長10時間）
            text: 台本テキスト（正確なテキスト、必須）
            language: 言語コード（互換性のため残すが、APIでは自動検出されるため使用されない）

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
                "words": [...]  # オプション（単語レベルのタイミング情報）
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
            # ✅ 正しいリクエスト形式: multipart/form-data
            # ✅ フィールド名は 'file' (audio ではない)
            # ✅ language と model_id は不要（自動検出される）
            with open(audio_path, 'rb') as f:
                files = {
                    'file': (audio_path.name, f, 'audio/mpeg')
                }
                data = {
                    'text': text
                    # language と model_id は不要（自動検出）
                }
                headers = {
                    'xi-api-key': self.api_key
                }

                self.logger.debug(f"Sending request to {self.endpoint}")
                self.logger.debug(f"Text length: {len(text)} characters")

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
            self.logger.debug(f"ElevenLabs FA response keys: {list(result.keys())}")
            self.logger.debug(
                f"Response sample: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}"
            )

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
        self.logger.debug(f"Response keys: {list(elevenlabs_response.keys())}")

        characters = []
        char_start_times = []
        char_end_times = []
        words = []

        # 🔥 実際のレスポンス形式: {"characters": [{"text": "織", "start": 0.1, "end": 0.2}, ...]}
        if "characters" not in elevenlabs_response:
            # alignment キーがある場合はそちらを試す
            if "alignment" in elevenlabs_response:
                alignment_data = elevenlabs_response["alignment"]
                if isinstance(alignment_data, list):
                    for item in alignment_data:
                        # 複数のキー名に対応
                        char = item.get("text") or item.get("character") or item.get("char", "")
                        start = float(item.get("start", item.get("start_time", 0.0)))
                        end = float(item.get("end", item.get("end_time", start)))

                        if char:
                            characters.append(char)
                            char_start_times.append(start)
                            char_end_times.append(end)
            else:
                raise ValueError(
                    f"Missing 'characters' key. Available keys: {list(elevenlabs_response.keys())}"
                )
        else:
            # 形式: characters キーがある場合（実際のレスポンス形式）
            char_list = elevenlabs_response["characters"]

            if not char_list:
                raise ValueError("Empty characters list in response")

            self.logger.info(f"Processing {len(char_list)} characters")

            for item in char_list:
                # 🔥 キー名は "text" です（"character" や "char" ではない）
                char = item.get("text") or item.get("character") or item.get("char", "")
                start = float(item.get("start", item.get("start_time", 0.0)))
                end = float(item.get("end", item.get("end_time", start)))  # endが無い場合はstartを使用

                if not char:
                    self.logger.warning(f"Empty character at {start}s, skipping")
                    continue

                characters.append(char)
                char_start_times.append(start)
                char_end_times.append(end)

        if not characters:
            raise ValueError("No valid characters extracted")

        self.logger.info(
            f"✓ Extracted {len(characters)} characters "
            f"(0.00s - {char_end_times[-1] if char_end_times else 0:.2f}s)"
        )

        # 単語情報も取得（あれば）
        if "words" in elevenlabs_response:
            words_data = elevenlabs_response["words"]
            if isinstance(words_data, list):
                words = words_data
            else:
                self.logger.warning(f"Unexpected words format: {type(words_data)}")
                words = []

        # バリデーション
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
