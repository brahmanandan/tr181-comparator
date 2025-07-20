"""Base extractor interface and source information for TR181 node extraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
from .models import TR181Node
from .logging import get_logger, performance_monitor, LogCategory

# Forward declarations for type hints
if False:  # TYPE_CHECKING
    from .hooks import DeviceConnectionHook, DeviceConfig


@dataclass
class SourceInfo:
    """Metadata about a TR181 data source."""
    type: str  # 'cwmp', 'device', or 'subset'
    identifier: str  # Source identifier (URL, file path, device ID, etc.)
    timestamp: datetime  # When the data was extracted/created
    metadata: Dict[str, Any]  # Additional source-specific metadata
    
    def __post_init__(self):
        """Validate source info after initialization."""
        if not self.type:
            raise ValueError("SourceInfo type cannot be empty")
        if not self.identifier:
            raise ValueError("SourceInfo identifier cannot be empty")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("SourceInfo timestamp must be a datetime object")
        if self.metadata is None:
            self.metadata = {}


class ValidationResult:
    """Result of validation operations with errors and warnings."""
    
    def __init__(self):
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def add_error(self, message: str):
        """Add an error message and mark validation as failed."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
    
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False
    
    def __bool__(self):
        """Return True if validation passed (no errors)."""
        return self.is_valid
    
    def __str__(self):
        """String representation of validation result."""
        if self.is_valid and not self.warnings:
            return "Validation passed"
        
        parts = []
        if not self.is_valid:
            parts.append(f"Validation failed with {len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        
        return "; ".join(parts)


class NodeExtractor(ABC):
    """Abstract base class for TR181 node extractors.
    
    This class defines the interface that all TR181 node extractors must implement.
    Extractors are responsible for retrieving TR181 node data from various sources
    such as CWMP endpoints, device APIs, or subset definition files.
    """
    
    def __init__(self, source_identifier: str, metadata: Optional[Dict[str, Any]] = None):
        """Initialize the extractor with source information.
        
        Args:
            source_identifier: Unique identifier for the data source
            metadata: Optional metadata about the source
        """
        self._source_identifier = source_identifier
        self._metadata = metadata or {}
        self._extraction_timestamp: Optional[datetime] = None
    
    @abstractmethod
    async def extract(self) -> List[TR181Node]:
        """Extract TR181 nodes from the data source.
        
        Returns:
            List of TR181Node objects extracted from the source
            
        Raises:
            ConnectionError: If unable to connect to the data source
            ValidationError: If the extracted data is invalid
            Exception: For other extraction failures
        """
        pass
    
    @abstractmethod
    async def validate(self) -> ValidationResult:
        """Validate the data source and extraction capability.
        
        This method should check if the data source is accessible and
        if the extractor can successfully retrieve data from it.
        
        Returns:
            ValidationResult indicating if the source is valid and accessible
        """
        pass
    
    @abstractmethod
    def get_source_info(self) -> SourceInfo:
        """Get metadata about the data source.
        
        Returns:
            SourceInfo object containing source metadata
        """
        pass
    
    def _update_extraction_timestamp(self):
        """Update the extraction timestamp to current time."""
        self._extraction_timestamp = datetime.now()
    
    def _validate_extracted_nodes(self, nodes: List[TR181Node]) -> ValidationResult:
        """Validate a list of extracted TR181 nodes.
        
        This base validation checks for common issues across all extractor types.
        Subclasses can override or extend this method for source-specific validation.
        
        Args:
            nodes: List of TR181Node objects to validate
            
        Returns:
            ValidationResult with any validation errors or warnings
        """
        result = ValidationResult()
        
        if not nodes:
            result.add_warning("No TR181 nodes were extracted")
            return result
        
        # Check for duplicate paths
        paths_seen = set()
        for node in nodes:
            if node.path in paths_seen:
                result.add_error(f"Duplicate node path found: {node.path}")
            paths_seen.add(node.path)
        
        # Validate individual nodes
        for node in nodes:
            node_validation = self._validate_single_node(node)
            result.merge(node_validation)
        
        # Check for orphaned child references
        all_paths = {node.path for node in nodes}
        for node in nodes:
            if node.children:
                for child_path in node.children:
                    if child_path not in all_paths:
                        result.add_warning(f"Node {node.path} references non-existent child: {child_path}")
            
            if node.parent and node.parent not in all_paths:
                result.add_warning(f"Node {node.path} references non-existent parent: {node.parent}")
        
        return result
    
    def _validate_single_node(self, node: TR181Node) -> ValidationResult:
        """Validate a single TR181 node.
        
        Args:
            node: TR181Node to validate
            
        Returns:
            ValidationResult for the node
        """
        result = ValidationResult()
        
        # Basic path validation
        if not node.path.startswith('Device.'):
            result.add_warning(f"Node path should start with 'Device.': {node.path}")
        
        # Check for proper TR181 naming conventions
        path_parts = node.path.split('.')
        for i, part in enumerate(path_parts):
            if i == 0:  # Skip 'Device'
                continue
            if not part:
                result.add_error(f"Empty path component in: {node.path}")
            elif not part[0].isupper() and not part.isdigit():
                result.add_warning(f"Path component '{part}' should start with uppercase letter in: {node.path}")
        
        # Validate data type consistency
        if node.value is not None:
            type_validation = self._validate_node_data_type(node)
            result.merge(type_validation)
        
        return result
    
    def _validate_node_data_type(self, node: TR181Node) -> ValidationResult:
        """Validate that a node's value matches its declared data type.
        
        Args:
            node: TR181Node to validate
            
        Returns:
            ValidationResult for data type validation
        """
        result = ValidationResult()
        
        if node.value is None:
            return result
        
        expected_type = node.data_type.lower()
        value = node.value
        
        if expected_type == 'string' and not isinstance(value, str):
            result.add_error(f"Expected string, got {type(value).__name__} for {node.path}")
        elif expected_type == 'int' and not isinstance(value, int):
            result.add_error(f"Expected int, got {type(value).__name__} for {node.path}")
        elif expected_type == 'boolean' and not isinstance(value, bool):
            result.add_error(f"Expected boolean, got {type(value).__name__} for {node.path}")
        elif expected_type == 'datetime':
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    result.add_error(f"Invalid datetime format for {node.path}: {value}")
            elif not isinstance(value, datetime):
                result.add_error(f"Expected datetime or ISO string, got {type(value).__name__} for {node.path}")
        
        return result


class CWMPExtractor(NodeExtractor):
    """CWMP extractor for TR-069 protocol that extracts TR181 nodes from CWMP sources.
    
    This extractor uses CWMP/TR-069 protocol operations to discover and retrieve
    TR181 parameter information from CWMP-enabled devices or ACS systems.
    """
    
    def __init__(self, cwmp_hook: 'CWMPHook', device_config: 'DeviceConfig', 
                 metadata: Optional[Dict[str, Any]] = None):
        """Initialize the CWMP extractor.
        
        Args:
            cwmp_hook: CWMP communication hook instance
            device_config: CWMP device connection configuration
            metadata: Optional metadata about the CWMP source
        """
        super().__init__(device_config.endpoint, metadata)
        self.cwmp_hook = cwmp_hook
        self.device_config = device_config
        self._connected = False
        self._parameter_cache: Dict[str, Dict[str, Any]] = {}
        
        # Initialize logging
        self.logger = get_logger("cwmp_extractor")
        
        # Initialize error handling components
        from .errors import RetryManager, RetryConfig, GracefulDegradationManager
        self.retry_manager = RetryManager(
            config=RetryConfig(
                max_attempts=device_config.retry_count if hasattr(device_config, 'retry_count') else 3,
                base_delay=1.0,
                max_delay=30.0,
                backoff_factor=2.0
            )
        )
        self.degradation_manager = GracefulDegradationManager(min_success_rate=0.7)
        
        # Log initialization
        self.logger.info(
            "CWMP extractor initialized",
            LogCategory.EXTRACTION,
            context={
                'endpoint': device_config.endpoint,
                'device_type': device_config.type,
                'timeout': device_config.timeout
            }
        )
    
    @performance_monitor("extract_cwmp_nodes", "cwmp_extractor")
    async def extract(self) -> List[TR181Node]:
        """Extract TR181 nodes from CWMP source using GetParameterNames and GetParameterValues.
        
        Returns:
            List of TR181Node objects extracted from the CWMP source
            
        Raises:
            ConnectionError: If unable to connect to the CWMP source
            ValidationError: If the extracted data is invalid
            Exception: For other extraction failures
        """
        from .errors import ConnectionError, ValidationError, ErrorContext, report_error
        
        try:
            # Ensure connection is established
            if not self._connected:
                await self._ensure_connection()
            
            # Discover all parameters using recursive GetParameterNames
            print("Discovering TR181 parameters from CWMP source...")
            parameter_paths = await self._discover_all_parameters()
            
            if not parameter_paths:
                print("No parameters discovered from CWMP source")
                return []
            
            print(f"Discovered {len(parameter_paths)} parameters")
            
            # Get parameter attributes for all discovered parameters
            print("Retrieving parameter attributes...")
            parameter_attributes = await self._get_parameter_attributes_batch(parameter_paths)
            
            # Get parameter values for all discovered parameters
            print("Retrieving parameter values...")
            parameter_values = await self._get_parameter_values_batch(parameter_paths)
            
            # Build TR181Node objects from the collected data
            print("Building TR181 node structure...")
            nodes = await self._build_node_structure(parameter_paths, parameter_attributes, parameter_values)
            
            # Validate extracted nodes
            validation_result = self._validate_extracted_nodes(nodes)
            if not validation_result.is_valid:
                print(f"Validation warnings: {len(validation_result.warnings)} warnings, {len(validation_result.errors)} errors")
                if validation_result.errors:
                    # Log errors but don't fail extraction unless critical
                    for error in validation_result.errors[:5]:  # Log first 5 errors
                        print(f"Validation error: {error}")
            
            self._update_extraction_timestamp()
            print(f"Successfully extracted {len(nodes)} TR181 nodes from CWMP source")
            return nodes
            
        except Exception as e:
            context = ErrorContext(
                operation="extract_cwmp_nodes",
                component="CWMPExtractor",
                metadata={
                    "endpoint": self.device_config.endpoint,
                    "connected": self._connected
                }
            )
            
            if isinstance(e, (ConnectionError, ValidationError)):
                # Re-raise known errors with context
                e.context = context
                raise e
            else:
                # Wrap unknown errors
                report_error(
                    error=ConnectionError(
                        message=f"CWMP extraction failed: {str(e)}",
                        endpoint=self.device_config.endpoint,
                        context=context,
                        cause=e
                    )
                )
                raise ConnectionError(
                    message=f"CWMP extraction failed: {str(e)}",
                    endpoint=self.device_config.endpoint,
                    context=context,
                    cause=e
                )
    
    async def validate(self) -> ValidationResult:
        """Validate the CWMP source and extraction capability.
        
        Returns:
            ValidationResult indicating if the CWMP source is valid and accessible
        """
        result = ValidationResult()
        
        try:
            # Test connection to CWMP source
            connection_success = await self.cwmp_hook.connect(self.device_config)
            if not connection_success:
                result.add_error("Failed to connect to CWMP source")
                return result
            
            self._connected = True
            
            # Test basic CWMP operations
            try:
                # Test GetParameterNames with a basic path
                test_params = await self.cwmp_hook.get_parameter_names("Device.DeviceInfo.")
                if not test_params:
                    result.add_warning("No parameters found under Device.DeviceInfo - CWMP source may be empty")
                else:
                    result.add_warning(f"CWMP source validation successful - found {len(test_params)} test parameters")
                
                # Test GetParameterValues with a common parameter
                if test_params:
                    test_values = await self.cwmp_hook.get_parameter_values([test_params[0]])
                    if test_values:
                        result.add_warning("CWMP GetParameterValues operation successful")
                
            except Exception as e:
                result.add_error(f"CWMP operation test failed: {str(e)}")
            
        except Exception as e:
            result.add_error(f"CWMP connection validation failed: {str(e)}")
        finally:
            # Clean up test connection
            if self._connected:
                try:
                    await self.cwmp_hook.disconnect()
                    self._connected = False
                except Exception:
                    pass  # Ignore disconnect errors during validation
        
        return result
    
    def get_source_info(self) -> SourceInfo:
        """Get metadata about the CWMP source.
        
        Returns:
            SourceInfo object containing CWMP source metadata
        """
        return SourceInfo(
            type="cwmp",
            identifier=self.device_config.endpoint,
            timestamp=self._extraction_timestamp or datetime.now(),
            metadata={
                **self._metadata,
                "device_type": self.device_config.type,
                "timeout": self.device_config.timeout,
                "retry_count": getattr(self.device_config, 'retry_count', 3),
                "parameters_cached": len(self._parameter_cache)
            }
        )
    
    async def _ensure_connection(self) -> None:
        """Ensure connection to CWMP source is established."""
        from .errors import ConnectionError
        
        if not self._connected:
            try:
                connection_success = await self.cwmp_hook.connect(self.device_config)
                if not connection_success:
                    raise ConnectionError(
                        message="Failed to establish CWMP connection",
                        endpoint=self.device_config.endpoint
                    )
                self._connected = True
            except Exception as e:
                if isinstance(e, ConnectionError):
                    raise e
                raise ConnectionError(
                    message=f"CWMP connection failed: {str(e)}",
                    endpoint=self.device_config.endpoint,
                    cause=e
                )
    
    async def _discover_all_parameters(self) -> List[str]:
        """Discover all TR181 parameters using recursive GetParameterNames operations.
        
        Returns:
            List of all discovered parameter paths
            
        Raises:
            ConnectionError: If parameter discovery fails completely
        """
        all_parameters = []
        paths_to_explore = ["Device."]
        explored_paths = set()
        failed_paths = []
        
        while paths_to_explore:
            current_path = paths_to_explore.pop(0)
            
            if current_path in explored_paths:
                continue
            
            explored_paths.add(current_path)
            
            try:
                # Get parameter names under current path
                parameters = await self.cwmp_hook.get_parameter_names(current_path)
                
                for param_path in parameters:
                    if param_path not in all_parameters:
                        all_parameters.append(param_path)
                    
                    # If this looks like an object path (ends with .), add it for further exploration
                    if param_path.endswith('.') and param_path not in explored_paths:
                        paths_to_explore.append(param_path)
                    
                    # Also check for numbered instances (e.g., Device.WiFi.Radio.1.)
                    if not param_path.endswith('.'):
                        # Check if this could be a parent of numbered instances
                        potential_object_path = param_path + '.'
                        if potential_object_path not in explored_paths:
                            # Try to see if there are numbered instances
                            try:
                                instance_params = await self.cwmp_hook.get_parameter_names(potential_object_path)
                                if instance_params:
                                    paths_to_explore.append(potential_object_path)
                            except Exception:
                                # Ignore errors when checking for instances
                                pass
                
            except Exception as e:
                print(f"Warning: Failed to get parameters for path {current_path}: {str(e)}")
                failed_paths.append(current_path)
                
                # If we fail on the root Device. path, this is a critical failure
                if current_path == "Device.":
                    from .errors import ConnectionError
                    raise ConnectionError(
                        message=f"Failed to discover parameters from CWMP source: {str(e)}",
                        endpoint=self.device_config.endpoint,
                        cause=e
                    )
                continue
        
        return all_parameters
    
    async def _get_parameter_attributes_batch(self, parameter_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get parameter attributes for a batch of parameters with error handling.
        
        Args:
            parameter_paths: List of parameter paths to get attributes for
            
        Returns:
            Dictionary mapping parameter paths to their attributes
        """
        all_attributes = {}
        batch_size = 50  # Process in batches to avoid overwhelming the device
        
        for i in range(0, len(parameter_paths), batch_size):
            batch = parameter_paths[i:i + batch_size]
            
            try:
                batch_attributes = await self.cwmp_hook.get_parameter_attributes(batch)
                all_attributes.update(batch_attributes)
            except Exception as e:
                print(f"Warning: Failed to get attributes for batch {i//batch_size + 1}: {str(e)}")
                
                # Try individual parameters in this batch
                for param_path in batch:
                    try:
                        param_attributes = await self.cwmp_hook.get_parameter_attributes([param_path])
                        all_attributes.update(param_attributes)
                    except Exception as param_e:
                        print(f"Warning: Failed to get attributes for {param_path}: {str(param_e)}")
                        # Provide default attributes
                        all_attributes[param_path] = {
                            "type": "string",
                            "access": "read-only",
                            "notification": "off"
                        }
        
        return all_attributes
    
    async def _get_parameter_values_batch(self, parameter_paths: List[str]) -> Dict[str, Any]:
        """Get parameter values for a batch of parameters with error handling.
        
        Args:
            parameter_paths: List of parameter paths to get values for
            
        Returns:
            Dictionary mapping parameter paths to their current values
        """
        all_values = {}
        batch_size = 50  # Process in batches to avoid overwhelming the device
        
        for i in range(0, len(parameter_paths), batch_size):
            batch = parameter_paths[i:i + batch_size]
            
            try:
                batch_values = await self.cwmp_hook.get_parameter_values(batch)
                all_values.update(batch_values)
            except Exception as e:
                print(f"Warning: Failed to get values for batch {i//batch_size + 1}: {str(e)}")
                
                # Try individual parameters in this batch
                for param_path in batch:
                    try:
                        param_values = await self.cwmp_hook.get_parameter_values([param_path])
                        all_values.update(param_values)
                    except Exception as param_e:
                        print(f"Warning: Failed to get value for {param_path}: {str(param_e)}")
                        # Leave value as None for failed parameters
                        all_values[param_path] = None
        
        return all_values
    
    async def _build_node_structure(self, parameter_paths: List[str], 
                                  parameter_attributes: Dict[str, Dict[str, Any]], 
                                  parameter_values: Dict[str, Any]) -> List[TR181Node]:
        """Build TR181Node objects from discovered parameter data.
        
        Args:
            parameter_paths: List of all discovered parameter paths
            parameter_attributes: Dictionary of parameter attributes
            parameter_values: Dictionary of parameter values
            
        Returns:
            List of TR181Node objects with hierarchical relationships
        """
        from .models import AccessLevel
        
        nodes = []
        path_to_node = {}
        
        # First pass: create all nodes
        for param_path in parameter_paths:
            attributes = parameter_attributes.get(param_path, {})
            value = parameter_values.get(param_path)
            
            # Extract parameter name from path
            param_name = param_path.split('.')[-1] if not param_path.endswith('.') else param_path.split('.')[-2]
            
            # Determine if this is an object node
            is_object = param_path.endswith('.')
            
            # Map CWMP access levels to our enum
            access_str = attributes.get("access", "read-only").lower()
            if access_str in ["read-write", "readwrite"]:
                access = AccessLevel.READ_WRITE
            elif access_str in ["write-only", "writeonly"]:
                access = AccessLevel.WRITE_ONLY
            else:
                access = AccessLevel.READ_ONLY
            
            # Map CWMP data types to standard types
            data_type = self._map_cwmp_data_type(attributes.get("type", "string"))
            
            # Create TR181Node
            node = TR181Node(
                path=param_path,
                name=param_name,
                data_type=data_type,
                access=access,
                value=value,
                description=attributes.get("description"),
                is_object=is_object,
                is_custom=False  # CWMP parameters are standard TR181
            )
            
            nodes.append(node)
            path_to_node[param_path] = node
        
        # Second pass: establish parent-child relationships
        for node in nodes:
            # Find parent
            path_parts = node.path.rstrip('.').split('.')
            if len(path_parts) > 1:
                # Try different parent path formats
                potential_parents = []
                
                # For Device.WiFi.Radio.1.Channel, try:
                # - Device.WiFi.Radio.1.
                # - Device.WiFi.Radio.
                # - Device.WiFi.
                for i in range(len(path_parts) - 1, 0, -1):
                    parent_path = '.'.join(path_parts[:i]) + '.'
                    if parent_path in path_to_node:
                        potential_parents.append(parent_path)
                
                if potential_parents:
                    # Use the most specific parent
                    parent_path = potential_parents[0]
                    node.parent = parent_path
                    
                    # Add this node as child to parent
                    parent_node = path_to_node[parent_path]
                    if parent_node.children is None:
                        parent_node.children = []
                    if node.path not in parent_node.children:
                        parent_node.children.append(node.path)
        
        return nodes
    
    def _validate_node_data_type(self, node: TR181Node) -> ValidationResult:
        """Validate that a node's value matches its declared data type.
        
        Override for CWMP extractor to be more lenient since CWMP values often come as strings
        and may need conversion. It focuses on whether the value can be reasonably
        interpreted as the expected type rather than strict type matching.
        
        Args:
            node: TR181Node to validate
            
        Returns:
            ValidationResult for data type validation
        """
        result = ValidationResult()
        
        if node.value is None:
            return result
        
        expected_type = node.data_type.lower()
        value = node.value
        
        # For CWMP extractors, be more lenient with type validation
        # since values often come as strings from CWMP APIs
        if expected_type == 'string':
            # Any value can be converted to string, so this is always valid
            pass
        elif expected_type == 'int':
            # Check if value can be converted to int
            if not isinstance(value, int):
                if isinstance(value, str):
                    try:
                        int(value)  # Try to convert
                    except ValueError:
                        result.add_error(f"Value '{value}' cannot be converted to int for {node.path}")
                else:
                    result.add_warning(f"Expected int-compatible value, got {type(value).__name__} for {node.path}")
        elif expected_type == 'boolean':
            # Check if value can be interpreted as boolean
            if not isinstance(value, bool):
                if isinstance(value, str):
                    if value.lower() not in ['true', 'false', '1', '0', 'yes', 'no', 'on', 'off']:
                        result.add_error(f"Value '{value}' cannot be interpreted as boolean for {node.path}")
                elif isinstance(value, int):
                    if value not in [0, 1]:
                        result.add_warning(f"Integer value {value} may not represent a boolean for {node.path}")
                else:
                    result.add_warning(f"Expected boolean-compatible value, got {type(value).__name__} for {node.path}")
        elif expected_type == 'datetime':
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    result.add_error(f"Invalid datetime format for {node.path}: {value}")
            elif not isinstance(value, datetime):
                result.add_warning(f"Expected datetime or ISO string, got {type(value).__name__} for {node.path}")
        
        return result
    
    def _map_cwmp_data_type(self, cwmp_type: str) -> str:
        """Map CWMP data types to standard TR181 data types.
        
        Args:
            cwmp_type: CWMP data type string
            
        Returns:
            Standard TR181 data type string
        """
        type_mapping = {
            "xsd:string": "string",
            "string": "string",
            "xsd:int": "int",
            "int": "int",
            "integer": "int",
            "xsd:boolean": "boolean",
            "boolean": "boolean",
            "bool": "boolean",
            "xsd:datetime": "dateTime",
            "datetime": "dateTime",
            "date": "dateTime",
            "xsd:base64binary": "base64",
            "base64": "base64",
            "xsd:hexbinary": "hexBinary",
            "hex": "hexBinary",
            "unsignedint": "int",
            "long": "int",
            "unsignedlong": "int"
        }
        
        return type_mapping.get(cwmp_type.lower(), "string")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_connection()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._connected:
            try:
                await self.cwmp_hook.disconnect()
                self._connected = False
            except Exception:
                pass  # Ignore disconnect errors


# Import comprehensive error classes from errors module
from .errors import (
    ConnectionError, ValidationError, AuthenticationError, TimeoutError,
    ProtocolError, ConfigurationError, ErrorContext, ErrorCategory,
    ErrorSeverity, RetryManager, RetryConfig, GracefulDegradationManager,
    PartialResult, report_error
)


class SubsetManager(NodeExtractor):
    """Manages custom TR181 subsets and custom node definitions.
    
    This class handles loading, saving, and validating custom TR181 node subsets
    from JSON/YAML files. It supports both standard TR181 nodes and custom
    node definitions while ensuring proper validation and duplicate detection.
    """
    
    def __init__(self, subset_path: str, metadata: Optional[Dict[str, Any]] = None):
        """Initialize the SubsetManager with a file path.
        
        Args:
            subset_path: Path to the subset definition file (JSON or YAML)
            metadata: Optional metadata about the subset
        """
        super().__init__(subset_path, metadata)
        self.subset_path = subset_path
        self._nodes: List[TR181Node] = []
        self._loaded = False
    
    async def extract(self) -> List[TR181Node]:
        """Extract TR181 nodes from the subset definition file.
        
        Returns:
            List of TR181Node objects from the subset
            
        Raises:
            FileNotFoundError: If the subset file doesn't exist
            ValidationError: If the subset data is invalid
            Exception: For other loading failures
        """
        if not self._loaded:
            await self._load_subset()
        
        self._update_extraction_timestamp()
        return self._nodes.copy()
    
    async def validate(self) -> ValidationResult:
        """Validate the subset file and its contents.
        
        Returns:
            ValidationResult indicating if the subset is valid
        """
        result = ValidationResult()
        
        try:
            # Check if file exists and is readable
            import os
            if not os.path.exists(self.subset_path):
                result.add_error(f"Subset file not found: {self.subset_path}")
                return result
            
            if not os.access(self.subset_path, os.R_OK):
                result.add_error(f"Subset file is not readable: {self.subset_path}")
                return result
            
            # Try to load and validate the subset
            await self._load_subset()
            validation_result = self._validate_extracted_nodes(self._nodes)
            result.merge(validation_result)
            
        except Exception as e:
            result.add_error(f"Failed to validate subset: {str(e)}")
        
        return result
    
    def get_source_info(self) -> SourceInfo:
        """Get metadata about the subset source.
        
        Returns:
            SourceInfo object containing subset metadata
        """
        return SourceInfo(
            type="subset",
            identifier=self.subset_path,
            timestamp=self._extraction_timestamp or datetime.now(),
            metadata={
                **self._metadata,
                "node_count": len(self._nodes),
                "custom_nodes": sum(1 for node in self._nodes if node.is_custom),
                "file_format": self._detect_file_format()
            }
        )
    
    async def save_subset(self, nodes: List[TR181Node]) -> None:
        """Save TR181 nodes to the subset file.
        
        Args:
            nodes: List of TR181Node objects to save
            
        Raises:
            ValidationError: If nodes fail validation
            Exception: For file writing failures
        """
        # Validate nodes before saving
        validation_result = await self._validate_nodes_for_saving(nodes)
        if not validation_result.is_valid:
            raise ValidationError(f"Cannot save subset: {'; '.join(validation_result.errors)}")
        
        # Convert nodes to serializable format
        subset_data = self._nodes_to_dict(nodes)
        
        # Write to file
        await self._write_subset_file(subset_data)
        
        # Update internal state
        self._nodes = nodes.copy()
        self._loaded = True
        self._update_extraction_timestamp()
    
    async def add_custom_node(self, node: TR181Node) -> None:
        """Add a custom node to the subset.
        
        Args:
            node: TR181Node to add (will be marked as custom)
            
        Raises:
            ValidationError: If the node is invalid or conflicts with existing nodes
        """
        # Ensure we have loaded existing nodes
        if not self._loaded:
            await self._load_subset()
        
        # Mark as custom node
        node.is_custom = True
        
        # Validate the custom node
        validation_result = await self._validate_custom_node(node)
        if not validation_result.is_valid:
            raise ValidationError(f"Invalid custom node: {'; '.join(validation_result.errors)}")
        
        # Check for conflicts with existing nodes
        existing_paths = {existing_node.path for existing_node in self._nodes}
        if node.path in existing_paths:
            raise ValidationError(f"Node path already exists: {node.path}")
        
        # Add the node
        self._nodes.append(node)
    
    async def remove_node(self, path: str) -> bool:
        """Remove a node from the subset by path.
        
        Args:
            path: TR181 path of the node to remove
            
        Returns:
            True if node was removed, False if not found
        """
        if not self._loaded:
            await self._load_subset()
        
        original_count = len(self._nodes)
        self._nodes = [node for node in self._nodes if node.path != path]
        return len(self._nodes) < original_count
    
    def get_custom_nodes(self) -> List[TR181Node]:
        """Get only the custom nodes from the subset.
        
        Returns:
            List of custom TR181Node objects
        """
        return [node for node in self._nodes if node.is_custom]
    
    def get_standard_nodes(self) -> List[TR181Node]:
        """Get only the standard TR181 nodes from the subset.
        
        Returns:
            List of standard TR181Node objects
        """
        return [node for node in self._nodes if not node.is_custom]
    
    async def _load_subset(self) -> None:
        """Load subset definition from file."""
        import json
        import os
        
        if not os.path.exists(self.subset_path):
            # Create empty subset if file doesn't exist
            self._nodes = []
            self._loaded = True
            return
        
        # Check if file is empty
        if os.path.getsize(self.subset_path) == 0:
            # Create empty subset if file is empty
            self._nodes = []
            self._loaded = True
            return
        
        try:
            with open(self.subset_path, 'r', encoding='utf-8') as f:
                if self._detect_file_format() == 'yaml':
                    import yaml
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            # Handle case where file contains null/empty data
            if data is None:
                self._nodes = []
                self._loaded = True
                return
            
            self._nodes = self._dict_to_nodes(data)
            self._loaded = True
            
        except Exception as e:
            raise ValidationError(f"Failed to load subset from {self.subset_path}: {str(e)}")
    
    async def _write_subset_file(self, data: Dict[str, Any]) -> None:
        """Write subset data to file."""
        import json
        import os
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.subset_path), exist_ok=True)
        
        try:
            with open(self.subset_path, 'w', encoding='utf-8') as f:
                if self._detect_file_format() == 'yaml':
                    import yaml
                    yaml.safe_dump(data, f, default_flow_style=False, indent=2)
                else:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Failed to write subset to {self.subset_path}: {str(e)}")
    
    def _detect_file_format(self) -> str:
        """Detect file format based on extension."""
        if self.subset_path.lower().endswith(('.yml', '.yaml')):
            return 'yaml'
        return 'json'
    
    def _nodes_to_dict(self, nodes: List[TR181Node]) -> Dict[str, Any]:
        """Convert TR181Node objects to dictionary format for serialization."""
        return {
            "version": "1.0",
            "metadata": {
                "created": datetime.now().isoformat(),
                "description": "TR181 node subset definition",
                "total_nodes": len(nodes),
                "custom_nodes": sum(1 for node in nodes if node.is_custom)
            },
            "nodes": [self._node_to_dict(node) for node in nodes]
        }
    
    def _node_to_dict(self, node: TR181Node) -> Dict[str, Any]:
        """Convert a single TR181Node to dictionary format."""
        node_dict = {
            "path": node.path,
            "name": node.name,
            "data_type": node.data_type,
            "access": node.access.value,
            "is_object": node.is_object,
            "is_custom": node.is_custom
        }
        
        # Add optional fields if present
        if node.value is not None:
            node_dict["value"] = node.value
        if node.description:
            node_dict["description"] = node.description
        if node.parent:
            node_dict["parent"] = node.parent
        if node.children:
            node_dict["children"] = node.children
        
        # Add value range if present
        if node.value_range:
            range_dict = {}
            if node.value_range.min_value is not None:
                range_dict["min_value"] = node.value_range.min_value
            if node.value_range.max_value is not None:
                range_dict["max_value"] = node.value_range.max_value
            if node.value_range.allowed_values:
                range_dict["allowed_values"] = node.value_range.allowed_values
            if node.value_range.pattern:
                range_dict["pattern"] = node.value_range.pattern
            if node.value_range.max_length is not None:
                range_dict["max_length"] = node.value_range.max_length
            if range_dict:
                node_dict["value_range"] = range_dict
        
        # Add events if present
        if node.events:
            node_dict["events"] = [
                {
                    "name": event.name,
                    "path": event.path,
                    "parameters": event.parameters,
                    "description": event.description
                }
                for event in node.events
            ]
        
        # Add functions if present
        if node.functions:
            node_dict["functions"] = [
                {
                    "name": func.name,
                    "path": func.path,
                    "input_parameters": func.input_parameters,
                    "output_parameters": func.output_parameters,
                    "description": func.description
                }
                for func in node.functions
            ]
        
        return node_dict
    
    def _dict_to_nodes(self, data: Dict[str, Any]) -> List[TR181Node]:
        """Convert dictionary data to TR181Node objects."""
        if not isinstance(data, dict) or "nodes" not in data:
            raise ValidationError("Invalid subset format: missing 'nodes' key")
        
        nodes = []
        for node_data in data["nodes"]:
            node = self._dict_to_node(node_data)
            nodes.append(node)
        
        return nodes
    
    def _dict_to_node(self, node_data: Dict[str, Any]) -> TR181Node:
        """Convert dictionary data to a single TR181Node object."""
        from .models import AccessLevel, ValueRange, TR181Event, TR181Function
        
        # Required fields
        try:
            path = node_data["path"]
            name = node_data["name"]
            data_type = node_data["data_type"]
            access = AccessLevel(node_data["access"])
        except KeyError as e:
            context = ErrorContext(
                operation="parse_node_data",
                component="SubsetManager",
                metadata={"node_data": node_data}
            )
            raise ValidationError(
                message=f"Missing required field in node data: {e}",
                node_path=node_data.get("path", "unknown"),
                context=context,
                cause=e
            )
        except ValueError as e:
            context = ErrorContext(
                operation="parse_access_level",
                component="SubsetManager",
                metadata={"access_value": node_data.get("access")}
            )
            raise ValidationError(
                message=f"Invalid access level: {e}",
                node_path=node_data.get("path", "unknown"),
                context=context,
                cause=e
            )
        
        # Optional fields
        value = node_data.get("value")
        description = node_data.get("description")
        parent = node_data.get("parent")
        children = node_data.get("children", [])
        is_object = node_data.get("is_object", False)
        is_custom = node_data.get("is_custom", False)
        
        # Value range
        value_range = None
        if "value_range" in node_data:
            range_data = node_data["value_range"]
            value_range = ValueRange(
                min_value=range_data.get("min_value"),
                max_value=range_data.get("max_value"),
                allowed_values=range_data.get("allowed_values"),
                pattern=range_data.get("pattern"),
                max_length=range_data.get("max_length")
            )
        
        # Events
        events = []
        if "events" in node_data:
            for event_data in node_data["events"]:
                event = TR181Event(
                    name=event_data["name"],
                    path=event_data["path"],
                    parameters=event_data["parameters"],
                    description=event_data.get("description")
                )
                events.append(event)
        
        # Functions
        functions = []
        if "functions" in node_data:
            for func_data in node_data["functions"]:
                function = TR181Function(
                    name=func_data["name"],
                    path=func_data["path"],
                    input_parameters=func_data["input_parameters"],
                    output_parameters=func_data["output_parameters"],
                    description=func_data.get("description")
                )
                functions.append(function)
        
        return TR181Node(
            path=path,
            name=name,
            data_type=data_type,
            access=access,
            value=value,
            description=description,
            parent=parent,
            children=children,
            is_object=is_object,
            is_custom=is_custom,
            value_range=value_range,
            events=events,
            functions=functions
        )
    
    async def _validate_nodes_for_saving(self, nodes: List[TR181Node]) -> ValidationResult:
        """Validate nodes before saving to file."""
        result = ValidationResult()
        
        # Basic validation using parent class method
        base_validation = self._validate_extracted_nodes(nodes)
        result.merge(base_validation)
        
        # Additional validation for saving
        paths_seen = set()
        for node in nodes:
            # Check for duplicates
            if node.path in paths_seen:
                result.add_error(f"Duplicate node path: {node.path}")
            paths_seen.add(node.path)
            
            # Validate custom nodes have proper naming
            if node.is_custom:
                custom_validation = await self._validate_custom_node(node)
                result.merge(custom_validation)
        
        return result
    
    async def _validate_custom_node(self, node: TR181Node) -> ValidationResult:
        """Validate a custom TR181 node definition."""
        result = ValidationResult()
        
        # Custom nodes should follow TR181 naming conventions
        if not node.path.startswith('Device.'):
            result.add_error(f"Custom node path must start with 'Device.': {node.path}")
        
        # Check path format
        path_parts = node.path.split('.')
        for i, part in enumerate(path_parts):
            if i == 0:  # Skip 'Device'
                continue
            if not part:
                result.add_error(f"Empty path component in custom node: {node.path}")
            elif not part[0].isupper() and not part.isdigit():
                result.add_warning(f"Custom node path component '{part}' should start with uppercase letter: {node.path}")
        
        # Validate data type
        valid_types = ['string', 'int', 'boolean', 'dateTime', 'base64', 'hexBinary']
        if node.data_type not in valid_types:
            result.add_warning(f"Custom node uses non-standard data type '{node.data_type}' in {node.path}")
        
        # Validate value against data type if present
        if node.value is not None:
            type_validation = self._validate_node_data_type(node)
            result.merge(type_validation)
        
        return result


class HookBasedDeviceExtractor(NodeExtractor):
    """Device extractor that uses pluggable communication hooks for TR181 node extraction.
    
    This extractor connects to devices using various communication protocols through
    pluggable hooks (REST API, CWMP, etc.) and extracts TR181 node information.
    """
    
    def __init__(self, hook: 'DeviceConnectionHook', device_config: 'DeviceConfig', 
                 metadata: Optional[Dict[str, Any]] = None):
        """Initialize the hook-based device extractor.
        
        Args:
            hook: Device communication hook instance
            device_config: Device connection configuration
            metadata: Optional metadata about the device
        """
        super().__init__(device_config.endpoint, metadata)
        self.hook = hook
        self.device_config = device_config
        self._connected = False
        self._connection_validated = False
        
        # Initialize error handling components
        self.retry_manager = RetryManager(
            config=RetryConfig(
                max_attempts=device_config.retry_count if hasattr(device_config, 'retry_count') else 3,
                base_delay=1.0,
                max_delay=30.0,
                backoff_factor=2.0
            )
        )
        self.degradation_manager = GracefulDegradationManager(min_success_rate=0.7)
    
    async def extract(self) -> List[TR181Node]:
        """Extract TR181 nodes from the device using the communication hook.
        
        Returns:
            List of TR181Node objects extracted from the device
            
        Raises:
            ConnectionError: If unable to connect to the device
            ValidationError: If the extracted data is invalid
            Exception: For other extraction failures
        """
        context = ErrorContext(
            operation="extract_nodes",
            component="HookBasedDeviceExtractor",
            metadata={
                "endpoint": self.device_config.endpoint,
                "hook_type": type(self.hook).__name__
            }
        )
        
        try:
            # Ensure we're connected with retry logic
            await self.retry_manager.execute_with_retry(
                self._ensure_connected,
                "device_connection",
                context
            )
            
            # Discover all parameter names with retry
            parameter_names = await self.retry_manager.execute_with_retry(
                self._discover_all_parameters,
                "parameter_discovery",
                context
            )
            
            if not parameter_names:
                print("No parameters discovered from device")
                self._update_extraction_timestamp()
                return []
            
            print(f"Discovered {len(parameter_names)} parameters")
            
            # Build nodes from parameters
            nodes = await self._build_nodes_from_parameters(parameter_names)
            
            # Validate extracted nodes
            validation_result = self._validate_extracted_nodes(nodes)
            if not validation_result.is_valid:
                error = ValidationError(
                    message=f"Extracted nodes failed validation: {'; '.join(validation_result.errors)}",
                    validation_errors=validation_result.errors,
                    context=context
                )
                report_error(error)
                raise error
            
            if validation_result.warnings:
                print(f"Extraction completed with warnings: {'; '.join(validation_result.warnings)}")
            
            self._update_extraction_timestamp()
            print(f"Successfully extracted {len(nodes)} TR181 nodes from device")
            return nodes
            
        except (ConnectionError, ValidationError, AuthenticationError, TimeoutError, ProtocolError) as e:
            # These are already TR181Error instances, just report and re-raise
            report_error(e)
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error = ConnectionError(
                message=f"Unexpected error during node extraction: {str(e)}",
                endpoint=self.device_config.endpoint,
                context=context,
                cause=e
            )
            report_error(error)
            raise error
            
            # Get parameter attributes and values
            nodes = await self._build_nodes_from_parameters(parameter_names)
            
            # Validate extracted nodes
            validation_result = self._validate_extracted_nodes(nodes)
            if not validation_result.is_valid:
                raise ValidationError(f"Extracted nodes failed validation: {'; '.join(validation_result.errors)}")
            
            if validation_result.warnings:
                print(f"Extraction completed with warnings: {'; '.join(validation_result.warnings)}")
            
            self._update_extraction_timestamp()
            print(f"Successfully extracted {len(nodes)} TR181 nodes from device")
            return nodes
            
        except ConnectionError:
            raise
        except Exception as e:
            raise Exception(f"Failed to extract TR181 nodes from device {self.device_config.endpoint}: {str(e)}")
    
    async def validate(self) -> ValidationResult:
        """Validate the device connection and extraction capability.
        
        Returns:
            ValidationResult indicating if the device is accessible and valid
        """
        result = ValidationResult()
        
        try:
            # Test basic connectivity
            connection_result = await self._test_connectivity()
            if not connection_result:
                result.add_error(f"Cannot connect to device at {self.device_config.endpoint}")
                return result
            
            # Test parameter discovery capability
            try:
                test_params = await self.hook.get_parameter_names("Device.DeviceInfo")
                if not test_params:
                    result.add_warning("Device returned no parameters for Device.DeviceInfo - may not support TR181")
                else:
                    print(f"Device validation successful - found {len(test_params)} DeviceInfo parameters")
            except Exception as e:
                result.add_warning(f"Parameter discovery test failed: {str(e)}")
            
            # Test parameter value retrieval if we have parameters
            if not result.errors:
                try:
                    # Try to get a basic parameter that should exist on most devices
                    test_values = await self.hook.get_parameter_values(["Device.DeviceInfo.Manufacturer"])
                    if test_values:
                        print("Device parameter value retrieval test successful")
                    else:
                        result.add_warning("Device parameter value retrieval returned empty results")
                except Exception as e:
                    result.add_warning(f"Parameter value retrieval test failed: {str(e)}")
            
            self._connection_validated = True
            
        except Exception as e:
            result.add_error(f"Device validation failed: {str(e)}")
        
        return result
    
    def get_source_info(self) -> SourceInfo:
        """Get metadata about the device source.
        
        Returns:
            SourceInfo object containing device metadata
        """
        return SourceInfo(
            type="device",
            identifier=self.device_config.endpoint,
            timestamp=self._extraction_timestamp or datetime.now(),
            metadata={
                **self._metadata,
                "device_type": self.device_config.type,
                "hook_type": type(self.hook).__name__,
                "connected": self._connected,
                "validated": self._connection_validated,
                "timeout": self.device_config.timeout,
                "retry_count": self.device_config.retry_count
            }
        )
    
    async def disconnect(self) -> None:
        """Disconnect from the device and cleanup resources."""
        if self._connected:
            try:
                await self.hook.disconnect()
                print(f"Disconnected from device: {self.device_config.endpoint}")
            except Exception as e:
                print(f"Warning: Error during disconnect from {self.device_config.endpoint}: {str(e)}")
            finally:
                self._connected = False
                self._connection_validated = False
    
    async def test_parameter_write_access(self, test_params: Dict[str, Any]) -> Dict[str, bool]:
        """Test write access to specific parameters.
        
        Args:
            test_params: Dictionary of parameter paths to test values
            
        Returns:
            Dictionary mapping parameter paths to write success status
            
        Raises:
            ConnectionError: If device communication fails
        """
        await self._ensure_connected()
        
        write_results = {}
        for param_path, test_value in test_params.items():
            try:
                # Attempt to set the parameter value
                success = await self.hook.set_parameter_values({param_path: test_value})
                write_results[param_path] = success
            except Exception as e:
                print(f"Write test failed for {param_path}: {str(e)}")
                write_results[param_path] = False
        
        return write_results
    
    async def test_event_subscription(self, event_paths: List[str]) -> Dict[str, bool]:
        """Test event subscription capability.
        
        Args:
            event_paths: List of event paths to test subscription for
            
        Returns:
            Dictionary mapping event paths to subscription success status
            
        Raises:
            ConnectionError: If device communication fails
        """
        await self._ensure_connected()
        
        subscription_results = {}
        for event_path in event_paths:
            try:
                success = await self.hook.subscribe_to_event(event_path)
                subscription_results[event_path] = success
            except Exception as e:
                print(f"Event subscription test failed for {event_path}: {str(e)}")
                subscription_results[event_path] = False
        
        return subscription_results
    
    async def test_function_calls(self, function_tests: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Test function call capability.
        
        Args:
            function_tests: Dictionary mapping function paths to input parameters
            
        Returns:
            Dictionary mapping function paths to call results
            
        Raises:
            ConnectionError: If device communication fails
        """
        await self._ensure_connected()
        
        function_results = {}
        for function_path, input_params in function_tests.items():
            try:
                result = await self.hook.call_function(function_path, input_params)
                function_results[function_path] = {"success": True, "result": result}
            except Exception as e:
                print(f"Function call test failed for {function_path}: {str(e)}")
                function_results[function_path] = {"success": False, "error": str(e)}
        
        return function_results
    
    async def _ensure_connected(self) -> None:
        """Ensure connection to device is established."""
        if not self._connected:
            success = await self._connect_with_retry()
            if not success:
                raise ConnectionError(f"Failed to connect to device: {self.device_config.endpoint}")
    
    async def _connect_with_retry(self) -> bool:
        """Connect to device with retry logic and exponential backoff.
        
        Returns:
            True if connection successful, False otherwise
        """
        import asyncio
        
        for attempt in range(self.device_config.retry_count):
            try:
                print(f"Connecting to device {self.device_config.endpoint} (attempt {attempt + 1}/{self.device_config.retry_count})")
                success = await self.hook.connect(self.device_config)
                if success:
                    self._connected = True
                    print(f"Successfully connected to device: {self.device_config.endpoint}")
                    return True
                else:
                    print(f"Connection attempt {attempt + 1} failed")
            except Exception as e:
                print(f"Connection attempt {attempt + 1} failed with error: {str(e)}")
            
            # Exponential backoff for retry (except on last attempt)
            if attempt < self.device_config.retry_count - 1:
                wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                print(f"Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)
        
        print(f"Failed to connect to device after {self.device_config.retry_count} attempts")
        return False
    
    async def _test_connectivity(self) -> bool:
        """Test basic connectivity to the device.
        
        Returns:
            True if device is reachable and responsive, False otherwise
        """
        try:
            # Try to connect
            if not self._connected:
                success = await self._connect_with_retry()
                if not success:
                    return False
            
            # Test basic communication by trying to get a simple parameter
            try:
                await self.hook.get_parameter_names("Device")
                return True
            except Exception as e:
                print(f"Connectivity test failed: {str(e)}")
                return False
                
        except Exception as e:
            print(f"Connectivity test error: {str(e)}")
            return False
    
    async def _discover_all_parameters(self) -> List[str]:
        """Discover all TR181 parameters from the device.
        
        Returns:
            List of all parameter paths discovered
        """
        all_parameters = []
        
        try:
            # Start with root discovery
            root_params = await self.hook.get_parameter_names("Device.")
            all_parameters.extend(root_params)
            
            # For object parameters, we might need to discover sub-parameters
            # This is a simplified approach - real implementation might need recursive discovery
            object_paths = [param for param in root_params if param.endswith('.')]
            
            for obj_path in object_paths:
                try:
                    sub_params = await self.hook.get_parameter_names(obj_path)
                    # Avoid duplicates
                    for param in sub_params:
                        if param not in all_parameters:
                            all_parameters.append(param)
                except Exception as e:
                    print(f"Warning: Failed to discover sub-parameters for {obj_path}: {str(e)}")
            
            # Remove duplicates and sort
            all_parameters = sorted(list(set(all_parameters)))
            
        except Exception as e:
            print(f"Parameter discovery failed: {str(e)}")
            raise ConnectionError(f"Failed to discover parameters from device: {str(e)}")
        
        return all_parameters
    
    async def _build_nodes_from_parameters(self, parameter_names: List[str]) -> List[TR181Node]:
        """Build TR181Node objects from discovered parameter names.
        
        Args:
            parameter_names: List of parameter path names
            
        Returns:
            List of TR181Node objects
        """
        from .models import TR181Node, AccessLevel
        
        nodes = []
        
        # Process parameters in batches to avoid overwhelming the device
        batch_size = 50
        for i in range(0, len(parameter_names), batch_size):
            batch = parameter_names[i:i + batch_size]
            
            try:
                # Get attributes for this batch
                print(f"Getting attributes for parameters {i+1}-{min(i+batch_size, len(parameter_names))}")
                attributes = await self.hook.get_parameter_attributes(batch)
                
                # Get current values for this batch
                print(f"Getting values for parameters {i+1}-{min(i+batch_size, len(parameter_names))}")
                values = await self.hook.get_parameter_values(batch)
                
                # Build nodes for this batch
                for param_path in batch:
                    node = self._create_node_from_parameter(param_path, attributes.get(param_path, {}), values.get(param_path))
                    if node:
                        nodes.append(node)
                
            except Exception as e:
                print(f"Warning: Failed to process parameter batch {i+1}-{min(i+batch_size, len(parameter_names))}: {str(e)}")
                # Continue with next batch
                continue
        
        # Build hierarchical relationships
        self._build_node_relationships(nodes)
        
        return nodes
    
    def _create_node_from_parameter(self, param_path: str, attributes: Dict[str, Any], value: Any) -> Optional[TR181Node]:
        """Create a TR181Node from parameter information.
        
        Args:
            param_path: Parameter path
            attributes: Parameter attributes from device
            value: Current parameter value
            
        Returns:
            TR181Node object or None if creation fails
        """
        from .models import TR181Node, AccessLevel
        
        try:
            # Extract parameter name from path
            name = param_path.split('.')[-1] if '.' in param_path else param_path
            
            # Map device attributes to TR181Node format
            data_type = attributes.get('type', 'string')
            
            # Map access level
            access_str = attributes.get('access', 'read-only').lower()
            if access_str in ['read-write', 'readwrite']:
                access = AccessLevel.READ_WRITE
            elif access_str in ['write-only', 'writeonly']:
                access = AccessLevel.WRITE_ONLY
            else:
                access = AccessLevel.READ_ONLY
            
            # Determine if this is an object node
            is_object = param_path.endswith('.') or attributes.get('object', False)
            
            # Create the node
            node = TR181Node(
                path=param_path,
                name=name,
                data_type=data_type,
                access=access,
                value=value,
                description=attributes.get('description'),
                is_object=is_object,
                is_custom=False  # Device parameters are not custom
            )
            
            return node
            
        except Exception as e:
            print(f"Warning: Failed to create node for parameter {param_path}: {str(e)}")
            return None
    
    def _build_node_relationships(self, nodes: List[TR181Node]) -> None:
        """Build parent-child relationships between nodes.
        
        Args:
            nodes: List of TR181Node objects to build relationships for
        """
        # Create a mapping of paths to nodes
        node_map = {node.path: node for node in nodes}
        
        for node in nodes:
            # Find parent
            path_parts = node.path.split('.')
            if len(path_parts) > 1:
                # Try to find parent by removing last component
                parent_path = '.'.join(path_parts[:-1])
                if parent_path in node_map:
                    node.parent = parent_path
                    # Add this node as child to parent
                    parent_node = node_map[parent_path]
                    if node.path not in parent_node.children:
                        parent_node.children.append(node.path)
            
            # For object nodes, find direct children
            if node.is_object:
                node_prefix = node.path if node.path.endswith('.') else node.path + '.'
                for other_node in nodes:
                    if other_node.path != node.path and other_node.path.startswith(node_prefix):
                        # Check if it's a direct child (not grandchild)
                        relative_path = other_node.path[len(node_prefix):]
                        if '.' not in relative_path:  # Direct child
                            if other_node.path not in node.children:
                                node.children.append(other_node.path)
                            other_node.parent = node.path
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.disconnect()