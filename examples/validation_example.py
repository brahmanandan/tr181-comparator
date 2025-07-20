#!/usr/bin/env python3
"""
Validation Example for TR181 Node Comparator

This example demonstrates comprehensive validation features including:
- Data type validation
- Value range validation
- TR181 path format validation
- Custom validation rules
- Event and function validation
"""

import asyncio
import re
from datetime import datetime
from tr181_comparator import (
    TR181Validator, ValidationResult, EventFunctionTester,
    TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function,
    HookBasedDeviceExtractor, DeviceConfig, RESTAPIHook
)

class ComprehensiveValidator(TR181Validator):
    """Extended validator with comprehensive validation rules."""
    
    def __init__(self):
        super().__init__()
        self.custom_rules = self._load_custom_rules()
    
    def validate_node(self, node: TR181Node, actual_value=None) -> ValidationResult:
        """Perform comprehensive node validation."""
        result = super().validate_node(node, actual_value)
        
        # Add custom validation layers
        self._validate_business_rules(node, actual_value, result)
        self._validate_regulatory_compliance(node, actual_value, result)
        self._validate_interoperability(node, actual_value, result)
        
        return result
    
    def _validate_business_rules(self, node: TR181Node, value, result: ValidationResult):
        """Validate business-specific rules."""
        # WiFi SSID must follow corporate naming
        if 'WiFi.AccessPoint' in node.path and 'SSID' in node.name:
            if value and not self._validate_corporate_ssid(str(value)):
                result.add_error("SSID must follow corporate naming convention: CORP_[LOCATION]_[PURPOSE]")
        
        # Device names must include model year
        if 'DeviceInfo.ModelName' in node.path and value:
            if not re.search(r'20\d{2}', str(value)):
                result.add_warning("Model name should include year for inventory tracking")
        
        # Admin passwords must meet complexity requirements
        if 'Password' in node.path and 'Admin' in node.path and value:
            if not self._validate_password_complexity(str(value)):
                result.add_error("Admin password must meet complexity requirements")
    
    def _validate_regulatory_compliance(self, node: TR181Node, value, result: ValidationResult):
        """Validate regulatory compliance requirements."""
        # WiFi channel compliance (varies by region)
        if 'WiFi.Radio' in node.path and 'Channel' in node.name and value:
            region = self._get_regulatory_region()  # Would be configurable
            allowed_channels = self._get_allowed_channels(region)
            
            if value not in allowed_channels:
                result.add_error(f"Channel {value} not allowed in {region} regulatory domain")
        
        # Transmit power limits
        if 'TransmitPower' in node.path and value:
            max_power = self._get_max_transmit_power(node.path)
            if value > max_power:
                result.add_error(f"Transmit power {value}dBm exceeds regulatory limit {max_power}dBm")
        
        # Encryption requirements
        if 'Security.ModeEnabled' in node.path and value:
            if value in ['None', 'WEP']:
                result.add_error("Weak encryption modes not allowed for compliance")
    
    def _validate_interoperability(self, node: TR181Node, value, result: ValidationResult):
        """Validate interoperability requirements."""
        # Standard port usage
        if 'Port' in node.path and value:
            reserved_ports = [22, 23, 80, 443, 7547]  # SSH, Telnet, HTTP, HTTPS, CWMP
            if value in reserved_ports:
                result.add_warning(f"Port {value} is reserved for standard services")
        
        # Protocol version compatibility
        if 'Version' in node.path and value:
            if 'SNMP' in node.path and value not in ['v2c', 'v3']:
                result.add_warning("SNMP v1 has known security issues")
            elif 'TLS' in node.path and value < '1.2':
                result.add_error("TLS version must be 1.2 or higher for security")
    
    def _load_custom_rules(self):
        """Load custom validation rules from configuration."""
        return {
            'ssid_pattern': r'^CORP_[A-Z]{2,10}_[A-Z]{3,15}$',
            'password_min_length': 12,
            'password_complexity': True,
            'regulatory_region': 'US',
            'max_power_2_4ghz': 20,
            'max_power_5ghz': 23
        }
    
    def _validate_corporate_ssid(self, ssid):
        """Validate corporate SSID naming convention."""
        pattern = self.custom_rules['ssid_pattern']
        return re.match(pattern, ssid) is not None
    
    def _validate_password_complexity(self, password):
        """Validate password complexity."""
        if len(password) < self.custom_rules['password_min_length']:
            return False
        
        if not self.custom_rules['password_complexity']:
            return True
        
        # Check complexity requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        return all([has_upper, has_lower, has_digit, has_special])
    
    def _get_regulatory_region(self):
        """Get regulatory region (would be configurable)."""
        return self.custom_rules.get('regulatory_region', 'US')
    
    def _get_allowed_channels(self, region):
        """Get allowed WiFi channels for region."""
        channel_maps = {
            'US': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 36, 40, 44, 48, 149, 153, 157, 161, 165],
            'EU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 36, 40, 44, 48],
            'JP': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 36, 40, 44, 48]
        }
        return channel_maps.get(region, channel_maps['US'])
    
    def _get_max_transmit_power(self, path):
        """Get maximum transmit power for frequency band."""
        if '2.4GHz' in path or '2_4GHz' in path:
            return self.custom_rules['max_power_2_4ghz']
        elif '5GHz' in path or '5_GHz' in path:
            return self.custom_rules['max_power_5ghz']
        return 20  # Default

