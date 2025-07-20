"""TR181 validation engine for comprehensive node validation."""

import re
from datetime import datetime
from typing import Any, List, Union

from .models import TR181Node, ValueRange, Severity


class ValidationResult:
    """Container for validation results with errors and warnings."""
    
    def __init__(self):
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def add_error(self, message: str):
        """Add an error message and mark validation as failed."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
    
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False
    
    def __str__(self) -> str:
        """String representation of validation result."""
        result = f"Valid: {self.is_valid}"
        if self.errors:
            result += f"\nErrors: {', '.join(self.errors)}"
        if self.warnings:
            result += f"\nWarnings: {', '.join(self.warnings)}"
        return result


class TR181Validator:
    """Comprehensive TR181 node validation engine."""
    
    # TR181 data types and their Python equivalents
    TR181_DATA_TYPES = {
        'string': str,
        'int': int,
        'unsignedint': int,
        'boolean': bool,
        'datetime': str,  # ISO format string
        'base64': str,
        'hexbinary': str,
        'long': int,
        'unsignedlong': int,
        'float': float,
        'double': float,
    }
    
    # TR181 path naming pattern - allows standard TR181 paths like Device.WiFi.Radio.1.Channel
    TR181_PATH_PATTERN = re.compile(r'^Device\.([A-Z][a-zA-Z0-9]*\.)*([A-Z][a-zA-Z0-9]*|\d+)(\.[A-Z][a-zA-Z0-9]*)*$')
    
    # TR181 parameter name pattern (must start with uppercase)
    TR181_NAME_PATTERN = re.compile(r'^[A-Z][a-zA-Z0-9]*$')
    
    # ISO 8601 datetime patterns
    DATETIME_PATTERNS = [
        re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'),  # 2023-01-01T12:00:00Z
        re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$'),  # 2023-01-01T12:00:00+05:00
        re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$'),  # 2023-01-01T12:00:00.123Z
    ]
    
    def validate_node(self, node: TR181Node, actual_value: Any = None) -> ValidationResult:
        """
        Perform comprehensive validation of a TR181 node.
        
        Args:
            node: The TR181Node to validate
            actual_value: Optional actual value to validate against node specification
            
        Returns:
            ValidationResult containing validation status, errors, and warnings
        """
        result = ValidationResult()
        
        # Validate node structure
        self._validate_node_structure(node, result)
        
        # Validate path format
        self._validate_path_format(node, result)
        
        # Validate data type specification
        self._validate_data_type_specification(node, result)
        
        # Validate actual value if provided
        if actual_value is not None:
            self._validate_data_type(node, actual_value, result)
            self._validate_range(node, actual_value, result)
        
        # Validate node's own value if present
        elif node.value is not None:
            self._validate_data_type(node, node.value, result)
            self._validate_range(node, node.value, result)
        
        # Validate value range specification
        if node.value_range:
            self._validate_range_specification(node, result)
        
        return result
    
    def _validate_node_structure(self, node: TR181Node, result: ValidationResult):
        """Validate basic node structure and required fields."""
        if not node.path:
            result.add_error("Node path cannot be empty")
        
        if not node.name:
            result.add_error("Node name cannot be empty")
        
        if not node.data_type:
            result.add_error("Node data_type cannot be empty")
        
        # Validate name format
        if node.name and not self.TR181_NAME_PATTERN.match(node.name):
            result.add_warning(f"Parameter name '{node.name}' should start with uppercase letter and contain only alphanumeric characters")
    
    def _validate_path_format(self, node: TR181Node, result: ValidationResult):
        """Validate TR181 path naming conventions."""
        if not node.path:
            return
        
        # Check if path starts with Device.
        if not node.path.startswith('Device.'):
            result.add_error(f"TR181 path must start with 'Device.' - got: {node.path}")
            return
        
        # Check individual path components
        path_parts = node.path.split('.')
        for i, part in enumerate(path_parts[1:], 1):  # Skip 'Device'
            if not part:
                result.add_error(f"Empty path component in {node.path}")
                continue
            
            # Check if it's a numeric index (allowed for multi-instance objects)
            if part.isdigit():
                continue
            
            # Check if it starts with uppercase
            if not part[0].isupper():
                result.add_warning(f"Path component '{part}' should start with uppercase letter in {node.path}")
            
            # Check for valid characters
            if not re.match(r'^[A-Za-z0-9]+$', part):
                result.add_warning(f"Path component '{part}' contains invalid characters in {node.path}")
    
    def _validate_data_type_specification(self, node: TR181Node, result: ValidationResult):
        """Validate that the data type specification is valid."""
        if not node.data_type:
            return
        
        data_type_lower = node.data_type.lower()
        if data_type_lower not in self.TR181_DATA_TYPES:
            result.add_warning(f"Unknown data type '{node.data_type}' for {node.path}")
    
    def _validate_data_type(self, node: TR181Node, value: Any, result: ValidationResult):
        """Validate that the actual value matches the expected data type."""
        if value is None:
            return
        
        expected_type = node.data_type.lower()
        
        if expected_type == 'string':
            if not isinstance(value, str):
                result.add_error(f"Expected string, got {type(value).__name__} for {node.path}")
        
        elif expected_type in ('int', 'unsignedint', 'long', 'unsignedlong'):
            if not isinstance(value, int):
                result.add_error(f"Expected integer, got {type(value).__name__} for {node.path}")
            elif expected_type in ('unsignedint', 'unsignedlong') and value < 0:
                result.add_error(f"Expected unsigned integer, got negative value {value} for {node.path}")
        
        elif expected_type in ('float', 'double'):
            if not isinstance(value, (int, float)):
                result.add_error(f"Expected numeric value, got {type(value).__name__} for {node.path}")
        
        elif expected_type == 'boolean':
            if not isinstance(value, bool):
                result.add_error(f"Expected boolean, got {type(value).__name__} for {node.path}")
        
        elif expected_type == 'datetime':
            if not isinstance(value, str):
                result.add_error(f"Expected datetime string, got {type(value).__name__} for {node.path}")
            else:
                self._validate_datetime_format(value, node.path, result)
        
        elif expected_type == 'base64':
            if not isinstance(value, str):
                result.add_error(f"Expected base64 string, got {type(value).__name__} for {node.path}")
            else:
                self._validate_base64_format(value, node.path, result)
        
        elif expected_type == 'hexbinary':
            if not isinstance(value, str):
                result.add_error(f"Expected hex binary string, got {type(value).__name__} for {node.path}")
            else:
                self._validate_hex_format(value, node.path, result)
    
    def _validate_datetime_format(self, value: str, path: str, result: ValidationResult):
        """Validate datetime string format (ISO 8601)."""
        # Check against known patterns
        for pattern in self.DATETIME_PATTERNS:
            if pattern.match(value):
                # Try to parse to ensure it's a valid date
                try:
                    # Handle different timezone formats
                    if value.endswith('Z'):
                        datetime.fromisoformat(value.replace('Z', '+00:00'))
                    else:
                        datetime.fromisoformat(value)
                    return
                except ValueError:
                    pass
        
        result.add_error(f"Invalid datetime format '{value}' for {path}. Expected ISO 8601 format (e.g., '2023-01-01T12:00:00Z')")
    
    def _validate_base64_format(self, value: str, path: str, result: ValidationResult):
        """Validate base64 string format."""
        import base64
        try:
            # Check if it's valid base64
            base64.b64decode(value, validate=True)
        except Exception:
            result.add_error(f"Invalid base64 format '{value}' for {path}")
    
    def _validate_hex_format(self, value: str, path: str, result: ValidationResult):
        """Validate hexadecimal string format."""
        if not re.match(r'^[0-9A-Fa-f]*$', value):
            result.add_error(f"Invalid hex binary format '{value}' for {path}. Must contain only hexadecimal characters")
        
        if len(value) % 2 != 0:
            result.add_error(f"Invalid hex binary format '{value}' for {path}. Must have even number of characters")
    
    def _validate_range(self, node: TR181Node, value: Any, result: ValidationResult):
        """Validate that the value falls within specified ranges."""
        if not node.value_range or value is None:
            return
        
        range_spec = node.value_range
        
        # Check allowed values (enumeration)
        if range_spec.allowed_values is not None:
            if value not in range_spec.allowed_values:
                result.add_error(f"Value '{value}' not in allowed values {range_spec.allowed_values} for {node.path}")
            return  # If enumeration is specified, other range checks don't apply
        
        # Check numeric ranges
        if range_spec.min_value is not None:
            try:
                if value < range_spec.min_value:
                    result.add_error(f"Value {value} below minimum {range_spec.min_value} for {node.path}")
            except TypeError:
                result.add_warning(f"Cannot compare value {value} with minimum {range_spec.min_value} for {node.path}")
        
        if range_spec.max_value is not None:
            try:
                if value > range_spec.max_value:
                    result.add_error(f"Value {value} above maximum {range_spec.max_value} for {node.path}")
            except TypeError:
                result.add_warning(f"Cannot compare value {value} with maximum {range_spec.max_value} for {node.path}")
        
        # Check string length
        if isinstance(value, str) and range_spec.max_length is not None:
            if len(value) > range_spec.max_length:
                result.add_error(f"String length {len(value)} exceeds maximum {range_spec.max_length} for {node.path}")
        
        # Check pattern matching
        if isinstance(value, str) and range_spec.pattern is not None:
            try:
                if not re.match(range_spec.pattern, value):
                    result.add_error(f"Value '{value}' does not match pattern '{range_spec.pattern}' for {node.path}")
            except re.error as e:
                result.add_warning(f"Invalid regex pattern '{range_spec.pattern}' for {node.path}: {e}")
    
    def _validate_range_specification(self, node: TR181Node, result: ValidationResult):
        """Validate that the range specification itself is valid."""
        range_spec = node.value_range
        
        # Check that min <= max if both are specified
        if (range_spec.min_value is not None and range_spec.max_value is not None):
            try:
                if range_spec.min_value > range_spec.max_value:
                    result.add_error(f"Minimum value {range_spec.min_value} is greater than maximum value {range_spec.max_value} for {node.path}")
            except TypeError:
                result.add_warning(f"Cannot compare min/max values for {node.path}: incompatible types")
        
        # Validate regex pattern if specified
        if range_spec.pattern is not None:
            try:
                re.compile(range_spec.pattern)
            except re.error as e:
                result.add_error(f"Invalid regex pattern '{range_spec.pattern}' for {node.path}: {e}")
        
        # Check max_length is positive
        if range_spec.max_length is not None and range_spec.max_length <= 0:
            result.add_error(f"Maximum length must be positive, got {range_spec.max_length} for {node.path}")
    
    def validate_multiple_nodes(self, nodes: List[TR181Node]) -> List[tuple[str, ValidationResult]]:
        """
        Validate multiple nodes and return results.
        
        Args:
            nodes: List of TR181Node objects to validate
            
        Returns:
            List of tuples containing (node_path, ValidationResult)
        """
        results = []
        for node in nodes:
            validation_result = self.validate_node(node)
            results.append((node.path, validation_result))
        return results
    
    def get_validation_summary(self, validation_results: List[tuple[str, ValidationResult]]) -> dict:
        """
        Generate a summary of validation results.
        
        Args:
            validation_results: List of (path, ValidationResult) tuples
            
        Returns:
            Dictionary with validation summary statistics
        """
        total_nodes = len(validation_results)
        valid_nodes = sum(1 for _, result in validation_results if result.is_valid)
        invalid_nodes = total_nodes - valid_nodes
        total_errors = sum(len(result.errors) for _, result in validation_results)
        total_warnings = sum(len(result.warnings) for _, result in validation_results)
        
        return {
            'total_nodes': total_nodes,
            'valid_nodes': valid_nodes,
            'invalid_nodes': invalid_nodes,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'validation_rate': valid_nodes / total_nodes if total_nodes > 0 else 0.0
        }