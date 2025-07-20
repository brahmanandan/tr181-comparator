"""Unit tests for device communication hooks."""

import pytest
from unittest.mock import AsyncMock, patch
from tr181_comparator.hooks import (
    DeviceConnectionHook, RESTAPIHook, CWMPHook, DeviceHookFactory,
    HookType, DeviceConfig
)
from tr181_comparator.extractors import ConnectionError


class TestDeviceConfig:
    """Test DeviceConfig dataclass."""
    
    def test_device_config_creation(self):
        """Test creating a DeviceConfig instance."""
        config = DeviceConfig(
            type="http",
            endpoint="http://192.168.1.1",
            authentication={"username": "admin", "password": "password"}
        )
        
        assert config.type == "http"
        assert config.endpoint == "http://192.168.1.1"
        assert config.authentication == {"username": "admin", "password": "password"}
        assert config.timeout == 30  # default value
        assert config.retry_count == 3  # default value
    
    def test_device_config_with_custom_values(self):
        """Test creating DeviceConfig with custom timeout and retry values."""
        config = DeviceConfig(
            type="cwmp",
            endpoint="http://device.example.com:7547",
            authentication={"cert_path": "/path/to/cert.pem"},
            timeout=60,
            retry_count=5
        )
        
        assert config.timeout == 60
        assert config.retry_count == 5


class TestDeviceHookFactory:
    """Test DeviceHookFactory functionality."""
    
    def test_create_rest_api_hook(self):
        """Test creating a REST API hook."""
        hook = DeviceHookFactory.create_hook(HookType.REST_API)
        assert isinstance(hook, RESTAPIHook)
    
    def test_create_cwmp_hook(self):
        """Test creating a CWMP hook."""
        hook = DeviceHookFactory.create_hook(HookType.CWMP)
        assert isinstance(hook, CWMPHook)
    
    def test_create_unsupported_hook_type(self):
        """Test creating an unsupported hook type raises ValueError."""
        # Create a mock enum value that doesn't exist in registry
        with pytest.raises(ValueError, match="Unsupported hook type"):
            # We can't easily create a new enum value, so we'll patch the registry
            with patch.object(DeviceHookFactory, '_hook_registry', {}):
                DeviceHookFactory.create_hook(HookType.REST_API)
    
    def test_get_supported_types(self):
        """Test getting supported hook types."""
        supported_types = DeviceHookFactory.get_supported_types()
        assert HookType.REST_API in supported_types
        assert HookType.CWMP in supported_types
        assert len(supported_types) == 2
    
    def test_register_new_hook_type(self):
        """Test registering a new hook type."""
        class CustomHook(DeviceConnectionHook):
            async def connect(self, config): return True
            async def disconnect(self): pass
            async def get_parameter_names(self, path_prefix="Device."): return []
            async def get_parameter_values(self, paths): return {}
            async def get_parameter_attributes(self, paths): return {}
            async def set_parameter_values(self, values): return True
            async def subscribe_to_event(self, event_path): return True
            async def call_function(self, function_path, input_params): return {}
        
        # Create a new hook type for testing
        custom_type = "custom"
        
        # Store original registry to restore later
        original_registry = DeviceHookFactory._hook_registry.copy()
        
        try:
            # Register the custom hook
            DeviceHookFactory._hook_registry[custom_type] = CustomHook
            
            # Test that it's now supported
            assert custom_type in [ht.value if hasattr(ht, 'value') else str(ht) 
                                 for ht in DeviceHookFactory.get_supported_types()]
        finally:
            # Restore original registry
            DeviceHookFactory._hook_registry = original_registry


