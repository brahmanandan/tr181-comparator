"""Unit tests for the event and function testing framework."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from tr181_comparator.event_function_tester import (
    EventFunctionTester, EventTestResult, FunctionTestResult, EventFunctionTestResult
)
from tr181_comparator.models import (
    TR181Node, TR181Event, TR181Function, AccessLevel
)
from tr181_comparator.validation import ValidationResult
from tr181_comparator.extractors import HookBasedDeviceExtractor
from tr181_comparator.hooks import DeviceConnectionHook, DeviceConfig


class MockDeviceHook(DeviceConnectionHook):
    """Mock device hook for testing."""
    
    def __init__(self):
        self.connected = False
        self.subscribe_results = {}
        self.function_results = {}
        self.should_raise_error = False
        self.error_message = "Mock error"
    
    async def connect(self, config: DeviceConfig) -> bool:
        self.connected = True
        return True
    
    async def disconnect(self) -> None:
        self.connected = False
    
    async def get_parameter_names(self, path_prefix: str = "Device.") -> List[str]:
        return ["Device.Test.Parameter1", "Device.Test.Parameter2"]
    
    async def get_parameter_values(self, paths: List[str]) -> Dict[str, Any]:
        return {path: f"value_{path.split('.')[-1]}" for path in paths}
    
    async def get_parameter_attributes(self, paths: List[str]) -> Dict[str, Dict[str, Any]]:
        return {path: {"type": "string", "access": "read-write"} for path in paths}
    
    async def set_parameter_values(self, values: Dict[str, Any]) -> bool:
        return True
    
    async def subscribe_to_event(self, event_path: str) -> bool:
        if self.should_raise_error:
            raise Exception(self.error_message)
        return self.subscribe_results.get(event_path, True)
    
    async def call_function(self, function_path: str, input_params: Dict[str, Any]) -> Dict[str, Any]:
        if self.should_raise_error:
            raise Exception(self.error_message)
        return self.function_results.get(function_path, {"result": "success"})


@pytest.fixture
def mock_device_hook():
    """Create a mock device hook."""
    return MockDeviceHook()


@pytest.fixture
def mock_device_extractor(mock_device_hook):
    """Create a mock device extractor."""
    config = DeviceConfig(
        type="test",
        endpoint="http://test.device",
        authentication={}
    )
    extractor = HookBasedDeviceExtractor(mock_device_hook, config)
    return extractor


@pytest.fixture
def sample_device_nodes():
    """Create sample device nodes for testing."""
    return [
        TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="TestNetwork"
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True
        ),
        TR181Node(
            path="Device.WiFi.Status",
            name="Status",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="Up"
        )
    ]


@pytest.fixture
def sample_event():
    """Create a sample TR181 event."""
    return TR181Event(
        name="WiFiChannelChange",
        path="Device.WiFi.Radio.1.ChannelChangeEvent",
        parameters=["Device.WiFi.Radio.1.Channel", "Device.WiFi.Radio.1.SSID"],
        description="Event triggered when WiFi channel changes"
    )


@pytest.fixture
def sample_function():
    """Create a sample TR181 function."""
    return TR181Function(
        name="SetWiFiChannel",
        path="Device.WiFi.Radio.1.SetChannel",
        input_parameters=["Device.WiFi.Radio.1.Channel"],
        output_parameters=["Device.WiFi.Status"],
        description="Function to set WiFi channel"
    )


@pytest.fixture
def event_function_tester(mock_device_extractor):
    """Create an EventFunctionTester instance."""
    return EventFunctionTester(mock_device_extractor)


class TestEventFunctionTester:
    """Test cases for EventFunctionTester class."""
    
    def test_init(self, event_function_tester, mock_device_extractor):
        """Test EventFunctionTester initialization."""
        assert event_function_tester.device_extractor == mock_device_extractor
        assert event_function_tester.hook == mock_device_extractor.hook
        assert event_function_tester._device_nodes_cache is None
    
    @pytest.mark.asyncio
    async def test_test_event_implementation_success(self, event_function_tester, sample_event, sample_device_nodes):
        """Test successful event implementation testing."""
        # Mock the device extractor to return our sample nodes
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            result = await event_function_tester.test_event_implementation(sample_event)
        
        assert isinstance(result, EventTestResult)
        assert result.event_name == sample_event.name
        assert result.event_path == sample_event.path
        assert result.status == EventFunctionTestResult.PASSED
        assert result.parameter_validation.is_valid
        assert result.subscription_test is True
        assert result.execution_time is not None
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_test_event_implementation_missing_parameters(self, event_function_tester, sample_device_nodes):
        """Test event implementation with missing parameters."""
        # Create an event with parameters not in device nodes
        event = TR181Event(
            name="MissingParamEvent",
            path="Device.Test.MissingEvent",
            parameters=["Device.Missing.Parameter1", "Device.Missing.Parameter2"]
        )
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            result = await event_function_tester.test_event_implementation(event)
        
        assert result.status == EventFunctionTestResult.FAILED
        assert not result.parameter_validation.is_valid
        assert len(result.parameter_validation.errors) == 2
    
    @pytest.mark.asyncio
    async def test_test_event_implementation_subscription_failure(self, event_function_tester, sample_event, sample_device_nodes, mock_device_hook):
        """Test event implementation with subscription failure."""
        # Configure mock to fail subscription
        mock_device_hook.subscribe_results[sample_event.path] = False
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            result = await event_function_tester.test_event_implementation(sample_event)
        
        assert result.status == EventFunctionTestResult.PASSED  # Parameters are valid, so still passes
        assert result.parameter_validation.is_valid
        assert result.subscription_test is False
    
    @pytest.mark.asyncio
    async def test_test_event_implementation_subscription_error(self, event_function_tester, sample_event, sample_device_nodes, mock_device_hook):
        """Test event implementation with subscription error."""
        # Configure mock to raise error on subscription
        mock_device_hook.should_raise_error = True
        mock_device_hook.error_message = "Subscription failed"
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            result = await event_function_tester.test_event_implementation(sample_event)
        
        assert result.status == EventFunctionTestResult.ERROR  # Subscription error occurred
        assert result.parameter_validation.is_valid
        assert result.subscription_test is False
        assert "Subscription failed" in str(result.details.get("subscription_error", ""))
    
    @pytest.mark.asyncio
    async def test_test_function_implementation_success(self, event_function_tester, sample_function, sample_device_nodes):
        """Test successful function implementation testing."""
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            result = await event_function_tester.test_function_implementation(sample_function)
        
        assert isinstance(result, FunctionTestResult)
        assert result.function_name == sample_function.name
        assert result.function_path == sample_function.path
        assert result.status == EventFunctionTestResult.PASSED
        assert result.input_validation.is_valid
        assert result.output_validation.is_valid
        assert result.execution_test is True
        assert result.execution_time is not None
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_test_function_implementation_missing_input_parameters(self, event_function_tester, sample_device_nodes):
        """Test function implementation with missing input parameters."""
        function = TR181Function(
            name="MissingInputFunction",
            path="Device.Test.MissingFunction",
            input_parameters=["Device.Missing.Input"],
            output_parameters=["Device.WiFi.Status"]
        )
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            result = await event_function_tester.test_function_implementation(function)
        
        assert result.status == EventFunctionTestResult.FAILED
        assert not result.input_validation.is_valid
        assert result.output_validation.is_valid
        assert len(result.input_validation.errors) == 1
    
    @pytest.mark.asyncio
    async def test_test_function_implementation_missing_output_parameters(self, event_function_tester, sample_device_nodes):
        """Test function implementation with missing output parameters."""
        function = TR181Function(
            name="MissingOutputFunction",
            path="Device.Test.MissingFunction",
            input_parameters=["Device.WiFi.Radio.1.Channel"],
            output_parameters=["Device.Missing.Output"]
        )
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            result = await event_function_tester.test_function_implementation(function)
        
        assert result.status == EventFunctionTestResult.FAILED
        assert result.input_validation.is_valid
        assert not result.output_validation.is_valid
        assert len(result.output_validation.errors) == 1
    
    @pytest.mark.asyncio
    async def test_test_function_implementation_execution_failure(self, event_function_tester, sample_function, sample_device_nodes, mock_device_hook):
        """Test function implementation with execution failure."""
        # Configure mock to fail function execution
        mock_device_hook.function_results[sample_function.path] = {}
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            result = await event_function_tester.test_function_implementation(sample_function)
        
        assert result.status == EventFunctionTestResult.PASSED  # Parameters are valid
        assert result.input_validation.is_valid
        assert result.output_validation.is_valid
        assert result.execution_test is False
    
    @pytest.mark.asyncio
    async def test_test_multiple_events(self, event_function_tester, sample_device_nodes):
        """Test testing multiple events."""
        events = [
            TR181Event(
                name="Event1",
                path="Device.Test.Event1",
                parameters=["Device.WiFi.Radio.1.Channel"]
            ),
            TR181Event(
                name="Event2",
                path="Device.Test.Event2",
                parameters=["Device.WiFi.Radio.1.SSID"]
            )
        ]
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            results = await event_function_tester.test_multiple_events(events)
        
        assert len(results) == 2
        assert all(isinstance(r, EventTestResult) for r in results)
        assert results[0].event_name == "Event1"
        assert results[1].event_name == "Event2"
    
    @pytest.mark.asyncio
    async def test_test_multiple_functions(self, event_function_tester, sample_device_nodes):
        """Test testing multiple functions."""
        functions = [
            TR181Function(
                name="Function1",
                path="Device.Test.Function1",
                input_parameters=["Device.WiFi.Radio.1.Channel"],
                output_parameters=["Device.WiFi.Status"]
            ),
            TR181Function(
                name="Function2",
                path="Device.Test.Function2",
                input_parameters=["Device.WiFi.Radio.1.SSID"],
                output_parameters=["Device.WiFi.Status"]
            )
        ]
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            results = await event_function_tester.test_multiple_functions(functions)
        
        assert len(results) == 2
        assert all(isinstance(r, FunctionTestResult) for r in results)
        assert results[0].function_name == "Function1"
        assert results[1].function_name == "Function2"
    
    @pytest.mark.asyncio
    async def test_test_node_events_and_functions(self, event_function_tester, sample_device_nodes):
        """Test testing events and functions associated with a node."""
        node = TR181Node(
            path="Device.WiFi.Radio.1",
            name="Radio",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            events=[
                TR181Event(
                    name="ChannelChange",
                    path="Device.WiFi.Radio.1.ChannelChangeEvent",
                    parameters=["Device.WiFi.Radio.1.Channel"]
                )
            ],
            functions=[
                TR181Function(
                    name="SetChannel",
                    path="Device.WiFi.Radio.1.SetChannel",
                    input_parameters=["Device.WiFi.Radio.1.Channel"],
                    output_parameters=["Device.WiFi.Status"]
                )
            ]
        )
        
        with patch.object(event_function_tester, '_get_device_nodes', return_value=sample_device_nodes):
            event_results, function_results = await event_function_tester.test_node_events_and_functions(node)
        
        assert len(event_results) == 1
        assert len(function_results) == 1
        assert event_results[0].event_name == "ChannelChange"
        assert function_results[0].function_name == "SetChannel"
    
    def test_get_test_summary(self, event_function_tester):
        """Test test summary generation."""
        event_results = [
            EventTestResult(
                event_name="Event1",
                event_path="Device.Test.Event1",
                status=EventFunctionTestResult.PASSED,
                message="Test passed",
                parameter_validation=ValidationResult(),
                subscription_test=True,
                execution_time=0.1
            ),
            EventTestResult(
                event_name="Event2",
                event_path="Device.Test.Event2",
                status=EventFunctionTestResult.FAILED,
                message="Test failed",
                parameter_validation=ValidationResult(),
                subscription_test=False,
                execution_time=0.2
            )
        ]
        
        function_results = [
            FunctionTestResult(
                function_name="Function1",
                function_path="Device.Test.Function1",
                status=EventFunctionTestResult.PASSED,
                message="Test passed",
                input_validation=ValidationResult(),
                output_validation=ValidationResult(),
                execution_test=True,
                execution_time=0.3
            )
        ]
        
        summary = event_function_tester.get_test_summary(event_results, function_results)
        
        assert summary["events"]["total"] == 2
        assert summary["events"]["passed"] == 1
        assert summary["events"]["failed"] == 1
        assert summary["events"]["subscription_success"] == 1
        assert abs(summary["events"]["avg_execution_time"] - 0.15) < 0.001
        
        assert summary["functions"]["total"] == 1
        assert summary["functions"]["passed"] == 1
        assert summary["functions"]["execution_success"] == 1
        
        assert summary["overall"]["total_tests"] == 3
        assert summary["overall"]["total_passed"] == 2
        assert summary["overall"]["success_rate"] == 2/3
    
    @pytest.mark.asyncio
    async def test_get_device_nodes_caching(self, event_function_tester, sample_device_nodes):
        """Test that device nodes are cached properly."""
        with patch.object(event_function_tester.device_extractor, 'extract', return_value=sample_device_nodes) as mock_extract:
            # First call should extract nodes
            nodes1 = await event_function_tester._get_device_nodes()
            assert mock_extract.call_count == 1
            assert nodes1 == sample_device_nodes
            
            # Second call should use cache
            nodes2 = await event_function_tester._get_device_nodes()
            assert mock_extract.call_count == 1  # Still only called once
            assert nodes2 == sample_device_nodes
    
    @pytest.mark.asyncio
    async def test_validate_event_parameters_with_warnings(self, event_function_tester):
        """Test event parameter validation with warnings for inappropriate access levels."""
        device_nodes = [
            TR181Node(
                path="Device.Test.WriteOnlyParam",
                name="WriteOnlyParam",
                data_type="string",
                access=AccessLevel.WRITE_ONLY,
                value="test"
            ),
            TR181Node(
                path="Device.Test.ReadWriteParam",
                name="ReadWriteParam",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="test"
            )
        ]
        
        event = TR181Event(
            name="TestEvent",
            path="Device.Test.Event",
            parameters=["Device.Test.WriteOnlyParam", "Device.Test.ReadWriteParam"]
        )
        
        result = await event_function_tester._validate_event_parameters(event, device_nodes)
        
        assert result.is_valid
        assert len(result.warnings) == 1
        assert "write-only" in result.warnings[0]
    
    @pytest.mark.asyncio
    async def test_validate_function_parameters_with_warnings(self, event_function_tester):
        """Test function parameter validation with warnings for inappropriate access levels."""
        device_nodes = [
            TR181Node(
                path="Device.Test.ReadOnlyInput",
                name="ReadOnlyInput",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="test"
            ),
            TR181Node(
                path="Device.Test.WriteOnlyOutput",
                name="WriteOnlyOutput",
                data_type="string",
                access=AccessLevel.WRITE_ONLY,
                value="test"
            )
        ]
        
        function = TR181Function(
            name="TestFunction",
            path="Device.Test.Function",
            input_parameters=["Device.Test.ReadOnlyInput"],
            output_parameters=["Device.Test.WriteOnlyOutput"]
        )
        
        input_result = await event_function_tester._validate_function_input_parameters(function, device_nodes)
        output_result = await event_function_tester._validate_function_output_parameters(function, device_nodes)
        
        assert input_result.is_valid
        assert len(input_result.warnings) == 1
        assert "read-only" in input_result.warnings[0]
        
        assert output_result.is_valid
        assert len(output_result.warnings) == 1
        assert "write-only" in output_result.warnings[0]
    
    @pytest.mark.asyncio
    async def test_error_handling_in_event_test(self, event_function_tester, sample_event):
        """Test error handling during event testing."""
        # Mock _get_device_nodes to raise an exception
        with patch.object(event_function_tester, '_get_device_nodes', side_effect=Exception("Device extraction failed")):
            result = await event_function_tester.test_event_implementation(sample_event)
        
        assert result.status == EventFunctionTestResult.ERROR
        assert "Device extraction failed" in result.message
        assert "error" in result.details
    
    @pytest.mark.asyncio
    async def test_error_handling_in_function_test(self, event_function_tester, sample_function):
        """Test error handling during function testing."""
        # Mock _get_device_nodes to raise an exception
        with patch.object(event_function_tester, '_get_device_nodes', side_effect=Exception("Device extraction failed")):
            result = await event_function_tester.test_function_implementation(sample_function)
        
        assert result.status == EventFunctionTestResult.ERROR
        assert "Device extraction failed" in result.message
        assert "error" in result.details


class TestEventTestResult:
    """Test cases for EventTestResult dataclass."""
    
    def test_event_test_result_creation(self):
        """Test EventTestResult creation."""
        validation_result = ValidationResult()
        result = EventTestResult(
            event_name="TestEvent",
            event_path="Device.Test.Event",
            status=EventFunctionTestResult.PASSED,
            message="Test passed",
            parameter_validation=validation_result,
            subscription_test=True,
            execution_time=0.5,
            details={"test": "data"}
        )
        
        assert result.event_name == "TestEvent"
        assert result.event_path == "Device.Test.Event"
        assert result.status == EventFunctionTestResult.PASSED
        assert result.message == "Test passed"
        assert result.parameter_validation == validation_result
        assert result.subscription_test is True
        assert result.execution_time == 0.5
        assert result.details == {"test": "data"}


class TestFunctionTestResult:
    """Test cases for FunctionTestResult dataclass."""
    
    def test_function_test_result_creation(self):
        """Test FunctionTestResult creation."""
        input_validation = ValidationResult()
        output_validation = ValidationResult()
        result = FunctionTestResult(
            function_name="TestFunction",
            function_path="Device.Test.Function",
            status=EventFunctionTestResult.PASSED,
            message="Test passed",
            input_validation=input_validation,
            output_validation=output_validation,
            execution_test=True,
            execution_time=0.7,
            details={"test": "data"}
        )
        
        assert result.function_name == "TestFunction"
        assert result.function_path == "Device.Test.Function"
        assert result.status == EventFunctionTestResult.PASSED
        assert result.message == "Test passed"
        assert result.input_validation == input_validation
        assert result.output_validation == output_validation
        assert result.execution_test is True
        assert result.execution_time == 0.7
        assert result.details == {"test": "data"}


class TestEventFunctionTestResult:
    """Test cases for EventFunctionTestResult enum."""
    
    def test_event_function_test_result_values(self):
        """Test EventFunctionTestResult enum values."""
        assert EventFunctionTestResult.PASSED.value == "passed"
        assert EventFunctionTestResult.FAILED.value == "failed"
        assert EventFunctionTestResult.SKIPPED.value == "skipped"
        assert EventFunctionTestResult.ERROR.value == "error"