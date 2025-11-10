# Phase 2 & Phase 6: 音声生成と字幕生成の詳細仕様

**作成日**: 2025年11月10日
**対象読者**: 開発者、AI補助ツール
**目的**: Phase 2（音声生成）とPhase 6（字幕生成）の動作を詳細に説明

---

## 概要

Phase 2とPhase 6は密接に連携して、音声とそれに同期した字幕を生成します。

```
Phase 2 (音声生成)
    ↓
audio_timing.json を生成
    ↓
Phase 6 (字幕生成)
    ↓
subtitles.srt を生成
```

---

## Phase 2: 音声生成（Audio Generation）

### 責務
台本から音声を生成し、**文字レベルのタイミング情報**を取得する。

### 入力
- `working/{subject}/01_script/script.json` - Phase 1で生成された台本

### 処理フロー

#### 1. 音声生成（Kokoro TTS）
```python
# src/generators/kokoro_audio_generator.py
result = generator.generate_with_timestamps(
    text=text_to_generate,
    previous_text=previous_text,  # 文脈用
    next_text=next_text
)
```

**重要**: Kokoro TTSは音声のみを生成。タイミング情報は含まれない。

#### 2. Whisperによるタイミング抽出
```python
# src/generators/kokoro_audio_generator.py: _extract_timestamps_with_whisper()
# 生成した音声をWhisperで解析
word_timings = whisper_extractor.extract_word_timings(
    audio_path=tmp_file,
    text=text  # 元のテキストを渡す
)
```

**Whisperの動作**:
- 音声を認識して**単語レベル**のタイミング情報を返す
- 句読点は音声に含まれないため、認識結果に**句読点は含まれない**
- 例: "戦国時代、織田信長です。" → ["戦国時代", "織田信長", "です"] （「、」「。」なし）

#### 3. 文字レベルへの展開とアライメント

ここが最も重要な処理です。

```python
# src/utils/whisper_timing.py: align_text_with_whisper_timings()

def align_text_with_whisper_timings(
    original_text: str,  # "戦国時代、織田信長です。"
    recognized_text: str,  # Whisperの認識結果（句読点なし）
    word_timings: List[Dict],  # Whisperの単語タイミング
    logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
```

**処理手順**:

##### 3.1. 比較用テキストの正規化
```python
def normalize_text(text: str) -> str:
    # 空白、句読点、記号を除去
    text = re.sub(r'[\s、。，．！？!?「」『』【】（）()〈〉《》]', '', text)
    return text

original_normalized = "戦国時代織田信長です"
recognized_normalized = "戦国時代織田信長です"
```

##### 3.2. Whisperの単語タイミングを文字に展開
```python
# kokoro_audio_generator.py: _expand_word_timings_to_chars()
for word_info in word_timings:
    word = "戦国時代"
    word_start = 0.0
    word_end = 0.98

    # 各文字に均等に時間を割り当て
    char_duration = (0.98 - 0.0) / 4  # = 0.245秒/文字

    for i, char in enumerate(word):
        characters.append(char)  # "戦", "国", "時", "代"
        start_times.append(0.0 + i * 0.245)
        end_times.append(0.0 + (i+1) * 0.245)
```

**結果**: 句読点を除いた文字のタイミング情報

##### 3.3. 元のテキストとアライメント（句読点を追加）

```python
# whisper_timing.py: align_text_with_whisper_timings()

normalized_char_count = 0
last_timing = None

for i, char in enumerate(original_text):
    if not normalize_text(char):  # 句読点・空白の場合
        # 直前の文字のタイミングを使用
        if last_timing:
            aligned_timings.append({
                "word": char,  # "、" や "。"
                "start": last_timing["end"],  # 直前の文字の終了時刻
                "end": last_timing["end"],    # 同じ時刻（瞬間表示）
                "probability": last_timing["probability"]
            })
        continue

    # 通常の文字
    recognized_idx = int(normalized_char_count * ratio)
    timing = recognized_chars[recognized_idx]
    aligned_timings.append({
        "word": char,
        "start": timing["start"],
        "end": timing["end"],
        "probability": timing["probability"]
    })
    last_timing = timing
    normalized_char_count += 1
```

