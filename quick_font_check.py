#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フォント問題診断スクリプト - Cursor用

このスクリプトをCursorに実行させて、現状を把握してください。

実行: python quick_font_check.py
"""

from pathlib import Path
import struct
import sys
import io

# WindowsでのUTF-8出力対応
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def main():
    print("=" * 70)
    print("🔍 フォント問題診断ツール（Cursor用）")
    print("=" * 70)
    print()
    
    # 1. フォントファイルの存在確認
    print("📁 Step 1: フォントファイルの存在確認")
    print("-" * 70)
    
    cinema_dir = Path("assets/fonts/cinema")
    target_font = cinema_dir / "cinecaption226.ttf"
    
    if not cinema_dir.exists():
        print(f"❌ {cinema_dir} が存在しません")
        return
    
    print(f"✅ {cinema_dir} 存在確認")
    print()
    
    # ディレクトリ内のファイル一覧
    print("📋 ディレクトリ内のファイル:")
    for file in cinema_dir.iterdir():
        if file.is_file():
            size_kb = file.stat().st_size / 1024
            print(f"  - {file.name:40} ({size_kb:>10.1f} KB)")
    print()
    
    # 2. ターゲットフォントの詳細チェック
    print("🎯 Step 2: cinecaption226.ttf の詳細")
    print("-" * 70)
    
    if not target_font.exists():
        print(f"❌ {target_font} が見つかりません")
        return
    
    size_bytes = target_font.stat().st_size
    size_kb = size_bytes / 1024
    size_mb = size_bytes / (1024 * 1024)
    
    print(f"ファイルパス: {target_font}")
    print(f"ファイルサイズ: {size_bytes:,} bytes ({size_kb:.1f} KB / {size_mb:.2f} MB)")
    print()
    
    # サイズから推測
    if size_bytes < 10 * 1024:  # 10KB未満
        print("⚠️  警告: ファイルサイズが小さすぎます（破損の可能性）")
    elif size_bytes > 50 * 1024 * 1024:  # 50MB以上
        print("⚠️  警告: ファイルサイズが大きすぎます")
    else:
        print("✅ ファイルサイズは妥当")
    print()
    
    # 3. TTFファイルの簡易検証
    print("🔍 Step 3: TTFファイルヘッダー検証")
    print("-" * 70)
    
    try:
        with open(target_font, 'rb') as f:
            # TTFファイルは 'OTTO' または 0x00010000 で始まる
            header = f.read(4)
            
            if header == b'\x00\x01\x00\x00':
                print("✅ 有効なTrueTypeフォントヘッダー（TTF）")
            elif header == b'OTTO':
                print("✅ 有効なOpenTypeフォントヘッダー（OTF）")
            elif header == b'true':
                print("✅ 有効なTrueTypeフォントヘッダー（Mac用）")
            else:
                print(f"❌ 不正なヘッダー: {header.hex()}")
                print(f"   これはフォントファイルではない可能性があります")
                
                # 最初の100バイトを表示
                f.seek(0)
                first_bytes = f.read(100)
                print(f"\n   最初の100バイト（hex）:")
                print(f"   {first_bytes.hex()}")
                print(f"\n   最初の100バイト（テキスト試行）:")
                try:
                    print(f"   {first_bytes.decode('utf-8', errors='replace')}")
                except:
                    print(f"   （デコードできません）")
    
    except Exception as e:
        print(f"❌ ファイル読み込みエラー: {e}")
    
    print()
    
    # 4. fontToolsを使った詳細解析（オプション）
    print("📊 Step 4: フォント内部名の抽出（fontTools使用）")
    print("-" * 70)
    
    try:
        from fontTools.ttLib import TTFont
        
        font = TTFont(str(target_font))
        name_table = font['name']
        
        print("フォント内部情報:")
        
        # Name ID 1: Font Family name
        # Name ID 2: Font Subfamily name (Regular, Bold, etc.)
        # Name ID 4: Full font name
        # Name ID 6: PostScript name
        
        name_ids = {
            1: "Family Name",
            2: "Subfamily Name",
            4: "Full Name",
            6: "PostScript Name"
        }
        
        found_names = {}
        
        for record in name_table.names:
            if record.nameID in name_ids:
                try:
                    if record.platformID == 3:  # Windows
                        name_str = record.string.decode('utf-16-be')
                    elif record.platformID == 1:  # Mac
                        name_str = record.string.decode('mac-roman')
                    else:
                        name_str = record.string.decode('utf-8', errors='replace')
                    
                    name_type = name_ids[record.nameID]
                    found_names[name_type] = name_str
                except:
                    pass
        
        for name_type, name_value in found_names.items():
            print(f"  {name_type:20}: {name_value}")
        
        print()
        
        # 重要な判定
        family_name = found_names.get("Family Name", "")
        full_name = found_names.get("Full Name", "")
        
        print("🎯 判定:")
        if "cinecap" in family_name.lower() or "cinecap" in full_name.lower():
            print("  ✅ CineCaptionフォントです")
        else:
            print("  ❌ CineCaptionフォントではない可能性があります")
            print(f"     実際のフォント: {family_name or full_name}")
            print()
            print("  💡 このフォントは cinecaption226.ttf という名前ですが、")
            print("     実際には別のフォントがリネームされている可能性があります。")
        
    except ImportError:
        print("⚠️  fontTools がインストールされていません")
        print("   インストール: pip install fonttools")
    except Exception as e:
        print(f"❌ フォント解析エラー: {e}")
    
    print()
    
    # 5. ASS字幕ファイルの確認
    print("📝 Step 5: ASS字幕ファイルの確認")
    print("-" * 70)
    
    ass_file = Path("data/working/織田信長/06_subtitles/subtitles.ass")
    
    if ass_file.exists():
        print(f"✅ {ass_file} 存在確認")
        
        try:
            with open(ass_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Styleセクションを抽出
                import re
                style_matches = re.findall(r'Style:\s*\w+,([^,]+),', content)
                
                if style_matches:
                    print("\nASS内のフォント名:")
                    for i, font_name in enumerate(set(style_matches), 1):
                        print(f"  {i}. {font_name}")
                    
                    # cinecaption226 があるか確認
                    if any('cinecaption226' in name for name in style_matches):
                        print("\n  ✅ 'cinecaption226' が設定されています")
                    else:
                        print("\n  ⚠️  'cinecaption226' が見つかりません")
        except Exception as e:
            print(f"❌ ASS読み込みエラー: {e}")
    else:
        print(f"⚠️  {ass_file} が見つかりません")
    
    print()
    
    # 6. まとめ
    print("=" * 70)
    print("📊 診断結果まとめ")
    print("=" * 70)
    print()
    print("次のステップ:")
    print("  1. 上記の診断結果をCursorに報告")
    print("  2. fontToolsをインストールしていない場合:")
    print("     pip install fonttools")
    print("  3. 再度このスクリプトを実行")
    print("  4. フォントの内部名を確認")
    print("  5. 必要に応じて修正")
    print()
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

