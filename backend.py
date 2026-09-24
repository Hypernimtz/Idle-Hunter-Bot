"""
backend.py — Persistence, locking, transaction helpers, typed models, and migration.

Deliberately imports nothing from bot.py, game_data.py, or discord so it can
be used in tests and analysis scripts without a running bot.
"""
from __future__ import annotations

import asyncio
import copy
import csv
import json
import logging
import os
import time
from contextlib import asynccontextmanager, AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Callable

logger = logging.getLogger(__name__)

DEGRADED_MODE = False

# Set once this process has lost (or never won) the single-instance lock. From
# then on our in-memory state is stale relative to whoever holds the lock, so
# every bulk write below becomes a no-op — otherwise the shutdown flush would
# overwrite the live instance's newer data with ours.
SAVES_DISABLED = False

def disable_saves() -> None:
    global SAVES_DISABLED
    SAVES_DISABLED = True

# backend.py - Add these imports at the top
import aiosqlite
from contextlib import asynccontextmanager
import json

# Replace the PostgreSQL/Redis section with SQLite:

_pool: Optional[aiosqlite.Connection] = None
_db_path = os.getenv("SQLITE_PATH", "idle_hunter.db")

async def init_databases():
    """Initialize SQLite database connection and create tables"""
    global _pool
    _pool = await aiosqlite.connect(_db_path)
    await _pool.execute("PRAGMA journal_mode=WAL")  # Better concurrency
    await _pool.execute("PRAGMA foreign_keys=ON")
    # WAL + NORMAL is the standard safe pairing (fsync only at checkpoints, still
    # crash-consistent); busy_timeout makes a briefly-locked DB wait, not error.
    await _pool.execute("PRAGMA synchronous=NORMAL")
    await _pool.execute("PRAGMA busy_timeout=5000")
    await init_schema()

