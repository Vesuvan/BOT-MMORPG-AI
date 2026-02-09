"""
Utility functions for screen capture, input handling, and preprocessing.

This module provides helper functions for:
- Screen grabbing and video capture
- Keyboard and gamepad input detection
- Direct key simulation
- Image preprocessing and data augmentation
- Version management and update checking
- Secure data loading
"""

from typing import List

# Version utilities
try:
    from .version import (
        check_for_updates,
        check_for_updates_async,
        get_current_version,
        compare_versions,
        UpdateInfo,
        VersionInfo,
    )
    _version_available = True
except ImportError:
    _version_available = False

# Secure loader utilities
try:
    from .secure_loader import (
        load_training_data_secure,
        validate_training_data_structure,
        DataValidationError,
    )
    _secure_loader_available = True
except ImportError:
    _secure_loader_available = False

__all__: List[str] = []

if _version_available:
    __all__.extend([
        "check_for_updates",
        "check_for_updates_async",
        "get_current_version",
        "compare_versions",
        "UpdateInfo",
        "VersionInfo",
    ])

if _secure_loader_available:
    __all__.extend([
        "load_training_data_secure",
        "validate_training_data_structure",
        "DataValidationError",
    ])
