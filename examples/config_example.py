#!/usr/bin/env python3
"""
TR181 Node Comparator Configuration Examples

This file demonstrates various configuration patterns for different
device types and communication protocols.
"""

import json
import yaml
from dataclasses import asdict
from tr181_comparator.config import (
    SystemConfig, DeviceConfig, OperatorRequirementConfig, ExportConfig, HookConfig
)

def create_basic_config():
    """Create a basic configuration with common settings."""
    
    # Device configurations
    devices = [
        DeviceConfig(
            name="main_gateway",
            type="cwmp",
            endpoint="http://192.168.1.1:7547/cwmp",
            authentication={
                "type": "basic",
                "username": "admin",
                "password": "admin123"
            },
            timeout=30,
            retry_count=3
        ),
        DeviceConfig(
            name="wifi_access_point",
            type="rest",
            endpoint="http://192.168.1.10/api/tr181",
            authentication={
                "type": "bearer",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            },
            timeout=20,
            retry_count=2,
            hook_config=HookConfig(
                api_version="v2",
                custom_headers={
                    "X-Device-Type": "WiFi-AP",
                    "Accept": "application/json"
                }
            )
        )
    ]
    
    # Operator requirement configurations
    operator_requirements = [
        OperatorRequirementConfig(
            name="wifi_parameters",
            file_path="operator_requirements/wifi.json",
            description="WiFi-related TR181 parameters"
        ),
        OperatorRequirementConfig(
            name="device_info",
            file_path="operator_requirements/device_info.yaml",
            description="Basic device information"
        )
    ]
    
    # Export configuration
    export_config = ExportConfig(
        default_format="json",
        include_metadata=True,
        output_directory="reports",
        timestamp_format="ISO8601"
    )
    
    # System configuration
    config = SystemConfig(
        devices=devices,
        operator_requirements=operator_requirements,
        export_settings=export_config,
        hook_configs={},
        connection_defaults={}
    )
    
    return config

def create_cwmp_configurations():
    """Create various CWMP device configurations."""
    
    configs = []
    
    # Basic CWMP with username/password
    configs.append(DeviceConfig(
        name="basic_cwmp_device",
        type="cwmp",
        endpoint="http://192.168.1.1:7547/cwmp",
        authentication={
            "type": "basic",
            "username": "admin",
            "password": "password123"
        },
        timeout=30,
        retry_count=3
    ))
    
    # CWMP with digest authentication
    configs.append(DeviceConfig(
        name="digest_cwmp_device",
        type="cwmp",
        endpoint="http://192.168.1.2:7547/cwmp",
        authentication={
            "type": "digest",
            "username": "admin",
            "password": "secure_password",
            "realm": "CWMP"
        },
        timeout=45,
        retry_count=2
    ))
    
    # CWMP with SSL/TLS
    configs.append(DeviceConfig(
        name="secure_cwmp_device",
        type="cwmp",
        endpoint="https://192.168.1.3:7548/cwmp",
        authentication={
            "type": "basic",
            "username": "admin",
            "password": "admin123"
        },
        timeout=60,
        retry_count=3,
        hook_config=HookConfig(
            ssl_verify=True,
            ssl_cert_path="/path/to/client.crt",
            ssl_key_path="/path/to/client.key",
            ssl_ca_path="/path/to/ca.crt"
        )
    ))
    
    # CWMP with custom connection parameters
    configs.append(DeviceConfig(
        name="custom_cwmp_device",
        type="cwmp",
        endpoint="http://device.example.com:8080/tr069",
        authentication={
            "type": "basic",
            "username": "device_admin",
            "password": "complex_password_123"
        },
        timeout=120,
        retry_count=5,
        hook_config=HookConfig(
            connection_id="TR069_SESSION_001",
            max_envelope_size=65536,
            soap_version="1.1",
            custom_headers={
                "X-Custom-Auth": "device-specific-token",
                "User-Agent": "TR181-Comparator/1.0"
            }
        )
    ))
    
    return configs

