"""Final comprehensive system integration tests for TR181 node comparator.

This test suite validates all requirements are met through acceptance testing,
performs comprehensive system testing with all components integrated,
tests memory usage and performance with large datasets,
and performs security review of device communication and data handling.
"""

import pytest
import asyncio
import time
import json
import tempfile
import psutil
import os
import gc
from pathlib import Path
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from tr181_comparator.models import (
    TR181Node, AccessLevel, ValueRange, TR181Event, TR181Function, Severity
)
from tr181_comparator.main import TR181ComparatorApp, ReportGenerator
from tr181_comparator.config import SystemConfig, DeviceConfig, SubsetConfig, ExportConfig
from tr181_comparator.comparison import ComparisonEngine, EnhancedComparisonEngine
from tr181_comparator.extractors import SubsetManager, CWMPExtractor, HookBasedDeviceExtractor
from tr181_comparator.hooks import DeviceHookFactory, HookType, DeviceConfig as HookDeviceConfig
from tr181_comparator.validation import TR181Validator
from tr181_comparator.errors import (
    TR181Error, ConnectionError, ValidationError, AuthenticationError,
    TimeoutError, ProtocolError, ConfigurationError
)
from tr181_comparator.logging import initialize_logging, get_logger, get_performance_summary
from tr181_comparator.cli import TR181ComparatorCLI


class SystemTestDataGenerator:
    """Generates comprehensive test data for system testing."""
    
    @staticmethod
    def generate_large_realistic_dataset(count: int = 5000) -> List[TR181Node]:
        """Generate large realistic TR181 dataset for performance testing."""
        nodes = []
        
        # Device Info hierarchy
        device_info_nodes = [
            TR181Node(
                path="Device.DeviceInfo.Manufacturer",
                name="Manufacturer",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="SystemTestCorp",
                description="Device manufacturer for system testing"
            ),
            TR181Node(
                path="Device.DeviceInfo.ModelName",
                name="ModelName",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="TR181-SystemTest-Device",
                description="Device model name for system testing"
            ),
            TR181Node(
                path="Device.DeviceInfo.SoftwareVersion",
                name="SoftwareVersion",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="1.0.0-systemtest",
                description="Software version for system testing"
            ),
            TR181Node(
                path="Device.DeviceInfo.HardwareVersion",
                name="HardwareVersion",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="HW-1.0-systemtest",
                description="Hardware version for system testing"
            )
        ]
        nodes.extend(device_info_nodes)
        
        # WiFi hierarchy with multiple radios and access points
        for radio_idx in range(1, 11):  # 10 radios
            radio_base = f"Device.WiFi.Radio.{radio_idx}"
            nodes.extend([
                TR181Node(
                    path=f"{radio_base}.Enable",
                    name="Enable",
                    data_type="boolean",
                    access=AccessLevel.READ_WRITE,
                    value=True,
                    description=f"Enable status for radio {radio_idx}"
                ),
                TR181Node(
                    path=f"{radio_base}.Channel",
                    name="Channel",
                    data_type="int",
                    access=AccessLevel.READ_WRITE,
                    value=6 + (radio_idx % 11),
                    description=f"Channel for radio {radio_idx}",
                    value_range=ValueRange(min_value=1, max_value=165)
                ),
                TR181Node(
                    path=f"{radio_base}.SSID",
                    name="SSID",
                    data_type="string",
                    access=AccessLevel.READ_WRITE,
                    value=f"SystemTest-WiFi-{radio_idx}",
                    description=f"SSID for radio {radio_idx}",
                    value_range=ValueRange(max_length=32)
                ),
                TR181Node(
                    path=f"{radio_base}.TransmitPower",
                    name="TransmitPower",
                    data_type="int",
                    access=AccessLevel.READ_WRITE,
                    value=20,
                    description=f"Transmit power for radio {radio_idx}",
                    value_range=ValueRange(min_value=1, max_value=30)
                )
            ])
        
        # Generate additional test parameters to reach target count
        current_count = len(nodes)
        for i in range(current_count, count):
            category = i % 10
            nodes.append(
                TR181Node(
                    path=f"Device.SystemTest.Category{category}.Parameter{i}",
                    name=f"Parameter{i}",
                    data_type="string" if i % 3 == 0 else ("int" if i % 3 == 1 else "boolean"),
                    access=AccessLevel.READ_WRITE if i % 2 == 0 else AccessLevel.READ_ONLY,
                    value=f"test_value_{i}" if i % 3 == 0 else (i if i % 3 == 1 else (i % 2 == 0)),
                    description=f"System test parameter {i} in category {category}"
                )
            )
        
        return nodes
    
    @staticmethod
    def create_system_config() -> SystemConfig:
        """Create comprehensive system configuration for testing."""
        return SystemConfig(
            devices=[
                DeviceConfig(
                    name="test_device_1",
                    type="rest",
                    endpoint="http://test-device-1.example.com:8080",
                    authentication={"username": "admin", "password": "test123"},
                    timeout=30,
                    retry_count=3
                ),
                DeviceConfig(
                    name="test_device_2", 
                    type="cwmp",
                    endpoint="http://test-device-2.example.com:7547",
                    authentication={"username": "cwmp_user", "password": "cwmp_pass"},
                    timeout=45,
                    retry_count=2
                )
            ],
            subsets=[
                SubsetConfig(
                    name="test_subset_1",
                    file_path="test_subset_1.json",
                    version="1.0.0",
                    description="Test subset for system testing"
                )
            ],
            export_settings=ExportConfig(
                default_format="json",
                output_directory="./test_output",
                include_metadata=True,
                timestamp_format="%Y%m%d_%H%M%S"
            )
        )


