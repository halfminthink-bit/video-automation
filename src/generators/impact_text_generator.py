"""
インパクトテキスト生成器

視聴者の興味を引く疑問形・衝撃系のテキストペアを生成
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI


# Ensure .env values override existing environment variables
load_dotenv(override=True)


class ImpactTextGenerator:
    """インパクトテキスト生成システム"""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            model: 使用するモデル
            logger: ロガー
        """
        self.model = model
        self.client = OpenAI()
        self.logger = logger or logging.getLogger(__name__)

    def generate_text_pairs(
        self,
        subject: str,
        script_data: Dict[str, Any],
        num_candidates: int = 5
    ) -> List[Dict[str, str]]:
        """
        インパクトテキストペアを生成

        Args:
            subject: 動画のテーマ
            script_data: 台本データ
            num_candidates: 生成する候補数

        Returns:
            テキストペアのリスト [{"main": "...", "sub": "..."}, ...]
        """
        self.logger.info(f"Generating impact text pairs for: {subject}")

        # プロンプトを構築
        prompt = self._build_prompt(subject, script_data, num_candidates)

        try:
            # API呼び出し
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.9,  # 高めの温度で多様性を確保
            )

            # JSONをパース
            result = json.loads(response.choices[0].message.content)
            candidates = result.get("candidates", [])

            self.logger.info(f"Generated {len(candidates)} text pair candidates")

            # 候補をログ出力
            for i, candidate in enumerate(candidates, 1):
                self.logger.debug(
                    f"Candidate {i}: Main='{candidate.get('main')}', "
                    f"Sub='{candidate.get('sub')}'"
                )

            return candidates

        except Exception as e:
            self.logger.error(f"Failed to generate text pairs: {e}", exc_info=True)
            # フォールバック
            return self._get_fallback_candidates(subject)

    def _get_system_prompt(self) -> str:
        """システムプロンプトを取得"""
        return """あなたはYouTubeサムネイルの超インパクトテキストを作成する専門家です。

【重要な原則】
1. **上部テキスト**（5-8文字）：誰でも理解できる簡単な言葉で視聴者の興味を引く
2. **下部テキスト**（15-25文字）：上部を補完し、もっと知りたくなる説明
3. **専門用語は絶対に使わない**：一般の人が理解できる言葉のみ
4. **感情に訴える**：疑問、驚き、衝撃を与える

【上部テキストの良い例】
- "なぜ死んだ？" (5文字)
- "99%知らない" (6文字)
- "衝撃の真実" (5文字)
- "まさかの結末" (6文字)
- "信じられない" (6文字)
- "本当にあった" (6文字)
- "誰も知らない" (6文字)

【上部テキストの悪い例】
- "産褥熱の予防法" → 専門用語
- "医学的発見" → 硬すぎる
- "歴史的偉業" → ありきたり

【下部テキストの良い例】
- "手洗いで命を救った男の真実" (14文字)
- "世界中の医師を敵に回した理由" (15文字)
- "誰も信じなかった天才の悲劇" (14文字)
- "たった一つの習慣が世界を変えた" (16文字)

【下部テキストの悪い例】
- "詳しく解説します" → 視聴欲を掻き立てない
- "歴史に残る発見" → 抽象的すぎる

日本語で出力してください。"""

    def _build_prompt(
        self,
        subject: str,
        script_data: Dict[str, Any],
        num_candidates: int
    ) -> str:
        """ユーザープロンプトを構築"""
        # 台本の概要を抽出
        script_summary = self._extract_script_summary(script_data)

        return f"""動画のテーマ: {subject}

台本の概要:
{script_summary}

【テキストペア生成条件】
- 上部テキスト: 5-8文字（厳守）
- 下部テキスト: 15-25文字（厳守）
- 専門用語を絶対に使わない
- 誰でも理解できる簡単な言葉のみ

【重要な指示】
1. 上部は**必ず5-8文字**、下部は**必ず15-25文字**
2. 上部は疑問形、衝撃系、驚き系のいずれか
3. 下部は「〜の真実」「〜の秘密」「〜の理由」などの形式を推奨
4. 視聴者が「もっと知りたい！」と思う内容

以下のJSON形式で{num_candidates}つの候補を出力してください：
{{
  "candidates": [
    {{
      "main": "なぜ死んだ？",
      "sub": "手洗いで命を救った男の真実",
      "reasoning": "疑問形で興味を引き、補足で詳細を説明"
    }}
  ]
}}

【各候補のバリエーション】
1. 疑問形（なぜ？本当？どうして？）
2. 数字系（99%、1人、100年）
3. 衝撃系（信じられない、まさか）
4. 対立系（vs、敵、戦い）
5. 謎提示（誰も知らない、秘密）

注意: 文字数を絶対に超えないこと！簡単な言葉のみ使用！"""

    def _extract_script_summary(self, script_data: Dict[str, Any]) -> str:
        """台本から概要を抽出"""
        sections = script_data.get("sections", [])

        if not sections:
            return script_data.get("subject", "")

        summary_parts = []

        # 最初の3セクションのみ
        for section in sections[:3]:
            title = section.get("title", "")
            content = section.get("content", "")

            # 最初の100文字のみ
            content_preview = content[:100] + "..." if len(content) > 100 else content

            if title and content_preview:
                summary_parts.append(f"- {title}: {content_preview}")

        return "\n".join(summary_parts) if summary_parts else script_data.get("subject", "")

    def _get_fallback_candidates(self, subject: str) -> List[Dict[str, str]]:
        """
        フォールバック用のデフォルト候補

        Args:
            subject: テーマ

        Returns:
            デフォルトのテキストペア候補
        """
        self.logger.warning("Using fallback text pair candidates")

        # subjectから最初の5文字を取得
        short_subject = subject[:5] if len(subject) >= 5 else subject

        return [
            {
                "main": "なぜ？",
                "sub": f"{short_subject}の驚くべき真実",
                "reasoning": "フォールバック（デフォルト）"
            },
            {
                "main": "信じられない",
                "sub": f"{short_subject}が世界を変えた理由",
                "reasoning": "フォールバック（デフォルト）"
            },
            {
                "main": "99%知らない",
                "sub": f"{short_subject}の隠された秘密",
                "reasoning": "フォールバック（デフォルト）"
            },
            {
                "main": "衝撃の事実",
                "sub": f"{short_subject}に隠された驚きの物語",
                "reasoning": "フォールバック（デフォルト）"
            },
            {
                "main": "本当にあった",
                "sub": f"{short_subject}の知られざる真実",
                "reasoning": "フォールバック（デフォルト）"
            }
        ]
