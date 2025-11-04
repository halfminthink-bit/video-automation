# 偉人動画自動生成システム - 改善提案書

**作成日**: 2025-11-04
**対象バージョン**: v1.0
**ステータス**: Phase 6完了、Phase 7実行前

---

## 📋 現状の評価

### ✅ 解決済みの問題

1. **字幕と音声の同期**
   - Whisperによる正確なタイミング抽出を実装
   - FP16/FP32の自動判定で警告を解消
   - 実装場所: `src/utils/whisper_timing.py`, `src/generators/subtitle_generator.py`

2. **字幕の重複**
   - Whisperのタイミング情報により重複を防止
   - 最小・最大表示時間の制約を適用

3. **BGMの読み込み**
   - script.jsonの`bgm_suggestion`フィールドに基づいてBGMを配置
   - 固定3曲構成（opening/main/ending）で一貫性を確保
   - 実装場所: `src/phases/phase_05_bgm.py`, `src/phases/phase_07_composition.py`

---

## 🎯 改善提案

### 優先度：高 🔴

#### 1. Whisperタイミング抽出の堅牢性向上

**問題**:
- Whisperが部分的に失敗した場合、該当セクションのタイミングが不正確になる
- セクション数と抽出された文の数が一致しない場合のハンドリングが不十分

**改善案**:
```python
# subtitle_generator.py の改善

def _create_hybrid_timing(
    self,
    section: ScriptSection,
    whisper_timings: List[Dict],
    fallback_start: float,
    fallback_duration: float
) -> List[Dict]:
    """
    Whisperと文字数比率のハイブリッド処理

    - Whisperのタイミングが利用できる場合はそれを使用
    - 利用できない場合は文字数比率で推定
    - 両方を組み合わせて最適なタイミングを生成
    """
    sentences = self._split_into_sentences(section.narration)
    timings = []

    for i, sentence in enumerate(sentences):
        if i < len(whisper_timings):
            # Whisperのタイミングを使用
            timings.append(whisper_timings[i])
        else:
            # フォールバック：文字数比率で推定
            estimated_timing = self._estimate_timing_from_chars(
                sentence, fallback_start, fallback_duration
            )
            timings.append(estimated_timing)

    return timings
```

**効果**:
- Whisperが部分的に失敗してもスムーズに処理を続行
- より正確なタイミング情報の生成

**実装難易度**: 中
**推定工数**: 2-3時間

---

#### 2. BGMの音量自動調整（オーディオダッキング）

**問題**:
- BGMとナレーションが同じ音量で再生されると、ナレーションが聞き取りにくい
- 現在は固定音量（30%）で対応しているが、シーンによって最適な音量が異なる

**改善案**:
```python
# phase_07_composition.py の改善

def _apply_audio_ducking(
    self,
    narration: AudioFileClip,
    bgm: AudioFileClip,
    duck_amount: float = 0.5,
    attack_time: float = 0.5,
    release_time: float = 0.5
) -> AudioFileClip:
    """
    オーディオダッキング（ナレーション時にBGMの音量を下げる）

    Args:
        narration: ナレーション音声
        bgm: BGM
        duck_amount: ダッキング量（0-1）
        attack_time: ダッキング開始の遅延時間（秒）
        release_time: ダッキング解除の遅延時間（秒）

    Returns:
        ダッキング処理されたBGM
    """
    from pydub import AudioSegment
    import numpy as np

    # ナレーションの音量エンベロープを取得
    narration_array = narration.to_soundarray()
    envelope = np.abs(narration_array).mean(axis=1)

    # エンベロープに基づいてBGMの音量を調整
    bgm_array = bgm.to_soundarray()

    for i in range(len(envelope)):
        if envelope[i] > 0.01:  # ナレーションがある部分
            # 音量を下げる
            bgm_array[i] *= duck_amount

    # 配列からAudioFileClipを再構築
    return AudioFileClip(bgm_array, fps=bgm.fps)
```

