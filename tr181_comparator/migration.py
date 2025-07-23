"""Migration utilities for TR181 comparator.

This module provides utilities for migrating from old terminology (subset)
to new terminology (operator requirement) in configuration files and scripts.
"""

import json
import yaml
import re
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union
import logging

# Configure logging
logger = logging.getLogger("tr181_migration")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class ConfigMigrator:
    """Migrates configuration files from old terminology to new terminology."""
    
    # Mapping of old keys to new keys
    KEY_MAPPING = {
        'subset_configs': 'operator_requirements',
        'subset_file_path': 'file_path',
        'subset_validation': 'operator_requirement_validation',
        'subset_manager': 'operator_requirement_manager',
        'subset_config': 'operator_requirement_config',
        'subset_nodes': 'operator_requirement_nodes',
        'subset_file': 'operator_requirement_file',
        'subset_vs_device': 'operator_requirement_vs_device',
        'validate_subset': 'validate_operator_requirement'
    }
    
    def __init__(self, backup: bool = True):
        """Initialize the config migrator.
        
        Args:
            backup: Whether to create backup files before migration
        """
        self.backup = backup
    
    def migrate_file(self, file_path: Union[str, Path]) -> bool:
        """Migrate a configuration file from old terminology to new terminology.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            True if migration was successful, False otherwise
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False
        
        # Create backup if requested
        if self.backup:
            backup_path = file_path.with_suffix(file_path.suffix + '.bak')
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
        
        try:
            # Determine file type
            if file_path.suffix.lower() in ['.yaml', '.yml']:
                return self._migrate_yaml_file(file_path)
            elif file_path.suffix.lower() == '.json':
                return self._migrate_json_file(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return False
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def _migrate_json_file(self, file_path: Path) -> bool:
        """Migrate a JSON configuration file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            True if migration was successful, False otherwise
        """
        try:
            # Load JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Migrate data
            migrated_data = self._migrate_dict(data)
            
            # Save migrated data
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(migrated_data, f, indent=2)
            
            logger.info(f"Successfully migrated JSON file: {file_path}")
            return True
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON file: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to migrate JSON file {file_path}: {e}")
            return False
    
    def _migrate_yaml_file(self, file_path: Path) -> bool:
        """Migrate a YAML configuration file.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            True if migration was successful, False otherwise
        """
        try:
            # Load YAML file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Migrate data
            migrated_data = self._migrate_dict(data)
            
            # Save migrated data
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(migrated_data, f, default_flow_style=False, indent=2)
            
            logger.info(f"Successfully migrated YAML file: {file_path}")
            return True
        except yaml.YAMLError:
            logger.error(f"Invalid YAML file: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to migrate YAML file {file_path}: {e}")
            return False
    
    def _migrate_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively migrate dictionary keys from old terminology to new terminology.
        
        Args:
            data: Dictionary to migrate
            
        Returns:
            Migrated dictionary
        """
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            # Check if key needs migration
            new_key = self.KEY_MAPPING.get(key, key)
            
            # Recursively migrate nested dictionaries and lists
            if isinstance(value, dict):
                result[new_key] = self._migrate_dict(value)
            elif isinstance(value, list):
                result[new_key] = self._migrate_list(value)
            else:
                result[new_key] = value
        
        return result
    
    def _migrate_list(self, data: List[Any]) -> List[Any]:
        """Recursively migrate lists containing dictionaries.
        
        Args:
            data: List to migrate
            
        Returns:
            Migrated list
        """
        result = []
        for item in data:
            if isinstance(item, dict):
                result.append(self._migrate_dict(item))
            elif isinstance(item, list):
                result.append(self._migrate_list(item))
            else:
                result.append(item)
        
        return result


