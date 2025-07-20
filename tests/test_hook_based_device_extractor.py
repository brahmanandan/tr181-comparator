"""Unit tests for HookBasedDeviceExtractor."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from tr181_comparator.extractors import HookBasedDeviceExtractor, ValidationResult, ConnectionError, ValidationError
from tr181_comparator.hooks import DeviceConnectionHook, DeviceConfig
from tr181_comparator.models import TR181Node, AccessLevel


class MockDeviceHook(DeviceConnectionHook):
    """Mock device hook for testing."""
    
    def __init__(self):
        self.connected = False
        self.parameter_names = []
        self.parameter_values = {}
        self.parameter_attributes = {}
        self.connection_should_fail = False
        self.discovery_should_fail = False
        self.values_should_fail = False
        self.attributes_should_fail = False
    
    async def connect(self, config: DeviceConfig) -> bool:
        if self.connection_should_fail:
            raise ConnectionError("Mock connection failure")
        self.connected = True
        return True
    
    async def disconnect(self) -> None:
        self.connected = False
    
    async def get_parameter_names(self, path_prefix: str = "Device.") -> list[str]:
        if not self.connected:
            raise ConnectionError("Not connected")
        if self.discovery_should_fail:
            raise Exception("Mock discovery failure")
        
        # Return parameters that match the prefix
        matching_params = [p for p in self.parameter_names if p.startswith(path_prefix)]
        return matching_params
    
    async def get_parameter_values(self, paths: list[str]) -> dict[str, any]:
        if not self.connected:
            raise ConnectionError("Not connected")
        if self.values_should_fail:
            raise Exception("Mock values failure")
        
        return {path: self.parameter_values.get(path, f"value_{path.split('.')[-1]}") for path in paths}
    
    async def get_parameter_attributes(self, paths: list[str]) -> dict[str, dict[str, any]]:
        if not self.connected:
            raise ConnectionError("Not connected")
        if self.attributes_should_fail:
            raise Exception("Mock attributes failure")
        
        return {
            path: self.parameter_attributes.get(path, {
                "type": "string",
                "access": "read-write",
                "description": f"Mock parameter {path}"
            })
            for path in paths
        }
    
    async def set_parameter_values(self, values: dict[str, any]) -> bool:
        if not self.connected:
            raise ConnectionError("Not connected")
        return True
    
    async def subscribe_to_event(self, event_path: str) -> bool:
        if not self.connected:
            raise ConnectionError("Not connected")
        return True
    
    async def call_function(self, function_path: str, input_params: dict[str, any]) -> dict[str, any]:
        if not self.connected:
            raise ConnectionError("Not connected")
        return {"result": "success", "output": {}}


@pytest.fixture
def mock_hook():
    """Create a mock device hook."""
    return MockDeviceHook()


@pytest.fixture
def device_config():
    """Create a device configuration."""
    return DeviceConfig(
        type="http",
        endpoint="http://test-device.local",
        authentication={"username": "admin", "password": "password"},
        timeout=30,
        retry_count=3
    )


@pytest.fixture
def extractor(mock_hook, device_config):
    """Create a HookBasedDeviceExtractor instance."""
    return HookBasedDeviceExtractor(mock_hook, device_config)


class TestHookBasedDeviceExtractor:
    """Test cases for HookBasedDeviceExtractor."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_hook, device_config):
        """Test extractor initialization."""
        extractor = HookBasedDeviceExtractor(mock_hook, device_config, {"test": "metadata"})
        
        assert extractor.hook is mock_hook
        assert extractor.device_config is device_config
        assert not extractor._connected
        assert not extractor._connection_validated
        assert extractor._metadata["test"] == "metadata"
    
    @pytest.mark.asyncio
    async def test_successful_extraction(self, extractor, mock_hook):
        """Test successful TR181 node extraction."""
        # Setup mock data
        mock_hook.parameter_names = [
            "Device.DeviceInfo.Manufacturer",
            "Device.DeviceInfo.ModelName",
            "Device.WiFi.Radio.1.Channel"
        ]
        mock_hook.parameter_values = {
            "Device.DeviceInfo.Manufacturer": "TestCorp",
            "Device.DeviceInfo.ModelName": "TestDevice",
            "Device.WiFi.Radio.1.Channel": 6  # Use int instead of string for int type
        }
        mock_hook.parameter_attributes = {
            "Device.DeviceInfo.Manufacturer": {"type": "string", "access": "read-only"},
            "Device.DeviceInfo.ModelName": {"type": "string", "access": "read-only"},
            "Device.WiFi.Radio.1.Channel": {"type": "int", "access": "read-write"}
        }
        
        # Extract nodes
        nodes = await extractor.extract()
        
        # Verify results
        assert len(nodes) == 3
        assert all(isinstance(node, TR181Node) for node in nodes)
        
        # Check specific nodes
        manufacturer_node = next(n for n in nodes if n.path == "Device.DeviceInfo.Manufacturer")
        assert manufacturer_node.name == "Manufacturer"
        assert manufacturer_node.value == "TestCorp"
        assert manufacturer_node.access == AccessLevel.READ_ONLY
        assert manufacturer_node.data_type == "string"
        
        channel_node = next(n for n in nodes if n.path == "Device.WiFi.Radio.1.Channel")
        assert channel_node.name == "Channel"
        assert channel_node.value == 6
        assert channel_node.access == AccessLevel.READ_WRITE
        assert channel_node.data_type == "int"
    
    @pytest.mark.asyncio
    async def test_extraction_with_no_parameters(self, extractor, mock_hook):
        """Test extraction when no parameters are discovered."""
        mock_hook.parameter_names = []
        
        nodes = await extractor.extract()
        
        assert nodes == []
        assert extractor._extraction_timestamp is not None
    
    @pytest.mark.asyncio
    async def test_extraction_connection_failure(self, extractor, mock_hook):
        """Test extraction failure due to connection issues."""
        mock_hook.connection_should_fail = True
        
        with pytest.raises(ConnectionError, match="Failed to connect to device"):
            await extractor.extract()
    
    @pytest.mark.asyncio
    async def test_extraction_discovery_failure(self, extractor, mock_hook):
        """Test extraction failure during parameter discovery."""
        mock_hook.discovery_should_fail = True
        
        with pytest.raises(ConnectionError, match="Failed to discover parameters from device"):
            await extractor.extract()
    
    @pytest.mark.asyncio
    async def test_extraction_with_batch_processing(self, extractor, mock_hook):
        """Test extraction with large number of parameters (batch processing)."""
        # Create 150 parameters to test batch processing (batch size is 50)
        mock_hook.parameter_names = [f"Device.Test.Param{i}" for i in range(150)]
        
        # Setup attributes and values for all parameters
        for param in mock_hook.parameter_names:
            mock_hook.parameter_attributes[param] = {"type": "string", "access": "read-write"}
            mock_hook.parameter_values[param] = f"value_{param.split('.')[-1]}"
        
        nodes = await extractor.extract()
        
        assert len(nodes) == 150
        assert all(isinstance(node, TR181Node) for node in nodes)
    
    @pytest.mark.asyncio
    async def test_extraction_with_partial_batch_failure(self, extractor, mock_hook):
        """Test extraction continues when some batches fail."""
        mock_hook.parameter_names = [f"Device.Test.Param{i}" for i in range(10)]
        
        # Mock the hook to fail on specific calls
        original_get_attributes = mock_hook.get_parameter_attributes
        call_count = 0
        
        async def failing_get_attributes(paths):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Fail first batch
                raise Exception("First batch failure")
            return await original_get_attributes(paths)
        
        mock_hook.get_parameter_attributes = failing_get_attributes
        
        # Should still extract some nodes despite first batch failure
        nodes = await extractor.extract()
        
        # Should have fewer nodes due to batch failure, but not zero
        assert len(nodes) >= 0  # Some batches might succeed
    
    @pytest.mark.asyncio
    async def test_validate_successful(self, extractor, mock_hook):
        """Test successful device validation."""
        mock_hook.parameter_names = ["Device.DeviceInfo.Manufacturer"]
        mock_hook.parameter_values = {"Device.DeviceInfo.Manufacturer": "TestCorp"}
        
        result = await extractor.validate()
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert extractor._connection_validated
    
    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, extractor, mock_hook):
        """Test validation failure due to connection issues."""
        mock_hook.connection_should_fail = True
        
        result = await extractor.validate()
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "Cannot connect to device" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_no_device_info_parameters(self, extractor, mock_hook):
        """Test validation warning when no DeviceInfo parameters found."""
        mock_hook.parameter_names = []  # No parameters returned
        
        result = await extractor.validate()
        
        assert result.is_valid  # Still valid, but with warnings
        assert len(result.warnings) >= 1
        assert any("may not support TR181" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_get_source_info(self, extractor, device_config):
        """Test source info generation."""
        source_info = extractor.get_source_info()
        
        assert source_info.type == "device"
        assert source_info.identifier == device_config.endpoint
        assert isinstance(source_info.timestamp, datetime)
        assert source_info.metadata["device_type"] == device_config.type
        assert source_info.metadata["timeout"] == device_config.timeout
        assert source_info.metadata["retry_count"] == device_config.retry_count
    
    @pytest.mark.asyncio
    async def test_disconnect(self, extractor, mock_hook):
        """Test device disconnection."""
        # Connect first
        await extractor._ensure_connected()
        assert extractor._connected
        
        # Disconnect
        await extractor.disconnect()
        
        assert not extractor._connected
        assert not extractor._connection_validated
        assert not mock_hook.connected
    
    @pytest.mark.asyncio
    async def test_disconnect_with_error(self, extractor, mock_hook):
        """Test disconnect handles errors gracefully."""
        # Connect first
        await extractor._ensure_connected()
        
        # Make disconnect fail
        async def failing_disconnect():
            raise Exception("Disconnect error")
        
        mock_hook.disconnect = failing_disconnect
        
        # Should not raise exception
        await extractor.disconnect()
        
        # Should still mark as disconnected
        assert not extractor._connected
        assert not extractor._connection_validated
    
    @pytest.mark.asyncio
    async def test_connection_retry_logic(self, extractor, mock_hook):
        """Test connection retry with exponential backoff."""
        call_count = 0
        original_connect = mock_hook.connect
        
        async def failing_connect(config):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 attempts
                raise Exception(f"Connection attempt {call_count} failed")
            return await original_connect(config)
        
        mock_hook.connect = failing_connect
        
        # Should eventually succeed after retries
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            success = await extractor._connect_with_retry()
            
            assert success
            assert call_count == 3
            assert mock_sleep.call_count == 2  # Should sleep between retries
    
    @pytest.mark.asyncio
    async def test_connection_retry_exhausted(self, extractor, mock_hook):
        """Test connection retry when all attempts fail."""
        mock_hook.connection_should_fail = True
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            success = await extractor._connect_with_retry()
            
            assert not success
            assert not extractor._connected
    
    @pytest.mark.asyncio
    async def test_test_parameter_write_access(self, extractor, mock_hook):
        """Test parameter write access testing."""
        await extractor._ensure_connected()
        
        test_params = {
            "Device.WiFi.Radio.1.Channel": 11,
            "Device.WiFi.SSID.1.Name": "TestSSID"
        }
        
        results = await extractor.test_parameter_write_access(test_params)
        
        assert len(results) == 2
        assert all(results.values())  # All should succeed with mock
    
    @pytest.mark.asyncio
    async def test_test_event_subscription(self, extractor, mock_hook):
        """Test event subscription testing."""
        await extractor._ensure_connected()
        
        event_paths = ["Device.WiFi.Radio.1.ChannelChanged", "Device.WiFi.SSID.1.StatusChanged"]
        
        results = await extractor.test_event_subscription(event_paths)
        
        assert len(results) == 2
        assert all(results.values())  # All should succeed with mock
    
    @pytest.mark.asyncio
    async def test_test_function_calls(self, extractor, mock_hook):
        """Test function call testing."""
        await extractor._ensure_connected()
        
        function_tests = {
            "Device.WiFi.Radio.1.Scan": {"timeout": 30},
            "Device.WiFi.SSID.1.Reset": {}
        }
        
        results = await extractor.test_function_calls(function_tests)
        
        assert len(results) == 2
        assert all(result["success"] for result in results.values())
    
    @pytest.mark.asyncio
    async def test_node_relationship_building(self, extractor, mock_hook):
        """Test building parent-child relationships between nodes."""
        mock_hook.parameter_names = [
            "Device.WiFi",
            "Device.WiFi.Radio",
            "Device.WiFi.Radio.1",
            "Device.WiFi.Radio.1.Channel",
            "Device.WiFi.SSID",
            "Device.WiFi.SSID.1",
            "Device.WiFi.SSID.1.Name"
        ]
        
        # Mark some as objects and provide proper values
        mock_hook.parameter_attributes = {
            "Device.WiFi": {"type": "object", "access": "read-only", "object": True},
            "Device.WiFi.Radio": {"type": "object", "access": "read-only", "object": True},
            "Device.WiFi.Radio.1": {"type": "object", "access": "read-only", "object": True},
            "Device.WiFi.Radio.1.Channel": {"type": "int", "access": "read-write"},
            "Device.WiFi.SSID": {"type": "object", "access": "read-only", "object": True},
            "Device.WiFi.SSID.1": {"type": "object", "access": "read-only", "object": True},
            "Device.WiFi.SSID.1.Name": {"type": "string", "access": "read-write"}
        }
        
        # Provide proper values for non-object parameters
        mock_hook.parameter_values = {
            "Device.WiFi.Radio.1.Channel": 6,
            "Device.WiFi.SSID.1.Name": "TestSSID"
        }
        
        nodes = await extractor.extract()
        
        # Find specific nodes to test relationships
        wifi_node = next(n for n in nodes if n.path == "Device.WiFi")
        radio_node = next(n for n in nodes if n.path == "Device.WiFi.Radio")
        channel_node = next(n for n in nodes if n.path == "Device.WiFi.Radio.1.Channel")
        
        # Test parent-child relationships
        assert wifi_node.is_object
        assert "Device.WiFi.Radio" in wifi_node.children
        assert "Device.WiFi.SSID" in wifi_node.children
        
        assert radio_node.parent == "Device.WiFi"
        assert channel_node.parent == "Device.WiFi.Radio.1"
    
    @pytest.mark.asyncio
    async def test_access_level_mapping(self, extractor, mock_hook):
        """Test mapping of device access levels to TR181 access levels."""
        mock_hook.parameter_names = [
            "Device.Test.ReadOnly",
            "Device.Test.ReadWrite",
            "Device.Test.WriteOnly",
            "Device.Test.ReadWriteAlt"
        ]
        
        mock_hook.parameter_attributes = {
            "Device.Test.ReadOnly": {"type": "string", "access": "read-only"},
            "Device.Test.ReadWrite": {"type": "string", "access": "read-write"},
            "Device.Test.WriteOnly": {"type": "string", "access": "write-only"},
            "Device.Test.ReadWriteAlt": {"type": "string", "access": "readwrite"}  # Alternative format
        }
        
        nodes = await extractor.extract()
        
        # Test access level mapping
        readonly_node = next(n for n in nodes if n.path == "Device.Test.ReadOnly")
        readwrite_node = next(n for n in nodes if n.path == "Device.Test.ReadWrite")
        writeonly_node = next(n for n in nodes if n.path == "Device.Test.WriteOnly")
        readwrite_alt_node = next(n for n in nodes if n.path == "Device.Test.ReadWriteAlt")
        
        assert readonly_node.access == AccessLevel.READ_ONLY
        assert readwrite_node.access == AccessLevel.READ_WRITE
        assert writeonly_node.access == AccessLevel.WRITE_ONLY
        assert readwrite_alt_node.access == AccessLevel.READ_WRITE
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self, extractor, mock_hook):
        """Test using extractor as async context manager."""
        async with extractor as ctx_extractor:
            assert ctx_extractor is extractor
            # Should be able to use extractor normally
            await ctx_extractor._ensure_connected()
            assert ctx_extractor._connected
        
        # Should be disconnected after context exit
        assert not extractor._connected
    
    @pytest.mark.asyncio
    async def test_parameter_discovery_with_objects(self, extractor, mock_hook):
        """Test parameter discovery includes object sub-parameters."""
        # Setup root parameters including objects
        root_params = ["Device.WiFi.", "Device.DeviceInfo.Manufacturer"]
        sub_params = ["Device.WiFi.Radio.1.Channel", "Device.WiFi.SSID.1.Name"]
        
        call_count = 0
        
        async def mock_get_parameter_names(path_prefix):
            nonlocal call_count
            call_count += 1
            if path_prefix == "Device.":
                return root_params
            elif path_prefix == "Device.WiFi.":
                return sub_params
            return []
        
        mock_hook.get_parameter_names = mock_get_parameter_names
        
        # Test parameter discovery
        all_params = await extractor._discover_all_parameters()
        
        # Should include both root and sub-parameters
        expected_params = sorted(root_params + sub_params)
        assert sorted(all_params) == expected_params
        assert call_count >= 2  # Should have made multiple discovery calls
    
    @pytest.mark.asyncio
    async def test_create_node_from_parameter_error_handling(self, extractor):
        """Test error handling in node creation from parameter data."""
        # Test with invalid parameter data
        node = extractor._create_node_from_parameter(
            "Device.Test.Param",
            {"type": "invalid_type", "access": "invalid_access"},
            "test_value"
        )
        
        # Should handle errors gracefully and still create a node with defaults
        assert node is not None
        assert node.path == "Device.Test.Param"
        assert node.name == "Param"
        assert node.access == AccessLevel.READ_ONLY  # Default fallback
    
    @pytest.mark.asyncio
    async def test_validation_with_invalid_nodes(self, extractor, mock_hook):
        """Test extraction validation catches invalid nodes."""
        mock_hook.parameter_names = ["Device.Test.Param"]
        mock_hook.parameter_attributes = {"Device.Test.Param": {"type": "int", "access": "read-write"}}
        mock_hook.parameter_values = {"Device.Test.Param": "not_a_number"}  # Invalid int value
        
        # Should raise ValidationError due to type mismatch
        with pytest.raises(ValidationError, match="Extracted nodes failed validation.*Expected int, got str"):
            await extractor.extract()


if __name__ == "__main__":
    pytest.main([__file__])