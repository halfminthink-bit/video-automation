"""
汎用偉人サムネイル用インパクトテキスト生成器

様々な偉人に対応できる汎用的なテキスト生成システム
上部：衝撃的な短文、下部：知的好奇心を刺激する説明文
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI


# Ensure .env values override existing environment variables
load_dotenv(override=True)


class UniversalImpactTextGenerator:
    """汎用偉人サムネイル用テキスト生成器"""

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
        self.base_prompt_template = self._create_base_template()

    def _create_base_template(self) -> str:
        """
        汎用性の高い基本プロンプトテンプレート

        Returns:
            プロンプトテンプレート
        """
        return """
{subject}についてYouTubeサムネイル用のテキストを生成してください。
視聴者層：歴史や偉人に興味がある一般視聴者（10代〜60代）

【必須情報】
- 人物名: {subject}
- 時代背景: {era}
- 主な功績: {achievement}
- 意外な側面: {unexpected_aspect}

【上部テキスト要件】
以下のパターンから最も効果的なものを5つ生成：

1. 衝撃パターン
   - "衝撃の〇〇" / "驚愕の事実"
   - 感情を揺さぶる短い表現（5-10文字）

2. 疑問パターン
   - "なぜ〇〇？" / "本当に〇〇？"
   - 視聴者に疑問を投げかける（5-10文字）

3. 数字パターン
   - "〇〇％の真実" / "〇〇回の挑戦"
   - 具体的な数字でインパクト（5-10文字）

4. 対比パターン
   - "天才か狂人か" / "英雄か悪人か"
   - 二面性を示す（5-10文字）

5. 意外性パターン
   - "実は〇〇だった" / "知られざる〇〇"
   - 一般認識とのギャップ（5-10文字）

【下部テキスト要件】
上部テキストと連動し、以下の要素を含む（20-30文字）：

1. 知的好奇心を刺激
   - なぜその結果になったのかを示唆
   - 一般に知られていない事実をほのめかす

2. 軽いネタバレ要素
   - 結末を完全に明かさない
   - "〜した男/女の真実"
   - "〜が招いた運命"

3. 視聴欲を高める
   - もっと知りたくなる表現
   - 謎や矛盾を提示

