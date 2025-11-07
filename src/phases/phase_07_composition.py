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
        TextClip,
        CompositeAudioClip,
        ColorClip,
        ImageClip,
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
        self.bgm_volume = bgm_config.get("volume", 0.2)  # 20%に下げる（従来は30%）
        self.bgm_fade_in = bgm_config.get("fade_in", 3.0)  # フェードイン3秒
        self.bgm_fade_out = bgm_config.get("fade_out", 3.0)  # フェードアウト3秒
        self.bgm_crossfade = bgm_config.get("crossfade", 2.0)  # セグメント間クロスフェード2秒

        # 字幕設定
        subtitle_config = self.phase_config.get("subtitle", {})
        self.subtitle_font = subtitle_config.get("font_family", "Arial")
        self.subtitle_size = subtitle_config.get("font_size", 60)
        self.subtitle_color = subtitle_config.get("color", "white")
        self.subtitle_position = subtitle_config.get("position", "bottom")
        self.subtitle_margin = subtitle_config.get("margin_bottom", 80)

        # 二分割レイアウト設定
        self.split_config = self.phase_config.get("split_layout", {})
        self.split_enabled = self.split_config.get("enabled", False)
    
    def get_phase_number(self) -> int:
        return 7
    
    def get_phase_name(self) -> str:
        return "Video Composition"
    
    def get_phase_directory(self) -> Path:
        return self.working_dir / "07_composition"
    
    def check_inputs_exist(self) -> bool:
        """必要な入力ファイルの存在確認"""
        required_files = []
        
        # Phase 1: 台本
        script_path = self.working_dir / "01_script" / "script.json"
        required_files.append(("Script", script_path))
        
        # Phase 2: 音声
        audio_path = self.working_dir / "02_audio" / "narration_full.mp3"
        required_files.append(("Audio", audio_path))
        
        # Phase 4: アニメ化動画
        animated_dir = self.working_dir / "04_animated"
        if not animated_dir.exists() or not list(animated_dir.glob("*.mp4")):
            self.logger.error(f"No animated clips found in: {animated_dir}")
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
    
    def _load_bgm(self) -> Optional[dict]:
        """BGMデータを読み込み（台本ベース）"""
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
        
        bgm_segments = []
        current_time = 0.0
        
        # 辞書として扱う（script["sections"]）
        for section in script.get("sections", []):
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
            
            segment = {
                "bgm_type": bgm_type,
                "file_path": str(bgm_file),
                "start_time": current_time,
                "duration": section.get("estimated_duration", 120),
                "section_id": section.get("section_id", 0),
                "section_title": section.get("title", "")
            }
            
            bgm_segments.append(segment)
            current_time += segment["duration"]
            
            self.logger.debug(
                f"BGM segment {segment['section_id']}: {bgm_type} "
                f"({current_time - segment['duration']:.1f}s - {current_time:.1f}s)"
            )
        
        if not bgm_segments:
            self.logger.warning("No BGM segments created - check if BGM files exist in assets/bgm/{opening,main,ending}/")
            return None

        self.logger.info(f"✓ Created {len(bgm_segments)} BGM segments from script:")
        for seg in bgm_segments:
            self.logger.info(f"  - {seg['bgm_type']}: {seg['section_title']} ({seg['duration']:.1f}s)")
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
                    bgm_clip = bgm_clip.looped(loops_needed)

                # 必要な長さにトリミング
                bgm_clip = bgm_clip.subclipped(0, min(duration, bgm_clip.duration))

                # 音量調整 (MoviePy 2.x)
                bgm_clip = bgm_clip.with_volume_scaled(self.bgm_volume)
                self.logger.debug(f"  Volume set to: {self.bgm_volume:.0%}")

                # フェード処理を適用
                if is_first:
                    # 最初のセグメント: フェードインのみ
                    bgm_clip = bgm_clip.audio_fadein(self.bgm_fade_in)
                    self.logger.debug(f"  Applied fade-in: {self.bgm_fade_in:.1f}s")

                if is_last:
                    # 最後のセグメント: フェードアウト
                    bgm_clip = bgm_clip.audio_fadeout(self.bgm_fade_out)
                    self.logger.debug(f"  Applied fade-out: {self.bgm_fade_out:.1f}s")
                elif not is_first:
                    # 中間セグメント: クロスフェード用にフェードイン/アウト
                    bgm_clip = bgm_clip.audio_fadein(self.bgm_crossfade)
                    bgm_clip = bgm_clip.audio_fadeout(self.bgm_crossfade)
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
                current_y = (img_height - total_height) // 2
                for i, line in enumerate(lines):
                    line_width = line_widths[i]
                    line_x = (img_width - line_width) // 2
                    
                    # 影を描画（エッジ効果）
                    for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
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
                
                # 画面下部に配置
                img_clip = img_clip.with_position(('center', self.resolution[1] - img_height - 20))
                
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
        output_dir = Path(self.config.get("paths", {}).get("output_dir", "data/output"))
        video_dir = output_dir / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = video_dir / f"{self.subject}.mp4"
        
        video.write_videofile(
            str(output_path),
            codec=self.codec,
            fps=self.fps,
            bitrate=self.bitrate,
            audio_codec="aac",
            threads=4,
            logger="bar"  # 進捗バーを表示
        )
        
        return output_path
    
    def _generate_thumbnail(self, video: 'VideoFileClip') -> Path:
        """サムネイルを生成"""
        output_dir = Path(self.config.get("paths", {}).get("output_dir", "data/output"))
        thumbnail_dir = output_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        
        thumbnail_path = thumbnail_dir / f"{self.subject}_thumbnail.jpg"
        
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
        二分割レイアウトの動画を生成

        左側: 黒背景 + 字幕（960x1080）
        右側: アニメ動画（960x1080にリサイズ）

        Args:
            animated_clips: Phase 4の動画ファイルパスリスト
            subtitles: 字幕データ
            total_duration: 全体の長さ（秒）

        Returns:
            合成された二分割レイアウト動画
        """
        self.logger.info("Creating split layout video...")

        # Step 1: 左側（字幕側）を生成
        self.logger.info("Creating subtitle side (left)...")
        left_side = self._create_subtitle_side(subtitles, total_duration)

        # Step 2: 右側（動画側）を生成
        self.logger.info("Creating video side (right)...")
        right_side = self._create_video_side(animated_clips, total_duration)

        # Step 3: 左右を横並びに配置
        self.logger.info("Compositing left and right sides...")
        final_video = CompositeVideoClip([
            left_side.with_position((0, 0)),           # 左側
            right_side.with_position((960, 0))         # 右側
        ], size=(1920, 1080))

        self.logger.info("Split layout video created successfully")
        return final_video

    def _create_subtitle_side(
        self,
        subtitles: List[SubtitleEntry],
        duration: float
    ) -> 'VideoFileClip':
        """
        左側の字幕エリアを生成

        - 960x1080の黒背景
        - 字幕を中央に配置（3行まで対応）
        - Pillowで画像を生成してImageClipに変換

        Returns:
            字幕側の動画クリップ
        """
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        # 黒背景の作成（960x1080）
        width = self.split_config.get('left_width', 960)
        height = self.resolution[1]  # 1080

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
            self.logger.info(f"Created subtitle side with {len(subtitle_clips)} subtitles")
        else:
            final_clip = black_bg
            self.logger.warning("No subtitle clips created, using black background only")

        return final_clip

    def _create_video_side(
        self,
        clip_paths: List[Path],
        duration: float
    ) -> 'VideoFileClip':
        """
        右側の動画エリアを生成

        - Phase 4の動画を960x1080にリサイズ
        - 連結してループ

        Returns:
            動画側のクリップ
        """
        width = self.split_config.get('right_width', 960)
        height = self.resolution[1]  # 1080

        # 各クリップを読み込んでリサイズ
        video_clips = []
        for i, clip_path in enumerate(clip_paths, 1):
            try:
                self.logger.debug(f"Loading clip {i}/{len(clip_paths)}: {clip_path.name}")
                clip = VideoFileClip(str(clip_path))

                # 960x1080にリサイズ（crop or fit）
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
        resize_method = self.split_config.get('right_side', {}).get('resize_method', 'crop')

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
        if any(punct in text_line1 for punct in ['。', '、', '！', '？']):
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
        line_spacing = self.split_config.get('left_side', {}).get('line_spacing', 1.3)
        spacing_px = int(line_heights[0] * (line_spacing - 1.0)) if line_heights else 10

        # 全体の高さ計算
        total_height = sum(line_heights) + spacing_px * (len(lines) - 1)

        # 描画開始位置（中央）
        start_y = (height - total_height) // 2

        # 各行を描画
        current_y = start_y
        stroke_width = self.phase_config.get('subtitle', {}).get('stroke_width', 2)

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