from __future__ import annotations

from pathlib import Path

from core.models import MetricSample, Variant

from .base import Channel


class MockDeployChannel(Channel):
    """Writes the generated tool HTML to ./_site on publish; deletes on unpublish."""

    name = "deploy"

    def __init__(self, site_dir: str | Path = "_site"):
        self.site_dir = Path(site_dir)
        self.site_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, variant: Variant) -> Path:
        slug = variant.spec.get("slug", str(variant.id))
        return self.site_dir / f"{slug}.html"

    def publish(self, variant: Variant) -> str:
        html = variant.spec.get("html") or _fallback_html(variant)
        path = self._path_for(variant)
        path.write_text(html, encoding="utf-8")
        return str(path)

    def unpublish(self, variant: Variant) -> None:
        path = self._path_for(variant)
        if path.exists():
            path.unlink()

    def fetch_metrics(self, variant: Variant, tick: int) -> list[MetricSample]:
        # Deploy itself emits no marketing metrics; it's a publishing target.
        return []


def _fallback_html(variant: Variant) -> str:
    slug = variant.spec.get("slug", "tool")
    title = variant.spec.get("title", slug)
    return f"<!doctype html><title>{title}</title><h1>{title}</h1>"