def create_rest_api_configurations():
    """Create various REST API device configurations."""
    
    configs = []
    
    # Basic REST API with API key
    configs.append(DeviceConfig(
        name="api_key_device",
        type="rest",
        endpoint="http://192.168.1.10/api/v1/tr181",
        authentication={
            "type": "api_key",
            "key": "your-api-key-here",
            "header": "X-API-Key"
        },
        timeout=30,
        retry_count=3
    ))
    
    # REST API with Bearer token
    configs.append(DeviceConfig(
        name="bearer_token_device",
        type="rest",
        endpoint="https://device.example.com/api/tr181",
        authentication={
            "type": "bearer",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        },
        timeout=25,
        retry_count=2,
        hook_config=HookConfig(
            api_version="v2",
            custom_headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
    ))
    
    # REST API with OAuth2
    configs.append(DeviceConfig(
        name="oauth2_device",
        type="rest",
        endpoint="https://secure-device.example.com/api/tr181",
        authentication={
            "type": "oauth2",
            "client_id": "your-client-id",
            "client_secret": "your-client-secret",
            "token_url": "https://auth.example.com/oauth/token",
            "scope": "tr181:read tr181:write"
        },
        timeout=40,
        retry_count=3,
        hook_config=HookConfig(
            oauth_refresh_threshold=300,  # Refresh token 5 minutes before expiry
            custom_headers={
                "X-Device-Model": "TR181-Device-v2.1"
            }
        )
    ))
    
    # REST API with custom authentication
    configs.append(DeviceConfig(
        name="custom_auth_device",
        type="rest",
        endpoint="http://192.168.1.20/device-api/tr181",
        authentication={
            "type": "custom",
            "method": "signature",
            "access_key": "AKIAIOSFODNN7EXAMPLE",
            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "signature_version": "v4"
        },
        timeout=35,
        retry_count=2,
        hook_config=HookConfig(
            signature_method="HMAC-SHA256",
            timestamp_header="X-Timestamp",
            signature_header="X-Signature"
        )
    ))
    
    return configs

def create_snmp_configurations():
    """Create SNMP device configurations (custom hook example)."""
    
    configs = []
    
    # SNMPv2c configuration
    configs.append(DeviceConfig(
        name="snmpv2_device",
        type="snmp",
        endpoint="192.168.1.30",
        authentication={
            "type": "community",
            "community": "public",
            "version": "2c"
        },
        timeout=20,
        retry_count=3,
        hook_config=HookConfig(
            port=161,
            mib_modules=["TR181-MIB", "DEVICE-MIB"],
            walk_timeout=30
        )
    ))
    
    # SNMPv3 with authentication
    configs.append(DeviceConfig(
        name="snmpv3_device",
        type="snmp",
        endpoint="192.168.1.31",
        authentication={
            "type": "usm",
            "version": "3",
            "username": "snmp_user",
            "auth_protocol": "SHA",
            "auth_password": "auth_password_123",
            "priv_protocol": "AES",
            "priv_password": "priv_password_456"
        },
        timeout=25,
        retry_count=2,
        hook_config=HookConfig(
            port=161,
            security_level="authPriv",
            context_name="device_context"
        )
    ))
    
    return configs

def create_production_config():
    """Create a production-ready configuration with multiple devices."""
    
    devices = []
    
    # Production gateway (CWMP)
    devices.append(DeviceConfig(
        name="prod_gateway",
        type="cwmp",
        endpoint="https://gateway.prod.example.com:7548/cwmp",
        authentication={
            "type": "digest",
            "username": "prod_admin",
            "password": "${GATEWAY_PASSWORD}",  # Environment variable
            "realm": "Production"
        },
        timeout=60,
        retry_count=3,
        hook_config=HookConfig(
            ssl_verify=True,
            ssl_cert_path="/etc/ssl/certs/gateway.crt",
            ssl_key_path="/etc/ssl/private/gateway.key",
            connection_pool_size=5
        )
    ))
    
    # WiFi controllers (REST API)
    for i in range(1, 4):
        devices.append(DeviceConfig(
            name=f"wifi_controller_{i}",
            type="rest",
            endpoint=f"https://wifi-{i}.prod.example.com/api/v2/tr181",
            authentication={
                "type": "oauth2",
                "client_id": "${WIFI_CLIENT_ID}",
                "client_secret": "${WIFI_CLIENT_SECRET}",
                "token_url": "https://auth.prod.example.com/oauth/token",
                "scope": "device:read device:monitor"
            },
            timeout=30,
            retry_count=2,
            hook_config=HookConfig(
                api_version="v2",
                rate_limit=100,  # requests per minute
                custom_headers={
                    "X-Environment": "production",
                    "X-Service": "tr181-comparator"
                }
            )
        ))
    
    # Monitoring devices (SNMP)
    devices.extend([
        DeviceConfig(
            name="network_monitor_1",
            type="snmp",
            endpoint="monitor1.prod.example.com",
            authentication={
                "type": "usm",
                "version": "3",
                "username": "monitor_user",
                "auth_protocol": "SHA256",
                "auth_password": "${SNMP_AUTH_PASSWORD}",
                "priv_protocol": "AES256",
                "priv_password": "${SNMP_PRIV_PASSWORD}"
            },
            timeout=45,
            retry_count=3,
            hook_config=HookConfig(
                port=161,
                security_level="authPriv",
                bulk_operations=True
            )
        )
    ])
    
    # Production operator requirements
    operator_requirements = [
        OperatorRequirementConfig(
            name="core_parameters",
            file_path="/etc/tr181-comparator/operator_requirements/core.json",
            description="Core TR181 parameters for all devices"
        ),
        OperatorRequirementConfig(
            name="wifi_parameters",
            file_path="/etc/tr181-comparator/operator_requirements/wifi.json",
            description="WiFi-specific parameters"
        ),
        OperatorRequirementConfig(
            name="monitoring_parameters",
            file_path="/etc/tr181-comparator/operator_requirements/monitoring.json",
            description="Parameters for network monitoring"
        )
    ]
    
    # Production export settings
    export_config = ExportConfig(
        default_format="json",
        include_metadata=True,
        output_directory="/var/log/tr181-comparator/reports",
        timestamp_format="ISO8601",
        compression=True,
        retention_days=90
    )
    
    config = SystemConfig(
        devices=devices,
        operator_requirements=operator_requirements,
        export_settings=export_config,
        hook_configs={},
        connection_defaults={
            "max_concurrent_connections": 10,
            "connection_timeout": 60,
            "retry_attempts": 3,
            "batch_size": 500,
            "memory_limit": "1GB"
        }
    )
    
    return config

def save_configurations():
    """Save example configurations to files."""
    
    # Basic configuration
    basic_config = create_basic_config()
    with open('examples/basic_config.json', 'w') as f:
        json.dump(asdict(basic_config), f, indent=2)
    
    # CWMP configurations
    cwmp_configs = create_cwmp_configurations()
    cwmp_examples = {"cwmp_devices": [asdict(config) for config in cwmp_configs]}
    with open('examples/cwmp_config.json', 'w') as f:
        json.dump(cwmp_examples, f, indent=2)
    
    # REST API configurations
    rest_configs = create_rest_api_configurations()
    rest_examples = {"rest_devices": [asdict(config) for config in rest_configs]}
    with open('examples/rest_config.json', 'w') as f:
        json.dump(rest_examples, f, indent=2)
    
    # SNMP configurations
    snmp_configs = create_snmp_configurations()
    snmp_examples = {"snmp_devices": [asdict(config) for config in snmp_configs]}
    with open('examples/snmp_config.json', 'w') as f:
        json.dump(snmp_examples, f, indent=2)
    
    # Production configuration
    prod_config = create_production_config()
    with open('examples/production_config.json', 'w') as f:
        json.dump(asdict(prod_config), f, indent=2)
    
    # YAML format example
    with open('examples/basic_config.yaml', 'w') as f:
        yaml.dump(asdict(basic_config), f, default_flow_style=False, indent=2)

def demonstrate_config_loading():
    """Demonstrate how to load and use configurations."""
    
    print("Configuration Loading Examples")
    print("=" * 40)
    
    # Load from JSON
    try:
        with open('examples/basic_config.json', 'r') as f:
            config_data = json.load(f)
        config = SystemConfig(**config_data)
        print(f"✓ Loaded configuration with {len(config.devices)} devices")
    except Exception as e:
        print(f"✗ Failed to load JSON config: {e}")
    
    # Load from YAML
    try:
        with open('examples/basic_config.yaml', 'r') as f:
            config_data = yaml.safe_load(f)
        config = SystemConfig(**config_data)
        print(f"✓ Loaded YAML configuration with {len(config.devices)} devices")
    except Exception as e:
        print(f"✗ Failed to load YAML config: {e}")
    
    # Environment variable substitution example
    import os
    os.environ['GATEWAY_PASSWORD'] = 'test_password_123'
    
    def substitute_env_vars(config_dict):
        """Simple environment variable substitution."""
        if isinstance(config_dict, dict):
            return {k: substitute_env_vars(v) for k, v in config_dict.items()}
        elif isinstance(config_dict, list):
            return [substitute_env_vars(item) for item in config_dict]
        elif isinstance(config_dict, str) and config_dict.startswith('${') and config_dict.endswith('}'):
            env_var = config_dict[2:-1]
            return os.environ.get(env_var, config_dict)
        else:
            return config_dict
    
    # Example with environment variable substitution
    config_with_env = {
        "devices": [{
            "name": "test_device",
            "type": "cwmp",
            "endpoint": "http://device.local/cwmp",
            "authentication": {
                "username": "admin",
                "password": "${GATEWAY_PASSWORD}"
            }
        }]
    }
    
    resolved_config = substitute_env_vars(config_with_env)
    print(f"✓ Environment variable substitution: {resolved_config['devices'][0]['authentication']['password']}")

if __name__ == "__main__":
    print("TR181 Node Comparator Configuration Examples")
    print("=" * 50)
    
    # Create and save example configurations
    save_configurations()
    print("✓ Example configuration files created")
    
    # Demonstrate configuration loading
    demonstrate_config_loading()
    
    print("\nConfiguration files created:")
    print("- examples/basic_config.json")
    print("- examples/basic_config.yaml")
    print("- examples/cwmp_config.json")
    print("- examples/rest_config.json")
    print("- examples/snmp_config.json")
    print("- examples/production_config.json")