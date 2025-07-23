"""Integration tests for error handling with extractors."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
import tempfile
import os

from tr181_comparator.extractors import OperatorRequirementManager, HookBasedDeviceExtractor
from tr181_comparator.errors import (
    ConnectionError, ValidationError, RetryManager, 
    GracefulDegradationManager, get_error_reporter
)
from tr181_comparator.hooks import DeviceConnectionHook
from tr181_comparator.models import TR181Node, AccessLevel


class MockDeviceHook(DeviceConnectionHook):
    """Mock device hook for testing error handling."""
    
    def __init__(self, should_fail=False, fail_count=0):
        self.should_fail = should_fail
        self.fail_count = fail_count
        self.call_count = 0
        self.connected = False
    
    async def connect(self, config):
        self.call_count += 1
        if self.should_fail and self.call_count <= self.fail_count:
            raise ConnectionError("Mock connection failed")
        self.connected = True
        return True
    
    async def disconnect(self):
        self.connected = False
    
    async def get_parameter_names(self, path_prefix="Device."):
        if not self.connected:
            raise ConnectionError("Not connected")
        return ["Device.WiFi.Radio.1.Channel", "Device.WiFi.Radio.1.SSID"]
    
    async def get_parameter_values(self, paths):
        if not self.connected:
            raise ConnectionError("Not connected")
        return {path: f"value_for_{path.split('.')[-1]}" for path in paths}
    
    async def get_parameter_attributes(self, paths):
        if not self.connected:
            raise ConnectionError("Not connected")
        return {
            path: {
                "type": "string",
                "access": "read-write",
                "notification": "passive"
            } for path in paths
        }
    
    async def set_parameter_values(self, values):
        return True
    
    async def subscribe_to_event(self, event_path):
        return True
    
    async def call_function(self, function_path, input_params):
        return {"result": "success"}


class MockDeviceConfig:
    """Mock device configuration."""
    def __init__(self, endpoint="http://test.device"):
        self.endpoint = endpoint
        self.retry_count = 3


class TestErrorHandlingIntegration:
    """Integration tests for error handling with extractors."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear error reporter history
        get_error_reporter().clear_history()
    
    @pytest.mark.asyncio
    async def test_operator_requirement_manager_file_not_found_error(self):
        """Test OperatorRequirementManager handling of missing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_file = os.path.join(temp_dir, "non_existent.json")
            
            operator_requirement_manager = OperatorRequirementManager(non_existent_file)
            
            # Should handle missing file gracefully by creating empty operator requirement
            nodes = await operator_requirement_manager.extract()
            assert nodes == []
            
            # Validation should pass for empty operator requirement
            validation_result = await operator_requirement_manager.validate()
            assert validation_result.is_valid
    
    @pytest.mark.asyncio
    async def test_operator_requirement_manager_invalid_json_error(self):
        """Test OperatorRequirementManager handling of invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            temp_file = f.name
        
        try:
            operator_requirement_manager = OperatorRequirementManager(temp_file)
            
            with pytest.raises(ValidationError) as exc_info:
                await operator_requirement_manager.extract()
            
            assert "Failed to load operator requirement" in str(exc_info.value)
            assert exc_info.value.category.value == "validation"
            
        finally:
            os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_device_extractor_connection_retry(self):
        """Test device extractor retry logic on connection failures."""
        # Mock hook that fails first 2 attempts, succeeds on 3rd
        mock_hook = MockDeviceHook(should_fail=True, fail_count=2)
        config = MockDeviceConfig()
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Should succeed after retries
        nodes = await extractor.extract()
        
        # Should have made 3 connection attempts
        assert mock_hook.call_count == 3
        assert len(nodes) == 2  # Should extract 2 nodes
        assert mock_hook.connected
    
    @pytest.mark.asyncio
    async def test_device_extractor_connection_failure_exhausted(self):
        """Test device extractor when all retry attempts fail."""
        # Mock hook that always fails
        mock_hook = MockDeviceHook(should_fail=True, fail_count=10)
        config = MockDeviceConfig()
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        with pytest.raises(ConnectionError) as exc_info:
            await extractor.extract()
        
        # Should have made maximum retry attempts
        assert mock_hook.call_count == 3  # max_attempts
        assert "Mock connection failed" in str(exc_info.value.cause)
    
    @pytest.mark.asyncio
    async def test_device_extractor_graceful_degradation(self):
        """Test device extractor graceful degradation with partial failures."""
        
        class PartialFailureHook(MockDeviceHook):
            async def get_parameter_attributes(self, paths):
                if not self.connected:
                    raise ConnectionError("Not connected")
                
                # Fail for one specific parameter
                if "Device.WiFi.Radio.1.SSID" in paths:
                    raise ValidationError("Failed to get SSID attributes")
                
                return {
                    path: {
                        "type": "string",
                        "access": "read-write",
                        "notification": "passive"
                    } for path in paths if path != "Device.WiFi.Radio.1.SSID"
                }
        
        mock_hook = PartialFailureHook()
        config = MockDeviceConfig()
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Should succeed with partial results
        nodes = await extractor.extract()
        
        # Should have extracted only the successful node
        assert len(nodes) == 1
        assert nodes[0].path == "Device.WiFi.Radio.1.Channel"
    
    @pytest.mark.asyncio
    async def test_error_reporting_integration(self):
        """Test that errors are properly reported to the global error reporter."""
        # Clear error history
        get_error_reporter().clear_history()
        
        # Create a failing extractor
        mock_hook = MockDeviceHook(should_fail=True, fail_count=10)
        config = MockDeviceConfig()
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        try:
            await extractor.extract()
        except ConnectionError:
            pass  # Expected
        
        # Check that errors were reported
        error_summary = get_error_reporter().get_error_summary()
        assert error_summary["total_errors"] > 0
        assert "connection" in error_summary["by_category"]
    
    @pytest.mark.asyncio
    async def test_retry_manager_standalone(self):
        """Test RetryManager as a standalone component."""
        retry_manager = RetryManager()
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await retry_manager.execute_with_retry(
            failing_operation,
            "test_operation"
        )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_manager_standalone(self):
        """Test GracefulDegradationManager as a standalone component."""
        degradation_manager = GracefulDegradationManager(min_success_rate=0.6)
        
        items = ["item1", "item2", "item3", "item4", "item5"]
        
        async def partially_failing_operation(item):
            if item in ["item2", "item4"]:
                raise ValueError(f"Failed to process {item}")
            return f"processed_{item}"
        
        result = await degradation_manager.execute_with_partial_success(
            items=items,
            operation=partially_failing_operation,
            operation_name="test_operation"
        )
        
        assert len(result.successful_items) == 3
        assert len(result.failed_items) == 2
        assert result.success_rate == 0.6
        assert result.is_acceptable(0.6)
    
    def test_error_context_propagation(self):
        """Test that error context is properly propagated through the system."""
        from tr181_comparator.errors import ErrorContext, ErrorCategory
        
        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            metadata={"test_key": "test_value"}
        )
        
        error = ConnectionError(
            message="Test connection error",
            endpoint="http://test.device",
            context=context
        )
        
        # Verify context is preserved
        assert error.context.operation == "test_operation"
        assert error.context.component == "test_component"
        assert error.context.metadata["test_key"] == "test_value"
        
        # Verify error can be serialized with context
        error_dict = error.to_dict()
        assert error_dict["context"]["operation"] == "test_operation"
        assert error_dict["context"]["metadata"]["test_key"] == "test_value"


if __name__ == "__main__":
    pytest.main([__file__])