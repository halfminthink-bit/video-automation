# Phase 07 動画統合の現状仕様書

**最終更新**: 2025-11-20  
**対象Phase**: Phase 7 (Video Composition V2)  
**目的**: 他のAIが現状を理解し、改善提案を行うための技術仕様書

---

## 📋 概要

Phase 07は、Phase 1-6で生成された全ての素材（台本、音声、画像、字幕、BGM）を統合し、完成動画を生成するフェーズです。

**実装方式**: FFmpeg直接統合（高速化）  
**処理時間**: 約1分（MoviePy版は15分）  
**出力形式**: MP4 (H.264/AAC)

---

## 🎬 動画仕様

### 基本設定

| 項目 | 値 | 設定ファイル |
|------|-----|-------------|
| **解像度** | 1920×1080 (Full HD) | `config/phases/video_composition.yaml` |
| **フレームレート** | 30 fps | `config/phases/video_composition.yaml` |
| **ビデオコーデック** | libx264 | `config/phases/video_composition.yaml` |
| **オーディオコーデック** | AAC | `config/phases/video_composition.yaml` |
| **エンコードプリセット** | faster | `config/phases/video_composition.yaml` |
| **CRF値** | 23 | コード内で固定 |
| **ビットレート** | 3000k | `config/phases/video_composition.yaml` |

### レイアウト構成

```
┌─────────────────────────────┐
│                             │
│   画像エリア (1920×864)     │  ← 上部80%
│  (背景動画 + 画像)          │
│                             │
├─────────────────────────────┤
│   黒バー (1920×216)         │  ← 下部20%
│   字幕表示エリア             │
└─────────────────────────────┘
```

- **上部864px**: 画像と背景動画を合成
- **下部216px**: 黒背景 + 字幕表示

---

## 🎨 画像処理

### 画像生成方法

**Phase 3で生成**:
- **AI**: Stable Diffusion (Replicate API経由)
- **プロンプト最適化**: Claude APIでキーワードからプロンプト生成
- **スタイル**: ジャンルごとに自動選択（ijin/urban/history_mystery）

### 画像仕様

| 項目 | 値 |
|------|-----|
| **解像度** | 1920×1080 (リサイズ後) |
| **形式** | PNG |
| **アスペクト比** | 16:9 |
| **リサイズ方法** | `resize_images_to_1920x1080()` で統一 |

### 画像配置

- **配置方法**: セクション内で音声の長さに応じて均等分割
- **タイミング**: `audio_timing.json`の文字レベルタイミングを使用
- **表示時間**: 各画像は音声の長さに合わせて自動調整

---

## 🎤 音声処理

### 音声生成方法

**Phase 2で生成**:
- **TTS API**: ElevenLabs API（デフォルト）
- **代替**: Kokoro TTS（設定で切り替え可能）
- **タイムスタンプ**: 文字レベルタイミング情報を取得

### 音声仕様

| 項目 | 値 |
|------|-----|
| **形式** | MP3 |
| **サンプルレート** | 48000 Hz |
| **チャンネル** | ステレオ |
| **タイミング精度** | 文字レベル（ElevenLabs） |

### 音声処理フロー

1. Phase 2で各セクションごとに音声生成
2. 文字レベルのタイミング情報を取得（`character_end_times_seconds`）
3. `audio_timing.json`に保存
4. Phase 6で字幕生成時に使用
5. Phase 7で動画の長さを音声に合わせる

---

## 🎵 BGM処理

### BGM選択方法

**Phase 5で選択**:
- **選択基準**: 台本の`bgm_suggestion`（opening/main/ending）
- **ライブラリ**: `assets/bgm/{genre}/` から選択
- **固定構造**: 3トラック（opening/main/ending）を事前に選択

### BGM仕様

| 項目 | 値 |
|------|-----|
| **基本音量** | 13% (ナレーションの13%) |
| **フェードイン** | 2.0秒 |
| **フェードアウト** | 2.0秒 |
| **クロスフェード** | 3.0秒（セグメント間） |
| **ループ** | 有効（必要な長さまで自動ループ） |

