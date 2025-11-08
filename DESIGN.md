# 偉人動画自動生成システム - 詳細設計書 v2.0

**作成日**: 2025年10月28日
**最終更新日**: 2025年11月8日
**対象読者**: 開発者、AI補助ツール
**設計方針**: 変更容易性、デバッグ性、フェーズ独立実行を最優先

## 📋 更新履歴

### v2.0 (2025年11月8日)
- Phase 8 (サムネイル生成) の実装完了を反映
- 日本語フォント対応の詳細を追加
- Whisper対応による字幕タイミング取得機能を追加
- BGM選択の固定3曲構成を反映
- 不要な一時ファイルの削除とプロジェクト構造の整理

### v1.0 (2025年10月28日)
- 初版作成

---

## 📐 設計の基本方針

### 1. 核心原則

#### 1.1 フェーズ独立性（Phase Independence）
```
各生成フェーズは完全に独立して実行可能とする。

理由:
- 台本だけ修正したい
- 音声だけ再生成したい  
- 映像素材だけ差し替えたい
→ これらを個別に実行できる必要がある

実装:
- 各フェーズの入力・出力を明確に定義
- フェーズ間はファイルシステム経由で疎結合
- 前フェーズの出力が存在すれば、そのフェーズをスキップ可能
```

#### 1.2 冪等性（Idempotency）
```
同じ入力で何度実行しても、同じ結果が得られる。

理由:
- デバッグ時に再現性が必須
- 部分的な再実行が安全に行える

実装:
- ランダム性が必要な箇所はシードを記録
- APIレスポンスはキャッシュ
- タイムスタンプ等の可変要素は設定ファイル化
```

#### 1.3 可観測性（Observability）
```
どの処理がどこまで進んでいるか、常に把握可能とする。

理由:
- 2-3時間の長時間処理で進捗不明は不安
- エラー発生箇所の特定が容易になる

実装:
- 各フェーズの進捗を%で表示
- 推定残り時間の表示
- 各処理の詳細ログ（DEBUG, INFO, WARNING, ERROR）
- 処理完了時に統計情報を出力
```

#### 1.4 変更容易性（Changeability）
```
仕様変更や調整が発生しても、影響範囲を最小化する。

理由:
- BGMの音量調整
- 字幕のフォントサイズ変更
- AI動画の配置戦略変更
→ これらが頻繁に発生する

実装:
- 設定値は全て外部化（YAML/JSON）
- ハードコーディング禁止
- プラグイン的な拡張機構
```

---

## 🏗️ システムアーキテクチャ

### 2. 全体構成図

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI / API Gateway                       │
│                   (src/cli.py, src/api.py)                   │
├─────────────────────────────────────────────────────────────┤
│                     Command Dispatcher                       │
│              各フェーズへのルーティングを担当                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Phase Orchestrator                        │
│               (src/core/orchestrator.py)                     │
│                                                               │
│  • 各フェーズの実行順序管理                                    │
│  • スキップ判定（既存出力があればスキップ）                     │
│  • エラーハンドリング（フェーズ単位でリトライ）                 │
│  • 進捗管理・ログ記録                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────┐
        │   Individual Phase Executors        │
        └─────────────────────────────────────┘
                ↓          ↓          ↓
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Phase 1  │  │ Phase 2  │  │ Phase 3  │
    │ 台本生成  │  │ 音声生成  │  │ 画像収集  │
    └──────────┘  └──────────┘  └──────────┘
                ↓          ↓          ↓
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Phase 4  │  │ Phase 5  │  │ Phase 6  │
    │ 静止画    │  │ BGM選択  │  │ 字幕生成  │
    │ アニメ化  │  │         │  │         │
    └──────────┘  └──────────┘  └──────────┘
                ↓          ↓          ↓
                    ┌──────────┐
                    │ Phase 7  │
                    │ 動画統合  │
                    └──────────┘
                ↓          ↓          ↓
    ┌──────────┐
    │ Phase 8  │
    │ サムネイル│
    │ 生成     │
    └──────────┘
                    ↓
        ┌─────────────────────────┐
        │   Final Output          │
        │   • 完成動画 (MP4)      │
        │   • サムネイル (PNG)    │
        │   • メタデータ (JSON)   │
        └─────────────────────────┘
