"""
MMORPG Action Mapping System for BOT-MMORPG-AI

This module defines comprehensive action mappings for MMORPG games,
supporting both keyboard+mouse and gamepad inputs.

Action Categories:
1. Movement: WASD, analog sticks
2. Skills: 1-9, F1-F12, skill combos
3. Combat: Attack, dodge, block, target
4. UI: Inventory, map, menu
5. Communication: Chat, emotes
6. Camera: Mouse look, zoom

Output Design:
- Multi-label: Multiple actions can be active simultaneously
- Continuous: Analog values for movement/camera
- Discrete: Button presses for skills
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional


class ActionCategory(Enum):
    """Categories of game actions."""

    MOVEMENT = auto()  # WASD, run, jump
    SKILLS = auto()  # Hotbar skills 1-9
    COMBAT = auto()  # Attack, dodge, block
    TARGETING = auto()  # Tab-target, click-target
    CAMERA = auto()  # Mouse look, zoom
    UI = auto()  # Inventory, map, menu
    COMMUNICATION = auto()  # Chat, emotes
    MODIFIER = auto()  # Shift, Ctrl, Alt


@dataclass
class ActionDefinition:
    """Definition of a single action."""

    id: int
    name: str
    category: ActionCategory
    key_binding: Optional[str] = None
    gamepad_binding: Optional[str] = None
    is_continuous: bool = False  # True for analog (movement, camera)
    is_toggle: bool = False  # True for toggle states (autorun)
    cooldown_ms: int = 0  # Minimum time between activations
    description: str = ""


@dataclass
class ActionGroup:
    """Group of related actions (e.g., movement directions)."""

    name: str
    actions: List[ActionDefinition]
    mutually_exclusive: bool = True  # Can only one be active?


# =============================================================================
# Standard MMORPG Action Definitions
# =============================================================================

# Movement Actions (0-15)
MOVEMENT_ACTIONS = [
    ActionDefinition(
        0,
        "move_forward",
        ActionCategory.MOVEMENT,
        "W",
        "Ly+",
        True,
        description="Move forward",
    ),
    ActionDefinition(
        1,
        "move_backward",
        ActionCategory.MOVEMENT,
        "S",
        "Ly-",
        True,
        description="Move backward",
    ),
    ActionDefinition(
        2,
        "move_left",
        ActionCategory.MOVEMENT,
        "A",
        "Lx-",
        True,
        description="Strafe left",
    ),
    ActionDefinition(
        3,
        "move_right",
        ActionCategory.MOVEMENT,
        "D",
        "Lx+",
        True,
        description="Strafe right",
    ),
    ActionDefinition(
        4,
        "move_forward_left",
        ActionCategory.MOVEMENT,
        "W+A",
        None,
        True,
        description="Move diagonally",
    ),
    ActionDefinition(
        5,
        "move_forward_right",
        ActionCategory.MOVEMENT,
        "W+D",
        None,
        True,
        description="Move diagonally",
    ),
    ActionDefinition(
        6,
        "move_backward_left",
        ActionCategory.MOVEMENT,
        "S+A",
        None,
        True,
        description="Move diagonally",
    ),
    ActionDefinition(
        7,
        "move_backward_right",
        ActionCategory.MOVEMENT,
        "S+D",
        None,
        True,
        description="Move diagonally",
    ),
    ActionDefinition(
        8,
        "jump",
        ActionCategory.MOVEMENT,
        "Space",
        "A",
        cooldown_ms=500,
        description="Jump",
    ),
    ActionDefinition(9, "sprint", ActionCategory.MOVEMENT, "Shift", "L3", description="Sprint/Run"),
    ActionDefinition(
        10,
        "crouch",
        ActionCategory.MOVEMENT,
        "Ctrl",
        "R3",
        is_toggle=True,
        description="Crouch/Sneak",
    ),
    ActionDefinition(
        11,
        "dodge",
        ActionCategory.MOVEMENT,
        "Alt",
        "B",
        cooldown_ms=1000,
        description="Dodge roll",
    ),
    ActionDefinition(
        12,
        "mount",
        ActionCategory.MOVEMENT,
        "Z",
        "DOWN",
        cooldown_ms=2000,
        description="Mount/Dismount",
    ),
    ActionDefinition(
        13,
        "autorun",
        ActionCategory.MOVEMENT,
        "NumLock",
        "L3+R3",
        is_toggle=True,
        description="Auto-run toggle",
    ),
    ActionDefinition(14, "swim_up", ActionCategory.MOVEMENT, "Space", "A", description="Swim up"),
    ActionDefinition(
        15, "swim_down", ActionCategory.MOVEMENT, "Ctrl", "B", description="Swim down"
    ),
]

# Skill Actions (16-35) - Hotbar slots
SKILL_ACTIONS = [
    ActionDefinition(
        16,
        "skill_1",
        ActionCategory.SKILLS,
        "1",
        "X",
        cooldown_ms=100,
        description="Skill slot 1",
    ),
    ActionDefinition(
        17,
        "skill_2",
        ActionCategory.SKILLS,
        "2",
        "Y",
        cooldown_ms=100,
        description="Skill slot 2",
    ),
    ActionDefinition(
        18,
        "skill_3",
        ActionCategory.SKILLS,
        "3",
        "RB",
        cooldown_ms=100,
        description="Skill slot 3",
    ),
    ActionDefinition(
        19,
        "skill_4",
        ActionCategory.SKILLS,
        "4",
        "LB",
        cooldown_ms=100,
        description="Skill slot 4",
    ),
    ActionDefinition(
        20,
        "skill_5",
        ActionCategory.SKILLS,
        "5",
        "RT+X",
        cooldown_ms=100,
        description="Skill slot 5",
    ),
    ActionDefinition(
        21,
        "skill_6",
        ActionCategory.SKILLS,
        "6",
        "RT+Y",
        cooldown_ms=100,
        description="Skill slot 6",
    ),
    ActionDefinition(
        22,
        "skill_7",
        ActionCategory.SKILLS,
        "7",
        "RT+RB",
        cooldown_ms=100,
        description="Skill slot 7",
    ),
    ActionDefinition(
        23,
        "skill_8",
        ActionCategory.SKILLS,
        "8",
        "RT+LB",
        cooldown_ms=100,
        description="Skill slot 8",
    ),
    ActionDefinition(
        24,
        "skill_9",
        ActionCategory.SKILLS,
        "9",
        "LT+X",
        cooldown_ms=100,
        description="Skill slot 9",
    ),
    ActionDefinition(
        25,
        "skill_0",
        ActionCategory.SKILLS,
        "0",
        "LT+Y",
        cooldown_ms=100,
        description="Skill slot 10",
    ),
    ActionDefinition(
        26,
        "skill_minus",
        ActionCategory.SKILLS,
        "-",
        "LT+RB",
        cooldown_ms=100,
        description="Skill slot 11",
    ),
    ActionDefinition(
        27,
        "skill_equals",
        ActionCategory.SKILLS,
        "=",
        "LT+LB",
        cooldown_ms=100,
        description="Skill slot 12",
    ),
    # F-key skills (common in WoW, FFXIV)
    ActionDefinition(
        28,
        "skill_f1",
        ActionCategory.SKILLS,
        "F1",
        None,
        cooldown_ms=100,
        description="F1 action",
    ),
    ActionDefinition(
        29,
        "skill_f2",
        ActionCategory.SKILLS,
        "F2",
        None,
        cooldown_ms=100,
        description="F2 action",
    ),
    ActionDefinition(
        30,
        "skill_f3",
        ActionCategory.SKILLS,
        "F3",
        None,
        cooldown_ms=100,
        description="F3 action",
    ),
    ActionDefinition(
        31,
        "skill_f4",
        ActionCategory.SKILLS,
        "F4",
        None,
        cooldown_ms=100,
        description="F4 action",
    ),
    # Quick slot skills (Shift+number)
    ActionDefinition(
        32,
        "skill_shift_1",
        ActionCategory.SKILLS,
        "Shift+1",
        None,
        cooldown_ms=100,
        description="Shift+1",
    ),
    ActionDefinition(
        33,
        "skill_shift_2",
        ActionCategory.SKILLS,
        "Shift+2",
        None,
        cooldown_ms=100,
        description="Shift+2",
    ),
    ActionDefinition(
        34,
        "skill_shift_3",
        ActionCategory.SKILLS,
        "Shift+3",
        None,
        cooldown_ms=100,
        description="Shift+3",
    ),
    ActionDefinition(
        35,
        "skill_shift_4",
        ActionCategory.SKILLS,
        "Shift+4",
        None,
        cooldown_ms=100,
        description="Shift+4",
    ),
]

# Combat Actions (36-47)
COMBAT_ACTIONS = [
    ActionDefinition(
        36,
        "attack_basic",
        ActionCategory.COMBAT,
        "LMB",
        "RT",
        description="Basic attack",
    ),
    ActionDefinition(
        37,
        "attack_heavy",
        ActionCategory.COMBAT,
        "RMB",
        "LT",
        cooldown_ms=500,
        description="Heavy attack",
    ),
    ActionDefinition(
        38,
        "block",
        ActionCategory.COMBAT,
        "RMB_hold",
        "LT_hold",
        description="Block/Parry",
    ),
    ActionDefinition(
        39, "interact", ActionCategory.COMBAT, "E", "A", description="Interact/Pickup"
    ),
    ActionDefinition(
        40,
        "use_item",
        ActionCategory.COMBAT,
        "Q",
        "UP",
        cooldown_ms=1000,
        description="Use quick item",
    ),
    ActionDefinition(
        41,
        "ultimate",
        ActionCategory.COMBAT,
        "R",
        "LB+RB",
        cooldown_ms=30000,
        description="Ultimate ability",
    ),
    ActionDefinition(
        42,
        "heal",
        ActionCategory.COMBAT,
        "H",
        "DOWN",
        cooldown_ms=10000,
        description="Heal/Potion",
    ),
    ActionDefinition(
        43,
        "buff_self",
        ActionCategory.COMBAT,
        "B",
        "LEFT",
        cooldown_ms=60000,
        description="Self buff",
    ),
    ActionDefinition(
        44,
        "combo_1",
        ActionCategory.COMBAT,
        "Shift+LMB",
        "RT+A",
        description="Combo attack 1",
    ),
    ActionDefinition(
        45,
        "combo_2",
        ActionCategory.COMBAT,
        "Shift+RMB",
        "LT+A",
        description="Combo attack 2",
    ),
    ActionDefinition(
        46,
        "weapon_swap",
        ActionCategory.COMBAT,
        "`",
        "SELECT",
        cooldown_ms=1000,
        description="Swap weapon",
    ),
    ActionDefinition(
        47,
        "special",
        ActionCategory.COMBAT,
        "V",
        "R3",
        cooldown_ms=5000,
        description="Special action",
    ),
]

# Targeting Actions (48-55)
TARGETING_ACTIONS = [
    ActionDefinition(
        48,
        "target_nearest",
        ActionCategory.TARGETING,
        "Tab",
        "RB",
        description="Target nearest enemy",
    ),
    ActionDefinition(
        49,
        "target_prev",
        ActionCategory.TARGETING,
        "Shift+Tab",
        "LB",
        description="Target previous",
    ),
    ActionDefinition(
        50,
        "target_self",
        ActionCategory.TARGETING,
        "F1",
        None,
        description="Target self",
    ),
    ActionDefinition(
        51,
        "target_party_1",
        ActionCategory.TARGETING,
        "F2",
        None,
        description="Target party member 1",
    ),
    ActionDefinition(
        52,
        "target_party_2",
        ActionCategory.TARGETING,
        "F3",
        None,
        description="Target party member 2",
    ),
    ActionDefinition(
        53,
        "target_party_3",
        ActionCategory.TARGETING,
        "F4",
        None,
        description="Target party member 3",
    ),
    ActionDefinition(
        54,
        "clear_target",
        ActionCategory.TARGETING,
        "Escape",
        "B",
        description="Clear target",
    ),
    ActionDefinition(
        55,
        "focus_target",
        ActionCategory.TARGETING,
        "Shift+F",
        None,
        description="Set focus target",
    ),
]

# Camera Actions (56-63) - Continuous values
CAMERA_ACTIONS = [
    ActionDefinition(
        56,
        "camera_left",
        ActionCategory.CAMERA,
        "MouseX-",
        "Rx-",
        True,
        description="Rotate camera left",
    ),
    ActionDefinition(
        57,
        "camera_right",
        ActionCategory.CAMERA,
        "MouseX+",
        "Rx+",
        True,
        description="Rotate camera right",
    ),
    ActionDefinition(
        58,
        "camera_up",
        ActionCategory.CAMERA,
        "MouseY-",
        "Ry-",
        True,
        description="Tilt camera up",
    ),
    ActionDefinition(
        59,
        "camera_down",
        ActionCategory.CAMERA,
        "MouseY+",
        "Ry+",
        True,
        description="Tilt camera down",
    ),
    ActionDefinition(60, "zoom_in", ActionCategory.CAMERA, "ScrollUp", "UP", description="Zoom in"),
    ActionDefinition(
        61,
        "zoom_out",
        ActionCategory.CAMERA,
        "ScrollDown",
        "DOWN",
        description="Zoom out",
    ),
    ActionDefinition(
        62,
        "first_person",
        ActionCategory.CAMERA,
        "Home",
        None,
        description="First person view",
    ),
    ActionDefinition(
        63,
        "reset_camera",
        ActionCategory.CAMERA,
        "End",
        "R3",
        description="Reset camera",
    ),
]

# UI Actions (64-71)
UI_ACTIONS = [
    ActionDefinition(
        64, "inventory", ActionCategory.UI, "I", "START", description="Open inventory"
    ),
    ActionDefinition(65, "map", ActionCategory.UI, "M", "SELECT", description="Open map"),
    ActionDefinition(66, "character", ActionCategory.UI, "C", None, description="Character screen"),
    ActionDefinition(67, "skills_menu", ActionCategory.UI, "K", None, description="Skills menu"),
    ActionDefinition(68, "quest_log", ActionCategory.UI, "J", None, description="Quest log"),
    ActionDefinition(69, "social", ActionCategory.UI, "O", None, description="Social/Friends"),
    ActionDefinition(
        70,
        "escape_menu",
        ActionCategory.UI,
        "Escape",
        "START",
        description="Escape/Pause menu",
    ),
    ActionDefinition(
        71,
        "screenshot",
        ActionCategory.UI,
        "PrintScreen",
        None,
        description="Take screenshot",
    ),
]

# Special state: No action
NO_ACTION = ActionDefinition(
    72, "idle", ActionCategory.MOVEMENT, None, None, description="No action/Idle"
)


# =============================================================================
# Action Space Configurations
# =============================================================================


@dataclass
class ActionSpaceConfig:
    """Configuration for model action space."""

    name: str
    description: str
    actions: List[ActionDefinition]
    output_type: str  # "single" (softmax) or "multi" (sigmoid)

    @property
    def num_actions(self) -> int:
        return len(self.actions)

    @property
    def action_names(self) -> List[str]:
        return [a.name for a in self.actions]

    def get_action_by_id(self, action_id: int) -> Optional[ActionDefinition]:
        for action in self.actions:
            if action.id == action_id:
                return action
        return None


# Basic action space (original - movement only)
ACTION_SPACE_BASIC = ActionSpaceConfig(
    name="basic",
    description="Basic WASD movement only (9 actions)",
    actions=[
        ActionDefinition(0, "W", ActionCategory.MOVEMENT, "W"),
        ActionDefinition(1, "S", ActionCategory.MOVEMENT, "S"),
        ActionDefinition(2, "A", ActionCategory.MOVEMENT, "A"),
        ActionDefinition(3, "D", ActionCategory.MOVEMENT, "D"),
        ActionDefinition(4, "WA", ActionCategory.MOVEMENT, "W+A"),
        ActionDefinition(5, "WD", ActionCategory.MOVEMENT, "W+D"),
        ActionDefinition(6, "SA", ActionCategory.MOVEMENT, "S+A"),
        ActionDefinition(7, "SD", ActionCategory.MOVEMENT, "S+D"),
        ActionDefinition(8, "NOKEY", ActionCategory.MOVEMENT, None),
    ],
    output_type="single",
)

# Standard action space (29 actions - current default)
ACTION_SPACE_STANDARD = ActionSpaceConfig(
    name="standard",
    description="Standard keyboard + gamepad (29 actions)",
    actions=MOVEMENT_ACTIONS[:9]
    + [  # Basic movement
        ActionDefinition(9, "gamepad_lt", ActionCategory.COMBAT, None, "LT", True),
        ActionDefinition(10, "gamepad_rt", ActionCategory.COMBAT, None, "RT", True),
        ActionDefinition(11, "gamepad_lx", ActionCategory.MOVEMENT, None, "Lx", True),
        ActionDefinition(12, "gamepad_ly", ActionCategory.MOVEMENT, None, "Ly", True),
        ActionDefinition(13, "gamepad_rx", ActionCategory.CAMERA, None, "Rx", True),
        ActionDefinition(14, "gamepad_ry", ActionCategory.CAMERA, None, "Ry", True),
        ActionDefinition(15, "gamepad_up", ActionCategory.UI, None, "UP"),
        ActionDefinition(16, "gamepad_down", ActionCategory.UI, None, "DOWN"),
        ActionDefinition(17, "gamepad_left", ActionCategory.UI, None, "LEFT"),
        ActionDefinition(18, "gamepad_right", ActionCategory.UI, None, "RIGHT"),
        ActionDefinition(19, "gamepad_start", ActionCategory.UI, None, "START"),
        ActionDefinition(20, "gamepad_select", ActionCategory.UI, None, "SELECT"),
        ActionDefinition(21, "gamepad_l3", ActionCategory.MOVEMENT, None, "L3"),
        ActionDefinition(22, "gamepad_r3", ActionCategory.CAMERA, None, "R3"),
        ActionDefinition(23, "gamepad_lb", ActionCategory.SKILLS, None, "LB"),
        ActionDefinition(24, "gamepad_rb", ActionCategory.SKILLS, None, "RB"),
        ActionDefinition(25, "gamepad_a", ActionCategory.COMBAT, None, "A"),
        ActionDefinition(26, "gamepad_b", ActionCategory.COMBAT, None, "B"),
        ActionDefinition(27, "gamepad_x", ActionCategory.SKILLS, None, "X"),
        ActionDefinition(28, "gamepad_y", ActionCategory.SKILLS, None, "Y"),
    ],
    output_type="single",
)

# Extended action space (73 actions - full MMORPG)
ACTION_SPACE_EXTENDED = ActionSpaceConfig(
    name="extended",
    description="Full MMORPG action space with skills (73 actions)",
    actions=(
        MOVEMENT_ACTIONS  # 0-15
        + SKILL_ACTIONS  # 16-35
        + COMBAT_ACTIONS  # 36-47
        + TARGETING_ACTIONS  # 48-55
        + CAMERA_ACTIONS  # 56-63
        + UI_ACTIONS  # 64-71
        + [NO_ACTION]  # 72
    ),
    output_type="multi",  # Allow simultaneous actions
)

# Compact skill-focused (for action games like Lost Ark, BDO)
ACTION_SPACE_COMBAT = ActionSpaceConfig(
    name="combat",
    description="Combat-focused with movement + skills (48 actions)",
    actions=(MOVEMENT_ACTIONS + SKILL_ACTIONS + COMBAT_ACTIONS),  # 0-15  # 16-35  # 36-47
    output_type="multi",
)


# =============================================================================
# Action Space Registry
# =============================================================================

ACTION_SPACES: Dict[str, ActionSpaceConfig] = {
    "basic": ACTION_SPACE_BASIC,
    "standard": ACTION_SPACE_STANDARD,
    "extended": ACTION_SPACE_EXTENDED,
    "combat": ACTION_SPACE_COMBAT,
}


def get_action_space(name: str = "standard") -> ActionSpaceConfig:
    """Get action space configuration by name."""
    return ACTION_SPACES.get(name.lower(), ACTION_SPACE_STANDARD)


def list_action_spaces() -> List[str]:
    """List available action space names."""
    return list(ACTION_SPACES.keys())


# =============================================================================
# Multi-Label Output Encoding
# =============================================================================


def encode_actions_multi_label(
    active_actions: List[str], action_space: ActionSpaceConfig
) -> List[int]:
    """
    Encode multiple simultaneous actions as multi-label vector.

    Args:
        active_actions: List of action names that are active
        action_space: Action space configuration

    Returns:
        Binary vector where 1 = action active, 0 = inactive
    """
    output = [0] * action_space.num_actions

    for action_name in active_actions:
        for i, action in enumerate(action_space.actions):
            if action.name == action_name:
                output[i] = 1
                break

    return output


def decode_actions_multi_label(
    output_vector: List[float], action_space: ActionSpaceConfig, threshold: float = 0.5
) -> List[ActionDefinition]:
    """
    Decode multi-label output to list of active actions.

    Args:
        output_vector: Model output (probabilities)
        action_space: Action space configuration
        threshold: Activation threshold

    Returns:
        List of active ActionDefinition objects
    """
    active_actions = []

    for i, (prob, action) in enumerate(zip(output_vector, action_space.actions)):
        if prob >= threshold:
            active_actions.append(action)

    return active_actions


# =============================================================================
# Game-Specific Presets
# =============================================================================

GAME_ACTION_PRESETS: Dict[str, str] = {
    # Action MMORPGs - need full skill bars
    "genshin_impact": "combat",
    "lost_ark": "combat",
    "black_desert_online": "combat",
    "new_world": "combat",
    # Tab-target MMORPGs - standard is fine
    "world_of_warcraft": "extended",
    "final_fantasy_xiv": "extended",
    "guild_wars_2": "combat",
    "elder_scrolls_online": "combat",
    # Simpler games
    "runescape": "standard",
    "albion_online": "standard",
    "path_of_exile": "combat",
    # Default
    "custom": "standard",
}


def get_recommended_action_space(game_id: str) -> ActionSpaceConfig:
    """Get recommended action space for a specific game."""
    game_id_lower = game_id.lower().replace(" ", "_").replace("-", "_")
    preset_name = GAME_ACTION_PRESETS.get(game_id_lower, "standard")
    return get_action_space(preset_name)


# =============================================================================
# Documentation
# =============================================================================

ACTION_SPACE_TABLE = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    MMORPG Action Space Configurations                          ║
╠═══════════════════╦════════════╦═════════════════════════════════════════════╣
║ Name              ║ Actions    ║ Description                                  ║
╠═══════════════════╬════════════╬═════════════════════════════════════════════╣
║ basic             ║ 9          ║ WASD movement only (original)                ║
║ standard          ║ 29         ║ Keyboard + full gamepad                      ║
║ combat            ║ 48         ║ Movement + skills + combat (action RPGs)     ║
║ extended          ║ 73         ║ Full MMORPG (movement, skills, UI, camera)   ║
╚═══════════════════╩════════════╩═════════════════════════════════════════════╝

Output Types:
- single: One action at a time (softmax) - good for simple routing
- multi: Multiple simultaneous actions (sigmoid) - good for combat

Game Recommendations:
- Genshin Impact, Lost Ark, BDO: combat (48 actions, multi-label)
- WoW, FFXIV: extended (73 actions, multi-label)
- RuneScape, Albion: standard (29 actions, single-label)
"""


if __name__ == "__main__":
    print(ACTION_SPACE_TABLE)
    print("\nAvailable action spaces:")
    for name, space in ACTION_SPACES.items():
        print(f"  {name}: {space.num_actions} actions - {space.description}")