async def demonstrate_data_type_validation():
    """Demonstrate data type validation."""
    print("Data Type Validation Examples")
    print("-" * 35)
    
    validator = TR181Validator()
    
    test_cases = [
        # Valid cases
        (TR181Node("Device.Test.StringParam", "StringParam", "string", AccessLevel.READ_WRITE), "test_value", True),
        (TR181Node("Device.Test.IntParam", "IntParam", "int", AccessLevel.READ_WRITE), 42, True),
        (TR181Node("Device.Test.BoolParam", "BoolParam", "boolean", AccessLevel.READ_WRITE), True, True),
        (TR181Node("Device.Test.DateParam", "DateParam", "dateTime", AccessLevel.READ_WRITE), "2023-12-01T10:30:00Z", True),
        
        # Invalid cases
        (TR181Node("Device.Test.StringParam", "StringParam", "string", AccessLevel.READ_WRITE), 123, False),
        (TR181Node("Device.Test.IntParam", "IntParam", "int", AccessLevel.READ_WRITE), "not_a_number", False),
        (TR181Node("Device.Test.BoolParam", "BoolParam", "boolean", AccessLevel.READ_WRITE), "maybe", False),
        (TR181Node("Device.Test.DateParam", "DateParam", "dateTime", AccessLevel.READ_WRITE), "invalid_date", False),
    ]
    
    for node, value, expected_valid in test_cases:
        result = validator.validate_node(node, value)
        status = "✓" if result.is_valid == expected_valid else "✗"
        print(f"{status} {node.path} ({node.data_type}) = {value}: {'Valid' if result.is_valid else 'Invalid'}")
        
        if not result.is_valid:
            for error in result.errors:
                print(f"    Error: {error}")

