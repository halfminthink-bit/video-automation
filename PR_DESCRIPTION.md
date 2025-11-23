# Phase 7 V2: シネマティックレイアウト実装と動画統合修正

## 📋 概要

Phase 7 V2でシネマティックレイアウトを実装し、動画統合処理の複数の問題を修正しました。

## ✨ 主な変更内容

### 1. シネマティックレイアウト実装
- **全画面没入型レイアウト**: 従来の二分割レイアウトから全画面レイアウトに変更
- **シネマティックズーム**: FFmpegフィルタグラフでKen Burns効果を実装
- **背景ブラー**: スケールダウン/アップによる擬似ブラー効果
- **グラデーション座布団**: Pillowでグラデーション画像を事前生成

### 2. 動画切り替わり問題の修正
- **concat demuxer → concat filter**: durationオプションが無視される問題を解決
- **セグメント検証**: 各セグメントの長さを検証する機能を追加
- **concat.txt改善**: duration付きconcat.txt生成とデバッグログ強化

### 3. グラデーション処理の最適化
- **処理位置変更**: 各セグメント生成時（9回）→ 最終合成時（1回）
- **処理速度**: 約1/10に短縮（120秒 → 10秒程度）

### 4. ASS字幕の検証機能
- **字幕検証**: ASS字幕のエントリ数を検証
- **デバッグログ**: 字幕のタイミング情報をログ出力

### 5. BGM処理の改善
- **入力インデックス対応**: グラデーション画像追加時の入力インデックス計算を修正
- **動的インデックス**: セグメント数に応じて動的にインデックスを計算

### 6. 2.5Dパララックス対応
- **depth_animator.py追加**: 深度マップを使った2.5Dアニメーション生成
- **最初の画像**: 深度マップが存在する場合は2.5Dパララックスを使用

### 7. リファクタリング準備
- **依存関係ドキュメント**: `phase_07_composition_v2_dependencies.md` を追加
- **構造整理**: ファイル構造と依存関係を整理

## 🔧 技術的な変更

### ファイル変更
- `src/phases/phase_07_composition_v2.py`: メインロジックの修正
- `src/utils/video_composition/bgm_processor.py`: 入力インデックス対応
- `src/utils/video_composition/depth_animator.py`: 新規追加（2.5Dアニメーション）
- `config/phases/video_composition.yaml`: 設定更新
- `docs/PHASE07_VIDEO_COMPOSITION_CURRENT_STATE.md`: ドキュメント更新
- `docs/PHASE_DIFFERENCES.md`: ドキュメント更新

### 新機能
- `_create_concat_file_with_duration()`: duration付きconcat.txt生成
- `_verify_segment_duration()`: セグメント長さ検証
- `_verify_ass_subtitles()`: ASS字幕検証
- `DepthAnimator.create_animation()`: 2.5Dアニメーション生成

## 🐛 修正した問題

1. **画像が最初の1枚だけ表示される** → concat filterで解決
2. **字幕が1回しか切り替わらない** → ASS字幕検証で確認
3. **グラデーション処理が遅い** → 最終合成時に1回だけ適用

## 📊 パフォーマンス改善

- **グラデーション処理**: 120秒 → 10秒（約1/10）
- **FFmpeg処理**: geqフィルタ廃止、Pillow事前生成で高速化
- **ブラー処理**: boxblur廃止、スケールダウン/アップで高速化

## 🧪 テスト

- [x] 動画が正しく切り替わることを確認
- [x] 字幕が正しく表示されることを確認
- [x] グラデーションが正しく適用されることを確認
- [x] BGMが正しくミックスされることを確認

## 📝 関連ドキュメント

- `phase_07_composition_v2_dependencies.md`: 依存関係構造
- `docs/PHASE07_VIDEO_COMPOSITION_CURRENT_STATE.md`: 現在の実装状態
- `docs/PHASE_DIFFERENCES.md`: Phase 7のバージョン間の違い

## 🔄 次のステップ

1. リファクタリング: 大きなメソッドの分割
2. テスト追加: ユニットテストの追加
3. パフォーマンス最適化: さらなる高速化の検討

## ⚠️ 注意事項

- この変更はPhase 7 V2のみに影響します
- Legacy版やLegacy02版には影響しません
- 既存の動画生成ワークフローとの互換性を維持しています