**重要なポイント**:
- 句読点には**直前の文字の終了時刻**を割り当てる
- 句読点は音声に含まれないが、表示用に位置情報が必要
- これにより、全ての文字（句読点含む）にタイミング情報が付与される

#### 4. audio_timing.jsonの生成

```python
# src/phases/phase_02_audio.py: _generate_all_sections_with_timestamps()

timing_info = {
    'section_id': section.section_id,
    'text': section.narration,        # 元のテキスト
    'tts_text': text_to_generate,     # TTS用テキスト
    'display_text': display_text,     # 字幕用テキスト
    'audio_path': str(audio_path),
    'characters': alignment.get('characters', []),           # ← 句読点を含む
    'char_start_times': alignment.get('character_start_times_seconds', []),
    'char_end_times': alignment.get('character_end_times_seconds', []),
    'offset': cumulative_offset,
    'duration': duration
}
```

**audio_timing.jsonの構造例**:
```json
{
  "section_id": 1,
  "text": "戦国時代、織田信長です。",
  "characters": ["戦", "国", "時", "代", "、", "織", "田", "信", "長", "で", "す", "。"],
  "char_start_times": [0.0, 0.34, 0.54, 0.74, 0.98, 0.98, 1.52, ...],
  "char_end_times": [0.34, 0.54, 0.74, 0.98, 0.98, 0.98, 1.62, ...],
  "offset": 0.0,
  "duration": 5.02
}
```

**注目点**:
- `characters[4]` = "、" （句読点が含まれる）
- `char_start_times[4]` = 0.98 （直前の文字の終了時刻）
- `char_end_times[4]` = 0.98 （同じ時刻 = 瞬間表示）

### 出力
- `working/{subject}/02_audio/audio_timing.json` - **文字レベルのタイミング情報（句読点を含む）**
- `working/{subject}/02_audio/sections/section_*.mp3` - 各セクションの音声
- `working/{subject}/02_audio/narration_full.mp3` - 結合された音声

---

## Phase 6: 字幕生成（Subtitle Generation）

### 責務
audio_timing.jsonを使用して、適切に分割された字幕を生成する。

### 入力
- `working/{subject}/02_audio/audio_timing.json` - Phase 2で生成された文字レベルのタイミング情報

### 処理フロー

#### 1. タイミング情報の読み込み

```python
# src/generators/subtitle_generator.py: generate_subtitles_from_char_timings()

for section in audio_timing_data:
    text = section.get("text")
    characters = section.get("characters", [])  # 句読点を含む
    char_start_times = section.get("char_start_times", [])
    char_end_times = section.get("char_end_times", [])
```

#### 2. 句読点位置の検出

```python
# subtitle_generator.py: _find_punctuation_positions_from_characters()

def _find_punctuation_positions_from_characters(
    self,
    characters: List[str]
) -> Dict[int, str]:
    """charactersから直接句読点位置を検出"""
    punctuation_marks = set(["。", "、", "！", "？", "…"])
    positions = {}

    for i, char in enumerate(characters):
        if char in punctuation_marks:
            positions[i] = char

    return positions

# 結果例: {4: "、", 11: "。", 47: "、", ...}
```

**なぜ直接検出するのか**:
- Phase 2の修正後、`characters`配列に句読点が含まれるようになった
- 古い方法（`_find_punctuation_positions`）は`characters`に句読点が**含まれない**前提だった
- 新しい方法で直接検出することで、正確に句読点位置を把握できる

#### 3. 文の分割

```python
# subtitle_generator.py: _split_by_punctuation()

def _split_by_punctuation(
    self,
    characters: List[str],
    punctuation_positions: Dict[int, str],
    start_times: List[float],
    end_times: List[float],
    offset: float
) -> List[Dict[str, Any]]:
    """句読点で大まかに分割（「。」のみで分割、「、」では分割しない）"""

    for i, char in enumerate(characters):
        current_chars.append(char)
        current_starts.append(start_times[i] + offset)
        current_ends.append(end_times[i] + offset)

        next_pos = i + 1
        punct = punctuation_positions.get(next_pos)
        should_split = (punct in ["。", "！", "？"]) or i == len(characters) - 1

        if should_split:
            # チャンクを保存
            chunks.append({
                "characters": current_chars.copy(),
                "start_times": current_starts.copy(),
                "end_times": current_ends.copy()
            })
            # リセット
            current_chars = []
```

