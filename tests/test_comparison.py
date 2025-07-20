"""Unit tests for the TR181 comparison engine."""

import pytest
from tr181_comparator.comparison import ComparisonEngine
from tr181_comparator.models import (
    TR181Node, AccessLevel, Severity, ValueRange, 
    TR181Event, TR181Function, NodeDifference
)


class TestComparisonEngine:
    """Test cases for the ComparisonEngine class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ComparisonEngine()
        
        # Create sample nodes for testing
        self.node1 = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6,
            description="WiFi channel number"
        )
        
        self.node2 = TR181Node(
            path="Device.WiFi.Radio.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="MyNetwork",
            description="Network SSID"
        )
        
        self.node3 = TR181Node(
            path="Device.WiFi.AccessPoint.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True,
            description="Access point enable status"
        )
    
    @pytest.mark.asyncio
    async def test_identical_sources_comparison(self):
        """Test comparison of identical node sources."""
        source1 = [self.node1, self.node2]
        source2 = [self.node1, self.node2]
        
        result = await self.engine.compare(source1, source2)
        
        assert len(result.only_in_source1) == 0
        assert len(result.only_in_source2) == 0
        assert len(result.differences) == 0
        assert result.summary.total_nodes_source1 == 2
        assert result.summary.total_nodes_source2 == 2
        assert result.summary.common_nodes == 2
        assert result.summary.differences_count == 0
    
    @pytest.mark.asyncio
    async def test_completely_different_sources(self):
        """Test comparison of completely different node sources."""
        source1 = [self.node1, self.node2]
        source2 = [self.node3]
        
        result = await self.engine.compare(source1, source2)
        
        assert len(result.only_in_source1) == 2
        assert len(result.only_in_source2) == 1
        assert len(result.differences) == 0
        assert result.summary.total_nodes_source1 == 2
        assert result.summary.total_nodes_source2 == 1
        assert result.summary.common_nodes == 0
        assert result.summary.differences_count == 0
        
        # Check that correct nodes are in each unique list
        source1_paths = {node.path for node in result.only_in_source1}
        source2_paths = {node.path for node in result.only_in_source2}
        
        assert "Device.WiFi.Radio.1.Channel" in source1_paths
        assert "Device.WiFi.Radio.1.SSID" in source1_paths
        assert "Device.WiFi.AccessPoint.1.Enable" in source2_paths
    
    @pytest.mark.asyncio
    async def test_partial_overlap_with_differences(self):
        """Test comparison with partial overlap and property differences."""
        # Create modified version of node1 with different properties
        modified_node1 = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="string",  # Different data type
            access=AccessLevel.READ_ONLY,  # Different access level
            value=11,  # Different value
            description="Modified channel description"  # Different description
        )
        
        source1 = [self.node1, self.node2]
        source2 = [modified_node1, self.node3]
        
        result = await self.engine.compare(source1, source2)
        
        assert len(result.only_in_source1) == 1  # node2
        assert len(result.only_in_source2) == 1  # node3
        assert len(result.differences) > 0  # Should have differences for modified_node1
        assert result.summary.common_nodes == 1  # Only Channel node is common
        
        # Check specific differences
        differences_by_property = {diff.property: diff for diff in result.differences}
        
        assert "data_type" in differences_by_property
        assert differences_by_property["data_type"].severity == Severity.ERROR
        assert differences_by_property["data_type"].source1_value == "int"
        assert differences_by_property["data_type"].source2_value == "string"
        
        assert "access" in differences_by_property
        assert differences_by_property["access"].severity == Severity.WARNING
        assert differences_by_property["access"].source1_value == "read-write"
        assert differences_by_property["access"].source2_value == "read-only"
        
        assert "value" in differences_by_property
        assert differences_by_property["value"].severity == Severity.INFO
        assert differences_by_property["value"].source1_value == 6
        assert differences_by_property["value"].source2_value == 11
    
    @pytest.mark.asyncio
    async def test_value_range_differences(self):
        """Test detection of value range differences."""
        range1 = ValueRange(min_value=1, max_value=11, allowed_values=[1, 6, 11])
        range2 = ValueRange(min_value=1, max_value=13, allowed_values=[1, 6, 11, 13])
        
        node_with_range1 = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value_range=range1
        )
        
        node_with_range2 = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value_range=range2
        )
        
        source1 = [node_with_range1]
        source2 = [node_with_range2]
        
        result = await self.engine.compare(source1, source2)
        
        assert len(result.differences) == 1
        assert result.differences[0].property == "value_range"
        assert result.differences[0].severity == Severity.WARNING
    
    @pytest.mark.asyncio
    async def test_events_and_functions_differences(self):
        """Test detection of events and functions differences."""
        event1 = TR181Event(name="ChannelChange", path="Device.WiFi.Radio.1", parameters=["Channel"])
        event2 = TR181Event(name="SSIDChange", path="Device.WiFi.Radio.1", parameters=["SSID"])
        
        function1 = TR181Function(
            name="Reset", 
            path="Device.WiFi.Radio.1", 
            input_parameters=["Type"], 
            output_parameters=["Status"]
        )
        
        node_with_events1 = TR181Node(
            path="Device.WiFi.Radio.1",
            name="Radio",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            events=[event1],
            functions=[function1]
        )
        
        node_with_events2 = TR181Node(
            path="Device.WiFi.Radio.1",
            name="Radio",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            events=[event1, event2],  # Different events
            functions=[]  # No functions
        )
        
        source1 = [node_with_events1]
        source2 = [node_with_events2]
        
        result = await self.engine.compare(source1, source2)
        
        # Should detect differences in events and functions
        differences_by_property = {diff.property: diff for diff in result.differences}
        
        assert "events" in differences_by_property
        assert differences_by_property["events"].source1_value == 1  # 1 event
        assert differences_by_property["events"].source2_value == 2  # 2 events
        
        assert "functions" in differences_by_property
        assert differences_by_property["functions"].source1_value == 1  # 1 function
        assert differences_by_property["functions"].source2_value == 0  # 0 functions
    
    @pytest.mark.asyncio
    async def test_children_differences(self):
        """Test detection of children list differences."""
        node_with_children1 = TR181Node(
            path="Device.WiFi",
            name="WiFi",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            children=["Device.WiFi.Radio.1", "Device.WiFi.AccessPoint.1"]
        )
        
        node_with_children2 = TR181Node(
            path="Device.WiFi",
            name="WiFi",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            children=["Device.WiFi.Radio.1", "Device.WiFi.Radio.2", "Device.WiFi.AccessPoint.1"]
        )
        
        source1 = [node_with_children1]
        source2 = [node_with_children2]
        
        result = await self.engine.compare(source1, source2)
        
        assert len(result.differences) == 1
        assert result.differences[0].property == "children"
        assert result.differences[0].severity == Severity.INFO
    
    @pytest.mark.asyncio
    async def test_null_value_handling(self):
        """Test proper handling of null/None values in comparisons."""
        node_with_null_value = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=None  # Null value
        )
        
        node_with_value = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6
        )
        
        source1 = [node_with_null_value]
        source2 = [node_with_value]
        
        result = await self.engine.compare(source1, source2)
        
        assert len(result.differences) == 1
        assert result.differences[0].property == "value"
        assert result.differences[0].source1_value is None
        assert result.differences[0].source2_value == 6
    
    @pytest.mark.asyncio
    async def test_custom_node_differences(self):
        """Test detection of custom node flag differences."""
        standard_node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            is_custom=False
        )
        
        custom_node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            is_custom=True
        )
        
        source1 = [standard_node]
        source2 = [custom_node]
        
        result = await self.engine.compare(source1, source2)
        
        assert len(result.differences) == 1
        assert result.differences[0].property == "is_custom"
        assert result.differences[0].source1_value is False
        assert result.differences[0].source2_value is True
        assert result.differences[0].severity == Severity.INFO
    
    @pytest.mark.asyncio
    async def test_empty_sources(self):
        """Test comparison of empty sources."""
        result = await self.engine.compare([], [])
        
        assert len(result.only_in_source1) == 0
        assert len(result.only_in_source2) == 0
        assert len(result.differences) == 0
        assert result.summary.total_nodes_source1 == 0
        assert result.summary.total_nodes_source2 == 0
        assert result.summary.common_nodes == 0
        assert result.summary.differences_count == 0
    
    @pytest.mark.asyncio
    async def test_one_empty_source(self):
        """Test comparison when one source is empty."""
        source1 = [self.node1, self.node2]
        source2 = []
        
        result = await self.engine.compare(source1, source2)
        
        assert len(result.only_in_source1) == 2
        assert len(result.only_in_source2) == 0
        assert len(result.differences) == 0
        assert result.summary.total_nodes_source1 == 2
        assert result.summary.total_nodes_source2 == 0
        assert result.summary.common_nodes == 0
    
    def test_build_node_map(self):
        """Test the node map building functionality."""
        nodes = [self.node1, self.node2, self.node3]
        node_map = self.engine._build_node_map(nodes)
        
        assert len(node_map) == 3
        assert "Device.WiFi.Radio.1.Channel" in node_map
        assert "Device.WiFi.Radio.1.SSID" in node_map
        assert "Device.WiFi.AccessPoint.1.Enable" in node_map
        assert node_map["Device.WiFi.Radio.1.Channel"] == self.node1
    
    def test_find_unique_nodes(self):
        """Test finding nodes unique to one source."""
        map1 = {"path1": self.node1, "path2": self.node2}
        map2 = {"path2": self.node2, "path3": self.node3}
        
        unique_to_map1 = self.engine._find_unique_nodes(map1, map2)
        unique_to_map2 = self.engine._find_unique_nodes(map2, map1)
        
        assert len(unique_to_map1) == 1
        assert unique_to_map1[0] == self.node1
        
        assert len(unique_to_map2) == 1
        assert unique_to_map2[0] == self.node3
    
    def test_value_ranges_differ(self):
        """Test value range difference detection."""
        range1 = ValueRange(min_value=1, max_value=10)
        range2 = ValueRange(min_value=1, max_value=11)
        range3 = ValueRange(min_value=1, max_value=10)
        
        assert self.engine._value_ranges_differ(range1, range2) is True
        assert self.engine._value_ranges_differ(range1, range3) is False
        assert self.engine._value_ranges_differ(None, range1) is True
        assert self.engine._value_ranges_differ(None, None) is False
    
    def test_lists_differ(self):
        """Test list difference detection."""
        list1 = ["a", "b", "c"]
        list2 = ["c", "b", "a"]  # Same elements, different order
        list3 = ["a", "b", "d"]  # Different elements
        
        assert self.engine._lists_differ(list1, list2) is False  # Order doesn't matter
        assert self.engine._lists_differ(list1, list3) is True
        assert self.engine._lists_differ(None, list1) is True
        assert self.engine._lists_differ(None, None) is False