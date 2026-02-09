"""
Prediction Overlays

Real-time visualization overlays for inference results.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# Color palette for actions (gaming-friendly colors)
ACTION_COLORS = {
    "attack": (255, 87, 87),  # Red
    "dodge": (87, 166, 255),  # Blue
    "skill": (255, 193, 87),  # Orange
    "move": (87, 255, 166),  # Green
    "idle": (180, 180, 180),  # Gray
    "default": (255, 255, 255),  # White
}


def get_action_color(action_name: str) -> Tuple[int, int, int]:
    """Get color for an action type."""
    action_lower = action_name.lower()

    for key, color in ACTION_COLORS.items():
        if key in action_lower:
            return color

    return ACTION_COLORS["default"]


def draw_confidence_bars(
    image: Image.Image,
    predictions: Dict[str, float],
    position: str = "right",
    bar_width: int = 150,
    bar_height: int = 20,
    spacing: int = 5,
    max_items: int = 5,
    font_size: int = 14,
) -> Image.Image:
    """
    Draw confidence bars on the image.

    Args:
        image: Input image
        predictions: Dict of {action_name: confidence}
        position: Bar position ("left", "right", "bottom")
        bar_width: Width of each bar in pixels
        bar_height: Height of each bar
        spacing: Spacing between bars
        max_items: Maximum number of bars to show
        font_size: Font size for labels

    Returns:
        Image with confidence bars overlay
    """
    # Make a copy
    result = image.copy()
    draw = ImageDraw.Draw(result)

    # Sort by confidence
    sorted_preds = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
    sorted_preds = sorted_preds[:max_items]

    # Try to load font
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size
        )
    except (IOError, OSError):
        font = ImageFont.load_default()

    # Calculate position
    img_width, img_height = result.size
    padding = 10
    total_height = len(sorted_preds) * (bar_height + spacing)

    if position == "right":
        x_start = img_width - bar_width - padding - 80  # Space for labels
        y_start = padding
    elif position == "left":
        x_start = padding + 80
        y_start = padding
    else:  # bottom
        x_start = (img_width - bar_width) // 2
        y_start = img_height - total_height - padding

    # Draw semi-transparent background
    bg_left = x_start - 85
    bg_right = x_start + bar_width + 5
    bg_top = y_start - 5
    bg_bottom = y_start + total_height + 5

    # Create overlay for transparency
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [bg_left, bg_top, bg_right, bg_bottom],
        fill=(0, 0, 0, 180),
    )
    result = Image.alpha_composite(result.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(result)

    # Draw bars
    for i, (action, confidence) in enumerate(sorted_preds):
        y = y_start + i * (bar_height + spacing)
        color = get_action_color(action)

        # Background bar
        draw.rectangle(
            [x_start, y, x_start + bar_width, y + bar_height],
            fill=(50, 50, 50),
            outline=(100, 100, 100),
        )

        # Confidence bar
        filled_width = int(bar_width * confidence)
        if filled_width > 0:
            draw.rectangle(
                [x_start, y, x_start + filled_width, y + bar_height],
                fill=color,
            )

        # Label
        label = f"{action[:10]}"
        draw.text((x_start - 80, y + 2), label, fill=(255, 255, 255), font=font)

        # Percentage
        pct_text = f"{confidence:.0%}"
        draw.text(
            (x_start + bar_width + 5, y + 2),
            pct_text,
            fill=(255, 255, 255),
            font=font,
        )

    return result.convert("RGB")


def draw_focus_regions(
    image: Image.Image,
    regions: List[Dict[str, Any]],
    line_width: int = 2,
) -> Image.Image:
    """
    Draw focus region boxes on the image.

    Args:
        image: Input image
        regions: List of dicts with x, y, w, h, and optional label/confidence
        line_width: Width of bounding box lines

    Returns:
        Image with focus regions drawn
    """
    result = image.copy()
    draw = ImageDraw.Draw(result)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except (IOError, OSError):
        font = ImageFont.load_default()

    for region in regions:
        x, y = region["x"], region["y"]
        w, h = region["w"], region["h"]
        label = region.get("label", "")
        confidence = region.get("confidence", 1.0)

        # Color based on confidence
        if confidence > 0.8:
            color = (0, 255, 0)  # Green
        elif confidence > 0.5:
            color = (255, 255, 0)  # Yellow
        else:
            color = (255, 0, 0)  # Red

        # Draw box
        draw.rectangle(
            [x, y, x + w, y + h],
            outline=color,
            width=line_width,
        )

        # Draw label if present
        if label:
            label_text = f"{label} {confidence:.0%}"
            # Background for text
            bbox = draw.textbbox((x, y - 18), label_text, font=font)
            draw.rectangle(bbox, fill=(0, 0, 0, 180))
            draw.text((x, y - 18), label_text, fill=color, font=font)

    return result


def draw_action_indicator(
    image: Image.Image,
    action: str,
    confidence: float,
    position: str = "top-center",
    size: int = 60,
) -> Image.Image:
    """
    Draw a large action indicator on the image.

    Args:
        image: Input image
        action: Action name
        confidence: Confidence level (0-1)
        position: Indicator position
        size: Size of the indicator

    Returns:
        Image with action indicator
    """
    result = image.copy()
    draw = ImageDraw.Draw(result)
    img_width, img_height = result.size

    # Get position
    if position == "top-center":
        cx = img_width // 2
        cy = size + 20
    elif position == "bottom-center":
        cx = img_width // 2
        cy = img_height - size - 20
    else:
        cx = img_width // 2
        cy = size + 20

    color = get_action_color(action)

    # Draw circular indicator
    draw.ellipse(
        [cx - size, cy - size, cx + size, cy + size],
        fill=(*color, 200),
        outline=(255, 255, 255),
        width=3,
    )

    # Draw action text
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24
        )
        small_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16
        )
    except (IOError, OSError):
        font = ImageFont.load_default()
        small_font = font

    # Action name
    action_short = action[:8].upper()
    bbox = draw.textbbox((0, 0), action_short, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(
        (cx - text_width // 2, cy - 15),
        action_short,
        fill=(255, 255, 255),
        font=font,
    )

    # Confidence
    conf_text = f"{confidence:.0%}"
    bbox = draw.textbbox((0, 0), conf_text, font=small_font)
    text_width = bbox[2] - bbox[0]
    draw.text(
        (cx - text_width // 2, cy + 15),
        conf_text,
        fill=(255, 255, 255),
        font=small_font,
    )

    return result


def generate_prediction_overlay(
    image: Union[Image.Image, np.ndarray],
    prediction: Optional[Any] = None,
    show_bars: bool = True,
    show_indicator: bool = True,
    show_regions: bool = False,
) -> Image.Image:
    """
    Generate a complete prediction overlay.

    Args:
        image: Input image
        prediction: InferenceResult or None
        show_bars: Show confidence bars
        show_indicator: Show main action indicator
        show_regions: Show focus regions (if available)

    Returns:
        Image with all overlays
    """
    # Convert to PIL if needed
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)

    # Ensure RGB
    if image.mode != "RGB":
        image = image.convert("RGB")

    result = image.copy()

    if prediction is None:
        # No prediction - return original with "WAITING" indicator
        draw = ImageDraw.Draw(result)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20
            )
        except (IOError, OSError):
            font = ImageFont.load_default()

        text = "Waiting for prediction..."
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((result.width - text_width) // 2, 10),
            text,
            fill=(255, 255, 0),
            font=font,
        )
        return result

    # Draw confidence bars
    if show_bars and hasattr(prediction, "all_probabilities"):
        result = draw_confidence_bars(result, prediction.all_probabilities)

    # Draw action indicator
    if show_indicator and hasattr(prediction, "action_name"):
        result = draw_action_indicator(
            result,
            prediction.action_name,
            prediction.confidence,
        )

    return result


def create_training_visualization(
    input_frame: Image.Image,
    attention_map: Optional[Image.Image],
    predictions: Dict[str, float],
    ground_truth: Optional[str] = None,
    epoch: int = 0,
    loss: float = 0.0,
) -> Image.Image:
    """
    Create a comprehensive training visualization.

    Combines input frame, attention map, predictions, and metrics
    into a single visualization panel.

    Args:
        input_frame: The input image
        attention_map: Attention/saliency map overlay
        predictions: Model predictions
        ground_truth: Actual label (if available)
        epoch: Current epoch
        loss: Current loss

    Returns:
        Combined visualization image
    """
    # Target size for each panel
    panel_size = (320, 240)

    # Resize input and attention
    input_resized = input_frame.resize(panel_size, Image.LANCZOS)

    if attention_map:
        attention_resized = attention_map.resize(panel_size, Image.LANCZOS)
    else:
        attention_resized = Image.new("RGB", panel_size, (50, 50, 50))

    # Create predictions panel
    pred_panel = Image.new("RGB", panel_size, (30, 30, 30))
    pred_panel = draw_confidence_bars(
        pred_panel,
        predictions,
        position="left",
        bar_width=200,
    )

    # Create metrics panel
    metrics_panel = Image.new("RGB", panel_size, (30, 30, 30))
    draw = ImageDraw.Draw(metrics_panel)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        title_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20
        )
    except (IOError, OSError):
        font = ImageFont.load_default()
        title_font = font

    draw.text((10, 10), "Training Metrics", fill=(255, 255, 255), font=title_font)
    draw.text((10, 50), f"Epoch: {epoch}", fill=(200, 200, 200), font=font)
    draw.text((10, 80), f"Loss: {loss:.4f}", fill=(200, 200, 200), font=font)

    if ground_truth:
        draw.text(
            (10, 120), f"Ground Truth: {ground_truth}", fill=(100, 255, 100), font=font
        )

    # Combine into 2x2 grid
    combined = Image.new("RGB", (panel_size[0] * 2, panel_size[1] * 2))
    combined.paste(input_resized, (0, 0))
    combined.paste(attention_resized, (panel_size[0], 0))
    combined.paste(pred_panel, (0, panel_size[1]))
    combined.paste(metrics_panel, (panel_size[0], panel_size[1]))

    return combined
