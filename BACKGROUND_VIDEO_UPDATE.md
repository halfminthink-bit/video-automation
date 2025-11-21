# 背景動画選択システムの修正

**修正日**: 2025年11月19日  
**コミット**: 7578fa9

---

## 📋 修正概要

背景動画選択システムを**BGMと同じ方式**に変更しました。

### 修正前
- 動画全体の長さから固定比率（15% / 70% / 15%）で分割
- 3つの動画ファイルを直接指定
- フォルダ構造: `assets/background_videos/opening_001.mp4`

### 修正後
- **台本のbgm_suggestionに従って選択**（BGMセレクターと同じ）
- 各カテゴリフォルダから動画をランダム選択
- フォルダ構造: `assets/background_videos/{opening,main,ending}/`

---

## 🔄 変更内容

### 1. BackgroundVideoSelector の修正

**ファイル**: `src/generators/background_video_selector.py`

#### 変更前
```python
def __init__(
    self,
    video_library_path: Path,
    fixed_videos: Dict[str, Dict[str, str]],  # 固定3動画
    timing_ratios: Dict[str, float],          # 比率指定
    ...
):
    ...

def select_videos_for_duration(self, total_duration: float) -> dict:
    # 全体の長さから比率で分割
    opening_duration = total_duration * 0.15
    main_duration = total_duration * 0.70
    ending_duration = total_duration * 0.15
```

#### 変更後
```python
def __init__(
    self,
    video_library_path: Path,
    transition_duration: float = 1.0,
    logger: Optional[logging.Logger] = None,
):
    # 各カテゴリの動画を読み込み
    self.videos = self._load_videos()  # opening/, main/, ending/

def select_videos_for_sections(self, sections: List) -> dict:
    # 台本のbgm_suggestionに従って選択
    for section in sections:
        bgm_type = section.bgm_suggestion.value  # opening/main/ending
        video_path = selected_videos[bgm_type]
        # セクションの長さに合わせて配置
```

---

### 2. Phase 7 V2 の修正

**ファイル**: `src/phases/phase_07_composition_v2.py`

#### 初期化部分
```python
# 変更前
self.bg_selector = BackgroundVideoSelector(
    video_library_path=Path(bg_config["background_video_library_path"]),
    fixed_videos=bg_config["fixed_background_structure"]["videos"],
    timing_ratios=bg_config["timing_ratios"],
    transition_duration=bg_config["transition"].get("duration", 1.0),
    logger=logger
)

# 変更後
self.bg_selector = BackgroundVideoSelector(
    video_library_path=Path(bg_config["background_video_library_path"]),
    transition_duration=bg_config["transition"].get("duration", 1.0),
    logger=logger
)
```

#### 実行部分
```python
# 変更前
bg_selection = self.bg_selector.select_videos_for_duration(audio_duration)

# 変更後
bg_selection = self.bg_selector.select_videos_for_sections(script.sections)
```

---

### 3. 設定ファイルの修正

**ファイル**: `config/phases/background_video.yaml`

#### 変更前
```yaml
background_video_library_path: "assets/background_videos"

fixed_background_structure:
  enabled: true
  videos:
    opening:
      file: "opening_001.mp4"
    main:
      file: "main_001.mp4"
    ending:
      file: "ending_001.mp4"

timing_ratios:
  opening: 0.15
  main: 0.70
  ending: 0.15
```

#### 変更後
```yaml
background_video_library_path: "assets/background_videos"

selection_mode: "script_based"

categories:
  opening:
    description: "オープニング用背景動画"
    usage: "bgm_suggestion: opening のセクションで使用"
  main:
    description: "メインパート用背景動画"
    usage: "bgm_suggestion: main のセクションで使用"
  ending:
    description: "エンディング用背景動画"
    usage: "bgm_suggestion: ending のセクションで使用"
```

---

## 📁 フォルダ構造

### 変更前
```
assets/background_videos/
├── opening_001.mp4
├── main_001.mp4
└── ending_001.mp4
```

### 変更後
```
assets/background_videos/
├── opening/
│   ├── video1.mp4
│   ├── video2.mp4
│   └── ...
├── main/
│   ├── video1.mp4
│   ├── video2.mp4
│   └── ...
└── ending/
    ├── video1.mp4
    ├── video2.mp4
    └── ...
```

---

## 🎯 動作の流れ

### 1. 台本の読み込み
```json
{
  "sections": [
    {
      "section_id": 1,
      "title": "導入",
      "bgm_suggestion": "opening",
      "estimated_duration": 45.0
    },
    {
      "section_id": 2,
      "title": "展開",
      "bgm_suggestion": "main",
      "estimated_duration": 180.0
    },
    {
      "section_id": 3,
      "title": "結末",
      "bgm_suggestion": "ending",
      "estimated_duration": 30.0
    }
  ]
}
```

### 2. 背景動画の選択
```python
# セクション1: opening (45秒)
segment = {
    "track_id": "opening",
    "video_path": "assets/background_videos/opening/video1.mp4",
    "start_time": 0.0,
    "duration": 45.0
}

# セクション2: main (180秒)
segment = {
    "track_id": "main",
    "video_path": "assets/background_videos/main/video1.mp4",
    "start_time": 45.0,
    "duration": 180.0
}

# セクション3: ending (30秒)
segment = {
    "track_id": "ending",
    "video_path": "assets/background_videos/ending/video1.mp4",
    "start_time": 225.0,
    "duration": 30.0
}
```

---

## ✅ メリット

1. **BGMと一貫性がある**
   - BGMと背景動画が同じタイミングで切り替わる
   - 台本の構成に沿った演出が可能

2. **柔軟性が高い**
   - 各カテゴリに複数の動画を配置可能
   - ランダム選択で動画のバリエーションが増える

3. **セクション単位で制御可能**
   - 各セクションの長さに正確に対応
   - 固定比率ではなく、台本の構成に従う

---

## 🚀 使用方法

### 1. 背景動画を配置
```bash
mkdir -p assets/background_videos/{opening,main,ending}

# 各フォルダに動画を配置
cp opening_video.mp4 assets/background_videos/opening/
cp main_video.mp4 assets/background_videos/main/
cp ending_video.mp4 assets/background_videos/ending/
```

### 2. 台本にbgm_suggestionを設定
```yaml
# working/{subject}/01_script/raw_script.yaml
sections:
  - section_id: 1
    title: "導入"
    bgm_suggestion: opening  # ← 背景動画もこれに従う
    narration: |
      ...
```

### 3. 実行
```bash
python -m src.phases.phase_07_composition_v2 "レオナルドダヴィンチ"
```

---

## 📝 注意事項

### 既存の動画ファイルの移動が必要

```bash
# 変更前の構造から変更後の構造へ移動
mkdir -p assets/background_videos/{opening,main,ending}
mv assets/background_videos/opening_001.mp4 assets/background_videos/opening/
mv assets/background_videos/main_001.mp4 assets/background_videos/main/
mv assets/background_videos/ending_001.mp4 assets/background_videos/ending/
```

### 動画の選択はランダム

- 各カテゴリフォルダ内の動画から1つをランダムに選択
- セッション全体で同じ動画を使用（セクションごとに変わらない）

---

## 🔗 関連コミット

- **初回実装**: aafabbb - Phase 1実装
- **今回の修正**: 7578fa9 - Script-based selection

---

**修正完了**: 2025年11月19日
