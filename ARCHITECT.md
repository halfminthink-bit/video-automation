# Phase 7: 動画統合 - 設計書

**フェーズ番号**: 7（最終フェーズ）  
**フェーズ名**: Video Composition（動画統合）  
**目的**: 全ての素材を1本の完成動画にまとめる

---

## 📋 概要

Phase 1-6で生成した全ての素材（台本、音声、画像、静止画アニメ、BGM、字幕）を統合し、YouTube等にアップロード可能な最終動画を生成する。

**キーコンセプト**:
- **常に動いている映像** - 静止画は使わず、全て動画クリップでループ
- **音声とのシンクロ** - ナレーションと映像のタイミングを完全一致
- **プロフェッショナルな仕上がり** - トランジション、BGM、字幕で視聴体験を向上

---

## 🎯 処理の流れ

### 1. 入力の読み込み

以下のPhase出力を読み込む：

- **Phase 1**: `data/working/{subject}/01_script/script.json` → 台本構造
- **Phase 2**: 
  - `data/working/{subject}/02_audio/narration_full.mp3` → 完全版ナレーション音声
  - `data/working/{subject}/02_audio/metadata.json` → 音声セグメント情報
  - `data/working/{subject}/02_audio/audio_analysis.json` → 音声解析結果
- **Phase 4**: `data/working/{subject}/04_animated/*.mp4` → 静止画アニメ動画ファイル群
- **Phase 5**: 
  - `data/working/{subject}/05_bgm/bgm_timeline.json` → BGMタイムライン
  - `data/working/{subject}/05_bgm/selected_tracks.json` → 選択されたBGMトラック情報
- **Phase 6**: 
  - `data/working/{subject}/06_subtitles/subtitles.srt` → 字幕ファイル（SRT形式）
  - `data/working/{subject}/06_subtitles/subtitle_timing.json` → 字幕タイミング情報

### 2. タイムライン構築

各セクションの音声の長さに合わせて、映像クリップを配置する。

**配置ルール**:
- **静止画アニメーションのみ使用**（Phase 4の出力）
- 各クリップにトランジション（フェード、クロスフェード）を設定
- 音声より短いクリップは自動的にループ

**注意**: Phase 5（AI動画生成）は削除されているため、静止画アニメーションのみを使用

### 3. 映像トラック作成

MoviePyを使用して動画クリップを結合。

**ループ戦略**:
- 音声より短いクリップは自動的にループ
- ループ接続時は0.5秒のクロスフェードでシームレスに
- 常に動きのある映像を維持

### 4. 音声トラック作成

ナレーションとBGMを混合。

**音声ミックス**:
```
[ナレーション: 100%音量]
        +
[BGM: 30%音量、フェードイン/アウト付き]
        ↓
    [最終音声]
```

**BGM配置**:
- Phase 5で選択されたBGMタイムラインを使用
- セクション境界で2秒のフェードイン/アウト
- BGM切り替え時は3秒のクロスフェード
- BGMがセグメント時間より短い場合、ループ再生

### 5. 字幕の焼き込み

Phase 6で生成されたSRTファイルから字幕を読み込み、動画に重ねる。

**字幕スタイル**（Phase 6の設定を継承）:
- フォント: Noto Sans JP Bold
- サイズ: 60px
- 色: 白文字
- 背景: 黒（透明度70%）
- 位置: 画面下部、下から80pxマージン
- 縁取り: 黒、2px

### 6. レンダリング

最終動画をMP4形式で出力。

**出力設定**:
- 解像度: 1920x1080 (Full HD)
- FPS: 30
- コーデック: H.264 (libx264)
- 音声コーデック: AAC
- ビットレート: 5000k
- プリセット: medium

### 7. サムネイル生成

動画の5秒地点のフレームをサムネイルとして抽出。

**サムネイル仕様**:
- 解像度: 1280x720
- フォーマット: JPEG
- 品質: 90%

### 8. メタデータ保存

