"""TR181 node comparison engine for identifying differences between sources."""

from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass
from .models import (
    TR181Node, NodeDifference, ComparisonSummary, ComparisonResult, 
    Severity, AccessLevel
)
from .validation import ValidationResult, TR181Validator
from .event_function_tester import EventFunctionTester, EventTestResult, FunctionTestResult

# Forward declaration to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .extractors import HookBasedDeviceExtractor


@dataclass
class EnhancedComparisonResult:
    """Enhanced comparison result that includes validation and event/function testing."""
    basic_comparison: ComparisonResult
    validation_results: List[Tuple[str, ValidationResult]]  # (path, validation_result)
    event_test_results: List[EventTestResult]
    function_test_results: List[FunctionTestResult]
    
    def get_summary(self) -> Dict[str, Any]:
        """Generate comprehensive summary of all comparison and validation results."""
        validation_errors = sum(1 for _, result in self.validation_results if not result.is_valid)
        validation_warnings = sum(len(result.warnings) for _, result in self.validation_results)
        
        event_failures = sum(1 for result in self.event_test_results if result.status.value in ['failed', 'error'])
        function_failures = sum(1 for result in self.function_test_results if result.status.value in ['failed', 'error'])
        
        return {
            'basic_comparison': {
                'total_differences': self.basic_comparison.summary.differences_count,
                'missing_in_device': len(self.basic_comparison.only_in_source1),
                'extra_in_device': len(self.basic_comparison.only_in_source2),
                'common_nodes': self.basic_comparison.summary.common_nodes
            },
            'validation': {
                'nodes_with_errors': validation_errors,
                'total_warnings': validation_warnings,
                'nodes_validated': len(self.validation_results)
            },
            'events': {
                'total_events_tested': len(self.event_test_results),
                'failed_events': event_failures
            },
            'functions': {
                'total_functions_tested': len(self.function_test_results),
                'failed_functions': function_failures
            }
        }


