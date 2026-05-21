
"""
curves.py — Canonical XP and economy formula definitions.

All reward/cost numbers that appear in bot logic should be derived from
or validated against the constants and functions here.  This module has
NO imports from bot.py or game_data.py so it can be used in analysis
scripts and tests without a Discord environment.

Design targets
──────────────
XP curve
  Level 1–100   : fast early ramp          (~5–15 min per level at full grind)
  Level 100–500 : steady mid-game          (~30–60 min per level)
  Level 500+    : prestige gate            (hours per level; prestige at 1000)

Money curve
  Each biome tier should generate enough money to fund the *next* tool
  within a reasonable session (2–4 hours active play).
  The idle system should provide 20–30 % of active hunt income.

Prestige gate
  Level 1 000 + ◈ 1 000 000 000 acts as a hard sink and resets progress.
  Reaching it for the first time should take ~3–6 months of normal play.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


# ─────────────────────────────────────────────────────────────────────────────
# XP CURVE
# ─────────────────────────────────────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    """
    XP required to advance FROM ``level`` to ``level + 1``.

    Three-bracket piecewise power curve anchored so requirements never
    decrease across bracket boundaries.

    Bracket 1  (1–100)  : fast, encouraging early progress
    Bracket 2  (101–500): moderate acceleration
    Bracket 3  (501+)   : steep late-game gate

    >>> xp_for_level(1)
    222
    >>> xp_for_level(100) > xp_for_level(99)
    True
    >>> xp_for_level(500) > xp_for_level(499)
    True
    """
    lvl = max(1, level)

    if lvl <= 100:
        return int(200 + (lvl ** 1.35) * 22)

    xp_at_100 = int(200 + (100 ** 1.35) * 22)

    if lvl <= 500:
        return xp_at_100 + int(((lvl - 100) ** 1.5) * 18)

    xp_at_500 = xp_at_100 + int(((500 - 100) ** 1.5) * 18)
    return xp_at_500 + int(((lvl - 500) ** 1.7) * 20)


def total_xp_to_level(target: int) -> int:
    """Cumulative XP needed to reach ``target`` from level 1."""
    return sum(xp_for_level(lvl) for lvl in range(1, target))


def hunts_to_level(
    target: int,
    xp_per_hunt_min: int = 10,
    xp_per_hunt_max: int = 50,
    multi_catch: int = 1,
    xp_boost_pct: int = 0,
) -> tuple[int, int]:
    """
    Estimated hunt range to reach ``target`` level from level 1.

    Returns (min_hunts, max_hunts).
    """
    total = total_xp_to_level(target)
    boost = 1 + xp_boost_pct / 100
    xp_min = xp_per_hunt_min * multi_catch * boost
    xp_max = xp_per_hunt_max * multi_catch * boost
    return int(total / xp_max), int(total / xp_min)


# ─────────────────────────────────────────────────────────────────────────────
# MONEY / HUNT REWARD CURVE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BiomeCurveParams:
    """
    All economic parameters for a single biome tier.

    Fields
    ------
    biome_key       : matches BIOME_LEVELS key
    level_req       : minimum player level to enter
    base_value_min  : lowest base animal sell value (before boosts)
    base_value_max  : highest base animal sell value (before boosts)
    rare_multiplier : sell value multiplier on a rare catch (default 3×)
    xp_min          : XP floor per catch
    xp_max          : XP ceiling per catch
    tool_tier_req   : minimum tool tier
    """
    biome_key:       str
    level_req:       int
    base_value_min:  int
    base_value_max:  int
    rare_multiplier: float = 3.0
    xp_min:          int   = 10
    xp_max:          int   = 50
    tool_tier_req:   int   = 1

    @property
    def avg_value(self) -> float:
        return (self.base_value_min + self.base_value_max) / 2

    def expected_sell_per_hunt(
        self,
        multi_catch: int = 1,
        luck_pct: int = 5,
        sell_boost_pct: int = 0,
    ) -> float:
        """
        Expected money per hunt factoring in rare-catch probability.

        luck_pct : base rare-catch chance (5 % minimum in game logic)
        """
        rare_chance = min(luck_pct / 100, 1.0)
        sell_mult   = 1 + sell_boost_pct / 100
        avg_base    = self.avg_value * sell_mult
        ev_per_catch = avg_base * (
            (1 - rare_chance) + rare_chance * self.rare_multiplier
        )
        return ev_per_catch * multi_catch

    def session_income(
        self,
        hours: float = 1.0,
        hunts_per_hour: int = 1200,   # 3 s cooldown → 1 200 hunts/hr
        multi_catch: int = 1,
        luck_pct: int = 5,
        sell_boost_pct: int = 0,
    ) -> float:
        total_hunts = hours * hunts_per_hour
        return total_hunts * self.expected_sell_per_hunt(
            multi_catch, luck_pct, sell_boost_pct
        )


# Canonical biome curve table.
# Values calibrated so a 2-hour active session in biome N produces
# roughly enough money to fund the cheapest tool for biome N+1.
BIOME_CURVES: list[BiomeCurveParams] = [
    BiomeCurveParams("village",             1,         18,      120,   tool_tier_req=1),
    BiomeCurveParams("forest",             10,        110,      400,   tool_tier_req=2),
    BiomeCurveParams("woods",              25,        200,      600,   tool_tier_req=3),
    BiomeCurveParams("small_desert",       50,        400,      800,   tool_tier_req=4),
    BiomeCurveParams("large_desert",      100,        700,    2_000,   tool_tier_req=5),
    BiomeCurveParams("tundra",            150,        800,    2_500,   tool_tier_req=6),
    BiomeCurveParams("jungle",            200,      1_200,    3_500,   tool_tier_req=7),
    BiomeCurveParams("swamp",             275,      1_500,    6_000,   tool_tier_req=8),
    BiomeCurveParams("volcanic_highlands",350,      3_500,    8_000,   tool_tier_req=10),
    BiomeCurveParams("cursed_ruins",      450,      5_000,   15_000,   tool_tier_req=13),
    BiomeCurveParams("rainbow",           600,     12_000,   50_000,   tool_tier_req=15),
    BiomeCurveParams("abyssal_depths",    800,     15_000,   50_000,   tool_tier_req=17),
    BiomeCurveParams("celestial_peaks",  1000,     35_000,  150_000,   tool_tier_req=19),
]

# Lookup by key for O(1) access at runtime
BIOME_CURVE_MAP: dict[str, BiomeCurveParams] = {
    b.biome_key: b for b in BIOME_CURVES
}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL COST / PAYBACK ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ToolPaybackResult:
    tool_name:        str
    tool_price:       int
    currency:         str   # "money" | "gems"
    biome_key:        str
    hunts_to_payback: float   # NaN when currency is gems
    hours_to_payback: float
    income_per_hunt:  float

    def is_reasonable(self, max_payback_hours: float = 8.0) -> bool:
        """True if payback time is within the acceptable window."""
        if self.currency != "money":
            return True          # gem tools have no money payback
        return self.hours_to_payback <= max_payback_hours


def tool_payback(
    tool_name: str,
    tool_price: int,
    tool_currency: str,
    biome_key: str,
    multi_catch: int,
    luck_pct: int = 5,
    sell_boost_pct: int = 0,
    hunts_per_hour: int = 1_200,
) -> ToolPaybackResult:
    """Calculate how many hunts / hours until a tool pays for itself."""
    import math
    curve = BIOME_CURVE_MAP.get(biome_key)
    if curve is None or tool_currency != "money":
        return ToolPaybackResult(
            tool_name=tool_name,
            tool_price=tool_price,
            currency=tool_currency,
            biome_key=biome_key,
            hunts_to_payback=math.nan,
            hours_to_payback=math.nan,
            income_per_hunt=math.nan,
        )

    income = curve.expected_sell_per_hunt(multi_catch, luck_pct, sell_boost_pct)
    hunts  = tool_price / income if income > 0 else math.inf
    hours  = hunts / hunts_per_hour
    return ToolPaybackResult(
        tool_name=tool_name,
        tool_price=tool_price,
        currency=tool_currency,
        biome_key=biome_key,
        hunts_to_payback=hunts,
        hours_to_payback=hours,
        income_per_hunt=income,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DAILY STREAK ECONOMICS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DailyTierParams:
    min_level:  int
    money_min:  int
    money_max:  int
    gems_min:   int
    gems_max:   int

    @property
    def avg_money(self) -> float:
        return (self.money_min + self.money_max) / 2

    @property
    def avg_gems(self) -> float:
        return (self.gems_min + self.gems_max) / 2

    def expected_daily(self, streak: int = 0, prestige: int = 0) -> dict[str, float]:
        """
        Expected value of a daily claim at a given streak and prestige level.

        Returns dict with "money" and "gems" keys (one will be 0 because
        reward type is random 50/50).
        """
        bonus = 1 + (streak / 100) + (prestige * 0.1)
        return {
            "money": self.avg_money * bonus * 0.5,   # 50 % chance
            "gems":  self.avg_gems  * bonus * 0.5,
        }


DAILY_TIERS: list[DailyTierParams] = [
    DailyTierParams(    1,          500,          2_000,   5,    15),
    DailyTierParams(   50,        2_000,         10_000,  10,    30),
    DailyTierParams(  100,       10_000,         50_000,  20,    60),
    DailyTierParams(  250,       50_000,        200_000,  40,   100),
    DailyTierParams(  500,      200_000,      1_000_000,  80,   200),
    DailyTierParams( 1000,    1_000_000,     10_000_000, 150,   400),
    DailyTierParams( 1200,   10_000_000,    100_000_000, 300,   800),
]


def get_daily_tier(level: int) -> DailyTierParams:
    result = DAILY_TIERS[0]
    for tier in DAILY_TIERS:
        if level >= tier.min_level:
            result = tier
    return result


# ─────────────────────────────────────────────────────────────────────────────
# IDLE INCOME
# ─────────────────────────────────────────────────────────────────────────────

def idle_rate_per_hour(biome_level_value: int, player_level: int) -> int:
    """
    Passive income rate per idle stack per hour.

    Mirrors bot.py formula exactly so analysis scripts stay in sync.
    """
    return (biome_level_value + player_level) * 100


def idle_cost_for_stack(current_stacks: int, base: int = 5_000, multiplier: int = 2) -> int:
    """Cost to hire the next idle stack."""
    return base * (multiplier ** current_stacks)


def idle_payback_hours(current_stacks: int, biome_level_value: int, player_level: int) -> float:
    """Hours until a new stack recoups its hiring cost."""
    cost = idle_cost_for_stack(current_stacks)
    rate = idle_rate_per_hour(biome_level_value, player_level)
    return cost / rate if rate > 0 else float("inf")


# ─────────────────────────────────────────────────────────────────────────────
# PRESTIGE GATE VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

PRESTIGE_MIN_LEVEL: int = 1_000
PRESTIGE_MIN_MONEY: int = 1_000_000_000   # ◈ 1 B

HUNT_COOLDOWN_SECONDS: int = 3


def time_to_prestige(
    hunts_per_hour: int = 1_200,
    multi_catch: int = 3,          # late-game tool
    xp_boost_pct: int = 60,        # reasonable late-game boosts
    luck_pct: int = 30,
    sell_boost_pct: int = 30,
) -> dict[str, float]:
    """
    Rough estimate of real-world time to first prestige.

    Returns dict with "level_hours" and "money_hours" keys;
    the bottleneck is whichever is larger.
    """
    # XP time
    _, max_hunts = hunts_to_level(
        PRESTIGE_MIN_LEVEL, multi_catch=multi_catch, xp_boost_pct=xp_boost_pct
    )
    level_hours = max_hunts / hunts_per_hour

    # Money time — use celestial_peaks as proxy for late-game income
    late_biome  = BIOME_CURVE_MAP["celestial_peaks"]
    income_ph   = late_biome.session_income(
        hours=1,
        hunts_per_hour=hunts_per_hour,
        multi_catch=multi_catch,
        luck_pct=luck_pct,
        sell_boost_pct=sell_boost_pct,
    )
    money_hours = PRESTIGE_MIN_MONEY / income_ph if income_ph > 0 else float("inf")

    return {
        "level_hours": level_hours,
        "money_hours": money_hours,
        "bottleneck":  "level" if level_hours > money_hours else "money",
        "total_hours": max(level_hours, money_hours),
    }

"""
telemetry.py — Lightweight economy telemetry layer.

