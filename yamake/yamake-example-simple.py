"""
A simple example of using yamake to build a project.

This example demonstrates how to use the yamake decorators to define targets
and their dependencies for building a simple project.
"""

import os
import shutil
import yamake


# Define a target for creating the build directory
@yamake.target(exists="build")
def setup_build_dir():
    """Create the build directory."""
    if not os.path.exists("build"):
        os.makedirs("build")
    return {"status": "Build directory created"}


# Define a target for compiling a source file
@yamake.target(depends=["setup_build_dir"], exists="build/main.o", check_mtime=True)
def compile_main():
    """Compile the main source file."""
    # This would typically run a compiler, but we'll simulate it
    with open("build/main.o", "w") as f:
        f.write("Compiled main.c at " + str(os.path.getmtime("examples/main.c")))
    return {"status": "Main file compiled"}


# Define a target for compiling another source file
@yamake.target(depends=["setup_build_dir"], exists="build/util.o", check_mtime=True)
def compile_util():
    """Compile the utility source file."""
    # This would typically run a compiler, but we'll simulate it
    with open("build/util.o", "w") as f:
        f.write("Compiled util.c at " + str(os.path.getmtime("examples/util.c")))
    return {"status": "Utility file compiled"}


# Define a target for linking the object files
@yamake.target(depends=["compile_main", "compile_util"], exists="build/program", check_mtime=True)
def link_program():
    """Link the object files into a program."""
    # This would typically run a linker, but we'll simulate it
    with open("build/program", "w") as f:
        f.write("Linked main.o and util.o\n")
        with open("build/main.o", "r") as main_f:
            f.write(main_f.read() + "\n")
        with open("build/util.o", "r") as util_f:
            f.write(util_f.read() + "\n")
    return {"status": "Program linked"}


# Define a target for installing the program
@yamake.target(depends=["link_program"], exists="dist/program")
def install():
    """Install the program to the distribution directory."""
    if not os.path.exists("dist"):
        os.makedirs("dist")
    shutil.copy("build/program", "dist/program")
    return {"status": "Program installed"}


# Define an abstract target that represents "building the project"
@yamake.target(depends=["link_program"])
def build():
    """Build the project."""
    return {"status": "Project built"}


# Define a default target
@yamake.default
@yamake.target(depends=["build"])
def default():
    """Default target."""
    return {"status": "Default target executed"}


# Define clean functions for targets
@yamake.clean
def clean_setup_build_dir():
    """Clean the build directory."""
    if os.path.exists("build"):
        shutil.rmtree("build")
    return {"status": "Build directory removed"}


@yamake.clean
def clean_install():
    """Clean the install directory."""
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    return {"status": "Distribution directory removed"}


if __name__ == "__main__":
    # Create the source files if they don't exist (for demonstration)
    if not os.path.exists("examples"):
        os.makedirs("examples")

    if not os.path.exists("examples/main.c"):
        with open("examples/main.c", "w") as f:
            f.write("int main() { return 0; }\n")

    if not os.path.exists("examples/util.c"):
        with open("examples/util.c", "w") as f:
            f.write("void util_function() {}\n")

    # Now run a build
    success, messages = yamake.run_targets()

    for msg in messages:
        print(msg)

    print("\nNow let's clean everything:")
    success, messages = yamake.run_targets(clean_mode=True)

    for msg in messages:
        print(msg)
