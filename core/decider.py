from __future__ import annotations

import json
from typing import Any, Protocol

from .models import Action, ActionType, MetricSample, Variant


class Decider(Protocol):
    def decide(
        self,
        *,
        venture_id: int,
        tick: int,
        variants: list[Variant],
        metrics_by_variant: dict[int, list[MetricSample]],
        venture_config: dict[str, Any],
    ) -> tuple[list[Action], dict[str, Any]]:
        ...


def _avg(samples: list[MetricSample], name: str) -> float:
    vals = [s.value for s in samples if s.name == name]
    return sum(vals) / len(vals) if vals else 0.0


class StubDecider:
    """Deterministic heuristic decider used by tests and `--decider=stub`."""

    def decide(self, *, venture_id, tick, variants, metrics_by_variant, venture_config):
        actions: list[Action] = []
        per_variant: dict[int, dict[str, Any]] = {}

        kill_clicks = venture_config.get("kill_max_clicks_per_tick", 1.0)
        scale_min_mrr = venture_config.get("scale_min_mrr_delta", 5.0)
        min_age = venture_config.get("min_age_before_kill", 3)
        max_scale = venture_config.get("max_variant_scale", 4.0)
        window = venture_config.get("decision_window_ticks", 3)

        for v in variants:
            samples = metrics_by_variant.get(v.id, [])
            recent = [s for s in samples if s.tick > tick - window]
            avg_clicks = _avg(recent, "clicks")
            avg_mrr = _avg(recent, "mrr_delta")
            age = tick - int(v.spec.get("launched_at_tick", tick))
            per_variant[v.id] = {
                "age": age,
                "avg_clicks": round(avg_clicks, 3),
                "avg_mrr": round(avg_mrr, 3),
                "scale": v.scale,
            }

            if age >= min_age and avg_clicks < kill_clicks:
                actions.append(
                    Action(
                        id=None,
                        venture_id=venture_id,
                        variant_id=v.id,
                        type=ActionType.KILL,
                        payload={"reason": f"avg_clicks {avg_clicks:.2f} < {kill_clicks}"},
                        tick=tick,
                    )
                )
            elif avg_mrr >= scale_min_mrr and v.scale < max_scale:
                actions.append(
                    Action(
                        id=None,
                        venture_id=venture_id,
                        variant_id=v.id,
                        type=ActionType.SCALE,
                        payload={
                            "factor": 1.5,
                            "reason": f"avg_mrr {avg_mrr:.2f} >= {scale_min_mrr}",
                        },
                        tick=tick,
                    )
                )

        return actions, {"per_variant": per_variant}


SYSTEM_PROMPT = (
    "You are an autonomous business operator. You manage a portfolio of "
    "micro-SaaS tool pages and decide each tick which variants to KILL, SCALE, "
    "or MUTATE based on measured performance.\n\n"
    "Reply with strict JSON only:\n"
    '{"actions":[{"variant_id":<int>,"type":"kill|scale|mutate",'
    '"payload":{...}}], "summary":"<one sentence>"}\n'
    "- KILL: variant has no traction. Payload: {\"reason\":\"...\"}\n"
    "- SCALE: variant earns; expand its budget. Payload: {\"factor\":<1.1-2.0>,\"reason\":\"...\"}\n"
    "- MUTATE: tweak the spec. Payload: {\"changes\":{...},\"reason\":\"...\"}\n"
    "Be conservative — never propose more than 3 actions per tick."
)


class ClaudeDecider:
    """Live decider backed by Claude. SYSTEM prompt is cached across ticks."""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    def decide(self, *, venture_id, tick, variants, metrics_by_variant, venture_config):
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError("anthropic SDK not installed; pip install anthropic") from e

        client = Anthropic()
        recent: dict[int, list[dict[str, Any]]] = {}
        window = venture_config.get("decision_window_ticks", 3)
        for v in variants:
            recent[v.id] = [
                {"name": s.name, "value": s.value, "tick": s.tick}
                for s in metrics_by_variant.get(v.id, [])
                if s.tick > tick - window
            ]
        variants_block = [
            {"id": v.id, "spec": v.spec, "status": v.status.value, "scale": v.scale}
            for v in variants
        ]

        user = (
            f"TICK {tick}\n\n"
            f"VENTURE_CONFIG:\n{json.dumps(venture_config, sort_keys=True)}\n\n"
            f"VARIANTS:\n{json.dumps(variants_block, sort_keys=True)}\n\n"
            f"RECENT_METRICS:\n{json.dumps(recent, sort_keys=True)}\n\n"
            f"Return JSON."
        )

        msg = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))
        data = _extract_json(text)

        actions = []
        for a in data.get("actions", []):
            try:
                atype = ActionType(a["type"])
            except (KeyError, ValueError):
                continue
            actions.append(
                Action(
                    id=None,
                    venture_id=venture_id,
                    variant_id=a.get("variant_id"),
                    type=atype,
                    payload=a.get("payload", {}),
                    tick=tick,
                )
            )

        usage = getattr(msg, "usage", None)
        return actions, {
            "summary": data.get("summary", ""),
            "usage": usage.model_dump() if usage else None,
        }


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise ValueError(f"decider returned non-JSON: {text[:200]}")