Responsibilities
────────────────
1. Record every money/gem in-flow and out-flow to an append-only CSV.
2. Provide fast in-process aggregation helpers so the bot can surface
   economy health stats without a database.
3. Expose a SnapshotCollector that periodically captures per-player
   balance percentiles for drift analysis.

The CSV format matches the existing economy_log.csv schema so old data
continues to load correctly:

    ts, user_id, source, delta, balance_after, currency

Nothing in this module imports from bot.py, game_data.py, or discord;
it is safe to import in tests and analysis scripts.
"""

import csv
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Sequence

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

ECONOMY_LOG          = "economy_log.csv"
_ECONOMY_FIELDS      = ["ts", "user_id", "source", "delta", "balance_after", "currency"]
_WRITE_LOCK          = threading.Lock()     # guards file writes from sync callers

# Sources treated as "sinks" (money leaves the economy)
SINK_SOURCES: frozenset[str] = frozenset({
    "shop boost", "shop tool", "shop ammo", "tool shop",
    "vehicle shop", "idle hiring", "lottery tickets",
    "coinflip loss", "roulette", "rps loss", "slots bet",
    "blackjack",
})

# Sources treated as "mints" (money enters the economy)
MINT_SOURCES: frozenset[str] = frozenset({
    "sell all", "sell", "idle", "daily", "lottery",
    "coinflip", "roulette win", "rps", "slots",
    "blackjack", "blackjack: 21", "blackjack: tie",
    "gift receive", "achievement", "prestige",
})


# ─────────────────────────────────────────────────────────────────────────────
# EVENT RECORDING
# ─────────────────────────────────────────────────────────────────────────────

def log_economy_event(
    user_id:       str,
    source:        str,
    delta:         int,
    balance_after: int,
    currency:      str = "money",
    path:          str = ECONOMY_LOG,
) -> None:
    """
    Append one row to the economy CSV.

    Thread-safe via a module-level lock.  Zero-delta events are silently
    dropped to keep the log clean.
    """
    if delta == 0:
        return

    row = {
        "ts":            int(time.time()),
        "user_id":       user_id,
        "source":        source,
        "delta":         delta,
        "balance_after": balance_after,
        "currency":      currency,
    }
    p           = Path(path)
    write_header = not p.exists()
    try:
        with _WRITE_LOCK:
            with open(p, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=_ECONOMY_FIELDS)
                if write_header:
                    w.writeheader()
                w.writerow(row)
    except OSError:
        logger.exception("Economy log write failed for user %s", user_id)


# ─────────────────────────────────────────────────────────────────────────────
# CSV READER
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EconomyEvent:
    ts:            int
    user_id:       str
    source:        str
    delta:         int
    balance_after: int
    currency:      str = "money"

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "EconomyEvent":
        return cls(
            ts=int(row.get("ts", 0)),
            user_id=str(row.get("user_id", "")),
            source=str(row.get("source", "")),
            delta=int(row.get("delta", 0)),
            balance_after=int(row.get("balance_after", 0)),
            currency=str(row.get("currency", "money")),
        )


def iter_events(
    path:     str   = ECONOMY_LOG,
    since_ts: int   = 0,
    currency: str   = "money",
) -> Iterator[EconomyEvent]:
    """
    Yield EconomyEvent objects from the CSV, optionally filtered by time
    and currency.  Rows with parse errors are skipped with a warning.
    """
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    ev = EconomyEvent.from_row(row)
                except (ValueError, KeyError):
                    logger.warning("Skipping malformed row: %s", row)
                    continue
                if ev.ts < since_ts:
                    continue
                if ev.currency != currency:
                    continue
                yield ev
    except FileNotFoundError:
        return


# ─────────────────────────────────────────────────────────────────────────────
# AGGREGATION
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EconomyWindow:
    """
    Aggregated economy statistics over a time window.

    All money values are in the same currency unit as the source events.
    """
    window_seconds:   int
    start_ts:         int
    end_ts:           int
    currency:         str

    total_minted:     int   = 0     # sum of positive deltas
    total_burned:     int   = 0     # sum of abs(negative deltas)
    net_flow:         int   = 0     # minted − burned
    event_count:      int   = 0
    unique_users:     int   = 0

    # per-source breakdowns
    minted_by_source: dict[str, int] = field(default_factory=dict)
    burned_by_source: dict[str, int] = field(default_factory=dict)

    @property
    def inflation_ratio(self) -> float:
        """minted / burned.  >1 = inflationary, <1 = deflationary."""
        return self.total_minted / self.total_burned if self.total_burned else float("inf")

    def top_mint_sources(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.minted_by_source.items(), key=lambda x: x[1], reverse=True)[:n]

    def top_burn_sources(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.burned_by_source.items(), key=lambda x: x[1], reverse=True)[:n]

    def summary_lines(self) -> list[str]:
        lines = [
            f"Window : {self.window_seconds // 3600}h",
            f"Minted : {self.total_minted:>15,}",
            f"Burned : {self.total_burned:>15,}",
            f"Net    : {self.net_flow:>+15,}",
            f"Ratio  : {self.inflation_ratio:.3f}",
            f"Events : {self.event_count:,}  Users: {self.unique_users:,}",
            "",
            "Top mint sources:",
        ]
        for src, amt in self.top_mint_sources():
            lines.append(f"  {src:<30} {amt:>15,}")
        lines.append("Top burn sources:")
        for src, amt in self.top_burn_sources():
            lines.append(f"  {src:<30} {amt:>15,}")
        return lines


def aggregate(
    window_seconds: int   = 86_400,
    path:           str   = ECONOMY_LOG,
    currency:       str   = "money",
) -> EconomyWindow:
    """
    Read the economy log and return aggregated stats for the last
    ``window_seconds`` of data.
    """
    now      = int(time.time())
    since    = now - window_seconds
    users:   set[str]        = set()
    minted:  dict[str, int]  = defaultdict(int)
    burned:  dict[str, int]  = defaultdict(int)
    count                    = 0

    for ev in iter_events(path, since_ts=since, currency=currency):
        users.add(ev.user_id)
        count += 1
        if ev.delta > 0:
            minted[ev.source] += ev.delta
        else:
            burned[ev.source] += abs(ev.delta)

    total_minted = sum(minted.values())
    total_burned = sum(burned.values())

    return EconomyWindow(
        window_seconds=window_seconds,
        start_ts=since,
        end_ts=now,
        currency=currency,
        total_minted=total_minted,
        total_burned=total_burned,
        net_flow=total_minted - total_burned,
        event_count=count,
        unique_users=len(users),
        minted_by_source=dict(minted),
        burned_by_source=dict(burned),
    )


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER SNAPSHOT  (for balance-distribution drift tracking)
# ─────────────────────────────────────────────────────────────────────────────

SNAPSHOT_LOG          = "economy_snapshots.csv"
_SNAPSHOT_FIELDS      = ["ts", "p10", "p25", "p50", "p75", "p90", "p99",
                         "mean", "total", "player_count"]


def capture_balance_snapshot(
    balances:  Sequence[int],
    path:      str = SNAPSHOT_LOG,
) -> None:
    """
    Record a percentile snapshot of the current balance distribution.

    Call this periodically (e.g. from a daily task loop) to track
    wealth distribution over time.
    """
    if not balances:
        return

    import statistics
    sorted_b = sorted(balances)
    n        = len(sorted_b)

    def percentile(pct: float) -> int:
        idx = max(0, min(int(pct / 100 * n), n - 1))
        return sorted_b[idx]

    row = {
        "ts":           int(time.time()),
        "p10":          percentile(10),
        "p25":          percentile(25),
        "p50":          percentile(50),
        "p75":          percentile(75),
        "p90":          percentile(90),
        "p99":          percentile(99),
        "mean":         int(statistics.mean(sorted_b)),
        "total":        sum(sorted_b),
        "player_count": n,
    }
    p           = Path(path)
    write_header = not p.exists()
    try:
        with open(p, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=_SNAPSHOT_FIELDS)
            if write_header:
                w.writeheader()
            w.writerow(row)
    except OSError:
        logger.exception("Snapshot write failed")


def iter_snapshots(path: str = SNAPSHOT_LOG) -> Iterator[dict]:
    """Yield snapshot rows as dicts (all values converted to int/float)."""
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    yield {k: int(v) for k, v in row.items()}
                except (ValueError, KeyError):
                    continue
    except FileNotFoundError:
        return


# ─────────────────────────────────────────────────────────────────────────────
# REALTIME HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HealthStatus:
    healthy:       bool
    warnings:      list[str] = field(default_factory=list)
    window_1h:     EconomyWindow | None = None
    window_24h:    EconomyWindow | None = None

    def as_discord_block(self, accent: int = 0x3498DB) -> str:
        """Return a markdown string suitable for an ephemeral bot embed."""
        status_icon = "🟢" if self.healthy else "🔴"
        lines = [f"### {status_icon} Economy Health"]
        if self.warnings:
            for w in self.warnings:
                lines.append(f"⚠️ {w}")
            lines.append("")

        for label, win in [("1h", self.window_1h), ("24h", self.window_24h)]:
            if win is None:
                continue
            lines.append(f"**Last {label}**")
            lines += [f"-# {l}" for l in win.summary_lines()]
        return "\n".join(lines)


def health_check(path: str = ECONOMY_LOG) -> HealthStatus:
    """
    Run a quick sanity check on economy data.

    Flags:
    - Inflation ratio > 10  (too much money printing)
    - Net flow > 5 × previous 24 h average (sudden spike)
    - No events in the last hour despite being in a likely-active window
    """
    w1  = aggregate(3_600,  path)
    w24 = aggregate(86_400, path)

    warnings: list[str] = []

    if w24.total_burned > 0 and w24.inflation_ratio > 10:
        warnings.append(
            f"High inflation ratio: {w24.inflation_ratio:.1f}× "
            f"(minted {w24.total_minted:,} / burned {w24.total_burned:,})"
        )

    if w24.total_minted == 0 and w1.event_count == 0:
        warnings.append("No economy events recorded in the last 24 h — log may be stale.")

    if w1.total_minted > 0 and w24.total_minted > 0:
        avg_hourly = w24.total_minted / 24
        if w1.total_minted > avg_hourly * 5:
            warnings.append(
                f"1h mint ({w1.total_minted:,}) is 5× above 24h average "
                f"({int(avg_hourly):,}/h) — possible exploit spike."
            )

    return HealthStatus(
        healthy=len(warnings) == 0,
        warnings=warnings,
        window_1h=w1,
        window_24h=w24,
    )

"""
analysis.py — Offline economy curve analysis and report generation.

