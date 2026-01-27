"""
Training Module

Provides curriculum-based training with progressive learning phases.
"""

from .curriculum import CurriculumTrainer, TrainingPhase

__all__ = ["CurriculumTrainer", "TrainingPhase"]