async def demonstrate_range_validation():
    """Demonstrate value range validation."""
    print(f"\nValue Range Validation Examples")
    print("-" * 35)
    
    validator = TR181Validator()
    
    # Test numeric ranges
    channel_node = TR181Node(
        path="Device.WiFi.Radio.1.Channel",
        name="Channel",
        data_type="int",
        access=AccessLevel.READ_WRITE,
        value_range=ValueRange(min_value=1, max_value=11)
    )
    
    channel_tests = [6, 1, 11, 0, 12, 13]  # Valid: 6, 1, 11; Invalid: 0, 12, 13
    
    print("WiFi Channel Range Validation (1-11):")
    for channel in channel_tests:
        result = validator.validate_node(channel_node, channel)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} Channel {channel}: {'Valid' if result.is_valid else 'Invalid'}")
        for error in result.errors:
            print(f"      Error: {error}")
    
    # Test enumerated values
    security_node = TR181Node(
        path="Device.WiFi.AccessPoint.1.Security.ModeEnabled",
        name="ModeEnabled",
        data_type="string",
        access=AccessLevel.READ_WRITE,
        value_range=ValueRange(allowed_values=["WPA2-PSK", "WPA3-PSK", "WPA2-Enterprise"])
    )
    
    security_tests = ["WPA2-PSK", "WPA3-PSK", "WEP", "None", "WPA2-Enterprise"]
    
    print(f"\nSecurity Mode Enumeration Validation:")
    for mode in security_tests:
        result = validator.validate_node(security_node, mode)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} Security mode '{mode}': {'Valid' if result.is_valid else 'Invalid'}")
        for error in result.errors:
            print(f"      Error: {error}")
    
    # Test string patterns
    ssid_node = TR181Node(
        path="Device.WiFi.AccessPoint.1.SSID",
        name="SSID",
        data_type="string",
        access=AccessLevel.READ_WRITE,
        value_range=ValueRange(
            max_length=32,
            pattern=r'^[a-zA-Z0-9_-]+$'  # Alphanumeric, underscore, hyphen only
        )
    )
    
    ssid_tests = ["ValidSSID", "Valid_SSID", "Valid-SSID", "Invalid SSID", "Invalid@SSID", "A" * 35]
    
    print(f"\nSSID Pattern Validation (alphanumeric, _, - only, max 32 chars):")
    for ssid in ssid_tests:
        result = validator.validate_node(ssid_node, ssid)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} SSID '{ssid}': {'Valid' if result.is_valid else 'Invalid'}")
        for error in result.errors:
            print(f"      Error: {error}")

async def demonstrate_path_validation():
    """Demonstrate TR181 path format validation."""
    print(f"\nTR181 Path Format Validation")
    print("-" * 35)
    
    validator = TR181Validator()
    
    path_tests = [
        # Valid paths
        ("Device.WiFi.Radio.1.Channel", True),
        ("Device.DeviceInfo.Manufacturer", True),
        ("Device.Ethernet.Interface.1.Enable", True),
        ("Device.X_VENDOR_CustomParam", True),
        
        # Invalid paths
        ("device.wifi.radio.1.channel", False),  # Wrong case
        ("WiFi.Radio.1.Channel", False),         # Missing Device prefix
        ("Device.WiFi..Radio.1.Channel", False), # Double dots
        ("Device.WiFi.Radio.1.", False),         # Trailing dot
        ("Device.WiFi.Radio.1.channel", False),  # Wrong case for parameter
    ]
    
    for path, expected_valid in path_tests:
        node = TR181Node(path, path.split('.')[-1], "string", AccessLevel.READ_ONLY)
        result = validator.validate_node(node)
        
        # Check path format specifically
        path_valid = validator.validate_path_format(path)
        status = "✓" if path_valid == expected_valid else "✗"
        
        print(f"{status} {path}: {'Valid' if path_valid else 'Invalid'}")
        
        if not result.is_valid:
            for error in result.errors:
                print(f"    Error: {error}")
        for warning in result.warnings:
            print(f"    Warning: {warning}")

