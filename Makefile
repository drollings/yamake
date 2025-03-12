.PHONY: test clean install dev example

# Run tests
test:
	pytest

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete

# Install the package
install:
	pip install -e .

# Install development dependencies
dev:
	pip install -e ".[dev]"
	pip install pytest pytest-cov

# Run example
example:
	python examples/simple.py

# Run the plugin example
plugin-example:
	cd examples/plugin_example && python build.py