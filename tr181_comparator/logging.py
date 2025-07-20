"""
Comprehensive logging and monitoring system for TR181 Node Comparator.

This module provides structured logging, performance monitoring, and debug capabilities
for troubleshooting connection and validation issues.
"""

import logging
import logging.handlers
import json
import time
import functools
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, Union, List
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import sys
import os


class LogLevel(Enum):
    """Log levels for the TR181 comparator system."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Categories for structured logging."""
    EXTRACTION = "extraction"
    COMPARISON = "comparison"
    VALIDATION = "validation"
    CONNECTION = "connection"
    PERFORMANCE = "performance"
    CONFIGURATION = "configuration"
    ERROR = "error"
    AUDIT = "audit"


@dataclass
class LogEntry:
    """Structured log entry for consistent logging format."""
    timestamp: str
    level: str
    category: str
    component: str
    message: str
    context: Dict[str, Any]
    correlation_id: Optional[str] = None
    duration_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert log entry to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class PerformanceMetric:
    """Performance monitoring metric."""
    operation: str
    component: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def finish(self, success: bool = True, error_message: Optional[str] = None):
        """Mark the metric as finished and calculate duration."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error_message = error_message


class LoggingConfig:
    """Configuration for the logging system."""
    
    def __init__(
        self,
        log_level: LogLevel = LogLevel.INFO,
        log_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        enable_console: bool = True,
        enable_structured: bool = True,
        enable_performance: bool = True,
        log_format: Optional[str] = None
    ):
        self.log_level = log_level
        self.log_file = log_file
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_console = enable_console
        self.enable_structured = enable_structured
        self.enable_performance = enable_performance
        self.log_format = log_format or (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Extract structured data from record
        log_entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=record.levelname,
            category=getattr(record, 'category', 'general'),
            component=getattr(record, 'component', record.name),
            message=record.getMessage(),
            context=getattr(record, 'context', {}),
            correlation_id=getattr(record, 'correlation_id', None),
            duration_ms=getattr(record, 'duration_ms', None)
        )
        
        return log_entry.to_json()


class PerformanceMonitor:
    """Performance monitoring and metrics collection."""
    
    def __init__(self):
        self._metrics: List[PerformanceMetric] = []
        self._active_metrics: Dict[str, PerformanceMetric] = {}
        self._lock = threading.Lock()
    
    def start_operation(
        self, 
        operation: str, 
        component: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start tracking a performance metric."""
        metric_id = f"{component}_{operation}_{int(time.time() * 1000)}"
        
        metric = PerformanceMetric(
            operation=operation,
            component=component,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        with self._lock:
            self._active_metrics[metric_id] = metric
        
        return metric_id
    
    def finish_operation(
        self, 
        metric_id: str, 
        success: bool = True, 
        error_message: Optional[str] = None
    ):
        """Finish tracking a performance metric."""
        with self._lock:
            if metric_id in self._active_metrics:
                metric = self._active_metrics.pop(metric_id)
                metric.finish(success, error_message)
                self._metrics.append(metric)
                
                # Log performance metric
                logger = TR181Logger.get_logger("performance")
                logger.log_performance(
                    operation=metric.operation,
                    component=metric.component,
                    duration_ms=metric.duration_ms,
                    success=metric.success,
                    metadata=metric.metadata
                )
    
    def get_metrics(
        self, 
        component: Optional[str] = None, 
        operation: Optional[str] = None
    ) -> List[PerformanceMetric]:
        """Get collected metrics with optional filtering."""
        with self._lock:
            metrics = self._metrics.copy()
        
        if component:
            metrics = [m for m in metrics if m.component == component]
        
        if operation:
            metrics = [m for m in metrics if m.operation == operation]
        
        return metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        with self._lock:
            metrics = self._metrics.copy()
        
        if not metrics:
            return {"total_operations": 0}
        
        successful_metrics = [m for m in metrics if m.success]
        failed_metrics = [m for m in metrics if not m.success]
        
        durations = [m.duration_ms for m in metrics if m.duration_ms is not None]
        
        summary = {
            "total_operations": len(metrics),
            "successful_operations": len(successful_metrics),
            "failed_operations": len(failed_metrics),
            "success_rate": len(successful_metrics) / len(metrics) if metrics else 0,
        }
        
        if durations:
            summary.update({
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
            })
        
        # Group by component
        components = {}
        for metric in metrics:
            if metric.component not in components:
                components[metric.component] = []
            components[metric.component].append(metric)
        
        summary["by_component"] = {}
        for component, comp_metrics in components.items():
            comp_durations = [m.duration_ms for m in comp_metrics if m.duration_ms is not None]
            summary["by_component"][component] = {
                "total_operations": len(comp_metrics),
                "successful_operations": len([m for m in comp_metrics if m.success]),
                "avg_duration_ms": sum(comp_durations) / len(comp_durations) if comp_durations else 0
            }
        
        return summary


class TR181Logger:
    """Main logger class for TR181 Node Comparator."""
    
    _instance: Optional['TR181Logger'] = None
    _lock = threading.Lock()
    
    def __init__(self, config: LoggingConfig):
        self.config = config
        self.performance_monitor = PerformanceMonitor()
        self._loggers: Dict[str, logging.Logger] = {}
        self._setup_logging()
    
    @classmethod
    def initialize(cls, config: LoggingConfig) -> 'TR181Logger':
        """Initialize the global logger instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config)
            return cls._instance
    
    @classmethod
    def get_instance(cls) -> Optional['TR181Logger']:
        """Get the global logger instance."""
        return cls._instance
    
    @classmethod
    def get_logger(cls, component: str) -> 'ComponentLogger':
        """Get a component-specific logger."""
        instance = cls.get_instance()
        if instance is None:
            # Initialize with default config if not already initialized
            instance = cls.initialize(LoggingConfig())
        
        return ComponentLogger(instance, component)
    
    def _setup_logging(self):
        """Set up the logging configuration."""
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.log_level.value))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        if self.config.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, self.config.log_level.value))
            
            if self.config.enable_structured:
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(logging.Formatter(self.config.log_format))
            
            root_logger.addHandler(console_handler)
        
        # File handler with rotation
        if self.config.log_file:
            # Ensure log directory exists
            log_path = Path(self.config.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                self.config.log_file,
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count
            )
            file_handler.setLevel(getattr(logging, self.config.log_level.value))
            
            if self.config.enable_structured:
                file_handler.setFormatter(StructuredFormatter())
            else:
                file_handler.setFormatter(logging.Formatter(self.config.log_format))
            
            root_logger.addHandler(file_handler)
    
    def get_component_logger(self, component: str) -> logging.Logger:
        """Get or create a logger for a specific component."""
        if component not in self._loggers:
            logger = logging.getLogger(f"tr181_comparator.{component}")
            self._loggers[component] = logger
        
        return self._loggers[component]


class ComponentLogger:
    """Component-specific logger with structured logging capabilities."""
    
    def __init__(self, tr181_logger: TR181Logger, component: str):
        self.tr181_logger = tr181_logger
        self.component = component
        self.logger = tr181_logger.get_component_logger(component)
    
    def _log(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        """Internal logging method with structured data."""
        extra = {
            'category': category.value,
            'component': self.component,
            'context': context or {},
            'correlation_id': correlation_id,
            'duration_ms': duration_ms
        }
        
        self.logger.log(
            getattr(logging, level.value),
            message,
            extra=extra
        )
    
    def debug(
        self,
        message: str,
        category: LogCategory = LogCategory.AUDIT,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, category, context, correlation_id)
    
    def info(
        self,
        message: str,
        category: LogCategory = LogCategory.AUDIT,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log info message."""
        self._log(LogLevel.INFO, message, category, context, correlation_id)
    
    def warning(
        self,
        message: str,
        category: LogCategory = LogCategory.ERROR,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, category, context, correlation_id)
    
    def error(
        self,
        message: str,
        category: LogCategory = LogCategory.ERROR,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log error message."""
        self._log(LogLevel.ERROR, message, category, context, correlation_id)
    
    def critical(
        self,
        message: str,
        category: LogCategory = LogCategory.ERROR,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, category, context, correlation_id)
    
    def log_extraction(
        self,
        message: str,
        source_type: str,
        source_id: str,
        node_count: Optional[int] = None,
        success: bool = True,
        correlation_id: Optional[str] = None
    ):
        """Log extraction operation."""
        context = {
            'source_type': source_type,
            'source_id': source_id,
            'success': success
        }
        if node_count is not None:
            context['node_count'] = node_count
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        self._log(level, message, LogCategory.EXTRACTION, context, correlation_id)
    
    def log_comparison(
        self,
        message: str,
        source1_type: str,
        source2_type: str,
        differences_count: int,
        success: bool = True,
        correlation_id: Optional[str] = None
    ):
        """Log comparison operation."""
        context = {
            'source1_type': source1_type,
            'source2_type': source2_type,
            'differences_count': differences_count,
            'success': success
        }
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        self._log(level, message, LogCategory.COMPARISON, context, correlation_id)
    
    def log_validation(
        self,
        message: str,
        validation_type: str,
        errors_count: int,
        warnings_count: int,
        success: bool = True,
        correlation_id: Optional[str] = None
    ):
        """Log validation operation."""
        context = {
            'validation_type': validation_type,
            'errors_count': errors_count,
            'warnings_count': warnings_count,
            'success': success
        }
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        self._log(level, message, LogCategory.VALIDATION, context, correlation_id)
    
    def log_connection(
        self,
        message: str,
        endpoint: str,
        protocol: str,
        success: bool = True,
        error_details: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """Log connection operation."""
        context = {
            'endpoint': endpoint,
            'protocol': protocol,
            'success': success
        }
        if error_details:
            context['error_details'] = error_details
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        self._log(level, message, LogCategory.CONNECTION, context, correlation_id)
    
    def log_performance(
        self,
        operation: str,
        component: str,
        duration_ms: float,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log performance metric."""
        context = {
            'operation': operation,
            'component': component,
            'success': success,
            'metadata': metadata or {}
        }
        
        message = f"Operation {operation} completed in {duration_ms:.2f}ms"
        self._log(LogLevel.INFO, message, LogCategory.PERFORMANCE, context, correlation_id, duration_ms)
    
    def log_configuration(
        self,
        message: str,
        config_type: str,
        success: bool = True,
        validation_errors: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log configuration operation."""
        context = {
            'config_type': config_type,
            'success': success
        }
        if validation_errors:
            context['validation_errors'] = validation_errors
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        self._log(level, message, LogCategory.CONFIGURATION, context, correlation_id)


def performance_monitor(
    operation: str,
    component: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Decorator for automatic performance monitoring."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Determine component name
            comp_name = component or func.__module__.split('.')[-1]
            
            # Get logger instance
            logger_instance = TR181Logger.get_instance()
            if logger_instance is None:
                # If no logger initialized, just run the function
                return func(*args, **kwargs)
            
            # Start performance monitoring
            metric_id = logger_instance.performance_monitor.start_operation(
                operation, comp_name, metadata
            )
            
            try:
                result = func(*args, **kwargs)
                logger_instance.performance_monitor.finish_operation(metric_id, True)
                return result
            except Exception as e:
                logger_instance.performance_monitor.finish_operation(
                    metric_id, False, str(e)
                )
                raise
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Determine component name
            comp_name = component or func.__module__.split('.')[-1]
            
            # Get logger instance
            logger_instance = TR181Logger.get_instance()
            if logger_instance is None:
                # If no logger initialized, just run the function
                return await func(*args, **kwargs)
            
            # Start performance monitoring
            metric_id = logger_instance.performance_monitor.start_operation(
                operation, comp_name, metadata
            )
            
            try:
                result = await func(*args, **kwargs)
                logger_instance.performance_monitor.finish_operation(metric_id, True)
                return result
            except Exception as e:
                logger_instance.performance_monitor.finish_operation(
                    metric_id, False, str(e)
                )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator


# Convenience functions for easy access
def get_logger(component: str) -> ComponentLogger:
    """Get a component logger."""
    return TR181Logger.get_logger(component)


def initialize_logging(
    log_level: LogLevel = LogLevel.INFO,
    log_file: Optional[str] = None,
    enable_performance: bool = True,
    enable_structured: bool = True
) -> TR181Logger:
    """Initialize the logging system with common defaults."""
    config = LoggingConfig(
        log_level=log_level,
        log_file=log_file,
        enable_performance=enable_performance,
        enable_structured=enable_structured
    )
    return TR181Logger.initialize(config)


def get_performance_summary() -> Dict[str, Any]:
    """Get performance monitoring summary."""
    instance = TR181Logger.get_instance()
    if instance:
        return instance.performance_monitor.get_summary()
    return {"error": "Logger not initialized"}