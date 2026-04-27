from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VariantStatus(str, Enum):
    ACTIVE = "active"
    KILLED = "killed"


class ActionType(str, Enum):
    LAUNCH = "launch"
    KILL = "kill"
    MUTATE = "mutate"
    SCALE = "scale"


@dataclass
class Venture:
    id: int | None
    name: str
    vertical: str
    config: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    active: bool = True


@dataclass
class Variant:
    id: int | None
    venture_id: int
    spec: dict[str, Any]
    status: VariantStatus = VariantStatus.ACTIVE
    created_at: float = 0.0
    external_ids: dict[str, str] = field(default_factory=dict)
    scale: float = 1.0


@dataclass
class MetricSample:
    id: int | None
    variant_id: int
    channel: str
    name: str
    value: float
    tick: int
    ts: float = 0.0


@dataclass
class Action:
    id: int | None
    venture_id: int
    variant_id: int | None
    type: ActionType
    payload: dict[str, Any] = field(default_factory=dict)
    tick: int = 0
    applied: bool = False
    ts: float = 0.0


@dataclass
class Decision:
    id: int | None
    venture_id: int
    tick: int
    context: dict[str, Any]
    actions: list[Action]
    ts: float = 0.0
