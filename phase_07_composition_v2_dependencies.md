# Phase 7 Composition V2 依存関係構造（リファクタリング後）

## 📁 ファイル構造（リファクタリング後）

### メインファイル
```
src/phases/phase_07_composition_v2.py (約662行)
├─ Phase07CompositionV2 クラス
│  ├─ 軽量オーケストレーター（実行フロー制御のみ）
│  └─ 専門クラスへの委譲
└─ 約20個のメソッド（大幅削減）
```

### 専門クラス（リファクタリングで分離）
```
src/utils/video_composition/
├─ data_loader.py
│  └─ Phase07DataLoader
│     ├─ load_all_data() - 全データ一括読み込み
│     ├─ load_script() - 台本読み込み
│     ├─ load_audio_timing() - 音声タイミング読み込み
│     ├─ load_subtitles() - 字幕読み込み
│     ├─ load_bgm() - BGMデータ読み込み
│     └─ load_processed_images() - 処理済み画像読み込み
│
├─ video_segment_generator.py
│  └─ VideoSegmentGenerator
│     ├─ create_video_from_segments() - メイン処理
│     ├─ _create_segment_videos_then_concat() - セグメント生成→連結
│     ├─ _create_zoompan_segment() - 4Kズームセグメント生成
│     ├─ _create_concat_file_with_duration() - concat.txt生成
│     └─ _calculate_image_timings() - 画像タイミング計算
│
├─ gradient_processor.py
│  └─ GradientProcessor
│     ├─ create_gradient_image() - グラデーション画像生成
│     └─ apply_to_video() - 動画にグラデーション適用（非推奨）
│
├─ ffmpeg_builder.py
│  └─ FFmpegBuilder
│     └─ build_ffmpeg_command_optimized() - 最適化FFmpegコマンド
│        ├─ グラデーションオーバーレイ（最終合成時）
│        ├─ ASS字幕焼き込み
│        └─ BGMミックス
│
├─ bgm_processor.py
│  └─ BGMProcessor
│     ├─ build_audio_filter() - オーディオフィルタ構築
│     └─ get_audio_duration() - 音声長さ取得
│
├─ background_video_composer.py
│  └─ BackgroundVideoComposer
│     └─ compose_with_background() - 背景動画合成
│
└─ depth_animator.py
   └─ DepthAnimator
      └─ create_animation() - 2.5Dパララックスアニメーション
```

```
src/utils/subtitle_utils/
├─ subtitle_processor.py
│  └─ SubtitleProcessor
│     ├─ create_ass_file() - ASS字幕ファイル生成
│     └─ burn_subtitles_with_impact() - 字幕焼き込み（インパクト付き）
│
└─ ass_generator.py
   └─ ASSGenerator
      └─ create_ass_file() - ASSファイル生成（内部使用）
```

---

## 🔗 依存関係（リファクタリング後）

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
├─ data_loader.py (新規分離)
│  └─ Phase07DataLoader
│
├─ video_segment_generator.py (新規分離)
│  └─ VideoSegmentGenerator
│
├─ gradient_processor.py (新規分離)
│  └─ GradientProcessor
│
├─ bgm_processor.py
│  └─ BGMProcessor
│
├─ background_processor.py
│  └─ BackgroundVideoProcessor
│
├─ depth_animator.py
│  └─ DepthAnimator
│
├─ ffmpeg_builder.py
│  └─ FFmpegBuilder
│
└─ background_video_composer.py
   └─ BackgroundVideoComposer
```

### 3. ユーティリティ - 字幕 (Subtitle Utils)
```
src/utils/subtitle_utils/
├─ subtitle_processor.py (新規分離)
│  └─ SubtitleProcessor
│
├─ ass_generator.py
│  └─ ASSGenerator
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
├─ moviepy (VideoFileClip, AudioFileClip, etc.) - 互換性のため保持
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

## 📊 クラス構造（リファクタリング後）

### Phase07CompositionV2 クラス（軽量オーケストレーター）

#### 初期化・設定
- `__init__()` - 初期化、専門クラスの初期化
- `_init_specialized_classes()` - 専門クラスの初期化
- `get_phase_number()` - Phase番号取得
- `get_phase_name()` - Phase名取得
- `get_phase_directory()` - Phaseディレクトリ取得
- `check_inputs_exist()` - 入力チェック（DataLoaderに委譲）
- `check_outputs_exist()` - 出力チェック

