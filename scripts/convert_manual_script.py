#!/usr/bin/env python3
"""
手動台本（YAML）をJSON形式に変換するスクリプト

使い方:
    python scripts/convert_manual_script.py イグナーツ・ゼンメルワイス

    または

    python scripts/convert_manual_script.py --all  # 全て変換
"""

import yaml
import json
import re
import logging
from pathlib import Path
from datetime import datetime
import sys
import argparse

logger = logging.getLogger(__name__)


def safe_print(text: str):
    """絵文字を含む文字列を安全に出力（Windowsのエンコーディングエラーを回避）"""
    try:
        print(text)
    except UnicodeEncodeError:
        # 絵文字をASCII文字に置き換え
        safe_text = text.replace('✅', '[OK]').replace('❌', '[ERROR]').replace('⚠️', '[WARNING]')
        print(safe_text)


class ScriptNormalizer:
    """YAML台本を厳密なフォーマットに正規化"""

    @staticmethod
    def extract_impact_sentences(text: str) -> tuple:
        """
        narrationからimpact markersを抽出
        
        マーカー形式:
        - @@文章@@   : normal（赤・70px）
        - @@@文章@@@ : mega（特大・中央、Phase 2で実装予定）
        
        Args:
            text: 元のnarration（マーカー付き）
        
        Returns:
            (clean_text, impact_data)
            - clean_text: マーカーを削除したnarration（TTS用）
            - impact_data: {"normal": [...], "mega": [...]}
        
        Example:
            入力:
                "「うつけ者」と呼ばれた。
                 @@誰もが侮った男が、革命児となった。@@
                 織田信長は天下を目指す。"
            
            出力:
                clean_text = "「うつけ者」と呼ばれた。\n誰もが侮った男が、革命児となった。\n織田信長は天下を目指す。"
                impact_data = {
                    "normal": ["誰もが侮った男が、革命児となった。"],
                    "mega": []
                }
        """
        impact_data = {"normal": [], "mega": []}
        
        # @@@...@@@ を検出（mega）- Phase 2で実装予定
        # 注意: @@@を先にチェックしないと@@にマッチしてしまう
        mega_pattern = r'@@@(.+?)@@@'
        for match in re.finditer(mega_pattern, text, re.DOTALL):
            sentence = match.group(1).strip()
            # 改行を含む場合は削除
            sentence = sentence.replace('\n', '')
            if sentence:
                impact_data["mega"].append(sentence)
        
        # @@...@@ を検出（normal）
        normal_pattern = r'@@(.+?)@@'
        for match in re.finditer(normal_pattern, text, re.DOTALL):
            sentence = match.group(1).strip()
            # 改行を含む場合は削除
            sentence = sentence.replace('\n', '')
            # megaと重複しないようにチェック
            if sentence and sentence not in impact_data["mega"]:
                impact_data["normal"].append(sentence)
        
        # マーカーを削除（TTSに影響しないように）
        clean_text = re.sub(r'@@@(.+?)@@@', r'\1', text)  # mega削除
        clean_text = re.sub(r'@@(.+?)@@', r'\1', clean_text)  # normal削除
        
        return clean_text, impact_data

    @staticmethod
    def normalize_narration(text: str) -> tuple:
        """
        narrationフィールドを正規化 + impact抽出
        
        処理順序:
        1. まずimpact markersを抽出（マーカー削除）
        2. その後、既存の正規化処理（空行削除、文末チェック等）
        
        Returns:
            (normalized_text, impact_data)
        
        Note:
            既存のnormalize_narrationメソッドを拡張
        """
        if not text:
            return text, {"normal": [], "mega": []}
        
        # 1. impact markersを抽出（先にやる！）
        clean_text, impact_data = ScriptNormalizer.extract_impact_sentences(text)
        
        # 2. 既存の正規化処理（空行削除、文末チェック等）
        lines = []
        for line in clean_text.split('\n'):
            line = line.strip()
            
            # 空行はスキップ
            if not line:
                continue
            
            # 文末チェック
            if line.endswith('。') or line.endswith('！'):
                lines.append(line)
            elif line.endswith('」'):
                lines.append(line + '。')
            else:
                lines.append(line + '。')
        
        result = '\n'.join(lines)
        result = re.sub(r'\n{2,}', '\n', result)
        
        return result, impact_data

    @staticmethod
    def normalize_thumbnail(thumbnail: dict) -> dict:
        """サムネイルテキストを正規化

        処理内容:
        upper_text:
          - 1行あたり3文字まで
          - 超過している場合は警告ログ
          - 2行目以降の先頭に全角スペース「　」を自動挿入

        lower_text:
          - 1行あたり5-7文字（推奨）
          - 範囲外の場合は警告ログ
          - 2行目以降の先頭に全角スペース「　」を自動挿入
        """
        if not thumbnail:
            return thumbnail

        # upper_textの正規化
        if "upper_text" in thumbnail:
            upper_lines = []
            for i, line in enumerate(thumbnail["upper_text"].split('\n')):
                line = line.strip()

                # 文字数チェック
                if len(line) > 3:
                    logger.warning(f"upper_text行が3文字超過: {line} ({len(line)}文字)")

                # 2行目以降は全角スペースを追加
                if i > 0 and line:
                    line = '　' + line

                upper_lines.append(line)

            thumbnail["upper_text"] = '\n'.join(upper_lines)

        # lower_textの正規化
        if "lower_text" in thumbnail:
            lower_lines = []
            for i, line in enumerate(thumbnail["lower_text"].split('\n')):
                line = line.strip()

                # 文字数チェック（5-7文字推奨）
                if line and (len(line) < 5 or len(line) > 7):
                    logger.warning(f"lower_text行が推奨範囲外: {line} ({len(line)}文字、推奨5-7文字)")

                # 2行目以降は全角スペースを追加
                if i > 0 and line:
                    line = '　' + line

                lower_lines.append(line)

            thumbnail["lower_text"] = '\n'.join(lower_lines)

        return thumbnail

    @staticmethod
    def normalize(data: dict) -> dict:
        """YAML全体を正規化（メインメソッド）"""
        # サムネイルを正規化
        if "thumbnail" in data and data["thumbnail"]:
            data["thumbnail"] = ScriptNormalizer.normalize_thumbnail(data["thumbnail"])

        # セクションを正規化（impact抽出はconvert_yaml_to_jsonで行う）
        if "sections" in data:
            for section in data["sections"]:
                # narrationはここでは正規化しない（convert_yaml_to_jsonでimpact抽出と同時に行う）
                # bgm_suggestionのチェック
                if "bgm" not in section or not section.get("bgm"):
                    section_id = section.get("section_id", "unknown")
                    logger.warning(f"Section {section_id}: bgm_suggestionが未設定です（デフォルト'main'を使用）")
                    section["bgm"] = "main"

        return data