**分割ルール**:
- 「。」「！」「？」で分割 → 新しい文の開始
- 「、」では分割しない → 同じ文の中で保持

**例**:
```
"戦国時代、織田信長です。尾張の領主でした。"
↓
チャンク1: "戦国時代、織田信長です"  （「。」で区切り）
チャンク2: "尾張の領主でした"
```

#### 4. 長い文の分割（36文字超）

```python
# subtitle_generator.py: _split_large_chunk()

if len(chunk_chars) > max_chars:  # max_chars = 36
    # スコアリング方式で分割位置を決定
    split_pos, reason = self._find_split_position_with_score(
        text="".join(remaining_chars),
        characters=remaining_chars,
        max_chars=max_chars,
        punctuation_positions={},
        boundaries=sub_boundaries
    )
```

#### 5. 分割位置の決定（スコアリング方式）

```python
# subtitle_generator.py: _find_split_position_with_score()

for pos in range(search_start, search_end):
    score = 0
    reason = ""

    # 【重要】「、」の処理
    # 「、」の直後で分割（「、」を含める）
    if pos > 0 and (pos - 1) in punctuation_positions:
        punct = punctuation_positions[pos - 1]
        if punct == "、":
            score += 120  # 最高優先度
            reason = "punctuation_after_comma"

    # その他の句読点（「。」など）も直後で分割
    if pos in punctuation_positions:
        punct = punctuation_positions[pos]
        if punct in ["。", "！", "？", "…"]:
            score += 120
            reason = f"punctuation_{punct}"

    # 助詞の後
    if pos in boundaries.get("particles", []):
        score += 100
        reason = "particle"

    # ひらがな→漢字
    elif pos in boundaries.get("hiragana_to_kanji", []):
        score += 80
        reason = "hiragana_to_kanji"

    # ... その他の条件
```

**分割優先順位**:
1. **「、」の直後** (スコア: 120) - 最優先
2. 助詞の後 (スコア: 100)
3. ひらがな→漢字 (スコア: 80)
4. 漢字→ひらがな (スコア: 60)
5. カタカナ境界 (スコア: 40)

**ペナルティ** (v2.2で追加):
- **最小断片長チェック** (MIN_CHUNK_LENGTH = 10)
  - 分割後の断片が10文字未満の場合: -200点
  - 極端に短い字幕を防止（例: "去ります" のみの4文字字幕）
- **バランスペナルティ**
  - 理想比率50:50から離れるほどペナルティ
  - 計算式: `abs(0.5 - actual_ratio) * 100`
  - なるべく均等な分割を促進

**「、」の分割例**:
```
入力: "彼が築いた礎は、後の豊臣秀吉、徳川家康へと..."  (40文字)
                    ↑pos-1=4   ↑pos=5

pos=5の時:
- (pos-1)=4 は「、」の位置
- 「、」の直後で分割
- 結果: ["彼が築いた礎は、", "後の豊臣秀吉、徳川家康へと..."]
```

**なぜpos-1をチェックするのか**:
- `pos`は「分割位置」= 次の文字の開始位置
- `pos-1`は「直前の文字」の位置
- 「、」を含めて分割するには、`pos-1`が「、」かチェックする必要がある

#### 6. 2行への分割

```python
# subtitle_generator.py: _split_into_balanced_lines()

def _split_into_balanced_lines(
    self,
    text: str,
    characters: List[str],
    max_chars_per_line: int,  # 18文字
    max_lines: int,           # 2行
    punctuation_positions: Dict[int, str],
    boundaries: Dict[str, List[int]]
) -> List[str]:
    """テキストを複数行に分割（なるべく均等に）"""
```

**処理**:
1. 1行目の分割位置を決定（18文字前後）
2. 句読点や文字種境界を考慮して自然な位置で分割
3. 2行目も同様に処理

