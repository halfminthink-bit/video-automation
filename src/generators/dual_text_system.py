"""
2段テキストシステム

メインキャッチ（5-7文字）とサブ説明文（15-20文字）のペアを生成
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI


# Ensure .env values override existing environment variables
load_dotenv(override=True)


class DualTextSystem:
    """2段構成のテキストペア生成システム"""

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
        tone: str = "dramatic",
        num_candidates: int = 5
    ) -> List[Dict[str, str]]:
        """
        2段構成のテキストペアを生成

        Args:
            subject: 動画のテーマ
            script_data: 台本データ
            tone: 口調
            num_candidates: 生成する候補数

        Returns:
            テキストペアのリスト [{"main": "...", "sub": "...", "color_scheme": "..."}, ...]
        """
        self.logger.info(f"Generating dual text pairs for: {subject}")

        # プロンプトを構築
        prompt = self._build_prompt(subject, script_data, tone, num_candidates)

        try:
            # API呼び出し
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
            )

            # JSONをパース
            result = json.loads(response.choices[0].message.content)
            candidates = result.get("candidates", [])

            self.logger.info(f"Generated {len(candidates)} text pair candidates")

            # 候補をログ出力
            for i, candidate in enumerate(candidates, 1):
                self.logger.debug(
                    f"Candidate {i}: Main='{candidate.get('main')}', "
                    f"Sub='{candidate.get('sub')}', Scheme={candidate.get('color_scheme')}"
                )

            return candidates

        except Exception as e:
            self.logger.error(f"Failed to generate text pairs: {e}", exc_info=True)
            # フォールバック
            return self._get_fallback_candidates(subject)

    def _get_system_prompt(self) -> str:
        """システムプロンプトを取得"""
        return """あなたはYouTubeサムネイルの2段構成テキストを作成する専門家です。

【重要な原則】
1. **メインキャッチ**（5-7文字）：超インパクト、視線を奪う
2. **サブ説明文**（15-20文字）：メインを補完し、視聴欲を掻き立てる
3. メインとサブは必ず連動させる
4. 感情を強く刺激する

【良い例】
- Main: "手を洗え！" (5文字)
  Sub: "今では当たり前の常識を生んだ男" (16文字)

- Main: "99%防ぐ" (5文字)
  Sub: "産褥熱から母親を救った医師" (14文字)

- Main: "3日天下" (4文字)
  Sub: "戦国時代を変えた革命児の真実" (16文字)

【悪い例】
- Main: "医学の父" → サブ: "歴史を作った" (つながりが弱い)
- Main: "知られざる偉人" (7文字超・説明的)
- Sub: "詳しく解説します" (視聴欲を掻き立てない)

【配色スキーム】
各ペアに適した配色を選択：
- fire: 炎・情熱系（白→黄→赤）
- ocean: 海・清潔系（白→シアン→青）
- royal: 王室・高貴系（金→赤→紫）
- nature: 自然・生命系（緑→黄→赤）
- electric: 電気・未来系（白→ピンク→シアン）

日本語で出力してください。"""

    def _build_prompt(
        self,
        subject: str,
        script_data: Dict[str, Any],
        tone: str,
        num_candidates: int
    ) -> str:
        """ユーザープロンプトを構築"""
        # 台本の概要を抽出
        script_summary = self._extract_script_summary(script_data)

        # トーンの説明
        tone_descriptions = {
            "dramatic": "劇的で感動的な表現",
            "shocking": "衝撃的で驚きを与える表現",
            "educational": "教育的で知的な表現",
            "casual": "カジュアルで親しみやすい表現"
        }
        tone_desc = tone_descriptions.get(tone, "バランスの取れた表現")

        return f"""動画のテーマ: {subject}

台本の概要:
{script_summary}

【テキストペア生成条件】
- 口調: {tone} ({tone_desc})
- メインキャッチ: 5-7文字（厳守）
- サブ説明文: 15-20文字（厳守）

【重要な指示】
1. メインは**必ず5-7文字**、サブは**必ず15-20文字**
2. メインとサブは意味的に連動させる
3. サブは「〜した男/女」「〜から○○を救った〜」形式を推奨
4. 各ペアに最適な配色スキームを選択

以下のJSON形式で{num_candidates}つの候補を出力してください：
{{
  "candidates": [
    {{
      "main": "手を洗え！",
      "sub": "今では当たり前の常識を生んだ男",
      "color_scheme": "ocean",
      "reasoning": "手洗いは清潔・医療と関連するためocean配色"
    }}
  ]
}}

【各候補のバリエーション】
1. 命令形 + 偉業説明
2. 数字 + 具体的成果
3. 短いフレーズ + 詳細文脈
4. 謎提示 + 解答ヒント
5. 対立構造 + 背景説明

注意: 文字数を絶対に超えないこと！"""

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

        return [
            {
                "main": f"{subject[:5]}",
                "sub": f"歴史に名を残した{subject}の物語",
                "color_scheme": "fire",
                "reasoning": "フォールバック（デフォルト）"
            },
            {
                "main": "真実は",
                "sub": f"{subject}が変えた世界の常識",
                "color_scheme": "ocean",
                "reasoning": "フォールバック（デフォルト）"
            },
            {
                "main": "知られざる",
                "sub": f"{subject}の驚くべき功績とは",
                "color_scheme": "royal",
                "reasoning": "フォールバック（デフォルト）"
            }
        ]
