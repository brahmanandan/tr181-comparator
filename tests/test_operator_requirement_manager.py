"""Unit tests for OperatorRequirementManager class."""

import pytest
import asyncio
import json
import yaml
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, mock_open

from tr181_comparator.extractors import OperatorRequirementManager, ValidationError, ValidationResult
from tr181_comparator.models import TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function


class TestOperatorRequirementManager:
    """Test cases for OperatorRequirementManager class."""
    
    @pytest.fixture
    def temp_json_file(self):
        """Create a temporary JSON file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            yield f.name
        # Clean up file if it still exists
        if os.path.exists(f.name):
            os.unlink(f.name)
    
    @pytest.fixture
    def temp_yaml_file(self):
        """Create a temporary YAML file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def sample_nodes(self):
        """Create sample TR181 nodes for testing."""
        return [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6,
                description="WiFi channel number",
                is_custom=False
            ),
            TR181Node(
                path="Device.Custom.TestParameter",
                name="TestParameter",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="test_value",
                description="Custom test parameter",
                is_custom=True,
                value_range=ValueRange(
                    allowed_values=["test_value", "other_value"],
                    max_length=50
                )
            )
        ]
    
    @pytest.fixture
    def sample_operator_requirement_data(self):
        """Create sample operator requirement data structure."""
        return {
            "version": "1.0",
            "metadata": {
                "created": "2024-01-01T00:00:00",
                "description": "Test operator requirement",
                "total_nodes": 2,
                "custom_nodes": 1
            },
            "nodes": [
                {
                    "path": "Device.WiFi.Radio.1.Channel",
                    "name": "Channel",
                    "data_type": "int",
                    "access": "read-write",
                    "is_object": False,
                    "is_custom": False,
                    "value": 6,
                    "description": "WiFi channel number"
                },
                {
                    "path": "Device.Custom.TestParameter",
                    "name": "TestParameter",
                    "data_type": "string",
                    "access": "read-only",
                    "is_object": False,
                    "is_custom": True,
                    "value": "test_value",
                    "description": "Custom test parameter",
                    "value_range": {
                        "allowed_values": ["test_value", "other_value"],
                        "max_length": 50
                    }
                }
            ]
        }
    
    def test_init(self, temp_json_file):
        """Test OperatorRequirementManager initialization."""
        manager = OperatorRequirementManager(temp_json_file)
        assert manager.operator_requirement_path == temp_json_file
        assert manager._nodes == []
        assert not manager._loaded
        assert manager._source_identifier == temp_json_file
    
    def test_detect_file_format_json(self, temp_json_file):
        """Test file format detection for JSON files."""
        manager = OperatorRequirementManager(temp_json_file)
        assert manager._detect_file_format() == 'json'
    
    def test_detect_file_format_yaml(self, temp_yaml_file):
        """Test file format detection for YAML files."""
        manager = OperatorRequirementManager(temp_yaml_file)
        assert manager._detect_file_format() == 'yaml'
    
    @pytest.mark.asyncio
    async def test_extract_empty_file(self, temp_json_file):
        """Test extracting from non-existent file creates empty operator requirement."""
        manager = OperatorRequirementManager(temp_json_file)
        nodes = await manager.extract()
        assert nodes == []
        assert manager._loaded
    
    @pytest.mark.asyncio
    async def test_extract_json_file(self, temp_json_file, sample_operator_requirement_data):
        """Test extracting nodes from JSON file."""
        # Write sample data to file
        with open(temp_json_file, 'w') as f:
            json.dump(sample_operator_requirement_data, f)
        
        manager = OperatorRequirementManager(temp_json_file)
        nodes = await manager.extract()
        
        assert len(nodes) == 2
        assert nodes[0].path == "Device.WiFi.Radio.1.Channel"
        assert nodes[0].data_type == "int"
        assert nodes[0].access == AccessLevel.READ_WRITE
        assert nodes[0].value == 6
        assert not nodes[0].is_custom
        
        assert nodes[1].path == "Device.Custom.TestParameter"
        assert nodes[1].is_custom
        assert nodes[1].value_range is not None
        assert nodes[1].value_range.allowed_values == ["test_value", "other_value"]
    
    @pytest.mark.asyncio
    async def test_extract_yaml_file(self, temp_yaml_file, sample_operator_requirement_data):
        """Test extracting nodes from YAML file."""
        # Write sample data to file
        with open(temp_yaml_file, 'w') as f:
            yaml.safe_dump(sample_operator_requirement_data, f)
        
        manager = OperatorRequirementManager(temp_yaml_file)
        nodes = await manager.extract()
        
        assert len(nodes) == 2
        assert nodes[0].path == "Device.WiFi.Radio.1.Channel"
        assert nodes[1].path == "Device.Custom.TestParameter"
    
    @pytest.mark.asyncio
    async def test_extract_invalid_json(self, temp_json_file):
        """Test extracting from invalid JSON file raises ValidationError."""
        # Write invalid JSON
        with open(temp_json_file, 'w') as f:
            f.write("invalid json content")
        
        manager = OperatorRequirementManager(temp_json_file)
        with pytest.raises(ValidationError):
            await manager.extract()
    
    @pytest.mark.asyncio
    async def test_validate_nonexistent_file(self, temp_json_file):
        """Test validating non-existent file."""
        # Delete the file created by fixture to test non-existent file
        os.unlink(temp_json_file)
        manager = OperatorRequirementManager(temp_json_file)
        result = await manager.validate()
        
        assert not result.is_valid
        assert "Operator requirement file not found" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_valid_file(self, temp_json_file, sample_operator_requirement_data):
        """Test validating valid operator requirement file."""
        # Write valid data
        with open(temp_json_file, 'w') as f:
            json.dump(sample_operator_requirement_data, f)
        
        manager = OperatorRequirementManager(temp_json_file)
        result = await manager.validate()
        
        assert result.is_valid
    
    def test_get_source_info(self, temp_json_file, sample_nodes):
        """Test getting source info."""
        manager = OperatorRequirementManager(temp_json_file)
        manager._nodes = sample_nodes
        
        source_info = manager.get_source_info()
        
        assert source_info.type == "operator_requirement"
        assert source_info.identifier == temp_json_file
        assert source_info.metadata["node_count"] == 2
        assert source_info.metadata["custom_nodes"] == 1
        assert source_info.metadata["file_format"] == "json"
    
    @pytest.mark.asyncio
    async def test_save_operator_requirement_json(self, temp_json_file, sample_nodes):
        """Test saving operator requirement to JSON file."""
        manager = OperatorRequirementManager(temp_json_file)
        await manager.save_operator_requirement(sample_nodes)
        
        # Verify file was written
        assert os.path.exists(temp_json_file)
        
        # Verify content
        with open(temp_json_file, 'r') as f:
            data = json.load(f)
        
        assert data["version"] == "1.0"
        assert data["metadata"]["total_nodes"] == 2
        assert data["metadata"]["custom_nodes"] == 1
        assert len(data["nodes"]) == 2
    
    @pytest.mark.asyncio
    async def test_save_operator_requirement_yaml(self, temp_yaml_file, sample_nodes):
        """Test saving operator requirement to YAML file."""
        manager = OperatorRequirementManager(temp_yaml_file)
        await manager.save_operator_requirement(sample_nodes)
        
        # Verify file was written
        assert os.path.exists(temp_yaml_file)
        
        # Verify content
        with open(temp_yaml_file, 'r') as f:
            data = yaml.safe_load(f)
        
        assert data["version"] == "1.0"
        assert len(data["nodes"]) == 2
    
    @pytest.mark.asyncio
    async def test_save_operator_requirement_with_duplicates(self, temp_json_file):
        """Test saving operator requirement with duplicate paths raises ValidationError."""
        duplicate_nodes = [
            TR181Node(
                path="Device.Test.Parameter",
                name="Parameter",
                data_type="string",
                access=AccessLevel.READ_ONLY
            ),
            TR181Node(
                path="Device.Test.Parameter",  # Duplicate path
                name="Parameter2",
                data_type="int",
                access=AccessLevel.READ_WRITE
            )
        ]
        
        manager = OperatorRequirementManager(temp_json_file)
        with pytest.raises(ValidationError) as exc_info:
            await manager.save_operator_requirement(duplicate_nodes)
        
        assert "Duplicate node path" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_add_custom_node(self, temp_json_file):
        """Test adding a custom node."""
        manager = OperatorRequirementManager(temp_json_file)
        
        custom_node = TR181Node(
            path="Device.Custom.NewParameter",
            name="NewParameter",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            description="New custom parameter"
        )
        
        await manager.add_custom_node(custom_node)
        
        assert len(manager._nodes) == 1
        assert manager._nodes[0].is_custom
        assert manager._nodes[0].path == "Device.Custom.NewParameter"
    
    @pytest.mark.asyncio
    async def test_add_custom_node_duplicate_path(self, temp_json_file, sample_nodes):
        """Test adding custom node with duplicate path raises ValidationError."""
        manager = OperatorRequirementManager(temp_json_file)
        manager._nodes = sample_nodes.copy()
        manager._loaded = True
        
        duplicate_node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",  # Already exists
            name="DuplicateChannel",
            data_type="int",
            access=AccessLevel.READ_ONLY
        )
        
        with pytest.raises(ValidationError) as exc_info:
            await manager.add_custom_node(duplicate_node)
        
        assert "Node path already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_add_custom_node_invalid_path(self, temp_json_file):
        """Test adding custom node with invalid path raises ValidationError."""
        manager = OperatorRequirementManager(temp_json_file)
        
        invalid_node = TR181Node(
            path="InvalidPath.Test",  # Doesn't start with Device.
            name="Test",
            data_type="string",
            access=AccessLevel.READ_ONLY
        )
        
        with pytest.raises(ValidationError) as exc_info:
            await manager.add_custom_node(invalid_node)
        
        assert "Custom node path must start with 'Device.'" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_remove_node(self, temp_json_file, sample_nodes):
        """Test removing a node by path."""
        manager = OperatorRequirementManager(temp_json_file)
        manager._nodes = sample_nodes.copy()
        manager._loaded = True
        
        # Remove existing node
        result = await manager.remove_node("Device.WiFi.Radio.1.Channel")
        assert result is True
        assert len(manager._nodes) == 1
        assert manager._nodes[0].path == "Device.Custom.TestParameter"
        
        # Try to remove non-existent node
        result = await manager.remove_node("Device.NonExistent.Parameter")
        assert result is False
        assert len(manager._nodes) == 1
    
    def test_get_custom_nodes(self, temp_json_file, sample_nodes):
        """Test getting only custom nodes."""
        manager = OperatorRequirementManager(temp_json_file)
        manager._nodes = sample_nodes
        
        custom_nodes = manager.get_custom_nodes()
        
        assert len(custom_nodes) == 1
        assert custom_nodes[0].path == "Device.Custom.TestParameter"
        assert custom_nodes[0].is_custom
    
    def test_get_standard_nodes(self, temp_json_file, sample_nodes):
        """Test getting only standard nodes."""
        manager = OperatorRequirementManager(temp_json_file)
        manager._nodes = sample_nodes
        
        standard_nodes = manager.get_standard_nodes()
        
        assert len(standard_nodes) == 1
        assert standard_nodes[0].path == "Device.WiFi.Radio.1.Channel"
        assert not standard_nodes[0].is_custom
    
    def test_node_to_dict_complete(self, temp_json_file):
        """Test converting a complete node to dictionary."""
        manager = OperatorRequirementManager(temp_json_file)
        
        node = TR181Node(
            path="Device.Test.Parameter",
            name="Parameter",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="test_value",
            description="Test parameter",
            parent="Device.Test",
            children=["Device.Test.Parameter.Child"],
            is_object=False,
            is_custom=True,
            value_range=ValueRange(
                min_value=1,
                max_value=100,
                allowed_values=["test_value", "other_value"],
                pattern="^test_.*",
                max_length=50
            ),
            events=[
                TR181Event(
                    name="TestEvent",
                    path="Device.Test.Event",
                    parameters=["Device.Test.Parameter"],
                    description="Test event"
                )
            ],
            functions=[
                TR181Function(
                    name="TestFunction",
                    path="Device.Test.Function",
                    input_parameters=["Device.Test.Input"],
                    output_parameters=["Device.Test.Output"],
                    description="Test function"
                )
            ]
        )
        
        result = manager._node_to_dict(node)
        
        assert result["path"] == "Device.Test.Parameter"
        assert result["name"] == "Parameter"
        assert result["data_type"] == "string"
        assert result["access"] == "read-write"
        assert result["value"] == "test_value"
        assert result["description"] == "Test parameter"
        assert result["parent"] == "Device.Test"
        assert result["children"] == ["Device.Test.Parameter.Child"]
        assert result["is_object"] is False
        assert result["is_custom"] is True
        
        # Check value range
        assert "value_range" in result
        assert result["value_range"]["min_value"] == 1
        assert result["value_range"]["max_value"] == 100
        assert result["value_range"]["allowed_values"] == ["test_value", "other_value"]
        assert result["value_range"]["pattern"] == "^test_.*"
        assert result["value_range"]["max_length"] == 50
        
        # Check events
        assert "events" in result
        assert len(result["events"]) == 1
        assert result["events"][0]["name"] == "TestEvent"
        
        # Check functions
        assert "functions" in result
        assert len(result["functions"]) == 1
        assert result["functions"][0]["name"] == "TestFunction"
    
    def test_dict_to_node_minimal(self, temp_json_file):
        """Test converting minimal dictionary to node."""
        manager = OperatorRequirementManager(temp_json_file)
        
        node_data = {
            "path": "Device.Test.Parameter",
            "name": "Parameter",
            "data_type": "string",
            "access": "read-only"
        }
        
        node = manager._dict_to_node(node_data)
        
        assert node.path == "Device.Test.Parameter"
        assert node.name == "Parameter"
        assert node.data_type == "string"
        assert node.access == AccessLevel.READ_ONLY
        assert node.value is None
        assert node.description is None
        assert node.parent is None
        assert node.children == []
        assert not node.is_object
        assert not node.is_custom
        assert node.value_range is None
        assert node.events == []
        assert node.functions == []
    
    def test_dict_to_node_missing_required_field(self, temp_json_file):
        """Test converting dictionary missing required field raises ValidationError."""
        manager = OperatorRequirementManager(temp_json_file)
        
        node_data = {
            "path": "Device.Test.Parameter",
            "name": "Parameter",
            # Missing data_type and access
        }
        
        with pytest.raises(ValidationError) as exc_info:
            manager._dict_to_node(node_data)
        
        assert "Missing required field" in str(exc_info.value)
    
    def test_dict_to_node_invalid_access_level(self, temp_json_file):
        """Test converting dictionary with invalid access level raises ValidationError."""
        manager = OperatorRequirementManager(temp_json_file)
        
        node_data = {
            "path": "Device.Test.Parameter",
            "name": "Parameter",
            "data_type": "string",
            "access": "invalid-access"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            manager._dict_to_node(node_data)
        
        assert "Invalid access level" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_custom_node_valid(self, temp_json_file):
        """Test validating a valid custom node."""
        manager = OperatorRequirementManager(temp_json_file)
        
        valid_node = TR181Node(
            path="Device.Custom.ValidParameter",
            name="ValidParameter",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="valid_value"
        )
        
        result = await manager._validate_custom_node(valid_node)
        assert result.is_valid
    
    @pytest.mark.asyncio
    async def test_validate_custom_node_invalid_path(self, temp_json_file):
        """Test validating custom node with invalid path."""
        manager = OperatorRequirementManager(temp_json_file)
        
        invalid_node = TR181Node(
            path="InvalidPath.Parameter",
            name="Parameter",
            data_type="string",
            access=AccessLevel.READ_ONLY
        )
        
        result = await manager._validate_custom_node(invalid_node)
        assert not result.is_valid
        assert any("must start with 'Device.'" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_custom_node_nonstandard_type(self, temp_json_file):
        """Test validating custom node with non-standard data type."""
        manager = OperatorRequirementManager(temp_json_file)
        
        node_with_custom_type = TR181Node(
            path="Device.Custom.Parameter",
            name="Parameter",
            data_type="customType",  # Non-standard type
            access=AccessLevel.READ_ONLY
        )
        
        result = await manager._validate_custom_node(node_with_custom_type)
        # Should still be valid but with warnings
        assert result.is_valid
        assert any("non-standard data type" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_nodes_for_saving_valid(self, temp_json_file, sample_nodes):
        """Test validating valid nodes for saving."""
        manager = OperatorRequirementManager(temp_json_file)
        
        result = await manager._validate_nodes_for_saving(sample_nodes)
        assert result.is_valid
    
    @pytest.mark.asyncio
    async def test_validate_nodes_for_saving_duplicates(self, temp_json_file):
        """Test validating nodes with duplicates for saving."""
        manager = OperatorRequirementManager(temp_json_file)
        
        duplicate_nodes = [
            TR181Node(
                path="Device.Test.Parameter",
                name="Parameter1",
                data_type="string",
                access=AccessLevel.READ_ONLY
            ),
            TR181Node(
                path="Device.Test.Parameter",  # Duplicate
                name="Parameter2",
                data_type="int",
                access=AccessLevel.READ_WRITE
            )
        ]
        
        result = await manager._validate_nodes_for_saving(duplicate_nodes)
        assert not result.is_valid
        assert any("Duplicate node path" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_write_operator_requirement_file_creates_directory(self, temp_json_file):
        """Test that writing operator requirement file creates necessary directories."""
        # Use a path with non-existent directory
        nested_path = os.path.join(os.path.dirname(temp_json_file), "nested", "operator_requirement.json")
        manager = OperatorRequirementManager(nested_path)
        
        data = {"version": "1.0", "nodes": []}
        await manager._write_operator_requirement_file(data)
        
        assert os.path.exists(nested_path)
        # Clean up
        os.unlink(nested_path)
        os.rmdir(os.path.dirname(nested_path))


if __name__ == "__main__":
    pytest.main([__file__])