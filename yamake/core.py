"""
Core functionality for the yamake build system.

This module contains the decorator implementations, index, and dependency resolution
algorithms that power the yamake build system.
"""

import os
import sys
import time
import inspect
import logging
import functools
from typing import Dict, List, Set, Callable, Optional, Union, Any, Tuple
from collections import defaultdict
from itertools import chain

# Setup logging
logger = logging.getLogger(__name__)

# Colors for terminal output
RED = "\033[1;31m"
GRN = "\033[1;32m"
YEL = "\033[1;33m"
BLU = "\033[1;34m"
MAG = "\033[0;35m"
CYN = "\033[0;36m"
WHI = "\033[1;37m"
NRM = "\033[0m"

ERROR = f"[{RED}ERROR{NRM}]"
WARNING = f"[{YEL}WARNING{NRM}]"
SUCCESS = f"[{GRN}SUCCESS{NRM}]"
DEBUG = f"[{MAG}DEBUG{NRM}]"
INFO = f"[{BLU}INFO{NRM}]"
EXEC = f"[{CYN}EXEC{NRM}]"
START = f"[{WHI}START{NRM}]"


# Target index - global state to track all registered targets
class TargetIndex:
    """TargetIndex for tracking all build targets."""

    def __init__(self):
        self.targets = {}  # name -> Target object
        self.default_targets = set()
        self.essentials = set()
        self.plugins = []

    def register(self, target):
        """Register a target in the global index."""
        if target.name in self.targets:
            logger.warning(f"{WARNING} Overwriting existing target: {target.name}")
        self.targets[target.name] = target
        if target.essential:
            self.essentials.add(target.name)
        if target.is_default:
            self.default_targets.add(target.name)
        return target

    def get(self, name):
        """Get a target by name."""
        return self.targets.get(name)

    def get_targets(self):
        """Get all registered targets."""
        return list(self.targets.values())

    def get_default_targets(self):
        """Get all default targets."""
        return [self.targets[name] for name in self.default_targets]

    def get_essential_targets(self):
        """Get all essential targets."""
        return [self.targets[name] for name in self.essentials]

    def clear(self):
        """Clear the index."""
        self.targets.clear()
        self.default_targets.clear()
        self.essentials.clear()
        self.plugins.clear()


# Create a global index
index = TargetIndex()


class Target:
    """Represents a build target with dependencies and actions."""

    def __init__(
        self,
        name: str,
        action_func: Callable = None,
        depends: List[str] = None,
        provides: List[str] = None,
        exists_in_fs: str = None,
        essential: bool = False,
        clean_func: Callable = None,
        check_mtime: bool = False,
        is_default: bool = False,
        is_abstract: bool = False,
    ):
        self.name = name
        self.action_func = action_func
        self.depends = set(depends) if depends else set()
        self.provides = set(provides) if provides else set()
        self.exists_in_fs = exists_in_fs
        self.essential = essential
        self.clean_func = clean_func
        self.check_mtime = check_mtime
        self.is_default = is_default
        self._is_abstract = is_abstract
        self.mtime = None

    def __repr__(self):
        return f"Target(name='{self.name}')"

    def resolve_dependencies(self, targets_dict):
        """Resolve string dependencies to actual Target objects."""
        self.depends = {targets_dict[d] for d in self.depends if d in targets_dict}
        self.provides = {targets_dict[p] for p in self.provides if p in targets_dict}

    def get_mtime(self):
        """Get the modification time of the target's output file if it exists_in_fs."""
        if not self.exists_in_fs:
            return None

        if os.path.exists(self.exists_in_fs):
            if self.check_mtime:
                self.mtime = os.stat(self.exists_in_fs).st_mtime
            else:
                self.mtime = 1.0
            return self.mtime
        return None

    def execute(self, dry_run=False):
        """Execute the target's action function if needed."""
        if dry_run:
            return True, f"Would execute target: {self.name}"

        if self.action_func:
            try:
                result = self.action_func()
                if isinstance(result, dict):
                    # Allow the action to update the target properties
                    for key, value in result.items():
                        if hasattr(self, key):
                            setattr(self, key, value)
                return True, f"Successfully executed target: {self.name}"
            except Exception as e:
                return False, f"Failed to execute target {self.name}: {str(e)}"
        return True, f"No action for target: {self.name}"

    def execute_clean(self, dry_run=False):
        """Execute the target's clean function if it exists_in_fs."""
        if dry_run:
            return True, f"Would clean target: {self.name}"

        if self.clean_func:
            try:
                result = self.clean_func()
                return True, f"Successfully cleaned target: {self.name}"
            except Exception as e:
                return False, f"Failed to clean target {self.name}: {str(e)}"
        return True, f"No clean action for target: {self.name}"

    def needs_update(self, dependency_mtimes):
        """Check if the target needs to be rebuilt based on dependency modification times."""
        if not self.exists_in_fs:
            return True

        target_mtime = self.get_mtime()
        if target_mtime is None:
            return True

        # If any dependency is newer than this target, rebuild
        for dep_mtime in dependency_mtimes:
            if dep_mtime is not None and dep_mtime > target_mtime:
                return True

        return False

    def is_abstract(self):
        """Check if this is an abstract target (no concrete output)."""
        if self._is_abstract:
            return True
        return not (self.exists_in_fs or self.action_func)


