"""
app.py
Powers the bot. [END]
"""
import asyncio, discord, random, time, json, string, requests, secrets, logging, aiosqlite
from discord.http import Route
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from collections import Counter, deque
from game_data import (
    # Biomes
    BIOME_LEVELS, BIOME_EMOJIS, BIOME_NAMES, BIOME_ANIMALS, BIOME_TOOL_TIER,
    BIOME_REGION, BIOME_MYTHS, WORLD_MAP_URL, biome_region, biome_location_line,
    # World conditions (Idle Hunter V2)
    WORLD_CONDITIONS, WORLD_CONDITION_SLOTS,
    MYTH_ENCOUNTER_MAX_WORLD, RARE_CATCH_MAX_WORLD,
    SIGHTING_CLUE_FLAVORS,
    # Tracking (Idle Hunter V2)
    TRACKING_ACTIONS, TRACKING_SCENES, TRACKING_EXPIRE_MIN,
    # Virality (Idle Hunter V2)
    SHARE_RARITY_MIN, SHARE_STORE_TTL,
    REFERRAL_QUALIFY_LEVEL, REFERRAL_QUALIFY_HUNTS, REFERRAL_QUALIFY_DAYS,
    REFERRAL_CODE_MAX_LEVEL, REFERRAL_QUALIFY_GEMS, REFERRAL_MILESTONES,
    # Multiplayer (Idle Hunter V2)
    GUILD_GOAL_PER_MEMBER, GUILD_GOAL_MIN, GUILD_GOAL_MAX, GUILD_GOAL_CONTRIB_MIN,
    TRIBE_EXPEDITION_MIN_MEMBERS, TRIBE_EXPEDITION_VOTE_MIN, TRIBE_EXPEDITIONS,
    TRIBE_EXPEDITION_GOAL_PER_MEMBER, TRIBE_EXPEDITION_POINTS, TRIBE_EXPEDITION_COOLDOWN_H,
    # Player HP + animal combat (Idle Hunter V2.1)
    PLAYER_BASE_HP, HP_REGEN_PER_MIN, CAMP_HP_REGEN_PER_MIN,
    KO_RECOVERY_HP, ROOKIE_KO_RECOVERY_HP,
    HEALING_ITEMS, MIN_ENCOUNTER_HUNTS_GAP,
    ANIMAL_ENCOUNTER_REWARD_MULT, ANIMAL_ENCOUNTER_XP_MULT, ANIMAL_ENCOUNTER_HEALTHY_BONUS,
    POWER_ATTACK_ACCURACY, POWER_ATTACK_DAMAGE_MULT,
    TRIAL_TOOL_MIN, TRIAL_TOOL, ROOKIE_GOALS,
    HUNTERS_PATH_STEPS, HUNTERS_PATH_REWARD_GEMS, HUNTERS_PATH_REWARD_TITLE,
    HUNTERS_PATH_MYTH_UNLOCK_STEP,
    animal_combat_stats, animal_encounter_chance, encounter_priority,
    tool_combat_damage, tool_combat_accuracy,
    # Animals
    ANIMAL_DATA, ANIMAL_EMOJI, animal_emoji,
    # Mythical creatures (mythic tier / boss roster)
    MYTHIC_CREATURES, MYTH_DROPS, creature_emoji,
    TROPHY_EFFECTS, TROPHY_SLOT_THRESHOLDS, trophy_emoji,
    # Tools
    TOOLS, get_tool_tier, can_hunt_biome, get_all_tools_sorted,
    tool_needs_ammo, get_tool_ammo_type, ammo_compatible_with_tool, tool_emoji,
    # Ammo
    AMMO, AMMO_TYPE_TOOLS, AMMO_TYPE_LABELS, AMMO_MAX_STACK, ammo_emoji,
    # Vehicles
    VEHICLES,
    # Shop
    SHOP_BOOST_ITEMS, shop_boost_price,
    # Daily
    DAILY_TIERS, get_daily_tier,
    # Onboarding (Idle Hunter V2)
    STARTER_PACKS,
    # Colors
    COLORS, COLOR_LABELS, COLOR_EMOJIS, COLOR_DESCRIPTIONS, color_display_name,
    # XP
    xp_for_level, total_xp_to_level,
    # Gamble
    ROULETTE_COLORS, ROULETTE_WEIGHTS, ROULETTE_BET_TYPES, RPS_CHOICES, RPS_BEATS, SLOT_BIOME_CONFIG,
    # Rarity icons
    RARITY_ICONS, RARITY_KEYS, SHARD_ICONS, CRYSTAL_ICONS, GEMSTONE_ICONS,
    # Emojis
    UPGRADE_EMOJI, TRIBE_EMOJIS, USER_EMOJIS, EMOJI, emoji, emoji_partial, adopt_named_emojis,
    # Tips
    TIPS,
    # Commands
    COMMAND_ID,
    # Badges
    BADGES, badge_emoji, SPECIAL_BADGES, badge_meta,
    # Achievements
    ACHIEVEMENTS, ACHIEVEMENT_TITLES,
    # Helpers
    today_utc, parse_amount, generate_verify_code, init_verify, card_emoji,
    # Rules
    RULES,
    # Hunting Crates + crafting economy
    CRATE_TIERS, CRATE_REWARDS, open_crate, roll_catch_drops,
    RARITY_CRATE, CRATE_RARITY, CRATE_TIER_WEIGHTS, roll_crate_rarity,
    MAX_PERSONAL_BOOST, MAX_TRIBE_BOOST,
    CRYSTAL_SHARD_COST, CRYSTAL_CRAFT_SECONDS, CRAFT_QUEUE_MAX, CRATE_CRYSTAL_COST,
    CRATE_GEMSTONE_CHANCE, MYTH_SHARD_KILL_CHANCE,
    # Quests
    QUEST_TEMPLATES, QUEST_TIERS, QUESTS_PER_DAY, QUESTS_MAX,
    WEEKLY_QUEST_TEMPLATES, QUESTS_PER_WEEK, WEEKLY_QUESTS_MAX, DAILY_QUEST_MILESTONES,
    generate_quest, roll_daily_quests, roll_weekly_quests, get_quest_tier,
    # Tribe progression
    TRIBE_XP_HUNT, TRIBE_XP_HUNT_CAP_DAY, TRIBE_XP_DAILY, TRIBE_XP_TASK,
    TRIBE_XP_TASK_CAP_DAY, TRIBE_XP_CONTRACT, TRIBE_LEVEL_CAP, tribe_xp_to_next,
    tribe_member_cap, TRIBE_UNLOCK_CONTRACTS, TRIBE_RECRUIT_PROBATION_H,
    TRIBE_REJOIN_COOLDOWN_H, TRIBE_CONTRACT_MIN_GROUP, TRIBE_LOG_MAX, TRIBE_CONTRACTS,
    # Global events
    EVENT_HOURS, FOX_ATTEMPTS_DAY, FOX_LEAD_START, FOX_TITLE_AT, FOX_ROUTES, FOX_SHOP,
    SHIP_DIVES_DAY, SHIP_SPOTS, SHIP_SHOP,
    DUCK_BREAD_DAY, DUCK_FEED_CHUNK, DUCK_GOAL_BASE, DUCK_CONTRIB_MIN, DUCK_ENDINGS,
)
import backend
from contextlib import asynccontextmanager
from backend import (
    init_databases, close_databases, bulk_save_users,
    delete_user as _backend_delete_user,
    bulk_save_tribes, register_save_callbacks,
    user_transaction as _backend_user_transaction,
    user_tribe_transaction as _backend_user_tribe_transaction,
    multi_user_transaction as _backend_multi_user_transaction,
    tribe_only_transaction, migrate_all_users,
    register_state_refs,
    claim_instance_lock, refresh_instance_lock, release_instance_lock,
    log_economy_event, SessionManager, RateLimiter,
    log_analytics as _backend_log_analytics,
    # Also import these if you need them:
    CURRENT_SCHEMA, User, Tribe, TribeRoles, VerifyState, Boosts, IdleState,
    Stats, BanRecord, AnimalRecord, AchievementProgress, BadgeState, GiftMail,
    get_user_lock, tribe_lock, state_lock
)
from dotenv import load_dotenv
import os
load_dotenv("token.env")

def ph(e: str) -> str:
    """Pass an icon through unchanged — plain unicode or a registered custom
    <:name:id>/<a:name:id> emoji, doesn't matter, both render fine as-is.
    Used to read as an obvious backtick-wrapped placeholder for uncustomized
    icons during development; dropped ahead of public promotion so the bot
    doesn't show code-looking text where an icon should be. Defined this
    early so module-level literals (ADMIN_BUFF_EVENT, etc.) can use it too."""
    return e


# BOT_TOKEN in token.env is for the original bot (minimize data loss)!!!
BOT_TOKEN = os.getenv("TOKEN")

logger = logging.getLogger(__name__)

# Unique per running process. If two instances are live on the same token you'll
# see two different INSTANCE_IDs in the host logs — that is the cause of every
# "message sent twice" / "double DM" / "Report not found" symptom.
import socket as _socket
INSTANCE_ID = f"{_socket.gethostname()}:{os.getpid()}:{secrets.token_hex(3)}"
print(f"🥾 Idle Hunter process starting — INSTANCE_ID={INSTANCE_ID}")

intents = discord.Intents.default()
# message_content is deliberately OFF: the bot is slash/component-only (no
# on_message, no prefix commands) and the intent needs Discord approval past
# 100 servers. `members` stays on — server leaderboards read guild.members.
intents.message_content = False
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

# ─────────────────────────────────────────────
# ADMINS
# ─────────────────────────────────────────────

BOT_ADMIN_ID = [
    "1286458710146940980",
]

def is_admin(interaction: discord.Interaction) -> bool:
    return str(interaction.user.id) in BOT_ADMIN_ID

BOT_OWNER_ID = [
    "1286458710146940980",
]

# Channel + role that /update entries and event launches are broadcast to.
ANNOUNCE_CHANNEL_ID = 1546375680290332704
ANNOUNCE_ROLE_ID    = 1548369932453019730   # "Bot updates"

# World sightings + world-condition shifts ("weather") — same channel, two roles.
ALERTS_CHANNEL_ID   = 1548367413517484072
SIGHTING_ROLE_ID    = 1548369979622297703   # "Bot alerts"
WORLD_EVENT_ROLE_ID = 1548371267365769236   # "Bot events"

# Weekly competitive-leaderboard recap.
COMPETITIVE_CHANNEL_ID = 1548375657581518929
COMPETITIVE_ROLE_ID    = 1548371231852732578   # "Competitive"

BETA_TESTER_ROLE_ID = 1548371207110398032   # not wired to anything yet

def test_token(token, name):
    url = "https://discord.com/api/v10/users/@me"
    headers = {"Authorization": f"Bot {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            print(f"✅ {name} token is valid")
            return True
        else:
            print(f"❌ {name} token failed: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ {name} token error: {e}")
        return False

# ─────────────────────────────────────────────
# GLOBALS
# ─────────────────────────────────────────────

DEV_MAIL              = ""
TIP_CHANCE            = 10
TIP_COOLDOWN_SEC      = 10 * 60   # a tip can fire at most this often, regardless of TIP_CHANCE
IDLE_COST             = 5_000
IDLE_STACK_MULTIPLIER = 2
# Animals actually reachable in some biome right now (the Earth-biome re-theme
# retired the old rosters but kept their ANIMAL_DATA rows for back-compat).
_CATCHABLE_ANIMALS = {a for lst in BIOME_ANIMALS.values() for a in lst}

HUNT_COOLDOWN         = 3
MYTH_ENCOUNTER_BASE   = 0.005   # base per-hunt chance to meet a cryptid (before luck / event)
MYTH_ENCOUNTER_LUCK   = 0.02    # extra chance approached asymptotically with luck
MYTH_ENCOUNTER_MAX    = 0.05    # hard cap after luck + event multiplier
MYTH_KILL_BASE        = 25      # base KILL success % (before tool tier / luck / difficulty)
MYTH_RUN_BASE         = 60      # base clean-getaway % on flee
MYTH_DEATH_LOSS_CASH  = 0.02    # losing the fight costs min(2% of cash, 3% of the bounty)
MYTH_DEATH_LOSS_VALUE = 0.03

# ── Mythic boss fight (turn-based) ──────────────────────────
FIGHT_PLAYER_HP        = 100
FIGHT_MONSTER_HP_BASE  = 74      # + biome tool-tier * FIGHT_MONSTER_HP_TIER
FIGHT_MONSTER_HP_TIER  = 4
FIGHT_SHOOT_AMMO       = 100     # rounds burned per Shoot (needs this many to fire)

# A player's FIRST mythic kill ever is a career-defining moment and pays out
# like one; every kill after that is real money but nowhere near repeatable-
# forever money — a flat 100M/1000 gems per kill would let anyone who farms
# a handful of mythics eclipse the entire rest of the economy.
MYTH_FIRST_KILL_BOUNTY   = 100_000_000
MYTH_FIRST_KILL_GEMS     = 1_000
MYTH_REPEAT_BOUNTY_RANGE = (15_000_000, 25_000_000)
MYTH_REPEAT_GEMS_RANGE   = (100, 250)
MYTH_XP_MULT             = 2.0   # mythic kills should out-XP a lucky danger-encounter roll
PRESTIGE_MIN_LEVEL    = 1000
PRESTIGE_MIN_MONEY    = 1_000_000_000
TRAVEL_MAX_MIN        = 60      # travel time between opposite edges of the world map
MAX_LOG_ENTRIES       = 50
INV_DISPLAY_MAX       = 10
AMMO_MAX_STACK        = 9_999
LOTTERY_TICKET_COST   = 10_000
GAMBLE_COOLDOWN       = 2       # seconds between wagers (0 during Admin's Day Off)
V2_FLAGS              = 32768
SUGGESTION_CHANNEL_ID = 1503581602234765322
BAN_APPEAL_CHANNEL_ID = 1503975028570718298
REPORTS_CHANNEL_ID    = 1503975073797771284
LOTTERY_CHANNEL_ID    = 1505064052391673958

# ─────────────────────────────────────────────
# FEATURE FLAGS  ·  Idle Hunter V2 rollout
# ─────────────────────────────────────────────
# Every V2 system is gated so a broken piece can be switched off from the host
# env without reverting code. Default ON; set e.g. FEATURE_TRACKING=0 to disable.
def _flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip() not in ("0", "false", "False", "no", "off", "")

FEATURE_ANALYTICS        = _flag("FEATURE_ANALYTICS")
FEATURE_ONBOARDING_V2    = _flag("FEATURE_ONBOARDING_V2")
FEATURE_WORLD_CONDITIONS = _flag("FEATURE_WORLD_CONDITIONS")
FEATURE_TRACKING         = _flag("FEATURE_TRACKING")
FEATURE_WORLD_SIGHTINGS  = _flag("FEATURE_WORLD_SIGHTINGS")
FEATURE_SHARE_CARDS      = _flag("FEATURE_SHARE_CARDS")
FEATURE_AUTO_EVENTS      = _flag("FEATURE_AUTO_EVENTS", "0")   # off until an admin opts in
FEATURE_EXPEDITIONS      = _flag("FEATURE_EXPEDITIONS")
FEATURE_SERVER_GOALS     = _flag("FEATURE_SERVER_GOALS")
FEATURE_REFERRALS        = _flag("FEATURE_REFERRALS")
FEATURE_ANIMAL_COMBAT    = _flag("FEATURE_ANIMAL_COMBAT")
FEATURE_HUNTERS_PATH     = _flag("FEATURE_HUNTERS_PATH")

# Feature-gated background loops defined later in the file register themselves
# here; on_ready starts every entry. Keeps task wiring next to its own code.
_V2_BACKGROUND_TASKS: list = []

# ─────────────────────────────────────────────
# ANALYTICS  ·  thin wrapper over backend.log_analytics
# ─────────────────────────────────────────────
def analytics(user_id, event: str, **meta) -> None:
    """Fire-and-forget funnel/retention event. Never raises."""
    if not FEATURE_ANALYTICS:
        return
    try:
        _backend_log_analytics(str(user_id) if user_id is not None else None,
                               event, (meta or None))
    except Exception:
        pass

# ─────────────────────────────────────────────
# INVITE URL  ·  least-privilege, NOT Administrator
# ─────────────────────────────────────────────
# Exactly the permissions Idle Hunter uses: read/post in a channel, post
# component containers, attach the world-map image, and render its custom emoji.
INVITE_PERMISSIONS = discord.Permissions(
    view_channel=True,
    send_messages=True,
    send_messages_in_threads=True,
    embed_links=True,
    attach_files=True,
    use_external_emojis=True,
    read_message_history=True,
)

def invite_url() -> str:
    cid = getattr(getattr(bot, "user", None), "id", None) or os.getenv("APPLICATION_ID", "")
    return discord.utils.oauth_url(
        cid, permissions=INVITE_PERMISSIONS,
        scopes=("bot", "applications.commands"),
    )

# ─────────────────────────────────────────────
# GLOBAL EVENTS  ·  admin-triggered, one at a time
# ─────────────────────────────────────────────
# `_active_event` (one slot) holds the running event, persisted in runtime_state.
# EVENTS is the registry the admin picks from. `kind`:
#   "buff"      — pure ev_* multipliers, no per-player mini-game (Admin's Day Off)
#   "activity"  — per-player mini-game (Thieving Fox, Shipwreck Scramble)
#   "community" — shared goal + vote (Duck Takeover)

ADMIN_BUFF_HOURS = 24

ADMIN_BUFF_EVENT = {
    "key":   "admin_buff",
    "name":  "Admin's Day Off",
    "emoji": "🎉",
    "kind":  "buff",
    "hours": ADMIN_BUFF_HOURS,
    "blurb": "The admin clocked out and left every debug toggle flipped **ON**. "
             "Nobody's watching the numbers. Enjoy it while it lasts, hunter.",
    "perks": [
        f"{emoji('clock')} Hunt cooldown **halved**",
        f"{emoji('plane')} Travel is **instant**",
        f"{ph('🔨')} Crystal crafting is **instant**",
        f"{ph('🔫')} Ammo is **not consumed** while hunting",
        f"{ph('💲')} Sell price **×2**",
        f"{ph(emoji('sparkles'))} XP **×2**",
        f"{ph(emoji('idle_camp'))} Idle camp: **×2** catch rate & **×2** storage",
        f"{ph(emoji('gem'))} Shard drops **10% → 25%**, crate drops **5% → 15%**",
        f"{ph('📅')} Daily reward **×2**",
        f"{emoji('shop')} Shop **50% off** everything",
        f"{emoji('dice')} Gamble: **no cooldown between wagers**",
        f"{ph('👹')} Mythic encounters **×3**, kill chance **+20**",
        f"{emoji('gift')} A one-time **bonus check** the first time you play",
    ],
    "gift_money": 5_000_000,
    "gift_gems":  75,
    "gift_crate": "Rare Crate",
}

EVENTS = {
    "admin_buff": ADMIN_BUFF_EVENT,
    "thieving_fox": {
        "key": "thieving_fox", "name": "The Thieving Fox", "emoji": "🦊",
        "kind": "activity", "hours": EVENT_HOURS,
        "blurb": "A fox nicked an event parcel and bolted. It never touches what you already own.",
        "actions": [f"{emoji('bow')} Hunt to pick up its trail", f"{emoji('trophy')} Run it down before it goes to ground"],
    },
    "shipwreck": {
        "key": "shipwreck", "name": "Shipwreck Scramble", "emoji": "🏴‍☠️",
        "kind": "activity", "hours": EVENT_HOURS,
        "blurb": "A wreck washed up on the Sunken Coast, and it's yours to strip for parts.",
        "actions": [f"{emoji('bow')} Hunt in the Sunken Coast to dive the wreck",
                    f"{emoji('money_bag')} Go deeper for a better haul — at higher risk"],
    },
    "duck": {
        "key": "duck", "name": "Duck Takeover", "emoji": "🦆",
        "kind": "community", "hours": EVENT_HOURS,
        "blurb": "The shop has been overrun. The ducks demand bread.",
        "actions": [f"{emoji('bow')} Hunt to find Bread Crumbs",
                    "`🥖` Feed the flock to push the community goal",
                    "`🗳️` Vote to decide how the takeover ends"],
    },
}

_active_event: dict | None = None   # {"key","name","started_ts","ends_ts","by",…} or None

def get_active_event() -> dict | None:
    """The running event, or None. Auto-clears when the window closes."""
    global _active_event
    if _active_event and time.time() >= _active_event.get("ends_ts", 0):
        _active_event = None
    return _active_event

def active_event_key() -> str:
    ev = get_active_event()
    return ev.get("key", "") if ev else ""

def active_event_def() -> dict:
    return EVENTS.get(active_event_key(), {})

def admin_buff_active() -> bool:
    return active_event_key() == "admin_buff"

def start_event(key: str, started_by: str = "system", automatic: bool = False) -> dict | None:
    global _active_event
    spec = EVENTS.get(key)
    if not spec:
        return None
    now = time.time()
    ev = {
        "key": key, "name": spec["name"], "kind": spec["kind"],
        "started_ts": now, "ends_ts": now + spec.get("hours", 24) * 3600,
        "by": str(started_by), "automatic": bool(automatic),
    }
    if spec["kind"] == "community":
        ev["community"] = {"progress": 0, "goal": _event_community_goal()}
        ev["votes"]  = {opt: 0 for opt in DUCK_ENDINGS}
        ev["voters"] = []
        ev["ending"] = None
    _active_event = ev
    return ev

def start_admin_buff(admin_id: str) -> dict:      # kept for back-compat
    return start_event("admin_buff", admin_id)

def stop_active_event() -> None:
    global _active_event
    _active_event = None

def _event_community_goal() -> int:
    now = time.time()
    recent = sum(1 for d in data.values() if now - d.get("_last_hunt_ts", 0) < 48 * 3600)
    return DUCK_GOAL_BASE * max(5, recent)

def _player_event(user_id: str) -> dict | None:
    """The player's per-event mini-game state, lazily wiped when the event
    changes. None when no activity/community event is running."""
    ev = get_active_event()
    if not ev or ev.get("kind") == "buff":
        return None
    st = data[user_id].setdefault("event", {})
    if st.get("started") != ev["started_ts"] or st.get("key") != ev["key"]:
        st.clear()
        st.update({"key": ev["key"], "started": ev["started_ts"], "journal": 0})
        data[user_id]["event_day"] = {}   # fresh daily attempts for the new event
        mark_user_dirty(user_id)
    return st

def _event_attempt(user_id: str, cap: int) -> bool:
    """Consume one daily rewarded attempt. Returns True if this one is still
    within `cap` (grants rewards), False if it's an over-cap 'journal only' run."""
    today = today_utc()
    ed = data[user_id].setdefault("event_day", {})
    if ed.get("tag") != today:
        ed.clear(); ed.update({"tag": today, "n": 0})
    ed["n"] += 1
    return ed["n"] <= cap

def _event_attempts_left(user_id: str, cap: int) -> int:
    ed = data[user_id].get("event_day", {})
    n = ed.get("n", 0) if ed.get("tag") == today_utc() else 0
    return max(0, cap - n)

def _grant_special_badge(user_id: str, key: str) -> bool:
    sb = data[user_id].setdefault("special_badges", [])
    if key in sb:
        return False
    sb.append(key)
    return True

def _grant_event_reward(user_id: str, *, title: str = "", badge: str = "") -> list[str]:
    """Idempotently grant an event title / cosmetic badge. Returns what was new."""
    got = []
    if title:
        et = data[user_id].setdefault("earned_titles", [])
        if title not in et:
            et.append(title); got.append(f'title **"{title}"**')
    if badge and _grant_special_badge(user_id, badge):
        got.append(f"the **{SPECIAL_BADGES.get(badge, {}).get('label', badge)}** badge")
    return got

async def _event_hunt_hook(user_id: str) -> None:
    """Passive event progress from a successful hunt (Duck Takeover bread crumbs)."""
    if active_event_key() != "duck":
        return
    async with user_transaction(user_id):
        st = _player_event(user_id)
        if st is None:
            return
        ed = data[user_id].setdefault("event_day", {})
        if ed.get("tag") != today_utc():
            ed.clear(); ed.update({"tag": today_utc(), "n": 0})
        banked_today = ed.get("bread", 0)
        if banked_today >= DUCK_BREAD_DAY:
            return
        crumbs = min(random.randint(1, 3), DUCK_BREAD_DAY - banked_today)
        ed["bread"] = banked_today + crumbs
        st["bread"] = st.get("bread", 0) + crumbs

# Convenience multipliers — all 1×/no-op unless the buff event is live.
def ev_sell_mult() -> float:      return 2.0 if admin_buff_active() else 1.0
def ev_xp_mult() -> float:        return 2.0 if admin_buff_active() else 1.0
def ev_daily_mult() -> float:     return 2.0 if admin_buff_active() else 1.0
def ev_idle_rate_mult() -> float: return 2.0 if admin_buff_active() else 1.0
def ev_idle_cap_mult() -> float:  return 2.0 if admin_buff_active() else 1.0
def ev_hunt_cd_mult() -> float:   return 0.5 if admin_buff_active() else 1.0
def ev_myth_encounter_mult() -> float: return 3.0 if admin_buff_active() else 1.0
def ev_myth_kill_bonus() -> int:  return 20 if admin_buff_active() else 0
def ev_shard_chance():            return 0.25 if admin_buff_active() else None   # None = use default
def ev_crate_chance():            return 0.15 if admin_buff_active() else None
def ev_ammo_free() -> bool:       return admin_buff_active()
def ev_travel_free() -> bool:     return admin_buff_active()
def ev_craft_instant() -> bool:   return admin_buff_active()

def ev_price(base: int) -> int:
    """Shop price after the event 50%-off, floored at 1."""
    return max(1, base // 2) if admin_buff_active() else base

def event_banner_line() -> str:
    ev = get_active_event()
    if not ev:
        return ""
    spec = EVENTS.get(ev["key"], ADMIN_BUFF_EVENT)
    return f"{spec.get('emoji', emoji('party_popper'))} **{ev['name']}** is live — ends <t:{int(ev['ends_ts'])}:R>"

# ═══════════════════════════════════════════════════════════════
# WORLD CONDITIONS  ·  rotating per-region wildlife/weather state (V2)
# ═══════════════════════════════════════════════════════════════
# Global, not per-player. `_world_conditions[biome] = {"key","started_ts","ends_ts"}`.
# Persisted in runtime_state.json; rotated by world_condition_task (every 10 min).
# One helper — get_world_modifiers(biome) — is the ONLY place hunt code reads it.

_world_conditions: dict[str, dict] = {}

# Declared here so runtime-state encode/load can see them; populated in the
# World Sightings (Phase 16) and Automatic Events (Phase 25) sprints.
_active_sighting: dict | None = None
_last_sighting_end: float = 0.0
_event_scheduler: dict = {"last_event_ts": 0.0, "next_event_ts": 0.0, "recent_keys": []}

def _prune_world_conditions() -> None:
    now = time.time()
    for b in [b for b, c in _world_conditions.items() if c.get("ends_ts", 0) <= now]:
        _world_conditions.pop(b, None)

def active_world_condition(biome: str) -> dict | None:
    """The live condition dict for a biome (with 'spec' merged in), or None."""
    if not FEATURE_WORLD_CONDITIONS:
        return None
    c = _world_conditions.get(biome)
    if not c or c.get("ends_ts", 0) <= time.time():
        return None
    spec = WORLD_CONDITIONS.get(c.get("key", ""), {})
    if not spec:
        return None
    return {**c, "spec": spec}

def get_world_modifiers(biome: str) -> dict:
    """{rare_mult, myth_mult, sell_mult, xp_mult} for a biome — all 1.0 when Normal.
    The single read point for world-condition effects in run_hunt / idle."""
    out = {"rare_mult": 1.0, "myth_mult": 1.0, "sell_mult": 1.0, "xp_mult": 1.0}
    c = active_world_condition(biome)
    if not c:
        return out
    spec = c["spec"]
    for k in out:
        try:
            out[k] = float(spec.get(k, 1.0))
        except (TypeError, ValueError):
            pass
    return out

def world_condition_line(biome: str) -> str:
    """One-line summary for menu / hunt panels — '' when Normal."""
    c = active_world_condition(biome)
    if not c:
        return ""
    spec = c["spec"]
    fx = []
    if spec.get("rare_mult", 1) > 1: fx.append(f"rare +{round((spec['rare_mult']-1)*100)}%")
    if spec.get("myth_mult", 1) > 1: fx.append(f"mythic +{round((spec['myth_mult']-1)*100)}%")
    if spec.get("sell_mult", 1) > 1: fx.append(f"sell +{round((spec['sell_mult']-1)*100)}%")
    if spec.get("xp_mult",   1) > 1: fx.append(f"XP +{round((spec['xp_mult']-1)*100)}%")
    tail = f" · {' · '.join(fx)}" if fx else ""
    return f"{spec['emoji']} **{spec['name']}** — ends <t:{int(c['ends_ts'])}:R>{tail}"

# ═══════════════════════════════════════════════════════════════
# WORLD SIGHTINGS  ·  a specific legend surfaces somewhere (V2, Phase 16-18)
# ═══════════════════════════════════════════════════════════════
# Distinct from world conditions: ONE global sighting at a time, in one region,
# for a set window. It starts hidden — players hunting there generate clues; at
# SIGHTING_CLUE_GOAL the creature is revealed and its encounter chance in that
# region jumps. Persisted in runtime_state.json via _active_sighting.

SIGHTING_CLUE_GOAL      = 50
SIGHTING_MIN_MIN        = 45     # discovery-phase length: 45-90 min
SIGHTING_MAX_MIN        = 90
SIGHTING_GAP_MIN_H      = 3      # min hours between sightings

# Post-reveal: the sighted creature becomes the ONLY thing that can appear in
# its biome, for a fixed window, at a flat pity-protected chance — replacing
# the old "everything in the biome gets a small multiplier" approach, which
# let the tracked creature (or its neighbors) show up before its own tracking
# even finished and undercut the whole point of the mystery.
SIGHTING_ENCOUNTER_WINDOW_MIN  = 120    # the creature stays huntable this long after reveal
SIGHTING_ENCOUNTER_CHANCE      = 0.15   # flat per-hunt chance during that window
SIGHTING_ENCOUNTER_PITY_HUNTS  = 15     # guaranteed encounter after this many empty hunts

def get_active_sighting() -> dict | None:
    global _active_sighting, _last_sighting_end
    if _active_sighting and time.time() >= _active_sighting.get("ends_ts", 0):
        _last_sighting_end = _active_sighting.get("ends_ts", time.time())
        _active_sighting = None
    return _active_sighting

def _sighting_encounter_roll(user_id: str, biome: str) -> tuple[float, str] | None:
    """None -> the sighting system has no opinion for this biome right now;
    use the normal ambient myth-encounter formula. Otherwise (chance,
    creature) OVERRIDES that formula entirely: (0.0, "") while an unrevealed
    sighting owns this biome — nothing should appear before its own tracking
    finishes — or a flat pity-protected shot at the specific creature during
    its post-reveal window."""
    if not FEATURE_WORLD_SIGHTINGS:
        return None
    sg = get_active_sighting()
    if not sg or sg.get("biome") != biome:
        return None
    if not sg.get("revealed"):
        return (0.0, "")
    pity = data[user_id].setdefault("_myth_pity", {})
    if pity.get("sighting_id") != sg.get("id"):
        pity["sighting_id"] = sg.get("id")
        pity["count"] = 0
    pity["count"] = pity.get("count", 0) + 1
    chance = 1.0 if pity["count"] >= SIGHTING_ENCOUNTER_PITY_HUNTS else SIGHTING_ENCOUNTER_CHANCE
    return (chance, sg.get("creature", ""))

def _sighting_here(biome: str) -> str:
    sg = get_active_sighting()
    if not sg or sg.get("biome") != biome:
        return ""
    if sg.get("revealed"):
        return f"{creature_emoji(sg['creature'])} **{sg['creature']}** sighted — ends <t:{int(sg['ends_ts'])}:R>"
    return (f"Unknown creature reported · clues {sg.get('clues',0)}/{SIGHTING_CLUE_GOAL} "
            f"· ends <t:{int(sg['ends_ts'])}:R>")

def active_sighting_banner() -> str:
    sg = get_active_sighting()
    if not sg:
        return ""
    where = BIOME_NAMES.get(sg.get("biome", ""), sg.get("biome", ""))
    if sg.get("revealed"):
        ico = creature_emoji(sg["creature"])
        return (f"{emoji('siren')} **GLOBAL SIGHTING — {ico} {sg['creature']}**\n"
                f"-# Confirmed in {where}. Elevated encounter chance until <t:{int(sg['ends_ts'])}:R>.")
    return (f"{emoji('siren')} **GLOBAL SIGHTING**\n"
            f"-# Something big reported in {where}. Identity unknown — "
            f"hunt there to gather clues (**{sg.get('clues',0)}/{SIGHTING_CLUE_GOAL}**).")

def active_sighting_line() -> str:
    """Single-line flattened version of active_sighting_banner(), for contexts
    that pack it alongside other bits under one shared `-#` subtext wrapper —
    banner() has its own embedded mid-string "-#" for its second line, which
    only renders as subtext when it's the first thing on its own line, so it
    can't just be joined with a space into another already-`-#`-prefixed line."""
    sg = get_active_sighting()
    if not sg:
        return ""
    where = BIOME_NAMES.get(sg.get("biome", ""), sg.get("biome", ""))
    if sg.get("revealed"):
        ico = creature_emoji(sg["creature"])
        return (f"{emoji('siren')} **GLOBAL SIGHTING** — {ico} {sg['creature']} confirmed in {where}, "
                f"ends <t:{int(sg['ends_ts'])}:R>")
    return (f"{emoji('siren')} **GLOBAL SIGHTING** — something big in {where}, "
            f"clues {sg.get('clues',0)}/{SIGHTING_CLUE_GOAL}")

def _sighting_add_clues(user_id: str, biome: str) -> None:
    """One hunt's contribution to the active sighting. Call inside run_hunt."""
    if not FEATURE_WORLD_SIGHTINGS:
        return
    sg = get_active_sighting()
    if not sg or sg.get("biome") != biome or sg.get("revealed"):
        if sg and sg.get("biome") == biome and sg.get("revealed"):
            st = data[user_id].setdefault("stats", {})
            st["sightings_joined"] = st.get("sightings_joined", 0) + 1
        return
    gained = random.randint(1, 3)
    if trophy_proc(user_id, "sighting_double_clue_pct"):   # Kraken: Kraken Ink Vial
        gained *= 2
    sg["clues"] = sg.get("clues", 0) + gained
    st = data[user_id].setdefault("stats", {})
    st["sightings_joined"] = st.get("sightings_joined", 0) + 1
    sg.setdefault("contributors", [])
    if user_id not in sg["contributors"]:
        sg["contributors"].append(user_id)
    analytics(user_id, "sighting_clue", biome=biome, clues=sg["clues"])
    if sg["clues"] >= SIGHTING_CLUE_GOAL and not sg.get("revealed"):
        sg["revealed"] = True
        sg["revealed_ts"] = time.time()
        # The hunting window starts fresh at reveal — the discovery phase's
        # own (much shorter) countdown isn't long enough to actually go kill
        # the thing once it's finally found.
        sg["ends_ts"] = sg["revealed_ts"] + SIGHTING_ENCOUNTER_WINDOW_MIN * 60

def spawn_world_sighting(force: bool = False) -> dict | None:
    """Start a new hidden sighting in a random myth-bearing region."""
    global _active_sighting
    if not FEATURE_WORLD_SIGHTINGS:
        return None
    if get_active_sighting():
        return None
    if not force and time.time() < _last_sighting_end + SIGHTING_GAP_MIN_H * 3600:
        return None
    pool = [b for b, ms in BIOME_MYTHS.items() if ms and b != "village"]
    if not pool:
        return None
    biome = random.choice(pool)
    creature = random.choice(BIOME_MYTHS[biome])
    now = time.time()
    _active_sighting = {
        "id": secrets.token_hex(4), "biome": biome, "creature": creature,
        "started_ts": now,
        "ends_ts": now + random.randint(SIGHTING_MIN_MIN, SIGHTING_MAX_MIN) * 60,
        "revealed": False, "clues": 0, "contributors": [],
    }
    return _active_sighting

def _v2_public_world_state() -> dict:
    """Small, PII-free snapshot for the public website's 'LIVE NOW' strip.
    Called on the event loop with no awaits — just reads module globals."""
    now = time.time()
    conds = []
    for b, c in list(_world_conditions.items()):
        if c.get("ends_ts", 0) <= now:
            continue
        spec = WORLD_CONDITIONS.get(c.get("key", ""), {})
        if spec:
            conds.append({"region": BIOME_NAMES.get(b, b),
                          "name": spec.get("name", ""), "emoji": spec.get("emoji", ""),
                          "ends_ts": int(c["ends_ts"])})
    sg = _active_sighting if (_active_sighting and _active_sighting.get("ends_ts", 0) > now) else None
    sighting = None
    if sg:
        sighting = {"region": BIOME_NAMES.get(sg.get("biome", ""), ""),
                    "revealed": bool(sg.get("revealed")),
                    "creature": sg.get("creature", "") if sg.get("revealed") else "",
                    "clues": sg.get("clues", 0), "clue_goal": SIGHTING_CLUE_GOAL,
                    "ends_ts": int(sg.get("ends_ts", 0))}
    ev = _active_event if (_active_event and _active_event.get("ends_ts", 0) > now) else None
    event = ({"name": ev.get("name", ""), "ends_ts": int(ev.get("ends_ts", 0))} if ev else None)
    return {"conditions": conds, "sighting": sighting, "event": event,
            "updated_ts": int(now)}

def rotate_world_conditions(force_fill: bool = False) -> list[str]:
    """Expire finished conditions, then top up to WORLD_CONDITION_SLOTS enhanced
    regions. Returns the biome keys that gained a NEW condition."""
    if not FEATURE_WORLD_CONDITIONS:
        return []
    _prune_world_conditions()
    now = time.time()
    slots = WORLD_CONDITION_SLOTS
    changed: list[str] = []
    open_slots = slots - len(_world_conditions)
    if open_slots <= 0 and not force_fill:
        return []
    all_biomes = [b for b in BIOME_NAMES if b != "village"]  # village stays calm
    candidates = [b for b in all_biomes if b not in _world_conditions]
    random.shuffle(candidates)
    keys = list(WORLD_CONDITIONS)
    for b in candidates[:max(0, open_slots)]:
        ck = random.choice(keys)
        spec = WORLD_CONDITIONS[ck]
        _world_conditions[b] = {
            "key": ck, "started_ts": now,
            "ends_ts": now + int(spec.get("duration", 3 * 3600)),
        }
        changed.append(b)
    return changed

# ── Rare ("perfect") catch chance — diminishing returns on luck ──────────
# 5% floor, asymptotically approaching ~30%. Used by active hunts and the
# idle camp. luck already includes tool + ammo + shop + tribe + temp boosts.
def rare_catch_chance(luck: float) -> float:
    lk = max(0, luck)
    return 0.05 + 0.25 * lk / (lk + 200)

# ═══════════════════════════════════════════════════════════════
# PLAYER HEALTH  ·  a real, persistent stat (Idle Hunter V2.1, Plan A #1-2)
# ═══════════════════════════════════════════════════════════════
# data[uid]["health"] = {hp, max_hp, last_regen_ts, injuries, rookie_revive_used}.
# The SAME pool both normal-animal fights and mythic boss fights draw from —
# no more fresh 100 HP every myth encounter. Regen is computed lazily; there is
# deliberately no background HP-tick loop.

def player_is_resting(user_id: str) -> bool:
    """True while the idle camp is running, or while onboarding is still in
    progress — both regen HP at the faster CAMP_HP_REGEN_PER_MIN rate."""
    d = data.get(user_id, {})
    if d.get("idle", {}).get("active"):
        return True
    return not d.get("onboarding", {}).get("completed", True)

def refresh_health(user_id: str) -> int:
    """Apply HP regen since the last check. Returns HP actually healed. Safe to
    call as often as you like — cheap, and a no-op once HP is full."""
    d = data.get(user_id)
    if not d:
        return 0
    h = d.setdefault("health", {"hp": PLAYER_BASE_HP, "max_hp": PLAYER_BASE_HP,
                                "last_regen_ts": time.time(), "injuries": [],
                                "rookie_revive_used": True})
    now = time.time()
    maxhp = effective_max_hp(user_id)
    if h.get("hp", maxhp) >= maxhp:
        h["last_regen_ts"] = now
        return 0
    elapsed = max(0.0, now - h.get("last_regen_ts", now))
    rate = CAMP_HP_REGEN_PER_MIN if player_is_resting(user_id) else HP_REGEN_PER_MIN
    rate *= 1 + trophy_effect_value(user_id, "hp_regen_pct") / 100   # Troll: Petrified Troll Nose
    healed = int(elapsed / 60 * rate)
    if healed <= 0:
        return 0
    before = h["hp"]
    h["hp"] = min(maxhp, h["hp"] + healed)
    h["last_regen_ts"] = now
    return h["hp"] - before

def player_hp(user_id: str) -> tuple[int, int]:
    h = data.get(user_id, {}).get("health") or {}
    return int(h.get("hp", PLAYER_BASE_HP)), effective_max_hp(user_id)

def hp_status_line(user_id: str) -> str:
    hp, mx = player_hp(user_id)
    ico = emoji("hp") or "❤️"
    tag = ""
    if hp <= mx * 0.25:
        tag = f" {emoji('warning')}"
    return f"{ico} **{hp}/{mx}**{tag}"

def apply_ko_recovery(user_id: str) -> dict:
    """Called the instant a fight drops the player to 0 HP. Never punishes a
    normal-animal loss beyond a short recovery — no cash/item/XP loss. A brand
    new player's FIRST knockout is fully cushioned by rookie protection."""
    h = data[user_id].setdefault("health", {"hp": PLAYER_BASE_HP, "max_hp": PLAYER_BASE_HP,
                                            "last_regen_ts": time.time(), "injuries": [],
                                            "rookie_revive_used": True})
    rookie = not h.get("rookie_revive_used", True)
    recover_to = ROOKIE_KO_RECOVERY_HP if rookie else KO_RECOVERY_HP
    h["hp"] = min(effective_max_hp(user_id), recover_to)
    h["last_regen_ts"] = time.time()
    if rookie:
        h["rookie_revive_used"] = True
    mark_user_dirty(user_id)
    return {"rookie_save": rookie, "hp": h["hp"]}

# ── The temporary trial weapon — tasted, then taken away on purpose ─────────
# Cosmetic/contextual: shown in the menu + equip panel and drives the scripted
# onboarding beat. It deliberately does NOT re-route live hunting's ammo/tool
# logic — see _onb_grant_trial_catches, which delivers the "two at once" feel
# through the same guaranteed-catch path the rest of onboarding already uses,
# so the real ammo-gated hunt loop is never at risk of being taught to a new
# player who owns no arrows yet.

def trial_tool_active(user_id: str) -> dict | None:
    tr = data.get(user_id, {}).get("trial_tool")
    if tr and tr.get("expires_at", 0) > time.time():
        return tr
    return None

def trial_tool_line(user_id: str) -> str:
    tr = trial_tool_active(user_id)
    if not tr:
        return ""
    t_info = TOOLS.get(tr["tool"], {})
    return (f"{t_info.get('emoji', emoji('bow'))} **Training {tr['tool']}** (loaner) — "
           f"returns <t:{int(tr['expires_at'])}:R>")

# ═══════════════════════════════════════════════════════════════
# FIELD GUIDE  ·  collection / world-completion (V2, Phase 43-44)
# ═══════════════════════════════════════════════════════════════
# Turns the flat "total caught" number into something worth travelling for:
# per-region species completion, mythic creatures discovered, world %.

_GUIDE_HUNT_BIOMES = [b for b in BIOME_NAMES if b != "village"] + ["village"]

# world-completion % → cosmetic title (earned_titles). No new badge art needed.
GUIDE_TITLE_MILESTONES = [
    (10,  "Field Naturalist"),
    (25,  "Regional Naturalist"),
    (50,  "World Traveller"),
    (75,  "Master Tracker"),
    (100, "Keeper of the Field Guide"),
]

def _region_species(biome: str) -> list[str]:
    return list(dict.fromkeys(BIOME_ANIMALS.get(biome, [])))

def _guide_region_progress(user_id: str, biome: str) -> tuple[int, int]:
    rec = data.get(user_id, {}).get("record", {}) or {}
    species = _region_species(biome)
    have = sum(1 for a in species if rec.get(a, {}).get("count", 0) > 0)
    return have, len(species)

def _myths_discovered(user_id: str) -> set[str]:
    """Creature names the player has actually KILLED at least once (myth_record),
    not just ones they happen to hold a trophy for — a Mythic Crate used to be
    able to hand out a random trophy and accidentally mark a creature
    "discovered" without ever fighting it. Fixed 2026-09-16."""
    mr = data.get(user_id, {}).get("myth_record", {}) or {}
    return {name for name, entry in mr.items() if entry.get("kills", 0) > 0}

def guide_completion(user_id: str) -> dict:
    """{species_have, species_total, regions_have, regions_total,
        myths_have, myths_total, world_pct}."""
    s_have = s_total = 0
    r_have = 0
    biomes = [b for b in BIOME_NAMES]
    for b in biomes:
        h, t = _guide_region_progress(user_id, b)
        s_have += h; s_total += t
        if h >= t and t > 0:
            r_have += 1
    m_have = len(_myths_discovered(user_id))
    m_total = len(MYTHIC_CREATURES)
    parts = []
    if s_total: parts.append(s_have / s_total)
    parts.append(r_have / max(1, len(biomes)))
    if m_total: parts.append(m_have / m_total)
    world_pct = round(100 * sum(parts) / len(parts), 1) if parts else 0.0
    return {"species_have": s_have, "species_total": s_total,
            "regions_have": r_have, "regions_total": len(biomes),
            "myths_have": m_have, "myths_total": m_total,
            "world_pct": world_pct}

def _grant_guide_titles(user_id: str) -> list[str]:
    """Award any world-completion milestone titles the player now qualifies for."""
    got = []
    pct = guide_completion(user_id)["world_pct"]
    earned = data[user_id].setdefault("earned_titles", [])
    for need, title in GUIDE_TITLE_MILESTONES:
        if pct >= need and title not in earned:
            earned.append(title); got.append(title)
    if got:
        mark_user_dirty(user_id)
        analytics(user_id, "guide_milestone", pct=pct, titles=got)
    return got

def _guide_bar(have: int, total: int, width: int = 14) -> str:
    """A row of custom emoji, filled tight against blank with no separator —
    plain unicode block characters (█/░) render inconsistently across fonts."""
    fill = 0 if total <= 0 else max(0, min(width, round(width * have / total)))
    return _pill_bar(fill, width)

def build_events_components(user_id: str) -> list:
    ev = get_active_event()
    if not ev:
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": (f"### {emoji('earth')} Global Events\n\n"
                                     "-# No events are running right now.\n"
                                     "-# Events are admin-triggered — check back later.")},
            {"type": 14, "divider": True, "spacing": 1},
            _back_row(user_id),
        ]}]
    key = ev.get("key", "")
    if key == "thieving_fox":
        return _build_fox_panel(user_id)
    if key == "shipwreck":
        return _build_shipwreck_panel(user_id)
    if key == "duck":
        return _build_duck_panel(user_id)
    # buff view
    g = EVENTS.get(ev["key"], ADMIN_BUFF_EVENT)
    content = (
        f"# {g['emoji']} {ev['name']}\n"
        f"{g['blurb']}\n\n"
        f"-# Started <t:{int(ev.get('started_ts',0))}:R> · **ends <t:{int(ev['ends_ts'])}:R>**\n\n"
        f"### What's flipped on\n" + "\n".join(f"- {p}" for p in g.get("perks", []))
    )
    return [{"type": 17, "accent_color": 0xF1C40F, "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        _back_row(user_id),
    ]}]

# ─────────────────────────────────────────────
# EVENT MINI-GAMES  (Fox / Shipwreck / Duck)
# ─────────────────────────────────────────────

def _event_end_line(ev: dict) -> str:
    return f"-# ends <t:{int(ev['ends_ts'])}:R>"

def _event_shop_btn(user_id: str, key: str) -> dict:
    return {"type": 2, "style": 2, "label": "Event Shop", "emoji": emoji_partial("shop"),
            "custom_id": f"event:shop:{key}:{user_id}"}

# ── 🦊 Thieving Fox ──────────────────────────────────────────
def _fox_reward(user_id: str) -> str:
    """One parcel recovered — additive rewards only."""
    st = data[user_id]["event"]
    st["parcels"] = st.get("parcels", 0) + 1
    st["recovered"] = st.get("recovered", 0) + 1
    bits = ["a **parcel token**"]
    if random.random() < 0.35:
        cr = "Epic Crate" if random.random() < 0.3 else "Rare Crate"
        data[user_id].setdefault("crate_inv", {})[cr] = data[user_id]["crate_inv"].get(cr, 0) + 1
        bits.append(f"a **{cr}**")
    got = []
    if st.get("perfect", True) and st["recovered"] >= FOX_TITLE_AT:
        got = _grant_event_reward(user_id, title="Outfoxed", badge="event_fox")
    st["lead"] = FOX_LEAD_START + st["recovered"]   # the fox gets craftier
    line = "`🦊` You corner the fox and grab the parcel — " + " and ".join(bits) + "!"
    if got:
        line += f"\n-# {emoji('sports_medal')} Unlocked " + " + ".join(got) + "."
    return line

def fox_route(user_id: str, route: str) -> dict:
    """Resolve one route choice. Mutates data[uid]['event']. Call in a txn."""
    st = _player_event(user_id)
    if st is None or route not in FOX_ROUTES:
        return {"msg": "The trail's gone cold.", "done": True}
    st.setdefault("lead", FOX_LEAD_START); st.setdefault("perfect", True); st.setdefault("parcels", 0)
    rewarded = _event_attempt(user_id, FOX_ATTEMPTS_DAY)
    r = FOX_ROUTES[route]
    if not rewarded:
        # Past the daily cap a run must be inert: it used to still move the fox,
        # so spamming the 100%-safe "Lie Low" route ground the lead to 0 for free
        # parcels + the Outfoxed title.
        st["journal"] = st.get("journal", 0) + 1
        return {"msg": f"{r['label']} — but you're out of tracking runs for today.\n"
                       "-# `📓` This one only fills your field journal."}
    if random.randint(1, 100) <= r["safe"]:
        st["lead"] = max(0, st["lead"] - random.randint(r["lo"], r["hi"]))
        msg = f"{r['label']} pays off — you close the gap."
    else:
        st["lead"] += r["fail_lead"]
        if r["breaks_perfect"]:
            st["perfect"] = False
        msg = f"{r['label']} goes wrong — you lose sight of it for a bit."
    if st["lead"] <= 0:
        return {"msg": msg + "\n\n" + _fox_reward(user_id)}
    return {"msg": msg}

def _build_fox_panel(user_id: str) -> list:
    ev = get_active_event()
    st = _player_event(user_id) or {}
    st.setdefault("lead", FOX_LEAD_START); st.setdefault("perfect", True)
    left = _event_attempts_left(user_id, FOX_ATTEMPTS_DAY)
    content = (
        f"# `🦊` {ev['name']}\n{EVENTS['thieving_fox']['blurb']}\n\n"
        f"**The fox's lead:** {_progress_bar(FOX_LEAD_START + st.get('recovered',0) - st['lead'], FOX_LEAD_START + st.get('recovered',0))}\n"
        f"-# {st['lead']} lengths ahead" + ("" if st.get('perfect', True) else " · trail broken (no *Outfoxed* this run)") + "\n"
        f"-# {emoji('gift')} Parcel tokens: **{st.get('parcels',0)}** · recovered **{st.get('recovered',0)}**"
        + (f" (need {FOX_TITLE_AT} clean for *Outfoxed*)" if st.get('recovered',0) < FOX_TITLE_AT else "") + "\n"
        f"-# {emoji('animal_fallback')} Tracking runs left today: **{left}/{FOX_ATTEMPTS_DAY}** · {_event_end_line(ev)[2:]}"
    )
    rows = [{"type": 10, "content": content}, {"type": 14, "divider": True, "spacing": 1}]
    rows.append({"type": 1, "components": [
        {"type": 2, "style": 3 if k == "steady" else 1 if k == "wait" else 4,
         "label": v["label"], "custom_id": f"event:fox:{k}:{user_id}"}
        for k, v in FOX_ROUTES.items()]})
    rows.append({"type": 1, "components": [_event_shop_btn(user_id, "thieving_fox"),
                                           _back_row(user_id)["components"][0]]})
    return [{"type": 17, "accent_color": 0xE67E22, "spoiler": False, "components": rows}]

# ── 🏴‍☠️ Shipwreck Scramble ─────────────────────────────────
def ship_dive(user_id: str, spot: str) -> dict:
    st = _player_event(user_id)
    if st is None or spot not in SHIP_SPOTS:
        return {"msg": "The tide's come in — nothing to dive."}
    st.setdefault("unbanked", 0); st.setdefault("banked", 0)
    rewarded = _event_attempt(user_id, SHIP_DIVES_DAY)
    s = SHIP_SPOTS[spot]
    if not rewarded:
        st["journal"] = st.get("journal", 0) + 1
        return {"msg": f"{s['label']} — but you're out of dives for today. Journal noted; no salvage."}
    gain = random.randint(s["lo"], s["hi"])
    st["unbanked"] += gain
    msg = f"`⚓` {s['label']}: **+{gain} salvage** (unbanked)."
    if s["risk"] and random.randint(1, 100) <= s["risk"]:
        lost = int(st["unbanked"] * s["loss"])
        st["unbanked"] = max(0, st["unbanked"] - lost)
        msg += f"\n-# {emoji('impact')} A beam gives way — you drop **{lost}** unbanked salvage scrambling out. (Banked salvage is safe.)"
    return {"msg": msg}

def ship_bank(user_id: str) -> dict:
    st = _player_event(user_id)
    if st is None:
        return {"msg": "Nothing to bank."}
    moved = st.get("unbanked", 0)
    st["banked"] = st.get("banked", 0) + moved
    st["unbanked"] = 0
    return {"msg": f"{emoji('bank')} Banked **{moved}** salvage — that's yours for keeps."}

def _build_shipwreck_panel(user_id: str) -> list:
    ev = get_active_event()
    st = _player_event(user_id) or {}
    left = _event_attempts_left(user_id, SHIP_DIVES_DAY)
    content = (
        f"# `🏴‍☠️` {ev['name']}\n{EVENTS['shipwreck']['blurb']}\n\n"
        f"`⚓` **Unbanked salvage:** {st.get('unbanked',0)}  (at risk on deep dives)\n"
        f"{emoji('bank')} **Banked salvage:** {st.get('banked',0)}  (safe — spend it in the shop)\n"
        f"-# `🤿` Dives left today: **{left}/{SHIP_DIVES_DAY}** · {_event_end_line(ev)[2:]}\n"
        f"-# Nothing you own or bought is ever at risk — only unbanked salvage."
    )
    rows = [{"type": 10, "content": content}, {"type": 14, "divider": True, "spacing": 1}]
    rows.append({"type": 1, "components": [
        {"type": 2, "style": 3 if k == "deck" else 2 if k == "cabins" else 4,
         "label": v["label"], "custom_id": f"event:ship:{k}:{user_id}"}
        for k, v in SHIP_SPOTS.items()]})
    rows.append({"type": 1, "components": [
        {"type": 2, "style": 1, "label": "Bank Salvage", "emoji": emoji_partial('bank'), "custom_id": f"event:ship:bank:{user_id}",
         "disabled": st.get("unbanked", 0) <= 0},
        _event_shop_btn(user_id, "shipwreck"),
        _back_row(user_id)["components"][0]]})
    return [{"type": 17, "accent_color": 0x2C6E8F, "spoiler": False, "components": rows}]

# ── 🦆 Duck Takeover ─────────────────────────────────────────
def duck_vote(user_id: str, option: str) -> str:
    ev = get_active_event()
    if not ev or ev.get("kind") != "community" or option not in DUCK_ENDINGS:
        return "The vote's closed."
    if user_id in ev.setdefault("voters", []):
        return "You've already cast your vote."
    ev.setdefault("votes", {o: 0 for o in DUCK_ENDINGS})[option] += 1
    ev["voters"].append(user_id)
    return f"`🗳️` Vote counted: **{DUCK_ENDINGS[option]['label']}**."

def _duck_try_claim(user_id: str) -> list[str]:
    """Grant the ending reward once the vote has resolved and this player has
    contributed enough. Idempotent — called from feed and from the panel."""
    ev = get_active_event()
    if not ev or not ev.get("ending"):
        return []
    st = data[user_id].get("event", {})
    if st.get("key") != "duck" or st.get("contrib", 0) < DUCK_CONTRIB_MIN:
        return []
    return _grant_event_reward(user_id, title=DUCK_ENDINGS[ev["ending"]]["title"], badge="event_duck")

def _duck_resolve(ev: dict) -> None:
    """Fire once when the community goal is reached — picks the ending and
    rewards everyone who already qualified. Late qualifiers claim via
    `_duck_try_claim` when they next interact."""
    if ev.get("ending"):
        return
    votes = ev.get("votes", {})
    winner = max(votes, key=lambda o: votes.get(o, 0)) if any(votes.values()) else "negotiate"
    ev["ending"] = winner
    end = DUCK_ENDINGS[winner]
    granted = 0
    for uid, d in data.items():
        st = d.get("event", {})
        if st.get("key") == "duck" and st.get("started") == ev["started_ts"] \
                and st.get("contrib", 0) >= DUCK_CONTRIB_MIN:
            if _grant_event_reward(uid, title=end["title"], badge="event_duck"):
                granted += 1
            mark_user_dirty(uid)
    try:
        bot.loop.create_task(_broadcast_update({
            "title": f"`🦆` Duck Takeover — {end['label']}!",
            "message": f"{end['text']}\n\n-# {granted} hunter(s) who chipped in earned the "
                       f"**\"{end['title']}\"** title and the Bread Winner badge.",
            "moderator": "", "date": int(time.time()),
        }))
    except Exception:
        pass

def duck_feed(user_id: str) -> str:
    ev = get_active_event()
    st = _player_event(user_id)
    if not ev or st is None:
        return "The ducks have moved on."
    have = st.get("bread", 0)
    if have <= 0:
        return "No breadcrumbs — go hunting to find some."
    give = min(have, DUCK_FEED_CHUNK)
    st["bread"] = have - give
    st["contrib"] = st.get("contrib", 0) + give
    comm = ev.setdefault("community", {"progress": 0, "goal": _event_community_goal()})
    comm["progress"] += give
    msg = f"`🍞` You toss **{give}** crumbs to the flock."
    if comm["progress"] >= comm["goal"] and not ev.get("ending"):
        _duck_resolve(ev)
        msg += f"\n-# {emoji('party_popper')} The community goal is met — the ducks are dealt with!"
    got = _duck_try_claim(user_id)
    if got:
        msg += f"\n-# {emoji('sports_medal')} You earned " + " + ".join(got) + "."
    return msg

def _build_duck_panel(user_id: str) -> list:
    ev = get_active_event()
    st = _player_event(user_id) or {}
    _duck_try_claim(user_id)
    comm = ev.get("community", {"progress": 0, "goal": 1})
    votes = ev.get("votes", {})
    voted = user_id in ev.get("voters", [])
    tally = " · ".join(f"{DUCK_ENDINGS[o]['label']} **{votes.get(o,0)}**" for o in DUCK_ENDINGS)
    end_line = ""
    if ev.get("ending"):
        e = DUCK_ENDINGS[ev["ending"]]
        end_line = f"\n\n### `🎬` {e['label']}\n{e['text']}"
    content = (
        f"# `🦆` {ev['name']}\n{EVENTS['duck']['blurb']}\n\n"
        f"`🍞` **Your breadcrumbs:** {st.get('bread',0)} · contributed **{st.get('contrib',0)}**"
        + (f" {emoji('check_mark')} (qualifies for the reward)" if st.get('contrib',0) >= DUCK_CONTRIB_MIN else f" (need {DUCK_CONTRIB_MIN} to earn the ending reward)") + "\n\n"
        f"**The flock is {int(100*min(1, comm['progress']/max(1,comm['goal'])))}% fed**\n"
        f"{_progress_bar(comm['progress'], comm['goal'])}\n-# {comm['progress']:,}/{comm['goal']:,} crumbs · {_event_end_line(ev)[2:]}\n\n"
        f"**Vote:** {tally}" + end_line
    )
    rows = [{"type": 10, "content": content}, {"type": 14, "divider": True, "spacing": 1}]
    rows.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": DUCK_ENDINGS[o]["label"], "disabled": voted or bool(ev.get("ending")),
         "custom_id": f"event:duck:vote:{o}:{user_id}"} for o in DUCK_ENDINGS]})
    rows.append({"type": 1, "components": [
        {"type": 2, "style": 3, "label": "🍞 Feed the Ducks", "custom_id": f"event:duck:feed:{user_id}",
         "disabled": st.get("bread", 0) <= 0},
        _back_row(user_id)["components"][0]]})
    return [{"type": 17, "accent_color": 0xF1C40F, "spoiler": False, "components": rows}]

# ── shared event shop ───────────────────────────────────────
_EVENT_SHOP = {"thieving_fox": ("parcels", "parcel token", FOX_SHOP),
               "shipwreck":    ("banked",  "banked salvage", SHIP_SHOP)}

def _build_event_shop_panel(user_id: str, key: str) -> list:
    if key not in _EVENT_SHOP:
        return build_events_components(user_id)
    field, unit, table = _EVENT_SHOP[key]
    st = _player_event(user_id) or {}
    have = st.get(field, 0)
    spec = EVENTS[key]
    rows = [{"type": 10, "content": f"### {spec['emoji']} {spec['name']} — Shop\n"
                                    f"-# You have **{have}** {unit}."},
            {"type": 14, "divider": True, "spacing": 1}]
    for i, it in enumerate(table):
        can = have >= it["cost"]
        rows.append({"type": 9,
            "components": [{"type": 10, "content": f"**{it['label']}** — {it['cost']} {unit}"}],
            "accessory": {"type": 2, "style": 1 if can else 2, "label": "Buy",
                          "custom_id": f"event:buy:{key}:{i}:{user_id}", "disabled": not can}})
    rows.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"event:back:{user_id}"}]})
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": rows}]

def event_shop_buy(user_id: str, key: str, idx: int) -> str:
    if key not in _EVENT_SHOP:
        return "Nothing to buy."
    field, unit, table = _EVENT_SHOP[key]
    if not (0 <= idx < len(table)):
        return "Unknown item."
    st = _player_event(user_id)
    it = table[idx]
    if st is None or st.get(field, 0) < it["cost"]:
        return f"{emoji('cross_mark')} Not enough {unit}."
    if it.get("title") and it["title"] in data[user_id].get("earned_titles", []):
        return f"{emoji('cross_mark')} You already own the title **\"{it['title']}\"**."
    st[field] -= it["cost"]
    if it.get("crate"):
        data[user_id].setdefault("crate_inv", {})[it["crate"]] = data[user_id]["crate_inv"].get(it["crate"], 0) + 1
        out = f"{emoji('check_mark')} Bought **{it['crate']}**."
    elif it.get("title"):
        _grant_event_reward(user_id, title=it["title"])
        out = f"{emoji('check_mark')} Unlocked the title **\"{it['title']}\"**."
    else:
        out = f"{emoji('check_mark')} Purchased."
    if key == "shipwreck" and _grant_special_badge(user_id, "event_anchor"):
        out += " You also earn the **Wreck Diver** badge."
    return out

# ─────────────────────────────────────────────
# INCORRENT USER MESSAGE
# ─────────────────────────────────────────────

def show_incorrect_user_message(user_id: str):
    return (
        f"This panel is controlled by <@{user_id}>.\n"
        "If you want to view it, you will have to run the original command yourself."
    )

# ─────────────────────────────────────────────
# AMMO HELPERS
# ─────────────────────────────────────────────

def get_equipped_ammo(user_id: str) -> str | None:
    return data[user_id].get("equipped_ammo")

def get_ammo_count(user_id: str, ammo_name: str) -> int:
    return data[user_id].get("ammo_inv", {}).get(ammo_name, 0)

def consume_ammo(user_id: str, ammo_name: str, count: int) -> bool:
    inv     = data[user_id].setdefault("ammo_inv", {})
    current = inv.get(ammo_name, 0)
    if current < count:
        return False
    inv[ammo_name] = current - count
    if inv[ammo_name] == 0:
        del inv[ammo_name]
    return True

def get_ammo_boosts(user_id: str) -> dict:
    ammo_name = get_equipped_ammo(user_id)
    if not ammo_name:
        return {"luck": 0, "sell": 0, "xp": 0}
    a = AMMO.get(ammo_name, {})
    return {
        "luck": a.get("boost_luck", 0),
        "sell": a.get("boost_sell", 0),
        "xp":   a.get("boost_xp",   0),
    }

# ─────────────────────────────────────────────
# COLORS
# ─────────────────────────────────────────────

def v2_color(user_id: str) -> discord.Color:
    c = data.get(user_id, {}).get("color", "green")
    if c == "colorless":
        return discord.Color.default()
    if c.startswith("#"):
        try:
            return discord.Color(int(c.lstrip("#"), 16))
        except ValueError:
            return discord.Color.default()
    return COLORS.get(c, discord.Color.default())

def _accent(user_id: str) -> int:
    return int(v2_color(user_id)) or 0x2ECC71

# ─────────────────────────────────────────────
# TEMP BOOSTS
# ─────────────────────────────────────────────

def get_active_temp_boosts(user_id: str) -> dict:
    """Return combined active temp boost percentages."""
    now = time.time()
    boosts = {"luck": 0, "sell": 0, "xp": 0}
    for b in data[user_id].get("temp_boosts", []):
        if b["expires_at"] > now:
            boosts[b["stat"]] = boosts.get(b["stat"], 0) + b["amount"]
    return boosts

# ─────────────────────────────────────────────
# PERSISTENCE
# ─────────────────────────────────────────────

# In-memory data stores (loaded from SQLite on startup)
data: dict[str, dict] = {}
tribe_data: dict[str, dict] = {}

# Dirty-tracking for the per-transaction flush. Backend's transaction context
# managers flush on every exit; without this they re-serialise *every* user on
# *every* mutation. These wrappers mark the owning user so the flush callback
# (registered in on_ready) writes just the changed rows. The 20s autosave_users
# loop stays a full write as the safety net for out-of-transaction mutations.
_dirty_users: set[str] = set()

def mark_user_dirty(user_id) -> None:
    _dirty_users.add(str(user_id))

@asynccontextmanager
async def user_transaction(user_id):
    mark_user_dirty(user_id)
    async with _backend_user_transaction(str(user_id)):
        yield

@asynccontextmanager
async def user_tribe_transaction(user_id, *tribe_names):
    mark_user_dirty(user_id)
    async with _backend_user_tribe_transaction(str(user_id), *tribe_names):
        yield

@asynccontextmanager
async def multi_user_transaction(*user_ids):
    for uid in user_ids:
        mark_user_dirty(uid)
    async with _backend_multi_user_transaction(*(str(u) for u in user_ids)):
        yield

async def load_all_data():
    """Load all user and tribe data from SQLite on startup"""
    global data, tribe_data
    
    # Load all users
    async with backend._pool.execute("SELECT user_id, data FROM users") as cursor:
        rows = await cursor.fetchall()
        data = {row[0]: json.loads(row[1]) for row in rows}
    
    # Apply migrations
    data = migrate_all_users(data)
    
    # Load all tribes
    async with backend._pool.execute("SELECT name, data FROM tribes") as cursor:
        rows = await cursor.fetchall()
        tribe_data = {row[0]: json.loads(row[1]) for row in rows}

    # One-time cleanup: drop any uid that ended up in more than one role list
    # (a stale promote/demote could leave one). tribe_roster(repair=True) rewrites
    # the officer/members lists in place; autosave_tribes persists it.
    _fixed = sum(1 for t in list(tribe_data) if _tribe_repair_roles(t))
    if _fixed:
        print(f"🧹 Cleaned duplicate role entries in {_fixed} tribe(s).")

    # Backfill the tribe-progression fields on every existing tribe.
    for _td in tribe_data.values():
        _ensure_tribe_fields(_td)

    print(f"✅ Loaded {len(data)} users and {len(tribe_data)} tribes from SQLite")

# ─────────────────────────────────────────────
# NON-BLOCKING FILE WRITES
# ─────────────────────────────────────────────

_file_write_lock: asyncio.Lock | None = None

def _write_text(path: str, text: str) -> None:
    # Write to a sibling temp file, then swap it in: a crash mid-write leaves
    # the old file intact instead of a truncated/empty one.
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def _append_line(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

async def _locked_write(path: str, text: str) -> None:
    global _file_write_lock
    if _file_write_lock is None:
        _file_write_lock = asyncio.Lock()
    async with _file_write_lock:
        await asyncio.to_thread(_write_text, path, text)

def _write_json_bg(path: str, obj) -> None:
    """Serialize now (consistent snapshot), write to disk off the event loop.

    Falls back to a blocking write when no loop is running (module import time)."""
    text = json.dumps(obj, indent=4, default=str)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _write_text(path, text)
        return
    loop.create_task(_locked_write(path, text))

def _append_line_bg(path: str, line: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _append_line(path, line)
        return
    loop.create_task(asyncio.to_thread(_append_line, path, line))

# ─────────────────────────────────────────────
# CONFIG (still uses JSON - this is fine)
# ─────────────────────────────────────────────

CONFIG_FILE = "config.json"

def save_config():
    _write_json_bg(CONFIG_FILE, {
        "dev_mail": DEV_MAIL,
        "maintenance": {
            "mode":     maintenance_mode,
            "warning":  maintenance_warning,
            "message":  maintenance_message,
            "channels": list(maintenance_channels),
            "warned":   list(_maintenance_warned),
        },
        "updates": UPDATE
    })

def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "dev_mail": "",
            "maintenance": {
                "mode": False, "warning": False,
                "message": "", "channels": [], "warned": [],
            },
            "updates": []
        }

# ─────────────────────────────────────────────
# Migration
# ─────────────────────────────────────────────

async def migrate_json_to_sqlite():
    import os
    
    if os.path.exists("users_info.json"):
        try:
            with open("users_info.json", "r") as f:
                users = json.load(f)
            await backend._pool.executemany("""
                INSERT OR IGNORE INTO users (user_id, data, username, level, money, prestige)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                (uid, json.dumps(d), d.get("username", ""),
                 d.get("level", 1), d.get("money", 0), d.get("prestige", 0))
                for uid, d in users.items()
            ])
            await backend._pool.commit()
            print(f"✅ Migrated {len(users)} users from users_info.json")
        except Exception as e:
            print(f"⚠️ User migration error: {e}")

    if os.path.exists("tribe_info.json"):
        try:
            with open("tribe_info.json", "r") as f:
                tribes = json.load(f)
            await backend._pool.executemany("""
                INSERT OR IGNORE INTO tribes (name, data, level, member_count)
                VALUES (?, ?, ?, ?)
            """, [
                (name, json.dumps(td), td.get("level", 1),
                 1 + len(td.get("roles", {}).get("officer", []))
                   + len(td.get("roles", {}).get("members", [])))
                for name, td in tribes.items()
            ])
            await backend._pool.commit()
            print(f"✅ Migrated {len(tribes)} tribes from tribe_info.json")
        except Exception as e:
            print(f"⚠️ Tribe migration error: {e}")

# ─────────────────────────────────────────────
# INITIAL LOAD (called from on_ready)
# ─────────────────────────────────────────────
# Load config
_cfg = load_config()
DEV_MAIL = _cfg.get("dev_mail", "")
UPDATE = _cfg.get("updates", [])  # ← This will always be a list
LATEST_UPDATE = UPDATE[-1] if UPDATE else {"title": "", "message": "", "moderator": "", "time": "", "id": 0}

# Maintenance settings
_m = _cfg.get("maintenance", {})
maintenance_mode = _m.get("mode", False)
maintenance_warning = _m.get("warning", False)
maintenance_message = _m.get("message", "")
maintenance_channels: set[int] = set(_m.get("channels", []))
_maintenance_warned: set[str] = set(_m.get("warned", []))
maintenance_time = 0

# Register save callbacks (will be re-registered in on_ready after DB init).
# Placeholders that do nothing until the real ones are set — must be async,
# since the transaction managers `await` whatever is registered here.
async def _noop_save() -> None:
    return None

register_save_callbacks(_noop_save, _noop_save)

# ─────────────────────────────────────────────
# TITLE HELPERS
# ─────────────────────────────────────────────

def get_earned_titles(user_id: str) -> list[str]:
    d      = data[user_id]
    titles = []
    for ach_key, tiers in ACHIEVEMENTS.items():
        if not isinstance(tiers, list):
            continue
        claimed_up_to = d.get("achievements", {}).get(ach_key, {}).get("claimed_up_to", -1)
        for i, tier_entry in enumerate(tiers):
            threshold = tier_entry[0]
            if i <= claimed_up_to:
                title_str = ACHIEVEMENT_TITLES.get(ach_key, {}).get(str(threshold))
                if title_str and title_str not in titles:
                    titles.append(title_str)
    return titles

# ─────────────────────────────────────────────
# USER / TRIBE INIT
# ─────────────────────────────────────────────

def init_user(user_id: str):
    user_id = str(user_id)
    today   = today_utc()
    defaults = {
        "schema_version": CURRENT_SCHEMA,"username": get_username(user_id),
        # Deliberately small: 10,000 used to buy tier-1-4 tools (up to the 8,000
        # Spear) outright with zero hunting. Onboarding's guaranteed catches
        # (~385 money) plus this starter cash should land a new player just
        # past the 500 Slingshot, so the FIRST tool purchase is actually
        # funded by hunting, not by the login bonus.
        "money": 150, "level": 1, "xp": 0, "inv": [], "_pending_sell": None,
        "gems": 100, "premium": False, "hunt_cd": 0, "daily_cd": 0,
        "color": "green", "biome": "village", "tribe": None, "tribe_inv": None,
        "verify": init_verify(user_id),
        "boosts": {"luck": 0, "sell": 0, "xp": 0, "crate_luck": 0},
        "idle": {"active": False, "stacks": 0, "started_at": 0,
                 "camp_biome": "village", "haul": [], "capacity_upgrades": 0},
        "tool": "Bare Hands", "owned_tools": ["Bare Hands"],
        "prestige": 0, "record": {}, "servers": [], "total_caught": 0,
        "log": [], "daily_streak": 0, "last_daily_date": "",
        "joined_date": today,
        "best_daily_streak": 0,
        "total_money_earned": 0,
        "mail_read_dev": False,
        "mail_dev_content_read": "",
        "mail_dev_notice_seen": "",
        "ammo_inv": {},
        "equipped_ammo": None,
        "vehicle": "None",
        "owned_vehicles": [],
        "achievements": {},
        "badges":       {},
        "featured_badge": "",
        "special_badges": [],
        "is_tester":      False,
        "earned_titles":  [],
        "equipped_title": None,
        "stats": {
            "ammo_used": 0, "lottery_wins": 0, "tools_used": [],
            "events_completed": 0, "total_xp_earned": 0,
            "bj_wins": 0, "cf_wins": 0, "rl_wins": 0,
            "rps_wins": 0, "slots_wins": 0, 
            "crates_opened": 0,
        },
        "crate_inv": {},
        "shards": {}, "crystals": {}, "gemstones": {}, "craft_queue": [],
        # Idle Hunter V2 — brand-new accounts start the guided first hunt.
        # (Existing players were marked completed by migration _migrate_v13.)
        "onboarding": {"version": 2, "completed": (not FEATURE_ONBOARDING_V2),
                       "step": "intro", "starter_pack": None},
        "guide_seen": [],
        "tracking": None,
        "referral_pending": "",
        # Idle Hunter V2.1 — persistent HP + animal combat + rookie systems.
        # rookie_revive_used mirrors onboarding.completed: False (free rescue
        # available) only for a genuinely brand-new account.
        "health": {"hp": PLAYER_BASE_HP, "max_hp": PLAYER_BASE_HP,
                   "last_regen_ts": time.time(), "injuries": [],
                   "rookie_revive_used": False},
        "healing_inv": {},
        "trial_tool": None,
        "fight": None,
        "rookie_goals": dict.fromkeys(ROOKIE_GOALS, False),
        "rookie_chest_claimed": False,
        # Hunter's Path — a post-onboarding checklist (buy a tool, complete a
        # quest, travel, start a camp) that teaches the systems onboarding
        # doesn't reach. Existing players are grandfathered as completed,
        # same reasoning as onboarding above: only brand-new accounts see it.
        "hunters_path": {"completed": (not FEATURE_HUNTERS_PATH), "rewarded": []},
        "tips_enabled": True,
        "_last_tip_ts": 0,
        "session": None,
    }
    _is_new_user = user_id not in data
    if _is_new_user:
        data[user_id] = dict(defaults)
        data[user_id]["onboarding"] = dict(defaults["onboarding"])  # own copy
        data[user_id]["health"] = dict(defaults["health"])          # own copy
        data[user_id]["shop_bought"] = {}   # brand-new: no legacy boost-derived counts
        data[user_id]["rookie_goals"] = dict(defaults["rookie_goals"])
        data[user_id]["hunters_path"] = dict(defaults["hunters_path"])  # own copy
        # Starting balances are minted out of thin air — record them so the
        # economy ledger reconciles with balances in circulation.
        log_economy_event(user_id, "starting balance", data[user_id]["money"], data[user_id]["money"])
        log_economy_event(user_id, "starting balance", data[user_id]["gems"], data[user_id]["gems"], currency="gems")
        if FEATURE_ANALYTICS:
            analytics(user_id, "user_created")
    else:
        for k, v in defaults.items():
            # An EXISTING account that somehow lacks onboarding/health must NOT
            # be dropped into rookie flows — migration marks all of them done.
            if k == "onboarding":
                data[user_id].setdefault("onboarding", {
                    "version": 2, "completed": True, "step": "done", "starter_pack": None})
                continue
            if k == "health":
                h = data[user_id].setdefault("health", dict(v))
                h.setdefault("rookie_revive_used", True)
                continue
            if k == "hunters_path":
                data[user_id].setdefault("hunters_path", {"completed": True})
                continue
            if k not in data[user_id]:
                data[user_id][k] = v

    data[user_id].setdefault("achievements", {})
    data[user_id].setdefault("badges", {})
    data[user_id].setdefault("special_badges", [])
    data[user_id].setdefault("is_tester", False)
    data[user_id].setdefault("tribe_day", {})
    data[user_id].setdefault("tribe_left_ts", 0.0)
    data[user_id].setdefault("event", {})
    data[user_id].setdefault("event_day", {})
    data[user_id].setdefault("earned_titles", [])
    data[user_id].setdefault("equipped_title", None)

    # Featured badge: shown next to the name in leaderboards / tribe rosters.
    # Backfill existing players to their first-earned badge (BADGES order); new
    # players get theirs set the moment they earn their first badge.
    if not data[user_id].get("featured_badge"):
        _bd = data[user_id].get("badges", {})
        _first = next((k for k in BADGES if _bd.get(k, {}).get("tier", 0) >= 1), "")
        if _first:
            data[user_id]["featured_badge"] = _first
    data[user_id].setdefault("stats", {})
    data[user_id]["stats"].setdefault("crates_opened", 0)
    data[user_id].setdefault("quests", [])
    data[user_id].setdefault("quests_last_roll", "")   # ISO date of last daily roll
    data[user_id].setdefault("temp_boosts", [])
    data[user_id].setdefault("health", {"hp": PLAYER_BASE_HP, "max_hp": PLAYER_BASE_HP,
                                        "last_regen_ts": time.time(), "injuries": [],
                                        "rookie_revive_used": True})
    data[user_id].setdefault("healing_inv", {})
    data[user_id].setdefault("trial_tool", None)
    data[user_id].setdefault("fight", None)
    data[user_id].setdefault("rookie_goals", dict.fromkeys(ROOKIE_GOALS, False))
    data[user_id].setdefault("rookie_chest_claimed", False)
    refresh_health(user_id)
    data[user_id].setdefault("myth_items", {})         # mythic-creature trophies (count, still tracked for compat)
    data[user_id].setdefault("myth_record", {})        # creature -> {kills, first_kill_ts, best_hp_left}
    data[user_id].setdefault("equipped_trophies", [])  # trophy names equipped in the Trophy Cabinet
    data[user_id].setdefault("_boss", None)            # pending boss encounter
    data[user_id].setdefault("travel", None)           # in-transit state, or None
    data[user_id].setdefault("crate_inv", {})
    data[user_id].setdefault("shards", {})             # rarity -> count
    data[user_id].setdefault("crystals", {})           # rarity -> count
    data[user_id].setdefault("gemstones", {})          # rarity -> count (decor)
    data[user_id].setdefault("craft_queue", [])        # [{rarity, done_ts}] crystal crafts

    for k, v in {
        "ammo_used": 0, "lottery_wins": 0, "tools_used": [], "events_completed": 0,
        "total_xp_earned": 0, "bj_wins": 0, "cf_wins": 0, "rl_wins": 0,
        "rps_wins": 0, "slots_wins": 0,
        "myths_killed": 0, "myths_died": 0, "myths_fled": 0,
    }.items():
        data[user_id]["stats"].setdefault(k, v)

    v = data[user_id].setdefault("verify", {})
    v.setdefault("needed", False); v.setdefault("time", 250); v.setdefault("code", generate_verify_code())
    b = data[user_id].setdefault("boosts", {})
    b.setdefault("luck", 0); b.setdefault("sell", 0); b.setdefault("xp", 0); b.setdefault("crate_luck", 0)
    idle = data[user_id].setdefault("idle", {})
    idle.setdefault("active", False); idle.setdefault("stacks", 0); idle.setdefault("started_at", 0)
    idle.setdefault("camp_biome", data[user_id].get("biome", "village") or "village")
    idle.setdefault("haul", []); idle.setdefault("capacity_upgrades", 0)
    data[user_id].setdefault("ammo_inv", {})
    data[user_id].setdefault("session", None)
    if "equipped_ammo" not in data[user_id]:
        data[user_id]["equipped_ammo"] = None
    if "Bare Hands" not in data[user_id].get("owned_tools", []):
        data[user_id].setdefault("owned_tools", []).insert(0, "Bare Hands")
    data[user_id].setdefault("onboarding", {
        "version": 2, "completed": True, "step": "done", "starter_pack": None})
    data[user_id].setdefault("hunters_path", {"completed": True})
    data[user_id].setdefault("guide_seen", [])
    data[user_id].setdefault("tracking", None)

    _track_daily_active(user_id, today)

def _track_daily_active(user_id: str, today: str) -> None:
    """Once-per-UTC-day bookkeeping: bump stats.active_days (used by the referral
    anti-alt gate) and, when analytics is on, emit daily_active / day_N_return.
    Cheap string compare on the hot path."""
    d = data.get(user_id)
    if not d or d.get("_a_day") == today:
        return
    d["_a_day"] = today
    st = d.setdefault("stats", {})
    st["active_days"] = st.get("active_days", 0) + 1
    if not FEATURE_ANALYTICS:
        return
    analytics(user_id, "daily_active")
    joined = d.get("joined_date", "")
    if joined and joined != today:
        try:
            d0 = datetime.strptime(joined, "%Y-%m-%d").date()
            d1 = datetime.strptime(today,  "%Y-%m-%d").date()
            gap = (d1 - d0).days
            if gap == 1:
                analytics(user_id, "day_1_return")
            elif gap == 3:
                analytics(user_id, "day_3_return")
            elif gap == 7:
                analytics(user_id, "day_7_return")
        except Exception:
            pass

def tick_verify(user_id: str):
    v = data[user_id]["verify"]
    if v["needed"]:
        return
    v["time"] -= 1
    if v["time"] <= 0:
        v["needed"] = True; v["time"] = 250; v["code"] = generate_verify_code()

def init_tribe(tribe_name, user_id):
    if tribe_name not in tribe_data:
        tribe_data[tribe_name] = {
            "description": None, "creator": user_id,
            "roles": {"leader": user_id, "officer": [], "members": [], "recruits": []},
            "banned": [], "level": 1, "xp": 0, "invites": [],
            "premium": False, "max_members": 5,
            "luck_boost": 0, "sell_price_boost": 0, "xp_boost": 0,
        }
        data[user_id]["tribe"] = tribe_name
    for k, v in {
        "description": None, "creator": user_id,
        "roles": {"leader": user_id, "officer": [], "members": [], "recruits": []},
        "banned": [], "level": 1, "xp": 0, "invites": [],
        "premium": False, "max_members": 5,
        "luck_boost": 0, "sell_price_boost": 0, "xp_boost": 0,
    }.items():
        tribe_data[tribe_name].setdefault(k, v)
    _ensure_tribe_fields(tribe_data[tribe_name])


# ─────────────────────────────────────────────
# TRIBE PROGRESSION  (Phase 1)
# ─────────────────────────────────────────────

def _week_tag() -> str:
    """ISO year-week tag, e.g. '2026-W37' — changes exactly at week rollover."""
    y, w, _ = datetime.now(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"

def _tribe_current_members(td: dict) -> list[str]:
    r = td.get("roles", {})
    return ([str(r.get("leader") or "")] + [str(x) for x in r.get("officer", [])]
            + [str(x) for x in r.get("members", [])] + [str(x) for x in r.get("recruits", [])])

def _roll_tribe_contracts(td: dict, scale: int) -> list[dict]:
    out = []
    for spec in TRIBE_CONTRACTS:
        if spec["kind"] == "hunting":
            target = max(spec["min_target"], spec["per_scale"] * scale)
        elif spec["kind"] == "exploration":
            reachable = len({BIOME_NAMES.get(data.get(u, {}).get("biome"), "")
                             for u in _tribe_current_members(td)} - {""}) or 3
            target = max(spec["min_target"], min(spec["max_target"], reachable, 5))
        else:  # teamwork
            target = max(spec["min_target"], min(spec["per_scale"] * scale,
                                                 len(_tribe_current_members(td))))
        out.append({"kind": spec["kind"], "label": spec["label"],
                    "target": int(target), "progress": 0, "done": False})
    return out

def _ensure_tribe_fields(td: dict) -> dict:
    """Backfill Phase-1 tribe-progression fields on a raw tribe dict (idempotent)."""
    td.setdefault("xp", 0)
    td.setdefault("level", 1)
    td.setdefault("max_members", 5)
    r = td.setdefault("roles", {"leader": "0", "officer": [], "members": [], "recruits": []})
    r.setdefault("recruits", [])
    td.setdefault("member_since", {})
    td.setdefault("contrib_lifetime", {})
    td.setdefault("log", [])
    # member cap floor by level (Perk-Shop "+1 Slot" purchases stack above it)
    td["max_members"] = max(int(td.get("max_members", 5)), tribe_member_cap(td.get("level", 1)))
    # backfill member_since for anyone already on the roster
    now = int(time.time())
    for uid in _tribe_current_members(td):
        if uid and uid != "0":
            td["member_since"].setdefault(uid, now)
    wk = td.get("week")
    tag = _week_tag()
    if not isinstance(wk, dict) or wk.get("tag") != tag:
        prev = wk if isinstance(wk, dict) else {}
        active = len([1 for v in prev.get("contrib", {}).values() if v > 0])
        scale  = max(TRIBE_CONTRACT_MIN_GROUP, active)
        td["week"] = {
            "tag": tag, "contrib": {}, "scale_group": scale,
            "contracts": _roll_tribe_contracts(td, scale),
            "explore_biomes": [], "task_members": [], "reroll_used": False,
        }
    return td

def _tribe_log(td: dict, text: str) -> None:
    td.setdefault("log", []).append({"ts": int(time.time()), "text": text})
    del td["log"][:-TRIBE_LOG_MAX]

def _tribe_apply_levelups(td: dict) -> int:
    """Spend banked XP into levels (cap TRIBE_LEVEL_CAP). Returns levels gained."""
    gained = 0
    while td["level"] < TRIBE_LEVEL_CAP and td["xp"] >= tribe_xp_to_next(td["level"]):
        td["xp"] -= tribe_xp_to_next(td["level"])
        td["level"] += 1
        gained += 1
        old_cap = td.get("max_members", 5)
        td["max_members"] = max(old_cap, tribe_member_cap(td["level"]))
        extra = " · +slots" if td["max_members"] > old_cap else ""
        _tribe_log(td, f"`⬆️` Tribe reached **Level {td['level']}**{extra}")
    if td["level"] >= TRIBE_LEVEL_CAP:
        td["xp"] = min(td["xp"], tribe_xp_to_next(TRIBE_LEVEL_CAP))
    return gained

def _tribe_day_counters(uid: str) -> dict:
    """The player's per-day tribe-XP cap counters, reset at date rollover."""
    today = today_utc()
    td = data[uid].setdefault("tribe_day", {})
    if td.get("tag") != today:
        td.clear()
        td.update({"tag": today, "hunts": 0, "daily": False, "tasks": 0})
    return td

async def award_tribe_xp(uid: str, source: str, *, catches: int = 0, biome: str = "") -> dict | None:
    """Grant tribe XP for a member's activity. `source` ∈ 'hunt'|'daily'|'task'.
    Applies per-member daily caps, banks XP + contribution, handles level-ups,
    and feeds the weekly contracts. Safe to call outside any transaction."""
    uid = str(uid)
    tname = data.get(uid, {}).get("tribe")
    if not tname or tname not in tribe_data:
        return None
    async with user_tribe_transaction(uid, tname):
        if data[uid].get("tribe") != tname or tname not in tribe_data:
            return None
        td = tribe_data[tname]
        _ensure_tribe_fields(td)
        cnt = _tribe_day_counters(uid)

        amount = 0
        if source == "hunt":
            room = max(0, TRIBE_XP_HUNT_CAP_DAY - cnt["hunts"])
            amount = min(TRIBE_XP_HUNT, room)
            if amount:
                cnt["hunts"] += amount
        elif source == "daily":
            if not cnt.get("daily"):
                amount = TRIBE_XP_DAILY
                cnt["daily"] = True
        elif source == "task":
            if cnt["tasks"] < TRIBE_XP_TASK_CAP_DAY:
                amount = TRIBE_XP_TASK
                cnt["tasks"] += 1
                if cnt["tasks"] >= 2 and uid not in td["week"]["task_members"]:
                    td["week"]["task_members"].append(uid)

        # ── weekly contract progress (independent of the XP cap) ──
        for i, ct in enumerate(td["week"]["contracts"]):
            before = ct["progress"]
            if ct["kind"] == "hunting" and source == "hunt":
                ct["progress"] += max(0, catches)
            elif ct["kind"] == "exploration" and source == "hunt" and biome:
                if biome not in td["week"]["explore_biomes"]:
                    td["week"]["explore_biomes"].append(biome)
                ct["progress"] = len(td["week"]["explore_biomes"])
            elif ct["kind"] == "teamwork":
                ct["progress"] = len(td["week"]["task_members"])
            if ct["progress"] != before and not ct["done"] and ct["progress"] >= ct["target"]:
                ct["done"] = True
                td["xp"] += TRIBE_XP_CONTRACT[i]
                _tribe_log(td, f"{emoji('check_mark')} Contract complete: **{ct['label']}** (+{TRIBE_XP_CONTRACT[i]} tribe XP)")

        if amount > 0:
            td["xp"] += amount
            td["contrib_lifetime"][uid] = td["contrib_lifetime"].get(uid, 0) + amount
            td["week"]["contrib"][uid] = td["week"]["contrib"].get(uid, 0) + amount

        # ── tribe expedition progress (V2, Phase 31) ──
        if FEATURE_EXPEDITIONS:
            _exp_feed(td, uid, source, catches)

        gained = _tribe_apply_levelups(td)
        return {"leveled": gained > 0, "level": td["level"]} if (amount or gained) else None

# ═══════════════════════════════════════════════════════════════
# TRIBE EXPEDITIONS  ·  vote a route, then normal play fills the bar (V2)
# ═══════════════════════════════════════════════════════════════

def _exp_state(tname: str) -> dict | None:
    exp = tribe_data.get(tname, {}).get("expedition")
    return exp if (exp and not exp.get("done")) else None

def _exp_feed(td: dict, uid: str, source: str, catches: int) -> None:
    """Add expedition points for one activity. Call inside a tribe transaction."""
    exp = td.get("expedition")
    if not exp or exp.get("stage") != "active" or exp.get("done"):
        return
    if time.time() >= exp.get("ends_ts", 0):
        return
    pts = 0
    if source == "hunt":
        pts = TRIBE_EXPEDITION_POINTS["hunt"] + max(0, catches) * TRIBE_EXPEDITION_POINTS["catch"]
    elif source == "daily":
        pts = TRIBE_EXPEDITION_POINTS["daily"]
    elif source == "task":
        pts = TRIBE_EXPEDITION_POINTS["quest"]
    elif source == "myth_kill":
        pts = TRIBE_EXPEDITION_POINTS["myth_kill"]
    if pts <= 0:
        return
    exp["progress"] = exp.get("progress", 0) + pts
    exp.setdefault("contributions", {})
    exp["contributions"][str(uid)] = exp["contributions"].get(str(uid), 0) + pts
    exp.setdefault("participants", [])
    if str(uid) not in exp["participants"]:
        exp["participants"].append(str(uid))

def _exp_lock_route(td: dict) -> None:
    exp = td["expedition"]
    spec = TRIBE_EXPEDITIONS[exp["key"]]
    tally = Counter(exp.get("votes", {}).values())
    route = tally.most_common(1)[0][0] if tally else next(iter(spec["routes"]))
    rspec = spec["routes"][route]
    members = max(1, len(_tribe_current_members(td)))
    goal = int(TRIBE_EXPEDITION_GOAL_PER_MEMBER * members * rspec.get("goal_mult", 1.0))
    now = time.time()
    exp.update({"stage": "active", "route": route, "goal": goal,
                "ends_ts": now + spec.get("hours", 6) * 3600})
    _tribe_log(td, f"`🧭` Route locked: **{rspec['label']}** — {goal:,} points by <t:{int(exp['ends_ts'])}:R>")

def _exp_cooldown_left(td: dict) -> int:
    """Seconds until this tribe may start another expedition (0 = ready).
    Counts from the completion of the last FINISHED one; a cancelled vote has
    no cooldown."""
    exp = td.get("expedition")
    if not exp or not exp.get("done") or not exp.get("completed_ts"):
        return 0
    ready = exp["completed_ts"] + TRIBE_EXPEDITION_COOLDOWN_H * 3600
    return max(0, int(ready - time.time()))

def _exp_start(tname: str, uid: str, key: str) -> tuple[bool, str]:
    td = tribe_data.get(tname)
    if not td:
        return False, "You're not in a tribe."
    _ensure_tribe_fields(td)
    if _exp_state(tname):
        return False, "Your tribe already has an expedition underway."
    cd = _exp_cooldown_left(td)
    if cd > 0:
        return False, f"Your tribe just ran one — next expedition available <t:{int(time.time()) + cd}:R>."
    spec = TRIBE_EXPEDITIONS.get(key)
    if not spec:
        return False, "Unknown expedition."
    if len(_tribe_current_members(td)) < TRIBE_EXPEDITION_MIN_MEMBERS:
        return False, f"You need at least **{TRIBE_EXPEDITION_MIN_MEMBERS}** tribe members."
    now = time.time()
    td["expedition"] = {
        "id": secrets.token_hex(4), "key": key, "stage": "voting",
        "started_ts": now, "vote_ends_ts": now + TRIBE_EXPEDITION_VOTE_MIN,
        "route": None, "votes": {}, "participants": [], "contributions": {},
        "progress": 0, "goal": 0, "ends_ts": 0, "done": False, "opened_by": str(uid),
    }
    _tribe_log(td, f"{emoji('tribe')} `{get_username(uid)}` opened **{spec['name']}** — vote a route!")
    return True, f"**{spec['name']}** opened. Everyone vote a route in `/expedition`."

def _exp_vote(tname: str, uid: str, route: str) -> tuple[bool, str]:
    td = tribe_data.get(tname)
    exp = td and td.get("expedition")
    if not exp or exp.get("stage") != "voting":
        return False, "There's no route vote open."
    spec = TRIBE_EXPEDITIONS[exp["key"]]
    if route not in spec["routes"]:
        return False, "Unknown route."
    exp.setdefault("votes", {})[str(uid)] = route
    members = _tribe_current_members(td)
    need = max(TRIBE_EXPEDITION_MIN_MEMBERS, (len(members) + 1) // 2)
    if len(exp["votes"]) >= need or time.time() >= exp.get("vote_ends_ts", 0):
        _exp_lock_route(td)
        rl = spec["routes"][exp["route"]]["label"]
        return True, f"Vote counted — route locked: **{rl}**! Go hunt."
    return True, "Vote counted."

def _exp_finish(td: dict, tname: str) -> None:
    """Wrap up an active expedition. Applies tribe XP + the log line and moves it
    to stage 'rewarding' with a frozen `pending` payout list. It is NOT marked
    `done` until every member in `pending` has been paid (see _exp_pay_out) — so
    a crash between finish and payout just resumes on the next task tick, and a
    payout is never lost or doubled. Call inside a tribe transaction."""
    exp = td.get("expedition")
    if not exp or exp.get("done") or exp.get("stage") == "rewarding":
        return
    spec = TRIBE_EXPEDITIONS.get(exp["key"], {})
    rspec = spec.get("routes", {}).get(exp.get("route", ""), {})
    success = exp.get("progress", 0) >= exp.get("goal", 1)
    exp["stage"] = "rewarding"
    exp["success"] = success
    exp["completed_ts"] = time.time()
    exp["paid"] = []
    if success:
        td["xp"] += int(rspec.get("xp", 500))
        _tribe_apply_levelups(td)
        _tribe_log(td, f"{emoji('trophy')} Expedition complete — **{spec.get('name','')}** "
                       f"via {rspec.get('label','')} (+{rspec.get('xp',500)} tribe XP)")
        total = max(1, sum(exp.get("contributions", {}).values()))
        pending = []
        for uid, pts in exp.get("contributions", {}).items():
            if pts <= 0:
                continue
            share = pts / total
            pending.append({
                "uid": str(uid),
                "crate": rspec.get("crate", "Rare Crate"),
                "title": rspec.get("title", "") if share >= 0.05 else "",
                "badge": rspec.get("badge", "") if share >= 0.15 else "",
                "gems": 20 if share >= 0.10 else 0,
            })
        exp["pending"] = pending
    else:
        _tribe_log(td, f"`🥀` Expedition failed — **{spec.get('name','')}** ran out of time "
                       f"({exp.get('progress',0):,}/{exp.get('goal',0):,}).")
        exp["pending"] = []
        exp["done"] = True   # nothing to pay out

async def _exp_pay_out(tname: str) -> None:
    """Grant every unpaid expedition reward for a tribe, then mark it done.
    Idempotent + crash-safe: each uid is added to `exp['paid']` in the same
    locked block that grants it, so a retry skips anyone already paid."""
    td = tribe_data.get(tname)
    exp = td and td.get("expedition")
    if not exp or exp.get("done") or exp.get("stage") != "rewarding":
        return
    for entry in list(exp.get("pending", [])):
        uid = str(entry.get("uid", ""))
        if not uid:
            continue
        if uid in exp.get("paid", []):
            continue
        if uid not in data:
            async with tribe_only_transaction(tname):
                e = tribe_data.get(tname, {}).get("expedition")
                if e and uid not in e.setdefault("paid", []):
                    e["paid"].append(uid)
            continue
        try:
            async with user_tribe_transaction(uid, tname):
                e = tribe_data.get(tname, {}).get("expedition")
                if not e or uid in e.get("paid", []):
                    continue
                ci = data[uid].setdefault("crate_inv", {})
                ci[entry["crate"]] = ci.get(entry["crate"], 0) + 1
                if entry.get("title"):
                    _grant_title(uid, entry["title"])
                if entry.get("badge"):
                    _grant_special_badge(uid, entry["badge"])
                if entry.get("gems"):
                    add_gems(uid, entry["gems"], "expedition")
                data[uid].setdefault("stats", {})
                data[uid]["stats"]["expedition_contrib"] = \
                    data[uid]["stats"].get("expedition_contrib", 0) + 1
                e.setdefault("paid", []).append(uid)
            analytics(uid, "expedition_reward", crate=entry["crate"], tribe=tname)
        except Exception as ex:
            print(f"expedition payout failed for {uid}:", ex)
    async with tribe_only_transaction(tname):
        e = tribe_data.get(tname, {}).get("expedition")
        if not e or e.get("done"):
            return
        remaining = [x for x in e.get("pending", [])
                     if str(x.get("uid")) not in e.get("paid", [])]
        if not remaining:
            e["done"] = True
            analytics(None, "expedition_completed", tribe=tname, key=e.get("key"),
                      success=True)

def _exp_bar(cur: int, goal: int, width: int = 16) -> str:
    fill = max(0, min(width, round(width * cur / goal))) if goal else 0
    return "█" * fill + "░" * (width - fill)

def build_expedition_components(user_id: str) -> list:
    tname = data[user_id].get("tribe")
    acc = _accent(user_id)
    def _wrap(body, rows):
        return [{"type": 17, "accent_color": acc, "spoiler": False, "components": [
            {"type": 10, "content": body},
            {"type": 14, "divider": True, "spacing": 1}, *rows,
        ]}]
    back = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Tribe", "custom_id": f"nav:tribe:{user_id}"},
        {"type": 2, "style": 2, "label": "Menu", "custom_id": f"nav:menu:{user_id}"}]}

    if not FEATURE_EXPEDITIONS:
        return _wrap(f"### {emoji('tribe')} Tribe Expeditions\n-# Not active right now.", [back])
    if not tname or tname not in tribe_data:
        return _wrap(f"### {emoji('tribe')} Tribe Expeditions\nJoin or create a tribe first — "
                     "expeditions are a group effort.", [back])

    td = tribe_data[tname]
    _ensure_tribe_fields(td)
    role = tribe_role_of(user_id, tname)
    can_lead = role in ("leader", "officer")
    exp = td.get("expedition")

    if not exp or exp.get("done"):
        last = ""
        if exp and exp.get("done"):
            sp = TRIBE_EXPEDITIONS.get(exp["key"], {})
            last = (f"\n-# Last: **{sp.get('name','')}** — "
                    f"{emoji('check_mark') + ' complete' if exp.get('success') else emoji('cross_mark') + ' failed'}.")
        if not can_lead:
            return _wrap(f"### {emoji('tribe')} Tribe Expeditions — {tname}\n"
                        f"No expedition running. A leader or officer can start one.{last}", [back])
        opts = [{"label": s["name"], "value": k, "emoji": {"name": s["emoji"]},
                 "description": s["blurb"][:100]} for k, s in TRIBE_EXPEDITIONS.items()]
        return _wrap(
            f"### {emoji('tribe')} Tribe Expeditions — {tname}\n"
            f"Pick an expedition. Your tribe then votes a route, and every hunt, "
            f"daily and mythic kill fills the shared bar.{last}\n"
            f"-# Needs **{TRIBE_EXPEDITION_MIN_MEMBERS}+** members.",
            [{"type": 1, "components": [{"type": 3, "custom_id": f"exped:startsel:{user_id}",
              "placeholder": "Start an expedition…", "options": opts}]}, back])

    spec = TRIBE_EXPEDITIONS.get(exp["key"], {})
    if exp.get("stage") == "voting":
        tally = Counter(exp.get("votes", {}).values())
        lines = [f"### {spec.get('emoji', emoji('tribe'))} {spec.get('name','Expedition')} — Route Vote",
                 f"-# {spec.get('blurb','')}", ""]
        rows = []
        rbtns = []
        for rk, r in spec.get("routes", {}).items():
            lines.append(f"{r['emoji']} **{r['label']}** — {r['desc']}  ·  {tally.get(rk,0)} vote(s)")
            rbtns.append({"type": 2, "style": 2, "label": r["label"], "emoji": {"name": r["emoji"]},
                          "custom_id": f"exped:vote:{rk}:{user_id}"})
        lines.append(f"\n-# Locks when most members vote, or <t:{int(exp['vote_ends_ts'])}:R>.")
        for i in range(0, len(rbtns), 3):
            rows.append({"type": 1, "components": rbtns[i:i+3]})
        rows.append(back)
        return _wrap("\n".join(lines), rows)

    if exp.get("stage") == "rewarding":
        r = spec.get("routes", {}).get(exp.get("route", ""), {})
        return _wrap(
            f"### {spec.get('emoji', emoji('tribe'))} {spec.get('name','Expedition')} — "
            f"{'Complete! ' + emoji('trophy') if exp.get('success') else 'Failed'}\n"
            + ("Rewards are being handed out to everyone who contributed — "
               "crates land within the half hour." if exp.get("success")
               else "You didn't reach the goal in time. Regroup and try again soon."),
            [back])

    # active
    r = spec.get("routes", {}).get(exp.get("route", ""), {})
    prog, goal = exp.get("progress", 0), exp.get("goal", 1)
    mine = exp.get("contributions", {}).get(user_id, 0)
    top = sorted(exp.get("contributions", {}).items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_txt = "\n".join(f"-# `{get_username(u)}` — {v:,}" for u, v in top) or "-# No points yet."
    body = (
        f"### {spec.get('emoji', emoji('tribe'))} {spec.get('name','Expedition')}\n"
        f"-# Route: {r.get('emoji','')} **{r.get('label','')}** · ends <t:{int(exp.get('ends_ts',0))}:R>\n\n"
        f"{_exp_bar(prog, goal)}  **{prog:,}/{goal:,}**\n\n"
        f"Your contribution: **{mine:,}**\n\n"
        f"**Top contributors**\n{top_txt}\n\n"
        f"-# Every hunt (+1/catch), daily (+8) and mythic kill (+25) counts. "
        f"Finish for +{r.get('xp',0)} tribe XP and a **{r.get('crate','crate')}** each."
    )
    return _wrap(body, [
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Hunt", "custom_id": f"hunt:again:{user_id}"},
            {"type": 2, "style": 2, "label": "🔄 Refresh", "custom_id": f"exped:refresh:{user_id}"}]},
        back])

# ═══════════════════════════════════════════════════════════════
# SERVER-WIDE WEEKLY GOALS  ·  every server chasing one number (V2, Phase 33-34)
# ═══════════════════════════════════════════════════════════════
# Backed by backend.guild_progress / guild_contributions. Lazy weekly rollover:
# the first touch of a new ISO week finalises the previous week (an ATOMIC claim
# picks the one caller that pays 25+ contributors) and opens a fresh goal scaled
# to the number of Idle Hunter *players* in that server, not Discord members.

_GUILD_GOAL_REWARD_CRATE = "Rare Crate"
_GUILD_GOAL_TITLE        = "Community Hunter"
# gid -> {"tag", "goal"} we have already ensured a row for this process. Bounds
# the member scan + rollover DB work to once per guild per week (+ restart).
_guild_goal_seen: dict[str, dict] = {}

def _guild_scale(guild) -> int:
    """Active Idle Hunter players in this server (fallback: known players)."""
    try:
        hunters = get_server_user_ids(guild)
    except Exception:
        return 5
    now = time.time()
    active = sum(1 for uid in hunters
                 if now - data.get(uid, {}).get("_last_hunt_ts", 0) < 7 * 86400)
    return max(5, active or len(hunters))

async def _guild_goal_finalize(gid: str, prev: dict) -> None:
    """Reward the previous week — exactly once, ever, for this (guild, week)."""
    if not prev:
        return
    # Atomic gate: only the winner of the 0→1 flip distributes rewards. A crash
    # after this means some contributors miss out; it never double-pays.
    try:
        won = await backend.guild_goal_claim_reward_once(gid, prev["week_tag"])
    except Exception:
        return
    if not won:
        return
    met = prev.get("progress", 0) >= prev.get("goal", 1) and prev.get("goal", 0) > 0
    if not met:
        analytics(None, "guild_goal_missed", guild=gid)
        return
    try:
        contributors = await backend.guild_goal_contributors(
            gid, prev["week_tag"], GUILD_GOAL_CONTRIB_MIN)
    except Exception:
        contributors = []
    for uid, amt in contributors:
        if uid not in data:
            continue
        try:
            async with user_transaction(uid):
                ci = data[uid].setdefault("crate_inv", {})
                ci[_GUILD_GOAL_REWARD_CRATE] = ci.get(_GUILD_GOAL_REWARD_CRATE, 0) + 1
                _grant_title(uid, _GUILD_GOAL_TITLE)
            await _dm_user(uid,
                f"## {emoji('earth')} Server Goal Smashed!\nYour server hit its weekly hunting goal and "
                f"you were one of the hunters who carried it. **1× {_GUILD_GOAL_REWARD_CRATE}** "
                f"+ the *{_GUILD_GOAL_TITLE}* title are yours.")
        except Exception as e:
            print("guild goal reward failed:", e)
    analytics(None, "guild_goal_met", guild=gid, contributors=len(contributors))

async def guild_goal_state(guild, *, ensure: bool = True) -> dict | None:
    """Current-week goal row for a guild. With ensure=True (default) it also
    rolls the week over and creates a fresh row when needed."""
    if not FEATURE_SERVER_GOALS or guild is None:
        return None
    gid = str(guild.id)
    tag = _week_tag()
    try:
        st = await backend.guild_goal_get(gid)
    except Exception:
        return None
    if st and st.get("week_tag") == tag:
        return st
    if not ensure:
        return st
    if st and st.get("week_tag") != tag:
        await _guild_goal_finalize(gid, st)
    goal = max(GUILD_GOAL_MIN, min(GUILD_GOAL_MAX,
                                   _guild_scale(guild) * GUILD_GOAL_PER_MEMBER))
    try:
        await backend.guild_goal_set(gid, tag, 0, goal, {}, reward_sent=0)
        return await backend.guild_goal_get(gid)
    except Exception:
        return None

async def _guild_goal_contribute(interaction, user_id: str, n: int) -> None:
    """Feed a hunt's catches into the server's weekly goal. Best-effort; the
    per-process cache keeps this off the DB except once per guild per week."""
    if not FEATURE_SERVER_GOALS or n <= 0:
        return
    guild = getattr(interaction, "guild", None)
    if guild is None:
        return
    gid = str(guild.id)
    tag = _week_tag()
    seen = _guild_goal_seen.get(gid)
    if not seen or seen.get("tag") != tag:
        st = await guild_goal_state(guild)          # rollover + create + member scan
        if not st:
            return
        seen = {"tag": tag, "goal": st.get("goal", 0)}
        _guild_goal_seen[gid] = seen
    try:
        gp, _uc = await backend.guild_goal_contribute(gid, str(user_id), tag, n)
    except Exception:
        return
    goal = seen.get("goal", 0)
    if goal and (gp - n) < goal <= gp:
        analytics(None, "guild_goal_reached", guild=gid)

def build_guild_goal_line(st: dict | None) -> str:
    if not st or not st.get("goal"):
        return ""
    prog, goal = st.get("progress", 0), st["goal"]
    pct = min(100, int(100 * prog / goal)) if goal else 0
    done = f" {emoji('check_mark')}" if prog >= goal else ""
    return (f"{emoji('earth')} **Weekly Server Goal** — catch {goal:,} animals\n"
            f"-# {prog:,}/{goal:,} ({pct}%){done} · "
            f"contribute **{GUILD_GOAL_CONTRIB_MIN}+** for a {_GUILD_GOAL_REWARD_CRATE} + title\n"
            f"-# {_guide_bar(prog, goal)}")

async def _world_goal_line(interaction: discord.Interaction) -> str:
    """Server-goal banner for the World screen. Every path that opens World
    must fetch this itself — it was previously only computed by the /world
    slash command, so the banner vanished the moment you navigated there any
    other way (Menu button, traveling to a new biome, etc)."""
    if not (FEATURE_SERVER_GOALS and interaction.guild is not None):
        return ""
    try:
        return build_guild_goal_line(await guild_goal_state(interaction.guild))
    except Exception:
        return ""

def _tribe_rejoin_ok(uid: str) -> tuple[bool, int]:
    """(allowed, seconds_left) — blocks joining a tribe within the rejoin cooldown."""
    left = data.get(str(uid), {}).get("tribe_left_ts", 0) or 0
    wait = int(left + TRIBE_REJOIN_COOLDOWN_H * 3600 - time.time())
    return (wait <= 0, max(0, wait))

def _tribe_is_banned(td: dict, uid: str) -> bool:
    return str(uid) in [str(x) for x in td.get("banned", [])]

# Server-side price list for the tribe shop — the button custom_id must never
# be trusted for cost/amount/field (it is client-visible and replayable).
TRIBE_SHOP_ITEMS = {
    "luck_boost":       (50, 5),
    "sell_price_boost": (50, 5),
    "xp_boost":         (50, 5),
    "max_members":      (100, 1),
}

def _tribe_join_recruit(td: dict, uid: str) -> None:
    """Add uid as a Recruit (24h probation). Call inside a tribe transaction."""
    uid = str(uid)
    _ensure_tribe_fields(td)
    for k in ("officer", "members", "recruits"):
        if uid in td["roles"].get(k, []):
            td["roles"][k].remove(uid)
    td["roles"].setdefault("recruits", []).append(uid)
    td["member_since"][uid] = int(time.time())
    _tribe_log(td, f"`➕` <@{uid}> joined as a Recruit.")

def _tribe_remove_member(td: dict, uid: str, *, note: str = "left") -> None:
    """Drop uid from every role list + weekly bookkeeping (lifetime contribution
    is kept). Call inside a tribe transaction."""
    uid = str(uid)
    _ensure_tribe_fields(td)
    for k in ("officer", "members", "recruits"):
        if uid in td["roles"].get(k, []):
            td["roles"][k].remove(uid)
    td.get("member_since", {}).pop(uid, None)
    td.get("week", {}).get("contrib", {}).pop(uid, None)
    tm = td.get("week", {}).get("task_members", [])
    if uid in tm:
        tm.remove(uid)
    _tribe_log(td, f"`➖` <@{uid}> {note} the tribe.")

def tribe_role_of(user_id: str, tribe_name: str) -> str | None:
    """Current role of ``user_id`` in ``tribe_name``: 'leader' | 'officer' |
    'member' | None. Always read this immediately before a tribe mutation —
    hidden buttons on a stale panel are not authorization."""
    td = tribe_data.get(tribe_name)
    if not td:
        return None
    roles = td.get("roles", {})
    if str(roles.get("leader")) == str(user_id):
        return "leader"
    if str(user_id) in [str(x) for x in roles.get("officer", [])]:
        return "officer"
    if str(user_id) in [str(x) for x in roles.get("members", [])]:
        return "member"
    if str(user_id) in [str(x) for x in roles.get("recruits", [])]:
        return "recruit"
    return None

_TRIBE_ROLE_RANK = {"leader": 0, "officer": 1, "member": 2, "recruit": 3}

def tribe_roster(tribe_name: str, *, repair: bool = False) -> list[tuple[str, str]]:
    """De-duplicated roster as ``[(uid, role)]`` — each player exactly once, at
    their **highest** role (leader > officer > member > recruit), in list order.
    ``repair=True`` also rewrites the officer/members/recruits lists to drop
    stray duplicates."""
    td = tribe_data.get(tribe_name)
    if not td:
        return []
    r       = td.get("roles", {})
    leader  = str(r.get("leader") or "")
    seen    = {leader} if leader and leader != "0" else set()
    officers, members, recruits = [], [], []
    for src, dst in (("officer", officers), ("members", members), ("recruits", recruits)):
        for x in r.get(src, []):
            x = str(x)
            if x and x != "0" and x not in seen:
                seen.add(x); dst.append(x)
    if repair and any(cur != [str(x) for x in r.get(src, [])]
                      for src, cur in (("officer", officers), ("members", members),
                                       ("recruits", recruits))):
        r["officer"], r["members"], r["recruits"] = officers, members, recruits

    roster: list[tuple[str, str]] = []
    if leader and leader != "0":
        roster.append((leader, "leader"))
    roster += [(o, "officer")  for o in officers]
    roster += [(m, "member")   for m in members]
    roster += [(x, "recruit")  for x in recruits]
    return roster

def _tribe_repair_roles(tribe_name: str) -> bool:
    """Drop stray duplicate uids from a tribe's officer/members lists.
    Returns True if anything changed."""
    td = tribe_data.get(tribe_name)
    if not td:
        return False
    r = td.get("roles", {})
    _snap = lambda: tuple([str(x) for x in r.get(k, [])] for k in ("officer", "members", "recruits"))
    before = _snap()
    tribe_roster(tribe_name, repair=True)
    return _snap() != before

async def _tribe_perm(interaction, user_id: str, tribe_name: str,
                      allowed: tuple = ("leader", "officer")) -> bool:
    """Re-check the user's *current* tribe role right before a mutation. Sends an
    ephemeral and returns False when they no longer qualify."""
    if tribe_role_of(user_id, tribe_name) not in allowed:
        await send_ephemeral_v2(
            interaction,
            f"{emoji('cross_mark')} You no longer have permission to do that in this tribe.",
            0xE74C3C,
        )
        return False
    return True

def add_money(user_id: str, amount: int, source: str) -> None:
    data[user_id]["money"] += amount
    mark_user_dirty(user_id)
    if amount != 0:
        log_economy_event(user_id, source, amount, data[user_id]["money"])
        session_track_money(user_id, source, amount)

def spend_money(user_id: str, amount: int, source: str) -> bool:
    if data[user_id]["money"] < amount:
        return False
    data[user_id]["money"] -= amount
    mark_user_dirty(user_id)
    log_economy_event(user_id, source, -amount, data[user_id]["money"])
    session_track_money(user_id, source, -amount)
    return True

def spend_gems(user_id: str, amount: int, source: str) -> bool:
    if data[user_id]["gems"] < amount:
        return False
    data[user_id]["gems"] -= amount
    mark_user_dirty(user_id)
    log_economy_event(user_id, source, -amount, data[user_id]["gems"], currency="gems")
    return True

def add_gems(user_id: str, amount: int, source: str) -> None:
    data[user_id]["gems"] += amount
    mark_user_dirty(user_id)
    if amount != 0:
        log_economy_event(user_id, source, amount, data[user_id]["gems"], currency="gems")

def _shop_purchase(user_id: str, currency: str, price: int, source: str) -> tuple[bool, str]:
    """Charge ``price`` in ``currency`` ("gems" or "money"). MUST be called inside
    a ``user_transaction``. Returns ``(ok, error_message)`` — on failure nothing
    was charged, so the caller must not grant the item."""
    price = ev_price(int(price))   # event 50%-off, no-op otherwise
    if currency == "gems":
        if not spend_gems(user_id, price, source):
            return False, f"{emoji('cross_mark')} You need {emoji('gem')} {price:,} for that."
    else:
        if not spend_money(user_id, price, source):
            return False, f"{emoji('cross_mark')} You need ◈ {price:,} for that."
    return True, ""

# ─────────────────────────────────────────────
# BADGE / ACHIEVEMENT STAT HELPERS
# ─────────────────────────────────────────────

def get_badge_stat(user_id: str, stat: str) -> int | float:
    d = data[user_id]
    s = d.get("stats", {})
    if stat == "daily_streak":    return d.get("daily_streak", 0)
    if stat == "animals_caught":  return d.get("total_caught", 0)
    if stat == "prestige":        return d.get("prestige", 0)
    if stat == "level":           return d.get("level", 1)
    if stat == "ammo_variety":
        return 1 if s.get("ammo_variety_done", False) else 0
    if stat == "game_master":
        return s.get("game_master_score", 0)
    return s.get(stat, 0)

# ─────────────────────────────────────────────
# BOOST HELPERS
# ─────────────────────────────────────────────

def add_personal_boost(user_id: str, stat: str, amount: int) -> None:
    """Add to a player's personal luck/sell/xp boost, capped at MAX_PERSONAL_BOOST.
    Never *reduces* a player already over the cap (grandfathered) — the cap only
    blocks new growth past it. Admin set_*/max_boosts bypass this entirely."""
    b   = data[user_id].setdefault("boosts", {})
    cur = b.get(stat, 0)
    b[stat] = cur if cur >= MAX_PERSONAL_BOOST else min(MAX_PERSONAL_BOOST, cur + amount)

def get_prestige_boost(user_id: str) -> int:
    return data[user_id].get("prestige", 0) * 20

# ─────────────────────────────────────────────
# TROPHY CABINET  ·  equippable mythic-trophy effects (2026-09-16)
# ─────────────────────────────────────────────
# A trophy is never sold or consumed — see game_data.TROPHY_EFFECTS for what
# each one does. Equipping/unequipping just moves a name in/out of
# equipped_trophies; the effect itself is read live from these helpers at
# whatever system it touches (combat, tracking, travel, camp, hunt...).

def equipped_trophy_names(user_id: str) -> list[str]:
    return data[user_id].get("equipped_trophies", []) or []

def trophy_effect_value(user_id: str, effect_key: str) -> float:
    """Sum of `value` across equipped trophies matching this effect_key.
    Every trophy's effect_key is unique, so in practice this is 0 or exactly
    one trophy's value — summing is just future-proofing."""
    total = 0.0
    for t in equipped_trophy_names(user_id):
        eff = TROPHY_EFFECTS.get(t)
        if eff and eff["effect_key"] == effect_key:
            total += eff["value"]
    return total

def trophy_has_effect(user_id: str, effect_key: str) -> bool:
    return trophy_effect_value(user_id, effect_key) > 0

def trophy_proc(user_id: str, effect_key: str) -> bool:
    """Roll a chance-based trophy effect — `value` is a percent (0-100)."""
    v = trophy_effect_value(user_id, effect_key)
    return v > 0 and random.random() * 100 < v

def unique_trophies_count(user_id: str) -> int:
    return len(data[user_id].get("myth_items", {}) or {})

def trophy_slots_unlocked(user_id: str) -> int:
    n = unique_trophies_count(user_id)
    return sum(1 for t in TROPHY_SLOT_THRESHOLDS if n >= t)

def effective_max_hp(user_id: str) -> int:
    base = data[user_id].get("health", {}).get("max_hp", PLAYER_BASE_HP)
    return int(base + trophy_effect_value(user_id, "max_hp_bonus"))

def _trophy_daily_use(user_id: str, key: str) -> bool:
    """Consume a once-per-day trophy proc (Hydra/Phoenix). Returns True the
    first time `key` is used today (UTC), False on any later attempt until
    the date rolls over."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used  = data[user_id].setdefault("_trophy_daily", {})
    if used.get(key) == today:
        return False
    used[key] = today
    mark_user_dirty(user_id)
    return True

def get_total_boosts(user_id: str) -> dict:
    personal   = data[user_id].get("boosts", {"luck": 0, "sell": 0, "xp": 0})
    prestige_b = get_prestige_boost(user_id)
    tribe_name = data[user_id].get("tribe")
    t_luck = t_sell = t_xp = 0
    if tribe_name and tribe_name in tribe_data:
        td     = tribe_data[tribe_name]
        t_luck = td.get("luck_boost", 0)
        t_sell = td.get("sell_price_boost", 0)
        t_xp   = td.get("xp_boost", 0)
    tool_info  = TOOLS.get(data[user_id].get("tool", "Bare Hands"), {})
    tool_luck  = tool_info.get("boost_luck", 0)
    tool_xp    = tool_info.get("boost_xp", 0)
    ammo_b     = get_ammo_boosts(user_id)
    vehicle_info = VEHICLES.get(data[user_id].get("vehicle"), {})
    temp_b = get_active_temp_boosts(user_id)
    vehicle_cd   = vehicle_info.get("boost_cd", 0)
    vehicle_luck = vehicle_info.get("boost_luck", 0)

    troph_sell = trophy_effect_value(user_id, "sell_pct")
    troph_luck = trophy_effect_value(user_id, "luck_pct")
    troph_cd   = trophy_effect_value(user_id, "hunt_cooldown_reduction")
    if trophy_has_effect(user_id, "luck_world_condition_pct") and active_world_condition(data[user_id].get("biome", "village")):
        troph_luck += trophy_effect_value(user_id, "luck_world_condition_pct")
    troph_xp = 0.0
    if trophy_has_effect(user_id, "xp_low_hp_pct"):
        hp, mx = player_hp(user_id)
        if mx > 0 and hp / mx < 0.5:
            troph_xp += trophy_effect_value(user_id, "xp_low_hp_pct")

    total_luck   = personal.get("luck", 0) + t_luck + prestige_b + tool_luck + ammo_b["luck"] + vehicle_luck + troph_luck
    return {
        "luck":       total_luck + temp_b.get("luck", 0),
        "sell":       personal.get("sell", 0) + t_sell + prestige_b + ammo_b["sell"] + temp_b.get("sell", 0) + troph_sell,
        "xp":         personal.get("xp",   0) + t_xp   + prestige_b + tool_xp + ammo_b["xp"] + temp_b.get("xp", 0) + troph_xp,
        "crate_luck": personal.get("crate_luck", 0),
        "p_luck":     personal.get("luck", 0),
        "p_sell":     personal.get("sell", 0),
        "p_xp":       personal.get("xp",   0),
        "t_luck":     t_luck, "t_sell": t_sell, "t_xp": t_xp,
        "prestige_b": prestige_b,
        "tool_luck":  tool_luck, "tool_xp": tool_xp,
        "ammo_luck":  ammo_b["luck"], "ammo_sell": ammo_b["sell"], "ammo_xp": ammo_b["xp"],
        "cd":         vehicle_cd + troph_cd,
    }

# ─────────────────────────────────────────────
# TRACKING
# ─────────────────────────────────────────────

async def update_user_servers(user_id: str, guild):
    if guild is None:
        return
    user_id  = str(user_id)
    if user_id not in data:
        return
    servers  = data[user_id].setdefault("servers", [])
    guild_id = str(guild.id)
    if guild_id not in servers:
        servers.append(guild_id)
    valid = []
    for sid in servers:
        g = bot.get_guild(int(sid))
        if g is None:
            valid.append(sid); continue
        if g.get_member(int(user_id)) is not None:
            valid.append(sid)
    data[user_id]["servers"] = valid

# ─────────────────────────────────────────────
# STATE DICTS
# ─────────────────────────────────────────────

_lb_state:             dict[str, dict] = {}
_log_state:            dict[str, int]  = {}
_record_state:         dict[str, dict] = {}
_profile_log_page:     dict[str, int]  = {}
_profile_record_page:  dict[str, int]  = {}
_ammo_shop_page:       dict[str, int]  = {}
_vehicle_shop_page:    dict[str, int]  = {}
_tool_shop_page:       dict[str, int]  = {}
_ach_page:             dict[str, int]  = {}
_badge_page:           dict[str, int]  = {}
_tribe_sort:           dict[str, str]  = {}
gift_cache:            dict[str, dict] = {}
_update_page:          dict[str, int] = {}  # Track current page per user
_rules_page:           dict[str, int] = {}
_help_page:            dict[str, int] = {}
_info_state:           dict[str, dict] = {}  # /info encyclopedia: {category, group, name}
_lb_publisher = None    # website leaderboard push (leaderboard_push.LeaderboardPublisher)

# /biomes world-map image. Discord CDN attachment URLs carry a short-lived
# signature (?ex=…&hm=…), so the imported constant is only a seed: a 12h task
# re-signs it through POST /attachments/refresh-urls and the fresh value is
# persisted in runtime_state.json. Always read it via world_map_url().
_world_map_url: str = WORLD_MAP_URL

def world_map_url() -> str:
    return _world_map_url or WORLD_MAP_URL

def _cdn_url_expiring(url: str, skew_seconds: int = 3600) -> bool:
    """True when a signed Discord CDN URL is unsigned-less-than skew from expiry
    (or already expired). Unsigned URLs never expire → False."""
    if not url or "ex=" not in url:
        return False
    try:
        ex_hex = url.split("ex=", 1)[1].split("&", 1)[0]
        return int(ex_hex, 16) - skew_seconds <= int(time.time())
    except (ValueError, IndexError):
        return False

async def refresh_world_map_url(*, force: bool = False) -> None:
    """Re-sign the world-map CDN URL so the /biomes image keeps loading."""
    global _world_map_url
    current = _world_map_url or WORLD_MAP_URL
    if not current or (not force and not _cdn_url_expiring(current)):
        return
    try:
        resp = await bot.http.request(
            Route("POST", "/attachments/refresh-urls"),
            json={"attachment_urls": [current]},
        )
        fresh = (resp or {}).get("refreshed_urls", [])
        new_url = fresh[0].get("refreshed") if fresh else None
        if new_url and new_url != _world_map_url:
            _world_map_url = new_url
            print("✅ World-map URL refreshed.")
    except Exception as e:
        print(f"World-map URL refresh failed: {e}")

# ─────────────────────────────────────────────
# LOTTERY DRAW
# ─────────────────────────────────────────────

async def run_lottery_draw():
    global lottery_data
    ld      = lottery_data
    tickets = ld.get("tickets", {})
    pool    = round(ld.get("pool", 0) * 0.8)
    total_t = sum(tickets.values())

    next_ts = lottery_next_midnight()

    if total_t == 0 or pool == 0:
        ld["tickets"] = {}
        ld["pool"]    = 0
        ld["next_ts"] = next_ts
        save_lottery(ld)
        return

    uids    = list(tickets.keys())
    weights = [tickets[u] for u in uids]
    winner_id = random.choices(uids, weights=weights, k=1)[0]

    winner_tickets = tickets[winner_id]
    chance_pct     = (winner_tickets / total_t) * 100
    cost           = winner_tickets * LOTTERY_TICKET_COST
    profit         = (pool - cost)

    # Close the draw on disk BEFORE paying. If we crash between the payout and
    # the reset, the old order re-drew the same pool on the next start (double
    # payout); now the worst case is one missed payout, which an admin can grant.
    ld["tickets"] = {}
    ld["pool"]    = 0
    ld["next_ts"] = next_ts
    _write_text("lottery.json", json.dumps(ld, indent=4, default=str))

    init_user(winner_id)
    async with user_transaction(winner_id):
        add_money(winner_id, pool, "lottery")
        data[winner_id]["stats"]["lottery_wins"] = (
            data[winner_id]["stats"].get("lottery_wins", 0) + 1
        )
        data[winner_id]["total_money_earned"] = (
            data[winner_id].get("total_money_earned", 0) + pool
        )
    winner_name = get_username(winner_id)

    sorted_buyers = sorted(tickets.items(), key=lambda x: x[1], reverse=True)
    medals        = {0: f"{emoji('first_place_medal')}", 1: f"{emoji('second_place_medal')}", 2: f"{emoji('third_place_medal')}"}
    top_lines     = []
    for i, (uid, tc) in enumerate(sorted_buyers[:5]):
        chance = (tc / total_t) * 100
        name   = get_username(uid)
        medal  = medals.get(i, f"**#{i+1}**")
        top_lines.append(f"{medal} `{chance:.1f}%` chance: `{name}`")
    top_block = "\n".join(top_lines) if top_lines else "-# No participants."

    profit_sign = "+" if profit >= 0 else ""
    profit_pct  = ((profit / cost) * 100) if cost > 0 else 0.0

    content = (
        f"### {emoji('lottery_ticket')} Lottery Winner: `{winner_name}`\n\n"
        f"-# Won: **◈ {pool:,}**\n"
        f"-# Profit: **◈ {profit:,}** ({profit_sign}{profit_pct:.1f}%)\n"
        f"-# Chance: **{chance_pct:.2f}%**\n"
        f"-# Cost: **◈ {cost:,}**\n\n"
        f"**Top Spenders:**\n{top_block}\n\n"
        f"-# Next lottery <t:{next_ts}:R>"
    )

    winner_entry = {
        "user_id":  winner_id,
        "username": winner_name,
        "won":      pool,
        "profit":   profit,
        "chance":   chance_pct,
        "cost":     cost,
        "ts":       int(time.time()),
    }

    ld["last_winner"] = winner_entry
    save_lottery(ld)

    channel = bot.get_channel(LOTTERY_CHANNEL_ID)
    if channel:
        try:
            route = Route(
                "POST", "/channels/{channel_id}/messages",
                channel_id=LOTTERY_CHANNEL_ID,
            )
            await bot.http.request(route, json={
                "flags": V2_FLAGS,
                "components": [{"type": 17, "accent_color": 0xF1C40F, "spoiler": False,
                    "components": [{"type": 10, "content": content}]}],
                "allowed_mentions": {"parse": []},
            })
        except Exception as e:
            print("Lottery channel send error:", e)

# ─────────────────────────────────────────────
# LOTTERY HELPERS
# ─────────────────────────────────────────────

def load_lottery() -> dict:
    try:
        with open("lottery.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"tickets": {}, "last_winner": None, "next_ts": 0, "pool": 0, "last_total_tickets": 0}

def save_lottery(ld: dict):
    _write_json_bg("lottery.json", ld)

def lottery_next_midnight() -> int:
    now = datetime.now(timezone.utc)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(nxt.timestamp())

lottery_data = load_lottery()
if lottery_data["next_ts"] == 0:
    lottery_data["next_ts"] = lottery_next_midnight()
    save_lottery(lottery_data)

# ─────────────────────────────────────────────
# IDLE  ·  HUNTING CAMP
# ─────────────────────────────────────────────
#
# You station hunters at a camp biome of your choice. They passively catch
# animals from that biome into a haul with limited capacity. When the haul is
# full, hunters sit idle until you return to /idle and collect it — the catches
# drop into your normal inventory, exactly like an active hunt.

IDLE_BASE_CAPACITY         = 15     # haul slots with 0 storage upgrades
IDLE_CAPACITY_PER_UPGRADE  = 12
IDLE_MAX_CAPACITY_UPGRADES = 15     # -> up to 195 slots
IDLE_MAX_HUNTERS           = 12
IDLE_BASE_CATCH_RATE       = 4.0    # catches / hour / hunter in a tier-1 biome

def biome_level(biome: str) -> int:
    return next((lvl for k, lvl in BIOME_LEVELS if k == biome), 1)

def idle_cost_for_stack(current_stacks: int) -> int:
    return IDLE_COST * (IDLE_STACK_MULTIPLIER ** current_stacks)

def idle_capacity(user_id: str) -> int:
    up = data[user_id].get("idle", {}).get("capacity_upgrades", 0)
    troph_mult = 1 + trophy_effect_value(user_id, "camp_capacity_pct") / 100   # Bunyip: Billabong Tusk
    return int((IDLE_BASE_CAPACITY + up * IDLE_CAPACITY_PER_UPGRADE) * ev_idle_cap_mult() * troph_mult)

def idle_capacity_upgrade_cost(current_upgrades: int) -> int:
    return 25_000 * (2 ** current_upgrades)

def idle_camp_biome(user_id: str) -> str:
    """The camp's biome for production. Falls back to Village if the player no
    longer meets that biome's level gate (e.g. after a prestige)."""
    b = data[user_id].get("idle", {}).get("camp_biome", "village")
    if b not in BIOME_ANIMALS:
        return "village"
    if data.get(user_id, {}).get("level", 1) < biome_level(b):
        return "village"
    return b

def idle_catches_per_hour(user_id: str) -> float:
    idle = data[user_id].get("idle", {})
    hunters = min(idle.get("stacks", 0), IDLE_MAX_HUNTERS)
    if hunters <= 0:
        return 0.0
    tier = BIOME_TOOL_TIER.get(idle_camp_biome(user_id), 1)
    troph_mult = 1 + trophy_effect_value(user_id, "camp_production_pct") / 100   # Yowie: Coarse Yowie Hair
    # richer biomes yield slower — the dangerous game is rarer
    return hunters * (IDLE_BASE_CATCH_RATE / (1 + tier * 0.12)) * ev_idle_rate_mult() * troph_mult

def idle_can_camp(user_id: str, biome: str) -> tuple[bool, str]:
    """(ok, reason) — a camp biome needs the player's level AND tool tier, same
    gates as hunting there in person."""
    if biome not in BIOME_ANIMALS:
        return False, "Unknown biome."
    lvl_req = biome_level(biome)
    if data[user_id]["level"] < lvl_req:
        return False, f"{BIOME_NAMES[biome]} unlocks at Level {lvl_req:,}."
    tier_req  = BIOME_TOOL_TIER.get(biome, 1)
    tool_name = data[user_id].get("tool", "Bare Hands")
    if get_tool_tier(tool_name) < tier_req:
        return False, f"{BIOME_NAMES[biome]} needs a Tier {tier_req}+ tool (you have {tool_name})."
    return True, ""

def _roll_idle_animal(user_id: str) -> str:
    return random.choice(BIOME_ANIMALS[idle_camp_biome(user_id)])

def idle_tick(user_id: str) -> int:
    """Materialise elapsed passive catches into the haul. Mutates state — call
    inside a ``user_transaction``. Returns how many new catches were added."""
    idle = data[user_id]["idle"]
    if not idle.get("active") or idle.get("stacks", 0) <= 0 or idle.get("started_at", 0) <= 0:
        return 0
    haul = idle.setdefault("haul", [])
    cap  = idle_capacity(user_id)
    if len(haul) >= cap:
        return 0  # full — hunters idle, clock frozen until the haul is collected
    rate = idle_catches_per_hour(user_id)
    if rate <= 0:
        return 0
    now   = time.time()
    n     = int((now - idle["started_at"]) / 3600 * rate)
    if n <= 0:
        return 0
    take = min(n, cap - len(haul))
    for _ in range(take):
        haul.append(_roll_idle_animal(user_id))
    idle["started_at"] = now
    mark_user_dirty(user_id)
    return take

def idle_haul_sell_value(user_id: str) -> int:
    """Approximate ◈ value of the current haul (before rare rolls)."""
    sell_boost = get_total_boosts(user_id)["sell"]
    return sum(int(ANIMAL_DATA.get(a, {}).get("value", 0) * (1 + sell_boost / 100))
              for a in data[user_id]["idle"].get("haul", []))

def idle_seconds_until_full(user_id: str) -> float:
    """Seconds until the haul reaches capacity at the current rate (-1 = never)."""
    idle = data[user_id].get("idle", {})
    rate = idle_catches_per_hour(user_id)
    if rate <= 0:
        return -1.0
    room = idle_capacity(user_id) - len(idle.get("haul", []))
    if room <= 0:
        return 0.0
    elapsed = (time.time() - idle["started_at"]) if idle.get("started_at", 0) > 0 else 0.0
    return max(0.0, (room / rate) * 3600 - elapsed)

def idle_pending_preview(user_id: str) -> int:
    """Read-only estimate of catches waiting (materialised + accrued), capped at
    capacity. Safe to call for menu/profile summaries — never mutates."""
    idle = data[user_id].get("idle", {})
    haul = len(idle.get("haul", []))
    if not idle.get("active") or idle.get("stacks", 0) <= 0:
        return haul
    rate  = idle_catches_per_hour(user_id)
    extra = 0
    if rate > 0 and idle.get("started_at", 0) > 0:
        extra = int((time.time() - idle["started_at"]) / 3600 * rate)
    return min(haul + extra, idle_capacity(user_id))

def collect_idle_haul(user_id: str) -> dict:
    """Flush the haul into the player's inventory (rare rolls, XP, records,
    quests — like an active hunt). Mutates — call inside a ``user_transaction``."""
    idle_tick(user_id)
    idle = data[user_id]["idle"]
    haul = idle.get("haul", [])
    if not haul:
        return {"count": 0, "per_animal": {}, "total_val": 0, "total_xp": 0,
                "level_ups": 0, "rares": 0}

    boosts     = get_total_boosts(user_id)
    sell_boost = boosts["sell"]; xp_boost = boosts["xp"]; luck_boost = boosts["luck"]

    per_animal: dict[str, dict] = {}
    total_val = total_xp = rares = 0
    _sell_ev, _xp_ev = ev_sell_mult(), ev_xp_mult()
    for animal in haul:
        base_val   = ANIMAL_DATA.get(animal, {}).get("value", 0)
        base_xp    = ANIMAL_DATA.get(animal, {}).get("xp", 0)
        sell_value = int(base_val * (1 + sell_boost / 100))
        xp_earned  = int(base_xp * (1 + xp_boost / 100))
        is_rare    = random.random() < rare_catch_chance(luck_boost) + trophy_effect_value(user_id, "perfect_catch_pp") / 100
        if is_rare:
            sell_value *= 3; xp_earned *= 2; rares += 1
            _chp = trophy_effect_value(user_id, "perfect_catch_hp_restore")   # Chupacabra: Hollow Fang
            if _chp:
                hh = data[user_id]["health"]
                hh["hp"] = min(effective_max_hp(user_id), hh["hp"] + int(_chp))
        sell_value = int(sell_value * _sell_ev)
        xp_earned  = int(xp_earned * _xp_ev)
        total_val += sell_value; total_xp += xp_earned
        data[user_id]["inv"].append(animal)
        record_catch(user_id, animal, "Idle Camp", sell_value)
        e = per_animal.setdefault(animal, {"count": 0, "rare": 0, "value": 0, "xp": 0})
        e["count"] += 1; e["value"] += sell_value; e["xp"] += xp_earned
        if is_rare:
            e["rare"] += 1

    data[user_id]["xp"]                      += total_xp
    data[user_id]["stats"]["total_xp_earned"] = data[user_id]["stats"].get("total_xp_earned", 0) + total_xp
    data[user_id]["total_money_earned"]       = data[user_id].get("total_money_earned", 0) + total_val
    data[user_id]["_pending_sell"]            = (data[user_id].get("_pending_sell") or 0) + total_val

    level_ups = 0
    while data[user_id]["xp"] >= xp_for_level(data[user_id]["level"]):
        data[user_id]["xp"]    -= xp_for_level(data[user_id]["level"])
        data[user_id]["level"] += 1
        level_ups += 1

    count = len(haul)
    idle["haul"] = []
    idle["started_at"] = time.time()
    mark_user_dirty(user_id)

    data[user_id]["stats"]["idle_collects"] = data[user_id]["stats"].get("idle_collects", 0) + 1
    if not data[user_id]["stats"].get("first_rare_ts"):
        for animal in per_animal:
            if ANIMAL_DATA.get(animal, {}).get("rarity", "common") in ("rare", "epic"):
                data[user_id]["stats"]["first_rare_ts"] = int(time.time())
                break
    _hp_result = hunters_path_maybe_complete(user_id)

    camp_b = idle_camp_biome(user_id)
    quest_progress(user_id, "idle_collections_quest", 1)
    quest_progress(user_id, "animals_caught", count)
    for animal, e in per_animal.items():
        rarity = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        quest_progress(user_id, "animal_caught_specific", e["count"], animal=animal)
        quest_progress(user_id, "rarity_caught", e["count"], rarity=rarity)
    if rares:
        quest_progress(user_id, "perfect_catches", rares)
    if level_ups:
        quest_progress(user_id, "levels_gained_quest", level_ups)
    quest_progress(user_id, "xp_earned_quest", total_xp)

    add_log_entry(user_id, {
        "ts": int(time.time()), "biome": camp_b, "tool": "Idle Camp", "ammo": None,
        "catches": [{"animal": a, "sell_value": e["value"], "xp_earned": e["xp"],
                     "is_rare": e["rare"] > 0} for a, e in per_animal.items()],
        "total_xp": total_xp, "level_ups": level_ups, "idle": True,
    })

    return {"count": count, "per_animal": per_animal, "total_val": total_val,
            "total_xp": total_xp, "level_ups": level_ups, "rares": rares,
            "hunters_path_result": _hp_result}

# ─────────────────────────────────────────────
# RECORD & LOG HELPERS
# ─────────────────────────────────────────────

def record_catch(user_id: str, animal: str, tool: str, value: int):
    record = data[user_id].setdefault("record", {})
    if animal not in record:
        record[animal] = {"count": 0, "total_earned": 0, "tools": {}, "best": 0}
    record[animal]["count"]        += 1
    record[animal]["total_earned"] += value
    record[animal]["best"]          = max(record[animal].get("best", 0), value)
    record[animal].setdefault("tools", {})[tool] = record[animal]["tools"].get(tool, 0) + 1
    data[user_id]["total_caught"] = data[user_id].get("total_caught", 0) + 1

# ─────────────────────────────────────────────
# SESSION TRACKING  ·  opt-in "/session" continuity log
# ─────────────────────────────────────────────
# A session is nothing but a snapshot start point plus running totals —
# it never changes what a hunt or a gamble actually pays out, it only
# narrates it back. Off by default (data[uid]["session"] is None) so
# players who never touch /session see zero difference.

_SESSION_GAMES = (
    ("blackjack", "Blackjack"),
    ("coinflip",  "Coinflip"),
    ("roulette",  "Roulette"),
    ("slots",     "Slots"),
    ("rps",       "Rock-Paper-Scissors"),
)
SESSION_RECENT_MAX = 8

def _session_game_label(source: str) -> str | None:
    s = source.lower()
    for kw, label in _SESSION_GAMES:
        if kw in s:
            return label
    return None

def session_active(user_id: str) -> bool:
    return data.get(user_id, {}).get("session") is not None

def session_start(user_id: str) -> None:
    data[user_id]["session"] = {
        "started_ts": time.time(),
        "hunts": 0, "value_earned": 0,
        "recent_catches": [],
        "games": {},
    }
    mark_user_dirty(user_id)

def session_stop(user_id: str) -> dict | None:
    sess = data[user_id].get("session")
    data[user_id]["session"] = None
    mark_user_dirty(user_id)
    return sess

def session_track_hunt(user_id: str, catches: list, total_val: int) -> None:
    sess = data.get(user_id, {}).get("session")
    if not sess or not catches:
        return
    sess["hunts"] += 1
    sess["value_earned"] += total_val
    rc = sess.setdefault("recent_catches", [])
    for c in catches:
        rc.insert(0, c["animal"])
    del rc[SESSION_RECENT_MAX:]

def session_track_money(user_id: str, source: str, delta: int) -> None:
    sess = data.get(user_id, {}).get("session")
    if not sess:
        return
    label = _session_game_label(source)
    if not label:
        return
    g = sess.setdefault("games", {}).setdefault(label, {"played": 0, "net": 0})
    g["net"] += delta
    if "bet" in source.lower():
        g["played"] += 1

def session_summary_lines(sess: dict) -> list[str]:
    dur_min = max(0, int((time.time() - sess["started_ts"]) / 60))
    lines = [f"`⏱️` Session length: **{dur_min} min**",
             f"{emoji('bow')} Hunts: **{sess['hunts']}** · ◈ Earned: **{sess['value_earned']:,}**"]
    if sess.get("recent_catches"):
        lines.append(f"{emoji('book')} Recent: " + " · ".join(sess["recent_catches"][:5]))
    games = sess.get("games") or {}
    if games:
        parts = []
        for name, g in games.items():
            sign = "+" if g["net"] >= 0 else ""
            parts.append(f"{name} ({g['played']} played, {sign}◈{g['net']:,})")
        lines.append(emoji('dice') + " " + " · ".join(parts))
    return lines

def session_hunt_line(user_id: str) -> str:
    """Short continuity line shown right on the hunt panel while a session is
    active — 'the last hunt didn't just disappear' feedback the panel itself
    was missing."""
    sess = data.get(user_id, {}).get("session")
    if not sess:
        return ""
    bits = [f"{emoji('stats')} This session: **{sess['hunts']}** hunts · ◈ **{sess['value_earned']:,}** earned"]
    if sess.get("recent_catches"):
        bits.append("Recent: " + " · ".join(sess["recent_catches"][:3]))
    return " — ".join(bits)

def add_log_entry(user_id: str, entry: dict):
    log = data[user_id].setdefault("log", [])
    log.insert(0, entry)
    if len(log) > MAX_LOG_ENTRIES:
        data[user_id]["log"] = log[:MAX_LOG_ENTRIES]

# ─────────────────────────────────────────────
# DAILY HELPERS
# ─────────────────────────────────────────────

def next_midnight_ts() -> int:
    now = datetime.now(timezone.utc)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(nxt.timestamp())

def calc_streak(last_date_str: str, current_streak: int) -> int:
    if not last_date_str:
        return 0
    try:
        last      = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        today     = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        days_missed = (today - last).days - 1
        if days_missed <= 0:
            return current_streak
        decay = int(2 ** (days_missed - 1))
        return max(0, current_streak - decay)
    except Exception:
        return 0

# ─────────────────────────────────────────────
# MAIL HELPERS
# ─────────────────────────────────────────────

def has_unread_mail(user_id: str) -> bool:
    d = data[user_id]
    if d.get("tribe_inv") and not d.get("tribe_inv_read", False):
        return True
    gifts = d.get("gift_mails", [])
    if any(not g.get("read", False) for g in gifts):
        return True
    if DEV_MAIL and d.get("mail_dev_content_read", "") != DEV_MAIL:
        return True
    return False

def has_new_mail_notice(user_id: str) -> bool:
    d = data[user_id]
    if DEV_MAIL and d.get("mail_dev_content_read", "") != DEV_MAIL \
            and d.get("mail_dev_notice_seen", "") != DEV_MAIL:
        return True
    tribe_inv = d.get("tribe_inv")
    if tribe_inv and not d.get("tribe_inv_read", False) \
            and d.get("tribe_inv_notice_seen", "") != tribe_inv:
        return True
    gifts = d.get("gift_mails", [])
    unread_gifts = [g for g in gifts if not g.get("read", False)]
    if unread_gifts:
        gift_notice_key = str(max(g.get("ts", 0) for g in unread_gifts))
        if d.get("gift_mail_notice_seen", "") != gift_notice_key:
            return True
    return False

# ─────────────────────────────────────────────
# BAN HELPERS
# ─────────────────────────────────────────────

def init_ban_record(user_id: str):
    data[user_id].setdefault("ban", {
        "active": False, "reason": "", "expires_ts": 0,
        "issued_ts": 0, "appeals_used": 0, "appeals_max": 2,
    })

def is_banned(user_id: str) -> bool:
    b = data.get(user_id, {}).get("ban", {})
    if not b.get("active"):
        return False
    exp = b.get("expires_ts", 0)
    if exp != 0 and time.time() > exp:
        data[user_id]["ban"]["active"] = False
        
        return False
    return True

def get_ban(user_id: str) -> dict:
    return data.get(user_id, {}).get("ban", {})

# ─────────────────────────────────────────────
# USERNAME HELPERS
# ─────────────────────────────────────────────

_unresolvable_users: set[str] = set()
_username_sweep_started = False

def _username_placeholder(uid: str) -> str:
    return f"User {uid[-4:]}"

def _is_placeholder_name(name: str) -> bool:
    return (not name) or name.startswith("User ")

def get_username(user_id: str) -> str:
    """Cached username lookup. Never performs network I/O (it used to call
    ``requests.get`` synchronously, which blocked the whole event loop on a
    cache miss). Async callers can await :func:`resolve_username` to backfill."""
    user_id_str = str(user_id)
    cached = data.get(user_id_str, {}).get("username", "")
    return cached or _username_placeholder(user_id_str)

async def resolve_username(user_id: str) -> str:
    """Async username lookup that populates the cache. Safe to call from event
    handlers — it uses discord.py's HTTP layer, not blocking ``requests``."""
    user_id_str = str(user_id)
    cached = data.get(user_id_str, {}).get("username", "")
    if cached and not _is_placeholder_name(cached):
        return cached
    if user_id_str in _unresolvable_users:
        return cached or _username_placeholder(user_id_str)
    try:
        user = await bot.fetch_user(int(user_id_str))
        if user_id_str in data:
            data[user_id_str]["username"] = user.name
        return user.name
    except discord.NotFound:
        _unresolvable_users.add(user_id_str)
        return _username_placeholder(user_id_str)
    except Exception as e:
        logger.error(f"resolve_username failed for {user_id_str}: {e}")
        return cached or _username_placeholder(user_id_str)

async def _username_backfill_sweep():
    """One-shot: fill in real usernames for players who only have a placeholder."""
    await asyncio.sleep(10)  # let on_ready settle
    targets = [uid for uid, d in list(data.items())
               if _is_placeholder_name(d.get("username", ""))]
    resolved = 0
    for uid in targets[:1000]:
        before = data.get(uid, {}).get("username", "")
        name   = await resolve_username(uid)
        if name != before and not _is_placeholder_name(name):
            resolved += 1
        await asyncio.sleep(0.3)  # stay well under the fetch-user rate limit
    if resolved:
        print(f"✅ Username backfill: resolved {resolved}/{len(targets)} placeholder names")

# ─────────────────────────────────────────────
# STATISTICS HELPERS
# ─────────────────────────────────────────────

def hunting_duration_str(joined_date_str: str) -> str:
    try:
        joined = datetime.strptime(joined_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now    = datetime.now(timezone.utc)
        delta  = now - joined
        years  = delta.days // 365
        months = (delta.days % 365) // 30
        days   = (delta.days % 365) % 30
        parts  = []
        if years:  parts.append(f"**{years}** year{'s' if years != 1 else ''}")
        if months: parts.append(f"**{months}** month{'s' if months != 1 else ''}")
        if days or not parts: parts.append(f"**{days}** day{'s' if days != 1 else ''}")
        return ", ".join(parts)
    except Exception:
        return "unknown"

def format_joined_date(joined_date_str: str) -> str:
    try:
        d = datetime.strptime(joined_date_str, "%Y-%m-%d")
        return d.strftime("%B %d, %Y")
    except Exception:
        return joined_date_str

def net_worth(user_id: str) -> int:
    d = data[user_id]
    return d.get("money", 0) + inv_sell_value(user_id)

# ─────────────────────────────────────────────
# INVENTORY HELPERS
# ─────────────────────────────────────────────

def inv_sell_value(user_id: str) -> int:
    pending = data[user_id].get("_pending_sell")
    if pending is not None and pending > 0:
        return pending
    sell_boost = get_total_boosts(user_id)["sell"]
    ev = ev_sell_mult()
    return sum(int(ANIMAL_DATA.get(a, {}).get("value", 0) * (1 + sell_boost / 100) * ev)
               for a in data[user_id].get("inv", []))

def inv_summary_lines(user_id: str, max_items: int = INV_DISPLAY_MAX) -> str:
    inv = data[user_id].get("inv", [])
    if not inv:
        return "-# Inventory is empty."
    counts = Counter(inv)
    lines  = [f"-# {animal_emoji(a)} **{a}** ×{c}" for a, c in counts.most_common(max_items)]
    if len(counts) > max_items:
        lines.append(f"-# … +{len(counts) - max_items} more types")
    return "\n".join(lines)

# ─────────────────────────────────────────────
# RAW PAYLOAD HELPERS
# ─────────────────────────────────────────────

# Emoji IDs the bot can actually use in a component `emoji` field — populated in
# on_ready from bot.emojis + application emojis. A custom emoji the bot can't see
# is silently dropped by Discord (leaving a blank slot / broken layout), so we
# strip those before sending and just keep the text label.
_usable_emoji_ids: set[str] = set()

def _clean_components(node):
    """Recursively drop `emoji` dicts that are empty or reference an emoji the
    bot cannot use. Mutates in place; returns the node for convenience."""
    if isinstance(node, list):
        for c in node:
            _clean_components(c)
    elif isinstance(node, dict):
        e = node.get("emoji")
        if isinstance(e, dict):
            eid = e.get("id")
            if (not e
                    or (not eid and not e.get("name"))
                    or (eid and _usable_emoji_ids and str(eid) not in _usable_emoji_ids)):
                node.pop("emoji", None)
        elif "emoji" in node and not isinstance(e, dict):
            node.pop("emoji", None)
        for v in node.values():
            _clean_components(v)
    return node

async def _raw(interaction: discord.Interaction, payload: dict):
    try:
        _clean_components((payload.get("data") or {}).get("components"))
    except Exception:
        pass
    route = Route(
        "POST", "/interactions/{interaction_id}/{interaction_token}/callback",
        interaction_id=interaction.id, interaction_token=interaction.token,
    )
    try:
        await interaction.client.http.request(route, json=payload)
    except discord.NotFound:
        # Discord already discarded this interaction (too much time passed
        # before we could ack — event-loop lag or a slow network hop) before
        # we ever got to reply. There's no valid response left to send here;
        # swallow it instead of letting every caller crash with an "Unknown
        # interaction" traceback for something nobody can recover from.
        cid = ((getattr(interaction, "data", {}) or {}).get("custom_id", "")) or interaction.type
        logger.warning("interaction expired before initial response (custom_id=%s)", cid)

async def update_v2(interaction: discord.Interaction, components: list):
    _clean_components(components)
    await _raw(interaction, {
        "type": 7,
        "data": {"flags": V2_FLAGS, "components": components, "allowed_mentions": {"parse": []}}
    })

async def edit_v2(interaction: discord.Interaction, components: list):
    _clean_components(components)
    route = Route(
        "PATCH",
        "/webhooks/{application_id}/{token}/messages/@original",
        application_id=interaction.application_id,
        token=interaction.token,
    )

    await interaction.client.http.request(route, json={
        "flags": V2_FLAGS,
        "components": components,
        "allowed_mentions": {"parse": []},
    })

async def smart_update_v2(interaction, components):
    # Pick the method that matches the ack state, but fall back to the other one
    # if it fails: the interaction can already be acked (a swallowed defer error,
    # or a second bot instance that beat us to it) in ways ``is_done()`` doesn't
    # see, and vice versa.
    primary, fallback = (
        (edit_v2, update_v2) if interaction.response.is_done()
        else (update_v2, edit_v2)
    )
    try:
        await primary(interaction, components)
        return
    except discord.HTTPException:
        pass
    await fallback(interaction, components)

async def send_v2_followup(interaction: discord.Interaction, components: list, *, ephemeral: bool = False):
    """Send a v2 container. ACK-aware: initial response (type 4) if the
    interaction is still unacknowledged, otherwise on the followup route."""
    _clean_components(components)
    flags = V2_FLAGS | 64 if ephemeral else V2_FLAGS
    if not interaction.response.is_done():
        await _raw(interaction, {"type": 4, "data": {
            "flags": flags, "components": components, "allowed_mentions": {"parse": []},
        }})
        return
    route = Route(
        "POST", "/webhooks/{application_id}/{token}",
        application_id=interaction.application_id,
        token=interaction.token,
    )
    await interaction.client.http.request(
        route,
        json={"flags": flags, "components": components, "allowed_mentions": {"parse": []}}
    )

async def send_ephemeral_v2(interaction: discord.Interaction, content: str, color: int = 0xE74C3C):
    """Send a quick ephemeral v2 container.

    ACK-aware: if the interaction has already been responded to / deferred, this
    goes out on the followup route; otherwise it becomes the initial response
    (type 4) so callers no longer need to defer first.
    """
    container = [{"type": 17, "accent_color": color, "spoiler": False,
        "components": [{"type": 10, "content": content}]}]

    if not interaction.response.is_done():
        await _raw(interaction, {"type": 4, "data": {
            "flags": V2_FLAGS | 64,
            "components": container,
            "allowed_mentions": {"parse": []},
        }})
        return

    route = Route(
        "POST", "/webhooks/{application_id}/{token}",
        application_id=interaction.application_id,
        token=interaction.token,
    )
    await interaction.client.http.request(route, json={
        "flags": V2_FLAGS | 64,
        "components": container,
        "allowed_mentions": {"parse": []},
    })

async def maybe_send_hunt_tip(interaction: discord.Interaction, result: dict) -> None:
    """A hunt result carrying a 'tip' (see run_hunt — opt-out via /settings,
    rate-limited to at most once every TIP_COOLDOWN_SEC) is shown as its own
    private followup rather than crowding the hunt panel itself."""
    tip = result.get("tip")
    if not tip:
        return
    await send_ephemeral_v2(interaction, f"{emoji('tip')} **Tip:** {tip}", 0x3498DB)

# ─────────────────────────────────────────────
# MAIL NOTIFICATION
# ─────────────────────────────────────────────

async def maybe_send_mail_notification(interaction: discord.Interaction, user_id: str):
    init_user(user_id)
    if not has_new_mail_notice(user_id):
        return
    mail_cmd_id = COMMAND_ID.get("mail", "0")
    await send_ephemeral_v2(
        interaction,
        f"### {emoji('mail')} You have new mail!\nUse </mail:{mail_cmd_id}> to check your mailbox.",
        0xF1C40F,
    )
    d = data[user_id]
    if DEV_MAIL and d.get("mail_dev_content_read", "") != DEV_MAIL:
        d["mail_dev_notice_seen"] = DEV_MAIL
    tribe_inv = d.get("tribe_inv")
    if tribe_inv and not d.get("tribe_inv_read", False):
        d["tribe_inv_notice_seen"] = tribe_inv
    gifts = d.get("gift_mails", [])
    unread_gifts = [g for g in gifts if not g.get("read", False)]
    if unread_gifts:
        gift_notice_key = str(max(g.get("ts", 0) for g in unread_gifts))
        d["gift_mail_notice_seen"] = gift_notice_key
    

# ─────────────────────────────────────────────
# VERIFY EMBED (v2)
# ─────────────────────────────────────────────

def _verify_cmd_ref() -> str:
    """`</verify:id>` mention when the hard-coded command id looks real, else a
    plain ``/verify`` — a stale id renders as literal "</verify:...>" text."""
    cmd_id = COMMAND_ID.get("verify", "0")
    return f"</verify:{cmd_id}>" if cmd_id and cmd_id != "0" else "`/verify`"

def build_verify_v2(user_id: str) -> list:
    verify = data[user_id]["verify"]
    code   = verify["code"]

    return [{
        "type": 17,
        "accent_color": 0xE67E22,
        "spoiler": False,
        "components": [
            {
                "type": 10,
                "content":
                    f"## {emoji('lock')} Verification Required\n"
                    f"Hey, <@{user_id}>! Just checking if all is well!\n\n"
                    f"Run {_verify_cmd_ref()} "
                    f"with code to continue playing:\n\n"
                    f"# Code: `{code}`\n\n"
                    "-# This helps prevent automation."
            },
            {
                "type": 14,
                "divider": True,
                "spacing": 1
            },
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 1,
                        "label": "Refresh",
                        "custom_id": f"verify:refresh:{user_id}"
                    }
                ]
            }
        ]
    }]

def verify_needed_components(user_id: str) -> list:
    code    = data[user_id]["verify"]["code"]
    content = (
        f"### {emoji('lock')} Verification Required\n"
        f"Run {_verify_cmd_ref()} with the code below to continue.\n"
        f"We're preventing autoclickers.\n"
        f"Your code: `{code}`"
    )
    return [{"type": 17, "accent_color": 0xE67E22, "spoiler": False,
             "components": [{"type": 10, "content": content}]}]

# ─────────────────────────────────────────────
# Everything
# ─────────────────────────────────────────────

async def check_everything(interaction: discord.Interaction, user_id: str):
    await check_achievements_and_badges(interaction, user_id)
    await maybe_send_mail_notification(interaction, user_id)
    await maybe_grant_event_gift(interaction, user_id)
    await _referral_check_qualified(user_id)
    _rookie_goal_scan(user_id)

async def maybe_grant_event_gift(interaction: discord.Interaction, user_id: str):
    """One-time welcome bonus, granted the first time a player is seen
    during the event."""
    ev = get_active_event()
    if not ev or ev.get("key") != "admin_buff":
        return
    d = data.get(user_id)
    if not d or d.get("_event_gift") == ev["started_ts"]:
        return
    d["_event_gift"] = ev["started_ts"]
    g = ADMIN_BUFF_EVENT
    async with user_transaction(user_id):
        add_money(user_id, g["gift_money"], "event gift")
        d["total_money_earned"] = d.get("total_money_earned", 0) + g["gift_money"]
        add_gems(user_id, g["gift_gems"], "event gift")
        ci = d.setdefault("crate_inv", {})
        ci[g["gift_crate"]] = ci.get(g["gift_crate"], 0) + 1
    try:
        await send_ephemeral_v2(interaction,
            f"### {g['emoji']} Welcome Bonus Check\n"
            f"The admin left this on your desk on the way out:\n"
            f"-# **◈ {g['gift_money']:,}** · {emoji('gem')} **{g['gift_gems']}** · {emoji('package')} **1× {g['gift_crate']}**\n"
            f"-# {event_banner_line()}", 0x2ECC71)
    except Exception:
        pass

# ─────────────────────────────────────────────
# TRAVEL BETWEEN BIOMES (each biome is a place on Earth)
# ─────────────────────────────────────────────

def travel_time_min(from_biome: str, to_biome: str) -> int:
    """Minutes to travel between two biomes — scales with east–west distance on
    the world map, capped at TRAVEL_MAX_MIN (opposite edges)."""
    if ev_travel_free():
        return 0                      # buff event — the company jet
    a = biome_region(from_biome).get("map_x", 50)
    b = biome_region(to_biome).get("map_x", 50)
    return max(1, min(TRAVEL_MAX_MIN, round(abs(a - b) * (TRAVEL_MAX_MIN / 100.0))))

def is_traveling(user_id: str) -> bool:
    t = data[user_id].get("travel")
    return bool(t and time.time() < t.get("arrive_ts", 0))

def travel_tick(user_id: str) -> str | None:
    """If a trip has finished, land the player at the destination. Mutates state
    — safe to call outside a transaction (only touches one user). Returns the
    biome key just arrived at, or None."""
    t = data[user_id].get("travel")
    if not t:
        return None
    if time.time() >= t.get("arrive_ts", 0):
        dest = t.get("dest", data[user_id]["biome"])
        data[user_id]["biome"] = dest
        data[user_id]["travel"] = None
        mark_user_dirty(user_id)
        return dest
    return None

def start_travel(user_id: str, dest: str) -> dict:
    """Begin a trip to ``dest`` from the player's last confirmed biome. Returns
    the new travel dict. Re-routing mid-trip restarts the clock from the origin
    biome (the last place actually stood on)."""
    origin = data[user_id]["biome"]
    mins   = travel_time_min(origin, dest)
    now    = time.time()
    if mins > 0:
        red = trophy_effect_value(user_id, "travel_time_pct")   # Kelpie: Dripping Bridle
        if red:
            mins = max(1, round(mins * (1 - red / 100)))
        if trophy_proc(user_id, "travel_instant_pct"):          # Hippogriff: Primary Flight Quill
            mins = 0
    if mins <= 0:                     # instant (buff event, or a trophy proc) — just arrive
        data[user_id]["biome"]  = dest
        data[user_id]["travel"] = None
        mark_user_dirty(user_id)
        return {"dest": dest, "origin": origin, "depart_ts": now,
                "arrive_ts": now, "mins": 0}
    tr = {"dest": dest, "origin": origin, "depart_ts": now,
          "arrive_ts": now + mins * 60, "mins": mins}
    data[user_id]["travel"] = tr
    mark_user_dirty(user_id)
    return tr

def travel_status_line(user_id: str) -> str:
    """One-line transit banner, or '' when not traveling."""
    t = data[user_id].get("travel")
    if not t or time.time() >= t.get("arrive_ts", 0):
        return ""
    r = biome_region(t["dest"])
    return (f"{emoji('plane')} In transit to {BIOME_EMOJIS.get(t['dest'],'')} **{BIOME_NAMES.get(t['dest'], t['dest'])}** "
            f"({r['region']}) — arrives <t:{int(t['arrive_ts'])}:R>")


# ─────────────────────────────────────────────
# CRAFTING ECONOMY  ·  shards → crystals → crates
# ─────────────────────────────────────────────
# shards[rarity]  — drop from catches (10%), a mythic KILL (20%)
# crystals[rarity] — 9 shards fused, 5 min each, queued via /craft
# crate_inv[name]  — 9 matching crystals bought in the /craft crate shop
# gemstones[rarity] — decorative 5% bonus when opening a crate of that rarity

def _rarity_label(rarity: str) -> str:
    return rarity[:1].upper() + rarity[1:]

def shard_count(user_id: str, rarity: str) -> int:
    return int(data.get(user_id, {}).get("shards", {}).get(rarity, 0))

def crystal_count(user_id: str, rarity: str) -> int:
    return int(data.get(user_id, {}).get("crystals", {}).get(rarity, 0))

def add_shard(user_id: str, rarity: str, n: int = 1) -> None:
    s = data[user_id].setdefault("shards", {})
    s[rarity] = s.get(rarity, 0) + n

def add_crystal(user_id: str, rarity: str, n: int = 1) -> None:
    c = data[user_id].setdefault("crystals", {})
    c[rarity] = c.get(rarity, 0) + n

def add_gemstone(user_id: str, rarity: str, n: int = 1) -> None:
    g = data[user_id].setdefault("gemstones", {})
    g[rarity] = g.get(rarity, 0) + n

def craft_tick(user_id: str) -> int:
    """Convert any finished crystal crafts in the queue into crystals. Mutates
    one user — safe outside a transaction. Returns how many crystals completed."""
    q = data.get(user_id, {}).get("craft_queue")
    if not q:
        return 0
    now  = time.time()
    done = [e for e in q if e.get("done_ts", 0) <= now]
    if not done:
        return 0
    for e in done:
        add_crystal(user_id, e["rarity"], 1)
    data[user_id]["craft_queue"] = [e for e in q if e.get("done_ts", 0) > now]
    mark_user_dirty(user_id)
    return len(done)

def queue_crystal_craft(user_id: str, rarity: str) -> dict:
    """Spend CRYSTAL_SHARD_COST shards to queue one crystal craft. Serial queue —
    each craft starts when the previous finishes. Call inside a transaction."""
    if rarity not in RARITY_KEYS:
        return {"ok": False, "reason": "bad_rarity"}
    q = data[user_id].setdefault("craft_queue", [])
    if len(q) >= CRAFT_QUEUE_MAX:
        return {"ok": False, "reason": "queue_full"}
    if shard_count(user_id, rarity) < CRYSTAL_SHARD_COST:
        return {"ok": False, "reason": "not_enough_shards"}
    data[user_id]["shards"][rarity] -= CRYSTAL_SHARD_COST
    if ev_craft_instant():                       # buff event — the forge runs itself
        add_crystal(user_id, rarity, 1)
        mark_user_dirty(user_id)
        return {"ok": True, "rarity": rarity, "done_ts": time.time(), "queued": len(q), "instant": True}
    start = max([time.time()] + [e.get("done_ts", 0) for e in q])
    done_ts = start + CRYSTAL_CRAFT_SECONDS
    q.append({"rarity": rarity, "done_ts": done_ts})
    mark_user_dirty(user_id)
    return {"ok": True, "rarity": rarity, "done_ts": done_ts, "queued": len(q)}

def gemstone_line(user_id: str) -> str:
    """Profile line for decorative gemstones — '' when the player has none."""
    g = data.get(user_id, {}).get("gemstones", {}) or {}
    parts = [f"{GEMSTONE_ICONS[r]} {int(g[r])}" for r in RARITY_KEYS if g.get(r, 0) > 0]
    return (f"{emoji('gem')} Gemstones: " + " · ".join(parts)) if parts else ""

def craft_queue_summary(user_id: str) -> str:
    q = sorted(data.get(user_id, {}).get("craft_queue", []), key=lambda e: e.get("done_ts", 0))
    if not q:
        return ""
    lines = []
    for e in q[:6]:
        ico = CRYSTAL_ICONS.get(e["rarity"], "`🔷`")
        lines.append(f"-# {ico} {_rarity_label(e['rarity'])} Crystal — <t:{int(e['done_ts'])}:R>")
    if len(q) > 6:
        lines.append(f"-# …and {len(q) - 6} more")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# HUNT LOGIC
# ─────────────────────────────────────────────

def run_hunt(user_id: str) -> dict:
    init_user(user_id)

    now = time.time()
    cd  = data[user_id]["hunt_cd"]

    # Per-player, bounded hunt-timing history. An autoclicker fires at a near
    # constant interval; a human varies. We only nudge a verify check on a long,
    # implausibly tight streak — identical timing alone is not proof of cheating,
    # and one global list (the old design) mixed every player's hunts together.
    ht      = data[user_id].setdefault("_hunt_times", [])
    last_ts = data[user_id].get("_last_hunt_ts")
    data[user_id]["_last_hunt_ts"] = now
    if last_ts is not None:
        ht.append(round(now - last_ts, 2))
        del ht[:-12]                       # keep only the last 12 intervals
        if len(ht) >= 10 and (max(ht) - min(ht)) <= 0.10:
            data[user_id]["verify"]["time"] = 1   # tick_verify below trips it
            ht.clear()

    tick_verify(user_id)
    if data[user_id]["verify"]["needed"]:
        return {"ok": False, "verify": True}

    # Arrived while away? Land first, then continue.
    travel_tick(user_id)
    if is_traveling(user_id):
        t = data[user_id]["travel"]
        return {"ok": False, "verify": False, "traveling": True,
                "dest": t["dest"], "arrive_ts": int(t["arrive_ts"])}

    # A boss encounter is still unresolved — re-show it instead of a new hunt.
    if data[user_id].get("_boss"):
        return {"ok": False, "verify": False, "boss_pending": True,
                "creature": data[user_id]["_boss"]["creature"]}

    # A normal-animal encounter is still unresolved — same idea, smaller stakes.
    if data[user_id].get("fight"):
        return {"ok": False, "verify": False, "animal_fight_pending": True,
                "animal": data[user_id]["fight"].get("animal", "")}

    # A tracking sequence is still in progress — resume it (or drop a stale one).
    _tr = data[user_id].get("tracking")
    if _tr:
        if _tr.get("expires_ts", 0) <= now:
            data[user_id]["tracking"] = None
        else:
            return {"ok": False, "verify": False, "tracking_pending": True,
                    "creature": _tr.get("creature", "")}

    if now < cd:
        return {"ok": False, "cooldown_ts": int(cd), "remaining": cd - now, "verify": False}

    biome     = data[user_id]["biome"]
    tool_name = data[user_id].get("tool", "Bare Hands")

    if not can_hunt_biome(tool_name, biome):
        return {"ok": False, "verify": False, "tool_locked": True,
                "biome_name": BIOME_NAMES[biome],
                "req_tier":   BIOME_TOOL_TIER.get(biome, 1),
                "tool_name":  tool_name}

    needs_ammo = tool_needs_ammo(tool_name)
    multi      = TOOLS.get(tool_name, {}).get("multi_catch", 1)
    ammo_name  = get_equipped_ammo(user_id)
    ammo_cost  = multi

    if needs_ammo:
        if not ammo_name or not ammo_compatible_with_tool(ammo_name, tool_name):
            _atype = get_tool_ammo_type(tool_name)
            _inv   = data[user_id].get("ammo_inv", {})
            owns_ammo = any(
                qty > 0 and AMMO.get(n, {}).get("ammo_type") == _atype
                for n, qty in _inv.items()
            )
            return {"ok": False, "verify": False, "no_ammo": True,
                    "ammo_type": AMMO_TYPE_LABELS.get(_atype, "ammo"),
                    "tool_name": tool_name, "owns_ammo": owns_ammo}
        if get_ammo_count(user_id, ammo_name) < ammo_cost:
            data[user_id]["equipped_ammo"] = None
            return {"ok": False, "verify": False, "no_ammo": True,
                    "ammo_type": AMMO_TYPE_LABELS.get(get_tool_ammo_type(tool_name), "ammo"),
                    "tool_name": tool_name, "ran_out": True}

    boosts     = get_total_boosts(user_id)
    sell_boost = boosts["sell"]
    xp_boost   = boosts["xp"]
    luck_boost = boosts["luck"]

    # World condition for this region (all 1.0 when Normal / feature off).
    world_mods  = get_world_modifiers(biome)
    _wc_active  = active_world_condition(biome)

    # Tips are opt-out and deliberately rare — a hard cooldown on top of the
    # dice roll so they can't cluster even for someone hunting constantly.
    tip = None
    if (data[user_id].get("tips_enabled", True)
            and now - data[user_id].get("_last_tip_ts", 0) >= TIP_COOLDOWN_SEC
            and random.randint(1, TIP_CHANCE) == 1):
        tip = random.choice(TIPS)
        data[user_id]["_last_tip_ts"] = now

    # ── Mythical-creature encounter — rolled FIRST. When a cryptid turns up, the
    #    hunt is nothing but the encounter: no ordinary catches, no ammo spent,
    #    no shard/crate drops. Only ever one at a time (the _boss guard above).
    # Suppressed through the early stretch of Hunter's Path (see
    # hunters_path_myths_allowed): a mythic dropping into a player's very
    # first hunts undercuts both systems at once — it steals the moment from
    # whichever early Path step they were mid-chasing, and it burns the "holy
    # crap, there's way more later" impact on someone who hasn't even seen
    # the normal loop feel good yet. It unlocks partway through the Path
    # (once "travel" is done) since the Path's own final step needs one to
    # actually fire, and rolls exactly as before once the Path is done, was
    # never active, or the feature is disabled.
    if not data[user_id].get("_boss") and hunters_path_myths_allowed(user_id):
        myth_pool = BIOME_MYTHS.get(biome, [])
        _sight_roll = _sighting_encounter_roll(user_id, biome)
        _forced_creature = ""
        if _sight_roll is not None:
            # An active sighting OWNS this biome's encounter roll — either
            # suppressing it to nothing (still hidden: nothing should upstage
            # its own reveal) or overriding it with a flat, pity-protected
            # shot at the specific creature (its post-reveal window).
            _enc, _forced_creature = _sight_roll
        else:
            _lk   = max(0, luck_boost)
            _enc_cap = MYTH_ENCOUNTER_MAX_WORLD if world_mods["myth_mult"] > 1 else MYTH_ENCOUNTER_MAX
            _enc  = min(_enc_cap,
                        (MYTH_ENCOUNTER_BASE + MYTH_ENCOUNTER_LUCK * _lk / (_lk + 200))
                        * ev_myth_encounter_mult()
                        * world_mods["myth_mult"])
        if myth_pool and random.random() < _enc:
            creature = _forced_creature or random.choice(myth_pool)
            if _forced_creature:
                data[user_id].setdefault("_myth_pity", {})["count"] = 0
            eff_cd = max(1.0, (HUNT_COOLDOWN - boosts.get("cd", 0)) * ev_hunt_cd_mult())
            data[user_id]["hunt_cd"] = now + eff_cd
            quest_progress(user_id, "hunts_done",      1)
            quest_progress(user_id, "hunts_in_biome",  1, biome=biome)
            quest_progress(user_id, "tool_tier_hunts", 1, tool_tier=TOOLS.get(tool_name, {}).get("tier", 1))
            data[user_id]["stats"]["lifetime_hunts"] = data[user_id]["stats"].get("lifetime_hunts", 0) + 1
            if data[user_id]["stats"]["lifetime_hunts"] == 10:
                analytics(user_id, "hunts_10")
            add_log_entry(user_id, {
                "ts": int(now), "biome": biome, "tool": tool_name, "ammo": ammo_name,
                "catches": [], "total_xp": 0, "level_ups": 0, "myth": creature,
            })
            analytics(user_id, "myth_encounter", creature=creature, biome=biome)
            data[user_id]["stats"]["myth_encounters"] = data[user_id]["stats"].get("myth_encounters", 0) + 1
            _sighting_add_clues(user_id, biome)
            _mhp = FIGHT_MONSTER_HP_BASE + BIOME_TOOL_TIER.get(biome, 1) * FIGHT_MONSTER_HP_TIER
            if FEATURE_TRACKING:
                _tracking_start(user_id, creature, biome)
                analytics(user_id, "myth_tracking_started", creature=creature, biome=biome)
            else:
                refresh_health(user_id)   # HP is persistent now — no fresh 100 per fight
                data[user_id]["_boss"] = {
                    "creature": creature, "biome": biome,
                    "ts": int(now), "eid": secrets.token_hex(4),
                    "mhp": _mhp, "mhp_max": _mhp, "turn": 1,
                    "fallen": False, "guard": False, "enrage": False, "mdebuff": False, "log": [],
                }
            return {
                "ok": True,
                "biome": biome, "biome_name": BIOME_NAMES[biome], "biome_emoji": BIOME_EMOJIS[biome],
                "catches": [], "total_xp": 0,
                "level": data[user_id]["level"], "xp": data[user_id]["xp"],
                "xp_needed": xp_for_level(data[user_id]["level"]),
                "balance": data[user_id]["money"],
                "pending_sell_value": 0,
                "level_ups": 0, "tip": tip,
                "verify": False,
                "next_hunt_ts": int(data[user_id]["hunt_cd"]),
                "tool": tool_name, "ammo": ammo_name,
                "remaining_ammo": (get_ammo_count(user_id, ammo_name)
                                   if (needs_ammo and ammo_name) else None),
                "shard_drops": {}, "crate_drops": {},
                "myth_encounter": (creature if not FEATURE_TRACKING else None),
                "tracking_encounter": (creature if FEATURE_TRACKING else None),
            }

    catches   = []
    total_xp  = 0
    total_val = 0

    _sell_ev = ev_sell_mult() * world_mods["sell_mult"]
    _xp_ev   = ev_xp_mult()   * world_mods["xp_mult"]
    _rare_p  = min(RARE_CATCH_MAX_WORLD if world_mods["rare_mult"] > 1 else 1.0,
                   rare_catch_chance(luck_boost) * world_mods["rare_mult"]
                   + trophy_effect_value(user_id, "perfect_catch_pp") / 100)   # Grindylow: Webbed Claw

    rolled = [random.choice(BIOME_ANIMALS[biome]) for _ in range(multi)]

    # ── One dangerous animal, at most, becomes an interactive encounter ──
    # Every OTHER rolled animal (including any not selected) resolves as an
    # instant catch as always. Never fires on top of an existing fight/tracking,
    # and never fires within MIN_ENCOUNTER_HUNTS_GAP hunts of the last one —
    # keeps encounters a rare bonus moment, not a chained run of interruptions.
    danger_result = None
    gap_ok = data[user_id].get("hunts_since_fight", MIN_ENCOUNTER_HUNTS_GAP) >= MIN_ENCOUNTER_HUNTS_GAP
    if (FEATURE_ANIMAL_COMBAT and gap_ok and not data[user_id].get("fight")
            and not data[user_id].get("_boss") and not tracking_active(user_id)):
        candidates = [a for a in rolled if random.random() < animal_encounter_chance(a)]
        if candidates:
            danger_pick = max(candidates, key=encounter_priority)
            rolled.remove(danger_pick)   # only that one occurrence
            danger_result = start_animal_encounter(user_id, danger_pick, biome)
    data[user_id]["hunts_since_fight"] = (
        0 if danger_result else
        data[user_id].get("hunts_since_fight", MIN_ENCOUNTER_HUNTS_GAP) + 1
    )

    for animal in rolled:
        animal_value = ANIMAL_DATA.get(animal, {}).get("value", 0)
        sell_value   = int(animal_value * (1 + sell_boost / 100))
        animal_xp    = ANIMAL_DATA.get(animal, {}).get("xp", 0)
        xp_earned    = int(animal_xp * (1 + xp_boost / 100))
        is_rare      = random.random() < _rare_p
        if is_rare:
            sell_value *= 3; xp_earned *= 2
            _chp = trophy_effect_value(user_id, "perfect_catch_hp_restore")   # Chupacabra: Hollow Fang
            if _chp:
                hh = data[user_id]["health"]
                hh["hp"] = min(effective_max_hp(user_id), hh["hp"] + int(_chp))
        sell_value = int(sell_value * _sell_ev)
        xp_earned  = int(xp_earned * _xp_ev)

        # Catch-excitement flags — computed against the record BEFORE this
        # catch is recorded, so "new species" / "personal best" reflect what
        # actually just happened rather than the post-write state.
        _rarity   = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        _prior    = data[user_id].get("record", {}).get(animal)
        is_new_species  = _prior is None
        is_personal_best = (not is_new_species and _prior.get("best", 0) > 0
                             and sell_value > _prior.get("best", 0))
        is_first_rare = (_rarity in ("rare", "epic")
                          and not data[user_id]["stats"].get("first_rare_ts"))
        if is_first_rare:
            data[user_id]["stats"]["first_rare_ts"] = int(now)

        catches.append({"animal": animal, "sell_value": sell_value,
                        "xp_earned": xp_earned, "is_rare": is_rare,
                        "is_new_species": is_new_species,
                        "is_personal_best": is_personal_best,
                        "is_first_rare": is_first_rare})
        total_xp  += xp_earned
        total_val += sell_value
        data[user_id]["inv"].append(animal)
        record_catch(user_id, animal, tool_name, sell_value)
        if tool_name not in data[user_id]["stats"].get("tools_used", []):
            data[user_id]["stats"].setdefault("tools_used", []).append(tool_name)
        if needs_ammo:
            data[user_id]["stats"]["ammo_used"] = data[user_id]["stats"].get("ammo_used", 0) + 1
        data[user_id]["stats"]["total_xp_earned"] = \
            data[user_id]["stats"].get("total_xp_earned", 0) + xp_earned

    if catches:
        _vhp = trophy_effect_value(user_id, "hunt_hp_restore")   # Vampires: Coffin Nail
        if _vhp:
            hh = data[user_id]["health"]
            hh["hp"] = min(effective_max_hp(user_id), hh["hp"] + int(_vhp))

    # How much ammo this hunt actually consumed — captured before ammo_name is
    # cleared below, so the hunt that empties the stack still advances the quest.
    ammo_spent_this_hunt = ammo_cost if (needs_ammo and ammo_name and not ev_ammo_free()) else 0
    if needs_ammo and ammo_name and not ev_ammo_free() and trophy_proc(user_id, "ammo_save_pct"):  # Zombie: Vial of Grave Dust
        ammo_spent_this_hunt = 0
        remaining_ammo = get_ammo_count(user_id, ammo_name)
    elif needs_ammo and ammo_name and not ev_ammo_free():
        consume_ammo(user_id, ammo_name, ammo_cost)
        remaining_ammo = get_ammo_count(user_id, ammo_name)
        if remaining_ammo == 0:
            data[user_id]["equipped_ammo"] = None
            ammo_name = None
    elif needs_ammo and ammo_name:
        remaining_ammo = get_ammo_count(user_id, ammo_name)   # buff event — nothing spent
    else:
        remaining_ammo = None

    effective_cd = max(1.0, (HUNT_COOLDOWN - boosts.get("cd", 0)) * ev_hunt_cd_mult())
    data[user_id]["hunt_cd"]            = now + effective_cd
    data[user_id]["xp"]                += total_xp
    data[user_id]["total_money_earned"] = data[user_id].get("total_money_earned", 0) + total_val
    data[user_id]["_pending_sell"]      = (data[user_id].get("_pending_sell") or 0) + total_val
    session_track_hunt(user_id, catches, total_val)

    level_ups = 0
    while data[user_id]["xp"] >= xp_for_level(data[user_id]["level"]):
        data[user_id]["xp"]    -= xp_for_level(data[user_id]["level"])
        data[user_id]["level"] += 1
        level_ups += 1

    # ── Materials: per-catch shard / direct-crate rolls ─────────────
    crate_luck_boost = boosts.get("crate_luck", 0)
    _ev_sh, _ev_cr = ev_shard_chance(), ev_crate_chance()
    shard_drops: dict[str, int] = {}
    crate_drops: dict[str, int] = {}
    auto_opened: list[str] = []   # "Settings → Auto-Open Crates" reward lines, shown instead of crate_drops
    auto_open = data[user_id].get("auto_open_crates", False)
    for c in catches:
        c_rarity = ANIMAL_DATA.get(c["animal"], {}).get("rarity", "common")
        roll = roll_catch_drops(c_rarity, crate_luck_boost,
                                shard_chance=_ev_sh, crate_chance=_ev_cr, biome=biome,
                                crate_chance_bonus=trophy_effect_value(user_id, "crate_drop_pp") / 100)  # Loch Ness
        if roll["shard"]:
            add_shard(user_id, roll["shard"], 1)
            shard_drops[roll["shard"]] = shard_drops.get(roll["shard"], 0) + 1
        if roll["crate"]:
            if auto_open:
                reward, extras, _ = _resolve_crate_reward(user_id, roll["crate"])
                bonus = f" +{GEMSTONE_ICONS.get(extras['gemstone'], emoji('gem'))}" if extras.get("gemstone") else ""
                auto_opened.append(f"{CRATE_TIERS[roll['crate']]['emoji']} {roll['crate']} → {_fmt_reward(reward)}{bonus}")
            else:
                ci = data[user_id].setdefault("crate_inv", {})
                ci[roll["crate"]] = ci.get(roll["crate"], 0) + 1
                crate_drops[roll["crate"]] = crate_drops.get(roll["crate"], 0) + 1

    # Quests
    tool_tier = TOOLS.get(tool_name, {}).get("tier", 1)
    data[user_id]["stats"]["lifetime_hunts"] = data[user_id]["stats"].get("lifetime_hunts", 0) + 1
    if data[user_id]["stats"]["lifetime_hunts"] == 10:
        analytics(user_id, "hunts_10")
    quest_progress(user_id, "hunts_done",         1)
    quest_progress(user_id, "hunts_in_biome",     1, biome=biome)
    quest_progress(user_id, "tool_tier_hunts",    1, tool_tier=tool_tier)
    if ammo_spent_this_hunt:
        quest_progress(user_id, "ammo_used_quest",  ammo_spent_this_hunt)
    for c in catches:
        animal  = c["animal"]
        rarity  = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        quest_progress(user_id, "animals_caught",       1)
        quest_progress(user_id, "animal_caught_specific", 1, animal=animal)
        quest_progress(user_id, "rarity_caught",        1, rarity=rarity)
        if c.get("is_rare"):
            quest_progress(user_id, "perfect_catches",  1)
    _mats_dropped = sum(shard_drops.values()) + sum(crate_drops.values()) + len(auto_opened)
    if _mats_dropped:
        quest_progress(user_id, "crate_drops_earned", _mats_dropped)
    if level_ups:
        quest_progress(user_id, "levels_gained_quest", level_ups)
    quest_progress(user_id, "xp_earned_quest", total_xp)

    add_log_entry(user_id, {
        "ts": int(now), "biome": biome, "tool": tool_name, "ammo": ammo_name,
        "catches": catches, "total_xp": total_xp, "level_ups": level_ups,
    })

    _rares = sum(1 for c in catches if c.get("is_rare"))
    _wc_key = _wc_active["key"] if _wc_active else ""
    analytics(user_id, "hunt", biome=biome, catches=len(catches),
              rare=_rares, level_ups=level_ups, condition=_wc_key)
    if _rares:
        analytics(user_id, "rare_catch", biome=biome, n=_rares)
    if _wc_key:
        data[user_id]["stats"]["world_conditions_hunted"] = \
            data[user_id]["stats"].get("world_conditions_hunted", 0) + 1
    _sighting_add_clues(user_id, biome)
    _guide = data[user_id].setdefault("guide_seen", [])
    if biome not in _guide:
        _guide.append(biome)
        analytics(user_id, "region_explored", biome=biome, total=len(_guide))
        _grant_guide_titles(user_id)

    # One checkpoint covers every Path step a single hunt could just have
    # finished (hunt_with_tool, discover_5, travel, catch_new_region,
    # first_rare, myth_lead) — each is a live check, so catching them all
    # here instead of at each individual trigger point is exactly equivalent.
    _hp_result = hunters_path_maybe_complete(user_id)

    return {
        "ok": True,
        "biome": biome, "biome_name": BIOME_NAMES[biome], "biome_emoji": BIOME_EMOJIS[biome],
        "catches": catches, "total_xp": total_xp,
        "level": data[user_id]["level"], "xp": data[user_id]["xp"],
        "xp_needed": xp_for_level(data[user_id]["level"]),
        "balance": data[user_id]["money"],
        "pending_sell_value": total_val,
        "level_ups": level_ups, "tip": tip,
        "verify": False,
        "next_hunt_ts": int(data[user_id]["hunt_cd"]),
        "tool": tool_name, "ammo": ammo_name, "remaining_ammo": remaining_ammo,
        "shard_drops": shard_drops,
        "crate_drops": crate_drops,
        "auto_opened": auto_opened,
        "myth_encounter": None,
        "animal_encounter": danger_result,
        "hunters_path_result": _hp_result,
    }

# ─────────────────────────────────────────────
# SELL ALL
# ─────────────────────────────────────────────

def sell_all_inv(user_id: str) -> dict:
    inv = data[user_id]["inv"]
    if not inv:
        return {"total": 0, "count": 0}
    count = len(inv)
    total = data[user_id].pop("_pending_sell", None)
    if total is None:
        sell_boost = get_total_boosts(user_id)["sell"]
        ev = ev_sell_mult()
        total = sum(int(ANIMAL_DATA.get(a, {}).get("value", 0) * (1 + sell_boost / 100) * ev) for a in inv)
    data[user_id]["inv"] = []
    add_money(user_id, total, "sell all")

    # Don't re-add to total_money_earned — run_hunt already counted it
    return {"total": total, "count": count}


# ─────────────────────────────────────────────
# MYTHICAL-CREATURE ENCOUNTER RESOLUTION
# ─────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════
# TRACKING SEQUENCE — the approach before the fight (V2, Phase 11-15)
# ═══════════════════════════════════════════════════════════════
# A mythic roll seeds data[uid]["tracking"]; the player makes 2-4 choices to
# locate the creature, then the EXISTING _boss fight begins with a tracking_bonus
# baked into the starting state. Two mistakes and the creature is gone.

TRACK_BONUS_HP_MULT = {"ambush": 0.82, "careful": 1.0, "": 1.0, "shaken": 1.0}

def tracking_active(user_id: str) -> bool:
    tr = data.get(user_id, {}).get("tracking")
    if not tr:
        return False
    if tr.get("expires_ts", 0) <= time.time():
        return False
    return True

def _tracking_scene(key: str) -> dict:
    for s in TRACKING_SCENES:
        if s["key"] == key:
            return s
    return TRACKING_SCENES[0]

def _tracking_start(user_id: str, creature: str, biome: str) -> dict:
    need = random.choice([2, 3, 3, 4])
    tr = {
        "id": secrets.token_hex(4), "creature": creature, "biome": biome,
        "step": 0, "need": need, "progress": 0, "goal": need * 3,
        "mistakes": 0, "perfect": True,
        "scene": random.choice([s["key"] for s in TRACKING_SCENES]),
        "expires_ts": time.time() + TRACKING_EXPIRE_MIN * 60,
    }
    data[user_id]["tracking"] = tr
    st = data[user_id].setdefault("stats", {})
    st["tracks_started"] = st.get("tracks_started", 0) + 1
    mark_user_dirty(user_id)
    return tr

def _tracking_locate(user_id: str, tr: dict) -> dict:
    creature, biome = tr["creature"], tr["biome"]
    perfect = tr["perfect"] and tr["mistakes"] == 0
    enough  = tr["progress"] >= tr["goal"]
    bonus = "ambush" if (perfect and enough) else ("careful" if perfect else
            ("shaken" if tr["mistakes"] >= 1 else ""))
    base_mhp = FIGHT_MONSTER_HP_BASE + BIOME_TOOL_TIER.get(biome, 1) * FIGHT_MONSTER_HP_TIER
    mhp0 = max(1, int(base_mhp * TRACK_BONUS_HP_MULT.get(bonus, 1.0)))
    refresh_health(user_id)   # HP is persistent — a bad track costs a chunk of your CURRENT HP
    if bonus == "shaken":
        h = data[user_id]["health"]
        h["hp"] = max(1, h["hp"] - 12)
    data[user_id]["_boss"] = {
        "creature": creature, "biome": biome,
        "ts": int(time.time()), "eid": secrets.token_hex(4),
        "mhp": mhp0, "mhp_max": base_mhp, "turn": 1,
        "fallen": False, "guard": False, "enrage": False,
        "mdebuff": bonus in ("ambush", "careful"),   # monster off-balance turn 1
        "log": [], "tracking_bonus": bonus,
    }
    data[user_id]["tracking"] = None
    st = data[user_id].setdefault("stats", {})
    st["tracks_completed"] = st.get("tracks_completed", 0) + 1
    mark_user_dirty(user_id)
    analytics(user_id, "myth_tracking_completed", creature=creature,
              biome=biome, bonus=bonus, steps=tr["step"])
    return {"kind": "located", "creature": creature, "bonus": bonus}

def _tracking_lose(user_id: str, tr: dict) -> dict:
    creature = tr["creature"]
    data[user_id]["tracking"] = None
    st = data[user_id].setdefault("stats", {})
    st["tracks_lost"] = st.get("tracks_lost", 0) + 1
    mark_user_dirty(user_id)
    analytics(user_id, "myth_tracking_lost", creature=creature, biome=tr["biome"])
    return {"kind": "lost", "creature": creature}

_TRACK_GAIN_LINES = [
    "You close the gap — the trail is hot.",
    "Fresh sign. You're gaining on it.",
    "The tracks are getting easier to read. Nearly there.",
    "You move quiet and quick. It hasn't noticed you.",
]

def tracking_choice(user_id: str, action: str) -> dict:
    """Resolve one tracking decision. Mutates — call inside a user_transaction.
    Returns {kind: 'ongoing'|'located'|'lost'|'none', line}."""
    tr = data[user_id].get("tracking")
    if not tr or tr.get("expires_ts", 0) <= time.time():
        data[user_id]["tracking"] = None
        return {"kind": "none"}
    spec = TRACKING_ACTIONS.get(action)
    if action == "closein":
        if tr["progress"] >= tr["goal"]:
            return _tracking_locate(user_id, tr)
        return {"kind": "ongoing", "line": "Not close enough yet — keep on the trail."}
    if not spec:
        return {"kind": "none"}

    risk = max(1, spec["risk"] - trophy_effect_value(user_id, "tracking_success_pct"))   # Bigfoot: Matted Fur Tuft
    spooked = random.randint(1, 100) <= risk
    if spooked:
        if trophy_proc(user_id, "tracking_mistake_ignore_pct"):                          # Bogeyman: Jar of Closet Shadow
            line = "A twig cracks under your boot — but it doesn't seem to notice."
        else:
            tr["mistakes"] += 1
            tr["perfect"]   = False
            tr["progress"]  = max(0, tr["progress"] - 1)
            line = "A twig cracks under your boot. It freezes — then bolts. You lose ground."
    else:
        tr["progress"] += spec["progress"]
        line = random.choice(_TRACK_GAIN_LINES)
    tr["step"] += 1
    tr["scene"] = random.choice([s["key"] for s in TRACKING_SCENES if s["key"] != tr["scene"]])
    mark_user_dirty(user_id)

    mistake_cap = 2 + int(trophy_effect_value(user_id, "tracking_extra_mistake"))        # Minotaur: Bronze Nose-Ring
    if tr["mistakes"] >= mistake_cap:
        out = _tracking_lose(user_id, tr); out["line"] = line; return out
    if tr["step"] >= tr["need"] or tr["progress"] >= tr["goal"] + 3:
        out = _tracking_locate(user_id, tr); out["line"] = line; return out
    return {"kind": "ongoing", "line": line}

def _track_bar(cur: int, goal: int, width: int = 12) -> str:
    fill = max(0, min(width, round(width * cur / goal))) if goal else 0
    return "▰" * fill + "▱" * (width - fill)

def build_tracking_components(user_id: str, line: str = "") -> list:
    tr = data[user_id].get("tracking")
    if not tr:
        return build_menu_components(user_id, data[user_id].get("_display_name", "Hunter"))
    creature = tr["creature"]
    ico = creature_emoji(creature)
    scene = _tracking_scene(tr.get("scene", "prints"))
    trid = tr["id"]
    near = tr["progress"] >= tr["goal"]

    gorgon_hint = ""
    if trophy_has_effect(user_id, "tracking_reveal_risk"):                        # Gorgon: Stone-Gaze Lens
        riskiest = max(TRACKING_ACTIONS, key=lambda a: TRACKING_ACTIONS[a]["risk"])
        gorgon_hint = f"\n-# {emoji('trophy')} Stone-Gaze Lens: **{TRACKING_ACTIONS[riskiest]['label']}** looks riskiest right now."

    mistake_cap = 2 + int(trophy_effect_value(user_id, "tracking_extra_mistake"))
    body = (
        f"### {ico} On the Trail — {scene['title']}\n"
        f"-# Tracking something big through {BIOME_NAMES.get(tr['biome'], tr['biome'])}. "
        f"{mistake_cap} mistake{'s' if mistake_cap != 1 else ''} and it's gone.\n\n"
        f"{scene['text']}\n\n"
        + (f"-# {line}\n" if line else "")
        + f"Trail: {_track_bar(tr['progress'], tr['goal'])}  ·  "
          f"Missteps: {'●' * tr['mistakes']}{'○' * (mistake_cap - tr['mistakes'])}"
        + gorgon_hint
    )

    def _tb(act, style=2):
        s = TRACKING_ACTIONS[act]
        return {"type": 2, "style": style, "label": s["label"], "emoji": {"name": s["emoji"]},
                "custom_id": f"hunt:track:{act}:{trid}:{user_id}"}

    rows = [
        {"type": 1, "components": [_tb("follow", 3), _tb("observe", 2), _tb("flank", 2)]},
        {"type": 1, "components": [_tb("push", 4)] + (
            [{"type": 2, "style": 1, "label": "Close In", "emoji": emoji_partial('target'),
              "custom_id": f"hunt:track:closein:{trid}:{user_id}"}] if near else [])},
    ]
    return [{"type": 17, "accent_color": 0x8E44AD, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        *rows,
    ]}]

def build_tracking_outcome_components(user_id: str, outcome: dict) -> list:
    """Shown when a track is LOST (located hands straight to the fight panel)."""
    creature = outcome.get("creature", "it")
    ico = creature_emoji(creature)
    body = (
        f"### {ico} {creature} — Gone\n"
        f"{outcome.get('line', '')}\n"
        "You lost the trail in the undergrowth. No fight, no trophy — but you know "
        "it's out here now.\n"
        "-# Keep hunting this region and you may cross its path again."
    )
    return [{"type": 17, "accent_color": 0xE67E22, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Hunt", "custom_id": f"hunt:again:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"hunt:back:{user_id}"},
        ]},
    ]}]

_TRACK_BONUS_BLURB = {
    "ambush":  f"{emoji('target')} **Ambush** — you got the drop on it. It starts hurt and off-balance.",
    "careful": "`🔭` **Careful approach** — you read its moves. It swings wild on the first exchange.",
    "shaken":  "`😰` **Close call** — you spooked it once and it nearly ran. You're a little rattled.",
    "":        "",
}

# ═══════════════════════════════════════════════════════════════
# SHARE CARDS  ·  turn a rare moment into a channel post (V2, Phase 19-23)
# ═══════════════════════════════════════════════════════════════
# _share_store[sid] = {owner, kind, created_ts, shared, owner_name, ...fields}.
# In-memory + short-lived on purpose (SHARE_STORE_TTL). Only the owner can post,
# and only once. The public card's "Start Hunting" button drops any clicker
# straight into their own first hunt (a new account → onboarding).

_share_store: dict[str, dict] = {}

def _share_gc() -> None:
    now = time.time()
    for k in [k for k, v in _share_store.items()
              if now - v.get("created_ts", 0) > SHARE_STORE_TTL]:
        _share_store.pop(k, None)

def make_share(owner_id: str, kind: str, **fields) -> str:
    if not FEATURE_SHARE_CARDS:
        return ""
    _share_gc()
    sid = secrets.token_hex(5)
    _share_store[sid] = {"owner": str(owner_id), "kind": kind,
                         "created_ts": time.time(), "shared": False, **fields}
    return sid

def _share_row(sid: str, owner_id: str, label: str = "Show Off") -> dict | None:
    if not sid:
        return None
    return {"type": 1, "components": [
        {"type": 2, "style": 1, "label": label, "emoji": emoji_partial("cheering_megaphone"),
         "custom_id": f"share:post:{sid}:{owner_id}"}]}

def _rarity_shareable(rarity: str, personal_first: bool = False) -> bool:
    if not FEATURE_SHARE_CARDS:
        return False
    if rarity in SHARE_RARITY_MIN:
        return True
    return rarity == "rare" and personal_first

def build_share_public_components(sid: str) -> list:
    sh = _share_store.get(sid, {})
    name  = sh.get("owner_name") or "A hunter"
    owner = sh.get("owner", "0")
    kind  = sh.get("kind", "")
    biome_nm = BIOME_NAMES.get(sh.get("biome", ""), sh.get("biome", ""))

    if kind == "myth_kill":
        creature = sh.get("creature", "a mythical creature")
        ico = creature_emoji(creature)
        hp = sh.get("php")
        hp_line = f" with only **{hp} HP** to spare" if isinstance(hp, int) and hp > 0 else ""
        drop_line = f"\n-# {emoji('trophy')} {sh['drop']}" if sh.get("drop") else ""
        body = (f"## {ico} Mythical Hunt\n"
                f"**{name}** tracked down and killed **{creature}**{hp_line}.\n"
                f"-# {emoji('location_pin')} {biome_nm}{drop_line}\n\n"
                "Think you can find one?")
        color = 0x9B59B6
    elif kind == "rare_catch":
        animal = sh.get("animal", "a rare animal")
        a_em = animal_emoji(animal)
        body = (f"## {a_em} {sh.get('rarity','Rare').title()} Catch\n"
                f"**{name}** just bagged a **{animal}** in {biome_nm}"
                f"{' — a personal first' if sh.get('personal_first') else ''}.\n\n"
                "Your move, hunter.")
        color = 0xF1C40F
    elif kind == "prestige":
        body = (f"## {emoji('prestige')} Prestige {sh.get('prestige', '')}\n"
                f"**{name}** just reset everything for permanent power. Again.\n\n"
                "Start your own climb.")
        color = 0xE67E22
    elif kind == "expedition":
        body = (f"## {emoji('tribe')} Expedition Complete\n"
                f"**{name}**'s tribe cleared **{sh.get('expedition','an expedition')}**.\n\n"
                "Build a tribe. Run your own.")
        color = 0x1ABC9C
    else:
        body = f"**{name}** is out hunting in {biome_nm}."
        color = 0x2ECC71

    return [{"type": 17, "accent_color": color, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Start Hunting", "emoji": emoji_partial('bow'), "custom_id": f"hunt:again:{owner}"},
            {"type": 2, "style": 5, "label": "Add Idle Hunter", "url": invite_url()},
        ]},
    ]}]

# ═══════════════════════════════════════════════════════════════
# REFERRALS  ·  bring a friend, both earn once they actually play
# ═══════════════════════════════════════════════════════════════

_REFERRAL_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def _mint_referral_code() -> str:
    return "HUNT-" + "".join(random.choice(_REFERRAL_ALPHABET) for _ in range(5))

def _grant_title(user_id: str, title: str) -> bool:
    et = data[user_id].setdefault("earned_titles", [])
    if title and title not in et:
        et.append(title)
        mark_user_dirty(user_id)
        return True
    return False

async def _referral_get_code(user_id: str) -> str:
    try:
        return await backend.referral_code_get_or_make(str(user_id), _mint_referral_code)
    except Exception:
        return ""

async def _referral_bind(user_id: str, raw_code: str) -> tuple[bool, str]:
    """Try to bind `user_id` to the referrer behind `raw_code`. Returns (ok, message)."""
    if not FEATURE_REFERRALS:
        return False, "Referrals aren't active right now."
    code = (raw_code or "").strip().upper()
    if not code:
        return False, "Enter a referral code like `HUNT-AB12C`."
    init_user(user_id)
    if data[user_id].get("level", 1) > REFERRAL_CODE_MAX_LEVEL:
        return False, (f"Referral codes can only be entered before Level "
                       f"{REFERRAL_CODE_MAX_LEVEL + 1}. You're past that — but you can "
                       f"still invite friends with your own code!")
    existing = await backend.referral_of(str(user_id))
    if existing:
        return False, "You already entered a referral code — one per hunter, forever."
    owner = await backend.referral_code_owner(code)
    if not owner:
        return False, "That code doesn't match anyone. Check the spelling?"
    if str(owner) == str(user_id):
        return False, "You can't refer yourself, obviously."
    od = data.get(str(owner), {})
    if od.get("is_tester") or od.get("ban", {}).get("active"):
        return False, "That code can't be used."
    if not await backend.referral_record(str(user_id), str(owner), code):
        return False, "Couldn't record that — you may already have a referrer."
    data[user_id]["referral_pending"] = ""
    data[user_id].pop("_ref_done", None)
    mark_user_dirty(user_id)
    analytics(user_id, "referral_entered", referrer=str(owner))
    return True, (f"You're in **{od.get('username') or 'another hunter'}**'s crew. "
                  f"Reach **Level {REFERRAL_QUALIFY_LEVEL}**, **{REFERRAL_QUALIFY_HUNTS} hunts** "
                  f"and play on **{REFERRAL_QUALIFY_DAYS} different days** — then you both earn a reward.")

def _referral_qualifies(d: dict) -> bool:
    """The play bar a referred account must clear: level + hunts + 2 distinct
    active UTC days (a light anti-alt gate on top of level/hunts)."""
    st = d.get("stats", {})
    return (d.get("level", 1) >= REFERRAL_QUALIFY_LEVEL
            and st.get("lifetime_hunts", 0) >= REFERRAL_QUALIFY_HUNTS
            and st.get("active_days", 0) >= REFERRAL_QUALIFY_DAYS)

async def _referral_check_qualified(user_id: str) -> None:
    """Fire once a referred player has genuinely started playing. Rewards both
    sides and applies the referrer's milestone. Safe to call from anywhere and
    from concurrent callers — the payout is gated by an atomic DB flip."""
    if not FEATURE_REFERRALS:
        return
    uid = str(user_id)
    d = data.get(uid)
    if not d or d.get("_ref_done"):
        return
    # Cheap gate: no DB round-trip until they could plausibly qualify.
    if not _referral_qualifies(d):
        return
    try:
        rec = await backend.referral_of(uid)
    except Exception:
        return
    if not rec or rec.get("reward_claimed"):
        d["_ref_done"] = True
        return
    # Atomic: exactly one caller wins the 0→1 flip and pays both sides.
    won = await backend.claim_referral_reward_once(uid)
    d["_ref_done"] = True
    if not won:
        return
    referrer = str(rec["referrer_id"])
    analytics(uid, "referral_qualified", referrer=referrer)

    async with user_transaction(uid):
        add_gems(uid, REFERRAL_QUALIFY_GEMS, "referral")
        _grant_title(uid, "Brought In")
    try:
        await _dm_user(uid, f"## {emoji('handshake')} Referral reward!\nYou hit Level {REFERRAL_QUALIFY_LEVEL} "
                            f"— you and the hunter who invited you each earned "
                            f"**{emoji('gem')} {REFERRAL_QUALIFY_GEMS}** and a title.")
    except Exception:
        pass

    init_user(referrer)
    stats = await backend.referral_stats(referrer)
    n_qual = stats.get("qualified", 0)
    ms = REFERRAL_MILESTONES.get(n_qual)
    async with user_transaction(referrer):
        add_gems(referrer, REFERRAL_QUALIFY_GEMS, "referral")
        got = []
        if ms:
            if ms.get("title") and _grant_title(referrer, ms["title"]):
                got.append(f'title "{ms["title"]}"')
            if ms.get("badge") and _grant_special_badge(referrer, ms["badge"]):
                got.append(f'the {SPECIAL_BADGES.get(ms["badge"], {}).get("label", ms["badge"])} badge')
            if ms.get("gems"):
                add_gems(referrer, ms["gems"], "referral milestone")
                got.append(f"{ms['gems']} gems")
    analytics(referrer, "referral_reward", qualified_total=n_qual)
    try:
        extra = (" You also unlocked " + " + ".join(got) + "!") if got else ""
        await _dm_user(referrer,
            f"## {emoji('handshake')} One of your hunters made it!\n"
            f"A hunter you referred just reached Level {REFERRAL_QUALIFY_LEVEL}. "
            f"You earned **{emoji('gem')} {REFERRAL_QUALIFY_GEMS}**.{extra}\n"
            f"-# Qualified referrals: **{n_qual}**")
    except Exception:
        pass

def build_refer_components(user_id: str, code: str,
                           stats: dict | None = None, note: str = "") -> list:
    st = stats or {"invited": 0, "qualified": 0}
    ladder = "\n".join(
        f"-# {emoji('check_mark') if st['qualified'] >= n else '▫️'} **{n}** qualified — "
        + " · ".join(filter(None, [
            (f'title "{m["title"]}"' if m.get("title") else ""),
            (f'{m["badge"]} badge' if m.get("badge") else ""),
            (f'{m["gems"]} gems' if m.get("gems") else ""),
        ]))
        for n, m in sorted(REFERRAL_MILESTONES.items())
    )
    body = (
        f"## {emoji('handshake')} Invite a Hunter\n"
        f"Your referral code:\n# `{code or '—'}`\n\n"
        "A friend enters it with `/refer code:<code>` in their first few levels. "
        f"When they reach **Level {REFERRAL_QUALIFY_LEVEL}**, **{REFERRAL_QUALIFY_HUNTS} hunts** "
        f"and have played **{REFERRAL_QUALIFY_DAYS} different days**, you **both** get gems and a cosmetic.\n\n"
        f"-# Invited: **{st['invited']}** · Qualified: **{st['qualified']}**\n\n"
        + ladder
    )
    if note:
        body = f"-# {note}\n\n" + body
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 5, "label": "Invite Idle Hunter", "url": invite_url()},
            {"type": 2, "style": 2, "label": "◀ Menu", "custom_id": f"nav:menu:{user_id}"},
        ]},
    ]}]

# ═══════════════════════════════════════════════════════════════
# ANIMAL COMBAT — short fights against dangerous ordinary wildlife (V2.1)
# ═══════════════════════════════════════════════════════════════
# One multi-catch hunt can surface AT MOST one interactive encounter (see
# run_hunt's danger-pick logic below); everything else resolves instantly as
# always. Reuses the SAME ambush/normal/shaken vocabulary as myth tracking
# (Sprint 4) rather than inventing new terms, but as a single roll — a full
# multi-step tracking dialogue doesn't fit a hunt that can fire every 3s.
# data[uid]["fight"] = {kind:"animal", animal, biome, eid, mhp, mhp_max, turn,
#                        guard, log, bonus}. Player HP lives in
# data[uid]["health"] — the same pool the mythic fight below now also uses.

def animal_fight_active(user_id: str) -> bool:
    f = data.get(user_id, {}).get("fight")
    return bool(f and f.get("kind") == "animal")

def _animal_encounter_roll(user_id: str, stats: dict) -> str:
    """One-shot ambush determination for a normal danger encounter. Returns
    'ambush' (you got the drop), 'normal', or 'shaken' (it got you first)."""
    luck = max(0, get_total_boosts(user_id).get("luck", 0))
    tier = get_tool_tier(data[user_id].get("tool", "Bare Hands"))
    skill = luck / 4 + tier * 3
    atk = stats["attack_chance"]
    p_ambush = min(0.55, 0.15 + skill / 300)
    p_shaken = max(0.05, atk - skill / 400)
    p_shaken = max(0.0, min(p_shaken, 1 - p_ambush - 0.05))
    r = random.random()
    if r < p_ambush:
        return "ambush"
    if r > 1 - p_shaken:
        return "shaken"
    return "normal"

_ANIMAL_BONUS_BLURB = {
    "ambush": f"{emoji('target')} **Ambush** — you got the drop on it. It starts hurt.",
    "shaken": f"{emoji('warning')} **Ambushed!** — it got the jump on you first.",
    "normal": "",
}

def start_animal_encounter(user_id: str, animal: str, biome: str) -> dict:
    """Resolve a dangerous-animal pick into either a fled-away beat or a fight.
    Mutates data[uid]; call inside the same transaction as run_hunt."""
    stats = animal_combat_stats(animal)
    if stats["flee_chance"] > 0 and random.random() < stats["flee_chance"]:
        analytics(user_id, "animal_fled", animal=animal, biome=biome)
        return {"kind": "fled", "animal": animal}
    refresh_health(user_id)
    h = data[user_id]["health"]
    bonus = _animal_encounter_roll(user_id, stats)
    mhp = max(1, int(stats["hp"] * 0.75)) if bonus == "ambush" else stats["hp"]
    pre_dmg = 0
    if bonus == "shaken" and stats["damage"][1] > 0:
        pre_dmg = random.randint(*stats["damage"])
        h["hp"] = max(1, h["hp"] - pre_dmg)
    data[user_id]["fight"] = {
        "kind": "animal", "animal": animal, "biome": biome, "eid": secrets.token_hex(4),
        "mhp": mhp, "mhp_max": stats["hp"], "turn": 1, "guard": False,
        "log": [], "bonus": bonus,
    }
    st = data[user_id].setdefault("stats", {})
    st["animal_fights_started"] = st.get("animal_fights_started", 0) + 1
    analytics(user_id, "animal_encounter", animal=animal, biome=biome, bonus=bonus)
    return {"kind": "fight", "animal": animal, "bonus": bonus, "pre_dmg": pre_dmg}

def _animal_fight_win(user_id: str, name: str, biome: str, *, bonus_mult: float = 1.0) -> dict:
    data[user_id]["fight"] = None
    animal_value = ANIMAL_DATA.get(name, {}).get("value", 0)
    animal_xp    = ANIMAL_DATA.get(name, {}).get("xp", 0)
    boosts = get_total_boosts(user_id)
    hp, mx = player_hp(user_id)
    # 10× the normal payout for winning the fight, +10% more if you finish
    # healthy (>75% HP) — this replaces animals' instant-catch payout entirely,
    # it doesn't stack with it.
    healthy_bonus = ANIMAL_ENCOUNTER_HEALTHY_BONUS if (mx and hp / mx > 0.75) else 0.0
    mult    = ANIMAL_ENCOUNTER_REWARD_MULT * (1 + healthy_bonus) * bonus_mult
    xp_mult = ANIMAL_ENCOUNTER_XP_MULT * (1 + healthy_bonus) * bonus_mult
    sell_value = int(animal_value * (1 + boosts.get("sell", 0) / 100) * mult * ev_sell_mult())
    xp_earned  = int(animal_xp * (1 + boosts.get("xp", 0) / 100) * xp_mult * ev_xp_mult())
    d = data[user_id]
    d.setdefault("inv", []).append(name)
    d["_pending_sell"] = (d.get("_pending_sell") or 0) + sell_value
    d["xp"] = d.get("xp", 0) + xp_earned
    d["total_money_earned"] = d.get("total_money_earned", 0) + sell_value
    record_catch(user_id, name, d.get("tool", "Bare Hands"), sell_value)
    level_ups = 0
    while d["xp"] >= xp_for_level(d["level"]):
        d["xp"] -= xp_for_level(d["level"]); d["level"] += 1; level_ups += 1
    st = d.setdefault("stats", {})
    st["animal_fights_won"] = st.get("animal_fights_won", 0) + 1
    mark_user_dirty(user_id)
    analytics(user_id, "animal_fight_won", animal=name, biome=biome)
    return {"kind": "win", "animal": name, "sell_value": sell_value, "xp": xp_earned,
            "level_ups": level_ups, "level": d["level"], "hp": hp, "max_hp": mx}

def _animal_fight_ko(user_id: str, name: str, biome: str) -> dict:
    data[user_id]["fight"] = None
    rec = apply_ko_recovery(user_id)
    st = data[user_id].setdefault("stats", {})
    st["animal_fights_lost"] = st.get("animal_fights_lost", 0) + 1
    analytics(user_id, "animal_fight_ko", animal=name, biome=biome, rookie_save=rec["rookie_save"])
    return {"kind": "ko", "animal": name, "rookie_save": rec["rookie_save"], "hp": rec["hp"]}

def animal_fight_turn(user_id: str, action: str) -> dict:
    """Resolve one round. Mutates — call inside a user_transaction.
    Returns {kind: 'ongoing'|'win'|'ko'|'escape'|'none'}."""
    f = data[user_id].get("fight")
    if not f or f.get("kind") != "animal":
        return {"kind": "none"}
    name  = f["animal"]
    biome = f.get("biome", data[user_id].get("biome", "village"))
    stats = animal_combat_stats(name)
    h     = data[user_id]["health"]
    tool  = data[user_id].get("tool", "Bare Hands")
    dmin, dmax = tool_combat_damage(tool)
    acc   = tool_combat_accuracy(tool)
    log: list[str] = []
    R = random.randint

    if action == "flee":
        # Leaving is always a clean getaway — you lose only this encounter's
        # animal, keep the rest of the hunt, and take no hit for it.
        data[user_id]["fight"] = None
        st = data[user_id].setdefault("stats", {})
        st["animal_fights_fled"] = st.get("animal_fights_fled", 0) + 1
        return {"kind": "escape", "animal": name}

    dealt = 0
    if action == "attack":
        if random.random() < min(0.97, acc):
            dealt = R(dmin, dmax)
            log.append(f"{emoji('target')} You hit the {name} for **{dealt}**.")
        else:
            log.append(f"{emoji('target')} Your shot goes wide.")
    elif action == "power":
        if random.random() < POWER_ATTACK_ACCURACY:
            dealt = int(R(dmin, dmax) * POWER_ATTACK_DAMAGE_MULT)
            log.append(f"{emoji('impact')} Power attack connects for **{dealt}**!")
        else:
            log.append(f"{emoji('impact')} You overcommit and miss completely.")
    elif action == "defend":
        f["guard"] = True
        log.append(f"{emoji('shield')} You brace for its counterattack.")
    elif action == "heal":
        item = next((n for n in HEALING_ITEMS
                    if data[user_id].get("healing_inv", {}).get(n, 0) > 0), None)
        if not item:
            log.append(f"{emoji('adhesive_bandage')} You don't have anything to heal with.")
        else:
            inv = data[user_id]["healing_inv"]
            inv[item] -= 1
            if inv[item] <= 0:
                del inv[item]
            before = h["hp"]
            h["hp"] = min(effective_max_hp(user_id), h["hp"] + HEALING_ITEMS[item]["heal"])
            log.append(f"{emoji('adhesive_bandage')} You use a **{item}** (+{h['hp']-before} HP).")
    else:
        return {"kind": "none"}

    if dealt:
        f["mhp"] = max(0, f["mhp"] - dealt)
    if f["mhp"] <= 0:
        f["log"] = (f.get("log", []) + log)[-4:]
        return _animal_fight_win(user_id, name, biome)

    # ── the animal's turn ──
    guarded = f.pop("guard", False)
    if stats["damage"][1] > 0 and random.random() < stats["attack_chance"]:
        base = R(*stats["damage"])
        mdmg = max(1, int(base * 0.4)) if guarded else base
        if guarded:
            log.append(f"{emoji('shield')} It lunges — your guard soaks most of it (**{mdmg}**).")
        else:
            log.append(f"{emoji('warning')} The {name} strikes back for **{mdmg}**.")
        h["hp"] = max(0, h["hp"] - mdmg)
    else:
        log.append(f"The {name} hesitates.")

    f["turn"] = f.get("turn", 1) + 1
    f["log"] = (f.get("log", []) + log)[-4:]
    if h["hp"] <= 0:
        return _animal_fight_ko(user_id, name, biome)
    mark_user_dirty(user_id)
    return {"kind": "ongoing"}

def build_animal_fight_components(user_id: str, intro: bool = False,
                                  extra_catches: list | None = None) -> list:
    f = data[user_id].get("fight")
    if not f or f.get("kind") != "animal":
        return build_menu_components(user_id, data[user_id].get("_display_name", "Hunter"))
    name = f["animal"]
    ico = animal_emoji(name)
    mhp, mmax = f.get("mhp", 1), f.get("mhp_max", 1)
    hp, mx = player_hp(user_id)
    hp_ico = emoji("hp") or "❤️"

    extra_line = ""
    if intro and extra_catches:
        kept = [c["animal"] for c in extra_catches]
        if kept:
            extra_line = "-# Also caught: " + ", ".join(f"**{a}**" for a in kept) + "\n\n"

    if intro or not f.get("log"):
        bonus_line = _ANIMAL_BONUS_BLURB.get(f.get("bonus", ""), "")
        log_txt = f"-# A **{ico} {name}** turns to face you!" + (f"\n-# {bonus_line}" if bonus_line else "")
    else:
        log_txt = "\n".join(f"-# {ln}" for ln in f.get("log", []))

    # Combat is deliberately styled apart from every browsing screen — no
    # shop/inventory/menu chrome, just the two combatants and the log.
    body = (
        f"## {emoji('warning')} WILD {name.upper()}\n"
        f"{extra_line}"
        f"{ico} **{name.upper()}**\n{mhp}/{mmax}\n{_hp_bar(mhp, mmax)}\n\n"
        f"{hp_ico} **YOU**\n{hp}/{mx}\n{_hp_bar(hp, mx)}\n\n"
        f"{log_txt}"
    )
    heal_avail = any(n > 0 for n in data[user_id].get("healing_inv", {}).values())
    eid = f["eid"]
    def _abtn(action, label, style, emj, disabled=False):
        return {"type": 2, "style": style, "label": label, "emoji": emoji_partial(emj),
                "disabled": disabled, "custom_id": f"hunt:afight:{action}:{eid}:{user_id}"}
    return [{"type": 17, "accent_color": 0xE67E22, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [_abtn("attack", "Attack", 3, "bow"),
                                    _abtn("power", "Power Attack", 1, "impact")]},
        {"type": 1, "components": [_abtn("defend", "Defend", 2, "shield"),
                                    _abtn("heal", "Heal", 2, "adhesive_bandage", disabled=not heal_avail),
                                    _abtn("flee", "Flee", 4, "🏃")]},
    ]}]

def build_animal_fight_outcome_components(user_id: str, outcome: dict) -> list:
    name = outcome.get("animal", "the animal")
    ico = animal_emoji(name)
    kind = outcome["kind"]
    if kind == "win":
        lvl = ""
        if outcome.get("level_ups") == 1:
            lvl = f"\n-# {USER_EMOJIS['level_up']} Level up! Now level **{outcome['level']}**"
        elif outcome.get("level_ups", 0) > 1:
            lvl = f"\n-# {USER_EMOJIS['level_up']} Level up ×{outcome['level_ups']}! Now level **{outcome['level']}**"
        body = (
            f"### {ico} {name} — Caught!\n"
            f"A hard-won catch.\n"
            f"-# **+ ◈ {outcome['sell_value']:,}** · **+ {outcome['xp']:,} XP**\n"
            f"-# {emoji('hp') or '❤️'} HP: **{outcome['hp']}/{outcome.get('max_hp', PLAYER_BASE_HP)}**{lvl}"
        )
        color = 0x2ECC71
    elif kind == "ko":
        rescue = (f"\n-# {emoji('shield')} **Rookie Protection** kicked in — your first knockout is always a soft landing."
                  if outcome.get("rookie_save") else "")
        body = (
            f"### `💀` Knocked Out\n"
            f"The **{name}** got the better of you. A ranger finds you and drags you back to camp.\n"
            f"-# {emoji('hp') or '❤️'} Recovered to **{outcome['hp']}/{PLAYER_BASE_HP}** HP.{rescue}\n"
            f"-# Nothing lost — no cash, no items, no XP."
        )
        color = 0xE74C3C
    else:  # escape
        body = (f"### `💨` {name} — you got away.\n"
                "-# No catch this time — but you live to hunt again.")
        color = 0xE67E22
    return [{"type": 17, "accent_color": color, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Hunt",     "custom_id": f"hunt:again:{user_id}"},
            {"type": 2, "style": 1, "label": "Sell All", "custom_id": f"hunt:sell_all:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",   "custom_id": f"hunt:back:{user_id}"},
        ]},
    ]}]

# ═══════════════════════════════════════════════════════════════
# ROOKIE GOALS + FIRST-DAY CHEST  (V2.1, Plan B)
# ═══════════════════════════════════════════════════════════════
# Five cheap, natural checkpoints. catch_5 / reach_level_5 / discover_5 are
# threshold-scanned from stats already tracked elsewhere; buy_tool and
# view_world are flipped directly at their own trigger points. buy_tool used
# to be "win a dangerous encounter", but that's RNG-gated (Epic/Legendary-only,
# 3%/12% chance) — a rookie could sit on 4/5 goals for a long time waiting on
# luck. Buying a tool is guaranteed to happen in the first few minutes.

_ROOKIE_CHEST_TITLE = "Rookie Hunter"
_ROOKIE_CHEST_CRATE = "Rare Crate"
_ROOKIE_CHEST_GEMS  = 50

def _ensure_rookie_goals(d: dict) -> dict:
    """Get-or-init d['rookie_goals'], self-healing its key set against the
    current ROOKIE_GOALS — so renaming/adding a goal (e.g. win_combat ->
    buy_tool) doesn't strand players whose dict was saved under the old shape.
    A renamed key carries its old value forward rather than resetting it."""
    rg = d.setdefault("rookie_goals", {})
    if "buy_tool" not in rg and "win_combat" in rg:
        rg["buy_tool"] = rg.pop("win_combat")
    for k in ROOKIE_GOALS:
        rg.setdefault(k, False)
    return rg

def _rookie_goal_scan(user_id: str) -> list[str]:
    """Check the threshold-based goals, flip any newly met, grant the chest
    once all five are done. Returns newly-completed keys."""
    d = data.get(user_id)
    if not d:
        return []
    rg = _ensure_rookie_goals(d)
    newly = []
    def _set(k, cond):
        if not rg.get(k) and cond:
            rg[k] = True
            newly.append(k)
    _set("catch_5", d.get("total_caught", 0) >= 5)
    _set("reach_level_5", d.get("level", 1) >= 5)
    _set("discover_5", len(d.get("record", {})) >= 5)
    if newly:
        mark_user_dirty(user_id)
        analytics(user_id, "rookie_goal_progress", goals=newly)
    if all(rg.values()) and not d.get("rookie_chest_claimed"):
        _grant_rookie_chest(user_id)
    return newly

def _rookie_goal_progress(user_id: str, key: str) -> None:
    """Directly flip a non-threshold rookie goal (buy_tool, view_world)."""
    d = data.get(user_id)
    if not d:
        return
    rg = _ensure_rookie_goals(d)
    if key in rg and not rg[key]:
        rg[key] = True
        mark_user_dirty(user_id)
        analytics(user_id, "rookie_goal_progress", goals=[key])
    _rookie_goal_scan(user_id)

def _grant_rookie_chest(user_id: str) -> None:
    d = data[user_id]
    if d.get("rookie_chest_claimed"):
        return
    d["rookie_chest_claimed"] = True
    ci = d.setdefault("crate_inv", {})
    ci[_ROOKIE_CHEST_CRATE] = ci.get(_ROOKIE_CHEST_CRATE, 0) + 1
    add_gems(user_id, _ROOKIE_CHEST_GEMS, "rookie chest")
    _grant_title(user_id, _ROOKIE_CHEST_TITLE)
    mark_user_dirty(user_id)
    analytics(user_id, "rookie_chest_claimed")

def rookie_goals_block(user_id: str) -> str:
    """A short progress block for the onboarding 'done' panel and /menu."""
    d = data.get(user_id, {})
    rg = _ensure_rookie_goals(d) if d else {}
    done = sum(1 for v in rg.values() if v)
    total = len(ROOKIE_GOALS)
    lines = [f"{emoji('check_mark') if rg.get(k) else '▫️'} {spec['emoji']} {spec['label']}"
             for k, spec in ROOKIE_GOALS.items()]
    chest = f" {emoji('gift')} Claimed!" if d.get("rookie_chest_claimed") else ""
    return (f"**Rookie Goals — {done}/{total}**{chest}\n" + "\n".join(f"-# {ln}" for ln in lines))

def three_goals_lines(user_id: str) -> list[str]:
    """Always-on 3-tier goal ladder — immediate (next tool), medium (next
    region), long-term (a species-discovery milestone) — so a player is never
    left wondering what to do after a hunt. Shown permanently on /menu."""
    d = data[user_id]
    lines = []

    owned = set(d.get("owned_tools", []))
    next_tool = next((n for n, t in get_all_tools_sorted()
                       if n not in owned and t.get("price", 0) > 0), None)
    if next_tool:
        t = TOOLS[next_tool]
        cur_sym = "◈" if t["currency"] == "money" else emoji("gem")
        lines.append(f"{emoji('target')} **Now:** Buy **{next_tool}** ({cur_sym} {t['price']:,})")

    next_biome = next(((k, lvl) for k, lvl in BIOME_LEVELS if lvl > d.get("level", 1)), None)
    if next_biome:
        bk, lvl = next_biome
        lines.append(f"{emoji('world_map')} **Soon:** Reach Level **{lvl}** to unlock **{BIOME_NAMES.get(bk, bk)}**")

    discovered = len(d.get("record", {}))
    total_species = len(ANIMAL_DATA)
    if discovered < total_species:
        target = min(total_species, ((discovered // 10) + 1) * 10)
        lines.append(f"{emoji('book')} **Long-term:** Discover **{target}** species ({discovered}/{target})")

    return lines

# ─────────────────────────────────────────────
# HUNTER'S PATH  ·  first-hour progression spine (2026-09-15)
# ─────────────────────────────────────────────
# Onboarding V2 teaches /hunt/sell/trial-tool. This is everything after —
# the main progression spine for the first hour, one step per system in the
# game, so a player is never left with only /hunt and no reason to open
# anything else. Every step is a LIVE check against state the game already
# tracks (never a separately-stored progress counter), so it can never
# desync from what actually happened. Every step also pays out something
# real the moment it completes — see HUNTERS_PATH_STEPS[i]["reward"].

def _hunters_path_done_flags(user_id: str) -> list[bool]:
    d = data.get(user_id, {})
    rg = d.get("rookie_goals", {})
    stats = d.get("stats", {})
    tools_used = set(stats.get("tools_used", []))
    record = d.get("record", {})
    village_animals = set(BIOME_ANIMALS.get("village", []))
    return [
        bool(rg.get("buy_tool")),                                    # buy_tool
        bool(tools_used - {"Bare Hands"}),                            # hunt_with_tool
        bool(d.get("last_daily_date")),                               # claim_daily
        bool(stats.get("first_quest_claim_ts")),                      # complete_quest
        len(record) >= 5,                                             # discover_5
        stats.get("crates_opened", 0) >= 1,                           # open_crate
        len(d.get("guide_seen", [])) >= 2,                            # travel
        any(a not in village_animals for a in record),               # catch_new_region
        d.get("idle", {}).get("stacks", 0) > 0,                       # start_camp
        stats.get("idle_collects", 0) >= 1,                           # check_camp
        bool(stats.get("first_rare_ts")),                             # first_rare
        stats.get("myth_encounters", 0) >= 1,                         # myth_lead
    ]

def hunters_path_active(user_id: str) -> bool:
    if not FEATURE_HUNTERS_PATH:
        return False
    hp = data.get(user_id, {}).get("hunters_path") or {}
    return not hp.get("completed", True)

def hunters_path_current_step(user_id: str) -> int:
    """Index of the first unfinished step, or len(HUNTERS_PATH_STEPS) if all done."""
    for i, ok in enumerate(_hunters_path_done_flags(user_id)):
        if not ok:
            return i
    return len(HUNTERS_PATH_STEPS)

def hunters_path_myths_allowed(user_id: str) -> bool:
    """Mythics are suppressed through the early stretch of the Path (see
    run_hunt) so they can't steal a moment from whichever step the player is
    mid-chasing, but stay off forever once the Path reaches its own
    'myth_lead' step — which needs one to actually fire."""
    if not hunters_path_active(user_id):
        return True
    return hunters_path_current_step(user_id) >= HUNTERS_PATH_MYTH_UNLOCK_STEP

def _grant_hunters_path_reward(user_id: str, step: dict) -> str:
    """Pay out one step's reward, return a short display line for the toast."""
    r = step.get("reward") or {}
    parts = []
    if "money" in r:
        add_money(user_id, r["money"], f"hunters_path:{step['key']}")
        parts.append(f"◈ {r['money']:,}")
    if "gems" in r:
        add_gems(user_id, r["gems"], f"hunters_path:{step['key']}")
        parts.append(f"{emoji('gem')} {r['gems']}")
    if "crate" in r:
        ci = data[user_id].setdefault("crate_inv", {})
        ci[r["crate"]] = ci.get(r["crate"], 0) + 1
        parts.append(f"{CRATE_TIERS.get(r['crate'], {}).get('emoji', emoji('package'))} {r['crate']}")
    return " · ".join(parts)

def hunters_path_maybe_complete(user_id: str) -> dict:
    """Call after anything that could finish a step. Grants each step's own
    reward exactly once as it completes, plus the checklist-wide bonus once
    every step is done. Returns {'newly_done': [(step, reward_line), ...],
    'all_done': bool} so callers can toast whatever just happened."""
    if not hunters_path_active(user_id):
        return {"newly_done": [], "all_done": False}
    hp = data[user_id]["hunters_path"]
    rewarded = hp.setdefault("rewarded", [])
    done = _hunters_path_done_flags(user_id)
    newly = []
    for i, ok in enumerate(done):
        step = HUNTERS_PATH_STEPS[i]
        if ok and step["key"] not in rewarded:
            rewarded.append(step["key"])
            line = _grant_hunters_path_reward(user_id, step)
            newly.append((step, line))
    all_done = all(done)
    just_finished = False
    if all_done and not hp.get("completed"):
        hp["completed"] = True
        add_gems(user_id, HUNTERS_PATH_REWARD_GEMS, "hunter's path complete")
        _grant_title(user_id, HUNTERS_PATH_REWARD_TITLE)
        analytics(user_id, "hunters_path_completed")
        just_finished = True
    if newly or just_finished:
        mark_user_dirty(user_id)
    return {"newly_done": newly, "all_done": just_finished}

def hunters_path_line(user_id: str) -> str:
    """Compact one-line summary for /menu's 'now' block."""
    if not hunters_path_active(user_id):
        return ""
    i = hunters_path_current_step(user_id)
    if i >= len(HUNTERS_PATH_STEPS):
        return ""
    step = HUNTERS_PATH_STEPS[i]
    return f"{emoji('world_map')} **Hunter's Path** {i}/{len(HUNTERS_PATH_STEPS)} — {step['emoji']} {step['label']}"

def hunters_path_next_hint(user_id: str) -> str:
    """A short 'what to do next' line for panels that just finished a step —
    the command-teaching chain from the design brief (finish a sale, get told
    to open /shop; finish that, get told to open /quests; etc). Empty once
    the whole path is done."""
    if not hunters_path_active(user_id):
        return ""
    i = hunters_path_current_step(user_id)
    if i >= len(HUNTERS_PATH_STEPS):
        return ""
    step = HUNTERS_PATH_STEPS[i]
    return f"`➡️` **Next:** {step['hint']}"

async def _hunters_path_notify(interaction: discord.Interaction, user_id: str, result: dict) -> None:
    """Send the appropriate ephemeral toast after a Hunter's Path-relevant
    action: the completion celebration if this action finished the whole
    checklist, otherwise the reward(s) for whatever step(s) just completed
    plus a 'Next:' hint (nothing at all if nothing changed)."""
    if not result:
        return
    if result.get("all_done"):
        await send_ephemeral_v2(interaction,
            f"{emoji('party_popper')} **Hunter's Path complete!** +{HUNTERS_PATH_REWARD_GEMS} gems and the "
            f"**{HUNTERS_PATH_REWARD_TITLE}** title — you've got the run of the place now.",
            0x2ECC71)
        return
    newly = result.get("newly_done") or []
    if not newly:
        return
    lines = [f"{emoji('check_mark')} **{step['label']}** — {line}" if line else f"{emoji('check_mark')} **{step['label']}**"
             for step, line in newly]
    hint = hunters_path_next_hint(user_id)
    if hint:
        lines.append(hint)
    await send_ephemeral_v2(interaction, "\n".join(lines), 0x3498DB)

def build_hunters_path_components(user_id: str) -> list:
    """The full checklist panel. One button jumps to whatever system the
    current step needs; every other step is listed but not buttoned — with
    12 steps there's no room for one button each, and only the step you can
    actually act on needs one."""
    done = _hunters_path_done_flags(user_id)
    cur  = hunters_path_current_step(user_id)
    total = len(HUNTERS_PATH_STEPS)

    lines = [f"### {emoji('world_map')} Hunter's Path — {sum(done)}/{total}"]
    if cur >= total:
        lines.append("-# All done — you've got the run of the place now.")
    else:
        lines.append("-# Finish these in order — each one pays out immediately, "
                      f"and the whole path is worth {emoji('diamond_small')} **{HUNTERS_PATH_REWARD_GEMS} gems** "
                      f"and the **{HUNTERS_PATH_REWARD_TITLE}** title.")
    for i, step in enumerate(HUNTERS_PATH_STEPS):
        if done[i]:
            mark = f"{emoji('check_mark')}"
        elif i == cur:
            mark = "▶️"
        else:
            mark = emoji('lock')
        r = step.get("reward") or {}
        r_bits = []
        if "money" in r: r_bits.append(f"◈{r['money']:,}")
        if "gems" in r: r_bits.append(f"{emoji('gem')}{r['gems']}")
        if "crate" in r: r_bits.append(r["crate"])
        r_line = " · ".join(r_bits)
        lines.append(f"-# {mark} {step['emoji']} {step['label']} — *{r_line}*" +
                     (f"\n-#   {step['hint']}" if i == cur else ""))

    rows = []
    if cur < total:
        step = HUNTERS_PATH_STEPS[cur]
        rows.append({"type": 1, "components": [
            {"type": 2, "style": 1, "label": f"Go: {step['label']}",
             "emoji": {"name": step["emoji"]},
             "custom_id": f"nav:{step['panel']}:{user_id}"},
        ]})
    rows.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Menu", "custom_id": f"nav:menu:{user_id}"},
    ]})

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": "\n".join(lines)},
        {"type": 14, "divider": True, "spacing": 2},
        *rows,
    ]}]

# ═══════════════════════════════════════════════════════════════
# MYTHIC BOSS FIGHT — turn-based brawl (player HP vs monster HP)
# ═══════════════════════════════════════════════════════════════
# `_boss` gains combat fields on first render/turn:
#   php, mhp, mhp_max, turn, fallen, guard, enrage, mdebuff, log[]

FIGHT_ACTIONS = {
    "punch":  {"label": "Punch",  "uni": "👊", "key": "fight_punch"},
    "kick":   {"label": "Kick",   "uni": "🦵", "key": "fight_kick"},
    "defend": {"label": "Defend", "uni": "🛡️", "key": "fight_defend"},
    "shoot":  {"label": "Shoot",  "uni": "🔫", "key": "fight_shoot"},
    "taunt":  {"label": "Taunt",  "uni": "😤", "key": "fight_taunt"},
    "flee":   {"label": "Flee",   "uni": "🏃", "key": "fight_flee"},
}

def _fa_icon(a: str) -> str:
    d = FIGHT_ACTIONS[a]
    return emoji(d["key"]) or d["uni"]

def _fa_partial(a: str) -> dict:
    d = FIGHT_ACTIONS[a]
    p = emoji_partial(d["key"])
    eid = p.get("id")
    if eid and (not _usable_emoji_ids or eid in _usable_emoji_ids):
        return p
    return {"name": d["uni"]}

def _myth_monster_hp(biome: str) -> int:
    return FIGHT_MONSTER_HP_BASE + BIOME_TOOL_TIER.get(biome, 1) * FIGHT_MONSTER_HP_TIER

def _myth_can_shoot(user_id: str) -> bool:
    tool = data[user_id].get("tool", "Bare Hands")
    if not tool_needs_ammo(tool):
        return False
    an = get_equipped_ammo(user_id)
    return bool(an and ammo_compatible_with_tool(an, tool)
               and get_ammo_count(user_id, an) >= FIGHT_SHOOT_AMMO)

def _myth_fight_ensure(user_id: str) -> dict | None:
    """Backfill combat fields on `_boss` — for a fresh encounter or a hand-off
    from the pre-rework KILL/RUN encounter. Player HP is data[uid]["health"] —
    persistent, not reset to 100 here."""
    b = data[user_id].get("_boss")
    if not b:
        return None
    if b.pop("php", None) is not None:
        # legacy row from before HP became persistent — drop the stale field
        mark_user_dirty(user_id)
    refresh_health(user_id)
    if "mhp" not in b:
        mhp = _myth_monster_hp(b.get("biome", data[user_id].get("biome", "village")))
        b.update({"mhp": mhp, "mhp_max": mhp, "turn": 1,
                  "fallen": False, "guard": False, "enrage": False,
                  "mdebuff": False, "log": []})
        mark_user_dirty(user_id)
    return b

def _hp_bar(cur: int, mx: int) -> str:
    pct = 100.0 if mx <= 0 else max(0, min(100, max(0, cur) / mx * 100))
    return _pct_bar(pct)

def _myth_fight_win(user_id: str, name: str, c: dict, biome: str, b: dict) -> dict:
    data[user_id]["_boss"] = None
    php_left = max(0, data[user_id].get("health", {}).get("hp", 0))
    stats   = data[user_id].setdefault("stats", {})
    is_first_kill = stats.get("myths_killed", 0) == 0
    if is_first_kill:
        bounty, gems_gain = MYTH_FIRST_KILL_BOUNTY, MYTH_FIRST_KILL_GEMS
    else:
        bounty    = random.randint(*MYTH_REPEAT_BOUNTY_RANGE)
        gems_gain = random.randint(*MYTH_REPEAT_GEMS_RANGE)
    xp_gain = int(c.get("xp", 0) * MYTH_XP_MULT)
    add_money(user_id, bounty, "myth kill")
    add_gems(user_id, gems_gain, "myth kill")
    data[user_id]["total_money_earned"] = data[user_id].get("total_money_earned", 0) + bounty
    data[user_id]["xp"] += xp_gain
    stats["total_xp_earned"] = stats.get("total_xp_earned", 0) + xp_gain
    level_ups = 0
    while data[user_id]["xp"] >= xp_for_level(data[user_id]["level"]):
        data[user_id]["xp"] -= xp_for_level(data[user_id]["level"])
        data[user_id]["level"] += 1
        level_ups += 1
    drop = c.get("drop", "")
    trophy_count = 0
    if drop:
        mi = data[user_id].setdefault("myth_items", {})
        mi[drop] = mi.get(drop, 0) + 1
        trophy_count = mi[drop]
    mr = data[user_id].setdefault("myth_record", {})
    entry = mr.setdefault(name, {"kills": 0, "first_kill_ts": int(time.time()), "best_hp_left": 0})
    entry["kills"] += 1
    entry["best_hp_left"] = max(entry.get("best_hp_left", 0), php_left)
    is_new_discovery = entry["kills"] == 1
    myth_shard = random.random() < MYTH_SHARD_KILL_CHANCE
    if myth_shard:
        add_shard(user_id, "mythic", 1)
    data[user_id]["total_caught"] = data[user_id].get("total_caught", 0) + 1
    stats["myths_killed"] = stats.get("myths_killed", 0) + 1
    first_title = ""
    if is_first_kill:
        earned = data[user_id].setdefault("earned_titles", [])
        if "Mythic Slayer" not in earned:
            earned.append("Mythic Slayer")
            first_title = "Mythic Slayer"
    analytics(user_id, "myth_killed", creature=name, biome=biome, php_left=php_left,
              first_kill=is_first_kill)
    quest_progress(user_id, "animals_caught", 1)
    quest_progress(user_id, "rarity_caught", 1, rarity="mythic")
    quest_progress(user_id, "hunts_in_biome", 1, biome=biome)
    if xp_gain:
        quest_progress(user_id, "xp_earned_quest", xp_gain)
    if level_ups:
        quest_progress(user_id, "levels_gained_quest", level_ups)
    mark_user_dirty(user_id)
    _sid = make_share(user_id, "myth_kill", creature=name, biome=biome, drop=drop, php=php_left)
    return {"kind": "kill", "creature": name, "bounty": bounty, "gems": gems_gain, "xp": xp_gain,
            "drop": drop, "drop_value": c.get("drop_value", 0), "myth_shard": myth_shard,
            "trophy_count": trophy_count, "is_new_discovery": is_new_discovery,
            "level_ups": level_ups, "level": data[user_id]["level"],
            "balance": data[user_id]["money"], "php": php_left,
            "is_first_kill": is_first_kill, "first_title": first_title,
            "share_id": _sid}

def _myth_fight_lose(user_id: str, name: str, c: dict) -> dict:
    data[user_id]["_boss"] = None
    stats = data[user_id].setdefault("stats", {})
    loss  = max(0, min(int(data[user_id]["money"] * MYTH_DEATH_LOSS_CASH),
                       int(c.get("value", 0) * MYTH_DEATH_LOSS_VALUE)))
    loss  = int(loss * (1 - trophy_effect_value(user_id, "myth_loss_pct") / 100))  # Garm: Broken Hel-Chain Link
    if loss > 0:
        spend_money(user_id, loss, "myth death")
    stats["myths_died"] = stats.get("myths_died", 0) + 1
    rec = apply_ko_recovery(user_id)   # the existing cash penalty stands; HP still recovers
    phoenix_save = False
    if trophy_has_effect(user_id, "phoenix_revive_daily") and _trophy_daily_use(user_id, "phoenix"):
        target_hp = int(trophy_effect_value(user_id, "phoenix_revive_daily"))
        if rec["hp"] < target_hp:
            data[user_id]["health"]["hp"] = min(effective_max_hp(user_id), target_hp)
            rec["hp"] = data[user_id]["health"]["hp"]
        phoenix_save = True
    mark_user_dirty(user_id)
    return {"kind": "death", "creature": name, "loss": loss,
            "balance": data[user_id]["money"], "rookie_save": rec["rookie_save"], "hp": rec["hp"],
            "phoenix_save": phoenix_save}

def myth_fight_turn(user_id: str, action: str) -> dict:
    """Resolve one round of the boss fight. Mutates — call inside a
    ``user_transaction``. Returns {kind: 'ongoing'|'kill'|'death'|'escape'|'none'}."""
    b = _myth_fight_ensure(user_id)
    if not b:
        return {"kind": "none"}
    h     = data[user_id]["health"]
    name  = b["creature"]
    c     = MYTHIC_CREATURES.get(name, {})
    biome = b.get("biome", data[user_id].get("biome", "village"))
    ico   = creature_emoji(name)
    tool  = data[user_id].get("tool", "Bare Hands")
    tier  = get_tool_tier(tool)
    luck  = max(0, get_total_boosts(user_id).get("luck", 0))
    diff  = BIOME_TOOL_TIER.get(biome, 1)
    acc_b = luck // 25 + trophy_effect_value(user_id, "combat_accuracy_pct")          # Roc: Grapnel Talon
    pk_acc_b = trophy_effect_value(user_id, "punch_kick_accuracy_pct")                # Manticore: Barbed Tail-Spine
    dmg_mult = 1 + trophy_effect_value(user_id, "myth_dmg_pct") / 100                 # Werewolf: Silver-Burned Fang
    R     = random.randint
    log: list[str] = []

    # ── FLEE ──
    if action == "flee":
        clean = R(1, 100) <= min(96, MYTH_RUN_BASE + luck // 2 + trophy_effect_value(user_id, "myth_flee_pct"))  # Sirens
        data[user_id]["_boss"] = None
        data[user_id].setdefault("stats", {})
        data[user_id]["stats"]["myths_fled"] = data[user_id]["stats"].get("myths_fled", 0) + 1
        mark_user_dirty(user_id)
        return {"kind": "escape", "creature": name, "clean": clean}

    # Dragon: Bottle of Dragon Breath — burn ticks from a previous turn's ignition
    if b.get("burn_turns", 0) > 0:
        bd = b.get("burn_dmg", 0)
        b["mhp"] = max(0, b["mhp"] - bd)
        b["burn_turns"] -= 1
        log.append(f"{emoji('fire')} The burn sears it for **{bd}** ({b['burn_turns']} turn(s) left).")
        if b["mhp"] <= 0:
            b["log"] = (b.get("log", []) + log)[-4:]
            return _myth_fight_win(user_id, name, c, biome, b)

    def _land_hit(dealt: int) -> int:
        """Apply the shared on-hit trophy effects (damage mult, first-hit
        bonus, burn ignition, double-hit) to a successful player attack."""
        dealt = int(dealt * dmg_mult)
        if not b.get("first_hit_done"):
            dealt += int(trophy_effect_value(user_id, "first_hit_bonus_dmg"))         # Chimera: Fire-Gland Sac
            if trophy_has_effect(user_id, "burn_on_hit"):                             # Dragon: Bottle of Dragon Breath
                b["burn_turns"] = 3
                b["burn_dmg"]   = max(5, dealt // 3)
                log.append(f"{emoji('fire')} The hit catches fire — it'll burn for **{b['burn_dmg']}**/turn.")
            b["first_hit_done"] = True
        if trophy_proc(user_id, "double_hit_pct"):                                    # Scylla: Six-Fanged Collar
            log.append(f"{emoji('impact')} The strike lands twice!")
            dealt *= 2
        if trophy_proc(user_id, "enemy_skip_pct"):                                    # Cockatrice: Petrifying Eye
            b["stun"] = True
            log.append(f"`👁️` It staggers — its next attack will miss.")
        return dealt

    dealt = 0
    if b.get("fallen"):
        b["fallen"] = False
        log.append("You're still scrambling up — no attack this turn.")
    elif action == "punch":
        if R(1, 100) <= 92 + acc_b + pk_acc_b:
            dealt = R(7, 13) + tier // 2
            if b.pop("enrage", False):
                dealt = int(dealt * 1.5); log.append("`💢` Opening exploited!")
            dealt = _land_hit(dealt)
            log.append(f"{_fa_icon('punch')} You hammer the {name} for **{dealt}**.")
        else:
            log.append(f"{_fa_icon('punch')} Your jab glances off.")
    elif action == "kick":
        if R(1, 100) <= 64 + acc_b + pk_acc_b:
            dealt = R(17, 27) + tier
            if b.pop("enrage", False):
                dealt = int(dealt * 1.5); log.append("`💢` Opening exploited!")
            dealt = _land_hit(dealt)
            log.append(f"{_fa_icon('kick')} A crushing kick lands — **{dealt}**!")
        elif R(1, 100) <= 35:
            b["fallen"] = True
            log.append(f"{_fa_icon('kick')} You overreach, slip, and go down hard.")
        else:
            log.append(f"{_fa_icon('kick')} The {name} reads the kick and steps clear.")
    elif action == "defend":
        b["guard"] = True
        heal = R(5, 10)
        h["hp"] = min(effective_max_hp(user_id), h["hp"] + heal)
        log.append(f"{_fa_icon('defend')} You plant your feet and steady up (+{heal} HP).")
    elif action == "shoot":
        if not tool_needs_ammo(tool):
            log.append(f"{_fa_icon('shoot')} Your {tool} takes no ammo — close the distance instead.")
        elif not _myth_can_shoot(user_id):
            _at = AMMO_TYPE_LABELS.get(get_tool_ammo_type(tool), "ammo")
            log.append(f"{_fa_icon('shoot')} *click* — you need **{FIGHT_SHOOT_AMMO}** {_at} to lay down fire.")
        else:
            an = get_equipped_ammo(user_id)
            if not ev_ammo_free():
                consume_ammo(user_id, an, FIGHT_SHOOT_AMMO)
                if get_ammo_count(user_id, an) == 0:
                    data[user_id]["equipped_ammo"] = None
            if R(1, 100) <= 88 + acc_b:
                dealt = R(24, 42) + tier
                if b.pop("enrage", False):
                    dealt = int(dealt * 1.5); log.append("`💢` Opening exploited!")
                dealt = _land_hit(dealt)
                log.append(f"{_fa_icon('shoot')} You unload {FIGHT_SHOOT_AMMO} rounds into it — **{dealt}** damage!")
            else:
                log.append(f"{_fa_icon('shoot')} {FIGHT_SHOOT_AMMO} rounds spent, the volley goes wide.")
    elif action == "taunt":
        b["enrage"]  = True
        b["mdebuff"] = True
        log.append(f"{_fa_icon('taunt')} You taunt the {name} — it lunges, wild and off-balance.")
    else:
        return {"kind": "none"}

    if dealt:
        b["mhp"] = max(0, b["mhp"] - dealt)
    if b["mhp"] <= 0:
        b["log"] = (b.get("log", []) + log)[-4:]
        return _myth_fight_win(user_id, name, c, biome, b)

    # ── MONSTER TURN ──
    if b.pop("stun", False):
        b.pop("guard", False)   # a skipped attack still "used up" this round's defend
        b.pop("mdebuff", False)
        log.append(f"{ico} Still reeling — it can't attack this turn.")
    else:
        macc = 80 - diff // 2 - (25 if b.pop("mdebuff", False) else 0)
        if b.get("fallen") or R(1, 100) <= macc:
            base    = R(6 + diff // 3, 12 + diff)
            special = random.random() < 0.15
            mdmg    = int(base * 1.6) if special else base
            mdmg    = int(mdmg * (1 - trophy_effect_value(user_id, "incoming_dmg_pct") / 100))  # Sea Serpent
            if not b.get("first_enemy_hit_done"):
                red = trophy_effect_value(user_id, "first_enemy_hit_reduction_pct")   # Yeti: Frost-Matted Pelt
                if red:
                    mdmg = max(1, int(mdmg * (1 - red / 100)))
                b["first_enemy_hit_done"] = True
            if b.pop("guard", False):
                mdmg = max(1, int(mdmg * 0.4))
                log.append(f"{ico} It slams into your guard — you eat **{mdmg}**.")
            elif special:
                log.append(f"{ico} **{name}** — *{c.get('call', 'a savage strike')}* — **{mdmg}**!")
            else:
                log.append(f"{ico} The {name} tears back for **{mdmg}**.")
            h["hp"] = max(0, h["hp"] - mdmg)
        else:
            b.pop("guard", False)
            log.append(f"{ico} The {name} lunges and misses.")

    if h["hp"] <= 0:
        if trophy_has_effect(user_id, "hydra_survive_daily") and _trophy_daily_use(user_id, "hydra"):
            h["hp"] = 1
            log.append(f"`🐍` **Immortal Head Tooth** flickers — you survive at **1 HP**.")
        else:
            b["log"] = (b.get("log", []) + log)[-4:]
            return _myth_fight_lose(user_id, name, c)

    b["turn"] = b.get("turn", 1) + 1
    b["log"] = (b.get("log", []) + log)[-4:]
    mark_user_dirty(user_id)
    return {"kind": "ongoing"}

# ─────────────────────────────────────────────
# PROGRESS BAR / FORMAT HELPERS
# ─────────────────────────────────────────────

def _pill_bar(filled: int, width: int) -> str:
    """`filled` consecutive slots (out of `width`) joined into one seamless
    pill — left+middle…+right — never repeated `whole` tiles, which render as
    a strip of separate circles instead of one bar. `whole` is only for a
    single filled slot; `middle` fills everything between the two caps."""
    filled = max(0, min(width, filled))
    if filled <= 0:
        segs = []
    elif filled == 1:
        segs = [emoji("green_bar_whole")]
    else:
        segs = ([emoji("green_bar_left")]
                + [emoji("green_bar_middle")] * (filled - 2)
                + [emoji("green_bar_right")])
    return "".join(segs) + emoji("blank_icon") * (width - filled)

def _pct_bar(pct: float) -> str:
    """Render 0–100 as the green pill bar: up to 10 slots, 5% resolution.
    left/middle/right join full 10%-slots into one seamless pill; whole /
    half_whole cover a bar that's just one slot long; half_right caps off
    a final +5% after slots that came before it."""
    units = max(0, min(20, int(pct / 5 + 0.5)))   # 5%-steps, 0..20
    if units == 0:
        return ""
    out, i = [], 0
    while i * 2 < units:
        remaining = units - i * 2
        is_first  = i == 0
        is_last   = remaining <= 2
        if remaining >= 2:
            if is_first and is_last:
                out.append(emoji("green_bar_whole"))
            elif is_first:
                out.append(emoji("green_bar_left"))
            elif is_last:
                out.append(emoji("green_bar_right"))
            else:
                out.append(emoji("green_bar_middle"))
        else:
            out.append(emoji("green_bar_half_whole") if is_first else emoji("green_bar_half_right"))
        i += 1
    return "".join(out)

def _progress_bar(current: int, maximum: int, width: int = 16) -> str:
    if maximum <= 0:
        return f"{_pct_bar(100)} 100%"
    pct = min(current / maximum, 1.0) * 100
    return f"{_pct_bar(pct)} {pct:.1f}%"

def _fmt(n: int) -> str:
    return f"{n:,}"

def _reward_str(rtype: str, amount: int) -> str:
    icon = "◈" if rtype == "money" else emoji("gem")
    return f"{icon} {amount:,}"

def _back_row(user_id: str) -> dict:
    return {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Back",
         "custom_id": f"nav:menu:{user_id}"}
    ]}

def _ach_back_row(user_id: str) -> dict:
    return {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Back",
         "custom_id": f"ach:back:{user_id}"}
    ]}

# ─────────────────────────────────────────────
# UI HELPERS  ·  shared building blocks for the redesigned screens
# ─────────────────────────────────────────────
# One screen = one purpose, ~5 things visible before buttons, one green
# primary action, predictable "◀ Back | 🏠 Menu" footers. These helpers exist
# so every screen builds that the same way instead of hand-rolling
# {"type": 14}/{"type": 10}/{"type": 1} dicts slightly differently each time.
# (ph() itself now lives near the top of the file — module-level literals
# like ADMIN_BUFF_EVENT need it before this section is even parsed.)

def ui_header(icon: str, title: str, subtitle: str = "") -> str:
    head = f"## {ph(icon)} {title}"
    if subtitle:
        head += f"\n-# {subtitle}"
    return head

def ui_section(body: str, accessory: dict = None) -> dict:
    """A single Discord content block. Pass `accessory` (a button dict) to
    get a type-9 section — text plus one action pinned to its right, the
    pattern Shop already used well — otherwise a plain type-10 text block."""
    if accessory:
        return {"type": 9, "components": [{"type": 10, "content": body}],
                "accessory": accessory}
    return {"type": 10, "content": body}

def ui_progress(current: int, target: int, width: int = 10) -> tuple[str, str]:
    """(bar, pct_label) — the custom-emoji bar (never raw unicode blocks,
    they render inconsistently across fonts) plus a percentage with no
    decimal noise: '<1%', a whole number, or '100%'."""
    if target <= 0:
        return _pill_bar(width, width), "100%"
    pct = min(100.0, current / target * 100)
    filled = max(0, min(width, round(width * current / target)))
    bar = _pill_bar(filled, width)
    if pct >= 100:
        label = "100%"
    elif pct < 1:
        label = "<1%"
    else:
        label = f"{int(pct)}%"
    return bar, label

def ui_footer(user_id: str, *, back: str = None, back_label: str = "◀ Back") -> dict:
    """The standard bottom row: an optional Back to the immediate parent
    screen, always followed by Home to Menu. Skip `back` on a screen that
    IS one hop from Menu already — no point offering the same button twice."""
    buttons = []
    if back:
        buttons.append({"type": 2, "style": 2, "label": back_label, "custom_id": back})
    buttons.append({"type": 2, "style": 2, "label": "Menu", "emoji": emoji_partial('home'), "custom_id": f"nav:menu:{user_id}"})
    return {"type": 1, "components": buttons}

def ui_money(n: int) -> str:
    return f"◈ {n:,}"

def ui_status(on: bool) -> str:
    return f"{emoji('check_mark')} ON" if on else "`⬜` OFF"

# ─────────────────────────────────────────────
# BADGE HELPERS
# ─────────────────────────────────────────────

def _special_badge_keys(user_id: str) -> list[str]:
    """Admin-granted special badge keys the player holds, in SPECIAL_BADGES order."""
    held = data.get(user_id, {}).get("special_badges", [])
    return [k for k in SPECIAL_BADGES if k in held]

def get_badge_display(user_id: str) -> str:
    parts = []
    for badge_key, bdef in BADGES.items():
        tier = data.get(user_id, {}).get("badges", {}).get(badge_key, {}).get("tier", 0)
        if tier < 1:
            continue
        ico = badge_emoji(badge_key, tier)
        parts.append(ico if ico else f"`{bdef['abbr']}{'🏆' if tier == 2 else '🥇'}`")
    for badge_key in _special_badge_keys(user_id):
        ico = badge_emoji(badge_key, 1)
        parts.append(ico if ico else f"`{SPECIAL_BADGES[badge_key]['abbr']}★`")
    return " ".join(parts) if parts else ""

def _badge_tier(user_id: str, badge_key: str) -> int:
    if badge_key in SPECIAL_BADGES:
        return 1 if badge_key in data.get(user_id, {}).get("special_badges", []) else 0
    return data.get(user_id, {}).get("badges", {}).get(badge_key, {}).get("tier", 0)

def _earned_badge_keys(user_id: str) -> list[str]:
    """Badge keys the player has (Gold+ for stat badges, held for special ones),
    stat badges first in BADGES order, then special badges in SPECIAL_BADGES order."""
    return ([k for k in BADGES if _badge_tier(user_id, k) >= 1]
            + _special_badge_keys(user_id))

def featured_badge_key(user_id: str) -> str | None:
    """The badge shown next to the player's name in lists. Their explicit pick if
    still earned, else their first-earned badge, else None."""
    earned = _earned_badge_keys(user_id)
    if not earned:
        return None
    pick = data.get(user_id, {}).get("featured_badge")
    return pick if pick in earned else earned[0]

def featured_badge_icon(user_id: str) -> str:
    """Emoji string for the featured badge (custom emoji, or 🥇/🏆 fallback), or ''."""
    key = featured_badge_key(user_id)
    if not key:
        return ""
    tier = _badge_tier(user_id, key)
    return badge_emoji(key, tier) or ("🏆" if tier >= 2 else "🥇")

def featured_badge_suffix(user_id: str) -> str:
    """featured_badge_icon with a leading space when set — shown AFTER the name
    (tribe-role icons go before the name, the badge goes after)."""
    ico = featured_badge_icon(user_id)
    return f" {ico}" if ico else ""

# ─────────────────────────────────────────────
# ACHIEVEMENTS PAGE BUILDER
# ─────────────────────────────────────────────

ACH_LABELS = {
    "daily_streak":    "Daily Streak",
    "animals_caught":  "Animals Caught",
    "ammo_used":       "Ammo Used",
    "tools_bought_all":"Buy All Tools",
    "tools_used_all":  "Use All Tools",
    "gamble":          "Gamble",
    "crates_opened": "Crates Opened",
}

_ACH_LINES_PER_PAGE = 15
_BADGE_LINES_PER_PAGE = 30

def build_achievements_pages(user_id: str) -> list[str]:
    d         = data[user_id]
    s         = d.get("stats", {})
    pages     = []
    cur_page  = []
    cur_lines = 0

    def flush():
        nonlocal cur_lines
        if cur_page:
            pages.append("\n".join(cur_page))
            cur_page.clear()
        cur_lines = 0

    all_tools_owned = all(t in d.get("owned_tools", []) for t in TOOLS)
    all_tools_used  = all(t in s.get("tools_used", []) for t in TOOLS)

    ACH_SOURCES = {
        "daily_streak":    d.get("daily_streak", 0),
        "animals_caught":  d.get("total_caught", 0),
        "ammo_used":       s.get("ammo_used", 0),
        "tools_bought_all":1 if all_tools_owned else 0,
        "tools_used_all":  1 if all_tools_used  else 0,
        "gamble":          0,
        "crates_opened": d.get("stats", {}).get("crates_opened", 0),
    }

    for ach_key, tiers in ACHIEVEMENTS.items():
        label         = ACH_LABELS.get(ach_key, ach_key.replace("_", " ").title())
        claimed_up_to = d["achievements"].get(ach_key, {}).get("claimed_up_to", -1)
        current_val   = ACH_SOURCES.get(ach_key, 0)

        # Each achievement group starts on its own page
        if cur_lines > 0:
            flush()

        cur_page.append(f"### {emoji('achievements')} {label}")
        cur_lines += 2

        if not tiers:
            cur_page.append("-# Coming soon!")
            cur_lines += 1
            continue

        for i, tier_entry in enumerate(tiers):
            # Unpack tier format
            if len(tier_entry) == 2:
                threshold, rewards = tier_entry
                if not isinstance(rewards, list) or (
                    len(rewards) == 2 and isinstance(rewards[0], str)
                ):
                    rewards = [rewards]
            elif len(tier_entry) == 3:
                threshold, rtype, amount = tier_entry
                rewards = [(rtype, amount)]
            else:
                continue

            done  = claimed_up_to >= i
            check = f"{emoji('check_mark')}" if done else "`⬜`"
            bar   = _progress_bar(min(current_val, threshold), threshold) + f"\n`{current_val}/{threshold}`\n"
            reward_parts = [_reward_str(rtype, amount) for rtype, amount in rewards]
            reward = " + ".join(reward_parts)
            line1  = f"{check} **{_fmt(threshold)}** — {reward}"
            line2  = f"-# {bar}"
            cur_page.append(line1)
            cur_page.append(line2)
            cur_lines += 3

            if cur_lines >= _ACH_LINES_PER_PAGE:
                flush()
                # Re-add the header for continuation pages within same achievement
                cur_page.append(f"### {emoji('achievements')} {label}")
                cur_lines += 2

    flush()
    return pages if pages else ["No achievements yet."]


def _closest_achievement_reward(user_id: str) -> tuple[dict | None, int]:
    """(best, close_count) — best is the next unclaimed tier across every
    achievement with the highest %-to-completion (or None if everything is
    claimed); close_count is how many other next-tiers are >=80% there too.
    Powers Progression's 'closest reward' callout."""
    d = data[user_id]
    s = d.get("stats", {})
    all_tools_owned = all(t in d.get("owned_tools", []) for t in TOOLS)
    all_tools_used  = all(t in s.get("tools_used", []) for t in TOOLS)
    ACH_SOURCES = {
        "daily_streak":    d.get("daily_streak", 0),
        "animals_caught":  d.get("total_caught", 0),
        "ammo_used":       s.get("ammo_used", 0),
        "tools_bought_all":1 if all_tools_owned else 0,
        "tools_used_all":  1 if all_tools_used  else 0,
        "gamble":          0,
        "crates_opened":   s.get("crates_opened", 0),
    }
    candidates = []
    for ach_key, tiers in ACHIEVEMENTS.items():
        if not tiers:
            continue
        label         = ACH_LABELS.get(ach_key, ach_key.replace("_", " ").title())
        claimed_up_to = d["achievements"].get(ach_key, {}).get("claimed_up_to", -1)
        current_val   = ACH_SOURCES.get(ach_key, 0)
        for i, tier_entry in enumerate(tiers):
            if i <= claimed_up_to:
                continue
            if len(tier_entry) == 2:
                threshold, rewards = tier_entry
                if not isinstance(rewards, list) or (
                    len(rewards) == 2 and isinstance(rewards[0], str)
                ):
                    rewards = [rewards]
            elif len(tier_entry) == 3:
                threshold, rtype, amount = tier_entry
                rewards = [(rtype, amount)]
            else:
                continue
            if threshold <= 0:
                continue
            pct = min(current_val, threshold) / threshold
            reward = " + ".join(_reward_str(rt, amt) for rt, amt in rewards)
            candidates.append({"label": label, "current": current_val,
                                "threshold": threshold, "pct": pct, "reward": reward})
            break  # only the next unclaimed tier per achievement counts
    if not candidates:
        return None, 0
    best = max(candidates, key=lambda c: c["pct"])
    close_count = sum(1 for c in candidates if c is not best and c["pct"] >= 0.8)
    return best, close_count


_BADGE_TIER_NAME = {1: "GOLD", 2: "PLATINUM"}
_BADGES_PER_PAGE = 4   # each entry now breathes (icon+name, tracks, next tier, bar) —
                        # showing Gold AND Platinum stacked at once was the whole problem.

def _badge_entry_text(user_id: str, badge_key: str, bdef: dict, featured: str) -> str:
    """One badge, one screenful's worth of signal: current tier, the NEXT tier
    only (never both at once), one bar with a whole-number percent, short
    numbers throughout. A maxed badge drops the bar entirely."""
    tier   = _badge_tier(user_id, badge_key)
    label  = bdef["label"]
    gold_t = bdef["gold"]
    plat_t = bdef["plat"]
    stat   = bdef["stat"]
    cur    = get_badge_stat(user_id, stat)
    star   = " `★`" if badge_key == featured else ""
    tracks = bdef.get("tracks", "")

    maxed = tier >= 2 or (tier >= 1 and not plat_t)
    if maxed:
        medal     = emoji('trophy') if tier == 2 else f"{emoji('first_place_medal')}"
        tier_name = _BADGE_TIER_NAME.get(tier, "GOLD")
        return (f"{medal} **{label}** · {tier_name}{star}\n"
                f"-# {tracks}\n"
                f"-# {emoji('check_mark')} Badge fully completed")

    next_target = gold_t if tier == 0 else plat_t
    next_name   = "Gold" if tier == 0 else "Platinum"
    lead_icon   = emoji('lock') if tier == 0 else f"{emoji('first_place_medal')}"
    title_line  = f"{lead_icon} **{label}**{' · GOLD' if tier == 1 else ''}{star}"

    if next_target <= 3:
        # A 1-or-2-step target renders as a meaningless bar (0% or 100%, no
        # in-between) — show it as a plain done/not-done line instead.
        done = cur >= next_target
        status = f"{emoji('check_mark')} Completed" if done else f"{emoji('lock')} Not completed"
        return f"{title_line}\n-# {tracks}\n-# {status}"

    bar, pct_label = ui_progress(cur, next_target)
    return (f"{title_line}\n"
            f"-# {tracks}\n"
            f"-# {emoji('trophy') if tier == 1 else emoji('first_place_medal')} Next: {next_name}\n"
            f"-# {_short_num(cur)} / {_short_num(next_target)}\n"
            f"-# {bar} {pct_label}")

def build_badges_pages(user_id: str) -> list[str]:
    featured  = featured_badge_key(user_id)
    entries   = [_badge_entry_text(user_id, k, bdef, featured) for k, bdef in BADGES.items()]

    held_special = _special_badge_keys(user_id)
    if held_special:
        special_lines = ["### `★` Special Badges\n-# Handed out by the developers."]
        for badge_key in held_special:
            sb   = SPECIAL_BADGES[badge_key]
            star = " `★`" if badge_key == featured else ""
            ico  = badge_emoji(badge_key, 1) or "★"
            special_lines.append(f"{ico} **{sb['label']}**{star}\n-# {sb['blurb']}")
        entries.append("\n\n".join(special_lines))

    pages = ["\n\n".join(entries[i:i + _BADGES_PER_PAGE])
             for i in range(0, len(entries), _BADGES_PER_PAGE)]
    return pages if pages else ["No badges yet."]

# ─────────────────────────────────────────────
# PROGRESSION HUB + COMPONENTS
# ─────────────────────────────────────────────

def build_progression_hub(user_id: str) -> list:
    d             = data[user_id]
    total_ach     = sum(
        d["achievements"].get(k, {}).get("claimed_up_to", -1) + 1
        for k in ACHIEVEMENTS if ACHIEVEMENTS.get(k)
    )
    total_possible = sum(len(v) for v in ACHIEVEMENTS.values() if isinstance(v, list))
    badge_count   = sum(
        1 for k in BADGES
        if d.get("badges", {}).get(k, {}).get("tier", 0) >= 1
    )
    special_count = len(_special_badge_keys(user_id))
    title_count   = len(d.get("earned_titles", []))
    equipped_title = d.get("equipped_title")
    featured       = featured_badge_key(user_id)
    featured_line  = (f"Featured: {featured_badge_icon(user_id)} "
                       f"**{badge_meta(featured).get('label', featured)}**" if featured else "None yet")
    title_line     = f'"{equipped_title}"' if equipped_title else "None equipped"
    gc             = guide_completion(user_id)
    best, close_count = _closest_achievement_reward(user_id)

    lines = [
        ui_header(emoji('trophy'), "PROGRESSION",
                  f"Level {d['level']} · Prestige {d.get('prestige', 0)}\n"
                  f"{ph(emoji('book'))} World Completion **{gc['world_pct']:.0f}%**"),
        "",
        f"{ph(emoji('sports_medal'))} **ACHIEVEMENTS**",
        f"{total_ach}/{total_possible}" + (f" · {close_count} reward{'s' if close_count != 1 else ''} close" if close_count else ""),
        "",
        f"{ph(emoji('military_medal'))} **BADGES**",
        f"{badge_count}/{len(BADGES)}" + (f" (+{special_count} `★` special)" if special_count else "") + f" · {featured_line}",
        "",
        f"{ph(emoji('label'))} **TITLES**",
        f"{title_count} unlocked · {title_line}",
    ]
    if best:
        bar, pct_label = ui_progress(best["current"], best["threshold"])
        lines += [
            "",
            f"{ph(emoji('target'))} **CLOSEST REWARD**",
            best["label"],
            f"{bar} {_short_num(best['current'])}/{_short_num(best['threshold'])} ({pct_label})",
            f"Reward: {best['reward']}",
        ]
    content = "\n".join(lines)

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Achievements", "emoji": emoji_partial('sports_medal'),
             "custom_id": f"ach:achievements:{user_id}"},
            {"type": 2, "style": 1, "label": "Badges", "emoji": emoji_partial('military_medal'),
             "custom_id": f"ach:badges:{user_id}"},
        ]},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Titles", "emoji": emoji_partial('label'),
             "custom_id": f"ach:titles:{user_id}"},
            {"type": 2, "style": 2, "label": "Collection", "emoji": emoji_partial('book'),
             "custom_id": f"guide:open:{user_id}"},
        ]},
        ui_footer(user_id),
    ]}]

def build_achievements_components(user_id: str) -> list:
    pages = build_achievements_pages(user_id)
    page  = _ach_page.get(user_id, 0)
    page  = max(0, min(page, len(pages) - 1))
    total = len(pages)
    content = f"### {emoji('achievements')} Achievements — Page {page+1}/{total}\n\n{pages[page]}"
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Prev",
         "custom_id": f"ach:prev:{user_id}", "disabled": page == 0},
        {"type": 2, "style": 2, "label": "Next ▶",
         "custom_id": f"ach:next:{user_id}", "disabled": page >= total - 1},
        {"type": 2, "style": 2, "label": "◀ Back",
         "custom_id": f"ach:back:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

def build_badges_components(user_id: str) -> list:
    pages = build_badges_pages(user_id)
    page  = _badge_page.get(user_id, 0)
    page  = max(0, min(page, len(pages) - 1))
    total = len(pages)

    featured = featured_badge_key(user_id)
    feat_line = ""
    if featured:
        feat_line = (f"\n-# `★` Featured: {featured_badge_icon(user_id)} "
                     f"**{badge_meta(featured).get('label', featured)}** — shown next to your name on leaderboards.")
    content = f"### {emoji('military_medal')} Badges — Page {page+1}/{total}{feat_line}\n\n{pages[page]}"

    comps = [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
    ]

    earned = _earned_badge_keys(user_id)
    if earned:
        opts = []
        for k in earned[:25]:
            tier = _badge_tier(user_id, k)
            meta = badge_meta(k)
            kind = "Special" if k in SPECIAL_BADGES else ("Platinum" if tier >= 2 else "Gold")
            o = {"label": meta.get("label", k)[:100], "value": k,
                 "default": k == featured,
                 "description": f"[{meta.get('abbr', '?')}] · {kind}"[:100]}
            em = emoji_partial(badge_emoji(k, tier))
            if em:
                o["emoji"] = em
            opts.append(o)
        comps.append({"type": 1, "components": [{"type": 3,
            "custom_id": f"badge:feature:{user_id}",
            "placeholder": "★ Feature a badge…",
            "min_values": 1, "max_values": 1, "flows": {}, "options": opts}]})

    comps.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Prev",
         "custom_id": f"badge:prev:{user_id}", "disabled": page == 0},
        {"type": 2, "style": 2, "label": "Next ▶",
         "custom_id": f"badge:next:{user_id}", "disabled": page >= total - 1},
        {"type": 2, "style": 2, "label": "◀ Back",
         "custom_id": f"ach:back:{user_id}"},
    ]})
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ─────────────────────────────────────────────
# TITLE PANEL
# ─────────────────────────────────────────────

def build_title_components(user_id: str) -> list:
    d        = data[user_id]
    earned   = d.get("earned_titles", [])
    equipped = d.get("equipped_title")

    if not earned:
        content = (
            f"### {emoji('label')} Titles\n\n"
            "-# You haven't unlocked any titles yet.\n"
            "-# Complete achievements to earn titles!"
        )
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            _ach_back_row(user_id),
        ]}]

    equipped_line = f'Equipped: **"{equipped}"**' if equipped else "Equipped: *None*"
    lines = "\n".join(
        f"{emoji('check_mark') if t == equipped else '`⬜`'} {t}" for t in earned
    )
    content = (
        f"### {emoji('label')} Titles\n"
        f"{equipped_line}\n\n"
        f"**Unlocked ({len(earned)}):**\n{lines}"
    )
    options = [{"label": "— None (unequip) —", "value": "__none__", "default": not equipped}]
    options += [
        {"label": t[:100], "value": t[:100], "default": t == equipped}
        for t in earned[:24]
    ]
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"title:equip:{user_id}",
            "placeholder": "Select a title to equip...",
            "min_values": 1, "max_values": 1, "flows": {},
            "options": options,
        }]},
        {"type": 14, "divider": True, "spacing": 1},
        _ach_back_row(user_id),
    ]}]

# ─────────────────────────────────────────────
# MENU PANEL
# ─────────────────────────────────────────────

def build_menu_components(user_id: str, display_name: str) -> list:
    """Menu answers one question: 'what should I do?' Everything else — the
    full stat dump, tribe/vehicle/ammo detail, inventory contents — lives one
    tap away on its own screen (Profile, Equipment, Inventory, Progression).
    Redesigned 2026-09-15: was a 20-line debug-dashboard text wall plus a
    flat 22-item dropdown; now ~5 things visible before any buttons."""
    d         = data[user_id]
    refresh_health(user_id)
    biome     = d.get("biome", "village")
    tool_name = d.get("tool", "Bare Hands")
    level     = d["level"]
    mail_indicator = f" {emoji('mail')}" if has_unread_mail(user_id) else ""

    where_line = (travel_status_line(user_id) if is_traveling(user_id)
                  else f"{BIOME_NAMES[biome]} · {tool_name} · {hp_status_line(user_id)}")
    header = ui_header(emoji('bow'), f"{display_name} — Level {level}", where_line)

    xp_bar, xp_pct = ui_progress(d["xp"], xp_for_level(level))
    wallet_block = (
        f"{ui_money(d['money'])}    {emoji('gem')} **{d['gems']}**\n"
        f"XP {xp_bar} {xp_pct}"
    )

    ammo_name  = d.get("equipped_ammo")
    ammo_count = get_ammo_count(user_id, ammo_name) if ammo_name else 0
    ammo_line  = f"{ammo_emoji(ammo_name)} {ammo_name} ×{ammo_count}" if ammo_name else f"{ph(emoji('diamond_small'))} No ammo"
    vehicle_name = d.get("vehicle", "None")
    v_info       = VEHICLES.get(vehicle_name, {})
    equip_bits = [f"{tool_emoji(tool_name)} {tool_name}", ammo_line]
    if vehicle_name and vehicle_name != "None":
        equip_bits.append(f"{ph(v_info.get('emoji', emoji('jeep')))} {vehicle_name}")
    equip_block = f"\n-# {emoji('equipment')} Equipped: " + " · ".join(equip_bits)

    goal_block = ""
    _goals = three_goals_lines(user_id)
    if _goals:
        _goal_text = _goals[0].split("**Now:** ", 1)[-1]
        goal_block = f"\n\n{ph(emoji('target'))} **NEXT GOAL**\n{_goal_text}"

    now_bits = []
    _wc_here = active_world_condition(biome)
    if _wc_here and not is_traveling(user_id):
        now_bits.append(f"{BIOME_EMOJIS[biome]} {world_condition_line(biome)}")
    _sg_line = active_sighting_line()
    if _sg_line:
        now_bits.append(_sg_line)
    if get_active_event():
        now_bits.append(event_banner_line())
    stacks = d.get("idle", {}).get("stacks", 0)
    if stacks:
        idle_haul = idle_pending_preview(user_id)
        idle_cap  = idle_capacity(user_id)
        now_bits.append(f"{ph(emoji('package'))} Camp haul: **{idle_haul}/{idle_cap}**")
    now_block = ("\n\n" + "\n".join(f"-# {b}" for b in now_bits)) if now_bits else ""

    content = f"{header}\n\n{wallet_block}{equip_block}{goal_block}{now_block}"

    row1 = {"type": 1, "components": [
        {"type": 2, "style": 3, "label": "Hunt", "emoji": emoji_partial("bow"),
         "custom_id": f"hunt:again:{user_id}"},
        {"type": 2, "style": 2, "label": "World", "emoji": emoji_partial('earth'),
         "custom_id": f"nav:world:{user_id}"},
        {"type": 2, "style": 2, "label": "Shop", "emoji": emoji_partial("shop"),
         "custom_id": f"nav:shop:{user_id}"},
    ]}
    row2 = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Inventory", "emoji": emoji_partial("inventory"),
         "custom_id": f"nav:inv:{user_id}"},
        {"type": 2, "style": 2, "label": "Progress", "emoji": emoji_partial("achievements"),
         "custom_id": f"nav:progression:{user_id}"},
    ]}
    more_row = {"type": 1, "components": [{"type": 3,
        "custom_id": f"menu:nav:{user_id}",
        "placeholder": "More...",
        "min_values": 1, "max_values": 1, "flows": {},
        "options": [
            {"label": "Equipment",      "emoji": emoji_partial("equipment"),      "value": "equip",       "description": "Equip tools, ammo and vehicles"},
            {"label": "Quests",         "emoji": emoji_partial('quests'),                  "value": "quests",      "description": "Daily quest progress and rewards"},
            {"label": "Daily",          "emoji": emoji_partial("daily"),          "value": "daily",       "description": "Claim your daily reward"},
            {"label": "Camp",           "emoji": emoji_partial("idle_camp"),      "value": "idle",        "description": "Manage your Hunting Camp"},
            {"label": "Tribe",          "emoji": emoji_partial("tribe"),          "value": "tribe",       "description": "View your tribe"},
            {"label": "Crafting",       "emoji": {"name": "🔨"},                  "value": "craft",       "description": "Fuse shards into crystals & buy crates"},
            {"label": "Leaderboard",    "emoji": emoji_partial("leaderboard"),    "value": "leaderboard", "description": "View global leaderboards"},
            {"label": "Events",         "emoji": emoji_partial('earth'),                  "value": "events",      "description": "View ongoing global events"},
            {"label": "Gamble",         "emoji": emoji_partial("dice"),           "value": "gamble",      "description": "Try your luck at mini-games"},
            {"label": "Lottery",        "emoji": emoji_partial("lottery_ticket"), "value": "lottery",     "description": "Buy tickets for the daily lottery"},
            {"label": f"Mail{mail_indicator}", "emoji": emoji_partial("mail"),    "value": "mail",        "description": "Check your mailbox"},
            {"label": "Settings",       "emoji": emoji_partial("settings"),       "value": "settings",    "description": "Preferences and the hunter's guide"},
            {"label": "Updates",        "emoji": emoji_partial("list"),           "value": "update",      "description": "View latest updates"},
            {"label": "Collection",     "emoji": emoji_partial('book'),                  "value": "guide",       "description": "Species, Mythicals, trophies & world completion"},
            {"label": "Refer a Friend", "emoji": emoji_partial('handshake'),                  "value": "refer",       "description": "Your referral code — you both earn"},
        ]
    }]}

    menu_rows = [row1, row2, more_row]
    if hunters_path_active(user_id):
        menu_rows.append({"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Hunter's Path", "emoji": emoji_partial('world_map'),
             "custom_id": f"nav:hpath:{user_id}"},
        ]})

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 2},
        *menu_rows,
    ]}]

# ─────────────────────────────────────────────
# PROFILE PANEL
# ─────────────────────────────────────────────

def _viewing_other(target_id: str, viewer_id) -> bool:
    """True when ``viewer_id`` is a different person than the profile's owner."""
    return bool(viewer_id) and str(viewer_id) != str(target_id)

def _profile_owner_seg(target_id: str, viewer_id) -> str:
    """Trailing segment(s) of a profile/log custom_id. Carries the viewer id only
    on a cross-view (someone looking at another player) so the dispatch can keep
    the ◀ Menu button and the tab headers pointed at the right person."""
    return (f"{target_id}:{viewer_id}"
            if _viewing_other(target_id, viewer_id) else str(target_id))

def _profile_title(icon: str, name: str, noun: str, target_id: str, viewer_id) -> str:
    if _viewing_other(target_id, viewer_id):
        return f"### {emoji('eyes')} {name}'s {noun}"
    return f"### {icon} {name}'s {noun}"

def _profile_tab_rows(active: str, target_id: str, viewer_id=None) -> list:
    seg    = _profile_owner_seg(target_id, viewer_id)
    nav_id = viewer_id or target_id
    def _b(panel: str, label: str) -> dict:
        return {"type": 2, "style": 3 if active == panel else 1,
                "label": label, "custom_id": f"profile:{panel}:{seg}"}
    return [
        {"type": 1, "components": [_b("main", "Main Profile"),
                                   _b("inventory", "Inventory"),
                                   _b("statistics", "Statistics")]},
        {"type": 1, "components": [_b("leaderboard", "Rankings"),
                                   _b("log", "Hunting Log"),
                                   {"type": 2, "style": 2, "label": "◀ Menu",
                                    "custom_id": f"nav:menu:{nav_id}"}]},
    ]

def build_profile_components(user_id: str, display_name: str,
                              active_panel: str = "main", viewer_id: str = None) -> list:
    d         = data[user_id]
    boosts    = get_total_boosts(user_id)
    biome     = d.get("biome", "village")
    tool_name = d.get("tool", "Bare Hands")
    tribe_nm  = d.get("tribe")
    tribe_inv = d.get("tribe_inv")
    prestige  = d.get("prestige", 0)
    inv       = d.get("inv", [])
    sell_val  = inv_sell_value(user_id)

    idle      = d.get("idle", {})
    stacks    = idle.get("stacks", 0)
    idle_haul = idle_pending_preview(user_id)
    idle_cap  = idle_capacity(user_id)
    idle_camp_nm = BIOME_NAMES.get(idle_camp_biome(user_id), "Village")

    tribe_line  = f"**{tribe_nm}**" if tribe_nm else "None"
    if tribe_inv:
        tribe_line += f" *(invite: {tribe_inv})*"


    ammo_name   = d.get("equipped_ammo")
    ammo_count  = get_ammo_count(user_id, ammo_name) if ammo_name else 0
    ammo_line   = f"{ammo_emoji(ammo_name)} **{ammo_name}** ×{ammo_count}" if ammo_name else "None"

    vehicle_name = d.get("vehicle", "None")
    v_info       = VEHICLES.get(vehicle_name, {})
    vehicle_line = f"{ph(v_info.get('emoji', emoji('jeep')))} **{vehicle_name}**" if vehicle_name and vehicle_name != "None" else "None"

    badge_str      = get_badge_display(user_id)
    equipped_title = d.get("equipped_title")
    title_line     = f'`🏷️` *"{equipped_title}"*\n' if equipped_title else ""
    badge_line     = f"{badge_str}\n\n" if badge_str else ""
    gem_str        = gemstone_line(user_id)
    gem_disp       = f"{gem_str}\n" if gem_str else ""

    viewing_note = f"-# {emoji('eyes')} You're viewing another hunter's profile.\n" if _viewing_other(user_id, viewer_id) else ""
    tester_note  = f"-# {emoji('test_tube')} **TESTER ACCOUNT** — excluded from all leaderboards.\n" if d.get("is_tester") else ""
    stats = (
        f"{_profile_title(USER_EMOJIS['profile'], display_name, 'Profile', user_id, viewer_id)}\n"
        f"{viewing_note}"
        f"{tester_note}"
        f"{title_line}"
        f"{USER_EMOJIS['levels']} Lv. **{d['level']}** ({d['xp']:,}/{xp_for_level(d['level']):,} XP) · "
        f"{emoji('prestige')} Prestige **{prestige}**\n"
        f"{hp_status_line(user_id)} · **◈ {d['money']:,}** · {emoji('gem')} **{d['gems']}**\n"
        + (f"{travel_status_line(user_id)}\n"
           if is_traveling(user_id) else
           f"{BIOME_EMOJIS[biome]} **{BIOME_NAMES[biome]}** · {biome_region(biome)['region']}\n")
        + f"{tool_emoji(tool_name)} **{tool_name}** (T{get_tool_tier(tool_name)})\n"
        f"{ph(emoji('diamond_small'))} Ammo: {ammo_line}\n"
        f"{ph(emoji('jeep'))} Vehicle: {vehicle_line}\n"
        f"{TRIBE_EMOJIS['tribe']} {tribe_line}\n"
        f"{gem_disp}\n"
        f"{badge_line}"
        f"{emoji('luck')} Luck: + **{boosts['luck']}%** · "
        f"{emoji('sell_boost')} Sell: + **{boosts['sell']}%** · "
        f"{emoji('xp_boost')} XP: + **{boosts['xp']}%**\n\n"
        f"{emoji('idle_camp')} Camp: **{stacks}** hunter(s)"
        f"{f' · Haul {idle_haul}/{idle_cap} @ {idle_camp_nm}' if stacks else ''}\n\n"
        f"{emoji('inventory')} Inventory ({len(inv)} items · ◈ {sell_val:,}):\n"
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": stats},
        {"type": 14, "divider": True, "spacing": 1},
        *_profile_tab_rows(active_panel, user_id, viewer_id),
    ]}]

# ─────────────────────────────────────────────
# STATISTICS PANEL
# ─────────────────────────────────────────────

def build_statistics_components(user_id: str, display_name: str, viewer_id: str = None) -> list:
    d            = data[user_id]
    joined_str   = d.get("joined_date", today_utc())
    joined_fmt   = format_joined_date(joined_str)
    duration_str = hunting_duration_str(joined_str)
    streak       = d.get("daily_streak", 0)
    best_streak  = d.get("best_daily_streak", 0)
    nw           = net_worth(user_id)
    total_caught = d.get("total_caught", 0)
    total_earned = d.get("total_money_earned", 0)
    record       = d.get("record", {})
    s            = d.get("stats", {})

    animal_lines = []
    for animal, entry in sorted(record.items(), key=lambda x: x[1]["count"], reverse=True):
        animal_lines.append(f"-# {animal_emoji(animal)} **{entry['count']}×** {animal}")
    animal_block = "\n".join(animal_lines) if animal_lines else "-# No animals caught yet."

    content = (
        f"{_profile_title(USER_EMOJIS['stats'], display_name, 'Statistics', user_id, viewer_id)}\n\n"
        f"Started hunting on **{joined_fmt}**.\n"
        f"Have been hunting for {duration_str}.\n\n"
        f"{emoji('fire')} Current daily streak: **{streak}**\n"
        f"{emoji('trophy')} Best daily streak: **{best_streak}**\n\n"
        f"{emoji('money_bag')} Net worth: **◈ {nw:,}**\n"
        f"{emoji('package')} Total ◈ earned: **◈ {total_earned:,}**\n"
        f"{emoji('target')} Total animals caught: **{total_caught:,}**\n"
        f"{emoji('diamond_small')} Ammo used: **{s.get('ammo_used', 0):,}**\n"
        f"{emoji('dice')} Gamble wins — BJ: **{s.get('bj_wins',0):,}** · CF: **{s.get('cf_wins',0):,}** · "
        f"RL: **{s.get('rl_wins',0):,}** · RPS: **{s.get('rps_wins',0):,}** · "
        f"Slots: **{s.get('slots_wins',0):,}**\n"
        f"{emoji('lottery_ticket')} Lottery wins: **{s.get('lottery_wins',0):,}**\n\n"
        f"**Animals Caught:**\n{animal_block}"
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        *_profile_tab_rows("statistics", user_id, viewer_id),
    ]}]

# ─────────────────────────────────────────────
# INVENTORY PANEL
# ─────────────────────────────────────────────

_INV_MAX_PER_RARITY = 6

def build_inventory_components(user_id: str, display_name: str, viewer_id: str = None,
                                standalone: bool = False) -> list:
    """`standalone=True` is the dedicated Menu → Inventory screen (redesigned
    2026-09-15: rarity gives the list hierarchy instead of 15 equal-weight
    lines, and the footer is Sell All / Materials / Menu). `standalone=False`
    (the default) is unchanged — this same builder also renders the
    Inventory TAB inside /profile, where the footer must stay the profile
    tab row so Main/Statistics/Rankings/Log switching keeps working."""
    d           = data[user_id]
    inv         = d.get("inv", [])
    sell_value  = inv_sell_value(user_id)
    total_items = len(inv)

    if standalone:
        header = ui_header(emoji('inventory'), "INVENTORY",
                            f"{total_items} animal{'s' if total_items != 1 else ''} · worth {ui_money(sell_value)}")
        if not inv:
            content = header + "\n\n-# Inventory is empty. Go hunt something."
        else:
            counts    = Counter(inv)
            by_rarity: dict[str, list] = {}
            for a, c in counts.items():
                r = ANIMAL_DATA.get(a, {}).get("rarity", "common")
                by_rarity.setdefault(r, []).append((a, c))
            blocks = [header]
            for r in reversed(RARITY_KEYS):
                entries = by_rarity.get(r)
                if not entries:
                    continue
                entries.sort(key=lambda x: -x[1])
                shown = entries[:_INV_MAX_PER_RARITY]
                lines = [f"{RARITY_ICONS.get(r, '')} **{r.upper()}**"]
                lines += [f"• {animal_emoji(a)} {a} ×{c}" for a, c in shown]
                if len(entries) > _INV_MAX_PER_RARITY:
                    lines.append(f"-# +{len(entries) - _INV_MAX_PER_RARITY} more")
                blocks.append("\n".join(lines))
            content = "\n\n".join(blocks)
    else:
        if not inv:
            inventory_text = "-# Inventory is empty."
        else:
            counts    = Counter(inv)
            MAX_LINES = 15
            top       = counts.most_common(MAX_LINES)
            lines     = [f"-# {animal_emoji(a)} **{a}** ×{c}" for a, c in top]
            if len(counts) > MAX_LINES:
                hidden_types  = len(counts) - MAX_LINES
                hidden_items  = total_items - sum(c for _, c in top)
                lines.append(f"-# … +{hidden_items:,} more ({hidden_types} other type"
                             f"{'s' if hidden_types != 1 else ''})")
            inventory_text = "\n".join(lines)
        content = (
            f"{_profile_title(emoji('inventory'), display_name, 'Inventory', user_id, viewer_id)}\n"
            f"{emoji('inventory')} Total items: **{total_items}** · Worth: **◈ {sell_value:,}**\n\n"
            f"{inventory_text}"
        )

    trophies   = d.get("myth_items", {}) or {}
    troph_comps = []
    if trophies:
        t_count = len(trophies)
        equipped_n = len(equipped_trophy_names(user_id))
        slots_n    = trophy_slots_unlocked(user_id)
        troph_comps = [
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": f"Trophy Cabinet ({t_count} collected · {equipped_n}/{slots_n} equipped)",
                 "emoji": emoji_partial("trophy"), "custom_id": f"collection:trophies:{user_id}"},
            ]},
        ]

    if standalone:
        footer_rows = [
            {"type": 1, "components": [
                {"type": 2, "style": 1, "label": f"Sell All · {ui_money(sell_value)}",
                 "custom_id": f"hunt:sell_all:{user_id}"},
                {"type": 2, "style": 2, "label": "Materials", "emoji": emoji_partial('gem'),
                 "custom_id": f"nav:craft:{user_id}"},
            ]},
            ui_footer(user_id),
        ]
    else:
        footer_rows = list(_profile_tab_rows("inventory", user_id, viewer_id))

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        *troph_comps,
        {"type": 14, "divider": True, "spacing": 1},
        *footer_rows,
    ]}]

# ─────────────────────────────────────────────
# HUNT PANELS
# ─────────────────────────────────────────────

def build_hunt_components(user_id: str, result: dict) -> list:
    """Redesigned 2026-09-15: the old panel spent four separate '-#' lines on
    balance/HP/level/tool-and-ammo/inventory before a single catch was even
    shown. Condensed to one header line, one compact catch block per animal,
    one XP bar, one inventory line — plus the session continuity line, which
    is the one thing the old constantly-refreshing panel was missing."""
    d         = data[user_id]
    inv_count = len(d.get("inv", []))
    sell_val  = inv_sell_value(user_id)
    tool_name = result["tool"]

    # ── Tracking sequence — locate the creature before the fight (V2) ──
    if result.get("tracking_encounter") or tracking_active(user_id):
        return build_tracking_components(user_id)

    # ── Boss encounter — drop straight into the turn-based fight ──
    creature = result.get("myth_encounter") or (d.get("_boss") or {}).get("creature")
    if creature and creature in MYTHIC_CREATURES:
        return build_myth_fight_components(user_id, intro=True)

    ammo_name = result.get("ammo")
    if ammo_name:
        ammo_line = f"{ammo_emoji(ammo_name)} {ammo_name} ×{result.get('remaining_ammo', 0)}"
    else:
        ammo_line = "no ammo"
    hp, mx = player_hp(user_id)
    hp_ico = emoji("hp") or "❤️"
    header = ui_header(tool_emoji(tool_name), f"{result['biome_name'].upper()} HUNT",
                        f"{tool_name} · {ammo_line} · {hp_ico} {hp}/{mx}")

    total_xp_earned = 0
    total_sell_val  = 0
    catch_parts = []
    _share_animal = _share_rarity = None
    for c in result["catches"]:
        animal      = c["animal"]
        rarity      = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        rarity_icon = RARITY_ICONS.get(rarity, "")
        a_em        = animal_emoji(animal)
        total_xp_earned += c['xp_earned']
        total_sell_val  += c['sell_value']
        tag = ""
        if c.get("is_new_species"):
            tag = f"\n{ph('🆕')} **NEW SPECIES!**"
        elif c.get("is_personal_best"):
            tag = f"\n{ph(emoji('trophy'))} **Personal best!**"
        if c.get("is_first_rare"):
            tag += f"\n{ph('🌟')} **First rare catch!**"
        if c["is_rare"]:
            tag += f"\n{emoji('sparkles')} **Perfect Catch!**"
        catch_parts.append(
            f"{a_em} **{animal}**\n"
            f"-# {rarity_icon} {rarity.title()} · {ui_money(c['sell_value'])} · +{c['xp_earned']} XP"
            f"{tag}"
        )
        _pf = d.get("record", {}).get(animal, {}).get("count", 0) <= 1
        if _rarity_shareable(rarity, personal_first=_pf):
            _share_animal, _share_rarity = animal, rarity

    _biome_animals = BIOME_ANIMALS.get(result["biome"], [])
    _discovered    = sum(1 for a in _biome_animals if a in d.get("record", {}))
    xp_bar, xp_pct = ui_progress(result["xp"], result["xp_needed"])
    progress_block = (
        f"{ph(emoji('book'))} {result['biome_name']}  {_discovered}/{len(_biome_animals)} species\n"
        f"XP {xp_bar} {xp_pct}"
    )
    if result.get("level_ups"):
        ups = result["level_ups"]
        progress_block += (f"\n-# {USER_EMOJIS['level_up']} "
                            f"Level up{'×' + str(ups) if ups > 1 else ''}! Now level **{result['level']}**")

    extra_bits = []
    shard_drops = result.get("shard_drops") or {}
    crate_drops = result.get("crate_drops") or {}
    if shard_drops:
        got = " · ".join(f"{SHARD_ICONS.get(r,'')} {n}× {_rarity_label(r)} Shard"
                         for r, n in shard_drops.items())
        extra_bits.append(f"-# {emoji('gem')} Shard drop: {got}")
    if crate_drops:
        got = " · ".join(f"{CRATE_TIERS[n]['emoji']} {cnt}× **{n}**"
                         for n, cnt in crate_drops.items())
        extra_bits.append(f"-# {emoji('package')} Crate drop: {got}")
    auto_opened = result.get("auto_opened") or []
    if auto_opened:
        extra_bits.append(f"-# {emoji('crate_sample')} Auto-opened: " + " · ".join(auto_opened))
    _ae = result.get("animal_encounter")
    if _ae and _ae.get("kind") == "fled":
        extra_bits.append(f"-# `💨` A **{_ae['animal']}** caught your scent and bolted before you got close.")
    if _ae and _ae.get("kind") == "fight":
        return build_animal_fight_components(user_id, intro=True, extra_catches=result["catches"])
    extra_block = ("\n" + "\n".join(extra_bits)) if extra_bits else ""

    footer_bits = [f"{ph(emoji('inventory'))} {inv_count} animal{'s' if inv_count != 1 else ''} · worth {ui_money(sell_val)} "
                   f"· balance {ui_money(d['money'])}"]
    _sess_line = session_hunt_line(user_id)
    if _sess_line:
        footer_bits.append(_sess_line)
    footer_block = "\n".join(f"-# {b}" for b in footer_bits)

    content = (
        f"{header}\n\n"
        + "\n\n".join(catch_parts) + ("\n\n" if catch_parts else "")
        + progress_block + extra_block + "\n\n" + footer_block
    )

    btn_row1 = {"type": 1, "components": [
        {"type": 2, "style": 3, "label": "Hunt Again", "custom_id": f"hunt:again:{user_id}"},
        {"type": 2, "style": 1, "label": "Sell All",   "custom_id": f"hunt:sell_all:{user_id}"},
    ]}
    btn_row2 = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Inventory", "emoji": emoji_partial("inventory"),
         "custom_id": f"nav:inv:{user_id}"},
        {"type": 2, "style": 2, "label": "World", "emoji": emoji_partial('earth'),
         "custom_id": f"nav:world:{user_id}"},
    ]}

    comps = [
        {"type": 10, "content": content},
        {"type": 14, "divider": False, "spacing": 1},
        btn_row1, btn_row2,
    ]
    if _share_animal:
        _sid = make_share(user_id, "rare_catch", animal=_share_animal,
                          rarity=_share_rarity, biome=result.get("biome", ""),
                          personal_first=(d.get("record", {}).get(_share_animal, {}).get("count", 0) <= 1))
        _sr = _share_row(_sid, user_id, f"Show Off ({_share_rarity.title()})")
        if _sr:
            comps.append(_sr)
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]


_MYTH_TAUNTS = [
    "It hasn't blinked once.",
    "Every hair on your neck is standing up.",
    "This is what the stories were about.",
    "No trophy is worth this. (It absolutely is.)",
    "Somewhere, a folklorist is taking notes.",
]

def build_myth_fight_components(user_id: str, intro: bool = False) -> list:
    """The turn-based boss-fight panel: HP bars + a rolling combat log + actions."""
    b = _myth_fight_ensure(user_id)
    if not b:
        return build_menu_components(user_id, data[user_id].get("_display_name", "Hunter"))
    name  = b["creature"]
    c     = MYTHIC_CREATURES.get(name, {})
    ico   = creature_emoji(name)
    eid   = b.get("eid", "")
    mhp, mmax = b.get("mhp", 1), b.get("mhp_max", 1)
    php, pmax = player_hp(user_id)
    hp_ico = emoji("hp") or "❤️"

    if intro or not b.get("log"):
        _bonus_line = _TRACK_BONUS_BLURB.get(b.get("tracking_bonus", ""), "")
        log_txt = (f"-# {RARITY_ICONS.get('mythic','')} **You've run the {ico} {name} to ground!**\n"
                   f"-# {random.choice(_MYTH_TAUNTS)}"
                   + (f"\n-# {_bonus_line}" if _bonus_line else ""))
    else:
        log_txt = "\n".join(f"-# {ln}" for ln in b.get("log", []))

    # Mythics get the hardest visual break from normal browsing screens in
    # the whole bot — a boxed banner and a distinct dark accent, not just
    # another combat panel.
    body = (
        f"## {ico} {name.upper()}\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"**MYTHICAL ENCOUNTER** · Round {b.get('turn', 1)}\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"-# {c.get('aka', '')} · {c.get('behavior', '')}\n\n"
        f"{ico} **{name.upper()}**\n{mhp}/{mmax}\n{_hp_bar(mhp, mmax)}\n\n"
        f"{hp_ico} **YOU**\n{php}/{pmax}\n{_hp_bar(php, pmax)}\n\n"
        f"{log_txt}"
    )

    def _btn(a, style, disabled=False):
        return {"type": 2, "style": style, "label": FIGHT_ACTIONS[a]["label"],
                "emoji": _fa_partial(a), "disabled": disabled,
                "custom_id": f"hunt:fight:{a}:{eid}:{user_id}"}

    return [{"type": 17, "accent_color": 0x4B0082, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [_btn("punch", 2), _btn("kick", 4), _btn("defend", 3)]},
        {"type": 1, "components": [
            _btn("shoot", 1, disabled=not _myth_can_shoot(user_id)),
            _btn("taunt", 2), _btn("flee", 2)]},
    ]}]

# Back-compat: older callers pass a creature name.
def build_myth_encounter_components(user_id: str, creature: str = "") -> list:
    return build_myth_fight_components(user_id)


def build_myth_outcome_components(user_id: str, outcome: dict) -> list:
    d    = data[user_id]
    name = outcome.get("creature", "the creature")
    ico  = creature_emoji(name)
    kind = outcome.get("kind")

    if kind == "kill":
        lvl = ""
        if outcome.get("level_ups", 0) == 1:
            lvl = f"\n-# {USER_EMOJIS['level_up']} Level up! Now level **{outcome['level']}**"
        elif outcome.get("level_ups", 0) > 1:
            lvl = f"\n-# {USER_EMOJIS['level_up']} Level up ×{outcome['level_ups']}! Now level **{outcome['level']}**"
        shard_line = (f"\n-# {SHARD_ICONS['mythic']} Mythic Shard recovered — fuse it in `/craft`."
                      if outcome.get("myth_shard") else "")
        hp_left = outcome.get("php", 0)
        finish  = ("Not a scratch on you." if hp_left >= FIGHT_PLAYER_HP
                   else f"You walk away with **{hp_left} HP** to spare." if hp_left > 25
                   else "You're bleeding, but you're standing. It isn't.")
        first_line = ""
        if outcome.get("is_first_kill"):
            title_bit = f" · {emoji('label')} Title unlocked: **\"{outcome['first_title']}\"**" if outcome.get("first_title") else ""
            first_line = f"\n-# {emoji('party_popper')} **Your first Mythical kill ever.** This one's paying out big{title_bit}."
        drop = outcome.get("drop", "")
        eff  = TROPHY_EFFECTS.get(drop, {})
        if outcome.get("is_new_discovery") and eff:
            trophy_block = (
                f"\n\n### {emoji('trophy')} TROPHY UNLOCKED\n"
                f"**{drop}**\n"
                f"-# Effect while equipped: {eff['desc']}\n"
                f"-# Added to your Trophy Cabinet.{shard_line}"
            )
        elif drop:
            trophy_block = f"\n-# {emoji('trophy')} +1 **{drop}** (×{outcome.get('trophy_count', 1)} total){shard_line}"
        else:
            trophy_block = shard_line
        body = (
            f"### {ico} {name} — DOWN!\n"
            f"You beat the **{name}** into the dirt. {finish}\n"
            f"{first_line}"
            f"-# **+ ◈ {outcome['bounty']:,}** · **+ {emoji('gem')} {outcome.get('gems', 0):,}** · "
            f"**+ {outcome['xp']:,} XP**"
            f"{trophy_block}\n"
            f"-# Balance: **◈ {outcome['balance']:,}**{lvl}"
        )
        color = 0x2ECC71
    elif kind == "death":
        rescue = (f"\n-# {emoji('shield')} **Rookie Protection** kicked in — your first knockout is always a soft landing."
                  if outcome.get("rookie_save") else "")
        phoenix = (f"\n-# {emoji('fire')} **Everburning Ember** flared — you're back on your feet."
                  if outcome.get("phoenix_save") else "")
        _, _mx = player_hp(user_id)
        body = (
            f"### {ico} {name} — you're down.\n"
            f"It was faster, stronger, and hungrier. You went out swinging.\n"
            f"-# You lost **◈ {outcome['loss']:,}**.\n"
            f"-# {emoji('hp') or '❤️'} Recovered to **{outcome.get('hp', KO_RECOVERY_HP)}/{_mx}** HP.{rescue}{phoenix}\n"
            f"-# Balance: **◈ {outcome['balance']:,}**"
        )
        color = 0xE74C3C
    else:  # escape
        body = (
            f"### {ico} {name} — you ran.\n"
            + ("You slip away clean before it can turn.\n" if outcome.get("clean")
               else "It gets one last swipe in as you bolt — but you're gone.\n")
            + "-# No bounty, no trophy — but you live to hunt again."
        )
        color = 0xE67E22

    comps = [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Hunt",     "custom_id": f"hunt:again:{user_id}"},
            {"type": 2, "style": 1, "label": "Sell All", "custom_id": f"hunt:sell_all:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",   "custom_id": f"hunt:back:{user_id}"},
        ]},
    ]
    if kind == "kill":
        _sr = _share_row(outcome.get("share_id", ""), user_id, "Show Off This Kill")
        if _sr:
            comps.append(_sr)
    return [{"type": 17, "accent_color": color, "spoiler": False, "components": comps}]

def build_hunt_sold_components(user_id: str, sold: dict) -> list:
    if sold["count"] == 0:
        body = "### Inventory Sold\nYour inventory is empty.\n-# Nothing to sell."
    else:
        body = (
            f"### Inventory Sold\n"
            f"Sold **{sold['count']}** animals.\n"
            f"-# Earned **◈ {sold['total']:,}** · Balance: **◈ {data[user_id]['money']:,}**"
        )
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 3, "label": "Hunt",     "custom_id": f"hunt:again:{user_id}"},
        {"type": 2, "style": 1, "label": "Sell All", "custom_id": f"hunt:sell_all:{user_id}", "disabled": True},
        {"type": 2, "style": 2, "label": "◀ Back",   "custom_id": f"hunt:back:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

# ═══════════════════════════════════════════════════════════════
# ONBOARDING  ·  interactive first-hunt for brand-new players (V2 / V2.1)
# ═══════════════════════════════════════════════════════════════
# Steps: intro → catch → sell → trial → danger → pack → done. Every scripted
# panel is one screen with 1-3 buttons (custom_id "onb:<action>:<uid>") except
# "danger", which hands off to the REAL animal-fight engine
# (build_animal_fight_components / hunt:afight) so a new player is taught the
# actual system, not a throwaway lookalike.
#
# 2026-09-12: dropped "tracks" (a flavor-only follow/observe screen with no
# mechanical branching — pure filler between intro and catch), and "world" /
# "mystery" (full-screen explainers for world conditions and mythic creatures,
# shown before the player had even decided they like hunting). Both concepts
# are still teased in the "done" panel's goal list, and the real systems
# introduce themselves the moment they actually fire in play — no need to
# front-load the explanation. Six steps beats ten for a first-time player.
#
# Deliberate choice: don't give permanent gear or big money here. The first
# catch, the trial weapon's double-catch and the scripted fight all pay through
# the real inventory/sell/combat paths — no fake tutorial currency — but the
# Training Shortbow is a LOAN (data[uid]["trial_tool"], never added to
# owned_tools) that expires and dangles the real ◈25,000 purchase as a goal.
# Guarded so nothing here can be farmed (onboarding.completed / starter_pack /
# _onb_caught / trial_tool). Disable the whole flow with FEATURE_ONBOARDING_V2=0.

_ONB_STEPS = ("intro", "catch", "sell", "trial", "danger", "pack", "done")

# Steps retired in the 2026-09-12 simplification above. Kept recognized (not
# treated as corrupt data) purely so a player already mid-flow at deploy time
# gets fast-forwarded to the nearest equivalent instead of being reset to
# "intro" or stranded on a screen that no longer renders. See
# _onb_canonical_step(), used by every write (_onb_set_step) and by the one
# render entry point (build_onboarding_components).
_ONB_RETIRED_STEP_SKIP = {"tracks": "catch", "world": "done", "mystery": "done"}
_ONB_LEGACY_STEPS = tuple(_ONB_RETIRED_STEP_SKIP)

def _onb_canonical_step(step: str) -> str:
    """Map a retired step name forward to its replacement (idempotent)."""
    seen = set()
    while step in _ONB_RETIRED_STEP_SKIP and step not in seen:
        seen.add(step)
        step = _ONB_RETIRED_STEP_SKIP[step]
    return step

def onboarding_active(user_id: str) -> bool:
    if not FEATURE_ONBOARDING_V2:
        return False
    ob = data.get(user_id, {}).get("onboarding") or {}
    return not ob.get("completed", True)

def _onb(user_id: str) -> dict:
    return data[user_id].setdefault(
        "onboarding", {"version": 2, "completed": False, "step": "intro", "starter_pack": None})

def _onb_set_step(user_id: str, step: str) -> None:
    ob = _onb(user_id)
    ob["step"] = _onb_canonical_step(step)
    if ob["step"] == "done":
        ob["completed"] = True
    mark_user_dirty(user_id)

def _onb_first_animal() -> str:
    pool = BIOME_ANIMALS.get("village", [])
    for pick in ("Black-Tailed Deer", "Cottontail Rabbit"):
        if pick in pool:
            return pick
    return pool[0] if pool else "Black-Tailed Deer"

def _onb_grant_first_catch(user_id: str) -> tuple[str, int, int, int]:
    """Deliver the guaranteed first catch through the real inventory path.
    Also hands over one free Bandage — teaches healing exists before it's
    ever needed. Returns (animal, value, xp, level_ups)."""
    animal = _onb_first_animal()
    val = int(ANIMAL_DATA.get(animal, {}).get("value", 0)) or 120
    xp  = int(ANIMAL_DATA.get(animal, {}).get("xp", 0)) or 15
    d = data[user_id]
    level_ups = 0
    if not d.get("_onb_caught"):
        d["_onb_caught"] = True
        d.setdefault("inv", []).append(animal)
        d["_pending_sell"] = (d.get("_pending_sell") or 0) + val
        d["xp"] = d.get("xp", 0) + xp
        d["total_money_earned"] = d.get("total_money_earned", 0) + val
        record_catch(user_id, animal, d.get("tool", "Bare Hands"), val)
        while d["xp"] >= xp_for_level(d["level"]):
            d["xp"] -= xp_for_level(d["level"]); d["level"] += 1; level_ups += 1
        hi = d.setdefault("healing_inv", {})
        hi["Bandage"] = hi.get("Bandage", 0) + 1
        mark_user_dirty(user_id)
    return animal, val, xp, level_ups

def _onb_grant_trial_and_catches(user_id: str) -> tuple[list, dict]:
    """Loan the Training Shortbow (never added to owned_tools — see module
    docstring) and immediately deliver its signature double-catch, scripted
    so a brand new account with zero arrows never hits the ammo gate. Returns
    ([(animal,value,xp), ...], trial_tool_dict)."""
    d = data[user_id]
    tr = d.get("trial_tool")
    if not tr or tr.get("expires_at", 0) <= time.time():
        tr = {"tool": TRIAL_TOOL, "expires_at": time.time() + TRIAL_TOOL_MIN * 60}
        d["trial_tool"] = tr
    results = []
    if not d.get("_onb_trial_caught"):
        d["_onb_trial_caught"] = True
        pool = [a for a in BIOME_ANIMALS.get("village", []) if a != _onb_first_animal()]
        picks = pool[:2] if len(pool) >= 2 else (pool * 2)[:2]
        for animal in picks:
            val = int(ANIMAL_DATA.get(animal, {}).get("value", 0)) or 60
            xp  = int(ANIMAL_DATA.get(animal, {}).get("xp", 0)) or 12
            d.setdefault("inv", []).append(animal)
            d["_pending_sell"] = (d.get("_pending_sell") or 0) + val
            d["xp"] = d.get("xp", 0) + xp
            d["total_money_earned"] = d.get("total_money_earned", 0) + val
            record_catch(user_id, animal, TRIAL_TOOL, val)
            results.append((animal, val, xp))
        while d["xp"] >= xp_for_level(d["level"]):
            d["xp"] -= xp_for_level(d["level"]); d["level"] += 1
        mark_user_dirty(user_id)
    return results, tr

def _onb_start_scripted_danger(user_id: str) -> str:
    """The first dangerous encounter — real engine, favourably seeded so a new
    player is very likely to win in 1-2 clicks. Returns the animal name."""
    animal = "Western Coyote" if "Western Coyote" in BIOME_ANIMALS.get("village", []) \
        else BIOME_ANIMALS["village"][-1]
    refresh_health(user_id)
    stats = animal_combat_stats(animal)
    scripted_hp = max(8, int(stats["hp"] * 0.4))   # a couple of solid hits should do it
    data[user_id]["fight"] = {
        "kind": "animal", "animal": animal, "biome": "village",
        "eid": secrets.token_hex(4), "mhp": scripted_hp, "mhp_max": stats["hp"],
        "turn": 1, "guard": False, "log": [], "bonus": "ambush",
    }
    st = data[user_id].setdefault("stats", {})
    st["animal_fights_started"] = st.get("animal_fights_started", 0) + 1
    analytics(user_id, "onboarding_scripted_danger", animal=animal)
    mark_user_dirty(user_id)
    return animal

def _onb_after_scripted_danger(user_id: str, outcome: dict) -> list:
    """Route the scripted danger fight's outcome back into the guided flow —
    win, KO or flee, a new player is never left stranded mid-combat."""
    kind = outcome.get("kind")
    if kind == "win":
        _grant_title(user_id, "Rookie Hunter")
        hi = data[user_id].setdefault("healing_inv", {})
        hi["First Aid Kit"] = hi.get("First Aid Kit", 0) + 1
        mark_user_dirty(user_id)
        analytics(user_id, "onboarding_danger_won")
        data[user_id]["_onb_danger_note"] = "won"
    else:
        note = "ko" if kind == "ko" else "fled"   # 'escape' (flee) also reads as 'fled'
        analytics(user_id, "onboarding_danger_" + note)
        data[user_id]["_onb_danger_note"] = note
    _onb_set_step(user_id, "pack")
    return build_onboarding_components(user_id)

def _onb_grant_pack(user_id: str, key: str) -> bool:
    ob = _onb(user_id)
    if ob.get("starter_pack"):
        return False
    p = STARTER_PACKS.get(key)
    if not p:
        return False
    tb = data[user_id].setdefault("temp_boosts", [])
    expires_at = time.time() + p["duration"]
    for stat, amount in p["boosts"].items():
        tb.append({"stat": stat, "amount": amount, "expires_at": expires_at})
    data[user_id]["temp_boosts"] = [b for b in tb if b["expires_at"] > time.time()]
    ob["starter_pack"] = key
    mark_user_dirty(user_id)
    return True

def _onb_btn(uid: str, action: str, label: str, style: int = 3, emoji_uni: str = "") -> dict:
    b = {"type": 2, "style": style, "label": label, "custom_id": f"onb:{action}:{uid}"}
    if emoji_uni:
        em = emoji_partial(emoji_uni)
        if em:
            b["emoji"] = em
    return b

def build_onboarding_components(user_id: str) -> list:
    ob   = _onb(user_id)
    step = ob.get("step", "intro")
    if step in _ONB_LEGACY_STEPS:
        # Self-heal a step persisted before the 2026-09-12 simplification —
        # fast-forward instead of rendering a screen that no longer exists.
        _onb_set_step(user_id, step)
        step = ob["step"]
    acc  = 0x2ECC71

    if step in ("intro", ""):
        body = (
            f"# {emoji('bow')} IDLE HUNTER\n"
            "### The Pacific Northwest\n"
            "Rain drums on the cedars. Mist sits low between the trunks.\n\n"
            "Something just moved in the brush ahead of you.\n"
            "-# Every hunter starts here. Let's see what it is."
        )
        rows = [{"type": 1, "components": [_onb_btn(user_id, "track", "Track It", 3, "animal_fallback")]}]

    elif step == "catch":
        animal = _onb_first_animal()
        val = int(ANIMAL_DATA.get(animal, {}).get("value", 0)) or 120
        xp  = int(ANIMAL_DATA.get(animal, {}).get("xp", 0)) or 15
        a_em = animal_emoji(animal)
        body = (
            f"### {a_em} {animal}\n"
            "There it is — head down, grazing, unaware of you.\n"
            "Steady your hands. This is the shot.\n\n"
            f"-# Value: **◈ {val:,}** · XP: **+{xp}**"
        )
        rows = [{"type": 1, "components": [_onb_btn(user_id, "shoot", "Take the Shot", 3, "bow")]}]

    elif step == "sell":
        d = data[user_id]
        animal = _onb_first_animal()
        val = int(ANIMAL_DATA.get(animal, {}).get("value", 0)) or 120
        xp  = int(ANIMAL_DATA.get(animal, {}).get("xp", 0)) or 15
        a_em = animal_emoji(animal)
        lvl_line = (f"\n\n`⬆️` **LEVEL {d['level']}!**" if d.get("level", 1) > 1 else "")
        body = (
            f"### {emoji('target')} CLEAN HIT!\n"
            f"{a_em} **{animal}**\n\n"
            f"**+ {xp} XP** · **+ ◈ {val:,}**"
            f"{lvl_line}\n\n"
            f"{emoji('book')} **New Field Guide entry** — 1/{len(BIOME_ANIMALS.get('village', []))} "
            f"Pacific Northwest species discovered\n"
            f"{emoji('gift')} **+1 Bandage** (restores 25 HP — you'll want it later)\n\n"
            "-# A trader in the village will take the catch off your hands. Money "
            "buys better gear, and better gear reaches wilder places."
        )
        rows = [{"type": 1, "components": [_onb_btn(user_id, "sell", "Sell It", 1, "money_bag")]}]

    elif step == "trial":
        t_info = TOOLS.get(TRIAL_TOOL, {})
        body = (
            f"### {emoji('gift')} Training Loan\n"
            f"{t_info.get('emoji', emoji('bow'))} **Training {TRIAL_TOOL}** — yours for the next "
            f"**{TRIAL_TOOL_MIN} minutes**.\n\n"
            f"-# Multi-catch: **{t_info.get('multi_catch', 2)}** — it catches more than "
            f"one animal per hunt. Try it out."
        )
        rows = [{"type": 1, "components": [_onb_btn(user_id, "trial_hunt", "Hunt With It", 3, "bow")]}]

    elif step == "pack":
        lines = "\n".join(
            f"{p['emoji']} **{p['label']}** — {p['blurb']}"
            for p in STARTER_PACKS.values()
        )
        note = data[user_id].pop("_onb_danger_note", None)
        danger_line = ""
        if note == "won":
            danger_line = f"{emoji('trophy')} **First dangerous hunt won!** Title unlocked: *\"Rookie Hunter\"* · {emoji('gift')} First Aid Kit\n\n"
        elif note == "ko":
            danger_line = ("`💀` That one got the better of you — a ranger dragged you back. "
                           f"{emoji('shield')} Rookie Protection covered you. Nothing lost.\n\n")
        elif note == "fled":
            danger_line = "`💨` It got away. Nothing lost — on to the next one.\n\n"
        body = (
            f"{danger_line}"
            f"### {emoji('inventory')} Choose a Starting Specialty\n"
            "Pick the edge that suits how you want to play. It lasts 30 minutes — "
            "just enough to find your feet.\n\n" + lines
        )
        rows = [{"type": 1, "components": [
            _onb_btn(user_id, f"pack:{k}", STARTER_PACKS[k]["label"], 2, STARTER_PACKS[k]["emoji"])
            for k in STARTER_PACKS
        ]}]

    elif step == "danger":
        # Transient — the fight panel owns this step. Only reached on a stale
        # re-render (e.g. a refresh mid-fight); never leaves the player stuck.
        if data[user_id].get("fight"):
            return build_animal_fight_components(user_id)
        _onb_set_step(user_id, "pack")
        return build_onboarding_components(user_id)

    else:  # done
        pk = STARTER_PACKS.get(ob.get("starter_pack") or "", {})
        pk_line = (f"\n-# Active: {pk['emoji']} **{pk['label']}** ({pk['blurb'].split(' — ')[0]})"
                   if pk else "")
        real_price = TOOLS.get(TRIAL_TOOL, {}).get("price", 25000)
        body = (
            f"### {emoji('bow')} You're a Hunter Now\n"
            f"{USER_EMOJIS['levels']} Level **{data[user_id]['level']}** · "
            f"{hp_status_line(user_id)} · {emoji('book')} **{len(data[user_id].get('record', {}))}** species discovered · "
            f"**◈ {data[user_id]['money']:,}**\n"
            f"{pk_line}\n\n"
            "**Next goals:**\n"
            f"{emoji('bow')} Earn your real **{TRIAL_TOOL}** — ◈ {real_price:,}\n"
            f"{emoji('book')} Discover 5 Pacific Northwest species\n"
            f"{emoji('earth')} Investigate your first World Condition\n"
            f"`👹` Find your first Mythical Creature\n"
            f"{emoji('tribe')} Join or create a Tribe\n\n"
            f"{rookie_goals_block(user_id)}"
        )
        rows = [{"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Hunt Again", "emoji": emoji_partial('bow'),
             "custom_id": f"hunt:again:{user_id}"},
            {"type": 2, "style": 2, "label": "View the World", "emoji": emoji_partial('world_map'),
             "custom_id": f"nav:world:{user_id}"},
            {"type": 2, "style": 2, "label": "Find a Tribe", "emoji": emoji_partial('tribe'),
             "custom_id": f"nav:tribe:{user_id}"},
        ]}]

    if step not in ("done", "danger"):
        rows.append({"type": 1, "components": [
            {"type": 2, "style": 2, "label": "Skip intro",
             "custom_id": f"onb:skip:{user_id}"}]})

    return [{"type": 17, "accent_color": acc, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        *rows,
    ]}]

async def _maybe_onboard(interaction: discord.Interaction, user_id: str) -> bool:
    """If the player is mid-onboarding, (re)show the current step and return
    True so the caller stops. Safe to call from any command entry point."""
    if not onboarding_active(user_id):
        return False
    step = _onb(user_id).get("step", "intro")
    if (step not in _ONB_STEPS and step not in _ONB_LEGACY_STEPS) or step == "done":
        _onb_set_step(user_id, "intro")
    if not data[user_id].get("_onb_started"):
        data[user_id]["_onb_started"] = True
        analytics(user_id, "onboarding_started")
    await send_v2_followup(interaction, build_onboarding_components(user_id))
    return True

# ─────────────────────────────────────────────
# COLOR PANEL
# ─────────────────────────────────────────────

def build_color_panel_components(user_id: str) -> list:
    current    = data[user_id].get("color", "green")
    user_level = data[user_id].get("level", 1)
    custom_line = "Available now." if user_level >= 1200 else f"Unlocks at Level 1200 (you: {user_level})."
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": (
            f"### {emoji('palette')} Choose Your Color\n"
            f"Current: **{color_display_name(current)}**\n"
            f"-# Cosmetic only. No extra boosts, money, gems, etc."
        )},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "**Standard Colors**"},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"hunter_color_select:{user_id}",
            "placeholder": "Select a color...", "min_values": 1, "max_values": 1, "flows": {},
            "options": [{"label": COLOR_LABELS[k], "value": k,
                          "description": COLOR_DESCRIPTIONS[k], "default": k == current}
                        for k in COLORS.keys()]}]},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 9,
         "components": [{"type": 10, "content": f"**Custom Hex**\n{custom_line}"}],
         "accessory": {"type": 2, "style": 2, "label": "Set Custom Hex",
                        "custom_id": f"hunter_color_hex:{user_id}"}},
        _back_row(user_id),
    ]}]

# ─────────────────────────────────────────────
# BIOME PANEL
# ─────────────────────────────────────────────

def _travel_confirm_components(user_id: str, biome_key: str) -> list:
    """The ONE confirmation step every travel path funnels through — the biome
    select on /world, and the 'Travel Now' button on world-condition / global
    sighting announcements alike — so a stray click never commits a hunter to
    a multi-minute trip by accident."""
    mins = travel_time_min(data[user_id]["biome"], biome_key)
    r = biome_region(biome_key)
    trip_line = "You're already here — hunt away." if mins <= 0 else f"~{mins} min · no hunting or camp collection until you land."
    body = (
        f"### {emoji('plane')} Travel to {BIOME_EMOJIS.get(biome_key,'')} {BIOME_NAMES.get(biome_key, biome_key)}?\n"
        f"-# {r['region']}, {r['continent']}\n\n"
        f"{trip_line}"
    )
    return [{"type": 17, "accent_color": 0x3498DB, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Travel Now", "emoji": emoji_partial("plane"),
             "custom_id": f"travel:confirm:{biome_key}:{user_id}"},
            {"type": 2, "style": 2, "label": "Cancel",
             "custom_id": f"travel:cancel:{user_id}"},
        ]},
    ]}]

def _biome_select_row(user_id: str) -> dict:
    """The 'Travel to…' destination dropdown, shared by the World screen —
    travel used to live behind its own separate Biomes screen one click away;
    it's folded directly into World now so picking a destination doesn't
    redirect anywhere."""
    user_level    = data[user_id]["level"]
    current_biome = data[user_id]["biome"]
    tool_name     = data[user_id].get("tool", "Bare Hands")
    tool_tier     = get_tool_tier(tool_name)
    traveling     = is_traveling(user_id)

    options = []
    for biome_key, lvl_req in BIOME_LEVELS:
        r          = biome_region(biome_key)
        locked     = user_level < lvl_req
        needs_tool = tool_tier < BIOME_TOOL_TIER.get(biome_key, 1)
        mins       = travel_time_min(current_biome, biome_key)
        if locked:
            desc = f"{emoji('lock')} Unlocks at Level {lvl_req}"
        elif biome_key == current_biome:
            desc = f"`📍` You are here · {r['region']}"
        else:
            trip = "already here" if mins <= 0 else f"~{mins} min away"
            warn = f" · {emoji('warning')} needs a better tool" if needs_tool else ""
            desc = f"{r['region']} · {trip}{warn}"
        opt = {
            "label": f"{BIOME_NAMES[biome_key]}", "value": biome_key,
            "description": desc[:100],
            "default": biome_key == current_biome and not traveling,
        }
        # Select-option label/description are plain text — a custom emoji's
        # <:name:id> markup shows as literal text there, never an icon. The
        # only place a custom emoji actually renders on an option is this
        # dedicated `emoji` field.
        if locked:
            opt["emoji"] = emoji_partial("lock")
        else:
            em = emoji_partial(BIOME_EMOJIS.get(biome_key, ""))
            if em:
                opt["emoji"] = em
        options.append(opt)

    return {"type": 1, "components": [{"type": 3,
        "custom_id": f"biome:select:{user_id}",
        "placeholder": "Travel to…", "min_values": 1, "max_values": 1, "flows": {},
        "options": options}]}

def build_biome_panel_components(user_id: str) -> list:
    """Deprecated standalone Biomes screen — kept only so a stale message
    still holding an old nav:biome custom_id doesn't hard-error. New travel
    UI lives on the World screen itself (build_world_components)."""
    return build_world_components(user_id)

# ═══════════════════════════════════════════════════════════════
# WORLD SCREEN  ·  "what's happening out there right now" (V2, Phase 9)
# ═══════════════════════════════════════════════════════════════

def _world_region_rows(user_id: str) -> list[str]:
    cur = data[user_id].get("biome", "village")
    lvl = data[user_id].get("level", 1)
    rows = []
    for biome_key, lvl_req in BIOME_LEVELS:
        r = biome_region(biome_key)
        em = BIOME_EMOJIS.get(biome_key, "")
        here = " ← you are here" if biome_key == cur else ""
        if lvl < lvl_req:
            rows.append(f"{em} **{BIOME_NAMES[biome_key]}** — {emoji('lock')} Level {lvl_req}")
            continue
        cond = active_world_condition(biome_key)
        sight = _sighting_here(biome_key)
        if sight:
            rows.append(f"{em} **{BIOME_NAMES[biome_key]}** — {emoji('siren')} {sight}{here}")
        elif cond:
            spec = cond["spec"]
            hot = f" {emoji('fire')}" if spec.get("myth_mult", 1) > 1 or spec.get("rare_mult", 1) >= 1.3 else ""
            rows.append(f"{em} **{BIOME_NAMES[biome_key]}** — {spec['emoji']} {spec['name']}{hot}{here}")
        else:
            rows.append(f"{em} **{BIOME_NAMES[biome_key]}** — {r['region']} · Normal{here}")
    return rows

def build_world_components(user_id: str, goal_line: str = "") -> list:
    """The map is the star — redesigned 2026-09-15 to drop the full per-region
    list (10-13 lines of near-identical text) from the main screen. That list
    now lives behind 'All Regions'; this screen only shows where you are and
    what's actually happening right now."""
    d = data[user_id]
    cur = d.get("biome", "village")
    _rookie_goal_progress(user_id, "view_world")

    where = f"{BIOME_EMOJIS.get(cur,'')} **{BIOME_NAMES.get(cur, cur)}** — {biome_region(cur)['region']}"
    header = ui_header(emoji('earth'), "WORLD", where)

    now_bits = []
    if is_traveling(user_id):
        now_bits.append(travel_status_line(user_id))
    elif active_world_condition(cur):
        now_bits.append(world_condition_line(cur))
    if get_active_event():
        now_bits.append(event_banner_line())
    sg = active_sighting_banner()
    if sg:
        now_bits.append(sg)
    now_block = ("\n\n" + "\n\n".join(now_bits)) if now_bits else ""

    body = header + now_block
    if goal_line:
        body += f"\n\n{goal_line}"
    body += f"\n\n-# {ph('🧭')} Pick a destination below to travel — you leave at once and can't hunt until you arrive."

    comps = []
    _map = world_map_url()
    if _map:
        comps.append({"type": 12, "items": [{"media": {"url": _map}}]})
    comps += [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        _biome_select_row(user_id),
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Hunt", "emoji": emoji_partial("bow"),
             "custom_id": f"hunt:again:{user_id}"},
            {"type": 2, "style": 2, "label": "Collection", "emoji": emoji_partial('book'),
             "custom_id": f"guide:open:{user_id}"},
            {"type": 2, "style": 2, "label": "All Regions", "emoji": {"name": "🌐"},
             "custom_id": f"nav:allregions:{user_id}"},
        ]},
        ui_footer(user_id),
    ]
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

def build_world_regions_components(user_id: str) -> list:
    """The full biome-by-biome status list — every region's condition and
    lock state, one line each. Moved off the main World screen so that
    screen can stay a map, not a spreadsheet."""
    gc = guide_completion(user_id)
    header = ui_header("🌐", "ALL REGIONS")
    body = header + "\n\n" + "\n".join(_world_region_rows(user_id))
    body += (f"\n\n-# {emoji('book')} Field Guide: **{gc['world_pct']:.0f}%** of the world "
             f"({gc['species_have']}/{gc['species_total']} species · "
             f"{gc['myths_have']}/{gc['myths_total']} mythic)")
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        ui_footer(user_id, back=f"nav:world:{user_id}"),
    ]}]

# ═══════════════════════════════════════════════════════════════
# FIELD GUIDE PANEL  (V2, Phase 43-44)
# ═══════════════════════════════════════════════════════════════

def _collection_region_select(user_id: str, custom_id: str, selected: str) -> dict:
    opts = []
    for biome_key, lvl_req in BIOME_LEVELS:
        opts.append({
            "label": BIOME_NAMES[biome_key],
            "value": biome_key,
            "emoji": emoji_partial(BIOME_EMOJIS.get(biome_key, "")),
            "description": biome_region(biome_key).get("region", "") or None,
            "default": biome_key == selected,
        })
    for o in opts:
        if not o["description"]:
            o.pop("description")
    return {"type": 1, "components": [{"type": 3, "custom_id": custom_id,
            "placeholder": "Choose a region...", "min_values": 1, "max_values": 1,
            "options": opts}]}

def build_collection_components(user_id: str) -> list:
    """Collection hub — 2026-09-16 rework of the old Hunter's Field Guide.
    Trophies got their own tile here (see build_trophy_cabinet_components)
    since they're now equippable relics, not sellable junk."""
    gc = guide_completion(user_id)
    trophies_have = unique_trophies_count(user_id)
    earned = data[user_id].get("earned_titles", [])
    next_ms = next(((n, ttl) for n, ttl in GUIDE_TITLE_MILESTONES
                    if ttl not in earned and gc['world_pct'] < n), None)
    lines = [
        f"## {emoji('collection')} COLLECTION",
        f"-# World Completion: **{gc['world_pct']:.1f}%**",
        _guide_bar(int(gc['world_pct']), 100),
        "",
        f"{emoji('animal_fallback')} Species        **{gc['species_have']}** / {gc['species_total']}",
        f"{emoji('ghost')} Mythicals       **{gc['myths_have']}** / {gc['myths_total']}",
        f"{emoji('trophy')} Trophies        **{trophies_have}** / {gc['myths_total']}",
        f"{emoji('earth')} Regions         **{gc['regions_have']}** / {gc['regions_total']}",
    ]
    if next_ms:
        lines.append(f"\n-# Next reward: **{next_ms[0]}%** → *\"{next_ms[1]}\"*")

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": "\n".join(lines)},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "Species", "emoji": emoji_partial("animal_fallback"),
             "custom_id": f"collection:species:{user_id}"},
            {"type": 2, "style": 2, "label": "Mythicals", "emoji": emoji_partial("ghost"),
             "custom_id": f"collection:mythicals:{user_id}"},
        ]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "Trophies", "emoji": emoji_partial("trophy"),
             "custom_id": f"collection:trophies:{user_id}"},
            {"type": 2, "style": 2, "label": "Regions", "emoji": emoji_partial("earth"),
             "custom_id": f"collection:regions:{user_id}"},
        ]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Menu", "custom_id": f"nav:menu:{user_id}"},
        ]},
    ]}]

def build_collection_species_components(user_id: str, biome: str = None) -> list:
    biome = biome if biome in BIOME_NAMES else data[user_id].get("biome", "village")
    if biome not in BIOME_NAMES:
        biome = "village"
    rec     = data[user_id].get("record", {}) or {}
    species = _region_species(biome)
    have    = sum(1 for a in species if rec.get(a, {}).get("count", 0) > 0)
    lines = [f"## {BIOME_EMOJIS.get(biome,'')} {BIOME_NAMES[biome].upper()} COLLECTION",
             f"-# {have} / {len(species)} Species", ""]
    for a in species:
        entry  = rec.get(a)
        rarity = ANIMAL_DATA.get(a, {}).get("rarity", "common")
        if entry and entry.get("count", 0) > 0:
            lines.append(f"{emoji('check_mark')} {animal_emoji(a)} **{a}**")
            lines.append(f"-# Caught ×{entry['count']} · Best ◈{entry.get('best', 0):,}")
        else:
            lines.append(f"{emoji('black_question_mark_ornament')} Unknown Species")
            lines.append(f"-# {_rarity_label(rarity)}")
    comps = [
        {"type": 10, "content": "\n".join(lines)},
        {"type": 14, "divider": True, "spacing": 1},
        _collection_region_select(user_id, f"collection:species_sel:{user_id}", biome),
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Collection", "custom_id": f"collection:hub:{user_id}"},
        ]},
    ]
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

def build_collection_mythicals_components(user_id: str, biome: str = None) -> list:
    biome = biome if biome in BIOME_NAMES else data[user_id].get("biome", "village")
    if biome not in BIOME_NAMES:
        biome = "village"
    creatures = BIOME_MYTHS.get(biome, [])
    mr = data[user_id].get("myth_record", {}) or {}
    mi = data[user_id].get("myth_items", {}) or {}
    have = sum(1 for cr in creatures if mr.get(cr, {}).get("kills", 0) > 0)
    lines = [f"## {emoji('ghost')} {BIOME_NAMES[biome].upper()} MYTHICALS",
             f"-# {have} / {len(creatures)} discovered", ""]
    for name in creatures:
        entry = mr.get(name)
        drop  = MYTHIC_CREATURES.get(name, {}).get("drop", "")
        if entry and entry.get("kills", 0) > 0:
            lines.append(f"{emoji('check_mark')} {creature_emoji(name)} **{name.upper()}**")
            trophy_bit = f" · {emoji('trophy')} {drop} ×{mi.get(drop, 0)}" if drop else ""
            lines.append(f"-# Kills: {entry['kills']}{trophy_bit}")
        else:
            lines.append(f"{emoji('black_question_mark_ornament')} UNKNOWN CREATURE")
            lines.append(f"-# {emoji('earth')} {BIOME_NAMES[biome]} · Not discovered")
    comps = [
        {"type": 10, "content": "\n".join(lines)},
        {"type": 14, "divider": True, "spacing": 1},
        _collection_region_select(user_id, f"collection:mythicals_sel:{user_id}", biome),
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Collection", "custom_id": f"collection:hub:{user_id}"},
        ]},
    ]
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

def build_collection_regions_components(user_id: str) -> list:
    lines = [f"## {emoji('earth')} REGIONS", ""]
    for biome_key, lvl_req in BIOME_LEVELS:
        h, t = _guide_region_progress(user_id, biome_key)
        em = BIOME_EMOJIS.get(biome_key, "")
        tick = f" {emoji('check_mark')}" if (t and h >= t) else ""
        lines.append(f"{em} **{BIOME_NAMES[biome_key]}**  {h}/{t}{tick}")
    comps = [
        {"type": 10, "content": "\n".join(lines)},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "World", "emoji": emoji_partial('earth'), "custom_id": f"nav:world:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Collection", "custom_id": f"collection:hub:{user_id}"},
        ]},
    ]
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ─────────────────────────────────────────────
# TROPHY CABINET  ·  equippable mythic-trophy relics
# ─────────────────────────────────────────────

def _trophy_equip(user_id: str, slot_idx: int, trophy_name: str | None) -> None:
    eq = [t for t in (data[user_id].get("equipped_trophies", []) or []) if t]
    if trophy_name:
        eq = [t for t in eq if t != trophy_name]
    while len(eq) <= slot_idx:
        eq.append(None)
    eq[slot_idx] = trophy_name
    data[user_id]["equipped_trophies"] = [t for t in eq if t]
    mark_user_dirty(user_id)

def build_trophy_cabinet_components(user_id: str) -> list:
    owned    = data[user_id].get("myth_items", {}) or {}
    equipped = equipped_trophy_names(user_id)
    slots    = trophy_slots_unlocked(user_id)
    lines = [f"## {emoji('trophy')} TROPHY CABINET", f"-# Collected: {len(owned)} / {len(MYTHIC_CREATURES)}", ""]
    if slots:
        lines.append("**ACTIVE**")
        for i in range(slots):
            tname = equipped[i] if i < len(equipped) else None
            if tname and tname in TROPHY_EFFECTS:
                lines.append(f"{i+1}. {trophy_emoji(tname)} **{tname}**\n-# {TROPHY_EFFECTS[tname]['desc']}")
            else:
                lines.append(f"{i+1}. **— empty —**\n-# Use the Slot {i+1} button below to equip one.")
        next_th = next((t for t in TROPHY_SLOT_THRESHOLDS if t > len(owned)), None)
        if next_th:
            lines.append(f"\n-# Slot {slots+1} unlocks at **{next_th}** unique trophies.")
    else:
        lines.append("-# Slot 1 unlocks after your first Mythical kill.")
    comps = [{"type": 10, "content": "\n".join(lines)}, {"type": 14, "divider": True, "spacing": 1}]
    if slots:
        comps.append({"type": 1, "components": [
            {"type": 2, "style": 2, "label": f"Slot {i+1}", "custom_id": f"collection:slot:{i}:{user_id}"}
            for i in range(slots)
        ]})
    comps.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "View All", "custom_id": f"collection:trophies_all:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Collection", "custom_id": f"collection:hub:{user_id}"},
    ]})
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

def build_trophy_all_components(user_id: str) -> list:
    owned = data[user_id].get("myth_items", {}) or {}
    lines = [f"## {emoji('trophy')} ALL TROPHIES", f"-# {len(owned)} / {len(TROPHY_EFFECTS)} collected", ""]
    for trophy, eff in TROPHY_EFFECTS.items():
        tick = emoji('check_mark') if trophy in owned else emoji('black_question_mark_ornament')
        ico = trophy_emoji(trophy) if trophy in owned else emoji('black_question_mark_ornament')
        lines.append(f"{tick} {ico} **{trophy}** — {eff['creature']}")
        lines.append(f"-# {eff['desc']}")
    comps = [
        {"type": 10, "content": "\n".join(lines)},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Trophy Cabinet", "custom_id": f"collection:trophies:{user_id}"},
        ]},
    ]
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

def build_trophy_slot_picker_components(user_id: str, slot_idx: int) -> list:
    slots = trophy_slots_unlocked(user_id)
    if slot_idx < 0 or slot_idx >= slots:
        return build_trophy_cabinet_components(user_id)
    owned    = data[user_id].get("myth_items", {}) or {}
    equipped = equipped_trophy_names(user_id)
    current  = equipped[slot_idx] if slot_idx < len(equipped) else None
    lines = [f"## {emoji('trophy')} Trophy Cabinet — Slot {slot_idx + 1}",
             (f"-# Currently equipped: **{current}**" if current else "-# Choose a trophy to equip in this slot.")]

    options = [{"label": "— Unequip —", "value": "__none__", "default": current is None}]
    for tname in owned:
        eff = TROPHY_EFFECTS.get(tname, {})
        opt = {"label": tname[:100], "value": tname, "default": tname == current}
        if eff.get("desc"):
            opt["description"] = eff["desc"][:100]
        em = emoji_partial(trophy_emoji(tname))
        if em:
            opt["emoji"] = em
        options.append(opt)
    options = options[:25]   # Discord select cap — practically unreachable (34 trophies max)

    comps = [
        {"type": 10, "content": "\n".join(lines)},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 3, "custom_id": f"collection:slot_sel:{slot_idx}:{user_id}",
            "placeholder": "Select a trophy...", "min_values": 1, "max_values": 1, "options": options}]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Trophy Cabinet", "custom_id": f"collection:trophies:{user_id}"},
        ]},
    ]
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ─────────────────────────────────────────────
# EQUIP PANEL
# ─────────────────────────────────────────────

def build_equip_components(user_id: str) -> list:
    """Redesigned 2026-09-15: was a paragraph explaining ammo state, then a
    separate paragraph for vehicle state, each with its own dropdown and its
    own divider. Now one compact loadout summary up top, then Tool/Ammo/
    Vehicle each as a one-line label + its dropdown — no re-explaining how
    equipment works every time this opens."""
    owned    = data[user_id].get("owned_tools", ["Bare Hands"])
    equipped = data[user_id].get("tool", "Bare Hands")
    t_info   = TOOLS[equipped]
    ammo_type = t_info.get("ammo_type")

    equipped_ammo = data[user_id].get("equipped_ammo")
    ammo_count    = get_ammo_count(user_id, equipped_ammo) if equipped_ammo else 0
    a_info_eq     = AMMO.get(equipped_ammo, {})

    equipped_vehicle = data[user_id].get("vehicle", "None")
    v_info_eq        = VEHICLES.get(equipped_vehicle, {})

    loadout = [
        ui_header(emoji('settings'), "LOADOUT"),
        "",
        f"{tool_emoji(equipped)} **{equipped}** · Tier {get_tool_tier(equipped)}",
        f"{ph(emoji('target'))} {t_info['multi_catch']} catch{'es' if t_info['multi_catch'] != 1 else ''}/hunt",
        f"{USER_EMOJIS['luck_boost']} +{t_info['boost_luck']}% Luck · "
        f"{USER_EMOJIS['xp_boost']} +{t_info['boost_xp']}% XP",
    ]
    if ammo_type:
        if equipped_ammo and ammo_compatible_with_tool(equipped_ammo, equipped):
            loadout += [
                "",
                f"{ammo_emoji(equipped_ammo)} **{equipped_ammo}** ×{ammo_count}",
                f"{USER_EMOJIS['luck_boost']} +{a_info_eq.get('boost_luck',0)}% · "
                f"{USER_EMOJIS['sell_boost']} +{a_info_eq.get('boost_sell',0)}% · "
                f"{USER_EMOJIS['xp_boost']} +{a_info_eq.get('boost_xp',0)}%",
            ]
        else:
            loadout += ["", f"-# {emoji('warning')} No {AMMO_TYPE_LABELS.get(ammo_type,'ammo')} equipped — hunting blocked!"]
    if equipped_vehicle and equipped_vehicle != "None":
        cd_luck = f" · {USER_EMOJIS['luck_boost']} +{v_info_eq['boost_luck']}% Luck" if v_info_eq.get("boost_luck") else ""
        loadout += [
            "",
            f"{ph(v_info_eq.get('emoji', emoji('jeep')))} **{equipped_vehicle}**",
            f"`⏱️` -{v_info_eq.get('boost_cd',0)}s Hunt cooldown{cd_luck}",
        ]

    comps = [{"type": 10, "content": "\n".join(loadout)},
              {"type": 14, "divider": True, "spacing": 1}]

    equip_opts = [
        {"label": f"{n} (T{TOOLS[n]['tier']})", "emoji": emoji_partial(tool_emoji(n)),
         "value": n, "description": TOOLS[n]["description"], "default": n == equipped}
        for n in owned
    ]
    comps += [
        {"type": 10, "content": "**Tool**"},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"tools:equip:{user_id}",
            "placeholder": "Select tool to equip...", "min_values": 1, "max_values": 1,
            "flows": {}, "options": equip_opts}]},
    ]

    if ammo_type:
        user_ammo_inv = data[user_id].get("ammo_inv", {})
        compatible    = [
            name for name, a in AMMO.items()
            if a["ammo_type"] == ammo_type and user_ammo_inv.get(name, 0) > 0
        ]
        comps.append({"type": 10, "content": "**Ammo**"})
        if compatible:
            ammo_opts = [
                {"label": n, "emoji": emoji_partial(ammo_emoji(n)), "value": n,
                 "description": f"{AMMO[n]['description']} · Amount: {user_ammo_inv.get(n, 0)}",
                 "default": n == equipped_ammo}
                for n in compatible
            ]
            comps.append({"type": 1, "components": [{"type": 3,
                "custom_id": f"tools:ammo_equip:{user_id}",
                "placeholder": f"Select {AMMO_TYPE_LABELS.get(ammo_type, 'ammo')} to equip...",
                "min_values": 1, "max_values": 1, "flows": {},
                "options": ammo_opts[:25]}]})
        else:
            comps.append({"type": 10, "content":
                f"-# No {AMMO_TYPE_LABELS.get(ammo_type, 'ammo')} owned. Buy some in Shop → Ammo."})

    owned_vehicles = data[user_id].get("owned_vehicles", [])
    comps.append({"type": 10, "content": "**Vehicle**"})
    if owned_vehicles:
        vehicle_opts = [
            {"label": f"{VEHICLES[n]['emoji']} {n}", "value": n,
             "description": f"-{VEHICLES[n]['boost_cd']}s cooldown · T{VEHICLES[n]['tier']}",
             "default": n == equipped_vehicle}
            for n in owned_vehicles
        ]
        comps.append({"type": 1, "components": [{"type": 3,
            "custom_id": f"tools:vehicle_equip:{user_id}",
            "placeholder": "Select vehicle...", "min_values": 1, "max_values": 1,
            "flows": {}, "options": vehicle_opts[:25]}]})
    else:
        comps.append({"type": 10, "content": "-# No vehicles owned. Buy one in Shop → Vehicles."})

    comps.append({"type": 14, "divider": True, "spacing": 1})
    comps.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Shop", "emoji": emoji_partial("shop"),
         "custom_id": f"nav:shop:{user_id}"},
    ]})
    comps.append(ui_footer(user_id))
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ─────────────────────────────────────────────
# SHOP PANEL
# ─────────────────────────────────────────────

def _shop_price_str(n: int) -> str:
    """Exact with commas below 1M (500, 2,000) — short form above it (2.5M),
    matching how a player actually reads a price at each scale."""
    return f"{n:,}" if n < 1_000_000 else _short_num(n)

_SHOP_BOOST_ICONS = {"luck": "luck", "sell": "sell_boost", "xp": "xp_boost", "crate_luck": "crate_sample"}

def build_shop_components(user_id: str, tab: str = "boosts") -> list:
    d = data[user_id]
    _ev_note = (f"\n{ADMIN_BUFF_EVENT['emoji']} **Admin's Day Off** — every price is **50% off**"
                if admin_buff_active() else
                "\n-# `🦆` The ducks have taken the shop. They're letting you browse. For now."
                if active_event_key() == "duck" else "")
    shop_header = ui_header("🛒", "SHOP", f"{ui_money(d['money'])} · {emoji('gem')} {d['gems']}") + _ev_note

    tab_options = [
        {"label": "Boosts",   "emoji": emoji_partial('test_tube'), "value": "boosts",   "default": tab == "boosts"},
        {"label": "Tools",    "emoji": emoji_partial('wrench'), "value": "tools",    "default": tab == "tools"},
        {"label": "Ammo",     "emoji": emoji_partial('diamond_small'), "value": "ammo",     "default": tab == "ammo"},
        {"label": "Healing",  "emoji": emoji_partial('adhesive_bandage'), "value": "healing",  "default": tab == "healing"},
        {"label": "Vehicles", "emoji": emoji_partial('jeep'), "value": "vehicles", "default": tab == "vehicles"},
    ]
    tab_dropdown = {"type": 1, "components": [{"type": 3,
        "custom_id": f"shop:tab_dd:{user_id}",
        "placeholder": "Browse shop...",
        "min_values": 1, "max_values": 1, "flows": {},
        "options": tab_options,
    }]}

    if tab == "boosts":
        item_sections = []
        for name, item in SHOP_BOOST_ITEMS.items():
            boost_key = item.get("boost_key")
            icon      = emoji(_SHOP_BOOST_ICONS.get(boost_key, "")) or "🧪"
            bought    = shop_bought_count(d, name) if boost_key else 0
            maxed     = bought >= item["max_qty"]
            _pr       = ev_price(shop_boost_price(name, bought))
            price_line = (f"{emoji('check_mark')} Maxed" if maxed else
                          (f"{emoji('gem')} {_shop_price_str(_pr)}" if item["currency"] == "gems"
                           else f"◈ {_shop_price_str(_pr)}"))
            content   = (
                f"### {icon} {name}\n"
                f"{bought}/{item['max_qty']} · {price_line}\n"
                f"-# {item['description']}"
            )
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": {"type": 2, "style": 3,
                    "label": "Buy" if not maxed else "Maxed",
                    "custom_id": f"shop:buy:{name}:{user_id}",
                    "disabled": maxed},
            })
        comps  = [{"type": 10, "content": shop_header},
                  {"type": 14, "divider": True, "spacing": 1},
                  tab_dropdown,
                  {"type": 14, "divider": True, "spacing": 1},
                  *item_sections,
                  _back_row(user_id)]

    elif tab == "tools":
        owned      = d.get("owned_tools", ["Bare Hands"])
        equipped_t = d.get("tool", "Bare Hands")
        all_tools  = get_all_tools_sorted()
        page       = _tool_shop_page.get(user_id, 0)
        per_page   = 5
        total_pages = max(1, (len(all_tools) + per_page - 1) // per_page)
        page       = max(0, min(page, total_pages - 1))
        page_tools = all_tools[page * per_page:(page + 1) * per_page]
        item_sections = []
        for name, t in page_tools:
            already  = name in owned
            equipped = already and name == equipped_t
            _pr      = ev_price(t['price'])
            acc_emoji = None
            if already:
                status_line = f"{emoji('check_mark')} Owned" + (" · Equipped" if equipped else "")
                _mc = t.get("multi_catch", 1)
                detail_line = f"{_mc} catch{'es' if _mc != 1 else ''}/hunt"
                acc_label, acc_style, acc_dis = ("Equipped", 2, True) if equipped else ("Owned", 2, True)
            else:
                is_gems    = t["currency"] == "gems"
                balance    = d["gems"] if is_gems else d["money"]
                can_afford = balance >= _pr
                cur_icon   = emoji('gem') if is_gems else "◈"
                status_line = f"{cur_icon} {_shop_price_str(_pr)}"
                if can_afford:
                    detail_line = f"+{t['boost_luck']}% Luck · +{t['boost_xp']}% XP"
                    acc_label, acc_style, acc_dis = "Buy", 1, False
                else:
                    detail_line = f"You need {cur_icon} {_shop_price_str(_pr - balance)} more."
                    acc_label, acc_style, acc_dis = "Locked", 2, True
                    acc_emoji = emoji_partial("lock")
            content = (f"### {t['emoji']} {name}\n"
                       f"Tier {t['tier']} · {status_line}\n"
                       f"-# {detail_line}")
            accessory = {"type": 2, "style": acc_style,
                "label": acc_label,
                "custom_id": f"shop:tool_buy_acc:{name}:{user_id}",
                "disabled": acc_dis}
            if acc_emoji:
                accessory["emoji"] = acc_emoji
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": accessory,
            })
        page_nav_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev",
             "custom_id": f"shop:tool_prev:{user_id}", "disabled": page == 0},
            {"type": 2, "style": 2, "label": f"Page {page+1}/{total_pages}",
             "custom_id": f"shop:tool_noop:{user_id}", "disabled": True},
            {"type": 2, "style": 2, "label": "Next ▶",
             "custom_id": f"shop:tool_next:{user_id}", "disabled": page >= total_pages - 1},
        ]}
        comps = [{"type": 10, "content": shop_header},
                 {"type": 14, "divider": True, "spacing": 1},
                 tab_dropdown,
                 {"type": 14, "divider": True, "spacing": 1},
                 *item_sections,
                 {"type": 14, "divider": True, "spacing": 1},
                 page_nav_row,
                 _back_row(user_id)]

    elif tab == "ammo":
        grouped: dict[str, list[str]] = {}
        for name, a in AMMO.items():
            grouped.setdefault(a["ammo_type"], []).append(name)
        ammo_types    = list(grouped.keys())
        # Default to Bullets (Silver Bullet's group) rather than whatever
        # ammo_type happens to be first in AMMO — a player opening the shop
        # cold should land somewhere with a gem-tier item, not just Arrows.
        _default_page = ammo_types.index("bullet") if "bullet" in ammo_types else 0
        ammo_tab_page = _ammo_shop_page.get(user_id, _default_page)
        ammo_tab_page = max(0, min(ammo_tab_page, len(ammo_types) - 1))
        current_type  = ammo_types[ammo_tab_page]
        compat_tools  = ", ".join(AMMO_TYPE_TOOLS.get(current_type, []))
        # A player buying ammo for the wrong tool is a common frustration —
        # the ammo TYPE and its compatible tools get their own bold heading,
        # not folded into the wallet line.
        category_block = (
            f"## {AMMO_TYPE_LABELS[current_type]}\n"
            f"-# Fits: **{compat_tools}**"
        )
        item_sections = []
        for name in grouped[current_type]:
            a         = AMMO[name]
            owned_qty = d.get("ammo_inv", {}).get(name, 0)
            _pr       = ev_price(a['price'])
            ps        = (f"◈ {_shop_price_str(_pr)}/shot" if a["currency"] == "money"
                         else f"{emoji('gem')} {_shop_price_str(_pr)}/shot")
            boosts_s  = f"+{a['boost_luck']}% Luck · +{a['boost_sell']}% Sell · +{a['boost_xp']}% XP"
            content   = (
                f"### {a['emoji']} {name}\n"
                f"Owned: **{owned_qty}** · {ps}\n"
                f"-# {boosts_s}"
            )
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": {"type": 2, "style": 1, "label": "Buy",
                    "custom_id": f"shop:ammo_buy_acc:{name}:{user_id}"},
            })
        type_nav_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev Type",
             "custom_id": f"shop:ammo_prev:{user_id}", "disabled": ammo_tab_page == 0},
            {"type": 2, "style": 2, "label": f"Page {ammo_tab_page + 1}/{len(ammo_types)}",
             "custom_id": f"shop:ammo_noop:{user_id}", "disabled": True},
            {"type": 2, "style": 2, "label": "Next Type ▶",
             "custom_id": f"shop:ammo_next:{user_id}",
             "disabled": ammo_tab_page >= len(ammo_types) - 1},
        ]}
        comps = [{"type": 10, "content": shop_header},
                 {"type": 14, "divider": True, "spacing": 1},
                 tab_dropdown,
                 {"type": 14, "divider": True, "spacing": 1},
                 {"type": 10, "content": category_block},
                 {"type": 14, "divider": False, "spacing": 1},
                 *item_sections,
                 {"type": 14, "divider": True, "spacing": 1},
                 type_nav_row,
                 _back_row(user_id)]

    elif tab == "healing":
        header = f"{shop_header}\n{hp_status_line(user_id)}"
        item_sections = []
        for name, it in HEALING_ITEMS.items():
            owned_qty = d.get("healing_inv", {}).get(name, 0)
            _pr = ev_price(it["price"])
            content = (f"### {it['emoji']} {name}\n"
                      f"Owned: **{owned_qty}** · ◈ {_shop_price_str(_pr)}\n"
                      f"-# Restores **{it['heal']} HP**. Use it mid-fight or from your inventory.")
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": {"type": 2, "style": 1, "label": "Buy",
                    "custom_id": f"shop:heal_buy:{name}:{user_id}"},
            })
        comps = [{"type": 10, "content": header},
                 {"type": 14, "divider": True, "spacing": 1},
                 tab_dropdown,
                 {"type": 14, "divider": True, "spacing": 1},
                 *item_sections,
                 _back_row(user_id)]

    else:  # vehicles
        owned_v      = data[user_id].get("owned_vehicles", [])
        equipped_v   = data[user_id].get("vehicle", "None")
        all_vehicles = list(VEHICLES.items())
        page         = _vehicle_shop_page.get(user_id, 0)
        per_page     = 5
        total_pages  = max(1, (len(all_vehicles) + per_page - 1) // per_page)
        page         = max(0, min(page, total_pages - 1))
        page_vehicles = all_vehicles[page * per_page:(page + 1) * per_page]
        item_sections = []
        for name, v in page_vehicles:
            already  = name in owned_v
            is_equip = name == equipped_v
            _pr      = ev_price(v['price'])
            cd_str   = f"-{v['boost_cd']}s cooldown"
            luck_str = f" · +{v['boost_luck']}% Luck" if v["boost_luck"] else ""
            if is_equip:
                status_line, detail_line = f"{emoji('check_mark')} Equipped", f"{cd_str}{luck_str}"
            elif already:
                status_line, detail_line = f"{emoji('package')} Owned", f"{cd_str}{luck_str}"
            else:
                is_gems    = v["currency"] == "gems"
                balance    = d["gems"] if is_gems else d["money"]
                can_afford = balance >= _pr
                cur_icon   = emoji('gem') if is_gems else "◈"
                status_line = f"{cur_icon} {_shop_price_str(_pr)}"
                detail_line = (f"{cd_str}{luck_str}" if can_afford
                               else f"You need {cur_icon} {_shop_price_str(_pr - balance)} more.")
            content  = (
                f"### {v['emoji']} {name}\n"
                f"Tier {v['tier']} · {status_line}\n"
                f"-# {detail_line}"
            )
            acc_emoji = None
            if not already:
                is_gems    = v["currency"] == "gems"
                can_afford = (d["gems"] if is_gems else d["money"]) >= _pr
                if can_afford:
                    acc_label, acc_style, acc_dis = "Buy", 1, False
                else:
                    acc_label, acc_style, acc_dis = "Locked", 2, True
                    acc_emoji = emoji_partial("lock")
                acc_cid = f"shop:vehicle_buy_acc:{name}:{user_id}"
            elif not is_equip:
                acc_label, acc_style, acc_dis = "Equip",  3, False
                acc_cid = f"shop:vehicle_equip_acc:{name}:{user_id}"
            else:
                acc_label, acc_style, acc_dis = "Equipped", 2, True
                acc_cid = f"shop:vehicle_noop:{user_id}"
            accessory = {"type": 2, "style": acc_style, "label": acc_label,
                "custom_id": acc_cid, "disabled": acc_dis}
            if acc_emoji:
                accessory["emoji"] = acc_emoji
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": accessory,
            })
        page_nav_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev",
             "custom_id": f"shop:vehicle_prev:{user_id}", "disabled": page == 0},
            {"type": 2, "style": 2, "label": "Next ▶",
             "custom_id": f"shop:vehicle_next:{user_id}", "disabled": page >= total_pages - 1},
        ]}
        comps = [{"type": 10, "content": shop_header},
                 {"type": 14, "divider": True, "spacing": 1},
                 tab_dropdown,
                 {"type": 14, "divider": True, "spacing": 1},
                 *item_sections,
                 {"type": 14, "divider": True, "spacing": 1},
                 page_nav_row,
                 _back_row(user_id)]

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ─────────────────────────────────────────────
# TUTORIAL PANELS
# ─────────────────────────────────────────────

TUTORIAL_GUIDE: list[tuple[str, str]] = [
    ("Hunt", (
        f"### {emoji('bow')} Start hunting!\n"
        "Use `/hunt` or the **Hunt** button on `/menu` to go hunting in your current biome.\n"
        "-# Hunting has a short cooldown between tries."
    )),
    ("Sell", (
        f"### {emoji('money_bag')} Cash in your catch!\n"
        "Hit **Sell All** on the hunt screen to turn everything in your bag into ◈.\n"
        "-# Sell boost increases how much ◈ you get per animal."
    )),
    ("Biome", (
        f"### {emoji('world_map')} Try a new biome!\n"
        "Better biomes have rarer animals and higher payouts.\n"
        "Use `/world` → **Travel** to switch once you level up.\n"
        "-# Each biome has a minimum level and tool tier requirement."
    )),
    ("Tools", (
        f"### {emoji('equipment')} Upgrade your tool!\n"
        "Better tools catch more animals per hunt and boost XP.\n"
        "Open `/shop` → Tools to see what's available.\n"
        "-# Higher tier tools unlock higher tier biomes."
    )),
    ("Ammo", (
        f"### {emoji('diamond_small')} Some tools need ammo!\n"
        "Buy ammo in `/shop` → Ammo, then equip via `/equip`.\n"
        "-# Running out of ammo mid-hunt will block hunting."
    )),
    ("Equip", (
        f"### {emoji('settings')} Equip your gear!\n"
        "Purchases don't auto-equip — use `/equip` to switch tools and load ammo.\n"
        "-# Vehicles reduce your hunt cooldown."
    )),
    ("Daily", (
        f"### {emoji('daily')} Claim your daily!\n"
        f"Free ◈ or {emoji('gem')} every day — use `/daily`.\n"
        "-# Keep a streak for a bonus multiplier!"
    )),
    ("Hunting Camp", (
        f"### {emoji('idle_camp')} Set up a Hunting Camp!\n"
        "Use `/idle` to station hunters in a biome — they catch animals into a "
        "haul while you're away, and you collect it into your inventory.\n"
        "-# Pick a richer biome for better animals, and upgrade storage so the "
        "haul doesn't fill up while you're gone."
    )),
    ("Tribe", (
        f"### {emoji('tribe')} Join a tribe!\n"
        "Tribes share Luck, Sell, and XP boosts across all members.\n"
        "-# Use `/id` to get a friend's user ID."
    )),
    ("Prestige", (
        f"### {emoji('prestige')} Prestige is the endgame!\n"
        "Hit Level 1,000 and ◈ 1B? You can `/prestige` for a "
        "**permanent +20% to all boosts**.\n"
        "-# Tribe, badges and titles are kept on prestige — level, gear, boosts and "
        "materials reset, and gems are capped at 100."
    )),
]

def build_tutorial_guide_components(user_id: str, idx: int = 0) -> list:
    idx = max(0, min(idx, len(TUTORIAL_GUIDE) - 1))
    title, body = TUTORIAL_GUIDE[idx]
    content = f"{body}\n\n-# Step {idx + 1}/{len(TUTORIAL_GUIDE)} · {title}"
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev",
             "custom_id": f"tutorial_guide:nav:{idx - 1}:{user_id}", "disabled": idx == 0},
            {"type": 2, "style": 2, "label": "Next ▶",
             "custom_id": f"tutorial_guide:nav:{idx + 1}:{user_id}",
             "disabled": idx == len(TUTORIAL_GUIDE) - 1},
        ]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Settings",
             "custom_id": f"settings:nav:main:{user_id}"},
        ]},
    ]}]

def init_notif(user_id: str):
    n = data[user_id].setdefault("notif", {"daily_dm": False, "leaderboard_dm": False})
    n.setdefault("daily_dm",       False)
    n.setdefault("leaderboard_dm", False)

def build_settings_components(user_id: str) -> list:
    """Redesigned 2026-09-15: each setting used to be text block + button row
    + divider — three components apiece. Now one section per setting, with
    the ON/OFF state itself as the clickable accessory."""
    init_notif(user_id)
    n = data[user_id]["notif"]
    header = ui_header(emoji('settings'), "SETTINGS")

    def _setting_section(key: str, icon: str, label: str, blurb: str, on: bool):
        content = f"{icon} **{label}**\n-# {blurb}"
        accessory = {"type": 2, "style": 3 if on else 2, "label": ui_status(on),
                     "custom_id": f"settings:toggle:{key}:{user_id}"}
        return ui_section(content, accessory)

    tips_on      = data[user_id].get("tips_enabled", True)
    auto_open_on = data[user_id].get("auto_open_crates", False)

    sections = [
        _setting_section("tips_enabled", emoji('tip'), "Hunt Tips",
                          "Occasional gameplay tips, at most once every 10 minutes.", tips_on),
        _setting_section("daily_dm", emoji('daily'), "Daily Reminder",
                          "DM you once your daily reward is ready to claim.", n["daily_dm"]),
        _setting_section("leaderboard_dm", emoji('leaderboard'), "Rank Alerts",
                          "DM you if you fall out of the global Top 3.", n["leaderboard_dm"]),
        _setting_section("auto_open_crates", emoji('crate_sample'), "Auto-Open Crates",
                          "Instantly open crates you find while hunting instead of stacking them in your inventory.",
                          auto_open_on),
    ]

    comps = [{"type": 10, "content": header}, {"type": 14, "divider": True, "spacing": 1}]
    for i, sec in enumerate(sections):
        if i > 0:
            comps.append({"type": 14, "divider": True, "spacing": 1})
        comps.append(sec)
    comps.append({"type": 14, "divider": True, "spacing": 1})
    comps.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Hunter's Guide", "emoji": emoji_partial("book"),
         "custom_id": f"settings:tutorial:{user_id}"},
    ]})
    comps.append(ui_footer(user_id))
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ─────────────────────────────────────────────
# RULES
# ─────────────────────────────────────────────

RULES_LINES_PER_PAGE = 15

def build_rules_components(user_id: str, page: int = 0) -> list:
    # Each rule = 3 lines (number+title, description, spacing)
    lines_per_rule = 3
    rules_per_page = max(1, RULES_LINES_PER_PAGE // lines_per_rule)
    total_pages = max(1, (len(RULES) + rules_per_page - 1) // rules_per_page)
    page = max(0, min(page, total_pages - 1))

    start = page * rules_per_page
    end   = start + rules_per_page
    page_rules = RULES[start:end]

    sections = []
    for num, title, desc in page_rules:
        sections.append({
            "type": 9,
            "components": [{"type": 10, "content": (
                f"**{num}. {title}**"
                f"{desc}\n"
            )}],
            "accessory": {
                "type": 2, "style": 2, "label": f"#{num}",
                "custom_id": f"rules:noop:{num}:{user_id}",  # ← num makes it unique
                "disabled": True,
            }
        })

    nav_row = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Prev",
         "custom_id": f"rules:prev:{user_id}", "disabled": page == 0},
        {"type": 2, "style": 2, "label": f"{page + 1}/{total_pages}",
         "custom_id": f"rules:noop2:{user_id}", "disabled": True},
        {"type": 2, "style": 2, "label": "Next ▶",
         "custom_id": f"rules:next:{user_id}", "disabled": page >= total_pages - 1},
    ]}

    return [{"type": 17, "accent_color": 0xE74C3C, "spoiler": False, "components": [
        {"type": 10, "content": f"### {emoji('quests')} Idle Hunter Rules\n-# Page {page + 1}/{total_pages} · {len(RULES)} rules total"},
        {"type": 14, "divider": True, "spacing": 1},
        *sections,
        {"type": 14, "divider": True, "spacing": 1},
        nav_row,
    ]}]

# ─────────────────────────────────────────────
# REMAINING PANELS (idle, daily, prestige, update, lottery, gamble, etc.)
# ─────────────────────────────────────────────

UPDATE_LINES_PER_PAGE = 15

def build_update_components(user_id: str, mode: str = "all", page: int = 0) -> list:
    global UPDATE

    if not UPDATE:
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {emoji('list')} Updates\n\n-# No updates posted yet."},
            {"type": 14, "divider": True, "spacing": 1},
            _back_row(user_id),
        ]}]

    if mode == "view":
        # Single update view
        update_id = page  # reuse page param as index
        update_id = max(0, min(update_id, len(UPDATE) - 1))
        u = UPDATE[update_id]
        date_str = f"<t:{int(u.get('date', 0))}:F>" if u.get('date') else "Unknown"
        content = (
            f"### {u['title']}\n"
            f"{u['message']}\n\n"
            f"-# By: `{get_username(u['moderator'])}`\n"
            f"-# {date_str}\n"
            f"-# ID: {update_id + 1}"
        )
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "◀ Back",
                 "custom_id": f"update:back_to_list:{user_id}"},
            ]},
        ]}]

    # List view — paginated
    # Build all section components first, then paginate by line count
    sections = []
    for i, u in enumerate(reversed(UPDATE)):
        actual_id = len(UPDATE) - i  # so ID still shows correctly (newest = highest ID)
        date_str = f"<t:{int(u.get('date', 0))}:R>" if u.get('date') else "Unknown"
        section = {
            "type": 9,
            "components": [{"type": 10, "content": (
                f"**{u['title']}**\n"
                f"-# By: `{get_username(u['moderator'])}`\n"
                f"-# {date_str} · ID: {actual_id}"
            )}],
            "accessory": {
                "type": 2, "style": 1, "label": "View",
                "custom_id": f"update:view:{len(UPDATE) - 1 - i}:{user_id}",
            }
        }
        sections.append(section)

    # Paginate: each section = 3 lines
    lines_per_section = 3
    sections_per_page = max(1, UPDATE_LINES_PER_PAGE // lines_per_section)
    total_pages = max(1, (len(sections) + sections_per_page - 1) // sections_per_page)
    page = max(0, min(page, total_pages - 1))

    start = page * sections_per_page
    end   = start + sections_per_page
    page_sections = sections[start:end]

    nav_row = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Prev",
         "custom_id": f"update:prev:{user_id}", "disabled": page == 0},
        {"type": 2, "style": 2, "label": f"{page + 1}/{total_pages}",
         "custom_id": f"update:noop:{user_id}", "disabled": True},
        {"type": 2, "style": 2, "label": "Next ▶",
         "custom_id": f"update:next:{user_id}", "disabled": page >= total_pages - 1},
    ]}

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": f"### {emoji('list')} Updates"},
        {"type": 14, "divider": True, "spacing": 1},
        *page_sections,
        {"type": 14, "divider": True, "spacing": 1},
        nav_row,
        {"type": 14, "divider": True, "spacing": 1},
        _back_row(user_id),
    ]}]


_upd_admin_page: dict[str, int] = {}
_UPD_ADMIN_PER_PAGE = 6

def build_update_admin_components(admin_id: str, page: int = 0, note: str = "") -> list:
    """Admin control panel for the developer update log — add / edit / delete via
    buttons + a modal, so nothing is typed as a slash-command argument."""
    total       = len(UPDATE)
    total_pages = max(1, (total + _UPD_ADMIN_PER_PAGE - 1) // _UPD_ADMIN_PER_PAGE)
    page        = max(0, min(page, total_pages - 1))
    _upd_admin_page[admin_id] = page

    header = (
        f"## {emoji('announcement')} Update Control\n"
        f"**Add Update** opens a form — type the title and the full message there. "
        f"New updates post to the announcements channel automatically.\n"
        f"-# {total} update(s) in the log · newest first"
    )
    if note:
        header += f"\n\n{note}"

    blocks: list = [{"type": 10, "content": header},
                    {"type": 14, "divider": True, "spacing": 1}]

    # newest first; index is the position in UPDATE (0 = oldest)
    order = list(range(total - 1, -1, -1))
    shown = order[page * _UPD_ADMIN_PER_PAGE:(page + 1) * _UPD_ADMIN_PER_PAGE]

    for idx in shown:
        u = UPDATE[idx]
        preview = (u.get("message", "") or "").replace("\n", " ")
        if len(preview) > 90:
            preview = preview[:90] + "…"
        blocks.append({
            "type": 9,
            "components": [{"type": 10, "content": (
                f"**#{idx + 1} · {u.get('title', '(untitled)')}**\n"
                f"-# {preview or '(no body)'}\n"
                f"-# <t:{int(u.get('date', 0))}:R> · by `{get_username(str(u.get('moderator', '')))}`"
            )}],
            "accessory": {"type": 2, "style": 2, "label": "Edit",
                          "custom_id": f"updadm:edit:{idx}:{admin_id}"},
        })

    if not shown:
        blocks.append({"type": 10, "content": "-# The log is empty. Hit **Add Update** to post the first one."})

    if shown:
        del_opts = [{
            "label": f"#{i + 1} · {UPDATE[i].get('title', '(untitled)')[:80]}",
            "value": str(i),
        } for i in shown]
        blocks.append({"type": 1, "components": [{"type": 3,
            "custom_id": f"updadm:delsel:{admin_id}",
            "placeholder": "🗑 Delete an update…",
            "min_values": 1, "max_values": 1, "flows": {}, "options": del_opts}]})

    blocks.append({"type": 1, "components": [
        {"type": 2, "style": 3, "label": "Add Update", "emoji": {"name": "➕"},
         "custom_id": f"updadm:add:{admin_id}"},
        {"type": 2, "style": 2, "label": "Refresh", "emoji": emoji_partial("refresh"),
         "custom_id": f"updadm:refresh:{admin_id}"},
    ]})
    if total_pages > 1:
        blocks.append({"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev",
             "custom_id": f"updadm:prev:{admin_id}", "disabled": page == 0},
            {"type": 2, "style": 2, "label": f"{page + 1}/{total_pages}",
             "custom_id": f"updadm:noop:{admin_id}", "disabled": True},
            {"type": 2, "style": 2, "label": "Next ▶",
             "custom_id": f"updadm:next:{admin_id}", "disabled": page >= total_pages - 1},
        ]})

    return [{"type": 17, "accent_color": 0x2ECC71, "spoiler": False, "components": blocks}]

def _apply_update_add(admin_id: str, title: str, message: str) -> dict:
    """Append a new update, persist, and fire the channel broadcast. Returns the entry."""
    global UPDATE, LATEST_UPDATE
    entry = {"title": title.strip(), "message": message.strip(),
             "moderator": str(admin_id), "date": int(time.time()), "id": len(UPDATE) + 1}
    UPDATE.append(entry)
    LATEST_UPDATE = UPDATE[-1]
    save_config()
    bot.loop.create_task(_broadcast_update(entry))
    return entry

def _apply_update_edit(admin_id: str, idx: int, title: str, message: str) -> None:
    global UPDATE, LATEST_UPDATE
    UPDATE[idx] = {"title": title.strip(), "message": message.strip(),
                   "moderator": str(admin_id), "date": int(time.time()), "id": idx + 1}
    LATEST_UPDATE = UPDATE[-1]
    save_config()

def _apply_update_delete(admin_id: str, idx: int) -> dict | None:
    """Remove UPDATE[idx], renumber, persist. Returns the removed entry or None."""
    global UPDATE, LATEST_UPDATE
    if not (0 <= idx < len(UPDATE)):
        return None
    removed = UPDATE.pop(idx)
    for i, up in enumerate(UPDATE, 1):
        up["id"] = i
    LATEST_UPDATE = UPDATE[-1] if UPDATE else {"title": "", "message": ""}
    save_config()
    admin_audit(admin_id, "update_delete", f"#{idx + 1} {removed.get('title', '')[:60]}")
    return removed

_quest_page: dict[str, int] = {}
 
QUESTS_PER_PAGE = 3   # how many quests shown per page
 
def _quest_section(q: dict, claim_prefix: str, user_id: str) -> dict:
    """One Discord section for a quest — a Claim accessory when it's ready,
    otherwise just its own compact progress block. Shared by the daily and
    weekly panels."""
    bar, pct_label = ui_progress(q["progress"], q["target"])
    done_tag = f"{ph(emoji('check_mark'))} " if q.get("completed") else ""
    reward_bits = [f"+{q['xp_reward']:,} XP"]
    if q.get("money_reward"):
        reward_bits.append(f"◈{q['money_reward']:,}")
    if q.get("gems_reward"):
        reward_bits.append(f"{emoji('gem')}{q['gems_reward']}")
    if q.get("crate_reward"):
        reward_bits.append(f"1× {q['crate_reward']}")
    content = (
        f"{done_tag}{q['icon']} {q['description']}\n"
        f"{bar} {q['progress']:,}/{q['target']:,} ({pct_label})\n"
        f"-# Reward: {' · '.join(reward_bits)}"
    )
    accessory = None
    if q.get("completed") and not q.get("claimed"):
        accessory = {"type": 2, "style": 3, "label": "CLAIM",
                     "custom_id": f"{claim_prefix}:{q['id']}:{user_id}"}
    return ui_section(content, accessory)


def build_quests_components(user_id: str, page: int = 0) -> list:
    """
    Build the /quests daily panel. Shows QUESTS_PER_PAGE quests per page with
    Prev / Next buttons, a Claim button per completed quest, and the lifetime
    daily-quest milestone track underneath.

    Rolls the daily queue itself (rather than relying on every caller to
    remember to) so every entry point — /quests daily, the menu button, the
    lambda-dispatch nav map — always sees a fresh batch.
    """
    quest_daily_roll_if_needed(user_id)
    d         = data[user_id]
    all_quests = d.get("quests", [])

    # Separate active from claimed (shown at bottom of last page)
    active  = [q for q in all_quests if not q.get("claimed")]
    claimed = [q for q in all_quests if q.get("claimed")]

    display = active   # show only active; claimed are hidden to reduce clutter

    total_pages = max(1, -(-len(display) // QUESTS_PER_PAGE))  # ceiling div
    page        = max(0, min(page, total_pages - 1))
    start       = page * QUESTS_PER_PAGE
    page_quests = display[start : start + QUESTS_PER_PAGE]

    from datetime import datetime, timezone
    next_reset_ts = int(
        datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        + 86400
    )

    total_today     = len(all_quests)
    completed_today = len(claimed) + sum(1 for q in active if q.get("completed"))
    header = ui_header(emoji('quests'), "DAILY QUESTS",
                        f"{completed_today}/{total_today} complete · resets <t:{next_reset_ts}:R>")

    quest_sections = [_quest_section(q, "quests:claim", user_id) for q in page_quests]
    if not quest_sections:
        quest_sections.append(ui_section(
            "-# No quests active right now.\n-# Come back tomorrow for a new batch!"))

    # Navigation row
    nav_buttons = []
    if page > 0:
        nav_buttons.append({
            "type": 2, "style": 2, "label": "◀",
            "custom_id": f"quests:page:{page - 1}:{user_id}",
        })
    nav_buttons.append({
        "type": 2, "style": 2,
        "label": f"Page {page + 1}/{total_pages}",
        "custom_id": f"quests:noop:{user_id}",
        "disabled": True,
    })
    if page < total_pages - 1:
        nav_buttons.append({
            "type": 2, "style": 2, "label": "▶",
            "custom_id": f"quests:page:{page + 1}:{user_id}",
        })

    components = [{"type": 10, "content": header},
                  {"type": 14, "divider": True, "spacing": 1}]
    for i, sec in enumerate(quest_sections):
        if i > 0:
            components.append({"type": 14, "divider": True, "spacing": 1})
        components.append(sec)
    components.append({"type": 14, "divider": True, "spacing": 1})
    components.append({"type": 1, "components": nav_buttons})

    # ── Lifetime milestone track ───────────────
    total_claimed = d["stats"].get("daily_quests_completed_total", 0)
    next_ms = next(((th, g) for th, g in DAILY_QUEST_MILESTONES if th > total_claimed), None)
    components.append({"type": 14, "divider": True, "spacing": 1})
    if next_ms:
        th, g = next_ms
        bar, pct_label = ui_progress(total_claimed, th)
        ms_body = (f"{emoji('gem')} **Milestone:** {total_claimed:,}/{th:,} daily quests completed (lifetime)\n"
                   f"{bar} {pct_label} — next reward: **+{g} gems**")
    else:
        th_last, g_last = DAILY_QUEST_MILESTONES[-1]
        ms_body = (f"{emoji('gem')} **Milestone:** {total_claimed:,} daily quests completed lifetime — "
                   f"every milestone claimed! (last: +{g_last} gems at {th_last:,})")
    components.append({"type": 10, "content": ms_body})

    components.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Weekly Quest ▶",
         "custom_id": f"quests:goweekly:{user_id}"},
    ]})
    components.append(ui_footer(user_id))

    return [{"type": 17, "accent_color": _accent(user_id),
             "spoiler": False, "components": components}]


def build_weekly_quests_components(user_id: str) -> list:
    """Build the /quests weekly panel — its own standalone screen, no
    pagination (QUESTS_PER_WEEK=2 never needs it)."""
    quest_weekly_roll_if_needed(user_id)
    d = data[user_id]

    weekly_all    = d.get("weekly_quests", [])
    weekly_active = [q for q in weekly_all if not q.get("claimed")]
    weekly_claimed_n = sum(1 for q in weekly_all if q.get("claimed"))
    weekly_reset_ts = int(d.get("weekly_quests_last_roll", time.time()) + WEEK_SECONDS)

    header = ui_header(emoji('quests'), "WEEKLY QUEST",
        f"{weekly_claimed_n}/{len(weekly_all)} complete · resets <t:{weekly_reset_ts}:R>")

    components = [{"type": 10, "content": header},
                  {"type": 14, "divider": True, "spacing": 1}]
    if not weekly_active:
        components.append(ui_section("-# No weekly quest active right now."))
    else:
        for i, q in enumerate(weekly_active):
            if i > 0:
                components.append({"type": 14, "divider": True, "spacing": 1})
            components.append(_quest_section(q, "wquests:claim", user_id))

    components.append({"type": 14, "divider": True, "spacing": 1})
    components.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Daily Quests",
         "custom_id": f"wquests:godaily:{user_id}"},
    ]})
    components.append(ui_footer(user_id))

    return [{"type": 17, "accent_color": _accent(user_id),
             "spoiler": False, "components": components}]
 
 

def _short_num(n: int) -> str:
    n = int(n)
    if n >= 1_000_000_000: return f"{n / 1_000_000_000:.1f}B".replace(".0", "")
    if n >= 1_000_000:     return f"{n / 1_000_000:.1f}M".replace(".0", "")
    if n >= 1_000:         return f"{n / 1_000:.1f}K".replace(".0", "")
    return str(n)

def _idle_biome_select(user_id: str) -> dict:
    lvl    = data[user_id]["level"]
    tier   = get_tool_tier(data[user_id].get("tool", "Bare Hands"))
    camp_b = idle_camp_biome(user_id)
    opts = []
    for biome_key, lvl_req in BIOME_LEVELS:
        tier_req = BIOME_TOOL_TIER.get(biome_key, 1)
        if lvl < lvl_req:
            desc = f"{emoji('lock')} Unlocks at Level {lvl_req:,}"
        elif tier < tier_req:
            desc = f"{emoji('warning')} Needs a Tier {tier_req}+ tool"
        else:
            desc = f"Lv {lvl_req:,}+ · tier-{tier_req} game"
        opts.append({"label": BIOME_NAMES[biome_key], "value": biome_key,
                     "description": desc, "default": biome_key == camp_b})
    return {"type": 1, "components": [{"type": 3,
        "custom_id": f"idle:biome:{user_id}",
        "placeholder": "🗺️ Move the camp to another biome...",
        "min_values": 1, "max_values": 1, "flows": {},
        "options": opts}]}

def build_idle_components(user_id: str) -> list:
    d       = data[user_id]
    idle    = d["idle"]
    hunters = idle.get("stacks", 0)
    camp_b  = idle_camp_biome(user_id)
    cap     = idle_capacity(user_id)
    haul_n  = len(idle.get("haul", []))
    active  = idle.get("active") and hunters > 0
    accent  = _accent(user_id)
    up_cur  = idle.get("capacity_upgrades", 0)

    if not active:
        first_cost = idle_cost_for_stack(hunters)
        body = (
            f"### {emoji('idle_camp')} Hunting Camp\n"
            f"{emoji('red_ball')} **No hunters stationed.**\n"
            f"-# Hire a hunter and they'll bring back animals from your camp biome "
            f"while you're away — you collect the haul into your inventory.\n\n"
            f"-# {emoji('world_map')} Camp biome: {BIOME_EMOJIS[camp_b]} **{BIOME_NAMES[camp_b]}**\n"
            f"-# {emoji('package')} Haul storage: **{haul_n}/{cap}**\n"
            f"-# Balance: **◈ {d['money']:,}**"
        )
        rows = []
        if haul_n:
            rows.append({"type": 1, "components": [
                {"type": 2, "style": 3, "label": f"Collect Haul ({haul_n})", "emoji": emoji_partial("inventory"),
                 "custom_id": f"idle:collect:{user_id}"}]})
        rows.append({"type": 1, "components": [
            {"type": 2, "style": 1, "label": f"👤 Hire Hunter (◈ {_short_num(first_cost)})",
             "custom_id": f"idle:hire:{user_id}"}]})
        rows.append(_idle_biome_select(user_id))
        rows.append(_back_row(user_id))
        return [{"type": 17, "accent_color": accent, "spoiler": False, "components": [
            {"type": 10, "content": body},
            {"type": 14, "divider": True, "spacing": 1},
            *rows,
        ]}]

    rate     = idle_catches_per_hour(user_id)
    haul_val = idle_haul_sell_value(user_id)
    full     = haul_n >= cap
    if full:
        fill_line = f"{emoji('warning')} **HAUL FULL** — your hunters are sitting idle! Collect to send them back out."
    else:
        ts = int(time.time() + idle_seconds_until_full(user_id))
        fill_line = f"{emoji('cooldown')} Haul fills <t:{ts}:R>"

    hire_cost     = idle_cost_for_stack(hunters)
    up_cost       = idle_capacity_upgrade_cost(up_cur)
    up_maxed      = up_cur >= IDLE_MAX_CAPACITY_UPGRADES
    hunters_maxed = hunters >= IDLE_MAX_HUNTERS

    body = (
        f"### {emoji('idle_camp')} Hunting Camp\n"
        f"{emoji('green_ball')} **{hunters}** hunter(s) camping in {BIOME_EMOJIS[camp_b]} **{BIOME_NAMES[camp_b]}**\n\n"
        f"{emoji('package')} **Haul: {haul_n}/{cap}**\n"
        f"-# {_progress_bar(haul_n, cap, width=14)}\n"
        f"{fill_line}\n\n"
        f"-# `📈` Rate: **~{rate:.1f} catches/hr**\n"
        f"-# {emoji('money_bag')} Haul value: **◈ {haul_val:,}** — goes to your inventory on collect\n"
        f"-# Balance: **◈ {d['money']:,}**"
    )
    btns = [
        {"type": 2, "style": 3, "label": f"Collect ({haul_n})", "emoji": emoji_partial("inventory"),
         "custom_id": f"idle:collect:{user_id}", "disabled": haul_n == 0},
        {"type": 2, "style": 1,
         "label": "👤 Hunters maxed" if hunters_maxed else f"👤 Hire (◈ {_short_num(hire_cost)})",
         "custom_id": f"idle:hire:{user_id}", "disabled": hunters_maxed},
        {"type": 2, "style": 1,
         "label": "Storage maxed" if up_maxed else f"+Storage (◈ {_short_num(up_cost)})",
         "emoji": emoji_partial('package'),
         "custom_id": f"idle:upgrade:{user_id}", "disabled": up_maxed},
    ]
    return [{"type": 17, "accent_color": accent, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": btns},
        _idle_biome_select(user_id),
        _back_row(user_id),
    ]}]

def build_idle_haul_result_components(user_id: str, result: dict) -> list:
    d      = data[user_id]
    camp_b = idle_camp_biome(user_id)

    if result["count"] == 0:
        body = (
            f"### {emoji('idle_camp')} Hunting Camp — Nothing to Collect\n"
            "Your hunters haven't brought anything back yet.\n"
            "-# Check again later, or station more hunters."
        )
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": body},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "◀ Back to Camp",
                 "custom_id": f"idle:camp:{user_id}"}]},
        ]}]

    lines = []
    for animal, e in sorted(result["per_animal"].items(), key=lambda kv: -kv[1]["value"]):
        rare_tag = f" · {e['rare']}{emoji('sparkles')}" if e["rare"] else ""
        lines.append(f"-# {animal_emoji(animal)} **{animal}** ×{e['count']}{rare_tag} · ◈ {e['value']:,}")

    lvl_line = ""
    if result["level_ups"] == 1:
        lvl_line = f"\n-# {USER_EMOJIS['level_up']} Level up! Now level **{d['level']}**"
    elif result["level_ups"] > 1:
        lvl_line = f"\n-# {USER_EMOJIS['level_up']} Level up ×{result['level_ups']}! Now level **{d['level']}**"

    inv_count = len(d.get("inv", []))
    sell_val  = inv_sell_value(user_id)
    body = (
        f"### {d.get('_display_name', 'Hunter')}'s Hunting Camp — Haul Collected\n"
        f"Your hunters brought back **{result['count']}** animals from "
        f"{BIOME_EMOJIS[camp_b]} **{BIOME_NAMES[camp_b]}**:\n"
        + "\n".join(lines)
        + f"\n\n**+ {result['total_xp']:,} XP · Sell Value: ◈ {result['total_val']:,}**"
        f"{lvl_line}\n"
        f"-# {emoji('inventory')} Inventory: **{inv_count}** · Sell value: **◈ {sell_val:,}**\n"
        f"-# ◈ **{d['money']:,}** · Level **{d['level']:,}** "
        f"({d['xp']:,}/{xp_for_level(d['level']):,})"
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": False, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Sell All", "emoji": emoji_partial("coin_sample"), "custom_id": f"hunt:sell_all:{user_id}"},
            {"type": 2, "style": 3, "label": "◀ Back to Camp", "custom_id": f"idle:camp:{user_id}"},
        ]},
    ]}]

def build_daily_components(user_id: str, claimed: bool = False,
                            reward_type: str = "", reward_amt: int = 0, streak: int = 0) -> list:
    last_date  = data[user_id].get("last_daily_date", "")
    already    = last_date == today_utc()
    cur_streak = data[user_id].get("daily_streak", 0)
    nxt_ts     = next_midnight_ts()
    if claimed:
        icon = "◈ " if reward_type == "money" else emoji("gem")
        body = (
            f"### {emoji('daily')} Daily Claimed!\n"
            f"You received **{icon}{reward_amt:,}**!\n"
            f"-# {emoji('fire')} Streak: **{streak}** days · +{streak}% bonus\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    elif already:
        body = (
            f"### {emoji('daily')} Daily\nAlready claimed today!\n"
            f"-# {emoji('fire')} Streak: **{cur_streak}** days\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    else:
        tier = get_daily_tier(data[user_id]["level"])
        body = (
            f"### {emoji('daily')} Daily Reward\nClaim your daily reward!\n"
            f"-# {emoji('fire')} Streak: **{cur_streak}** days · +{cur_streak}% bonus\n"
            f"-# {emoji('money_bag')} Possible: ◈ {tier['money_min']:,}–{tier['money_max']:,} "
            f"or {emoji('gem')}{tier['gems_min']}–{tier['gems_max']}\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    btns = []
    if not already and not claimed:
        btns.append({"type": 2, "style": 3, "label": "Claim Daily",
                     "custom_id": f"daily:claim:{user_id}"})
    btns.append({"type": 2, "style": 2, "label": "◀ Back",
                 "custom_id": f"nav:back:{user_id}"})
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": btns},
    ]}]

RESET_GEM_CAP = 100

def _shop_bought_map(d: dict) -> dict:
    """The player's per-item shop purchase counts, tracked separately from the
    boost total so boosts won from crates never count as purchases. Accounts that
    pre-date the tracker are migrated once, seeded from their current boosts (the
    old behaviour) so nobody's shop progress jumps."""
    m = d.get("shop_bought")
    if m is None:
        m = {}
        for name, item in SHOP_BOOST_ITEMS.items():
            if item.get("boost_key") and item.get("boost_amt"):
                m[name] = d.get("boosts", {}).get(item["boost_key"], 0) // item["boost_amt"]
        d["shop_bought"] = m
    return m

def shop_bought_count(d: dict, item_name: str) -> int:
    return int(_shop_bought_map(d).get(item_name, 0))

def apply_account_reset(user_id: str, prestige: bool = False) -> int:
    """Reset a hunter back to a fresh start. Gear/progression and personal +
    timed boosts are wiped and gems are capped at RESET_GEM_CAP; badges,
    achievements, titles, tribe, trophies and lifetime stats survive.
    prestige=True (the player-facing /prestige confirm) also advances the
    prestige count by one; prestige=False (admin "Reset Account") leaves the
    prestige count exactly as it was. Returns the new prestige count. Caller
    must run this inside a user_transaction."""
    d = data[user_id]
    # Log the wipe so the economy ledger still reconciles with balances in
    # circulation (otherwise reset money/gems just silently vanish from it).
    _old_money = int(d.get("money", 0))
    _old_gems  = int(d.get("gems", 0))
    _new_gems  = min(_old_gems, RESET_GEM_CAP)
    if _old_money > 0:
        log_economy_event(user_id, "reset wipe", -_old_money, 0)
    if _old_gems > _new_gems:
        log_economy_event(user_id, "reset wipe", -(_old_gems - _new_gems), _new_gems, currency="gems")
    d.update({
        "prestige": d.get("prestige", 0) + (1 if prestige else 0),
        "level": 1, "xp": 0, "money": 0,
        "gems": _new_gems,
        "inv": [], "biome": "village", "record": {}, "total_caught": 0,
        "_pending_sell": None, "_slots_biome": "village",
        # Wipe late-game state so a fresh level-1 hunter isn't still in
        # transit, mid-boss, or running a camp in an end-game biome.
        "travel": None, "_boss": None,
        # Personal + timed boosts are erased — a fresh run starts at +0%.
        "boosts": {"luck": 0, "sell": 0, "xp": 0}, "temp_boosts": [],
        "shop_bought": {},
        # Gear resets too — a fresh run starts back at Bare Hands,
        # not still kitted out with end-game tools/ammo/vehicle.
        "tool": "Bare Hands", "owned_tools": ["Bare Hands"],
        "ammo_inv": {}, "equipped_ammo": None,
        "vehicle": "None", "owned_vehicles": [],
        # Crafting materials wipe too — a fresh run doesn't keep a
        # stockpile of crates/shards/crystals from the last one.
        "crate_inv": {}, "shards": {}, "crystals": {}, "craft_queue": [],
        # Camp resets fully too — no hired hunters, no capacity upgrades,
        # same as a brand-new account.
        "idle": {
            "active":            False,
            "stacks":            0,
            "started_at":        0,
            "camp_biome":        "village",
            "haul":              [],
            "capacity_upgrades": 0,
        },
    })
    mark_user_dirty(user_id)
    return d["prestige"]

def build_prestige_components(user_id: str) -> list:
    level    = data[user_id]["level"]
    money    = data[user_id]["money"]
    gems     = data[user_id].get("gems", 0)
    current  = data[user_id].get("prestige", 0)
    next_p   = current + 1
    boost    = next_p * 20
    lvl_ok   = level >= PRESTIGE_MIN_LEVEL
    money_ok = money >= PRESTIGE_MIN_MONEY
    body = (
        f"### {emoji('prestige')} Prestige {next_p}\n"
        f"Current: **Prestige {current}** (+{current * 20}% all boosts)\n\n"
        f"**Requirements:**\n"
        f"-# {emoji('check_mark') if lvl_ok else emoji('cross_mark')} Level **{PRESTIGE_MIN_LEVEL:,}** (you: {level:,})\n"
        f"-# {emoji('check_mark') if money_ok else emoji('cross_mark')} **◈ {PRESTIGE_MIN_MONEY:,}** (you: ◈ {money:,})\n\n"
        f"**Reward:** +**{boost}%** permanent Luck, Sell & XP\n"
        f"Prestiging costs almost everything: your gems drop to **{min(gems, RESET_GEM_CAP):,}** at most "
        f"(currently {emoji('gem')} {gems:,}) and your personal boosts are erased. "
        f"Please re-think about your decision before you click **Prestige**.\n"
        f"-# Resets: Level/XP, Money, Gems (max {RESET_GEM_CAP}), Personal & Temporary Boosts, Tools, Ammo, Vehicle, "
        f"Animal Inventory, Biome, Field Guide, Total Caught, Travel, Camp (Hunters/Upgrades/Haul/Location), Crates/Materials\n"
        f"-# Kept: Prestige Bonus, Badges, Achievements, Titles, Tribe, Special Badges, "
        f"Lifetime Stats, Cosmetics, Hunt History"
    )
    btns = []
    if lvl_ok and money_ok:
        btns.append({"type": 2, "style": 4, "label": "Prestige", "emoji": emoji_partial('check_mark'),
                     "custom_id": f"prestige:confirm:{user_id}"})
    btns.append({"type": 2, "style": 2, "label": "◀ Back",
                 "custom_id": f"nav:back:{user_id}"})
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": btns},
    ]}]

def build_prestige_done_components(user_id: str, new_prestige: int) -> list:
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": (
            f"### {emoji('prestige')} Prestige {new_prestige}!\n"
            f"All progress reset. Welcome back, hunter.\n"
            f"-# Permanent bonus: +**{new_prestige * 20}%** to all boosts · "
            f"Gems: {emoji('gem')} {data[user_id].get('gems', 0):,}"
        )},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Menu", "custom_id": f"nav:menu:{user_id}"}
        ]},
    ]}]

def build_lottery_components(user_id: str) -> list:
    ld = lottery_data
    tickets = ld.get("tickets", {})
    my_tickets = tickets.get(user_id, 0)
    next_ts = ld.get("next_ts", 0)
    last_w = ld.get("last_winner")
    
    # Calculate ticket change from previous lottery
    last_total = ld.get("last_total_tickets", 0)
    current_total = sum(tickets.values())
    if last_total == 0:
        keyword = "no previous data of"
    elif current_total > last_total:
        increase = ((current_total - last_total) / last_total) * 100
        if increase <= 30:
            keyword = "more"
        elif increase <= 60:
            keyword = "some more"
        elif increase <= 90:
            keyword = "a lot more"
        else:
            keyword = "a GIGANTIC more (buyers says help) of"
    elif current_total < last_total:
        decrease = ((last_total - current_total) / last_total) * 100
        if decrease <= 30:
            keyword = "a bit fewer"
        elif decrease <= 60:
            keyword = "fewer to some degree"
        elif decrease <= 90:
            keyword = "a lot fewer"
        else:
            keyword = f"a GIGANTIC fewer (economy says help) of"
    else:
        keyword = "the same number of"
    
    last_line = (f"Last win: **◈ {last_w['won']:,}** by `{last_w['username']}`"
                  if last_w else "Last win: *None yet*")
    
    # Store for next comparison
    ld["last_total_tickets"] = current_total
    save_lottery(ld)
    
    content = (
        f"### {emoji('lottery_ticket')} Lottery\n{last_line}\n\n"
        f"Your tickets: **{my_tickets}**\n\n"
        f"Tickets cost: **◈ {LOTTERY_TICKET_COST:,}** each\n\n"
        f"There are currently {keyword} tickets compared to the previous lottery.\n\n"
        f"-# More tickets = better chance\n\n"
        f"-# Next lottery <t:{next_ts}:R>\n"
        f"-# Join the server in /invite to know more information about the winners!"
    )
    return [{"type": 17, "accent_color": 0xF1C40F, "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Buy Tickets", "emoji": emoji_partial("lottery_ticket"),
             "custom_id": f"lottery:buy:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"nav:menu:{user_id}"},
        ]},
    ]}]

# ─────────────────────────────────────────────
# CRATE PANEL
# ─────────────────────────────────────────────

def _fmt_reward(reward: dict) -> str:
    t = reward["type"]
    if t == "money":
        return f"◈ {reward['amount']:,}"
    if t == "gems":
        return f"{emoji('gem')} {reward['amount']:,}"
    if t == "perm_boost":
        stat_label = {"luck": "Luck", "sell": "Sell", "xp": "XP"}.get(reward["stat"], reward["stat"])
        return f"{emoji('sparkles')} **+{reward['amount']}% {stat_label}** (permanent!)"
    if t == "temp_boost":
        stat_label = {"luck": "Luck", "sell": "Sell", "xp": "XP"}.get(reward["stat"], reward["stat"])
        return f"{emoji('clock')} **+{reward['amount']}% {stat_label}** for {reward['minutes']} min"
    if t == "title":
        return f'`🏷️` Title: **"{reward["title"]}"**'
    return "???"

def _crystals_owned_line(user_id: str) -> str:
    have = [f"{CRYSTAL_ICONS[r]} {crystal_count(user_id, r)}"
            for r in RARITY_KEYS if crystal_count(user_id, r) > 0]
    return " · ".join(have) if have else "-# No crystals yet — craft them from shards in `/craft`."

def _crate_shop_sections(user_id: str) -> list:
    """The 6 type-9 crate rows (buy with crystals) — shared by the /craft screen."""
    inv = data[user_id].get("crate_inv", {})
    sections = []
    for name, crate in CRATE_TIERS.items():
        rarity = crate["rarity"]
        cost   = crate["crystal_cost"]
        have   = crystal_count(user_id, rarity)
        owned  = inv.get(name, 0)
        can    = have >= cost
        content = (
            f"{crate['emoji']} **{name}** — {CRYSTAL_ICONS[rarity]} {cost} "
            f"{_rarity_label(rarity)} Crystal{'s' if cost != 1 else ''} "
            f"(you have **{have}**) · Owned: **{owned}**\n"
            f"-# {crate['description']}"
        )
        sections.append({
            "type": 9,
            "components": [{"type": 10, "content": content}],
            "accessory": {"type": 2, "style": 1 if can else 2, "label": "Buy",
                "custom_id": f"crate:buy:{name}:{user_id}", "disabled": not can},
        })
    return sections

def build_crate_shop_components(user_id: str) -> list:
    # The crate shop now lives inside the /craft screen. Kept as a thin alias so
    # existing `crate:shop` buttons and cross-user panels still resolve.
    return build_craft_components(user_id)

def build_crate_open_menu_components(user_id: str) -> list:
    d = data[user_id]
    inv = d.get("crate_inv", {})
    owned = {k: v for k, v in inv.items() if v > 0}

    if not owned:
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {emoji('package')} Open Crates\n\n-# You don't own any crates.\n-# Buy some in `/craft`."},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "◀ Craft",
                 "custom_id": f"craft:open:{user_id}"},
            ]},
        ]}]

    options = [
        {"label": f"{CRATE_TIERS[n]['emoji']} {n} (×{v})", "value": n,
         "description": CRATE_TIERS[n]["description"]}
        for n, v in owned.items()
    ]

    inv_lines = "\n".join(
        f"-# {CRATE_TIERS[n]['emoji']} **{n}** ×{v}" for n, v in owned.items()
    )

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": f"### {emoji('package')} Open a Crate\n{inv_lines}"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"crate:open_select:{user_id}",
            "placeholder": "Select a crate to open...",
            "min_values": 1, "max_values": 1, "flows": {},
            "options": options,
        }]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Craft",
             "custom_id": f"craft:open:{user_id}"},
        ]},
    ]}]

def build_crate_result_components(user_id: str, crate_name: str, reward: dict,
                                  extras: dict | None = None) -> list:
    crate = CRATE_TIERS[crate_name]
    reward_str = _fmt_reward(reward)
    remaining = data[user_id].get("crate_inv", {}).get(crate_name, 0)
    extras = extras or {}

    bonus = ""
    if extras.get("gemstone"):
        r = extras["gemstone"]
        bonus += f"\n{GEMSTONE_ICONS.get(r, emoji('gem'))} **Bonus:** a {_rarity_label(r)} Gemstone!"

    content = (
        f"### {crate['emoji']} {crate_name} Opened!\n\n"
        f"You received:\n**{reward_str}**{bonus}\n\n"
        f"-# {crate_name} remaining: **{remaining}**"
    )

    btns = [{"type": 2, "style": 2, "label": "◀ Craft",
              "custom_id": f"craft:open:{user_id}"}]
    if remaining > 0:
        btns.insert(0, {"type": 2, "style": 3, "label": f"Open Another {crate_name}",
                         "custom_id": f"crate:open_again:{crate_name}:{user_id}"})

    return [{"type": 17, "accent_color": crate["color"], "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": btns},
    ]}]

# ─────────────────────────────────────────────
# CRAFT PANEL  ·  9 shards → 1 crystal (timed)
# ─────────────────────────────────────────────

def build_craft_components(user_id: str, notice: str = "") -> list:
    craft_tick(user_id)
    d = data[user_id]
    q = d.get("craft_queue", [])

    shard_lines = []
    for r in RARITY_KEYS:
        sc, cc = shard_count(user_id, r), crystal_count(user_id, r)
        if sc or cc:
            shard_lines.append(
                f"-# {SHARD_ICONS[r]} **{sc}** {_rarity_label(r)} Shard"
                f"{'s' if sc != 1 else ''} · {CRYSTAL_ICONS[r]} **{cc}** Crystal{'s' if cc != 1 else ''}"
            )
    mats = "\n".join(shard_lines) if shard_lines else "-# No shards or crystals yet — catch animals to find shards."

    header = (
        f"### {ph('🔨')} Craft\n"
        f"Fuse **{CRYSTAL_SHARD_COST}** shards into **1** crystal "
        f"(~{CRYSTAL_CRAFT_SECONDS // 60} min each, queued), then spend crystals on "
        f"crates below. Open crates with </use:{COMMAND_ID.get('use','0')}>.\n"
        f"{mats}"
    )
    if notice:
        header += f"\n\n{notice}"

    qsum = craft_queue_summary(user_id)
    if qsum:
        header += f"\n\n**In the forge ({len(q)}/{CRAFT_QUEUE_MAX}):**\n{qsum}"

    craftable = [r for r in RARITY_KEYS if shard_count(user_id, r) >= CRYSTAL_SHARD_COST]
    rows: list = [
        {"type": 10, "content": header},
        {"type": 14, "divider": True, "spacing": 1},
    ]
    if len(q) >= CRAFT_QUEUE_MAX:
        rows.append({"type": 10, "content": f"-# {emoji('warning')} The forge queue is full — wait for a crystal to finish."})
    elif craftable:
        opts = [{
            "label": f"{_rarity_label(r)} Crystal",
            "value": r,
            "description": f"Uses {CRYSTAL_SHARD_COST} of your {shard_count(user_id, r)} {_rarity_label(r)} shards",
            "emoji": emoji_partial(CRYSTAL_ICONS[r]) or None,
        } for r in craftable]
        for o in opts:
            if not o.get("emoji"):
                o.pop("emoji", None)
        rows.append({"type": 1, "components": [{"type": 3,
            "custom_id": f"craft:queue:{user_id}",
            "placeholder": "🔨 Fuse shards into a crystal…",
            "min_values": 1, "max_values": 1, "flows": {}, "options": opts}]})
    else:
        rows.append({"type": 10, "content": f"-# Need at least {CRYSTAL_SHARD_COST} shards of one rarity to craft a crystal."})

    rows.append({"type": 14, "divider": True, "spacing": 1})
    rows.append({"type": 10, "content": f"### {emoji('package')} Crate Shop\n{_crystals_owned_line(user_id)}"})
    rows.extend(_crate_shop_sections(user_id))

    rows.append({"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Refresh", "emoji": emoji_partial("refresh"), "custom_id": f"craft:open:{user_id}"},
        _back_row(user_id)["components"][0],
    ]})
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": rows}]

# ─────────────────────────────────────────────
# QUEST HELPERS
# ─────────────────────────────────────────────
 
def quest_daily_roll_if_needed(user_id: str):
    """
    If the player hasn't received their daily quest batch yet today,
    add up to QUESTS_PER_DAY new quests — as long as the total stays
    under QUESTS_MAX (15).  Called at the top of every quest panel open
    and also from init_user lazy-init on first hunt.
    """
    today = today_utc()
    d     = data[user_id]
    active_quests = d.setdefault("quests", [])

    # Drop unclaimed quests from a template that's been retired from the daily
    # pool entirely (e.g. maintain_streak moved to weekly-only) — unconditional,
    # not gated behind "already rolled today", so a relic quest from before a
    # rebalance disappears the next time this player's panel is opened rather
    # than lingering until their next natural daily roll.
    _daily_ids = {t["id"] for t in QUEST_TEMPLATES}
    d["quests"] = [q for q in active_quests
                   if q.get("claimed") or q.get("template") in _daily_ids]
    active_quests = d["quests"]

    if d.get("quests_last_roll") == today:
        return   # already rolled today

    # Drop expired/claimed quests that are more than 7 days old (housekeeping)
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    d["quests"] = [q for q in active_quests
                   if not q.get("claimed") or q.get("created_date", "") >= cutoff]
    # Drop quests that target an animal retired in the Earth-biome re-theme —
    # they can never progress. (Claimed ones are kept for the 7-day window above.)
    d["quests"] = [q for q in d["quests"]
                   if q.get("claimed")
                   or not (q.get("requires", {}).get("animal")
                           and q["requires"]["animal"] not in _CATCHABLE_ANIMALS)]
    active_quests = d["quests"]

    slots_free = QUESTS_MAX - len(active_quests)
    if slots_free <= 0:
        d["quests_last_roll"] = today
        return
 
    existing_templates = [q["template"] for q in active_quests if not q.get("claimed")]
    level  = d.get("level", 1)
    new_qs = roll_daily_quests(level, existing_templates)
 
    # Never exceed cap
    new_qs = new_qs[:slots_free]
    d["quests"].extend(new_qs)
    d["quests_last_roll"] = today


WEEK_SECONDS = 7 * 86400

def quest_weekly_roll_if_needed(user_id: str):
    """Same shape as quest_daily_roll_if_needed, but on a rolling 7-day
    window (epoch-based, not a calendar day string) and drawing from
    WEEKLY_QUEST_TEMPLATES into data[uid]["weekly_quests"]."""
    now = time.time()
    d   = data[user_id]
    last_roll = d.get("weekly_quests_last_roll", 0)
    if now - last_roll < WEEK_SECONDS:
        return   # still inside this week's window

    active_quests = d.setdefault("weekly_quests", [])

    # Drop quests claimed more than a week ago (housekeeping), and any
    # targeting an animal retired from the current biome roster.
    cutoff = now - WEEK_SECONDS
    d["weekly_quests"] = [q for q in active_quests
                           if not q.get("claimed") or q.get("created_ts", now) >= cutoff]
    d["weekly_quests"] = [q for q in d["weekly_quests"]
                           if q.get("claimed")
                           or not (q.get("requires", {}).get("animal")
                                   and q["requires"]["animal"] not in _CATCHABLE_ANIMALS)]
    active_quests = d["weekly_quests"]

    slots_free = WEEKLY_QUESTS_MAX - len(active_quests)
    if slots_free <= 0:
        d["weekly_quests_last_roll"] = now
        return

    existing_templates = [q["template"] for q in active_quests if not q.get("claimed")]
    level  = d.get("level", 1)
    new_qs = roll_weekly_quests(level, existing_templates)
    for q in new_qs:
        q["created_ts"] = now

    new_qs = new_qs[:slots_free]
    d["weekly_quests"].extend(new_qs)
    d["weekly_quests_last_roll"] = now


def quest_progress(user_id: str, stat: str, amount: int = 1, *, absolute: bool = False, **ctx):
    """
    Advance progress on all active (unclaimed) quests that track `stat`.

    absolute=True: `amount` is the *current value* of a running total (e.g. the
    player's daily streak), not an increment — progress is set to it (never
    decreasing), so a "reach a 3-day streak" quest can't complete early from
    1 + 2 accumulating to 3 on day two.

    ctx keyword args carry extra context used by some quest types:
        biome      – current biome key  (for hunts_in_biome)
        animal     – animal just caught (for animal_caught_specific)
        rarity     – rarity of caught animal (for rarity_caught)
        tool_tier  – tier of current tool (for tool_tier_hunts)
        crate_name – name of opened crate (for crate_tier_opened)
    """
    d = data[user_id]
    newly_completed = []

    for q in d.get("quests", []) + d.get("weekly_quests", []):
        if q.get("claimed") or q.get("completed"):
            continue
        if q["stat"] != stat:
            continue
 
        req = q.get("requires", {})
 
        # Gating checks — only count if context matches the quest requirement
        if "biome" in req and ctx.get("biome") != req["biome"]:
            continue
        if "animal" in req and ctx.get("animal") != req.get("animal"):
            continue
        if "rarity" in req:
            rarity_order = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]
            req_idx  = rarity_order.index(req["rarity"]) if req["rarity"] in rarity_order else 0
            got_idx  = rarity_order.index(ctx["rarity"]) if ctx.get("rarity") in rarity_order else 0
            if got_idx < req_idx:
                continue
        if "tier" in req and ctx.get("tool_tier", 0) < req["tier"]:
            continue
        if "crate_tier" in req and ctx.get("crate_name") != req["crate_tier"]:
            continue
 
        if absolute:
            q["progress"] = min(max(q["progress"], amount), q["target"])
        else:
            q["progress"] = min(q["progress"] + amount, q["target"])
        if q["progress"] >= q["target"] and not q["completed"]:
            q["completed"] = True
            newly_completed.append(q)
 
    return newly_completed   # caller can notify if desired
 
 
def quest_claim(user_id: str, quest_id: str, *, list_key: str = "quests") -> dict:
    """
    Mark quest as claimed and grant XP + money (+ gems/crate on the templates
    that roll a bonus — see generate_quest). `list_key` picks the daily
    ("quests") or weekly ("weekly_quests") queue.
    Returns {"ok": bool, "xp": int, "money": int, "gems": int,
             "crate": str|None, "level_ups": int}
    """
    d = data[user_id]
    for q in d.get(list_key, []):
        if q["id"] != quest_id:
            continue
        if not q.get("completed"):
            return {"ok": False, "reason": "not_complete"}
        if q.get("claimed"):
            return {"ok": False, "reason": "already_claimed"}

        xp    = q["xp_reward"]
        money = q.get("money_reward", 0)
        gems  = q.get("gems_reward", 0)
        crate = q.get("crate_reward")
        q["claimed"] = True

        d["xp"] += xp
        d["stats"]["total_xp_earned"] = d["stats"].get("total_xp_earned", 0) + xp
        if money:
            add_money(user_id, money, "quest")
            d["total_money_earned"] = d.get("total_money_earned", 0) + money
        if gems:
            add_gems(user_id, gems, "quest")
        if crate:
            ci = d.setdefault("crate_inv", {})
            ci[crate] = ci.get(crate, 0) + 1
        d["stats"].setdefault("first_quest_claim_ts", int(time.time()))
        _hp_result = hunters_path_maybe_complete(user_id)

        # Track the "complete quests" daily meta-quest — only for daily
        # claims; a weekly quest finishing isn't "completing another quest
        # today" in the sense that meta-quest means.
        milestone_gems = 0
        milestone_hit  = None
        if list_key == "quests":
            quest_progress(user_id, "quests_completed_today", 1)

            # Lifetime daily-quest milestone track — a cumulative counter
            # that never resets, alongside the daily/weekly queues.
            total = d["stats"].get("daily_quests_completed_total", 0) + 1
            d["stats"]["daily_quests_completed_total"] = total
            claimed_ms = d.setdefault("daily_quest_milestones_claimed", [])
            for threshold, gem_reward in DAILY_QUEST_MILESTONES:
                if total >= threshold and threshold not in claimed_ms:
                    claimed_ms.append(threshold)
                    add_gems(user_id, gem_reward, "quest_milestone")
                    milestone_gems += gem_reward
                    milestone_hit = threshold
                    break   # one milestone per claim — the next one waits for the next quest

        level_ups = 0
        while d["xp"] >= xp_for_level(d["level"]):
            d["xp"]    -= xp_for_level(d["level"])
            d["level"] += 1
            level_ups   += 1

        return {"ok": True, "xp": xp, "money": money, "gems": gems, "crate": crate,
                "level_ups": level_ups,
                "level": d["level"], "xp_now": d["xp"],
                "xp_needed": xp_for_level(d["level"]),
                "hunters_path_result": _hp_result,
                "milestone_gems": milestone_gems, "milestone_hit": milestone_hit}

    return {"ok": False, "reason": "not_found"}

# ─────────────────────────────────────────────
# GAMBLE PANELS
# ─────────────────────────────────────────────

# Plain unicode so the reels render everywhere (DMs, user installs, any server).
SLOT_SYMBOLS = ["`🍒`", "`🍋`", "`🔔`", "`⭐`", "`💎`", "7️⃣"]

BJ_SUITS = ["♠", "♥", "♦", "♣"]
BJ_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def _bj_deck() -> list:
    deck = [f"{r}{s}" for s in BJ_SUITS for r in BJ_RANKS]
    random.shuffle(deck)
    return deck

def _bj_value(card: str) -> int:
    rank = card[:-1]
    if rank in ("J", "Q", "K"): return 10
    if rank == "A": return 11
    return int(rank)

def _bj_hand_value(hand: list) -> int:
    total = sum(_bj_value(c) for c in hand)
    aces  = sum(1 for c in hand if c[:-1] == "A")
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total

_CARD_BACK = emoji("card_back") or "🂠"

def _bj_hand_str(hand: list, hide_second: bool = False) -> str:
    if hide_second and len(hand) >= 2:
        return f"{card_emoji(hand[0])} {_CARD_BACK}"
    return " ".join(card_emoji(c) for c in hand)

_bj_state: dict[str, dict] = {}


def _bj_resume_or_clear(user_id: str) -> None:
    """Drop a *settled* blackjack hand so the player gets a fresh deal screen,
    but never erase an unfinished hand whose stake was already deducted —
    opening the menu / 'Play Again' must resume that hand, not eat the bet."""
    st = _bj_state.get(user_id)
    if not st or st.get("done"):
        _bj_state.pop(user_id, None)

def build_gamble_menu(user_id: str) -> list:
    d = data[user_id]
    content = (
        f"### {emoji('dice')} Gamble\n"
        f"Balance: **◈ {d['money']:,}**\n\n"
        f"-# Select a game from the dropdown below."
    )
    game_options = [
        {"label": "Coinflip", "emoji": emoji_partial("coinflip"),  "value": "coinflip",
         "description": "Double or nothing on a coin toss"},
        {"label": "Slots", "emoji": emoji_partial("slot_machine"), "value": "slots",
         "description": "Spin the reels — higher biomes, bigger wins"},
        {"label": "🃏 Blackjack",           "value": "blackjack",
         "description": "Beat the dealer to 21"},
        {"label": "Roulette", "emoji": emoji_partial("red_ball"),  "value": "roulette",
         "description": "Bet on Red, Black or Green"},
        {"label": "✊ Rock Paper Scissors",  "value": "rps",
         "description": "Beat the bot hand-to-hand"},
        {"label": "Dice", "emoji": emoji_partial("dice"),  "value": "dice",
         "description": "Roll 2 dice — bet Low, Seven or High"},
        {"label": "🔼 High-Low",            "value": "highlow",
         "description": "Guess if the next card is higher or lower"},
    ]
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"gamble:game_select:{user_id}",
            "placeholder": "🎮 Choose a game...",
            "min_values": 1, "max_values": 1, "flows": {},
            "options": game_options,
        }]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "Responsible Gambling", "emoji": emoji_partial('warning'),
             "custom_id": f"gamble:warn:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"nav:menu:{user_id}"},
        ]},
    ]}]

def build_gamble_warning_panel(user_id: str) -> list:
    content = (
        f"### {emoji('warning')} A word on gambling\n"
        "These games use **◈ in-game currency only** — you can't win or lose real money here, "
        "and ◈ has no cash value.\n\n"
        "**Real-world gambling is different.** The odds are always tilted toward the house, "
        "losses can pile up quickly, and for some people it becomes a serious addiction that "
        "hurts their finances, relationships and health.\n\n"
        "**If gambling is a problem for you or someone you know:**\n"
        f"-# {emoji('earth')} begambleaware.org  ·  gamblersanonymous.org\n"
        "-# `🇺🇸` 1-800-GAMBLER   ·  `🇬🇧` GamCare 0808 8020 133\n"
        "-# `🇨🇦` 1-866-531-2600  ·  `🇦🇺` 1800 858 858\n\n"
        "-# Set limits, play for fun, and stop when it stops being fun."
    )
    return [{"type": 17, "accent_color": 0xE67E22, "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"gamble:back:{user_id}"},
        ]},
    ]}]

# ── DICE (2d6) ──
DICE_BETS = {
    # key: (label, predicate on total, payout multiplier)
    "low":   ("Low (2–6)",  lambda t: 2 <= t <= 6,  2.2),
    "seven": ("Seven (7)",  lambda t: t == 7,       5.5),
    "high":  ("High (8–12)", lambda t: 8 <= t <= 12, 2.2),
}

def build_dice_panel(user_id: str, state: str = "bet", result: dict = None) -> list:
    d           = data[user_id]
    current_bet = d.get("_dice_bet", 0)
    no_bet      = current_bet == 0
    bet_line    = f"Bet: **◈ {current_bet:,}**" if current_bet else "Bet: *not set*"
    if state == "bet":
        content = (
            f"### {emoji('dice')} Dice\n{bet_line}\n\n"
            f"Two dice are rolled. Bet on the total:\n"
            f"-# Low 2–6 → ×2.2  ·  Seven → ×5.5  ·  High 8–12 → ×2.2"
        )
    else:
        d1, d2 = result["dice"]; total = d1 + d2
        bet    = result["bet"]; won = result["won"]
        pick   = DICE_BETS[result["pick"]][0]
        payout = result["payout"]
        head   = f"{emoji('check_mark')} You won!" if won else f"{emoji('cross_mark')} You lost!"
        money_line = (f"**+◈ {payout - bet:,}**" if won else f"**-◈ {bet:,}**")
        content = (
            f"### {emoji('dice')} Dice — {head}\n"
            f"{emoji('dice')} **{d1}** + {emoji('dice')} **{d2}** = **{total}**  ·  you bet **{pick}**\n\n"
            f"{money_line} · Balance: **◈ {d['money']:,}**\n\n{bet_line}"
        )
    row_bets = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": f"{DICE_BETS[k][0]} (×{DICE_BETS[k][2]})",
         "custom_id": f"gamble:dice:{k}:{user_id}", "disabled": no_bet}
        for k in ("low", "seven", "high")
    ]}
    row_util = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Change Bet", "custom_id": f"gamble:dice:setbet:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Back",     "custom_id": f"gamble:back:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        row_bets, row_util,
    ]}]

# ── HIGH-LOW ──
_HL_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]  # index 0..12 == value 1..13
_HL_SUITS = ["♠", "♥", "♦", "♣"]
_HL_HOUSE_EDGE = 0.92

def _hl_card(n: int, suit: str) -> str:
    """Card emoji for High-Low value n (1..13) with a display-only suit."""
    return card_emoji(f"{_HL_RANKS[n - 1]}{suit if suit in _HL_SUITS else '♠'}")

def _hl_multipliers(n: int) -> tuple[float, float]:
    """Payout for guessing higher / lower than card value n (1..13), tuned so
    each side pays back ~0.92 (ties push and refund the stake). A side is
    returned as 0.0 (disabled) when it's too close to a sure thing to be worth
    betting — the player takes the longshot side or re-deals."""
    push_p = 1 / 13
    def m(count: int) -> float:
        if count <= 0:
            return 0.0
        mult = round((_HL_HOUSE_EDGE - push_p) / (count / 13), 2)
        return mult if mult >= 1.1 else 0.0
    return m(13 - n), m(n - 1)

def build_highlow_panel(user_id: str, state: str = "draw", result: dict = None) -> list:
    d           = data[user_id]
    current_bet = d.get("_hl_bet", 0)
    no_bet      = current_bet == 0
    bet_line    = f"Bet: **◈ {current_bet:,}**" if current_bet else "Bet: *not set*"

    if state == "result":
        n = result["n"]; m = result["m"]
        outcome = result["outcome"]; bet = result["bet"]; payout = result["payout"]
        guess_lbl = "Higher" if result["guess"] == "hi" else "Lower"
        if outcome == "win":
            head, money = f"{emoji('check_mark')} You won!", f"**+◈ {payout - bet:,}**"
        elif outcome == "push":
            head, money = f"{emoji('handshake')} Push — same card", f"Bet refunded"
        else:
            head, money = f"{emoji('cross_mark')} You lost!", f"**-◈ {bet:,}**"
        content = (
            f"### `🔼` High-Low — {head}\n"
            f"Card was {_hl_card(n, result.get('s', '♠'))}, you guessed **{guess_lbl}** "
            f"→ next card {_hl_card(m, result.get('ms', '♠'))}\n\n"
            f"{money} · Balance: **◈ {d['money']:,}**\n\n{bet_line}"
        )
        row_bets = {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "🃏 Deal again",
             "custom_id": f"gamble:hl:draw:{user_id}", "disabled": no_bet},
            {"type": 2, "style": 2, "label": "Change Bet",
             "custom_id": f"gamble:hl:setbet:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"gamble:back:{user_id}"},
        ]}
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            row_bets,
        ]}]

    n = d.get("_hl_n")
    if state == "guess" and n:
        m_hi, m_lo = _hl_multipliers(n)
        note = ("-# That side is too close to a sure thing to bet — take the "
                "longshot or re-deal." if (m_hi == 0 or m_lo == 0) else
                "-# Same card = push (bet refunded).")
        content = (
            f"### `🔼` High-Low\n{bet_line}\n\n"
            f"The card is {_hl_card(n, d.get('_hl_s', '♠'))}.\n"
            f"Will the next card be higher or lower?\n{note}"
        )
        row = {"type": 1, "components": [
            {"type": 2, "style": 3, "label": f"🔼 Higher (×{m_hi})" if m_hi else "🔼 Higher —",
             "custom_id": f"gamble:hl:hi:{user_id}", "disabled": (m_hi == 0)},
            {"type": 2, "style": 4, "label": f"🔽 Lower (×{m_lo})" if m_lo else "🔽 Lower —",
             "custom_id": f"gamble:hl:lo:{user_id}", "disabled": (m_lo == 0)},
        ]}
        row_util = {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Re-deal", "emoji": emoji_partial("refresh"), "custom_id": f"gamble:hl:draw:{user_id}"},
            {"type": 2, "style": 2, "label": "Change Bet", "custom_id": f"gamble:hl:setbet:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",     "custom_id": f"gamble:back:{user_id}"},
        ]}
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            row, row_util,
        ]}]

    # state == "draw" — nothing dealt yet
    content = (
        f"### `🔼` High-Low\n{bet_line}\n\n"
        f"A card (A–K) is drawn. Guess whether the **next** card is higher or lower.\n"
        f"-# Longer odds pay more · same card refunds your bet."
    )
    row = {"type": 1, "components": [
        {"type": 2, "style": 3, "label": "🃏 Deal", "custom_id": f"gamble:hl:draw:{user_id}",
         "disabled": no_bet},
        {"type": 2, "style": 2, "label": "Change Bet", "custom_id": f"gamble:hl:setbet:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"gamble:back:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        row,
    ]}]

def build_coinflip_panel(user_id: str, state: str = "pick", result: dict = None) -> list:
    d           = data[user_id]
    current_bet = d.get("_cf_bet", 0)
    last_pick   = d.get("_cf_last_pick")
    no_bet      = current_bet == 0
    bet_line    = f"Bet: **◈ {current_bet:,}**" if current_bet else "Bet: *not set*"
    last_line   = (f"-# Last guess: **{'Heads' if last_pick == 'heads' else 'Tails'}**"
                   if last_pick else "-# Last guess: **None**")

    if state == "pick":
        content = (
            f"### {emoji('coinflip')} Coinflip\n{last_line}\n{bet_line}\n\n"
            f"Pick heads or tails — win to double your bet!\n"
            f"-# Set a bet first, then pick your side."
        )
    else:
        won = result["won"]; bet = result["bet"]
        flip = result["flip"]; pick = result["pick"]
        flip_lbl = "Heads" if flip == "heads" else "Tails"
        pick_lbl = "Heads" if pick == "heads" else "Tails"
        if won:
            content = (
                f"### {emoji('coinflip')} Coinflip — {emoji('check_mark')} You won!\n"
                f"**{flip_lbl}!** You picked **{pick_lbl}** — correct!\n\n"
                f"**+◈ {bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
        else:
            content = (
                f"### {emoji('coinflip')} Coinflip — {emoji('cross_mark')} You lost!\n"
                f"**{flip_lbl}!** You picked **{pick_lbl}** — wrong!\n\n"
                f"**-◈ {bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "Heads",
             "custom_id": f"gamble:cf:heads:{user_id}", "disabled": no_bet},
            {"type": 2, "style": 1, "label": "Tails",
             "custom_id": f"gamble:cf:tails:{user_id}", "disabled": no_bet},
            {"type": 2, "style": 2, "label": "Change Bet",
             "custom_id": f"gamble:cf:setbet:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"gamble:back:{user_id}"},
        ]},
    ]}]

def _slots_biome(user_id: str) -> str:
    """Which slots table the player has selected. Kept separate from the real
    hunting `biome` so picking a slots table never teleports the hunter. Falls
    back to Village if the table's level gate is no longer met."""
    b = data[user_id].get("_slots_biome") or data[user_id].get("biome", "village")
    if b not in SLOT_BIOME_CONFIG:
        return "village"
    if data.get(user_id, {}).get("level", 1) < biome_level(b):
        return "village"
    return b

def _slots_biome_config(user_id: str) -> tuple:
    return SLOT_BIOME_CONFIG.get(_slots_biome(user_id), SLOT_BIOME_CONFIG["village"])

def _slots_biome_options(user_id: str) -> list:
    user_level = data[user_id].get("level", 1)
    cur        = _slots_biome(user_id)
    opts = []
    for biome_key, lvl_req in BIOME_LEVELS:
        cfg = SLOT_BIOME_CONFIG.get(biome_key)
        if not cfg:
            continue
        min_b, max_b, chance, mult = cfg
        locked = user_level < lvl_req
        desc   = (f"Locked (Level {lvl_req})" if locked
                  else f"Win: {chance}% · ×{mult} · Max ◈{max_b:,}")
        opts.append({
            "label": BIOME_NAMES.get(biome_key, biome_key), "value": biome_key,
            "description": desc, "default": biome_key == cur,
        })
    return opts

def build_slots_chances_panel(user_id: str) -> list:
    user_level = data[user_id].get("level", 1)
    lines = []
    for biome_key, lvl_req in BIOME_LEVELS:
        cfg = SLOT_BIOME_CONFIG.get(biome_key)
        if not cfg:
            continue
        min_b, max_b, chance, mult = cfg
        locked   = user_level < lvl_req
        lock_str = f" {emoji('lock')}" if locked else ""
        lines.append(
            f"{BIOME_EMOJIS.get(biome_key, emoji('world_map'))} **{BIOME_NAMES.get(biome_key, biome_key)}**{lock_str}\n"
            f"-# Bet: ◈{min_b:,}–◈{max_b:,} · Win: {chance}% · ×{mult}"
        )
    content = f"### {emoji('slot_machine')} Slots — Win Chances by Biome\n\n" + "\n\n".join(lines)
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"gamble:menu:slots:{user_id}"},
        ]},
    ]}]

def build_slots_panel(user_id: str, state: str = "bet", result: dict = None) -> list:
    d           = data[user_id]
    biome       = _slots_biome(user_id)
    cfg         = SLOT_BIOME_CONFIG.get(biome, SLOT_BIOME_CONFIG["village"])
    min_b, max_b, chance, mult = cfg
    current_bet = d.get("_slots_bet", 0)
    no_bet      = current_bet == 0
    biome_dd    = {"type": 1, "components": [{"type": 3,
        "custom_id": f"gamble:slots:biome:{user_id}",
        "placeholder": "🗺️ Select biome...", "min_values": 1, "max_values": 1,
        "flows": {}, "options": _slots_biome_options(user_id),
    }]}
    bet_line = f"Bet: **◈ {current_bet:,}**" if current_bet else "Bet: *not set — use Change Bet*"
    if state == "bet":
        content = (
            f"### {emoji('slot_machine')} Slots Machine\n"
            f"{BIOME_EMOJIS.get(biome, emoji('world_map'))} **{BIOME_NAMES.get(biome, biome)}**\n\n"
            f"Min: **◈ {min_b:,}** · Max: **◈ {max_b:,}**\n"
            f"Win: **{chance}%** · Multiplier: **×{mult}**\n\n{bet_line}"
        )
    else:
        reels = result["reels"]; bet = result["bet"]
        payout = result["payout"]; won = result["won"]
        reel_str = f"[ {reels[0]} | {reels[1]} | {reels[2]} ]"
        outcome  = f"{emoji('check_mark')} **Won! +◈ {payout - bet:,}**" if won else f"{emoji('cross_mark')} **No win. -◈ {bet:,}**"
        content  = (
            f"### {emoji('slot_machine')} Slots Machine\n{reel_str}\n\n"
            f"{outcome}\nBalance: **◈ {d['money']:,}**\n\n"
            f"{BIOME_EMOJIS.get(biome,emoji('world_map'))} {BIOME_NAMES.get(biome,biome)} · "
            f"Win: {chance}% · ×{mult}\n{bet_line}"
        )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        biome_dd,
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Roll!", "emoji": emoji_partial("slot_machine"),
             "custom_id": f"gamble:slots:spin:{user_id}", "disabled": no_bet},
            {"type": 2, "style": 2, "label": "Change Bet",
             "custom_id": f"gamble:slots:setbet:{user_id}"},
            {"type": 2, "style": 1, "label": "View Chances",
             "custom_id": f"gamble:slots:chances:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"gamble:back:{user_id}"},
        ]},
    ]}]

def build_roulette_panel(user_id: str, state: str = "bet", result: dict = None) -> list:
    d           = data[user_id]
    current_bet = d.get("_roulette_bet", 0)
    last_pick   = d.get("_roulette_pick")
    no_bet      = current_bet == 0
    bet_line    = f"Bet: **◈ {current_bet:,}**" if current_bet else "Bet: *not set*"
    last_line   = (f"-# Last bet: **{ROULETTE_BET_TYPES[last_pick][0]}**"
                   if last_pick else "-# Last bet: **None**")
    _rl_style = {"red": 4, "black": 2, "green": 3}
    row_colors = {"type": 1, "components": [
        {"type": 2, "style": _rl_style[k],
         "label": f"{ROULETTE_BET_TYPES[k][0]} (×{ROULETTE_BET_TYPES[k][2]})",
         "custom_id": f"gamble:rl:{k}:{user_id}", "disabled": no_bet}
        for k in ROULETTE_COLORS
    ]}
    row_util = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Change Bet", "custom_id": f"gamble:rl:setbet:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Back",     "custom_id": f"gamble:back:{user_id}"},
    ]}
    _odds = "  ·  ".join(
        f"{ROULETTE_BET_TYPES[k][0]} {ROULETTE_BET_TYPES[k][1]}% → ×{ROULETTE_BET_TYPES[k][2]}"
        for k in ROULETTE_COLORS
    )
    if state == "bet":
        content = (
            f"### {emoji('red_ball')} Roulette\n{last_line}\n{bet_line}\n\n"
            f"Pick where the ball lands:\n"
            f"-# {_odds}"
        )
    else:
        color = result["color"]; pick = result["pick"]
        bet = result["bet"]; won = result["won"]; payout = result["payout"]
        color_ico = {"red": emoji('red_ball'), "black": "⚫", "green": emoji('green_ball')}.get(color, "⚪")
        pick_lbl  = ROULETTE_BET_TYPES.get(pick, (pick,))[0]
        if won:
            content = (
                f"### {emoji('red_ball')} Roulette — {emoji('check_mark')} You won!\n"
                f"Result: **{color_ico} {color.title()}** — You bet **{pick_lbl}**\n\n"
                f"**+◈ {payout - bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
        else:
            content = (
                f"### {emoji('red_ball')} Roulette — {emoji('cross_mark')} You lost!\n"
                f"Result: **{color_ico} {color.title()}** — You bet **{pick_lbl}**\n\n"
                f"**-◈ {bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        row_colors, row_util,
    ]}]

def build_blackjack_panel(user_id: str) -> list:
    st = _bj_state.get(user_id)
    d  = data[user_id]
    if not st:
        content = (
            f"### `🃏` Blackjack\nBalance: **◈ {d['money']:,}**\n\n"
            f"Get closer to 21 than the dealer without busting.\n"
            f"**Bust = lose your entire bet.**\n\n"
            f"-# Dealer stands on 17 · Blackjack pays ×2.5"
        )
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 3, "label": "🃏 Place Bet & Deal",
                 "custom_id": f"gamble:bj:deal:{user_id}"},
                {"type": 2, "style": 2, "label": "◀ Back",
                 "custom_id": f"gamble:back:{user_id}"},
            ]},
        ]}]
    player_val = _bj_hand_value(st["player"])
    dealer_val = _bj_hand_value(st["dealer"])
    bet        = st["bet"]
    done       = st.get("done", False)
    if not done:
        content = (
            f"### `🃏` Blackjack · Bet: **◈ {bet:,}**\n\n"
            f"**Your hand:** {_bj_hand_str(st['player'])} — **{player_val}**\n"
            f"**Dealer:** {_bj_hand_str(st['dealer'], hide_second=True)}\n\n"
            f"-# Balance: **◈ {d['money']:,}**"
        )
        _hid = st.get("hid", "")
        action_row = {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Hit",   "custom_id": f"gamble:bj:hit:{_hid}:{user_id}"},
            {"type": 2, "style": 1, "label": "Stand", "custom_id": f"gamble:bj:stand:{_hid}:{user_id}"},
        ]}
    else:
        outcome = st.get("outcome", "")
        net     = st.get("net", 0)
        sign    = "+" if net >= 0 else ""
        content = (
            f"### `🃏` Blackjack · {outcome}\n\n"
            f"**Your hand:** {_bj_hand_str(st['player'])} — **{player_val}**\n"
            f"**Dealer:** {_bj_hand_str(st['dealer'])} — **{dealer_val}**\n\n"
            f"**{sign}◈ {net:,}** · Balance: **◈ {d['money']:,}**"
        )
        action_row = {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "🃏 Play Again",
             "custom_id": f"gamble:menu:blackjack:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"gamble:back:{user_id}"},
        ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        action_row,
    ]}]

def build_rps_panel(user_id: str, state: str = "pick", result: dict = None) -> list:
    d           = data[user_id]
    current_bet = d.get("_rps_bet", 0)
    last_pick   = d.get("_rps_last_pick")
    no_bet      = current_bet == 0
    bet_line    = f"Bet: **◈ {current_bet:,}**" if current_bet else "Bet: *not set*"
    last_line   = (f"-# Last pick: **{RPS_CHOICES.get(last_pick,'?')} {last_pick.title()}**"
                   if last_pick else "-# Last pick: **None**")
    row_picks = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "✊ Rock",
         "custom_id": f"gamble:rps:rock:{user_id}",     "disabled": no_bet},
        {"type": 2, "style": 1, "label": "🖐️ Paper",
         "custom_id": f"gamble:rps:paper:{user_id}",    "disabled": no_bet},
        {"type": 2, "style": 1, "label": "✌️ Scissors",
         "custom_id": f"gamble:rps:scissors:{user_id}", "disabled": no_bet},
    ]}
    row_util = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Change Bet", "custom_id": f"gamble:rps:setbet:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Back",     "custom_id": f"gamble:back:{user_id}"},
    ]}
    if state == "pick":
        content = (
            f"### `✊` Rock Paper Scissors\n{last_line}\n{bet_line}\n\n"
            f"Beat the bot to double your bet!\n"
            f"-# Tie = bet refunded · Loss = lose bet"
        )
    else:
        pick = result["pick"]; bot_pick = result["bot_pick"]
        bet  = result["bet"];  outcome  = result["outcome"]
        p_ico = RPS_CHOICES.get(pick, "?"); b_ico = RPS_CHOICES.get(bot_pick, "?")
        if outcome == "win":
            content = (
                f"### `✊` RPS — {emoji('check_mark')} You won!\n"
                f"You: **{p_ico} {pick.title()}** vs Bot: **{b_ico} {bot_pick.title()}**\n\n"
                f"**+◈ {bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
        elif outcome == "tie":
            content = (
                f"### `✊` RPS — {emoji('handshake')} Tie!\n"
                f"You: **{p_ico} {pick.title()}** vs Bot: **{b_ico} {bot_pick.title()}**\n\n"
                f"Bet refunded · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
        else:
            content = (
                f"### `✊` RPS — {emoji('cross_mark')} You lost!\n"
                f"You: **{p_ico} {pick.title()}** vs Bot: **{b_ico} {bot_pick.title()}**\n\n"
                f"**-◈ {bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        row_picks, row_util,
    ]}]

# ─────────────────────────────────────────────
# HELP PANEL
# ─────────────────────────────────────────────

HELP_PER_PAGE = 12

def build_help_components(user_id: str, page: int = 0) -> list:
    cmds  = sorted(bot.tree.get_commands(), key=lambda c: c.name)
    rows  = []
    for c in cmds:
        if isinstance(c, app_commands.Group):
            for sub in sorted(c.commands, key=lambda s: s.name):
                rows.append(f"`/{c.name} {sub.name}` — {sub.description or 'No description'}")
        else:
            rows.append(f"</{c.name}:{COMMAND_ID.get(c.name,'0')}> — {c.description or 'No description'}")

    total_pages = max(1, (len(rows) + HELP_PER_PAGE - 1) // HELP_PER_PAGE)
    page        = max(0, min(page, total_pages - 1))
    page_rows   = rows[page * HELP_PER_PAGE:(page + 1) * HELP_PER_PAGE]

    content = (
        f"### {emoji('book')} Commands\n"
        f"-# Page {page + 1}/{total_pages} · {len(rows)} commands total\n\n"
        + "\n".join(page_rows)
        + "\n\n-# Use /verify if blocked from commands."
    )
    nav_row = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Prev",
         "custom_id": f"help:prev:{user_id}", "disabled": page == 0},
        {"type": 2, "style": 2, "label": f"{page + 1}/{total_pages}",
         "custom_id": f"help:noop:{user_id}", "disabled": True},
        {"type": 2, "style": 2, "label": "Next ▶",
         "custom_id": f"help:next:{user_id}", "disabled": page >= total_pages - 1},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        nav_row,
        _back_row(user_id),
    ]}]

# ─────────────────────────────────────────────
# MAIL PANEL
# ─────────────────────────────────────────────

def build_mail_components(user_id: str, tab: str = "tribe", mark_read: bool = True) -> list:
    d = data[user_id]
    tribe_unread = bool(d.get("tribe_inv") and not d.get("tribe_inv_read", False))
    gifts_unread = any(not g.get("read", False) for g in d.get("gift_mails", []))
    dev_unread   = bool(DEV_MAIL and d.get("mail_dev_content_read", "") != DEV_MAIL)
    tab_options  = [
        {"label": f"{'🔴 ' if tribe_unread else ''}Tribe Invites", "emoji": emoji_partial("tribe"), "value": "tribe",  "default": tab == "tribe"},
        {"label": f"{'🔴 ' if gifts_unread else ''}Gifts", "emoji": emoji_partial("gift"),          "value": "gifts",  "default": tab == "gifts"},
        {"label": f"{'🔴 ' if dev_unread   else ''}Dev Mail", "emoji": emoji_partial("announcement"),       "value": "dev",    "default": tab == "dev"},
    ]
    tab_dd = {"type": 1, "components": [{"type": 3,
        "custom_id": f"mail:tab_dd:{user_id}",
        "placeholder": "📬 Select mailbox...", "min_values": 1, "max_values": 1,
        "flows": {}, "options": tab_options,
    }]}
    back_btn = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Menu", "custom_id": f"nav:menu:{user_id}"}
    ]}

    if tab == "tribe":
        tribe_inv = d.get("tribe_inv")
        if tribe_inv and tribe_inv in tribe_data:
            td    = tribe_data[tribe_inv]
            total = 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"])
            unread_tag = "" if d.get("tribe_inv_read", False) else f" {emoji('new_notif')}"
            content = (
                f"### {emoji('tribe')} Tribe Invites{unread_tag}\n\n"
                f"Pending invite to **{tribe_inv}**!\n\n"
                f"-# {TRIBE_EMOJIS['members']} {total}/{td['max_members']} members\n"
                f"-# {TRIBE_EMOJIS['luck_boost']} {td['luck_boost']}% · "
                f"{TRIBE_EMOJIS['sell_boost']} {td['sell_price_boost']}% · "
                f"{TRIBE_EMOJIS['xp_boost']} {td['xp_boost']}%"
            )
            d["tribe_inv_read"] = True
            action_btns = {"type": 1, "components": [
                {"type": 2, "style": 3, "label": "Accept", "emoji": emoji_partial('check_mark'),
                 "custom_id": f"mail:tribe:accept:{user_id}"},
                {"type": 2, "style": 4, "label": "Decline", "emoji": emoji_partial('cross_mark'),
                 "custom_id": f"mail:tribe:decline:{user_id}"},
            ]}
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": content},
                {"type": 14, "divider": True, "spacing": 1},
                tab_dd,
                {"type": 14, "divider": True, "spacing": 1},
                action_btns, back_btn,
            ]}]
        else:
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": f"### {emoji('tribe')} Tribe Invites\n\n-# No pending tribe invites."},
                {"type": 14, "divider": True, "spacing": 1},
                tab_dd,
                {"type": 14, "divider": True, "spacing": 1},
                back_btn,
            ]}]

    elif tab == "gifts":
        gifts = d.get("gift_mails", [])
        if not gifts:
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": f"### {emoji('gift')} Gift Mail\n\n-# No gift mail."},
                {"type": 14, "divider": True, "spacing": 1},
                tab_dd,
                {"type": 14, "divider": True, "spacing": 1},
                back_btn,
            ]}]
        mail_sections = []
        for i, g in enumerate(gifts):
            read       = g.get("read", False)
            sender     = g.get("sender_name", "Unknown")
            amt_str    = g.get("amt_str", "")
            msg        = g.get("message", "")
            ts         = g.get("ts", 0)
            unread_dot = "" if read else f" {emoji('new_notif')}"
            content    = (
                f"**Gift from {sender}{unread_dot}**\n"
                f"-# {amt_str} · <t:{ts}:R>\n"
                f"-# _{msg}_"
            )
            mail_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": {"type": 2, "style": 2 if read else 3,
                    "label": "Mark Unread" if read else "Mark Read",
                    "custom_id": f"mail:gift_toggle:{i}:{user_id}"},
            })
            if mark_read:
                g["read"] = True
        delete_btn = {"type": 1, "components": [
            {"type": 2, "style": 4, "label": "Delete All", "emoji": emoji_partial("trash"),
             "custom_id": f"mail:gifts:clear:{user_id}"},
        ]}
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {emoji('gift')} Gift Mail"},
            {"type": 14, "divider": True, "spacing": 1},
            tab_dd,
            {"type": 14, "divider": True, "spacing": 1},
            *mail_sections,
            {"type": 14, "divider": True, "spacing": 1},
            delete_btn, back_btn,
        ]}]

    else:  # dev
        is_read = d.get("mail_dev_content_read", "") == DEV_MAIL
        if not DEV_MAIL:
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": f"### {emoji('announcement')} Dev Mail\n\n-# No messages from the dev team."},
                {"type": 14, "divider": True, "spacing": 1},
                tab_dd,
                {"type": 14, "divider": True, "spacing": 1},
                back_btn,
            ]}]
        unread_tag  = "" if is_read else f" {emoji('new_notif')}"
        dev_section = {
            "type": 9,
            "components": [{"type": 10, "content": f"### {emoji('announcement')} Dev Mail{unread_tag}\n\n{DEV_MAIL}"}],
            "accessory": {"type": 2, "style": 3 if not is_read else 2,
                "label": "Mark as Read" if not is_read else "Read",
                "emoji": emoji_partial('check_mark') if not is_read else {},
                "custom_id": f"mail:dev:read:{user_id}",
                "disabled": is_read},
        }
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 14, "divider": True, "spacing": 1},
            tab_dd,
            {"type": 14, "divider": True, "spacing": 1},
            dev_section,
            {"type": 14, "divider": True, "spacing": 1},
            back_btn,
        ]}]

# ─────────────────────────────────────────────
# BAN PANEL
# ─────────────────────────────────────────────

def build_ban_components(user_id: str) -> list:
    b         = get_ban(user_id)
    reason    = b.get("reason", "No reason provided.")
    exp_ts    = b.get("expires_ts", 0)
    used      = b.get("appeals_used", 0)
    max_app   = b.get("appeals_max", 2)
    remaining = max_app - used
    if exp_ts == 0:
        duration_line = "-# This ban is **permanent**."
    else:
        duration_line = f"-# You will be unbanned <t:{exp_ts}:R>."
    body = (
        f"### `🔨` You have been banned"
        + (f" until <t:{exp_ts}:R>" if exp_ts != 0 else "")
        + "!\n\n"
        f"Reason: {reason}\n\n"
        f"You can appeal **{max_app}** times.\n"
        f"{duration_line}"
    )
    return [{"type": 17, "accent_color": 0xE74C3C, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": f"Appeal ({remaining} left)",
             "custom_id": f"ban:appeal:{user_id}",
             "disabled": remaining <= 0},
        ]},
    ]}]

# ─────────────────────────────────────────────
# GIFT PANELS
# ─────────────────────────────────────────────

def build_gift_confirm_components(sender_id: str, recipient: discord.User,
                                   format: str, parsed: int, message: str) -> list:
    gift_id = secrets.token_hex(4)
    amt_str = f"◈ {parsed:,}" if format == "money" else f"{emoji('gem')} {parsed:,}"
    gift_cache[gift_id] = {
        "sender_id": sender_id, "recipient_id": recipient.id,
        "format": format, "parsed": parsed, "message": message,
    }
    content = (
        f"### {emoji('gift')} Confirm Gift\n"
        f"Send **{amt_str}** to {recipient.mention}?\n\n"
        f"> {message}\n\n"
        f"-# This action cannot be undone."
    )
    return [{"type": 17, "accent_color": _accent(sender_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Confirm", "emoji": emoji_partial('check_mark'),
             "custom_id": f"gift:confirm:{gift_id}"},
            {"type": 2, "style": 4, "label": "Cancel", "emoji": emoji_partial('cross_mark'),
             "custom_id": f"gift:cancel:{gift_id}"},
        ]},
    ]}]

def build_gift_sent_components(sender_id: str, recipient: discord.User,
                                amt_str: str, bal_str: str, sent_message: str) -> list:
    content = (
        f"### {emoji('gift')} Gift Sent!\n"
        f"**{recipient.mention}** received **{amt_str}**!\n"
        f"Your balance: **{bal_str}**\n\n"
        f"> {sent_message}"
    )
    return [{"type": 17, "accent_color": _accent(sender_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Menu",
             "custom_id": f"nav:menu:{sender_id}"},
        ]},
    ]}]

# ─────────────────────────────────────────────
# TRIBE PANELS
# ─────────────────────────────────────────────

_TRIBE_ROLE_ICON = {"leader": TRIBE_EMOJIS["leader"], "officer": TRIBE_EMOJIS["officer"],
                    "member": "`🧑`", "recruit": "`🌱`"}

def build_tribe_components(user_id: str, tribe_name: str,
                            page: str = "main", sort_mode: str = "rank") -> list:
    td         = tribe_data[tribe_name]
    _ensure_tribe_fields(td)
    roster     = tribe_roster(tribe_name, repair=True)   # each player once, highest role
    is_leader  = td["roles"]["leader"] == user_id
    is_officer = user_id in td["roles"].get("officer", [])
    lvl        = td.get("level", 1)
    to_next    = tribe_xp_to_next(lvl)

    def _member_list(limit: int = 15) -> str:
        all_m = list(roster)
        if sort_mode == "level":
            all_m.sort(key=lambda x: data.get(x[0], {}).get("level", 0), reverse=True)
        return "\n".join(
            f"{_TRIBE_ROLE_ICON.get(r, '`🧑`')} `{get_username(uid)}`{featured_badge_suffix(uid)} — Lv. **{data.get(uid,{}).get('level','?')}**"
            for uid, r in all_m[:limit]
        ) + (f"\n-# …and {len(all_m) - limit} more" if len(all_m) > limit else "")

    total_m = len(roster)

    _TRIBE_TABS = [
        ("main",      "Overview",      "tribe",         "Level, roster and perks"),
        ("contrib",   "Contributions", "tribe_members", "Weekly & lifetime XP by member"),
        ("contracts", "Contracts",     "list",          "This week's shared goals"),
        ("roles",     "Roles",         "tribe_leader",  "Leader, officers, members, recruits"),
        ("log",       "Activity Log",  "clock",         "Recent tribe events"),
        ("shop",      "Perk Shop",     "shop",          "Spend gems on tribe boosts"),
        ("actions",   "Actions",       "tribe_set_desc","Invite, kick, promote, leave…"),
    ]
    _tab_labels = {p: lbl for p, lbl, *_ in _TRIBE_TABS}

    def _nav_row() -> dict:
        cur = page if page in _tab_labels else "main"
        return {"type": 1, "components": [{"type": 3,
            "custom_id": f"tribe:navsel:{user_id}",
            "placeholder": f"{_tab_labels.get(cur, 'Tribe')} — jump to…",
            "min_values": 1, "max_values": 1, "flows": {},
            "options": [
                {"label": lbl, "value": p, "description": desc,
                 "default": p == cur, "emoji": emoji_partial(ek)}
                for p, lbl, ek, desc in _TRIBE_TABS
            ]}]}

    def _util_row() -> dict:
        sort_lbl = "Sort: Level" if sort_mode == "rank" else "Sort: Rank"
        return {"type": 1, "components": [
            {"type": 2, "style": 2, "label": sort_lbl, "custom_id": f"tribe:sort:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"nav:menu:{user_id}"},
        ]}

    if page == "main":
        # Redesigned 2026-09-15: the roster used to be dumped straight onto
        # Overview as up to 15 text lines. It now lives behind the Members
        # button (the existing "roles" tab); Overview is just the dashboard —
        # level, size, weekly contract progress, and your own contribution.
        desc_line = f"\n`📝` *{td['description']}*" if td.get("description") else ""
        xp_bar, xp_pct = ui_progress(td["xp"], to_next) if lvl < TRIBE_LEVEL_CAP else ("", "")
        header = ui_header(emoji('tribe'), tribe_name.upper(), f"Level {lvl} Tribe{desc_line}")
        lines = [
            header, "",
            f"{TRIBE_EMOJIS['members']} **{total_m}/{td['max_members']}** Members",
        ]
        if lvl < TRIBE_LEVEL_CAP:
            lines.append(f"{USER_EMOJIS['xp']} {td['xp']:,} / {to_next:,} XP\n{xp_bar} {xp_pct}")
        else:
            lines.append(f"{USER_EMOJIS['xp']} **MAX LEVEL**")

        if lvl >= TRIBE_UNLOCK_CONTRACTS and td["week"]["contracts"]:
            cts = td["week"]["contracts"]
            avg_pct = sum(min(1.0, c["progress"] / c["target"]) if c["target"] else 1.0
                          for c in cts) / len(cts)
            lines.append(f"{ph('🔥')} Weekly Contract: **{avg_pct * 100:.0f}%**")

        wk_contrib   = td["week"]["contrib"].get(user_id, 0)
        life_contrib = td["contrib_lifetime"].get(user_id, 0)
        lines += ["", f"{ph(emoji('target'))} **YOUR CONTRIBUTION**",
                  f"This week: **{wk_contrib:,}** XP · Lifetime: **{life_contrib:,}** XP"]
        content = "\n".join(lines)

        nav_btn_rows = []
        row1 = [{"type": 2, "style": 1, "label": "Contracts", "emoji": emoji_partial('quests'),
                 "custom_id": f"tribe:nav:contracts:{user_id}"},
                {"type": 2, "style": 1, "label": "Members", "emoji": {"name": "👥"},
                 "custom_id": f"tribe:nav:roles:{user_id}"}]
        if FEATURE_EXPEDITIONS:
            _exp = td.get("expedition")
            _exp_lbl = "Expedition (active)" if _exp and not _exp.get("done") else "Expedition"
            row1.append({"type": 2, "style": 1, "label": _exp_lbl, "emoji": {"name": "⚔️"},
                         "custom_id": f"exped:refresh:{user_id}"})
        nav_btn_rows.append({"type": 1, "components": row1})

        row2 = [{"type": 2, "style": 2, "label": "Perks", "emoji": {"name": "🛠️"},
                 "custom_id": f"tribe:nav:shop:{user_id}"}]
        if is_leader or is_officer:
            row2.append({"type": 2, "style": 2, "label": "Manage", "emoji": emoji_partial('settings'),
                         "custom_id": f"tribe:nav:actions:{user_id}"})
        nav_btn_rows.append({"type": 1, "components": row2})

        _rows_main = [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            *nav_btn_rows,
            _nav_row(),
            ui_footer(user_id),
        ]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
                 "components": _rows_main}]

    elif page == "contrib":
        wk   = td["week"]["contrib"]
        life = td["contrib_lifetime"]
        def _rows(src, top=10):
            rows = sorted(src.items(), key=lambda kv: kv[1], reverse=True)[:top]
            if not rows:
                return "-# Nothing yet."
            return "\n".join(
                f"{'▸ ' if uid == user_id else ''}`{get_username(uid)}` — **{v:,}**"
                for uid, v in rows)
        content = (
            f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Contributions\n"
            f"-# Tribe XP each member has banked. Your own row is marked ▸.\n\n"
            f"**This week** ({td['week']['tag']})\n{_rows(wk)}\n\n"
            f"**Lifetime**\n{_rows(life)}"
        )
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            _nav_row(), _util_row(),
        ]}]

    elif page == "contracts":
        if lvl < TRIBE_UNLOCK_CONTRACTS:
            content = (f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Contracts\n"
                       f"-# {emoji('lock')} Weekly shared contracts unlock at **Tribe Level {TRIBE_UNLOCK_CONTRACTS}**.")
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": content},
                {"type": 14, "divider": True, "spacing": 1},
                _nav_row(), _util_row(),
            ]}]
        lines = [f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Weekly Contracts",
                 f"-# Week {td['week']['tag']} · scaling group **{td['week']['scale_group']}**"]
        for i, ct in enumerate(td["week"]["contracts"]):
            spec = next(s for s in TRIBE_CONTRACTS if s["kind"] == ct["kind"])
            tick = f"{emoji('check_mark')}" if ct["done"] else _progress_bar(ct["progress"], ct["target"])
            lines.append(
                f"\n**{ct['label']}** — +{TRIBE_XP_CONTRACT[i]} tribe XP\n"
                f"-# {spec['desc'].format(target=ct['target'])}\n"
                f"-# {ct['progress']:,}/{ct['target']:,} {tick}")
        rows = [{"type": 10, "content": "\n".join(lines)},
                {"type": 14, "divider": True, "spacing": 1}]
        if (is_leader or is_officer) and not td["week"].get("reroll_used"):
            rows.append({"type": 1, "components": [
                {"type": 2, "style": 2, "label": "🎲 Reroll (1/week)",
                 "custom_id": f"tribe:contract_reroll:{user_id}"}]})
        rows += [_nav_row(), _util_row()]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": rows}]

    elif page == "roles":
        now = int(time.time())
        groups = {"leader": [], "officer": [], "member": [], "recruit": []}
        for uid, r in roster:
            groups[r].append(uid)
        def _grp(title, uids, extra=lambda u: ""):
            if not uids:
                return ""
            body = "\n".join(f"-# `{get_username(u)}`{extra(u)}" for u in uids)
            return f"\n**{title}**\n{body}\n"
        def _prob(u):
            since = td.get("member_since", {}).get(u, now)
            done  = int(since) + TRIBE_RECRUIT_PROBATION_H * 3600
            return f" — full member <t:{done}:R>" if done > now else " — promoting soon"
        content = (
            f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Roles\n"
            f"-# Recruits become full Members after {TRIBE_RECRUIT_PROBATION_H}h."
            + _grp("`👑` Leader", groups["leader"])
            + _grp(f"{emoji('military_medal')} Officers", groups["officer"])
            + _grp("`🧑` Members", groups["member"])
            + _grp("`🌱` Recruits", groups["recruit"], _prob)
        )
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            _nav_row(), _util_row(),
        ]}]

    elif page == "log":
        entries = td.get("log", [])[-15:][::-1]
        body = "\n".join(f"-# <t:{e['ts']}:R> · {e['text']}" for e in entries) or "-# No activity yet."
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Activity Log\n\n{body}"},
            {"type": 14, "divider": True, "spacing": 1},
            _nav_row(), _util_row(),
        ]}]

    elif page == "members":
        content  = (
            f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Members\n"
            f"{TRIBE_EMOJIS['members']} **{total_m}/{td['max_members']}**\n\n{_member_list()}"
        )
        sort_lbl = "Sort: Level" if sort_mode == "rank" else "Sort: Rank"
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": sort_lbl,
                 "custom_id": f"tribe:sort:{user_id}"},
                {"type": 2, "style": 2, "label": "◀ Back",
                 "custom_id": f"tribe:nav:main:{user_id}"},
            ]},
        ]}]

    elif page == "shop":
        def _bl(key):
            return f" · **MAX {MAX_TRIBE_BOOST}%**" if td.get(key, 0) >= MAX_TRIBE_BOOST else f" — 50 {emoji('gem')}"
        content = (
            f"### {emoji('shop')} Tribe Shop — {tribe_name}\n"
            f"{emoji('gem')} Your Gems: **{data[user_id]['gems']}**\n\n"
            f"{TRIBE_EMOJIS['luck_boost']} Luck Boost: **{td['luck_boost']}%**{_bl('luck_boost')}\n"
            f"{TRIBE_EMOJIS['sell_boost']} Sell Boost: **{td['sell_price_boost']}%**{_bl('sell_price_boost')}\n"
            f"{TRIBE_EMOJIS['xp_boost']} XP Boost: **{td['xp_boost']}%**{_bl('xp_boost')}\n"
            f"{TRIBE_EMOJIS['members']} +1 Slot: **{td['max_members']}** — 100 {emoji('gem')}\n"
            f"-# Tribe boosts cap at {MAX_TRIBE_BOOST}%."
        )
        btns = []
        if is_leader or is_officer:
            btns = [
                {"type": 2, "style": 3, "label": "Luck +5%",
                 "custom_id": f"tribe:shop:luck_boost:50:5:{user_id}",
                 "disabled": td.get("luck_boost", 0) >= MAX_TRIBE_BOOST},
                {"type": 2, "style": 3, "label": "Sell +5%",
                 "custom_id": f"tribe:shop:sell_price_boost:50:5:{user_id}",
                 "disabled": td.get("sell_price_boost", 0) >= MAX_TRIBE_BOOST},
                {"type": 2, "style": 3, "label": "XP +5%",
                 "custom_id": f"tribe:shop:xp_boost:50:5:{user_id}",
                 "disabled": td.get("xp_boost", 0) >= MAX_TRIBE_BOOST},
                {"type": 2, "style": 3, "label": "+1 Slot",
                 "custom_id": f"tribe:shop:max_members:100:1:{user_id}"},
            ]
        rows = [{"type": 10, "content": content}, {"type": 14, "divider": True, "spacing": 1}]
        if btns:
            rows.append({"type": 1, "components": btns})
        rows += [_nav_row(), _util_row()]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": rows}]

    elif page == "actions":
        content     = (
            f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Actions\n"
            f"-# Select an action from the dropdown below."
        )
        action_opts = [{"label": "Leave Tribe", "emoji": emoji_partial("tribe_leave"), "value": "leave",
                        "description": "Leave your current tribe."}]
        if is_leader or is_officer:
            action_opts += [
                {"label": "Invite Player",   "emoji": emoji_partial("tribe_invite"),   "value": "invite",   "description": "Send a tribe invite."},
                {"label": "Kick Member",     "emoji": emoji_partial("tribe_kick"),     "value": "kick",     "description": "Remove a member."},
                {"label": "Ban List",        "emoji": emoji_partial("tribe_ban"),      "value": "banlist",  "description": "View and manage bans."},
                {"label": "Set Description", "emoji": emoji_partial("tribe_set_desc"), "value": "set_desc", "description": "Set tribe description."},
            ]
        if is_leader:
            action_opts += [
                {"label": "Promote Member",      "emoji": emoji_partial("tribe_promote"),  "value": "promote",  "description": "Promote to officer."},
                {"label": "Demote Officer",      "emoji": emoji_partial("tribe_demote"),   "value": "demote",   "description": "Demote to member."},
                {"label": "Transfer Leadership", "emoji": emoji_partial("tribe_transfer"), "value": "transfer", "description": "Transfer leader role."},
            ]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:action_select:{user_id}",
                "placeholder": "Select an action...",
                "min_values": 1, "max_values": 1, "flows": {}, "options": action_opts,
            }]},
            _nav_row(), _util_row(),
        ]}]

    elif page in ("kick_picker", "promote_picker", "demote_picker", "transfer_picker"):
        role_map  = {
            "kick_picker":     (td["roles"]["officer"] + td["roles"]["members"] + td["roles"].get("recruits", []), "kick", "Kick Member"),
            "promote_picker":  (td["roles"]["members"],                          "promote",  "Promote Member"),
            "demote_picker":   (td["roles"]["officer"],                          "demote",   "Demote Officer"),
            "transfer_picker": (td["roles"]["officer"],                          "transfer", "Transfer Leadership"),
        }
        targets, action_key, title = role_map[page]
        if not targets:
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": f"### {title}\n-# No eligible members."},
                {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                    "custom_id": f"tribe:nav:actions:{user_id}"}]},
            ]}]
        opts = [
            {"label": f"{action_key.title()} @{data.get(uid,{}).get('username', uid)} "
                      f"(Lv. {data.get(uid,{}).get('level','?')})",
             "value": uid, "description": f"ID: {uid}"}
            for uid in targets[:25]
        ]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {title}\n-# Select a member."},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:{action_key}_confirm:{user_id}",
                "placeholder": f"Select member...", "min_values": 1, "max_values": 1,
                "flows": {}, "options": opts,
            }]},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                "custom_id": f"tribe:nav:actions:{user_id}"}]},
        ]}]

    elif page == "banlist":
        banned   = td.get("banned", [])
        members  = td["roles"]["officer"] + td["roles"]["members"]
        ban_text = "\n".join(f"{TRIBE_EMOJIS['ban']} <@{u}>" for u in banned) or "*(none)*"
        ban_opts = ([{"label": f"Ban {u}", "value": f"ban:{u}",
                      "description": f"Level {data.get(u,{}).get('level','?')}"}
                     for u in members] or [{"label": "No bannable members", "value": "none"}])
        unban_opts = ([{"label": f"Unban {u}", "value": f"unban:{u}"} for u in banned] or
                      [{"label": "No banned players", "value": "none"}])
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content":
             f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Ban List\n\n**Banned:**\n{ban_text}"},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:ban_action:{user_id}",
                "placeholder": "Ban a member...", "min_values": 1, "max_values": 1,
                "flows": {}, "options": ban_opts[:25]}]},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:unban_action:{user_id}",
                "placeholder": "Unban a player...", "min_values": 1, "max_values": 1,
                "flows": {}, "options": unban_opts[:25]}]},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                "custom_id": f"tribe:nav:actions:{user_id}"}]},
        ]}]

    return build_tribe_components(user_id, tribe_name, "main", sort_mode)

# ─────────────────────────────────────────────
# LEADERBOARD PANELS
# ─────────────────────────────────────────────

HUNTER_LB_STATS = {
    "Level":                lambda uid: data[uid].get("level", 1),
    "Money":                lambda uid: data[uid].get("money", 0),
    "Total Animals Caught": lambda uid: data[uid].get("total_caught", 0),
    "Prestige Count":       lambda uid: data[uid].get("prestige", 0),
    # ── Idle Hunter V2 — reward exploration, not just grind (Phase 45) ──
    "Mythic Creatures Slain": lambda uid: data[uid].get("stats", {}).get("myths_killed", 0),
    "Tracking Successes":     lambda uid: data[uid].get("stats", {}).get("tracks_completed", 0),
    "Regions Explored":       lambda uid: len(data[uid].get("guide_seen", [])),
}

LB_PERIOD_LABELS = {"all": "All-Time", "daily": "Today", "weekly": "This Week"}

def _lb_period_tag(period: str) -> str:
    """A string that changes exactly when a new daily/weekly period starts,
    so a stale snapshot is detected by simple inequality."""
    now = datetime.now(timezone.utc)
    if period == "daily":
        return now.strftime("%Y-%m-%d")
    if period == "weekly":
        y, w, _ = now.isocalendar()
        return f"{y}-W{w:02d}"
    return "all"

def _lb_period_value(uid: str, stat: str, period: str) -> int:
    """Current all-time value, or the amount gained since the current
    daily/weekly period started (snapshotted lazily, per user)."""
    stat    = stat if stat in HUNTER_LB_STATS else "Level"
    current = HUNTER_LB_STATS[stat](uid)
    if period == "all":
        return current
    d      = data[uid]
    snaps  = d.setdefault("lb_snap", {})
    tag    = _lb_period_tag(period)
    snap   = snaps.get(period)
    if not snap or snap.get("tag") != tag:
        snap = {"tag": tag, **{s: fn(uid) for s, fn in HUNTER_LB_STATS.items()}}
        snaps[period] = snap
    return max(0, current - snap.get(stat, current))

def get_server_user_ids(guild) -> list:
    if guild is None:
        return list(data.keys())
    member_ids = {str(m.id) for m in guild.members}
    return [uid for uid in data if uid in member_ids]

def _lb_eligible(uid: str) -> bool:
    """False for TESTER accounts — they are maxed for testing and must not appear
    on any leaderboard (global, server, personal ranks, rank-loss DMs, website)."""
    return not data.get(uid, {}).get("is_tester", False)

def build_leaderboard_v2_components(user_id: str, guild, mode: str = "hunter",
                                     scope: str = "global", stat: str = "Level",
                                     page: int = 0, period: str = "all") -> list:
    PS     = 10
    medals = {0: f"{emoji('first_place_medal')}", 1: f"{emoji('second_place_medal')}", 2: f"{emoji('third_place_medal')}"}
    if mode == "hunter":
        val_fn = lambda u: _lb_period_value(u, stat, period)
        cands  = get_server_user_ids(guild) if scope == "server" else list(data.keys())
        cands  = [u for u in cands if _lb_eligible(u)]
        ranked = sorted(cands, key=val_fn, reverse=True)
        total  = len(ranked)
        items  = ranked[page * PS:(page + 1) * PS]
        lines  = []
        for i, uid in enumerate(items):
            pos     = page * PS + i
            val     = val_fn(uid)
            val_str = f"◈ {val:,}" if stat == "Money" else f"**{val:,}**"
            you     = " ← you" if uid == user_id else ""
            fb = featured_badge_suffix(uid)
            lines.append(f"{medals.get(pos, f'**#{pos+1}**')} `{get_username(uid)}`{fb} — {val_str}{you}")
        vpos   = next((i for i, u in enumerate(ranked) if u == user_id), None)
        footer = f"-# Your rank: **#{vpos+1}**" if vpos is not None else "-# Not ranked."
        scope_label  = f"{guild.name} Server" if scope == "server" and guild else "Global"
        period_label = LB_PERIOD_LABELS.get(period, "All-Time")
        content = (
            f"### {emoji('leaderboard')} {scope_label} Leaderboard — {stat} ({period_label})\n\n"
            + "\n".join(lines)
            + f"\n\n{footer} · Page **{page+1}/{max(1,(total+PS-1)//PS)}**"
        )
    else:
        if scope == "server" and guild:
            mids = {str(m.id) for m in guild.members}
            vt   = [t for t, td in tribe_data.items()
                    if td["roles"]["leader"] in mids or
                    any(u in mids for u in td["roles"]["officer"] + td["roles"]["members"]
                        + td["roles"].get("recruits", []))]
        else:
            vt = list(tribe_data.keys())
        ranked  = sorted(vt, key=lambda t: tribe_data[t].get("level", 1), reverse=True)
        total   = len(ranked)
        items   = ranked[page * PS:(page + 1) * PS]
        vtribe  = data.get(user_id, {}).get("tribe")
        lines   = []
        for i, tname in enumerate(items):
            pos = page * PS + i
            lv  = tribe_data[tname].get("level", 1)
            cnt = 1 + len(tribe_data[tname]["roles"]["officer"]) + len(tribe_data[tname]["roles"]["members"])
            you = " ← your tribe" if tname == vtribe else ""
            lines.append(f"{medals.get(pos, f'**#{pos+1}**')} **{tname}** — Lv. {lv} · {cnt} members{you}")
        vpos   = next((i for i, t in enumerate(ranked) if t == vtribe), None)
        footer = f"-# Tribe rank: **#{vpos+1}**" if vpos is not None else "-# Not ranked."
        scope_label = f"{guild.name} Server" if scope == "server" and guild else "Global"
        content = (
            f"### {emoji('leaderboard')} {scope_label} Tribe Leaderboard\n\n"
            + "\n".join(lines)
            + f"\n\n{footer} · Page **{page+1}/{max(1,(total+PS-1)//PS)}**"
        )

    components = []
    if mode == "hunter":
        stat_options = [{"label": s, "value": s, "default": (s == stat)}
                       for s in HUNTER_LB_STATS.keys()]
        components.append({"type": 1, "components": [{"type": 3,
            "custom_id": f"lb:stat:{user_id}",
            "placeholder": "Sort by stat...", "options": stat_options}]})
        components.append({"type": 1, "components": [
            {"type": 2, "style": 3 if period == "all" else 2, "label": "All-Time",
             "custom_id": f"lb:period:all:{user_id}"},
            {"type": 2, "style": 3 if period == "daily" else 2, "label": "Daily",
             "custom_id": f"lb:period:daily:{user_id}"},
            {"type": 2, "style": 3 if period == "weekly" else 2, "label": "Weekly",
             "custom_id": f"lb:period:weekly:{user_id}"},
        ]})

    components.append({"type": 1, "components": [
        {"type": 2, "style": 3 if mode == "hunter" else 1, "label": "👤 Hunters",
         "custom_id": f"lb:mode:hunter:{user_id}"},
        {"type": 2, "style": 3 if mode == "tribe" else 1, "label": "Tribes",
         "custom_id": f"lb:mode:tribe:{user_id}"},
    ]})
    scope_label_btn = "Global" if scope == "server" else "Server"
    scope_key_btn   = "globe_with_meridians" if scope == "server" else "home"
    components.append({"type": 1, "components": [
        {"type": 2, "style": 1, "label": scope_label_btn, "emoji": emoji_partial(scope_key_btn),
         "custom_id": f"lb:scope:{user_id}"},
    ]})
    if mode == "hunter":
        cands_len = len([u for u in (get_server_user_ids(guild) if scope == "server"
                                     else list(data.keys())) if _lb_eligible(u)])
    else:
        cands_len = len(list(tribe_data.keys()))
    total_pages = max(1, (cands_len + PS - 1) // PS)
    components.append({"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Prev",
         "custom_id": f"lb:prev:{user_id}", "disabled": (page == 0)},
        {"type": 2, "style": 1, "label": "Next ▶",
         "custom_id": f"lb:next:{user_id}", "disabled": (page >= total_pages - 1)},
    ]})
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        *components,
    ]}]

# ─────────────────────────────────────────────
# RECORD PANELS
# ─────────────────────────────────────────────

def build_record_v2_components(user_id: str, biome_idx: int = 0) -> list:
    total_biomes = len(BIOME_LEVELS)
    biome_key    = BIOME_LEVELS[biome_idx][0]
    biome_req    = BIOME_LEVELS[biome_idx][1]
    user_level   = data[user_id].get("level", 1)
    if user_level < biome_req:
        content = (
            f"### {BIOME_EMOJIS[biome_key]} {BIOME_NAMES[biome_key]} — Record Book\n"
            f"{emoji('lock')} **Locked**\n-# Unlocks at Level **{biome_req}**."
        )
    else:
        record = data[user_id].get("record", {})
        lines  = []
        for animal in BIOME_ANIMALS[biome_key]:
            rarity     = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
            rarity_ico = RARITY_ICONS.get(rarity, "")
            entry      = record.get(animal)
            if entry:
                top_tool = max(entry.get("tools", {"?": 0}), key=entry.get("tools", {"?": 0}).get)
                lines.append(
                    f"{animal_emoji(animal)} {rarity_ico} **{animal}**\n"
                    f"-# ×{entry['count']} caught · ◈ {entry['total_earned']:,} · {emoji('wrench')} {top_tool}"
                )
            else:
                lines.append(f"{ANIMAL_EMOJI} {rarity_ico} **{animal}**\n-# Not caught yet")
        content = (f"### {BIOME_EMOJIS[biome_key]} {BIOME_NAMES[biome_key]} — Record Book\n\n"
                   + "\n\n".join(lines))
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Prev Biome",
         "custom_id": f"record:prev:{user_id}", "disabled": (biome_idx == 0)},
        {"type": 2, "style": 1, "label": "Next Biome ▶",
         "custom_id": f"record:next:{user_id}", "disabled": (biome_idx >= total_biomes - 1)},
        {"type": 2, "style": 2, "label": "◀ Back to Profile",
         "custom_id": f"profile:main:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

def build_record_standalone_v2_components(viewer_id: str, target_id: str, biome_idx: int = 0) -> list:
    total_biomes = len(BIOME_LEVELS)
    biome_key    = BIOME_LEVELS[biome_idx][0]
    biome_req    = BIOME_LEVELS[biome_idx][1]
    user_level   = data[target_id].get("level", 1)
    target_name  = data[target_id].get("_display_name", "Hunter")
    if user_level < biome_req:
        content = (
            f"### {BIOME_EMOJIS[biome_key]} {BIOME_NAMES[biome_key]} — {target_name}'s Record\n"
            f"{emoji('lock')} **Locked**"
        )
    else:
        record = data[target_id].get("record", {})
        lines  = []
        for animal in BIOME_ANIMALS[biome_key]:
            rarity     = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
            rarity_ico = RARITY_ICONS.get(rarity, "")
            entry      = record.get(animal)
            if entry:
                top_tool = max(entry.get("tools", {"?": 0}), key=entry.get("tools", {"?": 0}).get)
                lines.append(
                    f"{animal_emoji(animal)} {rarity_ico} **{animal}**\n"
                    f"-# ×{entry['count']} · ◈ {entry['total_earned']:,} · {emoji('wrench')} {top_tool}"
                )
            else:
                lines.append(f"{ANIMAL_EMOJI} {rarity_ico} **{animal}**\n-# Not caught yet")
        content = (f"### {BIOME_EMOJIS[biome_key]} {BIOME_NAMES[biome_key]} — {target_name}'s Record\n\n"
                   + "\n\n".join(lines))
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Prev Biome",
         "custom_id": f"record_cmd:prev:{viewer_id}:{target_id}", "disabled": (biome_idx == 0)},
        {"type": 2, "style": 1, "label": "Next Biome ▶",
         "custom_id": f"record_cmd:next:{viewer_id}:{target_id}",
         "disabled": (biome_idx >= total_biomes - 1)},
    ]}
    return [{"type": 17, "accent_color": _accent(viewer_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

# ─────────────────────────────────────────────
# LOG PANELS
# ─────────────────────────────────────────────

def build_log_v2_components(user_id: str, page: int = 0,
                            display_name: str = "", viewer_id: str = None) -> list:
    seg     = _profile_owner_seg(user_id, viewer_id)
    other   = _viewing_other(user_id, viewer_id)
    title   = f"### {emoji('eyes')} {display_name}'s Hunt Log" if other and display_name else f"### {emoji('list')} Hunt Log"
    log   = data[user_id].get("log", [])
    total = len(log)
    if not log or page >= total:
        content = f"{title}\nNo hunts recorded yet."
        btn_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Back to Profile",
             "custom_id": f"profile:main:{seg}"}
        ]}
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            btn_row,
        ]}]
    entry    = log[page]
    ts       = entry.get("ts", 0)
    biome    = entry.get("biome", "village")
    tool     = entry.get("tool", "Bare Hands")
    ammo_log = entry.get("ammo")
    catches  = entry.get("catches", [])
    total_xp = entry.get("total_xp", 0)
    lv_ups   = entry.get("level_ups", 0)
    catch_lines = []
    if entry.get("myth"):
        catch_lines.append(f"{RARITY_ICONS.get('mythic','')} **Encountered {entry['myth']}** "
                           f"— a mythic hunt (no other game)")
    for c in catches:
        animal     = c["animal"]
        rarity     = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        rarity_ico = RARITY_ICONS.get(rarity, "")
        rare_tag   = f" · {emoji('sparkles')} **Rare!**" if c.get("is_rare") else ""
        catch_lines.append(
            f"{animal_emoji(animal)} **{animal}**{rare_tag}\n"
            f"-# {rarity_ico} {rarity.title()} · +{c['xp_earned']:,} XP · ◈ {c['sell_value']:,}"
        )
    footer    = f"\n\n-# Total XP: **+{total_xp:,}**"
    if lv_ups:
        footer += f"\n-# {USER_EMOJIS['level_up']} Leveled up **×{lv_ups}**"
    ammo_line = f" · {ammo_emoji(ammo_log)} {ammo_log}" if ammo_log else ""
    content   = (
        f"{title} — Entry {page+1}/{total}\n"
        f"-# <t:{ts}:F> · {tool_emoji(tool)} **{tool}**{ammo_line} · "
        f"{BIOME_NAMES.get(biome, biome)}\n\n"
        + "\n\n".join(catch_lines) + footer
    )
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Newer",
         "custom_id": f"log:prev:{seg}", "disabled": (page == 0)},
        {"type": 2, "style": 1, "label": "Older ▶",
         "custom_id": f"log:next:{seg}", "disabled": (page >= total - 1)},
        {"type": 2, "style": 2, "label": "◀ Back to Profile",
         "custom_id": f"profile:main:{seg}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

def build_log_standalone_v2_components(user_id: str, page: int = 0) -> list:
    log   = data[user_id].get("log", [])
    total = len(log)
    if not log or page >= total:
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {emoji('list')} Hunt Log\nNo hunts recorded yet."},
        ]}]
    entry    = log[page]
    ts       = entry.get("ts", 0)
    biome    = entry.get("biome", "village")
    tool     = entry.get("tool", "Bare Hands")
    ammo_log = entry.get("ammo")
    catches  = entry.get("catches", [])
    total_xp = entry.get("total_xp", 0)
    lv_ups   = entry.get("level_ups", 0)
    catch_lines = []
    if entry.get("myth"):
        catch_lines.append(f"{RARITY_ICONS.get('mythic','')} **Encountered {entry['myth']}** "
                           f"— a mythic hunt (no other game)")
    for c in catches:
        animal     = c["animal"]
        rarity     = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        rarity_ico = RARITY_ICONS.get(rarity, "")
        rare_tag   = f" · {emoji('sparkles')} **Perfect Catch!**" if c.get("is_rare") else ""
        catch_lines.append(
            f"{animal_emoji(animal)} **{animal}**{rare_tag}\n"
            f"-# {rarity_ico} {rarity.title()} · +{c['xp_earned']:,} XP · ◈ {c['sell_value']:,}"
        )
    footer    = f"\n\n-# Total XP: **+{total_xp:,}**"
    if lv_ups:
        footer += f"\n-# {USER_EMOJIS['level_up']} Leveled up **×{lv_ups}**"
    ammo_line = f" · {ammo_emoji(ammo_log)} {ammo_log}" if ammo_log else ""
    content   = (
        f"### {emoji('list')} Hunt Log — Entry {page+1}/{total}\n"
        f"-# <t:{ts}:F> · {tool_emoji(tool)} **{tool}**{ammo_line} · "
        f"{BIOME_NAMES.get(biome, biome)}\n\n"
        + "\n\n".join(catch_lines) + footer
    )
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Newer",
         "custom_id": f"log_cmd:prev:{user_id}", "disabled": (page == 0)},
        {"type": 2, "style": 1, "label": "Older ▶",
         "custom_id": f"log_cmd:next:{user_id}", "disabled": (page >= total - 1)},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

# ─────────────────────────────────────────────
# PERSONAL LEADERBOARD
# ─────────────────────────────────────────────

def build_personal_leaderboard_components(user_id: str, display_name: str = "",
                                          viewer_id: str = None) -> list:
    d             = data[user_id]
    heading = (f"### {emoji('eyes')} {display_name}'s Rankings"
               if _viewing_other(user_id, viewer_id) else f"### {emoji('leaderboard')} Your Rankings")

    if not _lb_eligible(user_id):
        content = (
            f"{heading}\n\n"
            f"### {emoji('test_tube')} Not ranked — TESTER account\n"
            f"-# Tester accounts are excluded from every leaderboard.\n\n"
            f"-# ◈ {d['money']:,} · Lv. {d['level']} · {d.get('total_caught', 0):,} caught"
        )
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            *_profile_tab_rows("leaderboard", user_id, viewer_id),
        ]}]

    all_users     = [(uid, ud) for uid, ud in data.items() if _lb_eligible(uid)]
    money_sorted  = sorted(all_users, key=lambda x: x[1].get("money", 0), reverse=True)
    money_rank    = next((i+1 for i, (uid, _) in enumerate(money_sorted) if uid == user_id), len(money_sorted))
    level_sorted  = sorted(all_users, key=lambda x: (x[1].get("level", 1), x[1].get("xp", 0)), reverse=True)
    level_rank    = next((i+1 for i, (uid, _) in enumerate(level_sorted) if uid == user_id), len(level_sorted))
    caught_sorted = sorted(all_users, key=lambda x: x[1].get("total_caught", 0), reverse=True)
    caught_rank   = next((i+1 for i, (uid, _) in enumerate(caught_sorted) if uid == user_id), len(caught_sorted))
    total_players = len(all_users)
    tribe_nm      = d.get("tribe")
    tribe_section = ""
    if tribe_nm and tribe_nm in tribe_data:
        td_r = tribe_data[tribe_nm]
        tribe_members = [(uid, data[uid]) for uid in
                         ([td_r["roles"]["leader"]] + td_r["roles"]["officer"]
                          + td_r["roles"]["members"] + td_r["roles"].get("recruits", []))
                         if uid in data and _lb_eligible(uid)]
        t_money_sorted = sorted(tribe_members, key=lambda x: x[1].get("money", 0), reverse=True)
        t_money_rank   = next((i+1 for i, (uid, _) in enumerate(t_money_sorted) if uid == user_id), len(tribe_members))
        t_level_sorted = sorted(tribe_members, key=lambda x: (x[1].get("level", 1), x[1].get("xp", 0)), reverse=True)
        t_level_rank   = next((i+1 for i, (uid, _) in enumerate(t_level_sorted) if uid == user_id), len(tribe_members))
        tribe_section  = (
            f"\n\n### {TRIBE_EMOJIS['tribe']} Tribe Rankings — {tribe_nm}\n"
            f"{emoji('money_bag')} **Balance:** #{t_money_rank}/{len(tribe_members)}\n"
            f"{USER_EMOJIS['levels']} **Level:** #{t_level_rank}/{len(tribe_members)}"
        )
    content = (
        f"{heading}\n\n"
        f"### {emoji('earth')} Global\n"
        f"{emoji('money_bag')} **Balance:** #{money_rank:,}/{total_players:,}\n"
        f"{USER_EMOJIS['levels']} **Level:** #{level_rank:,}/{total_players:,}\n"
        f"{emoji('target')} **Animals:** #{caught_rank:,}/{total_players:,}"
        f"{tribe_section}\n\n"
        f"-# ◈ {d['money']:,} · Lv. {d['level']} · {d.get('total_caught', 0):,} caught"
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        *_profile_tab_rows("leaderboard", user_id, viewer_id),
    ]}]

# ─────────────────────────────────────────────
# ACHIEVEMENT + BADGE CHECKER
# ─────────────────────────────────────────────

async def check_achievements_and_badges(interaction: discord.Interaction, user_id: str):
    init_user(user_id)
    d = data[user_id]
    notifs = []

    all_tools_owned = all(t in d.get("owned_tools", []) for t in TOOLS)
    all_tools_used = all(t in d.get("stats", {}).get("tools_used", []) for t in TOOLS)

    ACH_SOURCES = {
        "daily_streak":    d.get("daily_streak", 0),
        "animals_caught":  d.get("total_caught", 0),
        "ammo_used":       d.get("stats", {}).get("ammo_used", 0),
        "tools_bought_all": 1 if all_tools_owned else 0,
        "tools_used_all":  1 if all_tools_used else 0,
        "crates_opened": d.get("stats", {}).get("crates_opened", 0),
    }

    for ach_key, tiers in ACHIEVEMENTS.items():
        if not tiers or not isinstance(tiers, list):
            continue
            
        current_val = ACH_SOURCES.get(ach_key, 0)
        ach_data = d["achievements"].setdefault(ach_key, {"claimed_up_to": -1})
        claimed_idx = ach_data.get("claimed_up_to", -1)

        for i, tier_entry in enumerate(tiers):
            if i <= claimed_idx:
                continue

            # Parse the tier format - modern format: (threshold, [(rtype, amount), ...])
            if isinstance(tier_entry, (list, tuple)) and len(tier_entry) >= 2:
                threshold = tier_entry[0]
                rewards = tier_entry[1]
                
                # Handle both list of tuples or single tuple
                if isinstance(rewards, (list, tuple)):
                    if len(rewards) == 2 and isinstance(rewards[0], str):
                        # Single reward as tuple
                        rewards = [rewards]
                else:
                    # Invalid format, skip
                    continue
            else:
                continue

            if current_val < threshold:
                break

            reward_strs = []
            for rtype, amount in rewards:
                # Route through the ledgered helpers so achievement payouts show
                # up in /bot economy (they used to bypass it entirely).
                if rtype == "money":
                    add_money(user_id, amount, "achievement")
                elif rtype == "gems":
                    add_gems(user_id, amount, "achievement")
                else:
                    d[rtype] = d.get(rtype, 0) + amount
                if rtype == "money":
                    d["total_money_earned"] = d.get("total_money_earned", 0) + amount
                icon = "◈" if rtype == "money" else emoji("gem")
                reward_strs.append(f"{icon} {amount:,}")

            d["achievements"][ach_key]["claimed_up_to"] = i
            reward_text = " + ".join(reward_strs)
            label = ACH_LABELS.get(ach_key, ach_key.replace("_", " ").title())
            notifs.append((
                f"{emoji('achievements')} Achievement Unlocked!",
                f"**{label}** — Tier {i+1}\nReward: **{reward_text}**",
                0xF1C40F,
            ))
            
            title_str = ACHIEVEMENT_TITLES.get(ach_key, {}).get(str(threshold))
            if title_str:
                earned = d.setdefault("earned_titles", [])
                if title_str not in earned:
                    earned.append(title_str)
                    notifs.append((
                        f"{emoji('label')} Title Unlocked!",
                        f'**"{title_str}"**\n-# Equip it with /title',
                        0x3498DB,
                    ))

    # Badges
    all_ach_done = all(
        len(ACHIEVEMENTS.get(k, [])) > 0 and
        d["achievements"].get(k, {}).get("claimed_up_to", -1) >= len(ACHIEVEMENTS[k]) - 1
        for k in ACHIEVEMENTS if ACHIEVEMENTS.get(k) and isinstance(ACHIEVEMENTS[k], list)
    )

    for badge_key, bdef in BADGES.items():
        stat = bdef["stat"]
        gold_t = bdef["gold"]
        plat_t = bdef["plat"]
        abbr = bdef["abbr"]
        label = bdef["label"]
        
        if stat == "game_master":
            cur = 1 if all_ach_done else 0
        else:
            cur = get_badge_stat(user_id, stat)
            
        bstate = d["badges"].setdefault(badge_key, {"tier": 0, "notified_gold": False, "notified_plat": False})
        cur_tier = bstate.get("tier", 0)

        if cur_tier < 1 and cur >= gold_t:
            bstate["tier"] = 1
            # First badge ever → feature it automatically (changeable in
            # /progression → Badges).
            if not d.get("featured_badge"):
                d["featured_badge"] = badge_key
            if not bstate.get("notified_gold"):
                bstate["notified_gold"] = True
                notifs.append((f"{emoji('first_place_medal')} Gold Badge Earned!",
                    f"**{label}** `[{abbr}🥇]`\n-# Keep going for Platinum!", 0xF1C40F))

        if plat_t and cur_tier < 2 and cur >= plat_t:
            bstate["tier"] = 2
            if not bstate.get("notified_plat"):
                bstate["notified_plat"] = True
                notifs.append((f"{emoji('trophy')} Platinum Badge Earned!",
                    f"**{label}** `[{abbr}🏆]`", 0xE8E8E8))

    all_badge_plat = all(
        d["badges"].get(k, {}).get("tier", 0) >= (2 if BADGES[k]["plat"] else 1)
        for k in BADGES
    )
    if all_badge_plat:
        gm = d["badges"].setdefault("game_master", {"tier": 0, "notified_gold": False, "notified_plat": False})
        if gm.get("tier", 0) < 2 and not gm.get("notified_plat"):
            gm["tier"] = 2
            gm["notified_plat"] = True
            notifs.append((f"{emoji('trophy')} Platinum Badge Earned!",
                "**Game Master** `[GM🏆]`\nYou've completed everything. Legendary.", 0xE8E8E8))

    # Send notifications
    for title, body, color in notifs:
        try:
            route = Route("POST", "/webhooks/{application_id}/{token}",
                          application_id=interaction.application_id, token=interaction.token)
            await interaction.client.http.request(route, json={
                "flags": V2_FLAGS | 64,
                "components": [{"type": 17, "accent_color": color, "spoiler": False,
                    "components": [{"type": 10, "content": f"### {title}\n{body}"}]}],
                "allowed_mentions": {"parse": []},
            })
        except Exception as e:
            print(f"Achievement notif error: {e}")

# ─────────────────────────────────────────────
# NAVIGATION DISPATCHER
# ─────────────────────────────────────────────

async def _navigate(interaction: discord.Interaction, user_id: str,
                    panel: str, display_name: str = ""):
    dn = display_name or interaction.user.display_name
    if panel == "menu":
        await smart_update_v2(interaction, build_menu_components(user_id, dn))
    elif panel == "shop":
        await smart_update_v2(interaction, build_shop_components(user_id, "boosts"))
    elif panel == "biome":
        await smart_update_v2(interaction, build_biome_panel_components(user_id))
    elif panel == "world":
        await smart_update_v2(interaction, build_world_components(user_id, await _world_goal_line(interaction)))
    elif panel == "allregions":
        await smart_update_v2(interaction, build_world_regions_components(user_id))
    elif panel in ("guide", "fieldguide"):
        await smart_update_v2(interaction, build_collection_components(user_id))
    elif panel in ("refer", "referral"):
        _code = await _referral_get_code(user_id)
        try:
            _st = await backend.referral_stats(user_id)
        except Exception:
            _st = {"invited": 0, "qualified": 0}
        await smart_update_v2(interaction, build_refer_components(user_id, _code, _st))
    elif panel in ("expedition", "exped"):
        await smart_update_v2(interaction, build_expedition_components(user_id))
    elif panel == "color":
        await smart_update_v2(interaction, build_color_panel_components(user_id))
    elif panel == "equip":
        await smart_update_v2(interaction, build_equip_components(user_id))
    elif panel == "inv":
        await smart_update_v2(interaction, build_inventory_components(user_id, dn, standalone=True))
    elif panel == "idle":
        async with user_transaction(user_id):
            idle_tick(user_id)
        await smart_update_v2(interaction, build_idle_components(user_id))
    elif panel == "quests":
        await smart_update_v2(interaction, build_quests_components(user_id))
    elif panel == "hpath":
        await smart_update_v2(interaction, build_hunters_path_components(user_id))
    elif panel == "daily":
        await smart_update_v2(interaction, build_daily_components(user_id))
    elif panel == "prestige":
        await smart_update_v2(interaction, build_prestige_components(user_id))
    elif panel == "mail":
        await smart_update_v2(interaction, build_mail_components(user_id, "tribe"))
    elif panel == "help":
        _help_page[user_id] = 0
        await smart_update_v2(interaction, build_help_components(user_id, 0))
    elif panel in ("crates", "craft"):
        await smart_update_v2(interaction, build_craft_components(user_id))
    elif panel == "update":
        _update_page[user_id] = 0
        await smart_update_v2(interaction, build_update_components(user_id, "all", 0))
    elif panel == "lottery":
        await smart_update_v2(interaction, build_lottery_components(user_id))
    elif panel == "gamble":
        await smart_update_v2(interaction, build_gamble_menu(user_id))
    elif panel == "leaderboard":
        _lb_state[user_id] = {"mode": "hunter", "scope": "global", "stat": "Level",
                               "page": 0, "period": "all", "guild": interaction.guild}
        await smart_update_v2(interaction, build_leaderboard_v2_components(
            user_id, interaction.guild, "hunter", "global", "Level", 0, "all"))
    elif panel == "tribe":
        tribe_nm = data[user_id].get("tribe")
        if tribe_nm and tribe_nm in tribe_data:
            await smart_update_v2(interaction, build_tribe_components(user_id, tribe_nm, "main"))
        else:
            await smart_update_v2(interaction, build_menu_components(user_id, dn))
    elif panel == "profile":
        await smart_update_v2(interaction, build_profile_components(user_id, dn, active_panel="main"))
    elif panel == "progression":
        await smart_update_v2(interaction, build_progression_hub(user_id))
    elif panel == "events":
        await smart_update_v2(interaction, build_events_components(user_id))
    elif panel == "settings":
        await smart_update_v2(interaction, build_settings_components(user_id))
    else:
        await smart_update_v2(interaction, build_menu_components(user_id, dn))

# ─────────────────────────────────────────────
# COMMON INIT
# ─────────────────────────────────────────────

async def _common_init(interaction: discord.Interaction, *, auto_defer: bool = True) -> str | None:
    """Run the shared per-interaction bootstrap (init user, maintenance / ban /
    verify gates) and return the caller's user id, or ``None`` when a gate has
    already answered the interaction and the caller should stop.

    ``auto_defer`` (default ``True``) makes this ACK the interaction with a
    deferred response so the caller can reply on the followup route. Pass
    ``auto_defer=False`` from handlers that may need to open a modal — those must
    keep the interaction unacknowledged and defer themselves once they know a
    modal is not being sent.
    """
    global maintenance_mode, maintenance_warning, maintenance_message, _maintenance_warned

    # Startup race guard — Discord can deliver interactions before on_ready's
    # load_all_data() has populated `data` from SQLite. Without this, an
    # unlucky first command sees an empty `data` dict, init_user() treats the
    # player as brand new, and they get a phantom level-1/no-gear record
    # instead of their real save. Refuse everything (type-4, no defer needed)
    # until the load has actually finished.
    if not _data_loaded_ok:
        await _raw(interaction, {"type": 4, "data": {
            "flags": V2_FLAGS | 64,
            "components": [{"type": 17, "accent_color": 0xE67E22, "spoiler": False,
                "components": [{"type": 10, "content":
                    "### `⏳` Still Starting Up\n"
                    "Idle Hunter just restarted and is loading player data. "
                    "Try again in a few seconds."
                }]}],
            "allowed_mentions": {"parse": []},
        }})
        return None

    user_id = str(interaction.user.id)

    # A banned player must still be able to open the appeal modal, which requires
    # the interaction to stay unacknowledged — let that one custom_id past the gates.
    raw_cid = ""
    if interaction.type == discord.InteractionType.component:
        raw_cid = ((getattr(interaction, "data", {}) or {}).get("custom_id", "")) or ""
    is_appeal = raw_cid.startswith("ban:appeal")
    # The verify card's own "Refresh" button (verify:refresh:<id>) must not be
    # swallowed by the verify gate below, or it can never refresh the code.
    is_verify_ui = raw_cid.startswith("verify:")

    async def _maybe_defer():
        if not auto_defer:
            return
        try:
            await interaction.response.defer()
        except Exception:
            pass

    # Admin bypass
    if user_id in BOT_ADMIN_ID:
        init_user(user_id)
        data[user_id]["username"] = interaction.user.name
        await update_user_servers(user_id, interaction.guild)
        await _maybe_defer()
        return user_id

    # Maintenance — type 4 immediate response, no defer
    if maintenance_mode:
        await _raw(interaction, {"type": 4, "data": {
            "flags": V2_FLAGS | 64,
            "components": [{"type": 17, "accent_color": 0xE67E22, "spoiler": False,
                "components": [{"type": 10, "content":
                    f"### {emoji('wrench')} Bot Maintenance\n**Idle Hunter is currently under maintenance.**\n\n"
                    f"Reason: {maintenance_message}\n"
                    "Please be patient — we'll be back shortly!\n\n"
                    f"-# All your data is safe. See you soon, hunter. {emoji('idle_camp')}"
                }]}],
            "allowed_mentions": {"parse": []},
        }})
        return None

    init_user(user_id)
    data[user_id]["username"] = interaction.user.name
    init_ban_record(user_id)
    travel_tick(user_id)   # land the player if a trip finished while they were away
    craft_tick(user_id)    # collect any crystals finished while they were away
    await update_user_servers(user_id, interaction.guild)

    # Ban — type 4 immediate (skipped for the appeal button so its modal can open)
    if is_banned(user_id) and not is_appeal:
        await _raw(interaction, {"type": 4, "data": {
            "flags": V2_FLAGS | 64,
            "components": build_ban_components(user_id),
            "allowed_mentions": {"parse": []},
        }})
        return None

    if is_appeal:
        # Leave the interaction unacknowledged; the ban:appeal handler sends a modal.
        return user_id

    # Defer now (unless the caller opted out to keep the option of a modal open).
    await _maybe_defer()

    # Let the verify card's Refresh button run even while verify-locked.
    if is_verify_ui:
        return user_id

    tick_verify(user_id)
    if data[user_id]["verify"]["needed"]:
        # Ephemeral for component clicks so the verify code isn't posted publicly.
        await send_v2_followup(
            interaction, verify_needed_components(user_id),
            ephemeral=(interaction.type == discord.InteractionType.component),
        )
        return None

    # Only emit the one-time maintenance warning once the interaction is already
    # acknowledged — otherwise it would consume the initial response that a
    # component handler still needs for its update.
    if (maintenance_warning and user_id not in _maintenance_warned
            and interaction.response.is_done()):
        _maintenance_warned.add(user_id)
        try:
            await send_ephemeral_v2(
                interaction,
                f"### {emoji('warning')} Maintenance Coming Soon\n"
                f"**Idle Hunter will enter maintenance shortly.**\n\n"
                f"Reason: {maintenance_message}\n\n"
                "-# You will only see this message once.",
                0xF39C12,
            )
        except Exception:
            pass

    return user_id


async def _modal_gate(interaction: discord.Interaction, user_id: str | None = None) -> bool:
    """Re-run the maintenance / ban / verify gates for a **modal submission**.

    discord.py routes ``Modal.on_submit`` directly, bypassing both
    :func:`_tree_gate` (slash commands) and the component gate in
    :func:`_dispatch_component`. Any modal that spends currency or mutates state
    must call this first — a form opened before a ban / maintenance / verify-lock
    would otherwise still commit. Returns ``False`` (after answering the
    interaction) when the caller must stop.
    """
    uid = str(user_id or interaction.user.id)
    if uid in BOT_ADMIN_ID:
        return True
    if maintenance_mode:
        await send_ephemeral_v2(
            interaction,
            f"### {emoji('wrench')} Bot Maintenance\n**Idle Hunter is currently under maintenance.**\n\n"
            f"Reason: {maintenance_message}\n\n-# Please try again shortly.",
            0xE67E22)
        return False
    init_user(uid)
    init_ban_record(uid)
    if is_banned(uid):
        await send_ephemeral_v2(
            interaction,
            "### `🔨` You are banned\nYou can't do that right now. Open `/menu` to appeal.",
            0xE74C3C)
        return False
    tick_verify(uid)
    if data[uid]["verify"]["needed"]:
        await send_ephemeral_v2(
            interaction,
            "### `🤖` Verification required\nRun `/verify` (or open `/menu`) before doing that.",
            0xF39C12)
        return False
    return True


# Commands that must stay reachable even while a player is verify-locked, banned
# or the bot is in maintenance — the escape hatches.
_CMD_GATE_EXEMPT = {"verify", "help", "invite"}

async def _tree_gate(interaction: discord.Interaction) -> bool:
    """Global pre-check for EVERY slash command: maintenance → ban → verify.

    Runs before the command body, so it also covers commands that never call
    :func:`_common_init` (``/report``, ``/suggest``, ``/rules`` …). Component
    clicks are gated separately inside :func:`_dispatch_component`. Returns
    ``False`` after answering the interaction to stop the command from running.
    """
    if interaction.type is discord.InteractionType.autocomplete:
        return True

    # Resolve the root command name. discord.py's ``interaction.command`` can come
    # back ``None`` (resolver miss on a stale/desynced tree); fall back to the raw
    # payload name so a resolver hiccup can never lock a player out of the escape
    # hatches — most importantly ``/verify`` itself.
    cmd  = interaction.command
    if cmd is not None:
        root = cmd.qualified_name.split(" ", 1)[0]
    else:
        root = ((getattr(interaction, "data", {}) or {}).get("name", "") or "")
    if root in _CMD_GATE_EXEMPT:
        return True

    user_id = str(interaction.user.id)
    if user_id in BOT_ADMIN_ID:
        return True

    init_user(user_id)

    if maintenance_mode:
        await _raw(interaction, {"type": 4, "data": {
            "flags": V2_FLAGS | 64,
            "components": [{"type": 17, "accent_color": 0xE67E22, "spoiler": False,
                "components": [{"type": 10, "content":
                    f"### {emoji('wrench')} Bot Maintenance\n**Idle Hunter is currently under maintenance.**\n\n"
                    f"Reason: {maintenance_message}\n"
                    "Please be patient — we'll be back shortly!\n\n"
                    f"-# All your data is safe. See you soon, hunter. {emoji('idle_camp')}"
                }]}],
            "allowed_mentions": {"parse": []},
        }})
        return False

    init_ban_record(user_id)
    if is_banned(user_id):
        await _raw(interaction, {"type": 4, "data": {
            "flags": V2_FLAGS | 64,
            "components": build_ban_components(user_id),
            "allowed_mentions": {"parse": []},
        }})
        return False

    if data[user_id]["verify"]["needed"]:
        await _raw(interaction, {"type": 4, "data": {
            "flags": V2_FLAGS | 64,
            "components": verify_needed_components(user_id),
            "allowed_mentions": {"parse": []},
        }})
        return False

    return True

bot.tree.interaction_check = _tree_gate


def _resolve_crate_reward(user_id: str, crate_name: str) -> tuple[dict, dict, dict]:
    """Apply a single crate's reward to user_id — money/gems/boost/title plus
    the bonus-gemstone roll, quest progress and stat bookkeeping. Must be
    called from inside a ``user_transaction``. Shared by the manual /use crate
    flow and auto-open-on-pickup (Settings). Returns (reward, extras, hp_result)."""
    reward = open_crate(crate_name)

    if reward["type"] == "money":
        add_money(user_id, reward["amount"], "crate")
        data[user_id]["total_money_earned"] = data[user_id].get("total_money_earned", 0) + reward["amount"]
    elif reward["type"] == "gems":
        add_gems(user_id, reward["amount"], "crate")
    elif reward["type"] == "perm_boost":
        add_personal_boost(user_id, reward["stat"], reward["amount"])
    elif reward["type"] == "temp_boost":
        tb = data[user_id].setdefault("temp_boosts", [])
        tb.append({
            "stat": reward["stat"],
            "amount": reward["amount"],
            "expires_at": time.time() + reward["minutes"] * 60,
        })
        # Prune expired entries
        data[user_id]["temp_boosts"] = [b for b in tb if b["expires_at"] > time.time()]
    elif reward["type"] == "title":
        title = reward["title"]
        earned = data[user_id].setdefault("earned_titles", [])
        if title not in earned:
            earned.append(title)

    data[user_id]["stats"]["crates_opened"] = data[user_id]["stats"].get("crates_opened", 0) + 1
    _hp_result = hunters_path_maybe_complete(user_id)

    # ── Bonus roll: decorative gemstone. Trophies no longer drop from
    # crates (2026-09-16) — a trophy now means "I actually defeated this
    # Mythical," so crates can't shortcut that or fake a "discovery."
    extras: dict = {}
    crate_rarity = CRATE_RARITY.get(crate_name, "common")
    if random.random() < CRATE_GEMSTONE_CHANCE:
        add_gemstone(user_id, crate_rarity, 1)
        extras["gemstone"] = crate_rarity

    # Quests advance here — only after a crate was actually spent.
    quest_progress(user_id, "crates_opened_quest", 1)
    quest_progress(user_id, "crate_tier_opened",   1, crate_name=crate_name)

    return reward, extras, _hp_result


async def _open_crate_and_show(interaction, user_id: str, crate_name: str):
    if crate_name not in CRATE_TIERS:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Unknown crate.", 0xE74C3C)
        return
    have = True
    async with user_transaction(user_id):
        # Check + consume under the lock: a double-click used to pass the
        # pre-lock check twice and then KeyError on the already-deleted entry.
        inv = data[user_id].setdefault("crate_inv", {})
        if inv.get(crate_name, 0) <= 0:
            have = False
        else:
            inv[crate_name] -= 1
            if inv[crate_name] == 0:
                del inv[crate_name]
            reward, extras, _hp_result = _resolve_crate_reward(user_id, crate_name)
    if not have:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You don't have any **{crate_name}**.", 0xE74C3C)
        return

    await smart_update_v2(interaction, build_crate_result_components(user_id, crate_name, reward, extras))
    await _hunters_path_notify(interaction, user_id, _hp_result)
    await check_achievements_and_badges(interaction, user_id)

# ─────────────────────────────────────────────
# SUGGESTION / REPORT / APPEAL / BLACKJACK STORES
# ─────────────────────────────────────────────
# These survive restarts via runtime_state.json (see below) so their message
# buttons don't turn into dead "not found" clicks.
_suggestion_store: dict[str, dict] = {}
_report_store:     dict[str, dict] = {}
# appeal_id -> {user_id, reason, channel_msg_id, handled}
_appeal_store:     dict[str, dict] = {}

RUNTIME_STATE_FILE = "runtime_state.json"

def _encode_runtime_state() -> dict:
    def enc_sugg(e: dict) -> dict:
        e = dict(e)
        e["votes"] = {k: sorted(v) for k, v in e.get("votes", {}).items()}
        return e
    def enc_rep(e: dict) -> dict:
        e = dict(e)
        e["seen"] = sorted(e.get("seen", []))
        return e
    return {
        "suggestions": {k: enc_sugg(v) for k, v in _suggestion_store.items()},
        "reports":     {k: enc_rep(v)  for k, v in _report_store.items()},
        "appeals":     dict(_appeal_store),
        "blackjack":   dict(_bj_state),
        "world_map":   {"url": _world_map_url},
        "event":       (dict(_active_event) if get_active_event() else None),
        "world_conditions": dict(_world_conditions),
        "world_sighting":   (dict(_active_sighting) if _active_sighting else None),
        "last_sighting_end": _last_sighting_end,
        "event_scheduler":  dict(_event_scheduler),
        "last_weekly_lb_tag": _last_weekly_lb_tag,
    }

def load_runtime_state() -> None:
    try:
        with open(RUNTIME_STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    for k, v in raw.get("suggestions", {}).items():
        v["votes"] = {kk: set(vv) for kk, vv in v.get("votes", {}).items()}
        _suggestion_store[k] = v
    for k, v in raw.get("reports", {}).items():
        v["seen"] = set(v.get("seen", []))
        _report_store[k] = v
    _appeal_store.update(raw.get("appeals", {}))
    _bj_state.update(raw.get("blackjack", {}))
    global _world_map_url, _active_event, _world_conditions, _active_sighting, _event_scheduler, _last_sighting_end
    global _last_weekly_lb_tag
    _saved_map = (raw.get("world_map") or {}).get("url", "")
    if _saved_map and not _cdn_url_expiring(_saved_map, skew_seconds=0):
        _world_map_url = _saved_map
    _saved_ev = raw.get("event")
    if _saved_ev and _saved_ev.get("ends_ts", 0) > time.time():
        _active_event = _saved_ev
    _wc = raw.get("world_conditions") or {}
    now = time.time()
    _world_conditions = {b: c for b, c in _wc.items()
                         if isinstance(c, dict) and c.get("ends_ts", 0) > now}
    _sg = raw.get("world_sighting")
    if _sg and _sg.get("ends_ts", 0) > now:
        _active_sighting = _sg
    try:
        _last_sighting_end = float(raw.get("last_sighting_end", 0) or 0)
    except (TypeError, ValueError):
        _last_sighting_end = 0.0
    _es = raw.get("event_scheduler")
    if isinstance(_es, dict):
        _event_scheduler.update(_es)
    _last_weekly_lb_tag = str(raw.get("last_weekly_lb_tag", "") or "")
    print(f"✅ Runtime state loaded "
          f"({len(_suggestion_store)} suggestions, {len(_report_store)} reports, "
          f"{len(_appeal_store)} appeals, {len(_bj_state)} blackjack hands)")

# ─────────────────────────────────────────────
# ADMIN AUDIT LOG
# ─────────────────────────────────────────────

ADMIN_LOG_FILE = "admin_actions.log"

def admin_audit(admin_id, action: str, detail: str) -> None:
    _append_line_bg(ADMIN_LOG_FILE, json.dumps({
        "ts": int(time.time()), "admin": str(admin_id),
        "action": action, "detail": detail,
    }))

def _cid_opens_modal(parts: list[str], values: list) -> bool:
    """True when this component custom_id leads to ``interaction.response.send_modal``.

    Those handlers must run with the interaction still unacknowledged, so
    ``on_interaction`` must not defer them.
    """
    if not parts:
        return False
    a  = parts[0]
    b  = parts[1] if len(parts) > 1 else ""
    c  = parts[2] if len(parts) > 2 else ""

    if a == "hunter_color_hex":
        return True
    if a == "crate" and b == "buy":
        return True
    if a == "shop" and b in ("ammo_buy", "ammo_buy_acc"):
        return True
    if a == "ban" and b == "appeal":
        return True
    if a == "lottery" and b == "buy":
        return True
    if a == "tribe_create":
        return True
    if a == "tribe" and b in ("action", "action_select"):
        sub = (values[0] if (b == "action_select" and values) else c)
        return sub in ("invite", "set_desc", "leave")
    if a == "gamble" and c in ("setbet", "deal"):
        return True
    if a == "suggestion" and b in ("agree", "neutral", "disagree"):
        return True
    if a == "admin" and b in ("modal", "act"):
        return True
    if a == "updadm" and b in ("add", "edit"):
        return True
    if a == "announce":
        # Not actually a modal — a public announcement-card button. It has no
        # baked-in owner, so it must reply ephemerally to whoever clicked
        # rather than through the auto-defer (which would post publicly).
        return True
    return False


# Guards against the *same* component interaction id being processed twice —
# a gateway redelivery or an internal re-dispatch. (A genuine double-click sends
# two distinct interaction ids; the per-handler "does this store own it" checks
# below are what absorb those, and a second bot instance running on the same
# token.) Bounded so it can't grow without end.
_handled_interaction_ids: "deque[int]" = deque(maxlen=4096)
_handled_interaction_set: set[int] = set()

def _already_handled(interaction_id: int) -> bool:
    if interaction_id in _handled_interaction_set:
        return True
    if len(_handled_interaction_ids) == _handled_interaction_ids.maxlen:
        _handled_interaction_set.discard(_handled_interaction_ids[0])
    _handled_interaction_ids.append(interaction_id)
    _handled_interaction_set.add(interaction_id)
    return False


@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        await _dispatch_component(interaction)
    except discord.HTTPException as e:
        # Responding to the interaction failed — almost always "already
        # acknowledged" / "unknown interaction" because another bot instance (or
        # another path) already answered it. Log a one-liner, and don't push a
        # scary ephemeral at the user: someone else's response is already there.
        cid = ((getattr(interaction, "data", {}) or {}).get("custom_id", "")) or "?"
        logger.warning("interaction response failed (custom_id=%s, instance=%s): %s", cid, INSTANCE_ID, e)
    except Exception:
        cid = ((getattr(interaction, "data", {}) or {}).get("custom_id", "")) or "?"
        logger.exception("component handler crashed (custom_id=%s)", cid)
        if interaction.type == discord.InteractionType.component:
            try:
                await send_ephemeral_v2(
                    interaction,
                    f"{emoji('warning')} Something went wrong handling that. Please try again.",
                    0xE74C3C,
                )
            except Exception:
                pass


# ── Cross-user panels ────────────────────────────────────────────────────
# When someone clicks a button on ANOTHER player's panel, instead of the old
# "this isn't your panel" rejection they get their OWN top-level panel for that
# feature, sent as an ephemeral (the original owner's message is untouched).
# Only safe, view-your-own-state panels are listed here — admin / gift / tribe
# mutations / confirmations / ban / verify still reject a non-owner.
# Value: fn(clicker_id: str, interaction) -> components list.
_CROSS_USER_PANELS = {
    "menu":           lambda uid, it: build_menu_components(uid, it.user.display_name),
    "nav":            lambda uid, it: build_menu_components(uid, it.user.display_name),
    "shop":           lambda uid, it: build_shop_components(uid),
    "tools":          lambda uid, it: build_equip_components(uid),
    "gamble":         lambda uid, it: build_gamble_menu(uid),
    "inv":            lambda uid, it: build_inventory_components(uid, it.user.display_name),
    "crate":          lambda uid, it: build_crate_shop_components(uid),
    "craft":          lambda uid, it: build_craft_components(uid),
    "idle":           lambda uid, it: build_idle_components(uid),
    "settings":       lambda uid, it: build_settings_components(uid),
    "quests":         lambda uid, it: build_quests_components(uid),
    "daily":          lambda uid, it: build_daily_components(uid),
    "badge":          lambda uid, it: build_badges_components(uid),
    "ach":            lambda uid, it: build_achievements_components(uid),
    "title":          lambda uid, it: build_title_components(uid),
    "lottery":        lambda uid, it: build_lottery_components(uid),
    "biome":          lambda uid, it: build_biome_panel_components(uid),
    "world":          lambda uid, it: build_world_components(uid),
    "guide":          lambda uid, it: build_collection_components(uid),
    "collection":     lambda uid, it: build_collection_components(uid),
    "exped":          lambda uid, it: build_expedition_components(uid),
    "mail":           lambda uid, it: build_mail_components(uid),
    "lb":             lambda uid, it: build_leaderboard_v2_components(uid, it.guild),
    "rules":          lambda uid, it: build_rules_components(uid, 0),
    "help":           lambda uid, it: build_help_components(uid, 0),
    "update":         lambda uid, it: build_update_components(uid),
    "tutorial_guide": lambda uid, it: build_tutorial_guide_components(uid, 0),
    "record_cmd":     lambda uid, it: build_record_standalone_v2_components(uid, uid, 0),
    "log_cmd":        lambda uid, it: build_log_standalone_v2_components(uid, 0),
}


async def _dispatch_component(interaction: discord.Interaction):
    # Application commands self-bootstrap in their own callbacks; modal submits
    # are routed by discord.py's modal store. Only component interactions are
    # handled here.
    if interaction.type != discord.InteractionType.component:
        return

    if _already_handled(interaction.id):
        return

    raw    = getattr(interaction, "data", {}) or {}
    cid    = raw.get("custom_id", "")
    values = raw.get("values", [])
    parts  = cid.split(":")

    valid = await _common_init(interaction, auto_defer=False)
    if not valid: return

    # Defer here (not in _common_init) so modal-opening handlers keep the
    # unacknowledged interaction they need for send_modal().
    if not _cid_opens_modal(parts, values) and not interaction.response.is_done():
        try:
            await interaction.response.defer()
        except Exception:
            pass

    # ── Cross-user panel redirect ─────────────
    # Clicking someone else's panel button opens the clicker's OWN version of
    # that panel (ephemeral) rather than rejecting them. Only the safe view
    # panels in _CROSS_USER_PANELS; everything else still owner-guards below.
    if len(parts) >= 2 and parts[-1].isdigit():
        _clicker = str(interaction.user.id)
        if parts[-1] != _clicker and parts[0] in _CROSS_USER_PANELS:
            try:
                _own = _CROSS_USER_PANELS[parts[0]](_clicker, interaction)
            except Exception:
                logger.exception("cross-user panel build failed (custom_id=%s)", cid)
                _own = None
            if _own:
                await send_v2_followup(interaction, _own, ephemeral=True)
                return
            # builder failed — fall through to the normal owner-guarded handler

    # ── PUBLIC ANNOUNCEMENT BUTTONS ───────────
    # No baked-in owner — anyone in the server can click these, so the
    # clicking user IS the target, derived fresh each time rather than
    # checked against a custom_id segment like every other button here.
    if parts[0] == "announce":
        clicker = str(interaction.user.id)
        init_user(clicker)
        sub = parts[1] if len(parts) > 1 else ""
        if sub == "events":
            await send_v2_followup(interaction, build_events_components(clicker), ephemeral=True)
            return
        if sub == "leaderboard":
            _lb_state[clicker] = {"mode": "hunter", "scope": "global", "stat": "Level",
                                   "page": 0, "period": "all", "guild": interaction.guild}
            await send_v2_followup(interaction, build_leaderboard_v2_components(
                clicker, interaction.guild, "hunter", "global", "Level", 0, "all"), ephemeral=True)
            return
        if sub == "hunt":
            can_hunt, remaining = await RateLimiter.can_hunt(clicker, HUNT_COOLDOWN * ev_hunt_cd_mult())
            if not can_hunt:
                await send_ephemeral_v2(interaction,
                    f"{emoji('cooldown')} Wait **{remaining:.1f}s** before hunting!", 0xE67E22)
                return
            async with user_transaction(clicker):
                result = run_hunt(clicker)
            if not result.get("ok"):
                await send_v2_followup(interaction, build_menu_components(
                    clicker, interaction.user.display_name), ephemeral=True)
                return
            await award_tribe_xp(clicker, "hunt", catches=len(result.get("catches", [])),
                                 biome=result.get("biome", ""))
            await _event_hunt_hook(clicker)
            await _guild_goal_contribute(interaction, clicker, len(result.get("catches", [])))
            await send_v2_followup(interaction, build_hunt_components(clicker, result), ephemeral=True)
            return
        if sub == "travel":
            biome_key = parts[2] if len(parts) > 2 else ""
            if biome_key not in BIOME_NAMES:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Unknown region.", 0xE74C3C)
                return
            lvl_req = next((lvl for k, lvl in BIOME_LEVELS if k == biome_key), 1)
            if data[clicker]["level"] < lvl_req:
                await send_ephemeral_v2(interaction,
                    f"{emoji('cross_mark')} {BIOME_NAMES[biome_key]} unlocks at Level {lvl_req}.", 0xE74C3C)
                return
            travel_tick(clicker)
            if biome_key == data[clicker]["biome"] and not is_traveling(clicker):
                await send_ephemeral_v2(interaction, f"{emoji('location_pin')} You're already here.", 0xE67E22)
                return
            # Same confirmation card every travel path uses — a public
            # announce-card click is no exception to "confirm before departing".
            await send_v2_followup(interaction, _travel_confirm_components(clicker, biome_key), ephemeral=True)
            return
        return

    # ── ADMIN CONTROL PANEL ───────────────────
    if parts[0] == "admin":
        global maintenance_warning
        if not is_admin(interaction):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Admins only.", 0xE74C3C)
            return
        admin_id = parts[-1]
        kind     = parts[1] if len(parts) > 1 else "home"
        arg      = parts[2] if len(parts) > 3 else ""

        if kind == "home":
            await smart_update_v2(interaction, build_admin_panel(admin_id, "home"))
            return
        if kind == "nav":
            await smart_update_v2(interaction, build_admin_panel(admin_id, arg))
            return
        if kind == "navsel":
            dest = values[0] if values else "home"
            await smart_update_v2(interaction, build_admin_panel(admin_id, dest))
            return
        if kind in ("event", "eventsel"):
            if kind == "eventsel" or arg == "start":
                if get_active_event():
                    await smart_update_v2(interaction, build_admin_panel(
                        admin_id, "events", f"{emoji('cross_mark')} An event is already running — stop it first."))
                    return
                ekey = (values[0] if values else "") if kind == "eventsel" else "admin_buff"
                ev = start_event(ekey, admin_id)
                if not ev:
                    await smart_update_v2(interaction, build_admin_panel(
                        admin_id, "events", f"{emoji('cross_mark')} Unknown event."))
                    return
                admin_audit(admin_id, "event_start", f"{ekey} until {int(ev['ends_ts'])}")
                spec = EVENTS[ekey]
                bot.loop.create_task(_broadcast_event_start(ev))
                await smart_update_v2(interaction, build_admin_panel(
                    admin_id, "events",
                    f"{spec['emoji']} **{spec['name']}** started & announced — ends <t:{int(ev['ends_ts'])}:R>."))
                return
            if arg == "stop":
                stop_active_event()
                admin_audit(admin_id, "event_stop", active_event_key() or "?")
                await smart_update_v2(interaction, build_admin_panel(
                    admin_id, "events", "`⏹️` Event stopped."))
                return
            return
        if kind in ("modal", "act"):
            # "modal": op is in the custom_id (arg). "act": op is the picked select value.
            op = (values[0] if values else "") if kind == "act" else arg
            modal = _admin_modal_for(op, admin_id)
            if modal is not None:
                await interaction.response.send_modal(modal)
            else:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Unknown admin action.", 0xE74C3C)
            return
        if kind == "cancel":
            _admin_pending.pop(arg, None)
            await smart_update_v2(interaction, build_admin_panel(admin_id, "home", "`✖` Action cancelled."))
            return
        if kind == "confirm":
            pend = _admin_pending.pop(arg, None)
            if not pend or pend["admin_id"] != str(admin_id):
                await smart_update_v2(interaction, build_admin_panel(
                    admin_id, "home", f"{emoji('cross_mark')} That confirmation expired — run the action again."))
                return
            try:
                section, note = await _admin_apply(pend["op"], pend["params"], admin_id)
            except Exception as e:
                logger.exception("admin apply failed")
                section, note = _admin_section_for(pend["op"]), f"{emoji('cross_mark')} Action failed: {e}"
            await smart_update_v2(interaction, build_admin_panel(admin_id, section, note))
            return
        if kind == "do":
            if arg == "maint_toggle":
                # Enabling now goes through the maint_enable modal (it needs a
                # reason); this button only ever fires to disable.
                await _admin_stage(
                    interaction, admin_id, "maint_toggle", {},
                    "Disable maintenance mode — the bot reopens to everyone.")
                return
            if arg == "wipe_crates":
                holders = sum(1 for d in data.values()
                              if d.get("crate_inv") or d.get("shards") or d.get("crystals")
                              or d.get("craft_queue"))
                await _admin_stage(
                    interaction, admin_id, "wipe_crates", {},
                    f"`🧨` **WIPE EVERYONE'S CRATES** — clears `crate_inv`, `shards`, `crystals` and "
                    f"`craft_queue` for **all {len(data):,}** players ({holders:,} currently hold some). "
                    f"Gemstones are kept. Cannot be undone.")
                return
            if arg == "maint_warn_toggle":
                maintenance_warning = not maintenance_warning
                if not maintenance_warning:
                    _maintenance_warned.clear()
                save_config()
                admin_audit(admin_id, "maint_warn_toggle", f"warning={maintenance_warning}")
                note = (f"{emoji('yellow_ball')} Maintenance warning **on**." if maintenance_warning
                        else "`⚪` Maintenance warning **off** (warned list cleared).")
                await smart_update_v2(interaction, build_admin_panel(admin_id, "maint", note))
                return
            if arg == "v2_sighting":
                sg = spawn_world_sighting(force=True)
                admin_audit(admin_id, "v2_sighting", sg.get("biome", "?") if sg else "none")
                note = (f"{emoji('siren')} Sighting spawned in **{BIOME_NAMES.get(sg['biome'], sg['biome'])}** "
                        f"({sg['creature']})." if sg else f"{emoji('cross_mark')} Couldn't spawn a sighting.")
                await smart_update_v2(interaction, build_admin_panel(admin_id, "info", note))
                return
            if arg == "v2_conditions":
                ch = rotate_world_conditions(force_fill=True)
                admin_audit(admin_id, "v2_conditions", ",".join(ch))
                await smart_update_v2(interaction, build_admin_panel(
                    admin_id, "info",
                    f"`🌦️` World topped up — {len(_world_conditions)} region(s) enhanced."))
                return
            await smart_update_v2(interaction, build_admin_panel(admin_id, "maint", f"{emoji('cross_mark')} Unknown action."))
            return
        return

    # ── TRIBE CREATE (modal) ──────────────────
    if parts[0] == "tribe_create":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        if data[owner_id].get("tribe"):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You're already in a tribe.", 0xE74C3C)
            return
        await interaction.response.send_modal(TribeCreateModal(owner_id))
        return

    # ── RULES ─────────────────────────────────
    if parts[0] == "rules":
        owner_id = parts[-1]

        if parts[1] == "prev":
            _rules_page[owner_id] = max(0, _rules_page.get(owner_id, 0) - 1)
        elif parts[1] == "next":
            _rules_page[owner_id] = _rules_page.get(owner_id, 0) + 1
        elif parts[1] == "noop" or parts[1] == "noop2":
            return

        await smart_update_v2(interaction, build_rules_components(owner_id, _rules_page.get(owner_id, 0)))
        return

    # ── HELP (paged) ──────────────────────────
    if parts[0] == "help":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        if parts[1] == "prev":
            _help_page[owner_id] = max(0, _help_page.get(owner_id, 0) - 1)
        elif parts[1] == "next":
            _help_page[owner_id] = _help_page.get(owner_id, 0) + 1
        elif parts[1] == "noop":
            return
        await smart_update_v2(interaction, build_help_components(owner_id, _help_page.get(owner_id, 0)))
        return

    if parts[0] == "update":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        action = parts[1]

        if action == "view":
            update_idx = int(parts[2])
            await smart_update_v2(interaction, build_update_components(owner_id, "view", update_idx))
            return

        elif action == "back_to_list":
            page = _update_page.get(owner_id, 0)
            await smart_update_v2(interaction, build_update_components(owner_id, "all", page))
            return

        elif action == "prev":
            _update_page[owner_id] = max(0, _update_page.get(owner_id, 0) - 1)
            await smart_update_v2(interaction, build_update_components(owner_id, "all", _update_page[owner_id]))
            return

        elif action == "next":
            _update_page[owner_id] = _update_page.get(owner_id, 0) + 1
            await smart_update_v2(interaction, build_update_components(owner_id, "all", _update_page[owner_id]))
            return

        elif action == "noop":
            return

    # ── UPDATE CONTROL (admin: add/edit/delete via modal) ──
    if parts[0] == "updadm":
        if not is_admin(interaction):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Admins only.", 0xE74C3C)
            return
        admin_id = parts[-1]
        action   = parts[1]
        page     = _upd_admin_page.get(admin_id, 0)

        if action == "add":
            await interaction.response.send_modal(UpdateAddModal(admin_id))
            return
        if action == "edit":
            idx = int(parts[2])
            if not (0 <= idx < len(UPDATE)):
                await smart_update_v2(interaction, build_update_admin_components(
                    admin_id, page, f"{emoji('cross_mark')} That update no longer exists."))
                return
            await interaction.response.send_modal(UpdateEditModal(admin_id, idx))
            return
        if action == "refresh":
            await smart_update_v2(interaction, build_update_admin_components(admin_id, page))
            return
        if action == "prev":
            await smart_update_v2(interaction, build_update_admin_components(admin_id, page - 1))
            return
        if action == "next":
            await smart_update_v2(interaction, build_update_admin_components(admin_id, page + 1))
            return
        if action == "noop":
            return
        if action == "delsel":
            idx = int(values[0]) if values else -1
            if not (0 <= idx < len(UPDATE)):
                await smart_update_v2(interaction, build_update_admin_components(admin_id, page))
                return
            u = UPDATE[idx]
            await smart_update_v2(interaction, [{"type": 17, "accent_color": 0xE74C3C,
                "spoiler": False, "components": [
                {"type": 10, "content":
                    f"### {emoji('trash')} Delete update #{idx + 1}?\n"
                    f"**{u.get('title', '(untitled)')}**\n-# This does not un-send the channel announcement."},
                {"type": 14, "divider": True, "spacing": 1},
                {"type": 1, "components": [
                    {"type": 2, "style": 4, "label": "Delete",
                     "custom_id": f"updadm:delok:{idx}:{admin_id}"},
                    {"type": 2, "style": 2, "label": "Cancel",
                     "custom_id": f"updadm:refresh:{admin_id}"},
                ]},
            ]}])
            return
        if action == "delok":
            removed = _apply_update_delete(admin_id, int(parts[2]))
            note = (f"{emoji('trash')} Deleted **{removed.get('title', '(untitled)')}**."
                    if removed else f"{emoji('cross_mark')} That update no longer exists.")
            await smart_update_v2(interaction, build_update_admin_components(admin_id, page, note))
            return
        return

    # ── QUESTS ────────────────────────────────
    if parts[0] == "quests":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
 
        if parts[1] == "back":
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
            return
 
        if parts[1] == "noop":
            return   # disabled page-counter button

        if parts[1] == "goweekly":
            await smart_update_v2(interaction, build_weekly_quests_components(owner_id))
            return

        if parts[1] == "page":
            page = int(parts[2])
            _quest_page[owner_id] = page
            await smart_update_v2(interaction, build_quests_components(owner_id, page))
            return
 
        if parts[1] == "claim":
            quest_id = parts[2]
            result   = quest_claim(owner_id, quest_id)
            if not result["ok"]:
                reason_msg = {
                    "not_complete":    f"{emoji('cross_mark')} That quest isn't completed yet.",
                    "already_claimed": f"{emoji('warning')} Already claimed.",
                    "not_found":       f"{emoji('cross_mark')} Quest not found.",
                }.get(result.get("reason", ""), f"{emoji('cross_mark')} Couldn't claim.")
                await send_ephemeral_v2(interaction, reason_msg, 0xE74C3C)
                return
 
            await award_tribe_xp(owner_id, "task")

            xp_msg = f"+{result['xp']:,} XP"
            if result.get("money"):
                xp_msg += f" · ◈{result['money']:,}"
            if result.get("gems"):
                xp_msg += f" · {emoji('gem')}{result['gems']}"
            if result.get("crate"):
                xp_msg += f" · 1× {result['crate']}"
            if result["level_ups"] == 1:
                xp_msg += f" · Level up! Now level **{result['level']}**"
            elif result["level_ups"] > 1:
                xp_msg += f" · Level up ×{result['level_ups']}! Now level **{result['level']}**"

            await send_ephemeral_v2(interaction, f"{emoji('check_mark')} Quest complete! {xp_msg}", 0x2ECC71)
            if result.get("milestone_hit"):
                total_now = data[owner_id]["stats"].get("daily_quests_completed_total", 0)
                await send_ephemeral_v2(interaction,
                    f"{emoji('gem')} **Milestone reached!** {total_now:,} daily quests completed "
                    f"lifetime — **+{result['milestone_gems']} gems**.", 0x9B59B6)
            await _hunters_path_notify(interaction, owner_id, result.get("hunters_path_result"))
            page = _quest_page.get(owner_id, 0)
            await smart_update_v2(interaction, build_quests_components(owner_id, page))
            return

    # ── WEEKLY QUEST ───────────────────────────
    if parts[0] == "wquests" and parts[1] == "godaily":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await smart_update_v2(interaction, build_quests_components(owner_id, _quest_page.get(owner_id, 0)))
        return

    if parts[0] == "wquests" and parts[1] == "claim":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        quest_id = parts[2]
        result   = quest_claim(owner_id, quest_id, list_key="weekly_quests")
        if not result["ok"]:
            reason_msg = {
                "not_complete":    f"{emoji('cross_mark')} That quest isn't completed yet.",
                "already_claimed": f"{emoji('warning')} Already claimed.",
                "not_found":       f"{emoji('cross_mark')} Quest not found.",
            }.get(result.get("reason", ""), f"{emoji('cross_mark')} Couldn't claim.")
            await send_ephemeral_v2(interaction, reason_msg, 0xE74C3C)
            return

        await award_tribe_xp(owner_id, "task")

        xp_msg = f"+{result['xp']:,} XP"
        if result.get("money"):
            xp_msg += f" · ◈{result['money']:,}"
        if result.get("gems"):
            xp_msg += f" · {emoji('gem')}{result['gems']}"
        if result.get("crate"):
            xp_msg += f" · 1× {result['crate']}"
        if result["level_ups"] == 1:
            xp_msg += f" · Level up! Now level **{result['level']}**"
        elif result["level_ups"] > 1:
            xp_msg += f" · Level up ×{result['level_ups']}! Now level **{result['level']}**"

        await send_ephemeral_v2(interaction, f"{emoji('check_mark')} Weekly quest complete! {xp_msg}", 0x2ECC71)
        await _hunters_path_notify(interaction, owner_id, result.get("hunters_path_result"))
        await smart_update_v2(interaction, build_weekly_quests_components(owner_id))
        return

    # ── CRATES ────────────────────────────────
    if parts[0] == "crate":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        action = parts[1]

        if action == "buy":
            crate_name = parts[2]
            if crate_name not in CRATE_TIERS:
                await send_ephemeral_v2(interaction, "Unknown crate.", 0xE74C3C)
                return
            await interaction.response.send_modal(CrateBuyModal(owner_id, crate_name))
            return


        if action == "shop":
            await smart_update_v2(interaction, build_crate_shop_components(owner_id))
            return

        if action == "open_menu":
            await smart_update_v2(interaction, build_crate_open_menu_components(owner_id))
            return

        if action == "open_select":
            crate_name = values[0] if values else None
            if not crate_name or crate_name not in CRATE_TIERS:
                return
            await _open_crate_and_show(interaction, owner_id, crate_name)
            return

        if action == "open_again":
            crate_name = parts[2]
            await _open_crate_and_show(interaction, owner_id, crate_name)
            return

        return

    # ── CRAFT (shards → crystals) ─────────────
    if parts[0] == "craft":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "open":
            await smart_update_v2(interaction, build_craft_components(owner_id))
            return

        if parts[1] == "queue":
            rarity = values[0] if values else None
            if rarity not in RARITY_KEYS:
                return
            async with user_transaction(owner_id):
                res = queue_crystal_craft(owner_id, rarity)
            if res.get("ok") and res.get("instant"):
                notice = (f"{ADMIN_BUFF_EVENT['emoji']} Instant fuse — a {CRYSTAL_ICONS[rarity]} "
                          f"**{_rarity_label(rarity)} Crystal** is ready now.")
            elif res.get("ok"):
                notice = (f"{emoji('check_mark')} Fusing a {CRYSTAL_ICONS[rarity]} **{_rarity_label(rarity)} Crystal** — "
                          f"ready <t:{int(res['done_ts'])}:R>.")
            else:
                notice = {
                    "not_enough_shards": f"{emoji('cross_mark')} Need {CRYSTAL_SHARD_COST} {_rarity_label(rarity)} shards.",
                    "queue_full":        f"{emoji('cross_mark')} The forge queue is full.",
                    "bad_rarity":        f"{emoji('cross_mark')} Unknown rarity.",
                }.get(res.get("reason"), f"{emoji('cross_mark')} Couldn't craft that.")
            await smart_update_v2(interaction, build_craft_components(owner_id, notice))
            return

        return

    # ── GLOBAL EVENT MINI-GAMES ───────────────
    if parts[0] == "event":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        init_user(owner_id)
        sub = parts[1]

        if sub == "back":
            await smart_update_v2(interaction, build_events_components(owner_id))
            return
        if sub == "shop":
            await smart_update_v2(interaction, _build_event_shop_panel(owner_id, parts[2]))
            return
        if sub == "buy":
            key, idx = parts[2], int(parts[3])
            async with user_transaction(owner_id):
                msg = event_shop_buy(owner_id, key, idx)
            await send_ephemeral_v2(interaction, msg, 0x2ECC71 if msg.startswith(f"{emoji('check_mark')}") else 0xE74C3C)
            await smart_update_v2(interaction, _build_event_shop_panel(owner_id, key))
            return
        if sub == "fox":
            async with user_transaction(owner_id):
                res = fox_route(owner_id, parts[2])
            await send_ephemeral_v2(interaction, res["msg"], 0x2ECC71)
            await smart_update_v2(interaction, build_events_components(owner_id))
            await check_achievements_and_badges(interaction, owner_id)
            return
        if sub == "ship":
            act = parts[2]
            async with user_transaction(owner_id):
                res = ship_bank(owner_id) if act == "bank" else ship_dive(owner_id, act)
            await send_ephemeral_v2(interaction, res["msg"], 0x2ECC71)
            await smart_update_v2(interaction, build_events_components(owner_id))
            return
        if sub == "duck":
            if parts[2] == "vote":
                async with user_transaction(owner_id):
                    msg = duck_vote(owner_id, parts[3])
            else:  # feed
                async with user_transaction(owner_id):
                    msg = duck_feed(owner_id)
            await send_ephemeral_v2(interaction, msg, 0x2ECC71)
            await smart_update_v2(interaction, build_events_components(owner_id))
            await check_achievements_and_badges(interaction, owner_id)
            return
        return

    # ── SETTINGS / TUTORIAL GUIDE ─────────────
    if parts[0] == "settings":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "nav" and parts[2] == "main":
            await smart_update_v2(interaction, build_settings_components(owner_id))
            return

        if parts[1] == "tutorial":
            await smart_update_v2(interaction, build_tutorial_guide_components(owner_id, 0))
            return

        if parts[1] == "toggle":
            key = parts[2]
            init_notif(owner_id)
            if key in ("daily_dm", "leaderboard_dm"):
                data[owner_id]["notif"][key] = not data[owner_id]["notif"][key]
            elif key == "tips_enabled":
                data[owner_id]["tips_enabled"] = not data[owner_id].get("tips_enabled", True)
            elif key == "auto_open_crates":
                data[owner_id]["auto_open_crates"] = not data[owner_id].get("auto_open_crates", False)
            await smart_update_v2(interaction, build_settings_components(owner_id))
            return

    if parts[0] == "tutorial_guide":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "nav":
            idx = int(parts[2])
            await smart_update_v2(interaction, build_tutorial_guide_components(owner_id, idx))
            return

    # ── ONBOARDING (interactive first hunt) ───
    if parts[0] == "onb":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        init_user(owner_id)
        action = parts[1] if len(parts) > 2 else ""
        if not onboarding_active(owner_id):
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
            return

        if action == "track":
            _onb_set_step(owner_id, "catch")
        elif action in ("follow", "observe"):
            # Retired "tracks" step buttons — only reachable via a stale panel
            # still open in Discord from before this step was cut. Same
            # destination as "track" above.
            analytics(owner_id, "onboarding_first_track", choice=action)
            _onb_set_step(owner_id, "catch")
        elif action == "shoot":
            async with user_transaction(owner_id):
                animal, val, xp, level_ups = _onb_grant_first_catch(owner_id)
                _onb_set_step(owner_id, "sell")
            analytics(owner_id, "onboarding_first_catch", animal=animal, value=val, level_ups=level_ups)
        elif action == "sell":
            async with user_transaction(owner_id):
                sold = sell_all_inv(owner_id)
                _onb_set_step(owner_id, "trial")
            analytics(owner_id, "onboarding_first_sell", earned=sold.get("total", 0))
        elif action == "trial_hunt":
            # Grants the Training Shortbow loan + its guaranteed double-catch,
            # then goes straight into the scripted danger encounter — the same
            # "instant catches + one dangerous target" panel a real hunt shows.
            async with user_transaction(owner_id):
                results, tr = _onb_grant_trial_and_catches(owner_id)
                danger_animal = _onb_start_scripted_danger(owner_id)
                _onb_set_step(owner_id, "danger")
            analytics(owner_id, "onboarding_trial_granted", tool=tr["tool"])
            extra_catches = [{"animal": a} for a, _v, _x in results]
            await smart_update_v2(interaction,
                build_animal_fight_components(owner_id, intro=True, extra_catches=extra_catches))
            return
        elif action == "continue":
            # Retired "world"/"mystery" step buttons — only reachable via a
            # stale panel still open in Discord from before those steps were
            # cut. _onb_set_step() canonicalizes either target straight to
            # "done" (see _ONB_RETIRED_STEP_SKIP).
            step = _onb(owner_id).get("step")
            nxt = {"world": "mystery", "mystery": "done"}.get(step)
            if nxt:
                async with user_transaction(owner_id):
                    _onb_set_step(owner_id, nxt)
                if _onb(owner_id).get("step") == "done":
                    analytics(owner_id, "onboarding_completed")
        elif action == "pack":
            key = parts[2] if len(parts) > 3 else ""
            async with user_transaction(owner_id):
                ok = _onb_grant_pack(owner_id, key)
                _onb_set_step(owner_id, "done")
            analytics(owner_id, "onboarding_pack_selected", pack=key, granted=ok)
            analytics(owner_id, "onboarding_completed")
        elif action == "skip":
            async with user_transaction(owner_id):
                _onb_set_step(owner_id, "done")
            analytics(owner_id, "onboarding_skipped")
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
            return
        await smart_update_v2(interaction, build_onboarding_components(owner_id))
        return

    # ── HUNT ──────────────────────────────────
    if parts[0] == "hunt":
        owner_id   = parts[-1]
        clicker_id = str(interaction.user.id)

        if parts[1] == "again":
            # A stranger clicking someone else's "Hunt" button just hunts for
            # themselves — their result is posted as a new message in the channel
            # (their own panel) so the original owner's message is left alone.
            actor    = owner_id if clicker_id == owner_id else clicker_id
            is_owner = actor == owner_id

            init_user(actor)
            if onboarding_active(actor):
                comps = build_onboarding_components(actor)
                if is_owner:
                    await smart_update_v2(interaction, comps)
                else:
                    await send_v2_followup(interaction, comps, ephemeral=True)
                return
            can_hunt, remaining = await RateLimiter.can_hunt(actor, HUNT_COOLDOWN * ev_hunt_cd_mult())
            if not can_hunt:
                await send_ephemeral_v2(interaction, f"{emoji('cooldown')} Wait **{remaining:.1f}s** before hunting again!", 0xE67E22)
                return
            async with user_transaction(actor):
                result = run_hunt(actor)
            if result.get("ok"):
                await award_tribe_xp(actor, "hunt", catches=len(result.get("catches", [])),
                                     biome=result.get("biome", ""))
                await _event_hunt_hook(actor)
                await _guild_goal_contribute(interaction, actor, len(result.get("catches", [])))
            if result.get("verify"):
                await send_ephemeral_v2(interaction,
                    f"{emoji('lock')} **Verification Required**\nRun {_verify_cmd_ref()} with code `{data[actor]['verify']['code']}`",
                    0xE67E22)
                return
            if result.get("tool_locked"):
                await send_ephemeral_v2(interaction,
                    f"{emoji('cross_mark')} **{result['biome_name']}** needs Tier {result['req_tier']}+. Use </equip:{COMMAND_ID.get('equip','0')}>",
                    0xE74C3C)
                return
            if result.get("no_ammo"):
                ran_out = result.get("ran_out", False)
                atype   = result.get("ammo_type", "ammo")
                if ran_out:
                    msg = f"{emoji('impact')} You ran out of {atype}! Your ammo was unequipped."
                elif result.get("owns_ammo"):
                    msg = (f"{emoji('warning')} **{result['tool_name']}** needs {atype} equipped. "
                           f"You own some — load it in </equip:{COMMAND_ID.get('equip','0')}>.")
                else:
                    msg = (f"{emoji('warning')} **{result['tool_name']}** needs {atype} equipped. "
                           f"Buy some in </shop:{COMMAND_ID.get('shop','0')}> → Ammo!")
                await send_ephemeral_v2(interaction, msg, 0xE67E22)
                return
            if result.get("traveling"):
                await send_ephemeral_v2(interaction,
                    f"{emoji('plane')} You're in transit to **{BIOME_NAMES.get(result['dest'], result['dest'])}** — "
                    f"arrives <t:{result['arrive_ts']}:R>. You can't hunt until you land.",
                    0xE67E22)
                return
            if result.get("boss_pending"):
                comps = build_myth_encounter_components(actor, result["creature"])
                if is_owner:
                    await smart_update_v2(interaction, comps)
                else:
                    await send_v2_followup(interaction, comps)
                return
            if result.get("tracking_pending") or result.get("tracking_encounter") or tracking_active(actor):
                comps = build_tracking_components(actor)
                if is_owner:
                    await smart_update_v2(interaction, comps)
                else:
                    await send_v2_followup(interaction, comps)
                return
            if result.get("animal_fight_pending") or animal_fight_active(actor):
                comps = build_animal_fight_components(actor)
                if is_owner:
                    await smart_update_v2(interaction, comps)
                else:
                    await send_v2_followup(interaction, comps)
                return
            if not result["ok"]:
                await send_ephemeral_v2(interaction,
                    f"{emoji('cooldown')} Hunt again <t:{result.get('cooldown_ts', int(time.time()+3))}:R>.",
                    0xE67E22)
                return
            data[actor]["_display_name"] = interaction.user.display_name
            if is_owner:
                await smart_update_v2(interaction, build_hunt_components(actor, result))
            else:
                await send_v2_followup(interaction, build_hunt_components(actor, result))
            await maybe_send_hunt_tip(interaction, result)
            await _hunters_path_notify(interaction, actor, result.get("hunters_path_result"))
            return

        if clicker_id != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "fight":
            init_user(owner_id)
            # custom_id: hunt:fight:<action>:<eid>:<user_id> — the encounter id ties
            # the button to this specific boss; a stale button is rejected.
            action = parts[2] if len(parts) >= 5 else ""
            eid    = parts[3] if len(parts) >= 5 else None
            boss   = data[owner_id].get("_boss")
            if not boss or boss.get("eid") != eid or action not in FIGHT_ACTIONS:
                await smart_update_v2(interaction,
                    build_menu_components(owner_id, interaction.user.display_name))
                return
            async with user_transaction(owner_id):
                boss = data[owner_id].get("_boss")
                outcome = (myth_fight_turn(owner_id, action)
                           if boss and boss.get("eid") == eid else {"kind": "none"})
            if outcome.get("kind") == "none":
                await smart_update_v2(interaction,
                    build_menu_components(owner_id, interaction.user.display_name))
                return
            if outcome.get("kind") == "ongoing":
                await smart_update_v2(interaction, build_myth_fight_components(owner_id))
                return
            if outcome.get("kind") == "kill":
                await award_tribe_xp(owner_id, "myth_kill")
                await _guild_goal_contribute(interaction, owner_id, 1)
            await smart_update_v2(interaction, build_myth_outcome_components(owner_id, outcome))
            await check_everything(interaction, owner_id)
            return

        if parts[1] == "track":
            # custom_id: hunt:track:<action>:<trid>:<uid>
            init_user(owner_id)
            action = parts[2] if len(parts) >= 5 else ""
            trid   = parts[3] if len(parts) >= 5 else None
            tr     = data[owner_id].get("tracking")
            if not tr or tr.get("id") != trid:
                if data[owner_id].get("_boss"):
                    await smart_update_v2(interaction, build_myth_fight_components(owner_id))
                else:
                    await smart_update_v2(interaction,
                        build_menu_components(owner_id, interaction.user.display_name))
                return
            async with user_transaction(owner_id):
                tr = data[owner_id].get("tracking")
                outcome = (tracking_choice(owner_id, action)
                           if tr and tr.get("id") == trid else {"kind": "none"})
            k = outcome.get("kind")
            if k == "ongoing":
                await smart_update_v2(interaction,
                    build_tracking_components(owner_id, outcome.get("line", "")))
            elif k == "located":
                await smart_update_v2(interaction, build_myth_fight_components(owner_id, intro=True))
            elif k == "lost":
                await smart_update_v2(interaction, build_tracking_outcome_components(owner_id, outcome))
                await check_everything(interaction, owner_id)
            else:
                await smart_update_v2(interaction,
                    build_menu_components(owner_id, interaction.user.display_name))
            return

        if parts[1] == "afight":
            # custom_id: hunt:afight:<action>:<eid>:<uid> — a normal dangerous-
            # animal fight (separate from the mythic hunt:fight above).
            init_user(owner_id)
            action = parts[2] if len(parts) >= 5 else ""
            eid    = parts[3] if len(parts) >= 5 else None
            f = data[owner_id].get("fight")
            if not f or f.get("kind") != "animal" or f.get("eid") != eid:
                await smart_update_v2(interaction,
                    build_menu_components(owner_id, interaction.user.display_name))
                return
            async with user_transaction(owner_id):
                f = data[owner_id].get("fight")
                outcome = (animal_fight_turn(owner_id, action)
                           if f and f.get("kind") == "animal" and f.get("eid") == eid
                           else {"kind": "none"})
            k = outcome.get("kind")
            if k == "none":
                await smart_update_v2(interaction,
                    build_menu_components(owner_id, interaction.user.display_name))
                return
            if k == "ongoing":
                await smart_update_v2(interaction, build_animal_fight_components(owner_id))
                return
            # A scripted onboarding fight resolves into the guided flow instead
            # of the generic outcome panel — never leaves a new player stranded.
            if onboarding_active(owner_id):
                async with user_transaction(owner_id):
                    comps = _onb_after_scripted_danger(owner_id, outcome)
                await smart_update_v2(interaction, comps)
                return
            await smart_update_v2(interaction, build_animal_fight_outcome_components(owner_id, outcome))
            await check_everything(interaction, owner_id)
            return

        if parts[1] in ("kill", "run"):
            # Legacy buttons from before the fight rework — re-show the fight.
            init_user(owner_id)
            if data[owner_id].get("_boss"):
                await smart_update_v2(interaction, build_myth_fight_components(owner_id))
            else:
                await smart_update_v2(interaction,
                    build_menu_components(owner_id, interaction.user.display_name))
            return

        if parts[1] == "sell_all":
            init_user(owner_id)
            async with user_transaction(owner_id):
                sold = sell_all_inv(owner_id)
            if sold.get("count"):
                analytics(owner_id, "sell", count=sold["count"], total=sold["total"])
            await smart_update_v2(interaction, build_hunt_sold_components(owner_id, sold))
            return

        if parts[1] == "back":
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
            return

    # ── MENU NAV ──────────────────────────────
    if parts[0] == "menu":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "nav":
            panel = values[0] if values else "menu"
            init_user(owner_id)
            if onboarding_active(owner_id):
                await smart_update_v2(interaction, build_onboarding_components(owner_id))
                return
            if panel == "hunt":
                can_hunt, remaining = await RateLimiter.can_hunt(owner_id, HUNT_COOLDOWN * ev_hunt_cd_mult())
                if not can_hunt:
                    await send_ephemeral_v2(interaction, f"{emoji('cooldown')} Wait **{remaining:.1f}s** before hunting!", 0xE67E22)
                    return
                async with user_transaction(owner_id):
                    result = run_hunt(owner_id)
                if result.get("ok"):
                    await award_tribe_xp(owner_id, "hunt", catches=len(result.get("catches", [])),
                                         biome=result.get("biome", ""))
                    await _event_hunt_hook(owner_id)
                    await _guild_goal_contribute(interaction, owner_id, len(result.get("catches", [])))
                if result.get("verify"):
                    await send_ephemeral_v2(interaction,
                        f"{emoji('lock')} **Verification Required**\nRun {_verify_cmd_ref()} with code `{data[owner_id]['verify']['code']}`",
                        0xE67E22)
                    return
                if result.get("tool_locked"):
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cross_mark')} **{result['biome_name']}** needs Tier {result['req_tier']}+.",
                        0xE74C3C)
                    return
                if result.get("no_ammo"):
                    ran_out = result.get("ran_out", False)
                    atype   = result.get("ammo_type", "ammo")
                    if ran_out:
                        msg = f"{emoji('impact')} You ran out of {atype}! Your ammo was unequipped."
                    elif result.get("owns_ammo"):
                        msg = (f"{emoji('warning')} **{result['tool_name']}** needs {atype} equipped. "
                               f"You own some — load it in </equip:{COMMAND_ID.get('equip','0')}>.")
                    else:
                        msg = (f"{emoji('warning')} **{result['tool_name']}** needs {atype} equipped. "
                               f"Buy some in </shop:{COMMAND_ID.get('shop','0')}> → Ammo!")
                    await send_ephemeral_v2(interaction, msg, 0xE67E22)
                    return
                if result.get("traveling"):
                    await send_ephemeral_v2(interaction,
                        f"{emoji('plane')} In transit to **{BIOME_NAMES.get(result['dest'], result['dest'])}** — "
                        f"arrives <t:{result['arrive_ts']}:R>.", 0xE67E22)
                    return
                if result.get("boss_pending"):
                    await smart_update_v2(interaction,
                        build_myth_encounter_components(owner_id, result["creature"]))
                    return
                if result.get("tracking_pending") or result.get("tracking_encounter") or tracking_active(owner_id):
                    await smart_update_v2(interaction, build_tracking_components(owner_id))
                    return
                if result.get("animal_fight_pending") or animal_fight_active(owner_id):
                    await smart_update_v2(interaction, build_animal_fight_components(owner_id))
                    return
                if not result["ok"]:
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cooldown')} Hunt again <t:{result.get('cooldown_ts', int(time.time()+3))}:R>.",
                        0xE67E22)
                    return

                data[owner_id]["_display_name"] = interaction.user.display_name
                await smart_update_v2(interaction, build_hunt_components(owner_id, result))
                await maybe_send_hunt_tip(interaction, result)
                await _hunters_path_notify(interaction, owner_id, result.get("hunters_path_result"))
                return
            else:
                await _navigate(interaction, owner_id, panel, interaction.user.display_name)
                return

        if parts[1] == "help":
            _help_page[owner_id] = 0
            await smart_update_v2(interaction, build_help_components(owner_id, 0))
            return
        return

    # ── /info ENCYCLOPEDIA ────────────────────
    if parts[0] == "info":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        sub = parts[1] if len(parts) > 1 else ""
        st  = _info_state.get(owner_id) or {"category": "biomes", "group": None, "name": None}
        if sub == "cat":
            new_cat = values[0] if values else "biomes"
            first   = _info_entries(new_cat)[0][0]
            st = {"category": new_cat, "group": _info_group_of(new_cat, first), "name": first}
        elif sub == "grp":
            _, _, g = (values[0] if values else "").partition("|")
            ents = _info_entries_in_group(st.get("category", "biomes"), g)
            st = {"category": st.get("category", "biomes"), "group": g,
                  "name": ents[0][0] if ents else st.get("name")}
        elif sub == "name":
            _, _, nm = (values[0] if values else "").partition("|")
            cat = st.get("category", "biomes")
            st = {"category": cat, "group": _info_group_of(cat, nm), "name": nm}
        _info_state[owner_id] = st
        await smart_update_v2(interaction, build_info_components(owner_id))
        return

    # ── SHARE A MOMENT ────────────────────────
    if parts[0] == "share":
        owner_id = parts[-1]
        sub = parts[1] if len(parts) > 1 else ""
        sid = parts[2] if len(parts) > 3 else ""
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction,
                "-# That's someone else's moment to share.", 0xE67E22)
            return
        sh = _share_store.get(sid)
        if not sh or sh.get("owner") != owner_id:
            await send_ephemeral_v2(interaction,
                "-# That share expired — grab a fresh one from a recent result.", 0xE67E22)
            return
        if sh.get("shared"):
            await send_ephemeral_v2(interaction, "-# Already shared this one!", 0xE67E22)
            return
        sh["shared"] = True
        sh["owner_name"] = interaction.user.display_name
        analytics(owner_id, "share_posted", kind=sh.get("kind"))
        await send_v2_followup(interaction, build_share_public_components(sid), ephemeral=False)
        return

    # ── TRIBE EXPEDITIONS ─────────────────────
    if parts[0] == "exped":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        init_user(owner_id)
        sub   = parts[1] if len(parts) > 1 else ""
        arg   = parts[2] if len(parts) > 3 else ""
        tname = data[owner_id].get("tribe")
        note  = ""
        if tname and tname in tribe_data:
            if sub in ("start", "startsel"):
                key = (values[0] if values else "") if sub == "startsel" else arg
                if tribe_role_of(owner_id, tname) not in ("leader", "officer"):
                    note = "Only a leader or officer can start an expedition."
                else:
                    async with user_tribe_transaction(owner_id, tname):
                        ok, note = _exp_start(tname, owner_id, key)
                    if ok:
                        analytics(owner_id, "expedition_started", key=key, tribe=tname)
            elif sub == "vote":
                async with user_tribe_transaction(owner_id, tname):
                    ok, note = _exp_vote(tname, owner_id, arg)
        comps = build_expedition_components(owner_id)
        if note:
            comps[0]["components"].insert(0, {"type": 10, "content": f"-# {note}"})
        await smart_update_v2(interaction, comps)
        return

    # ── FIELD GUIDE / WORLD ───────────────────
    if parts[0] in ("guide", "world"):
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        init_user(owner_id)
        if parts[0] == "guide":
            await smart_update_v2(interaction, build_collection_components(owner_id))
        else:
            await smart_update_v2(interaction, build_world_components(owner_id, await _world_goal_line(interaction)))
        return

    # ── COLLECTION ─────────────────────────────
    if parts[0] == "collection":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        init_user(owner_id)
        sub = parts[1]
        if sub == "hub":
            await smart_update_v2(interaction, build_collection_components(owner_id))
        elif sub == "species":
            await smart_update_v2(interaction, build_collection_species_components(owner_id))
        elif sub == "species_sel":
            biome = values[0] if values else None
            await smart_update_v2(interaction, build_collection_species_components(owner_id, biome))
        elif sub == "mythicals":
            await smart_update_v2(interaction, build_collection_mythicals_components(owner_id))
        elif sub == "mythicals_sel":
            biome = values[0] if values else None
            await smart_update_v2(interaction, build_collection_mythicals_components(owner_id, biome))
        elif sub == "regions":
            await smart_update_v2(interaction, build_collection_regions_components(owner_id))
        elif sub == "trophies":
            await smart_update_v2(interaction, build_trophy_cabinet_components(owner_id))
        elif sub == "trophies_all":
            await smart_update_v2(interaction, build_trophy_all_components(owner_id))
        elif sub == "slot":
            slot_idx = int(parts[2])
            await smart_update_v2(interaction, build_trophy_slot_picker_components(owner_id, slot_idx))
        elif sub == "slot_sel":
            slot_idx = int(parts[2])
            chosen = (values[0] if values else "__none__")
            async with user_transaction(owner_id):
                _trophy_equip(owner_id, slot_idx, None if chosen == "__none__" else chosen)
            await smart_update_v2(interaction, build_trophy_cabinet_components(owner_id))
        return

    # ── GENERIC NAV ───────────────────────────
    if parts[0] == "nav":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        action = parts[1]
        if action in ("back", "menu"):
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
        else:
            await _navigate(interaction, owner_id, action, interaction.user.display_name)
        return

    # ── COLOR ─────────────────────────────────
    if parts[0] == "hunter_color_select":
        owner_id = parts[1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        color_key = values[0] if values else None
        if not color_key or color_key not in COLORS:
            await send_ephemeral_v2(interaction, "Invalid color.", 0xE74C3C)
            return
        data[owner_id]["color"] = color_key
        
        await smart_update_v2(interaction, build_color_panel_components(owner_id))
        return

    if parts[0] == "hunter_color_hex":
        owner_id = parts[1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        if data[owner_id]["level"] < 1200:
            await send_ephemeral_v2(interaction, "Unlocks at Level 1200.", 0xE74C3C)
            return
        await interaction.response.send_modal(CustomColorModal(owner_id))
        return

    # ── BIOME / TRAVEL ────────────────────────
    if parts[0] == "biome" and parts[1] == "select":
        owner_id  = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        biome_key = values[0] if values else None
        if not biome_key:
            return
        lvl_req = next((lvl for k, lvl in BIOME_LEVELS if k == biome_key), 1)
        if data[owner_id]["level"] < lvl_req:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} {BIOME_NAMES[biome_key]} unlocks at Level {lvl_req}.", 0xE74C3C)
            return
        travel_tick(owner_id)
        if biome_key == data[owner_id]["biome"] and not is_traveling(owner_id):
            await send_ephemeral_v2(interaction, f"{emoji('location_pin')} You're already here.", 0xE67E22)
            return
        # Every travel path — this select and the "Travel Now" announcement
        # button alike — funnels through the same confirmation card in a
        # fresh ephemeral, so nothing commits a trip on a single stray click.
        await send_v2_followup(interaction, _travel_confirm_components(owner_id, biome_key), ephemeral=True)
        return

    if parts[0] == "travel" and parts[1] == "cancel":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await smart_update_v2(interaction, [{"type": 17, "accent_color": 0x95A5A6, "spoiler": False,
            "components": [{"type": 10, "content": f"{emoji('cross_mark')} Travel cancelled."}]}])
        return

    if parts[0] == "travel" and parts[1] == "confirm":
        biome_key = parts[2]
        owner_id  = parts[3]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        if biome_key not in BIOME_NAMES:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Unknown region.", 0xE74C3C)
            return
        lvl_req = next((lvl for k, lvl in BIOME_LEVELS if k == biome_key), 1)
        if data[owner_id]["level"] < lvl_req:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} {BIOME_NAMES[biome_key]} unlocks at Level {lvl_req}.", 0xE74C3C)
            return
        travel_tick(owner_id)
        if biome_key == data[owner_id]["biome"] and not is_traveling(owner_id):
            await smart_update_v2(interaction, [{"type": 17, "accent_color": 0xE67E22, "spoiler": False,
                "components": [{"type": 10, "content": f"{emoji('location_pin')} You're already here."}]}])
            return
        async with user_transaction(owner_id):
            tr = start_travel(owner_id, biome_key)
        if tr["mins"] <= 0:
            body = (f"{ADMIN_BUFF_EVENT['emoji']} **Admin's Day Off** — you're whisked straight to "
                    f"**{BIOME_NAMES.get(biome_key, biome_key)}** ({biome_location_line(biome_key)}). "
                    f"Hunt away.")
            color = 0x2ECC71
        else:
            body = (f"{emoji('plane')} Departing for **{BIOME_NAMES.get(biome_key, biome_key)}** "
                    f"({biome_location_line(biome_key)}). Arrives <t:{int(tr['arrive_ts'])}:R> "
                    f"(~{tr['mins']} min). No hunting or camp until you land.")
            color = 0x3498DB
        await smart_update_v2(interaction, [{"type": 17, "accent_color": color, "spoiler": False,
            "components": [{"type": 10, "content": body}]}])
        return

    # ── TOOLS ─────────────────────────────────
    if parts[0] == "tools":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "equip":
            tool_name = values[0] if values else None
            if tool_name and tool_name in data[owner_id].get("owned_tools", []):
                old_tool = data[owner_id].get("tool", "Bare Hands")
                data[owner_id]["tool"] = tool_name
                if get_tool_ammo_type(tool_name) != get_tool_ammo_type(old_tool):
                    data[owner_id]["equipped_ammo"] = None
                
            await smart_update_v2(interaction, build_equip_components(owner_id))
            return

        if parts[1] == "ammo_equip":
            ammo_name = values[0] if values else None
            tool_name = data[owner_id].get("tool", "Bare Hands")
            if ammo_name and ammo_name in AMMO and ammo_compatible_with_tool(ammo_name, tool_name):
                if get_ammo_count(owner_id, ammo_name) > 0:
                    data[owner_id]["equipped_ammo"] = ammo_name
                    
                else:
                    await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You don't own that ammo.", 0xE74C3C)
                    return
            await smart_update_v2(interaction, build_equip_components(owner_id))
            return

        if parts[1] == "vehicle_equip":
            vehicle_name = values[0] if values else None
            if vehicle_name and vehicle_name in data[owner_id].get("owned_vehicles", []):
                data[owner_id]["vehicle"] = vehicle_name
                
            await smart_update_v2(interaction, build_equip_components(owner_id))
            return

    # ── SHOP ──────────────────────────────────
    if parts[0] == "shop":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        # Modals must be the initial response — handle before defer
        if parts[1] == "ammo_buy_acc":
            ammo_name = parts[2]
            if ammo_name not in AMMO:
                await send_ephemeral_v2(interaction, "Unknown ammo.", 0xE74C3C)
                return
            await interaction.response.send_modal(AmmoBuyModal(owner_id, ammo_name))
            return

        if parts[1] == "ammo_buy":
            ammo_name = values[0] if values else None
            if not ammo_name or ammo_name not in AMMO:
                await send_ephemeral_v2(interaction, "Unknown ammo.", 0xE74C3C)
                return
            await interaction.response.send_modal(AmmoBuyModal(owner_id, ammo_name))
            return


        if parts[1] == "tab_dd":
            tab = values[0] if values else "boosts"
            await smart_update_v2(interaction, build_shop_components(owner_id, tab))
            return

        if parts[1] == "tab":
            tab = parts[2]
            await smart_update_v2(interaction, build_shop_components(owner_id, tab))
            return

        if parts[1] == "buy":
            item_name = parts[2]
            if item_name not in SHOP_BOOST_ITEMS:
                await send_ephemeral_v2(interaction, "Unknown item.", 0xE74C3C)
                return
            item      = SHOP_BOOST_ITEMS[item_name]
            boost_key = item.get("boost_key")
            boost_amt = item.get("boost_amt", 0)
            async with user_transaction(owner_id):
                # Everything is (re)computed under the lock so a double-click
                # can't buy past the cap or at a stale price.
                bought = shop_bought_count(data[owner_id], item_name)
                if boost_key and bought >= item["max_qty"]:
                    ok, err = False, f"Max {item_name} already owned."
                else:
                    price = shop_boost_price(item_name, bought)
                    ok, err = _shop_purchase(owner_id, item["currency"], price, "shop boost")
                    if ok:
                        _shop_bought_map(data[owner_id])[item_name] = bought + 1
                        if boost_key:
                            add_personal_boost(owner_id, boost_key, boost_amt)
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
            await smart_update_v2(interaction, build_shop_components(owner_id, "boosts"))
            return

        if parts[1] == "heal_buy":
            item_name = parts[2]
            if item_name not in HEALING_ITEMS:
                await send_ephemeral_v2(interaction, "Unknown item.", 0xE74C3C)
                return
            price = HEALING_ITEMS[item_name]["price"]
            async with user_transaction(owner_id):
                ok, err = _shop_purchase(owner_id, "money", price, "healing item")
                if ok:
                    hi = data[owner_id].setdefault("healing_inv", {})
                    hi[item_name] = hi.get(item_name, 0) + 1
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
            await smart_update_v2(interaction, build_shop_components(owner_id, "healing"))
            return

        if parts[1] == "tool_prev":
            _tool_shop_page[owner_id] = max(0, _tool_shop_page.get(owner_id, 0) - 1)
            await smart_update_v2(interaction, build_shop_components(owner_id, "tools"))
            return

        if parts[1] == "tool_next":
            _tool_shop_page[owner_id] = _tool_shop_page.get(owner_id, 0) + 1
            await smart_update_v2(interaction, build_shop_components(owner_id, "tools"))
            return

        if parts[1] == "tool_noop":
            return

        if parts[1] == "tool_buy_acc":
            tool_name = parts[2]
            if tool_name not in TOOLS:
                await send_ephemeral_v2(interaction, "Unknown tool.", 0xE74C3C)
                return
            if tool_name in data[owner_id].get("owned_tools", []):
                await send_ephemeral_v2(interaction, "Already owned.", 0xE74C3C)
                return
            t = TOOLS[tool_name]
            async with user_transaction(owner_id):
                # Re-check ownership under the lock (double-click guard).
                if tool_name in data[owner_id].get("owned_tools", []):
                    ok, err = False, "Already owned."
                else:
                    ok, err = _shop_purchase(owner_id, t["currency"], t["price"], "shop tool")
                if ok:
                    data[owner_id]["owned_tools"].append(tool_name)
                    data[owner_id]["tool"] = tool_name
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
            analytics(owner_id, "upgrade", tool=tool_name, price=t["price"])
            _rookie_goal_progress(owner_id, "buy_tool")
            _hp_done = hunters_path_maybe_complete(owner_id)
            await _hunters_path_notify(interaction, owner_id, _hp_done)
            await smart_update_v2(interaction, build_shop_components(owner_id, "tools"))
            return

        if parts[1] == "tool_buy":
            tool_name = values[0] if values else None
            if not tool_name or tool_name not in TOOLS:
                await send_ephemeral_v2(interaction, "Unknown tool.", 0xE74C3C)
                return
            if tool_name in data[owner_id].get("owned_tools", []):
                await send_ephemeral_v2(interaction, "Already owned.", 0xE74C3C)
                return
            t = TOOLS[tool_name]
            async with user_transaction(owner_id):
                # Re-check ownership under the lock (double-click guard).
                if tool_name in data[owner_id].get("owned_tools", []):
                    ok, err = False, "Already owned."
                else:
                    ok, err = _shop_purchase(owner_id, t["currency"], t["price"], "shop tool")
                if ok:
                    data[owner_id]["owned_tools"].append(tool_name)
                    data[owner_id]["tool"] = tool_name
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
            analytics(owner_id, "upgrade", tool=tool_name, price=t["price"])
            _rookie_goal_progress(owner_id, "buy_tool")
            _hp_done = hunters_path_maybe_complete(owner_id)
            await _hunters_path_notify(interaction, owner_id, _hp_done)
            await smart_update_v2(interaction, build_shop_components(owner_id, "tools"))
            return

        if parts[1] == "ammo_prev":
            _ammo_shop_page[owner_id] = max(0, _ammo_shop_page.get(owner_id, 0) - 1)
            await smart_update_v2(interaction, build_shop_components(owner_id, "ammo"))
            return

        if parts[1] == "ammo_next":
            _ammo_shop_page[owner_id] = _ammo_shop_page.get(owner_id, 0) + 1
            await smart_update_v2(interaction, build_shop_components(owner_id, "ammo"))
            return

        if parts[1] == "ammo_noop":
            return

        if parts[1] == "vehicle_prev":
            _vehicle_shop_page[owner_id] = max(0, _vehicle_shop_page.get(owner_id, 0) - 1)
            await smart_update_v2(interaction, build_shop_components(owner_id, "vehicles"))
            return

        if parts[1] == "vehicle_next":
            _vehicle_shop_page[owner_id] = _vehicle_shop_page.get(owner_id, 0) + 1
            await smart_update_v2(interaction, build_shop_components(owner_id, "vehicles"))
            return

        if parts[1] == "vehicle_noop":
            return

        if parts[1] == "vehicle_buy_acc":
            vehicle_name = parts[2]
            if vehicle_name not in VEHICLES:
                await send_ephemeral_v2(interaction, "Unknown vehicle.", 0xE74C3C)
                return
            if vehicle_name in data[owner_id].get("owned_vehicles", []):
                await send_ephemeral_v2(interaction, "Already owned.", 0xE74C3C)
                return
            v = VEHICLES[vehicle_name]
            async with user_transaction(owner_id):
                if vehicle_name in data[owner_id].get("owned_vehicles", []):
                    ok, err = False, "Already owned."
                else:
                    ok, err = _shop_purchase(owner_id, v["currency"], v["price"], "vehicle shop")
                if ok:
                    data[owner_id].setdefault("owned_vehicles", []).append(vehicle_name)
                    data[owner_id]["vehicle"] = vehicle_name
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
            await smart_update_v2(interaction, build_shop_components(owner_id, "vehicles"))
            return

        if parts[1] == "vehicle_equip_acc":
            vehicle_name = parts[2]
            if vehicle_name in data[owner_id].get("owned_vehicles", []):
                data[owner_id]["vehicle"] = vehicle_name
                
            await smart_update_v2(interaction, build_shop_components(owner_id, "vehicles"))
            return

        if parts[1] == "vehicle_buy":
            vehicle_name = values[0] if values else None
            if not vehicle_name or vehicle_name not in VEHICLES:
                await send_ephemeral_v2(interaction, "Unknown vehicle.", 0xE74C3C)
                return
            if vehicle_name in data[owner_id].get("owned_vehicles", []):
                await send_ephemeral_v2(interaction, "Already owned.", 0xE74C3C)
                return
            v = VEHICLES[vehicle_name]
            async with user_transaction(owner_id):
                if vehicle_name in data[owner_id].get("owned_vehicles", []):
                    ok, err = False, "Already owned."
                else:
                    ok, err = _shop_purchase(owner_id, v["currency"], v["price"], "vehicle shop")
                if ok:
                    data[owner_id].setdefault("owned_vehicles", []).append(vehicle_name)
                    data[owner_id]["vehicle"] = vehicle_name
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
            await smart_update_v2(interaction, build_shop_components(owner_id, "vehicles"))
            return

        if parts[1] == "vehicle_equip":
            vehicle_name = values[0] if values else None
            if vehicle_name and vehicle_name in data[owner_id].get("owned_vehicles", []):
                data[owner_id]["vehicle"] = vehicle_name
                
            await smart_update_v2(interaction, build_equip_components(owner_id))
            return

    # ── IDLE  ·  HUNTING CAMP ─────────────────
    if parts[0] == "idle":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        sub  = parts[1]
        idle = data[owner_id]["idle"]

        if sub == "camp":
            async with user_transaction(owner_id):
                idle_tick(owner_id)
            await smart_update_v2(interaction, build_idle_components(owner_id))
            return

        if sub == "collect":
            async with user_transaction(owner_id):
                result = collect_idle_haul(owner_id)
            await smart_update_v2(interaction, build_idle_haul_result_components(owner_id, result))
            await _hunters_path_notify(interaction, owner_id, result.get("hunters_path_result"))
            await check_everything(interaction, owner_id)
            return

        if sub == "hire":
            _err = None
            _hp_done = None
            async with user_transaction(owner_id):
                # Re-check under the lock: a double-click queues a second
                # handler that already passed any pre-lock check.
                idle = data[owner_id]["idle"]
                cost = idle_cost_for_stack(idle.get("stacks", 0))
                if idle.get("stacks", 0) >= IDLE_MAX_HUNTERS:
                    _err = f"`👤` You've hit the max of **{IDLE_MAX_HUNTERS}** hunters."
                elif data[owner_id]["money"] < cost:
                    _err = f"{emoji('cross_mark')} You need **◈ {cost:,}** to hire another hunter."
                else:
                    idle_tick(owner_id)   # bank catches at the old rate first
                    if not spend_money(owner_id, cost, "idle: hire hunter"):
                        _err = f"{emoji('cross_mark')} You need **◈ {cost:,}** to hire another hunter."
                    else:
                        idle["stacks"] = idle.get("stacks", 0) + 1
                        _hp_done = hunters_path_maybe_complete(owner_id)
                        idle["active"] = True
                        if idle.get("started_at", 0) <= 0:
                            idle["started_at"] = time.time()
            if _err:
                await send_ephemeral_v2(interaction, _err, 0xE74C3C)
                return
            await _hunters_path_notify(interaction, owner_id, _hp_done)
            await smart_update_v2(interaction, build_idle_components(owner_id))
            return

        if sub == "upgrade":
            _err = None
            async with user_transaction(owner_id):
                idle = data[owner_id]["idle"]
                cur  = idle.get("capacity_upgrades", 0)
                cost = idle_capacity_upgrade_cost(cur)
                if cur >= IDLE_MAX_CAPACITY_UPGRADES:
                    _err = f"{emoji('package')} Storage is already fully upgraded."
                elif data[owner_id]["money"] < cost:
                    _err = (f"{emoji('cross_mark')} You need **◈ {cost:,}** to expand storage "
                            f"(+{IDLE_CAPACITY_PER_UPGRADE} slots).")
                else:
                    idle_tick(owner_id)
                    if not spend_money(owner_id, cost, "idle: storage upgrade"):
                        _err = (f"{emoji('cross_mark')} You need **◈ {cost:,}** to expand storage "
                                f"(+{IDLE_CAPACITY_PER_UPGRADE} slots).")
                    else:
                        idle["capacity_upgrades"] = cur + 1
            if _err:
                await send_ephemeral_v2(interaction, _err, 0xE74C3C)
                return
            await smart_update_v2(interaction, build_idle_components(owner_id))
            return

        if sub == "biome":
            biome_key = values[0] if values else None
            ok, reason = idle_can_camp(owner_id, biome_key or "")
            if not ok:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} {reason}", 0xE74C3C)
                return
            async with user_transaction(owner_id):
                idle_tick(owner_id)   # bank catches from the old biome first
                idle["camp_biome"] = biome_key
            await smart_update_v2(interaction, build_idle_components(owner_id))
            return
        return

    # ── DAILY ─────────────────────────────────
    if parts[0] == "daily" and parts[1] == "claim":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
 
        today_str = today_utc()
        claimed   = False
        rtype     = "money"
        amt       = 0
        streak    = 0
 
        if data[owner_id].get("last_daily_date", "") != today_str:
            async with user_transaction(owner_id):
                # Re-check under the lock so a double-click can't claim twice.
                if data[owner_id].get("last_daily_date", "") != today_str:
                    streak = calc_streak(
                        data[owner_id].get("last_daily_date", ""),
                        data[owner_id].get("daily_streak", 0),
                    ) + 1
                    data[owner_id]["daily_streak"]    = streak
                    data[owner_id]["last_daily_date"] = today_str
                    if streak > data[owner_id].get("best_daily_streak", 0):
                        data[owner_id]["best_daily_streak"] = streak
                    level    = data[owner_id]["level"]
                    prestige = data[owner_id].get("prestige", 0)
                    tier     = get_daily_tier(level)
                    bonus    = (1 + (streak / 100) + (prestige * 0.1)) * ev_daily_mult()
                    rtype    = random.choice(["money", "gems"])
                    if rtype == "money":
                        base = random.randint(tier["money_min"], tier["money_max"])
                        amt  = int(base * bonus)
                        add_money(owner_id, amt, "daily")
                        data[owner_id]["total_money_earned"] = (
                            data[owner_id].get("total_money_earned", 0) + amt
                        )
                    else:
                        base = random.randint(tier["gems_min"], tier["gems_max"])
                        amt  = int(base * bonus)
                        add_gems(owner_id, amt, "daily")
                    claimed = True
            if claimed:
                quest_progress(owner_id, "dailies_claimed_quest", 1)
                # Streak quests track the *highest* streak reached, not a running sum.
                quest_progress(owner_id, "daily_streak_reached",
                               data[owner_id].get("daily_streak", 0), absolute=True)
                analytics(owner_id, "daily_claimed", streak=streak, reward=rtype, amount=amt)
                await _referral_check_qualified(owner_id)

        _hp_result = None
        if claimed:
            await award_tribe_xp(owner_id, "daily")
            _hp_result = hunters_path_maybe_complete(owner_id)
        await check_achievements_and_badges(interaction, owner_id)
        await smart_update_v2(
            interaction,
            build_daily_components(
                owner_id,
                claimed=claimed,
                reward_type=rtype,
                reward_amt=amt,
                streak=streak,
            ),
        )
        await _hunters_path_notify(interaction, owner_id, _hp_result)
        return

    # ── PRESTIGE ──────────────────────────────
    if parts[0] == "prestige" and parts[1] == "confirm":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        _ok = False
        async with user_transaction(owner_id):
            # Re-check under the lock: a double-click must not prestige twice
            # (the first reset drops level/money below the requirements).
            if data[owner_id]["level"] >= PRESTIGE_MIN_LEVEL and data[owner_id]["money"] >= PRESTIGE_MIN_MONEY:
                new_p = apply_account_reset(owner_id, prestige=True)
                _ok = True
        if not _ok:
            await send_ephemeral_v2(interaction, "Requirements not met.", 0xE74C3C)
            return
        await smart_update_v2(interaction, build_prestige_done_components(owner_id, new_p))
        return

    # ── MAIL ──────────────────────────────────
    if parts[0] == "mail":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "tab_dd":
            tab = values[0] if values else "tribe"
            async with user_transaction(owner_id):
                if tab == "dev" and DEV_MAIL:
                    data[owner_id]["mail_dev_content_read"] = DEV_MAIL
            await smart_update_v2(interaction, build_mail_components(owner_id, tab))
            return

        if parts[1] == "gift_toggle":
            idx   = int(parts[2])
            gifts = data[owner_id].get("gift_mails", [])
            if 0 <= idx < len(gifts):
                gifts[idx]["read"] = not gifts[idx].get("read", True)
                mark_user_dirty(owner_id)
            # mark_read=False: re-drawing the panel must not undo the toggle
            await smart_update_v2(interaction, build_mail_components(owner_id, "gifts", mark_read=False))
            return

        if parts[1] == "tab":
            tab = parts[2]
            if tab == "dev" and DEV_MAIL:
                data[owner_id]["mail_dev_content_read"] = DEV_MAIL
            await smart_update_v2(interaction, build_mail_components(owner_id, tab))
            return

        if parts[1] == "tribe":
            sub = parts[2]
            tribe_inv = data[owner_id].get("tribe_inv")
            if sub == "accept":
                if not tribe_inv or tribe_inv not in tribe_data:
                    await send_ephemeral_v2(interaction, "Tribe no longer exists.", 0xE74C3C)
                    return
                if data[owner_id].get("tribe"):
                    await send_ephemeral_v2(interaction, "Already in a tribe.", 0xE74C3C)
                    return
                
                td = tribe_data[tribe_inv]  # FIXED: Define td here
                _ensure_tribe_fields(td)
                if len(tribe_roster(tribe_inv)) >= td["max_members"]:
                    await send_ephemeral_v2(interaction, "Tribe is full.", 0xE74C3C)
                    return
                _ok, _wait = _tribe_rejoin_ok(owner_id)
                if not _ok:
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cross_mark')} You left a tribe recently — you can join again <t:{int(time.time()+_wait)}:R>.", 0xE74C3C)
                    return

                _err = None
                async with user_tribe_transaction(owner_id, tribe_inv):
                    if tribe_inv not in tribe_data or data[owner_id].get("tribe") \
                            or data[owner_id].get("tribe_inv") != tribe_inv:
                        _err = "That invite is no longer valid."
                    elif _tribe_is_banned(td, owner_id):
                        _err = "You are banned from that tribe."
                    elif len(tribe_roster(tribe_inv)) >= td["max_members"]:
                        _err = "Tribe is full."
                    else:
                        _tribe_join_recruit(td, owner_id)
                        if owner_id in td.get("invites", []):
                            td["invites"].remove(owner_id)
                        data[owner_id]["tribe"] = tribe_inv
                        data[owner_id]["tribe_inv"] = None
                        data[owner_id]["tribe_inv_read"] = False
                if _err:
                    await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} {_err}", 0xE74C3C)
                    return

                await smart_update_v2(interaction, build_mail_components(owner_id, "tribe"))
                return

        if parts[1] == "gifts" and parts[2] == "clear":
            async with user_transaction(owner_id):
                data[owner_id]["gift_mails"] = []
            await smart_update_v2(interaction, build_mail_components(owner_id, "gifts"))
            return

        if parts[1] == "dev" and parts[2] == "read":
            async with user_transaction(owner_id):
                data[owner_id]["mail_dev_content_read"] = DEV_MAIL
            await smart_update_v2(interaction, build_mail_components(owner_id, "dev"))
            return

        return

    # ── GIFT CONFIRM ──────────────────────────
    if parts[0] == "gift":
        action  = parts[1]
        gift_id = parts[2]
        gdata   = gift_cache.get(gift_id)

        if not gdata:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} This gift confirmation expired.", 0xE74C3C)
            return

        owner_id = str(gdata["sender_id"])
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if action == "cancel":
            gift_cache.pop(gift_id, None)
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
            return

        if action == "confirm":
            recipient_id = str(gdata["recipient_id"])
            fmt = gdata["format"]
            parsed = int(gdata["parsed"])
            message = gdata["message"]
            init_user(recipient_id)
            
            # Define these BEFORE using them
            amt_str = f"◈ {parsed:,}" if fmt == "money" else f"{emoji('gem')} {parsed:,}"
            icon = "◈" if fmt == "money" else emoji("gem")

            # Pre-check without locks (fast path for obvious failures)
            if data[owner_id][fmt] < parsed:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough {icon}!", 0xE74C3C)
                return
            
            # Lock both users in a consistent order (see multi_user_transaction).
            bal_str = None
            already = False
            blocked = None
            async with multi_user_transaction(owner_id, recipient_id):
                # Consume the one-time confirmation *inside* the lock. Two
                # overlapping confirm clicks otherwise both clear the pre-check
                # and both transfer; popping here lets only the first through.
                if gift_cache.pop(gift_id, None) is None:
                    already = True
                elif data[owner_id][fmt] < parsed:
                    bal_str = None
                elif fmt == "gems" and (_block := _gem_gift_block(owner_id, parsed)):
                    bal_str = None
                    blocked = _block
                else:
                    if fmt == "money":
                        spend_money(owner_id, parsed, "gift send")
                        add_money(recipient_id, parsed, "gift receive")
                        bal_str = f"◈ {data[owner_id]['money']:,}"
                    else:
                        spend_gems(owner_id, parsed, "gift send")
                        add_gems(recipient_id, parsed, "gift receive")
                        gd = data[owner_id].get("gem_gift_day") or {}
                        if gd.get("tag") != today_utc():
                            gd = {"tag": today_utc(), "sent": 0}
                        gd["sent"] += parsed
                        data[owner_id]["gem_gift_day"] = gd
                        bal_str = f"{emoji('gem')} {data[owner_id]['gems']:,}"

                    gift_entry = {
                        "sender_id": owner_id,
                        "sender_name": interaction.user.display_name,
                        "fmt": fmt,
                        "amt_str": amt_str,
                        "message": message,
                        "ts": int(time.time()),
                        "read": False,
                    }
                    data[recipient_id].setdefault("gift_mails", []).insert(0, gift_entry)
                    data[recipient_id]["gift_mails"] = data[recipient_id]["gift_mails"][:20]

            if already:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} This gift was already sent.", 0xE74C3C)
                return
            if bal_str is None:
                await send_ephemeral_v2(interaction,
                    f"{emoji('cross_mark')} {blocked}" if blocked else f"{emoji('cross_mark')} Not enough {icon}!",
                    0xE74C3C)
                return

            try:
                recipient_user = await bot.fetch_user(int(recipient_id))
                try:
                    route = Route("POST", "/users/@me/channels")
                    dm_ch = await bot.http.request(route, json={"recipient_id": recipient_id})
                    dm_route = Route(
                        "POST", "/channels/{channel_id}/messages",
                        channel_id=dm_ch["id"],
                    )
                    await bot.http.request(dm_route, json={
                        "flags": V2_FLAGS,
                        "components": [{
                            "type": 17, "accent_color": 0x2ECC71, "spoiler": False,
                            "components": [{"type": 10, "content":
                                f"### {emoji('gift')} You received a gift!\n"
                                f"**{interaction.user.display_name}** sent you **{amt_str}**!\n\n"
                                f"> {message}\n\n"
                                f"-# Use </mail:{COMMAND_ID.get('mail','0')}> to view your gift mail."
                            }]
                        }],
                        "allowed_mentions": {"parse": []},
                    })
                except Exception:
                    pass
                await smart_update_v2(
                    interaction,
                    build_gift_sent_components(owner_id, recipient_user, amt_str, bal_str, message),
                )
            except Exception:
                await send_ephemeral_v2(interaction, f"{emoji('check_mark')} Gift sent! ({amt_str})", 0x2ECC71)
            return
 

    # ── TRIBE NAVIGATION ──────────────────────
    if parts[0] == "tribe":
        action   = parts[1]
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        tribe_nm = data[owner_id].get("tribe")
        if not tribe_nm or tribe_nm not in tribe_data:
            await send_ephemeral_v2(interaction, "You're not in a tribe.", 0xE74C3C)
            return
        sort = _tribe_sort.get(owner_id, "rank")

        # Modals before defer
        if action in ("action_select", "action"):
            sub = (values[0] if action == "action_select"
                   else (parts[2] if len(parts) > 2 else None))

            if sub == "invite":
                await interaction.response.send_modal(TribeInviteModal(owner_id, tribe_nm))
                return

            if sub == "set_desc":
                await interaction.response.send_modal(TribeSetDescModal(owner_id, tribe_nm))
                return

            if sub == "leave":
                td_l    = tribe_data[tribe_nm]
                total_m = len(tribe_roster(tribe_nm))
                is_ldr  = td_l["roles"]["leader"] == owner_id
                if is_ldr and total_m > 1:
                    await interaction.response.send_modal(TribeLeaveLeaderModal(owner_id, tribe_nm))
                    return
                # Non-modal leave falls through to defer below


        if action == "nav":
            page = parts[2]
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, page, sort))
            return

        if action == "navsel":
            page = values[0] if values else "main"
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, page, sort))
            return

        if action == "sort":
            new_sort = "level" if sort == "rank" else "rank"
            _tribe_sort[owner_id] = new_sort
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "main", new_sort))
            return

        if action == "contract_reroll":
            if not await _tribe_perm(interaction, owner_id, tribe_nm): return
            async with user_tribe_transaction(owner_id, tribe_nm):
                if tribe_role_of(owner_id, tribe_nm) in ("leader", "officer"):
                    td_r = tribe_data[tribe_nm]
                    _ensure_tribe_fields(td_r)
                    if not td_r["week"].get("reroll_used"):
                        td_r["week"]["reroll_used"] = True
                        td_r["week"]["explore_biomes"] = []
                        td_r["week"]["contracts"] = _roll_tribe_contracts(
                            td_r, td_r["week"].get("scale_group", TRIBE_CONTRACT_MIN_GROUP))
                        _tribe_log(td_r, f"{emoji('dice')} <@{owner_id}> rerolled this week's contracts.")
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "contracts", sort))
            return

        if action == "shop":
            boost_key = parts[2]
            if boost_key not in TRIBE_SHOP_ITEMS:
                await send_ephemeral_v2(interaction, "Unknown shop item.", 0xE74C3C)
                return
            cost, amount = TRIBE_SHOP_ITEMS[boost_key]
            if not await _tribe_perm(interaction, owner_id, tribe_nm): return
            _err = None
            async with user_tribe_transaction(owner_id, tribe_nm):
                # Everything re-checked under the lock; price/amount come from
                # the server-side table, not the button id.
                if tribe_role_of(owner_id, tribe_nm) not in ("leader", "officer"):
                    _err = f"{emoji('cross_mark')} You no longer have permission to do that in this tribe."
                elif tribe_data[tribe_nm].get(boost_key, 0) >= MAX_TRIBE_BOOST:
                    _err = f"{emoji('cross_mark')} This tribe boost is already at the maximum **{MAX_TRIBE_BOOST}%**."
                elif not spend_gems(owner_id, cost, "tribe shop"):
                    _err = f"Need {emoji('gem')}{cost}."
                else:
                    tribe_data[tribe_nm][boost_key] = min(
                        MAX_TRIBE_BOOST,
                        tribe_data[tribe_nm].get(boost_key, 0) + amount,
                    )
            if _err:
                await send_ephemeral_v2(interaction, _err, 0xE74C3C)
                return
            await smart_update_v2(
                interaction,
                build_tribe_components(owner_id, tribe_nm, "shop", sort),
            )
            return

        if action == "ban_action":
            if not await _tribe_perm(interaction, owner_id, tribe_nm): return
            val = values[0] if values else "none"
            if val != "none":
                a, target = val.split(":", 1)
                if a == "ban":
                    async with user_tribe_transaction(owner_id, tribe_nm):
                        if tribe_role_of(owner_id, tribe_nm) not in ("leader", "officer"):
                            pass
                        else:
                            td_r = tribe_data[tribe_nm]
                            _kicker = tribe_role_of(owner_id, tribe_nm)
                            if target == td_r["roles"].get("leader") or target == owner_id:
                                pass  # can't ban the leader or yourself
                            elif _kicker == "officer" and tribe_role_of(target, tribe_nm) in ("officer", "leader"):
                                pass  # officers can't ban other officers (same rule as kick)
                            else:
                                _tribe_remove_member(td_r, target, note="was banned from")
                                if target in data:
                                    data[target]["tribe"] = None
                                    data[target]["tribe_left_ts"] = time.time()
                                    mark_user_dirty(target)
                                blist = td_r.setdefault("banned", [])
                                if target not in blist:
                                    blist.append(target)
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort))
            return

        if action == "unban_action":
            if not await _tribe_perm(interaction, owner_id, tribe_nm): return
            val = values[0] if values else "none"
            if val != "none":
                a, target = val.split(":", 1)
                if a == "unban":
                    async with user_tribe_transaction(owner_id, tribe_nm):
                        if tribe_role_of(owner_id, tribe_nm) in ("leader", "officer"):
                            blist = tribe_data[tribe_nm].get("banned", [])
                            if target in blist:
                                blist.remove(target)
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort))
            return

        if action == "action_select":
            sub = values[0] if values else None
            if not sub:
                return

            # invite, set_desc, leave (modal) already handled above
            if sub == "kick":
                await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "kick_picker", sort))
                return

            if sub == "banlist":
                await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort))
                return

            if sub == "promote":
                await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "promote_picker", sort))
                return

            if sub == "demote":
                await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "demote_picker", sort))
                return

            if sub == "transfer":
                await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "transfer_picker", sort))
                return

            if sub == "leave":
                # Same rules as the panel button and /tribe leave: recruits count
                # as members, the rejoin cooldown is stamped, and the roster is
                # cleaned through _tribe_remove_member.
                td_l = tribe_data[tribe_nm]
                _left = False
                async with user_tribe_transaction(owner_id, tribe_nm):
                    total_m = len(tribe_roster(tribe_nm))
                    is_ldr  = td_l["roles"]["leader"] == owner_id
                    if is_ldr and total_m > 1:
                        pass   # leader with members must hand off first (modal path)
                    else:
                        if is_ldr:
                            tribe_data.pop(tribe_nm, None)
                        else:
                            _tribe_remove_member(td_l, owner_id, note="left")
                        data[owner_id]["tribe"] = None
                        data[owner_id]["tribe_left_ts"] = time.time()
                        _left = True
                if not _left:
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cross_mark')} You lead this tribe. Transfer leadership first.", 0xE74C3C)
                    return
                await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
                return

            return

        if action == "kick_confirm":
            if not await _tribe_perm(interaction, owner_id, tribe_nm): return
            target = values[0] if values else None
            if target:
                async with user_tribe_transaction(owner_id, tribe_nm):
                    td_r      = tribe_data[tribe_nm]
                    kicker    = tribe_role_of(owner_id, tribe_nm)
                    target_rl = tribe_role_of(target, tribe_nm)
                    # officers may only remove members / recruits; leader removes anyone
                    can = (kicker == "leader" and target_rl in ("officer", "member", "recruit")) or \
                          (kicker == "officer" and target_rl in ("member", "recruit"))
                    if can and target != td_r["roles"].get("leader") and target != owner_id:
                        _tribe_remove_member(td_r, target, note="was kicked from")
                        if target in data:
                            data[target]["tribe"]     = None
                            data[target]["tribe_inv"] = None
                            data[target]["tribe_left_ts"] = time.time()
                            mark_user_dirty(target)
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort))
            return

        if action == "promote_confirm":
            if not await _tribe_perm(interaction, owner_id, tribe_nm, ("leader",)): return
            target = values[0] if values else None
            if target:
                async with user_tribe_transaction(owner_id, tribe_nm):
                    if tribe_role_of(owner_id, tribe_nm) == "leader":
                        td_r = tribe_data[tribe_nm]
                        if target in td_r["roles"]["members"]:
                            td_r["roles"]["members"].remove(target)
                            td_r["roles"]["officer"].append(target)
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort))
            return

        if action == "demote_confirm":
            if not await _tribe_perm(interaction, owner_id, tribe_nm, ("leader",)): return
            target = values[0] if values else None
            if target:
                async with user_tribe_transaction(owner_id, tribe_nm):
                    if tribe_role_of(owner_id, tribe_nm) == "leader":
                        td_r = tribe_data[tribe_nm]
                        if target in td_r["roles"]["officer"]:
                            td_r["roles"]["officer"].remove(target)
                            td_r["roles"]["members"].append(target)
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort))
            return

        if action == "transfer_confirm":
            if not await _tribe_perm(interaction, owner_id, tribe_nm, ("leader",)): return
            target = values[0] if values else None
            if target:
                async with user_tribe_transaction(owner_id, tribe_nm):
                    if tribe_role_of(owner_id, tribe_nm) == "leader":
                        td_r = tribe_data[tribe_nm]
                        # Only a current officer can be handed leadership; a stale
                        # picker must not crown someone who has since left.
                        if target in td_r["roles"]["officer"]:
                            td_r["roles"]["officer"].remove(target)
                            td_r["roles"]["leader"] = target
                            if owner_id not in td_r["roles"]["officer"]:
                                td_r["roles"]["officer"].append(owner_id)
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "main", sort))
            return

        if action == "action":
            sub = parts[2]
            # invite, set_desc, leave (modal) already handled above
            if sub == "banlist":
                await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort))
                return
            if sub == "leave":
                td_l    = tribe_data[tribe_nm]
                total_m = len(tribe_roster(tribe_nm))
                is_ldr  = td_l["roles"]["leader"] == owner_id
                if is_ldr and total_m > 1:
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cross_mark')} You lead this tribe. Use `/tribe leave new_leader:@someone` or transfer leadership first.",
                        0xE74C3C)
                    return
                async with user_tribe_transaction(owner_id, tribe_nm):
                    if is_ldr and total_m == 1:
                        tribe_data.pop(tribe_nm, None)
                    else:
                        _tribe_remove_member(td_l, owner_id, note="left")
                    data[owner_id]["tribe"] = None
                    data[owner_id]["tribe_left_ts"] = time.time()
                await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
                return

    # ── TRIBE INVITE ACCEPT/DECLINE (DM) ──────
    if cid.startswith("tribe_invite_accept:") or cid.startswith("tribe_invite_decline:"):
        action_str, owner_id, tribe_nm = cid.split(":", 2)
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        if action_str.endswith("accept"):
            if data[owner_id].get("tribe"):
                await send_ephemeral_v2(interaction, "Already in a tribe.", 0xE74C3C)
                return
            if tribe_nm not in tribe_data:
                await send_ephemeral_v2(interaction, "Tribe no longer exists.", 0xE74C3C)
                return
            td_a  = tribe_data[tribe_nm]
            _ensure_tribe_fields(td_a)
            if len(tribe_roster(tribe_nm)) >= td_a["max_members"]:
                await send_ephemeral_v2(interaction, "Tribe is full.", 0xE74C3C)
                return
            _ok, _wait = _tribe_rejoin_ok(owner_id)
            if not _ok:
                await send_ephemeral_v2(interaction,
                    f"{emoji('cross_mark')} You left a tribe recently — you can join again <t:{int(time.time()+_wait)}:R>.", 0xE74C3C)
                return
            _err = None
            async with user_tribe_transaction(owner_id, tribe_nm):
                if tribe_nm not in tribe_data or data[owner_id].get("tribe"):
                    _err = "That invite is no longer valid."
                elif owner_id not in td_a.get("invites", []) or data[owner_id].get("tribe_inv") != tribe_nm:
                    _err = "That invite is no longer valid."
                elif _tribe_is_banned(td_a, owner_id):
                    _err = "You are banned from that tribe."
                elif len(tribe_roster(tribe_nm)) >= td_a["max_members"]:
                    _err = "Tribe is full."
                else:
                    _tribe_join_recruit(td_a, owner_id)
                    td_a["invites"].remove(owner_id)
                    data[owner_id]["tribe"]     = tribe_nm
                    data[owner_id]["tribe_inv"] = None
            if _err:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} {_err}", 0xE74C3C)
                return
            await send_ephemeral_v2(interaction, f"{emoji('check_mark')} Joined **{tribe_nm}** as a Recruit!", 0x2ECC71)
        else:
            if tribe_nm in tribe_data and owner_id in tribe_data[tribe_nm].get("invites", []):
                tribe_data[tribe_nm]["invites"].remove(owner_id)
            data[owner_id]["tribe_inv"] = None
            
            await send_ephemeral_v2(interaction, "Invite declined.", 0xE74C3C)
        return

    # ── BAN APPEAL ────────────────────────────
    if parts[0] == "ban" and parts[1] == "appeal":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        b = get_ban(owner_id)
        if b.get("appeals_used", 0) >= b.get("appeals_max", 2):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} No appeal chances left.", 0xE74C3C)
            return
        await interaction.response.send_modal(BanAppealModal(owner_id))
        return

    # ── BAN APPEAL REVIEW (admin channel) ─────
    if parts[0] == "appeal" and len(parts) >= 3:
        # custom_id: appeal:<accept|reject>:<target_id>:<appeal_id>
        if not is_admin(interaction):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Admins only.", 0xE74C3C)
            return

        decision  = parts[1]
        target_id = parts[2]
        appeal_id = parts[3] if len(parts) > 3 else ""
        store     = _appeal_store.get(appeal_id, {})

        if decision not in ("accept", "reject"):
            return
        if store.get("handled"):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} This appeal was already handled.", 0xE67E22)
            return

        init_user(target_id)
        init_ban_record(target_id)
        ban = data[target_id]["ban"]

        if decision == "accept":
            async with user_transaction(target_id):
                ban["active"] = False
            dm_color = 0x2ECC71
            dm_body  = (
                f"### {emoji('check_mark')} Your ban appeal was accepted\n"
                "Your ban has been lifted — welcome back, hunter.\n"
                "-# Please keep it fair from here on out."
            )
            admin_note = f"{emoji('check_mark')} Appeal accepted — ban lifted."
        else:
            remaining = max(0, ban.get("appeals_max", 2) - ban.get("appeals_used", 0))
            dm_color = 0xE74C3C
            dm_body  = (
                f"### {emoji('cross_mark')} Your ban appeal was rejected\n"
                "The team reviewed your appeal and decided to keep the ban in place.\n"
                f"-# Appeals remaining: **{remaining}**"
            )
            admin_note = f"{emoji('cross_mark')} Appeal rejected."

        # DM the appellant
        try:
            route    = Route("POST", "/users/@me/channels")
            dm_ch    = await bot.http.request(route, json={"recipient_id": target_id})
            dm_route = Route("POST", "/channels/{channel_id}/messages", channel_id=dm_ch["id"])
            await bot.http.request(dm_route, json={
                "flags": V2_FLAGS,
                "components": [{"type": 17, "accent_color": dm_color, "spoiler": False,
                    "components": [{"type": 10, "content": dm_body}]}],
                "allowed_mentions": {"parse": []},
            })
        except Exception as e:
            print("Appeal decision DM error:", e)

        # Mark the appeal channel message resolved (strip the buttons)
        if store:
            store["handled"] = True
        channel_msg_id = store.get("channel_msg_id")
        if channel_msg_id:
            try:
                patch_route = Route("PATCH", "/channels/{channel_id}/messages/{message_id}",
                                    channel_id=BAN_APPEAL_CHANNEL_ID, message_id=channel_msg_id)
                await bot.http.request(patch_route, json={
                    "flags": V2_FLAGS,
                    "components": [{"type": 17, "accent_color": dm_color, "spoiler": False,
                        "components": [{"type": 10, "content":
                            f"### `📋` Ban Appeal — {admin_note}\n"
                            f"**User:** <@{target_id}> (`{target_id}`)\n"
                            f"**Reason for ban:** {ban.get('reason', 'N/A')}\n\n"
                            f"**Appeal message:**\n{store.get('reason', '—')}\n\n"
                            f"-# Handled by <@{interaction.user.id}>"
                        }]}],
                    "allowed_mentions": {"parse": []},
                })
            except Exception as e:
                print("Appeal message patch error:", e)

        await send_ephemeral_v2(interaction,
            f"{admin_note}\n-# <@{target_id}> has been notified.", dm_color)
        return

    # ── ACHIEVEMENTS / BADGES / TITLES ────────
    if parts[0] == "ach":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "prev":
            _ach_page[owner_id] = max(0, _ach_page.get(owner_id, 0) - 1)
            await smart_update_v2(interaction, build_achievements_components(owner_id))
            return

        if parts[1] == "next":
            pages = build_achievements_pages(owner_id)
            _ach_page[owner_id] = min(len(pages) - 1, _ach_page.get(owner_id, 0) + 1)
            await smart_update_v2(interaction, build_achievements_components(owner_id))
            return

        if parts[1] == "noop":
            return

        if parts[1] == "badges":
            await smart_update_v2(interaction, build_badges_components(owner_id))
            return

        if parts[1] == "achievements":
            _ach_page[owner_id] = 0
            await smart_update_v2(interaction, build_achievements_components(owner_id))
            return

        if parts[1] == "titles":
            await smart_update_v2(interaction, build_title_components(owner_id))
            return

        if parts[1] == "back":
            await smart_update_v2(interaction, build_progression_hub(owner_id))
            return

        return

    # ── TITLE ─────────────────────────────────
    if parts[0] == "title":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "equip":
            chosen = values[0] if values else None
            if chosen == "__none__":
                data[owner_id]["equipped_title"] = None
            elif chosen and chosen in data[owner_id].get("earned_titles", []):
                data[owner_id]["equipped_title"] = chosen
            
            await smart_update_v2(interaction, build_title_components(owner_id))
            return

    if parts[0] == "badge":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "prev":
            _badge_page[owner_id] = max(0, _badge_page.get(owner_id, 0) - 1)
            await smart_update_v2(interaction, build_badges_components(owner_id))
            return

        if parts[1] == "next":
            pages = build_badges_pages(owner_id)
            _badge_page[owner_id] = min(len(pages) - 1, _badge_page.get(owner_id, 0) + 1)
            await smart_update_v2(interaction, build_badges_components(owner_id))
            return

        if parts[1] == "feature":
            choice = values[0] if values else None
            if choice and choice in _earned_badge_keys(owner_id):
                data[owner_id]["featured_badge"] = choice
                mark_user_dirty(owner_id)
            await smart_update_v2(interaction, build_badges_components(owner_id))
            return

        if parts[1] == "noop":
            return

        return

    # ── GAMBLE ────────────────────────────────
    if parts[0] == "gamble":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        # Defer handling lives in on_interaction now: _cid_opens_modal() keeps
        # setbet / deal interactions unacknowledged so send_modal() works.
        init_user(owner_id)

        no_cd_subs  = {"back", "game_select", "menu", "warn"}
        no_cd_subs2 = {"setbet", "chances", "biome"}   # views / config, not a wager
        _sub2      = parts[2] if len(parts) > 2 else ""
        _is_wager  = parts[1] not in no_cd_subs and _sub2 not in no_cd_subs2
        if _is_wager:
            now         = time.time()
            last_gamble = data[owner_id].get("last_gamble", 0)
            gcd         = 0 if admin_buff_active() else GAMBLE_COOLDOWN
            if now - last_gamble < gcd:
                remaining = gcd - (now - last_gamble)
                await send_ephemeral_v2(interaction,
                    f"{emoji('cooldown')} Wait **{remaining:.1f}s** before gambling again.", 0xE67E22)
                return

        if parts[1] == "back":
            await smart_update_v2(interaction, build_gamble_menu(owner_id))
            return

        if parts[1] == "warn":
            await smart_update_v2(interaction, build_gamble_warning_panel(owner_id))
            return

        if parts[1] == "game_select":
            game = values[0] if values else None
            if game == "coinflip":
                await smart_update_v2(interaction, build_coinflip_panel(owner_id))
            elif game == "slots":
                await smart_update_v2(interaction, build_slots_panel(owner_id))
            elif game == "blackjack":
                _bj_resume_or_clear(owner_id)
                await smart_update_v2(interaction, build_blackjack_panel(owner_id))
            elif game == "roulette":
                await smart_update_v2(interaction, build_roulette_panel(owner_id))
            elif game == "rps":
                await smart_update_v2(interaction, build_rps_panel(owner_id))
            elif game == "dice":
                await smart_update_v2(interaction, build_dice_panel(owner_id))
            elif game == "highlow":
                data[owner_id].pop("_hl_n", None)
                data[owner_id].pop("_hl_s", None)
                await smart_update_v2(interaction, build_highlow_panel(owner_id))
            return

        if parts[1] == "menu":
            game = parts[2]
            if game == "coinflip":
                await smart_update_v2(interaction, build_coinflip_panel(owner_id))
            elif game == "slots":
                await smart_update_v2(interaction, build_slots_panel(owner_id))
            elif game == "blackjack":
                _bj_resume_or_clear(owner_id)
                await smart_update_v2(interaction, build_blackjack_panel(owner_id))
            return

        if parts[1] == "cf":
            sub = parts[2]
            if sub == "setbet":
                await interaction.response.send_modal(SetBetModal(owner_id, "cf"))
                return
            bet = data[owner_id].get("_cf_bet", 0)
            if not bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈.", 0xE74C3C)
                return
 
            flip = random.choice(["heads", "tails"])
            won  = flip == sub

            async with user_transaction(owner_id):
                paid = spend_money(owner_id, bet, "coinflip bet")
                if paid:
                    data[owner_id]["_cf_last_pick"] = sub
                    data[owner_id]["last_gamble"]   = time.time()
                    if won:
                        add_money(owner_id, bet * 2, "coinflip win")
                        data[owner_id]["stats"]["cf_wins"] = (
                            data[owner_id]["stats"].get("cf_wins", 0) + 1)
            if not paid:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈ for that bet.", 0xE74C3C)
                return

            result = {"won": won, "bet": bet, "flip": flip, "pick": sub}
            await smart_update_v2(interaction, build_coinflip_panel(owner_id, "result", result))
            return

        if parts[1] == "slots":
            sub = parts[2]
            if sub == "biome":
                biome_key  = values[0] if values else None
                user_level = data[owner_id].get("level", 1)
                if biome_key and biome_key in SLOT_BIOME_CONFIG:
                    lvl_req = next((lvl for k, lvl in BIOME_LEVELS if k == biome_key), 1)
                    if user_level < lvl_req:
                        await send_ephemeral_v2(interaction,
                            f"{emoji('cross_mark')} {BIOME_NAMES.get(biome_key, biome_key)} unlocks at Level {lvl_req}.",
                            0xE74C3C)
                        return
                    data[owner_id]["_slots_biome"] = biome_key   # NOT the real hunting biome
                await smart_update_v2(interaction, build_slots_panel(owner_id))
                return
            if sub == "setbet":
                cfg = _slots_biome_config(owner_id)
                await interaction.response.send_modal(SetBetModal(owner_id, "slots", cfg[0], cfg[1]))
                return
            if sub == "chances":
                await smart_update_v2(interaction, build_slots_chances_panel(owner_id))
                return
            if sub == "spin":
                bet = data[owner_id].get("_slots_bet", 0)
                if not bet:
                    await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Set a bet first.", 0xE74C3C)
                    return
                min_b, max_b, chance, mult = _slots_biome_config(owner_id)
                if bet < min_b:
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cross_mark')} Minimum bet on this table is **◈ {min_b:,}** — raise your bet.", 0xE74C3C)
                    return
                if bet > max_b:
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cross_mark')} Maximum bet on this table is **◈ {max_b:,}** — lower your bet.", 0xE74C3C)
                    return
                won    = random.randint(1, 100) <= chance
                payout = int(bet * mult) if won else 0
                # Make the reels tell the truth: 3-of-a-kind on a win, never on a loss.
                if won:
                    s     = random.choice(SLOT_SYMBOLS)
                    reels = [s, s, s]
                else:
                    reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
                    while len(set(reels)) == 1:
                        reels[random.randint(0, 2)] = random.choice(SLOT_SYMBOLS)
                async with user_transaction(owner_id):
                    paid = spend_money(owner_id, bet, "slots bet")
                    if paid:
                        if payout:
                            add_money(owner_id, payout, "slots")
                        if won:
                            data[owner_id]["stats"]["slots_wins"] = data[owner_id]["stats"].get("slots_wins", 0) + 1
                        data[owner_id]["last_gamble"] = time.time()
                if not paid:
                    await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈ for that bet.", 0xE74C3C)
                    return

                result = {"reels": reels, "bet": bet, "payout": payout, "won": won}
                await smart_update_v2(interaction, build_slots_panel(owner_id, "result", result))
                return

        if parts[1] == "rl":
            sub = parts[2]
            if sub == "setbet":
                await interaction.response.send_modal(SetBetModal(owner_id, "rl"))
                return
            bet = data[owner_id].get("_roulette_bet", 0)
            if not bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈.", 0xE74C3C)
                return
            if sub not in ROULETTE_BET_TYPES:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Unknown bet type.", 0xE74C3C)
                return
            color      = random.choices(ROULETTE_COLORS, weights=ROULETTE_WEIGHTS, k=1)[0]
            _, _, mult = ROULETTE_BET_TYPES[sub]
            won        = color == sub
            payout     = int(bet * mult) if won else 0
            async with user_transaction(owner_id):
                paid = spend_money(owner_id, bet, "roulette bet")
                if paid:
                    data[owner_id]["_roulette_pick"] = sub
                    if payout:
                        add_money(owner_id, payout, "roulette win")
                    if won:
                        data[owner_id]["stats"]["rl_wins"] = data[owner_id]["stats"].get("rl_wins", 0) + 1
                    data[owner_id]["last_gamble"] = time.time()
            if not paid:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈ for that bet.", 0xE74C3C)
                return

            result = {"color": color, "pick": sub, "bet": bet, "won": won, "payout": payout}
            await smart_update_v2(interaction, build_roulette_panel(owner_id, "result", result))
            return

        if parts[1] == "rps":
            sub = parts[2]
            if sub == "setbet":
                await interaction.response.send_modal(SetBetModal(owner_id, "rps"))
                return
            bet = data[owner_id].get("_rps_bet", 0)
            if not bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈.", 0xE74C3C)
                return
            if sub not in RPS_CHOICES:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Unknown choice.", 0xE74C3C)
                return
            bot_pick = random.choice(list(RPS_CHOICES.keys()))
            if sub == bot_pick:
                outcome = "tie"
            elif RPS_BEATS[sub] == bot_pick:
                outcome = "win"
            else:
                outcome = "lose"
            async with user_transaction(owner_id):
                paid = spend_money(owner_id, bet, "rps bet")
                if paid:
                    data[owner_id]["_rps_last_pick"] = sub
                    if outcome == "tie":
                        add_money(owner_id, bet, "rps push")          # stake back
                    elif outcome == "win":
                        add_money(owner_id, bet * 2, "rps win")
                        data[owner_id]["stats"]["rps_wins"] = data[owner_id]["stats"].get("rps_wins", 0) + 1
                    data[owner_id]["last_gamble"] = time.time()
            if not paid:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈ for that bet.", 0xE74C3C)
                return

            result = {"pick": sub, "bot_pick": bot_pick, "bet": bet, "outcome": outcome}
            await smart_update_v2(interaction, build_rps_panel(owner_id, "result", result))
            return

        if parts[1] == "dice":
            sub = parts[2]
            if sub == "setbet":
                await interaction.response.send_modal(SetBetModal(owner_id, "dice"))
                return
            bet = data[owner_id].get("_dice_bet", 0)
            if not bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈.", 0xE74C3C)
                return
            if sub not in DICE_BETS:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Unknown bet.", 0xE74C3C)
                return
            d1, d2       = random.randint(1, 6), random.randint(1, 6)
            total        = d1 + d2
            _, pred, mlt = DICE_BETS[sub]
            won          = pred(total)
            payout       = int(bet * mlt) if won else 0
            async with user_transaction(owner_id):
                paid = spend_money(owner_id, bet, "dice bet")
                if paid:
                    if payout:
                        add_money(owner_id, payout, "dice win")
                    data[owner_id]["last_gamble"] = time.time()
            if not paid:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈ for that bet.", 0xE74C3C)
                return
            result = {"dice": (d1, d2), "pick": sub, "bet": bet, "won": won, "payout": payout}
            await smart_update_v2(interaction, build_dice_panel(owner_id, "result", result))
            return

        if parts[1] == "hl":
            sub = parts[2]
            if sub == "setbet":
                await interaction.response.send_modal(SetBetModal(owner_id, "hl"))
                return
            bet = data[owner_id].get("_hl_bet", 0)
            if not bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈.", 0xE74C3C)
                return

            if sub == "draw":
                data[owner_id]["_hl_n"] = random.randint(1, 13)
                data[owner_id]["_hl_s"] = random.choice(_HL_SUITS)
                await smart_update_v2(interaction, build_highlow_panel(owner_id, "guess"))
                return

            if sub in ("hi", "lo"):
                n = data[owner_id].get("_hl_n")
                if not n:
                    await smart_update_v2(interaction, build_highlow_panel(owner_id))
                    return
                m_hi, m_lo = _hl_multipliers(n)
                mlt        = m_hi if sub == "hi" else m_lo
                if mlt == 0:
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cross_mark')} That side isn't a valid bet on this card — re-deal or take the other side.", 0xE74C3C)
                    return
                m  = random.randint(1, 13)
                ms = random.choice(_HL_SUITS)
                s  = data[owner_id].get("_hl_s", "♠")
                if m == n:
                    outcome, payout = "push", bet          # refund
                elif (m > n) == (sub == "hi"):
                    outcome, payout = "win", int(bet * mlt)
                else:
                    outcome, payout = "lose", 0
                async with user_transaction(owner_id):
                    paid = spend_money(owner_id, bet, "highlow bet")
                    if paid:
                        if payout:
                            add_money(owner_id, payout, f"highlow {outcome}")
                        data[owner_id]["last_gamble"] = time.time()
                        data[owner_id].pop("_hl_n", None)
                        data[owner_id].pop("_hl_s", None)
                if not paid:
                    await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈ for that bet.", 0xE74C3C)
                    return
                result = {"n": n, "m": m, "s": s, "ms": ms, "guess": sub,
                          "outcome": outcome, "bet": bet, "payout": payout}
                await smart_update_v2(interaction, build_highlow_panel(owner_id, "result", result))
                return
            return

        if parts[1] == "bj":
            action = parts[2]
            if action == "deal":
                cur = _bj_state.get(owner_id)
                if cur and not cur.get("done"):
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cross_mark')} Finish your current hand first.", 0xE74C3C)
                    return
                await interaction.response.send_modal(BlackjackBetModal(owner_id))
                return
            # custom_id is gamble:bj:<action>:<hid>:<user_id> — the hand id ties a
            # button to one specific deal; stale buttons from a prior hand miss.
            hid = parts[3] if len(parts) >= 5 else None
            st  = _bj_state.get(owner_id)
            if not st or st.get("done") or st.get("hid") != hid:
                await smart_update_v2(interaction, build_blackjack_panel(owner_id))
                return
            async with user_transaction(owner_id):
                st = _bj_state.get(owner_id)
                if not st or st.get("done") or st.get("hid") != hid:
                    pass   # a concurrent click already settled this hand
                else:
                    if action == "hit":
                        st["player"].append(st["deck"].pop())
                        pv = _bj_hand_value(st["player"])
                        if pv > 21:
                            st.update({"done": True, "outcome": f"{emoji('impact')} Bust!", "net": -st["bet"]})
                        elif pv == 21:
                            action = "stand"
                    if not st.get("done") and action == "stand":
                        while _bj_hand_value(st["dealer"]) < 17:
                            st["dealer"].append(st["deck"].pop())
                        p_val = _bj_hand_value(st["player"])
                        d_val = _bj_hand_value(st["dealer"])
                        bet   = st["bet"]
                        if d_val > 21 or p_val > d_val:
                            add_money(owner_id, bet * 2, "blackjack win")
                            st.update({"done": True, "outcome": f"{emoji('check_mark')} You win!", "net": bet})
                            data[owner_id]["stats"]["bj_wins"] = (
                                data[owner_id]["stats"].get("bj_wins", 0) + 1
                            )
                        elif p_val == d_val:
                            add_money(owner_id, bet, "blackjack: tie")
                            st.update({"done": True, "outcome": f"{emoji('handshake')} Push!", "net": 0})
                        else:
                            st.update({"done": True, "outcome": f"{emoji('cross_mark')} Dealer wins.", "net": -bet})
            await smart_update_v2(interaction, build_blackjack_panel(owner_id))
            return

    # ── LOTTERY ───────────────────────────────
    if parts[0] == "lottery":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        init_user(owner_id)

        if parts[1] == "buy":
            await interaction.response.send_modal(LotteryBuyModal(owner_id))
            return
        
        await smart_update_v2(interaction, build_lottery_components(owner_id))
        return

    # ── PROFILE ───────────────────────────────
    if parts[0] == "profile":
        panel     = parts[1]
        target_id = parts[2]
        self_id   = str(interaction.user.id)
        # custom_id is profile:<panel>:<target>[:<viewer>] — the 4th segment is
        # present only on a cross-view (someone browsing another player's profile).
        cid_viewer = parts[3] if len(parts) > 3 else self_id
        if self_id != cid_viewer and self_id != target_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(cid_viewer), 0xE74C3C)
            return
        init_user(target_id)
        is_self = (target_id == self_id)
        nm  = (interaction.user.display_name if is_self
               else (data.get(target_id, {}).get("_display_name") or get_username(target_id)))
        vid = None if is_self else self_id

        if panel == "main":
            await smart_update_v2(interaction, build_profile_components(target_id, nm, "main", viewer_id=vid))
            return
        if panel == "inventory":
            await smart_update_v2(interaction, build_inventory_components(target_id, nm, viewer_id=vid))
            return
        if panel == "statistics":
            await smart_update_v2(interaction, build_statistics_components(target_id, nm, viewer_id=vid))
            return
        if panel == "leaderboard":
            await smart_update_v2(interaction, build_personal_leaderboard_components(target_id, nm, viewer_id=vid))
            return
        if panel == "log":
            key      = vid or target_id
            log_page = _profile_log_page.get(key, 0)
            await smart_update_v2(interaction, build_log_v2_components(target_id, log_page, nm, viewer_id=vid))
            return
        await _navigate(interaction, self_id, panel, interaction.user.display_name)
        return

    # ── VERIFY REFRESH ────────────────────────────
    if parts[0] == "verify":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        if parts[1] == "refresh":
            await smart_update_v2(interaction, build_verify_v2(owner_id))
        return

    # ── LOG PROFILE ───────────────────────────
    if parts[0] == "log":
        target_id  = parts[2]
        self_id    = str(interaction.user.id)
        cid_viewer = parts[3] if len(parts) > 3 else self_id
        if self_id != cid_viewer and self_id != target_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(cid_viewer), 0xE74C3C)
            return
        is_self = (target_id == self_id)
        vid = None if is_self else self_id
        key = vid or target_id
        nm  = (interaction.user.display_name if is_self
               else (data.get(target_id, {}).get("_display_name") or get_username(target_id)))

        current_page = _profile_log_page.get(key, 0)
        total        = len(data[target_id].get("log", []))
        if parts[1] == "prev":
            _profile_log_page[key] = max(0, current_page - 1)
        elif parts[1] == "next":
            _profile_log_page[key] = min(max(total - 1, 0), current_page + 1)
        await smart_update_v2(interaction,
            build_log_v2_components(target_id, _profile_log_page.get(key, 0), nm, viewer_id=vid))
        return

    # ── RECORD PROFILE ────────────────────────
    if parts[0] == "record":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        current_page = _profile_record_page.get(owner_id, 0)
        total        = len(BIOME_LEVELS)
        if parts[1] == "prev":
            _profile_record_page[owner_id] = max(0, current_page - 1)
        elif parts[1] == "next":
            _profile_record_page[owner_id] = min(total - 1, current_page + 1)
        await smart_update_v2(interaction, build_record_v2_components(owner_id, _profile_record_page[owner_id]))
        return

    # ── LOG CMD ───────────────────────────────
    if parts[0] == "log_cmd":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        current_page = _log_state.get(owner_id, 0)
        total        = len(data[owner_id].get("log", []))
        if parts[1] == "prev":
            _log_state[owner_id] = max(0, current_page - 1)
        elif parts[1] == "next":
            _log_state[owner_id] = min(total - 1, current_page + 1)
        await smart_update_v2(interaction, build_log_standalone_v2_components(owner_id, _log_state[owner_id]))
        return

    # ── RECORD CMD ────────────────────────────
    if parts[0] == "record_cmd":
        action    = parts[1]
        viewer_id = parts[2]
        target_id = parts[3]
        if str(interaction.user.id) != viewer_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(target_id), 0xE74C3C)
            return

        state        = _record_state.get(viewer_id, {"target_id": target_id, "biome_idx": 0})
        current_page = state["biome_idx"]
        total        = len(BIOME_LEVELS)
        if action == "prev":
            state["biome_idx"] = max(0, current_page - 1)
        elif action == "next":
            state["biome_idx"] = min(total - 1, current_page + 1)
        _record_state[viewer_id] = state
        await smart_update_v2(interaction, build_record_standalone_v2_components(viewer_id, target_id, state["biome_idx"]))
        return

    # ── LEADERBOARD ───────────────────────────
    if parts[0] == "lb":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        state  = _lb_state.get(owner_id, {
            "mode": "hunter", "scope": "global",
            "stat": "Level", "page": 0, "period": "all",
            "guild": interaction.guild,
        })
        state.setdefault("period", "all")
        action = parts[1]
        if action == "stat":
            state["stat"] = values[0] if values else "Level"
            state["page"] = 0
        elif action == "period":
            state["period"] = parts[2]
            state["page"]   = 0
        elif action == "mode":
            state["mode"] = parts[2]
            state["stat"] = "Level"
            state["page"] = 0
        elif action == "scope":
            state["scope"] = "global" if state["scope"] == "server" else "server"
            state["page"]  = 0
        elif action == "prev":
            state["page"] = max(0, state["page"] - 1)
        elif action == "next":
            PS    = 10
            if state["mode"] == "hunter":
                cands = [u for u in (get_server_user_ids(state["guild"])
                                     if state["scope"] == "server" else list(data.keys()))
                         if _lb_eligible(u)]
            else:
                cands = list(tribe_data.keys())
            total_pages = max(1, (len(cands) + PS - 1) // PS)
            state["page"] = min(total_pages - 1, state["page"] + 1)
        _lb_state[owner_id] = state
        await smart_update_v2(interaction, build_leaderboard_v2_components(
            owner_id, state["guild"], state["mode"],
            state["scope"], state["stat"], state["page"], state["period"]))
        return

    # ── SUGGESTION buttons (admin channel) ────
    if parts[0] == "suggestion":
        # custom_id format: suggestion:<action>:<submitter_id>:<msg_id>
        action       = parts[1]
        submitter_id = parts[2]
        msg_id       = parts[3]

        if not is_admin(interaction):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Admins only.", 0xE74C3C)
            return

        if action in ("agree", "neutral", "disagree"):
            entry    = _suggestion_store.get(msg_id)
            admin_id = str(interaction.user.id)

            if not entry:
                # This store doesn't know the suggestion. Either it genuinely
                # expired, or another bot instance owns it and will respond —
                # stay silent so we don't double up on that instance's reply.
                return
            if entry.get("answered"):
                await send_ephemeral_v2(interaction,
                    f"{emoji('lock')} This suggestion has already been answered — voting is closed.", 0x95A5A6)
                return

            votes = entry.setdefault("votes", {"agree": set(), "neutral": set(), "disagree": set()})
            for v in votes.values():
                v.discard(admin_id)
            votes[action].add(admin_id)

            # Open the reply modal (must be the initial response); the channel
            # message is patched afterwards on a separate HTTP call.
            await interaction.response.send_modal(
                SuggestionReplyModal(submitter_id, msg_id, action)
            )

            # Refresh the channel message with the new vote counts.
            channel_msg_id = entry.get("channel_msg_id")
            if channel_msg_id:
                try:
                    await bot.http.request(
                        Route("PATCH", "/channels/{channel_id}/messages/{message_id}",
                              channel_id=SUGGESTION_CHANNEL_ID, message_id=channel_msg_id),
                        json={"flags": V2_FLAGS,
                              "components": _suggestion_msg_components(entry, submitter_id, msg_id),
                              "allowed_mentions": {"parse": []}})
                except Exception:
                    pass
            return

        return

    # ── REPORT buttons (admin + public) ───────
    if parts[0] == "report_btn":
        # custom_id: report_btn:<action>:<submitter_id>:<msg_id>
        action       = parts[1]
        submitter_id = parts[2]
        msg_id       = parts[3]
        clicker_id   = str(interaction.user.id)

        if action == "also_seen":
            entry = _report_store.get(msg_id)
            if entry is None:
                # Unknown to this store: it was already resolved, or another bot
                # instance owns it. Stay silent rather than fire a spurious
                # "not found" alongside the owning instance's real response.
                return
            if clicker_id == submitter_id:
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You submitted this report.", 0xE74C3C)
                return
            seen_set = entry.setdefault("seen", set())
            if clicker_id in seen_set:
                await send_ephemeral_v2(interaction, f"{emoji('check_mark')} Already recorded your confirmation.", 0x95A5A6)
                return
            seen_set.add(clicker_id)
            seen_n = len(seen_set)
            # Patch channel message button label with updated count
            channel_msg_id = entry.get("channel_msg_id")
            if channel_msg_id:
                try:
                    patch_route = Route("PATCH", "/channels/{channel_id}/messages/{message_id}",
                                        channel_id=REPORTS_CHANNEL_ID, message_id=channel_msg_id)
                    await bot.http.request(patch_route, json={
                        "flags": V2_FLAGS,
                        "components": [{"type": 17, "accent_color": entry.get("color", 0xE67E22), "spoiler": False,
                            "components": [
                                {"type": 10, "content": entry.get("content", "")},
                                {"type": 14, "divider": True, "spacing": 1},
                                {"type": 1, "components": [
                                    {"type": 2, "style": 1, "label": f"I've also seen this ({seen_n})", "emoji": emoji_partial("eyes"),
                                     "custom_id": f"report_btn:also_seen:{submitter_id}:{msg_id}"},
                                    {"type": 2, "style": 3, "label": "Resolved", "emoji": emoji_partial('check_mark'),
                                     "custom_id": f"report_btn:resolved:{submitter_id}:{msg_id}"},
                                ]},
                            ]}],
                        "allowed_mentions": {"parse": []},
                    })
                except Exception:
                    pass
            await send_ephemeral_v2(interaction, f"{emoji('check_mark')} Noted — thanks for confirming!", 0x2ECC71)
            # DM the original reporter
            try:
                route = Route("POST", "/users/@me/channels")
                dm_ch = await bot.http.request(route, json={"recipient_id": submitter_id})
                dm_route = Route("POST", "/channels/{channel_id}/messages", channel_id=dm_ch["id"])
                await bot.http.request(dm_route, json={
                    "flags": V2_FLAGS,
                    "components": [{"type": 17, "accent_color": 0xF39C12, "spoiler": False,
                        "components": [{"type": 10, "content":
                            f"### {emoji('eyes')} Someone else has seen your report!\n"
                            f"**{interaction.user.display_name}** confirmed they've also experienced the issue you reported.\n"
                            f"-# Total confirmations: **{seen_n}**"
                        }]}],
                    "allowed_mentions": {"parse": []},
                })
            except Exception:
                pass
            return

        if action == "resolved":
            if not is_admin(interaction):
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Admins only.", 0xE74C3C)
                return
            entry = _report_store.get(msg_id)
            if entry is None:
                # Already resolved (double-click), or another bot instance owns
                # this report. Don't send a second "resolved" DM with a bogus
                # 0-confirmations count — let the owning instance handle it.
                return
            # DM the submitter
            try:
                route = Route("POST", "/users/@me/channels")
                dm_ch = await bot.http.request(route, json={"recipient_id": submitter_id})
                dm_route = Route("POST", "/channels/{channel_id}/messages", channel_id=dm_ch["id"])
                seen_count = len(entry.get("seen", set()))
                await bot.http.request(dm_route, json={
                    "flags": V2_FLAGS,
                    "components": [{"type": 17, "accent_color": 0x2ECC71, "spoiler": False,
                        "components": [{"type": 10, "content":
                            f"### {emoji('check_mark')} Your report has been resolved!\n"
                            f"The team has marked your report as resolved. Thank you for helping improve the game!\n"
                            f"-# {seen_count} other player(s) confirmed this issue."
                        }]}],
                    "allowed_mentions": {"parse": []},
                })
            except Exception:
                pass

            # Mark the report channel message as resolved (strip the buttons)
            channel_msg_id = entry.get("channel_msg_id")
            if channel_msg_id:
                try:
                    patch_route = Route("PATCH", "/channels/{channel_id}/messages/{message_id}",
                                        channel_id=REPORTS_CHANNEL_ID, message_id=channel_msg_id)
                    await bot.http.request(patch_route, json={
                        "flags": V2_FLAGS,
                        "components": [{"type": 17, "accent_color": 0x2ECC71, "spoiler": False,
                            "components": [{"type": 10, "content":
                                entry.get("content", "")
                                + f"\n\n{emoji('check_mark')} **Resolved** by <@{interaction.user.id}>"}]}],
                        "allowed_mentions": {"parse": []},
                    })
                except Exception:
                    pass

            _report_store.pop(msg_id, None)
            await send_ephemeral_v2(interaction,
                f"{emoji('check_mark')} Report marked as resolved. The reporter has been notified.", 0x2ECC71)
            return

        return


# ─────────────────────────────────────────────
# MODALS
# ─────────────────────────────────────────────

class _V2Modal(discord.ui.Modal):
    """Base for every modal in this bot.

    ``on_error`` swallows Discord HTTP failures quietly: when a second copy of
    the bot is running on the same token, both instances register the modal and
    both run ``on_submit`` — the loser hits "Unknown interaction" / "already
    acknowledged". That's noise, not a bug in the handler, so log one line and
    don't push an error at the user (the winning instance already replied).
    """
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if isinstance(error, discord.HTTPException):
            logger.warning("modal response failed (%s): %s", type(self).__name__, error)
            return
        logger.exception("modal crashed (%s)", type(self).__name__, exc_info=error)
        try:
            await send_ephemeral_v2(
                interaction,
                f"{emoji('warning')} Something went wrong. Please try again.",
                0xE74C3C,
            )
        except Exception:
            pass


class SetBetModal(_V2Modal, title="Set Your Bet"):
    bet_input = discord.ui.TextInput(
        label="Bet amount (◈)",
        placeholder="e.g. 1000, 50K, 1M",
        required=True,
        max_length=20,
    )

    def __init__(self, user_id: str, game: str, min_bet: int = 1, max_bet: int = 0):
        super().__init__()
        self.user_id = str(user_id)
        self.game    = game
        self.min_bet = min_bet
        self.max_bet = max_bet
        if min_bet or max_bet:
            self.bet_input.placeholder = (
                f"Min: ◈{min_bet:,}  Max: ◈{max_bet:,}" if max_bet
                else f"Min: ◈{min_bet:,}"
            )

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        parsed = parse_amount(self.bet_input.value)
        if not parsed or parsed <= 0:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Invalid amount.", 0xE74C3C)
            return
        if parsed > data[self.user_id]["money"]:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈.", 0xE74C3C)
            return
        if self.min_bet and parsed < self.min_bet:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Minimum bet is ◈ {self.min_bet:,}.", 0xE74C3C)
            return
        if self.max_bet and parsed > self.max_bet:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Maximum bet is ◈ {self.max_bet:,}.", 0xE74C3C)
            return
        key_map = {"cf": "_cf_bet", "slots": "_slots_bet", "rl": "_roulette_bet",
                   "rps": "_rps_bet", "dice": "_dice_bet", "hl": "_hl_bet"}
        data[self.user_id][key_map[self.game]] = parsed
        builders = {
            "cf":    lambda: build_coinflip_panel(self.user_id),
            "slots": lambda: build_slots_panel(self.user_id),
            "rl":    lambda: build_roulette_panel(self.user_id),
            "rps":   lambda: build_rps_panel(self.user_id),
            "dice":  lambda: build_dice_panel(self.user_id),
            "hl":    lambda: build_highlow_panel(self.user_id),
        }
        await smart_update_v2(interaction, builders[self.game]())

class CrateBuyModal(_V2Modal, title="Buy Crates"):
    qty_input = discord.ui.TextInput(
        label="How many to buy?",
        placeholder="e.g. 1, 5, 10",
        required=True,
        max_length=6,
    )

    def __init__(self, user_id: str, crate_name: str):
        super().__init__()
        self.user_id    = str(user_id)
        self.crate_name = crate_name

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        raw = self.qty_input.value.strip()
        qty = parse_amount(raw)
        if not qty or qty <= 0:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Invalid amount.", 0xE74C3C)
            return

        crate  = CRATE_TIERS[self.crate_name]
        rarity = crate["rarity"]
        need   = crate["crystal_cost"] * qty

        have = crystal_count(self.user_id, rarity)
        if have < need:
            await send_ephemeral_v2(
                interaction,
                f"{emoji('cross_mark')} Need {CRYSTAL_ICONS[rarity]} **{need}** {_rarity_label(rarity)} "
                f"Crystals for {qty}× {self.crate_name} — you have **{have}**.",
                0xE74C3C)
            return

        async with user_transaction(self.user_id):
            if crystal_count(self.user_id, rarity) < need:   # re-check under lock
                await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough crystals.", 0xE74C3C)
                return
            data[self.user_id].setdefault("crystals", {})[rarity] = (
                crystal_count(self.user_id, rarity) - need)
            inv = data[self.user_id].setdefault("crate_inv", {})
            inv[self.crate_name] = inv.get(self.crate_name, 0) + qty

        await smart_update_v2(interaction, build_crate_shop_components(self.user_id))

class LotteryBuyModal(_V2Modal, title="Buy Lottery Tickets"):
    qty_input = discord.ui.TextInput(
        label="How many tickets?",
        placeholder=f"e.g. 5  (◈{LOTTERY_TICKET_COST:,} each)",
        required=True,
        max_length=10,
    )

    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = str(user_id)

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        raw = self.qty_input.value.strip()
        qty = parse_amount(raw)
        if not qty or qty <= 0:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Invalid amount.", 0xE74C3C)
            return
        total_cost = qty * LOTTERY_TICKET_COST
        if data[self.user_id]["money"] < total_cost:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Need **◈ {total_cost:,}** for {qty:,} ticket(s).", 0xE74C3C)
            return
        paid = False
        async with user_transaction(self.user_id):
            if data[self.user_id]["money"] >= total_cost:          # re-check under lock
                paid = spend_money(self.user_id, total_cost, "lottery tickets")
                if paid:
                    ld = lottery_data
                    ld["tickets"][self.user_id] = ld["tickets"].get(self.user_id, 0) + qty
                    ld["pool"]                  = ld.get("pool", 0) + total_cost
                    save_lottery(ld)
        if not paid:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Need **◈ {total_cost:,}** for {qty:,} ticket(s).", 0xE74C3C)
            return
        await smart_update_v2(interaction, build_lottery_components(self.user_id))

class CustomColorModal(_V2Modal, title="Custom Embed Color"):
    hex_input = discord.ui.TextInput(
        label="Hex Color Code",
        placeholder="#FF69B4",
        required=True,
        max_length=7,
    )

    def __init__(self, user_id):
        super().__init__()
        self.user_id = str(user_id)

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        raw = self.hex_input.value.strip().lstrip("#")
        if len(raw) != 6 or not all(c in string.hexdigits for c in raw):
            await send_ephemeral_v2(interaction, "Invalid hex. Use `#RRGGBB`.", 0xE74C3C)
            return
        async with user_transaction(self.user_id):
            data[self.user_id]["color"] = f"#{raw.upper()}"
        await smart_update_v2(interaction, build_color_panel_components(self.user_id))

class AmmoBuyModal(_V2Modal, title="Buy Ammo"):
    qty_input = discord.ui.TextInput(
        label="How many shots to buy?",
        placeholder=f"e.g. 100  (max {AMMO_MAX_STACK:,} per ammo type)",
        required=True,
        max_length=6,
    )

    def __init__(self, user_id: str, ammo_name: str):
        super().__init__()
        self.user_id   = str(user_id)
        self.ammo_name = ammo_name

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        raw = self.qty_input.value.strip()
        if not raw.isdigit() or int(raw) <= 0:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Enter a positive whole number.", 0xE74C3C)
            return
        qty = int(raw)
        a   = AMMO.get(self.ammo_name)
        if not a:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Unknown ammo.", 0xE74C3C)
            return
        current_owned = data[self.user_id].get("ammo_inv", {}).get(self.ammo_name, 0)
        can_buy       = AMMO_MAX_STACK - current_owned
        if can_buy <= 0:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Already at max stack ({AMMO_MAX_STACK:,}) for **{self.ammo_name}**.", 0xE74C3C)
            return
        if qty > can_buy:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Can only buy **{can_buy:,}** more (stack limit: {AMMO_MAX_STACK:,}).", 0xE74C3C)
            return
        total_cost = ev_price(a["price"] * qty)   # event 50%-off
        currency   = a["currency"]
        paid = False
        async with user_transaction(self.user_id):
            # re-check stack room under the lock, then charge + grant atomically
            owned_now = data[self.user_id].get("ammo_inv", {}).get(self.ammo_name, 0)
            if owned_now + qty > AMMO_MAX_STACK:
                pass
            elif currency == "money":
                paid = spend_money(self.user_id, total_cost, "shop ammo")
            else:
                paid = spend_gems(self.user_id, total_cost, "shop ammo")
            if paid:
                inv = data[self.user_id].setdefault("ammo_inv", {})
                inv[self.ammo_name] = owned_now + qty
        if not paid:
            icon = "◈" if currency == "money" else emoji('gem')
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Need {icon} {total_cost:,} to buy {qty:,}× {self.ammo_name}.", 0xE74C3C)
            return
        await smart_update_v2(interaction, build_shop_components(self.user_id, "ammo"))

class TribeInviteModal(_V2Modal, title="Invite a Player"):
    uid_input = discord.ui.TextInput(
        label="User ID",
        placeholder="123456789012345678",
        required=True,
        max_length=100,
    )

    def __init__(self, user_id, tribe_name):
        super().__init__()
        self.user_id    = str(user_id)
        self.tribe_name = tribe_name

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        raw = self.uid_input.value.strip()
        if raw.startswith("<@") and raw.endswith(">"):
            raw = raw.replace("<@", "").replace("!", "").replace(">", "").strip()
        ok, msg = await _tribe_do_invite(
            self.user_id, self.tribe_name, raw, interaction.user.display_name)
        await send_ephemeral_v2(interaction, msg, 0x2ECC71 if ok else 0xE74C3C)

class TribeSetDescModal(_V2Modal, title="Set Tribe Description"):
    desc_input = discord.ui.TextInput(
        label="Description",
        placeholder="Enter a description...",
        required=True,
        max_length=200,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, user_id, tribe_name):
        super().__init__()
        self.user_id    = str(user_id)
        self.tribe_name = tribe_name

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        if tribe_role_of(self.user_id, self.tribe_name) not in ("leader", "officer"):
            await send_ephemeral_v2(
                interaction, f"{emoji('cross_mark')} You no longer have permission to edit this tribe.", 0xE74C3C)
            return
        async with user_tribe_transaction(self.user_id, self.tribe_name):
            if tribe_role_of(self.user_id, self.tribe_name) in ("leader", "officer"):
                tribe_data[self.tribe_name]["description"] = self.desc_input.value
        sort = _tribe_sort.get(self.user_id, "rank")
        await smart_update_v2(interaction, build_tribe_components(self.user_id, self.tribe_name, "actions", sort))

class TribeLeaveLeaderModal(_V2Modal, title="Assign New Leader Before Leaving"):
    uid_input = discord.ui.TextInput(
        label="New Leader User ID",
        placeholder="123456789012345678",
        required=True,
        max_length=20,
    )

    def __init__(self, user_id, tribe_name):
        super().__init__()
        self.user_id    = str(user_id)
        self.tribe_name = tribe_name

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        if tribe_role_of(self.user_id, self.tribe_name) != "leader":
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Only the leader can transfer leadership.", 0xE74C3C)
            return
        target = self.uid_input.value.strip()
        td     = tribe_data.get(self.tribe_name)
        if not td:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Tribe no longer exists.", 0xE74C3C)
            return
        all_ids = td["roles"]["officer"] + td["roles"]["members"] + td["roles"].get("recruits", [])
        if target not in all_ids:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} That user is not a tribe member.", 0xE74C3C)
            return
        async with user_tribe_transaction(self.user_id, self.tribe_name):
            if tribe_role_of(self.user_id, self.tribe_name) == "leader":
                _ensure_tribe_fields(td)
                _tribe_remove_member(td, target, note="was promoted to leader in")
                _tribe_remove_member(td, self.user_id, note="stepped down and left")
                td["roles"]["leader"]       = target
                td["member_since"][target]  = int(time.time())
                data[self.user_id]["tribe"] = None
                data[self.user_id]["tribe_left_ts"] = time.time()
        await smart_update_v2(interaction, build_menu_components(self.user_id, interaction.user.display_name))

class TribeCreateModal(_V2Modal, title="Create a Tribe"):
    name_input = discord.ui.TextInput(
        label="Tribe Name",
        placeholder="Enter your tribe name...",
        required=True,
        max_length=32,
    )
    desc_input = discord.ui.TextInput(
        label="Description",
        placeholder="Optional...",
        required=False,
        max_length=200,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, user_id):
        super().__init__()
        self.user_id = str(user_id)

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        name = self.name_input.value.strip()
        if not name:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Enter a tribe name.", 0xE74C3C)
            return
        created = False
        err     = f"{emoji('cross_mark')} Could not create tribe."
        async with user_tribe_transaction(self.user_id, name):
            # membership + name availability can both change while the form is open
            if data[self.user_id].get("tribe"):
                err = f"{emoji('cross_mark')} You're already in a tribe."
            elif name in tribe_data:
                err = f"{emoji('cross_mark')} Tribe name taken."
            else:
                init_tribe(name, self.user_id)
                tribe_data[name]["description"] = self.desc_input.value.strip()
                created = True
        if not created:
            await send_ephemeral_v2(interaction, err, 0xE74C3C)
            return
        await smart_update_v2(interaction, build_tribe_components(self.user_id, name, "main"))

class BanAppealModal(_V2Modal, title="Submit a Ban Appeal"):
    reason_input = discord.ui.TextInput(
        label="Why should your ban be lifted?",
        placeholder="Explain your situation honestly...",
        required=True,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = str(user_id)

    async def on_submit(self, interaction: discord.Interaction):
        b       = get_ban(self.user_id)
        used    = b.get("appeals_used", 0)
        max_app = b.get("appeals_max", 2)
        if used >= max_app:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You have no appeal chances left.", 0xE74C3C)
            return
        data[self.user_id]["ban"]["appeals_used"] = used + 1

        import uuid as _uuid
        appeal_id = _uuid.uuid4().hex[:12]
        _appeal_store[appeal_id] = {
            "user_id": self.user_id,
            "reason": self.reason_input.value,
            "channel_msg_id": None,
            "handled": False,
        }

        # Ack the appellant immediately, then post to the review channel.
        await send_ephemeral_v2(interaction,
            f"{emoji('check_mark')} Your appeal has been submitted. Admins will review it shortly.", 0x2ECC71)

        exp_ts  = b.get("expires_ts", 0)
        exp_str = f"<t:{exp_ts}:R>" if exp_ts != 0 else "Permanent"
        try:
            route = Route("POST", "/channels/{channel_id}/messages",
                          channel_id=BAN_APPEAL_CHANNEL_ID)
            sent = await bot.http.request(route, json={
                "flags": V2_FLAGS,
                "components": [{"type": 17, "accent_color": 0x3498DB, "spoiler": False,
                    "components": [
                        {"type": 10, "content":
                            f"### `📋` Ban Appeal\n"
                            f"**User:** <@{self.user_id}> (`{self.user_id}`)\n"
                            f"**Reason for ban:** {b.get('reason', 'N/A')}\n"
                            f"**Ban expires:** {exp_str}\n"
                            f"**Appeals used:** {data[self.user_id]['ban']['appeals_used']}/{max_app}\n\n"
                            f"**Appeal message:**\n{self.reason_input.value}"
                        },
                        {"type": 14, "divider": True, "spacing": 1},
                        {"type": 1, "components": [
                            {"type": 2, "style": 3, "label": "Accept", "emoji": emoji_partial('check_mark'),
                             "custom_id": f"appeal:accept:{self.user_id}:{appeal_id}"},
                            {"type": 2, "style": 4, "label": "Reject", "emoji": emoji_partial('cross_mark'),
                             "custom_id": f"appeal:reject:{self.user_id}:{appeal_id}"},
                        ]},
                    ]}],
                "allowed_mentions": {"parse": []},
            })
            _appeal_store[appeal_id]["channel_msg_id"] = sent.get("id")
        except Exception as e:
            print("Appeal channel send error:", e)

class BlackjackBetModal(_V2Modal, title="Blackjack — Place Your Bet"):
    bet_input = discord.ui.TextInput(
        label="Bet amount (◈)",
        placeholder="e.g. 1000, 50K, 1M",
        required=True,
        max_length=20,
    )

    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = str(user_id)

    async def on_submit(self, interaction: discord.Interaction):
        if not await _modal_gate(interaction, self.user_id):
            return
        parsed = parse_amount(self.bet_input.value)
        if not parsed or parsed <= 0:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Invalid amount.", 0xE74C3C)
            return

        cur = _bj_state.get(self.user_id)
        if cur and not cur.get("done"):
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Finish your current hand first.", 0xE74C3C)
            return

        deck   = _bj_deck()
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]
        hid    = secrets.token_hex(4)

        busy = False
        async with user_transaction(self.user_id):
            # Re-check under the lock and register the hand in the SAME critical
            # section: two bets submitted at once used to both pass the check
            # above, and the second hand silently replaced (and lost) the first.
            cur = _bj_state.get(self.user_id)
            if cur and not cur.get("done"):
                busy = True
                paid = False
            else:
                paid = spend_money(self.user_id, parsed, "blackjack bet")
                if paid:
                    data[self.user_id]["last_gamble"] = time.time()
                    _bj_state[self.user_id] = {
                        "hid": hid, "bet": parsed, "deck": deck,
                        "player": player, "dealer": dealer,
                        "done": False,
                    }
        if busy:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Finish your current hand first.", 0xE74C3C)
            return
        if not paid:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough ◈ for that bet.", 0xE74C3C)
            return

        # Settle natural blackjacks up-front — but check BOTH hands first.
        p_bj = _bj_hand_value(player) == 21
        d_bj = _bj_hand_value(dealer) == 21
        if p_bj or d_bj:
            async with user_transaction(self.user_id):
                st = _bj_state.get(self.user_id)
                if st and st.get("hid") == hid and not st.get("done"):
                    if p_bj and d_bj:
                        add_money(self.user_id, parsed, "blackjack: push (both 21)")
                        st.update({"done": True, "outcome": f"{emoji('handshake')} Push — both blackjack", "net": 0})
                    elif p_bj:
                        payout = int(parsed * 2.5)
                        add_money(self.user_id, payout, "blackjack: 21")
                        st["dealer"] = dealer
                        st.update({"done": True, "outcome": "`🃏` Blackjack!", "net": payout - parsed})
                        data[self.user_id]["stats"]["bj_wins"] = (
                            data[self.user_id]["stats"].get("bj_wins", 0) + 1)
                    else:  # dealer blackjack only
                        st.update({"done": True, "outcome": f"{emoji('cross_mark')} Dealer blackjack", "net": -parsed})

        await smart_update_v2(interaction, build_blackjack_panel(self.user_id))

_VERDICT_LABELS = {"agree": f"{emoji('check_mark')} Agreed", "neutral": "`➖` Neutral", "disagree": f"{emoji('cross_mark')} Disagreed"}
_VERDICT_COLORS = {"agree": 0x2ECC71,   "neutral": 0x95A5A6,    "disagree": 0xE74C3C}

def _suggestion_msg_components(entry: dict, submitter_id: str, msg_id: str) -> list:
    """Build the suggestion channel message. Once `entry['answered']` is set the
    body is struck through and the vote buttons are disabled (but keep their
    counts) so nobody — admins included — can vote again."""
    votes    = entry.get("votes", {}) or {}
    a        = len(votes.get("agree", ())    or ())
    n        = len(votes.get("neutral", ())  or ())
    d        = len(votes.get("disagree", ()) or ())
    answered = bool(entry.get("answered"))
    title    = entry.get("title", "") or "Suggestion"
    text     = entry.get("text", "") or ""
    who      = entry.get("username") or entry.get("display_name") or "Unknown"
    num      = entry.get("number", "?")
    poster   = entry.get("user_id", submitter_id)

    if answered:
        struck  = "\n".join(f"~~{ln}~~" if ln.strip() else ln for ln in text.split("\n"))
        verdict = _VERDICT_LABELS.get(entry.get("verdict", ""), "Answered")
        header  = (
            f"## ~~Suggestion #{num}: {title}~~\n"
            f"-# Submitted by: <@{poster}> ({who})\n"
            f"{struck}\n\n"
            f"-------------------------------------------\n"
            f"{emoji('lock')} **Answered** — {verdict} · a reply was sent to the suggester\n"
            f"-# Final tally — {emoji('check_mark')} {a} · `➖` {n} · {emoji('cross_mark')} {d}"
        )
        accent = _VERDICT_COLORS.get(entry.get("verdict", ""), 0x95A5A6)
    else:
        header = (
            f"## Suggestion #{num}: {title}\n"
            f"-# Submitted by: <@{poster}> ({who})\n"
            f"{text}\n\n"
            f"{emoji('check_mark')} {a} | `➖` {n} | {emoji('cross_mark')} {d}"
        )
        accent = 0x3498DB

    def _btn(style: int, label: str, act: str) -> dict:
        b = {"type": 2, "style": style, "label": label,
             "custom_id": f"suggestion:{act}:{submitter_id}:{msg_id}"}
        if answered:
            b["disabled"] = True
        return b

    return [{"type": 17, "accent_color": accent, "spoiler": False, "components": [
        {"type": 10, "content": header},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            _btn(3, f"{emoji('check_mark')} Agree · {a}",    "agree"),
            _btn(2, f"`➖` Neutral · {n}",  "neutral"),
            _btn(4, f"{emoji('cross_mark')} Disagree · {d}", "disagree"),
        ]},
    ]}]

class SuggestionReplyModal(_V2Modal, title="Reply to Suggester"):
    reply_input = discord.ui.TextInput(
        label="Your reply",
        placeholder="This message will be sent to the suggester via DM.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=800,
    )

    def __init__(self, submitter_id: str, msg_id: str, vote_action: str):
        super().__init__()
        self.submitter_id = submitter_id
        self.msg_id       = msg_id
        self.vote_action  = vote_action

    async def on_submit(self, interaction: discord.Interaction):
        reply_text = self.reply_input.value.strip()
        verdict    = _VERDICT_LABELS.get(self.vote_action, "")
        color      = _VERDICT_COLORS.get(self.vote_action, 0x3498DB)
        entry      = _suggestion_store.get(self.msg_id)

        votes      = entry.get("votes", {}) if entry else {}
        agree_n    = len(votes.get("agree",    set()))
        neutral_n  = len(votes.get("neutral",  set()))
        disagree_n = len(votes.get("disagree", set()))

        # Ack the admin first (keeps us inside the 3s window).
        await send_ephemeral_v2(
            interaction,
            f"{emoji('check_mark')} **{verdict}** recorded and your reply was DM'd to <@{self.submitter_id}>. "
            f"The suggestion is now locked.",
            color,
        )

        # DM the suggester
        try:
            route    = Route("POST", "/users/@me/channels")
            dm_ch    = await bot.http.request(route, json={"recipient_id": self.submitter_id})
            dm_route = Route("POST", "/channels/{channel_id}/messages", channel_id=dm_ch["id"])
            title_line = f"### {entry['title']}\n" if entry and entry.get("title") else ""
            await bot.http.request(dm_route, json={
                "flags": V2_FLAGS,
                "components": [{"type": 17, "accent_color": color, "spoiler": False,
                    "components": [{"type": 10, "content":
                        f"### {emoji('tip')} Your Suggestion Got a Response!\n"
                        f"**Verdict:** {verdict}\n\n"
                        f"{title_line}"
                        f"{reply_text}\n\n"
                        f"-# From the dev team.\n"
                        f"-# Tally — {emoji('check_mark')} {agree_n} · `➖` {neutral_n} · {emoji('cross_mark')} {disagree_n}"
                    }]}],
                "allowed_mentions": {"parse": []},
            })
        except Exception:
            pass

        # Lock the suggestion: strike it through, disable the vote buttons.
        if entry is not None:
            entry["answered"]    = True
            entry["verdict"]     = self.vote_action
            entry["answered_by"] = str(interaction.user.id)
            channel_msg_id = entry.get("channel_msg_id")
            if channel_msg_id:
                try:
                    await bot.http.request(
                        Route("PATCH", "/channels/{channel_id}/messages/{message_id}",
                              channel_id=SUGGESTION_CHANNEL_ID, message_id=channel_msg_id),
                        json={"flags": V2_FLAGS,
                              "components": _suggestion_msg_components(entry, self.submitter_id, self.msg_id),
                              "allowed_mentions": {"parse": []}})
                except Exception as e:
                    print("Suggestion lock-patch error:", e)


@bot.tree.command(name="menu", description="Open the main hunter menu")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def menu_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    if await _maybe_onboard(interaction, user_id):
        return
    await send_v2_followup(interaction, build_menu_components(user_id, interaction.user.display_name))
    await check_everything(interaction, str(interaction.user.id))

@bot.tree.command(name="profile", description="View your hunter profile (or another player's)")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(user="User to view (leave empty for yourself)")
async def profile_cmd(interaction: discord.Interaction, user: discord.User = None):
    viewer_id = await _common_init(interaction)
    if not viewer_id: return
    target    = user or interaction.user
    target_id = str(target.id)
    if target_id != viewer_id and target_id not in data:
        # Looking someone up must not create an account for them (fake leaderboard
        # rows, analytics, ledger entries).
        await send_ephemeral_v2(interaction,
            f"{emoji('cross_mark')} That player hasn't started Idle Hunter yet.", 0xE74C3C)
        return
    init_user(target_id)
    data[target_id]["_display_name"] = target.display_name
    vid = None if target_id == viewer_id else viewer_id
    await send_v2_followup(interaction,
        build_profile_components(target_id, target.display_name, viewer_id=vid))
    await check_everything(interaction, viewer_id)

@bot.tree.command(name="hunt", description="Go hunting in your current biome!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def hunt_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id:
        return

    if await _maybe_onboard(interaction, user_id):
        return

    # ✅ SIMPLE RATE LIMIT CHECK - Just add this block
    can_hunt, remaining = await RateLimiter.can_hunt(user_id, HUNT_COOLDOWN * ev_hunt_cd_mult())
    if not can_hunt:
        await send_ephemeral_v2(
            interaction,
            f"{emoji('cooldown')} Please wait **{remaining:.1f} seconds** before hunting again!",
            0xE67E22
        )
        return
    
    # ✅ Everything below is YOUR EXISTING CODE, unchanged
    async with user_transaction(user_id):
        result = run_hunt(user_id)  # Still synchronous, no await needed

    if result.get("ok"):
        await award_tribe_xp(user_id, "hunt", catches=len(result.get("catches", [])),
                             biome=result.get("biome", ""))
        await _event_hunt_hook(user_id)
        await _guild_goal_contribute(interaction, user_id, len(result.get("catches", [])))

    if result.get("verify"):
        await send_v2_followup(interaction, build_verify_v2(user_id))
        return
    
    if result.get("tool_locked"):
        await send_ephemeral_v2(interaction,
            f"{emoji('cross_mark')} **{result['biome_name']}** needs Tier {result['req_tier']}+. "
            f"Use </shop:{COMMAND_ID.get('shop','0')}> or </equip:{COMMAND_ID.get('equip','0')}>.",
            0xE74C3C)
        return
    
    if result.get("no_ammo"):
        ran_out = result.get("ran_out", False)
        atype = result.get("ammo_type", "ammo")
        if ran_out:
            msg = f"{emoji('impact')} You ran out of {atype}! Your ammo was unequipped."
        elif result.get("owns_ammo"):
            msg = (f"{emoji('warning')} **{result['tool_name']}** needs {atype} equipped. "
                   f"You own some — load it in </equip:{COMMAND_ID.get('equip','0')}>.")
        else:
            msg = (f"{emoji('warning')} **{result['tool_name']}** needs {atype} equipped. "
                   f"Buy some in </shop:{COMMAND_ID.get('shop','0')}> → Ammo!")
        await send_ephemeral_v2(interaction, msg, 0xE67E22)
        return

    if result.get("traveling"):
        await send_ephemeral_v2(interaction,
            f"{emoji('plane')} You're in transit to **{BIOME_NAMES.get(result['dest'], result['dest'])}** "
            f"({biome_location_line(result['dest'])}) — arrives <t:{result['arrive_ts']}:R>.\n"
            f"-# You can't hunt or run the camp until you land.",
            0xE67E22)
        return

    if result.get("boss_pending"):
        await send_v2_followup(interaction,
            build_myth_encounter_components(user_id, result["creature"]))
        return

    if result.get("tracking_pending") or result.get("tracking_encounter") or tracking_active(user_id):
        await send_v2_followup(interaction, build_tracking_components(user_id))
        return

    if result.get("animal_fight_pending") or animal_fight_active(user_id):
        await send_v2_followup(interaction, build_animal_fight_components(user_id))
        return

    if not result["ok"]:
        remaining = result.get("remaining", 3)
        await send_ephemeral_v2(interaction,
            f"{emoji('cooldown')} Hunt again <t:{result.get('cooldown_ts', int(time.time()+remaining))}:R>.",
            0xE67E22)
        return
    data[user_id]["_display_name"] = interaction.user.display_name
    await send_v2_followup(interaction, build_hunt_components(user_id, result))
    await maybe_send_hunt_tip(interaction, result)
    await _hunters_path_notify(interaction, user_id, result.get("hunters_path_result"))
    await check_everything(interaction, user_id)

@bot.tree.command(name="progression", description="View your achievements, badges, and titles")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def achievements_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    _ach_page[user_id] = 0
    await send_v2_followup(interaction, build_progression_hub(user_id))

@bot.tree.command(name="settings", description="Manage your preferences, notifications and hunter's guide")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def settings_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_settings_components(user_id))

@bot.tree.command(name="events", description="View ongoing global events")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def events_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_events_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="shop", description="Buy boosts, tools and ammo")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def shop_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_shop_components(user_id, "boosts"))
    await check_everything(interaction, user_id)

@bot.tree.command(name="world", description="See what's happening across the world right now — and travel between biomes")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def world_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    if await _maybe_onboard(interaction, user_id): return
    goal_line = await _world_goal_line(interaction)
    await send_v2_followup(interaction, build_world_components(user_id, goal_line))
    await check_everything(interaction, user_id)

@bot.tree.command(name="guide", description="Your Collection — species, Mythicals, trophies & world completion")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def guide_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_collection_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="expedition", description="Your tribe's expedition — vote a route, fill the bar together")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def expedition_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_expedition_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="servergoal", description="This server's weekly community hunting goal")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def servergoal_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    if interaction.guild is None:
        await send_ephemeral_v2(interaction, "-# Run this in a server to see its goal.", 0xE67E22)
        return
    if not FEATURE_SERVER_GOALS:
        await send_ephemeral_v2(interaction, "-# Server goals aren't active right now.", 0xE67E22)
        return
    st = await guild_goal_state(interaction.guild)
    line = build_guild_goal_line(st) or "-# No goal yet — hunt to kick it off."
    try:
        me = await backend.guild_goal_contributors(str(interaction.guild.id),
                                                   _week_tag(), 1)
        mine = dict(me).get(str(user_id), 0)
    except Exception:
        mine = 0
    body = (f"### {emoji('earth')} {interaction.guild.name} — Weekly Goal\n{line}\n\n"
            f"-# Your catches this week: **{mine}**")
    await send_v2_followup(interaction, [{"type": 17, "accent_color": _accent(user_id),
        "spoiler": False, "components": [
            {"type": 10, "content": body},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 3, "label": "Hunt", "custom_id": f"hunt:again:{user_id}"},
                {"type": 2, "style": 2, "label": "◀ Menu", "custom_id": f"nav:menu:{user_id}"}]},
        ]}])

@bot.tree.command(name="color", description="Change your color for containers")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def color_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_color_panel_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="equip", description="Equip your tools, ammo and vehicles")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def equip_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_equip_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="idle", description="Manage your passive Hunting Camp")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def idle_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    if is_traveling(user_id):
        t = data[user_id]["travel"]
        await send_ephemeral_v2(interaction,
            f"{emoji('plane')} You're in transit to **{BIOME_NAMES.get(t['dest'], t['dest'])}** — "
            f"arrives <t:{int(t['arrive_ts'])}:R>. The Hunting Camp is on hold until you land.",
            0xE67E22)
        return
    async with user_transaction(user_id):
        idle_tick(user_id)
    await send_v2_followup(interaction, build_idle_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="daily", description="Claim your daily reward")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def daily_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_daily_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="prestige", description="Reset for a permanent boost multiplier")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def prestige_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_prestige_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="mail", description="Check your mailbox")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def mail_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_mail_components(user_id, "tribe"))

quests_group = app_commands.Group(
    name="quests",
    description="View and claim your daily and weekly quests",
    allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
)

@quests_group.command(name="daily", description="View and claim your daily quests")
async def quests_daily_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id:
        return
    init_user(user_id)
    _quest_page[user_id] = 0
    await send_v2_followup(interaction, build_quests_components(user_id, 0))

@quests_group.command(name="weekly", description="View and claim your weekly quest")
async def quests_weekly_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id:
        return
    init_user(user_id)
    await send_v2_followup(interaction, build_weekly_quests_components(user_id))

bot.tree.add_command(quests_group)

# ─────────────────────────────────────────────
# /tribe  — command group
# ─────────────────────────────────────────────

async def _tribe_menu_send(interaction: discord.Interaction, user_id: str):
    """Render the tribe panel (or the 'no tribe' prompt) on a deferred interaction."""
    tribe_nm  = data[user_id].get("tribe")
    tribe_inv = data[user_id].get("tribe_inv")
    if not tribe_nm and tribe_inv and tribe_inv in tribe_data:
        await send_ephemeral_v2(interaction,
            f"You have a pending invite to **{tribe_inv}**! "
            f"Use </mail:{COMMAND_ID.get('mail','0')}> to accept.", 0xF1C40F)
        return
    if not tribe_nm or tribe_nm not in tribe_data:
        await send_v2_followup(interaction, [{"type": 17, "accent_color": _accent(user_id),
            "spoiler": False, "components": [
                {"type": 10, "content":
                    f"### {TRIBE_EMOJIS['tribe']} No Tribe\n"
                    "You are not in a tribe! Create one with `/tribe create` or wait for an invite."},
                {"type": 1, "components": [
                    {"type": 2, "style": 1, "label": "Create Tribe", "emoji": emoji_partial('tribe'),
                     "custom_id": f"tribe_create:{user_id}"},
                ]},
            ]}])
        return
    await send_v2_followup(interaction, build_tribe_components(user_id, tribe_nm, "main"))

def _tribe_info_text(tribe_name: str) -> str:
    td = tribe_data[tribe_name]
    _ensure_tribe_fields(td)
    roster  = [(uid, _TRIBE_ROLE_ICON.get(role, "`🧑`")) for uid, role in tribe_roster(tribe_name)]
    total   = len(roster)
    mlist   = "\n".join(
        f"{ic} `{get_username(uid)}`{featured_badge_suffix(uid)} — Lv. {data.get(uid, {}).get('level', '?')}"
        for uid, ic in roster[:25]
    )
    desc = f"\n`📝` *{td['description']}*\n" if td.get("description") else ""
    _tn = tribe_xp_to_next(td['level'])
    return (
        f"### {TRIBE_EMOJIS['tribe']} {tribe_name}{desc}\n"
        f"{USER_EMOJIS['levels']} **Level {td['level']}**"
        + (f" · {USER_EMOJIS['xp']} {td['xp']:,}/{_tn:,} XP\n" if td['level'] < TRIBE_LEVEL_CAP else " · **MAX**\n")
        + f"{TRIBE_EMOJIS['members']} **{total}/{td['max_members']}** members\n"
        f"{TRIBE_EMOJIS['luck_boost']} **{td['luck_boost']}%** · "
        f"{TRIBE_EMOJIS['sell_boost']} **{td['sell_price_boost']}%** · "
        f"{TRIBE_EMOJIS['xp_boost']} **{td['xp_boost']}%**\n\n"
        f"**Members:**\n{mlist}"
    )

async def _tribe_do_invite(inviter_id: str, tribe_name: str,
                           target_id: str, inviter_name: str) -> tuple[bool, str]:
    """Shared invite flow used by both /tribe invite and the panel's invite modal."""
    inviter_id, target_id = str(inviter_id), str(target_id)
    if not target_id.isdigit():
        return False, f"{emoji('cross_mark')} Invalid user ID."
    if target_id == inviter_id:
        return False, f"{emoji('cross_mark')} You can't invite yourself."
    if tribe_name not in tribe_data:
        return False, f"{emoji('cross_mark')} Tribe not found."
    td = tribe_data[tribe_name]
    if td["roles"]["leader"] != inviter_id and inviter_id not in td["roles"].get("officer", []):
        return False, f"{emoji('cross_mark')} Only the leader or officers can invite."
    if target_id not in data:
        return False, f"{emoji('cross_mark')} That player hasn't started Idle Hunter yet."
    _ensure_tribe_fields(td)
    if _tribe_is_banned(td, target_id):
        return False, f"{emoji('cross_mark')} That player is banned from your tribe. Unban them first."
    if data[target_id].get("tribe"):
        return False, f"{emoji('cross_mark')} That player is already in a tribe."
    if data[target_id].get("tribe_inv"):
        return False, f"{emoji('cross_mark')} That player already has a pending invite."
    if len(tribe_roster(tribe_name)) >= td["max_members"]:
        return False, f"{emoji('cross_mark')} Your tribe is full."
    _ok, _wait = _tribe_rejoin_ok(target_id)
    if not _ok:
        return False, f"{emoji('cross_mark')} That player left a tribe recently — invite them again <t:{int(time.time()+_wait)}:R>."
    td.setdefault("invites", []).append(target_id)
    async with user_tribe_transaction(inviter_id, tribe_name):
        data[target_id]["tribe_inv"]      = tribe_name
        data[target_id]["tribe_inv_read"] = False
    bot.loop.create_task(_dm_user_v2(
        target_id,
        [{"type": 17, "accent_color": _accent(inviter_id), "spoiler": False,
          "components": [{"type": 10, "content":
              f"### {TRIBE_EMOJIS['invite']} Tribe Invite\n"
              f"You've been invited to **{tribe_name}** by **{inviter_name}**!\n\n"
              f"-# Use </mail:{COMMAND_ID.get('mail','0')}> to accept or decline."
          }]}],
        "Tribe invite",
    ))
    return True, f"{emoji('check_mark')} Invite sent to <@{target_id}>."

tribe_group = app_commands.Group(
    name="tribe",
    description="Create, view and manage your tribe",
    allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
)

@tribe_group.command(name="menu", description="View your tribe and its options")
async def tribe_menu_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await _tribe_menu_send(interaction, user_id)

@tribe_group.command(name="create", description="Create a new tribe")
@app_commands.describe(name="Tribe name (2–32 characters)", description="Optional description")
async def tribe_create_cmd(interaction: discord.Interaction, name: str, description: str = ""):
    user_id = await _common_init(interaction)
    if not user_id: return
    if data[user_id].get("tribe"):
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You're already in a tribe.", 0xE74C3C)
        return
    if data[user_id].get("tribe_inv"):
        await send_ephemeral_v2(interaction,
            f"{emoji('cross_mark')} Resolve your pending invite first — </mail:{COMMAND_ID.get('mail','0')}>.", 0xF1C40F)
        return
    name = name.strip()
    if not 2 <= len(name) <= 32:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Tribe name must be 2–32 characters.", 0xE74C3C)
        return
    if name in tribe_data:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} That tribe name is already taken.", 0xE74C3C)
        return
    init_tribe(name, user_id)
    tribe_data[name]["description"] = description.strip()[:200] or None
    await send_v2_followup(interaction, build_tribe_components(user_id, name, "main"))

@tribe_group.command(name="invite", description="Invite a player to your tribe")
@app_commands.describe(user="The player to invite")
async def tribe_invite_cmd(interaction: discord.Interaction, user: discord.User):
    inviter_id = await _common_init(interaction)
    if not inviter_id: return
    tribe_nm = data[inviter_id].get("tribe")
    if not tribe_nm or tribe_nm not in tribe_data:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You're not in a tribe.", 0xE74C3C)
        return
    ok, msg = await _tribe_do_invite(inviter_id, tribe_nm, str(user.id), interaction.user.display_name)
    await send_ephemeral_v2(interaction, msg, 0x2ECC71 if ok else 0xE74C3C)

@tribe_group.command(name="leave", description="Leave your current tribe")
@app_commands.describe(new_leader="Who becomes leader — required if you lead a tribe with other members")
async def tribe_leave_cmd(interaction: discord.Interaction, new_leader: discord.User = None):
    user_id = await _common_init(interaction)
    if not user_id: return
    tribe_nm = data[user_id].get("tribe")
    if not tribe_nm or tribe_nm not in tribe_data:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You're not in a tribe.", 0xE74C3C)
        return
    td      = tribe_data[tribe_nm]
    _ensure_tribe_fields(td)
    total_m = len(tribe_roster(tribe_nm))
    is_ldr  = td["roles"]["leader"] == user_id

    if is_ldr and total_m > 1:
        if new_leader is None:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} You lead this tribe. Re-run `/tribe leave` with `new_leader` set to an existing "
                "member, or hand it off from `/tribe menu` → Actions.", 0xE74C3C)
            return
        nl = str(new_leader.id)
        if nl not in (td["roles"]["officer"] + td["roles"]["members"] + td["roles"].get("recruits", [])):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} That player isn't in your tribe.", 0xE74C3C)
            return
        async with user_tribe_transaction(user_id, tribe_nm):
            _tribe_remove_member(td, nl, note="was promoted to leader in")
            _tribe_remove_member(td, user_id, note="stepped down and left")
            td["roles"]["leader"]  = nl
            td["member_since"][nl] = int(time.time())
            data[user_id]["tribe"] = None
            data[user_id]["tribe_left_ts"] = time.time()
        await send_ephemeral_v2(interaction,
            f"{emoji('check_mark')} You left **{tribe_nm}**. <@{nl}> is now the leader.", 0x2ECC71)
        return

    async with user_tribe_transaction(user_id, tribe_nm):
        if is_ldr and total_m == 1:
            tribe_data.pop(tribe_nm, None)
        else:
            _tribe_remove_member(td, user_id, note="left")
        data[user_id]["tribe"] = None
        data[user_id]["tribe_left_ts"] = time.time()
    await send_ephemeral_v2(interaction, f"{emoji('check_mark')} You left **{tribe_nm}**.", 0x2ECC71)

@tribe_group.command(name="info", description="View info about a tribe")
@app_commands.describe(name="Tribe name (defaults to your own tribe)")
async def tribe_info_cmd(interaction: discord.Interaction, name: str = None):
    user_id = await _common_init(interaction)
    if not user_id: return
    target = name or data[user_id].get("tribe")
    if not target or target not in tribe_data:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Tribe not found.", 0xE74C3C)
        return
    await send_v2_followup(interaction, [{"type": 17, "accent_color": _accent(user_id),
        "spoiler": False, "components": [{"type": 10, "content": _tribe_info_text(target)}]}])

bot.tree.add_command(tribe_group)

@bot.tree.command(name="leaderboard", description="View hunter and tribe leaderboards")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def leaderboard_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    _lb_state[user_id] = {
        "mode": "hunter", "scope": "global",
        "stat": "Level", "page": 0, "period": "all",
        "guild": interaction.guild,
    }
    await send_v2_followup(interaction,
        build_leaderboard_v2_components(user_id, interaction.guild, "hunter", "global", "Level", 0, "all"))
    await check_everything(interaction, user_id)

@bot.tree.command(name="record", description="View a hunter's catch record book")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(user="User to view (leave empty for yourself)")
async def record_cmd(interaction: discord.Interaction, user: discord.User = None):
    viewer_id = await _common_init(interaction)
    if not viewer_id: return
    target    = user or interaction.user
    target_id = str(target.id)
    if target_id != viewer_id and target_id not in data:
        # Looking someone up must not create an account for them (fake leaderboard
        # rows, analytics, ledger entries).
        await send_ephemeral_v2(interaction,
            f"{emoji('cross_mark')} That player hasn't started Idle Hunter yet.", 0xE74C3C)
        return
    init_user(target_id)
    data[target_id]["_display_name"] = target.display_name
    _record_state[viewer_id] = {"target_id": target_id, "biome_idx": 0}
    await send_v2_followup(interaction,
        build_record_standalone_v2_components(viewer_id, target_id, 0))
    await check_everything(interaction, viewer_id)

@bot.tree.command(name="log", description="View your recent hunt log")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def log_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    _log_state[user_id] = 0
    await send_v2_followup(interaction, build_log_standalone_v2_components(user_id, 0))
    await check_everything(interaction, user_id)

# Gem gifts are the alt-farming exit: a fresh account collects ~395 gems of
# starter bonuses (~$4 at the 100 gems ≈ $1 rate) and could just /gift them out.
# Gate gem gifting on account maturity and cap what one player can send per day.
GIFT_GEMS_MIN_LEVEL    = 10
GIFT_GEMS_MIN_AGE_DAYS = 3
GIFT_GEMS_DAILY_CAP    = 500

def _gem_gift_block(sender_id: str, amount: int) -> str | None:
    """Reason a gem gift can't go out right now, or None if it's allowed."""
    d = data[sender_id]
    if d.get("level", 1) < GIFT_GEMS_MIN_LEVEL:
        return f"You need to be **level {GIFT_GEMS_MIN_LEVEL}** to gift gems."
    try:
        joined = datetime.strptime(d.get("joined_date", ""), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - joined).days
    except (ValueError, TypeError):
        age_days = GIFT_GEMS_MIN_AGE_DAYS   # unknown join date = legacy account
    if age_days < GIFT_GEMS_MIN_AGE_DAYS:
        return f"Your account must be **{GIFT_GEMS_MIN_AGE_DAYS} days old** to gift gems."
    gd = d.get("gem_gift_day") or {}
    sent = gd.get("sent", 0) if gd.get("tag") == today_utc() else 0
    if sent + amount > GIFT_GEMS_DAILY_CAP:
        left = max(0, GIFT_GEMS_DAILY_CAP - sent)
        return f"You can gift at most **{GIFT_GEMS_DAILY_CAP:,}** gems per day ({left:,} left today)."
    return None

@bot.tree.command(name="gift", description="Gift money or gems to another player")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(
    user="Who to gift",
    format="money or gems",
    amount="Amount (e.g. 1000, 2.5M, 1B)",
    sent_message="Message to include with the gift",
)
@app_commands.choices(format=[
    app_commands.Choice(name="Money (◈)", value="money"),
    app_commands.Choice(name="Gems (`💎`)", value="gems"),
])
async def gift_cmd(interaction: discord.Interaction,
                   user: discord.User, format: str,
                   amount: str, sent_message: str = "No message."):
    sender_id = await _common_init(interaction)
    if not sender_id: return
    parsed = parse_amount(amount)
    if parsed is None or parsed <= 0:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Invalid amount.", 0xE74C3C)
        return
    receiver_id = str(user.id)
    if receiver_id == sender_id:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You can't gift yourself.", 0xE74C3C)
        return
    # Only existing players can receive gifts — init_user() here used to mint a
    # full account (leaderboard row, analytics, starter gems) for any @mention.
    if receiver_id not in data:
        await send_ephemeral_v2(interaction,
            f"{emoji('cross_mark')} That player hasn't started Idle Hunter yet.", 0xE74C3C)
        return
    icon = "◈" if format == "money" else emoji("gem")
    if data[sender_id][format] < parsed:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Not enough {icon}!", 0xE74C3C)
        return
    if format == "gems":
        _block = _gem_gift_block(sender_id, parsed)
        if _block:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} {_block}", 0xE74C3C)
            return
    await send_v2_followup(interaction,
        build_gift_confirm_components(sender_id, user, format, parsed, sent_message))

@bot.tree.command(name="verify", description="Verify you're not an autoclicker!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(code="Your 4-character verification code")
async def verify_cmd(interaction: discord.Interaction, code: str):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    init_user(user_id)
    v = data[user_id]["verify"]
    if not v["needed"]:
        await send_ephemeral_v2(interaction, f"{emoji('check_mark')} You don't need to verify right now!", 0x2ECC71)
        return
    if code.upper() == v["code"].upper():
        async with user_transaction(user_id):
            v["needed"] = False
            v["time"]   = 250
            v["code"]   = generate_verify_code()
        await send_ephemeral_v2(interaction, f"### {emoji('check_mark')} Verified!\nHappy hunting!", 0x2ECC71)
    else:
        await send_ephemeral_v2(interaction, f"### {emoji('cross_mark')} Wrong Code\nTry again.", 0xE74C3C)

@bot.tree.command(name="invite", description="Invite Idle Hunter to your server!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def invite_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    init_user(user_id)
    url1 = invite_url()
    url2 = "https://discord.gg/X9JzdxeS8p"
    await interaction.response.defer(ephemeral=True)
    route = Route("POST", "/webhooks/{application_id}/{token}",
                  application_id=interaction.application_id,
                  token=interaction.token)
    await bot.http.request(route, json={
        "flags": V2_FLAGS,
        "components": [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
            "components": [{"type": 10, "content":
                f"### {emoji('link')} Invite Idle Hunter\n"
                f"[Click here to invite the bot!]({url1})\n"
                f"[Join the support server]({url2})"
            }]}],
        "allowed_mentions": {"parse": []},
    })

@bot.tree.command(name="refer", description="Invite a friend — you both earn when they start playing")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(code="A friend's referral code (leave empty to see your own)")
async def refer_cmd(interaction: discord.Interaction, code: str = None):
    user_id = await _common_init(interaction)
    if not user_id: return
    if not FEATURE_REFERRALS:
        await send_ephemeral_v2(interaction, "-# Referrals aren't active right now.", 0xE67E22)
        return
    if code:
        ok, msg = await _referral_bind(user_id, code)
        await send_ephemeral_v2(interaction, (f"### {emoji('check_mark')} Referral set\n" if ok else f"### {emoji('cross_mark')} ") + msg,
                                0x2ECC71 if ok else 0xE74C3C)
        return
    my_code = await _referral_get_code(user_id)
    try:
        stats = await backend.referral_stats(user_id)
    except Exception:
        stats = {"invited": 0, "qualified": 0}
    await send_v2_followup(interaction, build_refer_components(user_id, my_code, stats))

@bot.tree.command(name="id", description="Get a user's Discord ID")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(user="User to look up")
async def id_cmd(interaction: discord.Interaction, user: discord.User = None):
    viewer_id = str(interaction.user.id)
    init_user(viewer_id)
    target = user or interaction.user
    await interaction.response.defer(ephemeral=True)
    route = Route("POST", "/webhooks/{application_id}/{token}",
                  application_id=interaction.application_id,
                  token=interaction.token)
    await bot.http.request(route, json={
        "flags": V2_FLAGS | 64,
        "components": [{"type": 17, "accent_color": _accent(viewer_id), "spoiler": False,
            "components": [{"type": 10, "content":
                f"### {target.name}'s ID\n`{target.id}`\n"
                f"-# Use this to invite players to your tribe."
            }]}],
        "allowed_mentions": {"parse": []},
    })

# ─────────────────────────────────────────────
# /info  — encyclopedia: biomes · tools · ammo · animals
# ─────────────────────────────────────────────

_INFO_CATEGORIES = ("biomes", "tools", "ammo", "animals", "myths", "badges")
_INFO_CAT_LABELS = {"biomes": "Biomes", "tools": "Tools", "ammo": "Ammo",
                    "animals": "Animals", "myths": "Mythical Creatures", "badges": "Badges"}

# game_data.py has no per-biome flavour text of its own — keep short blurbs here.
_INFO_BIOME_BLURB = {
    "village":            "Rain-soaked evergreen country on the edge of the Pacific Northwest.",
    "forest":             "The hedgerows, moors and old woodland of the British Isles.",
    "woods":              "Boreal Scandinavia — elk, bear and wolverine under tall pines.",
    "small_desert":       "The Nile's edge and the open Sahara: scorpions, vipers, jackals.",
    "sunken_coast":       "The cold North Atlantic off Cape Ann — cod, seals, whales and worse.",
    "tundra":             "The treeless alpine summits of the Transylvanian Alps — the cold roof above vampire country.",
    "jungle":             "The steaming forests of Southeast Asia and the hills of Japan.",
    "swamp":              "The billabongs and flooded backwaters of southeastern Australia.",
    "volcanic_highlands": "The volcanic highlands of Anatolia, in Turkey.",
    "cursed_ruins":       "The ruins and mountains of Ancient Greece.",
    "rainbow":            "The reefs and rainforest of the Caribbean.",
    "abyssal_depths":     "The lightless deep of the Mediterranean Sea.",
    "celestial_peaks":    "The roof of the world — the highest ridges of the Himalayas.",
}

# animal name -> [biome_key, ...]  (a few animals live in more than one biome)
_ANIMAL_BIOMES: dict[str, list[str]] = {}
for _bk, _alist in BIOME_ANIMALS.items():
    for _a in _alist:
        _ANIMAL_BIOMES.setdefault(_a, []).append(_bk)


def _emoji_cdn_url(emoji_key_or_str: str, size: int = 256) -> str | None:
    """CDN image URL for a custom `<:name:id>` emoji (or registry key), else None."""
    p = emoji_partial(emoji_key_or_str or "")
    if not p.get("id"):
        return None
    ext = "gif" if p.get("animated") else "png"
    return f"https://cdn.discordapp.com/emojis/{p['id']}.{ext}?size={size}"


def _info_price(price: int, currency: str) -> str:
    if currency == "gems":
        return f"{emoji('gem')} {price:,}"
    return f"◈ {price:,}"


def _info_entries(category: str) -> list[tuple[str, str]]:
    """(key, label) pairs for every entry in a category."""
    if category == "biomes":
        return [(k, BIOME_NAMES[k]) for k, _ in BIOME_LEVELS]
    if category == "tools":
        return [(n, f"{n} (T{TOOLS[n]['tier']})") for n, _ in get_all_tools_sorted()]
    if category == "ammo":
        return [(n, n) for n in AMMO]
    if category == "animals":
        return [(n, n) for n in sorted(ANIMAL_DATA)]
    if category == "myths":
        return [(n, n) for n in sorted(MYTHIC_CREATURES)]
    if category == "badges":
        return (sorted(((k, b["label"]) for k, b in BADGES.items()), key=lambda p: p[1])
                + [(k, f"{b['label']} (special)") for k, b in SPECIAL_BADGES.items()])
    return []


def _info_groups(category: str) -> list[tuple[str, str]]:
    """(group_key, label) sub-filters — ammo, animals and myths need one."""
    if category == "ammo":
        return [(t, AMMO_TYPE_LABELS[t]) for t in AMMO_TYPE_LABELS]
    if category in ("animals", "myths"):
        return [(k, BIOME_NAMES[k]) for k, _ in BIOME_LEVELS]
    return []


def _info_group_of(category: str, key: str) -> str | None:
    if category == "ammo":
        return AMMO.get(key, {}).get("ammo_type")
    if category == "animals":
        bs = _ANIMAL_BIOMES.get(key)
        return bs[0] if bs else None
    if category == "myths":
        return MYTHIC_CREATURES.get(key, {}).get("biome")
    return None


def _info_entries_in_group(category: str, group: str | None) -> list[tuple[str, str]]:
    if category == "ammo":
        return [(n, n) for n, a in AMMO.items() if a["ammo_type"] == group]
    if category == "animals":
        return [(n, n) for n in BIOME_ANIMALS.get(group, [])]
    if category == "myths":
        return [(n, n) for n in BIOME_MYTHS.get(group, [])]
    return _info_entries(category)


def _info_resolve(category: str, raw: str) -> str | None:
    """Turn a typed / picked value into a real entry key."""
    raw_l = (raw or "").strip().lower()
    if not raw_l:
        return None
    ents = _info_entries(category)
    for key, label in ents:
        if raw_l in (key.lower(), label.lower()):
            return key
    for key, label in ents:
        if key.lower().startswith(raw_l) or label.lower().startswith(raw_l):
            return key
    return None


def _info_render_biome(key: str):
    name    = BIOME_NAMES[key]
    em      = BIOME_EMOJIS[key]
    lvl     = dict(BIOME_LEVELS)[key]
    tier    = BIOME_TOOL_TIER.get(key, 1)
    at_tier = [n for n, t in TOOLS.items() if t["tier"] == tier]
    animals = BIOME_ANIMALS[key]
    vals    = [ANIMAL_DATA[a]["value"] for a in animals]
    xps     = [ANIMAL_DATA[a]["xp"] for a in animals]
    rar: list[str] = []
    for a in animals:
        r = ANIMAL_DATA[a]["rarity"]
        if r not in rar:
            rar.append(r)
    reg   = biome_region(key)
    myths = BIOME_MYTHS.get(key, [])
    lines = [
        f"### {USER_EMOJIS['biome']} Hunting Information",
        f"-# {emoji('location_pin')} **Location:** {reg['region']}, {reg['continent']}",
        f"-# **Unlocks at:** Level {lvl:,}",
        f"-# **Tool needed:** Tier {tier}+" + (f" (e.g. {at_tier[0]})" if at_tier else ""),
        f"-# **Species:** {len(animals)}",
        f"-# **Value range:** ◈ {min(vals):,} – ◈ {max(vals):,}",
        f"-# **XP range:** {min(xps):,} – {max(xps):,}",
        f"-# **Rarities:** " + " ".join(RARITY_ICONS.get(r, r.title()) for r in rar),
    ]
    if myths:
        lines.append(f"-# **{RARITY_ICONS.get('mythic','')} Mythical creatures:** "
                     + ", ".join(myths))
    lines += ["", f"### {emoji('animal_fallback')} Animals here"]
    for a in animals:
        ad = ANIMAL_DATA[a]
        lines.append(f"-# {RARITY_ICONS.get(ad['rarity'], '')} **{a}** — "
                     f"◈ {ad['value']:,} · {ad['xp']:,} XP")
    map_img = reg.get("map_image") or ""
    thumb   = map_img if map_img.startswith("http") else _emoji_cdn_url(em)
    return f"# {em} {name}", f"-# {_INFO_BIOME_BLURB.get(key, '')}", "\n".join(lines), thumb


def _info_render_tool(key: str):
    t          = TOOLS[key]
    at         = t.get("ammo_type")
    unlockable = [BIOME_NAMES[b] for b, _ in BIOME_LEVELS
                  if BIOME_TOOL_TIER.get(b, 1) <= t["tier"]]
    lines = [
        f"### {emoji('bow')} Hunting Information",
        f"-# **Tier:** {t['tier']}",
        f"-# **Price:** {_info_price(t['price'], t['currency'])}",
        f"-# **Luck boost:** +{t['boost_luck']}",
        f"-# **XP boost:** +{t['boost_xp']}",
        f"-# **Catches per hunt:** {t['multi_catch']}",
        f"-# **Ammo:** " + (AMMO_TYPE_LABELS.get(at, at) if at else "None needed"),
        f"-# **Unlocks biomes up to:** " +
            (f"{unlockable[-1]} ({len(unlockable)} total)" if unlockable else "—"),
    ]
    if at:
        lines.append("-# **Compatible ammo:** " +
                     ", ".join(n for n, a in AMMO.items() if a["ammo_type"] == at))
    return (f"# {tool_emoji(key)} {key}", f"-# {t['description']}", "\n".join(lines),
            _emoji_cdn_url(tool_emoji(key)) or _emoji_cdn_url("bow"))


def _info_render_ammo(key: str):
    a     = AMMO[key]
    at    = a["ammo_type"]
    tools = AMMO_TYPE_TOOLS.get(at, [])
    lines = [
        f"### {emoji('equipment')} Hunting Information",
        f"-# **Type:** {AMMO_TYPE_LABELS.get(at, at)}",
        f"-# **Price:** {_info_price(a['price'], a['currency'])} per round",
        f"-# **Luck boost:** +{a.get('boost_luck', 0)}%",
        f"-# **Sell boost:** +{a.get('boost_sell', 0)}%",
        f"-# **XP boost:** +{a.get('boost_xp', 0)}%",
        f"-# **Used by:** " + (", ".join(tools) if tools else "—"),
        f"-# **Max stack:** {AMMO_MAX_STACK:,}",
    ]
    return (f"# {ammo_emoji(key)} {key}", f"-# {a['description']}", "\n".join(lines),
            _emoji_cdn_url(ammo_emoji(key)) or _emoji_cdn_url("equipment"))


def _info_render_animal(key: str):
    ad     = ANIMAL_DATA[key]
    r      = ad["rarity"]
    biomes = _ANIMAL_BIOMES.get(key, [])
    b_txt  = ", ".join(BIOME_NAMES[b] for b in biomes) or "—"
    unlock = min((dict(BIOME_LEVELS)[b] for b in biomes), default=1)
    a_em   = animal_emoji(key)
    lines = [
        f"### {emoji('animal_fallback')} Hunting Information",
        f"-# **Rarity:** {RARITY_ICONS.get(r, '')} {r.title()}",
        f"-# **Found in:** {b_txt}",
        f"-# **Unlocks at:** Level {unlock:,}",
        f"-# **Base value:** ◈ {ad['value']:,}",
        f"-# **Base XP:** {ad['xp']:,}",
        f"-# **Perfect Catch:** ◈ {ad['value'] * 3:,} · {ad['xp'] * 2:,} XP",
        f"-# Perfect Catches fire on ~5% of hits — every point of Luck raises that.",
    ]
    header = f"# {RARITY_ICONS.get(r, '')} {a_em} {key}".replace("  ", " ").strip()
    return header, f"-# {r.title()} animal", "\n".join(lines), _emoji_cdn_url(RARITY_ICONS.get(r))


def _info_render_myth(key: str):
    c     = MYTHIC_CREATURES[key]
    ico   = creature_emoji(key)
    biome = c["biome"]
    reg   = biome_region(biome)
    lines = [
        f"### {emoji('book')} Vital Statistics",
        f"-# **Also known as:** {c['aka']}",
        f"-# **Height:** {c['height']}",
        f"-# **Description:** {c['description']}",
        f"-# **Call:** {c['call']}",
        f"-# **Diet:** {c['diet']}",
        f"-# **Behavior:** {c['behavior']}",
        "",
        f"### {emoji('world_map')} Hunting Information",
        f"-# **Region:** {BIOME_NAMES.get(biome, biome)} — {emoji('location_pin')} {reg['region']}, {reg['continent']}",
        f"-# **Encounter:** ~{MYTH_ENCOUNTER_BASE*100:.1f}%–{MYTH_ENCOUNTER_MAX*100:.0f}% per hunt there "
        f"ambiently (scales with luck); a Global Sighting there makes it guaranteed-huntable "
        f"for {SIGHTING_ENCOUNTER_WINDOW_MIN // 60}h · **Rarity:** {RARITY_ICONS.get('mythic','')} Mythic",
        f"-# **First-kill bounty:** ◈ {MYTH_FIRST_KILL_BOUNTY:,} · {emoji('gem')} {MYTH_FIRST_KILL_GEMS:,} · {int(c['xp']*MYTH_XP_MULT):,} XP\n"
        f"-# **Repeat-kill bounty:** ◈ {MYTH_REPEAT_BOUNTY_RANGE[0]:,}–{MYTH_REPEAT_BOUNTY_RANGE[1]:,} · "
        f"{emoji('gem')} {MYTH_REPEAT_GEMS_RANGE[0]}–{MYTH_REPEAT_GEMS_RANGE[1]} · {int(c['xp']*MYTH_XP_MULT):,} XP",
        f"-# **Drops:** {c['drop']} (trophy, worth ◈ {c['drop_value']:,})",
        f"-# **The fight:** turn-based brawl — you at {FIGHT_PLAYER_HP} HP vs it at "
        f"{FIGHT_MONSTER_HP_BASE + BIOME_TOOL_TIER.get(biome,1)*FIGHT_MONSTER_HP_TIER} HP. "
        f"Punch, Kick (big, risky), Defend, Shoot (**{FIGHT_SHOOT_AMMO} rounds** a volley), Taunt, or Flee. "
        f"Lose and it costs at most **{int(MYTH_DEATH_LOSS_CASH*100)}%** of your cash.",
    ]
    return (f"# {ico} {key}", f"-# {c['blurb']}", "\n".join(lines),
            _emoji_cdn_url(creature_emoji(key)))


def _info_render_badge(key: str):
    if key in SPECIAL_BADGES:
        sb  = SPECIAL_BADGES[key]
        ico = badge_emoji(key, 1) or "★"
        lines = [
            "### `★` Special Badge",
            "-# **Tracks:** nothing — this one is handed out by the developers.",
            f"-# **Tag:** `[{sb['abbr']}]` (shown on your profile once granted)",
            "",
            "-# Can't be earned by playing. Grateful recipients only.",
        ]
        return (f"# {ico} {sb['label']}", f"-# {sb['blurb']}", "\n".join(lines),
                _emoji_cdn_url(badge_emoji(key, 1)))
    b       = BADGES[key]
    gold_e  = badge_emoji(key, 1) or "🥇"
    plat_e  = badge_emoji(key, 2) or "🏆"
    lines = [
        f"### {emoji('military_medal')} Badge Info",
        f"-# **Tracks:** {b.get('tracks', b['stat'])}",
        f"-# {gold_e} **Gold** at {b['gold']:,}",
    ]
    if b.get("plat"):
        lines.append(f"-# {plat_e} **Platinum** at {b['plat']:,}")
    else:
        lines.append(f"-# {emoji('trophy')} No Platinum tier — Gold is the top of this one.")
    lines += [
        f"-# **Tag:** `[{b['abbr']}]` (shown on your profile once earned)",
        "",
        f"-# Earn badges just by playing — check progress in `/progression` → {emoji('military_medal')} Badges.",
    ]
    return (f"# {gold_e} {b['label']}", f"-# {b['blurb']}", "\n".join(lines),
            _emoji_cdn_url(badge_emoji(key, 1)))


def _info_render(category: str, key: str):
    if category == "biomes":
        return _info_render_biome(key)
    if category == "tools":
        return _info_render_tool(key)
    if category == "ammo":
        return _info_render_ammo(key)
    if category == "animals":
        return _info_render_animal(key)
    if category == "myths":
        return _info_render_myth(key)
    if category == "badges":
        return _info_render_badge(key)
    return "# ?", "", "Nothing to show.", None


def build_info_components(user_id: str) -> list:
    st  = _info_state.get(user_id) or {}
    cat = st.get("category") if st.get("category") in _INFO_CATEGORIES else "biomes"
    key = st.get("name")

    entries = _info_entries(cat)
    keyset  = {k for k, _ in entries}
    if key not in keyset:
        key = entries[0][0]
    grp = st.get("group") or _info_group_of(cat, key)
    _info_state[user_id] = {"category": cat, "group": grp, "name": key}

    header, blurb, body, img = _info_render(cat, key)
    top_text = f"{header}\n{blurb}" if blurb else header
    if img:
        top = {"type": 9,
               "components": [{"type": 10, "content": top_text}],
               "accessory": {"type": 11, "media": {"url": img}}}
    else:
        top = {"type": 10, "content": top_text}

    rows: list = [
        top,
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"info:cat:{user_id}",
            "placeholder": "Category…", "min_values": 1, "max_values": 1, "flows": {},
            "options": [{"label": _INFO_CAT_LABELS[c], "value": c, "default": c == cat}
                        for c in _INFO_CATEGORIES]}]},
    ]

    groups = _info_groups(cat)
    if groups:
        rows.append({"type": 1, "components": [{"type": 3,
            "custom_id": f"info:grp:{user_id}",
            "placeholder": "Filter…", "min_values": 1, "max_values": 1, "flows": {},
            "options": [{"label": lbl, "value": f"{cat}|{g}", "default": g == grp}
                        for g, lbl in groups[:25]]}]})
        name_entries = _info_entries_in_group(cat, grp)
    else:
        name_entries = entries

    rows.append({"type": 1, "components": [{"type": 3,
        "custom_id": f"info:name:{user_id}",
        "placeholder": "Select an entry…", "min_values": 1, "max_values": 1, "flows": {},
        "options": [{"label": lbl[:100], "value": f"{cat}|{k}", "default": k == key}
                    for k, lbl in name_entries[:25]]}]})

    rows.append(_back_row(user_id))
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": rows}]


async def _info_name_autocomplete(interaction: discord.Interaction, current: str):
    cat = getattr(interaction.namespace, "category", None) or "biomes"
    cur = (current or "").lower()
    out = []
    for key, label in _info_entries(cat):
        if cur in label.lower() or cur in key.lower():
            out.append(app_commands.Choice(name=label[:100], value=key[:100]))
        if len(out) >= 25:
            break
    return out


@bot.tree.command(name="info",
                  description="Look up info on biomes, tools, ammo, animals, mythical creatures and badges")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(category="What kind of thing to look up",
                       name="Which one — type to search")
@app_commands.choices(category=[
    app_commands.Choice(name=_INFO_CAT_LABELS[c], value=c) for c in _INFO_CATEGORIES
])
@app_commands.autocomplete(name=_info_name_autocomplete)
async def info_cmd(interaction: discord.Interaction,
                   category: app_commands.Choice[str], name: str):
    user_id = await _common_init(interaction)
    if not user_id:
        return
    cat = category.value
    key = _info_resolve(cat, name)
    if key is None:
        await send_ephemeral_v2(
            interaction,
            f"{emoji('cross_mark')} Couldn't find a **{_INFO_CAT_LABELS.get(cat, cat)}** entry called `{name}`.\n"
            f"-# Start typing in the **name** field and pick one from the list.",
            0xE74C3C)
        return
    _info_state[user_id] = {"category": cat, "group": _info_group_of(cat, key), "name": key}
    await send_v2_followup(interaction, build_info_components(user_id))
    await check_everything(interaction, user_id)


@bot.tree.command(name="help", description="View all available commands")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def help_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    init_user(user_id)
    _help_page[user_id] = 0
    await interaction.response.defer()
    await send_v2_followup(interaction, build_help_components(user_id, 0))
    await check_everything(interaction, user_id)

@bot.tree.command(name="craft", description="Fuse shards into crystals and buy Hunting Crates")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def craft_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_craft_components(user_id))
    await check_everything(interaction, user_id)

def _canon_crate_name(value: str) -> str | None:
    """Resolve a loose crate string ('mythic', 'Mythic Crate') to a CRATE_TIERS key."""
    v = value.strip().lower()
    for n in CRATE_TIERS:
        nl = n.lower()
        if v in (nl, nl.replace(" crate", "")):
            return n
    return None

_HEALING_ALIASES = {
    "meds": "Field Medkit", "med": "Field Medkit",
    "medkit": "Field Medkit", "med kit": "Field Medkit",
    "first aid": "First Aid Kit", "firstaid": "First Aid Kit",
}

def _canon_healing_name(value: str) -> str | None:
    """Resolve a loose healing-item string ('meds', 'bandage') to a HEALING_ITEMS key."""
    v = value.strip().lower()
    if v in _HEALING_ALIASES:
        return _HEALING_ALIASES[v]
    for n in HEALING_ITEMS:
        if v == n.lower():
            return n
    return None

async def _use_healing_item_and_show(interaction: discord.Interaction, user_id: str, item_name: str):
    inv = data[user_id].get("healing_inv", {})
    if inv.get(item_name, 0) <= 0:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You don't have any **{item_name}**.", 0xE74C3C)
        return
    refresh_health(user_id)
    hp, mx = player_hp(user_id)
    if hp >= mx:
        await send_ephemeral_v2(interaction,
            f"`❤️` You're already at full HP (**{hp}/{mx}**) — save your **{item_name}** for later.", 0x2ECC71)
        return
    async with user_transaction(user_id):
        inv = data[user_id]["healing_inv"]
        inv[item_name] -= 1
        if inv[item_name] <= 0:
            del inv[item_name]
        h = data[user_id]["health"]
        before = h["hp"]
        h["hp"] = min(effective_max_hp(user_id), h["hp"] + HEALING_ITEMS[item_name]["heal"])
        healed = h["hp"] - before
        new_hp, new_mx = h["hp"], effective_max_hp(user_id)
    ico = emoji("hp") or "❤️"
    await send_ephemeral_v2(interaction,
        f"{HEALING_ITEMS[item_name]['emoji']} You use a **{item_name}** (+{healed} HP).\n"
        f"{ico} **{new_hp}/{new_mx}**", 0x2ECC71)

@bot.tree.command(name="use", description="Open a crate or use a healing item you own")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(item="What to use — start typing to pick a crate or healing item you own")
async def use_cmd(interaction: discord.Interaction, item: str):
    user_id = await _common_init(interaction)
    if not user_id:
        return
    crate_name = _canon_crate_name(item)
    if crate_name:
        await _open_crate_and_show(interaction, user_id, crate_name)
        return
    heal_name = _canon_healing_name(item)
    if heal_name:
        await _use_healing_item_and_show(interaction, user_id, heal_name)
        return
    await send_ephemeral_v2(interaction,
        f"{emoji('cross_mark')} `{item}` isn't something you can use. `/use` opens Hunting Crates or heals with items like a "
        f"Bandage / First Aid Kit / Field Medkit — buy them in </craft:{COMMAND_ID.get('craft','0')}> or "
        f"the shop.", 0xE67E22)

@use_cmd.autocomplete("item")
async def _use_item_autocomplete(interaction: discord.Interaction, current: str):
    uid = str(interaction.user.id)
    d = data.get(uid) or {}
    cur = current.lower()
    out = [app_commands.Choice(name=f"{n} (×{c})", value=n)
           for n, c in (d.get("crate_inv") or {}).items() if c > 0 and cur in n.lower()]
    out += [app_commands.Choice(name=f"{n} (×{c}) — heal {HEALING_ITEMS[n]['heal']} HP", value=n)
            for n, c in (d.get("healing_inv") or {}).items() if c > 0 and cur in n.lower()]
    return out[:25]

@bot.tree.command(name="rules", description="View the Idle Hunter rules")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def rules_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    init_user(user_id)
    _rules_page[user_id] = 0
    await interaction.response.defer()
    route = Route("POST", "/webhooks/{application_id}/{token}",
                  application_id=interaction.application_id,
                  token=interaction.token)
    await bot.http.request(route, json={
        "flags": V2_FLAGS,
        "components": _clean_components(build_rules_components(user_id, 0)),
        "allowed_mentions": {"parse": []},
    })

@bot.tree.command(name="lottery", description="Buy tickets for the daily lottery draw")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def lottery_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_lottery_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="gamble", description="Try your luck at various games")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def gamble_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_gamble_menu(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="suggest", description="Make a suggestion for Idle Hunter")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(
    title="Short title for your suggestion",
    suggestion="Your full suggestion",
)
async def suggest_cmd(interaction: discord.Interaction, title: str, suggestion: str):
    user_id = str(interaction.user.id)
    init_user(user_id)
    await interaction.response.defer(ephemeral=True)
    if data[user_id]["level"] < 5:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You must be at least **Level 5** to send suggestions.", 0xE74C3C)
        return
    now          = time.time()
    last_suggest = data[user_id].get("last_suggest", 0)
    cooldown     = 3600
    if not is_admin(interaction):
        if now - last_suggest < cooldown:
            remaining = int(cooldown - (now - last_suggest))
            mins, secs = remaining // 60, remaining % 60
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} You can suggest again in **{mins}m {secs}s**.", 0xE74C3C)
            return
        if len(suggestion.strip()) < 20:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Suggestion must be at least **20 characters**.", 0xE74C3C)
            return
        if len(title.strip()) < 3:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Title must be at least **3 characters**.", 0xE74C3C)
            return
    async with user_transaction(user_id):
        data[user_id]["last_suggest"] = now
    try:
        import uuid as _uuid
        msg_id = _uuid.uuid4().hex[:12]
        route = Route("POST", "/channels/{channel_id}/messages",
                      channel_id=SUGGESTION_CHANNEL_ID)
        sent = await bot.http.request(route, json={
            "flags": V2_FLAGS,
            "components": [{"type": 17, "accent_color": 0x3498DB, "spoiler": False,
                "components": [
                    {"type": 10, "content":
                        f"### {emoji('tip')} New Suggestion\n"
                        f"**From:** {interaction.user.display_name} (`{user_id}`)\n"
                        f"**Level:** {data[user_id]['level']} · "
                        f"**Prestige:** {data[user_id].get('prestige', 0)} · "
                        f"**Caught:** {data[user_id].get('total_caught', 0):,}\n"
                        f"### {title.strip()}\n"
                        f"{suggestion.strip()}"
                    },
                    {"type": 14, "divider": True, "spacing": 1},
                    {"type": 1, "components": [
                        {"type": 2, "style": 3, "label": "Agree (0)", "emoji": emoji_partial('check_mark'),
                         "custom_id": f"suggestion:agree:{user_id}:{msg_id}"},
                        {"type": 2, "style": 2, "label": "➖ Neutral (0)",
                         "custom_id": f"suggestion:neutral:{user_id}:{msg_id}"},
                        {"type": 2, "style": 4, "label": "Disagree (0)", "emoji": emoji_partial('cross_mark'),
                         "custom_id": f"suggestion:disagree:{user_id}:{msg_id}"},
                    ]},
                ]}],
            "allowed_mentions": {"parse": []},
        })
        _suggestion_store[msg_id] = {
            "user_id": user_id, "display_name": interaction.user.display_name,
            "title": title.strip(), "text": suggestion.strip(),
            "channel_msg_id": sent.get("id"),
            "votes": {"agree": set(), "neutral": set(), "disagree": set()},
        }
    except Exception:
        pass
    await send_ephemeral_v2(interaction,
        f"### {emoji('tip')} Suggestion Sent!\nYour suggestion has been forwarded to the developers. Thank you!", 0x2ECC71)

@bot.tree.command(name="report", description="Report a user or a bug")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(
    type="What are you reporting?",
    title="Short title for your report",
    target_user="User to report (leave empty for bug reports)",
    description="Describe the issue in detail",
)
@app_commands.choices(type=[
    app_commands.Choice(name="User", value="user"),
    app_commands.Choice(name="Bug",  value="bug"),
])
async def report_cmd(interaction: discord.Interaction, type: str,
                     title: str, description: str, target_user: discord.User = None):
    user_id = str(interaction.user.id)
    init_user(user_id)
    await interaction.response.defer(ephemeral=True)
    if type == "user" and target_user is None:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Please specify a user to report.", 0xE74C3C)
        return
    if type == "user" and str(target_user.id) == user_id:
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} You can't report yourself.", 0xE74C3C)
        return
    now         = time.time()
    last_report = data[user_id].get("last_report", 0)
    cooldown    = 1800
    if is_admin(interaction) == False:
        if now - last_report < cooldown:
            remaining = int(cooldown - (now - last_report))
            mins, secs = remaining // 60, remaining % 60
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} You can submit another report in **{mins}m {secs}s**.", 0xE74C3C)
            return
        if len(description.strip()) < 20:
            await send_ephemeral_v2(interaction,
                f"{emoji('cross_mark')} Description must be at least **20 characters**.", 0xE74C3C)
            return
    async with user_transaction(user_id):
        data[user_id]["last_report"] = now
    channel = bot.get_channel(REPORTS_CHANNEL_ID)
    if channel:
        try:
            import uuid as _uuid
            msg_id = _uuid.uuid4().hex[:12]
            if type == "user":
                content = (
                    f"### {emoji('siren')} User Report: {title.strip()}\n"
                    f"-# Submitted by: <@{user_id}> ({interaction.user.name})\n"
                    f"**Reported user:** {target_user.display_name} (`{target_user.id}`)\n\n"
                    f"{description.strip()}"
                )
                color = 0xE74C3C
            else:
                content = (
                    f"### `🐛` Bug Report: {title.strip()}\n"
                    f"-# Submitted by: <@{user_id}> ({interaction.user.name})\n"
                    f"**Level:** {data[user_id]['level']} · "
                    f"**Prestige:** {data[user_id].get('prestige', 0)}\n\n"
                    f"{description.strip()}"
                )
                color = 0xE67E22
            route = Route("POST", "/channels/{channel_id}/messages",
                          channel_id=REPORTS_CHANNEL_ID)
            sent = await bot.http.request(route, json={
                "flags": V2_FLAGS,
                "components": [{"type": 17, "accent_color": color, "spoiler": False,
                    "components": [
                        {"type": 10, "content": content},
                        {"type": 14, "divider": True, "spacing": 1},
                        {"type": 1, "components": [
                            {"type": 2, "style": 1, "label": "I've also seen this (0)", "emoji": emoji_partial("eyes"),
                             "custom_id": f"report_btn:also_seen:{user_id}:{msg_id}"},
                            {"type": 2, "style": 3, "label": "Resolved", "emoji": emoji_partial('check_mark'),
                             "custom_id": f"report_btn:resolved:{user_id}:{msg_id}"},
                        ]},
                    ]}],
                "allowed_mentions": {"parse": []},
            })
            _report_store[msg_id] = {
                "user_id": user_id, "text": description.strip(),
                "content": content, "color": color,
                "channel_msg_id": sent.get("id"),
                "seen": set(),
            }
        except Exception as e:
            print("Report channel send error:", e)
    await send_ephemeral_v2(interaction,
        f"### {emoji('check_mark')} Report Submitted\n"
        "Your report has been sent to the moderation team. Thank you!\n"
        "-# Abuse of this system may result in a ban.", 0x2ECC71)

@bot.tree.command(name="tutorial", description="View the hunter's guide")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def tutorial_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_tutorial_guide_components(user_id, 0))

# ─────────────────────────────────────────────
# ADMIN COMMANDS
# ─────────────────────────────────────────────

# ── /update  (developer update log) ──────────

_ANNOUNCE_KIND_LABELS = {
    "event":     f"{emoji('earth')} WORLD EVENT",
    "sighting":  "`🔎` SIGHTING",
    "condition": f"{emoji('warning')} WORLD CONDITION",
    "result":    f"{emoji('trophy')} COMMUNITY RESULT",
}

def announce_card(kind: str, icon: str, title: str, *, subtitle: str = "", flavor: str = "",
                   actions: list[str] | None = None, progress_label: str = "",
                   progress_current: int | None = None, progress_target: int | None = None,
                   progress_unit: str = "", ends_ts: int | None = None, extra: str = "") -> str:
    """The one formula every global announcement follows, instead of each one
    inventing its own layout: KIND -> ICON TITLE (+ subtitle) -> one flavor
    sentence -> what to do -> progress -> time left. Every actionable line
    stands alone instead of being buried in a paragraph."""
    lines = [f"## {_ANNOUNCE_KIND_LABELS.get(kind, kind.upper())}",
             f"### {ph(icon)} {title}"]
    if subtitle:
        lines.append(f"-# {subtitle}")
    lines.append("")
    if flavor:
        lines.append(flavor)
        lines.append("")
    if actions:
        lines += list(actions)
        lines.append("")
    if ends_ts:
        lines.append(f"{emoji('cooldown')} Ends <t:{int(ends_ts)}:R>")
    if progress_target:
        bar, pct_label = ui_progress(progress_current or 0, progress_target)
        unit = f" {progress_unit}" if progress_unit else ""
        lines.append(f"{progress_label}: `{progress_current or 0:,} / {progress_target:,}{unit}`")
        lines.append(f"{bar} {pct_label}")
    if extra:
        lines.append("")
        lines.append(extra)
    return "\n".join(lines).strip()

def _announce_card_components(body_md: str, color: int, buttons: list[dict] | None = None,
                               thumb_url: str | None = None) -> list:
    top = ({"type": 9, "components": [{"type": 10, "content": body_md}],
             "accessory": {"type": 11, "media": {"url": thumb_url}}}
           if thumb_url else {"type": 10, "content": body_md})
    comps = [{"type": 17, "accent_color": color, "spoiler": False, "components": [top]}]
    if buttons:
        comps.append({"type": 1, "components": buttons})
    return comps

async def _announce(body_md: str, *, channel_id: int = ANNOUNCE_CHANNEL_ID,
                     role_id: int = ANNOUNCE_ROLE_ID, color: int = 0x2ECC71, ping: bool = True,
                     buttons: list[dict] | None = None, thumb_url: str | None = None) -> dict | None:
    """Post to a channel, optionally pinging one role. Best-effort — a failure
    here never breaks the caller. `body_md` may use ##/-# markdown.

    The ping (when present) is its OWN top-level text component ahead of the
    accent-colored card, not text glued onto the card itself — a role mention
    inside the card reads as part of the announcement; separated, it reads as
    what it is: a notification pointing at a card.

    Returns the created message's raw payload (so a caller — e.g. the
    sighting tracker — can edit it in place later), or None on failure.
    """
    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except Exception:
            return None
    components = []
    if ping:
        components.append({"type": 10, "content": f"<@&{role_id}>"})
    components += _announce_card_components(body_md, color, buttons, thumb_url)
    try:
        route = Route("POST", "/channels/{channel_id}/messages", channel_id=channel_id)
        return await bot.http.request(route, json={
            "flags": V2_FLAGS,
            "components": components,
            "allowed_mentions": {"roles": [str(role_id)]} if ping else {"parse": []},
        })
    except Exception as e:
        print("announce failed:", e)
        return None

async def _announce_edit(channel_id: int, message_id: int, body_md: str, color: int,
                          buttons: list[dict] | None = None, thumb_url: str | None = None) -> bool:
    """Edit an existing announcement card in place — used so a sighting's clue
    count updates the SAME message instead of spamming a new one every tick."""
    try:
        route = Route("PATCH", "/channels/{channel_id}/messages/{message_id}",
                      channel_id=channel_id, message_id=message_id)
        await bot.http.request(route, json={
            "flags": V2_FLAGS,
            "components": _announce_card_components(body_md, color, buttons, thumb_url),
        })
        return True
    except Exception as e:
        print("announce edit failed:", e)
        return False

async def _broadcast_update(u: dict) -> None:
    """Post a /update log entry to the announcements channel."""
    mod = get_username(str(u.get("moderator", ""))) or "the developers"
    await _announce(
        f"## {emoji('announcement')} {u.get('title', 'Update')}\n"
        f"{u.get('message', '')}\n\n"
        f"-# <t:{int(u.get('date', time.time()))}:D> · by {mod} · "
        f"see the full log with `/update view`")

async def _broadcast_expedition_result(tname: str, success: bool) -> None:
    """Post a public COMMUNITY RESULT card when a tribe's expedition wraps up
    — previously an entirely internal affair, visible only inside that
    tribe's own panels."""
    td  = tribe_data.get(tname)
    exp = td and td.get("expedition")
    if not exp:
        return
    spec  = TRIBE_EXPEDITIONS.get(exp.get("key", ""), {})
    rspec = spec.get("routes", {}).get(exp.get("route", ""), {})
    if success:
        body = announce_card(
            "result", spec.get('emoji', emoji('tribe')), f"{spec.get('name', 'Expedition')} Complete",
            subtitle=tname,
            flavor=f"**{tname}** cleared it via {rspec.get('label', 'their chosen route')}.",
            actions=[f"{emoji('gift')} Every contributor received a {rspec.get('crate', 'Rare Crate')}",
                     f"{emoji('sparkles')} +{rspec.get('xp', 500):,} tribe XP"],
        )
        color = 0x1ABC9C
    else:
        body = announce_card(
            "result", "🥀", f"{spec.get('name', 'Expedition')} Failed", subtitle=tname,
            flavor=f"**{tname}** ran out of time at {exp.get('progress', 0):,}/{exp.get('goal', 0):,}.",
        )
        color = 0x7F8C8D
    await _announce(body, color=color)

async def _broadcast_event_start(ev: dict) -> None:
    """Post an event-launch announcement when an admin starts a global event.
    Redesigned 2026-09-15 onto the shared announce_card formula — a real
    button instead of a raw '/events' instruction, and no more 'Runs until
    in 4 hours' (was 'Runs until' + a relative timestamp that already reads
    as 'in 4 hours')."""
    spec = EVENTS.get(ev.get("key", ""), {})
    kind = spec.get("kind", "activity")
    actions = list(spec.get("perks") or spec.get("actions") or [])

    progress_kwargs = {}
    if kind == "community" and ev.get("community"):
        progress_kwargs = {
            "progress_label": "Community", "progress_unit": "Bread",
            "progress_current": ev["community"].get("progress", 0),
            "progress_target": ev["community"].get("goal", 1),
        }

    body = announce_card(
        "event", spec.get('emoji', emoji('party_popper')), ev.get("name", "An Event"),
        flavor=spec.get("blurb", ""), actions=actions,
        ends_ts=ev.get("ends_ts"), **progress_kwargs,
    )
    buttons = [{"type": 2, "style": 1, "label": "Join Event",
                "emoji": {"name": spec.get('emoji', emoji('party_popper'))}, "custom_id": "announce:events:open"}]
    if kind != "buff":
        buttons.append({"type": 2, "style": 3, "label": "Hunt",
                         "emoji": emoji_partial('bow'), "custom_id": "announce:hunt:go"})
    await _announce(body, color=0xF1C40F, buttons=buttons)

class UpdateAddModal(_V2Modal, title="📢 Add Update"):
    title_in = discord.ui.TextInput(
        label="Title", placeholder="e.g. Crafting rework & new /use command",
        max_length=240, required=True)
    body_in = discord.ui.TextInput(
        label="Message (markdown & line breaks kept)",
        style=discord.TextStyle.paragraph, max_length=3900, required=True,
        placeholder="Write the full changelog here. **bold**, -# small text, • bullets all work.")

    def __init__(self, admin_id: str):
        super().__init__()
        self.admin_id = str(admin_id)

    async def on_submit(self, interaction: discord.Interaction):
        if self.admin_id not in BOT_ADMIN_ID:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Admins only.", 0xE74C3C)
            return
        entry = _apply_update_add(self.admin_id, self.title_in.value, self.body_in.value)
        admin_audit(self.admin_id, "update_add", entry["title"][:80])
        await smart_update_v2(interaction, build_update_admin_components(
            self.admin_id, 0, f"{emoji('check_mark')} Posted **{entry['title']}** — announced to the channel."))


class UpdateEditModal(_V2Modal, title="📢 Edit Update"):
    title_in = discord.ui.TextInput(label="Title", max_length=240, required=True)
    body_in = discord.ui.TextInput(
        label="Message", style=discord.TextStyle.paragraph, max_length=3900, required=True)

    def __init__(self, admin_id: str, idx: int):
        super().__init__()
        self.admin_id = str(admin_id)
        self.idx      = idx
        if 0 <= idx < len(UPDATE):
            self.title_in.default = (UPDATE[idx].get("title", "") or "")[:240]
            self.body_in.default  = (UPDATE[idx].get("message", "") or "")[:3900]

    async def on_submit(self, interaction: discord.Interaction):
        if self.admin_id not in BOT_ADMIN_ID:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Admins only.", 0xE74C3C)
            return
        if not (0 <= self.idx < len(UPDATE)):
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} That update no longer exists.", 0xE74C3C)
            return
        _apply_update_edit(self.admin_id, self.idx, self.title_in.value, self.body_in.value)
        admin_audit(self.admin_id, "update_edit", f"#{self.idx + 1}")
        page = _upd_admin_page.get(self.admin_id, 0)
        await smart_update_v2(interaction, build_update_admin_components(
            self.admin_id, page, f"{emoji('check_mark')} Saved changes to update **#{self.idx + 1}** (not re-announced)."))


update_group = app_commands.Group(
    name="update",
    description="Developer update log",
    allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
)

@update_group.command(name="control", description="Admin: add / edit / delete updates via a form")
@app_commands.check(is_admin)
async def update_control_cmd(interaction: discord.Interaction):
    admin_id = str(interaction.user.id)
    init_user(admin_id)
    await interaction.response.defer(ephemeral=True)
    await send_v2_followup(interaction, build_update_admin_components(admin_id, 0), ephemeral=True)

@update_group.command(name="view", description="View the latest updates from the developers")
async def update_view_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id:
        return
    _update_page[user_id] = 0
    await send_v2_followup(interaction, build_update_components(user_id, "all", 0))
    await check_everything(interaction, user_id)

@update_group.command(name="add", description="Append a new update to the end of the queue")
@app_commands.check(is_admin)
@app_commands.describe(title="The title to display", message="The update message to display")
async def update_add_cmd(interaction: discord.Interaction, title: str, message: str):
    await interaction.response.defer(ephemeral=True)
    _apply_update_add(str(interaction.user.id), title, message)

    mod_name = get_username(LATEST_UPDATE["moderator"])
    await send_ephemeral_v2(
        interaction,
        f"### {emoji('list')} Update Added (ID: {len(UPDATE)})\n"
        f"### **{LATEST_UPDATE['title']}**\n"
        f"{LATEST_UPDATE['message']}\n\n"
        f"-# Responsible Moderator: `{mod_name}`\n"
        f"-# Date: <t:{LATEST_UPDATE['date']}:D>\n\n"
        f"-# Updates are shown from oldest to newest (ID 1 is oldest)",
        0x2ECC71,
    )

@update_group.command(name="change", description="Edit the update queue (delete / change / reorder)")
@app_commands.check(is_admin)
@app_commands.describe(
    id="The update ID you want to change", 
    action="Queue operation", 
    title="The title to display (for add/change)", 
    message="The update message (for add/change)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="Delete", value="del"),
    app_commands.Choice(name="Change", value="chg"),
    app_commands.Choice(name="Add to Front", value="add_front"),
    app_commands.Choice(name="Pop First", value="pop_first"),
    app_commands.Choice(name="Pop Last", value="pop_last"),
    app_commands.Choice(name="View Queue", value="view"),
])
async def update_change_cmd(
    interaction: discord.Interaction,
    id: int,
    action: str,
    title: str = None,
    message: str = None
):
    global UPDATE, LATEST_UPDATE
    
    await interaction.response.defer(ephemeral=True)
    
    # View queue (no modifications)
    if action == "view":
        if not UPDATE:
            await send_ephemeral_v2(interaction, f"{emoji('list')} Update queue is empty.", 0xF1C40F)
            return
        
        queue_display = []
        for i, update in enumerate(UPDATE, 1):
            queue_display.append(
                f"**ID {i}:** {update['title']}\n"
                f"-# {update['message'][:50]}...\n"
                f"-# By <{get_username(update['moderator'])}>\n"
                f"-# <t:{update['date']}:D>"
            )
        
        await send_ephemeral_v2(
            interaction,
            f"### {emoji('list')} Update Queue ({len(UPDATE)} updates)\n\n" + "\n\n".join(queue_display[-5:]),  # Show last 5
            0x3498DB
        )
        return
    
    # Add to front (push to beginning of queue)
    if action == "add_front":
        if not title or not message:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Both title and message required for adding.", 0xE74C3C)
            return
        
        UPDATE.insert(0, {
            "title": title,
            "message": message,
            "moderator": str(interaction.user.id),
            "date": int(time.time())
        })
        
        # Recalculate IDs
        for i, update in enumerate(UPDATE, 1):
            update["id"] = i

        LATEST_UPDATE = UPDATE[-1]  # Latest is still the last one
        save_config()
        bot.loop.create_task(_broadcast_update(UPDATE[0]))

        await send_ephemeral_v2(
            interaction,
            f"### {emoji('list')} Update Added to Front\n"
            f"### {title}\n"
            f"{message}\n"
            f"-# By: `{get_username(str(interaction.user.id))}`\n"
            f"-# Date: <t:{int(time.time())}:D>, ID: {id}"
            f"-# Queue size: {len(UPDATE)} updates\n"
            f"-# Oldest ID: 1 · Newest ID: {len(UPDATE)}",
            0x2ECC71
        )
        return
    
    # Pop first (remove oldest update)
    if action == "pop_first":
        if not UPDATE:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Queue is empty!", 0xE74C3C)
            return
        
        removed = UPDATE.pop(0)
        
        # Recalculate IDs
        for i, update in enumerate(UPDATE, 1):
            update["id"] = i
        
        if UPDATE:
            LATEST_UPDATE = UPDATE[-1]
        else:
            LATEST_UPDATE = {"title": "", "message": ""}
        
        save_config()
        
        await send_ephemeral_v2(
            interaction,
            f"### {emoji('list')} Oldest Update Removed\n"
            f"**Removed:**\n"
            f"### {removed['title']}\n{removed['message']}\n"
            f"-# By: `{get_username(removed['moderator'])}`\n"
            f"-# Date: <t:{removed['date']}:D>, ID: {removed['id']}\n\n"
            f"-# Queue size now: {len(UPDATE)} updates",
            0xE67E22
        )
        return
    
    # Pop last (remove newest update)
    if action == "pop_last":
        if not UPDATE:
            await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Queue is empty!", 0xE74C3C)
            return
        
        removed = UPDATE.pop()
        
        if UPDATE:
            LATEST_UPDATE = UPDATE[-1]
        else:
            LATEST_UPDATE = {"title": "", "message": ""}
        
        save_config()
        
        await send_ephemeral_v2(
            interaction,
            f"### {emoji('list')} Newest Update Removed\n"
            f"**Removed:**\n"
            f"### {removed['title']}\n{removed['message']}\n"
            f"-# By: `{get_username(removed['moderator'])}`\n"
            f"-# Date: <t:{removed['date']}:D>, ID: {removed['id']}\n\n"
            f"-# Queue size now: {len(UPDATE)} updates",
            0xE67E22
        )
        return
    
    # Validate ID for delete/change operations
    if id <= 0 or id > len(UPDATE):
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} ID must be between 1 and {len(UPDATE)}", 0xE74C3C)
        return
    
    PREV_UPDATE = UPDATE[id - 1]
    
    # Delete by ID
    if action == "del":
        del UPDATE[id - 1]
        
        # Recalculate IDs
        for i, update in enumerate(UPDATE, 1):
            update["id"] = i
        
        if UPDATE:
            LATEST_UPDATE = UPDATE[-1]
        else:
            LATEST_UPDATE = {"title": "", "message": ""}
        
        save_config()
        
        await send_ephemeral_v2(
            interaction,
            f"### {emoji('list')} Update Deleted (ID {id})\n"
            f"**Deleted:**\n" 
            f"### {PREV_UPDATE['title']}\n{PREV_UPDATE['message']}\n"
            f"-# By: `{get_username(PREV_UPDATE['moderator'])}`\n"
            f"-# Date: <t:{PREV_UPDATE['date']}:D>, ID: {PREV_UPDATE['id']}\n\n"
            f"-# Queue size now: {len(UPDATE)} updates",
            0xE74C3C if len(UPDATE) == 0 else 0x2ECC71
        )
    
    # Change by ID
    elif action == "chg":
        if title is None or message is None:
            await send_ephemeral_v2(
                interaction,
                f"{emoji('cross_mark')} Both title and message required for changing an update.",
                0xE74C3C
            )
            return
        
        UPDATE[id - 1] = {
            "title": title,
            "message": message,
            "moderator": str(interaction.user.id),
            "date": int(time.time()),
            "id": id
        }
        
        LATEST_UPDATE = UPDATE[-1]
        save_config()
        
        await send_ephemeral_v2(
            interaction,
            f"### {emoji('list')} Update Changed (ID {id})\n"
            f"**Before:**\n" 
            f"### {PREV_UPDATE['title']}\n{PREV_UPDATE['message']}\n"
            f"-# By: `{get_username(PREV_UPDATE['moderator'])}`\n"
            f"-# Date: <t:{PREV_UPDATE['date']}:D>, ID: {PREV_UPDATE['id']}\n"
            f"**After:**\n" 
            f"### {title}\n"
            f"{message}\n"
            f"-# By: `{get_username(str(interaction.user.id))}`\n"
            f"-# Date: <t:{int(time.time())}:D>, ID: {id}",
            0x2ECC71
        )

bot.tree.add_command(update_group)


# ─────────────────────────────────────────────
# SESSION  ·  opt-in "since I last checked" continuity log
# ─────────────────────────────────────────────

session_group = app_commands.Group(
    name="session",
    description="Track hunts and gambling since you started a session",
    allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
)

@session_group.command(name="start", description="Start tracking hunts and gambling as one session")
async def session_start_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    if session_active(user_id):
        await send_ephemeral_v2(
            interaction,
            f"{emoji('stats')} You already have a session running — `/session stop` to close it out first, "
            "or `/session status` to check it.",
            0xE67E22)
        return
    session_start(user_id)
    await send_ephemeral_v2(
        interaction,
        f"{emoji('stats')} **Session started.** Your hunts and gambling from here on get tallied up — "
        "check in any time with `/session status`, or wrap it up with `/session stop`.",
        0x2ECC71)

@session_group.command(name="status", description="See your current session's totals so far")
async def session_status_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    sess = data[user_id].get("session")
    if not sess:
        await send_ephemeral_v2(
            interaction,
            f"{emoji('stats')} No session running. Start one with `/session start`.",
            0xE67E22)
        return
    lines = "\n".join(session_summary_lines(sess))
    await send_ephemeral_v2(interaction, f"### {emoji('stats')} Session So Far\n{lines}", 0x3498DB)

@session_group.command(name="stop", description="Stop your session and see the final tally")
async def session_stop_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    sess = data[user_id].get("session")
    if not sess:
        await send_ephemeral_v2(
            interaction,
            f"{emoji('stats')} No session running. Start one with `/session start`.",
            0xE67E22)
        return
    session_stop(user_id)
    lines = "\n".join(session_summary_lines(sess))
    await send_ephemeral_v2(interaction, f"### {emoji('stats')} Session Complete\n{lines}", 0x2ECC71)

bot.tree.add_command(session_group)


bot_group = app_commands.Group(
    name="bot",
    description="Admin bot controls",
    allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
)

@bot_group.command(name="devmail", description="Sets the developer mail message")
@app_commands.check(is_admin)
@app_commands.describe(message="The developer mail message")
async def setdevmail_cmd(interaction: discord.Interaction, message: str = ""):
    global DEV_MAIL
    user_id  = str(interaction.user.id)
    init_user(user_id)
    new_mail = message.strip()
    old_mail = DEV_MAIL
    changed  = new_mail != old_mail
    DEV_MAIL = new_mail
    save_config()
    async with user_transaction(user_id):
        if changed or not DEV_MAIL:
            for uid in data:
                data[uid]["mail_dev_content_read"] = ""
                data[uid]["mail_dev_notice_seen"]  = ""
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### {emoji('announcement')} Dev Mail Set\n{DEV_MAIL if DEV_MAIL else 'Dev mail cleared.'}", 0x2ECC71)

@bot_group.command(name="ban", description="Ban a user from using the bot")
@app_commands.check(is_admin)
@app_commands.describe(
    user_id="Discord user ID to ban",
    days="Duration in days (0 = permanent)",
    reason="Reason for the ban",
)
async def ban_cmd(interaction: discord.Interaction, user_id: str, days: int, reason: str):
    if not user_id.isdigit():
        await interaction.response.defer(ephemeral=True)
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Invalid user ID.", 0xE74C3C)
        return
    await _apply_ban(user_id, days, reason.strip(), by=interaction.user.id)
    duration_str = f"**{days} days**" if days > 0 else "**Permanent**"
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### `🔨` User Banned\n"
        f"<@{user_id}> has been banned.\n"
        f"Duration: {duration_str}\nReason: {reason}", 0xE74C3C)

@bot_group.command(name="unban", description="Unban a user")
@app_commands.check(is_admin)
@app_commands.describe(user_id="Discord user ID to unban")
async def unban_cmd(interaction: discord.Interaction, user_id: str):
    if not user_id.isdigit() or user_id not in data:
        await interaction.response.defer(ephemeral=True)
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} User not found.", 0xE74C3C)
        return
    async with user_transaction(user_id):
        data[user_id]["ban"]["active"] = False
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### {emoji('check_mark')} User Unbanned\n<@{user_id}> has been unbanned.", 0x2ECC71)

@bot_group.command(name="warn", description="Warn a user")
@app_commands.check(is_admin)
@app_commands.describe(user_id="Discord user ID to warn", reason="Reason for the warning")
async def warn_cmd(interaction: discord.Interaction, user_id: str, reason: str):
    if not user_id.isdigit():
        await interaction.response.defer(ephemeral=True)
        await send_ephemeral_v2(interaction, f"{emoji('cross_mark')} Invalid user ID.", 0xE74C3C)
        return
    warn_count = await _apply_warn(user_id, reason.strip(), by=interaction.user.id)
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### {emoji('warning')} User Warned\n"
        f"<@{user_id}> has been warned.\n"
        f"Reason: {reason}\nTotal warnings: **{warn_count}**", 0xF1C40F)

def _currency_balance_block(field: str, icon: str, label: str) -> str:
    """One currency's balance distribution — sync, reads only live player data.
    Split out from the flow stats below so the (sync) /admin panel can still
    show this without needing to await a DB query."""
    all_balances = sorted(d.get(field, 0) for d in data.values())
    n = len(all_balances)
    total = sum(all_balances)
    median = all_balances[n // 2] if n else 0
    p90    = all_balances[int(n * 0.9)]  if n else 0
    p99    = all_balances[int(n * 0.99)] if n else 0
    top_holder = max(data.items(), key=lambda x: x[1].get(field, 0), default=(None, {}))
    return (
        f"### {icon} {label}\n"
        f"**In circulation:** {icon} {total:,} across **{n:,}** players\n"
        f"**Median / P90 / P99 balance:** {icon} {median:,} / {icon} {p90:,} / {icon} {p99:,}\n"
        f"**Top holder:** `{top_holder[1].get('username', '?')}` — {icon} {top_holder[1].get(field, 0):,}"
    )

async def _currency_flow_block(currency: str, icon: str) -> str:
    """All-time and 24h earned/spent plus top sources, from the economy_log
    table — the source of truth for mint/burn, since balances alone can't
    tell you WHY they moved. Async: this is the part that needs the DB."""
    s = await backend.economy_summary(currency)
    net_all = s["minted_all"] - s["burned_all"]
    net_24h = s["minted_24h"] - s["burned_24h"]

    def _src_lines(rows):
        return "\n".join(f"-#   `{src}` — {icon} {amt:,}" for src, amt in rows) or "-#   (no data yet)"

    last_at = s.get("last_event_at")
    if last_at:
        try:
            ts = int(datetime.strptime(last_at, "%Y-%m-%d %H:%M:%S")
                      .replace(tzinfo=timezone.utc).timestamp())
            last_line = f"-# Last economy event: <t:{ts}:R>\n"
        except ValueError:
            last_line = ""
    else:
        last_line = "-# Last economy event: none yet\n"

    return (
        f"{last_line}"
        f"**All-time:** {emoji('green_ball')} Earned {icon} {s['minted_all']:,} · "
        f"{emoji('red_ball')} Spent {icon} {s['burned_all']:,} · Net {icon} {net_all:,}\n"
        f"**Last 24h:** {emoji('green_ball')} Earned {icon} {s['minted_24h']:,} · "
        f"{emoji('red_ball')} Spent {icon} {s['burned_24h']:,} · Net {icon} {net_24h:,}\n\n"
        f"**Top earn sources (all-time):**\n{_src_lines(s['top_earn'])}\n"
        f"**Top spend sources (all-time):**\n{_src_lines(s['top_spend'])}"
    )

async def _economy_dashboard_text() -> str:
    gem_icon = emoji("gem") or "💎"
    money = _currency_balance_block("money", "◈", "Money") + "\n" + await _currency_flow_block("money", "◈")
    gems  = _currency_balance_block("gems", gem_icon, "Gems") + "\n" + await _currency_flow_block("gems", gem_icon)
    return f"### `📊` Economy Dashboard\n\n{money}\n\n{gems}"

@bot_group.command(name="economy", description="Economy diagnostics")
@app_commands.check(is_admin)
async def economy_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction, await _economy_dashboard_text(), 0x3498DB)

async def _funnel_report_text(since_days: int) -> str:
    steps = await backend.funnel_report(since_days)
    base = steps[0]["count"]
    lines = [f"### `📉` Acquisition → Retention Funnel — last {since_days}d\n"]
    if base == 0:
        lines.append("-# No new players joined in this window.")
        return "\n".join(lines)
    prev = base
    for i, s in enumerate(steps):
        pct_of_start = (s["count"] / base * 100) if base else 0
        if i == 0:
            lines.append(f"**{s['label']}: {s['count']:,}**")
        else:
            pct_of_prev = (s["count"] / prev * 100) if prev else 0
            bar = _pct_bar(pct_of_start)
            lines.append(f"{bar + ' ' if bar else ''}**{s['label']}: {s['count']:,}**")
            lines.append(f"-# {pct_of_start:.0f}% of new · {pct_of_prev:.0f}% of prev step")
        prev = s["count"] or prev
    lines.append(
        "\n-# Each step counts cohort members who *ever* reached it, not just "
        "within this window — D7 numbers stay low until the cohort is a week old. "
        "Playtime-minutes isn't instrumented yet, so \"10 hunts\" stands in for "
        "the engagement gate before D1/D3/D7."
    )
    return "\n".join(lines)

@bot_group.command(name="funnel", description="Admin: acquisition & retention funnel")
@app_commands.describe(days="Cohort window in days (players who joined this recently)")
@app_commands.check(is_admin)
async def funnel_cmd(interaction: discord.Interaction, days: int = 30):
    await interaction.response.defer(ephemeral=True)
    days = max(1, min(365, days))
    await send_ephemeral_v2(interaction, await _funnel_report_text(days), 0x3498DB)

# ─────────────────────────────────────────────
# ADMIN CONTROL PANEL  (/admin)
# ─────────────────────────────────────────────

ADMIN_ACCENT = 0x5865F2

def _maint_status_line() -> str:
    if maintenance_mode:
        return f"{emoji('red_ball')} **Active** — all non-admin commands are blocked."
    if maintenance_warning:
        return f"{emoji('yellow_ball')} **Warning** — players are being told maintenance is coming soon."
    return f"{emoji('green_ball')} **Normal** — bot is running for everyone."

def _admin_row(*buttons: dict) -> dict:
    return {"type": 1, "components": list(buttons)}

def _admin_btn(label: str, cid: str, style: int = 2, emoji_key: str = "") -> dict:
    d = {"type": 2, "style": style, "label": label, "custom_id": cid}
    ep = emoji_partial(emoji_key) if emoji_key else None
    if ep:
        d["emoji"] = ep
    return d

# Sections shown in the "jump to a section" dropdown on every admin screen.
_ADMIN_SECTIONS = [
    ("home",     "home",                     "Overview",       "Dashboard & maintenance status"),
    ("economy",  "money_bag",                "Economy",        "Money & gems — give / take / set"),
    ("progress", "chart_with_upwards_trend", "Progression",    "Level, prestige, XP, catches, streak"),
    ("items",    "inventory",                "Items & Perks",  "Tools, ammo, crates, boosts, premium, titles"),
    ("world",    "earth",                    "World & State",  "Biome, cooldowns, verify lock, idle"),
    ("player",   "shield",                   "Moderation",     "Lookup, ban, unban, warn, clear warnings"),
    ("danger",   "skull_and_crossbones",     "Danger Zone",    "Reset or delete an entire account"),
    ("events",   "party_popper",             "Events",         "Start / stop the Admin's Day Off buff"),
    ("maint",    "wrench",                   "Maintenance",    "Maintenance mode & warnings"),
    ("info",     "bar_chart",                "Server Info",    "Economy dashboard & roster counts"),
]
# Select-option labels are plain text (custom emoji only renders via the
# option's own "emoji" field, never embedded in "label" — see _admin_navsel).
# This combined form is only for message CONTENT headers, where embedding
# is fine.
_ADMIN_SECTION_LABEL = {v: f"{emoji(k)} {l}" for v, k, l, _ in _ADMIN_SECTIONS}

# section -> [(op, emoji key, dropdown label)]  — the action picker inside each section.
_ADMIN_SECTION_ACTIONS: dict[str, list[tuple[str, str, str]]] = {
    "economy": [
        ("give_money", "banknote_with_dollar_sign", "Give money"),
        ("take_money", "money_with_wings",           "Take money"),
        ("set_money",  "equals",                     "Set money to an exact amount"),
        ("give_gems",  "gem",                        "Give gems"),
        ("take_gems",  "gem",                        "Take gems"),
        ("set_gems",   "equals",                     "Set gems to an exact amount"),
    ],
    "progress": [
        ("set_level",    "chart_with_upwards_trend", "Set level"),
        ("set_prestige", "prestige",                 "Set prestige"),
        ("set_xp",       "sparkles",                 "Set XP into current level"),
        ("set_caught",   "target",                   "Set total animals caught"),
        ("set_streak",   "fire",                     "Set daily streak"),
    ],
    "items": [
        ("grant_tool",      "wrench",       "Grant a tool"),
        ("grant_all_tools", "toolbox",      "Grant every tool"),
        ("set_vehicle",     "jeep",         "Set vehicle"),
        ("give_item",       "animal_fallback", "Give animal(s) to inventory"),
        ("clear_inventory", "trash",        "Clear the animal inventory"),
        ("clear_crates",    "trash",        "Clear all crates"),
        ("give_ammo",       "pistol",       "Give ammo"),
        ("give_crate",      "package",      "Give crate(s)"),
        ("refund_crates",   "package",      "Refund crate(s) to a player"),
        ("give_shard",      "gem",          "Give shard(s) (by rarity)"),
        ("give_crystal",    "diamond_blue", "Give crystal(s) (by rarity)"),
        ("set_luck",        "four_leaf_clover", "Set personal luck boost %"),
        ("set_sell",        "dollar",       "Set personal sell boost %"),
        ("set_xpb",         "books",        "Set personal XP boost %"),
        ("max_boosts",      "rocket",       "Max all personal boosts"),
        ("toggle_premium",  "prestige",     "Toggle premium"),
        ("grant_title",     "label",        "Grant a title"),
        ("grant_special",   "military_medal", "Grant a special badge"),
        ("revoke_special",  "minus",        "Revoke a special badge"),
    ],
    "world": [
        ("set_biome",       "earth",            "Set current biome"),
        ("clear_cooldowns", "stopwatch",        "Clear hunt & daily cooldowns"),
        ("clearverify",     "key",              "Clear verify lock"),
        ("clear_idle",      "sleeping_symbol",  "Reset Hunting Camp (hunters/upgrades/haul)"),
    ],
    "player": [
        ("lookup",        "search",     "Look up a player"),
        ("toggle_tester", "test_tube",  "Toggle TESTER flag"),
        ("ban",           "hammer",     "Ban a player"),
        ("unban",         "check_mark", "Unban a player"),
        ("warn",          "warning",    "Warn a player"),
        ("clearwarns",    "broom",      "Clear all warnings"),
    ],
    "danger": [
        ("reset_account",  "recycle", "Reset account (wipe progress/boosts, gems max 100, no prestige)"),
        ("delete_account", "trash",   "Delete account (erase all data)"),
    ],
}

_ADMIN_SECTION_HINT = {
    "economy":  "Amounts accept shorthand — `1k`, `2.5m`, `1b`.",
    "progress": "Whole numbers only. Setting the level also zeroes current-level XP.",
    "items":    "Names must match the game exactly (case-insensitive). Animals / ammo / "
                "crates also ask for a quantity; shards / crystals take a rarity.",
    "world":    "Biome accepts the id or the display name (e.g. `rainbow` or `Rainbow Realm`).",
    "player":   "Every action takes a Discord user ID.",
    "danger":   f"{emoji('warning')} Irreversible. A confirmation step is always shown first.",
}


def _admin_navsel(a: str, current: str) -> dict:
    return {"type": 1, "components": [{
        "type": 3, "custom_id": f"admin:navsel:{a}",
        "placeholder": "📂 Jump to a section…",
        "options": [
            {"label": lbl, "value": val, "description": desc, "emoji": emoji_partial(key),
             "default": (val == current)}
            for val, key, lbl, desc in _ADMIN_SECTIONS
        ],
    }]}


def _admin_actsel(a: str, section: str):
    acts = _ADMIN_SECTION_ACTIONS.get(section)
    if not acts:
        return None
    return {"type": 1, "components": [{
        "type": 3, "custom_id": f"admin:act:{section}:{a}",
        "placeholder": "⚙️ Pick an action…",
        "options": [{"label": lbl, "value": op, "emoji": emoji_partial(key)} for op, key, lbl in acts],
    }]}


def build_admin_panel(admin_id: str, section: str = "home", note: str = "") -> list:
    a = admin_id
    if section not in _ADMIN_SECTION_LABEL:
        section = "home"

    blocks: list = [
        {"type": 10, "content": f"## `🛠️` Admin Panel — {_ADMIN_SECTION_LABEL[section]}"},
        _admin_navsel(a, section),
    ]
    if note:
        blocks.append({"type": 14, "divider": True, "spacing": 1})
        blocks.append({"type": 10, "content": note})
    blocks.append({"type": 14, "divider": True, "spacing": 1})

    accent = ADMIN_ACCENT

    if section == "home":
        banned = sum(1 for d in data.values() if d.get("ban", {}).get("active"))
        ev_line = f"**Event:** {event_banner_line()}\n" if get_active_event() else ""
        blocks.append({"type": 10, "content":
            f"-# Signed in as <@{a}> · this panel is private to you\n"
            f"**Maintenance:** {_maint_status_line()}\n"
            f"{ev_line}"
            f"-# `👥` {len(data):,} users · `🏕️` {len(tribe_data):,} tribes · `🔨` {banned:,} banned\n\n"
            "Pick a section from **Jump to a section** above, then choose an action from that "
            "section's menu. Every action asks for a target Discord user ID; economy, progression "
            "and destructive actions show a confirm step."})
        blocks.append(_admin_row(
            _admin_btn("Events", f"admin:nav:events:{a}", 1, emoji_key="party_popper"),
            _admin_btn("Maintenance", f"admin:nav:maint:{a}", 1, emoji_key="wrench"),
            _admin_btn("Server Info", f"admin:nav:info:{a}", 1, emoji_key="bar_chart"),
            _admin_btn("Refresh", f"admin:home:{a}", emoji_key="refresh"),
        ))

    elif section == "events":
        ev = get_active_event()
        if ev:
            spec = EVENTS.get(ev["key"], ADMIN_BUFF_EVENT)
            extra = ("\n\n" + "\n".join(f"-# {p}" for p in spec.get("perks", []))
                     if spec.get("perks") else f"\n-# {spec.get('blurb','')}")
            blocks.append({"type": 10, "content":
                f"### {spec['emoji']} {ev['name']} — **LIVE** ({spec.get('kind','buff')})\n"
                f"-# Started <t:{int(ev['started_ts'])}:R> by <@{ev.get('by','?')}> · "
                f"ends <t:{int(ev['ends_ts'])}:R>" + extra})
            blocks.append(_admin_row(
                _admin_btn("Stop Event Now", f"admin:event:stop:{a}", 4, emoji_key="stop_square"),
                _admin_btn("◀ Overview", f"admin:home:{a}"),
            ))
        else:
            blocks.append({"type": 10, "content":
                "### `🎉` Events\n-# Pick one to start server-wide. One runs at a time; "
                "it auto-ends after its window and you can stop it early here.\n\n"
                + "\n".join(f"-# {s['emoji']} **{s['name']}** — {s['blurb'][:90]}…"
                            for s in EVENTS.values())})
            blocks.append({"type": 1, "components": [{"type": 3,
                "custom_id": f"admin:eventsel:{a}",
                "placeholder": "▶️ Start an event…",
                "options": [{"label": f"{s['emoji']} {s['name']}", "value": k,
                             "description": f"{s.get('kind','buff')} · {s.get('hours',24)}h"}
                            for k, s in EVENTS.items()]}]})
            blocks.append(_admin_row(_admin_btn("◀ Overview", f"admin:home:{a}")))

    elif section == "maint":
        blocks.append({"type": 10, "content":
            f"### `🔧` Maintenance\n"
            f"**Status:** {_maint_status_line()}\n"
            f"**Reason:** {maintenance_message or '—'}\n"
            f"-# Warned users: {len(_maintenance_warned)}"})
        if maintenance_mode:
            blocks.append(_admin_row(
                _admin_btn("Disable", f"admin:do:maint_toggle:{a}", 3, emoji_key="green_ball"),
                _admin_btn("Toggle Warning", f"admin:do:maint_warn_toggle:{a}", emoji_key="yellow_ball"),
            ))
        else:
            # Enabling requires a reason, so this opens a modal directly rather
            # than a bare confirm — there's no separate "set reason" step anymore.
            blocks.append(_admin_row(
                _admin_btn("Enable Now", f"admin:modal:maint_enable:{a}", 4, emoji_key="red_ball"),
                _admin_btn("Toggle Warning", f"admin:do:maint_warn_toggle:{a}", emoji_key="yellow_ball"),
            ))
        blocks.append(_admin_row(
            _admin_btn("◀ Overview", f"admin:home:{a}"),
        ))

    elif section == "info":
        banned  = sum(1 for d in data.values() if d.get("ban", {}).get("active"))
        premium = sum(1 for d in data.values() if d.get("premium"))
        blocks.append({"type": 10, "content":
            f"{_currency_balance_block('money', '◈', 'Money')}\n"
            f"{_currency_balance_block('gems', emoji('gem') or '💎', 'Gems')}\n"
            f"-# Full earn/spend breakdown: </bot economy:{COMMAND_ID.get('bot','0')}>\n\n"
            f"**Roster:**\n"
            f"-# `👥` Users: {len(data):,}  ·  `🏕️` Tribes: {len(tribe_data):,}\n"
            f"-# 🔨 Banned: {banned:,}  ·  {emoji('vip')} Premium: {premium:,}"})
        # ── Idle Hunter V2 — live world + onboarding funnel ──
        _conds = ", ".join(f"{BIOME_NAMES.get(b,b)}: {WORLD_CONDITIONS.get(c['key'],{}).get('name','?')}"
                           for b, c in _world_conditions.items()) or "none"
        _sg = get_active_sighting()
        _sg_txt = (f"{_sg['creature'] if _sg.get('revealed') else '`❓`'} in "
                   f"{BIOME_NAMES.get(_sg['biome'], _sg['biome'])} "
                   f"({_sg.get('clues',0)}/{SIGHTING_CLUE_GOAL})") if _sg else "none"
        _flags = " ".join(k.replace("FEATURE_", "").lower()
                          for k, v in (("FEATURE_ONBOARDING_V2", FEATURE_ONBOARDING_V2),
                                       ("FEATURE_WORLD_CONDITIONS", FEATURE_WORLD_CONDITIONS),
                                       ("FEATURE_TRACKING", FEATURE_TRACKING),
                                       ("FEATURE_WORLD_SIGHTINGS", FEATURE_WORLD_SIGHTINGS),
                                       ("FEATURE_SHARE_CARDS", FEATURE_SHARE_CARDS),
                                       ("FEATURE_AUTO_EVENTS", FEATURE_AUTO_EVENTS),
                                       ("FEATURE_EXPEDITIONS", FEATURE_EXPEDITIONS),
                                       ("FEATURE_SERVER_GOALS", FEATURE_SERVER_GOALS),
                                       ("FEATURE_REFERRALS", FEATURE_REFERRALS)) if v) or "none"
        blocks.append({"type": 10, "content":
            f"**{emoji('earth')} V2 live world**\n"
            f"-# Conditions: {_conds}\n"
            f"-# Sighting: {_sg_txt}\n"
            f"-# Features on: {_flags}\n"
            f"-# Funnel & retention: </bot funnel:{COMMAND_ID.get('bot','0')}>"})
        blocks.append(_admin_row(
            _admin_btn("Force Sighting", f"admin:do:v2_sighting:{a}", 1, emoji_key="siren"),
            _admin_btn("Top up Conditions", f"admin:do:v2_conditions:{a}", 1, emoji_key="weather_showers"),
        ))
        blocks.append(_admin_row(
            _admin_btn("Refresh", f"admin:nav:info:{a}", emoji_key="refresh"),
            _admin_btn("◀ Overview", f"admin:home:{a}"),
        ))

    else:  # economy / progress / items / world / player / danger
        if section == "danger":
            accent = 0xE74C3C
        blocks.append({"type": 10, "content": f"-# {_ADMIN_SECTION_HINT.get(section, '')}"})
        actsel = _admin_actsel(a, section)
        if actsel:
            blocks.append(actsel)
        if section == "danger":
            _wiped = sum(1 for d in data.values()
                         if d.get("crate_inv") or d.get("shards") or d.get("crystals")
                         or d.get("craft_queue"))
            blocks.append({"type": 14, "divider": True, "spacing": 1})
            blocks.append({"type": 10, "content":
                "**`🧨` Server-wide wipe**\n"
                f"-# Clears **every** player's crates, shards, crystals and craft queue "
                f"({_wiped:,} player(s) currently hold some). Gemstones are kept."})
            blocks.append(_admin_row(
                _admin_btn("Wipe ALL Crates & Materials", f"admin:do:wipe_crates:{a}", 4, emoji_key="firecracker"),
            ))
        blocks.append(_admin_row(_admin_btn("◀ Overview", f"admin:home:{a}")))

    return [{"type": 17, "accent_color": accent, "spoiler": False, "components": blocks}]

# ── Admin action model: modal → validate → confirm (ephemeral) → apply ──

# op -> (modal title, number-field label). Each takes "target user id + one number".
# Modal titles / field labels are plain text — no emoji object slot exists for
# them (same restriction as button/select labels), so these stay unadorned.
_ADMIN_AMOUNT_OPS = {
    "give_money":   ("Give Money",      "Amount (◈)"),
    "take_money":   ("Take Money",      "Amount (◈)"),
    "set_money":    ("Set Money",       "New balance (◈)"),
    "give_gems":    ("Give Gems",       "Amount (gems)"),
    "take_gems":    ("Take Gems",       "Amount (gems)"),
    "set_gems":     ("Set Gems",        "New balance (gems)"),
    "set_level":    ("Set Level",       "New level"),
    "set_prestige": ("Set Prestige",    "New prestige"),
    "set_xp":       ("Set XP",          "XP into current level"),
    "set_caught":   ("Set Total Caught", "New total caught"),
    "set_streak":   ("Set Daily Streak", "New streak"),
    "set_luck":     ("Set Luck Boost",  "Luck boost %"),
    "set_sell":     ("Set Sell Boost",  "Sell boost %"),
    "set_xpb":      ("Set XP Boost",    "XP boost %"),
}

# Subset of the above that takes a plain whole number (no k/m/b shorthand).
_ADMIN_INT_OPS = {
    "set_level", "set_prestige", "set_xp", "set_caught", "set_streak",
    "set_luck", "set_sell", "set_xpb",
}
_ADMIN_INT_RANGE = {
    "set_level":    (1, 100_000),
    "set_prestige": (0, 100_000),
    "set_xp":       (0, 1_000_000_000_000),
    "set_caught":   (0, 1_000_000_000_000),
    "set_streak":   (0, 1_000_000),
    "set_luck":     (0, 100_000),
    "set_sell":     (0, 100_000),
    "set_xpb":      (0, 100_000),
}

# op -> (modal title, value-field label, placeholder, wants a quantity field)
_ADMIN_TEXT_OPS = {
    "set_biome":   ("Set Biome",           "Biome id or name",     "e.g. forest / Rainbow Realm", False),
    "grant_tool":  ("Grant Tool",          "Exact tool name",      "e.g. Longbow",                False),
    "set_vehicle": ("Set Vehicle",         "Vehicle name or None", "e.g. Helicopter",             False),
    "grant_title": ("Grant Title",         "Title text",           "e.g. Beta Tester",            False),
    "grant_special":  ("Grant Special Badge",  "Badge key or name", "special recon / tester / bug hunter", False),
    "revoke_special": ("Revoke Special Badge", "Badge key or name", "special recon / tester / bug hunter", False),
    "give_item":   ("Give Animals", "Exact animal name",     "e.g. Golden Deer",           True),
    "give_ammo":   ("Give Ammo",    "Exact ammo name",       "e.g. Silver Bullet",         True),
    "give_crate":  ("Give Crates",  "Exact crate name",      "e.g. Mythic Crate",          True),
    "refund_crates": ("Refund Crates", "Exact crate name",     "e.g. Mythic Crate",          True),
    "give_shard":  ("Give Shards",  "Rarity",                "common / rare / mythic …",   True),
    "give_crystal":("Give Crystals","Rarity",                "common / rare / mythic …",   True),
}

# op -> modal title. Takes only a target user id.
_ADMIN_UID_OPS = {
    "lookup":          "Player Lookup",
    "toggle_tester":   "Toggle Tester",
    "unban":           "Unban Player",
    "clearwarns":      "Clear Warnings",
    "clearverify":     "Clear Verify Lock",
    "clear_cooldowns": "Clear Cooldowns",
    "clear_inventory": "Clear Inventory",
    "clear_crates":    "Clear Crates",
    "clear_idle":      "Reset Hunting Camp",
    "grant_all_tools": "Grant All Tools",
    "max_boosts":      "Max Personal Boosts",
    "toggle_premium":  "Toggle Premium",
    "reset_account":   "Reset Account",
    "delete_account":  "Delete Account",
}

ADMIN_MAX_MONEY    = 1_000_000_000_000   # per single give/take/set action
ADMIN_MAX_LEVEL    = 100_000
ADMIN_MAX_PRESTIGE = 100_000
ADMIN_MAX_BOOST    = 100_000
ADMIN_MAX_BAN_DAYS = 3650
ADMIN_MAX_GIVE_QTY = 100_000

# op -> section, so a result banner lands back on the right screen.
_ADMIN_OP_SECTION = {op: sec for sec, acts in _ADMIN_SECTION_ACTIONS.items() for op, _, _ in acts}

# Important actions: an "are you sure?" step is inserted before they run.
_ADMIN_CONFIRM_OPS = {
    "give_money", "take_money", "set_money", "give_gems", "take_gems", "set_gems",
    "set_level", "set_prestige", "set_xp", "set_caught", "set_streak",
    "set_luck", "set_sell", "set_xpb", "max_boosts",
    "grant_all_tools", "clear_inventory", "clear_crates", "clear_idle", "toggle_premium", "toggle_tester",
    "grant_special", "revoke_special",
    "ban", "warn", "unban", "clearwarns", "maint_toggle",
    "reset_account", "delete_account", "wipe_crates",
}

_admin_pending: dict[str, dict] = {}

async def _refresh_admin(interaction: discord.Interaction, admin_id: str, section: str, note: str = ""):
    await smart_update_v2(interaction, build_admin_panel(admin_id, section, note))

def _admin_section_for(op: str) -> str:
    if op in ("maint_toggle", "maint_warn_toggle", "maint_enable"):
        return "maint"
    if op in ("ban", "warn", "unban", "clearwarns", "lookup"):
        return "player"
    if op == "wipe_crates":
        return "danger"
    return _ADMIN_OP_SECTION.get(op, "home")

def _build_admin_confirm(admin_id: str, token: str, summary: str) -> list:
    return [{"type": 17, "accent_color": 0xE67E22, "spoiler": False, "components": [
        {"type": 10, "content":
            f"### {emoji('warning')} Confirm admin action\n{summary}\n\n-# This is not auto-undoable."},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 4, "label": "Confirm", "emoji": emoji_partial('check_mark'),
             "custom_id": f"admin:confirm:{token}:{admin_id}"},
            {"type": 2, "style": 2, "label": "✖ Cancel",
             "custom_id": f"admin:cancel:{token}:{admin_id}"},
        ]},
    ]}]

async def _admin_stage(interaction: discord.Interaction, admin_id: str,
                       op: str, params: dict, summary: str):
    """Gate an important action behind a confirm panel; run trivial ones now."""
    if op not in _ADMIN_CONFIRM_OPS:
        section, note = await _admin_apply(op, params, admin_id)
        await _refresh_admin(interaction, admin_id, section, note)
        return
    token = secrets.token_hex(4)
    _admin_pending[token] = {"admin_id": str(admin_id), "op": op,
                             "params": params, "summary": summary, "ts": time.time()}
    await smart_update_v2(interaction, _build_admin_confirm(admin_id, token, summary))

async def _broadcast_maintenance(enabled: bool):
    """Post to the one announcements channel every server sees (same route as
    /update and event start posts) — a per-channel opt-in list never reaches
    more than whichever channel an admin happened to click the button from."""
    if enabled:
        await _announce(
            f"## `🔧` Maintenance Started\n**Idle Hunter is now in maintenance mode.**\n\n"
            f"Reason: {maintenance_message or '—'}\n-# Your data is safe. Back soon `🏕️`",
            color=0xE74C3C, ping=True)
    else:
        await _announce(
            f"## {emoji('check_mark')} Bot Back Online\n**Idle Hunter is back!** All commands work again. {emoji('bow')}",
            color=0x2ECC71, ping=False)
def _amount_summary(op: str, target: str, val: int) -> str:
    return {
        "give_money":   f"Give **◈ {val:,}** to <@{target}>.",
        "take_money":   f"Take **◈ {val:,}** from <@{target}>.",
        "set_money":    f"Set <@{target}>'s money to **◈ {val:,}**.",
        "give_gems":    f"Give **`💎` {val:,}** to <@{target}>.",
        "take_gems":    f"Take **`💎` {val:,}** from <@{target}>.",
        "set_gems":     f"Set <@{target}>'s gems to **`💎` {val:,}**.",
        "set_level":    f"Set <@{target}> to **Level {val:,}** (current-level XP reset to 0).",
        "set_prestige": f"Set <@{target}> to **Prestige {val:,}**.",
        "set_xp":       f"Set <@{target}>'s current-level XP to **{val:,}**.",
        "set_caught":   f"Set <@{target}>'s total caught to **{val:,}**.",
        "set_streak":   f"Set <@{target}>'s daily streak to **{val:,}**.",
        "set_luck":     f"Set <@{target}>'s personal luck boost to **{val:,}%**.",
        "set_sell":     f"Set <@{target}>'s personal sell boost to **{val:,}%**.",
        "set_xpb":      f"Set <@{target}>'s personal XP boost to **{val:,}%**.",
    }.get(op, f"{op}: {val:,} on <@{target}>")


_RARITY_POOL = {r: r for r in RARITY_KEYS}
_SPECIAL_BADGE_POOL = {k: SPECIAL_BADGES[k]["label"] for k in SPECIAL_BADGES}
_ADMIN_TEXT_POOL = {
    "grant_tool":  TOOLS,
    "set_vehicle": VEHICLES,
    "give_item":   ANIMAL_DATA,
    "give_ammo":   AMMO,
    "give_crate":  CRATE_TIERS,
    "refund_crates": CRATE_TIERS,
    "give_shard":  _RARITY_POOL,
    "give_crystal": _RARITY_POOL,
    "grant_special":  _SPECIAL_BADGE_POOL,
    "revoke_special": _SPECIAL_BADGE_POOL,
}

def _admin_canon_text(op: str, value: str) -> str:
    if op == "set_biome":
        if value.lower() in BIOME_NAMES:
            return value.lower()
        for bid, nm in BIOME_NAMES.items():
            if nm.lower() == value.lower():
                return bid
        return value
    if op == "set_vehicle" and value.lower() in ("none", "-", "remove", "clear"):
        return "None"
    if op in ("grant_special", "revoke_special"):
        return _canon_special_badge(value)
    pool = _ADMIN_TEXT_POOL.get(op)
    if pool:
        for k in pool:
            if k.lower() == value.lower():
                return k
    return value

def _canon_special_badge(value: str) -> str:
    """Resolve a loose badge string ('tester', 'Bug Hunter', 'special_recon') to a
    SPECIAL_BADGES key, or return the input unchanged if nothing matches."""
    norm = value.strip().lower().replace(" ", "_")
    for k, sb in SPECIAL_BADGES.items():
        if norm in (k, k.replace("_badge", ""), sb["label"].lower().replace(" ", "_"),
                    sb["abbr"].lower()):
            return k
    return value

def _admin_validate_text(op: str, value: str) -> str | None:
    if op == "set_biome":
        ok = value.lower() in BIOME_NAMES or value.lower() in {v.lower() for v in BIOME_NAMES.values()}
        if not ok:
            return f"{emoji('cross_mark')} Unknown biome `{value}`. Ids: {', '.join(list(BIOME_NAMES)[:6])}…"
        return None
    if op == "grant_title":
        return None if value else f"{emoji('cross_mark')} Enter a title."
    if op == "set_vehicle" and value.lower() in ("none", "-", "remove", "clear"):
        return None
    if op in ("grant_special", "revoke_special"):
        if _canon_special_badge(value) in SPECIAL_BADGES:
            return None
        names = ", ".join(sb["label"] for sb in SPECIAL_BADGES.values())
        return f"{emoji('cross_mark')} Unknown special badge `{value}`. One of: {names}."
    pool = _ADMIN_TEXT_POOL.get(op)
    if pool and not any(k.lower() == value.lower() for k in pool):
        kind = {"grant_tool": "tool", "set_vehicle": "vehicle", "give_item": "animal",
                "give_ammo": "ammo", "give_crate": "crate", "refund_crates": "crate",
                "give_shard": "rarity", "give_crystal": "rarity"}.get(op, "value")
        sample = ", ".join(list(pool)[:6])
        return f"{emoji('cross_mark')} Unknown {kind} `{value}`. e.g. {sample}…"
    return None

def _admin_text_summary(op: str, target: str, value: str, qty: int) -> str:
    return {
        "set_biome":   f"Move <@{target}> to biome **{BIOME_NAMES.get(value, value)}**.",
        "grant_tool":  f"Grant the tool **{value}** to <@{target}>.",
        "set_vehicle": f"Set <@{target}>'s vehicle to **{value}**.",
        "grant_title": f"Grant the title **{value}** to <@{target}>.",
        "give_item":   f"Add **{qty:,}× {value}** to <@{target}>'s inventory.",
        "give_ammo":   f"Give **{qty:,}× {value}** ammo to <@{target}>.",
        "give_crate":  f"Give **{qty:,}× {value}** to <@{target}>.",
        "refund_crates": f"Refund **{qty:,}× {value}** to <@{target}>.",
        "give_shard":  f"Give **{qty:,}× {value} shard(s)** to <@{target}>.",
        "give_crystal": f"Give **{qty:,}× {value} crystal(s)** to <@{target}>.",
        "grant_special":  f"Grant the special badge **{SPECIAL_BADGES.get(value, {}).get('label', value)}** to <@{target}>.",
        "revoke_special": f"Revoke the special badge **{SPECIAL_BADGES.get(value, {}).get('label', value)}** from <@{target}>.",
    }.get(op, "…")


async def _admin_apply(op: str, params: dict, admin_id: str) -> tuple[str, str]:
    """Execute an admin action. Returns (panel_section, result_banner)."""
    target = params.get("target")
    if target and op != "delete_account":
        init_user(target)
        init_ban_record(target)
    sec = _admin_section_for(op)

    # ── currency: give / take / set money & gems ──
    if op in ("give_money", "take_money", "set_money", "give_gems", "take_gems", "set_gems"):
        amount = params["amount"]
        async with user_transaction(target):
            d = data[target]
            if op == "give_money":
                add_money(target, amount, "admin grant")
                d["total_money_earned"] = d.get("total_money_earned", 0) + amount
                note = f"`💵` Gave **◈ {amount:,}** to <@{target}> (now ◈ {d['money']:,})."
            elif op == "take_money":
                taken = min(amount, d.get("money", 0))
                add_money(target, -taken, "admin remove")
                note = f"`💸` Took **◈ {taken:,}** from <@{target}> (now ◈ {d['money']:,})."
            elif op == "set_money":
                add_money(target, amount - d.get("money", 0), "admin set")
                note = f"`🟰` <@{target}>'s money is now **◈ {amount:,}**."
            elif op == "give_gems":
                add_gems(target, amount, "admin grant")
                note = f"`💎` Gave **{amount:,}** gems to <@{target}> (now {d['gems']:,})."
            elif op == "take_gems":
                taken = min(amount, d.get("gems", 0))
                add_gems(target, -taken, "admin remove")
                note = f"`💎` Took **{taken:,}** gems from <@{target}> (now {d['gems']:,})."
            else:  # set_gems
                add_gems(target, amount - d.get("gems", 0), "admin set")
                note = f"`🟰` <@{target}>'s gems are now **{amount:,}**."
        admin_audit(admin_id, op, f"{target} {amount}")
        return "economy", note

    # ── integer stats: level / prestige / xp / caught / streak / boosts ──
    if op in _ADMIN_INT_OPS:
        val = params["value"]
        async with user_transaction(target):
            d = data[target]
            if op == "set_level":
                d["level"], d["xp"] = val, 0
                note = f"`📈` <@{target}> is now **Level {val:,}**."
            elif op == "set_prestige":
                d["prestige"] = val
                note = f"{emoji('prestige')} <@{target}> is now **Prestige {val:,}**."
            elif op == "set_xp":
                d["xp"] = val
                note = f"`✨` Set <@{target}>'s current-level XP to **{val:,}**."
            elif op == "set_caught":
                d["total_caught"] = val
                note = f"{emoji('target')} Set <@{target}>'s total caught to **{val:,}**."
            elif op == "set_streak":
                d["daily_streak"] = val
                d["best_daily_streak"] = max(d.get("best_daily_streak", 0), val)
                note = f"{emoji('fire')} Set <@{target}>'s daily streak to **{val:,}**."
            else:
                key = {"set_luck": "luck", "set_sell": "sell", "set_xpb": "xp"}[op]
                d.setdefault("boosts", {})[key] = val
                note = f"Set <@{target}>'s personal **{key}** boost to **{val:,}%**."
        admin_audit(admin_id, op, f"{target} -> {val}")
        return sec, note

    # ── text / grants: biome / tool / vehicle / title / items / ammo / crates ──
    if op in _ADMIN_TEXT_OPS:
        value = params["value"]
        qty   = int(params.get("qty", 1))
        async with user_transaction(target):
            d = data[target]
            if op == "set_biome":
                d["biome"] = value
                note = f"{emoji('earth')} Moved <@{target}> to **{BIOME_NAMES.get(value, value)}**."
            elif op == "grant_tool":
                d.setdefault("owned_tools", [])
                if value not in d["owned_tools"]:
                    d["owned_tools"].append(value)
                note = f"`🔧` Granted **{value}** to <@{target}>."
            elif op == "set_vehicle":
                d["vehicle"] = value
                if value != "None":
                    d.setdefault("owned_vehicles", [])
                    if value not in d["owned_vehicles"]:
                        d["owned_vehicles"].append(value)
                note = f"{emoji('jeep')} <@{target}>'s vehicle is now **{value}**."
            elif op == "grant_title":
                d.setdefault("earned_titles", [])
                if value not in d["earned_titles"]:
                    d["earned_titles"].append(value)
                note = f"`🏷️` Granted the title **{value}** to <@{target}>."
            elif op == "grant_special":
                sbl = SPECIAL_BADGES.get(value, {}).get("label", value)
                d.setdefault("special_badges", [])
                if value not in d["special_badges"]:
                    d["special_badges"].append(value)
                note = f"`🎖️` Granted the special badge **{sbl}** to <@{target}>."
            elif op == "revoke_special":
                sbl = SPECIAL_BADGES.get(value, {}).get("label", value)
                d.setdefault("special_badges", [])
                if value in d["special_badges"]:
                    d["special_badges"].remove(value)
                if d.get("featured_badge") == value:
                    d["featured_badge"] = ""
                note = f"`➖` Revoked the special badge **{sbl}** from <@{target}>."
            elif op == "give_item":
                tool = d.get("tool", "Bare Hands")
                for _ in range(qty):
                    d.setdefault("inv", []).append(value)
                    record_catch(target, value, tool, 0)
                note = f"`🐾` Added **{qty:,}× {value}** to <@{target}>'s inventory."
            elif op == "give_ammo":
                inv = d.setdefault("ammo_inv", {})
                inv[value] = min(AMMO_MAX_STACK, inv.get(value, 0) + qty)
                note = f"`🔫` <@{target}> now holds **{inv[value]:,}× {value}**."
            elif op == "give_crate":
                inv = d.setdefault("crate_inv", {})
                inv[value] = inv.get(value, 0) + qty
                note = f"`📦` Gave **{qty:,}× {value}** to <@{target}> (now {inv[value]:,})."
            elif op == "refund_crates":
                inv = d.setdefault("crate_inv", {})
                inv[value] = inv.get(value, 0) + qty
                note = f"`📦` Refunded **{qty:,}× {value}** to <@{target}> (now {inv[value]:,})."
            elif op == "give_shard":
                inv = d.setdefault("shards", {})
                inv[value] = inv.get(value, 0) + qty
                note = f"`💎` Gave **{qty:,}× {value} shard(s)** to <@{target}> (now {inv[value]:,})."
            elif op == "give_crystal":
                inv = d.setdefault("crystals", {})
                inv[value] = inv.get(value, 0) + qty
                note = f"`🔷` Gave **{qty:,}× {value} crystal(s)** to <@{target}> (now {inv[value]:,})."
        admin_audit(admin_id, op, f"{target} {value} x{qty}")
        return sec, note

    # ── uid-only maintenance / state actions ──
    if op == "clearverify":
        async with user_transaction(target):
            v = data[target].setdefault("verify", {})
            v["needed"], v["time"] = False, 250
        admin_audit(admin_id, "clearverify", target)
        return sec, f"{emoji('key')} Cleared the verify lock for <@{target}>."
    if op == "clear_cooldowns":
        async with user_transaction(target):
            data[target]["hunt_cd"] = 0
            data[target]["daily_cd"] = 0
        admin_audit(admin_id, "clear_cooldowns", target)
        return sec, f"{emoji('clock')} Cleared hunt & daily cooldowns for <@{target}>."
    if op == "clear_inventory":
        async with user_transaction(target):
            data[target]["inv"] = []
            data[target]["_pending_sell"] = None   # cached sell value would outlive the animals
        admin_audit(admin_id, "clear_inventory", target)
        return sec, f"{emoji('trash')} Cleared <@{target}>'s animal inventory."
    if op == "clear_crates":
        async with user_transaction(target):
            data[target]["crate_inv"] = {}
        admin_audit(admin_id, "clear_crates", target)
        return sec, f"{emoji('trash')} Cleared <@{target}>'s crates."
    if op == "clear_idle":
        async with user_transaction(target):
            data[target]["idle"] = {"active": False, "stacks": 0, "started_at": 0,
                                    "camp_biome": data[target].get("biome", "village") or "village",
                                    "haul": [], "capacity_upgrades": 0}
        admin_audit(admin_id, "clear_idle", target)
        return sec, f"{emoji('idle_camp')} Reset <@{target}>'s Hunting Camp."
    if op == "grant_all_tools":
        async with user_transaction(target):
            data[target]["owned_tools"] = list(TOOLS.keys())
        admin_audit(admin_id, "grant_all_tools", target)
        return sec, f"`🧰` Gave <@{target}> every tool in the game."
    if op == "max_boosts":
        async with user_transaction(target):
            data[target].setdefault("boosts", {}).update(
                {"luck": ADMIN_MAX_BOOST, "sell": ADMIN_MAX_BOOST, "xp": ADMIN_MAX_BOOST})
        admin_audit(admin_id, "max_boosts", target)
        return sec, f"`🚀` Maxed <@{target}>'s personal luck / sell / XP boosts."
    if op == "toggle_premium":
        async with user_transaction(target):
            new = not data[target].get("premium", False)
            data[target]["premium"] = new
        admin_audit(admin_id, "toggle_premium", f"{target}={new}")
        return sec, f"{emoji('vip')} Premium for <@{target}> is now **{'ON' if new else 'OFF'}**."
    if op == "toggle_tester":
        async with user_transaction(target):
            new = not data[target].get("is_tester", False)
            data[target]["is_tester"] = new
        admin_audit(admin_id, "toggle_tester", f"{target}={new}")
        return sec, (f"`🧪` TESTER flag for <@{target}> is now **{'ON' if new else 'OFF'}**"
                     + (" — hidden from all leaderboards." if new else " — back on the leaderboards."))
    if op == "reset_account":
        init_user(target)
        async with user_transaction(target):
            apply_account_reset(target, prestige=False)
            gems = data[target]["gems"]
        admin_audit(admin_id, "reset_account", target)
        return "danger", (f"`♻️` Reset <@{target}> — gear, level, money, boosts and materials wiped, gems capped at "
                           f"{gems:,}. Prestige count unchanged (no prestige given); badges, titles, tribe and trophies were kept.")
    if op == "delete_account":
        data.pop(target, None)
        _dirty_users.discard(target)
        try:
            await _backend_delete_user(target)
        except Exception as e:
            logger.exception("delete_account backend delete failed")
            return "danger", f"{emoji('warning')} Dropped <@{target}> from memory, but the DB delete failed: {e}"
        admin_audit(admin_id, "delete_account", target)
        return "danger", f"{emoji('trash')} Deleted all stored data for `{target}`. They start fresh if they play again."

    if op == "ban":
        days, reason = params["days"], params["reason"]
        await _apply_ban(target, days, reason, by=admin_id)
        admin_audit(admin_id, "ban", f"{target} days={days} reason={reason!r}")
        dur = f"{days} day(s)" if days > 0 else "permanent"
        return "player", f"`🔨` Banned <@{target}> ({dur})."
    if op == "warn":
        count = await _apply_warn(target, params["reason"], by=admin_id)
        admin_audit(admin_id, "warn", f"{target} reason={params['reason']!r}")
        return "player", f"{emoji('warning')} Warned <@{target}> — now on **{count}** warning(s)."
    if op == "unban":
        async with user_transaction(target):
            data[target].setdefault("ban", {})["active"] = False
        admin_audit(admin_id, "unban", target)
        return "player", f"{emoji('check_mark')} Unbanned <@{target}>."
    if op == "clearwarns":
        async with user_transaction(target):
            data[target]["warnings"] = []
        admin_audit(admin_id, "clearwarns", target)
        return "player", f"`🧹` Cleared all warnings for <@{target}>."
    if op == "wipe_crates":
        touched = 0
        for uid, d in list(data.items()):
            if not (d.get("crate_inv") or d.get("shards") or d.get("crystals") or d.get("craft_queue")):
                continue
            async with user_transaction(uid):
                data[uid]["crate_inv"]   = {}
                data[uid]["shards"]      = {}
                data[uid]["crystals"]    = {}
                data[uid]["craft_queue"] = []
            touched += 1
        admin_audit(admin_id, "wipe_crates", f"players={touched}")
        return "danger", (f"`🧨` Wiped crates, shards, crystals & craft queues for **{touched:,}** "
                          f"player(s). Gemstones untouched.")
    if op == "maint_toggle":
        # Only ever reached to disable now — enabling goes through the
        # maint_enable modal below, since it needs a reason.
        global maintenance_mode, maintenance_warning, maintenance_message
        maintenance_mode    = False
        maintenance_warning = False
        maintenance_message = ""
        save_config()
        admin_audit(admin_id, "maint_toggle", "mode=False")
        bot.loop.create_task(_broadcast_maintenance(False))
        return "maint", f"{emoji('green_ball')} Maintenance mode **disabled** — the bot is open again."

    return _admin_section_for(op), f"{emoji('cross_mark')} Unknown action."

class AdminAmountModal(_V2Modal):
    def __init__(self, admin_id: str, op: str):
        title_txt, amt_label = _ADMIN_AMOUNT_OPS[op]
        super().__init__(title=title_txt)
        self.admin_id = str(admin_id)
        self.op       = op
        placeholder = "whole number" if op in _ADMIN_INT_OPS else "e.g. 500000 or 500k"
        self.uid_in = discord.ui.TextInput(label="Target user ID", placeholder="123456789012345678", max_length=25)
        self.amt_in = discord.ui.TextInput(label=amt_label, placeholder=placeholder, max_length=25)
        self.add_item(self.uid_in)
        self.add_item(self.amt_in)

    async def on_submit(self, interaction: discord.Interaction):
        section = _admin_section_for(self.op)
        target = self.uid_in.value.strip().strip("<@!> ")
        if not target.isdigit():
            await _refresh_admin(interaction, self.admin_id, section, f"{emoji('cross_mark')} Invalid user ID.")
            return

        if self.op in _ADMIN_INT_OPS:
            raw = self.amt_in.value.strip().replace(",", "")
            if not raw.isdigit():
                await _refresh_admin(interaction, self.admin_id, section, f"{emoji('cross_mark')} Enter a whole number.")
                return
            val    = int(raw)
            lo, hi = _ADMIN_INT_RANGE[self.op]
            if not lo <= val <= hi:
                await _refresh_admin(interaction, self.admin_id, section,
                                     f"{emoji('cross_mark')} Value must be between {lo:,} and {hi:,}.")
                return
            await _admin_stage(interaction, self.admin_id, self.op,
                               {"target": target, "value": val},
                               _amount_summary(self.op, target, val))
            return

        amount = parse_amount(self.amt_in.value.strip())
        if amount is None or amount < 0:
            await _refresh_admin(interaction, self.admin_id, section, f"{emoji('cross_mark')} Invalid amount.")
            return
        if self.op in ("give_money", "take_money", "give_gems", "take_gems") and amount <= 0:
            await _refresh_admin(interaction, self.admin_id, section, f"{emoji('cross_mark')} Amount must be positive.")
            return
        if amount > ADMIN_MAX_MONEY:
            await _refresh_admin(interaction, self.admin_id, section,
                                 f"{emoji('cross_mark')} Above the per-action cap of **{ADMIN_MAX_MONEY:,}**.")
            return
        await _admin_stage(interaction, self.admin_id, self.op,
                           {"target": target, "amount": amount},
                           _amount_summary(self.op, target, amount))


class AdminTextModal(_V2Modal):
    def __init__(self, admin_id: str, op: str):
        title, vlabel, vplace, wants_qty = _ADMIN_TEXT_OPS[op]
        super().__init__(title=title)
        self.admin_id  = str(admin_id)
        self.op        = op
        self.wants_qty = wants_qty
        self.uid_in = discord.ui.TextInput(label="Target user ID", placeholder="123456789012345678", max_length=25)
        self.val_in = discord.ui.TextInput(label=vlabel, placeholder=vplace, max_length=100)
        self.add_item(self.uid_in)
        self.add_item(self.val_in)
        if wants_qty:
            self.qty_in = discord.ui.TextInput(label="Quantity", default="1", required=False, max_length=7)
            self.add_item(self.qty_in)

    async def on_submit(self, interaction: discord.Interaction):
        section = _admin_section_for(self.op)
        target = self.uid_in.value.strip().strip("<@!> ")
        if not target.isdigit():
            await _refresh_admin(interaction, self.admin_id, section, f"{emoji('cross_mark')} Invalid user ID.")
            return
        value = self.val_in.value.strip()
        if not value:
            await _refresh_admin(interaction, self.admin_id, section, f"{emoji('cross_mark')} Enter a value.")
            return
        qty = 1
        if self.wants_qty:
            raw = (self.qty_in.value or "1").strip().replace(",", "")
            if not raw.isdigit() or not (1 <= int(raw) <= ADMIN_MAX_GIVE_QTY):
                await _refresh_admin(interaction, self.admin_id, section,
                                     f"{emoji('cross_mark')} Quantity must be a whole number 1–{ADMIN_MAX_GIVE_QTY:,}.")
                return
            qty = int(raw)
        err = _admin_validate_text(self.op, value)
        if err:
            await _refresh_admin(interaction, self.admin_id, section, err)
            return
        value = _admin_canon_text(self.op, value)
        await _admin_stage(interaction, self.admin_id, self.op,
                           {"target": target, "value": value, "qty": qty},
                           _admin_text_summary(self.op, target, value, qty))

class AdminBanModal(_V2Modal, title="🔨 Ban Player"):
    uid_in    = discord.ui.TextInput(label="Target user ID", max_length=25)
    days_in   = discord.ui.TextInput(label="Duration in days (0 = permanent)", default="0", max_length=6)
    reason_in = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, max_length=400)

    def __init__(self, admin_id: str):
        super().__init__()
        self.admin_id = str(admin_id)

    async def on_submit(self, interaction: discord.Interaction):
        target = self.uid_in.value.strip().strip("<@!> ")
        if not target.isdigit():
            await _refresh_admin(interaction, self.admin_id, "player", f"{emoji('cross_mark')} Invalid user ID.")
            return
        raw_days = self.days_in.value.strip() or "0"
        days = max(0, min(int(raw_days) if raw_days.isdigit() else 0, ADMIN_MAX_BAN_DAYS))
        reason = self.reason_in.value.strip()
        dur = f"{days} day(s)" if days > 0 else "permanent"
        await _admin_stage(interaction, self.admin_id, "ban",
                           {"target": target, "days": days, "reason": reason},
                           f"Ban <@{target}> (**{dur}**) — reason: {reason or '—'}")

class AdminWarnModal(_V2Modal, title="⚠️ Warn Player"):
    uid_in    = discord.ui.TextInput(label="Target user ID", max_length=25)
    reason_in = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, max_length=400)

    def __init__(self, admin_id: str):
        super().__init__()
        self.admin_id = str(admin_id)

    async def on_submit(self, interaction: discord.Interaction):
        target = self.uid_in.value.strip().strip("<@!> ")
        if not target.isdigit():
            await _refresh_admin(interaction, self.admin_id, "player", f"{emoji('cross_mark')} Invalid user ID.")
            return
        reason = self.reason_in.value.strip()
        await _admin_stage(interaction, self.admin_id, "warn",
                           {"target": target, "reason": reason},
                           f"Warn <@{target}> — reason: {reason or '—'}")

class AdminUserIdModal(_V2Modal):
    def __init__(self, admin_id: str, op: str):
        super().__init__(title=_ADMIN_UID_OPS.get(op, "Admin"))
        self.admin_id = str(admin_id)
        self.op       = op
        self.uid_in   = discord.ui.TextInput(label="Target user ID", placeholder="123456789012345678", max_length=25)
        self.add_item(self.uid_in)

    async def on_submit(self, interaction: discord.Interaction):
        section = _admin_section_for(self.op)
        target = self.uid_in.value.strip().strip("<@!> ")
        if not target.isdigit():
            await _refresh_admin(interaction, self.admin_id, section, f"{emoji('cross_mark')} Invalid user ID.")
            return

        if self.op == "lookup":
            init_user(target)
            init_ban_record(target)
            d = data[target]
            b = d.get("ban", {})
            ban_line = ("`🔨` Banned" + (f" (until <t:{b['expires_ts']}:R>)" if b.get("expires_ts") else " (permanent)")) \
                       if b.get("active") else f"{emoji('check_mark')} Not banned"
            boosts = d.get("boosts", {})
            note = (
                f"### `🔍` {get_username(target)} (`{target}`)\n"
                f"-# {ban_line}  ·  {(emoji('vip') + ' Premium') if d.get('premium') else 'Free'}\n"
                f"**Level:** {d.get('level', 1):,} (xp {d.get('xp', 0):,})  ·  **Prestige:** {d.get('prestige', 0)}\n"
                f"**Money:** ◈ {d.get('money', 0):,}  ·  **Gems:** `💎` {d.get('gems', 0):,}\n"
                f"**Caught:** {d.get('total_caught', 0):,}  ·  **Streak:** {d.get('daily_streak', 0)}  ·  "
                f"**Biome:** {BIOME_NAMES.get(d.get('biome'), d.get('biome', '—'))}\n"
                f"**Tool:** {d.get('tool', '—')}  ·  **Vehicle:** {d.get('vehicle', '—')}  ·  "
                f"**Tribe:** {d.get('tribe') or '—'}\n"
                f"**Boosts:** `🍀` {boosts.get('luck', 0)}% · `💲` {boosts.get('sell', 0)}% · `📚` {boosts.get('xp', 0)}%\n"
                f"**Inv:** {len(d.get('inv', []))} animals  ·  **Owned tools:** {len(d.get('owned_tools', []))}\n"
                f"**Warnings:** {len(d.get('warnings', []))}  ·  **Joined:** {d.get('joined_date', '—')}"
            )
            await _refresh_admin(interaction, self.admin_id, "player", note)
            return

        summaries = {
            "unban":           f"Unban <@{target}>.",
            "clearwarns":      f"Clear **all** warnings for <@{target}>.",
            "clearverify":     f"Clear the verify lock for <@{target}>.",
            "clear_cooldowns": f"Reset hunt & daily cooldowns for <@{target}>.",
            "clear_inventory": f"Delete <@{target}>'s **entire** animal inventory.",
            "clear_crates":    f"Delete <@{target}>'s **entire** crate inventory.",
            "clear_idle":      f"Reset <@{target}>'s Hunting Camp — clears hired hunters, capacity upgrades and any pending haul.",
            "grant_all_tools": f"Give <@{target}> **every tool** in the game.",
            "max_boosts":      f"Set <@{target}>'s personal luck / sell / XP boosts to the max.",
            "toggle_premium":  f"Toggle premium status for <@{target}>.",
            "toggle_tester":   (f"`🧪` Toggle the **TESTER** flag for <@{target}> — a tester account is "
                                f"hidden from every leaderboard (global, server, personal, rank-loss DMs "
                                f"and the website)."),
            "reset_account":   (f"`♻️` **RESET <@{target}>** — level, money, gear, biome, materials and all boosts "
                                f"are wiped and gems are capped at {RESET_GEM_CAP}. Prestige is NOT changed. "
                                f"Badges, titles, tribe and trophies are kept. Cannot be undone."),
            "delete_account":  (f"{emoji('trash')} **DELETE <@{target}>** — erases their row from the database "
                                f"entirely. If they use the bot again they start from zero. "
                                f"Cannot be undone."),
        }
        await _admin_stage(interaction, self.admin_id, self.op,
                           {"target": target}, summaries.get(self.op, "…"))

class AdminMaintEnableModal(_V2Modal, title="🔧 Enable Maintenance"):
    msg_in = discord.ui.TextInput(label="Reason shown to players", style=discord.TextStyle.paragraph, max_length=400)

    def __init__(self, admin_id: str):
        super().__init__()
        self.admin_id = str(admin_id)

    async def on_submit(self, interaction: discord.Interaction):
        global maintenance_mode, maintenance_message, maintenance_warning
        maintenance_message = self.msg_in.value.strip()
        maintenance_mode    = True
        maintenance_warning = False
        save_config()
        admin_audit(self.admin_id, "maint_toggle", f"mode=True reason={maintenance_message}")
        bot.loop.create_task(_broadcast_maintenance(True))
        await _refresh_admin(interaction, self.admin_id, "maint",
                              f"{emoji('red_ball')} Maintenance mode **enabled** and announced.")

def _admin_modal_for(op: str, admin_id: str):
    if op in _ADMIN_AMOUNT_OPS:
        return AdminAmountModal(admin_id, op)
    if op in _ADMIN_TEXT_OPS:
        return AdminTextModal(admin_id, op)
    if op == "ban":
        return AdminBanModal(admin_id)
    if op == "warn":
        return AdminWarnModal(admin_id)
    if op in _ADMIN_UID_OPS:
        return AdminUserIdModal(admin_id, op)
    if op == "maint_enable":
        return AdminMaintEnableModal(admin_id)
    return None

# ── Shared ban / warn helpers (also used by the /bot ban and /bot warn commands) ──

async def _dm_user_v2(target_id: str, container: list, label: str) -> None:
    """Best-effort DM of a v2 container. Never raises."""
    try:
        _clean_components(container)
        route    = Route("POST", "/users/@me/channels")
        dm_ch    = await bot.http.request(route, json={"recipient_id": str(target_id)})
        dm_route = Route("POST", "/channels/{channel_id}/messages", channel_id=dm_ch["id"])
        await bot.http.request(dm_route, json={
            "flags": V2_FLAGS, "components": container, "allowed_mentions": {"parse": []},
        })
    except Exception as e:
        print(f"{label} DM error for {target_id}:", e)

async def _apply_ban(target_id: str, days: int, reason: str, *, by: str):
    init_user(target_id)
    init_ban_record(target_id)
    now    = int(time.time())
    exp_ts = (now + days * 86400) if days > 0 else 0
    async with user_transaction(target_id):
        data[target_id]["ban"] = {
            "active": True, "reason": reason or "No reason given",
            "expires_ts": exp_ts, "issued_ts": now,
            "appeals_used": 0, "appeals_max": 2, "by": str(by),
        }
    # DM off the critical path so a slow DM API can't blow the 3s ack window.
    bot.loop.create_task(_dm_user_v2(target_id, build_ban_components(target_id), "Ban"))

async def _apply_warn(target_id: str, reason: str, *, by: str) -> int:
    init_user(target_id)
    entry = {"reason": reason or "No reason given", "ts": int(time.time()), "by": str(by)}
    async with user_transaction(target_id):
        data[target_id].setdefault("warnings", []).append(entry)
    count = len(data[target_id]["warnings"])
    body = (
        f"### {emoji('warning')} You have been warned!\n\n"
        f"Reason: {entry['reason']}\n\n"
        f"-# This is warning **#{count}**. Continued violations may result in a ban.\n"
        f"-# Admins will never warn or ban you for no reason."
    )
    bot.loop.create_task(_dm_user_v2(
        target_id,
        [{"type": 17, "accent_color": 0xF39C12, "spoiler": False,
          "components": [{"type": 10, "content": body}]}],
        "Warn",
    ))
    return count

@bot_group.command(name="admin", description="Open the admin control panel")
@app_commands.check(is_admin)
async def admin_cmd(interaction: discord.Interaction):
    admin_id = str(interaction.user.id)
    init_user(admin_id)
    await interaction.response.defer(ephemeral=True)
    await send_v2_followup(interaction, build_admin_panel(admin_id, "home"), ephemeral=True)

bot.tree.add_command(bot_group)

# ─────────────────────────────────────────────
# AUTOSAVE & TASKS
# ─────────────────────────────────────────────

@tasks.loop(seconds=20)
async def autosave_users():
    """Full safety-net save. Per-transaction flushes only write changed rows
    (see _flush_dirty_users); this catches any mutation made outside a
    transaction, so it stays a full write."""
    if data:
        _dirty_users.clear()
        await bulk_save_users(data)
    try:
        await backend.flush_economy_buffer()
    except Exception as e:
        print("economy flush error:", e)
    try:
        await backend.flush_analytics_buffer()
    except Exception as e:
        print("analytics flush error:", e)

@tasks.loop(seconds=20)
async def autosave_tribes():
    """Save tribes to SQLite"""
    if tribe_data:
        await bulk_save_tribes(tribe_data)

_runtime_state_last = ""

@tasks.loop(seconds=5)
async def autosave_runtime_state():
    """Persist the suggestion / report / appeal / blackjack stores when they change."""
    global _runtime_state_last
    if _lock_lost:
        return
    text = json.dumps(_encode_runtime_state(), indent=4, default=str)
    if text != _runtime_state_last:
        _runtime_state_last = text
        await _locked_write(RUNTIME_STATE_FILE, text)

@autosave_users.error
async def _aue(e): print("Autosave users error:", e)

@autosave_tribes.error
async def _ate(e): print("Autosave tribes error:", e)

@autosave_runtime_state.error
async def _arse(e): print("Autosave runtime-state error:", e)

@tasks.loop(seconds=30)
async def lottery_tick():
    global lottery_data
    if time.time() >= lottery_data.get("next_ts", 0):
        await run_lottery_draw()

@lottery_tick.error
async def _lte(error): print("Lottery tick error:", error)

_lock_lost = False

@tasks.loop(hours=24)
async def db_backup_task():
    """Daily consistent snapshot of the SQLite DB (newest 7 kept). Set BACKUP_DIR
    in token.env to put them somewhere other than next to the DB."""
    if _lock_lost or not _data_loaded_ok:
        return
    try:
        path = await backend.backup_database()
        print(f"💾 DB backup written: {path}")
    except Exception as e:
        print(f"⚠️ DB backup failed: {e}")

@db_backup_task.error
async def _dbbe(error): print("DB backup task error:", error)

@tasks.loop(seconds=3)
async def instance_heartbeat():
    """Keep the single-instance lock alive. If another process has taken it over
    (our row is gone), stand down — two instances double every payout."""
    try:
        still_ours = await refresh_instance_lock(INSTANCE_ID)
    except Exception as e:
        print(f"instance heartbeat error: {e}")
        return
    if not still_ours:
        print("=" * 72)
        print("⛔ LOST THE SINGLE-INSTANCE LOCK — another process took over.")
        print("   Shutting this one down to avoid duplicate payouts / DMs.")
        print("   (Saves are disabled: our in-memory data is stale.)")
        print("=" * 72)
        backend.disable_saves()
        global _lock_lost
        _lock_lost = True
        await bot.close()

@instance_heartbeat.error
async def _ihe(error): print("Instance heartbeat error:", error)

async def _dm_user(uid: str, content: str) -> bool:
    """Best-effort DM. Returns False (silently) on closed DMs, unknown user,
    rate limits, etc. — notifications are a nice-to-have, never worth a crash.

    Sent as a v2 container (never a plain-text message) — see `_dm_user_v2`
    for callers that already build their own container."""
    try:
        user = bot.get_user(int(uid)) or await bot.fetch_user(int(uid))
        if not user:
            return False
        container = [{"type": 17, "accent_color": 0x2ECC71, "spoiler": False,
            "components": [{"type": 10, "content": content}]}]
        await _dm_user_v2(uid, container, "notify")
        return True
    except Exception:
        return False

@tasks.loop(minutes=15)
async def daily_reminder_task():
    """DM players (opted in, off by default) once their daily reward is ready."""
    today_str = today_utc()
    for uid, d in list(data.items()):
        if not d.get("notif", {}).get("daily_dm"):
            continue
        if d.get("last_daily_date", "") == today_str:
            continue  # already claimed today
        if d.get("_daily_dm_date") == today_str:
            continue  # already reminded today
        d["_daily_dm_date"] = today_str
        await _dm_user(uid,
            f"## {emoji('daily')} Your daily reward is ready!\n"
            "Use `/daily` in Idle Hunter to claim it.\n"
            f"-# Turn this off any time in `/menu` → Settings.")

@daily_reminder_task.error
async def _drte(error): print("Daily reminder task error:", error)

_lb_top3_cache: dict[str, set] = {}

@tasks.loop(minutes=15)
async def leaderboard_rank_watch_task():
    """DM players (opted in, off by default) when they drop out of the global
    Top 3 on any hunter leaderboard stat."""
    global _lb_top3_cache
    for stat, fn in HUNTER_LB_STATS.items():
        try:
            ranked = sorted((u for u in data.keys() if _lb_eligible(u)),
                            key=lambda u: fn(u), reverse=True)
        except Exception as e:
            print(f"Leaderboard rank watch ({stat}) sort error:", e)
            continue
        top3_now  = set(ranked[:3])
        prev_top3 = _lb_top3_cache.get(stat, set())
        for uid in (prev_top3 - top3_now):
            d = data.get(uid)
            if not d or not d.get("notif", {}).get("leaderboard_dm"):
                continue
            await _dm_user(uid,
                f"## {emoji('leaderboard')} You fell out of the Top 3!\n"
                f"You're no longer in the global Top 3 for **{stat}**.\n"
                "-# Use `/leaderboard` to check your rank, or turn this off in "
                "`/menu` → Settings.")
        _lb_top3_cache[stat] = top3_now

@leaderboard_rank_watch_task.error
async def _lrwte(error): print("Leaderboard rank watch task error:", error)

@tasks.loop(hours=6)
async def world_map_url_refresh_task():
    """Keep the /biomes world-map image URL signed and loading. Discord CDN
    signatures last ~24h, so re-sign well inside that window."""
    await refresh_world_map_url(force=True)

@world_map_url_refresh_task.error
async def _wmurte(error): print("World-map URL refresh task error:", error)

@tasks.loop(minutes=30)
async def tribe_maintenance_task():
    """Promote recruits past probation, roll each tribe's weekly contracts at
    the ISO-week rollover, and keep the level-scaled member cap in sync."""
    if not tribe_data:
        return
    now  = int(time.time())
    cutoff = TRIBE_RECRUIT_PROBATION_H * 3600
    exp_reward_tribes: list[str] = []
    exp_finished: list[tuple[str, bool]] = []   # (tribe name, success) — announced after the lock
    async with tribe_only_transaction():
        for tname, td in list(tribe_data.items()):
            try:
                _ensure_tribe_fields(td)   # also rolls the week when its tag is stale
                promoted = []
                for uid in list(td["roles"].get("recruits", [])):
                    if now - int(td.get("member_since", {}).get(uid, now)) >= cutoff:
                        td["roles"]["recruits"].remove(uid)
                        td["roles"].setdefault("members", []).append(uid)
                        promoted.append(uid)
                for uid in promoted:
                    _tribe_log(td, f"`🎖️` <@{uid}> passed probation — now a full Member.")
                # ── expedition state machine ──
                exp = td.get("expedition")
                if FEATURE_EXPEDITIONS and exp and not exp.get("done"):
                    if exp.get("stage") == "voting" and now >= exp.get("vote_ends_ts", 0):
                        if exp.get("votes"):
                            _exp_lock_route(td)
                        else:
                            exp["done"] = True
                            _tribe_log(td, "`🏕️` Expedition cancelled — nobody voted a route.")
                    elif exp.get("stage") == "active" and (
                            exp.get("progress", 0) >= exp.get("goal", 1)
                            or now >= exp.get("ends_ts", 0)):
                        _exp_finish(td, tname)   # → stage 'rewarding' (or done, on fail)
                        exp_finished.append((tname, bool(exp.get("success"))))
                    if exp.get("stage") == "rewarding" and not exp.get("done"):
                        exp_reward_tribes.append(tname)
            except Exception as e:
                print(f"tribe_maintenance_task error for {tname}:", e)

    # Distribute expedition rewards outside the tribe-only lock so each recipient
    # is locked properly. Crash-safe + idempotent (see _exp_pay_out).
    for tname in dict.fromkeys(exp_reward_tribes):
        try:
            await _exp_pay_out(tname)
        except Exception as e:
            print(f"expedition pay-out failed for {tname}:", e)

    for tname, success in exp_finished:
        try:
            await _broadcast_expedition_result(tname, success)
        except Exception as e:
            print(f"expedition result announcement failed for {tname}:", e)

@tribe_maintenance_task.error
async def _tmte(error): print("Tribe maintenance task error:", error)

@tasks.loop(minutes=10)
async def world_condition_task():
    """Expire finished world conditions and top the world back up to
    WORLD_CONDITION_SLOTS enhanced regions. Conditions last 3-4h, so they age
    out on their own — this only fills empty slots."""
    if not FEATURE_WORLD_CONDITIONS:
        return
    try:
        changed = rotate_world_conditions()
        if changed:
            names = ", ".join(BIOME_NAMES.get(b, b) for b in changed)
            print(f"🌦️  New world condition(s): {names}")
            if len(changed) == 1:
                b = changed[0]
                c = _world_conditions.get(b, {})
                spec = WORLD_CONDITIONS.get(c.get("key", ""), {})
                fx = []
                if spec.get("rare_mult", 1) > 1: fx.append(f"{emoji('rarity_rare')} Rare +{round((spec['rare_mult']-1)*100)}%")
                if spec.get("myth_mult", 1) > 1: fx.append(f"{emoji('rarity_mythic')} Mythic +{round((spec['myth_mult']-1)*100)}%")
                if spec.get("sell_mult", 1) > 1: fx.append(f"{emoji('sell_boost')} Sell +{round((spec['sell_mult']-1)*100)}%")
                if spec.get("xp_mult",   1) > 1: fx.append(f"{emoji('xp_boost')} XP +{round((spec['xp_mult']-1)*100)}%")
                body = announce_card(
                    "condition", spec.get("emoji", "🌦️"), spec.get("name", "?"),
                    subtitle=BIOME_NAMES.get(b, b), flavor=spec.get("blurb", ""),
                    actions=fx, ends_ts=c.get("ends_ts"),
                )
                buttons = [{"type": 2, "style": 3, "label": "Travel Now",
                            "emoji": emoji_partial("plane"), "custom_id": f"announce:travel:{b}"}]
            else:
                lines = []
                for b in changed:
                    c = _world_conditions.get(b, {})
                    spec = WORLD_CONDITIONS.get(c.get("key", ""), {})
                    lines.append(
                        f"{spec.get('emoji', '🌦️')} **{BIOME_NAMES.get(b, b)}** — "
                        f"{spec.get('name', '?')} (ends <t:{int(c.get('ends_ts', 0))}:R>)"
                    )
                body = announce_card(
                    "condition", "`🌦️`", "Multiple Regions Shifted",
                    flavor="\n".join(lines),
                )
                buttons = None
            await _announce(body, channel_id=ALERTS_CHANNEL_ID, role_id=WORLD_EVENT_ROLE_ID,
                             color=0x3498DB, buttons=buttons)
    except Exception as e:
        print("world_condition_task error:", e)

@world_condition_task.error
async def _wcte(error): print("World condition task error:", error)

_sighting_announced: dict[str, str] = {}   # sighting id -> last stage announced

def _sighting_progress_body(sg: dict) -> str:
    """The in-progress (unrevealed) card — one EDITED message that updates as
    clues come in, instead of a new post every tick."""
    where = BIOME_NAMES.get(sg["biome"], sg["biome"])
    clues = sg.get("clues", 0)
    flavor_line = sg.get("_clue_flavor") or ""
    extra = f"Recent clue:\n> {flavor_line}" if flavor_line else ""
    return announce_card(
        "sighting", "❓", "UNKNOWN CREATURE SIGHTED", subtitle=where,
        flavor=f"Something enormous is moving through {where}. Its identity is still unknown.",
        actions=[f"{emoji('bow')} Hunt in {where} to uncover clues"],
        progress_label="Clues discovered",
        progress_current=clues, progress_target=SIGHTING_CLUE_GOAL,
        extra=extra,
    )

def _sighting_reveal_body(sg: dict) -> str:
    """The one dramatic beat in the whole announcement system — a real story
    moment, not a stat update. Deliberately its own layout rather than the
    generic announce_card formula."""
    where    = BIOME_NAMES.get(sg["biome"], sg["biome"])
    name     = sg["creature"]
    ico      = creature_emoji(name)
    c        = MYTHIC_CREATURES.get(name, {})
    window_h = SIGHTING_ENCOUNTER_WINDOW_MIN // 60
    return (
        f"## {emoji('warning')} IDENTITY REVEALED\n"
        f"### {ph(emoji('earth'))} {where}\n\n"
        f"The tracks belong to...\n\n"
        f"# {ico} {name.upper()}\n\n"
        f"**FIRST-KILL BOUNTY**\n"
        f"◈ {MYTH_FIRST_KILL_BOUNTY:,}\n"
        f"{emoji('gem')} {MYTH_FIRST_KILL_GEMS:,}\n"
        f"{emoji('trophy')} {c.get('drop', 'Unique Trophy')}\n\n"
        f"`⚔️` Hunters in **{where}** may now encounter it.\n"
        f"`⏳` Available for the next {window_h}h."
    )

@tasks.loop(minutes=8)
async def world_sighting_task():
    """Spawn / reveal / retire the single global sighting and announce each
    stage. The in-progress card is EDITED in place as clues come in (one
    message, updated) instead of spamming a new post every tick; the reveal
    replaces it with one dramatic beat rather than posting yet another card."""
    if not FEATURE_WORLD_SIGHTINGS:
        return
    try:
        sg = get_active_sighting()
        if not sg:
            # ~35% chance each tick once the cooldown has passed
            if random.random() < 0.35:
                sg = spawn_world_sighting()
                if sg:
                    _sighting_announced[sg["id"]] = "spawned"
                    analytics(None, "sighting_spawned", biome=sg["biome"], creature=sg["creature"])
                    resp = await _announce(
                        _sighting_progress_body(sg),
                        channel_id=ALERTS_CHANNEL_ID, role_id=SIGHTING_ROLE_ID, color=0xE74C3C,
                        thumb_url=_emoji_cdn_url(BIOME_EMOJIS.get(sg["biome"])))
                    if resp:
                        sg["channel_id"] = ALERTS_CHANNEL_ID
                        sg["msg_id"] = resp.get("id")
                    sg["last_clues_announced"] = 0
            return

        if not sg.get("revealed"):
            # Edit the existing card in place whenever the clue count moved.
            if sg.get("msg_id") and sg.get("clues", 0) != sg.get("last_clues_announced", -1):
                sg["_clue_flavor"] = random.choice(SIGHTING_CLUE_FLAVORS)
                ok = await _announce_edit(sg["channel_id"], sg["msg_id"],
                                           _sighting_progress_body(sg), 0xE74C3C,
                                           thumb_url=_emoji_cdn_url(BIOME_EMOJIS.get(sg["biome"])))
                if ok:
                    sg["last_clues_announced"] = sg.get("clues", 0)
            return

        if _sighting_announced.get(sg["id"]) != "revealed":
            _sighting_announced[sg["id"]] = "revealed"
            analytics(None, "sighting_revealed", biome=sg["biome"], creature=sg["creature"])
            body = _sighting_reveal_body(sg)
            buttons = [{"type": 2, "style": 3, "label": f"Travel to {BIOME_NAMES.get(sg['biome'], sg['biome'])}",
                        "emoji": emoji_partial("plane"), "custom_id": f"announce:travel:{sg['biome']}"}]
            edited = False
            if sg.get("msg_id"):
                edited = await _announce_edit(sg["channel_id"], sg["msg_id"], body, 0x9B59B6, buttons)
            if edited:
                # An edit never notifies anyone — this IS the biggest moment
                # in the whole system, so it still gets a fresh ping, just a
                # short one pointing back at the card that just transformed.
                ch = bot.get_channel(sg["channel_id"])
                if ch is None:
                    try:
                        ch = await bot.fetch_channel(sg["channel_id"])
                    except Exception:
                        ch = None
                if ch is not None:
                    try:
                        _ico = creature_emoji(sg["creature"]) or "🚨"
                        route = Route("POST", "/channels/{channel_id}/messages", channel_id=sg["channel_id"])
                        await bot.http.request(route, json={
                            "flags": V2_FLAGS,
                            "components": [{"type": 10, "content":
                                f"<@&{SIGHTING_ROLE_ID}> {_ico} **The sighting has been identified.** `⬆️`"}],
                            "allowed_mentions": {"roles": [str(SIGHTING_ROLE_ID)]},
                        })
                    except Exception as e:
                        print("sighting reveal ping failed:", e)
            else:
                await _announce(body, channel_id=ALERTS_CHANNEL_ID, role_id=SIGHTING_ROLE_ID,
                                 color=0x9B59B6, buttons=buttons)
    except Exception as e:
        print("world_sighting_task error:", e)

@world_sighting_task.error
async def _wste(error): print("World sighting task error:", error)

_last_weekly_lb_tag: str = ""

def _weekly_leaderboard_recap_text(new_tag: str) -> str:
    """Final standings for the week that just ended, from each player's
    'weekly' leaderboard snapshot (the same lazy baseline /leaderboard's
    weekly tab uses) — read BEFORE it gets rebased to the new week below.
    Redesigned 2026-09-15 to spotlight the #1 earner as the headline instead
    of a flat five-line list with no hierarchy."""
    rows = []
    for uid, d in data.items():
        if not _lb_eligible(uid):
            continue
        snap = d.get("lb_snap", {}).get("weekly")
        if not snap or snap.get("tag") == new_tag:
            continue   # no baseline for the week that just ended
        gained = max(0, HUNTER_LB_STATS["Money"](uid) - snap.get("Money", 0))
        if gained > 0:
            rows.append((uid, gained))
    rows.sort(key=lambda r: r[1], reverse=True)
    if not rows:
        return announce_card("result", emoji('trophy'), "Weekly Leaderboard", subtitle="Top Earner",
                              flavor="No qualifying activity was recorded last week.")
    winner_uid, winner_gained = rows[0]
    medals = {1: f"{emoji('second_place_medal')}", 2: f"{emoji('third_place_medal')}"}
    runner_ups = [
        f"{medals.get(i, f'#{i+1}')} `{get_username(uid)}`{featured_badge_suffix(uid)} — {ui_money(gained)}"
        for i, (uid, gained) in enumerate(rows[1:5], start=1)
    ]
    return announce_card(
        "result", emoji('trophy'), f"{get_username(winner_uid)}{featured_badge_suffix(winner_uid)}",
        subtitle="Top Earner This Week",
        flavor=f"Made {ui_money(winner_gained)} more than anyone else this week.",
        actions=runner_ups,
    )

@tasks.loop(minutes=30)
async def weekly_leaderboard_task():
    """Post a Money-earned recap once per ISO week and re-seed every player's
    weekly snapshot right at the rollover, so next week's recap is complete
    even for players who never opened /leaderboard."""
    global _last_weekly_lb_tag
    try:
        tag = _week_tag()
        if tag == _last_weekly_lb_tag:
            return
        text = _weekly_leaderboard_recap_text(tag)
        for uid, d in data.items():
            d.setdefault("lb_snap", {})["weekly"] = {
                "tag": tag, **{s: fn(uid) for s, fn in HUNTER_LB_STATS.items()}
            }
            mark_user_dirty(uid)
        _last_weekly_lb_tag = tag
        await _announce(text, channel_id=COMPETITIVE_CHANNEL_ID, role_id=COMPETITIVE_ROLE_ID, color=0xF1C40F,
                         buttons=[{"type": 2, "style": 1, "label": "View Leaderboard",
                                   "emoji": emoji_partial('trophy'), "custom_id": "announce:leaderboard:open"}])
    except Exception as e:
        print("weekly_leaderboard_task error:", e)

@weekly_leaderboard_task.error
async def _wlte(error): print("Weekly leaderboard task error:", error)

@tasks.loop(minutes=15)
async def automatic_event_scheduler():
    """Occasionally start a community/activity event on its own. Opt-in
    (FEATURE_AUTO_EVENTS). Aims for ~2-3 events/week, never back-to-back repeats."""
    if not FEATURE_AUTO_EVENTS:
        return
    try:
        if get_active_event():
            return
        now = time.time()
        if now < _event_scheduler.get("next_event_ts", 0):
            return
        # small per-tick chance so start time isn't perfectly predictable
        if _event_scheduler.get("last_event_ts", 0) and random.random() > 0.25:
            return
        recent = _event_scheduler.get("recent_keys", [])[-2:]
        pool = [k for k, s in EVENTS.items()
                if s.get("kind") != "buff" and k not in recent]
        if not pool:
            pool = [k for k, s in EVENTS.items() if s.get("kind") != "buff"]
        key = random.choice(pool)
        ev = start_event(key, "system", automatic=True)
        if not ev:
            return
        _event_scheduler["last_event_ts"] = now
        _event_scheduler["next_event_ts"] = now + random.randint(48, 96) * 3600
        _event_scheduler["recent_keys"] = (recent + [key])[-3:]
        analytics(None, "auto_event_started", key=key)
        await _broadcast_event_start(ev)
    except Exception as e:
        print("automatic_event_scheduler error:", e)

@automatic_event_scheduler.error
async def _aese(error): print("Automatic event scheduler error:", error)

if FEATURE_WORLD_SIGHTINGS:
    _V2_BACKGROUND_TASKS.append(world_sighting_task)
if FEATURE_AUTO_EVENTS:
    _V2_BACKGROUND_TASKS.append(automatic_event_scheduler)
_V2_BACKGROUND_TASKS.append(weekly_leaderboard_task)

@tasks.loop(hours=24)
async def analytics_prune_task():
    """Keep the analytics table bounded — drop rows older than 120 days."""
    try:
        removed = await backend.prune_analytics(120)
        if removed:
            print(f"🧹 Pruned {removed} old analytics rows.")
    except Exception as e:
        print("analytics prune error:", e)

@analytics_prune_task.error
async def _apte(error): print("Analytics prune task error:", error)

# ─────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────

_ready_once = False
# Discord can start delivering interactions as soon as the gateway connects —
# it does NOT wait for on_ready to finish. If a slash command lands before
# load_all_data() has populated `data` from SQLite, _common_init's init_user()
# sees an empty dict, decides the player is brand new, and hands back a
# fresh default record (level 1, Bare Hands, no ammo, no boosts) instead of
# their real save — a real account looking wiped for exactly one unlucky
# command, right after every restart. Gate every interaction on this instead.
_data_loaded_ok = False

@bot.event
async def on_ready():
    global _ready_once, _data_loaded_ok
    print(f"Logged in as {bot.user}  [INSTANCE_ID={INSTANCE_ID}]")

    # on_ready fires again on every gateway RESUME/reconnect. The DB open + data
    # load below must happen exactly once per process — re-running them leaks the
    # old aiosqlite connection and reloads the DB over in-memory state that may
    # hold unsaved changes.
    if _ready_once:
        print("on_ready re-fired (reconnect) — init already done, skipping.")
        return
    _ready_once = True

    # Initialize SQLite and load data
    try:
        await init_databases()
        print("✅ Database initialized")
    except Exception as e:
        _ready_once = False
        print(f"❌ Database init failed: {e}")
        return

    # ── Single-instance guard ────────────────────────────────────────────
    # Two bot processes on one token double every payout / DM / verify code.
    # Fail CLOSED: if we can't even verify the lock (DB hiccup, etc.), refuse
    # to start rather than assume we're safe — that's exactly the moment a
    # second instance could already be live. Set ALLOW_UNSAFE_START=1 to
    # force a start anyway (e.g. a known-solo dev box with a flaky DB).
    try:
        _ok, _holder = await claim_instance_lock(
            INSTANCE_ID, _socket.gethostname(), os.getpid())
    except Exception as e:
        if os.environ.get("ALLOW_UNSAFE_START") == "1":
            print(f"⚠️ instance-lock check failed ({e}) — "
                  f"ALLOW_UNSAFE_START=1 set, continuing without it.")
            _ok, _holder = True, None
        else:
            print("=" * 72)
            print(f"⛔ INSTANCE-LOCK CHECK FAILED ({e}) — refusing to start.")
            print("   Starting anyway could run two instances and double every")
            print("   payout, DM and verify code. Fix the DB/lock issue, or set")
            print("   ALLOW_UNSAFE_START=1 to override.")
            print("=" * 72)
            backend.disable_saves()
            await bot.close()
            return
    if not _ok:
        print("=" * 72)
        print("⛔ ANOTHER BOT INSTANCE IS ALREADY RUNNING — this process will exit.")
        if _holder:
            print(f"   Lock held by {_holder['instance_id']} "
                  f"(host {_holder['hostname']}, pid {_holder['pid']}, "
                  f"heartbeat {_holder['age_s']}s ago)")
        print("   Running two instances doubles payouts, DMs and verify codes.")
        print("   Fix the host to run exactly ONE process, then restart.")
        print("=" * 72)
        # leave _ready_once = True: a gateway reconnect must not re-run init here.
        backend.disable_saves()
        await bot.close()
        return
    print(f"🔒 Instance lock acquired  [{INSTANCE_ID}]")

    await migrate_json_to_sqlite()

    try:
        await load_all_data()
        _data_loaded_ok = True
        print("✅ Data loaded")
    except Exception as e:
        print(f"❌ Data load failed: {e}")
        # We already hold the instance lock and an open DB connection at this
        # point. Resetting _ready_once and returning would let a gateway
        # RESUME re-run this whole function from the top — re-opening the DB
        # (leaking the old connection) while this process still holds the
        # lock, and with _data_loaded_ok never set, every interaction would
        # be stuck on "Still Starting Up" forever. Clean up and stop instead;
        # the process manager should restart us fresh.
        try:
            await release_instance_lock(INSTANCE_ID)
        except Exception as e2:
            print(f"   (also failed to release instance lock: {e2})")
        try:
            await close_databases()
        except Exception as e2:
            print(f"   (also failed to close databases: {e2})")
        await bot.close()
        return

    load_runtime_state()

    # Make sure the world is never empty on boot (Idle Hunter V2).
    if FEATURE_WORLD_CONDITIONS:
        try:
            rotate_world_conditions(force_fill=True)
        except Exception as e:
            print("initial world-condition fill failed:", e)

    # Let the transaction managers snapshot / roll back the live state dicts.
    register_state_refs(data, tribe_data)

    # Transaction flushes now write only the users changed since the last
    # flush, and are awaited by the transaction managers themselves — so the
    # write has actually landed in SQLite before the transaction (and any
    # Discord reply built on its result) completes. A fire-and-forget
    # asyncio.create_task() here would let the process crash between "the
    # player got their response" and "the row was actually written".
    async def _flush_dirty_users():
        if not _dirty_users:
            return
        batch_ids = [uid for uid in list(_dirty_users) if uid in data]
        _dirty_users.clear()
        if not batch_ids:
            return
        batch = {uid: data[uid] for uid in batch_ids}
        try:
            await bulk_save_users(batch)
        except Exception as e:
            # The write failed — put the markers back so the next flush (or
            # the 20s full autosave) retries instead of silently dropping them.
            for uid in batch_ids:
                _dirty_users.add(uid)
            print(f"incremental user save failed, re-queued {len(batch_ids)}: {e}")

    async def _flush_tribes_cb():
        await bulk_save_tribes(tribe_data)

    register_save_callbacks(_flush_dirty_users, _flush_tribes_cb)

    try:
        synced = await bot.tree.sync()
        # Keep COMMAND_ID (used for clickable </cmd:id> mentions) current — the
        # hardcoded game_data table misses newer commands otherwise.
        for _sc in synced:
            COMMAND_ID[_sc.name] = str(_sc.id)
        print(f"Synced {len(synced)} commands  [INSTANCE_ID={INSTANCE_ID}]")
    except Exception as e:
        print("Sync failed:", e)

    await asyncio.to_thread(test_token, BOT_TOKEN, "Main bot")

    await bot.change_presence(activity=discord.Game(name="/menu | Idle Hunter"))

    # Which custom emoji can the bot actually use in component `emoji` fields?
    # (guild emoji from every server it's in, plus its own application emoji)
    try:
        _usable_emoji_ids.update(str(e.id) for e in bot.emojis)
        _named_emojis = {e.name: str(e) for e in bot.emojis}
        try:
            for _ae in await bot.fetch_application_emojis():
                _usable_emoji_ids.add(str(_ae.id))
                _named_emojis[_ae.name] = str(_ae)
        except Exception:
            pass
        # Registry keys still on a unicode placeholder switch to an uploaded emoji
        # of the same name (name it exactly like the key, e.g. `heart`).
        _adopted = adopt_named_emojis(_named_emojis)
        if _adopted:
            print(f"🎨 Adopted {len(_adopted)} uploaded emoji by name: {sorted(_adopted)[:20]}"
                  + (" …" if len(_adopted) > 20 else ""))
        _missing = sorted({
            eid for k in EMOJI
            if (eid := emoji_partial(k).get("id")) and eid not in _usable_emoji_ids
        })
        if _missing:
            print(f"⚠️ {len(_missing)} registry emoji not usable by the bot "
                  f"(re-upload to a bot server or as app emoji): {_missing[:12]}"
                  + (" …" if len(_missing) > 12 else ""))
    except Exception as e:
        print("emoji usability scan failed:", e)

    if not instance_heartbeat.is_running():      instance_heartbeat.start()
    if not autosave_users.is_running():         autosave_users.start()
    if not autosave_tribes.is_running():        autosave_tribes.start()
    if not autosave_runtime_state.is_running(): autosave_runtime_state.start()
    if not lottery_tick.is_running():           lottery_tick.start()
    if not daily_reminder_task.is_running():    daily_reminder_task.start()
    if not leaderboard_rank_watch_task.is_running(): leaderboard_rank_watch_task.start()
    if not world_map_url_refresh_task.is_running(): world_map_url_refresh_task.start()
    if not tribe_maintenance_task.is_running(): tribe_maintenance_task.start()
    if not analytics_prune_task.is_running():   analytics_prune_task.start()
    if not db_backup_task.is_running():         db_backup_task.start()
    if FEATURE_WORLD_CONDITIONS and not world_condition_task.is_running():
        world_condition_task.start()
    for _v2task in _V2_BACKGROUND_TASKS:
        try:
            if not _v2task.is_running():
                _v2task.start()
        except Exception as e:
            print(f"V2 task start failed ({_v2task}):", e)

    # Optional public-website leaderboard push (no-op unless LEADERBOARD_URL +
    # LEADERBOARD_PUSH_TOKEN are set in token.env). Only public names + scores.
    global _lb_publisher
    if _lb_publisher is None:
        try:
            from leaderboard_push import LeaderboardPublisher
            _lb_publisher = LeaderboardPublisher(lambda: data, lambda: tribe_data,
                                                _v2_public_world_state)
            _lb_publisher.start()
        except Exception as e:
            print("Leaderboard publisher not started:", e)

    global _username_sweep_started
    if not _username_sweep_started:
        _username_sweep_started = True
        bot.loop.create_task(_username_backfill_sweep())

    print("Autosave started.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        msg = f"{emoji('lock')} You don't have permission to use that command."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"{emoji('cooldown')} That command is on cooldown — try again in {error.retry_after:.0f}s."
    else:
        logger.exception("app command error", exc_info=error)
        msg = f"{emoji('warning')} Something went wrong running that command. Please try again."
    try:
        await send_ephemeral_v2(interaction, msg, 0xE74C3C)
    except Exception:
        pass

# ─────────────────────────────────────────────
# GRACEFUL SHUTDOWN
# ─────────────────────────────────────────────

_bot_close_orig = bot.close

async def _graceful_close():
    """Final save + clean DB close. discord.py calls Client.close() from the
    bot.run() finally block on SIGINT/SIGTERM, so this runs on every shutdown."""
    print("Shutting down — flushing final state...")
    try:
        if _lb_publisher is not None:
            await _lb_publisher.stop()
    except Exception as e:
        print(f"  leaderboard publisher stop failed: {e}")
    try:
        if data:
            await bulk_save_users(data)
        if tribe_data:
            await bulk_save_tribes(tribe_data)
        _dirty_users.clear()
    except Exception as e:
        print(f"  final user/tribe save failed: {e}")
    try:
        if not _lock_lost:
            text = json.dumps(_encode_runtime_state(), indent=4, default=str)
            await _locked_write(RUNTIME_STATE_FILE, text)
    except Exception as e:
        print(f"  runtime-state save failed: {e}")
    try:
        await backend.flush_economy_buffer()
    except Exception as e:
        print(f"  economy-buffer flush failed: {e}")
    try:
        await backend.flush_analytics_buffer()
    except Exception as e:
        print(f"  analytics-buffer flush failed: {e}")
    try:
        await release_instance_lock(INSTANCE_ID)
    except Exception as e:
        print(f"  instance-lock release failed: {e}")
    try:
        await close_databases()
        print("  database closed cleanly.")
    except Exception as e:
        print(f"  database close failed: {e}")
    await _bot_close_orig()

bot.close = _graceful_close

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

bot.run(BOT_TOKEN)
