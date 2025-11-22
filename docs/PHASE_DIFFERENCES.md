# Phase 6/7 各バージョンの違い

## Phase 6: 字幕生成

### `phase_06_subtitles.py` (通常版)
- **基本機能**: 基本的な字幕生成
- **出力**: 
  - `subtitles.srt` (SRT形式)
  - `subtitle_timing.json` (タイミング情報)
- **特徴**:
  - 文字レベルタイミングから字幕を生成
  - 句読点削除、タイミング調整、ギャップ最適化
  - セクションタイトル対応（`audio_timing.json`の`title_timing`から読み込み）
- **使用場面**: 通常の字幕生成

### `phase_06_subtitles_v2.py` (V2版 - インパクト字幕対応)
- **基本機能**: インパクト字幕対応の字幕生成
- **出力**: 
  - `subtitles.srt` (SRT形式)
  - `subtitle_timing.json` (タイミング情報 + `impact_level`フィールド)
- **追加機能**:
  - **インパクトレベル判定**: `script.json`の`impact_sentences`から判定
    - `none`: 通常字幕
    - `normal`: 通常の強調（赤文字など）
    - `mega`: 特大インパクト
  - **セクションタイトル対応**: `audio_timing.json`の`title_timing`から読み込み、`section_title`として追加
  - **正規化マッチング**: 句点・改行・空白を除去して柔軟にマッチング
- **使用場面**: インパクト字幕を使用する場合（Phase 7 V2と組み合わせて使用）

---

## Phase 7: 動画統合

### `phase_07_composition.py` (FFmpeg版 - 標準)
- **技術**: FFmpegによる高速処理
- **処理時間**: 約1分（MoviePy版の約15分から大幅短縮）
- **入力素材**:
  - Phase 3の画像（静止画）
  - Phase 2の音声
  - Phase 6の字幕（SRT形式）
- **レイアウト**:
  - 解像度: 1920x1080
  - 上部864px: 画像表示
  - 下部216px: 黒バー + 字幕
- **字幕**: ASS形式、`cinecaption`フォント、60px
- **BGM**: 音量10%、フェードイン/アウト付き
- **特徴**:
  - セクションタイトル対応（`subtitle_timing.json`の`special_type: "section_title"`を検出）
  - 画像タイミング: `audio_timing.json`から正確な時間を取得して均等分割
- **使用場面**: 通常の動画生成（推奨）

### `phase_07_composition_legacy.py` (MoviePy版 - Legacy)
- **技術**: MoviePyによる処理
- **処理時間**: 約15分（FFmpeg版より遅い）
- **入力素材**:
  - **Phase 4の動画**（Phase 3の画像を動画化したもの）
  - Phase 2の音声
  - Phase 6の字幕
- **特徴**:
  - Phase 4で生成された動画クリップを使用
  - MoviePyの機能をフル活用
- **使用場面**: Phase 4の動画を使用したい場合（`--legacy`オプション）

### `phase_07_composition_legacy02.py` (MoviePy版 - Legacy02)
- **技術**: MoviePyによる処理
- **処理時間**: 約15分（FFmpeg版より遅い）
- **入力素材**:
  - **Phase 3の画像**（静止画を直接使用）
  - Phase 2の音声
  - Phase 6の字幕
- **特徴**:
  - Phase 4をスキップしてPhase 3の画像を直接使用
  - 処理時間短縮（Phase 4が不要）
- **使用場面**: Phase 4をスキップしてPhase 3の画像を直接使用したい場合（`--legacy02`オプション）

### `phase_07_composition_v2.py` (V2版 - 背景動画 + インパクト字幕)
- **技術**: FFmpegによる高速処理
- **処理時間**: 約1分（FFmpeg版と同等）
- **入力素材**:
  - Phase 3の画像（静止画）
  - **背景動画**（`assets/background_videos`から選択）
  - Phase 2の音声
  - Phase 6 V2の字幕（`impact_level`情報付き）
- **追加機能**:
  - **背景動画対応**: 
    - 背景動画ライブラリから自動選択
    - セクションごとに適切な背景動画を選択（opening/main/ending）
    - 背景動画をスケール・ループして動画全体に適用
  - **インパクト字幕対応**:
    - `subtitle_timing.json`の`impact_level`を読み込み
    - `none`: 通常字幕（白、60px）
    - `normal`: 通常インパクト（赤、70px）
    - `mega`: 特大インパクト（白、100px、中央）
    - `section_title`: セクションタイトル（赤、100px、中央）
  - **BGMセグメント対応**: opening/main/endingごとに適切なBGMを選択
- **レイアウト**:
  - 背景動画の上に画像をオーバーレイ
  - 画像はスケールして中央配置
  - 字幕は下部に表示
- **使用場面**: 背景動画とインパクト字幕を使用する場合（`--use-v2`オプション）

---

## 使用例

### Phase 6
```bash
# 通常版
python -m src.cli run-phase "織田信長" --phase 6

# V2版（インパクト字幕対応）
python -m src.cli run-phase "織田信長" --phase 6 --use-v2
```

### Phase 7
```bash
# 標準版（FFmpeg、推奨）
python -m src.cli run-phase "織田信長" --phase 7

# Legacy版（MoviePy、Phase 4の動画を使用）
python -m src.cli run-phase "織田信長" --phase 7 --legacy

# Legacy02版（MoviePy、Phase 3の画像を直接使用）
python -m src.cli run-phase "織田信長" --phase 7 --legacy02

# V2版（背景動画 + インパクト字幕）
python -m src.cli run-phase "織田信長" --phase 7 --use-v2
```

---

## 推奨組み合わせ

1. **通常の動画生成**:
   - Phase 6: 通常版
   - Phase 7: 標準版（FFmpeg）

2. **インパクト字幕付き動画**:
   - Phase 6: V2版（`--use-v2`）
   - Phase 7: V2版（`--use-v2`）

3. **背景動画付き動画**:
   - Phase 6: V2版（`--use-v2`）
   - Phase 7: V2版（`--use-v2`）

4. **Phase 4の動画を使用**:
   - Phase 6: 通常版
   - Phase 7: Legacy版（`--legacy`）

5. **Phase 4をスキップ**:
   - Phase 6: 通常版
   - Phase 7: Legacy02版（`--legacy02`）