class ComparisonEngine:
    """Engine for comparing TR181 nodes from different sources."""
    
    async def compare(self, source1: List[TR181Node], source2: List[TR181Node]) -> ComparisonResult:
        """
        Compare two lists of TR181 nodes and identify differences.
        
        Args:
            source1: First source of TR181 nodes
            source2: Second source of TR181 nodes
            
        Returns:
            ComparisonResult containing all differences and summary statistics
        """
        # Build lookup maps for efficient comparison
        map1 = self._build_node_map(source1)
        map2 = self._build_node_map(source2)
        
        # Find nodes only in source1
        only_in_source1 = self._find_unique_nodes(map1, map2)
        
        # Find nodes only in source2
        only_in_source2 = self._find_unique_nodes(map2, map1)
        
        # Find common nodes with differences
        differences = self._find_differences(map1, map2)
        
        # Calculate summary statistics
        common_paths = set(map1.keys()) & set(map2.keys())
        summary = ComparisonSummary(
            total_nodes_source1=len(source1),
            total_nodes_source2=len(source2),
            common_nodes=len(common_paths),
            differences_count=len(differences)
        )
        
        return ComparisonResult(
            only_in_source1=only_in_source1,
            only_in_source2=only_in_source2,
            differences=differences,
            summary=summary
        )
    
    def _build_node_map(self, nodes: List[TR181Node]) -> Dict[str, TR181Node]:
        """Build a lookup map from node path to node object."""
        return {node.path: node for node in nodes}
    
    def _find_unique_nodes(self, map1: Dict[str, TR181Node], map2: Dict[str, TR181Node]) -> List[TR181Node]:
        """Find nodes that exist in map1 but not in map2."""
        unique_paths = set(map1.keys()) - set(map2.keys())
        return [map1[path] for path in unique_paths]
    
    def _find_differences(self, map1: Dict[str, TR181Node], map2: Dict[str, TR181Node]) -> List[NodeDifference]:
        """Find differences between common nodes in both maps."""
        differences = []
        common_paths = set(map1.keys()) & set(map2.keys())
        
        for path in common_paths:
            node1, node2 = map1[path], map2[path]
            node_differences = self._compare_nodes(node1, node2)
            differences.extend(node_differences)
        
        return differences
    
    def _compare_nodes(self, node1: TR181Node, node2: TR181Node) -> List[NodeDifference]:
        """Compare two nodes and return list of differences."""
        differences = []
        
        # Compare data type
        if node1.data_type != node2.data_type:
            differences.append(NodeDifference(
                path=node1.path,
                property="data_type",
                source1_value=node1.data_type,
                source2_value=node2.data_type,
                severity=Severity.ERROR
            ))
        
        # Compare access level
        if node1.access != node2.access:
            differences.append(NodeDifference(
                path=node1.path,
                property="access",
                source1_value=node1.access.value,
                source2_value=node2.access.value,
                severity=Severity.WARNING
            ))
        
        # Compare values (if both have values)
        if node1.value is not None and node2.value is not None and node1.value != node2.value:
            differences.append(NodeDifference(
                path=node1.path,
                property="value",
                source1_value=node1.value,
                source2_value=node2.value,
                severity=Severity.INFO
            ))
        elif node1.value is not None and node2.value is None:
            differences.append(NodeDifference(
                path=node1.path,
                property="value",
                source1_value=node1.value,
                source2_value=None,
                severity=Severity.INFO
            ))
        elif node1.value is None and node2.value is not None:
            differences.append(NodeDifference(
                path=node1.path,
                property="value",
                source1_value=None,
                source2_value=node2.value,
                severity=Severity.INFO
            ))
        
        # Compare descriptions
        if node1.description != node2.description:
            differences.append(NodeDifference(
                path=node1.path,
                property="description",
                source1_value=node1.description,
                source2_value=node2.description,
                severity=Severity.INFO
            ))
        
        # Compare object status
        if node1.is_object != node2.is_object:
            differences.append(NodeDifference(
                path=node1.path,
                property="is_object",
                source1_value=node1.is_object,
                source2_value=node2.is_object,
                severity=Severity.WARNING
            ))
        
        # Compare custom status
        if node1.is_custom != node2.is_custom:
            differences.append(NodeDifference(
                path=node1.path,
                property="is_custom",
                source1_value=node1.is_custom,
                source2_value=node2.is_custom,
                severity=Severity.INFO
            ))
        
        # Compare value ranges
        if self._value_ranges_differ(node1.value_range, node2.value_range):
            differences.append(NodeDifference(
                path=node1.path,
                property="value_range",
                source1_value=node1.value_range,
                source2_value=node2.value_range,
                severity=Severity.WARNING
            ))
        
        # Compare children lists
        if self._lists_differ(node1.children, node2.children):
            differences.append(NodeDifference(
                path=node1.path,
                property="children",
                source1_value=node1.children,
                source2_value=node2.children,
                severity=Severity.INFO
            ))
        
        # Compare events
        if self._events_differ(node1.events, node2.events):
            differences.append(NodeDifference(
                path=node1.path,
                property="events",
                source1_value=len(node1.events) if node1.events else 0,
                source2_value=len(node2.events) if node2.events else 0,
                severity=Severity.INFO
            ))
        
        # Compare functions
        if self._functions_differ(node1.functions, node2.functions):
            differences.append(NodeDifference(
                path=node1.path,
                property="functions",
                source1_value=len(node1.functions) if node1.functions else 0,
                source2_value=len(node2.functions) if node2.functions else 0,
                severity=Severity.INFO
            ))
        
        return differences
    
    def _value_ranges_differ(self, range1, range2) -> bool:
        """Check if two value ranges are different."""
        if range1 is None and range2 is None:
            return False
        if range1 is None or range2 is None:
            return True
        
        return (
            range1.min_value != range2.min_value or
            range1.max_value != range2.max_value or
            range1.allowed_values != range2.allowed_values or
            range1.pattern != range2.pattern or
            range1.max_length != range2.max_length
        )
    
    def _lists_differ(self, list1, list2) -> bool:
        """Check if two lists are different (handling None values)."""
        if list1 is None and list2 is None:
            return False
        if list1 is None or list2 is None:
            return True
        
        # Convert to sets for comparison (order doesn't matter)
        return set(list1) != set(list2)
    
    def _events_differ(self, events1, events2) -> bool:
        """Check if two event lists are different."""
        if events1 is None and events2 is None:
            return False
        if events1 is None or events2 is None:
            return True
        
        if len(events1) != len(events2):
            return True
        
        # Compare event names and paths
        events1_set = {(e.name, e.path) for e in events1}
        events2_set = {(e.name, e.path) for e in events2}
        return events1_set != events2_set
    
    def _functions_differ(self, functions1, functions2) -> bool:
        """Check if two function lists are different."""
        if functions1 is None and functions2 is None:
            return False
        if functions1 is None or functions2 is None:
            return True
        
        if len(functions1) != len(functions2):
            return True
        
        # Compare function names and paths
        functions1_set = {(f.name, f.path) for f in functions1}
        functions2_set = {(f.name, f.path) for f in functions2}
        return functions1_set != functions2_set


