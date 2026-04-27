from __future__ import annotations

from pathlib import Path

from channels.mock_analytics import MockAnalyticsChannel
from channels.mock_deploy import MockDeployChannel
from channels.mock_seo import MockSEOChannel
from channels.mock_stripe import MockStripeChannel
from core.controller import Controller
from core.decider import StubDecider
from core.models import VariantStatus, Venture
from core.store import Store
from ventures.microsaas import generator as microsaas_gen
from ventures.microsaas.policy import venture_defaults


def _bootstrap(tmp_path: Path):
    store = Store(tmp_path / "state.db")
    channels = [
        MockSEOChannel(seed=42),
        MockAnalyticsChannel(seed=42),
        MockStripeChannel(seed=42),
        MockDeployChannel(site_dir=tmp_path / "_site"),
    ]
    decider = StubDecider()
    controller = Controller(store, decider, channels, dry_run=False)
    venture = store.add_venture(
        Venture(id=None, name="t", vertical="microsaas", config=venture_defaults())
    )
    for spec in microsaas_gen.load_seed_specs():
        controller.launch(venture.id, spec, at_tick=0)
    return store, controller, venture.id


def test_dry_run_persists_nothing(tmp_path: Path) -> None:
    store, controller, venture_id = _bootstrap(tmp_path)
    controller.dry_run = True

    summary = controller.tick(venture_id, current_tick=5)
    assert summary["metrics_collected"] > 0
    # No metrics or actions persisted in dry-run mode.
    for v in store.list_variants(venture_id):
        assert store.metrics_for_variant(v.id) == []
    assert store.list_actions(venture_id) == []


def test_min_age_blocks_early_kill(tmp_path: Path) -> None:
    _, controller, venture_id = _bootstrap(tmp_path)
    summary = controller.tick(venture_id, current_tick=1)
    # The weak variant has zero clicks but is age 1 — below min_age_before_kill (3).
    assert all(a[0] != "kill" for a in summary["actions"])


def test_real_run_persists_decision_and_actions(tmp_path: Path) -> None:
    store, controller, venture_id = _bootstrap(tmp_path)
    controller.tick(venture_id, current_tick=3)
    actions = store.list_actions(venture_id)
    # KILL on the weak variant should fire and be persisted as applied.
    kill_actions = [a for a in actions if a.type.value == "kill"]
    assert len(kill_actions) >= 1
    assert all(a.applied for a in kill_actions)