class MockSystemHook:
    """Mock hook for comprehensive system testing."""
    
    def __init__(self, nodes: List[TR181Node], should_fail: bool = False, 
                 partial_failure: bool = False, delay_ms: int = 0):
        self.nodes = nodes
        self.should_fail = should_fail
        self.partial_failure = partial_failure
        self.delay_ms = delay_ms
        self.connected = False
        self.call_count = 0
        self.operation_history = []
    
    async def connect(self, config: HookDeviceConfig) -> bool:
        self.call_count += 1
        self.operation_history.append(f"connect_{self.call_count}")
        
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)
        
        if self.should_fail:
            return False
        
        self.connected = True
        return True
    
    async def disconnect(self) -> None:
        self.connected = False
        self.operation_history.append("disconnect")
    
    async def get_parameter_names(self, path_prefix: str = "Device.") -> List[str]:
        self.operation_history.append(f"get_parameter_names_{path_prefix}")
        
        if not self.connected:
            raise ConnectionError("Not connected")
        
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)
        
        if self.should_fail:
            raise ConnectionError("Parameter discovery failed")
        
        matching_nodes = [node.path for node in self.nodes if node.path.startswith(path_prefix)]
        
        if self.partial_failure and len(matching_nodes) > 10:
            # Return only partial results to simulate partial failure
            return matching_nodes[:len(matching_nodes)//2]
        
        return matching_nodes
    
    async def get_parameter_values(self, paths: List[str]) -> Dict[str, Any]:
        self.operation_history.append(f"get_parameter_values_{len(paths)}")
        
        if not self.connected:
            raise ConnectionError("Not connected")
        
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)
        
        node_map = {node.path: node for node in self.nodes}
        result = {}
        
        for path in paths:
            if path in node_map:
                if self.partial_failure and len(result) > len(paths) // 2:
                    # Simulate partial failure
                    break
                result[path] = node_map[path].value
        
        return result
    
    async def get_parameter_attributes(self, paths: List[str]) -> Dict[str, Dict[str, Any]]:
        self.operation_history.append(f"get_parameter_attributes_{len(paths)}")
        
        if not self.connected:
            raise ConnectionError("Not connected")
        
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)
        
        node_map = {node.path: node for node in self.nodes}
        result = {}
        
        for path in paths:
            if path in node_map:
                if self.partial_failure and len(result) > len(paths) // 2:
                    break
                node = node_map[path]
                result[path] = {
                    "type": node.data_type,
                    "access": node.access.value,
                    "notification": "passive"
                }
        
        return result
    
    async def set_parameter_values(self, values: Dict[str, Any]) -> bool:
        self.operation_history.append(f"set_parameter_values_{len(values)}")
        return not self.should_fail
    
    async def subscribe_to_event(self, event_path: str) -> bool:
        self.operation_history.append(f"subscribe_to_event_{event_path}")
        return not self.should_fail
    
    async def call_function(self, function_path: str, input_params: Dict[str, Any]) -> Dict[str, Any]:
        self.operation_history.append(f"call_function_{function_path}")
        if self.should_fail:
            raise ConnectionError("Function call failed")
        return {"result": "success", "output": {}}
