#!/usr/bin/env python3
"""Test script for backward compatibility with deprecated terminology."""

import os
import sys
import json
import asyncio
from pathlib import Path

from tr181_comparator.cli import TR181ComparatorCLI
from tr181_comparator.config import SubsetConfig, SystemConfig, ExportConfig
from tr181_comparator.main import TR181ComparatorApp
from tr181_comparator.extractors import SubsetManager


async def test_deprecated_cli_commands():
    """Test deprecated CLI commands."""
    print("Testing deprecated CLI commands...")
    
    # Create test files
    with open("test_subset.json", "w") as f:
        json.dump({
            "name": "Test Subset",
            "nodes": [
                {
                    "path": "Device.WiFi.Radio.1.Channel",
                    "value": 6
                }
            ]
        }, f)
    
    with open("test_device.json", "w") as f:
        json.dump({
            "type": "rest",
            "endpoint": "http://test-device.example.com:8080",
            "authentication": {
                "username": "test",
                "password": "test123"
            }
        }, f)
    
    # Test deprecated CLI commands
    cli = TR181ComparatorCLI()
    
    # Test 'validate-subset' command
    print("\nTesting 'validate-subset' command...")
    try:
        result = await cli.run([
            'validate-subset',
            '--subset-file', 'test_subset.json'
        ])
        print(f"Command returned: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 'subset-vs-device' command
    print("\nTesting 'subset-vs-device' command...")
    try:
        result = await cli.run([
            'subset-vs-device',
            '--subset-file', 'test_subset.json',
            '--device-config', 'test_device.json',
            '--output', 'test_output.json'
        ])
        print(f"Command returned: {result}")
    except Exception as e:
        print(f"Error: {e}")


async def test_deprecated_api_usage():
    """Test deprecated API usage."""
    print("\nTesting deprecated API usage...")
    
    # Test SubsetConfig class
    print("\nTesting SubsetConfig class...")
    try:
        subset_config = SubsetConfig(
            name="Test Subset",
            description="Test subset for backward compatibility",
            file_path="test_subset.json"
        )
        print(f"Created SubsetConfig: {subset_config}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test SubsetManager class
    print("\nTesting SubsetManager class...")
    try:
        subset_manager = SubsetManager("test_subset.json")
        print(f"Created SubsetManager: {subset_manager}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test deprecated methods in TR181ComparatorApp
    print("\nTesting deprecated methods in TR181ComparatorApp...")
    try:
        system_config = SystemConfig(
            devices=[],
            operator_requirements=[],
            export_settings=ExportConfig(
                default_format='json',
                include_metadata=True
            ),
            hook_configs={},
            connection_defaults={}
        )
        
        app = TR181ComparatorApp(system_config)
        
        # Test validate_subset method
        is_valid, errors = await app.validate_subset_file("test_subset.json")
        print(f"validate_subset_file result: {is_valid}, errors: {errors}")
        
        # We can't actually test compare_subset_vs_device without mocking
        print("Note: compare_subset_vs_device method exists but not tested")
        
    except Exception as e:
        print(f"Error: {e}")


async def main():
    """Run all backward compatibility tests."""
    print("=== TR181 Comparator Backward Compatibility Tests ===\n")
    
    await test_deprecated_cli_commands()
    await test_deprecated_api_usage()
    
    # Clean up test files
    print("\nCleaning up test files...")
    for file in ["test_subset.json", "test_device.json", "test_output.json"]:
        if os.path.exists(file):
            os.remove(file)
    
    print("\nBackward compatibility tests completed.")


if __name__ == "__main__":
    asyncio.run(main())