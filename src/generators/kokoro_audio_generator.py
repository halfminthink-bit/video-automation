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
from pathlib import Path
from typing import Dict, List, Optional, Any



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
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            api_url: Kokoro FastAPI のベースURL（環境変数 KOKORO_API_URL を優先）
            voice: 使用する音声名（af_bella, af_sarah, af_sky等）
            speed: 速度（0.5-2.0）
            response_format: 出力形式（mp3, wav, opus, flac）
            logger: ロガー

        Raises:
            ConnectionError: APIサーバーに接続できない場合
        """
        # 環境変数からURLを取得（オーバーライド優先）
        self.api_url = os.getenv("KOKORO_API_URL", api_url or "http://localhost:8880")
        self.voice = voice
        self.speed = speed
        self.response_format = response_format
        self.logger = logger or logging.getLogger(__name__)

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
        Kokoro TTS FastAPIを使用してタイムスタンプ付き音声を生成

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
        import base64
        import json

        self.logger.info(f"Generating audio with timestamps: {text[:50]}...")

        # ✅ 修正1: エンドポイントを変更
        url = f"{self.api_url}/dev/captioned_speech"  # ← 重要！

        payload = {
            "model": "kokoro",
            "input": text,
            "voice": self.voice,
            "speed": self.speed,
            "response_format": self.response_format,
            "stream": False
        }

        try:
            response = requests.post(url, json=payload, stream=False, timeout=60)
            response.raise_for_status()

            # ✅ 修正2: JSONレスポンスをパース
            result = response.json()

            # ✅ 修正3: Base64デコード
            audio_base64 = result.get("audio", "")
            if not audio_base64:
                raise ValueError("API returned empty audio field")

            # ✅ 修正4: タイムスタンプ取得（Noneチェック）
            timestamps = result.get("timestamps") or []

            self.logger.info(f"Received {len(timestamps)} timestamps from API")

            if not timestamps:
                self.logger.warning("No timestamps received from API")

            # ✅ 修正5: ElevenLabs互換形式に変換
            characters = []
            start_times = []
            end_times = []

            for ts in timestamps:
                if isinstance(ts, dict):
                    word = ts.get("word", "")
                    if word:
                        characters.append(word)
                        start_times.append(float(ts.get("start_time", 0.0)))
                        end_times.append(float(ts.get("end_time", 0.0)))

            alignment = {
                'characters': characters,
                'character_start_times_seconds': start_times,
                'character_end_times_seconds': end_times
            }

            self.logger.info(
                f"✓ Generated {len(characters)} words, "
                f"duration: {end_times[-1] if end_times else 0:.2f}s"
            )

            return {
                'audio_base64': audio_base64,
                'alignment': alignment
            }

        except Exception as e:
            self.logger.error(f"Error: {e}", exc_info=True)
            raise

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
