"""
Phase 6: 字幕生成（Subtitle Generation）

台本と音声解析データから字幕を生成し、SRT形式で出力する。
"""

import json
import sys
from pathlib import Path
from typing import List, Optional, Any, Dict
import logging

# プロジェクトルートをパスに追加
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.core.phase_base import PhaseBase
from src.core.models import (
    SubtitleGeneration,
    SubtitleEntry,
    VideoScript,
    ScriptSection,
    AudioGeneration,
    AudioSegment
)
from src.core.config_manager import ConfigManager
from src.core.exceptions import (
    PhaseExecutionError,
    PhaseValidationError,
    PhaseInputMissingError
)
from src.generators.subtitle_generator import create_subtitle_generator


class Phase06Subtitles(PhaseBase):
    """Phase 6: 字幕生成"""
    
    def get_phase_number(self) -> int:
        return 6
    
    def get_phase_name(self) -> str:
        return "Subtitle Generation"
    
    def check_inputs_exist(self) -> bool:
        """Phase 1（台本）とPhase 2（音声タイミング）の出力を確認"""
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        audio_timing_path = self.config.get_phase_dir(self.subject, 2) / "audio_timing.json"

        if not script_path.exists():
            self.logger.error(f"Script not found: {script_path}")
            return False

        # audio_timing.json が存在する場合は優先的に使用
        if audio_timing_path.exists():
            self.logger.info(f"Found audio timing data: {audio_timing_path}")
            return True

        # フォールバック：audio_analysis.json と metadata.json
        audio_analysis_path = self.config.get_phase_dir(self.subject, 2) / "audio_analysis.json"
        if not audio_analysis_path.exists():
            self.logger.error(
                f"Neither audio_timing.json nor audio_analysis.json found. "
                "Please run Phase 2 with with_timestamps enabled."
            )
            return False

        self.logger.warning(
            "Using fallback mode without timing data. "
            "For better subtitle sync, enable with_timestamps in Phase 2."
        )
        return True
    
    def check_outputs_exist(self) -> bool:
        """字幕ファイルが存在するかチェック"""
        srt_path = self.phase_dir / "subtitles.srt"
        json_path = self.phase_dir / "subtitle_timing.json"
        
        exists = srt_path.exists() and json_path.exists()
        
        if exists:
            self.logger.info(f"Subtitles already exist: {srt_path}")
        
        return exists
    
    def get_output_paths(self) -> List[Path]:
        """出力ファイルのパスリスト"""
        return [
            self.phase_dir / "subtitles.srt",
            self.phase_dir / "subtitle_timing.json",
            self.phase_dir / "metadata.json"
        ]
    
    def execute_phase(self) -> SubtitleGeneration:
        """
        字幕生成の実行（audio_timing.json からタイミング情報を使用）

        Returns:
            SubtitleGeneration: 生成された字幕

        Raises:
            PhaseExecutionError: 実行エラー
        """
        self.logger.info(f"Generating subtitles for: {self.subject}")

        try:
            # 1. 台本を読み込み
            script = self._load_script()
            self.logger.info(
                f"Loaded script: {len(script.sections)} sections, "
                f"estimated {script.total_estimated_duration:.0f}s"
            )

            # 2. audio_timing.json を読み込み（存在する場合）
            audio_timing_path = self.config.get_phase_dir(self.subject, 2) / "audio_timing.json"

            if audio_timing_path.exists():
                # タイムスタンプ付き音声データを使用
                self.logger.info("Using audio timing data with character-level timings")

                # audio_timing.jsonを読み込み
                with open(audio_timing_path, 'r', encoding='utf-8') as f:
                    audio_timing_data = json.load(f)

                # 字幕生成器を作成
                generator = create_subtitle_generator(
                    config=self.phase_config,
                    logger=self.logger
                )

                # 新しいメソッドを使用：文字レベルタイミングから字幕を生成
                subtitles = generator.generate_subtitles_from_char_timings(
                    audio_timing_data=audio_timing_data
                )
                
                # 3行字幕を修正（鍵かっこの場合のみ）
                subtitles = self._fix_three_line_quotations(subtitles)
                self.logger.info("Fixed 3-line quotations")
            else:
                # フォールバック：Whisperまたは文字数比率を使用
                self.logger.warning("Audio timing data not found, using fallback method")
                audio_segments = self._load_audio_segments()
                self.logger.info(f"Loaded audio segments: {len(audio_segments)}")

                # 字幕生成器を作成
                generator = create_subtitle_generator(
                    config=self.phase_config,
                    logger=self.logger
                )

                # 音声ファイルのパスを取得（Whisper使用のため）
                audio_path = self.config.get_phase_dir(self.subject, 2) / "narration_full.mp3"

                # 字幕を生成
                self.logger.info("Generating subtitles...")
                subtitles = generator.generate_subtitles(
                    script=script,
                    audio_segments=audio_segments,
                    config=self.phase_config,
                    audio_path=audio_path if audio_path.exists() else None
                )

            # 3. 句点での表示延長を適用（句読点削除の前に実行）
            self.logger.info("Adjusting subtitle timing for sentence endings...")
            subtitles = self._adjust_subtitle_timing_with_sentence_end(subtitles)

            # 3.5. 全字幕の一律延長は不要（句点延長で制御するため無効化）
            # self.logger.info("Extending subtitle display times (0.2s margin before next)...")
            # subtitles = self._extend_subtitle_display(subtitles)

            # 4. 句読点を削除（分割ロジックの後に実行）
            self.logger.info("Removing punctuation from subtitles...")
            subtitles = self._remove_punctuation_from_subtitles(subtitles)

            # 5. SRTファイルを保存
            srt_path = self._save_srt_file(subtitles)

            # 7. タイミングJSONを保存
            timing_path = self._save_timing_json(subtitles)

            # 8. 結果をモデルに変換
            subtitle_gen = SubtitleGeneration(
                subject=self.subject,
                subtitles=subtitles,
                srt_path=str(srt_path),
            )

            # 9. メタデータを保存
            self._save_generation_metadata(subtitle_gen)

            self.logger.info(
                f"Subtitle generation complete: "
                f"{len(subtitles)} entries, "
                f"SRT: {srt_path}"
            )

            return subtitle_gen

        except Exception as e:
            self.logger.error(f"Subtitle generation failed: {e}", exc_info=True)
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Subtitle generation failed: {e}"
            ) from e
    
    def validate_output(self, output: SubtitleGeneration) -> bool:
        """
        生成された字幕をバリデーション
        
        Args:
            output: SubtitleGeneration モデル
            
        Returns:
            バリデーション成功なら True
            
        Raises:
            PhaseValidationError: バリデーション失敗時
        """
        self.logger.info("Validating subtitle output...")
        
        # SRTファイルが存在するか
        srt_path = Path(output.srt_path)
        if not srt_path.exists():
            raise PhaseValidationError(
                self.get_phase_number(),
                f"SRT file not found: {output.srt_path}"
            )
        
        # 字幕エントリ数チェック
        if len(output.subtitles) == 0:
            raise PhaseValidationError(
                self.get_phase_number(),
                "No subtitles generated"
            )
        
        # 各字幕エントリのバリデーション
        for i, subtitle in enumerate(output.subtitles):
            if subtitle.start_time < 0:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Subtitle {i} has negative start_time: {subtitle.start_time}"
                )
            
            if subtitle.end_time <= subtitle.start_time:
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Subtitle {i} has invalid time range: "
                    f"{subtitle.start_time} - {subtitle.end_time}"
                )
            
            if not subtitle.text_line1.strip():
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Subtitle {i} has empty text_line1"
                )
        
        self.logger.info("Subtitle validation passed ✓")
        return True
    
    # ========================================
    # 内部メソッド
    # ========================================
    
    def _load_script(self) -> VideoScript:
        """
        Phase 1の台本を読み込み
        
        Returns:
            VideoScript モデル
            
        Raises:
            PhaseInputMissingError: 台本ファイルが見つからない場合
        """
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        
        if not script_path.exists():
            raise PhaseInputMissingError(
                self.get_phase_number(),
                [str(script_path)]
            )
        
        self.logger.debug(f"Loading script from: {script_path}")
        
        with open(script_path, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
        
        # Pydanticモデルに変換
        script = VideoScript(**script_data)
        
        return script
    
    def _load_audio_segments(self) -> List[AudioSegment]:
        """
        Phase 2の音声セグメント情報を読み込み
        
        Returns:
            AudioSegmentのリスト
            
        Note:
            metadata.jsonからsegments情報を取得。
            存在しない場合は、audio_analysis.jsonから基本情報を取得し、
            推定タイミングを計算する。
        """
        metadata_path = self.config.get_phase_dir(self.subject, 2) / "metadata.json"
        audio_analysis_path = self.config.get_phase_dir(self.subject, 2) / "audio_analysis.json"
        
        # metadata.jsonからsegmentsを取得を試みる
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            segments_data = metadata.get("segments", [])
            if segments_data:
                self.logger.info(f"Loaded {len(segments_data)} segments from metadata")
                return [AudioSegment(**seg) for seg in segments_data]
        
        # metadata.jsonにsegmentsがない場合、audio_analysis.jsonから推定
        self.logger.warning(
            "Segments not found in metadata.json. "
            "Estimating timing from audio_analysis.json"
        )
        
        if not audio_analysis_path.exists():
            raise PhaseInputMissingError(
                self.get_phase_number(),
                [str(audio_analysis_path)]
            )
        
        with open(audio_analysis_path, 'r', encoding='utf-8') as f:
            audio_analysis = json.load(f)
        
        # 台本から各セクションの推定時間を使用
        script = self._load_script()
        segments = []
        current_time = 0.0
        
        for section in script.sections:
            # 推定時間を使用（実際の音声時間がわからないため）
            duration = section.estimated_duration
            
            segment = AudioSegment(
                section_id=section.section_id,
                audio_path="",  # 不明
                duration=duration,
                start_time=current_time
            )
            segments.append(segment)
            current_time += duration
        
        self.logger.info(f"Estimated {len(segments)} segments from script")
        return segments
    
    def _save_srt_file(self, subtitles: List[SubtitleEntry]) -> Path:
        """
        SRTファイルを保存

        Args:
            subtitles: 字幕エントリのリスト

        Returns:
            保存されたSRTファイルのPath
        """
        srt_path = self.phase_dir / "subtitles.srt"

        with open(srt_path, 'w', encoding='utf-8') as f:
            for subtitle in subtitles:
                # インデックス
                f.write(f"{subtitle.index}\n")

                # タイムコード（HH:MM:SS,mmm形式）
                start_str = self._format_srt_time(subtitle.start_time)
                end_str = self._format_srt_time(subtitle.end_time)
                f.write(f"{start_str} --> {end_str}\n")

                # テキスト（2行まで）
                f.write(f"{subtitle.text_line1}\n")
                if subtitle.text_line2:
                    f.write(f"{subtitle.text_line2}\n")

                # 空行
                f.write("\n")

        self.logger.info(f"SRT file saved: {srt_path}")
        return srt_path
    
    def _format_srt_time(self, seconds: float) -> str:
        """
        秒数をSRT形式（HH:MM:SS,mmm）に変換
        
        Args:
            seconds: 秒数
            
        Returns:
            SRT形式のタイムコード文字列
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _save_timing_json(self, subtitles: List[SubtitleEntry]) -> Path:
        """
        タイミングJSONを保存

        Args:
            subtitles: 字幕エントリのリスト

        Returns:
            保存されたJSONファイルのPath
        """
        timing_path = self.phase_dir / "subtitle_timing.json"

        timing_data = {
            "subject": self.subject,
            "subtitle_count": len(subtitles),
            "total_duration": max([s.end_time for s in subtitles]) if subtitles else 0,
            "subtitles": [
                {
                    "index": s.index,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.end_time - s.start_time,
                    "text_line1": s.text_line1,
                    "text_line2": s.text_line2
                }
                for s in subtitles
            ]
        }

        with open(timing_path, 'w', encoding='utf-8') as f:
            json.dump(timing_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Timing JSON saved: {timing_path}")
        return timing_path

    def _normalize_section_timings(self, section_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        セクションのタイミング情報を正規化

        各セクションの char_start_times を、最初の文字が0秒から始まるように調整。
        これにより、音声生成時の最初の無音部分を除外できる。

        Args:
            section_data: セクションのタイミング情報

        Returns:
            正規化されたセクションデータ
        """
        char_start_times = section_data.get('char_start_times', [])
        char_end_times = section_data.get('char_end_times', [])

        if not char_start_times:
            return section_data

        # 最初の文字の開始時間（無音部分）
        first_char_start = min(char_start_times)

        if first_char_start > 0.1:  # 0.1秒以上の無音がある場合
            self.logger.info(
                f"Section {section_data.get('section_id')}: "
                f"Removing {first_char_start:.2f}s leading silence"
            )

            # タイミングを正規化
            normalized_data = section_data.copy()
            normalized_data['char_start_times'] = [
                t - first_char_start for t in char_start_times
            ]
            normalized_data['char_end_times'] = [
                t - first_char_start for t in char_end_times
            ]
            normalized_data['duration'] = (
                section_data.get('duration', 0) - first_char_start
            )

            return normalized_data

        return section_data

    def _split_long_sentence(
        self,
        sentence: Dict[str, Any],
        max_chars: int = 36
    ) -> List[Dict[str, Any]]:
        """
        長い文を分割（鍵かっこ対応版）

        鍵かっこがある場合のみ特別処理を行い、
        ない場合は既存ロジック（_split_long_sentence_original）を使用。

        Args:
            sentence: 文のデータ {'text': str, 'start_time': float, 'end_time': float, 'char_data': [...]}
            max_chars: 最大文字数（デフォルト36）

        Returns:
            分割された文のリスト
        """
        text = sentence['text']

        # ========== 【新規追加】鍵かっこチェック（ここから） ==========
        quotation_info = self._analyze_quotation(text)

        if quotation_info is not None:
            # 鍵かっこがある場合は専用ロジックで処理
            self.logger.debug(f"Quotation detected: {text[:30]}...")
            self.logger.debug(
                f"Quotation analysis: "
                f"inner_length={quotation_info['inner_length']}, "
                f"full='{quotation_info['full']}'"
            )
            return self._split_sentence_with_quotation(sentence, max_chars, quotation_info)
        # ========== 【新規追加】鍵かっこチェック（ここまで） ==========

        # 鍵かっこがない場合は既存ロジックを使用
        return self._split_long_sentence_original(sentence, max_chars)

    def _split_long_sentence_original(
        self,
        sentence: Dict[str, Any],
        max_chars: int = 36
    ) -> List[Dict[str, Any]]:
        """
        36文字を超える長い文を分割（オリジナル実装）

        注意: このメソッドは既存ロジックをそのまま保持。
              鍵かっこ対応は _split_long_sentence で行う。

        分割の優先順位:
        1. 20~36文字の範囲で、36文字目に一番近い「、」
        2. 「、」がない場合:
           - 助詞の後
           - ひらがな→漢字の境目
           - 漢字→ひらがなの境目
        3. 強制分割

        Args:
            sentence: 文のデータ {'text': str, 'start_time': float, 'end_time': float, 'char_data': [...]}
            max_chars: 最大文字数（デフォルト36）

        Returns:
            分割された文のリスト
        """
        text = sentence['text']

        # 36文字以内 → そのまま返す
        if len(text) <= max_chars:
            return [sentence]

        self.logger.debug(f"Splitting long sentence: {len(text)} chars")

        # ステップ1: 20~36文字の範囲で「、」を探す
        split_pos = None

        # 20~36文字の範囲で「、」を探す（36文字目に近い方から）
        for pos in range(max_chars, 19, -1):  # 36文字目から20文字目まで逆順
            if pos < len(text) and text[pos] == '、':
                split_pos = pos + 1  # 「、」を含める
                self.logger.debug(f"Found comma at position {pos} (range 20-36)")
                break

        # ステップ2: 「、」が見つからない場合、助詞・文字種境目を探す
        if split_pos is None:
            # 助詞リスト
            particles = ['は', 'が', 'を', 'に', 'で', 'と', 'も', 'や', 'から', 'まで', 'より']

            # 16~20文字の範囲で助詞を探す
            for pos in range(20, 15, -1):
                if pos < len(text) and text[pos] in particles:
                    split_pos = pos + 1
                    self.logger.debug(f"Found particle at position {pos}")
                    break

            # ひらがな→漢字の境目を探す（16~20文字の範囲）
            if split_pos is None:
                for pos in range(20, 15, -1):
                    if pos > 0 and pos < len(text):
                        prev_char = text[pos - 1]
                        curr_char = text[pos]
                        if self._get_char_type(prev_char) == 'hiragana' and \
                           self._get_char_type(curr_char) == 'kanji':
                            split_pos = pos
                            self.logger.debug(f"Found hiragana->kanji boundary at position {pos}")
                            break

            # 漢字→ひらがなの境目を探す（16~20文字の範囲）
            if split_pos is None:
                for pos in range(20, 15, -1):
                    if pos > 0 and pos < len(text):
                        prev_char = text[pos - 1]
                        curr_char = text[pos]
                        if self._get_char_type(prev_char) == 'kanji' and \
                           self._get_char_type(curr_char) == 'hiragana':
                            split_pos = pos
                            self.logger.debug(f"Found kanji->hiragana boundary at position {pos}")
                            break

        # ステップ3: 強制分割（適切な位置が見つからない場合）
        if split_pos is None:
            split_pos = max_chars // 2  # 真ん中で分割
            self.logger.debug(f"Force split at position {split_pos}")

        # 文字列を分割
        first_part_text = text[:split_pos]
        remaining_text = text[split_pos:]

        # タイミング情報を計算
        total_duration = sentence['end_time'] - sentence['start_time']
        total_chars = len(text)
        first_part_ratio = len(first_part_text) / total_chars
        first_part_duration = total_duration * first_part_ratio

        result = [
            {
                'text': first_part_text,
                'start_time': sentence['start_time'],
                'end_time': sentence['start_time'] + first_part_duration
            }
        ]

        # 残りのテキストを再帰的に処理
        if remaining_text:
            remaining_sentence = {
                'text': remaining_text,
                'start_time': sentence['start_time'] + first_part_duration,
                'end_time': sentence['end_time']
            }
            result.extend(self._split_long_sentence_original(remaining_sentence, max_chars))

        self.logger.debug(f"Split into {len(result)} parts")
        return result

    def _generate_from_audio_timing(self, timing_path: Path) -> List[SubtitleEntry]:
        """
        audio_timing.json から字幕を生成（シンプルルール）

        ルール:
        1. 短い文（36文字以内）→ そのまま出す
        2. 長い文（36文字超）→ 読点で分割
        3. 各字幕を2行に分割（18文字×2）
        4. 句読点は最後に削除
        """
        self.logger.info(f"Loading audio timing data from: {timing_path}")

        with open(timing_path, 'r', encoding='utf-8') as f:
            timing_data = json.load(f)

        # 各セクションのタイミングを正規化（無音除去）
        normalized_timing_data = []
        for section_data in timing_data:
            normalized_section = self._normalize_section_timings(section_data)
            normalized_timing_data.append(normalized_section)

        subtitles = []
        subtitle_index = 1

        # 設定を取得
        min_duration = self.phase_config.get("timing", {}).get("min_display_duration", 4.0)
        max_chars_per_line = self.phase_config.get("max_chars_per_line", 18)
        max_chars_per_subtitle = max_chars_per_line * 2  # 36文字

        # 1行の絶対的な制限（厳格に18文字）
        ABSOLUTE_MAX_CHARS_PER_LINE = 18  # これを超えたら必ず字幕を分割

        for section_data in normalized_timing_data:
            section_id = section_data.get('section_id', 0)
            characters = section_data.get('characters', [])
            char_start_times = section_data.get('char_start_times', [])
            char_end_times = section_data.get('char_end_times', [])
            offset = section_data.get('offset', 0.0)

            # display_text を取得（フォールバックで text または tts_text を使用）
            display_text = section_data.get('display_text') or section_data.get('tts_text') or section_data.get('text', '')

            # ステップ1: 「。」で文を分割（タイミング情報を取得）
            tts_sentences = self._split_by_period_with_timing(
                characters, char_start_times, char_end_times, offset
            )

            # display_text を '。' で分割（鍵かっこ内は無視）
            display_sentences_text = self._split_by_period_smart(display_text)

            # display_text で置き換え
            sentences = []
            for idx, tts_sent in enumerate(tts_sentences):
                if idx < len(display_sentences_text):
                    # display_text を使用
                    sentence = {
                        'text': display_sentences_text[idx],
                        'start_time': tts_sent['start_time'],
                        'end_time': tts_sent['end_time'],
                        'char_data': tts_sent.get('char_data', [])
                    }
                    sentences.append(sentence)
                    self.logger.debug(f"Using display_text: {display_sentences_text[idx][:30]}...")
                else:
                    # フォールバック: tts_text を使用
                    sentences.append(tts_sent)
                    self.logger.warning(f"Display text not available for sentence {idx}, using TTS text")

            # display_text の方が文が多い場合は警告
            if len(display_sentences_text) > len(tts_sentences):
                self.logger.warning(
                    f"Display text has more sentences ({len(display_sentences_text)}) "
                    f"than TTS text ({len(tts_sentences)})"
                )

            # ステップ2: 各文を処理（シンプルルール）
            for sentence in sentences:
                sentence_text = sentence['text']
                sentence_len = len(sentence_text)
                self.logger.debug(f"Processing sentence: '{sentence_text[:50]}...'")

                # 鍵かっこの有無をチェック
                has_quotation = '「' in sentence_text and '」' in sentence_text

                # 長い文、または鍵かっこがある文 → 分割処理
                if sentence_len > max_chars_per_subtitle or has_quotation:
                    if has_quotation:
                        self.logger.debug(f"Sentence with quotation ({sentence_len} chars), using special logic...")
                    else:
                        self.logger.debug(f"Long sentence ({sentence_len} chars), splitting...")
                    sentence_parts = self._split_long_sentence(sentence, max_chars_per_subtitle)
                else:
                    # 短い文かつ鍵かっこなし → そのまま
                    sentence_parts = [sentence]

                # ステップ3: 各パートを字幕に変換
                for part in sentence_parts:
                    # 2行に分割（18文字×2）
                    # 鍵かっこがある場合は専用メソッドを使用
                    if '「' in part['text'] and '」' in part['text']:
                        line1, line2 = self._split_quotation_into_two_lines(
                            part['text'],
                            max_chars_per_line
                        )
                    else:
                        line1, line2 = self._split_text_into_lines_strict(
                            part['text'],
                            max_chars_per_line,
                            ABSOLUTE_MAX_CHARS_PER_LINE
                        )

                    # 字幕エントリ作成（句読点削除は後で実行される）
                    subtitle = SubtitleEntry(
                        index=subtitle_index,
                        start_time=part['start_time'],
                        end_time=part['end_time'],
                        text_line1=line1,
                        text_line2=line2
                    )
                    subtitles.append(subtitle)
                    subtitle_index += 1

        self.logger.info(f"Generated {len(subtitles)} subtitles")
        return subtitles

    def _group_characters_into_words(
        self,
        text: str,
        characters: List[str],
        start_times: List[float],
        end_times: List[float],
        offset: float
    ) -> List[Dict[str, Any]]:
        """
        文字レベルのタイミング情報を単語レベルに変換

        Args:
            text: 元のテキスト
            characters: 文字のリスト
            start_times: 各文字の開始時間
            end_times: 各文字の終了時間
            offset: 累積時間オフセット

        Returns:
            単語情報のリスト [{'text': str, 'start': float, 'end': float}, ...]
        """
        words = []
        current_word = ""
        word_start = None

        for i, char in enumerate(characters):
            if i >= len(start_times) or i >= len(end_times):
                break

            # オフセットを適用
            char_start = start_times[i] + offset
            char_end = end_times[i] + offset

            # 空白で単語を区切る
            # 「。」は完全に除外、「、」は前の単語に付ける
            if char == '。':
                # 「。」は無視（スキップ）
                continue
            elif char in [' ', '　', '\n']:
                # 空白・改行で単語を区切る
                if current_word:
                    words.append({
                        'text': current_word,
                        'start': word_start,
                        'end': char_start
                    })
                    current_word = ""
                    word_start = None
            elif char == '、':
                # 「、」は前の単語に付ける
                if current_word:
                    current_word += char
                else:
                    # 単語がない場合（行頭など）は無視
                    continue
            else:
                # 通常の文字
                if word_start is None:
                    word_start = char_start
                current_word += char

        # 最後の単語を追加
        if current_word and word_start is not None:
            words.append({
                'text': current_word,
                'start': word_start,
                'end': end_times[-1] + offset if end_times else word_start
            })

        return words

    def _create_subtitle_groups(
        self,
        words: List[Dict[str, Any]],
        max_words: int = 5,
        max_duration: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        単語を字幕グループにまとめる

        Args:
            words: 単語情報のリスト
            max_words: 1つの字幕に含める最大単語数
            max_duration: 1つの字幕の最大表示時間（秒）

        Returns:
            字幕グループのリスト [{'text': str, 'start_time': float, 'end_time': float}, ...]
        """
        groups = []
        current_group = []
        group_start = None

        for word in words:
            if not current_group:
                # 新しいグループを開始
                current_group = [word]
                group_start = word['start']
            else:
                # グループに追加するか判定
                group_duration = word['end'] - group_start
                should_split = (
                    len(current_group) >= max_words or
                    group_duration >= max_duration
                    # 句読点での区切りは削除（「。」は既に除外済み）
                )

                if should_split:
                    # 現在のグループを完了
                    groups.append({
                        'text': ''.join([w['text'] for w in current_group]),
                        'start_time': group_start,
                        'end_time': current_group[-1]['end']
                    })
                    # 新しいグループを開始
                    current_group = [word]
                    group_start = word['start']
                else:
                    # グループに追加
                    current_group.append(word)

        # 最後のグループを追加
        if current_group:
            groups.append({
                'text': ''.join([w['text'] for w in current_group]),
                'start_time': group_start,
                'end_time': current_group[-1]['end']
            })

        return groups

    def _split_by_period_smart(self, text: str) -> List[str]:
        """
        「。」で分割するが、鍵かっこ内の「。」は無視
        
        Args:
            text: 分割するテキスト
        
        Returns:
            分割された文のリスト（各文に「。」が含まれる）
        
        Examples:
            >>> _split_by_period_smart("こんにちは。元気ですか。")
            ['こんにちは。', '元気ですか。']
            
            >>> _split_by_period_smart("「見てくれ。太陽は動いている」と言った。")
            ['「見てくれ。太陽は動いている」', 'と言った。']
        """
        sentences = []
        current = ""
        in_quotation = False
        
        for char in text:
            current += char
            
            # 鍵かっこの開閉を追跡
            if char == '「':
                in_quotation = True
            elif char == '」':
                in_quotation = False
            
            # 句点で分割（ただし鍵かっこ内は除く）
            if char == '。':
                self.logger.debug(
                    f"Period in display_text: in_quotation={in_quotation}, "
                    f"current='{current[:30]}...'"
                )
                
                if not in_quotation:
                    self.logger.debug(f"  → Splitting")
                else:
                    self.logger.debug(f"  → Not splitting (inside quotation)")
            
            if char == '。' and not in_quotation:
                if current.strip():
                    sentences.append(current)
                current = ""
        
        # 残りを追加
        if current.strip():
            sentences.append(current)
        
        return sentences

    def _split_by_period_with_timing(
        self,
        characters: List[str],
        char_start_times: List[float],
        char_end_times: List[float],
        offset: float
    ) -> List[Dict[str, Any]]:
        """
        文字列を句読点「。」で分割し、各文のタイミング情報を付与
        
        ただし、鍵かっこ内の「。」では分割しない。

        Returns:
            [{'text': str, 'start_time': float, 'end_time': float,
              'char_data': [(char, start, end), ...]}, ...]
        """
        sentences = []
        current_sentence = ""
        sentence_start_time = None
        sentence_char_data = []
        in_quotation = False  # 鍵かっこ内フラグ

        for i, char in enumerate(characters):
            if i >= len(char_start_times) or i >= len(char_end_times):
                break

            char_start = char_start_times[i] + offset
            char_end = char_end_times[i] + offset

            if sentence_start_time is None:
                sentence_start_time = char_start

            current_sentence += char
            sentence_char_data.append((char, char_start, char_end))

            # 鍵かっこの開閉を追跡
            if char == '「':
                in_quotation = True
            elif char == '」':
                in_quotation = False

            # 「。」で文を区切る（ただし鍵かっこ内は除く）
            # 修正: char が複数文字の場合も考慮して endswith を使用
            if char.endswith('。'):
                self.logger.debug(
                    f"Period detected at pos {i}: char='{char}', "
                    f"in_quotation={in_quotation}, current='{current_sentence[:30]}...'"
                )
                
                if not in_quotation:
                    self.logger.debug(f"  → Splitting sentence")
                else:
                    self.logger.debug(f"  → Not splitting (inside quotation)")
            
            if char.endswith('。') and not in_quotation:
                # 句点の終了時刻を使用（セクション間は延長しない）
                # 延長は後段の _adjust_subtitle_timing_with_sentence_end で実施
                sentence_end_time = char_end

                sentences.append({
                    'text': current_sentence,
                    'start_time': sentence_start_time,
                    'end_time': sentence_end_time,  # 次の文字の開始時刻まで表示
                    'char_data': sentence_char_data
                })
                current_sentence = ""
                # 次の文の開始時刻を設定（改行文字などをスキップ）
                if i + 1 < len(characters):
                    # 改行や空白をスキップして次の実際の文字を探す
                    next_char_idx = i + 1
                    while next_char_idx < len(characters) and characters[next_char_idx] in ['\n', '\r', ' ']:
                        next_char_idx += 1

                    if next_char_idx < len(char_start_times):
                        sentence_start_time = char_start_times[next_char_idx] + offset
                    else:
                        sentence_start_time = None
                else:
                    sentence_start_time = None
                sentence_char_data = []

        # 最後の文
        if current_sentence and sentence_start_time is not None:
            last_end = char_end_times[-1] + offset if char_end_times else sentence_start_time
            sentences.append({
                'text': current_sentence,
                'start_time': sentence_start_time,
                'end_time': last_end,
                'char_data': sentence_char_data
            })

        return sentences

    def _split_by_multiple_commas(
        self,
        sentence: Dict[str, Any],
        max_chars_per_line: int = 15
    ) -> List[Dict[str, Any]]:
        """
        複数の「、」がある長めの文を分割
        
        各チャンクが1行（16文字程度）で収まるように細かく分割

        Args:
            sentence: 文のデータ（text, start_time, end_time, char_data）
            max_chars_per_line: 1行あたりの推奨最大文字数

        Returns:
            分割されたチャンクのリスト
        """
        text = sentence['text']
        char_data = sentence['char_data']

        # 「、」の位置を全て見つける
        comma_positions = [i for i, char in enumerate(text) if char == '、']

        if not comma_positions:
            # 「、」がない場合はそのまま返す
            return [{
                'text': text,
                'start_time': sentence['start_time'],
                'end_time': sentence['end_time']
            }]

        # 各「、」で分割してチャンクを作成
        chunks = []
        start_pos = 0

        for comma_pos in comma_positions:
            end_pos = comma_pos + 1  # 「、」を含める
            chunk_text = text[start_pos:end_pos]
            chunk_char_data = char_data[start_pos:end_pos]

            if chunk_char_data:
                chunk_start = chunk_char_data[0][1]
                chunk_end = chunk_char_data[-1][2]

                chunks.append({
                    'text': chunk_text,
                    'start_time': chunk_start,
                    'end_time': chunk_end
                })

            start_pos = end_pos

        # 最後の部分（最後の「、」の後ろ）
        if start_pos < len(text):
            chunk_text = text[start_pos:]
            chunk_char_data = char_data[start_pos:]

            if chunk_char_data:
                chunk_start = chunk_char_data[0][1]
                chunk_end = chunk_char_data[-1][2]

                chunks.append({
                    'text': chunk_text,
                    'start_time': chunk_start,
                    'end_time': chunk_end
                })

        return chunks

    def _split_sentence_by_comma_if_needed(
        self,
        sentence: Dict[str, Any],
        max_chars: int
    ) -> List[Dict[str, Any]]:
        """
        長い文を「、」で意味の区切りを入れて分割

        ロジック:
        1. 32文字以内なら何もしない
        2. 32文字超なら、32文字以内で最も後ろにある「、」で区切る
        3. 区切った後の部分がまだ32文字超なら、再帰的に処理
        """
        text = sentence['text']
        char_data = sentence['char_data']

        # 32文字以内ならそのまま
        if len(text) <= max_chars:
            return [{
                'text': text,
                'start_time': sentence['start_time'],
                'end_time': sentence['end_time']
            }]

        # 「、」の位置を全て見つける
        comma_positions = [i for i, char in enumerate(text) if char == '、']

        # 「、」がない場合は仕方ないのでそのまま
        if not comma_positions:
            return [{
                'text': text,
                'start_time': sentence['start_time'],
                'end_time': sentence['end_time']
            }]

        # 32文字以内で最も後ろにある「、」を見つける
        split_position = None
        for pos in comma_positions:
            if pos + 1 <= max_chars:  # 「、」を含めた位置
                split_position = pos + 1
            else:
                break

        # 適切な分割位置が見つからない（最初の「、」が32文字超）
        # → 強制的に最初の「、」で区切る
        if split_position is None:
            split_position = comma_positions[0] + 1

        # 分割
        first_part_text = text[:split_position]
        second_part_text = text[split_position:]

        first_part_char_data = char_data[:split_position]
        second_part_char_data = char_data[split_position:]

        # タイミング情報
        first_start = first_part_char_data[0][1] if first_part_char_data else sentence['start_time']
        first_end = first_part_char_data[-1][2] if first_part_char_data else sentence['start_time']

        second_start = second_part_char_data[0][1] if second_part_char_data else first_end
        second_end = second_part_char_data[-1][2] if second_part_char_data else sentence['end_time']

        # 最初のチャンク
        chunks = [{
            'text': first_part_text,
            'start_time': first_start,
            'end_time': first_end
        }]

        # 残りの部分を再帰的に処理
        if second_part_text:
            remaining_sentence = {
                'text': second_part_text,
                'start_time': second_start,
                'end_time': second_end,
                'char_data': second_part_char_data
            }
            remaining_chunks = self._split_sentence_by_comma_if_needed(
                remaining_sentence, max_chars
            )
            chunks.extend(remaining_chunks)

        return chunks

    def _split_text_into_lines(
        self,
        text: str,
        max_chars_per_line: int = 15
    ) -> tuple[str, str]:
        """
        字幕テキストを2行に分割

        Args:
            text: 分割するテキスト
            max_chars_per_line: 1行あたりの最大文字数

        Returns:
            (line1, line2) のタプル。line2は空文字列の場合もある
        """
        # 短い場合はそのまま返す
        if len(text) <= max_chars_per_line:
            return (text, "")

        # 2行分を超える場合は、最大文字数×2で切り詰め
        max_total = max_chars_per_line * 2
        if len(text) > max_total:
            text = text[:max_total]

        # 読点「、」で分割を試みる
        if '、' in text:
            parts = text.split('、')
            # 最初の部分が適切な長さなら、そこで分割
            if len(parts[0]) <= max_chars_per_line:
                line1 = parts[0] + '、'
                line2 = '、'.join(parts[1:])
                # line2が長すぎる場合は、さらに調整
                if len(line2) > max_chars_per_line:
                    # line2を切り詰める
                    line2 = line2[:max_chars_per_line]
                return (line1, line2)

        # 読点がない、または適切な位置にない場合は、中央付近で分割
        mid = len(text) // 2
        # 中央付近の適切な区切り位置を探す（前後3文字の範囲）
        best_pos = mid
        for offset in range(4):
            # 前方を探索
            pos = mid - offset
            if pos > 0 and pos < len(text):
                # 分割に適した文字かチェック
                if text[pos] in ['、', ' ', '　']:
                    best_pos = pos + 1
                    break
            # 後方を探索
            pos = mid + offset
            if pos > 0 and pos < len(text):
                if text[pos] in ['、', ' ', '　']:
                    best_pos = pos + 1
                    break

        # 各行が最大文字数を超えないように調整
        line1 = text[:best_pos].strip()
        line2 = text[best_pos:].strip()

        if len(line1) > max_chars_per_line:
            line1 = line1[:max_chars_per_line]
        if len(line2) > max_chars_per_line:
            line2 = line2[:max_chars_per_line]

        return (line1, line2)

    def _split_quotation_into_two_lines(
        self,
        text: str,
        max_chars_per_line: int = 18
    ) -> tuple[str, str]:
        """
        鍵かっこ内テキストを2行に分割
        
        優先順位:
        1. \n がある場合は\nで分割（各行が18文字以内の場合）
        2. それ以外は通常の分割ロジック
        
        Args:
            text: 分割するテキスト（「」を含む可能性あり）
            max_chars_per_line: 1行あたりの最大文字数
        
        Returns:
            (line1, line2) のタプル
        """
        # 鍵かっこを除去
        if text.startswith('「'):
            text = text[1:]
        if text.endswith('」'):
            text = text[:-1]
        
        # 改行がある場合
        if '\n' in text:
            parts = text.split('\n', 1)  # 最初の改行で2分割
            line1 = parts[0].strip()
            line2 = parts[1].strip() if len(parts) > 1 else ""
            
            # 各行が18文字以内か確認
            if len(line1) <= max_chars_per_line and len(line2) <= max_chars_per_line:
                # 改行で分割可能
                return (line1, line2)
            
            # 18文字超える場合は、改行を削除して通常分割
            text = text.replace('\n', '')
        
        # 改行がない、または18文字超える場合は通常の分割
        return self._split_text_into_lines_strict(text, max_chars_per_line, max_chars_per_line)

    def _split_text_into_lines_strict(
        self,
        text: str,
        recommended_max: int = 16,
        absolute_max: int = 16
    ) -> tuple[str, str]:
        """
        字幕テキストを2行に分割（厳密版・改善版）

        分割優先順位:
        1. 「、」での分割
        2. ひらがな→漢字の境界
        3. 漢字→ひらがなの境界
        4. カタカナとの境界
        5. 中央での強制分割

        ルール:
        - 推奨: 各行16文字以内
        - 最大: 各行16文字以内（厳格な制限）
        - 繰り返し記号（々、ー等）の直前では分割しない
        - 句読点のみの行は作らない（句読点を削除）

        Args:
            text: 分割するテキスト
            recommended_max: 推奨最大文字数（16文字）
            absolute_max: 絶対的な最大文字数（16文字）

        Returns:
            (line1, line2) のタプル
        """
        # 短い場合はそのまま返す
        if len(text) <= recommended_max:
            return (text, "")

        # 優先順位1: 「、」がある場合
        if '、' in text:
            # 全ての「、」の位置を取得
            comma_positions = [i for i, char in enumerate(text) if char == '、']

            # 最適な「、」を探す（各行が推奨文字数に近くなるように）
            best_split = None
            best_score = float('inf')

            for pos in comma_positions:
                split_pos = pos + 1  # 「、」を含める
                line1_len = split_pos
                line2_len = len(text) - split_pos

                # 絶対制限チェック
                if line1_len <= absolute_max and line2_len <= absolute_max:
                    # スコア計算: 推奨値からの乖離を最小化
                    score = abs(line1_len - recommended_max) + abs(line2_len - recommended_max)
                    if score < best_score:
                        best_score = score
                        best_split = split_pos

            if best_split:
                line1 = text[:best_split]
                line2 = text[best_split:]
                # 句読点のみの行をチェック
                line1, line2 = self._remove_punctuation_only_line(line1, line2)
                return (line1, line2)

        # 優先順位2-4: 文字種の境界で分割を試みる
        # 理想的な分割位置の範囲を計算
        ideal_min = max(1, recommended_max - 5)  # 推奨値の前後5文字
        ideal_max = min(len(text) - 1, recommended_max + 5)

        # 文字種の境界を探す（理想的な範囲内）
        best_boundary_split = None
        best_boundary_score = float('inf')

        for pos in range(ideal_min, ideal_max + 1):
            if pos <= 0 or pos >= len(text):
                continue

            line1_len = pos
            line2_len = len(text) - pos

            # 絶対制限チェック
            if line1_len > absolute_max or line2_len > absolute_max:
                continue

            # 前後の文字を取得
            prev_char = text[pos - 1]
            curr_char = text[pos]

            # 繰り返し記号の直前はスキップ
            if curr_char in ['々', 'ー', '・', '～', '…']:
                continue

            # 文字種を判定
            prev_type = self._get_char_type(prev_char)
            curr_type = self._get_char_type(curr_char)

            # 文字種の境界でスコアを計算
            if prev_type != curr_type:
                # 優先度を設定
                priority = 0

                # ひらがな→漢字（最も優先）
                if prev_type == 'hiragana' and curr_type == 'kanji':
                    priority = 1
                # 漢字→ひらがな（2番目）
                elif prev_type == 'kanji' and curr_type == 'hiragana':
                    priority = 2
                # カタカナとの境界（3番目）
                elif prev_type == 'katakana' or curr_type == 'katakana':
                    priority = 3
                # その他の境界
                else:
                    priority = 4

                # スコア計算: 優先度 + 推奨値からの乖離
                score = priority * 100 + abs(line1_len - recommended_max) + abs(line2_len - recommended_max)

                if score < best_boundary_score:
                    best_boundary_score = score
                    best_boundary_split = pos

        if best_boundary_split:
            line1 = text[:best_boundary_split]
            line2 = text[best_boundary_split:]
            # 句読点のみの行をチェック
            line1, line2 = self._remove_punctuation_only_line(line1, line2)
            return (line1, line2)

        # 優先順位5: 中央での強制分割（最終手段）
        # まず中央で試す
        mid = len(text) // 2

        # 中央付近で単語の区切りを探す
        for offset in range(min(5, len(text) // 4)):  # 前後5文字の範囲
            # 前方
            if mid - offset > 0 and mid - offset <= absolute_max:
                pos = mid - offset
                if len(text) - pos <= absolute_max:  # line2も制限内
                    # 自然な区切り位置かチェック
                    if self._is_good_split_position(text, pos):
                        line1 = text[:pos]
                        line2 = text[pos:]
                        # 句読点のみの行をチェック
                        line1, line2 = self._remove_punctuation_only_line(line1, line2)
                        return (line1, line2)

            # 後方
            if mid + offset < len(text) and mid + offset <= absolute_max:
                pos = mid + offset
                if len(text) - pos <= absolute_max:  # line2も制限内
                    if self._is_good_split_position(text, pos):
                        line1 = text[:pos]
                        line2 = text[pos:]
                        # 句読点のみの行をチェック
                        line1, line2 = self._remove_punctuation_only_line(line1, line2)
                        return (line1, line2)

        # 適切な位置が見つからない場合: 強制的に中央で分割
        # ただし、絶対制限は守る
        if mid > absolute_max:
            mid = absolute_max

        line1 = text[:mid]
        line2 = text[mid:]
        # 句読点のみの行をチェック
        line1, line2 = self._remove_punctuation_only_line(line1, line2)
        return (line1, line2)

    def _remove_punctuation_only_line(
        self,
        line1: str,
        line2: str
    ) -> tuple[str, str]:
        """
        句読点のみの行を削除

        line1またはline2が句読点のみの場合、その句読点を削除する

        Args:
            line1: 1行目のテキスト
            line2: 2行目のテキスト

        Returns:
            (修正後のline1, 修正後のline2) のタプル
        """
        # 句読点のリスト
        punctuation_chars = ['。', '！', '？', '、', '…']

        # line2が句読点のみかチェック
        if line2 and all(char in punctuation_chars for char in line2.strip()):
            # 句読点を削除
            return (line1.rstrip(), "")

        # line1が句読点のみかチェック（稀なケース）
        if line1 and all(char in punctuation_chars for char in line1.strip()):
            # line1を削除してline2をline1に
            return (line2, "")

        return (line1, line2)

    def _is_good_split_position(self, text: str, pos: int) -> bool:
        """
        テキストの分割位置が適切かどうかを判定

        適切な分割位置:
        - 句読点の直後（。、！？）
        - ひらがな→カタカナの境界
        - カタカナ→漢字の境界
        - 漢字→ひらがなの境界

        不適切な分割位置:
        - 繰り返し記号・長音記号の直前（々、ー、・、～、…）

        Args:
            text: 元のテキスト
            pos: 分割位置

        Returns:
            適切ならTrue
        """
        if pos <= 0 or pos >= len(text):
            return False

        prev_char = text[pos - 1]
        curr_char = text[pos]

        # 句読点の直後
        if prev_char in ['。', '、', '！', '？', '」', '』']:
            return True

        # 繰り返し記号・長音記号の直前は分割しない
        if curr_char in ['々', 'ー', '・', '～', '…']:
            return False

        # 文字種の境界
        prev_type = self._get_char_type(prev_char)
        curr_type = self._get_char_type(curr_char)

        # ひらがな→カタカナ、カタカナ→漢字など
        if prev_type != curr_type:
            return True

        return False

    def _get_char_type(self, char: str) -> str:
        """
        文字の種類を判定

        Returns:
            'hiragana', 'katakana', 'kanji', 'other'
        """
        code = ord(char)

        # ひらがな: U+3040 - U+309F
        if 0x3040 <= code <= 0x309F:
            return 'hiragana'

        # カタカナ: U+30A0 - U+30FF
        if 0x30A0 <= code <= 0x30FF:
            return 'katakana'

        # 漢字: U+4E00 - U+9FFF
        if 0x4E00 <= code <= 0x9FFF:
            return 'kanji'

        return 'other'

    def _analyze_quotation(self, text: str) -> Optional[Dict[str, Any]]:
        """
        鍵かっこを分析（新規メソッド）

        Args:
            text: 分析対象のテキスト

        Returns:
            鍵かっこ情報の辞書、または None
            {
                'start': int,      # 「の位置
                'end': int,        # 」の位置
                'length': int,     # 「...」全体の長さ
                'inner_text': str, # 「」の中身
                'before': str,     # 「の前のテキスト
                'after': str       # 」の後のテキスト
            }
        """
        # 「と」を探す
        start = text.find('「')
        end = text.find('」')

        # 鍵かっこがない、または不完全な場合はNone
        if start == -1 or end == -1 or start >= end:
            return None

        # 複数の鍵かっこがある場合は最初の1組のみ処理
        # （複雑なケースは既存ロジックに任せる）

        inner_text = text[start+1:end]
        quotation_full = text[start:end+1]  # 「...」全体
        
        # 改行を除いた長さを計算
        inner_text_without_newline = inner_text.replace('\n', '')

        return {
            'start': start,
            'end': end,
            'length': len(quotation_full),
            'inner_text': inner_text,
            'inner_length': len(inner_text_without_newline),  # 改行除外
            'before': text[:start].strip(),
            'after': text[end+1:].strip(),
            'full': quotation_full
        }

    def _split_sentence_with_quotation(
        self,
        sentence: Dict,
        max_chars: int,
        quotation_info: Dict[str, Any]
    ) -> List[Dict]:
        """
        鍵かっこを含む文を分割（新規メソッド）

        核心ルール:
        - 鍵かっこ内が36文字以内 → 1つの字幕として扱う（句点で分割しない）
        - 鍵かっこ内が37文字以上 → 既存ロジックで分割（鍵かっこは後で付与）

        Args:
            sentence: 文の情報 {'text': str, 'start_time': float, 'end_time': float, ...}
            max_chars: 最大文字数（36）
            quotation_info: _analyze_quotation の結果

        Returns:
            分割された文のリスト
        """
        text = sentence['text']
        q_info = quotation_info

        # ========================================
        # ケース1: 鍵かっこ内が36文字以内
        # → 1つの字幕として扱う（句点で分割しない）
        # ========================================
        if q_info['inner_length'] <= 36:
            self.logger.debug(
                f"Short quotation ({q_info['inner_length']} chars), keeping as one subtitle"
            )

            parts = []

            # パート1: 前の文
            if q_info['before']:
                parts.append({
                    'text': q_info['before'],
                    'start_time': sentence['start_time'],
                    'end_time': sentence['end_time'],
                    'char_data': sentence.get('char_data', [])
                })

            # パート2: 鍵かっこ部分（そのまま）
            parts.append({
                'text': q_info['full'],
                'start_time': sentence['start_time'],
                'end_time': sentence['end_time'],
                'char_data': sentence.get('char_data', [])
            })

            # パート3: 後ろの文
            if q_info['after']:
                parts.append({
                    'text': q_info['after'],
                    'start_time': sentence['start_time'],
                    'end_time': sentence['end_time'],
                    'char_data': sentence.get('char_data', [])
                })

            return parts

        # ========================================
        # ケース2: 鍵かっこ内が37文字以上
        # → 既存ロジックで分割してから鍵かっこを付与
        # ========================================
        else:
            self.logger.debug(
                f"Long quotation ({q_info['inner_length']} chars), splitting with existing logic"
            )

            # 鍵かっこを外して既存ロジックで分割
            temp_sentence = {
                'text': q_info['inner_text'],  # 「」を除いた中身
                'start_time': sentence['start_time'],
                'end_time': sentence['end_time'],
                'char_data': sentence.get('char_data', [])
            }

            # 既存の分割ロジックを呼び出す
            # ※ この時点で句点での分割が行われる
            inner_parts = self._split_long_sentence_original(temp_sentence, max_chars)

            # 分割結果の最初と最後に「」を付ける
            if inner_parts:
                inner_parts[0]['text'] = '「' + inner_parts[0]['text']
                inner_parts[-1]['text'] = inner_parts[-1]['text'] + '」'

            # 前後の文も追加
            result = []

            # パート0: 前の文
            if q_info['before']:
                result.append({
                    'text': q_info['before'],
                    'start_time': sentence['start_time'],
                    'end_time': sentence['end_time'],
                    'char_data': sentence.get('char_data', [])
                })

            # パート1〜N: 鍵かっこ内の分割結果
            result.extend(inner_parts)

            # パートN+1: 後ろの文
            if q_info['after']:
                result.append({
                    'text': q_info['after'],
                    'start_time': sentence['start_time'],
                    'end_time': sentence['end_time'],
                    'char_data': sentence.get('char_data', [])
                })

            return result

    def _adjust_subtitle_timing_with_sentence_end(
        self,
        subtitles: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        句点（。！？）で終わる字幕のみ、次の字幕開始0.3秒前まで延長を許可

        ルール:
        1. 字幕の開始時刻は絶対に変更しない（ElevenLabs FA通り）
        2. 字幕が句点（。！？）で終わる場合のみ、終了時刻を延長可能
        3. 延長は次の字幕開始の0.3秒前まで
        4. 句点で終わらない字幕（、など）は延長しない

        Args:
            subtitles: 調整前の字幕リスト

        Returns:
            調整後の字幕リスト
        """
        # 設定を取得
        extension_config = self.phase_config.get("sentence_end_extension", {})
        enabled = extension_config.get("enabled", True)
        next_start_margin = extension_config.get("next_start_margin", 0.3)

        if not enabled:
            self.logger.info("Sentence end extension is disabled")
            return subtitles

        self.logger.info(
            f"Adjusting subtitle timing for sentence endings "
            f"(margin: {next_start_margin}s)"
        )

        adjusted = []
        extended_count = 0

        for i, sub in enumerate(subtitles):
            # 全行のテキストを結合して句点判定
            full_text = sub.text_line1
            if sub.text_line2:
                full_text += sub.text_line2

            # デフォルトは元の終了時刻
            new_end = sub.end_time

            # 🔍 デバッグログ: テキスト末尾と句点判定
            trimmed = full_text.rstrip()
            end_snippet = trimmed[-5:] if len(trimmed) >= 5 else trimmed
            ends_with_punct = trimmed.endswith(('。', '！', '？'))
            self.logger.debug(
                f"字幕 {sub.index}: 末尾='{end_snippet}' (句点判定: {ends_with_punct})"
            )

            # 句点（。！？）で終わる場合のみ延長を検討
            if ends_with_punct:
                # 次の字幕が存在するか確認
                if i < len(subtitles) - 1:
                    next_start = subtitles[i + 1].start_time

                    # 次の字幕開始の0.3秒前まで延長可能
                    max_end = next_start - next_start_margin

                    # 現在の終了時刻より後なら延長
                    if max_end > sub.end_time:
                        old_end = sub.end_time
                        new_end = max_end
                        extended_count += 1
                        self.logger.info(
                            f"字幕 {sub.index}: 句点終わりのため延長 "
                            f"{old_end:.3f}秒 → {new_end:.3f}秒 "
                            f"(+{new_end - old_end:.3f}秒)"
                        )
                    else:
                        # 🔍 延長できない理由
                        self.logger.debug(
                            f"字幕 {sub.index}: 句点あるが延長不要 "
                            f"(max_end={max_end:.3f}秒 <= current_end={sub.end_time:.3f}秒)"
                        )
                else:
                    # 🔍 最後の字幕
                    self.logger.debug(f"字幕 {sub.index}: 句点あるが最後の字幕のため延長なし")
            else:
                # 🔍 句点で終わらない理由を記録（ギャップ情報）
                if i < len(subtitles) - 1:
                    next_start = subtitles[i + 1].start_time
                    gap = next_start - sub.end_time
                    self.logger.debug(
                        f"字幕 {sub.index}: 句点なし（延長スキップ） gap={gap:.3f}秒"
                    )

            # 新しい字幕エントリを作成
            adjusted_sub = SubtitleEntry(
                index=sub.index,
                start_time=sub.start_time,  # 開始は絶対に変更しない
                end_time=new_end,           # 句点で終わる場合のみ延長
                text_line1=sub.text_line1,
                text_line2=sub.text_line2
            )
            adjusted.append(adjusted_sub)

        self.logger.info(
            f"Subtitle timing adjustment complete: {extended_count}/{len(subtitles)} subtitles extended"
        )
        return adjusted

    def _extend_subtitle_display(self, subtitles: List[SubtitleEntry]) -> List[SubtitleEntry]:
        """
        字幕の表示時間を延長（次の字幕の0.2秒前まで）

        Args:
            subtitles: 字幕エントリのリスト

        Returns:
            調整済み字幕エントリのリスト
        """
        adjusted_subtitles = []
        extended_count = 0

        for i, subtitle in enumerate(subtitles):
            # 最後の字幕以外
            if i < len(subtitles) - 1:
                next_subtitle = subtitles[i + 1]

                # 次の字幕開始の0.2秒前まで延長可能
                max_end_time = next_subtitle.start_time - 0.2

                # 現在の終了時間と比較して長い方を採用
                if subtitle.end_time < max_end_time:
                    old_end = subtitle.end_time
                    subtitle = SubtitleEntry(
                        index=subtitle.index,
                        start_time=subtitle.start_time,
                        end_time=max_end_time,
                        text_line1=subtitle.text_line1,
                        text_line2=subtitle.text_line2
                    )
                    extended_count += 1
                    self.logger.debug(
                        f"Extended subtitle {i+1}: "
                        f"{subtitle.start_time:.2f}s - {old_end:.2f}s -> {subtitle.end_time:.2f}s "
                        f"(extended by {max_end_time - old_end:.2f}s)"
                    )

            adjusted_subtitles.append(subtitle)

        self.logger.info(
            f"Extended subtitle display times: {extended_count}/{len(subtitles)} subtitles extended "
            f"(0.2s margin before next)"
        )
        return adjusted_subtitles

    def _fix_three_line_quotations(
        self,
        subtitles: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        鍵かっこ内で3行になっている字幕を修正
        
        3行目がある場合:
        - 3行目を次の字幕の1行目に移動
        - 鍵かっこの場合のみ適用
        
        Args:
            subtitles: 字幕リスト
        
        Returns:
            修正後の字幕リスト
        """
        fixed_subtitles = []
        carry_over_text = ""  # 次の字幕に繰り越すテキスト
        
        for i, subtitle in enumerate(subtitles):
            # 前の字幕からの繰り越しがある場合
            if carry_over_text:
                # 現在の字幕の1行目に追加
                subtitle.text_line1 = carry_over_text + subtitle.text_line1
                carry_over_text = ""
            
            # 3行目があるかチェック
            if subtitle.text_line3:
                # 鍵かっこがある場合のみ処理
                full_text = subtitle.text_line1 + subtitle.text_line2 + subtitle.text_line3
                
                if '「' in full_text or '」' in full_text:
                    self.logger.debug(
                        f"Found 3-line quotation at subtitle {subtitle.index}, "
                        f"moving line3 to next subtitle"
                    )
                    
                    # 3行目を次の字幕に繰り越し
                    carry_over_text = subtitle.text_line3
                    
                    # 現在の字幕は2行に修正
                    new_subtitle = SubtitleEntry(
                        index=subtitle.index,
                        start_time=subtitle.start_time,
                        end_time=subtitle.end_time,
                        text_line1=subtitle.text_line1,
                        text_line2=subtitle.text_line2
                    )
                    fixed_subtitles.append(new_subtitle)
                else:
                    # 鍵かっこがない場合はそのまま
                    fixed_subtitles.append(subtitle)
            else:
                # 3行目がない場合はそのまま
                fixed_subtitles.append(subtitle)
        
        # 最後に繰り越しが残っている場合（通常はありえない）
        if carry_over_text:
            self.logger.warning(f"Carry-over text remains: {carry_over_text}")
            # 最後の字幕に追加
            if fixed_subtitles:
                last_subtitle = fixed_subtitles[-1]
                fixed_subtitles[-1] = SubtitleEntry(
                    index=last_subtitle.index,
                    start_time=last_subtitle.start_time,
                    end_time=last_subtitle.end_time,
                    text_line1=last_subtitle.text_line1 + carry_over_text,
                    text_line2=last_subtitle.text_line2
                )
        
        return fixed_subtitles

    def _remove_punctuation_from_subtitles(
        self,
        subtitles: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        字幕から句読点を削除

        重要: 分割ロジックの後に実行すること
        分割位置の判定には句読点を使うため、削除は最後に行う

        削除対象: 。、！？，．（ただし鍵かっこ内は除く）
        削除しない: 「」『』・～…（カギカッコや中点等）、鍵かっこ内の句読点

        Args:
            subtitles: 句読点を含む字幕リスト

        Returns:
            句読点を削除した字幕リスト
        """
        # 削除対象の句読点
        punctuation_to_remove = ['。', '！', '？', '，', '．']

        cleaned_subtitles = []

        for subtitle in subtitles:
            # 🔥 NEW: 鍵かっこ内の句読点は残す処理
            # 2行にまたがる鍵かっこに対応するため、結合してから処理
            combined_text = subtitle.text_line1
            if subtitle.text_line2:
                combined_text += subtitle.text_line2
            
            # 結合テキストから句読点を削除（鍵かっこ内は残す）
            # 同時に、各文字が処理後のどの位置に対応するかを記録
            cleaned_combined, char_mapping = self._remove_punctuation_except_in_quotation_with_mapping(
                combined_text,
                punctuation_to_remove
            )
            
            # 元の行1の最後の文字が処理後のどの位置に対応するかを取得
            original_line1_len = len(subtitle.text_line1)
            split_pos = len(cleaned_combined)
            if original_line1_len > 0 and original_line1_len - 1 < len(char_mapping):
                # 行1の最後の文字の位置を取得（削除された文字の場合は前の有効な文字を探す）
                for i in range(original_line1_len - 1, -1, -1):
                    if i < len(char_mapping) and char_mapping[i] != -1:
                        split_pos = char_mapping[i] + 1
                        break
            
            # 分割
            line1 = cleaned_combined[:split_pos] if split_pos > 0 else ""
            line2 = cleaned_combined[split_pos:] if subtitle.text_line2 else ""

            # 空の字幕をスキップ（句読点のみの行が削除されて空になった場合）
            if not line1.strip() and not line2.strip():
                self.logger.debug(f"Skipping empty subtitle at index {subtitle.index}")
                continue

            # 新しいSubtitleEntryを作成
            cleaned_subtitle = SubtitleEntry(
                index=subtitle.index,
                start_time=subtitle.start_time,
                end_time=subtitle.end_time,
                text_line1=line1,
                text_line2=line2
            )

            cleaned_subtitles.append(cleaned_subtitle)

        # インデックスを再割り当て（空の字幕をスキップした場合に連番にする）
        for i, subtitle in enumerate(cleaned_subtitles, start=1):
            subtitle.index = i

        self.logger.info(f"Removed punctuation from {len(cleaned_subtitles)} subtitles")
        return cleaned_subtitles

    def _remove_punctuation_except_in_quotation_with_mapping(
        self,
        text: str,
        punctuation_to_remove: List[str]
    ) -> tuple[str, List[int]]:
        """
        鍵かっこ内の句読点は残して削除（文字位置のマッピングも返す）
        
        Args:
            text: 処理対象テキスト
            punctuation_to_remove: 削除対象の句読点リスト
        
        Returns:
            (処理後のテキスト, 元の位置→処理後位置のマッピング)
        """
        result = []
        char_mapping = []  # 元の位置 -> 処理後の位置
        in_quotation = False
        result_pos = 0
        
        for i, char in enumerate(text):
            if char == '「' or char == '『':
                in_quotation = True
                result.append(char)
                char_mapping.append(result_pos)
                result_pos += 1
            elif char == '」' or char == '』':
                in_quotation = False
                result.append(char)
                char_mapping.append(result_pos)
                result_pos += 1
            elif char in punctuation_to_remove and not in_quotation:
                # 鍵かっこ外の句読点のみ削除（マッピングには含めない）
                char_mapping.append(-1)  # 削除された文字
            else:
                result.append(char)
                char_mapping.append(result_pos)
                result_pos += 1
        
        return ''.join(result), char_mapping

    def _remove_punctuation_except_in_quotation(
        self,
        text: str,
        punctuation_to_remove: List[str]
    ) -> str:
        """
        鍵かっこ内の句読点は残して削除
        
        Args:
            text: 処理対象テキスト
            punctuation_to_remove: 削除対象の句読点リスト
        
        Returns:
            処理後のテキスト
        """
        result = []
        in_quotation = False
        
        for char in text:
            if char == '「' or char == '『':
                in_quotation = True
                result.append(char)
            elif char == '」' or char == '』':
                in_quotation = False
                result.append(char)
            elif char in punctuation_to_remove and not in_quotation:
                # 鍵かっこ外の句読点のみ削除
                continue
            else:
                result.append(char)
        
        return ''.join(result)

    def _save_generation_metadata(self, subtitle_gen: SubtitleGeneration):
        """
        生成メタデータを保存
        
        Args:
            subtitle_gen: SubtitleGeneration モデル
        """
        metadata = {
            "subject": self.subject,
            "phase": self.get_phase_number(),
            "phase_name": self.get_phase_name(),
            "generated_at": subtitle_gen.generated_at.isoformat(),
            "subtitle_count": len(subtitle_gen.subtitles),
            "srt_path": subtitle_gen.srt_path,
            "total_duration": max([s.end_time for s in subtitle_gen.subtitles]) if subtitle_gen.subtitles else 0,
            "config_used": {
                "max_lines": self.phase_config.get("max_lines", 2),
                "max_chars_per_line": self.phase_config.get("max_chars_per_line", 20),
                "min_display_duration": self.phase_config.get("timing", {}).get("min_display_duration", 4.0),
                "max_display_duration": self.phase_config.get("timing", {}).get("max_display_duration", 6.0),
                "use_mecab": self.phase_config.get("morphological_analysis", {}).get("use_mecab", False)
            }
        }
        
        self.save_metadata(metadata, "metadata.json")
        self.logger.info("Generation metadata saved")


# ========================================
# スタンドアロン実行用
# ========================================

def main():
    """テスト実行"""
    from src.utils.logger import setup_logger
    
    # 設定とロガーを初期化
    config = ConfigManager()
    logger = setup_logger(
        name="phase_06_test",
        log_dir=config.get_path("logs_dir"),
        level="DEBUG"
    )
    
    # Phase 6を実行
    subject = "織田信長"
    
    phase = Phase06Subtitles(
        subject=subject,
        config=config,
        logger=logger
    )
    
    # 実行
    execution = phase.run(skip_if_exists=False)
    
    # 結果表示
    print(f"\n{'='*60}")
    print(f"Phase 6 Execution Result")
    print(f"{'='*60}")
    print(f"Status: {execution.status}")
    print(f"Duration: {execution.duration_seconds:.2f}s")
    
    if execution.status.value == "completed":
        print(f"\nOutput files:")
        for path in execution.output_paths:
            print(f"  - {path}")
        
        # 字幕を読み込んで表示
        srt_path = Path(execution.output_paths[0])
        if srt_path.exists():
            print(f"\nFirst 3 subtitles from SRT:")
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                entries = content.split('\n\n')[:3]
                for entry in entries:
                    print(f"\n---")
                    print(entry)
    else:
        print(f"\nError: {execution.error_message}")


if __name__ == "__main__":
    main()