class EnhancedComparisonEngine(ComparisonEngine):
    """Enhanced comparison engine that includes validation and event/function testing."""
    
    def __init__(self):
        """Initialize the enhanced comparison engine with validator."""
        super().__init__()
        self.validator = TR181Validator()
    
    async def compare_with_validation(self, subset_nodes: List[TR181Node], device_nodes: List[TR181Node], 
                                    device_extractor: Optional['HookBasedDeviceExtractor'] = None) -> EnhancedComparisonResult:
        """
        Enhanced comparison that includes validation and event/function testing.
        
        Args:
            subset_nodes: TR181 nodes from subset specification
            device_nodes: TR181 nodes from device implementation
            device_extractor: Optional device extractor for event/function testing
            
        Returns:
            EnhancedComparisonResult with comprehensive comparison, validation, and test results
        """
        # Perform basic comparison
        basic_result = await self.compare(subset_nodes, device_nodes)
        
        # Perform validation on common nodes
        validation_results = await self._validate_node_implementations(subset_nodes, device_nodes)
        
        # Test events and functions if device extractor is available
        event_test_results = []
        function_test_results = []
        
        if device_extractor:
            event_function_tester = EventFunctionTester(device_extractor)
            event_test_results, function_test_results = await self._test_events_and_functions(
                subset_nodes, event_function_tester, device_nodes
            )
        
        return EnhancedComparisonResult(
            basic_comparison=basic_result,
            validation_results=validation_results,
            event_test_results=event_test_results,
            function_test_results=function_test_results
        )
    
    async def _validate_node_implementations(self, subset_nodes: List[TR181Node], 
                                           device_nodes: List[TR181Node]) -> List[Tuple[str, ValidationResult]]:
        """Validate device node implementations against subset specifications."""
        validation_results = []
        device_map = self._build_node_map(device_nodes)
        
        for subset_node in subset_nodes:
            if subset_node.path in device_map:
                device_node = device_map[subset_node.path]
                validation_result = await self._validate_node_implementation(subset_node, device_node)
                validation_results.append((subset_node.path, validation_result))
        
        return validation_results
    
    async def _validate_node_implementation(self, subset_node: TR181Node, device_node: TR181Node) -> ValidationResult:
        """Validate device node implementation against subset specification."""
        result = ValidationResult()
        
        # Validate data type consistency
        if subset_node.data_type != device_node.data_type:
            result.add_error(f"Data type mismatch for {subset_node.path}: expected {subset_node.data_type}, got {device_node.data_type}")
        
        # Validate access level consistency
        if subset_node.access != device_node.access:
            result.add_warning(f"Access level mismatch for {subset_node.path}: expected {subset_node.access.value}, got {device_node.access.value}")
        
        # Validate value against subset constraints
        if subset_node.value_range and device_node.value is not None:
            range_validation = self.validator.validate_node(subset_node, device_node.value)
            result.merge(range_validation)
        
        # Validate data type of actual value
        if device_node.value is not None:
            type_validation = self.validator.validate_node(device_node)
            result.merge(type_validation)
        
        # Validate object consistency
        if subset_node.is_object != device_node.is_object:
            result.add_warning(f"Object type mismatch for {subset_node.path}: expected is_object={subset_node.is_object}, got is_object={device_node.is_object}")
        
        # Validate children consistency for object nodes
        if subset_node.is_object and subset_node.children and device_node.children:
            subset_children = set(subset_node.children)
            device_children = set(device_node.children)
            
            missing_children = subset_children - device_children
            if missing_children:
                result.add_error(f"Missing child nodes for {subset_node.path}: {list(missing_children)}")
            
            extra_children = device_children - subset_children
            if extra_children:
                result.add_warning(f"Extra child nodes for {subset_node.path}: {list(extra_children)}")
        
        return result
    
    async def _test_events_and_functions(self, subset_nodes: List[TR181Node], 
                                       event_function_tester: EventFunctionTester,
                                       device_nodes: List[TR181Node]) -> Tuple[List[EventTestResult], List[FunctionTestResult]]:
        """Test events and functions from subset nodes against device implementation."""
        event_test_results = []
        function_test_results = []
        
        # Collect all events and functions from subset nodes
        all_events = []
        all_functions = []
        
        for node in subset_nodes:
            if node.events:
                all_events.extend(node.events)
            if node.functions:
                all_functions.extend(node.functions)
        
        # Test events
        if all_events:
            event_test_results = await event_function_tester.test_multiple_events(all_events, device_nodes)
        
        # Test functions
        if all_functions:
            function_test_results = await event_function_tester.test_multiple_functions(all_functions, device_nodes)
        
        return event_test_results, function_test_results
    
    def get_enhanced_summary(self, result: EnhancedComparisonResult) -> Dict[str, Any]:
        """Generate a comprehensive summary of enhanced comparison results."""
        basic_summary = result.get_summary()
        
        # Add detailed validation breakdown
        validation_details = {}
        for path, validation_result in result.validation_results:
            if not validation_result.is_valid or validation_result.warnings:
                validation_details[path] = {
                    'is_valid': validation_result.is_valid,
                    'errors': validation_result.errors,
                    'warnings': validation_result.warnings
                }
        
        # Add event test details
        event_details = {}
        for event_result in result.event_test_results:
            if event_result.status.value in ['failed', 'error']:
                event_details[event_result.event_name] = {
                    'status': event_result.status.value,
                    'message': event_result.message,
                    'subscription_test': event_result.subscription_test
                }
        
        # Add function test details
        function_details = {}
        for function_result in result.function_test_results:
            if function_result.status.value in ['failed', 'error']:
                function_details[function_result.function_name] = {
                    'status': function_result.status.value,
                    'message': function_result.message,
                    'execution_test': function_result.execution_test
                }
        
        # Calculate overall compliance score
        total_checks = (
            len(result.validation_results) + 
            len(result.event_test_results) + 
            len(result.function_test_results)
        )
        
        passed_checks = (
            sum(1 for _, vr in result.validation_results if vr.is_valid) +
            sum(1 for er in result.event_test_results if er.status.value == 'passed') +
            sum(1 for fr in result.function_test_results if fr.status.value == 'passed')
        )
        
        compliance_score = passed_checks / total_checks if total_checks > 0 else 1.0
        
        enhanced_summary = {
            **basic_summary,
            'compliance': {
                'score': compliance_score,
                'total_checks': total_checks,
                'passed_checks': passed_checks,
                'failed_checks': total_checks - passed_checks
            },
            'details': {
                'validation_issues': validation_details,
                'event_failures': event_details,
                'function_failures': function_details
            }
        }
        
        return enhanced_summary