```

### 3. データフロー設計

#### 3.1 ディレクトリ構造（確定版）

```
video-automation/
│
├── config/                              # 設定ファイル（全て外部化）
│   ├── .env                             # APIキー（gitignore）
│   ├── .env.example                     # 環境変数テンプレート
│   ├── settings.yaml                    # システム全体設定
│   ├── phases/                          # フェーズ別設定
│   │   ├── script_generation.yaml       # 台本生成設定
│   │   ├── audio_generation.yaml        # 音声生成設定
│   │   ├── image_animation.yaml         # 静止画アニメ設定
│   │   ├── ai_video_generation.yaml     # AI動画生成設定
│   │   ├── bgm_selection.yaml           # BGM選択設定
│   │   ├── subtitle_generation.yaml     # 字幕生成設定
│   │   └── video_composition.yaml       # 動画統合設定
│   └── templates/                       # テンプレート
│       ├── script_template.yaml         # 台本構造テンプレート
│       └── thumbnail_template.yaml      # サムネイルレイアウト
│
├── data/                                # データディレクトリ
│   ├── input/                           # 入力データ
│   │   ├── subjects.json                # 偉人リスト
│   │   └── manual_overrides/            # 手動調整用
│   │       ├── {subject}_script.json    # 台本の手動修正版
│   │       └── {subject}_images.json    # 画像の手動選択
│   │
│   ├── working/                         # 作業ディレクトリ（中間データ）
│   │   └── {subject}/                   # 偉人ごとのワークスペース
│   │       ├── phase_status.json        # フェーズ実行状態
│   │       ├── 01_script/               # Phase 1出力
│   │       │   ├── script.json          # 構造化台本
│   │       │   ├── metadata.json        # 生成メタデータ
│   │       │   └── script.log           # 処理ログ
│   │       ├── 02_audio/                # Phase 2出力
│   │       │   ├── narration_full.mp3   # 完全版音声
│   │       │   ├── sections/            # セクション別音声
│   │       │   │   ├── section_00.mp3
│   │       │   │   └── ...
│   │       │   └── audio_analysis.json  # 音声解析結果
│   │       ├── 03_images/               # Phase 3出力
│   │       │   ├── collected/           # 収集画像
│   │       │   │   ├── img_001.jpg
│   │       │   │   └── ...
│   │       │   ├── classified.json      # 画像分類結果
│   │       │   └── download_log.json    # ダウンロード履歴
│   │       ├── 04_animated/             # Phase 4出力
│   │       │   ├── animated_001.mp4     # アニメ化動画
│   │       │   └── ...
│   │       ├── 05_bgm/                  # Phase 5出力
│   │       │   ├── selected_tracks.json # 選択されたBGM
│   │       │   └── bgm_timeline.json    # BGM配置情報
│   │       ├── 06_subtitles/            # Phase 6出力
│   │       │   ├── subtitles.srt        # 字幕ファイル
│   │       │   ├── subtitle_timing.json # タイミング情報
│   │       │   └── metadata.json        # 生成メタデータ
│   │       ├── 07_composition/          # Phase 7出力
│   │       │   ├── timeline.json        # 最終タイムライン
│   │       │   └── composition.log      # 合成ログ
│   │       └── 08_thumbnail/            # Phase 8出力
│   │           ├── thumbnails/          # 生成されたサムネイル
│   │           │   └── *.png
│   │           ├── catchcopy_candidates.json  # キャッチコピー候補
│   │           └── metadata.json        # 生成メタデータ
│   │
│   ├── output/                          # 最終出力
│   │   ├── videos/                      # 完成動画
│   │   │   └── {subject}.mp4
│   │   ├── thumbnails/                  # サムネイル
│   │   │   └── {subject}_thumbnail.jpg
│   │   ├── metadata/                    # メタデータ
│   │   │   └── {subject}_metadata.json
│   │   └── reports/                     # 統計レポート
│   │       └── {subject}_report.html
│   │
│   ├── cache/                           # 再利用可能キャッシュ
│   │   ├── api_responses/               # API応答キャッシュ
│   │   │   ├── claude/
│   │   │   ├── elevenlabs/
│   │   │   └── kling_ai/
│   │   ├── downloaded_assets/           # ダウンロード済み素材
│   │   │   ├── images/
│   │   │   ├── bgm/
│   │   │   └── fonts/
│   │   └── models/                      # AIモデルキャッシュ
│   │
│   └── database.db                      # SQLite DB
│
├── src/                                 # ソースコード
│   ├── __init__.py
│   │
│   ├── core/                            # コア機能
│   │   ├── __init__.py
│   │   ├── orchestrator.py              # フェーズ実行管理
│   │   ├── config_manager.py            # 設定管理
│   │   ├── phase_base.py                # 基底Phaseクラス
│   │   ├── models.py                    # データモデル（Pydantic）
│   │   ├── database.py                  # DB操作
│   │   └── exceptions.py                # カスタム例外
│   │
│   ├── phases/                          # 各フェーズ実装
│   │   ├── __init__.py
│   │   ├── phase_01_script.py           # Phase 1: 台本生成
│   │   ├── phase_02_audio.py            # Phase 2: 音声生成
│   │   ├── phase_03_images.py           # Phase 3: 画像収集
│   │   ├── phase_04_animation.py        # Phase 4: 静止画アニメ化
│   │   ├── phase_05_bgm.py              # Phase 5: BGM選択
│   │   ├── phase_06_subtitles.py        # Phase 6: 字幕生成
│   │   ├── phase_07_composition.py      # Phase 7: 動画統合
│   │   └── phase_08_thumbnail.py        # Phase 8: サムネイル生成
│   │
│   ├── generators/                      # 個別生成器（フェーズから呼ばれる）
│   │   ├── __init__.py
│   │   ├── script_generator.py          # Claude API呼び出し
│   │   ├── audio_generator.py           # ElevenLabs呼び出し
│   │   ├── image_collector.py           # 画像API呼び出し
│   │   ├── ai_video_generator.py        # Kling AI呼び出し（未実装）
│   │   ├── subtitle_generator.py        # 字幕生成ロジック
│   │   ├── catchcopy_generator.py       # キャッチコピー生成（Claude）
│   │   ├── gptimage_thumbnail_generator.py  # DALL-E 3サムネイル生成
│   │   └── pillow_thumbnail_generator.py    # Pillowサムネイル生成
│   │
│   ├── processors/                      # 処理ユーティリティ
│   │   ├── __init__.py
│   │   ├── image_animator.py            # MoviePyでの画像アニメ化
│   │   ├── audio_processor.py           # 音声解析・分割
│   │   ├── video_compositor.py          # MoviePyでの動画合成
│   │   ├── bgm_manager.py               # BGM選択・配置ロジック
│   │
│   ├── utils/                           # ユーティリティ
│   │   ├── __init__.py
│   │   ├── logger.py                    # ログ設定
│   │   ├── whisper_timing.py            # Whisperによるタイミング情報取得
│   │   ├── file_handler.py              # ファイル操作
│   │   ├── cache_manager.py             # キャッシュ管理
│   │   ├── progress_tracker.py          # 進捗管理
│   │   ├── validator.py                 # バリデーション
│   │   └── cost_calculator.py           # コスト計算
│   │
│   ├── cli.py                           # CLIエントリポイント
│   └── api.py                           # API（将来的に）
│
├── assets/                              # 静的アセット
│   ├── fonts/                           # フォントファイル
│   │   ├── NotoSansJP-Bold.ttf
│   │   └── YuGothic-Bold.ttc
│   ├── bgm/                             # BGM音源（著作権フリー）
│   │   ├── epic/
│   │   │   ├── epic_01.mp3
│   │   │   └── ...
│   │   ├── calm/
│   │   ├── hopeful/
│   │   └── dramatic/
│   └── templates/                       # 画像テンプレート
│       └── thumbnail_base.psd
│
├── tests/                               # テストコード
│   ├── __init__.py
│   ├── unit/                            # ユニットテスト
│   │   ├── test_script_generator.py
│   │   └── ...
│   ├── integration/                     # 統合テスト
│   │   ├── test_phase_pipeline.py
│   │   └── ...
│   └── fixtures/                        # テストデータ
│       ├── sample_script.json
│       └── sample_images/
│
├── logs/                                # ログファイル
│   ├── YYYYMMDD_HHMMSS_generation.log   # 実行ログ
│   └── errors/                          # エラーログ
│
├── docs/                                # ドキュメント
│   ├── ARCHITECTURE.md                  # 本ドキュメント
│   ├── API_REFERENCE.md                 # API仕様
│   ├── PHASE_DETAILS.md                 # 各フェーズの詳細
│   ├── CONFIGURATION.md                 # 設定ガイド
│   └── TROUBLESHOOTING.md               # トラブルシューティング
│
├── scripts/                             # 補助スクリプト
│   ├── setup.sh                         # 環境セットアップ
│   ├── download_assets.py               # アセットダウンロード
│   └── cleanup.py                       # キャッシュクリーンアップ
│
├── requirements.txt                     # 依存パッケージ
├── pyproject.toml                       # Poetryプロジェクト設定
├── .gitignore
├── README.md
└── DESIGN.md                            # 本ドキュメント
```

#### 3.2 データモデル定義（Pydantic）

```python
# src/core/models.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

# ========================================
# Enum定義
# ========================================

class PhaseStatus(str, Enum):
    """フェーズの実行状態"""
    PENDING = "pending"       # 未実行
    RUNNING = "running"       # 実行中
    COMPLETED = "completed"   # 完了
    FAILED = "failed"         # 失敗
    SKIPPED = "skipped"       # スキップ（既存出力あり）