**効果**:
- ナレーションが明瞭に聞こえるようになる
- よりプロフェッショナルな音声ミキシング

**実装難易度**: 中〜高
**推定工数**: 4-6時間

**代替案（簡易版）**:
- ナレーション部分でBGM音量を20%、無音部分で40%に設定
- 実装が簡単で効果も十分

---

#### 3. 字幕の重複検出と自動調整

**問題**:
- Whisperのタイミング情報にも誤差があり、稀に字幕が重複する可能性がある
- 現在は最小・最大表示時間で制約しているが、隣接字幕との重複チェックがない

**改善案**:
```python
# subtitle_generator.py の改善

def _adjust_subtitle_overlaps(
    self,
    subtitles: List[SubtitleEntry]
) -> List[SubtitleEntry]:
    """
    字幕の重複を検出して自動調整

    Args:
        subtitles: 字幕エントリのリスト

    Returns:
        調整された字幕エントリのリスト
    """
    adjusted = []

    for i, subtitle in enumerate(subtitles):
        if i == 0:
            adjusted.append(subtitle)
            continue

        prev_subtitle = adjusted[-1]

        # 重複をチェック
        if subtitle.start_time < prev_subtitle.end_time:
            self.logger.warning(
                f"Overlap detected: Subtitle {i} starts at {subtitle.start_time:.2f}s "
                f"but previous ends at {prev_subtitle.end_time:.2f}s"
            )

            # 調整方法1: 前の字幕の終了時間を早める
            gap = 0.1  # 0.1秒の間隔を確保
            prev_subtitle.end_time = subtitle.start_time - gap

            # 最小表示時間を確保
            if prev_subtitle.end_time - prev_subtitle.start_time < self.min_display_duration:
                # 調整方法2: 次の字幕の開始時間を遅らせる
                subtitle.start_time = prev_subtitle.end_time + gap

            self.logger.info(
                f"Adjusted: Previous ends at {prev_subtitle.end_time:.2f}s, "
                f"Current starts at {subtitle.start_time:.2f}s"
            )

        adjusted.append(subtitle)

    return adjusted
```

**効果**:
- 字幕の重複を完全に防止
- より安定した字幕表示

**実装難易度**: 低
**推定工数**: 1-2時間

---

### 優先度：中 🟡

#### 4. クリップループ時のトランジション改善

**問題**:
- 現在のクリップループは単純な連結のため、ループの継ぎ目が目立つ
- クロスフェードを追加してより自然なループを実現したい

**改善案**:
```python
# phase_07_composition.py の改善

def _concatenate_clips_with_crossfade(
    self,
    clips: List[VideoFileClip],
    target_duration: float,
    crossfade_duration: float = 0.5
) -> VideoFileClip:
    """
    クロスフェード付きでクリップを連結

    Args:
        clips: 動画クリップのリスト
        target_duration: 目標長さ（秒）
        crossfade_duration: クロスフェードの長さ（秒）

    Returns:
        連結された動画クリップ
    """
    from moviepy import concatenate_videoclips, CompositeVideoClip

    final_clips = []
    current_duration = 0.0

    while current_duration < target_duration:
        for i, clip in enumerate(clips):
            if current_duration >= target_duration:
                break

            remaining = target_duration - current_duration

            if clip.duration <= remaining:
                final_clips.append(clip)
                current_duration += clip.duration
            else:
                # 最後のクリップをトリミング
                trimmed = clip.subclipped(0, remaining)
                final_clips.append(trimmed)
                current_duration += remaining

    # クロスフェード付きで連結
    if len(final_clips) <= 1:
        return final_clips[0] if final_clips else None

    result = final_clips[0]
    for next_clip in final_clips[1:]:
        # クロスフェードトランジション
        result = result.crossfadein(next_clip, crossfade_duration)

    return result
```

**効果**:
- より自然なクリップのループ
- プロフェッショナルな見た目

**実装難易度**: 中
**推定工数**: 2-3時間

