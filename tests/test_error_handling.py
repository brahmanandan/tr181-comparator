"""Unit tests for the comprehensive error handling and recovery system."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from tr181_comparator.errors import (
    TR181Error, ConnectionError, ValidationError, AuthenticationError,
    TimeoutError, ProtocolError, ConfigurationError, ErrorContext,
    ErrorCategory, ErrorSeverity, RecoveryAction, RetryConfig,
    RetryManager, GracefulDegradationManager, PartialResult,
    ErrorReporter, get_error_reporter, report_error
)


class TestTR181Error:
    """Test cases for the base TR181Error class."""
    
    def test_basic_error_creation(self):
        """Test basic error creation with minimal parameters."""
        error = TR181Error(
            message="Test error",
            category=ErrorCategory.CONNECTION
        )
        
        assert error.message == "Test error"
        assert error.category == ErrorCategory.CONNECTION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.error_code.startswith("TR181_CONNECTION_")
        assert isinstance(error.timestamp, datetime)
    
    def test_error_with_full_context(self):
        """Test error creation with full context information."""
        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            attempt_number=2,
            max_attempts=3,
            metadata={"key": "value"}
        )
        
        recovery_actions = [
            RecoveryAction(
                action_type="retry",
                description="Retry the operation",
                automatic=True
            )
        ]
        
        error = TR181Error(
            message="Test error with context",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            recovery_actions=recovery_actions,
            error_code="CUSTOM_ERROR_001"
        )
        
        assert error.context == context
        assert len(error.recovery_actions) == 1
        assert error.recovery_actions[0].action_type == "retry"
        assert error.error_code == "CUSTOM_ERROR_001"
    
    def test_error_to_dict(self):
        """Test error serialization to dictionary."""
        context = ErrorContext(
            operation="test_op",
            component="test_comp"
        )
        
        error = TR181Error(
            message="Test error",
            category=ErrorCategory.TIMEOUT,
            context=context
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["message"] == "Test error"
        assert error_dict["category"] == "timeout"
        assert error_dict["context"]["operation"] == "test_op"
        assert "timestamp" in error_dict
    
    def test_user_message_with_recovery_actions(self):
        """Test user-friendly message generation."""
        recovery_actions = [
            RecoveryAction("check_network", "Check network connectivity"),
            RecoveryAction("retry", "Retry the operation")
        ]
        
        error = TR181Error(
            message="Connection failed",
            category=ErrorCategory.CONNECTION,
            recovery_actions=recovery_actions
        )
        
        user_msg = error.get_user_message()
        assert "Connection failed" in user_msg
        assert "Check network connectivity" in user_msg
        assert "Retry the operation" in user_msg


class TestSpecificErrors:
    """Test cases for specific error types."""
    
    def test_connection_error(self):
        """Test ConnectionError with endpoint and timeout."""
        error = ConnectionError(
            message="Failed to connect",
            endpoint="http://device.local",
            timeout=30.0
        )
        
        assert error.endpoint == "http://device.local"
        assert error.timeout == 30.0
        assert error.category == ErrorCategory.CONNECTION
        assert any("timeout" in action.description.lower() for action in error.recovery_actions)
    
    def test_validation_error(self):
        """Test ValidationError with validation details."""
        validation_errors = ["Missing required field", "Invalid data type"]
        
        error = ValidationError(
            message="Validation failed",
            validation_errors=validation_errors,
            node_path="Device.WiFi.Radio.1"
        )
        
        assert error.validation_errors == validation_errors
        assert error.node_path == "Device.WiFi.Radio.1"
        assert error.category == ErrorCategory.VALIDATION
    
    def test_authentication_error(self):
        """Test AuthenticationError with auth method."""
        error = AuthenticationError(
            message="Authentication failed",
            auth_method="basic_auth"
        )
        
        assert error.auth_method == "basic_auth"
        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.severity == ErrorSeverity.HIGH
    
    def test_timeout_error(self):
        """Test TimeoutError with duration and operation."""
        error = TimeoutError(
            message="Operation timed out",
            timeout_duration=60.0,
            operation="parameter_discovery"
        )
        
        assert error.timeout_duration == 60.0
        assert error.operation == "parameter_discovery"
        assert error.category == ErrorCategory.TIMEOUT
    
    def test_protocol_error(self):
        """Test ProtocolError with protocol details."""
        error_details = {"code": 500, "response": "Internal Server Error"}
        
        error = ProtocolError(
            message="Protocol error occurred",
            protocol="REST",
            error_details=error_details
        )
        
        assert error.protocol == "REST"
        assert error.error_details == error_details
        assert error.category == ErrorCategory.PROTOCOL
    
    def test_configuration_error(self):
        """Test ConfigurationError with config details."""
        error = ConfigurationError(
            message="Invalid configuration",
            config_key="endpoint",
            expected_type=str,
            actual_value=123
        )
        
        assert error.config_key == "endpoint"
        assert error.expected_type == str
        assert error.actual_value == 123
        assert error.category == ErrorCategory.CONFIGURATION


class TestRetryManager:
    """Test cases for the RetryManager class."""
    
    @pytest.fixture
    def retry_manager(self):
        """Create a RetryManager for testing."""
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,  # Short delay for testing
            max_delay=1.0,
            backoff_factor=2.0
        )
        return RetryManager(config)
    
    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self, retry_manager):
        """Test successful operation that doesn't need retry."""
        mock_operation = AsyncMock(return_value="success")
        
        result = await retry_manager.execute_with_retry(
            mock_operation,
            "test_operation"
        )
        
        assert result == "success"
        assert mock_operation.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_retryable_exception(self, retry_manager):
        """Test retry logic with retryable exceptions."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = [
            ConnectionError("First attempt failed"),
            ConnectionError("Second attempt failed"),
            "success"  # Third attempt succeeds
        ]
        
        result = await retry_manager.execute_with_retry(
            mock_operation,
            "test_operation"
        )
        
        assert result == "success"
        assert mock_operation.call_count == 3
    
    @pytest.mark.asyncio
    async def test_non_retryable_exception(self, retry_manager):
        """Test that non-retryable exceptions are not retried."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = ValidationError(
            "Validation failed"
        )
        
        # ValidationError is not in retryable_exceptions by default
        retry_manager.config.retryable_exceptions = (ConnectionError, TimeoutError)
        
        with pytest.raises(ValidationError):
            await retry_manager.execute_with_retry(
                mock_operation,
                "test_operation"
            )
        
        assert mock_operation.call_count == 1
    
    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self, retry_manager):
        """Test behavior when max attempts are exceeded."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = ConnectionError(
            "Always fails"
        )
        
        with pytest.raises(ConnectionError):
            await retry_manager.execute_with_retry(
                mock_operation,
                "test_operation"
            )
        
        assert mock_operation.call_count == 3  # max_attempts
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_wrapping(self, retry_manager):
        """Test that unexpected exceptions are not retried and passed through."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = ValueError("Unexpected error")
        
        # ValueError is not in retryable_exceptions, so it should be raised immediately
        with pytest.raises(ValueError) as exc_info:
            await retry_manager.execute_with_retry(
                mock_operation,
                "test_operation"
            )
        
        assert str(exc_info.value) == "Unexpected error"
        assert mock_operation.call_count == 1  # Should not retry
    
    def test_delay_calculation(self, retry_manager):
        """Test exponential backoff delay calculation."""
        # Disable jitter for predictable testing
        retry_manager.config.jitter = False
        
        # Test delay calculation for different attempts
        delay1 = retry_manager._calculate_delay(1)
        delay2 = retry_manager._calculate_delay(2)
        delay3 = retry_manager._calculate_delay(3)
        
        # Should follow exponential backoff pattern
        assert delay1 == 0.1  # base_delay
        assert delay2 == 0.2  # base_delay * backoff_factor
        assert delay3 == 0.4  # base_delay * backoff_factor^2
    
    def test_delay_capping(self, retry_manager):
        """Test that delay is capped at max_delay."""
        # Disable jitter for predictable testing
        retry_manager.config.jitter = False
        
        # Set a very high attempt number
        delay = retry_manager._calculate_delay(10)
        
        # Should be capped at max_delay
        assert delay <= retry_manager.config.max_delay
        assert delay == retry_manager.config.max_delay  # Should be exactly max_delay


