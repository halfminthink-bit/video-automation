"""FFmpegコマンドを構築するユーティリティ"""

import multiprocessing
import platform
from pathlib import Path
from typing import List, Optional


class FFmpegBuilder:
    """
    FFmpegコマンドの構築を担当
    
    機能:
    - 基本的なFFmpegコマンド構築
    - ASS字幕対応コマンド構築
    - デバッグ版コマンド構築
    - 最適化版コマンド構築
    """
    
    def __init__(
        self,
        project_root: Path,
        logger,
        encode_preset: str = "faster",
        threads: int = 0,
        bgm_processor=None
    ):
        """
        Args:
            project_root: プロジェクトのルートパス
            logger: ロガー
            encode_preset: エンコードプリセット
            threads: スレッド数（0の場合は自動）
            bgm_processor: BGMProcessorインスタンス
        """
        self.project_root = project_root
        self.logger = logger
        self.encode_preset = encode_preset
        self.threads = threads
        self.bgm_processor = bgm_processor
    
    def _normalize_path(self, p: Path) -> str:
        """WindowsパスをUnix形式に変換（ffmpeg互換）"""
        is_windows = platform.system() == 'Windows'
        path_str = str(p.resolve())
        if is_windows:
            path_str = path_str.replace('\\', '/')
        return path_str
    
    def _get_threads(self) -> int:
        """スレッド数を取得"""
        return self.threads if self.threads > 0 else multiprocessing.cpu_count()
    
    def build_ffmpeg_command(
        self,
        concat_file: Path,
        audio_path: Path,
        srt_path: Optional[Path],
        output_path: Path,
        bgm_data: Optional[dict]
    ) -> List[str]:
        """
        ffmpegコマンドを構築

        - 黒バー（下部216px）を追加
        - SRT字幕を焼き込み（srt_pathがNoneでない場合のみ）
        - BGMをナレーションとミックス（音量調整、フェード付き）
        
        Args:
            concat_file: concatファイルのパス
            audio_path: 音声ファイルのパス
            srt_path: 字幕ファイル（Noneの場合は字幕フィルタをスキップ）
            output_path: 出力動画パス
            bgm_data: BGMデータ
        
        Returns:
            FFmpegコマンド（リスト形式）
        """
        threads = self._get_threads()

        # 基本コマンド
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', self._normalize_path(concat_file),
            '-i', self._normalize_path(audio_path),
        ]

        # BGMファイルを入力として追加
        bgm_segments = []
        if bgm_data and bgm_data.get("segments"):
            bgm_segments = bgm_data.get("segments", [])
            for segment in bgm_segments:
                bgm_path = segment.get("file_path")
                if bgm_path and Path(bgm_path).exists():
                    cmd.extend(['-i', self._normalize_path(Path(bgm_path))])

        # ビデオフィルタを構築
        video_filters = []

        # 1. 黒バーを削除（Phase 04/07 v2で導入したグラデーション座布団が既に適用されているため不要）
        # video_filters.append("drawbox=y=ih-216:color=black@1.0:width=iw:height=216:t=fill")

        # 2. 字幕フィルタ（srt_pathがNoneでない場合のみ追加）
        # Pass 1では字幕なし、Pass 2で別途追加
        if srt_path and srt_path.exists():
            self.logger.warning("⚠️ Subtitle filter in Pass 1 is deprecated. Use Pass 2 instead.")

        # ビデオフィルタを適用
        if video_filters:
            cmd.extend(['-vf', ','.join(video_filters)])

        # オーディオフィルタ（BGMがある場合）
        if bgm_segments and self.bgm_processor:
            audio_filter = self.bgm_processor.build_audio_filter(bgm_segments)
            cmd.extend(['-filter_complex', audio_filter])
            cmd.extend(['-map', '0:v', '-map', '[audio]'])
        else:
            # BGMなし: ナレーションのみ
            cmd.extend(['-map', '0:v', '-map', '1:a'])

        # 音声の長さを取得
        if self.bgm_processor:
            audio_duration = self.bgm_processor.get_audio_duration(audio_path)
        else:
            audio_duration = 60.0  # デフォルト値
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
            self._normalize_path(output_path)
        ])

        return cmd
    
    def build_ffmpeg_command_with_ass(
        self,
        concat_file: Path,
        audio_path: Path,
        ass_path: Path,
        output_path: Path,
        bgm_data: Optional[dict]
    ) -> List[str]:
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
        threads = self._get_threads()

        # 基本コマンド
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', self._normalize_path(concat_file),
            '-i', self._normalize_path(audio_path),
        ]

        # BGMファイルを入力として追加
        bgm_segments = []
        if bgm_data and bgm_data.get("segments"):
            bgm_segments = bgm_data.get("segments", [])
            for segment in bgm_segments:
                bgm_path = segment.get("file_path")
                if bgm_path and Path(bgm_path).exists():
                    cmd.extend(['-i', self._normalize_path(Path(bgm_path))])

        # ビデオフィルタを構築
        video_filters = []

        # 1. 画像をリサイズ・パディング（1920x1080）
        video_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease")
        video_filters.append("pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black")

        # 2. 黒バーを削除（Phase 04/07 v2で導入したグラデーション座布団が既に適用されているため不要）
        # video_filters.append("drawbox=y=864:color=black:width=1920:height=216:t=fill")

        # 3. ASS字幕を焼き込み
        # Windowsパスのエスケープ処理
        ass_path_str = self._normalize_path(ass_path)
        # バックスラッシュとコロンをエスケープ（ffmpegのass filter用）
        ass_path_escaped = ass_path_str.replace('\\', '\\\\\\\\').replace(':', '\\\\:')
        video_filters.append(f"ass={ass_path_escaped}")

        # ビデオフィルタを適用
        cmd.extend(['-vf', ','.join(video_filters)])

        # オーディオフィルタ（BGMがある場合）
        if bgm_segments and self.bgm_processor:
            audio_filter = self.bgm_processor.build_audio_filter(bgm_segments)
            cmd.extend(['-filter_complex', audio_filter])
            cmd.extend(['-map', '0:v', '-map', '[audio]'])
        else:
            # BGMなし: ナレーションのみ
            cmd.extend(['-map', '0:v', '-map', '1:a'])

        # 音声の長さを取得
        if self.bgm_processor:
            audio_duration = self.bgm_processor.get_audio_duration(audio_path)
        else:
            audio_duration = 60.0  # デフォルト値
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
            self._normalize_path(output_path)
        ])

        return cmd
    
    def build_ffmpeg_command_with_ass_debug(
        self,
        concat_file: Path,
        audio_path: Path,
        ass_path: Path,
        output_path: Path,
        bgm_data: Optional[dict]
    ) -> List[str]:
        """
        FFmpegコマンドを構築（ASS字幕デバッグ版）

        追加:
        - loglevel=info（字幕処理の詳細ログ）
        - assフィルタのfontsdir指定（Windowsでのフォント探索補助）
        """
        threads = self._get_threads()
        is_windows = platform.system() == 'Windows'

        # 基本コマンド（loglevel追加）
        cmd = [
            'ffmpeg',
            '-y',
            '-loglevel', 'info',
            '-f', 'concat',
            '-safe', '0',
            '-i', self._normalize_path(concat_file),
            '-i', self._normalize_path(audio_path),
        ]

        # BGMファイルを入力として追加
        bgm_segments = []
        if bgm_data and bgm_data.get("segments"):
            bgm_segments = bgm_data.get("segments", [])
            for segment in bgm_segments:
                bgm_path = segment.get("file_path")
                if bgm_path and Path(bgm_path).exists():
                    cmd.extend(['-i', self._normalize_path(Path(bgm_path))])

        # ビデオフィルタの構築
        video_filters = []

        # 1. スケーリングとパディング
        video_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")

        # 2. 黒バーを削除（Phase 04/07 v2で導入したグラデーション座布団が既に適用されているため不要）
        # video_filters.append("drawbox=y=ih-216:color=black@1.0:width=iw:height=216:t=fill")

        # 3. ASS字幕を適用（fontsdir指定）
        if ass_path and ass_path.exists():
            ass_path_str = str(ass_path.resolve()).replace('\\', '/')
            # プロジェクト内のフォントディレクトリを優先的に使用
            fonts_dir_path = self.project_root / "assets" / "fonts" / "cinema"
            fonts_dir_str = str(fonts_dir_path.resolve()).replace('\\', '/')
            
            if is_windows:
                # コロンをエスケープ（C: → C\:）
                ass_path_str = ass_path_str.replace(':', '\\:')
                fonts_dir_str = fonts_dir_str.replace(':', '\\:')
                ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'"
            else:
                ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'"
            video_filters.append(ass_filter)
            self.logger.debug(f"ASS filter: {ass_filter}")

        if video_filters:
            filter_chain = ','.join(video_filters)
            cmd.extend(['-vf', filter_chain])
            self.logger.debug(f"Video filter chain: {filter_chain}")

        # オーディオフィルタ（BGMがある場合）
        if bgm_segments and self.bgm_processor:
            audio_filter = self.bgm_processor.build_audio_filter(bgm_segments)
            cmd.extend(['-filter_complex', audio_filter])
            cmd.extend(['-map', '0:v', '-map', '[audio]'])
        else:
            cmd.extend(['-map', '0:v', '-map', '1:a'])

        # 音声の長さを取得
        if self.bgm_processor:
            audio_duration = self.bgm_processor.get_audio_duration(audio_path)
        else:
            audio_duration = 60.0  # デフォルト値

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
            self._normalize_path(output_path)
        ])

        return cmd
    
    def build_ffmpeg_command_optimized(
        self,
        concat_file: Path,
        audio_path: Path,
        ass_path: Path,
        output_path: Path,
        bgm_data: Optional[dict],
        gradient_path: Optional[Path] = None
    ) -> List[str]:
        """
        最適化されたFFmpegコマンド（グラデーション対応）

        変更点:
        1. setpts=PTS-STARTPTSフィルタを追加（タイミング同期改善）
        2. -shortest を削除（音声の長さに正確に合わせる）
        3. フォントディレクトリを明示的に指定
        4. グラデーションを最終合成時に適用（一番上のレイヤー）
        """
        threads = self._get_threads()
        is_windows = platform.system() == 'Windows'

        # 基本コマンド（concat demuxer使用）
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', self._normalize_path(concat_file),
        ]

        # グラデーション入力（concatの次）
        gradient_input_idx = 1
        if gradient_path and gradient_path.exists():
            cmd.extend(['-loop', '1', '-i', self._normalize_path(gradient_path)])
            self.logger.info(f"🎨 Adding gradient overlay: {gradient_path.name}")

        # 音声入力
        audio_input_idx = gradient_input_idx + (1 if (gradient_path and gradient_path.exists()) else 0)
        cmd.extend(['-i', self._normalize_path(audio_path)])

        # BGM入力
        bgm_segments = []
        bgm_input_start = audio_input_idx + 1
        if bgm_data and bgm_data.get("segments"):
            bgm_segments = bgm_data.get("segments", [])
            for segment in bgm_segments:
                bgm_path = segment.get("file_path")
                if bgm_path and Path(bgm_path).exists():
                    cmd.extend(['-i', self._normalize_path(Path(bgm_path))])

        # ビデオフィルタ構築（filter_complex使用）
        video_filter_parts = []

        # 1. concat動画の処理
        video_filter_parts.append("[0:v]setpts=PTS-STARTPTS[v_concat]")

        # 2. グラデーションオーバーレイ（一番上のレイヤー）
        if gradient_path and gradient_path.exists():
            video_filter_parts.append(f"[v_concat][{gradient_input_idx}:v]overlay=0:0:format=auto[v_grad]")
            current_video = "[v_grad]"
        else:
            current_video = "[v_concat]"

        # 3. スケーリング
        video_filter_parts.append(f"{current_video}scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[v_scaled]")
        current_video = "[v_scaled]"

        # 4. ASS字幕
        if ass_path and ass_path.exists():
            ass_path_str = str(ass_path.resolve())
            # プロジェクト内のフォントディレクトリを優先的に使用
            fonts_dir_path = self.project_root / "assets" / "fonts" / "cinema"
            fonts_dir_resolved = fonts_dir_path.resolve()
            fonts_dir_str = str(fonts_dir_resolved).replace('\\', '/')
            
            # デバッグ: フォントディレクトリ情報
            self.logger.info(f"[Font Debug] フォントディレクトリ: {fonts_dir_resolved}")
            self.logger.info(f"[Font Debug] フォントディレクトリ存在確認: {fonts_dir_resolved.exists()}")
            
            # デバッグ: cinecaption226.ttf の存在確認（.ttfファイルのみ）
            cinecaption_font = fonts_dir_resolved / "cinecaption226.ttf"
            self.logger.info(f"[Font Debug] cinecaption226.ttf パス: {cinecaption_font}")
            self.logger.info(f"[Font Debug] cinecaption226.ttf 存在確認: {cinecaption_font.exists()}")
            
            # デバッグ: フォントディレクトリ内の全フォントファイル一覧
            if fonts_dir_resolved.exists():
                font_files = list(fonts_dir_resolved.glob("*.ttf")) + list(fonts_dir_resolved.glob("*.TTF"))
                self.logger.debug(f"[Font Debug] フォントディレクトリ内のフォントファイル: {[f.name for f in font_files]}")
            
            if is_windows:
                ass_path_str = ass_path_str.replace('\\', '/')
                ass_path_str = ass_path_str.replace(':', '\\:')
                # コロンをエスケープ（C: → C\:）
                fonts_dir_str = fonts_dir_str.replace(':', '\\:')
                ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'"
            else:
                ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'"

            # デバッグ: ASSフィルタの内容
            self.logger.info(f"[Font Debug] ASS filter: {ass_filter}")
            self.logger.info(f"[Font Debug] fontsdir パラメータ: {fonts_dir_str}")

            video_filter_parts.append(f"{current_video}{ass_filter}[v_final]")
        else:
            video_filter_parts.append(f"{current_video}copy[v_final]")

        # フィルタチェーン適用（filter_complex）
        video_filter = ";".join(video_filter_parts)
        cmd.extend(['-filter_complex', video_filter])

        # オーディオ処理
        if bgm_segments and self.bgm_processor:
            # 既存のfilter_complexに追加
            narration_input = audio_input_idx
            audio_filter = self.bgm_processor.build_audio_filter(
                bgm_segments,
                narration_input=narration_input,
                bgm_input_start=bgm_input_start
            )
            # ビデオフィルタとオーディオフィルタを結合
            combined_filter = video_filter + ";" + audio_filter
            # filter_complexの値を置き換え（cmd[-1]がfilter_complexの値）
            cmd[-1] = combined_filter
            cmd.extend(['-map', '[v_final]', '-map', '[audio]'])
        else:
            cmd.extend(['-map', '[v_final]', '-map', f'{audio_input_idx}:a'])

        # 音声の長さを取得して正確に設定
        if self.bgm_processor:
            audio_duration = self.bgm_processor.get_audio_duration(audio_path)
        else:
            audio_duration = 60.0  # デフォルト値

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
            self._normalize_path(output_path)
        ])

        return cmd


