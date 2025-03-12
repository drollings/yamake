"""
Unit tests for the yamake.core module.
"""

import os
import time
import pytest
import tempfile
from pathlib import Path

import yamake
from yamake.core import registry, Target


@pytest.fixture
def clean_registry():
    """Fixture to clean the registry before and after each test."""
    registry.clear()
    yield registry
    registry.clear()


def test_target_decorator(clean_registry):
    """Test that the target decorator registers a function correctly."""

    @yamake.target(depends=["dep1", "dep2"], provides=["out1"])
    def my_target():
        """This is a test target."""
        return {"results": "success"}

    # Check the target was registered
    assert "my_target" in clean_registry.targets
    target = clean_registry.targets["my_target"]

    # Basic properties
    assert target.name == "my_target"
    assert target.action_func == my_target

    # Dependencies and provides are still strings at this point
    assert target.depends == {"dep1", "dep2"}
    assert target.provides == {"out1"}


def test_task_decorator(clean_registry):
    """Test that the task decorator works as a simplified target."""

    @yamake.task(depends=["dep1"])
    def simple_task():
        """This is a simple task."""
        return {"status": "complete"}

    # Check the target was registered
    assert "simple_task" in clean_registry.targets
    target = clean_registry.targets["simple_task"]

    # Basic properties
    assert target.name == "simple_task"
    assert target.action_func == simple_task
    assert target.depends == {"dep1"}
    assert not target.provides
    assert not target.essential


def test_default_decorator(clean_registry):
    """Test that the default decorator marks a target as default."""

    @yamake.target()
    def normal_target():
        pass

    @yamake.default
    @yamake.target()
    def default_target():
        pass

    # Check that only the default target is marked as default
    assert not clean_registry.targets["normal_target"].is_default
    assert clean_registry.targets["default_target"].is_default
    assert "default_target" in clean_registry.default_targets


def test_essential_decorator(clean_registry):
    """Test that the essential decorator marks a target as essential."""

    @yamake.target()
    def normal_target():
        pass

    @yamake.essential
    @yamake.target()
    def essential_target():
        pass

    # Check that only the essential target is marked as essential
    assert not clean_registry.targets["normal_target"].essential
    assert clean_registry.targets["essential_target"].essential
    assert "essential_target" in clean_registry.essentials


def test_provides_decorator(clean_registry):
    """Test that the provides decorator adds provided artifacts."""

    @yamake.target()
    def base_target():
        pass

    @yamake.provides("feature1", "feature2")
    @yamake.target()
    def provider_target():
        pass

    # Check that provides were added
    assert not clean_registry.targets["base_target"].provides
    assert clean_registry.targets["provider_target"].provides == {"feature1", "feature2"}


def test_clean_decorator(clean_registry):
    """Test that the clean decorator adds a clean function to a target."""

    @yamake.target()
    def build_target():
        return {"built": True}

    @yamake.clean
    def clean_build_target():
        return {"cleaned": True}

    # Check that the clean function was added to the target
    target = clean_registry.targets["build_target"]
    assert target.clean_func == clean_build_target


def test_dependency_resolution():
    """Test that dependencies are properly resolved."""
    registry.clear()

    # Create a simple linear dependency chain
    @yamake.target()
    def target_c():
        return {"status": "C built"}

    @yamake.target(depends=["target_c"])
    def target_b():
        return {"status": "B built"}

    @yamake.target(depends=["target_b"])
    def target_a():
        return {"status": "A built"}

    # Run the target resolution
    success, messages = yamake.run_targets(["target_a"], dry_run=True)

    # Check that the targets are resolved in the correct order
    assert success
    assert "target_c" in str(messages)
    assert "target_b" in str(messages)
    assert "target_a" in str(messages)

    # Check that the order is correct (c before b before a)
    c_pos = str(messages).find("target_c")
    b_pos = str(messages).find("target_b")
    a_pos = str(messages).find("target_a")
    assert c_pos < b_pos < a_pos

    registry.clear()


