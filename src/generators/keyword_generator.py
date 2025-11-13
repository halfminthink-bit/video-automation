"""
Claude APIを使って画像キーワードを生成
"""

import json
from typing import List
import anthropic


class KeywordGenerator:
    """セクション内容から画像キーワードを生成"""

    def __init__(self, api_key: str, logger):
        """
        Args:
            api_key: Anthropic API Key
            logger: ロガー
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.logger = logger

    def generate_keywords(
        self,
        section_title: str,
        narration: str,
        atmosphere: str,
        subject: str,
        target_count: int = 3
    ) -> List[str]:
        """
        セクション内容からキーワードを生成

        Args:
            section_title: セクションタイトル
            narration: ナレーション全文
            atmosphere: 雰囲気（壮大、静か、など）
            subject: 偉人名
            target_count: 生成するキーワード数

        Returns:
            生成されたキーワードのリスト
        """

        prompt = self._build_prompt(
            section_title=section_title,
            narration=narration,
            atmosphere=atmosphere,
            subject=subject,
            target_count=target_count
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # レスポンスからキーワードを抽出
            content = response.content[0].text.strip()

            # JSONレスポンスをパース
            keywords = self._parse_response(content, target_count)

            self.logger.info(f"Generated keywords via Claude API: {keywords}")

            return keywords

        except Exception as e:
            self.logger.error(f"Failed to generate keywords via Claude API: {e}")

            # フォールバック: デフォルトキーワード
            fallback_keywords = [
                subject,
                "歴史的瞬間",
                "時代背景"
            ]

            self.logger.warning(f"Using fallback keywords: {fallback_keywords}")
            return fallback_keywords[:target_count]

    def _build_prompt(
        self,
        section_title: str,
        narration: str,
        atmosphere: str,
        subject: str,
        target_count: int
    ) -> str:
        """プロンプトを構築"""

        prompt = f"""あなたは動画制作のためのキーワード生成AIです。

以下のセクション内容から、画像生成に最適なキーワードを{target_count}つ提案してください。

# セクション情報
- タイトル: {section_title}
- 雰囲気: {atmosphere}
- 主人公: {subject}

# ナレーション内容:
{narration}

# キーワード生成の要件
1. Stable Diffusionで画像生成できる具体的なキーワード
2. ナレーションの内容を視覚的に表現できるもの
3. {subject}の人物像や時代背景が伝わるもの
4. 雰囲気「{atmosphere}」に合ったもの

# 出力形式
以下のJSON形式で出力してください。キーワードのみを出力し、説明は不要です。
```json
{{
  "keywords": [
    "キーワード1",
    "キーワード2",
    "キーワード3"
  ]
}}
```

# 例
入力: 「織田信長が本能寺で最期を迎える場面」
出力:
```json
{{
  "keywords": [
    "本能寺の変",
    "織田信長最期",
    "炎上する寺院"
  ]
}}
```

それでは、上記のセクション内容から{target_count}つのキーワードを生成してください。
"""

        return prompt

    def _parse_response(self, content: str, target_count: int) -> List[str]:
        """Claude APIのレスポンスをパース"""

        # ```json ``` で囲まれている場合は除去
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # JSONパース
        try:
            data = json.loads(content)
            keywords = data.get("keywords", [])

            # target_count分だけ取得
            return keywords[:target_count]

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            self.logger.debug(f"Response content: {content}")

            # フォールバック: 改行で分割してキーワードを抽出
            lines = content.strip().split('\n')
            keywords = [
                line.strip().strip('"').strip("'").strip('-').strip()
                for line in lines
                if line.strip() and len(line.strip()) > 0
            ]

            return keywords[:target_count]
