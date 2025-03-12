#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Written by Daniel Rollings

"""
Command-line interface for the yamake build system.
"""

import os
import sys
import argparse
import importlib.util
import logging
from typing import List

from core import registry, run_targets, load_plugin

# Setup logging
logger = logging.getLogger(__name__)


def parse_args(args=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="yamake: A decorator-based build system with powerful dependency resolution.")

    parser.add_argument("targets", nargs="*", help="Target(s) to build")

    parser.add_argument("-f", "--file", dest="build_file", help="Python file containing build definitions")

    parser.add_argument("-c", "--clean", action="store_true", help="Clean targets instead of building them")

    parser.add_argument("-n", "--dry-run", action="store_true", help="Don't actually build, just show what would be built")

    parser.add_argument("-p", "--plugin", dest="plugins", action="append", help="Load plugin modules")

    parser.add_argument("-l", "--list", action="store_true", help="List all available targets")

    parser.add_argument("-d", "--debug", action="store_true", help="Show debug output")

    return parser.parse_args(args)


def load_build_file(file_path):
    """
    Load a Python file containing build definitions.

    Args:
        file_path: Path to the Python file

    Returns:
        True if the file was loaded successfully, False otherwise
    """
    if not file_path:
        # If no file is specified, try common names
        for common_name in ["yamakefile.py", "Yamakefile.py", "build.py"]:
            if os.path.exists(common_name):
                file_path = common_name
                break
        else:
            logger.error("No build file specified and no default build file found")
            return False

    try:
        # Load the file as a module
        spec = importlib.util.spec_from_file_location("yamakefile", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True
    except Exception as e:
        logger.error(f"Failed to load build file {file_path}: {e}")
        return False


def list_targets():
    """List all available targets with their dependencies."""
    targets = registry.get_targets()
    default_targets = registry.get_default_targets()
    essential_targets = registry.get_essential_targets()

    print("Available targets:")
    print("=================")

    for target in sorted(targets, key=lambda t: t.name):
        # Show special target types
        annotations = []
        if target in default_targets:
            annotations.append("default")
        if target in essential_targets:
            annotations.append("essential")
        if target.is_abstract():
            annotations.append("abstract")

        annotation_str = f" ({', '.join(annotations)})" if annotations else ""

        print(f"{target.name}{annotation_str}")

        # Show dependencies
        if target.depends:
            deps = ", ".join(d.name for d in target.depends)
            print(f"  depends: {deps}")

        # Show what this provides
        if target.provides:
            provides = ", ".join(p.name for p in target.provides)
            print(f"  provides: {provides}")

        # Show output file if any
        if target.exists:
            print(f"  output: {target.exists}")

        print()

    # Show default targets if any
    if default_targets:
        print(f"Default targets: {', '.join(t.name for t in default_targets)}")


def main(args=None):
    """Main entry point for the yamake command-line tool."""
    args = parse_args(args)

    # Set up logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(message)s")

    # Load plugin modules if specified
    if args.plugins:
        for plugin in args.plugins:
            load_plugin(plugin)

    # Load the build file
    if not load_build_file(args.build_file):
        return 1

    # List targets if requested
    if args.list:
        list_targets()
        return 0

    # Run the specified targets
    success, messages = run_targets(args.targets, clean_mode=args.clean, dry_run=args.dry_run, debug=args.debug)

    # Print messages
    for msg in messages:
        print(msg)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
