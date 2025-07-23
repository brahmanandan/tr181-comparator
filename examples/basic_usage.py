#!/usr/bin/env python3
"""
Basic Usage Examples for TR181 Node Comparator

This file demonstrates the most common usage patterns for the TR181 Node Comparator.
"""

import asyncio
import json
from datetime import datetime
from tr181_comparator import (
    CWMPExtractor, OperatorRequirementManager, HookBasedDeviceExtractor,
    ComparisonEngine, EnhancedComparisonEngine,
    TR181Node, AccessLevel, ValueRange,
    DeviceConfig, RESTAPIHook, CWMPHook
)

async def example_1_basic_cwmp_extraction():
    """Example 1: Extract TR181 nodes from a CWMP device."""
    print("Example 1: Basic CWMP Extraction")
    print("-" * 40)
    
    # Configure CWMP connection
    cwmp_config = {
        'endpoint': 'http://192.168.1.1:7547/cwmp',
        'username': 'admin',
        'password': 'admin123',
        'timeout': 30
    }
    
    try:
        # Create CWMP extractor
        extractor = CWMPExtractor(cwmp_config)
        
        # Validate connection first
        if await extractor.validate():
            print("✓ CWMP connection validated")
            
            # Extract all TR181 nodes
            nodes = await extractor.extract()
            print(f"✓ Extracted {len(nodes)} TR181 nodes")
            
            # Display first few nodes
            print("\nFirst 5 nodes:")
            for node in nodes[:5]:
                print(f"  {node.path}: {node.data_type} = {node.value} ({node.access})")
            
            # Get source information
            source_info = extractor.get_source_info()
            print(f"\nSource: {source_info.type} - {source_info.identifier}")
            print(f"Extracted at: {source_info.timestamp}")
            
        else:
            print("✗ CWMP connection validation failed")
            
    except Exception as e:
        print(f"✗ CWMP extraction failed: {e}")

async def example_2_create_custom_operator_requirement():
    """Example 2: Create and save a custom TR181 operator requirement."""
    print("\nExample 2: Create Custom Operator Requirement")
    print("-" * 40)
    
    # Define custom TR181 nodes
    custom_nodes = [
        TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            description="WiFi channel number",
            value_range=ValueRange(
                min_value=1,
                max_value=11,
                allowed_values=[1, 6, 11]  # Non-overlapping channels
            )
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            description="WiFi network name",
            value_range=ValueRange(
                max_length=32,
                pattern=r'^[a-zA-Z0-9_-]+$'
            )
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            description="Enable/disable WiFi access point"
        ),
        TR181Node(
            path="Device.DeviceInfo.Manufacturer",
            name="Manufacturer",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            description="Device manufacturer name"
        ),
        TR181Node(
            path="Device.DeviceInfo.ModelName",
            name="ModelName",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            description="Device model name"
        )
    ]
    
    try:
        # Create operator requirement manager
        operator_requirement_manager = OperatorRequirementManager("examples/wifi_operator_requirement.json")
        
        # Save the custom operator requirement
        await operator_requirement_manager.save_operator_requirement(custom_nodes)
        print("✓ Custom operator requirement saved to wifi_operator_requirement.json")
        
        # Load it back to verify
        loaded_nodes = await operator_requirement_manager.extract()
        print(f"✓ Loaded {len(loaded_nodes)} nodes from operator requirement")
        
        # Display operator requirement contents
        print("\nOperator requirement contents:")
        for node in loaded_nodes:
            constraints = ""
            if node.value_range:
                if node.value_range.allowed_values:
                    constraints = f" (allowed: {node.value_range.allowed_values})"
                elif node.value_range.min_value is not None or node.value_range.max_value is not None:
                    constraints = f" (range: {node.value_range.min_value}-{node.value_range.max_value})"
            print(f"  {node.path}: {node.data_type} ({node.access}){constraints}")
        
    except Exception as e:
        print(f"✗ Operator requirement creation failed: {e}")

