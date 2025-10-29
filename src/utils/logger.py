# logging
"""
ロギングシステム

リッチなコンソール出力とファイルログを提供。
進捗状況、エラー、デバッグ情報を記録。
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from rich.logging import RichHandler
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class CustomFormatter(logging.Formatter):
    """カスタムフォーマッター（Richが使えない場合のフォールバック）"""
    
    # カラーコード
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        if sys.stdout.isatty():  # ターミナル出力の場合のみカラー化
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


def setup_logger(
    name: str,
    log_dir: Optional[Path] = None,
    level: str = "INFO",
    to_console: bool = True,
    to_file: bool = True,
    rich_traceback: bool = True
) -> logging.Logger:
    """
    ロガーをセットアップ
    
    Args:
        name: ロガー名（通常は __name__ を使用）
        log_dir: ログファイルの保存先ディレクトリ
        level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        to_console: コンソールに出力するか
        to_file: ファイルに出力するか
        rich_traceback: リッチなトレースバック表示（Richが利用可能な場合）
        
    Returns:
        設定済みのロガー
        
    使用例:
        logger = setup_logger(__name__)
        logger.info("処理を開始します")
        logger.error("エラーが発生しました", exc_info=True)
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers = []  # 既存ハンドラをクリア
    
    # フォーマット定義
    file_format = logging.Formatter(
        "[{levelname}] {asctime} - {name} - {message}",
        style='{',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラ
    if to_console:
        if RICH_AVAILABLE:
            # Rich使用
            console_handler = RichHandler(
                console=Console(stderr=True),
                rich_tracebacks=rich_traceback,
                tracebacks_show_locals=True,
                markup=True
            )
            console_handler.setLevel(logging.INFO)
        else:
            # 標準ハンドラ（カラー付き）
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.INFO)
            console_formatter = CustomFormatter(
                "[{levelname}] {asctime} - {message}",
                style='{',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
        
        logger.addHandler(console_handler)
    
    # ファイルハンドラ
    if to_file and log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{timestamp}_{name.replace('.', '_')}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # ファイルは全レベルを記録
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


def get_phase_logger(
    phase_number: int,
    phase_name: str,
    subject: str,
    log_dir: Optional[Path] = None
) -> logging.Logger:
    """
    フェーズ専用のロガーを取得
    
    Args:
        phase_number: フェーズ番号
        phase_name: フェーズ名
        subject: 偉人名
        log_dir: ログディレクトリ
        
    Returns:
        フェーズ専用ロガー
    """
    logger_name = f"phase_{phase_number:02d}_{phase_name}_{subject}"
    return setup_logger(
        name=logger_name,
        log_dir=log_dir,
        level="DEBUG"
    )


class LoggerContext:
    """
    ログコンテキストマネージャー
    
    withステートメント内でログレベルを一時的に変更。
    
    使用例:
        with LoggerContext(logger, "DEBUG"):
            # この中はDEBUGレベルで出力
            logger.debug("詳細情報")
    """
    
    def __init__(self, logger: logging.Logger, level: str):
        self.logger = logger
        self.new_level = getattr(logging, level.upper())
        self.old_level = None
    
    def __enter__(self):
        self.old_level = self.logger.level
        self.logger.setLevel(self.new_level)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.old_level)


def log_phase_start(logger: logging.Logger, phase_number: int, phase_name: str):
    """フェーズ開始をログ出力"""
    separator = "=" * 60
    if RICH_AVAILABLE:
        logger.info(f"\n[bold cyan]{separator}[/bold cyan]")
        logger.info(f"[bold green]Phase {phase_number}: {phase_name}[/bold green]")
        logger.info(f"[bold cyan]{separator}[/bold cyan]\n")
    else:
        logger.info(f"\n{separator}")
        logger.info(f"Phase {phase_number}: {phase_name}")
        logger.info(f"{separator}\n")


def log_phase_complete(
    logger: logging.Logger,
    phase_number: int,
    duration_seconds: float
):
    """フェーズ完了をログ出力"""
    if RICH_AVAILABLE:
        logger.info(
            f"[bold green]✓[/bold green] "
            f"Phase {phase_number} completed in {duration_seconds:.1f}s"
        )
    else:
        logger.info(f"✓ Phase {phase_number} completed in {duration_seconds:.1f}s")


def log_phase_error(
    logger: logging.Logger,
    phase_number: int,
    error: Exception
):
    """フェーズエラーをログ出力"""
    if RICH_AVAILABLE:
        logger.error(
            f"[bold red]✗[/bold red] "
            f"Phase {phase_number} failed: {error}",
            exc_info=True
        )
    else:
        logger.error(f"✗ Phase {phase_number} failed: {error}", exc_info=True)


def log_progress(
    logger: logging.Logger,
    message: str,
    current: int,
    total: int
):
    """進捗状況をログ出力"""
    percentage = (current / total) * 100 if total > 0 else 0
    
    if RICH_AVAILABLE:
        logger.info(
            f"[cyan]Progress:[/cyan] {message} "
            f"[yellow]{current}/{total}[/yellow] "
            f"([green]{percentage:.1f}%[/green])"
        )
    else:
        logger.info(f"Progress: {message} {current}/{total} ({percentage:.1f}%)")


def log_api_call(
    logger: logging.Logger,
    service: str,
    endpoint: str,
    status: str = "success"
):
    """API呼び出しをログ出力"""
    if status == "success":
        color = "green" if RICH_AVAILABLE else ""
        symbol = "✓"
    else:
        color = "red" if RICH_AVAILABLE else ""
        symbol = "✗"
    
    if RICH_AVAILABLE:
        logger.debug(
            f"[{color}]{symbol}[/{color}] "
            f"API: {service} - {endpoint}"
        )
    else:
        logger.debug(f"{symbol} API: {service} - {endpoint}")


def log_cost(
    logger: logging.Logger,
    service: str,
    cost_jpy: float,
    cumulative_jpy: float
):
    """コスト情報をログ出力"""
    if RICH_AVAILABLE:
        logger.info(
            f"[yellow]Cost:[/yellow] {service} "
            f"¥{cost_jpy:.0f} "
            f"(Total: [bold]¥{cumulative_jpy:.0f}[/bold])"
        )
    else:
        logger.info(f"Cost: {service} ¥{cost_jpy:.0f} (Total: ¥{cumulative_jpy:.0f})")


# ========================================
# グローバルロガー
# ========================================

_global_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """
    グローバルロガーを取得
    
    Returns:
        グローバルロガー
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = setup_logger(
            name="video_automation",
            level="INFO"
        )
    
    return _global_logger