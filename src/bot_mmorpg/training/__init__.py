"""
Training Module

Provides curriculum-based training with progressive learning phases.
"""

from .curriculum import CurriculumConfig, CurriculumTrainer, TrainingPhase

__all__ = ["CurriculumConfig", "CurriculumTrainer", "TrainingPhase"]
