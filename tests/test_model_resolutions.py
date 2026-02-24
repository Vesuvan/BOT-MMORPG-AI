"""
Test neural network models with variable input resolutions.

This test verifies that our models can handle different input resolutions,
which is essential for supporting various game capture settings.

Resolution Support:
- 480x270: Default (NN optimized)
- 640x360: Low resolution
- 960x540: Medium resolution (tested here as second resolution)
- 1280x720: HD (max supported, experimental)
"""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(ROOT / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)


# Skip all tests if PyTorch not available
try:
    import torch

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PYTORCH_AVAILABLE, reason="PyTorch required for model resolution tests"
)


# Test resolutions: default (480x270) and medium (960x540)
# We test these two to verify models handle variable input sizes
TEST_RESOLUTIONS = [
    (480, 270, "default"),  # Default NN resolution
    (960, 540, "medium"),  # Medium resolution (4x pixels)
]


@pytest.fixture
def device():
    """Get available device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class TestModelResolutions:
    """Test that models work with different input resolutions."""

    def test_efficientnet_lstm_resolutions(self, device):
        """Test EfficientNet-LSTM with multiple resolutions."""
        from bot_mmorpg.scripts.models_pytorch import get_model

        model = get_model("efficientnet_lstm", num_actions=29, pretrained=False)
        model.to(device)
        model.eval()

        for width, height, name in TEST_RESOLUTIONS:
            # Single frame input
            x_single = torch.randn(1, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x_single)

            assert output.shape == (1, 29), (
                f"EfficientNet-LSTM {name} ({width}x{height}) single frame: "
                f"expected (1, 29), got {output.shape}"
            )

            # Sequence input (4 frames)
            x_seq = torch.randn(1, 4, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x_seq)

            assert output.shape == (1, 29), (
                f"EfficientNet-LSTM {name} ({width}x{height}) sequence: "
                f"expected (1, 29), got {output.shape}"
            )

    def test_efficientnet_simple_resolutions(self, device):
        """Test EfficientNet (simple) with multiple resolutions."""
        from bot_mmorpg.scripts.models_pytorch import get_model

        model = get_model("efficientnet_simple", num_actions=29, pretrained=False)
        model.to(device)
        model.eval()

        for width, height, name in TEST_RESOLUTIONS:
            x = torch.randn(1, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x)

            assert output.shape == (1, 29), (
                f"EfficientNet-Simple {name} ({width}x{height}): "
                f"expected (1, 29), got {output.shape}"
            )

    def test_mobilenetv3_resolutions(self, device):
        """Test MobileNetV3 with multiple resolutions."""
        from bot_mmorpg.scripts.models_pytorch import get_model

        model = get_model("mobilenet_v3", num_actions=29, pretrained=False)
        model.to(device)
        model.eval()

        for width, height, name in TEST_RESOLUTIONS:
            x = torch.randn(1, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x)

            assert output.shape == (1, 29), (
                f"MobileNetV3 {name} ({width}x{height}): " f"expected (1, 29), got {output.shape}"
            )

    def test_resnet18_lstm_resolutions(self, device):
        """Test ResNet18-LSTM with multiple resolutions."""
        from bot_mmorpg.scripts.models_pytorch import get_model

        model = get_model("resnet18_lstm", num_actions=29, pretrained=False)
        model.to(device)
        model.eval()

        for width, height, name in TEST_RESOLUTIONS:
            # Single frame
            x_single = torch.randn(1, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x_single)

            assert output.shape == (1, 29), (
                f"ResNet18-LSTM {name} ({width}x{height}) single: "
                f"expected (1, 29), got {output.shape}"
            )

            # Sequence (4 frames)
            x_seq = torch.randn(1, 4, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x_seq)

            assert output.shape == (1, 29), (
                f"ResNet18-LSTM {name} ({width}x{height}) sequence: "
                f"expected (1, 29), got {output.shape}"
            )

    def test_alexnet_resolutions(self, device):
        """Test AlexNet (legacy) with multiple resolutions."""
        from bot_mmorpg.scripts.models_pytorch import get_model

        model = get_model("alexnet", num_actions=29)
        model.to(device)
        model.eval()

        for width, height, name in TEST_RESOLUTIONS:
            x = torch.randn(1, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x)

            assert output.shape == (1, 29), (
                f"AlexNet {name} ({width}x{height}): " f"expected (1, 29), got {output.shape}"
            )

    def test_sentnet_2d_resolutions(self, device):
        """Test SentNet 2D (legacy) with multiple resolutions."""
        from bot_mmorpg.scripts.models_pytorch import get_model

        model = get_model("sentnet_2d", num_actions=29)
        model.to(device)
        model.eval()

        for width, height, name in TEST_RESOLUTIONS:
            x = torch.randn(1, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x)

            assert output.shape == (1, 29), (
                f"SentNet2D {name} ({width}x{height}): " f"expected (1, 29), got {output.shape}"
            )


class TestResolutionConfig:
    """Test resolution configuration module."""

    def test_game_config_exists(self):
        """Test that game configurations are properly defined."""
        from bot_mmorpg.config.game_resolutions import get_game_config

        # Test known games
        known_games = [
            "genshin_impact",
            "world_of_warcraft",
            "final_fantasy_xiv",
            "guild_wars_2",
            "lost_ark",
        ]

        for game_id in known_games:
            config = get_game_config(game_id)
            assert config is not None, f"Missing config for {game_id}"
            assert config.game_id == game_id
            assert config.recommended_resolution is not None

    def test_resolution_parsing(self):
        """Test resolution string parsing."""
        from bot_mmorpg.config.game_resolutions import parse_resolution

        assert parse_resolution("480x270") == (480, 270)
        assert parse_resolution("640x360") == (640, 360)
        assert parse_resolution("1280x720") == (1280, 720)
        assert parse_resolution("native") == (0, 0)
        assert parse_resolution("invalid") == (480, 270)  # Default fallback

    def test_performance_estimate(self):
        """Test performance estimation for resolutions."""
        from bot_mmorpg.config.game_resolutions import get_performance_estimate

        # Default resolution should have baseline performance
        perf_480 = get_performance_estimate(480, 270)
        assert perf_480["training_speed"] == 1.0
        assert perf_480["recommended"] is True

        # Higher resolutions should be slower
        perf_720 = get_performance_estimate(1280, 720)
        assert perf_720["training_speed"] < perf_480["training_speed"]
        assert perf_720["memory_usage"] > perf_480["memory_usage"]

    def test_ui_options(self):
        """Test UI dropdown options generation."""
        from bot_mmorpg.config.game_resolutions import get_resolution_options_for_ui

        options = get_resolution_options_for_ui()
        assert len(options) >= 4  # At least 4 resolution options

        # Check that one is recommended
        recommended = [o for o in options if o.get("recommended")]
        assert len(recommended) >= 1, "Should have at least one recommended option"

        # Check native option exists
        native = [o for o in options if o["value"] == "native"]
        assert len(native) == 1, "Should have native option"


class TestResolutionConsistency:
    """Test that output shapes are consistent across resolutions."""

    def test_output_shape_consistency(self, device):
        """
        Verify that different input resolutions produce same output shape.

        This is critical - the model should always output (batch, num_actions)
        regardless of input resolution, thanks to AdaptiveAvgPool layers.
        """
        from bot_mmorpg.scripts.models_pytorch import get_model

        model = get_model("efficientnet_lstm", num_actions=29, pretrained=False)
        model.to(device)
        model.eval()

        # Test with all supported resolutions
        resolutions = [
            (480, 270),  # Default
            (640, 360),  # Low
            (960, 540),  # Medium
            (1280, 720),  # HD (max)
        ]

        outputs = []
        for width, height in resolutions:
            x = torch.randn(1, 3, height, width).to(device)
            with torch.no_grad():
                output = model(x)
            outputs.append(output.shape)

        # All outputs should be identical
        expected_shape = (1, 29)
        for i, (shape, (w, h)) in enumerate(zip(outputs, resolutions)):
            assert (
                shape == expected_shape
            ), f"Resolution {w}x{h} produced shape {shape}, expected {expected_shape}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
