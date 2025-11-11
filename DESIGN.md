# 偉人動画自動生成システム - 詳細設計書 v3.0

**作成日**: 2025年10月28日
**最終更新日**: 2025年11月11日
**対象読者**: 開発者、AI補助ツール
**設計方針**: 変更容易性、デバッグ性、フェーズ独立実行を最優先

## 📋 更新履歴

### v3.0 (2025年11月11日)
- **Phase 2: 音声生成の改善**
  - 句点（。！？）での間隔制御機能を追加
  - `punctuation_pause`設定による自然な音声リズムの実現
  - 句点後の無音時間を調整可能（デフォルト: 0.8秒）
  - セクション間無音との区別を明確化

- **Phase 6: 字幕生成の改善**
  - フォントの太さ設定を詳細化
  - `stroke_width`による縁取りの太さ調整（デフォルト: 2px）
  - `font_weight`設定追加（regular/medium/bold/black）
  - 視認性向上のための推奨設定を明記
  - 改行（\n）の正確な処理ロジックを追加
  - 長文の句読点分割（36文字超で「、」優先）

- **Phase 7: 動画統合の改善**
  - 字幕バーの高さを30%から20%に削減
  - オーバーレイ方式による黒バー表示（右側の黒バーを解消）
  - 1920x1080解像度で864px動画+216px字幕バー構成

- **Phase 8: サムネイル生成の改善**
  - 横顔・側面アングルを重視した構図
  - 若々しいエネルギッシュな表現
  - 壮大な背景（城、山、風景）の強調
  - 実写過ぎない印象的なスタイル（cinematic artistic style）
  - Stable Diffusion対応（Phase 3と同じ仕組み）

### v2.3 (2025年11月11日)
- Phase 8にStable Diffusion対応を追加
- Claude APIによるSD用プロンプト最適化を実装

### v2.2 (2025年11月10日)
- Phase 6の長文分割ロジックを改善
- 最小断片長保証（MIN_CHUNK_LENGTH = 10文字）を追加

### v2.1 (2025年11月10日)
- Phase 2とPhase 6の句読点処理を修正
- 「、」の分割位置を修正（「、」の直後で分割）

---

## 🔄 ワークフロー（まとめ）
```
1. テンプレート作成
   ↓
   python scripts/create_script_template.py "グリゴリー・ラスプーチン"

2. YAMLファイルを編集（これがメイン作業）
   ↓
   data/input/manual_scripts/偉人名.yaml

3. JSONに変換（1コマンド）
   ↓
   python scripts/convert_manual_script.py "グリゴリー・ラスプーチン"

4. 動画生成（自動で手動台本が使われる）
   ↓
   python -m src.cli generate "グリゴリー・ラスプーチン"
```

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

---

## 🔄 フェーズ詳細設計

### Phase 2: 音声生成（Audio Generation）

**責務**: Kokoro TTS/ElevenLabsを使用してナレーション音声を生成

**入力**:
- `working/{subject}/01_script/script.json`

**処理**:
1. 台本からナレーション原稿を抽出
2. セクションごとに音声生成
3. 句点（。！？）での間隔制御
4. 生成した音声をpydubで結合
5. 音声解析（実際の長さ、無音部分検出）
6. Whisperによる文字レベルタイミング情報の生成

**出力**:
- `working/{subject}/02_audio/narration_full.mp3`
- `working/{subject}/02_audio/sections/section_XX.mp3`
- `working/{subject}/02_audio/audio_timing.json` （文字レベルタイミング情報）
- `working/{subject}/02_audio/audio_analysis.json`

#### 📌 句点での間隔制御（重要な新機能）

**目的**: 自然な音声リズムを作るため、句点後に適切な間隔を挿入

