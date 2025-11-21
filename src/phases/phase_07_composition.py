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
from ..utils.image_timing_matcher_fixed import ImageTimingMatcherFixed
from ..utils.image_timing_matcher_llm import ImageTimingMatcherLLM


class Phase07Composition(PhaseBase):
    """
    Phase 7: 動画統合（FFmpeg版 - Legacy02仕様完全準拠）

    主な機能:
    - FFmpegによる高速動画生成（1パス処理）
    - ASS字幕を直接生成（subtitles.json + audio_timing.json）
    - Legacy02と100%同じ結果を生成

    仕様:
    - 解像度: 1920x1080
    - レイアウト: 上部864px（画像）+ 下部216px（黒バー + 字幕）
    - 画像: セクション内で均等分割（audio_timing.jsonから正確な時間取得）
    - BGM: 音量10%、フェードイン/アウト付き
    - 字幕: ASS形式、Noto-Sans-JP-Bold、60px、黒縁取り2px

    処理時間: MoviePy版（15分）→ FFmpeg版（1分）
    """

    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger,
        genre: Optional[str] = None,
        use_legacy: bool = False
    ):
        super().__init__(subject, config, logger)
        self.genre = genre

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
        self.bgm_base_volume = bgm_config.get("volume", 0.1)
        self.bgm_volume_amplification = bgm_config.get("volume_amplification", 1.0)

        # BGMタイプごとの音量倍率を読み込み
        self.bgm_volume_by_type = bgm_config.get("volume_by_type", {})
        self.logger.info(
            f"BGM volume settings: base={self.bgm_base_volume:.0%}, "
            f"amplification={self.bgm_volume_amplification:.1f}x"
        )
        if self.bgm_volume_by_type:
            self.logger.info("BGM volume by type:")
            for bgm_type, multiplier in self.bgm_volume_by_type.items():
                final_volume = min(self.bgm_base_volume * self.bgm_volume_amplification * multiplier, 1.0)
                self.logger.info(f"  {bgm_type}: {multiplier:.1f}x → {final_volume:.1%}")

        # BGM fade設定
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
        import subprocess

        try:
            # ffprobe を使用して音声ファイルの長さを取得
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=False,  # バイナリモードで
                check=True
            )
            duration_str = result.stdout.decode('utf-8', errors='ignore').strip()
            duration = float(duration_str)
            self.logger.debug(f"Audio duration ({audio_path.name}): {duration:.2f}s")
            return duration
        except Exception as e:
            self.logger.warning(f"Failed to get audio duration for {audio_path}: {e}")
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
                # 🔥 重要: durationフィールドを直接使用（優先）
                duration = section.get('duration')

                if duration is not None:
                    self.logger.info(f"Section {section_id} duration from audio_timing: {duration:.2f}s")
                    return duration

                # フォールバック1: char_end_timesの最後の値
                char_end_times = section.get('char_end_times', [])
                if char_end_times:
                    duration = char_end_times[-1]
                    self.logger.info(f"Section {section_id} duration from char_end_times: {duration:.2f}s")
                    return duration

                # フォールバック2: character_end_times_seconds（古い形式）
                char_end_times = section.get('character_end_times_seconds', [])
                if char_end_times:
                    duration = char_end_times[-1]
                    self.logger.info(f"Section {section_id} duration from character_end_times_seconds: {duration:.2f}s")
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

        # ジャンル設定から BGM パスを取得
        if self.genre:
            genre_config = self.config.get_genre_config(self.genre)
            bgm_library_config = genre_config.get("bgm_library", "assets/bgm")
            self.logger.info(f"Using genre-specific BGM library: {bgm_library_config} (genre={self.genre})")
        else:
            # フォールバック: 従来の動作（paths.bgm_library）
            bgm_library_config = self.config.get("paths", {}).get("bgm_library", "assets/bgm")
            self.logger.warning("No genre specified, using default BGM library from paths.bgm_library")

        bgm_base_path = Path(bgm_library_config)

        # 相対パスの場合はプロジェクトルートからの絶対パスに変換
        if not bgm_base_path.is_absolute():
            project_root = Path(__file__).parent.parent.parent
            bgm_base_path = project_root / bgm_base_path

        self.logger.info(f"BGM library path resolved: {bgm_base_path}")

        if not bgm_base_path.exists():
            self.logger.warning(f"BGM library not found: {bgm_base_path}")
            return None

        # 台本を読み込んでBGM情報を取得
        script = self._load_script()

        # 音声タイミングデータを読み込み（実際の音声長を取得するため）
        audio_timing = self._load_audio_timing()

        bgm_segments = []
        current_time = 0.0

        # BGMタイプごとにセクションをグループ化
        bgm_groups = {}
        section_order = {}  # 各BGMタイプの最小Section IDを記録

        for section in script.get("sections", []):
            section_id = section.get("section_id", 0)
            bgm_type = section.get("bgm_suggestion", "main")

            if bgm_type not in bgm_groups:
                bgm_groups[bgm_type] = []
                section_order[bgm_type] = section_id  # 最初に出現したSection IDを記録

            bgm_groups[bgm_type].append({
                'section_id': section_id,
                'duration': self._get_section_duration(section_id, audio_timing),
                'title': section.get('title', '')
            })

        # Section IDの順序でソート（アルファベット順ではなく）
        sorted_bgm_types = sorted(bgm_groups.keys(), key=lambda bgm_type: section_order[bgm_type])

        # 各BGMタイプごとにセグメントを作成
        for bgm_type in sorted_bgm_types:
            sections = bgm_groups[bgm_type]
            # BGMフォルダからファイルを探す
            # bgm_base_pathが既にジャンルフォルダを含む場合はそのまま使用
            # そうでない場合は、ジャンルが指定されている場合はジャンルフォルダを追加
            if self.genre and not str(bgm_base_path).endswith(self.genre):
                bgm_folder = bgm_base_path / self.genre / bgm_type
            else:
                bgm_folder = bgm_base_path / bgm_type
            
            if not bgm_folder.exists():
                self.logger.warning(f"BGM folder not found: {bgm_folder}")
                continue

            bgm_files = list(bgm_folder.glob("*.mp3"))
            if not bgm_files:
                self.logger.warning(f"No MP3 files found in: {bgm_folder}")
                continue

            bgm_file = bgm_files[0]

            # 連続するセクションの合計時間
            total_duration = sum(s['duration'] for s in sections)

            segment = {
                "bgm_type": bgm_type,
                "file_path": str(bgm_file),
                "start_time": current_time,
                "duration": total_duration,
                "section_ids": [s['section_id'] for s in sections],
                "section_titles": [s['title'] for s in sections],
                "volume": self._get_bgm_volume_for_type(bgm_type)
            }

            bgm_segments.append(segment)
            current_time += total_duration

            self.logger.info(
                f"BGM segment: {bgm_type} "
                f"[{segment['start_time']:.1f}s - {current_time:.1f}s] "
                f"Duration: {total_duration:.1f}s "
                f"(Sections: {segment['section_ids']}) "
                f"Volume: {segment['volume']:.1%}"
            )

        if not bgm_segments:
            self.logger.warning("No BGM segments created - check if BGM files exist in assets/bgm/{opening,main,ending}/")
            return None

        # デバッグログ: BGMセグメント詳細情報
        self.logger.info("=" * 60)
        self.logger.info("BGM Segments Debug Info:")
        for i, seg in enumerate(bgm_segments):
            self.logger.info(
                f"  Segment {i+1}: {seg['bgm_type']} "
                f"[{seg['start_time']:.1f}s - {seg['start_time'] + seg['duration']:.1f}s] "
                f"Duration: {seg['duration']:.1f}s"
            )
        self.logger.info("=" * 60)

        self.logger.info(f"✓ Created {len(bgm_segments)} BGM segments (using actual audio durations):")
        for seg in bgm_segments:
            self.logger.info(
                f"  - Sections {seg['section_ids']}: {seg['bgm_type']} "
                f"({seg['start_time']:.1f}s - {seg['start_time'] + seg['duration']:.1f}s, "
                f"duration: {seg['duration']:.1f}s)"
            )
        return {"segments": bgm_segments}

    def _get_bgm_volume_for_type(self, bgm_type: str) -> float:
        """
        BGMタイプに応じた音量を計算

        Args:
            bgm_type: BGMタイプ（opening/main/ending）

        Returns:
            最終的なBGM音量（0.0-1.0）
        """
        # タイプごとの倍率を取得（デフォルト: 1.0）
        type_multiplier = self.bgm_volume_by_type.get(bgm_type, 1.0)

        # 最終音量 = 基本音量 × 全体増幅率 × タイプ別倍率
        final_volume = self.bgm_base_volume * self.bgm_volume_amplification * type_multiplier

        # 最大100%に制限
        return min(final_volume, 1.0)

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
                # Legacy版: 基本音量のみ使用（タイプ別音量は未対応）
                bgm_clip = bgm_clip.with_volume_scaled(self.bgm_base_volume)
                self.logger.debug(f"  Volume set to: {self.bgm_base_volume:.0%}")

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
        """日本語フォントを読み込む（cinecaption226.ttf優先）"""
        from PIL import ImageFont

        # プロジェクトルートからフォントパスを取得
        project_root = self.config.project_root
        cinecaption_font = project_root / "assets" / "fonts" / "cinema" / "cinecaption226.ttf"

        # フォントパスのリスト（cinecaption226.ttfを最優先）
        font_paths = [
            # プロジェクト内のフォント（最優先）
            str(cinecaption_font),
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
        ffmpegで直接統合（高速版・セグメントベース方式・Legacy02仕様完全準拠）

        改善点:
        - セグメントベースのアプローチで字幕同期を保証
        - 各画像を独立した動画として生成してから結合
        - ASS字幕を正確なタイミングで適用
        - BGM音量を10%に固定（Legacy02と同じ）
        - 黒バー（下部216px）+ ASS字幕を1回の処理で実行
        """
        import subprocess

        render_start = time.time()

        try:
            # 1. データ読み込み
            self.logger.info("Loading data...")
            audio_path = self._get_audio_path()
            audio_timing = self._load_audio_timing()
            subtitles = self._load_subtitles()
            script = self._load_script()

            # 2. BGM読み込み（YAML設定から音量を取得）
            bgm_config = self.phase_config.get("bgm", {})
            base_volume = bgm_config.get("volume", 0.1)
            amplification = bgm_config.get("volume_amplification", 1.0)
            self.logger.info(
                f"Loading BGM data (base volume: {base_volume:.0%}, "
                f"amplification: {amplification:.1f}x)..."
            )
            bgm_data = self._load_bgm()

            # 3. セグメントベースの動画生成（字幕同期の問題を解決）
            self.logger.info("Creating video using segment-based approach...")
            final_output = self._create_segment_videos_then_concat(audio_path, bgm_data)

            # 4. サムネイル生成
            self.logger.info("Generating thumbnail...")
            thumbnail_path = self._generate_thumbnail_with_ffmpeg(final_output)

            # 5. メタデータ生成
            render_time = time.time() - render_start
            file_size_mb = final_output.stat().st_size / (1024 * 1024)

            # 音声の長さを取得
            audio_duration = self._get_audio_duration(audio_path)

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
                    total_duration=audio_duration,
                    resolution=self.resolution,
                    fps=self.fps
                ),
                render_time_seconds=render_time,
                file_size_mb=file_size_mb,
                completed_at=datetime.now()
            )

            self._save_metadata(composition)

            self.logger.info(f"✅ Composition completed in {render_time:.1f}s (Segment-based FFmpeg)")
            self.logger.info(f"Final video: {final_output}")
            self.logger.info(f"File size: {file_size_mb:.1f} MB")
            self.logger.info(f"Video duration: {audio_duration:.2f}s")
            return composition

        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg failed: {e.stderr}")
            raise
        except Exception as e:
            self.logger.error(f"Video composition failed: {e}", exc_info=True)
            raise

    def _create_segment_videos_then_concat(self, audio_path: Path, bgm_data: Optional[dict]) -> Path:
        """
        セグメントごとに動画を作成してから連結（方法2: タイミング同期の問題を解決）

        利点：
        - 各セグメントのタイミングが正確
        - concat demuxerで高速結合
        - 字幕の同期問題なし

        手順：
        1. 各画像を個別の動画に変換（字幕なし）
        2. concat demuxerで連結
        3. ASS字幕を適用

        Args:
            audio_path: 音声ファイルのパス
            bgm_data: BGMデータ

        Returns:
            最終動画のパス
        """
        import subprocess
        import tempfile

        self.logger.info("🎬 Using segment-based approach for better subtitle sync...")

        # 一時ディレクトリ作成
        temp_dir = Path(tempfile.mkdtemp(prefix="video_segments_"))
        segment_files = []
        concat_list = None

        try:
            # 1. 画像とタイミング情報を取得
            self.logger.info("Loading image files and timing information...")
            script = self._load_script()
            audio_timing = self._load_audio_timing()

            # classified.jsonから全画像を取得
            classified_path = self.working_dir / "03_images" / "classified.json"
            if not classified_path.exists():
                raise FileNotFoundError(f"classified.json not found: {classified_path}")

            with open(classified_path, 'r', encoding='utf-8') as f:
                classified_data = json.load(f)

            all_images = classified_data.get('images', [])

            # セクションIDと時間のマッピングを作成
            section_durations = {}
            if isinstance(audio_timing, list):
                for timing_section in audio_timing:
                    section_id = timing_section.get('section_id')
                    char_end_times = timing_section.get('char_end_times', [])
                    if section_id and char_end_times:
                        section_durations[section_id] = char_end_times[-1]
            elif isinstance(audio_timing, dict):
                sections = audio_timing.get('sections', [audio_timing])
                for timing_section in sections:
                    section_id = timing_section.get('section_id')
                    char_end_times = timing_section.get('char_end_times', [])
                    if section_id and char_end_times:
                        section_durations[section_id] = char_end_times[-1]

            # セクションごとに画像をグループ化
            section_images = {sid: [] for sid in section_durations.keys()}
            for img in all_images:
                file_path = Path(img.get('file_path', ''))
                if not file_path.exists():
                    continue

                # ファイル名からセクション番号を抽出
                match = re.search(r'section_(\d+)', file_path.name)
                if match:
                    section_num = int(match.group(1))
                    if section_num in section_images:
                        section_images[section_num].append(file_path)

            # 各セクション内でソート
            for section_num in section_images.keys():
                section_images[section_num].sort(key=lambda p: p.name)

            # 2. 画像ごとの表示時間を計算
            image_timings = []
            sorted_section_ids = sorted(section_images.keys())

            # 音声の実際の長さを取得
            actual_audio_duration = self._get_audio_duration(audio_path)
            self.logger.info(f"Actual audio duration: {actual_audio_duration:.3f}s")

            # 画像タイミングモードを確認
            image_timing_config = self.phase_config.get("image_timing", {})
            timing_mode = image_timing_config.get("mode", "equal_split")
            
            if timing_mode == "llm":
                # LLM駆動型画像配置モード
                self.logger.info("🤖 Using LLM-driven image timing mode")
                try:
                    # 字幕タイミングを読み込み
                    subtitle_timing_path = self.working_dir / "06_subtitles" / "subtitle_timing.json"
                    if subtitle_timing_path.exists():
                        with open(subtitle_timing_path, 'r', encoding='utf-8') as f:
                            subtitle_timing_data = json.load(f)
                        subtitle_timing = subtitle_timing_data.get('subtitles', [])
                        
                        # APIキーを取得
                        try:
                            api_key = self.config.get_api_key("CLAUDE_API_KEY")
                        except Exception:
                            # 環境変数から直接取得を試みる
                            import os
                            api_key = os.getenv("CLAUDE_API_KEY")
                            if not api_key:
                                raise ValueError("CLAUDE_API_KEY not found in config or environment")
                        
                        # ImageTimingMatcherLLMを初期化
                        llm_config = image_timing_config.get("llm", {})
                        matcher = ImageTimingMatcherLLM(
                            working_dir=self.working_dir,
                            api_key=api_key,
                            model=llm_config.get("model", "claude-3-haiku-20240307"),
                            cache_dir=llm_config.get("cache_dir"),
                            min_duration=llm_config.get("min_display_duration", 3.0),
                            max_duration=llm_config.get("max_display_duration", 15.0),
                            gap_threshold=llm_config.get("gap_threshold", 2.0),
                            logger=self.logger
                        )
                        
                        # セクションごとに画像クリップを生成
                        all_image_clips = []
                        for section_id in sorted_section_ids:
                            image_clips = matcher.match_images_to_subtitles(
                                script_data=script,
                                classified_images=classified_data,
                                subtitle_timing=subtitle_timing,
                                section_id=section_id
                            )
                            all_image_clips.extend(image_clips)
                        
                        # 時間順にソート
                        all_image_clips.sort(key=lambda clip: clip['start_time'])
                        
                        # image_timingsに変換
                        for clip in all_image_clips:
                            image_path = Path(clip['image_path'])
                            start_time = clip['start_time']
                            end_time = clip['end_time']
                            duration = end_time - start_time
                            
                            if image_path.exists():
                                image_timings.append({
                                    'path': image_path,
                                    'duration': duration,
                                    'start_time': start_time,
                                    'end_time': end_time
                                })
                        
                        self.logger.info(f"✅ Generated {len(image_timings)} image clips with LLM matching")
                    else:
                        self.logger.warning(f"subtitle_timing.json not found. Falling back to equal split mode.")
                        raise FileNotFoundError(f"subtitle_timing.json not found: {subtitle_timing_path}")
                except Exception as e:
                    self.logger.warning(f"LLM matching failed: {e}. Falling back to keyword match mode.")
                    timing_mode = "keyword_match"  # フォールバック
            
            if timing_mode == "keyword_match":
                # キーワードマッチングモード
                self.logger.info("🎯 Using keyword-based image timing mode")
                try:
                    # 字幕タイミングを読み込み
                    subtitle_timing_path = self.working_dir / "06_subtitles" / "subtitle_timing.json"
                    if subtitle_timing_path.exists():
                        with open(subtitle_timing_path, 'r', encoding='utf-8') as f:
                            subtitle_timing_data = json.load(f)
                        subtitle_timing = subtitle_timing_data.get('subtitles', [])
                        
                        # ImageTimingMatcherFixedを初期化
                        keyword_match_config = image_timing_config.get("keyword_match", {})
                        matcher = ImageTimingMatcherFixed(
                            working_dir=self.working_dir,  # audio_timing.jsonを読むため
                            min_duration=keyword_match_config.get("min_display_duration", 3.0),
                            max_duration=keyword_match_config.get("max_display_duration", 15.0),
                            section_boundary_switch=keyword_match_config.get("section_boundary_switch", True),
                            exact_match_weight=keyword_match_config.get("priority", {}).get("exact_match_weight", 10.0),
                            partial_match_weight=keyword_match_config.get("priority", {}).get("partial_match_weight", 5.0),
                            same_section_weight=keyword_match_config.get("priority", {}).get("same_section_weight", 3.0),
                            keyword_length_weight=keyword_match_config.get("priority", {}).get("keyword_length_weight", 1.0),
                            logger=self.logger
                        )
                        
                        # セクションごとに画像クリップを生成
                        all_image_clips = []
                        for section_id in sorted_section_ids:
                            image_clips = matcher.match_images_to_subtitles(
                                script_data=script,
                                classified_images=classified_data,
                                subtitle_timing=subtitle_timing,
                                section_id=section_id
                            )
                            all_image_clips.extend(image_clips)
                        
                        # 時間順にソート
                        all_image_clips.sort(key=lambda clip: clip['start_time'])
                        
                        # image_timingsに変換
                        for clip in all_image_clips:
                            image_path = Path(clip['image_path'])
                            start_time = clip['start_time']
                            end_time = clip['end_time']
                            duration = end_time - start_time
                            
                            if image_path.exists():
                                image_timings.append({
                                    'path': image_path,
                                    'duration': duration,
                                    'start_time': start_time,
                                    'end_time': end_time
                                })
                        
                        self.logger.info(f"✅ Generated {len(image_timings)} image clips with keyword matching")
                    else:
                        self.logger.warning(f"subtitle_timing.json not found. Falling back to equal split mode.")
                        raise FileNotFoundError(f"subtitle_timing.json not found: {subtitle_timing_path}")
                except Exception as e:
                    self.logger.warning(f"Keyword matching failed: {e}. Falling back to equal split mode.")
                    timing_mode = "equal_split"  # フォールバック
            
            if timing_mode == "equal_split":
                # 均等分割モード（従来の方法）
                self.logger.info("📊 Using equal split image timing mode")
                
                # Section 1とSection 2の合計時間を計算
                section_1_2_duration = 0
                for section_id in sorted_section_ids[:-1]:  # 最後以外
                    section_1_2_duration += section_durations.get(section_id, 0)

                # Section 3に必要な時間（音声の実際の長さ - Section 1,2の合計）
                if len(sorted_section_ids) >= 3:
                    remaining_duration = actual_audio_duration - section_1_2_duration
                    self.logger.info(
                        f"Section 1+2 duration: {section_1_2_duration:.3f}s, "
                        f"Section 3 needs: {remaining_duration:.3f}s"
                    )

                for section_id in sorted_section_ids:
                    images = section_images[section_id]
                    images_count = len(images)

                    if images_count == 0:
                        continue

                    # 最後のセクション（Section 3）は音声の実際の長さに合わせる
                    if section_id == sorted_section_ids[-1] and len(sorted_section_ids) >= 3:
                        section_duration = remaining_duration
                    else:
                        section_duration = section_durations.get(section_id, 0)

                    if section_duration == 0:
                        continue

                    # このセクションの各画像の表示時間（均等分割）
                    duration_per_image = section_duration / images_count

                    self.logger.info(
                        f"Section {section_id}: {images_count} images × {duration_per_image:.3f}s = {section_duration:.3f}s"
                    )

                    for image_path in images:
                        image_timings.append({
                            'path': image_path,
                            'duration': duration_per_image
                        })

            self.logger.info(f"Total images to process: {len(image_timings)}")

            # 3. 各画像を動画セグメントに変換
            self.logger.info("Creating video segments from images...")
            for i, timing in enumerate(image_timings):
                img_path = timing['path']
                duration = timing['duration']
                output_segment = temp_dir / f"segment_{i:03d}.mp4"

                cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1',
                    '-i', str(img_path),
                    '-t', f"{duration:.6f}",
                    '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',  # 速度重視
                    '-crf', '0',  # ロスレス
                    '-pix_fmt', 'yuv420p',
                    '-r', '30',  # FPS統一
                    str(output_segment)
                ]

                try:
                    result = subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        text=False,  # バイナリモードで取得
                        encoding=None  # エンコーディングを指定しない
                    )
                    segment_files.append(output_segment)
                    if (i + 1) % 3 == 0 or i == len(image_timings) - 1:
                        self.logger.info(f"  Created {i + 1}/{len(image_timings)} segments")
                except subprocess.CalledProcessError as e:
                    # エラーメッセージをUTF-8でデコード（失敗時は無視）
                    try:
                        stderr_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''
                    except:
                        stderr_msg = '<decode failed>'
                    self.logger.error(f"Failed to create segment {i}: {stderr_msg}")
                    raise

            # 4. concat用のファイルリスト作成
            concat_list = temp_dir / "concat.txt"
            with open(concat_list, 'w', encoding='utf-8') as f:
                for segment in segment_files:
                    # パスを正規化（Windowsの場合は/区切りに）
                    path_str = str(segment.resolve())
                    if platform.system() == 'Windows':
                        path_str = path_str.replace('\\', '/')
                    f.write(f"file '{path_str}'\n")

            self.logger.info(f"Created concat file with {len(segment_files)} segments")

            # 5. ASS字幕を生成
            self.logger.info("Creating ASS subtitles...")
            ass_path = self._create_ass_subtitles_fixed()

            # 6. 最終動画を生成（concat + 字幕 + 音声）
            output_dir = Path(self.config.get("paths", {}).get("output_dir", "data/output"))
            output_dir = output_dir / "videos"
            output_dir.mkdir(parents=True, exist_ok=True)
            final_output = output_dir / f"{self.subject}.mp4"

            self.logger.info("Combining segments with audio and subtitles...")

            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_list),
                '-i', str(audio_path)
            ]

            # BGM入力
            bgm_input_indices = []
            if bgm_data and bgm_data.get("segments"):
                for segment in bgm_data["segments"]:
                    bgm_path = segment.get("file_path")
                    if bgm_path and Path(bgm_path).exists():
                        cmd.extend(['-i', str(bgm_path)])
                        bgm_input_indices.append(len(cmd) // 2 - 1)

            # フィルタ構築
            ass_path_str = str(ass_path).replace('\\', '/').replace(':', '\\:')
            video_filter = f"drawbox=y=ih-216:color=black@1.0:width=iw:height=216:t=fill,ass='{ass_path_str}'"
            cmd.extend(['-vf', video_filter])

            # オーディオ処理
            if bgm_input_indices:
                # BGM情報のデバッグ出力
                self.logger.info("=" * 60)
                self.logger.info("BGM Configuration:")
                self.logger.info(f"  Base volume: {self.bgm_base_volume:.1%}")
                self.logger.info(f"  Amplification: {self.bgm_volume_amplification:.1f}x")
                self.logger.info(f"  Total segments: {len(bgm_data.get('segments', []))}")

                for i, seg in enumerate(bgm_data.get('segments', [])):
                    bgm_path = Path(seg.get('file_path', ''))
                    if bgm_path.exists():
                        actual_duration = self._get_audio_duration(bgm_path)
                        need_loop = seg['duration'] > actual_duration
                        self.logger.info(
                            f"  Segment {i+1}: {seg['bgm_type']} "
                            f"[{seg['start_time']:.1f}s-{seg['start_time']+seg['duration']:.1f}s] "
                            f"BGM: {actual_duration:.1f}s, Need: {seg['duration']:.1f}s "
                            f"{'(LOOP)' if need_loop else '(NO LOOP)'}"
                        )
                self.logger.info("=" * 60)

                audio_filter = self._build_audio_filter(bgm_data["segments"])
                cmd.extend(['-filter_complex', audio_filter])
                cmd.extend(['-map', '0:v', '-map', '[audio]'])
            else:
                cmd.extend(['-map', '0:v', '-map', '1:a'])

            # エンコード設定
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', self.encode_preset,
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-t', f'{actual_audio_duration:.3f}',  # 音声の正確な長さを指定
                '-avoid_negative_ts', 'make_zero',  # タイムスタンプの問題を回避
                str(final_output)
            ])

            # FFmpegを実行
            self.logger.info("Running final ffmpeg command...")
            self.logger.info("=" * 60)
            self.logger.info("FFmpeg command preview:")

            # コマンドを見やすく表示
            for j, arg in enumerate(cmd):
                if j == 0:
                    self.logger.info(f"  {arg}")
                elif arg.startswith('-'):
                    self.logger.info(f"  {arg} \\")
                else:
                    self.logger.info(f"    {arg} \\")

            self.logger.info("=" * 60)

            try:
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=False,  # バイナリモードで取得
                    encoding=None  # エンコーディングを指定しない
                )
                self.logger.info(f"✅ Video generation completed: {final_output}")

                # 必要に応じてログ出力（UTF-8でデコード）
                if result.stdout:
                    try:
                        stdout = result.stdout.decode('utf-8', errors='ignore')
                        if stdout.strip():
                            self.logger.debug(f"FFmpeg output: {stdout}")
                    except:
                        pass  # デコードできない場合は無視

            except subprocess.CalledProcessError as e:
                self.logger.error(f"❌ ffmpeg failed with code {e.returncode}")
                # エラーメッセージをUTF-8でデコード（失敗時は無視）
                try:
                    stderr_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''
                    self.logger.error(f"STDERR:\n{stderr_msg}")
                except:
                    self.logger.error("STDERR: <decode failed>")
                raise

            return final_output

        finally:
            # 7. 一時ファイルをクリーンアップ
            self.logger.info("Cleaning up temporary files...")
            for segment in segment_files:
                if segment.exists():
                    segment.unlink()
            if concat_list and concat_list.exists():
                concat_list.unlink()
            if temp_dir.exists():
                try:
                    # ディレクトリ内のファイルを削除してからディレクトリを削除
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    self.logger.warning(f"Failed to delete temp directory: {e}")
            self.logger.info("✅ Cleanup completed")

    def _load_audio_timing(self) -> dict:
        """audio_timing.jsonを読み込み"""
        timing_path = self.working_dir / "02_audio" / "audio_timing.json"
        if not timing_path.exists():
            raise FileNotFoundError(f"audio_timing.json not found: {timing_path}")

        with open(timing_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _create_ffmpeg_concat_file(self, script: dict) -> Path:
        """
        画像をセクション単位で分割して表示（Legacy02仕様完全準拠）

        処理フロー:
        1. audio_timing.jsonから各セクションの正確な時間を取得
        2. classified.jsonから全画像を取得
        3. 画像をセクション番号でグループ化
        4. 各セクション内で画像を均等分割
        5. concat fileを生成

        Args:
            script: スクリプトデータ（sectionsを含む）

        Returns:
            concatファイルのパス
        """
        concat_file = self.phase_dir / "ffmpeg_concat.txt"

        # audio_timing.jsonから各セクションの時間を取得（Legacy02仕様）
        audio_timing_path = self.working_dir / "02_audio" / "audio_timing.json"

        if not audio_timing_path.exists():
            raise FileNotFoundError(f"audio_timing.json not found: {audio_timing_path}")

        with open(audio_timing_path, 'r', encoding='utf-8') as f:
            audio_timing = json.load(f)

        # セクションIDと時間のマッピングを作成
        section_durations = {}

        # audio_timing.jsonの構造を確認してから処理
        if isinstance(audio_timing, list):
            # リスト形式の場合（各要素がセクション）
            for timing_section in audio_timing:
                section_id = timing_section.get('section_id')
                # 正しいキー名: char_end_times
                char_end_times = timing_section.get('char_end_times', [])
                if section_id and char_end_times:
                    section_durations[section_id] = char_end_times[-1]
                    self.logger.debug(
                        f"Section {section_id}: {char_end_times[-1]:.2f}s "
                        f"({len(char_end_times)} chars)"
                    )
        elif isinstance(audio_timing, dict):
            # 辞書形式の場合（sectionsキーを含む可能性）
            sections = audio_timing.get('sections', [])
            if not sections:
                # sectionsキーがない場合は、dictのvaluesを直接使用
                sections = [audio_timing]

            for timing_section in sections:
                section_id = timing_section.get('section_id')
                char_end_times = timing_section.get('char_end_times', [])
                if section_id and char_end_times:
                    section_durations[section_id] = char_end_times[-1]
                    self.logger.debug(
                        f"Section {section_id}: {char_end_times[-1]:.2f}s "
                        f"({len(char_end_times)} chars)"
                    )
        else:
            self.logger.error(f"❌ Unexpected audio_timing format: {type(audio_timing)}")
            raise ValueError(f"Unexpected audio_timing format: {type(audio_timing)}")

        # セクション時間が取得できたか確認
        if not section_durations:
            # デバッグ用: audio_timing.jsonの内容を表示
            self.logger.error("❌ Failed to load section durations from audio_timing.json")
            self.logger.error(f"audio_timing.json type: {type(audio_timing)}")
            if isinstance(audio_timing, list) and audio_timing:
                first_section = audio_timing[0]
                self.logger.error(f"First section keys: {list(first_section.keys())}")

            raise ValueError(
                "No section durations found in audio_timing.json. "
                "Please check the file structure."
            )

        self.logger.info(f"✅ Loaded section durations from audio_timing.json: {section_durations}")

        # classified.jsonから全画像を取得
        classified_path = self.working_dir / "03_images" / "classified.json"

        if not classified_path.exists():
            raise FileNotFoundError(f"classified.json not found: {classified_path}")

        with open(classified_path, 'r', encoding='utf-8') as f:
            classified_data = json.load(f)

        all_images = classified_data.get('images', [])
        self.logger.info(f"Total images in classified.json: {len(all_images)}")
        
        # セクションごとに画像をグループ化
        section_images = {}
        for section_id in section_durations.keys():
            section_images[section_id] = []

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
                if section_num in section_images:
                    section_images[section_num].append(file_path)

        # 各セクション内でファイル名順にソート（順序を保証）
        for section_num in section_images.keys():
            section_images[section_num].sort(key=lambda p: p.name)
            self.logger.info(f"Section {section_num}: {len(section_images[section_num])} images, duration: {section_durations[section_num]:.2f}s")

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

        # 画像タイミングモードを確認
        image_timing_config = self.phase_config.get("image_timing", {})
        timing_mode = image_timing_config.get("mode", "equal_split")
        
        if timing_mode == "keyword_match":
            # キーワードマッチングモード
            self.logger.info("🎯 Using keyword-based image timing mode")
            try:
                return self._create_concat_file_with_keyword_matching(
                    script,
                    classified_data,
                    section_durations,
                    section_images,
                    concat_file,
                    normalize_concat_path
                )
            except FileNotFoundError as e:
                self.logger.warning(f"Keyword matching failed: {e}. Falling back to equal split mode.")
                # フォールバック: 均等分割モードで続行
            except Exception as e:
                self.logger.error(f"Keyword matching error: {e}. Falling back to equal split mode.", exc_info=True)
                # フォールバック: 均等分割モードで続行
        
        # 均等分割モード（従来の方法）
        self.logger.info("📊 Using equal split image timing mode")
        
        # セクション順にソート
        sorted_section_ids = sorted(section_images.keys())

        for section_id in sorted_section_ids:
            images = section_images[section_id]
            section_duration = section_durations.get(section_id, 0)
            images_count = len(images)

            if images_count == 0:
                self.logger.warning(f"⚠️ No images found for section {section_id}")
                continue

            if section_duration == 0:
                self.logger.warning(f"⚠️ Section {section_id} duration is 0, skipping")
                continue

            # このセクションの各画像の表示時間（Legacy02と同じ均等分割）
            duration_per_image = section_duration / images_count

            self.logger.info(
                f"Section {section_id}: {images_count} images × {duration_per_image:.2f}s = {section_duration:.2f}s"
            )

            for j, image_path in enumerate(images):
                # パス正規化
                normalized_path = normalize_concat_path(image_path)
                concat_lines.append(f"file {normalized_path}")

                # 最後の画像以外はduration指定
                is_last_section = (section_id == sorted_section_ids[-1])
                is_last_image_in_section = (j == len(images) - 1)
                is_very_last_image = is_last_section and is_last_image_in_section

                if not is_very_last_image:
                    concat_lines.append(f"duration {duration_per_image:.6f}")

                total_images += 1

        # 最後の画像を再度追加（ffmpeg concat仕様）
        # durationを指定しないことで、音声の最後まで表示される
        last_section_id = sorted_section_ids[-1]
        if section_images[last_section_id]:
            last_image = section_images[last_section_id][-1]
            normalized_last = normalize_concat_path(last_image)
            concat_lines.append(f"file {normalized_last}")
            self.logger.debug(f"Added final image without duration: {last_image.name}")
        
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
    
    def _create_concat_file_with_keyword_matching(
        self,
        script: dict,
        classified_data: dict,
        section_durations: dict,
        section_images: dict,
        concat_file: Path,
        normalize_concat_path
    ) -> Path:
        """
        キーワードマッチングモードでconcatファイルを生成
        
        Args:
            script: 台本データ
            classified_data: 分類済み画像データ
            section_durations: セクション時間の辞書
            section_images: セクションごとの画像リスト
            concat_file: concatファイルのパス
            normalize_concat_path: パス正規化関数
            
        Returns:
            concatファイルのパス
        """
        # 字幕タイミングを読み込み
        subtitle_timing_path = self.working_dir / "06_subtitles" / "subtitle_timing.json"
        if not subtitle_timing_path.exists():
            self.logger.warning(
                f"subtitle_timing.json not found: {subtitle_timing_path}. "
                "Falling back to equal split mode."
            )
            # 均等分割モードにフォールバック（再帰を避けるため、直接処理）
            # この場合は通常の処理を続行するため、Noneを返して呼び出し元で処理
            raise FileNotFoundError(f"subtitle_timing.json not found: {subtitle_timing_path}")
        
        with open(subtitle_timing_path, 'r', encoding='utf-8') as f:
            subtitle_timing_data = json.load(f)
        
        subtitle_timing = subtitle_timing_data.get('subtitles', [])
        
        # ImageTimingMatcherを初期化
        keyword_match_config = self.phase_config.get("image_timing", {}).get("keyword_match", {})
        matcher = ImageTimingMatcher(
            min_duration=keyword_match_config.get("min_display_duration", 3.0),
            max_duration=keyword_match_config.get("max_display_duration", 15.0),
            section_boundary_switch=keyword_match_config.get("section_boundary_switch", True),
            exact_match_weight=keyword_match_config.get("priority", {}).get("exact_match_weight", 10.0),
            partial_match_weight=keyword_match_config.get("priority", {}).get("partial_match_weight", 5.0),
            same_section_weight=keyword_match_config.get("priority", {}).get("same_section_weight", 3.0),
            keyword_length_weight=keyword_match_config.get("priority", {}).get("keyword_length_weight", 1.0),
            logger=self.logger
        )
        
        # セクションごとに画像クリップを生成
        all_image_clips = []
        sorted_section_ids = sorted(section_durations.keys())
        
        for section_id in sorted_section_ids:
            image_clips = matcher.match_images_to_subtitles(
                script_data=script,
                classified_images=classified_data,
                subtitle_timing=subtitle_timing,
                section_id=section_id
            )
            all_image_clips.extend(image_clips)
        
        # 時間順にソート
        all_image_clips.sort(key=lambda clip: clip['start_time'])
        
        # concatファイルを生成
        concat_lines = []
        
        for i, clip in enumerate(all_image_clips):
            image_path = Path(clip['image_path'])
            start_time = clip['start_time']
            end_time = clip['end_time']
            duration = end_time - start_time
            
            if not image_path.exists():
                self.logger.warning(f"Image file not found: {image_path}")
                continue
            
            normalized_path = normalize_concat_path(image_path)
            concat_lines.append(f"file {normalized_path}")
            
            # 最後のクリップ以外はduration指定
            if i < len(all_image_clips) - 1:
                concat_lines.append(f"duration {duration:.6f}")
            
            self.logger.debug(
                f"Added image: {image_path.name} "
                f"({start_time:.3f}s - {end_time:.3f}s, {duration:.3f}s) "
                f"keyword: {clip.get('keyword_matched', 'N/A')}"
            )
        
        # 最後の画像を再度追加（ffmpeg concat仕様）
        if all_image_clips:
            last_clip = all_image_clips[-1]
            last_image_path = Path(last_clip['image_path'])
            if last_image_path.exists():
                normalized_last = normalize_concat_path(last_image_path)
                concat_lines.append(f"file {normalized_last}")
                self.logger.debug(f"Added final image without duration: {last_image_path.name}")
        
        # ファイルに書き込み
        with open(concat_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(concat_lines))
        
        # 検証
        if not concat_file.exists() or concat_file.stat().st_size == 0:
            raise ValueError("Failed to create valid concat file (empty or not created)")
        
        self.logger.info(f"✅ Concat file created with keyword matching: {len(all_image_clips)} image clips")
        self.logger.info(f"Concat file path: {concat_file}")
        
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
    
    def _create_ass_subtitles(self) -> Path:
        """
        ASS字幕ファイルを生成（改善版）

        修正点:
        1. タイミングの丸め処理を削除（全字幕を正確に表示）
        2. デバッグログを追加
        3. 空字幕のスキップ条件を厳格化

        Returns:
            ASS字幕ファイルのパス
        """
        subtitles = self._load_subtitles()

        if not subtitles:
            self.logger.warning("No subtitles found, creating empty ASS file")
            ass_path = self.phase_dir / "subtitles.ass"
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(self._get_ass_header())
            return ass_path

        # ASSヘッダー
        ass_content = self._get_ass_header()

        # 字幕生成のログ
        self.logger.info(f"Creating ASS subtitles for {len(subtitles)} entries:")

        skipped_count = 0
        created_count = 0

        # 字幕イベントを追加
        for i, subtitle in enumerate(subtitles, 1):
            # タイミングはそのまま使用（丸めない）
            start_time = self._format_ass_time(subtitle.start_time)
            end_time = self._format_ass_time(subtitle.end_time)

            # 複数行のテキストを結合（改行文字を削除）
            text_parts = []

            # text_line1の先頭の改行を削除
            line1 = subtitle.text_line1.lstrip('\n').strip()
            if line1:
                text_parts.append(line1)

            if subtitle.text_line2:
                line2 = subtitle.text_line2.strip()
                if line2:
                    text_parts.append(line2)

            if subtitle.text_line3:
                line3 = subtitle.text_line3.strip()
                if line3:
                    text_parts.append(line3)

            # 空の字幕はスキップ（ログあり）
            if not text_parts:
                self.logger.warning(
                    f"  Subtitle {i}: SKIPPED (empty text) "
                    f"[{subtitle.start_time:.3f}s - {subtitle.end_time:.3f}s]"
                )
                skipped_count += 1
                continue

            subtitle_text = '\\N'.join(text_parts)  # ASS形式の改行

            # デバッグログ（最初の30文字を表示）
            preview_text = subtitle_text.replace('\\N', ' ')[:30]
            self.logger.debug(
                f"  Subtitle {i}: {subtitle.start_time:.3f}s - {subtitle.end_time:.3f}s "
                f"'{preview_text}...'"
            )

            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{subtitle_text}\n"
            created_count += 1

        # ASSファイルに書き込み
        ass_path = self.phase_dir / "subtitles.ass"
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        self.logger.info(
            f"✅ Created ASS subtitle file: {created_count} entries created, "
            f"{skipped_count} skipped"
        )

        # 検証: セクション境界の字幕を確認
        try:
            self._verify_section_subtitles(subtitles)
        except Exception as e:
            self.logger.debug(f"Subtitle verification skipped due to error: {e}")

        return ass_path

    def verify_subtitle_timing_detailed(self) -> None:
        """
        字幕タイミングを詳細に検証（Legacy02との比較）
        """
        subtitles = self._load_subtitles()

        # audio_timing.jsonからセクション情報を取得
        timing = self._load_audio_timing()
        if not timing:
            self.logger.warning("audio_timing.json not available; skipping detailed subtitle timing verification")
            return

        if isinstance(timing, dict):
            sections = timing.get('sections', [])
        else:
            sections = timing

        self.logger.info("=" * 60)
        self.logger.info("字幕タイミング詳細検証")
        self.logger.info("=" * 60)

        # セクションの開始・終了を計算
        prev_end = 0.0
        for i, section in enumerate(sections, 1):
            # 可能なキーに対応
            char_end_times = section.get('char_end_times') or section.get('character_end_times_seconds') or []
            section_end = float(char_end_times[-1]) if char_end_times else float(section.get('duration', prev_end))
            section_start = prev_end

            self.logger.info(f"\n【Section {i}】 {section_start:.2f}s - {section_end:.2f}s")
            self.logger.info(f"  タイトル: {section.get('subtitle') or section.get('title', '')}")

            # このセクション内の字幕を抽出（±0.5秒のバッファ）
            section_subtitles = [
                s for s in subtitles
                if s.start_time >= section_start - 0.5 and s.start_time < section_end + 0.5
            ]

            for sub in section_subtitles:
                text = sub.text_line1.lstrip('\n').strip()[:30]
                self.logger.info(
                    f"  字幕 {sub.index:2d}: {sub.start_time:6.3f}s - {sub.end_time:6.3f}s "
                    f"({sub.end_time - sub.start_time:4.2f}s) '{text}...'"
                )

            if not section_subtitles:
                self.logger.warning("  ⚠️ このセクションに字幕がありません！")

            prev_end = section_end

    def _create_ass_subtitles_fixed(self) -> Path:
        """
        ASS字幕ファイルを生成（完全修正版）

        重要な修正:
        1. タイミングの微調整を削除（オリジナルのタイミングを維持）
        2. 各字幕のデバッグ情報を出力
        3. セクション境界の字幕を特別に処理（ログ）
        """
        subtitles = self._load_subtitles()

        if not subtitles:
            self.logger.warning("No subtitles found, creating empty ASS file")
            ass_path = self.phase_dir / "subtitles.ass"
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(self._get_ass_header_fixed())
            return ass_path

        # ASSヘッダー
        ass_content = self._get_ass_header_fixed()

        # セクション境界のタイミング（必要に応じて動的化可能）
        section_boundaries = []
        try:
            timing = self._load_audio_timing()
            boundaries = []
            if timing:
                sections = timing.get('sections', timing) if isinstance(timing, dict) else timing
                prev_end = 0.0
                for section in sections:
                    char_end_times = section.get('char_end_times') or section.get('character_end_times_seconds') or []
                    end = float(char_end_times[-1]) if char_end_times else float(section.get('duration', prev_end))
                    # セクション開始は前の終了
                    boundaries.append(end)
                    prev_end = end
            section_boundaries = boundaries[:-1]  # 最後の終端は境界として不要
        except Exception:
            pass

        self.logger.info(f"ASS字幕生成: {len(subtitles)}個のエントリ")

        for subtitle in subtitles:
            # オリジナルのタイミングをそのまま使用
            start_time = subtitle.start_time
            end_time = subtitle.end_time

            # セクション境界付近の字幕を特別にログ
            for boundary in section_boundaries:
                if abs(start_time - boundary) < 1.0:
                    self.logger.info(
                        f"  境界付近の字幕: {start_time:.3f}s (境界: {boundary:.2f}s)"
                    )

            # ASS形式の時刻に変換（高精度版）
            start_time_str = self._format_ass_time_precise(start_time)
            end_time_str = self._format_ass_time_precise(end_time)

            # テキスト処理（改行・空行を整理）
            text_parts = []
            line1 = subtitle.text_line1.lstrip('\n').strip()
            if line1:
                text_parts.append(line1)
            if subtitle.text_line2:
                line2 = subtitle.text_line2.strip()
                if line2:
                    text_parts.append(line2)
            if subtitle.text_line3:
                line3 = subtitle.text_line3.strip()
                if line3:
                    text_parts.append(line3)
            if not text_parts:
                continue

            subtitle_text = '\\N'.join(text_parts)

            # ASSイベント行を追加
            ass_content += f"Dialogue: 0,{start_time_str},{end_time_str},Default,,0,0,0,,{subtitle_text}\n"

        # ファイルに保存
        ass_path = self.phase_dir / "subtitles.ass"
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        self.logger.info(f"✅ ASS字幕ファイル作成完了: {ass_path.name}")

        # 検証
        self._verify_ass_file(ass_path)

        return ass_path

    def _get_ass_header_fixed(self) -> str:
        """
        ASS字幕のヘッダー（2行字幕の位置調整版）
        """
        video_width = 1920
        video_height = 1080

        # フォントサイズ
        font_size = 48

        # 黒バーの高さ: 216px
        # 黒バーの開始位置: 1080 - 216 = 864px
        # 黒バーの中央: 864 + 216/2 = 972px

        # MarginVは画面下部からの距離
        # 2行字幕を考慮して、少し下げる
        # 字幕の高さ（2行）: 約48*2 + 行間 = 約100px
        # 黒バー中央（972px）に字幕中央を配置するには：
        # MarginV = 1080 - 972 - 38 ≒ 70 （さらに約15px下げる）
        margin_v = 70  # 83→70 に変更（さらに下方向へ）

        return f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0
Timer: 100.0000
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,MS Mincho,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,2,2,10,10,{margin_v},128

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _format_ass_time_precise(self, seconds: float) -> str:
        """
        秒数をASS形式の時刻に高精度変換（センチ秒を四捨五入）
        """
        total_centisecs = int(seconds * 100 + 0.5)  # 四捨五入
        hours = total_centisecs // 360000
        minutes = (total_centisecs % 360000) // 6000
        secs = (total_centisecs % 6000) // 100
        centisecs = total_centisecs % 100
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def _verify_ass_file(self, ass_path: Path) -> None:
        """
        生成されたASSファイルを検証
        """
        try:
            with open(ass_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self.logger.warning(f"Failed to open ASS file for verification: {e}")
            return

        dialogue_lines = [l for l in lines if l.startswith('Dialogue:')]
        self.logger.info(f"ASS検証: {len(dialogue_lines)}個のDialogue行")

        # 最初の3つと最後の3つを表示
        preview_lines = dialogue_lines[:3] + dialogue_lines[-3:] if dialogue_lines else []
        for line in preview_lines:
            parts = line.split(',', 9)
            if len(parts) >= 10:
                start = parts[1]
                end = parts[2]
                text = parts[9].strip()[:30]
                self.logger.debug(f"  {start} → {end}: {text}...")

    def _build_ffmpeg_command_optimized(
        self,
        concat_file: Path,
        audio_path: Path,
        ass_path: Path,
        output_path: Path,
        bgm_data: Optional[dict]
    ) -> list:
        """
        最適化されたFFmpegコマンド

        変更点:
        1. setpts=PTS-STARTPTSフィルタを追加（タイミング同期改善）
        2. -shortest を削除（音声の長さに正確に合わせる）
        3. フォントディレクトリを明示的に指定
        """
        import multiprocessing

        is_windows = platform.system() == 'Windows'

        def normalize_path(p: Path) -> str:
            path_str = str(p.resolve())
            if is_windows:
                path_str = path_str.replace('\\', '/')
            return path_str

        threads = self.threads if self.threads > 0 else multiprocessing.cpu_count()

        # 基本コマンド
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', normalize_path(concat_file),
            '-i', normalize_path(audio_path),
        ]

        # BGM入力
        bgm_segments = []
        if bgm_data and bgm_data.get("segments"):
            bgm_segments = bgm_data.get("segments", [])
            for segment in bgm_segments:
                bgm_path = segment.get("file_path")
                if bgm_path and Path(bgm_path).exists():
                    cmd.extend(['-i', normalize_path(Path(bgm_path))])

        # ビデオフィルタ構築
        video_filters = []

        # 1. タイミング同期
        video_filters.append("setpts=PTS-STARTPTS")

        # 2. スケーリング
        video_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")

        # 3. 黒バー
        video_filters.append("drawbox=y=ih-216:color=black@1.0:width=iw:height=216:t=fill")

        # 4. ASS字幕
        if ass_path and ass_path.exists():
            ass_path_str = str(ass_path.resolve())
            # プロジェクト内のフォントディレクトリを優先的に使用
            project_root = self.config.project_root
            fonts_dir_path = project_root / "assets" / "fonts" / "cinema"
            fonts_dir_str = str(fonts_dir_path.resolve()).replace('\\', '/')
            
            if is_windows:
                ass_path_str = ass_path_str.replace('\\', '/')
                ass_path_str = ass_path_str.replace(':', '\\:')
                fonts_dir_str = fonts_dir_str.replace(':', '\\:')
                ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'"
            else:
                ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'"

            video_filters.append(ass_filter)

        # フィルタチェーン適用
        cmd.extend(['-vf', ','.join(video_filters)])

        # オーディオ処理
        if bgm_segments:
            # BGM情報のデバッグ出力
            self.logger.info("=" * 60)
            self.logger.info("BGM Configuration:")
            self.logger.info(f"  Base volume: {self.bgm_base_volume:.1%}")
            self.logger.info(f"  Amplification: {self.bgm_volume_amplification:.1f}x")
            self.logger.info(f"  Total segments: {len(bgm_segments)}")

            for i, seg in enumerate(bgm_segments):
                bgm_path = Path(seg.get('file_path', ''))
                if bgm_path.exists():
                    actual_duration = self._get_audio_duration(bgm_path)
                    need_loop = seg['duration'] > actual_duration
                    self.logger.info(
                        f"  Segment {i+1}: {seg.get('bgm_type', 'unknown')} "
                        f"[{seg['start_time']:.1f}s-{seg['start_time']+seg['duration']:.1f}s] "
                        f"BGM: {actual_duration:.1f}s, Need: {seg['duration']:.1f}s "
                        f"{'(LOOP)' if need_loop else '(NO LOOP)'}"
                    )
            self.logger.info("=" * 60)

            audio_filter = self._build_audio_filter(bgm_segments)
            cmd.extend(['-filter_complex', audio_filter])
            cmd.extend(['-map', '0:v', '-map', '[audio]'])
        else:
            cmd.extend(['-map', '0:v', '-map', '1:a'])

        # 音声の長さを取得して正確に設定
        audio_duration = self._get_audio_duration(audio_path)

        # エンコード設定
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.encode_preset,
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '48000',
            '-t', f"{audio_duration:.3f}",  # 小数点3桁まで指定
            '-threads', str(threads),
            normalize_path(output_path)
        ])

        return cmd

    def run_ffmpeg_with_timing_fix(self) -> None:
        """
        タイミング修正版のFFmpeg実行
        """
        # 1. 字幕タイミングの詳細検証
        self.logger.info("=" * 60)
        self.logger.info("Phase 1: 字幕タイミング検証")
        self.logger.info("=" * 60)
        self.verify_subtitle_timing_detailed()

        # 2. データ読み込み
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Phase 2: データ読み込み")
        self.logger.info("=" * 60)

        subtitles = self._load_subtitles()
        self.logger.info(f"✓ {len(subtitles)}個の字幕を読み込み")

        bgm_volume = self.phase_config.get('bgm', {}).get('volume', 0.1)
        bgm_data = self._load_bgm()
        self.logger.info(f"✓ BGM音量: {int(bgm_volume * 100)}%")

        # 3. concat.txt作成
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Phase 3: 画像リスト作成")
        self.logger.info("=" * 60)

        concat_file = self._create_ffmpeg_concat_file(self._load_script())
        self.logger.info(f"✓ concat.txt作成: {concat_file}")

        # 4. ASS字幕作成
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Phase 4: ASS字幕生成")
        self.logger.info("=" * 60)

        ass_path = self._create_ass_subtitles_fixed()

        # 5. FFmpeg実行
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Phase 5: FFmpeg実行")
        self.logger.info("=" * 60)

        audio_path = self._get_audio_path()
        output_dir = Path(self.config.get("paths", {}).get("output_dir", "data/output")) / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self.subject}.mp4"

        cmd = self._build_ffmpeg_command_optimized(
            concat_file=concat_file,
            audio_path=audio_path,
            ass_path=ass_path,
            output_path=output_path,
            bgm_data=bgm_data
        )

        # コマンドをログに出力（デバッグ用）
        self.logger.debug("FFmpegコマンド:")
        try:
            self.logger.debug(" ".join(cmd))
        except Exception:
            pass

        # 実行
        try:
            result = __import__('subprocess').run(cmd, capture_output=True, text=True, check=True)
            self.logger.info(f"✅ 動画生成完了: {output_path}")
        except __import__('subprocess').CalledProcessError as e:
            self.logger.error(f"FFmpeg失敗: {e.stderr}")
            raise

        # 6. 検証
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Phase 6: 出力検証")
        self.logger.info("=" * 60)

        if output_path.exists():
            file_size = output_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"✓ ファイルサイズ: {file_size:.1f} MB")

            # 動画の長さを確認
            duration_cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(output_path)
            ]

            try:
                result = __import__('subprocess').run(duration_cmd, capture_output=True, text=True, check=True)
                duration = float(result.stdout.strip())
                self.logger.info(f"✓ 動画の長さ: {duration:.2f}秒")
            except Exception:
                pass

    def _get_ass_header(self) -> str:
        """ASS字幕のヘッダーを生成（サイズ調整版）"""
        # 解像度を明示
        video_width = 1920
        video_height = 1080
        # 黒バー内の縦位置（中央108px - 20pxオフセット → 88）
        margin_v = 88
        # やや大きめのフォント
        font_size = 42

        return f"""[Script Info]
Title: Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,MS Mincho,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,{margin_v},128

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _format_ass_time(self, seconds: float) -> str:
        """
        秒数をASS形式の時刻に変換（高精度版 H:MM:SS.CS）
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        # センチ秒を四捨五入し、99でクリップ
        centisecs = round((seconds % 1) * 100)
        if centisecs >= 100:
            centisecs = 99
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def _build_ffmpeg_command_with_ass_debug(
        self,
        concat_file: Path,
        audio_path: Path,
        ass_path: Path,
        output_path: Path,
        bgm_data: Optional[dict]
    ) -> list:
        """
        FFmpegコマンドを構築（ASS字幕デバッグ版）

        追加:
        - loglevel=info（字幕処理の詳細ログ）
        - assフィルタのfontsdir指定（Windowsでのフォント探索補助）
        """
        import multiprocessing

        # Windowsの場合はパスを正規化
        is_windows = platform.system() == 'Windows'

        def normalize_path(p: Path) -> str:
            """WindowsパスをUnix形式に変換（ffmpeg互換）"""
            path_str = str(p.resolve())
            if is_windows:
                path_str = path_str.replace('\\', '/')
            return path_str

        # スレッド数を決定
        threads = self.threads if self.threads > 0 else multiprocessing.cpu_count()

        # 基本コマンド（loglevel追加）
        cmd = [
            'ffmpeg',
            '-y',
            '-loglevel', 'info',
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

        # ビデオフィルタの構築
        video_filters = []

        # 1. スケーリングとパディング
        video_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")

        # 2. 黒バーを追加（下部216px）
        video_filters.append("drawbox=y=ih-216:color=black@1.0:width=iw:height=216:t=fill")

        # 3. ASS字幕を適用（fontsdir指定）
        if ass_path and ass_path.exists():
            ass_path_str = str(ass_path.resolve()).replace('\\', '/')
            if is_windows:
                # コロンをエスケープ（C: → C\:）
                ass_path_str = ass_path_str.replace(':', '\\:')
                fonts_dir = "C\\:/Windows/Fonts"
                ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir}'"
            else:
                ass_filter = f"ass='{ass_path_str}'"
            video_filters.append(ass_filter)
            self.logger.debug(f"ASS filter: {ass_filter}")

        if video_filters:
            filter_chain = ','.join(video_filters)
            cmd.extend(['-vf', filter_chain])
            self.logger.debug(f"Video filter chain: {filter_chain}")

        # オーディオフィルタ（BGMがある場合）
        if bgm_segments:
            audio_filter = self._build_audio_filter(bgm_segments)
            cmd.extend(['-filter_complex', audio_filter])
            cmd.extend(['-map', '0:v', '-map', '[audio]'])
        else:
            cmd.extend(['-map', '0:v', '-map', '1:a'])

        # 音声の長さを取得
        audio_duration = self._get_audio_duration(audio_path)

        # エンコード設定
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.encode_preset,
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '48000',
            '-t', str(audio_duration),
            '-threads', str(threads),
            normalize_path(output_path)
        ])

        return cmd

    def analyze_subtitle_coverage(self) -> None:
        """
        字幕カバレッジを分析（どの時間帯に字幕があるか）
        """
        subtitles = self._load_subtitles()

        # 可能なら音声長を取得。失敗時は大まかな値で可視化のみ実行
        try:
            audio_path = self._get_audio_path()
            audio_duration = self._get_audio_duration(audio_path)
        except Exception:
            audio_duration = max((s.end_time for s in subtitles), default=0.0)

        self.logger.info("=== Subtitle Coverage Analysis ===")
        self.logger.info(f"Total audio duration: {audio_duration:.1f}s")
        self.logger.info(f"Total subtitles: {len(subtitles)}")

        timeline = [' '] * max(1, int(audio_duration))

        for i, sub in enumerate(subtitles, 1):
            start_idx = int(max(0.0, sub.start_time))
            end_idx = min(int(max(0.0, sub.end_time)), len(timeline) - 1)

            for idx in range(start_idx, end_idx + 1):
                if 0 <= idx < len(timeline):
                    timeline[idx] = '█'

            text_preview = sub.text_line1.lstrip('\n').strip()[:20]
            self.logger.info(
                f"  {i:2d}: {sub.start_time:6.2f}s - {sub.end_time:6.2f}s "
                f"({sub.end_time - sub.start_time:4.2f}s) '{text_preview}...'"
            )

        # タイムラインの表示（10秒ごと）
        self.logger.info("\nTimeline (█ = subtitle present):")
        for i in range(0, len(timeline), 10):
            segment = ''.join(timeline[i:i+10])
            self.logger.info(f"  {i:3d}s-{min(i+9, len(timeline)-1):3d}s: [{segment}]")

        # ギャップの検出
        self.logger.info("\nGaps in subtitles:")
        for i in range(len(subtitles) - 1):
            gap = subtitles[i + 1].start_time - subtitles[i].end_time
            if gap > 0.5:
                self.logger.warning(
                    f"  Gap of {gap:.2f}s between subtitle {i+1} and {i+2} "
                    f"({subtitles[i].end_time:.2f}s - {subtitles[i+1].start_time:.2f}s)"
                )

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

        # ASSヘッダー（フォント・スタイル定義）- Legacy02完全準拠
        ass_header = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,MS Mincho,45,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,2,2,10,10,120,1

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

    def _build_ffmpeg_command_with_ass(
        self,
        concat_file: Path,
        audio_path: Path,
        ass_path: Path,
        output_path: Path,
        bgm_data: Optional[dict]
    ) -> list:
        """
        ASS字幕を使用したFFmpegコマンドを構築（Legacy02仕様完全準拠）

        処理フロー:
        1. 画像をconcat
        2. 黒バー（下部216px、y=864）を追加
        3. ASS字幕を焼き込み
        4. BGMとナレーションをミックス

        Args:
            concat_file: 画像のconcatファイル
            audio_path: ナレーション音声
            ass_path: ASS字幕ファイル
            output_path: 出力動画パス
            bgm_data: BGMデータ

        Returns:
            FFmpegコマンド（リスト形式）
        """
        import multiprocessing

        # Windowsパス正規化
        is_windows = platform.system() == 'Windows'

        def normalize_path(p: Path) -> str:
            """WindowsパスをUnix形式に変換"""
            path_str = str(p.resolve())
            if is_windows:
                path_str = path_str.replace('\\', '/')
            return path_str

        # スレッド数
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

        # 1. 画像をリサイズ・パディング（1920x1080）
        video_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease")
        video_filters.append("pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black")

        # 2. 黒バーを追加（下部216px、y=864）
        video_filters.append("drawbox=y=864:color=black:width=1920:height=216:t=fill")

        # 3. ASS字幕を焼き込み
        # Windowsパスのエスケープ処理
        ass_path_str = normalize_path(ass_path)
        # バックスラッシュとコロンをエスケープ（ffmpegのass filter用）
        ass_path_escaped = ass_path_str.replace('\\', '\\\\\\\\').replace(':', '\\\\:')
        video_filters.append(f"ass={ass_path_escaped}")

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

        # 音声の長さを取得
        audio_duration = self._get_audio_duration(audio_path)
        self.logger.debug(f"Audio duration: {audio_duration:.2f}s (video will match this)")

        # エンコード設定
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.encode_preset,
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-threads', str(threads),
            '-t', str(audio_duration),
            '-y',
            normalize_path(output_path)
        ])

        return cmd

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
        self.logger.debug(f"Audio duration: {audio_duration:.2f}s (video will match this)")

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
            '-y',
            normalize_path(output_path)
        ])

        return cmd

    def _build_audio_filter(self, bgm_segments: List[dict]) -> str:
        """
        BGMミックス用のffmpegフィルター生成（セグメントごとの音量対応）

        戦略:
        1. 各BGMをループ・トリミング
        2. anullsrcで前に無音を追加
        3. concatで結合
        4. 各BGMに個別の音量を適用
        5. 全BGMをamixでミックス
        6. ナレーションとミックス
        """
        filters = []

        self.logger.info("=" * 60)
        self.logger.info("Building audio filter:")
        self.logger.info(f"  BGM segments: {len(bgm_segments)}")

        # ナレーション（入力1）
        filters.append("[1:a]volume=1.0[narration]")

        # 各BGMセグメントを処理
        bgm_outputs = []
        for i, segment in enumerate(bgm_segments):
            input_idx = i + 2  # BGMは入力2から
            start_time = segment.get('start_time', 0)
            duration = segment.get('duration', 0)
            fade_in = segment.get('fade_in', self.bgm_fade_in)
            fade_out = segment.get('fade_out', self.bgm_fade_out)
            bgm_volume = segment.get('volume', 0.13)  # セグメントごとの音量を取得

            # BGMファイルの実際の長さを取得
            bgm_path = Path(segment.get('file_path', ''))
            if bgm_path.exists():
                bgm_actual_duration = self._get_audio_duration(bgm_path)
            else:
                bgm_actual_duration = 30.0

            self.logger.info(
                f"  BGM {i+1} ({segment.get('bgm_type')}): "
                f"start={start_time:.1f}s, duration={duration:.1f}s, "
                f"bgm_length={bgm_actual_duration:.1f}s, "
                f"volume={bgm_volume:.1%}"
            )

            # Step 1: BGMをループ・トリミング
            if duration > bgm_actual_duration:
                loop_count = int(duration / bgm_actual_duration) + 2
                bgm_part = (
                    f"[{input_idx}:a]"
                    f"aloop=loop={loop_count}:size={int(bgm_actual_duration * 48000)},"
                    f"atrim=0:{duration},"
                    f"asetpts=PTS-STARTPTS"
                    f"[bgm{i}_trimmed]"
                )
                self.logger.info(f"    Looping {loop_count} times")
            else:
                bgm_part = (
                    f"[{input_idx}:a]"
                    f"atrim=0:{min(duration, bgm_actual_duration)},"
                    f"asetpts=PTS-STARTPTS"
                    f"[bgm{i}_trimmed]"
                )

            filters.append(bgm_part)

            # Step 2: フェード適用
            fade_part = (
                f"[bgm{i}_trimmed]"
                f"afade=t=in:st=0:d={fade_in},"
                f"afade=t=out:st={duration - fade_out}:d={fade_out},"
                f"volume={bgm_volume:.3f}"
                f"[bgm{i}_faded]"
            )
            filters.append(fade_part)

            # Step 3: 前に無音を追加（anullsrc + concat）
            if start_time > 0:
                silence_part = (
                    f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={start_time}"
                    f"[silence{i}];"
                    f"[silence{i}][bgm{i}_faded]concat=n=2:v=0:a=1"
                    f"[bgm{i}]"
                )
                self.logger.info(f"    Adding {start_time:.1f}s silence before BGM")
            else:
                silence_part = f"[bgm{i}_faded]acopy[bgm{i}]"

            filters.append(silence_part)
            bgm_outputs.append(f'[bgm{i}]')

        # Step 4: 全BGMをミックス
        if len(bgm_outputs) > 1:
            bgm_mix = f"{''.join(bgm_outputs)}amix=inputs={len(bgm_outputs)}:duration=longest:dropout_transition=0[bgm_all]"
            filters.append(bgm_mix)
            self.logger.info(f"  Mixing {len(bgm_outputs)} BGM tracks")

            # Step 5: ナレーションとミックス（ナレーションの長さに合わせる）
            final_mix = "[narration][bgm_all]amix=inputs=2:duration=first:dropout_transition=3[audio]"
        else:
            final_mix = f"[narration]{bgm_outputs[0]}amix=inputs=2:duration=first:dropout_transition=3[audio]"

        filters.append(final_mix)

        filter_str = ";".join(filters)
        self.logger.info("=" * 60)
        self.logger.debug(f"Filter string:\n{filter_str}")

        return filter_str

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
        
        # force_styleの定義（Legacy02完全準拠）
        force_style = (
            "FontName=MS Mincho,"       # Legacy02と同じMS明朝
            "FontSize=45,"              # Legacy02準拠: サイズ45
            "PrimaryColour=&HFFFFFF,"   # 白色
            "OutlineColour=&H00000000," # 黒縁取り
            "Outline=3,"                # 縁取りの太さ3
            "Shadow=2,"                 # 影を追加
            "Alignment=2,"              # 下部中央
            "MarginV=120"               # Legacy02と同じマージン
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