**例**:
```
入力: "彼が築いた礎は、後の豊臣秀吉"  (18文字)
↓
line1: "彼が築いた礎は、"  (9文字)
line2: "後の豊臣秀吉"      (7文字)
```

**長文分割の改善例** (v2.2):
```
入力: "信長は49歳でこの世を去ります"  (15文字、2行に収まらない場合)

【改善前】
- "信長は49歳で" (7文字)
- "去ります" (4文字) ← 短すぎる
- ⚠️ "この世を" が抜ける問題

【改善後】
最小断片長ペナルティとバランスペナルティにより:
- 4文字の断片は -200点のペナルティ
- バランス悪い分割もペナルティ
- より自然な分割位置を選択
- テキスト欠落を防止
```

**36文字超の分割改善例** (v2.2):
```
入力: "しかし天正10年、京都本能寺で明智光秀の謀反により、信長は49歳でこの世を去ります"
(40文字)

【改善前】
_split_large_chunk() が max_chars=36 で分割:
1. 探索範囲: 33~39文字
2. 結果: 35文字 + 5文字
3. 残り "を去ります" (5文字) が短すぎる字幕になる

【改善後】
残りが10文字未満にならないよう調整:
1. max_split_pos = 40 - 10 = 30
2. adjusted_max_chars = min(36, 30) = 30
3. 探索範囲: 27~33文字
4. 結果: 約30文字 + 約10文字 のバランスの良い分割
```

#### 7. 句読点の削除

```python
# src/phases/phase_06_subtitles.py: _remove_punctuation_from_subtitles()

def _remove_punctuation_from_subtitles(
    self,
    subtitles: List[SubtitleEntry]
) -> List[SubtitleEntry]:
    """字幕から句読点を削除"""

    # 削除対象の句読点（「、」は残す）
    punctuation_to_remove = ['。', '！', '？', '，', '．']

    for subtitle in subtitles:
        # 各行から句読点を削除
        line1 = subtitle.text_line1
        for punct in punctuation_to_remove:
            line1 = line1.replace(punct, '')

        # 空の字幕をスキップ
        if not line1.strip() and not line2.strip():
            continue

        cleaned_subtitles.append(...)
```

**削除ルール**:
- **削除**: 「。」「！」「？」（文末の句読点）
- **保持**: 「、」（読みやすさのため）

**なぜ「、」を残すのか**:
- 文の区切りを明確にする
- 読む速度を調整しやすい
- 視覚的に自然

#### 8. 空の字幕のフィルタリング

```python
# phase_06_subtitles.py: _remove_punctuation_from_subtitles()

# 空の字幕をスキップ（句読点のみの行が削除されて空になった場合）
if not line1.strip() and not line2.strip() and not (line3 and line3.strip()):
    self.logger.debug(f"Skipping empty subtitle at index {subtitle.index}")
    continue

# インデックスを再割り当て（連番を維持）
for i, subtitle in enumerate(cleaned_subtitles, start=1):
    subtitle.index = i
```

**なぜ必要か**:
- 句読点のみの行（例: "。"）を削除すると空になる
- 空の字幕はバリデーションエラーになる
- フィルタリングして連番を維持

#### 9. SRTファイルの生成

```python
# phase_06_subtitles.py: _save_srt_file()

1
00:00:00,000 --> 00:00:03,720
戦国時代、「うつけ者」と
呼ばれた若武者がいました

2
00:00:03,720 --> 00:00:05,020
織田信長です
```

### 出力
- `working/{subject}/06_subtitles/subtitles.srt` - SRT形式の字幕
- `working/{subject}/06_subtitles/subtitle_timing.json` - タイミング情報のJSON

---

## 重要な仕様と設計判断

### 1. なぜ句読点を含めるのか？

**Phase 2で句読点を含める理由**:
- Phase 6で文の境界を正確に検出するため
- 分割位置の判定に句読点情報が必要
- 表示用テキストとして「、」を残すため

**Phase 6で「、」を残す理由**:
- 読みやすさの向上
- 文の区切りを明確にする
- 視覚的に自然な字幕

