"""
Pytest configuration and fixtures.

This module contains shared pytest fixtures and configuration
for the test suite.
"""

import pytest
from typing import Generator


@pytest.fixture
def sample_image_shape() -> tuple:
    """Return the standard image shape used in the project."""
    return (270, 480, 3)


@pytest.fixture
def num_output_classes() -> int:
    """Return the number of output classes for the model."""
    return 29


@pytest.fixture
def temp_model_path(tmp_path) -> Generator[str, None, None]:
    """Provide a temporary path for model files."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    yield str(model_dir)