---

#### 5. プレビュー動画生成機能

**問題**:
- Phase 7のレンダリングには時間がかかる（数分〜数十分）
- 問題があった場合、全体を再レンダリングする必要がある

**改善案**:
```python
# phase_07_composition.py の改善

def generate_preview(
    self,
    preview_duration: float = 60.0,
    preview_resolution: Tuple[int, int] = (1280, 720),
    preview_fps: int = 24
) -> Path:
    """
    プレビュー動画を生成（低解像度、短時間）

    Args:
        preview_duration: プレビューの長さ（秒）
        preview_resolution: プレビューの解像度
        preview_fps: プレビューのFPS

    Returns:
        プレビュー動画のパス
    """
    self.logger.info("Generating preview video...")

    # 通常の処理と同じだが、以下の設定で高速化
    # - 低解像度
    # - 低FPS
    # - 短時間（最初の60秒のみ）

    # ... 実装 ...

    preview_path = self.phase_dir / "preview.mp4"

    # 低解像度・低FPSでレンダリング
    video.write_videofile(
        str(preview_path),
        codec="libx264",
        fps=preview_fps,
        bitrate="2000k",
        preset="ultrafast"  # 高速プリセット
    )

    self.logger.info(f"Preview generated: {preview_path}")
    return preview_path
```

**使用例**:
```bash
# プレビュー生成コマンド
python -m src.cli preview "織田信長" --duration 60
```

**効果**:
- 問題の早期発見
- イテレーション速度の向上

**実装難易度**: 中
**推定工数**: 3-4時間

---

#### 6. タイムライン可視化ツール

**問題**:
- タイムライン構造をテキストログだけでは把握しにくい
- BGM切り替え、字幕タイミング、クリップ配置を視覚的に確認したい

