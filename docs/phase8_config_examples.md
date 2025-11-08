# Phase 8 サムネイル生成 - 設定例

## 概要

Phase 8では、以下の3つの方法でサムネイルを生成できます：

1. **DALL-E 3 + Pillow + Claude** (推奨)
2. **gpt-image-1 + Pillow + Claude**
3. **Pillow のみ** (無料)

---

## 設定例

### 1. DALL-E 3 + Pillow + Claude (推奨)

**特徴**:
- ✅ 高品質な背景画像
- ✅ バズるキャッチコピー
- ✅ 完璧な日本語
- ✅ 速い（30秒程度）
- 💰 コスト: $0.04-0.08/枚

**config.yaml**:
```yaml
phase_08_thumbnail:
  use_dalle: true
  
  # キャッチコピー生成設定
  catchcopy:
    enabled: true
    model: gpt-4.1-mini  # または gpt-4o-mini
    tone: dramatic  # dramatic, shocking, educational, casual
    target_audience: 一般
    main_title_length: 20
    sub_title_length: 10
    num_candidates: 5
  
  # 背景画像生成設定
  gptimage:
    model: dall-e-3  # DALL-E 3を使用
    width: 1280
    height: 720
    style: dramatic  # dramatic, professional, minimalist, vibrant
    quality: standard  # standard または hd
    layout: center  # center, left, right
```

**料金**:
- `quality: standard`: $0.04/枚
- `quality: hd`: $0.08/枚

---

### 2. gpt-image-1 + Pillow + Claude

**特徴**:
- ✅ 高品質な背景画像
- ✅ バズるキャッチコピー
- ✅ 完璧な日本語
- ⚠️ 遅い（2分程度）
- 💰 コスト: $0.011-0.167/枚

**config.yaml**:
```yaml
phase_08_thumbnail:
  use_dalle: true
  
  catchcopy:
    enabled: true
    model: gpt-4.1-mini
    tone: dramatic
    target_audience: 一般
    main_title_length: 20
    sub_title_length: 10
    num_candidates: 5
  
  gptimage:
    model: gpt-image-1  # gpt-image-1を使用
    width: 1280
    height: 720
    style: dramatic
    quality: medium  # low, medium, high
    layout: center
```

**料金**:
- `quality: low`: $0.011/枚
- `quality: medium`: $0.042/枚
- `quality: high`: $0.167/枚

---

### 3. Pillow のみ (無料)

**特徴**:
- ✅ 完全無料
- ✅ 高速
- ✅ 完璧な日本語
- ⚠️ グラデーション背景のみ（またはPhase 3の画像を使用）

**config.yaml**:
```yaml
phase_08_thumbnail:
  use_dalle: false  # Pillowのみを使用
  
  pillow:
    width: 1280
    height: 720
    layout: background  # background, center, left
```

---

## トーンの選択

### dramatic（劇的）
- インパクトがある
- 感情を揺さぶる
- 例: "手洗いで命を救った男"

### shocking（衝撃的）
- 驚きを与える
- 強い表現
- 例: "医者に殺された発見者"

### educational（教育的）
- 知的で落ち着いた表現
- 例: "手洗いの歴史を変えた男"

### casual（カジュアル）
- 親しみやすい
- 軽い口調
- 例: "手洗いってこんなに大事！"

---

## スタイルの選択

### dramatic
- 大胆な色使い
- ドラマチックな照明
- 高コントラスト

### professional
- モダンな色パレット
- ソフトな照明
- バランスの取れた構図

### minimalist
- シンプルな形状
- 落ち着いた色
- ネガティブスペースを活用

### vibrant
- 明るい色
- エネルギッシュな構図
- ダイナミックな要素

---

## レイアウトの選択

### center
- テキストを中央に配置
- バランスが良い

### left
- テキストを左寄せ
- 右側に視覚的な要素を配置

### right
- テキストを右寄せ
- 左側に視覚的な要素を配置

---

## 環境変数

### OPENAI_API_KEY

DALL-E 3またはgpt-image-1を使用する場合は、OpenAI APIキーを設定してください。

**Windows**:
```powershell
$env:OPENAI_API_KEY = "sk-proj-..."
```

**Linux/Mac**:
```bash
export OPENAI_API_KEY="sk-proj-..."
```

または `.env` ファイルに設定:
```
OPENAI_API_KEY=sk-proj-...
```

---

## 推奨設定

### 一般的な動画
```yaml
phase_08_thumbnail:
  use_dalle: true
  
  catchcopy:
    enabled: true
    tone: dramatic
  
  gptimage:
    model: dall-e-3
    quality: standard
    style: dramatic
```

### 教育系動画
```yaml
phase_08_thumbnail:
  use_dalle: true
  
  catchcopy:
    enabled: true
    tone: educational
  
  gptimage:
    model: dall-e-3
    quality: standard
    style: professional
```

### エンタメ系動画
```yaml
phase_08_thumbnail:
  use_dalle: true
  
  catchcopy:
    enabled: true
    tone: shocking
  
  gptimage:
    model: dall-e-3
    quality: hd
    style: vibrant
```

### コスト重視
```yaml
phase_08_thumbnail:
  use_dalle: false  # Pillowのみ
  
  pillow:
    layout: background  # Phase 3の画像を使用
```

---

## トラブルシューティング

### 401 Authentication Error

**原因**: OpenAI APIキーが無効または未設定

**解決策**:
1. OpenAI APIキーを確認
2. 環境変数 `OPENAI_API_KEY` を設定
3. `.env` ファイルに設定

### 404 Not Found (gpt-image-1)

**原因**: gpt-image-1がサポートされていない

**解決策**:
1. DALL-E 3を使用する（`model: dall-e-3`）
2. Pillowのみを使用する（`use_dalle: false`）

### キャッチコピー生成失敗

**原因**: Claude APIエラー

**解決策**:
- フォールバックで自動的にデフォルトタイトルを使用
- `catchcopy.enabled: false` でキャッチコピー生成を無効化

---

## まとめ

- **推奨**: DALL-E 3 + Pillow + Claude
- **コスト重視**: Pillowのみ
- **高品質**: DALL-E 3 (HD品質)
