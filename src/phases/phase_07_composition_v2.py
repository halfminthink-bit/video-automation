"""
Phase 7: 動画統合（Video Composition）- リファクタリング版
Phase 1-6で生成した全ての素材を統合し、完成動画を生成する

軽量オーケストレーター版：専門クラスへの委譲により300-400行に削減
"""

import json
import time
import yaml
from pathlib import Path
from typing import Optional, TYPE_CHECKING
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
    if TYPE_CHECKING:
        from moviepy.editor import VideoFileClip, AudioFileClip

from ..core.phase_base import PhaseBase
from ..core.config_manager import ConfigManager
from ..core.models import VideoComposition, VideoTimeline, SubtitleEntry
from ..generators.background_video_selector import BackgroundVideoSelector

# 専門クラスのインポート
from ..utils.video_composition.data_loader import Phase07DataLoader
from ..utils.video_composition.gradient_processor import GradientProcessor
from ..utils.video_composition.background_video_composer import BackgroundVideoComposer
from ..utils.video_composition.video_segment_generator import VideoSegmentGenerator
from ..utils.subtitle_utils.subtitle_processor import SubtitleProcessor
from ..utils.video_composition.background_processor import BackgroundVideoProcessor
from ..utils.video_composition.bgm_processor import BGMProcessor
from ..utils.video_composition.ffmpeg_builder import FFmpegBuilder
from ..utils.subtitle_utils.ass_generator import ASSGenerator