**設定例（config/phases/audio_generation.yaml）**:
```yaml
# ========================================
# 音声生成サービス選択
# ========================================
service: "kokoro"  # または "elevenlabs"

# ========================================
# 句点での間隔制御（全サービス共通）
# ========================================
punctuation_pause:
  enabled: true                    # 句点での間隔制御を有効化

  # 各句読点の後に挿入する無音時間（秒）
  pause_duration:
    period: 0.8                    # 「。」の後の無音時間
    exclamation: 0.9               # 「！」の後の無音時間
    question: 0.9                  # 「？」の後の無音時間
    comma: 0.0                     # 「、」の後の無音時間（通常は挿入しない）

  # セクション末尾の句点は間隔を挿入しない
  skip_section_end: true           # セクション末尾の句点はスキップ

# セクション間の無音時間（句点での間隔とは別）
inter_section_silence: 0.5

# ========================================
# Kokoro TTS 設定
# ========================================
kokoro:
  api_url: "http://localhost:8880"
  voice: "jf_alpha"                # 日本語女性音声
  speed: 1.0
  response_format: "mp3"

# ========================================
# Whisper タイムスタンプ取得設定
# ========================================
whisper:
  enabled: true                    # Whisper使用の有効化
  model: "small"                   # 日本語認識精度向上のため推奨
  language: "ja"
  device: "auto"
```

#### 実装の詳細

**句点での間隔制御の仕組み**:

1. **ナレーション原稿の分析**
   ```python
   # 句読点位置を検出
   narration = "信長は尾張の大うつけと呼ばれた。しかし彼は天下統一を目指した！"
   # → 「。」の位置: 18
   # → 「！」の位置: 39
   ```

2. **無音クリップの挿入**
   ```python
   from pydub import AudioSegment

   # 音声生成
   audio = kokoro_tts.generate(narration)

   # 句点位置で分割
   segments = []
   for sentence in split_by_punctuation(narration):
       segment_audio = kokoro_tts.generate(sentence)
       segments.append(segment_audio)

       # 句読点の種類に応じた無音を追加
       if sentence.endswith('。'):
           silence = AudioSegment.silent(duration=800)  # 0.8秒
       elif sentence.endswith('！') or sentence.endswith('？'):
           silence = AudioSegment.silent(duration=900)  # 0.9秒
       else:
           silence = AudioSegment.silent(duration=0)

       segments.append(silence)

   # 結合
   final_audio = sum(segments)
   ```

3. **タイミング情報の調整**
   ```python
   # audio_timing.jsonに無音時間を反映
   # 各文字のタイミング情報に無音時間のオフセットを追加
   ```

**設定値の調整ガイドライン**:

| 句読点 | 推奨値（秒） | 説明 |
|--------|-------------|------|
| 。（句点） | 0.6 - 1.0 | 文の終わり。次の文への切り替わりを明確に |
| ！（感嘆符） | 0.8 - 1.2 | 感情的な強調。やや長めの間 |
| ？（疑問符） | 0.8 - 1.2 | 疑問。考える時間を与える |
| 、（読点） | 0.0 - 0.3 | 文中の区切り。通常は無音を入れない |

**注意事項**:
- **セクション末尾の句点**: `skip_section_end: true`の場合、セクション末尾の句点後には無音を挿入しない（`inter_section_silence`が代わりに適用される）
- **Whisperタイミング情報**: 無音挿入後のタイミング情報はWhisperで再取得されるため、自動的に調整される
- **字幕との同期**: Phase 6で生成される字幕は、無音時間を含むタイミング情報に基づいて正確に同期される

---

### Phase 6: 字幕生成（Subtitle Generation）

**責務**: 音声に同期した字幕を生成

**入力**:
- `working/{subject}/01_script/script.json`
- `working/{subject}/02_audio/audio_timing.json` （文字レベルタイミング情報）
- `working/{subject}/02_audio/audio_analysis.json` （フォールバック用）

**処理**:
1. Phase 2で生成された文字レベルのタイミング情報を読み込み
2. `\n`（改行）を検出し、改行位置で字幕を分割
3. 長い文（36文字超）を適切な位置で分割
   - 優先順位: `\n`改行 > 「、」の直後 > 助詞の後 > 文字種境界
4. 各文を2行（18文字×2）に分割
5. 句読点を処理（「。」「！」「？」を削除、「、」は保持）
6. 空の字幕をフィルタリング
7. SRTファイル生成

