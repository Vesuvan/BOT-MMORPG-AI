"""
Game Resolution Presets for BOT-MMORPG-AI

This module defines optimal capture resolutions for different MMORPG games.
The neural networks can work with various resolutions, but performance varies.

Resolution Guidelines:
- MINIMUM (Best Performance): 480x270 - Fastest training/inference, recommended default
- LOW (Good Performance): 640x360 - Good balance of speed and detail
- MEDIUM (Moderate): 960x540 - More detail, slower training
- HD (Experimental): 1280x720 - Maximum supported, NOT recommended for training
- 4K: NOT SUPPORTED (future hyperresolution mapping feature)

The default resolution is chosen based on:
1. Game minimum UI requirements (text readability)
2. Neural network efficiency
3. Dataset size considerations
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from enum import Enum


class ResolutionTier(Enum):
    """Resolution quality tiers."""

    MINIMUM = "minimum"  # 480x270 - Best performance, recommended
    LOW = "low"  # 640x360 - Good performance
    MEDIUM = "medium"  # 960x540 - Moderate performance
    HD = "hd"  # 1280x720 - Experimental, not recommended
    NATIVE = "native"  # Full screen capture


@dataclass
class Resolution:
    """Screen resolution configuration."""

    width: int
    height: int
    name: str
    recommended: bool = False
    experimental: bool = False
    description: str = ""

    @property
    def aspect_ratio(self) -> str:
        """Calculate aspect ratio string."""
        from math import gcd

        divisor = gcd(self.width, self.height)
        return f"{self.width // divisor}:{self.height // divisor}"

    @property
    def pixel_count(self) -> int:
        """Total pixels for performance estimation."""
        return self.width * self.height

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"


@dataclass
class GameResolutionConfig:
    """Resolution configuration for a specific game."""

    game_id: str
    game_name: str
    min_resolution: Resolution
    recommended_resolution: Resolution
    max_resolution: Resolution
    supported_resolutions: List[Resolution]
    notes: str = ""
    min_ui_width: int = 480  # Minimum width for readable UI


# =============================================================================
# Standard Resolution Presets
# =============================================================================

RESOLUTION_480P = Resolution(
    width=480,
    height=270,
    name="480x270 (NN Default)",
    recommended=True,
    description="Best performance, fastest training. Default for neural networks.",
)

RESOLUTION_640P = Resolution(
    width=640,
    height=360,
    name="640x360 (Low)",
    recommended=False,
    description="Good balance of speed and detail.",
)

RESOLUTION_960P = Resolution(
    width=960,
    height=540,
    name="960x540 (Medium)",
    recommended=False,
    description="More detail, slower training. Good for complex UIs.",
)

RESOLUTION_720P = Resolution(
    width=1280,
    height=720,
    name="1280x720 (HD)",
    recommended=False,
    experimental=True,
    description="EXPERIMENTAL: Maximum supported. Large datasets, slow training.",
)

RESOLUTION_NATIVE = Resolution(
    width=0,
    height=0,  # Determined at runtime
    name="Native (Full Screen)",
    recommended=False,
    experimental=True,
    description="EXPERIMENTAL: Uses full screen resolution. Not recommended.",
)

# Standard resolutions list (16:9 aspect ratio)
STANDARD_RESOLUTIONS = [
    RESOLUTION_480P,
    RESOLUTION_640P,
    RESOLUTION_960P,
    RESOLUTION_720P,
]


# =============================================================================
# Game-Specific Configurations
# =============================================================================

# Analysis of MMORPG minimum resolutions:
# - Most MMORPGs are designed for 1280x720 minimum
# - UI elements typically scale down to ~640x360 readable
# - Bot AI needs to see: minimap, HP/MP bars, skills, inventory indicators
# - For 16:9 games, 480x270 captures enough detail for gameplay patterns

GAME_CONFIGS: Dict[str, GameResolutionConfig] = {
    # =========================================================================
    # Popular MMORPGs - Resolution Analysis
    # =========================================================================
    "genshin_impact": GameResolutionConfig(
        game_id="genshin_impact",
        game_name="Genshin Impact",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_480P,
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=640,
        notes="Mobile-optimized UI scales well. 480x270 captures all essential elements.",
    ),
    "world_of_warcraft": GameResolutionConfig(
        game_id="world_of_warcraft",
        game_name="World of Warcraft",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_640P,  # WoW has detailed UI
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=800,
        notes="Complex UI with many addons. 640x360 recommended for addon text.",
    ),
    "final_fantasy_xiv": GameResolutionConfig(
        game_id="final_fantasy_xiv",
        game_name="Final Fantasy XIV",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_640P,  # FFXIV has detailed hotbars
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=800,
        notes="Detailed HUD with many skills. 640x360 for better hotbar visibility.",
    ),
    "guild_wars_2": GameResolutionConfig(
        game_id="guild_wars_2",
        game_name="Guild Wars 2",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_480P,
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=640,
        notes="Clean UI design. 480x270 sufficient for core gameplay.",
    ),
    "lost_ark": GameResolutionConfig(
        game_id="lost_ark",
        game_name="Lost Ark",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_640P,  # Complex skill system
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=720,
        notes="Many skill indicators. 640x360 recommended for combat clarity.",
    ),
    "elder_scrolls_online": GameResolutionConfig(
        game_id="elder_scrolls_online",
        game_name="Elder Scrolls Online",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_480P,
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=640,
        notes="Minimal UI design. 480x270 works well for action combat.",
    ),
    "black_desert_online": GameResolutionConfig(
        game_id="black_desert_online",
        game_name="Black Desert Online",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_640P,  # Fast combat, detailed effects
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=720,
        notes="Action combat with many effects. 640x360 for skill visibility.",
    ),
    "new_world": GameResolutionConfig(
        game_id="new_world",
        game_name="New World",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_480P,
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=640,
        notes="Clean modern UI. 480x270 captures gameplay well.",
    ),
    "path_of_exile": GameResolutionConfig(
        game_id="path_of_exile",
        game_name="Path of Exile",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_640P,  # Complex loot/skills
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=800,
        notes="Complex UI with many indicators. 640x360 for item/skill visibility.",
    ),
    "runescape": GameResolutionConfig(
        game_id="runescape",
        game_name="RuneScape / OSRS",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_480P,
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=480,
        notes="Low-res friendly. 480x270 is ideal for classic gameplay.",
    ),
    "albion_online": GameResolutionConfig(
        game_id="albion_online",
        game_name="Albion Online",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_480P,
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=480,
        notes="Isometric view scales well. 480x270 recommended.",
    ),
    # =========================================================================
    # Default / Custom Games
    # =========================================================================
    "custom": GameResolutionConfig(
        game_id="custom",
        game_name="Custom Game",
        min_resolution=RESOLUTION_480P,
        recommended_resolution=RESOLUTION_480P,
        max_resolution=RESOLUTION_720P,
        supported_resolutions=STANDARD_RESOLUTIONS,
        min_ui_width=480,
        notes="Default configuration. Use 480x270 for best performance.",
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_game_config(game_id: str) -> GameResolutionConfig:
    """Get resolution configuration for a game."""
    game_id_lower = game_id.lower().replace(" ", "_").replace("-", "_")
    return GAME_CONFIGS.get(game_id_lower, GAME_CONFIGS["custom"])


def get_recommended_resolution(game_id: str) -> Resolution:
    """Get recommended resolution for a game."""
    config = get_game_config(game_id)
    return config.recommended_resolution


def get_supported_resolutions(game_id: str) -> List[Resolution]:
    """Get list of supported resolutions for a game."""
    config = get_game_config(game_id)
    return config.supported_resolutions


def parse_resolution(resolution_str: str) -> Tuple[int, int]:
    """
    Parse resolution string to (width, height) tuple.

    Accepts: "480x270", "640x360", "native", etc.
    """
    if resolution_str.lower() == "native":
        return (0, 0)  # Caller should detect native resolution

    try:
        parts = resolution_str.lower().split("x")
        return (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        # Default to recommended
        return (480, 270)


def get_resolution_for_model(
    resolution_str: str, native_width: int = 1920, native_height: int = 1080
) -> Tuple[int, int]:
    """
    Get actual resolution dimensions for model input.

    Args:
        resolution_str: Resolution string (e.g., "480x270", "native")
        native_width: Native screen width (for "native" option)
        native_height: Native screen height (for "native" option)

    Returns:
        (width, height) tuple
    """
    width, height = parse_resolution(resolution_str)

    if width == 0 or height == 0:
        # Cap native at HD for model compatibility
        return (min(native_width, 1280), min(native_height, 720))

    return (width, height)


def get_resolution_options_for_ui() -> List[Dict[str, str]]:
    """
    Get resolution options formatted for UI dropdowns.

    Returns list of dicts with 'value', 'label', 'recommended', 'experimental' keys.
    """
    options = []
    for res in STANDARD_RESOLUTIONS:
        label = res.name
        if res.recommended:
            label += " [Recommended]"
        if res.experimental:
            label += " [Experimental]"

        options.append(
            {
                "value": str(res),
                "label": label,
                "recommended": res.recommended,
                "experimental": res.experimental,
                "description": res.description,
            }
        )

    # Add native option
    options.append(
        {
            "value": "native",
            "label": "Native (Full Screen) [Experimental]",
            "recommended": False,
            "experimental": True,
            "description": "Uses full screen resolution. Not recommended for training.",
        }
    )

    return options


def get_performance_estimate(width: int, height: int) -> Dict[str, Any]:
    """
    Estimate performance characteristics for a resolution.

    Returns dict with:
    - training_speed: relative speed (1.0 = baseline at 480x270)
    - memory_usage: relative memory (1.0 = baseline)
    - dataset_size_factor: how much larger datasets will be
    """
    baseline_pixels = 480 * 270  # 129,600 pixels
    current_pixels = width * height

    ratio = current_pixels / baseline_pixels

    return {
        "training_speed": 1.0 / ratio,  # Inversely proportional
        "memory_usage": ratio,
        "dataset_size_factor": ratio,
        "pixels": current_pixels,
        "recommended": ratio <= 1.5,  # Up to 640x360 is recommended
    }


# =============================================================================
# Resolution Table (for documentation)
# =============================================================================

RESOLUTION_TABLE = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    MMORPG Game Resolution Analysis                             ║
╠═══════════════════════════╦════════════╦════════════╦═════════════════════════╣
║ Game                      ║ Recommended ║ Max        ║ Notes                   ║
╠═══════════════════════════╬════════════╬════════════╬═════════════════════════╣
║ Genshin Impact            ║ 480x270    ║ 1280x720   ║ Mobile UI scales well   ║
║ World of Warcraft         ║ 640x360    ║ 1280x720   ║ Complex addon UI        ║
║ Final Fantasy XIV         ║ 640x360    ║ 1280x720   ║ Detailed hotbars        ║
║ Guild Wars 2              ║ 480x270    ║ 1280x720   ║ Clean UI design         ║
║ Lost Ark                  ║ 640x360    ║ 1280x720   ║ Many skill indicators   ║
║ Elder Scrolls Online      ║ 480x270    ║ 1280x720   ║ Minimal UI design       ║
║ Black Desert Online       ║ 640x360    ║ 1280x720   ║ Action combat effects   ║
║ New World                 ║ 480x270    ║ 1280x720   ║ Clean modern UI         ║
║ Path of Exile             ║ 640x360    ║ 1280x720   ║ Complex loot system     ║
║ RuneScape / OSRS          ║ 480x270    ║ 1280x720   ║ Low-res friendly        ║
║ Albion Online             ║ 480x270    ║ 1280x720   ║ Isometric scales well   ║
╠═══════════════════════════╩════════════╩════════════╩═════════════════════════╣
║ Default (Custom Games)    ║ 480x270    ║ 1280x720   ║ Best performance        ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Performance Notes:
- 480x270:  1.0x speed, 1.0x memory, 1.0x dataset size (RECOMMENDED)
- 640x360:  0.56x speed, 1.78x memory, 1.78x dataset size (Good)
- 960x540:  0.25x speed, 4.0x memory, 4.0x dataset size (Moderate)
- 1280x720: 0.14x speed, 7.1x memory, 7.1x dataset size (EXPERIMENTAL)

4K (3840x2160) is NOT SUPPORTED - reserved for future hyperresolution mapping.
"""


if __name__ == "__main__":
    print(RESOLUTION_TABLE)
    print("\nResolution options for UI:")
    for opt in get_resolution_options_for_ui():
        print(f"  {opt['value']}: {opt['label']}")
