"""Integration tests for enhanced comparison engine with validation and event/function testing."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import List

from tr181_comparator.models import (
    TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function, Severity
)
from tr181_comparator.comparison import EnhancedComparisonEngine, EnhancedComparisonResult
from tr181_comparator.validation import ValidationResult
from tr181_comparator.event_function_tester import EventTestResult, FunctionTestResult, EventFunctionTestResult
from tr181_comparator.extractors import HookBasedDeviceExtractor
from tr181_comparator.hooks import DeviceConnectionHook, DeviceConfig


class MockDeviceHook(DeviceConnectionHook):
    """Mock device hook for testing."""
    
    def __init__(self):
        self.connected = False
        self.parameters = {}
        self.attributes = {}
    
    async def connect(self, config) -> bool:
        self.connected = True
        return True
    
    async def disconnect(self) -> None:
        self.connected = False
    
    async def get_parameter_names(self, path_prefix: str = "Device.") -> List[str]:
        return [
            "Device.WiFi.Radio.1.Channel",
            "Device.WiFi.Radio.1.SSID",
            "Device.WiFi.AccessPoint.1.Enable"
        ]
    
    async def get_parameter_values(self, paths: List[str]) -> dict:
        return {path: f"value_for_{path.split('.')[-1]}" for path in paths}
    
    async def get_parameter_attributes(self, paths: List[str]) -> dict:
        return {
            path: {
                "type": "string",
                "access": "read-write",
                "notification": "passive"
            } for path in paths
        }
    
    async def set_parameter_values(self, values: dict) -> bool:
        return True
    
    async def subscribe_to_event(self, event_path: str) -> bool:
        return True
    
    async def call_function(self, function_path: str, input_params: dict) -> dict:
        return {"result": "success", "output": {}}


@pytest.fixture
def mock_device_extractor():
    """Create a mock device extractor for testing."""
    hook = MockDeviceHook()
    device_config = DeviceConfig(
        type="mock",
        endpoint="http://mock-device:8080",
        authentication={},
        timeout=30,
        retry_count=3
    )
    extractor = HookBasedDeviceExtractor(hook, device_config)
    return extractor


@pytest.fixture
def sample_subset_nodes():
    """Create sample subset nodes for testing."""
    return [
        TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=6,
            description="WiFi channel number",
            value_range=ValueRange(min_value=1, max_value=11),
            events=[
                TR181Event(
                    name="ChannelChanged",
                    path="Device.WiFi.Radio.1.Channel",
                    parameters=["Device.WiFi.Radio.1.Channel"]
                )
            ]
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_WRITE,
            value="TestNetwork",
            description="WiFi network name",
            value_range=ValueRange(max_length=32),
            functions=[
                TR181Function(
                    name="SetSSID",
                    path="Device.WiFi.Radio.1.SSID",
                    input_parameters=["Device.WiFi.Radio.1.SSID"],
                    output_parameters=["Device.WiFi.Radio.1.Status"]
                )
            ]
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True,
            description="Access point enable status"
        )
    ]


@pytest.fixture
def sample_device_nodes():
    """Create sample device nodes for testing."""
    return [
        TR181Node(
            path="Device.WiFi.Radio.1.Channel",
            name="Channel",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=8,  # Different value
            description="WiFi channel number"
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.SSID",
            name="SSID",
            data_type="string",
            access=AccessLevel.READ_ONLY,  # Different access level
            value="TestNetwork",
            description="WiFi network name"
        ),
        TR181Node(
            path="Device.WiFi.AccessPoint.1.Enable",
            name="Enable",
            data_type="boolean",
            access=AccessLevel.READ_WRITE,
            value=True,
            description="Access point enable status"
        ),
        TR181Node(
            path="Device.WiFi.Radio.1.Status",  # Extra node in device
            name="Status",
            data_type="string",
            access=AccessLevel.READ_ONLY,
            value="Up",
            description="Radio status"
        )
    ]


@pytest.fixture
def enhanced_engine():
    """Create an enhanced comparison engine for testing."""
    return EnhancedComparisonEngine()


class TestEnhancedComparisonEngine:
    """Test cases for the enhanced comparison engine."""
    
    @pytest.mark.asyncio
    async def test_basic_comparison_functionality(self, enhanced_engine, sample_subset_nodes, sample_device_nodes):
        """Test that basic comparison functionality still works."""
        result = await enhanced_engine.compare_with_validation(
            sample_subset_nodes, sample_device_nodes
        )
        
        assert isinstance(result, EnhancedComparisonResult)
        assert result.basic_comparison is not None
        
        # Check basic comparison results
        basic = result.basic_comparison
        assert basic.summary.total_nodes_source1 == 3  # subset nodes
        assert basic.summary.total_nodes_source2 == 4  # device nodes
        assert basic.summary.common_nodes == 3
        assert len(basic.only_in_source2) == 1  # Device.WiFi.Radio.1.Status
        assert basic.only_in_source2[0].path == "Device.WiFi.Radio.1.Status"
    
    @pytest.mark.asyncio
    async def test_validation_integration(self, enhanced_engine, sample_subset_nodes, sample_device_nodes):
        """Test validation integration in enhanced comparison."""
        result = await enhanced_engine.compare_with_validation(
            sample_subset_nodes, sample_device_nodes
        )
        
        # Check validation results
        assert len(result.validation_results) == 3  # All common nodes validated
        
        # Find validation results by path
        validation_by_path = {path: validation for path, validation in result.validation_results}
        
        # Check SSID validation (access level mismatch)
        ssid_validation = validation_by_path["Device.WiFi.Radio.1.SSID"]
        assert len(ssid_validation.warnings) > 0
        assert any("Access level mismatch" in warning for warning in ssid_validation.warnings)
        
        # Check Channel validation (should be valid despite value difference)
        channel_validation = validation_by_path["Device.WiFi.Radio.1.Channel"]
        assert channel_validation.is_valid  # Value 8 is within range 1-11
    
    @pytest.mark.asyncio
    async def test_event_function_testing_integration(self, enhanced_engine, sample_subset_nodes, 
                                                    sample_device_nodes, mock_device_extractor):
        """Test event and function testing integration."""
        # Mock the device extractor's extract method
        mock_device_extractor.extract = AsyncMock(return_value=sample_device_nodes)
        
        result = await enhanced_engine.compare_with_validation(
            sample_subset_nodes, sample_device_nodes, mock_device_extractor
        )
        
        # Check event test results
        assert len(result.event_test_results) == 1  # One event from Channel node
        event_result = result.event_test_results[0]
        assert event_result.event_name == "ChannelChanged"
        assert event_result.status in [EventFunctionTestResult.PASSED, EventFunctionTestResult.FAILED]
        
        # Check function test results
        assert len(result.function_test_results) == 1  # One function from SSID node
        function_result = result.function_test_results[0]
        assert function_result.function_name == "SetSSID"
        assert function_result.status in [EventFunctionTestResult.PASSED, EventFunctionTestResult.FAILED]
    
    @pytest.mark.asyncio
    async def test_comprehensive_summary(self, enhanced_engine, sample_subset_nodes, 
                                       sample_device_nodes, mock_device_extractor):
        """Test comprehensive summary generation."""
        mock_device_extractor.extract = AsyncMock(return_value=sample_device_nodes)
        
        result = await enhanced_engine.compare_with_validation(
            sample_subset_nodes, sample_device_nodes, mock_device_extractor
        )
        
        summary = result.get_summary()
        
        # Check summary structure
        assert 'basic_comparison' in summary
        assert 'validation' in summary
        assert 'events' in summary
        assert 'functions' in summary
        
        # Check basic comparison summary
        basic_summary = summary['basic_comparison']
        assert basic_summary['common_nodes'] == 3
        assert basic_summary['extra_in_device'] == 1
        
        # Check validation summary
        validation_summary = summary['validation']
        assert validation_summary['nodes_validated'] == 3
        assert validation_summary['total_warnings'] >= 1  # At least SSID access level warning
        
        # Check event/function summaries
        assert summary['events']['total_events_tested'] == 1
        assert summary['functions']['total_functions_tested'] == 1
    
    @pytest.mark.asyncio
    async def test_enhanced_summary_with_compliance_score(self, enhanced_engine, sample_subset_nodes, 
                                                        sample_device_nodes, mock_device_extractor):
        """Test enhanced summary with compliance scoring."""
        mock_device_extractor.extract = AsyncMock(return_value=sample_device_nodes)
        
        result = await enhanced_engine.compare_with_validation(
            sample_subset_nodes, sample_device_nodes, mock_device_extractor
        )
        
        enhanced_summary = enhanced_engine.get_enhanced_summary(result)
        
        # Check compliance scoring
        assert 'compliance' in enhanced_summary
        compliance = enhanced_summary['compliance']
        assert 'score' in compliance
        assert 'total_checks' in compliance
        assert 'passed_checks' in compliance
        assert 'failed_checks' in compliance
        
        # Score should be between 0 and 1
        assert 0 <= compliance['score'] <= 1
        assert compliance['total_checks'] == compliance['passed_checks'] + compliance['failed_checks']
        
        # Check details section
        assert 'details' in enhanced_summary
        details = enhanced_summary['details']
        assert 'validation_issues' in details
        assert 'event_failures' in details
        assert 'function_failures' in details
    
    @pytest.mark.asyncio
    async def test_validation_with_range_constraints(self, enhanced_engine):
        """Test validation with value range constraints."""
        subset_node = TR181Node(
            path="Device.Test.Parameter",
            name="Parameter",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value_range=ValueRange(min_value=1, max_value=10)
        )
        
        # Device node with value outside range
        device_node = TR181Node(
            path="Device.Test.Parameter",
            name="Parameter",
            data_type="int",
            access=AccessLevel.READ_WRITE,
            value=15  # Outside range
        )
        
        result = await enhanced_engine.compare_with_validation([subset_node], [device_node])
        
        # Should have validation error for out-of-range value
        assert len(result.validation_results) == 1
        path, validation_result = result.validation_results[0]
        assert not validation_result.is_valid
        assert any("above maximum" in error for error in validation_result.errors)
    
    @pytest.mark.asyncio
    async def test_validation_with_data_type_mismatch(self, enhanced_engine):
        """Test validation with data type mismatches."""
        subset_node = TR181Node(
            path="Device.Test.Parameter",
            name="Parameter",
            data_type="int",
            access=AccessLevel.READ_WRITE
        )
        
        # Device node with different data type
        device_node = TR181Node(
            path="Device.Test.Parameter",
            name="Parameter",
            data_type="string",  # Different type
            access=AccessLevel.READ_WRITE
        )
        
        result = await enhanced_engine.compare_with_validation([subset_node], [device_node])
        
        # Should have validation error for data type mismatch
        assert len(result.validation_results) == 1
        path, validation_result = result.validation_results[0]
        assert not validation_result.is_valid
        assert any("Data type mismatch" in error for error in validation_result.errors)
    
    @pytest.mark.asyncio
    async def test_object_node_children_validation(self, enhanced_engine):
        """Test validation of object node children."""
        subset_node = TR181Node(
            path="Device.WiFi.Radio.1",
            name="Radio",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            children=["Device.WiFi.Radio.1.Channel", "Device.WiFi.Radio.1.SSID"]
        )
        
        # Device node missing one child
        device_node = TR181Node(
            path="Device.WiFi.Radio.1",
            name="Radio",
            data_type="object",
            access=AccessLevel.READ_ONLY,
            is_object=True,
            children=["Device.WiFi.Radio.1.Channel"]  # Missing SSID
        )
        
        result = await enhanced_engine.compare_with_validation([subset_node], [device_node])
        
        # Should have validation error for missing child
        assert len(result.validation_results) == 1
        path, validation_result = result.validation_results[0]
        assert not validation_result.is_valid
        assert any("Missing child nodes" in error for error in validation_result.errors)
    
    @pytest.mark.asyncio
    async def test_without_device_extractor(self, enhanced_engine, sample_subset_nodes, sample_device_nodes):
        """Test enhanced comparison without device extractor (no event/function testing)."""
        result = await enhanced_engine.compare_with_validation(
            sample_subset_nodes, sample_device_nodes, device_extractor=None
        )
        
        # Should have basic comparison and validation, but no event/function tests
        assert result.basic_comparison is not None
        assert len(result.validation_results) > 0
        assert len(result.event_test_results) == 0
        assert len(result.function_test_results) == 0
        
        # Summary should still work
        summary = result.get_summary()
        assert summary['events']['total_events_tested'] == 0
        assert summary['functions']['total_functions_tested'] == 0
    
    @pytest.mark.asyncio
    async def test_empty_node_lists(self, enhanced_engine):
        """Test enhanced comparison with empty node lists."""
        result = await enhanced_engine.compare_with_validation([], [])
        
        assert result.basic_comparison.summary.total_nodes_source1 == 0
        assert result.basic_comparison.summary.total_nodes_source2 == 0
        assert len(result.validation_results) == 0
        assert len(result.event_test_results) == 0
        assert len(result.function_test_results) == 0
        
        # Summary should handle empty results gracefully
        summary = result.get_summary()
        assert summary['basic_comparison']['common_nodes'] == 0
        assert summary['validation']['nodes_validated'] == 0


class TestEnhancedComparisonResult:
    """Test cases for the EnhancedComparisonResult class."""
    
    def test_summary_generation(self):
        """Test summary generation from enhanced comparison result."""
        from tr181_comparator.models import ComparisonResult, ComparisonSummary
        
        # Create mock basic comparison result
        basic_result = ComparisonResult(
            only_in_source1=[],
            only_in_source2=[],
            differences=[],
            summary=ComparisonSummary(
                total_nodes_source1=5,
                total_nodes_source2=5,
                common_nodes=5,
                differences_count=2
            )
        )
        
        # Create mock validation results
        validation_results = [
            ("Device.Test.1", ValidationResult()),
            ("Device.Test.2", ValidationResult())
        ]
        validation_results[1][1].add_error("Test error")
        validation_results[1][1].add_warning("Test warning")
        
        # Create mock event/function results
        event_results = [
            EventTestResult(
                event_name="TestEvent",
                event_path="Device.Test.Event",
                status=EventFunctionTestResult.PASSED,
                message="Test passed",
                parameter_validation=ValidationResult()
            )
        ]
        
        function_results = [
            FunctionTestResult(
                function_name="TestFunction",
                function_path="Device.Test.Function",
                status=EventFunctionTestResult.FAILED,
                message="Test failed",
                input_validation=ValidationResult(),
                output_validation=ValidationResult()
            )
        ]
        
        # Create enhanced result
        enhanced_result = EnhancedComparisonResult(
            basic_comparison=basic_result,
            validation_results=validation_results,
            event_test_results=event_results,
            function_test_results=function_results
        )
        
        # Test summary generation
        summary = enhanced_result.get_summary()
        
        assert summary['basic_comparison']['total_differences'] == 2
        assert summary['basic_comparison']['common_nodes'] == 5
        assert summary['validation']['nodes_with_errors'] == 1
        assert summary['validation']['total_warnings'] == 1
        assert summary['validation']['nodes_validated'] == 2
        assert summary['events']['total_events_tested'] == 1
        assert summary['events']['failed_events'] == 0
        assert summary['functions']['total_functions_tested'] == 1
        assert summary['functions']['failed_functions'] == 1


if __name__ == "__main__":
    pytest.main([__file__])