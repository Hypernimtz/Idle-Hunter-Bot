"""
backend.py — Persistence, locking, transaction helpers, typed models, and migration.

Deliberately imports nothing from bot.py, game_data.py, or discord so it can
be used in tests and analysis scripts without a running bot.
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Callable

logger = logging.getLogger(__name__)

DEGRADED_MODE = False

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
    await init_schema()

async def close_databases():
    """Close SQLite connection"""
    global _pool
    if _pool:
        await _pool.close()

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
    
    # Create indexes
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_users_level ON users(level DESC)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_users_money ON users(money DESC)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_users_prestige ON users(prestige DESC)")
    await _pool.execute("CREATE INDEX IF NOT EXISTS idx_tribes_level ON tribes(level DESC)")

# Remove Redis cache (simplify) or keep with simple dict cache:
_data_cache: dict[str, dict] = {}
_tribe_cache: dict[str, dict] = {}

async def get_user(user_id: str) -> dict:
    """Get user data with simple in-memory cache"""
    if user_id in _data_cache:
        return _data_cache[user_id].copy()
    
    async with _pool.execute(
        "SELECT data FROM users WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        _data_cache[user_id] = data
        return data.copy()

async def save_user(user_id: str, data: dict):
    """Save user data to SQLite"""
    await _pool.execute("""
        INSERT OR REPLACE INTO users (user_id, data, username, level, money, prestige, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        user_id,
        json.dumps(data),
        data.get("username", ""),
        data.get("level", 1),
        data.get("money", 0),
        data.get("prestige", 0)
    ))
    await _pool.commit()
    
    # Update cache
    _data_cache[user_id] = data

async def bulk_save_users(users: dict[str, dict]):
    """Bulk save multiple users"""
    await _pool.executemany("""
        INSERT OR REPLACE INTO users (user_id, data, username, level, money, prestige, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """, [
        (uid, json.dumps(data), data.get("username", ""), 
         data.get("level", 1), data.get("money", 0), data.get("prestige", 0))
        for uid, data in users.items()
    ])
    await _pool.commit()
    
    # Update cache
    _data_cache.update(users)

