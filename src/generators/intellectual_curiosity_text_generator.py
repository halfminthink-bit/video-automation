"""
知的好奇心を刺激するテキスト自動生成器

「えっ！？」と驚くような上下テキストペアを生成
- 上部: 黄色/金色、10文字以内、超インパクト
- 下部: 白文字、10-20文字、1-2行、詳細説明
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI


# Ensure .env values override existing environment variables
load_dotenv(override=True)


class IntellectualCuriosityTextGenerator:
    """知的好奇心を刺激するテキスト自動生成器"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
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

    def generate_surprise_texts(
        self,
        subject: str,
        context: Optional[Dict[str, Any]] = None,
        num_candidates: int = 5
    ) -> List[Dict[str, Any]]:
        """
        「えっ！？」と驚くような上下テキストペアを生成

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト（台本など）
            num_candidates: 生成する候補数

        Returns:
            テキストペアの候補リスト
        """
        self.logger.info(f"Generating surprise texts for: {subject}")

        # プロンプトを構築
        prompt = self._build_prompt(subject, context, num_candidates)

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
            patterns = result.get("patterns", [])

            self.logger.info(f"Generated {len(patterns)} surprise text patterns")

            # 候補をログ出力
            for i, pattern in enumerate(patterns, 1):
                self.logger.debug(
                    f"Pattern {i}: Top='{pattern.get('top')}', "
                    f"Bottom='{pattern.get('bottom')}'"
                )

            return patterns

        except Exception as e:
            self.logger.error(f"Failed to generate surprise texts: {e}", exc_info=True)
            # フォールバック
            return self._get_fallback_patterns(subject)

    def _get_system_prompt(self) -> str:
        """システムプロンプトを取得"""
        return """あなたはYouTubeサムネイル用の知的好奇心を刺激するテキストを作成する専門家です。

【ミッション】
視聴者が「えっ！？」と驚き、思わず動画を見たくなるような衝撃的なテキストペアを生成する。

【重要原則】
1. **上部テキスト（10文字以内厳守）**: 一瞬で強烈なインパクトを与える超短文
2. **下部テキスト（10-20文字程度、1-2行OK）**: 上部を補完し、具体的な驚きの内容を示唆
3. **常識を覆す**: 多くの人が知っている「常識」と真逆の事実を提示
4. **感情を刺激**: 驚き、疑問、衝撃を直接的に引き出す

【上部テキストのパターン】（10文字以内厳守）

1. 【一言ショックパターン】
   - "実は○○だった"
   - "○○じゃない！"
   - "嘘だった？"
   - "裏の顔"
   - "真実は…"

2. 【衝撃ワードパターン】
   - "殺された"
   - "追放された"
   - "黒歴史"
   - "隠された"
   - "禁断の"
   - "裏切り"

3. 【疑問形パターン】
   - "天才？"
   - "英雄？"
   - "誰？"
   - "なぜ？"
   - "本当？"

4. 【反転パターン】
   - "逆だった"
   - "間違い"
   - "偽物"

【下部テキストの原則】（10-20文字程度、1-2行OK）

- 上部のインパクトを具体化
- 一般常識との矛盾を簡潔に説明
- 「実は...」「本当は...」を使った反転
- 1行に収まらない場合は改行を使って2行に（\nで区切る）
- 数字や具体的な事実を含めると効果的

【優れた例】

✅ 例1（常識の反転）
{{
  "top": "背は高い",
  "bottom": "167cmは当時の平均以上\nイギリスの嘘だった",
  "surprise_type": "常識覆し"
}}

✅ 例2（衝撃事実）
{{
  "top": "天才？",
  "bottom": "発明の9割は他人のもの\n特許で勝っただけ",
  "surprise_type": "意外な面"
}}

✅ 例3（悲劇的事実）
{{
  "top": "殺された医師",
  "bottom": "手洗い提案で精神病院送り\n医師に殺された天才",
  "surprise_type": "衝撃事実"
}}

✅ 例4（裏の顔）
{{
  "top": "裏切者？",
  "bottom": "本能寺の変の真実\n実は味方が敵だった",
  "surprise_type": "隠された真実"
}}

【避けるべき表現】
❌ 専門用語、難しい言葉
❌ 抽象的すぎる表現
❌ ありきたりな驚き
❌ 上部が10文字を超える
❌ 下部が20文字を大きく超える（25文字以上は避ける）

日本語で出力してください。"""

    def _build_prompt(
        self,
        subject: str,
        context: Optional[Dict[str, Any]],
        num_candidates: int
    ) -> str:
        """ユーザープロンプトを構築"""
        # コンテキストから情報を抽出
        context_info = ""
        if context:
            if "sections" in context:
                # 台本の最初のセクションを使用
                sections = context.get("sections", [])
                if sections:
                    first_section = sections[0]
                    content = first_section.get("content", "")[:200]
                    context_info = f"\n台本の概要:\n{content}"

        return f"""対象人物・テーマ: {subject}
{context_info}

【タスク】
{subject}について、視聴者が「えっ！？」と驚くような知的好奇心を刺激するテキストペアを{num_candidates}パターン生成してください。

【要件】
- 上部テキスト: 10文字以内（厳守）
- 下部テキスト: 10-20文字程度（1-2行、改行OK）
- 常識を覆す、または衝撃的な事実を提示
- 視聴者の「えっ！？」を引き出す

【出力形式】
以下のJSON形式で{num_candidates}パターン返してください：

{{
    "patterns": [
        {{
            "top": "上部テキスト（10文字以内）",
            "bottom": "下部テキスト（10-20文字、改行可）",
            "surprise_type": "常識覆し/衝撃事実/意外な面/隠された真実",
            "curiosity_score": 1-10,
            "reasoning": "このテキストペアを選んだ理由"
        }}
    ]
}}

【重要】
- 各パターンは異なるアプローチを使用
- curiosity_scoreは主観的な知的好奇心刺激度（高いほど良い）
- 対象人物・テーマに関連した具体的な内容にする
- 上部は必ず10文字以内、下部は20文字を大きく超えないこと"""

    def _get_fallback_patterns(self, subject: str) -> List[Dict[str, Any]]:
        """フォールバック用のデフォルトパターン"""
        return [
            {
                "top": "真実は？",
                "bottom": "教科書に載らない\n驚きの事実",
                "surprise_type": "常識覆し",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            },
            {
                "top": "裏の顔",
                "bottom": "知られざる\n意外な一面",
                "surprise_type": "意外な面",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            },
            {
                "top": "衝撃の事実",
                "bottom": "誰も知らない\n本当の姿",
                "surprise_type": "衝撃事実",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            },
            {
                "top": "嘘だった？",
                "bottom": "世間の常識を覆す\n真実",
                "surprise_type": "常識覆し",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            },
            {
                "top": "隠された秘密",
                "bottom": "歴史が隠した\n驚愕の真相",
                "surprise_type": "隠された真実",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            }
        ]
