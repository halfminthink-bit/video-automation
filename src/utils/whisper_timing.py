"""
Whisperを使用して音声から単語レベルのタイミング情報を取得するユーティリティ
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import tempfile

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None

try:
    import stable_whisper
    STABLE_WHISPER_AVAILABLE = True
except ImportError:
    STABLE_WHISPER_AVAILABLE = False
    stable_whisper = None


class WhisperTimingExtractor:
    """Whisperを使用して音声から単語レベルのタイミング情報を取得"""
    
    def __init__(
        self,
        model_name: str = "base",
        logger: Optional[logging.Logger] = None,
        language: str = "ja",
        use_stable_ts: bool = True,
        suppress_silence: bool = True,
        vad: bool = True,
        vad_threshold: float = 0.35
    ):
        """
        初期化

        Args:
            model_name: Whisperモデル名（tiny, base, small, medium, large）
            logger: ロガー
            language: 言語コード（"ja" = 日本語）
            use_stable_ts: stable-tsを使用するか（無音抑制、ギャップ調整が有効）
            suppress_silence: 無音区間を抑制するか（stable-ts使用時のみ）
            vad: Voice Activity Detectionを使用するか（stable-ts使用時のみ）
            vad_threshold: VADの閾値（0-1、低いほど厳格）
        """
        if not WHISPER_AVAILABLE:
            raise ImportError(
                "whisper package is required. "
                "Install with: pip install openai-whisper"
            )

        self.logger = logger or logging.getLogger(__name__)
        self.language = language
        self.use_stable_ts = use_stable_ts and STABLE_WHISPER_AVAILABLE
        self.suppress_silence = suppress_silence
        self.vad = vad
        self.vad_threshold = vad_threshold

        # stable-tsが利用可能だが、インストールされていない場合は警告
        if use_stable_ts and not STABLE_WHISPER_AVAILABLE:
            self.logger.warning(
                "stable-ts is not available. Falling back to standard Whisper. "
                "Install with: pip install stable-ts"
            )
            self.use_stable_ts = False

        model_type = "stable-ts" if self.use_stable_ts else "Whisper"
        self.logger.info(f"Loading {model_type} model: {model_name}")

        try:
            # CPUで実行する場合はFP32を使用（FP16はGPUのみ対応）
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"

            if self.use_stable_ts:
                # stable-tsモデルをロード
                self.model = stable_whisper.load_model(model_name, device=device)
                self.logger.info(
                    f"stable-ts model loaded successfully on {device} "
                    f"(suppress_silence={suppress_silence}, vad={vad})"
                )
            else:
                # 標準Whisperモデルをロード
                self.model = whisper.load_model(model_name, device=device)
                self.logger.info(f"Whisper model loaded successfully on {device}")
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            raise
    
    def extract_word_timings(
        self,
        audio_path: Path,
        text: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        音声から単語レベルのタイミング情報を取得
        
        Args:
            audio_path: 音声ファイルのパス
            text: オプション：元のテキスト（精度向上のため）
            
        Returns:
            単語タイミング情報のリスト:
            [
                {
                    "word": "織田",
                    "start": 0.5,
                    "end": 0.8,
                    "probability": 0.95
                },
                ...
            ]
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        self.logger.info(f"Extracting word timings from: {audio_path}")
        
        try:
            # Whisperで音声認識（word_timestamps=Trueで単語レベルのタイミングを取得）
            # CPUではFP16が使えないため、fp16=Falseを明示的に指定
            import torch
            fp16_enabled = torch.cuda.is_available()

            # 共通パラメータ
            transcribe_params = {
                "language": self.language,
                "word_timestamps": True,
                # initial_promptは使用しない（全文をスキップされるため）
                # Whisperの仕様: initial_promptは「直前に話された内容」として機能し、
                # 渡されたテキストを「もう話し終わった」と判断してスキップする
                "fp16": fp16_enabled,
                # 🔥 累積エラー防止（最重要）
                "condition_on_previous_text": False,
                "no_speech_threshold": 0.3,
                "logprob_threshold": -1.0,
                "compression_ratio_threshold": 2.4,
                "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                "beam_size": 5,
                "patience": 1.0,
                "length_penalty": 1.0,
                "suppress_tokens": "-1",
                "task": "transcribe"
            }

            # stable-ts使用時は追加パラメータを設定
            if self.use_stable_ts:
                transcribe_params.update({
                    "suppress_silence": self.suppress_silence,
                    "vad": self.vad,
                    "vad_threshold": self.vad_threshold
                })
                self.logger.debug(
                    f"Using stable-ts with suppress_silence={self.suppress_silence}, "
                    f"vad={self.vad}, vad_threshold={self.vad_threshold}"
                )

            result = self.model.transcribe(str(audio_path), **transcribe_params)

            # 🔥 stable-ts使用時：ギャップ調整で発話境界を最適化
            if self.use_stable_ts:
                result = result.adjust_gaps(
                    duration_threshold=0.75,
                    one_section=True  # TTS音声推奨
                )
                self.logger.debug("Applied gap adjustment to transcription result")

            # デバッグ: Whisperの認識結果を確認
            if self.use_stable_ts:
                # stable-ts: 属性アクセス
                recognized_text = result.text
                segments = result.segments
                self.logger.info(f"Whisper recognized text: {recognized_text}")
                self.logger.info(f"Number of segments: {len(segments)}")
                for i, seg in enumerate(segments):
                    segment_text = seg.text
                    words = seg.words if hasattr(seg, 'words') else []
                    # stable-tsにはno_speech_probがない
                    self.logger.info(
                        f"  Segment {i}: {segment_text} "
                        f"({len(words)} words)"
                    )
            else:
                # 通常のWhisper: 辞書アクセス
                recognized_text = result.get('text', '')
                segments = result.get("segments", [])
                self.logger.info(f"Whisper recognized text: {recognized_text}")
                self.logger.info(f"Number of segments: {len(segments)}")
                for i, seg in enumerate(segments):
                    segment_text = seg.get("text", "")
                    words = seg.get("words", []) or []
                    no_speech_prob = seg.get("no_speech_prob", 0)
                    self.logger.info(
                        f"  Segment {i}: {segment_text} "
                        f"({len(words)} words, no_speech_prob={no_speech_prob:.3f})"
                    )
            
            # 単語レベルのタイミング情報を抽出
            word_timings = []
            if self.use_stable_ts:
                # stable-ts: 属性アクセス
                for segment in result.segments:
                    if hasattr(segment, 'words') and segment.words:
                        for word in segment.words:
                            word_timings.append({
                                "word": word.word.strip(),
                                "start": word.start,
                                "end": word.end,
                                "probability": getattr(word, 'probability', 1.0)
                            })
                
                # 最終時刻の取得
                last_duration = result.segments[-1].end if result.segments else 0
                self.logger.info(
                    f"Extracted {len(word_timings)} word timings from stable-ts "
                    f"(duration: {last_duration:.1f}s)"
                )
            else:
                # 通常のWhisper: 辞書アクセス
                for segment in result.get("segments", []):
                    for word_info in segment.get("words", []):
                        word_timings.append({
                            "word": word_info.get("word", "").strip(),
                            "start": word_info.get("start", 0.0),
                            "end": word_info.get("end", 0.0),
                            "probability": word_info.get("probability", 1.0)
                        })
                
                last_duration = result.get('segments', [{}])[-1].get('end', 0) if result.get('segments') else 0
                self.logger.info(
                    f"Extracted {len(word_timings)} word timings from Whisper "
                    f"(duration: {last_duration:.1f}s)"
                )

            # 🔥 新機能：元のテキストが提供されている場合、アライメントを実行
            if text:
                self.logger.info("Aligning timings with original text...")
                
                # 認識テキストの取得
                if self.use_stable_ts:
                    recognized_text = result.text
                else:
                    recognized_text = result.get('text', '')
                
                aligned_timings = align_text_with_whisper_timings(
                    original_text=text,
                    recognized_text=recognized_text,
                    word_timings=word_timings,
                    logger=self.logger
                )
                self.logger.info(
                    f"✓ Alignment complete: {len(aligned_timings)} characters mapped"
                )
                return aligned_timings
            else:
                # 元のテキストがない場合は、認識結果をそのまま返す
                return word_timings
            
        except Exception as e:
            self.logger.error(f"Failed to extract word timings: {e}", exc_info=True)
            raise
    
    def extract_sentence_timings(
        self,
        audio_path: Path,
        sentences: List[str],
        word_timings: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        文レベルのタイミング情報を取得
        
        単語タイミング情報から、各文の開始・終了時間を計算する
        
        Args:
            audio_path: 音声ファイルのパス
            sentences: 文のリスト
            word_timings: 事前に取得した単語タイミング情報（Noneの場合は取得）
            
        Returns:
            文タイミング情報のリスト:
            [
                {
                    "sentence": "織田信長は...",
                    "start": 0.5,
                    "end": 3.2
                },
                ...
            ]
        """
        if word_timings is None:
            # 単語タイミング情報を取得
            word_timings = self.extract_word_timings(audio_path)
        
        if not word_timings:
            self.logger.warning("No word timings available, returning empty list")
            return []
        
        # 各文のタイミングを計算
        sentence_timings = []
        current_word_idx = 0
        total_words = len(word_timings)
        
        for sentence_idx, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            
            # 文の文字数を計算（日本語の場合、文字数で大体の長さを推定）
            sentence_length = len(sentence)
            
            # この文に対応する単語数を推定（簡易版：文字数の比率）
            # 実際の音声認識結果と台本の文字数が異なる可能性があるため、
            # 累積文字数から推定
            total_sentence_chars = sum(len(s) for s in sentences)
            if total_sentence_chars > 0:
                char_ratio = sentence_length / total_sentence_chars
                estimated_words = int(total_words * char_ratio)
            else:
                estimated_words = max(1, sentence_length // 2)  # 1文字 = 0.5単語（推定）
            
            # 開始位置を決定
            sentence_start = None
            sentence_end = None
            
            # 現在の位置から開始して、単語タイミングを取得
            words_for_sentence = min(estimated_words, total_words - current_word_idx)
            
            if words_for_sentence > 0 and current_word_idx < total_words:
                # この文に対応する単語タイミングを取得
                sentence_start = word_timings[current_word_idx]["start"]
                sentence_end = word_timings[min(
                    current_word_idx + words_for_sentence - 1,
                    total_words - 1
                )]["end"]
                
                # 次の文の開始位置を更新
                current_word_idx += words_for_sentence
            else:
                # タイミングが見つからない場合、前の文の終了時間を使用
                if sentence_timings:
                    last_end = sentence_timings[-1]["end"]
                    # 推定時間を計算（文字数から）
                    estimated_duration = len(sentence) * 0.15  # 1文字 = 0.15秒（推定）
                    sentence_start = last_end
                    sentence_end = last_end + estimated_duration
                else:
                    # 最初の文でタイミングが見つからない場合
                    sentence_start = 0.0
                    estimated_duration = len(sentence) * 0.15
                    sentence_end = estimated_duration
            
            if sentence_start is not None and sentence_end is not None:
                sentence_timings.append({
                    "sentence": sentence,
                    "start": sentence_start,
                    "end": sentence_end,
                    "duration": sentence_end - sentence_start
                })
        
        self.logger.info(
            f"Extracted {len(sentence_timings)} sentence timings "
            f"from {len(word_timings)} words"
        )
        
        return sentence_timings
    
    def _split_sentence_to_words(self, sentence: str) -> List[str]:
        """
        文を単語に分割（簡易版）
        
        より正確には形態素解析を使用すべきだが、
        ここでは簡易的に空白と句読点で分割
        
        Args:
            sentence: 入力文
            
        Returns:
            単語のリスト
        """
        # 句読点を除去して空白で分割
        import re
        # 句読点を空白に置換
        text = re.sub(r'[。、，！？]', ' ', sentence)
        # 連続する空白を1つに
        text = re.sub(r'\s+', ' ', text)
        words = [w.strip() for w in text.split() if w.strip()]
        return words


def align_text_with_whisper_timings(
    original_text: str,
    recognized_text: str,
    word_timings: List[Dict[str, Any]],
    logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    元のテキストとWhisperの認識結果をアライメント

    DTWが利用可能な場合は高精度アライメント、
    そうでない場合はフォールバック（文字数比率）

    Args:
        original_text: 元のnarration text（正確な固有名詞を含む）
        recognized_text: Whisperが認識したテキスト（誤認識あり）
        word_timings: Whisperから取得した単語タイミング情報
        logger: ロガー

    Returns:
        元のテキストの文字にマッピングされたタイミング情報
    """
    if logger:
        logger.info(
            f"Aligning texts: original={len(original_text)} chars, "
            f"recognized={len(recognized_text)} chars"
        )

    # 🔥 DTWが利用可能ならDTWを使用
    try:
        from src.utils.dtw_aligner import create_dtw_aligner

        dtw_aligner = create_dtw_aligner(
            logger=logger,
            debug_mode=True,  # 最初はデバッグモード有効
            output_dir=None   # デフォルトのdebug/dtwを使用
        )

        if dtw_aligner:
            if logger:
                logger.info("Using DTW for high-precision alignment")

            aligned_timings = dtw_aligner.align(
                original_text=original_text,
                recognized_text=recognized_text,
                word_timings=word_timings
            )

            if logger:
                logger.info("✓ DTW alignment successful")
            return aligned_timings
        else:
            if logger:
                logger.warning("DTW not available, falling back to ratio-based alignment")

    except ImportError as e:
        if logger:
            logger.warning(f"DTW import failed: {e}, using fallback alignment")
    except Exception as e:
        if logger:
            logger.error(f"DTW alignment failed: {e}, using fallback alignment")

    # 🔥 フォールバック：従来の文字数比率方式
    if logger:
        logger.info("Using ratio-based alignment (fallback)")

    # 空白と句読点を除去して比較用テキストを作成
    import re
    def normalize_text(text: str) -> str:
        """比較用にテキストを正規化"""
        # 全角英数字を半角に
        text = text.translate(str.maketrans(
            '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        ))
        # 空白、句読点、記号を除去
        text = re.sub(r'[\s、。，．！？!?「」『』【】（）()〈〉《》]', '', text)
        return text

    original_normalized = normalize_text(original_text)
    recognized_normalized = normalize_text(recognized_text)

    # Whisperの認識結果から文字とタイミングのマッピングを作成
    recognized_chars = []
    for word_info in word_timings:
        word = word_info.get("word", "").strip()
        word_normalized = normalize_text(word)
        for char in word_normalized:
            recognized_chars.append({
                "char": char,
                "start": word_info.get("start", 0.0),
                "end": word_info.get("end", 0.0),
                "probability": word_info.get("probability", 1.0)
            })

    if logger:
        logger.info(
            f"Recognized chars: {len(recognized_chars)}, "
            f"normalized: '{recognized_normalized[:50]}...'"
        )

    # 簡易的なアライメント：文字数比率でマッピング
    # より高度な実装では編集距離（Levenshtein距離）を使用可能
    aligned_timings = []

    if len(recognized_chars) == 0:
        # 認識結果が空の場合、均等にタイミングを割り当て
        if logger:
            logger.warning("No recognized characters, using uniform timing")
        duration_per_char = 0.15  # 1文字あたり0.15秒と仮定
        for i, char in enumerate(original_text):
            # 句読点も含む全ての文字を処理
            aligned_timings.append({
                "word": char,
                "start": i * duration_per_char,
                "end": (i + 1) * duration_per_char,
                "probability": 0.5
            })
    else:
        # 文字数比率でマッピング
        # 句読点を除外した文字のみでインデックスを計算
        original_chars = [c for c in original_text if normalize_text(c)]
        ratio = len(recognized_chars) / max(len(original_chars), 1)

        if logger:
            logger.info(
                f"Alignment ratio: {ratio:.2f} "
                f"({len(recognized_chars)} recognized / {len(original_chars)} original)"
            )

        # 句読点を除外した文字のインデックスカウンター
        normalized_char_count = 0
        last_timing = None

        for i, char in enumerate(original_text):
            if not normalize_text(char):
                # 句読点・空白の場合
                # 直前の文字のタイミングを使用（音声には含まれないが表示用に必要）
                if last_timing:
                    # 直前の文字の終了時刻をそのまま使用（瞬間表示）
                    aligned_timings.append({
                        "word": char,
                        "start": last_timing["end"],
                        "end": last_timing["end"],
                        "probability": last_timing.get("probability", 0.5)
                    })
                else:
                    # 最初の文字が句読点の場合（稀）
                    aligned_timings.append({
                        "word": char,
                        "start": 0.0,
                        "end": 0.0,
                        "probability": 0.5
                    })
                continue

            # 通常の文字の場合
            # 対応する認識文字のインデックスを計算
            recognized_idx = int(normalized_char_count * ratio)
            recognized_idx = min(recognized_idx, len(recognized_chars) - 1)

            if recognized_idx < len(recognized_chars):
                timing = recognized_chars[recognized_idx]
                aligned_timings.append({
                    "word": char,
                    "start": timing["start"],
                    "end": timing["end"],
                    "probability": timing["probability"]
                })
                last_timing = timing
            else:
                # 範囲外の場合、最後のタイミングを使用
                last_timing = recognized_chars[-1]
                aligned_timings.append({
                    "word": char,
                    "start": last_timing["end"],
                    "end": last_timing["end"] + 0.15,
                    "probability": 0.5
                })

            normalized_char_count += 1

    if logger:
        logger.info(
            f"✓ Aligned {len(aligned_timings)} characters from original text "
            f"to Whisper timings"
        )

    return aligned_timings


def create_whisper_extractor(
    model_name: str = "base",
    logger: Optional[logging.Logger] = None,
    language: str = "ja",
    use_stable_ts: bool = True,
    suppress_silence: bool = True,
    vad: bool = True,
    vad_threshold: float = 0.35
) -> Optional[WhisperTimingExtractor]:
    """
    WhisperTimingExtractorを作成

    Args:
        model_name: Whisperモデル名
        logger: ロガー
        language: 言語コード
        use_stable_ts: stable-tsを使用するか（無音抑制、ギャップ調整が有効）
        suppress_silence: 無音区間を抑制するか（stable-ts使用時のみ）
        vad: Voice Activity Detectionを使用するか（stable-ts使用時のみ）
        vad_threshold: VADの閾値（0-1、低いほど厳格）

    Returns:
        WhisperTimingExtractor（利用不可の場合はNone）
    """
    if not WHISPER_AVAILABLE:
        if logger:
            logger.warning(
                "Whisper not available. Install with: pip install openai-whisper"
            )
        return None

    try:
        return WhisperTimingExtractor(
            model_name=model_name,
            logger=logger,
            language=language,
            use_stable_ts=use_stable_ts,
            suppress_silence=suppress_silence,
            vad=vad,
            vad_threshold=vad_threshold
        )
    except Exception as e:
        if logger:
            logger.error(f"Failed to create Whisper extractor: {e}")
        return None

