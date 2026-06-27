"""
ScheduledPolicies — Tier 3 feature.

Allows users to define per-cache cleanup schedules (weekly / monthly / never).
Policies are stored in the DB. On startup (and on manual trigger), the
policy engine checks which policies are due and queues the appropriate items
for dry-run confirmation before any actual cleanup runs.

Safety requirements (from spec):
- User approval always required — engine only *proposes*, never auto-deletes
- Safety checks (dry-run) run before confirmation dialog is shown
- Dry-run support — can simulate without touching files
- DANGER items can never have a policy applied
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from app.database.db import get_connection


# ── DB helpers ────────────────────────────────────────────────────────────────

def init_policy_table():
    """Idempotent — safe to call multiple times. Also called from init_db()."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cleanup_policies (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_id     TEXT    NOT NULL UNIQUE,
                cache_name   TEXT    NOT NULL,
                frequency    TEXT    NOT NULL,
                last_run     TEXT,
                enabled      INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_cleanup_policies_cache_id
                ON cleanup_policies(cache_id);
        """)


def get_all_policies() -> list:
    init_policy_table()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM cleanup_policies ORDER BY cache_name"
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_policy(cache_id: str, cache_name: str, frequency: str):
    """Set or update a policy for a cache item."""
    init_policy_table()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO cleanup_policies (cache_id, cache_name, frequency)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_id) DO UPDATE SET
                cache_name = excluded.cache_name,
                frequency  = excluded.frequency,
                enabled    = 1
        """, (cache_id, cache_name, frequency))


def delete_policy(cache_id: str):
    init_policy_table()
    with get_connection() as conn:
        conn.execute("DELETE FROM cleanup_policies WHERE cache_id = ?", (cache_id,))


def mark_policy_run(cache_id: str):
    """Record that a policy-triggered clean just completed."""
    init_policy_table()
    with get_connection() as conn:
        conn.execute(
            "UPDATE cleanup_policies SET last_run = ? WHERE cache_id = ?",
            (datetime.now().isoformat(), cache_id)
        )


def get_due_policies() -> list:
    """
    Return policies that are due for a run based on their frequency
    and last_run timestamp.
    """
    init_policy_table()
    now = datetime.now()
    due = []
    for policy in get_all_policies():
        if not policy["enabled"] or policy["frequency"] == "never":
            continue
        last = policy.get("last_run")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if policy["frequency"] == "weekly":
                    next_run = last_dt + timedelta(weeks=1)
                elif policy["frequency"] == "monthly":
                    next_run = last_dt + timedelta(days=30)
                else:
                    continue
                if now < next_run:
                    continue
            except Exception:
                pass  # malformed date — treat as never run, so it's due
        due.append(policy)
    return due