### 2. なぜ「、」の直後で分割するのか？

**正しい分割**:
```
"彼が築いた礎は、" | "後の豊臣秀吉"
```

**間違った分割**:
```
"彼が築いた礎は" | "、後の豊臣秀吉"
```

**理由**:
- 日本語の自然な読み方として、「、」は前の文節に属する
- 「、」が行頭に来ると不自然
- 読点は前の内容の区切りを示すため、前に含めるべき

### 3. なぜスコアリング方式を使うのか？

**利点**:
- 優先順位を明確に設定できる
- 複数の条件を組み合わせて判断できる
- 調整が容易（スコアを変更するだけ）

**優先順位の設計**:
1. 句読点（120点）- 文法的に最も重要
2. 助詞（100点）- 文節の区切り
3. 文字種境界（80-40点）- 自然な読み
4. 強制分割（最終手段）

### 4. タイミング情報の精度

**Whisperの役割**:
- 音声認識により単語レベルのタイミングを取得
- 認識精度は高いが、句読点は含まれない

**文字レベルへの展開**:
- 単語内で均等に時間を配分
- 句読点は直前の文字の時刻を使用

**精度の保証**:
- Whisperの認識精度に依存
- 認識率が低い場合はフォールバック（文字数比率）

---

## トラブルシューティング

### 問題1: 句読点が表示されない

**原因**: Phase 2でcharacters配列に句読点が含まれていない

**確認方法**:
```bash
# audio_timing.jsonを確認
cat working/織田信長/02_audio/audio_timing.json | jq '.[] | .characters'
# 句読点が含まれているか確認
```

**解決方法**: Phase 2を再実行
```bash
python -m src.phases.phase_02_audio --subject 織田信長 --force
```

### 問題2: 不自然な分割位置

**原因**: 句読点位置が正しく検出されていない

**確認方法**:
```python
# デバッグログを有効にする
self.logger.debug(f"Punctuation positions: {punctuation_positions}")
```

**解決方法**: `_find_punctuation_positions_from_characters`が正しく呼ばれているか確認

### 問題3: 空の字幕が生成される

**原因**: 句読点のみの行が削除されて空になる

**確認方法**:
```python
# デバッグログで確認
self.logger.debug(f"Skipping empty subtitle at index {subtitle.index}")
```

**解決方法**: 自動的にフィルタリングされる（v2.1で修正済み）

---

## 設定ファイル

### config/phases/subtitle_generation.yaml

```yaml
max_lines: 2
max_chars_per_line: 18  # 1行あたりの最大文字数

timing:
  min_display_duration: 4.0  # 最低表示時間（秒）
  max_display_duration: 6.0  # 最大表示時間（秒）

# 句読点表示設定
remove_punctuation_in_display: true  # 「。！？」を削除、「、」は保持

# 分割戦略
splitting:
  window_size: 3  # 分割位置の探索範囲
  priority_scores:
    punctuation: 120        # 句読点（最優先）
    particle: 100           # 助詞
    hiragana_to_kanji: 80   # ひらがな→漢字
    kanji_to_hiragana: 60   # 漢字→ひらがな
    katakana_boundary: 40   # カタカナ境界
```

---

## まとめ

### Phase 2の責務
1. 音声を生成（Kokoro TTS）
2. Whisperで単語レベルのタイミングを取得
3. 文字レベルに展開し、句読点を含める
4. audio_timing.jsonとして保存

### Phase 6の責務
1. audio_timing.jsonを読み込み
2. 句読点位置を検出
3. 文を適切に分割（「、」の直後など）
4. 2行に分割
5. 句読点を削除（「、」は保持）
6. 空の字幕をフィルタリング
7. SRTファイルとして保存

### 連携のポイント
- Phase 2で生成された**characters配列に句読点が含まれる**ことが前提
- Phase 6はこの情報を使って正確な分割を実現
- 「、」の直後で分割することで自然な日本語字幕を生成

### 今後の拡張性
- スコアリングの調整による分割精度の向上
- 新しい句読点への対応（「：」「；」など）
- より高度な自然言語処理の導入
