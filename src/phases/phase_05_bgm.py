# src/phases/phase_06_bgm.py
"""
Phase 6: BGM選択

台本のbgm_suggestionに基づいてBGMを配置する。
起承転結の3曲構成（opening/main/ending）を使用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

# プロジェクトルートをパスに追加
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.core.phase_base import PhaseBase
from src.core.models import (
    BGMTrack,
    BGMSegment,
    BGMSelection,
    BGMType,
    BGMCategory,
    VideoScript,
    ScriptSection
)
from src.core.config_manager import ConfigManager
from src.core.exceptions import PhaseExecutionError, PhaseValidationError


class BGMManager:
    """BGM配置ロジック（台本ベース）"""
    
    def __init__(
        self,
        bgm_library_path: Path,
        fixed_tracks: Dict[str, Dict[str, str]],
        default_volume: float = 0.3,
        fade_in: float = 2.0,
        fade_out: float = 2.0,
        crossfade_duration: float = 3.0,
        logger: Optional[logging.Logger] = None,
    ):
        self.bgm_library_path = Path(bgm_library_path)
        self.fixed_tracks = fixed_tracks
        self.default_volume = default_volume
        self.fade_in = fade_in
        self.fade_out = fade_out
        self.crossfade_duration = crossfade_duration
        self.logger = logger or logging.getLogger(__name__)
        
        # 3つのBGMを読み込み
        self.tracks = self._load_fixed_tracks()
    
    def _load_fixed_tracks(self) -> Dict[str, BGMTrack]:
        """固定の3曲を読み込み"""
        tracks = {}
        
        for position, info in self.fixed_tracks.items():
            file_path = self.bgm_library_path / info["file"]
            
            if not file_path.exists():
                self.logger.warning(f"BGM file not found: {file_path}")
                continue
            
            # BGMTypeに変換（opening/main/ending）
            try:
                bgm_type = BGMType(position)
            except ValueError:
                self.logger.warning(f"Invalid BGM position: {position}")
                continue
            
            category_value = info.get("category")
            if category_value:
                try:
                    bgm_category = BGMCategory(category_value)
                except ValueError:
                    self.logger.warning(
                        f"Invalid BGM category '{category_value}' for {position}. "
                        "Falling back to 'dramatic'."
                    )
                    bgm_category = BGMCategory.DRAMATIC
            else:
                bgm_category = BGMCategory.DRAMATIC

            track = BGMTrack(
                track_id=position,
                file_path=str(file_path),
                category=bgm_category,
                duration=0.0,  # 実際の長さは後で取得可能
                title=info["title"],
            )
            tracks[position] = track
            self.logger.info(f"Loaded {position}: {info['title']}")
        
        if len(tracks) < 3:
            self.logger.error(
                f"Expected 3 BGM tracks, but only loaded {len(tracks)}. "
                "Please check your BGM files."
            )
        
        return tracks
    
    def create_bgm_timeline(
        self,
        sections: List[ScriptSection],
    ) -> BGMSelection:
        """
        台本のbgm_suggestionに基づいてBGMタイムラインを作成
        
        Args:
            sections: 台本のセクションリスト
            
        Returns:
            BGMSelection: BGM配置結果
        """
        segments: List[BGMSegment] = []
        current_time = 0.0
        previous_bgm: Optional[BGMType] = None
        
        for i, section in enumerate(sections):
            section_duration = section.estimated_duration
            bgm_type = section.bgm_suggestion
            
            # BGMが切り替わる場合
            if previous_bgm and previous_bgm != bgm_type:
                # 前のセグメントにクロスフェード用のフェードアウトを設定
                if segments:
                    segments[-1].fade_out = self.crossfade_duration
                
                self.logger.info(
                    f"BGM switch at {current_time:.1f}s: "
                    f"{previous_bgm.value} → {bgm_type.value}"
                )
            
            # フェードイン判定
            # - 最初のセクション、または
            # - BGMが切り替わった場合
            fade_in_duration = self.fade_in if (i == 0 or previous_bgm != bgm_type) else 0
            
            # セグメント作成
            segment = BGMSegment(
                track_id=bgm_type.value,
                start_time=current_time,
                duration=section_duration,
                volume=self.default_volume,
                fade_in=fade_in_duration,
                fade_out=self.fade_out,
            )
            segments.append(segment)
            
            self.logger.info(
                f"Section {section.section_id}: {section.title} "
                f"→ {bgm_type.value} ({current_time:.1f}s - {current_time + section_duration:.1f}s)"
            )
            
            current_time += section_duration
            previous_bgm = bgm_type
        
        return BGMSelection(
            subject="",  # Phase実行時に設定
            segments=segments,
            tracks_used=list(self.tracks.values()),
        )


class Phase05BGM(PhaseBase):
    """Phase 5: BGM選択"""
    
    def get_phase_number(self) -> int:
        return 5
    
    def get_phase_name(self) -> str:
        return "BGM Selection"
    
    def check_inputs_exist(self) -> bool:
        """Phase 1 (台本) の出力を確認"""
        script_path = self.working_dir / "01_script" / "script.json"

        if not script_path.exists():
            self.logger.error(f"Script not found: {script_path}")
            return False

        return True
    
    def check_outputs_exist(self) -> bool:
        """出力が既に存在するかチェック"""
        timeline_path = self.phase_dir / "bgm_timeline.json"
        return timeline_path.exists()
    
    def get_output_paths(self) -> list[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / "bgm_timeline.json",
            self.phase_dir / "selected_tracks.json"
        ]
    
    def execute_phase(self) -> BGMSelection:
        """
        Phase 6 実行（台本ベースBGM選択）
        
        Returns:
            BGMSelection: BGM配置結果
            
        Raises:
            PhaseExecutionError: 実行失敗時
        """
        self.logger.info("Creating BGM timeline based on script suggestions")
        
        try:
            # BGMマネージャー初期化
            bgm_manager = self._create_bgm_manager()
            
            # 台本を読み込み
            script = self._load_script()
            
            self.logger.info(
                f"Processing {len(script.sections)} sections "
                f"(total {script.total_estimated_duration:.0f}s)"
            )
            
            # 台本のbgm_suggestionに基づいてBGMタイムライン作成
            bgm_selection = bgm_manager.create_bgm_timeline(
                sections=script.sections,
            )
            
            # subjectを設定
            bgm_selection.subject = self.subject
            
            # 結果を保存
            self._save_output(bgm_selection)
            
            # 統計情報を出力
            self._log_statistics(bgm_selection)
            
            return bgm_selection
            
        except Exception as e:
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"BGM selection failed: {e}"
            ) from e
    
    def validate_output(self, output: BGMSelection) -> bool:
        """
        BGM配置結果をバリデーション
        
        Args:
            output: BGM配置結果
            
        Returns:
            バリデーション成功なら True
            
        Raises:
            PhaseValidationError: バリデーション失敗時
        """
        # セグメント数チェック
        if len(output.segments) == 0:
            raise PhaseValidationError(
                self.get_phase_number(),
                "No BGM segments created"
            )
        
        # 使用トラック数チェック
        if len(output.tracks_used) != 3:
            self.logger.warning(
                f"Expected 3 BGM tracks, but got {len(output.tracks_used)}"
            )
        
        # タイムラインの整合性チェック
        for i, segment in enumerate(output.segments):
            # 時間が負でないか
            if segment.start_time < 0:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Segment {i} has negative start_time: {segment.start_time}"
                )
            
            # 時間長が正か
            if segment.duration <= 0:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Segment {i} has invalid duration: {segment.duration}"
                )
            
            # 音量が範囲内か
            if not 0 <= segment.volume <= 1:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Segment {i} has invalid volume: {segment.volume}"
                )
        
        self.logger.info("BGM selection validation passed")
        return True
    
    # ========================================
    # 内部メソッド
    # ========================================
    
    def _create_bgm_manager(self) -> BGMManager:
        """BGMマネージャーを作成"""
        bgm_library = Path(self.phase_config.get("bgm_library_path", "assets/bgm"))
        fixed_structure = self.phase_config.get("fixed_bgm_structure", {})
        
        if not fixed_structure.get("enabled", False):
            raise ValueError(
                "fixed_bgm_structure must be enabled in config. "
                "Please check config/phases/bgm_selection.yaml"
            )
        
        default_settings = self.phase_config.get("default_settings", {})
        transition_settings = self.phase_config.get("transition_between_tracks", {})
        
        return BGMManager(
            bgm_library_path=bgm_library,
            fixed_tracks=fixed_structure["tracks"],
            default_volume=default_settings.get("volume", 0.3),
            fade_in=default_settings.get("fade_in_duration", 2.0),
            fade_out=default_settings.get("fade_out_duration", 2.0),
            crossfade_duration=transition_settings.get("duration", 3.0),
            logger=self.logger,
        )
    
    def _load_script(self) -> VideoScript:
        """台本を読み込み"""
        script_path = self.working_dir / "01_script" / "script.json"

        with open(script_path, "r", encoding="utf-8") as f:
            script_data = json.load(f)
        
        # Pydanticモデルに変換
        return VideoScript(**script_data)
    
    def _save_output(self, selection: BGMSelection) -> None:
        """結果を保存"""
        # タイムライン保存
        timeline_path = self.phase_dir / "bgm_timeline.json"
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(
                selection.model_dump(mode='json'),
                f,
                indent=2,
                ensure_ascii=False
            )
        
        self.logger.info(f"Saved BGM timeline: {timeline_path}")
        
        # 使用トラック一覧を保存
        tracks_path = self.phase_dir / "selected_tracks.json"
        tracks_data = [track.model_dump(mode='json') for track in selection.tracks_used]
        with open(tracks_path, "w", encoding="utf-8") as f:
            json.dump(tracks_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved selected tracks: {tracks_path}")
    
    def _log_statistics(self, selection: BGMSelection):
        """統計情報をログ出力"""
        # BGMごとの使用時間を集計
        bgm_usage = {}
        for segment in selection.segments:
            track_id = segment.track_id
            bgm_usage[track_id] = bgm_usage.get(track_id, 0) + segment.duration
        
        self.logger.info("=" * 60)
        self.logger.info("BGM Selection Statistics")
        self.logger.info("=" * 60)
        self.logger.info(f"Total segments: {len(selection.segments)}")
        
        for track_id, duration in bgm_usage.items():
            percentage = (duration / sum(bgm_usage.values())) * 100
            self.logger.info(f"  {track_id}: {duration:.1f}s ({percentage:.1f}%)")
        
        # BGM切り替え回数を数える
        switches = 0
        prev_id = None
        for segment in selection.segments:
            if prev_id and prev_id != segment.track_id:
                switches += 1
            prev_id = segment.track_id
        
        self.logger.info(f"BGM switches: {switches}")
        self.logger.info("=" * 60)
    
    def load_bgm_selection(self) -> Optional[BGMSelection]:
        """
        保存済みのBGM選択結果を読み込み
        
        Returns:
            BGMSelection または None（存在しない場合）
        """
        timeline_path = self.phase_dir / "bgm_timeline.json"
        
        if not timeline_path.exists():
            return None
        
        try:
            with open(timeline_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            selection = BGMSelection(**data)
            self.logger.info(f"BGM selection loaded: {timeline_path}")
            return selection
            
        except Exception as e:
            self.logger.error(f"Failed to load BGM selection: {e}")
            return None


# ========================================
# スタンドアロン実行用
# ========================================

def main():
    """テスト実行"""
    from src.utils.logger import setup_logger
    
    # 設定とロガーを初期化
    config = ConfigManager()
    logger = setup_logger(
        name="phase_05_test",
        log_dir=config.get_path("logs_dir"),
        level="DEBUG"
    )
    
    # Phase 5を実行
    subject = "織田信長"
    
    phase = Phase05BGM(
        subject=subject,
        config=config,
        logger=logger
    )
    
    # 実行
    execution = phase.run(skip_if_exists=False)
    
    # 結果表示
    print(f"\n{'='*60}")
    print(f"Phase 5 Execution Result")
    print(f"{'='*60}")
    print(f"Status: {execution.status}")
    print(f"Duration: {execution.duration_seconds:.2f}s")
    
    if execution.status.value == "completed":
        print(f"\nOutput files:")
        for path in execution.output_paths:
            print(f"  - {path}")
        
        # BGM選択結果を読み込んで表示
        selection = phase.load_bgm_selection()
        if selection:
            print(f"\nBGM Selection:")
            print(f"  Segments: {len(selection.segments)}")
            print(f"  Tracks used: {len(selection.tracks_used)}")
            
            # タイムライン表示
            print(f"\nTimeline:")
            for seg in selection.segments:
                print(
                    f"  {seg.start_time:6.1f}s - {seg.start_time + seg.duration:6.1f}s: "
                    f"{seg.track_id} (vol: {seg.volume:.0%})"
                )
    else:
        print(f"\nError: {execution.error_message}")


if __name__ == "__main__":
    main()