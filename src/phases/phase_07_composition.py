"""
Phase 7: 動画統合（Video Composition）
Phase 1-6で生成した全ての素材を統合し、完成動画を生成する
"""

import json
import platform
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

try:
    from moviepy import (
        VideoFileClip,
        AudioFileClip,
        CompositeVideoClip,
        concatenate_videoclips,
        concatenate_audioclips,
        TextClip,
        CompositeAudioClip,
        ColorClip,
        ImageClip,
        afx,
    )
    
    MOVIEPY_AVAILABLE = True
    MOVIEPY_IMPORT_ERROR = None
except ImportError as e:
    MOVIEPY_AVAILABLE = False
    MOVIEPY_IMPORT_ERROR = str(e)
    # 型ヒント用のダミー（実行時には使用されない）
    if TYPE_CHECKING:
        from moviepy.editor import VideoFileClip, AudioFileClip

from ..core.phase_base import PhaseBase
from ..core.config_manager import ConfigManager
from ..core.models import VideoComposition, VideoTimeline, TimelineClip, SubtitleEntry


class Phase07Composition(PhaseBase):
    """Phase 7: 動画統合"""
    
    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger,
        use_legacy: bool = False
    ):
        super().__init__(subject, config, logger)

        if not MOVIEPY_AVAILABLE:
            error_msg = "MoviePy is required. Install with: pip install moviepy"
            if MOVIEPY_IMPORT_ERROR:
                error_msg += f"\n\nImport error details: {MOVIEPY_IMPORT_ERROR}"
            raise ImportError(error_msg)

        self.use_legacy = use_legacy
        self.phase_config = config.get_phase_config(7)

        # Legacy版を使う場合は、legacy設定を読み込む
        if self.use_legacy:
            self.logger.info("🔄 Using legacy (moviepy) mode")
            legacy_config_path = Path(__file__).parent.parent.parent / "config/phases/video_composition_legacy.yaml"
            if legacy_config_path.exists():
                import yaml
                with open(legacy_config_path, 'r', encoding='utf-8') as f:
                    legacy_config = yaml.safe_load(f)
                # phase_configを上書き
                self.phase_config.update(legacy_config)
                self.logger.info(f"✓ Loaded legacy config: {legacy_config_path}")

        # 出力設定
        output_config = self.phase_config.get("output", {})
        self.resolution = tuple(output_config.get("resolution", [1920, 1080]))
        self.fps = output_config.get("fps", 30)
        self.codec = output_config.get("codec", "libx264")
        self.bitrate = output_config.get("bitrate", "5000k")

        # クリップループ設定
        clip_config = self.phase_config.get("clip_loop", {})
        self.clip_loop_enabled = clip_config.get("enabled", True)
        self.crossfade_duration = clip_config.get("crossfade_duration", 0.5)
        self.min_clip_duration = clip_config.get("min_clip_duration", 4.0)

        # BGM設定
        bgm_config = self.phase_config.get("bgm", {})
        self.bgm_volume = bgm_config.get("volume", 0.1)  # 10%に下げる
        self.bgm_fade_in = bgm_config.get("fade_in", 3.0)  # フェードイン3秒
        self.bgm_fade_out = bgm_config.get("fade_out", 3.0)  # フェードアウト3秒
        self.bgm_crossfade = bgm_config.get("crossfade", 2.0)  # セグメント間クロスフェード2秒

        # 字幕設定
        subtitle_config = self.phase_config.get("subtitle", {})
        self.subtitle_font = subtitle_config.get("font_family", "Arial")
        self.subtitle_size = subtitle_config.get("font_size", 60)
        self.subtitle_color = subtitle_config.get("color", "white")
        self.subtitle_position = subtitle_config.get("position", "bottom")
        self.subtitle_margin = subtitle_config.get("margin_bottom", 150)

        # 二分割レイアウト設定
        self.split_config = self.phase_config.get("split_layout", {})
        self.split_enabled = self.split_config.get("enabled", False)

        # パフォーマンス設定
        perf_config = self.phase_config.get("performance", {})
        self.use_ffmpeg_direct = perf_config.get("use_ffmpeg_direct", False)
        self.encode_preset = perf_config.get("preset", "faster")
        self.parallel_processing = perf_config.get("parallel_processing", True)
        self.threads = perf_config.get("threads", 0)
    
    def get_phase_number(self) -> int:
        return 7
    
    def get_phase_name(self) -> str:
        return "Video Composition"
    
    def get_phase_directory(self) -> Path:
        return self.working_dir / "07_composition"
    
    def check_inputs_exist(self) -> bool:
        """
        必要な入力ファイルの存在確認

        Phase04無効化により、Phase03の画像を直接使用
        """
        required_files = []

        # Phase 1: 台本
        script_path = self.working_dir / "01_script" / "script.json"
        required_files.append(("Script", script_path))

        # Phase 2: 音声
        audio_path = self.working_dir / "02_audio" / "narration_full.mp3"
        required_files.append(("Audio", audio_path))

        # Phase 3: 画像（Phase04無効化により直接使用）
        images_dir = self.working_dir / "03_images"
        if not images_dir.exists():
            self.logger.error(f"Images directory not found: {images_dir}")
            return False

        # 画像の存在確認（resized または generated ディレクトリ）
        resized_dir = images_dir / "resized"
        generated_dir = images_dir / "generated"
        classified_json = images_dir / "classified.json"

        has_images = False
        if resized_dir.exists() and list(resized_dir.glob("*.png")):
            has_images = True
            self.logger.info(f"Found images in: {resized_dir}")
        elif generated_dir.exists() and list(generated_dir.glob("*.png")):
            has_images = True
            self.logger.info(f"Found images in: {generated_dir}")
        elif classified_json.exists():
            has_images = True
            self.logger.info(f"Found image metadata: {classified_json}")

        if not has_images:
            self.logger.error(f"No images found in: {images_dir}")
            return False

        # Phase 6: 字幕
        subtitle_path = self.working_dir / "06_subtitles" / "subtitle_timing.json"
        required_files.append(("Subtitles", subtitle_path))

        # 各ファイルの存在確認
        all_exist = True
        for name, path in required_files:
            if not path.exists():
                self.logger.error(f"{name} not found: {path}")
                all_exist = False

        return all_exist
    
    def check_outputs_exist(self) -> bool:
        """出力ファイルの存在確認"""
        output_dir = self.config.get("paths", {}).get("output_dir", "data/output")
        video_path = Path(output_dir) / "videos" / f"{self.subject}.mp4"
        return video_path.exists()
    
    def execute_phase(self) -> VideoComposition:
        """動画統合の実行"""
        self.logger.info(f"Starting video composition for: {self.subject}")
        render_start = time.time()

        # Legacy版の分岐
        if self.use_legacy:
            self.logger.info("🎬 Executing legacy moviepy composition")
            return self._execute_legacy()

        # ffmpeg直接統合モードの分岐
        if self.use_ffmpeg_direct:
            self.logger.info("🔥 Using ffmpeg direct integration (high-speed mode)")
            return self._execute_ffmpeg_direct()
        else:
            self.logger.info("Using MoviePy integration (standard mode)")
            return self._execute_moviepy()

    def _execute_moviepy(self) -> VideoComposition:
        """MoviePyを使用した動画統合（従来の方法）"""
        render_start = time.time()

        try:
            # 1. データ読み込み
            self.logger.info("Loading data...")
            script = self._load_script()
            audio_path = self._get_audio_path()
            animated_clips = self._load_animated_clips()
            subtitles = self._load_subtitles()
            bgm_data = self._load_bgm()
            
            # 2. 音声の長さを取得
            audio_clip = AudioFileClip(str(audio_path))
            total_duration = audio_clip.duration
            self.logger.info(f"Total audio duration: {total_duration:.1f}s")

            # 3. 動画生成（二分割レイアウト or 全画面）
            if self.split_enabled:
                self.logger.info("Creating split layout video (subtitle | video)...")

                # 二分割レイアウトで動画生成
                final_video = self._create_split_layout_video(
                    animated_clips=animated_clips,
                    subtitles=subtitles,
                    total_duration=total_duration
                )

                # 音声を追加
                self.logger.info("Adding audio track...")
                final_video = final_video.with_audio(audio_clip)

                # BGMを追加
                if bgm_data:
                    self.logger.info("Adding BGM...")
                    final_video = self._add_bgm(final_video, bgm_data)

            else:
                # 既存の処理（全画面動画）
                self.logger.info("Creating full-screen video with bottom subtitles...")

                # 3. 映像クリップを作成
                video_clips = self._create_video_clips(animated_clips, total_duration)

                # 4. 映像を連結
                final_video = self._concatenate_clips(video_clips, total_duration)

                # 5. 音声を追加
                final_video = final_video.with_audio(audio_clip)

                # 6. BGMを追加（オプション）
                if bgm_data:
                    final_video = self._add_bgm(final_video, bgm_data)

                # 7. 字幕を追加
                final_video = self._add_subtitles(final_video, subtitles)
            
            # 8. 動画をレンダリング
            self.logger.info("Rendering final video...")
            output_path = self._render_video(final_video)
            
            # 9. サムネイル生成
            self.logger.info("Generating thumbnail...")
            thumbnail_path = self._generate_thumbnail(final_video)
            
            # 10. メタデータ保存
            render_time = time.time() - render_start
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            
            composition = VideoComposition(
                subject=self.subject,
                output_video_path=str(output_path),
                thumbnail_path=str(thumbnail_path),
                metadata_path=str(self.phase_dir / "metadata.json"),
                timeline=VideoTimeline(
                    subject=self.subject,
                    clips=[],  # 簡略化
                    audio_path=str(audio_path),
                    bgm_segments=[],
                    subtitles=subtitles,
                    total_duration=total_duration,
                    resolution=self.resolution,
                    fps=self.fps
                ),
                render_time_seconds=render_time,
                file_size_mb=file_size_mb,
                completed_at=datetime.now()
            )
            
            self._save_metadata(composition)
            
            # メモリ解放
            final_video.close()
            audio_clip.close()
            
            self.logger.info(
                f"✓ Video composition complete: {file_size_mb:.1f}MB in {render_time:.1f}s"
            )
            
            return composition
            
        except Exception as e:
            self.logger.error(f"Video composition failed: {e}", exc_info=True)
            raise
    
    def validate_output(self, output: VideoComposition) -> bool:
        """出力のバリデーション"""
        video_path = Path(output.output_video_path)
        
        if not video_path.exists():
            self.logger.error(f"Output video not found: {video_path}")
            return False
        
        if video_path.stat().st_size == 0:
            self.logger.error("Output video is empty")
            return False
        
        self.logger.info("Output validation passed")
        return True

    def _execute_legacy(self) -> VideoComposition:
        """
        Legacy版の実行

        phase_07_composition_legacy.py の実装をそのまま実行
        """
        import importlib.util

        legacy_module_path = Path(__file__).parent / "phase_07_composition_legacy.py"

        if not legacy_module_path.exists():
            raise FileNotFoundError(
                f"Legacy module not found: {legacy_module_path}\n"
                "Please ensure phase_07_composition_legacy.py exists in the same directory."
            )

        # legacy版モジュールをインポート
        spec = importlib.util.spec_from_file_location(
            "phase_07_composition_legacy",
            legacy_module_path
        )
        legacy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy_module)

        # legacy版のクラスをインスタンス化
        LegacyPhase07 = legacy_module.Phase07Composition
        legacy_phase = LegacyPhase07(
            subject=self.subject,
            config=self.config,
            logger=self.logger
        )

        # legacy版のexecute_phaseを実行
        self.logger.info("Executing legacy Phase07Composition.execute_phase()")
        return legacy_phase.execute_phase()

    def _load_script(self) -> dict:
        """台本データを読み込み"""
        script_path = self.working_dir / "01_script" / "script.json"
        with open(script_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_audio_path(self) -> Path:
        """音声ファイルパスを取得"""
        return self.working_dir / "02_audio" / "narration_full.mp3"
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        音声ファイルの長さを取得
        
        Args:
            audio_path: 音声ファイルのパス
        
        Returns:
            音声の長さ（秒）
        """
        try:
            from moviepy import AudioFileClip
            audio_clip = AudioFileClip(str(audio_path))
            duration = audio_clip.duration
            audio_clip.close()
            self.logger.debug(f"Audio duration: {duration:.2f}s")
            return duration
        except Exception as e:
            self.logger.warning(f"Failed to get audio duration from file: {e}")
            # フォールバック: audio_timing.jsonから合計時間を計算
            audio_timing = self._load_audio_timing()
            if isinstance(audio_timing, list):
                total_duration = 0.0
                for section in audio_timing:
                    char_end_times = section.get('character_end_times_seconds', [])
                    if char_end_times:
                        total_duration = max(total_duration, char_end_times[-1])
                if total_duration > 0:
                    self.logger.info(f"Audio duration from timing data: {total_duration:.2f}s")
                    return total_duration
            # 最後のフォールバック: デフォルト値
            self.logger.warning("Using default audio duration: 420.0s")
            return 420.0
    
    def _load_animated_clips(self) -> List[Path]:
        """アニメ化動画クリップを読み込み（セクション順を保持）"""
        animated_dir = self.working_dir / "04_animated"
        plan_path = animated_dir / "animation_plan.json"

        # animation_plan.jsonが存在する場合は、そこに記録された順序（= セクション順）を使用
        if plan_path.exists():
            try:
                with open(plan_path, 'r', encoding='utf-8') as f:
                    plan = json.load(f)

                clips = [Path(clip['output_path']) for clip in plan.get('animated_clips', [])]

                # ファイルの存在確認
                missing_clips = [clip for clip in clips if not clip.exists()]
                if missing_clips:
                    self.logger.warning(f"{len(missing_clips)} clips not found, falling back to file scan")
                    raise FileNotFoundError("Some clips are missing")

                self.logger.info(f"Loaded {len(clips)} clips from animation_plan.json (section order preserved)")
                return clips

            except Exception as e:
                self.logger.warning(f"Failed to load animation_plan.json: {e}")
                self.logger.warning("Falling back to filename sort (may not preserve section order)")
        else:
            self.logger.warning("animation_plan.json not found")
            self.logger.warning("Falling back to filename sort (may not preserve section order)")

        # フォールバック: 従来のファイル名順ソート
        clips = sorted(animated_dir.glob("*.mp4"))
        self.logger.info(f"Found {len(clips)} animated clips (sorted by filename)")
        return clips
    
    def _load_subtitles(self) -> List[SubtitleEntry]:
        """字幕データを読み込み"""
        subtitle_path = self.working_dir / "06_subtitles" / "subtitle_timing.json"

        if not subtitle_path.exists():
            self.logger.warning("Subtitle data not found, using empty list")
            return []

        with open(subtitle_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        subtitles = []
        for item in data.get("subtitles", []):
            subtitle = SubtitleEntry(
                index=item["index"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                text_line1=item["text_line1"],
                text_line2=item.get("text_line2", ""),
                text_line3=item.get("text_line3", "")
            )
            subtitles.append(subtitle)

        self.logger.info(f"Loaded {len(subtitles)} subtitles")
        return subtitles
    
    def _load_audio_timing(self) -> Optional[dict]:
        """Phase 2の音声タイミングデータを読み込み"""
        audio_timing_path = self.working_dir / "02_audio" / "audio_timing.json"
        
        if not audio_timing_path.exists():
            self.logger.warning(f"audio_timing.json not found: {audio_timing_path}")
            return None
        
        try:
            with open(audio_timing_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Phase 2がリスト形式で保存している場合、辞書形式に変換
            if isinstance(data, list):
                self.logger.debug("Converting audio_timing.json from list to dict format")
                data = {'sections': data}
            
            sections = data.get('sections', [])
            self.logger.info(f"✓ Loaded audio timing data with {len(sections)} sections")
            return data
        except Exception as e:
            self.logger.error(f"Failed to load audio_timing.json: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def _get_section_duration(self, section_id: int, audio_timing: Optional[dict]) -> float:
        """
        セクションの実際の音声長を取得
        
        Args:
            section_id: セクションID
            audio_timing: audio_timing.jsonの内容（リスト形式または辞書形式）
        """
        if not audio_timing:
            # フォールバック: 音声ファイルから直接取得
            audio_file = self.working_dir / "02_audio" / "sections" / f"section_{section_id:02d}.mp3"
            if audio_file.exists():
                try:
                    audio_clip = AudioFileClip(str(audio_file))
                    duration = audio_clip.duration
                    audio_clip.close()
                    self.logger.debug(f"Section {section_id} duration from audio file: {duration:.2f}s")
                    return duration
                except Exception as e:
                    self.logger.warning(f"Failed to get duration from {audio_file}: {e}")
            
            # 最後のフォールバック: デフォルト値
            self.logger.warning(f"Using default duration for section {section_id}")
            return 120.0
        
        # audio_timing.jsonの構造チェック
        if isinstance(audio_timing, dict):
            # 辞書形式（古い形式）
            sections = audio_timing.get('sections', [])
        elif isinstance(audio_timing, list):
            # リスト形式（新しい形式）
            sections = audio_timing
        else:
            self.logger.warning(f"Unexpected audio_timing type: {type(audio_timing)}")
            return 120.0
        
        # セクションを探す
        for section in sections:
            if section.get('section_id') == section_id:
                # 文字レベルタイミングから長さを計算
                char_end_times = section.get('character_end_times_seconds', [])
                if char_end_times:
                    duration = char_end_times[-1]  # 最後の文字の終了時刻
                    self.logger.debug(f"Section {section_id} actual duration from timings: {duration:.2f}s")
                    return duration
                
                # フォールバック: durationフィールド
                duration = section.get('duration', 120.0)
                self.logger.debug(f"Section {section_id} duration from field: {duration:.2f}s")
                return duration
        
        # セクションが見つからない場合
        self.logger.warning(f"Section {section_id} not found in audio_timing")
        
        # 最後のフォールバック: 音声ファイルから直接取得
        audio_file = self.working_dir / "02_audio" / "sections" / f"section_{section_id:02d}.mp3"
        if audio_file.exists():
            try:
                audio_clip = AudioFileClip(str(audio_file))
                duration = audio_clip.duration
                audio_clip.close()
                self.logger.debug(f"Section {section_id} duration from audio file: {duration:.2f}s")
                return duration
            except Exception as e:
                self.logger.warning(f"Failed to get duration from {audio_file}: {e}")
        
        # 最後のフォールバック: デフォルト値
        self.logger.warning(f"Using default duration for section {section_id}")
        return 120.0
    
    def _load_bgm(self) -> Optional[dict]:
        """BGMデータを読み込み（実際の音声長を使用）"""
        # BGMフォルダのパス（プロジェクトルートからの絶対パス）
        bgm_library_config = self.config.get("paths", {}).get("bgm_library", "assets/bgm")
        bgm_base_path = Path(bgm_library_config)

        # 相対パスの場合はプロジェクトルートからの絶対パスに変換
        if not bgm_base_path.is_absolute():
            project_root = Path(__file__).parent.parent.parent
            bgm_base_path = project_root / bgm_base_path

        self.logger.info(f"BGM library path: {bgm_base_path}")

        if not bgm_base_path.exists():
            self.logger.warning(f"BGM library not found: {bgm_base_path}")
            return None
        
        # 台本を読み込んでBGM情報を取得
        script = self._load_script()
        
        # 音声タイミングデータを読み込み（実際の音声長を取得するため）
        audio_timing = self._load_audio_timing()
        
        bgm_segments = []
        current_time = 0.0
        
        # 辞書として扱う（script["sections"]）
        for section in script.get("sections", []):
            section_id = section.get("section_id", 0)
            bgm_type = section.get("bgm_suggestion", "main")  # "opening", "main", "ending"

            # BGMフォルダからファイルを探す
            bgm_folder = bgm_base_path / bgm_type
            if not bgm_folder.exists():
                self.logger.warning(f"BGM folder not found: {bgm_folder}")
                self.logger.warning(f"Looking for BGM type '{bgm_type}' in section '{section.get('title', 'unknown')}'")
                continue

            # フォルダ内の最初のMP3ファイルを使用
            bgm_files = list(bgm_folder.glob("*.mp3"))
            if not bgm_files:
                self.logger.warning(f"No MP3 files found in: {bgm_folder}")
                continue

            bgm_file = bgm_files[0]  # 最初のファイルを使用
            self.logger.debug(f"Found BGM file: {bgm_file.name} for type '{bgm_type}'")
            
            # 実際の音声長を取得（audio_timing.jsonまたは音声ファイルから）
            actual_duration = self._get_section_duration(section_id, audio_timing)
            
            segment = {
                "bgm_type": bgm_type,
                "file_path": str(bgm_file),
                "start_time": current_time,
                "duration": actual_duration,  # ← 実際の音声長を使用
                "section_id": section_id,
                "section_title": section.get("title", "")
            }
            
            bgm_segments.append(segment)
            current_time += actual_duration  # ← 実際の長さで累積
            
            self.logger.debug(
                f"BGM segment {segment['section_id']}: {bgm_type} "
                f"({current_time - segment['duration']:.1f}s - {current_time:.1f}s)"
            )
        
        if not bgm_segments:
            self.logger.warning("No BGM segments created - check if BGM files exist in assets/bgm/{opening,main,ending}/")
            return None

        self.logger.info(f"✓ Created {len(bgm_segments)} BGM segments (using actual audio durations):")
        for seg in bgm_segments:
            self.logger.info(
                f"  - Section {seg['section_id']}: {seg['bgm_type']} "
                f"({seg['start_time']:.1f}s - {seg['start_time'] + seg['duration']:.1f}s, "
                f"duration: {seg['duration']:.1f}s) - {seg['section_title']}"
            )
        return {"segments": bgm_segments}
    
    def _create_video_clips(
        self,
        clip_paths: List[Path],
        target_duration: float
    ) -> List['VideoFileClip']:
        """動画クリップをロードして準備"""
        clips = []
        
        self.logger.info(f"Loading {len(clip_paths)} video clips...")
        
        for i, path in enumerate(clip_paths, 1):
            try:
                self.logger.debug(f"Loading clip {i}/{len(clip_paths)}: {path.name}")
                clip = VideoFileClip(str(path))
                
                # 解像度を統一
                if clip.size != self.resolution:
                    self.logger.debug(f"  Resizing from {clip.size} to {self.resolution}")
                    # MoviePy 2.xではresizedメソッドを使用
                    clip = clip.resized(self.resolution)
                
                clips.append(clip)
                self.logger.debug(f"  ✓ Loaded: duration={clip.duration:.1f}s, size={clip.size}")
                
            except Exception as e:
                self.logger.error(f"Failed to load clip {path.name}: {e}")
                self.logger.error(f"  Full path: {path}")
                # 失敗してもスキップして続行
                continue
        
        self.logger.info(f"Successfully loaded {len(clips)}/{len(clip_paths)} clips")
        
        if not clips:
            self.logger.error("No clips were loaded successfully!")
            self.logger.error("Please check if the video files are corrupted or in an unsupported format")
        
        return clips
    
    def _concatenate_clips(
        self,
        clips: List['VideoFileClip'],
        target_duration: float
    ) -> 'VideoFileClip':
        """クリップを連結してループ"""
        if not clips:
            raise ValueError("No clips to concatenate")
        
        # クリップをループして必要な長さにする
        if self.clip_loop_enabled:
            final_clips = []
            current_duration = 0.0
            
            while current_duration < target_duration:
                for clip in clips:
                    if current_duration >= target_duration:
                        break
                    
                    remaining = target_duration - current_duration
                    
                    if clip.duration <= remaining:
                        final_clips.append(clip)
                        current_duration += clip.duration
                    else:
                        # 最後のクリップをトリミング
                        trimmed = clip.subclipped(0, remaining)
                        final_clips.append(trimmed)
                        current_duration += remaining
            
            # クロスフェードで連結
            if len(final_clips) > 1:
                video = concatenate_videoclips(
                    final_clips,
                    method="compose",
                    transition=None
                )
            else:
                video = final_clips[0]
        else:
            # 単純連結
            video = concatenate_videoclips(clips, method="compose")
        
        return video
    
    def _add_bgm(self, video: 'VideoFileClip', bgm_data: dict) -> 'VideoFileClip':
        """BGMを追加（セクションごとに切り替え）"""
        try:
            bgm_segments = bgm_data.get("segments", [])
            if not bgm_segments:
                self.logger.info("No BGM segments to add")
                return video

            self.logger.info(f"Adding {len(bgm_segments)} BGM segments to video...")

            # BGMセグメントごとにクリップを作成
            bgm_clips = []
            total_segments = len(bgm_segments)

            for idx, segment in enumerate(bgm_segments):
                bgm_path = Path(segment.get("file_path", ""))

                if not bgm_path.exists():
                    self.logger.warning(f"BGM file not found: {bgm_path}")
                    continue

                start_time = segment.get("start_time", 0.0)
                duration = segment.get("duration", 0.0)
                is_first = (idx == 0)
                is_last = (idx == total_segments - 1)

                # BGMファイルを読み込み
                bgm_clip = AudioFileClip(str(bgm_path))
                original_duration = bgm_clip.duration

                # BGMが短い場合はループ
                if bgm_clip.duration < duration:
                    loops_needed = int(duration / bgm_clip.duration) + 1
                    self.logger.debug(f"  Looping BGM {loops_needed} times (original: {original_duration:.1f}s, needed: {duration:.1f}s)")
                    # MoviePy 2.xではlooped()メソッドがないため、手動でループ
                    bgm_clip = concatenate_audioclips([bgm_clip] * loops_needed)

                # 必要な長さにトリミング
                bgm_clip = bgm_clip.subclipped(0, min(duration, bgm_clip.duration))

                # 音量調整 (MoviePy 2.x)
                bgm_clip = bgm_clip.with_volume_scaled(self.bgm_volume)
                self.logger.debug(f"  Volume set to: {self.bgm_volume:.0%}")

                # フェード処理を適用（MoviePy 2.0）
                if is_first:
                    # 最初のセグメント: フェードインのみ
                    bgm_clip = bgm_clip.with_effects([afx.AudioFadeIn(self.bgm_fade_in)])
                    self.logger.debug(f"  Applied fade-in: {self.bgm_fade_in:.1f}s")

                if is_last:
                    # 最後のセグメント: フェードアウト
                    bgm_clip = bgm_clip.with_effects([afx.AudioFadeOut(self.bgm_fade_out)])
                    self.logger.debug(f"  Applied fade-out: {self.bgm_fade_out:.1f}s")
                elif not is_first:
                    # 中間セグメント: クロスフェード用にフェードイン/アウト（両方適用）
                    bgm_clip = bgm_clip.with_effects([
                        afx.AudioFadeIn(self.bgm_crossfade),
                        afx.AudioFadeOut(self.bgm_crossfade)
                    ])
                    self.logger.debug(f"  Applied crossfade: {self.bgm_crossfade:.1f}s")

                # 開始時間を設定
                bgm_clip = bgm_clip.with_start(start_time)

                bgm_clips.append(bgm_clip)

                self.logger.info(
                    f"  ✓ Added BGM segment {idx+1}/{total_segments}: {segment.get('bgm_type')} "
                    f"({start_time:.1f}s - {start_time + duration:.1f}s) - {bgm_path.name}"
                )
            
            if not bgm_clips:
                self.logger.warning("No BGM clips were created")
                return video

            # ナレーションとBGMをミックス
            self.logger.info(f"Mixing narration with {len(bgm_clips)} BGM segments...")
            final_audio = CompositeAudioClip([video.audio] + bgm_clips)
            video = video.with_audio(final_audio)

            self.logger.info(f"✓ Successfully added {len(bgm_clips)} BGM segments to video")
            
        except Exception as e:
            self.logger.warning(f"Failed to add BGM: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
        
        return video
    
    def _add_subtitles(
        self,
        video: 'VideoFileClip',
        subtitles: List[SubtitleEntry]
    ) -> 'VideoFileClip':
        """字幕を動画に焼き込み（Pillow実装）"""
        if not subtitles:
            self.logger.info("No subtitles to add")
            return video
        
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from moviepy import ImageClip
        
        subtitle_clips = []

        # フォントの準備（明朝体）
        font = self._load_japanese_font(self.subtitle_size)
        
        for subtitle in subtitles:
            try:
                # 字幕テキストを作成
                text = subtitle.text_line1
                if subtitle.text_line2:
                    text += "\n" + subtitle.text_line2
                
                # 画像を作成（透明背景）
                img_width = self.resolution[0]
                img_height = 200  # 字幕エリアの高さ
                
                # RGBA画像を作成（透明背景）
                img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                
                # テキストサイズを取得（複数行対応）
                lines = text.split('\n')
                line_heights = []
                line_widths = []
                
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    line_height = bbox[3] - bbox[1]
                    line_widths.append(line_width)
                    line_heights.append(line_height)
                
                total_height = sum(line_heights) + (len(lines) - 1) * 10  # 行間10px
                max_width = max(line_widths)
                
                # 背景矩形を描画（半透明黒）
                padding = 20
                bg_x1 = (img_width - max_width) // 2 - padding
                bg_y1 = (img_height - total_height) // 2 - padding
                bg_x2 = (img_width + max_width) // 2 + padding
                bg_y2 = (img_height + total_height) // 2 + padding
                
                draw.rectangle(
                    [bg_x1, bg_y1, bg_x2, bg_y2],
                    fill=(0, 0, 0, 180)  # 半透明黒
                )
                
                # テキストを描画（中央揃え）
                stroke_width = self.phase_config.get('subtitle', {}).get('stroke_width', 3)
                current_y = (img_height - total_height) // 2
                for i, line in enumerate(lines):
                    line_width = line_widths[i]
                    line_x = (img_width - line_width) // 2

                    # 影を描画（エッジ効果）
                    for dx, dy in [(-stroke_width, -stroke_width), (-stroke_width, stroke_width),
                                   (stroke_width, -stroke_width), (stroke_width, stroke_width)]:
                        draw.text((line_x + dx, current_y + dy), line,
                                 font=font, fill=(0, 0, 0, 255))

                    # メインテキストを描画
                    draw.text((line_x, current_y), line,
                             font=font, fill=(255, 255, 255, 255))

                    current_y += line_heights[i] + 10
                
                # PILImageをnumpy配列に変換
                img_array = np.array(img)
                
                # ImageClipを作成
                img_clip = ImageClip(img_array, duration=subtitle.end_time - subtitle.start_time)
                img_clip = img_clip.with_start(subtitle.start_time)

                # 画面下部に配置（設定値を使用）
                img_clip = img_clip.with_position(('center', self.resolution[1] - img_height - self.subtitle_margin))
                
                subtitle_clips.append(img_clip)
                
            except Exception as e:
                self.logger.warning(f"Failed to create subtitle {subtitle.index}: {e}")
                import traceback
                self.logger.debug(traceback.format_exc())
                continue
        
        if subtitle_clips:
            # 字幕を動画に合成
            video = CompositeVideoClip([video] + subtitle_clips)
            self.logger.info(f"Added {len(subtitle_clips)} subtitles using Pillow")
        
        return video
    
    def _render_video(self, video: 'VideoFileClip') -> Path:
        """動画をレンダリング"""
        import multiprocessing
        
        output_dir = Path(self.config.get("paths", {}).get("output_dir", "data/output"))
        video_dir = output_dir / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = video_dir / f"{self.subject}.mp4"
        
        # CPUコア数を取得（最適化）
        threads = multiprocessing.cpu_count()
        
        # エンコード設定を取得（preset追加）
        preset = self.phase_config.get('output', {}).get('preset', 'ultrafast')
        
        self.logger.info(f"Encoding with {threads} threads, preset={preset}")
        
        video.write_videofile(
            str(output_path),
            codec=self.codec,
            fps=self.fps,
            bitrate=self.bitrate,
            audio_codec="aac",
            threads=threads,  # 全CPUコアを使用
            preset=preset,    # エンコード速度を最適化
            logger="bar"      # 進捗バーを表示
        )
        
        return output_path
    
    def _generate_thumbnail(self, video: 'VideoFileClip') -> Path:
        """サムネイルを生成"""
        # Phase 7のディレクトリにサムネイルを保存
        thumbnail_path = self.phase_dir / f"{self.subject}_thumbnail.jpg"
        
        # 5秒目のフレームを抽出
        timestamp = min(5.0, video.duration / 2)
        frame = video.get_frame(timestamp)
        
        from PIL import Image
        img = Image.fromarray(frame)
        img.save(thumbnail_path, quality=90)
        
        return thumbnail_path
    
    def _create_split_layout_video(
        self,
        animated_clips: List[Path],
        subtitles: List[SubtitleEntry],
        total_duration: float
    ) -> 'VideoFileClip':
        """
        二分割レイアウトの動画を生成（オーバーレイ方式）

        - 動画：1920x1080（フルサイズ）
        - 下部に黒バー（1920x324）をオーバーレイ
        - 黒バーの上に字幕を表示

        Args:
            animated_clips: Phase 4の動画ファイルパスリスト
            subtitles: 字幕データ
            total_duration: 全体の長さ（秒）

        Returns:
            合成された動画（下部に黒バー+字幕がオーバーレイ）
        """
        self.logger.info("Creating split layout video (overlay mode)...")

        # 比率を取得（デフォルト0.7 = 70%）
        ratio = self.split_config.get('ratio', 0.7)
        top_height = int(1080 * ratio)        # 756px (70%)
        bottom_height = 1080 - top_height     # 324px (30%)

        self.logger.info(f"Layout: Full video 1920x1080 + Bottom overlay {bottom_height}px (subtitle)")

        # Step 1: 動画を1920x1080のままロードして連結
        self.logger.info("Loading video clips (full size 1920x1080)...")
        video_clips = self._create_video_clips(animated_clips, total_duration)
        base_video = self._concatenate_clips(video_clips, total_duration)

        # Step 2: 下部の字幕バー（オーバーレイ用）を生成
        self.logger.info("Creating bottom subtitle overlay...")
        bottom_overlay = self._create_bottom_subtitle_bar(subtitles, total_duration, bottom_height)

        # Step 3: 動画の上に下部バーをオーバーレイ
        self.logger.info("Overlaying subtitle bar on video...")
        final_video = CompositeVideoClip([
            base_video.with_position((0, 0)),                    # フルサイズ動画
            bottom_overlay.with_position((0, top_height))        # 下部にオーバーレイ
        ], size=(1920, 1080))

        self.logger.info("Overlay layout video created successfully")
        return final_video

    def _create_bottom_subtitle_bar(
        self,
        subtitles: List[SubtitleEntry],
        duration: float,
        bar_height: int
    ) -> 'VideoFileClip':
        """
        下部の字幕バーを生成

        - 1920 x bar_height の黒背景
        - 字幕を中央に配置（横方向・縦方向ともに中央、3行まで対応）
        - Pillowで画像を生成してImageClipに変換

        Args:
            subtitles: 字幕データ
            duration: 動画の長さ（秒）
            bar_height: 下部エリアの高さ（324px）

        Returns:
            字幕バーの動画クリップ
        """
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        # 下部字幕バーのサイズ（1920 x bar_height）
        width = 1920
        height = bar_height

        # 字幕クリップのリスト
        subtitle_clips = []

        # フォント読み込み
        font = self._load_japanese_font(self.subtitle_size)

        for subtitle in subtitles:
            try:
                # 字幕画像を生成（3行対応）
                img = self._create_subtitle_image(
                    text_line1=subtitle.text_line1,
                    text_line2=subtitle.text_line2,
                    text_line3=subtitle.text_line3,
                    width=width,
                    height=height,
                    font=font
                )

                # ImageClipに変換
                img_array = np.array(img)
                clip = ImageClip(img_array, duration=subtitle.end_time - subtitle.start_time)
                clip = clip.with_start(subtitle.start_time)

                subtitle_clips.append(clip)

            except Exception as e:
                self.logger.warning(f"Failed to create subtitle image for index {subtitle.index}: {e}")
                continue

        # 黒背景のベースクリップ
        black_bg = ColorClip(size=(width, height), color=(0, 0, 0), duration=duration)

        # 字幕を合成
        if subtitle_clips:
            final_clip = CompositeVideoClip([black_bg] + subtitle_clips)
            self.logger.info(f"Created bottom subtitle bar with {len(subtitle_clips)} subtitles")
        else:
            final_clip = black_bg
            self.logger.warning("No subtitle clips created, using black background only")

        return final_clip

    def _create_top_video_area(
        self,
        clip_paths: List[Path],
        duration: float,
        area_height: int
    ) -> 'VideoFileClip':
        """
        上部の動画エリアを生成

        - Phase 4の動画を 1920 x area_height にリサイズ
        - 連結してループ

        Args:
            clip_paths: Phase 4の動画ファイルパスリスト
            duration: 動画の長さ（秒）
            area_height: 上部エリアの高さ（756px）

        Returns:
            動画エリアのクリップ
        """
        width = 1920
        height = area_height

        # 各クリップを読み込んでリサイズ
        video_clips = []
        for i, clip_path in enumerate(clip_paths, 1):
            try:
                self.logger.debug(f"Loading clip {i}/{len(clip_paths)}: {clip_path.name}")
                clip = VideoFileClip(str(clip_path))

                # 1920 x area_height にリサイズ（crop or fit）
                clip_resized = self._resize_clip_for_split_layout(clip, width, height)
                video_clips.append(clip_resized)

                self.logger.debug(f"  Resized to {width}x{height}")

            except Exception as e:
                self.logger.error(f"Failed to load clip {clip_path.name}: {e}")
                continue

        # クリップを連結
        if video_clips:
            concatenated = concatenate_videoclips(video_clips, method="compose")

            # 音声の長さに合わせてループ
            if concatenated.duration < duration:
                loops = int(duration / concatenated.duration) + 1
                self.logger.info(f"Looping video clips {loops} times to match duration")
                concatenated = concatenate_videoclips([concatenated] * loops, method="compose")

            # 長さを調整
            final_clip = concatenated.subclipped(0, duration)
        else:
            # クリップがない場合は黒画面
            self.logger.warning("No video clips loaded, using black background")
            final_clip = ColorClip(size=(width, height), color=(0, 0, 0), duration=duration)

        return final_clip

    def _resize_clip_for_split_layout(
        self,
        clip: 'VideoFileClip',
        target_width: int,
        target_height: int
    ) -> 'VideoFileClip':
        """
        クリップを目標サイズにリサイズ

        resize_method設定に応じて処理:
        - "crop": アスペクト比を保ちつつクロップ
        - "fit": アスペクト比を保ちつつフィット（余白あり）
        - "stretch": アスペクト比無視して引き伸ばし
        """
        resize_method = self.split_config.get('top_side', {}).get('resize_method', 'crop')

        if resize_method == "crop":
            # クロップ（はみ出た部分をカット）
            # まず高さを合わせる
            clip = clip.resized(height=target_height)
            if clip.w > target_width:
                # 中央でクロップ
                x_center = clip.w / 2
                x1 = int(x_center - target_width / 2)
                clip = clip.cropped(x1=x1, width=target_width)
            return clip

        elif resize_method == "fit":
            # フィット（アスペクト比を保持、余白あり）
            clip = clip.resized(width=target_width)
            if clip.h < target_height:
                # 上下に黒い余白を追加
                # CompositeVideoClipで中央配置
                y_offset = (target_height - clip.h) // 2
                bg = ColorClip(size=(target_width, target_height), color=(0, 0, 0))
                clip = CompositeVideoClip([bg, clip.with_position((0, y_offset))])
            return clip

        else:  # stretch
            # 引き伸ばし
            return clip.resized((target_width, target_height))

    def _create_subtitle_image(
        self,
        text_line1: str,
        text_line2: Optional[str],
        text_line3: Optional[str],
        width: int,
        height: int,
        font
    ) -> 'Image.Image':
        """
        字幕画像を生成（最大3行）

        - 透明背景のRGBA画像
        - テキストを中央に配置
        - 影・縁取り効果

        注意: text_line1/2/3 は既に句読点が削除されている前提

        Returns:
            PIL Image (RGBA)
        """
        from PIL import Image, ImageDraw

        # 句読点チェック（Phase 6で削除済みのはず）
        # 注意: 「、」はPhase 6で意図的に残されるため、警告から除外
        # 削除対象: 。！？（句点のみ）
        if any(punct in text_line1 for punct in ['。', '！', '？']):
            self.logger.warning(
                f"Punctuation found in subtitle text: {text_line1}. "
                "This should have been removed in Phase 6."
            )

        # 透明背景
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # テキスト行をリスト化
        lines = [text_line1]
        if text_line2:
            lines.append(text_line2)
        if text_line3:
            lines.append(text_line3)

        # 各行のサイズを計算
        line_heights = []
        line_widths = []

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            line_widths.append(line_width)
            line_heights.append(line_height)

        # 行間を取得
        line_spacing = self.split_config.get('bottom_side', {}).get('line_spacing', 1.3)
        spacing_px = int(line_heights[0] * (line_spacing - 1.0)) if line_heights else 10

        # 全体の高さ計算
        total_height = sum(line_heights) + spacing_px * (len(lines) - 1)

        # 描画開始位置（中央）
        base_y = (height - total_height) // 2
        # オフセットを適用（負の値で上に移動）
        offset_y = self.split_config.get('bottom_side', {}).get('subtitle_offset_y', 0)
        start_y = base_y + offset_y

        # 各行を描画
        current_y = start_y
        stroke_width = self.phase_config.get('subtitle', {}).get('stroke_width', 3)

        for i, line in enumerate(lines):
            line_width = line_widths[i]
            line_x = (width - line_width) // 2  # 中央揃え

            # 影を描画（4方向）
            for dx, dy in [(-stroke_width, -stroke_width), (-stroke_width, stroke_width),
                           (stroke_width, -stroke_width), (stroke_width, stroke_width)]:
                draw.text((line_x + dx, current_y + dy), line,
                         font=font, fill=(0, 0, 0, 255))

            # メインテキスト
            draw.text((line_x, current_y), line,
                     font=font, fill=(255, 255, 255, 255))

            current_y += line_heights[i] + spacing_px

        return img

    def _load_japanese_font(self, size: int):
        """日本語フォントを読み込む（明朝体優先）"""
        from PIL import ImageFont

        # フォントパスのリスト（明朝体を優先）
        font_paths = [
            # Windows 明朝体
            "C:/Windows/Fonts/msmincho.ttc",  # MS明朝
            "C:/Windows/Fonts/yumin.ttf",     # 游明朝
            "C:/Windows/Fonts/BIZ-UDMinchoM.ttc",  # BIZ UD明朝
            # Linux 明朝体
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",  # Noto Serif CJK
            "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf",  # 日本語明朝
            # macOS 明朝体
            "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",  # ヒラギノ明朝
            "/Library/Fonts/ヒラギノ明朝 ProN W3.ttc",
            # フォールバック: ゴシック体
            "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
            "C:/Windows/Fonts/meiryo.ttc",     # メイリオ
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # Linux
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",  # macOS
        ]

        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, size)
                self.logger.info(f"Using font: {font_path}")
                return font
            except:
                continue

        # フォントが見つからない場合はデフォルト
        self.logger.warning("Japanese font not found, using default font")
        return ImageFont.load_default()

    def _execute_ffmpeg_direct(self) -> VideoComposition:
        """
        ffmpegで直接統合（高速版・2パス方式）
        
        Pass 1: 字幕なし動画生成（黒バー + 映像 + 音声 + BGM）
        Pass 2: 字幕焼き込み（シンプルなコマンドでエスケープ問題を回避）
        
        利点:
        - Windows環境でのパスエスケープ問題を完全回避
        - force_styleの複雑なクォート処理が不要
        - デバッグが容易（各パスを個別に確認可能）
        """
        import subprocess

        render_start = time.time()

        try:
            # 1-4. データ読み込み（既存コード）
            self.logger.info("Loading data...")
            audio_path = self._get_audio_path()
            audio_timing = self._load_audio_timing()
            subtitles = self._load_subtitles()
            bgm_data = self._load_bgm()
            script = self._load_script()
            
            self.logger.info("Creating ffmpeg concat file...")
            concat_file = self._create_ffmpeg_concat_file(script)
            
            self.logger.info("Preparing subtitle file...")
            srt_path = self.working_dir / "06_subtitles" / "subtitles.srt"
            
            if not srt_path.exists():
                raise FileNotFoundError(f"❌ Subtitle file not found: {srt_path}")
            
            file_size = srt_path.stat().st_size
            if file_size == 0:
                raise ValueError(f"❌ Subtitle file is empty: {srt_path}")
            
            self.logger.info(f"✅ Subtitle file found: {srt_path.name} ({file_size} bytes)")

            # 5. 出力パス準備
            output_dir = Path(self.config.get("paths", {}).get("output_dir", "data/output"))
            output_dir = output_dir / "videos"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Pass 1: 字幕なし動画（一時ファイル）
            temp_output = self.working_dir / "07_composition" / f"{self.subject}_temp_no_subs.mp4"
            final_output = output_dir / f"{self.subject}.mp4"

            # 6. Pass 1: 字幕なし動画を生成
            self.logger.info("Pass 1: Building video without subtitles...")
            cmd_pass1 = self._build_ffmpeg_command(
                concat_file=concat_file,
                audio_path=audio_path,
                srt_path=None,  # 字幕なし
                output_path=temp_output,
                bgm_data=bgm_data
            )
            
            self.logger.info(f"Running ffmpeg Pass 1 (preset: {self.encode_preset})...")
            try:
                result = subprocess.run(
                    cmd_pass1,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
                self.logger.info(f"✅ Pass 1 completed: {temp_output}")
                
            except subprocess.CalledProcessError as e:
                self.logger.error(f"❌ ffmpeg Pass 1 failed with code {e.returncode}")
                self.logger.error(f"STDOUT:\n{e.stdout}")
                self.logger.error(f"STDERR:\n{e.stderr}")
                
                cmd_str = ' '.join(f'"{c}"' if ' ' in str(c) else str(c) for c in cmd_pass1)
                self.logger.error(f"Command:\n{cmd_str}")
                raise

            # 7. Pass 2: 字幕を焼き込む
            self.logger.info("Pass 2: Burning subtitles...")
            self._burn_subtitles(temp_output, srt_path, final_output)
            
            # 8. 一時ファイルを削除
            if temp_output.exists():
                temp_output.unlink()
                self.logger.info(f"Temporary file deleted: {temp_output.name}")

            # 9. サムネイル生成
            self.logger.info("Generating thumbnail...")
            thumbnail_path = self._generate_thumbnail_with_ffmpeg(final_output)

            # 10. メタデータ生成
            render_time = time.time() - render_start
            file_size_mb = final_output.stat().st_size / (1024 * 1024)

            composition = VideoComposition(
                subject=self.subject,
                output_video_path=str(final_output),
                thumbnail_path=str(thumbnail_path),
                metadata_path=str(self.phase_dir / "metadata.json"),
                timeline=VideoTimeline(
                    subject=self.subject,
                    clips=[],
                    audio_path=str(audio_path),
                    bgm_segments=[],
                    subtitles=subtitles,
                    total_duration=0.0,  # TODO: 計算
                    resolution=self.resolution,
                    fps=self.fps
                ),
                render_time_seconds=render_time,
                file_size_mb=file_size_mb,
                completed_at=datetime.now()
            )

            self._save_metadata(composition)

            self.logger.info(f"✅ Composition completed in {render_time:.1f}s (2-pass mode)")
            self.logger.info(f"Final video: {final_output}")
            self.logger.info(f"File size: {file_size_mb:.1f} MB")
            return composition

        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg failed: {e.stderr}")
            raise
        except Exception as e:
            self.logger.error(f"Video composition failed: {e}", exc_info=True)
            raise

    def _load_audio_timing(self) -> dict:
        """audio_timing.jsonを読み込み"""
        timing_path = self.working_dir / "02_audio" / "audio_timing.json"
        if not timing_path.exists():
            raise FileNotFoundError(f"audio_timing.json not found: {timing_path}")

        with open(timing_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _create_ffmpeg_concat_file(self, script: dict) -> Path:
        """
        18枚の画像をセクション単位で分割して表示
        
        処理フロー:
        1. BGMデータから各セクションの時間を取得
        2. classified.jsonから全18枚の画像を取得
        3. 画像をセクション番号でグループ化
        4. 各セクション内で画像を均等分割
        5. concat fileを生成
        
        Args:
            script: スクリプトデータ（sectionsを含む）
        
        Returns:
            concatファイルのパス
        """
        concat_file = self.phase_dir / "ffmpeg_concat.txt"
        
        # BGMデータから各セクションの時間を取得
        bgm_data = self._load_bgm()
        segments = bgm_data.get('segments', [])
        
        if not segments:
            raise ValueError("No BGM segments found. Cannot determine section durations.")
        
        # classified.jsonから全画像を取得
        classified_path = self.working_dir / "03_images" / "classified.json"
        
        if not classified_path.exists():
            raise FileNotFoundError(f"classified.json not found: {classified_path}")
        
        with open(classified_path, 'r', encoding='utf-8') as f:
            classified_data = json.load(f)
        
        all_images = classified_data.get('images', [])
        self.logger.info(f"Total images in classified.json: {len(all_images)}")
        
        # セクションごとに画像をグループ化
        section_images = {
            1: [],  # section_01_*
            2: [],  # section_02_*
            3: [],  # section_03_*
            4: [],  # section_04_*
            5: [],  # section_05_*
            6: []   # section_06_*
        }
        
        # 画像をセクション番号で分類
        for img in all_images:
            file_path_str = img.get('file_path', '')
            file_path = Path(file_path_str)
            
            if not file_path.exists():
                self.logger.warning(f"Image file not found: {file_path}")
                continue
            
            # ファイル名からセクション番号を抽出（section_01_, section_02_など）
            filename = file_path.name
            match = re.search(r'section_(\d+)', filename)
            if match:
                section_num = int(match.group(1))
                if 1 <= section_num <= 6:
                    section_images[section_num].append(file_path)
        
        # 各セクション内でファイル名順にソート（順序を保証）
        for section_num in range(1, 7):
            section_images[section_num].sort(key=lambda p: p.name)
            self.logger.debug(f"Section {section_num}: {len(section_images[section_num])} images")
        
        # concat file生成
        concat_lines = []
        total_images = 0
        
        is_windows = platform.system() == 'Windows'
        
        def normalize_concat_path(p: Path) -> str:
            """concatファイル用にパスを正規化"""
            path_str = str(p.resolve())
            if is_windows:
                # Windowsパスを/区切りに
                path_str = path_str.replace('\\', '/')
            # シングルクォートでエスケープ
            return f"'{path_str}'"
        
        for i, segment in enumerate(segments, 1):
            section_duration = segment.get('duration', 0)
            images = section_images.get(i, [])
            images_count = len(images)
            
            if images_count == 0:
                self.logger.warning(f"⚠️ No images found for section {i}")
                continue
            
            if section_duration == 0:
                self.logger.warning(f"⚠️ Section {i} duration is 0, skipping")
                continue
            
            # このセクションの各画像の表示時間
            duration_per_image = section_duration / images_count
            
            self.logger.info(
                f"Section {i}: {images_count} images × {duration_per_image:.1f}s = {section_duration:.1f}s"
            )
            
            for j, image_path in enumerate(images):
                # パス正規化
                normalized_path = normalize_concat_path(image_path)
                concat_lines.append(f"file {normalized_path}")
                
                # 最後の画像以外はduration指定
                is_last_image = (i == len(segments) and j == len(images) - 1)
                if not is_last_image:
                    concat_lines.append(f"duration {duration_per_image:.3f}")
                
                total_images += 1
        
        # 最後の画像を追加（ffmpeg concat仕様）
        if section_images[6]:
            last_image = section_images[6][-1]
            normalized_last = normalize_concat_path(last_image)
            # 既に追加されている場合は何もしない
            if concat_lines[-1] != f"file {normalized_last}":
                concat_lines.append(f"file {normalized_last}")
        
        # ファイルに書き込み
        with open(concat_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(concat_lines))
        
        # 検証
        if not concat_file.exists() or concat_file.stat().st_size == 0:
            raise ValueError("Failed to create valid concat file (empty or not created)")
        
        self.logger.info(f"✅ Concat file created: {total_images} images total")
        self.logger.info(f"Concat file path: {concat_file}")
        
        # デバッグ: concatファイルの内容を表示（最初の10行のみ）
        with open(concat_file, 'r', encoding='utf-8') as f:
            concat_content = f.read()
            lines = concat_content.split('\n')
            preview = '\n'.join(lines[:10])
            self.logger.debug(f"Concat file preview (first 10 lines):\n{preview}...")
        
        return concat_file
    
    def _get_section_duration_from_script(self, section: dict) -> float:
        """
        スクリプトからセクションの長さを取得
        
        Args:
            section: スクリプトのセクション辞書
        
        Returns:
            長さ（秒）
        """
        section_id = section.get('section_id')
        
        # audio_timing.jsonから正確な長さを取得
        audio_timing_path = self.working_dir / "02_audio" / "audio_timing.json"
        
        if audio_timing_path.exists():
            try:
                with open(audio_timing_path, 'r', encoding='utf-8') as f:
                    audio_timing = json.load(f)
                
                # リスト形式のaudio_timingから該当セクションを探す
                if isinstance(audio_timing, list):
                    for timing_section in audio_timing:
                        if timing_section.get('section_id') == section_id:
                            # 文字レベルタイミングの最後から長さを取得
                            char_end_times = timing_section.get('character_end_times_seconds', [])
                            if char_end_times:
                                duration = char_end_times[-1]
                                self.logger.debug(f"Section {section_id} duration from timings: {duration:.2f}s")
                                return duration
                elif isinstance(audio_timing, dict):
                    # 辞書形式の場合
                    for timing_section in audio_timing.get('sections', []):
                        if timing_section.get('section_id') == section_id:
                            char_end_times = timing_section.get('character_end_times_seconds', [])
                            if char_end_times:
                                duration = char_end_times[-1]
                                self.logger.debug(f"Section {section_id} duration from timings: {duration:.2f}s")
                                return duration
            except Exception as e:
                self.logger.warning(f"Failed to load audio_timing.json: {e}")
        
        # フォールバック: スクリプトのduration
        duration = section.get('duration', 120.0)
        self.logger.debug(f"Section {section_id} duration from script: {duration:.2f}s")
        return duration
    
    def _convert_srt_to_ass(self, srt_path: Path) -> Path:
        """
        SRTファイルをASS形式に変換（スタイル埋め込み）
        
        Args:
            srt_path: SRTファイルのパス
        
        Returns:
            ASS形式の字幕ファイルパス
        """
        import re
        
        ass_path = srt_path.with_suffix('.ass')
        
        # ASSヘッダー（フォント・スタイル定義）
        ass_header = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{self.subtitle_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,3,3,0,2,10,10,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        # SRTを読み込んでASSに変換
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        # SRTパース
        subtitle_blocks = re.split(r'\n\n+', srt_content.strip())
        
        ass_events = []
        for block in subtitle_blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            # タイムスタンプ行を取得
            time_line = lines[1]
            match = re.match(
                r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})', 
                time_line
            )
            if not match:
                continue
            
            # ASS形式のタイムスタンプに変換（H:MM:SS.CS）
            start = f"{match.group(1)}:{match.group(2)}:{match.group(3)}.{match.group(4)[:2]}"
            end = f"{match.group(5)}:{match.group(6)}:{match.group(7)}.{match.group(8)[:2]}"
            
            # テキスト取得（改行を\Nに変換）
            text = '\\N'.join(lines[2:])
            
            ass_events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        
        # ASSファイルに書き込み
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_header)
            f.write('\n'.join(ass_events))
        
        self.logger.info(f"✅ Converted SRT to ASS: {ass_path.name}")
        return ass_path

    def _build_ffmpeg_command(
        self,
        concat_file: Path,
        audio_path: Path,
        srt_path: Optional[Path],  # Noneの場合は字幕なし
        output_path: Path,
        bgm_data: Optional[dict]
    ) -> list:
        """
        ffmpegコマンドを構築

        - 黒バー（下部216px）を追加
        - SRT字幕を焼き込み（srt_pathがNoneでない場合のみ）
        - BGMをナレーションとミックス（音量調整、フェード付き）
        
        Args:
            srt_path: 字幕ファイル（Noneの場合は字幕フィルタをスキップ）
        
        修正点:
        - Windowsパスを/区切りに統一
        - 字幕フィルタはPass 1ではスキップ（Pass 2で別途追加）
        """
        import multiprocessing

        # Windowsの場合はパスを正規化
        is_windows = platform.system() == 'Windows'
        
        def normalize_path(p: Path) -> str:
            """WindowsパスをUnix形式に変換（ffmpeg互換）"""
            path_str = str(p.resolve())
            if is_windows:
                # C:\Users\... → C:/Users/...
                path_str = path_str.replace('\\', '/')
            return path_str

        # スレッド数を決定
        threads = self.threads if self.threads > 0 else multiprocessing.cpu_count()

        # 基本コマンド
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', normalize_path(concat_file),
            '-i', normalize_path(audio_path),
        ]

        # BGMファイルを入力として追加
        bgm_segments = []
        if bgm_data and bgm_data.get("segments"):
            bgm_segments = bgm_data.get("segments", [])
            for segment in bgm_segments:
                bgm_path = segment.get("file_path")
                if bgm_path and Path(bgm_path).exists():
                    cmd.extend(['-i', normalize_path(Path(bgm_path))])

        # ビデオフィルタを構築
        video_filters = []

        # 1. 黒バーを追加（下部216px）
        video_filters.append("drawbox=y=ih-216:color=black@1.0:width=iw:height=216:t=fill")

        # 2. 字幕フィルタ（srt_pathがNoneでない場合のみ追加）
        # Pass 1では字幕なし、Pass 2で別途追加
        if srt_path and srt_path.exists():
            self.logger.warning("⚠️ Subtitle filter in Pass 1 is deprecated. Use Pass 2 instead.")

        # ビデオフィルタを適用
        if video_filters:
            cmd.extend(['-vf', ','.join(video_filters)])

        # オーディオフィルタ（BGMがある場合）
        if bgm_segments:
            audio_filter = self._build_audio_filter(bgm_segments)
            cmd.extend(['-filter_complex', audio_filter])
            cmd.extend(['-map', '0:v', '-map', '[audio]'])
        else:
            # BGMなし: ナレーションのみ
            cmd.extend(['-map', '0:v', '-map', '1:a'])

        # 音声の長さを取得
        audio_duration = self._get_audio_duration(audio_path)
        
        # エンコード設定
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.encode_preset,
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-threads', str(threads),
            '-t', str(audio_duration),  # 音声の長さを明示的に指定
            '-shortest',
            '-y',
            normalize_path(output_path)
        ])

        return cmd

    def _build_audio_filter(self, bgm_segments: List[dict]) -> str:
        """
        BGMミックス用のffmpegフィルター生成

        Args:
            bgm_segments: BGMセグメント情報のリスト

        Returns:
            filter_complex文字列

        例:
            [1:a]volume=1.0[narration];
            [2:a]volume=0.1,afade=t=in:st=0:d=3,afade=t=out:st=147:d=3[bgm0];
            [3:a]volume=0.1,afade=t=in:st=150:d=3,afade=t=out:st=297:d=3[bgm1];
            [narration][bgm0][bgm1]amix=inputs=3:duration=first[audio]
        """
        filters = []

        # ナレーション（入力1）
        filters.append("[1:a]volume=1.0[narration]")

        # 各BGMセグメント（入力2以降）
        for i, segment in enumerate(bgm_segments):
            input_idx = i + 2  # BGMは入力2から
            volume = segment.get('volume', self.bgm_volume)
            start_time = segment.get('start_time', 0)
            duration = segment.get('duration', 0)
            fade_in = segment.get('fade_in', self.bgm_fade_in)
            fade_out = segment.get('fade_out', self.bgm_fade_out)

            # フェードアウトの開始時刻を計算
            fade_out_start = start_time + duration - fade_out

            bgm_filter = (
                f"[{input_idx}:a]"
                f"volume={volume},"
                f"afade=t=in:st={start_time}:d={fade_in},"
                f"afade=t=out:st={fade_out_start}:d={fade_out}"
                f"[bgm{i}]"
            )
            filters.append(bgm_filter)

        # ミックス
        inputs = ['[narration]'] + [f'[bgm{i}]' for i in range(len(bgm_segments))]
        mix_filter = f"{''.join(inputs)}amix=inputs={len(inputs)}:duration=first[audio]"
        filters.append(mix_filter)

        return ";".join(filters)

    def _burn_subtitles(self, input_video: Path, srt_path: Path, output_path: Path) -> None:
        """
        Pass 2: 動画に字幕を焼き込む
        
        シンプルなffmpegコマンドでエスケープ問題を回避
        
        Args:
            input_video: Pass 1で生成した字幕なし動画
            srt_path: 字幕ファイル（SRT）
            output_path: 最終出力パス
        """
        import subprocess
        
        is_windows = platform.system() == 'Windows'
        
        # パス正規化
        def normalize_path(p: Path) -> str:
            path_str = str(p.resolve())
            if is_windows:
                path_str = path_str.replace('\\', '/')
            return path_str
        
        input_normalized = normalize_path(input_video)
        output_normalized = normalize_path(output_path)
        
        # 字幕ファイルは相対パスまたは短いパスを使用（エスケープ問題回避）
        # Windowsの場合、作業ディレクトリを字幕ファイルと同じ場所に設定
        srt_filename = srt_path.name
        srt_dir = srt_path.parent
        
        # force_styleの定義（MoviePy版コミット 5beb5add と同じ設定値）
        # MoviePy版の設定: subtitle_size=60, subtitle_margin=150
        force_style = (
            "FontName=Arial,"           # MoviePy版と同じフォント
            "FontSize=60,"              # MoviePy版: subtitle_size=60
            "PrimaryColour=&HFFFFFF,"   # MoviePy版: color=white
            "OutlineColour=&H00000000," # MoviePy版: stroke_width=3の黒縁取り
            "Outline=3,"                # MoviePy版: stroke_width=3
            "Shadow=0,"                 # MoviePy版: 影なし（4方向の縁取りで代用）
            "Alignment=2,"              # MoviePy版: position=bottom（下部中央）
            "MarginV=70"                # MoviePy版: margin_bottom=150から調整（黒バー216px内に配置）
        )
        
        # コマンド構築（字幕ファイル名のみ使用）
        cmd = [
            'ffmpeg',
            '-i', input_normalized,
            '-vf', f"subtitles={srt_filename}:force_style='{force_style}'",
            '-c:v', 'libx264',
            '-preset', self.encode_preset,
            '-crf', '23',
            '-c:a', 'copy',  # 音声は再エンコードしない
            '-y',
            output_normalized
        ]
        
        self.logger.info(f"Burning subtitles: {srt_filename}")
        self.logger.debug(f"Force style: {force_style}")
        
        try:
            # 字幕ファイルのディレクトリで実行（相対パス解決のため）
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=str(srt_dir)  # 作業ディレクトリを字幕ディレクトリに設定
            )
            
            self.logger.info(f"✅ Pass 2 completed: {output_path}")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ ffmpeg Pass 2 failed with code {e.returncode}")
            self.logger.error(f"STDOUT:\n{e.stdout}")
            self.logger.error(f"STDERR:\n{e.stderr}")
            
            # コマンドをログ
            cmd_str = ' '.join(f'"{c}"' if ' ' in str(c) else str(c) for c in cmd)
            self.logger.error(f"Command:\n{cmd_str}")
            
            raise
    
    def _generate_thumbnail_with_ffmpeg(self, video_path: Path) -> Path:
        """ffmpegでサムネイルを生成"""
        import subprocess

        thumbnail_dir = Path(self.config.get("paths", {}).get("output_dir", "data/output")) / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_path = thumbnail_dir / f"{self.subject}_preview.jpg"

        # 5秒の位置からサムネイルを抽出
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', '5.0',
            '-vframes', '1',
            '-q:v', '2',
            '-y',
            str(thumbnail_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        self.logger.info(f"Thumbnail generated: {thumbnail_path}")
        return thumbnail_path

    def _save_metadata(self, composition: VideoComposition):
        """メタデータを保存"""
        metadata_path = self.phase_dir / "metadata.json"

        data = {
            "subject": composition.subject,
            "output_video_path": composition.output_video_path,
            "thumbnail_path": composition.thumbnail_path,
            "render_time_seconds": composition.render_time_seconds,
            "file_size_mb": composition.file_size_mb,
            "completed_at": composition.completed_at.isoformat(),
            "resolution": list(self.resolution),
            "fps": self.fps
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Metadata saved: {metadata_path}")