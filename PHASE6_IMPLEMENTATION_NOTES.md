# Phase 6 (字幕生成) 実装ガイド

## 質問への回答

### 1. Phase基底クラスの引数

**答え**: `subject`, `config`, `logger` の3つ。`working_dir`は**不要**です。

```python
class Phase06Subtitles(PhaseBase):
    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger: Optional[logging.Logger] = None
    ):
        # PhaseBaseが自動的に以下を設定:
        # - self.working_dir = config.get_working_dir(subject)
        # - self.phase_dir = self.get_phase_directory()
```

**理由**:
- `working_dir`は`ConfigManager`から`get_working_dir(subject)`で取得される
- `phase_dir`も`config.get_phase_dir(subject, phase_number)`で取得される
- PhaseBaseの`__init__`で自動設定されるため、引数として渡す必要はない

### 2. ConfigManagerの初期化方法

**答え**: デフォルトコンストラクタを使用（設定ファイルのパスは自動検出）

```python
from src.core.config_manager import ConfigManager

# 最もシンプルな方法（推奨）
config = ConfigManager()

# または、明示的にパスを指定
config = ConfigManager(
    main_config_path="config/settings.yaml",  # オプション
    env_path="config/.env",  # オプション
    project_root=Path("."),  # オプション（自動検出される）
    env_override=False  # .envがOS環境変数を上書きするか
)
```

**ConfigManagerの動作**:
- プロジェクトルートを自動検出（`config/settings.yaml`または`src/core/config_manager.py`の存在を確認）
- `config/settings.yaml`を読み込む
- `config/.env`があれば環境変数として読み込む
- 各フェーズの設定ファイル（`config/phases/*.yaml`）を自動読み込み

### 3. ロガーの設定方法

**答え**: PhaseBaseが自動設定。手動で設定する場合は`setup_logger`を使用

```python
from src.utils.logger import setup_logger

# PhaseBaseを使う場合（自動設定される）
phase = Phase06Subtitles(
    subject="織田信長",
    config=config,
    logger=None  # Noneの場合は自動生成される
)

# 手動で設定する場合
logger = setup_logger(
    name="phase_06_custom",
    log_dir=config.get_path("logs_dir"),
    level="DEBUG"  # DEBUG, INFO, WARNING, ERROR
)
```

**PhaseBaseのロガー設定**:
- `logger=None`の場合、PhaseBaseが自動的にロガーを生成
- ロガー名: `f"phase_{self.get_phase_number()}_{subject}"`
- ログディレクトリ: `config.get_path("logs_dir")`
- ファイルとコンソールの両方に出力

### 4. 他のPhaseと同じパターンになっているか

**答え**: **はい、同じパターンです**。以下の要素が一致しています:

#### ✅ PhaseBaseの継承パターン
```python
class Phase06Subtitles(PhaseBase):
    def get_phase_number(self) -> int:
        return 6
    
    def get_phase_name(self) -> str:
        return "Subtitle Generation"
    
    def check_inputs_exist(self) -> bool:
        # Phase 1とPhase 2の出力を確認
        ...
    
    def check_outputs_exist(self) -> bool:
        # 字幕ファイルの存在確認
        ...
    
    def execute_phase(self) -> SubtitleGeneration:
        # 実際の処理
        ...
    
    def validate_output(self, output: SubtitleGeneration) -> bool:
        # バリデーション
        ...
```

#### ✅ 入力ファイルの読み込みパターン
```python
# Phase 1の台本を読み込み
script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"

# Phase 2の音声解析を読み込み
audio_analysis_path = self.config.get_phase_dir(self.subject, 2) / "audio_analysis.json"
```

#### ✅ 出力ファイルの保存パターン
```python
# SRTファイルを保存
srt_path = self.phase_dir / "subtitles.srt"

# メタデータを保存
self.save_metadata(metadata, "metadata.json")
```

#### ✅ エラーハンドリングパターン
```python
try:
    # 処理
    ...
except Exception as e:
    raise PhaseExecutionError(
        self.get_phase_number(),
        f"Subtitle generation failed: {e}"
    ) from e
```

---

## 2. 依存関係の確認

### 必要なパッケージ（既にインストール済み）
- ✅ `pydantic`: データモデル検証
- ✅ `pyyaml`: YAML設定ファイル読み込み
- ✅ `python-dotenv`: 環境変数管理

### オプション（MeCab）
- **使用する場合**: `pip install python-mecab` （日本語の形態素解析でより自然な分割）
- **使用しない場合**: 句点・読点による簡易分割を使用（デフォルト）
- **設定**: `config/phases/subtitle_generation.yaml`の`morphological_analysis.use_mecab: false`

---

## 3. Phase 1, 2の出力フォーマット