class TestGracefulDegradationManager:
    """Test cases for the GracefulDegradationManager class."""
    
    @pytest.fixture
    def degradation_manager(self):
        """Create a GracefulDegradationManager for testing."""
        return GracefulDegradationManager(min_success_rate=0.6)
    
    @pytest.mark.asyncio
    async def test_all_items_successful(self, degradation_manager):
        """Test processing when all items succeed."""
        items = ["item1", "item2", "item3"]
        mock_operation = AsyncMock(side_effect=lambda x: f"processed_{x}")
        
        result = await degradation_manager.execute_with_partial_success(
            items=items,
            operation=mock_operation,
            operation_name="test_operation"
        )
        
        assert len(result.successful_items) == 3
        assert len(result.failed_items) == 0
        assert result.success_rate == 1.0
        assert result.is_acceptable()
    
    @pytest.mark.asyncio
    async def test_partial_success_acceptable(self, degradation_manager):
        """Test processing with acceptable partial success."""
        items = ["item1", "item2", "item3", "item4", "item5"]
        
        def mock_operation(item):
            if item in ["item2", "item4"]:
                raise ValueError(f"Failed to process {item}")
            return f"processed_{item}"
        
        result = await degradation_manager.execute_with_partial_success(
            items=items,
            operation=mock_operation,
            operation_name="test_operation"
        )
        
        assert len(result.successful_items) == 3
        assert len(result.failed_items) == 2
        assert result.success_rate == 0.6  # 3/5
        assert result.is_acceptable(0.6)
    
    @pytest.mark.asyncio
    async def test_partial_success_unacceptable(self, degradation_manager):
        """Test processing with unacceptable partial success."""
        items = ["item1", "item2", "item3", "item4", "item5"]
        
        def mock_operation(item):
            if item in ["item1", "item3", "item4", "item5"]:
                raise ValueError(f"Failed to process {item}")
            return f"processed_{item}"
        
        with pytest.raises(ValidationError) as exc_info:
            await degradation_manager.execute_with_partial_success(
                items=items,
                operation=mock_operation,
                operation_name="test_operation"
            )
        
        assert "success rate" in str(exc_info.value)
        assert "below minimum threshold" in str(exc_info.value)