async def demonstrate_custom_validation():
    """Demonstrate custom validation rules."""
    print(f"\nCustom Validation Rules")
    print("-" * 35)
    
    validator = ComprehensiveValidator()
    
    # Test corporate SSID validation
    ssid_node = TR181Node(
        path="Device.WiFi.AccessPoint.1.SSID",
        name="SSID",
        data_type="string",
        access=AccessLevel.READ_WRITE
    )
    
    ssid_tests = [
        "CORP_NYC_GUEST",      # Valid
        "CORP_LA_EMPLOYEE",    # Valid
        "MyWiFiNetwork",       # Invalid - doesn't follow convention
        "CORP_GUEST",          # Invalid - missing location
    ]
    
    print("Corporate SSID Naming Convention (CORP_[LOCATION]_[PURPOSE]):")
    for ssid in ssid_tests:
        result = validator.validate_node(ssid_node, ssid)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} SSID '{ssid}': {'Valid' if result.is_valid else 'Invalid'}")
        for error in result.errors:
            print(f"      Error: {error}")
        for warning in result.warnings:
            print(f"      Warning: {warning}")
    
    # Test password complexity
    password_node = TR181Node(
        path="Device.Users.User.1.AdminPassword",
        name="AdminPassword",
        data_type="string",
        access=AccessLevel.WRITE_ONLY
    )
    
    password_tests = [
        "ComplexP@ssw0rd123",  # Valid - meets all requirements
        "SimplePassword",      # Invalid - no numbers or special chars
        "short",               # Invalid - too short
        "password123",         # Invalid - no uppercase or special chars
    ]
    
    print(f"\nAdmin Password Complexity Validation:")
    for password in password_tests:
        result = validator.validate_node(password_node, password)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} Password complexity: {'Valid' if result.is_valid else 'Invalid'}")
        for error in result.errors:
            print(f"      Error: {error}")
    
    # Test regulatory compliance
    channel_node = TR181Node(
        path="Device.WiFi.Radio.1.Channel",
        name="Channel",
        data_type="int",
        access=AccessLevel.READ_WRITE
    )
    
    channel_tests = [1, 6, 11, 13, 14]  # 13, 14 not allowed in US
    
    print(f"\nRegulatory Compliance Validation (US channels):")
    for channel in channel_tests:
        result = validator.validate_node(channel_node, channel)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} Channel {channel}: {'Valid' if result.is_valid else 'Invalid'}")
        for error in result.errors:
            print(f"      Error: {error}")

async def demonstrate_event_function_validation():
    """Demonstrate event and function validation."""
    print(f"\nEvent and Function Validation")
    print("-" * 35)
    
    # Create mock device nodes for testing
    device_nodes = [
        TR181Node("Device.WiFi.Radio.1.Channel", "Channel", "int", AccessLevel.READ_WRITE, value=6),
        TR181Node("Device.WiFi.Radio.1.OperatingFrequencyBand", "OperatingFrequencyBand", "string", AccessLevel.READ_ONLY, value="2.4GHz"),
        TR181Node("Device.WiFi.AccessPoint.1.AssociatedDeviceNumberOfEntries", "AssociatedDeviceNumberOfEntries", "int", AccessLevel.READ_ONLY, value=3),
        TR181Node("Device.WiFi.Radio.1.ScanSettings.Timeout", "Timeout", "int", AccessLevel.READ_WRITE, value=30),
        TR181Node("Device.WiFi.Radio.1.ScanResult.NumberOfEntries", "NumberOfEntries", "int", AccessLevel.READ_ONLY, value=0),
    ]
    
    # Define events to test
    test_events = [
        TR181Event(
            name="WiFiChannelChange",
            path="Device.WiFi.Radio.1.ChannelChangeEvent",
            parameters=["Device.WiFi.Radio.1.Channel", "Device.WiFi.Radio.1.OperatingFrequencyBand"],
            description="Triggered when WiFi channel changes"
        ),
        TR181Event(
            name="ClientConnect",
            path="Device.WiFi.AccessPoint.1.ClientConnectEvent",
            parameters=["Device.WiFi.AccessPoint.1.AssociatedDeviceNumberOfEntries", "Device.WiFi.AccessPoint.1.MissingParam"],
            description="Triggered when a client connects"
        )
    ]
    
    # Define functions to test
    test_functions = [
        TR181Function(
            name="WiFiScan",
            path="Device.WiFi.Radio.1.Scan()",
            input_parameters=["Device.WiFi.Radio.1.ScanSettings.Timeout"],
            output_parameters=["Device.WiFi.Radio.1.ScanResult.NumberOfEntries"],
            description="Perform WiFi network scan"
        ),
        TR181Function(
            name="InvalidFunction",
            path="Device.WiFi.Radio.1.InvalidFunction()",
            input_parameters=["Device.WiFi.Radio.1.MissingInput"],
            output_parameters=["Device.WiFi.Radio.1.MissingOutput"],
            description="Function with missing parameters"
        )
    ]
    
    # Create mock device extractor for testing
    device_config = DeviceConfig(
        name="test_device",
        type="rest",
        endpoint="http://test.local/api"
    )
    hook = RESTAPIHook()
    device_extractor = HookBasedDeviceExtractor(device_config, hook)
    
    # Create event/function tester
    tester = EventFunctionTester(device_extractor)
    
    print("Event Implementation Validation:")
    for event in test_events:
        result = await tester.test_event_implementation(event, device_nodes)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} Event '{event.name}': {'Valid' if result.is_valid else 'Invalid'}")
        
        for error in result.errors:
            print(f"      Error: {error}")
        for warning in result.warnings:
            print(f"      Warning: {warning}")
    
    print(f"\nFunction Implementation Validation:")
    for function in test_functions:
        result = await tester.test_function_implementation(function, device_nodes)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} Function '{function.name}': {'Valid' if result.is_valid else 'Invalid'}")
        
        for error in result.errors:
            print(f"      Error: {error}")
        for warning in result.warnings:
            print(f"      Warning: {warning}")