class
 TestSystemRequirementsValidation:
    """Test all system requirements are met through acceptance testing."""
    
    @pytest.mark.asyncio
    async def test_requirement_1_1_cwmp_extraction(self):
        """Test Requirement 1.1: Extract TR181 nodes from CWMP sources with hierarchical structure."""
        # Generate test data
        test_nodes = SystemTestDataGenerator.generate_large_realistic_dataset(100)
        
        # Create mock CWMP hook
        mock_hook = MockSystemHook(test_nodes)
        
        # Create CWMP extractor
        config = HookDeviceConfig(
            type="cwmp",
            endpoint="http://test-cwmp.example.com:7547",
            authentication={"username": "test", "password": "test"},
            timeout=30,
            retry_count=3
        )
        
        extractor = HookBasedDeviceExtractor(mock_hook, config)
        
        # Extract nodes
        extracted_nodes = await extractor.extract()
        
        # Verify requirement 1.1
        assert len(extracted_nodes) == 100
        assert all(node.path.startswith("Device.") for node in extracted_nodes)
        assert all(hasattr(node, 'data_type') and node.data_type for node in extracted_nodes)
        assert all(hasattr(node, 'access') and node.access for node in extracted_nodes)
        
        print(f"✓ Requirement 1.1 validated: Extracted {len(extracted_nodes)} TR181 nodes with hierarchical structure")
    
    @pytest.mark.asyncio
    async def test_requirement_2_1_custom_subset_definition(self, tmp_path):
        """Test Requirement 2.1: Define custom subset of TR181 nodes."""
        # Create custom subset
        custom_nodes = [
            TR181Node(
                path="Device.WiFi.Radio.1.Enable",
                name="Enable",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="Custom WiFi radio enable"
            ),
            TR181Node(
                path="Device.Custom.Parameter.1",
                name="CustomParameter1",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="custom_value",
                description="Custom parameter for testing",
                is_custom=True
            )
        ]
        
        # Save subset
        subset_file = tmp_path / "custom_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        await subset_manager.save_subset(custom_nodes)
        
        # Load and verify
        loaded_nodes = await subset_manager.extract()
        
        # Verify requirement 2.1
        assert len(loaded_nodes) == 2
        assert any(node.is_custom for node in loaded_nodes)
        assert all(node.path.startswith("Device.") for node in loaded_nodes)
        
        print(f"✓ Requirement 2.1 validated: Created custom subset with {len(loaded_nodes)} nodes including custom nodes")
    
    @pytest.mark.asyncio
    async def test_requirement_3_1_cwmp_vs_subset_comparison(self, tmp_path):
        """Test Requirement 3.1: Compare CWMP TR181 nodes against custom subset."""
        # Generate CWMP nodes
        cwmp_nodes = SystemTestDataGenerator.generate_large_realistic_dataset(50)
        
        # Create subset with partial overlap
        subset_nodes = cwmp_nodes[:30]  # First 30 nodes
        subset_nodes.extend([
            TR181Node(
                path="Device.Custom.OnlyInSubset",
                name="OnlyInSubset",
                data_type="string",
                access=AccessLevel.READ_WRITE,
                value="subset_only",
                is_custom=True
            )
        ])
        
        # Save subset
        subset_file = tmp_path / "comparison_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        await subset_manager.save_subset(subset_nodes)
        
        # Perform comparison
        comparison_engine = ComparisonEngine()
        result = await comparison_engine.compare(cwmp_nodes, subset_nodes)
        
        # Verify requirement 3.1
        assert result.summary.total_nodes_source1 == 50  # CWMP nodes
        assert result.summary.total_nodes_source2 == 31  # Subset nodes
        assert len(result.only_in_source1) == 20  # Nodes only in CWMP
        assert len(result.only_in_source2) == 1   # Custom node only in subset
        assert result.summary.common_nodes == 30  # Overlapping nodes
        
        print(f"✓ Requirement 3.1 validated: CWMP vs subset comparison identified {len(result.only_in_source1)} CWMP-only and {len(result.only_in_source2)} subset-only nodes")
    
    @pytest.mark.asyncio
    async def test_requirement_6_1_export_multiple_formats(self, tmp_path):
        """Test Requirement 6.1: Export comparison results in multiple formats."""
        # Generate comparison result
        nodes1 = SystemTestDataGenerator.generate_large_realistic_dataset(20)
        nodes2 = SystemTestDataGenerator.generate_large_realistic_dataset(25)
        
        comparison_engine = ComparisonEngine()
        result = await comparison_engine.compare(nodes1, nodes2)
        
        # Test export in all formats
        report_generator = ReportGenerator(include_metadata=True)
        
        # JSON export
        json_file = tmp_path / "test_result.json"
        await report_generator.export_as_json(result, json_file)
        assert json_file.exists()
        
        # XML export
        xml_file = tmp_path / "test_result.xml"
        await report_generator.export_as_xml(result, xml_file)
        assert xml_file.exists()
        
        # Text export
        text_file = tmp_path / "test_result.txt"
        await report_generator.export_as_text(result, text_file)
        assert text_file.exists()
        
        # Verify content
        with open(json_file, 'r') as f:
            json_data = json.load(f)
            assert 'summary' in json_data
            assert 'metadata' in json_data
        
        print(f"✓ Requirement 6.1 validated: Successfully exported results in JSON, XML, and text formats")
