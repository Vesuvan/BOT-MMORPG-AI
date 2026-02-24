"""
BOT-MMORPG-AI Configuration System

This module provides a hierarchical configuration system with:
- Hardware auto-detection
- Game profile loading
- Settings merging with proper precedence
- Model recommendation engine
"""

from .hardware_detector import HardwareDetector, HardwareTier
from .model_selector import ModelRecommendation, ModelSelector
from .profile_loader import GameProfile, GameProfileLoader
from .settings_manager import SettingsManager

__all__ = [
    "HardwareDetector",
    "HardwareTier",
    "GameProfileLoader",
    "GameProfile",
    "SettingsManager",
    "ModelSelector",
    "ModelRecommendation",
]