def test_diamond_dependencies():
    """Test that diamond dependencies are handled correctly."""
    registry.clear()

    # Create a diamond dependency graph:
    #       A
    #      / \
    #     B   C
    #      \ /
    #       D

    @yamake.target()
    def target_d():
        return {"status": "D built"}

    @yamake.target(depends=["target_d"])
    def target_c():
        return {"status": "C built"}

    @yamake.target(depends=["target_d"])
    def target_b():
        return {"status": "B built"}

    @yamake.target(depends=["target_b", "target_c"])
    def target_a():
        return {"status": "A built"}

    # Run the target resolution
    success, messages = yamake.run_targets(["target_a"], dry_run=True)

    # Check that each target appears only once
    assert success
    assert str(messages).count("target_d") == 1
    assert str(messages).count("target_c") == 1
    assert str(messages).count("target_b") == 1
    assert str(messages).count("target_a") == 1

    # Check that D comes before B and C, and both come before A
    d_pos = str(messages).find("target_d")
    b_pos = str(messages).find("target_b")
    c_pos = str(messages).find("target_c")
    a_pos = str(messages).find("target_a")
    assert d_pos < b_pos
    assert d_pos < c_pos
    assert b_pos < a_pos
    assert c_pos < a_pos

    registry.clear()


def test_abstract_targets():
    """Test that abstract targets are handled correctly."""
    registry.clear()

    # Create an abstract target that's provided by a concrete target
    @yamake.target(name="abstract_feature")
    def abstract_feature():
        pass

    @yamake.target(provides=["abstract_feature"])
    def concrete_provider():
        return {"status": "Provider built"}

    @yamake.target(depends=["abstract_feature"])
    def consumer():
        return {"status": "Consumer built"}

    # Run the target resolution
    success, messages = yamake.run_targets(["consumer"], dry_run=True)

    # Check that the concrete provider is built, not the abstract target
    assert success
    assert "concrete_provider" in str(messages)
    assert "Consumer built" in str(messages)

    # And verify the build order
    provider_pos = str(messages).find("concrete_provider")
    consumer_pos = str(messages).find("consumer")
    assert provider_pos < consumer_pos

    registry.clear()


def test_timestamp_based_rebuilding():
    """Test that targets are only rebuilt when dependencies change."""
    registry.clear()

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = Path(tmp_dir) / "input.txt"
        output_file = Path(tmp_dir) / "output.txt"

        # Create initial input file
        with open(input_file, "w") as f:
            f.write("Initial content")

        # Define targets that use the files
        @yamake.target(exists=str(input_file))
        def input_target():
            pass

        @yamake.target(depends=["input_target"], exists=str(output_file), check_mtime=True)
        def output_target():
            # Create the output file
            with open(output_file, "w") as f:
                with open(input_file, "r") as in_f:
                    f.write(f"Processed: {in_f.read()}")
            return {"status": "Output generated"}

        # First build - should create the output file
        success, messages = yamake.run_targets(["output_target"])
        assert success
        assert "Output generated" in str(messages)
        assert output_file.exists()

        # Second build - should skip because nothing changed
        success, messages = yamake.run_targets(["output_target"])
        assert success
        assert "up to date" in str(messages)

        # Modify the input file with a small delay to ensure timestamp difference
        time.sleep(0.1)
        with open(input_file, "w") as f:
            f.write("Modified content")

        # Third build - should rebuild because input changed
        success, messages = yamake.run_targets(["output_target"])
        assert success
        assert "Output generated" in str(messages)

        # Verify the output contains the new content
        with open(output_file, "r") as f:
            content = f.read()
        assert "Modified content" in content

    registry.clear()


def test_clean_function_execution():
    """Test that clean functions are executed correctly."""
    registry.clear()

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_file = Path(tmp_dir) / "output.txt"

        # Define a target with a clean function
        @yamake.target(exists=str(output_file))
        def build_target():
            with open(output_file, "w") as f:
                f.write("Built content")
            return {"status": "Target built"}

        @yamake.clean
        def clean_build_target():
            if output_file.exists():
                os.remove(output_file)
            return {"status": "Target cleaned"}

        # First build - should create the file
        success, messages = yamake.run_targets(["build_target"])
        assert success
        assert output_file.exists()

        # Clean - should remove the file
        success, messages = yamake.run_targets(["build_target"], clean_mode=True)
        assert success
        assert "Target cleaned" in str(messages)
        assert not output_file.exists()

    registry.clear()
