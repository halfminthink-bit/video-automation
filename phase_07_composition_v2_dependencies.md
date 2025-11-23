# Phase 7 Composition V2 依存関係構造

## 📁 ファイル構造

### メインファイル
```
src/phases/phase_07_composition_v2.py (5235行)
├─ Phase07CompositionV2 クラス
└─ 83個のメソッド
```

---

## 🔗 依存関係

### 1. コアモジュール (Core)
```
src/core/
├─ phase_base.py
│  └─ PhaseBase (基底クラス)
├─ config_manager.py
│  └─ ConfigManager (設定管理)
└─ models.py
   ├─ VideoComposition
   ├─ VideoTimeline
   ├─ TimelineClip
   └─ SubtitleEntry
```

### 2. ユーティリティ - 動画合成 (Video Composition)
```
src/utils/video_composition/
├─ bgm_processor.py
│  └─ BGMProcessor
│     ├─ build_audio_filter()
│     ├─ create_bgm_filter_for_background()
│     └─ get_audio_duration()
│
├─ background_processor.py
│  └─ BackgroundVideoProcessor
│
├─ depth_animator.py
│  └─ DepthAnimator
│     └─ create_animation() (2.5Dパララックス)
│
├─ ffmpeg_builder.py
│  └─ FFmpegBuilder
│     ├─ build_ffmpeg_command_optimized()
│     ├─ build_ffmpeg_command_with_ass_debug()
│     └─ build_ffmpeg_command_with_ass()
│
└─ image_processor.py
```

### 3. ユーティリティ - 字幕 (Subtitle Utils)
```
src/utils/subtitle_utils/
├─ ass_generator.py
│  └─ ASSGenerator
│     ├─ create_ass_file()
│     └─ format_ass_time()
│
├─ animation_tags.py
├─ style_converter.py
└─ style_loader.py
```

### 4. ユーティリティ - 画像タイミング
```
src/utils/
├─ image_timing_matcher_fixed.py
│  └─ ImageTimingMatcherFixed (キーワードマッチング)
│
└─ image_timing_matcher_llm.py
   └─ ImageTimingMatcherLLM (LLM駆動型)
```

### 5. ジェネレーター
```
src/generators/
└─ background_video_selector.py
   └─ BackgroundVideoSelector
```

### 6. 外部ライブラリ
```
標準ライブラリ:
├─ json
├─ platform
├─ random
├─ re
├─ subprocess
├─ time
├─ yaml
├─ pathlib.Path
├─ typing (List, Dict, Any, Optional, TYPE_CHECKING)
└─ datetime

外部パッケージ:
├─ moviepy (VideoFileClip, AudioFileClip, etc.)
├─ PIL (Image)
└─ numpy (np)
```

### 7. 設定ファイル
```
config/phases/
├─ video_composition.yaml (Phase 7設定)
├─ video_composition_legacy.yaml (Legacy設定)
└─ video_composition_legacy02.yaml (Legacy02設定)
```

### 8. 呼び出し元
```
src/cli.py
└─ run_phase() 関数
   └─ Phase07CompositionV2 をインポート・使用
```

---

## 📊 クラス構造

### Phase07CompositionV2 クラス

#### 初期化・設定
- `__init__()` - 初期化、プロセッサー初期化
- `get_phase_number()` - Phase番号取得
- `get_phase_name()` - Phase名取得
- `get_phase_directory()` - Phaseディレクトリ取得
- `check_inputs_exist()` - 入力チェック
- `check_outputs_exist()` - 出力チェック

#### 実行メソッド
- `execute_phase()` - メイン実行
- `_execute_moviepy()` - MoviePy版実行
- `_execute_legacy()` - Legacy版実行
- `_execute_ffmpeg_direct()` - FFmpeg直接実行（メイン）
- `_execute_with_background_video()` - 背景動画付き実行

#### データ読み込み
- `_load_script()` - 台本読み込み
- `_load_audio_timing()` - 音声タイミング読み込み
- `_load_subtitles()` - 字幕読み込み
- `_load_animated_clips()` - アニメーション動画読み込み
- `_load_bgm()` - BGMデータ読み込み
- `_get_images_for_sections()` - セクション画像取得

#### 動画セグメント生成
- `_create_segment_videos_then_concat()` - セグメント生成→連結（メイン）
- `_create_zoompan_segment()` - 4Kズームセグメント生成
- `_create_concat_file_with_duration()` - concat.txt生成（duration付き）
- `_verify_segment_duration()` - セグメント長さ検証
- `_calculate_image_timings()` - 画像タイミング計算