**出力**:
- `working/{subject}/06_subtitles/subtitles.srt`
- `working/{subject}/06_subtitles/subtitle_timing.json`
- `working/{subject}/06_subtitles/metadata.json`

#### 📌 字幕フォントの太さ設定（重要）

**目的**: 視認性を高めるため、フォントの太さを調整可能にする

**設定例（config/phases/subtitle_generation.yaml）**:
```yaml
# ========================================
# 字幕の基本設定
# ========================================
max_lines: 2                       # 最大2行
max_chars_per_line: 18             # 1行あたり最大18文字

# ========================================
# フォント設定（重要）
# ========================================
font:
  # フォントファミリー
  family: "Noto Sans JP Bold"      # 日本語フォント名

  # フォントサイズ（ピクセル）
  size: 60                         # デフォルト: 60px
  # 推奨値:
  # - 50-55px: やや小さめ（多くの文字を表示）
  # - 60-65px: 標準（推奨）
  # - 70-80px: 大きめ（高齢者向け）

  # フォントの太さ（weight）
  font_weight: "bold"              # regular/medium/bold/black
  # - regular: 通常の太さ（400）
  # - medium: やや太め（500-600）
  # - bold: 太字（700）★推奨
  # - black: 極太（900）

  # 文字色
  color: "#FFFFFF"                 # 白色

  # 背景色と透明度
  background_color: "#000000"      # 黒色
  background_opacity: 0.7          # 0.0-1.0（0.7 = 70%不透明）

  # 配置
  position: "bottom"               # 画面下部
  margin_bottom: 80                # 下からのマージン（px）

  # ========================================
  # 縁取り設定（視認性向上の鍵）
  # ========================================
  stroke_enabled: true             # 縁取りを有効化
  stroke_color: "#000000"          # 黒色の縁取り
  stroke_width: 3                  # 縁取りの太さ（ピクセル）
  # 推奨値:
  # - 2px: 標準の太さ（デフォルト）
  # - 3px: やや太め ★推奨（視認性向上）
  # - 4-5px: 太め（背景が明るい場合）
  # - 6px以上: 極太（目立たせたい場合）

  # ========================================
  # シャドウ設定（さらなる視認性向上）
  # ========================================
  shadow_enabled: true             # シャドウを有効化
  shadow_offset: [3, 3]            # シャドウのオフセット [x, y]（ピクセル）
  # 推奨値:
  # - [2, 2]: 標準
  # - [3, 3]: やや強調 ★推奨
  # - [4, 4]: 強調（背景が明るい場合）

  shadow_color: "#000000"          # 黒色のシャドウ
  shadow_opacity: 0.8              # 0.0-1.0（0.8 = 80%不透明）
  shadow_blur: 2                   # シャドウのぼかし（ピクセル）
  # 推奨値:
  # - 0: ぼかしなし（シャープ）
  # - 2: 軽いぼかし ★推奨
  # - 4: 強いぼかし（柔らかい印象）
```

#### フォントの太さ設定の詳細ガイド

**1. フォントサイズ（size）**
```yaml
# 用途に応じた推奨値
size: 60   # 標準（1920x1080で18文字が収まる）
size: 65   # やや大きめ（視認性重視）
size: 70   # 大きめ（高齢者向け、文字数制限注意）
size: 55   # やや小さめ（多くの文字を表示）
```

**2. フォントウェイト（font_weight）**
```yaml
# 太さの段階
font_weight: "regular"  # 400 - 通常（細め）
font_weight: "medium"   # 500-600 - やや太め
font_weight: "bold"     # 700 - 太字 ★推奨
font_weight: "black"    # 900 - 極太
```

**3. 縁取りの太さ（stroke_width）**

縁取りは視認性を大きく左右します：

```yaml
# 背景が暗い場合（推奨）
stroke_width: 2   # 標準
stroke_width: 3   # やや太め ★推奨

# 背景が明るい場合
stroke_width: 4   # 太め
stroke_width: 5   # かなり太め

# 背景が複雑な場合
stroke_width: 6   # 極太（目立たせたい）
```

