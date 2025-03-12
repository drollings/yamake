# yamake

**Warning:  this is freshly refactored and in a pre-alpha state.** 

A decorator-driven Python library for dependency systems with duck-typing resolution.

## Features

- **Intuitive, Pythonic Interface**: Define build targets using decorators
- **Powerful Dependency Resolution**: Handles complex dependency graphs with ease
- **Abstract Targets and Provides**: Support for duck-typed abstract target conditions.
- **File Timestamp Checking**: Conditionally rebuild only what's necessary, like make, 
- **Command-Line Interface**: Easy to use from the command line

## Installation

```bash
pip install yamake
```

## Example Usage

Create a build file (e.g., `build.py`):

```python
import os
import yamake

@yamake.target(exists="build")
def setup_build_dir():
    """Create the build directory."""
    if not os.path.exists("build"):
        os.makedirs("build")
    return {"status": "Build directory created"}

@yamake.target(depends=["setup_build_dir"], exists="build/main.o", check_mtime=True)
def compile_main():
    """Compile the main source file."""
    with open("build/main.o", "w") as f:
        f.write("Compiled main.c")
    return {"status": "Main file compiled"}

@yamake.target(depends=["compile_main"], exists="build/program")
def link_program():
    """Link the program."""
    with open("build/program", "w") as f:
        f.write("Linked main.o")
    return {"status": "Program linked"}

@yamake.default
@yamake.target(depends=["link_program"])
def default():
    """Default target."""
    return {"status": "Build completed"}

@yamake.clean
def clean_setup_build_dir():
    """Clean the build directory."""
    if os.path.exists("build"):
        import shutil
        shutil.rmtree("build")
    return {"status": "Build directory removed"}
```

Run from the command line:

```bash
yamake             # Build the default target
yamake link_program  # Build a specific target
yamake -c         # Clean
yamake -l         # List available targets
yamake -n         # Dry run (show what would be done)
```

Or run programmatically:

```python
import yamake

success, messages = yamake.run_targets(["link_program"])
for msg in messages:
    print(msg)
```

## Core Decorators

- `@yamake.target()`: Define a build target with dependencies, output files, etc.
- `@yamake.task()`: Simplified decorator for basic tasks
- `@yamake.default`: Mark a target as the default to build
- `@yamake.provides()`: Specify what abstract features a target provides
- `@yamake.essential`: Mark a target as essential
- `@yamake.clean`: Define a clean function for a target

## Advanced Features

### Abstract Targets and Features

```python
@yamake.target(name="feature_encryption")
def feature_encryption():
    """Abstract target representing encryption feature."""
    pass

@yamake.target(provides=["feature_encryption"], exists="build/encryption.o")
def build_encryption():
    """Build the encryption module."""
    # Implementation...
    return {"status": "Encryption module built"}

@yamake.target(depends=["feature_encryption"])
def secure_app():
    """Build a secure application using encryption."""
    # Implementation...
    return {"status": "Secure app built"}
```

### Plugin System

Create a plugin file:

```python
def initialize(registry):
    global _registry
    _registry = registry
    return {"plugin_initialized": True}

def custom_target(name=None, priority=0):
    def decorator(func):
        from yamake.core import Target
        nonlocal name
        if name is None:
            name = func.__name__
            
        target = Target(name=name, action_func=func)
        target.priority = priority
        _registry.register(target)
        return func
    return decorator
```

Use the plugin:

```python
import yamake
yamake.load_plugin("my_plugin")

@my_plugin.custom_target(priority=10)
def high_priority_task():
    return {"status": "High priority task executed"}
```

## License

MIT License