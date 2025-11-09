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
from pathlib import Path
from datetime import datetime
import sys
import argparse


def convert_yaml_to_json(yaml_path: Path, output_path: Path):
    """YAMLをJSONに変換"""

    # YAML読み込み
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # JSON形式に変換
    script_json = {
        "subject": data["subject"],
        "title": data["title"],
        "description": data["description"],
        "sections": [],
        "total_estimated_duration": 0,
        "generated_at": datetime.now().isoformat(),
        "model_version": "manual"
    }

    # セクションを変換
    for section in data["sections"]:
        script_json["sections"].append({
            "section_id": section["section_id"],
            "title": section["title"],
            "narration": section["narration"].strip(),
            "estimated_duration": float(section["duration"]),
            "image_keywords": section["keywords"],
            "atmosphere": section["atmosphere"],
            "requires_ai_video": False,
            "ai_video_prompt": None,
            "bgm_suggestion": section["bgm"]
        })

        script_json["total_estimated_duration"] += section["duration"]

    # JSON保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(script_json, f, indent=2, ensure_ascii=False)

    print(f"✅ Converted: {yaml_path.name} → {output_path}")


def main():
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
