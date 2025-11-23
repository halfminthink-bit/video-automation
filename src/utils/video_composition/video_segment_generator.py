"""
動画セグメント生成

画像から動画セグメントを生成し、最終動画を作成する専門クラス
"""

import json
import random
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Any

from ...core.config_manager import ConfigManager


class VideoSegmentGenerator:
    """
    動画セグメント生成

    責任:
    - 画像タイミングの計算（LLM、キーワードマッチング、均等分割）
    - 画像から動画セグメントの生成（ズーム効果付き）
    - セグメントの連結
    - BGM・音声の統合
    """

    def __init__(
        self,
        config: ConfigManager,
        logger,
        working_dir: Path,
        phase_dir: Path,
        phase_config: Optional[Dict] = None,
        encode_preset: str = "ultrafast"
    ):
        """
        初期化

        Args:
            config: ConfigManager インスタンス
            logger: ロガー
            working_dir: 作業ディレクトリ
            phase_dir: フェーズディレクトリ
            phase_config: Phase設定
            encode_preset: エンコードプリセット
        """
        self.config = config
        self.logger = logger
        self.working_dir = working_dir
        self.phase_dir = phase_dir
        self.phase_config = phase_config or {}
        self.encode_preset = encode_preset

        # 依存する他のプロセッサ
        from .bgm_processor import BGMProcessor
        from .ffmpeg_builder import FFmpegBuilder
        from .gradient_processor import GradientProcessor

        bgm_fade_in = 3.0
        bgm_fade_out = 3.0
        self.bgm_processor = BGMProcessor(
            config.project_root,
            logger,
            bgm_fade_in=bgm_fade_in,
            bgm_fade_out=bgm_fade_out
        )

        self.ffmpeg_builder = FFmpegBuilder(
            config.project_root,
            logger,
            encode_preset=encode_preset,
            threads=0,
            bgm_processor=self.bgm_processor
        )

        self.gradient_processor = GradientProcessor(
            logger=logger,
            working_dir=working_dir
        )

    def create_video_from_segments(
        self,
        audio_path: Path,
        script: dict,
        audio_timing: dict,
        bgm_data: Optional[dict] = None,
        output_path: Optional[Path] = None,
        ass_path: Optional[Path] = None
    ) -> Path:
        """
        画像セグメントから最終動画を生成

        Args:
            audio_path: 音声ファイルのパス
            script: 台本データ
            audio_timing: 音声タイミングデータ
            bgm_data: BGMデータ
            output_path: 出力パス（指定しない場合は phase_dir/final_video.mp4）
            ass_path: ASS字幕ファイルのパス（指定しない場合は生成されない）

        Returns:
            生成された動画のパス
        """
        if output_path is None:
            output_path = self.phase_dir / "final_video.mp4"

        # セグメントベースの動画生成
        video_path = self._create_segment_videos_then_concat(
            audio_path=audio_path,
            script=script,
            audio_timing=audio_timing,
            bgm_data=bgm_data,
            output_path=output_path,
            ass_path=ass_path
        )

        return video_path

    def calculate_image_timings(
        self,
        audio_path: Path,
        script: dict,
        audio_timing: dict,
        resolve_image_path_func
    ) -> List[dict]:
        """
        画像タイミングを計算（LLM、キーワードマッチング、均等分割の3モード対応）

        Args:
            audio_path: 音声ファイルのパス
            script: 台本データ
            audio_timing: 音声タイミングデータ
            resolve_image_path_func: 画像パス解決関数

        Returns:
            画像タイミングのリスト [{'path': Path, 'duration': float, 'depth_map_path': Optional[str]}, ...]
        """
        # 1. processed_images.jsonから画像を取得
        processed_json = self.working_dir / "04_processed" / "processed_images.json"
        all_images = []
        classified_data = None

        if processed_json.exists():
            try:
                self.logger.info(f"Loading processed images from {processed_json}")
                with open(processed_json, 'r', encoding='utf-8') as f:
                    processed_data = json.load(f)

                processed_images = processed_data.get('images', [])

                for img_data in processed_images:
                    processed_path_str = img_data.get('processed_file_path', '')
                    processed_path = resolve_image_path_func(processed_path_str)

                    if processed_path and processed_path.exists():
                        depth_map_path_str = img_data.get('depth_map_path', '')
                        depth_map_path = None
                        if depth_map_path_str:
                            depth_map_path = resolve_image_path_func(depth_map_path_str)
                            if depth_map_path and not depth_map_path.exists():
                                depth_map_path = None

                        all_images.append({
                            'file_path': str(processed_path),
                            'section_id': img_data.get('section_id'),
                            'image_id': img_data.get('image_id'),
                            'keywords': img_data.get('keywords', []),
                            'depth_map_path': str(depth_map_path) if depth_map_path else None
                        })
                        self.logger.debug(f"  Using processed image: {processed_path.name}")

                if all_images:
                    self.logger.info(f"✅ Loaded {len(all_images)} processed images")
            except Exception as e:
                self.logger.warning(f"Failed to load processed_images.json: {e}, falling back to classified.json")
                all_images = []

        # 2. フォールバック: classified.jsonから元画像を取得
        if not all_images:
            classified_path = self.working_dir / "03_images" / "classified.json"
            if not classified_path.exists():
                raise FileNotFoundError(f"Neither processed_images.json nor classified.json found")

            self.logger.info(f"Loading images from {classified_path}")
            with open(classified_path, 'r', encoding='utf-8') as f:
                classified_data = json.load(f)

            all_images = classified_data.get('images', [])
            self.logger.info(f"✅ Loaded {len(all_images)} images from classified.json")

        # 3. セクションIDと時間のマッピングを作成
        section_durations = {}
        if isinstance(audio_timing, list):
            for timing_section in audio_timing:
                section_id = timing_section.get('section_id')
                if section_id:
                    total_duration = timing_section.get('total_duration')
                    if total_duration:
                        section_durations[section_id] = total_duration
                    else:
                        narration_timing = timing_section.get('narration_timing', {})
                        end_time = narration_timing.get('end_time')
                        if end_time:
                            section_durations[section_id] = end_time
                        else:
                            char_end_times = timing_section.get('char_end_times', [])
                            if char_end_times:
                                section_durations[section_id] = char_end_times[-1]
        elif isinstance(audio_timing, dict):
            sections = audio_timing.get('sections', [audio_timing])
            for timing_section in sections:
                section_id = timing_section.get('section_id')
                if section_id:
                    total_duration = timing_section.get('total_duration')
                    if total_duration:
                        section_durations[section_id] = total_duration
                    else:
                        narration_timing = timing_section.get('narration_timing', {})
                        end_time = narration_timing.get('end_time')
                        if end_time:
                            section_durations[section_id] = end_time
                        else:
                            char_end_times = timing_section.get('char_end_times', [])
                            if char_end_times:
                                section_durations[section_id] = char_end_times[-1]

        if section_durations:
            self.logger.info(f"✅ Loaded {len(section_durations)} section durations")

        # 4. セクションごとに画像をグループ化
        section_images = {sid: [] for sid in section_durations.keys()}
        image_info_map = {}

        for img in all_images:
            file_path = Path(img.get('file_path', ''))
            if not file_path.exists():
                continue

            section_num = img.get('section_id')
            if not section_num:
                match = re.search(r'section_(\d+)', file_path.name)
                if match:
                    section_num = int(match.group(1))
                else:
                    continue

            image_info_map[str(file_path)] = {
                'section_id': section_num,
                'depth_map_path': img.get('depth_map_path')
            }

            if section_num in section_images:
                section_images[section_num].append(file_path)

        # 各セクション内でソート
        for section_num in section_images.keys():
            section_images[section_num].sort(key=lambda p: p.name)

        # 5. 画像タイミング計算（均等分割モード）
        image_timings = []
        sorted_section_ids = sorted(section_images.keys())
        actual_audio_duration = self.bgm_processor.get_audio_duration(audio_path)
        self.logger.info(f"Actual audio duration: {actual_audio_duration:.3f}s")

        # 均等分割モード（デフォルト）
        self.logger.info("📊 Using equal split image timing mode")
        for section_id in sorted_section_ids:
            images = section_images[section_id]
            if not images:
                continue

            section_duration = section_durations.get(section_id, 0)
            duration_per_image = section_duration / len(images) if images else 0

            for image_path in images:
                img_info = image_info_map.get(str(image_path), {})
                image_timings.append({
                    'path': image_path,
                    'duration': duration_per_image,
                    'section_id': img_info.get('section_id'),
                    'depth_map_path': img_info.get('depth_map_path')
                })

        self.logger.info(f"Total images to process: {len(image_timings)}")
        return image_timings

    def _create_segment_videos_then_concat(
        self,
        audio_path: Path,
        script: dict,
        audio_timing: dict,
        bgm_data: Optional[dict],
        output_path: Path,
        ass_path: Optional[Path] = None
    ) -> Path:
        """
        セグメントごとに動画を作成してから連結

        Args:
            audio_path: 音声ファイルのパス
            script: 台本データ
            audio_timing: 音声タイミングデータ
            bgm_data: BGMデータ
            output_path: 出力パス
            ass_path: ASS字幕ファイルのパス（オプション）

        Returns:
            最終動画のパス
        """
        self.logger.info("🎬 Using segment-based approach for better subtitle sync...")

        # 一時ディレクトリ作成
        temp_dir = Path(tempfile.mkdtemp(prefix="video_segments_"))
        segment_files = []
        concat_list = None

        try:
            # 画像タイミング計算（resolve_image_path は Phase07DataLoader から渡す必要がある）
            # ここでは簡易的に実装
            def resolve_image_path(path_str):
                if not path_str:
                    return None
                path = Path(path_str)
                if path.exists():
                    return path
                # プロジェクトルートからの相対パス
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
                return None

            image_timings = self.calculate_image_timings(
                audio_path=audio_path,
                script=script,
                audio_timing=audio_timing,
                resolve_image_path_func=resolve_image_path
            )

            if not image_timings:
                raise ValueError("No image timings calculated")

            # 各画像をセグメント動画に変換（グラデーションなし）
            self.logger.info(f"Creating {len(image_timings)} video segments...")
            for i, timing in enumerate(image_timings):
                img_path = timing['path']
                duration = timing['duration']
                depth_map_path = timing.get('depth_map_path')

                segment_file = temp_dir / f"segment_{i:04d}.mp4"
                self.logger.info(f"  [{i+1}/{len(image_timings)}] {img_path.name} ({duration:.2f}s)")

                # 2.5D処理 or ズーム処理でセグメント生成（グラデーションなし）
                depth_map = None
                if depth_map_path:
                    depth_map = Path(depth_map_path) if isinstance(depth_map_path, str) else depth_map_path
                    if not depth_map.exists():
                        depth_map = None
                
                if depth_map:
                    # 2.5D処理
                    from .depth_animator import DepthAnimator
                    depth_animator = DepthAnimator(logger=self.logger)
                    
                    temp_2_5d = temp_dir / f"segment_2_5d_{i:04d}.mp4"
                    self.logger.info(f"  🎬 2.5D animation: {depth_map.name}")
                    success = depth_animator.create_animation(
                        image_path=img_path,
                        depth_path=depth_map,
                        duration=duration,
                        output_path=temp_2_5d,
                        movement_type="dolly_zoom"
                    )
                    
                    if success:
                        # 2.5D動画を正規化（FFmpegで再エンコードしてコーデック統一）
                        # グラデーションは適用せず、フォーマット正規化のみ
                        normalized_2_5d = temp_dir / f"segment_2_5d_norm_{i:04d}.mp4"
                        self.logger.info(f"  🔄 Normalizing 2.5D segment format...")
                        norm_cmd = [
                            'ffmpeg', '-y',
                            '-i', str(temp_2_5d),
                            '-c:v', 'libx264', '-preset', self.encode_preset, '-crf', '18',
                            '-pix_fmt', 'yuv420p', '-r', '30',
                            str(normalized_2_5d)
                        ]
                        if self._run_ffmpeg_safe(norm_cmd, timeout=300):
                            segment_file = normalized_2_5d
                            # 一時ファイルを削除
                            if temp_2_5d.exists():
                                temp_2_5d.unlink()
                        else:
                            # 正規化失敗時は元のファイルを使用
                            self.logger.warning(f"Normalization failed, using original 2.5D file")
                            segment_file = temp_2_5d
                    else:
                        # 2.5D失敗時は通常のズーム処理にフォールバック
                        self.logger.warning(f"2.5D failed, falling back to zoom for {img_path.name}")
                        self._create_zoompan_segment(
                            img_path=img_path,
                            duration=duration,
                            output_path=segment_file,
                            seed=i
                        )
                else:
                    # 通常のズーム処理（グラデーションなし）
                    self._create_zoompan_segment(
                        img_path=img_path,
                        duration=duration,
                        output_path=segment_file,
                        seed=i
                    )

                segment_files.append(segment_file)

            # concat.txt 生成
            concat_list = temp_dir / "concat.txt"
            self._create_concat_file_with_duration(
                segment_files=segment_files,
                image_timings=image_timings,
                output_path=concat_list
            )

            # グラデーション画像を生成（最終合成時に使用）
            gradient_path = self.gradient_processor.create_gradient_image(
                width=1920,
                height=1080,
                gradient_ratio=0.35
            )
            self.logger.info(f"🎨 Gradient image ready: {gradient_path.name}")

            # ASS字幕ファイルのパス（既に生成されている場合はそれを使用、なければNone）
            if ass_path is None:
                # ASSファイルが存在するか確認
                default_ass_path = self.phase_dir / "subtitles.ass"
                if default_ass_path.exists():
                    ass_path = default_ass_path
                    self.logger.info(f"📝 Using existing ASS file: {ass_path.name}")
                else:
                    self.logger.warning("⚠️ ASS file not found, video will be created without subtitles")
                    ass_path = None

            # 動画を連結 + グラデーション（独立レイヤー） + 音声 + 字幕 + BGM
            cmd = self.ffmpeg_builder.build_ffmpeg_command_optimized(
                concat_file=concat_list,
                audio_path=audio_path,
                ass_path=ass_path,
                output_path=output_path,
                bgm_data=bgm_data,
                gradient_path=gradient_path
            )

            self.logger.info("🎬 Running final FFmpeg merge...")
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            self.logger.info(f"✅ Video created: {output_path}")
            return output_path

        finally:
            # クリーンアップ
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _create_zoompan_segment(
        self,
        img_path: Path,
        duration: float,
        output_path: Path,
        seed: int
    ):
        """
        4Kズーム処理（グラデーションなし）

        Args:
            img_path: 画像ファイルのパス
            duration: セグメントの長さ（秒）
            output_path: 出力パス
            seed: ランダムシード
        """
        random.seed(seed)
        move_type = random.choice(["zoom_in", "zoom_out", "pan_right", "pan_left"])

        fps = 30
        frames = int(duration * fps)
        zoom_speed = 0.0003

        # 4K処理用フィルタ
        scale_4k = "scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160"

        if move_type == "zoom_in":
            z_expr = f"z='min(zoom+{zoom_speed},{1.15})'"
            pos = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        elif move_type == "zoom_out":
            z_expr = f"z='if(eq(on,0),{1.15},max(zoom-{zoom_speed},1.0))'"
            pos = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        elif move_type == "pan_right":
            x_expr = f"x='(iw-iw/zoom)*(on/{frames})'"
            z_expr = "z='1.1'"
            pos = f"{x_expr}:y='ih/2-(ih/zoom/2)'"
        else:  # pan_left
            x_expr = f"x='(iw-iw/zoom)*(1-on/{frames})'"
            z_expr = "z='1.1'"
            pos = f"{x_expr}:y='ih/2-(ih/zoom/2)'"

        filter_complex = (
            # 背景: 軽量擬似ブラー (1920 -> 192 -> 1920)
            f"[0:v]scale=192:108,scale=1920:1080:flags=bicubic,eq=brightness=-0.3[bg];"
            # 前景: 4Kアップスケール -> Zoompan -> 1080pダウンコンバート
            f"[0:v]{scale_4k},zoompan={z_expr}:d={frames}:{pos}:s=3840x2160:fps={fps},scale=1920:1080[fg];"
            # 合成（グラデーションなし）
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[out]"
        )

        cmd = [
            'ffmpeg', '-y',
            '-loop', '1', '-i', str(img_path),
            '-t', f"{duration:.6f}",
            '-filter_complex', filter_complex,
            '-map', '[out]',
            '-c:v', 'libx264', '-preset', self.encode_preset, '-crf', '18',
            '-pix_fmt', 'yuv420p', '-r', '30',
            str(output_path)
        ]

        if not self._run_ffmpeg_safe(cmd, timeout=300):
            raise RuntimeError(f"Failed to create zoom segment: {img_path.name}")

    def _create_concat_file_with_duration(
        self,
        segment_files: List[Path],
        image_timings: List[dict],
        output_path: Path
    ) -> Path:
        """
        FFmpeg concat用ファイル生成（duration付き）

        Args:
            segment_files: セグメントファイルのリスト
            image_timings: 画像タイミング情報のリスト
            output_path: 出力パス

        Returns:
            生成されたconcatファイルのパス
        """
        concat_lines = []

        for i, (seg_file, timing) in enumerate(zip(segment_files, image_timings)):
            # パス正規化
            path_str = str(seg_file.resolve()).replace('\\', '/').replace("'", "'\\''")
            concat_lines.append(f"file '{path_str}'")

            # 最後以外はduration指定
            if i < len(segment_files) - 1:
                duration = timing['duration']
                concat_lines.append(f"duration {duration:.6f}")

            self.logger.debug(
                f"  Concat entry {i+1}: {seg_file.name} "
                f"(duration: {timing['duration']:.3f}s)"
            )

        # 最後のファイルを再度追加（ffmpeg concat仕様）
        if segment_files:
            last_file = segment_files[-1]
            path_str = str(last_file.resolve()).replace('\\', '/').replace("'", "'\\''")
            concat_lines.append(f"file '{path_str}'")
            self.logger.debug(f"  Added final frame: {last_file.name} (no duration)")

        # ファイルに書き込み
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(concat_lines))

        self.logger.info(f"📄 concat.txt created with {len(concat_lines)} lines")
        return output_path

    def _verify_segment_duration(self, segment_path: Path, expected_duration: float) -> bool:
        """
        セグメント動画の長さを検証

        Args:
            segment_path: セグメントファイルのパス
            expected_duration: 期待される長さ（秒）

        Returns:
            検証に成功した場合 True
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(segment_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            actual_duration = float(result.stdout.strip())

            # 許容誤差: ±0.1秒
            tolerance = 0.1
            if abs(actual_duration - expected_duration) <= tolerance:
                return True
            else:
                self.logger.warning(
                    f"Duration mismatch: {segment_path.name} "
                    f"(expected: {expected_duration:.3f}s, actual: {actual_duration:.3f}s)"
                )
                return False

        except Exception as e:
            self.logger.error(f"Failed to verify segment duration: {e}")
            return False

    def _run_ffmpeg_safe(self, cmd: List[str], timeout: int = 600) -> bool:
        """
        安全なFFmpeg実行ヘルパー（デッドロック防止・タイムアウト付き）

        Args:
            cmd: FFmpegコマンド（リスト形式）
            timeout: タイムアウト（秒）

        Returns:
            成功した場合 True
        """
        try:
            # stdin, stdout, stderr 全てを DEVNULL にしてブロッキングを防ぐ
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                timeout=timeout
            )
            return True
        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ FFmpeg timed out after {timeout}s")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ FFmpeg execution failed with code {e.returncode}")
            return False
