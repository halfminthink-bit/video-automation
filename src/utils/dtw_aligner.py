"""
DTWベースの高精度アライメント

Dynamic Time Warpingを使用して、Whisperの認識結果と元テキストを
最適にアライメントする。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json

try:
    from fastdtw import fastdtw
    from scipy.spatial.distance import euclidean
    DTW_AVAILABLE = True
except ImportError:
    DTW_AVAILABLE = False
    fastdtw = None

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False


class DTWAligner:
    """
    DTWを使用した高精度アライメント

    機能:
    - Whisperの認識結果と元テキストの最適マッピング
    - 文字レベルのタイミング情報生成
    - デバッグ用の詳細ログとビジュアライゼーション
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        debug_mode: bool = True,
        output_dir: Optional[Path] = None
    ):
        """
        初期化

        Args:
            logger: ロガー
            debug_mode: デバッグモード（詳細ログ + 可視化）
            output_dir: デバッグファイルの出力先
        """
        if not DTW_AVAILABLE:
            raise ImportError(
                "fastdtw is required for DTW alignment. "
                "Install with: pip install fastdtw scipy"
            )

        self.logger = logger or logging.getLogger(__name__)
        self.debug_mode = debug_mode
        self.output_dir = output_dir or Path("debug/dtw")

        if self.debug_mode:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"DTW debug mode enabled: {self.output_dir}")

    def align(
        self,
        original_text: str,
        recognized_text: str,
        word_timings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        DTWを使用してアライメント実行

        Args:
            original_text: 元のテキスト（正確な固有名詞を含む）
            recognized_text: Whisperの認識結果
            word_timings: Whisperから取得した単語タイミング情報

        Returns:
            元のテキストの各文字にマッピングされたタイミング情報
        """
        self.logger.info("=" * 60)
        self.logger.info("Starting DTW alignment")
        self.logger.info("=" * 60)

        # 1. テキスト正規化
        original_normalized, original_chars = self._normalize_text(original_text)
        recognized_normalized, recognized_chars = self._normalize_text(recognized_text)

        self.logger.info(f"Original text: {original_text}")
        self.logger.info(f"Original normalized: {original_normalized}")
        self.logger.info(f"Recognized text: {recognized_text}")
        self.logger.info(f"Recognized normalized: {recognized_normalized}")

        # 2. Whisperの単語タイミングから文字レベルのタイミングマップを作成
        recognized_char_timings = self._create_char_timing_map(
            word_timings,
            recognized_text
        )

        self.logger.info(
            f"Created timing map: {len(recognized_char_timings)} characters "
            f"from {len(word_timings)} words"
        )

        # 3. 特徴ベクトルの作成
        original_features = self._create_features(original_normalized)
        recognized_features = self._create_features(recognized_normalized)

        self.logger.info(
            f"Feature vectors: original={len(original_features)}, "
            f"recognized={len(recognized_features)}"
        )

        # 4. DTWでアライメント実行
        distance, path = self._run_dtw(original_features, recognized_features)

        self.logger.info(f"DTW distance: {distance:.2f}")
        self.logger.info(f"DTW path length: {len(path)}")

        # 5. パスの検証
        self._validate_path(path, len(original_normalized), len(recognized_normalized))

        # 6. パスに基づいてタイミングを割り当て
        aligned_timings = self._assign_timings(
            original_text,
            original_normalized,
            recognized_char_timings,
            path
        )

        self.logger.info(
            f"✓ DTW alignment complete: {len(aligned_timings)} characters mapped"
        )

        # 7. デバッグ出力
        if self.debug_mode:
            self._debug_output(
                original_text,
                original_normalized,
                recognized_text,
                recognized_normalized,
                path,
                aligned_timings,
                distance
            )

        return aligned_timings

    def _normalize_text(self, text: str) -> Tuple[str, List[int]]:
        """
        テキストを正規化し、元の文字位置を保持

        Returns:
            (正規化テキスト, 元の文字位置リスト)
        """
        import re

        # 全角英数字を半角に
        text_normalized = text.translate(str.maketrans(
            '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        ))

        # 空白、句読点、記号を除去しつつ、元の位置を記録
        normalized = []
        char_positions = []

        for i, char in enumerate(text_normalized):
            if not re.match(r'[\s、。，．！？!?「」『』【】（）()〈〉《》\n]', char):
                normalized.append(char)
                char_positions.append(i)

        return ''.join(normalized), char_positions

    def _create_char_timing_map(
        self,
        word_timings: List[Dict[str, Any]],
        recognized_text: str
    ) -> List[Dict[str, Any]]:
        """
        単語レベルのタイミングから文字レベルのタイミングマップを作成

        Args:
            word_timings: 単語レベルのタイミング情報
            recognized_text: 認識されたテキスト

        Returns:
            文字レベルのタイミング情報リスト
        """
        char_timings = []

        self.logger.debug("Creating character timing map:")

        for word_info in word_timings:
            word = word_info.get("word", "").strip()
            if not word:
                continue

            # 単語を正規化
            word_normalized = word.translate(str.maketrans(
                '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
                '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            ))
            import re
            word_normalized = re.sub(r'[\s、。，．！？!?「」『』【】（）()〈〉《》]', '', word_normalized)

            if not word_normalized:
                continue

            # 単語の時間を文字数で分割
            word_duration = word_info["end"] - word_info["start"]
            char_duration = word_duration / len(word_normalized)

            self.logger.debug(
                f"  Word: '{word}' ({word_info['start']:.2f}-{word_info['end']:.2f}s) "
                f"→ {len(word_normalized)} chars"
            )

            for i, char in enumerate(word_normalized):
                char_start = word_info["start"] + (i * char_duration)
                char_end = char_start + char_duration

                char_timings.append({
                    "char": char,
                    "start": char_start,
                    "end": char_end,
                    "probability": word_info.get("probability", 1.0)
                })

        return char_timings

    def _create_features(self, text: str) -> List[List[float]]:
        """
        テキストから特徴ベクトルを作成

        文字を数値ベクトルに変換してDTWで比較できるようにする

        Args:
            text: 正規化済みテキスト

        Returns:
            特徴ベクトルのリスト
        """
        features = []

        for char in text:
            # 文字を数値ベクトルに変換
            # Unicode code pointを使用
            code_point = ord(char)

            # 複数の特徴を持つベクトルに変換
            # (より高度な実装では、文字の種類や位置情報も含める)
            feature = [
                float(code_point),           # 文字コード
                float(code_point % 256),     # 下位8ビット
                float(code_point // 256),    # 上位ビット
            ]
            features.append(feature)

        return features

    def _run_dtw(
        self,
        original_features: List[List[float]],
        recognized_features: List[List[float]]
    ) -> Tuple[float, List[Tuple[int, int]]]:
        """
        DTWアルゴリズムを実行

        Args:
            original_features: 元テキストの特徴ベクトル
            recognized_features: 認識テキストの特徴ベクトル

        Returns:
            (距離, アライメントパス)
        """
        self.logger.info("Running DTW algorithm...")

        # FastDTWで計算（O(N)の高速版）
        distance, path = fastdtw(
            recognized_features,  # 認識結果
            original_features,    # 元テキスト
            dist=euclidean
        )

        # パスを反転（recognized → original の順に）
        # FastDTWは (recognized_idx, original_idx) のタプルを返す

        self.logger.info(f"DTW computation complete")
        self.logger.debug(f"  Distance: {distance:.2f}")
        self.logger.debug(f"  Path: {path[:5]}...{path[-5:]}")

        return distance, path

    def _validate_path(
        self,
        path: List[Tuple[int, int]],
        original_length: int,
        recognized_length: int
    ):
        """
        DTWパスを検証

        Args:
            path: DTWのアライメントパス
            original_length: 元テキストの長さ
            recognized_length: 認識テキストの長さ
        """
        self.logger.info("Validating DTW path...")

        # 1. パスの開始と終了を確認
        if not path:
            raise ValueError("DTW path is empty")

        start_rec, start_orig = path[0]
        end_rec, end_orig = path[-1]

        self.logger.debug(f"  Path start: recognized[{start_rec}] → original[{start_orig}]")
        self.logger.debug(f"  Path end: recognized[{end_rec}] → original[{end_orig}]")

        # 2. 単調性を確認（時間が逆行していないか）
        for i in range(1, len(path)):
            prev_rec, prev_orig = path[i-1]
            curr_rec, curr_orig = path[i]

            if curr_rec < prev_rec or curr_orig < prev_orig:
                self.logger.warning(
                    f"Non-monotonic path detected at step {i}: "
                    f"({prev_rec},{prev_orig}) → ({curr_rec},{curr_orig})"
                )

        # 3. カバレッジを確認
        recognized_covered = set(rec_idx for rec_idx, _ in path)
        original_covered = set(orig_idx for _, orig_idx in path)

        rec_coverage = len(recognized_covered) / recognized_length * 100
        orig_coverage = len(original_covered) / original_length * 100

        self.logger.info(
            f"  Coverage: recognized={rec_coverage:.1f}%, original={orig_coverage:.1f}%"
        )

        if rec_coverage < 80 or orig_coverage < 80:
            self.logger.warning("Low coverage detected - alignment may be inaccurate")

    def _assign_timings(
        self,
        original_text: str,
        original_normalized: str,
        recognized_char_timings: List[Dict[str, Any]],
        path: List[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """
        DTWパスに基づいてタイミングを割り当て

        Args:
            original_text: 元のテキスト（句読点含む）
            original_normalized: 正規化済み元テキスト
            recognized_char_timings: 認識結果の文字タイミング
            path: DTWのアライメントパス

        Returns:
            元テキストの各文字にマッピングされたタイミング情報
        """
        self.logger.info("Assigning timings based on DTW path...")

        # パスから original_idx → recognized_idx のマッピングを作成
        path_map = {}
        for rec_idx, orig_idx in path:
            if orig_idx not in path_map:
                path_map[orig_idx] = []
            path_map[orig_idx].append(rec_idx)

        self.logger.debug(f"  Path map created: {len(path_map)} original chars mapped")

        # 各正規化文字にタイミングを割り当て
        normalized_timings = []

        for orig_idx in range(len(original_normalized)):
            if orig_idx in path_map:
                # マッピングされている場合
                rec_indices = path_map[orig_idx]

                # 複数の認識文字にマッピングされている場合は平均を取る
                timings = [
                    recognized_char_timings[rec_idx]
                    for rec_idx in rec_indices
                    if rec_idx < len(recognized_char_timings)
                ]

                if timings:
                    # 開始時刻は最小、終了時刻は最大
                    start = min(t["start"] for t in timings)
                    end = max(t["end"] for t in timings)
                    prob = sum(t["probability"] for t in timings) / len(timings)

                    normalized_timings.append({
                        "char": original_normalized[orig_idx],
                        "start": start,
                        "end": end,
                        "probability": prob
                    })
                else:
                    # タイミング情報がない場合は補間
                    self.logger.warning(f"No timing for original[{orig_idx}], interpolating")
                    normalized_timings.append(self._interpolate_timing(normalized_timings))
            else:
                # マッピングされていない場合は補間
                self.logger.debug(f"Original[{orig_idx}] not in path, interpolating")
                normalized_timings.append(self._interpolate_timing(normalized_timings))

        # 元のテキスト（句読点含む）にタイミングを割り当て
        aligned_timings = []
        normalized_idx = 0

        for char in original_text:
            import re
            if re.match(r'[\s、。，．！？!?「」『』【】（）()〈〉《》\n]', char):
                # 句読点・空白の場合：直前の文字の終了時刻を使用
                if aligned_timings:
                    last = aligned_timings[-1]
                    aligned_timings.append({
                        "word": char,
                        "start": last["end"],
                        "end": last["end"],
                        "probability": 1.0
                    })
                else:
                    aligned_timings.append({
                        "word": char,
                        "start": 0.0,
                        "end": 0.0,
                        "probability": 1.0
                    })
            else:
                # 通常の文字
                if normalized_idx < len(normalized_timings):
                    timing = normalized_timings[normalized_idx]
                    aligned_timings.append({
                        "word": char,
                        "start": timing["start"],
                        "end": timing["end"],
                        "probability": timing["probability"]
                    })
                    normalized_idx += 1
                else:
                    # 範囲外（通常は発生しない）
                    self.logger.warning(f"Normalized index out of range: {normalized_idx}")
                    if aligned_timings:
                        last = aligned_timings[-1]
                        aligned_timings.append({
                            "word": char,
                            "start": last["end"],
                            "end": last["end"] + 0.1,
                            "probability": 0.5
                        })

        return aligned_timings

    def _interpolate_timing(
        self,
        previous_timings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        前後のタイミングから補間

        Args:
            previous_timings: これまでのタイミング情報

        Returns:
            補間されたタイミング情報
        """
        if not previous_timings:
            return {
                "char": "",
                "start": 0.0,
                "end": 0.1,
                "probability": 0.5
            }

        last = previous_timings[-1]
        return {
            "char": "",
            "start": last["end"],
            "end": last["end"] + 0.1,
            "probability": 0.5
        }

    def _debug_output(
        self,
        original_text: str,
        original_normalized: str,
        recognized_text: str,
        recognized_normalized: str,
        path: List[Tuple[int, int]],
        aligned_timings: List[Dict[str, Any]],
        distance: float
    ):
        """
        デバッグ情報を出力

        Args:
            original_text: 元のテキスト
            original_normalized: 正規化済み元テキスト
            recognized_text: 認識テキスト
            recognized_normalized: 正規化済み認識テキスト
            path: DTWパス
            aligned_timings: アライメント結果
            distance: DTW距離
        """
        self.logger.info("Generating debug output...")

        # 1. テキスト比較をファイルに出力
        debug_file = self.output_dir / "alignment_debug.txt"

        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("DTW Alignment Debug Output\n")
            f.write("=" * 80 + "\n\n")

            f.write("Original Text:\n")
            f.write(f"  Raw: {original_text}\n")
            f.write(f"  Normalized: {original_normalized}\n")
            f.write(f"  Length: {len(original_text)} chars ({len(original_normalized)} normalized)\n\n")

            f.write("Recognized Text:\n")
            f.write(f"  Raw: {recognized_text}\n")
            f.write(f"  Normalized: {recognized_normalized}\n")
            f.write(f"  Length: {len(recognized_text)} chars ({len(recognized_normalized)} normalized)\n\n")

            f.write(f"DTW Distance: {distance:.2f}\n\n")

            f.write("Alignment Path (first 20 and last 20):\n")
            for i, (rec_idx, orig_idx) in enumerate(path[:20] + path[-20:]):
                rec_char = recognized_normalized[rec_idx] if rec_idx < len(recognized_normalized) else "?"
                orig_char = original_normalized[orig_idx] if orig_idx < len(original_normalized) else "?"
                f.write(f"  {i}: recognized[{rec_idx}]='{rec_char}' → original[{orig_idx}]='{orig_char}'\n")

            if len(path) > 40:
                f.write(f"  ... ({len(path) - 40} more steps)\n")

            f.write("\nAligned Timings (first 20 and last 20):\n")
            for i, timing in enumerate(aligned_timings[:20] + aligned_timings[-20:]):
                f.write(
                    f"  {i}: '{timing['word']}' "
                    f"{timing['start']:.3f}-{timing['end']:.3f}s "
                    f"(prob={timing['probability']:.2f})\n"
                )

            if len(aligned_timings) > 40:
                f.write(f"  ... ({len(aligned_timings) - 40} more characters)\n")

        self.logger.info(f"  Text debug output: {debug_file}")

        # 2. JSONで詳細データを出力
        json_file = self.output_dir / "alignment_debug.json"

        debug_data = {
            "original_text": original_text,
            "original_normalized": original_normalized,
            "recognized_text": recognized_text,
            "recognized_normalized": recognized_normalized,
            "dtw_distance": distance,
            "path_length": len(path),
            "path": path,
            "aligned_timings": aligned_timings
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"  JSON debug output: {json_file}")

        # 3. ビジュアライゼーション（オプション）
        if VISUALIZATION_AVAILABLE:
            self._visualize_alignment(
                original_normalized,
                recognized_normalized,
                path
            )

    def _visualize_alignment(
        self,
        original_normalized: str,
        recognized_normalized: str,
        path: List[Tuple[int, int]]
    ):
        """
        アライメントを可視化

        Args:
            original_normalized: 正規化済み元テキスト
            recognized_normalized: 正規化済み認識テキスト
            path: DTWパス
        """
        try:
            import numpy as np

            # コストマトリックスを作成（ヒートマップ用）
            cost_matrix = np.zeros((len(recognized_normalized), len(original_normalized)))

            for rec_idx, orig_idx in path:
                cost_matrix[rec_idx, orig_idx] = 1

            # プロット
            plt.figure(figsize=(12, 10))
            sns.heatmap(
                cost_matrix,
                cmap='Blues',
                xticklabels=list(original_normalized),
                yticklabels=list(recognized_normalized),
                cbar_kws={'label': 'Alignment'}
            )

            plt.xlabel('Original Text (normalized)')
            plt.ylabel('Recognized Text (normalized)')
            plt.title('DTW Alignment Path')

            # パスを赤線で描画
            path_x = [orig_idx for _, orig_idx in path]
            path_y = [rec_idx for rec_idx, _ in path]
            plt.plot(path_x, path_y, 'r-', linewidth=2, label='DTW Path')
            plt.legend()

            # 保存
            viz_file = self.output_dir / "alignment_visualization.png"
            plt.savefig(viz_file, dpi=150, bbox_inches='tight')
            plt.close()

            self.logger.info(f"  Visualization saved: {viz_file}")

        except Exception as e:
            self.logger.warning(f"Failed to create visualization: {e}")


def create_dtw_aligner(
    logger: Optional[logging.Logger] = None,
    debug_mode: bool = True,
    output_dir: Optional[Path] = None
) -> Optional[DTWAligner]:
    """
    DTWAlignerを作成

    Args:
        logger: ロガー
        debug_mode: デバッグモード
        output_dir: デバッグ出力先

    Returns:
        DTWAligner（利用不可の場合はNone）
    """
    if not DTW_AVAILABLE:
        if logger:
            logger.warning(
                "fastdtw not available. Install with: pip install fastdtw scipy"
            )
        return None

    try:
        return DTWAligner(
            logger=logger,
            debug_mode=debug_mode,
            output_dir=output_dir
        )
    except Exception as e:
        if logger:
            logger.error(f"Failed to create DTW aligner: {e}")
        return None
