"""
Settings Manager

Handles configuration loading, merging, and persistence with proper precedence.
"""

import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .hardware_detector import HardwareDetector, HardwareTier
from .profile_loader import GameProfile, GameProfileLoader


@dataclass
class TrainingConfig:
    """Training configuration with all parameters."""

    # Model
    architecture: str = "efficientnet_lstm"
    pretrained: bool = True
    freeze_backbone_epochs: int = 10

    # Input
    input_size: tuple = (224, 224)
    temporal_frames: int = 4
    normalize: str = "imagenet"

    # Training
    batch_size: int = 16
    epochs: int = 50
    learning_rate: float = 0.001
    weight_decay: float = 0.0001
    optimizer: str = "adamw"

    # Scheduler
    scheduler_type: str = "cosine"
    warmup_epochs: int = 5
    min_lr: float = 0.00001

    # Data
    validation_split: float = 0.2
    num_workers: int = 4
    shuffle: bool = True

    # Augmentation
    augmentation_enabled: bool = True
    augmentations: List[str] = field(
        default_factory=lambda: ["brightness", "contrast"]
    )

    # Checkpoints
    save_best: bool = True
    save_interval: int = 5
    early_stopping_patience: int = 10

    # Class balance
    class_balance_enabled: bool = True
    class_balance_method: str = "weighted_loss"


@dataclass
class InferenceConfig:
    """Inference configuration."""

    confidence_threshold: float = 0.7
    cooldown_ms: int = 100
    max_actions_per_second: int = 20
    temporal_buffer_size: int = 4
    use_temporal_smoothing: bool = True
    safety_enabled: bool = True
    emergency_stop_key: str = "F12"
    target_fps: int = 30
    use_half_precision: bool = False


@dataclass
class SessionConfig:
    """Complete session configuration."""

    game_id: str
    task: str
    hardware_tier: str
    training: TrainingConfig
    inference: InferenceConfig

    # Metadata
    created_at: Optional[str] = None
    profile_version: str = "1.0"


