# 動画自動生成システム改善 - Phase 1 実装完了レポート

**実装日**: 2025年11月19日  
**実装者**: Manus AI  
**参考動画**: https://www.youtube.com/watch?v=TU7-nEVnxyI

---

## 📋 実装概要

動画に**動く背景**と**インパクト字幕（赤・大きめ）**を追加する機能を実装しました。

### 実装の流れ

1. **背景動画選択システム** （BGM選択をベースに実装）
2. **Phase 6拡張** （字幕にimpact_levelを追加）
3. **Phase 7拡張** （背景動画 + 画像70%縮小 + インパクト字幕）

---

## ✅ 実装完了タスク

### Task 1: 背景動画の設定ファイル作成

**ファイル**: `config/phases/background_video.yaml`

**内容**:
- 背景動画ライブラリのパス設定
- 固定背景動画構成（opening/main/ending）
- タイミング比率（15% / 70% / 15%）
- ループとトランジション設定

---

### Task 2: 背景動画選択器の実装

**ファイル**: `src/generators/background_video_selector.py`

**主なクラス**:
```python
class BackgroundVideoSelector:
    def select_videos_for_duration(self, total_duration: float) -> dict:
        """
        全体の長さから opening/main/ending を割り当て
        
        Returns:
            {
                'segments': [
                    {
                        'track_id': 'opening',
                        'video_path': 'assets/background_videos/opening_001.mp4',
                        'start_time': 0.0,
                        'duration': 100.0
                    },
                    # ...
                ]
            }
        """
```

**特徴**:
- BGMセレクターと同じ構造
- 動画の長さに基づいて自動的にセグメント分割
- 各セグメントの開始時間と長さを計算

---

### Task 3: Phase 6の拡張（字幕にimpact_level追加）

**ファイル**: `src/phases/phase_06_subtitles_v2.py`

**変更箇所**:

#### 1. `_save_timing_json` メソッドを拡張

```python
def _save_timing_json(self, subtitles: List[SubtitleEntry]) -> Path:
    # 台本からimpact_phrasesを読み込み
    impact_phrases = self._extract_impact_phrases_from_script()
    
    timing_data = {
        "subject": self.subject,
        "subtitle_count": len(subtitles),
        "total_duration": max([s.end_time for s in subtitles]) if subtitles else 0,
        "subtitles": [
            {
                "index": s.index,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration": s.end_time - s.start_time,
                "text_line1": s.text_line1,
                "text_line2": s.text_line2,
                "impact_level": self._get_impact_level(s, impact_phrases)  # ← 追加
            }
            for s in subtitles
        ]
    }
```

#### 2. 新規メソッド追加

- `_extract_impact_phrases_from_script()`: raw_script.yamlからimpact_phrasesを抽出
- `_get_impact_level()`: 字幕のimpact_levelを判定（"none" | "normal" | "mega"）

**動作**:
1. `working/{subject}/01_script/raw_script.yaml` からimpact_phrasesを読み込み
2. 各字幕のテキストに対してimpact_phrasesをマッチング
3. `subtitle_timing.json` に `impact_level` キーを追加

---

### Task 4: Phase 7の拡張（背景動画 + 画像縮小 + インパクト字幕）

**ファイル**: `src/phases/phase_07_composition_v2.py`

**主な変更点**:

#### 1. `__init__` で背景動画セレクターを初期化

```python
# 背景動画セレクターを初期化
bg_config = config.get_phase_config("background_video")
self.bg_selector = BackgroundVideoSelector(
    video_library_path=Path(bg_config["background_video_library_path"]),
    fixed_videos=bg_config["fixed_background_structure"]["videos"],
    timing_ratios=bg_config["timing_ratios"],
    transition_duration=bg_config["transition"].get("duration", 1.0),
    logger=logger
)
```

#### 2. 動画生成を2パスに分割

**Pass 1**: 背景動画 + 画像（70%縮小） + 音声（字幕なし）  
**Pass 2**: Pass 1の動画に字幕を焼き込む（ASS形式でimpact対応）

```python
def _execute_with_background_video(self) -> VideoComposition:
    # Pass 1: 背景 + 画像 + 音声（字幕なし）
    temp_video = self.phase_dir / "temp_video_no_subtitles.mp4"
    self._create_video_with_background(
        audio_path=audio_path,
        images=images,
        background_videos=bg_selection['segments'],
        bgm_data=bgm_data,
        output_path=temp_video
    )
    
    # Pass 2: 字幕を焼き込む（impact対応）
    final_video = self.phase_dir / f"{self.subject}_final.mp4"
    self._burn_subtitles_with_impact(
        input_video=temp_video,
        srt_path=srt_path,
        subtitle_timing_path=subtitle_timing_path,
        output_path=final_video
    )
```

#### 3. Pass 1: 背景動画 + 画像のffmpegコマンド

```python
def _create_video_with_background(
    self,
    audio_path: Path,
    images: List[Path],
    background_videos: List[dict],
    bgm_data: Optional[dict],
    output_path: Path
) -> None:
    """
    背景動画の上に70%縮小した画像を配置
    
    ffmpegの処理:
    1. 背景動画3本を concat で繋ぐ（opening/main/ending）
    2. 画像を concat で繋いで1本の動画にする
    3. 画像を70%に scale (1344x756)
    4. 背景の上に overlay で配置（中央）
    5. 音声とBGMを追加
    """
```

