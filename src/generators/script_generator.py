"""
Script Generator - Claude APIを使用した台本生成

Claude APIを呼び出して、構造化された台本を生成する。
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Warning: anthropic package not installed. Run: pip install anthropic")


class ScriptGenerator:
    """
    台本生成クラス
    
    Claude APIを使用して、偉人についての動画台本を生成する。
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 8000,
        temperature: float = 0.7,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            api_key: Claude APIキー
            model: 使用するモデル名
            max_tokens: 最大トークン数
            temperature: 生成の多様性（0-1）
            logger: ロガー
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")
        
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger = logger or logging.getLogger(__name__)
    
    def generate(
        self,
        subject: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        台本を生成
        
        Args:
            subject: 偉人名
            config: 生成設定（config/phases/script_generation.yaml）
            
        Returns:
            生成された台本（辞書形式）
            
        Raises:
            Exception: API呼び出し失敗時
        """
        self.logger.info(f"Generating script for: {subject}")
        
        # プロンプト作成
        prompt = self._build_prompt(subject, config)
        
        # API呼び出し
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # レスポンスからテキストを取得
            response_text = response.content[0].text
            self.logger.debug(f"API Response: {response_text[:200]}...")
            
            # JSONパース
            script_data = self._parse_response(response_text)
            
            # メタデータを追加
            script_data["subject"] = subject
            script_data["generated_at"] = datetime.now().isoformat()
            script_data["model_version"] = self.model
            
            # 推定時間を計算
            total_duration = sum(
                section.get("estimated_duration", 0)
                for section in script_data.get("sections", [])
            )
            script_data["total_estimated_duration"] = total_duration
            
            self.logger.info(
                f"Script generated: {len(script_data.get('sections', []))} sections, "
                f"{total_duration:.0f}s total"
            )
            
            return script_data
            
        except Exception as e:
            self.logger.error(f"Failed to generate script: {e}", exc_info=True)
            raise
    
    def _build_prompt(self, subject: str, config: Dict[str, Any]) -> str:
        """
        プロンプトを構築
        
        Args:
            subject: 偉人名
            config: 生成設定
            
        Returns:
            完成したプロンプト
        """
        # 設定から値を取得
        sections_config = config.get("sections", {})
        count_min = sections_config.get("count_min", 5)
        count_max = sections_config.get("count_max", 7)
        target_duration = sections_config.get("target_duration_per_section", 120)
        
        ai_triggers = config.get("ai_video_trigger_keywords", [])
        
        # プロンプトテンプレート
        prompt_template = config.get("prompt_template", "")
        
        if prompt_template:
            # テンプレートに値を埋め込み
            prompt = prompt_template.format(subject=subject)
        else:
            # デフォルトプロンプト
            prompt = f"""あなたは歴史解説動画の台本作家です。
{subject}について、15分（約900秒）の動画台本を作成してください。

## 要件
1. 全体を{count_min}-{count_max}個のセクションに分割
2. 各セクションは約{target_duration}秒程度
3. 高齢者にも分かりやすい言葉遣い
4. ナレーションは自然な話し言葉
5. 重要なシーンでは「AI動画が必要」と判定

## AI動画が必要と判定するキーワード
{', '.join(ai_triggers) if ai_triggers else '戦闘, 決戦, 革命'}

## 出力形式（JSON）
{{
  "title": "動画タイトル",
  "description": "YouTube説明文（200文字程度）",
  "sections": [
    {{
      "section_id": 1,
      "title": "セクションタイトル",
      "narration": "ナレーション原稿（自然な話し言葉、200-300文字）",
      "estimated_duration": 120,
      "image_keywords": ["キーワード1", "キーワード2", "キーワード3"],
      "atmosphere": "壮大/静か/希望/劇的/悲劇的",
      "requires_ai_video": false,
      "ai_video_prompt": null
    }}
  ]
}}

## 注意事項
- 必ずJSON形式で出力（JSONのみ、説明文は不要）
- ナレーションは読みやすく、句読点を適切に配置
- 画像キーワードは日本語または英語（検索精度向上のため）
- AI動画が必要な場合、ai_video_promptに具体的な描写を記載
- セクションIDは1から連番

それでは、{subject}の台本をJSON形式で出力してください。
"""
        
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        APIレスポンスをパースしてJSON化
        
        Args:
            response_text: APIからの生テキスト
            
        Returns:
            パースされた台本データ
            
        Raises:
            ValueError: JSON パース失敗時
        """
        # JSONブロックを抽出（```json で囲まれている場合）
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            json_text = response_text[start:end].strip()
        else:
            json_text = response_text.strip()
        
        try:
            data = json.loads(json_text)
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            self.logger.debug(f"Raw response: {response_text}")
            
            # リトライ用に整形を試みる
            json_text = self._clean_json_text(json_text)
            try:
                data = json.loads(json_text)
                self.logger.info("JSON parsing succeeded after cleaning")
                return data
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON response from API: {e}")
    
    def _clean_json_text(self, text: str) -> str:
        """
        JSONテキストをクリーンアップ
        
        Args:
            text: 生のテキスト
            
        Returns:
            クリーンアップされたテキスト
        """
        # 先頭・末尾の空白を削除
        text = text.strip()
        
        # コメント行を削除（// で始まる行）
        lines = text.split('\n')
        lines = [line for line in lines if not line.strip().startswith('//')]
        text = '\n'.join(lines)
        
        # 末尾のカンマを削除
        text = text.replace(',\n}', '\n}')
        text = text.replace(',\n]', '\n]')
        
        return text


# ========================================
# テスト用のダミージェネレーター
# ========================================

class DummyScriptGenerator:
    """
    テスト用のダミー台本生成器
    
    APIキーがない場合や、テスト時に使用。
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def generate(self, subject: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """ダミーの台本を生成"""
        self.logger.warning(f"Using dummy generator for: {subject}")
        
        return {
            "subject": subject,
            "title": f"{subject}の生涯 - 激動の時代を生きた偉人",
            "description": f"{subject}の生涯を15分で解説する動画です。",
            "sections": [
                {
                    "section_id": 1,
                    "title": "誕生と幼少期",
                    "narration": f"{subject}は、激動の時代に生まれました。幼い頃から、並外れた才能を示していたと言われています。",
                    "estimated_duration": 120,
                    "image_keywords": [subject, "幼少期", "出生地"],
                    "atmosphere": "静か",
                    "requires_ai_video": False,
                    "ai_video_prompt": None,
                    "bgm_suggestion": "opening"
                },
                {
                    "section_id": 2,
                    "title": "青年期の試練",
                    "narration": f"青年期の{subject}は、数々の困難に直面します。しかし、その経験が後の偉業へとつながっていくのです。",
                    "estimated_duration": 150,
                    "image_keywords": [subject, "青年期", "試練"],
                    "atmosphere": "劇的",
                    "requires_ai_video": False,
                    "ai_video_prompt": None,
                    "bgm_suggestion": "main"
                },
                {
                    "section_id": 3,
                    "title": "最盛期",
                    "narration": f"{subject}は、この時期に最大の功績を残します。その活躍は、歴史に深く刻まれることになりました。",
                    "estimated_duration": 180,
                    "image_keywords": [subject, "最盛期", "功績"],
                    "atmosphere": "壮大",
                    "requires_ai_video": True,
                    "ai_video_prompt": f"{subject}の最も輝かしい瞬間を描く",
                    "bgm_suggestion": "main"
                },
                {
                    "section_id": 4,
                    "title": "晩年",
                    "narration": f"晩年の{subject}は、静かに余生を過ごしました。しかし、その影響力は今も色褪せることがありません。",
                    "estimated_duration": 120,
                    "image_keywords": [subject, "晩年", "隠居"],
                    "atmosphere": "静か",
                    "requires_ai_video": False,
                    "ai_video_prompt": None,
                    "bgm_suggestion": "main"
                },
                {
                    "section_id": 5,
                    "title": "遺産と影響",
                    "narration": f"{subject}が残した遺産は、現代にまで続いています。その功績を振り返りながら、この動画を締めくくりたいと思います。",
                    "estimated_duration": 150,
                    "image_keywords": [subject, "遺産", "影響"],
                    "atmosphere": "希望",
                    "requires_ai_video": False,
                    "ai_video_prompt": None,
                    "bgm_suggestion": "ending"
                }
            ],
            "total_estimated_duration": 720,
            "generated_at": datetime.now().isoformat(),
            "model_version": "dummy"
        }


# ========================================
# ファクトリー関数
# ========================================

def create_script_generator(
    api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    use_dummy: bool = False,
    logger: Optional[logging.Logger] = None
) -> 'ScriptGenerator | DummyScriptGenerator':
    """
    台本生成器を作成
    
    Args:
        api_key: Claude APIキー（Noneの場合はダミー使用）
        config: 生成設定
        use_dummy: 強制的にダミーを使用
        logger: ロガー
        
    Returns:
        ScriptGenerator または DummyScriptGenerator
    """
    if use_dummy or not api_key:
        return DummyScriptGenerator(logger=logger)
    
    config = config or {}
    
    return ScriptGenerator(
        api_key=api_key,
        model=config.get("model", "claude-sonnet-4-20250514"),
        max_tokens=config.get("max_tokens", 8000),
        temperature=config.get("temperature", 0.7),
        logger=logger
    )


if __name__ == "__main__":
    # 簡易テスト
    import os
    import sys
    from pathlib import Path
    
    # プロジェクトルートをパスに追加
    project_root = Path(__file__).parent.parent.parent
    if project_root.exists():
        sys.path.insert(0, str(project_root))
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("Warning: python-dotenv not installed")
    
    # ロガー設定
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s'
    )
    
    # APIキーを取得
    api_key = os.getenv("CLAUDE_API_KEY")
    
    # 設定
    config = {
        "sections": {
            "count_min": 5,
            "count_max": 7,
            "target_duration_per_section": 120
        },
        "ai_video_trigger_keywords": ["戦闘", "決戦", "革命"]
    }
    
    # 生成器を作成
    generator = create_script_generator(
        api_key=api_key,
        config=config,
        use_dummy=not api_key  # APIキーがない場合はダミー使用
    )
    
    # 台本生成
    script = generator.generate("織田信長", config)
    
    # 結果を表示
    print(json.dumps(script, indent=2, ensure_ascii=False))