class TestRESTAPIHook:
    """Test RESTAPIHook functionality."""
    
    @pytest.fixture
    def rest_hook(self):
        """Create a RESTAPIHook instance for testing."""
        return RESTAPIHook()
    
    @pytest.fixture
    def device_config(self):
        """Create a DeviceConfig for testing."""
        return DeviceConfig(
            type="http",
            endpoint="http://192.168.1.1",
            authentication={"username": "admin", "password": "password"}
        )
    
    @pytest.mark.asyncio
    async def test_connect_success(self, rest_hook, device_config):
        """Test successful connection to REST API."""
        result = await rest_hook.connect(device_config)
        
        assert result is True
        assert rest_hook.connected is True
        assert rest_hook.base_url == device_config.endpoint
    
    @pytest.mark.asyncio
    async def test_disconnect(self, rest_hook, device_config):
        """Test disconnection from REST API."""
        # First connect
        await rest_hook.connect(device_config)
        assert rest_hook.connected is True
        
        # Then disconnect
        await rest_hook.disconnect()
        assert rest_hook.connected is False
        assert rest_hook.base_url is None
    
    @pytest.mark.asyncio
    async def test_get_parameter_names_when_connected(self, rest_hook, device_config):
        """Test getting parameter names when connected."""
        await rest_hook.connect(device_config)
        
        result = await rest_hook.get_parameter_names("Device.WiFi.")
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(param, str) for param in result)
    
    @pytest.mark.asyncio
    async def test_get_parameter_names_when_not_connected(self, rest_hook):
        """Test getting parameter names when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await rest_hook.get_parameter_names()
    
    @pytest.mark.asyncio
    async def test_get_parameter_values_when_connected(self, rest_hook, device_config):
        """Test getting parameter values when connected."""
        await rest_hook.connect(device_config)
        
        paths = ["Device.WiFi.Radio.1.Channel", "Device.WiFi.Radio.1.SSID"]
        result = await rest_hook.get_parameter_values(paths)
        
        assert isinstance(result, dict)
        assert len(result) == len(paths)
        for path in paths:
            assert path in result
    
    @pytest.mark.asyncio
    async def test_get_parameter_values_when_not_connected(self, rest_hook):
        """Test getting parameter values when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await rest_hook.get_parameter_values(["Device.WiFi.Radio.1.Channel"])
    
    @pytest.mark.asyncio
    async def test_get_parameter_attributes_when_connected(self, rest_hook, device_config):
        """Test getting parameter attributes when connected."""
        await rest_hook.connect(device_config)
        
        paths = ["Device.WiFi.Radio.1.Channel"]
        result = await rest_hook.get_parameter_attributes(paths)
        
        assert isinstance(result, dict)
        assert len(result) == len(paths)
        for path in paths:
            assert path in result
            assert isinstance(result[path], dict)
            assert "type" in result[path]
            assert "access" in result[path]
    
    @pytest.mark.asyncio
    async def test_get_parameter_attributes_when_not_connected(self, rest_hook):
        """Test getting parameter attributes when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await rest_hook.get_parameter_attributes(["Device.WiFi.Radio.1.Channel"])
    
    @pytest.mark.asyncio
    async def test_set_parameter_values_when_connected(self, rest_hook, device_config):
        """Test setting parameter values when connected."""
        await rest_hook.connect(device_config)
        
        values = {"Device.WiFi.Radio.1.Channel": 6}
        result = await rest_hook.set_parameter_values(values)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_set_parameter_values_when_not_connected(self, rest_hook):
        """Test setting parameter values when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await rest_hook.set_parameter_values({"Device.WiFi.Radio.1.Channel": 6})
    
    @pytest.mark.asyncio
    async def test_subscribe_to_event_when_connected(self, rest_hook, device_config):
        """Test subscribing to event when connected."""
        await rest_hook.connect(device_config)
        
        result = await rest_hook.subscribe_to_event("Device.WiFi.AccessPoint.1.AssociatedDevice.")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_subscribe_to_event_when_not_connected(self, rest_hook):
        """Test subscribing to event when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await rest_hook.subscribe_to_event("Device.WiFi.AccessPoint.1.AssociatedDevice.")
    
    @pytest.mark.asyncio
    async def test_call_function_when_connected(self, rest_hook, device_config):
        """Test calling function when connected."""
        await rest_hook.connect(device_config)
        
        result = await rest_hook.call_function(
            "Device.WiFi.AccessPoint.1.AC.Stats.Reset()",
            {"ResetType": "All"}
        )
        
        assert isinstance(result, dict)
        assert "result" in result
    
    @pytest.mark.asyncio
    async def test_call_function_when_not_connected(self, rest_hook):
        """Test calling function when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await rest_hook.call_function("Device.WiFi.AccessPoint.1.AC.Stats.Reset()", {})


