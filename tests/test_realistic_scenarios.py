"""Realistic scenario integration tests for TR181 node comparator.

This module contains tests for realistic usage scenarios including:
- Firmware upgrade validation
- Multi-vendor device comparison
- Compliance validation
- Configuration drift detection
"""

import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import AsyncMock

from tr181_comparator.models import (
    TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function
)
from tr181_comparator.comparison import ComparisonEngine, EnhancedComparisonEngine
from tr181_comparator.extractors import CWMPExtractor, HookBasedDeviceExtractor, SubsetManager
from tr181_comparator.hooks import DeviceConfig
from tr181_comparator.errors import ConnectionError, ValidationError

# Test utility classes
class TestDataGenerator:
    """Utility class for generating realistic test data."""
    
    @staticmethod
    def generate_realistic_tr181_nodes(count: int = 50) -> List[TR181Node]:
        """Generate realistic TR181 node structures for testing."""
        nodes = []
        
        # Device Info nodes
        nodes.extend([
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="TechCorp",
                description="Device manufacturer"
            ),
            TR181Node(
                path="Device.DeviceInfo.ModelName",
                name="ModelName", 
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="TR181-Router-Pro",
                description="Device model name"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="Radio enable status"
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
        current_count = len(nodes)
        for i in range(current_count, count):
            nodes.append(
                TR181Node(
                    path=f"Device.Test.Parameter.{i}",
                    name=f"Parameter{i}",
                    data_type="string",
                    access=AccessLevel.READ_WRITE,
                    value=f"test_value_{i}",
                    description=f"Test parameter {i}"
                )
            )
        
        return nodes
    
    @staticmethod
    def create_modified_nodes(original_nodes: List[TR181Node], 
                            modification_ratio: float = 0.3) -> List[TR181Node]:
        """Create modified version of nodes for comparison testing."""
        modified_nodes = []
        modification_count = int(len(original_nodes) * modification_ratio)
        
        for i, node in enumerate(original_nodes):
            if i < modification_count:
                # Create modified version
                modified_node = TR181Node(
                    path=node.path,
                    name=node.name,
                    data_type=node.data_type,
                    access=AccessLevel.READ_ONLY if node.access == AccessLevel.READ_WRITE else node.access,
                    value=f"modified_{node.value}" if isinstance(node.value, str) else node.value,
                    description=f"Modified: {node.description}" if node.description else None
                )
                modified_nodes.append(modified_node)
            else:
                modified_nodes.append(node)
        
        return modified_nodes


class MockCWMPHook:
    """Mock CWMP hook for integration testing."""
    
    def __init__(self, nodes: List[TR181Node]):
        self.nodes = nodes
        self.connected = False
        self.should_fail = False
    
    async def connect(self, config: DeviceConfig) -> bool:
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


class MockDeviceHook:
    """Mock device hook for integration testing."""
    
    def __init__(self, nodes: List[TR181Node]):
        self.nodes = nodes
        self.connected = False
        self.should_fail = False
    
    async def connect(self, config: DeviceConfig) -> bool:
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


class TestRealisticScenarios:
    """Test realistic usage scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_firmware_upgrade_comparison(self):
        """Test comparison scenario for firmware upgrade validation."""
        # Generate base device nodes
        base_nodes = TestDataGenerator.generate_realistic_tr181_nodes(50)
        
        # Simulate pre-upgrade device state
        pre_upgrade_nodes = base_nodes.copy()
        
        # Simulate post-upgrade device state with some changes
        post_upgrade_nodes = TestDataGenerator.create_modified_nodes(base_nodes, 0.1)
        
        # Add some new nodes (new features)
        new_nodes = [
            TR181Node(
                path="Device.DeviceInfo.FirmwareVersion",
                name="FirmwareVersion",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="3.0.0",  # New firmware version
                description="Current firmware version"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.WiFi6Support",
                name="WiFi6Support",
                data_type="boolean",
                access=AccessLevel.READ_ONLY,
                value=True,
                description="WiFi 6 support indicator"
            )
        ]
        post_upgrade_nodes.extend(new_nodes)
        
        # Create device configurations
        device_config = DeviceConfig(
            type="cwmp",
            endpoint="http://device.example.com:7547",
            authentication={"username": "admin", "password": "password"},
            timeout=30,
            retry_count=3
        )
        
        # Create extractors
        pre_hook = MockCWMPHook(pre_upgrade_nodes)
        pre_extractor = CWMPExtractor(pre_hook, device_config)
        
        post_hook = MockCWMPHook(post_upgrade_nodes)
        post_extractor = CWMPExtractor(post_hook, device_config)
        
        # Extract and compare
        pre_nodes = await pre_extractor.extract()
        post_nodes = await post_extractor.extract()
        
        comparison_engine = ComparisonEngine()
        result = await comparison_engine.compare(pre_nodes, post_nodes)
        
        # Verify upgrade changes detected
        assert len(result.only_in_source2) >= 2  # New nodes added
        assert len(result.differences) > 0  # Some parameters changed
        
        # Check for specific new features
        new_node_paths = {node.path for node in result.only_in_source2}
        assert "Device.DeviceInfo.FirmwareVersion" in new_node_paths
        assert "Device.WiFi.Radio.1.WiFi6Support" in new_node_paths
        
        # Verify no critical nodes were removed
        removed_node_paths = {node.path for node in result.only_in_source1}
        critical_paths = [
            "Device.DeviceInfo.Manufacturer",
            "Device.DeviceInfo.ModelName",
            "Device.WiFi.Radio.1.Enable"
        ]
        for critical_path in critical_paths:
            assert critical_path not in removed_node_paths, f"Critical node {critical_path} was removed"
    
    @pytest.mark.asyncio
    async def test_multi_vendor_device_comparison(self):
        """Test comparison between devices from different vendors."""
        # Vendor A device (more comprehensive TR181 support)
        vendor_a_nodes = TestDataGenerator.generate_realistic_tr181_nodes(80)
        
        # Vendor B device (different subset of TR181 support)
        vendor_b_base_nodes = TestDataGenerator.generate_realistic_tr181_nodes(60)
        # Add vendor-specific custom nodes
        vendor_b_custom_nodes = [
            TR181Node(
                path="Device.X_VENDORB_CustomFeature.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                is_custom=True,
                description="Vendor B custom feature"
            ),
            TR181Node(
                path="Device.X_VENDORB_CustomFeature.Mode",
                name="Mode",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="advanced",
                is_custom=True,
                description="Vendor B custom mode",
                value_range=ValueRange(allowed_values=["basic", "advanced", "expert"])
            )
        ]
        vendor_b_nodes = vendor_b_base_nodes + vendor_b_custom_nodes
        
        # Create device configurations
        cwmp_config = DeviceConfig(
            type="cwmp",
            endpoint="http://vendor-a-device.example.com:7547",
            authentication={"username": "admin", "password": "password"},
            timeout=30,
            retry_count=3
        )
        
        rest_config = DeviceConfig(
            type="rest",
            endpoint="http://vendor-b-device.example.com:8080",
            authentication={"token": "vendor-b-token"},
            timeout=30,
            retry_count=3
        )
        
        # Create extractors
        vendor_a_hook = MockCWMPHook(vendor_a_nodes)
        vendor_a_extractor = CWMPExtractor(vendor_a_hook, cwmp_config)
        
        vendor_b_hook = MockDeviceHook(vendor_b_nodes)
        vendor_b_extractor = HookBasedDeviceExtractor(vendor_b_hook, rest_config)
        
        # Extract and compare
        vendor_a_extracted = await vendor_a_extractor.extract()
        vendor_b_extracted = await vendor_b_extractor.extract()
        
        comparison_engine = ComparisonEngine()
        result = await comparison_engine.compare(vendor_a_extracted, vendor_b_extracted)
        
        # Verify multi-vendor comparison results
        assert result.summary.total_nodes_source1 == 80
        assert result.summary.total_nodes_source2 == 62  # 60 + 2 custom
        assert len(result.only_in_source1) > 0  # Vendor A unique features
        assert len(result.only_in_source2) > 0  # Vendor B unique features
        
        # Check for custom nodes
        vendor_b_unique_paths = {node.path for node in result.only_in_source2}
        custom_nodes = [path for path in vendor_b_unique_paths if "X_VENDORB" in path]
        assert len(custom_nodes) >= 2
        
        # Analyze compatibility
        compatibility_score = result.summary.common_nodes / min(
            result.summary.total_nodes_source1, 
            result.summary.total_nodes_source2
        )
        
        print(f"Vendor compatibility score: {compatibility_score:.2f}")
        print(f"Vendor A unique features: {len(result.only_in_source1)}")
        print(f"Vendor B unique features: {len(result.only_in_source2)}")
    
    @pytest.mark.asyncio
    async def test_compliance_validation_scenario(self, tmp_path):
        """Test compliance validation against a standard subset."""
        # Create compliance subset (required TR181 parameters)
        compliance_nodes = [
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                description="Device manufacturer (required)"
            ),
            TR181Node(
                path="Device.DeviceInfo.ModelName",
                name="ModelName",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                description="Device model name (required)"
            ),
            TR181Node(
                path="Device.WiFi.RadioNumberOfEntries",
                name="RadioNumberOfEntries",
                data_type="int",
                access=AccessLevel.READ_ONLY,
                value_range=ValueRange(min_value=0),
                description="Number of WiFi radios (required)"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                description="WiFi radio enable (required)"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value_range=ValueRange(min_value=1, max_value=165),
                description="WiFi channel (required)"
            )
        ]
        
        # Create subset manager
        subset_file = tmp_path / "compliance_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        await subset_manager.save_subset(compliance_nodes)
        
        # Create device with partial compliance
        device_nodes = TestDataGenerator.generate_realistic_tr181_nodes(30)
        # Remove one required parameter to simulate non-compliance
        device_nodes = [node for node in device_nodes if node.path != "Device.WiFi.RadioNumberOfEntries"]
        
        device_config = DeviceConfig(
            type="rest",
            endpoint="http://test-device.example.com:8080",
            authentication={"token": "test-token"},
            timeout=30,
            retry_count=3
        )
        
        device_hook = MockDeviceHook(device_nodes)
        device_extractor = HookBasedDeviceExtractor(device_hook, device_config)
        
        # Perform enhanced comparison for compliance validation
        enhanced_engine = EnhancedComparisonEngine()
        
        subset_extracted = await subset_manager.extract()
        device_extracted = await device_extractor.extract()
        
        result = await enhanced_engine.compare_with_validation(
            subset_extracted, device_extracted, device_extractor
        )
        
        # Analyze compliance
        summary = result.get_summary()
        
        # Check compliance metrics
        missing_required = len(result.basic_comparison.only_in_source1)
        validation_errors = summary['validation']['nodes_with_errors']
        
        compliance_score = (
            (result.basic_comparison.summary.common_nodes - validation_errors) /
            len(compliance_nodes)
        )
        
        assert 0 <= compliance_score <= 1
        assert missing_required > 0  # Should have missing required parameter
        
        # Check specific missing parameter
        missing_paths = {node.path for node in result.basic_comparison.only_in_source1}
        assert "Device.WiFi.RadioNumberOfEntries" in missing_paths
        
        print(f"Compliance score: {compliance_score:.2f}")
        print(f"Missing required parameters: {missing_required}")
        print(f"Validation errors: {validation_errors}")
    
    @pytest.mark.asyncio
    async def test_configuration_drift_detection(self):
        """Test detection of configuration drift over time."""
        # Create baseline configuration
        baseline_nodes = TestDataGenerator.generate_realistic_tr181_nodes(40)
        
        # Simulate configuration drift
        drifted_nodes = []
        for node in baseline_nodes:
            if "Channel" in node.path and node.data_type == "int":
                # Channel changed
                drifted_node = TR181Node(
                    path=node.path,
                    name=node.name,
                    data_type=node.data_type,
                    access=node.access,
                    value=11 if node.value == 6 else 6,  # Channel drift
                    description=node.description,
                    value_range=node.value_range
                )
                drifted_nodes.append(drifted_node)
            elif "Enable" in node.path and node.data_type == "boolean":
                # Some features disabled
                drifted_node = TR181Node(
                    path=node.path,
                    name=node.name,
                    data_type=node.data_type,
                    access=node.access,
                    value=False if node.value is True else node.value,  # Disabled
                    description=node.description
                )
                drifted_nodes.append(drifted_node)
            else:
                drifted_nodes.append(node)
        
        # Create device configurations
        device_config = DeviceConfig(
            type="cwmp",
            endpoint="http://device.example.com:7547",
            authentication={"username": "admin", "password": "password"},
            timeout=30,
            retry_count=3
        )
        
        # Create extractors
        baseline_hook = MockCWMPHook(baseline_nodes)
        baseline_extractor = CWMPExtractor(baseline_hook, device_config)
        
        current_hook = MockCWMPHook(drifted_nodes)
        current_extractor = CWMPExtractor(current_hook, device_config)
        
        # Extract and compare
        baseline_extracted = await baseline_extractor.extract()
        current_extracted = await current_extractor.extract()
        
        comparison_engine = ComparisonEngine()
        result = await comparison_engine.compare(baseline_extracted, current_extracted)
        
        # Verify drift detection
        assert len(result.differences) > 0  # Should detect configuration changes
        
        # Analyze drift types
        channel_drifts = [diff for diff in result.differences if "Channel" in diff.path]
        enable_drifts = [diff for diff in result.differences if "Enable" in diff.path]
        
        assert len(channel_drifts) > 0  # Should detect channel changes
        assert len(enable_drifts) > 0  # Should detect enable/disable changes
        
        # Calculate drift severity
        critical_drifts = [diff for diff in result.differences if diff.severity.value == "error"]
        warning_drifts = [diff for diff in result.differences if diff.severity.value == "warning"]
        
        print(f"Total configuration drifts detected: {len(result.differences)}")
        print(f"Critical drifts: {len(critical_drifts)}")
        print(f"Warning drifts: {len(warning_drifts)}")
        print(f"Channel drifts: {len(channel_drifts)}")
        print(f"Enable/disable drifts: {len(enable_drifts)}")
    
    @pytest.mark.asyncio
    async def test_device_migration_validation(self, tmp_path):
        """Test validation when migrating from one device to another."""
        # Create source device configuration
        source_nodes = TestDataGenerator.generate_realistic_tr181_nodes(50)
        
        # Create target device with different capabilities
        target_base_nodes = TestDataGenerator.generate_realistic_tr181_nodes(45)
        
        # Add some target-specific nodes
        target_specific_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.BeamForming",
                name="BeamForming",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="Beamforming support on target device"
            ),
            TR181Node(
                path="Device.WiFi.Radio.1.MU_MIMO",
                name="MU_MIMO",
                data_type="boolean",
                access=AccessLevel.READ_ONLY,
                value=True,
                description="MU-MIMO support on target device"
            )
        ]
        
        target_nodes = target_base_nodes + target_specific_nodes
        
        # Create migration plan (subset of source configuration to migrate)
        migration_nodes = source_nodes[:35]  # Migrate subset of configuration
        migration_file = tmp_path / "migration_plan.json"
        migration_manager = SubsetManager(str(migration_file))
        await migration_manager.save_subset(migration_nodes)
        
        # Create device configurations
        source_config = DeviceConfig(
            type="cwmp",
            endpoint="http://source-device.example.com:7547",
            authentication={"username": "admin", "password": "password"},
            timeout=30,
            retry_count=3
        )
        
        target_config = DeviceConfig(
            type="rest",
            endpoint="http://target-device.example.com:8080",
            authentication={"token": "target-token"},
            timeout=30,
            retry_count=3
        )
        
        # Create extractors
        source_hook = MockCWMPHook(source_nodes)
        source_extractor = CWMPExtractor(source_hook, source_config)
        
        target_hook = MockDeviceHook(target_nodes)
        target_extractor = HookBasedDeviceExtractor(target_hook, target_config)
        
        # Perform migration validation
        enhanced_engine = EnhancedComparisonEngine()
        
        migration_extracted = await migration_manager.extract()
        target_extracted = await target_extractor.extract()
        
        result = await enhanced_engine.compare_with_validation(
            migration_extracted, target_extracted, target_extractor
        )
        
        # Analyze migration compatibility
        summary = result.get_summary()
        
        migration_compatibility = (
            result.basic_comparison.summary.common_nodes / 
            len(migration_nodes)
        )
        
        missing_features = len(result.basic_comparison.only_in_source1)
        new_features = len(result.basic_comparison.only_in_source2)
        
        assert migration_compatibility > 0.5  # Should have reasonable compatibility
        
        # Check for target-specific features
        new_feature_paths = {node.path for node in result.basic_comparison.only_in_source2}
        assert "Device.WiFi.Radio.1.BeamForming" in new_feature_paths
        assert "Device.WiFi.Radio.1.MU_MIMO" in new_feature_paths
        
        print(f"Migration compatibility: {migration_compatibility:.2f}")
        print(f"Missing features on target: {missing_features}")
        print(f"New features on target: {new_features}")
        print(f"Validation errors: {summary['validation']['nodes_with_errors']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])