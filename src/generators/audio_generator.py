"""
音声生成器

ElevenLabs APIを使用してテキストから音声を生成。
APIが利用できない場合はダミー生成器を使用。
"""

import logging
import base64
from pathlib import Path
from typing import Optional, Dict, Any
import time
import subprocess
import tempfile

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    ElevenLabs = None
    VoiceSettings = None


class AudioGenerator:
    """ElevenLabs APIを使用した音声生成クラス"""
    
    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model: str = "eleven_multilingual_v2",
        settings: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            api_key: ElevenLabs APIキー
            voice_id: 使用する音声ID
            model: モデル名
            settings: 音声設定（stability, similarity_boost, speed等）
            logger: ロガー
            
        Raises:
            ImportError: elevenlabsパッケージがインストールされていない場合
        """
        if not ELEVENLABS_AVAILABLE:
            raise ImportError(
                "elevenlabs package is required. "
                "Install it with: pip install elevenlabs"
            )
        
        # 新しいAPI: ElevenLabsクライアントを作成
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.model = model
        self.settings = settings or {}
        self.logger = logger or logging.getLogger(__name__)
        
        # 速度設定を取得（デフォルト: 1.0 = 通常速度）
        self.speed = self.settings.get("speed", 1.0)
        
        self.logger.info(
            f"AudioGenerator initialized: "
            f"voice_id={voice_id}, model={model}, speed={self.speed}"
        )
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        ffprobeを使用して音声の長さを取得
        
        Args:
            audio_path: 音声ファイルパス
            
        Returns:
            音声の長さ（秒）
        """
        import json
        
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(audio_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        return float(info['format']['duration'])
    
    def generate(self, text: str) -> bytes:
        """
        テキストから音声を生成（バイナリデータを返す）
        
        Args:
            text: 生成するテキスト
            
        Returns:
            音声データ（MP3バイナリ）
            
        Raises:
            Exception: 生成失敗時
        """
        self.logger.debug(f"Generating audio for text: {text[:50]}...")
        
        # VoiceSettingsを作成
        voice_settings = VoiceSettings(
            stability=self.settings.get("stability", 0.5),
            similarity_boost=self.settings.get("similarity_boost", 0.75),
            style=self.settings.get("style", 0),
            use_speaker_boost=self.settings.get("use_speaker_boost", True)
        )
        
        # 新しいAPI: text_to_speech.convert()を使用
        # speed パラメータを追加
        response = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id=self.model,
            voice_settings=voice_settings,
            output_format="mp3_44100_128"  # 出力フォーマットを明示
        )
        
        # ストリームからバイナリデータを取得
        audio_data = b"".join(response)
        
        # 速度調整が必要な場合（speed != 1.0）、ffmpegで調整
        if self.speed != 1.0:
            audio_data = self._adjust_speed(audio_data, self.speed)
        
        return audio_data

    def generate_with_timestamps(
        self,
        text: str,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        タイムスタンプ付きで音声を生成（文脈対応）

        ElevenLabs API の convert_with_timestamps() メソッドを使用して、
        音声データと文字レベルのタイミング情報を同時に取得。

        previous_text/next_textを指定することで、前後の文脈を考慮した
        自然なイントネーションで音声を生成できる。

        Args:
            text: 生成するテキスト
            previous_text: 前のテキスト（文脈用、無料）
            next_text: 次のテキスト（文脈用、無料）

        Returns:
            {
                'audio_base64': str,  # Base64エンコードされた音声データ
                'alignment': {
                    'characters': List[str],  # 文字のリスト
                    'character_start_times_seconds': List[float],  # 各文字の開始時間
                    'character_end_times_seconds': List[float]  # 各文字の終了時間
                }
            }

        Raises:
            ValueError: レスポンスの検証失敗時
            Exception: API呼び出し失敗時
        """
        self.logger.info(f"Generating audio with timestamps: {text[:50]}...")

        if previous_text:
            self.logger.debug(f"Using previous_text for context: {previous_text[:30]}...")
        if next_text:
            self.logger.debug(f"Using next_text for context: {next_text[:30]}...")

        try:
            # VoiceSettingsを作成
            voice_settings = VoiceSettings(
                stability=self.settings.get("stability", 0.5),
                similarity_boost=self.settings.get("similarity_boost", 0.75),
                style=self.settings.get("style", 0),
                use_speaker_boost=self.settings.get("use_speaker_boost", True)
            )

            # ElevenLabs SDK の convert_with_timestamps() を使用
            # previous_text / next_text を追加
            self.logger.debug(
                f"API call: voice_id={self.voice_id}, model={self.model}, "
                f"output_format=mp3_44100_128"
            )

            response = self.client.text_to_speech.convert_with_timestamps(
                text=text,
                voice_id=self.voice_id,
                model_id=self.model,
                output_format="mp3_44100_128",
                voice_settings=voice_settings,
                previous_text=previous_text,
                next_text=next_text
            )

            # レスポンスから情報を取得
            # Pydantic モデルの場合は属性アクセス、辞書の場合は get() を使用
            # 注意: ElevenLabs APIは audio_base_64 (アンダースコア入り) を返す
            if hasattr(response, 'audio_base_64'):
                audio_base64 = response.audio_base_64
            elif isinstance(response, dict):
                audio_base64 = response.get('audio_base_64', '')
            else:
                audio_base64 = ''

            # audio_base64 の検証
            if not audio_base64:
                error_msg = (
                    "API returned empty audio_base_64. "
                    "Possible causes: API key invalid, insufficient credits, "
                    "model not supporting timestamps, or network issues."
                )
                self.logger.error(error_msg)
                self.logger.error(f"Response type: {type(response)}")
                self.logger.error(f"Response attributes: {dir(response)}")
                raise ValueError(error_msg)

            # アライメント情報を取得
            if hasattr(response, 'alignment'):
                alignment = response.alignment
                characters = alignment.characters if hasattr(alignment, 'characters') else []
                start_times = (
                    alignment.character_start_times_seconds
                    if hasattr(alignment, 'character_start_times_seconds')
                    else []
                )
                end_times = (
                    alignment.character_end_times_seconds
                    if hasattr(alignment, 'character_end_times_seconds')
                    else []
                )
            elif isinstance(response, dict) and 'alignment' in response:
                alignment = response['alignment']
                characters = alignment.get('characters', [])
                start_times = alignment.get('character_start_times_seconds', [])
                end_times = alignment.get('character_end_times_seconds', [])
            else:
                characters = []
                start_times = []
                end_times = []

            result = {
                'audio_base64': audio_base64,
                'alignment': {
                    'characters': characters,
                    'character_start_times_seconds': start_times,
                    'character_end_times_seconds': end_times
                }
            }

            # 成功ログ
            char_count = len(characters)
            audio_size = len(audio_base64) if audio_base64 else 0
            self.logger.info(
                f"Generated audio with {char_count} characters "
                f"(audio_base64 size: {audio_size} bytes)"
            )

            return result

        except Exception as e:
            self.logger.error(f"Failed to generate audio with timestamps: {e}")
            self.logger.error(f"Text: {text[:100]}...")
            self.logger.error(f"Voice ID: {self.voice_id}, Model: {self.model}")
            raise
    
        # レスポンスのデバッグ情報をログ出力
        self.logger.debug(f"Response type: {type(response)}")
        self.logger.debug(f"Response attributes: {dir(response)}")

        # レスポンスから情報を取得
        # Pydanticモデルの場合、model_dump()やdict()で辞書に変換できる
        if hasattr(response, 'model_dump'):
            response_dict = response.model_dump()
            self.logger.debug(f"Response dict keys: {response_dict.keys()}")
        elif hasattr(response, 'dict'):
            response_dict = response.dict()
            self.logger.debug(f"Response dict keys: {response_dict.keys()}")
        elif isinstance(response, dict):
            response_dict = response
            self.logger.debug(f"Response is already a dict with keys: {response_dict.keys()}")
        else:
            # フォールバック: 属性から直接取得
            self.logger.warning(f"Unknown response format, trying attribute access")
            response_dict = {
                'audio_base64': getattr(response, 'audio_base64', ''),
                'alignment': getattr(response, 'alignment', {})
            }

        # audio_base64を取得
        audio_base64 = response_dict.get('audio_base64', '')
        if not audio_base64:
            self.logger.error("audio_base64 is empty!")
            self.logger.error(f"Full response: {response_dict}")
            raise ValueError("ElevenLabs API returned empty audio_base64")

        # alignmentを取得
        alignment = response_dict.get('alignment', {})
        if isinstance(alignment, dict):
            characters = alignment.get('characters', [])
            char_start_times = alignment.get('character_start_times_seconds', [])
            char_end_times = alignment.get('character_end_times_seconds', [])
        else:
            # alignmentがオブジェクトの場合
            characters = getattr(alignment, 'characters', [])
            char_start_times = getattr(alignment, 'character_start_times_seconds', [])
            char_end_times = getattr(alignment, 'character_end_times_seconds', [])

        result = {
            'audio_base64': audio_base64,
            'alignment': {
                'characters': characters,
                'character_start_times_seconds': char_start_times,
                'character_end_times_seconds': char_end_times
            }
        }

        self.logger.info(
            f"Generated audio: {len(audio_base64)} chars base64, "
            f"{len(characters)} character timings"
        )

        return result

    def _adjust_speed(self, audio_data: bytes, speed: float) -> bytes:
        """
        ffmpegを使用して音声速度を調整
        
        Args:
            audio_data: 元の音声データ
            speed: 速度倍率（0.5=半分の速度、2.0=2倍速）
            
        Returns:
            速度調整後の音声データ
        """
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_in:
            tmp_in.write(audio_data)
            tmp_in_path = Path(tmp_in.name)
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_out:
            tmp_out_path = Path(tmp_out.name)
        
        try:
            # ffmpegで速度調整（asetrate + atempo）
            # 0.5-2.0の範囲はatempoで対応
            # それ以外はasetrateも併用
            
            if 0.5 <= speed <= 2.0:
                # atempoのみで対応可能
                cmd = [
                    'ffmpeg',
                    '-i', str(tmp_in_path),
                    '-filter:a', f'atempo={speed}',
                    '-y',
                    str(tmp_out_path)
                ]
            else:
                # asetrateとatempoを組み合わせ
                # speed = 0.85の場合は atempo=0.85 で対応
                self.logger.warning(
                    f"Speed {speed} is out of atempo range (0.5-2.0). "
                    "Using asetrate+atempo combination."
                )
                cmd = [
                    'ffmpeg',
                    '-i', str(tmp_in_path),
                    '-filter:a', f'asetrate=44100*{speed},aresample=44100,atempo=1.0',
                    '-y',
                    str(tmp_out_path)
                ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # 調整後のデータを読み込み
            with open(tmp_out_path, 'rb') as f:
                return f.read()
        finally:
            tmp_in_path.unlink(missing_ok=True)
            tmp_out_path.unlink(missing_ok=True)
    
    def generate_to_file(
        self,
        text: str,
        output_path: Path,
        max_retries: int = 5
    ) -> float:
        """
        テキストから音声を生成してファイルに保存
        
        Args:
            text: 生成するテキスト
            output_path: 出力ファイルパス
            max_retries: 最大リトライ回数
            
        Returns:
            生成された音声の長さ（秒）
            
        Raises:
            Exception: 最大リトライ回数を超えても失敗した場合
        """
        self.logger.info(f"Generating audio: {text[:50]}... (speed={self.speed})")
        
        for attempt in range(max_retries):
            try:
                # 音声生成
                audio_data = self.generate(text)
                
                # ファイルに保存
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
                
                # 長さを取得（ffprobeを使用）
                duration = self._get_audio_duration(output_path)
                file_size = output_path.stat().st_size / (1024 * 1024)
                
                self.logger.info(
                    f"Audio generated: {output_path} "
                    f"({duration:.1f}s, {file_size:.2f}MB, speed={self.speed}x)"
                )
                
                return duration
                
            except Exception as e:
                self.logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                
                if attempt < max_retries - 1:
                    # レート制限対応: 待機時間を徐々に増やす
                    wait_time = 10 * (attempt + 1)
                    self.logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(
                        f"Failed to generate audio after {max_retries} attempts"
                    )
                    raise


class DummyAudioGenerator:
    """
    テスト用ダミー音声生成器
    
    実際のAPIを呼び出さず、無音MP3を生成する。
    テストやAPIクレジットの節約に使用。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)
        self.logger.warning(
            "DummyAudioGenerator initialized. "
            "Will generate silent audio instead of real speech."
        )
    
    def generate(self, text: str) -> bytes:
        """
        ダミー音声データを生成
        
        Args:
            text: テキスト（文字数から推定時間を計算）
            
        Returns:
            音声データ（無音MP3バイナリ）
        """
        # 推定時間を計算（1文字 = 0.5秒）
        estimated_duration = len(text) * 0.5
        
        # 一時ファイルに無音を生成
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            # ffmpegで無音を生成
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'anullsrc=r=44100:cl=mono',
                '-t', str(estimated_duration),
                '-q:a', '9',
                '-acodec', 'libmp3lame',
                '-y',
                str(tmp_path)
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # バイナリを読み込み
            with open(tmp_path, 'rb') as f:
                return f.read()
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def generate_to_file(
        self,
        text: str,
        output_path: Path,
        max_retries: int = 5
    ) -> float:
        """
        ダミー音声（無音）を生成してファイルに保存
        
        テキストの文字数から推定時間を計算: 1文字 = 0.5秒
        
        Args:
            text: テキスト
            output_path: 出力ファイルパス
            max_retries: 未使用（互換性のため）
            
        Returns:
            生成された音声の長さ（秒）
        """
        self.logger.warning(f"Using dummy generator for: {text[:50]}...")
        
        # 推定時間を計算（1文字 = 0.5秒）
        estimated_duration = len(text) * 0.5
        
        # 保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # ffmpegで無音を生成
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'anullsrc=r=44100:cl=mono',
            '-t', str(estimated_duration),
            '-q:a', '9',
            '-acodec', 'libmp3lame',
            '-y',
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        file_size = output_path.stat().st_size / (1024 * 1024)
        
        self.logger.info(
            f"Dummy audio saved: {output_path} "
            f"({estimated_duration:.1f}s, {file_size:.2f}MB)"
        )
        
        return estimated_duration


