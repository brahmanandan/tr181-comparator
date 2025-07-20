"""Unit tests for core data models."""

import pytest
from tr181_comparator.models import (
    TR181Node, ValueRange, TR181Event, TR181Function,
    AccessLevel, Severity
)


class TestAccessLevel:
    """Test AccessLevel enum."""
    
    def test_access_level_values(self):
        """Test that AccessLevel enum has correct values."""
        assert AccessLevel.READ_ONLY.value == "read-only"
        assert AccessLevel.READ_WRITE.value == "read-write"
        assert AccessLevel.WRITE_ONLY.value == "write-only"


class TestSeverity:
    """Test Severity enum."""
    
    def test_severity_values(self):
        """Test that Severity enum has correct values."""
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"


class TestValueRange:
    """Test ValueRange dataclass."""
    
    def test_value_range_creation(self):
        """Test ValueRange can be created with various constraints."""
        # Test with all None values
        range1 = ValueRange()
        assert range1.min_value is None
        assert range1.max_value is None
        assert range1.allowed_values is None
        assert range1.pattern is None
        assert range1.max_length is None
        
        # Test with numeric range
        range2 = ValueRange(min_value=0, max_value=100)
        assert range2.min_value == 0
        assert range2.max_value == 100
        
        # Test with enumerated values
        range3 = ValueRange(allowed_values=["auto", "manual", "disabled"])
        assert range3.allowed_values == ["auto", "manual", "disabled"]
        
        # Test with string constraints
        range4 = ValueRange(pattern=r"^[A-Z]{2,8}$", max_length=8)
        assert range4.pattern == r"^[A-Z]{2,8}$"
        assert range4.max_length == 8


class TestTR181Event:
    """Test TR181Event dataclass."""
    
    def test_event_creation(self):
        """Test TR181Event creation with required fields."""
        event = TR181Event(
            name="WiFiRadioStatsUpdate",
            path="Device.WiFi.Radio.1.Stats",
            parameters=["Device.WiFi.Radio.1.Stats.BytesSent", "Device.WiFi.Radio.1.Stats.BytesReceived"]
        )
        assert event.name == "WiFiRadioStatsUpdate"
        assert event.path == "Device.WiFi.Radio.1.Stats"
        assert len(event.parameters) == 2
        assert event.description is None
        
    def test_event_with_description(self):
        """Test TR181Event creation with optional description."""
        event = TR181Event(
            name="TestEvent",
            path="Device.Test",
            parameters=["Device.Test.Param1"],
            description="Test event description"
        )
        assert event.description == "Test event description"


class TestTR181Function:
    """Test TR181Function dataclass."""
    
    def test_function_creation(self):
        """Test TR181Function creation with required fields."""
        function = TR181Function(
            name="WiFiScan",
            path="Device.WiFi.Radio.1.Scan()",
            input_parameters=["Device.WiFi.Radio.1.ScanSettings.SSID"],
            output_parameters=["Device.WiFi.Radio.1.ScanResults.NumberOfEntries"]
        )
        assert function.name == "WiFiScan"
        assert function.path == "Device.WiFi.Radio.1.Scan()"
        assert len(function.input_parameters) == 1
        assert len(function.output_parameters) == 1
        assert function.description is None
        
    def test_function_with_description(self):
        """Test TR181Function creation with optional description."""
        function = TR181Function(
            name="TestFunction",
            path="Device.Test.Function()",
            input_parameters=[],
            output_parameters=[],
            description="Test function description"
        )
        assert function.description == "Test function description"


class TestTR181Node:
    """Test TR181Node dataclass."""
    
    def test_minimal_node_creation(self):
        """Test TR181Node creation with minimal required fields."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        assert node.path == "Device.WiFi.Radio.1.Channel"
        assert node.name == "Channel"
        assert node.data_type == "int"
        assert node.access == AccessLevel.READ_WRITE
        assert node.value is None
        assert node.description is None
        assert node.parent is None
        assert node.children == []
        assert node.is_object is False
        assert node.is_custom is False
        assert node.value_range is None
        assert node.events == []
        assert node.functions == []
    
    def test_complete_node_creation(self):
        """Test TR181Node creation with all fields populated."""
        value_range = ValueRange(min_value=1, max_value=11)
        event = TR181Event("ChannelChange", "Device.WiFi.Radio.1.Channel", [])
        function = TR181Function("SetChannel", "Device.WiFi.Radio.1.SetChannel()", ["Channel"], [])
        
        node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6,
            description="WiFi channel number",
            parent="Device.WiFi.Radio.1",
            children=["Device.WiFi.Radio.1.Channel.Stats"],
            is_object=False,
            is_custom=False,
            value_range=value_range,
            events=[event],
            functions=[function]
        )
        
        assert node.value == 6
        assert node.description == "WiFi channel number"
        assert node.parent == "Device.WiFi.Radio.1"
        assert node.children == ["Device.WiFi.Radio.1.Channel.Stats"]
        assert node.value_range == value_range
        assert len(node.events) == 1
        assert len(node.functions) == 1
    
    def test_node_validation_empty_path(self):
        """Test that TR181Node validation fails with empty path."""
        with pytest.raises(ValueError, match="TR181Node path cannot be empty"):
            TR181Node(
                path="",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE
            )
    
    def test_node_validation_empty_name(self):
        """Test that TR181Node validation fails with empty name."""
        with pytest.raises(ValueError, match="TR181Node name cannot be empty"):
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="",
                data_type="int",
                access=AccessLevel.READ_WRITE
            )
    
    def test_node_validation_empty_data_type(self):
        """Test that TR181Node validation fails with empty data_type."""
        with pytest.raises(ValueError, match="TR181Node data_type cannot be empty"):
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="",
                access=AccessLevel.READ_WRITE
            )
    
    def test_node_validation_invalid_access(self):
        """Test that TR181Node validation fails with invalid access level."""
        with pytest.raises(ValueError, match="TR181Node access must be an AccessLevel enum"):
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access="invalid-access"  # Should be AccessLevel enum
            )
    
    def test_node_object_type(self):
        """Test TR181Node for object-type nodes."""
        node = TR181Node(
            path="Device.WiFi.Radio.1",
            name="Radio",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            children=[
                "Device.WiFi.Radio.1.Channel",
                "Device.WiFi.Radio.1.SSID",
                "Device.WiFi.Radio.1.Enable"
            ]
        )
        assert node.is_object is True
        assert len(node.children) == 3
    
    def test_node_custom_type(self):
        """Test TR181Node for custom (non-standard) nodes."""
        node = TR181Node(
            path="Device.Custom.VendorSpecific.Parameter",
            name="Parameter",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            is_custom=True
        )
        assert node.is_custom is True
    
    def test_node_with_complex_value_range(self):
        """Test TR181Node with complex value range constraints."""
        value_range = ValueRange(
            min_value=0,
            max_value=255,
            allowed_values=[0, 1, 6, 11],
            pattern=r"^\d{1,3}$",
            max_length=3
        )
        
        node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value_range=value_range
        )
        
        assert node.value_range.min_value == 0
        assert node.value_range.max_value == 255
        assert node.value_range.allowed_values == [0, 1, 6, 11]
        assert node.value_range.pattern == r"^\d{1,3}$"
        assert node.value_range.max_length == 3