動画の詳細情報をJSON形式で保存。

---

## 📂 入力ファイル構造

```
data/working/{subject}/
├── 01_script/
│   └── script.json                    # 台本（Phase 1）
├── 02_audio/
│   ├── narration_full.mp3            # 完全版ナレーション（Phase 2）
│   ├── metadata.json                 # 音声セグメント情報（Phase 2）
│   └── audio_analysis.json           # 音声解析結果（Phase 2）
├── 04_animated/
│   ├── ai_*.mp4                      # 静止画アニメ動画（Phase 4）
│   └── ...                           # 複数の動画ファイル
├── 05_bgm/
│   ├── bgm_timeline.json             # BGMタイムライン（Phase 5）
│   └── selected_tracks.json          # 選択されたBGMトラック（Phase 5）
└── 06_subtitles/
    ├── subtitles.srt                 # SRT字幕（Phase 6）
    └── subtitle_timing.json          # 字幕タイミング情報（Phase 6）
```

---

## 📤 出力ファイル構造

```
data/working/{subject}/07_composition/
├── timeline.json                     # タイムライン情報
├── composition.log                   # 処理ログ
└── metadata.json                     # メタデータ

data/output/
├── videos/
│   └── {subject}.mp4                 # 完成動画
├── thumbnails/
│   └── {subject}_thumbnail.jpg       # サムネイル
└── metadata/
    └── {subject}_metadata.json       # 最終メタデータ
```

---

## 📊 データ構造

### タイムライン構造

```python
timeline = [
    {
        "clip_id": "clip_001",
        "clip_type": "animated",        # "animated"のみ（AI動画は削除）
        "source_path": "path/to/video.mp4",
        "start_time": 0.0,              # タイムライン上の開始時間（秒）
        "duration": 30.0,               # 表示時間（秒）
        "original_duration": 10.0,      # 元の動画の長さ（秒）
        "loop_count": 3,                # ループ回数
        "transition_in": "fade",        # 開始トランジション
        "transition_out": "crossfade",  # 終了トランジション
        "z_index": 0                    # レイヤー順序
    },
    ...
]
```

### BGMタイムライン構造（Phase 5から読み込み）

```python
# Phase 5のbgm_timeline.jsonから読み込む
bgm_timeline = [
    {
        "track_id": "opening",
        "start_time": 0.0,              # 動画内の開始時間
        "duration": 120.0,              # 使用時間
        "volume": 0.3,                  # 音量（0-1）
        "fade_in": 2.0,                 # フェードイン時間
        "fade_out": 2.0                 # フェードアウト時間
    },
    ...
]
```

### 字幕構造（Phase 6から継承）

```python
subtitles = [
    {
        "index": 1,
        "start_time": 0.0,
        "end_time": 4.5,
        "text_line1": "こんにちは。今日は織田信長について",
        "text_line2": "学びます。"
    },
    ...
]
```

---

## 🔧 技術的な実装方針

### クリップのループ処理

**基本方針**: 音声の長さに対して映像が短い場合、シームレスにループ

```
例: 120秒の音声、10秒の静止画アニメ3本の場合

1. 各クリップを40秒ずつ担当
2. 10秒のクリップを4回ループ（40秒に）
3. ループ接続時に0.5秒のクロスフェードでシームレス化
```

**計算式**:
```
必要なループ回数 = ceil(目標時間 / 元の動画の長さ)
各ループ間に0.5秒のクロスフェード
最終的に目標時間にトリミング
```

### BGMのループ処理

**基本方針**: BGMセグメントの時間がBGMファイルの長さより長い場合、ループ再生

```
例: 120秒のBGMセグメント、60秒のBGMファイルの場合

1. BGMファイルを2回ループ
2. 120秒にトリミング
3. フェードイン/アウトを適用
```

### トランジション戦略

