#!/usr/bin/env python3
"""
Enhanced Comparison Example for TR181 Node Comparator

This example demonstrates advanced comparison features including:
- Validation of device implementations against specifications
- Event and function testing
- Custom validation rules
- Comprehensive reporting
"""

import asyncio
import json
from datetime import datetime
from tr181_comparator import (
    EnhancedComparisonEngine, OperatorRequirementManager, HookBasedDeviceExtractor,
    TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function,
    DeviceConfig, RESTAPIHook, TR181Validator, ValidationResult
)

class CustomEnterpriseValidator(TR181Validator):
    """Custom validator with enterprise-specific rules."""
    
    def validate_node(self, node: TR181Node, actual_value=None) -> ValidationResult:
        """Validate node with enterprise rules."""
        # Run standard validation first
        result = super().validate_node(node, actual_value)
        
        # Add enterprise-specific validation
        self._validate_enterprise_naming(node, result)
        self._validate_security_requirements(node, actual_value, result)
        self._validate_performance_requirements(node, actual_value, result)
        
        return result
    
    def _validate_enterprise_naming(self, node: TR181Node, result: ValidationResult):
        """Validate enterprise naming conventions."""
        # WiFi SSIDs must start with company prefix
        if 'WiFi.AccessPoint' in node.path and 'SSID' in node.name:
            if node.value and not str(node.value).startswith('CORP_'):
                result.add_warning("WiFi SSID should start with 'CORP_' prefix")
        
        # Custom parameters must be in vendor namespace
        if node.is_custom and not node.path.startswith('Device.X_VENDOR_'):
            result.add_error("Custom parameters must use vendor-specific namespace")
    
    def _validate_security_requirements(self, node: TR181Node, value, result: ValidationResult):
        """Validate security requirements."""
        # Password parameters should be write-only
        if 'Password' in node.path and node.access != AccessLevel.WRITE_ONLY:
            result.add_error(f"Password parameter {node.path} must be write-only")
        
        # Check for weak default passwords
        if 'Password' in node.path and value:
            weak_passwords = ['admin', 'password', '123456', 'default', '']
            if str(value).lower() in weak_passwords:
                result.add_error(f"Weak default password detected in {node.path}")
        
        # Encryption should be enabled
        if 'Encryption' in node.path and value == 'None':
            result.add_error("Encryption must be enabled for security")
    
    def _validate_performance_requirements(self, node: TR181Node, value, result: ValidationResult):
        """Validate performance requirements."""
        # WiFi channel validation for optimal performance
        if 'WiFi.Radio' in node.path and 'Channel' in node.name:
            if value and value not in [1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161]:
                result.add_warning(f"WiFi channel {value} may cause interference")
        
        # Transmit power limits
        if 'TransmitPower' in node.path and value:
            if '2.4GHz' in node.path and value > 20:
                result.add_error(f"2.4GHz transmit power {value}dBm exceeds limit (20dBm)")
            elif '5GHz' in node.path and value > 23:
                result.add_error(f"5GHz transmit power {value}dBm exceeds limit (23dBm)")

