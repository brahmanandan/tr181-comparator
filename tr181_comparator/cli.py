"""Command-line interface for TR181 node comparator."""

import argparse
import asyncio
import json
import logging
import sys
import warnings
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from .config import ConfigurationManager, SystemConfig, DeviceConfig, OperatorRequirementConfig
from .main import TR181ComparatorApp
from .models import TR181Node
from .errors import TR181Error, report_error
from .logging import (
    initialize_logging, LogLevel, get_logger, LogCategory,
    get_performance_summary
)
from .deprecation import deprecated, deprecated_argument, DEPRECATED_CLI_COMMANDS, DEPRECATED_CLI_ARGUMENTS


class CLIProgressReporter:
    """Progress reporter for CLI operations."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.start_time = None
        self.current_step = 0
        self.total_steps = 0
    
    def start_operation(self, operation_name: str, total_steps: int = 0):
        """Start a new operation with progress tracking."""
        self.start_time = datetime.now()
        self.current_step = 0
        self.total_steps = total_steps
        print(f"Starting {operation_name}...")
        if self.verbose and total_steps > 0:
            print(f"Total steps: {total_steps}")
    
    def update_progress(self, step_name: str, step_number: Optional[int] = None):
        """Update progress with current step information."""
        if step_number is not None:
            self.current_step = step_number
        else:
            self.current_step += 1
        
        if self.total_steps > 0:
            percentage = (self.current_step / self.total_steps) * 100
            print(f"[{percentage:.1f}%] {step_name}")
        else:
            print(f"[{self.current_step}] {step_name}")
    
    def complete_operation(self, operation_name: str, success: bool = True):
        """Complete the operation and show final status."""
        if self.start_time:
            duration = datetime.now() - self.start_time
            status = "completed successfully" if success else "failed"
            print(f"{operation_name} {status} in {duration.total_seconds():.2f} seconds")
        else:
            status = "completed" if success else "failed"
            print(f"{operation_name} {status}")
    
    def show_error(self, error_message: str):
        """Show error message."""
        print(f"ERROR: {error_message}", file=sys.stderr)
    
    def show_warning(self, warning_message: str):
        """Show warning message."""
        print(f"WARNING: {warning_message}")
    
    def show_info(self, info_message: str):
        """Show informational message."""
        if self.verbose:
            print(f"INFO: {info_message}")


class TR181ComparatorCLI:
    """Main CLI interface for TR181 node comparator."""
    
    def __init__(self):
        self.config_manager = ConfigurationManager()
        self.app = None
        self.progress_reporter = None
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create and configure the argument parser."""
        parser = argparse.ArgumentParser(
            description="TR181 Node Comparator - Compare TR181 data model implementations against operator requirement definitions",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Compare CWMP source against operator requirement definitions
  tr181-compare cwmp-vs-operator-requirement --cwmp-config cwmp.json --operator-requirement-file requirement.json --output report.json
  
  # Compare operator requirement definitions against device implementation
  tr181-compare operator-requirement-vs-device --operator-requirement-file requirement.json --device-config device.json --output report.json
  
  # Compare two device implementations
  tr181-compare device-vs-device --device1-config dev1.json --device2-config dev2.json --output report.json
  
  # List available configurations
  tr181-compare list-configs
  
  # Validate an operator requirement definition file
  tr181-compare validate-operator-requirement --operator-requirement-file requirement.json
  
  # Extract TR181 nodes from operator requirement definitions
  tr181-compare extract --source-type operator-requirement --source-config requirement.json --output nodes.json
  
  # Deprecated commands (still supported with warnings):
  tr181-compare subset-vs-device --operator-requirement-file requirement.json --device-config device.json --output report.json
  tr181-compare validate-subset --operator-requirement-file requirement.json
            """
        )
        
        # Global options
        parser.add_argument('--config', '-c', type=str, default='config.json',
                          help='Path to system configuration file (default: config.json)')
        parser.add_argument('--verbose', '-v', action='store_true',
                          help='Enable verbose output')
        parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                          default='INFO', help='Set logging level')
        parser.add_argument('--log-file', type=str,
                          help='Path to log file (default: console only)')
        
        # Subcommands
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # CWMP vs Operator Requirement comparison
        cwmp_operator_requirement_parser = subparsers.add_parser('cwmp-vs-operator-requirement',
                                                  help='Compare CWMP source against operator requirement definitions')
        cwmp_operator_requirement_parser.add_argument('--cwmp-config', required=True,
                                      help='Path to CWMP configuration file')
        cwmp_operator_requirement_parser.add_argument('--operator-requirement-file', required=True,
                                      help='Path to operator requirement definition file')
        cwmp_operator_requirement_parser.add_argument('--output', '-o', required=True,
                                      help='Output file path for comparison results')
        cwmp_operator_requirement_parser.add_argument('--format', choices=['json', 'xml', 'text'],
                                      default='json', help='Output format (json, xml, or text)')
        cwmp_operator_requirement_parser.add_argument('--include-metadata', action='store_true',
                                      help='Include metadata and additional details in output')
        
        # Operator Requirement vs Device comparison
        operator_requirement_device_parser = subparsers.add_parser('operator-requirement-vs-device',
                                                   help='Compare operator requirement against device implementation')
        operator_requirement_device_parser.add_argument('--operator-requirement-file', required=True,
                                        help='Path to operator requirement definition file')
        operator_requirement_device_parser.add_argument('--device-config', required=True,
                                        help='Path to device configuration file')
        operator_requirement_device_parser.add_argument('--output', '-o', required=True,
                                        help='Output file path for comparison results')
        operator_requirement_device_parser.add_argument('--format', choices=['json', 'xml', 'text'],
                                        default='json', help='Output format')
        operator_requirement_device_parser.add_argument('--include-validation', action='store_true',
                                        help='Include validation and event/function testing')
        operator_requirement_device_parser.add_argument('--include-metadata', action='store_true',
                                        help='Include metadata in output')
        
        # Deprecated alias for backward compatibility
        deprecated_operator_requirement_device_parser = subparsers.add_parser('subset-vs-device',
                                                   help='[DEPRECATED] Use operator-requirement-vs-device instead')
        # Create mutually exclusive group for the file argument
        deprecated_operator_requirement_file_group = deprecated_operator_requirement_device_parser.add_mutually_exclusive_group(required=True)
        deprecated_operator_requirement_file_group.add_argument('--operator-requirement-file',
                                        help='Path to operator requirement definition file')
        deprecated_operator_requirement_file_group.add_argument('--subset-file',
                                        help='[DEPRECATED] Path to subset definition file (use --operator-requirement-file)')
        deprecated_operator_requirement_device_parser.add_argument('--device-config', required=True,
                                        help='Path to device configuration file')
        deprecated_operator_requirement_device_parser.add_argument('--output', '-o', required=True,
                                        help='Output file path for comparison results')
        deprecated_operator_requirement_device_parser.add_argument('--format', choices=['json', 'xml', 'text'],
                                        default='json', help='Output format')
        deprecated_operator_requirement_device_parser.add_argument('--include-validation', action='store_true',
                                        help='Include validation and event/function testing')
        deprecated_operator_requirement_device_parser.add_argument('--include-metadata', action='store_true',
                                        help='Include metadata in output')
        
        # Device vs Device comparison
        device_device_parser = subparsers.add_parser('device-vs-device',
                                                   help='Compare two device implementations')
        device_device_parser.add_argument('--device1-config', required=True,
                                        help='Path to first device configuration file')
        device_device_parser.add_argument('--device2-config', required=True,
                                        help='Path to second device configuration file')
        device_device_parser.add_argument('--output', '-o', required=True,
                                        help='Output file path for comparison results')
        device_device_parser.add_argument('--format', choices=['json', 'xml', 'text'],
                                        default='json', help='Output format')
        device_device_parser.add_argument('--include-metadata', action='store_true',
                                        help='Include metadata in output')
        
        # Configuration management commands
        list_configs_parser = subparsers.add_parser('list-configs',
                                                  help='List available configurations')
        
        validate_operator_requirement_parser = subparsers.add_parser('validate-operator-requirement',
                                                     help='Validate an operator requirement definition file')
        validate_operator_requirement_parser.add_argument('--operator-requirement-file', required=True,
                                          help='Path to operator requirement definition file')
        
        # Deprecated alias for backward compatibility
        deprecated_validate_operator_requirement_parser = subparsers.add_parser('validate-subset',
                                                     help='[DEPRECATED] Use validate-operator-requirement instead')
        # Create mutually exclusive group for the file argument
        deprecated_validate_operator_requirement_file_group = deprecated_validate_operator_requirement_parser.add_mutually_exclusive_group(required=True)
        deprecated_validate_operator_requirement_file_group.add_argument('--operator-requirement-file',
                                          help='Path to operator requirement definition file')
        deprecated_validate_operator_requirement_file_group.add_argument('--subset-file',
                                          help='[DEPRECATED] Path to subset definition file (use --operator-requirement-file)')
        
        create_config_parser = subparsers.add_parser('create-config',
                                                   help='Create a default configuration file')
        create_config_parser.add_argument('--output', '-o', default='config.json',
                                        help='Output path for configuration file')
        
        # Extract command for standalone extraction
        extract_parser = subparsers.add_parser('extract',
                                             help='Extract TR181 nodes from a source')
        extract_parser.add_argument('--source-type', choices=['cwmp', 'device', 'operator-requirement'],
                                  required=True, help='Type of source to extract from')
        extract_parser.add_argument('--source-config', required=True,
                                  help='Path to source configuration file')
        extract_parser.add_argument('--output', '-o', required=True,
                                  help='Output file path for extracted nodes')
        extract_parser.add_argument('--format', choices=['json', 'xml'],
                                  default='json', help='Output format')
        
        return parser
    
    def setup_logging(self, log_level: str, log_file: Optional[str] = None, verbose: bool = False):
        """Setup structured logging configuration."""
        # Map string log level to LogLevel enum
        log_level_map = {
            'DEBUG': LogLevel.DEBUG,
            'INFO': LogLevel.INFO,
            'WARNING': LogLevel.WARNING,
            'ERROR': LogLevel.ERROR
        }
        
        level = log_level_map.get(log_level.upper(), LogLevel.INFO)
        
        # Initialize structured logging system
        initialize_logging(
            log_level=level,
            log_file=log_file,
            enable_performance=True,
            enable_structured=True
        )
        
        # Get CLI logger
        self.logger = get_logger("cli")
        
        # Log CLI initialization
        self.logger.info(
            "CLI logging initialized",
            LogCategory.AUDIT,
            context={
                'log_level': log_level,
                'log_file': log_file,
                'verbose': verbose
            }
        )
    
    async def run(self, args: List[str] = None) -> int:
        """Run the CLI with given arguments."""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        # Setup logging
        self.setup_logging(parsed_args.log_level, parsed_args.log_file, parsed_args.verbose)
        
        # Setup progress reporter
        self.progress_reporter = CLIProgressReporter(parsed_args.verbose)
        
        try:
            # Load system configuration if it exists
            config_path = Path(parsed_args.config)
            if config_path.exists():
                system_config = self.config_manager.load_config(config_path)
                self.logger.log_configuration(
                    f"System configuration loaded from {config_path}",
                    "system", True, correlation_id=f"cli_{int(datetime.now().timestamp())}"
                )
            else:
                system_config = self.config_manager.create_default_config()
                self.logger.log_configuration(
                    f"Using default configuration (config file not found: {config_path})",
                    "system", True, correlation_id=f"cli_{int(datetime.now().timestamp())}"
                )
                if parsed_args.verbose:
                    self.progress_reporter.show_info(f"Using default configuration (config file not found: {config_path})")
            
            # Initialize main application
            self.app = TR181ComparatorApp(system_config, self.progress_reporter)
            
            # Log command execution
            self.logger.info(
                f"Executing CLI command: {parsed_args.command}",
                LogCategory.AUDIT,
                context={
                    'command': parsed_args.command,
                    'args': vars(parsed_args)
                }
            )
            
            # Check for deprecated commands
            if parsed_args.command in DEPRECATED_CLI_COMMANDS:
                new_command = DEPRECATED_CLI_COMMANDS[parsed_args.command]
                self.progress_reporter.show_warning(
                    f"Command '{parsed_args.command}' is deprecated. Use '{new_command}' instead."
                )
                
                # Log deprecation warning
                self.logger.warning(
                    "Deprecated CLI command used",
                    LogCategory.AUDIT,
                    context={
                        'deprecated_command': parsed_args.command,
                        'replacement': new_command
                    }
                )
            
            # Execute command
            if parsed_args.command == 'cwmp-vs-operator-requirement':
                return await self._handle_cwmp_vs_operator_requirement(parsed_args)
            elif parsed_args.command == 'operator-requirement-vs-device':
                return await self._handle_operator_requirement_vs_device(parsed_args)
            elif parsed_args.command == 'subset-vs-device':
                return await self._handle_operator_requirement_vs_device_deprecated(parsed_args)
            elif parsed_args.command == 'device-vs-device':
                return await self._handle_device_vs_device(parsed_args)
            elif parsed_args.command == 'list-configs':
                return await self._handle_list_configs(parsed_args)
            elif parsed_args.command == 'validate-operator-requirement':
                return await self._handle_validate_operator_requirement(parsed_args)
            elif parsed_args.command == 'validate-subset':
                return await self._handle_validate_operator_requirement_deprecated(parsed_args)
            elif parsed_args.command == 'create-config':
                return await self._handle_create_config(parsed_args)
            elif parsed_args.command == 'extract':
                return await self._handle_extract(parsed_args)
            else:
                parser.print_help()
                return 1
        
        except TR181Error as e:
            self.logger.error(
                f"TR181 Error in CLI: {e}",
                LogCategory.ERROR,
                context={'error_type': type(e).__name__, 'command': getattr(parsed_args, 'command', 'unknown')}
            )
            self.progress_reporter.show_error(f"TR181 Error: {e}")
            report_error(e)
            return 1
        except Exception as e:
            self.logger.critical(
                f"Unexpected error in CLI: {e}",
                LogCategory.ERROR,
                context={'error_type': type(e).__name__, 'command': getattr(parsed_args, 'command', 'unknown')}
            )
            self.progress_reporter.show_error(f"Unexpected error: {e}")
            logging.exception("Unexpected error in CLI")
            return 1
        finally:
            # Log performance summary if available
            try:
                perf_summary = get_performance_summary()
                if perf_summary.get('total_operations', 0) > 0:
                    self.logger.info(
                        "CLI session performance summary",
                        LogCategory.PERFORMANCE,
                        context=perf_summary
                    )
            except Exception:
                pass  # Don't fail on performance summary errors
    
    async def _handle_cwmp_vs_operator_requirement(self, args) -> int:
        """Handle CWMP vs operator requirement comparison command."""
        try:
            result = await self.app.compare_cwmp_vs_operator_requirement(
                cwmp_config_path=args.cwmp_config,
                operator_requirement_file_path=args.operator_requirement_file
            )
            
            await self._save_comparison_result(
                result, args.output, args.format, args.include_metadata
            )
            
            self._print_comparison_summary(result)
            return 0
        
        except Exception as e:
            self.progress_reporter.show_error(f"CWMP vs operator requirement comparison failed: {e}")
            return 1
    
    async def _handle_operator_requirement_vs_device(self, args) -> int:
        """Handle operator requirement vs device comparison command."""
        try:
            result = await self.app.compare_operator_requirement_vs_device(
                operator_requirement_file_path=args.operator_requirement_file,
                device_config_path=args.device_config,
                include_validation=args.include_validation
            )
            
            await self._save_comparison_result(
                result, args.output, args.format, args.include_metadata
            )
            
            self._print_comparison_summary(result)
            return 0
        
        except Exception as e:
            self.progress_reporter.show_error(f"Operator requirement vs device comparison failed: {e}")
            return 1
    
    async def _handle_operator_requirement_vs_device_deprecated(self, args) -> int:
        """Handle deprecated operator requirement vs device comparison command."""
        try:
            # Show command deprecation warning
            self.logger.warning(
                "Deprecated CLI command used",
                LogCategory.AUDIT,
                context={
                    'deprecated_command': 'subset-vs-device',
                    'replacement': 'operator-requirement-vs-device'
                }
            )
            
            # Determine which argument was provided
            operator_requirement_file = getattr(args, 'operator_requirement_file', None) or getattr(args, 'subset_file', None)
            
            if not operator_requirement_file:
                self.progress_reporter.show_error("Either --operator-requirement-file or --subset-file must be provided")
                return 1
            
            # Show deprecation warning if --subset-file was used
            if hasattr(args, 'subset_file') and args.subset_file:
                self.logger.warning(
                    "Deprecated CLI argument used",
                    LogCategory.AUDIT,
                    context={
                        'deprecated_argument': 'subset-file',
                        'replacement': 'operator-requirement-file'
                    }
                )
                self.progress_reporter.show_warning(
                    "Argument '--subset-file' is deprecated. Use '--operator-requirement-file' instead."
                )
            
            result = await self.app.compare_operator_requirement_vs_device(
                operator_requirement_file_path=operator_requirement_file,
                device_config_path=args.device_config,
                include_validation=args.include_validation
            )
            
            await self._save_comparison_result(
                result, args.output, args.format, args.include_metadata
            )
            
            self._print_comparison_summary(result)
            return 0
        
        except Exception as e:
            self.progress_reporter.show_error(f"Operator requirement vs device comparison failed: {e}")
            return 1
    
    async def _handle_device_vs_device(self, args) -> int:
        """Handle device vs device comparison command."""
        try:
            result = await self.app.compare_device_vs_device(
                device1_config_path=args.device1_config,
                device2_config_path=args.device2_config
            )
            
            await self._save_comparison_result(
                result, args.output, args.format, args.include_metadata
            )
            
            self._print_comparison_summary(result)
            return 0
        
        except Exception as e:
            self.progress_reporter.show_error(f"Device vs device comparison failed: {e}")
            return 1
    
    async def _handle_list_configs(self, args) -> int:
        """Handle list configurations command."""
        try:
            config = self.config_manager.get_config()
            if not config:
                print("No configuration loaded")
                return 1
            
            print("Available Configurations:")
            print("=" * 50)
            
            print(f"\nDevices ({len(config.devices)}):")
            for i, device in enumerate(config.devices):
                name = device.name or f"Device {i+1}"
                print(f"  {i+1}. {name} ({device.type}) - {device.endpoint}")
            
            print(f"\nOperator Requirements ({len(config.operator_requirements)}):")
            for i, operator_requirement in enumerate(config.operator_requirements):
                print(f"  {i+1}. {operator_requirement.name} - {operator_requirement.file_path}")
            
            print(f"\nHook Configurations ({len(config.hook_configs)}):")
            for hook_name, hook_config in config.hook_configs.items():
                print(f"  - {hook_name}: {hook_config.hook_type}")
            
            return 0
        
        except Exception as e:
            self.progress_reporter.show_error(f"Failed to list configurations: {e}")
            return 1
    
    async def _handle_validate_operator_requirement(self, args) -> int:
        """Handle validate operator requirement command."""
        try:
            is_valid, errors = await self.app.validate_operator_requirement_file(args.operator_requirement_file)
            
            if is_valid:
                print(f"Operator requirement file '{args.operator_requirement_file}' is valid")
                return 0
            else:
                print(f"Operator requirement file '{args.operator_requirement_file}' has validation errors:")
                for error in errors:
                    print(f"  - {error}")
                return 1
        
        except Exception as e:
            self.progress_reporter.show_error(f"Failed to validate operator requirement: {e}")
            return 1
    
    async def _handle_validate_operator_requirement_deprecated(self, args) -> int:
        """Handle deprecated validate operator requirement command."""
        try:
            # Show command deprecation warning
            self.logger.warning(
                "Deprecated CLI command used",
                LogCategory.AUDIT,
                context={
                    'deprecated_command': 'validate-subset',
                    'replacement': 'validate-operator-requirement'
                }
            )
            
            # Determine which argument was provided
            operator_requirement_file = getattr(args, 'operator_requirement_file', None) or getattr(args, 'subset_file', None)
            
            if not operator_requirement_file:
                self.progress_reporter.show_error("Either --operator-requirement-file or --subset-file must be provided")
                return 1
            
            # Show deprecation warning if --subset-file was used
            if hasattr(args, 'subset_file') and args.subset_file:
                self.logger.warning(
                    "Deprecated CLI argument used",
                    LogCategory.AUDIT,
                    context={
                        'deprecated_argument': 'subset-file',
                        'replacement': 'operator-requirement-file'
                    }
                )
                self.progress_reporter.show_warning(
                    "Argument '--subset-file' is deprecated. Use '--operator-requirement-file' instead."
                )
            
            is_valid, errors = await self.app.validate_operator_requirement_file(operator_requirement_file)
            
            if is_valid:
                print(f"Operator requirement file '{operator_requirement_file}' is valid")
                return 0
            else:
                print(f"Operator requirement file '{operator_requirement_file}' has validation errors:")
                for error in errors:
                    print(f"  - {error}")
                return 1
        
        except Exception as e:
            self.progress_reporter.show_error(f"Failed to validate operator requirement: {e}")
            return 1
    
    async def _handle_create_config(self, args) -> int:
        """Handle create configuration command."""
        try:
            default_config = self.config_manager.create_default_config()
            self.config_manager.save_config(default_config, args.output)
            print(f"Default configuration created at: {args.output}")
            return 0
        
        except Exception as e:
            self.progress_reporter.show_error(f"Failed to create configuration: {e}")
            return 1
    
    async def _handle_extract(self, args) -> int:
        """Handle extract command."""
        try:
            nodes = await self.app.extract_nodes(
                source_type=args.source_type,
                source_config_path=args.source_config
            )
            
            await self._save_extracted_nodes(nodes, args.output, args.format)
            
            print(f"Extracted {len(nodes)} TR181 nodes to {args.output}")
            return 0
        
        except Exception as e:
            self.progress_reporter.show_error(f"Failed to extract nodes: {e}")
            return 1
    
    async def _save_comparison_result(self, result: Any, output_path: str, 
                                   format_type: str, include_metadata: bool):
        """Save comparison result to file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format_type == 'json':
            await self._save_as_json(result, output_file, include_metadata)
        elif format_type == 'xml':
            await self._save_as_xml(result, output_file, include_metadata)
        elif format_type == 'text':
            await self._save_as_text(result, output_file, include_metadata)
    
    async def _save_extracted_nodes(self, nodes: List[TR181Node], output_path: str, format_type: str):
        """Save extracted nodes to file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format_type == 'json':
            # Convert nodes to dictionaries for JSON serialization
            nodes_data = [self._node_to_dict(node) for node in nodes]
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(nodes_data, f, indent=2, default=str)
        elif format_type == 'xml':
            # Simple XML format for nodes
            xml_content = self._nodes_to_xml(nodes)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)
    
    async def _save_as_json(self, result: Any, output_file: Path, include_metadata: bool):
        """Save result as JSON."""
        # This would use the report generator from the main app
        await self.app.export_result_as_json(result, output_file, include_metadata)
    
    async def _save_as_xml(self, result: Any, output_file: Path, include_metadata: bool):
        """Save result as XML."""
        # This would use the report generator from the main app
        await self.app.export_result_as_xml(result, output_file, include_metadata)
    
    async def _save_as_text(self, result: Any, output_file: Path, include_metadata: bool):
        """Save result as human-readable text."""
        # This would use the report generator from the main app
        await self.app.export_result_as_text(result, output_file, include_metadata)
    
    def _print_comparison_summary(self, result: Any):
        """Print a summary of comparison results to console."""
        if hasattr(result, 'get_summary'):
            summary = result.get_summary()
            print("\nComparison Summary:")
            print("=" * 30)
            
            if 'basic_comparison' in summary:
                basic = summary['basic_comparison']
                print(f"Total differences: {basic['total_differences']}")
                print(f"Missing in target: {basic['missing_in_device']}")
                print(f"Extra in target: {basic['extra_in_device']}")
                print(f"Common nodes: {basic['common_nodes']}")
            
            if 'validation' in summary:
                validation = summary['validation']
                print(f"Validation errors: {validation['nodes_with_errors']}")
                print(f"Validation warnings: {validation['total_warnings']}")
            
            if 'compliance' in summary:
                compliance = summary['compliance']
                print(f"Compliance score: {compliance['score']:.2%}")
        else:
            # Basic comparison result
            if hasattr(result, 'summary'):
                print(f"\nComparison Summary:")
                print(f"Total differences: {result.summary.differences_count}")
                print(f"Common nodes: {result.summary.common_nodes}")
    
    def _node_to_dict(self, node: TR181Node) -> Dict[str, Any]:
        """Convert TR181Node to dictionary for serialization."""
        return {
            'path': node.path,
            'name': node.name,
            'data_type': node.data_type,
            'access': node.access.value,
            'value': node.value,
            'description': node.description,
            'parent': node.parent,
            'children': node.children,
            'is_object': node.is_object,
            'is_custom': node.is_custom,
            'value_range': self._value_range_to_dict(node.value_range) if node.value_range else None,
            'events': [self._event_to_dict(e) for e in node.events] if node.events else [],
            'functions': [self._function_to_dict(f) for f in node.functions] if node.functions else []
        }
    
    def _value_range_to_dict(self, value_range) -> Dict[str, Any]:
        """Convert ValueRange to dictionary."""
        return {
            'min_value': value_range.min_value,
            'max_value': value_range.max_value,
            'allowed_values': value_range.allowed_values,
            'pattern': value_range.pattern,
            'max_length': value_range.max_length
        }
    
    def _event_to_dict(self, event) -> Dict[str, Any]:
        """Convert TR181Event to dictionary."""
        return {
            'name': event.name,
            'path': event.path,
            'parameters': event.parameters,
            'description': event.description
        }
    
    def _function_to_dict(self, function) -> Dict[str, Any]:
        """Convert TR181Function to dictionary."""
        return {
            'name': function.name,
            'path': function.path,
            'input_parameters': function.input_parameters,
            'output_parameters': function.output_parameters,
            'description': function.description
        }
    
    def _nodes_to_xml(self, nodes: List[TR181Node]) -> str:
        """Convert nodes list to XML format."""
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append('<tr181_nodes>')
        
        for node in nodes:
            xml_lines.append(f'  <node path="{node.path}">')
            xml_lines.append(f'    <name>{node.name}</name>')
            xml_lines.append(f'    <data_type>{node.data_type}</data_type>')
            xml_lines.append(f'    <access>{node.access.value}</access>')
            if node.value is not None:
                xml_lines.append(f'    <value>{node.value}</value>')
            if node.description:
                xml_lines.append(f'    <description>{node.description}</description>')
            xml_lines.append(f'    <is_object>{node.is_object}</is_object>')
            xml_lines.append(f'    <is_custom>{node.is_custom}</is_custom>')
            xml_lines.append('  </node>')
        
        xml_lines.append('</tr181_nodes>')
        return '\n'.join(xml_lines)


def main():
    """Main entry point for the CLI."""
    cli = TR181ComparatorCLI()
    try:
        exit_code = asyncio.run(cli.run())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()