**4. シャドウの設定（shadow_offset）**

シャドウは立体感を出し、視認性を高めます：

```yaml
# 標準的な設定
shadow_offset: [2, 2]   # 標準
shadow_blur: 2          # 軽いぼかし

# 強調したい場合
shadow_offset: [3, 3]   # やや強調 ★推奨
shadow_blur: 2          # 軽いぼかし
shadow_opacity: 0.8     # やや濃い

# さらに強調したい場合
shadow_offset: [4, 4]   # 強調
shadow_blur: 3          # 中程度のぼかし
shadow_opacity: 0.9     # 濃い
```

#### 視認性を最大化する推奨設定

```yaml
font:
  family: "Noto Sans JP Bold"
  size: 65                         # やや大きめ
  font_weight: "bold"              # 太字
  color: "#FFFFFF"

  # 縁取りを太くする
  stroke_enabled: true
  stroke_color: "#000000"
  stroke_width: 3                  # ★ 標準より太め

  # シャドウを強化
  shadow_enabled: true
  shadow_offset: [3, 3]            # ★ やや大きめ
  shadow_color: "#000000"
  shadow_opacity: 0.85             # ★ やや濃いめ
  shadow_blur: 2

  # 背景も調整
  background_color: "#000000"
  background_opacity: 0.75         # ★ やや濃いめ
```

#### 改行（\n）の処理ロジック

**優先順位**:
1. **`\n`（改行）**: 明示的な改行がある場合、その位置で必ず分割
2. **長文分割（36文字超）**: 「、」の直後で優先的に分割
3. **2行分割（18文字×2）**: 自然な位置で2行に分割

**実装の詳細**:
```python
# 1. \n改行の検出と分割
def _split_section_by_newline(text, characters, start_times, end_times):
    # textを\nで分割
    text_parts = text.split('\n')

    # characters配列から対応する部分を抽出
    for part in text_parts:
        # 記号を除外してマッチング
        part_clean = ''.join([c for c in part if c not in exclude_symbols])
        pos = chars_str.find(part_clean, search_start)

        # subsectionを作成
        subsections.append({
            "characters": characters[pos:end_pos],
            "start_times": start_times[pos:end_pos],
            "end_times": end_times[pos:end_pos]
        })

# 2. 長文（36文字超）の分割
def _split_large_chunk(remaining_chars, max_chars=36):
    # 優先順位1: 36文字より前で最も後ろの「、」を探す
    comma_positions = [i for i, c in enumerate(remaining_chars)
                      if c == '、' and i < max_chars]

    if comma_positions:
        split_pos = comma_positions[-1] + 1  # 「、」の直後で分割
        reason = "comma_split_priority"
    else:
        # 優先順位2: スコアリングロジック
        split_pos, reason = _find_split_position_with_score(...)

    return split_pos, reason
```

---

### Phase 7: 動画統合（Video Composition）

**責務**: 全ての素材を統合して最終動画を生成

**最新の改善点**:

#### 📌 字幕バーの高さ調整

**変更内容**: 字幕バーを30%から20%に削減

**理由**:
- max_lines: 2（最大2行）なので30%は過剰
- 動画表示領域を広げることで視認性向上

**設定例（config/phases/video_composition.yaml）**:
```yaml
# ========================================
# 動画レイアウト設定
# ========================================
layout:
  type: "split"                    # 分割レイアウト

  # 上下分割の比率
  ratio: 0.8                       # 上部80%が動画、下部20%が字幕
  # 1920x1080の場合:
  # - 上部: 1920x864 (80%)
  # - 下部: 1920x216 (20%)

  # オーバーレイ方式（黒バーを画像の上に配置）
  overlay_mode: true               # オーバーレイ方式を使用
  # - 画像を1920x1080のままロード
  # - 下部216pxに黒バーをオーバーレイ
  # - 右側の黒バーが発生しない
```

#### オーバーレイ方式の実装

