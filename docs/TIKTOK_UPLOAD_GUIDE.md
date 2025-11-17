# TikTok自動投稿ガイド

このドキュメントでは、Phase 11のTikTok自動投稿機能の使い方を説明します。

## 概要

Phase 11は、Phase 10で生成された縦型動画を自動的にTikTokに投稿します。

**実装方式:**
- **Selenium + Cookie認証**: Bot検知を回避するため、手動ログイン後のCookieを使用
- **ヘッドレスモード対応**: 検証中は画面表示、本番環境ではヘッドレスモードで実行可能
- **ジャンル別設定**: ジャンルごとに異なるアカウント・ハッシュタグを使用可能

## 初回セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

これにより、以下のパッケージがインストールされます:
- `selenium>=4.15.0`
- `webdriver-manager>=4.0.0`

### 2. TikTokアカウントにログイン

初回のみ、手動でログインしてCookieを保存する必要があります。

```bash
python scripts/tiktok_login.py --cookies config/.tiktok_cookies_ijin.pkl
```

**手順:**
1. ブラウザウィンドウが自動的に開きます
2. TikTokのログインページが表示されます
3. **手動で**メールアドレスとパスワードを入力してログイン
4. 2段階認証やCAPTCHAがある場合は完了させる
5. ログインが完了すると、自動的にCookieが保存されます

**ログイン情報:**
- メールアドレス: `ijin_history@outlook.jp`
- パスワード: `Kyota_0123`

### 3. 設定ファイルの確認

`config/genres/ijin.yaml` にTikTok設定が含まれていることを確認:

```yaml
tiktok:
  cookies_file: "config/.tiktok_cookies_ijin.pkl"
  hashtags:
    - "歴史"
    - "偉人"
    - "解説"
    - "日本史"
```

## 使い方

### Phase 11を単体で実行

```bash
python -m src.phases.phase_11_tiktok レオナルドダヴィンチ --genre ijin
```

**オプション:**
- `--genre ijin`: ジャンルを指定（ijin.yamlの設定を使用）
- `--force`: 既にアップロード済みでも再実行
- `--debug`: デバッグログを有効化

### オーケストレーターから実行

```bash
python -m src.core.orchestrator レオナルドダヴィンチ --start-phase 11 --end-phase 11 --genre ijin
```

## 設定

### Phase 11の設定 (`config/phases/phase_11_tiktok.yaml`)

```yaml
upload:
  max_clips: 5                    # 最大アップロード数
  headless: false                 # ヘッドレスモード（検証中はfalse推奨）
  wait_after_upload: 10           # アップロード後の待機時間（秒）
  wait_between_uploads: 30        # クリップ間の待機時間（秒）
  browser: "chrome"               # 使用するブラウザ

metadata_generation:
  title_template: "{subject} #{clip_number}"
  hashtags:
    - "歴史"
    - "解説"

authentication:
  cookies_file: "config/.tiktok_cookies_default.pkl"

output:
  upload_log: "tiktok_upload_log.json"
```

### ジャンル別設定の優先順位

1. **ジャンル設定** (`config/genres/ijin.yaml`)
   - `tiktok.cookies_file`: ジャンル専用のCookieファイル
   - `tiktok.hashtags`: ジャンル専用のハッシュタグ

2. **Phase設定** (`config/phases/phase_11_tiktok.yaml`)
   - デフォルトの設定

## トラブルシューティング

### Cookieファイルが見つからない

**エラー:**
```
TikTok cookies file not found: config/.tiktok_cookies_ijin.pkl
```

**解決方法:**
```bash
python scripts/tiktok_login.py --cookies config/.tiktok_cookies_ijin.pkl
```

### ログインがタイムアウトする

**エラー:**
```
Login timeout. Please try again.
```

**解決方法:**
- 待機時間を増やす: `--wait-time 600`（10分）
- 2段階認証を事前に無効化しておく
- CAPTCHAが表示された場合は手動で解決する

### アップロードが失敗する

**考えられる原因:**
1. **Cookie有効期限切れ**: 再度ログインスクリプトを実行
2. **Bot検知**: ヘッドレスモードをOFFにして実行
3. **TikTokのUI変更**: 要素セレクタが古い可能性（コード更新が必要）

**デバッグ方法:**
```bash
python -m src.phases.phase_11_tiktok レオナルドダヴィンチ --genre ijin --debug
```

### ヘッドレスモードで動作しない

TikTokはヘッドレスブラウザを検知する可能性があります。

**解決方法:**
1. `config/phases/phase_11_tiktok.yaml` で `headless: false` に設定
2. 検証が完了してから `headless: true` に変更

## 実装の詳細

### アーキテクチャ

```
Phase 11 (phase_11_tiktok.py)
    ↓
TikTokUploader (src/utils/tiktok_uploader.py)
    ↓
Selenium WebDriver
    ↓
TikTok Web UI
```

### Cookie認証の仕組み

1. **初回ログイン**: 手動でログインし、ブラウザのCookieを保存（pickle形式）
2. **自動投稿**: 保存したCookieをSeleniumで読み込み、TikTokに認証済みとして扱われる
3. **セッション維持**: Cookieの有効期限内は再ログイン不要

### Bot検知回避の工夫

- `--disable-blink-features=AutomationControlled`: Selenium検知を無効化
- User-Agent偽装: 通常のChromeブラウザとして振る舞う
- `navigator.webdriver` を `undefined` に設定
- 適度な待機時間を挿入

## よくある質問

### Q: 複数のアカウントを使い分けたい

A: ジャンルごとに異なるCookieファイルを使用できます。

```yaml
# config/genres/ijin.yaml
tiktok:
  cookies_file: "config/.tiktok_cookies_ijin.pkl"

# config/genres/urban.yaml
tiktok:
  cookies_file: "config/.tiktok_cookies_urban.pkl"
```

それぞれのアカウントでログインスクリプトを実行:
```bash
python scripts/tiktok_login.py --cookies config/.tiktok_cookies_ijin.pkl
python scripts/tiktok_login.py --cookies config/.tiktok_cookies_urban.pkl
```

### Q: ハッシュタグをカスタマイズしたい

A: ジャンル設定ファイルで変更できます。

```yaml
# config/genres/ijin.yaml
tiktok:
  hashtags:
    - "歴史"
    - "偉人"
    - "解説"
    - "日本史"
    - "教育"
```

### Q: アップロード数を増やしたい

A: Phase 11の設定で `max_clips` を変更します。

```yaml
# config/phases/phase_11_tiktok.yaml
upload:
  max_clips: 10  # 最大10本までアップロード
```

### Q: 投稿間隔を調整したい

A: `wait_between_uploads` を変更します。

```yaml
upload:
  wait_between_uploads: 60  # 60秒（1分）待機
```

## 注意事項

1. **TikTok利用規約の遵守**: 自動投稿はTikTokの利用規約に違反する可能性があります
2. **投稿頻度**: 短時間に大量投稿するとアカウント停止のリスクがあります
3. **Cookie管理**: Cookieファイルは機密情報なので `.gitignore` に追加してください
4. **UI変更**: TikTokはUIを頻繁に変更するため、要素セレクタの更新が必要になる場合があります

## 参考リンク

- [Selenium公式ドキュメント](https://www.selenium.dev/documentation/)
- [WebDriver Manager](https://github.com/SergeyPirogov/webdriver_manager)
- [TikTok Web版](https://www.tiktok.com/@14nnoahiato)
