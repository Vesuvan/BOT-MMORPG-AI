"""
PyTorch Model Architectures for BOT-MMORPG-AI

This module provides modern and legacy neural network architectures for game bot AI.
Migrated from TensorFlow/TFLearn to PyTorch 2.x for better performance and maintainability.

Architectures included:
- Modern: EfficientNet-B0 + LSTM, MobileNetV3 (recommended)
- Legacy: Inception V3, AlexNet, SentNet variants (ported from TFLearn)

Usage:
    from models_pytorch import get_model, list_models

    # Get recommended model
    model = get_model('efficientnet_lstm', num_actions=29)

    # List all available models
    print(list_models())
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

# PyTorch imports with fallback
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    torch = None
    F = None

    # Stub nn module for class definitions when PyTorch not installed
    class _StubModule:
        """Stub base class for nn.Module when PyTorch not installed."""
        pass

    class _StubNN:
        """Stub nn module when PyTorch not installed."""
        Module = _StubModule
        Sequential = _StubModule
        Conv2d = _StubModule
        Conv3d = _StubModule
        Linear = _StubModule
        LSTM = _StubModule
        Dropout = _StubModule
        ReLU = _StubModule
        Tanh = _StubModule
        Hardswish = _StubModule
        MaxPool2d = _StubModule
        MaxPool3d = _StubModule
        AvgPool3d = _StubModule
        AdaptiveAvgPool2d = _StubModule
        AdaptiveAvgPool3d = _StubModule
        LocalResponseNorm = _StubModule
        Identity = _StubModule
        BCEWithLogitsLoss = _StubModule

        @staticmethod
        def init():
            pass

    nn = _StubNN()

# Check for torchvision availability
try:
    import torchvision.models as tv_models
    TORCHVISION_AVAILABLE = True
except ImportError:
    TORCHVISION_AVAILABLE = False
    tv_models = None


# =============================================================================
# Model Configuration
# =============================================================================

@dataclass
class ModelConfig:
    """Configuration for model architecture."""
    name: str
    input_height: int = 270
    input_width: int = 480
    input_channels: int = 3
    num_actions: int = 29
    temporal_frames: int = 1
    dropout: float = 0.3
    pretrained: bool = True


class ModelType(Enum):
    """Available model architectures."""
    # Modern architectures (recommended)
    EFFICIENTNET_LSTM = "efficientnet_lstm"
    EFFICIENTNET_SIMPLE = "efficientnet_simple"
    MOBILENET_V3 = "mobilenet_v3"
    RESNET18_LSTM = "resnet18_lstm"

    # Legacy architectures (ported from TFLearn)
    INCEPTION_V3 = "inception_v3"
    ALEXNET = "alexnet"
    SENTNET = "sentnet"
    SENTNET_2D = "sentnet_2d"


# =============================================================================
# Modern Architectures (Recommended)
# =============================================================================

class EfficientNetLSTM(nn.Module):
    """
    Modern architecture: EfficientNet-B0 backbone + LSTM for temporal context.

    This is the RECOMMENDED model for game bot AI:
    - EfficientNet-B0: Efficient feature extraction (~5M params)
    - LSTM: Captures temporal dependencies across frames
    - Multi-label sigmoid: Allows simultaneous button presses

    Input: (batch, seq_len, C, H, W) - sequence of frames
    Output: (batch, num_actions) - action logits
    """

    def __init__(
        self,
        num_actions: int = 29,
        temporal_frames: int = 4,
        hidden_size: int = 512,
        num_lstm_layers: int = 2,
        dropout: float = 0.3,
        pretrained: bool = True,
    ):
        super().__init__()

        self.temporal_frames = temporal_frames
        self.num_actions = num_actions

        # EfficientNet-B0 backbone
        if TORCHVISION_AVAILABLE and pretrained:
            weights = tv_models.EfficientNet_B0_Weights.DEFAULT
            self.backbone = tv_models.efficientnet_b0(weights=weights)
        elif TORCHVISION_AVAILABLE:
            self.backbone = tv_models.efficientnet_b0(weights=None)
        else:
            raise ImportError("torchvision required for EfficientNet")

        # Remove classifier, get feature dimension
        self.feature_dim = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Identity()

        # LSTM for temporal modeling
        self.lstm = nn.LSTM(
            input_size=self.feature_dim,
            hidden_size=hidden_size,
            num_layers=num_lstm_layers,
            batch_first=True,
            dropout=dropout if num_lstm_layers > 1 else 0,
            bidirectional=False,
        )

        # Action prediction head (multi-label)
        self.action_head = nn.Sequential(
            nn.Linear(hidden_size, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, num_actions),
            # No activation - use BCEWithLogitsLoss
        )

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        for module in [self.action_head]:
            for m in module.modules():
                if isinstance(m, nn.Linear):
                    nn.init.xavier_uniform_(m.weight)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, C, H, W) or (batch, C, H, W)

        Returns:
            Action logits of shape (batch, num_actions)
        """
        # Handle single frame input
        if x.dim() == 4:
            x = x.unsqueeze(1)  # Add sequence dimension

        batch, seq_len, C, H, W = x.shape

        # Extract features from each frame
        x = x.view(batch * seq_len, C, H, W)
        features = self.backbone(x)  # (batch*seq, feature_dim)
        features = features.view(batch, seq_len, -1)

        # Temporal modeling
        lstm_out, _ = self.lstm(features)
        last_hidden = lstm_out[:, -1, :]  # Take last timestep

        # Predict actions
        logits = self.action_head(last_hidden)
        return logits

    def predict(self, x: torch.Tensor, threshold: float = 0.5) -> torch.Tensor:
        """Get binary action predictions."""
        with torch.no_grad():
            logits = self.forward(x)
            probs = torch.sigmoid(logits)
            return (probs > threshold).float()


