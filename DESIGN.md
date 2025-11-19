# 偉人動画自動生成システム - 詳細設計書 v4.2

**作成日**: 2025年10月28日
**最終更新日**: 2025年11月14日
**対象読者**: 開発者、AI補助ツール
**設計方針**: 変更容易性、デバッグ性、フェーズ独立実行を最優先

## 📋 更新履歴

### v4.2 (2025年11月14日)
- **Phase 6: 引用符内の句読点保持機能**
  - **引用符内句読点の保持** - 「」『』内の句読点（。、！？）を削除せず保持
  - `_remove_punctuation_except_in_quotation`メソッドの追加
  - 引用符外の句読点のみ削除する仕組み
  - 引用符内の改行文字（\n）を自動削除
  - 30文字を超える引用符をカンマで分割
  - 3行になった引用符を次の字幕に移動
  - `remove_punctuation_in_display`のデフォルト値をFalseに変更
  - 複数行にわたる引用符の正確な処理

### v4.1 (2025年11月13日)
- **Phase 3: AI画像生成の修正**
  - **リサイズ処理の完全修正** - 1344x768 → 1920x1080 PNGに確実に変換
  - SD生成サイズの設定ファイルからの読み込み
  - 元のJPEGファイルの自動削除機能追加
  - `width`/`height`パラメータの明示的指定
  - キーワード自動生成機能の詳細ドキュメント化

- **Phase 8: サムネイル生成の詳細化**
  - Phase 03との分離の明確化
  - SD生成サイズとリサイズフローの詳細ドキュメント化
  - IntellectualCuriosityGeneratorの処理フロー説明
  - 1344x768 → 1280x720 PNGへの変換プロセス

- **Phase 03/08分離の重要性**
  - 両フェーズの違いを明確に表形式で整理
  - トラブルシューティングガイドの追加
  - よくある混同ポイントの説明

### v4.0 (2025年11月13日)
- **Phase 2: タイミング抽出の大幅改善**
  - **ElevenLabs Forced Alignment統合** - Whisperから切り替え
  - 台本と音声の完璧なアライメント（99-100%精度）
  - 固有名詞（「延暦寺」「長篠」など）の100%正確な処理
  - 文字レベルの高精度タイミング
  - Whisperへの自動フォールバック機構
  - 環境変数による柔軟な設定（ELEVENLABS_API_KEY）

- **Phase 6: 字幕タイミングの完璧な同期**
  - `subtitle_gap`を0.1秒から0.01秒（MIN_GAP）に削減
  - 文字レベルタイミングの正確さを100%活用
  - 音声と字幕の完全同期を実現
  - `lead_time`と`subtitle_gap`のデフォルト値を0.0に設定
  - 次の字幕との最小限のギャップのみ適用

- **設定ファイルの改善**
  - `.env.example`を追加（環境変数の設定例）
  - `audio_generation.yaml`にElevenLabs FA設定を追加
  - `subtitle_generation.yaml`のタイミング設定を最適化

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

**責務**: Kokoro TTS/ElevenLabsを使用してナレーション音声を生成し、高精度タイミング情報を抽出

**入力**:
- `working/{subject}/01_script/script.json`

**処理**:
1. 台本からナレーション原稿を抽出
2. セクションごとに音声生成
3. 句点（。！？）での間隔制御
4. 生成した音声をpydubで結合
5. 音声解析（実際の長さ、無音部分検出）
6. **🔥 ElevenLabs Forced Alignmentによる文字レベルタイミング情報の生成**（優先）
7. フォールバック: Whisperによるタイミング抽出

**出力**:
- `working/{subject}/02_audio/narration_full.mp3`
- `working/{subject}/02_audio/sections/section_XX.mp3`
- `working/{subject}/02_audio/audio_timing.json` （**高精度**文字レベルタイミング情報）
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
- **タイミング情報**: 無音挿入後のタイミング情報はElevenLabs FA/Whisperで再取得されるため、自動的に調整される
- **字幕との同期**: Phase 6で生成される字幕は、無音時間を含むタイミング情報に基づいて正確に同期される

#### 📌 ElevenLabs Forced Alignment統合（v4.0の最重要機能）

**目的**: Whisperの代わりにElevenLabs Forced Alignment APIを使用し、台本と音声の完璧なアライメントを実現

**背景**:
- Whisperは汎用音声認識のため、台本があるケースでは精度が劣る
- 固有名詞（「延暦寺」「長篠」など）の認識ミス
- 短い発話（0.9秒など）で特にズレが顕著

**解決策**:
- ElevenLabs Forced Alignmentで台本と音声を照合
- 99-100%の精度を実現
- TTS音声（Kokoro TTS）との相性が良い

**設定例（config/phases/audio_generation.yaml）**:
```yaml
# ========================================
# タイミング抽出設定
# ========================================
# 🔥 ElevenLabs Forced Alignment（台本と音声の完璧なアラインメント）
use_elevenlabs_fa: true

# ElevenLabs API Key（環境変数から自動取得）
# .envファイルに ELEVENLABS_API_KEY=your_key_here を設定
elevenlabs_api_key: null  # 実際には環境変数から読み込まれます

# ========================================
# Whisper設定（フォールバック用）
# ========================================
whisper:
  enabled: true           # ElevenLabs FAが失敗した場合に使用
  model: "small"
  language: "ja"
  use_stable_ts: true
  suppress_silence: true
  vad: true
  vad_threshold: 0.35
```

