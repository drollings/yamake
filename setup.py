"""
Setup script for the yamake package.
"""

from setuptools import setup, find_packages

setup(
    name="yamake",
    version="0.1.0",
    description="A decorator-based build system with powerful dependency resolution",
    author="Based on Daniel Rollings' yamake",
    author_email="example@example.com",
    url="https://github.com/example/yamake",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "yamake=yamake.cli:main",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Build Tools",
    ],
)