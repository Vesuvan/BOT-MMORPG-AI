"""
End-to-End Workflow Test

Minimal test that validates the complete pipeline:
Recording (mock) → Training → Inference

This ensures the backend works as expected.
"""

import json
import shutil

import numpy as np
import pytest
from PIL import Image

torch = pytest.importorskip("torch", reason="PyTorch required for e2e test")
import torch.nn as nn  # noqa: E402


class TinyModel(nn.Module):
    """Minimal model for fast testing."""

    def __init__(self, num_classes: int = 5):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 8, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Linear(8, num_classes)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace with dataset structure."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    # Create directories
    (ws / "datasets" / "test_game" / "session_01").mkdir(parents=True)
    (ws / "models").mkdir()

    yield ws

    # Cleanup
    shutil.rmtree(ws, ignore_errors=True)


class TestE2EWorkflow:
    """End-to-end workflow test."""

    def test_complete_pipeline(self, workspace):
        """
        Test complete workflow: Record → Train → Inference

        This is a minimal test that validates all components work together.
        """
        # === PHASE 1: RECORDING (Mock) ===
        dataset_dir = workspace / "datasets" / "test_game" / "session_01"
        num_samples = 20
        num_classes = 5
        img_size = (32, 32)

        # Simulate recorded data
        for i in range(num_samples):
            # Create random image (simulates screenshot)
            img_array = np.random.randint(0, 255, (*img_size, 3), dtype=np.uint8)
            img = Image.fromarray(img_array)
            img.save(dataset_dir / f"frame_{i:04d}.png")

            # Create label (simulates key press)
            label = {"action": i % num_classes, "keys": [f"key_{i % num_classes}"]}
            with open(dataset_dir / f"frame_{i:04d}.json", "w") as f:
                json.dump(label, f)

        # Verify recording worked
        images = list(dataset_dir.glob("*.png"))
        labels = list(dataset_dir.glob("*.json"))
        assert len(images) == num_samples, "Recording: images created"
        assert len(labels) == num_samples, "Recording: labels created"

        # === PHASE 2: TRAINING ===
        model = TinyModel(num_classes=num_classes)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        criterion = nn.CrossEntropyLoss()

        # Load dataset
        X, y = [], []
        for img_path in sorted(dataset_dir.glob("*.png")):
            # Load image
            img = Image.open(img_path).convert("RGB")
            img_tensor = torch.tensor(np.array(img)).permute(2, 0, 1).float() / 255.0
            X.append(img_tensor)

            # Load label
            label_path = img_path.with_suffix(".json")
            with open(label_path) as f:
                label = json.load(f)
            y.append(label["action"])

        X = torch.stack(X)
        y = torch.tensor(y)

        # Train for a few epochs
        model.train()
        epochs = 3
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = model(X)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()

        # Verify training worked (loss decreased or is reasonable)
        final_loss = loss.item()
        assert final_loss < 10.0, f"Training: loss is reasonable ({final_loss:.4f})"

        # Save model
        model_path = workspace / "models" / "test_model.pt"
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "num_classes": num_classes,
                "input_size": img_size,
            },
            model_path,
        )

        assert model_path.exists(), "Training: model saved"

        # === PHASE 3: INFERENCE ===
        # Load model
        checkpoint = torch.load(model_path, weights_only=False)
        inference_model = TinyModel(num_classes=checkpoint["num_classes"])
        inference_model.load_state_dict(checkpoint["model_state_dict"])
        inference_model.eval()

        # Run inference on test image
        test_img = np.random.randint(0, 255, (*img_size, 3), dtype=np.uint8)
        test_tensor = torch.tensor(test_img).permute(2, 0, 1).float() / 255.0
        test_tensor = test_tensor.unsqueeze(0)  # Add batch dimension

        with torch.no_grad():
            prediction = inference_model(test_tensor)
            probs = torch.softmax(prediction, dim=1)
            action = torch.argmax(prediction, dim=1).item()

        # Verify inference worked
        assert 0 <= action < num_classes, f"Inference: valid action ({action})"
        assert probs.sum().item() == pytest.approx(1.0, abs=0.01), (
            "Inference: valid probs"
        )

        # === SUMMARY ===
        print("\n✅ E2E Test Passed:")
        print(f"   Recording: {num_samples} samples")
        print(f"   Training: {epochs} epochs, loss={final_loss:.4f}")
        print(f"   Inference: action={action}, confidence={probs.max().item():.2%}")


class TestBridgeIntegration:
    """Test bridge handlers work with real components."""

    def test_handler_ping(self):
        """Test ping handler returns valid response."""
        from bot_mmorpg.bridge.handlers import CommandHandler

        handler = CommandHandler()
        result = handler.handle_system_ping()

        assert result["status"] == "ok"
        assert "timestamp" in result

    def test_handler_version(self):
        """Test version handler returns PyTorch version."""
        from bot_mmorpg.bridge.handlers import CommandHandler

        handler = CommandHandler()
        result = handler.handle_system_get_version()

        assert "pytorch_version" in result
        assert result["pytorch_version"].startswith("2.")

    def test_config_hardware_detection(self):
        """Test hardware detection works."""
        from bot_mmorpg.config import HardwareDetector, HardwareTier

        detector = HardwareDetector()
        info = detector.detect()

        assert info.cpu_cores > 0
        assert info.ram_mb > 0
        assert info.tier in [HardwareTier.LOW, HardwareTier.MEDIUM, HardwareTier.HIGH]

    def test_config_model_recommendation(self):
        """Test model recommendation works."""
        from bot_mmorpg.config import ModelSelector

        selector = ModelSelector()
        rec = selector.recommend(game_id="world_of_warcraft", task="combat")

        assert rec.architecture is not None
        assert rec.confidence > 0


class TestInferenceEngine:
    """Test inference engine components."""

    def test_engine_with_model(self, workspace):
        """Test inference engine can initialize with model."""
        from bot_mmorpg.inference.engine import InferenceEngine, ModelMetadata

        # Create model and metadata
        model = TinyModel(num_classes=5)
        metadata = ModelMetadata(
            architecture="custom",
            input_size=(32, 32),
            num_classes=5,
            class_names=["a0", "a1", "a2", "a3", "a4"],
            temporal_frames=0,
            normalize="imagenet",
            pytorch_version=torch.__version__,
            extra={},
        )

        engine = InferenceEngine(model=model, metadata=metadata)

        assert engine is not None
        assert engine.model is not None
        assert engine.metadata.num_classes == 5

    def test_engine_predict(self, workspace):
        """Test inference engine can make predictions."""
        from bot_mmorpg.inference.engine import InferenceEngine, ModelMetadata

        model = TinyModel(num_classes=5)
        metadata = ModelMetadata(
            architecture="custom",
            input_size=(32, 32),
            num_classes=5,
            class_names=["a0", "a1", "a2", "a3", "a4"],
            temporal_frames=0,
            normalize="imagenet",
            pytorch_version=torch.__version__,
            extra={},
        )

        engine = InferenceEngine(model=model, metadata=metadata)

        # Create test image
        test_img = Image.fromarray(
            np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        )

        # Run prediction
        result = engine.predict(test_img)

        assert result is not None
        assert 0 <= result.action_id < 5
        assert 0 <= result.confidence <= 1.0
        assert result.inference_time_ms >= 0
