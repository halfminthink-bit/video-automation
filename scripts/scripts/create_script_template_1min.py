#!/usr/bin/env python3
"""
手動台本のテンプレートファイルを生成（1分版）

使い方:
    python scripts/create_script_template_1min.py 織田信長
    python scripts/create_script_template_1min.py "グリゴリー・ラスプーチン"
"""

import sys
from pathlib import Path

TEMPLATE = """# ========================================
# 手動台本テンプレート（1分版）
# ========================================

subject: "{subject}"
title: "{subject}の生涯"
description: "{subject}について1分で解説する短編動画です"

# ========================================
# セクション（3セクション × 20秒 = 60秒 = 1分）
# ========================================

sections:
  - section_id: 1
    title: "導入"
    bgm: "opening"  # opening / main / ending
    atmosphere: "壮大"  # 壮大/静か/希望/劇的/悲劇的
    duration: 20  # 秒

    narration: |
      ここにナレーション原稿を書く（複数行OK）
      
      【導入の書き方】
      - インパクトある出だし
      - 最も印象的な事実を提示
      - 視聴者の興味を引く

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
      
      【展開の書き方】
      - 最も重要なエピソード
      - クライマックスとなる出来事
      - 短く濃く伝える

    keywords:
      - "{subject}"
      - "キーワード4"
      - "キーワード5"

  - section_id: 3
    title: "締め"
    bgm: "ending"
    atmosphere: "希望"
    duration: 20

    narration: |
      ここにナレーション原稿を書く
      
      【締めの書き方】
      - 最も印象的な結末
      - 感動的な余韻
      - 視聴者の心に残る一言

    keywords:
      - "{subject}"
      - "キーワード6"
      - "キーワード7"
"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_script_template_1min.py <偉人名>")
        print("\n例:")
        print("  python scripts/create_script_template_1min.py 織田信長")
        print('  python scripts/create_script_template_1min.py "グリゴリー・ラスプーチン"')
        sys.exit(1)

    subject = sys.argv[1]
    output_dir = Path("data/input/manual_scripts")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1分版は _1min サフィックスを付ける
    output_path = output_dir / f"{subject}_1min.yaml"

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
    print(f"\n📝 1分版テンプレート（3セクション × 20秒 = 60秒）")
    print(f"\n次のステップ:")
    print(f"1. {output_path} を編集")
    print(f"2. python scripts/convert_manual_script.py \"{subject}_1min\"")

if __name__ == "__main__":
    main()