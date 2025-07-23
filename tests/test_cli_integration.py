"""Integration tests for CLI functionality and user workflows."""

import asyncio
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from tr181_comparator.cli import TR181ComparatorCLI, CLIProgressReporter
from tr181_comparator.main import TR181ComparatorApp
from tr181_comparator.config import SystemConfig, DeviceConfig, OperatorRequirementConfig, ExportConfig
from tr181_comparator.models import (
    TR181Node, AccessLevel, ComparisonResult, ComparisonSummary, 
    NodeDifference, Severity
)
from tr181_comparator.comparison import EnhancedComparisonResult


class TestCLIProgressReporter:
    """Test CLI progress reporter functionality."""
    
    def test_progress_reporter_initialization(self):
        """Test progress reporter initialization."""
        reporter = CLIProgressReporter(verbose=True)
        assert reporter.verbose is True
        assert reporter.start_time is None
        assert reporter.current_step == 0
        assert reporter.total_steps == 0
    
    def test_start_operation(self, capsys):
        """Test starting an operation."""
        reporter = CLIProgressReporter(verbose=True)
        reporter.start_operation("Test Operation", 5)
        
        captured = capsys.readouterr()
        assert "Starting Test Operation..." in captured.out
        assert "Total steps: 5" in captured.out
        assert reporter.total_steps == 5
    
    def test_update_progress_with_steps(self, capsys):
        """Test updating progress with step numbers."""
        reporter = CLIProgressReporter(verbose=True)
        reporter.start_operation("Test Operation", 3)
        reporter.update_progress("Step 1", 1)
        
        captured = capsys.readouterr()
        assert "[33.3%] Step 1" in captured.out
    
    def test_update_progress_without_total(self, capsys):
        """Test updating progress without total steps."""
        reporter = CLIProgressReporter(verbose=True)
        reporter.start_operation("Test Operation")
        reporter.update_progress("Step 1")
        
        captured = capsys.readouterr()
        assert "[1] Step 1" in captured.out
    
    def test_complete_operation(self, capsys):
        """Test completing an operation."""
        reporter = CLIProgressReporter(verbose=True)
        reporter.start_operation("Test Operation")
        reporter.complete_operation("Test Operation", success=True)
        
        captured = capsys.readouterr()
        assert "Test Operation completed successfully" in captured.out
    
    def test_show_messages(self, capsys):
        """Test showing different types of messages."""
        reporter = CLIProgressReporter(verbose=True)
        
        reporter.show_error("Test error")
        reporter.show_warning("Test warning")
        reporter.show_info("Test info")
        
        captured = capsys.readouterr()
        assert "ERROR: Test error" in captured.err
        assert "WARNING: Test warning" in captured.out
        assert "INFO: Test info" in captured.out


