"""
知的好奇心を刺激するテキスト自動生成器

「えっ！？」と驚くような上下テキストペアを生成
- 上部: 黄色/金色、10文字以内、超インパクト
- 下部: 白文字、10-20文字、1-2行、詳細説明
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI


def _load_env_with_overrides() -> None:
    """Load environment variables giving priority to project .env files."""
    project_root = Path(__file__).resolve().parents[2]
    env_candidates = [
        project_root / ".env",
        project_root / "config" / ".env",
    ]

    loaded = False
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
            loaded = True

    if not loaded:
        load_dotenv(override=True)


_load_env_with_overrides()


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
視聴者が「えっ！？」と驚き、思わず動画を見たくなるような衝撃的なテキストを生成する。

【新仕様：固定上部テキスト + 2行下部テキスト】

**上部テキスト**: 固定フレーズから選択
- "あなたは知っている？"
- "教科書には載っていない！"
- "世界が隠した真実"
- "99%が知らない事実"
- "歴史の裏側"

**下部テキスト**: 2行構成（必須）
- **1行目**: 衝撃的な事実・真実（10-15文字）
- **2行目**: 詳細説明・理由（10-15文字）
- 合計：20-30文字程度

【2行テキストの原則】

1. **1行目**（10-15文字）
   - 最も衝撃的な事実を一言で
   - 視聴者の「えっ！？」を引き出す
   - 短く、強烈に

   例：
   - "医師に殺された天才"
   - "死亡率90%減の発見"
   - "精神病院で亡くなった"

2. **2行目**（10-15文字）
   - 1行目の補足・詳細
   - なぜそうなったのか
   - どんな結果になったのか

   例：
   - "手洗いを提案しただけで"
   - "誰も信じなかった理由"
   - "医学界を救った男の末路"

【優れた例】

✅ 例1（悲劇）
{{
  "line1": "医師に殺された天才",
  "line2": "手洗いを提案しただけで",
  "impact_type": "悲劇"
}}

✅ 例2（不理解）
{{
  "line1": "死亡率90%減の発見",
  "line2": "誰も信じなかった理由",
  "impact_type": "不理解"
}}

✅ 例3（皮肉）
{{
  "line1": "精神病院で亡くなった",
  "line2": "医学界を救った男の末路",
  "impact_type": "皮肉"
}}

✅ 例4（常識の反転）
{{
  "line1": "背は低くなかった",
  "line2": "167cmは当時の平均以上",
  "impact_type": "常識覆し"
}}

✅ 例5（意外な事実）
{{
  "line1": "発明の9割は他人のもの",
  "line2": "特許で勝っただけの男",
  "impact_type": "意外な面"
}}

【避けるべき表現】
❌ 専門用語、難しい言葉
❌ 抽象的すぎる表現
❌ ありきたりな驚き
❌ 1行が15文字を大きく超える
❌ 2行合計が30文字を大きく超える

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
{subject}について、視聴者が「えっ！？」と驚くような2行構成の下部テキストを{num_candidates}パターン生成してください。

【要件】
- **1行目**: 衝撃的な事実・真実（10-15文字）
- **2行目**: 詳細説明・理由（10-15文字）
- 常識を覆す、または衝撃的な事実を提示
- 視聴者の「えっ！？」を引き出す

【出力形式】
以下のJSON形式で{num_candidates}パターン返してください：

{{
    "patterns": [
        {{
            "line1": "1行目テキスト（10-15文字）",
            "line2": "2行目テキスト（10-15文字）",
            "impact_type": "悲劇/不理解/皮肉/常識覆し/意外な面",
            "curiosity_score": 1-10,
            "reasoning": "このテキストペアを選んだ理由"
        }}
    ]
}}

【重要】
- 各パターンは異なるアプローチを使用
- curiosity_scoreは主観的な知的好奇心刺激度（高いほど良い）
- 対象人物・テーマに関連した具体的な内容にする
- 1行目は10-15文字、2行目は10-15文字を守る
- 2行合計で20-30文字程度"""

    def _get_fallback_patterns(self, subject: str) -> List[Dict[str, Any]]:
        """フォールバック用のデフォルトパターン"""
        return [
            {
                "line1": "教科書に載らない事実",
                "line2": "驚きの真実がここに",
                "impact_type": "常識覆し",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            },
            {
                "line1": "知られざる裏の顔",
                "line2": "意外な一面とは？",
                "impact_type": "意外な面",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            },
            {
                "line1": "誰も知らない真実",
                "line2": "本当の姿を公開",
                "impact_type": "衝撃事実",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            },
            {
                "line1": "常識を覆す発見",
                "line2": "世間の嘘が明らかに",
                "impact_type": "常識覆し",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            },
            {
                "line1": "歴史が隠した秘密",
                "line2": "驚愕の真相とは？",
                "impact_type": "隠された真実",
                "curiosity_score": 7,
                "reasoning": "フォールバック（汎用パターン）"
            }
        ]
