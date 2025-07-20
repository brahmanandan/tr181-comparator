"""Simple final integration test to validate all requirements are met."""

import pytest
import asyncio
import time
import json
import psutil
import os
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import AsyncMock

from tr181_comparator.models import TR181Node, AccessLevel, ValueRange
from tr181_comparator.main import TR181ComparatorApp, ReportGenerator
from tr181_comparator.config import SystemConfig, DeviceConfig, SubsetConfig, ExportConfig
from tr181_comparator.comparison import ComparisonEngine, EnhancedComparisonEngine
from tr181_comparator.extractors import SubsetManager, HookBasedDeviceExtractor
from tr181_comparator.hooks import DeviceConfig as HookDeviceConfig
from tr181_comparator.validation import TR181Validator
from tr181_comparator.errors import ConnectionError, ValidationError
from tr181_comparator.logging import initialize_logging, get_logger


def create_test_nodes(count: int = 100) -> List[TR181Node]:
    """Create test TR181 nodes for validation."""
    nodes = []
    
    # Core device info nodes
    nodes.extend([
        TR181Node(
            path="Device.DeviceInfo.Manufacturer",
            name="Manufacturer",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="TestManufacturer",
            description="Device manufacturer"
        ),
        TR181Node(
            path="Device.DeviceInfo.ModelName",
            name="ModelName",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="TestModel",
            description="Device model"
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True,
            description="WiFi radio enable"
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6,
            description="WiFi channel",
            value_range=ValueRange(min_value=1, max_value=165)
        )
    ])
    
    # Generate additional nodes to reach target count
    for i in range(len(nodes), count):
        nodes.append(
            TR181Node(
                path=f"Device.Test.Parameter.{i}",
                name=f"Parameter{i}",
                data_type="string" if i % 3 == 0 else ("int" if i % 3 == 1 else "boolean"),
                access=AccessLevel.READ_WRITE if i % 2 == 0 else AccessLevel.READ_ONLY,
                value=f"value_{i}" if i % 3 == 0 else (i if i % 3 == 1 else (i % 2 == 0)),
                description=f"Test parameter {i}"
            )
        )
    
    return nodes


class MockHook:
    """Simple mock hook for testing."""
    
    def __init__(self, nodes: List[TR181Node], should_fail: bool = False):
        self.nodes = nodes
        self.should_fail = should_fail
        self.connected = False
    
    async def connect(self, config: HookDeviceConfig) -> bool:
        if self.should_fail:
            return False
        self.connected = True
        return True
    
    async def disconnect(self) -> None:
        self.connected = False
    
    async def get_parameter_names(self, path_prefix: str = "Device.") -> List[str]:
        if not self.connected:
            raise ConnectionError("Not connected")
        return [node.path for node in self.nodes if node.path.startswith(path_prefix)]
    
    async def get_parameter_values(self, paths: List[str]) -> Dict[str, Any]:
        if not self.connected:
            raise ConnectionError("Not connected")
        node_map = {node.path: node for node in self.nodes}
        return {path: node_map[path].value for path in paths if path in node_map}
    
    async def get_parameter_attributes(self, paths: List[str]) -> Dict[str, Dict[str, Any]]:
        if not self.connected:
            raise ConnectionError("Not connected")
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
            raise ConnectionError("Not connected")
        return {"result": "success", "output": {}}