# ========================================
# ファクトリー関数
# ========================================

def create_audio_generator(
    api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    use_dummy: bool = False,
    logger: Optional[logging.Logger] = None
):
    """
    音声生成器を作成
    
    APIキーがない場合やuse_dummy=Trueの場合は
    ダミー生成器を返す。
    
    Args:
        api_key: ElevenLabs APIキー
        config: 設定辞書（voice_id, model, settings等）
        use_dummy: Trueの場合、ダミー生成器を使用
        logger: ロガー
        
    Returns:
        AudioGenerator または DummyAudioGenerator
        
    Example:
        # 通常使用
        generator = create_audio_generator(
            api_key="your_key",
            config={"voice_id": "...", "model": "...", "settings": {"speed": 0.85}}
        )
        
        # ダミーモード
        generator = create_audio_generator(use_dummy=True)
    """
    if use_dummy or not api_key:
        if logger:
            logger.info("Creating DummyAudioGenerator")
        return DummyAudioGenerator(logger=logger)
    
    if not ELEVENLABS_AVAILABLE:
        if logger:
            logger.warning(
                "elevenlabs package not available. "
                "Falling back to DummyAudioGenerator"
            )
        return DummyAudioGenerator(logger=logger)
    
    config = config or {}
    
    if logger:
        logger.info("Creating AudioGenerator with ElevenLabs API")
    
    return AudioGenerator(
        api_key=api_key,
        voice_id=config.get("voice_id", "21m00Tcm4TlvDq8ikWAM"),
        model=config.get("model", "eleven_multilingual_v2"),
        settings=config.get("settings", {}),
        logger=logger
    )


# ========================================
# テスト用関数
# ========================================

def test_audio_generator():
    """音声生成器の動作テスト"""
    import tempfile
    
    # ダミーモードでテスト
    generator = create_audio_generator(use_dummy=True)
    
    test_text = "これはテストです。音声生成が正しく動作するか確認しています。"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test.mp3"
        
        try:
            duration = generator.generate_to_file(test_text, output_path)
            
            print(f"✓ Test passed: generated {duration:.1f}s audio")
            print(f"  File: {output_path}")
            print(f"  Size: {output_path.stat().st_size / 1024:.1f}KB")
        except Exception as e:
            print(f"✗ Test failed: {e}")
            raise


if __name__ == "__main__":
    # 簡易テスト
    logging.basicConfig(level=logging.INFO)
    test_audio_generator()