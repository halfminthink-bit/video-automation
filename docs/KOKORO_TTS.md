# Kokoro TTS 統合ガイド

Kokoro TTS FastAPIは、**完全無料**のテキスト音声合成（TTS）システムで、単語レベルのタイムスタンプを直接取得できます。

## 📋 概要

- **完全無料**: APIキー不要、クレジット制限なし
- **タイムスタンプ対応**: 単語レベルのタイミング情報を取得
- **高品質**: 自然な音声合成
- **多言語対応**: 日本語を含む複数言語に対応
- **ローカル実行**: Dockerで簡単にセットアップ

---

## 🚀 セットアップ

### 1. Docker Composeでサーバーを起動

```bash
# CPUバージョン（推奨）
docker-compose -f docker-compose-kokoro.yml up -d

# ログを確認
docker-compose -f docker-compose-kokoro.yml logs -f
```

### 2. APIが起動したか確認

```bash
# 利用可能な音声のリストを取得
curl http://localhost:8880/v1/audio/voices

# または、ブラウザで Web UI を開く
open http://localhost:8880/web
```

### 3. 環境変数を設定（オプション）

`config/.env` ファイルに以下を追加（デフォルトでOK）:

```bash
KOKORO_API_URL=http://localhost:8880
```

### 4. 設定ファイルを更新

`config/phases/audio_generation.yaml` で使用するサービスを選択:

```yaml
# "kokoro" に変更
service: "kokoro"

# Kokoro TTS の設定
kokoro:
  api_url: "http://localhost:8880"
  voice: "jf_alpha"  # または af_sarah, af_sky など
  speed: 1.0
  response_format: "mp3"
```

---

## 🎤 利用可能な音声

### 女性の声（American Female）

| 音声名 | 特徴 | 推奨 |
|--------|------|------|
| `af_bella` | 人気、安定した音質 | ⭐ |
| `af_sarah` | 人気、自然な音質 | ⭐ |
| `af_sky` | 明るめの声 | |
| `af_heart` | 落ち着いた声 | |
| `af_alloy` | バランスが良い | |
| `af_aoede` | クリアな声 | |
| `af_jessica` | 温かみのある声 | |
| `af_kore` | エネルギッシュ | |
| `af_nicole` | 落ち着き | |
| `af_nova` | モダンな声 | |
| `af_river` | 滑らかな声 | |

### その他の音声

- **男性の声**: `am_*` プレフィックス
- **英国英語**: `bf_*` / `bm_*` プレフィックス
- **日本語**: `jf_*` プレフィックス（利用可能な場合）

---

## 💻 使用方法

### Phase 2で音声を生成

```bash
# Kokoro TTS を使用して音声生成
python -m src.cli run-phase "織田信長" --phase 2
```

### Python コードでの使用例

```python
from pathlib import Path
from src.generators.kokoro_audio_generator import KokoroAudioGenerator

# 生成器を初期化
generator = KokoroAudioGenerator(
    api_url="http://localhost:8880",
    voice="af_bella"
)

# 音声を生成
result = generator.generate_with_timestamps(
    text="これはテストです。",
    output_path=Path("output.mp3"),
    speed=1.0
)

# タイムスタンプ情報を取得
print(f"音声の長さ: {result['alignment']['character_end_times_seconds'][-1]:.2f}秒")
print(f"文字数: {len(result['alignment']['characters'])}")
```

---

## 📊 出力フォーマット

### audio_timing.json

```json
{
  "sections": [
    {
      "section_id": 1,
      "audio_path": "C:\\...\\section_01.mp3",
      "duration": 45.0,
      "alignment": {
        "characters": ["こ", "れ", "は", "テ", "ス", "ト"],
        "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
        "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
      }
    }
  ]
}
```

---

## 🔧 トラブルシューティング

### Docker起動エラー

```bash
# ポート8880が使用中か確認
netstat -ano | findstr :8880

# 別のポートを使う場合
docker run -p 9000:8880 ghcr.io/remsky/kokoro-fastapi-cpu:latest
```

その後、`config/.env` を更新:

```bash
KOKORO_API_URL=http://localhost:9000
```

### API接続エラー

```bash
# コンテナが起動しているか確認
docker ps | grep kokoro

# ログを確認
docker-compose -f docker-compose-kokoro.yml logs
```

### 音声品質の調整

`config/phases/audio_generation.yaml` で速度を調整:

```yaml
kokoro:
  speed: 0.9  # ゆっくり
  # または
  speed: 1.2  # 速め
```

---

## 🔄 ElevenLabsに戻す

Kokoro TTSから ElevenLabs に戻す場合:

```yaml
# config/phases/audio_generation.yaml
service: "elevenlabs"  # "kokoro" から変更
```

---

## 🎯 パフォーマンス比較

| 項目 | Kokoro TTS | ElevenLabs |
|------|------------|------------|
| 価格 | **完全無料** | 有料（$5-$330/月） |
| タイムスタンプ | ✅ 標準対応 | ✅ 対応 |
| 音質 | 高品質 | 最高品質 |
| 速度 | 高速（ローカル） | 中程度（API） |
| セットアップ | Docker必須 | APIキーのみ |
| オフライン | ✅ 可能 | ❌ 不可 |

---

## 📚 参考リンク

- [Kokoro FastAPI GitHub](https://github.com/remsky/kokoro-fastapi)
- [Kokoro TTS 公式ドキュメント](https://huggingface.co/hexgrad/Kokoro-82M)
- [Docker Compose 公式ドキュメント](https://docs.docker.com/compose/)

---

## 🆘 サポート

問題が発生した場合:

1. [GitHub Issues](https://github.com/halfminthink-bit/video-automation/issues) で報告
2. ログファイルを確認: `logs/phase_02_*.log`
3. Docker ログを確認: `docker-compose logs kokoro-tts`

---

**注意**: Kokoro TTS は完全無料ですが、ElevenLabsと比較して音質がわずかに劣る場合があります。用途に応じて選択してください。