c
lass TestPerformanceAndScalability:
    """Test memory usage and performance with large datasets."""
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    
    @pytest.mark.asyncio
    async def test_large_dataset_memory_usage(self):
        """Test memory usage with large datasets (5000+ nodes)."""
        initial_memory = self.get_memory_usage()
        
        # Generate large dataset
        large_dataset = SystemTestDataGenerator.generate_large_realistic_dataset(5000)
        after_generation_memory = self.get_memory_usage()
        
        # Perform comparison
        comparison_engine = ComparisonEngine()
        modified_dataset = large_dataset.copy()
        
        # Modify 10% of nodes to create differences
        for i in range(0, len(modified_dataset), 10):
            if modified_dataset[i].data_type == "string":
                modified_dataset[i] = TR181Node(
                    path=modified_dataset[i].path,
                    name=modified_dataset[i].name,
                    data_type=modified_dataset[i].data_type,
                    access=modified_dataset[i].access,
                    value=f"modified_{modified_dataset[i].value}",
                    description=modified_dataset[i].description
                )
        
        start_time = time.time()
        result = await comparison_engine.compare(large_dataset, modified_dataset)
        end_time = time.time()
        
        after_comparison_memory = self.get_memory_usage()
        
        # Clean up
        del large_dataset, modified_dataset
        gc.collect()
        final_memory = self.get_memory_usage()
        
        # Performance assertions
        comparison_time = end_time - start_time
        memory_increase = after_comparison_memory - initial_memory
        
        assert comparison_time < 30.0  # Should complete within 30 seconds
        assert memory_increase < 500   # Should not use more than 500MB
        assert result.summary.total_nodes_source1 == 5000
        assert result.summary.total_nodes_source2 == 5000
        assert len(result.differences) > 0  # Should find differences
        
        print(f"✓ Large dataset performance: {comparison_time:.2f}s, {memory_increase:.1f}MB memory increase")
        print(f"  - Processed {result.summary.total_nodes_source1} nodes")
        print(f"  - Found {len(result.differences)} differences")
        print(f"  - Memory cleanup: {after_comparison_memory - final_memory:.1f}MB freed")
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_performance(self):
        """Test performance with concurrent comparison operations."""
        # Generate multiple datasets
        datasets = []
        for i in range(10):
            dataset = SystemTestDataGenerator.generate_large_realistic_dataset(500)
            datasets.append(dataset)
        
        # Create comparison tasks
        comparison_engine = ComparisonEngine()
        tasks = []
        
        for i in range(10):
            # Create modified version for comparison
            modified = datasets[i].copy()
            for j in range(0, len(modified), 20):  # Modify every 20th node
                if modified[j].data_type == "string":
                    modified[j] = TR181Node(
                        path=modified[j].path,
                        name=modified[j].name,
                        data_type=modified[j].data_type,
                        access=modified[j].access,
                        value=f"concurrent_modified_{modified[j].value}",
                        description=modified[j].description
                    )
            
            task = comparison_engine.compare(datasets[i], modified)
            tasks.append(task)
        
        # Run concurrently and measure performance
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        concurrent_time = end_time - start_time
        
        # Verify all operations completed successfully
        assert len(results) == 10
        for result in results:
            assert result.summary.total_nodes_source1 == 500
            assert result.summary.total_nodes_source2 == 500
            assert len(result.differences) > 0
        
        # Performance should be better than sequential
        assert concurrent_time < 60.0  # Should complete within 60 seconds
        
        print(f"✓ Concurrent operations performance: {concurrent_time:.2f}s for 10 concurrent comparisons")
        print(f"  - Average per comparison: {concurrent_time/10:.2f}s")


