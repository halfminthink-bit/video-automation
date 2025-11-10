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
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            api_url: Kokoro FastAPI のベースURL（環境変数 KOKORO_API_URL を優先）
            voice: 使用する音声名（af_bella, af_sarah, af_sky等）
            logger: ロガー

        Raises:
            ConnectionError: APIサーバーに接続できない場合
        """
        # 環境変数からURLを取得（オーバーライド優先）
        self.api_url = os.getenv("KOKORO_API_URL", api_url or "http://localhost:8880")
        self.voice = voice
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
        next_text: Optional[str] = None,
        output_path: Optional[Path] = None,
        speed: float = 1.0,
        response_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        テキストから音声とタイムスタンプを生成

        Args:
            text: 生成するテキスト
            previous_text: 前のテキスト（Kokoro TTSでは未使用、互換性のため保持）
            next_text: 次のテキスト（Kokoro TTSでは未使用、互換性のため保持）
            output_path: 出力ファイルパス（Noneの場合は保存しない）
            speed: 速度（0.5-2.0）
            response_format: 出力形式（mp3, wav, opus, flac）

        Returns:
            {
                "audio_base64": str,  # Base64エンコードされた音声データ
                "alignment": {
                    "characters": List[str],
                    "character_start_times_seconds": List[float],
                    "character_end_times_seconds": List[float]
                }
            }

        Raises:
            Exception: 音声生成失敗時
        """
        self.logger.info(f"Kokoro TTS で音声生成: {len(text)} 文字")

        try:
            response = requests.post(
                f"{self.api_url}/dev/captioned_speech",
                json={
                    "model": "kokoro",
                    "input": text,
                    "voice": self.voice,
                    "speed": speed,
                    "response_format": response_format,
                    "stream": False,
                },
                timeout=300  # 長い文章用に5分
            )
            response.raise_for_status()

            # レスポンスをJSON解析
            result = response.json()

            # Base64エンコードされた音声を取得
            audio_base64 = result.get("audio")
            if not audio_base64:
                raise ValueError("APIレスポンスに音声データが含まれていません")

            # タイムスタンプ情報を取得
            timestamps = result.get("timestamps", [])

            # ElevenLabs互換のフォーマットに変換
            characters = []
            char_start_times = []
            char_end_times = []

            for ts in timestamps:
                word = ts.get("word", "")
                start_time = ts.get("start_time", 0.0)
                end_time = ts.get("end_time", 0.0)

                # 単語を文字に分解
                for i, char in enumerate(word):
                    characters.append(char)
                    # 文字ごとの時間を均等に分割
                    char_duration = (end_time - start_time) / len(word)
                    char_start_times.append(start_time + i * char_duration)
                    char_end_times.append(start_time + (i + 1) * char_duration)

            # 出力ファイルに保存する場合
            if output_path:
                audio_bytes = base64.b64decode(audio_base64)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
                self.logger.info(f"音声ファイルを保存: {output_path}")

            # 音声の長さを計算
            duration = char_end_times[-1] if char_end_times else 0.0

            self.logger.info(
                f"音声生成完了: {duration:.2f}秒, "
                f"{len(timestamps)} 単語, {len(characters)} 文字"
            )

            return {
                "audio_base64": audio_base64,
                "alignment": {
                    "characters": characters,
                    "character_start_times_seconds": char_start_times,
                    "character_end_times_seconds": char_end_times
                }
            }

        except requests.exceptions.Timeout:
            error_msg = f"音声生成がタイムアウトしました（テキスト長: {len(text)}文字）"
            self.logger.error(error_msg)
            raise TimeoutError(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"API呼び出しエラー: {e}"
            self.logger.error(error_msg)
            raise
        except Exception as e:
            self.logger.error(f"音声生成失敗: {e}")
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

            result = self.generate_with_timestamps(
                text=narration,
                output_path=output_path,
                speed=speed
            )

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

            result = generator.generate_with_timestamps(
                text=test_text,
                output_path=output_path
            )

            print("\n" + "="*60)
            print("✓ テスト成功")
            print("="*60)
            print(f"ファイル: {output_path}")
            print(f"音声長: {result['alignment']['character_end_times_seconds'][-1]:.2f}秒")
            print(f"文字数: {len(result['alignment']['characters'])}")
            print(f"サイズ: {output_path.stat().st_size / 1024:.1f}KB")

    except Exception as e:
        print(f"\n✗ テスト失敗: {e}")
        raise


if __name__ == "__main__":
    test_kokoro_generator()
