# src/phases/phase_06_bgm.py
"""
Phase 6: BGM選択

台本のセクション雰囲気に基づいてBGMを選択・配置する。
Phase 5 (AI動画) はスキップし、Phase 4の静止画アニメーション結果を使用。
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from pydantic import BaseModel, Field


# ========================================
# データモデル
# ========================================

class BGMTrack(BaseModel):
    """BGM音源情報"""
    track_id: str
    file_path: str
    category: str  # calm, dramatic, hopeful
    duration: float = 0.0  # 音声ファイルから取得（オプション）
    title: str = ""
    artist: Optional[str] = None


class BGMSegment(BaseModel):
    """タイムライン上のBGM配置"""
    track_id: str
    start_time: float
    duration: float
    volume: float = 0.3
    fade_in: float = 2.0
    fade_out: float = 2.0


class BGMSelection(BaseModel):
    """BGM選択結果"""
    subject: str
    segments: List[BGMSegment] = Field(default_factory=list)
    tracks_used: List[BGMTrack] = Field(default_factory=list)


# ========================================
# BGMマネージャー（3曲固定版）
# ========================================

class BGMManager:
    """BGM選択・配置ロジック（3曲固定）"""
    
    def __init__(
        self,
        bgm_library_path: Path,
        fixed_tracks: Dict[str, Dict[str, str]],
        timing: Dict[str, float],
        default_volume: float = 0.3,
        fade_in: float = 2.0,
        fade_out: float = 2.0,
        logger: Optional[logging.Logger] = None,
    ):
        self.bgm_library_path = Path(bgm_library_path)
        self.fixed_tracks = fixed_tracks
        self.timing = timing
        self.default_volume = default_volume
        self.fade_in = fade_in
        self.fade_out = fade_out
        self.logger = logger or logging.getLogger(__name__)
        
        # 3つのBGMを読み込み
        self.tracks = self._load_fixed_tracks()
        
    def _load_fixed_tracks(self) -> Dict[str, BGMTrack]:
        """固定の3曲を読み込み"""
        tracks = {}
        
        for position, info in self.fixed_tracks.items():
            file_path = self.bgm_library_path / info["file"]
            
            if not file_path.exists():
                self.logger.error(f"BGM file not found: {file_path}")
                continue
            
            track = BGMTrack(
                track_id=position,
                file_path=str(file_path),
                category=position,
                title=info["title"],
            )
            tracks[position] = track
            self.logger.info(f"Loaded {position}: {info['title']}")
        
        return tracks
    
    def create_bgm_timeline(
        self,
        audio_duration: float,
    ) -> BGMSelection:
        """3曲固定のBGMタイムラインを作成"""
        segments: List[BGMSegment] = []
        
        # 各BGMの使用時間を計算
        opening_duration = audio_duration * self.timing["opening_ratio"]
        main_duration = audio_duration * self.timing["main_ratio"]
        ending_duration = audio_duration * self.timing["ending_ratio"]
        
        current_time = 0.0
        
        # オープニングBGM
        if "opening" in self.tracks:
            segments.append(BGMSegment(
                track_id="opening",
                start_time=current_time,
                duration=opening_duration,
                volume=self.default_volume,
                fade_in=self.fade_in,
                fade_out=self.fade_out,
            ))
            current_time += opening_duration
            self.logger.info(f"Opening BGM: 0s - {opening_duration:.1f}s")
        
        # メインBGM
        if "main" in self.tracks:
            segments.append(BGMSegment(
                track_id="main",
                start_time=current_time,
                duration=main_duration,
                volume=self.default_volume,
                fade_in=self.fade_in,
                fade_out=self.fade_out,
            ))
            current_time += main_duration
            self.logger.info(f"Main BGM: {current_time - main_duration:.1f}s - {current_time:.1f}s")
        
        # エンディングBGM
        if "ending" in self.tracks:
            segments.append(BGMSegment(
                track_id="ending",
                start_time=current_time,
                duration=ending_duration,
                volume=self.default_volume,
                fade_in=self.fade_in,
                fade_out=self.fade_out,
            ))
            self.logger.info(f"Ending BGM: {current_time:.1f}s - {current_time + ending_duration:.1f}s")
        
        return BGMSelection(
            subject="",  # 後で設定
            segments=segments,
            tracks_used=list(self.tracks.values()),
        )


# ========================================
# Phase 6 実装
# ========================================

class Phase06BGM:
    """Phase 6: BGM選択"""
    
    def __init__(
        self,
        subject: str,
        working_dir: Path,
        config: Dict[str, Any],
        logger: logging.Logger,
    ):
        self.subject = subject
        self.working_dir = Path(working_dir)
        self.config = config
        self.logger = logger
        
        # フェーズディレクトリ
        self.phase_dir = self.working_dir / self.subject / "06_bgm"
        self.phase_dir.mkdir(parents=True, exist_ok=True)
        
        # BGMマネージャー初期化（3曲固定）
        bgm_library = Path(config.get("bgm_library_path", "assets/bgm"))
        fixed_structure = config.get("fixed_bgm_structure", {})
        
        if not fixed_structure.get("enabled", False):
            raise ValueError("Fixed BGM structure is required")
        
        default_settings = config.get("default_settings", {})
        timing = config.get("timing", {
            "opening_ratio": 0.15,
            "main_ratio": 0.70,
            "ending_ratio": 0.15,
        })
        
        self.bgm_manager = BGMManager(
            bgm_library_path=bgm_library,
            fixed_tracks=fixed_structure["tracks"],
            timing=timing,
            default_volume=default_settings.get("volume", 0.3),
            fade_in=default_settings.get("fade_in_duration", 2.0),
            fade_out=default_settings.get("fade_out_duration", 2.0),
            logger=self.logger,
        )
    
    def check_inputs_exist(self) -> bool:
        """Phase 1 (台本) と Phase 2 (音声) の出力を確認"""
        script_path = self.working_dir / self.subject / "01_script" / "script.json"
        audio_path = self.working_dir / self.subject / "02_audio" / "audio_analysis.json"
        
        if not script_path.exists():
            self.logger.error(f"Script not found: {script_path}")
            return False
        
        if not audio_path.exists():
            self.logger.error(f"Audio analysis not found: {audio_path}")
            return False
        
        return True
    
    def check_outputs_exist(self) -> bool:
        """出力が既に存在するかチェック"""
        output_path = self.phase_dir / "bgm_timeline.json"
        return output_path.exists()
    
    def load_script(self) -> Dict[str, Any]:
        """台本を読み込み"""
        script_path = self.working_dir / self.subject / "01_script" / "script.json"
        with open(script_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def load_audio_analysis(self) -> Dict[str, Any]:
        """音声解析結果を読み込み"""
        audio_path = self.working_dir / self.subject / "02_audio" / "audio_analysis.json"
        with open(audio_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def execute(self) -> BGMSelection:
        """Phase 6 実行（3曲固定）"""
        self.logger.info("=== Phase 6: BGM Selection (Fixed 3 Tracks) ===")
        
        # 入力チェック
        if not self.check_inputs_exist():
            raise FileNotFoundError("Required inputs not found")
        
        # 既存出力チェック
        if self.check_outputs_exist():
            self.logger.info("BGM timeline already exists, skipping")
            return self._load_existing_output()
        
        # 音声解析を読み込み（全体の長さを取得）
        audio_analysis = self.load_audio_analysis()
        audio_duration = audio_analysis.get("total_duration", 0.0)
        
        self.logger.info(f"Total audio duration: {audio_duration:.1f}s")
        
        # 3曲固定のBGMタイムライン作成
        bgm_selection = self.bgm_manager.create_bgm_timeline(
            audio_duration=audio_duration,
        )
        
        # subjectを設定
        bgm_selection.subject = self.subject
        
        # 結果を保存
        self._save_output(bgm_selection)
        
        self.logger.info(f"BGM selection complete: {len(bgm_selection.segments)} segments")
        return bgm_selection
    
    def _save_output(self, selection: BGMSelection) -> None:
        """結果を保存"""
        # タイムライン保存
        timeline_path = self.phase_dir / "bgm_timeline.json"
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(selection.model_dump(), f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved BGM timeline: {timeline_path}")
        
        # 使用トラック一覧を保存
        tracks_path = self.phase_dir / "selected_tracks.json"
        tracks_data = [track.model_dump() for track in selection.tracks_used]
        with open(tracks_path, "w", encoding="utf-8") as f:
            json.dump(tracks_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved selected tracks: {tracks_path}")
    
    def _load_existing_output(self) -> BGMSelection:
        """既存の出力を読み込み"""
        timeline_path = self.phase_dir / "bgm_timeline.json"
        with open(timeline_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BGMSelection(**data)


# ========================================
# テスト用エントリポイント
# ========================================

if __name__ == "__main__":
    import sys
    
    # ロギング設定
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    
    # テスト設定
    config = {
        "bgm_library_path": "assets/bgm",
        "atmosphere_mapping": {
            "壮大": "dramatic",
            "静か": "calm",
            "希望": "hopeful",
            "劇的": "dramatic",
            "悲劇的": "dramatic",
        },
        "default_settings": {
            "volume": 0.3,
            "fade_in_duration": 2.0,
            "fade_out_duration": 2.0,
        },
    }
    
    # Phase 6 実行
    phase = Phase06BGM(
        subject="織田信長",
        working_dir=Path("data/working"),
        config=config,
        logger=logger,
    )
    
    try:
        result = phase.execute()
        print(f"\n✓ BGM selection completed!")
        print(f"  Segments: {len(result.segments)}")
        print(f"  Tracks used: {len(result.tracks_used)}")
        
        # セグメント詳細を表示
        print("\nBGM Timeline:")
        for i, seg in enumerate(result.segments, 1):
            print(f"  {i}. {seg.track_id}")
            print(f"     Time: {seg.start_time:.1f}s - {seg.start_time + seg.duration:.1f}s")
            print(f"     Duration: {seg.duration:.1f}s, Volume: {seg.volume:.1%}")
        
    except Exception as e:
        logger.error(f"Phase 6 failed: {e}", exc_info=True)
        sys.exit(1)