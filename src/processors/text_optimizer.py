"""
テキスト最適化器

Claude APIを使用して、音声合成用にテキストを最適化する。
固有名詞の読み仮名追加、難読漢字のひらがな化など。
"""

import logging
from typing import Optional
from anthropic import Anthropic


class TextOptimizer:
    """Claude APIでテキストを音声読み上げ用に最適化"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            api_key: Anthropic APIキー
            model: 使用するClaudeモデル
            logger: ロガー
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.logger = logger or logging.getLogger(__name__)

    def optimize_for_tts(
        self,
        text: str,
        context: Optional[str] = None
    ) -> dict:
        """
        テキストを音声合成用に最適化

        Args:
            text: 最適化するナレーション
            context: 文脈情報（偉人の生涯、時代背景など）

        Returns:
            {
                "tts_text": str,      # 音声用（平仮名のみ）
                "display_text": str   # 字幕用（元の漢字）
            }
        """
        prompt = self._build_optimization_prompt(text, context)

        self.logger.debug(f"Optimizing text: {text[:50]}...")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            optimized_response = response.content[0].text.strip()
            self.logger.info(f"Text optimized successfully")

            # レスポンスをパース（JSON形式を期待）
            import json
            try:
                result = json.loads(optimized_response)
                # tts_textとdisplay_textが両方存在するか確認
                if "tts_text" in result and "display_text" in result:
                    return result
                else:
                    self.logger.warning("Response missing required fields, using original text")
                    return {
                        "tts_text": text,
                        "display_text": text
                    }
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse JSON response, using original text")
                return {
                    "tts_text": text,
                    "display_text": text
                }

        except Exception as e:
            self.logger.error(f"Failed to optimize text: {e}")
            # 最適化失敗時は元のテキストを両方に使用
            self.logger.warning("Returning original text for both tts_text and display_text")
            return {
                "tts_text": text,
                "display_text": text
            }

    def _build_optimization_prompt(
        self,
        text: str,
        context: Optional[str]
    ) -> str:
        """最適化プロンプトを構築"""

        context_section = f"""
【文脈情報】
{context}
""" if context else ""

        return f"""あなたは音声合成AIの前処理専門家です。
以下のナレーション原稿を、ElevenLabsが正確に読み上げられるように最適化してください。

{context_section}

【重要】
音声用テキスト（tts_text）と字幕用テキスト（display_text）の2種類を生成してください。

【tts_text（音声用）の最適化ルール】
1. **固有名詞を平仮名のみで記載**
   - 人名・地名・寺社名などは全て平仮名
   - 括弧は使用しない
   - 例: 織田信長 → おだのぶなが

2. **読みづらい漢字→ひらがな化**
   - 難読漢字、同音異義語、読み間違いしやすい言葉
   - 例: 雰囲気→ふんいき、重々→じゅうじゅう

3. **数字の読み方を平仮名で記載**
   - 西暦や大きな数字は平仮名
   - 例: 1560年 → せんごひゃくろくじゅうねん

4. **句読点を適切に配置**
   - 長い文は読点で区切る
   - AIの息継ぎポイントを制御

5. **長文を分割**
   - 1文は20-30文字程度に
   - 複雑な構文は簡潔に

【display_text（字幕用）の最適化ルール】
1. **元の漢字を保持**
   - 固有名詞は漢字のまま
   - 例: 織田信長（漢字のまま）

2. **括弧は不要**
   - 読み仮名の括弧は付けない

3. **句読点は元のまま**
   - 句読点の位置はtts_textと同じ

4. **意味・内容は絶対に変更しない**
   - あくまで表示用の調整

【入力テキスト】
{text}

【出力形式】
必ずJSON形式で返してください。説明や解説は不要です。

{{
  "tts_text": "音声用のテキスト（平仮名のみ）",
  "display_text": "字幕用のテキスト（漢字を保持）"
}}
"""
