"""Core data models for TR181 node representation and comparison."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Any


class AccessLevel(Enum):
    """TR181 parameter access levels."""
    READ_ONLY = "read-only"
    READ_WRITE = "read-write"
    WRITE_ONLY = "write-only"


class Severity(Enum):
    """Severity levels for comparison differences and validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValueRange:
    """Value constraints and validation rules for TR181 parameters."""
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    allowed_values: Optional[List[Any]] = None  # For enumerated values
    pattern: Optional[str] = None  # Regex pattern for string validation
    max_length: Optional[int] = None  # For string length validation


@dataclass
class TR181Event:
    """TR181 event definition with associated parameters."""
    name: str
    path: str
    parameters: List[str]  # Event parameter paths
    description: Optional[str] = None


@dataclass
class TR181Function:
    """TR181 function definition with input/output parameters."""
    name: str
    path: str
    input_parameters: List[str]
    output_parameters: List[str]
    description: Optional[str] = None


@dataclass
class TR181Node:
    """Complete TR181 node representation with all metadata and relationships."""
    path: str                    # Full parameter path (e.g., "Device.WiFi.Radio.1.Channel")
    name: str                    # Parameter name
    data_type: str              # string, int, boolean, dateTime, etc.
    access: AccessLevel         # read-only, read-write, write-only
    value: Optional[Any] = None # Current value (if available)
    description: Optional[str] = None  # Parameter description
    parent: Optional[str] = None       # Parent node path
    children: Optional[List[str]] = None  # Child node paths
    is_object: bool = False     # True if this is an object node
    is_custom: bool = False     # True if this is a custom (non-standard) node
    value_range: Optional[ValueRange] = None  # Value constraints and validation rules
    events: Optional[List[TR181Event]] = None  # Associated events
    functions: Optional[List[TR181Function]] = None  # Associated functions

    def __post_init__(self):
        """Validate node data after initialization."""
        if not self.path:
            raise ValueError("TR181Node path cannot be empty")
        if not self.name:
            raise ValueError("TR181Node name cannot be empty")
        if not self.data_type:
            raise ValueError("TR181Node data_type cannot be empty")
        if not isinstance(self.access, AccessLevel):
            raise ValueError("TR181Node access must be an AccessLevel enum")
        
        # Ensure children list is initialized if None
        if self.children is None:
            self.children = []
        
        # Ensure events list is initialized if None
        if self.events is None:
            self.events = []
            
        # Ensure functions list is initialized if None
        if self.functions is None:
            self.functions = []


@dataclass
class NodeDifference:
    """Represents a difference between two TR181 nodes."""
    path: str
    property: str
    source1_value: Any
    source2_value: Any
    severity: Severity


@dataclass
class ComparisonSummary:
    """Summary statistics for a comparison operation."""
    total_nodes_source1: int
    total_nodes_source2: int
    common_nodes: int
    differences_count: int


@dataclass
class ComparisonResult:
    """Complete result of comparing two TR181 node sources."""
    only_in_source1: List[TR181Node]
    only_in_source2: List[TR181Node]
    differences: List[NodeDifference]
    summary: ComparisonSummary