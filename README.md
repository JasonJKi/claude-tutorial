# claude-tutorial — AI-managed venture controller (MVP)

A small simulation harness for running an AI-driven business loop end-to-end:

> **product → exposure → funnel → payment → measurement → decide → repeat**

The first venture is a **programmatic-SEO micro-SaaS factory** (single-purpose
tool pages with a Stripe paywall). Real third-party services are stubbed out
behind a `Channel` interface so the loop can be developed and tested without
touching real money or real ad accounts.

## Quick start

```bash
pip install pytest                   # for running tests
# (optional, only for --decider claude)
pip install anthropic
export ANTHROPIC_API_KEY=...

# Reset the DB and run 20 ticks of the deterministic stub decider.
python -m bin.tick --reset --seed 42 --decider stub --ticks 20

# Run another 5 ticks against the same DB.
python -m bin.tick --ticks 5

# Dry run — print proposed actions without persisting.
python -m bin.tick --dry-run --ticks 1
```

Sample output:

```
tick=  1  active= 3  metrics= 27  proposed=1  applied=1  rejected=0  actions=[scale#1]
tick=  3  active= 3  metrics= 27  proposed=2  applied=2  rejected=0  actions=[scale#1; kill#3]
tick= 11  active= 2  metrics= 18  proposed=1  applied=1  rejected=0  actions=[scale#2]
```

The strong tool gets scaled up (capped at 4×), the weak tool gets killed at
tick 3, and the borderline tool eventually accumulates enough revenue to
scale around tick 11.

## Layout

```
core/        # harness: models, store, controller, decider, policy
channels/    # mock Channel adapters (SEO, analytics, Stripe, deploy)
ventures/    # one vertical (microsaas) — generator + seed specs
bin/         # tick.py CLI entry point
tests/       # pytest suite
data/        # SQLite state db (gitignored)
_site/       # generated tool HTML (gitignored)
```

## Tests

```bash
python -m pytest -q
```

## Inspecting state

```bash
sqlite3 data/state.db "SELECT id, type, variant_id, payload FROM actions ORDER BY id;"
sqlite3 data/state.db "SELECT variant_id, name, value, tick FROM metrics WHERE name='mrr_delta' ORDER BY tick;"
```

## What's mocked vs. real

| Layer | Today | Real swap-in |
|-------|-------|--------------|
| Decider | `StubDecider` heuristic; `ClaudeDecider` (Anthropic SDK) | same |
| SEO channel | seeded simulation | Google Search Console API |
| Analytics | seeded simulation | Plausible / PostHog |
| Stripe | seeded simulation | Stripe API |
| Deploy | writes HTML to `_site/` | Cloudflare Pages / Vercel |

Swapping in a real channel is a drop-in: implement `Channel.publish`,
`Channel.unpublish`, `Channel.fetch_metrics` and register it in `bin/tick.py`.