```python
def _create_split_layout_video(self, animated_clips, subtitles, total_duration):
    # Step 1: 動画を1920x1080のままロードして連結
    video_clips = self._create_video_clips(animated_clips, total_duration)
    base_video = self._concatenate_clips(video_clips, total_duration)

    # Step 2: 下部の字幕バー（オーバーレイ用）を生成
    bottom_height = int(1080 * 0.2)  # 216px
    top_height = 1080 - bottom_height  # 864px

    bottom_overlay = self._create_bottom_subtitle_bar(
        subtitles, total_duration, bottom_height
    )

    # Step 3: 動画の上に下部バーをオーバーレイ
    final_video = CompositeVideoClip([
        base_video.with_position((0, 0)),
        bottom_overlay.with_position((0, top_height))
    ], size=(1920, 1080))

    return final_video
```

---

### Phase 8: サムネイル生成（Thumbnail Generation）

**責務**: 動画用のサムネイルを生成

**最新の改善点（v3.0）**:

#### 📌 スタイリッシュな構図と表現

**変更内容**: より印象的でかっこいいサムネイル生成

**新しい要件**:
1. **横顔・側面アングル**: 正面ではなく、プロファイルビューや3/4アングル
2. **若々しさ**: 渋い顔ではなく、エネルギッシュで若々しい表現
3. **壮大な背景**: 城、山、自然など美しく壮大な景色
4. **迫力**: 顔の表情ではなく、雰囲気と構図で迫力を表現
5. **印象的スタイル**: 実写過ぎず、シネマティックでアーティスティック

**プロンプト設定例**:

```yaml
# ========================================
# 背景画像生成方法の選択
# ========================================
use_stable_diffusion: true        # true=SD, false=DALL-E 3

# ========================================
# Stable Diffusion設定
# ========================================
stable_diffusion:
  # プロンプトテンプレート（v3.0対応）
  prompt_template: |
    Cinematic stylized scene of {subject} in profile or side angle,
    standing majestically against grand scenic background.

    CHARACTER PORTRAYAL (CRITICAL):
    - {subject} shown with YOUTHFUL, ENERGETIC appearance - not old or stern-faced
    - PROFILE VIEW, SIDE ANGLE, or THREE-QUARTER VIEW - NOT frontal face
    - Full body or 3/4 body shot showing elegant stance
    - Convey powerful PRESENCE and ATMOSPHERE, not facial details
    - Dynamic posture creating visual impact
    - Stylish, cool composition

    BACKGROUND - GRAND AND SCENIC (CRITICAL):
    - MAGNIFICENT background: castle, mountain range, dramatic sky, vast natural landscape
    - Grand architectural or natural elements emphasizing epic scale
    - Beautiful, impressive environment that enhances atmosphere
    - Period-appropriate setting with visual grandeur
    - Create depth and scale with scenic elements

    VISUAL STYLE:
    - Cinematic and artistic - stylized realism, NOT overly photorealistic
    - Like epic movie poster or dramatic historical painting
    - Professional quality with artistic flair
    - Dramatic lighting highlighting atmosphere and scale
    - Rich, vibrant colors with artistic balance
    - Impressive but not documentary-style photo

    COMPOSITION REQUIREMENTS (CRITICAL):
    - DYNAMIC, STYLISH ANGLE - not static frontal view
    - Subject positioned impressively against grand background
    - 16:9 horizontal landscape format
    - Emphasize SCALE and GRANDEUR of the scene
    - Profile or side view preferred for cool factor
    - Atmospheric depth and visual interest

    CRITICAL REQUIREMENTS:
    1. Youthful, energetic - NOT old or stern
    2. Profile/side angle - NOT frontal face
    3. Grand scenic background (castle, nature, mountains)
    4. Atmospheric presence - NOT facial focus
    5. Stylish composition - NOT static pose
    6. Artistic cinematic style - NOT overly photorealistic

  # ネガティブプロンプト
  negative_prompt: |
    frontal face view, facial close-up, old appearance, stern expression,
    plain background, static centered pose, overly photorealistic,
    documentary style, modern elements, multiple subjects
```

