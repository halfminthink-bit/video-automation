"""
「教科書には載せてくれない」シリーズ専用テキスト生成器

下部テキストのみをClaude APIで生成（知的好奇心を刺激）
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
        # Fall back to default search behaviour
        load_dotenv(override=True)


_load_env_with_overrides()


class TextbookTextGenerator:
    """「教科書には載せてくれない」シリーズ専用テキスト生成器"""

    # 上部テキスト（固定）
    FIXED_TOP_TEXT = "教科書には載せてくれない"

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

    def generate_bottom_texts(
        self,
        subject: str,
        context: Optional[Dict[str, Any]] = None,
        num_candidates: int = 5
    ) -> List[Dict[str, Any]]:
        """
        下部テキストのみを生成（知的好奇心を刺激）

        Args:
            subject: 対象人物・テーマ
            context: 追加コンテキスト（台本など）
            num_candidates: 生成する候補数

        Returns:
            テキスト候補のリスト
        """
        self.logger.info(f"Generating textbook-style bottom texts for: {subject}")

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
                temperature=0.9,  # 多様性を確保
            )

            # JSONをパース
            result = json.loads(response.choices[0].message.content)
            patterns = result.get("patterns", [])

            self.logger.info(f"Generated {len(patterns)} bottom text candidates")

            # 候補をログ出力
            for i, pattern in enumerate(patterns, 1):
                self.logger.debug(
                    f"Candidate {i}: '{pattern.get('text')}' "
                    f"(category: {pattern.get('category')}, "
                    f"impact: {pattern.get('impact_level', 0)})"
                )

            return patterns

        except Exception as e:
            self.logger.error(f"Failed to generate bottom texts: {e}", exc_info=True)
            # フォールバック
            return self._get_fallback_texts(subject)

    def _get_system_prompt(self) -> str:
        """システムプロンプトを取得"""
        return """あなたは「教科書には載せてくれない」シリーズの専門テキストライターです。

【シリーズコンセプト】
- 上部テキスト: 「教科書には載せてくれない」（固定）
- 下部テキスト: 歴史の裏側・謎・真実を示唆する知的好奇心を刺激するフレーズ

【下部テキストの要件】
- 10-15文字程度
- 教科書では教えない内容を匂わせる
- 知的好奇心を刺激
- 歴史の謎・真実・秘密を示唆

【優れた下部テキストの例】
✅ "日本史の謎" (5文字)
✅ "戦国時代の闇" (6文字)
✅ "天才たちの狂気" (7文字)
✅ "歴史の裏側" (5文字)
✅ "偉人たちの裏の顔" (8文字)
✅ "消された真実" (6文字)
✅ "隠された秘密" (6文字)
✅ "世界史の闇" (5文字)
✅ "禁断の歴史" (5文字)
✅ "真実の物語" (5文字)

【カテゴリ別パターン】

1. 【謎パターン】
   - "〇〇の謎"
   - "隠された〇〇"
   - "消された〇〇"
   例: "日本史の謎", "消された真実", "隠された秘密"

2. 【真実パターン】
   - "〇〇の真実"
   - "真実の〇〇"
   - "本当の〇〇"
   例: "歴史の真実", "真実の物語", "本当の姿"

3. 【秘密パターン】
   - "〇〇の秘密"
   - "秘密の〇〇"
   - "〇〇の正体"
   例: "偉人の秘密", "秘密の歴史", "天才の正体"

4. 【闇パターン】
   - "〇〇の闇"
   - "〇〇の裏側"
   - "裏の〇〇"
   例: "世界史の闇", "歴史の裏側", "裏の顔"

5. 【事件・陰謀パターン】
   - "〇〇の陰謀"
   - "〇〇事件の真相"
   - "禁断の〇〇"
   例: "歴史の陰謀", "禁断の真実", "事件の真相"

【避けるべき表現】
❌ 専門用語
❌ 難しい言葉
❌ 抽象的すぎる表現
❌ ありきたりな表現

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
「教科書には載せてくれない」シリーズの下部テキストを{num_candidates}パターン生成してください。

【要件】
- 10-15文字程度
- 教科書で教えない内容を示唆
- 知的好奇心を刺激
- 歴史の謎・真実・秘密を匂わせる

【出力形式】
以下のJSON形式で{num_candidates}パターン返してください：

{{
    "patterns": [
        {{
            "text": "下部テキスト（10-15文字）",
            "category": "謎/真実/秘密/闇/事件",
            "impact_level": 1-10,
            "reasoning": "このテキストを選んだ理由"
        }}
    ]
}}

【重要】
- 各パターンは異なるカテゴリを使用
- impact_levelは主観的な衝撃度（高いほど良い）
- 対象人物・テーマに関連した内容にする"""

    def _extract_script_summary(self, script_data: Dict[str, Any]) -> str:
        """台本から概要を抽出"""
        sections = script_data.get("sections", [])
        if not sections:
            return "（台本情報なし）"

        # 最初のセクションの内容を取得
        first_section = sections[0]
        content = first_section.get("content", "")

        # 最初の200文字を返す
        return content[:200] + "..." if len(content) > 200 else content

    def _get_fallback_texts(self, subject: str) -> List[Dict[str, Any]]:
        """フォールバック用のデフォルトテキスト"""
        return [
            {
                "text": "日本史の謎",
                "category": "謎",
                "impact_level": 8,
                "reasoning": "フォールバック（汎用的な謎パターン）"
            },
            {
                "text": "歴史の真実",
                "category": "真実",
                "impact_level": 7,
                "reasoning": "フォールバック（汎用的な真実パターン）"
            },
            {
                "text": "偉人の秘密",
                "category": "秘密",
                "impact_level": 7,
                "reasoning": "フォールバック（汎用的な秘密パターン）"
            },
            {
                "text": "世界史の闇",
                "category": "闇",
                "impact_level": 8,
                "reasoning": "フォールバック（汎用的な闇パターン）"
            },
            {
                "text": "隠された真実",
                "category": "真実",
                "impact_level": 7,
                "reasoning": "フォールバック（汎用的な真実パターン）"
            }
        ]