async def create_comprehensive_operator_requirement():
    """Create a comprehensive operator requirement with events and functions."""
    print("Creating comprehensive TR181 operator requirement...")
    
    # Define events
    wifi_events = [
        TR181Event(
            name="WiFiChannelChange",
            path="Device.WiFi.Radio.1.ChannelChangeEvent",
            parameters=["Device.WiFi.Radio.1.Channel", "Device.WiFi.Radio.1.OperatingFrequencyBand"],
            description="Triggered when WiFi channel changes"
        ),
        TR181Event(
            name="ClientConnect",
            path="Device.WiFi.AccessPoint.1.ClientConnectEvent",
            parameters=["Device.WiFi.AccessPoint.1.AssociatedDeviceNumberOfEntries"],
            description="Triggered when a client connects to WiFi"
        )
    ]
    
    # Define functions
    wifi_functions = [
        TR181Function(
            name="WiFiScan",
            path="Device.WiFi.Radio.1.Scan()",
            input_parameters=["Device.WiFi.Radio.1.ScanSettings.Timeout"],
            output_parameters=["Device.WiFi.Radio.1.ScanResult.NumberOfEntries"],
            description="Perform WiFi network scan"
        ),
        TR181Function(
            name="ResetToDefaults",
            path="Device.FactoryReset()",
            input_parameters=["Device.FactoryResetType"],
            output_parameters=["Device.RebootRequired"],
            description="Reset device to factory defaults"
        )
    ]
    
    # Create comprehensive node set
    nodes = [
        # WiFi Radio parameters
        TR181Node(
            path="Device.WiFi.Radio.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            description="Enable/disable WiFi radio",
            events=wifi_events[:1]  # Channel change event
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            description="WiFi channel number",
            value_range=ValueRange(
                min_value=1,
                max_value=165,
                allowed_values=[1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161]
            ),
            events=wifi_events[:1],
            functions=wifi_functions[:1]  # WiFi scan function
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.TransmitPower",
            name="TransmitPower",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            description="Transmit power in dBm",
            value_range=ValueRange(min_value=1, max_value=23)
        ),
        
        # WiFi Access Point parameters
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            description="Enable/disable access point"
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            description="WiFi network name",
            value_range=ValueRange(
                max_length=32,
                pattern=r'^CORP_[a-zA-Z0-9_-]+$'  # Enterprise naming convention
            ),
            events=wifi_events[1:]  # Client connect event
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Security.ModeEnabled",
            name="ModeEnabled",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            description="Security mode",
            value_range=ValueRange(
                allowed_values=["WPA2-PSK", "WPA3-PSK", "WPA2-Enterprise", "WPA3-Enterprise"]
            )
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Security.KeyPassphrase",
            name="KeyPassphrase",
            data_type="string",
            access=AccessLevel.WRITE_ONLY,  # Security requirement
            description="WiFi password",
            value_range=ValueRange(min_length=8, max_length=63)
        ),
        
        # Device Information
        TR181Node(
            path="Device.DeviceInfo.Manufacturer",
            name="Manufacturer",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            description="Device manufacturer"
        ),
        TR181Node(
            path="Device.DeviceInfo.ModelName",
            name="ModelName",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            description="Device model name"
        ),
        TR181Node(
            path="Device.DeviceInfo.SoftwareVersion",
            name="SoftwareVersion",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            description="Software version",
            value_range=ValueRange(
                pattern=r'^\d+\.\d+\.\d+$'  # Semantic versioning
            )
        ),
        
        # Custom vendor parameters
        TR181Node(
            path="Device.X_VENDOR_CustomFeature.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            description="Enable custom vendor feature",
            is_custom=True
        ),
        TR181Node(
            path="Device.X_VENDOR_CustomFeature.Mode",
            name="Mode",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            description="Custom feature mode",
            value_range=ValueRange(
                allowed_values=["Standard", "Enhanced", "Performance"]
            ),
            is_custom=True,
            functions=wifi_functions[1:]  # Reset function
        )
    ]
    
    # Save comprehensive operator requirement
    operator_requirement_manager = OperatorRequirementManager("examples/comprehensive_operator_requirement.json")
    await operator_requirement_manager.save_operator_requirement(nodes)
    print(f"✓ Saved {len(nodes)} nodes to comprehensive operator requirement")
    
    return nodes

async def create_mock_device_implementation():
    """Create mock device implementation with various compliance issues."""
    print("Creating mock device implementation...")
    
    # Device implementation with some issues for demonstration
    device_nodes = [
        # WiFi Radio - mostly compliant
        TR181Node(
            path="Device.WiFi.Radio.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=13  # Issue: Not in allowed channels list
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.TransmitPower",
            name="TransmitPower",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=25  # Issue: Exceeds power limit
        ),
        
        # WiFi Access Point - has security issues
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="MyWiFi"  # Issue: Doesn't follow naming convention
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Security.ModeEnabled",
            name="ModeEnabled",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="WPA2-PSK"  # Compliant
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Security.KeyPassphrase",
            name="KeyPassphrase",
            data_type="string",
            access=AccessLevel.READ_WRITE,  # Issue: Should be write-only
            value="password123"  # Issue: Weak password
        ),
        
        # Device Information - compliant
        TR181Node(
            path="Device.DeviceInfo.Manufacturer",
            name="Manufacturer",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="Example Corp"
        ),
        TR181Node(
            path="Device.DeviceInfo.ModelName",
            name="ModelName",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="WiFi-Router-Pro"
        ),
        TR181Node(
            path="Device.DeviceInfo.SoftwareVersion",
            name="SoftwareVersion",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="2.1.0"  # Compliant with semantic versioning
        ),
        
        # Custom vendor parameters - has namespace issue
        TR181Node(
            path="Device.CustomFeature.Enable",  # Issue: Wrong namespace
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True,
            is_custom=True
        ),
        
        # Extra parameter not in operator requirement
        TR181Node(
            path="Device.WiFi.Radio.1.OperatingFrequencyBand",
            name="OperatingFrequencyBand",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="2.4GHz"
        )
    ]
    
    print(f"✓ Created {len(device_nodes)} mock device nodes")
    return device_nodes

