# Contributing to BOT-MMORPG-AI

First off, thank you for considering contributing to BOT-MMORPG-AI! It's people like you that make this project such a great tool for the AI gaming community.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to contact@ruslanmv.com.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When creating a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples**
- **Describe the behavior you observed and what you expected**
- **Include screenshots if relevant**
- **Include your environment details** (OS, Python version, GPU, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Use a clear and descriptive title**
- **Provide a detailed description of the proposed functionality**
- **Explain why this enhancement would be useful**
- **List any alternatives you've considered**

### Pull Requests

1. Fork the repository and create your branch from `main`
2. If you've added code that should be tested, add tests
3. Ensure the test suite passes (`make test`)
4. Make sure your code follows the style guidelines (`make check`)
5. Write a clear commit message

## Development Setup

### Prerequisites

- Python 3.8-3.11
- Git
- uv package manager (recommended)

### Setup Steps

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/BOT-MMORPG-AI.git
cd BOT-MMORPG-AI

# Install development dependencies
make install-dev

# Run tests to verify setup
make test
```

## Development Workflow

### Code Style

We use the following tools to maintain code quality:

- **Black**: Code formatting (100 character line length)
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pylint**: Additional linting

Format your code before committing:

```bash
make format
make check
```

### Writing Tests

- Write unit tests for new functionality
- Use pytest fixtures for common test data
- Mark tests appropriately: `@pytest.mark.unit`, `@pytest.mark.integration`
- Aim for high test coverage

```python
import pytest

@pytest.mark.unit
def test_my_function():
    assert my_function(input) == expected_output
```

### Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Update README.md if adding new features
- Include type hints in function signatures

```python
def process_image(image: np.ndarray, size: tuple) -> np.ndarray:
    """
    Process and resize an image.

    Args:
        image: Input image as numpy array
        size: Target size as (width, height)

    Returns:
        Processed image as numpy array

    Raises:
        ValueError: If image is invalid
    """
    pass
```

### Commit Messages

Follow these guidelines for commit messages:

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters
- Reference issues and pull requests liberally

Example:
```
Add motion detection for stuck prevention

- Implement delta calculation between frames
- Add motion threshold configuration
- Include evasive maneuvers when stuck

Fixes #123
```

## Project Structure

```
BOT-MMORPG-AI/
├── src/bot_mmorpg/      # Main package source
│   ├── models/          # Neural network models
│   ├── utils/           # Utility functions
│   └── scripts/         # CLI scripts
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   └── integration/    # Integration tests
├── versions/            # Version implementations
├── frontend/            # Frontend utilities
└── docs/               # Documentation
```

## Testing

### Running Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# With coverage
make test-cov

# Fast tests (exclude slow)
make test-fast
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use descriptive test names
- One assertion per test when possible

## Building and Releasing

### Building

```bash
# Build distribution packages
make build

# This creates wheel and source distributions in dist/
```

### Release Process

1. Update version in `src/bot_mmorpg/__init__.py`
2. Update CHANGELOG.md
3. Create a git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
4. Push tag: `git push origin v1.0.0`
5. Build distribution: `make build`
6. Create GitHub release with notes

## Getting Help

- Join our [Slack community](https://aws-ml-group.slack.com/)
- Open an issue with the `question` label
- Email: contact@ruslanmv.com
- Website: [ruslanmv.com](https://ruslanmv.com/)

## Recognition

Contributors will be recognized in:
- GitHub contributors page
- CONTRIBUTORS.md file
- Release notes

Thank you for contributing to BOT-MMORPG-AI! 🎮🤖
