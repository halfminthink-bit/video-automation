"""
YouTube Shorts メタデータ生成ユーティリティ

Claude APIを使用して、Shorts向けに最適化されたメタデータを生成する。
本編動画への誘導を含む説明文を自動生成。
"""

import json
import os
from typing import Dict, Any, Optional
import logging
from anthropic import Anthropic


class ShortsMetadataGenerator:
    """Shortsメタデータ生成クラス"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-haiku-4-5",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            api_key: Claude APIキー（Noneの場合は環境変数から取得）
            model: Claudeモデル名
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)

        # Claude API初期化
        api_key = api_key or os.getenv("CLAUDE_API_KEY")
        if not api_key:
            raise ValueError("CLAUDE_API_KEY not provided and environment variable not set")

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate_metadata(
        self,
        subject: str,
        original_title: str,
        original_description: str,
        clip_number: int,
        total_clips: int,
        main_video_url: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Shorts用メタデータを生成

        Args:
            subject: 偉人名
            original_title: 本編動画のタイトル
            original_description: 本編動画の説明文
            clip_number: クリップ番号（1, 2, 3...）
            total_clips: 総クリップ数
            main_video_url: 本編動画のURL（Phase 9の結果から取得）
            max_tokens: 最大トークン数
            temperature: 温度パラメータ

        Returns:
            {
                "title": "タイトル #1",
                "description": "説明文\n\n続きはこちら👉 [URL]",
                "tags": ["#Shorts", "歴史", ...]
            }
        """
        self.logger.info(f"Generating Shorts metadata for: {subject} (clip {clip_number}/{total_clips})")

        # シンプルなタイトル生成
        title = f"{original_title} #{clip_number}"

        # システムプロンプト
        system_prompt = """
あなたはYouTube Shortsのメタデータ最適化の専門家です。

【目標】
1. 短くて魅力的な説明文を作成
2. 本編動画への誘導を自然に組み込む
3. #Shortsハッシュタグを含める

【制約条件】
- 説明文: 2-3行の簡潔な要約 + 本編誘導 + ハッシュタグ
- タグ: 5-8個（必ず#Shortsを含める）
- 日本語で自然な表現
"""

        # ユーザープロンプト
        user_prompt = f"""
以下のYouTube Shorts用メタデータを生成してください。

## 動画情報
- テーマ: {subject}
- 本編タイトル: {original_title}
- クリップ番号: {clip_number}/{total_clips}
- 本編URL: {main_video_url or "（なし）"}

## 本編の説明文（要約に使用）
{original_description[:500]}

## 出力形式
以下のJSON形式で出力してください：

```json
{{
  "description": "2-3行の魅力的な要約\\n\\n📺 続きはYouTube本編で！\\n👉 {main_video_url or '[URL]'}\\n\\n#Shorts #{subject} #歴史 #解説",
  "tags": ["Shorts", "歴史", "{subject}", "解説", ...]
}}
```

## 説明文の構成
1. フック（1-2行）: このクリップの見どころを端的に
2. 本編誘導: 「📺 続きはYouTube本編で！」+ URL
3. ハッシュタグ: #Shorts #{subject} #歴史 など

## タグの戦略
- 必須: "Shorts"（必ず含める）
- テーマ: "{subject}", "歴史", "解説"
- 関連キーワード: 時代、エピソード等（3-5個）
"""

        try:
            # Claude APIを呼び出し
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )

            # レスポンスからテキストを取得
            response_text = response.content[0].text

            # JSONを抽出
            metadata = self._extract_json(response_text)

            # タイトルを追加
            metadata["title"] = title

            # タグに "Shorts" が含まれていることを確認
            if "tags" in metadata and "Shorts" not in metadata["tags"]:
                metadata["tags"].insert(0, "Shorts")

            self.logger.info(f"Metadata generated successfully for clip {clip_number}")
            self.logger.debug(f"Title: {metadata.get('title')}")
            self.logger.debug(f"Tags: {metadata.get('tags')}")

            return metadata

        except Exception as e:
            self.logger.error(f"Failed to generate metadata via Claude API: {e}")
            # フォールバック: シンプルなメタデータを返す
            return self._create_fallback_metadata(
                subject=subject,
                title=title,
                clip_number=clip_number,
                main_video_url=main_video_url
            )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        テキストからJSONを抽出

        Args:
            text: Claude APIのレスポンステキスト

        Returns:
            抽出されたJSON（辞書）

        Raises:
            ValueError: JSONの抽出に失敗した場合
        """
        # コードブロックからJSONを抽出
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            json_str = text[start:end].strip()
        else:
            # コードブロックがない場合、全体をJSONとして解析
            json_str = text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            self.logger.debug(f"JSON string: {json_str}")
            raise ValueError(f"Invalid JSON in response: {e}")

    def _create_fallback_metadata(
        self,
        subject: str,
        title: str,
        clip_number: int,
        main_video_url: Optional[str]
    ) -> Dict[str, Any]:
        """
        フォールバック用のシンプルなメタデータを作成

        Args:
            subject: 偉人名
            title: タイトル
            clip_number: クリップ番号
            main_video_url: 本編URL

        Returns:
            シンプルなメタデータ
        """
        self.logger.warning("Using fallback metadata")

        description = f"{subject}の物語 Part {clip_number}\n\n"

        if main_video_url:
            description += f"📺 続きはYouTube本編で！\n👉 {main_video_url}\n\n"

        description += f"#Shorts #{subject} #歴史 #解説"

        return {
            "title": title,
            "description": description,
            "tags": ["Shorts", "歴史", subject, "解説", "偉人"]
        }
