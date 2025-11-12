#!/usr/bin/env python3
"""
手動台本のテンプレートファイルを生成（15分版）

使い方:
    python scripts/create_script_template.py 織田信長
    python scripts/create_script_template.py "グリゴリー・ラスプーチン"
"""

import sys
from pathlib import Path

TEMPLATE = """# ========================================
# 手動台本テンプレート（15分版）
# ========================================

subject: "{subject}"
title: "{subject}の生涯"
description: "{subject}について15分で解説する動画です"

# ========================================
# サムネイル用キャッチコピー
# ========================================
# upper_text: サムネイル上部に表示（推奨: 5-8文字 × 2行）
# lower_text: サムネイル下部に表示（推奨: 10-15文字 × 2行）
# ※ 改行コード \\n を使って2行表示にできます
# ※ インパクトのある短文で視聴者の興味を引くこと

thumbnail:
  upper_text: "ここに上部テキスト\\nを入力"
  lower_text: "ここに下部テキスト\\nを入力"

# 改行の例:
# upper_text: "革新者か\\n破壊者か"
# lower_text: "戦国時代を変えた\\n男の真実"

# ========================================
# セクション（目安：6セクション × 150秒 = 900秒 = 15分）
# ========================================

sections:
  - section_id: 1
    title: "導入：生い立ちと時代背景"
    bgm: "opening"  # opening / main / ending
    atmosphere: "壮大"  # 壮大/静か/希望/劇的/悲劇的
    duration: 150  # 秒（約2.5分）

    narration: |
      ここにナレーション原稿を書く（複数行OK）
      【導入部分の書き方】
      - 生い立ちや出生地
      - 時代背景
      - 視聴者を物語の世界に引き込む
      - インパクトある出だし

    keywords:
      - "{subject}"
      - "生い立ち"
      - "時代背景"

  - section_id: 2
    title: "展開：若き日の試練"
    bgm: "main"
    atmosphere: "劇的"
    duration: 150

    narration: |
      ここにナレーション原稿を書く
      【若き日の書き方】
      - 青年期の困難や挑戦
      - 初めての成功体験
      - 人格形成に影響を与えた出来事

    keywords:
      - "{subject}"
      - "青年期"
      - "試練"

  - section_id: 3
    title: "展開：転機となる出来事"
    bgm: "main"
    atmosphere: "劇的"
    duration: 150

    narration: |
      ここにナレーション原稿を書く
      【転機の書き方】
      - 人生の転機となる重要な出来事
      - 運命の出会い
      - 決断の瞬間

    keywords:
      - "{subject}"
      - "転機"
      - "出会い"

  - section_id: 4
    title: "クライマックス：最盛期と功績"
    bgm: "main"
    atmosphere: "壮大"
    duration: 150

    narration: |
      ここにナレーション原稿を書く
      【最盛期の書き方】
      - 最も輝かしい時期
      - 最大の功績
      - 歴史に残る瞬間

    keywords:
      - "{subject}"
      - "最盛期"
      - "功績"

  - section_id: 5
    title: "転落：晩年の苦悩"
    bgm: "main"
    atmosphere: "悲劇的"
    duration: 150

    narration: |
      ここにナレーション原稿を書く
      【晩年の書き方】
      - 困難や挫折
      - 晩年の苦悩
      - 最期の瞬間

    keywords:
      - "{subject}"
      - "晩年"
      - "苦悩"

  - section_id: 6
    title: "締め：遺産と現代への影響"
    bgm: "ending"
    atmosphere: "希望"
    duration: 150

    narration: |
      ここにナレーション原稿を書く
      【締めの書き方】
      - 後世への影響
      - 現代に残した遺産
      - 感動的な余韻を残す

    keywords:
      - "{subject}"
      - "遺産"
      - "影響"
"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_script_template.py <偉人名>")
        print("\n例:")
        print("  python scripts/create_script_template.py 織田信長")
        print('  python scripts/create_script_template.py "グリゴリー・ラスプーチン"')
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
    print(f"\n📝 15分版テンプレート（6セクション × 150秒 = 900秒）")
    print(f"\n次のステップ:")
    print(f"1. {output_path} を編集")
    print(f"2. python scripts/convert_manual_script.py \"{subject}\"")

if __name__ == "__main__":
    main()