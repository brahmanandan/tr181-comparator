"""Tests for migration utilities."""

import unittest
import json
import yaml
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from tr181_comparator.migration import ConfigMigrator, ScriptMigrator, migrate_directory


class TestConfigMigrator(unittest.TestCase):
    """Test the ConfigMigrator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.migrator = ConfigMigrator(backup=False)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def test_migrate_json_file(self):
        """Test migrating a JSON configuration file."""
        # Create test JSON file
        test_data = {
            "subset_configs": [
                {
                    "name": "Test Subset",
                    "description": "Test subset config",
                    "subset_file_path": "test.json"
                }
            ],
            "subset_validation": {
                "enabled": True
            }
        }
        
        file_path = Path(self.temp_dir.name) / "test_config.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        # Migrate the file
        result = self.migrator.migrate_file(file_path)
        self.assertTrue(result)
        
        # Check the migrated file
        with open(file_path, 'r', encoding='utf-8') as f:
            migrated_data = json.load(f)
        
        # Verify the keys were migrated
        self.assertIn("operator_requirements", migrated_data)
        self.assertNotIn("subset_configs", migrated_data)
        self.assertEqual(len(migrated_data["operator_requirements"]), 1)
        self.assertEqual(migrated_data["operator_requirements"][0]["name"], "Test Subset")
        self.assertIn("file_path", migrated_data["operator_requirements"][0])
        self.assertNotIn("subset_file_path", migrated_data["operator_requirements"][0])
        self.assertIn("operator_requirement_validation", migrated_data)
        self.assertNotIn("subset_validation", migrated_data)
    
    def test_migrate_yaml_file(self):
        """Test migrating a YAML configuration file."""
        # Create test YAML file
        test_data = """
subset_configs:
  - name: Test Subset
    description: Test subset config
    subset_file_path: test.yaml
subset_validation:
  enabled: true
"""
        
        file_path = Path(self.temp_dir.name) / "test_config.yaml"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(test_data)
        
        # Migrate the file
        result = self.migrator.migrate_file(file_path)
        self.assertTrue(result)
        
        # Check the migrated file
        with open(file_path, 'r', encoding='utf-8') as f:
            migrated_data = yaml.safe_load(f)
        
        # Verify the keys were migrated
        self.assertIn("operator_requirements", migrated_data)
        self.assertNotIn("subset_configs", migrated_data)
        self.assertEqual(len(migrated_data["operator_requirements"]), 1)
        self.assertEqual(migrated_data["operator_requirements"][0]["name"], "Test Subset")
        self.assertIn("file_path", migrated_data["operator_requirements"][0])
        self.assertNotIn("subset_file_path", migrated_data["operator_requirements"][0])
        self.assertIn("operator_requirement_validation", migrated_data)
        self.assertNotIn("subset_validation", migrated_data)
    
    def test_migrate_invalid_file(self):
        """Test migrating an invalid file."""
        # Create invalid JSON file
        file_path = Path(self.temp_dir.name) / "invalid.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("This is not valid JSON")
        
        # Migrate the file
        result = self.migrator.migrate_file(file_path)
        self.assertFalse(result)
    
    def test_migrate_nonexistent_file(self):
        """Test migrating a nonexistent file."""
        file_path = Path(self.temp_dir.name) / "nonexistent.json"
        result = self.migrator.migrate_file(file_path)
        self.assertFalse(result)


class TestScriptMigrator(unittest.TestCase):
    """Test the ScriptMigrator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.migrator = ScriptMigrator(backup=False)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def test_migrate_python_file(self):
        """Test migrating a Python script."""
        # Create test Python file
        test_script = """
from tr181_comparator.extractors import SubsetManager
from tr181_comparator.config import SubsetConfig

def test_function():
    # Create a subset manager
    subset_manager = SubsetManager("test.json")
    
    # Create a subset config
    subset_config = SubsetConfig(
        name="Test",
        description="Test config",
        file_path="test.json"
    )
    
    # Call some methods
    result = app.compare_subset_vs_device(subset_file_path="test.json", device_config_path="device.json")
    is_valid = app.validate_subset("test.json")
    
    # Use CLI commands
    cmd = "tr181-compare subset-vs-device --subset-file test.json --device-config device.json"
"""
        
        file_path = Path(self.temp_dir.name) / "test_script.py"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(test_script)
        
        # Migrate the file
        result = self.migrator.migrate_file(file_path)
        self.assertTrue(result)
        
        # Check the migrated file
        with open(file_path, 'r', encoding='utf-8') as f:
            migrated_script = f.read()
        
        # Verify the terms were migrated
        self.assertIn("OperatorRequirementManager", migrated_script)
        self.assertNotIn("SubsetManager", migrated_script)
        self.assertIn("OperatorRequirementConfig", migrated_script)
        self.assertNotIn("SubsetConfig", migrated_script)
        self.assertIn("operator_requirement_manager", migrated_script)
        self.assertNotIn("subset_manager", migrated_script)
        self.assertIn("operator_requirement_config", migrated_script)
        self.assertNotIn("subset_config", migrated_script)
        self.assertIn("compare_operator_requirement_vs_device", migrated_script)
        self.assertNotIn("compare_subset_vs_device", migrated_script)
        self.assertIn("validate_operator_requirement", migrated_script)
        self.assertNotIn("validate_subset", migrated_script)
        self.assertIn("operator-requirement-vs-device", migrated_script)
        self.assertNotIn("subset-vs-device", migrated_script)
        self.assertIn("--operator-requirement-file", migrated_script)
        self.assertNotIn("--subset-file", migrated_script)
    
    def test_migrate_nonpython_file(self):
        """Test migrating a non-Python file."""
        file_path = Path(self.temp_dir.name) / "test.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("This is not a Python file")
        
        result = self.migrator.migrate_file(file_path)
        self.assertFalse(result)
    
    def test_migrate_nonexistent_file(self):
        """Test migrating a nonexistent file."""
        file_path = Path(self.temp_dir.name) / "nonexistent.py"
        result = self.migrator.migrate_file(file_path)
        self.assertFalse(result)


