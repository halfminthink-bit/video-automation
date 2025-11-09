# 知的好奇心サムネイル自動生成システム（Phase 08統合版）

## 概要

「えっ！？」と驚く知的好奇心を刺激するサムネイルを完全自動で生成するシステムです。

**Phase 08に統合済み**: `python -m src.phases.phase_08_thumbnail "イグナーツゼンメルワイス"` で直接実行可能です。

### 🌟 重要な変更点（明るい写真モード）

**従来の問題**: 暗い雰囲気重視で人物の顔が見えにくかった

**新しいアプローチ**:
- ✨ **明るいプロフェッショナル写真**: 人物の顔がはっきり認識できる
- 📸 **スタジオライティング風**: DALL-E 3に明るく撮影するよう指示
- 🎨 **軽いビネット効果**: 暗くせず、軽く中央を強調する程度
- 💡 **明るさ強化**: 自動的に明るさを1.1倍に調整

### デザイン仕様

```
┌─────────────────────────────┐
│                             │
│      【上部：インパクト】      │
│     黄色/金色・10文字以内      │
│     大きく目立つフォント       │
│                             │
├─────────────────────────────┤
│                             │
│      （中央：画像領域）        │
│   DALL-E 3生成ドラマチック画像 │
│                             │
├─────────────────────────────┤
│                             │
│    【下部：詳細説明】          │
│   白文字・10-20文字程度        │
│      1-2行で構成             │
│                             │
└─────────────────────────────┘
```

### 特徴

- **完全自動生成**: 上下両方のテキストをClaude APIで自動生成
- **強烈なインパクト**: 上部10文字以内で「えっ！？」を引き出す
- **詳細な補完**: 下部1-2行で具体的な驚きの内容を説明
- **常識を覆す**: 多くの人が知っている「常識」と真逆の事実を提示
- **ドラマチックな背景**: DALL-E 3で生成した迫力ある画像

## ファイル構成

```
src/phases/
└── phase_08_thumbnail.py                    # Phase 08統合（メイン実行）

src/generators/
├── intellectual_curiosity_generator.py      # メインジェネレータ
├── intellectual_curiosity_text_generator.py # テキスト生成（Claude API）
├── intellectual_curiosity_text_renderer.py  # テキスト描画
└── bright_background_processor.py           # 明るい背景処理（NEW）

config/
└── intellectual_curiosity_thumbnail.yaml    # 設定ファイル

scripts/
└── test_intellectual_curiosity_thumbnail.py # テストスクリプト
```

## 使い方

### 1. Phase 08から実行（推奨）

```bash
# .envファイルにOPENAI_API_KEYを設定してから実行
python -m src.phases.phase_08_thumbnail "イグナーツゼンメルワイス"

# 他の人物でも実行可能
python -m src.phases.phase_08_thumbnail "織田信長"
python -m src.phases.phase_08_thumbnail "ナポレオン"
```

**特徴**:
- ✅ `.env`ファイルを自動的にオーバーライド読み込み
- ✅ デフォルトで知的好奇心モードを使用
- ✅ `data/subjects/<人物名>/phase_08_thumbnail/thumbnails/` に出力
- ✅ 5つのバリエーションを自動生成

### 2. プログラムから直接使用

```python
from pathlib import Path
from src.generators.intellectual_curiosity_generator import create_intellectual_curiosity_generator

# ジェネレーターを作成
generator = create_intellectual_curiosity_generator()

# サムネイルを生成
output_dir = Path("output/thumbnails")
thumbnail_paths = generator.generate_thumbnails(
    subject="イグナーツ・ゼンメルワイス",
    output_dir=output_dir,
    num_variations=5
)

print(f"Generated {len(thumbnail_paths)} thumbnails")
```

### 3. コンテキストを指定

```python
# 台本データを渡すとより適切なテキストが生成される
context = {
    "sections": [
        {
            "content": "ゼンメルワイスは手洗いの重要性を発見したが..."
        }
    ]
}

thumbnail_paths = generator.generate_thumbnails(
    subject="イグナーツ・ゼンメルワイス",
    output_dir=output_dir,
    context=context,
    num_variations=5
)
```

### 4. テストスクリプトから実行

```bash
# 指定主題でテスト
python scripts/test_intellectual_curiosity_thumbnail.py \
    --subject "イグナーツ・ゼンメルワイス"

# バリエーション数を指定
python scripts/test_intellectual_curiosity_thumbnail.py \
    --subject "織田信長" \
    --num-variations 5

# 設定ファイルのexamplesを実行
python scripts/test_intellectual_curiosity_thumbnail.py --run-examples

# デバッグモード
python scripts/test_intellectual_curiosity_thumbnail.py \
    --subject "ナポレオン" \
    --debug
```

## 設定

`config/intellectual_curiosity_thumbnail.yaml` で詳細設定が可能：

```yaml
# テキストスタイル
styles:
  top_text:
    color: "#FFD700"  # 金色/黄色
    font_size: 90
  bottom_text:
    color: "#FFFFFF"  # 白
    font_size_1line: 55
    font_size_2lines: 45

# 背景処理（明るい写真モード）
background:
  vignette: 0.2              # 軽いビネット - 顔を明るく保つ
  edge_shadow: true          # 軽い影のみ
  enhance_brightness: true   # 明るさ強化（1.1倍）

# DALL-E設定
dalle:
  size: "1792x1024"
  quality: "standard"
```

## テキスト生成のパターン

### 上部テキスト（10文字以内厳守）

