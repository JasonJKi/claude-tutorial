from __future__ import annotations

from pathlib import Path

from core.models import (
    Action,
    ActionType,
    Decision,
    MetricSample,
    Variant,
    VariantStatus,
    Venture,
)
from core.store import Store


def _store(tmp_path: Path) -> Store:
    return Store(tmp_path / "state.db")


def test_venture_crud(tmp_path: Path) -> None:
    s = _store(tmp_path)
    v = s.add_venture(Venture(id=None, name="microsaas-demo", vertical="microsaas",
                              config={"budget": 100}))
    assert v.id is not None
    fetched = s.get_venture(v.id)
    assert fetched is not None
    assert fetched.name == "microsaas-demo"
    assert fetched.config == {"budget": 100}

    inactive = s.add_venture(Venture(id=None, name="paused", vertical="microsaas",
                                     active=False))
    actives = s.list_ventures(active_only=True)
    assert [x.id for x in actives] == [v.id]
    all_ = s.list_ventures(active_only=False)
    assert {x.id for x in all_} == {v.id, inactive.id}


def test_variant_crud_and_status_filter(tmp_path: Path) -> None:
    s = _store(tmp_path)
    venture = s.add_venture(Venture(id=None, name="v1", vertical="microsaas"))
    a = s.add_variant(Variant(id=None, venture_id=venture.id, spec={"slug": "a"}))
    b = s.add_variant(Variant(id=None, venture_id=venture.id, spec={"slug": "b"}))

    b.status = VariantStatus.KILLED
    b.external_ids = {"seo": "page-b"}
    b.scale = 0.0
    s.update_variant(b)

    actives = s.list_variants(venture.id, status=VariantStatus.ACTIVE)
    killed = s.list_variants(venture.id, status=VariantStatus.KILLED)
    assert [x.id for x in actives] == [a.id]
    assert [x.id for x in killed] == [b.id]

    refetched = s.get_variant(b.id)
    assert refetched is not None
    assert refetched.status == VariantStatus.KILLED
    assert refetched.external_ids == {"seo": "page-b"}
    assert refetched.scale == 0.0


def test_metrics_window(tmp_path: Path) -> None:
    s = _store(tmp_path)
    venture = s.add_venture(Venture(id=None, name="v1", vertical="microsaas"))
    variant = s.add_variant(Variant(id=None, venture_id=venture.id, spec={"slug": "x"}))

    samples = [
        MetricSample(id=None, variant_id=variant.id, channel="seo",
                     name="impressions", value=10.0, tick=t)
        for t in range(5)
    ]
    s.add_metrics(samples)

    all_metrics = s.metrics_for_variant(variant.id)
    assert len(all_metrics) == 5
    recent = s.metrics_for_variant(variant.id, since_tick=3)
    assert [m.tick for m in recent] == [3, 4]


def test_decision_persists_actions(tmp_path: Path) -> None:
    s = _store(tmp_path)
    venture = s.add_venture(Venture(id=None, name="v1", vertical="microsaas"))
    variant = s.add_variant(Variant(id=None, venture_id=venture.id, spec={"slug": "x"}))

    actions = [
        Action(id=None, venture_id=venture.id, variant_id=variant.id,
               type=ActionType.SCALE, payload={"factor": 2.0}, tick=1),
        Action(id=None, venture_id=venture.id, variant_id=None,
               type=ActionType.LAUNCH, payload={"spec": {"slug": "new"}}, tick=1),
    ]
    decision = Decision(id=None, venture_id=venture.id, tick=1,
                        context={"summary": "test"}, actions=actions)
    saved = s.add_decision(decision)
    assert saved.id is not None
    assert all(a.id is not None for a in saved.actions)

    persisted = s.list_actions(venture.id)
    assert len(persisted) == 2
    assert {a.type for a in persisted} == {ActionType.SCALE, ActionType.LAUNCH}

    s.mark_action_applied(persisted[0].id)
    assert s.list_actions(venture.id)[0].applied is True