#### DALL-E 3プロンプトの例

```yaml
dalle:
  # DALL-E 3用プロンプト（v3.0対応）
  prompt_template: |
    A stylish, cinematic scene of {subject} standing majestically
    against a grand scenic background.

    CHARACTER PORTRAYAL:
    - Show {subject} with a YOUTHFUL, ENERGETIC presence - not old or stern
    - Profile view, side angle, or three-quarter view - NOT frontal face
    - Full body or 3/4 body shot showing stylish stance
    - Convey PRESENCE and ATMOSPHERE rather than facial expression
    - Dynamic, cool posture that creates visual impact

    BACKGROUND - GRAND AND SCENIC (CRITICAL):
    - MAGNIFICENT natural or architectural background
    - Examples: Castle silhouette, mountain range, dramatic sky, vast landscape
    - Grand scale that emphasizes the epic atmosphere
    - Beautiful, impressive environment that enhances the mood
    - Period-appropriate setting with visual grandeur

    VISUAL STYLE:
    - Cinematic and artistic - impressive but not overly photorealistic
    - Stylized realism with artistic flair
    - Like an epic movie poster or dramatic painting
    - Rich colors and dramatic lighting

    COMPOSITION (CRITICAL):
    - Dynamic, stylish angle - NOT static frontal pose
    - Subject positioned impressively against grand background
    - Horizontal 16:9 format
    - Space at top and bottom for text overlay
    - Emphasize the SCALE and GRANDEUR of the scene

    CRITICAL REQUIREMENTS:
    1. Youthful, energetic portrayal - NOT stern or aged
    2. Profile/side angle - NOT frontal face view
    3. Grand scenic background (castle, nature, mountains, etc.)
    4. Atmospheric presence - NOT facial expression focus
    5. Stylish, dynamic composition - NOT static pose
    6. Cinematic and impressive - NOT overly photorealistic
```

---

## 🎛️ 設定ファイルの完全な例

### config/phases/audio_generation.yaml（完全版）

```yaml
# ========================================
# Phase 2: 音声生成設定
# ========================================

# ========================================
# 音声生成サービス選択
# ========================================
service: "kokoro"  # または "elevenlabs"

# ========================================
# 句点での間隔制御（重要）
# ========================================
punctuation_pause:
  enabled: true                    # 句点での間隔制御を有効化

  # 各句読点の後に挿入する無音時間（秒）
  pause_duration:
    period: 0.8                    # 「。」の後
    exclamation: 0.9               # 「！」の後
    question: 0.9                  # 「？」の後
    comma: 0.0                     # 「、」の後（通常は挿入しない）

  # セクション末尾の句点は間隔を挿入しない
  skip_section_end: true

# セクション間の無音時間（句点での間隔とは別）
inter_section_silence: 0.5

# ========================================
# Kokoro TTS 設定
# ========================================
kokoro:
  api_url: "http://localhost:8880"
  voice: "jf_alpha"                # 日本語女性音声
  speed: 1.0
  response_format: "mp3"

# ========================================
# Whisper タイムスタンプ取得設定
# ========================================
whisper:
  enabled: true
  model: "small"                   # 日本語認識精度向上
  language: "ja"
  device: "auto"

# ========================================
# ElevenLabs設定（service: "elevenlabs"の場合）
# ========================================
voice_id: "3JDquces8E8bkmvbh6Bc"
model: "eleven_turbo_v2_5"
with_timestamps: true

settings:
  stability: 0.7
  similarity_boost: 0.75
  style: 0
  use_speaker_boost: true
  speed: 1.0

format:
  codec: "mp3_44100_128"
  sample_rate: 44100
  channels: 1

# リトライ設定
retry:
  max_attempts: 5
  delay_seconds: 10

# キャッシュ設定
cache:
  enabled: true
  use_cached_audio: true
```

### config/phases/subtitle_generation.yaml（完全版）

