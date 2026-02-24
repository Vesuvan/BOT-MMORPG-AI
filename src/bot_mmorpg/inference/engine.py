"""
Unified Inference Engine

A model-agnostic inference engine that:
- Auto-detects model architecture from checkpoint
- Handles temporal buffering for LSTM models
- Provides consistent API across all architectures
- Includes safety features and rate limiting
"""

import logging
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """Result of a single inference."""

    action_id: int
    action_name: str
    confidence: float
    all_probabilities: Dict[str, float]
    temporal_context: int  # Number of frames used
    inference_time_ms: float


@dataclass
class ModelMetadata:
    """Metadata loaded from checkpoint."""

    architecture: str
    input_size: Tuple[int, int]
    num_classes: int
    class_names: List[str]
    temporal_frames: int
    normalize: str  # imagenet, [0,1], [-1,1]
    pytorch_version: str
    extra: Dict[str, Any]


class TemporalBuffer:
    """Buffer for temporal models (LSTM)."""

    def __init__(self, max_frames: int):
        self.max_frames = max_frames
        self.buffer: Deque[torch.Tensor] = deque(maxlen=max_frames)

    def add(self, frame: torch.Tensor):
        """Add a frame to the buffer."""
        self.buffer.append(frame)

    def get_sequence(self) -> Optional[torch.Tensor]:
        """Get the current sequence for inference."""
        if len(self.buffer) < self.max_frames:
            return None

        # Stack frames: (temporal_frames, C, H, W)
        return torch.stack(list(self.buffer), dim=0)

    def is_ready(self) -> bool:
        """Check if buffer has enough frames."""
        return len(self.buffer) >= self.max_frames

    def clear(self):
        """Clear the buffer."""
        self.buffer.clear()


