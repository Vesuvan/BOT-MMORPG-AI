"""
Setup Wizard Controller

Orchestrates the Zero-to-Hero setup process with a clean, user-friendly flow.
"""

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from bot_mmorpg.config import (
    GameProfileLoader,
    HardwareDetector,
    ModelSelector,
    SettingsManager,
)


class WizardStep(Enum):
    """Wizard steps in order."""

    WELCOME = auto()
    HARDWARE = auto()
    GAME_SELECT = auto()
    TASK_SELECT = auto()
    MODEL_SELECT = auto()
    DATA_GUIDANCE = auto()
    TRAINING_CONFIG = auto()
    REVIEW = auto()
    COMPLETE = auto()


@dataclass
class WizardState:
    """Current state of the wizard."""

    current_step: WizardStep = WizardStep.WELCOME
    completed_steps: List[WizardStep] = field(default_factory=list)

    # User selections
    game_id: Optional[str] = None
    game_name: Optional[str] = None
    task: Optional[str] = None
    architecture: Optional[str] = None
    skill_level: str = "beginner"

    # Detected/computed values
    hardware_tier: Optional[str] = None
    hardware_summary: Optional[str] = None
    recommended_architecture: Optional[str] = None
    recommended_samples: int = 5000

    # Configuration
    batch_size: int = 16
    epochs: int = 50
    learning_rate: float = 0.001
    input_size: tuple = (224, 224)
    temporal_frames: int = 4

    # Final config
    final_config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for saving."""
        return {
            "game_id": self.game_id,
            "game_name": self.game_name,
            "task": self.task,
            "architecture": self.architecture,
            "skill_level": self.skill_level,
            "hardware_tier": self.hardware_tier,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "input_size": list(self.input_size),
            "temporal_frames": self.temporal_frames,
        }


class SetupWizard:
    """
    Zero-to-Hero Setup Wizard

    Guides users through the complete setup process with intelligent
    defaults and clear explanations.

    Usage:
        wizard = SetupWizard()

        # CLI mode
        wizard.run_cli()

        # Or programmatic mode
        wizard.start()
        wizard.set_game("world_of_warcraft")
        wizard.set_task("combat")
        config = wizard.finish()
    """

    STEP_ORDER = [
        WizardStep.WELCOME,
        WizardStep.HARDWARE,
        WizardStep.GAME_SELECT,
        WizardStep.TASK_SELECT,
        WizardStep.MODEL_SELECT,
        WizardStep.DATA_GUIDANCE,
        WizardStep.TRAINING_CONFIG,
        WizardStep.REVIEW,
        WizardStep.COMPLETE,
    ]

    def __init__(self):
        self.state = WizardState()
        self.hardware_detector = HardwareDetector()
        self.profile_loader = GameProfileLoader()
        self.model_selector = ModelSelector()
        self.settings_manager = SettingsManager()

        # Callbacks for UI integration
        self._on_step_change: Optional[Callable] = None
        self._on_recommendation: Optional[Callable] = None

    def start(self) -> WizardState:
        """Start the wizard and return initial state."""
        self.state = WizardState()
        self._detect_hardware()
        return self.state

    def _detect_hardware(self):
        """Detect hardware capabilities."""
        info = self.hardware_detector.detect()
        self.state.hardware_tier = info.tier.value
        self.state.hardware_summary = info.summary()

    # Step handlers

    def set_game(self, game_id: str) -> Dict[str, Any]:
        """
        Set the selected game and get available tasks.

        Returns dict with tasks and recommendations.
        """
        try:
            profile = self.profile_loader.load(game_id)
            self.state.game_id = game_id
            self.state.game_name = profile.name

            # Get available tasks
            tasks = []
            for task_name in profile.list_tasks():
                task_config = profile.get_task_config(task_name)
                tasks.append(
                    {
                        "id": task_name,
                        "name": task_name.replace("_", " ").title(),
                        "description": task_config.description if task_config else "",
                        "temporal": task_config.temporal if task_config else False,
                    }
                )

            self._complete_step(WizardStep.GAME_SELECT)

            return {
                "game_name": profile.name,
                "tasks": tasks,
                "recommended_samples": profile.minimum_samples,
            }

        except FileNotFoundError:
            # Custom game - use defaults
            self.state.game_id = game_id
            self.state.game_name = game_id.replace("_", " ").title()

            return {
                "game_name": self.state.game_name,
                "tasks": self._default_tasks(),
                "recommended_samples": 5000,
            }

    def _default_tasks(self) -> List[Dict]:
        """Default tasks for custom games."""
        return [
            {
                "id": "combat",
                "name": "Combat",
                "description": "Real-time combat with reaction requirements",
                "temporal": True,
            },
            {
                "id": "farming",
                "name": "Farming",
                "description": "Resource gathering and repetitive tasks",
                "temporal": False,
            },
            {
                "id": "navigation",
                "name": "Navigation",
                "description": "Pathfinding and movement",
                "temporal": True,
            },
            {
                "id": "crafting",
                "name": "Crafting",
                "description": "Crafting UI interaction",
                "temporal": False,
            },
        ]

    def set_task(self, task: str) -> Dict[str, Any]:
        """
        Set the selected task and get model recommendations.

        Returns dict with recommended model and alternatives.
        """
        self.state.task = task

        # Get model recommendation
        recommendation = self.model_selector.recommend(
            game_id=self.state.game_id, task=task
        )

        self.state.recommended_architecture = recommendation.architecture.value
        self.state.architecture = recommendation.architecture.value  # Default selection
        self.state.batch_size = recommendation.recommended_batch_size
        self.state.input_size = recommendation.recommended_input_size
        self.state.temporal_frames = recommendation.recommended_temporal_frames

        # Get alternatives
        alternatives = self.model_selector.list_architectures()

        self._complete_step(WizardStep.TASK_SELECT)

        return {
            "recommended": {
                "id": recommendation.architecture.value,
                "name": recommendation.architecture.display_name,
                "confidence": recommendation.confidence,
                "reasons": recommendation.reasons,
                "warnings": recommendation.warnings,
                "speed": recommendation.estimated_speed,
                "accuracy": recommendation.estimated_accuracy,
            },
            "alternatives": alternatives,
            "hardware_tier": self.state.hardware_tier,
        }

    def set_model(self, architecture: str) -> Dict[str, Any]:
        """
        Set the selected model architecture.

        Returns configuration details.
        """
        self.state.architecture = architecture

        # Update config based on model
        is_temporal = "lstm" in architecture.lower()
        if not is_temporal:
            self.state.temporal_frames = 0

        self._complete_step(WizardStep.MODEL_SELECT)

        return {
            "architecture": architecture,
            "temporal_frames": self.state.temporal_frames,
            "input_size": self.state.input_size,
            "batch_size": self.state.batch_size,
        }

    def get_data_guidance(self) -> Dict[str, Any]:
        """
        Get data collection guidance.

        Returns recommended samples, tips, and quality requirements.
        """
        try:
            profile = self.profile_loader.load(self.state.game_id)
            min_samples = profile.minimum_samples
        except (FileNotFoundError, TypeError):
            min_samples = 5000

        self.state.recommended_samples = min_samples

        temporal = self.state.temporal_frames > 0

        tips = [
            "Play naturally - the bot learns from your playstyle",
            "Include variety - different situations help generalization",
            "Maintain consistent key bindings during recording",
        ]

        if temporal:
            tips.extend(
                [
                    "Record continuous gameplay sessions (not short clips)",
                    "Include combat sequences with enemy reactions",
                ]
            )

        quality_checks = [
            {"name": "Minimum Samples", "target": min_samples, "importance": "critical"},
            {
                "name": "Class Balance",
                "target": "< 3:1 ratio",
                "importance": "high",
            },
            {"name": "No Blur/Corruption", "target": "100%", "importance": "medium"},
        ]

        self._complete_step(WizardStep.DATA_GUIDANCE)

        return {
            "minimum_samples": min_samples,
            "tips": tips,
            "quality_checks": quality_checks,
            "temporal_recording": temporal,
        }

    def set_training_config(
        self,
        epochs: Optional[int] = None,
        batch_size: Optional[int] = None,
        learning_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Set custom training configuration (optional).

        If not called, uses recommended defaults.
        """
        if epochs is not None:
            self.state.epochs = epochs
        if batch_size is not None:
            self.state.batch_size = batch_size
        if learning_rate is not None:
            self.state.learning_rate = learning_rate

        self._complete_step(WizardStep.TRAINING_CONFIG)

        return {
            "epochs": self.state.epochs,
            "batch_size": self.state.batch_size,
            "learning_rate": self.state.learning_rate,
        }

    def get_review(self) -> Dict[str, Any]:
        """
        Get complete configuration review before starting.

        Returns all settings for user confirmation.
        """
        self._complete_step(WizardStep.REVIEW)

        return {
            "game": {"id": self.state.game_id, "name": self.state.game_name},
            "task": self.state.task,
            "hardware": {
                "tier": self.state.hardware_tier,
                "summary": self.state.hardware_summary,
            },
            "model": {
                "architecture": self.state.architecture,
                "input_size": self.state.input_size,
                "temporal_frames": self.state.temporal_frames,
            },
            "training": {
                "epochs": self.state.epochs,
                "batch_size": self.state.batch_size,
                "learning_rate": self.state.learning_rate,
            },
            "data": {"minimum_samples": self.state.recommended_samples},
        }

    def finish(self) -> Dict[str, Any]:
        """
        Finalize the wizard and generate complete configuration.

        Returns the final configuration ready for training.
        """
        # Create session config using settings manager
        session_config = self.settings_manager.create_session_config(
            game_id=self.state.game_id,
            task=self.state.task,
            overrides={
                "training": {
                    "model": {"architecture": self.state.architecture},
                    "input": {
                        "size": list(self.state.input_size),
                        "temporal_frames": self.state.temporal_frames,
                    },
                    "parameters": {
                        "epochs": self.state.epochs,
                        "batch_size": self.state.batch_size,
                        "learning_rate": self.state.learning_rate,
                    },
                }
            },
        )

        # Save session config
        config_path = self.settings_manager.save_session_config(session_config)

        self.state.final_config = self.state.to_dict()
        self._complete_step(WizardStep.COMPLETE)

        return {
            "config": self.state.final_config,
            "config_path": str(config_path),
            "ready_for_training": True,
            "next_steps": [
                "1. Start data collection with F9 (default)",
                "2. Play the game naturally - bot learns from you",
                f"3. Collect at least {self.state.recommended_samples} samples",
                "4. Start training from the Training tab",
            ],
        }

    def _complete_step(self, step: WizardStep):
        """Mark a step as completed."""
        if step not in self.state.completed_steps:
            self.state.completed_steps.append(step)

        # Move to next step
        current_idx = self.STEP_ORDER.index(step)
        if current_idx < len(self.STEP_ORDER) - 1:
            self.state.current_step = self.STEP_ORDER[current_idx + 1]

    def get_progress(self) -> Dict[str, Any]:
        """Get wizard progress information."""
        total_steps = len(self.STEP_ORDER) - 2  # Exclude WELCOME and COMPLETE
        completed = len(
            [s for s in self.state.completed_steps if s not in (WizardStep.WELCOME, WizardStep.COMPLETE)]
        )

        return {
            "current_step": self.state.current_step.name,
            "completed_steps": [s.name for s in self.state.completed_steps],
            "progress_percent": int((completed / total_steps) * 100),
            "steps_remaining": total_steps - completed,
        }

    # CLI Interface

    def run_cli(self):
        """Run the wizard in CLI mode."""
        print("\n" + "=" * 60)
        print("  BOT-MMORPG-AI: Zero-to-Hero Setup Wizard")
        print("=" * 60 + "\n")

        self.start()

        # Hardware detection
        print("Detecting hardware...")
        print(f"\n{self.state.hardware_summary}\n")
        print(f"Hardware Tier: {self.state.hardware_tier.upper()}")
        input("\nPress Enter to continue...")

        # Game selection
        print("\n" + "-" * 40)
        print("Step 1: Select Your Game")
        print("-" * 40)
        games = self.profile_loader.list_games()
        for i, game in enumerate(games, 1):
            print(f"  {i}. {game['name']}")
        print(f"  {len(games) + 1}. Custom Game")

        choice = int(input("\nEnter choice: ")) - 1
        if choice < len(games):
            game_id = games[choice]["id"]
        else:
            game_id = input("Enter custom game ID (e.g., my_game): ")

        result = self.set_game(game_id)
        print(f"\nSelected: {result['game_name']}")

        # Task selection
        print("\n" + "-" * 40)
        print("Step 2: Select Your Task")
        print("-" * 40)
        for i, task in enumerate(result["tasks"], 1):
            temporal_str = " (temporal)" if task["temporal"] else ""
            print(f"  {i}. {task['name']}{temporal_str}")
            print(f"     {task['description']}")

        choice = int(input("\nEnter choice: ")) - 1
        task_id = result["tasks"][choice]["id"]
        result = self.set_task(task_id)

        # Model recommendation
        print("\n" + "-" * 40)
        print("Step 3: Model Selection")
        print("-" * 40)
        rec = result["recommended"]
        print(f"\n  Recommended: {rec['name']}")
        print(f"  Confidence: {rec['confidence']:.0%}")
        print("\n  Why this model:")
        for reason in rec["reasons"]:
            print(f"    + {reason}")

        if rec["warnings"]:
            print("\n  Notes:")
            for warning in rec["warnings"]:
                print(f"    ! {warning}")

        use_recommended = input("\nUse recommended model? [Y/n]: ").lower() != "n"
        if not use_recommended:
            print("\nAvailable models:")
            for i, alt in enumerate(result["alternatives"], 1):
                print(f"  {i}. {alt['name']}")
            choice = int(input("Enter choice: ")) - 1
            arch = result["alternatives"][choice]["id"]
        else:
            arch = rec["id"]

        self.set_model(arch)

        # Data guidance
        print("\n" + "-" * 40)
        print("Step 4: Data Collection Tips")
        print("-" * 40)
        guidance = self.get_data_guidance()
        print(f"\n  Minimum samples needed: {guidance['minimum_samples']}")
        print("\n  Tips:")
        for tip in guidance["tips"]:
            print(f"    - {tip}")

        input("\nPress Enter to continue...")

        # Review
        print("\n" + "-" * 40)
        print("Step 5: Review Configuration")
        print("-" * 40)
        review = self.get_review()
        print(f"\n  Game: {review['game']['name']}")
        print(f"  Task: {review['task']}")
        print(f"  Model: {review['model']['architecture']}")
        print(f"  Input Size: {review['model']['input_size']}")
        print(f"  Epochs: {review['training']['epochs']}")
        print(f"  Batch Size: {review['training']['batch_size']}")

        confirm = input("\nProceed with this configuration? [Y/n]: ").lower() != "n"
        if not confirm:
            print("\nWizard cancelled.")
            return None

        # Finish
        result = self.finish()
        print("\n" + "=" * 60)
        print("  Setup Complete!")
        print("=" * 60)
        print(f"\n  Configuration saved to: {result['config_path']}")
        print("\n  Next steps:")
        for step in result["next_steps"]:
            print(f"    {step}")

        return result


# CLI entry point
if __name__ == "__main__":
    wizard = SetupWizard()
    wizard.run_cli()
