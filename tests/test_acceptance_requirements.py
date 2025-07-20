"""Acceptance tests that validate all requirements from the requirements document.

This test suite systematically validates each requirement and acceptance criteria
to ensure the system meets all specified functionality.
"""

import pytest
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock

from tr181_comparator.models import (
    TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function
)
from tr181_comparator.main import TR181ComparatorApp
from tr181_comparator.config import SystemConfig, DeviceConfig, SubsetConfig, ExportConfig
from tr181_comparator.comparison import ComparisonEngine, EnhancedComparisonEngine
from tr181_comparator.extractors import SubsetManager, HookBasedDeviceExtractor
from tr181_comparator.hooks import DeviceHookFactory, HookType, DeviceConfig as HookDeviceConfig
from tr181_comparator.validation import TR181Validator
from tr181_comparator.errors import ConnectionError, ValidationError


class AcceptanceTestDataGenerator:
    """Generates test data for acceptance testing."""
    
    @staticmethod
    def create_cwmp_nodes() -> List[TR181Node]:
        """Create realistic CWMP TR181 nodes for testing."""
        return [
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="CWMP_Manufacturer",
                description="Device manufacturer from CWMP"
            ),
            TR181Node(
                path="Device.DeviceInfo.ModelName",
                name="ModelName",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="CWMP_Model_123",
                description="Device model from CWMP"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="WiFi radio enable from CWMP"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6,
                description="WiFi channel from CWMP",
                value_range=ValueRange(min_value=1, max_value=165)
            ),
            TR181Node(
                path="Device.WiFi.AccessPoint.1.SSID",
                name="SSID",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="CWMP_WiFi_Network",
                description="WiFi SSID from CWMP",
                value_range=ValueRange(max_length=32)
            ),
            TR181Node(
                path="Device.Ethernet.Interface.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="Ethernet interface enable from CWMP"
            ),
            TR181Node(
                path="Device.Ethernet.Interface.1.Status",
                name="Status",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="Up",
                description="Ethernet interface status from CWMP",
                value_range=ValueRange(allowed_values=["Up", "Down", "Unknown", "Dormant", "NotPresent", "LowerLayerDown", "Error"])
            )
        ]
    
    @staticmethod
    def create_custom_subset_nodes() -> List[TR181Node]:
        """Create custom subset nodes including standard and custom parameters."""
        return [
            # Standard TR181 nodes
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="Custom_Manufacturer",
                description="Device manufacturer in custom subset"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="WiFi radio enable in custom subset"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=11,
                description="WiFi channel in custom subset",
                value_range=ValueRange(min_value=1, max_value=165)
            ),
            # Custom nodes
            TR181Node(
                path="Device.Custom.VendorSpecific.Parameter1",
                name="Parameter1",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="custom_value_1",
                description="Custom vendor-specific parameter 1",
                is_custom=True
            ),
            TR181Node(
                path="Device.Custom.VendorSpecific.Parameter2",
                name="Parameter2",
                data_type="int",
                access=AccessLevel.READ_ONLY,
                value=42,
                description="Custom vendor-specific parameter 2",
                is_custom=True,
                value_range=ValueRange(min_value=0, max_value=100)
            )
        ]
    
    @staticmethod
    def create_device_implementation_nodes() -> List[TR181Node]:
        """Create device implementation nodes for testing."""
        return [
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="Device_Manufacturer",
                description="Device manufacturer from actual device"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=False,  # Different value
                description="WiFi radio enable from actual device"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=1,  # Different value
                description="WiFi channel from actual device",
                value_range=ValueRange(min_value=1, max_value=165)
            ),
            # Missing some parameters that are in subset
            # Extra parameter not in subset
            TR181Node(
                path="Device.Implementation.ExtraParameter",
                name="ExtraParameter",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="extra_implementation_value",
                description="Extra parameter in device implementation"
            )
        ]