class SettingsManager:
    """
    Manages configuration with hierarchical precedence:

    1. Session overrides (highest priority)
    2. User preferences
    3. Game profile + task preset
    4. Hardware-detected recommendations
    5. Global defaults (lowest priority)

    Usage:
        manager = SettingsManager()
        config = manager.create_session_config(
            game_id="world_of_warcraft",
            task="combat"
        )
        print(config.training.architecture)
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the settings manager.

        Args:
            project_root: Project root directory. Auto-detected if None.
        """
        self.project_root = project_root or self._find_project_root()
        self.settings_dir = self.project_root / "settings"

        self._defaults: Optional[Dict] = None
        self._user_prefs: Optional[Dict] = None

        self.hardware_detector = HardwareDetector()
        self.profile_loader = GameProfileLoader(self.project_root / "game_profiles")

    def _find_project_root(self) -> Path:
        """Find the project root directory."""
        current = Path(__file__).parent
        for _ in range(5):
            if (current / "settings").exists() or (current / "pyproject.toml").exists():
                return current
            current = current.parent

        return Path.cwd()

    def _load_defaults(self) -> Dict:
        """Load global defaults."""
        if self._defaults is not None:
            return self._defaults

        defaults_path = self.settings_dir / "defaults.yaml"
        if defaults_path.exists():
            with open(defaults_path) as f:
                self._defaults = yaml.safe_load(f) or {}
        else:
            self._defaults = {}

        return self._defaults

    def _load_user_preferences(self) -> Dict:
        """Load user preferences (if exists)."""
        if self._user_prefs is not None:
            return self._user_prefs

        user_prefs_path = self.settings_dir / "user_preferences.yaml"
        if user_prefs_path.exists():
            with open(user_prefs_path) as f:
                self._user_prefs = yaml.safe_load(f) or {}
        else:
            self._user_prefs = {}

        return self._user_prefs

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dictionaries.

        Values from override take precedence over base.
        """
        result = deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)

        return result

    def create_session_config(
        self,
        game_id: str,
        task: str = "combat",
        overrides: Optional[Dict] = None,
    ) -> SessionConfig:
        """
        Create a complete session configuration.

        Merges settings from all sources with proper precedence.

        Args:
            game_id: Game identifier
            task: Task type (combat, farming, etc.)
            overrides: Optional manual overrides (highest priority)

        Returns:
            SessionConfig with all settings resolved
        """
        # 1. Start with defaults
        defaults = self._load_defaults()

        # 2. Detect hardware
        hw_info = self.hardware_detector.detect()
        tier = hw_info.tier.value

        # 3. Load game profile
        try:
            profile = self.profile_loader.load(game_id)
        except FileNotFoundError:
            profile = None

        # 4. Load user preferences
        user_prefs = self._load_user_preferences()

        # 5. Build merged config
        merged = self._merge_all_sources(
            defaults=defaults,
            hardware_tier=tier,
            profile=profile,
            task=task,
            user_prefs=user_prefs,
            overrides=overrides or {},
        )

        # 6. Create typed config objects
        training_config = self._build_training_config(merged, hw_info)
        inference_config = self._build_inference_config(merged)

        return SessionConfig(
            game_id=game_id,
            task=task,
            hardware_tier=tier,
            training=training_config,
            inference=inference_config,
        )

    def _merge_all_sources(
        self,
        defaults: Dict,
        hardware_tier: str,
        profile: Optional[GameProfile],
        task: str,
        user_prefs: Dict,
        overrides: Dict,
    ) -> Dict:
        """Merge all configuration sources."""
        result = deepcopy(defaults)

        # Apply game profile settings
        if profile:
            tier_config = profile.get_tier_config(hardware_tier)
            task_config = profile.get_task_config(task)

            # Merge profile training settings
            profile_training = {
                "model": {
                    "architecture": tier_config.architecture,
                },
                "input": {
                    "size": tier_config.input_size,
                    "temporal_frames": tier_config.temporal_frames,
                },
                "parameters": {
                    "batch_size": tier_config.batch_size,
                    "learning_rate": profile.learning_rate.get("initial", 0.001),
                },
                "data": {
                    "num_workers": tier_config.workers,
                },
            }

            if task_config:
                profile_training["augmentation"] = {
                    "types": task_config.augmentation,
                }
                # Override architecture if task-specific
                profile_training["model"]["architecture"] = (
                    task_config.recommended_architecture
                )

            result = self._deep_merge(result, {"training": profile_training})

        # Apply user preferences
        result = self._deep_merge(result, user_prefs)

        # Apply session overrides
        result = self._deep_merge(result, overrides)

        return result

    def _build_training_config(
        self, merged: Dict, hw_info: Any
    ) -> TrainingConfig:
        """Build TrainingConfig from merged settings."""
        training = merged.get("training", {})
        model = training.get("model", {})
        input_cfg = training.get("input", {})
        params = training.get("parameters", {})
        scheduler = training.get("scheduler", {})
        data = training.get("data", {})
        aug = training.get("augmentation", {})
        checkpoints = training.get("checkpoints", {})
        early_stop = training.get("early_stopping", {})
        balance = training.get("class_balance", {})

        return TrainingConfig(
            architecture=model.get("architecture", "efficientnet_lstm"),
            pretrained=model.get("pretrained", True),
            freeze_backbone_epochs=model.get("freeze_backbone_epochs", 10),
            input_size=tuple(input_cfg.get("size", [224, 224])),
            temporal_frames=input_cfg.get("temporal_frames", 4),
            normalize=input_cfg.get("normalize", "imagenet"),
            batch_size=params.get("batch_size", 16),
            epochs=params.get("epochs", 50),
            learning_rate=params.get("learning_rate", 0.001),
            weight_decay=params.get("weight_decay", 0.0001),
            optimizer=params.get("optimizer", "adamw"),
            scheduler_type=scheduler.get("type", "cosine"),
            warmup_epochs=scheduler.get("warmup_epochs", 5),
            min_lr=scheduler.get("min_lr", 0.00001),
            validation_split=data.get("validation_split", 0.2),
            num_workers=data.get("num_workers", hw_info.cpu_cores // 2),
            shuffle=data.get("shuffle", True),
            augmentation_enabled=aug.get("enabled", True),
            augmentations=aug.get("types", ["brightness", "contrast"]),
            save_best=checkpoints.get("save_best", True),
            save_interval=checkpoints.get("save_interval", 5),
            early_stopping_patience=early_stop.get("patience", 10),
            class_balance_enabled=balance.get("enabled", True),
            class_balance_method=balance.get("method", "weighted_loss"),
        )

    def _build_inference_config(self, merged: Dict) -> InferenceConfig:
        """Build InferenceConfig from merged settings."""
        inference = merged.get("inference", {})
        confidence = inference.get("confidence", {})
        execution = inference.get("execution", {})
        temporal = inference.get("temporal", {})
        safety = inference.get("safety", {})
        performance = inference.get("performance", {})

        return InferenceConfig(
            confidence_threshold=confidence.get("threshold", 0.7),
            cooldown_ms=execution.get("cooldown_ms", 100),
            max_actions_per_second=execution.get("max_actions_per_second", 20),
            temporal_buffer_size=temporal.get("buffer_size", 4),
            use_temporal_smoothing=temporal.get("use_temporal_smoothing", True),
            safety_enabled=safety.get("enabled", True),
            emergency_stop_key=safety.get("emergency_stop_key", "F12"),
            target_fps=performance.get("target_fps", 30),
            use_half_precision=performance.get("use_half_precision", False),
        )

    def save_session_config(
        self, config: SessionConfig, path: Optional[Path] = None
    ) -> Path:
        """
        Save session configuration to file.

        Args:
            config: SessionConfig to save
            path: Optional custom path. Defaults to settings/session/current.yaml

        Returns:
            Path where config was saved
        """
        if path is None:
            session_dir = self.settings_dir / "session"
            session_dir.mkdir(exist_ok=True)
            path = session_dir / "current_training.yaml"

        from datetime import datetime

        data = {
            "version": config.profile_version,
            "created_at": datetime.now().isoformat(),
            "game_id": config.game_id,
            "task": config.task,
            "hardware_tier": config.hardware_tier,
            "training": {
                "architecture": config.training.architecture,
                "input_size": list(config.training.input_size),
                "temporal_frames": config.training.temporal_frames,
                "batch_size": config.training.batch_size,
                "epochs": config.training.epochs,
                "learning_rate": config.training.learning_rate,
                "optimizer": config.training.optimizer,
                "augmentations": config.training.augmentations,
            },
            "inference": {
                "confidence_threshold": config.inference.confidence_threshold,
                "cooldown_ms": config.inference.cooldown_ms,
                "target_fps": config.inference.target_fps,
                "emergency_stop_key": config.inference.emergency_stop_key,
            },
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        return path

    def get_quick_config(
        self, game_id: str, task: str = "combat"
    ) -> Dict[str, Any]:
        """
        Get a simple dictionary config for quick use.

        Useful for scripts that don't need full SessionConfig.
        """
        config = self.create_session_config(game_id, task)

        return {
            "architecture": config.training.architecture,
            "input_size": config.training.input_size,
            "temporal_frames": config.training.temporal_frames,
            "batch_size": config.training.batch_size,
            "epochs": config.training.epochs,
            "learning_rate": config.training.learning_rate,
            "num_workers": config.training.num_workers,
            "confidence_threshold": config.inference.confidence_threshold,
        }
