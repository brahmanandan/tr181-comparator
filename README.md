# TR-181 Node Comparator

A comprehensive tool for comparing TR-181 data model implementations across different sources including CWMP devices, operator requirement definitions, and device implementations.

## Overview

The TR-181 Node Comparator is designed to help network administrators, device manufacturers, and system integrators validate and compare TR-181 data model implementations. It supports multiple comparison scenarios and provides detailed analysis with validation, event testing, and function testing capabilities.

## Features

- **Multi-Source Comparison**: Compare TR-181 implementations between:
  - CWMP devices vs operator requirement definitions
  - Operator requirement definitions vs device implementations  
  - Device vs device implementations
- **Enhanced Validation**: Built-in TR-181 specification validation
- **Event & Function Testing**: Test TR-181 events and functions
- **Multiple Export Formats**: JSON, XML, and human-readable text reports
- **Flexible Configuration**: YAML-based configuration system
- **Comprehensive Logging**: Structured logging with performance monitoring
- **Error Handling**: Robust error handling with graceful degradation
- **CLI Interface**: Easy-to-use command-line interface

## Installation

### From Source

```bash
git clone https://github.com/yourusername/tr181-comparator.git
cd tr181-comparator
pip install -e .
```

### Using pip

```bash
pip install tr181-node-comparator
```

## Quick Start

### Basic Usage

```bash
# Compare CWMP device against operator requirement definition
tr181-compare cwmp-vs-operator-requirement --cwmp-config device1.json --operator-requirement-file operator-requirement.yaml

# Compare operator requirement against device implementation
tr181-compare operator-requirement-vs-device --operator-requirement-file operator-requirement.yaml --device-config device2.json

# Compare two devices
tr181-compare device-vs-device --device1-config device1.json --device2-config device2.json
```

### With Enhanced Validation

```bash
# Include validation and testing
tr181-compare operator-requirement-vs-device --operator-requirement-file operator-requirement.yaml --device-config device.json --validate --test-events --test-functions
```

## Configuration

### Device Configuration Example

```json
{
  "type": "rest_api",
  "endpoint": "https://device.example.com/api",
  "authentication": {
    "type": "basic",
    "username": "admin",
    "password": "password"
  },
  "timeout": 30,
  "retry_count": 3
}
```

### CWMP Configuration Example

```json
{
  "endpoint": "http://acs.example.com:7547",
  "authentication": {
    "type": "digest",
    "username": "cwmp_user",
    "password": "cwmp_pass"
  },
  "connection_request": {
    "url": "http://device.example.com:7547",
    "username": "cr_user",
    "password": "cr_pass"
  }
}
```

### Operator Requirement Definition Example

```yaml
nodes:
  - path: "Device.DeviceInfo."
    required: true
    validation:
      - type: "presence"
  - path: "Device.WiFi.Radio.{i}."
    required: true
    validation:
      - type: "instance_count"
        min: 1
        max: 4
```

## API Usage

```python
from tr181_comparator import TR181ComparatorApp
from tr181_comparator.config import SystemConfig

# Initialize the application
config = SystemConfig.load_from_file("config.yaml")
app = TR181ComparatorApp(config)

# Perform comparison
result = await app.compare_operator_requirement_vs_device(
    "operator-requirement.yaml", 
    "device.json", 
    include_validation=True
)

# Export results
await app.export_result_as_json(result, Path("report.json"))
```

## Command Line Interface

### Available Commands

- `cwmp-vs-operator-requirement`: Compare CWMP device against operator requirement definition
- `operator-requirement-vs-device`: Compare operator requirement definition against device implementation
- `device-vs-device`: Compare two device implementations
- `extract-nodes`: Extract TR-181 nodes from a source
- `validate-operator-requirement`: Validate an operator requirement definition file

### Global Options

- `--config`: Path to system configuration file
- `--verbose`: Enable verbose output
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--output-format`: Export format (json, xml, text)
- `--output-file`: Output file path

## Examples

### Example 1: Basic Device Comparison

```bash
tr181-compare device-vs-device \
  --device1-config router1.json \
  --device2-config router2.json \
  --output-format json \
  --output-file comparison_report.json
```

### Example 2: Comprehensive Validation

```bash
tr181-compare operator-requirement-vs-device \
  --operator-requirement-file broadband_operator_requirement.yaml \
  --device-config cpe_device.json \
  --validate \
  --test-events \
  --test-functions \
  --verbose \
  --output-file validation_report.json
```

### Example 3: Node Extraction

```bash
tr181-compare extract-nodes \
  --source-type device \
  --source-config device.json \
  --output-file extracted_nodes.json
```

## Project Structure

```
tr181_comparator/
├── __init__.py          # Package initialization
├── cli.py              # Command-line interface
├── main.py             # Main application class
├── config.py           # Configuration management
├── models.py           # Data models
├── comparison.py       # Comparison engines
├── extractors.py       # Node extractors
├── hooks.py            # Device connection hooks
├── validation.py       # TR-181 validation
├── errors.py           # Error handling
└── logging.py          # Logging and monitoring
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tr181_comparator

# Run specific test category
pytest tests/test_comparison.py
```

### Code Quality

```bash
# Format code
black tr181_comparator/

# Lint code
flake8 tr181_comparator/

# Type checking
mypy tr181_comparator/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Documentation

- [User Guide](docs/user_guide.md)
- [Developer Guide](docs/developer_guide.md)
- [API Reference](docs/api_reference.md)
- [Troubleshooting Guide](docs/troubleshooting_guide.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Create an issue on GitHub for bug reports or feature requests
- Check the [troubleshooting guide](docs/troubleshooting_guide.md) for common issues
- Review the [API documentation](docs/api_reference.md) for detailed usage information

## Changelog

### v0.1.0 (Current)
- Initial release
- Basic comparison functionality
- CWMP, device, and operator requirement support
- Enhanced validation and testing
- Multiple export formats
- Comprehensive error handling and logging