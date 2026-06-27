"""
app/database/db.py  (v5)

Changes from v4
---------------
* scan_history now stores duration_seconds and scan_id for trend tracking
* get_scan_trend() — last-N scans for dashboard trend chart
* get_cleanup_stats() added (was missing from exports in v4)
* WAL + synchronous=NORMAL retained
* All connections use check_same_thread=False (safe with WAL)
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional


DB_PATH = Path.home() / ".devcache_guardian" / "guardian.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


_SCHEMA_VERSION = 2   # Increment when schema changes


def _get_schema_version(conn) -> int:
    try:
        row = conn.execute(
            "SELECT value FROM preferences WHERE key='schema_version'"
        ).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def _set_schema_version(conn, version: int):
    conn.execute(
        "INSERT OR REPLACE INTO preferences (key, value) VALUES ('schema_version', ?)",
        (str(version),)
    )


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_at       TEXT    NOT NULL,
                total_bytes      INTEGER DEFAULT 0,
                item_count       INTEGER DEFAULT 0,
                duration_seconds REAL    DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS cleanup_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                cleaned_at      TEXT    NOT NULL,
                cache_id        TEXT    NOT NULL,
                cache_name      TEXT    NOT NULL,
                bytes_reclaimed INTEGER DEFAULT 0,
                method          TEXT,
                command         TEXT,
                success         INTEGER DEFAULT 1,
                error_message   TEXT
            );

            CREATE TABLE IF NOT EXISTS ignored_paths (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                path     TEXT UNIQUE NOT NULL,
                added_at TEXT        NOT NULL,
                reason   TEXT
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            -- scan_item_snapshots for growth-delta tracking
            CREATE TABLE IF NOT EXISTS scan_item_snapshots (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id    INTEGER NOT NULL,
                cache_id   TEXT    NOT NULL,
                cache_name TEXT    NOT NULL,
                ecosystem  TEXT,
                size_bytes INTEGER DEFAULT 0
            );

            -- Indexes for all hot query paths
            CREATE INDEX IF NOT EXISTS idx_scan_history_scanned_at
                ON scan_history(scanned_at DESC);

            CREATE INDEX IF NOT EXISTS idx_cleanup_history_cleaned_at
                ON cleanup_history(cleaned_at DESC);

            CREATE INDEX IF NOT EXISTS idx_cleanup_history_cache_id
                ON cleanup_history(cache_id);

            CREATE INDEX IF NOT EXISTS idx_scan_item_snapshots_scan_id
                ON scan_item_snapshots(scan_id);

            CREATE INDEX IF NOT EXISTS idx_scan_item_snapshots_cache_id
                ON scan_item_snapshots(cache_id);
        """)
        # Migrate: add duration_seconds if upgrading from older schema
        try:
            conn.execute("ALTER TABLE scan_history ADD COLUMN duration_seconds REAL DEFAULT 0")
        except Exception:
            pass  # column already exists

        defaults = {
            "scan_on_startup":           "true",
            "scheduled_scan":            "false",
            "size_warning_threshold_gb": "5",
            "theme":                     "system",
            "window_geometry":           "",
            "show_status_bar":           "true",
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO preferences (key, value) VALUES (?,?)", (k, v)
            )

        # ── Schema version migrations ─────────────────────────────────────────
        ver = _get_schema_version(conn)

        if ver < 2:
            # v2: backup history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backup_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    backed_up_at TEXT   NOT NULL,
                    cache_name  TEXT    NOT NULL,
                    cache_path  TEXT    NOT NULL,
                    backup_dir  TEXT    NOT NULL,
                    file_count  INTEGER DEFAULT 0,
                    trigger     TEXT    DEFAULT 'manual'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_backup_history_backed_up_at
                    ON backup_history(backed_up_at DESC)
            """)
            _set_schema_version(conn, 2)

    # Ensure policy table exists (deferred import avoids circular dependency)
    try:
        from app.database.policies import init_policy_table
        init_policy_table()
    except Exception:
        pass


# ── scan history ──────────────────────────────────────────────────────────────

def log_scan(total_bytes: int, item_count: int, duration_seconds: float = 0.0):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO scan_history (scanned_at, total_bytes, item_count, duration_seconds)"
            " VALUES (?,?,?,?)",
            (datetime.now().isoformat(), total_bytes, item_count, duration_seconds),
        )
    # Prune old data to prevent unbounded DB growth (non-blocking; runs after commit)
    try:
        prune_old_snapshots()
    except Exception:
        pass


def get_last_scan() -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scan_history ORDER BY scanned_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_scan_trend(limit: int = 14) -> list:
    """Return last N scan records for the trend chart (oldest first)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scan_history ORDER BY scanned_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


# ── cleanup history ───────────────────────────────────────────────────────────

