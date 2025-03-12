"""
A more complex example of using yamake to build a project with abstract targets and features.

This example demonstrates how to use the yamake decorators to create a build system
that can handle abstract targets, feature flags, and complex dependency relationships.
"""

import os
import shutil
import yamake


# Define some abstract targets/features
@yamake.target(name="feature_logging")
def feature_logging():
    """Abstract target representing the logging feature."""
    pass


@yamake.target(name="feature_encryption")
def feature_encryption():
    """Abstract target representing the encryption feature."""
    pass


@yamake.target(name="platform_linux")
def platform_linux():
    """Abstract target representing the Linux platform."""
    pass


@yamake.target(name="platform_windows")
def platform_windows():
    """Abstract target representing the Windows platform."""
    pass


# Define concrete targets that provide these features
@yamake.target(provides=["feature_logging"], exists="build/logging.o")
def build_logging():
    """Build the logging module."""
    if not os.path.exists("build"):
        os.makedirs("build")
    with open("build/logging.o", "w") as f:
        f.write("Compiled logging module\n")
    return {"status": "Logging module built"}


@yamake.target(provides=["feature_encryption"], exists="build/encryption.o")
def build_encryption():
    """Build the encryption module."""
    if not os.path.exists("build"):
        os.makedirs("build")
    with open("build/encryption.o", "w") as f:
        f.write("Compiled encryption module\n")
    return {"status": "Encryption module built"}


@yamake.target(provides=["platform_linux"], exists="build/platform_linux.o")
def build_linux_platform():
    """Build the Linux platform layer."""
    if not os.path.exists("build"):
        os.makedirs("build")
    with open("build/platform_linux.o", "w") as f:
        f.write("Compiled Linux platform layer\n")
    return {"status": "Linux platform layer built"}


@yamake.target(provides=["platform_windows"], exists="build/platform_windows.o")
def build_windows_platform():
    """Build the Windows platform layer."""
    if not os.path.exists("build"):
        os.makedirs("build")
    with open("build/platform_windows.o", "w") as f:
        f.write("Compiled Windows platform layer\n")
    return {"status": "Windows platform layer built"}


# Now define the main application that depends on abstract features
@yamake.target(
    depends=["feature_logging", "feature_encryption"],
    exists="build/core.o"
)
def build_core():
    """Build the core application."""
    if not os.path.exists("build"):
        os.makedirs("build")
    with open("build/core.o", "w") as f:
        f.write("Compiled core application with logging and encryption\n")
    return {"status": "Core application built"}


# Define platform-specific application builds
@yamake.target(
    name="build_linux_app",
    depends=["build_core", "platform_linux"],
    exists="build/app_linux"
)
def build_linux_app():
    """Build the Linux application."""
    with open("build/app_linux", "w") as f:
        f.write("Linux application built with:\n")
        with open("build/core.o", "r") as core_f:
            f.write(core_f.read())
        with open("build/platform_linux.o", "r") as platform_f:
            f.write(platform_f.read())
    return {"status": "Linux application built"}


@yamake.target(
    name="build_windows_app",
    depends=["build_core", "platform_windows"],
    exists="build/app_windows.exe"
)
def build_windows_app():
    """Build the Windows application."""
    with open("build/app_windows.exe", "w") as f:
        f.write("Windows application built with:\n")
        with open("build/core.o", "r") as core_f:
            f.write(core_f.read())
        with open("build/platform_windows.o", "r") as platform_f:
            f.write(platform_f.read())
    return {"status": "Windows application built"}


# Define targets for different product configurations
@yamake.target(depends=["build_linux_app"])
def product_linux():
    """Build the Linux product."""
    return {"status": "Linux product built"}


@yamake.target(depends=["build_windows_app"])
def product_windows():
    """Build the Windows product."""
    return {"status": "Windows product built"}


@yamake.target(depends=["product_linux", "product_windows"])
def product_all():
    """Build products for all platforms."""
    return {"status": "All products built"}


# Set the default target
@yamake.default
@yamake.target(depends=["product_linux"])
def default():
    """Default target."""
    return {"status": "Default target executed"}


# Define clean function
@yamake.clean
def clean_all():
    """Clean all build artifacts."""
    if os.path.exists("build"):
        shutil.rmtree("build")
    return {"status": "All build artifacts removed"}


if __name__ == "__main__":
    # Run a build for all products
    success, messages = yamake.run_targets(["product_all"])
    
    for msg in messages:
        print(msg)
    
    print("\nNow let's clean everything:")
    success, messages = yamake.run_targets(clean_mode=True)
    
    for msg in messages:
        print(msg)