#### グラデーション処理
- `_create_gradient_image()` - グラデーション画像生成
- `_apply_gradient_to_video()` - 動画にグラデーション適用

#### 字幕処理
- `_create_ass_subtitles_fixed()` - ASS字幕生成（修正版）
- `_create_ass_subtitles()` - ASS字幕生成（旧版）
- `_verify_ass_subtitles()` - ASS字幕検証
- `_convert_srt_to_ass()` - SRT→ASS変換
- `_convert_srt_to_ass_with_impact()` - SRT→ASS変換（インパクト付き）
- `_burn_subtitles()` - 字幕焼き込み
- `_burn_subtitles_with_impact()` - 字幕焼き込み（インパクト付き）

#### FFmpegコマンド構築
- `_build_ffmpeg_command_optimized()` - 最適化FFmpegコマンド
- `_build_ffmpeg_command_with_ass_debug()` - ASS字幕デバッグ付き
- `_build_ffmpeg_command_with_ass()` - ASS字幕付き
- `_build_ffmpeg_command()` - 基本FFmpegコマンド
- `_build_audio_filter()` - オーディオフィルタ構築

#### 背景動画処理
- `_create_video_with_background()` - 背景動画付き動画生成
- `_create_background_concat_file()` - 背景動画concat.txt生成
- `_align_background_videos_with_bgm()` - BGMと背景動画の同期
- `_create_bgm_filter_for_background()` - 背景動画用BGMフィルタ

#### レイアウト処理
- `_create_split_layout_video()` - 分割レイアウト動画生成
- `_create_bottom_subtitle_bar()` - 下部字幕バー生成
- `_create_top_video_area()` - 上部動画エリア生成
- `_resize_clip_for_split_layout()` - 分割レイアウト用リサイズ

#### ユーティリティ
- `_resolve_image_path()` - 画像パス解決
- `_get_audio_path()` - 音声パス取得
- `_get_audio_duration()` - 音声長さ取得
- `_get_video_duration()` - 動画長さ取得
- `_get_section_duration()` - セクション長さ取得
- `_get_section_duration_from_script()` - 台本からセクション長さ取得
- `_get_bgm_volume_for_type()` - BGMタイプ別音量取得
- `_detect_section_title_segments()` - セクションタイトル検出
- `_run_ffmpeg_safe()` - FFmpeg安全実行
- `_create_ffmpeg_concat_file()` - FFmpeg concat.txt生成
- `_create_concat_file_with_keyword_matching()` - キーワードマッチングconcat.txt
- `_create_image_concat_file()` - 画像concat.txt生成
- `_generate_thumbnail()` - サムネイル生成
- `_generate_thumbnail_with_ffmpeg()` - FFmpegでサムネイル生成
- `_save_metadata()` - メタデータ保存
- `_load_japanese_font()` - 日本語フォント読み込み
- `_create_subtitle_image()` - 字幕画像生成
- `_format_ass_time()` - ASS時間フォーマット
- `_format_ass_time_precise()` - ASS時間フォーマット（精密版）
- `_get_ass_header()` - ASSヘッダー取得
- `_get_ass_header_fixed()` - ASSヘッダー取得（修正版）
- `_verify_ass_file()` - ASSファイル検証
- `verify_subtitle_timing_detailed()` - 字幕タイミング詳細検証
- `analyze_subtitle_coverage()` - 字幕カバレッジ分析
- `run_ffmpeg_with_timing_fix()` - タイミング修正付きFFmpeg実行
- `validate_output()` - 出力検証

---

## 🔄 データフロー

### メイン実行フロー
```
execute_phase()
  └─ _execute_ffmpeg_direct()
      ├─ _load_script()
      ├─ _load_audio_timing()
      ├─ _load_bgm()
      └─ _create_segment_videos_then_concat()
          ├─ _calculate_image_timings()
          ├─ _create_zoompan_segment() (各画像)
          ├─ _create_concat_file_with_duration()
          ├─ _create_gradient_image()
          ├─ _create_ass_subtitles_fixed()
          └─ FFmpeg最終合成
              ├─ concat filter (セグメント連結)
              ├─ グラデーション overlay
              ├─ ASS字幕焼き込み
              └─ BGMミックス
```

