"""Deprecation utilities for TR181 comparator.

This module provides utilities for handling deprecated functionality and
showing appropriate warnings when deprecated features are used.
"""

import warnings
import functools
import inspect
from typing import Callable, Any, Optional, Dict, Type, TypeVar, cast

# Type variable for generic function type
F = TypeVar('F', bound=Callable[..., Any])


def deprecated(message: str) -> Callable[[F], F]:
    """Decorator to mark functions, methods, or classes as deprecated.
    
    Args:
        message: Message explaining the deprecation and suggesting alternatives
        
    Returns:
        Decorator function that adds deprecation warning
    """
    def decorator(func_or_class: F) -> F:
        if inspect.isclass(func_or_class):
            # Handle class deprecation
            original_init = func_or_class.__init__
            
            @functools.wraps(original_init)
            def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
                warnings.warn(
                    f"Class {func_or_class.__name__} is deprecated. {message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
                original_init(self, *args, **kwargs)
            
            func_or_class.__init__ = new_init  # type: ignore
            return cast(F, func_or_class)
        else:
            # Handle function/method deprecation
            @functools.wraps(func_or_class)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                warnings.warn(
                    f"Function {func_or_class.__name__} is deprecated. {message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
                return func_or_class(*args, **kwargs)
            
            return cast(F, wrapper)
    
    return decorator


def deprecated_argument(argument_name: str, message: str) -> Callable[[F], F]:
    """Decorator to mark function/method arguments as deprecated.
    
    Args:
        argument_name: Name of the deprecated argument
        message: Message explaining the deprecation and suggesting alternatives
        
    Returns:
        Decorator function that adds deprecation warning when argument is used
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if argument_name in kwargs:
                warnings.warn(
                    f"Argument '{argument_name}' in {func.__name__} is deprecated. {message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
            return func(*args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator


def deprecated_property(message: str) -> Callable[[property], property]:
    """Decorator to mark class properties as deprecated.
    
    Args:
        message: Message explaining the deprecation and suggesting alternatives
        
    Returns:
        Decorator function that adds deprecation warning when property is accessed
    """
    def decorator(prop: property) -> property:
        @property
        def wrapper(self: Any) -> Any:
            warnings.warn(
                f"Property is deprecated. {message}",
                category=DeprecationWarning,
                stacklevel=2
            )
            return prop.__get__(self)
        
        if prop.fset:
            @wrapper.setter  # type: ignore
            def wrapper_set(self: Any, value: Any) -> None:
                warnings.warn(
                    f"Property setter is deprecated. {message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
                prop.__set__(self, value)  # type: ignore
        
        if prop.fdel:
            @wrapper.deleter  # type: ignore
            def wrapper_del(self: Any) -> None:
                warnings.warn(
                    f"Property deleter is deprecated. {message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
                prop.__delete__(self)  # type: ignore
        
        return wrapper
    
    return decorator


class DeprecatedClassAlias:
    """Create an alias for a class that issues a deprecation warning when used.
    
    This class can be used to create backward-compatible aliases for renamed classes.
    """
    
    def __init__(self, new_class: Type, message: str):
        """Initialize with the new class and deprecation message.
        
        Args:
            new_class: The new class that should be used instead
            message: Message explaining the deprecation and suggesting alternatives
        """
        self.new_class = new_class
        self.message = message
    
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Create an instance of the new class with a deprecation warning."""
        warnings.warn(
            f"This class is deprecated. {self.message}",
            category=DeprecationWarning,
            stacklevel=2
        )
        return self.new_class(*args, **kwargs)


# Dictionary mapping old CLI commands to new ones for deprecation messages
DEPRECATED_CLI_COMMANDS = {
    'subset-vs-device': 'operator-requirement-vs-device',
    'validate-subset': 'validate-operator-requirement'
}

# Dictionary mapping old CLI arguments to new ones for deprecation messages
DEPRECATED_CLI_ARGUMENTS = {
    'subset-file': 'operator-requirement-file',
    'subset_file': 'operator_requirement_file'
}

# Dictionary mapping old API method names to new ones for deprecation messages
DEPRECATED_API_METHODS = {
    'compare_subset_vs_device': 'compare_operator_requirement_vs_device',
    'validate_subset_file': 'validate_operator_requirement_file',
    'extract_subset_nodes': 'extract_operator_requirement_nodes'
}

# Dictionary mapping old configuration keys to new ones for deprecation messages
DEPRECATED_CONFIG_KEYS = {
    'subset_configs': 'operator_requirement_configs',
    'subset_file_path': 'operator_requirement_file_path',
    'subset_validation': 'operator_requirement_validation'
}