class AnimationType(str, Enum):
    """静止画アニメーションタイプ"""
    ZOOM_IN = "zoom_in"           # ゆっくりズームイン
    ZOOM_OUT = "zoom_out"         # ゆっくりズームアウト
    PAN_RIGHT = "pan_right"       # 右へパン
    PAN_LEFT = "pan_left"         # 左へパン
    TILT_CORRECT = "tilt_correct" # 傾き補正
    STATIC = "static"             # 静止

class TransitionType(str, Enum):
    """トランジションタイプ"""
    FADE = "fade"                 # フェード
    CROSSFADE = "crossfade"       # クロスフェード
    NONE = "none"                 # トランジションなし

class BGMCategory(str, Enum):
    """BGMカテゴリ"""
    EPIC = "epic"                 # 壮大
    CALM = "calm"                 # 静か
    HOPEFUL = "hopeful"           # 希望
    DRAMATIC = "dramatic"         # ドラマチック
    TRAGIC = "tragic"             # 悲劇的

# ========================================
# Phase 1: 台本生成
# ========================================

class ScriptSection(BaseModel):
    """台本の1セクション"""
    section_id: int
    title: str
    narration: str                    # ナレーション原稿
    estimated_duration: float         # 推定時間（秒）
    image_keywords: List[str]         # 画像検索キーワード
    atmosphere: str                   # セクションの雰囲気（BGM選択用）
    requires_ai_video: bool = False   # AI動画が必要か
    ai_video_prompt: Optional[str] = None  # AI動画用プロンプト
    
class VideoScript(BaseModel):
    """完全な台本"""
    subject: str                      # 偉人名
    title: str                        # 動画タイトル
    description: str                  # 説明文（YouTube用）
    sections: List[ScriptSection]
    total_estimated_duration: float   # 総推定時間
    generated_at: datetime
    model_version: str                # 使用したClaudeモデル

# ========================================
# Phase 2: 音声生成
# ========================================

class AudioSegment(BaseModel):
    """音声セグメント"""
    section_id: int
    audio_path: str                   # MP3ファイルパス
    duration: float                   # 実際の長さ（秒）
    start_time: float = 0             # 開始時間（統合後）

class AudioGeneration(BaseModel):
    """音声生成結果"""
    subject: str
    full_audio_path: str              # 統合版音声
    segments: List[AudioSegment]
    total_duration: float
    generated_at: datetime

# ========================================
# Phase 3: 画像収集
# ========================================

class ImageClassification(str, Enum):
    """画像の分類"""
    PORTRAIT = "portrait"             # 肖像画
    LANDSCAPE = "landscape"           # 風景
    ARCHITECTURE = "architecture"     # 建築物
    DOCUMENT = "document"             # 古文書・資料
    BATTLE = "battle"                 # 戦闘シーン
    DAILY_LIFE = "daily_life"         # 日常風景

class CollectedImage(BaseModel):
    """収集した画像"""
    image_id: str                     # 一意ID
    file_path: str                    # ローカルパス
    source_url: str                   # 元URL
    source: str                       # Pexels, Wikimedia等
    classification: ImageClassification
    keywords: List[str]
    resolution: tuple[int, int]       # (width, height)
    aspect_ratio: float
    quality_score: float              # 品質スコア（0-1）

class ImageCollection(BaseModel):
    """画像収集結果"""
    subject: str
    images: List[CollectedImage]
    collected_at: datetime

# ========================================
# Phase 4: 静止画アニメーション
# ========================================

class AnimatedClip(BaseModel):
    """アニメーション化されたクリップ"""
    clip_id: str
    source_image_id: str              # 元画像ID
    output_path: str                  # 生成動画パス
    animation_type: AnimationType
    duration: float
    resolution: tuple[int, int]
    start_time: float = 0             # タイムライン上の開始時間

class ImageAnimationResult(BaseModel):
    """静止画アニメーション結果"""
    subject: str
    animated_clips: List[AnimatedClip]
    generated_at: datetime

# ========================================
# Phase 5: BGM選択（注：AI動画生成機能は未実装）
# ========================================

class AIVideoClip(BaseModel):
    """AI生成動画クリップ"""
    clip_id: str
    prompt: str                       # 生成プロンプト
    output_path: str
    duration: float
    resolution: tuple[int, int]
    cost_usd: float                   # 生成コスト
    service: str                      # Kling AI等
    start_time: float = 0             # タイムライン上の開始時間

class AIVideoGeneration(BaseModel):
    """AI動画生成結果"""
    subject: str
    clips: List[AIVideoClip]
    total_duration: float
    total_cost_usd: float
    generated_at: datetime

# ========================================
# Phase 5: BGM選択
# ========================================

class BGMTrack(BaseModel):
    """BGM音源"""
    track_id: str
    file_path: str                    # MP3ファイルパス
    category: BGMCategory
    duration: float
    title: str
    artist: Optional[str] = None

class BGMSegment(BaseModel):
    """BGMセグメント（タイムライン上の配置）"""
    track_id: str
    start_time: float                 # 動画内の開始時間
    duration: float                   # 使用時間
    volume: float = 0.3               # 音量（0-1、デフォルト30%）
    fade_in: float = 2.0              # フェードイン時間
    fade_out: float = 2.0             # フェードアウト時間

class BGMSelection(BaseModel):
    """BGM選択結果"""
    subject: str
    segments: List[BGMSegment]
    tracks_used: List[BGMTrack]
    selected_at: datetime

# ========================================
# Phase 6: 字幕生成
# ========================================

class SubtitleEntry(BaseModel):
    """字幕エントリ"""
    index: int
    start_time: float                 # 秒
    end_time: float                   # 秒
    text_line1: str                   # 1行目
    text_line2: str                   # 2行目（空の場合あり）

class SubtitleGeneration(BaseModel):
    """字幕生成結果"""
    subject: str
    subtitles: List[SubtitleEntry]
    srt_path: str                     # SRTファイルパス
    generated_at: datetime

# ========================================
# Phase 7: 動画統合
# ========================================

class TimelineClip(BaseModel):
    """タイムライン上のクリップ"""
    clip_type: str                    # "animated", "ai_video", "static"
    source_path: str
    start_time: float
    duration: float
    transition_in: TransitionType = TransitionType.FADE
    transition_out: TransitionType = TransitionType.FADE
    z_index: int = 0                  # レイヤー順序

class VideoTimeline(BaseModel):
    """最終タイムライン"""
    subject: str
    clips: List[TimelineClip]
    audio_path: str
    bgm_segments: List[BGMSegment]
    subtitles: List[SubtitleEntry]
    total_duration: float
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30

class VideoComposition(BaseModel):
    """動画統合結果"""
    subject: str
    output_video_path: str
    thumbnail_path: str
    metadata_path: str
    timeline: VideoTimeline
    render_time_seconds: float
    file_size_mb: float
    completed_at: datetime

# ========================================
# 全体管理
# ========================================

class PhaseExecution(BaseModel):
    """フェーズ実行情報"""
    phase_number: int
    phase_name: str
    status: PhaseStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    output_paths: List[str] = []