### 画像タイミング計算フロー
```
_calculate_image_timings()
  ├─ processed_images.json 読み込み
  ├─ classified.json 読み込み（フォールバック）
  ├─ audio_timing.json 読み込み
  └─ タイミングモード選択:
      ├─ LLMモード → ImageTimingMatcherLLM
      ├─ キーワードマッチング → ImageTimingMatcherFixed
      └─ 均等分割モード
```

### 字幕生成フロー
```
_create_ass_subtitles_fixed()
  ├─ subtitle_timing.json 読み込み
  ├─ ASSGenerator.create_ass_file()
  └─ スタイル適用
```

### BGM処理フロー
```
_load_bgm()
  └─ BGMProcessor.build_audio_filter()
      ├─ 各BGMセグメント処理
      ├─ ループ・トリミング
      ├─ フェードイン/アウト
      └─ ナレーションとミックス
```

---

## 📦 インスタンス変数

### プロセッサー
- `self.bgm_processor: BGMProcessor`
- `self.ass_generator: ASSGenerator`
- `self.depth_animator: DepthAnimator`
- `self.background_processor: BackgroundVideoProcessor`
- `self.ffmpeg_builder: FFmpegBuilder`
- `self.background_video_selector: BackgroundVideoSelector`

### 設定
- `self.phase_config: dict`
- `self.genre: Optional[str]`
- `self.use_legacy: bool`
- `self.resolution: tuple`
- `self.fps: int`
- `self.bgm_base_volume: float`
- `self.bgm_volume_amplification: float`
- `self.bgm_fade_in: float`
- `self.bgm_fade_out: float`
- `self.subtitle_font: str`
- `self.encode_preset: str`

---

## 🎯 リファクタリング候補

### 1. 大きなメソッドの分割
- `_create_segment_videos_then_concat()` (約630行) → 複数メソッドに分割
- `_calculate_image_timings()` (約310行) → タイミングモード別に分割
- `_create_ass_subtitles_fixed()` (約230行) → 処理ステップ別に分割

### 2. 責任の分離
- **動画セグメント生成**: 別クラス `VideoSegmentGenerator`
- **字幕処理**: 別クラス `SubtitleProcessor` (ASSGeneratorを拡張)
- **FFmpegコマンド構築**: FFmpegBuilderに移行
- **画像タイミング計算**: 既存のMatcherクラスを活用

### 3. 重複コードの統合
- `_format_ass_time()` と `_format_ass_time_precise()` → 統合
- `_get_ass_header()` と `_get_ass_header_fixed()` → 統合
- `_build_ffmpeg_command_*()` メソッド群 → FFmpegBuilderに統合

### 4. 設定の外部化
- ハードコードされた値（解像度、FPS、フォントサイズなど）→ 設定ファイルへ

### 5. エラーハンドリングの統一
- 各メソッドのエラーハンドリングを統一パターンに

---

## 📝 ファイルサイズ
- **総行数**: 5235行
- **クラス数**: 1
- **メソッド数**: 83
- **平均メソッド長**: 約63行

---

## 🔍 依存関係の詳細

### 直接依存 (Direct Dependencies)
1. `src/core/phase_base.py` - 基底クラス
2. `src/core/config_manager.py` - 設定管理
3. `src/core/models.py` - データモデル
4. `src/utils/video_composition/bgm_processor.py` - BGM処理
5. `src/utils/video_composition/depth_animator.py` - 2.5Dアニメーション
6. `src/utils/video_composition/background_processor.py` - 背景動画処理
7. `src/utils/video_composition/ffmpeg_builder.py` - FFmpegコマンド構築
8. `src/utils/subtitle_utils/ass_generator.py` - ASS字幕生成
9. `src/utils/image_timing_matcher_fixed.py` - 画像タイミング（固定）
10. `src/utils/image_timing_matcher_llm.py` - 画像タイミング（LLM）
11. `src/generators/background_video_selector.py` - 背景動画選択

### 間接依存 (Indirect Dependencies)
- 他のPhaseクラス（Phase01-06の出力を使用）
- 設定ファイル（YAML）
- データファイル（JSON）

---

## 🚀 推奨リファクタリング戦略

1. **段階的リファクタリング**
   - Step 1: 大きなメソッドの分割
   - Step 2: 責任の分離（クラス抽出）
   - Step 3: 重複コードの統合
   - Step 4: テストの追加

2. **優先度**
   - **高**: `_create_segment_videos_then_concat()` の分割
   - **中**: 字幕処理の分離
   - **低**: ユーティリティメソッドの整理

3. **テスト戦略**
   - 各リファクタリング後に既存の動作確認
   - 段階的にユニットテストを追加

