# Migration Guide: Subset to Operator Requirement Terminology

This guide helps you migrate your code and configurations from the old "Subset" terminology to the new "Operator Requirement" terminology.

## Overview

The TR-181 Node Comparator has updated its terminology to better reflect industry standards. The term "Subset definitions" has been replaced with "Operator Requirement definitions" throughout the codebase, configuration files, and documentation.

## Automatic Migration

The easiest way to migrate your code and configuration files is to use the built-in migration utility:

```bash
# Migrate a single file
python -m tr181_comparator.migration path/to/your/file.json

# Migrate a directory (non-recursive)
python -m tr181_comparator.migration path/to/your/directory

# Migrate a directory and all subdirectories
python -m tr181_comparator.migration path/to/your/directory --recursive

# Migrate without creating backup files
python -m tr181_comparator.migration path/to/your/directory --no-backup

# Specify file types to migrate
python -m tr181_comparator.migration path/to/your/directory --file-types .json,.py,.yaml
```

## Manual Migration

If you prefer to manually update your code and configurations, follow these guidelines:

### Python Code Changes

| Old Term | New Term |
|----------|----------|
| `SubsetManager` | `OperatorRequirementManager` |
| `SubsetConfig` | `OperatorRequirementConfig` |
| `subset_manager` | `operator_requirement_manager` |
| `subset_config` | `operator_requirement_config` |
| `subset_file` | `operator_requirement_file` |
| `subset_vs_device` | `operator_requirement_vs_device` |
| `validate_subset` | `validate_operator_requirement` |
| `extract_subset_nodes` | `extract_operator_requirement_nodes` |
| `compare_subset_vs_device` | `compare_operator_requirement_vs_device` |

### Configuration File Changes

| Old Key | New Key |
|---------|---------|
| `subset_configs` | `operator_requirements` |
| `subset_file_path` | `file_path` |
| `subset_validation` | `operator_requirement_validation` |

### CLI Command Changes

| Old Command | New Command |
|-------------|-------------|
| `subset-vs-device` | `operator-requirement-vs-device` |
| `validate-subset` | `validate-operator-requirement` |

### CLI Argument Changes

| Old Argument | New Argument |
|--------------|--------------|
| `--subset-file` | `--operator-requirement-file` |

## Backward Compatibility

For backward compatibility, the old terminology is still supported but will generate deprecation warnings. These warnings will help you identify code that needs to be updated.

### Deprecation Warnings

When using deprecated terminology, you will see warnings like:

```
DeprecationWarning: Class SubsetManager is deprecated. Use OperatorRequirementManager instead.
DeprecationWarning: Function validate_subset_file is deprecated. Use validate_operator_requirement_file instead.
DeprecationWarning: Argument '--subset-file' is deprecated. Use '--operator-requirement-file' instead.
```

### Handling Deprecation Warnings

To suppress deprecation warnings temporarily while you migrate your code, you can use:

```python
import warnings

# Suppress all deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Or suppress specific deprecation warnings
warnings.filterwarnings("ignore", message=".*SubsetManager.*", category=DeprecationWarning)
```

However, it's recommended to update your code to use the new terminology rather than suppressing the warnings.

## Testing After Migration

After migrating your code and configurations, it's important to test thoroughly:

1. Run all unit tests to ensure functionality is preserved
2. Test CLI commands with the new terminology
3. Verify that configuration files are correctly loaded
4. Check that your custom scripts work with the new terminology

## Need Help?

If you encounter any issues during migration, please:

1. Check the error messages for specific guidance
2. Refer to the API documentation for the new class and method names
3. Contact support if you need additional assistance