class MockAcceptanceHook:
    """Mock hook for acceptance testing with realistic behavior."""
    
    def __init__(self, nodes: List[TR181Node], connection_should_fail: bool = False):
        self.nodes = nodes
        self.connection_should_fail = connection_should_fail
        self.connected = False
        self.connection_attempts = 0
    
    async def connect(self, config: HookDeviceConfig) -> bool:
        self.connection_attempts += 1
        if self.connection_should_fail:
            return False
        self.connected = True
        return True
    
    async def disconnect(self) -> None:
        self.connected = False
    
    async def get_parameter_names(self, path_prefix: str = "Device.") -> List[str]:
        if not self.connected:
            raise ConnectionError("Device not connected")
        return [node.path for node in self.nodes if node.path.startswith(path_prefix)]
    
    async def get_parameter_values(self, paths: List[str]) -> Dict[str, Any]:
        if not self.connected:
            raise ConnectionError("Device not connected")
        node_map = {node.path: node for node in self.nodes}
        return {path: node_map[path].value for path in paths if path in node_map}
    
    async def get_parameter_attributes(self, paths: List[str]) -> Dict[str, Dict[str, Any]]:
        if not self.connected:
            raise ConnectionError("Device not connected")
        node_map = {node.path: node for node in self.nodes}
        return {
            path: {
                "type": node_map[path].data_type,
                "access": node_map[path].access.value,
                "notification": "passive"
            }
            for path in paths if path in node_map
        }
    
    async def set_parameter_values(self, values: Dict[str, Any]) -> bool:
        return self.connected
    
    async def subscribe_to_event(self, event_path: str) -> bool:
        return self.connected
    
    async def call_function(self, function_path: str, input_params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.connected:
            raise ConnectionError("Device not connected")
        return {"result": "success", "output": {}}


class TestRequirement1_CWMPExtraction:
    """Test Requirement 1: Extract TR181 nodes from CWMP sources."""
    
    @pytest.mark.asyncio
    async def test_1_1_extract_tr181_nodes_with_hierarchical_structure(self):
        """
        WHEN a CWMP source is provided THEN the system SHALL extract all TR181 nodes 
        with their complete hierarchical structure
        """
        # Arrange
        cwmp_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()
        mock_hook = MockAcceptanceHook(cwmp_nodes)
        
        config = HookDeviceConfig(
            type="cwmp",
            endpoint="http://test-cwmp.example.com:7547",
            authentication={"username": "test", "password": "test"},
            timeout=30,
            retry_count=3
        )
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Act
        extracted_nodes = await extractor.extract()
        
        # Assert
        assert len(extracted_nodes) == len(cwmp_nodes)
        assert all(node.path.startswith("Device.") for node in extracted_nodes)
        
        # Verify hierarchical structure is preserved
        device_info_nodes = [n for n in extracted_nodes if n.path.startswith("Device.DeviceInfo")]
        wifi_nodes = [n for n in extracted_nodes if n.path.startswith("Device.WiFi")]
        ethernet_nodes = [n for n in extracted_nodes if n.path.startswith("Device.Ethernet")]
        
        assert len(device_info_nodes) >= 2  # Manufacturer, ModelName
        assert len(wifi_nodes) >= 3  # Radio.Enable, Radio.Channel, AccessPoint.SSID
        assert len(ethernet_nodes) >= 2  # Interface.Enable, Interface.Status
        
        print("✓ AC 1.1: Successfully extracted TR181 nodes with hierarchical structure")
    
    @pytest.mark.asyncio
    async def test_1_2_preserve_parameter_names_types_access(self):
        """
        WHEN TR181 nodes are extracted THEN the system SHALL preserve parameter names, 
        data types, and access permissions
        """
        # Arrange
        cwmp_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()
        mock_hook = MockAcceptanceHook(cwmp_nodes)
        
        config = HookDeviceConfig(
            type="cwmp",
            endpoint="http://test-cwmp.example.com:7547",
            authentication={"username": "test", "password": "test"},
            timeout=30,
            retry_count=3
        )
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Act
        extracted_nodes = await extractor.extract()
        
        # Assert - verify all required attributes are preserved
        for node in extracted_nodes:
            assert node.path is not None and len(node.path) > 0
            assert node.name is not None and len(node.name) > 0
            assert node.data_type is not None and len(node.data_type) > 0
            assert node.access is not None
            assert isinstance(node.access, AccessLevel)
        
        # Verify specific examples
        manufacturer_node = next((n for n in extracted_nodes if n.path == "Device.DeviceInfo.Manufacturer"), None)
        assert manufacturer_node is not None
        assert manufacturer_node.name == "Manufacturer"
        assert manufacturer_node.data_type == "string"
        assert manufacturer_node.access == AccessLevel.READ_ONLY
        
        channel_node = next((n for n in extracted_nodes if n.path == "Device.WiFi.Radio.1.Channel"), None)
        assert channel_node is not None
        assert channel_node.name == "Channel"
        assert channel_node.data_type == "int"
        assert channel_node.access == AccessLevel.READ_WRITE
        
        print("✓ AC 1.2: Successfully preserved parameter names, data types, and access permissions")
    
    @pytest.mark.asyncio
    async def test_1_3_provide_structured_representation(self):
        """
        WHEN extraction is complete THEN the system SHALL provide a structured 
        representation of all discovered nodes
        """
        # Arrange
        cwmp_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()
        mock_hook = MockAcceptanceHook(cwmp_nodes)
        
        config = HookDeviceConfig(
            type="cwmp",
            endpoint="http://test-cwmp.example.com:7547",
            authentication={"username": "test", "password": "test"},
            timeout=30,
            retry_count=3
        )
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Act
        extracted_nodes = await extractor.extract()
        source_info = extractor.get_source_info()
        
        # Assert - verify structured representation
        assert isinstance(extracted_nodes, list)
        assert all(isinstance(node, TR181Node) for node in extracted_nodes)
        
        # Verify source info provides metadata
        assert source_info.type == "device"
        assert source_info.identifier is not None
        assert source_info.timestamp is not None
        assert isinstance(source_info.metadata, dict)
        
        # Verify nodes can be organized by hierarchy
        node_hierarchy = {}
        for node in extracted_nodes:
            path_parts = node.path.split('.')
            current_level = node_hierarchy
            for part in path_parts[:-1]:  # Exclude the final parameter name
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
        
        # Should have Device as root with sub-hierarchies
        assert "Device" in node_hierarchy
        assert "DeviceInfo" in node_hierarchy["Device"]
        assert "WiFi" in node_hierarchy["Device"]
        assert "Ethernet" in node_hierarchy["Device"]
        
        print("✓ AC 1.3: Successfully provided structured representation of discovered nodes")
    
    @pytest.mark.asyncio
    async def test_1_4_report_invalid_cwmp_source_errors(self):
        """
        IF the CWMP source is invalid or inaccessible THEN the system SHALL 
        report specific error details
        """
        # Arrange - create hook that fails connection
        mock_hook = MockAcceptanceHook([], connection_should_fail=True)
        
        config = HookDeviceConfig(
            type="cwmp",
            endpoint="http://invalid-cwmp.example.com:7547",
            authentication={"username": "invalid", "password": "invalid"},
            timeout=5,  # Short timeout
            retry_count=1
        )
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            await extractor.extract()
        
        # Verify specific error details are provided
        error = exc_info.value
        assert "Failed to connect to device" in str(error)
        assert hasattr(error, 'error_id')
        assert hasattr(error, 'category')
        
        print("✓ AC 1.4: Successfully reported specific error details for invalid CWMP source")


class TestRequirement2_CustomSubsetDefinition:
    """Test Requirement 2: Define custom subset of TR181 nodes with additional custom nodes."""
    
    @pytest.mark.asyncio
    async def test_2_1_allow_selection_of_specific_tr181_nodes(self, tmp_path):
        """
        WHEN defining a custom subset THEN the system SHALL allow selection of 
        specific TR181 nodes from the standard
        """
        # Arrange
        standard_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()
        selected_nodes = [
            standard_nodes[0],  # Device.DeviceInfo.Manufacturer
            standard_nodes[2],  # Device.WiFi.Radio.1.Enable
            standard_nodes[3],  # Device.WiFi.Radio.1.Channel
        ]
        
        subset_file = tmp_path / "selected_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        
        # Act
        await subset_manager.save_subset(selected_nodes)
        loaded_nodes = await subset_manager.extract()
        
        # Assert
        assert len(loaded_nodes) == 3
        assert any(node.path == "Device.DeviceInfo.Manufacturer" for node in loaded_nodes)
        assert any(node.path == "Device.WiFi.Radio.1.Enable" for node in loaded_nodes)
        assert any(node.path == "Device.WiFi.Radio.1.Channel" for node in loaded_nodes)
        
        # Verify all selected nodes are standard TR181 nodes
        assert all(node.path.startswith("Device.") for node in loaded_nodes)
        assert all(not getattr(node, 'is_custom', False) for node in loaded_nodes)
        
        print("✓ AC 2.1: Successfully allowed selection of specific TR181 nodes from standard")
    
    @pytest.mark.asyncio
    async def test_2_2_accept_custom_node_definitions(self, tmp_path):
        """
        WHEN adding custom nodes THEN the system SHALL accept node definitions with 
        name, type, and access level specifications
        """
        # Arrange
        custom_nodes = [
            TR181Node(
                path="Device.Custom.VendorA.Parameter1",
                name="Parameter1",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="custom_string_value",
                description="Custom string parameter",
                is_custom=True
            ),
            TR181Node(
                path="Device.Custom.VendorA.Parameter2",
                name="Parameter2",
                data_type="int",
                access=AccessLevel.READ_ONLY,
                value=123,
                description="Custom integer parameter",
                is_custom=True,
                value_range=ValueRange(min_value=0, max_value=1000)
            ),
            TR181Node(
                path="Device.Custom.VendorA.Parameter3",
                name="Parameter3",
                data_type="boolean",
                access=AccessLevel.WRITE_ONLY,
                value=True,
                description="Custom boolean parameter",
                is_custom=True
            )
        ]
        
        subset_file = tmp_path / "custom_nodes_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        
        # Act
        await subset_manager.save_subset(custom_nodes)
        loaded_nodes = await subset_manager.extract()
        
        # Assert
        assert len(loaded_nodes) == 3
        
        for node in loaded_nodes:
            assert node.name is not None and len(node.name) > 0
            assert node.data_type in ["string", "int", "boolean"]
            assert node.access in [AccessLevel.READ_WRITE, AccessLevel.READ_ONLY, AccessLevel.WRITE_ONLY]
            assert node.is_custom is True
        
        # Verify specific custom nodes
        string_node = next((n for n in loaded_nodes if n.data_type == "string"), None)
        assert string_node is not None
        assert string_node.access == AccessLevel.READ_WRITE
        
        int_node = next((n for n in loaded_nodes if n.data_type == "int"), None)
        assert int_node is not None
        assert int_node.access == AccessLevel.READ_ONLY
        assert int_node.value_range is not None
        
        bool_node = next((n for n in loaded_nodes if n.data_type == "boolean"), None)
        assert bool_node is not None
        assert bool_node.access == AccessLevel.WRITE_ONLY
        
        print("✓ AC 2.2: Successfully accepted custom node definitions with name, type, and access level")
    
    @pytest.mark.asyncio
    async def test_2_3_validate_tr181_naming_conventions(self, tmp_path):
        """
        WHEN the subset is saved THEN the system SHALL validate that all node 
        definitions follow proper TR181 naming conventions
        """
        # Arrange
        valid_nodes = [
            TR181Node(
                path="Device.Custom.ValidPath.Parameter1",
                name="Parameter1",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="valid",
                is_custom=True
            )
        ]
        
        invalid_nodes = [
            TR181Node(
                path="invalid.path.without.device.prefix",
                name="InvalidParameter",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="invalid"
            )
        ]
        
        subset_file = tmp_path / "validation_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        
        # Act & Assert - Valid nodes should save successfully
        await subset_manager.save_subset(valid_nodes)
        validation_result = await subset_manager.validate()
        assert validation_result.is_valid
        
        # Invalid nodes should trigger validation warnings
        await subset_manager.save_subset(invalid_nodes)
        validation_result = await subset_manager.validate()
        # Should have warnings about naming convention violations
        assert len(validation_result.warnings) > 0 or not validation_result.is_valid
        
        print("✓ AC 2.3: Successfully validated TR181 naming conventions")
    
    @pytest.mark.asyncio
    async def test_2_4_report_duplicate_node_conflicts(self, tmp_path):
        """
        IF duplicate node names exist THEN the system SHALL report conflicts 
        and prevent saving
        """
        # Arrange
        duplicate_nodes = [
            TR181Node(
                path="Device.Custom.Test.Parameter1",
                name="Parameter1",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="first_value",
                is_custom=True
            ),
            TR181Node(
                path="Device.Custom.Test.Parameter1",  # Duplicate path
                name="Parameter1",
                data_type="int",  # Different type
                access=AccessLevel.READ_ONLY,
                value=42,
                is_custom=True
            )
        ]
        
        subset_file = tmp_path / "duplicate_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await subset_manager.save_subset(duplicate_nodes)
        
        # Verify error message mentions duplicates
        error_message = str(exc_info.value)
        assert "duplicate" in error_message.lower() or "conflict" in error_message.lower()
        
        print("✓ AC 2.4: Successfully reported duplicate node conflicts and prevented saving")


class TestRequirement3_CWMPVsSubsetComparison:
    """Test Requirement 3: Compare CWMP TR181 nodes against custom subset."""
    
    @pytest.mark.asyncio
    async def test_3_1_identify_nodes_missing_from_subset(self):
        """
        WHEN comparing CWMP nodes to custom subset THEN the system SHALL identify 
        nodes present in CWMP but missing from subset
        """
        # Arrange
        cwmp_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()  # 7 nodes
        subset_nodes = cwmp_nodes[:4]  # Only first 4 nodes
        
        comparison_engine = ComparisonEngine()
        
        # Act
        result = await comparison_engine.compare(cwmp_nodes, subset_nodes)
        
        # Assert
        assert len(result.only_in_source1) == 3  # 3 nodes only in CWMP
        assert result.summary.total_nodes_source1 == 7  # Total CWMP nodes
        assert result.summary.total_nodes_source2 == 4  # Total subset nodes
        
        # Verify the missing nodes are correctly identified
        missing_paths = [node.path for node in result.only_in_source1]
        expected_missing = [
            "Device.WiFi.AccessPoint.1.SSID",
            "Device.Ethernet.Interface.1.Enable", 
            "Device.Ethernet.Interface.1.Status"
        ]
        
        for expected_path in expected_missing:
            assert expected_path in missing_paths
        
        print("✓ AC 3.1: Successfully identified nodes present in CWMP but missing from subset")
    
    @pytest.mark.asyncio
    async def test_3_2_identify_nodes_missing_from_cwmp(self):
        """
        WHEN comparing CWMP nodes to custom subset THEN the system SHALL identify 
        nodes present in subset but missing from CWMP
        """
        # Arrange
        cwmp_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()
        subset_nodes = AcceptanceTestDataGenerator.create_custom_subset_nodes()  # Includes custom nodes
        
        comparison_engine = ComparisonEngine()
        
        # Act
        result = await comparison_engine.compare(cwmp_nodes, subset_nodes)
        
        # Assert
        subset_only_nodes = result.only_in_source2
        assert len(subset_only_nodes) >= 2  # At least the 2 custom nodes
        
        # Verify custom nodes are identified as subset-only
        custom_paths = [node.path for node in subset_only_nodes if getattr(node, 'is_custom', False)]
        assert "Device.Custom.VendorSpecific.Parameter1" in custom_paths
        assert "Device.Custom.VendorSpecific.Parameter2" in custom_paths
        
        print("✓ AC 3.2: Successfully identified nodes present in subset but missing from CWMP")
    
    @pytest.mark.asyncio
    async def test_3_3_generate_detailed_comparison_report(self):
        """
        WHEN comparison is complete THEN the system SHALL generate a detailed report 
        showing differences in node structure, types, and access permissions
        """
        # Arrange
        cwmp_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()
        
        # Create modified subset with different values/properties
        subset_nodes = []
        for node in cwmp_nodes[:3]:
            modified_node = TR181Node(
                path=node.path,
                name=node.name,
                data_type=node.data_type,
                access=AccessLevel.READ_ONLY if node.access == AccessLevel.READ_WRITE else node.access,  # Change access
                value=f"modified_{node.value}" if isinstance(node.value, str) else node.value,
                description=f"Modified: {node.description}"
            )
            subset_nodes.append(modified_node)
        
        comparison_engine = ComparisonEngine()
        
        # Act
        result = await comparison_engine.compare(cwmp_nodes, subset_nodes)
        
        # Assert
        assert len(result.differences) > 0  # Should find differences
        
        # Verify different types of differences are captured
        access_differences = [d for d in result.differences if d.property == "access"]
        value_differences = [d for d in result.differences if d.property == "value"]
        description_differences = [d for d in result.differences if d.property == "description"]
        
        assert len(access_differences) > 0  # Should find access level differences
        assert len(value_differences) > 0  # Should find value differences
        assert len(description_differences) > 0  # Should find description differences
        
        # Verify summary information
        assert result.summary.total_nodes_source1 == len(cwmp_nodes)
        assert result.summary.total_nodes_source2 == len(subset_nodes)
        assert result.summary.common_nodes == len(subset_nodes)
        assert result.summary.differences_count == len(result.differences)
        
        print("✓ AC 3.3: Successfully generated detailed report showing differences in structure, types, and access")
    
    @pytest.mark.asyncio
    async def test_3_4_highlight_property_mismatches(self):
        """
        WHEN nodes have different properties THEN the system SHALL highlight 
        specific property mismatches
        """
        # Arrange
        original_node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6,
            description="Original channel parameter",
            value_range=ValueRange(min_value=1, max_value=165)
        )
        
        modified_node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="string",  # Different type
            access=AccessLevel.READ_ONLY,  # Different access
            value="channel_6",  # Different value
            description="Modified channel parameter",  # Different description
            value_range=ValueRange(max_length=20)  # Different range
        )
        
        comparison_engine = ComparisonEngine()
        
        # Act
        result = await comparison_engine.compare([original_node], [modified_node])
        
        # Assert
        differences = result.differences
        assert len(differences) >= 4  # Should find multiple property differences
        
        # Verify specific property mismatches are highlighted
        property_types = [d.property for d in differences]
        assert "data_type" in property_types
        assert "access" in property_types
        assert "value" in property_types
        assert "description" in property_types
        
        # Verify difference details
        data_type_diff = next(d for d in differences if d.property == "data_type")
        assert data_type_diff.source1_value == "int"
        assert data_type_diff.source2_value == "string"
        assert data_type_diff.severity in [s.value for s in Severity]
        
        access_diff = next(d for d in differences if d.property == "access")
        assert access_diff.source1_value == AccessLevel.READ_WRITE.value
        assert access_diff.source2_value == AccessLevel.READ_ONLY.value
        
        print("✓ AC 3.4: Successfully highlighted specific property mismatches")