**動作フロー**:
```
音声生成（Kokoro TTS）
  ↓
ElevenLabs FA → タイミング抽出（優先）
  ↓ 失敗時
Whisper → タイミング抽出（フォールバック）
  ↓
audio_timing.json生成
```

**セットアップ**:
1. ElevenLabs API Keyを取得: https://elevenlabs.io/app/settings/api-keys
2. `.env.example`をコピー: `cp .env.example .env`
3. API Keyを設定: `ELEVENLABS_API_KEY=your_key_here`

**コスト**:
- 1分の音声: 約$0.0006（約0.1円）
- 10分の動画: 約1円

**実装の詳細**:

1. **ElevenLabs FAの呼び出し**
   ```python
   # src/utils/elevenlabs_forced_alignment.py

   class ElevenLabsForcedAligner:
       def align(self, audio_path, text, language="ja"):
           # ElevenLabs APIにリクエスト
           response = requests.post(
               "https://api.elevenlabs.io/v1/audio-native",
               files={'audio': audio_file},
               data={'text': text, 'language': language},
               headers={'xi-api-key': self.api_key}
           )

           # audio_timing.json形式に変換
           return {
               "characters": [...],
               "char_start_times": [...],
               "char_end_times": [...]
           }
   ```

2. **Whisperへのフォールバック**
   ```python
   # src/generators/kokoro_audio_generator.py

   def _extract_timestamps_with_whisper(self, audio_base64, text):
       # まずElevenLabs FAを試す
       if self.use_elevenlabs_fa and self.elevenlabs_aligner:
           try:
               alignment = self.elevenlabs_aligner.align(
                   audio_path=audio_path,
                   text=text,
                   language="ja"
               )
               return alignment
           except Exception as e:
               self.logger.warning("ElevenLabs FA failed, falling back to Whisper")

       # Whisperフォールバック
       whisper_extractor = WhisperTimingExtractor(...)
       word_timings = whisper_extractor.extract_word_timings(...)
       return self._expand_word_timings_to_chars(word_timings)
   ```

**期待される改善**:

| 項目 | Whisper | ElevenLabs FA |
|------|---------|---------------|
| タイミング精度 | 90-95% | 99-100% |
| 固有名詞の認識 | 不正確（認識ミスあり） | 完璧（台本と一致） |
| 短い発話 | ズレが顕著 | 正確 |
| 処理速度 | やや遅い | 高速 |

**注意事項**:
- API Keyが未設定の場合、自動的にWhisperにフォールバック
- Phase 6（字幕生成）のコードは変更不要
- `audio_timing.json`の形式は同じまま

---

### Phase 6: 字幕生成（Subtitle Generation）

**責務**: 音声に完璧に同期した字幕を生成

**入力**:
- `working/{subject}/01_script/script.json`
- `working/{subject}/02_audio/audio_timing.json` （**高精度**文字レベルタイミング情報）
- `working/{subject}/02_audio/audio_analysis.json` （フォールバック用）

**処理**:
1. Phase 2で生成された文字レベルのタイミング情報を読み込み
2. `\n`（改行）を検出し、改行位置で字幕を分割
3. 長い文（36文字超）を適切な位置で分割
   - 優先順位: `\n`改行 > 「、」の直後 > 助詞の後 > 文字種境界
4. 各文を2行（18文字×2）に分割
5. 句読点を処理（「。」「！」「？」を削除、「、」は保持）
6. 空の字幕をフィルタリング
7. **🔥 音声と完璧に同期したタイミングでSRTファイル生成**

**出力**:
- `working/{subject}/06_subtitles/subtitles.srt`
- `working/{subject}/06_subtitles/subtitle_timing.json`
- `working/{subject}/06_subtitles/metadata.json`

#### 📌 タイミングの完璧な同期（v4.0の重要改善）

**変更内容**: `subtitle_gap`を0.1秒から0.01秒（MIN_GAP）に削減

**背景**:
- ElevenLabs FA/stable-tsで取得した文字レベルタイミングは非常に正確
- 従来の`subtitle_gap: 0.1秒`は不要な調整だった
- 字幕が音声より0.1秒早く消える問題が発生

**解決策**:
- 文字レベルタイミングをそのまま使用
- 次の字幕との重なり防止のために**最小限のギャップ（0.01秒）のみ**適用

**設定例（config/phases/subtitle_generation.yaml）**:
```yaml
# ========================================
# タイミング設定
# ========================================
timing:
  min_display_duration: 1.0
  max_display_duration: 6.0

  # 🔥 v4.0: 文字レベルタイミングの正確さを100%活用
  lead_time: 0.0         # リードタイムなし（音声と完全同期）
  subtitle_gap: 0.0      # ギャップなし（最小ギャップは内部で0.01秒）

  prevent_overlap: true
  overlap_priority: "next_subtitle"
```

**実装の詳細**:

```python
# src/generators/subtitle_generator.py

def generate_subtitles_from_char_timings(self, audio_timing_data):
    # 🔥 文字レベルタイミング使用時は subtitle_gap を適用しない
    # 理由: audio_timing.json から取得したタイミングは既に正確
    # 最小ギャップは 0.01秒 のみ（次の字幕との重なりを防ぐ最小限の調整）
    MIN_GAP = 0.01

    for i, temp_sub in enumerate(temp_subtitles):
        subtitle_start = temp_sub["start"]
        subtitle_end = temp_sub["end"]

        # 次の字幕があるか確認
        next_start = temp_subtitles[i + 1]["start"] if i + 1 < len(temp_subtitles) else None

        # 🔥 重なり防止（最小ギャップのみ）
        if self.prevent_overlap and next_start is not None:
            max_allowed_end = next_start - MIN_GAP  # 0.01秒のギャップのみ

            if subtitle_end > max_allowed_end:
                subtitle_end = max_allowed_end

        # 字幕を作成
        subtitles.append(SubtitleEntry(
            start_time=subtitle_start,
            end_time=subtitle_end,
            ...
        ))
```

