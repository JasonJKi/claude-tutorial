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


def test_strong_scales_weak_dies_over_20_ticks(tmp_path: Path) -> None:
    store = Store(tmp_path / "state.db")
    channels = [
        MockSEOChannel(seed=42),
        MockAnalyticsChannel(seed=42),
        MockStripeChannel(seed=42),
        MockDeployChannel(site_dir=tmp_path / "_site"),
    ]
    controller = Controller(store, StubDecider(), channels)

    venture = store.add_venture(
        Venture(id=None, name="e2e", vertical="microsaas", config=venture_defaults())
    )
    launched = {}
    for spec in microsaas_gen.load_seed_specs():
        v = controller.launch(venture.id, spec, at_tick=0)
        launched[spec["slug"]] = v.id

    for tick in range(1, 21):
        controller.tick(venture.id, tick)

    strong = store.get_variant(launched["json-to-csv"])
    borderline = store.get_variant(launched["regex-explainer"])
    weak = store.get_variant(launched["yaml-prettifier"])

    assert strong.status == VariantStatus.ACTIVE
    assert strong.scale >= 3.0, f"expected strong variant scaled up, got {strong.scale}"

    assert weak.status == VariantStatus.KILLED, "expected weak variant killed"

    # Borderline should still be alive after 20 ticks (its age boost saves it).
    assert borderline.status == VariantStatus.ACTIVE


def test_kill_unpublishes_from_deploy_channel(tmp_path: Path) -> None:
    site_dir = tmp_path / "_site"
    store = Store(tmp_path / "state.db")
    channels = [
        MockSEOChannel(seed=1),
        MockAnalyticsChannel(seed=1),
        MockStripeChannel(seed=1),
        MockDeployChannel(site_dir=site_dir),
    ]
    controller = Controller(store, StubDecider(), channels)
    venture = store.add_venture(
        Venture(id=None, name="t", vertical="microsaas", config=venture_defaults())
    )
    weak_spec = next(
        s for s in microsaas_gen.load_seed_specs() if s["slug"] == "yaml-prettifier"
    )
    controller.launch(venture.id, weak_spec, at_tick=0)
    assert (site_dir / "yaml-prettifier.html").exists()

    for tick in range(1, 6):
        controller.tick(venture.id, tick)

    assert not (site_dir / "yaml-prettifier.html").exists()


def test_simulation_is_deterministic_for_seed(tmp_path: Path) -> None:
    def run(db_dir: Path) -> list[tuple[str, int]]:
        store = Store(db_dir / "state.db")
        channels = [
            MockSEOChannel(seed=99),
            MockAnalyticsChannel(seed=99),
            MockStripeChannel(seed=99),
            MockDeployChannel(site_dir=db_dir / "_site"),
        ]
        controller = Controller(store, StubDecider(), channels)
        venture = store.add_venture(
            Venture(id=None, name="d", vertical="microsaas", config=venture_defaults())
        )
        for spec in microsaas_gen.load_seed_specs():
            controller.launch(venture.id, spec, at_tick=0)
        for tick in range(1, 11):
            controller.tick(venture.id, tick)
        return [(a.type.value, a.variant_id) for a in store.list_actions(venture.id)]

    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    assert run(a_dir) == run(b_dir)