### BGMタイプ別音量

| タイプ | 倍率 | 最終音量 |
|--------|------|----------|
| opening | 1.5x | 19.5% |
| main | 1.0x | 13.0% |
| ending | 0.7x | 9.1% |

### BGM処理フロー

1. Phase 5でBGMタイムライン作成（`bgm_timeline.json`）
2. Phase 7でFFmpegフィルター構築
3. 各セグメントをループ・トリミング
4. フェードイン/アウト適用
5. ナレーションとミックス（`amix`フィルター）

---

## 🎬 背景動画処理

### 背景動画選択方法

**Phase 7で選択**:
- **ライブラリ**: `assets/background_videos/`
- **カテゴリ**: opening/main/ending
- **選択モード**: ランダム（設定で変更可能）

### 背景動画仕様

| 項目 | 値 |
|------|-----|
| **解像度** | 1920×1080（リサイズ後） |
| **クロップ** | 1920×864（上部864pxを抽出） |
| **速度調整** | opening/main: 0.5倍速、ending: 1.0倍速 |
| **ループ** | 有効（必要な長さまで自動ループ、最大20回） |

### 背景動画処理フロー

1. 台本の`bgm_suggestion`に基づいて背景動画を選択
2. 各セグメントを処理:
   - リサイズ: 1920×1080
   - クロップ: 1920×864（上部）
   - 速度調整: opening/mainは0.5倍速
   - ループ/トリミング: 必要な長さに調整
3. concatファイルを作成
4. FFmpegで結合

---

## 📝 字幕処理

### 字幕生成方法

**Phase 6で生成**:
- **入力**: `audio_timing.json`（文字レベルタイミング）
- **分割**: 形態素解析（MeCabオプション）またはルールベース
- **出力**: SRT形式 + `subtitle_timing.json`（impact_level付き）

### 字幕スタイル（impact_level対応）

#### 1. Normal（impact_level: none）