class InferenceEngine:
    """
    Unified inference engine for all model architectures.

    Automatically handles:
    - Model loading and architecture detection
    - Preprocessing based on model requirements
    - Temporal buffering for LSTM models
    - Confidence thresholding
    - Rate limiting for actions

    Usage:
        engine = InferenceEngine.from_checkpoint("model.pth")
        result = engine.predict(frame)
        if result.confidence > 0.7:
            execute_action(result.action_name)
    """

    # ImageNet normalization
    IMAGENET_MEAN = [0.485, 0.456, 0.406]
    IMAGENET_STD = [0.229, 0.224, 0.225]

    def __init__(
        self,
        model: nn.Module,
        metadata: ModelMetadata,
        device: Optional[torch.device] = None,
        confidence_threshold: float = 0.7,
        cooldown_ms: int = 100,
    ):
        """
        Initialize the inference engine.

        Args:
            model: Loaded PyTorch model
            metadata: Model metadata
            device: Inference device (auto-detect if None)
            confidence_threshold: Minimum confidence for action
            cooldown_ms: Minimum ms between actions
        """
        self.model = model
        self.metadata = metadata
        self.device = device or self._detect_device()
        self.confidence_threshold = confidence_threshold
        self.cooldown_ms = cooldown_ms

        self.model.to(self.device)
        self.model.eval()

        # Setup preprocessing
        self.transform = self._build_transform()

        # Temporal buffer for LSTM models
        self.temporal_buffer: Optional[TemporalBuffer] = None
        if metadata.temporal_frames > 0:
            self.temporal_buffer = TemporalBuffer(metadata.temporal_frames)

        # Rate limiting
        self.last_action_time = 0.0
        self.action_count = 0

        # Safety
        self.emergency_stop = False

        logger.info(
            f"InferenceEngine initialized: {metadata.architecture}, "
            f"input={metadata.input_size}, temporal={metadata.temporal_frames}"
        )

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: Union[str, Path],
        confidence_threshold: float = 0.7,
        cooldown_ms: int = 100,
    ) -> "InferenceEngine":
        """
        Load an inference engine from a checkpoint.

        Automatically detects architecture and loads model.

        Args:
            checkpoint_path: Path to .pth checkpoint
            confidence_threshold: Minimum confidence for action
            cooldown_ms: Minimum ms between actions

        Returns:
            Configured InferenceEngine
        """
        checkpoint_path = Path(checkpoint_path)

        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

        # Load checkpoint
        device = cls._detect_device_static()
        checkpoint = torch.load(checkpoint_path, map_location=device)

        # Extract metadata
        metadata = cls._extract_metadata(checkpoint)

        # Build model
        model = cls._build_model(metadata)

        # Load weights
        if "model_state_dict" in checkpoint:
            model.load_state_dict(checkpoint["model_state_dict"])
        else:
            model.load_state_dict(checkpoint)

        return cls(
            model=model,
            metadata=metadata,
            device=device,
            confidence_threshold=confidence_threshold,
            cooldown_ms=cooldown_ms,
        )

    @staticmethod
    def _detect_device_static() -> torch.device:
        """Detect best available device (static version)."""
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    def _detect_device(self) -> torch.device:
        """Detect best available device."""
        return self._detect_device_static()

    @staticmethod
    def _extract_metadata(checkpoint: Dict) -> ModelMetadata:
        """Extract metadata from checkpoint."""
        # Try different metadata locations
        meta = checkpoint.get("metadata", checkpoint.get("model_metadata", {}))
        config = checkpoint.get("config", checkpoint.get("training_config", {}))

        # Architecture
        architecture = meta.get(
            "architecture",
            config.get(
                "architecture",
                config.get("model", {}).get("architecture", "efficientnet_lstm"),
            ),
        )

        # Input size
        input_size = meta.get("input_size", config.get("input_size", [224, 224]))
        if isinstance(input_size, list):
            input_size = tuple(input_size)

        # Classes
        num_classes = meta.get("num_classes", config.get("num_classes", 12))
        class_names = meta.get("class_names", [f"action_{i}" for i in range(num_classes)])

        # Temporal
        temporal_frames = meta.get(
            "temporal_frames",
            config.get("temporal_frames", config.get("input", {}).get("temporal_frames", 0)),
        )
        if "lstm" not in architecture.lower():
            temporal_frames = 0

        return ModelMetadata(
            architecture=architecture,
            input_size=input_size,
            num_classes=num_classes,
            class_names=class_names,
            temporal_frames=temporal_frames,
            normalize=meta.get("normalize", "imagenet"),
            pytorch_version=meta.get("pytorch_version", torch.__version__),
            extra=meta,
        )

    @staticmethod
    def _build_model(metadata: ModelMetadata) -> nn.Module:
        """Build model based on metadata."""
        # Import here to avoid circular imports
        import sys
        from pathlib import Path

        # Add src to path if needed
        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from bot_mmorpg.scripts.models_pytorch import create_model

        model = create_model(
            architecture=metadata.architecture,
            num_classes=metadata.num_classes,
            input_size=metadata.input_size,
            temporal_frames=metadata.temporal_frames,
            pretrained=False,  # We'll load weights separately
        )

        return model

    def _build_transform(self) -> transforms.Compose:
        """Build preprocessing transform."""
        transform_list = [
            transforms.Resize(self.metadata.input_size),
            transforms.ToTensor(),
        ]

        if self.metadata.normalize == "imagenet":
            transform_list.append(
                transforms.Normalize(mean=self.IMAGENET_MEAN, std=self.IMAGENET_STD)
            )
        elif self.metadata.normalize == "[-1,1]":
            transform_list.append(transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]))
        # [0,1] is already handled by ToTensor

        return transforms.Compose(transform_list)

    def predict(
        self,
        frame: Union[np.ndarray, Image.Image, torch.Tensor],
    ) -> Optional[InferenceResult]:
        """
        Predict action for a frame.

        Args:
            frame: Input frame (numpy array, PIL Image, or tensor)

        Returns:
            InferenceResult or None if:
            - Emergency stop is active
            - Cooldown not met
            - Temporal buffer not ready (for LSTM models)
        """
        # Safety check
        if self.emergency_stop:
            return None

        # Rate limiting
        current_time = time.time() * 1000  # Convert to ms
        if current_time - self.last_action_time < self.cooldown_ms:
            return None

        start_time = time.perf_counter()

        # Preprocess
        if isinstance(frame, np.ndarray):
            frame = Image.fromarray(frame)
        if isinstance(frame, Image.Image):
            frame = self.transform(frame)
        if not isinstance(frame, torch.Tensor):
            raise ValueError(f"Unsupported frame type: {type(frame)}")

        # Handle temporal models
        if self.temporal_buffer is not None:
            self.temporal_buffer.add(frame)

            if not self.temporal_buffer.is_ready():
                # Not enough frames yet
                return None

            # Get temporal sequence
            input_tensor = self.temporal_buffer.get_sequence()
            input_tensor = input_tensor.unsqueeze(0).to(self.device)  # Add batch dim
            temporal_context = self.metadata.temporal_frames
        else:
            input_tensor = frame.unsqueeze(0).to(self.device)
            temporal_context = 1

        # Inference
        with torch.no_grad():
            outputs = self.model(input_tensor)
            probabilities = F.softmax(outputs, dim=1)

        # Get prediction
        probs = probabilities[0].cpu().numpy()
        action_id = int(np.argmax(probs))
        confidence = float(probs[action_id])

        # Build probability dict
        all_probs = {self.metadata.class_names[i]: float(p) for i, p in enumerate(probs)}

        # Calculate inference time
        inference_time = (time.perf_counter() - start_time) * 1000

        # Update timing
        self.last_action_time = current_time
        self.action_count += 1

        return InferenceResult(
            action_id=action_id,
            action_name=self.metadata.class_names[action_id],
            confidence=confidence,
            all_probabilities=all_probs,
            temporal_context=temporal_context,
            inference_time_ms=inference_time,
        )

    def predict_batch(self, frames: List[Union[np.ndarray, Image.Image]]) -> List[InferenceResult]:
        """
        Batch prediction for multiple frames.

        Note: For temporal models, this processes frames sequentially.
        """
        results = []
        for frame in frames:
            result = self.predict(frame)
            if result:
                results.append(result)
        return results

    def should_execute(self, result: InferenceResult) -> bool:
        """Check if action should be executed based on confidence."""
        return result.confidence >= self.confidence_threshold

    def set_emergency_stop(self, stop: bool = True):
        """Set emergency stop state."""
        self.emergency_stop = stop
        if stop:
            logger.warning("Emergency stop activated!")
            if self.temporal_buffer:
                self.temporal_buffer.clear()

    def reset(self):
        """Reset engine state (clear buffers, counters)."""
        if self.temporal_buffer:
            self.temporal_buffer.clear()
        self.last_action_time = 0.0
        self.action_count = 0
        self.emergency_stop = False

    def get_stats(self) -> Dict[str, Any]:
        """Get inference statistics."""
        return {
            "model": self.metadata.architecture,
            "device": str(self.device),
            "actions_predicted": self.action_count,
            "temporal_buffer_size": len(self.temporal_buffer.buffer) if self.temporal_buffer else 0,
            "emergency_stop": self.emergency_stop,
            "confidence_threshold": self.confidence_threshold,
            "cooldown_ms": self.cooldown_ms,
        }


def load_inference_engine(
    model_path: Union[str, Path],
    confidence: float = 0.7,
    cooldown: int = 100,
) -> InferenceEngine:
    """
    Convenience function to load an inference engine.

    Args:
        model_path: Path to model checkpoint
        confidence: Confidence threshold
        cooldown: Action cooldown in ms

    Returns:
        Configured InferenceEngine
    """
    return InferenceEngine.from_checkpoint(
        model_path,
        confidence_threshold=confidence,
        cooldown_ms=cooldown,
    )
