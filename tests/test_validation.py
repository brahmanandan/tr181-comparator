"""Unit tests for TR181 validation engine."""

import pytest
from datetime import datetime

from tr181_comparator.validation import TR181Validator, ValidationResult
from tr181_comparator.models import TR181Node, AccessLevel, ValueRange


class TestValidationResult:
    """Test ValidationResult class functionality."""
    
    def test_init(self):
        """Test ValidationResult initialization."""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
    
    def test_add_error(self):
        """Test adding error messages."""
        result = ValidationResult()
        result.add_error("Test error")
        
        assert result.is_valid is False
        assert "Test error" in result.errors
        assert len(result.warnings) == 0
    
    def test_add_warning(self):
        """Test adding warning messages."""
        result = ValidationResult()
        result.add_warning("Test warning")
        
        assert result.is_valid is True
        assert "Test warning" in result.warnings
        assert len(result.errors) == 0
    
    def test_merge(self):
        """Test merging validation results."""
        result1 = ValidationResult()
        result1.add_error("Error 1")
        result1.add_warning("Warning 1")
        
        result2 = ValidationResult()
        result2.add_error("Error 2")
        result2.add_warning("Warning 2")
        
        result1.merge(result2)
        
        assert result1.is_valid is False
        assert "Error 1" in result1.errors
        assert "Error 2" in result1.errors
        assert "Warning 1" in result1.warnings
        assert "Warning 2" in result1.warnings
    
    def test_str_representation(self):
        """Test string representation of validation result."""
        result = ValidationResult()
        result.add_error("Test error")
        result.add_warning("Test warning")
        
        str_repr = str(result)
        assert "Valid: False" in str_repr
        assert "Test error" in str_repr
        assert "Test warning" in str_repr