### script.jsonの構造
```json
{
  "subject": "織田信長",
  "title": "織田信長の生涯",
  "description": "...",
  "sections": [
    {
      "section_id": 0,
      "title": "導入",
      "narration": "こんにちは。今日は織田信長について学びます。",
      "estimated_duration": 15.0,
      "image_keywords": ["織田信長"],
      "atmosphere": "壮大",
      "requires_ai_video": false,
      "bgm_suggestion": "opening"
    }
  ],
  "total_estimated_duration": 900.0,
  "generated_at": "2025-11-03T12:00:00",
  "model_version": "claude-sonnet-4-20250514"
}
```

**キー名**:
- セクションID: `section_id`（整数）
- ナレーション原稿: `narration`（文字列）

### audio_analysis.jsonの構造
```json
{
  "duration": 910.5,
  "sample_rate": 44100,
  "channels": 1,
  "format": "mp3",
  "file_size_mb": 14.2,
  "bit_rate": 128000,
  "codec": "mp3"
}
```

**注意**: `audio_analysis.json`には`segments`配列は含まれません。
セグメント情報は`metadata.json`にあります。

### metadata.json（Phase 2）の構造
```json
{
  "subject": "織田信長",
  "phase": 2,
  "segments": [
    {
      "section_id": 0,
      "audio_path": "sections/section_00.mp3",
      "duration": 15.2,
      "start_time": 0.0
    },
    {
      "section_id": 1,
      "audio_path": "sections/section_01.mp3",
      "duration": 20.5,
      "start_time": 15.2
    }
  ],
  "total_duration": 910.5
}
```

**キー名**:
- セグメント配列: `segments`
- 開始時間: `start_time`（秒、float）
- 長さ: `duration`（秒、float）
- セクションID: `section_id`（整数）

---

## 4. 設定ファイルの配置

### ✅ config/settings.yaml
- プロジェクトルートの`config/settings.yaml`に配置
- `phases`セクションに`"06_subtitles": "config/phases/subtitle_generation.yaml"`が定義されている

### ✅ config/phases/subtitle_generation.yaml
- 既に作成済み
- 以下の設定が含まれている:
  - `max_lines`: 字幕の最大行数（デフォルト: 2）
  - `max_chars_per_line`: 1行あたりの最大文字数（デフォルト: 20）
  - `timing`: タイミング設定（min_display_duration, max_display_duration, lead_time）
  - `morphological_analysis`: 形態素解析設定（use_mecab, break_on）

### パス設定
- `working_dir`: `data/working`
- Phase 6のディレクトリ: `data/working/{subject}/06_subtitles/`

---

## 5. テストデータ

### テストデータの作成方法

**Option 1: Phase 1, 2を実行**
```bash
python -m src.phases.phase_01_script
python -m src.phases.phase_02_audio
```

**Option 2: 手動でテストデータを作成**
```python
# テスト用のscript.jsonとaudio_analysis.jsonを手動で作成
```

### 実際のテスト実行
```python
from src.core.config_manager import ConfigManager
from src.phases.phase_06_subtitles import Phase06Subtitles

config = ConfigManager()
phase = Phase06Subtitles(
    subject="織田信長",
    config=config
)
result = phase.run(skip_if_exists=False)
```

---

## 6. コードのロジック

### 字幕の分割ロジック
1. **文への分割**: 句点（。）、読点（、）、感嘆符（！）、疑問符（？）で文に分割
2. **2行への分割**: 1行あたり最大20文字。読点や句点で自然な位置で分割
3. **タイミング計算**: 各文の文字数に比例して表示時間を割り当て

### タイミング計算のアルゴリズム
```python
# 各文の文字数から時間を按分
sentence_duration = section_duration * (sentence_chars / total_chars)

# 最小・最大表示時間の制約を適用
sentence_duration = max(min_display, min(sentence_duration, max_display))
```

### SRTフォーマットの生成
```python
# フォーマット: HH:MM:SS,mmm
start_str = "00:00:15,200"
end_str = "00:00:18,500"

# 出力例
"""
1
00:00:15,200 --> 00:00:18,500
こんにちは。今日は織田信長について
学びます。

2
00:00:18,500 --> 00:00:22,000
織田信長は1534年に尾張国で
生まれました。
"""
```

---

## 実装の確認チェックリスト

- [x] PhaseBaseを正しく継承
- [x] `get_phase_number()`と`get_phase_name()`を実装
- [x] `check_inputs_exist()`でPhase 1, 2の出力を確認
- [x] `check_outputs_exist()`で字幕ファイルの存在確認
- [x] `execute_phase()`で字幕生成処理を実装
- [x] `validate_output()`でバリデーション
- [x] ConfigManagerから設定を取得
- [x] ロガーを使用（PhaseBaseが自動設定）
- [x] エラーハンドリング（PhaseExecutionError, PhaseValidationError）
- [x] SRTファイルとJSONファイルの出力
- [x] 他のPhaseと同じパターンに従っている

---

## 実行方法

```python
# スタンドアロン実行
python -m src.phases.phase_06_subtitles

# または、CLIから
python -m src.cli run-phase "織田信長" --phase 6
```