class ScriptMigrator:
    """Migrates Python scripts from old terminology to new terminology."""
    
    # Mapping of old terms to new terms
    TERM_MAPPING = {
        'SubsetManager': 'OperatorRequirementManager',
        'SubsetConfig': 'OperatorRequirementConfig',
        'subset_manager': 'operator_requirement_manager',
        'subset_config': 'operator_requirement_config',
        'subset_file': 'operator_requirement_file',
        'subset_vs_device': 'operator_requirement_vs_device',
        'validate_subset': 'validate_operator_requirement',
        'extract_subset_nodes': 'extract_operator_requirement_nodes',
        'compare_subset_vs_device': 'compare_operator_requirement_vs_device',
        'subset_nodes': 'operator_requirement_nodes',
        'subset_validation': 'operator_requirement_validation'
    }
    
    # Regular expressions for more complex replacements
    REGEX_REPLACEMENTS = [
        # Replace function calls with arguments
        (r'compare_subset_vs_device\((.*?subset_file_path\s*=\s*["\'].*?["\'])', 
         r'compare_operator_requirement_vs_device(\1'),
        
        # Replace function calls with positional arguments
        (r'compare_subset_vs_device\(([^,)]*?),', 
         r'compare_operator_requirement_vs_device(\1,'),
        
        # Replace CLI commands in strings
        (r'(["\'])subset-vs-device(["\'])', 
         r'\1operator-requirement-vs-device\2'),
        
        # Replace CLI arguments in strings
        (r'(["\'])--subset-file(["\'])', 
         r'\1--operator-requirement-file\2'),
    ]
    
    def __init__(self, backup: bool = True):
        """Initialize the script migrator.
        
        Args:
            backup: Whether to create backup files before migration
        """
        self.backup = backup
    
    def migrate_file(self, file_path: Union[str, Path]) -> bool:
        """Migrate a Python script from old terminology to new terminology.
        
        Args:
            file_path: Path to the Python script
            
        Returns:
            True if migration was successful, False otherwise
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False
        
        # Only process Python files
        if file_path.suffix.lower() != '.py':
            logger.warning(f"Not a Python file: {file_path}")
            return False
        
        # Create backup if requested
        if self.backup:
            backup_path = file_path.with_suffix(file_path.suffix + '.bak')
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Apply migrations
            migrated_content = self._migrate_content(content)
            
            # Save migrated content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(migrated_content)
            
            logger.info(f"Successfully migrated Python script: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to migrate Python script {file_path}: {e}")
            return False
    
    def _migrate_content(self, content: str) -> str:
        """Migrate Python script content from old terminology to new terminology.
        
        Args:
            content: Python script content
            
        Returns:
            Migrated content
        """
        # Apply simple term replacements
        for old_term, new_term in self.TERM_MAPPING.items():
            content = content.replace(old_term, new_term)
        
        # Apply regex replacements
        for pattern, replacement in self.REGEX_REPLACEMENTS:
            content = re.sub(pattern, replacement, content)
        
        return content


def migrate_directory(directory_path: Union[str, Path], 
                    file_types: List[str] = ['.json', '.yaml', '.yml', '.py'],
                    recursive: bool = True,
                    backup: bool = True) -> Tuple[int, int]:
    """Migrate all supported files in a directory.
    
    Args:
        directory_path: Path to the directory
        file_types: List of file extensions to process
        recursive: Whether to process subdirectories
        backup: Whether to create backup files before migration
        
    Returns:
        Tuple of (successful_migrations, failed_migrations)
    """
    directory_path = Path(directory_path)
    if not directory_path.exists() or not directory_path.is_dir():
        logger.error(f"Directory not found: {directory_path}")
        return 0, 0
    
    config_migrator = ConfigMigrator(backup=backup)
    script_migrator = ScriptMigrator(backup=backup)
    
    successful = 0
    failed = 0
    
    # Process files in directory
    for file_path in directory_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in file_types:
            if file_path.suffix.lower() == '.py':
                success = script_migrator.migrate_file(file_path)
            else:
                success = config_migrator.migrate_file(file_path)
            
            if success:
                successful += 1
            else:
                failed += 1
        
        # Process subdirectories if recursive
        elif recursive and file_path.is_dir():
            sub_successful, sub_failed = migrate_directory(
                file_path, file_types, recursive, backup
            )
            successful += sub_successful
            failed += sub_failed
    
    return successful, failed


def main():
    """Command-line interface for migration utilities."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate TR181 comparator files from old terminology to new terminology"
    )
    parser.add_argument('path', help="Path to file or directory to migrate")
    parser.add_argument('--no-backup', action='store_true', 
                      help="Don't create backup files before migration")
    parser.add_argument('--recursive', action='store_true',
                      help="Process subdirectories recursively")
    parser.add_argument('--file-types', default='.json,.yaml,.yml,.py',
                      help="Comma-separated list of file extensions to process")
    parser.add_argument('--verbose', action='store_true',
                      help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Parse file types
    file_types = [ext if ext.startswith('.') else f'.{ext}' 
                for ext in args.file_types.split(',')]
    
    # Process path
    path = Path(args.path)
    if path.is_file():
        # Migrate single file
        if path.suffix.lower() == '.py':
            migrator = ScriptMigrator(backup=not args.no_backup)
            success = migrator.migrate_file(path)
        else:
            migrator = ConfigMigrator(backup=not args.no_backup)
            success = migrator.migrate_file(path)
        
        if success:
            logger.info(f"Successfully migrated file: {path}")
            return 0
        else:
            logger.error(f"Failed to migrate file: {path}")
            return 1
    elif path.is_dir():
        # Migrate directory
        successful, failed = migrate_directory(
            path, file_types, args.recursive, not args.no_backup
        )
        
        logger.info(f"Migration complete: {successful} files migrated successfully, {failed} files failed")
        return 0 if failed == 0 else 1
    else:
        logger.error(f"Path not found: {path}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())