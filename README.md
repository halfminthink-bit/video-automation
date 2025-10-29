# video-automation
# 偉人動画自動生成システム

AIを活用して、歴史上の偉人についての15分解説動画を自動生成するシステムです。

## 🎯 プロジェクト概要

このシステムは、偉人の名前を入力するだけで、以下の8つのフェーズを自動実行し、完成した動画を出力します：

1. **台本生成** - Claude APIで構造化された台本を作成
2. **音声生成** - ElevenLabsでナレーション音声を合成
3. **画像収集** - Pexels/Wikimedia等から関連画像を収集
4. **静止画アニメーション** - MoviePyで画像にズーム/パン効果を付与
5. **AI動画生成** - Kling AIで重要シーンの動画を生成
6. **BGM選択** - セクションの雰囲気に合わせてBGMを配置
7. **字幕生成** - 音声に同期した字幕を作成
8. **動画統合** - 全ての素材を統合し、最終動画を出力

## 🚀 セットアップ

### 1. 必要な環境

- Python 3.9以上
- FFmpeg（MoviePyが使用）
- 十分なディスク容量（1動画あたり約5GB）

### 2. インストール

```bash
# リポジトリをクローン
git clone <your-repo-url>
cd video-automation

# 仮想環境を作成（推奨）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

### 3. FFmpegのインストール

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# https://ffmpeg.org/download.html からダウンロード
```

### 4. API キーの設定

```bash
# .envファイルを作成
cp config/.env.example config/.env

# エディタで.envを開き、APIキーを設定
# CLAUDE_API_KEY=your_actual_key
# ELEVENLABS_API_KEY=your_actual_key
# ...
```

### 5. 設定の確認

```bash
# 設定ファイルを確認・調整
vim config/settings.yaml
```

## 📖 使い方

### 基本的な使用例

```bash
# 1本の動画を生成
python -m src.cli generate "織田信長"

# バッチ生成
python -m src.cli batch data/input/subjects.json
```

### フェーズ指定実行

```bash
# 特定のフェーズのみ実行
python -m src.cli run-phase "織田信長" --phase 1  # 台本のみ

# 特定のフェーズから実行
python -m src.cli generate "織田信長" --from-phase 5

# 既存出力を無視して強制再生成
python -m src.cli generate "織田信長" --force
```

### 状態確認

```bash
# プロジェクト状態確認
python -m src.cli status "織田信長"

# コスト試算
python -m src.cli estimate-cost "織田信長"
```

## 📁 ディレクトリ構造

```
video-automation/
├── config/              # 設定ファイル
│   ├── settings.yaml    # メイン設定
│   └── phases/          # 各フェーズの設定
├── src/                 # ソースコード
│   ├── core/            # コアシステム
│   ├── phases/          # 各フェーズ実装
│   ├── generators/      # API呼び出し
│   ├── processors/      # 動画処理
│   └── utils/           # ユーティリティ
├── data/                # データディレクトリ
│   ├── working/         # 作業ディレクトリ
│   ├── output/          # 完成動画
│   └── cache/           # キャッシュ
├── assets/              # 静的アセット
│   ├── fonts/           # フォント
│   └── bgm/             # BGM音源
└── logs/                # ログファイル
```

## ⚙️ 設定のカスタマイズ

### メイン設定（config/settings.yaml）

```yaml
# 基本設定
execution:
  skip_existing_outputs: true  # 既存出力をスキップ
  max_retries: 3              # API失敗時のリトライ回数

# コスト管理
cost_tracking:
  alert_threshold_jpy: 2000   # 予算超過アラート
```

### フェーズ別設定

各フェーズの設定は `config/phases/` 以下のYAMLファイルで管理：

- `script_generation.yaml` - 台本生成の設定
- `audio_generation.yaml` - 音声合成の設定
- `image_animation.yaml` - アニメーション効果の設定
- ...

詳細は `docs/CONFIGURATION.md` を参照してください。

## 🧪 テスト

```bash
# 全テストを実行
pytest

# カバレッジ付きで実行
pytest --cov=src tests/

# 特定のテストのみ実行
pytest tests/unit/test_script_generator.py
```

## 📊 コスト見積もり

1本の動画生成にかかる概算コスト：

- Claude API（台本生成）: ¥15-30
- ElevenLabs（音声合成）: ¥100-150
- Kling AI（AI動画生成）: ¥200-400
- 画像API: ¥0（無料プラン使用時）

**合計: 約¥315-580 / 1本**

## 🐛 トラブルシューティング

### よくある問題

**Q: MoviePyでエラーが出る**
```bash
# FFmpegのインストールを確認
ffmpeg -version

# パスが通っているか確認
which ffmpeg
```

**Q: APIキーエラー**
```bash
# .envファイルが正しい場所にあるか確認
ls config/.env

# 環境変数が読み込まれているか確認
python -c "from dotenv import load_dotenv; load_dotenv('config/.env'); import os; print(os.getenv('CLAUDE_API_KEY'))"
```

詳細は `docs/TROUBLESHOOTING.md` を参照。

## 📝 ライセンス

MIT License

## 🤝 貢献

Issue・Pull Requestを歓迎します！

## 📧 お問い合わせ

質問や提案がある場合は、Issueを作成してください。

---

**バージョン**: 1.0.0  
**最終更新**: 2025年10月28日