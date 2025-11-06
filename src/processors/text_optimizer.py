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
    ) -> str:
        """
        テキストを音声合成用に最適化

        Args:
            text: 最適化するナレーション
            context: 文脈情報（偉人の生涯、時代背景など）

        Returns:
            最適化されたテキスト
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

            optimized = response.content[0].text.strip()
            self.logger.info(f"Text optimized successfully")

            return optimized

        except Exception as e:
            self.logger.error(f"Failed to optimize text: {e}")
            # 最適化失敗時は元のテキストを返す
            self.logger.warning("Returning original text")
            return text

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

【最適化ルール】
1. **固有名詞に読み仮名を追加**
   - 人名・地名・寺社名などの固有名詞
   - 括弧で読み仮名を追加: 織田信長（おだのぶなが）

2. **読みづらい漢字→ひらがな化**
   - 難読漢字、同音異義語、読み間違いしやすい言葉
   - 例: 雰囲気→ふんいき、重々→じゅうじゅう、早急→さっきゅう

3. **数字の読み方を明示**
   - 西暦や大きな数字には読み仮名
   - 例: 1560年（せんごひゃくろくじゅうねん）、1万（いちまん）

4. **句読点を適切に配置**
   - 長い文は読点で区切る
   - AIの息継ぎポイントを制御

5. **長文を分割**
   - 1文は20-30文字程度に
   - 複雑な構文は簡潔に

6. **意味・内容は絶対に変更しない**
   - あくまで読み上げやすさのための調整
   - 情報の追加・削除は禁止

【入力テキスト】
{text}

【出力】
最適化されたテキストのみを返してください。
説明や解説は不要です。
"""
