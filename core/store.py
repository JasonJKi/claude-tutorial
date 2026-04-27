from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .models import (
    Action,
    ActionType,
    Decision,
    MetricSample,
    Variant,
    VariantStatus,
    Venture,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS ventures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    vertical TEXT NOT NULL,
    config TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER NOT NULL REFERENCES ventures(id),
    spec TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    external_ids TEXT NOT NULL DEFAULT '{}',
    scale REAL NOT NULL DEFAULT 1.0
);

CREATE INDEX IF NOT EXISTS idx_variants_venture ON variants(venture_id, status);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL REFERENCES variants(id),
    channel TEXT NOT NULL,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    tick INTEGER NOT NULL,
    ts REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_variant ON metrics(variant_id, name, tick);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER NOT NULL REFERENCES ventures(id),
    variant_id INTEGER REFERENCES variants(id),
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    tick INTEGER NOT NULL,
    applied INTEGER NOT NULL DEFAULT 0,
    ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER NOT NULL REFERENCES ventures(id),
    tick INTEGER NOT NULL,
    context TEXT NOT NULL,
    ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_actions (
    decision_id INTEGER NOT NULL REFERENCES decisions(id),
    action_id INTEGER NOT NULL REFERENCES actions(id),
    PRIMARY KEY (decision_id, action_id)
);
"""


class Store:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add_venture(self, v: Venture) -> Venture:
        ts = v.created_at or time.time()
        cur = self._conn.execute(
            "INSERT INTO ventures (name, vertical, config, created_at, active) "
            "VALUES (?, ?, ?, ?, ?)",
            (v.name, v.vertical, json.dumps(v.config), ts, int(v.active)),
        )
        self._conn.commit()
        v.id = cur.lastrowid
        v.created_at = ts
        return v

    def get_venture(self, vid: int) -> Venture | None:
        row = self._conn.execute("SELECT * FROM ventures WHERE id = ?", (vid,)).fetchone()
        return _row_to_venture(row) if row else None

    def list_ventures(self, active_only: bool = True) -> list[Venture]:
        sql = "SELECT * FROM ventures"
        if active_only:
            sql += " WHERE active = 1"
        return [_row_to_venture(r) for r in self._conn.execute(sql)]

    def add_variant(self, v: Variant) -> Variant:
        ts = v.created_at or time.time()
        cur = self._conn.execute(
            "INSERT INTO variants (venture_id, spec, status, created_at, external_ids, scale) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                v.venture_id,
                json.dumps(v.spec),
                v.status.value,
                ts,
                json.dumps(v.external_ids),
                v.scale,
            ),
        )
        self._conn.commit()
        v.id = cur.lastrowid
        v.created_at = ts
        return v

    def get_variant(self, vid: int) -> Variant | None:
        row = self._conn.execute("SELECT * FROM variants WHERE id = ?", (vid,)).fetchone()
        return _row_to_variant(row) if row else None

    def list_variants(
        self, venture_id: int, status: VariantStatus | None = None
    ) -> list[Variant]:
        if status is None:
            rows = self._conn.execute(
                "SELECT * FROM variants WHERE venture_id = ? ORDER BY id",
                (venture_id,),
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM variants WHERE venture_id = ? AND status = ? ORDER BY id",
                (venture_id, status.value),
            )
        return [_row_to_variant(r) for r in rows]

    def update_variant(self, v: Variant) -> None:
        self._conn.execute(
            "UPDATE variants SET status = ?, external_ids = ?, scale = ? WHERE id = ?",
            (v.status.value, json.dumps(v.external_ids), v.scale, v.id),
        )
        self._conn.commit()

    def add_metrics(self, samples: list[MetricSample]) -> None:
        if not samples:
            return
        now = time.time()
        self._conn.executemany(
            "INSERT INTO metrics (variant_id, channel, name, value, tick, ts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (s.variant_id, s.channel, s.name, s.value, s.tick, s.ts or now)
                for s in samples
            ],
        )
        self._conn.commit()

    def metrics_for_variant(
        self, variant_id: int, since_tick: int | None = None
    ) -> list[MetricSample]:
        if since_tick is None:
            rows = self._conn.execute(
                "SELECT * FROM metrics WHERE variant_id = ? ORDER BY tick, id",
                (variant_id,),
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM metrics WHERE variant_id = ? AND tick >= ? ORDER BY tick, id",
                (variant_id, since_tick),
            )
        return [_row_to_metric(r) for r in rows]

    def add_action(self, a: Action) -> Action:
        ts = a.ts or time.time()
        cur = self._conn.execute(
            "INSERT INTO actions (venture_id, variant_id, type, payload, tick, applied, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                a.venture_id,
                a.variant_id,
                a.type.value,
                json.dumps(a.payload),
                a.tick,
                int(a.applied),
                ts,
            ),
        )
        self._conn.commit()
        a.id = cur.lastrowid
        a.ts = ts
        return a

    def mark_action_applied(self, action_id: int) -> None:
        self._conn.execute("UPDATE actions SET applied = 1 WHERE id = ?", (action_id,))
        self._conn.commit()

    def list_actions(self, venture_id: int | None = None) -> list[Action]:
        if venture_id is None:
            rows = self._conn.execute("SELECT * FROM actions ORDER BY id")
        else:
            rows = self._conn.execute(
                "SELECT * FROM actions WHERE venture_id = ? ORDER BY id",
                (venture_id,),
            )
        return [_row_to_action(r) for r in rows]

    def add_decision(self, d: Decision) -> Decision:
        ts = d.ts or time.time()
        cur = self._conn.execute(
            "INSERT INTO decisions (venture_id, tick, context, ts) VALUES (?, ?, ?, ?)",
            (d.venture_id, d.tick, json.dumps(d.context), ts),
        )
        d.id = cur.lastrowid
        d.ts = ts
        for a in d.actions:
            if a.id is None:
                self.add_action(a)
            self._conn.execute(
                "INSERT INTO decision_actions (decision_id, action_id) VALUES (?, ?)",
                (d.id, a.id),
            )
        self._conn.commit()
        return d


def _row_to_venture(r: sqlite3.Row) -> Venture:
    return Venture(
        id=r["id"],
        name=r["name"],
        vertical=r["vertical"],
        config=json.loads(r["config"]),
        created_at=r["created_at"],
        active=bool(r["active"]),
    )


def _row_to_variant(r: sqlite3.Row) -> Variant:
    return Variant(
        id=r["id"],
        venture_id=r["venture_id"],
        spec=json.loads(r["spec"]),
        status=VariantStatus(r["status"]),
        created_at=r["created_at"],
        external_ids=json.loads(r["external_ids"]),
        scale=r["scale"],
    )


def _row_to_metric(r: sqlite3.Row) -> MetricSample:
    return MetricSample(
        id=r["id"],
        variant_id=r["variant_id"],
        channel=r["channel"],
        name=r["name"],
        value=r["value"],
        tick=r["tick"],
        ts=r["ts"],
    )


def _row_to_action(r: sqlite3.Row) -> Action:
    return Action(
        id=r["id"],
        venture_id=r["venture_id"],
        variant_id=r["variant_id"],
        type=ActionType(r["type"]),
        payload=json.loads(r["payload"]),
        tick=r["tick"],
        applied=bool(r["applied"]),
        ts=r["ts"],
    )