class TestRequirement4_SubsetVsDeviceComparison:
    """Test Requirement 4: Compare custom subset against actual device implementations."""
    
    @pytest.mark.asyncio
    async def test_4_1_connect_and_retrieve_device_data_model(self):
        """
        WHEN comparing subset to device implementation THEN the system SHALL connect 
        to the target device and retrieve its current data model
        """
        # Arrange
        device_nodes = AcceptanceTestDataGenerator.create_device_implementation_nodes()
        mock_hook = MockAcceptanceHook(device_nodes)
        
        config = HookDeviceConfig(
            type="rest",
            endpoint="http://test-device.example.com:8080",
            authentication={"username": "admin", "password": "admin123"},
            timeout=30,
            retry_count=3
        )
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Act
        extracted_nodes = await extractor.extract()
        source_info = extractor.get_source_info()
        
        # Assert
        assert mock_hook.connected  # Verify connection was established
        assert mock_hook.connection_attempts == 1  # Verify connection was attempted
        assert len(extracted_nodes) == len(device_nodes)
        
        # Verify data model retrieval
        assert source_info.type == "device"
        assert "test-device.example.com" in source_info.identifier
        
        # Verify all expected device nodes were retrieved
        device_paths = [node.path for node in extracted_nodes]
        expected_paths = [node.path for node in device_nodes]
        assert set(device_paths) == set(expected_paths)
        
        print("✓ AC 4.1: Successfully connected to device and retrieved current data model")
    
    @pytest.mark.asyncio
    async def test_4_2_identify_matching_implementations(self, tmp_path):
        """
        WHEN device data is retrieved THEN the system SHALL identify implemented 
        nodes that match the subset specification
        """
        # Arrange
        subset_nodes = AcceptanceTestDataGenerator.create_custom_subset_nodes()
        device_nodes = AcceptanceTestDataGenerator.create_device_implementation_nodes()
        
        # Save subset
        subset_file = tmp_path / "device_comparison_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        await subset_manager.save_subset(subset_nodes)
        
        # Create device extractor
        mock_hook = MockAcceptanceHook(device_nodes)
        config = HookDeviceConfig(
            type="rest",
            endpoint="http://test-device.example.com:8080",
            authentication={"username": "admin", "password": "admin123"},
            timeout=30,
            retry_count=3
        )
        device_extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Act
        enhanced_engine = EnhancedComparisonEngine()
        result = await enhanced_engine.compare_with_validation(subset_nodes, device_nodes, device_extractor)
        
        # Assert
        basic_result = result.basic_comparison
        common_nodes = basic_result.summary.common_nodes
        
        # Should find matching implementations
        assert common_nodes > 0
        
        # Verify specific matches
        subset_paths = {node.path for node in subset_nodes}
        device_paths = {node.path for node in device_nodes}
        expected_matches = subset_paths & device_paths
        
        assert common_nodes == len(expected_matches)
        
        # Should identify Device.DeviceInfo.Manufacturer and Device.WiFi.Radio.1.Enable as matches
        assert "Device.DeviceInfo.Manufacturer" in expected_matches
        assert "Device.WiFi.Radio.1.Enable" in expected_matches
        
        print("✓ AC 4.2: Successfully identified implemented nodes that match subset specification")
    
    @pytest.mark.asyncio
    async def test_4_3_report_missing_extra_and_mismatched_implementations(self, tmp_path):
        """
        WHEN comparison is complete THEN the system SHALL report missing implementations, 
        extra implementations, and property mismatches
        """
        # Arrange
        subset_nodes = AcceptanceTestDataGenerator.create_custom_subset_nodes()  # 5 nodes
        device_nodes = AcceptanceTestDataGenerator.create_device_implementation_nodes()  # 4 nodes, some different
        
        comparison_engine = ComparisonEngine()
        
        # Act
        result = await comparison_engine.compare(subset_nodes, device_nodes)
        
        # Assert
        # Missing implementations (in subset but not in device)
        missing_implementations = result.only_in_source1
        assert len(missing_implementations) > 0
        
        # Should include the custom nodes and WiFi.Radio.1.Channel
        missing_paths = [node.path for node in missing_implementations]
        assert "Device.Custom.VendorSpecific.Parameter1" in missing_paths
        assert "Device.Custom.VendorSpecific.Parameter2" in missing_paths
        assert "Device.WiFi.Radio.1.Channel" in missing_paths
        
        # Extra implementations (in device but not in subset)
        extra_implementations = result.only_in_source2
        assert len(extra_implementations) > 0
        
        # Should include Device.Implementation.ExtraParameter
        extra_paths = [node.path for node in extra_implementations]
        assert "Device.Implementation.ExtraParameter" in extra_paths
        
        # Property mismatches (common nodes with different properties)
        property_mismatches = result.differences
        assert len(property_mismatches) > 0
        
        # Should find differences in WiFi.Radio.1.Enable (different values)
        enable_differences = [d for d in property_mismatches if d.path == "Device.WiFi.Radio.1.Enable"]
        assert len(enable_differences) > 0
        
        print("✓ AC 4.3: Successfully reported missing, extra, and mismatched implementations")
    
    @pytest.mark.asyncio
    async def test_4_4_provide_connectivity_error_messages(self):
        """
        IF device connection fails THEN the system SHALL provide clear 
        connectivity error messages
        """
        # Arrange
        mock_hook = MockAcceptanceHook([], connection_should_fail=True)
        
        config = HookDeviceConfig(
            type="rest",
            endpoint="http://unreachable-device.example.com:8080",
            authentication={"username": "admin", "password": "wrong_password"},
            timeout=5,  # Short timeout
            retry_count=1
        )
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            await extractor.extract()
        
        # Verify clear error message
        error = exc_info.value
        error_message = str(error)
        
        assert "connect" in error_message.lower() or "connection" in error_message.lower()
        assert hasattr(error, 'error_id')  # Should have error ID for tracking
        assert hasattr(error, 'category')  # Should have error category
        
        # Verify error provides actionable information
        assert "device" in error_message.lower()
        
        print("✓ AC 4.4: Successfully provided clear connectivity error messages")


