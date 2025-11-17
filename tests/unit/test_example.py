"""
Example unit tests for BOT-MMORPG-AI.

These tests serve as templates and examples for writing
additional unit tests.
"""

import pytest


@pytest.mark.unit
def test_image_shape(sample_image_shape):
    """Test that the standard image shape is correct."""
    height, width, channels = sample_image_shape
    assert height == 270
    assert width == 480
    assert channels == 3


@pytest.mark.unit
def test_output_classes(num_output_classes):
    """Test that the number of output classes is correct."""
    assert num_output_classes == 29
    # 9 keyboard + 20 gamepad inputs
    assert num_output_classes == 9 + 20


@pytest.mark.unit
def test_version_format():
    """Test that the package version follows semantic versioning."""
    from bot_mmorpg import __version__

    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