async def example_3_basic_comparison():
    """Example 3: Compare CWMP nodes against custom operator requirement."""
    print("\nExample 3: Basic Comparison")
    print("-" * 40)
    
    try:
        # Load the operator requirement we created in example 2
        operator_requirement_manager = OperatorRequirementManager("examples/wifi_operator_requirement.json")
        operator_requirement_nodes = await operator_requirement_manager.extract()
        print(f"✓ Loaded {len(operator_requirement_nodes)} nodes from operator requirement")
        
        # For demonstration, create some mock CWMP nodes
        # In real usage, these would come from CWMPExtractor
        mock_cwmp_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6
            ),
            TR181Node(
                path="Device.WiFi.AccessPoint.1.SSID",
                name="SSID",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="MyWiFiNetwork"
            ),
            TR181Node(
                path="Device.WiFi.AccessPoint.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True
            ),
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="Example Corp"
            ),
            # This node exists in CWMP but not in operator requirement
            TR181Node(
                path="Device.WiFi.Radio.1.TransmitPower",
                name="TransmitPower",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=20
            )
        ]
        print(f"✓ Created {len(mock_cwmp_nodes)} mock CWMP nodes")
        
        # Perform comparison
        engine = ComparisonEngine()
        result = await engine.compare(mock_cwmp_nodes, operator_requirement_nodes)
        
        # Display results
        print(f"\nComparison Results:")
        print(f"  CWMP nodes: {result.summary.total_nodes_source1}")
        print(f"  Operator requirement nodes: {result.summary.total_nodes_source2}")
        print(f"  Common nodes: {result.summary.common_nodes}")
        print(f"  Differences: {result.summary.differences_count}")
        
        if result.only_in_source1:
            print(f"\nNodes only in CWMP ({len(result.only_in_source1)}):")
            for node in result.only_in_source1:
                print(f"  + {node.path} = {node.value}")
        
        if result.only_in_source2:
            print(f"\nNodes only in operator requirement ({len(result.only_in_source2)}):")
            for node in result.only_in_source2:
                print(f"  - {node.path}")
        
        if result.differences:
            print(f"\nProperty differences ({len(result.differences)}):")
            for diff in result.differences:
                print(f"  ~ {diff.path}.{diff.property}: {diff.source1_value} vs {diff.source2_value}")
        
    except Exception as e:
        print(f"✗ Comparison failed: {e}")

async def example_4_device_extraction():
    """Example 4: Extract TR181 nodes from a device using REST API."""
    print("\nExample 4: Device Extraction via REST API")
    print("-" * 40)
    
    try:
        # Configure device connection
        device_config = DeviceConfig(
            name="test_device",
            type="rest",
            endpoint="http://192.168.1.10/api/tr181",
            authentication={
                "type": "bearer",
                "token": "your-api-token-here"
            },
            timeout=30
        )
        
        # Create device extractor with REST API hook
        hook = RESTAPIHook()
        extractor = HookBasedDeviceExtractor(device_config, hook)
        
        # Validate device connectivity
        if await extractor.validate():
            print("✓ Device connection validated")
            
            # Extract TR181 nodes from device
            device_nodes = await extractor.extract()
            print(f"✓ Extracted {len(device_nodes)} nodes from device")
            
            # Display device information
            source_info = extractor.get_source_info()
            print(f"\nDevice: {source_info.identifier}")
            print(f"Type: {source_info.type}")
            print(f"Extracted at: {source_info.timestamp}")
            
            # Show some example nodes
            if device_nodes:
                print(f"\nSample device nodes:")
                for node in device_nodes[:3]:
                    print(f"  {node.path}: {node.data_type} = {node.value}")
            
        else:
            print("✗ Device connection validation failed")
            print("Note: This example uses dummy REST API hook implementation")
            
    except Exception as e:
        print(f"✗ Device extraction failed: {e}")

async def example_5_enhanced_comparison():
    """Example 5: Enhanced comparison with validation."""
    print("\nExample 5: Enhanced Comparison with Validation")
    print("-" * 40)
    
    try:
        # Load operator requirement (specification)
        operator_requirement_manager = OperatorRequirementManager("examples/wifi_operator_requirement.json")
        operator_requirement_nodes = await operator_requirement_manager.extract()
        
        # Create mock device nodes with some validation issues
        device_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=13  # Invalid channel (not in allowed values)
            ),
            TR181Node(
                path="Device.WiFi.AccessPoint.1.SSID",
                name="SSID",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="My WiFi Network!"  # Invalid characters
            ),
            TR181Node(
                path="Device.WiFi.AccessPoint.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True
            ),
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="Example Corp"
            )
        ]
        
        # Perform enhanced comparison
        enhanced_engine = EnhancedComparisonEngine()
        result = await enhanced_engine.compare_with_validation(
            operator_requirement_nodes, 
            device_nodes
        )
        
        # Display comprehensive results
        summary = result.get_summary()
        
        print("Enhanced Comparison Summary:")
        print(f"  Basic comparison differences: {summary['basic_comparison']['total_differences']}")
        print(f"  Missing in device: {summary['basic_comparison']['missing_in_device']}")
        print(f"  Extra in device: {summary['basic_comparison']['extra_in_device']}")
        print(f"  Validation errors: {summary['validation']['nodes_with_errors']}")
        print(f"  Validation warnings: {summary['validation']['total_warnings']}")
        
        # Show validation issues
        if result.validation_results:
            print(f"\nValidation Issues:")
            for path, validation_result in result.validation_results:
                if not validation_result.is_valid:
                    print(f"  ERROR - {path}:")
                    for error in validation_result.errors:
                        print(f"    {error}")
                elif validation_result.warnings:
                    print(f"  WARNING - {path}:")
                    for warning in validation_result.warnings:
                        print(f"    {warning}")
        
    except Exception as e:
        print(f"✗ Enhanced comparison failed: {e}")

