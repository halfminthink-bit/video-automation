# 「教科書には載せてくれない」シリーズサムネイル生成システム

## 概要

「教科書には載せてくれない」シリーズの統一感あるサムネイルを自動生成するシステムです。

### デザイン仕様

```
┌──────────────────────────────────┐
│  教科書には載せてくれない           │ ← 上部20%：白文字・黒影（固定）
│                                  │
├──────────────────────────────────┤
│                                  │
│        【人物画像エリア】         │ ← 中央60%：完全に空ける
│         （3人並び等）            │    画像をしっかり見せる
│                                  │
├──────────────────────────────────┤
│        日本史の謎                │ ← 下部20%：黄色文字・黒影（可変）
│                                  │
└──────────────────────────────────┘
```

### 特徴

- **上部テキスト**: 「教科書には載せてくれない」（固定、白文字、太い黒縁）
- **中央エリア**: 人物画像（DALL-E 3生成、歴史的スタイル）
- **下部テキスト**: 知的好奇心を刺激するフレーズ（金色、極太黒縁）
- **背景処理**: 暗めのビネット効果で重厚感を演出
- **自動生成**: Claude APIで下部テキスト5パターンを自動生成

## ファイル構成

```
src/generators/
├── textbook_series_generator.py      # メインジェネレータ
├── textbook_text_generator.py        # テキスト生成（Claude API）
├── textbook_text_renderer.py         # テキスト描画
└── dark_vignette_processor.py        # 背景処理（暗化・ビネット）

config/
└── textbook_series_thumbnail.yaml    # 設定ファイル

scripts/
└── test_textbook_series_thumbnail.py # テストスクリプト
```

## 使い方

### 1. 基本的な使い方

```python
from pathlib import Path
from src.generators.textbook_series_generator import create_textbook_series_generator

# ジェネレーターを作成
generator = create_textbook_series_generator()

# サムネイルを生成
output_dir = Path("output/thumbnails")
thumbnail_paths = generator.generate_thumbnails(
    subjects="織田信長",
    output_dir=output_dir,
    num_variations=5
)

print(f"Generated {len(thumbnail_paths)} thumbnails")
```

### 2. 複数人物の場合

```python
# 複数人物を並べる
thumbnail_paths = generator.generate_thumbnails(
    subjects=["織田信長", "豊臣秀吉", "徳川家康"],
    output_dir=output_dir,
    num_variations=5
)
```

### 3. コンテキストを指定

```python
# 台本データを渡すとより適切なテキストが生成される
context = {
    "sections": [
        {
            "content": "織田信長は戦国時代の武将で、天下統一を目指した..."
        }
    ]
}

thumbnail_paths = generator.generate_thumbnails(
    subjects="織田信長",
    output_dir=output_dir,
    context=context,
    num_variations=5
)
```

### 4. コマンドラインから実行

```bash
# 単一人物
python scripts/test_textbook_series_thumbnail.py --subject "織田信長"

# 複数人物
python scripts/test_textbook_series_thumbnail.py \
    --subjects "織田信長" "豊臣秀吉" "徳川家康" \
    --num-variations 5

# 設定ファイルのexamplesを実行
python scripts/test_textbook_series_thumbnail.py --run-examples

# デバッグモード
python scripts/test_textbook_series_thumbnail.py \
    --subject "ナポレオン" \
    --debug
```

## 設定

`config/textbook_series_thumbnail.yaml` で詳細設定が可能：

```yaml
# テキストスタイル
text_style:
  top:
    font_size: 65
    color: "#FFFFFF"  # 白
  bottom:
    font_size: 80
    color: "#FFD700"  # 金色

# 背景処理
background:
  darkness: 0.7      # 70%の明るさ
  vignette: 0.6      # 強めのビネット
  edge_shadow: true

# DALL-E設定
dalle:
  size: "1792x1024"
  quality: "standard"
```

## テキスト生成のカテゴリ

下部テキストは以下のカテゴリで自動生成されます：

1. **謎パターン**
   - "日本史の謎"
   - "隠された秘密"
   - "消された真実"

2. **真実パターン**
   - "歴史の真実"
   - "真実の物語"

3. **秘密パターン**
   - "偉人の秘密"
   - "天才の正体"

4. **闇パターン**
   - "世界史の闇"
   - "歴史の裏側"

5. **事件パターン**
   - "事件の真相"
   - "禁断の真実"

## 技術仕様

### レイアウト（20/60/20）

- **上部ゾーン（20%）**: 固定テキスト
  - フォントサイズ: 65px
  - 色: 白（#FFFFFF）
  - 縁取り: 黒25px + グレー12px

- **中央ゾーン（60%）**: 人物画像
  - DALL-E 3で生成（1792x1024）
  - 歴史的スタイル
  - セピア調または落ち着いた色調

- **下部ゾーン（20%）**: 可変テキスト
  - フォントサイズ: 65-80px（文字数で自動調整）
  - 色: 金色（#FFD700）
  - 縁取り: 黒30px + 暗赤15px
  - グロー効果付き

### 背景処理

1. **暗化処理**: 全体を70%の明るさに
2. **ビネット効果**: 強め（0.6）で中央を明るく保つ
3. **エッジシャドウ**: 上下150pxに影を追加
4. **オプション**: テクスチャオーバーレイ（羊皮紙風など）

### DALL-E 3プロンプト

- **単一人物**: 中央配置のポートレート
- **複数人物**: 横並びまたはアート的配置
- **スタイル**: 歴史的、神秘的、教育的
- **ライティング**: ドラマチックだが顔が見える明るさ

## 出力例

生成されるサムネイル：

```
textbook_織田信長_日本史の謎_v1.png
textbook_織田信長_戦国時代の闇_v2.png
textbook_織田信長_偉人の秘密_v3.png
textbook_織田信長_歴史の真実_v4.png
textbook_織田信長_消された真実_v5.png
```

## トラブルシューティング

### フォントが見つからない

フォントは以下の順で自動検索されます：

1. `assets/fonts/GenEiKiwamiGothic-EB.ttf`
2. `assets/fonts/NotoSansJP-Bold.ttf`
3. システムフォント

フォントファイルを `assets/fonts/` に配置してください。

### DALL-E 3のAPI制限

- 1分間に5リクエストまで
- エラーが出た場合は少し待ってからリトライ

### テキストが長すぎる

下部テキストは10-15文字を推奨。
`config/textbook_series_thumbnail.yaml` で調整可能：

```yaml
text_generation:
  bottom_text:
    min_length: 10
    max_length: 15
```

## 開発者向け情報

### コンポーネント

1. **TextbookTextGenerator**: Claude APIでテキスト生成
2. **TextbookTextRenderer**: PIL/Pillowでテキスト描画
3. **DarkVignetteProcessor**: 背景の暗化・ビネット処理
4. **TextbookSeriesGenerator**: 全てを統合

### カスタマイズ

各コンポーネントは独立しているため、個別にカスタマイズ可能：

```python
from src.generators.textbook_text_renderer import TextbookTextRenderer

# テキストレンダラーのみを使用
renderer = TextbookTextRenderer(canvas_size=(1280, 720))
top_layer = renderer.render_top_text()
bottom_layer = renderer.render_bottom_text("日本史の謎")
```

## ライセンス

このプロジェクトと同じライセンスに従います。

## 貢献

改善提案やバグ報告は Issue または Pull Request でお願いします。