Run directly to produce a text report and optional PNG charts:

    python analysis.py                       # text report only
    python analysis.py --charts              # + PNG charts (requires matplotlib)
    python analysis.py --log path/to/log.csv # use a specific log file

Nothing here imports from bot.py or requires Discord to be running.
"""

import argparse
import math
import sys
from pathlib import Path

# Allow running from repo root or the economy/ subdirectory
sys.path.insert(0, str(Path(__file__).parent))

# Approximate tool table — mirrors TOOLS in game_data.py without importing it
_TOOL_SUMMARY = [
    ("Bare Hands",     0,             "money",  1,  1),
    ("Slingshot",      500,           "money",  2,  1),
    ("Hunting Knife",  2_000,         "money",  3,  1),
    ("Spear",          8_000,         "money",  4,  1),
    ("Shortbow",       25_000,        "money",  5,  2),
    ("Longbow",        80_000,        "money",  6,  2),
    ("Crossbow",       250_000,       "money",  7,  2),
    ("Musket",         750_000,       "money",  8,  2),
    ("Hunting Rifle",  2_000_000,     "money",  9,  3),
    ("Shotgun",        5_000_000,     "money", 10,  3),
    ("Sniper Rifle",   10_000_000,    "money", 11,  3),
    ("Tranq Gun",      25_000_000,    "money", 12,  3),
    ("Plasma Caster",  50_000_000,    "money", 13,  4),
    ("Gravity Trap",   100_000_000,   "money", 14,  4),
    ("Soul Snare",     250,           "gems",  15,  4),
    ("Void Bow",       350,           "gems",  16,  4),
    ("Celestial Lance",500,           "gems",  17,  5),
    ("Mythic Net",     700,           "gems",  18,  5),
    ("Dragon Cannon",  1_000,         "gems",  19,  5),
    ("Cosmic RPG",     1_500,         "gems",  20,  6),
]

# Map tool tier → highest biome that tier can access.
# A T9 tool can hunt anywhere with tool_tier_req <= 9, so we want the
# best (highest-value) such biome — that is the last biome whose
# tool_tier_req <= tool_tier.
_TIER_TO_BIOME: dict[int, str] = {}
for _tool_tier in range(1, 101):
    best = None
    for _b in BIOME_CURVES:
        if _b.tool_tier_req <= _tool_tier:
            best = _b.biome_key
    if best:
        _TIER_TO_BIOME[_tool_tier] = best


# ─────────────────────────────────────────────────────────────────────────────
# SECTION PRINTERS
# ─────────────────────────────────────────────────────────────────────────────

SEP = "─" * 78


def _header(title: str) -> str:
    pad = (78 - len(title) - 2) // 2
    return f"\n{'─' * pad} {title} {'─' * (78 - pad - len(title) - 2)}"


def section_xp_curve(levels: list[int] | None = None) -> list[str]:
    if levels is None:
        levels = [1, 10, 25, 50, 100, 200, 300, 500, 750, 1000, 1200]

    lines = [_header("XP CURVE")]
    lines.append(f"{'Level':>6}  {'XP to next':>14}  {'Cumulative XP':>16}  "
                 f"{'Hunts (min)':>12}  {'Hunts (max)':>12}")
    lines.append(SEP)

    for lvl in levels:
        step     = xp_for_level(lvl)
        total    = total_xp_to_level(lvl)
        h_min, h_max = hunts_to_level(lvl + 1)
        lines.append(
            f"{lvl:>6}  {step:>14,}  {total:>16,}  {h_min:>12,}  {h_max:>12,}"
        )

    # Key milestones
    lines.append("")
    lines.append("Key milestones:")
    for milestone in (100, 500, 1000):
        h_min, h_max = hunts_to_level(milestone)
        hrs_min = h_min / (3600 / HUNT_COOLDOWN_SECONDS)
        hrs_max = h_max / (3600 / HUNT_COOLDOWN_SECONDS)
        lines.append(
            f"  Level {milestone:>4}: {h_min:>10,}–{h_max:>10,} hunts  "
            f"({hrs_min:.0f}–{hrs_max:.0f} h at 3 s CD)"
        )
    return lines


def section_biome_income() -> list[str]:
    lines = [_header("BIOME INCOME ESTIMATE")]
    lines.append(
        f"{'Biome':<26}  {'Lvl':>4}  {'Avg val':>9}  {'EV/hunt':>10}  "
        f"{'2h active':>12}  {'Tier':>5}"
    )
    lines.append(SEP)

    for b in BIOME_CURVES:
        ev   = b.expected_sell_per_hunt(multi_catch=1, luck_pct=5, sell_boost_pct=0)
        inc2 = b.session_income(hours=2, multi_catch=1)
        lines.append(
            f"{b.biome_key:<26}  {b.level_req:>4}  "
            f"{b.avg_value:>9,.0f}  {ev:>10,.0f}  "
            f"{inc2:>12,.0f}  T{b.tool_tier_req:>2}"
        )

    lines.append("")
    lines.append("(Assumes: 1× multi-catch, 5% luck, 0% sell boost, 3 s cooldown)")
    return lines


def section_tool_payback() -> list[str]:
    lines = [_header("TOOL COST / PAYBACK")]
    lines.append(
        f"{'Tool':<20}  {'Price':>14}  {'Biome':>22}  "
        f"{'Income/hunt':>12}  {'Payback h':>10}  {'OK?':>5}"
    )
    lines.append(SEP)

    for name, price, currency, tier, multi in _TOOL_SUMMARY:
        biome_key = _TIER_TO_BIOME.get(tier, "village")
        result    = tool_payback(name, price, currency, biome_key, multi)
        if math.isnan(result.hours_to_payback):
            ph_str  = "  gem tool"
            ok_str  = "  n/a"
            inc_str = "  n/a"
        else:
            inc_str = f"{result.income_per_hunt:>12,.0f}"
            ph_str  = f"{result.hours_to_payback:>10.1f}"
            ok_str  = "  ✓" if result.is_reasonable() else "  ✗"

        price_str = f"◈ {price:,}" if currency == "money" else f"💎 {price}"
        lines.append(
            f"{name:<20}  {price_str:>14}  {biome_key:>22}  "
            f"{inc_str}  {ph_str}  {ok_str}"
        )

    lines.append("")
    lines.append("Payback threshold: 8 h (multi-catch/boosts reduce this significantly)")
    return lines


def section_idle_payback() -> list[str]:
    lines = [_header("IDLE STACK PAYBACK")]
    lines.append(
        f"{'Stack #':>8}  {'Cost':>12}  {'Rate/h (village L1)':>22}  "
        f"{'Payback h':>10}  {'Rate/h (celestial L1000)':>26}  {'Payback h':>10}"
    )
    lines.append(SEP)

    for stack in range(0, 10):
        cost      = 5_000 * (2 ** stack)
        rate_low  = idle_rate_per_hour(1,   1)    # village biome level, level 1 player
        rate_high = idle_rate_per_hour(1000, 1000) # celestial + level 1000
        pb_low    = cost / rate_low  if rate_low  else math.inf
        pb_high   = cost / rate_high if rate_high else math.inf
        lines.append(
            f"{stack + 1:>8}  {cost:>12,}  {rate_low:>22,}  "
            f"{pb_low:>10.1f}  {rate_high:>26,}  {pb_high:>10.2f}"
        )

    return lines


def section_daily_value() -> list[str]:
    lines = [_header("DAILY REWARD VALUE")]
    lines.append(f"{'Level':>6}  {'Avg money/day':>16}  {'Avg gems/day':>14}  "
                 f"{'30-day sum (money)':>20}  {'streak bonus @100':>20}")
    lines.append(SEP)

    for lvl in (1, 50, 100, 250, 500, 1000, 1200):
        tier     = get_daily_tier(lvl)
        ev       = tier.expected_daily(streak=0)
        ev100    = tier.expected_daily(streak=100)
        streak_ratio = ev100["money"] / ev["money"] if ev["money"] else 0
        lines.append(
            f"{lvl:>6}  {ev['money']:>16,.0f}  {ev['gems']:>14,.1f}  "
            f"{ev['money'] * 30:>20,.0f}  {streak_ratio:>19.2f}×"
        )

    return lines


def section_prestige_gate() -> list[str]:
    lines = [_header("PRESTIGE GATE ESTIMATE")]
    scenarios = [
        # (label, hunts_per_hour, multi_catch, xp_boost_pct, luck_pct, sell_boost_pct)
        # Early game: 3 s CD, T3 tool (1× catch), no boosts
        ("Early game (T3, 1× catch, 0% boost)",  1_200, 1,  0,  5,  0),
        # Mid game: T9 (3× catch), 30% xp boost from upgrades + tribe
        ("Mid game  (T9, 3× catch, 30% boost)",  1_200, 3, 30, 15, 20),
        # Late game: T15+ (4× catch), vehicle (-0.3 s CD ~= 1333/hr), heavy boosts
        ("Late game (T15, 4× catch, 80% boost)", 1_333, 4, 80, 35, 50),
    ]
    for label, hunts_ph, multi, xp_b, luck, sell_b in scenarios:
        result = time_to_prestige(
            hunts_per_hour=hunts_ph,
            multi_catch=multi,
            xp_boost_pct=xp_b,
            luck_pct=luck,
            sell_boost_pct=sell_b,
        )
        lines.append(f"  {label}")
        lines.append(
            f"    Level gate: {result['level_hours']:>8,.0f} h  |  "
            f"Money gate: {result['money_hours']:>8,.0f} h  |  "
            f"Bottleneck: {result['bottleneck']}  |  "
            f"Total: {result['total_hours']:,.0f} h"
        )
    lines.append("")
    lines.append(f"  Prestige requires: Level {PRESTIGE_MIN_LEVEL:,} + "
                 f"◈ {PRESTIGE_MIN_MONEY:,}")
    return lines


def section_economy_live(log_path: str) -> list[str]:
    lines = [_header("LIVE ECONOMY HEALTH")]
    status = health_check(log_path)
    lines += status.as_discord_block().splitlines()
    return lines


def section_balance_snapshots() -> list[str]:
    lines = [_header("BALANCE DISTRIBUTION HISTORY")]
    snaps = list(iter_snapshots())
    if not snaps:
        lines.append("  No snapshot data found.  Run capture_balance_snapshot() periodically.")
        return lines

    lines.append(f"{'Date':>12}  {'p10':>12}  {'p50':>12}  {'p90':>12}  "
                 f"{'p99':>12}  {'Total':>18}  {'Players':>8}")
    lines.append(SEP)
    import datetime
    for s in snaps[-20:]:   # last 20 snapshots
        dt = datetime.datetime.fromtimestamp(s["ts"]).strftime("%Y-%m-%d")
        lines.append(
            f"{dt:>12}  {s['p10']:>12,}  {s['p50']:>12,}  {s['p90']:>12,}  "
            f"{s['p99']:>12,}  {s['total']:>18,}  {s['player_count']:>8,}"
        )
    return lines


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONAL CHART GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_charts(output_dir: str = ".") -> list[str]:
    """Generate PNG charts; returns list of file paths created."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return []

    paths: list[str] = []
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── Chart 1: XP curve ──────────────────────────────────────────────────
    levels   = list(range(1, 1_201))
    xp_steps = [xp_for_level(l) for l in levels]
    cum_xp   = [total_xp_to_level(l) for l in levels]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    ax1.plot(levels, xp_steps, color="#2ECC71", linewidth=1.5)
    ax1.set_title("XP Required Per Level")
    ax1.set_xlabel("Level")
    ax1.set_ylabel("XP to next level")
    ax1.set_yscale("log")
    ax1.grid(True, alpha=0.3)
    for milestone in (100, 500, 1000):
        ax1.axvline(milestone, color="red", linestyle="--", alpha=0.5, label=f"L{milestone}")
    ax1.legend()

    ax2.plot(levels, [c / 1e6 for c in cum_xp], color="#3498DB", linewidth=1.5)
    ax2.set_title("Cumulative XP to Reach Level")
    ax2.set_xlabel("Level")
    ax2.set_ylabel("Cumulative XP (millions)")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    p1 = str(out / "xp_curve.png")
    plt.savefig(p1, dpi=120)
    plt.close()
    paths.append(p1)

    # ── Chart 2: Biome income ladder ───────────────────────────────────────
    biome_names   = [b.biome_key.replace("_", " ").title() for b in BIOME_CURVES]
    income_1h_1x  = [b.session_income(1, multi_catch=1) for b in BIOME_CURVES]
    income_1h_5x  = [b.session_income(1, multi_catch=5, luck_pct=50, sell_boost_pct=80)
                     for b in BIOME_CURVES]

    x = np.arange(len(biome_names))
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x - 0.2, income_1h_1x, 0.4, label="Base (1× catch)", color="#2ECC71", alpha=0.8)
    ax.bar(x + 0.2, income_1h_5x, 0.4, label="Max (5× catch, 50% luck, 80% sell)",
           color="#F1C40F", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(biome_names, rotation=35, ha="right", fontsize=8)
    ax.set_yscale("log")
    ax.set_ylabel("Income per hour (◈)")
    ax.set_title("Biome Income per Hour")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    p2 = str(out / "biome_income.png")
    plt.savefig(p2, dpi=120)
    plt.close()
    paths.append(p2)

    # ── Chart 3: Tool payback heatmap ──────────────────────────────────────
    money_tools = [(n, p, t, m) for n, p, c, t, m in _TOOL_SUMMARY if c == "money" and p > 0]
    tool_names  = [t[0] for t in money_tools]
    pb_hours    = []
    for name, price, tier, multi in money_tools:
        biome = _TIER_TO_BIOME.get(tier, "village")
        r = tool_payback(name, price, "money", biome, multi)
        pb_hours.append(min(r.hours_to_payback, 100))   # cap at 100 h for readability

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#2ECC71" if h <= 8 else "#F39C12" if h <= 24 else "#E74C3C" for h in pb_hours]
    ax.barh(tool_names, pb_hours, color=colors)
    ax.axvline(8, color="green",  linestyle="--", alpha=0.7, label="8 h (good)")
    ax.axvline(24, color="orange", linestyle="--", alpha=0.7, label="24 h (marginal)")
    ax.set_xlabel("Hours to payback (capped at 100)")
    ax.set_title("Tool Payback Time (no boosts)")
    ax.legend()
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    p3 = str(out / "tool_payback.png")
    plt.savefig(p3, dpi=120)
    plt.close()
    paths.append(p3)

    return paths


# ─────────────────────────────────────────────────────────────────────────────
# FULL REPORT
# ─────────────────────────────────────────────────────────────────────────────

def full_report(log_path: str = ECONOMY_LOG, charts: bool = False) -> str:
    sections = [
        section_xp_curve(),
        section_biome_income(),
        section_tool_payback(),
        section_idle_payback(),
        section_daily_value(),
        section_prestige_gate(),
        section_economy_live(log_path),
        section_balance_snapshots(),
    ]
    lines = [f"IDLE HUNTER — ECONOMY ANALYSIS REPORT", "=" * 78]
    for sec in sections:
        lines += sec

    if charts:
        generated = generate_charts()
        lines.append(_header("CHARTS"))
        if generated:
            for p in generated:
                lines.append(f"  Saved: {p}")
        else:
            lines.append("  matplotlib not available — install with: pip install matplotlib")

    lines.append("\n" + "=" * 78)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Idle Hunter economy analysis")
    parser.add_argument("--log",    default=ECONOMY_LOG, help="Path to economy_log.csv")
    parser.add_argument("--charts", action="store_true",  help="Generate PNG charts")
    parser.add_argument("--out",    default="analysis_output", help="Chart output directory")
    args = parser.parse_args()

    report = full_report(log_path=args.log, charts=args.charts)
    print(report)