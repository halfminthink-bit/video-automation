"""
Script Converter - マークダウン台本をJSON形式に変換

ユーザーが書いたマークダウン形式の台本テキストを、
Phase 1の出力形式（script.json, metadata.json）に自動変換する。
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging


class ScriptConverter:
    """
    マークダウン台本をJSON形式に変換

    入力: data/scripts/{偉人名}.md
    出力: script.json, metadata.json (Phase 1形式)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化

        Args:
            api_key: Claude APIキー（画像キーワード提案用、オプション）
            logger: ロガー
        """
        self.api_key = api_key
        self.logger = logger or logging.getLogger(__name__)
        self.use_api = bool(api_key)

        if self.use_api:
            self.logger.info("Claude API mode enabled for advanced keyword suggestions")
        else:
            self.logger.info("Simple mode: using rule-based keyword extraction")

    def convert(
        self,
        markdown_path: Path,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        マークダウンをJSONに変換

        Args:
            markdown_path: 入力MDファイル
            output_dir: 出力ディレクトリ（script.json, metadata.jsonを保存）
                       Noneの場合は data/working/{subject}/01_script に保存

        Returns:
            変換結果の辞書 {
                'script_path': Path,
                'metadata_path': Path,
                'script_data': Dict
            }
        """
        self.logger.info(f"Converting markdown script: {markdown_path}")

        # 1. マークダウン読み込み
        with open(markdown_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # 2. パース
        parsed = self._parse_markdown(md_content)
        self.logger.info(f"Parsed: subject={parsed['subject']}, sections={len(parsed['paragraphs'])}")

        # 3. セクション生成
        sections = []
        for i, paragraph in enumerate(parsed['paragraphs'], 1):
            section = self._generate_section_info(
                section_id=i,
                narration=paragraph,
                total_sections=len(parsed['paragraphs']),
                subject=parsed['subject']
            )
            sections.append(section)

        # 4. script.json構築
        script_data = {
            "subject": parsed['subject'],
            "title": parsed['title'],
            "description": parsed.get('description') or self._generate_description(
                parsed['subject'],
                '\n'.join(parsed['paragraphs'])
            ),
            "sections": sections,
            "total_estimated_duration": sum(s['estimated_duration'] for s in sections),
            "generated_at": datetime.now().isoformat(),
            "model_version": "script_converter_v1"
        }

        # 5. 出力ディレクトリ決定
        if output_dir is None:
            subject = parsed['subject']
            output_dir = Path(f"data/working/{subject}/01_script")

        output_dir.mkdir(parents=True, exist_ok=True)

        # 6. JSON保存
        script_path, metadata_path = self._save_json(script_data, output_dir)

        self.logger.info(f"✓ Conversion completed")
        self.logger.info(f"  - Total sections: {len(sections)}")
        self.logger.info(f"  - Total duration: {script_data['total_estimated_duration']:.1f}s")

        return {
            'script_path': script_path,
            'metadata_path': metadata_path,
            'script_data': script_data
        }

    def _parse_markdown(self, content: str) -> Dict[str, Any]:
        """
        マークダウンをパース

        Args:
            content: マークダウンテキスト

        Returns:
            {
                'subject': '織田信長',
                'title': 'タイトル',
                'description': '説明文',
                'paragraphs': ['段落1', '段落2', ...]
            }
        """
        lines = content.strip().split('\n')

        subject = None
        title = None
        description = None
        paragraphs = []
        current_paragraph = []

        for line in lines:
            line_stripped = line.strip()

            # タイトル行（# で始まる）
            if line_stripped.startswith('# '):
                title_text = line_stripped[2:].strip()

                # タイトルから偉人名とサブタイトルを分離
                # パターン: "# 織田信長" または "# 織田信長 - サブタイトル"
                if ' - ' in title_text or ' — ' in title_text:
                    # サブタイトル付き
                    separator = ' - ' if ' - ' in title_text else ' — '
                    parts = title_text.split(separator, 1)
                    subject = parts[0].strip()
                    title = title_text  # 完全なタイトルを使用
                else:
                    # サブタイトルなし
                    subject = title_text
                    title = title_text

            # 説明文（> で始まる）
            elif line_stripped.startswith('> '):
                description = line_stripped[2:].strip()

            # 空行 → 段落区切り
            elif line_stripped == '':
                if current_paragraph:
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []

            # 本文
            elif line_stripped:
                current_paragraph.append(line_stripped)

        # 最後の段落を追加
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))

        # バリデーション
        if not subject:
            raise ValueError("No subject found in markdown (expected '# 偉人名' format)")

        if not paragraphs:
            raise ValueError("No paragraphs found in markdown")

        return {
            'subject': subject,
            'title': title,
            'description': description,
            'paragraphs': paragraphs
        }

    def _generate_section_info(
        self,
        section_id: int,
        narration: str,
        total_sections: int,
        subject: str
    ) -> Dict[str, Any]:
        """
        セクションのメタ情報を生成

        Args:
            section_id: セクションID（1から）
            narration: ナレーション文
            total_sections: 総セクション数
            subject: 偉人名

        Returns:
            {
                'section_id': 1,
                'title': '導入',
                'narration': '...',
                'estimated_duration': 20.0,
                'image_keywords': [...],
                'atmosphere': '壮大',
                'requires_ai_video': False,
                'ai_video_prompt': None,
                'bgm_suggestion': 'opening'
            }
        """
        return {
            'section_id': section_id,
            'title': self._generate_section_title(section_id, total_sections),
            'narration': narration,
            'estimated_duration': self._estimate_duration(narration),
            'image_keywords': self._suggest_image_keywords(subject, narration),
            'atmosphere': self._detect_atmosphere(narration),
            'requires_ai_video': False,  # デフォルトはFalse
            'ai_video_prompt': None,
            'bgm_suggestion': self._suggest_bgm(section_id, total_sections)
        }

    def _generate_section_title(self, section_id: int, total_sections: int) -> str:
        """
        セクションタイトルを生成

        Args:
            section_id: セクションID（1から）
            total_sections: 総セクション数

        Returns:
            セクションタイトル
        """
        if total_sections == 1:
            return "本編"
        elif section_id == 1:
            return "導入"
        elif section_id == total_sections:
            return "締め"
        else:
            return "展開"

    def _estimate_duration(self, narration: str) -> float:
        """
        文字数から時間を推定（日本語1文字 ≈ 0.15秒）

        Args:
            narration: ナレーション文

        Returns:
            推定時間（秒）
        """
        char_count = len(narration)
        duration = char_count * 0.15

        # 最小5秒、最大60秒
        return max(5.0, min(60.0, duration))

    def _suggest_image_keywords(self, subject: str, narration: str) -> List[str]:
        """
        画像キーワードを提案

        Claude API使用時: より高度な提案
        非使用時: 簡易的な固有名詞抽出

        Args:
            subject: 偉人名
            narration: ナレーション文

        Returns:
            画像キーワードリスト（3-5個）
        """
        if self.use_api:
            # TODO: Claude APIを使った高度な提案（Phase 3）
            return self._suggest_image_keywords_simple(subject, narration)
        else:
            return self._suggest_image_keywords_simple(subject, narration)

    def _suggest_image_keywords_simple(
        self,
        subject: str,
        narration: str
    ) -> List[str]:
        """
        単純なキーワード抽出（固有名詞抽出）

        Args:
            subject: 偉人名
            narration: ナレーション文

        Returns:
            画像キーワードリスト（最大5個）
        """
        keywords = [subject]

        # 時代・場所関連のキーワードパターン
        era_patterns = [
            r'(戦国時代|江戸時代|明治時代|昭和|平成|鎌倉時代|室町時代)',
            r'(京都|江戸|東京|大阪|尾張|駿府|長崎|横浜)',
        ]

        for pattern in era_patterns:
            matches = re.findall(pattern, narration)
            for match in matches:
                if match not in keywords:
                    keywords.append(match)
                    if len(keywords) >= 5:
                        return keywords

        # カタカナ語（外来語・人名等）
        katakana_pattern = r'[ァ-ヴー]{3,}'
        katakana_words = re.findall(katakana_pattern, narration)
        for word in katakana_words[:2]:
            if word not in keywords:
                keywords.append(word)
                if len(keywords) >= 5:
                    return keywords

        # 重要そうな漢字連続（人名・地名等）
        kanji_pattern = r'[一-龥]{2,}'
        kanji_words = re.findall(kanji_pattern, narration)
        # 頻度の高い一般的な語は除外
        stop_words = ['時代', 'という', 'いました', 'ました', 'として', 'こと', '世紀']

        for word in kanji_words:
            if word not in keywords and word not in stop_words and len(word) >= 2:
                keywords.append(word)
                if len(keywords) >= 5:
                    return keywords

        # 最低3個は確保
        while len(keywords) < 3:
            keywords.append(f"{subject} 歴史")

        return keywords[:5]

    def _detect_atmosphere(self, narration: str) -> str:
        """
        ナレーションから雰囲気を判定

        Args:
            narration: ナレーション文

        Returns:
            雰囲気（壮大/劇的/悲劇的/静か/希望）
        """
        # キーワードベース判定
        atmosphere_keywords = {
            '悲劇的': ['死', '最期', '悲劇', '失敗', '滅亡', '敗北', '消え', '去り', '倒れ'],
            '劇的': ['革新', '戦略', '勝利', '挑戦', '戦い', '倒し', '鎮圧', '立ち向かい'],
            '静か': ['静か', '穏やか', '余生', '晩年', '平和', '安らか'],
            '希望': ['希望', '未来', '継承', '遺産', '受け継', '築い', '残し'],
            '壮大': ['野望', '天下', '統一', '偉業', '大きな', '築き上げ', '創り']
        }

        # 各雰囲気のスコアを計算
        scores = {}
        for atmosphere, keywords in atmosphere_keywords.items():
            score = sum(1 for keyword in keywords if keyword in narration)
            scores[atmosphere] = score

        # 最もスコアの高い雰囲気を返す
        if max(scores.values()) > 0:
            return max(scores.items(), key=lambda x: x[1])[0]

        # デフォルト
        return '壮大'

    def _suggest_bgm(self, section_id: int, total_sections: int) -> str:
        """
        起承転結に基づいてBGMを提案

        Args:
            section_id: セクションID（1から）
            total_sections: 総セクション数

        Returns:
            BGM提案（opening/main/ending）
        """
        if section_id == 1:
            return "opening"
        elif section_id == total_sections:
            return "ending"
        else:
            return "main"

    def _generate_description(self, subject: str, narration_all: str) -> str:
        """
        全ナレーションから説明文を生成

        Args:
            subject: 偉人名
            narration_all: 全ナレーション

        Returns:
            説明文
        """
        # 推定時間を計算
        duration = self._estimate_duration(narration_all)
        minutes = int(duration / 60)

        if minutes == 0:
            time_str = f"{int(duration)}秒"
        else:
            time_str = f"{minutes}分"

        # フォールバック版: シンプルな説明文
        description = f"{subject}の生涯を{time_str}で解説"

        # ナレーションから重要なキーワードを抽出して追加
        keywords = self._suggest_image_keywords_simple(subject, narration_all)
        if len(keywords) > 1:
            # 偉人名を除いた他のキーワードを使用
            other_keywords = [k for k in keywords[1:3] if k != subject]
            if other_keywords:
                description += f"。{', '.join(other_keywords)}を中心に、その栄光と軌跡を追います"

        return description

    def _save_json(
        self,
        script_data: Dict[str, Any],
        output_dir: Path
    ) -> tuple[Path, Path]:
        """
        script.json と metadata.json を保存

        Args:
            script_data: スクリプトデータ
            output_dir: 出力ディレクトリ

        Returns:
            (script_path, metadata_path)
        """
        # script.json
        script_path = output_dir / "script.json"
        with open(script_path, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"✓ Saved script.json to {script_path}")

        # metadata.json
        metadata = self._generate_metadata(script_data)
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        self.logger.info(f"✓ Saved metadata.json to {metadata_path}")

        return script_path, metadata_path

    def _generate_metadata(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        metadata.jsonを生成

        Args:
            script_data: スクリプトデータ

        Returns:
            メタデータ辞書
        """
        # 雰囲気の分布を計算
        atmosphere_distribution = {}
        for section in script_data['sections']:
            atmosphere = section['atmosphere']
            atmosphere_distribution[atmosphere] = atmosphere_distribution.get(atmosphere, 0) + 1

        # AI動画セクション数をカウント
        ai_video_sections = sum(1 for s in script_data['sections'] if s.get('requires_ai_video', False))

        return {
            'subject': script_data['subject'],
            'phase': 1,
            'phase_name': 'Script Generation',
            'generated_at': script_data['generated_at'],
            'model_version': script_data['model_version'],
            'total_sections': len(script_data['sections']),
            'total_duration': script_data['total_estimated_duration'],
            'ai_video_sections': ai_video_sections,
            'atmosphere_distribution': atmosphere_distribution,
            'config_used': {
                'model': 'script_converter',
                'temperature': None,
                'max_tokens': None
            }
        }