def log_cleanup(cache_id: str, cache_name: str, bytes_reclaimed: int,
                method: str, command: Optional[str], success: bool,
                error: Optional[str] = None):
    method_clean = method.replace("CleanupMethod.", "").lower() if method else ""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO cleanup_history
               (cleaned_at, cache_id, cache_name, bytes_reclaimed,
                method, command, success, error_message)
               VALUES (?,?,?,?,?,?,?,?)""",
            (datetime.now().isoformat(), cache_id, cache_name,
             bytes_reclaimed, method_clean, command,
             1 if success else 0, error),
        )


def get_cleanup_history(limit: int = 100) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM cleanup_history ORDER BY cleaned_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_cleanup_stats() -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) AS ops,
                   SUM(CASE WHEN success=1 THEN bytes_reclaimed ELSE 0 END) AS total_bytes,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok
               FROM cleanup_history"""
        ).fetchone()
        return dict(row) if row else {"ops": 0, "total_bytes": 0, "ok": 0}


# ── ignored paths ─────────────────────────────────────────────────────────────

def get_ignored_paths() -> List[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT path FROM ignored_paths").fetchall()
        return [r["path"] for r in rows]


def add_ignored_path(path: str, reason: str = ""):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO ignored_paths (path, added_at, reason) VALUES (?,?,?)",
            (path, datetime.now().isoformat(), reason),
        )


def remove_ignored_path(path: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM ignored_paths WHERE path = ?", (path,))


# ── preferences ───────────────────────────────────────────────────────────────

def get_preference(key: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_preference(key: str, value: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?,?)", (key, value)
        )


# ── scan item snapshots (for growth monitoring) ───────────────────────────────

def log_scan_items(scan_id: int, items: list):
    """
    Persist per-item sizes alongside each scan so we can compute growth deltas.
    items: list of dicts with keys: cache_id, cache_name, ecosystem, size_bytes

    Table and indexes are created in init_db(); this function only inserts rows.
    """
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO scan_item_snapshots (scan_id, cache_id, cache_name, ecosystem, size_bytes)"
            " VALUES (?,?,?,?,?)",
            [(scan_id, i["cache_id"], i["cache_name"], i.get("ecosystem",""), i["size_bytes"])
             for i in items]
        )


def get_last_scan_id() -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM scan_history ORDER BY scanned_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None


def prune_old_snapshots(keep_days: int = 90):
    """
    Remove scan_item_snapshots for scans older than `keep_days` days.
    Prevents unbounded database growth on machines that scan daily.
    Called automatically after each scan log.
    """
    with get_connection() as conn:
        try:
            conn.execute("""
                DELETE FROM scan_item_snapshots
                WHERE scan_id IN (
                    SELECT id FROM scan_history
                    WHERE scanned_at < datetime('now', ?)
                )
            """, (f"-{keep_days} days",))
            # Also prune orphaned scan_history rows beyond 90 days
            conn.execute(
                "DELETE FROM scan_history WHERE scanned_at < datetime('now', ?)",
                (f"-{keep_days} days",)
            )
        except Exception:
            pass  # Non-critical — data stays but doesn't grow critically


def get_growth_deltas() -> list:
    """
    Compare the two most recent scans and return per-item growth.
    Returns list of dicts: {cache_id, cache_name, ecosystem,
                             prev_bytes, curr_bytes, delta_bytes}
    Positive delta = grew, negative = shrank/cleaned.
    """
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT id FROM scan_history ORDER BY scanned_at DESC LIMIT 2"
            ).fetchall()
            if len(rows) < 2:
                return []
            curr_id, prev_id = rows[0]["id"], rows[1]["id"]

            results = conn.execute("""
                SELECT
                    c.cache_id,
                    c.cache_name,
                    c.ecosystem,
                    COALESCE(p.size_bytes, 0) AS prev_bytes,
                    c.size_bytes              AS curr_bytes,
                    c.size_bytes - COALESCE(p.size_bytes, 0) AS delta_bytes
                FROM scan_item_snapshots c
                LEFT JOIN scan_item_snapshots p
                    ON p.cache_id = c.cache_id AND p.scan_id = ?
                WHERE c.scan_id = ?
                ORDER BY ABS(delta_bytes) DESC
            """, (prev_id, curr_id)).fetchall()
            return [dict(r) for r in results]
        except Exception:
            return []



# get_health_score has been moved to app.services.scoring (SRP: business logic
# does not belong in the database layer).  A thin shim is kept here so any
# import from app.database still works during the transition period.
def get_health_score(items: list) -> dict:  # pragma: no cover
    """Deprecated shim — import from app.services.scoring instead."""
    from app.services.scoring import get_health_score as _real
    return _real(items)


# ── backup history ─────────────────────────────────────────────────────────────

def log_backup(cache_name: str, cache_path: str, backup_dir: str,
               file_count: int, trigger: str = "pre_clean"):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO backup_history "
            "(backed_up_at, cache_name, cache_path, backup_dir, file_count, trigger)"
            " VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(), cache_name, cache_path,
             backup_dir, file_count, trigger),
        )


def get_backup_history(limit: int = 100) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM backup_history ORDER BY backed_up_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def wal_checkpoint():
    """Flush WAL to main DB file — call on application exit."""
    try:
        with get_connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass
