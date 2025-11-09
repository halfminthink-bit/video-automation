"""
上部固定テキストパターン

サムネイル上部に表示する固定フレーズのパターンを管理
"""

import random
from typing import List


class FixedTopTextPatterns:
    """上部固定テキストパターン"""

    PATTERNS = [
        "あなたは知っている？",
        "教科書には載っていない！",
        "世界が隠した真実",
        "99%が知らない事実",
        "歴史の裏側",
    ]

    @classmethod
    def get_random_pattern(cls) -> str:
        """
        ランダムに1つ選択

        Returns:
            ランダムに選ばれた固定フレーズ
        """
        return random.choice(cls.PATTERNS)

    @classmethod
    def get_pattern_by_tone(cls, tone: str = "question") -> str:
        """
        トーンに応じて選択

        Args:
            tone: "question" (疑問形) | "declaration" (断定形) | "mystery" (謎)

        Returns:
            トーンに応じた固定フレーズ
        """
        patterns_map = {
            "question": "あなたは知っている？",
            "declaration": "教科書には載っていない！",
            "mystery": "世界が隠した真実",
            "fact": "99%が知らない事実",
            "history": "歴史の裏側"
        }
        return patterns_map.get(tone, cls.PATTERNS[0])

    @classmethod
    def get_pattern_by_index(cls, index: int) -> str:
        """
        インデックスで選択（循環）

        Args:
            index: パターンインデックス

        Returns:
            インデックスに対応する固定フレーズ
        """
        return cls.PATTERNS[index % len(cls.PATTERNS)]

    @classmethod
    def get_all_patterns(cls) -> List[str]:
        """
        すべてのパターンを取得

        Returns:
            すべての固定フレーズのリスト
        """
        return cls.PATTERNS.copy()
