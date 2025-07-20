"""Unit tests for configuration management system."""

import json
import yaml
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

from tr181_comparator.config import (
    DeviceConfig, HookConfig, SubsetConfig, ExportConfig, SystemConfig,
    ConfigurationManager, DEFAULT_HOOK_CONFIGS
)


class TestDeviceConfig:
    """Test DeviceConfig dataclass and validation."""
    
    def test_valid_device_config(self):
        """Test creating a valid device configuration."""
        config = DeviceConfig(
            type="rest",
            endpoint="http://192.168.1.1:8080",
            authentication={"username": "admin", "password": "secret"},
            timeout=60,
            retry_count=5,
            name="Test Device",
            description="Test device for unit tests"
        )
        
        assert config.type == "rest"
        assert config.endpoint == "http://192.168.1.1:8080"
        assert config.authentication == {"username": "admin", "password": "secret"}
        assert config.timeout == 60
        assert config.retry_count == 5
        assert config.name == "Test Device"
        assert config.description == "Test device for unit tests"
    
    def test_device_config_defaults(self):
        """Test device configuration with default values."""
        config = DeviceConfig(
            type="cwmp",
            endpoint="http://device.local",
            authentication={"token": "abc123"}
        )
        
        assert config.timeout == 30
        assert config.retry_count == 3
        assert config.name is None
        assert config.description is None
    
    def test_device_config_validation_empty_type(self):
        """Test validation fails for empty device type."""
        with pytest.raises(ValueError, match="Device type cannot be empty"):
            DeviceConfig(
                type="",
                endpoint="http://test.com",
                authentication={}
            )
    
    def test_device_config_validation_empty_endpoint(self):
        """Test validation fails for empty endpoint."""
        with pytest.raises(ValueError, match="Device endpoint cannot be empty"):
            DeviceConfig(
                type="rest",
                endpoint="",
                authentication={}
            )
    
    def test_device_config_validation_invalid_auth(self):
        """Test validation fails for invalid authentication."""
        with pytest.raises(ValueError, match="Authentication must be a dictionary"):
            DeviceConfig(
                type="rest",
                endpoint="http://test.com",
                authentication="invalid"
            )
    
    def test_device_config_validation_invalid_timeout(self):
        """Test validation fails for invalid timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            DeviceConfig(
                type="rest",
                endpoint="http://test.com",
                authentication={},
                timeout=0
            )
    
    def test_device_config_validation_invalid_retry_count(self):
        """Test validation fails for negative retry count."""
        with pytest.raises(ValueError, match="Retry count cannot be negative"):
            DeviceConfig(
                type="rest",
                endpoint="http://test.com",
                authentication={},
                retry_count=-1
            )


class TestHookConfig:
    """Test HookConfig dataclass and validation."""
    
    def test_valid_hook_config(self):
        """Test creating a valid hook configuration."""
        config = HookConfig(
            hook_type="rest",
            endpoint_template="http://{host}:{port}/api",
            default_headers={"Content-Type": "application/json"},
            timeout=45,
            retry_count=2,
            rest_config={"api_version": "v1"}
        )
        
        assert config.hook_type == "rest"
        assert config.endpoint_template == "http://{host}:{port}/api"
        assert config.default_headers == {"Content-Type": "application/json"}
        assert config.timeout == 45
        assert config.retry_count == 2
        assert config.rest_config == {"api_version": "v1"}
    
    def test_hook_config_defaults(self):
        """Test hook configuration with default values."""
        config = HookConfig(
            hook_type="cwmp",
            endpoint_template="http://{host}/cwmp",
            default_headers={}
        )
        
        assert config.timeout == 30
        assert config.retry_count == 3
        assert config.rest_config is None
        assert config.cwmp_config is None
        assert config.snmp_config is None
    
    def test_hook_config_validation_empty_type(self):
        """Test validation fails for empty hook type."""
        with pytest.raises(ValueError, match="Hook type cannot be empty"):
            HookConfig(
                hook_type="",
                endpoint_template="http://test.com",
                default_headers={}
            )
    
    def test_hook_config_validation_empty_template(self):
        """Test validation fails for empty endpoint template."""
        with pytest.raises(ValueError, match="Endpoint template cannot be empty"):
            HookConfig(
                hook_type="rest",
                endpoint_template="",
                default_headers={}
            )
    
    def test_hook_config_validation_invalid_headers(self):
        """Test validation fails for invalid headers."""
        with pytest.raises(ValueError, match="Default headers must be a dictionary"):
            HookConfig(
                hook_type="rest",
                endpoint_template="http://test.com",
                default_headers="invalid"
            )


class TestSubsetConfig:
    """Test SubsetConfig dataclass and validation."""
    
    def test_valid_subset_config(self):
        """Test creating a valid subset configuration."""
        created_date = datetime.now()
        modified_date = datetime.now()
        
        config = SubsetConfig(
            name="WiFi Subset",
            description="WiFi-related TR181 parameters",
            file_path="/path/to/wifi_subset.json",
            version="2.0",
            created_date=created_date,
            modified_date=modified_date
        )
        
        assert config.name == "WiFi Subset"
        assert config.description == "WiFi-related TR181 parameters"
        assert config.file_path == "/path/to/wifi_subset.json"
        assert config.version == "2.0"
        assert config.created_date == created_date
        assert config.modified_date == modified_date
    
    def test_subset_config_defaults(self):
        """Test subset configuration with default values."""
        config = SubsetConfig(
            name="Test Subset",
            description="Test description",
            file_path="/test/path"
        )
        
        assert config.version == "1.0"
        assert config.created_date is None
        assert config.modified_date is None
    
    def test_subset_config_validation_empty_name(self):
        """Test validation fails for empty name."""
        with pytest.raises(ValueError, match="Subset name cannot be empty"):
            SubsetConfig(
                name="",
                description="Test",
                file_path="/test"
            )
    
    def test_subset_config_validation_empty_file_path(self):
        """Test validation fails for empty file path."""
        with pytest.raises(ValueError, match="Subset file path cannot be empty"):
            SubsetConfig(
                name="Test",
                description="Test",
                file_path=""
            )
    
    def test_subset_config_validation_empty_version(self):
        """Test validation fails for empty version."""
        with pytest.raises(ValueError, match="Subset version cannot be empty"):
            SubsetConfig(
                name="Test",
                description="Test",
                file_path="/test",
                version=""
            )


class TestExportConfig:
    """Test ExportConfig dataclass and validation."""
    
    def test_valid_export_config(self):
        """Test creating a valid export configuration."""
        config = ExportConfig(
            default_format="xml",
            include_metadata=False,
            output_directory="/custom/reports",
            timestamp_format="%Y%m%d_%H%M%S",
            json_settings={"indent": 4},
            xml_settings={"encoding": "utf-8"},
            text_settings={"line_width": 120}
        )
        
        assert config.default_format == "xml"
        assert config.include_metadata is False
        assert config.output_directory == "/custom/reports"
        assert config.timestamp_format == "%Y%m%d_%H%M%S"
        assert config.json_settings == {"indent": 4}
        assert config.xml_settings == {"encoding": "utf-8"}
        assert config.text_settings == {"line_width": 120}
    
    def test_export_config_defaults(self):
        """Test export configuration with default values."""
        config = ExportConfig(default_format="json")
        
        assert config.include_metadata is True
        assert config.output_directory == "./reports"
        assert config.timestamp_format == "%Y-%m-%d_%H-%M-%S"
        assert config.json_settings is None
        assert config.xml_settings is None
        assert config.text_settings is None
    
    def test_export_config_validation_invalid_format(self):
        """Test validation fails for invalid format."""
        with pytest.raises(ValueError, match="Default format must be one of"):
            ExportConfig(default_format="invalid")
    
    def test_export_config_validation_empty_directory(self):
        """Test validation fails for empty output directory."""
        with pytest.raises(ValueError, match="Output directory cannot be empty"):
            ExportConfig(
                default_format="json",
                output_directory=""
            )
    
    def test_export_config_validation_empty_timestamp_format(self):
        """Test validation fails for empty timestamp format."""
        with pytest.raises(ValueError, match="Timestamp format cannot be empty"):
            ExportConfig(
                default_format="json",
                timestamp_format=""
            )


class TestSystemConfig:
    """Test SystemConfig dataclass and validation."""
    
    def test_valid_system_config(self):
        """Test creating a valid system configuration."""
        device = DeviceConfig(
            type="rest",
            endpoint="http://test.com",
            authentication={}
        )
        
        subset = SubsetConfig(
            name="Test Subset",
            description="Test",
            file_path="/test"
        )
        
        export_settings = ExportConfig(default_format="json")
        
        hook_configs = {"rest": DEFAULT_HOOK_CONFIGS["rest"]}
        
        config = SystemConfig(
            devices=[device],
            subsets=[subset],
            export_settings=export_settings,
            hook_configs=hook_configs,
            connection_defaults={"timeout": 30},
            logging_config={"level": "INFO"}
        )
        
        assert len(config.devices) == 1
        assert len(config.subsets) == 1
        assert config.export_settings == export_settings
        assert config.hook_configs == hook_configs
        assert config.connection_defaults == {"timeout": 30}
        assert config.logging_config == {"level": "INFO"}
    
    def test_system_config_validation_invalid_devices(self):
        """Test validation fails for invalid devices."""
        with pytest.raises(ValueError, match="Devices must be a list"):
            SystemConfig(
                devices="invalid",
                subsets=[],
                export_settings=ExportConfig(default_format="json"),
                hook_configs={},
                connection_defaults={}
            )
    
    def test_system_config_validation_invalid_export_settings(self):
        """Test validation fails for invalid export settings."""
        with pytest.raises(ValueError, match="Export settings must be an ExportConfig instance"):
            SystemConfig(
                devices=[],
                subsets=[],
                export_settings="invalid",
                hook_configs={},
                connection_defaults={}
            )


class TestDefaultHookConfigs:
    """Test default hook configurations."""
    
    def test_default_rest_hook_config(self):
        """Test default REST hook configuration."""
        config = DEFAULT_HOOK_CONFIGS["rest"]
        
        assert config.hook_type == "rest"
        assert config.endpoint_template == "http://{host}:{port}/api/tr181"
        assert config.default_headers == {"Content-Type": "application/json"}
        assert config.rest_config is not None
        assert "parameter_names_endpoint" in config.rest_config
    
    def test_default_cwmp_hook_config(self):
        """Test default CWMP hook configuration."""
        config = DEFAULT_HOOK_CONFIGS["cwmp"]
        
        assert config.hook_type == "cwmp"
        assert config.endpoint_template == "http://{host}:{port}/cwmp"
        assert config.default_headers == {"SOAPAction": ""}
        assert config.cwmp_config is not None
        assert "namespace" in config.cwmp_config


class TestConfigurationManager:
    """Test ConfigurationManager class."""
    
    def test_init_default_path(self):
        """Test initialization with default config path."""
        manager = ConfigurationManager()
        assert manager.config_path == Path("config.json")
        assert manager.get_config() is None
    
    def test_init_custom_path(self):
        """Test initialization with custom config path."""
        manager = ConfigurationManager("/custom/config.yaml")
        assert manager.config_path == Path("/custom/config.yaml")
    
    def test_create_default_config(self):
        """Test creating default configuration."""
        manager = ConfigurationManager()
        config = manager.create_default_config()
        
        assert isinstance(config, SystemConfig)
        assert config.devices == []
        assert config.subsets == []
        assert config.export_settings.default_format == "json"
        assert "rest" in config.hook_configs
        assert "cwmp" in config.hook_configs
    
    def test_load_config_file_not_found(self):
        """Test loading configuration when file doesn't exist."""
        manager = ConfigurationManager("/nonexistent/config.json")
        
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            manager.load_config()
    
    def test_load_config_json(self):
        """Test loading JSON configuration."""
        config_data = {
            "devices": [{
                "type": "rest",
                "endpoint": "http://test.com",
                "authentication": {"token": "test"}
            }],
            "subsets": [{
                "name": "Test Subset",
                "description": "Test",
                "file_path": "/test"
            }],
            "export_settings": {
                "default_format": "json"
            },
            "hook_configs": {
                "rest": {
                    "hook_type": "rest",
                    "endpoint_template": "http://{host}/api",
                    "default_headers": {}
                }
            },
            "connection_defaults": {"timeout": 30}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            manager = ConfigurationManager()
            config = manager.load_config(temp_path)
            
            assert isinstance(config, SystemConfig)
            assert len(config.devices) == 1
            assert config.devices[0].type == "rest"
            assert len(config.subsets) == 1
            assert config.subsets[0].name == "Test Subset"
        finally:
            Path(temp_path).unlink()
    
    def test_load_config_yaml(self):
        """Test loading YAML configuration."""
        config_data = {
            "devices": [{
                "type": "cwmp",
                "endpoint": "http://cwmp.test.com",
                "authentication": {"username": "admin", "password": "secret"}
            }],
            "subsets": [],
            "export_settings": {
                "default_format": "xml"
            },
            "hook_configs": {},
            "connection_defaults": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(config_data, f)
            temp_path = f.name
        
        try:
            manager = ConfigurationManager()
            config = manager.load_config(temp_path)
            
            assert isinstance(config, SystemConfig)
            assert len(config.devices) == 1
            assert config.devices[0].type == "cwmp"
            assert config.export_settings.default_format == "xml"
        finally:
            Path(temp_path).unlink()
    
    def test_load_config_invalid_json(self):
        """Test loading invalid JSON configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name
        
        try:
            manager = ConfigurationManager()
            with pytest.raises(ValueError, match="Invalid configuration file format"):
                manager.load_config(temp_path)
        finally:
            Path(temp_path).unlink()
    
    def test_save_config_json(self):
        """Test saving configuration to JSON file."""
        manager = ConfigurationManager()
        config = manager.create_default_config()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            manager.save_config(config, temp_path)
            
            # Verify file was created and contains valid JSON
            with open(temp_path, 'r') as f:
                loaded_data = json.load(f)
            
            assert "devices" in loaded_data
            assert "subsets" in loaded_data
            assert "export_settings" in loaded_data
        finally:
            Path(temp_path).unlink()
    
    def test_save_config_yaml(self):
        """Test saving configuration to YAML file."""
        manager = ConfigurationManager()
        config = manager.create_default_config()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            manager.save_config(config, temp_path)
            
            # Verify file was created and contains valid YAML
            with open(temp_path, 'r') as f:
                loaded_data = yaml.safe_load(f)
            
            assert "devices" in loaded_data
            assert "subsets" in loaded_data
            assert "export_settings" in loaded_data
        finally:
            Path(temp_path).unlink()
    
    def test_validate_config_valid(self):
        """Test validation of valid configuration."""
        manager = ConfigurationManager()
        config = manager.create_default_config()
        
        errors = manager.validate_config(config)
        assert errors == []
    
    def test_validate_config_invalid_device(self):
        """Test validation with invalid device configuration."""
        manager = ConfigurationManager()
        config = manager.create_default_config()
        
        # Create a device with valid initial values, then modify to invalid
        valid_device = DeviceConfig(
            type="rest",
            endpoint="http://test.com",
            authentication={}
        )
        # Manually set invalid timeout to bypass __post_init__ validation
        valid_device.timeout = -1
        config.devices.append(valid_device)
        
        errors = manager.validate_config(config)
        assert len(errors) > 0
        assert any("Timeout must be positive" in error for error in errors)
    
    def test_validate_config_missing_subset_file(self):
        """Test validation with missing subset file."""
        manager = ConfigurationManager()
        config = manager.create_default_config()
        
        # Add subset with non-existent file
        subset = SubsetConfig(
            name="Test Subset",
            description="Test",
            file_path="/nonexistent/file.json"
        )
        config.subsets.append(subset)
        
        errors = manager.validate_config(config)
        assert len(errors) > 0
        assert any("File not found" in error for error in errors)
    
    def test_dict_conversion_with_datetime(self):
        """Test dictionary conversion with datetime fields."""
        manager = ConfigurationManager()
        
        # Create config with datetime
        created_date = datetime.now()
        subset_data = {
            "name": "Test Subset",
            "description": "Test",
            "file_path": "/test",
            "created_date": created_date.isoformat()
        }
        
        config_data = {
            "devices": [],
            "subsets": [subset_data],
            "export_settings": {"default_format": "json"},
            "hook_configs": {},
            "connection_defaults": {}
        }
        
        config = manager._dict_to_config(config_data)
        assert isinstance(config.subsets[0].created_date, datetime)
        
        # Convert back to dict
        result_dict = manager._config_to_dict(config)
        assert "subsets" in result_dict