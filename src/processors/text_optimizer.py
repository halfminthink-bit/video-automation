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

            # レスポンスをINFOレベルで出力（デバッグ用）
            self.logger.info(f"Claude API response (first 300 chars): {optimized_response[:300]}")

            # レスポンスをパース（JSON形式を期待）
            import json
            import re

            try:
                # マークダウンのコードブロック記法を除去
                # ```json ... ``` または ``` ... ``` を除去
                json_text = optimized_response

                # ```json で始まる場合
                if json_text.startswith("```json"):
                    json_text = json_text[7:]  # ```json を除去
                    self.logger.info("Removed ```json prefix")
                elif json_text.startswith("```"):
                    json_text = json_text[3:]  # ``` を除去
                    self.logger.info("Removed ``` prefix")

                # 末尾の ``` を除去
                if json_text.endswith("```"):
                    json_text = json_text[:-3]
                    self.logger.info("Removed ``` suffix")

                # 前後の空白を除去
                json_text = json_text.strip()

                self.logger.info(f"Cleaned JSON (first 200 chars): {json_text[:200]}")

                result = json.loads(json_text)

                # tts_textとdisplay_textが両方存在するか確認
                if "tts_text" in result and "display_text" in result:
                    self.logger.info(
                        f"✓ Successfully parsed JSON: "
                        f"tts_text={result['tts_text'][:50]}..., "
                        f"display_text={result['display_text'][:50]}..."
                    )
                    # 追加の詳細ログ
                    self.logger.info(f"TTS text: {result['tts_text'][:100]}...")
                    self.logger.info(f"Display text: {result['display_text'][:100]}...")
                    return result
                else:
                    self.logger.warning("Response missing required fields (tts_text or display_text)")
                    self.logger.warning(f"Response keys: {list(result.keys())}")
                    return {
                        "tts_text": text,
                        "display_text": text
                    }
            except json.JSONDecodeError as e:
                self.logger.warning(f"✗ Failed to parse JSON: {e}")
                self.logger.warning(f"Full response (first 500 chars): {optimized_response[:500]}")
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

{context_section}

【タスク】
以下のナレーション原稿を最適化し、JSON形式で2種類のテキストを返してください。

【入力テキスト】
{text}

【出力ルール】

1. **tts_text（音声用）**: ElevenLabsが読み上げる用
   - 固有名詞は全て平仮名（括弧なし）
     例: 織田信長 → おだのぶなが
   - 難読漢字も平仮名化
     例: 雰囲気→ふんいき、明智光秀→あけちみつひで
   - 数字は平仮名で読み方を明示
     例: 1560年→せんごひゃくろくじゅうねん、49歳→よんじゅうきゅうさい
   - 句読点は元のまま維持

2. **display_text（字幕用）**: 字幕として表示する用
   - 固有名詞は漢字のまま（括弧なし）
   - 難読漢字も元の漢字のまま
   - 数字は元のまま
   - 句読点は元のまま維持

【出力形式】
JSON形式のみを返してください。説明文、コードブロック記法（```）、その他の文章は一切含めないでください。

{{
  "tts_text": "ここに音声用テキスト（平仮名）",
  "display_text": "ここに字幕用テキスト（漢字）"
}}"""