**期待される改善**:

**Before（v3.0）**:
```json
// 字幕5番: 「～天下を席巻」
{
  "start_time": 17.592,
  "end_time": 25.812  // 音声: 25.912秒 → 0.1秒早く消える
}
```

**After（v4.0）**:
```json
// 字幕5番: 「～天下を席巻」
{
  "start_time": 17.592,
  "end_time": 25.912  // 音声: 25.912秒 → 完璧に一致！
}
```

**注意事項**:
- この修正は`generate_subtitles_from_char_timings`メソッドのみに適用
- フォールバックメソッド（文字数ベースのタイミング推定）には影響しない
- 最低表示時間（min_display_duration）と重なり防止（prevent_overlap）は引き続き機能

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

#### 📌 引用符内の句読点保持（v4.2の重要機能）

**目的**: 引用符（「」『』）内の句読点を削除せず、原文のまま表示する

**背景**:
- 従来は全ての句読点（。、！？）を削除していた
- 引用符内の句読点も削除されてしまい、読みにくかった
- 「織田信長は言った。天下布武、これが我が目標だ」→「織田信長は言った天下布武これが我が目標だ」

**解決策**:
- 引用符内の句読点は保持
- 引用符外の句読点のみ削除
- 「織田信長は言った「天下布武、これが我が目標だ。」」→「織田信長は言った「天下布武、これが我が目標だ。」」

**設定例（config/phases/subtitle_generation.yaml）**:
```yaml
# 句読点は字幕に表示しない（除去する）
# 🔥 v4.2: デフォルト値はコード内でFalseに変更済み
# 設定ファイルでtrueを指定しても、引用符内の句読点は保持される
remove_punctuation_in_display: true
```

**実装の詳細**:

```python
# src/phases/phase_06_subtitles.py

def _remove_punctuation_except_in_quotation(
    self,
    text: str,
    punctuation_to_remove: List[str]
) -> str:
    """
    引用符内の句読点は残して削除

    Args:
        text: 処理対象テキスト
        punctuation_to_remove: 削除対象の句読点リスト（。、！？）

    Returns:
        処理後のテキスト
    """
    result = []
    in_quotation = False

    for char in text:
        if char == '「' or char == '『':
            in_quotation = True
            result.append(char)
        elif char == '」' or char == '』':
            in_quotation = False
            result.append(char)
        elif char in punctuation_to_remove and not in_quotation:
            # 引用符外の句読点のみ削除
            continue
        else:
            result.append(char)

    return ''.join(result)

def _remove_punctuation_from_subtitles(self, subtitles):
    """
    句読点を削除（引用符内は保持）

    削除対象: 。、！？（引用符外のみ）
    削除しない: 「」『』内の句読点、カギカッコ自体
    """
    punctuation_to_remove = ['。', '！', '？', '，', '．']

    cleaned_subtitles = []

    for subtitle in subtitles:
        # 🔥 NEW: 引用符内の句読点は残す処理
        line1 = self._remove_punctuation_except_in_quotation(
            subtitle.text_line1,
            punctuation_to_remove
        )

        line2 = ""
        if subtitle.text_line2:
            line2 = self._remove_punctuation_except_in_quotation(
                subtitle.text_line2,
                punctuation_to_remove
            )

        # 空の字幕をスキップ
        if not line1.strip() and not line2.strip():
            continue

        cleaned_subtitles.append(...)

    return cleaned_subtitles
```

#### 📌 引用符内の改行処理（v4.2の重要機能）

**目的**: 引用符内の改行文字（\n）を自動削除し、字幕表示を正しくする

**背景**:
- 台本で「これが\n我が道だ」のように引用符内に改行がある場合
- 改行を含めて字幕を生成すると表示が崩れる
- 引用符内の改行は削除し、1つの連続したテキストとして処理すべき

**解決策**:
- 引用符（「」『』）内の改行文字を自動削除
- 引用符外の改行は従来通り字幕分割に使用
- characters配列、start_times、end_times からも該当部分を削除

**実装の詳細**:

```python
# src/generators/subtitle_generator.py

def generate_subtitles_from_char_timings(self, audio_timing_data):
    # 🔥 NEW: 引用符内の改行を削除（常に実行）
    cleaned_characters = []
    cleaned_start_times = []
    cleaned_end_times = []
    in_quotation = False

    for i, char in enumerate(characters):
        if char == '「' or char == '『':
            in_quotation = True
            cleaned_characters.append(char)
            cleaned_start_times.append(start_times[i])
            cleaned_end_times.append(end_times[i])
        elif char == '」' or char == '』':
            in_quotation = False
            cleaned_characters.append(char)
            cleaned_start_times.append(start_times[i])
            cleaned_end_times.append(end_times[i])
        elif char == '\n' and in_quotation:
            # 引用符内の改行はスキップ（タイミングも削除）
            self.logger.debug(f"Skipping newline inside quotation at index {i}")
            continue
        else:
            cleaned_characters.append(char)
            cleaned_start_times.append(start_times[i])
            cleaned_end_times.append(end_times[i])

    # 以降は cleaned_* を使用
    characters = cleaned_characters
    start_times = cleaned_start_times
    end_times = cleaned_end_times
```

