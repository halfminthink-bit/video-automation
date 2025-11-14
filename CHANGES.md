# ジャンル別設定機能の実装

実装日: 2025-11-14

## 目的

複数のYouTubeチャンネルを運用するため、ジャンル別にプロンプトと設定をカスタマイズ可能にする。

## 変更内容

### 新規ファイル

- `config/genres/ijin.yaml`: 偉人ジャンル設定
- `config/prompts/script/ijin.j2`: 台本プロンプトテンプレート
- `config/prompts/image/ijin.j2`: 画像生成プロンプトテンプレート
- `config/prompts/thumbnail/ijin.j2`: サムネイルプロンプトテンプレート
- `config/variations/audio.yaml`: 音声バリエーション設定
- `config/variations/thumbnail_text.yaml`: テキストレイアウト設定
- `config/variations/thumbnail_style.yaml`: サムネイルスタイル設定

### 修正ファイル

#### `requirements.txt`
- `jinja2>=3.1.0` を追加（プロンプトテンプレート機能用）

#### `src/core/config_manager.py`
- `get_genre_config(genre_name)` メソッドを追加
- `get_variation_config(variation_type)` メソッドを追加
- `load_prompt_template(template_path)` メソッドを追加
- Jinja2環境の初期化処理を追加

#### `src/phases/phase_01_script.py`
- `__init__` に `genre` パラメータを追加
- ジャンル別プロンプトテンプレート対応の準備

#### `src/phases/phase_02_audio.py`
- `__init__` に `audio_var` パラメータを追加
- バリエーション設定の読み込み処理を追加
- `_find_audio_variation()` ヘルパーメソッドを追加
- 音声サービス設定の動的上書き機能を実装

#### `src/phases/phase_03_images.py`
- `__init__` に `genre` パラメータを追加
- ジャンル別プロンプトテンプレートの読み込み処理を追加
- ImageGeneratorへのテンプレート渡し処理を実装

#### `src/phases/phase_08_thumbnail.py`
- `__init__` に `genre`, `text_layout`, `style` パラメータを追加
- `_generate_with_intellectual_curiosity()` にジャンル対応処理を追加
- `_find_layout()` ヘルパーメソッドを追加
- `_find_style()` ヘルパーメソッドを追加
- テキストレイアウトとスタイルのバリエーション読み込み処理を実装

#### `src/cli.py`
- `generate` コマンドに以下のオプションを追加:
  - `--genre`: ジャンル名
  - `--audio-var`: 音声バリエーションID
  - `--text-layout`: テキストレイアウトID
  - `--thumbnail-style`: サムネイルスタイルID
- `run_phase()` 関数のシグネチャを拡張
- `generate_video()` 関数のシグネチャを拡張
- 各フェーズへのパラメータ渡し処理を実装

## 使用方法

### 基本的な使い方

```bash
python -m src.cli generate "徳川家康" --genre ijin
```

### フルオプション指定

```bash
python -m src.cli generate "徳川家康" \
  --genre ijin \
  --audio-var kokoro_standard \
  --text-layout two_line_red_white \
  --thumbnail-style dramatic_side
```

### 特定フェーズのみ実行

```bash
# Phase 2のみ（音声バリエーション指定）
python -m src.cli run-phase "徳川家康" --phase 2 --audio-var kokoro_fast

# Phase 8のみ（サムネイル設定指定）
python -m src.cli run-phase "徳川家康" --phase 8 \
  --genre ijin \
  --text-layout two_line_yellow_black \
  --thumbnail-style bold_front
```

## バリエーション設定一覧

### 音声バリエーション (`audio.yaml`)
- `kokoro_standard`: Kokoro TTS 標準速度
- `kokoro_fast`: Kokoro TTS 高速（1.1倍）
- `kokoro_slow`: Kokoro TTS 低速（0.9倍）
- `elevenlabs_standard`: ElevenLabs 標準設定
- `elevenlabs_expressive`: ElevenLabs 表現力重視

### テキストレイアウト (`thumbnail_text.yaml`)
- `two_line_red_white`: 上赤・下白の2行レイアウト
- `two_line_yellow_black`: 上黄・下黒の2行レイアウト
- `three_zone`: 3ゾーンレイアウト

### サムネイルスタイル (`thumbnail_style.yaml`)
- `dramatic_side`: ドラマチックな横顔構図
- `bold_front`: ボールドな正面構図
- `action_dynamic`: アクション構図

## 互換性

- 既存コマンド（オプション無し）は全て動作を維持
- 新オプションは全てオプショナル（指定なしでも従来通り動作）
- 既存の設定ファイルとの互換性を保持

## 注意事項

- ジャンル設定ファイルが見つからない場合は、既存のデフォルト処理にフォールバック
- バリエーション設定が見つからない場合は、警告ログを出力して既存設定を使用
- フォントファイルは `fonts/` ディレクトリに配置されている前提
- PhaseOrchestrator への完全な統合は今後の改善予定

## 制限事項

- CSV バッチ処理機能は未実装（低優先度のため後回し）
- ImageGenerator と IntellectualCuriosityGenerator 内部でのテンプレート処理は部分実装
- PhaseOrchestrator を使用した generate コマンドでは、新しいパラメータが正しく伝播されない可能性あり（run-phase コマンドでは正常動作）

## 今後の改善予定

- CSVバッチ処理機能の実装
- ImageGenerator/IntellectualCuriosityGenerator の完全なテンプレート対応
- PhaseOrchestrator への新パラメータの完全統合
- より柔軟なバリエーション設定の追加

---

# 追加修正（2025-11-14）

## 目的

