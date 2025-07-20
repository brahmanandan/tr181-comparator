"""
Tests for the comprehensive logging and monitoring system.
"""

import pytest
import json
import tempfile
import time
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from tr181_comparator.logging import (
    LogLevel, LogCategory, LogEntry, PerformanceMetric, LoggingConfig,
    StructuredFormatter, PerformanceMonitor, TR181Logger, ComponentLogger,
    performance_monitor, get_logger, initialize_logging, get_performance_summary
)


class TestLogEntry:
    """Test LogEntry dataclass functionality."""
    
    def test_log_entry_creation(self):
        """Test creating a log entry with all fields."""
        entry = LogEntry(
            timestamp="2023-01-01T12:00:00Z",
            level="INFO",
            category="test",
            component="test_component",
            message="Test message",
            context={"key": "value"},
            correlation_id="test-123",
            duration_ms=100.5
        )
        
        assert entry.timestamp == "2023-01-01T12:00:00Z"
        assert entry.level == "INFO"
        assert entry.category == "test"
        assert entry.component == "test_component"
        assert entry.message == "Test message"
        assert entry.context == {"key": "value"}
        assert entry.correlation_id == "test-123"
        assert entry.duration_ms == 100.5
    
    def test_log_entry_to_dict(self):
        """Test converting log entry to dictionary."""
        entry = LogEntry(
            timestamp="2023-01-01T12:00:00Z",
            level="INFO",
            category="test",
            component="test_component",
            message="Test message",
            context={"key": "value"}
        )
        
        result = entry.to_dict()
        expected = {
            'timestamp': "2023-01-01T12:00:00Z",
            'level': "INFO",
            'category': "test",
            'component': "test_component",
            'message': "Test message",
            'context': {"key": "value"},
            'correlation_id': None,
            'duration_ms': None
        }
        
        assert result == expected
    
    def test_log_entry_to_json(self):
        """Test converting log entry to JSON string."""
        entry = LogEntry(
            timestamp="2023-01-01T12:00:00Z",
            level="INFO",
            category="test",
            component="test_component",
            message="Test message",
            context={"key": "value"}
        )
        
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        
        assert parsed['timestamp'] == "2023-01-01T12:00:00Z"
        assert parsed['level'] == "INFO"
        assert parsed['message'] == "Test message"


class TestPerformanceMetric:
    """Test PerformanceMetric functionality."""
    
    def test_performance_metric_creation(self):
        """Test creating a performance metric."""
        start_time = time.time()
        metric = PerformanceMetric(
            operation="test_operation",
            component="test_component",
            start_time=start_time,
            metadata={"test": "data"}
        )
        
        assert metric.operation == "test_operation"
        assert metric.component == "test_component"
        assert metric.start_time == start_time
        assert metric.end_time is None
        assert metric.duration_ms is None
        assert metric.success is True
        assert metric.error_message is None
        assert metric.metadata == {"test": "data"}
    
    def test_performance_metric_finish(self):
        """Test finishing a performance metric."""
        start_time = time.time()
        metric = PerformanceMetric(
            operation="test_operation",
            component="test_component",
            start_time=start_time
        )
        
        time.sleep(0.01)  # Small delay to ensure duration > 0
        metric.finish(success=True)
        
        assert metric.end_time is not None
        assert metric.duration_ms is not None
        assert metric.duration_ms > 0
        assert metric.success is True
        assert metric.error_message is None
    
    def test_performance_metric_finish_with_error(self):
        """Test finishing a performance metric with error."""
        start_time = time.time()
        metric = PerformanceMetric(
            operation="test_operation",
            component="test_component",
            start_time=start_time
        )
        
        metric.finish(success=False, error_message="Test error")
        
        assert metric.success is False
        assert metric.error_message == "Test error"