#### 📌 長い引用符の分割処理（v4.2の重要機能）

**目的**: 30文字を超える引用符を適切に分割する

**背景**:
- 「織田信長は、天下布武を掲げ、延暦寺を焼き討ちにし、長篠の戦いで武田軍を破った。」
- このような長い引用符は1つの字幕に収まらない
- カンマ（、）で分割することで読みやすくする

**解決策**:
- 30文字を超える引用符をカンマ位置で分割
- 引用符内の句読点分割は行わない（従来の仕様）
- 3行になった場合、line3を次の字幕に移動

**実装の詳細**:

```python
# src/generators/subtitle_generator.py

# 長い引用符の分割
if len(remaining_chars) > 30:
    # カンマで分割
    comma_positions = [i for i, c in enumerate(remaining_chars[:30]) if c == '、']
    if comma_positions:
        split_pos = comma_positions[-1] + 1  # カンマの直後
    else:
        split_pos = 30  # カンマがない場合は30文字で強制分割
```

**注意事項**:
- `remove_punctuation_in_display`のデフォルト値は**コード内でFalse**に変更済み
- 設定ファイルで`true`を指定しても、引用符内の句読点は保持される
- Phase 6の`phase_06_subtitles.py`が句読点削除処理を管理
- `SubtitleGenerator`は引用符処理に特化

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

### Phase 3: AI画像生成（AI Image Generation）

**責務**: Stable Diffusion APIを使用して動画本編用の高品質画像を生成

**入力**:
- `working/{subject}/01_script/script.json`

**処理**:
1. 台本からセクションごとにキーワードを抽出
2. キーワードが不足している場合、Claude APIで自動生成
3. 各キーワードでStable Diffusion画像を生成
   - Claudeでプロンプト最適化
   - スタイル自動選択（写実、油絵、浮世絵等）
4. 生成した画像を1920x1080にリサイズ（PNG形式）
5. 元のJPEGファイルを削除

**出力**:
- `working/{subject}/03_images/generated/section_XX_sd_XXXXXXXX_YYYYMMDD_HHMMSS.png` (1920x1080)
- `working/{subject}/03_images/classified.json`
- `working/{subject}/03_images/generation_log.json`

#### 📌 画像生成サイズとリサイズ（重要）

**問題**: Phase 03とPhase 08のサイズ混同が頻発する

**Phase 03の仕様**:
```yaml
# config/phases/image_collection.yaml

ai_generation:
  stable_diffusion:
    # SD API生成サイズ（SDXL標準）
    width: 1344    # 16:9に近い
    height: 768

    # ↓ リサイズ処理で変換
    # 最終出力: 1920x1080 PNG（動画本編用）
```

**処理フロー**:
```
1. SD API生成: 1344x768 (JPEG)
   ↓
2. リサイズ処理: resize_images_to_1920x1080()
   ↓
3. 最終出力: 1920x1080 (PNG)
   ↓
4. 元のJPEGファイル削除（1344x768のJPEGは残らない）
```

**実装の詳細**:

```python
# src/phases/phase_03_images.py

def _generate_section_images(self, ...):
    # 🔥 Phase 03専用: SD生成サイズを設定ファイルから取得
    sd_config = self.phase_config.get("ai_generation", {}).get("stable_diffusion", {})
    width = sd_config.get("width", 1344)
    height = sd_config.get("height", 768)

    self.logger.debug(f"Phase 03 SD generation size: {width}x{height}")

    # 画像生成（サイズを明示的に指定）
    image = generator.generate_image(
        keyword=keyword,
        atmosphere=section.atmosphere,
        section_context=section_context_with_narration,
        image_type=image_type,
        style=style,
        section_id=section_id,
        is_first_image=is_first_image,
        width=width,      # ← 設定ファイルから取得
        height=height     # ← 設定ファイルから取得
    )
```

```python
# リサイズ処理と元ファイル削除

# 1. リサイズ実行（JPEG → PNG）
resized_files = resize_images_to_1920x1080(
    generated_dir,
    logger=self.logger,
    output_format="PNG"  # Phase 3は動画本編用にPNG形式
)

# 2. 元のJPEGファイルを削除（PNG形式に変換されたため）
jpeg_files = list(generated_dir.glob("*.jpg"))
if jpeg_files:
    self.logger.info(f"Removing {len(jpeg_files)} original JPEG files...")
    for jpeg_file in jpeg_files:
        try:
            jpeg_file.unlink()
            self.logger.debug(f"Deleted: {jpeg_file.name}")
        except Exception as e:
            self.logger.warning(f"Failed to delete {jpeg_file.name}: {e}")
    self.logger.info(f"✓ Removed {len(jpeg_files)} original JPEG files")
```

#### 📌 キーワード自動生成（Claude API）

**目的**: 台本でキーワードが不足している場合、Claude APIで自動生成

**動作条件**:
- `image_keywords`が空: 3つ全て生成
- `image_keywords`が1つ: 2つ追加生成
- `image_keywords`が3つ以上: キーワード生成をスキップ

**ログ例**:
```
⚠️  WARNING: Section 2 has insufficient keywords (1/3)
🔄 Generating additional keywords via Claude API...
✅ Generated keywords: ["キーワード2", "キーワード3"]
Final keywords for Section 2: ["既存キーワード1", "キーワード2", "キーワード3"]
```