# Decorator functions
def target(name=None, depends=None, provides=None, exists_in_fs=None, check_mtime=False, essential=False):
    """Decorator to define a build target."""

    def decorator(func):
        nonlocal name
        if name is None:
            name = func.__name__

        tgt = Target(name=name, action_func=func, depends=depends, provides=provides, exists_in_fs=exists_in_fs, essential=essential, check_mtime=check_mtime)
        index.register(tgt)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def task(name=None, depends=None):
    """Simplified decorator for basic tasks with no complex requirements."""
    return target(name=name, depends=depends)


def default(func=None):
    """Mark a target as a default target."""

    def decorator(func):
        target_name = func.__name__
        tgt = index.get(target_name)
        if tgt:
            tgt.is_default = True
        else:
            # Create a new target and mark it as default
            tgt = Target(name=target_name, action_func=func, is_default=True)
            index.register(tgt)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


def provides(*artifacts):
    """Decorator to specify what a target provides."""

    def decorator(func):
        target_name = func.__name__
        tgt = index.get(target_name)
        if tgt:
            tgt.provides.update(artifacts)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def essential(func=None):
    """Mark a target as essential."""

    def decorator(func):
        target_name = func.__name__
        tgt = index.get(target_name)
        if tgt:
            tgt.essential = True
        else:
            # Create a new target and mark it as essential
            tgt = Target(name=target_name, action_func=func, essential=True)
            index.register(tgt)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


def clean(func):
    """Add a clean function to a target."""
    target_name = func.__name__.replace("clean_", "")
    tgt = index.get(target_name)
    if tgt:
        tgt.clean_func = func
    else:
        logger.warning(f"{WARNING} No target found for clean function: {target_name}")

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def load_plugin(module_name):
    """Load a plugin module."""
    try:
        plugin = __import__(module_name, fromlist=["*"])
        index.plugins.append(plugin)

        # Let the plugin initialize
        if hasattr(plugin, "initialize"):
            plugin.initialize(index)

        return plugin
    except ImportError as e:
        logger.error(f"{ERROR} Failed to load plugin {module_name}: {e}")
        return None


def get_targets():
    """Get all registered targets."""
    return index.get_targets()


def _calculate_providers(index):
    """Calculate which targets provide which other targets."""
    targets = index.targets
    providers = defaultdict(set)

    for target_name, target in targets.items():
        for provided in target.provides:
            if provided in targets:
                providers[provided].add(target_name)

    # Calculate full providers (transitive closure)
    full_providers = {}
    for target_name, provider_names in providers.items():
        new_set = set(provider_names)

        # Find all indirect providers
        prev_set = set()
        while prev_set != new_set:
            prev_set = set(new_set)
            to_add = set()
            for p in new_set:
                if p in providers:
                    to_add.update(providers[p])
            new_set.update(to_add)

        full_providers[target_name] = new_set

    return providers, full_providers


