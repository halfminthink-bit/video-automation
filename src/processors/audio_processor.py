"""
音声処理ユーティリティ

ffmpeg-pythonを使用した音声ファイルの結合、解析、変換を提供。
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import tempfile
import shutil


class AudioProcessor:
    """音声処理ユーティリティクラス"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            logger: ロガー（Noneの場合は標準ロガーを使用）
        """
        self.logger = logger or logging.getLogger(__name__)
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """ffmpegがインストールされているか確認"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.debug("ffmpeg is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error(
                "ffmpeg not found. Please install ffmpeg:\n"
                "  Windows: https://ffmpeg.org/download.html\n"
                "  macOS: brew install ffmpeg\n"
                "  Linux: sudo apt-get install ffmpeg"
            )
            raise RuntimeError("ffmpeg is required but not found")
    
    def _get_audio_info(self, audio_path: Path) -> Dict[str, Any]:
        """
        ffprobeで音声ファイル情報を取得
        
        Args:
            audio_path: 音声ファイルパス
            
        Returns:
            音声情報の辞書
        """
        # Windowsでの日本語パス対応: パスを絶対パスに変換
        audio_path = Path(audio_path).resolve()
        
        # ファイルの存在チェック
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        self.logger.debug(f"Getting audio info for: {audio_path}")
        
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(audio_path)
        ]

        # Windowsの場合、環境変数でエンコーディングを指定
        env = os.environ.copy()
        if sys.platform == 'win32':
            # Windowsでのエンコーディング問題を回避
            env['PYTHONIOENCODING'] = 'utf-8'

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True,
            env=env
        )

        # stdout が None または空の場合のエラーハンドリング
        if not result.stdout:
            error_msg = (
                f"ffprobe returned no output for {audio_path}.\n"
                f"File exists: {audio_path.exists()}\n"
                f"File size: {audio_path.stat().st_size if audio_path.exists() else 'N/A'} bytes\n"
                f"stderr: {result.stderr}\n"
                f"Command: {' '.join(cmd)}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        return json.loads(result.stdout)
    
    def combine_audio_files(
        self,
        audio_paths: List[Path],
        output_path: Path,
        silence_duration: float = 0.5
    ) -> float:
        """
        複数の音声ファイルを結合
        
        各音声ファイルの間に無音を挿入して結合する。
        
        Args:
            audio_paths: 音声ファイルのパスリスト
            output_path: 出力ファイルパス
            silence_duration: セクション間の無音時間（秒）
            
        Returns:
            統合後の音声の長さ（秒）
            
        Raises:
            FileNotFoundError: 音声ファイルが見つからない場合
            Exception: 結合処理が失敗した場合
        """
        if not audio_paths:
            raise ValueError("audio_paths cannot be empty")
        
        self.logger.info(f"Combining {len(audio_paths)} audio files")
        
        # 各ファイルが存在するか確認
        for path in audio_paths:
            if not path.exists():
                raise FileNotFoundError(f"Audio file not found: {path}")
        
        # 出力ディレクトリを作成
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 無音ファイルを作成
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as silence_file:
            silence_path = Path(silence_file.name)
        
        try:
            # 無音を生成
            self._create_silence_file(silence_path, silence_duration)
            
            # 結合するファイルリストを作成（音声+無音+音声+無音+...）
            files_to_concat = []
            for i, audio_path in enumerate(audio_paths):
                files_to_concat.append(audio_path)
                # 最後のファイル以外は無音を追加
                if i < len(audio_paths) - 1:
                    files_to_concat.append(silence_path)
            
            # concat用のファイルリストを作成
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as concat_file:
                concat_list_path = Path(concat_file.name)
                for file_path in files_to_concat:
                    # パスにスペースや特殊文字がある場合のエスケープ
                    path_str = str(file_path).replace('\\', '/')
                    concat_file.write(f"file '{path_str}'\n")
            
            try:
                # ffmpegで結合（再エンコード）
                # -c copy ではなく再エンコードすることで互換性の問題を回避
                cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_list_path),
                    '-c:a', 'libmp3lame',  # MP3コーデックで再エンコード
                    '-b:a', '128k',  # ビットレート
                    '-ar', '44100',  # サンプリングレート
                    '-y',  # 上書き
                    str(output_path)
                ]

                try:
                    # Windowsでのエンコーディング対応
                    env = os.environ.copy()
                    if sys.platform == 'win32':
                        env['PYTHONIOENCODING'] = 'utf-8'
                    
                    result = subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        env=env
                    )

                    # デバッグ用にffmpegの出力をログに記録
                    if result.stderr:
                        self.logger.debug(f"ffmpeg output: {result.stderr}")
                except subprocess.CalledProcessError as e:
                    # ffmpegのエラー詳細をログに記録
                    self.logger.error(f"ffmpeg command failed: {' '.join(cmd)}")
                    self.logger.error(f"ffmpeg stdout: {e.stdout}")
                    self.logger.error(f"ffmpeg stderr: {e.stderr}")

                    # concat listの内容も記録
                    with open(concat_list_path, 'r', encoding='utf-8') as f:
                        concat_content = f.read()
                    self.logger.error(f"Concat list content:\n{concat_content}")

                    raise
                
                # 長さを取得
                duration = self.get_duration(output_path)
                file_size = output_path.stat().st_size / (1024 * 1024)
                
                self.logger.info(
                    f"Combined audio saved: {output_path} "
                    f"({duration:.1f}s, {file_size:.1f}MB)"
                )
                
                return duration
                
            finally:
                # 一時ファイルを削除
                concat_list_path.unlink(missing_ok=True)
        
        finally:
            # 無音ファイルを削除
            silence_path.unlink(missing_ok=True)
    
    def _create_silence_file(self, output_path: Path, duration: float):
        """
        無音ファイルを作成
        
        Args:
            output_path: 出力ファイルパス
            duration: 無音の長さ（秒）
        """
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=mono',
            '-t', str(duration),
            '-q:a', '9',
            '-acodec', 'libmp3lame',
            '-y',
            str(output_path)
        ]
        
        # Windowsでのエンコーディング対応
        env = os.environ.copy()
        if sys.platform == 'win32':
            env['PYTHONIOENCODING'] = 'utf-8'
        
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
    
    def get_duration(self, audio_path: Path) -> float:
        """
        音声ファイルの長さを取得
        
        Args:
            audio_path: 音声ファイルパス
            
        Returns:
            音声の長さ（秒）
            
        Raises:
            FileNotFoundError: ファイルが見つからない場合
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        info = self._get_audio_info(audio_path)
        duration = float(info['format']['duration'])
        
        self.logger.debug(f"Duration of {audio_path.name}: {duration:.1f}s")
        
        return duration
    
    def analyze_audio(self, audio_path: Path) -> Dict[str, Any]:
        """
        音声ファイルを解析
        
        音声の長さ、サンプルレート、チャンネル数などを解析。
        
        Args:
            audio_path: 音声ファイルパス
            
        Returns:
            解析結果の辞書:
            {
                "duration": 910.5,
                "sample_rate": 44100,
                "channels": 1,
                "format": "mp3",
                "file_size_mb": 14.2
            }
            
        Raises:
            FileNotFoundError: ファイルが見つからない場合
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        self.logger.info(f"Analyzing audio: {audio_path}")
        
        info = self._get_audio_info(audio_path)
        
        # ファイルサイズ取得
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        
        # オーディオストリームを取得
        audio_stream = None
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_stream = stream
                break
        
        if not audio_stream:
            raise ValueError(f"No audio stream found in {audio_path}")
        
        analysis = {
            "duration": float(info['format']['duration']),
            "sample_rate": int(audio_stream.get('sample_rate', 0)),
            "channels": int(audio_stream.get('channels', 0)),
            "format": "mp3",
            "file_size_mb": file_size_mb,
            "bit_rate": int(info['format'].get('bit_rate', 0)),
            "codec": audio_stream.get('codec_name', 'unknown')
        }
        
        self.logger.info(
            f"Analysis complete: {analysis['duration']:.1f}s, "
            f"{analysis['file_size_mb']:.1f}MB"
        )
        
        return analysis
    
    def create_silence(self, duration: float, output_path: Optional[Path] = None) -> Path:
        """
        無音を生成
        
        Args:
            duration: 無音の長さ（秒）
            output_path: 出力パス（Noneの場合は一時ファイル）
            
        Returns:
            無音ファイルのPath
        """
        if duration < 0:
            raise ValueError("duration must be non-negative")
        
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix='.mp3'))
        
        self._create_silence_file(output_path, duration)
        self.logger.debug(f"Created {duration:.1f}s silence: {output_path}")
        
        return output_path


# ========================================
# ユーティリティ関数
# ========================================

def create_audio_processor(logger: Optional[logging.Logger] = None) -> AudioProcessor:
    """
    AudioProcessorインスタンスを作成
    
    Args:
        logger: ロガー
        
    Returns:
        AudioProcessor
    """
    return AudioProcessor(logger=logger)