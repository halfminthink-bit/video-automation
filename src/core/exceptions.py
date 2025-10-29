# custom exceptions
"""
カスタム例外定義

プロジェクト固有のエラーハンドリングを明確化。
"""


class VideoAutomationError(Exception):
    """基底例外クラス"""
    pass


# ========================================
# Phase関連の例外
# ========================================

class PhaseExecutionError(VideoAutomationError):
    """フェーズ実行時の一般的なエラー"""
    def __init__(self, phase_number: int, message: str):
        self.phase_number = phase_number
        self.message = message
        super().__init__(f"Phase {phase_number} error: {message}")


class PhaseInputMissingError(PhaseExecutionError):
    """必要な入力ファイルが存在しない"""
    def __init__(self, phase_number: int, missing_files: list):
        self.missing_files = missing_files
        message = f"Required inputs missing: {', '.join(missing_files)}"
        super().__init__(phase_number, message)


class PhaseValidationError(PhaseExecutionError):
    """出力データのバリデーションエラー"""
    def __init__(self, phase_number: int, validation_message: str):
        super().__init__(phase_number, f"Validation failed: {validation_message}")


# ========================================
# API関連の例外
# ========================================

class APIError(VideoAutomationError):
    """API呼び出しエラーの基底クラス"""
    def __init__(self, service: str, message: str):
        self.service = service
        self.message = message
        super().__init__(f"{service} API error: {message}")


class ClaudeAPIError(APIError):
    """Claude API固有のエラー"""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__("Claude", message)


class ElevenLabsAPIError(APIError):
    """ElevenLabs API固有のエラー"""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__("ElevenLabs", message)


class KlingAPIError(APIError):
    """Kling AI API固有のエラー"""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__("Kling AI", message)


class ImageAPIError(APIError):
    """画像API（Pexels/Wikimedia等）のエラー"""
    def __init__(self, service: str, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__(service, message)


class APIRateLimitError(APIError):
    """APIレート制限エラー"""
    def __init__(self, service: str, retry_after: int = None):
        self.retry_after = retry_after
        message = f"Rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(service, message)


# ========================================
# 設定関連の例外
# ========================================

class ConfigurationError(VideoAutomationError):
    """設定ファイル関連のエラー"""
    pass


class MissingAPIKeyError(ConfigurationError):
    """APIキーが設定されていない"""
    def __init__(self, key_name: str):
        self.key_name = key_name
        super().__init__(f"API key not found: {key_name}. Please set it in config/.env")


class InvalidConfigError(ConfigurationError):
    """設定値が不正"""
    def __init__(self, config_path: str, message: str):
        self.config_path = config_path
        super().__init__(f"Invalid config in {config_path}: {message}")


# ========================================
# ファイル操作関連の例外
# ========================================

class FileOperationError(VideoAutomationError):
    """ファイル操作エラーの基底クラス"""
    pass


class FileNotFoundError(FileOperationError):
    """必要なファイルが見つからない"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        super().__init__(f"File not found: {file_path}")


class FileWriteError(FileOperationError):
    """ファイル書き込みエラー"""
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        super().__init__(f"Failed to write {file_path}: {message}")


class InsufficientDiskSpaceError(FileOperationError):
    """ディスク容量不足"""
    def __init__(self, required_mb: float, available_mb: float):
        self.required_mb = required_mb
        self.available_mb = available_mb
        super().__init__(
            f"Insufficient disk space. Required: {required_mb:.1f}MB, "
            f"Available: {available_mb:.1f}MB"
        )


# ========================================
# 動画処理関連の例外
# ========================================

class VideoProcessingError(VideoAutomationError):
    """動画処理エラーの基底クラス"""
    pass


class MoviePyError(VideoProcessingError):
    """MoviePy処理エラー"""
    def __init__(self, message: str):
        super().__init__(f"MoviePy error: {message}")


class AudioProcessingError(VideoProcessingError):
    """音声処理エラー"""
    def __init__(self, message: str):
        super().__init__(f"Audio processing error: {message}")


class SubtitleGenerationError(VideoProcessingError):
    """字幕生成エラー"""
    def __init__(self, message: str):
        super().__init__(f"Subtitle generation error: {message}")


class RenderTimeoutError(VideoProcessingError):
    """レンダリングタイムアウト"""
    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Rendering timed out after {timeout_seconds} seconds")


# ========================================
# リソース関連の例外
# ========================================

class ResourceError(VideoAutomationError):
    """リソース不足エラー"""
    pass


class InsufficientMemoryError(ResourceError):
    """メモリ不足"""
    def __init__(self, required_mb: float, available_mb: float):
        self.required_mb = required_mb
        self.available_mb = available_mb
        super().__init__(
            f"Insufficient memory. Required: {required_mb:.1f}MB, "
            f"Available: {available_mb:.1f}MB"
        )


class CostLimitExceededError(ResourceError):
    """コスト上限超過"""
    def __init__(self, limit_jpy: float, estimated_jpy: float):
        self.limit_jpy = limit_jpy
        self.estimated_jpy = estimated_jpy
        super().__init__(
            f"Cost limit exceeded. Limit: ¥{limit_jpy:.0f}, "
            f"Estimated: ¥{estimated_jpy:.0f}"
        )


# ========================================
# バリデーション関連の例外
# ========================================

class ValidationError(VideoAutomationError):
    """バリデーションエラー"""
    pass


class InvalidSubjectError(ValidationError):
    """不正な偉人名"""
    def __init__(self, subject: str):
        self.subject = subject
        super().__init__(f"Invalid subject: {subject}")


class InvalidDurationError(ValidationError):
    """不正な時間長"""
    def __init__(self, duration: float, min_duration: float, max_duration: float):
        self.duration = duration
        self.min_duration = min_duration
        self.max_duration = max_duration
        super().__init__(
            f"Invalid duration: {duration}s. "
            f"Must be between {min_duration}s and {max_duration}s"
        )