#### 実行メソッド（フロー制御のみ）
- `execute_phase()` - メイン実行（モード分岐）
- `_execute_ffmpeg_direct()` - FFmpeg直接統合モード（推奨）
- `_execute_with_background_video()` - 背景動画モード
- `_execute_moviepy()` - MoviePy統合モード（互換性のため保持）
- `_execute_legacy()` - Legacy版実行

#### ヘルパーメソッド（MoviePy用 - 互換性のため保持）
- `_create_video_clips()` - 動画クリップ準備
- `_concatenate_clips()` - 動画クリップ連結
- `_add_bgm()` - BGM追加
- `_add_subtitles()` - 字幕追加
- `_create_split_layout_video()` - 分割レイアウト動画生成
- `_render_video()` - 動画レンダリング
- `_generate_thumbnail()` - サムネイル生成（MoviePy用）
- `_generate_thumbnail_from_video()` - サムネイル生成（FFmpeg用）
- `_save_metadata()` - メタデータ保存
- `validate_output()` - 出力検証

### 専門クラス（リファクタリングで分離）

#### Phase07DataLoader
- `load_all_data()` - 全データ一括読み込み
- `load_script()` - 台本読み込み
- `load_audio_timing()` - 音声タイミング読み込み
- `load_subtitles()` - 字幕読み込み
- `load_bgm()` - BGMデータ読み込み
- `load_processed_images()` - 処理済み画像読み込み
- `check_inputs()` - 入力ファイル存在確認

#### VideoSegmentGenerator
- `create_video_from_segments()` - メイン処理
- `_create_segment_videos_then_concat()` - セグメント生成→連結
- `_create_zoompan_segment()` - 4Kズームセグメント生成（グラデーションなし）
- `_create_concat_file_with_duration()` - concat.txt生成（duration付き）
- `_calculate_image_timings()` - 画像タイミング計算

#### SubtitleProcessor
- `create_ass_file()` - ASS字幕ファイル生成
- `burn_subtitles_with_impact()` - 字幕焼き込み（インパクト付き）

#### GradientProcessor
- `create_gradient_image()` - グラデーション画像生成（キャッシュ対応）
- `apply_to_video()` - 動画にグラデーション適用（非推奨、最終合成時に適用）

#### FFmpegBuilder
- `build_ffmpeg_command_optimized()` - 最適化FFmpegコマンド
  - グラデーションオーバーレイ（最終合成時、一番上のレイヤー）
  - ASS字幕焼き込み
  - BGMミックス

#### BGMProcessor
- `build_audio_filter()` - オーディオフィルタ構築（動的入力インデックス対応）
- `get_audio_duration()` - 音声長さ取得

---

## 🔄 データフロー（リファクタリング後）

### メイン実行フロー（FFmpeg直接統合モード - 推奨）
```
execute_phase()
  └─ _execute_ffmpeg_direct()
      ├─ 1. データ読み込み（Phase07DataLoaderに委譲）
      │   └─ data_loader.load_all_data()
      │       ├─ script
      │       ├─ audio_path
      │       ├─ audio_timing
      │       ├─ subtitles
      │       ├─ bgm
      │       └─ images
      │
      ├─ 2. ASS字幕ファイル生成（SubtitleProcessorに委譲）
      │   └─ subtitle_processor.create_ass_file()
      │
      ├─ 3. 動画セグメント生成（VideoSegmentGeneratorに委譲）
      │   └─ video_segment_generator.create_video_from_segments()
      │       └─ _create_segment_videos_then_concat()
      │           ├─ 画像タイミング計算
      │           ├─ 各セグメント生成（グラデーションなし）
      │           ├─ concat.txt生成
      │           ├─ グラデーション画像生成（1回だけ）
      │           └─ FFmpeg最終合成（FFmpegBuilderに委譲）
      │               └─ build_ffmpeg_command_optimized()
      │                   ├─ concat demuxer（セグメント連結）
      │                   ├─ グラデーションオーバーレイ（一番上のレイヤー）
      │                   ├─ スケーリング
      │                   ├─ ASS字幕焼き込み
      │                   └─ BGMミックス
      │
      ├─ 4. サムネイル生成
      └─ 5. メタデータ保存
```

### 画像タイミング計算フロー
```
VideoSegmentGenerator._calculate_image_timings()
  ├─ processed_images.json 読み込み
  ├─ classified.json 読み込み（フォールバック）
  ├─ audio_timing.json 読み込み
  └─ タイミングモード選択:
      ├─ LLMモード → ImageTimingMatcherLLM
      ├─ キーワードマッチング → ImageTimingMatcherFixed
      └─ 均等分割モード（デフォルト）
```