class ProjectStatus(BaseModel):
    """プロジェクト全体の状態"""
    subject: str
    overall_status: PhaseStatus
    phases: List[PhaseExecution]
    created_at: datetime
    updated_at: datetime
    estimated_cost_jpy: float
    actual_cost_jpy: Optional[float] = None

class GenerationReport(BaseModel):
    """生成レポート"""
    subject: str
    success: bool
    total_duration_seconds: float
    cost_breakdown: Dict[str, float]  # {"claude": 15, "elevenlabs": 120, ...}
    total_cost_jpy: float
    output_video_path: str
    output_thumbnail_path: str
    phases_summary: List[PhaseExecution]
    generated_at: datetime
```

---

## 🔄 フェーズ詳細設計

### 4. Phase Base Class（基底クラス）

全てのフェーズはこの基底クラスを継承する。

```python
# src/core/phase_base.py

from abc import ABC, abstractmethod
from typing import Any, Optional
from pathlib import Path
import logging
from datetime import datetime

from .models import PhaseStatus, PhaseExecution
from .config_manager import ConfigManager

class PhaseBase(ABC):
    """
    フェーズ基底クラス
    
    全てのフェーズはこのクラスを継承し、
    以下のメソッドを実装する必要がある。
    """
    
    def __init__(
        self,
        subject: str,
        working_dir: Path,
        config: ConfigManager,
        logger: logging.Logger
    ):
        self.subject = subject
        self.working_dir = working_dir
        self.config = config
        self.logger = logger
        
        # フェーズ固有のディレクトリ
        self.phase_dir = self.get_phase_directory()
        self.phase_dir.mkdir(parents=True, exist_ok=True)
        
        # 実行情報
        self.execution = PhaseExecution(
            phase_number=self.get_phase_number(),
            phase_name=self.get_phase_name(),
            status=PhaseStatus.PENDING
        )
    
    @abstractmethod
    def get_phase_number(self) -> int:
        """フェーズ番号を返す（1-8）"""
        pass
    
    @abstractmethod
    def get_phase_name(self) -> str:
        """フェーズ名を返す"""
        pass
    
    @abstractmethod
    def get_phase_directory(self) -> Path:
        """フェーズのワーキングディレクトリを返す"""
        pass
    
    @abstractmethod
    def check_inputs_exist(self) -> bool:
        """
        前フェーズの出力（このフェーズの入力）が
        存在するかチェック
        """
        pass
    
    @abstractmethod
    def check_outputs_exist(self) -> bool:
        """
        このフェーズの出力が既に存在するかチェック
        （存在すればスキップ可能）
        """
        pass
    
    @abstractmethod
    def execute_phase(self) -> Any:
        """
        フェーズの実際の処理を実行
        
        Returns:
            フェーズの出力データ（Pydanticモデル）
        """
        pass
    
    @abstractmethod
    def validate_output(self, output: Any) -> bool:
        """
        出力データが正しいかバリデーション
        """
        pass
    
    def run(self, skip_if_exists: bool = True) -> PhaseExecution:
        """
        フェーズを実行（共通処理）
        
        Args:
            skip_if_exists: 出力が既に存在する場合スキップするか
            
        Returns:
            PhaseExecution: 実行結果
        """
        self.logger.info(f"=== Phase {self.get_phase_number()}: {self.get_phase_name()} ===")
        
        # 入力チェック
        if not self.check_inputs_exist():
            self.execution.status = PhaseStatus.FAILED
            self.execution.error_message = "Required inputs do not exist"
            self.logger.error(f"Phase {self.get_phase_number()} failed: inputs missing")
            return self.execution
        
        # 既存出力チェック
        if skip_if_exists and self.check_outputs_exist():
            self.execution.status = PhaseStatus.SKIPPED
            self.logger.info(f"Phase {self.get_phase_number()} skipped: outputs already exist")
            return self.execution
        
        # 実行
        try:
            self.execution.status = PhaseStatus.RUNNING
            self.execution.started_at = datetime.now()
            self.logger.info(f"Phase {self.get_phase_number()} started")
            
            # 実際の処理
            output = self.execute_phase()
            
            # バリデーション
            if not self.validate_output(output):
                raise ValueError("Output validation failed")
            
            # 成功
            self.execution.status = PhaseStatus.COMPLETED
            self.execution.completed_at = datetime.now()
            self.execution.duration_seconds = (
                self.execution.completed_at - self.execution.started_at
            ).total_seconds()
            
            self.logger.info(
                f"Phase {self.get_phase_number()} completed "
                f"({self.execution.duration_seconds:.1f}s)"
            )
            
            return self.execution
            
        except Exception as e:
            self.execution.status = PhaseStatus.FAILED
            self.execution.completed_at = datetime.now()
            self.execution.error_message = str(e)
            
            self.logger.error(
                f"Phase {self.get_phase_number()} failed: {e}",
                exc_info=True
            )
            
            return self.execution
```

### 5. 各フェーズの詳細設計

#### Phase 1: 台本生成（Script Generation）

**責務**: Claude APIを使用して構造化された台本を生成

**入力**:
- `subjects.json`: 偉人名リスト
- `config/phases/script_generation.yaml`: 台本生成設定

**処理**:
1. Claude APIにプロンプトを送信
2. JSON形式で台本を受け取る
3. Pydanticモデルでバリデーション
4. 各セクションの推定時間を計算
5. AI動画が必要なシーンを特定

**出力**:
- `working/{subject}/01_script/script.json`: 構造化台本
- `working/{subject}/01_script/metadata.json`: 生成メタデータ

**設定例（config/phases/script_generation.yaml）**:
```yaml
model: "claude-sonnet-4-20250514"
max_tokens: 8000
temperature: 0.7

sections:
  count: 5-7
  target_duration_per_section: 120-180  # 秒

ai_video_trigger_keywords:
  - "戦闘"
  - "決戦"
  - "襲撃"
  - "建設"
  - "革命"

prompt_template: |
  あなたは歴史解説動画の台本作家です。
  {subject}について、15分（約900秒）の動画台本を作成してください。
  
  要件:
  1. 全体を5-7個のセクションに分割
  2. 各セクションは2-3分程度
  3. 高齢者にも分かりやすい言葉遣い
  4. ナレーションは自然な話し言葉
  5. 重要なシーンではAI動画生成が必要か判定
  
  出力形式はJSON: ...
```

**スキップ条件**:
- `working/{subject}/01_script/script.json`が存在する

**エラーハンドリング**:
- Claude API失敗 → 3回リトライ
- JSON パース失敗 → 構造修正を試みる
- バリデーション失敗 → エラーログに詳細記録

---

#### Phase 2: 音声生成（Audio Generation）

**責務**: ElevenLabsを使用してナレーション音声を生成

**入力**:
- `working/{subject}/01_script/script.json`

**処理**:
1. 台本からナレーション原稿を抽出
2. セクションごとにElevenLabs APIで音声生成
3. 生成した音声をpydubで結合
4. 音声解析（実際の長さ、無音部分検出）

**出力**:
- `working/{subject}/02_audio/narration_full.mp3`
- `working/{subject}/02_audio/sections/section_XX.mp3`
- `working/{subject}/02_audio/audio_analysis.json`

**設定例（config/phases/audio_generation.yaml）**:
```yaml
service: "elevenlabs"
voice_id: "21m00Tcm4TlvDq8ikWAM"  # 要調整
model: "eleven_multilingual_v2"

