# pydantic models
"""
データモデル定義

全てのデータ構造をPydanticモデルで定義。
各フェーズの入出力、設定、状態管理に使用。
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Tuple
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


class ImageClassification(str, Enum):
    """画像の分類"""
    PORTRAIT = "portrait"             # 肖像画
    LANDSCAPE = "landscape"           # 風景
    ARCHITECTURE = "architecture"     # 建築物
    DOCUMENT = "document"             # 古文書・資料
    BATTLE = "battle"                 # 戦闘シーン
    DAILY_LIFE = "daily_life"         # 日常風景


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

    @field_validator('estimated_duration')
    @classmethod
    def validate_duration(cls, v):
        if v <= 0:
            raise ValueError('estimated_duration must be positive')
        return v


class VideoScript(BaseModel):
    """完全な台本"""
    subject: str                      # 偉人名
    title: str                        # 動画タイトル
    description: str                  # 説明文（YouTube用）
    sections: List[ScriptSection]
    total_estimated_duration: float   # 総推定時間
    generated_at: datetime = Field(default_factory=datetime.now)
    model_version: str = "claude-sonnet-4-20250514"  # 使用したClaudeモデル

    @field_validator('sections')
    @classmethod
    def validate_sections(cls, v):
        if len(v) == 0:
            raise ValueError('sections cannot be empty')
        return v


# ========================================
# Phase 2: 音声生成
# ========================================

class AudioSegment(BaseModel):
    """音声セグメント"""
    section_id: int
    audio_path: str                   # MP3ファイルパス
    duration: float                   # 実際の長さ（秒）
    start_time: float = 0             # 開始時間（統合後）

    @field_validator('duration')
    @classmethod
    def validate_duration(cls, v):
        if v <= 0:
            raise ValueError('duration must be positive')
        return v


class AudioGeneration(BaseModel):
    """音声生成結果"""
    subject: str
    full_audio_path: str              # 統合版音声
    segments: List[AudioSegment]
    total_duration: float
    generated_at: datetime = Field(default_factory=datetime.now)


# ========================================
# Phase 3: 画像収集
# ========================================

class CollectedImage(BaseModel):
    """収集した画像"""
    image_id: str                     # 一意ID
    file_path: str                    # ローカルパス
    source_url: str                   # 元URL
    source: str                       # Pexels, Wikimedia等
    classification: ImageClassification
    keywords: List[str]
    resolution: Tuple[int, int]       # (width, height)
    aspect_ratio: float
    quality_score: float              # 品質スコア（0-1）

    @field_validator('quality_score')
    @classmethod
    def validate_quality(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('quality_score must be between 0 and 1')
        return v


class ImageCollection(BaseModel):
    """画像収集結果"""
    subject: str
    images: List[CollectedImage]
    collected_at: datetime = Field(default_factory=datetime.now)


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
    resolution: Tuple[int, int]
    start_time: float = 0             # タイムライン上の開始時間


class ImageAnimationResult(BaseModel):
    """静止画アニメーション結果"""
    subject: str
    animated_clips: List[AnimatedClip]
    generated_at: datetime = Field(default_factory=datetime.now)


# ========================================
# Phase 5: AI動画生成
# ========================================

class AIVideoClip(BaseModel):
    """AI生成動画クリップ"""
    clip_id: str
    prompt: str                       # 生成プロンプト
    output_path: str
    duration: float
    resolution: Tuple[int, int]
    cost_usd: float                   # 生成コスト
    service: str = "kling_ai"         # Kling AI等
    start_time: float = 0             # タイムライン上の開始時間


class AIVideoGeneration(BaseModel):
    """AI動画生成結果"""
    subject: str
    clips: List[AIVideoClip]
    total_duration: float
    total_cost_usd: float
    generated_at: datetime = Field(default_factory=datetime.now)


# ========================================
# Phase 6: BGM選択
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

    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('volume must be between 0 and 1')
        return v


class BGMSelection(BaseModel):
    """BGM選択結果"""
    subject: str
    segments: List[BGMSegment]
    tracks_used: List[BGMTrack]
    selected_at: datetime = Field(default_factory=datetime.now)


# ========================================
# Phase 7: 字幕生成
# ========================================

class SubtitleEntry(BaseModel):
    """字幕エントリ"""
    index: int
    start_time: float                 # 秒
    end_time: float                   # 秒
    text_line1: str                   # 1行目
    text_line2: str = ""              # 2行目（空の場合あり）

    @field_validator('end_time')
    @classmethod
    def validate_end_time(cls, v, info):
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v


class SubtitleGeneration(BaseModel):
    """字幕生成結果"""
    subject: str
    subtitles: List[SubtitleEntry]
    srt_path: str                     # SRTファイルパス
    generated_at: datetime = Field(default_factory=datetime.now)


# ========================================
# Phase 8: 動画統合
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
    resolution: Tuple[int, int] = (1920, 1080)
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
    completed_at: datetime = Field(default_factory=datetime.now)


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
    output_paths: List[str] = Field(default_factory=list)

    @field_validator('phase_number')
    @classmethod
    def validate_phase_number(cls, v):
        if not 1 <= v <= 8:
            raise ValueError('phase_number must be between 1 and 8')
        return v


class ProjectStatus(BaseModel):
    """プロジェクト全体の状態"""
    subject: str
    overall_status: PhaseStatus
    phases: List[PhaseExecution]
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    estimated_cost_jpy: float = 0.0
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
    generated_at: datetime = Field(default_factory=datetime.now)