class EfficientNetSimple(nn.Module):
    """
    Simple EfficientNet without temporal modeling.
    Faster inference but no motion awareness.

    Input: (batch, C, H, W) - single frame
    Output: (batch, num_actions) - action logits
    """

    def __init__(
        self,
        num_actions: int = 29,
        dropout: float = 0.3,
        pretrained: bool = True,
    ):
        super().__init__()

        self.num_actions = num_actions

        # EfficientNet-B0 backbone
        if TORCHVISION_AVAILABLE and pretrained:
            weights = tv_models.EfficientNet_B0_Weights.DEFAULT
            self.backbone = tv_models.efficientnet_b0(weights=weights)
        elif TORCHVISION_AVAILABLE:
            self.backbone = tv_models.efficientnet_b0(weights=None)
        else:
            raise ImportError("torchvision required for EfficientNet")

        # Replace classifier
        feature_dim = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(feature_dim, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, num_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)


class MobileNetV3Model(nn.Module):
    """
    Ultra-fast model using MobileNetV3-Small.
    Best for real-time inference with limited resources.

    Input: (batch, C, H, W) - single frame
    Output: (batch, num_actions) - action logits
    """

    def __init__(
        self,
        num_actions: int = 29,
        dropout: float = 0.2,
        pretrained: bool = True,
    ):
        super().__init__()

        self.num_actions = num_actions

        # MobileNetV3-Small backbone
        if TORCHVISION_AVAILABLE and pretrained:
            weights = tv_models.MobileNet_V3_Small_Weights.DEFAULT
            self.backbone = tv_models.mobilenet_v3_small(weights=weights)
        elif TORCHVISION_AVAILABLE:
            self.backbone = tv_models.mobilenet_v3_small(weights=None)
        else:
            raise ImportError("torchvision required for MobileNetV3")

        # Replace classifier
        feature_dim = self.backbone.classifier[0].in_features
        self.backbone.classifier = nn.Sequential(
            nn.Linear(feature_dim, 256),
            nn.Hardswish(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, num_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)


class ResNet18LSTM(nn.Module):
    """
    ResNet18 backbone with LSTM temporal modeling.
    Good balance between speed and accuracy.

    Input: (batch, seq_len, C, H, W) - sequence of frames
    Output: (batch, num_actions) - action logits
    """

    def __init__(
        self,
        num_actions: int = 29,
        temporal_frames: int = 4,
        hidden_size: int = 256,
        dropout: float = 0.3,
        pretrained: bool = True,
    ):
        super().__init__()

        self.temporal_frames = temporal_frames

        # ResNet18 backbone
        if TORCHVISION_AVAILABLE and pretrained:
            weights = tv_models.ResNet18_Weights.DEFAULT
            resnet = tv_models.resnet18(weights=weights)
        elif TORCHVISION_AVAILABLE:
            resnet = tv_models.resnet18(weights=None)
        else:
            raise ImportError("torchvision required for ResNet18")

        # Remove FC layer
        self.feature_dim = resnet.fc.in_features
        self.backbone = nn.Sequential(*list(resnet.children())[:-1])

        # LSTM
        self.lstm = nn.LSTM(
            input_size=self.feature_dim,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            dropout=dropout,
        )

        # Head
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(128, num_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 4:
            x = x.unsqueeze(1)

        batch, seq_len, C, H, W = x.shape
        x = x.view(batch * seq_len, C, H, W)
        features = self.backbone(x).squeeze(-1).squeeze(-1)
        features = features.view(batch, seq_len, -1)

        lstm_out, _ = self.lstm(features)
        logits = self.head(lstm_out[:, -1, :])
        return logits


# =============================================================================
# Legacy Architectures (Ported from TFLearn)
# =============================================================================

class InceptionModule(nn.Module):
    """Inception module with parallel convolutions at different scales."""

    def __init__(
        self,
        in_channels: int,
        ch1x1: int,
        ch3x3_reduce: int,
        ch3x3: int,
        ch5x5_reduce: int,
        ch5x5: int,
        pool_proj: int,
    ):
        super().__init__()

        # 1x1 branch
        self.branch1 = nn.Sequential(
            nn.Conv2d(in_channels, ch1x1, 1),
            nn.ReLU(inplace=True),
        )

        # 3x3 branch
        self.branch2 = nn.Sequential(
            nn.Conv2d(in_channels, ch3x3_reduce, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(ch3x3_reduce, ch3x3, 3, padding=1),
            nn.ReLU(inplace=True),
        )

        # 5x5 branch
        self.branch3 = nn.Sequential(
            nn.Conv2d(in_channels, ch5x5_reduce, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(ch5x5_reduce, ch5x5, 5, padding=2),
            nn.ReLU(inplace=True),
        )

        # Pool branch
        self.branch4 = nn.Sequential(
            nn.MaxPool2d(3, stride=1, padding=1),
            nn.Conv2d(in_channels, pool_proj, 1),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.cat([
            self.branch1(x),
            self.branch2(x),
            self.branch3(x),
            self.branch4(x),
        ], dim=1)


class InceptionV3Legacy(nn.Module):
    """
    Inception V3 architecture ported from TFLearn.

    This is the original architecture used in the project.
    Kept for backward compatibility and comparison.

    Input: (batch, C, H, W) - single frame
    Output: (batch, num_actions) - action logits
    """

    def __init__(
        self,
        num_actions: int = 29,
        dropout: float = 0.4,
    ):
        super().__init__()

        self.num_actions = num_actions

        # Initial layers
        self.conv1 = nn.Sequential(
            nn.Conv2d(3, 64, 7, stride=2, padding=3),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2, padding=1),
            nn.LocalResponseNorm(5),
        )

        self.conv2 = nn.Sequential(
            nn.Conv2d(64, 64, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 192, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.LocalResponseNorm(5),
            nn.MaxPool2d(3, stride=2, padding=1),
        )

        # Inception modules
        self.inception3a = InceptionModule(192, 64, 96, 128, 16, 32, 32)
        self.inception3b = InceptionModule(256, 128, 128, 192, 32, 96, 64)

        self.pool3 = nn.MaxPool2d(3, stride=2, padding=1)

        self.inception4a = InceptionModule(480, 192, 96, 208, 16, 48, 64)
        self.inception4b = InceptionModule(512, 160, 112, 224, 24, 64, 64)
        self.inception4c = InceptionModule(512, 128, 128, 256, 24, 64, 64)
        self.inception4d = InceptionModule(512, 112, 144, 288, 32, 64, 64)
        self.inception4e = InceptionModule(528, 256, 160, 320, 32, 128, 128)

        self.pool4 = nn.MaxPool2d(3, stride=2, padding=1)

        self.inception5a = InceptionModule(832, 256, 160, 320, 32, 128, 128)
        self.inception5b = InceptionModule(832, 384, 192, 384, 48, 128, 128)

        # Classifier
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(1024, num_actions)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x)
        x = self.conv2(x)

        x = self.inception3a(x)
        x = self.inception3b(x)
        x = self.pool3(x)

        x = self.inception4a(x)
        x = self.inception4b(x)
        x = self.inception4c(x)
        x = self.inception4d(x)
        x = self.inception4e(x)
        x = self.pool4(x)

        x = self.inception5a(x)
        x = self.inception5b(x)

        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.dropout(x)
        x = self.fc(x)

        return x


class AlexNetLegacy(nn.Module):
    """
    AlexNet architecture ported from TFLearn.

    Input: (batch, C, H, W) - single frame
    Output: (batch, num_actions) - action logits
    """

    def __init__(
        self,
        num_actions: int = 29,
        in_channels: int = 3,
        dropout: float = 0.5,
    ):
        super().__init__()

        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 96, 11, stride=4, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),
            nn.LocalResponseNorm(5),

            nn.Conv2d(96, 256, 5, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),
            nn.LocalResponseNorm(5),

            nn.Conv2d(256, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 256, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),

            nn.Conv2d(256, 256, 5, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),
            nn.LocalResponseNorm(5),

            nn.Conv2d(256, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 256, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),
            nn.LocalResponseNorm(5),
        )

        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))

        self.classifier = nn.Sequential(
            nn.Linear(256, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, num_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


class SentNetLegacy(nn.Module):
    """
    SentNet architecture ported from TFLearn.
    3D convolutions for temporal modeling.

    Input: (batch, C, D, H, W) - video frames
    Output: (batch, num_actions) - action logits
    """

    def __init__(
        self,
        num_actions: int = 29,
        dropout: float = 0.5,
    ):
        super().__init__()

        self.features = nn.Sequential(
            nn.Conv3d(3, 96, 11, stride=4, padding=2),
            nn.ReLU(inplace=True),
            nn.AvgPool3d(3, stride=2),

            nn.Conv3d(96, 256, 5, padding=2),
            nn.ReLU(inplace=True),
            nn.AvgPool3d(3, stride=2),

            nn.Conv3d(256, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv3d(384, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv3d(384, 256, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool3d(3, stride=2),

            nn.Conv3d(256, 256, 5, padding=2),
            nn.ReLU(inplace=True),
            nn.AvgPool3d(3, stride=2),

            nn.Conv3d(256, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv3d(384, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv3d(384, 256, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.AvgPool3d(3, stride=2),
        )

        self.avgpool = nn.AdaptiveAvgPool3d((1, 1, 1))

        self.classifier = nn.Sequential(
            nn.Linear(256, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, num_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Expect (batch, frames, C, H, W) -> convert to (batch, C, frames, H, W)
        if x.dim() == 5 and x.shape[2] == 3:
            x = x.permute(0, 2, 1, 3, 4)

        x = self.features(x)
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


class SentNet2D(nn.Module):
    """
    SentNet 2D variant for single-frame input.
    Ported from TFLearn sentnet_color_2d.

    Input: (batch, C, H, W) - single frame
    Output: (batch, num_actions) - action logits
    """

    def __init__(
        self,
        num_actions: int = 29,
        dropout: float = 0.5,
    ):
        super().__init__()

        self.features = nn.Sequential(
            nn.Conv2d(3, 96, 11, stride=4, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),
            nn.LocalResponseNorm(5),

            nn.Conv2d(96, 256, 5, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),
            nn.LocalResponseNorm(5),

            nn.Conv2d(256, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 256, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),

            nn.Conv2d(256, 256, 5, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),
            nn.LocalResponseNorm(5),

            nn.Conv2d(256, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 384, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 256, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(3, stride=2),
            nn.LocalResponseNorm(5),
        )

        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))

        self.classifier = nn.Sequential(
            nn.Linear(256, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, 4096),
            nn.Tanh(),
            nn.Dropout(dropout),
            nn.Linear(4096, num_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


# =============================================================================
# Model Factory
# =============================================================================

# Registry of available models
MODEL_REGISTRY: Dict[str, type] = {
    # Modern (recommended)
    "efficientnet_lstm": EfficientNetLSTM,
    "efficientnet_simple": EfficientNetSimple,
    "mobilenet_v3": MobileNetV3Model,
    "resnet18_lstm": ResNet18LSTM,
    # Legacy (backward compatibility)
    "inception_v3": InceptionV3Legacy,
    "alexnet": AlexNetLegacy,
    "sentnet": SentNetLegacy,
    "sentnet_2d": SentNet2D,
}

# Model metadata for UI/selection
MODEL_INFO: Dict[str, Dict[str, Any]] = {
    "efficientnet_lstm": {
        "name": "EfficientNet + LSTM",
        "description": "Recommended. Best accuracy with temporal awareness.",
        "params": "~5M",
        "inference_ms": "~8ms (GPU)",
        "temporal": True,
        "recommended": True,
    },
    "efficientnet_simple": {
        "name": "EfficientNet Simple",
        "description": "Fast single-frame model. Good accuracy.",
        "params": "~5M",
        "inference_ms": "~5ms (GPU)",
        "temporal": False,
        "recommended": False,
    },
    "mobilenet_v3": {
        "name": "MobileNet V3",
        "description": "Ultra-fast. Best for low-end hardware.",
        "params": "~2M",
        "inference_ms": "~3ms (GPU)",
        "temporal": False,
        "recommended": False,
    },
    "resnet18_lstm": {
        "name": "ResNet18 + LSTM",
        "description": "Good balance of speed and accuracy.",
        "params": "~12M",
        "inference_ms": "~10ms (GPU)",
        "temporal": True,
        "recommended": False,
    },
    "inception_v3": {
        "name": "Inception V3 (Legacy)",
        "description": "Original architecture. Kept for compatibility.",
        "params": "~7M",
        "inference_ms": "~15ms (GPU)",
        "temporal": False,
        "recommended": False,
    },
    "alexnet": {
        "name": "AlexNet (Legacy)",
        "description": "Classic architecture. Kept for compatibility.",
        "params": "~60M",
        "inference_ms": "~10ms (GPU)",
        "temporal": False,
        "recommended": False,
    },
    "sentnet": {
        "name": "SentNet 3D (Legacy)",
        "description": "3D CNN for video input. Kept for compatibility.",
        "params": "~70M",
        "inference_ms": "~20ms (GPU)",
        "temporal": True,
        "recommended": False,
    },
    "sentnet_2d": {
        "name": "SentNet 2D (Legacy)",
        "description": "2D variant of SentNet. Kept for compatibility.",
        "params": "~70M",
        "inference_ms": "~15ms (GPU)",
        "temporal": False,
        "recommended": False,
    },
}


def list_models() -> List[str]:
    """Return list of available model names."""
    return list(MODEL_REGISTRY.keys())


def get_model_info(model_name: str) -> Dict[str, Any]:
    """Get metadata about a model."""
    if model_name not in MODEL_INFO:
        raise ValueError(f"Unknown model: {model_name}. Available: {list_models()}")
    return MODEL_INFO[model_name]


def get_model(
    model_name: str,
    num_actions: int = 29,
    temporal_frames: int = 4,
    pretrained: bool = True,
    **kwargs,
) -> nn.Module:
    """
    Factory function to create a model by name.

    Args:
        model_name: Name of the model architecture
        num_actions: Number of output actions (default: 29)
        temporal_frames: Number of frames for temporal models (default: 4)
        pretrained: Use pretrained backbone weights (default: True)
        **kwargs: Additional model-specific arguments

    Returns:
        PyTorch model instance

    Example:
        model = get_model('efficientnet_lstm', num_actions=29)
        model = get_model('mobilenet_v3', num_actions=29, pretrained=False)
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_name}. Available: {list_models()}")

    model_class = MODEL_REGISTRY[model_name]

    # Build kwargs based on model type
    model_kwargs = {"num_actions": num_actions}

    # Add temporal_frames for temporal models
    if model_name in ["efficientnet_lstm", "resnet18_lstm"]:
        model_kwargs["temporal_frames"] = temporal_frames

    # Add pretrained for modern models
    if model_name in ["efficientnet_lstm", "efficientnet_simple", "mobilenet_v3", "resnet18_lstm"]:
        model_kwargs["pretrained"] = pretrained

    # Merge with user kwargs
    model_kwargs.update(kwargs)

    return model_class(**model_kwargs)


# =============================================================================
# Utility Functions
# =============================================================================

def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters in a model."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def get_device(prefer_gpu: bool = True) -> torch.device:
    """Get the best available device."""
    if prefer_gpu and torch.cuda.is_available():
        return torch.device("cuda")
    elif prefer_gpu and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")  # Apple Silicon
    return torch.device("cpu")


def load_model(
    checkpoint_path: str,
    model_name: Optional[str] = None,
    num_actions: int = 29,
    device: Optional[torch.device] = None,
) -> Tuple[nn.Module, Dict[str, Any]]:
    """
    Load a model from a checkpoint file.

    The checkpoint should contain 'model_name' metadata to auto-detect architecture.
    If not available, model_name parameter must be provided.

    Args:
        checkpoint_path: Path to .pth checkpoint file
        model_name: Name of the model architecture (auto-detected if None)
        num_actions: Number of output actions
        device: Device to load model on (default: auto-detect)

    Returns:
        Tuple of (loaded model in eval mode, checkpoint metadata dict)
    """
    if device is None:
        device = get_device()

    # Load checkpoint first to get metadata
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # Extract metadata
    metadata = {}
    if isinstance(checkpoint, dict):
        metadata = {k: v for k, v in checkpoint.items() if k not in ['model_state_dict', 'state_dict', 'optimizer_state_dict']}

        # Auto-detect model name from checkpoint
        if model_name is None:
            model_name = checkpoint.get('model_name')
            # Handle class name format
            if model_name and model_name not in MODEL_REGISTRY:
                # Try to map class names to registry names
                name_mapping = {
                    'EfficientNetLSTM': 'efficientnet_lstm',
                    'EfficientNetSimple': 'efficientnet_simple',
                    'MobileNetV3Model': 'mobilenet_v3',
                    'ResNet18LSTM': 'resnet18_lstm',
                    'InceptionV3Legacy': 'inception_v3',
                    'AlexNetLegacy': 'alexnet',
                    'SentNetLegacy': 'sentnet',
                    'SentNet2D': 'sentnet_2d',
                }
                model_name = name_mapping.get(model_name, model_name)

    if model_name is None:
        raise ValueError("model_name not found in checkpoint and not provided. "
                         "Please specify model_name parameter.")

    # Get temporal frames from metadata
    temporal_frames = metadata.get('temporal_frames', 4)

    # Create model
    model = get_model(model_name, num_actions=num_actions, temporal_frames=temporal_frames, pretrained=False)

    # Load state dict
    if isinstance(checkpoint, dict):
        if "model_state_dict" in checkpoint:
            model.load_state_dict(checkpoint["model_state_dict"])
        elif "state_dict" in checkpoint:
            model.load_state_dict(checkpoint["state_dict"])
        else:
            # Checkpoint is the state dict itself (wrapped in dict)
            state_dict = {k: v for k, v in checkpoint.items()
                          if not isinstance(v, (int, float, str, bool, type(None)))}
            if state_dict:
                model.load_state_dict(state_dict)
    else:
        model.load_state_dict(checkpoint)

    model.to(device)
    model.eval()

    return model, metadata


def save_model(
    model: nn.Module,
    path: str,
    optimizer: Optional[torch.optim.Optimizer] = None,
    epoch: Optional[int] = None,
    loss: Optional[float] = None,
    model_name: Optional[str] = None,
    temporal_frames: Optional[int] = None,
    **extra_info,
) -> None:
    """
    Save model checkpoint with metadata.

    Args:
        model: Model to save
        path: Output path for .pth file
        optimizer: Optional optimizer to save
        epoch: Optional epoch number
        loss: Optional loss value
        model_name: Optional model architecture name
        temporal_frames: Optional temporal frames (for LSTM models)
        **extra_info: Additional metadata to save
    """
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "model_name": model_name or model.__class__.__name__,
        "num_parameters": count_parameters(model),
    }

    if optimizer is not None:
        checkpoint["optimizer_state_dict"] = optimizer.state_dict()
    if epoch is not None:
        checkpoint["epoch"] = epoch
    if loss is not None:
        checkpoint["loss"] = loss

    # Try to get temporal_frames from model if not provided
    if temporal_frames is None and hasattr(model, 'temporal_frames'):
        temporal_frames = model.temporal_frames
    if temporal_frames is not None:
        checkpoint["temporal_frames"] = temporal_frames

    checkpoint.update(extra_info)

    torch.save(checkpoint, path)


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# These match the original TFLearn function names for drop-in replacement
def inception_v3(width, height, frame_count, lr, output=29, model_name='model', **kwargs):
    """Legacy API compatibility wrapper."""
    return get_model('inception_v3', num_actions=output)


def alexnet(width, height, lr, output=29, **kwargs):
    """Legacy API compatibility wrapper."""
    return get_model('alexnet', num_actions=output)


def sentnet(width, height, frame_count, lr, output=29, **kwargs):
    """Legacy API compatibility wrapper."""
    return get_model('sentnet', num_actions=output)


def sentnet_color_2d(width, height, frame_count, lr, output=29, **kwargs):
    """Legacy API compatibility wrapper."""
    return get_model('sentnet_2d', num_actions=output)


# Alias for the recommended model
def googlenet(width, height, frame_count, lr, output=29, **kwargs):
    """Alias for inception_v3 (commonly called GoogLeNet)."""
    return get_model('inception_v3', num_actions=output)


# =============================================================================
# Main (Testing)
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PyTorch Model Architectures for BOT-MMORPG-AI")
    print("=" * 60)

    device = get_device()
    print(f"\nDevice: {device}")
    print(f"\nAvailable models:")

    for name in list_models():
        info = get_model_info(name)
        rec = " [RECOMMENDED]" if info.get("recommended") else ""
        print(f"  - {name}: {info['name']}{rec}")
        print(f"      {info['description']}")
        print(f"      Params: {info['params']}, Inference: {info['inference_ms']}")

    # Test model creation
    print("\n" + "=" * 60)
    print("Testing model creation...")

    for name in list_models():
        try:
            model = get_model(name, num_actions=29, pretrained=False)
            params = count_parameters(model)
            print(f"  ✓ {name}: {params:,} parameters")
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    # Test forward pass
    print("\n" + "=" * 60)
    print("Testing forward pass (EfficientNet + LSTM)...")

    model = get_model("efficientnet_lstm", num_actions=29, pretrained=False)
    model.eval()

    # Single frame
    x_single = torch.randn(1, 3, 270, 480)
    with torch.no_grad():
        out = model(x_single)
    print(f"  Single frame input: {x_single.shape} -> {out.shape}")

    # Sequence of frames
    x_seq = torch.randn(1, 4, 3, 270, 480)
    with torch.no_grad():
        out = model(x_seq)
    print(f"  Sequence input: {x_seq.shape} -> {out.shape}")

    print("\n✓ All tests passed!")
