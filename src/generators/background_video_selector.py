# src/generators/background_video_selector.py
"""
背景動画選択器

BGMセレクターと同じ構造で、背景動画を選択する。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional


class BackgroundVideoSelector:
    """背景動画選択ロジック"""
    
    def __init__(
        self,
        video_library_path: Path,
        fixed_videos: Dict[str, Dict[str, str]],
        timing_ratios: Dict[str, float],
        transition_duration: float = 1.0,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Args:
            video_library_path: 背景動画ライブラリのパス
            fixed_videos: 固定動画の設定（opening/main/ending）
            timing_ratios: タイミング比率の設定
            transition_duration: トランジション時間（秒）
            logger: ロガー
        """
        self.video_library_path = Path(video_library_path)
        self.fixed_videos = fixed_videos
        self.timing_ratios = timing_ratios
        self.transition_duration = transition_duration
        self.logger = logger or logging.getLogger(__name__)
        
        # 動画ファイルの存在確認
        self.video_paths = self._load_video_paths()
    
    def _load_video_paths(self) -> Dict[str, Path]:
        """固定の3動画のパスを読み込み"""
        video_paths = {}
        
        for position, info in self.fixed_videos.items():
            file_path = self.video_library_path / info["file"]
            
            if not file_path.exists():
                self.logger.warning(f"Background video file not found: {file_path}")
                continue
            
            video_paths[position] = file_path
            self.logger.info(f"Loaded {position}: {info['title']} ({file_path})")
        
        if len(video_paths) < 3:
            self.logger.error(
                f"Expected 3 background videos, but only loaded {len(video_paths)}. "
                "Please check your video files."
            )
        
        return video_paths
    
    def select_videos_for_duration(self, total_duration: float) -> dict:
        """
        全体の長さから opening/main/ending を割り当て
        
        Args:
            total_duration: 動画全体の長さ（秒）
            
        Returns:
            {
                'segments': [
                    {
                        'track_id': 'opening',
                        'video_path': 'assets/background_videos/opening_001.mp4',
                        'start_time': 0.0,
                        'duration': 100.0
                    },
                    # ...
                ]
            }
        """
        segments = []
        current_time = 0.0
        
        # 各セグメントの長さを計算
        opening_duration = total_duration * self.timing_ratios.get("opening", 0.15)
        main_duration = total_duration * self.timing_ratios.get("main", 0.70)
        ending_duration = total_duration * self.timing_ratios.get("ending", 0.15)
        
        # Opening セグメント
        if "opening" in self.video_paths:
            segments.append({
                "track_id": "opening",
                "video_path": str(self.video_paths["opening"]),
                "start_time": current_time,
                "duration": opening_duration,
            })
            self.logger.info(
                f"Opening: {current_time:.1f}s - {current_time + opening_duration:.1f}s "
                f"({opening_duration:.1f}s)"
            )
            current_time += opening_duration
        
        # Main セグメント
        if "main" in self.video_paths:
            segments.append({
                "track_id": "main",
                "video_path": str(self.video_paths["main"]),
                "start_time": current_time,
                "duration": main_duration,
            })
            self.logger.info(
                f"Main: {current_time:.1f}s - {current_time + main_duration:.1f}s "
                f"({main_duration:.1f}s)"
            )
            current_time += main_duration
        
        # Ending セグメント
        if "ending" in self.video_paths:
            segments.append({
                "track_id": "ending",
                "video_path": str(self.video_paths["ending"]),
                "start_time": current_time,
                "duration": ending_duration,
            })
            self.logger.info(
                f"Ending: {current_time:.1f}s - {current_time + ending_duration:.1f}s "
                f"({ending_duration:.1f}s)"
            )
            current_time += ending_duration
        
        return {
            "segments": segments,
            "total_duration": total_duration,
        }
