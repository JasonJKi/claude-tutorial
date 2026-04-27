from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on the path when invoked as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from channels.mock_analytics import MockAnalyticsChannel  # noqa: E402
from channels.mock_deploy import MockDeployChannel  # noqa: E402
from channels.mock_seo import MockSEOChannel  # noqa: E402
from channels.mock_stripe import MockStripeChannel  # noqa: E402
from core.controller import Controller  # noqa: E402
from core.decider import ClaudeDecider, StubDecider  # noqa: E402
from core.models import Venture, VariantStatus  # noqa: E402
from core.store import Store  # noqa: E402
from ventures.microsaas import generator as microsaas_gen  # noqa: E402
from ventures.microsaas.policy import venture_defaults  # noqa: E402


VENTURE_NAME = "microsaas-demo"


def build_channels(seed: int, site_dir: Path) -> list:
    return [
        MockSEOChannel(seed=seed),
        MockAnalyticsChannel(seed=seed),
        MockStripeChannel(seed=seed),
        MockDeployChannel(site_dir=site_dir),
    ]


def reset_state(db_path: Path, site_dir: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    if site_dir.exists():
        for p in site_dir.glob("*.html"):
            p.unlink()


def seed_venture(controller: Controller, store: Store) -> int:
    venture = store.add_venture(
        Venture(
            id=None,
            name=VENTURE_NAME,
            vertical="microsaas",
            config=venture_defaults(),
        )
    )
    for spec in microsaas_gen.load_seed_specs():
        controller.launch(venture.id, spec, at_tick=0)
    return venture.id


def find_or_seed_venture(controller: Controller, store: Store) -> int:
    for v in store.list_ventures():
        if v.name == VENTURE_NAME:
            return v.id
    return seed_venture(controller, store)


def format_tick_summary(s: dict) -> str:
    head = (
        f"tick={s['tick']:>3}  active={s['active_variants']:>2}  "
        f"metrics={s['metrics_collected']:>3}  "
        f"proposed={s['proposed']}  applied={s['applied']}  rejected={s['rejected']}"
    )
    actions = "; ".join(f"{t}#{vid}" for t, vid, _ in s["actions"]) or "—"
    return f"{head}  actions=[{actions}]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AI venture controller loop.")
    parser.add_argument("--ticks", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for mock channels")
    parser.add_argument("--decider", choices=("stub", "claude"), default="stub")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without persisting metrics, decisions, or variant updates")
    parser.add_argument("--reset", action="store_true",
                        help="Drop the DB and re-seed before running")
    parser.add_argument("--db", type=Path, default=Path("data/state.db"))
    parser.add_argument("--site-dir", type=Path, default=Path("_site"))
    args = parser.parse_args(argv)

    if args.reset:
        reset_state(args.db, args.site_dir)

    store = Store(args.db)
    decider = StubDecider() if args.decider == "stub" else ClaudeDecider()
    channels = build_channels(args.seed, args.site_dir)
    controller = Controller(store, decider, channels, dry_run=args.dry_run)

    venture_id = find_or_seed_venture(controller, store)

    # Find the next tick number based on existing metrics, so reruns continue.
    start_tick = 1
    for v in store.list_variants(venture_id):
        for s in store.metrics_for_variant(v.id):
            start_tick = max(start_tick, s.tick + 1)

    for n in range(args.ticks):
        summary = controller.tick(venture_id, start_tick + n)
        print(format_tick_summary(summary))

    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
