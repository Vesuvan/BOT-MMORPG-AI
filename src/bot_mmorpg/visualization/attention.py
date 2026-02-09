"""
Attention Map Visualization

Generates attention/saliency maps to show what the model is focusing on.
Uses Grad-CAM for CNN-based models.
"""

import logging
from typing import Optional, Union

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy imports
_torch = None
_F = None


def _get_torch():
    global _torch, _F
    if _torch is None:
        import torch
        import torch.nn.functional as F

        _torch = torch
        _F = F
    return _torch, _F


class GradCAM:
    """
    Gradient-weighted Class Activation Mapping (Grad-CAM).

    Visualizes which parts of the input image are most important
    for the model's prediction.
    """

    def __init__(self, model, target_layer: Optional[str] = None):
        """
        Initialize Grad-CAM.

        Args:
            model: PyTorch model
            target_layer: Name of the target layer for visualization.
                         If None, tries to auto-detect the last conv layer.
        """
        torch, _ = _get_torch()

        self.model = model
        self.model.eval()

        # Find target layer
        self.target_layer = self._find_target_layer(target_layer)

        # Storage for gradients and activations
        self.gradients = None
        self.activations = None

        # Register hooks
        self._register_hooks()

    def _find_target_layer(self, layer_name: Optional[str]):
        """Find the target layer for Grad-CAM."""
        if layer_name:
            # Get layer by name
            for name, module in self.model.named_modules():
                if name == layer_name:
                    return module
            raise ValueError(f"Layer {layer_name} not found in model")

        # Auto-detect: find last Conv2d layer
        torch, _ = _get_torch()
        last_conv = None

        for module in self.model.modules():
            if isinstance(module, torch.nn.Conv2d):
                last_conv = module

        if last_conv is None:
            raise ValueError("No Conv2d layer found in model")

        return last_conv

    def _register_hooks(self):
        """Register forward and backward hooks."""

        def forward_hook(module, input, output):
            self.activations = output.detach()

        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0].detach()

        self.target_layer.register_forward_hook(forward_hook)
        self.target_layer.register_full_backward_hook(backward_hook)

    def generate(
        self,
        input_tensor,
        target_class: Optional[int] = None,
    ) -> np.ndarray:
        """
        Generate Grad-CAM heatmap.

        Args:
            input_tensor: Input tensor (B, C, H, W) or (C, H, W)
            target_class: Target class index. If None, uses predicted class.

        Returns:
            Heatmap as numpy array (H, W) with values in [0, 1]
        """
        torch, F = _get_torch()

        # Ensure batch dimension
        if input_tensor.dim() == 3:
            input_tensor = input_tensor.unsqueeze(0)

        # Enable gradients
        input_tensor.requires_grad_(True)

        # Forward pass
        output = self.model(input_tensor)

        # Get target class
        if target_class is None:
            target_class = output.argmax(dim=1).item()

        # Backward pass
        self.model.zero_grad()
        one_hot = torch.zeros_like(output)
        one_hot[0, target_class] = 1
        output.backward(gradient=one_hot, retain_graph=True)

        # Compute Grad-CAM
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = (weights * self.activations).sum(dim=1, keepdim=True)
        cam = F.relu(cam)

        # Normalize
        cam = cam - cam.min()
        cam = cam / (cam.max() + 1e-8)

        # Resize to input size
        cam = F.interpolate(
            cam,
            size=input_tensor.shape[2:],
            mode="bilinear",
            align_corners=False,
        )

        return cam[0, 0].cpu().numpy()


def generate_attention_map(
    model,
    image: Union[Image.Image, np.ndarray],
    target_class: Optional[int] = None,
    colormap: str = "jet",
    alpha: float = 0.5,
) -> Image.Image:
    """
    Generate an attention map overlay on the input image.

    Args:
        model: PyTorch model (or None for placeholder)
        image: Input image (PIL or numpy)
        target_class: Target class for Grad-CAM
        colormap: Matplotlib colormap name
        alpha: Overlay transparency

    Returns:
        PIL Image with attention overlay
    """
    # Convert to PIL if needed
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)

    # Ensure RGB
    if image.mode != "RGB":
        image = image.convert("RGB")

    # If no model, return a placeholder heatmap
    if model is None:
        return _generate_placeholder_heatmap(image, colormap, alpha)

    try:
        torch, _ = _get_torch()
        from torchvision import transforms

        # Preprocess image
        transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )

        input_tensor = transform(image)

        # Generate Grad-CAM
        gradcam = GradCAM(model)
        heatmap = gradcam.generate(input_tensor, target_class)

        # Apply colormap
        heatmap_colored = _apply_colormap(heatmap, colormap)

        # Resize heatmap to original image size
        heatmap_pil = Image.fromarray(heatmap_colored)
        heatmap_pil = heatmap_pil.resize(image.size, Image.BILINEAR)

        # Blend with original image
        result = Image.blend(image, heatmap_pil, alpha)

        return result

    except Exception as e:
        logger.warning(f"Grad-CAM failed: {e}, using placeholder")
        return _generate_placeholder_heatmap(image, colormap, alpha)


def _generate_placeholder_heatmap(
    image: Image.Image,
    colormap: str = "jet",
    alpha: float = 0.5,
) -> Image.Image:
    """Generate a placeholder heatmap (center-focused)."""
    width, height = image.size

    # Create center-focused gaussian
    y, x = np.ogrid[:height, :width]
    cx, cy = width // 2, height // 2
    sigma = min(width, height) // 4

    heatmap = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma**2))
    heatmap = (heatmap * 255).astype(np.uint8)

    # Apply colormap
    heatmap_colored = _apply_colormap(heatmap / 255.0, colormap)
    heatmap_pil = Image.fromarray(heatmap_colored)

    # Blend
    return Image.blend(image, heatmap_pil, alpha)


def _apply_colormap(heatmap: np.ndarray, colormap: str = "jet") -> np.ndarray:
    """Apply a colormap to a heatmap array."""
    try:
        import matplotlib.cm as cm

        cmap = cm.get_cmap(colormap)
        colored = cmap(heatmap)
        return (colored[:, :, :3] * 255).astype(np.uint8)
    except ImportError:
        # Fallback: simple red-yellow-green colormap
        heatmap = (heatmap * 255).astype(np.uint8)
        colored = np.zeros((*heatmap.shape, 3), dtype=np.uint8)
        colored[:, :, 0] = heatmap  # Red channel
        colored[:, :, 1] = 255 - heatmap  # Green channel (inverted)
        return colored