def _order_by_dependencies(targets_to_build, all_targets, essential_targets):
    """Order targets for building based on dependencies."""
    # Convert names to actual Target objects
    targets_set = {all_targets[t] for t in targets_to_build if t in all_targets}
    essential_set = {all_targets[t] for t in essential_targets if t in all_targets}

    # Find targets with no dependencies
    no_deps = {t for t in targets_set & essential_set if not t.depends}
    with_deps = {t for t in targets_set & essential_set if t.depends}

    # Create the initial dependency layers
    layers = [list(no_deps), list(with_deps)]

    # Find all targets that are provided by the essentials
    provides_set = essential_set.copy()
    for target in essential_set:
        provides_set.update(target.provides)

    # All remaining targets that aren't provided by the essentials
    depends_set = targets_set - provides_set

    # Keep track of all targets that have been handled
    all_handled = provides_set.copy()

    # Find all dependencies
    all_deps = set()
    for target in depends_set:
        all_deps.update(target.depends)

    # Iteratively resolve dependencies
    for _ in range(10):  # Limit iterations to prevent infinite loops
        # Find targets whose dependencies are all satisfied
        ready = {t for t in depends_set if not t.depends or all(d in all_handled for d in t.depends)}
        if ready:
            layers.append(list(ready))
            all_handled.update(ready)
            depends_set -= ready
        else:
            break

    # Filter out abstract targets and return in order
    return [t for layer in layers for t in layer if not t.is_abstract()]


def _resolve_dependencies(targets_to_build, all_targets, providers, full_providers, essential_targets):
    """Resolve which targets need to be built including dependencies."""
    targets_set = set(targets_to_build)
    result_set = set(targets_to_build)

    # Add essential targets if needed
    if any(t not in all_targets or all_targets[t].essential for t in targets_to_build):
        result_set.update(essential_targets)

    # Keep track of new additions to process
    to_process = set(result_set)

    while to_process:
        current = to_process.pop()
        if current not in all_targets:
            continue

        target = all_targets[current]

        # Add direct dependencies
        for dep_name in target.depends:
            if dep_name not in result_set:
                result_set.add(dep_name)
                to_process.add(dep_name)

        # Add things that provide abstract dependencies
        if target.is_abstract():
            # If abstract, add targets that provide it
            if current in providers:
                for provider in providers[current]:
                    if provider not in result_set:
                        result_set.add(provider)
                        to_process.add(provider)

    return result_set


def run_targets(target_names=None, clean_mode=False, dry_run=False, debug=False):
    """
    Run the specified targets or default targets.

    Args:
        target_names: List of target names to build, or None for default targets
        clean_mode: If True, run clean actions instead of build actions
        dry_run: If True, just print what would be done without executing
        debug: If True, print debug information

    Returns:
        Tuple of (success, messages)
    """
    all_targets = {t.name: t for t in index.get_targets()}

    # Use default targets if none specified
    if not target_names:
        default_targets = index.get_default_targets()
        if default_targets:
            target_names = [t.name for t in default_targets]
        else:
            return False, ["No targets specified and no default targets defined"]

    messages = []
    messages.append(f"{START} Building targets: {', '.join(target_names)}")

    # Get the direct providers and full transitive closure of providers
    providers, full_providers = _calculate_providers(index)

    # Get essential targets
    essential_target_names = {t.name for t in index.get_essential_targets()}

    # Resolve all dependencies
    targets_to_build = _resolve_dependencies(target_names, all_targets, providers, full_providers, essential_target_names)

    if debug:
        messages.append(f"{DEBUG} Resolved targets to build: {', '.join(targets_to_build)}")

    # Check if any targets are missing
    missing = [t for t in targets_to_build if t not in all_targets]
    if missing:
        messages.append(f"{ERROR} Missing targets: {', '.join(missing)}")
        return False, messages

    # Order the targets for building
    ordered_targets = _order_by_dependencies(targets_to_build, all_targets, essential_target_names)

    if debug:
        messages.append(f"{DEBUG} Build order: {[t.name for t in ordered_targets]}")

    # Execute targets in order
    success = True
    for target in ordered_targets:
        target_name = target.name

        if clean_mode:
            status, msg = target.execute_clean(dry_run)
        else:
            # Check if we need to rebuild based on file timestamps
            dependencies = [d.get_mtime() for d in target.depends if not d.is_abstract()]
            needs_update = target.needs_update(dependencies)

            if needs_update or not target.exists_in_fs:
                status, msg = target.execute(dry_run)
            else:
                status, msg = True, f"Target {target_name} is up to date"

        if status:
            messages.append(f"{SUCCESS} {msg}")
        else:
            messages.append(f"{ERROR} {msg}")
            success = False
            break

    return success, messages
