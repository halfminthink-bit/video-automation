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


class WhisperTimingExtractor:
    """Whisperを使用して音声から単語レベルのタイミング情報を取得"""
    
    def __init__(
        self,
        model_name: str = "base",
        logger: Optional[logging.Logger] = None,
        language: str = "ja"
    ):
        """
        初期化
        
        Args:
            model_name: Whisperモデル名（tiny, base, small, medium, large）
            logger: ロガー
            language: 言語コード（"ja" = 日本語）
        """
        if not WHISPER_AVAILABLE:
            raise ImportError(
                "whisper package is required. "
                "Install with: pip install openai-whisper"
            )
        
        self.logger = logger or logging.getLogger(__name__)
        self.language = language
        
        self.logger.info(f"Loading Whisper model: {model_name}")
        try:
            # CPUで実行する場合はFP32を使用（FP16はGPUのみ対応）
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = whisper.load_model(model_name, device=device)
            self.logger.info(f"Whisper model loaded successfully on {device}")
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
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

            result = self.model.transcribe(
                str(audio_path),
                language=self.language,
                word_timestamps=True,
                initial_prompt=None,  # 前のテキストの影響を完全に排除
                fp16=fp16_enabled,  # CPUの場合はFP32を使用
                # 認識精度向上のための追加パラメータ
                condition_on_previous_text=False,  # 前のセグメントの影響を受けない
                no_speech_threshold=0.3,  # 音声の冒頭を見逃しにくくする（0.6→0.3）
                logprob_threshold=-1.0,  # 確率が低い結果も許容
                compression_ratio_threshold=2.4,  # 圧縮比の閾値を緩和
                temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],  # 複数の温度で試行（失敗時の自動リトライ）
                beam_size=5,  # ビームサーチのサイズ
                patience=1.0,  # 探索の粘り強さ
                length_penalty=1.0,  # 長い文を優先しない
                suppress_tokens="-1",  # トークン抑制を無効化
                task="transcribe"  # 翻訳ではなく文字起こし
            )

            # デバッグ: Whisperの認識結果を確認
            self.logger.info(f"Whisper recognized text: {result.get('text', '')}")
            segments = result.get("segments", [])
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
            for segment in result.get("segments", []):
                for word_info in segment.get("words", []):
                    word_timings.append({
                        "word": word_info.get("word", "").strip(),
                        "start": word_info.get("start", 0.0),
                        "end": word_info.get("end", 0.0),
                        "probability": word_info.get("probability", 1.0)
                    })
            
            self.logger.info(
                f"Extracted {len(word_timings)} word timings "
                f"(duration: {result.get('segments', [{}])[-1].get('end', 0):.1f}s)"
            )
            
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


def create_whisper_extractor(
    model_name: str = "base",
    logger: Optional[logging.Logger] = None,
    language: str = "ja"
) -> Optional[WhisperTimingExtractor]:
    """
    WhisperTimingExtractorを作成
    
    Args:
        model_name: Whisperモデル名
        logger: ロガー
        language: 言語コード
        
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
            language=language
        )
    except Exception as e:
        if logger:
            logger.error(f"Failed to create Whisper extractor: {e}")
        return None