| 項目 | 値 |
|------|-----|
| **フォント** | Noto Sans JP Bold |
| **サイズ** | 60px |
| **色** | 白 (#FFFFFF) |
| **縁取り** | 黒、2px |
| **シャドウ** | 有効、オフセット(2,2) |
| **位置** | 下部中央（alignment: 2） |
| **マージン** | 下から70px |

#### 2. ImpactNormal（impact_level: normal）

| 項目 | 値 |
|------|-----|
| **フォント** | Noto Sans JP Bold |
| **サイズ** | 80px |
| **色** | 赤 (#FF0000) |
| **縁取り** | 黒、3px |
| **シャドウ** | 有効、オフセット(2,2) |
| **位置** | 下部中央（alignment: 2） |
| **マージン** | 下から70px |

#### 3. ImpactMega（impact_level: mega）

| 項目 | 値 |
|------|-----|
| **フォント** | Noto Sans JP Bold |
| **サイズ** | 120px |
| **色** | 黄 (#FFFF00) |
| **縁取り** | 赤 (#FF0000)、4px |
| **シャドウ** | 有効、オフセット(3,3) |
| **位置** | 画面中央（alignment: 5） |
| **マージン** | 0px |
| **アニメーション** | 無効（現在は空配列） |

### impact_level判定方法

**Phase 6で判定**:
1. `script.json`の`impact_sentences`を読み込み
2. 字幕テキストと`impact_sentences`を正規化して比較
   - 句点・読点・改行・空白を除去
3. 完全一致で判定:
   - `mega`リストに一致 → `impact_level: "mega"`
   - `normal`リストに一致 → `impact_level: "normal"`
   - どちらにも一致しない → `impact_level: "none"`

### 字幕タイミング

- **タイミング精度**: 文字レベル（ElevenLabsタイムスタンプ）
- **最小表示時間**: 1.0秒
- **最大表示時間**: 6.0秒
- **句点延長**: 有効（次の字幕開始の0.3秒前まで延長可能）
- **重なり防止**: 有効

---

## 🔧 FFmpeg処理

### コマンド構築

**FFmpegBuilderクラス**で構築:
- `build_ffmpeg_command`: 基本版
- `build_ffmpeg_command_with_ass`: ASS字幕版
- `build_ffmpeg_command_with_ass_debug`: デバッグ版
- `build_ffmpeg_command_optimized`: 最適化版

### 処理フロー

1. **画像concat**: 画像をconcatファイルで結合
2. **背景動画concat**: 背景動画をconcatファイルで結合
3. **レイアウト合成**:
   - 画像を1920×1080にリサイズ・パディング
   - 背景動画を1920×864にクロップ
   - 画像と背景動画を合成（overlay）
4. **黒バー追加**: 下部216pxに黒バーを描画
5. **字幕焼き込み**: ASS形式の字幕を`ass`フィルターで焼き込み
6. **音声ミックス**: ナレーションとBGMを`amix`でミックス

### FFmpegフィルター例

```bash
# ビデオフィルター
-vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,drawbox=y=864:color=black:width=1920:height=216:t=fill,ass='subtitles.ass'"

# オーディオフィルター（BGMありの場合）
-filter_complex "[1:a]volume=1.0[narration];[2:a]aloop=loop=2:size=48000,atrim=0:10,afade=t=in:st=0:d=2,afade=t=out:st=8:d=2,volume=0.13[bgm0];[narration][bgm0]amix=inputs=2:duration=first:dropout_transition=3[audio]"
```

---

## 📁 ファイル構造

### 入力ファイル

```
data/working/{subject}/
├── 01_script/
│   └── script.json              # 台本（impact_sentences含む）
├── 02_audio/
│   ├── narration_full.mp3       # 統合音声
│   └── audio_timing.json        # 文字レベルタイミング
├── 03_images/
│   └── generated/
│       └── section_*.png        # 生成画像（1920×1080）
├── 05_bgm/
│   └── bgm_timeline.json        # BGMタイムライン
└── 06_subtitles/
    ├── subtitles.srt            # SRT字幕
    └── subtitle_timing.json    # タイミング情報（impact_level付き）
```

### 出力ファイル

```
data/working/{subject}/07_composition/
├── {subject}_final.mp4         # 完成動画
├── subtitles.ass               # ASS字幕ファイル
├── bg_concat.txt               # 背景動画concatファイル
├── image_concat.txt            # 画像concatファイル
└── metadata.json               # メタデータ
```

---

## 🛠️ 技術スタック

### 使用ライブラリ

| 用途 | ライブラリ/ツール |
|------|-------------------|
| **動画処理** | FFmpeg |
| **音声生成** | ElevenLabs API / Kokoro TTS |
| **画像生成** | Stable Diffusion (Replicate API) |
| **プロンプト最適化** | Claude API |
| **設定管理** | PyYAML |
| **ログ** | Python logging |

### 主要クラス

| クラス | 役割 | ファイル |
|--------|------|----------|
| `Phase07CompositionV2` | Phase 7のメインクラス | `src/phases/phase_07_composition_v2.py` |
| `BackgroundVideoProcessor` | 背景動画処理 | `src/utils/video_composition/background_processor.py` |
| `ImageProcessor` | 画像処理 | `src/utils/video_composition/image_processor.py` |
| `BGMProcessor` | BGM処理 | `src/utils/video_composition/bgm_processor.py` |
| `FFmpegBuilder` | FFmpegコマンド構築 | `src/utils/video_composition/ffmpeg_builder.py` |
| `ASSGenerator` | ASS字幕生成 | `src/utils/subtitle_utils/ass_generator.py` |
| `StyleLoader` | スタイル設定読み込み | `src/utils/subtitle_utils/style_loader.py` |
| `StyleConverter` | スタイル変換 | `src/utils/subtitle_utils/style_converter.py` |

---

## ⚙️ 設定ファイル

### 主要設定ファイル

1. **`config/phases/video_composition.yaml`**
   - 動画出力設定
   - BGM設定
   - パフォーマンス設定

2. **`config/phases/subtitle_generation.yaml`**
   - 字幕スタイル設定（impact_level対応）
   - タイミング設定
   - 分割戦略

3. **`config/phases/background_video.yaml`**
   - 背景動画ライブラリパス
   - 選択モード
   - 速度設定

---

## 🔍 処理フロー詳細

### Phase 7実行フロー

```
1. 入力ファイル確認
   ├── script.json
   ├── narration_full.mp3
   ├── audio_timing.json
   ├── section_*.png
   ├── bgm_timeline.json
   └── subtitle_timing.json

2. 背景動画選択・処理
   ├── bgm_suggestionに基づいて背景動画を選択
   ├── 各セグメントを処理（リサイズ・クロップ・速度調整）
   └── bg_concat.txtを作成

3. 画像concatファイル作成
   ├── 画像を音声の長さに応じて均等分割
   └── image_concat.txtを作成

4. ASS字幕生成
   ├── subtitle_timing.jsonからimpact_levelを取得
   ├── スタイル設定を読み込み
   └── subtitles.assを生成

5. BGMフィルター構築
   ├── 各BGMセグメントをループ・トリミング
   ├── フェードイン/アウト適用
   └── ナレーションとミックス

6. FFmpegコマンド実行
   ├── 画像と背景動画を合成
   ├── 黒バーを追加
   ├── 字幕を焼き込み
   └── 音声をミックス

7. 完成動画出力
   └── {subject}_final.mp4
```

---

## 📊 パフォーマンス

### 処理時間

| 処理 | 時間 |
|------|------|
| 背景動画処理 | 10-30秒（セグメント数による） |
| 画像concat | <1秒 |
| ASS字幕生成 | <1秒 |
| BGMフィルター構築 | <1秒 |
| FFmpeg実行 | 30-60秒 |
| **合計** | **約1-2分** |

### メモリ使用量

- **並列処理**: 有効（デフォルト）
- **スレッド数**: 自動検出（CPU数）
- **クリップ保持**: 最大10クリップ

---

## 🎯 現在の制約・課題

### 既知の制約

1. **アニメーション**: megaスタイルのアニメーションは現在無効化
2. **背景動画ループ**: 最大20回に制限（処理時間考慮）
3. **字幕分割**: MeCab未使用時はルールベース分割（精度がやや低い）

### 改善の余地

1. **アニメーション実装**: ASS形式のアニメーションタグを正しく実装
2. **背景動画トランジション**: セグメント間のトランジション未実装
3. **字幕タイミング**: より自然なタイミング調整
4. **エンコード品質**: CRF値の最適化

---

## 📝 設定変更方法

### 字幕スタイル変更

`config/phases/subtitle_generation.yaml`の`styles:`セクションを編集:

```yaml
styles:
  none:
    font:
      size: 60        # フォントサイズ
      color: "#FFFFFF"  # 色
    # ...
```

### BGM音量変更

`config/phases/video_composition.yaml`の`bgm:`セクションを編集:

```yaml
bgm:
  volume: 0.13  # 基本音量（0.0-1.0）
  volume_by_type:
    opening: 1.5
    main: 1.0
    ending: 0.7
```

### 動画品質変更

`config/phases/video_composition.yaml`の`output:`セクションを編集:

```yaml
output:
  resolution: [1920, 1080]
  fps: 30
  preset: "faster"  # ultrafast/veryfast/faster/fast/medium
```

---

## 🔗 関連ドキュメント

- `docs/PHASE_DETAILS.md`: 全Phaseの詳細
- `docs/ARCHITECTURE.md`: アーキテクチャ概要
- `config/phases/video_composition.yaml`: 動画統合設定
- `config/phases/subtitle_generation.yaml`: 字幕生成設定

---

## 📌 注意事項

1. **Phase 6必須**: `subtitle_timing.json`に`impact_level`が含まれている必要がある
2. **Phase 2必須**: `audio_timing.json`が存在する必要がある（文字レベルタイミング）
3. **背景動画**: `assets/background_videos/{category}/`に動画ファイルが必要
4. **フォント**: システムに`Noto Sans JP Bold`がインストールされている必要がある

---

**このドキュメントは、Phase 07の現状を正確に反映しています。改善提案を行う際は、この仕様を基準としてください。**