class TestRequirement5_DeviceVsDeviceComparison:
    """Test Requirement 5: Compare TR181 implementations between two different devices."""
    
    @pytest.mark.asyncio
    async def test_5_1_retrieve_data_models_from_both_devices(self):
        """
        WHEN comparing two devices THEN the system SHALL retrieve TR181 data models 
        from both devices simultaneously
        """
        # Arrange
        device1_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()
        device2_nodes = AcceptanceTestDataGenerator.create_device_implementation_nodes()
        
        mock_hook1 = MockAcceptanceHook(device1_nodes)
        mock_hook2 = MockAcceptanceHook(device2_nodes)
        
        config1 = HookDeviceConfig(
            type="cwmp",
            endpoint="http://device1.example.com:7547",
            authentication={"username": "admin1", "password": "pass1"},
            timeout=30,
            retry_count=3
        )
        
        config2 = HookDeviceConfig(
            type="rest",
            endpoint="http://device2.example.com:8080",
            authentication={"username": "admin2", "password": "pass2"},
            timeout=30,
            retry_count=3
        )
        
        extractor1 = HookBasedDeviceExtractor(mock_hook1, config1)
        extractor2 = HookBasedDeviceExtractor(mock_hook2, config2)
        
        # Act - Extract from both devices simultaneously
        device1_task = extractor1.extract()
        device2_task = extractor2.extract()
        
        device1_extracted, device2_extracted = await asyncio.gather(device1_task, device2_task)
        
        # Assert
        assert len(device1_extracted) == len(device1_nodes)
        assert len(device2_extracted) == len(device2_nodes)
        
        # Verify both connections were established
        assert mock_hook1.connected
        assert mock_hook2.connected
        
        # Verify data models were retrieved from both devices
        device1_paths = {node.path for node in device1_extracted}
        device2_paths = {node.path for node in device2_extracted}
        
        # Should have different sets of paths
        assert device1_paths != device2_paths
        
        print("✓ AC 5.1: Successfully retrieved TR181 data models from both devices simultaneously")
    
    @pytest.mark.asyncio
    async def test_5_2_perform_comprehensive_node_comparison(self):
        """
        WHEN device data is collected THEN the system SHALL perform a comprehensive 
        node-by-node comparison
        """
        # Arrange
        device1_nodes = AcceptanceTestDataGenerator.create_cwmp_nodes()
        device2_nodes = AcceptanceTestDataGenerator.create_device_implementation_nodes()
        
        comparison_engine = ComparisonEngine()
        
        # Act
        result = await comparison_engine.compare(device1_nodes, device2_nodes)
        
        # Assert
        # Verify comprehensive comparison was performed
        assert result.summary.total_nodes_source1 == len(device1_nodes)
        assert result.summary.total_nodes_source2 == len(device2_nodes)
        
        # Should identify common nodes
        assert result.summary.common_nodes > 0
        
        # Should identify unique nodes in each device
        assert len(result.only_in_source1) > 0  # Nodes only in device 1
        assert len(result.only_in_source2) > 0  # Nodes only in device 2
        
        # Should identify property differences in common nodes
        assert len(result.differences) > 0
        
        # Verify node-by-node comparison details
        all_compared_paths = set()
        
        # Add paths from unique nodes
        all_compared_paths.update(node.path for node in result.only_in_source1)
        all_compared_paths.update(node.path for node in result.only_in_source2)
        
        # Add paths from differences
        all_compared_paths.update(diff.path for diff in result.differences)
        
        # Should have compared all unique paths
        device1_paths = {node.path for node in device1_nodes}
        device2_paths = {node.path for node in device2_nodes}
        all_device_paths = device1_paths | device2_paths
        
        # All paths should be accounted for in the comparison
        common_paths = device1_paths & device2_paths
        unique_paths = (device1_paths | device2_paths) - common_paths
        
        assert len(all_compared_paths) >= len(unique_paths)
        
        print("✓ AC 5.2: Successfully performed comprehensive node-by-node comparison")
    
    @pytest.mark.asyncio
    async def test_5_3_generate_device_comparison_report(self):
        """
        WHEN comparison is complete THEN the system SHALL generate a report showing 
        nodes unique to each device and common nodes with different values
        """
        # Arrange
        device1_nodes = [
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="Vendor1",
                description="Device 1 manufacturer"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6,
                description="Device 1 WiFi channel"
            ),
            TR181Node(
                path="Device.Vendor1.SpecificFeature",
                name="SpecificFeature",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="Vendor 1 specific feature"
            )
        ]
        
        device2_nodes = [
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="Vendor2",  # Different value
                description="Device 2 manufacturer"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=11,  # Different value
                description="Device 2 WiFi channel"
            ),
            TR181Node(
                path="Device.Vendor2.SpecificFeature",
                name="SpecificFeature",
                data_type="string",  # Different type
                access=AccessLevel.READ_ONLY,
                value="vendor2_feature",
                description="Vendor 2 specific feature"
            )
        ]
        
        comparison_engine = ComparisonEngine()
        
        # Act
        result = await comparison_engine.compare(device1_nodes, device2_nodes)
        
        # Assert
        # Nodes unique to device 1
        device1_unique = result.only_in_source1
        assert len(device1_unique) == 1
        assert device1_unique[0].path == "Device.Vendor1.SpecificFeature"
        
        # Nodes unique to device 2
        device2_unique = result.only_in_source2
        assert len(device2_unique) == 1
        assert device2_unique[0].path == "Device.Vendor2.SpecificFeature"
        
        # Common nodes with different values
        differences = result.differences
        assert len(differences) >= 2  # Should find value differences
        
        # Verify manufacturer value difference
        manufacturer_diffs = [d for d in differences if d.path == "Device.DeviceInfo.Manufacturer" and d.property == "value"]
        assert len(manufacturer_diffs) == 1
        assert manufacturer_diffs[0].source1_value == "Vendor1"
        assert manufacturer_diffs[0].source2_value == "Vendor2"
        
        # Verify channel value difference
        channel_diffs = [d for d in differences if d.path == "Device.WiFi.Radio.1.Channel" and d.property == "value"]
        assert len(channel_diffs) == 1
        assert channel_diffs[0].source1_value == 6
        assert channel_diffs[0].source2_value == 11
        
        print("✓ AC 5.3: Successfully generated report showing unique nodes and value differences")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])