"""
YouTube メタデータ生成ユーティリティ

Claude APIを使用してYouTube動画のメタデータを生成する
"""

import json
import os
from typing import Dict, Any, Optional
import logging
from anthropic import Anthropic


class YouTubeMetadataGenerator:
    """Claude APIを使用してYouTubeメタデータを生成"""

    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            config: metadata_generation設定
            logger: ロガー
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Claude API初期化
        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            raise ValueError("CLAUDE_API_KEY environment variable not set")

        self.client = Anthropic(api_key=api_key)

        # 設定値を取得
        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.max_tokens = config.get("max_tokens", 4000)
        self.temperature = config.get("temperature", 0.7)
        self.system_prompt = config.get("system_prompt", "")
        self.user_prompt_template = config.get("user_prompt_template", "")

    def generate_metadata(
        self,
        subject: str,
        script_content: str,
        image_themes: str,
        duration: float,
        target_audience: str,
        tag_strategy: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        メタデータを生成

        Args:
            subject: 動画のテーマ（偉人名）
            script_content: スクリプトの内容
            image_themes: 画像のテーマ（Phase 3/4から抽出）
            duration: 動画の長さ（秒）
            target_audience: ターゲット視聴者
            tag_strategy: タグ生成戦略

        Returns:
            メタデータ辞書
        """
        self.logger.info(f"Generating YouTube metadata for: {subject}")

        # ユーザープロンプトを構築
        user_prompt = self.user_prompt_template.format(
            subject=subject,
            duration=int(duration),
            target_audience=target_audience,
            script_content=script_content[:3000],  # トークン制限のため3000文字まで
            image_themes=image_themes[:1000],      # 1000文字まで
            big_keywords=tag_strategy.get("big_keywords", 3),
            medium_keywords=tag_strategy.get("medium_keywords", 5),
            long_tail_keywords=tag_strategy.get("long_tail_keywords", 7)
        )

        try:
            # Claude APIを呼び出し
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )

            # レスポンスからテキストを取得
            response_text = response.content[0].text

            # JSONを抽出（```json ... ``` の部分）
            metadata = self._extract_json_from_response(response_text)

            # バリデーション
            self._validate_metadata(metadata)

            self.logger.info("Metadata generation successful")
            self.logger.debug(f"Generated title: {metadata.get('title')}")
            self.logger.debug(f"Generated {len(metadata.get('tags', []))} tags")

            return metadata

        except Exception as e:
            self.logger.error(f"Failed to generate metadata: {e}")
            # フォールバックメタデータを返す
            return self._create_fallback_metadata(subject, duration)

    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        レスポンスからJSONを抽出

        Args:
            response_text: Claude APIのレスポンステキスト

        Returns:
            メタデータ辞書
        """
        # ```json ... ``` の部分を探す
        start_marker = "```json"
        end_marker = "```"

        start_idx = response_text.find(start_marker)
        if start_idx == -1:
            # マーカーがない場合は全体をJSONとしてパース
            return json.loads(response_text)

        start_idx += len(start_marker)
        end_idx = response_text.find(end_marker, start_idx)

        if end_idx == -1:
            raise ValueError("JSON end marker not found")

        json_str = response_text[start_idx:end_idx].strip()
        return json.loads(json_str)

    def _validate_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        メタデータをバリデーション

        Args:
            metadata: メタデータ辞書

        Raises:
            ValueError: バリデーションエラー
        """
        # 必須フィールドのチェック
        required_fields = ["title", "description", "tags"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field: {field}")

        # タイトルの長さチェック
        title = metadata["title"]
        if len(title) > 100:
            self.logger.warning(f"Title too long ({len(title)} chars), truncating to 100")
            metadata["title"] = title[:97] + "..."

        # タグの数チェック
        tags = metadata["tags"]
        if len(tags) > 15:
            self.logger.warning(f"Too many tags ({len(tags)}), keeping first 15")
            metadata["tags"] = tags[:15]

        # 各タグの長さチェック
        for i, tag in enumerate(tags):
            if len(tag) > 30:
                self.logger.warning(f"Tag too long: {tag}, truncating")
                metadata["tags"][i] = tag[:30]

        # 説明文の長さチェック
        description = metadata["description"]
        if len(description) > 5000:
            self.logger.warning(f"Description too long ({len(description)} chars), truncating")
            metadata["description"] = description[:4997] + "..."

    def _create_fallback_metadata(
        self,
        subject: str,
        duration: float
    ) -> Dict[str, Any]:
        """
        フォールバックメタデータを作成

        Args:
            subject: 動画のテーマ
            duration: 動画の長さ（秒）

        Returns:
            フォールバックメタデータ
        """
        self.logger.info("Using fallback metadata")

        minutes = int(duration / 60)

        return {
            "title": f"{subject}の物語【歴史解説】",
            "description": f"""
{subject}について詳しく解説します。

この動画では、{subject}の生涯と功績について、
わかりやすく紹介しています。

【動画の長さ】
約{minutes}分

【チャンネル登録お願いします】
歴史解説動画を定期的に投稿しています。

#歴史 #{subject} #解説
""".strip(),
            "tags": [
                "歴史",
                "偉人",
                "解説",
                subject,
                f"{subject}の生涯",
                "歴史解説",
                "日本史",
                "世界史"
            ],
            "category_id": "22",
            "privacy_status": "private"
        }
