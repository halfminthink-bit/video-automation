"""
キャッチコピー生成器

Claudeを使用してYouTubeサムネイル用のバズるキャッチコピーを生成します。
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI


# Ensure .env values override existing environment variables
load_dotenv(override=True)


class CatchcopyGenerator:
    """Claudeを使用してキャッチコピーを生成"""
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            model: 使用するモデル（デフォルト: gpt-4.1-mini）
            logger: ロガー
        """
        self.model = model
        self.client = OpenAI()
        self.logger = logger or logging.getLogger(__name__)
    
    def generate_catchcopy(
        self,
        subject: str,
        script_data: Dict[str, Any],
        tone: str = "dramatic",
        target_audience: str = "一般",
        main_length: int = 20,
        sub_length: int = 10,
        num_candidates: int = 5
    ) -> List[Dict[str, str]]:
        """
        キャッチコピーを生成
        
        Args:
            subject: 動画のテーマ
            script_data: 台本データ
            tone: 口調（dramatic, shocking, educational, casual）
            target_audience: ターゲット層
            main_length: メインタイトルの文字数
            sub_length: サブタイトルの文字数
            num_candidates: 候補数
            
        Returns:
            キャッチコピーの候補リスト
        """
        self.logger.info(f"Generating catchcopy for: {subject}")
        self.logger.info(f"Tone: {tone}, Target: {target_audience}")
        
        # プロンプトを構築
        prompt = self._build_prompt(
            subject, script_data, tone, target_audience,
            main_length, sub_length, num_candidates
        )
        
        try:
            # Claude APIを呼び出し
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.8,  # 創造性を高める
            )
            
            # JSONをパース
            result = json.loads(response.choices[0].message.content)
            candidates = result.get("candidates", [])
            
            self.logger.info(f"Generated {len(candidates)} catchcopy candidates")
            
            # 候補をログ出力
            for i, candidate in enumerate(candidates, 1):
                self.logger.debug(
                    f"Candidate {i}: {candidate.get('main_title')} / "
                    f"{candidate.get('sub_title')}"
                )
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"Failed to generate catchcopy: {e}", exc_info=True)
            # フォールバック: デフォルトのキャッチコピーを返す
            return self._get_fallback_candidates(subject)
    
    def _get_system_prompt(self) -> str:
        """システムプロンプトを取得"""
        return """あなたはYouTubeサムネイルのキャッチコピーを考える専門家です。
視聴者の注目を引き、クリック率を最大化する文言を生成してください。

以下の原則に従ってください：
1. インパクトがある
2. 疑問を喚起する
3. 感情を揺さぶる
4. 具体的である
5. 短くて覚えやすい
6. 誇張しすぎない（クリックベイトにならない）

日本語で出力してください。"""
    
    def _build_prompt(
        self,
        subject: str,
        script_data: Dict[str, Any],
        tone: str,
        target_audience: str,
        main_length: int,
        sub_length: int,
        num_candidates: int
    ) -> str:
        """ユーザープロンプトを構築"""
        # 台本の概要を抽出
        script_summary = self._extract_script_summary(script_data)
        
        # トーンの説明
        tone_descriptions = {
            "dramatic": "劇的で感動的な表現を使う",
            "shocking": "衝撃的で驚きを与える表現を使う",
            "educational": "教育的で知的な表現を使う",
            "casual": "カジュアルで親しみやすい表現を使う"
        }
        tone_desc = tone_descriptions.get(tone, "バランスの取れた表現を使う")
        
        return f"""動画のテーマ: {subject}

台本の概要:
{script_summary}

以下の条件でキャッチコピーを生成してください：
- 口調: {tone} ({tone_desc})
- ターゲット層: {target_audience}
- 文字数: メインタイトル {main_length}文字以内、サブタイトル {sub_length}文字以内

以下のJSON形式で{num_candidates}つの候補を出力してください：
{{
  "candidates": [
    {{
      "main_title": "メインタイトル",
      "sub_title": "サブタイトル",
      "reasoning": "このコピーを選んだ理由"
    }}
  ]
}}

注意: 
- メインタイトルとサブタイトルは必ず指定された文字数以内にしてください
- 各候補は異なるアプローチで作成してください
- クリックベイトにならないように注意してください"""
    
    def _extract_script_summary(self, script_data: Dict[str, Any]) -> str:
        """台本から概要を抽出"""
        sections = script_data.get("sections", [])
        
        if not sections:
            # セクションがない場合はsubjectのみ
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
        フォールバック用のデフォルト候補を返す
        
        Args:
            subject: テーマ
            
        Returns:
            デフォルトのキャッチコピー候補
        """
        self.logger.warning("Using fallback catchcopy candidates")
        
        return [
            {
                "main_title": f"{subject}の真実",
                "sub_title": "知られざる物語",
                "reasoning": "フォールバック（デフォルト）"
            },
            {
                "main_title": f"{subject}とは何か",
                "sub_title": "徹底解説",
                "reasoning": "フォールバック（デフォルト）"
            },
            {
                "main_title": f"{subject}の秘密",
                "sub_title": "驚きの事実",
                "reasoning": "フォールバック（デフォルト）"
            }
        ]
