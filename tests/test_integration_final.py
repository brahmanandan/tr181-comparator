"""Final comprehensive integration tests for TR181 node comparator."""

import pytest
import asyncio
import time
from typing import List, Dict, Any

from tr181_comparator.models import TR181Node, AccessLevel, ValueRange
from tr181_comparator.comparison import ComparisonEngine
from tr181_comparator.extractors import SubsetManager
from tr181_comparator.errors import ConnectionError


def generate_test_nodes(count: int = 50) -> List[TR181Node]:
    """Generate test TR181 nodes."""
    nodes = []
    
    # Core device info nodes
    nodes.extend([
        TR181Node(
            path="Device.DeviceInfo.Manufacturer",
            name="Manufacturer",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="TestCorp"
        ),
        TR181Node(
            path="Device.DeviceInfo.ModelName",
            name="ModelName",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="TestDevice"
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6,
            value_range=ValueRange(min_value=1, max_value=165)
        )
    ])
    
    # Generate additional test nodes
    for i in range(len(nodes), count):
        nodes.append(
            TR181Node(
                path=f"Device.Test.Parameter.{i}",
                name=f"Parameter{i}",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value=f"value_{i}"
            )
        )
    
    return nodes


def create_modified_nodes(nodes: List[TR181Node], ratio: float = 0.3) -> List[TR181Node]:
    """Create modified version of nodes."""
    modified = []
    mod_count = int(len(nodes) * ratio)
    
    for i, node in enumerate(nodes):
        if i < mod_count:
            # Modify this node
            modified_node = TR181Node(
                path=node.path,
                name=node.name,
                data_type=node.data_type,
                access=AccessLevel.READ_ONLY if node.access == AccessLevel.READ_WRITE else node.access,
                value=f"modified_{node.value}" if isinstance(node.value, str) else node.value
            )
            modified.append(modified_node)
        else:
            modified.append(node)
    
    return modified


class TestComprehensiveIntegration:
    """Comprehensive integration tests."""
    
    @pytest.mark.asyncio
    async def test_subset_comparison_scenario(self, tmp_path):
        """Test subset vs subset comparison scenario."""
        # Generate test data
        source_nodes = generate_test_nodes(30)
        target_nodes = create_modified_nodes(source_nodes, 0.2)
        
        # Create subset files
        source_file = tmp_path / "source_subset.json"
        target_file = tmp_path / "target_subset.json"
        
        source_manager = SubsetManager(str(source_file))
        target_manager = SubsetManager(str(target_file))
        
        # Save subsets
        await source_manager.save_subset(source_nodes)
        await target_manager.save_subset(target_nodes)
        
        # Extract and compare
        source_extracted = await source_manager.extract()
        target_extracted = await target_manager.extract()
        
        engine = ComparisonEngine()
        result = await engine.compare(source_extracted, target_extracted)
        
        # Verify results
        assert result.summary.total_nodes_source1 == 30
        assert result.summary.total_nodes_source2 == 30
        assert result.summary.common_nodes == 30
        assert len(result.differences) > 0  # Should have differences due to modifications
        
        print(f"Comparison completed: {len(result.differences)} differences found")
    
    @pytest.mark.asyncio
    async def test_large_dataset_performance(self):
        """Test performance with large datasets."""
        # Generate large datasets
        large_dataset1 = generate_test_nodes(1000)
        large_dataset2 = create_modified_nodes(large_dataset1, 0.1)
        
        # Measure comparison time
        engine = ComparisonEngine()
        start_time = time.time()
        
        result = await engine.compare(large_dataset1, large_dataset2)
        
        end_time = time.time()
        comparison_time = end_time - start_time
        
        # Performance assertions
        assert comparison_time < 5.0  # Should complete within 5 seconds
        assert result.summary.total_nodes_source1 == 1000
        assert result.summary.total_nodes_source2 == 1000
        assert result.summary.common_nodes == 1000
        assert len(result.differences) > 0
        
        print(f"Large dataset comparison completed in {comparison_time:.3f} seconds")
    
    @pytest.mark.asyncio
    async def test_empty_dataset_handling(self):
        """Test handling of empty datasets."""
        engine = ComparisonEngine()
        
        # Empty vs empty
        result = await engine.compare([], [])
        assert result.summary.total_nodes_source1 == 0
        assert result.summary.total_nodes_source2 == 0
        assert result.summary.common_nodes == 0
        assert len(result.differences) == 0
        
        # Empty vs non-empty
        nodes = generate_test_nodes(10)
        result = await engine.compare([], nodes)
        assert result.summary.total_nodes_source1 == 0
        assert result.summary.total_nodes_source2 == 10
        assert len(result.only_in_source2) == 10
        
        print("Empty dataset handling verified")
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent comparison operations."""
        # Generate multiple datasets
        datasets = [generate_test_nodes(100) for _ in range(5)]
        modified_datasets = [create_modified_nodes(ds, 0.2) for ds in datasets]
        
        # Create comparison tasks
        engine = ComparisonEngine()
        tasks = [
            engine.compare(datasets[i], modified_datasets[i])
            for i in range(5)
        ]
        
        # Run concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Verify all completed successfully
        assert len(results) == 5
        for result in results:
            assert result.summary.total_nodes_source1 == 100
            assert result.summary.total_nodes_source2 == 100
            assert len(result.differences) > 0
        
        concurrent_time = end_time - start_time
        print(f"Concurrent operations completed in {concurrent_time:.3f} seconds")
    
    @pytest.mark.asyncio
    async def test_subset_validation_scenario(self, tmp_path):
        """Test subset validation and error handling."""
        # Create valid subset
        valid_nodes = generate_test_nodes(20)
        valid_file = tmp_path / "valid_subset.json"
        valid_manager = SubsetManager(str(valid_file))
        await valid_manager.save_subset(valid_nodes)
        
        # Test extraction
        extracted = await valid_manager.extract()
        assert len(extracted) == 20
        
        # Test validation
        validation_result = await valid_manager.validate()
        assert validation_result.is_valid
        
        print("Subset validation completed successfully")
    
    def test_node_data_integrity(self):
        """Test TR181 node data integrity."""
        # Test node creation with all fields
        node = TR181Node(
            path="Device.Test.ComplexParameter",
            name="ComplexParameter",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="test_value",
            description="Test parameter with all fields",
            value_range=ValueRange(max_length=50, pattern=r"^test_.*")
        )
        
        # Verify all fields
        assert node.path == "Device.Test.ComplexParameter"
        assert node.name == "ComplexParameter"
        assert node.data_type == "string"
        assert node.access == AccessLevel.READ_WRITE
        assert node.value == "test_value"
        assert node.description == "Test parameter with all fields"
        assert node.value_range.max_length == 50
        assert node.value_range.pattern == r"^test_.*"
        
        print("Node data integrity verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])