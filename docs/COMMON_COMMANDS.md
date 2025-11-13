# よく使うコマンド集

よく使う CLI / スクリプト操作をまとめました。必要に応じて `"織田信長"` の部分を他の偉人名に置き換えてください。

---

## 0. 事前準備

```powershell
cd C:\Users\hyokaimen\kyota\video-automation
.\venv\Scripts\activate
```

---

## 1. 動画生成（全フェーズ一括実行）

### 1-1. 通常の動画生成（Phase 1-9）

```powershell
# 基本的な実行（既存出力がある場合はスキップ）
python -m src.cli generate "織田信長"

# 既存出力を無視して強制再実行
python -m src.cli generate "織田信長" --force

# 指定フェーズから実行
python -m src.cli generate "ニコラ・テスラ" --from-phase 3

# 指定フェーズまで実行
python -m src.cli generate "織田信長" --until-phase 7

# フェーズ範囲を指定（Phase 3-7のみ実行）
python -m src.cli generate "織田信長" --from-phase 3 --until-phase 7
```

### 1-2. 自動台本生成を使用（--auto）

```powershell
# 自動台本生成 + 全フェーズ実行（Phase 1-9）
python -m src.cli generate "織田信長" --auto

# 自動台本生成のみ（Phase 1のみ実行）
python -m src.cli generate "織田信長" --auto --until-phase 1

# 自動台本生成後、Phase 2以降を実行
python -m src.cli generate "織田信長" --auto --from-phase 2
```

### 1-3. 手動台本を使用（--manual）

```powershell
# 手動台本を変換してから全フェーズ実行
python -m src.cli generate "織田信長" --manual

# 手動台本変換のみ（Phase 1のみ実行）
python -m src.cli generate "織田信長" --manual --until-phase 1
```

**注意**: `--auto` と `--manual` は同時に指定できません。

---

## 2. 個別フェーズ実行

### 2-1. 基本的な個別フェーズ実行

```powershell
# Phase 1: 台本生成
python -m src.cli run-phase "マリー・キュリー" --phase 1

# Phase 2: 音声生成（Kokoro TTS）
python -m src.cli run-phase "織田信長" --phase 2

# Phase 3: 画像生成
python -m src.cli run-phase "ニコラ・テスラ" --phase 3

# Phase 4: 画像アニメーション
python -m src.cli run-phase "織田信長" --phase 4

# Phase 5: BGM選択
python -m src.cli run-phase "織田信長" --phase 5

# Phase 6: 字幕生成
python -m src.cli run-phase "織田信長" --phase 6

# Phase 7: 動画合成
python -m src.cli run-phase "織田信長" --phase 7

# Phase 8: サムネイル生成
python -m src.cli run-phase "織田信長" --phase 8

# Phase 9: YouTubeアップロード
python -m src.cli run-phase "織田信長" --phase 9
```

### 2-2. 自動台本生成を使用（Phase 1のみ）

```powershell
# Phase 1で自動台本生成を使用
python -m src.cli run-phase "織田信長" --phase 1 --auto
```

### 2-3. 既存出力がある場合はスキップ

```powershell
# 既に出力がある場合はスキップ
python -m src.cli run-phase "織田信長" --phase 2 --skip-if-exists
```

---

## 3. 手動台本ワークフロー

### 3-1. 台本テンプレート生成

```powershell
python scripts/create_script_template.py "田中"
```

テンプレートは `data/input/manual_scripts/` に生成されるので編集する。

### 3-2. YAML を JSON (manual override) へ変換

```powershell
# 単一ファイルを変換
python scripts/convert_manual_script.py "ニコラテスラ"

# 全てのYAMLファイルを変換
python scripts/convert_manual_script.py --all
```

生成結果は `data/input/manual_overrides/` に保存され、Phase1 以降で利用される。

**変換時の自動正規化**:
- 空行の削除
- 文末の「。」追加（。！以外で終わる場合）
- 連続改行（\n\n）の正規化
- サムネイルテキストの整形

---

## 4. Kokoro TTS (Phase 2) 用 Docker 起動

```powershell
# Dockerコンテナを起動
docker compose -f docker-compose-kokoro.yml up -d

# 状態確認
docker ps | findstr kokoro

# ログ追跡
docker compose -f docker-compose-kokoro.yml logs -f

# 停止
docker compose -f docker-compose-kokoro.yml down
```

---

## 5. ログ / 状態確認

```powershell
# 直近の動画生成ログを見る
Get-Content .\logs\*.log -Tail 50

# プロジェクト状態を CLI で確認
python -m src.cli status "織田信長"
```

---

## 6. よくある使用パターン

### パターン1: 自動台本で新規動画を作成

```powershell
# 1. 自動台本生成（Phase 1）
python -m src.cli generate "織田信長" --auto --until-phase 1

# 2. 生成された台本を確認・編集（必要に応じて）
# data/working/織田信長/script.json を確認

# 3. 残りのフェーズを実行
python -m src.cli generate "織田信長" --from-phase 2
```

### パターン2: 手動台本で動画を作成

```powershell
# 1. テンプレート生成
python scripts/create_script_template.py "田中"

# 2. YAMLファイルを編集
# data/input/manual_scripts/田中.yaml を編集

# 3. JSONに変換
python scripts/convert_manual_script.py "田中"

# 4. 動画生成
python -m src.cli generate "田中" --manual
```

### パターン3: 特定フェーズのみ再実行

```powershell
# Phase 3（画像生成）のみ再実行
python -m src.cli run-phase "織田信長" --phase 3 --skip-if-exists

# Phase 6-7（字幕と動画合成）のみ再実行
python -m src.cli generate "織田信長" --from-phase 6 --until-phase 7
```

---

## 7. トラブルシューティング

### エラーが発生した場合

1. ログを確認
   ```powershell
   Get-Content .\logs\*.log -Tail 100
   ```

2. エラーログファイルを確認
   - `logs/error_*.txt` に詳細なエラー情報が保存されます

3. 特定フェーズのみ再実行
   ```powershell
   python -m src.cli run-phase "織田信長" --phase <フェーズ番号> --skip-if-exists
   ```

---

必要に応じてこのファイルを追記してください。Git で共有しておくとチーム全体で再利用できます。
