"""
Phase 7: 動画統合（Legacy02版）
Phase03の静止画を直接使用（moviepy）
Phase04の動画化をスキップ
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


class Phase07CompositionLegacy02(PhaseBase):
    """
    Phase 7: 動画統合（Legacy02版）

    Phase03の静止画を直接使用（moviepy）
    Phase04の動画化をスキップ
    """

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

        # Legacy02設定を読み込む
        import yaml
        legacy02_config_path = Path("config/phases/video_composition_legacy02.yaml")
        if legacy02_config_path.exists():
            with open(legacy02_config_path, 'r', encoding='utf-8') as f:
                legacy02_config = yaml.safe_load(f)
            if legacy02_config:
                self.phase_config.update(legacy02_config)

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

        # Phase 3: 画像（Legacy02ではPhase04をスキップ）
        classified_path = self.working_dir / "03_images" / "classified.json"
        required_files.append(("Classified Images", classified_path))

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
    
    def _load_images_from_phase03(self) -> Dict[int, List[Path]]:
        """
        Phase03の静止画を読み込み（全画像版）

        各セクションの全画像を読み込み、セクションIDをキーとした辞書で返す

        Returns:
            Dict[int, List[Path]]: セクションID -> 画像パスのリスト
        """
        # classified.jsonを読み込み
        classified_path = self.working_dir / "03_images" / "classified.json"

        if not classified_path.exists():
            raise FileNotFoundError(f"classified.json not found: {classified_path}")

        with open(classified_path, 'r', encoding='utf-8') as f:
            classified_data = json.load(f)

        section_images: Dict[int, List[Path]] = {}

        # 1. sections形式を試す（古い形式）
        if 'sections' in classified_data and classified_data['sections']:
            for section_data in classified_data.get('sections', []):
                section_id = section_data.get('section_id')
                images = section_data.get('images', [])

                if images:
                    section_images[section_id] = []
                    # 全ての画像を追加
                    for img_data in images:
                        image_path = Path(img_data.get('file_path'))

                        # PNG形式に変換されているはず
                        if image_path.suffix.lower() == '.jpg':
                            image_path = image_path.with_suffix('.png')

                        if image_path.exists():
                            section_images[section_id].append(image_path)
                            self.logger.debug(f"Section {section_id}: {image_path.name}")
                        else:
                            self.logger.warning(f"Image not found: {image_path}")
                else:
                    self.logger.warning(f"No images for section {section_id}")

        # 2. images形式（新しい形式）- sectionsがない場合
        elif 'images' in classified_data and classified_data['images']:
            # セクションごとにグループ化（ファイル名から抽出）
            import re

            for img_data in classified_data['images']:
                file_path = img_data.get('file_path')
                if not file_path:
                    continue

                # ファイル名からセクション番号を抽出 (section_01, section_02, etc.)
                match = re.search(r'section_(\d+)', file_path)
                if match:
                    section_id = int(match.group(1))
                    if section_id not in section_images:
                        section_images[section_id] = []

                    image_path = Path(file_path)

                    # PNG形式に変換されているはず
                    if image_path.suffix.lower() == '.jpg':
                        image_path = image_path.with_suffix('.png')

                    if image_path.exists():
                        section_images[section_id].append(image_path)
                    else:
                        self.logger.warning(f"Image not found: {image_path}")

        # 3. どちらもない場合
        else:
            self.logger.error("classified.json has neither 'sections' nor 'images' array")
            raise ValueError("Invalid classified.json format: missing 'sections' or 'images'")

        total_images = sum(len(images) for images in section_images.values())
        self.logger.info(f"Loaded {total_images} images from Phase03 across {len(section_images)} sections")
        for section_id in sorted(section_images.keys()):
            self.logger.debug(f"  Section {section_id}: {len(section_images[section_id])} images")

        return section_images

    def _load_animated_clips(self) -> List[Path]:
        """
        Phase03の静止画を読み込み（Legacy02版）

        Phase04の動画は使用せず、classified.jsonから直接画像を取得
        """
        # classified.jsonを読み込み
        classified_path = self.working_dir / "03_images" / "classified.json"

        if not classified_path.exists():
            raise FileNotFoundError(f"classified.json not found: {classified_path}")

        with open(classified_path, 'r', encoding='utf-8') as f:
            classified_data = json.load(f)

        # 画像を取得（sections形式とimages形式の両方に対応）
        image_paths = []

        # 1. sections形式を試す（古い形式）
        if 'sections' in classified_data and classified_data['sections']:
            for section_data in classified_data.get('sections', []):
                section_id = section_data.get('section_id')
                images = section_data.get('images', [])

                if images:
                    # 最初の画像を使用
                    first_image = Path(images[0].get('file_path'))

                    # PNG形式に変換されているはず
                    if first_image.suffix.lower() == '.jpg':
                        first_image = first_image.with_suffix('.png')

                    if first_image.exists():
                        image_paths.append(first_image)
                        self.logger.debug(f"Section {section_id}: {first_image.name}")
                    else:
                        self.logger.warning(f"Image not found: {first_image}")
                else:
                    self.logger.warning(f"No images for section {section_id}")

        # 2. images形式（新しい形式）- sectionsがない場合
        elif 'images' in classified_data and classified_data['images']:
            # セクションごとにグループ化（ファイル名から抽出）
            import re
            section_images = {}

            for img_data in classified_data['images']:
                file_path = img_data.get('file_path')
                if not file_path:
                    continue

                # ファイル名からセクション番号を抽出 (section_01, section_02, etc.)
                match = re.search(r'section_(\d+)', file_path)
                if match:
                    section_id = int(match.group(1))
                    if section_id not in section_images:
                        section_images[section_id] = []
                    section_images[section_id].append(file_path)

            # セクション番号順にソートして、各セクションの最初の画像を使用
            for section_id in sorted(section_images.keys()):
                first_image_path = section_images[section_id][0]
                first_image = Path(first_image_path)

                # PNG形式に変換されているはず
                if first_image.suffix.lower() == '.jpg':
                    first_image = first_image.with_suffix('.png')

                if first_image.exists():
                    image_paths.append(first_image)
                    self.logger.debug(f"Section {section_id}: {first_image.name}")
                else:
                    self.logger.warning(f"Image not found: {first_image}")

        # 3. どちらもない場合
        else:
            self.logger.error("classified.json has neither 'sections' nor 'images' array")
            raise ValueError("Invalid classified.json format: missing 'sections' or 'images'")

        self.logger.info(f"Loaded {len(image_paths)} images from Phase03")

        return image_paths

    def _create_image_slideshow(
        self,
        section_images: Dict[int, List[Path]],
        target_width: int = 1920,
        target_height: int = 1080
    ) -> 'VideoFileClip':
        """
        全セクションの画像スライドショーを作成
        各セクション内の画像は均等に分割して表示

        Args:
            section_images: セクションID -> 画像パスのリストの辞書
            target_width: 目標の幅（デフォルト: 1920）
            target_height: 目標の高さ（デフォルト: 1080）

        Returns:
            連結された動画クリップ
        """
        all_clips = []

        # スクリプトを読み込んでセクションの長さを取得
        script = self._load_script()

        for section_id in sorted(section_images.keys()):
            images = section_images[section_id]

            if len(images) == 0:
                self.logger.warning(f"Section {section_id}: No images found")
                continue

            # セクションの総時間
            section_duration = self._get_section_duration(section_id, script)

            # 各画像の表示時間（均等分割）
            duration_per_image = section_duration / len(images)

            self.logger.info(
                f"Section {section_id}: {len(images)} images × "
                f"{duration_per_image:.2f}s = {section_duration:.2f}s"
            )

            # セクション内の全画像をクリップ化
            for i, image_path in enumerate(images):
                clip = ImageClip(str(image_path))
                clip = clip.resized((target_width, target_height))
                clip = clip.with_duration(duration_per_image)
                all_clips.append(clip)

                self.logger.debug(
                    f"  Image {i+1}: {image_path.name} ({duration_per_image:.2f}s)"
                )

        # 全クリップを連結
        final_clip = concatenate_videoclips(all_clips, method="compose")

        self.logger.info(
            f"✓ Image slideshow: {final_clip.duration:.2f}s, {len(all_clips)} clips"
        )

        return final_clip

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
    
    def _get_section_duration(self, section_id: int, script: dict) -> float:
        """
        セクションの実際の音声長を取得

        audio_timing.jsonから正確な長さを取得
        """
        # audio_timing.jsonから取得
        audio_timing_path = self.working_dir / "02_audio" / "audio_timing.json"

        if audio_timing_path.exists():
            try:
                with open(audio_timing_path, 'r', encoding='utf-8') as f:
                    audio_timing = json.load(f)

                # リスト形式のaudio_timingから該当セクションを探す
                if isinstance(audio_timing, list):
                    for section_data in audio_timing:
                        if section_data.get('section_id') == section_id:
                            # 🔥 重要: durationフィールドを直接使用（優先）
                            duration = section_data.get('duration')

                            if duration is not None:
                                self.logger.info(f"Section {section_id} duration from audio_timing: {duration:.2f}s")
                                return duration

                            # フォールバック1: char_end_timesの最後の値
                            char_end_times = section_data.get('char_end_times', [])
                            if char_end_times:
                                duration = char_end_times[-1]
                                self.logger.info(f"Section {section_id} duration from char_end_times: {duration:.2f}s")
                                return duration

                            # フォールバック2: character_end_times_seconds（古い形式）
                            char_end_times = section_data.get('character_end_times_seconds', [])
                            if char_end_times:
                                duration = char_end_times[-1]
                                self.logger.info(f"Section {section_id} duration from character_end_times_seconds: {duration:.2f}s")
                                return duration

                self.logger.warning(f"Section {section_id} not found in audio_timing.json")

            except Exception as e:
                self.logger.error(f"Failed to read audio_timing.json: {e}")

        # フォールバック: スクリプトのduration
        for section in script.get('sections', []):
            if section.get('section_id') == section_id:
                duration = section.get('duration', 120.0)
                self.logger.debug(f"Section {section_id} duration from script: {duration:.2f}s")
                return duration

        # 最後のフォールバック
        self.logger.warning(f"Using default duration 120s for section {section_id}")
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
            actual_duration = self._get_section_duration(section_id, script)
            
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
    ) -> List['ImageClip']:
        """
        Phase03の静止画から動画クリップを作成（Legacy02版）

        各セクション内で複数画像を均等分割して表示

        Note: このメソッドは互換性のために残していますが、
        内部的には_create_image_slideshow()を使用しています。
        """
        self.logger.info(f"Creating image clips from Phase03 (with multi-image per section)...")

        # 全画像を読み込み（セクションごとに複数画像）
        section_images = self._load_images_from_phase03()

        # 画像スライドショーを作成
        slideshow = self._create_image_slideshow(
            section_images,
            self.resolution[0],
            self.resolution[1]
        )

        # List[ImageClip]形式で返す必要があるため、
        # スライドショー全体を1つのクリップとしてリストに入れる
        # ※ _concatenate_clips()で再度連結されますが、既に連結済みなのでそのまま返す
        return [slideshow]
    
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

        - 背景: Phase03の画像スライドショー（1920x1080フルサイズ）
        - Layer 1: 黒バーオーバーレイ（1920x216、常に表示）
        - Layer 2+: 字幕（黒バーの上に配置、タイミングで表示）

        Args:
            animated_clips: Phase03の画像パスリスト
            subtitles: 字幕データ
            total_duration: 音声の総時間（秒）

        Returns:
            合成された動画クリップ
        """
        self.logger.info("Creating split layout video (overlay mode)...")

        # レイアウト設定（設定ファイルから比率を読み取る）
        ratio = self.split_config.get('ratio', 0.8)  # デフォルトを0.8に変更
        top_height = int(1080 * ratio)
        bottom_height = 1080 - top_height

        self.logger.info(f"Layout: Full video 1920x1080 + Bottom overlay {bottom_height}px (subtitle)")

        # 1. 背景: 画像スライドショー（1920x1080フルサイズ）
        self.logger.info("Creating image slideshow (full 1920x1080)...")
        background_video = self._create_top_video_area(animated_clips, total_duration, 1080)

        # 🔥 重要: 背景動画の長さを確認
        actual_bg_duration = background_video.duration
        self.logger.info(f"Background video duration: {actual_bg_duration:.2f}s")

        # 2. 黒バーオーバーレイ（独立レイヤー、常に表示）
        self.logger.info("Creating black bar overlay...")
        black_bar = ColorClip(
            size=(1920, bottom_height),
            color=(0, 0, 0)
        ).with_duration(actual_bg_duration).with_position((0, top_height))

        self.logger.info(f"Black bar overlay: {1920}x{bottom_height}px at y={top_height}")

        # 3. 字幕クリップ（黒バーの上に配置）
        self.logger.info("Creating subtitle clips...")
        subtitle_clips = self._create_subtitle_clips_on_black_bar(
            subtitles,
            black_bar_y=top_height,
            black_bar_height=bottom_height
        )

        self.logger.info(f"Created {len(subtitle_clips)} subtitle clips")

        # 4. 全てのレイヤーを合成
        self.logger.info("Compositing all layers...")
        final_video = CompositeVideoClip([
            background_video,  # Layer 0: 背景（画像スライドショー）
            black_bar,         # Layer 1: 黒バー（常に表示）
            *subtitle_clips    # Layer 2+: 字幕（タイミングで表示）
        ])

        self.logger.info(f"✓ Overlay layout video created: {final_video.duration:.2f}s")

        return final_video

    def _create_subtitle_clips_on_black_bar(
        self,
        subtitles: List[SubtitleEntry],
        black_bar_y: int,
        black_bar_height: int
    ) -> List['ImageClip']:
        """
        黒バーの上に配置する字幕クリップを生成

        Args:
            subtitles: 字幕データ
            black_bar_y: 黒バーのY座標（864px）
            black_bar_height: 黒バーの高さ（216px）

        Returns:
            字幕クリップのリスト
        """
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        subtitle_clips = []

        # フォント読み込み
        font = self._load_japanese_font(self.subtitle_size)

        for subtitle in subtitles:
            try:
                # 字幕画像を生成（透明背景、3行対応）
                img = self._create_subtitle_image(
                    text_line1=subtitle.text_line1,
                    text_line2=subtitle.text_line2,
                    text_line3=subtitle.text_line3,
                    width=1920,
                    height=black_bar_height,
                    font=font
                )

                # ImageClipに変換
                img_array = np.array(img)
                clip = ImageClip(img_array, duration=subtitle.end_time - subtitle.start_time)
                clip = clip.with_start(subtitle.start_time)

                # 黒バーの位置に配置
                clip = clip.with_position((0, black_bar_y))

                subtitle_clips.append(clip)

            except Exception as e:
                self.logger.warning(f"Failed to create subtitle clip for index {subtitle.index}: {e}")
                continue

        return subtitle_clips

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
        上部の動画エリアを生成（画像スライドショー）

        - Phase03の画像を 1920 x area_height にリサイズ
        - 各セクション内で複数画像を均等分割して表示
        - 連結してスライドショー化

        Args:
            clip_paths: Phase03の画像パスリスト（互換性のため残す、未使用）
            duration: 総時間（音声の長さ）
            area_height: エリアの高さ（864px）

        Returns:
            連結された動画クリップ
        """
        width = 1920
        height = area_height  # 864px（全体1080の80%）

        self.logger.info("Creating image slideshow from Phase03 (with multi-image per section)...")

        # 全画像を読み込み（セクションごとに複数画像）
        section_images = self._load_images_from_phase03()

        # 画像スライドショーを作成（1920x1080）
        slideshow = self._create_image_slideshow(section_images, width, 1080)

        # area_heightが1080と異なる場合はリサイズ
        if height != 1080:
            slideshow = self._resize_clip_for_split_layout(slideshow, width, height)
            self.logger.info(f"Resized slideshow to {width}x{height}")

        return slideshow

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