async def example_6_export_results():
    """Example 6: Export comparison results in different formats."""
    print("\nExample 6: Export Comparison Results")
    print("-" * 40)
    
    try:
        # Perform a basic comparison (reusing previous examples)
        operator_requirement_manager = OperatorRequirementManager("examples/wifi_operator_requirement.json")
        operator_requirement_nodes = await operator_requirement_manager.extract()
        
        # Mock CWMP nodes
        cwmp_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6
            ),
            TR181Node(
                path="Device.WiFi.AccessPoint.1.SSID",
                name="SSID",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="TestNetwork"
            )
        ]
        
        engine = ComparisonEngine()
        result = await engine.compare(cwmp_nodes, operator_requirement_nodes)
        
        # Export to JSON
        json_report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "comparison_type": "cwmp_vs_operator_requirement",
                "tool_version": "1.0.0"
            },
            "summary": {
                "total_cwmp_nodes": result.summary.total_nodes_source1,
                "total_operator_requirement_nodes": result.summary.total_nodes_source2,
                "common_nodes": result.summary.common_nodes,
                "differences": result.summary.differences_count
            },
            "results": {
                "only_in_cwmp": [
                    {
                        "path": node.path,
                        "type": node.data_type,
                        "value": node.value,
                        "access": node.access.value
                    }
                    for node in result.only_in_source1
                ],
                "only_in_operator_requirement": [
                    {
                        "path": node.path,
                        "type": node.data_type,
                        "access": node.access.value
                    }
                    for node in result.only_in_source2
                ],
                "differences": [
                    {
                        "path": diff.path,
                        "property": diff.property,
                        "cwmp_value": diff.source1_value,
                        "operator_requirement_value": diff.source2_value,
                        "severity": diff.severity.value
                    }
                    for diff in result.differences
                ]
            }
        }
        
        # Save JSON report
        with open("examples/comparison_report.json", "w") as f:
            json.dump(json_report, f, indent=2)
        print("✓ JSON report saved to comparison_report.json")
        
        # Create human-readable text report
        text_report = f"""TR181 Comparison Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY
=======
CWMP Nodes: {result.summary.total_nodes_source1}
Operator Requirement Nodes: {result.summary.total_nodes_source2}
Common Nodes: {result.summary.common_nodes}
Differences: {result.summary.differences_count}

NODES ONLY IN CWMP
==================
"""
        
        for node in result.only_in_source1:
            text_report += f"{node.path}: {node.data_type} = {node.value} ({node.access.value})\n"
        
        text_report += f"""
NODES ONLY IN OPERATOR REQUIREMENT
==================================
"""
        
        for node in result.only_in_source2:
            text_report += f"{node.path}: {node.data_type} ({node.access.value})\n"
        
        if result.differences:
            text_report += f"""
PROPERTY DIFFERENCES
====================
"""
            for diff in result.differences:
                text_report += f"{diff.path}.{diff.property}: {diff.source1_value} vs {diff.source2_value}\n"
        
        # Save text report
        with open("examples/comparison_report.txt", "w") as f:
            f.write(text_report)
        print("✓ Text report saved to comparison_report.txt")
        
        print(f"\nReports generated:")
        print(f"  - examples/comparison_report.json (machine-readable)")
        print(f"  - examples/comparison_report.txt (human-readable)")
        
    except Exception as e:
        print(f"✗ Export failed: {e}")

async def main():
    """Run all examples."""
    print("TR181 Node Comparator - Basic Usage Examples")
    print("=" * 50)
    
    # Run examples in sequence
    await example_1_basic_cwmp_extraction()
    await example_2_create_custom_operator_requirement()
    await example_3_basic_comparison()
    await example_4_device_extraction()
    await example_5_enhanced_comparison()
    await example_6_export_results()
    
    print(f"\n" + "=" * 50)
    print("All examples completed!")
    print("\nFiles created:")
    print("  - examples/wifi_operator_requirement.json")
    print("  - examples/comparison_report.json")
    print("  - examples/comparison_report.txt")

if __name__ == "__main__":
    asyncio.run(main())