class TestTR181ComparatorCLI:
    """Test CLI interface functionality."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return TR181ComparatorCLI()
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary configuration file."""
        config_data = {
            "devices": [],
            "operator_requirements": [],
            "export_settings": {
                "default_format": "json",
                "include_metadata": True,
                "output_directory": "./reports"
            },
            "hook_configs": {},
            "connection_defaults": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        yield temp_path
        Path(temp_path).unlink()
    
    @pytest.fixture
    def temp_operator_requirement_file(self):
        """Create temporary operator requirement file."""
        operator_requirement_data = {
            "version": "1.0",
            "metadata": {
                "created": "2025-01-01T00:00:00",
                "description": "Test operator requirement definition",
                "total_nodes": 1,
                "custom_nodes": 0
            },
            "nodes": [
                {
                    "path": "Device.WiFi.Radio.1.Channel",
                    "name": "Channel",
                    "data_type": "int",
                    "access": "read-write",
                    "value": 6,
                    "is_object": False,
                    "is_custom": False
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(operator_requirement_data, f)
            temp_path = f.name
        
        yield temp_path
        Path(temp_path).unlink()
    
    @pytest.fixture
    def temp_device_config(self):
        """Create temporary device configuration."""
        device_config = {
            "type": "rest",
            "endpoint": "http://192.168.1.1:8080",
            "authentication": {"type": "basic", "username": "admin", "password": "admin"},
            "timeout": 30,
            "retry_count": 3
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(device_config, f)
            temp_path = f.name
        
        yield temp_path
        Path(temp_path).unlink()
    
    def test_create_parser(self, cli):
        """Test argument parser creation."""
        parser = cli.create_parser()
        
        # Test that parser is created
        assert parser is not None
        
        # Test help doesn't raise exception
        with pytest.raises(SystemExit):
            parser.parse_args(['--help'])
    
    def test_parser_global_options(self, cli):
        """Test global command line options."""
        parser = cli.create_parser()
        
        # Test default values
        args = parser.parse_args(['list-configs'])
        assert args.config == 'config.json'
        assert args.verbose is False
        assert args.log_level == 'INFO'
        assert args.log_file is None
        
        # Test custom values
        args = parser.parse_args([
            '--config', 'custom.json',
            '--verbose',
            '--log-level', 'DEBUG',
            '--log-file', 'test.log',
            'list-configs'
        ])
        assert args.config == 'custom.json'
        assert args.verbose is True
        assert args.log_level == 'DEBUG'
        assert args.log_file == 'test.log'
    
    def test_parser_cwmp_vs_operator_requirement_command(self, cli):
        """Test CWMP vs operator requirement command parsing."""
        parser = cli.create_parser()
        
        args = parser.parse_args([
            'cwmp-vs-operator-requirement',
            '--cwmp-config', 'cwmp.json',
            '--operator-requirement-file', 'operator_requirement.json',
            '--output', 'result.json',
            '--format', 'xml',
            '--include-metadata'
        ])
        
        assert args.command == 'cwmp-vs-operator-requirement'
        assert args.cwmp_config == 'cwmp.json'
        assert args.operator_requirement_file == 'operator_requirement.json'
        assert args.output == 'result.json'
        assert args.format == 'xml'
        assert args.include_metadata is True
    
    def test_parser_operator_requirement_vs_device_command(self, cli):
        """Test operator requirement vs device command parsing."""
        parser = cli.create_parser()
        
        args = parser.parse_args([
            'operator-requirement-vs-device',
            '--operator-requirement-file', 'operator_requirement.json',
            '--device-config', 'device.json',
            '--output', 'result.json',
            '--include-validation'
        ])
        
        assert args.command == 'operator-requirement-vs-device'
        assert args.operator_requirement_file == 'operator_requirement.json'
        assert args.device_config == 'device.json'
        assert args.output == 'result.json'
        assert args.include_validation is True
    
    def test_parser_device_vs_device_command(self, cli):
        """Test device vs device command parsing."""
        parser = cli.create_parser()
        
        args = parser.parse_args([
            'device-vs-device',
            '--device1-config', 'device1.json',
            '--device2-config', 'device2.json',
            '--output', 'result.json'
        ])
        
        assert args.command == 'device-vs-device'
        assert args.device1_config == 'device1.json'
        assert args.device2_config == 'device2.json'
        assert args.output == 'result.json'
    
    def test_parser_extract_command(self, cli):
        """Test extract command parsing."""
        parser = cli.create_parser()
        
        args = parser.parse_args([
            'extract',
            '--source-type', 'device',
            '--source-config', 'device.json',
            '--output', 'nodes.json',
            '--format', 'xml'
        ])
        
        assert args.command == 'extract'
        assert args.source_type == 'device'
        assert args.source_config == 'device.json'
        assert args.output == 'nodes.json'
        assert args.format == 'xml'
    
    @pytest.mark.asyncio
    async def test_run_with_missing_config(self, cli):
        """Test running CLI with missing configuration file."""
        with patch.object(cli, 'config_manager') as mock_config_manager:
            mock_config_manager.load_config.side_effect = FileNotFoundError()
            mock_config_manager.create_default_config.return_value = Mock()
            
            with patch.object(cli, 'app') as mock_app:
                result = await cli.run(['--config', 'nonexistent.json', 'list-configs'])
                
                # Should use default config when file doesn't exist
                mock_config_manager.create_default_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_list_configs_command(self, cli, temp_config_file):
        """Test running list-configs command."""
        with patch.object(cli, 'config_manager') as mock_config_manager:
            mock_config = Mock()
            mock_config.devices = []
            mock_config.operator_requirements = []
            mock_config.hook_configs = {}
            mock_config_manager.get_config.return_value = mock_config
            mock_config_manager.load_config.return_value = mock_config
            
            result = await cli.run(['--config', temp_config_file, 'list-configs'])
            assert result == 0
    
    @pytest.mark.asyncio
    async def test_run_create_config_command(self, cli):
        """Test running create-config command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'new_config.json'
            
            with patch.object(cli, 'config_manager') as mock_config_manager:
                mock_config_manager.create_default_config.return_value = Mock()
                
                result = await cli.run(['create-config', '--output', str(output_path)])
                assert result == 0
                mock_config_manager.save_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_validate_operator_requirement_command(self, cli, temp_config_file, temp_operator_requirement_file):
        """Test running validate-operator-requirement command."""
        with patch.object(cli, 'app') as mock_app:
            mock_app.validate_operator_requirement_file = AsyncMock(return_value=(True, []))
            
            result = await cli.run([
                '--config', temp_config_file,
                'validate-operator-requirement',
                '--operator-requirement-file', temp_operator_requirement_file
            ])
            assert result == 0
    
    @pytest.mark.asyncio
    async def test_run_extract_command(self, cli, temp_config_file, temp_device_config):
        """Test running extract command."""
        mock_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6
            )
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'nodes.json'
            
            with patch.object(cli, 'app') as mock_app:
                mock_app.extract_nodes = AsyncMock(return_value=mock_nodes)
                
                result = await cli.run([
                    '--config', temp_config_file,
                    'extract',
                    '--source-type', 'device',
                    '--source-config', temp_device_config,
                    '--output', str(output_path)
                ])
                assert result == 0
                assert output_path.exists()
    
    @pytest.mark.asyncio
    async def test_run_operator_requirement_vs_device_command(self, cli, temp_config_file, 
                                              temp_operator_requirement_file, temp_device_config):
        """Test running operator-requirement-vs-device command."""
        mock_result = ComparisonResult(
            only_in_source1=[],
            only_in_source2=[],
            differences=[],
            summary=ComparisonSummary(
                total_nodes_source1=1,
                total_nodes_source2=1,
                common_nodes=1,
                differences_count=0
            )
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'result.json'
            
            with patch.object(cli, 'app') as mock_app:
                mock_app.compare_operator_requirement_vs_device = AsyncMock(return_value=mock_result)
                mock_app.export_result_as_json = AsyncMock()
                
                result = await cli.run([
                    '--config', temp_config_file,
                    'operator-requirement-vs-device',
                    '--operator-requirement-file', temp_operator_requirement_file,
                    '--device-config', temp_device_config,
                    '--output', str(output_path)
                ])
                assert result == 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, cli, temp_config_file):
        """Test CLI error handling."""
        with patch.object(cli, 'app') as mock_app:
            mock_app.validate_operator_requirement_file = AsyncMock(side_effect=Exception("Test error"))
            
            result = await cli.run([
                '--config', temp_config_file,
                'validate-operator-requirement',
                '--operator-requirement-file', 'nonexistent.json'
            ])
            assert result == 1
    
    def test_node_to_dict_conversion(self, cli):
        """Test TR181Node to dictionary conversion."""
        node = TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6,
            description="WiFi channel",
            is_object=False,
            is_custom=False
        )
        
        result = cli._node_to_dict(node)
        
        assert result['path'] == "Device.WiFi.Radio.1.Channel"
        assert result['name'] == "Channel"
        assert result['data_type'] == "int"
        assert result['access'] == "read-write"
        assert result['value'] == 6
        assert result['description'] == "WiFi channel"
        assert result['is_object'] is False
        assert result['is_custom'] is False
    
    def test_nodes_to_xml_conversion(self, cli):
        """Test nodes to XML conversion."""
        nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6
            )
        ]
        
        xml_content = cli._nodes_to_xml(nodes)
        
        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml_content
        assert '<tr181_nodes>' in xml_content
        assert 'path="Device.WiFi.Radio.1.Channel"' in xml_content
        assert '<name>Channel</name>' in xml_content
        assert '<data_type>int</data_type>' in xml_content
        assert '<access>read-write</access>' in xml_content
        assert '<value>6</value>' in xml_content
        assert '</tr181_nodes>' in xml_content


class TestCLIIntegrationWorkflows:
    """Test complete CLI workflows end-to-end."""
    
    @pytest.fixture
    def setup_test_environment(self):
        """Setup test environment with temporary files."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        # Create config file
        config_data = {
            "devices": [
                {
                    "type": "rest",
                    "endpoint": "http://192.168.1.1:8080",
                    "authentication": {"type": "basic", "username": "admin", "password": "admin"},
                    "timeout": 30,
                    "retry_count": 3,
                    "name": "Test Device"
                }
            ],
            "operator_requirements": [
                {
                    "name": "Test Operator Requirement",
                    "description": "Test operator requirement for CLI testing",
                    "file_path": str(temp_path / "operator_requirement.json"),
                    "version": "1.0"
                }
            ],
            "export_settings": {
                "default_format": "json",
                "include_metadata": True,
                "output_directory": str(temp_path / "reports")
            },
            "hook_configs": {},
            "connection_defaults": {}
        }
        
        config_file = temp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Create operator requirement file
        operator_requirement_data = {
            "version": "1.0",
            "metadata": {
                "created": "2025-01-01T00:00:00",
                "description": "Test operator requirement definition",
                "total_nodes": 1,
                "custom_nodes": 0
            },
            "nodes": [
                {
                    "path": "Device.WiFi.Radio.1.Channel",
                    "name": "Channel",
                    "data_type": "int",
                    "access": "read-write",
                    "value": 6,
                    "is_object": False,
                    "is_custom": False
                }
            ]
        }
        
        operator_requirement_file = temp_path / "operator_requirement.json"
        with open(operator_requirement_file, 'w') as f:
            json.dump(operator_requirement_data, f)
        
        # Create device config file
        device_config = {
            "type": "rest",
            "endpoint": "http://192.168.1.1:8080",
            "authentication": {"type": "basic", "username": "admin", "password": "admin"},
            "timeout": 30,
            "retry_count": 3
        }
        
        device_config_file = temp_path / "device.json"
        with open(device_config_file, 'w') as f:
            json.dump(device_config, f)
        
        yield {
            'temp_dir': temp_path,
            'config_file': config_file,
            'operator_requirement_file': operator_requirement_file,
            'device_config_file': device_config_file
        }
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_complete_operator_requirement_vs_device_workflow(self, setup_test_environment):
        """Test complete operator requirement vs device comparison workflow."""
        env = setup_test_environment
        cli = TR181ComparatorCLI()
        
        # Mock the comparison result
        mock_result = EnhancedComparisonResult(
            basic_comparison=ComparisonResult(
                only_in_source1=[],
                only_in_source2=[],
                differences=[],
                summary=ComparisonSummary(
                    total_nodes_source1=1,
                    total_nodes_source2=1,
                    common_nodes=1,
                    differences_count=0
                )
            ),
            validation_results=[],
            event_test_results=[],
            function_test_results=[]
        )
        
        output_file = env['temp_dir'] / 'comparison_result.json'
        
        with patch('tr181_comparator.cli.TR181ComparatorApp') as mock_app_class:
            mock_app = AsyncMock()
            mock_app.compare_operator_requirement_vs_device = AsyncMock(return_value=mock_result)
            mock_app.export_result_as_json = AsyncMock()
            mock_app_class.return_value = mock_app
            
            result = await cli.run([
                '--config', str(env['config_file']),
                '--verbose',
                'operator-requirement-vs-device',
                '--operator-requirement-file', str(env['operator_requirement_file']),
                '--device-config', str(env['device_config_file']),
                '--output', str(output_file),
                '--include-validation'
            ])
            
            assert result == 0
            mock_app.compare_operator_requirement_vs_device.assert_called_once()
            mock_app.export_result_as_json.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_configuration_management_workflow(self, setup_test_environment):
        """Test configuration management workflow."""
        env = setup_test_environment
        cli = TR181ComparatorCLI()
        
        # Test list-configs command
        result = await cli.run([
            '--config', str(env['config_file']),
            'list-configs'
        ])
        assert result == 0
        
        # Test create-config command
        new_config_file = env['temp_dir'] / 'new_config.json'
        result = await cli.run([
            'create-config',
            '--output', str(new_config_file)
        ])
        assert result == 0
        assert new_config_file.exists()
    
    @pytest.mark.asyncio
    async def test_extraction_workflow(self, setup_test_environment):
        """Test node extraction workflow."""
        env = setup_test_environment
        cli = TR181ComparatorCLI()
        
        mock_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Channel",
                name="Channel",
                data_type="int",
                access=AccessLevel.READ_WRITE,
                value=6
            )
        ]
        
        output_file = env['temp_dir'] / 'extracted_nodes.json'
        
        with patch('tr181_comparator.cli.TR181ComparatorApp') as mock_app_class:
            mock_app = AsyncMock()
            mock_app.extract_nodes = AsyncMock(return_value=mock_nodes)
            mock_app_class.return_value = mock_app
            
            result = await cli.run([
                '--config', str(env['config_file']),
                'extract',
                '--source-type', 'operator-requirement',
                '--source-config', str(env['operator_requirement_file']),
                '--output', str(output_file)
            ])
            
            assert result == 0
            mock_app.extract_nodes.assert_called_once_with(
                source_type='operator-requirement', 
                source_config_path=str(env['operator_requirement_file'])
            )
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, setup_test_environment):
        """Test error handling and recovery in workflows."""
        env = setup_test_environment
        cli = TR181ComparatorCLI()
        
        # Test with invalid operator requirement file
        result = await cli.run([
            '--config', str(env['config_file']),
            'validate-operator-requirement',
            '--operator-requirement-file', 'nonexistent.json'
        ])
        assert result == 1
        
        # Test with invalid device config
        with patch('tr181_comparator.cli.TR181ComparatorApp') as mock_app_class:
            mock_app = AsyncMock()
            mock_app.compare_operator_requirement_vs_device = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            mock_app_class.return_value = mock_app
            
            result = await cli.run([
                '--config', str(env['config_file']),
                'operator-requirement-vs-device',
                '--operator-requirement-file', str(env['operator_requirement_file']),
                '--device-config', str(env['device_config_file']),
                '--output', str(env['temp_dir'] / 'result.json')
            ])
            assert result == 1


if __name__ == '__main__':
    pytest.main([__file__])