class TestPartialResult:
    """Test cases for the PartialResult class."""
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        successful_items = ["item1", "item2", "item3"]
        failed_items = [("item4", Exception()), ("item5", Exception())]
        
        result = PartialResult(
            successful_items=successful_items,
            failed_items=failed_items,
            total_items=5
        )
        
        assert result.success_rate == 0.6  # 3/5
    
    def test_empty_result(self):
        """Test partial result with no items."""
        result = PartialResult(
            successful_items=[],
            failed_items=[],
            total_items=0
        )
        
        assert result.success_rate == 0.0
    
    def test_is_acceptable(self):
        """Test acceptability checking."""
        result = PartialResult(
            successful_items=["item1", "item2", "item3"],
            failed_items=[("item4", Exception())],
            total_items=4
        )
        
        assert result.is_acceptable(0.5)  # 75% > 50%
        assert not result.is_acceptable(0.8)  # 75% < 80%


class TestErrorReporter:
    """Test cases for the ErrorReporter class."""
    
    @pytest.fixture
    def error_reporter(self):
        """Create an ErrorReporter for testing."""
        return ErrorReporter()
    
    def test_report_error(self, error_reporter):
        """Test error reporting."""
        error = TR181Error(
            message="Test error",
            category=ErrorCategory.CONNECTION,
            severity=ErrorSeverity.HIGH
        )
        
        error_reporter.report_error(error)
        
        assert len(error_reporter.error_history) == 1
        assert error_reporter.error_history[0] == error
    
    def test_error_summary(self, error_reporter):
        """Test error summary generation."""
        # Add some test errors
        errors = [
            TR181Error("Error 1", ErrorCategory.CONNECTION, ErrorSeverity.HIGH),
            TR181Error("Error 2", ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM),
            TR181Error("Error 3", ErrorCategory.CONNECTION, ErrorSeverity.LOW),
        ]
        
        for error in errors:
            error_reporter.report_error(error)
        
        summary = error_reporter.get_error_summary()
        
        assert summary["total_errors"] == 3
        assert summary["by_category"]["connection"] == 2
        assert summary["by_category"]["validation"] == 1
        assert summary["by_severity"]["high"] == 1
        assert summary["by_severity"]["medium"] == 1
        assert summary["by_severity"]["low"] == 1
    
    def test_error_summary_time_window(self, error_reporter):
        """Test error summary with time window filtering."""
        # Create an old error (simulate by setting timestamp)
        old_error = TR181Error("Old error", ErrorCategory.CONNECTION)
        old_error.timestamp = datetime.now() - timedelta(hours=2)
        
        # Create a recent error
        recent_error = TR181Error("Recent error", ErrorCategory.VALIDATION)
        
        error_reporter.error_history = [old_error, recent_error]
        
        # Get summary for last hour
        summary = error_reporter.get_error_summary(timedelta(hours=1))
        
        assert summary["total_errors"] == 1  # Only recent error
        assert "validation" in summary["by_category"]
        assert "connection" not in summary["by_category"]
    
    def test_clear_history(self, error_reporter):
        """Test clearing error history."""
        error = TR181Error("Test error", ErrorCategory.CONNECTION)
        error_reporter.report_error(error)
        
        assert len(error_reporter.error_history) == 1
        
        error_reporter.clear_history()
        
        assert len(error_reporter.error_history) == 0


