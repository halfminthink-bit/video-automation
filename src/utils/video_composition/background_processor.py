"""背景動画を処理するユーティリティ"""

import subprocess
from pathlib import Path
from typing import List, Dict, Optional


class BackgroundVideoProcessor:
    """
    背景動画の処理を担当
    
    機能:
    - concatファイル作成
    - 動画の長さ取得
    - セグメント処理（リサイズ、速度調整、ループ、トリミング）
    """
    
    def __init__(self, project_root: Path, logger):
        """
        Args:
            project_root: プロジェクトのルートパス
            logger: ロガー
        """
        self.project_root = project_root
        self.logger = logger
    
    def create_concat_file(
        self, 
        segments: List[Dict], 
        output_dir: Path
    ) -> Path:
        """
        背景動画のconcatファイルを作成
        
        Args:
            segments: 背景動画セグメント情報
                [
                    {
                        'video_path': 'assets/bg/main.mp4',
                        'duration': 52.0,
                        'track_id': 'main'
                    }
                ]
            output_dir: 出力ディレクトリ
        
        Returns:
            concatファイルのパス
        
        処理フロー:
        1. 各セグメントを処理（リサイズ、速度調整、ループ、トリミング）
        2. 処理済みファイルのパスをconcat.txtに書き込み
        3. concat.txtのパスを返す
        """
        concat_file = output_dir / "bg_concat.txt"
        temp_files = []
        
        self.logger.info(
            f"Creating background video concat file for {len(segments)} segments..."
        )
        
        for i, seg in enumerate(segments):
            video_path = Path(seg['video_path'])
            if not video_path.is_absolute():
                video_path = self.project_root / video_path
            
            # ファイル存在確認
            if not video_path.exists():
                self.logger.error(f"Background video not found: {video_path}")
                continue
            
            duration = seg['duration']
            track_id = seg.get('track_id', '')
            temp_file = output_dir / f"bg_temp_{i}_{track_id}.mp4"
            
            # セグメント処理
            try:
                self.process_segment(
                    video_path=video_path,
                    duration=duration,
                    track_id=track_id,
                    output_path=temp_file
                )
                temp_files.append(temp_file)
            except Exception as e:
                self.logger.error(
                    f"Failed to process background video {video_path.name}: {e}"
                )
                continue
        
        # concatファイル作成
        if not temp_files:
            raise RuntimeError("No background videos were successfully processed")
        
        with open(concat_file, 'w', encoding='utf-8') as f:
            for temp_file in temp_files:
                # Windowsパス対応
                temp_path_str = str(temp_file).replace('\\', '/')
                f.write(f"file '{temp_path_str}'\n")
        
        self.logger.info(
            f"Background concat file created: {concat_file} "
            f"({len(temp_files)} segments)"
        )
        
        return concat_file
    
    def process_segment(
        self,
        video_path: Path,
        duration: float,
        track_id: str,
        output_path: Path
    ) -> None:
        """
        1つのセグメントを処理
        
        処理内容:
        1. リサイズ・クロップ（1920x1080 → 1920x864）
        2. 速度調整（opening/mainは0.5倍速）
        3. ループまたはトリミング（必要な長さに調整）
        
        Args:
            video_path: 元動画のパス
            duration: 必要な長さ（秒）
            track_id: トラックID（opening/main/ending）
            output_path: 出力先
        """
        self.logger.info(
            f"Processing background {video_path.name}: "
            f"{track_id} -> {duration:.1f}s"
        )
        
        # 動画の長さを取得
        video_duration = self.get_video_duration(video_path)
        
        # 速度調整
        if track_id in ['opening', 'main']:
            speed_filter = 'setpts=PTS*2'  # 0.5倍速
            effective_duration = video_duration * 2
            speed_info = "0.5x speed"
        else:
            speed_filter = 'setpts=PTS-STARTPTS'
            effective_duration = video_duration
            speed_info = "1.0x speed"
        
        # ループまたはトリミング
        if duration > effective_duration:
            loop_count = int(duration / effective_duration) + 1
            # 20回を上限とする（処理時間を考慮）
            if loop_count > 20:
                loop_count = 20
                self.logger.warning(
                    f"Loop count capped at 20 (calculated: {int(duration / effective_duration) + 1})"
                )
            
            vf = (
                f"scale=1920:1080,crop=1920:864:0:0,"
                f"{speed_filter},"
                f"loop=loop={loop_count}:size=32767:start=0,"
                f"trim=duration={duration},"
                f"setpts=PTS-STARTPTS"
            )
            loop_info = f"looping {loop_count}x"
            
            self.logger.info(
                f"  Video length: {video_duration:.1f}s "
                f"→ Effective: {effective_duration:.1f}s (speed={speed_info}) "
                f"→ Loops needed: {loop_count}x for {duration:.1f}s"
            )
        else:
            vf = (
                f"scale=1920:1080,crop=1920:864:0:0,"
                f"{speed_filter},"
                f"trim=duration={duration},"
                f"setpts=PTS-STARTPTS"
            )
            loop_info = "trimming"
        
        # ffmpegで処理
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', vf,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-an',
            '-y', str(output_path)
        ]
        
        self.logger.info(f"  {speed_info}, {loop_info}")
        self.logger.info("  Running ffmpeg command (this may take a while)...")
        
        try:
            result = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            self.logger.info(f"  ✓ Background video processed successfully")
        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"  Failed to process background video: {e.stderr}"
            )
            raise
    
    def get_video_duration(self, video_path: Path) -> float:
        """
        動画の長さを取得
        
        Args:
            video_path: 動画ファイルのパス
        
        Returns:
            動画の長さ（秒）
        """
        import json
        
        try:
            # ffprobe を使用して動画ファイルの長さを取得
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                str(video_path)
            ]
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            data = json.loads(result.stdout)
            duration = float(data.get('format', {}).get('duration', 10.0))
            return duration
        except (subprocess.CalledProcessError, ValueError, KeyError) as e:
            self.logger.warning(
                f"Could not get video duration for {video_path.name}: {e}"
            )
            return 10.0  # デフォルト値