**改善案**:
```python
# 新規ファイル: src/utils/timeline_visualizer.py

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path
from typing import List, Dict, Any

def visualize_timeline(
    timeline_data: Dict[str, Any],
    output_path: Path
):
    """
    タイムラインを可視化してPNG画像として保存

    Args:
        timeline_data: タイムライン情報（Phase 7のtimeline.json）
        output_path: 出力画像のパス
    """
    fig, ax = plt.subplots(figsize=(20, 10))

    # 動画クリップを描画
    y_offset = 0
    for clip in timeline_data.get("clips", []):
        rect = patches.Rectangle(
            (clip["start_time"], y_offset),
            clip["duration"],
            0.5,
            linewidth=1,
            edgecolor='blue',
            facecolor='lightblue',
            label=clip["clip_type"]
        )
        ax.add_patch(rect)

    y_offset += 1

    # BGMを描画
    for bgm in timeline_data.get("bgm_segments", []):
        rect = patches.Rectangle(
            (bgm["start_time"], y_offset),
            bgm["duration"],
            0.5,
            linewidth=1,
            edgecolor='green',
            facecolor='lightgreen',
            label=f"BGM: {bgm['track_id']}"
        )
        ax.add_patch(rect)

    y_offset += 1

    # 字幕を描画
    for subtitle in timeline_data.get("subtitles", []):
        rect = patches.Rectangle(
            (subtitle["start_time"], y_offset),
            subtitle["end_time"] - subtitle["start_time"],
            0.3,
            linewidth=1,
            edgecolor='red',
            facecolor='pink'
        )
        ax.add_patch(rect)

    ax.set_xlim(0, timeline_data.get("total_duration", 900))
    ax.set_ylim(0, y_offset + 1)
    ax.set_xlabel('Time (seconds)')
    ax.set_title('Video Timeline Visualization')

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

**使用例**:
```bash
# タイムライン可視化コマンド
python -m src.cli visualize-timeline "織田信長"
```

**効果**:
- タイムライン構造の直感的な理解
- 問題箇所の特定が容易

**実装難易度**: 低〜中
**推定工数**: 2-3時間

---

### 優先度：低 🟢

#### 7. BGM選択のカスタマイズ機能

**問題**:
- 現在は固定の3曲構成のみ
- ユーザーが好みのBGMを選択できない

**改善案**:
- BGMライブラリからユーザーが曲を選択できるUIを提供
- 各セクションごとにBGMを手動で設定できる機能

**実装難易度**: 高
**推定工数**: 8-10時間

---

#### 8. 字幕スタイルのテンプレート化

**問題**:
- 字幕のスタイル（フォント、色、サイズ等）がハードコーディングされている
- ブランドや用途に応じてスタイルを変更したい

**改善案**:
- 字幕スタイルをYAMLテンプレートで定義
- 複数のプリセットから選択可能に

**実装難易度**: 中
**推定工数**: 4-5時間

---

#### 9. Whisperモデルのキャッシュと並列処理

**問題**:
- Whisperモデルのロードに時間がかかる
- 複数の偉人を処理する際、毎回モデルをロードしている

**改善案**:
- Whisperモデルをメモリにキャッシュ
- バッチ処理時にモデルを再利用

**実装難易度**: 低
**推定工数**: 1-2時間

---

## 📊 優先順位マトリックス

| 改善案 | 優先度 | 効果 | 実装難易度 | 推定工数 |
|--------|--------|------|-----------|---------|
| 1. Whisperタイミング抽出の堅牢性向上 | 🔴 高 | 高 | 中 | 2-3h |
| 2. BGMの音量自動調整 | 🔴 高 | 高 | 中〜高 | 4-6h |
| 3. 字幕の重複検出と自動調整 | 🔴 高 | 中 | 低 | 1-2h |
| 4. クリップループ時のトランジション改善 | 🟡 中 | 中 | 中 | 2-3h |
| 5. プレビュー動画生成機能 | 🟡 中 | 高 | 中 | 3-4h |
| 6. タイムライン可視化ツール | 🟡 中 | 中 | 低〜中 | 2-3h |
| 7. BGM選択のカスタマイズ機能 | 🟢 低 | 中 | 高 | 8-10h |
| 8. 字幕スタイルのテンプレート化 | 🟢 低 | 低 | 中 | 4-5h |
| 9. Whisperモデルのキャッシュ | 🟢 低 | 低 | 低 | 1-2h |

---

## 🚀 推奨実装順序

### Phase 7実行前（即座に実装）
1. **字幕の重複検出と自動調整** (1-2h) - 最も簡単で効果的
2. **Whisperタイミング抽出の堅牢性向上** (2-3h) - 安定性の向上

### Phase 7実行後（次回の改善サイクル）
1. **プレビュー動画生成機能** (3-4h) - イテレーション速度の向上
2. **BGMの音量自動調整** (4-6h) - 音質の大幅な改善
3. **タイムライン可視化ツール** (2-3h) - デバッグの効率化

### 長期的な改善
1. **クリップループ時のトランジション改善** (2-3h)
2. **Whisperモデルのキャッシュ** (1-2h)
3. **BGM選択のカスタマイズ機能** (8-10h)
4. **字幕スタイルのテンプレート化** (4-5h)

---

## 📝 まとめ

### 現在の実装の評価
- ✅ **字幕と音声の同期**: Whisperによる正確なタイミング抽出で解決
- ✅ **字幕の重複**: Whisperのタイミング情報で大幅に改善
- ✅ **BGMの読み込み**: bgm_suggestionフィールドで正しく実装

### 次のステップ
1. Phase 7を実行して動画を生成
2. 生成された動画を確認し、問題があれば優先度の高い改善案を実装
3. イテレーションを繰り返して品質を向上

### 長期的なビジョン
- より自然な音声ミキシング（オーディオダッキング）
- プロフェッショナルなビジュアルトランジション
- ユーザーによるカスタマイズ機能の拡充

---

**最終更新**: 2025-11-04
**レビュー者**: Claude Code
**ステータス**: Phase 7実行前の最終確認完了
