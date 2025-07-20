"""Tests for CWMP extractor implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, List, Any

from tr181_comparator.extractors import CWMPExtractor, ValidationResult, SourceInfo
from tr181_comparator.hooks import CWMPHook, DeviceConfig
from tr181_comparator.models import TR181Node, AccessLevel
from tr181_comparator.errors import ConnectionError, ValidationError


class TestCWMPExtractor:
    """Test CWMPExtractor functionality."""
    
    @pytest.fixture
    def device_config(self):
        """Create a DeviceConfig for testing."""
        return DeviceConfig(
            type="cwmp",
            endpoint="http://acs.example.com:7547",
            authentication={"username": "admin", "password": "password"},
            timeout=30,
            retry_count=3
        )
    
    @pytest.fixture
    def mock_cwmp_hook(self):
        """Create a mock CWMP hook for testing."""
        hook = AsyncMock(spec=CWMPHook)
        hook.connect.return_value = True
        hook.disconnect.return_value = None
        return hook
    
    @pytest.fixture
    def cwmp_extractor(self, mock_cwmp_hook, device_config):
        """Create a CWMPExtractor instance for testing."""
        return CWMPExtractor(mock_cwmp_hook, device_config)
    
    @pytest.fixture
    def sample_parameter_names(self):
        """Sample parameter names returned by CWMP GetParameterNames."""
        return [
            "Device.",
            "Device.DeviceInfo.",
            "Device.DeviceInfo.Manufacturer",
            "Device.DeviceInfo.ModelName",
            "Device.DeviceInfo.SoftwareVersion",
            "Device.WiFi.",
            "Device.WiFi.RadioNumberOfEntries",
            "Device.WiFi.Radio.",
            "Device.WiFi.Radio.1.",
            "Device.WiFi.Radio.1.Enable",
            "Device.WiFi.Radio.1.Channel",
            "Device.WiFi.Radio.1.SSID",
            "Device.WiFi.AccessPoint.",
            "Device.WiFi.AccessPoint.1.",
            "Device.WiFi.AccessPoint.1.Enable",
            "Device.WiFi.AccessPoint.1.SSID"
        ]
    
    @pytest.fixture
    def sample_parameter_attributes(self):
        """Sample parameter attributes returned by CWMP GetParameterAttributes."""
        return {
            "Device.DeviceInfo.Manufacturer": {
                "type": "xsd:string",
                "access": "read-only",
                "notification": "off"
            },
            "Device.DeviceInfo.ModelName": {
                "type": "xsd:string", 
                "access": "read-only",
                "notification": "off"
            },
            "Device.DeviceInfo.SoftwareVersion": {
                "type": "xsd:string",
                "access": "read-only", 
                "notification": "passive"
            },
            "Device.WiFi.RadioNumberOfEntries": {
                "type": "xsd:int",
                "access": "read-only",
                "notification": "off"
            },
            "Device.WiFi.Radio.1.Enable": {
                "type": "xsd:boolean",
                "access": "read-write",
                "notification": "passive"
            },
            "Device.WiFi.Radio.1.Channel": {
                "type": "xsd:int",
                "access": "read-write",
                "notification": "active"
            },
            "Device.WiFi.Radio.1.SSID": {
                "type": "xsd:string",
                "access": "read-write",
                "notification": "passive"
            },
            "Device.WiFi.AccessPoint.1.Enable": {
                "type": "xsd:boolean",
                "access": "read-write",
                "notification": "passive"
            },
            "Device.WiFi.AccessPoint.1.SSID": {
                "type": "xsd:string",
                "access": "read-write",
                "notification": "passive"
            }
        }
    
    @pytest.fixture
    def sample_parameter_values(self):
        """Sample parameter values returned by CWMP GetParameterValues."""
        return {
            "Device.DeviceInfo.Manufacturer": "ExampleCorp",
            "Device.DeviceInfo.ModelName": "TR181-Device-v1.0",
            "Device.DeviceInfo.SoftwareVersion": "1.2.3",
            "Device.WiFi.RadioNumberOfEntries": "1",
            "Device.WiFi.Radio.1.Enable": "true",
            "Device.WiFi.Radio.1.Channel": "11",
            "Device.WiFi.Radio.1.SSID": "TestNetwork",
            "Device.WiFi.AccessPoint.1.Enable": "true",
            "Device.WiFi.AccessPoint.1.SSID": "TestAP"
        }
    
    def setup_mock_cwmp_responses(self, mock_hook, parameter_names, parameter_attributes, parameter_values):
        """Setup mock CWMP hook responses for testing."""
        # Mock parameter discovery
        def mock_get_parameter_names(path_prefix="Device."):
            # Return parameters that start with the prefix
            matching_params = [p for p in parameter_names if p.startswith(path_prefix) and p != path_prefix]
            # For recursive discovery, return immediate children
            if path_prefix == "Device.":
                return ["Device.DeviceInfo.", "Device.WiFi."]
            elif path_prefix == "Device.DeviceInfo.":
                return [p for p in parameter_names if p.startswith(path_prefix) and p.count('.') == path_prefix.count('.')]
            elif path_prefix == "Device.WiFi.":
                return ["Device.WiFi.RadioNumberOfEntries", "Device.WiFi.Radio.", "Device.WiFi.AccessPoint."]
            elif path_prefix == "Device.WiFi.Radio.":
                return ["Device.WiFi.Radio.1."]
            elif path_prefix == "Device.WiFi.Radio.1.":
                return [p for p in parameter_names if p.startswith(path_prefix) and not p.endswith('.')]
            elif path_prefix == "Device.WiFi.AccessPoint.":
                return ["Device.WiFi.AccessPoint.1."]
            elif path_prefix == "Device.WiFi.AccessPoint.1.":
                return [p for p in parameter_names if p.startswith(path_prefix) and not p.endswith('.')]
            else:
                return []
        
        mock_hook.get_parameter_names.side_effect = mock_get_parameter_names
        
        # Mock parameter attributes
        def mock_get_parameter_attributes(paths):
            return {path: parameter_attributes.get(path, {"type": "string", "access": "read-only"}) for path in paths}
        
        mock_hook.get_parameter_attributes.side_effect = mock_get_parameter_attributes
        
        # Mock parameter values
        def mock_get_parameter_values(paths):
            return {path: parameter_values.get(path) for path in paths}
        
        mock_hook.get_parameter_values.side_effect = mock_get_parameter_values
    
    @pytest.mark.asyncio
    async def test_extract_success(self, cwmp_extractor, mock_cwmp_hook, sample_parameter_names, 
                                 sample_parameter_attributes, sample_parameter_values):
        """Test successful extraction of TR181 nodes from CWMP source."""
        # Setup mock responses
        self.setup_mock_cwmp_responses(
            mock_cwmp_hook, sample_parameter_names, 
            sample_parameter_attributes, sample_parameter_values
        )
        
        # Perform extraction
        nodes = await cwmp_extractor.extract()
        
        # Verify results
        assert isinstance(nodes, list)
        assert len(nodes) > 0
        
        # Check that we have the expected nodes
        node_paths = {node.path for node in nodes}
        expected_paths = {
            "Device.DeviceInfo.Manufacturer",
            "Device.DeviceInfo.ModelName", 
            "Device.DeviceInfo.SoftwareVersion",
            "Device.WiFi.RadioNumberOfEntries",
            "Device.WiFi.Radio.1.Enable",
            "Device.WiFi.Radio.1.Channel",
            "Device.WiFi.Radio.1.SSID",
            "Device.WiFi.AccessPoint.1.Enable",
            "Device.WiFi.AccessPoint.1.SSID"
        }
        
        # Check that all expected parameter nodes are present
        for expected_path in expected_paths:
            assert expected_path in node_paths, f"Expected parameter {expected_path} not found in extracted nodes"
        
        # Verify node properties
        manufacturer_node = next(node for node in nodes if node.path == "Device.DeviceInfo.Manufacturer")
        assert manufacturer_node.name == "Manufacturer"
        assert manufacturer_node.data_type == "string"
        assert manufacturer_node.access == AccessLevel.READ_ONLY
        assert manufacturer_node.value == "ExampleCorp"
        assert manufacturer_node.is_custom is False
        
        channel_node = next(node for node in nodes if node.path == "Device.WiFi.Radio.1.Channel")
        assert channel_node.name == "Channel"
        assert channel_node.data_type == "int"
        assert channel_node.access == AccessLevel.READ_WRITE
        assert channel_node.value == "11"
        
        # Verify CWMP hook was called correctly
        mock_cwmp_hook.connect.assert_called_once()
        assert mock_cwmp_hook.get_parameter_names.call_count > 0
        assert mock_cwmp_hook.get_parameter_attributes.call_count > 0
        assert mock_cwmp_hook.get_parameter_values.call_count > 0
    
    @pytest.mark.asyncio
    async def test_extract_with_hierarchical_structure(self, cwmp_extractor, mock_cwmp_hook, 
                                                     sample_parameter_names, sample_parameter_attributes, 
                                                     sample_parameter_values):
        """Test that extracted nodes have proper hierarchical parent-child relationships."""
        # Setup mock responses
        self.setup_mock_cwmp_responses(
            mock_cwmp_hook, sample_parameter_names,
            sample_parameter_attributes, sample_parameter_values
        )
        
        # Perform extraction
        nodes = await cwmp_extractor.extract()
        
        # Build lookup map
        node_map = {node.path: node for node in nodes}
        
        # Check parent-child relationships for object nodes
        if "Device.WiFi.Radio.1." in node_map:
            radio_object = node_map["Device.WiFi.Radio.1."]
            assert radio_object.is_object is True
            
            # Check that radio parameters have correct parent
            if "Device.WiFi.Radio.1.Channel" in node_map:
                channel_node = node_map["Device.WiFi.Radio.1.Channel"]
                assert channel_node.parent == "Device.WiFi.Radio.1."
                
                # Check that parent has this child
                assert "Device.WiFi.Radio.1.Channel" in radio_object.children
    
    @pytest.mark.asyncio
    async def test_extract_connection_failure(self, cwmp_extractor, mock_cwmp_hook):
        """Test extraction failure when CWMP connection fails."""
        # Mock connection failure
        mock_cwmp_hook.connect.return_value = False
        
        # Extraction should raise ConnectionError
        with pytest.raises(ConnectionError, match="Failed to establish CWMP connection"):
            await cwmp_extractor.extract()
    
    @pytest.mark.asyncio
    async def test_extract_parameter_discovery_failure(self, cwmp_extractor, mock_cwmp_hook):
        """Test extraction when parameter discovery fails."""
        # Mock successful connection but failed parameter discovery
        mock_cwmp_hook.connect.return_value = True
        mock_cwmp_hook.get_parameter_names.side_effect = Exception("CWMP operation failed")
        
        # Extraction should raise ConnectionError
        with pytest.raises(ConnectionError, match="Failed to discover parameters from CWMP source"):
            await cwmp_extractor.extract()
    
    @pytest.mark.asyncio
    async def test_extract_empty_parameter_list(self, cwmp_extractor, mock_cwmp_hook):
        """Test extraction when no parameters are discovered."""
        # Mock successful connection but empty parameter list
        mock_cwmp_hook.connect.return_value = True
        mock_cwmp_hook.get_parameter_names.return_value = []
        
        # Extraction should return empty list
        nodes = await cwmp_extractor.extract()
        assert nodes == []
    
    @pytest.mark.asyncio
    async def test_extract_partial_failure_graceful_degradation(self, cwmp_extractor, mock_cwmp_hook,
                                                              sample_parameter_names, sample_parameter_attributes):
        """Test graceful degradation when some parameter operations fail."""
        # Setup partial mock responses
        mock_cwmp_hook.connect.return_value = True
        
        # Mock parameter discovery success
        def mock_get_parameter_names(path_prefix="Device."):
            if path_prefix == "Device.":
                return ["Device.DeviceInfo.Manufacturer", "Device.WiFi.Radio.1.Channel"]
            return []
        
        mock_cwmp_hook.get_parameter_names.side_effect = mock_get_parameter_names
        
        # Mock partial attribute failure
        def mock_get_parameter_attributes(paths):
            if "Device.DeviceInfo.Manufacturer" in paths:
                return {"Device.DeviceInfo.Manufacturer": sample_parameter_attributes["Device.DeviceInfo.Manufacturer"]}
            else:
                raise Exception("Attribute retrieval failed")
        
        mock_cwmp_hook.get_parameter_attributes.side_effect = mock_get_parameter_attributes
        
        # Mock partial value failure
        def mock_get_parameter_values(paths):
            if "Device.DeviceInfo.Manufacturer" in paths:
                return {"Device.DeviceInfo.Manufacturer": "ExampleCorp"}
            else:
                raise Exception("Value retrieval failed")
        
        mock_cwmp_hook.get_parameter_values.side_effect = mock_get_parameter_values
        
        # Extraction should succeed with partial data
        nodes = await cwmp_extractor.extract()
        assert len(nodes) > 0
        
        # Should have at least the successful parameter
        node_paths = {node.path for node in nodes}
        assert "Device.DeviceInfo.Manufacturer" in node_paths
    
    @pytest.mark.asyncio
    async def test_validate_success(self, cwmp_extractor, mock_cwmp_hook):
        """Test successful validation of CWMP source."""
        # Mock successful connection and basic operations
        mock_cwmp_hook.connect.return_value = True
        mock_cwmp_hook.get_parameter_names.return_value = ["Device.DeviceInfo.Manufacturer"]
        mock_cwmp_hook.get_parameter_values.return_value = {"Device.DeviceInfo.Manufacturer": "TestCorp"}
        
        # Perform validation
        result = await cwmp_extractor.validate()
        
        # Should be valid with warnings about successful operations
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("validation successful" in warning for warning in result.warnings)
        
        # Verify cleanup
        mock_cwmp_hook.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, cwmp_extractor, mock_cwmp_hook):
        """Test validation failure when CWMP connection fails."""
        # Mock connection failure
        mock_cwmp_hook.connect.return_value = False
        
        # Perform validation
        result = await cwmp_extractor.validate()
        
        # Should be invalid
        assert result.is_valid is False
        assert any("Failed to connect to CWMP source" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_operation_failure(self, cwmp_extractor, mock_cwmp_hook):
        """Test validation when CWMP operations fail."""
        # Mock successful connection but failed operations
        mock_cwmp_hook.connect.return_value = True
        mock_cwmp_hook.get_parameter_names.side_effect = Exception("CWMP operation failed")
        
        # Perform validation
        result = await cwmp_extractor.validate()
        
        # Should be invalid
        assert result.is_valid is False
        assert any("CWMP operation test failed" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_empty_source(self, cwmp_extractor, mock_cwmp_hook):
        """Test validation when CWMP source is empty."""
        # Mock successful connection but no parameters
        mock_cwmp_hook.connect.return_value = True
        mock_cwmp_hook.get_parameter_names.return_value = []
        
        # Perform validation
        result = await cwmp_extractor.validate()
        
        # Should be valid but with warning about empty source
        assert result.is_valid is True
        assert any("CWMP source may be empty" in warning for warning in result.warnings)
    
    def test_get_source_info(self, cwmp_extractor, device_config):
        """Test getting source information."""
        source_info = cwmp_extractor.get_source_info()
        
        assert isinstance(source_info, SourceInfo)
        assert source_info.type == "cwmp"
        assert source_info.identifier == device_config.endpoint
        assert isinstance(source_info.timestamp, datetime)
        assert source_info.metadata["device_type"] == device_config.type
        assert source_info.metadata["timeout"] == device_config.timeout
        assert source_info.metadata["retry_count"] == device_config.retry_count
    
    def test_map_cwmp_data_type(self, cwmp_extractor):
        """Test CWMP data type mapping."""
        # Test standard mappings
        assert cwmp_extractor._map_cwmp_data_type("xsd:string") == "string"
        assert cwmp_extractor._map_cwmp_data_type("xsd:int") == "int"
        assert cwmp_extractor._map_cwmp_data_type("xsd:boolean") == "boolean"
        assert cwmp_extractor._map_cwmp_data_type("xsd:dateTime") == "dateTime"
        assert cwmp_extractor._map_cwmp_data_type("xsd:base64Binary") == "base64"
        assert cwmp_extractor._map_cwmp_data_type("xsd:hexBinary") == "hexBinary"
        
        # Test alternative formats
        assert cwmp_extractor._map_cwmp_data_type("string") == "string"
        assert cwmp_extractor._map_cwmp_data_type("int") == "int"
        assert cwmp_extractor._map_cwmp_data_type("boolean") == "boolean"
        assert cwmp_extractor._map_cwmp_data_type("unsignedInt") == "int"
        assert cwmp_extractor._map_cwmp_data_type("long") == "int"
        
        # Test unknown type defaults to string
        assert cwmp_extractor._map_cwmp_data_type("unknown_type") == "string"
    
    @pytest.mark.asyncio
    async def test_context_manager(self, cwmp_extractor, mock_cwmp_hook):
        """Test CWMP extractor as async context manager."""
        mock_cwmp_hook.connect.return_value = True
        
        async with cwmp_extractor as extractor:
            assert extractor is cwmp_extractor
            assert extractor._connected is True
            mock_cwmp_hook.connect.assert_called_once()
        
        # Should disconnect on exit
        mock_cwmp_hook.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager_connection_failure(self, cwmp_extractor, mock_cwmp_hook):
        """Test context manager with connection failure."""
        mock_cwmp_hook.connect.return_value = False
        
        with pytest.raises(ConnectionError):
            async with cwmp_extractor:
                pass
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, cwmp_extractor, mock_cwmp_hook):
        """Test that large parameter lists are processed in batches."""
        # Create a large list of parameters
        large_parameter_list = [f"Device.Test.Param{i}" for i in range(150)]
        
        mock_cwmp_hook.connect.return_value = True
        mock_cwmp_hook.get_parameter_names.return_value = large_parameter_list
        
        # Mock batch responses
        def mock_get_attributes(paths):
            return {path: {"type": "string", "access": "read-only"} for path in paths}
        
        def mock_get_values(paths):
            return {path: f"value_{path.split('.')[-1]}" for path in paths}
        
        mock_cwmp_hook.get_parameter_attributes.side_effect = mock_get_attributes
        mock_cwmp_hook.get_parameter_values.side_effect = mock_get_values
        
        # Perform extraction
        nodes = await cwmp_extractor.extract()
        
        # Should have processed all parameters
        assert len(nodes) == 150
        
        # Should have made multiple batch calls (150 params / 50 batch size = 3 calls each)
        assert mock_cwmp_hook.get_parameter_attributes.call_count >= 3
        assert mock_cwmp_hook.get_parameter_values.call_count >= 3


class TestCWMPExtractorIntegration:
    """Integration tests for CWMP extractor with realistic scenarios."""
    
    @pytest.fixture
    def realistic_cwmp_data(self):
        """Realistic CWMP data structure for integration testing."""
        return {
            "parameter_names": [
                "Device.",
                "Device.DeviceInfo.",
                "Device.DeviceInfo.Manufacturer",
                "Device.DeviceInfo.ModelName",
                "Device.DeviceInfo.SoftwareVersion",
                "Device.DeviceInfo.HardwareVersion",
                "Device.ManagementServer.",
                "Device.ManagementServer.URL",
                "Device.ManagementServer.Username",
                "Device.ManagementServer.PeriodicInformEnable",
                "Device.ManagementServer.PeriodicInformInterval",
                "Device.WiFi.",
                "Device.WiFi.RadioNumberOfEntries",
                "Device.WiFi.SSIDNumberOfEntries",
                "Device.WiFi.Radio.",
                "Device.WiFi.Radio.1.",
                "Device.WiFi.Radio.1.Enable",
                "Device.WiFi.Radio.1.Status",
                "Device.WiFi.Radio.1.Name",
                "Device.WiFi.Radio.1.OperatingFrequencyBand",
                "Device.WiFi.Radio.1.Channel",
                "Device.WiFi.Radio.1.AutoChannelEnable",
                "Device.WiFi.Radio.1.TransmitPower",
                "Device.WiFi.SSID.",
                "Device.WiFi.SSID.1.",
                "Device.WiFi.SSID.1.Enable",
                "Device.WiFi.SSID.1.Status",
                "Device.WiFi.SSID.1.Name",
                "Device.WiFi.SSID.1.SSID",
                "Device.WiFi.AccessPoint.",
                "Device.WiFi.AccessPoint.1.",
                "Device.WiFi.AccessPoint.1.Enable",
                "Device.WiFi.AccessPoint.1.Status",
                "Device.WiFi.AccessPoint.1.SSIDReference"
            ],
            "parameter_attributes": {
                "Device.DeviceInfo.Manufacturer": {"type": "xsd:string", "access": "read-only"},
                "Device.DeviceInfo.ModelName": {"type": "xsd:string", "access": "read-only"},
                "Device.DeviceInfo.SoftwareVersion": {"type": "xsd:string", "access": "read-only"},
                "Device.DeviceInfo.HardwareVersion": {"type": "xsd:string", "access": "read-only"},
                "Device.ManagementServer.URL": {"type": "xsd:string", "access": "read-write"},
                "Device.ManagementServer.Username": {"type": "xsd:string", "access": "read-write"},
                "Device.ManagementServer.PeriodicInformEnable": {"type": "xsd:boolean", "access": "read-write"},
                "Device.ManagementServer.PeriodicInformInterval": {"type": "xsd:int", "access": "read-write"},
                "Device.WiFi.RadioNumberOfEntries": {"type": "xsd:int", "access": "read-only"},
                "Device.WiFi.SSIDNumberOfEntries": {"type": "xsd:int", "access": "read-only"},
                "Device.WiFi.Radio.1.Enable": {"type": "xsd:boolean", "access": "read-write"},
                "Device.WiFi.Radio.1.Status": {"type": "xsd:string", "access": "read-only"},
                "Device.WiFi.Radio.1.Name": {"type": "xsd:string", "access": "read-write"},
                "Device.WiFi.Radio.1.OperatingFrequencyBand": {"type": "xsd:string", "access": "read-write"},
                "Device.WiFi.Radio.1.Channel": {"type": "xsd:int", "access": "read-write"},
                "Device.WiFi.Radio.1.AutoChannelEnable": {"type": "xsd:boolean", "access": "read-write"},
                "Device.WiFi.Radio.1.TransmitPower": {"type": "xsd:int", "access": "read-write"},
                "Device.WiFi.SSID.1.Enable": {"type": "xsd:boolean", "access": "read-write"},
                "Device.WiFi.SSID.1.Status": {"type": "xsd:string", "access": "read-only"},
                "Device.WiFi.SSID.1.Name": {"type": "xsd:string", "access": "read-write"},
                "Device.WiFi.SSID.1.SSID": {"type": "xsd:string", "access": "read-write"},
                "Device.WiFi.AccessPoint.1.Enable": {"type": "xsd:boolean", "access": "read-write"},
                "Device.WiFi.AccessPoint.1.Status": {"type": "xsd:string", "access": "read-only"},
                "Device.WiFi.AccessPoint.1.SSIDReference": {"type": "xsd:string", "access": "read-write"}
            },
            "parameter_values": {
                "Device.DeviceInfo.Manufacturer": "TechCorp",
                "Device.DeviceInfo.ModelName": "WiFi-Router-Pro",
                "Device.DeviceInfo.SoftwareVersion": "2.1.4",
                "Device.DeviceInfo.HardwareVersion": "1.0",
                "Device.ManagementServer.URL": "http://acs.provider.com:7547/",
                "Device.ManagementServer.Username": "device123",
                "Device.ManagementServer.PeriodicInformEnable": "true",
                "Device.ManagementServer.PeriodicInformInterval": "3600",
                "Device.WiFi.RadioNumberOfEntries": "1",
                "Device.WiFi.SSIDNumberOfEntries": "1",
                "Device.WiFi.Radio.1.Enable": "true",
                "Device.WiFi.Radio.1.Status": "Up",
                "Device.WiFi.Radio.1.Name": "wlan0",
                "Device.WiFi.Radio.1.OperatingFrequencyBand": "2.4GHz",
                "Device.WiFi.Radio.1.Channel": "6",
                "Device.WiFi.Radio.1.AutoChannelEnable": "false",
                "Device.WiFi.Radio.1.TransmitPower": "100",
                "Device.WiFi.SSID.1.Enable": "true",
                "Device.WiFi.SSID.1.Status": "Enabled",
                "Device.WiFi.SSID.1.Name": "Primary",
                "Device.WiFi.SSID.1.SSID": "MyHomeNetwork",
                "Device.WiFi.AccessPoint.1.Enable": "true",
                "Device.WiFi.AccessPoint.1.Status": "Enabled",
                "Device.WiFi.AccessPoint.1.SSIDReference": "Device.WiFi.SSID.1."
            }
        }
    
    @pytest.mark.asyncio
    async def test_realistic_cwmp_extraction(self, realistic_cwmp_data):
        """Test extraction with realistic CWMP device data."""
        # Create mock hook with realistic data
        mock_hook = AsyncMock(spec=CWMPHook)
        mock_hook.connect.return_value = True
        
        # Setup realistic parameter discovery
        def mock_get_parameter_names(path_prefix="Device."):
            params = realistic_cwmp_data["parameter_names"]
            if path_prefix == "Device.":
                return ["Device.DeviceInfo.", "Device.ManagementServer.", "Device.WiFi."]
            elif path_prefix == "Device.DeviceInfo.":
                return [p for p in params if p.startswith(path_prefix) and not p.endswith('.')]
            elif path_prefix == "Device.ManagementServer.":
                return [p for p in params if p.startswith(path_prefix) and not p.endswith('.')]
            elif path_prefix == "Device.WiFi.":
                wifi_params = [p for p in params if p.startswith(path_prefix) and p.count('.') == 3]
                return wifi_params + ["Device.WiFi.Radio.", "Device.WiFi.SSID.", "Device.WiFi.AccessPoint."]
            elif path_prefix == "Device.WiFi.Radio.":
                return ["Device.WiFi.Radio.1."]
            elif path_prefix == "Device.WiFi.Radio.1.":
                return [p for p in params if p.startswith(path_prefix) and not p.endswith('.')]
            elif path_prefix == "Device.WiFi.SSID.":
                return ["Device.WiFi.SSID.1."]
            elif path_prefix == "Device.WiFi.SSID.1.":
                return [p for p in params if p.startswith(path_prefix) and not p.endswith('.')]
            elif path_prefix == "Device.WiFi.AccessPoint.":
                return ["Device.WiFi.AccessPoint.1."]
            elif path_prefix == "Device.WiFi.AccessPoint.1.":
                return [p for p in params if p.startswith(path_prefix) and not p.endswith('.')]
            return []
        
        mock_hook.get_parameter_names.side_effect = mock_get_parameter_names
        
        # Setup attribute and value responses
        mock_hook.get_parameter_attributes.side_effect = lambda paths: {
            path: realistic_cwmp_data["parameter_attributes"].get(path, {"type": "string", "access": "read-only"})
            for path in paths
        }
        mock_hook.get_parameter_values.side_effect = lambda paths: {
            path: realistic_cwmp_data["parameter_values"].get(path) for path in paths
        }
        
        # Create extractor and perform extraction
        device_config = DeviceConfig(
            type="cwmp",
            endpoint="http://device.example.com:7547",
            authentication={"username": "admin", "password": "password"}
        )
        extractor = CWMPExtractor(mock_hook, device_config)
        
        nodes = await extractor.extract()
        
        # Verify comprehensive extraction
        assert len(nodes) > 20  # Should have extracted many parameters
        
        # Check specific nodes exist with correct properties
        node_map = {node.path: node for node in nodes}
        
        # Device info nodes
        assert "Device.DeviceInfo.Manufacturer" in node_map
        manufacturer = node_map["Device.DeviceInfo.Manufacturer"]
        assert manufacturer.value == "TechCorp"
        assert manufacturer.access == AccessLevel.READ_ONLY
        assert manufacturer.data_type == "string"
        
        # Management server nodes
        assert "Device.ManagementServer.PeriodicInformInterval" in node_map
        interval = node_map["Device.ManagementServer.PeriodicInformInterval"]
        assert interval.value == "3600"
        assert interval.access == AccessLevel.READ_WRITE
        assert interval.data_type == "int"
        
        # WiFi nodes
        assert "Device.WiFi.Radio.1.Channel" in node_map
        channel = node_map["Device.WiFi.Radio.1.Channel"]
        assert channel.value == "6"
        assert channel.access == AccessLevel.READ_WRITE
        assert channel.data_type == "int"
        
        # Boolean nodes
        assert "Device.WiFi.Radio.1.Enable" in node_map
        enable = node_map["Device.WiFi.Radio.1.Enable"]
        assert enable.value == "true"
        assert enable.access == AccessLevel.READ_WRITE
        assert enable.data_type == "boolean"
        
        # Verify hierarchical structure
        if "Device.WiFi.Radio.1." in node_map:
            radio_obj = node_map["Device.WiFi.Radio.1."]
            assert radio_obj.is_object is True
            assert "Device.WiFi.Radio.1.Channel" in radio_obj.children
            assert channel.parent == "Device.WiFi.Radio.1."
    
    @pytest.mark.asyncio
    async def test_cwmp_simulator_integration(self):
        """Test integration with a simulated CWMP device response."""
        # This test simulates a more realistic CWMP interaction pattern
        
        class CWMPSimulator:
            """Simulates CWMP device responses."""
            
            def __init__(self):
                self.connected = False
                self.parameters = {
                    "Device.": ["Device.DeviceInfo.", "Device.WiFi."],
                    "Device.DeviceInfo.": [
                        "Device.DeviceInfo.Manufacturer",
                        "Device.DeviceInfo.ModelName",
                        "Device.DeviceInfo.SerialNumber"
                    ],
                    "Device.WiFi.": [
                        "Device.WiFi.RadioNumberOfEntries",
                        "Device.WiFi.Radio."
                    ],
                    "Device.WiFi.Radio.": ["Device.WiFi.Radio.1."],
                    "Device.WiFi.Radio.1.": [
                        "Device.WiFi.Radio.1.Enable",
                        "Device.WiFi.Radio.1.Channel",
                        "Device.WiFi.Radio.1.SSID"
                    ]
                }
                
                self.attributes = {
                    "Device.DeviceInfo.Manufacturer": {"type": "xsd:string", "access": "read-only"},
                    "Device.DeviceInfo.ModelName": {"type": "xsd:string", "access": "read-only"},
                    "Device.DeviceInfo.SerialNumber": {"type": "xsd:string", "access": "read-only"},
                    "Device.WiFi.RadioNumberOfEntries": {"type": "xsd:int", "access": "read-only"},
                    "Device.WiFi.Radio.1.Enable": {"type": "xsd:boolean", "access": "read-write"},
                    "Device.WiFi.Radio.1.Channel": {"type": "xsd:int", "access": "read-write"},
                    "Device.WiFi.Radio.1.SSID": {"type": "xsd:string", "access": "read-write"}
                }
                
                self.values = {
                    "Device.DeviceInfo.Manufacturer": "SimulatedCorp",
                    "Device.DeviceInfo.ModelName": "TestDevice-1000",
                    "Device.DeviceInfo.SerialNumber": "SN123456789",
                    "Device.WiFi.RadioNumberOfEntries": "1",
                    "Device.WiFi.Radio.1.Enable": "true",
                    "Device.WiFi.Radio.1.Channel": "11",
                    "Device.WiFi.Radio.1.SSID": "TestNetwork"
                }
        
        # Create simulator and mock hook
        simulator = CWMPSimulator()
        mock_hook = AsyncMock(spec=CWMPHook)
        
        # Wire up simulator to mock hook
        mock_hook.connect.return_value = True
        mock_hook.get_parameter_names.side_effect = lambda path: simulator.parameters.get(path, [])
        mock_hook.get_parameter_attributes.side_effect = lambda paths: {
            path: simulator.attributes.get(path, {"type": "string", "access": "read-only"})
            for path in paths
        }
        mock_hook.get_parameter_values.side_effect = lambda paths: {
            path: simulator.values.get(path) for path in paths
        }
        
        # Create extractor and test
        device_config = DeviceConfig(
            type="cwmp",
            endpoint="http://simulator.test:7547",
            authentication={"username": "test", "password": "test"}
        )
        extractor = CWMPExtractor(mock_hook, device_config)
        
        # Test validation
        validation_result = await extractor.validate()
        assert validation_result.is_valid is True
        
        # Test extraction
        nodes = await extractor.extract()
        assert len(nodes) > 0
        
        # Verify specific simulated data
        node_map = {node.path: node for node in nodes}
        assert "Device.DeviceInfo.SerialNumber" in node_map
        serial_node = node_map["Device.DeviceInfo.SerialNumber"]
        assert serial_node.value == "SN123456789"
        assert serial_node.access == AccessLevel.READ_ONLY
        
        # Test source info
        source_info = extractor.get_source_info()
        assert source_info.type == "cwmp"
        assert source_info.identifier == "http://simulator.test:7547"