**トランジションタイプ**:
- `FADE`: 黒画面を経由（1秒）
- `CROSSFADE`: 前のクリップが薄れながら次が現れる（1秒）
- `NONE`: カット（トランジションなし）

**適用ルール**:
- 同じセクション内: CROSSFADE（滑らか）
- セクション境界: FADE（区切りを明確に）
- 静止画アニメ → 静止画アニメ: CROSSFADE

### 音声ミックス

**ナレーション**:
- Phase 2で生成した`narration_full.mp3`を使用
- 音量: 100%（調整なし）

**BGM**:
- Phase 5で選択されたトラックを使用
- 音量: 30%（ナレーションを邪魔しない）
- フェードイン: 2秒（急に始まらない）
- フェードアウト: 2秒（急に終わらない）
- クロスフェード: 3秒（BGM切り替え時）
- **ループ処理**: セグメント時間がBGMファイルより長い場合、自動ループ

### 字幕の焼き込み

**実装方法**:
1. Phase 6で生成されたSRTファイルを解析
2. 各字幕エントリをTextClipとして生成
3. CompositeVideoClipで動画に重ねる

**注意点**:
- 日本語フォントを明示的に指定（Noto Sans JP Bold）
- 背景の黒ボックスを半透明に
- 画面下部に固定配置
- 2行表示に対応

---

## ⚙️ 設定ファイル仕様

### `config/phases/video_composition.yaml`

```yaml
# 出力設定
output:
  resolution: [1920, 1080]
  fps: 30
  codec: "libx264"
  audio_codec: "aac"
  preset: "medium"          # ultrafast, fast, medium, slow
  bitrate: "5000k"

# クリップループ設定
clip_loop:
  enabled: true
  crossfade_duration: 0.5   # ループ接続時のクロスフェード（秒）
  min_clip_duration: 4.0    # 最小クリップ長（秒）
  max_clip_duration: 30.0   # 最大クリップ長（秒）

# トランジション設定
transitions:
  default: "crossfade"
  fade_duration: 1.0        # フェード時間（秒）
  crossfade_duration: 1.0   # クロスフェード時間（秒）
  
  # セクション境界のトランジション
  section_boundary: "fade"
  
  # クリップタイプ別のトランジション
  animated_to_animated: "crossfade"

# BGM設定
bgm:
  volume: 0.3               # BGM音量（0-1）
  fade_in: 2.0              # フェードイン時間（秒）
  fade_out: 2.0             # フェードアウト時間（秒）
  crossfade: 3.0            # BGM切り替え時のクロスフェード（秒）
  loop_enabled: true         # BGMループを有効化

# 字幕設定（Phase 6の設定を継承）
subtitle:
  font_family: "Noto Sans JP Bold"
  font_size: 60             # ピクセル
  color: "#FFFFFF"          # 白
  background_color: "#000000"   # 黒
  background_opacity: 0.7
  stroke_color: "#000000"
  stroke_width: 2
  position: "bottom"
  margin_bottom: 80         # 下からのマージン（px）
  align: "center"
  method: "caption"         # MoviePyのテキスト描画方法

# サムネイル設定
thumbnail:
  timestamp: 5.0            # 抽出する時間（秒）
  resolution: [1280, 720]
  format: "jpeg"
  quality: 90

# メモリ管理
memory:
  max_clips_in_memory: 10   # 同時にメモリに保持する最大クリップ数
  release_clips: true       # 使用済みクリップを解放

# プログレスバー
progress:
  enabled: true
  show_eta: true            # 推定残り時間を表示
```

---

## 🔄 処理フロー詳細

### ステップ1: 初期化と入力検証

```
1. Phase 1-6の出力ファイルが全て存在するか確認
2. 設定ファイル（video_composition.yaml）を読み込み
3. 出力ディレクトリを作成
4. ロガーを初期化
```

### ステップ2: データ読み込み