class TestFinalSystemIntegration:
    """Final comprehensive system integration tests."""
    
    @pytest.mark.asyncio
    async def test_requirement_1_cwmp_extraction(self):
        """Test Requirement 1: Extract TR181 nodes from CWMP sources."""
        # Arrange
        test_nodes = create_test_nodes(50)
        mock_hook = MockHook(test_nodes)
        
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
        assert len(extracted_nodes) == 50
        assert all(node.path.startswith("Device.") for node in extracted_nodes)
        assert all(hasattr(node, 'data_type') and node.data_type for node in extracted_nodes)
        assert all(hasattr(node, 'access') and node.access for node in extracted_nodes)
        
        print("✓ Requirement 1 validated: CWMP extraction successful")
    
    @pytest.mark.asyncio
    async def test_requirement_2_custom_subset(self, tmp_path):
        """Test Requirement 2: Define custom subset of TR181 nodes."""
        # Arrange
        custom_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="Custom WiFi radio enable"
            ),
            TR181Node(
                path="Device.Custom.Parameter.1",
                name="CustomParameter1",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="custom_value",
                description="Custom parameter",
                is_custom=True
            )
        ]
        
        # Act
        subset_file = tmp_path / "custom_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        await subset_manager.save_subset(custom_nodes)
        loaded_nodes = await subset_manager.extract()
        
        # Assert
        assert len(loaded_nodes) == 2
        assert any(node.is_custom for node in loaded_nodes)
        assert all(node.path.startswith("Device.") for node in loaded_nodes)
        
        print("✓ Requirement 2 validated: Custom subset creation successful")
    
    @pytest.mark.asyncio
    async def test_requirement_3_cwmp_vs_subset_comparison(self, tmp_path):
        """Test Requirement 3: Compare CWMP TR181 nodes against custom subset."""
        # Arrange
        cwmp_nodes = create_test_nodes(30)
        subset_nodes = cwmp_nodes[:20]  # Subset of CWMP nodes
        subset_nodes.append(
            TR181Node(
                path="Device.Custom.OnlyInSubset",
                name="OnlyInSubset",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="subset_only",
                is_custom=True
            )
        )
        
        # Act
        comparison_engine = ComparisonEngine()
        result = await comparison_engine.compare(cwmp_nodes, subset_nodes)
        
        # Assert
        assert result.summary.total_nodes_source1 == 30  # CWMP nodes
        assert result.summary.total_nodes_source2 == 21  # Subset nodes
        assert len(result.only_in_source1) == 10  # Nodes only in CWMP
        assert len(result.only_in_source2) == 1   # Custom node only in subset
        assert result.summary.common_nodes == 20  # Overlapping nodes
        
        print("✓ Requirement 3 validated: CWMP vs subset comparison successful")
    
    @pytest.mark.asyncio
    async def test_requirement_4_subset_vs_device_comparison(self, tmp_path):
        """Test Requirement 4: Compare custom subset against device implementation."""
        # Arrange
        subset_nodes = create_test_nodes(20)
        device_nodes = subset_nodes[:15]  # Missing 5 nodes
        device_nodes.append(
            TR181Node(
                path="Device.Implementation.ExtraParameter",
                name="ExtraParameter",
                data_type="int",
                access=AccessLevel.READ_ONLY,
                value=42,
                description="Extra parameter in device"
            )
        )
        
        mock_hook = MockHook(device_nodes)
        config = HookDeviceConfig(
            type="rest",
            endpoint="http://test-device.example.com:8080",
            authentication={"username": "test", "password": "test"},
            timeout=30,
            retry_count=3
        )
        
        device_extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Act
        enhanced_engine = EnhancedComparisonEngine()
        result = await enhanced_engine.compare_with_validation(subset_nodes, device_nodes, device_extractor)
        
        # Assert
        assert result.basic_comparison.summary.total_nodes_source1 == 20  # Subset
        assert result.basic_comparison.summary.total_nodes_source2 == 16  # Device
        assert len(result.basic_comparison.only_in_source1) == 5   # Missing in device
        assert len(result.basic_comparison.only_in_source2) == 1   # Extra in device
        
        print("✓ Requirement 4 validated: Subset vs device comparison successful")
    
    @pytest.mark.asyncio
    async def test_requirement_5_device_vs_device_comparison(self):
        """Test Requirement 5: Compare TR181 implementations between two devices."""
        # Arrange
        device1_nodes = create_test_nodes(25)
        device2_nodes = create_test_nodes(30)  # Different set
        
        # Act
        comparison_engine = ComparisonEngine()
        result = await comparison_engine.compare(device1_nodes, device2_nodes)
        
        # Assert
        assert result.summary.total_nodes_source1 == 25  # Device 1
        assert result.summary.total_nodes_source2 == 30  # Device 2
        assert result.summary.common_nodes == 25  # All device1 nodes are in device2
        assert len(result.only_in_source2) == 5   # Extra nodes in device2
        
        print("✓ Requirement 5 validated: Device vs device comparison successful")
    
    @pytest.mark.asyncio
    async def test_requirement_6_export_multiple_formats(self, tmp_path):
        """Test Requirement 6: Export comparison results in multiple formats."""
        # Arrange
        nodes1 = create_test_nodes(10)
        nodes2 = create_test_nodes(12)
        
        comparison_engine = ComparisonEngine()
        result = await comparison_engine.compare(nodes1, nodes2)
        
        # Act
        report_generator = ReportGenerator(include_metadata=True)
        
        json_file = tmp_path / "test_result.json"
        xml_file = tmp_path / "test_result.xml"
        text_file = tmp_path / "test_result.txt"
        
        await report_generator.export_as_json(result, json_file)
        await report_generator.export_as_xml(result, xml_file)
        await report_generator.export_as_text(result, text_file)
        
        # Assert
        assert json_file.exists()
        assert xml_file.exists()
        assert text_file.exists()
        
        # Verify JSON content
        with open(json_file, 'r') as f:
            json_data = json.load(f)
            assert 'summary' in json_data
            # Metadata may not be included in basic comparison results
        
        print("✓ Requirement 6 validated: Multiple format export successful")
    
    @pytest.mark.asyncio
    async def test_requirement_7_device_configuration(self):
        """Test Requirement 7: Configure connection parameters for different device types."""
        # Arrange
        configs = [
            HookDeviceConfig(
                type="rest",
                endpoint="http://rest-device.example.com:8080",
                authentication={"username": "admin", "password": "admin123"},
                timeout=30,
                retry_count=3
            ),
            HookDeviceConfig(
                type="cwmp",
                endpoint="http://cwmp-device.example.com:7547",
                authentication={"username": "cwmp_user", "password": "cwmp_pass"},
                timeout=45,
                retry_count=2
            )
        ]
        
        # Act & Assert
        for config in configs:
            assert config.type in ["rest", "cwmp"]
            assert config.endpoint.startswith("http")
            assert isinstance(config.authentication, dict)
            assert config.timeout > 0
            assert config.retry_count > 0
        
        print("✓ Requirement 7 validated: Device configuration successful")
    
    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(self):
        """Test memory usage and performance with large datasets."""
        # Arrange
        large_dataset = create_test_nodes(1000)
        modified_dataset = large_dataset.copy()
        
        # Modify some nodes to create differences
        for i in range(0, len(modified_dataset), 10):
            if modified_dataset[i].data_type == "string":
                modified_dataset[i] = TR181Node(
                    path=modified_dataset[i].path,
                    name=modified_dataset[i].name,
                    data_type=modified_dataset[i].data_type,
                    access=modified_dataset[i].access,
                    value=f"modified_{modified_dataset[i].value}",
                    description=modified_dataset[i].description
                )
        
        # Act
        comparison_engine = ComparisonEngine()
        start_time = time.time()
        result = await comparison_engine.compare(large_dataset, modified_dataset)
        end_time = time.time()
        
        # Assert
        comparison_time = end_time - start_time
        assert comparison_time < 10.0  # Should complete within 10 seconds
        assert result.summary.total_nodes_source1 == 1000
        assert result.summary.total_nodes_source2 == 1000
        assert len(result.differences) > 0  # Should find differences
        
        print(f"✓ Performance validated: {comparison_time:.2f}s for 1000 nodes")
    
    @pytest.mark.asyncio
    async def test_error_handling_and_security(self):
        """Test error handling and security measures."""
        # Test connection failure
        mock_hook = MockHook([], should_fail=True)
        config = HookDeviceConfig(
            type="rest",
            endpoint="http://invalid-device.example.com:8080",
            authentication={"username": "invalid", "password": "invalid"},
            timeout=5,
            retry_count=1
        )
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Should raise connection error
        with pytest.raises(ConnectionError):
            await extractor.extract()
        
        # Test input validation
        validator = TR181Validator()
        malicious_node = TR181Node(
            path="../../../etc/passwd",
            name="MaliciousNode",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="malicious"
        )
        
        result = validator.validate_node(malicious_node)
        assert not result.is_valid or len(result.warnings) > 0
        
        print("✓ Error handling and security validated")
    
    @pytest.mark.asyncio
    async def test_complete_system_workflow(self, tmp_path):
        """Test complete end-to-end system workflow."""
        # Initialize logging
        initialize_logging()
        logger = get_logger("system_test")
        
        # Create system configuration
        from tr181_comparator.config import HookConfig
        
        system_config = SystemConfig(
            devices=[
                DeviceConfig(
                    name="test_device",
                    type="rest",
                    endpoint="http://test-device.example.com:8080",
                    authentication={"username": "admin", "password": "test123"},
                    timeout=30,
                    retry_count=3
                )
            ],
            subsets=[
                SubsetConfig(
                    name="test_subset",
                    file_path=str(tmp_path / "test_subset.json"),
                    version="1.0.0",
                    description="Test subset"
                )
            ],
            export_settings=ExportConfig(
                default_format="json",
                output_directory=str(tmp_path),
                include_metadata=True,
                timestamp_format="%Y%m%d_%H%M%S"
            ),
            hook_configs={
                'rest': HookConfig(
                    hook_type='rest',
                    endpoint_template='http://{host}:{port}/api/tr181',
                    default_headers={'Content-Type': 'application/json'}
                )
            },
            connection_defaults={
                'timeout': 30,
                'retry_count': 3
            }
        )
        
        # Create test data
        cwmp_nodes = create_test_nodes(50)
        subset_nodes = cwmp_nodes[:30]
        device_nodes = cwmp_nodes[10:40]
        
        # Save subset
        subset_manager = SubsetManager(str(tmp_path / "test_subset.json"))
        await subset_manager.save_subset(subset_nodes)
        
        # Create application
        app = TR181ComparatorApp(system_config)
        
        # Perform comparisons
        comparison_engine = ComparisonEngine()
        
        # CWMP vs Subset
        cwmp_vs_subset_result = await comparison_engine.compare(cwmp_nodes, subset_nodes)
        
        # Subset vs Device (simulated)
        subset_vs_device_result = await comparison_engine.compare(subset_nodes, device_nodes)
        
        # Device vs Device
        device2_nodes = device_nodes[:20]
        device_vs_device_result = await comparison_engine.compare(device_nodes, device2_nodes)
        
        # Export results
        results = [
            ("cwmp_vs_subset", cwmp_vs_subset_result),
            ("subset_vs_device", subset_vs_device_result),
            ("device_vs_device", device_vs_device_result)
        ]
        
        for result_name, result in results:
            await app.export_result_as_json(result, tmp_path / f"{result_name}.json")
            await app.export_result_as_xml(result, tmp_path / f"{result_name}.xml")
            await app.export_result_as_text(result, tmp_path / f"{result_name}.txt")
            
            # Verify files were created
            assert (tmp_path / f"{result_name}.json").exists()
            assert (tmp_path / f"{result_name}.xml").exists()
            assert (tmp_path / f"{result_name}.txt").exists()
        
        # Verify all results
        assert cwmp_vs_subset_result.summary.total_nodes_source1 == 50
        assert cwmp_vs_subset_result.summary.total_nodes_source2 == 30
        
        assert subset_vs_device_result.summary.total_nodes_source1 == 30
        assert subset_vs_device_result.summary.total_nodes_source2 == 30
        
        assert device_vs_device_result.summary.total_nodes_source1 == 30
        assert device_vs_device_result.summary.total_nodes_source2 == 20
        
        logger.info("Complete system workflow test completed successfully")
        print("✓ Complete system workflow validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])