async def perform_enhanced_comparison():
    """Perform comprehensive enhanced comparison."""
    print("\nPerforming Enhanced Comparison...")
    print("-" * 50)
    
    # Create test data
    operator_requirement_nodes = await create_comprehensive_operator_requirement()
    device_nodes = await create_mock_device_implementation()
    
    # Create enhanced comparison engine with custom validator
    enhanced_engine = EnhancedComparisonEngine()
    enhanced_engine.validator = CustomEnterpriseValidator()
    
    # Perform enhanced comparison
    result = await enhanced_engine.compare_with_validation(
        operator_requirement_nodes,
        device_nodes
    )
    
    # Generate comprehensive summary
    summary = result.get_summary()
    
    print("Enhanced Comparison Results:")
    print("=" * 30)
    print(f"Operator requirement nodes: {len(operator_requirement_nodes)}")
    print(f"Device nodes: {len(device_nodes)}")
    print(f"Common nodes: {summary['basic_comparison']['common_nodes']}")
    print(f"Missing in device: {summary['basic_comparison']['missing_in_device']}")
    print(f"Extra in device: {summary['basic_comparison']['extra_in_device']}")
    print(f"Property differences: {summary['basic_comparison']['total_differences']}")
    print(f"Validation errors: {summary['validation']['nodes_with_errors']}")
    print(f"Validation warnings: {summary['validation']['total_warnings']}")
    
    # Show detailed validation results
    if result.validation_results:
        print(f"\nValidation Issues:")
        print("-" * 20)
        
        error_count = 0
        warning_count = 0
        
        for path, validation_result in result.validation_results:
            if not validation_result.is_valid:
                error_count += 1
                print(f"❌ ERROR - {path}:")
                for error in validation_result.errors:
                    print(f"   {error}")
            
            if validation_result.warnings:
                warning_count += 1
                print(f"⚠️  WARNING - {path}:")
                for warning in validation_result.warnings:
                    print(f"   {warning}")
        
        print(f"\nSummary: {error_count} errors, {warning_count} warnings")
    
    # Show missing implementations
    if result.basic_comparison.only_in_source1:
        print(f"\nMissing Implementations:")
        print("-" * 25)
        for node in result.basic_comparison.only_in_source1:
            print(f"❌ {node.path} ({node.data_type})")
    
    # Show extra implementations
    if result.basic_comparison.only_in_source2:
        print(f"\nExtra Implementations:")
        print("-" * 22)
        for node in result.basic_comparison.only_in_source2:
            print(f"➕ {node.path} = {node.value}")
    
    # Show property differences
    if result.basic_comparison.differences:
        print(f"\nProperty Differences:")
        print("-" * 21)
        for diff in result.basic_comparison.differences:
            severity_icon = "❌" if diff.severity.value == "error" else "⚠️"
            print(f"{severity_icon} {diff.path}.{diff.property}: {diff.source1_value} → {diff.source2_value}")
    
    return result

