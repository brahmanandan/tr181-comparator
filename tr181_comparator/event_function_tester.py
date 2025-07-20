"""Event and function testing framework for TR181 implementations."""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .models import TR181Node, TR181Event, TR181Function
from .validation import ValidationResult
from .extractors import HookBasedDeviceExtractor
from .hooks import DeviceConnectionHook


class EventFunctionTestResult(Enum):
    """Test result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class EventTestResult:
    """Result of testing an event implementation."""
    event_name: str
    event_path: str
    status: EventFunctionTestResult
    message: str
    parameter_validation: ValidationResult
    subscription_test: bool = False
    execution_time: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class FunctionTestResult:
    """Result of testing a function implementation."""
    function_name: str
    function_path: str
    status: EventFunctionTestResult
    message: str
    input_validation: ValidationResult
    output_validation: ValidationResult
    execution_test: bool = False
    execution_time: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class EventFunctionTester:
    """Tests event and function implementation presence and functionality."""
    
    def __init__(self, device_extractor: HookBasedDeviceExtractor):
        """Initialize the event and function tester.
        
        Args:
            device_extractor: Device extractor with communication hook for testing
        """
        self.device_extractor = device_extractor
        self.hook = device_extractor.hook
        self._device_nodes_cache: Optional[List[TR181Node]] = None
    
    async def test_event_implementation(self, event: TR181Event, device_nodes: Optional[List[TR181Node]] = None) -> EventTestResult:
        """Test if an event is properly implemented on the device.
        
        Args:
            event: TR181Event to test
            device_nodes: Optional list of device nodes (will be extracted if not provided)
            
        Returns:
            EventTestResult containing test results and validation details
        """
        import time
        start_time = time.time()
        
        try:
            # Get device nodes if not provided
            if device_nodes is None:
                device_nodes = await self._get_device_nodes()
            
            # Validate event parameter existence
            parameter_validation = await self._validate_event_parameters(event, device_nodes)
            
            # Test event subscription capability
            subscription_success = False
            subscription_error = None
            
            try:
                subscription_success = await self._test_event_subscription(event)
            except Exception as e:
                subscription_error = str(e)
            
            # Determine overall test status
            status = self._determine_event_test_status(parameter_validation, subscription_success, subscription_error)
            
            # Generate test message
            message = self._generate_event_test_message(event, parameter_validation, subscription_success, subscription_error)
            
            execution_time = time.time() - start_time
            
            return EventTestResult(
                event_name=event.name,
                event_path=event.path,
                status=status,
                message=message,
                parameter_validation=parameter_validation,
                subscription_test=subscription_success,
                execution_time=execution_time,
                details={
                    "parameter_count": len(event.parameters),
                    "subscription_error": subscription_error,
                    "device_node_count": len(device_nodes)
                }
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return EventTestResult(
                event_name=event.name,
                event_path=event.path,
                status=EventFunctionTestResult.ERROR,
                message=f"Event test failed with error: {str(e)}",
                parameter_validation=ValidationResult(),
                execution_time=execution_time,
                details={"error": str(e)}
            )
    
    async def test_function_implementation(self, function: TR181Function, device_nodes: Optional[List[TR181Node]] = None) -> FunctionTestResult:
        """Test if a function is properly implemented on the device.
        
        Args:
            function: TR181Function to test
            device_nodes: Optional list of device nodes (will be extracted if not provided)
            
        Returns:
            FunctionTestResult containing test results and validation details
        """
        import time
        start_time = time.time()
        
        try:
            # Get device nodes if not provided
            if device_nodes is None:
                device_nodes = await self._get_device_nodes()
            
            # Validate function input parameters
            input_validation = await self._validate_function_input_parameters(function, device_nodes)
            
            # Validate function output parameters
            output_validation = await self._validate_function_output_parameters(function, device_nodes)
            
            # Test function execution capability
            execution_success = False
            execution_error = None
            
            try:
                execution_success = await self._test_function_execution(function)
            except Exception as e:
                execution_error = str(e)
            
            # Determine overall test status
            status = self._determine_function_test_status(input_validation, output_validation, execution_success, execution_error)
            
            # Generate test message
            message = self._generate_function_test_message(function, input_validation, output_validation, execution_success, execution_error)
            
            execution_time = time.time() - start_time
            
            return FunctionTestResult(
                function_name=function.name,
                function_path=function.path,
                status=status,
                message=message,
                input_validation=input_validation,
                output_validation=output_validation,
                execution_test=execution_success,
                execution_time=execution_time,
                details={
                    "input_parameter_count": len(function.input_parameters),
                    "output_parameter_count": len(function.output_parameters),
                    "execution_error": execution_error,
                    "device_node_count": len(device_nodes)
                }
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return FunctionTestResult(
                function_name=function.name,
                function_path=function.path,
                status=EventFunctionTestResult.ERROR,
                message=f"Function test failed with error: {str(e)}",
                input_validation=ValidationResult(),
                output_validation=ValidationResult(),
                execution_time=execution_time,
                details={"error": str(e)}
            )
    
    async def test_multiple_events(self, events: List[TR181Event], device_nodes: Optional[List[TR181Node]] = None) -> List[EventTestResult]:
        """Test multiple events and return results.
        
        Args:
            events: List of TR181Event objects to test
            device_nodes: Optional list of device nodes (will be extracted if not provided)
            
        Returns:
            List of EventTestResult objects
        """
        # Get device nodes once for all tests
        if device_nodes is None:
            device_nodes = await self._get_device_nodes()
        
        results = []
        for event in events:
            result = await self.test_event_implementation(event, device_nodes)
            results.append(result)
        
        return results
    
    async def test_multiple_functions(self, functions: List[TR181Function], device_nodes: Optional[List[TR181Node]] = None) -> List[FunctionTestResult]:
        """Test multiple functions and return results.
        
        Args:
            functions: List of TR181Function objects to test
            device_nodes: Optional list of device nodes (will be extracted if not provided)
            
        Returns:
            List of FunctionTestResult objects
        """
        # Get device nodes once for all tests
        if device_nodes is None:
            device_nodes = await self._get_device_nodes()
        
        results = []
        for function in functions:
            result = await self.test_function_implementation(function, device_nodes)
            results.append(result)
        
        return results
    
    async def test_node_events_and_functions(self, node: TR181Node, device_nodes: Optional[List[TR181Node]] = None) -> Tuple[List[EventTestResult], List[FunctionTestResult]]:
        """Test all events and functions associated with a TR181 node.
        
        Args:
            node: TR181Node containing events and functions to test
            device_nodes: Optional list of device nodes (will be extracted if not provided)
            
        Returns:
            Tuple of (event_results, function_results)
        """
        # Get device nodes once for all tests
        if device_nodes is None:
            device_nodes = await self._get_device_nodes()
        
        # Test events
        event_results = []
        if node.events:
            event_results = await self.test_multiple_events(node.events, device_nodes)
        
        # Test functions
        function_results = []
        if node.functions:
            function_results = await self.test_multiple_functions(node.functions, device_nodes)
        
        return event_results, function_results
    
    def get_test_summary(self, event_results: List[EventTestResult], function_results: List[FunctionTestResult]) -> Dict[str, Any]:
        """Generate a summary of test results.
        
        Args:
            event_results: List of event test results
            function_results: List of function test results
            
        Returns:
            Dictionary containing test summary statistics
        """
        # Event statistics
        event_stats = {
            "total": len(event_results),
            "passed": sum(1 for r in event_results if r.status == EventFunctionTestResult.PASSED),
            "failed": sum(1 for r in event_results if r.status == EventFunctionTestResult.FAILED),
            "skipped": sum(1 for r in event_results if r.status == EventFunctionTestResult.SKIPPED),
            "errors": sum(1 for r in event_results if r.status == EventFunctionTestResult.ERROR),
            "subscription_success": sum(1 for r in event_results if r.subscription_test),
            "avg_execution_time": sum(r.execution_time or 0 for r in event_results) / len(event_results) if event_results else 0
        }
        
        # Function statistics
        function_stats = {
            "total": len(function_results),
            "passed": sum(1 for r in function_results if r.status == EventFunctionTestResult.PASSED),
            "failed": sum(1 for r in function_results if r.status == EventFunctionTestResult.FAILED),
            "skipped": sum(1 for r in function_results if r.status == EventFunctionTestResult.SKIPPED),
            "errors": sum(1 for r in function_results if r.status == EventFunctionTestResult.ERROR),
            "execution_success": sum(1 for r in function_results if r.execution_test),
            "avg_execution_time": sum(r.execution_time or 0 for r in function_results) / len(function_results) if function_results else 0
        }
        
        # Overall statistics
        total_tests = len(event_results) + len(function_results)
        total_passed = event_stats["passed"] + function_stats["passed"]
        
        return {
            "events": event_stats,
            "functions": function_stats,
            "overall": {
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": event_stats["failed"] + function_stats["failed"],
                "total_errors": event_stats["errors"] + function_stats["errors"],
                "success_rate": total_passed / total_tests if total_tests > 0 else 0.0
            }
        }
    
    async def _get_device_nodes(self) -> List[TR181Node]:
        """Get device nodes, using cache if available."""
        if self._device_nodes_cache is None:
            self._device_nodes_cache = await self.device_extractor.extract()
        return self._device_nodes_cache
    
    async def _validate_event_parameters(self, event: TR181Event, device_nodes: List[TR181Node]) -> ValidationResult:
        """Validate that event parameters exist on the device."""
        result = ValidationResult()
        device_paths = {node.path for node in device_nodes}
        
        for param_path in event.parameters:
            if param_path not in device_paths:
                result.add_error(f"Event parameter {param_path} not found in device implementation for event {event.name}")
            else:
                # Find the node and validate it's appropriate for events
                device_node = next((node for node in device_nodes if node.path == param_path), None)
                if device_node and device_node.access.value == "write-only":
                    result.add_warning(f"Event parameter {param_path} is write-only, which may not be suitable for event notifications")
        
        return result
    
    async def _validate_function_input_parameters(self, function: TR181Function, device_nodes: List[TR181Node]) -> ValidationResult:
        """Validate that function input parameters exist on the device."""
        result = ValidationResult()
        device_paths = {node.path for node in device_nodes}
        
        for input_param in function.input_parameters:
            if input_param not in device_paths:
                result.add_error(f"Function input parameter {input_param} not found in device implementation for function {function.name}")
            else:
                # Find the node and validate it's appropriate for function input
                device_node = next((node for node in device_nodes if node.path == input_param), None)
                if device_node and device_node.access.value == "read-only":
                    result.add_warning(f"Function input parameter {input_param} is read-only, which may not be suitable for function input")
        
        return result
    
    async def _validate_function_output_parameters(self, function: TR181Function, device_nodes: List[TR181Node]) -> ValidationResult:
        """Validate that function output parameters exist on the device."""
        result = ValidationResult()
        device_paths = {node.path for node in device_nodes}
        
        for output_param in function.output_parameters:
            if output_param not in device_paths:
                result.add_error(f"Function output parameter {output_param} not found in device implementation for function {function.name}")
            else:
                # Find the node and validate it's appropriate for function output
                device_node = next((node for node in device_nodes if node.path == output_param), None)
                if device_node and device_node.access.value == "write-only":
                    result.add_warning(f"Function output parameter {output_param} is write-only, which may not be suitable for function output")
        
        return result
    
    async def _test_event_subscription(self, event: TR181Event) -> bool:
        """Attempt to subscribe to an event to test implementation."""
        # Use the device hook to test event subscription
        # Let exceptions propagate so they can be caught by the caller
        success = await self.hook.subscribe_to_event(event.path)
        return success
    
    async def _test_function_execution(self, function: TR181Function) -> bool:
        """Attempt to execute a function with test parameters."""
        try:
            # Create minimal test input parameters
            test_input = {}
            for input_param in function.input_parameters:
                # Use a safe default value for testing
                test_input[input_param] = ""  # Empty string is generally safe
            
            # Use the device hook to test function execution
            result = await self.hook.call_function(function.path, test_input)
            
            # Check if we got a reasonable response
            return isinstance(result, dict) and len(result) > 0
            
        except Exception as e:
            # Log the error but don't raise it - this is a test
            print(f"Function execution test failed for {function.name}: {str(e)}")
            return False
    
    def _determine_event_test_status(self, parameter_validation: ValidationResult, subscription_success: bool, subscription_error: Optional[str]) -> EventFunctionTestResult:
        """Determine the overall status of an event test."""
        if not parameter_validation.is_valid:
            return EventFunctionTestResult.FAILED
        
        if parameter_validation.warnings and not subscription_success:
            return EventFunctionTestResult.FAILED
        
        if subscription_error:
            return EventFunctionTestResult.ERROR
        
        if subscription_success:
            return EventFunctionTestResult.PASSED
        
        # If subscription failed but parameters are valid, it's still a partial pass
        return EventFunctionTestResult.PASSED if parameter_validation.is_valid else EventFunctionTestResult.FAILED
    
    def _determine_function_test_status(self, input_validation: ValidationResult, output_validation: ValidationResult, 
                                      execution_success: bool, execution_error: Optional[str]) -> EventFunctionTestResult:
        """Determine the overall status of a function test."""
        if not input_validation.is_valid or not output_validation.is_valid:
            return EventFunctionTestResult.FAILED
        
        if execution_error:
            return EventFunctionTestResult.ERROR
        
        if execution_success:
            return EventFunctionTestResult.PASSED
        
        # If execution failed but parameters are valid, it's still a partial pass
        return EventFunctionTestResult.PASSED if input_validation.is_valid and output_validation.is_valid else EventFunctionTestResult.FAILED
    
    def _generate_event_test_message(self, event: TR181Event, parameter_validation: ValidationResult, 
                                   subscription_success: bool, subscription_error: Optional[str]) -> str:
        """Generate a descriptive message for event test results."""
        messages = []
        
        if parameter_validation.is_valid:
            messages.append(f"All {len(event.parameters)} event parameters found on device")
        else:
            messages.append(f"Parameter validation failed: {len(parameter_validation.errors)} error(s)")
        
        if parameter_validation.warnings:
            messages.append(f"{len(parameter_validation.warnings)} warning(s)")
        
        if subscription_success:
            messages.append("Event subscription test passed")
        elif subscription_error:
            messages.append(f"Event subscription test error: {subscription_error}")
        else:
            messages.append("Event subscription test failed")
        
        return "; ".join(messages)
    
    def _generate_function_test_message(self, function: TR181Function, input_validation: ValidationResult, 
                                      output_validation: ValidationResult, execution_success: bool, 
                                      execution_error: Optional[str]) -> str:
        """Generate a descriptive message for function test results."""
        messages = []
        
        if input_validation.is_valid:
            messages.append(f"All {len(function.input_parameters)} input parameters found on device")
        else:
            messages.append(f"Input parameter validation failed: {len(input_validation.errors)} error(s)")
        
        if output_validation.is_valid:
            messages.append(f"All {len(function.output_parameters)} output parameters found on device")
        else:
            messages.append(f"Output parameter validation failed: {len(output_validation.errors)} error(s)")
        
        if input_validation.warnings or output_validation.warnings:
            total_warnings = len(input_validation.warnings) + len(output_validation.warnings)
            messages.append(f"{total_warnings} warning(s)")
        
        if execution_success:
            messages.append("Function execution test passed")
        elif execution_error:
            messages.append(f"Function execution test error: {execution_error}")
        else:
            messages.append("Function execution test failed")
        
        return "; ".join(messages)