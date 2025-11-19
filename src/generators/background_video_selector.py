# src/generators/background_video_selector.py
"""
背景動画選択器

BGMセレクターと同じ構造で、台本のbgm_suggestionに基づいて背景動画を選択する。
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Dict, List, Optional


class BackgroundVideoSelector:
    """背景動画選択ロジック（台本ベース）"""
    
    def __init__(
        self,
        video_library_path: Path,
        transition_duration: float = 1.0,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Args:
            video_library_path: 背景動画ライブラリのパス
            transition_duration: トランジション時間（秒）
            logger: ロガー
        """
        self.video_library_path = Path(video_library_path)
        self.transition_duration = transition_duration
        self.logger = logger or logging.getLogger(__name__)
        
        # 各カテゴリの動画を読み込み
        self.videos = self._load_videos()
    
    def _load_videos(self) -> Dict[str, List[Path]]:
        """
        各カテゴリ（opening/main/ending）の動画を読み込み
        
        Returns:
            {
                'opening': [Path('opening/video1.mp4'), ...],
                'main': [Path('main/video1.mp4'), ...],
                'ending': [Path('ending/video1.mp4'), ...]
            }
        """
        videos = {
            'opening': [],
            'main': [],
            'ending': []
        }
        
        for category in ['opening', 'main', 'ending']:
            category_dir = self.video_library_path / category
            
            if not category_dir.exists():
                self.logger.warning(f"Background video directory not found: {category_dir}")
                continue
            
            # mp4ファイルを取得
            video_files = sorted(category_dir.glob("*.mp4"))
            
            if not video_files:
                self.logger.warning(f"No video files found in: {category_dir}")
                continue
            
            videos[category] = video_files
            self.logger.info(f"Loaded {len(video_files)} videos for {category}")
        
        return videos
    
    def select_videos_for_sections(self, sections: List) -> dict:
        """
        台本のbgm_suggestionに基づいて背景動画タイムラインを作成
        
        Args:
            sections: 台本のセクションリスト（ScriptSectionオブジェクト）
            
        Returns:
            {
                'segments': [
                    {
                        'track_id': 'opening',
                        'video_path': 'assets/background_videos/opening/video1.mp4',
                        'start_time': 0.0,
                        'duration': 100.0
                    },
                    # ...
                ]
            }
        """
        segments = []
        current_time = 0.0
        previous_type = None
        
        # 各カテゴリで使用する動画をランダムに選択（セッション全体で固定）
        selected_videos = {}
        for category in ['opening', 'main', 'ending']:
            if self.videos[category]:
                selected_videos[category] = random.choice(self.videos[category])
                self.logger.info(f"Selected {category} video: {selected_videos[category].name}")
            else:
                self.logger.warning(f"No videos available for {category}")
        
        for i, section in enumerate(sections):
            section_duration = section.estimated_duration
            bgm_type = section.bgm_suggestion.value  # BGMType enum → str
            
            # 背景動画が切り替わる場合
            if previous_type and previous_type != bgm_type:
                self.logger.info(
                    f"Background video switch at {current_time:.1f}s: "
                    f"{previous_type} → {bgm_type}"
                )
            
            # 対応する背景動画を取得
            if bgm_type in selected_videos:
                video_path = selected_videos[bgm_type]
                
                segment = {
                    "track_id": bgm_type,
                    "video_path": str(video_path),
                    "start_time": current_time,
                    "duration": section_duration,
                }
                segments.append(segment)
                
                self.logger.info(
                    f"Section {section.section_id}: {section.title} "
                    f"→ {bgm_type} video ({current_time:.1f}s - {current_time + section_duration:.1f}s)"
                )
            else:
                self.logger.warning(
                    f"No video available for {bgm_type} in section {section.section_id}"
                )
            
            current_time += section_duration
            previous_type = bgm_type
        
        return {
            "segments": segments,
            "total_duration": current_time,
        }
