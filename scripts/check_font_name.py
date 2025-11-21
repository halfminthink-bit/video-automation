"""フォントファイルの内部名を確認するスクリプト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from fontTools.ttLib import TTFont
    
    font_path = project_root / "assets" / "fonts" / "cinema" / "cinecaption226.ttf"
    
    if not font_path.exists():
        print(f"[ERROR] フォントファイルが見つかりません: {font_path}")
        sys.exit(1)
    
    print(f"[INFO] フォントファイル: {font_path}")
    print(f"[INFO] ファイルサイズ: {font_path.stat().st_size / 1024:.1f} KB")
    print()
    
    # フォントを読み込む
    font = TTFont(str(font_path))
    name_table = font['name']
    
    print("[INFO] フォント内部名:")
    print("=" * 60)
    
    # 重要な名前IDを取得
    name_ids = {
        1: "Font Family (フォントファミリー名)",
        2: "Font Subfamily (フォントサブファミリー名)",
        3: "Unique Font Identifier (一意のフォント識別子)",
        4: "Full Font Name (完全なフォント名)",
        6: "PostScript Name (PostScript名)",
    }
    
    def decode_name(record):
        """フォント名を安全にデコード"""
        if isinstance(record.string, str):
            return record.string
        try:
            # Windows (platformID=3) は UTF-16-BE
            if record.platformID == 3:
                return record.string.decode('utf-16-be')
            # Mac (platformID=1) は MacRoman
            elif record.platformID == 1:
                return record.string.decode('mac_roman', errors='replace')
            # Unicode (platformID=0) は UTF-16-BE
            else:
                return record.string.decode('utf-16-be', errors='replace')
        except:
            # フォールバック: latin-1で試す
            try:
                return record.string.decode('latin-1', errors='replace')
            except:
                return str(record.string)
    
    for name_id, description in name_ids.items():
        names = [decode_name(record) for record in name_table.names if record.nameID == name_id]
        if names:
            print(f"{description}:")
            for name in set(names):
                print(f"  - {name}")
            print()
    
    # 推奨フォント名を表示
    print("=" * 60)
    print("[INFO] 推奨フォント名（ASSファイルで使用すべき名前）:")
    
    # 優先順位: PostScript名 > Full Font Name > Font Family
    postscript_name = None
    full_font_name = None
    font_family = None
    
    for record in name_table.names:
        decoded = decode_name(record)
        if record.nameID == 6:  # PostScript名
            postscript_name = decoded
        elif record.nameID == 4:  # Full Font Name
            full_font_name = decoded
        elif record.nameID == 1:  # Font Family
            font_family = decoded
    
    recommended = postscript_name or full_font_name or font_family
    if recommended:
        print(f"  [OK] {recommended}")
    else:
        print("  [WARNING] フォント名を取得できませんでした")
    
    font.close()
    
except ImportError:
    print("[ERROR] fontToolsがインストールされていません")
    print("   インストール: pip install fonttools")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