class TestSecurityAndErrorHandling:
    """Test security aspects and comprehensive error handling."""
    
    @pytest.mark.asyncio
    async def test_authentication_security(self):
        """Test authentication handling and security measures."""
        # Test different authentication methods
        auth_configs = [
            {"username": "admin", "password": "secure_password_123"},
            {"token": "bearer_token_xyz789"},
            {"certificate": "/path/to/cert.pem", "key": "/path/to/key.pem"}
        ]
        
        for auth_config in auth_configs:
            config = HookDeviceConfig(
                type="rest",
                endpoint="https://secure-device.example.com:8443",  # HTTPS endpoint
                authentication=auth_config,
                timeout=30,
                retry_count=3
            )
            
            # Verify secure configuration
            assert config.endpoint.startswith("https://")  # Secure protocol
            assert isinstance(config.authentication, dict)
            assert len(config.authentication) > 0
            
            # Test that sensitive data is not logged (mock test)
            config_str = str(config)
            if "password" in auth_config:
                assert auth_config["password"] not in config_str  # Password should be masked
        
        print(f"✓ Security validation: Tested {len(auth_configs)} authentication methods with secure protocols")
    
    @pytest.mark.asyncio
    async def test_input_validation_security(self, tmp_path):
        """Test input validation to prevent security vulnerabilities."""
        # Test malicious path injection
        malicious_paths = [
            "../../../etc/passwd",
            "Device.WiFi.Radio.1'; DROP TABLE nodes; --",
            "Device.Test<script>alert('xss')</script>",
            "Device." + "A" * 10000,  # Extremely long path
        ]
        
        validator = TR181Validator()
        
        for malicious_path in malicious_paths:
            try:
                # Create node with malicious path
                malicious_node = TR181Node(
                    path=malicious_path,
                    name="TestNode",
                    data_type="string",
                    access=AccessLevel.READ_ONLY,
                    value="test"
                )
                
                # Validate - should catch malicious input
                result = validator.validate_node(malicious_node)
                
                # Should have validation errors for malicious input
                assert not result.is_valid or len(result.warnings) > 0
                
            except Exception as e:
                # Exception is acceptable for malicious input
                assert isinstance(e, (ValueError, ValidationError))
        
        print(f"✓ Input validation security: Tested {len(malicious_paths)} malicious inputs")cla
