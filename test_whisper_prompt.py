# test_whisper_prompt.py を作成して実行
import whisper

# Section 2の音声とテキストでテスト
model = whisper.load_model("small")

# テスト1: initial_prompt なし
result1 = model.transcribe(
    "data/working/織田信長/02_audio/sections/section_02.mp3",
    language="ja",
    word_timestamps=False
)
print("=== Without initial_prompt ===")
print(f"Recognized: {result1['text']}")
print(f"Length: {len(result1['text'])} chars")

# テスト2: initial_prompt あり（全文）
full_text = "信長は革新的な戦略で次々と敵を倒していきます。鉄砲を大量に使い、比叡山を焼き討ちし、一向一揆を鎮圧。「天下布武」の印を掲げ、古い権威に立ち向かいました。まさに天下統一まであと一歩というところまで来ていたのです。"
result2 = model.transcribe(
    "data/working/織田信長/02_audio/sections/section_02.mp3",
    language="ja",
    word_timestamps=False,
    initial_prompt=full_text
)
print("\n=== With initial_prompt (full text) ===")
print(f"Recognized: {result2['text']}")
print(f"Length: {len(result2['text'])} chars")

# テスト3: initial_prompt あり（前半のみ）
first_half = "信長は革新的な戦略で次々と敵を倒していきます。"
result3 = model.transcribe(
    "data/working/織田信長/02_audio/sections/section_02.mp3",
    language="ja",
    word_timestamps=False,
    initial_prompt=first_half
)
print("\n=== With initial_prompt (first half only) ===")
print(f"Recognized: {result3['text']}")
print(f"Length: {len(result3['text'])} chars")