**設定例**:
```yaml
# config/phases/image_collection.yaml

ai_generation:
  # Claude APIキー（キーワード生成用）
  claude_api_key_env: "CLAUDE_API_KEY"

  # プロンプト最適化（強く推奨）
  optimize_prompts: true
```

#### 📌 Phase 03とPhase 08の分離（重要）

**混同しやすいポイント**:
- 両者とも**SD生成サイズは1344x768**（SDXL標準）
- **リサイズ後のサイズが異なる**
- **用途が異なる**（動画本編 vs サムネイル）

| 項目 | Phase 03（動画本編） | Phase 08（サムネイル） |
|------|---------------------|----------------------|
| SD生成サイズ | 1344x768 (JPEG) | 1344x768 (JPEG) |
| リサイズ後 | **1920x1080 PNG** | **1280x720 PNG** |
| 用途 | 動画本編の画像 | YouTubeサムネイル |
| 設定ファイル | `image_collection.yaml` | コード内で動的作成 |
| ジェネレーター | `ImageGenerator` | `IntellectualCuriosityGenerator` |
| 元ファイル処理 | JPEG削除 | JPEG削除（内部） |

**重要**: Phase 03とPhase 08は完全に独立して動作します。相互に影響を与えません。

---

### Phase 8: サムネイル生成（Thumbnail Generation）

**責務**: YouTube用のサムネイルを生成

**入力**:
- `working/{subject}/01_script/script.json`
- `working/{subject}/03_images/classified.json`（従来の方法の場合のみ）

**処理**:
1. 台本から`thumbnail`フィールドを読み込み（`upper_text`, `lower_text`）
2. Stable Diffusion APIで背景画像を生成（デフォルト）
3. 背景画像をリサイズ（1344x768 → 1280x720）
4. テキストオーバーレイ（上部・下部）
5. 最終的なサムネイルを保存

**出力**:
- `working/{subject}/08_thumbnail/thumbnails/*.png` (1280x720)
- `working/{subject}/08_thumbnail/metadata.json`

#### 📌 サムネイル画像生成サイズ（Phase 03との違い）

**Phase 08の仕様**:
```yaml
# config/phases/thumbnail_generation.yaml

# デフォルト: Stable Diffusion生成
use_intellectual_curiosity: true
use_stable_diffusion: true

# Phase 08専用のSD設定（コード内で動的作成）
stable_diffusion:
  width: 1344    # SD APIで1344x768を生成（SDXL標準サイズ）
  height: 768    # ↓ 1280x720にリサイズされる
  api_key_env: "STABILITY_API_KEY"

# 最終出力サイズ
output:
  resolution: [1280, 720]  # YouTubeサムネイル標準
```

**処理フロー**:
```
1. SD API生成: 1344x768 (JPEG)
   ↓
2. IntellectualCuriosityGeneratorが内部でリサイズ
   ↓
3. 最終出力: 1280x720 (PNG)
   ↓
4. テキストオーバーレイ（upper_text, lower_text）
```

**実装の詳細**:

```python
# src/phases/phase_08_thumbnail.py

def _generate_with_intellectual_curiosity(self, script_data):
    # Phase 8専用の設定を上書き
    phase8_config = self.phase_config.copy()
    phase8_config["use_stable_diffusion"] = True  # SD生成を有効化
    phase8_config["stable_diffusion"] = {
        "width": 1344,   # SD APIで1344x768を生成（SDXL標準サイズ）
        "height": 768,   # 1280x720にリサイズされる
        "api_key_env": "STABILITY_API_KEY"
    }
    phase8_config["output"] = {
        "resolution": [1280, 720]  # 最終的なサムネイルサイズ
    }

    generator = create_intellectual_curiosity_generator(
        config=phase8_config,
        logger=self.logger
    )

    # サムネイルを1枚のみ生成
    thumbnail_paths = generator.generate_thumbnails(
        subject=self.subject,
        output_dir=thumbnail_dir,
        context=script_data,
        num_variations=1  # Phase 8は1枚のみ
    )
```

```python
# src/generators/intellectual_curiosity_generator.py

def generate_thumbnails(self, subject, output_dir, context, num_variations):
    # 1. 背景画像を生成（SD: 1344x768）
    background = self._generate_background_image_sd(subject, context)

    # 2. 背景画像をリサイズ（1344x768 → 1280x720）
    background = background.resize(self.canvas_size, Image.Resampling.LANCZOS)
    self.logger.info(f"Background resized to: {background.size}")

    # 3. テキストオーバーレイ
    thumbnail = self._generate_single_thumbnail(
        background=background,
        top_text=upper_text,      # script.jsonから取得
        line1=lower_text,         # script.jsonから取得
        line2="",
        output_dir=output_dir,
        index=1,
        subject=subject
    )
```

#### 📌 Phase 03とPhase 08の独立性（絶対に混同しないこと）

**なぜ分離が重要か**:
- 用途が異なる（動画本編 vs サムネイル）
- リサイズ後のサイズが異なる
- テキストオーバーレイの有無
- ファイル形式の最適化（動画品質 vs YouTube 2MB制限）

**確認方法**:
```bash
# Phase 03の出力を確認
ls -lh data/working/{subject}/03_images/generated/
# 期待: section_XX_sd_*.png (1920x1080)

# Phase 08の出力を確認
ls -lh data/working/{subject}/08_thumbnail/thumbnails/
# 期待: *.png (1280x720)
```

**トラブルシューティング**:

| 問題 | 原因 | 解決策 |
|------|------|--------|
| Phase 03の画像が1344x768のまま | リサイズ処理が実行されていない | `resize_images_to_1920x1080()`が呼ばれているか確認 |
| Phase 03にJPEGとPNGが混在 | 元のJPEGファイルが削除されていない | 最新版で修正済み（JPEGは自動削除） |
| Phase 08のサイズが間違っている | `output.resolution`が正しく設定されていない | `[1280, 720]`を確認 |

---

### 最新の改善点（v4.1 - Phase 03/08）

#### 📌 Phase 03のリサイズ処理修正（重要）

**問題**: Phase 03で生成された画像が1344x768のままで1920x1080にリサイズされない

**根本原因**:
1. `phase_03_images.py`で`ImageGenerator.generate_image()`を呼び出す際、`width`/`height`パラメータを指定していなかった
2. そのため、`ImageGenerator`のデフォルト値（1344x768）が使われていた
3. リサイズ処理は実行されるが、元のJPEGファイル（1344x768）が削除されず残っていた

**解決策**:
1. 設定ファイル（`image_collection.yaml`）からサイズを読み込む
2. `generate_image()`にサイズパラメータを明示的に渡す
3. リサイズ後、元のJPEGファイルを自動削除

**修正内容（v4.1）**:
- `src/phases/phase_03_images.py`を修正
- SD生成サイズを設定ファイルから取得
- リサイズ後のJPEGファイル削除処理を追加

---

### 最新の改善点（v3.0）**:

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

## ⚙️ 設定ファイルの構造と優先度

### 設定ファイルの種類と役割

システムでは、以下の3種類の設定ファイルを使用します：

1. **`config/phases/*.yaml`** - 各フェーズの基本設定
2. **`config/variations/*.yaml`** - バリエーション設定（選択肢）
3. **`config/genres/*.yaml`** - ジャンル別設定

### 設定ファイルの優先度

**優先度（高い順）**:

1. **コマンドライン引数**
   - `--genre`: ジャンル指定
   - `--audio-var`: 音声バリエーション指定
   - `--text-layout`: サムネイルテキストレイアウト指定
   - `--thumbnail-style`: サムネイルスタイル指定

2. **ジャンル設定** (`config/genres/*.yaml`)
   - プロンプトテンプレートのパス
   - YouTube認証情報
   - BGMライブラリのパス
   - TikTok設定

3. **フェーズ設定** (`config/phases/*.yaml`)
   - 各フェーズの処理方法
   - API設定（サービス選択、パラメータ）
   - デフォルト値

4. **バリエーション設定** (`config/variations/*.yaml`)
   - 選択可能なバリエーションのリスト
   - 各バリエーションの詳細設定

### `config/phases` と `config/variations` の違い

#### `config/phases/*.yaml`（処理方法の設定）

各フェーズの**処理方法**や**API設定**を定義します。

**例: `config/phases/audio_generation.yaml`**
```yaml
service: "kokoro"  # 使用する音声サービス
with_timestamps: true  # タイムスタンプを取得するか
punctuation_pause:
  enabled: true
  pause_duration:
    period: 0.8
```

**例: `config/phases/thumbnail_generation.yaml`**
```yaml
stable_diffusion:
  style: "photorealistic"  # SDのスタイル（photorealistic, oil_painting, ukiyo-e など）
  width: 1344
  height: 768
```

#### `config/variations/*.yaml`（選択肢の定義）

ユーザーが選べる**バリエーション**のリストを定義します。

**例: `config/variations/audio.yaml`**
```yaml
audio_variations:
  - id: "kokoro_standard"
    service: "kokoro"
    voice: "jf_alpha"
    speed: 1.0
  
  - id: "elevenlabs_standard"
    service: "elevenlabs"
    voice_id: "3JDquces8E8bkmvbh6Bc"
    model: "eleven_multilingual_v2"
```

**例: `config/variations/thumbnail_text.yaml`**
```yaml
text_layouts:
  - id: "two_line_center_adjusted"
    description: "中央揃え2行レイアウト（バランス改善版）"
    upper:
      position: [640, 120]
      font_size: 65
      color: "#FFFF00"
  
  - id: "two_line_upper_lower_max_impact"
    description: "横書き・上部特大＆下部特大（バランス改善版）"
    upper:
      position: [640, 130]
      font_size: 70
```

### 設定ファイルの読み込み方法

#### 1. フェーズ設定の読み込み

```python
# Phase 2の設定を読み込む
phase_config = config.get_phase_config(2)
service = phase_config.get("service", "kokoro")
```

#### 2. バリエーション設定の読み込み

```python
# 音声バリエーションのリストを読み込む
audio_config = config.get_variation_config("audio")
variations = audio_config.get("audio_variations", [])

# 特定のバリエーションを検索
variation_id = "kokoro_standard"
for var in variations:
    if var["id"] == variation_id:
        # このバリエーションの設定を使用
        break
```

#### 3. ジャンル設定の読み込み

```python
# ジャンル設定を読み込む
genre_config = config.get_genre_config("ijin")
prompt_template_path = genre_config["prompts"]["thumbnail"]
```

### 実行時にどの設定が使われるか

#### 一括実行時 (`generate`)

```powershell
python -m src.cli generate "エリサ・ラム事件" \
  --genre urban \
  --audio-var kokoro_standard \
  --text-layout two_line_center_adjusted \
  --thumbnail-style dramatic_side
```

**実行フロー**:

