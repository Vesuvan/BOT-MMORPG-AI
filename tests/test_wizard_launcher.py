"""
Tests for UI Launcher Wizard

Tests the Setup Wizard controller that guides users through configuration.
"""

import pytest


class TestWizardState:
    """Test wizard state management."""

    def test_initial_state(self):
        """Test initial wizard state."""
        from launcher.wizard.wizard_controller import WizardState, WizardStep

        state = WizardState()

        assert state.current_step == WizardStep.WELCOME
        assert state.completed_steps == []
        assert state.game_id is None
        assert state.task is None
        assert state.architecture is None

    def test_state_to_dict(self):
        """Test state serialization."""
        from launcher.wizard.wizard_controller import WizardState

        state = WizardState()
        state.game_id = "world_of_warcraft"
        state.task = "combat"
        state.architecture = "efficientnet_lstm"

        data = state.to_dict()

        assert data["game_id"] == "world_of_warcraft"
        assert data["task"] == "combat"
        assert data["architecture"] == "efficientnet_lstm"
        assert isinstance(data["input_size"], list)


class TestSetupWizard:
    """Test wizard workflow."""

    @pytest.fixture
    def wizard(self):
        """Create a wizard instance with mocked dependencies."""
        from launcher.wizard.wizard_controller import SetupWizard

        wizard = SetupWizard()
        return wizard

    def test_wizard_start(self, wizard):
        """Test wizard initialization."""
        state = wizard.start()

        assert state is not None
        assert state.hardware_tier is not None
        assert state.hardware_summary is not None

    def test_set_game_builtin(self, wizard):
        """Test setting a built-in game."""
        wizard.start()
        result = wizard.set_game("world_of_warcraft")

        assert result["game_name"] == "World of Warcraft"
        assert "tasks" in result
        assert len(result["tasks"]) > 0
        assert wizard.state.game_id == "world_of_warcraft"

    def test_set_game_custom(self, wizard):
        """Test setting a custom game."""
        wizard.start()
        result = wizard.set_game("my_custom_game")

        assert result["game_name"] == "My Custom Game"
        assert "tasks" in result
        # Custom games get default tasks
        assert len(result["tasks"]) > 0

    def test_set_task(self, wizard):
        """Test task selection and model recommendation."""
        wizard.start()
        wizard.set_game("world_of_warcraft")
        result = wizard.set_task("combat")

        assert wizard.state.task == "combat"
        assert "recommended" in result
        assert result["recommended"]["confidence"] > 0
        assert "alternatives" in result

    def test_set_model(self, wizard):
        """Test model selection."""
        wizard.start()
        wizard.set_game("world_of_warcraft")
        wizard.set_task("combat")
        result = wizard.set_model("efficientnet_lstm")

        assert wizard.state.architecture == "efficientnet_lstm"
        assert result["architecture"] == "efficientnet_lstm"

    def test_data_guidance(self, wizard):
        """Test data collection guidance."""
        wizard.start()
        wizard.set_game("world_of_warcraft")
        wizard.set_task("combat")
        wizard.set_model("efficientnet_lstm")
        result = wizard.get_data_guidance()

        assert "minimum_samples" in result
        assert result["minimum_samples"] > 0
        assert "tips" in result
        assert len(result["tips"]) > 0

    def test_training_config(self, wizard):
        """Test training configuration."""
        wizard.start()
        result = wizard.set_training_config(epochs=100, batch_size=32)

        assert result["epochs"] == 100
        assert result["batch_size"] == 32
        assert wizard.state.epochs == 100
        assert wizard.state.batch_size == 32

    def test_review(self, wizard):
        """Test configuration review."""
        wizard.start()
        wizard.set_game("world_of_warcraft")
        wizard.set_task("combat")
        wizard.set_model("efficientnet_lstm")
        wizard.get_data_guidance()
        result = wizard.get_review()

        assert "game" in result
        assert result["game"]["id"] == "world_of_warcraft"
        assert "model" in result
        assert "training" in result

    def test_finish(self, wizard, tmp_path):
        """Test wizard completion."""
        # Mock the settings manager to use tmp directory
        wizard.settings_manager.user_dir = tmp_path

        wizard.start()
        wizard.set_game("world_of_warcraft")
        wizard.set_task("combat")
        wizard.set_model("efficientnet_lstm")
        wizard.get_data_guidance()
        wizard.get_review()
        result = wizard.finish()

        assert result["ready_for_training"] is True
        assert "config_path" in result
        assert "next_steps" in result
        assert len(result["next_steps"]) > 0

    def test_progress_tracking(self, wizard):
        """Test progress tracking through wizard."""
        wizard.start()
        progress1 = wizard.get_progress()

        wizard.set_game("world_of_warcraft")
        progress2 = wizard.get_progress()

        wizard.set_task("combat")
        progress3 = wizard.get_progress()

        # Progress should increase
        assert progress2["progress_percent"] > progress1["progress_percent"]
        assert progress3["progress_percent"] > progress2["progress_percent"]


class TestWizardSteps:
    """Test wizard step enum and ordering."""

    def test_step_order(self):
        """Test step ordering is correct."""
        from launcher.wizard.wizard_controller import SetupWizard, WizardStep

        expected_order = [
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

        assert SetupWizard.STEP_ORDER == expected_order


class TestWizardDefaultTasks:
    """Test default task generation for custom games."""

    def test_default_tasks_content(self):
        """Test default tasks for custom games."""
        from launcher.wizard.wizard_controller import SetupWizard

        wizard = SetupWizard()
        tasks = wizard._default_tasks()

        task_ids = [t["id"] for t in tasks]

        assert "combat" in task_ids
        assert "farming" in task_ids
        assert "navigation" in task_ids
        assert "crafting" in task_ids

        # Combat should be temporal
        combat = next(t for t in tasks if t["id"] == "combat")
        assert combat["temporal"] is True

        # Farming should not be temporal
        farming = next(t for t in tasks if t["id"] == "farming")
        assert farming["temporal"] is False