class TestTR181Validator:
    """Test TR181Validator class functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = TR181Validator()
    
    def test_init(self):
        """Test validator initialization."""
        assert self.validator is not None
        assert len(self.validator.TR181_DATA_TYPES) > 0
        assert self.validator.TR181_PATH_PATTERN is not None
    
    def test_validate_valid_node(self):
        """Test validation of a valid TR181 node."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6
        )
        
        result = self.validator.validate_node(node)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_node_structure_errors(self):
        """Test validation of node structure errors."""
        # Test invalid name format (lowercase start)
        node = TR181Node(
            path="Device.WiFi.Channel",
            name="channel",  # Should start with uppercase
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        result = self.validator.validate_node(node)
        # Should have warning about name format
        name_warnings = [w for w in result.warnings if "uppercase letter" in w]
        assert len(name_warnings) > 0
        
        # Test unknown data type
        node = TR181Node(
            path="Device.WiFi.Channel",
            name="Channel",
            data_type="unknown_type",
            access=AccessLevel.READ_WRITE
        )
        result = self.validator.validate_node(node)
        # Should have warning about unknown data type
        type_warnings = [w for w in result.warnings if "Unknown data type" in w]
        assert len(type_warnings) > 0
    
    def test_validate_path_format(self):
        """Test TR181 path format validation."""
        # Valid paths
        valid_paths = [
            "Device.WiFi.Radio.1.Channel",
            "Device.DeviceInfo.Manufacturer",
            "Device.Ethernet.Interface.1.Stats.BytesSent"
        ]
        
        for path in valid_paths:
            node = TR181Node(
                path=path,
                name="TestParam",
                data_type="string",
                access=AccessLevel.READ_ONLY
            )
            result = self.validator.validate_node(node)
            # Should not have path format errors
            path_errors = [e for e in result.errors if "path" in e.lower()]
            assert len(path_errors) == 0, f"Unexpected path error for {path}: {path_errors}"
        
        # Invalid paths
        invalid_paths = [
            "WiFi.Radio.1.Channel",  # Doesn't start with Device.
            "device.WiFi.Channel",   # Lowercase device
            "Device..WiFi.Channel",  # Empty component
            "Device.WiFi..Channel"   # Empty component
        ]
        
        for path in invalid_paths:
            node = TR181Node(
                path=path,
                name="TestParam",
                data_type="string",
                access=AccessLevel.READ_ONLY
            )
            result = self.validator.validate_node(node)
            # Should have path format errors
            path_errors = [e for e in result.errors + result.warnings if "path" in e.lower() or "Device" in e]
            assert len(path_errors) > 0, f"Expected path error for {path}"
    
    def test_validate_data_types(self):
        """Test data type validation."""
        test_cases = [
            # (data_type, valid_value, invalid_value)
            ("string", "test", 123),
            ("int", 42, "not_int"),
            ("boolean", True, "not_bool"),
            ("float", 3.14, "not_float"),
        ]
        
        for data_type, valid_value, invalid_value in test_cases:
            # Test valid value
            node = TR181Node(
                path="Device.Test.Param",
                name="Param",
                data_type=data_type,
                access=AccessLevel.READ_WRITE,
                value=valid_value
            )
            result = self.validator.validate_node(node)
            type_errors = [e for e in result.errors if "Expected" in e and "got" in e]
            assert len(type_errors) == 0, f"Unexpected type error for {data_type} with value {valid_value}"
            
            # Test invalid value
            node = TR181Node(
                path="Device.Test.Param",
                name="Param",
                data_type=data_type,
                access=AccessLevel.READ_WRITE,
                value=invalid_value
            )
            result = self.validator.validate_node(node)
            type_errors = [e for e in result.errors if "Expected" in e and "got" in e]
            assert len(type_errors) > 0, f"Expected type error for {data_type} with value {invalid_value}"
    
    def test_validate_unsigned_integers(self):
        """Test unsigned integer validation."""
        # Valid unsigned int
        node = TR181Node(
            path="Device.Test.Param",
            name="Param",
            data_type="unsignedint",
            access=AccessLevel.READ_WRITE,
            value=42
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is True
        
        # Invalid negative unsigned int
        node = TR181Node(
            path="Device.Test.Param",
            name="Param",
            data_type="unsignedint",
            access=AccessLevel.READ_WRITE,
            value=-1
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("unsigned integer" in error and "negative" in error for error in result.errors)
    
    def test_validate_datetime_formats(self):
        """Test datetime format validation."""
        valid_datetimes = [
            "2023-01-01T12:00:00Z",
            "2023-12-31T23:59:59+05:00",
            "2023-06-15T10:30:45.123Z"
        ]
        
        for dt_str in valid_datetimes:
            node = TR181Node(
                path="Device.Test.DateTime",
                name="DateTime",
                data_type="datetime",
                access=AccessLevel.READ_WRITE,
                value=dt_str
            )
            result = self.validator.validate_node(node)
            dt_errors = [e for e in result.errors if "datetime format" in e.lower()]
            assert len(dt_errors) == 0, f"Unexpected datetime error for {dt_str}"
        
        invalid_datetimes = [
            "2023-01-01",  # Missing time
            "12:00:00",    # Missing date
            "2023-13-01T12:00:00Z",  # Invalid month
            "not-a-date"   # Invalid format
        ]
        
        for dt_str in invalid_datetimes:
            node = TR181Node(
                path="Device.Test.DateTime",
                name="DateTime",
                data_type="datetime",
                access=AccessLevel.READ_WRITE,
                value=dt_str
            )
            result = self.validator.validate_node(node)
            dt_errors = [e for e in result.errors if "datetime format" in e.lower()]
            assert len(dt_errors) > 0, f"Expected datetime error for {dt_str}"
    
    def test_validate_base64_format(self):
        """Test base64 format validation."""
        # Valid base64
        node = TR181Node(
            path="Device.Test.Base64",
            name="Base64",
            data_type="base64",
            access=AccessLevel.READ_WRITE,
            value="SGVsbG8gV29ybGQ="  # "Hello World" in base64
        )
        result = self.validator.validate_node(node)
        b64_errors = [e for e in result.errors if "base64" in e.lower()]
        assert len(b64_errors) == 0
        
        # Invalid base64
        node = TR181Node(
            path="Device.Test.Base64",
            name="Base64",
            data_type="base64",
            access=AccessLevel.READ_WRITE,
            value="Invalid@Base64!"
        )
        result = self.validator.validate_node(node)
        b64_errors = [e for e in result.errors if "base64" in e.lower()]
        assert len(b64_errors) > 0
    
    def test_validate_hex_format(self):
        """Test hexadecimal format validation."""
        # Valid hex
        node = TR181Node(
            path="Device.Test.Hex",
            name="Hex",
            data_type="hexbinary",
            access=AccessLevel.READ_WRITE,
            value="48656C6C6F"  # "Hello" in hex
        )
        result = self.validator.validate_node(node)
        hex_errors = [e for e in result.errors if "hex" in e.lower()]
        assert len(hex_errors) == 0
        
        # Invalid hex - odd length
        node = TR181Node(
            path="Device.Test.Hex",
            name="Hex",
            data_type="hexbinary",
            access=AccessLevel.READ_WRITE,
            value="48656C6C6"  # Odd length
        )
        result = self.validator.validate_node(node)
        hex_errors = [e for e in result.errors if "hex" in e.lower()]
        assert len(hex_errors) > 0
        
        # Invalid hex - invalid characters
        node = TR181Node(
            path="Device.Test.Hex",
            name="Hex",
            data_type="hexbinary",
            access=AccessLevel.READ_WRITE,
            value="48656C6G"  # 'G' is not hex
        )
        result = self.validator.validate_node(node)
        hex_errors = [e for e in result.errors if "hex" in e.lower()]
        assert len(hex_errors) > 0
    
    def test_validate_range_enumeration(self):
        """Test enumerated value validation."""
        value_range = ValueRange(allowed_values=["auto", "manual", "disabled"])
        
        # Valid enumerated value
        node = TR181Node(
            path="Device.Test.Mode",
            name="Mode",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="auto",
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is True
        
        # Invalid enumerated value
        node = TR181Node(
            path="Device.Test.Mode",
            name="Mode",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="invalid",
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("not in allowed values" in error for error in result.errors)
    
    def test_validate_numeric_ranges(self):
        """Test numeric range validation."""
        value_range = ValueRange(min_value=1, max_value=100)
        
        # Valid value in range
        node = TR181Node(
            path="Device.Test.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=50,
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is True
        
        # Value below minimum
        node = TR181Node(
            path="Device.Test.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=0,
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("below minimum" in error for error in result.errors)
        
        # Value above maximum
        node = TR181Node(
            path="Device.Test.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=101,
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("above maximum" in error for error in result.errors)
    
    def test_validate_string_length(self):
        """Test string length validation."""
        value_range = ValueRange(max_length=10)
        
        # Valid string length
        node = TR181Node(
            path="Device.Test.Name",
            name="Name",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="short",
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is True
        
        # String too long
        node = TR181Node(
            path="Device.Test.Name",
            name="Name",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="this_string_is_too_long",
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("exceeds maximum" in error for error in result.errors)
    
    def test_validate_string_pattern(self):
        """Test string pattern validation."""
        value_range = ValueRange(pattern=r'^[A-Z][a-z]+$')  # Capitalized word
        
        # Valid pattern match
        node = TR181Node(
            path="Device.Test.Name",
            name="Name",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="Hello",
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is True
        
        # Invalid pattern match
        node = TR181Node(
            path="Device.Test.Name",
            name="Name",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="hello",  # lowercase first letter
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("does not match pattern" in error for error in result.errors)
    
    def test_validate_range_specification(self):
        """Test validation of range specification itself."""
        # Invalid range: min > max
        value_range = ValueRange(min_value=100, max_value=50)
        node = TR181Node(
            path="Device.Test.Value",
            name="Value",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("greater than maximum" in error for error in result.errors)
        
        # Invalid regex pattern
        value_range = ValueRange(pattern="[invalid regex")
        node = TR181Node(
            path="Device.Test.Value",
            name="Value",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("Invalid regex pattern" in error for error in result.errors)
        
        # Invalid max_length
        value_range = ValueRange(max_length=-1)
        node = TR181Node(
            path="Device.Test.Value",
            name="Value",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value_range=value_range
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is False
        assert any("must be positive" in error for error in result.errors)
    
    def test_validate_multiple_nodes(self):
        """Test validation of multiple nodes."""
        nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6
            ),
            TR181Node(
                path="Device.WiFi.SSID.1.Name",
                name="Name",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="TestNetwork"
            ),
            TR181Node(
                path="invalid_path",  # This should fail
                name="Invalid",
                data_type="string",
                access=AccessLevel.READ_ONLY
            )
        ]
        
        results = self.validator.validate_multiple_nodes(nodes)
        assert len(results) == 3
        
        # First two should be valid
        assert results[0][1].is_valid is True
        assert results[1][1].is_valid is True
        
        # Third should be invalid due to path
        assert results[2][1].is_valid is False
    
    def test_get_validation_summary(self):
        """Test validation summary generation."""
        validation_results = [
            ("Device.Valid.Node1", ValidationResult()),  # Valid
            ("Device.Valid.Node2", ValidationResult()),  # Valid
        ]
        
        # Add some errors and warnings
        invalid_result = ValidationResult()
        invalid_result.add_error("Test error")
        invalid_result.add_warning("Test warning")
        validation_results.append(("Device.Invalid.Node", invalid_result))
        
        summary = self.validator.get_validation_summary(validation_results)
        
        assert summary['total_nodes'] == 3
        assert summary['valid_nodes'] == 2
        assert summary['invalid_nodes'] == 1
        assert summary['total_errors'] == 1
        assert summary['total_warnings'] == 1
        assert summary['validation_rate'] == 2/3
    
    def test_validate_with_actual_value(self):
        """Test validation with separate actual value parameter."""
        node = TR181Node(
            path="Device.Test.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value_range=ValueRange(min_value=1, max_value=11)
        )
        
        # Valid actual value
        result = self.validator.validate_node(node, actual_value=6)
        assert result.is_valid is True
        
        # Invalid actual value
        result = self.validator.validate_node(node, actual_value=15)
        assert result.is_valid is False
        assert any("above maximum" in error for error in result.errors)
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # None values
        node = TR181Node(
            path="Device.Test.Param",
            name="Param",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value=None
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is True  # None values should not cause errors
        
        # Empty string value
        node = TR181Node(
            path="Device.Test.Param",
            name="Param",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value=""
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is True  # Empty strings are valid
        
        # Zero values
        node = TR181Node(
            path="Device.Test.Param",
            name="Param",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=0
        )
        result = self.validator.validate_node(node)
        assert result.is_valid is True  # Zero is a valid integer