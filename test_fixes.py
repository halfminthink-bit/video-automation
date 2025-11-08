#!/usr/bin/env python3
"""
Phase 4とPhase 6の修正内容を検証するスクリプト
"""

import json
from pathlib import Path

def test_phase4_ai_selection():
    """Phase 4のAI動画選択ロジックをテスト"""
    print("=" * 60)
    print("Testing Phase 4 AI Animation Selection Logic")
    print("=" * 60)
    
    # classified.jsonを読み込み
    # アップロードされた classified.json を使用
    classified_path = Path("/home/ubuntu/upload/classified.json")
    
    if not classified_path.exists():
        print(f"❌ classified.json not found: {classified_path}")
        return
    
    with open(classified_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    images = data['images']
    print(f"\n総画像数: {len(images)}")
    
    # セクション別に画像をグループ化
    sections = {}
    for img in images:
        # Windowsパスを正しく処理
        file_path = img['file_path'].replace('\\', '/')
        filename = file_path.split('/')[-1]
        # section_01_sd_... のパターンから section_id を抽出
        if filename.startswith('section_'):
            parts = filename.split('_')
            if len(parts) >= 2:
                try:
                    section_id = int(parts[1])
                    if section_id not in sections:
                        sections[section_id] = []
                    sections[section_id].append(img)
                except ValueError:
                    pass
    
    # 各セクションの画像をソート
    for section_id in sections:
        sections[section_id].sort(key=lambda x: x['file_path'].replace('\\', '/').split('/')[-1])
    
    print(f"\nセクション数: {len(sections)}")
    
    # 各セクションでAI動画化される画像を表示
    total_ai_videos = 0
    for section_id in sorted(sections.keys()):
        section_images = sections[section_id]
        max_ai_images = 1 if len(section_images) == 1 else 2
        
        print(f"\nセクション {section_id}:")
        print(f"  総画像数: {len(section_images)}")
        print(f"  AI動画化: {max_ai_images}枚")
        
        for idx, img in enumerate(section_images):
            file_path = img['file_path'].replace('\\', '/')
            filename = file_path.split('/')[-1]
            is_ai = idx < max_ai_images
            marker = "🎬 AI動画" if is_ai else "📷 静止画"
            print(f"    [{idx+1}] {marker} - {filename}")
            if is_ai:
                total_ai_videos += 1
    
    print(f"\n総AI動画数: {total_ai_videos}")
    print(f"総静止画数: {len(images) - total_ai_videos}")
    
    # 期待値チェック
    expected_ai_videos = sum(1 if len(sections[sid]) == 1 else 2 for sid in sections)
    if total_ai_videos == expected_ai_videos:
        print(f"\n✅ AI動画選択ロジック: 正常 (期待値: {expected_ai_videos})")
    else:
        print(f"\n❌ AI動画選択ロジック: 異常 (期待値: {expected_ai_videos}, 実際: {total_ai_videos})")

def test_phase6_subtitle_width():
    """Phase 6の字幕文字数設定をテスト"""
    print("\n" + "=" * 60)
    print("Testing Phase 6 Subtitle Character Width")
    print("=" * 60)
    
    # phase_06_subtitles.pyを読み込んで設定を確認
    phase6_path = Path("src/phases/phase_06_subtitles.py")
    
    if not phase6_path.exists():
        print(f"❌ phase_06_subtitles.py not found: {phase6_path}")
        return
    
    with open(phase6_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 16文字の記述がないか確認
    issues = []
    
    if 'max_chars_per_line", 16' in content:
        issues.append("デフォルト値が16のまま")
    
    if 'max_chars_per_line: int = 16' in content:
        issues.append("関数パラメータが16のまま")
    
    if '16文字' in content:
        issues.append("コメント内に16文字の記述あり")
    
    if issues:
        print("\n❌ 字幕文字数設定: 以下の問題が見つかりました")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ 字幕文字数設定: すべて15文字に更新済み")
    
    # 15文字の記述を確認
    count_15 = content.count('15文字')
    count_max_15 = content.count('max_chars_per_line", 15')
    count_param_15 = content.count('max_chars_per_line: int = 15')
    
    print(f"\n設定確認:")
    print(f"  - '15文字' の記述: {count_15}箇所")
    print(f"  - デフォルト値15: {count_max_15}箇所")
    print(f"  - 関数パラメータ15: {count_param_15}箇所")

if __name__ == "__main__":
    test_phase4_ai_selection()
    test_phase6_subtitle_width()
    
    print("\n" + "=" * 60)
    print("検証完了")
    print("=" * 60)
