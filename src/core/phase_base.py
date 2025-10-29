# base class
"""
Phase基底クラス

全てのフェーズはこのクラスを継承する。
共通処理（入力チェック、スキップ判定、エラーハンドリング等）を提供。
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List
from pathlib import Path
import logging
from datetime import datetime
import json

from .models import PhaseStatus, PhaseExecution
from .config_manager import ConfigManager
from .exceptions import PhaseInputMissingError, PhaseValidationError
from ..utils.logger import (
    log_phase_start,
    log_phase_complete,
    log_phase_error
)


class PhaseBase(ABC):
    """
    フェーズ基底クラス
    
    全てのフェーズはこのクラスを継承し、
    以下の抽象メソッドを実装する必要がある:
    - get_phase_number()
    - get_phase_name()
    - check_inputs_exist()
    - check_outputs_exist()
    - execute_phase()
    - validate_output()
    """
    
    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            subject: 偉人名
            config: 設定マネージャー
            logger: ロガー（Noneの場合は自動作成）
        """
        self.subject = subject
        self.config = config
        
        # ロガー設定
        if logger is None:
            from ..utils.logger import setup_logger
            log_dir = config.get_path("logs_dir")
            self.logger = setup_logger(
                name=f"phase_{self.get_phase_number()}_{subject}",
                log_dir=log_dir
            )
        else:
            self.logger = logger
        
        # ディレクトリ設定
        self.working_dir = config.get_working_dir(subject)
        self.phase_dir = self.get_phase_directory()
        self.phase_dir.mkdir(parents=True, exist_ok=True)
        
        # 実行情報
        self.execution = PhaseExecution(
            phase_number=self.get_phase_number(),
            phase_name=self.get_phase_name(),
            status=PhaseStatus.PENDING
        )
        
        # フェーズ固有の設定を読み込み
        self.phase_config = config.get_phase_config(self.get_phase_number())
    
    # ========================================
    # 抽象メソッド（サブクラスで実装必須）
    # ========================================
    
    @abstractmethod
    def get_phase_number(self) -> int:
        """
        フェーズ番号を返す（1-8）
        
        Returns:
            フェーズ番号
        """
        pass
    
    @abstractmethod
    def get_phase_name(self) -> str:
        """
        フェーズ名を返す
        
        Returns:
            フェーズ名（例: "Script Generation"）
        """
        pass
    
    @abstractmethod
    def check_inputs_exist(self) -> bool:
        """
        前フェーズの出力（このフェーズの入力）が存在するかチェック
        
        Returns:
            全ての必要な入力が存在する場合 True
        """
        pass
    
    @abstractmethod
    def check_outputs_exist(self) -> bool:
        """
        このフェーズの出力が既に存在するかチェック
        
        Returns:
            出力が存在し、スキップ可能な場合 True
        """
        pass
    
    @abstractmethod
    def execute_phase(self) -> Any:
        """
        フェーズの実際の処理を実行
        
        Returns:
            フェーズの出力データ（Pydanticモデル）
        
        Raises:
            PhaseExecutionError: 実行エラー
        """
        pass
    
    @abstractmethod
    def validate_output(self, output: Any) -> bool:
        """
        出力データが正しいかバリデーション
        
        Args:
            output: execute_phase()の戻り値
            
        Returns:
            バリデーション成功なら True
            
        Raises:
            PhaseValidationError: バリデーションエラー
        """
        pass
    
    # ========================================
    # 共通メソッド
    # ========================================
    
    def get_phase_directory(self) -> Path:
        """
        フェーズのワーキングディレクトリを取得
        
        Returns:
            フェーズディレクトリのPath
        """
        return self.config.get_phase_dir(self.subject, self.get_phase_number())
    
    def get_input_paths(self) -> List[Path]:
        """
        このフェーズの入力ファイルパスのリストを取得
        
        サブクラスでオーバーライド可能。
        デフォルトでは空リストを返す。
        
        Returns:
            入力ファイルパスのリスト
        """
        return []
    
    def get_output_paths(self) -> List[Path]:
        """
        このフェーズの出力ファイルパスのリストを取得
        
        サブクラスでオーバーライド可能。
        デフォルトでは空リストを返す。
        
        Returns:
            出力ファイルパスのリスト
        """
        return []
    
    def save_metadata(self, data: dict, filename: str = "metadata.json"):
        """
        メタデータをJSONで保存
        
        Args:
            data: 保存するデータ（辞書）
            filename: ファイル名（デフォルト: metadata.json）
        """
        output_path = self.phase_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.debug(f"Metadata saved: {output_path}")
    
    def load_metadata(self, filename: str = "metadata.json") -> dict:
        """
        メタデータをJSONから読み込み
        
        Args:
            filename: ファイル名
            
        Returns:
            読み込んだデータ（辞書）
        """
        input_path = self.phase_dir / filename
        
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
    
    def run(self, skip_if_exists: bool = True) -> PhaseExecution:
        """
        フェーズを実行（共通処理）
        
        Args:
            skip_if_exists: 出力が既に存在する場合スキップするか
            
        Returns:
            PhaseExecution: 実行結果
        """
        log_phase_start(
            self.logger,
            self.get_phase_number(),
            self.get_phase_name()
        )
        
        # 入力チェック
        if not self.check_inputs_exist():
            missing_files = [
                str(p) for p in self.get_input_paths()
                if not p.exists()
            ]
            
            self.execution.status = PhaseStatus.FAILED
            self.execution.error_message = f"Required inputs missing: {missing_files}"
            
            log_phase_error(
                self.logger,
                self.get_phase_number(),
                PhaseInputMissingError(self.get_phase_number(), missing_files)
            )
            
            return self.execution
        
        # 既存出力チェック
        if skip_if_exists and self.check_outputs_exist():
            self.execution.status = PhaseStatus.SKIPPED
            self.logger.info(
                f"Phase {self.get_phase_number()} skipped: outputs already exist"
            )
            return self.execution
        
        # 実行
        try:
            self.execution.status = PhaseStatus.RUNNING
            self.execution.started_at = datetime.now()
            self.logger.info(f"Phase {self.get_phase_number()} started")
            
            # 実際の処理
            output = self.execute_phase()
            
            # バリデーション
            if not self.validate_output(output):
                raise PhaseValidationError(
                    self.get_phase_number(),
                    "Output validation failed"
                )
            
            # 成功
            self.execution.status = PhaseStatus.COMPLETED
            self.execution.completed_at = datetime.now()
            self.execution.duration_seconds = (
                self.execution.completed_at - self.execution.started_at
            ).total_seconds()
            
            # 出力パスを記録
            self.execution.output_paths = [
                str(p) for p in self.get_output_paths()
            ]
            
            log_phase_complete(
                self.logger,
                self.get_phase_number(),
                self.execution.duration_seconds
            )
            
            return self.execution
            
        except Exception as e:
            self.execution.status = PhaseStatus.FAILED
            self.execution.completed_at = datetime.now()
            self.execution.error_message = str(e)
            
            log_phase_error(
                self.logger,
                self.get_phase_number(),
                e
            )
            
            return self.execution
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"phase={self.get_phase_number()}, "
            f"subject={self.subject}, "
            f"status={self.execution.status}"
            ")"
        )