1. **ジャンル設定の読み込み** (`config/genres/urban.yaml`)
   - プロンプトテンプレート: `config/prompts/thumbnail/urban.j2`
   - YouTube認証情報: `config/.youtube_credentials_urban.json`
   - BGMライブラリ: `assets/bgm/urban`

2. **Phase 2（音声生成）**
   - `config/phases/audio_generation.yaml` から処理方法を読み込み
   - `--audio-var kokoro_standard` → `config/variations/audio.yaml` から該当バリエーションを検索
   - 見つかったバリエーションの設定を使用

3. **Phase 8（サムネイル生成）**
   - `config/phases/thumbnail_generation.yaml` から処理方法を読み込み
   - `--text-layout two_line_center_adjusted` → `config/variations/thumbnail_text.yaml` から該当レイアウトを検索
   - `--thumbnail-style dramatic_side` → `config/variations/thumbnail_style.yaml` から該当スタイルを検索
   - `config/genres/urban.yaml` からプロンプトテンプレートを読み込み

#### 単発実行時 (`run-phase`)

```powershell
python -m src.cli run-phase "エリサ・ラム事件" --phase 8 \
  --text-layout two_line_center_adjusted \
  --thumbnail-style dramatic_side \
  --genre urban
```

**実行フロー**:

1. **Phase 8の設定を読み込み**
   - `config/phases/thumbnail_generation.yaml` から処理方法を読み込み
   - `--genre urban` → `config/genres/urban.yaml` からプロンプトテンプレートを読み込み

2. **バリエーション設定の読み込み**
   - `--text-layout two_line_center_adjusted` → `config/variations/thumbnail_text.yaml` から該当レイアウトを検索
   - `--thumbnail-style dramatic_side` → `config/variations/thumbnail_style.yaml` から該当スタイルを検索

### 設定ファイルの優先順位の具体例

#### 例1: Phase 8（サムネイル生成）

**優先順位（高い順）**:

1. **コマンドライン引数** (`--text-layout`, `--thumbnail-style`)
   ```powershell
   python -m src.cli run-phase "エリサ・ラム事件" --phase 8 \
     --text-layout two_line_center_adjusted
   ```

2. **ジャンル設定** (`config/genres/urban.yaml`)
   ```yaml
   prompts:
     thumbnail: "config/prompts/thumbnail/urban.j2"
   ```

3. **フェーズ設定** (`config/phases/thumbnail_generation.yaml`)
   ```yaml
   stable_diffusion:
     style: "photorealistic"  # デフォルトスタイル
     width: 1344
     height: 768
   ```

4. **バリエーション設定** (`config/variations/thumbnail_text.yaml`)
   ```yaml
   text_layouts:
     - id: "two_line_center_adjusted"
       upper:
         font_size: 65  # デフォルトのフォントサイズ
   ```

**注意**: 現在、Phase 8では `thumbnail_generation.yaml` の `text_style_v3` による上書きは無効化されています。全てのテキストスタイルは `config/variations/thumbnail_text.yaml` から直接選ばれます。

#### 例2: Phase 2（音声生成）

**優先順位（高い順）**:

1. **コマンドライン引数** (`--audio-var`)
   ```powershell
   python -m src.cli generate "エリサ・ラム事件" --audio-var kokoro_standard
   ```

2. **フェーズ設定** (`config/phases/audio_generation.yaml`)
   ```yaml
   service: "kokoro"  # デフォルトサービス
   with_timestamps: true
   ```

3. **バリエーション設定** (`config/variations/audio.yaml`)
   ```yaml
   audio_variations:
     - id: "kokoro_standard"
       service: "kokoro"
       voice: "jf_alpha"
       speed: 1.0
   ```

**実装の詳細**:
- `--audio-var` が指定されていない場合、`audio_generation.yaml` の `service` とデフォルト設定が使用される
- `--audio-var` が指定されている場合、`config/variations/audio.yaml` から該当バリエーションを検索し、その設定を使用

### サムネイル生成の設定フロー（Phase 8）

```
1. コマンドライン引数
   --text-layout two_line_center_adjusted
   --thumbnail-style dramatic_side
   --genre urban
   ↓
2. ジャンル設定読み込み (config/genres/urban.yaml)
   prompts.thumbnail → "config/prompts/thumbnail/urban.j2"
   ↓
3. フェーズ設定読み込み (config/phases/thumbnail_generation.yaml)
   stable_diffusion.style → "photorealistic"
   stable_diffusion.width → 1344
   ↓
4. バリエーション設定読み込み (config/variations/thumbnail_text.yaml)
   text_layouts → [two_line_center_adjusted, ...]
   ↓
5. バリエーション設定読み込み (config/variations/thumbnail_style.yaml)
   styles → [dramatic_side, ...]
   ↓
6. 統合
   - プロンプト: urban.j2（ジャンル設定から）
   - SDスタイル: photorealistic（フェーズ設定から）
   - テキストレイアウト: two_line_center_adjusted（バリエーション設定から）
   - スタイル: dramatic_side（バリエーション設定から）
```

### 音源（BGM）の設定

BGMの設定は以下の2箇所で管理されます：

1. **`config/phases/bgm_selection.yaml`** - BGM選択の処理方法
   - デフォルト音量
   - フェードイン/アウト時間
   - トラック間のトランジション設定

2. **`config/genres/*.yaml`** - ジャンル別BGMライブラリのパス
   ```yaml
   bgm_library: "assets/bgm/ijin"
   ```

3. **`assets/bgm/{genre}/`** - 実際のBGMファイル
   - 固定トラック構成（intro, main, outro など）

