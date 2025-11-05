# Makefile for YouTube Video Downloader

.PHONY: help install install-dev test test-unit test-integration lint format type-check security clean build upload docs

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install package in production mode"
	@echo "  install-dev  - Install package in development mode"
	@echo "  test         - Run all tests"
	@echo "  test-unit    - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code with black and isort"
	@echo "  type-check   - Run type checking with mypy"
	@echo "  security     - Run security checks"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build package"
	@echo "  upload       - Upload package to PyPI"
	@echo "  docs         - Generate documentation"

# Installation
install:
	pip install .

install-dev:
	pip install -r requirements-dev.txt
	pip install -e .
	pre-commit install

# Testing
test:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing

test-unit:
	pytest tests/ -v -m "unit" --cov=. --cov-report=term-missing

test-integration:
	pytest tests/ -v -m "integration" --cov=. --cov-report=term-missing

test-slow:
	pytest tests/ -v -m "slow" --cov=. --cov-report=term-missing

test-all:
	tox

# Code quality
lint:
	flake8 . --count --statistics
	bandit -r . --severity-level medium

format:
	black .
	isort .

type-check:
	mypy . --ignore-missing-imports

security:
	bandit -r . --severity-level medium
	safety check

# Quality checks (all)
quality: format lint type-check security

# Build and distribution
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .tox/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

upload: build
	twine check dist/*
	twine upload dist/*

upload-test: build
	twine check dist/*
	twine upload --repository testpypi dist/*

# Documentation
docs:
	@echo "Generating CLI help documentation..."
	youtube-downloader --help > docs/cli-help.txt
	youtube-downloader help-examples > docs/examples.txt

# Development helpers
dev-setup: install-dev
	@echo "Development environment setup complete!"
	@echo "Run 'make test' to verify installation"

check: format lint type-check test
	@echo "All checks passed!"

# CI simulation
ci: clean install-dev check security
	@echo "CI simulation complete!"

# Release preparation
release-check: clean build
	twine check dist/*
	@echo "Release check complete. Ready for upload."