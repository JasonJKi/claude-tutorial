from __future__ import annotations

from typing import Any

from .models import Action, ActionType, Variant


DEFAULTS: dict[str, Any] = {
    "max_actions_per_tick": 5,
    "min_age_before_kill": 3,
    "max_variant_scale": 4.0,
    "max_active_variants": 8,
}


def venture_config_with_defaults(venture_config: dict[str, Any]) -> dict[str, Any]:
    return {**DEFAULTS, **venture_config}


def filter_actions(
    proposed: list[Action],
    variants_by_id: dict[int, Variant],
    venture_config: dict[str, Any],
    current_tick: int,
) -> tuple[list[Action], list[str]]:
    """Apply guardrails to proposed actions. Returns (allowed, rejection_reasons)."""
    cfg = venture_config_with_defaults(venture_config)
    allowed: list[Action] = []
    rejected: list[str] = []

    active_count = sum(
        1 for v in variants_by_id.values() if v.status.value == "active"
    )

    for a in proposed:
        if len(allowed) >= cfg["max_actions_per_tick"]:
            rejected.append(f"{a.type.value}: per-tick cap reached")
            continue

        if a.type == ActionType.KILL:
            v = variants_by_id.get(a.variant_id)
            if v is None:
                rejected.append("KILL: unknown variant")
                continue
            age = current_tick - int(v.spec.get("launched_at_tick", current_tick))
            if age < cfg["min_age_before_kill"]:
                rejected.append(
                    f"KILL variant {a.variant_id}: age {age} < min {cfg['min_age_before_kill']}"
                )
                continue

        elif a.type == ActionType.SCALE:
            v = variants_by_id.get(a.variant_id)
            if v is None:
                rejected.append("SCALE: unknown variant")
                continue
            factor = float(a.payload.get("factor", 1.5))
            projected = v.scale * factor
            if projected > cfg["max_variant_scale"]:
                cap_factor = cfg["max_variant_scale"] / v.scale if v.scale else 1.0
                if cap_factor <= 1.0:
                    rejected.append(
                        f"SCALE variant {a.variant_id}: at scale cap {cfg['max_variant_scale']}"
                    )
                    continue
                a.payload["factor"] = cap_factor
                a.payload["capped"] = True

        elif a.type == ActionType.LAUNCH:
            if active_count >= cfg["max_active_variants"]:
                rejected.append(
                    f"LAUNCH: active variant cap {cfg['max_active_variants']} reached"
                )
                continue
            active_count += 1

        allowed.append(a)

    return allowed, rejected
