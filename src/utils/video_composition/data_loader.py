"""
Phase 07 データローダー

Phase 7（動画統合）で必要な全データの読み込みを担当する専門クラス
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from moviepy import AudioFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    AudioFileClip = None

from ...core.models import SubtitleEntry
from ...core.config_manager import ConfigManager


class Phase07DataLoader:
    """
    Phase 07 データローダー

    責任:
    - 台本、音声、字幕、BGM、画像などの読み込み
    - 音声タイミングデータの読み込み
    - 入力ファイルの存在確認
    """

    def __init__(
        self,
        working_dir: Path,
        config: ConfigManager,
        logger,
        genre: Optional[str] = None,
        bgm_base_volume: float = 0.1,
        bgm_volume_amplification: float = 1.0,
        bgm_volume_by_type: Optional[Dict[str, float]] = None
    ):
        """
        初期化

        Args:
            working_dir: 作業ディレクトリ（data/subjects/{subject}/）
            config: ConfigManager インスタンス
            logger: ロガー
            genre: ジャンル（BGM選択に使用）
            bgm_base_volume: BGM基本音量
            bgm_volume_amplification: BGM音量増幅率
            bgm_volume_by_type: BGMタイプごとの音量倍率
        """
        self.working_dir = working_dir
        self.config = config
        self.logger = logger
        self.genre = genre
        self.bgm_base_volume = bgm_base_volume
        self.bgm_volume_amplification = bgm_volume_amplification
        self.bgm_volume_by_type = bgm_volume_by_type or {}

        # BGMProcessor（音声長取得に必要）
        from .bgm_processor import BGMProcessor
        from .background_processor import BackgroundVideoProcessor

        bgm_fade_in = 3.0
        bgm_fade_out = 3.0
        self.bgm_processor = BGMProcessor(
            config.project_root,
            logger,
            bgm_fade_in=bgm_fade_in,
            bgm_fade_out=bgm_fade_out
        )
        self.bg_processor = BackgroundVideoProcessor(
            config.project_root,
            logger
        )

    def load_all_data(self) -> Dict[str, Any]:
        """
        すべてのデータを一括読み込み

        Returns:
            dict: {
                'script': dict,
                'audio_path': Path,
                'audio_timing': dict,
                'subtitles': List[SubtitleEntry],
                'bgm': Optional[dict],
                'images': List[Path],
                'section_title_segments': List[dict]
            }
        """
        self.logger.info("Loading all data...")

        script = self.load_script()
        audio_path = self.get_audio_path()
        audio_timing = self.load_audio_timing()
        subtitles = self.load_subtitles()
        bgm = self.load_bgm()
        section_title_segments = self.detect_section_title_segments()

        # 画像は台本が必要
        images = self.get_images_for_sections(script)

        return {
            'script': script,
            'audio_path': audio_path,
            'audio_timing': audio_timing,
            'subtitles': subtitles,
            'bgm': bgm,
            'images': images,
            'section_title_segments': section_title_segments
        }

    def check_inputs(self) -> bool:
        """
        入力ファイルの存在確認

        Returns:
            bool: すべての入力ファイルが存在する場合 True
        """
        required_files = []

        # Phase 1: 台本
        script_path = self.working_dir / "01_script" / "script.json"
        required_files.append(("Script", script_path))

        # Phase 2: 音声
        audio_path = self.working_dir / "02_audio" / "narration_full.mp3"
        required_files.append(("Audio", audio_path))

        # Phase 3: 画像
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

    # ========================================
    # データ読み込みメソッド
    # ========================================

    def load_script(self) -> dict:
        """台本データを読み込み"""
        script_path = self.working_dir / "01_script" / "script.json"
        with open(script_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_audio_path(self) -> Path:
        """音声ファイルパスを取得"""
        return self.working_dir / "02_audio" / "narration_full.mp3"

    def get_audio_duration(self, audio_path: Path) -> float:
        """
        音声ファイルの長さを取得

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            音声の長さ（秒）
        """
        return self.bgm_processor.get_audio_duration(audio_path)

    def get_video_duration(self, video_path: Path) -> float:
        """
        動画ファイルの長さを取得

        Args:
            video_path: 動画ファイルのパス

        Returns:
            動画の長さ（秒）
        """
        return self.bg_processor.get_video_duration(video_path)

    def load_audio_timing(self, raise_on_missing: bool = False) -> Optional[dict]:
        """
        Phase 2の音声タイミングデータを読み込み

        Args:
            raise_on_missing: Trueの場合、ファイルが見つからない場合に例外を発生させる

        Returns:
            音声タイミングデータ（辞書形式）。見つからない場合は None

        Raises:
            FileNotFoundError: raise_on_missing=True でファイルが見つからない場合
        """
        audio_timing_path = self.working_dir / "02_audio" / "audio_timing.json"

        if not audio_timing_path.exists():
            if raise_on_missing:
                raise FileNotFoundError(f"audio_timing.json not found: {audio_timing_path}")
            else:
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
            if raise_on_missing:
                raise
            return None

    def get_section_duration(self, section_id: int, audio_timing: Optional[dict]) -> float:
        """
        セクションの実際の音声長を取得

        Args:
            section_id: セクションID
            audio_timing: audio_timing.jsonの内容（リスト形式または辞書形式）

        Returns:
            セクションの長さ（秒）
        """
        if not audio_timing:
            # フォールバック: 音声ファイルから直接取得
            audio_file = self.working_dir / "02_audio" / "sections" / f"section_{section_id:02d}.mp3"
            if audio_file.exists():
                try:
                    if not MOVIEPY_AVAILABLE:
                        self.logger.warning("MoviePy not available, using default duration")
                        return 120.0

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
                if not MOVIEPY_AVAILABLE:
                    self.logger.warning("MoviePy not available, using default duration")
                    return 120.0

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

    def load_subtitles(self) -> List[SubtitleEntry]:
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

    def detect_section_title_segments(self) -> List[dict]:
        """
        subtitle_timing.jsonからセクションタイトル区間を検出

        Returns:
            セクションタイトル区間のリスト [{'start': float, 'end': float, 'text': str}, ...]
        """
        subtitle_file = self.working_dir / "06_subtitles" / "subtitle_timing.json"

        if not subtitle_file.exists():
            self.logger.warning(f"subtitle_timing.json not found: {subtitle_file}")
            return []

        try:
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                subtitle_data = json.load(f)
                subtitles = subtitle_data.get('subtitles', [])

            # セクションタイトル区間を検出
            title_segments = []
            for subtitle in subtitles:
                # special_typeが"section_title"の字幕を検出
                if subtitle.get('special_type') == 'section_title':
                    title_segments.append({
                        'start': subtitle['start_time'],
                        'end': subtitle['end_time'],
                        'text': subtitle.get('text_line1', '')
                    })

            # 🔍 デバッグ: special_typeが設定されていない場合、テキストパターンで検出（一時的フォールバック）
            if len(title_segments) == 0:
                self.logger.warning("  ⚠️ No section title segments found via special_type!")
                self.logger.info("  🔍 [DEBUG] Trying fallback: detecting by text pattern...")

                # セクションタイトルのパターン（「起：」「承転：」「結：」など）
                title_patterns = ['起：', '承転：', '結：', '序：', '破：', '急：']

                for subtitle in subtitles:
                    text = subtitle.get('text_line1', '')
                    # パターンマッチング
                    if any(pattern in text for pattern in title_patterns):
                        title_segments.append({
                            'start': subtitle['start_time'],
                            'end': subtitle['end_time'],
                            'text': text
                        })
                        self.logger.info(f"  ✅ [FALLBACK] Detected title by pattern: {subtitle['start_time']:.2f}s - {subtitle['end_time']:.2f}s: '{text}'")

            self.logger.info(f"🔍 [DEBUG] Detected {len(title_segments)} section title segments")
            if len(title_segments) == 0:
                self.logger.warning("  ⚠️ No section title segments found! Check subtitle_timing.json for 'special_type': 'section_title'")
                # デバッグ: 全字幕を確認
                self.logger.info("  [DEBUG] All subtitles in file:")
                for i, sub in enumerate(subtitles[:10]):  # 最初の10個のみ表示
                    self.logger.info(f"    [{i}] special_type={sub.get('special_type')}, text={sub.get('text_line1', '')[:30]}")
            else:
                for seg in title_segments:
                    self.logger.info(f"  ✅ {seg['start']:.2f}s - {seg['end']:.2f}s: '{seg['text']}'")

            return title_segments

        except Exception as e:
            self.logger.error(f"Failed to detect section title segments: {e}", exc_info=True)
            return []

    def load_animated_clips(self) -> List[Path]:
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

    def load_bgm(self) -> Optional[dict]:
        """BGMデータを読み込み（実際の音声長を使用）"""

        # ジャンル設定から BGM パスを取得
        if self.genre:
            genre_config = self.config.get_genre_config(self.genre)
            bgm_library_config = genre_config.get("bgm_library", "assets/bgm")
            self.logger.info(f"Using genre-specific BGM library: {bgm_library_config} (genre={self.genre})")
        else:
            # フォールバック: ジャンルが指定されていない場合の処理
            # 1. まず、利用可能なジャンルフォルダを探す
            default_bgm_path = Path(__file__).parent.parent.parent.parent / "assets" / "bgm"
            available_genres = []
            if default_bgm_path.exists():
                for item in default_bgm_path.iterdir():
                    if item.is_dir() and (item / "opening").exists() and (item / "main").exists():
                        available_genres.append(item.name)

            # 2. 利用可能なジャンルがある場合は、最初のものを使用（通常はijin）
            if available_genres:
                inferred_genre = available_genres[0]  # 通常は "ijin"
                bgm_library_config = f"assets/bgm/{inferred_genre}"
                self.logger.info(
                    f"No genre specified, inferred genre '{inferred_genre}' from BGM folder structure. "
                    f"Using: {bgm_library_config} (available genres: {', '.join(available_genres)})"
                )
            else:
                # 3. ジャンルフォルダが見つからない場合はデフォルトパスを使用
                bgm_library_config = self.config.get("paths", {}).get("bgm_library", "assets/bgm")
                self.logger.warning(
                    f"No genre specified and no genre folders found in {default_bgm_path}. "
                    f"Using default BGM library: {bgm_library_config}"
                )

        bgm_base_path = Path(bgm_library_config)

        # 相対パスの場合はプロジェクトルートからの絶対パスに変換
        if not bgm_base_path.is_absolute():
            project_root = Path(__file__).parent.parent.parent.parent
            bgm_base_path = project_root / bgm_base_path

        self.logger.info(f"BGM library path resolved: {bgm_base_path}")

        if not bgm_base_path.exists():
            self.logger.warning(f"BGM library not found: {bgm_base_path}")
            return None

        # 台本を読み込んでBGM情報を取得
        script = self.load_script()

        # 音声タイミングデータを読み込み（実際の音声長を取得するため）
        audio_timing = self.load_audio_timing()

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
                'duration': self.get_section_duration(section_id, audio_timing),
                'title': section.get('title', '')
            })

        # Section IDの順序でソート（アルファベット順ではなく）
        sorted_bgm_types = sorted(bgm_groups.keys(), key=lambda bgm_type: section_order[bgm_type])

        # 各BGMタイプごとにセグメントを作成
        for bgm_type in sorted_bgm_types:
            sections = bgm_groups[bgm_type]
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
                "volume": self.get_bgm_volume_for_type(bgm_type)
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

    def get_bgm_volume_for_type(self, bgm_type: str) -> float:
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

    def get_images_for_sections(self, script: dict) -> List[Path]:
        """
        セクションごとの画像を取得（processed_images.json を優先）

        Args:
            script: 台本データ

        Returns:
            画像ファイルのパスリスト（セクション順）
        """
        # 1. 優先: processed_images.json から加工済み画像を取得
        processed_json = self.working_dir / "04_processed" / "processed_images.json"

        if processed_json.exists():
            try:
                with open(processed_json, 'r', encoding='utf-8') as f:
                    processed_data = json.load(f)

                processed_images = processed_data.get('images', [])

                if processed_images:
                    self.logger.info(f"Loading processed images from {processed_json}")

                    # セクションID順にソート
                    sections = script.get('sections', [])
                    section_ids = [s.get('section_id', 0) for s in sections]

                    # セクションID順に画像を抽出
                    images = []
                    for section_id in section_ids:
                        # 該当セクションの加工済み画像を検索
                        section_processed = [
                            img for img in processed_images
                            if img.get('section_id') == section_id
                        ]

                        if section_processed:
                            # 最初の1枚を使用（将来的に複数対応可能）
                            processed_path_str = section_processed[0].get('processed_file_path', '')
                            processed_path = self.resolve_image_path(processed_path_str)

                            if processed_path and processed_path.exists():
                                images.append(processed_path)
                                self.logger.debug(
                                    f"Section {section_id}: Using processed image: {processed_path.name}"
                                )
                            else:
                                self.logger.warning(
                                    f"Section {section_id}: Processed image not found: {processed_path_str}"
                                )
                                # 元画像へのフォールバック
                                original_path = Path(section_processed[0].get('original_file_path', ''))
                                if original_path.exists():
                                    images.append(original_path)
                                    self.logger.debug(
                                        f"Section {section_id}: Using original image as fallback: {original_path.name}"
                                    )

                    if images:
                        self.logger.info(f"✓ Loaded {len(images)} processed images")
                        # 深度マップ情報も保持（将来の2.5D実装用）
                        depth_maps = [
                            Path(img.get('depth_map_path', ''))
                            for img in processed_images
                            if img.get('depth_map_path')
                        ]
                        if depth_maps:
                            self.logger.debug(f"  Found {len(depth_maps)} depth maps (for future 2.5D implementation)")
                        return images
                    else:
                        self.logger.warning("No valid processed images found, falling back to generated images")

            except Exception as e:
                self.logger.warning(f"Failed to load processed_images.json: {e}, falling back to generated images")

        # 2. フォールバック: 従来の方式（03_images/generated から読み込む）
        self.logger.info("Using fallback: loading images from 03_images/generated")
        images_dir = self.working_dir / "03_images" / "generated"

        if not images_dir.exists():
            raise FileNotFoundError(f"Images directory not found: {images_dir}")

        # セクションID順に画像を取得
        images = []
        sections = script.get('sections', [])

        for section in sections:
            section_id = section.get('section_id', 0)

            # セクションIDに基づいて画像ファイルを検索
            section_images = sorted(
                list(images_dir.glob(f"section_{section_id:02d}_*.*"))
            )

            if not section_images:
                # フォールバック: section_XX で始まるファイルを検索
                section_images = sorted(
                    [f for f in images_dir.glob(f"section_{section_id:02d}*.*")]
                )

            if section_images:
                images.append(section_images[0])
                self.logger.debug(f"Section {section_id}: Using image: {section_images[0].name}")
            else:
                self.logger.warning(f"Section {section_id}: No image found")

        self.logger.info(f"✓ Loaded {len(images)} images from generated directory")
        return images

    def resolve_image_path(self, path_str: Optional[str]) -> Optional[Path]:
        """パスを絶対パス・相対パス・ファイル名から柔軟に解決"""
        if not path_str:
            return None

        # 1. そのままチェック
        path = Path(path_str)
        if path.exists():
            return path

        # 2. プロジェクトルートからの相対パス
        try:
            parts = Path(path_str).parts
            if 'data' in parts:
                idx = parts.index('data')
                rel = Path(*parts[idx:])
                abs_path = self.config.project_root / rel
                if abs_path.exists():
                    return abs_path
        except:
            pass

        # 3. ファイル名検索
        filename = Path(path_str).name
        search_dir = self.working_dir / "04_processed" / "processed"
        if search_dir.exists():
            found = list(search_dir.glob(f"**/{filename}"))
            if found:
                return found[0]

        return None
