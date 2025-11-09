#!/usr/bin/env python3
"""
手動台本のテンプレートファイルを生成

使い方:
    python scripts/create_script_template.py 織田信長
"""

import sys
from pathlib import Path

TEMPLATE = """# ========================================
# 手動台本テンプレート
# ========================================

subject: "{subject}"
title: "{subject}の生涯"
description: "{subject}について解説する動画です"

# ========================================
# セクション
# ========================================

sections:
  - section_id: 1
    title: "導入"
    bgm: "opening"  # opening / main / ending
    atmosphere: "壮大"  # 壮大/静か/希望/劇的/悲劇的
    duration: 20  # 秒

    narration: |
      ここにナレーション原稿を書く（複数行OK）

    keywords:
      - "{subject}"
      - "キーワード2"
      - "キーワード3"

  - section_id: 2
    title: "展開"
    bgm: "main"
    atmosphere: "劇的"
    duration: 20

    narration: |
      ここにナレーション原稿を書く

    keywords:
      - "{subject}"
      - "キーワード4"

  - section_id: 3
    title: "締め"
    bgm: "ending"
    atmosphere: "希望"
    duration: 20

    narration: |
      ここにナレーション原稿を書く

    keywords:
      - "{subject}"
      - "キーワード5"
"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_script_template.py <偉人名>")
        sys.exit(1)

    subject = sys.argv[1]
    output_dir = Path("data/input/manual_scripts")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{subject}.yaml"

    if output_path.exists():
        print(f"⚠️  File already exists: {output_path}")
        overwrite = input("Overwrite? (y/n): ")
        if overwrite.lower() != 'y':
            print("Cancelled")
            sys.exit(0)

    # テンプレート生成
    content = TEMPLATE.format(subject=subject)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Template created: {output_path}")
    print(f"\n次のステップ:")
    print(f"1. {output_path} を編集")
    print(f"2. python scripts/convert_manual_script.py {subject}")

if __name__ == "__main__":
    main()