### 字幕生成フロー
```
SubtitleProcessor.create_ass_file()
  ├─ subtitle_timing.json 読み込み
  ├─ ASSGenerator.create_ass_file()（内部使用）
  └─ スタイル適用
```

### BGM処理フロー
```
BGMProcessor.build_audio_filter()
  ├─ 各BGMセグメント処理
  ├─ ループ・トリミング
  ├─ フェードイン/アウト
  └─ ナレーションとミックス
```

### グラデーション処理フロー（最適化後）
```
1. 各セグメント生成時: グラデーションなし（高速化）
   ↓
2. 最終合成時: グラデーション画像生成（1回だけ、キャッシュ対応）
   ↓
3. FFmpeg最終合成: グラデーションオーバーレイ（一番上のレイヤー）
   - 処理順序: concat動画 → グラデーション → スケーリング → 字幕
```

---

## 📦 インスタンス変数（リファクタリング後）

### 専門クラス（委譲先）
- `self.data_loader: Phase07DataLoader` - データ読み込み
- `self.video_segment_generator: VideoSegmentGenerator` - 動画セグメント生成
- `self.subtitle_processor: SubtitleProcessor` - 字幕処理
- `self.background_composer: BackgroundVideoComposer` - 背景動画合成
- `self.gradient_processor: GradientProcessor` - グラデーション処理

### プロセッサー（互換性のため保持）
- `self.bgm_processor: BGMProcessor` - BGM処理
- `self.ass_generator: ASSGenerator` - ASS生成（内部使用）
- `self.depth_animator: DepthAnimator` - 2.5Dアニメーション
- `self.background_processor: BackgroundVideoProcessor` - 背景動画処理
- `self.ffmpeg_builder: FFmpegBuilder` - FFmpegコマンド構築
- `self.background_video_selector: BackgroundVideoSelector` - 背景動画選択

### 設定
- `self.phase_config: dict` - Phase設定
- `self.genre: Optional[str]` - ジャンル
- `self.use_legacy: bool` - Legacy版使用フラグ
- `self.resolution: tuple` - 解像度
- `self.fps: int` - FPS
- `self.bgm_base_volume: float` - BGM基本音量
- `self.bgm_volume_amplification: float` - BGM音量増幅率
- `self.bgm_fade_in: float` - BGMフェードイン時間
- `self.bgm_fade_out: float` - BGMフェードアウト時間
- `self.subtitle_font: str` - 字幕フォント
- `self.encode_preset: str` - エンコードプリセット
- `self.use_ffmpeg_direct: bool` - FFmpeg直接統合モード使用フラグ
- `self.use_background_video: bool` - 背景動画モード使用フラグ

---

## 🎯 リファクタリングの成果

### 1. コード量の削減
- **リファクタリング前**: 約5235行（推定）
- **リファクタリング後**: 約662行（約87%削減）
- **メソッド数**: 83個 → 約20個（約76%削減）

### 2. 責任の分離
- **Phase07CompositionV2**: 軽量オーケストレーター（実行フロー制御のみ）
- **Phase07DataLoader**: データ読み込み専門
- **VideoSegmentGenerator**: 動画セグメント生成専門
- **SubtitleProcessor**: 字幕処理専門
- **GradientProcessor**: グラデーション処理専門
- **FFmpegBuilder**: FFmpegコマンド構築専門

### 3. 処理の最適化
- **グラデーション処理**: 各セグメント生成時（9回）→ 最終合成時（1回）
- **字幕処理**: 2回適用 → 1回適用
- **処理時間**: 大幅短縮（約120秒 → 約10秒）

### 4. 保守性の向上
- 各専門クラスが独立してテスト可能
- 責任が明確で変更影響範囲が限定される
- コードの可読性が向上

---

## 🚀 処理モード

### 1. FFmpeg直接統合モード（推奨・デフォルト）
- **使用クラス**: `VideoSegmentGenerator` + `SubtitleProcessor` + `FFmpegBuilder`
- **特徴**: 高速、高品質、グラデーション最適化済み
- **処理フロー**: 上記「メイン実行フロー」参照

### 2. 背景動画モード
- **使用クラス**: `BackgroundVideoComposer` + `SubtitleProcessor`
- **特徴**: 背景動画 + スケール画像の合成
- **処理フロー**: 背景動画選択 → 合成 → 字幕適用