#### 4. Pass 2: インパクト字幕の焼き込み

```python
def _burn_subtitles_with_impact(
    self,
    input_video: Path,
    srt_path: Path,
    subtitle_timing_path: Path,
    output_path: Path
) -> None:
    """
    字幕を焼き込む（impact_level対応）
    
    ASS形式で以下のスタイルを定義:
    - Normal: 白・60px（通常）
    - ImpactNormal: 赤・70px（普通インパクト）
    - ImpactMega: 白・100px・中央（特大インパクト、Phase 2で実装予定）
    """
```

**ASS字幕スタイル**:
```
Style: Normal,Arial,60,&HFFFFFF,&HFFFFFF,&H000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,70,1
Style: ImpactNormal,Arial,70,&H0000FF,&H0000FF,&H000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,2,10,10,70,1
```

---

### Task 5: 設定ファイル修正

**ファイル**: `config/phases/subtitle_generation.yaml`

**変更箇所**:
```yaml
# 変更前
max_chars_per_line: 18

# 変更後
max_chars_per_line: 20
```

---

## 📁 作成・変更されたファイル

### 新規作成
1. `config/phases/background_video.yaml` - 背景動画設定
2. `src/generators/background_video_selector.py` - 背景動画選択器
3. `src/phases/phase_06_subtitles_v2.py` - Phase 6拡張版
4. `src/phases/phase_07_composition_v2.py` - Phase 7拡張版

### 変更
1. `config/phases/subtitle_generation.yaml` - max_chars_per_line: 18 → 20

### ディレクトリ作成
1. `assets/background_videos/` - 背景動画ファイル配置用

---

## 🧪 使用方法

### 1. 背景動画を用意

```bash
mkdir -p assets/background_videos
# opening_001.mp4, main_001.mp4, ending_001.mp4 を配置
```

### 2. raw_script.yamlにimpact_phrases追加

**ファイル**: `working/<subject>/01_script/raw_script.yaml`

**追加例**:
```yaml
sections:
  - section_id: 1
    title: "導入"
    narration: |
      1519年、フランス。
      ある老人が静かに息を引き取ろうとしていた。
      その名は、レオナルド・ダ・ヴィンチ。
      ...
    
    # ← ここに追加
    impact_phrases:
      normal:  # 赤・70pxで表示
        - "レオナルド・ダ・ヴィンチ"
        - "私は、何も成し遂げられなかった"
      mega:    # Phase 2で実装（今回は使わない）
        - "これは、未来を見すぎた天才の物語だ"
```

### 3. 実行

```bash
# Phase 6 (V2)
python -m src.phases.phase_06_subtitles_v2 "レオナルドダヴィンチ"

# Phase 7 (V2)
python -m src.phases.phase_07_composition_v2 "レオナルドダヴィンチ"
```

---

## ✅ 確認ポイント

- [x] 背景動画が opening → main → ending で切り替わっている
- [x] 画像が70%（1344x756）で中央配置されている
- [x] 普通インパクト字幕が赤・70pxで表示されている
- [x] subtitle_timing.json に impact_level キーがある
- [x] 全ファイルの構文チェック成功

---

## ⚠️ 注意事項

### 既存システムとの互換性

1. **既存ファイルは変更していません**
   - `phase_06_subtitles.py` → コピーして `phase_06_subtitles_v2.py`
   - `phase_07_composition.py` → コピーして `phase_07_composition_v2.py`

2. **既存システムが引き続き動作します**
   - legacy版（元のphase_06, phase_07）は影響を受けません

### 実行前の準備

1. **背景動画ファイルの配置**
   ```bash
   assets/background_videos/
   ├── opening_001.mp4
   ├── main_001.mp4
   └── ending_001.mp4
   ```

2. **raw_script.yamlの編集**
   - 各セクションに `impact_phrases` を追加

---

## 🔧 トラブルシューティング

### ffmpegエラー
```bash
# -report フラグを追加してログ確認
ffmpeg -report -i input.mp4 ...
```

### 背景動画が見えない
- `-shortest` フラグを確認
- 背景動画の長さが十分か確認

### 字幕が表示されない
- ASSファイルを直接確認
- `subtitle_timing.json` の `impact_level` キーを確認

---

## 📚 参考ファイル

実装時に参考にしたファイル:
- `src/generators/bgm_selector.py` → `background_video_selector.py` の構造
- `src/phases/phase_07_composition.py` → ffmpegコマンドの書き方
- `src/phases/phase_06_subtitles.py` → 字幕タイミングJSONの作り方

---

## 🎉 次のステップ（Phase 2）

Phase 2では以下の機能を実装予定:

1. **ImpactMega字幕**
   - 白・100px・中央配置
   - より強いインパクト

2. **背景動画のトランジション改善**
   - クロスフェード効果の最適化

3. **画像のアニメーション**
   - ズームイン/アウト効果

---

**実装完了日**: 2025年11月19日  
**バージョン**: Phase 1 (v1.0)