【出力形式】
5パターンをJSON形式で：
{{
    "patterns": [
        {{
            "main": "上部テキスト",
            "sub": "下部テキスト",
            "impact_type": "使用したパターン種別",
            "effectiveness_score": 1-10の効果予測値
        }}
    ]
}}
"""

    def analyze_subject(
        self,
        subject: str,
        script_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        偉人の特徴を分析して生成に必要な情報を抽出

        Args:
            subject: 偉人の名前
            script_content: 台本内容（オプション）

        Returns:
            分析結果の辞書
        """
        self.logger.info(f"Analyzing subject: {subject}")

        analysis_prompt = f"""
{subject}について、サムネイルテキスト生成に必要な情報を分析してください。

【分析項目】
1. 時代背景（いつの時代の人物か）
2. 主な功績（最も有名な業績）
3. 意外な側面（一般的に知られていない事実）
4. ドラマチックな要素（波乱、対立、悲劇など）
5. 現代への影響（なぜ今でも重要か）
6. カテゴリ（科学者、武将、芸術家、政治家、発明家、思想家など）

以下のJSON形式で返してください：
{{
    "era": "時代（例：古代ギリシャ、中世ヨーロッパ、戦国時代、19世紀など）",
    "achievement": "主な功績の簡潔な説明",
    "unexpected_aspect": "意外な側面や知られざる事実",
    "dramatic_element": "ドラマチックな要素",
    "modern_impact": "現代への影響",
    "category": "カテゴリ",
    "culture": "文化圏（西洋/東洋/その他）"
}}
"""

        if script_content:
            analysis_prompt += f"\n\n【参考情報：台本内容】\n{script_content[:500]}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは歴史と偉人に詳しい分析専門家です。正確で魅力的な情報を提供してください。"
                    },
                    {"role": "user", "content": analysis_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )

            analysis = json.loads(response.choices[0].message.content)
            self.logger.info(f"Analysis completed for {subject}")
            self.logger.debug(f"Analysis result: {analysis}")

            return analysis

        except Exception as e:
            self.logger.error(f"Failed to analyze subject: {e}", exc_info=True)
            # フォールバック
            return {
                "era": "不明",
                "achievement": f"{subject}の偉業",
                "unexpected_aspect": "知られざる真実",
                "dramatic_element": "波乱の人生",
                "modern_impact": "現代に残る影響",
                "category": "その他",
                "culture": "不明"
            }

    def generate_text_variations(
        self,
        subject: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        様々なアプローチでテキストを生成

        Args:
            subject: 偉人の名前
            context: コンテキスト情報（分析結果など）

        Returns:
            生成されたテキストバリエーションのリスト
        """
        self.logger.info(f"Generating text variations for: {subject}")

        # 1. 偉人の分析（contextがない場合）
        if not context:
            context = self.analyze_subject(subject)

        # 2. 複数の角度からテキスト生成
        all_variations = []

        approaches = [
            ("shocking", self._generate_shocking_approach(subject, context)),
            ("mystery", self._generate_mystery_approach(subject, context)),
            ("contrast", self._generate_contrast_approach(subject, context)),
            ("number", self._generate_number_approach(subject, context)),
            ("fate", self._generate_fate_approach(subject, context))
        ]

        for approach_name, prompt in approaches:
            try:
                variations = self._call_generation_api(prompt)
                # アプローチ名を追加
                for variation in variations:
                    variation["approach"] = approach_name
                all_variations.extend(variations)
            except Exception as e:
                self.logger.warning(f"Failed to generate {approach_name} approach: {e}")

        self.logger.info(f"Generated {len(all_variations)} total variations")

        return all_variations

    def _generate_shocking_approach(
        self,
        subject: str,
        analysis: Dict[str, Any]
    ) -> str:
        """衝撃・驚愕系アプローチ"""
        return f"""
{subject}の最も衝撃的な事実に焦点を当てたテキスト生成：

【背景情報】
- 時代: {analysis.get('era', '不明')}
- 功績: {analysis.get('achievement', '不明')}
- 意外な側面: {analysis.get('unexpected_aspect', '不明')}
- ドラマ: {analysis.get('dramatic_element', '不明')}

【生成要件】
上部：感情に訴える衝撃的な短文（最大10文字）
例：
- "衝撃の最期"
- "信じられない"
- "まさかの真実"

下部：その衝撃の内容を示唆（ネタバレしすぎない、20-30文字）
例：
- "天才が迎えた悲劇的な結末の真相"
- "誰も予想しなかった運命の皮肉"

3つの候補を以下のJSON形式で出力：
{{
    "patterns": [
        {{
            "main": "上部テキスト",
            "sub": "下部テキスト",
            "impact_type": "衝撃",
            "reasoning": "このテキストが効果的な理由"
        }}
    ]
}}
"""

    def _generate_mystery_approach(
        self,
        subject: str,
        analysis: Dict[str, Any]
    ) -> str:
        """謎・疑問系アプローチ"""
        return f"""
{subject}の謎や矛盾に焦点を当てたテキスト生成：

【背景情報】
- 時代: {analysis.get('era', '不明')}
- 功績: {analysis.get('achievement', '不明')}
- 意外な側面: {analysis.get('unexpected_aspect', '不明')}

【生成要件】
上部：疑問を投げかける（最大10文字）
例：
- "なぜ殺された？"
- "本当の敵は？"
- "隠された理由"

下部：その謎の核心に迫る示唆（20-30文字）
例：
- "歴史が隠した暗殺の真の動機"
- "味方に裏切られた本当の理由"

3つの候補を以下のJSON形式で出力：
{{
    "patterns": [
        {{
            "main": "上部テキスト",
            "sub": "下部テキスト",
            "impact_type": "疑問",
            "reasoning": "このテキストが効果的な理由"
        }}
    ]
}}
"""

    def _generate_contrast_approach(
        self,
        subject: str,
        analysis: Dict[str, Any]
    ) -> str:
        """対比・二面性アプローチ"""
        return f"""
{subject}の二面性や対比に焦点を当てたテキスト生成：

【背景情報】
- 時代: {analysis.get('era', '不明')}
- 功績: {analysis.get('achievement', '不明')}
- ドラマ: {analysis.get('dramatic_element', '不明')}

【生成要件】
上部：対比を示す（最大10文字）
例：
- "天才か狂人か"
- "英雄か悪人か"
- "聖人か罪人か"

下部：その対比の背景を示唆（20-30文字）
例：
- "時代を救った男が憎まれた理由"
- "偉業の裏に隠された暗い真実"

3つの候補を以下のJSON形式で出力：
{{
    "patterns": [
        {{
            "main": "上部テキスト",
            "sub": "下部テキスト",
            "impact_type": "対比",
            "reasoning": "このテキストが効果的な理由"
        }}
    ]
}}
"""

    def _generate_number_approach(
        self,
        subject: str,
        analysis: Dict[str, Any]
    ) -> str:
        """数字・具体性アプローチ"""
        return f"""
{subject}について数字を使った具体的なテキスト生成：

【背景情報】
- 時代: {analysis.get('era', '不明')}
- 功績: {analysis.get('achievement', '不明')}
- 現代への影響: {analysis.get('modern_impact', '不明')}

【生成要件】
上部：数字を含む衝撃的な短文（最大10文字）
例：
- "99%知らない"
- "3回の裏切り"
- "最後の7日間"

下部：その数字の背景を説明（20-30文字）
例：
- "世界を変えた発見が無視された真実"
- "命を救った行動が招いた悲劇"

3つの候補を以下のJSON形式で出力：
{{
    "patterns": [
        {{
            "main": "上部テキスト",
            "sub": "下部テキスト",
            "impact_type": "数字",
            "reasoning": "このテキストが効果的な理由"
        }}
    ]
}}
"""

    def _generate_fate_approach(
        self,
        subject: str,
        analysis: Dict[str, Any]
    ) -> str:
        """運命・意外性アプローチ"""
        return f"""
{subject}の運命や意外な展開に焦点を当てたテキスト生成：

【背景情報】
- 時代: {analysis.get('era', '不明')}
- 意外な側面: {analysis.get('unexpected_aspect', '不明')}
- ドラマ: {analysis.get('dramatic_element', '不明')}

【生成要件】
上部：意外性を示す（最大10文字）
例：
- "実は〇〇だった"
- "知られざる真実"
- "運命の皮肉"

下部：その意外性の内容を示唆（20-30文字）
例：
- "栄光の裏で苦しんだ孤独な人生"
- "成功が招いた予想外の悲劇"

3つの候補を以下のJSON形式で出力：
{{
    "patterns": [
        {{
            "main": "上部テキスト",
            "sub": "下部テキスト",
            "impact_type": "運命",
            "reasoning": "このテキストが効果的な理由"
        }}
    ]
}}
"""

    def _call_generation_api(self, prompt: str) -> List[Dict[str, Any]]:
        """
        テキスト生成APIを呼び出し

        Args:
            prompt: 生成プロンプト

        Returns:
            生成されたパターンのリスト
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたはYouTubeサムネイル用の超インパクトテキストを作成する専門家です。視聴者の興味を最大限に引き出すテキストを生成してください。"
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.9,  # 高めの温度で多様性を確保
            )

            result = json.loads(response.choices[0].message.content)
            patterns = result.get("patterns", [])

            return patterns

        except Exception as e:
            self.logger.error(f"API call failed: {e}", exc_info=True)
            return []

    def select_best_combinations(
        self,
        variations: List[Dict[str, Any]],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        最も効果的な組み合わせを選択

        Args:
            variations: すべてのバリエーション
            top_n: 選択する上位N個

        Returns:
            選択されたトップN個のバリエーション
        """
        # effectiveness_scoreでソート（存在しない場合は0）
        sorted_variations = sorted(
            variations,
            key=lambda x: x.get("effectiveness_score", 0),
            reverse=True
        )

        return sorted_variations[:top_n]


def create_universal_impact_text_generator(
    model: str = "gpt-4o-mini",
    logger: Optional[logging.Logger] = None
) -> UniversalImpactTextGenerator:
    """
    UniversalImpactTextGeneratorのファクトリー関数

    Args:
        model: 使用するモデル
        logger: ロガー

    Returns:
        UniversalImpactTextGenerator インスタンス
    """
    return UniversalImpactTextGenerator(model=model, logger=logger)
