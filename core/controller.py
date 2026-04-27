from __future__ import annotations

from typing import Any

from channels.base import Channel
from ventures.microsaas import generator as microsaas_gen

from .decider import Decider
from .models import (
    Action,
    ActionType,
    Decision,
    MetricSample,
    Variant,
    VariantStatus,
)
from .policy import filter_actions
from .store import Store


class Controller:
    def __init__(
        self,
        store: Store,
        decider: Decider,
        channels: list[Channel],
        dry_run: bool = False,
    ):
        self.store = store
        self.decider = decider
        self.channels = channels
        self.dry_run = dry_run

    def tick(self, venture_id: int, current_tick: int) -> dict[str, Any]:
        venture = self.store.get_venture(venture_id)
        if venture is None:
            raise ValueError(f"unknown venture {venture_id}")
        active_variants = self.store.list_variants(
            venture_id, status=VariantStatus.ACTIVE
        )

        all_samples: list[MetricSample] = []
        for v in active_variants:
            for ch in self.channels:
                all_samples.extend(ch.fetch_metrics(v, current_tick))
        if not self.dry_run:
            self.store.add_metrics(all_samples)

        window = int(venture.config.get("decision_window_ticks", 3))
        metrics_by_variant: dict[int, list[MetricSample]] = {}
        for v in active_variants:
            if self.dry_run:
                metrics_by_variant[v.id] = [s for s in all_samples if s.variant_id == v.id]
            else:
                metrics_by_variant[v.id] = self.store.metrics_for_variant(
                    v.id, since_tick=max(0, current_tick - window + 1)
                )

        proposed, decider_ctx = self.decider.decide(
            venture_id=venture_id,
            tick=current_tick,
            variants=active_variants,
            metrics_by_variant=metrics_by_variant,
            venture_config=venture.config,
        )

        variants_by_id = {v.id: v for v in active_variants}
        allowed, rejected = filter_actions(
            proposed, variants_by_id, venture.config, current_tick
        )

        applied: list[Action] = []
        for a in allowed:
            self._apply(a, variants_by_id)
            a.applied = True
            applied.append(a)

        if not self.dry_run:
            self.store.add_decision(
                Decision(
                    id=None,
                    venture_id=venture_id,
                    tick=current_tick,
                    context={"decider": decider_ctx, "rejected": rejected},
                    actions=applied,
                )
            )

        return {
            "tick": current_tick,
            "venture_id": venture_id,
            "active_variants": len(active_variants),
            "metrics_collected": len(all_samples),
            "proposed": len(proposed),
            "rejected": len(rejected),
            "applied": len(applied),
            "actions": [(a.type.value, a.variant_id, a.payload.get("reason"))
                        for a in applied],
            "rejection_reasons": rejected,
        }

    def launch(self, venture_id: int, spec: dict[str, Any], at_tick: int = 0) -> Variant:
        rendered = microsaas_gen.render(spec)
        rendered["launched_at_tick"] = at_tick
        variant = Variant(id=None, venture_id=venture_id, spec=rendered)
        if not self.dry_run:
            variant = self.store.add_variant(variant)
        for ch in self.channels:
            ext = ch.publish(variant)
            variant.external_ids[ch.name] = ext
        if not self.dry_run:
            self.store.update_variant(variant)
        return variant

    def _apply(self, action: Action, variants_by_id: dict[int, Variant]) -> None:
        if action.type == ActionType.KILL:
            v = variants_by_id.get(action.variant_id)
            if v is None:
                return
            v.status = VariantStatus.KILLED
            v.scale = 0.0
            for ch in self.channels:
                ch.unpublish(v)
            if not self.dry_run:
                self.store.update_variant(v)

        elif action.type == ActionType.SCALE:
            v = variants_by_id.get(action.variant_id)
            if v is None:
                return
            factor = float(action.payload.get("factor", 1.5))
            v.scale = v.scale * factor
            if not self.dry_run:
                self.store.update_variant(v)

        elif action.type == ActionType.MUTATE:
            v = variants_by_id.get(action.variant_id)
            if v is None:
                return
            changes = action.payload.get("changes", {})
            v.spec = microsaas_gen.mutate(v.spec, changes)
            for ch in self.channels:
                ch.publish(v)
            if not self.dry_run:
                self.store.update_variant(v)

        elif action.type == ActionType.LAUNCH:
            spec = action.payload.get("spec")
            if spec is None:
                return
            self.launch(action.venture_id, spec, at_tick=action.tick)
