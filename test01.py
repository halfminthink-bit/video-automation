"""
1分版の台本生成テスト

Phase 1を1分版の設定で実行し、台本を生成する。
"""

import sys
import json
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.phases.phase_01_script import Phase01Script
from src.core.config_manager import ConfigManager
from src.utils.logger import setup_logger


def main():
    """1分版の台本生成テスト"""
    
    # 設定を読み込み
    config = ConfigManager()
    logger = setup_logger(
        name="test_1min_script",
        log_dir=config.get_path("logs_dir"),
        level="INFO"
    )
    
    logger.info("="*60)
    logger.info("1分版 台本生成テスト")
    logger.info("="*60)
    
    # 偉人名
    subject = "織田信長"
    
    # Phase01を作成
    phase = Phase01Script(
        subject=subject,
        config=config,
        logger=logger
    )
    
    # 1分版の設定を読み込み
    import yaml
    config_path = Path("config/phases/script_generation_1min.yaml")
    
    if not config_path.exists():
        logger.error(f"設定ファイルが見つかりません: {config_path}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        phase_config_1min = yaml.safe_load(f)
    
    # phase_configを1分版に置き換え
    phase.phase_config = phase_config_1min
    
    logger.info(f"偉人: {subject}")
    logger.info(f"設定: {config_path}")
    logger.info(f"セクション数: {phase_config_1min['sections']['count_min']}-{phase_config_1min['sections']['count_max']}")
    logger.info(f"各セクション: {phase_config_1min['sections']['target_duration_per_section']}秒")
    logger.info("")
    
    # 台本生成を実行
    try:
        logger.info("台本生成を開始...")
        execution = phase.run(skip_if_exists=False)
        
        logger.info("")
        logger.info("="*60)
        logger.info("実行結果")
        logger.info("="*60)
        logger.info(f"ステータス: {execution.status.value}")
        logger.info(f"実行時間: {execution.duration_seconds:.2f}秒")
        
        if execution.status.value == "completed":
            logger.info("")
            logger.info("出力ファイル:")
            for path in execution.output_paths:
                logger.info(f"  ✓ {path}")
            
            # 台本を読み込んで内容を表示
            script = phase.load_script()
            if script:
                logger.info("")
                logger.info("="*60)
                logger.info("生成された台本")
                logger.info("="*60)
                logger.info(f"タイトル: {script.title}")
                logger.info(f"セクション数: {len(script.sections)}")
                logger.info(f"総時間: {script.total_estimated_duration:.1f}秒")
                logger.info("")
                
                for i, section in enumerate(script.sections, 1):
                    logger.info(f"セクション {i}: {section.title}")
                    logger.info(f"  時間: {section.estimated_duration}秒")
                    logger.info(f"  BGM: {section.bgm_suggestion.value}")
                    logger.info(f"  雰囲気: {section.atmosphere}")
                    logger.info(f"  ナレーション: {section.narration[:100]}...")
                    logger.info("")
                
                # JSONを整形して表示
                logger.info("="*60)
                logger.info("JSON出力")
                logger.info("="*60)
                script_dict = script.model_dump(mode='json')
                print(json.dumps(script_dict, indent=2, ensure_ascii=False))
        else:
            logger.error(f"エラー: {execution.error_message}")
    
    except Exception as e:
        logger.error(f"実行エラー: {e}", exc_info=True)


if __name__ == "__main__":
    main()