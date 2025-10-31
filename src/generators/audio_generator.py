"""
音声生成器

ElevenLabs APIを使用してテキストから音声を生成。
APIが利用できない場合はダミー生成器を使用。
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
import time
import subprocess
import tempfile

try:
    from elevenlabs import generate, set_api_key, Voice, VoiceSettings
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False


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
            settings: 音声設定（stability, similarity_boost等）
            logger: ロガー
            
        Raises:
            ImportError: elevenlabsパッケージがインストールされていない場合
        """
        if not ELEVENLABS_AVAILABLE:
            raise ImportError(
                "elevenlabs package is required. "
                "Install it with: pip install elevenlabs"
            )
        
        set_api_key(api_key)
        self.voice_id = voice_id
        self.model = model
        self.settings = settings or {}
        self.logger = logger or logging.getLogger(__name__)
        
        self.logger.info(
            f"AudioGenerator initialized: "
            f"voice_id={voice_id}, model={model}"
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
        
        audio_data = generate(
            text=text,
            voice=Voice(
                voice_id=self.voice_id,
                settings=VoiceSettings(
                    stability=self.settings.get("stability", 0.5),
                    similarity_boost=self.settings.get("similarity_boost", 0.75),
                    style=self.settings.get("style", 0),
                    use_speaker_boost=self.settings.get("use_speaker_boost", True)
                )
            ),
            model=self.model
        )
        
        return audio_data
    
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
        self.logger.info(f"Generating audio: {text[:50]}...")
        
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
                    f"({duration:.1f}s, {file_size:.2f}MB)"
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
            config={"voice_id": "...", "model": "..."}
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