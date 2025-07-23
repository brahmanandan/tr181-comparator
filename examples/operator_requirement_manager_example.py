#!/usr/bin/env python3
"""
Example demonstrating OperatorRequirementManager functionality for managing custom TR181 operator requirements.

This example shows how to:
1. Create and manage custom TR181 node operator requirements
2. Load and save operator requirement definitions from/to JSON and YAML files
3. Add custom nodes with validation
4. Validate operator requirement definitions and TR181 naming conventions
"""

import asyncio
import json
import tempfile
import os
import sys

# Add parent directory to path to import tr181_comparator
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tr181_comparator.extractors import OperatorRequirementManager, ValidationError
from tr181_comparator.models import TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function


async def main():
    """Demonstrate OperatorRequirementManager functionality."""
    print("=== TR181 OperatorRequirementManager Example ===\n")
    
    # Create temporary files for demonstration
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as json_file:
        json_path = json_file.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as yaml_file:
        yaml_path = yaml_file.name
    
    try:
        # 1. Create an OperatorRequirementManager for JSON format
        print("1. Creating OperatorRequirementManager for JSON format")
        json_manager = OperatorRequirementManager(json_path)
        print(f"   Operator requirement path: {json_path}")
        print(f"   File format: {json_manager._detect_file_format()}")
        
        # 2. Create sample TR181 nodes
        print("\n2. Creating sample TR181 nodes")
        sample_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6,
                description="WiFi channel number",
                is_custom=False,
                value_range=ValueRange(min_value=1, max_value=11)
            ),
            TR181Node(
                path="Device.WiFi.SSID.1.SSID",
                name="SSID",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="MyNetwork",
                description="WiFi network name",
                is_custom=False,
                value_range=ValueRange(max_length=32)
            )
        ]
        
        for node in sample_nodes:
            print(f"   - {node.path} ({node.data_type}, {node.access.value})")
        
        # 3. Save operator requirement to JSON file
        print("\n3. Saving operator requirement to JSON file")
        await json_manager.save_operator_requirement(sample_nodes)
        print(f"   Saved {len(sample_nodes)} nodes to {json_path}")
        
        # Verify file was created and show content
        with open(json_path, 'r') as f:
            data = json.load(f)
        print(f"   File contains {data['metadata']['total_nodes']} nodes")
        
        # 4. Load operator requirement from JSON file
        print("\n4. Loading operator requirement from JSON file")
        loaded_nodes = await json_manager.extract()
        print(f"   Loaded {len(loaded_nodes)} nodes")
        for node in loaded_nodes:
            print(f"   - {node.path}: {node.value}")
        
        # 5. Add a custom node
        print("\n5. Adding a custom node")
        custom_node = TR181Node(
            path="Device.Custom.TestParameter",
            name="TestParameter",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="custom_value",
            description="Custom test parameter for demonstration",
            is_custom=True,
            value_range=ValueRange(
                allowed_values=["custom_value", "other_value"],
                max_length=50
            ),
            events=[
                TR181Event(
                    name="TestEvent",
                    path="Device.Custom.TestEvent",
                    parameters=["Device.Custom.TestParameter"],
                    description="Test event for custom parameter"
                )
            ]
        )
        
        await json_manager.add_custom_node(custom_node)
        print(f"   Added custom node: {custom_node.path}")
        print(f"   Total nodes now: {len(json_manager._nodes)}")
        
        # 6. Get custom and standard nodes separately
        print("\n6. Separating custom and standard nodes")
        custom_nodes = json_manager.get_custom_nodes()
        standard_nodes = json_manager.get_standard_nodes()
        print(f"   Custom nodes: {len(custom_nodes)}")
        for node in custom_nodes:
            print(f"   - {node.path} (custom)")
        print(f"   Standard nodes: {len(standard_nodes)}")
        for node in standard_nodes:
            print(f"   - {node.path} (standard)")
        
        # 7. Save updated operator requirement with custom node
        print("\n7. Saving updated operator requirement with custom node")
        await json_manager.save_operator_requirement(json_manager._nodes)
        print(f"   Saved {len(json_manager._nodes)} nodes (including custom)")
        
        # 8. Validate operator requirement
        print("\n8. Validating operator requirement")
        validation_result = await json_manager.validate()
        if validation_result.is_valid:
            print("   ✓ Operator requirement validation passed")
        else:
            print("   ✗ Operator requirement validation failed:")
            for error in validation_result.errors:
                print(f"     - {error}")
        
        if validation_result.warnings:
            print("   Warnings:")
            for warning in validation_result.warnings:
                print(f"     - {warning}")
        
        # 9. Demonstrate YAML format
        print("\n9. Demonstrating YAML format")
        yaml_manager = OperatorRequirementManager(yaml_path)
        print(f"   YAML path: {yaml_path}")
        print(f"   File format: {yaml_manager._detect_file_format()}")
        
        # Save same nodes to YAML
        await yaml_manager.save_operator_requirement(json_manager._nodes)
        print(f"   Saved {len(json_manager._nodes)} nodes to YAML format")
        
        # Load from YAML
        yaml_nodes = await yaml_manager.extract()
        print(f"   Loaded {len(yaml_nodes)} nodes from YAML")
        
        # 10. Get source information
        print("\n10. Source information")
        json_source_info = json_manager.get_source_info()
        yaml_source_info = yaml_manager.get_source_info()
        
        print(f"   JSON source:")
        print(f"     Type: {json_source_info.type}")
        print(f"     Node count: {json_source_info.metadata['node_count']}")
        print(f"     Custom nodes: {json_source_info.metadata['custom_nodes']}")
        print(f"     Format: {json_source_info.metadata['file_format']}")
        
        print(f"   YAML source:")
        print(f"     Type: {yaml_source_info.type}")
        print(f"     Node count: {yaml_source_info.metadata['node_count']}")
        print(f"     Custom nodes: {yaml_source_info.metadata['custom_nodes']}")
        print(f"     Format: {yaml_source_info.metadata['file_format']}")
        
        # 11. Demonstrate error handling
        print("\n11. Demonstrating error handling")
        
        # Try to add duplicate node
        try:
            duplicate_node = TR181Node(
                path="Device.WiFi.Radio.1.Channel",  # Already exists
                name="DuplicateChannel",
                data_type="int",
                access=AccessLevel.READ_ONLY
            )
            await json_manager.add_custom_node(duplicate_node)
        except ValidationError as e:
            print(f"   ✓ Caught expected error for duplicate node: {e}")
        
        # Try to add invalid custom node
        try:
            invalid_node = TR181Node(
                path="InvalidPath.Test",  # Doesn't start with Device.
                name="Test",
                data_type="string",
                access=AccessLevel.READ_ONLY
            )
            await json_manager.add_custom_node(invalid_node)
        except ValidationError as e:
            print(f"   ✓ Caught expected error for invalid path: {e}")
        
        # 12. Remove a node
        print("\n12. Removing a node")
        initial_count = len(json_manager._nodes)
        removed = await json_manager.remove_node("Device.WiFi.SSID.1.SSID")
        final_count = len(json_manager._nodes)
        print(f"   Removed node: {removed}")
        print(f"   Node count: {initial_count} -> {final_count}")
        
        print("\n=== OperatorRequirementManager Example Complete ===")
        
    finally:
        # Clean up temporary files
        for path in [json_path, yaml_path]:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    asyncio.run(main())