class TestLoggingConfig:
    """Test LoggingConfig functionality."""
    
    def test_default_config(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        
        assert config.log_level == LogLevel.INFO
        assert config.log_file is None
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.backup_count == 5
        assert config.enable_console is True
        assert config.enable_structured is True
        assert config.enable_performance is True
        assert "%(asctime)s" in config.log_format
    
    def test_custom_config(self):
        """Test custom logging configuration."""
        config = LoggingConfig(
            log_level=LogLevel.DEBUG,
            log_file="/tmp/test.log",
            max_file_size=1024,
            backup_count=3,
            enable_console=False,
            enable_structured=False,
            enable_performance=False,
            log_format="%(message)s"
        )
        
        assert config.log_level == LogLevel.DEBUG
        assert config.log_file == "/tmp/test.log"
        assert config.max_file_size == 1024
        assert config.backup_count == 3
        assert config.enable_console is False
        assert config.enable_structured is False
        assert config.enable_performance is False
        assert config.log_format == "%(message)s"


class TestStructuredFormatter:
    """Test StructuredFormatter functionality."""
    
    def test_structured_formatter(self):
        """Test structured JSON formatting."""
        import logging
        
        formatter = StructuredFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Add structured data
        record.category = "test_category"
        record.component = "test_component"
        record.context = {"key": "value"}
        record.correlation_id = "test-123"
        record.duration_ms = 100.5
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        assert parsed['level'] == "INFO"
        assert parsed['category'] == "test_category"
        assert parsed['component'] == "test_component"
        assert parsed['message'] == "Test message"
        assert parsed['context'] == {"key": "value"}
        assert parsed['correlation_id'] == "test-123"
        assert parsed['duration_ms'] == 100.5
        assert 'timestamp' in parsed


class TestPerformanceMonitor:
    """Test PerformanceMonitor functionality."""
    
    def test_performance_monitor_basic(self):
        """Test basic performance monitoring."""
        monitor = PerformanceMonitor()
        
        # Start operation
        metric_id = monitor.start_operation("test_op", "test_component")
        assert metric_id is not None
        
        # Finish operation
        monitor.finish_operation(metric_id, success=True)
        
        # Check metrics
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].operation == "test_op"
        assert metrics[0].component == "test_component"
        assert metrics[0].success is True
    
    def test_performance_monitor_with_metadata(self):
        """Test performance monitoring with metadata."""
        monitor = PerformanceMonitor()
        
        metadata = {"test_key": "test_value", "count": 42}
        metric_id = monitor.start_operation("test_op", "test_component", metadata)
        monitor.finish_operation(metric_id, success=True)
        
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].metadata == metadata
    
    def test_performance_monitor_filtering(self):
        """Test performance monitor filtering."""
        monitor = PerformanceMonitor()
        
        # Add multiple metrics
        id1 = monitor.start_operation("op1", "comp1")
        id2 = monitor.start_operation("op2", "comp1")
        id3 = monitor.start_operation("op1", "comp2")
        
        monitor.finish_operation(id1)
        monitor.finish_operation(id2)
        monitor.finish_operation(id3)
        
        # Test component filtering
        comp1_metrics = monitor.get_metrics(component="comp1")
        assert len(comp1_metrics) == 2
        
        # Test operation filtering
        op1_metrics = monitor.get_metrics(operation="op1")
        assert len(op1_metrics) == 2
        
        # Test combined filtering
        specific_metrics = monitor.get_metrics(component="comp1", operation="op1")
        assert len(specific_metrics) == 1
    
    def test_performance_monitor_summary(self):
        """Test performance monitor summary generation."""
        monitor = PerformanceMonitor()
        
        # Add successful operations
        for i in range(3):
            metric_id = monitor.start_operation(f"op{i}", "test_component")
            monitor.finish_operation(metric_id, success=True)
        
        # Add failed operation
        metric_id = monitor.start_operation("failed_op", "test_component")
        monitor.finish_operation(metric_id, success=False, error_message="Test error")
        
        summary = monitor.get_summary()
        
        assert summary['total_operations'] == 4
        assert summary['successful_operations'] == 3
        assert summary['failed_operations'] == 1
        assert summary['success_rate'] == 0.75
        assert 'avg_duration_ms' in summary
        assert 'by_component' in summary
        assert 'test_component' in summary['by_component']


class TestTR181Logger:
    """Test TR181Logger functionality."""
    
    def setup_method(self):
        """Reset logger instance before each test."""
        TR181Logger._instance = None
    
    def teardown_method(self):
        """Clean up after each test."""
        TR181Logger._instance = None
    
    def test_logger_initialization(self):
        """Test logger initialization."""
        config = LoggingConfig(log_level=LogLevel.DEBUG)
        logger = TR181Logger.initialize(config)
        
        assert logger is not None
        assert logger.config.log_level == config.log_level
        assert isinstance(logger.performance_monitor, PerformanceMonitor)
    
    def test_logger_singleton(self):
        """Test logger singleton behavior."""
        config = LoggingConfig()
        logger1 = TR181Logger.initialize(config)
        logger2 = TR181Logger.get_instance()
        
        assert logger1 is logger2
    
    def test_get_component_logger(self):
        """Test getting component-specific loggers."""
        config = LoggingConfig()
        logger = TR181Logger.initialize(config)
        
        comp_logger = logger.get_component_logger("test_component")
        assert comp_logger is not None
        assert comp_logger.name == "tr181_comparator.test_component"


