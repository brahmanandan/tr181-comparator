"""TR181 Node Comparator - A tool for comparing TR181 data model implementations."""

from .models import (
    TR181Node, ValueRange, TR181Event, TR181Function,
    AccessLevel, Severity
)
from .extractors import (
    NodeExtractor, SourceInfo, ValidationResult
)
from .errors import (
    TR181Error, ConnectionError, ValidationError, AuthenticationError,
    TimeoutError, ProtocolError, ConfigurationError, ErrorContext,
    ErrorCategory, ErrorSeverity, RetryManager, RetryConfig,
    GracefulDegradationManager, PartialResult, ErrorReporter,
    get_error_reporter, report_error
)
from .hooks import (
    DeviceConnectionHook, RESTAPIHook, CWMPHook, DeviceHookFactory,
    HookType, DeviceConfig
)
from .main import TR181ComparatorApp
from .cli import TR181ComparatorCLI, CLIProgressReporter
from .logging import (
    LogLevel, LogCategory, LogEntry, PerformanceMetric, LoggingConfig,
    TR181Logger, ComponentLogger, performance_monitor, get_logger,
    initialize_logging, get_performance_summary
)

__version__ = "0.1.0"

__all__ = [
    # Models
    'TR181Node', 'ValueRange', 'TR181Event', 'TR181Function',
    'AccessLevel', 'Severity',
    # Extractors
    'NodeExtractor', 'SourceInfo', 'ValidationResult',
    # Error Handling
    'TR181Error', 'ConnectionError', 'ValidationError', 'AuthenticationError',
    'TimeoutError', 'ProtocolError', 'ConfigurationError', 'ErrorContext',
    'ErrorCategory', 'ErrorSeverity', 'RetryManager', 'RetryConfig',
    'GracefulDegradationManager', 'PartialResult', 'ErrorReporter',
    'get_error_reporter', 'report_error',
    # Hooks
    'DeviceConnectionHook', 'RESTAPIHook', 'CWMPHook', 'DeviceHookFactory',
    'HookType', 'DeviceConfig',
    # Main Application
    'TR181ComparatorApp',
    # CLI
    'TR181ComparatorCLI', 'CLIProgressReporter',
    # Logging and Monitoring
    'LogLevel', 'LogCategory', 'LogEntry', 'PerformanceMetric', 'LoggingConfig',
    'TR181Logger', 'ComponentLogger', 'performance_monitor', 'get_logger',
    'initialize_logging', 'get_performance_summary'
]