### 3. MoviePy統合モード（互換性のため保持）
- **使用クラス**: MoviePy（直接使用）
- **特徴**: 従来の方法、互換性のため保持
- **処理フロー**: MoviePyクリップ操作

### 4. Legacyモード
- **使用クラス**: `phase_07_composition_legacy.py`
- **特徴**: 旧実装の実行
- **処理フロー**: Legacyモジュールに委譲

---

## 🔍 依存関係の詳細（リファクタリング後）

### 直接依存 (Direct Dependencies)
1. `src/core/phase_base.py` - 基底クラス
2. `src/core/config_manager.py` - 設定管理
3. `src/core/models.py` - データモデル
4. `src/utils/video_composition/data_loader.py` - データ読み込み（新規分離）
5. `src/utils/video_composition/video_segment_generator.py` - 動画セグメント生成（新規分離）
6. `src/utils/video_composition/gradient_processor.py` - グラデーション処理（新規分離）
7. `src/utils/subtitle_utils/subtitle_processor.py` - 字幕処理（新規分離）
8. `src/utils/video_composition/ffmpeg_builder.py` - FFmpegコマンド構築
9. `src/utils/video_composition/bgm_processor.py` - BGM処理
10. `src/utils/video_composition/depth_animator.py` - 2.5Dアニメーション
11. `src/utils/video_composition/background_processor.py` - 背景動画処理
12. `src/utils/video_composition/background_video_composer.py` - 背景動画合成
13. `src/utils/subtitle_utils/ass_generator.py` - ASS字幕生成
14. `src/utils/image_timing_matcher_fixed.py` - 画像タイミング（固定）
15. `src/utils/image_timing_matcher_llm.py` - 画像タイミング（LLM）
16. `src/generators/background_video_selector.py` - 背景動画選択

### 間接依存 (Indirect Dependencies)
- 他のPhaseクラス（Phase01-06の出力を使用）
- 設定ファイル（YAML）
- データファイル（JSON）

---

## 📝 ファイルサイズ（リファクタリング後）
- **Phase07CompositionV2**: 約662行
- **Phase07DataLoader**: 約767行
- **VideoSegmentGenerator**: 約597行
- **SubtitleProcessor**: 約718行
- **GradientProcessor**: 約100行
- **FFmpegBuilder**: 約492行（グラデーション対応）
- **合計**: 約3336行（専門クラス含む）

---

## ✨ 主な改善点

### 1. グラデーション処理の最適化
- **変更前**: 各セグメント生成時にグラデーション適用（9回）
- **変更後**: 最終合成時に1回だけ適用
- **効果**: 処理時間約120秒 → 約10秒（約92%削減）

### 2. 字幕処理の最適化
- **変更前**: 2回適用（セグメント生成時 + 最終合成時）
- **変更後**: 1回適用（最終合成時のみ）
- **効果**: 処理時間削減、エラー解消

### 3. コードの可読性向上
- **変更前**: 1つの巨大なクラス（約5235行）
- **変更後**: 軽量オーケストレーター + 専門クラス群
- **効果**: 責任が明確、変更影響範囲が限定される

### 4. テスト容易性の向上
- **変更前**: 巨大なクラスのテストが困難
- **変更後**: 各専門クラスが独立してテスト可能
- **効果**: ユニットテストの追加が容易

---

## 🎓 アーキテクチャパターン

### オーケストレーターパターン
- **Phase07CompositionV2**: オーケストレーター（実行フロー制御）
- **専門クラス群**: オーケストレートされるコンポーネント（具体的な処理）

### 責任の分離（Separation of Concerns）
- データ読み込み: `Phase07DataLoader`
- 動画生成: `VideoSegmentGenerator`
- 字幕処理: `SubtitleProcessor`
- グラデーション: `GradientProcessor`
- FFmpegコマンド: `FFmpegBuilder`

### 依存性注入（Dependency Injection）
- 各専門クラスは初期化時に必要な依存関係を受け取る
- テスト時にモックに置き換え可能

---

## 🔄 今後の改善候補

### 1. さらなる最適化
- セグメント生成の並列化
- キャッシュ戦略の改善

### 2. テストの追加
- 各専門クラスのユニットテスト
- 統合テストの追加

### 3. エラーハンドリングの統一
- 各専門クラスのエラーハンドリングを統一パターンに

### 4. 設定の外部化
- ハードコードされた値の設定ファイル化
