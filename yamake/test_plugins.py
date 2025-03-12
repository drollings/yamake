"""
Unit tests for the yamake plugin system.
"""

import os
import pytest
import tempfile
from pathlib import Path

import yamake
from yamake.core import registry, load_plugin


@pytest.fixture
def clean_registry():
    """Fixture to clean the registry before and after each test."""
    registry.clear()
    yield registry
    registry.clear()


def test_plugin_loading(clean_registry):
    """Test loading a plugin module."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        plugin_path = Path(tmp_dir) / "test_plugin.py"

        # Create a simple plugin
        with open(plugin_path, "w") as f:
            f.write(
                """
# Test plugin for yamake

def initialize(registry):
    \"\"\"Initialize the plugin.\"\"\"
    # Register a new target from the plugin
    from yamake.core import Target
    
    target = Target(
        name="plugin_target",
        action_func=lambda: {"status": "Plugin target executed"}
    )
    registry.register(target)
    return {"plugin_registered": True}

def custom_function():
    \"\"\"Custom function provided by the plugin.\"\"\"
    return "Plugin function called"
"""
            )

        # Add the temporary directory to Python path
        import sys

        sys.path.insert(0, tmp_dir)

        try:
            # Load the plugin
            plugin = load_plugin("test_plugin")

            # Check that the plugin was loaded
            assert plugin is not None
            assert hasattr(plugin, "initialize")
            assert hasattr(plugin, "custom_function")

            # Check that the plugin's target was registered
            assert "plugin_target" in registry.targets

            # Check that we can call the plugin's custom function
            assert plugin.custom_function() == "Plugin function called"
        finally:
            # Clean up
            sys.path.remove(tmp_dir)


def test_plugin_customization(clean_registry):
    """Test that plugins can customize the build process."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        plugin_path = Path(tmp_dir) / "custom_plugin.py"

        # Create a plugin that adds a custom target type
        with open(plugin_path, "w") as f:
            f.write(
                """
# Custom plugin that adds a special target type

def initialize(registry):
    \"\"\"Initialize the plugin.\"\"\"
    global _registry
    _registry = registry
    return {"initialized": True}

# Define a custom decorator for creating special targets
def special_target(name=None, priority=0):
    \"\"\"Decorator for special high-priority targets.\"\"\"
    def decorator(func):
        from yamake.core import Target
        nonlocal name
        if name is None:
            name = func.__name__
            
        # Create target with special properties
        target = Target(
            name=name,
            action_func=func,
            essential=True
        )
        
        # Add custom attribute
        target.priority = priority
        
        # Register the target
        _registry.register(target)
        return func
    return decorator
"""
            )

        # Add the temporary directory to Python path
        import sys

        sys.path.insert(0, tmp_dir)

        try:
            # Load the plugin
            plugin = load_plugin("custom_plugin")
            assert plugin is not None

            # Use the plugin's custom decorator
            @plugin.special_target(priority=10)
            def high_priority_task():
                return {"status": "High priority task executed"}

            # Check that the target was registered
            assert "high_priority_task" in registry.targets
            target = registry.targets["high_priority_task"]

            # Check that the custom attribute was set
            assert hasattr(target, "priority")
            assert target.priority == 10

            # Check that the target is marked as essential
            assert target.essential
            assert "high_priority_task" in registry.essentials

        finally:
            # Clean up
            sys.path.remove(tmp_dir)
