"""Comprehensive error handling and recovery system for TR181 Node Comparator.

This module provides custom exception classes, retry logic with exponential backoff,
and graceful degradation mechanisms for handling various failure scenarios.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from datetime import datetime, timedelta


class ErrorSeverity(Enum):
    """Severity levels for errors and recovery actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors for better classification and handling."""
    CONNECTION = "connection"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    TIMEOUT = "timeout"
    PROTOCOL = "protocol"
    DATA_FORMAT = "data_format"
    PERMISSION = "permission"
    RESOURCE = "resource"
    CONFIGURATION = "configuration"


@dataclass
class ErrorContext:
    """Context information for error reporting and recovery."""
    operation: str
    component: str
    timestamp: datetime = field(default_factory=datetime.now)
    attempt_number: int = 1
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary for logging."""
        return {
            'operation': self.operation,
            'component': self.component,
            'timestamp': self.timestamp.isoformat(),
            'attempt_number': self.attempt_number,
            'max_attempts': self.max_attempts,
            'metadata': self.metadata
        }


@dataclass
class RecoveryAction:
    """Describes a recovery action that can be taken for an error."""
    action_type: str
    description: str
    automatic: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)


class TR181Error(Exception):
    """Base exception class for all TR181 Node Comparator errors.
    
    Provides enhanced error reporting with context, severity, recovery suggestions,
    and structured error information for better debugging and user experience.
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        recovery_actions: Optional[List[RecoveryAction]] = None,
        error_code: Optional[str] = None
    ):
        """Initialize TR181Error with comprehensive error information.
        
        Args:
            message: Human-readable error message
            category: Error category for classification
            severity: Error severity level
            context: Context information about the error
            cause: Original exception that caused this error
            recovery_actions: List of suggested recovery actions
            error_code: Unique error code for programmatic handling
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext(operation="unknown", component="unknown")
        self.cause = cause
        self.recovery_actions = recovery_actions or []
        self.timestamp = datetime.now()
        self.error_code = error_code or self._generate_error_code()
    
    def _generate_error_code(self) -> str:
        """Generate a unique error code based on category and timestamp."""
        timestamp_str = self.timestamp.strftime("%Y%m%d%H%M%S")
        return f"TR181_{self.category.value.upper()}_{timestamp_str}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging and serialization."""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'timestamp': self.timestamp.isoformat(),
            'context': self.context.to_dict() if self.context else None,
            'cause': str(self.cause) if self.cause else None,
            'recovery_actions': [
                {
                    'action_type': action.action_type,
                    'description': action.description,
                    'automatic': action.automatic,
                    'parameters': action.parameters
                }
                for action in self.recovery_actions
            ]
        }
    
    def get_user_message(self) -> str:
        """Get a user-friendly error message with recovery suggestions."""
        msg = f"Error: {self.message}"
        
        if self.recovery_actions:
            msg += "\n\nSuggested actions:"
            for i, action in enumerate(self.recovery_actions, 1):
                msg += f"\n{i}. {action.description}"
        
        return msg
    
    def __str__(self) -> str:
        """String representation of the error."""
        return f"[{self.error_code}] {self.message}"


class ConnectionError(TR181Error):
    """Exception raised when unable to connect to a data source.
    
    This error indicates network connectivity issues, unreachable endpoints,
    or connection establishment failures.
    """
    
    def __init__(
        self,
        message: str,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        """Initialize ConnectionError with connection-specific information.
        
        Args:
            message: Error message
            endpoint: The endpoint that failed to connect
            timeout: Connection timeout value if applicable
            context: Error context
            cause: Original exception
        """
        recovery_actions = [
            RecoveryAction(
                action_type="retry",
                description="Retry the connection with exponential backoff",
                automatic=True
            ),
            RecoveryAction(
                action_type="check_network",
                description="Verify network connectivity and endpoint availability"
            ),
            RecoveryAction(
                action_type="check_config",
                description="Verify connection configuration (URL, port, credentials)"
            )
        ]
        
        if timeout:
            recovery_actions.append(
                RecoveryAction(
                    action_type="increase_timeout",
                    description=f"Consider increasing timeout (current: {timeout}s)",
                    parameters={"current_timeout": timeout}
                )
            )
        
        super().__init__(
            message=message,
            category=ErrorCategory.CONNECTION,
            severity=ErrorSeverity.HIGH,
            context=context,
            cause=cause,
            recovery_actions=recovery_actions
        )
        
        self.endpoint = endpoint
        self.timeout = timeout


class ValidationError(TR181Error):
    """Exception raised when extracted data fails validation.
    
    This error indicates data integrity issues, format problems,
    or constraint violations in TR181 node data.
    """
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[str]] = None,
        node_path: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        """Initialize ValidationError with validation-specific information.
        
        Args:
            message: Error message
            validation_errors: List of specific validation error messages
            node_path: TR181 node path that failed validation
            context: Error context
            cause: Original exception
        """
        recovery_actions = [
            RecoveryAction(
                action_type="check_data_format",
                description="Verify data format matches TR181 specifications"
            ),
            RecoveryAction(
                action_type="partial_recovery",
                description="Continue with valid nodes, skip invalid ones",
                automatic=True
            )
        ]
        
        if node_path:
            recovery_actions.append(
                RecoveryAction(
                    action_type="inspect_node",
                    description=f"Inspect node data for path: {node_path}",
                    parameters={"node_path": node_path}
                )
            )
        
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            cause=cause,
            recovery_actions=recovery_actions
        )
        
        self.validation_errors = validation_errors or []
        self.node_path = node_path