async def demonstrate_validation_reporting():
    """Demonstrate comprehensive validation reporting."""
    print(f"\nValidation Reporting")
    print("-" * 25)
    
    validator = ComprehensiveValidator()
    
    # Create a comprehensive test node with multiple issues
    test_node = TR181Node(
        path="Device.WiFi.AccessPoint.1.SSID",
        name="SSID",
        data_type="string",
        access=AccessLevel.READ_WRITE,
        value_range=ValueRange(
            max_length=32,
            pattern=r'^CORP_[A-Z]{2,10}_[A-Z]{3,15}$'
        )
    )
    
    # Test with problematic value
    problematic_value = "MyHomeWiFi!"  # Violates pattern, has special char
    
    result = validator.validate_node(test_node, problematic_value)
    
    print(f"Comprehensive Validation Report for {test_node.path}:")
    print(f"Value: '{problematic_value}'")
    print(f"Overall Status: {'✓ VALID' if result.is_valid else '✗ INVALID'}")
    
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for i, error in enumerate(result.errors, 1):
            print(f"  {i}. {error}")
    
    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for i, warning in enumerate(result.warnings, 1):
            print(f"  {i}. {warning}")
    
    # Generate validation summary
    validation_summary = {
        "parameter": test_node.path,
        "data_type": test_node.data_type,
        "access_level": test_node.access.value,
        "test_value": problematic_value,
        "validation_result": {
            "is_valid": result.is_valid,
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "errors": result.errors,
            "warnings": result.warnings
        },
        "constraints": {
            "max_length": test_node.value_range.max_length if test_node.value_range else None,
            "pattern": test_node.value_range.pattern if test_node.value_range else None,
            "allowed_values": test_node.value_range.allowed_values if test_node.value_range else None
        },
        "recommendations": []
    }
    
    # Add recommendations based on errors
    if "pattern" in str(result.errors):
        validation_summary["recommendations"].append("Update SSID to follow corporate naming convention: CORP_[LOCATION]_[PURPOSE]")
    
    if "special" in str(result.errors).lower():
        validation_summary["recommendations"].append("Remove special characters from SSID")
    
    print(f"\nValidation Summary:")
    print(f"  Parameter: {validation_summary['parameter']}")
    print(f"  Status: {'PASS' if validation_summary['validation_result']['is_valid'] else 'FAIL'}")
    print(f"  Issues: {validation_summary['validation_result']['error_count']} errors, {validation_summary['validation_result']['warning_count']} warnings")
    
    if validation_summary["recommendations"]:
        print(f"  Recommendations:")
        for rec in validation_summary["recommendations"]:
            print(f"    - {rec}")

async def main():
    """Run all validation examples."""
    print("TR181 Node Comparator - Validation Examples")
    print("=" * 50)
    
    try:
        await demonstrate_data_type_validation()
        await demonstrate_range_validation()
        await demonstrate_path_validation()
        await demonstrate_custom_validation()
        await demonstrate_event_function_validation()
        await demonstrate_validation_reporting()
        
        print(f"\n" + "=" * 50)
        print("All validation examples completed successfully!")
        
    except Exception as e:
        print(f"❌ Validation examples failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())