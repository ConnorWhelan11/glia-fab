from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class FabRole(str, Enum):
    SPAWN_PLAYER = "spawn_player"
    COLLIDER = "collider"
    TRIGGER = "trigger"
    INTERACT = "interact"


_NAME_ALIASES: dict[FabRole, tuple[str, ...]] = {
    FabRole.SPAWN_PLAYER: ("SPAWN_PLAYER", "OL_SPAWN_PLAYER", "OL_SPAWN_PLAYER_"),
    FabRole.COLLIDER: ("COLLIDER_", "OL_COLLIDER_"),
    FabRole.TRIGGER: ("TRIGGER_", "OL_TRIGGER_"),
    FabRole.INTERACT: ("INTERACT_", "OL_INTERACT_"),
}


def infer_role_from_name(name: str) -> FabRole | None:
    """Infer Fab role purely from a node/object name (case-insensitive)."""
    normalized = name.strip().upper()

    if normalized == "SPAWN_PLAYER" or normalized.startswith("SPAWN_PLAYER_"):
        return FabRole.SPAWN_PLAYER
    if normalized == "OL_SPAWN_PLAYER" or normalized.startswith("OL_SPAWN_PLAYER_"):
        return FabRole.SPAWN_PLAYER

    if normalized.startswith("COLLIDER_") or normalized.startswith("OL_COLLIDER_"):
        return FabRole.COLLIDER
    if normalized.startswith("TRIGGER_") or normalized.startswith("OL_TRIGGER_"):
        return FabRole.TRIGGER
    if normalized.startswith("INTERACT_") or normalized.startswith("OL_INTERACT_"):
        return FabRole.INTERACT

    return None


@dataclass
class FabGameContractReport:
    spawns: list[str] = field(default_factory=list)
    colliders: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    interactables: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def playable(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "spawns": self.spawns,
            "colliders": self.colliders,
            "triggers": self.triggers,
            "interactables": self.interactables,
            "errors": self.errors,
            "warnings": self.warnings,
            "playable": self.playable,
        }


def validate_fab_game_contract(
    exported_object_names: Iterable[str],
    *,
    require_colliders: bool = True,
) -> FabGameContractReport:
    """Validate the minimal Blender→Godot contract against exported object names."""
    report = FabGameContractReport()

    for name in exported_object_names:
        role = infer_role_from_name(name)
        if role is None:
            continue
        if role == FabRole.SPAWN_PLAYER:
            report.spawns.append(name)
        elif role == FabRole.COLLIDER:
            report.colliders.append(name)
        elif role == FabRole.TRIGGER:
            report.triggers.append(name)
        elif role == FabRole.INTERACT:
            report.interactables.append(name)

    if len(report.spawns) == 0:
        report.errors.append(
            "Missing player spawn marker (expected SPAWN_PLAYER or ol_spawn_player)."
        )
    elif len(report.spawns) > 1:
        report.errors.append(
            "Multiple player spawns found; expected exactly 1 "
            f"(found {len(report.spawns)})."
        )

    if require_colliders and len(report.colliders) == 0:
        report.errors.append(
            "Missing collider marker meshes (expected COLLIDER_* or ol_collider_*)."
        )

    return report


__all__ = [
    "FabRole",
    "FabGameContractReport",
    "infer_role_from_name",
    "validate_fab_game_contract",
]