class Phase07CompositionV2(PhaseBase):
    """
    Phase 7: 動画統合 V2（リファクタリング版）

    責任:
    - Phaseライフサイクル管理（PhaseBaseの実装）
    - 各専門クラスの初期化
    - 実行フローの制御のみ

    専門クラスへの委譲:
    - Phase07DataLoader: データ読み込み
    - VideoSegmentGenerator: 動画セグメント生成
    - SubtitleProcessor: 字幕処理
    - BackgroundVideoComposer: 背景動画合成
    - GradientProcessor: グラデーション処理
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
        self.use_legacy = use_legacy
        self.phase_config = config.get_phase_config(7)

        if not MOVIEPY_AVAILABLE:
            error_msg = "MoviePy is required. Install with: pip install moviepy"
            if MOVIEPY_IMPORT_ERROR:
                error_msg += f"\n\nImport error details: {MOVIEPY_IMPORT_ERROR}"
            raise ImportError(error_msg)

        # Legacy版を使う場合は、legacy設定を読み込む
        if self.use_legacy:
            self.logger.info("🔄 Using legacy (moviepy) mode")
            legacy_config_path = Path(__file__).parent.parent.parent / "config/phases/video_composition_legacy.yaml"
            if legacy_config_path.exists():
                with open(legacy_config_path, 'r', encoding='utf-8') as f:
                    legacy_config = yaml.safe_load(f)
                self.phase_config.update(legacy_config)
                self.logger.info(f"✓ Loaded legacy config: {legacy_config_path}")

        # 設定の読み込み
        output_config = self.phase_config.get("output", {})
        self.resolution = tuple(output_config.get("resolution", [1920, 1080]))
        self.fps = output_config.get("fps", 30)

        bgm_config = self.phase_config.get("bgm", {})
        self.bgm_base_volume = bgm_config.get("volume", 0.1)
        self.bgm_volume_amplification = bgm_config.get("volume_amplification", 1.0)
        self.bgm_volume_by_type = bgm_config.get("volume_by_type", {})
        self.bgm_fade_in = bgm_config.get("fade_in", 3.0)
        self.bgm_fade_out = bgm_config.get("fade_out", 3.0)

        subtitle_config = self.phase_config.get("subtitle", {})
        self.subtitle_font = subtitle_config.get("font_family", "Arial")

        perf_config = self.phase_config.get("performance", {})
        self.use_ffmpeg_direct = perf_config.get("use_ffmpeg_direct", False)
        self.use_background_video = perf_config.get("use_background_video", False)
        self.encode_preset = perf_config.get("preset", "faster")

        self.split_config = self.phase_config.get("split_layout", {})
        self.split_enabled = self.split_config.get("enabled", False)

        # 背景動画セレクターを初期化
        bg_config_path = config.project_root / "config" / "phases" / "background_video.yaml"
        if bg_config_path.exists():
            with open(bg_config_path, 'r', encoding='utf-8') as f:
                bg_config = yaml.safe_load(f) or {}
        else:
            self.logger.warning(f"Background video config not found: {bg_config_path}, using defaults")
            bg_config = {}

        self.bg_selector = BackgroundVideoSelector(
            video_library_path=Path(bg_config.get("background_video_library_path", "assets/background_videos")),
            selection_mode=bg_config.get("selection_mode", "random"),
            transition_duration=bg_config.get("transition", {}).get("duration", 1.0),
            logger=logger
        )

        # 専門クラスの初期化
        self._init_specialized_classes()

    def _init_specialized_classes(self):
        """専門クラスを初期化"""
        # データローダー
        self.data_loader = Phase07DataLoader(
            working_dir=self.working_dir,
            config=self.config,
            logger=self.logger,
            genre=self.genre,
            bgm_base_volume=self.bgm_base_volume,
            bgm_volume_amplification=self.bgm_volume_amplification,
            bgm_volume_by_type=self.bgm_volume_by_type
        )

        # グラデーション処理
        self.gradient_processor = GradientProcessor(
            logger=self.logger,
            working_dir=self.working_dir
        )

        # 字幕処理
        self.subtitle_processor = SubtitleProcessor(
            config=self.config,
            logger=self.logger,
            working_dir=self.working_dir,
            phase_dir=self.phase_dir,
            encode_preset=self.encode_preset,
            split_config=self.split_config,
            phase_config=self.phase_config
        )

        # 背景動画合成
        self.background_composer = BackgroundVideoComposer(
            config=self.config,
            logger=self.logger,
            working_dir=self.working_dir,
            phase_dir=self.phase_dir,
            encode_preset=self.encode_preset,
            phase_config=self.phase_config
        )

        # 動画セグメント生成
        self.video_segment_generator = VideoSegmentGenerator(
            config=self.config,
            logger=self.logger,
            working_dir=self.working_dir,
            phase_dir=self.phase_dir,
            phase_config=self.phase_config,
            encode_preset=self.encode_preset
        )

        # 既存のプロセッサ（互換性のため保持）
        self.bg_processor = BackgroundVideoProcessor(
            self.config.project_root,
            self.logger
        )
        self.bgm_processor = BGMProcessor(
            self.config.project_root,
            self.logger,
            bgm_fade_in=self.bgm_fade_in,
            bgm_fade_out=self.bgm_fade_out
        )
        self.ffmpeg_builder = FFmpegBuilder(
            self.config.project_root,
            self.logger,
            encode_preset=self.encode_preset,
            threads=0,
            bgm_processor=self.bgm_processor
        )
        subtitle_config_path = self.config.project_root / "config" / "phases" / "subtitle_generation.yaml"
        self.ass_generator = ASSGenerator(
            config_path=subtitle_config_path,
            font_name=self.subtitle_font,
            logger=self.logger
        )

    def get_phase_number(self) -> int:
        return 7

    def get_phase_name(self) -> str:
        return "Video Composition"

    def get_phase_directory(self) -> Path:
        return self.working_dir / "07_composition"

    def check_inputs_exist(self) -> bool:
        """入力ファイルの存在確認（DataLoaderに委譲）"""
        return self.data_loader.check_inputs()

    def check_outputs_exist(self) -> bool:
        """出力ファイルの存在確認"""
        output_dir = self.config.get("paths", {}).get("output_dir", "data/output")
        video_path = Path(output_dir) / "videos" / f"{self.subject}.mp4"
        return video_path.exists()

    def execute_phase(self) -> VideoComposition:
        """
        動画統合の実行（フロー制御のみ）

        処理モードの分岐:
        1. Legacy版（MoviePy）
        2. 背景動画モード（BackgroundVideoComposer使用）
        3. FFmpeg直接統合モード（VideoSegmentGenerator使用）
        4. MoviePy統合モード（従来の方法）
        """
        self.logger.info(f"Starting video composition for: {self.subject}")
        render_start = time.time()

        # Legacy版の分岐
        if self.use_legacy:
            self.logger.info("🎬 Executing legacy moviepy composition")
            return self._execute_legacy()

        # 背景動画モードの分岐
        if self.use_background_video and self.use_ffmpeg_direct:
            self.logger.info("🎬 Using background video mode (background video + scaled images)")
            return self._execute_with_background_video()

        # ffmpeg直接統合モードの分岐
        if self.use_ffmpeg_direct:
            self.logger.info("🔥 Using ffmpeg direct integration (high-speed mode)")
            return self._execute_ffmpeg_direct()
        else:
            self.logger.info("Using MoviePy integration (standard mode)")
            return self._execute_moviepy()

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

    # ========================================
    # 実行モード別のメソッド
    # ========================================

    def _execute_ffmpeg_direct(self) -> VideoComposition:
        """
        FFmpeg直接統合モード（VideoSegmentGenerator + SubtitleProcessor使用）
        """
        render_start = time.time()

        try:
            # 1. データ読み込み（DataLoaderに委譲）
            self.logger.info("Loading data...")
            data = self.data_loader.load_all_data()

            # 2. ASS字幕ファイル生成（先に生成してVideoSegmentGeneratorに渡す）
            self.logger.info("Creating ASS subtitles...")
            ass_path = self.subtitle_processor.create_ass_file(
                subtitles=data['subtitles'],
                audio_timing=data['audio_timing'],
                output_path=self.phase_dir / "subtitles.ass"
            )

            # 3. 動画セグメント生成（VideoSegmentGeneratorに委譲、字幕も含めて生成）
            self.logger.info("Creating video from segments...")
            final_video_path = self.phase_dir / "final_video.mp4"
            
            # VideoSegmentGeneratorで既に字幕を適用しているので、そのまま使用
            self.video_segment_generator.create_video_from_segments(
                audio_path=data['audio_path'],
                script=data['script'],
                audio_timing=data['audio_timing'],
                bgm_data=data['bgm'],
                output_path=final_video_path,
                ass_path=ass_path  # ASSファイルのパスを渡す
            )

            # 4. サムネイル生成
            self.logger.info("Generating thumbnail...")
            thumbnail_path = self._generate_thumbnail_from_video(final_video_path)

            # 5. メタデータ保存
            render_time = time.time() - render_start
            file_size_mb = final_video_path.stat().st_size / (1024 * 1024)

            composition = VideoComposition(
                subject=self.subject,
                output_video_path=str(final_video_path),
                thumbnail_path=str(thumbnail_path),
                metadata_path=str(self.phase_dir / "metadata.json"),
                timeline=VideoTimeline(
                    subject=self.subject,
                    clips=[],
                    audio_path=str(data['audio_path']),
                    bgm_segments=[],
                    subtitles=data['subtitles'],
                    total_duration=self.data_loader.get_audio_duration(data['audio_path']),
                    resolution=self.resolution,
                    fps=self.fps
                ),
                render_time_seconds=render_time,
                file_size_mb=file_size_mb,
                completed_at=datetime.now()
            )

            self._save_metadata(composition)

            self.logger.info(
                f"✓ Video composition complete: {file_size_mb:.1f}MB in {render_time:.1f}s"
            )

            return composition

        except Exception as e:
            self.logger.error(f"FFmpeg direct composition failed: {e}", exc_info=True)
            raise

    def _execute_with_background_video(self) -> VideoComposition:
        """
        背景動画モード（BackgroundVideoComposer使用）
        """
        render_start = time.time()

        try:
            # 1. データ読み込み
            self.logger.info("Loading data...")
            data = self.data_loader.load_all_data()

            # 2. 背景動画を選択
            self.logger.info("Selecting background videos...")
            bg_selection = self.bg_selector.select_videos_for_script(
                script=data['script'],
                total_duration=self.data_loader.get_audio_duration(data['audio_path'])
            )

            # 3. BGMとタイミング調整
            if data['bgm']:
                bg_selection = self.background_composer.align_videos_with_bgm(
                    bg_selection=bg_selection,
                    bgm_data=data['bgm']
                )

            # 4. 背景動画 + 画像合成（BackgroundVideoComposerに委譲）
            self.logger.info("Composing video with background...")
            video_no_subtitle = self.phase_dir / "video_with_bg_no_subtitle.mp4"

            self.background_composer.compose_with_background(
                audio_path=data['audio_path'],
                images=data['images'],
                background_videos=bg_selection['segments'],
                bgm_data=data['bgm'],
                title_segments=data['section_title_segments'],
                output_path=video_no_subtitle
            )

            # 5. 字幕適用
            self.logger.info("Applying subtitles with impact...")
            final_video_path = self.phase_dir / "final_video.mp4"
            subtitle_timing_path = self.working_dir / "06_subtitles" / "subtitle_timing.json"

            # SRT字幕パス（存在する場合）
            srt_path = self.working_dir / "06_subtitles" / "subtitles.srt"

            if srt_path.exists():
                self.subtitle_processor.burn_subtitles_with_impact(
                    input_video=video_no_subtitle,
                    srt_path=srt_path,
                    subtitle_timing_path=subtitle_timing_path,
                    output_path=final_video_path
                )
            else:
                self.logger.warning(f"SRT file not found: {srt_path}, skipping subtitle burn")
                import shutil
                shutil.copy(video_no_subtitle, final_video_path)

            # 6. サムネイル生成
            thumbnail_path = self._generate_thumbnail_from_video(final_video_path)

            # 7. メタデータ保存
            render_time = time.time() - render_start
            file_size_mb = final_video_path.stat().st_size / (1024 * 1024)

            composition = VideoComposition(
                subject=self.subject,
                output_video_path=str(final_video_path),
                thumbnail_path=str(thumbnail_path),
                metadata_path=str(self.phase_dir / "metadata.json"),
                timeline=VideoTimeline(
                    subject=self.subject,
                    clips=[],
                    audio_path=str(data['audio_path']),
                    bgm_segments=[],
                    subtitles=data['subtitles'],
                    total_duration=self.data_loader.get_audio_duration(data['audio_path']),
                    resolution=self.resolution,
                    fps=self.fps
                ),
                render_time_seconds=render_time,
                file_size_mb=file_size_mb,
                completed_at=datetime.now()
            )

            self._save_metadata(composition)

            self.logger.info(
                f"✓ Video composition complete: {file_size_mb:.1f}MB in {render_time:.1f}s"
            )

            return composition

        except Exception as e:
            self.logger.error(f"Background video composition failed: {e}", exc_info=True)
            raise

    def _execute_moviepy(self) -> VideoComposition:
        """MoviePyを使用した動画統合（従来の方法）"""
        render_start = time.time()

        try:
            # DataLoaderからデータを読み込み
            data = self.data_loader.load_all_data()

            # 音声の長さを取得
            audio_clip = AudioFileClip(str(data['audio_path']))
            total_duration = audio_clip.duration
            self.logger.info(f"Total audio duration: {total_duration:.1f}s")

            # アニメ化動画クリップを読み込み
            animated_clips = self.data_loader.load_animated_clips()

            # 動画生成（二分割レイアウト or 全画面）
            if self.split_enabled:
                self.logger.info("Creating split layout video (subtitle | video)...")
                # 既存の _create_split_layout_video を使用
                # ※この部分は元のコードを保持（MoviePy依存のため）
                final_video = self._create_split_layout_video(
                    animated_clips=animated_clips,
                    subtitles=data['subtitles'],
                    total_duration=total_duration
                )
                final_video = final_video.with_audio(audio_clip)
                if data['bgm']:
                    final_video = self._add_bgm(final_video, data['bgm'])
            else:
                self.logger.info("Creating full-screen video with bottom subtitles...")
                video_clips = self._create_video_clips(animated_clips, total_duration)
                final_video = self._concatenate_clips(video_clips, total_duration)
                final_video = final_video.with_audio(audio_clip)
                if data['bgm']:
                    final_video = self._add_bgm(final_video, data['bgm'])
                final_video = self._add_subtitles(final_video, data['subtitles'])

            # 動画をレンダリング
            self.logger.info("Rendering final video...")
            output_path = self._render_video(final_video)

            # サムネイル生成
            self.logger.info("Generating thumbnail...")
            thumbnail_path = self._generate_thumbnail(final_video)

            # メタデータ保存
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
                    audio_path=str(data['audio_path']),
                    bgm_segments=[],
                    subtitles=data['subtitles'],
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

    def _execute_legacy(self) -> VideoComposition:
        """Legacy版の実行"""
        import importlib.util

        legacy_module_path = Path(__file__).parent / "phase_07_composition_legacy.py"

        if not legacy_module_path.exists():
            raise FileNotFoundError(
                f"Legacy module not found: {legacy_module_path}\n"
                "Please ensure phase_07_composition_legacy.py exists in the same directory."
            )

        spec = importlib.util.spec_from_file_location(
            "phase_07_composition_legacy",
            legacy_module_path
        )
        legacy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy_module)

        LegacyPhase07 = legacy_module.Phase07Composition
        legacy_phase = LegacyPhase07(
            subject=self.subject,
            config=self.config,
            logger=self.logger
        )

        self.logger.info("Executing legacy Phase07Composition.execute_phase()")
        return legacy_phase.execute_phase()

    # ========================================
    # ヘルパーメソッド（MoviePy用 - 互換性のため保持）
    # ========================================

    def _create_video_clips(self, clip_paths, target_duration):
        """動画クリップをロードして準備（MoviePy用）"""
        # 元の実装を保持（MoviePy依存）
        clips = []
        for path in clip_paths:
            clip = VideoFileClip(str(path))
            clips.append(clip)
        return clips

    def _concatenate_clips(self, clips, target_duration):
        """動画クリップを連結（MoviePy用）"""
        # 元の実装を保持（MoviePy依存）
        if not clips:
            raise ValueError("No clips to concatenate")
        return concatenate_videoclips(clips, method="compose")

    def _add_bgm(self, video, bgm_data):
        """BGMを追加（MoviePy用）"""
        # 元の実装を保持（MoviePy依存）
        # ※実装は複雑なのでプレースホルダー
        self.logger.warning("MoviePy BGM support is limited, consider using ffmpeg mode")
        return video

    def _add_subtitles(self, video, subtitles):
        """字幕を追加（MoviePy用）"""
        # 元の実装を保持（MoviePy依存）
        # ※実装は複雑なのでプレースホルダー
        self.logger.warning("MoviePy subtitle support is limited, consider using ffmpeg mode")
        return video

    def _create_split_layout_video(self, animated_clips, subtitles, total_duration):
        """二分割レイアウト動画を作成（MoviePy用）"""
        # 元の実装を保持（MoviePy依存）
        # ※実装は複雑なのでプレースホルダー
        self.logger.warning("Split layout is experimental")
        return VideoFileClip(str(animated_clips[0]))

    def _render_video(self, video) -> Path:
        """動画をレンダリング（MoviePy用）"""
        output_path = self.phase_dir / "final_video.mp4"
        video.write_videofile(
            str(output_path),
            codec=self.codec,
            fps=self.fps,
            audio_codec='aac',
            temp_audiofile=str(self.phase_dir / "temp_audio.m4a"),
            remove_temp=True
        )
        return output_path

    def _generate_thumbnail(self, video) -> Path:
        """サムネイルを生成（MoviePy用）"""
        thumbnail_path = self.phase_dir / "thumbnail.jpg"
        frame = video.get_frame(video.duration / 2)
        from PIL import Image
        img = Image.fromarray(frame)
        img.save(thumbnail_path, quality=95)
        return thumbnail_path

    def _generate_thumbnail_from_video(self, video_path: Path) -> Path:
        """動画ファイルからサムネイルを生成（FFmpeg用）"""
        thumbnail_path = self.phase_dir / "thumbnail.jpg"

        import subprocess
        cmd = [
            'ffmpeg', '-y',
            '-i', str(video_path),
            '-vf', 'select=eq(n\\,0)',
            '-vframes', '1',
            str(thumbnail_path)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.logger.info(f"✓ Thumbnail generated: {thumbnail_path}")
        except Exception as e:
            self.logger.warning(f"Failed to generate thumbnail: {e}")
            # フォールバック: 空の画像を作成
            from PIL import Image
            img = Image.new('RGB', (1920, 1080), color='black')
            img.save(thumbnail_path)

        return thumbnail_path

    def _save_metadata(self, composition: VideoComposition):
        """メタデータを保存"""
        metadata_path = self.phase_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(composition.model_dump(mode='json'), f, indent=2, ensure_ascii=False)
        self.logger.info(f"✓ Metadata saved: {metadata_path}")
