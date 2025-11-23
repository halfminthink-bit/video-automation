"""
背景動画合成

背景動画、画像、BGMを統合して最終動画を生成する専門クラス
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Optional

from ...core.config_manager import ConfigManager


class BackgroundVideoComposer:
    """
    背景動画合成

    責任:
    - 背景動画 + 画像のオーバーレイ
    - BGMとのタイミング調整
    - 効果音の追加
    """

    def __init__(
        self,
        config: ConfigManager,
        logger,
        working_dir: Path,
        phase_dir: Path,
        encode_preset: str = "medium",
        phase_config: Optional[Dict] = None
    ):
        """
        初期化

        Args:
            config: ConfigManager インスタンス
            logger: ロガー
            working_dir: 作業ディレクトリ
            phase_dir: フェーズディレクトリ
            encode_preset: エンコードプリセット
            phase_config: Phase設定
        """
        self.config = config
        self.logger = logger
        self.working_dir = working_dir
        self.phase_dir = phase_dir
        self.encode_preset = encode_preset
        self.phase_config = phase_config or {}

        # 依存する他のプロセッサ
        from .background_processor import BackgroundVideoProcessor
        from .bgm_processor import BGMProcessor

        self.bg_processor = BackgroundVideoProcessor(
            config.project_root,
            logger
        )

        bgm_fade_in = 3.0
        bgm_fade_out = 3.0
        self.bgm_processor = BGMProcessor(
            config.project_root,
            logger,
            bgm_fade_in=bgm_fade_in,
            bgm_fade_out=bgm_fade_out
        )

    def compose_with_background(
        self,
        audio_path: Path,
        images: List[Path],
        background_videos: List[dict],
        bgm_data: Optional[dict],
        title_segments: Optional[List[dict]] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        背景動画 + 画像 + BGM を合成

        Args:
            audio_path: 音声ファイルのパス
            images: 画像のリスト
            background_videos: 背景動画セグメント情報のリスト
            bgm_data: BGMデータ
            title_segments: セクションタイトル区間のリスト
            output_path: 出力パス（指定しない場合は phase_dir/video_with_bg.mp4）

        Returns:
            生成された動画のパス
        """
        if output_path is None:
            output_path = self.phase_dir / "video_with_bg.mp4"

        self._create_video_with_background(
            audio_path=audio_path,
            images=images,
            background_videos=background_videos,
            bgm_data=bgm_data,
            title_segments=title_segments,
            output_path=output_path
        )

        return output_path

    def align_videos_with_bgm(
        self,
        bg_selection: dict,
        bgm_data: dict
    ) -> dict:
        """
        背景動画のタイミングをBGMのタイミングに合わせる

        Args:
            bg_selection: 背景動画の選択結果
            bgm_data: BGMデータ（segmentsを含む）

        Returns:
            タイミング調整後の背景動画選択結果
        """
        bgm_segments = bgm_data.get('segments', [])
        bg_segments = bg_selection.get('segments', [])

        # BGMセグメントのタイミングを使って背景動画のタイミングを調整
        aligned_segments = []

        # BGMセグメントごとに背景動画をマッピング
        for bgm_seg in bgm_segments:
            bgm_type = bgm_seg.get('bgm_type', '')
            bgm_start = bgm_seg.get('start_time', 0)
            bgm_duration = bgm_seg.get('duration', 0)

            # 対応する背景動画セグメントを探す
            matching_bg_seg = None
            for bg_seg in bg_segments:
                if bg_seg.get('track_id', '') == bgm_type:
                    matching_bg_seg = bg_seg
                    break

            if matching_bg_seg:
                # BGMのタイミングに合わせて背景動画のタイミングを調整
                aligned_seg = {
                    'track_id': bgm_type,
                    'video_path': matching_bg_seg.get('video_path', ''),
                    'start_time': bgm_start,  # BGMのstart_timeを使用
                    'duration': bgm_duration  # BGMのdurationを使用
                }
                aligned_segments.append(aligned_seg)

                self.logger.info(
                    f"Aligned background video: {bgm_type} "
                    f"[{bgm_start:.1f}s - {bgm_start + bgm_duration:.1f}s] "
                    f"(was: [{matching_bg_seg.get('start_time', 0):.1f}s - "
                    f"{matching_bg_seg.get('start_time', 0) + matching_bg_seg.get('duration', 0):.1f}s])"
                )
            else:
                self.logger.warning(
                    f"No matching background video found for BGM type: {bgm_type}"
                )

        return {
            'segments': aligned_segments,
            'total_duration': bg_selection.get('total_duration', 0)
        }

    def _create_video_with_background(
        self,
        audio_path: Path,
        images: List[Path],
        background_videos: List[dict],
        bgm_data: Optional[dict],
        title_segments: Optional[List[dict]] = None,
        output_path: Path = None
    ) -> None:
        """
        背景動画 + 画像75%縮小 + 黒バー + セクションタイトル演出

        新しい処理フロー:
        1. 背景動画を事前処理（リサイズ・ループ・トリミング）
        2. 処理済み動画をconcatで繋ぐ（シンプル）
        3. 画像をconcatで繋ぐ
        4. オーバーレイ
        5. 黒バー追加
        6. BGM追加

        Args:
            audio_path: 音声ファイルのパス
            images: 画像のリスト
            background_videos: 背景動画セグメント情報のリスト
            bgm_data: BGMデータ
            title_segments: セクションタイトル区間のリスト
            output_path: 出力パス
        """
        # 音声の長さを取得
        audio_duration = self.bgm_processor.get_audio_duration(audio_path)
        self.logger.info(f"Audio duration: {audio_duration:.2f} seconds")

        # 1. 背景動画をconcatファイルとして準備
        self.logger.info(f"Creating background video concat file for {len(background_videos)} segments...")
        bg_concat_file = self._create_background_concat_file(background_videos)
        self.logger.info(f"✓ Background video concat file created")

        # 2. 画像concatファイル作成
        image_concat_file = self._create_image_concat_file(images, audio_duration)
        self.logger.info(f"Image concat file created: {image_concat_file}")

        # 3. ffmpegコマンド（シンプル版）
        cmd = [
            'ffmpeg',
            # 背景動画（concat形式）
            '-f', 'concat',
            '-safe', '0',
            '-i', str(bg_concat_file),  # [0] 背景
            # 画像（concat形式）
            '-f', 'concat',
            '-safe', '0',
            '-i', str(image_concat_file),  # [1] 画像
            # 音声
            '-i', str(audio_path),  # [2] 音声
        ]

        # BGMファイルを追加
        bgm_input_start_index = 3
        if bgm_data:
            seen_files = set()
            for segment in bgm_data.get('segments', []):
                file_path = segment.get('file_path')
                if file_path and file_path not in seen_files:
                    bgm_file_path = Path(file_path)
                    if not bgm_file_path.is_absolute():
                        bgm_file_path = self.config.project_root / bgm_file_path

                    cmd.extend(['-i', str(bgm_file_path)])
                    seen_files.add(file_path)

            self.logger.info(f"Added {len(seen_files)} BGM files")

        # 効果音ファイルを追加
        sfx_inputs = []
        if title_segments is None:
            title_segments = []

        section_title_config = self.phase_config.get('section_title', {})
        sfx_config = section_title_config.get('sound_effect', {})

        if sfx_config.get('enabled', True) and title_segments:
            sfx_path = self.config.project_root / sfx_config.get('file', 'assets/sfx/impact_title.mp3')

            if sfx_path.exists():
                original_volume = sfx_config.get('volume', 0.5)
                debug_volume = 1.0  # デバッグ用に音量を上げる

                for seg in title_segments:
                    sfx_inputs.append({
                        'file': sfx_path,
                        'start_time': seg['start'],
                        'volume': debug_volume,
                        'fade_in': sfx_config.get('fade_in', 0.05),
                        'fade_out': sfx_config.get('fade_out', 0.1)
                    })

                # 効果音ファイルを入力として追加（重複なし）
                seen_sfx_files = set()
                for sfx in sfx_inputs:
                    if str(sfx['file']) not in seen_sfx_files:
                        cmd.extend(['-i', str(sfx['file'])])
                        seen_sfx_files.add(str(sfx['file']))

                self.logger.info(f"🔊 Added {len(sfx_inputs)} sound effects")
            else:
                self.logger.warning(f"Sound effect file not found: {sfx_path}")

        # BGMフィルターを作成
        bgm_filter = ""
        bgm_map = []
        bgm_volume_multiplier = section_title_config.get('bgm_volume_multiplier', 0.7)

        if bgm_data:
            bgm_filter, bgm_map = self._create_bgm_filter_for_background(
                bgm_data=bgm_data,
                audio_path=audio_path,
                num_bg_videos=0,  # 背景動画は事前処理済み
                sfx_inputs=sfx_inputs,
                title_segments=title_segments,
                bgm_volume_multiplier=bgm_volume_multiplier
            )

        # 4. シンプルなフィルター + 黒オーバーレイ
        filter_complex = (
            # 背景: そのまま使用（事前処理済み）
            '[0:v]copy[bg];'
            # 画像: 75%縮小（1440x810）
            '[1:v]scale=1440:810[img];'
            # オーバーレイ（固定位置: 240, 27）
            '[bg][img]overlay=240:27[composed];'
            # 黒バー追加（下部216px）
            '[composed]pad=1920:1080:0:0:black[padded];'
        )

        # 黒オーバーレイを追加（セクションタイトル区間のみ）
        overlay_config = section_title_config.get('overlay', {})
        overlay_enabled = section_title_config.get('enabled', True)

        # デバッグ情報
        self.logger.info("=" * 60)
        self.logger.info("🔍 Section Title Overlay Debug Info:")
        self.logger.info(f"  overlay_enabled: {overlay_enabled}")
        self.logger.info(f"  title_segments count: {len(title_segments) if title_segments else 0}")

        if title_segments:
            self.logger.info(f"  Title segments details:")
            for i, seg in enumerate(title_segments):
                self.logger.info(f"    [{i+1}] {seg['start']:.2f}s - {seg['end']:.2f}s: '{seg.get('text', 'N/A')}'")
        else:
            self.logger.warning("  ⚠️ No title segments found! Overlay will not be applied.")
        self.logger.info("=" * 60)

        # BGMフィルターを追加
        if bgm_filter:
            filter_complex += bgm_filter
        else:
            # BGMがない場合は音声のみ
            filter_complex += '[2:a]anull[audio_out];'

        # フィルターコンプレックスとマッピング
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[padded]',
            '-map', '[audio_out]' if bgm_filter else '[2:a]',
        ])

        # 出力設定
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.encode_preset,
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            '-y',
            str(output_path)
        ])

        # 実行
        self.logger.info("Running ffmpeg for background video composition...")
        self.logger.debug(f"Command: {' '.join(cmd)}")

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            self.logger.info(f"✓ Background video composition complete: {output_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to compose background video: {e}")
            self.logger.error(f"STDERR: {e.stderr}")
            raise

    def _create_background_concat_file(
        self,
        background_videos: List[dict]
    ) -> Path:
        """
        背景動画のconcatファイルを作成（BGMと同じ方式）

        Args:
            background_videos: 背景動画セグメント情報のリスト

        Returns:
            concatファイルのパス
        """
        return self.bg_processor.create_concat_file(
            background_videos,
            self.phase_dir
        )

    def _create_bgm_filter_for_background(
        self,
        bgm_data: dict,
        audio_path: Path,
        num_bg_videos: int = 0,
        sfx_inputs: List[dict] = None,
        title_segments: List[dict] = None,
        bgm_volume_multiplier: float = 1.0
    ) -> tuple:
        """
        BGMフィルターを作成（タイムラインに基づいた切り替え対応）

        Args:
            bgm_data: {"segments": [...]} 形式
            audio_path: 音声ファイルのパス
            num_bg_videos: 背景動画の数（BGMファイルの入力インデックス計算用）
            sfx_inputs: 効果音の入力情報リスト
            title_segments: セクションタイトル区間のリスト
            bgm_volume_multiplier: タイトル区間でのBGM音量倍率（デフォルト: 1.0）

        Returns:
            (bgm_filter, bgm_map) タプル
        """
        return self.bgm_processor.create_bgm_filter_for_background(
            bgm_data,
            audio_path,
            num_bg_videos,
            sfx_inputs,
            title_segments,
            bgm_volume_multiplier
        )

    def _create_image_concat_file(
        self,
        images: List[Path],
        audio_duration: float
    ) -> Path:
        """
        画像のconcatファイルを作成

        Args:
            images: 画像ファイルのリスト
            audio_duration: 音声の長さ（秒）

        Returns:
            concatファイルのパス
        """
        concat_file = self.phase_dir / "images_concat.txt"

        # 各画像の表示時間を計算（均等分割）
        duration_per_image = audio_duration / len(images) if images else 0

        with open(concat_file, 'w', encoding='utf-8') as f:
            for img_path in images:
                # Windows対応: バックスラッシュをスラッシュに変換
                img_path_str = str(img_path.resolve()).replace('\\', '/')
                f.write(f"file '{img_path_str}'\n")
                f.write(f"duration {duration_per_image:.6f}\n")

            # 最後の画像（durationなし）
            if images:
                last_img = str(images[-1].resolve()).replace('\\', '/')
                f.write(f"file '{last_img}'\n")

        self.logger.debug(f"Created image concat file: {concat_file}")
        return concat_file