async def get_tribe(tribe_name: str) -> dict:
    """Get tribe data"""
    if tribe_name in _tribe_cache:
        return _tribe_cache[tribe_name].copy()
    
    async with _pool.execute(
        "SELECT data FROM tribes WHERE name = ?", (tribe_name,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        _tribe_cache[tribe_name] = data
        return data.copy()

async def save_tribe(tribe_name: str, data: dict):
    """Save tribe data"""
    member_count = 1 + len(data.get("roles", {}).get("officer", [])) + len(data.get("roles", {}).get("members", []))
    
    await _pool.execute("""
        INSERT OR REPLACE INTO tribes (name, data, level, member_count, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (tribe_name, json.dumps(data), data.get("level", 1), member_count))
    await _pool.commit()
    
    _tribe_cache[tribe_name] = data

async def bulk_save_tribes(tribes_dict: dict):
    """Save all tribes to SQLite"""
    for name, tribe_data in tribes_dict.items():
        await save_tribe(name, tribe_data)

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
    
    async with _BUFFER_LOCK:
        _economy_buffer.append({
            "user_id": user_id,
            "source": source,
            "delta": delta,
            "balance_after": balance_after,
            "currency": currency
        })
        
        if len(_economy_buffer) >= _BUFFER_SIZE:
            await _flush_economy_buffer()

async def _flush_economy_buffer():
    """Write buffered economy events to SQLite"""
    global _economy_buffer
    async with _BUFFER_LOCK:
        if not _economy_buffer:
            return
        buffer = _economy_buffer[:]
        _economy_buffer = []
    
    await _pool.executemany("""
        INSERT INTO economy_log (user_id, source, delta, balance_after, currency)
        VALUES (?, ?, ?, ?, ?)
    """, [(e["user_id"], e["source"], e["delta"], e["balance_after"], e["currency"]) for e in buffer])
    await _pool.commit()

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


# In backend.py, REPLACE the SAVE CALLBACKS section (around line 200-250):

# ─────────────────────────────────────────────
# SAVE CALLBACKS (NOW USING SQLITE)
# ─────────────────────────────────────────────

_save_users_fn:  Callable | None = None
_save_tribes_fn: Callable | None = None


def register_save_callbacks(save_users: Callable, save_tribes: Callable) -> None:
    """
    Wire up the flush functions used by transaction context managers.
    Call once from bot.py after data globals are initialised.
    """
    global _save_users_fn, _save_tribes_fn
    _save_users_fn = save_users
    _save_tribes_fn = save_tribes


def _flush_users() -> None:
    """Flush users to SQLite - called by transaction context managers"""
    if _save_users_fn is not None:
        _save_users_fn()  # This will call bulk_save_users(data) from main.py


def _flush_tribes() -> None:
    """Flush tribes to SQLite - called by transaction context managers"""
    if _save_tribes_fn is not None:
        _save_tribes_fn()  # This will call bulk_save_tribes(tribe_data) from main.py


# ─────────────────────────────────────────────
# TRANSACTION CONTEXT MANAGERS
# ─────────────────────────────────────────────

@asynccontextmanager
async def user_transaction(user_id: str):
    """
    Serialise all mutations to data[user_id] and guarantee a flush on exit.

        async with user_transaction(user_id):
            data[user_id]["money"] += 100
            # save_data_users() fires automatically, even on exception
    """
    async with get_user_lock(user_id):
        try:
            yield
        finally:
            _flush_users()


@asynccontextmanager
async def user_tribe_transaction(user_id: str):
    """
    Serialise mutations to both data[user_id] and tribe_data, flush both.
    Acquires user lock first, tribe_lock second — never reversed.

        async with user_tribe_transaction(user_id):
            data[user_id]["tribe"] = tribe_name
            tribe_data[tribe_name]["roles"]["members"].append(user_id)
    """
    async with get_user_lock(user_id):
        async with tribe_lock:
            try:
                yield
            finally:
                _flush_users()
                _flush_tribes()


@asynccontextmanager
async def tribe_only_transaction():
    """
    Serialise mutations to tribe_data when there is no single owning user
    (e.g. lottery draw).  Prefer user_tribe_transaction when a user is involved.
    """
    async with tribe_lock:
        try:
            yield
        finally:
            _flush_tribes()


# ─────────────────────────────────────────────
# LEGACY ASYNC WRAPPERS
# ─────────────────────────────────────────────

async def mutate_users_state(mutator: Callable) -> None:
    async with state_lock:
        mutator()
        _flush_users()


async def mutate_users_and_tribes_state(mutator: Callable) -> None:
    async with state_lock:
        mutator()
        _flush_users()
        _flush_tribes()


# ─────────────────────────────────────────────
# ECONOMY LOG
# ─────────────────────────────────────────────

ECONOMY_LOG     = "economy_log.csv"

def log_economy_event(
    user_id: str,
    source: str,
    delta: int,
    balance_after: int,
    currency: str = "money",
    path: str = ECONOMY_LOG,
) -> None:
    return log_economy_event_buffered(user_id, source, delta, balance_after, currency)


# ─────────────────────────────────────────────
# SCHEMA VERSION
# ─────────────────────────────────────────────

CURRENT_SCHEMA: int = 3  # bump whenever a new migration is added


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
    active:     bool  = False
    stacks:     int   = 0
    started_at: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "IdleState":
        return cls(
            active=bool(d.get("active", False)),
            stacks=int(d.get("stacks", 0)),
            started_at=float(d.get("started_at", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "active":     self.active,
            "stacks":     self.stacks,
            "started_at": self.started_at,
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

    @classmethod
    def from_dict(cls, d: dict) -> "Stats":
        return cls(
            ammo_used=int(d.get("ammo_used", 0)),
            lottery_wins=int(d.get("lottery_wins", 0)),
            tools_used=list(d.get("tools_used", [])),
            events_completed=int(d.get("events_completed", 0)),
            total_xp_earned=int(d.get("total_xp_earned", 0)),
            bj_wins=int(d.get("bj_wins", 0)),
            cf_wins=int(d.get("cf_wins", 0)),
            rl_wins=int(d.get("rl_wins", 0)),
            rps_wins=int(d.get("rps_wins", 0)),
            slots_wins=int(d.get("slots_wins", 0)),
            ammo_variety_done=bool(d.get("ammo_variety_done", False)),
            game_master_score=int(d.get("game_master_score", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "ammo_used":         self.ammo_used,
            "lottery_wins":      self.lottery_wins,
            "tools_used":        self.tools_used,
            "events_completed":  self.events_completed,
            "total_xp_earned":   self.total_xp_earned,
            "bj_wins":           self.bj_wins,
            "cf_wins":           self.cf_wins,
            "rl_wins":           self.rl_wins,
            "rps_wins":          self.rps_wins,
            "slots_wins":        self.slots_wins,
            "ammo_variety_done": self.ammo_variety_done,
            "game_master_score": self.game_master_score,
        }


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

    # Location
    biome: str = "village"

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
    last_suggest: float = 0.0
    last_report:  float = 0.0
    last_gamble:  float = 0.0

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
            biome=str(d.get("biome", "village")),
            hunt_cd=float(d.get("hunt_cd", 0)),
            daily_cd=float(d.get("daily_cd", 0)),
            daily_streak=int(d.get("daily_streak", 0)),
            best_daily_streak=int(d.get("best_daily_streak", 0)),
            last_daily_date=str(d.get("last_daily_date", "")),
            joined_date=str(d.get("joined_date", "")),
            color=str(d.get("color", "green")),
            equipped_title=d.get("equipped_title"),
            earned_titles=list(d.get("earned_titles", [])),
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
            last_suggest=float(d.get("last_suggest", 0)),
            last_report=float(d.get("last_report", 0)),
            last_gamble=float(d.get("last_gamble", 0)),
        )
        # Restore ephemeral gamble state if it somehow survived a restart
        u._cf_bet        = int(d.get("_cf_bet", 0))
        u._cf_last_pick  = str(d.get("_cf_last_pick", ""))
        u._slots_bet     = int(d.get("_slots_bet", 0))
        u._roulette_bet  = int(d.get("_roulette_bet", 0))
        u._roulette_pick = str(d.get("_roulette_pick", ""))
        u._rps_bet       = int(d.get("_rps_bet", 0))
        u._rps_last_pick = str(d.get("_rps_last_pick", ""))
        return u

    def to_dict(self) -> dict:
        return {
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
            "biome":                  self.biome,
            "hunt_cd":                self.hunt_cd,
            "daily_cd":               self.daily_cd,
            "daily_streak":           self.daily_streak,
            "best_daily_streak":      self.best_daily_streak,
            "last_daily_date":        self.last_daily_date,
            "joined_date":            self.joined_date,
            "color":                  self.color,
            "equipped_title":         self.equipped_title,
            "earned_titles":          self.earned_titles,
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
            "last_suggest":           self.last_suggest,
            "last_report":            self.last_report,
            "last_gamble":            self.last_gamble,
        }


# ─────────────────────────────────────────────
# TRIBE MODELS
# ─────────────────────────────────────────────

@dataclass
class TribeRoles:
    leader:  str       = "0"
    officer: list[str] = field(default_factory=list)
    members: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "TribeRoles":
        return cls(
            leader=str(d.get("leader", "0")),
            officer=list(d.get("officer", [])),
            members=list(d.get("members", [])),
        )

    def to_dict(self) -> dict:
        return {
            "leader":  self.leader,
            "officer": self.officer,
            "members": self.members,
        }

    def all_member_ids(self) -> list[str]:
        return [self.leader] + self.officer + self.members

    def count(self) -> int:
        return 1 + len(self.officer) + len(self.members)


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


MIGRATIONS: list[tuple[int, Any]] = [
    (1, _migrate_v1),
    (2, _migrate_v2),
    (3, _migrate_v3),
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