class TestDirectoryMigration(unittest.TestCase):
    """Test the migrate_directory function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        
        # Create test directory structure
        self.sub_dir = self.root_dir / "subdir"
        self.sub_dir.mkdir()
        
        # Create test files
        self.json_file = self.root_dir / "config.json"
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump({"subset_configs": []}, f)
        
        self.yaml_file = self.root_dir / "config.yaml"
        with open(self.yaml_file, 'w', encoding='utf-8') as f:
            f.write("subset_configs: []")
        
        self.py_file = self.root_dir / "script.py"
        with open(self.py_file, 'w', encoding='utf-8') as f:
            f.write("from tr181_comparator.extractors import SubsetManager")
        
        self.sub_json_file = self.sub_dir / "subconfig.json"
        with open(self.sub_json_file, 'w', encoding='utf-8') as f:
            json.dump({"subset_validation": True}, f)
        
        self.txt_file = self.root_dir / "readme.txt"
        with open(self.txt_file, 'w', encoding='utf-8') as f:
            f.write("This is a text file")
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def test_migrate_directory_nonrecursive(self):
        """Test migrating a directory non-recursively."""
        successful, failed = migrate_directory(
            self.root_dir, recursive=False, backup=False
        )
        
        # Should migrate 3 files in root dir (json, yaml, py)
        self.assertEqual(successful, 3)
        self.assertEqual(failed, 0)
        
        # Check that root files were migrated
        with open(self.json_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            self.assertIn("operator_requirements", json_data)
            self.assertNotIn("subset_configs", json_data)
        
        with open(self.yaml_file, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
            self.assertIn("operator_requirements", yaml_data)
            self.assertNotIn("subset_configs", yaml_data)
        
        with open(self.py_file, 'r', encoding='utf-8') as f:
            py_content = f.read()
            self.assertIn("OperatorRequirementManager", py_content)
            self.assertNotIn("SubsetManager", py_content)
        
        # Check that subdir file was NOT migrated
        with open(self.sub_json_file, 'r', encoding='utf-8') as f:
            sub_json_data = json.load(f)
            self.assertIn("subset_validation", sub_json_data)
            self.assertNotIn("operator_requirement_validation", sub_json_data)
    
    def test_migrate_directory_recursive(self):
        """Test migrating a directory recursively."""
        successful, failed = migrate_directory(
            self.root_dir, recursive=True, backup=False
        )
        
        # Should migrate 4 files (3 in root + 1 in subdir)
        self.assertEqual(successful, 4)
        self.assertEqual(failed, 0)
        
        # Check that subdir file was migrated
        with open(self.sub_json_file, 'r', encoding='utf-8') as f:
            sub_json_data = json.load(f)
            self.assertIn("operator_requirement_validation", sub_json_data)
            self.assertNotIn("subset_validation", sub_json_data)
    
    def test_migrate_directory_with_filter(self):
        """Test migrating a directory with file type filter."""
        successful, failed = migrate_directory(
            self.root_dir, file_types=['.json'], recursive=True, backup=False
        )
        
        # Should migrate 2 JSON files (1 in root + 1 in subdir)
        self.assertEqual(successful, 2)
        self.assertEqual(failed, 0)
        
        # Check that JSON files were migrated
        with open(self.json_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            self.assertIn("operator_requirements", json_data)
        
        with open(self.sub_json_file, 'r', encoding='utf-8') as f:
            sub_json_data = json.load(f)
            self.assertIn("operator_requirement_validation", sub_json_data)
        
        # Check that YAML and Python files were NOT migrated
        with open(self.yaml_file, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
            self.assertIn("subset_configs", yaml_data)
            self.assertNotIn("operator_requirements", yaml_data)
        
        with open(self.py_file, 'r', encoding='utf-8') as f:
            py_content = f.read()
            self.assertIn("SubsetManager", py_content)
            self.assertNotIn("OperatorRequirementManager", py_content)
    
    def test_migrate_nonexistent_directory(self):
        """Test migrating a nonexistent directory."""
        nonexistent_dir = self.root_dir / "nonexistent"
        successful, failed = migrate_directory(nonexistent_dir)
        self.assertEqual(successful, 0)
        self.assertEqual(failed, 0)


if __name__ == '__main__':
    unittest.main()