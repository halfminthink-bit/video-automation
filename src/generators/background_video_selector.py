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
        selection_mode: str = "random",
        transition_duration: float = 1.0,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Args:
            video_library_path: 背景動画ライブラリのパス
            selection_mode: 選択モード（random, sequential）
            transition_duration: トランジション時間（秒）
            logger: ロガー
        """
        self.video_library_path = Path(video_library_path)
        self.selection_mode = selection_mode
        self.transition_duration = transition_duration
        self.logger = logger or logging.getLogger(__name__)
        
        # 各カテゴリの動画を読み込み
        self.videos = self._load_videos()
        
        # sequential モード用のインデックス
        self._sequential_indices = {
            'opening': 0,
            'main': 0,
            'ending': 0
        }
    
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
        
        # 各カテゴリで使用する動画を選択（セッション全体で固定）
        selected_videos = {}
        for category in ['opening', 'main', 'ending']:
            if self.videos[category]:
                if self.selection_mode == "random":
                    selected_videos[category] = random.choice(self.videos[category])
                elif self.selection_mode == "sequential":
                    # 順番に選択（インデックスを循環）
                    idx = self._sequential_indices[category] % len(self.videos[category])
                    selected_videos[category] = self.videos[category][idx]
                    self._sequential_indices[category] += 1
                else:
                    # デフォルト: 最初の動画
                    selected_videos[category] = self.videos[category][0]
                
                self.logger.info(f"Selected {category} video: {selected_videos[category].name} (mode: {self.selection_mode})")
            else:
                self.logger.warning(f"No videos available for {category}")
        
        for i, section in enumerate(sections):
            # 辞書またはオブジェクトの両方に対応
            if isinstance(section, dict):
                section_duration = section.get('estimated_duration', 0.0)
                bgm_type_raw = section.get('bgm_suggestion', 'main')
                section_id = section.get('section_id', i + 1)
                section_title = section.get('title', f'Section {section_id}')
                
                # bgm_suggestionが文字列の場合
                if isinstance(bgm_type_raw, str):
                    bgm_type = bgm_type_raw
                else:
                    # BGMType enum の場合
                    bgm_type = bgm_type_raw.value if hasattr(bgm_type_raw, 'value') else str(bgm_type_raw)
            else:
                # ScriptSectionオブジェクトの場合（既存の処理）
                section_duration = section.estimated_duration
                bgm_type = section.bgm_suggestion.value if hasattr(section.bgm_suggestion, 'value') else str(section.bgm_suggestion)
                section_id = section.section_id
                section_title = section.title
            
            # 常にmainカテゴリの動画を使用
            if 'main' in selected_videos:
                video_path = selected_videos['main']
                
                segment = {
                    "track_id": "main",  # 常にmainとして設定
                    "video_path": str(video_path),
                    "start_time": current_time,
                    "duration": section_duration,
                }
                segments.append(segment)
                
                self.logger.info(
                    f"Section {section_id}: {section_title} "
                    f"→ main video (always) ({current_time:.1f}s - {current_time + section_duration:.1f}s)"
                )
            else:
                self.logger.warning(
                    f"No main video available for section {section_id}"
                )
            
            current_time += section_duration
            previous_type = bgm_type
        
        return {
            "segments": segments,
            "total_duration": current_time,
        }
