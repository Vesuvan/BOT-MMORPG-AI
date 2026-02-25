"""
Model Selection System

Recommends the best neural network architecture based on:
- Hardware capabilities
- Game requirements
- Task type
- User preferences
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .hardware_detector import HardwareDetector, HardwareTier, SystemInfo
from .profile_loader import GameProfile, GameProfileLoader


class Architecture(Enum):
    """Available neural network architectures."""

    MOBILENETV3 = "mobilenetv3"
    EFFICIENTNET_SIMPLE = "efficientnet_simple"
    EFFICIENTNET_LSTM = "efficientnet_lstm"
    RESNET18_LSTM = "resnet18_lstm"

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        names = {
            "mobilenetv3": "MobileNetV3 (Lightweight)",
            "efficientnet_simple": "EfficientNet (Balanced)",
            "efficientnet_lstm": "EfficientNet-LSTM (Temporal)",
            "resnet18_lstm": "ResNet18-LSTM (Spatial)",
        }
        return names.get(self.value, self.value)

    @property
    def supports_temporal(self) -> bool:
        """Whether this architecture supports temporal processing."""
        return "lstm" in self.value.lower()


@dataclass
class ModelRecommendation:
    """A model recommendation with reasoning."""

    architecture: Architecture
    confidence: float  # 0-1, how confident we are this is the right choice
    reasons: List[str]  # Why this model was chosen
    warnings: List[str]  # Potential issues to be aware of

    # Estimated performance metrics
    estimated_speed: str  # "fast", "medium", "slow"
    estimated_accuracy: str  # "good", "better", "best"
    estimated_vram_mb: int

    # Configuration
    recommended_input_size: Tuple[int, int]
    recommended_temporal_frames: int
    recommended_batch_size: int

    def summary(self) -> str:
        """Human-readable recommendation summary."""
        lines = [
            f"Recommended: {self.architecture.display_name}",
            f"Confidence: {self.confidence:.0%}",
            "",
            "Why this model:",
        ]
        for reason in self.reasons:
            lines.append(f"  + {reason}")

        if self.warnings:
            lines.append("")
            lines.append("Notes:")
            for warning in self.warnings:
                lines.append(f"  ! {warning}")

        lines.extend(
            [
                "",
                f"Speed: {self.estimated_speed.upper()}",
                f"Accuracy: {self.estimated_accuracy.upper()}",
                f"VRAM Usage: ~{self.estimated_vram_mb}MB",
            ]
        )

        return "\n".join(lines)


# Model characteristics database
MODEL_SPECS = {
    Architecture.MOBILENETV3: {
        "vram_mb": 800,
        "speed": "fast",
        "accuracy": "good",
        "min_vram": 2048,
        "temporal": False,
        "best_for": ["farming", "gathering", "simple tasks"],
        "input_sizes": [(160, 160), (224, 224)],
    },
    Architecture.EFFICIENTNET_SIMPLE: {
        "vram_mb": 1500,
        "speed": "medium",
        "accuracy": "better",
        "min_vram": 4096,
        "temporal": False,
        "best_for": ["crafting", "navigation", "moderate complexity"],
        "input_sizes": [(224, 224), (256, 256)],
    },
    Architecture.EFFICIENTNET_LSTM: {
        "vram_mb": 2500,
        "speed": "medium",
        "accuracy": "best",
        "min_vram": 6144,
        "temporal": True,
        "best_for": ["combat", "dungeons", "reaction-based tasks"],
        "input_sizes": [(224, 224), (256, 256)],
    },
    Architecture.RESNET18_LSTM: {
        "vram_mb": 2000,
        "speed": "medium",
        "accuracy": "better",
        "min_vram": 4096,
        "temporal": True,
        "best_for": ["navigation", "spatial awareness", "world bosses"],
        "input_sizes": [(224, 224)],
    },
}


class ModelSelector:
    """
    Intelligent model selection system.

    Recommends the best architecture based on multiple factors and provides
    clear reasoning for the recommendation.

    Usage:
        selector = ModelSelector()
        recommendation = selector.recommend(
            game_id="world_of_warcraft",
            task="combat"
        )
        print(recommendation.summary())
    """

    def __init__(self):
        self.hardware_detector = HardwareDetector()
        self.profile_loader = GameProfileLoader()

    def recommend(
        self,
        game_id: Optional[str] = None,
        task: Optional[str] = None,
        priority: str = "balanced",  # speed | accuracy | balanced
        force_temporal: Optional[bool] = None,
    ) -> ModelRecommendation:
        """
        Get a model recommendation.

        Args:
            game_id: Game identifier (optional, for game-specific tuning)
            task: Task type (combat, farming, etc.)
            priority: Optimization priority
            force_temporal: Force temporal/non-temporal (overrides auto-detect)

        Returns:
            ModelRecommendation with full details
        """
        # Detect hardware
        hw_info = self.hardware_detector.detect()

        # Load game profile if available
        profile = None
        if game_id:
            try:
                profile = self.profile_loader.load(game_id)
            except FileNotFoundError:
                pass

        # Determine requirements
        needs_temporal = self._determine_temporal_need(
            task, profile, force_temporal, hw_info
        )

        # Score each architecture
        scores = self._score_architectures(
            hw_info=hw_info,
            profile=profile,
            task=task,
            priority=priority,
            needs_temporal=needs_temporal,
        )

        # Get best architecture
        best_arch = max(scores, key=lambda a: scores[a]["score"])
        best_score = scores[best_arch]

        # Build recommendation
        return self._build_recommendation(
            architecture=best_arch,
            score_data=best_score,
            hw_info=hw_info,
            profile=profile,
            task=task,
        )

    def _determine_temporal_need(
        self,
        task: Optional[str],
        profile: Optional[GameProfile],
        force_temporal: Optional[bool],
        hw_info: SystemInfo,
    ) -> bool:
        """Determine if temporal processing is needed."""
        if force_temporal is not None:
            return force_temporal

        # Check if hardware can support temporal
        if hw_info.tier == HardwareTier.LOW:
            return False

        # Check task requirements
        temporal_tasks = {
            "combat",
            "dungeon",
            "guardian_raid",
            "world_boss",
            "expedition",
        }
        if task and task.lower() in temporal_tasks:
            return True

        # Check profile
        if profile:
            task_config = profile.get_task_config(task) if task else None
            if task_config and task_config.temporal:
                return True
            # Default to profile's recommendation
            if "lstm" in profile.recommended_architecture.lower():
                return True

        return False

    def _score_architectures(
        self,
        hw_info: SystemInfo,
        profile: Optional[GameProfile],
        task: Optional[str],
        priority: str,
        needs_temporal: bool,
    ) -> Dict[Architecture, Dict]:
        """Score each architecture based on requirements."""
        scores = {}

        for arch in Architecture:
            specs = MODEL_SPECS[arch]
            score = 0.0
            reasons = []
            warnings = []

            # Hardware compatibility
            vram = hw_info.gpu.vram_mb if hw_info.gpu else 0
            if vram < specs["min_vram"]:
                score -= 50
                warnings.append(
                    f"May exceed available VRAM ({vram}MB < {specs['min_vram']}MB)"
                )

            # Temporal matching
            if needs_temporal:
                if specs["temporal"]:
                    score += 30
                    reasons.append("Supports temporal processing for reactions")
                else:
                    score -= 20
                    warnings.append("No temporal support - may miss action patterns")
            else:
                if not specs["temporal"]:
                    score += 10
                    reasons.append("Efficient for non-temporal tasks")

            # Hardware tier matching
            tier_scores = {
                HardwareTier.LOW: {
                    Architecture.MOBILENETV3: 40,
                    Architecture.EFFICIENTNET_SIMPLE: 10,
                    Architecture.EFFICIENTNET_LSTM: -20,
                    Architecture.RESNET18_LSTM: 0,
                },
                HardwareTier.MEDIUM: {
                    Architecture.MOBILENETV3: 20,
                    Architecture.EFFICIENTNET_SIMPLE: 30,
                    Architecture.EFFICIENTNET_LSTM: 25,
                    Architecture.RESNET18_LSTM: 25,
                },
                HardwareTier.HIGH: {
                    Architecture.MOBILENETV3: 0,
                    Architecture.EFFICIENTNET_SIMPLE: 20,
                    Architecture.EFFICIENTNET_LSTM: 40,
                    Architecture.RESNET18_LSTM: 30,
                },
            }
            tier_bonus = tier_scores[hw_info.tier][arch]
            score += tier_bonus
            if tier_bonus > 20:
                reasons.append(f"Optimal for {hw_info.tier.value} hardware")

            # Priority matching
            if priority == "speed":
                if specs["speed"] == "fast":
                    score += 25
                    reasons.append("Fastest inference time")
                elif specs["speed"] == "slow":
                    score -= 15
            elif priority == "accuracy":
                if specs["accuracy"] == "best":
                    score += 25
                    reasons.append("Highest accuracy potential")
                elif specs["accuracy"] == "good":
                    score -= 10

            # Task matching
            if task:
                task_lower = task.lower()
                if any(t in task_lower for t in specs["best_for"]):
                    score += 20
                    reasons.append(f"Designed for {task} tasks")

            # Profile recommendation bonus
            if profile:
                if profile.recommended_architecture == arch.value:
                    score += 15
                    reasons.append(f"Recommended for {profile.name}")

            scores[arch] = {
                "score": score,
                "reasons": reasons,
                "warnings": warnings,
            }

        return scores

    def _build_recommendation(
        self,
        architecture: Architecture,
        score_data: Dict,
        hw_info: SystemInfo,
        profile: Optional[GameProfile],
        task: Optional[str],
    ) -> ModelRecommendation:
        """Build the final recommendation object."""
        specs = MODEL_SPECS[architecture]

        # Determine input size
        if profile:
            tier_config = profile.get_tier_config(hw_info.tier.value)
            input_size = tuple(tier_config.input_size)
        else:
            input_size = specs["input_sizes"][0]

        # Determine temporal frames
        if specs["temporal"]:
            if hw_info.tier == HardwareTier.HIGH:
                temporal_frames = 4
            elif hw_info.tier == HardwareTier.MEDIUM:
                temporal_frames = 2
            else:
                temporal_frames = 0
        else:
            temporal_frames = 0

        # Determine batch size
        batch_sizes = {
            HardwareTier.LOW: 8,
            HardwareTier.MEDIUM: 16,
            HardwareTier.HIGH: 32,
        }
        batch_size = batch_sizes[hw_info.tier]

        # Calculate confidence based on score
        max_possible_score = 100
        confidence = min(1.0, max(0.3, (score_data["score"] + 50) / max_possible_score))

        return ModelRecommendation(
            architecture=architecture,
            confidence=confidence,
            reasons=score_data["reasons"] or ["General-purpose architecture"],
            warnings=score_data["warnings"],
            estimated_speed=specs["speed"],
            estimated_accuracy=specs["accuracy"],
            estimated_vram_mb=specs["vram_mb"],
            recommended_input_size=input_size,
            recommended_temporal_frames=temporal_frames,
            recommended_batch_size=batch_size,
        )

    def list_architectures(self) -> List[Dict]:
        """List all available architectures with their specs."""
        result = []
        for arch in Architecture:
            specs = MODEL_SPECS[arch]
            result.append(
                {
                    "id": arch.value,
                    "name": arch.display_name,
                    "temporal": specs["temporal"],
                    "speed": specs["speed"],
                    "accuracy": specs["accuracy"],
                    "min_vram_mb": specs["min_vram"],
                    "best_for": specs["best_for"],
                }
            )
        return result

    def compare(
        self, game_id: Optional[str] = None, task: Optional[str] = None
    ) -> List[ModelRecommendation]:
        """
        Compare all architectures for given requirements.

        Returns list of recommendations sorted by confidence.
        """
        recommendations = []
        for arch in Architecture:
            # Temporarily force each architecture and get its score
            rec = self.recommend(
                game_id=game_id,
                task=task,
                force_temporal=MODEL_SPECS[arch]["temporal"],
            )
            recommendations.append(rec)

        return sorted(recommendations, key=lambda r: r.confidence, reverse=True)
