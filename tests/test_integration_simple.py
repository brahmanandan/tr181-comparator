"""Simple integration test to verify basic functionality."""

import pytest
from tr181_comparator.models import TR181Node, AccessLevel
from tr181_comparator.comparison import ComparisonEngine


class TestBasicIntegration:
    """Basic integration tests."""
    
    @pytest.mark.asyncio
    async def test_simple_comparison(self):
        """Test basic comparison functionality."""
        # Create simple test nodes
        node1 = TR181Node(
            path="Device.Test.Parameter1",
            name="Parameter1",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="test1"
        )
        
        node2 = TR181Node(
            path="Device.Test.Parameter2",
            name="Parameter2",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="test2"
        )
        
        # Create comparison engine
        engine = ComparisonEngine()
        
        # Test comparison
        result = await engine.compare([node1], [node2])
        
        # Verify results
        assert result.summary.total_nodes_source1 == 1
        assert result.summary.total_nodes_source2 == 1
        assert result.summary.common_nodes == 0
        assert len(result.only_in_source1) == 1
        assert len(result.only_in_source2) == 1
        assert len(result.differences) == 0
    
    def test_node_creation(self):
        """Test TR181Node creation."""
        node = TR181Node(
            path="Device.Test.Parameter",
            name="Parameter",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="test"
        )
        
        assert node.path == "Device.Test.Parameter"
        assert node.name == "Parameter"
        assert node.data_type == "string"
        assert node.access == AccessLevel.READ_WRITE
        assert node.value == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])