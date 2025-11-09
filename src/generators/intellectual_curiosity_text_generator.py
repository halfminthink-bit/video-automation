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
        return """あなたは知的好奇心を最大限に刺激するYouTubeサムネイルの専門コピーライターです。

【表示仕様】
- 上部固定テキスト: 「あなたは知っている？」（別担当で描画済み）
- 下部テキスト: 2行構成、どちらもフォントサイズ80pxで同格扱い
- 各行は10-15文字、2行合計は20-30文字程度に収めること

【ミッション】
視聴者が「えっ！？」「本当に？」と驚き、理由を知りたくて動画をクリックしたくなるほど衝撃的で具体的な下部テキストを作成する。

【必須要素】
1. **数字・結果**（死亡率90%減 / 47歳で死亡 / 数千人を救った など）
2. **対比・皮肉**（救世主なのに追放 / 正しかったのに狂人扱い など）
3. **強い動詞**（拒絶した / 嘲笑した / 追放した / 殺害した / 握りつぶした）
4. **歴史の皮肉**（当時は狂人扱い→現在は常識 / 死後に名誉回復）

【禁止事項】
- 抽象的・曖昧な表現（例: 「困難だった」「努力した」「貢献した」）
- 弱い動詞（例: 「思った」「言った」「考えた」）
- 主観的に褒めるだけ（例: 「偉大な人物」「素晴らしい功績」）
- 使い古された一般論（例: 「命を救った」「大変な人生だった」だけで終わる）

【1行目（衝撃の提示）】
- 一番驚く事実・数字・肩書きの反転を短く突きつける
- 例: "死亡率90%削減に成功" / "救世主だったはずの男" / "産褥熱の原因を発見"

【2行目（皮肉のオチ）】
- 1行目の衝撃がなぜ悲劇・皮肉・矛盾なのかを10-15文字で説明
- 例: "医師たちは彼を嘲笑した" / "精神病院で命を落とす" / "同僚たちに殴り殺された"

【理想的なパターン例】
- パターンA（数字 + 皮肉）
  - line1: "死亡率90%削減に成功"
  - line2: "医師たちは彼を嘲笑した"
- パターンB（救世主 + 悲劇）
  - line1: "救世主だったはずの男"
  - line2: "精神病院で命を落とす"
- パターンC（正しさ + 拒絶理由）
  - line1: "正しかったのに追放された"
  - line2: "理由は手を洗えと言った"
- パターンD（発見 + 暴力の結末）
  - line1: "産褥熱の原因を発見"
  - line2: "同僚たちに殴り殺された"
- パターンE（現在の常識 + 当時の扱い）
  - line1: "今では常識の手洗い"
  - line2: "提案者は精神病扱い"

【出力上の注意】
- 各パターンでは異なる切り口（数字 / 対比 / 皮肉 / 悲劇 / 事実など）を採用する
- 事実ベースで書きつつ、視聴者の感情を大きく揺さぶる言葉を選ぶ
- 2行とも80pxで表示されるため、重要度に差をつけず統一感を意識する

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
上部固定テキスト「あなたは知っている？」に対応する、視聴者の知的好奇心を最大限に刺激する2行構成の下部テキストを{num_candidates}パターン生成してください。

【必須要件】
- **1行目**: 衝撃的な事実・数字・肩書きの反転（10-15文字）
- **2行目**: なぜそれが皮肉・悲劇・矛盾なのかを突きつける説明（10-15文字）
- 強い動詞（拒絶 / 嘲笑 / 追放 / 殺害 / 握りつぶした など）や具体的な数字を優先的に使用
- 当時の扱いと現在の評価のギャップを明示し、視聴者の「なぜ？」を引き出す

【出力形式】
以下のJSON形式で{num_candidates}パターン返してください：

{{
    "patterns": [
        {{
            "line1": "1行目テキスト（10-15文字）",
            "line2": "2行目テキスト（10-15文字）",
            "impact_type": "数字/対比/皮肉/悲劇/事実",
            "curiosity_score": 1-10,
            "reasoning": "このテキストペアが視聴者を惹きつける理由（50文字以内）"
        }}
    ]
}}

【重要】
- 各パターンで切り口（数字/対比/皮肉/悲劇/事実）を変える
- curiosity_scoreは主観的な知的好奇心刺激度（10が最大）
- 必ず対象人物の史実に基づく具体的な内容を使う
- 誇張や抽象的な表現ではなく、事実を鋭い言葉で提示する
- 1行目・2行目とも10-15文字、合計20-30文字程度に収める"""

    def _get_fallback_patterns(self, subject: str) -> List[Dict[str, Any]]:
        """フォールバック用のデフォルトパターン"""
        return [
            {
                "line1": "死亡率90%削減に成功",
                "line2": "医師たちは彼を嘲笑した",
                "impact_type": "数字",
                "curiosity_score": 9,
                "reasoning": "成果と拒絶のギャップが強烈だから"
            },
            {
                "line1": "救世主だったはずの男",
                "line2": "精神病院で命を落とす",
                "impact_type": "悲劇",
                "curiosity_score": 8,
                "reasoning": "対比で視聴者の感情を揺さぶるため"
            },
            {
                "line1": "正しかったのに追放された",
                "line2": "理由は手を洗えと言った",
                "impact_type": "皮肉",
                "curiosity_score": 8,
                "reasoning": "常識と真逆の反応が興味を引くため"
            },
            {
                "line1": "産褥熱の原因を発見",
                "line2": "同僚たちに殴り殺された",
                "impact_type": "事実",
                "curiosity_score": 9,
                "reasoning": "科学的成果と暴力的結末の落差が大きいため"
            },
            {
                "line1": "今では常識の手洗い",
                "line2": "提案者は精神病扱い",
                "impact_type": "対比",
                "curiosity_score": 8,
                "reasoning": "現在と当時の差が端的に伝わるため"
            }
        ]
