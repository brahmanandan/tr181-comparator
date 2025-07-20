"""Configuration management system for TR181 node comparator."""

import json
import yaml
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime


@dataclass
class DeviceConfig:
    """Configuration for device connections."""
    type: str  # 'rest', 'cwmp', 'snmp', etc.
    endpoint: str
    authentication: Dict[str, Any]
    timeout: int = 30
    retry_count: int = 3
    name: Optional[str] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        """Validate device configuration after initialization."""
        if not self.type:
            raise ValueError("Device type cannot be empty")
        if not self.endpoint:
            raise ValueError("Device endpoint cannot be empty")
        if not isinstance(self.authentication, dict):
            raise ValueError("Authentication must be a dictionary")
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if self.retry_count < 0:
            raise ValueError("Retry count cannot be negative")


@dataclass
class HookConfig:
    """Configuration for device communication hooks."""
    hook_type: str  # 'rest', 'cwmp', 'snmp', etc.
    endpoint_template: str  # URL template with placeholders
    default_headers: Dict[str, str]
    timeout: int = 30
    retry_count: int = 3
    
    # Protocol-specific configurations
    rest_config: Optional[Dict[str, Any]] = None
    cwmp_config: Optional[Dict[str, Any]] = None
    snmp_config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate hook configuration after initialization."""
        if not self.hook_type:
            raise ValueError("Hook type cannot be empty")
        if not self.endpoint_template:
            raise ValueError("Endpoint template cannot be empty")
        if not isinstance(self.default_headers, dict):
            raise ValueError("Default headers must be a dictionary")
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if self.retry_count < 0:
            raise ValueError("Retry count cannot be negative")


@dataclass
class SubsetConfig:
    """Configuration for TR181 subset definitions."""
    name: str
    description: str
    file_path: str
    version: str = "1.0"
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate subset configuration after initialization."""
        if not self.name:
            raise ValueError("Subset name cannot be empty")
        if not self.file_path:
            raise ValueError("Subset file path cannot be empty")
        if not self.version:
            raise ValueError("Subset version cannot be empty")


@dataclass
class ExportConfig:
    """Configuration for export and reporting functionality."""
    default_format: str  # 'json', 'xml', or 'text'
    include_metadata: bool = True
    output_directory: str = "./reports"
    timestamp_format: str = "%Y-%m-%d_%H-%M-%S"
    
    # Format-specific settings
    json_settings: Optional[Dict[str, Any]] = None
    xml_settings: Optional[Dict[str, Any]] = None
    text_settings: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate export configuration after initialization."""
        valid_formats = ['json', 'xml', 'text']
        if self.default_format not in valid_formats:
            raise ValueError(f"Default format must be one of: {valid_formats}")
        if not self.output_directory:
            raise ValueError("Output directory cannot be empty")
        if not self.timestamp_format:
            raise ValueError("Timestamp format cannot be empty")


@dataclass
class SystemConfig:
    """Main system configuration containing all subsystem configurations."""
    devices: List[DeviceConfig]
    subsets: List[SubsetConfig]
    export_settings: ExportConfig
    hook_configs: Dict[str, HookConfig]
    connection_defaults: Dict[str, Any]
    logging_config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate system configuration after initialization."""
        if not isinstance(self.devices, list):
            raise ValueError("Devices must be a list")
        if not isinstance(self.subsets, list):
            raise ValueError("Subsets must be a list")
        if not isinstance(self.export_settings, ExportConfig):
            raise ValueError("Export settings must be an ExportConfig instance")
        if not isinstance(self.hook_configs, dict):
            raise ValueError("Hook configs must be a dictionary")
        if not isinstance(self.connection_defaults, dict):
            raise ValueError("Connection defaults must be a dictionary")


# Default hook configurations
DEFAULT_HOOK_CONFIGS = {
    'rest': HookConfig(
        hook_type='rest',
        endpoint_template='http://{host}:{port}/api/tr181',
        default_headers={'Content-Type': 'application/json'},
        rest_config={
            'parameter_names_endpoint': '/parameters',
            'parameter_values_endpoint': '/values',
            'parameter_attributes_endpoint': '/attributes',
            'set_parameters_endpoint': '/set',
            'events_endpoint': '/events',
            'functions_endpoint': '/functions'
        }
    ),
    'cwmp': HookConfig(
        hook_type='cwmp',
        endpoint_template='http://{host}:{port}/cwmp',
        default_headers={'SOAPAction': ''},
        cwmp_config={
            'namespace': 'urn:dslforum-org:cwmp-1-0',
            'envelope_template': 'soap_envelope.xml',
            'rpc_methods': {
                'get_parameter_names': 'GetParameterNames',
                'get_parameter_values': 'GetParameterValues',
                'get_parameter_attributes': 'GetParameterAttributes',
                'set_parameter_values': 'SetParameterValues'
            }
        }
    )
}