class TestGlobalErrorReporter:
    """Test cases for global error reporter functions."""
    
    def test_get_global_error_reporter(self):
        """Test getting the global error reporter instance."""
        reporter1 = get_error_reporter()
        reporter2 = get_error_reporter()
        
        # Should return the same instance
        assert reporter1 is reporter2
    
    def test_global_report_error(self):
        """Test global error reporting function."""
        error = TR181Error("Global test error", ErrorCategory.TIMEOUT)
        
        # Clear any existing history
        get_error_reporter().clear_history()
        
        report_error(error)
        
        # Should be in global reporter's history
        assert len(get_error_reporter().error_history) == 1
        assert get_error_reporter().error_history[0] == error


class TestErrorContext:
    """Test cases for ErrorContext class."""
    
    def test_error_context_creation(self):
        """Test ErrorContext creation and serialization."""
        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            attempt_number=2,
            max_attempts=3,
            metadata={"key": "value"}
        )
        
        context_dict = context.to_dict()
        
        assert context_dict["operation"] == "test_operation"
        assert context_dict["component"] == "test_component"
        assert context_dict["attempt_number"] == 2
        assert context_dict["max_attempts"] == 3
        assert context_dict["metadata"]["key"] == "value"
        assert "timestamp" in context_dict


class TestRecoveryAction:
    """Test cases for RecoveryAction class."""
    
    def test_recovery_action_creation(self):
        """Test RecoveryAction creation."""
        action = RecoveryAction(
            action_type="retry",
            description="Retry the operation",
            automatic=True,
            parameters={"delay": 5.0}
        )
        
        assert action.action_type == "retry"
        assert action.description == "Retry the operation"
        assert action.automatic is True
        assert action.parameters["delay"] == 5.0


if __name__ == "__main__":
    pytest.main([__file__])