async def backup_database(backup_dir: str | None = None, keep: int = 7) -> str | None:
    """Write a consistent snapshot of the live DB (VACUUM INTO — safe while the
    bot is running, unlike copying the file) and prune to the newest ``keep``.
    Returns the new backup's path, or None if there is no open DB."""
    if _pool is None:
        return None
    dest_dir = Path(backup_dir or os.getenv("BACKUP_DIR", "") or (Path(_db_path).resolve().parent / "backups"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"idle_hunter-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.db"
    await _pool.execute("VACUUM INTO ?", (str(dest),))
    old = sorted(dest_dir.glob("idle_hunter-*.db"))
    for f in old[:-keep] if keep > 0 else []:
        try:
            f.unlink()
        except OSError:
            pass
    return str(dest)

async def close_databases():
    """Close SQLite connection (idempotent)."""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        finally:
            _pool = None

async def init_schema():
    """Create all tables if they don't exist"""
    async with _pool.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,  -- JSON stored as TEXT
            username TEXT,
            level INTEGER DEFAULT 1,
            money INTEGER DEFAULT 0,
            prestige INTEGER DEFAULT 0,
            last_active TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """): pass
    
    await _pool.execute("""
        CREATE TABLE IF NOT EXISTS tribes (
            name TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            member_count INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    await _pool.execute("""
        CREATE TABLE IF NOT EXISTS economy_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            source TEXT NOT NULL,
            delta INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            currency TEXT DEFAULT 'money',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _pool.execute("""
        CREATE INDEX IF NOT EXISTS idx_economy_log_currency_created
        ON economy_log(currency, created_at)
    """)

    # Product analytics — funnel + retention events (Idle Hunter V2). Never
    # holds anything a player couldn't see about themselves; metadata is a small
    # JSON blob. Written through the buffered helpers further down this file.
    await _pool.execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            event TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Per-guild cooperative weekly goals (Idle Hunter V2, Phase 33-34). Kept in
    # SQLite rather than runtime_state.json so thousands of guilds scale.
    await _pool.execute("""
        CREATE TABLE IF NOT EXISTS guild_progress (
            guild_id TEXT PRIMARY KEY,
            week_tag TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            goal INTEGER DEFAULT 0,
            reward_sent INTEGER DEFAULT 0,
            data TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _pool.execute("""
        CREATE TABLE IF NOT EXISTS guild_contributions (
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            week_tag TEXT NOT NULL,
            contribution INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, week_tag)
        )
    """)

    # Referral program (Idle Hunter V2, Phase 35-39). A player has exactly one
    # referrer forever (referred_id PRIMARY KEY); the reward only fires once the
    # referred account actually plays (see qualification checks in app.py).
    await _pool.execute("""
        CREATE TABLE IF NOT EXISTS referral_codes (
            user_id TEXT UNIQUE NOT NULL,
            code TEXT PRIMARY KEY NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _pool.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referred_id TEXT PRIMARY KEY,
            referrer_id TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            qualified_at TEXT,
            reward_claimed INTEGER DEFAULT 0
        )
    """)

    # Single-row table used to enforce "only one live bot instance" (see
    # claim_instance_lock). Two instances on one token double every payout / DM.
    await _pool.execute("""
        CREATE TABLE IF NOT EXISTS bot_instance (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            instance_id TEXT NOT NULL,
            hostname    TEXT,
            pid         INTEGER,
            claimed_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            heartbeat   REAL NOT NULL
        )
    """)

    # Create indexes
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_users_level ON users(level DESC)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_users_money ON users(money DESC)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_users_prestige ON users(prestige DESC)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_tribes_level ON tribes(level DESC)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_analytics_event ON analytics_events(event, created_at)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_analytics_user ON analytics_events(user_id, created_at)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)")
    await _pool.commit()

# Upsert that keeps immutable columns (created_at, last_active) intact — plain
# INSERT OR REPLACE deletes + re-inserts the row, resetting those defaults.
_USER_UPSERT = """
    INSERT INTO users (user_id, data, username, level, money, prestige, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    ON CONFLICT(user_id) DO UPDATE SET
        data=excluded.data, username=excluded.username, level=excluded.level,
        money=excluded.money, prestige=excluded.prestige, updated_at=excluded.updated_at
"""

# Rows serialised + written per step. json.dumps of every player used to run in one
# uninterrupted burst on the event loop (and one giant commit on the single DB
# connection), stalling every click behind it. Chunking bounds each stall to a few
# ms and lets small saves (a form submit, a purchase) interleave with a full save.
_SAVE_CHUNK = 40

async def bulk_save_users(users: dict[str, dict]):
    """Save many users, a chunk at a time, yielding to the event loop between
    chunks. Each user is serialised atomically within one loop step, so every row
    is a consistent snapshot even though the whole save spans several steps."""
    if SAVES_DISABLED:
        return
    items = list(users.items())          # snapshot of membership; values read per chunk
    for start in range(0, len(items), _SAVE_CHUNK):
        rows = [
            (uid, json.dumps(data), data.get("username", ""),
             data.get("level", 1), data.get("money", 0), data.get("prestige", 0))
            for uid, data in items[start:start + _SAVE_CHUNK]
        ]
        await _pool.executemany(_USER_UPSERT, rows)
        await _pool.commit()
        if start + _SAVE_CHUNK < len(items):
            await asyncio.sleep(0)

async def delete_user(user_id: str) -> None:
    """Permanently remove a user row from SQLite."""
    await _pool.execute("DELETE FROM users WHERE user_id = ?", (str(user_id),))
    await _pool.commit()

_TRIBE_UPSERT = """
    INSERT INTO tribes (name, data, level, member_count, updated_at)
    VALUES (?, ?, ?, ?, datetime('now'))
    ON CONFLICT(name) DO UPDATE SET
        data=excluded.data, level=excluded.level,
        member_count=excluded.member_count, updated_at=excluded.updated_at
"""

def _tribe_row(name: str, data: dict) -> tuple:
    _r = data.get("roles", {})
    member_count = (1 + len(_r.get("officer", [])) + len(_r.get("members", []))
                    + len(_r.get("recruits", [])))
    return (name, json.dumps(data), data.get("level", 1), member_count)

_dirty_tribes: set[str] = set()
_dirty_all_tribes = False

def mark_tribes_dirty(*names: str) -> None:
    """Record which tribes a transaction touched so the flush rewrites only those.
    No names = "could have been any" -> the next flush writes every tribe."""
    global _dirty_all_tribes
    if names:
        _dirty_tribes.update(names)
    else:
        _dirty_all_tribes = True

def take_dirty_tribes() -> tuple[set[str], bool]:
    """Pop and return (dirty tribe names, all_dirty)."""
    global _dirty_all_tribes
    names, all_dirty = set(_dirty_tribes), _dirty_all_tribes
    _dirty_tribes.clear()
    _dirty_all_tribes = False
    return names, all_dirty

async def delete_tribe(name: str) -> None:
    """Remove a disbanded tribe's row — without this it reloaded from SQLite on the
    next restart, resurrecting a tribe whose leader had already left."""
    if SAVES_DISABLED:
        return
    await _pool.execute("DELETE FROM tribes WHERE name = ?", (name,))
    await _pool.commit()

async def bulk_save_tribes(tribes_dict: dict):
    """Bulk save multiple tribes — one executemany + one commit, mirroring
    bulk_save_users (a per-tribe save_tribe() loop committed once per tribe,
    which gets slow as the tribe count grows)."""
    if not tribes_dict or SAVES_DISABLED:
        return
    await _pool.executemany(_TRIBE_UPSERT, [
        _tribe_row(name, tribe_data) for name, tribe_data in tribes_dict.items()
    ])
    await _pool.commit()

# Simple cache helpers (replace Redis)
class SessionManager:
    """Simple in-memory session storage (or use dict with TTL)"""
    _sessions: dict[str, dict] = {}
    
    @staticmethod
    async def set(user_id: str, key: str, value: Any, ttl: int = 3600):
        SessionManager._sessions[f"{user_id}:{key}"] = {
            "value": value,
            "expires": time.time() + ttl
        }
    
    @staticmethod
    async def get(user_id: str, key: str) -> Any:
        data = SessionManager._sessions.get(f"{user_id}:{key}")
        if data and data["expires"] > time.time():
            return data["value"]
        SessionManager._sessions.pop(f"{user_id}:{key}", None)
        return None
    
    @staticmethod
    async def delete(user_id: str, key: str):
        SessionManager._sessions.pop(f"{user_id}:{key}", None)

class RateLimiter:
    """Simple in-memory rate limiting"""
    _hunt_cooldowns: dict[str, float] = {}
    _gamble_cooldowns: dict[str, float] = {}
    
    @staticmethod
    async def can_hunt(user_id: str, cooldown_seconds: int = 3) -> tuple[bool, float]:
        last = RateLimiter._hunt_cooldowns.get(user_id, 0)
        elapsed = time.time() - last
        if elapsed < cooldown_seconds:
            return False, cooldown_seconds - elapsed
        RateLimiter._hunt_cooldowns[user_id] = time.time()
        return True, 0
    
    @staticmethod
    async def can_gamble(user_id: str, cooldown_seconds: int = 0) -> tuple[bool, float]:
        if cooldown_seconds == 0:
            return True, 0
        last = RateLimiter._gamble_cooldowns.get(user_id, 0)
        elapsed = time.time() - last
        if elapsed < cooldown_seconds:
            return False, cooldown_seconds - elapsed
        RateLimiter._gamble_cooldowns[user_id] = time.time()
        return True, 0

# Economy log with SQLite (remove CSV file)
_economy_buffer = []
_BUFFER_SIZE = 100
_BUFFER_LOCK = asyncio.Lock()

async def log_economy_event_buffered(
    user_id: str,
    source: str,
    delta: int,
    balance_after: int,
    currency: str = "money"
):
    """Buffer economy events for batch writing"""
    if delta == 0:
        return

    to_write = None
    async with _BUFFER_LOCK:
        _economy_buffer.append({
            "user_id": user_id,
            "source": source,
            "delta": delta,
            "balance_after": balance_after,
            "currency": currency
        })
        if len(_economy_buffer) >= _BUFFER_SIZE:
            # Detach the batch while we still hold the lock, then write it OUTSIDE
            # the lock — calling flush_economy_buffer() here would re-acquire the
            # same non-reentrant lock and deadlock forever.
            to_write = _economy_buffer[:]
            _economy_buffer.clear()

    if to_write:
        await _write_economy_rows(to_write)

async def _write_economy_rows(rows: list) -> None:
    if not rows or _pool is None:
        return
    await _pool.executemany("""
        INSERT INTO economy_log (user_id, source, delta, balance_after, currency)
        VALUES (?, ?, ?, ?, ?)
    """, [(e["user_id"], e["source"], e["delta"], e["balance_after"], e["currency"]) for e in rows])
    await _pool.commit()

async def flush_economy_buffer():
    """Drain and persist whatever is currently buffered. Safe to call on its own
    (shutdown, periodic flush) — never from inside the buffer lock."""
    global _economy_buffer
    async with _BUFFER_LOCK:
        if not _economy_buffer:
            return
        buffer = _economy_buffer[:]
        _economy_buffer = []
    await _write_economy_rows(buffer)


async def economy_summary(currency: str = "money", top_n: int = 5) -> dict:
    """All-time and last-24h minted/burned totals for one currency, plus the
    top sources on each side (what's paying players, what's draining them).
    Flushes the in-memory buffer first so nothing recent is missing."""
    await flush_economy_buffer()
    if _pool is None:
        return {"minted_all": 0, "burned_all": 0, "minted_24h": 0, "burned_24h": 0,
                "top_earn": [], "top_spend": [], "last_event_at": None}
    async with _pool.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN delta > 0 THEN delta ELSE 0 END), 0),
             COALESCE(SUM(CASE WHEN delta < 0 THEN -delta ELSE 0 END), 0),
             COALESCE(SUM(CASE WHEN delta > 0 AND created_at >= datetime('now', '-1 day')
                          THEN delta ELSE 0 END), 0),
             COALESCE(SUM(CASE WHEN delta < 0 AND created_at >= datetime('now', '-1 day')
                          THEN -delta ELSE 0 END), 0),
             MAX(created_at)
           FROM economy_log WHERE currency = ?""",
        (currency,),
    ) as cur:
        minted_all, burned_all, minted_24h, burned_24h, last_event_at = await cur.fetchone()
    async with _pool.execute(
        """SELECT source, SUM(delta) FROM economy_log
           WHERE currency = ? AND delta > 0 GROUP BY source ORDER BY 2 DESC LIMIT ?""",
        (currency, top_n),
    ) as cur:
        top_earn = await cur.fetchall()
    async with _pool.execute(
        """SELECT source, -SUM(delta) FROM economy_log
           WHERE currency = ? AND delta < 0 GROUP BY source ORDER BY 2 DESC LIMIT ?""",
        (currency, top_n),
    ) as cur:
        top_spend = await cur.fetchall()
    return {
        "minted_all": minted_all, "burned_all": burned_all,
        "minted_24h": minted_24h, "burned_24h": burned_24h,
        "top_earn": list(top_earn), "top_spend": list(top_spend),
        "last_event_at": last_event_at,
    }


# ─────────────────────────────────────────────
# PRODUCT ANALYTICS  (funnel + retention events)
# ─────────────────────────────────────────────
# Same buffered fire-and-forget shape as the economy log. `log_analytics` is the
# sync entry point used from anywhere; the row is flushed on size, on the 20s
# autosave loop, and on shutdown. Nothing here is Discord-aware.

_analytics_buffer: list[dict] = []
_ANALYTICS_BUFFER_SIZE = 40
_ANALYTICS_LOCK = asyncio.Lock()


async def log_analytics_buffered(user_id, event: str, metadata: dict | None = None) -> None:
    to_write = None
    async with _ANALYTICS_LOCK:
        _analytics_buffer.append({
            "user_id": (str(user_id) if user_id is not None else None),
            "event": str(event)[:64],
            "metadata": (json.dumps(metadata, default=str)[:2000] if metadata else None),
        })
        if len(_analytics_buffer) >= _ANALYTICS_BUFFER_SIZE:
            to_write = _analytics_buffer[:]
            _analytics_buffer.clear()
    if to_write:
        await _write_analytics_rows(to_write)


async def _write_analytics_rows(rows: list) -> None:
    if not rows or _pool is None:
        return
    await _pool.executemany(
        "INSERT INTO analytics_events (user_id, event, metadata) VALUES (?, ?, ?)",
        [(e["user_id"], e["event"], e["metadata"]) for e in rows],
    )
    await _pool.commit()


async def flush_analytics_buffer() -> None:
    """Drain the analytics buffer. Safe to call standalone (autosave, shutdown)."""
    global _analytics_buffer
    async with _ANALYTICS_LOCK:
        if not _analytics_buffer:
            return
        buf = _analytics_buffer[:]
        _analytics_buffer = []
    await _write_analytics_rows(buf)


async def prune_analytics(days: int = 120) -> int:
    """Delete analytics rows older than `days`. Returns rows removed."""
    if _pool is None:
        return 0
    cur = await _pool.execute(
        "DELETE FROM analytics_events WHERE created_at < datetime('now', ?)",
        (f"-{int(days)} days",),
    )
    await _pool.commit()
    return cur.rowcount or 0


def log_analytics(user_id, event: str, metadata: dict | None = None) -> None:
    """Fire-and-forget analytics write. No-op when no event loop is running."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(log_analytics_buffered(user_id, event, metadata))
    except RuntimeError:
        pass


# ─────────────────────────────────────────────
# ANALYTICS / GUILD-GOAL / REFERRAL  read+write helpers
# ─────────────────────────────────────────────

async def analytics_counts(events: list[str], since_days: int = 7) -> dict[str, int]:
    """{event: distinct-user count in the window} — powers the admin funnel view."""
    if _pool is None or not events:
        return {}
    out: dict[str, int] = {}
    qs = ",".join("?" for _ in events)
    async with _pool.execute(
        f"""SELECT event, COUNT(DISTINCT COALESCE(user_id,'?')) FROM analytics_events
            WHERE event IN ({qs}) AND created_at >= datetime('now', ?)
            GROUP BY event""",
        (*events, f"-{int(since_days)} days"),
    ) as cur:
        for ev, n in await cur.fetchall():
            out[ev] = n
    return {e: out.get(e, 0) for e in events}


# Acquisition→retention funnel step definitions, in order. Each step counts a
# cohort member (a user_created in the window) who ever fired ANY of its
# events — not just within the window — so a step's number only grows as the
# cohort matures (e.g. day_7_return needs the account to be 7+ days old).
FUNNEL_STEPS: list[tuple[str, str, tuple[str, ...]]] = [
    ("new_players",        "New players",         ("user_created",)),
    ("started_onboarding", "Started onboarding",  ("onboarding_started",)),
    ("first_hunt",         "First hunt",          ("onboarding_first_track", "hunt")),
    ("first_sell",         "First sell",          ("onboarding_first_sell", "sell")),
    ("first_upgrade",      "First upgrade",       ("upgrade",)),
    ("ten_hunts",          "10 hunts",            ("hunts_10",)),
    ("day_1_return",       "Returned D1",         ("day_1_return",)),
    ("day_3_return",       "Returned D3",         ("day_3_return",)),
    ("day_7_return",       "Returned D7",         ("day_7_return",)),
]


async def funnel_report(since_days: int = 30) -> list[dict]:
    """Cohort funnel for players who joined in the last `since_days`: how many
    of them ever reached each later milestone. Powers the /funnel admin
    command. Returns FUNNEL_STEPS order as [{key, label, count}, ...]."""
    if _pool is None:
        return [{"key": k, "label": lbl, "count": 0} for k, lbl, _ in FUNNEL_STEPS]
    case_lines = []
    params: list = []
    for key, _label, events in FUNNEL_STEPS[1:]:
        qs = " OR ".join("ae.event = ?" for _ in events)
        case_lines.append(f"COUNT(DISTINCT CASE WHEN {qs} THEN ae.user_id END) AS {key}")
        params.extend(events)
    sql = f"""
        WITH cohort AS (
            SELECT DISTINCT user_id FROM analytics_events
            WHERE event = 'user_created' AND user_id IS NOT NULL
              AND created_at >= datetime('now', ?)
        )
        SELECT (SELECT COUNT(*) FROM cohort), {", ".join(case_lines)}
        FROM analytics_events ae
        JOIN cohort c ON c.user_id = ae.user_id
    """
    async with _pool.execute(sql, (f"-{int(since_days)} days", *params)) as cur:
        row = await cur.fetchone()
    counts = [row[0] if row else 0] + (list(row[1:]) if row else [0] * (len(FUNNEL_STEPS) - 1))
    return [{"key": k, "label": lbl, "count": int(c or 0)}
            for (k, lbl, _), c in zip(FUNNEL_STEPS, counts)]


async def guild_goal_get(guild_id: str) -> dict | None:
    if _pool is None:
        return None
    async with _pool.execute(
        "SELECT guild_id, week_tag, progress, goal, reward_sent, data "
        "FROM guild_progress WHERE guild_id = ?",
        (str(guild_id),),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    try:
        extra = json.loads(row[5] or "{}")
    except Exception:
        extra = {}
    return {"guild_id": row[0], "week_tag": row[1], "progress": row[2],
            "goal": row[3], "reward_sent": bool(row[4]), "data": extra}


async def guild_goal_set(guild_id: str, week_tag: str, progress: int,
                         goal: int, data: dict | None = None,
                         reward_sent: int = 0) -> None:
    """Create/replace the single row for a guild (used at weekly rollover)."""
    if _pool is None:
        return
    await _pool.execute(
        """INSERT INTO guild_progress (guild_id, week_tag, progress, goal, reward_sent, data, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(guild_id) DO UPDATE SET
             week_tag=excluded.week_tag, progress=excluded.progress,
             goal=excluded.goal, reward_sent=excluded.reward_sent,
             data=excluded.data, updated_at=excluded.updated_at""",
        (str(guild_id), week_tag, int(progress), int(goal), int(reward_sent),
         json.dumps(data or {}, default=str)),
    )
    await _pool.commit()


async def guild_goal_claim_reward_once(guild_id: str, week_tag: str) -> bool:
    """Atomically flip reward_sent 0→1 for this guild's week. Returns True to the
    ONE caller that won the flip — that caller (and only it) distributes rewards.
    A crash after this returns True means some contributors miss out; a crash
    before means the next rollover retries. Never double-pays."""
    if _pool is None:
        return False
    cur = await _pool.execute(
        "UPDATE guild_progress SET reward_sent = 1 "
        "WHERE guild_id = ? AND week_tag = ? AND reward_sent = 0",
        (str(guild_id), week_tag),
    )
    await _pool.commit()
    return (cur.rowcount or 0) > 0


async def guild_goal_contribute(guild_id: str, user_id: str, week_tag: str,
                                amount: int) -> tuple[int, int]:
    """Add `amount` to this guild's weekly total and the player's own tally.
    Returns (new_guild_progress, new_user_contribution)."""
    if _pool is None:
        return (0, 0)
    await _pool.execute(
        """INSERT INTO guild_contributions (guild_id, user_id, week_tag, contribution)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(guild_id, user_id, week_tag)
           DO UPDATE SET contribution = contribution + excluded.contribution""",
        (str(guild_id), str(user_id), week_tag, int(amount)),
    )
    await _pool.execute(
        "UPDATE guild_progress SET progress = progress + ?, updated_at = datetime('now') "
        "WHERE guild_id = ? AND week_tag = ?",
        (int(amount), str(guild_id), week_tag),
    )
    await _pool.commit()
    async with _pool.execute(
        "SELECT progress FROM guild_progress WHERE guild_id = ?", (str(guild_id),),
    ) as cur:
        gp = await cur.fetchone()
    async with _pool.execute(
        "SELECT contribution FROM guild_contributions WHERE guild_id=? AND user_id=? AND week_tag=?",
        (str(guild_id), str(user_id), week_tag),
    ) as cur:
        uc = await cur.fetchone()
    return ((gp[0] if gp else 0), (uc[0] if uc else 0))


async def guild_goal_contributors(guild_id: str, week_tag: str,
                                  min_contribution: int = 1) -> list[tuple[str, int]]:
    if _pool is None:
        return []
    async with _pool.execute(
        """SELECT user_id, contribution FROM guild_contributions
           WHERE guild_id = ? AND week_tag = ? AND contribution >= ?
           ORDER BY contribution DESC""",
        (str(guild_id), week_tag, int(min_contribution)),
    ) as cur:
        return [(r[0], r[1]) for r in await cur.fetchall()]


async def referral_code_get_or_make(user_id: str, mint) -> str:
    """Return this player's referral code, minting one with `mint()` if needed.
    `mint` is a callable returning a fresh candidate code string."""
    if _pool is None:
        return ""
    async with _pool.execute(
        "SELECT code FROM referral_codes WHERE user_id = ?", (str(user_id),),
    ) as cur:
        row = await cur.fetchone()
    if row:
        return row[0]
    for _ in range(12):
        cand = mint()
        try:
            await _pool.execute(
                "INSERT INTO referral_codes (user_id, code) VALUES (?, ?)",
                (str(user_id), cand),
            )
            await _pool.commit()
            return cand
        except Exception:
            continue
    return ""


async def referral_code_owner(code: str) -> str | None:
    if _pool is None:
        return None
    async with _pool.execute(
        "SELECT user_id FROM referral_codes WHERE code = ?", (code.strip().upper(),),
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else None


async def referral_of(referred_id: str) -> dict | None:
    if _pool is None:
        return None
    async with _pool.execute(
        """SELECT referred_id, referrer_id, code, qualified_at, reward_claimed
           FROM referrals WHERE referred_id = ?""", (str(referred_id),),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    return {"referred_id": row[0], "referrer_id": row[1], "code": row[2],
            "qualified_at": row[3], "reward_claimed": bool(row[4])}


async def referral_record(referred_id: str, referrer_id: str, code: str) -> bool:
    """Bind a referred player to a referrer. False if they already have one."""
    if _pool is None:
        return False
    try:
        await _pool.execute(
            "INSERT INTO referrals (referred_id, referrer_id, code) VALUES (?, ?, ?)",
            (str(referred_id), str(referrer_id), code.strip().upper()),
        )
        await _pool.commit()
        return True
    except Exception:
        return False


async def claim_referral_reward_once(referred_id: str) -> bool:
    """Atomically mark this referral qualified + reward-claimed in ONE statement.
    Returns True only to the single caller that won the flip (reward_claimed 0→1);
    that caller alone hands out both sides' rewards. Concurrent callers get False.
    A crash after True means the pair may miss the reward (never a double pay)."""
    if _pool is None:
        return False
    cur = await _pool.execute(
        "UPDATE referrals SET reward_claimed = 1, "
        "qualified_at = COALESCE(qualified_at, datetime('now')) "
        "WHERE referred_id = ? AND reward_claimed = 0",
        (str(referred_id),),
    )
    await _pool.commit()
    return (cur.rowcount or 0) > 0


async def referral_mark_qualified(referred_id: str) -> None:
    """Record that a referral hit the play threshold (without paying yet)."""
    if _pool is None:
        return
    await _pool.execute(
        "UPDATE referrals SET qualified_at = datetime('now') "
        "WHERE referred_id = ? AND qualified_at IS NULL",
        (str(referred_id),),
    )
    await _pool.commit()


async def referral_stats(referrer_id: str) -> dict:
    """{invited, qualified} counts for a referrer's /refer panel."""
    if _pool is None:
        return {"invited": 0, "qualified": 0}
    async with _pool.execute(
        """SELECT COUNT(*), COUNT(qualified_at) FROM referrals WHERE referrer_id = ?""",
        (str(referrer_id),),
    ) as cur:
        row = await cur.fetchone()
    return {"invited": (row[0] if row else 0), "qualified": (row[1] if row else 0)}

# Leaderboard using SQLite
async def update_leaderboard(user_id: str, stat: str, value: int):
    """Placeholder - leaderboard queries directly from SQLite"""
    pass  # We'll query directly from the table

async def get_leaderboard(stat: str, limit: int = 10) -> list[tuple[str, int]]:
    """Get top N from leaderboard using SQLite"""
    if stat == "money":
        query = "SELECT user_id, money FROM users ORDER BY money DESC LIMIT ?"
    elif stat == "level":
        query = "SELECT user_id, level FROM users ORDER BY level DESC, data->>'xp' DESC LIMIT ?"
    else:
        return []
    
    async with _pool.execute(query, (limit,)) as cursor:
        rows = await cursor.fetchall()
        return [(row[0], row[1]) for row in rows]


# ─────────────────────────────────────────────
# LOCK REGISTRY
# ─────────────────────────────────────────────

# Per-user locks — serialise concurrent interactions for the same user.
# Acquiring order rule to prevent deadlock:
#   user lock THEN tribe_lock  (never the reverse)
_user_locks: dict[str, asyncio.Lock] = {}


def get_user_lock(user_id: str) -> asyncio.Lock:
    """Return (and lazily create) the asyncio.Lock for this user."""
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


# Single global lock for tribe_data mutations.
tribe_lock = asyncio.Lock()

# Legacy alias kept so any existing bot.py references still resolve.
state_lock = tribe_lock


# ─────────────────────────────────────────────
# SINGLE-INSTANCE LOCK  (DB-backed)
# ─────────────────────────────────────────────
# Every "duplicate DM / double payout / verify loop" bug traces back to two bot
# processes on the same token. These three helpers let the process that owns the
# DB row be the only one that serves interactions:
#   • on_ready  → claim_instance_lock()  (refuse to start if another is live)
#   • every 3s → refresh_instance_lock() (bump heartbeat; shut down if lost)
#   • shutdown  → release_instance_lock()

INSTANCE_LOCK_TTL = 12   # seconds; a heartbeat older than this is stale → takeover.
# Keep this well above the heartbeat loop's interval (app.py, instance_heartbeat)
# — otherwise a live, healthy process can look abandoned before its next beat
# and a second instance takes over while the first is still serving interactions.


async def claim_instance_lock(instance_id: str, hostname: str = "",
                              pid: int = 0) -> tuple[bool, Optional[dict]]:
    """Try to become the single active instance.

    Returns ``(True, None)`` on success. Returns ``(False, holder)`` when another
    instance holds a *fresh* lock (``holder`` = dict describing it). A lock whose
    heartbeat is older than ``INSTANCE_LOCK_TTL`` is considered abandoned and is
    taken over.
    """
    now = time.time()
    # One atomic UPSERT: insert if absent, else overwrite only when the row is
    # already ours or its heartbeat has gone stale.
    await _pool.execute(
        """
        INSERT INTO bot_instance (id, instance_id, hostname, pid, claimed_at, heartbeat)
        VALUES (1, ?, ?, ?, datetime('now'), ?)
        ON CONFLICT(id) DO UPDATE SET
            instance_id = excluded.instance_id,
            hostname    = excluded.hostname,
            pid         = excluded.pid,
            claimed_at  = excluded.claimed_at,
            heartbeat   = excluded.heartbeat
        WHERE bot_instance.instance_id = excluded.instance_id
           OR bot_instance.heartbeat  < ?
        """,
        (instance_id, hostname, pid, now, now - INSTANCE_LOCK_TTL),
    )
    await _pool.commit()

    async with _pool.execute(
        "SELECT instance_id, hostname, pid, heartbeat FROM bot_instance WHERE id = 1"
    ) as cur:
        row = await cur.fetchone()

    if row and row[0] == instance_id:
        return True, None
    if not row:
        return False, None
    return False, {"instance_id": row[0], "hostname": row[1], "pid": row[2],
                   "age_s": round(now - row[3], 1)}


async def refresh_instance_lock(instance_id: str) -> bool:
    """Bump our heartbeat. Returns ``False`` if the row is no longer ours (another
    instance took over) — the caller should shut this process down."""
    cur = await _pool.execute(
        "UPDATE bot_instance SET heartbeat = ? WHERE id = 1 AND instance_id = ?",
        (time.time(), instance_id),
    )
    await _pool.commit()
    return cur.rowcount > 0


async def release_instance_lock(instance_id: str) -> None:
    """Drop the lock on graceful shutdown (only if it is still ours)."""
    try:
        await _pool.execute(
            "DELETE FROM bot_instance WHERE id = 1 AND instance_id = ?", (instance_id,)
        )
        await _pool.commit()
    except Exception:
        pass


# ─────────────────────────────────────────────
# SAVE CALLBACKS (NOW USING SQLITE)
# ─────────────────────────────────────────────

_save_users_fn:  Callable | None = None
_save_tribes_fn: Callable | None = None


def register_save_callbacks(save_users: Callable, save_tribes: Callable) -> None:
    """
    Wire up the async flush functions used by transaction context managers.
    Each must be a zero-arg *coroutine function* — the transaction managers
    `await` it directly, so the DB write is guaranteed to have landed before
    the transaction (and whatever Discord response follows it) completes.
    Call once from app.py after data globals are initialised.
    """
    global _save_users_fn, _save_tribes_fn
    _save_users_fn = save_users
    _save_tribes_fn = save_tribes


async def _flush_users() -> None:
    """Flush users to SQLite - awaited by transaction context managers so the
    write finishes before the transaction (and any reply built on its result)
    does — no fire-and-forget task that could still be in flight on crash."""
    if _save_users_fn is not None:
        await _save_users_fn()


async def _flush_tribes() -> None:
    """Flush tribes to SQLite - see _flush_users."""
    if _save_tribes_fn is not None:
        await _save_tribes_fn()


# ─────────────────────────────────────────────
# TRANSACTION CONTEXT MANAGERS  —  snapshot + rollback
# ─────────────────────────────────────────────
#
# The managers below lock, then take a deep-copy snapshot of the state they
# guard. If the body raises, the snapshot is restored *before* the flush, so a
# crash between "deduct" and "deliver" can no longer leave money or items in a
# half-applied state — the DB ends up matching the pre-transaction memory.
#
# app.py registers the live dicts via register_state_refs(); until it does (e.g.
# in tests / analysis scripts) snapshotting is a no-op and behaviour is exactly
# as before.

_users_ref:  Optional[dict] = None
_tribes_ref: Optional[dict] = None
_MISSING = object()


def register_state_refs(users: dict, tribes: dict) -> None:
    """Give the transaction managers direct access to the in-memory state dicts
    so they can snapshot / roll back. Call once, after the data is loaded."""
    global _users_ref, _tribes_ref
    _users_ref, _tribes_ref = users, tribes


def _snap_user(uid: str):
    if _users_ref is None:
        return _MISSING
    cur = _users_ref.get(uid, _MISSING)
    return _MISSING if cur is _MISSING else copy.deepcopy(cur)


def _restore_user(uid: str, snap) -> None:
    if _users_ref is None:
        return
    if snap is _MISSING:
        _users_ref.pop(uid, None)          # user didn't exist before the txn
        return
    cur = _users_ref.get(uid)
    if isinstance(cur, dict):
        cur.clear(); cur.update(snap)          # keep the dict object identity
    else:
        _users_ref[uid] = snap


def _snap_tribes():
    return _MISSING if _tribes_ref is None else copy.deepcopy(_tribes_ref)


def _restore_tribes(snap) -> None:
    if _tribes_ref is None or snap is _MISSING:
        return
    for k in [k for k in _tribes_ref if k not in snap]:
        del _tribes_ref[k]
    for k, v in snap.items():
        cur = _tribes_ref.get(k)
        if isinstance(cur, dict):
            cur.clear(); cur.update(v)
        else:
            _tribes_ref[k] = v


def _snap_tribe(name: str):
    """Snapshot a single tribe (or _MISSING if it doesn't exist yet — e.g. the
    transaction is about to create it). Cheap alternative to _snap_tribes()
    for the common case of a transaction touching one known tribe."""
    if _tribes_ref is None:
        return _MISSING
    cur = _tribes_ref.get(name, _MISSING)
    return _MISSING if cur is _MISSING else copy.deepcopy(cur)


def _restore_tribe(name: str, snap) -> None:
    if _tribes_ref is None:
        return
    if snap is _MISSING:
        _tribes_ref.pop(name, None)         # tribe didn't exist before the txn
        return
    cur = _tribes_ref.get(name)
    if isinstance(cur, dict):
        cur.clear(); cur.update(snap)           # keep the dict object identity
    else:
        _tribes_ref[name] = snap


@asynccontextmanager
async def user_transaction(user_id: str):
    """
    Serialise all mutations to data[user_id], roll back on error, flush on exit.

        async with user_transaction(user_id):
            data[user_id]["money"] += 100
            # flushed automatically; reverted + flushed if the body raises
    """
    async with get_user_lock(user_id):
        snap = _snap_user(user_id)
        try:
            yield
        except BaseException:
            _restore_user(user_id, snap)
            raise
        finally:
            await _flush_users()


@asynccontextmanager
async def multi_user_transaction(*user_ids: str):
    """Serialise mutations to several users at once, roll back all on error.

    Locks are taken in a globally consistent order (sorted, de-duplicated) so two
    interactions that touch the same pair of users — e.g. A gifting B while B
    gifts A — can never each hold one lock while waiting on the other.

        async with multi_user_transaction(sender_id, recipient_id):
            spend_money(sender_id, n, "gift"); add_money(recipient_id, n, "gift")
    """
    uniq = sorted({str(u) for u in user_ids})
    async with AsyncExitStack() as stack:
        for uid in uniq:
            await stack.enter_async_context(get_user_lock(uid))
        snaps = {uid: _snap_user(uid) for uid in uniq}
        try:
            yield
        except BaseException:
            for uid, s in snaps.items():
                _restore_user(uid, s)
            raise
        finally:
            await _flush_users()


@asynccontextmanager
async def user_tribe_transaction(user_id: str, *tribe_names: str):
    """
    Serialise mutations to both data[user_id] and the given tribe(s), roll back
    on error, flush both. Acquires user lock first, tribe_lock second — never
    reversed.

    Pass the name of every tribe the transaction body will mutate (almost
    always just the caller's own tribe) — only those are deep-copied for
    rollback instead of the whole tribe_data structure, which gets expensive
    as the tribe count grows. A tribe that doesn't exist yet (the body is
    about to create it) snapshots as "absent" and is dropped again on error.
    Call sites that can't name their tribe(s) up front may omit tribe_names,
    which falls back to the old full-tribe_data snapshot.

        async with user_tribe_transaction(user_id, tribe_name):
            data[user_id]["tribe"] = tribe_name
            tribe_data[tribe_name]["roles"]["members"].append(user_id)
    """
    async with get_user_lock(user_id):
        async with tribe_lock:
            usnap = _snap_user(user_id)
            if tribe_names:
                tsnaps = {name: _snap_tribe(name) for name in tribe_names}
                full_snap = _MISSING
            else:
                tsnaps = None
                full_snap = _snap_tribes()
            try:
                yield
            except BaseException:
                _restore_user(user_id, usnap)
                if tsnaps is not None:
                    for name, s in tsnaps.items():
                        _restore_tribe(name, s)
                else:
                    _restore_tribes(full_snap)
                raise
            finally:
                mark_tribes_dirty(*tribe_names)
                await _flush_users()
                await _flush_tribes()


@asynccontextmanager
async def tribe_only_transaction(*tribe_names: str):
    """
    Serialise mutations to tribe_data when there is no single owning user
    (e.g. lottery draw, an expedition payout to a member who already left).
    Prefer user_tribe_transaction when a user is involved.

    Pass the tribe name(s) being mutated to snapshot only those; omit for a
    call site that may touch any tribe (e.g. an all-tribes maintenance sweep),
    which falls back to the old full-tribe_data snapshot.
    """
    async with tribe_lock:
        if tribe_names:
            tsnaps = {name: _snap_tribe(name) for name in tribe_names}
            full_snap = _MISSING
        else:
            tsnaps = None
            full_snap = _snap_tribes()
        try:
            yield
        except BaseException:
            if tsnaps is not None:
                for name, s in tsnaps.items():
                    _restore_tribe(name, s)
            else:
                _restore_tribes(full_snap)
            raise
        finally:
            mark_tribes_dirty(*tribe_names)
            await _flush_tribes()


# ─────────────────────────────────────────────
# LEGACY ASYNC WRAPPERS
# ─────────────────────────────────────────────

async def mutate_users_state(mutator: Callable) -> None:
    async with state_lock:
        mutator()
        await _flush_users()


async def mutate_users_and_tribes_state(mutator: Callable) -> None:
    async with state_lock:
        mutator()
        mark_tribes_dirty()
        await _flush_users()
        await _flush_tribes()


# ─────────────────────────────────────────────
# ECONOMY LOG
# ─────────────────────────────────────────────

# Sync, fire-and-forget: economy log entries are analytics, not player state,
# so losing one on a crash is fine — unlike the save path above, this must
# stay non-blocking.
def log_economy_event(
    user_id: str,
    source: str,
    delta: int,
    balance_after: int,
    currency: str = "money",
) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(log_economy_event_buffered(user_id, source, delta, balance_after, currency))
    except RuntimeError:
        pass  # no running loop (e.g. in tests)


# ─────────────────────────────────────────────
# SCHEMA VERSION
# ─────────────────────────────────────────────

CURRENT_SCHEMA: int = 15  # bump whenever a new migration is added


# ─────────────────────────────────────────────
# NESTED MODELS
# ─────────────────────────────────────────────

@dataclass
class VerifyState:
    needed: bool = False
    time:   int  = 250
    code:   str  = ""

    @classmethod
    def from_dict(cls, d: dict) -> "VerifyState":
        return cls(
            needed=bool(d.get("needed", False)),
            time=int(d.get("time", 250)),
            code=str(d.get("code", "")),
        )

    def to_dict(self) -> dict:
        return {"needed": self.needed, "time": self.time, "code": self.code}


@dataclass
class Boosts:
    luck: int = 0
    sell: int = 0
    xp:   int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "Boosts":
        return cls(
            luck=int(d.get("luck", 0)),
            sell=int(d.get("sell", 0)),
            xp=int(d.get("xp", 0)),
        )

    def to_dict(self) -> dict:
        return {"luck": self.luck, "sell": self.sell, "xp": self.xp}


@dataclass
class IdleState:
    active:            bool      = False
    stacks:            int       = 0       # number of hunters stationed at the camp
    started_at:        float     = 0.0     # timestamp catches accumulate from
    camp_biome:        str       = "village"
    haul:              list[str] = field(default_factory=list)  # caught animals awaiting collection
    capacity_upgrades: int       = 0

    @classmethod
    def from_dict(cls, d: dict) -> "IdleState":
        return cls(
            active=bool(d.get("active", False)),
            stacks=int(d.get("stacks", 0)),
            started_at=float(d.get("started_at", 0)),
            camp_biome=str(d.get("camp_biome", "village") or "village"),
            haul=list(d.get("haul", [])),
            capacity_upgrades=int(d.get("capacity_upgrades", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "active":            self.active,
            "stacks":            self.stacks,
            "started_at":        self.started_at,
            "camp_biome":        self.camp_biome,
            "haul":              self.haul,
            "capacity_upgrades": self.capacity_upgrades,
        }


@dataclass
class Stats:
    ammo_used:         int       = 0
    lottery_wins:      int       = 0
    tools_used:        list[str] = field(default_factory=list)
    events_completed:  int       = 0
    total_xp_earned:   int       = 0
    bj_wins:           int       = 0
    cf_wins:           int       = 0
    rl_wins:           int       = 0
    rps_wins:          int       = 0
    slots_wins:        int       = 0
    ammo_variety_done: bool      = False
    game_master_score: int       = 0
    myths_killed:      int       = 0
    myths_died:        int       = 0
    myths_fled:        int       = 0
    # Idle Hunter V2 counters
    crates_opened:            int = 0
    lifetime_hunts:           int = 0
    active_days:              int = 0
    tracks_started:           int = 0
    tracks_completed:         int = 0
    tracks_lost:              int = 0
    sightings_joined:         int = 0
    shares_posted:            int = 0
    regions_explored:         int = 0
    world_conditions_hunted:  int = 0
    expedition_contrib:       int = 0
    # Idle Hunter V2.1 — animal combat counters
    animal_fights_started:    int = 0
    animal_fights_won:        int = 0
    animal_fights_lost:       int = 0
    animal_fights_fled:       int = 0

    # Anything not modeled above (older or future keys) is preserved verbatim.
    _extra: dict = field(default_factory=dict, repr=False)

    _INT_FIELDS = (
        "ammo_used", "lottery_wins", "events_completed", "total_xp_earned",
        "bj_wins", "cf_wins", "rl_wins", "rps_wins", "slots_wins",
        "game_master_score", "myths_killed", "myths_died", "myths_fled",
        "crates_opened", "lifetime_hunts", "active_days", "tracks_started",
        "tracks_completed", "tracks_lost", "sightings_joined", "shares_posted",
        "regions_explored", "world_conditions_hunted", "expedition_contrib",
        "animal_fights_started", "animal_fights_won", "animal_fights_lost",
        "animal_fights_fled",
    )

    @classmethod
    def from_dict(cls, d: dict) -> "Stats":
        d = d or {}
        s = cls(
            tools_used=list(d.get("tools_used", [])),
            ammo_variety_done=bool(d.get("ammo_variety_done", False)),
            **{k: int(d.get(k, 0) or 0) for k in cls._INT_FIELDS},
        )
        known = set(cls._INT_FIELDS) | {"tools_used", "ammo_variety_done"}
        s._extra = {k: v for k, v in d.items() if k not in known}
        return s

    def to_dict(self) -> dict:
        out = {k: getattr(self, k) for k in self._INT_FIELDS}
        out["tools_used"] = self.tools_used
        out["ammo_variety_done"] = self.ammo_variety_done
        out.update(self._extra)
        return out


@dataclass
class BanRecord:
    active:       bool = False
    reason:       str  = ""
    expires_ts:   int  = 0   # 0 = permanent
    issued_ts:    int  = 0
    appeals_used: int  = 0
    appeals_max:  int  = 2

    @classmethod
    def from_dict(cls, d: dict) -> "BanRecord":
        return cls(
            active=bool(d.get("active", False)),
            reason=str(d.get("reason", "")),
            expires_ts=int(d.get("expires_ts", 0)),
            issued_ts=int(d.get("issued_ts", 0)),
            appeals_used=int(d.get("appeals_used", 0)),
            appeals_max=int(d.get("appeals_max", 2)),
        )

    def to_dict(self) -> dict:
        return {
            "active":       self.active,
            "reason":       self.reason,
            "expires_ts":   self.expires_ts,
            "issued_ts":    self.issued_ts,
            "appeals_used": self.appeals_used,
            "appeals_max":  self.appeals_max,
        }

    def is_active(self) -> bool:
        if not self.active:
            return False
        if self.expires_ts != 0 and time.time() > self.expires_ts:
            return False
        return True


@dataclass
class AnimalRecord:
    count:        int            = 0
    total_earned: int            = 0
    tools:        dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "AnimalRecord":
        return cls(
            count=int(d.get("count", 0)),
            total_earned=int(d.get("total_earned", 0)),
            tools=dict(d.get("tools", {})),
        )

    def to_dict(self) -> dict:
        return {
            "count":        self.count,
            "total_earned": self.total_earned,
            "tools":        self.tools,
        }


@dataclass
class AchievementProgress:
    claimed_up_to: int = -1  # index of last claimed tier; -1 = none

    @classmethod
    def from_dict(cls, d: dict) -> "AchievementProgress":
        return cls(claimed_up_to=int(d.get("claimed_up_to", -1)))

    def to_dict(self) -> dict:
        return {"claimed_up_to": self.claimed_up_to}


@dataclass
class BadgeState:
    tier:          int  = 0
    notified_gold: bool = False
    notified_plat: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "BadgeState":
        return cls(
            tier=int(d.get("tier", 0)),
            notified_gold=bool(d.get("notified_gold", False)),
            notified_plat=bool(d.get("notified_plat", False)),
        )

    def to_dict(self) -> dict:
        return {
            "tier":          self.tier,
            "notified_gold": self.notified_gold,
            "notified_plat": self.notified_plat,
        }


@dataclass
class GiftMail:
    sender_id:   str  = ""
    sender_name: str  = ""
    fmt:         str  = "money"   # "money" | "gems"
    amt_str:     str  = ""
    message:     str  = ""
    ts:          int  = 0
    read:        bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "GiftMail":
        return cls(
            sender_id=str(d.get("sender_id", "")),
            sender_name=str(d.get("sender_name", "")),
            fmt=str(d.get("fmt", d.get("format", "money"))),
            amt_str=str(d.get("amt_str", "")),
            message=str(d.get("message", "")),
            ts=int(d.get("ts", 0)),
            read=bool(d.get("read", False)),
        )

    def to_dict(self) -> dict:
        return {
            "sender_id":   self.sender_id,
            "sender_name": self.sender_name,
            "fmt":         self.fmt,
            "amt_str":     self.amt_str,
            "message":     self.message,
            "ts":          self.ts,
            "read":        self.read,
        }


# ─────────────────────────────────────────────
# USER MODEL
# ─────────────────────────────────────────────

@dataclass
class User:
    # Identity
    schema_version:     int = CURRENT_SCHEMA
    username:           str = ""

    # Economy
    money:              int = 10_000
    gems:               int = 100
    total_money_earned: int = 0

    # Progression
    level:        int = 1
    xp:           int = 0
    prestige:     int = 0
    total_caught: int = 0

    # Inventory & gear
    inv:            list[str]      = field(default_factory=list)
    owned_tools:    list[str]      = field(default_factory=lambda: ["Bare Hands"])
    tool:           str            = "Bare Hands"
    ammo_inv:       dict[str, int] = field(default_factory=dict)
    equipped_ammo:  str | None     = None
    vehicle:        str            = "None"
    owned_vehicles: list[str]      = field(default_factory=list)
    myth_items:     dict[str, int] = field(default_factory=dict)  # mythic-creature trophies
    crate_inv:      dict[str, int] = field(default_factory=dict)  # crate name -> count
    shards:         dict[str, int] = field(default_factory=dict)  # rarity -> count
    crystals:       dict[str, int] = field(default_factory=dict)  # rarity -> count
    gemstones:      dict[str, int] = field(default_factory=dict)  # rarity -> count (decor)
    craft_queue:    list[dict]     = field(default_factory=list)  # [{rarity, done_ts}] crystal crafts

    # Location
    biome:  str          = "village"
    travel: dict | None  = None   # {dest, depart_ts, arrive_ts, mins} while in transit

    # Cooldowns (unix timestamps)
    hunt_cd:  float = 0.0
    daily_cd: float = 0.0

    # Daily streak
    daily_streak:      int = 0
    best_daily_streak: int = 0
    last_daily_date:   str = ""
    joined_date:       str = ""

    # Cosmetics
    color:          str        = "green"
    equipped_title: str | None = None
    earned_titles:  list[str]  = field(default_factory=list)
    featured_badge: str        = ""   # badge key shown next to the name in lists
    special_badges: list[str]  = field(default_factory=list)  # admin-granted badge keys

    # Social
    tribe:                 str | None = None
    tribe_inv:             str | None = None
    tribe_inv_read:        bool       = False
    tribe_inv_notice_seen: str        = ""
    servers:               list[str]  = field(default_factory=list)

    # Mail
    mail_read_dev:         bool           = False
    mail_dev_content_read: str            = ""
    mail_dev_notice_seen:  str            = ""
    gift_mails:            list[GiftMail] = field(default_factory=list)
    gift_mail_notice_seen: str            = ""

    # Nested state
    verify: VerifyState = field(default_factory=VerifyState)
    boosts: Boosts      = field(default_factory=Boosts)
    idle:   IdleState   = field(default_factory=IdleState)
    stats:  Stats       = field(default_factory=Stats)
    ban:    BanRecord   = field(default_factory=BanRecord)

    # Progress tracking
    record:       dict[str, AnimalRecord]        = field(default_factory=dict)
    achievements: dict[str, AchievementProgress] = field(default_factory=dict)
    badges:       dict[str, BadgeState]          = field(default_factory=dict)
    log:          list[dict]                     = field(default_factory=list)
    warnings:     list[dict]                     = field(default_factory=list)

    # Misc flags
    premium:      bool  = False
    is_tester:    bool  = False   # admin-set: maxed test account, hidden from leaderboards

    # Tribe progression (Phase 1)
    tribe_day:     dict  = field(default_factory=dict)  # {tag, hunts, daily, tasks} daily caps
    tribe_left_ts: float = 0.0                          # last tribe departure (rejoin cooldown)

    # Global events
    event:     dict = field(default_factory=dict)  # {key, started, …per-event mini-game state}
    event_day: dict = field(default_factory=dict)  # {tag, n} — daily rewarded-attempt counter
    last_suggest: float = 0.0
    last_report:  float = 0.0
    last_gamble:  float = 0.0

    # Idle Hunter V2
    onboarding:       dict = field(default_factory=lambda: {
        "version": 2, "completed": True, "step": "done", "starter_pack": None})
    guide_seen:       list[str]   = field(default_factory=list)  # biome keys hunted in
    tracking:         dict | None = None                          # active tracking sequence
    referral_pending: str         = ""

    # Everything the raw store carries that no field above models (e.g. _boss,
    # quests, temp_boosts, lb_snap, _hunt_times, notif, _a_day, _ref_done…).
    # Round-tripped verbatim so user_from_store → user_to_store never loses data.
    _extra: dict = field(default_factory=dict, repr=False)

    # Ephemeral — in-memory only, excluded from to_dict()
    _cf_bet:        int = field(default=0,  repr=False)
    _cf_last_pick:  str = field(default="", repr=False)
    _slots_bet:     int = field(default=0,  repr=False)
    _roulette_bet:  int = field(default=0,  repr=False)
    _roulette_pick: str = field(default="", repr=False)
    _rps_bet:       int = field(default=0,  repr=False)
    _rps_last_pick: str = field(default="", repr=False)
    _display_name:  str = field(default="", repr=False)

    _EPHEMERAL = frozenset({
        "_cf_bet", "_cf_last_pick", "_slots_bet",
        "_roulette_bet", "_roulette_pick",
        "_rps_bet", "_rps_last_pick", "_display_name",
    })

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        u = cls(
            schema_version=int(d.get("schema_version", 0)),
            username=str(d.get("username", "")),
            money=int(d.get("money", 10_000)),
            gems=int(d.get("gems", 100)),
            total_money_earned=int(d.get("total_money_earned", 0)),
            level=int(d.get("level", 1)),
            xp=int(d.get("xp", 0)),
            prestige=int(d.get("prestige", 0)),
            total_caught=int(d.get("total_caught", 0)),
            inv=list(d.get("inv", [])),
            owned_tools=list(d.get("owned_tools", ["Bare Hands"])),
            tool=str(d.get("tool", "Bare Hands")),
            ammo_inv=dict(d.get("ammo_inv", {})),
            equipped_ammo=d.get("equipped_ammo"),
            vehicle=str(d.get("vehicle", "None")),
            owned_vehicles=list(d.get("owned_vehicles", [])),
            myth_items=dict(d.get("myth_items", {})),
            crate_inv=dict(d.get("crate_inv", {})),
            shards=dict(d.get("shards", {})),
            crystals=dict(d.get("crystals", {})),
            gemstones=dict(d.get("gemstones", {})),
            craft_queue=list(d.get("craft_queue", [])),
            biome=str(d.get("biome", "village")),
            travel=d.get("travel"),
            hunt_cd=float(d.get("hunt_cd", 0)),
            daily_cd=float(d.get("daily_cd", 0)),
            daily_streak=int(d.get("daily_streak", 0)),
            best_daily_streak=int(d.get("best_daily_streak", 0)),
            last_daily_date=str(d.get("last_daily_date", "")),
            joined_date=str(d.get("joined_date", "")),
            color=str(d.get("color", "green")),
            equipped_title=d.get("equipped_title"),
            earned_titles=list(d.get("earned_titles", [])),
            featured_badge=str(d.get("featured_badge", "")),
            special_badges=list(d.get("special_badges", [])),
            tribe=d.get("tribe"),
            tribe_inv=d.get("tribe_inv"),
            tribe_inv_read=bool(d.get("tribe_inv_read", False)),
            tribe_inv_notice_seen=str(d.get("tribe_inv_notice_seen", "")),
            servers=list(d.get("servers", [])),
            mail_read_dev=bool(d.get("mail_read_dev", False)),
            mail_dev_content_read=str(d.get("mail_dev_content_read", "")),
            mail_dev_notice_seen=str(d.get("mail_dev_notice_seen", "")),
            gift_mails=[GiftMail.from_dict(g) for g in d.get("gift_mails", [])],
            gift_mail_notice_seen=str(d.get("gift_mail_notice_seen", "")),
            verify=VerifyState.from_dict(d.get("verify") or {}),
            boosts=Boosts.from_dict(d.get("boosts") or {}),
            idle=IdleState.from_dict(d.get("idle") or {}),
            stats=Stats.from_dict(d.get("stats") or {}),
            ban=BanRecord.from_dict(d.get("ban") or {}),
            record={
                k: AnimalRecord.from_dict(v)
                for k, v in d.get("record", {}).items()
            },
            achievements={
                k: AchievementProgress.from_dict(v)
                for k, v in d.get("achievements", {}).items()
            },
            badges={
                k: BadgeState.from_dict(v)
                for k, v in d.get("badges", {}).items()
            },
            log=list(d.get("log", [])),
            warnings=list(d.get("warnings", [])),
            premium=bool(d.get("premium", False)),
            is_tester=bool(d.get("is_tester", False)),
            tribe_day=dict(d.get("tribe_day", {})),
            tribe_left_ts=float(d.get("tribe_left_ts", 0)),
            event=dict(d.get("event", {})),
            event_day=dict(d.get("event_day", {})),
            last_suggest=float(d.get("last_suggest", 0)),
            last_report=float(d.get("last_report", 0)),
            last_gamble=float(d.get("last_gamble", 0)),
            onboarding=dict(d.get("onboarding") or {
                "version": 2, "completed": True, "step": "done", "starter_pack": None}),
            guide_seen=list(d.get("guide_seen", [])),
            tracking=d.get("tracking"),
            referral_pending=str(d.get("referral_pending", "")),
        )
        # Restore ephemeral gamble state if it somehow survived a restart
        u._cf_bet        = int(d.get("_cf_bet", 0))
        u._cf_last_pick  = str(d.get("_cf_last_pick", ""))
        u._slots_bet     = int(d.get("_slots_bet", 0))
        u._roulette_bet  = int(d.get("_roulette_bet", 0))
        u._roulette_pick = str(d.get("_roulette_pick", ""))
        u._rps_bet       = int(d.get("_rps_bet", 0))
        u._rps_last_pick = str(d.get("_rps_last_pick", ""))
        # Preserve any key the model doesn't name (verbatim, minus ephemerals).
        _modeled = set(_USER_MODELED_KEYS) | cls._EPHEMERAL
        u._extra = {k: v for k, v in d.items() if k not in _modeled}
        return u

    def to_dict(self) -> dict:
        out = {
            "schema_version":         self.schema_version,
            "username":               self.username,
            "money":                  self.money,
            "gems":                   self.gems,
            "total_money_earned":     self.total_money_earned,
            "level":                  self.level,
            "xp":                     self.xp,
            "prestige":               self.prestige,
            "total_caught":           self.total_caught,
            "inv":                    self.inv,
            "owned_tools":            self.owned_tools,
            "tool":                   self.tool,
            "ammo_inv":               self.ammo_inv,
            "equipped_ammo":          self.equipped_ammo,
            "vehicle":                self.vehicle,
            "owned_vehicles":         self.owned_vehicles,
            "myth_items":             self.myth_items,
            "crate_inv":              self.crate_inv,
            "shards":                 self.shards,
            "crystals":               self.crystals,
            "gemstones":              self.gemstones,
            "craft_queue":            self.craft_queue,
            "biome":                  self.biome,
            "travel":                 self.travel,
            "hunt_cd":                self.hunt_cd,
            "daily_cd":               self.daily_cd,
            "daily_streak":           self.daily_streak,
            "best_daily_streak":      self.best_daily_streak,
            "last_daily_date":        self.last_daily_date,
            "joined_date":            self.joined_date,
            "color":                  self.color,
            "equipped_title":         self.equipped_title,
            "earned_titles":          self.earned_titles,
            "featured_badge":         self.featured_badge,
            "special_badges":         self.special_badges,
            "tribe":                  self.tribe,
            "tribe_inv":              self.tribe_inv,
            "tribe_inv_read":         self.tribe_inv_read,
            "tribe_inv_notice_seen":  self.tribe_inv_notice_seen,
            "servers":                self.servers,
            "mail_read_dev":          self.mail_read_dev,
            "mail_dev_content_read":  self.mail_dev_content_read,
            "mail_dev_notice_seen":   self.mail_dev_notice_seen,
            "gift_mails":             [g.to_dict() for g in self.gift_mails],
            "gift_mail_notice_seen":  self.gift_mail_notice_seen,
            "verify":                 self.verify.to_dict(),
            "boosts":                 self.boosts.to_dict(),
            "idle":                   self.idle.to_dict(),
            "stats":                  self.stats.to_dict(),
            "ban":                    self.ban.to_dict(),
            "record":                 {k: v.to_dict() for k, v in self.record.items()},
            "achievements":           {k: v.to_dict() for k, v in self.achievements.items()},
            "badges":                 {k: v.to_dict() for k, v in self.badges.items()},
            "log":                    self.log,
            "warnings":               self.warnings,
            "premium":                self.premium,
            "is_tester":              self.is_tester,
            "tribe_day":              self.tribe_day,
            "tribe_left_ts":          self.tribe_left_ts,
            "event":                  self.event,
            "event_day":              self.event_day,
            "last_suggest":           self.last_suggest,
            "last_report":            self.last_report,
            "last_gamble":            self.last_gamble,
            "onboarding":             self.onboarding,
            "guide_seen":             self.guide_seen,
            "tracking":               self.tracking,
            "referral_pending":       self.referral_pending,
        }
        out.update(self._extra)   # carry unmodeled keys through unchanged
        return out


# Keys that User.to_dict() emits directly — used by from_dict to compute _extra.
_USER_MODELED_KEYS = frozenset({
    "schema_version", "username", "money", "gems", "total_money_earned", "level",
    "xp", "prestige", "total_caught", "inv", "owned_tools", "tool", "ammo_inv",
    "equipped_ammo", "vehicle", "owned_vehicles", "myth_items", "crate_inv",
    "shards", "crystals", "gemstones", "craft_queue", "biome", "travel", "hunt_cd",
    "daily_cd", "daily_streak", "best_daily_streak", "last_daily_date",
    "joined_date", "color", "equipped_title", "earned_titles", "featured_badge",
    "special_badges", "tribe", "tribe_inv", "tribe_inv_read",
    "tribe_inv_notice_seen", "servers", "mail_read_dev", "mail_dev_content_read",
    "mail_dev_notice_seen", "gift_mails", "gift_mail_notice_seen", "verify",
    "boosts", "idle", "stats", "ban", "record", "achievements", "badges", "log",
    "warnings", "premium", "is_tester", "tribe_day", "tribe_left_ts", "event",
    "event_day", "last_suggest", "last_report", "last_gamble", "onboarding",
    "guide_seen", "tracking", "referral_pending",
})


# ─────────────────────────────────────────────
# TRIBE MODELS
# ─────────────────────────────────────────────

@dataclass
class TribeRoles:
    leader:   str       = "0"
    officer:  list[str] = field(default_factory=list)
    members:  list[str] = field(default_factory=list)
    recruits: list[str] = field(default_factory=list)   # 24h probation

    @classmethod
    def from_dict(cls, d: dict) -> "TribeRoles":
        return cls(
            leader=str(d.get("leader", "0")),
            officer=list(d.get("officer", [])),
            members=list(d.get("members", [])),
            recruits=list(d.get("recruits", [])),
        )

    def to_dict(self) -> dict:
        return {
            "leader":   self.leader,
            "officer":  self.officer,
            "members":  self.members,
            "recruits": self.recruits,
        }

    def all_member_ids(self) -> list[str]:
        return [self.leader] + self.officer + self.members + self.recruits

    def count(self) -> int:
        return 1 + len(self.officer) + len(self.members) + len(self.recruits)


@dataclass
class Tribe:
    description:      str | None = None
    creator:          str        = "0"
    roles:            TribeRoles = field(default_factory=TribeRoles)
    banned:           list[str]  = field(default_factory=list)
    level:            int        = 1
    xp:               int        = 0
    invites:          list[str]  = field(default_factory=list)
    premium:          bool       = False
    max_members:      int        = 5
    luck_boost:       int        = 0
    sell_price_boost: int        = 0
    xp_boost:         int        = 0

    @classmethod
    def from_dict(cls, d: dict) -> "Tribe":
        return cls(
            description=d.get("description"),
            creator=str(d.get("creator", "0")),
            roles=TribeRoles.from_dict(d.get("roles") or {}),
            banned=list(d.get("banned", [])),
            level=int(d.get("level", 1)),
            xp=int(d.get("xp", 0)),
            invites=list(d.get("invites", [])),
            premium=bool(d.get("premium", False)),
            max_members=int(d.get("max_members", 5)),
            luck_boost=int(d.get("luck_boost", 0)),
            sell_price_boost=int(d.get("sell_price_boost", 0)),
            xp_boost=int(d.get("xp_boost", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "description":      self.description,
            "creator":          self.creator,
            "roles":            self.roles.to_dict(),
            "banned":           self.banned,
            "level":            self.level,
            "xp":               self.xp,
            "invites":          self.invites,
            "premium":          self.premium,
            "max_members":      self.max_members,
            "luck_boost":       self.luck_boost,
            "sell_price_boost": self.sell_price_boost,
            "xp_boost":         self.xp_boost,
        }

    def is_full(self) -> bool:
        return self.roles.count() >= self.max_members


# ─────────────────────────────────────────────
# MIGRATION LAYER
# ─────────────────────────────────────────────
# Rules:
#   - Each function receives ONE raw user dict and returns it upgraded
#   - Migrations are idempotent and additive — never remove fields
#   - To add: write _migrate_vN, bump CURRENT_SCHEMA, append to MIGRATIONS

def _migrate_v1(d: dict) -> dict:
    """v0 → v1: ensure stats sub-dict exists."""
    d.setdefault("stats", {})
    for key, default in [
        ("ammo_used", 0), ("lottery_wins", 0), ("tools_used", []),
        ("events_completed", 0), ("total_xp_earned", 0),
        ("bj_wins", 0), ("cf_wins", 0), ("rl_wins", 0),
        ("rps_wins", 0), ("slots_wins", 0),
    ]:
        d["stats"].setdefault(key, default)
    return d


def _migrate_v2(d: dict) -> dict:
    """v1 → v2: ban record, achievements, badges, titles, gift mail fields."""
    d.setdefault("ban", {
        "active": False, "reason": "", "expires_ts": 0,
        "issued_ts": 0, "appeals_used": 0, "appeals_max": 2,
    })
    d.setdefault("achievements", {})
    d.setdefault("badges", {})
    d.setdefault("earned_titles", [])
    d.setdefault("equipped_title", None)
    d.setdefault("gift_mails", [])
    d.setdefault("gift_mail_notice_seen", "")
    d.setdefault("tribe_inv_read", False)
    d.setdefault("tribe_inv_notice_seen", "")
    return d


def _migrate_v3(d: dict) -> dict:
    """v2 → v3: normalise ammo_inv values to int, ensure vehicle fields."""
    ammo = d.get("ammo_inv", {})
    d["ammo_inv"] = {k: int(v) for k, v in ammo.items() if int(v) > 0}
    if "equipped_ammo" not in d:
        d["equipped_ammo"] = None
    if not d.get("vehicle"):
        d["vehicle"] = "None"
    d.setdefault("owned_vehicles", [])
    return d


def _migrate_v4(d: dict) -> dict:
    """v3 → v4: add crate_luck to boosts, ensure crate_inv exists."""
    d.setdefault("crate_inv", {})
    boosts = d.setdefault("boosts", {})
    boosts.setdefault("crate_luck", 0)
    return d


def _migrate_v5(d: dict) -> dict:
    """v4 → v5: Hunting Camp idle rework — camp biome, haul buffer, storage upgrades.

    Existing idle ``stacks`` (hunters) and ``started_at`` carry over unchanged; the
    camp starts in whatever biome the player currently hunts.
    """
    idle = d.setdefault("idle", {})
    idle.setdefault("camp_biome", d.get("biome", "village") or "village")
    idle.setdefault("haul", [])
    idle.setdefault("capacity_upgrades", 0)
    return d


def _migrate_v6(d: dict) -> dict:
    """v5 → v6: mythical-creature boss encounters + Earth-biome travel.

    Adds the trophy inventory, the pending-encounter / travel scratch fields, and
    the new hunt stats. No animal or biome remap — biome keys are unchanged.
    """
    d.setdefault("myth_items", {})
    d.setdefault("_boss", None)
    d.setdefault("travel", None)
    st = d.setdefault("stats", {})
    for k in ("myths_killed", "myths_died", "myths_fled"):
        st.setdefault(k, 0)
    return d


def _migrate_v7(d: dict) -> dict:
    """v6 → v7: the desert-turned-water biome key 'large_desert' → 'sunken_coast'.
    Remap every place a player record stores a biome key."""
    OLD, NEW = "large_desert", "sunken_coast"
    if d.get("biome") == OLD:
        d["biome"] = NEW
    idle = d.get("idle")
    if isinstance(idle, dict) and idle.get("camp_biome") == OLD:
        idle["camp_biome"] = NEW
    boss = d.get("_boss")
    if isinstance(boss, dict) and boss.get("biome") == OLD:
        boss["biome"] = NEW
    tr = d.get("travel")
    if isinstance(tr, dict):
        for k in ("dest", "origin"):
            if tr.get(k) == OLD:
                tr[k] = NEW
    for e in d.get("log", []):
        if isinstance(e, dict) and e.get("biome") == OLD:
            e["biome"] = NEW
    for q in d.get("quests", []):
        req = q.get("requires") if isinstance(q, dict) else None
        if isinstance(req, dict) and req.get("biome") == OLD:
            req["biome"] = NEW
    return d


def _migrate_v8(d: dict) -> dict:
    """v7 → v8: add ``featured_badge`` — the one badge shown next to the player's
    name in leaderboard rows and tribe rosters. Empty here; app.py backfills it to
    the player's first-earned badge and keeps it in sync as badges are earned."""
    d.setdefault("featured_badge", "")
    return d


def _migrate_v9(d: dict) -> dict:
    """v8 → v9: the shard / crystal / crate crafting economy.
    Shards drop from catches, fuse (9→1, timed) into crystals via /craft, and
    9 crystals buy a crate in the crate shop. Gemstones are a decorative 5%
    crate-open bonus. All start empty; the old direct hunt-crate drop is gone."""
    d.setdefault("crate_inv", {})
    d.setdefault("shards", {})
    d.setdefault("crystals", {})
    d.setdefault("gemstones", {})
    d.setdefault("craft_queue", [])
    return d


def _migrate_v12(d: dict) -> dict:
    """v11 → v12: per-player global-event mini-game state + daily attempt counter.
    Both empty — populated only while an activity event is running."""
    d.setdefault("event", {})
    d.setdefault("event_day", {})
    return d


def _migrate_v11(d: dict) -> dict:
    """v10 → v11: tribe progression — per-member daily tribe-XP caps and the
    rejoin-cooldown timestamp. Tribe-side fields are backfilled at load time by
    app._ensure_tribe_fields (tribes are stored as raw dicts, not migrated here)."""
    d.setdefault("tribe_day", {})
    d.setdefault("tribe_left_ts", 0.0)
    return d


def _migrate_v10(d: dict) -> dict:
    """v9 → v10: admin-granted special badges + the TESTER account flag.
    ``special_badges`` holds badge keys from game_data.SPECIAL_BADGES; ``is_tester``
    marks a maxed test account that is hidden from every leaderboard. Both empty
    here — set only by an admin."""
    d.setdefault("special_badges", [])
    d.setdefault("is_tester", False)
    return d


def _migrate_v13(d: dict) -> dict:
    """v12 → v13: interactive onboarding (Idle Hunter V2).

    Every EXISTING player is marked ``completed`` — only brand-new accounts (via
    init_user) start the guided first-hunt flow. Also seeds the V2 exploration
    counters so the Field Guide / tracking / world-condition code can assume them.
    """
    d.setdefault("onboarding", {
        "version": 2, "completed": True, "step": "done", "starter_pack": None,
    })
    st = d.setdefault("stats", {})
    for k in ("tracks_started", "tracks_completed", "tracks_lost",
              "sightings_joined", "shares_posted", "regions_explored",
              "world_conditions_hunted", "expedition_contrib",
              "lifetime_hunts", "active_days"):
        st.setdefault(k, 0)
    d.setdefault("guide_seen", [])        # biome keys the player has hunted in
    d.setdefault("tracking", None)         # active tracking sequence, or None
    d.setdefault("referral_pending", "")   # code entered before it was bound
    return d


def _migrate_v14(d: dict) -> dict:
    """v13 → v14: persistent player HP + animal combat + healing + rookie systems.

    HP becomes a real, persistent player stat instead of a fresh 100 every
    mythic fight. EXISTING players start at full HP with rookie protection
    already spent (they don't get the new-player free-rescue); brand-new
    accounts get rookie_revive_used=False via init_user's own defaults.
    """
    d.setdefault("health", {
        "hp": 100, "max_hp": 100, "last_regen_ts": time.time(),
        "injuries": [], "rookie_revive_used": True,
    })
    d.setdefault("healing_inv", {})
    d.setdefault("trial_tool", None)       # {"tool", "expires_at"} during the onboarding loan
    d.setdefault("rookie_goals", {
        "catch_5": False, "reach_level_5": False, "discover_5": False,
        "buy_tool": False, "view_world": False,
    })
    d.setdefault("rookie_chest_claimed", False)
    d.setdefault("fight", None)            # active normal-animal encounter, or None
    st = d.setdefault("stats", {})
    for k in ("animal_fights_started", "animal_fights_won", "animal_fights_lost",
              "animal_fights_fled"):
        st.setdefault(k, 0)
    return d


def _migrate_v15(d: dict) -> dict:
    """v14 → v15: Collection rework — mythic kills get their own record instead
    of discovery being inferred from trophy ownership, and trophies become
    equippable relics instead of sellable junk. `myth_items` is left alone
    (still the per-trophy count, still where equip options come from)."""
    d.setdefault("myth_record", {})        # creature -> {kills, first_kill_ts, best_hp_left}
    d.setdefault("equipped_trophies", [])  # trophy names, length capped by unlocked slots
    return d


MIGRATIONS: list[tuple[int, Any]] = [
    (1, _migrate_v1),
    (2, _migrate_v2),
    (3, _migrate_v3),
    (4, _migrate_v4),
    (5, _migrate_v5),
    (6, _migrate_v6),
    (7, _migrate_v7),
    (8, _migrate_v8),
    (9, _migrate_v9),
    (10, _migrate_v10),
    (11, _migrate_v11),
    (12, _migrate_v12),
    (13, _migrate_v13),
    (14, _migrate_v14),
    (15, _migrate_v15),
]


def migrate_user_dict(d: dict) -> dict:
    """Apply all pending migrations to a single raw user dict."""
    current = int(d.get("schema_version", 0))
    for target_version, fn in MIGRATIONS:
        if current < target_version:
            d = fn(d)
            d["schema_version"] = target_version
            current = target_version
    return d


def migrate_all_users(raw: dict[str, dict]) -> dict[str, dict]:
    """Migrate every user in the raw JSON blob. Returns the same structure."""
    return {uid: migrate_user_dict(udict) for uid, udict in raw.items()}


# ─────────────────────────────────────────────
# STORE CONVENIENCE HELPERS
# ─────────────────────────────────────────────

def user_from_store(store: dict[str, dict], user_id: str) -> User:
    """Return a typed User from the raw store, migrating on the fly."""
    return User.from_dict(migrate_user_dict(store.get(user_id, {})))


def user_to_store(store: dict[str, dict], user_id: str, user: User) -> None:
    """Write a typed User back into the raw store (ready for JSON dump)."""
    store[user_id] = user.to_dict()


def tribe_from_store(store: dict[str, dict], name: str) -> Tribe:
    return Tribe.from_dict(store.get(name, {}))


def tribe_to_store(store: dict[str, dict], name: str, tribe: Tribe) -> None:
    store[name] = tribe.to_dict()
