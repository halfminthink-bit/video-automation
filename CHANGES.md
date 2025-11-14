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