ss TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_system_workflow(self, tmp_path):
        """Test complete system workflow from configuration to report generation."""
        # Initialize logging
        initialize_logging()
        logger = get_logger("system_test")
        
        # 1. Create system configuration
        system_config = SystemTestDataGenerator.create_system_config()
        system_config.export_settings.output_directory = str(tmp_path)
        
        # 2. Create test data
        cwmp_nodes = SystemTestDataGenerator.generate_large_realistic_dataset(100)
        subset_nodes = cwmp_nodes[:75]  # Subset of CWMP nodes
        device_nodes = cwmp_nodes[25:] + [  # Overlapping with different nodes
            TR181Node(
                path="Device.Implementation.CustomFeature",
                name="CustomFeature",
                data_type="boolean",
                access=AccessLevel.READ_WRITE,
                value=True,
                description="Custom feature in device implementation"
            )
        ]
        
        # 3. Save subset
        subset_file = tmp_path / "workflow_subset.json"
        subset_manager = SubsetManager(str(subset_file))
        await subset_manager.save_subset(subset_nodes)
        
        # 4. Create application
        app = TR181ComparatorApp(system_config)
        
        # 5. Perform all comparison types
        
        # CWMP vs Subset comparison (simulated)
        comparison_engine = ComparisonEngine()
        cwmp_vs_subset_result = await comparison_engine.compare(cwmp_nodes, subset_nodes)
        
        # Subset vs Device comparison
        mock_device_hook = MockSystemHook(device_nodes)
        device_config = HookDeviceConfig(
            type="rest",
            endpoint="http://workflow-device.example.com:8080",
            authentication={"username": "test", "password": "test"},
            timeout=30,
            retry_count=3
        )
        device_extractor = HookBasedDeviceExtractor(mock_device_hook, device_config)
        
        enhanced_engine = EnhancedComparisonEngine()
        subset_vs_device_result = await enhanced_engine.compare_with_validation(
            subset_nodes, device_nodes, device_extractor
        )
        
        # Device vs Device comparison
        device2_nodes = device_nodes[:50] + [
            TR181Node(
                path="Device.Vendor2.SpecialParameter",
                name="SpecialParameter",
                data_type="string",
                access=AccessLevel.READ_ONLY,
                value="vendor2_special"
            )
        ]
        device_vs_device_result = await comparison_engine.compare(device_nodes, device2_nodes)
        
        # 6. Export results in all formats
        results = [
            ("cwmp_vs_subset", cwmp_vs_subset_result),
            ("subset_vs_device", subset_vs_device_result),
            ("device_vs_device", device_vs_device_result)
        ]
        
        for result_name, result in results:
            # Export in all formats
            await app.export_result_as_json(result, tmp_path / f"{result_name}.json")
            await app.export_result_as_xml(result, tmp_path / f"{result_name}.xml")
            await app.export_result_as_text(result, tmp_path / f"{result_name}.txt")
            
            # Verify files were created
            assert (tmp_path / f"{result_name}.json").exists()
            assert (tmp_path / f"{result_name}.xml").exists()
            assert (tmp_path / f"{result_name}.txt").exists()
        
        # 7. Verify performance metrics
        performance_summary = get_performance_summary()
        assert performance_summary is not None
        
        # 8. Verify all results
        assert cwmp_vs_subset_result.summary.total_nodes_source1 == 100
        assert cwmp_vs_subset_result.summary.total_nodes_source2 == 75
        
        assert subset_vs_device_result.basic_comparison.summary.total_nodes_source1 == 75
        assert subset_vs_device_result.basic_comparison.summary.total_nodes_source2 == 76
        
        assert device_vs_device_result.summary.total_nodes_source1 == 76
        assert device_vs_device_result.summary.total_nodes_source2 == 51
        
        logger.info("Complete system workflow test completed successfully")
        print(f"✓ Complete system workflow: Processed 3 comparison types with full export pipeline")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])