"""
字幕処理

ASS字幕の生成と動画への焼き込みを担当する専門クラス
"""

import json
import platform
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any

from PIL import Image, ImageDraw, ImageFont

from ...core.models import SubtitleEntry
from ...core.config_manager import ConfigManager


class SubtitleProcessor:
    """
    字幕処理

    責任:
    - ASS字幕ファイルの生成
    - 動画への字幕焼き込み（SRT/ASS対応）
    - インパクト字幕対応
    - 字幕タイミング検証
    """

    def __init__(
        self,
        config: ConfigManager,
        logger,
        working_dir: Path,
        phase_dir: Path,
        encode_preset: str = "medium",
        split_config: Optional[Dict] = None,
        phase_config: Optional[Dict] = None
    ):
        """
        初期化

        Args:
            config: ConfigManager インスタンス
            logger: ロガー
            working_dir: 作業ディレクトリ（data/subjects/{subject}/）
            phase_dir: フェーズディレクトリ（07_composition/）
            encode_preset: エンコードプリセット
            split_config: 二分割レイアウト設定
            phase_config: Phase設定
        """
        self.config = config
        self.logger = logger
        self.working_dir = working_dir
        self.phase_dir = phase_dir
        self.encode_preset = encode_preset
        self.split_config = split_config or {}
        self.phase_config = phase_config or {}

    def create_ass_file(
        self,
        subtitles: List[SubtitleEntry],
        audio_timing: Optional[dict] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        ASS字幕ファイルを生成（完全修正版）

        重要な修正:
        1. タイミングの微調整を削除（オリジナルのタイミングを維持）
        2. 各字幕のデバッグ情報を出力
        3. セクション境界の字幕を特別に処理（ログ）

        Args:
            subtitles: 字幕エントリのリスト
            audio_timing: 音声タイミングデータ（オプション）
            output_path: 出力パス（指定しない場合は phase_dir/subtitles.ass）

        Returns:
            生成されたASS字幕ファイルのパス
        """
        if output_path is None:
            output_path = self.phase_dir / "subtitles.ass"

        if not subtitles:
            self.logger.warning("No subtitles found, creating empty ASS file")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(self._get_ass_header_fixed())
            return output_path

        # ASSヘッダー
        ass_content = self._get_ass_header_fixed()

        # セクション境界のタイミング（必要に応じて動的化可能）
        section_boundaries = []
        try:
            if audio_timing:
                boundaries = []
                sections = audio_timing.get('sections', audio_timing) if isinstance(audio_timing, dict) else audio_timing
                prev_end = 0.0
                for section in sections:
                    char_end_times = section.get('char_end_times') or section.get('character_end_times_seconds') or []
                    end = float(char_end_times[-1]) if char_end_times else float(section.get('duration', prev_end))
                    boundaries.append(end)
                    prev_end = end
                section_boundaries = boundaries[:-1]  # 最後の終端は境界として不要
        except Exception:
            pass

        self.logger.info(f"ASS字幕生成: {len(subtitles)}個のエントリ")

        # 🔍 デバッグ: subtitle_timing.jsonからspecial_typeを確認
        subtitle_timing_path = self.working_dir / "06_subtitles" / "subtitle_timing.json"
        subtitle_timing_data = {}
        if subtitle_timing_path.exists():
            try:
                with open(subtitle_timing_path, 'r', encoding='utf-8') as f:
                    subtitle_timing_data = json.load(f)
                self.logger.info(f"🔍 [DEBUG] Loaded subtitle_timing.json with {len(subtitle_timing_data.get('subtitles', []))} entries")
            except Exception as e:
                self.logger.warning(f"Failed to load subtitle_timing.json: {e}")

        # subtitle_timing.jsonのインデックスとSubtitleEntryのインデックスをマッピング
        timing_map = {}
        if subtitle_timing_data:
            for timing_sub in subtitle_timing_data.get('subtitles', []):
                idx = timing_sub.get('index')
                if idx is not None:
                    timing_map[idx] = timing_sub

        # セクションタイトルのパターン（フォールバック用）
        title_patterns = ['起：', '承転：', '結：', '序：', '破：', '急：']

        for subtitle in subtitles:
            # オリジナルのタイミングをそのまま使用
            start_time = subtitle.start_time
            end_time = subtitle.end_time

            # 🔍 デバッグ: special_typeを確認
            timing_info = timing_map.get(subtitle.index)
            special_type = timing_info.get('special_type') if timing_info else None

            # フォールバック: special_typeがNoneの場合、テキストパターンで判定
            if special_type is None:
                text = subtitle.text_line1
                if any(pattern in text for pattern in title_patterns):
                    special_type = 'section_title'
                    self.logger.info(f"🔍 [DEBUG] Detected section_title by pattern at index {subtitle.index}: {start_time:.2f}s - {end_time:.2f}s")
                    self.logger.info(f"  Text: {text}")

            if special_type == 'section_title':
                self.logger.info(f"🔍 [DEBUG] Using SectionTitle style for subtitle at index {subtitle.index}: {start_time:.2f}s - {end_time:.2f}s")
                self.logger.info(f"  Text: {subtitle.text_line1}")

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

            # 🔍 デバッグ: section_titleの場合は特別なスタイルを使用
            style_name = "SectionTitle" if special_type == 'section_title' else "Default"

            # ASSイベント行を追加
            ass_content += f"Dialogue: 0,{start_time_str},{end_time_str},{style_name},,0,0,0,,{subtitle_text}\n"

        # ファイルに保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        self.logger.info(f"✅ ASS字幕ファイル作成完了: {output_path.name}")

        # 検証
        self._verify_ass_file(output_path)

        return output_path

    def burn_subtitles(
        self,
        input_video: Path,
        subtitle_file: Path,
        output_path: Path,
        force_style: Optional[str] = None
    ) -> None:
        """
        動画に字幕を焼き込む（シンプル版）

        Args:
            input_video: 入力動画
            subtitle_file: 字幕ファイル（SRT形式）
            output_path: 出力パス
            force_style: 強制スタイル（指定しない場合はデフォルト）
        """
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
        srt_filename = subtitle_file.name
        srt_dir = subtitle_file.parent

        # force_styleの定義（Legacy02完全準拠）
        if force_style is None:
            force_style = (
                "FontName=CineCaption226,"  # Cinemaフォント
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
            subprocess.run(
                cmd,
                cwd=str(srt_dir),
                check=True,
                capture_output=True,
                text=True
            )
            self.logger.info(f"✓ Subtitle burning complete: {output_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to burn subtitles: {e}")
            self.logger.error(f"STDERR: {e.stderr}")
            raise

    def burn_subtitles_with_impact(
        self,
        input_video: Path,
        srt_path: Path,
        subtitle_timing_path: Path,
        output_path: Path
    ) -> None:
        """
        字幕を焼き込む（impact_level対応）

        ASS形式で以下のスタイルを定義:
        - Normal: 白・60px（通常）
        - ImpactNormal: 赤・70px（普通インパクト）
        - ImpactMega: 白・100px・中央（特大インパクト、Phase 2で実装予定）

        Args:
            input_video: 入力動画
            srt_path: 字幕ファイル（SRT形式）
            subtitle_timing_path: 字幕タイミングデータ
            output_path: 出力パス
        """
        is_windows = platform.system() == 'Windows'

        # パス正規化関数
        def normalize_path(p: Path) -> str:
            path_str = str(p.resolve())
            if is_windows:
                path_str = path_str.replace('\\', '/')
            return path_str

        # subtitle_timing.jsonを読み込み
        with open(subtitle_timing_path, 'r', encoding='utf-8') as f:
            timing_data = json.load(f)

        # SRTをASSに変換（impact対応）
        ass_path = self._convert_srt_to_ass_with_impact(
            srt_path=srt_path,
            timing_data=timing_data
        )

        # ASSファイルパスのエスケープ処理（Windows対応）
        ass_path_str = normalize_path(ass_path)
        # プロジェクト内のフォントディレクトリを優先的に使用
        project_root = self.config.project_root
        fonts_dir_path = project_root / "assets" / "fonts" / "cinema"
        fonts_dir_str = normalize_path(fonts_dir_path)

        # デバッグ: フォントディレクトリとフォントファイルの存在確認
        self.logger.info("=" * 60)
        self.logger.info("🔍 字幕フォント設定デバッグ情報:")
        self.logger.info(f"  フォントディレクトリ: {fonts_dir_path}")
        self.logger.info(f"  フォントディレクトリ存在: {fonts_dir_path.exists()}")

        # フォントファイルの存在確認（.ttfファイルのみ）
        cinecaption_font = fonts_dir_path / "cinecaption226.ttf"
        self.logger.info(f"  cinecaption226.ttf: {cinecaption_font}")
        self.logger.info(f"  cinecaption226.ttf存在: {cinecaption_font.exists()}")

        # ASSファイルの内容を確認（フォント名部分）
        try:
            with open(ass_path, 'r', encoding='utf-8') as f:
                ass_content = f.read()
                # フォント名を抽出
                import re
                font_matches = re.findall(r'Style:.*?,(.*?),', ass_content)
                if font_matches:
                    self.logger.info(f"  ASSファイル内のフォント名: {', '.join(set(font_matches))}")
        except Exception as e:
            self.logger.warning(f"  ASSファイル読み込みエラー: {e}")

        self.logger.info("=" * 60)

        if is_windows:
            # Windowsの場合、コロンをエスケープしてシングルクォートで囲む
            ass_path_str = ass_path_str.replace(':', '\\:')
            fonts_dir_str = fonts_dir_str.replace(':', '\\:')
            ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'"
        else:
            ass_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'"

        # 入力・出力パスの正規化
        input_normalized = normalize_path(input_video)
        output_normalized = normalize_path(output_path)

        # ffmpegで字幕を焼き込む
        cmd = [
            'ffmpeg',
            '-loglevel', 'warning',  # warningレベルでフォント関連の警告を取得
            '-i', input_normalized,
            '-vf', ass_filter,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            '-y',
            output_normalized
        ]

        self.logger.info("Running ffmpeg for subtitle burning...")
        self.logger.info(f"📺 FFmpeg ASS filter: {ass_filter}")
        self.logger.info(f"📁 FFmpeg fontsdir: {fonts_dir_str}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            # FFmpegの警告を出力（フォント問題のデバッグ用）
            if result.stderr:
                self.logger.warning("FFmpeg warnings:")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        self.logger.warning(f"  {line}")

            self.logger.info(f"✓ Subtitle burning complete: {output_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to burn subtitles: {e}")
            self.logger.error(f"STDERR: {e.stderr}")
            raise

    # ========================================
    # 補助メソッド
    # ========================================

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
        margin_v = 70  # 83→70 に変更（さらに下方向へ）

        # 🔍 デバッグ: SectionTitleスタイルを追加（センター、大きく）
        section_title_font_size = 120  # タイトル用に大きく
        section_title_margin_v = 400  # 画面中央に配置

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
Style: Default,CineCaption226,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,2,2,10,10,{margin_v},128
Style: SectionTitle,CineCaption226,{section_title_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,3,5,10,10,{section_title_margin_v},128

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

    def _convert_srt_to_ass_with_impact(
        self,
        srt_path: Path,
        timing_data: dict
    ) -> Path:
        """
        SRT字幕をASS形式に変換（impact_level対応）

        Args:
            srt_path: SRT字幕ファイル
            timing_data: subtitle_timing.jsonのデータ

        Returns:
            生成されたASS字幕ファイルのパス
        """
        # timing_dataから impact_level を取得
        impact_map = {}
        for sub in timing_data.get('subtitles', []):
            idx = sub.get('index')
            impact = sub.get('impact_level', 'normal')
            if idx is not None:
                impact_map[idx] = impact

        # SRTファイルを読み込み
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()

        # SRTをパース
        import re
        srt_blocks = srt_content.strip().split('\n\n')

        # ASSヘッダー
        ass_content = self._get_ass_header_with_impact()

        # SRTブロックをASSに変換
        for block in srt_blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue

            # インデックス
            try:
                index = int(lines[0].strip())
            except:
                continue

            # タイムスタンプ（SRT形式: 00:00:00,000 --> 00:00:02,000）
            time_match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})', lines[1])
            if not time_match:
                continue

            # SRTからASS形式に変換
            start_h, start_m, start_s, start_ms = time_match.group(1, 2, 3, 4)
            end_h, end_m, end_s, end_ms = time_match.group(5, 6, 7, 8)

            start_time_ass = f"{start_h}:{start_m}:{start_s}.{start_ms[:2]}"
            end_time_ass = f"{end_h}:{end_m}:{end_s}.{end_ms[:2]}"

            # テキスト
            text = '\n'.join(lines[2:]).replace('\n', '\\N')

            # impact_levelに応じてスタイルを選択
            impact = impact_map.get(index, 'normal')
            if impact == 'mega':
                style = 'ImpactMega'
            elif impact == 'normal' and index in impact_map:
                style = 'ImpactNormal'
            else:
                style = 'Normal'

            # Dialogueを追加
            ass_content += f"Dialogue: 0,{start_time_ass},{end_time_ass},{style},,0,0,0,,{text}\n"

        # ASSファイルを保存
        ass_path = srt_path.with_suffix('.ass')
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        self.logger.info(f"✓ Converted SRT to ASS with impact levels: {ass_path}")
        return ass_path

    def _get_ass_header_with_impact(self) -> str:
        """
        インパクト字幕用のASSヘッダー
        """
        video_width = 1920
        video_height = 1080

        return f"""[Script Info]
Title: Generated Subtitles with Impact
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0
Timer: 100.0000
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Normal,CineCaption226,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,2,2,10,10,70,128
Style: ImpactNormal,CineCaption226,70,&H0000FFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,4,3,2,10,10,70,128
Style: ImpactMega,CineCaption226,100,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,4,5,10,10,400,128

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def create_subtitle_image(
        self,
        text_line1: str,
        text_line2: Optional[str],
        text_line3: Optional[str],
        width: int,
        height: int,
        font
    ) -> Image.Image:
        """
        字幕画像を生成（最大3行）

        - 透明背景のRGBA画像
        - テキストを中央に配置
        - 影・縁取り効果

        注意: text_line1/2/3 は既に句読点が削除されている前提

        Args:
            text_line1: 1行目のテキスト
            text_line2: 2行目のテキスト（オプション）
            text_line3: 3行目のテキスト（オプション）
            width: 画像幅
            height: 画像高さ
            font: PILフォント

        Returns:
            PIL Image (RGBA)
        """
        # 句読点チェック（Phase 6で削除済みのはず）
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

    def load_japanese_font(self, size: int):
        """日本語フォントを読み込む（cinecaption226.ttf優先）"""
        # プロジェクトルートからフォントパスを取得
        project_root = self.config.project_root
        cinecaption_font = project_root / "assets" / "fonts" / "cinema" / "cinecaption226.ttf"

        # フォントパスのリスト（cinecaption226.ttfを最優先）
        font_paths = [
            # プロジェクト内のフォント（最優先）
            str(cinecaption_font),
            # Windows 明朝体
            "C:/Windows/Fonts/msmincho.ttc",
            "C:/Windows/Fonts/yumin.ttf",
            "C:/Windows/Fonts/BIZ-UDMinchoM.ttc",
            # Linux 明朝体
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf",
            # macOS 明朝体
            "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
            "/Library/Fonts/ヒラギノ明朝 ProN W3.ttc",
            # フォールバック: ゴシック体
            "C:/Windows/Fonts/msgothic.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
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
