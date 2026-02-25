"""
Curriculum Learning Module

Implements progressive training inspired by autonomous driving schools:
- Phase 1: Foundation (frozen backbone)
- Phase 2: Fine-tuning (progressive unfreezing)
- Phase 3: Polish (full model training)
- Phase 4: Validation (deployment readiness)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)


class TrainingPhase(Enum):
    """Training curriculum phases."""

    FOUNDATION = "foundation"
    FINE_TUNING = "fine_tuning"
    POLISH = "polish"
    VALIDATION = "validation"


@dataclass
class PhaseConfig:
    """Configuration for a training phase."""

    name: str
    epochs: int
    learning_rate: float
    freeze_backbone: bool
    unfreeze_layers: int  # Number of layers to unfreeze (from top)
    augmentation_strength: float  # 0.0 to 1.0
    weight_decay: float
    description: str


@dataclass
class TrainingMetrics:
    """Training metrics for a phase."""

    phase: TrainingPhase
    epoch: int
    train_loss: float
    val_loss: float
    train_accuracy: float
    val_accuracy: float
    learning_rate: float
    best_val_accuracy: float = 0.0


@dataclass
class CurriculumConfig:
    """Complete curriculum configuration."""

    total_epochs: int = 50
    phases: List[PhaseConfig] = field(default_factory=list)

    # Early stopping
    early_stopping_patience: int = 10
    early_stopping_min_delta: float = 0.001

    # Checkpointing
    checkpoint_dir: Optional[Path] = None
    save_best_only: bool = True

    @classmethod
    def default(cls, total_epochs: int = 50) -> "CurriculumConfig":
        """Create default curriculum configuration."""
        # Distribute epochs across phases
        foundation_epochs = max(5, int(total_epochs * 0.2))
        finetune_epochs = max(10, int(total_epochs * 0.4))
        polish_epochs = max(5, int(total_epochs * 0.3))
        validation_epochs = max(
            2, total_epochs - foundation_epochs - finetune_epochs - polish_epochs
        )

        phases = [
            PhaseConfig(
                name="Foundation",
                epochs=foundation_epochs,
                learning_rate=0.001,
                freeze_backbone=True,
                unfreeze_layers=0,
                augmentation_strength=0.3,
                weight_decay=0.01,
                description="Learn game-specific features with frozen backbone",
            ),
            PhaseConfig(
                name="Fine-tuning",
                epochs=finetune_epochs,
                learning_rate=0.0001,
                freeze_backbone=False,
                unfreeze_layers=10,  # Unfreeze top 10 layers
                augmentation_strength=0.5,
                weight_decay=0.001,
                description="Adapt model to user's playstyle",
            ),
            PhaseConfig(
                name="Polish",
                epochs=polish_epochs,
                learning_rate=0.00001,
                freeze_backbone=False,
                unfreeze_layers=-1,  # Unfreeze all
                augmentation_strength=0.7,
                weight_decay=0.0001,
                description="Handle edge cases with full model training",
            ),
            PhaseConfig(
                name="Validation",
                epochs=validation_epochs,
                learning_rate=0.000001,
                freeze_backbone=False,
                unfreeze_layers=-1,
                augmentation_strength=0.3,
                weight_decay=0.0001,
                description="Final validation and deployment readiness",
            ),
        ]

        return cls(total_epochs=total_epochs, phases=phases)


class CurriculumTrainer:
    """
    Curriculum-based trainer with progressive learning.

    Implements the autonomous driving school approach:
    - Start simple (frozen backbone, low augmentation)
    - Progressively increase complexity
    - Focus on edge cases in final phases

    Usage:
        trainer = CurriculumTrainer(model, config)
        trainer.fit(train_loader, val_loader)
    """

    def __init__(
        self,
        model: nn.Module,
        config: Optional[CurriculumConfig] = None,
        device: Optional[torch.device] = None,
    ):
        """
        Initialize the curriculum trainer.

        Args:
            model: PyTorch model to train
            config: Curriculum configuration (uses defaults if None)
            device: Training device (auto-detect if None)
        """
        self.model = model
        self.config = config or CurriculumConfig.default()
        self.device = device or self._detect_device()

        self.model.to(self.device)

        # Training state
        self.current_phase_idx = 0
        self.current_epoch = 0
        self.best_val_accuracy = 0.0
        self.patience_counter = 0
        self.history: List[TrainingMetrics] = []

        # Callbacks
        self._on_phase_start: Optional[Callable] = None
        self._on_epoch_end: Optional[Callable] = None
        self._on_training_complete: Optional[Callable] = None

        # Loss function
        self.criterion = nn.CrossEntropyLoss()

    def _detect_device(self) -> torch.device:
        """Detect best available device."""
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    @property
    def current_phase(self) -> PhaseConfig:
        """Get current training phase configuration."""
        return self.config.phases[self.current_phase_idx]

    def _setup_phase(self, phase: PhaseConfig) -> Tuple[torch.optim.Optimizer, Any]:
        """Setup optimizer and scheduler for a phase."""
        # Configure layer freezing
        self._configure_freezing(phase)

        # Get trainable parameters
        trainable_params = [p for p in self.model.parameters() if p.requires_grad]
        trainable_count = sum(p.numel() for p in trainable_params)
        total_count = sum(p.numel() for p in self.model.parameters())

        logger.info(
            f"Phase '{phase.name}': {trainable_count:,} / {total_count:,} parameters trainable"
        )

        # Create optimizer
        optimizer = AdamW(
            trainable_params,
            lr=phase.learning_rate,
            weight_decay=phase.weight_decay,
        )

        # Create scheduler
        scheduler = CosineAnnealingWarmRestarts(
            optimizer, T_0=phase.epochs, T_mult=1, eta_min=phase.learning_rate * 0.01
        )

        return optimizer, scheduler

    def _configure_freezing(self, phase: PhaseConfig):
        """Configure layer freezing based on phase."""
        if phase.freeze_backbone:
            # Freeze all backbone parameters
            for name, param in self.model.named_parameters():
                if "backbone" in name or "features" in name or "encoder" in name:
                    param.requires_grad = False
                else:
                    param.requires_grad = True
        elif phase.unfreeze_layers == -1:
            # Unfreeze all
            for param in self.model.parameters():
                param.requires_grad = True
        else:
            # Progressive unfreezing from top
            all_params = list(self.model.named_parameters())
            n_params = len(all_params)
            unfreeze_from = max(0, n_params - phase.unfreeze_layers)

            for i, (name, param) in enumerate(all_params):
                param.requires_grad = i >= unfreeze_from

    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        class_weights: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """
        Train the model using curriculum learning.

        Args:
            train_loader: Training data loader
            val_loader: Validation data loader
            class_weights: Optional class weights for imbalanced data

        Returns:
            Training summary with metrics
        """
        if class_weights is not None:
            self.criterion = nn.CrossEntropyLoss(weight=class_weights.to(self.device))

        total_epochs_done = 0

        for phase_idx, phase in enumerate(self.config.phases):
            self.current_phase_idx = phase_idx

            logger.info(f"\n{'=' * 50}")
            logger.info(
                f"Phase {phase_idx + 1}/{len(self.config.phases)}: {phase.name}"
            )
            logger.info(f"Description: {phase.description}")
            logger.info(f"Epochs: {phase.epochs}, LR: {phase.learning_rate}")
            logger.info("=" * 50)

            if self._on_phase_start:
                self._on_phase_start(phase)

            optimizer, scheduler = self._setup_phase(phase)

            for epoch in range(phase.epochs):
                self.current_epoch = total_epochs_done + epoch

                # Training
                train_loss, train_acc = self._train_epoch(
                    train_loader, optimizer, phase
                )

                # Validation
                val_loss, val_acc = self._validate(val_loader)

                # Update scheduler
                scheduler.step()

                # Record metrics
                metrics = TrainingMetrics(
                    phase=TrainingPhase(phase.name.lower().replace("-", "_")),
                    epoch=self.current_epoch,
                    train_loss=train_loss,
                    val_loss=val_loss,
                    train_accuracy=train_acc,
                    val_accuracy=val_acc,
                    learning_rate=optimizer.param_groups[0]["lr"],
                    best_val_accuracy=self.best_val_accuracy,
                )
                self.history.append(metrics)

                # Logging
                logger.info(
                    f"Epoch {self.current_epoch + 1}: "
                    f"train_loss={train_loss:.4f}, train_acc={train_acc:.2%}, "
                    f"val_loss={val_loss:.4f}, val_acc={val_acc:.2%}"
                )

                if self._on_epoch_end:
                    self._on_epoch_end(metrics)

                # Best model tracking
                if val_acc > self.best_val_accuracy:
                    self.best_val_accuracy = val_acc
                    self.patience_counter = 0
                    self._save_checkpoint("best")
                else:
                    self.patience_counter += 1

                # Early stopping check
                if self.patience_counter >= self.config.early_stopping_patience:
                    logger.info(
                        f"Early stopping triggered after {self.patience_counter} epochs without improvement"
                    )
                    break

            total_epochs_done += phase.epochs

            # Save phase checkpoint
            self._save_checkpoint(f"phase_{phase_idx + 1}")

        # Training complete
        if self._on_training_complete:
            self._on_training_complete(self.history)

        return self._get_summary()

    def _train_epoch(
        self,
        loader: DataLoader,
        optimizer: torch.optim.Optimizer,
        phase: PhaseConfig,
    ) -> Tuple[float, float]:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for batch_idx, (inputs, targets) in enumerate(loader):
            inputs = inputs.to(self.device)
            targets = targets.to(self.device)

            optimizer.zero_grad()
            outputs = self.model(inputs)
            loss = self.criterion(outputs, targets)

            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

        avg_loss = total_loss / len(loader)
        accuracy = correct / total

        return avg_loss, accuracy

    def _validate(self, loader: DataLoader) -> Tuple[float, float]:
        """Validate the model."""
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for inputs, targets in loader:
                inputs = inputs.to(self.device)
                targets = targets.to(self.device)

                outputs = self.model(inputs)
                loss = self.criterion(outputs, targets)

                total_loss += loss.item()
                _, predicted = outputs.max(1)
                total += targets.size(0)
                correct += predicted.eq(targets).sum().item()

        avg_loss = total_loss / len(loader)
        accuracy = correct / total

        return avg_loss, accuracy

    def _save_checkpoint(self, name: str):
        """Save a model checkpoint."""
        if self.config.checkpoint_dir is None:
            return

        self.config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        path = self.config.checkpoint_dir / f"model_{name}.pth"

        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "current_phase": self.current_phase_idx,
            "current_epoch": self.current_epoch,
            "best_val_accuracy": self.best_val_accuracy,
            "config": {
                "total_epochs": self.config.total_epochs,
                "phases": [p.name for p in self.config.phases],
            },
        }

        torch.save(checkpoint, path)
        logger.info(f"Saved checkpoint: {path}")

    def _get_summary(self) -> Dict[str, Any]:
        """Get training summary."""
        return {
            "total_epochs": self.current_epoch + 1,
            "phases_completed": self.current_phase_idx + 1,
            "best_val_accuracy": self.best_val_accuracy,
            "final_train_accuracy": self.history[-1].train_accuracy
            if self.history
            else 0,
            "final_val_accuracy": self.history[-1].val_accuracy if self.history else 0,
            "early_stopped": self.patience_counter
            >= self.config.early_stopping_patience,
            "history": [
                {
                    "epoch": m.epoch,
                    "phase": m.phase.value,
                    "train_loss": m.train_loss,
                    "val_loss": m.val_loss,
                    "train_acc": m.train_accuracy,
                    "val_acc": m.val_accuracy,
                }
                for m in self.history
            ],
        }

    def load_checkpoint(self, path: Path) -> bool:
        """Load a checkpoint and resume training."""
        if not path.exists():
            logger.warning(f"Checkpoint not found: {path}")
            return False

        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.current_phase_idx = checkpoint.get("current_phase", 0)
        self.current_epoch = checkpoint.get("current_epoch", 0)
        self.best_val_accuracy = checkpoint.get("best_val_accuracy", 0.0)

        logger.info(f"Loaded checkpoint from epoch {self.current_epoch}")
        return True


def calculate_class_weights(labels: List[int], num_classes: int) -> torch.Tensor:
    """
    Calculate class weights for imbalanced datasets.

    Args:
        labels: List of class labels
        num_classes: Total number of classes

    Returns:
        Tensor of class weights
    """
    import numpy as np

    counts = np.bincount(labels, minlength=num_classes)
    # Avoid division by zero
    counts = np.maximum(counts, 1)
    # Inverse frequency weighting
    weights = 1.0 / counts
    # Normalize
    weights = weights / weights.sum() * num_classes

    return torch.FloatTensor(weights)
