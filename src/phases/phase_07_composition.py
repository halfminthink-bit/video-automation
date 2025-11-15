"""
Phase 7: 動画統合（Video Composition）
Phase 1-6で生成した全ての素材を統合し、完成動画を生成する
"""

import json
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
        logger
    ):
        super().__init__(subject, config, logger)
        
        if not MOVIEPY_AVAILABLE:
            error_msg = "MoviePy is required. Install with: pip install moviepy"
            if MOVIEPY_IMPORT_ERROR:
                error_msg += f"\n\nImport error details: {MOVIEPY_IMPORT_ERROR}"
            raise ImportError(error_msg)
        
        self.phase_config = config.get_phase_config(7)

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
    
    def _load_script(self) -> dict:
        """台本データを読み込み"""
        script_path = self.working_dir / "01_script" / "script.json"
        with open(script_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_audio_path(self) -> Path:
        """音声ファイルパスを取得"""
        return self.working_dir / "02_audio" / "narration_full.mp3"
    
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
        """セクションの実際の音声長を取得"""
        if not audio_timing:
            # フォールバック: 音声ファイルから直接取得
            audio_file = self.working_dir / "02_audio" / f"section_{section_id:02d}.mp3"
            if audio_file.exists():
                try:
                    audio_clip = AudioFileClip(str(audio_file))
                    duration = audio_clip.duration
                    audio_clip.close()
                    self.logger.debug(f"Got duration from audio file: {duration:.2f}s")
                    return duration
                except Exception as e:
                    self.logger.warning(f"Failed to get duration from {audio_file}: {e}")
            
            # 最後のフォールバック: デフォルト値
            self.logger.warning(f"Using default duration for section {section_id}")
            return 120.0
        
        # audio_timing.jsonから取得
        for section in audio_timing.get('sections', []):
            if section.get('section_id') == section_id:
                duration = section.get('duration', 120.0)
                self.logger.debug(f"Section {section_id} actual duration: {duration:.2f}s")
                return duration
        
        self.logger.warning(f"Section {section_id} not found in audio_timing.json")
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
        ffmpegで直接統合（高速版）

        処理フロー:
        1. audio_timing.jsonから画像とタイミング情報を読み込み
        2. ffmpeg concatファイルを生成（画像+表示時間）
        3. 字幕ファイル（SRT）を準備
        4. BGM情報を読み込み
        5. ffmpegで一発処理:
           - concat demuxerで画像を連結
           - 音声トラックを追加
           - 字幕を焼き込み
           - BGMをミックス（volumeフィルタ使用）

        利点:
        - MoviePyのオーバーヘッドなし
        - メモリ使用量が少ない
        - 処理速度が3-5倍高速
        """
        import subprocess
        import tempfile

        render_start = time.time()

        try:
            # 1. データ読み込み
            self.logger.info("Loading data...")
            audio_path = self._get_audio_path()
            audio_timing = self._load_audio_timing()
            subtitles = self._load_subtitles()
            bgm_data = self._load_bgm()

            # 2. 画像リストとタイミング情報を取得
            images_dir = self.working_dir / "03_images"
            sections = audio_timing.get("sections", [])

            # 3. concat用のタイミングファイル作成
            self.logger.info("Creating ffmpeg concat file...")
            concat_file = self._create_ffmpeg_concat_file(sections, images_dir)

            # 4. 字幕ファイル準備（SRT形式）
            self.logger.info("Preparing subtitle file...")
            srt_path = self.phase_dir / "subtitles.srt"
            if not srt_path.exists():
                # Phase06で生成済みのはずだが、なければsubtitlesから生成
                srt_path = self.working_dir / "06_subtitles" / "subtitles.srt"

            # 5. 出力パス
            output_dir = Path(self.config.get("paths", {}).get("output_dir", "data/output"))
            output_dir = output_dir / "videos"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{self.subject}.mp4"

            # 6. ffmpegコマンドを構築
            self.logger.info("Building ffmpeg command...")
            cmd = self._build_ffmpeg_command(
                concat_file=concat_file,
                audio_path=audio_path,
                srt_path=srt_path,
                output_path=output_path,
                bgm_data=bgm_data
            )

            # 7. ffmpegを実行
            self.logger.info(f"Running ffmpeg (preset: {self.encode_preset})...")
            self.logger.debug(f"Command: {' '.join(str(c) for c in cmd[:15])}...")

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            self.logger.info(f"✅ Video rendered: {output_path}")

            # 8. サムネイル生成
            self.logger.info("Generating thumbnail...")
            thumbnail_path = self._generate_thumbnail_with_ffmpeg(output_path)

            # 9. メタデータ生成
            render_time = time.time() - render_start
            file_size_mb = output_path.stat().st_size / (1024 * 1024)

            composition = VideoComposition(
                subject=self.subject,
                output_video_path=str(output_path),
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

            self.logger.info(f"✅ Composition completed in {render_time:.1f}s (ffmpeg direct)")
            return composition

        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg failed: {e.stderr}")
            raise
        except Exception as e:
            self.logger.error(f"ffmpeg direct integration failed: {e}")
            raise

    def _load_audio_timing(self) -> dict:
        """audio_timing.jsonを読み込み"""
        timing_path = self.working_dir / "02_audio" / "audio_timing.json"
        if not timing_path.exists():
            raise FileNotFoundError(f"audio_timing.json not found: {timing_path}")

        with open(timing_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _create_ffmpeg_concat_file(self, sections: list, images_dir: Path) -> Path:
        """
        ffmpeg concat用のタイミングファイル生成

        Phase03のメタデータから画像パスを読み込み、各セクションの長さに合わせて配置

        フォーマット:
        file 'image1.png'
        duration 3.5
        file 'image2.png'
        duration 4.2
        ...
        """
        concat_file = self.phase_dir / "ffmpeg_concat.txt"

        # Phase03のメタデータから画像パスを取得
        classified_json = images_dir / "classified.json"
        image_paths = []

        if classified_json.exists():
            try:
                with open(classified_json, 'r', encoding='utf-8') as f:
                    classified_data = json.load(f)

                # セクションごとに最初の画像を取得
                for section in classified_data.get("sections", []):
                    if section.get("images"):
                        first_image = section["images"][0]
                        image_path = Path(first_image["file_path"])
                        image_paths.append(image_path)

                self.logger.info(f"Loaded {len(image_paths)} images from classified.json")
            except Exception as e:
                self.logger.warning(f"Failed to load classified.json: {e}, falling back to directory search")
                image_paths = []

        # フォールバック: ディレクトリから直接検索
        if not image_paths:
            # リサイズ済みの画像を検索（1920x1080 PNG）
            resized_dir = images_dir / "resized"
            if resized_dir.exists():
                # セクション順にソート（section_01, section_02, ...）
                for i in range(1, len(sections) + 1):
                    pattern = f"section_{i:02d}_*_001.png"
                    matches = list(resized_dir.glob(pattern))
                    if matches:
                        image_paths.append(matches[0])
                    else:
                        self.logger.warning(f"No image found for section {i:02d}")
            else:
                # generatedディレクトリから検索
                generated_dir = images_dir / "generated"
                for i in range(1, len(sections) + 1):
                    pattern = f"section_{i:02d}_*_001.png"
                    matches = list(generated_dir.glob(pattern))
                    if matches:
                        image_paths.append(matches[0])
                    else:
                        self.logger.warning(f"No image found for section {i:02d}")

        # concat用ファイルを作成
        with open(concat_file, 'w', encoding='utf-8') as f:
            for i, section in enumerate(sections):
                if i >= len(image_paths):
                    self.logger.warning(f"No image for section {i+1}, skipping")
                    continue

                image_path = image_paths[i]

                if not image_path.exists():
                    self.logger.warning(f"Image not found: {image_path}, skipping")
                    continue

                # セクションの長さを計算
                duration = section.get("end_time", 0) - section.get("start_time", 0)

                # パスをエスケープ（絶対パスに変換）
                abs_path = image_path.absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")

                f.write(f"file '{escaped_path}'\n")
                if i < len(sections) - 1:  # 最後以外はdurationを指定
                    f.write(f"duration {duration}\n")

            # 最後の画像（durationなし）
            if image_paths and sections:
                last_image = image_paths[-1]
                if last_image.exists():
                    abs_path = last_image.absolute()
                    escaped_path = str(abs_path).replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")

        self.logger.info(f"Concat file created with {len(image_paths)} images: {concat_file}")
        return concat_file

    def _build_ffmpeg_command(
        self,
        concat_file: Path,
        audio_path: Path,
        srt_path: Path,
        output_path: Path,
        bgm_data: Optional[dict]
    ) -> list:
        """
        ffmpegコマンドを構築

        - 黒バー（下部216px）を追加
        - SRT字幕を焼き込み
        - BGMをナレーションとミックス（音量調整、フェード付き）
        """
        import multiprocessing

        # スレッド数を決定
        threads = self.threads if self.threads > 0 else multiprocessing.cpu_count()

        # 基本コマンド
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),      # 入力0: 画像+タイミング
            '-i', str(audio_path),        # 入力1: 音声
        ]

        # BGMファイルを入力として追加
        bgm_segments = []
        if bgm_data and bgm_data.get("segments"):
            bgm_segments = bgm_data.get("segments", [])
            for segment in bgm_segments:
                bgm_path = segment.get("file_path")
                if bgm_path and Path(bgm_path).exists():
                    cmd.extend(['-i', str(bgm_path)])

        # ビデオフィルタを構築
        video_filters = []

        # 1. 黒バーを追加（下部216px）
        video_filters.append("drawbox=y=ih-216:color=black@1.0:width=iw:height=216:t=fill")

        # 2. 字幕フィルタ
        if srt_path.exists():
            # パスをエスケープ
            srt_str = str(srt_path).replace('\\', '\\\\').replace(':', '\\:')
            subtitle_filter = (
                f"subtitles={srt_str}:force_style='"
                f"FontName={self.subtitle_font},"
                f"FontSize={self.subtitle_size},"
                f"PrimaryColour=&HFFFFFF&,"
                f"OutlineColour=&H000000&,"
                f"Outline=2,"
                f"Shadow=2,"
                f"MarginV=20"
                f"'"
            )
            video_filters.append(subtitle_filter)

        # ビデオフィルタを適用
        cmd.extend(['-vf', ','.join(video_filters)])

        # オーディオフィルタ（BGMがある場合）
        if bgm_segments:
            audio_filter = self._build_audio_filter(bgm_segments)
            cmd.extend(['-filter_complex', audio_filter])
            cmd.extend(['-map', '0:v', '-map', '[audio]'])
        else:
            # BGMなし: ナレーションのみ
            cmd.extend(['-map', '0:v', '-map', '1:a'])

        # エンコード設定
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.encode_preset,
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-threads', str(threads),
            '-shortest',
            '-y',
            str(output_path)
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