**BGM選択の優先順位**:

1. ジャンル設定のBGMライブラリパス
2. フェーズ設定のデフォルト値
3. 固定トラック構成（`bgm_selection.yaml` の `fixed_bgm_structure`）

---

## 🎛️ 設定ファイルの完全な例

### config/phases/audio_generation.yaml（v4.0完全版）

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
# 🔥 v4.0: タイミング抽出設定
# ========================================
# ElevenLabs Forced Alignment（台本と音声の完璧なアラインメント）
use_elevenlabs_fa: true

# ElevenLabs API Key（環境変数から自動取得）
# .envファイルに ELEVENLABS_API_KEY=your_key_here を設定
elevenlabs_api_key: null  # 実際には環境変数から読み込まれます

# ========================================
# Whisper設定（フォールバック用）
# ========================================
whisper:
  enabled: true                    # ElevenLabs FA失敗時に使用
  model: "small"                   # 日本語認識精度向上
  language: "ja"
  device: "auto"

  # 🔥 stable-ts設定（音声と字幕の高精度同期）
  use_stable_ts: true
  suppress_silence: true
  vad: true
  vad_threshold: 0.35

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
# 🔥 v4.0: タイミング設定（完璧な同期）
# ========================================
timing:
  min_display_duration: 1.0
  max_display_duration: 6.0

  # 🔥 文字レベルタイミングの正確さを100%活用
  lead_time: 0.0         # リードタイムなし（音声と完全同期）
  subtitle_gap: 0.0      # ギャップなし（内部で0.01秒のMIN_GAPを使用）

  prevent_overlap: true
  overlap_priority: "next_subtitle"

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

# ========================================
# 🔥 v4.2: 句読点除去設定
# ========================================
# 句読点除去（引用符内は保持）
# デフォルト値はコード内でFalseに変更済み
# 設定ファイルでtrueを指定しても、引用符（「」『』）内の句読点は保持される
# 削除対象: 。！？（引用符外のみ）
# 保持対象: 引用符内の句読点、カギカッコ自体
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
   - **注意**: 引用符内の改行は自動削除される（v4.2）

4. **🔥 引用符の使い方（v4.2）**
   - 引用符内の句読点は自動的に保持される
   - 長い引用（30文字超）は自動でカンマ分割される
   - 引用符内に改行を入れても自動削除される
   - 例: `「天下布武、これが我が道だ。」` → 句読点がそのまま表示される

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

**問題**: 引用符内の句読点が削除されてしまう
```yaml
# 🔥 v4.2で解決済み
# remove_punctuation_in_displayの設定に関わらず、
# 引用符（「」『』）内の句読点は自動的に保持される
# コードの修正のみで対応済み、設定変更不要
```

**問題**: 引用符内に改行があると字幕が崩れる
```yaml
# 🔥 v4.2で解決済み
# 引用符内の改行文字（\n）は自動的に削除される
# 台本の修正不要、自動処理で対応
```

**問題**: 長い引用符が1つの字幕に収まらない
```yaml
# 🔥 v4.2で解決済み
# 30文字を超える引用符は自動でカンマ位置で分割される
# 分割ロジックがカンマを優先して適切に処理
```

---

**設計書バージョン**: 4.2
**最終更新日**: 2025年11月14日
**次回レビュー予定**: 新機能追加時

---

## 📋 Phase 03 & Phase 08 確認チェックリスト

このチェックリストは、Phase 03とPhase 08の動作を確認する際に使用します。

### Phase 03（AI画像生成）

- [x] **キーワード自動生成**: キーワード空の場合、Claude APIで自動生成される
- [x] **SD API生成サイズ**: 1344x768 (JPEG) で生成される
- [x] **リサイズ処理**: `resize_images_to_1920x1080()`で1920x1080に変換される
- [x] **保存ファイル**: 1920x1080 PNG形式で保存される
- [x] **元ファイル削除**: 元の1344x768 JPEGファイルが自動削除される
- [x] **エラーハンドリング**: 画像生成失敗時も続行し、適切にログ出力
- [x] **コスト表示**: セクションごとと合計のコストが正しく表示される

### Phase 08（サムネイル生成）

- [x] **使用API**: Stable Diffusion (IntellectualCuriosityGenerator経由)
- [x] **SD API生成サイズ**: 1344x768 (JPEG) で生成される
- [x] **リサイズ処理**: 内部で1280x720に変換される
- [x] **保存ファイル**: 1280x720 PNG形式で保存される
- [x] **upper_text配置**: 上部中央に配置され、色が正しい
- [x] **lower_text配置**: 下部中央に配置され、色が正しい
- [x] **改行処理**: `\n`と全角スペースが機能している
- [x] **Phase 03との独立性**: Phase 03と完全に独立して動作する

### 確認コマンド

```bash
# Phase 03の出力を確認
ls -lh data/working/{subject}/03_images/generated/
file data/working/{subject}/03_images/generated/*.png | head -3

# Phase 08の出力を確認
ls -lh data/working/{subject}/08_thumbnail/thumbnails/
file data/working/{subject}/08_thumbnail/thumbnails/*.png
```

### 期待される出力

```bash
# Phase 03
section_01_sd_*.png: PNG image data, 1920 x 1080, 8-bit/color RGB
section_02_sd_*.png: PNG image data, 1920 x 1080, 8-bit/color RGB

# Phase 08
*.png: PNG image data, 1280 x 720, 8-bit/color RGB
```
