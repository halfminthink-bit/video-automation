#!/usr/bin/env python3
"""
CLI entrypoint wrapper for video automation system

This file allows running the CLI using:
    python cli.py <command> [options]

Alternatively, you can use:
    python -m src.cli <command> [options]
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# src.cliのmain関数をインポートして実行
from src.cli import main

if __name__ == "__main__":
    sys.exit(main())

