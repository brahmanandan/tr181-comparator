# Design Document

## Overview

This design outlines the systematic approach to updating terminology throughout the TR-181 Node Comparator project from "Subset definitions" to "Operator Requirement definitions". The change affects multiple layers of the application including documentation, code, configuration, and user interfaces.

## Architecture

The terminology update will be implemented across several architectural layers:

1. **Documentation Layer**: README, API docs, user guides
2. **Code Layer**: Python modules, classes, functions, variables
3. **Configuration Layer**: Config files, examples, schemas
4. **Interface Layer**: CLI commands, API endpoints, error messages
5. **Test Layer**: Test files, test data, test documentation

## Components and Interfaces

### Documentation Components
- **README.md**: Primary project documentation
- **API Documentation**: Code docstrings and generated docs
- **User Guides**: Documentation in docs/ directory
- **Example Files**: Configuration examples and usage samples

### Code Components
- **SubsetManager Class**: Rename to OperatorRequirementManager
- **SubsetConfig Class**: Rename to OperatorRequirementConfig
- **CLI Commands**: Update subset-related commands
- **Variable Names**: Update subset-related variable names
- **Method Names**: Update subset-related method names

### Configuration Components
- **File Extensions**: Consider .yaml/.json for operator requirements
- **Configuration Keys**: Update configuration field names
- **Example Configurations**: Update all example files

### Interface Components
- **CLI Commands**: 
  - `subset-vs-device` → `operator-requirement-vs-device`
  - `validate-subset` → `validate-operator-requirement`
- **API Methods**: Update method names in TR181ComparatorApp
- **Error Messages**: Update all user-facing messages

## Data Models

### Current Model Structure
```python
class SubsetConfig:
    name: str
    file_path: str
    nodes: List[SubsetNode]

class SubsetManager:
    def __init__(self, subset_file_path: str)
    def extract(self) -> List[TR181Node]
    def validate(self) -> bool
```

### Updated Model Structure
```python
class OperatorRequirementConfig:
    name: str
    file_path: str
    nodes: List[OperatorRequirementNode]

class OperatorRequirementManager:
    def __init__(self, operator_requirement_file_path: str)
    def extract(self) -> List[TR181Node]
    def validate(self) -> bool
```

## Error Handling

### Error Message Updates
- Update all error messages to use "operator requirement" terminology
- Maintain error codes and severity levels
- Update error context information

### Validation Updates
- Update validation error messages
- Update configuration validation logic
- Maintain backward compatibility where possible

## Testing Strategy

### Test Categories
1. **Unit Tests**: Update test names and test data
2. **Integration Tests**: Update test scenarios
3. **CLI Tests**: Update command testing
4. **Documentation Tests**: Verify terminology consistency

### Test Data Updates
- Update example configuration files
- Update test fixture data
- Update expected output in tests

### Backward Compatibility Testing
- Ensure existing configurations still work with deprecation warnings
- Test migration path for existing users

## Migration Strategy

### Phase 1: Code Updates
1. Update class names and method names
2. Update variable names and constants
3. Update docstrings and comments
4. Add deprecation warnings for old terminology

### Phase 2: Interface Updates
1. Update CLI command names (with aliases for backward compatibility)
2. Update API method names
3. Update configuration field names
4. Update error messages

### Phase 3: Documentation Updates
1. Update README.md
2. Update API documentation
3. Update user guides
4. Update example configurations

### Phase 4: Testing and Validation
1. Update all test files
2. Update test data and fixtures
3. Run comprehensive testing
4. Validate documentation accuracy

## Backward Compatibility

### Deprecation Strategy
- Maintain old CLI command names as deprecated aliases
- Add deprecation warnings for old configuration keys
- Provide migration guide for users

### Configuration Migration
- Support both old and new configuration formats
- Provide automatic migration utility
- Clear migration documentation