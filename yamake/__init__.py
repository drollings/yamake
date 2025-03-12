"""
yamake: A declarative, decorator-based build system with powerful dependency resolution.

This module provides decorators and functions for defining build targets and their
dependencies in Python, inspired by the make/ninja build systems but with a more
pythonic interface.
"""

from .core import (
    target,
    task,
    default,
    provides,
    essential,
    clean,
    registry,
    run_targets,
    load_plugin,
    get_targets,
)

__version__ = "0.1.0"
__all__ = [
    "target",
    "task",
    "default",
    "provides",
    "essential",
    "clean",
    "registry",
    "run_targets",
    "load_plugin",
    "get_targets",
]