```
1. script.json を読み込み（台本構造）
2. metadata.json を読み込み（Phase 2、音声セグメント情報）
3. 静止画アニメファイルのリストを取得（Phase 4: 04_animated/*.mp4）
4. bgm_timeline.json を読み込み（BGM情報、Phase 5）
5. selected_tracks.json を読み込み（BGMトラック情報、Phase 5）
6. subtitles.srt を読み込み（字幕情報、Phase 6）
```

### ステップ3: タイムライン構築

**擬似コード**:
```python
timeline = []
current_time = 0.0

for section in script.sections:
    audio_segment = find_audio_segment(section.section_id)
    target_duration = audio_segment.duration
    
    # 静止画アニメーションのみ使用（AI動画は削除）
    animated_clips = get_animated_clips(section.section_id)
    clip_durations = distribute_duration(target_duration, len(animated_clips))
    
    for i, (clip, duration) in enumerate(zip(animated_clips, clip_durations)):
        loop_count = calculate_loop_count(clip.duration, duration)
        
        timeline.append({
            "clip_type": "animated",
            "source_path": clip.path,
            "start_time": current_time,
            "duration": duration,
            "original_duration": clip.duration,
            "loop_count": loop_count,
            "transition_in": "crossfade" if i > 0 else "fade",
            "transition_out": "crossfade" if i < len(animated_clips)-1 else "fade"
        })
        
        current_time += duration
```

### ステップ4: 映像トラック作成

**MoviePy実装イメージ**:
```python
video_clips = []

for item in timeline:
    clip = VideoFileClip(item["source_path"])
    
    # ループが必要な場合
    if item["loop_count"] > 1:
        loops = [clip]
        for i in range(item["loop_count"] - 1):
            next_clip = clip.copy()
            # クロスフェードで接続
            loops[-1] = loops[-1].crossfadeout(0.5)
            next_clip = next_clip.crossfadein(0.5)
            loops.append(next_clip)
        
        clip = concatenate_videoclips(loops, method="compose")
    
    # 長さを調整
    clip = clip.subclip(0, item["duration"])
    
    # トランジション
    if item["transition_in"] == "fade":
        clip = clip.fadein(1.0)
    elif item["transition_in"] == "crossfade":
        # 前のクリップとのクロスフェードは結合時に処理
        pass
    
    if item["transition_out"] == "fade":
        clip = clip.fadeout(1.0)
    
    video_clips.append(clip)

# 全てを結合
final_video = concatenate_videoclips(video_clips, method="compose")
```

### ステップ5: 音声トラック作成

**MoviePy実装イメージ**:
```python
# ナレーション
narration = AudioFileClip("data/working/{subject}/02_audio/narration_full.mp3")

# BGM（Phase 5から読み込み）
bgm_clips = []
for segment in bgm_timeline:
    bgm = AudioFileClip(segment["track_path"])
    
    # BGMループ処理（セグメント時間がBGMファイルより長い場合）
    if segment["duration"] > bgm.duration:
        loop_count = int(segment["duration"] / bgm.duration) + 1
        bgm = concatenate_audioclips([bgm] * loop_count)
    
    bgm = bgm.subclip(0, segment["duration"])
    bgm = bgm.volumex(segment["volume"])
    bgm = bgm.audio_fadein(segment["fade_in"])
    bgm = bgm.audio_fadeout(segment["fade_out"])
    bgm = bgm.set_start(segment["start_time"])
    bgm_clips.append(bgm)

# 混合
final_audio = CompositeAudioClip([narration] + bgm_clips)

# 動画に音声を設定
final_video = final_video.set_audio(final_audio)
```

### ステップ6: 字幕の焼き込み

