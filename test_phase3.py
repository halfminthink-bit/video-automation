#!/usr/bin/env python3
"""
Phase 3 統合テスト

実際の台本データを使用してPhase 3を実行し、
画像収集が正しく動作するか確認します。
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def create_test_script():
    """テスト用の台本を作成"""
    print("=" * 60)
    print("テスト用台本の作成")
    print("=" * 60)
    
    subject = "織田信長"
    script_dir = project_root / "data" / "working" / subject / "01_script"
    script_dir.mkdir(parents=True, exist_ok=True)
    
    # テスト台本データ
    # キーワードの使い分けをテスト
    script_data = {
        "subject": subject,
        "title": "織田信長の生涯",
        "description": "戦国時代の英雄、織田信長の波乱に満ちた生涯",
        "sections": [
            {
                "section_id": 1,
                "title": "出生と若年期",
                "narration": "織田信長は1534年、尾張国に生まれました。",
                "estimated_duration": 120.0,
                "image_keywords": [
                    "Oda Nobunaga",           # 人物 → Wikimedia
                    "Nagoya Castle",          # 特定の城 → Wikimedia
                    "Japanese warlord portrait"  # 肖像 → Wikimedia
                ],
                "atmosphere": "壮大",
                "requires_ai_video": False,
                "ai_video_prompt": None
            },
            {
                "section_id": 2,
                "title": "桶狭間の戦い",
                "narration": "1560年、桶狭間の戦いで今川義元を討ち取りました。",
                "estimated_duration": 120.0,
                "image_keywords": [
                    "Battle of Okehazama",    # 戦闘 → AI生成が理想
                    "samurai battle",         # 戦闘シーン → AI生成
                    "Japanese warfare"        # 戦争 → Wikimedia/AI
                ],
                "atmosphere": "劇的",
                "requires_ai_video": True,
                "ai_video_prompt": "桶狭間の戦い、今川義元との決戦"
            },
            {
                "section_id": 3,
                "title": "安土城の築城",
                "narration": "信長は琵琶湖のほとりに壮大な安土城を築きました。",
                "estimated_duration": 120.0,
                "image_keywords": [
                    "Azuchi Castle",          # 史跡 → Wikimedia
                    "Lake Biwa",              # 湖 → Pexels/Wikimedia
                    "Japanese castle"         # 城 → Wikimedia
                ],
                "atmosphere": "壮大",
                "requires_ai_video": False,
                "ai_video_prompt": None
            },
            {
                "section_id": 4,
                "title": "天下統一への道",
                "narration": "信長は次々と敵対勢力を倒し、天下統一に近づいていきました。",
                "estimated_duration": 120.0,
                "image_keywords": [
                    "Japanese mountain landscape",  # 風景 → Pexels
                    "sunset over mountains",        # 雰囲気 → Pexels
                    "dramatic sky"                  # 空 → Pexels
                ],
                "atmosphere": "希望",
                "requires_ai_video": False,
                "ai_video_prompt": None
            },
            {
                "section_id": 5,
                "title": "本能寺の変",
                "narration": "1582年、明智光秀の謀反により、信長は本能寺で最期を迎えました。",
                "estimated_duration": 120.0,
                "image_keywords": [
                    "Honnō-ji temple",        # 寺 → Wikimedia
                    "burning temple",         # 炎上 → AI生成が理想
                    "tragic moment"           # 悲劇 → Pexels/AI
                ],
                "atmosphere": "悲劇的",
                "requires_ai_video": True,
                "ai_video_prompt": "本能寺の変、炎上する寺"
            }
        ],
        "total_estimated_duration": 600.0,
        "generated_at": datetime.now().isoformat(),
        "model_version": "claude-sonnet-4-20250514"
    }
    
    # 保存
    script_path = script_dir / "script.json"
    with open(script_path, 'w', encoding='utf-8') as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 台本作成完了: {script_path}")
    print(f"\nセクション数: {len(script_data['sections'])}")
    print("\nキーワード戦略:")
    for section in script_data['sections']:
        print(f"\n{section['section_id']}. {section['title']}")
        for kw in section['image_keywords']:
            print(f"   - {kw}")
    
    return subject, script_path


def run_phase3(subject):
    """Phase 3を実行"""
    print("\n" + "=" * 60)
    print("Phase 3: 画像収集の実行")
    print("=" * 60)
    
    try:
        from src.core.config_manager import ConfigManager
        from src.phases.phase_03_images import Phase03Images
        from src.utils.logger import setup_logger
        
        # 設定マネージャー
        config = ConfigManager()
        
        # ロガー
        log_dir = config.get_path("logs_dir")
        logger = setup_logger(
            name=f"phase_03_{subject}",
            log_dir=log_dir,
            level="INFO"
        )
        
        # Phase 3インスタンス作成
        phase = Phase03Images(
            subject=subject,
            config=config,
            logger=logger
        )
        
        # 実行
        print("\n画像収集を開始します...")
        print("（Wikimediaからの収集には少し時間がかかります）\n")
        
        execution = phase.run(skip_if_exists=False)  # 強制再実行
        
        # 結果表示
        print("\n" + "=" * 60)
        print("Phase 3 実行結果")
        print("=" * 60)
        print(f"Status: {execution.status.value}")
        print(f"Duration: {execution.duration_seconds:.1f}s")
        
        if execution.status.value == "completed":
            # 統計を表示
            classified_path = phase.phase_dir / "classified.json"
            if classified_path.exists():
                with open(classified_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                total = len(data['images'])
                print(f"\n✓ 収集成功: {total}枚の画像")
                
                # ソース別
                sources = {}
                for img in data['images']:
                    src = img['source']
                    sources[src] = sources.get(src, 0) + 1
                
                print("\nソース別:")
                for src, count in sources.items():
                    percentage = (count / total * 100) if total > 0 else 0
                    print(f"  {src}: {count}枚 ({percentage:.1f}%)")
                
                # 分類別
                classifications = {}
                for img in data['images']:
                    cls = img['classification']
                    classifications[cls] = classifications.get(cls, 0) + 1
                
                print("\n分類別:")
                for cls, count in classifications.items():
                    percentage = (count / total * 100) if total > 0 else 0
                    print(f"  {cls}: {count}枚 ({percentage:.1f}%)")
                
                # 画像ファイルの確認
                collected_dir = phase.phase_dir / "collected"
                actual_files = len(list(collected_dir.glob("*.jpg")))
                print(f"\n実際のファイル数: {actual_files}枚")
                
                # 画像パスを表示
                print(f"\n画像の保存場所:")
                print(f"  {collected_dir}")
                
                return True
            else:
                print("✗ classified.jsonが見つかりません")
                return False
        else:
            print(f"\n✗ Phase 3失敗")
            if execution.error_message:
                print(f"エラー: {execution.error_message}")
            return False
            
    except Exception as e:
        print(f"\n✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_image_strategy(subject):
    """画像収集戦略が正しく動作したか検証"""
    print("\n" + "=" * 60)
    print("画像収集戦略の検証")
    print("=" * 60)
    
    classified_path = project_root / "data" / "working" / subject / "03_images" / "classified.json"
    
    if not classified_path.exists():
        print("✗ 検証用データが見つかりません")
        return False
    
    with open(classified_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    images = data['images']
    
    # 期待される戦略
    expectations = {
        "人物・史跡キーワード": {
            "keywords": ["Oda Nobunaga", "Nagoya Castle", "Azuchi Castle", "Honnō-ji"],
            "expected_sources": ["wikimedia_category", "wikimedia_search", "wikimedia_allimages"],
            "count": 0
        },
        "風景・雰囲気キーワード": {
            "keywords": ["mountain landscape", "sunset", "dramatic sky"],
            "expected_sources": ["pexels", "unsplash"],
            "count": 0
        },
        "戦闘キーワード": {
            "keywords": ["Battle", "battle", "samurai battle"],
            "expected_sources": ["ai_generation", "wikimedia_category"],
            "count": 0
        }
    }
    
    # 画像を分析
    for img in images:
        keywords_str = " ".join(img['keywords']).lower()
        source = img['source']
        
        for category, info in expectations.items():
            for kw in info['keywords']:
                if kw.lower() in keywords_str:
                    info['count'] += 1
                    if source in info['expected_sources']:
                        print(f"✓ {category}: '{kw}' → {source} (期待通り)")
                    else:
                        print(f"ℹ {category}: '{kw}' → {source} (予想外だが許容)")
                    break
    
    # サマリー
    print("\n戦略の適用結果:")
    for category, info in expectations.items():
        if info['count'] > 0:
            print(f"  {category}: {info['count']}枚")
    
    # Wikimediaの優先度確認
    wikimedia_count = sum(1 for img in images if 'wikimedia' in img['source'])
    pexels_count = sum(1 for img in images if img['source'] == 'pexels')
    total = len(images)
    
    print(f"\n全体の傾向:")
    print(f"  Wikimedia: {wikimedia_count}枚 ({wikimedia_count/total*100:.1f}%)")
    print(f"  Pexels: {pexels_count}枚 ({pexels_count/total*100:.1f}%)")
    
    if wikimedia_count > 0:
        print("\n✓ Wikimediaが正しく機能しています")
        return True
    else:
        print("\n⚠️ Wikimediaから画像が取得できませんでした")
        return False


def main():
    """メイン処理"""
    print("\n" + "🎬 " * 20)
    print("Phase 3: 画像収集 統合テスト")
    print("🎬 " * 20 + "\n")
    
    # Step 1: テスト台本作成
    subject, script_path = create_test_script()
    
    # Step 2: Phase 3実行
    success = run_phase3(subject)
    
    if not success:
        print("\n❌ Phase 3の実行に失敗しました")
        return 1
    
    # Step 3: 戦略検証
    strategy_ok = verify_image_strategy(subject)
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    
    if success and strategy_ok:
        print("✅ 全てのテストが成功しました！")
        print("\n次のステップ:")
        print("  1. 画像を確認:")
        print(f"     data/working/{subject}/03_images/collected/")
        print("  2. Phase 4（静止画アニメ）の実装へ進む")
        return 0
    else:
        print("⚠️ 一部のテストが失敗しました")
        print("\n確認事項:")
        if not success:
            print("  - Phase 3の実行ログを確認")
        if not strategy_ok:
            print("  - Wikimedia接続を確認")
            print("  - APIキーの設定を確認")
        return 1


if __name__ == "__main__":
    sys.exit(main())