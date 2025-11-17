"""
YouTube Shorts メタデータ生成

Claude APIを使用して、Shorts向けに最適化されたメタデータを生成する。
"""

import anthropic
import json
import re
from typing import Dict, Any, Optional
import logging


class ShortsMetadataGenerator:
    """Shortsメタデータ生成クラス"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5",
        logger: Optional[logging.Logger] = None
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.logger = logger or logging.getLogger(__name__)

    def generate_metadata(
        self,
        subject: str,
        original_title: str,
        original_description: str,
        clip_number: int,
        total_clips: int,
        main_video_url: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Shorts用メタデータを生成

        Args:
            subject: 偉人名
            original_title: 本編動画のタイトル
            original_description: 本編動画の説明文
            clip_number: クリップ番号（1, 2, 3...）
            total_clips: 総クリップ数
            main_video_url: 本編動画のURL
            config: メタデータ生成設定

        Returns:
            {
                "title": "タイトル #1",
                "description": "説明文\n\n続きはこちら👉 [URL]",
                "tags": ["#Shorts", "歴史", ...]
            }
        """
        config = config or {}

        # タイトル生成
        title_format = config.get("title_format", "{original_title} #{clip_number}")
        title = title_format.format(
            original_title=original_title,
            clip_number=clip_number
        )

        # 説明文生成（Claude API使用）
        try:
            description = self._generate_description_with_claude(
                subject=subject,
                original_description=original_description,
                clip_number=clip_number,
                total_clips=total_clips,
                main_video_url=main_video_url,
                config=config
            )
        except Exception as e:
            self.logger.warning(f"Claude API failed, using fallback: {e}")
            description = self._generate_fallback_description(
                subject=subject,
                clip_number=clip_number,
                main_video_url=main_video_url
            )

        # タグ生成
        tags = self._generate_tags(subject, config)

        return {
            "title": title,
            "description": description,
            "tags": tags
        }

    def _generate_description_with_claude(
        self,
        subject: str,
        original_description: str,
        clip_number: int,
        total_clips: int,
        main_video_url: Optional[str],
        config: Dict[str, Any]
    ) -> str:
        """Claude APIで説明文を生成"""

        template = config.get("description_template", "")

        prompt = f"""
以下のYouTube本編動画の説明文を元に、
Shorts #{clip_number} ({total_clips}本シリーズの{clip_number}本目) 用の
魅力的な短い説明文を生成してください。

【本編の説明文】
{original_description}

【要件】
- 2-3行で簡潔に
- 本編への誘導を含める
- テンプレート: {template}

【出力形式】
JSON形式で以下のキーを含めてください:
{{
  "summary": "短い要約（2-3行）"
}}
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        # レスポンスをパース
        content = response.content[0].text

        # JSONを抽出（```json ... ```を除去）
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        data = json.loads(content)
        summary = data.get("summary", "")

        # テンプレートに埋め込み
        description = template.format(
            summary=summary,
            main_video_url=main_video_url or "",
            subject=subject
        )

        return description

    def _generate_fallback_description(
        self,
        subject: str,
        clip_number: int,
        main_video_url: Optional[str]
    ) -> str:
        """フォールバック用の簡易説明文"""
        desc = f"{subject}の物語 #{clip_number}\n\n"

        if main_video_url:
            desc += f"📺 続きはYouTube本編で！\n👉 {main_video_url}\n\n"

        desc += f"#Shorts #{subject} #歴史 #解説"

        return desc

    def _generate_tags(self, subject: str, config: Dict[str, Any]) -> list:
        """タグ生成"""
        tags = ["Shorts", "歴史", "解説", subject]

        # 設定から追加タグを取得
        additional_tags = config.get("additional_tags", [])
        tags.extend(additional_tags)

        return tags