settings:
  stability: 0.5
  similarity_boost: 0.75
  style: 0
  use_speaker_boost: true

format:
  codec: "mp3"
  sample_rate: 44100
  channels: 1  # モノラル

# セクション間の無音時間（秒）
inter_section_silence: 0.5
```

**スキップ条件**:
- `working/{subject}/02_audio/narration_full.mp3`が存在する

**エラーハンドリング**:
- ElevenLabs API失敗 → 5回リトライ（レート制限考慮）
- 音声結合失敗 → pydub設定を調整して再試行

---

#### Phase 3: 画像収集（Image Collection）

**責務**: 台本に基づいて関連画像を収集・分類

**入力**:
- `working/{subject}/01_script/script.json`

**処理**:
1. 各セクションの`image_keywords`を抽出
2. Pexels/Wikimedia/Unsplash APIで画像検索
3. ダウンロード（並列処理で高速化）
4. Claude APIで画像を分類（portrait, landscape等）
5. 品質スコアリング（解像度、アスペクト比等）

**出力**:
- `working/{subject}/03_images/collected/*.jpg`
- `working/{subject}/03_images/classified.json`

**設定例（config/phases/image_collection.yaml）**:
```yaml
sources:
  - name: "pexels"
    api_key_env: "PEXELS_API_KEY"
    per_keyword_limit: 5
    priority: 1
    
  - name: "wikimedia"
    api_key_env: null  # 不要
    per_keyword_limit: 3
    priority: 2
    
  - name: "unsplash"
    api_key_env: "UNSPLASH_API_KEY"
    per_keyword_limit: 3
    priority: 3

target_count_per_section: 3-4

quality_filters:
  min_width: 1920
  min_height: 1080
  aspect_ratio_range: [1.5, 1.9]  # 16:9付近

classification:
  use_claude_api: true
  model: "claude-sonnet-4-20250514"
```

**スキップ条件**:
- `working/{subject}/03_images/classified.json`が存在し、
  十分な枚数の画像が収集されている

**エラーハンドリング**:
- API失敗 → 他のソースにフォールバック
- ダウンロード失敗 → スキップして次へ
- 画像不足 → 警告ログ、最低限の枚数確保

---

#### Phase 4: 静止画アニメーション（Image Animation）

**責務**: 収集した静止画をMoviePyでアニメーション化

**入力**:
- `working/{subject}/03_images/classified.json`
- `working/{subject}/02_audio/audio_analysis.json`

**処理**:
1. 各画像に適したアニメーションタイプを決定
   - 肖像画 → ゆっくりズームイン
   - 風景 → パン
   - 建築物 → ドリー（前進）
2. MoviePyで各画像を動画クリップ化
3. アニメーション効果を適用
4. タイムライン上の配置時間を計算

**出力**:
- `working/{subject}/04_animated/animated_XXX.mp4`
- `working/{subject}/04_animated/animation_plan.json`

**設定例（config/phases/image_animation.yaml）**:
```yaml
default_clip_duration: 8  # 秒

animation_patterns:
  zoom_in:
    zoom_factor: 1.1  # 10%拡大
    duration: 8
    easing: "ease_in_out"
    
  zoom_out:
    zoom_factor: 0.9  # 10%縮小
    duration: 8
    easing: "ease_in_out"
    
  pan_right:
    distance_percent: 10  # 画面幅の10%移動
    duration: 8
    easing: "linear"
    
  pan_left:
    distance_percent: 10
    duration: 8
    easing: "linear"
    
  static:
    duration: 6
    # 完全静止

# 画像分類ごとのデフォルトアニメーション
classification_defaults:
  portrait: "zoom_in"
  landscape: "pan_right"
  architecture: "zoom_in"
  document: "static"
  battle: "zoom_out"

# アニメーションのバリエーション
# 同じタイプが続かないようランダム化
variation_enabled: true
```

**スキップ条件**:
- `working/{subject}/04_animated/animation_plan.json`が存在し、
  全ての動画クリップが生成済み

**エラーハンドリング**:
- MoviePy処理失敗 → その画像はスキップ
- メモリ不足 → 解像度を下げて再試行

---

**注意**: AI動画生成機能は現在未実装です。将来的な拡張として検討されています。

---

#### Phase 5: BGM選択（BGM Selection）

**責務**: 台本のbgm_suggestionに基づいてBGMを選択・配置

**入力**:
- `working/{subject}/01_script/script.json`（bgm_suggestionフィールドを含む）

**処理**:
1. 台本の各セクションの`bgm_suggestion`を読み取る（opening/main/ending）
2. 固定の3曲構成から適切なBGMを選択
   - opening: 導入部のBGM
   - main: 展開～クライマックスのBGM
   - ending: 余韻・締めのBGM
3. タイムライン上の配置を決定
4. BGM切り替え時のクロスフェードを設定
5. フェードイン/アウトのタイミング計算

**出力**:
- `working/{subject}/05_bgm/selected_tracks.json`
- `working/{subject}/05_bgm/bgm_timeline.json`

**設定例（config/phases/bgm_selection.yaml）**:
```yaml
bgm_library_path: "assets/bgm/"

# 固定BGM構造（起承転結対応）
fixed_bgm_structure:
  enabled: true
  tracks:
    opening:
      file: "opening/intro_epic.mp3"
      title: "Epic Introduction"
    main:
      file: "main/dramatic_journey.mp3"
      title: "Dramatic Journey"
    ending:
      file: "ending/peaceful_resolution.mp3"
      title: "Peaceful Resolution"

default_settings:
  volume: 0.3  # ナレーションの30%
  fade_in_duration: 2.0
  fade_out_duration: 2.0

# BGM切り替え時のクロスフェード
transition_between_tracks:
  type: "crossfade"
  duration: 3.0
```

**重要な変更点**:
- 従来の`atmosphere`フィールドではなく、`bgm_suggestion`フィールドを使用
- 台本生成時（Phase 1）に各セクションに`bgm_suggestion`（BGMType: opening/main/ending）が設定される
- 固定の3曲構成により、動画全体で一貫した音楽の流れを作る

**スキップ条件**:
- `working/{subject}/05_bgm/bgm_timeline.json`が存在する

**エラーハンドリング**:
- BGMファイルなし → エラーログを記録、該当セクションをスキップ
- fixed_bgm_structureが無効 → エラーを発生させる（必須設定）

---

#### Phase 6: 字幕生成（Subtitle Generation）

**責務**: 音声に同期した字幕を生成

**入力**:
- `working/{subject}/01_script/script.json`
- `working/{subject}/02_audio/narration_full.mp3`（Whisper使用時）
- `working/{subject}/02_audio/audio_analysis.json`

**処理**:
1. Whisperを使用して音声から単語レベルのタイミング情報を取得（オプション）
2. ナレーション原稿を形態素解析
3. 2行構成になるよう文節で分割
4. Whisperのタイミング情報を使用して表示タイミングを計算
   - タイミング情報が取得できない場合は文字数比率で計算（フォールバック）
5. 各字幕の表示時間を4-6秒確保
6. SRTファイル生成

**出力**:
- `working/{subject}/06_subtitles/subtitles.srt`
- `working/{subject}/06_subtitles/subtitle_timing.json`
- `working/{subject}/06_subtitles/metadata.json`

**設定例（config/phases/subtitle_generation.yaml）**:
```yaml
max_lines: 2  # 最大2行
max_chars_per_line: 20  # 1行あたり最大文字数

timing:
  min_display_duration: 4.0  # 最低表示時間（秒）
  max_display_duration: 6.0  # 最大表示時間（秒）
  lead_time: 0.2  # 音声より少し早く表示（秒）

morphological_analysis:
  use_mecab: false  # MeCabで形態素解析（オプション）
  break_on: ["。", "、", "！", "？"]

# Whisper設定（音声から正確なタイミング情報を取得）
whisper:
  enabled: true  # Whisperを使用してタイミング情報を取得するか
  model: "base"  # Whisperモデル名（tiny, base, small, medium, large）

font:
  family: "Noto Sans JP Bold"
  size: 60  # ピクセル
  color: "#FFFFFF"  # 白
  background_color: "#000000"  # 黒
  background_opacity: 0.7
  position: "bottom"  # 画面下部
  margin_bottom: 80  # 下からのマージン（px）
```

**スキップ条件**:
- `working/{subject}/06_subtitles/subtitles.srt`と`subtitle_timing.json`が存在する

**エラーハンドリング**:
- Whisperのタイミング情報取得失敗 → 文字数比率で計算（フォールバック）
- 形態素解析失敗 → 単純な句点で分割
- タイミング計算エラー → 均等割り当てにフォールバック

**注意事項**:
- Whisperを使用する場合、初回実行時にモデルをダウンロードします（baseモデルで約150MB）
- 処理時間は音声の長さに比例します（約1分の音声で数秒〜数十秒）
- Whisperが利用できない場合は、従来の文字数比率方式に自動的にフォールバックします
- **FP16/FP32の処理**: CPU環境ではFP32を使用し、GPU環境ではFP16を使用します（自動判定）
  - これにより、CPU環境でのFP16警告が解消されます（whisper_timing.py:88-96で実装）

**実装の詳細**:
- `src/utils/whisper_timing.py`: Whisperによる単語レベルのタイミング抽出
- `src/generators/subtitle_generator.py`: Whisperのタイミング情報を使用した字幕生成
- 処理フロー:
  1. 音声ファイル全体からWhisperで単語タイミングを取得
  2. 各セクションの時間範囲に基づいて文のタイミングをマッピング
  3. 文レベルのタイミング情報から字幕エントリを生成
  4. 最小・最大表示時間の制約を適用して重複を防止

---

#### Phase 7: 動画統合（Video Composition）

**責務**: 全ての素材を統合して最終動画を生成

**入力**:
- Phase 1-6の全ての出力
- `working/{subject}/01_script/script.json`（BGM情報取得用）
- `working/{subject}/02_audio/narration_full.mp3`（音声）
- `working/{subject}/04_animated/*.mp4`（アニメ化動画）
- `working/{subject}/06_subtitles/subtitle_timing.json`（字幕）

**処理**:
1. タイムラインの構築
   - アニメ化静止画をループ配置
   - 音声の長さに合わせて動画クリップを調整
2. 音声トラックの統合（ナレーション + BGM）
   - ナレーション音声を読み込み
   - 台本のbgm_suggestionに基づいてBGMを配置
   - BGMセグメントごとにクリップを作成（ループ、音量調整、フェード処理）
   - ナレーションとBGMをCompositeAudioClipでミックス
3. 字幕オーバーレイ
4. トランジション効果の適用
5. MoviePyでレンダリング
6. サムネイル生成
7. メタデータJSON生成

**出力**:
- `output/videos/{subject}.mp4`
- `output/thumbnails/{subject}_thumbnail.jpg`
- `output/metadata/{subject}_metadata.json`

**設定例（config/phases/video_composition.yaml）**:
```yaml
resolution: [1920, 1080]
fps: 30
codec: "libx264"
audio_codec: "aac"
preset: "medium"  # fast, medium, slow
bitrate: "5000k"

transitions:
  default: "fade"
  fade_duration: 1.0

subtitle_style:
  # Phase 6の設定を継承

thumbnail:
  template: "assets/templates/thumbnail_base.psd"
  use_ai_generation: false  # 将来的にDALL-E等を使用可能
  fallback: "first_frame"  # 最初のフレームをサムネに

metadata:
  include_generation_stats: true
  include_cost_breakdown: true
```

**スキップ条件**:
- `output/videos/{subject}.mp4`が存在する

**エラーハンドリング**:
- メモリ不足 → チャンク分割してレンダリング
- レンダリング失敗 → プリセットを"fast"に変更して再試行
- FFmpegエラー → 詳細ログを記録、ユーザーに通知

---

#### Phase 8: サムネイル生成（Thumbnail Generation）

**責務**: 動画用のサムネイルを生成

**入力**:
- `working/{subject}/01_script/script.json`（台本情報）
- `working/{subject}/03_images/classified.json`（画像リスト、Pillow方式の場合）

**処理**:
1. **キャッチコピー生成**（Claude API使用）
   - 台本内容からメインタイトルとサブタイトルを生成
   - 複数候補（デフォルト5個）を生成
   - トーンとターゲット層に応じたキャッチコピーを作成
2. **背景画像生成**（DALL-E 3 / gpt-image-1使用）
   - テーマに基づいた背景画像をAI生成
   - スタイル（dramatic, professional, minimalist, vibrant）を指定可能
   - 1024x1024で生成後、1280x720にリサイズ
3. **テキストオーバーレイ**（Pillow使用）
   - 日本語フォントの読み込み（Windows/Linux/macOS対応）
   - テキストを画面下部に大きく配置
   - 影付きテキストで可読性を向上
   - レイアウト（center, left, right）を選択可能

**出力**:
- `working/{subject}/08_thumbnail/thumbnails/*.png`
- `working/{subject}/08_thumbnail/catchcopy_candidates.json`
- `working/{subject}/08_thumbnail/metadata.json`

**設定例（config/phases/thumbnail_generation.yaml）**:
```yaml
# サムネイル生成方式
use_dalle: true  # DALL-E 3 / gpt-image-1を使用するか

# GPT Image設定（use_dalle: true の場合）
gptimage:
  model: "dall-e-3"  # dall-e-3 または gpt-image-1
  width: 1280
  height: 720
  style: "dramatic"  # dramatic, professional, minimalist, vibrant
  quality: "medium"  # low, medium, high
  layout: "center"  # center, left, right（テキスト配置）

# キャッチコピー生成設定
catchcopy:
  enabled: true
  model: "gpt-4.1-mini"
  tone: "dramatic"  # dramatic, professional, casual, emotional
  target_audience: "一般"  # 一般, 若年層, 高齢者, 専門家
  main_title_length: 20  # メインタイトルの最大文字数
  sub_title_length: 10   # サブタイトルの最大文字数
  num_candidates: 5      # 生成する候補数

# Pillow方式設定（use_dalle: false の場合）
pillow:
  width: 1280
  height: 720
  title_patterns:
    - "{subject}の生涯"
    - "{subject}とは？"
    - "知られざる{subject}"
```

**日本語フォント対応**:
- Windows: MS Gothic, Meiryo, Yu Gothic を自動検出
- Linux: Noto Sans CJK を自動検出
- macOS: ヒラギノ角ゴシックを自動検出
- フォールバック: 日本語フォントが見つからない場合はデフォルトフォント使用

**テキスト配置の特徴**:
- タイトルフォントサイズ: 120px（大きく目立つように）
- サブタイトルフォントサイズ: 60px
- 配置: 画面下部（下から80-100pxのマージン）
- 影: オフセット6px（タイトル）、4px（サブタイトル）で可読性向上
- 半透明の黒いオーバーレイで背景とのコントラストを改善

**スキップ条件**:
- `working/{subject}/08_thumbnail/metadata.json`が存在し、
  サムネイル画像が生成済み

**エラーハンドリング**:
- DALL-E 3 API失敗 → エラーログを記録、処理を中断
- 日本語フォント読み込み失敗 → デフォルトフォントにフォールバック、警告ログ
- Claude API失敗（キャッチコピー生成） → デフォルトタイトル（subject名）を使用
- Pillow処理失敗 → エラーログを記録、処理を中断

**重要な実装ポイント**:
- マルチプラットフォーム対応のフォント検出機構
- DALL-E 3とPillowの組み合わせによる高品質なサムネイル生成
- Claudeによる魅力的なキャッチコピーの自動生成
- 下部配置の大きなテキストで視認性を最大化

---

## 🎛️ 設定管理システム

### 6. 設定ファイルの階層構造

```yaml
# config/settings.yaml（最上位設定）

project:
  name: "historical-figure-video-automation"
  version: "1.0.0"

paths:
  working_dir: "data/working"
  output_dir: "data/output"
  cache_dir: "data/cache"
  assets_dir: "assets"
  logs_dir: "logs"

execution:
  skip_existing_outputs: true  # 既存出力があればスキップ
  parallel_processing: false   # 並列処理（将来実装）
  max_retries: 3              # API失敗時のリトライ回数
  
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  format: "[{levelname}] {asctime} - {name} - {message}"
  to_file: true
  to_console: true

cost_tracking:
  enabled: true
  alert_threshold_jpy: 2000  # 予算超過アラート

# 各フェーズの設定は個別ファイルで管理
phases:
  01_script: "config/phases/script_generation.yaml"
  02_audio: "config/phases/audio_generation.yaml"
  03_images: "config/phases/image_collection.yaml"
  04_animation: "config/phases/image_animation.yaml"
  05_bgm: "config/phases/bgm_selection.yaml"
  06_subtitles: "config/phases/subtitle_generation.yaml"
  07_composition: "config/phases/video_composition.yaml"
  08_thumbnail: "config/phases/thumbnail_generation.yaml"
```

### 7. 設定管理クラス

```python
# src/core/config_manager.py

import yaml
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv
import os

class ConfigManager:
    """
    設定ファイルを階層的に管理するクラス
    
    使用例:
        config = ConfigManager("config/settings.yaml")
        claude_key = config.get_api_key("CLAUDE_API_KEY")
        script_config = config.get_phase_config(1)
    """
    
    def __init__(self, main_config_path: str = "config/settings.yaml"):
        # .envファイル読み込み
        load_dotenv("config/.env")
        
        # メイン設定読み込み
        with open(main_config_path, 'r', encoding='utf-8') as f:
            self.main_config = yaml.safe_load(f)
        
        # 各フェーズの設定を読み込み
        self.phase_configs = {}
        for phase_num, config_path in self.main_config['phases'].items():
            with open(config_path, 'r', encoding='utf-8') as f:
                self.phase_configs[phase_num] = yaml.safe_load(f)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        ドット記法で設定値を取得
        
        例: config.get("execution.skip_existing_outputs")
        """
        keys = key_path.split('.')
        value = self.main_config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_api_key(self, env_var_name: str) -> str:
        """環境変数からAPIキーを取得"""
        key = os.getenv(env_var_name)
        if not key:
            raise ValueError(f"API key not found: {env_var_name}")
        return key
    
    def get_phase_config(self, phase_number: int) -> Dict[str, Any]:
        """フェーズの設定を取得"""
        phase_key = f"{phase_number:02d}_*"
        for key, config in self.phase_configs.items():
            if key.startswith(f"{phase_number:02d}"):
                return config
        raise ValueError(f"Phase {phase_number} config not found")
    
    def update_phase_config(
        self,
        phase_number: int,
        key_path: str,
        value: Any
    ):
        """
        フェーズ設定を動的に更新
        （実行時にパラメータ調整する場合）
        """
        # 実装省略（必要に応じて）
        pass
```

---

## 🔍 デバッグ・監視システム

### 8. ロギングシステム

```python
# src/utils/logger.py

import logging
import sys
from pathlib import Path
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console

def setup_logger(
    name: str,
    log_dir: Path,
    level: str = "INFO",
    to_console: bool = True,
    to_file: bool = True
) -> logging.Logger:
    """
    リッチなロギング設定
    
    - コンソール: Rich形式でカラフル表示
    - ファイル: 詳細なテキストログ
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    logger.handlers = []  # 既存ハンドラをクリア
    
    # フォーマット
    file_format = logging.Formatter(
        "[{levelname}] {asctime} - {name} - {message}",
        style='{',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラ（Rich）
    if to_console:
        console_handler = RichHandler(
            console=Console(stderr=True),
            rich_tracebacks=True,
            tracebacks_show_locals=True
        )
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
    
    # ファイルハンドラ
    if to_file:
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{timestamp}_{name}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # ファイルは全て記録
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger
```

### 9. 進捗トラッカー

```python
# src/utils/progress_tracker.py

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
    TaskID
)
from typing import Optional

class ProgressTracker:
    """
    各フェーズの進捗を視覚的に表示
    
    使用例:
        with ProgressTracker() as tracker:
            task = tracker.add_task("Phase 1: Script", total=100)
            for i in range(100):
                # 処理
                tracker.update(task, advance=1)
    """
    
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        )
        self.tasks = {}
    
    def __enter__(self):
        self.progress.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.progress.__exit__(exc_type, exc_val, exc_tb)
    
    def add_task(self, description: str, total: float) -> TaskID:
        """タスクを追加"""
        task_id = self.progress.add_task(description, total=total)
        self.tasks[description] = task_id
        return task_id
    
    def update(self, task_id: TaskID, advance: float = 1):
        """進捗を更新"""
        self.progress.update(task_id, advance=advance)
    
    def complete(self, task_id: TaskID):
        """タスクを完了状態に"""
        self.progress.update(task_id, completed=True)
```

---

## 🧪 テスト戦略

### 10. テストの構造

```python
# tests/unit/test_script_generator.py

import pytest
from unittest.mock import Mock, patch
from src.generators.script_generator import ScriptGenerator
from src.core.models import VideoScript

@pytest.fixture
def mock_claude_api():
    """Claude APIのモック"""
    with patch('anthropic.Anthropic') as mock:
        # モックレスポンスの設定
        mock_response = Mock()
        mock_response.content = [Mock(text='{"title": "test", ...}')]
        mock.return_value.messages.create.return_value = mock_response
        yield mock

def test_script_generation(mock_claude_api):
    """台本生成の基本テスト"""
    generator = ScriptGenerator(api_key="test_key")
    script = generator.generate("織田信長")
    
    assert isinstance(script, VideoScript)
    assert script.subject == "織田信長"
    assert len(script.sections) > 0
    assert script.total_estimated_duration > 0

def test_script_validation():
    """台本のバリデーションテスト"""
    # 不正なデータでエラーが出るか確認
    with pytest.raises(ValueError):
        VideoScript(
            subject="",  # 空文字はNG
            title="test",
            sections=[]
        )
```

---

## 📝 使用例とコマンド

### 11. CLI使用例

```bash
# ========================================
# 基本的な使用例
# ========================================

# 1本生成（全フェーズ実行）
python -m src.cli generate "織田信良"

# バッチ生成
python -m src.cli batch data/input/subjects.json

# ========================================
# フェーズ指定実行
# ========================================

# 特定のフェーズのみ実行
python -m src.cli run-phase "織田信長" --phase 1  # 台本のみ
python -m src.cli run-phase "織田信長" --phase 2  # 音声のみ

# 特定のフェーズから実行
python -m src.cli generate "織田信長" --from-phase 5  # Phase 5から

# 特定のフェーズまで実行
python -m src.cli generate "織田信長" --until-phase 3  # Phase 3まで

# ========================================
# スキップ制御
# ========================================

# 既存出力を無視して強制再生成
python -m src.cli generate "織田信長" --force

# 特定フェーズのみ再生成
python -m src.cli regenerate "織田信長" --phase 7  # 字幕のみ再生成

# ========================================
# デバッグモード
# ========================================

# 詳細ログ出力
python -m src.cli generate "織田信長" --verbose

# ドライラン（実際の処理はしない）
python -m src.cli generate "織田信長" --dry-run

# ========================================
# 検査・確認コマンド
# ========================================

# プロジェクト状態確認
python -m src.cli status "織田信長"

# 出力例:
# Subject: 織田信長
# Status: Phase 5 / 8
# Progress: ████████░░░░ 62%
# 
# Phase Status:
#   [✓] Phase 1: Script Generation (12.3s)
#   [✓] Phase 2: Audio Generation (45.2s)
#   [✓] Phase 3: Image Collection (23.1s)
#   [✓] Phase 4: Image Animation (156.7s)
#   [✓] Phase 5: BGM Selection (5.2s)
#   [ ] Phase 6: Subtitle Generation
#   [ ] Phase 7: Video Composition

# キャッシュ確認
python -m src.cli cache-info

# コスト試算
python -m src.cli estimate-cost "織田信長"

# ========================================
# ユーティリティコマンド
# ========================================

# キャッシュクリア
python -m src.cli clear-cache "織田信長"
python -m src.cli clear-cache --all

# ログ表示
python -m src.cli logs --date 2025-10-28
python -m src.cli logs --subject "織田信長"

# 統計情報
python -m src.cli stats
python -m src.cli stats --subject "織田信長"
```

---

## 🎯 実装優先度とマイルストーン

### Week 1: 基盤構築
- [ ] Day 1-2: プロジェクト構造作成、設定システム
- [ ] Day 3-4: Phase 1-3（台本、音声、画像）実装
- [ ] Day 5-7: Phase 4（静止画アニメ）実装・テスト

### Week 2: 動画生成
- [ ] Day 1-2: Phase 5（BGM選択）実装
- [ ] Day 3-4: Phase 6（字幕生成）実装
- [ ] Day 5-7: Phase 7（動画統合）実装・テスト

### Week 3: 統合・最適化
- [ ] Day 1-2: エンドツーエンドテスト
- [ ] Day 3-4: エラーハンドリング強化
- [ ] Day 5: ドキュメント作成
- [ ] Day 6-7: バッファ・調整

---

## 💡 設計上の重要な決定事項

### 決定1: フェーズ独立性を最優先
**理由**: デバッグと修正を容易にするため  
**影響**: 各フェーズは完全に疎結合、ファイルシステム経由で通信

### 決定2: 設定の完全外部化
**理由**: コード変更なしでパラメータ調整可能にするため  
**影響**: YAMLファイルで全ての調整可能な値を管理

### 決定3: SQLite + ファイルシステムのハイブリッド
**理由**: シンプルさと拡張性のバランス  
**影響**: 中間データはファイル、メタデータはDB

### 決定4: MoviePyを主力とする
**理由**: Pythonネイティブで制御しやすい  
**影響**: 複雑な編集はFFmpegに頼らずMoviePyで実装

### 決定5: AI動画は最小限に
**理由**: コスト削減  
**影響**: 60秒のみAI生成、残りは静止画アニメ

---

## 📚 参考資料・依存関係

### 主要ライブラリ
- `anthropic`: Claude API
- `elevenlabs`: 音声合成
- `requests`: HTTP通信
- `moviepy`: 動画編集
- `pydantic`: データバリデーション
- `pyyaml`: 設定管理
- `rich`: リッチCLI
- `pytest`: テスト

### ドキュメント
- MoviePy: https://zulko.github.io/moviepy/
- Pydantic: https://docs.pydantic.dev/
- Rich: https://rich.readthedocs.io/

---

## ✅ この設計書の使い方

### 開発者向け
1. 各フェーズの実装時に該当セクションを参照
2. データモデルを見て入出力を確認
3. 設定ファイルのサンプルを参考に実装

### AI補助ツール向け
1. この設計書を全文読み込んで理解
2. 実装時にデータモデルと設定を参照
3. エラーハンドリングの方針に従ってコード生成

### 今後の拡張
- この設計書は生きたドキュメント
- 実装中に判明した変更は随時反映
- バージョン管理で変更履歴を追跡

---

**設計書バージョン**: 1.0.0  
**最終更新日**: 2025年10月28日  
**次回レビュー予定**: 実装開始後1週間