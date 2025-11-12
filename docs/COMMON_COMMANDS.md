# よく使うコマンド集

よく使う CLI / スクリプト操作をまとめました。必要に応じて `"グリゴリーラスプーチン"` の部分を他の偉人名に置き換えてください。

---

## 0. 事前準備

```powershell
cd C:\Users\hyokaimen\kyota\video-automation
.\venv\Scripts\activate
```

---

## 1. フェーズ実行関連

### 1-1. Phase1〜8 を一括実行

```powershell
python -m src.cli generate "織田信長"
```

- 既存出力を無視して再実行: `--force`
- 途中フェーズから/まで: `--from-phase 3 --until-phase 7`

### 1-2. 個別フェーズだけ実行

```powershell
python -m src.cli run-phase "織田信長" --phase 2
```

- 既存出力があるときはスキップ: `--skip-if-exists`

### 1-3. Kokoro TTS (Phase2) 用 Docker 起動

```powershell
docker compose -f docker-compose-kokoro.yml up -d
docker ps | findstr kokoro            # 状態確認
docker compose -f docker-compose-kokoro.yml logs -f  # ログ追跡
```

---

## 2. マニュアル台本ワークフロー

### 2-1. 台本テンプレート生成

```powershell
python scripts/create_script_template.py "グリゴリーラスプーチン"
```

テンプレートは `data/input/manual_scripts/` に生成されるので編集する。

### 2-2. YAML を JSON (manual override) へ変換

```powershell
python scripts/convert_manual_script.py "ラスプーチン"
```

生成結果は `data/input/manual_overrides/` に保存され、Phase1 以降で利用される。

---

## 3. ログ / 状態確認

```powershell
# 直近の動画生成ログを見る
Get-Content .\logs\*.log -Tail 50

# プロジェクト状態を CLI で確認
python -m src.cli status "織田信長"
```

---

必要に応じてこのファイルを追記してください。Git で共有しておくとチーム全体で再利用できます。