1. **一言ショックパターン**
   - "実は○○だった"
   - "○○じゃない！"
   - "嘘だった？"
   - "裏の顔"
   - "真実は…"

2. **衝撃ワードパターン**
   - "殺された"
   - "追放された"
   - "黒歴史"
   - "隠された"
   - "禁断の"

3. **疑問形パターン**
   - "天才？"
   - "英雄？"
   - "誰？"
   - "なぜ？"

4. **反転パターン**
   - "逆だった"
   - "間違い"
   - "偽物"

### 下部テキスト（10-20文字程度、1-2行OK）

- 上部のインパクトを具体化
- 一般常識との矛盾を簡潔に説明
- 「実は...」「本当は...」を使った反転
- 数字や具体的な事実を含める
- 1行に収まらない場合は改行（`\n`）で2行に

## 生成例

### 例1: イグナーツ・ゼンメルワイス

```
上部: "殺された医師"
下部: "手洗い提案で精神病院送り
      医師に殺された天才"
```

### 例2: ナポレオン

```
上部: "背は高い"
下部: "167cmは当時の平均以上
      イギリスの嘘だった"
```

### 例3: エジソン

```
上部: "天才？"
下部: "発明の9割は他人のもの
      特許で勝っただけ"
```

### 例4: 織田信長

```
上部: "裏切者？"
下部: "本能寺の変の真実
      実は味方が敵だった"
```

## 技術仕様

### レイアウト

- **上部エリア（200px）**: インパクトテキスト
  - フォントサイズ: 90px
  - 色: 金色（#FFD700）
  - 縁取り: 黒30px
  - グロー効果付き

- **中央エリア（340px）**: 画像
  - DALL-E 3で生成（1792x1024）
  - ドラマチック・神秘的スタイル

- **下部エリア（180px）**: 詳細説明
  - フォントサイズ: 55px（1行）/ 45px（2行）
  - 色: 白（#FFFFFF）
  - 縁取り: 黒20px
  - 半透明黒背景付き

### テキスト生成

Claude API（gpt-4o-mini）を使用して、以下を自動生成：

1. 常識を覆すパターン
2. 衝撃的事実パターン
3. 意外な面パターン
4. 隠された真実パターン

各パターンで驚き度（curiosity_score 1-10）を評価し、最適な組み合わせを選択。

### 背景処理（明るい写真モード）

1. **明るさ強化**: 全体を1.1倍に明るく（顔がはっきり見える）
2. **コントラスト強化**: 1.1倍で顔の輪郭をくっきり
3. **軽いビネット効果**: 弱め（0.2）で中央70%は明るさそのまま
4. **軽いエッジシャドウ**: 上下に軽い影（最大80透明度）でテキストを際立たせる

**重要**: 顔の認識性を最優先し、暗化処理は行いません

## 出力例

生成されるサムネイル：

```
curiosity_イグナーツゼンメルワイス_殺された医師_v1.png
curiosity_イグナーツゼンメルワイス_嘘だった_v2.png
curiosity_ナポレオン_背は高い_v1.png
curiosity_エジソン_天才_v1.png
```

## トラブルシューティング

### フォントが見つからない

フォントは以下の順で自動検索されます：

1. `assets/fonts/GenEiKiwamiGothic-EB.ttf`
2. `assets/fonts/NotoSansJP-Bold.ttf`
3. システムフォント

フォントファイルを `assets/fonts/` に配置してください。

### テキストが長すぎる

上部テキストは10文字厳守、下部テキストは10-20文字程度が推奨です。
設定ファイルで調整可能：

```yaml
text_generation:
  top_text:
    max_chars: 10
  bottom_text:
    min_chars: 10
    max_chars: 20
```

### DALL-E 3のAPI制限

- 1分間に5リクエストまで
- エラーが出た場合は少し待ってからリトライ

## 開発者向け情報

### コンポーネント

1. **Phase08Thumbnail**: Phase 08統合層（`.env`読み込み、実行管理）
2. **IntellectualCuriosityTextGenerator**: Claude APIで上下テキストを生成
3. **IntellectualCuriosityTextRenderer**: 上部黄色、下部白でレンダリング
4. **BrightBackgroundProcessor**: 明るい背景処理（顔を明るく保つ）
5. **IntellectualCuriosityGenerator**: 全てを統合

### カスタマイズ

各コンポーネントは独立しているため、個別にカスタマイズ可能：

```python
from src.generators.intellectual_curiosity_text_renderer import IntellectualCuriosityTextRenderer

# テキストレンダラーのみを使用
renderer = IntellectualCuriosityTextRenderer(canvas_size=(1280, 720))
top_layer = renderer.render_top_text("えっ！？")
bottom_layer = renderer.render_bottom_text("実は違った\n驚きの真実")
```

## 「教科書には載せてくれない」シリーズとの違い

| 項目 | 教科書シリーズ | 知的好奇心シリーズ |
|-----|------------|---------------|
| 上部テキスト | 固定（「教科書には載せてくれない」） | 自動生成（10文字以内） |
| 上部色 | 白 | 金色/黄色 |
| 下部テキスト | 自動生成（10-15文字） | 自動生成（10-20文字、1-2行） |
| 下部色 | 金色 | 白 |
| レイアウト | 20/60/20 | 200px/340px/180px |
| ターゲット | 歴史の謎・真実 | 常識を覆す驚き |

両システムは独立して使用できます。

## ライセンス

このプロジェクトと同じライセンスに従います。

## 貢献

改善提案やバグ報告は Issue または Pull Request でお願いします。
