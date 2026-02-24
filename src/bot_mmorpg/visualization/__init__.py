"""
Visualization Module

Real-time visualization utilities for training and inference.
"""

from .attention import GradCAM, generate_attention_map
from .overlays import draw_confidence_bars, generate_prediction_overlay

__all__ = [
    "generate_attention_map",
    "GradCAM",
    "generate_prediction_overlay",
    "draw_confidence_bars",
]
