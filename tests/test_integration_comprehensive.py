"""Comprehensive integration tests for TR181 node comparator."""

import pytest
import asyncio
import time
from typing import List, Dict, Any
from unittest.mock import AsyncMock

from tr181_comparator.models import (
    TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function
)
from tr181_comparator.comparison import ComparisonEngine
from tr181_comparator.extractors import CWMPExtractor, OperatorRequirementManager
from tr181_comparator.hooks import DeviceConfig
from tr181_comparator.errors import ConnectionError


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


@pytest.fixture
def realistic_tr181_nodes():
    """Generate realistic TR181 nodes for testing."""
    return TestDataGenerator.generate_realistic_tr181_nodes(50)


@pytest.fixture
def large_tr181_dataset():
    """Generate large TR181 dataset for performance testing."""
    return TestDataGenerator.generate_realistic_tr181_nodes(1000)


@pytest.fixture
def cwmp_device_config():
    """Create CWMP device configuration for testing."""
    return DeviceConfig(
        type="cwmp",
        endpoint="http://cwmp-device.example.com:7547",
        authentication={"username": "admin", "password": "password"},
        timeout=30,
        retry_count=3
    )


class TestEndToEndComparisons:
    """End-to-end integration tests for all comparison scenarios."""
    
    @pytest.mark.asyncio
    async def test_cwmp_vs_operator_requirement_comparison(self, realistic_tr181_nodes, cwmp_device_config, tmp_path):
        """Test CWMP vs operator requirement comparison scenario."""
        # Create CWMP extractor with mock hook
        cwmp_hook = MockCWMPHook(realistic_tr181_nodes)
        cwmp_extractor = CWMPExtractor(cwmp_hook, cwmp_device_config)
        
        # Create operator requirement with modified nodes
        operator_requirement_nodes = TestDataGenerator.create_modified_nodes(realistic_tr181_nodes[:30], 0.2)
        operator_requirement_file = tmp_path / "test_operator_requirement.json"
        operator_requirement_manager = OperatorRequirementManager(str(operator_requirement_file))
        await operator_requirement_manager.save_operator_requirement(operator_requirement_nodes)
        
        # Perform comparison
        comparison_engine = ComparisonEngine()
        
        # Extract from both sources
        cwmp_nodes = await cwmp_extractor.extract()
        operator_requirement_nodes_extracted = await operator_requirement_manager.extract()
        
        # Compare
        result = await comparison_engine.compare(cwmp_nodes, operator_requirement_nodes_extracted)
        
        # Verify results
        assert result.summary.total_nodes_source1 == len(realistic_tr181_nodes)
        assert result.summary.total_nodes_source2 == 30
        assert result.summary.common_nodes <= 30
        assert len(result.only_in_source1) > 0  # CWMP has more nodes
        
        print(f"CWMP nodes: {len(cwmp_nodes)}")
        print(f"Operator Requirement nodes: {len(operator_requirement_nodes_extracted)}")
        print(f"Common nodes: {result.summary.common_nodes}")
        print(f"Differences: {len(result.differences)}")


class TestPerformanceAndScalability:
    """Performance tests for large datasets and scalability."""
    
    @pytest.mark.asyncio
    async def test_large_dataset_comparison_performance(self, large_tr181_dataset):
        """Test comparison performance with large datasets (1000+ nodes)."""
        # Create two large datasets
        source1_nodes = large_tr181_dataset
        source2_nodes = TestDataGenerator.create_modified_nodes(large_tr181_dataset, 0.1)
        
        # Measure comparison time
        comparison_engine = ComparisonEngine()
        start_time = time.time()
        
        result = await comparison_engine.compare(source1_nodes, source2_nodes)
        
        end_time = time.time()
        comparison_time = end_time - start_time
        
        # Performance assertions
        assert comparison_time < 10.0  # Should complete within 10 seconds
        assert result.summary.total_nodes_source1 == 1000
        assert result.summary.total_nodes_source2 == 1000
        assert result.summary.common_nodes == 1000
        
        # Should have differences due to modifications
        assert len(result.differences) > 0
        
        print(f"Large dataset comparison completed in {comparison_time:.2f} seconds")
    
    @pytest.mark.asyncio
    async def test_extraction_performance_with_batching(self, large_tr181_dataset, cwmp_device_config):
        """Test extraction performance with large datasets and batching."""
        # Create CWMP extractor with large dataset
        cwmp_hook = MockCWMPHook(large_tr181_dataset)
        cwmp_extractor = CWMPExtractor(cwmp_hook, cwmp_device_config)
        
        # Measure extraction time
        start_time = time.time()
        
        extracted_nodes = await cwmp_extractor.extract()
        
        end_time = time.time()
        extraction_time = end_time - start_time
        
        # Performance assertions
        assert extraction_time < 15.0  # Should complete within 15 seconds
        assert len(extracted_nodes) == 1000
        
        print(f"Large dataset extraction completed in {extraction_time:.2f} seconds")


class TestErrorScenariosAndRecovery:
    """Test error scenarios and recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_connection_failure_recovery(self, realistic_tr181_nodes, cwmp_device_config):
        """Test recovery from connection failures."""
        # Create hook that initially fails then succeeds
        cwmp_hook = MockCWMPHook(realistic_tr181_nodes)
        cwmp_hook.should_fail = True
        
        cwmp_extractor = CWMPExtractor(cwmp_hook, cwmp_device_config)
        
        # First attempt should fail
        with pytest.raises(ConnectionError):
            await cwmp_extractor.extract()
        
        # Fix connection and retry
        cwmp_hook.should_fail = False
        
        # Should succeed on retry
        nodes = await cwmp_extractor.extract()
        assert len(nodes) == len(realistic_tr181_nodes)
    
    @pytest.mark.asyncio
    async def test_comparison_with_empty_sources(self):
        """Test comparison behavior with empty sources."""
        comparison_engine = ComparisonEngine()
        
        # Test empty vs empty
        result = await comparison_engine.compare([], [])
        assert result.summary.total_nodes_source1 == 0
        assert result.summary.total_nodes_source2 == 0
        assert result.summary.common_nodes == 0
        assert len(result.differences) == 0
        
        # Test empty vs non-empty
        nodes = TestDataGenerator.generate_realistic_tr181_nodes(10)
        result = await comparison_engine.compare([], nodes)
        assert result.summary.total_nodes_source1 == 0
        assert result.summary.total_nodes_source2 == 10
        assert len(result.only_in_source2) == 10
        
        # Test non-empty vs empty
        result = await comparison_engine.compare(nodes, [])
        assert result.summary.total_nodes_source1 == 10
        assert result.summary.total_nodes_source2 == 0
        assert len(result.only_in_source1) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])