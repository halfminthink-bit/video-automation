"""
Phase 3: AI画像生成の検証スクリプト

織田信長のscript.jsonを読み込み、実際に画像生成を試す。
"""

import sys
import os
from pathlib import Path
import logging
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# .envファイルを明示的に読み込み
env_path = project_root / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded .env from: {env_path}")
else:
    # ルートディレクトリの.envも試す
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded .env from: {env_path}")
    else:
        print(f"⚠ No .env file found (searched: config/.env and .env)")

from src.phases.phase_03_images import Phase03Images
from src.core.config_manager import ConfigManager


def setup_logging():
    """ロギング設定"""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(asctime)s - %(name)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)


def check_prerequisites():
    """前提条件をチェック"""
    logger = logging.getLogger(__name__)
    
    # 1. script.jsonの存在確認
    script_path = Path("data/working/織田信長/01_script/script.json")
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        logger.error("Phase 1を先に実行してください")
        return False
    
    logger.info(f"✓ Script found: {script_path}")
    
    # 2. APIキーの確認
    stability_key = os.getenv("STABILITY_API_KEY")
    claude_key = os.getenv("CLAUDE_API_KEY")
    
    if not stability_key:
        logger.warning("⚠ STABILITY_API_KEY not found")
        logger.warning("  .envファイルに以下を追加してください:")
        logger.warning("  STABILITY_API_KEY=your_key_here")
        return False
    
    logger.info("✓ STABILITY_API_KEY found")
    
    if not claude_key:
        logger.warning("⚠ CLAUDE_API_KEY not found (optional)")
        logger.warning("  プロンプト最適化なしで動作します")
    else:
        logger.info("✓ CLAUDE_API_KEY found (prompt optimization enabled)")
    
    return True


def test_phase03():
    """Phase 3のテスト実行"""
    logger = setup_logging()
    
    logger.info("=" * 60)
    logger.info("Phase 3: AI画像生成 - 検証テスト")
    logger.info("=" * 60)
    
    # 前提条件チェック
    if not check_prerequisites():
        logger.error("前提条件が満たされていません")
        return False
    
    try:
        # ConfigManager初期化
        config = ConfigManager("config/settings.yaml")
        logger.info("✓ Config loaded")
        
        # Phase 3初期化
        subject = "織田信長"
        working_dir = Path("data/working") / subject
        
        phase = Phase03Images(
            subject=subject,
            working_dir=working_dir,
            config=config,
            logger=logger
        )
        
        logger.info(f"✓ Phase 3 initialized for: {subject}")
        
        # 入力チェック
        if not phase.check_inputs_exist():
            logger.error("入力ファイルが見つかりません")
            return False
        
        logger.info("✓ Input files exist")
        
        # 出力が既に存在するかチェック
        if phase.check_outputs_exist():
            logger.info("⚠ 出力ファイルが既に存在します")
            response = input("再生成しますか？ (y/n): ")
            if response.lower() != 'y':
                logger.info("スキップしました")
                return True
        
        # Phase 3実行
        logger.info("\n画像生成を開始します...")
        logger.info("注意: これには数分かかります")
        logger.info("=" * 60)
        
        result = phase.execute_phase()
        
        # バリデーション
        if not phase.validate_output(result):
            logger.error("出力のバリデーションに失敗しました")
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ Phase 3完了!")
        logger.info("=" * 60)
        logger.info(f"生成画像数: {len(result.images)}")
        logger.info(f"出力先: {phase.phase_dir}")
        logger.info(f"画像: {phase.phase_dir / 'generated'}")
        logger.info(f"結果: {phase.phase_dir / 'classified.json'}")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}", exc_info=True)
        return False


def show_results():
    """生成結果を表示"""
    import json
    
    logger = logging.getLogger(__name__)
    result_path = Path("data/working/織田信長/03_images/classified.json")
    
    if not result_path.exists():
        logger.warning("結果ファイルが見つかりません")
        return
    
    with open(result_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info("\n" + "=" * 60)
    logger.info("生成結果サマリー")
    logger.info("=" * 60)
    
    images = data.get("images", [])
    logger.info(f"総画像数: {len(images)}")
    
    # 分類別
    classifications = {}
    for img in images:
        cls = img["classification"]
        classifications[cls] = classifications.get(cls, 0) + 1
    
    logger.info("\n分類別:")
    for cls, count in classifications.items():
        logger.info(f"  {cls}: {count}枚")
    
    # 最初の3枚を表示
    logger.info("\n最初の3枚:")
    for i, img in enumerate(images[:3]):
        logger.info(f"  [{i+1}] {Path(img['file_path']).name}")
        logger.info(f"      Keywords: {', '.join(img['keywords'])}")
        logger.info(f"      Resolution: {img['resolution']}")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    success = test_phase03()
    
    if success:
        # 結果を表示
        show_results()
        
        print("\n✓ テスト成功!")
        print("\n次のステップ:")
        print("1. 生成された画像を確認: data/working/織田信長/03_images/generated/")
        print("2. 結果JSONを確認: data/working/織田信長/03_images/classified.json")
        print("3. Phase 4に進む: python test_phase04.py")
    else:
        print("\n✗ テスト失敗")
        print("ログを確認してください")
        sys.exit(1)