class TestComponentLogger:
    """Test ComponentLogger functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        # Reset logger instance
        TR181Logger._instance = None
        
        # Initialize with test config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            self.log_file = f.name
        
        config = LoggingConfig(
            log_level=LogLevel.DEBUG,
            log_file=self.log_file,
            enable_structured=True
        )
        self.tr181_logger = TR181Logger.initialize(config)
        self.component_logger = ComponentLogger(self.tr181_logger, "test_component")
    
    def teardown_method(self):
        """Clean up test environment."""
        Path(self.log_file).unlink(missing_ok=True)
        TR181Logger._instance = None
    
    def test_basic_logging(self):
        """Test basic logging functionality."""
        self.component_logger.info("Test info message")
        self.component_logger.warning("Test warning message")
        self.component_logger.error("Test error message")
        
        # Check that log file was created and contains messages
        log_content = Path(self.log_file).read_text()
        assert "Test info message" in log_content
        assert "Test warning message" in log_content
        assert "Test error message" in log_content
    
    def test_structured_logging(self):
        """Test structured logging with context."""
        context = {"operation": "test", "count": 42}
        correlation_id = "test-123"
        
        self.component_logger.info(
            "Test structured message",
            LogCategory.AUDIT,
            context=context,
            correlation_id=correlation_id
        )
        
        # Read and parse log entries
        log_content = Path(self.log_file).read_text()
        log_lines = [line for line in log_content.strip().split('\n') if line]
        
        # Parse the JSON log entry
        log_entry = json.loads(log_lines[-1])
        
        assert log_entry['message'] == "Test structured message"
        assert log_entry['category'] == "audit"
        assert log_entry['component'] == "test_component"
        assert log_entry['context'] == context
        assert log_entry['correlation_id'] == correlation_id
    
    def test_specialized_logging_methods(self):
        """Test specialized logging methods."""
        correlation_id = "test-456"
        
        # Test extraction logging
        self.component_logger.log_extraction(
            "Extraction completed",
            "cwmp", "test-endpoint", 100, True, correlation_id
        )
        
        # Test comparison logging
        self.component_logger.log_comparison(
            "Comparison completed",
            "cwmp", "subset", 5, True, correlation_id
        )
        
        # Test validation logging
        self.component_logger.log_validation(
            "Validation completed",
            "node_validation", 2, 3, True, correlation_id
        )
        
        # Test connection logging
        self.component_logger.log_connection(
            "Connection established",
            "http://test.example.com", "REST", True, None, correlation_id
        )
        
        # Test configuration logging
        self.component_logger.log_configuration(
            "Configuration loaded",
            "device", True, None, correlation_id
        )
        
        # Check log file contains all entries
        log_content = Path(self.log_file).read_text()
        assert "Extraction completed" in log_content
        assert "Comparison completed" in log_content
        assert "Validation completed" in log_content
        assert "Connection established" in log_content
        assert "Configuration loaded" in log_content


class TestPerformanceMonitorDecorator:
    """Test performance monitoring decorator."""
    
    def setup_method(self):
        """Set up test environment."""
        TR181Logger._instance = None
        config = LoggingConfig(enable_performance=True)
        TR181Logger.initialize(config)
    
    def teardown_method(self):
        """Clean up test environment."""
        TR181Logger._instance = None
    
    def test_sync_function_decorator(self):
        """Test performance monitoring decorator on sync function."""
        @performance_monitor("test_operation", "test_component")
        def test_function(x, y):
            time.sleep(0.01)  # Small delay
            return x + y
        
        result = test_function(1, 2)
        assert result == 3
        
        # Check performance metrics
        summary = get_performance_summary()
        assert summary['total_operations'] >= 1
    
    @pytest.mark.asyncio
    async def test_async_function_decorator(self):
        """Test performance monitoring decorator on async function."""
        @performance_monitor("async_test_operation", "test_component")
        async def async_test_function(x, y):
            await asyncio.sleep(0.01)  # Small delay
            return x * y
        
        result = await async_test_function(3, 4)
        assert result == 12
        
        # Check performance metrics
        summary = get_performance_summary()
        assert summary['total_operations'] >= 1
    
    def test_decorator_with_exception(self):
        """Test performance monitoring decorator with exception."""
        @performance_monitor("failing_operation", "test_component")
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
        
        # Check that failed operation was recorded
        summary = get_performance_summary()
        assert summary['failed_operations'] >= 1


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def setup_method(self):
        """Set up test environment."""
        TR181Logger._instance = None
    
    def teardown_method(self):
        """Clean up test environment."""
        TR181Logger._instance = None
    
    def test_get_logger_function(self):
        """Test get_logger convenience function."""
        logger = get_logger("test_component")
        assert isinstance(logger, ComponentLogger)
        assert logger.component == "test_component"
    
    def test_initialize_logging_function(self):
        """Test initialize_logging convenience function."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name
        
        try:
            logger = initialize_logging(
                log_level=LogLevel.DEBUG,
                log_file=log_file,
                enable_performance=True,
                enable_structured=True
            )
            
            assert isinstance(logger, TR181Logger)
            assert logger.config.log_level == LogLevel.DEBUG
            assert logger.config.log_file == log_file
            assert logger.config.enable_performance is True
            assert logger.config.enable_structured is True
        finally:
            Path(log_file).unlink(missing_ok=True)
    
    def test_get_performance_summary_function(self):
        """Test get_performance_summary convenience function."""
        # Initialize logger
        initialize_logging()
        
        # Add some performance data
        logger = get_logger("test")
        instance = TR181Logger.get_instance()
        metric_id = instance.performance_monitor.start_operation("test", "test")
        instance.performance_monitor.finish_operation(metric_id)
        
        summary = get_performance_summary()
        assert isinstance(summary, dict)
        assert 'total_operations' in summary
        assert summary['total_operations'] >= 1
    
    def test_get_performance_summary_no_logger(self):
        """Test get_performance_summary when no logger is initialized."""
        summary = get_performance_summary()
        assert summary == {"error": "Logger not initialized"}


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple logging features."""
    
    def setup_method(self):
        """Set up test environment."""
        TR181Logger._instance = None
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            self.log_file = f.name
        
        config = LoggingConfig(
            log_level=LogLevel.DEBUG,
            log_file=self.log_file,
            enable_structured=True,
            enable_performance=True
        )
        self.logger = initialize_logging(
            log_level=LogLevel.DEBUG,
            log_file=self.log_file,
            enable_performance=True,
            enable_structured=True
        )
    
    def teardown_method(self):
        """Clean up test environment."""
        Path(self.log_file).unlink(missing_ok=True)
        TR181Logger._instance = None
    
    def test_full_logging_workflow(self):
        """Test a complete logging workflow with all features."""
        # Get component logger
        comp_logger = get_logger("integration_test")
        
        # Start an operation with correlation ID
        correlation_id = "integration-test-123"
        
        # Log operation start
        comp_logger.info(
            "Starting integration test operation",
            LogCategory.AUDIT,
            context={"test_type": "integration", "version": "1.0"},
            correlation_id=correlation_id
        )
        
        # Simulate some work with performance monitoring
        @performance_monitor("integration_work", "integration_test")
        def do_work():
            time.sleep(0.01)
            comp_logger.debug(
                "Performing work step",
                LogCategory.AUDIT,
                context={"step": 1},
                correlation_id=correlation_id
            )
            return "work_result"
        
        result = do_work()
        
        # Log connection attempt
        comp_logger.log_connection(
            "Connection test",
            "http://test.example.com", "HTTP", True, None, correlation_id
        )
        
        # Log validation
        comp_logger.log_validation(
            "Validation completed",
            "integration_test", 0, 1, True, correlation_id
        )
        
        # Log operation completion
        comp_logger.info(
            "Integration test operation completed",
            LogCategory.AUDIT,
            context={"result": result, "success": True},
            correlation_id=correlation_id
        )
        
        # Verify log file contains all entries
        log_content = Path(self.log_file).read_text()
        log_lines = [line for line in log_content.strip().split('\n') if line]
        
        # Parse JSON log entries
        log_entries = []
        for line in log_lines:
            try:
                entry = json.loads(line)
                log_entries.append(entry)
            except json.JSONDecodeError:
                pass  # Skip non-JSON lines
        
        # Verify we have the expected log entries
        correlation_entries = [e for e in log_entries if e.get('correlation_id') == correlation_id]
        assert len(correlation_entries) >= 4  # Start, connection, validation, completion
        
        # Verify performance summary
        summary = get_performance_summary()
        assert summary['total_operations'] >= 1
        assert 'integration_test' in summary['by_component']
        
        # Verify structured data is preserved
        start_entry = next(e for e in correlation_entries if "Starting integration" in e['message'])
        assert start_entry['context']['test_type'] == "integration"
        assert start_entry['context']['version'] == "1.0"


if __name__ == "__main__":
    pytest.main([__file__])