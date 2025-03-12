"""
Unit tests for the yamake.cli module.
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path

import yamake
from cli import main, parse_args
from core import registry


@pytest.fixture
def clean_registry():
    """Fixture to clean the registry before and after each test."""
    registry.clear()
    yield registry
    registry.clear()


def test_parse_args():
    """Test command line argument parsing."""
    # Test with no arguments
    args = parse_args([])
    assert args.targets == []
    assert not args.clean
    assert not args.dry_run

    # Test with targets
    args = parse_args(["target1", "target2"])
    assert args.targets == ["target1", "target2"]

    # Test with options
    args = parse_args(["-c", "-n", "-d", "target1"])
    assert args.clean
    assert args.dry_run
    assert args.debug
    assert args.targets == ["target1"]

    # Test with file option
    args = parse_args(["-f", "mybuild.py"])
    assert args.build_file == "mybuild.py"


def test_cli_list_targets(clean_registry, capsys):
    """Test listing targets from the CLI."""

    # Create some test targets
    @yamake.target()
    def basic_target():
        pass

    @yamake.default
    @yamake.target(depends=["basic_target"])
    def default_target():
        pass

    @yamake.essential
    @yamake.target()
    def essential_target():
        pass

    # Call the CLI with list option
    sys.argv = ["yamake", "-l"]
    try:
        main()
    except SystemExit:
        pass

    # Check output
    captured = capsys.readouterr()
    output = captured.out

    assert "basic_target" in output
    assert "default_target (default)" in output
    assert "essential_target (essential)" in output
    assert "depends: basic_target" in output


def test_cli_build_file_loading(clean_registry):
    """Test loading a build file from the CLI."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        build_file = Path(tmp_dir) / "build.py"

        # Create a simple build file
        with open(build_file, "w") as f:
            f.write(
                """
import yamake

@yamake.target()
def test_target():
    print("Target executed!")
    return {"status": "complete"}
"""
            )

        # Call the CLI with the file
        sys.argv = ["yamake", "-f", str(build_file), "test_target"]
        try:
            exit_code = main()
        except SystemExit as e:
            exit_code = e.code

        # Check that the target was registered
        assert "test_target" in registry.targets
        assert exit_code == 0


def test_cli_dry_run(clean_registry, capsys):
    """Test dry run mode from CLI."""

    # Create a test target that shouldn't be executed
    @yamake.target()
    def test_target():
        # This shouldn't be executed in dry run mode
        raise Exception("This should not be executed")

    # Call the CLI with dry run option
    sys.argv = ["yamake", "-n", "test_target"]
    try:
        exit_code = main()
    except SystemExit as e:
        exit_code = e.code

    # Check output
    captured = capsys.readouterr()
    output = captured.out

    assert "Would execute target: test_target" in output
    assert exit_code == 0


def test_cli_clean_mode(clean_registry, capsys):
    """Test clean mode from CLI."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "test.txt"

        # Create a test target with a clean function
        @yamake.target(exists=str(test_file))
        def test_target():
            with open(test_file, "w") as f:
                f.write("Test content")
            return {"status": "created"}

        @yamake.clean
        def clean_test_target():
            if test_file.exists():
                os.remove(test_file)
            return {"status": "cleaned"}

        # First build the target
        sys.argv = ["yamake", "test_target"]
        try:
            main()
        except SystemExit:
            pass

        assert test_file.exists()

        # Then clean it
        sys.argv = ["yamake", "-c", "test_target"]
        try:
            exit_code = main()
        except SystemExit as e:
            exit_code = e.code

        # Check output and file
        captured = capsys.readouterr()
        output = captured.out

        assert "Target cleaned" in output
        assert not test_file.exists()
        assert exit_code == 0
