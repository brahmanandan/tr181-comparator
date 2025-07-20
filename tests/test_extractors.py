"""Unit tests for extractor interface and base functionality."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from tr181_comparator.extractors import (
    SourceInfo, ValidationResult, NodeExtractor,
    ConnectionError, ValidationError
)
from tr181_comparator.models import TR181Node, AccessLevel


class TestSourceInfo:
    """Test SourceInfo dataclass."""
    
    def test_source_info_creation(self):
        """Test SourceInfo creation with required fields."""
        timestamp = datetime.now()
        source = SourceInfo(
            type="cwmp",
            identifier="http://192.168.1.1:7547/cwmp",
            timestamp=timestamp,
            metadata={"version": "1.0", "device_id": "12345"}
        )
        
        assert source.type == "cwmp"
        assert source.identifier == "http://192.168.1.1:7547/cwmp"
        assert source.timestamp == timestamp
        assert source.metadata["version"] == "1.0"
        assert source.metadata["device_id"] == "12345"
    
    def test_source_info_minimal(self):
        """Test SourceInfo creation with minimal fields."""
        timestamp = datetime.now()
        source = SourceInfo(
            type="subset",
            identifier="/path/to/subset.json",
            timestamp=timestamp,
            metadata={}
        )
        
        assert source.type == "subset"
        assert source.identifier == "/path/to/subset.json"
        assert source.timestamp == timestamp
        assert source.metadata == {}
    
    def test_source_info_auto_metadata_init(self):
        """Test that metadata is auto-initialized to empty dict."""
        timestamp = datetime.now()
        source = SourceInfo(
            type="device",
            identifier="device-001",
            timestamp=timestamp,
            metadata=None
        )
        
        assert source.metadata == {}
    
    def test_source_info_validation_empty_type(self):
        """Test SourceInfo validation fails with empty type."""
        with pytest.raises(ValueError, match="SourceInfo type cannot be empty"):
            SourceInfo(
                type="",
                identifier="test",
                timestamp=datetime.now(),
                metadata={}
            )
    
    def test_source_info_validation_empty_identifier(self):
        """Test SourceInfo validation fails with empty identifier."""
        with pytest.raises(ValueError, match="SourceInfo identifier cannot be empty"):
            SourceInfo(
                type="test",
                identifier="",
                timestamp=datetime.now(),
                metadata={}
            )
    
    def test_source_info_validation_invalid_timestamp(self):
        """Test SourceInfo validation fails with invalid timestamp."""
        with pytest.raises(ValueError, match="SourceInfo timestamp must be a datetime object"):
            SourceInfo(
                type="test",
                identifier="test",
                timestamp="2023-01-01",  # String instead of datetime
                metadata={}
            )


class TestValidationResult:
    """Test ValidationResult class."""
    
    def test_validation_result_initial_state(self):
        """Test ValidationResult initial state."""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert bool(result) is True
        assert str(result) == "Validation passed"
    
    def test_add_error(self):
        """Test adding errors to validation result."""
        result = ValidationResult()
        result.add_error("Test error message")
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0] == "Test error message"
        assert bool(result) is False
        assert "Validation failed with 1 error(s)" in str(result)
    
    def test_add_warning(self):
        """Test adding warnings to validation result."""
        result = ValidationResult()
        result.add_warning("Test warning message")
        
        assert result.is_valid is True  # Warnings don't affect validity
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning message"
        assert bool(result) is True
        assert "1 warning(s)" in str(result)
    
    def test_add_multiple_errors_and_warnings(self):
        """Test adding multiple errors and warnings."""
        result = ValidationResult()
        result.add_error("Error 1")
        result.add_error("Error 2")
        result.add_warning("Warning 1")
        result.add_warning("Warning 2")
        
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 2
        assert bool(result) is False
        
        str_result = str(result)
        assert "2 error(s)" in str_result
        assert "2 warning(s)" in str_result
    
    def test_merge_validation_results(self):
        """Test merging validation results."""
        result1 = ValidationResult()
        result1.add_error("Error from result1")
        result1.add_warning("Warning from result1")
        
        result2 = ValidationResult()
        result2.add_error("Error from result2")
        result2.add_warning("Warning from result2")
        
        result1.merge(result2)
        
        assert result1.is_valid is False
        assert len(result1.errors) == 2
        assert len(result1.warnings) == 2
        assert "Error from result1" in result1.errors
        assert "Error from result2" in result1.errors
        assert "Warning from result1" in result1.warnings
        assert "Warning from result2" in result1.warnings
    
    def test_merge_valid_with_invalid(self):
        """Test merging valid result with invalid result."""
        valid_result = ValidationResult()
        valid_result.add_warning("Just a warning")
        
        invalid_result = ValidationResult()
        invalid_result.add_error("An error")
        
        valid_result.merge(invalid_result)
        
        assert valid_result.is_valid is False
        assert len(valid_result.errors) == 1
        assert len(valid_result.warnings) == 1


class MockExtractor(NodeExtractor):
    """Mock implementation of NodeExtractor for testing."""
    
    def __init__(self, source_identifier: str, metadata=None, 
                 extract_result=None, validate_result=None):
        super().__init__(source_identifier, metadata)
        self._extract_result = extract_result or []
        self._validate_result = validate_result or ValidationResult()
    
    async def extract(self):
        """Mock extract method."""
        self._update_extraction_timestamp()
        return self._extract_result
    
    async def validate(self):
        """Mock validate method."""
        return self._validate_result
    
    def get_source_info(self):
        """Mock get_source_info method."""
        return SourceInfo(
            type="mock",
            identifier=self._source_identifier,
            timestamp=self._extraction_timestamp or datetime.now(),
            metadata=self._metadata
        )


class TestNodeExtractor:
    """Test NodeExtractor abstract base class."""
    
    def test_extractor_initialization(self):
        """Test NodeExtractor initialization."""
        extractor = MockExtractor("test-source", {"key": "value"})
        
        assert extractor._source_identifier == "test-source"
        assert extractor._metadata == {"key": "value"}
        assert extractor._extraction_timestamp is None
    
    def test_extractor_initialization_no_metadata(self):
        """Test NodeExtractor initialization without metadata."""
        extractor = MockExtractor("test-source")
        
        assert extractor._source_identifier == "test-source"
        assert extractor._metadata == {}
    
    @pytest.mark.asyncio
    async def test_extract_updates_timestamp(self):
        """Test that extract method updates extraction timestamp."""
        extractor = MockExtractor("test-source")
        
        assert extractor._extraction_timestamp is None
        
        await extractor.extract()
        
        assert extractor._extraction_timestamp is not None
        assert isinstance(extractor._extraction_timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_get_source_info(self):
        """Test get_source_info method."""
        metadata = {"version": "1.0", "type": "test"}
        extractor = MockExtractor("test-source", metadata)
        
        # Extract to set timestamp
        await extractor.extract()
        
        source_info = extractor.get_source_info()
        
        assert source_info.type == "mock"
        assert source_info.identifier == "test-source"
        assert source_info.timestamp == extractor._extraction_timestamp
        assert source_info.metadata == metadata
    
    def test_validate_extracted_nodes_empty(self):
        """Test validation of empty node list."""
        extractor = MockExtractor("test-source")
        result = extractor._validate_extracted_nodes([])
        
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "No TR181 nodes were extracted" in result.warnings[0]
    
    def test_validate_extracted_nodes_duplicate_paths(self):
        """Test validation catches duplicate node paths."""
        node1 = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        node2 = TR181Node(
            path="Device.WiFi.Radio.1.Channel",  # Duplicate path
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_extracted_nodes([node1, node2])
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Duplicate node path found: Device.WiFi.Radio.1.Channel" in result.errors[0]
    
    def test_validate_extracted_nodes_orphaned_children(self):
        """Test validation catches orphaned child references."""
        parent_node = TR181Node(
            path="Device.WiFi.Radio.1",
            name="Radio",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            children=["Device.WiFi.Radio.1.Channel", "Device.WiFi.Radio.1.NonExistent"]
        )
        child_node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            parent="Device.WiFi.Radio.1"
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_extracted_nodes([parent_node, child_node])
        
        assert result.is_valid is True  # Warnings don't affect validity
        assert len(result.warnings) == 1
        assert "references non-existent child: Device.WiFi.Radio.1.NonExistent" in result.warnings[0]
    
    def test_validate_extracted_nodes_orphaned_parent(self):
        """Test validation catches orphaned parent references."""
        child_node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            parent="Device.WiFi.Radio.1"  # Parent doesn't exist in the list
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_extracted_nodes([child_node])
        
        assert result.is_valid is True  # Warnings don't affect validity
        assert len(result.warnings) == 1
        assert "references non-existent parent: Device.WiFi.Radio.1" in result.warnings[0]
    
    def test_validate_single_node_path_conventions(self):
        """Test validation of TR181 path naming conventions."""
        # Valid node
        valid_node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        
        # Invalid node (doesn't start with Device.)
        invalid_node = TR181Node(
            path="System.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        
        # Node with lowercase component
        lowercase_node = TR181Node(
            path="Device.WiFi.radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        
        extractor = MockExtractor("test-source")
        
        valid_result = extractor._validate_single_node(valid_node)
        assert valid_result.is_valid is True
        assert len(valid_result.warnings) == 0
        
        invalid_result = extractor._validate_single_node(invalid_node)
        assert len(invalid_result.warnings) == 1
        assert "should start with 'Device.'" in invalid_result.warnings[0]
        
        lowercase_result = extractor._validate_single_node(lowercase_node)
        assert len(lowercase_result.warnings) == 1
        assert "should start with uppercase letter" in lowercase_result.warnings[0]
    
    def test_validate_single_node_empty_path_component(self):
        """Test validation catches empty path components."""
        node = TR181Node(
            path="Device.WiFi..Channel",  # Empty component
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_single_node(node)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Empty path component" in result.errors[0]
    
    def test_validate_node_data_type_string(self):
        """Test data type validation for string values."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="TestNetwork"
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_node_data_type_string_invalid(self):
        """Test data type validation for invalid string values."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value=123  # Should be string
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Expected string, got int" in result.errors[0]
    
    def test_validate_node_data_type_int(self):
        """Test data type validation for integer values."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_node_data_type_int_invalid(self):
        """Test data type validation for invalid integer values."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value="6"  # Should be int
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Expected int, got str" in result.errors[0]
    
    def test_validate_node_data_type_boolean(self):
        """Test data type validation for boolean values."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_node_data_type_boolean_invalid(self):
        """Test data type validation for invalid boolean values."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value="true"  # Should be bool
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Expected boolean, got str" in result.errors[0]
    
    def test_validate_node_data_type_datetime_string(self):
        """Test data type validation for datetime as ISO string."""
        node = TR181Node(
            path="Device.Time.CurrentLocalTime",
            name="CurrentLocalTime",
            data_type="datetime",
            access=AccessLevel.READ_ONLY,
            value="2023-12-01T10:30:00Z"
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_node_data_type_datetime_object(self):
        """Test data type validation for datetime object."""
        node = TR181Node(
            path="Device.Time.CurrentLocalTime",
            name="CurrentLocalTime",
            data_type="datetime",
            access=AccessLevel.READ_ONLY,
            value=datetime.now()
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_node_data_type_datetime_invalid_string(self):
        """Test data type validation for invalid datetime string."""
        node = TR181Node(
            path="Device.Time.CurrentLocalTime",
            name="CurrentLocalTime",
            data_type="datetime",
            access=AccessLevel.READ_ONLY,
            value="invalid-datetime"
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Invalid datetime format" in result.errors[0]
    
    def test_validate_node_data_type_datetime_invalid_type(self):
        """Test data type validation for invalid datetime type."""
        node = TR181Node(
            path="Device.Time.CurrentLocalTime",
            name="CurrentLocalTime",
            data_type="datetime",
            access=AccessLevel.READ_ONLY,
            value=123456789  # Should be datetime or string
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Expected datetime or ISO string, got int" in result.errors[0]
    
    def test_validate_node_data_type_none_value(self):
        """Test data type validation with None value (should pass)."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=None
        )
        
        extractor = MockExtractor("test-source")
        result = extractor._validate_node_data_type(node)
        
        assert result.is_valid is True
        assert len(result.errors) == 0


class TestExtractorExceptions:
    """Test custom extractor exceptions."""
    
    def test_connection_error(self):
        """Test ConnectionError exception."""
        error = ConnectionError("Unable to connect to device")
        assert "Unable to connect to device" in str(error)
        assert error.message == "Unable to connect to device"
        assert isinstance(error, Exception)
    
    def test_validation_error(self):
        """Test ValidationError exception."""
        error = ValidationError("Data validation failed")
        assert "Data validation failed" in str(error)
        assert error.message == "Data validation failed"
        assert isinstance(error, Exception)


class TestAbstractMethods:
    """Test that NodeExtractor abstract methods are properly defined."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that NodeExtractor cannot be instantiated directly."""
        with pytest.raises(TypeError):
            NodeExtractor("test-source")
    
    def test_mock_extractor_implements_all_methods(self):
        """Test that MockExtractor implements all required abstract methods."""
        extractor = MockExtractor("test-source")
        
        # Check that all abstract methods are implemented
        assert hasattr(extractor, 'extract')
        assert hasattr(extractor, 'validate')
        assert hasattr(extractor, 'get_source_info')
        
        # Check that methods are callable
        assert callable(extractor.extract)
        assert callable(extractor.validate)
        assert callable(extractor.get_source_info)