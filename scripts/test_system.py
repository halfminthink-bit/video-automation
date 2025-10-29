#!/usr/bin/env python3
"""
基盤システムの動作確認スクリプト

このスクリプトを実行して、基盤システムが正しく動作するか確認します。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """必要なモジュールがインポートできるか確認"""
    print("=" * 60)
    print("1. モジュールインポートテスト")
    print("=" * 60)
    
    try:
        from src.core import models
        print("✓ models.py インポート成功")
        
        from src.core import exceptions
        print("✓ exceptions.py インポート成功")
        
        from src.core import config_manager
        print("✓ config_manager.py インポート成功")
        
        from src.core import phase_base
        print("✓ phase_base.py インポート成功")
        
        from src.utils import logger
        print("✓ logger.py インポート成功")
        
        return True
    except Exception as e:
        print(f"✗ インポートエラー: {e}")
        return False


def test_config_manager():
    """設定マネージャーの動作確認"""
    print("\n" + "=" * 60)
    print("2. ConfigManagerテスト")
    print("=" * 60)
    
    try:
        from src.core.config_manager import ConfigManager
        
        config = ConfigManager()
        print(f"✓ ConfigManager初期化成功")
        print(f"  - プロジェクトルート: {config.project_root}")
        
        # 設定値の取得テスト
        project_name = config.get("project.name")
        print(f"✓ 設定値取得成功: project.name = {project_name}")
        
        # パスの取得テスト
        working_dir = config.get_path("working_dir")
        print(f"✓ パス取得成功: working_dir = {working_dir}")
        
        return True
    except Exception as e:
        print(f"✗ ConfigManagerエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_logger():
    """ロガーの動作確認"""
    print("\n" + "=" * 60)
    print("3. Loggerテスト")
    print("=" * 60)
    
    try:
        from src.utils.logger import setup_logger
        
        logger = setup_logger(
            name="test_logger",
            level="INFO",
            to_console=True,
            to_file=False
        )
        print("✓ Logger初期化成功")
        
        logger.info("これはINFOレベルのログです")
        logger.warning("これはWARNINGレベルのログです")
        
        return True
    except Exception as e:
        print(f"✗ Loggerエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_models():
    """データモデルの動作確認"""
    print("\n" + "=" * 60)
    print("4. Pydanticモデルテスト")
    print("=" * 60)
    
    try:
        from src.core.models import (
            ScriptSection,
            VideoScript,
            PhaseExecution,
            PhaseStatus
        )
        from datetime import datetime
        
        # ScriptSectionの作成テスト
        section = ScriptSection(
            section_id=1,
            title="テストセクション",
            narration="これはテストのナレーションです。",
            estimated_duration=120.0,
            image_keywords=["test", "sample"],
            atmosphere="壮大"
        )
        print("✓ ScriptSection作成成功")
        print(f"  - section_id: {section.section_id}")
        print(f"  - title: {section.title}")
        
        # VideoScriptの作成テスト
        script = VideoScript(
            subject="テスト偉人",
            title="テスト動画",
            description="これはテストです",
            sections=[section],
            total_estimated_duration=120.0
        )
        print("✓ VideoScript作成成功")
        print(f"  - subject: {script.subject}")
        print(f"  - sections: {len(script.sections)}個")
        
        # PhaseExecutionの作成テスト
        execution = PhaseExecution(
            phase_number=1,
            phase_name="Test Phase",
            status=PhaseStatus.COMPLETED
        )
        print("✓ PhaseExecution作成成功")
        print(f"  - status: {execution.status}")
        
        return True
    except Exception as e:
        print(f"✗ モデルエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exceptions():
    """例外クラスの動作確認"""
    print("\n" + "=" * 60)
    print("5. Exceptionsテスト")
    print("=" * 60)
    
    try:
        from src.core.exceptions import (
            PhaseExecutionError,
            MissingAPIKeyError,
            ClaudeAPIError
        )
        
        # 例外の作成テスト
        error1 = PhaseExecutionError(1, "テストエラー")
        print(f"✓ PhaseExecutionError: {error1}")
        
        error2 = MissingAPIKeyError("TEST_API_KEY")
        print(f"✓ MissingAPIKeyError: {error2}")
        
        error3 = ClaudeAPIError("テストメッセージ", 400)
        print(f"✓ ClaudeAPIError: {error3}")
        
        return True
    except Exception as e:
        print(f"✗ Exceptionsエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン処理"""
    print("\n" + "🚀 " * 20)
    print("基盤システム動作確認スクリプト")
    print("🚀 " * 20 + "\n")
    
    results = []
    
    # 各テストを実行
    results.append(("モジュールインポート", test_imports()))
    results.append(("ConfigManager", test_config_manager()))
    results.append(("Logger", test_logger()))
    results.append(("Pydanticモデル", test_models()))
    results.append(("Exceptions", test_exceptions()))
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n合計: {passed}/{total} テスト成功")
    
    if passed == total:
        print("\n🎉 全てのテストが成功しました！")
        return 0
    else:
        print("\n⚠️ 一部のテストが失敗しました")
        return 1


if __name__ == "__main__":
    sys.exit(main())