```yaml
# ========================================
# Phase 6: 字幕生成設定
# ========================================

# 字幕の最大行数と文字数
max_lines: 2
max_chars_per_line: 18

# ========================================
# フォント設定（詳細）
# ========================================
font:
  # フォントファミリー
  family: "Noto Sans JP Bold"

  # フォントサイズ（ピクセル）
  size: 65                         # 標準より少し大きめ

  # フォントの太さ
  font_weight: "bold"              # bold推奨

  # 文字色
  color: "#FFFFFF"                 # 白色

  # 背景
  background_color: "#000000"
  background_opacity: 0.75         # やや濃いめ

  # 配置
  position: "bottom"
  margin_bottom: 80

  # 縁取り設定（重要）
  stroke_enabled: true
  stroke_color: "#000000"
  stroke_width: 3                  # 太め（視認性向上）

  # シャドウ設定（重要）
  shadow_enabled: true
  shadow_offset: [3, 3]            # やや大きめ
  shadow_color: "#000000"
  shadow_opacity: 0.85
  shadow_blur: 2

# ========================================
# タイミング設定
# ========================================
timing:
  min_display_duration: 1.0
  max_display_duration: 6.0
  lead_time: 0.2

# ========================================
# 形態素解析設定
# ========================================
morphological_analysis:
  use_mecab: true
  break_on:
    - "。"
    - "！"
    - "？"

# ========================================
# 分割戦略
# ========================================
splitting:
  window_size: 3

  priority_scores:
    punctuation: 120
    morpheme_boundary: 150
    particle: 100
    hiragana_to_kanji: 80
    kanji_to_hiragana: 60
    katakana_boundary: 40

  penalties:
    distance_from_ideal: 5
    ends_with_n_tsu: 20
    splits_number: 50
    splits_alphabet: 50
    splits_verb_adjective: 500

  particles:
    - "は"
    - "が"
    - "を"
    - "に"
    - "で"
    - "と"
    - "も"
    - "や"
    - "から"
    - "まで"
    - "より"

  balance_lines: true
  min_line_length: 3

# 句読点除去
remove_punctuation_in_display: true

# Whisper設定
whisper:
  enabled: true
  model: "base"
```

---

## 🎯 実装のベストプラクティス

### Phase 2: 音声生成のベストプラクティス

1. **句点での間隔は控えめに**
   - 0.8-0.9秒程度が自然
   - 長すぎると不自然に聞こえる

2. **セクション間無音との使い分け**
   - 句点での間隔: 文レベルの区切り
   - セクション間無音: 話題の切り替わり

3. **Whisperモデルの選択**
   - 日本語の場合は`small`以上を推奨
   - `tiny`は認識精度が低い

### Phase 6: 字幕生成のベストプラクティス

1. **フォントの太さ設定**
   ```yaml
   # 推奨設定
   font_weight: "bold"
   stroke_width: 3
   shadow_offset: [3, 3]
   ```

2. **視認性テスト**
   - 様々な背景で字幕が読めるか確認
   - 明るい背景でもテスト必須

3. **改行（\n）の活用**
   - 台本で意図的に改行を入れることで、字幕の分割を制御可能
   - 例: `"是非に及ばず\n49歳で散った革命児"`

---

## 📚 トラブルシューティング

### Phase 2: 音声生成

**問題**: 句点後の間隔が長すぎる
```yaml
# 解決: pause_durationを短くする
punctuation_pause:
  pause_duration:
    period: 0.6  # 0.8 → 0.6に変更
```

**問題**: セクション末尾に不要な無音が入る
```yaml
# 解決: skip_section_endを有効化
punctuation_pause:
  skip_section_end: true
```

### Phase 6: 字幕生成

**問題**: 字幕が読みにくい
```yaml
# 解決: 縁取りとシャドウを強化
font:
  stroke_width: 4      # 2 → 4
  shadow_offset: [4, 4]  # [2, 2] → [4, 4]
```

**問題**: フォントが細すぎる
```yaml
# 解決: font_weightを太くする
font:
  font_weight: "black"  # "bold" → "black"
```

---

**設計書バージョン**: 3.0
**最終更新日**: 2025年11月11日
**次回レビュー予定**: 新機能追加時
