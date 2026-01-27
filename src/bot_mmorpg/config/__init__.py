"""
BOT-MMORPG-AI Configuration System

This module provides a hierarchical configuration system with:
- Hardware auto-detection
- Game profile loading
- Settings merging with proper precedence
- Model recommendation engine
"""

from .hardware_detector import HardwareDetector, HardwareTier
from .profile_loader import GameProfileLoader, GameProfile
from .settings_manager import SettingsManager
from .model_selector import ModelSelector, ModelRecommendation

__all__ = [
    "HardwareDetector",
    "HardwareTier",
    "GameProfileLoader",
    "GameProfile",
    "SettingsManager",
    "ModelSelector",
    "ModelRecommendation",
]
