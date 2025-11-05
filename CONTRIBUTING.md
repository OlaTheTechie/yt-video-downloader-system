# Contributing to YouTube Video Downloader

Thank you for your interest in contributing to YouTube Video Downloader! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Process](#contributing-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)

## Code of Conduct

This project adheres to a code of conduct that we expect all contributors to follow. Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- FFmpeg (for video processing features)
- Basic understanding of Python and command-line tools

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/youtube-video-downloader.git
   cd youtube-video-downloader
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   pip install -e .
   ```

4. **Verify Installation**
   ```bash
   youtube-downloader --help
   pytest
   ```

## Contributing Process

### 1. Create an Issue

Before starting work, create an issue to discuss:
- Bug reports with reproduction steps
- Feature requests with use cases
- Documentation improvements

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 3. Make Changes

- Write clean, readable code
- Follow existing code style
- Add tests for new functionality
- Update documentation as needed

### 4. Test Your Changes

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit
pytest -m integration

# Check code coverage
pytest --cov=. --cov-report=html
```

### 5. Submit Pull Request

- Push your branch to your fork
- Create a pull request with clear description
- Link to related issues
- Ensure all checks pass

## Coding Standards

### Python Style

We follow PEP 8 with some modifications:

```bash
# Format code
black .
isort .

# Check style
flake8 .

# Type checking
mypy .
```

### Code Organization

- **cli/**: Command-line interface components
- **config/**: Configuration management
- **core/**: Main application logic
- **models/**: Data models and types
- **services/**: Business logic services
- **tests/**: Test files

### Naming Conventions

- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Files/modules: `snake_case`

## Testing Guidelines

### Test Categories

- **Unit tests**: Test individual functions/methods
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test complete workflows

### Writing Tests

```python
import pytest
from your_module import YourClass

class TestYourClass:
    def test_basic_functionality(self):
        # Arrange
        instance = YourClass()
        
        # Act
        result = instance.method()
        
        # Assert
        assert result == expected_value
    
    def test_error_handling(self):
        with pytest.raises(ExpectedError):
            # Test error conditions
            pass
```

### Test Requirements

- All new features must have tests
- Bug fixes should include regression tests
- Maintain test coverage above 80%
- Tests should be fast and reliable

## Documentation

### Code Documentation

- Use docstrings for all public functions/classes
- Include type hints
- Document complex algorithms
- Add inline comments for clarity

```python
def download_video(url: str, config: DownloadConfig) -> DownloadResult:
    """
    Download a single video from YouTube.
    
    Args:
        url: YouTube video URL
        config: Download configuration settings
        
    Returns:
        DownloadResult with success status and file paths
        
    Raises:
        ValidationError: If URL is invalid
        DownloadError: If download fails
    """
```

### User Documentation

- Update README.md for new features
- Add examples to help documentation
- Update troubleshooting guide
- Keep changelog current

## Reporting Issues

### Bug Reports

Include the following information:

1. **System Information**
   - Python version
   - Operating system
   - FFmpeg version

2. **Steps to Reproduce**
   - Exact commands used
   - Input URLs (if not private)
   - Configuration files

3. **Expected vs Actual Behavior**
   - What you expected to happen
   - What actually happened
   - Error messages or logs

4. **Additional Context**
   - Screenshots if applicable
   - Log files with debug output

### Issue Template

```markdown
**Bug Description**
A clear description of the bug.

**To Reproduce**
Steps to reproduce the behavior:
1. Run command '...'
2. With URL '...'
3. See error

**Expected Behavior**
What you expected to happen.

**System Information**
- OS: [e.g., Ubuntu 20.04]
- Python: [e.g., 3.9.5]
- FFmpeg: [e.g., 4.4.0]

**Additional Context**
Any other context about the problem.
```

## Feature Requests

When requesting features:

1. **Describe the Use Case**
   - What problem does this solve?
   - Who would benefit from this feature?

2. **Propose a Solution**
   - How should it work?
   - What should the interface look like?

3. **Consider Alternatives**
   - Are there existing workarounds?
   - How do other tools handle this?

## Development Guidelines

### Architecture Principles

- **Separation of Concerns**: Each module has a single responsibility
- **Dependency Injection**: Use interfaces and dependency injection
- **Error Handling**: Comprehensive error handling with meaningful messages
- **Logging**: Detailed logging for debugging and monitoring
- **Configuration**: Flexible configuration with sensible defaults

### Performance Considerations

- **Memory Usage**: Stream large files, avoid loading into memory
- **Network Efficiency**: Use connection pooling and retry mechanisms
- **Parallel Processing**: Leverage threading for I/O-bound operations
- **Caching**: Cache expensive operations where appropriate

### Security Guidelines

- **Input Validation**: Validate all user inputs
- **Path Safety**: Prevent directory traversal attacks
- **Network Security**: Use HTTPS and validate certificates
- **File Permissions**: Set appropriate file permissions

## Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. Update version numbers
2. Update CHANGELOG.md
3. Run full test suite
4. Update documentation
5. Create release tag
6. Build and upload to PyPI

## Getting Help

- **Documentation**: Check README and help examples
- **Issues**: Search existing issues first
- **Discussions**: Use GitHub Discussions for questions
- **Code Review**: Ask for feedback on pull requests

## Recognition

Contributors are recognized in:
- CHANGELOG.md for significant contributions
- GitHub contributors page
- Release notes for major features

Thank you for contributing to YouTube Video Downloader!