class AuthenticationError(TR181Error):
    """Exception raised when authentication fails."""
    
    def __init__(
        self,
        message: str,
        auth_method: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        """Initialize AuthenticationError.
        
        Args:
            message: Error message
            auth_method: Authentication method that failed
            context: Error context
            cause: Original exception
        """
        recovery_actions = [
            RecoveryAction(
                action_type="check_credentials",
                description="Verify username, password, or authentication tokens"
            ),
            RecoveryAction(
                action_type="check_permissions",
                description="Ensure account has necessary permissions"
            ),
            RecoveryAction(
                action_type="refresh_token",
                description="Refresh authentication token if applicable",
                automatic=True
            )
        ]
        
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            cause=cause,
            recovery_actions=recovery_actions
        )
        
        self.auth_method = auth_method


class TimeoutError(TR181Error):
    """Exception raised when operations timeout."""
    
    def __init__(
        self,
        message: str,
        timeout_duration: Optional[float] = None,
        operation: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        """Initialize TimeoutError.
        
        Args:
            message: Error message
            timeout_duration: Timeout duration in seconds
            operation: Operation that timed out
            context: Error context
            cause: Original exception
        """
        recovery_actions = [
            RecoveryAction(
                action_type="increase_timeout",
                description=f"Increase timeout duration (current: {timeout_duration}s)",
                parameters={"current_timeout": timeout_duration}
            ),
            RecoveryAction(
                action_type="retry_smaller_batch",
                description="Retry with smaller data batch size",
                automatic=True
            )
        ]
        
        super().__init__(
            message=message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            cause=cause,
            recovery_actions=recovery_actions
        )
        
        self.timeout_duration = timeout_duration
        self.operation = operation


class ProtocolError(TR181Error):
    """Exception raised when protocol-specific errors occur."""
    
    def __init__(
        self,
        message: str,
        protocol: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        """Initialize ProtocolError.
        
        Args:
            message: Error message
            protocol: Protocol name (CWMP, REST, etc.)
            error_details: Protocol-specific error details
            context: Error context
            cause: Original exception
        """
        recovery_actions = [
            RecoveryAction(
                action_type="check_protocol_version",
                description=f"Verify {protocol} protocol version compatibility"
            ),
            RecoveryAction(
                action_type="fallback_protocol",
                description="Try alternative communication protocol",
                automatic=True
            )
        ]
        
        super().__init__(
            message=message,
            category=ErrorCategory.PROTOCOL,
            severity=ErrorSeverity.HIGH,
            context=context,
            cause=cause,
            recovery_actions=recovery_actions
        )
        
        self.protocol = protocol
        self.error_details = error_details or {}


class ConfigurationError(TR181Error):
    """Exception raised when configuration is invalid or missing."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        expected_type: Optional[Type] = None,
        actual_value: Optional[Any] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        """Initialize ConfigurationError.
        
        Args:
            message: Error message
            config_key: Configuration key that is invalid
            expected_type: Expected type for the configuration value
            actual_value: Actual value that was provided
            context: Error context
            cause: Original exception
        """
        recovery_actions = [
            RecoveryAction(
                action_type="check_config_file",
                description="Verify configuration file exists and is readable"
            ),
            RecoveryAction(
                action_type="validate_config",
                description="Validate all configuration values"
            )
        ]
        
        if config_key:
            recovery_actions.append(
                RecoveryAction(
                    action_type="fix_config_key",
                    description=f"Fix configuration key: {config_key}",
                    parameters={
                        "config_key": config_key,
                        "expected_type": str(expected_type) if expected_type else None,
                        "actual_value": actual_value
                    }
                )
            )
        
        super().__init__(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            cause=cause,
            recovery_actions=recovery_actions
        )
        
        self.config_key = config_key
        self.expected_type = expected_type
        self.actual_value = actual_value


@dataclass
class RetryConfig:
    """Configuration for retry logic with exponential backoff."""
    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    backoff_factor: float = 2.0  # Exponential backoff multiplier
    jitter: bool = True  # Add random jitter to prevent thundering herd
    retryable_exceptions: tuple = (ConnectionError, TimeoutError, ProtocolError)


class RetryManager:
    """Manages retry logic with exponential backoff for operations."""
    
    def __init__(self, config: Optional[RetryConfig] = None, logger: Optional[logging.Logger] = None):
        """Initialize RetryManager.
        
        Args:
            config: Retry configuration
            logger: Logger instance for retry events
        """
        self.config = config or RetryConfig()
        self.logger = logger or logging.getLogger(__name__)
    
    async def execute_with_retry(
        self,
        operation: Callable,
        operation_name: str,
        context: Optional[ErrorContext] = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute an operation with retry logic and exponential backoff.
        
        Args:
            operation: Async function to execute
            operation_name: Name of the operation for logging
            context: Error context for tracking
            *args: Arguments to pass to the operation
            **kwargs: Keyword arguments to pass to the operation
            
        Returns:
            Result of the operation
            
        Raises:
            TR181Error: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                if context:
                    context.attempt_number = attempt
                    context.max_attempts = self.config.max_attempts
                
                self.logger.info(
                    f"Executing {operation_name} (attempt {attempt}/{self.config.max_attempts})"
                )
                
                result = await operation(*args, **kwargs)
                
                if attempt > 1:
                    self.logger.info(f"{operation_name} succeeded after {attempt} attempts")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this exception is retryable
                if not isinstance(e, self.config.retryable_exceptions):
                    self.logger.error(f"{operation_name} failed with non-retryable error: {e}")
                    raise
                
                # Don't retry on the last attempt
                if attempt == self.config.max_attempts:
                    break
                
                # Calculate delay with exponential backoff
                delay = self._calculate_delay(attempt)
                
                self.logger.warning(
                    f"{operation_name} failed (attempt {attempt}/{self.config.max_attempts}): {e}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                
                await asyncio.sleep(delay)
        
        # All attempts failed
        error_msg = f"{operation_name} failed after {self.config.max_attempts} attempts"
        if context:
            context.attempt_number = self.config.max_attempts
        
        # Wrap the last exception in a TR181Error if it isn't already
        if isinstance(last_exception, TR181Error):
            raise last_exception
        else:
            raise ConnectionError(
                message=error_msg,
                context=context,
                cause=last_exception
            )
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number with exponential backoff.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff delay
        delay = self.config.base_delay * (self.config.backoff_factor ** (attempt - 1))
        
        # Add jitter to prevent thundering herd (before capping)
        if self.config.jitter:
            import random
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        # Cap at maximum delay and ensure non-negative
        delay = max(0, min(delay, self.config.max_delay))
        
        return delay


@dataclass
class PartialResult:
    """Represents a partial result when graceful degradation occurs."""
    successful_items: List[Any]
    failed_items: List[tuple[Any, Exception]]
    total_items: int
    success_rate: float = field(init=False)
    
    def __post_init__(self):
        """Calculate success rate after initialization."""
        if self.total_items > 0:
            self.success_rate = len(self.successful_items) / self.total_items
        else:
            self.success_rate = 0.0
    
    def is_acceptable(self, min_success_rate: float = 0.5) -> bool:
        """Check if the partial result meets minimum success criteria.
        
        Args:
            min_success_rate: Minimum acceptable success rate (0.0 to 1.0)
            
        Returns:
            True if success rate meets minimum threshold
        """
        return self.success_rate >= min_success_rate


class GracefulDegradationManager:
    """Manages graceful degradation for partial data scenarios."""
    
    def __init__(
        self,
        min_success_rate: float = 0.5,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize GracefulDegradationManager.
        
        Args:
            min_success_rate: Minimum acceptable success rate for operations
            logger: Logger instance
        """
        self.min_success_rate = min_success_rate
        self.logger = logger or logging.getLogger(__name__)
    
    async def execute_with_partial_success(
        self,
        items: List[Any],
        operation: Callable,
        operation_name: str,
        context: Optional[ErrorContext] = None
    ) -> PartialResult:
        """Execute an operation on multiple items with graceful degradation.
        
        Args:
            items: List of items to process
            operation: Async function to execute on each item
            operation_name: Name of the operation for logging
            context: Error context
            
        Returns:
            PartialResult with successful and failed items
        """
        successful_items = []
        failed_items = []
        
        self.logger.info(f"Starting {operation_name} for {len(items)} items")
        
        for i, item in enumerate(items):
            try:
                # Handle both sync and async operations
                if asyncio.iscoroutinefunction(operation):
                    result = await operation(item)
                else:
                    result = operation(item)
                successful_items.append(result)
                
            except Exception as e:
                self.logger.warning(f"{operation_name} failed for item {i}: {e}")
                failed_items.append((item, e))
        
        partial_result = PartialResult(
            successful_items=successful_items,
            failed_items=failed_items,
            total_items=len(items)
        )
        
        self.logger.info(
            f"{operation_name} completed: {len(successful_items)}/{len(items)} successful "
            f"({partial_result.success_rate:.1%} success rate)"
        )
        
        # Check if result is acceptable
        if not partial_result.is_acceptable(self.min_success_rate):
            error_msg = (
                f"{operation_name} success rate ({partial_result.success_rate:.1%}) "
                f"below minimum threshold ({self.min_success_rate:.1%})"
            )
            
            # Create ValidationError with recovery actions
            validation_error = ValidationError(
                message=error_msg,
                context=context
            )
            # Add recovery actions after creation
            validation_error.recovery_actions.extend([
                RecoveryAction(
                    action_type="lower_threshold",
                    description=f"Lower minimum success rate threshold (current: {self.min_success_rate:.1%})"
                ),
                RecoveryAction(
                    action_type="investigate_failures",
                    description="Investigate common causes of failures"
                )
            ])
            raise validation_error
        
        return partial_result


class ErrorReporter:
    """Centralized error reporting and logging system."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize ErrorReporter.
        
        Args:
            logger: Logger instance for error reporting
        """
        self.logger = logger or logging.getLogger(__name__)
        self.error_history: List[TR181Error] = []
    
    def report_error(self, error: TR181Error) -> None:
        """Report an error with appropriate logging level.
        
        Args:
            error: TR181Error to report
        """
        # Add to error history
        self.error_history.append(error)
        
        # Log based on severity (avoid 'message' key conflict with LogRecord)
        error_dict = error.to_dict()
        # Remove 'message' key to avoid conflict with LogRecord
        log_extra = {k: v for k, v in error_dict.items() if k != 'message'}
        
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"CRITICAL ERROR: {error}", extra=log_extra)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(f"ERROR: {error}", extra=log_extra)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"WARNING: {error}", extra=log_extra)
        else:
            self.logger.info(f"INFO: {error}", extra=log_extra)
    
    def get_error_summary(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get a summary of errors within a time window.
        
        Args:
            time_window: Time window to consider (default: last hour)
            
        Returns:
            Dictionary with error summary statistics
        """
        if time_window is None:
            time_window = timedelta(hours=1)
        
        cutoff_time = datetime.now() - time_window
        recent_errors = [
            error for error in self.error_history
            if error.timestamp >= cutoff_time
        ]
        
        # Count by category and severity
        category_counts = {}
        severity_counts = {}
        
        for error in recent_errors:
            category_counts[error.category.value] = category_counts.get(error.category.value, 0) + 1
            severity_counts[error.severity.value] = severity_counts.get(error.severity.value, 0) + 1
        
        return {
            'total_errors': len(recent_errors),
            'time_window_hours': time_window.total_seconds() / 3600,
            'by_category': category_counts,
            'by_severity': severity_counts,
            'most_recent': recent_errors[-1].to_dict() if recent_errors else None
        }
    
    def clear_history(self) -> None:
        """Clear the error history."""
        self.error_history.clear()


# Global error reporter instance
_global_error_reporter = ErrorReporter()


def get_error_reporter() -> ErrorReporter:
    """Get the global error reporter instance."""
    return _global_error_reporter


def report_error(error: TR181Error) -> None:
    """Report an error using the global error reporter."""
    _global_error_reporter.report_error(error)