ジャンル別設定機能の完成度を高めるため、以下の3つの機能を追加実装：
1. Phase 01のジャンル指定時にYAML→JSON変換フローを統合
2. Phase 02でElevenLabs使用時のひらがな変換処理を追加
3. プロンプトテンプレートに`thumbnail:`ブロック生成指示を追加

## 変更内容

### Phase 01 の改善

#### `src/phases/phase_01_script.py`
- **YAML→JSON変換フローの統合**
  - ジャンル指定時も `phase_01_auto_script.py` と同じフローを使用
  - `_execute_genre_generation()` メソッドを追加
  - `_call_claude_api_for_yaml()` メソッドを追加
  - `_save_yaml_to_manual_scripts()` メソッドを追加
  - `_save_script_as_json()` メソッドを追加
  - `_convert_yaml_dict_to_model()` メソッドを追加
  - YAMLファイルが `data/input/manual_scripts/` に保存されるように改善
  - ScriptNormalizerを使用した正規化処理を統合

**改善効果:**
- ジャンル指定時も手動台本と同じYAMLフォーマットで保存されるため、後から編集可能
- phase_01_auto_script.pyと同じ品質の正規化処理を適用
- デバッグが容易（YAML→JSON変換の中間ファイルが残る）

### Phase 02 の機能追加

#### `src/phases/phase_02_audio.py`
- **ElevenLabs使用時のひらがな変換処理を実装**
  - サービス判定処理を追加（line 102-105）
  - `_convert_script_to_hiragana()` メソッドを追加
  - `_convert_to_hiragana_via_claude()` メソッドを追加
  - Claude APIを使用した高精度なひらがな変換
  - セクションマーカー `[Section N]` で分割して台本に再適用
  - エラー時は元のテキストを使用（フォールバック処理）

**重要ポイント:**
- ElevenLabsは日本語の漢字をうまく発音できないため、全テキストをひらがなに変換
- Kokoro TTS使用時は変換不要（漢字のまま正しく発音可能）
- `audio_timing.json` の `tts_text` フィールドには既にひらがな対応済み（line 581）

### プロンプトテンプレートの改善

#### `config/prompts/script/ijin.j2`
- **`thumbnail:` ブロック生成指示を追加**
  - サムネイル用テキストの詳細な説明を追加
  - `upper_text` のキャッチコピー例を具体化
    - 例: "天下統一の野望", "革命の火種", "世界を変えた男"
  - 改行方法（`\\n`）を明記
  - YAML出力形式の完全なサンプルを追加
  - セクション構成の詳細な説明を追加

**改善効果:**
- Claude APIが必ず `thumbnail:` ブロックを含むYAMLを生成
- キャッチコピーの品質が向上（具体例による誘導）
- 改行指定が正しく行われる

## 使用例

### ジャンル指定でYAML生成
```bash
python -m src.cli generate "徳川家康" --genre ijin
```

**期待される動作:**
- ✓ `data/input/manual_scripts/徳川家康.yaml` が生成される
- ✓ `data/working/徳川家康/01_script/script.json` が生成される
- ✓ `script.json` に `thumbnail: { upper_text, lower_text }` が含まれる

### ElevenLabsでひらがな変換を使用
```bash
python -m src.cli generate "徳川家康" \
  --genre ijin \
  --audio-var elevenlabs_standard
```

**期待される動作:**
- ✓ `data/working/徳川家康/02_audio/audio_timing.json` が生成される
- ✓ `audio_timing.json` の `tts_text` がひらがなになっている
- ✓ 音声ファイルの発音が自然

### Kokoro TTS使用（変換なし）
```bash
python -m src.cli generate "徳川家康" \
  --genre ijin \
  --audio-var kokoro_standard
```

**期待される動作:**
- ✓ ひらがな変換はスキップされる（漢字のまま）
- ✓ Kokoroが漢字を正しく発音

## 技術詳細

### Phase 01: YAML→JSON変換フロー

1. **Claude APIでYAML生成**
   - Jinja2テンプレート（`ijin.j2`）を読み込み
   - `subject` 変数をレンダリング
   - Claude API（claude-sonnet-4）でYAML生成

2. **YAMLを保存**
   - `data/input/manual_scripts/{subject}.yaml` に保存
   - 後から手動編集可能

3. **YAML→JSON変換**
   - ScriptNormalizerで正規化
     - ナレーションの空行削除
     - 文末チェック（。、！、」。の補完）
     - サムネイルテキストの正規化
   - JSON形式に変換
   - `data/working/{subject}/01_script/script.json` に保存

### Phase 02: ひらがな変換フロー

1. **サービス判定**
   - `phase_config["service"]` を確認
   - ElevenLabsの場合のみ変換を実行

2. **台本全体を結合**
   - 全セクションのナレーションを結合
   - セクションマーカー `[Section {section_id}]` で区切る

3. **Claude APIでひらがな変換**
   - 漢字、カタカナをすべてひらがなに変換
   - 句読点、改行、マーカーは保持
   - 数字も「いち」「に」「さん」などに変換

4. **セクションごとに分割**
   - マーカーで分割してセクションに戻す
   - 各セクションの `narration` を更新

5. **audio_timing.jsonに保存**
   - `tts_text` フィールドにひらがなテキストを保存
   - `text` フィールドには元のテキストを保持（後方互換性）

## 互換性

- 既存のコマンドは全て動作を維持
- ジャンル指定なしの場合は従来通りの動作
- ElevenLabs以外のサービス使用時はひらがな変換をスキップ
- エラー時は元のテキストを使用（フォールバック処理）

## テスト済み項目

- [x] ジャンル指定時のYAML生成
- [x] YAML→JSON変換の正常動作
- [x] `thumbnail:` ブロックの生成
- [x] ElevenLabs使用時のひらがな変換
- [x] Kokoro使用時の変換スキップ
- [x] エラー時のフォールバック処理
