# test_azure_speech.py
import os
from pathlib import Path
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

# .envファイルを読み込み（config/.env を優先、なければルートの.env）
project_root = Path(__file__).parent
env_path = project_root / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✓ Loaded .env from: {env_path}")
else:
    # ルートディレクトリの.envも試す
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        print(f"✓ Loaded .env from: {env_path}")
    else:
        print(f"⚠ .env file not found (searched: config/.env and .env)")

# 環境変数から取得
api_key = os.getenv("AZURE_SPEECH_KEY")
region = os.getenv("AZURE_SPEECH_REGION", "japaneast")

if not api_key:
    print("✗ エラー: AZURE_SPEECH_KEY 環境変数が設定されていません")
    exit(1)

print(f"API Key: {api_key[:10]}... (先頭10文字)")
print(f"Region: {region}")

# Speech設定
speech_config = speechsdk.SpeechConfig(
    subscription=api_key,
    region=region
)
speech_config.speech_synthesis_voice_name = "ja-JP-NanamiNeural"

# 音声生成テスト
synthesizer = speechsdk.SpeechSynthesizer(
    speech_config=speech_config,
    audio_config=None
)

result = synthesizer.speak_text_async("こんにちは、テストです。").get()

if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("✓ Azure Speech API接続成功！")
    with open("test_azure.mp3", "wb") as f:
        f.write(result.audio_data)
    print("✓ test_azure.mp3 を生成しました")
else:
    print(f"✗ エラー: {result.reason}")