def convert_yaml_to_json(yaml_path: Path, output_path: Path):
    """YAMLをJSONに変換"""

    # YAML読み込み
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # 🔥 正規化処理
    normalizer = ScriptNormalizer()
    data = normalizer.normalize(data)

    # サムネイル情報の取得（フォールバック付き）
    thumbnail_data = data.get("thumbnail")
    if thumbnail_data is None:
        safe_print(f"⚠️  Warning: 'thumbnail' field not found in {yaml_path.name}, using fallback values")
        thumbnail = {
            "upper_text": data["subject"],  # フォールバック: 偉人名
            "lower_text": ""                # フォールバック: 空文字
        }
    else:
        thumbnail = {
            "upper_text": thumbnail_data.get("upper_text", data["subject"]),
            "lower_text": thumbnail_data.get("lower_text", "")
        }
        # 注: thumbnail内のテキストはstrip()しない（改行コード \n を保持するため）

    # JSON形式に変換
    script_json = {
        "subject": data["subject"],
        "title": data["title"],
        "description": data["description"],
        "thumbnail": thumbnail,
        "sections": [],
        "total_estimated_duration": 0,
        "generated_at": datetime.now().isoformat(),
        "model_version": "manual"
    }

    # セクションを変換（正規化済みデータから）
    for section in data["sections"]:
        # narrationを正規化 + impact抽出
        narration_text = section.get("narration", "")
        normalized_narration, impact_data = ScriptNormalizer.normalize_narration(narration_text)

        script_json["sections"].append({
            "section_id": section.get("section_id", 0),
            "title": section.get("title", ""),
            "narration": normalized_narration,  # ← マーカー削除済み（TTS用）
            "estimated_duration": float(section.get("duration", 0)),
            "image_keywords": section.get("keywords", []),
            "atmosphere": section.get("atmosphere", ""),
            "requires_ai_video": False,
            "ai_video_prompt": None,
            "bgm_suggestion": section.get("bgm", ""),
            "impact_sentences": impact_data  # ← 新規追加！
        })

        script_json["total_estimated_duration"] += section.get("duration", 0)

    # JSON保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(script_json, f, indent=2, ensure_ascii=False)

    safe_print(f"✅ Converted: {yaml_path.name} → {output_path}")


def main():
    # ロギング設定
    logging.basicConfig(
        level=logging.WARNING,
        format='[WARNING] %(message)s'
    )

    parser = argparse.ArgumentParser(description="手動台本をJSONに変換")
    parser.add_argument("subject", nargs="?", help="偉人名")
    parser.add_argument("--all", action="store_true", help="全て変換")
    args = parser.parse_args()

    manual_dir = Path("data/input/manual_scripts")
    output_dir = Path("data/input/manual_overrides")

    if args.all:
        # 全てのYAMLを変換
        yaml_files = list(manual_dir.glob("*.yaml"))
        if not yaml_files:
            safe_print(f"❌ No YAML files found in {manual_dir}")
            sys.exit(1)

        for yaml_file in yaml_files:
            subject = yaml_file.stem
            output_path = output_dir / f"{subject}_script.json"
            convert_yaml_to_json(yaml_file, output_path)

        safe_print(f"\n✅ Converted {len(yaml_files)} files")

    elif args.subject:
        # 指定された偉人のみ
        yaml_path = manual_dir / f"{args.subject}.yaml"
        output_path = output_dir / f"{args.subject}_script.json"

        if not yaml_path.exists():
            safe_print(f"❌ File not found: {yaml_path}")
            sys.exit(1)

        convert_yaml_to_json(yaml_path, output_path)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