**MoviePy実装イメージ**:
```python
subtitle_clips = []

# Phase 6のSRTファイルを読み込み
with open("data/working/{subject}/06_subtitles/subtitles.srt", 'r', encoding='utf-8') as f:
    srt_content = f.read()

# SRTパーサーで解析
subtitles = parse_srt(srt_content)

for sub in subtitles:
    text = sub["text_line1"]
    if sub["text_line2"]:
        text += "\n" + sub["text_line2"]
    
    txt_clip = TextClip(
        text,
        fontsize=60,
        font="Noto-Sans-JP-Bold",
        color='white',
        bg_color='black',
        method='caption',
        size=(1920, None),
        stroke_color='black',
        stroke_width=2
    )
    
    txt_clip = txt_clip.set_start(sub["start_time"])
    txt_clip = txt_clip.set_duration(sub["end_time"] - sub["start_time"])
    txt_clip = txt_clip.set_position(('center', 1080 - 80 - txt_clip.h))
    
    subtitle_clips.append(txt_clip)

# 字幕を動画に重ねる
final_video = CompositeVideoClip([final_video] + subtitle_clips)
```

### ステップ7: レンダリング

**MoviePy実装イメージ**:
```python
output_path = "data/output/videos/{subject}.mp4"

start_time = time.time()

final_video.write_videofile(
    output_path,
    fps=30,
    codec='libx264',
    audio_codec='aac',
    preset='medium',
    bitrate='5000k',
    threads=4,
    logger='bar'  # プログレスバー
)

render_time = time.time() - start_time

# メモリ解放
final_video.close()
for clip in video_clips:
    clip.close()
```

### ステップ8: サムネイル生成

**実装イメージ**:
```python
from PIL import Image

thumbnail_frame = final_video.get_frame(5.0)
thumbnail = Image.fromarray(thumbnail_frame)
thumbnail = thumbnail.resize((1280, 720), Image.LANCZOS)
thumbnail.save("data/output/thumbnails/{subject}_thumbnail.jpg", quality=90)
```

### ステップ9: メタデータ保存

**最終メタデータJSON構造**:
```json
{
  "subject": "織田信長",
  "title": "織田信長 - 天下布武への野望",
  "description": "戦国時代の風雲児、織田信長の生涯を15分で解説",
  "output_video_path": "data/output/videos/織田信長.mp4",
  "thumbnail_path": "data/output/thumbnails/織田信長_thumbnail.jpg",
  "duration_seconds": 840.5,
  "resolution": [1920, 1080],
  "fps": 30,
  "file_size_mb": 125.3,
  "render_time_seconds": 156.2,
  "timeline": {
    "total_clips": 25,
    "animated_clips": 25,
    "total_transitions": 24
  },
  "audio": {
    "narration_duration": 840.5,
    "bgm_tracks_used": 3,
    "total_audio_layers": 4
  },
  "subtitles": {
    "total_entries": 85,
    "average_display_time": 4.8
  },
  "generated_at": "2025-11-03T15:30:00",
  "render_info": {
    "codec": "libx264",
    "preset": "medium",
    "bitrate": "5000k"
  }
}
```

---

## 🎛️ エラーハンドリング

### メモリ不足エラー
```
対処法:
1. max_clips_in_memory を減らす
2. 解像度を一時的に下げる（720pでレンダリング）
3. クリップを分割して処理（チャンク処理）
```

### レンダリング失敗
```
対処法:
1. presetを"fast"に変更して再試行
2. bitrateを下げる（5000k → 3000k）
3. 問題のあるクリップを特定してスキップ
```

### 字幕フォントエラー
```
対処法:
1. システムにNoto Sans JPがインストールされているか確認
2. 代替フォント（Arial Unicode MS）にフォールバック
3. フォントパスを明示的に指定
```

### タイミングのズレ
```
対処法:
1. 音声とタイムラインの合計時間を再計算
2. 微調整（0.1秒単位）
3. 最後のクリップで吸収
```

---

## 📊 パフォーマンス最適化

### メモリ管理
```
- 使用済みクリップは即座にclose()
- 大きなクリップはロード→使用→解放を繰り返す
- CompositeVideoClipは最後にまとめて作成
```

### レンダリング高速化
```
- threads=4 で並列処理
- preset="fast" で速度優先（品質は若干低下）
- 低解像度プレビューを先に生成して確認
```

