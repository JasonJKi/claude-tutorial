from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} — {target_query}</title>
<meta name="description" content="{description}">
</head>
<body>
<h1>{title}</h1>
<p>{description}</p>
<section id="tool"></section>
<aside id="paywall" data-aggressiveness="{paywall_aggressiveness}">
  Free for {free_tier_uses_per_day} uses/day. Upgrade for ${price_monthly}/mo.
</aside>
</body>
</html>
"""


REQUIRED_FIELDS = (
    "slug",
    "title",
    "target_query",
    "description",
    "intrinsic_quality",
    "paywall_aggressiveness",
    "free_tier_uses_per_day",
    "price_monthly",
)


def render(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate a tool spec and return it with the rendered `html` field populated."""
    missing = [f for f in REQUIRED_FIELDS if f not in spec]
    if missing:
        raise ValueError(f"spec missing required fields: {missing}")
    out = dict(spec)
    out["html"] = HTML_TEMPLATE.format(**spec)
    return out


def mutate(spec: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial change set to a spec and re-render."""
    merged = {**spec, **changes}
    return render(merged)


def load_seed_specs(specs_dir: str | Path | None = None) -> list[dict[str, Any]]:
    if specs_dir is None:
        specs_dir = Path(__file__).parent / "specs"
    specs_dir = Path(specs_dir)
    out = []
    for path in sorted(specs_dir.glob("*.json")):
        with path.open() as f:
            out.append(render(json.load(f)))
    return out