async def generate_compliance_report(comparison_result):
    """Generate a comprehensive compliance report."""
    print(f"\nGenerating Compliance Report...")
    print("-" * 35)
    
    summary = comparison_result.get_summary()
    
    # Calculate compliance score
    total_checks = len(comparison_result.validation_results)
    error_count = summary['validation']['nodes_with_errors']
    warning_count = summary['validation']['total_warnings']
    
    # Compliance scoring
    compliance_score = max(0, 100 - (error_count * 10) - (warning_count * 2))
    compliance_level = "EXCELLENT" if compliance_score >= 90 else \
                     "GOOD" if compliance_score >= 75 else \
                     "FAIR" if compliance_score >= 50 else \
                     "POOR"
    
    # Create detailed report
    report = {
        "metadata": {
            "report_type": "TR181_Compliance_Report",
            "generated_at": datetime.now().isoformat(),
            "tool_version": "1.0.0",
            "validator": "CustomEnterpriseValidator"
        },
        "executive_summary": {
            "compliance_score": compliance_score,
            "compliance_level": compliance_level,
            "total_parameters_checked": total_checks,
            "critical_issues": error_count,
            "warnings": warning_count,
            "recommendation": "APPROVED" if compliance_score >= 75 else "REQUIRES_REVIEW"
        },
        "detailed_results": {
            "validation_issues": [],
            "missing_implementations": [],
            "extra_implementations": [],
            "property_differences": []
        },
        "compliance_categories": {
            "security": {"score": 0, "issues": []},
            "performance": {"score": 0, "issues": []},
            "naming_conventions": {"score": 0, "issues": []},
            "data_validation": {"score": 0, "issues": []}
        }
    }
    
    # Populate validation issues
    for path, validation_result in comparison_result.validation_results:
        if not validation_result.is_valid or validation_result.warnings:
            issue = {
                "parameter": path,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
                "severity": "error" if not validation_result.is_valid else "warning"
            }
            report["detailed_results"]["validation_issues"].append(issue)
            
            # Categorize issues
            for error in validation_result.errors + validation_result.warnings:
                if any(keyword in error.lower() for keyword in ['password', 'security', 'encryption']):
                    report["compliance_categories"]["security"]["issues"].append(error)
                elif any(keyword in error.lower() for keyword in ['channel', 'power', 'performance']):
                    report["compliance_categories"]["performance"]["issues"].append(error)
                elif any(keyword in error.lower() for keyword in ['naming', 'prefix', 'namespace']):
                    report["compliance_categories"]["naming_conventions"]["issues"].append(error)
                else:
                    report["compliance_categories"]["data_validation"]["issues"].append(error)
    
    # Calculate category scores
    for category in report["compliance_categories"]:
        issue_count = len(report["compliance_categories"][category]["issues"])
        report["compliance_categories"][category]["score"] = max(0, 100 - (issue_count * 15))
    
    # Populate other results
    report["detailed_results"]["missing_implementations"] = [
        {"parameter": node.path, "type": node.data_type, "access": node.access.value}
        for node in comparison_result.basic_comparison.only_in_source1
    ]
    
    report["detailed_results"]["extra_implementations"] = [
        {"parameter": node.path, "type": node.data_type, "value": node.value}
        for node in comparison_result.basic_comparison.only_in_source2
    ]
    
    report["detailed_results"]["property_differences"] = [
        {
            "parameter": diff.path,
            "property": diff.property,
            "expected": diff.source1_value,
            "actual": diff.source2_value,
            "severity": diff.severity.value
        }
        for diff in comparison_result.basic_comparison.differences
    ]
    
    # Save reports
    with open("examples/compliance_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Generate executive summary
    executive_summary = f"""
TR181 COMPLIANCE REPORT
=======================

Device Assessment: {report['executive_summary']['recommendation']}
Compliance Score: {compliance_score}/100 ({compliance_level})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY
-------
Parameters Checked: {total_checks}
Critical Issues: {error_count}
Warnings: {warning_count}

COMPLIANCE BY CATEGORY
----------------------
Security: {report['compliance_categories']['security']['score']}/100
Performance: {report['compliance_categories']['performance']['score']}/100
Naming Conventions: {report['compliance_categories']['naming_conventions']['score']}/100
Data Validation: {report['compliance_categories']['data_validation']['score']}/100

RECOMMENDATIONS
---------------
"""
    
    if compliance_score >= 90:
        executive_summary += "✅ Device meets all compliance requirements. Approved for deployment.\n"
    elif compliance_score >= 75:
        executive_summary += "✅ Device meets basic compliance requirements with minor issues.\n"
    elif compliance_score >= 50:
        executive_summary += "⚠️  Device has significant compliance issues that should be addressed.\n"
    else:
        executive_summary += "❌ Device has critical compliance issues. Not recommended for deployment.\n"
    
    executive_summary += f"\nDetailed technical report: compliance_report.json\n"
    
    with open("examples/executive_summary.txt", "w") as f:
        f.write(executive_summary)
    
    print("✓ Compliance report generated:")
    print("  - examples/compliance_report.json (detailed technical report)")
    print("  - examples/executive_summary.txt (executive summary)")
    
    # Display executive summary
    print(f"\n{executive_summary}")

async def main():
    """Run enhanced comparison example."""
    print("TR181 Enhanced Comparison Example")
    print("=" * 40)
    
    try:
        # Perform enhanced comparison
        result = await perform_enhanced_comparison()
        
        # Generate compliance report
        await generate_compliance_report(result)
        
        print(f"\n" + "=" * 40)
        print("Enhanced comparison completed successfully!")
        
    except Exception as e:
        print(f"❌ Enhanced comparison failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())