### ディスク容量管理
```
- 一時ファイルは/tmpに保存
- レンダリング完了後に中間ファイルを削除
- 圧縮設定でファイルサイズを抑える
```

---

## ✅ 出力検証

### バリデーションチェック
```
1. 動画ファイルが存在するか
2. 動画の長さが音声の長さと一致するか（±1秒許容）
3. 解像度が1920x1080か
4. FPSが30か
5. ファイルサイズが妥当か（目安: 1分あたり8-10MB）
6. サムネイルファイルが存在するか
7. メタデータJSONが正しく保存されているか
```

### 品質チェック
```
- 最初の10秒を再生して映像・音声が正常か確認
- 字幕が表示されているか確認
- BGMがナレーションを邪魔していないか確認
- トランジションが自然か確認
```

---

## 🚀 実装の優先度

### Phase 1（必須機能）
- タイムライン構築（ループ処理含む）
- 映像トラック作成
- 音声トラック作成（ナレーション + BGM、ループ処理含む）
- 基本的なレンダリング

### Phase 2（字幕とメタデータ）
- 字幕の焼き込み
- サムネイル生成
- メタデータ保存

### Phase 3（最適化）
- メモリ管理の改善
- エラーハンドリングの強化
- プログレスバーの改善

---

## 📝 実装時の注意点

- **MoviePyのバージョン**: v1.0.3以降を使用
- **ffmpegのインストール**: システムにffmpegが必要
- **日本語フォント**: Noto Sans JPを事前にインストール
- **メモリ**: 16GB以上推奨（15分動画の場合）
- **ディスク容量**: 作業領域として5GB以上確保
- **CPU**: マルチコア推奨（レンダリング時間短縮）

---

## 🎯 成功基準

✅ **全てのクリップが正しく配置されている**  
✅ **音声と映像が完全に同期している**  
✅ **字幕が正しいタイミングで表示される**  
✅ **BGMがナレーションを邪魔していない**  
✅ **トランジションが自然**  
✅ **動画の長さが音声の長さと一致（±1秒）**  
✅ **出力ファイルサイズが妥当（100-150MB for 15分）**  
✅ **レンダリングが5分以内に完了（medium preset）**  
✅ **エラーなく最後まで処理が完了**

---

## 📌 重要な実装詳細

### BGMループ処理の実装

Phase 5で選択されたBGMがセグメント時間より短い場合、自動的にループ再生する必要がある。

```python
# BGMループ処理の例
if segment["duration"] > bgm.duration:
    loop_count = math.ceil(segment["duration"] / bgm.duration)
    bgm_loops = [bgm] * loop_count
    bgm = concatenate_audioclips(bgm_loops)
    bgm = bgm.subclip(0, segment["duration"])
```

### 静止画アニメーションのクリップ分配

各セクションに対応する静止画アニメーションクリップを、セクションの音声時間に合わせて分配する。

```python
def distribute_duration(total_duration, num_clips):
    """全クリップに均等に時間を分配"""
    base_duration = total_duration / num_clips
    return [base_duration] * num_clips
```

### SRTファイルのパーサー

Phase 6で生成されたSRTファイルを解析して、字幕エントリのリストを取得する。

```python
def parse_srt(srt_content):
    """SRTファイルを解析"""
    entries = []
    blocks = srt_content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            index = int(lines[0])
            timecode = lines[1]
            text_lines = '\n'.join(lines[2:])
            
            start_time, end_time = parse_timecode(timecode)
            
            text_parts = text_lines.split('\n', 1)
            line1 = text_parts[0]
            line2 = text_parts[1] if len(text_parts) > 1 else ""
            
            entries.append({
                "index": index,
                "start_time": start_time,
                "end_time": end_time,
                "text_line1": line1,
                "text_line2": line2
            })
    
    return entries
```

---

**この設計書を次のAIに渡してコード実装を依頼してください。**