class ConfigurationManager:
    """Manages loading, saving, and validation of system configurations."""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize configuration manager with optional config file path."""
        self.config_path = Path(config_path) if config_path else Path("config.json")
        self._config: Optional[SystemConfig] = None
    
    def load_config(self, config_path: Optional[Union[str, Path]] = None) -> SystemConfig:
        """Load configuration from file (JSON or YAML)."""
        if config_path:
            self.config_path = Path(config_path)
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            self._config = self._dict_to_config(data)
            return self._config
            
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise ValueError(f"Invalid configuration file format: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    def save_config(self, config: SystemConfig, config_path: Optional[Union[str, Path]] = None) -> None:
        """Save configuration to file (JSON or YAML)."""
        if config_path:
            self.config_path = Path(config_path)
        
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = self._config_to_dict(config)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.safe_dump(data, f, default_flow_style=False, indent=2)
                else:
                    json.dump(data, f, indent=2, default=str)
            
            self._config = config
            
        except Exception as e:
            raise RuntimeError(f"Failed to save configuration: {e}")
    
    def get_config(self) -> Optional[SystemConfig]:
        """Get current loaded configuration."""
        return self._config
    
    def create_default_config(self) -> SystemConfig:
        """Create a default system configuration."""
        return SystemConfig(
            devices=[],
            subsets=[],
            export_settings=ExportConfig(
                default_format='json',
                include_metadata=True,
                output_directory='./reports'
            ),
            hook_configs=DEFAULT_HOOK_CONFIGS.copy(),
            connection_defaults={
                'timeout': 30,
                'retry_count': 3,
                'verify_ssl': True
            }
        )
    
    def validate_config(self, config: SystemConfig) -> List[str]:
        """Validate configuration and return list of validation errors."""
        errors = []
        
        try:
            # Validate devices
            for i, device in enumerate(config.devices):
                try:
                    # Re-validate device config
                    DeviceConfig(**asdict(device))
                except Exception as e:
                    errors.append(f"Device {i}: {e}")
            
            # Validate subsets
            for i, subset in enumerate(config.subsets):
                try:
                    # Re-validate subset config
                    SubsetConfig(**asdict(subset))
                    # Check if file exists
                    if not Path(subset.file_path).exists():
                        errors.append(f"Subset {i}: File not found: {subset.file_path}")
                except Exception as e:
                    errors.append(f"Subset {i}: {e}")
            
            # Validate export settings
            try:
                ExportConfig(**asdict(config.export_settings))
            except Exception as e:
                errors.append(f"Export settings: {e}")
            
            # Validate hook configs
            for hook_name, hook_config in config.hook_configs.items():
                try:
                    HookConfig(**asdict(hook_config))
                except Exception as e:
                    errors.append(f"Hook config '{hook_name}': {e}")
        
        except Exception as e:
            errors.append(f"General validation error: {e}")
        
        return errors
    
    def _dict_to_config(self, data: Dict[str, Any]) -> SystemConfig:
        """Convert dictionary to SystemConfig object."""
        # Convert devices
        devices = []
        for device_data in data.get('devices', []):
            devices.append(DeviceConfig(**device_data))
        
        # Convert subsets
        subsets = []
        for subset_data in data.get('subsets', []):
            # Handle datetime fields
            if 'created_date' in subset_data and isinstance(subset_data['created_date'], str):
                subset_data['created_date'] = datetime.fromisoformat(subset_data['created_date'])
            if 'modified_date' in subset_data and isinstance(subset_data['modified_date'], str):
                subset_data['modified_date'] = datetime.fromisoformat(subset_data['modified_date'])
            subsets.append(SubsetConfig(**subset_data))
        
        # Convert export settings
        export_settings = ExportConfig(**data.get('export_settings', {}))
        
        # Convert hook configs
        hook_configs = {}
        for hook_name, hook_data in data.get('hook_configs', {}).items():
            hook_configs[hook_name] = HookConfig(**hook_data)
        
        return SystemConfig(
            devices=devices,
            subsets=subsets,
            export_settings=export_settings,
            hook_configs=hook_configs,
            connection_defaults=data.get('connection_defaults', {}),
            logging_config=data.get('logging_config')
        )
    
    def _config_to_dict(self, config: SystemConfig) -> Dict[str, Any]:
        """Convert SystemConfig object to dictionary."""
        return asdict(config)