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


class ScriptNormalizer:
    """YAML台本を厳密なフォーマットに正規化"""

    @staticmethod
    def normalize_narration(text: str) -> str:
        """narrationフィールドを正規化

        処理内容:
        1. 空行を完全削除
        2. 文末チェック:
           - 。で終わる → そのまま
           - ！で終わる → そのまま
           - 」で終わる → 」。に変更
           - その他 → 。を追加
        3. 連続改行（\n\n以上）を1つの\nに正規化
        """
        if not text:
            return text

        # 行に分割して処理
        lines = []
        for line in text.split('\n'):
            # 前後の空白を削除
            line = line.strip()

            # 空行はスキップ
            if not line:
                continue

            # 文末チェック
            if line.endswith('。') or line.endswith('！'):
                # 既に正しい文末 → そのまま
                lines.append(line)
            elif line.endswith('」'):
                # 」で終わる場合 → 。を追加
                lines.append(line + '。')
            else:
                # その他 → 。を追加
                lines.append(line + '。')

        # 改行で再結合
        result = '\n'.join(lines)

        # 連続改行を1つに正規化（念のため）
        result = re.sub(r'\n{2,}', '\n', result)

        return result

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

        # セクションを正規化
        if "sections" in data:
            for section in data["sections"]:
                # narrationを正規化
                if "narration" in section:
                    section["narration"] = ScriptNormalizer.normalize_narration(section["narration"])

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
        print(f"⚠️  Warning: 'thumbnail' field not found in {yaml_path.name}, using fallback values")
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
        # narrationは既に正規化済み（空行削除、文末チェック、連続改行正規化が完了）
        narration_text = section.get("narration", "")

        script_json["sections"].append({
            "section_id": section.get("section_id", 0),
            "title": section.get("title", ""),
            "narration": narration_text,
            "estimated_duration": float(section.get("duration", 0)),
            "image_keywords": section.get("keywords", []),
            "atmosphere": section.get("atmosphere", ""),
            "requires_ai_video": False,
            "ai_video_prompt": None,
            "bgm_suggestion": section.get("bgm", "")
        })

        script_json["total_estimated_duration"] += section.get("duration", 0)

    # JSON保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(script_json, f, indent=2, ensure_ascii=False)

    print(f"✅ Converted: {yaml_path.name} → {output_path}")


def main():
    # ロギング設定
    logging.basicConfig(
        level=logging.WARNING,
        format='⚠️  Warning: %(message)s'
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
            print(f"❌ No YAML files found in {manual_dir}")
            sys.exit(1)

        for yaml_file in yaml_files:
            subject = yaml_file.stem
            output_path = output_dir / f"{subject}_script.json"
            convert_yaml_to_json(yaml_file, output_path)

        print(f"\n✅ Converted {len(yaml_files)} files")

    elif args.subject:
        # 指定された偉人のみ
        yaml_path = manual_dir / f"{args.subject}.yaml"
        output_path = output_dir / f"{args.subject}_script.json"

        if not yaml_path.exists():
            print(f"❌ File not found: {yaml_path}")
            sys.exit(1)

        convert_yaml_to_json(yaml_path, output_path)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
