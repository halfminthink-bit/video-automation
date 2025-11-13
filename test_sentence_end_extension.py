#!/usr/bin/env python3
"""
句点での表示延長機能のテストスクリプト

テストケース:
1. 句点で終わる字幕 → 次の字幕開始0.3秒前まで延長
2. 読点で終わる字幕 → 延長しない
3. 既に十分な長さの字幕 → 延長不要
4. 最後の字幕 → 次がないので延長しない
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.models import SubtitleEntry
from src.phases.phase_06_subtitles import Phase06Subtitles
from src.core.config_manager import ConfigManager
from src.utils.logger import setup_logger


def test_sentence_end_extension():
    """句点での表示延長機能をテスト"""

    # 設定とロガーを初期化
    config = ConfigManager()
    logger = setup_logger(
        name="test_sentence_end_extension",
        log_dir=config.get_path("logs_dir"),
        level="DEBUG"
    )

    # Phase 06インスタンスを作成（設定を取得するため）
    phase = Phase06Subtitles(
        subject="test",
        config=config,
        logger=logger
    )

    # テストケース1: 句点で終わる字幕（延長される）
    print("\n" + "="*60)
    print("テストケース1: 句点で終わる字幕")
    print("="*60)

    test_subtitles_1 = [
        SubtitleEntry(
            index=1,
            start_time=0.0,
            end_time=2.5,
            text_line1="信長は尾張の",
            text_line2="大うつけと呼ばれた。"
        ),
        SubtitleEntry(
            index=2,
            start_time=3.0,
            end_time=5.5,
            text_line1="しかし彼は",
            text_line2="天下統一を目指した。"
        ),
    ]

    result_1 = phase._adjust_subtitle_timing_with_sentence_end(test_subtitles_1)

    print(f"\n入力:")
    for sub in test_subtitles_1:
        print(f"  [{sub.start_time:.1f}-{sub.end_time:.1f}] {sub.text_line1} {sub.text_line2}")

    print(f"\n出力:")
    for sub in result_1:
        print(f"  [{sub.start_time:.1f}-{sub.end_time:.1f}] {sub.text_line1} {sub.text_line2}")

    # 検証
    assert result_1[0].start_time == 0.0, "開始時刻は変更されない"
    assert result_1[0].end_time == 2.7, f"終了時刻は2.7秒に延長される（実際: {result_1[0].end_time}）"
    assert result_1[1].start_time == 3.0, "次の字幕の開始時刻は変更されない"
    print("\n✓ テストケース1: 成功")

    # テストケース2: 読点で終わる字幕（延長しない）
    print("\n" + "="*60)
    print("テストケース2: 読点で終わる字幕（延長しない）")
    print("="*60)

    test_subtitles_2 = [
        SubtitleEntry(
            index=1,
            start_time=0.0,
            end_time=2.5,
            text_line1="信長は尾張の",
            text_line2="大うつけと呼ばれ、"
        ),
        SubtitleEntry(
            index=2,
            start_time=3.0,
            end_time=5.5,
            text_line1="各地で",
            text_line2="戦をしていた。"
        ),
    ]

    result_2 = phase._adjust_subtitle_timing_with_sentence_end(test_subtitles_2)

    print(f"\n入力:")
    for sub in test_subtitles_2:
        print(f"  [{sub.start_time:.1f}-{sub.end_time:.1f}] {sub.text_line1} {sub.text_line2}")

    print(f"\n出力:")
    for sub in result_2:
        print(f"  [{sub.start_time:.1f}-{sub.end_time:.1f}] {sub.text_line1} {sub.text_line2}")

    # 検証
    assert result_2[0].end_time == 2.5, f"読点で終わるので延長しない（実際: {result_2[0].end_time}）"
    print("\n✓ テストケース2: 成功")

    # テストケース3: 既に十分な長さの字幕（延長不要）
    print("\n" + "="*60)
    print("テストケース3: 既に十分な長さの字幕（延長不要）")
    print("="*60)

    test_subtitles_3 = [
        SubtitleEntry(
            index=1,
            start_time=0.0,
            end_time=2.8,
            text_line1="信長は尾張の",
            text_line2="大うつけと呼ばれた。"
        ),
        SubtitleEntry(
            index=2,
            start_time=3.0,
            end_time=5.5,
            text_line1="しかし彼は",
            text_line2="天下統一を目指した。"
        ),
    ]

    result_3 = phase._adjust_subtitle_timing_with_sentence_end(test_subtitles_3)

    print(f"\n入力:")
    for sub in test_subtitles_3:
        print(f"  [{sub.start_time:.1f}-{sub.end_time:.1f}] {sub.text_line1} {sub.text_line2}")

    print(f"\n出力:")
    for sub in result_3:
        print(f"  [{sub.start_time:.1f}-{sub.end_time:.1f}] {sub.text_line1} {sub.text_line2}")

    # 検証
    assert result_3[0].end_time == 2.8, f"既に2.7秒以上あるので延長しない（実際: {result_3[0].end_time}）"
    print("\n✓ テストケース3: 成功")

    # テストケース4: 最後の字幕（次がない）
    print("\n" + "="*60)
    print("テストケース4: 最後の字幕（次がないので延長しない）")
    print("="*60)

    test_subtitles_4 = [
        SubtitleEntry(
            index=1,
            start_time=0.0,
            end_time=2.5,
            text_line1="これが彼の",
            text_line2="人生だった。"
        ),
    ]

    result_4 = phase._adjust_subtitle_timing_with_sentence_end(test_subtitles_4)

    print(f"\n入力:")
    for sub in test_subtitles_4:
        print(f"  [{sub.start_time:.1f}-{sub.end_time:.1f}] {sub.text_line1} {sub.text_line2}")

    print(f"\n出力:")
    for sub in result_4:
        print(f"  [{sub.start_time:.1f}-{sub.end_time:.1f}] {sub.text_line1} {sub.text_line2}")

    # 検証
    assert result_4[0].end_time == 2.5, f"次の字幕がないので延長しない（実際: {result_4[0].end_time}）"
    print("\n✓ テストケース4: 成功")

    # 全テスト成功
    print("\n" + "="*60)
    print("全テストケース成功！")
    print("="*60)
    print("\n設定値:")
    print(f"  enabled: {phase.phase_config.get('sentence_end_extension', {}).get('enabled', True)}")
    print(f"  next_start_margin: {phase.phase_config.get('sentence_end_extension', {}).get('next_start_margin', 0.3)}秒")


if __name__ == "__main__":
    test_sentence_end_extension()
