"""Main application class that orchestrates all TR181 comparator components."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime

from .config import SystemConfig, DeviceConfig, SubsetConfig
from .models import TR181Node, ComparisonResult
from .comparison import ComparisonEngine, EnhancedComparisonEngine, EnhancedComparisonResult
from .extractors import (
    CWMPExtractor, HookBasedDeviceExtractor, SubsetManager, 
    NodeExtractor, ValidationResult
)
from .hooks import DeviceHookFactory, DeviceConfig as HookDeviceConfig, HookType
from .validation import TR181Validator
from .errors import (
    TR181Error, ConnectionError, ValidationError, ConfigurationError,
    ErrorCategory, ErrorSeverity, ErrorContext,
    report_error, get_error_reporter
)
from .logging import (
    get_logger, performance_monitor, LogCategory, 
    initialize_logging, LogLevel
)


class ReportGenerator:
    """Generates reports in various formats from comparison results."""
    
    def __init__(self, include_metadata: bool = True):
        self.include_metadata = include_metadata
    
    async def export_as_json(self, result: Union[ComparisonResult, EnhancedComparisonResult], 
                           output_path: Path, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Export comparison result as JSON."""
        try:
            data = self._result_to_dict(result)
            
            if self.include_metadata and metadata:
                data['metadata'] = metadata
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        
        except Exception as e:
            raise TR181Error(f"Failed to export JSON report: {e}", ErrorCategory.DATA_FORMAT)
    
    async def export_as_xml(self, result: Union[ComparisonResult, EnhancedComparisonResult], 
                          output_path: Path, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Export comparison result as XML."""
        try:
            xml_content = self._result_to_xml(result, metadata)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
        
        except Exception as e:
            raise TR181Error(f"Failed to export XML report: {e}", ErrorCategory.DATA_FORMAT)
    
    async def export_as_text(self, result: Union[ComparisonResult, EnhancedComparisonResult], 
                           output_path: Path, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Export comparison result as human-readable text."""
        try:
            text_content = self._result_to_text(result, metadata)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
        
        except Exception as e:
            raise TR181Error(f"Failed to export text report: {e}", ErrorCategory.DATA_FORMAT)
    
    def _result_to_dict(self, result: Union[ComparisonResult, EnhancedComparisonResult]) -> Dict[str, Any]:
        """Convert comparison result to dictionary."""
        if isinstance(result, EnhancedComparisonResult):
            return {
                'type': 'enhanced_comparison',
                'summary': result.get_summary(),
                'basic_comparison': self._basic_result_to_dict(result.basic_comparison),
                'validation_results': [
                    {
                        'path': path,
                        'is_valid': vr.is_valid,
                        'errors': vr.errors,
                        'warnings': vr.warnings
                    }
                    for path, vr in result.validation_results
                ],
                'event_test_results': [
                    {
                        'event_name': etr.event_name,
                        'status': etr.status.value,
                        'message': etr.message,
                        'subscription_test': etr.subscription_test
                    }
                    for etr in result.event_test_results
                ],
                'function_test_results': [
                    {
                        'function_name': ftr.function_name,
                        'status': ftr.status.value,
                        'message': ftr.message,
                        'execution_test': ftr.execution_test
                    }
                    for ftr in result.function_test_results
                ]
            }
        else:
            return self._basic_result_to_dict(result)
    
    def _basic_result_to_dict(self, result: ComparisonResult) -> Dict[str, Any]:
        """Convert basic comparison result to dictionary."""
        return {
            'type': 'basic_comparison',
            'summary': {
                'total_nodes_source1': result.summary.total_nodes_source1,
                'total_nodes_source2': result.summary.total_nodes_source2,
                'common_nodes': result.summary.common_nodes,
                'differences_count': result.summary.differences_count
            },
            'only_in_source1': [self._node_to_dict(node) for node in result.only_in_source1],
            'only_in_source2': [self._node_to_dict(node) for node in result.only_in_source2],
            'differences': [
                {
                    'path': diff.path,
                    'property': diff.property,
                    'source1_value': diff.source1_value,
                    'source2_value': diff.source2_value,
                    'severity': diff.severity.value
                }
                for diff in result.differences
            ]
        }
    
    def _node_to_dict(self, node: TR181Node) -> Dict[str, Any]:
        """Convert TR181Node to dictionary."""
        return {
            'path': node.path,
            'name': node.name,
            'data_type': node.data_type,
            'access': node.access.value,
            'value': node.value,
            'description': node.description,
            'is_object': node.is_object,
            'is_custom': node.is_custom
        }
    
    def _result_to_xml(self, result: Union[ComparisonResult, EnhancedComparisonResult], 
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """Convert comparison result to XML format."""
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append('<comparison_result>')
        
        if self.include_metadata and metadata:
            xml_lines.append('  <metadata>')
            for key, value in metadata.items():
                xml_lines.append(f'    <{key}>{value}</{key}>')
            xml_lines.append('  </metadata>')
        
        if isinstance(result, EnhancedComparisonResult):
            summary = result.get_summary()
            xml_lines.append('  <type>enhanced_comparison</type>')
        else:
            summary = {
                'basic_comparison': {
                    'total_differences': result.summary.differences_count,
                    'common_nodes': result.summary.common_nodes
                }
            }
            xml_lines.append('  <type>basic_comparison</type>')
        
        xml_lines.append('  <summary>')
        xml_lines.append(f'    <total_differences>{summary["basic_comparison"]["total_differences"]}</total_differences>')
        xml_lines.append(f'    <common_nodes>{summary["basic_comparison"]["common_nodes"]}</common_nodes>')
        xml_lines.append('  </summary>')
        
        xml_lines.append('</comparison_result>')
        return '\n'.join(xml_lines)
    
    def _result_to_text(self, result: Union[ComparisonResult, EnhancedComparisonResult], 
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """Convert comparison result to human-readable text format."""
        lines = []
        lines.append("TR181 Node Comparison Report")
        lines.append("=" * 50)
        lines.append("")
        
        if self.include_metadata and metadata:
            lines.append("Metadata:")
            for key, value in metadata.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        
        if isinstance(result, EnhancedComparisonResult):
            summary = result.get_summary()
            lines.append("Enhanced Comparison Summary:")
            lines.append(f"  Total differences: {summary['basic_comparison']['total_differences']}")
            lines.append(f"  Common nodes: {summary['basic_comparison']['common_nodes']}")
            lines.append(f"  Validation errors: {summary['validation']['nodes_with_errors']}")
            lines.append(f"  Validation warnings: {summary['validation']['total_warnings']}")
            lines.append(f"  Event test failures: {summary['events']['failed_events']}")
            lines.append(f"  Function test failures: {summary['functions']['failed_functions']}")
            if 'compliance' in summary:
                lines.append(f"  Compliance score: {summary['compliance']['score']:.2%}")
        else:
            lines.append("Basic Comparison Summary:")
            lines.append(f"  Total differences: {result.summary.differences_count}")
            lines.append(f"  Common nodes: {result.summary.common_nodes}")
            lines.append(f"  Nodes only in source 1: {len(result.only_in_source1)}")
            lines.append(f"  Nodes only in source 2: {len(result.only_in_source2)}")
        
        lines.append("")
        return '\n'.join(lines)


class TR181ComparatorApp:
    """Main application class that orchestrates all TR181 comparator components."""
    
    def __init__(self, config: SystemConfig, progress_reporter=None):
        """Initialize the TR181 comparator application."""
        self.config = config
        self.progress_reporter = progress_reporter
        
        # Initialize structured logging
        self.logger = get_logger("main")
        
        # Initialize components
        self.comparison_engine = ComparisonEngine()
        self.enhanced_comparison_engine = EnhancedComparisonEngine()
        self.validator = TR181Validator()
        self.report_generator = ReportGenerator(config.export_settings.include_metadata)
        self.hook_factory = DeviceHookFactory()
        
        # Error reporter
        self.error_reporter = get_error_reporter()
        
        # Log initialization
        self.logger.info(
            "TR181 Comparator App initialized",
            LogCategory.AUDIT,
            context={
                'config_type': type(config).__name__,
                'has_progress_reporter': progress_reporter is not None
            }
        )
    
    def _report_progress(self, step_name: str, step_number: Optional[int] = None):
        """Report progress if progress reporter is available."""
        if self.progress_reporter:
            self.progress_reporter.update_progress(step_name, step_number)
    
    def _report_info(self, message: str):
        """Report informational message."""
        if self.progress_reporter:
            self.progress_reporter.show_info(message)
        self.logger.info(message)
    
    def _report_warning(self, message: str):
        """Report warning message."""
        if self.progress_reporter:
            self.progress_reporter.show_warning(message)
        self.logger.warning(message)
    
    def _report_error(self, message: str):
        """Report error message."""
        if self.progress_reporter:
            self.progress_reporter.show_error(message)
        self.logger.error(message)
    
    @performance_monitor("compare_cwmp_vs_subset", "main")
    async def compare_cwmp_vs_subset(self, cwmp_config_path: str, subset_file_path: str) -> ComparisonResult:
        """Compare CWMP source against subset definition."""
        correlation_id = f"cwmp_subset_{int(datetime.now().timestamp())}"
        
        self.logger.info(
            "Starting CWMP vs Subset comparison",
            LogCategory.COMPARISON,
            context={
                'cwmp_config_path': cwmp_config_path,
                'subset_file_path': subset_file_path
            },
            correlation_id=correlation_id
        )
        
        if self.progress_reporter:
            self.progress_reporter.start_operation("CWMP vs Subset Comparison", 4)
        
        try:
            # Load CWMP configuration
            self._report_progress("Loading CWMP configuration", 1)
            cwmp_config = await self._load_cwmp_config(cwmp_config_path)
            
            # Extract CWMP nodes
            self._report_progress("Extracting CWMP nodes", 2)
            cwmp_extractor = CWMPExtractor(cwmp_config)
            cwmp_nodes = await cwmp_extractor.extract()
            
            self.logger.log_extraction(
                f"Extracted {len(cwmp_nodes)} nodes from CWMP source",
                "cwmp", cwmp_config_path, len(cwmp_nodes), True, correlation_id
            )
            self._report_info(f"Extracted {len(cwmp_nodes)} nodes from CWMP source")
            
            # Load subset nodes
            self._report_progress("Loading subset definition", 3)
            subset_manager = SubsetManager(subset_file_path)
            subset_nodes = await subset_manager.extract()
            
            self.logger.log_extraction(
                f"Loaded {len(subset_nodes)} nodes from subset",
                "subset", subset_file_path, len(subset_nodes), True, correlation_id
            )
            self._report_info(f"Loaded {len(subset_nodes)} nodes from subset")
            
            # Perform comparison
            self._report_progress("Performing comparison", 4)
            result = await self.comparison_engine.compare(cwmp_nodes, subset_nodes)
            
            self.logger.log_comparison(
                "CWMP vs Subset comparison completed successfully",
                "cwmp", "subset", result.summary.differences_count, True, correlation_id
            )
            
            if self.progress_reporter:
                self.progress_reporter.complete_operation("CWMP vs Subset Comparison")
            
            return result
        
        except Exception as e:
            error_msg = f"CWMP vs subset comparison failed: {e}"
            self.logger.log_comparison(
                error_msg, "cwmp", "subset", 0, False, correlation_id
            )
            self._report_error(error_msg)
            if self.progress_reporter:
                self.progress_reporter.complete_operation("CWMP vs Subset Comparison", False)
            raise TR181Error(error_msg, ErrorCategory.CONNECTION) from e
    
    @performance_monitor("compare_subset_vs_device", "main")
    async def compare_subset_vs_device(self, subset_file_path: str, device_config_path: str, 
                                     include_validation: bool = False) -> Union[ComparisonResult, EnhancedComparisonResult]:
        """Compare subset against device implementation."""
        correlation_id = f"subset_device_{int(datetime.now().timestamp())}"
        operation_name = "Subset vs Device Comparison"
        total_steps = 5 if include_validation else 4
        
        self.logger.info(
            f"Starting {operation_name}",
            LogCategory.COMPARISON,
            context={
                'subset_file_path': subset_file_path,
                'device_config_path': device_config_path,
                'include_validation': include_validation
            },
            correlation_id=correlation_id
        )
        
        if self.progress_reporter:
            self.progress_reporter.start_operation(operation_name, total_steps)
        
        try:
            # Load subset nodes
            self._report_progress("Loading subset definition", 1)
            subset_manager = SubsetManager(subset_file_path)
            subset_nodes = await subset_manager.extract()
            
            self.logger.log_extraction(
                f"Loaded {len(subset_nodes)} nodes from subset",
                "subset", subset_file_path, len(subset_nodes), True, correlation_id
            )
            self._report_info(f"Loaded {len(subset_nodes)} nodes from subset")
            
            # Load device configuration
            self._report_progress("Loading device configuration", 2)
            device_config = await self._load_device_config(device_config_path)
            
            self.logger.log_configuration(
                "Device configuration loaded successfully",
                "device", True, correlation_id=correlation_id
            )
            
            # Extract device nodes
            self._report_progress("Extracting device nodes", 3)
            device_extractor = await self._create_device_extractor(device_config)
            device_nodes = await device_extractor.extract()
            
            self.logger.log_extraction(
                f"Extracted {len(device_nodes)} nodes from device",
                "device", device_config_path, len(device_nodes), True, correlation_id
            )
            self._report_info(f"Extracted {len(device_nodes)} nodes from device")
            
            # Perform comparison
            if include_validation:
                self._report_progress("Performing enhanced comparison with validation", 4)
                result = await self.enhanced_comparison_engine.compare_with_validation(
                    subset_nodes, device_nodes, device_extractor
                )
                self._report_progress("Generating validation report", 5)
                
                # Log validation results
                if hasattr(result, 'get_summary'):
                    summary = result.get_summary()
                    self.logger.log_validation(
                        "Enhanced comparison with validation completed",
                        "subset_vs_device",
                        summary.get('validation', {}).get('nodes_with_errors', 0),
                        summary.get('validation', {}).get('total_warnings', 0),
                        True, correlation_id
                    )
            else:
                self._report_progress("Performing basic comparison", 4)
                result = await self.comparison_engine.compare(subset_nodes, device_nodes)
            
            self.logger.log_comparison(
                f"{operation_name} completed successfully",
                "subset", "device", 
                result.summary.differences_count if hasattr(result, 'summary') else 
                result.basic_comparison.summary.differences_count,
                True, correlation_id
            )
            
            if self.progress_reporter:
                self.progress_reporter.complete_operation(operation_name)
            
            return result
        
        except Exception as e:
            error_msg = f"Subset vs device comparison failed: {e}"
            self.logger.log_comparison(
                error_msg, "subset", "device", 0, False, correlation_id
            )
            self._report_error(error_msg)
            if self.progress_reporter:
                self.progress_reporter.complete_operation(operation_name, False)
            raise TR181Error(error_msg, ErrorCategory.CONNECTION) from e
    
    @performance_monitor("compare_device_vs_device", "main")
    async def compare_device_vs_device(self, device1_config_path: str, device2_config_path: str) -> ComparisonResult:
        """Compare two device implementations."""
        correlation_id = f"device_device_{int(datetime.now().timestamp())}"
        
        self.logger.info(
            "Starting Device vs Device comparison",
            LogCategory.COMPARISON,
            context={
                'device1_config_path': device1_config_path,
                'device2_config_path': device2_config_path
            },
            correlation_id=correlation_id
        )
        
        if self.progress_reporter:
            self.progress_reporter.start_operation("Device vs Device Comparison", 5)
        
        try:
            # Load device configurations
            self._report_progress("Loading device configurations", 1)
            device1_config = await self._load_device_config(device1_config_path)
            device2_config = await self._load_device_config(device2_config_path)
            
            self.logger.log_configuration(
                "Device configurations loaded successfully",
                "device_pair", True, correlation_id=correlation_id
            )
            
            # Extract nodes from first device
            self._report_progress("Extracting nodes from first device", 2)
            device1_extractor = await self._create_device_extractor(device1_config)
            device1_nodes = await device1_extractor.extract()
            
            self.logger.log_extraction(
                f"Extracted {len(device1_nodes)} nodes from first device",
                "device", device1_config_path, len(device1_nodes), True, correlation_id
            )
            self._report_info(f"Extracted {len(device1_nodes)} nodes from first device")
            
            # Extract nodes from second device
            self._report_progress("Extracting nodes from second device", 3)
            device2_extractor = await self._create_device_extractor(device2_config)
            device2_nodes = await device2_extractor.extract()
            
            self.logger.log_extraction(
                f"Extracted {len(device2_nodes)} nodes from second device",
                "device", device2_config_path, len(device2_nodes), True, correlation_id
            )
            self._report_info(f"Extracted {len(device2_nodes)} nodes from second device")
            
            # Perform comparison
            self._report_progress("Performing comparison", 4)
            result = await self.comparison_engine.compare(device1_nodes, device2_nodes)
            
            self._report_progress("Finalizing results", 5)
            
            self.logger.log_comparison(
                "Device vs Device comparison completed successfully",
                "device", "device", result.summary.differences_count, True, correlation_id
            )
            
            if self.progress_reporter:
                self.progress_reporter.complete_operation("Device vs Device Comparison")
            
            return result
        
        except Exception as e:
            error_msg = f"Device vs device comparison failed: {e}"
            self.logger.log_comparison(
                error_msg, "device", "device", 0, False, correlation_id
            )
            self._report_error(error_msg)
            if self.progress_reporter:
                self.progress_reporter.complete_operation("Device vs Device Comparison", False)
            raise TR181Error(error_msg, ErrorCategory.CONNECTION) from e
    
    async def extract_nodes(self, source_type: str, source_config_path: str) -> List[TR181Node]:
        """Extract TR181 nodes from a source."""
        if self.progress_reporter:
            self.progress_reporter.start_operation(f"Extracting {source_type} nodes", 2)
        
        try:
            self._report_progress(f"Loading {source_type} configuration", 1)
            
            if source_type == 'cwmp':
                config = await self._load_cwmp_config(source_config_path)
                extractor = CWMPExtractor(config)
            elif source_type == 'device':
                config = await self._load_device_config(source_config_path)
                extractor = await self._create_device_extractor(config)
            elif source_type == 'subset':
                extractor = SubsetManager(source_config_path)
            else:
                raise ValueError(f"Unsupported source type: {source_type}")
            
            self._report_progress(f"Extracting {source_type} nodes", 2)
            nodes = await extractor.extract()
            
            if self.progress_reporter:
                self.progress_reporter.complete_operation(f"Extracting {source_type} nodes")
            
            return nodes
        
        except Exception as e:
            error_msg = f"Failed to extract {source_type} nodes: {e}"
            self._report_error(error_msg)
            if self.progress_reporter:
                self.progress_reporter.complete_operation(f"Extracting {source_type} nodes", False)
            raise TR181Error(error_msg, ErrorCategory.DATA_FORMAT) from e
    
    async def validate_subset_file(self, subset_file_path: str) -> Tuple[bool, List[str]]:
        """Validate a subset definition file."""
        try:
            subset_manager = SubsetManager(subset_file_path)
            is_valid = await subset_manager.validate()
            
            if is_valid:
                return True, []
            else:
                # Get validation errors (this would be implemented in SubsetManager)
                return False, ["Subset validation failed - see logs for details"]
        
        except Exception as e:
            return False, [str(e)]
    
    async def export_result_as_json(self, result: Union[ComparisonResult, EnhancedComparisonResult], 
                                  output_path: Path, include_metadata: bool = True) -> None:
        """Export comparison result as JSON."""
        metadata = self._create_metadata() if include_metadata else None
        await self.report_generator.export_as_json(result, output_path, metadata)
    
    async def export_result_as_xml(self, result: Union[ComparisonResult, EnhancedComparisonResult], 
                                 output_path: Path, include_metadata: bool = True) -> None:
        """Export comparison result as XML."""
        metadata = self._create_metadata() if include_metadata else None
        await self.report_generator.export_as_xml(result, output_path, metadata)
    
    async def export_result_as_text(self, result: Union[ComparisonResult, EnhancedComparisonResult], 
                                  output_path: Path, include_metadata: bool = True) -> None:
        """Export comparison result as text."""
        metadata = self._create_metadata() if include_metadata else None
        await self.report_generator.export_as_text(result, output_path, metadata)
    
    async def _load_cwmp_config(self, config_path: str) -> Dict[str, Any]:
        """Load CWMP configuration from file."""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                raise FileNotFoundError(f"CWMP configuration file not found: {config_path}")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Validate required fields
            required_fields = ['endpoint', 'authentication']
            for field in required_fields:
                if field not in config:
                    raise ConfigurationError(f"Missing required field in CWMP config: {field}")
            
            return config
        
        except Exception as e:
            raise ConfigurationError(f"Failed to load CWMP configuration: {e}")
    
    async def _load_device_config(self, config_path: str) -> DeviceConfig:
        """Load device configuration from file."""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                raise FileNotFoundError(f"Device configuration file not found: {config_path}")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Create DeviceConfig object
            device_config = DeviceConfig(**config_data)
            return device_config
        
        except Exception as e:
            raise ConfigurationError(f"Failed to load device configuration: {e}")
    
    async def _create_device_extractor(self, device_config: DeviceConfig) -> HookBasedDeviceExtractor:
        """Create device extractor with appropriate hook."""
        try:
            # Convert DeviceConfig to HookDeviceConfig
            hook_device_config = HookDeviceConfig(
                type=device_config.type,
                endpoint=device_config.endpoint,
                authentication=device_config.authentication,
                timeout=device_config.timeout,
                retry_count=device_config.retry_count
            )
            
            # Convert string type to HookType enum
            hook_type_mapping = {
                'rest': HookType.REST_API,
                'rest_api': HookType.REST_API,
                'cwmp': HookType.CWMP,
                'tr069': HookType.CWMP
            }
            
            hook_type = hook_type_mapping.get(device_config.type.lower())
            if hook_type is None:
                raise ValueError(f"Unsupported hook type: {device_config.type}")
            
            # Create hook
            hook = self.hook_factory.create_hook(hook_type)
            
            # Create extractor
            extractor = HookBasedDeviceExtractor(hook, hook_device_config)
            
            return extractor
        
        except Exception as e:
            raise TR181Error(f"Failed to create device extractor: {e}", ErrorCategory.CONFIGURATION)
    
    def _create_metadata(self) -> Dict[str, Any]:
        """Create metadata for reports."""
        return {
            'timestamp': datetime.now().isoformat(),
            'generator': 'TR181 Node Comparator',
            'version': '0.1.0',
            'export_settings': {
                'include_metadata': self.config.export_settings.include_metadata,
                'default_format': self.config.export_settings.default_format
            }
        }