class TestCWMPHook:
    """Test CWMPHook functionality."""
    
    @pytest.fixture
    def cwmp_hook(self):
        """Create a CWMPHook instance for testing."""
        return CWMPHook()
    
    @pytest.fixture
    def device_config(self):
        """Create a DeviceConfig for testing."""
        return DeviceConfig(
            type="cwmp",
            endpoint="http://device.example.com:7547",
            authentication={"username": "admin", "password": "password"}
        )
    
    @pytest.mark.asyncio
    async def test_connect_success(self, cwmp_hook, device_config):
        """Test successful connection to CWMP device."""
        result = await cwmp_hook.connect(device_config)
        
        assert result is True
        assert cwmp_hook.connected is True
        assert cwmp_hook.connection_url == device_config.endpoint
    
    @pytest.mark.asyncio
    async def test_disconnect(self, cwmp_hook, device_config):
        """Test disconnection from CWMP device."""
        # First connect
        await cwmp_hook.connect(device_config)
        assert cwmp_hook.connected is True
        
        # Then disconnect
        await cwmp_hook.disconnect()
        assert cwmp_hook.connected is False
        assert cwmp_hook.connection_url is None
    
    @pytest.mark.asyncio
    async def test_get_parameter_names_when_connected(self, cwmp_hook, device_config):
        """Test getting parameter names when connected."""
        await cwmp_hook.connect(device_config)
        
        result = await cwmp_hook.get_parameter_names("Device.DeviceInfo.")
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(param, str) for param in result)
    
    @pytest.mark.asyncio
    async def test_get_parameter_names_when_not_connected(self, cwmp_hook):
        """Test getting parameter names when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await cwmp_hook.get_parameter_names()
    
    @pytest.mark.asyncio
    async def test_get_parameter_values_when_connected(self, cwmp_hook, device_config):
        """Test getting parameter values when connected."""
        await cwmp_hook.connect(device_config)
        
        paths = ["Device.DeviceInfo.Manufacturer", "Device.DeviceInfo.ModelName"]
        result = await cwmp_hook.get_parameter_values(paths)
        
        assert isinstance(result, dict)
        assert len(result) == len(paths)
        for path in paths:
            assert path in result
    
    @pytest.mark.asyncio
    async def test_get_parameter_values_when_not_connected(self, cwmp_hook):
        """Test getting parameter values when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await cwmp_hook.get_parameter_values(["Device.DeviceInfo.Manufacturer"])
    
    @pytest.mark.asyncio
    async def test_get_parameter_attributes_when_connected(self, cwmp_hook, device_config):
        """Test getting parameter attributes when connected."""
        await cwmp_hook.connect(device_config)
        
        paths = ["Device.DeviceInfo.Manufacturer"]
        result = await cwmp_hook.get_parameter_attributes(paths)
        
        assert isinstance(result, dict)
        assert len(result) == len(paths)
        for path in paths:
            assert path in result
            assert isinstance(result[path], dict)
            assert "type" in result[path]
            assert "access" in result[path]
    
    @pytest.mark.asyncio
    async def test_get_parameter_attributes_when_not_connected(self, cwmp_hook):
        """Test getting parameter attributes when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await cwmp_hook.get_parameter_attributes(["Device.DeviceInfo.Manufacturer"])
    
    @pytest.mark.asyncio
    async def test_set_parameter_values_when_connected(self, cwmp_hook, device_config):
        """Test setting parameter values when connected."""
        await cwmp_hook.connect(device_config)
        
        values = {"Device.WiFi.Radio.1.Channel": 11}
        result = await cwmp_hook.set_parameter_values(values)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_set_parameter_values_when_not_connected(self, cwmp_hook):
        """Test setting parameter values when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await cwmp_hook.set_parameter_values({"Device.WiFi.Radio.1.Channel": 11})
    
    @pytest.mark.asyncio
    async def test_subscribe_to_event_when_connected(self, cwmp_hook, device_config):
        """Test subscribing to event when connected."""
        await cwmp_hook.connect(device_config)
        
        result = await cwmp_hook.subscribe_to_event("Device.WiFi.AccessPoint.1.AssociatedDevice.")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_subscribe_to_event_when_not_connected(self, cwmp_hook):
        """Test subscribing to event when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await cwmp_hook.subscribe_to_event("Device.WiFi.AccessPoint.1.AssociatedDevice.")
    
    @pytest.mark.asyncio
    async def test_call_function_when_connected(self, cwmp_hook, device_config):
        """Test calling function when connected."""
        await cwmp_hook.connect(device_config)
        
        result = await cwmp_hook.call_function(
            "Device.WiFi.AccessPoint.1.AC.Stats.Reset()",
            {"ResetType": "All"}
        )
        
        assert isinstance(result, dict)
        assert "result" in result
    
    @pytest.mark.asyncio
    async def test_call_function_when_not_connected(self, cwmp_hook):
        """Test calling function when not connected raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected to device"):
            await cwmp_hook.call_function("Device.WiFi.AccessPoint.1.AC.Stats.Reset()", {})


class TestHookIntegration:
    """Integration tests for hook system."""
    
    @pytest.mark.asyncio
    async def test_hook_lifecycle_rest_api(self):
        """Test complete lifecycle of REST API hook."""
        hook = DeviceHookFactory.create_hook(HookType.REST_API)
        config = DeviceConfig(
            type="http",
            endpoint="http://192.168.1.1",
            authentication={"username": "admin", "password": "password"}
        )
        
        # Connect
        assert await hook.connect(config) is True
        
        # Perform operations
        params = await hook.get_parameter_names("Device.WiFi.")
        assert len(params) > 0
        
        values = await hook.get_parameter_values(params[:2])
        assert len(values) == 2
        
        attributes = await hook.get_parameter_attributes(params[:1])
        assert len(attributes) == 1
        
        # Disconnect
        await hook.disconnect()
    
    @pytest.mark.asyncio
    async def test_hook_lifecycle_cwmp(self):
        """Test complete lifecycle of CWMP hook."""
        hook = DeviceHookFactory.create_hook(HookType.CWMP)
        config = DeviceConfig(
            type="cwmp",
            endpoint="http://device.example.com:7547",
            authentication={"username": "admin", "password": "password"}
        )
        
        # Connect
        assert await hook.connect(config) is True
        
        # Perform operations
        params = await hook.get_parameter_names("Device.DeviceInfo.")
        assert len(params) > 0
        
        values = await hook.get_parameter_values(params[:2])
        assert len(values) == 2
        
        attributes = await hook.get_parameter_attributes(params[:1])
        assert len(attributes) == 1
        
        # Disconnect
        await hook.disconnect()