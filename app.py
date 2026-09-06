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
    # Animals
    ANIMAL_DATA, ANIMAL_EMOJI, animal_emoji,
    # Tools
    TOOLS, get_tool_tier, can_hunt_biome, get_all_tools_sorted,
    tool_needs_ammo, get_tool_ammo_type, ammo_compatible_with_tool,
    # Ammo
    AMMO, AMMO_TYPE_TOOLS, AMMO_TYPE_LABELS, AMMO_MAX_STACK,
    # Vehicles
    VEHICLES,
    # Shop
    SHOP_BOOST_ITEMS,
    # Daily
    DAILY_TIERS, get_daily_tier,
    # Colors
    COLORS, COLOR_LABELS, COLOR_EMOJIS, COLOR_DESCRIPTIONS, color_display_name,
    # XP
    xp_for_level, total_xp_to_level,
    # Gamble
    ROULETTE_COLORS, ROULETTE_WEIGHTS, ROULETTE_BET_TYPES, RPS_CHOICES, RPS_BEATS, SLOT_BIOME_CONFIG,
    # Rarity icons
    RARITY_ICONS,
    # Emojis
    UPGRADE_EMOJI, TRIBE_EMOJIS, USER_EMOJIS, EMOJI, emoji, emoji_partial,
    # Tips
    TIPS,
    # Commands
    COMMAND_ID,
    # Badges
    BADGES,
    # Achievements
    ACHIEVEMENTS, ACHIEVEMENT_TITLES,
    # Helpers
    today_utc, parse_amount, generate_verify_code, init_verify,
    # Rules
    RULES,
    # Hunting Crates
    CRATE_TIERS, CRATE_REWARDS, open_crate, roll_hunt_crate_drop,
    # Quests
    QUEST_TEMPLATES, QUEST_TIERS, QUESTS_PER_DAY, QUESTS_MAX,
    generate_quest, roll_daily_quests, get_quest_tier,
)
import backend
from contextlib import asynccontextmanager
from backend import (
    init_databases, close_databases, get_user, save_user, bulk_save_users,
    delete_user as _backend_delete_user,
    bulk_save_tribes, get_tribe, save_tribe, register_save_callbacks,
    user_transaction as _backend_user_transaction,
    user_tribe_transaction as _backend_user_tribe_transaction,
    multi_user_transaction as _backend_multi_user_transaction,
    tribe_only_transaction, migrate_all_users,
    log_economy_event, SessionManager, RateLimiter,
    # Also import these if you need them:
    CURRENT_SCHEMA, User, Tribe, TribeRoles, VerifyState, Boosts, IdleState,
    Stats, BanRecord, AnimalRecord, AchievementProgress, BadgeState, GiftMail,
    ECONOMY_LOG,
    get_user_lock, tribe_lock, state_lock
)
from dotenv import load_dotenv
import os, csv
load_dotenv("token.env")


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
intents.message_content = True
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
IDLE_COST             = 5_000
IDLE_STACK_MULTIPLIER = 2
HUNT_COOLDOWN         = 3
PRESTIGE_MIN_LEVEL    = 1000
PRESTIGE_MIN_MONEY    = 1_000_000_000
MAX_LOG_ENTRIES       = 50
INV_DISPLAY_MAX       = 10
AMMO_MAX_STACK        = 9_999
LOTTERY_TICKET_COST   = 10_000
GAMBLE_COOLDOWN       = 0
V2_FLAGS              = 32768
SUGGESTION_CHANNEL_ID = 1503581602234765322
BAN_APPEAL_CHANNEL_ID = 1503975028570718298
REPORTS_CHANNEL_ID    = 1503975073797771284
LOTTERY_CHANNEL_ID    = 1505064052391673958

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
async def user_tribe_transaction(user_id):
    mark_user_dirty(user_id)
    async with _backend_user_tribe_transaction(str(user_id)):
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
    
    print(f"✅ Loaded {len(data)} users and {len(tribe_data)} tribes from SQLite")

# ─────────────────────────────────────────────
# NON-BLOCKING FILE WRITES
# ─────────────────────────────────────────────

_file_write_lock: asyncio.Lock | None = None

def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

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
    else:
        print("⚠️ users_info.json not found")

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
    else:
        print("⚠️ tribe_info.json not found")

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

# Register save callbacks (will be re-registered in on_ready after DB init)
# For now, placeholder callbacks that do nothing until real ones are set
register_save_callbacks(lambda: None, lambda: None)

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
        "money": 10000, "level": 1, "xp": 0, "inv": [], "_pending_sell": None,
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
    }
    if user_id not in data:
        data[user_id] = dict(defaults)
    else:
        for k, v in defaults.items():
            if k not in data[user_id]:
                data[user_id][k] = v

    data[user_id].setdefault("achievements", {})
    data[user_id].setdefault("badges", {})
    data[user_id].setdefault("earned_titles", [])
    data[user_id].setdefault("equipped_title", None)
    data[user_id].setdefault("stats", {})
    data[user_id]["stats"].setdefault("crates_opened", 0)
    data[user_id].setdefault("quests", [])
    data[user_id].setdefault("quests_last_roll", "")   # ISO date of last daily roll
    data[user_id].setdefault("temp_boosts", [])

    for k, v in {
        "ammo_used": 0, "lottery_wins": 0, "tools_used": [], "events_completed": 0,
        "total_xp_earned": 0, "bj_wins": 0, "cf_wins": 0, "rl_wins": 0,
        "rps_wins": 0, "slots_wins": 0,
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
    if "equipped_ammo" not in data[user_id]:
        data[user_id]["equipped_ammo"] = None
    if "Bare Hands" not in data[user_id].get("owned_tools", []):
        data[user_id].setdefault("owned_tools", []).insert(0, "Bare Hands")

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
            "roles": {"leader": user_id, "officer": [], "members": []},
            "banned": [], "level": 1, "xp": 0, "invites": [],
            "premium": False, "max_members": 5,
            "luck_boost": 0, "sell_price_boost": 0, "xp_boost": 0,
        }
        data[user_id]["tribe"] = tribe_name
    for k, v in {
        "description": None, "creator": user_id,
        "roles": {"leader": user_id, "officer": [], "members": []},
        "banned": [], "level": 1, "xp": 0, "invites": [],
        "premium": False, "max_members": 5,
        "luck_boost": 0, "sell_price_boost": 0, "xp_boost": 0,
    }.items():
        tribe_data[tribe_name].setdefault(k, v)

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
    return None

async def _tribe_perm(interaction, user_id: str, tribe_name: str,
                      allowed: tuple = ("leader", "officer")) -> bool:
    """Re-check the user's *current* tribe role right before a mutation. Sends an
    ephemeral and returns False when they no longer qualify."""
    if tribe_role_of(user_id, tribe_name) not in allowed:
        await send_ephemeral_v2(
            interaction,
            "❌ You no longer have permission to do that in this tribe.",
            0xE74C3C,
        )
        return False
    return True

def add_money(user_id: str, amount: int, source: str) -> None:
    data[user_id]["money"] += amount
    mark_user_dirty(user_id)
    if amount != 0:
        log_economy_event(user_id, source, amount, data[user_id]["money"])

def spend_money(user_id: str, amount: int, source: str) -> bool:
    if data[user_id]["money"] < amount:
        return False
    data[user_id]["money"] -= amount
    mark_user_dirty(user_id)
    log_economy_event(user_id, source, -amount, data[user_id]["money"])
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
    price = int(price)
    if currency == "gems":
        if not spend_gems(user_id, price, source):
            return False, f"❌ You need {emoji('gem')} {price:,} for that."
    else:
        if not spend_money(user_id, price, source):
            return False, f"❌ You need ◈ {price:,} for that."
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

def get_prestige_boost(user_id: str) -> int:
    return data[user_id].get("prestige", 0) * 20

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
    total_luck   = personal.get("luck", 0) + t_luck + prestige_b + tool_luck + ammo_b["luck"] + vehicle_luck
    return {
        "luck":       total_luck + temp_b.get("luck", 0),
        "sell":       personal.get("sell", 0) + t_sell + prestige_b + ammo_b["sell"] + temp_b.get("sell", 0),
        "xp":         personal.get("xp",   0) + t_xp   + prestige_b + tool_xp + ammo_b["xp"] + temp_b.get("xp", 0),
        "crate_luck": personal.get("crate_luck", 0),
        "p_luck":     personal.get("luck", 0),
        "p_sell":     personal.get("sell", 0),
        "p_xp":       personal.get("xp",   0),
        "t_luck":     t_luck, "t_sell": t_sell, "t_xp": t_xp,
        "prestige_b": prestige_b,
        "tool_luck":  tool_luck, "tool_xp": tool_xp,
        "ammo_luck":  ammo_b["luck"], "ammo_sell": ammo_b["sell"], "ammo_xp": ammo_b["xp"],
        "cd":         vehicle_cd,
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
hunt_time:             list[float]     = []
_update_page:          dict[str, int] = {}  # Track current page per user
_rules_page:           dict[str, int] = {}

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
    medals        = {0: "🥇", 1: "🥈", 2: "🥉"}
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
        f"### 🎰 Lottery Winner: `{winner_name}`\n\n"
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
    ld["tickets"]     = {}
    ld["pool"]        = 0
    ld["next_ts"]     = next_ts
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
    return IDLE_BASE_CAPACITY + up * IDLE_CAPACITY_PER_UPGRADE

def idle_capacity_upgrade_cost(current_upgrades: int) -> int:
    return 25_000 * (2 ** current_upgrades)

def idle_camp_biome(user_id: str) -> str:
    b = data[user_id].get("idle", {}).get("camp_biome", "village")
    return b if b in BIOME_ANIMALS else "village"

def idle_catches_per_hour(user_id: str) -> float:
    idle = data[user_id].get("idle", {})
    hunters = min(idle.get("stacks", 0), IDLE_MAX_HUNTERS)
    if hunters <= 0:
        return 0.0
    tier = BIOME_TOOL_TIER.get(idle_camp_biome(user_id), 1)
    # richer biomes yield slower — the dangerous game is rarer
    return hunters * (IDLE_BASE_CATCH_RATE / (1 + tier * 0.12))

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
    for animal in haul:
        base_val   = ANIMAL_DATA.get(animal, {}).get("value", 0)
        base_xp    = ANIMAL_DATA.get(animal, {}).get("xp", 0)
        sell_value = int(base_val * (1 + sell_boost / 100))
        xp_earned  = int(base_xp * (1 + xp_boost / 100))
        is_rare    = random.randint(1, 100) <= (5 + luck_boost)
        if is_rare:
            sell_value *= 3; xp_earned *= 2; rares += 1
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
            "total_xp": total_xp, "level_ups": level_ups, "rares": rares}

# ─────────────────────────────────────────────
# RECORD & LOG HELPERS
# ─────────────────────────────────────────────

def record_catch(user_id: str, animal: str, tool: str, value: int):
    record = data[user_id].setdefault("record", {})
    if animal not in record:
        record[animal] = {"count": 0, "total_earned": 0, "tools": {}}
    record[animal]["count"]        += 1
    record[animal]["total_earned"] += value
    record[animal].setdefault("tools", {})[tool] = record[animal]["tools"].get(tool, 0) + 1
    data[user_id]["total_caught"] = data[user_id].get("total_caught", 0) + 1

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
    return sum(int(ANIMAL_DATA.get(a, {}).get("value", 0) * (1 + sell_boost / 100))
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

async def _raw(interaction: discord.Interaction, payload: dict):
    route = Route(
        "POST", "/interactions/{interaction_id}/{interaction_token}/callback",
        interaction_id=interaction.id, interaction_token=interaction.token,
    )
    await interaction.client.http.request(route, json=payload)

async def update_v2(interaction: discord.Interaction, components: list):
    await _raw(interaction, {
        "type": 7,
        "data": {"flags": V2_FLAGS, "components": components, "allowed_mentions": {"parse": []}}
    })

async def edit_v2(interaction: discord.Interaction, components: list):
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

# ─────────────────────────────────────────────
# HUNT LOGIC
# ─────────────────────────────────────────────

def run_hunt(user_id: str) -> dict:
    global hunt_time  # ← add this
    init_user(user_id)

    now = time.time()
    cd  = data[user_id]["hunt_cd"]
    hunt_time.append(round(cd - now, 2))

    if len(hunt_time) >= 10 and len(set(hunt_time)) <= 1:
        data[user_id]["verify"]["time"] -= max(data[user_id]["verify"]["time"], 50)
        hunt_time = []

    tick_verify(user_id)
    if data[user_id]["verify"]["needed"]:
        return {"ok": False, "verify": True}

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
            return {"ok": False, "verify": False, "no_ammo": True,
                    "ammo_type": AMMO_TYPE_LABELS.get(get_tool_ammo_type(tool_name), "ammo"),
                    "tool_name": tool_name}
        if get_ammo_count(user_id, ammo_name) < ammo_cost:
            data[user_id]["equipped_ammo"] = None
            return {"ok": False, "verify": False, "no_ammo": True,
                    "ammo_type": AMMO_TYPE_LABELS.get(get_tool_ammo_type(tool_name), "ammo"),
                    "tool_name": tool_name, "ran_out": True}

    boosts     = get_total_boosts(user_id)
    sell_boost = boosts["sell"]
    xp_boost   = boosts["xp"]
    luck_boost = boosts["luck"]

    catches   = []
    total_xp  = 0
    total_val = 0

    for _ in range(multi):
        animal       = random.choice(BIOME_ANIMALS[biome])
        animal_value = ANIMAL_DATA.get(animal, {}).get("value", 0)
        sell_value   = int(animal_value * (1 + sell_boost / 100))
        animal_xp    = ANIMAL_DATA.get(animal, {}).get("xp", 0)
        xp_earned    = int(animal_xp * (1 + xp_boost / 100))
        is_rare      = random.randint(1, 100) <= (5 + luck_boost)
        if is_rare:
            sell_value *= 3; xp_earned *= 2
        catches.append({"animal": animal, "sell_value": sell_value,
                        "xp_earned": xp_earned, "is_rare": is_rare})
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

    # How much ammo this hunt actually consumed — captured before ammo_name is
    # cleared below, so the hunt that empties the stack still advances the quest.
    ammo_spent_this_hunt = ammo_cost if (needs_ammo and ammo_name) else 0
    if needs_ammo and ammo_name:
        consume_ammo(user_id, ammo_name, ammo_cost)
        remaining_ammo = get_ammo_count(user_id, ammo_name)
        if remaining_ammo == 0:
            data[user_id]["equipped_ammo"] = None
            ammo_name = None
    else:
        remaining_ammo = None

    effective_cd = max(1.0, HUNT_COOLDOWN - boosts.get("cd", 0))
    data[user_id]["hunt_cd"]            = now + effective_cd
    data[user_id]["xp"]                += total_xp
    data[user_id]["total_money_earned"] = data[user_id].get("total_money_earned", 0) + total_val
    data[user_id]["_pending_sell"]      = (data[user_id].get("_pending_sell") or 0) + total_val

    level_ups = 0
    while data[user_id]["xp"] >= xp_for_level(data[user_id]["level"]):
        data[user_id]["xp"]    -= xp_for_level(data[user_id]["level"])
        data[user_id]["level"] += 1
        level_ups += 1

    tip = random.choice(TIPS) if random.randint(1, TIP_CHANCE) == 1 else None

    # ── Crate drop ───────────────────────────────────────────────────
    crate_luck_boost = boosts.get("crate_luck", 0)
    crate_drop = roll_hunt_crate_drop(crate_luck_boost)
    if crate_drop:
        crate_inv = data[user_id].setdefault("crate_inv", {})
        crate_inv[crate_drop] = crate_inv.get(crate_drop, 0) + 1

    # Quests
    tool_tier = TOOLS.get(tool_name, {}).get("tier", 1)
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
    if crate_drop:
        quest_progress(user_id, "crate_drops_earned", 1)
    if level_ups:
        quest_progress(user_id, "levels_gained_quest", level_ups)
    quest_progress(user_id, "xp_earned_quest", total_xp)

    add_log_entry(user_id, {
        "ts": int(now), "biome": biome, "tool": tool_name, "ammo": ammo_name,
        "catches": catches, "total_xp": total_xp, "level_ups": level_ups,
    })

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
        "crate_drop": crate_drop,
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
        total = sum(int(ANIMAL_DATA.get(a, {}).get("value", 0) * (1 + sell_boost / 100)) for a in inv)
    data[user_id]["inv"] = []
    add_money(user_id, total, "sell all")
    
    # Don't re-add to total_money_earned — run_hunt already counted it
    return {"total": total, "count": count}

# ─────────────────────────────────────────────
# PROGRESS BAR / FORMAT HELPERS
# ─────────────────────────────────────────────

def _progress_bar(current: int, maximum: int, width: int = 16) -> str:
    if maximum <= 0:
        return f"[{'█' * width}] 100%"
    pct    = min(current / maximum, 1.0)
    filled = int(pct * width)
    empty  = width - filled
    return f"[{'█' * filled}{'░' * empty}] {pct*100:.1f}%"

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
# BADGE HELPERS
# ─────────────────────────────────────────────

def get_badge_display(user_id: str) -> str:
    parts = []
    for badge_key, bdef in BADGES.items():
        tier = data.get(user_id, {}).get("badges", {}).get(badge_key, {}).get("tier", 0)
        if tier == 2:
            parts.append(f"`{bdef['abbr']}🏆`")
        elif tier == 1:
            parts.append(f"`{bdef['abbr']}🥇`")
    return " ".join(parts) if parts else ""

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
_BADGE_LINES_PER_PAGE = 15

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
            check = "✅" if done else "⬜"
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


def build_badges_pages(user_id: str) -> list[str]:
    d         = data[user_id]
    pages     = []
    cur_page  = []
    cur_lines = 0

    def flush():
        nonlocal cur_lines
        if cur_page:
            pages.append("\n".join(cur_page))
            cur_page.clear()
        cur_lines = 0

    for badge_key, bdef in BADGES.items():
        tier   = d.get("badges", {}).get(badge_key, {}).get("tier", 0)
        label  = bdef["label"]
        abbr   = bdef["abbr"]
        gold_t = bdef["gold"]
        plat_t = bdef["plat"]
        stat   = bdef["stat"]
        cur    = get_badge_stat(user_id, stat)

        icon = "🏆" if tier == 2 else ("🥇" if tier == 1 else "⬜")

        gold_bar   = _progress_bar(min(cur, gold_t), gold_t) + f"\n`{cur}/{gold_t}`\n"
        badge_line = f"**{label}** `[{abbr}{icon}]`"
        gold_done  = "✅" if tier >= 1 else "⬜"

        if plat_t:
            plat_bar  = _progress_bar(min(cur, plat_t), plat_t) + f"\n`{cur}/{plat_t}`\n"
            plat_done = "✅" if tier == 2 else "⬜"
            badge_entry = (
                f"{badge_line}\n"
                f"-# {gold_done} 🥇 Gold — {_fmt(gold_t)}\n"
                f"-# {gold_bar}\n"
                f"-# {plat_done} 🏆 Plat — {_fmt(plat_t)}\n"
                f"-# {plat_bar}"
            )
            entry_lines = 5
        else:
            badge_entry = (
                f"{badge_line}\n"
                f"-# 🥇 Gold — {_fmt(gold_t)}\n"
                f"-# {gold_bar}"
            )
            entry_lines = 3

        # Flush before adding if it won't fit
        if cur_lines + entry_lines + 1 > _BADGE_LINES_PER_PAGE and cur_lines > 0:
            flush()

        cur_page.append(badge_entry)
        cur_lines += entry_lines + 1  # +1 for spacing

    flush()
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
    title_count   = len(d.get("earned_titles", []))
    equipped_title = d.get("equipped_title")
    title_line    = f'🏷️ Equipped: *"{equipped_title}"*\n' if equipped_title else ""
    content = (
        f"### {emoji('achievements')} Achievements & Badges\n\n"
        f"{title_line}"
        f"{emoji('achievements')} Achievements: **{total_ach}/{total_possible}**\n"
        f"🎖️ Badges earned: **{badge_count}/{len(BADGES)}**\n"
        f"🏷️ Titles unlocked: **{title_count}**"
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "🏅 Achievements",
             "custom_id": f"ach:achievements:{user_id}"},
            {"type": 2, "style": 1, "label": "🎖️ Badges",
             "custom_id": f"ach:badges:{user_id}"},
            {"type": 2, "style": 1, "label": "🏷️ Titles",
             "custom_id": f"ach:titles:{user_id}"},
        ]},
        {"type": 14, "divider": True, "spacing": 1},
        _back_row(user_id),
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
    content = f"### 🎖️ Badges"
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Prev",
         "custom_id": f"badge:prev:{user_id}", "disabled": page == 0},
        {"type": 2, "style": 2, "label": "Next ▶",
         "custom_id": f"badge:next:{user_id}", "disabled": page >= total - 1},
        {"type": 2, "style": 2, "label": "◀ Back",
         "custom_id": f"ach:back:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

# ─────────────────────────────────────────────
# TITLE PANEL
# ─────────────────────────────────────────────

def build_title_components(user_id: str) -> list:
    d        = data[user_id]
    earned   = d.get("earned_titles", [])
    equipped = d.get("equipped_title")

    if not earned:
        content = (
            "### 🏷️ Titles\n\n"
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
        f"{'✅' if t == equipped else '⬜'} {t}" for t in earned
    )
    content = (
        f"### 🏷️ Titles\n"
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
    d         = data[user_id]
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

    tribe_line = f"**{tribe_nm}**" if tribe_nm else "None"
    if tribe_inv:
        tribe_line += f" *(invite: {tribe_inv})*"

    inv_lines      = inv_summary_lines(user_id, INV_DISPLAY_MAX)
    mail_indicator = " 📬" if has_unread_mail(user_id) else ""

    ammo_name  = d.get("equipped_ammo")
    ammo_count = get_ammo_count(user_id, ammo_name) if ammo_name else 0
    a_info     = AMMO.get(ammo_name, {})
    ammo_line  = f"{a_info.get('emoji','🔸')} **{ammo_name}** ×{ammo_count}" if ammo_name else "None"

    vehicle_name = d.get("vehicle", "None")
    v_info       = VEHICLES.get(vehicle_name, {})
    vehicle_line = f"{v_info.get('emoji','🚗')} **{vehicle_name}**" if vehicle_name and vehicle_name != "None" else "None"

    equipped_title = d.get("equipped_title")
    title_line     = f'🏷️ *"{equipped_title}"*\n' if equipped_title else ""

    boosts     = get_total_boosts(user_id)
    badge_str  = get_badge_display(user_id)
    badge_line = f"{badge_str}\n" if badge_str else ""

    stats = (
        f"### {USER_EMOJIS['profile']} {display_name}'s Menu\n"
        f"{title_line}"
        f"{badge_line}"
        f"{USER_EMOJIS['levels']} Level **{d['level']}** ({d['xp']:,}/{xp_for_level(d['level']):,} XP) · "
        f"{emoji('prestige')} Prestige **{prestige}**\n"
        f"**◈ {d['money']:,}** · {emoji('gem')} **{d['gems']}**\n\n"
        f"{BIOME_EMOJIS[biome]} **{BIOME_NAMES[biome]}** · "
        f"{TOOLS[tool_name]['emoji']} **{tool_name}** (T{get_tool_tier(tool_name)})\n"
        f"🔸 Ammo: {ammo_line}\n"
        f"🚗 Vehicle: {vehicle_line}\n"
        f"Tribe: {TRIBE_EMOJIS['tribe']} {tribe_line}\n\n"
        f"{emoji('luck')} Luck: + **{boosts['luck']}%** · "
        f"{emoji('sell_boost')} Sell: + **{boosts['sell']}%** · "
        f"{emoji('xp_boost')} XP: + **{boosts['xp']}%**\n\n"
        f"{emoji('idle_camp')} Camp: **{stacks}** hunter(s)"
        f"{f' · Haul {idle_haul}/{idle_cap} @ {idle_camp_nm}' if stacks else ''}\n\n"
        f"🎒 Inventory ({len(inv)} items · ◈ {sell_val:,}):\n"
        f"{inv_lines}"
    )

    dropdown = {"type": 1, "components": [{"type": 3,
        "custom_id": f"menu:nav:{user_id}",
        "placeholder": "📋 Navigate...",
        "min_values": 1, "max_values": 1, "flows": {},
        "options": [
            {"label": "Hunt",         "emoji": emoji_partial("bow"),  "value": "hunt",         "description": "Go hunting in your current biome"},
            {"label": "Shop",         "emoji": {"name": "🏪"},  "value": "shop",         "description": "Buy boosts, tools and ammo"},
            {"label": "Biome",        "emoji": emoji_partial("biome"),  "value": "biome",        "description": "Change your hunting biome"},
            {"label": "Color",        "emoji": {"name": "🎨"},  "value": "color",        "description": "Change your color of containers"},
            {"label": "Daily",        "emoji": emoji_partial("daily"),  "value": "daily",        "description": "Claim your daily reward"},
            {"label": "Prestige",     "emoji": emoji_partial("prestige"),  "value": "prestige",     "description": "Prestige for permanent boosts"},
            {"label": "Idle",         "emoji": emoji_partial("idle_camp"),  "value": "idle",         "description": "Manage your Hunting Camp"},
            {"label": "Crates",       "emoji": {"name": "📦"},  "value": "crates",       "description": "Buy and open hunting crates"},
            {"label": "Equip",        "emoji": emoji_partial("equipment"),  "value": "equip",        "description": "Equip tools, ammo and vehicles"},
            {"label": f"Mail{mail_indicator}", "emoji": emoji_partial("mail"), "value": "mail", "description": "Check your mailbox"},
            {"label": "Tribe",        "emoji": emoji_partial("tribe"),   "value": "tribe",   "description": "View your tribe"},
            {"label": "Profile",      "emoji": emoji_partial("profile"), "value": "profile", "description": "View your profile"},
            {"label": "Leaderboard",  "emoji": emoji_partial("leaderboard"),  "value": "leaderboard", "description": "View global leaderboards"},
            {"label": "Lottery",      "emoji": {"name": "🎰"},  "value": "lottery",      "description": "Buy tickets for the daily lottery"},
            {"label": "Gamble",       "emoji": {"name": "🎲"},  "value": "gamble",       "description": "Try your luck at mini-games"},
            {"label": "Progression",  "emoji": emoji_partial("achievements"),  "value": "progression",  "description": "View your achievements, badges, and titles"},
            {"label": "Events",       "emoji": {"name": "🌍"},  "value": "events",       "description": "View ongoing global events"},
            {"label": "Updates",      "emoji": emoji_partial("list"),      "value": "update",       "description": "View latest updates"},
            {"label": "Settings",     "emoji": emoji_partial("settings"),  "value": "settings",     "description": "Preferences and the hunter's guide"},
        ]
    }]}

    row2 = {"type": 1, "components": [
        {"type": 2, "style": 5, "label": "🔗 Invite Bot",
         "url": f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"},
        {"type": 2, "style": 5, "label": "🔗 Support Server",
         "url": f"https://discord.gg/X9JzdxeS8p"},
        {"type": 2, "style": 1, "label": "📖 Help",
         "custom_id": f"menu:help:{user_id}"},
    ]}

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": stats},
        {"type": 14, "divider": True, "spacing": 2},
        dropdown,
        row2,
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
        return f"### 👀 {name}'s {noun}"
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

    color_key   = d.get("color", "green")
    color_label = color_key.upper() if color_key.startswith("#") else \
                  f"{COLOR_EMOJIS.get(color_key, '')} {COLOR_LABELS.get(color_key, '')}"

    ammo_name   = d.get("equipped_ammo")
    ammo_count  = get_ammo_count(user_id, ammo_name) if ammo_name else 0
    a_info      = AMMO.get(ammo_name, {})
    ammo_line   = f"{a_info.get('emoji','🔸')} **{ammo_name}** ×{ammo_count}" if ammo_name else "None"

    vehicle_name = d.get("vehicle", "None")
    v_info       = VEHICLES.get(vehicle_name, {})
    vehicle_line = f"{v_info.get('emoji','🚗')} **{vehicle_name}**" if vehicle_name and vehicle_name != "None" else "None"

    badge_str      = get_badge_display(user_id)
    equipped_title = d.get("equipped_title")
    title_line     = f'🏷️ *"{equipped_title}"*\n' if equipped_title else ""
    badge_line     = f"{badge_str}\n\n" if badge_str else ""

    viewing_note = "-# 👀 You're viewing another hunter's profile.\n" if _viewing_other(user_id, viewer_id) else ""
    stats = (
        f"{_profile_title(USER_EMOJIS['profile'], display_name, 'Profile', user_id, viewer_id)}\n"
        f"{viewing_note}"
        f"{title_line}"
        f"{USER_EMOJIS['levels']} Lv. **{d['level']}** ({d['xp']:,}/{xp_for_level(d['level']):,} XP) · "
        f"{emoji('prestige')} Prestige **{prestige}**\n"
        f"**◈ {d['money']:,}** · {emoji('gem')} **{d['gems']}**\n"
        f"{BIOME_EMOJIS[biome]} **{BIOME_NAMES[biome]}** · "
        f"{TOOLS[tool_name]['emoji']} **{tool_name}** (T{get_tool_tier(tool_name)})\n"
        f"🔸 Ammo: {ammo_line}\n"
        f"🚗 Vehicle: {vehicle_line}\n"
        f"{TRIBE_EMOJIS['tribe']} {tribe_line}\n"
        f"{color_label}\n\n"
        f"{badge_line}"
        f"{emoji('luck')} Luck: + **{boosts['luck']}%** · "
        f"{emoji('sell_boost')} Sell: + **{boosts['sell']}%** · "
        f"{emoji('xp_boost')} XP: + **{boosts['xp']}%**\n\n"
        f"{emoji('idle_camp')} Camp: **{stacks}** hunter(s)"
        f"{f' · Haul {idle_haul}/{idle_cap} @ {idle_camp_nm}' if stacks else ''}\n\n"
        f"🎒 Inventory ({len(inv)} items · ◈ {sell_val:,}):\n"
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
        f"🔥 Current daily streak: **{streak}**\n"
        f"🏆 Best daily streak: **{best_streak}**\n\n"
        f"💰 Net worth: **◈ {nw:,}**\n"
        f"📦 Total ◈ earned: **◈ {total_earned:,}**\n"
        f"🎯 Total animals caught: **{total_caught:,}**\n"
        f"🔸 Ammo used: **{s.get('ammo_used', 0):,}**\n"
        f"🎰 Gamble wins — BJ: **{s.get('bj_wins',0):,}** · CF: **{s.get('cf_wins',0):,}** · "
        f"RL: **{s.get('rl_wins',0):,}** · RPS: **{s.get('rps_wins',0):,}** · "
        f"Slots: **{s.get('slots_wins',0):,}**\n"
        f"🎟️ Lottery wins: **{s.get('lottery_wins',0):,}**\n\n"
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

def build_inventory_components(user_id: str, display_name: str, viewer_id: str = None) -> list:
    d           = data[user_id]
    inv         = d.get("inv", [])
    sell_value  = inv_sell_value(user_id)
    total_items = len(inv)
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
        f"🎒 Total items: **{total_items}** · Worth: **◈ {sell_value:,}**\n\n"
        f"{inventory_text}"
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        *_profile_tab_rows("inventory", user_id, viewer_id),
    ]}]

# ─────────────────────────────────────────────
# HUNT PANELS
# ─────────────────────────────────────────────

def build_hunt_components(user_id: str, result: dict) -> list:
    d         = data[user_id]
    inv_count = len(d.get("inv", []))
    sell_val  = inv_sell_value(user_id)
    tool_name = result["tool"]

    level_line = ""
    if result.get("level_ups") == 1:
        level_line = f"\n-# {USER_EMOJIS['level_up']} Level up! Now level **{result['level']}**"
    elif result.get("level_ups", 0) > 1:
        level_line = f"\n-# {USER_EMOJIS['level_up']} Level up ×{result['level_ups']}! Now level **{result['level']}**"

    tip_line = f"\n-# 💡**Tip:** {result['tip']}" if result.get("tip") else ""

    ammo_name = result.get("ammo")
    if ammo_name:
        remaining = result.get("remaining_ammo", 0)
        ammo_line = f"**{ammo_name}** ({remaining} left)"
    else:
        ammo_line = "no ammo"

    stats_block = (
        f"-# **◈ {result['balance']:,}**\n"
        f"-# Level **{result['level']:,}** ({result['xp']:,}/{result['xp_needed']:,})\n"
        f"-# Using {tool_name} with {ammo_line} in {result['biome_name']}\n"
        f"-# 🎒 Inventory: **{inv_count}** · Sell value: **◈ {sell_val:,}**"
        f"{level_line}{tip_line}"
    )

    total_xp_earned = 0
    total_sell_val = 0

    catch_parts = []
    for c in result["catches"]:
        animal      = c["animal"]
        rarity      = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        rarity_icon = RARITY_ICONS.get(rarity, "")
        rare_tag    = " · ✨ **Perfect Catch!**" if c["is_rare"] else ""
        a_em        = animal_emoji(animal)
        total_xp_earned += c['xp_earned']
        total_sell_val += c['sell_value']
        catch_parts.append(
            f"You caught a **{a_em} {animal}**!\n"
            f"-# {rarity_icon} {rarity.title()}{rare_tag}\n"
        )
    catch_parts.append(
        f"**+ {total_xp_earned:,} XP · Sell Value: ◈ {total_sell_val:,}**"
    )

    crate_drop = result.get("crate_drop")
    if crate_drop:
        crate_info = CRATE_TIERS.get(crate_drop, {})
        catch_parts.append(
            f"\n{crate_info.get('emoji', '📦')} **Crate Drop!** You found a **{crate_drop}**!"
            f"\n-# Check your crates to open it."
        )

    title_content = (
        f"### {d.get('_display_name', 'Hunter')}'s "
        f"Hunting in {result['biome_name']}\n"
    )

    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 3, "label": "Hunt",     "custom_id": f"hunt:again:{user_id}"},
        {"type": 2, "style": 1, "label": "Sell All", "custom_id": f"hunt:sell_all:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Back",   "custom_id": f"hunt:back:{user_id}"},
    ]}

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": title_content + stats_block},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "\n".join(catch_parts)},
        {"type": 14, "divider": False, "spacing": 1},
        btn_row,
    ]}]

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

# ─────────────────────────────────────────────
# COLOR PANEL
# ─────────────────────────────────────────────

def build_color_panel_components(user_id: str) -> list:
    current    = data[user_id].get("color", "green")
    user_level = data[user_id].get("level", 1)
    custom_line = "Available now." if user_level >= 1200 else f"Unlocks at Level 1200 (you: {user_level})."
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": (
            f"### 🎨 Choose Your Color\n"
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

def build_biome_panel_components(user_id: str) -> list:
    user_level    = data[user_id]["level"]
    current_biome = data[user_id]["biome"]
    tool_name     = data[user_id].get("tool", "Bare Hands")
    tool_tier     = get_tool_tier(tool_name)
    options = []
    for biome_key, lvl_req in BIOME_LEVELS:
        locked     = user_level < lvl_req
        needs_tool = tool_tier < BIOME_TOOL_TIER.get(biome_key, 1)
        if locked:
            desc = f"Unlocks at Level {lvl_req}"
        elif needs_tool:
            desc = f"⚠️ Needs Tier {BIOME_TOOL_TIER[biome_key]} tool"
        else:
            desc = f"Level {lvl_req}+"
        options.append({
            "label": BIOME_NAMES[biome_key], "value": biome_key,
            "description": desc, "default": biome_key == current_biome,
        })
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": (
            f"### {USER_EMOJIS['biome']} Choose Your Biome\n"
            f"Current: {BIOME_EMOJIS[current_biome]} **{BIOME_NAMES[current_biome]}**\n"
            f"-# {TOOLS[tool_name]['emoji']} **{tool_name}** (Tier {tool_tier})"
        )},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"biome:select:{user_id}",
            "placeholder": "Select a biome...", "min_values": 1, "max_values": 1, "flows": {},
            "options": options}]},
        _back_row(user_id),
    ]}]

# ─────────────────────────────────────────────
# EQUIP PANEL
# ─────────────────────────────────────────────

def build_equip_components(user_id: str) -> list:
    owned    = data[user_id].get("owned_tools", ["Bare Hands"])
    equipped = data[user_id].get("tool", "Bare Hands")
    t_info   = TOOLS[equipped]
    ammo_type = t_info.get("ammo_type")

    equip_opts = [
        {"label": f"{TOOLS[n]['emoji']} {n} (T{TOOLS[n]['tier']})", "value": n,
         "description": TOOLS[n]["description"], "default": n == equipped}
        for n in owned
    ]

    equipped_ammo = data[user_id].get("equipped_ammo")
    ammo_count    = get_ammo_count(user_id, equipped_ammo) if equipped_ammo else 0
    a_info_eq     = AMMO.get(equipped_ammo, {})

    if ammo_type:
        user_ammo_inv = data[user_id].get("ammo_inv", {})
        compatible    = [
            name for name, a in AMMO.items()
            if a["ammo_type"] == ammo_type and user_ammo_inv.get(name, 0) > 0
        ]
        if compatible:
            ammo_opts = [
                {"label": f"{AMMO[n]['emoji']} {n}", "value": n,
                 "description": f"{AMMO[n]['description']} · Amount: {user_ammo_inv.get(n, 0)}",
                 "default": n == equipped_ammo}
                for n in compatible
            ]
            ammo_dropdown = {"type": 1, "components": [{"type": 3,
                "custom_id": f"tools:ammo_equip:{user_id}",
                "placeholder": f"Select {AMMO_TYPE_LABELS.get(ammo_type, 'ammo')} to equip...",
                "min_values": 1, "max_values": 1, "flows": {},
                "options": ammo_opts[:25],
            }]}
        else:
            ammo_dropdown = {"type": 10, "content":
                f"-# No {AMMO_TYPE_LABELS.get(ammo_type, 'ammo')} in inventory. Buy some in /shop → Ammo!"}

        if equipped_ammo and ammo_compatible_with_tool(equipped_ammo, equipped):
            ammo_status = (
                f"-# 🔸 Equipped: {a_info_eq.get('emoji','🔸')} **{equipped_ammo}** ×{ammo_count}\n"
                f"-# {USER_EMOJIS['luck_boost']} +{a_info_eq.get('boost_luck',0)}% · "
                f"{USER_EMOJIS['sell_boost']} +{a_info_eq.get('boost_sell',0)}% · "
                f"{USER_EMOJIS['xp_boost']} +{a_info_eq.get('boost_xp',0)}%"
            )
        else:
            ammo_status = f"-# ⚠️ No {AMMO_TYPE_LABELS.get(ammo_type,'ammo')} equipped — hunting blocked!"
    else:
        ammo_dropdown = None
        ammo_status   = "-# This tool requires no ammo."

    tool_desc = (
        f"### {UPGRADE_EMOJI} Tools\n"
        f"Equipped: {t_info['emoji']} **{equipped}** (Tier {get_tool_tier(equipped)})\n"
        f"-# {USER_EMOJIS['luck_boost']} +{t_info['boost_luck']}% · "
        f"{USER_EMOJIS['xp_boost']} +{t_info['boost_xp']}% · "
        f"🎯 Catches **{t_info['multi_catch']}** per hunt\n\n"
        f"**Ammo:**\n{ammo_status}\n\n"
        f"-# To buy tools, visit /shop → Tools."
    )

    comps = [
        {"type": 10, "content": tool_desc},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "**Select Tool to Equip**"},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"tools:equip:{user_id}",
            "placeholder": "Select tool to equip...", "min_values": 1, "max_values": 1,
            "flows": {}, "options": equip_opts}]},
    ]
    if ammo_dropdown:
        comps += [
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": f"**Select {AMMO_TYPE_LABELS.get(ammo_type,'Ammo')} to Equip**"},
            ammo_dropdown if isinstance(ammo_dropdown, dict) and ammo_dropdown.get("type") == 1
            else ammo_dropdown,
        ]
    elif ammo_type:
        comps += [
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": f"-# No {AMMO_TYPE_LABELS.get(ammo_type,'ammo')} owned."},
        ]

    equipped_vehicle = data[user_id].get("vehicle", "None")
    owned_vehicles   = data[user_id].get("owned_vehicles", [])
    v_info_eq        = VEHICLES.get(equipped_vehicle, {})

    if owned_vehicles:
        vehicle_opts = [
            {"label": f"{VEHICLES[n]['emoji']} {n}", "value": n,
             "description": f"-{VEHICLES[n]['boost_cd']}s cooldown · T{VEHICLES[n]['tier']}",
             "default": n == equipped_vehicle}
            for n in owned_vehicles
        ]
        comps += [
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": (
                f"**Vehicle:**\n"
                f"-# {v_info_eq.get('emoji','🚗')} **{equipped_vehicle}** — -{v_info_eq.get('boost_cd',0)}s cooldown"
                if equipped_vehicle and equipped_vehicle != "None"
                else "**Vehicle:**\n-# None equipped."
            )},
            {"type": 10, "content": "**Select Vehicle to Equip**"},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tools:vehicle_equip:{user_id}",
                "placeholder": "Select vehicle...", "min_values": 1, "max_values": 1,
                "flows": {}, "options": vehicle_opts[:25]}]},
        ]
    else:
        comps += [
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": "**Vehicle:**\n-# No vehicles owned. Buy one in /shop → Vehicles!"},
        ]

    comps.append(_back_row(user_id))
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ─────────────────────────────────────────────
# SHOP PANEL
# ─────────────────────────────────────────────

def build_shop_components(user_id: str, tab: str = "boosts") -> list:
    d = data[user_id]

    tab_options = [
        {"label": "🧪 Boosts",   "value": "boosts",   "default": tab == "boosts"},
        {"label": "🔧 Tools",    "value": "tools",    "default": tab == "tools"},
        {"label": "🔸 Ammo",     "value": "ammo",     "default": tab == "ammo"},
        {"label": "🚗 Vehicles", "value": "vehicles", "default": tab == "vehicles"},
    ]
    tab_dropdown = {"type": 1, "components": [{"type": 3,
        "custom_id": f"shop:tab_dd:{user_id}",
        "placeholder": "📋 Browse shop...",
        "min_values": 1, "max_values": 1, "flows": {},
        "options": tab_options,
    }]}

    if tab == "boosts":
        item_sections = []
        for name, item in SHOP_BOOST_ITEMS.items():
            boost_key = item.get("boost_key")
            bought    = (d.get("boosts", {}).get(boost_key, 0) // item["boost_amt"]
                         if boost_key else 0)
            maxed     = bought >= item["max_qty"]
            ps        = (f"{emoji('gem')}{item['price']}" if item["currency"] == "gems"
                         else f"◈ {item['price']:,}")
            content   = (
                f"**{name}** — {ps} · {bought}/{item['max_qty']}\n"
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
        header = f"### 🏪 Shop — Boosts\n**◈ {d['money']:,}** · {emoji('gem')} **{d['gems']}**"
        comps  = [{"type": 10, "content": header},
                  {"type": 14, "divider": True, "spacing": 1},
                  tab_dropdown,
                  {"type": 14, "divider": True, "spacing": 1},
                  *item_sections,
                  _back_row(user_id)]

    elif tab == "tools":
        owned      = d.get("owned_tools", ["Bare Hands"])
        all_tools  = get_all_tools_sorted()
        page       = _tool_shop_page.get(user_id, 0)
        per_page   = 5
        total_pages = max(1, (len(all_tools) + per_page - 1) // per_page)
        page       = max(0, min(page, total_pages - 1))
        page_tools = all_tools[page * per_page:(page + 1) * per_page]
        header     = f"### 🏪 Shop — Tools\n**◈ {d['money']:,}** · {emoji('gem')} **{d['gems']}**"
        item_sections = []
        for name, t in page_tools:
            already = name in owned
            ps      = ("✅ Owned" if already
                       else (f"◈ {t['price']:,}" if t["currency"] == "money" else f"{emoji('gem')}{t['price']}"))
            content = (f"{t['emoji']} **{name}** (T{t['tier']}) — {ps}\n"
                       f"-# {t['description']}")
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": {"type": 2, "style": 1 if not already else 2,
                    "label": "Buy" if not already else "Owned",
                    "custom_id": f"shop:tool_buy_acc:{name}:{user_id}",
                    "disabled": already},
            })
        page_nav_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev",
             "custom_id": f"shop:tool_prev:{user_id}", "disabled": page == 0},
            {"type": 2, "style": 2, "label": f"Page {page+1}/{total_pages}",
             "custom_id": f"shop:tool_noop:{user_id}", "disabled": True},
            {"type": 2, "style": 2, "label": "Next ▶",
             "custom_id": f"shop:tool_next:{user_id}", "disabled": page >= total_pages - 1},
        ]}
        comps = [{"type": 10, "content": header},
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
        ammo_tab_page = _ammo_shop_page.get(user_id, 0)
        ammo_tab_page = max(0, min(ammo_tab_page, len(ammo_types) - 1))
        current_type  = ammo_types[ammo_tab_page]
        compat_tools  = ", ".join(AMMO_TYPE_TOOLS.get(current_type, []))
        ammo_names    = grouped[current_type]
        header = (
            f"### 🏪 Shop — Ammo\n"
            f"**◈ {d['money']:,}** · {emoji('gem')} **{d['gems']}**\n"
            f"**— {AMMO_TYPE_LABELS[current_type]} —** *(for: {compat_tools})*"
        )
        item_sections = []
        for name in ammo_names:
            a         = AMMO[name]
            owned_qty = d.get("ammo_inv", {}).get(name, 0)
            ps        = (f"◈ {a['price']:,}/shot" if a["currency"] == "money"
                         else f"{emoji('gem')}{a['price']}/shot")
            boosts_s  = f"+{a['boost_luck']}% Luck · +{a['boost_sell']}% Sell · +{a['boost_xp']}% XP"
            content   = (
                f"{a['emoji']} **{name}** — {ps} · Owned: **{owned_qty}**\n"
                f"-# {a['description']}\n"
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
            {"type": 2, "style": 2, "label": "Next Type ▶",
             "custom_id": f"shop:ammo_next:{user_id}",
             "disabled": ammo_tab_page >= len(ammo_types) - 1},
        ]}
        comps = [{"type": 10, "content": header},
                 {"type": 14, "divider": True, "spacing": 1},
                 tab_dropdown,
                 {"type": 14, "divider": True, "spacing": 1},
                 *item_sections,
                 {"type": 14, "divider": True, "spacing": 1},
                 type_nav_row,
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
        header        = f"### 🏪 Shop — Vehicles\n**◈ {d['money']:,}** · {emoji('gem')} **{d['gems']}**"
        item_sections = []
        for name, v in page_vehicles:
            already  = name in owned_v
            is_equip = name == equipped_v
            ps       = ("✅ Equipped" if is_equip else
                        ("📦 Owned" if already else
                         (f"◈ {v['price']:,}" if v["currency"] == "money" else f"{emoji('gem')}{v['price']}")))
            cd_str   = f"-{v['boost_cd']}s cooldown"
            luck_str = f" · +{v['boost_luck']}% Luck" if v["boost_luck"] else ""
            content  = (
                f"{v['emoji']} **{name}** (T{v['tier']}) — {ps}\n"
                f"-# {v['description']}\n"
                f"-# {cd_str}{luck_str}"
            )
            if not already:
                acc_label, acc_style, acc_dis = "Buy",    1, False
                acc_cid = f"shop:vehicle_buy_acc:{name}:{user_id}"
            elif not is_equip:
                acc_label, acc_style, acc_dis = "Equip",  3, False
                acc_cid = f"shop:vehicle_equip_acc:{name}:{user_id}"
            else:
                acc_label, acc_style, acc_dis = "Equipped", 2, True
                acc_cid = f"shop:vehicle_noop:{user_id}"
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": {"type": 2, "style": acc_style, "label": acc_label,
                    "custom_id": acc_cid, "disabled": acc_dis},
            })
        page_nav_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev",
             "custom_id": f"shop:vehicle_prev:{user_id}", "disabled": page == 0},
            {"type": 2, "style": 2, "label": "Next ▶",
             "custom_id": f"shop:vehicle_next:{user_id}", "disabled": page >= total_pages - 1},
        ]}
        comps = [{"type": 10, "content": header},
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
        "### 💰 Cash in your catch!\n"
        "Hit **Sell All** on the hunt screen to turn everything in your bag into ◈.\n"
        "-# Sell boost increases how much ◈ you get per animal."
    )),
    ("Biome", (
        "### 🗺️ Try a new biome!\n"
        "Better biomes have rarer animals and higher payouts.\n"
        "Use `/biome` to switch once you level up.\n"
        "-# Each biome has a minimum level and tool tier requirement."
    )),
    ("Tools", (
        f"### {emoji('equipment')} Upgrade your tool!\n"
        "Better tools catch more animals per hunt and boost XP.\n"
        "Open `/shop` → Tools to see what's available.\n"
        "-# Higher tier tools unlock higher tier biomes."
    )),
    ("Ammo", (
        "### 🔸 Some tools need ammo!\n"
        "Buy ammo in `/shop` → Ammo, then equip via `/equip`.\n"
        "-# Running out of ammo mid-hunt will block hunting."
    )),
    ("Equip", (
        "### ⚙️ Equip your gear!\n"
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
        "### 🏕️ Join a tribe!\n"
        "Tribes share Luck, Sell, and XP boosts across all members.\n"
        "-# Use `/id` to get a friend's user ID."
    )),
    ("Prestige", (
        f"### {emoji('prestige')} Prestige is the endgame!\n"
        "Hit Level 1,000 and ◈ 1B? You can `/prestige` for a "
        "**permanent +20% to all boosts**.\n"
        "-# Gems, tools, tribe and ammo are kept on prestige."
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
    init_notif(user_id)
    n = data[user_id]["notif"]
    content = (
        f"### {emoji('settings')} Settings\n"
        "-# Manage your preferences below."
    )

    def _dm_row(key: str, icon: str, label: str, blurb: str):
        on = n[key]
        return [
            {"type": 10, "content": (
                f"{icon} **{label}** — {'🟢 ON' if on else '🔴 OFF'}\n"
                f"-# {blurb}"
            )},
            {"type": 1, "components": [
                {"type": 2, "style": 4 if on else 3,
                 "label": "Turn Off" if on else "Turn On",
                 "custom_id": f"settings:toggle:{key}:{user_id}"},
            ]},
        ]

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "📖 Tutorial Guide",
             "custom_id": f"settings:tutorial:{user_id}"},
        ]},
        {"type": 14, "divider": True, "spacing": 1},
        *_dm_row("daily_dm", emoji('daily'), "Daily Reminder DM",
                 "DM you once your daily reward is ready to claim. Off by default."),
        {"type": 14, "divider": True, "spacing": 1},
        *_dm_row("leaderboard_dm", emoji('leaderboard'), "Leaderboard Rank-Loss DM",
                 "DM you if you fall out of the global Top 3 on Level, Money, "
                 "Animals Caught, or Prestige. Off by default."),
        {"type": 14, "divider": True, "spacing": 1},
        _back_row(user_id),
    ]}]

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
        {"type": 10, "content": f"### 📜 Idle Hunter Rules\n-# Page {page + 1}/{total_pages} · {len(RULES)} rules total"},
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

_quest_page: dict[str, int] = {}
 
QUESTS_PER_PAGE = 3   # how many quests shown per page
 
def build_quests_components(user_id: str, page: int = 0) -> list:
    """
    Build the /quests panel.  Shows QUESTS_PER_PAGE quests per page with
    Prev / Next buttons and a Claim button per completed quest.
    """
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
 
    today = today_utc()
    roll_str = d.get("quests_last_roll", "")
    from datetime import datetime, timezone
    next_reset_ts = int(
        datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        + 86400
    )
 
    header = (
        f"### {emoji('quests')} Quests\n"
        f"-# **{len(active)}** active · **{len(claimed)}** completed · "
        f"Next drop: <t:{next_reset_ts}:R>"
    )
 
    # Build quest lines
    quest_blocks = []
    quest_buttons = []
 
    for q in page_quests:
        bar_filled  = min(10, int(q["progress"] / q["target"] * 10)) if q["target"] else 10
        bar_empty   = 10 - bar_filled
        bar         = "█" * bar_filled + "░" * bar_empty
 
        pct  = int(q["progress"] / q["target"] * 100) if q["target"] else 100
        done = "✅ " if q.get("completed") else ""
 
        line = (
            f"{done}{q['icon']} {q['description']}\n"
            f"-# `{bar}` {q['progress']:,}/{q['target']:,}  ·  +{q['xp_reward']:,} XP"
        )
        quest_blocks.append(line)
 
        # Claim button (only shown when completed and not yet claimed)
        if q.get("completed") and not q.get("claimed"):
            quest_buttons.append({
                "type": 2, "style": 3,
                "label": f"Claim: {q['icon']} quest",
                "custom_id": f"quests:claim:{q['id']}:{user_id}",
            })
 
    if not page_quests:
        quest_blocks.append(
            "-# No quests active right now.\n"
            "-# Come back tomorrow for a new batch!"
        )
 
    body = "\n\n".join(quest_blocks)
 
    # Navigation row
    nav_buttons = []
    if page > 0:
        nav_buttons.append({
            "type": 2, "style": 2, "label": "◀ Prev",
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
            "type": 2, "style": 2, "label": "Next ▶",
            "custom_id": f"quests:page:{page + 1}:{user_id}",
        })
    nav_buttons.append({
        "type": 2, "style": 2, "label": "◀ Menu",
        "custom_id": f"quests:back:{user_id}",
    })
 
    components = [
        {"type": 10, "content": header},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": body},
    ]
    if quest_buttons:
        components.append({"type": 14, "divider": False, "spacing": 1})
        # Discord limits 5 buttons per row; chunk into rows of 5
        for i in range(0, len(quest_buttons), 5):
            components.append({"type": 1, "components": quest_buttons[i:i+5]})
 
    components.append({"type": 14, "divider": True,  "spacing": 1})
    components.append({"type": 1,  "components": nav_buttons})
 
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
            desc = f"⚠️ Needs a Tier {tier_req}+ tool"
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
            f"🔴 **No hunters stationed.**\n"
            f"-# Hire a hunter and they'll bring back animals from your camp biome "
            f"while you're away — you collect the haul into your inventory.\n\n"
            f"-# 🗺️ Camp biome: {BIOME_EMOJIS[camp_b]} **{BIOME_NAMES[camp_b]}**\n"
            f"-# 📦 Haul storage: **{haul_n}/{cap}**\n"
            f"-# Balance: **◈ {d['money']:,}**"
        )
        rows = []
        if haul_n:
            rows.append({"type": 1, "components": [
                {"type": 2, "style": 3, "label": f"📥 Collect Haul ({haul_n})",
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
        fill_line = "⚠️ **HAUL FULL** — your hunters are sitting idle! Collect to send them back out."
    else:
        ts = int(time.time() + idle_seconds_until_full(user_id))
        fill_line = f"{emoji('cooldown')} Haul fills <t:{ts}:R>"

    hire_cost     = idle_cost_for_stack(hunters)
    up_cost       = idle_capacity_upgrade_cost(up_cur)
    up_maxed      = up_cur >= IDLE_MAX_CAPACITY_UPGRADES
    hunters_maxed = hunters >= IDLE_MAX_HUNTERS

    body = (
        f"### {emoji('idle_camp')} Hunting Camp\n"
        f"🟢 **{hunters}** hunter(s) camping in {BIOME_EMOJIS[camp_b]} **{BIOME_NAMES[camp_b]}**\n\n"
        f"📦 **Haul: {haul_n}/{cap}**\n"
        f"-# {_progress_bar(haul_n, cap, width=14)}\n"
        f"{fill_line}\n\n"
        f"-# 📈 Rate: **~{rate:.1f} catches/hr**\n"
        f"-# 💰 Haul value: **◈ {haul_val:,}** — goes to your inventory on collect\n"
        f"-# Balance: **◈ {d['money']:,}**"
    )
    btns = [
        {"type": 2, "style": 3, "label": f"📥 Collect ({haul_n})",
         "custom_id": f"idle:collect:{user_id}", "disabled": haul_n == 0},
        {"type": 2, "style": 1,
         "label": "👤 Hunters maxed" if hunters_maxed else f"👤 Hire (◈ {_short_num(hire_cost)})",
         "custom_id": f"idle:hire:{user_id}", "disabled": hunters_maxed},
        {"type": 2, "style": 1,
         "label": "📦 Storage maxed" if up_maxed else f"📦 +Storage (◈ {_short_num(up_cost)})",
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
        rare_tag = f" · {e['rare']}✨" if e["rare"] else ""
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
        f"-# 🎒 Inventory: **{inv_count}** · Sell value: **◈ {sell_val:,}**\n"
        f"-# ◈ **{d['money']:,}** · Level **{d['level']:,}** "
        f"({d['xp']:,}/{xp_for_level(d['level']):,})"
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": False, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "🪙 Sell All", "custom_id": f"hunt:sell_all:{user_id}"},
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
            f"-# 🔥 Streak: **{streak}** days · +{streak}% bonus\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    elif already:
        body = (
            f"### {emoji('daily')} Daily\nAlready claimed today!\n"
            f"-# 🔥 Streak: **{cur_streak}** days\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    else:
        tier = get_daily_tier(data[user_id]["level"])
        body = (
            f"### {emoji('daily')} Daily Reward\nClaim your daily reward!\n"
            f"-# 🔥 Streak: **{cur_streak}** days · +{cur_streak}% bonus\n"
            f"-# 💰 Possible: ◈ {tier['money_min']:,}–{tier['money_max']:,} "
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

def build_prestige_components(user_id: str) -> list:
    level    = data[user_id]["level"]
    money    = data[user_id]["money"]
    current  = data[user_id].get("prestige", 0)
    next_p   = current + 1
    boost    = next_p * 20
    lvl_ok   = level >= PRESTIGE_MIN_LEVEL
    money_ok = money >= PRESTIGE_MIN_MONEY
    body = (
        f"### {emoji('prestige')} Prestige {next_p}\n"
        f"Current: **Prestige {current}** (+{current * 20}% all boosts)\n\n"
        f"**Requirements:**\n"
        f"-# {'✅' if lvl_ok else '❌'} Level **{PRESTIGE_MIN_LEVEL:,}** (you: {level:,})\n"
        f"-# {'✅' if money_ok else '❌'} **◈ {PRESTIGE_MIN_MONEY:,}** (you: ◈ {money:,})\n\n"
        f"**Reward:** +**{boost}%** permanent Luck, Sell & XP\n"
        f"Prestiges costs almost everything. Please re-think about your decision before you click **Prestige**.\n"
        f"-# Resets: Level, Money, Inventory, Biome, Record, Tools, Ammo\n"
        f"-# Kept: Gems, Tribe, Log"
    )
    btns = []
    if lvl_ok and money_ok:
        btns.append({"type": 2, "style": 4, "label": "✅ Prestige",
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
            f"-# Permanent bonus: +**{new_prestige * 20}%** to all boosts"
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
        f"### 🎰 Lottery\n{last_line}\n\n"
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
            {"type": 2, "style": 3, "label": "🎟️ Buy Tickets",
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
        return f"✨ **+{reward['amount']}% {stat_label}** (permanent!)"
    if t == "temp_boost":
        stat_label = {"luck": "Luck", "sell": "Sell", "xp": "XP"}.get(reward["stat"], reward["stat"])
        return f"⏱️ **+{reward['amount']}% {stat_label}** for {reward['minutes']} min"
    if t == "title":
        return f'🏷️ Title: **"{reward["title"]}"**'
    return "???"

def build_crate_shop_components(user_id: str) -> list:
    d = data[user_id]
    inv = d.get("crate_inv", {})

    sections = []
    for name, crate in CRATE_TIERS.items():
        owned = inv.get(name, 0)
        ps = f"◈ {crate['price']:,}" if crate["currency"] == "money" else f"{emoji('gem')} {crate['price']:,}"
        content = (
            f"{crate['emoji']} **{name}** — {ps} · Owned: **{owned}**\n"
            f"-# {crate['description']}"
        )
        sections.append({
            "type": 9,
            "components": [{"type": 10, "content": content}],
            "accessory": {"type": 2, "style": 1, "label": "Buy",
                "custom_id": f"crate:buy:{name}:{user_id}"},
        })

    header = f"### 📦 Crate Shop\n**◈ {d['money']:,}** · {emoji('gem')} **{d['gems']}**"
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": header},
        {"type": 14, "divider": True, "spacing": 1},
        *sections,
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "Open Crates",
             "custom_id": f"crate:open_menu:{user_id}"},
            _back_row(user_id)["components"][0],
        ]},
    ]}]

def build_crate_open_menu_components(user_id: str) -> list:
    d = data[user_id]
    inv = d.get("crate_inv", {})
    owned = {k: v for k, v in inv.items() if v > 0}

    if not owned:
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": "### 📦 Open Crates\n\n-# You don't own any crates.\n-# Buy some in the Crate Shop!"},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "◀ Shop",
                 "custom_id": f"crate:shop:{user_id}"},
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
        {"type": 10, "content": f"### 📦 Open a Crate\n{inv_lines}"},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [{"type": 3,
            "custom_id": f"crate:open_select:{user_id}",
            "placeholder": "Select a crate to open...",
            "min_values": 1, "max_values": 1, "flows": {},
            "options": options,
        }]},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Shop",
             "custom_id": f"crate:shop:{user_id}"},
        ]},
    ]}]

def build_crate_result_components(user_id: str, crate_name: str, reward: dict) -> list:
    crate = CRATE_TIERS[crate_name]
    reward_str = _fmt_reward(reward)
    remaining = data[user_id].get("crate_inv", {}).get(crate_name, 0)

    content = (
        f"### {crate['emoji']} {crate_name} Opened!\n\n"
        f"You received:\n**{reward_str}**\n\n"
        f"-# {crate_name} remaining: **{remaining}**"
    )

    btns = [{"type": 2, "style": 2, "label": "◀ Back",
              "custom_id": f"crate:open_menu:{user_id}"}]
    if remaining > 0:
        btns.insert(0, {"type": 2, "style": 3, "label": f"Open Another {crate_name}",
                         "custom_id": f"crate:open_again:{crate_name}:{user_id}"})

    return [{"type": 17, "accent_color": crate["color"], "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": btns},
    ]}]

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
    if d.get("quests_last_roll") == today:
        return   # already rolled today
 
    active_quests = d.setdefault("quests", [])
 
    # Drop expired/claimed quests that are more than 7 days old (housekeeping)
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    d["quests"] = [q for q in active_quests
                   if not q.get("claimed") or q.get("created_date", "") >= cutoff]
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
 
    for q in d.get("quests", []):
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
 
 
def quest_claim(user_id: str, quest_id: str) -> dict:
    """
    Mark quest as claimed and grant XP.
    Returns {"ok": bool, "xp": int, "level_ups": int}
    """
    d = data[user_id]
    for q in d.get("quests", []):
        if q["id"] != quest_id:
            continue
        if not q.get("completed"):
            return {"ok": False, "reason": "not_complete"}
        if q.get("claimed"):
            return {"ok": False, "reason": "already_claimed"}
 
        xp = q["xp_reward"]
        q["claimed"] = True
 
        d["xp"] += xp
        d["stats"]["total_xp_earned"] = d["stats"].get("total_xp_earned", 0) + xp
 
        # Track "complete quests" meta-quest
        quest_progress(user_id, "quests_completed_today", 1)
 
        level_ups = 0
        while d["xp"] >= xp_for_level(d["level"]):
            d["xp"]    -= xp_for_level(d["level"])
            d["level"] += 1
            level_ups   += 1
 
        return {"ok": True, "xp": xp, "level_ups": level_ups,
                "level": d["level"], "xp_now": d["xp"],
                "xp_needed": xp_for_level(d["level"])}
 
    return {"ok": False, "reason": "not_found"}

# ─────────────────────────────────────────────
# GAMBLE PANELS
# ─────────────────────────────────────────────

# Plain unicode so the reels render everywhere (DMs, user installs, any server).
SLOT_SYMBOLS = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]

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

def _bj_hand_str(hand: list, hide_second: bool = False) -> str:
    if hide_second and len(hand) >= 2:
        return f"{hand[0]}  🂠"
    return "  ".join(hand)

_bj_state: dict[str, dict] = {}

def build_gamble_menu(user_id: str) -> list:
    d = data[user_id]
    content = (
        f"### 🎲 Gamble\n"
        f"Balance: **◈ {d['money']:,}**\n\n"
        f"-# Select a game from the dropdown below."
    )
    game_options = [
        {"label": "🪙 Coinflip",            "value": "coinflip",
         "description": "Double or nothing on a coin toss"},
        {"label": "🎰 Slots",               "value": "slots",
         "description": "Spin the reels — higher biomes, bigger wins"},
        {"label": "🃏 Blackjack",           "value": "blackjack",
         "description": "Beat the dealer to 21"},
        {"label": "🔴 Roulette",            "value": "roulette",
         "description": "Bet on Red, Black or Green"},
        {"label": "✊ Rock Paper Scissors",  "value": "rps",
         "description": "Beat the bot hand-to-hand"},
        {"label": "🎲 Dice",                "value": "dice",
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
            {"type": 2, "style": 2, "label": "⚠️ Responsible Gambling",
             "custom_id": f"gamble:warn:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"nav:menu:{user_id}"},
        ]},
    ]}]

def build_gamble_warning_panel(user_id: str) -> list:
    content = (
        "### ⚠️ A word on gambling\n"
        "These games use **◈ in-game currency only** — you can't win or lose real money here, "
        "and ◈ has no cash value.\n\n"
        "**Real-world gambling is different.** The odds are always tilted toward the house, "
        "losses can pile up quickly, and for some people it becomes a serious addiction that "
        "hurts their finances, relationships and health.\n\n"
        "**If gambling is a problem for you or someone you know:**\n"
        "-# 🌍 begambleaware.org  ·  gamblersanonymous.org\n"
        "-# 🇺🇸 1-800-GAMBLER   ·  🇬🇧 GamCare 0808 8020 133\n"
        "-# 🇨🇦 1-866-531-2600  ·  🇦🇺 1800 858 858\n\n"
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
            f"### 🎲 Dice\n{bet_line}\n\n"
            f"Two dice are rolled. Bet on the total:\n"
            f"-# Low 2–6 → ×2.2  ·  Seven → ×5.5  ·  High 8–12 → ×2.2"
        )
    else:
        d1, d2 = result["dice"]; total = d1 + d2
        bet    = result["bet"]; won = result["won"]
        pick   = DICE_BETS[result["pick"]][0]
        payout = result["payout"]
        head   = "✅ You won!" if won else "❌ You lost!"
        money_line = (f"**+◈ {payout - bet:,}**" if won else f"**-◈ {bet:,}**")
        content = (
            f"### 🎲 Dice — {head}\n"
            f"🎲 **{d1}** + 🎲 **{d2}** = **{total}**  ·  you bet **{pick}**\n\n"
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
_HL_HOUSE_EDGE = 0.92

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
            head, money = "✅ You won!", f"**+◈ {payout - bet:,}**"
        elif outcome == "push":
            head, money = "🤝 Push — same card", f"Bet refunded"
        else:
            head, money = "❌ You lost!", f"**-◈ {bet:,}**"
        content = (
            f"### 🔼 High-Low — {head}\n"
            f"Card was **{_HL_RANKS[n-1]}**, you guessed **{guess_lbl}** → next card **{_HL_RANKS[m-1]}**\n\n"
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
            f"### 🔼 High-Low\n{bet_line}\n\n"
            f"The card is **{_HL_RANKS[n-1]}**.\n"
            f"Will the next card be higher or lower?\n{note}"
        )
        row = {"type": 1, "components": [
            {"type": 2, "style": 3, "label": f"🔼 Higher (×{m_hi})" if m_hi else "🔼 Higher —",
             "custom_id": f"gamble:hl:hi:{user_id}", "disabled": (m_hi == 0)},
            {"type": 2, "style": 4, "label": f"🔽 Lower (×{m_lo})" if m_lo else "🔽 Lower —",
             "custom_id": f"gamble:hl:lo:{user_id}", "disabled": (m_lo == 0)},
        ]}
        row_util = {"type": 1, "components": [
            {"type": 2, "style": 1, "label": "🔄 Re-deal", "custom_id": f"gamble:hl:draw:{user_id}"},
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
        f"### 🔼 High-Low\n{bet_line}\n\n"
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
            f"### 🪙 Coinflip\n{last_line}\n{bet_line}\n\n"
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
                f"### 🪙 Coinflip — ✅ You won!\n"
                f"**{flip_lbl}!** You picked **{pick_lbl}** — correct!\n\n"
                f"**+◈ {bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
        else:
            content = (
                f"### 🪙 Coinflip — ❌ You lost!\n"
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

def _slots_biome_config(user_id: str) -> tuple:
    biome = data[user_id].get("biome", "village")
    return SLOT_BIOME_CONFIG.get(biome, SLOT_BIOME_CONFIG["village"])

def _slots_biome_options(user_id: str) -> list:
    user_level = data[user_id].get("level", 1)
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
            "description": desc, "default": biome_key == data[user_id].get("biome", "village"),
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
            f"{BIOME_EMOJIS.get(biome_key, '🗺️')} **{BIOME_NAMES.get(biome_key, biome_key)}**{lock_str}\n"
            f"-# Bet: ◈{min_b:,}–◈{max_b:,} · Win: {chance}% · ×{mult}"
        )
    content = "### 🎰 Slots — Win Chances by Biome\n\n" + "\n\n".join(lines)
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
    biome       = d.get("biome", "village")
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
            f"### 🎰 Slots Machine\n"
            f"{BIOME_EMOJIS.get(biome, '🗺️')} **{BIOME_NAMES.get(biome, biome)}**\n\n"
            f"Min: **◈ {min_b:,}** · Max: **◈ {max_b:,}**\n"
            f"Win: **{chance}%** · Multiplier: **×{mult}**\n\n{bet_line}"
        )
    else:
        reels = result["reels"]; bet = result["bet"]
        payout = result["payout"]; won = result["won"]
        reel_str = f"[ {reels[0]} | {reels[1]} | {reels[2]} ]"
        outcome  = f"✅ **Won! +◈ {payout - bet:,}**" if won else f"❌ **No win. -◈ {bet:,}**"
        content  = (
            f"### 🎰 Slots Machine\n{reel_str}\n\n"
            f"{outcome}\nBalance: **◈ {d['money']:,}**\n\n"
            f"{BIOME_EMOJIS.get(biome,'🗺️')} {BIOME_NAMES.get(biome,biome)} · "
            f"Win: {chance}% · ×{mult}\n{bet_line}"
        )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        biome_dd,
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "🎰 Roll!",
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
            f"### 🔴 Roulette\n{last_line}\n{bet_line}\n\n"
            f"Pick where the ball lands:\n"
            f"-# {_odds}"
        )
    else:
        color = result["color"]; pick = result["pick"]
        bet = result["bet"]; won = result["won"]; payout = result["payout"]
        color_ico = {"red": "🔴", "black": "⚫", "green": "🟢"}.get(color, "⚪")
        pick_lbl  = ROULETTE_BET_TYPES.get(pick, (pick,))[0]
        if won:
            content = (
                f"### 🔴 Roulette — ✅ You won!\n"
                f"Result: **{color_ico} {color.title()}** — You bet **{pick_lbl}**\n\n"
                f"**+◈ {payout - bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
        else:
            content = (
                f"### 🔴 Roulette — ❌ You lost!\n"
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
            f"### 🃏 Blackjack\nBalance: **◈ {d['money']:,}**\n\n"
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
            f"### 🃏 Blackjack · Bet: **◈ {bet:,}**\n\n"
            f"**Your hand:** {_bj_hand_str(st['player'])} — **{player_val}**\n"
            f"**Dealer:** {_bj_hand_str(st['dealer'], hide_second=True)}\n\n"
            f"-# Balance: **◈ {d['money']:,}**"
        )
        action_row = {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Hit",   "custom_id": f"gamble:bj:hit:{user_id}"},
            {"type": 2, "style": 1, "label": "Stand", "custom_id": f"gamble:bj:stand:{user_id}"},
        ]}
    else:
        outcome = st.get("outcome", "")
        net     = st.get("net", 0)
        sign    = "+" if net >= 0 else ""
        content = (
            f"### 🃏 Blackjack · {outcome}\n\n"
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
            f"### ✊ Rock Paper Scissors\n{last_line}\n{bet_line}\n\n"
            f"Beat the bot to double your bet!\n"
            f"-# Tie = bet refunded · Loss = lose bet"
        )
    else:
        pick = result["pick"]; bot_pick = result["bot_pick"]
        bet  = result["bet"];  outcome  = result["outcome"]
        p_ico = RPS_CHOICES.get(pick, "?"); b_ico = RPS_CHOICES.get(bot_pick, "?")
        if outcome == "win":
            content = (
                f"### ✊ RPS — ✅ You won!\n"
                f"You: **{p_ico} {pick.title()}** vs Bot: **{b_ico} {bot_pick.title()}**\n\n"
                f"**+◈ {bet:,}** · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
        elif outcome == "tie":
            content = (
                f"### ✊ RPS — 🤝 Tie!\n"
                f"You: **{p_ico} {pick.title()}** vs Bot: **{b_ico} {bot_pick.title()}**\n\n"
                f"Bet refunded · Balance: **◈ {d['money']:,}**\n\n"
                f"{last_line}\n{bet_line}"
            )
        else:
            content = (
                f"### ✊ RPS — ❌ You lost!\n"
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

def build_help_components(user_id: str) -> list:
    cmds  = sorted(bot.tree.get_commands(), key=lambda c: c.name)
    rows  = []
    for c in cmds:
        if isinstance(c, app_commands.Group):
            for sub in sorted(c.commands, key=lambda s: s.name):
                rows.append(f"`/{c.name} {sub.name}` — {sub.description or 'No description'}")
        else:
            rows.append(f"</{c.name}:{COMMAND_ID.get(c.name,'0')}> — {c.description or 'No description'}")
    lines = "\n".join(rows)
    content = f"### 📖 Commands\n{lines}\n-# Use /verify if blocked from commands."
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        _back_row(user_id),
    ]}]

# ─────────────────────────────────────────────
# MAIL PANEL
# ─────────────────────────────────────────────

def build_mail_components(user_id: str, tab: str = "tribe") -> list:
    d = data[user_id]
    tribe_unread = bool(d.get("tribe_inv") and not d.get("tribe_inv_read", False))
    gifts_unread = any(not g.get("read", False) for g in d.get("gift_mails", []))
    dev_unread   = bool(DEV_MAIL and d.get("mail_dev_content_read", "") != DEV_MAIL)
    tab_options  = [
        {"label": f"{'🔴 ' if tribe_unread else ''}🏕️ Tribe Invites", "value": "tribe",  "default": tab == "tribe"},
        {"label": f"{'🔴 ' if gifts_unread else ''}🎁 Gifts",          "value": "gifts",  "default": tab == "gifts"},
        {"label": f"{'🔴 ' if dev_unread   else ''}📢 Dev Mail",       "value": "dev",    "default": tab == "dev"},
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
                f"### 🏕️ Tribe Invites{unread_tag}\n\n"
                f"Pending invite to **{tribe_inv}**!\n\n"
                f"-# {TRIBE_EMOJIS['members']} {total}/{td['max_members']} members\n"
                f"-# {TRIBE_EMOJIS['luck_boost']} {td['luck_boost']}% · "
                f"{TRIBE_EMOJIS['sell_boost']} {td['sell_price_boost']}% · "
                f"{TRIBE_EMOJIS['xp_boost']} {td['xp_boost']}%"
            )
            d["tribe_inv_read"] = True
            action_btns = {"type": 1, "components": [
                {"type": 2, "style": 3, "label": "✅ Accept",
                 "custom_id": f"mail:tribe:accept:{user_id}"},
                {"type": 2, "style": 4, "label": "❌ Decline",
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
                {"type": 10, "content": "### 🏕️ Tribe Invites\n\n-# No pending tribe invites."},
                {"type": 14, "divider": True, "spacing": 1},
                tab_dd,
                {"type": 14, "divider": True, "spacing": 1},
                back_btn,
            ]}]

    elif tab == "gifts":
        gifts = d.get("gift_mails", [])
        if not gifts:
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": "### 🎁 Gift Mail\n\n-# No gift mail."},
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
            g["read"] = True
        delete_btn = {"type": 1, "components": [
            {"type": 2, "style": 4, "label": "🗑️ Delete All",
             "custom_id": f"mail:gifts:clear:{user_id}"},
        ]}
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": "### 🎁 Gift Mail"},
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
                {"type": 10, "content": "### 📢 Dev Mail\n\n-# No messages from the dev team."},
                {"type": 14, "divider": True, "spacing": 1},
                tab_dd,
                {"type": 14, "divider": True, "spacing": 1},
                back_btn,
            ]}]
        unread_tag  = "" if is_read else f" {emoji('new_notif')}"
        dev_section = {
            "type": 9,
            "components": [{"type": 10, "content": f"### 📢 Dev Mail{unread_tag}\n\n{DEV_MAIL}"}],
            "accessory": {"type": 2, "style": 3 if not is_read else 2,
                "label": "✅ Mark as Read" if not is_read else "Read",
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
        f"### 🔨 You have been banned"
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
        f"### 🎁 Confirm Gift\n"
        f"Send **{amt_str}** to {recipient.mention}?\n\n"
        f"> {message}\n\n"
        f"-# This action cannot be undone."
    )
    return [{"type": 17, "accent_color": _accent(sender_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "✅ Confirm",
             "custom_id": f"gift:confirm:{gift_id}"},
            {"type": 2, "style": 4, "label": "❌ Cancel",
             "custom_id": f"gift:cancel:{gift_id}"},
        ]},
    ]}]

def build_gift_sent_components(sender_id: str, recipient: discord.User,
                                amt_str: str, bal_str: str, sent_message: str) -> list:
    content = (
        f"### 🎁 Gift Sent!\n"
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

def build_tribe_components(user_id: str, tribe_name: str,
                            page: str = "main", sort_mode: str = "rank") -> list:
    td         = tribe_data[tribe_name]
    is_leader  = td["roles"]["leader"] == user_id
    is_officer = user_id in td["roles"].get("officer", [])

    def _member_list() -> str:
        all_m = ([(td["roles"]["leader"], "leader")] +
                 [(o, "officer") for o in td["roles"]["officer"]] +
                 [(m, "member")  for m in td["roles"]["members"]])
        if sort_mode == "level":
            all_m.sort(key=lambda x: data.get(x[0], {}).get("level", 0), reverse=True)
        icons = {"leader": TRIBE_EMOJIS["leader"], "officer": TRIBE_EMOJIS["officer"], "member": "🧑"}
        return "\n".join(
            f"{icons[r]} `{get_username(uid)}` — Lv. **{data.get(uid,{}).get('level','?')}**"
            for uid, r in all_m
        )

    total_m = 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"])

    if page == "main":
        desc_line = f"\n📝 *{td['description']}*\n" if td.get("description") else ""
        content   = (
            f"### {TRIBE_EMOJIS['tribe']} {tribe_name}{desc_line}\n"
            f"{USER_EMOJIS['levels']} Lv. **{td['level']}** · {USER_EMOJIS['xp']} **{td['xp']} XP**\n"
            f"{TRIBE_EMOJIS['members']} **{total_m}/{td['max_members']}**\n"
            f"{TRIBE_EMOJIS['luck_boost']} **{td['luck_boost']}%** · "
            f"{TRIBE_EMOJIS['sell_boost']} **{td['sell_price_boost']}%** · "
            f"{TRIBE_EMOJIS['xp_boost']} **{td['xp_boost']}%**\n\n"
            f"**Members ({sort_mode.title()}):**\n{_member_list()}"
        )
        sort_lbl = "Sort: Level" if sort_mode == "rank" else "Sort: Rank"
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 1, "label": "Members",
                 "custom_id": f"tribe:nav:members:{user_id}"},
                {"type": 2, "style": 1, "label": "Perk Shop",
                 "custom_id": f"tribe:nav:shop:{user_id}"},
                {"type": 2, "style": 1, "label": "Actions",
                 "custom_id": f"tribe:nav:actions:{user_id}"},
                {"type": 2, "style": 2, "label": sort_lbl,
                 "custom_id": f"tribe:sort:{user_id}"},
            ]},
            _back_row(user_id),
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
        content = (
            f"### 🏪 Tribe Shop — {tribe_name}\n"
            f"{emoji('gem')} Your Gems: **{data[user_id]['gems']}**\n\n"
            f"{TRIBE_EMOJIS['luck_boost']} Luck Boost: **{td['luck_boost']}%** — 50 {emoji('gem')}\n"
            f"{TRIBE_EMOJIS['sell_boost']} Sell Boost: **{td['sell_price_boost']}%** — 50 {emoji('gem')}\n"
            f"{TRIBE_EMOJIS['xp_boost']} XP Boost: **{td['xp_boost']}%** — 50 {emoji('gem')}\n"
            f"{TRIBE_EMOJIS['members']} +1 Slot: **{td['max_members']}** — 100 {emoji('gem')}"
        )
        btns = []
        if is_leader or is_officer:
            btns = [
                {"type": 2, "style": 3, "label": "Luck +5%",
                 "custom_id": f"tribe:shop:luck_boost:50:5:{user_id}"},
                {"type": 2, "style": 3, "label": "Sell +5%",
                 "custom_id": f"tribe:shop:sell_price_boost:50:5:{user_id}"},
                {"type": 2, "style": 3, "label": "XP +5%",
                 "custom_id": f"tribe:shop:xp_boost:50:5:{user_id}"},
                {"type": 2, "style": 3, "label": "+1 Slot",
                 "custom_id": f"tribe:shop:max_members:100:1:{user_id}"},
            ]
        btns.append({"type": 2, "style": 2, "label": "◀ Back",
                     "custom_id": f"tribe:nav:main:{user_id}"})
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": btns},
        ]}]

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
                "placeholder": "Select an action...", "min_values": 1, "max_values": 1,
                "flows": {}, "options": action_opts,
            }]},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "◀ Back",
                 "custom_id": f"tribe:nav:main:{user_id}"},
            ]},
        ]}]

    elif page in ("kick_picker", "promote_picker", "demote_picker", "transfer_picker"):
        role_map  = {
            "kick_picker":     (td["roles"]["officer"] + td["roles"]["members"], "kick",     "Kick Member"),
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

def build_leaderboard_v2_components(user_id: str, guild, mode: str = "hunter",
                                     scope: str = "global", stat: str = "Level",
                                     page: int = 0, period: str = "all") -> list:
    PS     = 10
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    if mode == "hunter":
        val_fn = lambda u: _lb_period_value(u, stat, period)
        cands  = get_server_user_ids(guild) if scope == "server" else list(data.keys())
        ranked = sorted(cands, key=val_fn, reverse=True)
        total  = len(ranked)
        items  = ranked[page * PS:(page + 1) * PS]
        lines  = []
        for i, uid in enumerate(items):
            pos     = page * PS + i
            val     = val_fn(uid)
            val_str = f"◈ {val:,}" if stat == "Money" else f"**{val:,}**"
            you     = " ← you" if uid == user_id else ""
            lines.append(f"{medals.get(pos, f'**#{pos+1}**')} `{get_username(uid)}` — {val_str}{you}")
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
                    any(u in mids for u in td["roles"]["officer"] + td["roles"]["members"])]
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
    scope_label_btn = "🌐 Global" if scope == "server" else "🏠 Server"
    components.append({"type": 1, "components": [
        {"type": 2, "style": 1, "label": scope_label_btn, "custom_id": f"lb:scope:{user_id}"},
    ]})
    cands_len = (len(get_server_user_ids(guild) if scope == "server" else list(data.keys()))
                 if mode == "hunter" else len(list(tribe_data.keys())))
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
                    f"-# ×{entry['count']} caught · ◈ {entry['total_earned']:,} · 🔧 {top_tool}"
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
                    f"-# ×{entry['count']} · ◈ {entry['total_earned']:,} · 🔧 {top_tool}"
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
    title   = f"### 👀 {display_name}'s Hunt Log" if other and display_name else f"### {emoji('list')} Hunt Log"
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
    for c in catches:
        animal     = c["animal"]
        rarity     = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        rarity_ico = RARITY_ICONS.get(rarity, "")
        rare_tag   = " · ✨ **Rare!**" if c.get("is_rare") else ""
        catch_lines.append(
            f"{animal_emoji(animal)} **{animal}**{rare_tag}\n"
            f"-# {rarity_ico} {rarity.title()} · +{c['xp_earned']:,} XP · ◈ {c['sell_value']:,}"
        )
    footer    = f"\n\n-# Total XP: **+{total_xp:,}**"
    if lv_ups:
        footer += f"\n-# {USER_EMOJIS['level_up']} Leveled up **×{lv_ups}**"
    ammo_line = f" · 🔸 {AMMO.get(ammo_log,{}).get('emoji','')} {ammo_log}" if ammo_log else ""
    content   = (
        f"{title} — Entry {page+1}/{total}\n"
        f"-# <t:{ts}:F> · {TOOLS.get(tool,{}).get('emoji','🔧')} **{tool}**{ammo_line} · "
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
    for c in catches:
        animal     = c["animal"]
        rarity     = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        rarity_ico = RARITY_ICONS.get(rarity, "")
        rare_tag   = " · ✨ **Perfect Catch!**" if c.get("is_rare") else ""
        catch_lines.append(
            f"{animal_emoji(animal)} **{animal}**{rare_tag}\n"
            f"-# {rarity_ico} {rarity.title()} · +{c['xp_earned']:,} XP · ◈ {c['sell_value']:,}"
        )
    footer    = f"\n\n-# Total XP: **+{total_xp:,}**"
    if lv_ups:
        footer += f"\n-# {USER_EMOJIS['level_up']} Leveled up **×{lv_ups}**"
    ammo_line = f" · 🔸 {AMMO.get(ammo_log,{}).get('emoji','')} {ammo_log}" if ammo_log else ""
    content   = (
        f"### {emoji('list')} Hunt Log — Entry {page+1}/{total}\n"
        f"-# <t:{ts}:F> · {TOOLS.get(tool,{}).get('emoji','🔧')} **{tool}**{ammo_line} · "
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
    all_users     = list(data.items())
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
                         ([td_r["roles"]["leader"]] + td_r["roles"]["officer"] + td_r["roles"]["members"])
                         if uid in data]
        t_money_sorted = sorted(tribe_members, key=lambda x: x[1].get("money", 0), reverse=True)
        t_money_rank   = next((i+1 for i, (uid, _) in enumerate(t_money_sorted) if uid == user_id), len(tribe_members))
        t_level_sorted = sorted(tribe_members, key=lambda x: (x[1].get("level", 1), x[1].get("xp", 0)), reverse=True)
        t_level_rank   = next((i+1 for i, (uid, _) in enumerate(t_level_sorted) if uid == user_id), len(tribe_members))
        tribe_section  = (
            f"\n\n### {TRIBE_EMOJIS['tribe']} Tribe Rankings — {tribe_nm}\n"
            f"💰 **Balance:** #{t_money_rank}/{len(tribe_members)}\n"
            f"{USER_EMOJIS['levels']} **Level:** #{t_level_rank}/{len(tribe_members)}"
        )
    heading = (f"### 👀 {display_name}'s Rankings"
               if _viewing_other(user_id, viewer_id) else f"### {emoji('leaderboard')} Your Rankings")
    content = (
        f"{heading}\n\n"
        f"### 🌍 Global\n"
        f"💰 **Balance:** #{money_rank:,}/{total_players:,}\n"
        f"{USER_EMOJIS['levels']} **Level:** #{level_rank:,}/{total_players:,}\n"
        f"🎯 **Animals:** #{caught_rank:,}/{total_players:,}"
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
                        "🏷️ Title Unlocked!",
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
            if not bstate.get("notified_gold"):
                bstate["notified_gold"] = True
                notifs.append(("🥇 Gold Badge Earned!",
                    f"**{label}** `[{abbr}🥇]`\n-# Keep going for Platinum!", 0xF1C40F))

        if plat_t and cur_tier < 2 and cur >= plat_t:
            bstate["tier"] = 2
            if not bstate.get("notified_plat"):
                bstate["notified_plat"] = True
                notifs.append(("🏆 Platinum Badge Earned!",
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
            notifs.append(("🏆 Platinum Badge Earned!",
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
    elif panel == "color":
        await smart_update_v2(interaction, build_color_panel_components(user_id))
    elif panel == "equip":
        await smart_update_v2(interaction, build_equip_components(user_id))
    elif panel == "idle":
        async with user_transaction(user_id):
            idle_tick(user_id)
        await smart_update_v2(interaction, build_idle_components(user_id))
    elif panel == "daily":
        await smart_update_v2(interaction, build_daily_components(user_id))
    elif panel == "prestige":
        await smart_update_v2(interaction, build_prestige_components(user_id))
    elif panel == "mail":
        await smart_update_v2(interaction, build_mail_components(user_id, "tribe"))
    elif panel == "help":
        await smart_update_v2(interaction, build_help_components(user_id))
    elif panel == "crates":
        await smart_update_v2(interaction, build_crate_shop_components(user_id))
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
        content = "### 🌍 Global Events\n\n-# No events are currently active.\n-# Check back later!"
        await smart_update_v2(interaction, [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
            "components": [{"type": 10, "content": content}, _back_row(user_id)]}])
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
                    "### 🔧 Bot Maintenance\n**Idle Hunter is currently under maintenance.**\n\n"
                    f"Reason: {maintenance_message}\n"
                    "Please be patient — we'll be back shortly!\n\n"
                    "-# All your data is safe. See you soon, hunter. 🏕️"
                }]}],
            "allowed_mentions": {"parse": []},
        }})
        return None

    init_user(user_id)
    data[user_id]["username"] = interaction.user.name
    init_ban_record(user_id)
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
        UNIX_TIME = int(time.time()) + (maintenance_time * 60)
        try:
            await send_ephemeral_v2(
                interaction,
                f"### ⚠️ Maintenance in <t:{UNIX_TIME}:R>\n"
                f"**Idle Hunter will enter maintenance shortly.**\n\n"
                f"Reason: {maintenance_message}\n\n"
                "-# You will only see this message once.",
                0xF39C12,
            )
        except Exception:
            pass

    return user_id


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
                    "### 🔧 Bot Maintenance\n**Idle Hunter is currently under maintenance.**\n\n"
                    f"Reason: {maintenance_message}\n"
                    "Please be patient — we'll be back shortly!\n\n"
                    "-# All your data is safe. See you soon, hunter. 🏕️"
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


async def _open_crate_and_show(interaction, user_id: str, crate_name: str):
    if crate_name not in CRATE_TIERS:
        await send_ephemeral_v2(interaction, "❌ Unknown crate.", 0xE74C3C)
        return
    inv = data[user_id].get("crate_inv", {})
    if inv.get(crate_name, 0) <= 0:
        await send_ephemeral_v2(interaction, f"❌ You don't have any **{crate_name}**.", 0xE74C3C)
        return

    async with user_transaction(user_id):
        inv[crate_name] -= 1
        if inv[crate_name] == 0:
            del inv[crate_name]

        reward = open_crate(crate_name)

        if reward["type"] == "money":
            add_money(user_id, reward["amount"], "crate")
            data[user_id]["total_money_earned"] = data[user_id].get("total_money_earned", 0) + reward["amount"]
        elif reward["type"] == "gems":
            add_gems(user_id, reward["amount"], "crate")
        elif reward["type"] == "perm_boost":
            data[user_id]["boosts"][reward["stat"]] = data[user_id]["boosts"].get(reward["stat"], 0) + reward["amount"]
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

        # Quests advance here — only after a crate was actually spent.
        quest_progress(user_id, "crates_opened_quest", 1)
        quest_progress(user_id, "crate_tier_opened",   1, crate_name=crate_name)

    await smart_update_v2(interaction, build_crate_result_components(user_id, crate_name, reward))
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
        logger.warning("interaction response failed (custom_id=%s): %s", cid, e)
    except Exception:
        cid = ((getattr(interaction, "data", {}) or {}).get("custom_id", "")) or "?"
        logger.exception("component handler crashed (custom_id=%s)", cid)
        if interaction.type == discord.InteractionType.component:
            try:
                await send_ephemeral_v2(
                    interaction,
                    "⚠️ Something went wrong handling that. Please try again.",
                    0xE74C3C,
                )
            except Exception:
                pass


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

    # ── ADMIN CONTROL PANEL ───────────────────
    if parts[0] == "admin":
        global maintenance_warning
        if not is_admin(interaction):
            await send_ephemeral_v2(interaction, "❌ Admins only.", 0xE74C3C)
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
        if kind in ("modal", "act"):
            # "modal": op is in the custom_id (arg). "act": op is the picked select value.
            op = (values[0] if values else "") if kind == "act" else arg
            modal = _admin_modal_for(op, admin_id)
            if modal is not None:
                await interaction.response.send_modal(modal)
            else:
                await send_ephemeral_v2(interaction, "❌ Unknown admin action.", 0xE74C3C)
            return
        if kind == "cancel":
            _admin_pending.pop(arg, None)
            await smart_update_v2(interaction, build_admin_panel(admin_id, "home", "✖ Action cancelled."))
            return
        if kind == "confirm":
            pend = _admin_pending.pop(arg, None)
            if not pend or pend["admin_id"] != str(admin_id):
                await smart_update_v2(interaction, build_admin_panel(
                    admin_id, "home", "❌ That confirmation expired — run the action again."))
                return
            try:
                section, note = await _admin_apply(pend["op"], pend["params"], admin_id)
            except Exception as e:
                logger.exception("admin apply failed")
                section, note = _admin_section_for(pend["op"]), f"❌ Action failed: {e}"
            await smart_update_v2(interaction, build_admin_panel(admin_id, section, note))
            return
        if kind == "do":
            if arg == "maint_toggle":
                await _admin_stage(
                    interaction, admin_id, "maint_toggle",
                    {"channel_id": interaction.channel_id},
                    ("Disable maintenance mode — the bot reopens to everyone."
                     if maintenance_mode else
                     "Enable maintenance mode **now** — this blocks every non-admin command."))
                return
            if arg == "maint_warn_toggle":
                maintenance_warning = not maintenance_warning
                if not maintenance_warning:
                    _maintenance_warned.clear()
                save_config()
                admin_audit(admin_id, "maint_warn_toggle", f"warning={maintenance_warning}")
                note = ("🟡 Maintenance warning **on**." if maintenance_warning
                        else "⚪ Maintenance warning **off** (warned list cleared).")
                await smart_update_v2(interaction, build_admin_panel(admin_id, "maint", note))
                return
            await smart_update_v2(interaction, build_admin_panel(admin_id, "maint", "❌ Unknown action."))
            return
        return

    # ── TRIBE CREATE (modal) ──────────────────
    if parts[0] == "tribe_create":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        if data[owner_id].get("tribe"):
            await send_ephemeral_v2(interaction, "❌ You're already in a tribe.", 0xE74C3C)
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
                    "not_complete":    "❌ That quest isn't completed yet.",
                    "already_claimed": "⚠️ Already claimed.",
                    "not_found":       "❌ Quest not found.",
                }.get(result.get("reason", ""), "❌ Couldn't claim.")
                await send_ephemeral_v2(interaction, reason_msg, 0xE74C3C)
                return
 
            xp_msg = f"+{result['xp']:,} XP"
            if result["level_ups"] == 1:
                xp_msg += f" · Level up! Now level **{result['level']}**"
            elif result["level_ups"] > 1:
                xp_msg += f" · Level up ×{result['level_ups']}! Now level **{result['level']}**"
 
            await send_ephemeral_v2(interaction, f"✅ Quest complete! {xp_msg}", 0x2ECC71)
            page = _quest_page.get(owner_id, 0)
            await smart_update_v2(interaction, build_quests_components(owner_id, page))
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
            can_hunt, remaining = await RateLimiter.can_hunt(actor, HUNT_COOLDOWN)
            if not can_hunt:
                await send_ephemeral_v2(interaction, f"{emoji('cooldown')} Wait **{remaining:.1f}s** before hunting again!", 0xE67E22)
                return
            async with user_transaction(actor):
                result = run_hunt(actor)
            if result.get("verify"):
                await send_ephemeral_v2(interaction,
                    f"{emoji('lock')} **Verification Required**\nRun {_verify_cmd_ref()} with code `{data[actor]['verify']['code']}`",
                    0xE67E22)
                return
            if result.get("tool_locked"):
                await send_ephemeral_v2(interaction,
                    f"❌ **{result['biome_name']}** needs Tier {result['req_tier']}+. Use </equip:{COMMAND_ID.get('equip','0')}>",
                    0xE74C3C)
                return
            if result.get("no_ammo"):
                ran_out = result.get("ran_out", False)
                atype   = result.get("ammo_type", "ammo")
                msg     = (f"💥 You ran out of {atype}! Your ammo was unequipped."
                           if ran_out else
                           f"⚠️ **{result['tool_name']}** needs {atype} equipped.")
                await send_ephemeral_v2(interaction, msg, 0xE67E22)
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
            return

        if clicker_id != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "sell_all":
            init_user(owner_id)
            async with user_transaction(owner_id):
                sold = sell_all_inv(owner_id)
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
            if panel == "hunt":
                can_hunt, remaining = await RateLimiter.can_hunt(owner_id, HUNT_COOLDOWN)
                if not can_hunt:
                    await send_ephemeral_v2(interaction, f"{emoji('cooldown')} Wait **{remaining:.1f}s** before hunting!", 0xE67E22)
                    return
                init_user(owner_id)
                async with user_transaction(owner_id):
                    result = run_hunt(owner_id)
                if result.get("verify"):
                    await send_ephemeral_v2(interaction,
                        f"{emoji('lock')} **Verification Required**\nRun {_verify_cmd_ref()} with code `{data[owner_id]['verify']['code']}`",
                        0xE67E22)
                    return
                if result.get("tool_locked"):
                    await send_ephemeral_v2(interaction,
                        f"❌ **{result['biome_name']}** needs Tier {result['req_tier']}+.",
                        0xE74C3C)
                    return
                if result.get("no_ammo"):
                    ran_out = result.get("ran_out", False)
                    atype   = result.get("ammo_type", "ammo")
                    msg     = (f"💥 You ran out of {atype}! Your ammo was unequipped."
                               if ran_out else
                               f"⚠️ **{result['tool_name']}** needs {atype} equipped.")
                    await send_ephemeral_v2(interaction, msg, 0xE67E22)
                    return
                if not result["ok"]:
                    await send_ephemeral_v2(interaction,
                        f"{emoji('cooldown')} Hunt again <t:{result.get('cooldown_ts', int(time.time()+3))}:R>.",
                        0xE67E22)
                    return
                
                data[owner_id]["_display_name"] = interaction.user.display_name
                await smart_update_v2(interaction, build_hunt_components(owner_id, result))
                return
            else:
                await _navigate(interaction, owner_id, panel, interaction.user.display_name)
                return

        if parts[1] == "help":
            await smart_update_v2(interaction, build_help_components(owner_id))
            return
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

    # ── BIOME ─────────────────────────────────
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
                f"❌ {BIOME_NAMES[biome_key]} unlocks at Level {lvl_req}.", 0xE74C3C)
            return
        data[owner_id]["biome"] = biome_key
        
        await smart_update_v2(interaction, build_biome_panel_components(owner_id))
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
                    await send_ephemeral_v2(interaction, "❌ You don't own that ammo.", 0xE74C3C)
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
            current   = data[owner_id]["boosts"].get(boost_key, 0) if boost_key else 0
            if boost_key and current >= boost_amt * item["max_qty"]:
                await send_ephemeral_v2(interaction, f"Max {item_name} already owned.", 0xE74C3C)
                return
            async with user_transaction(owner_id):
                ok, err = _shop_purchase(owner_id, item["currency"], item["price"], "shop boost")
                if ok and boost_key:
                    data[owner_id]["boosts"][boost_key] = current + boost_amt
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
            await smart_update_v2(interaction, build_shop_components(owner_id, "boosts"))
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
                ok, err = _shop_purchase(owner_id, t["currency"], t["price"], "shop tool")
                if ok:
                    data[owner_id]["owned_tools"].append(tool_name)
                    data[owner_id]["tool"] = tool_name
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
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
                ok, err = _shop_purchase(owner_id, t["currency"], t["price"], "shop tool")
                if ok:
                    data[owner_id]["owned_tools"].append(tool_name)
                    data[owner_id]["tool"] = tool_name
            if not ok:
                await send_ephemeral_v2(interaction, err, 0xE74C3C)
                return
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
            await check_everything(interaction, owner_id)
            return

        if sub == "hire":
            if idle.get("stacks", 0) >= IDLE_MAX_HUNTERS:
                await send_ephemeral_v2(interaction,
                    f"👤 You've hit the max of **{IDLE_MAX_HUNTERS}** hunters.", 0xE74C3C)
                return
            cost = idle_cost_for_stack(idle.get("stacks", 0))
            if data[owner_id]["money"] < cost:
                await send_ephemeral_v2(interaction,
                    f"❌ You need **◈ {cost:,}** to hire another hunter.", 0xE74C3C)
                return
            async with user_transaction(owner_id):
                idle_tick(owner_id)   # bank catches at the old rate first
                spend_money(owner_id, cost, "idle: hire hunter")
                idle["stacks"] = idle.get("stacks", 0) + 1
                idle["active"] = True
                if idle.get("started_at", 0) <= 0:
                    idle["started_at"] = time.time()
            await smart_update_v2(interaction, build_idle_components(owner_id))
            return

        if sub == "upgrade":
            cur = idle.get("capacity_upgrades", 0)
            if cur >= IDLE_MAX_CAPACITY_UPGRADES:
                await send_ephemeral_v2(interaction, "📦 Storage is already fully upgraded.", 0xE74C3C)
                return
            cost = idle_capacity_upgrade_cost(cur)
            if data[owner_id]["money"] < cost:
                await send_ephemeral_v2(interaction,
                    f"❌ You need **◈ {cost:,}** to expand storage "
                    f"(+{IDLE_CAPACITY_PER_UPGRADE} slots).", 0xE74C3C)
                return
            async with user_transaction(owner_id):
                idle_tick(owner_id)
                spend_money(owner_id, cost, "idle: storage upgrade")
                idle["capacity_upgrades"] = cur + 1
            await smart_update_v2(interaction, build_idle_components(owner_id))
            return

        if sub == "biome":
            biome_key = values[0] if values else None
            ok, reason = idle_can_camp(owner_id, biome_key or "")
            if not ok:
                await send_ephemeral_v2(interaction, f"❌ {reason}", 0xE74C3C)
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
                bonus    = 1 + (streak / 100) + (prestige * 0.1)
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
            quest_progress(owner_id, "dailies_claimed_quest", 1)
            # Streak quests track the *highest* streak reached, not a running sum.
            quest_progress(owner_id, "daily_streak_reached",
                           data[owner_id].get("daily_streak", 0), absolute=True)
 
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
        return

    # ── PRESTIGE ──────────────────────────────
    if parts[0] == "prestige" and parts[1] == "confirm":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if data[owner_id]["level"] < PRESTIGE_MIN_LEVEL or data[owner_id]["money"] < PRESTIGE_MIN_MONEY:
            await send_ephemeral_v2(interaction, "Requirements not met.", 0xE74C3C)
            return
        new_p = data[owner_id].get("prestige", 0) + 1
        async with user_transaction(owner_id):
            data[owner_id].update({
                "prestige": new_p, "level": 1, "xp": 0, "money": 0,
                "inv": [], "biome": "village", "record": {}, "total_caught": 0,
                "_pending_sell": None,
            })
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
            await smart_update_v2(interaction, build_mail_components(owner_id, "gifts"))
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
                total = 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"])
                if total >= td["max_members"]:
                    await send_ephemeral_v2(interaction, "Tribe is full.", 0xE74C3C)
                    return
                
                async with user_tribe_transaction(owner_id):
                    td["roles"]["members"].append(owner_id)
                    if owner_id in td.get("invites", []):
                        td["invites"].remove(owner_id)
                    data[owner_id]["tribe"] = tribe_inv
                    data[owner_id]["tribe_inv"] = None
                    data[owner_id]["tribe_inv_read"] = False
                
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
            await send_ephemeral_v2(interaction, "❌ This gift confirmation expired.", 0xE74C3C)
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
                await send_ephemeral_v2(interaction, f"❌ Not enough {icon}!", 0xE74C3C)
                return
            
            # Lock both users in a consistent order (see multi_user_transaction).
            bal_str = None
            async with multi_user_transaction(owner_id, recipient_id):
                # Re-check inside the lock
                if data[owner_id][fmt] < parsed:
                    bal_str = None
                else:
                    if fmt == "money":
                        spend_money(owner_id, parsed, "gift send")
                        add_money(recipient_id, parsed, "gift receive")
                        bal_str = f"◈ {data[owner_id]['money']:,}"
                    else:
                        spend_gems(owner_id, parsed, "gift send")
                        add_gems(recipient_id, parsed, "gift receive")
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

            if bal_str is None:
                await send_ephemeral_v2(interaction, f"❌ Not enough {icon}!", 0xE74C3C)
                return

            gift_cache.pop(gift_id, None)
            
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
                                f"### 🎁 You received a gift!\n"
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
                await send_ephemeral_v2(interaction, f"✅ Gift sent! ({amt_str})", 0x2ECC71)
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
                total_m = 1 + len(td_l["roles"]["officer"]) + len(td_l["roles"]["members"])
                is_ldr  = td_l["roles"]["leader"] == owner_id
                if is_ldr and total_m > 1:
                    await interaction.response.send_modal(TribeLeaveLeaderModal(owner_id, tribe_nm))
                    return
                # Non-modal leave falls through to defer below


        if action == "nav":
            page = parts[2]
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, page, sort))
            return

        if action == "sort":
            new_sort = "level" if sort == "rank" else "rank"
            _tribe_sort[owner_id] = new_sort
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "main", new_sort))
            return

        if action == "shop":
            boost_key = parts[2]
            cost      = int(parts[3])
            amount    = int(parts[4])
 
            # Pre-check outside lock (no mutation, safe to read)
            if data[owner_id]["gems"] < cost:
                await send_ephemeral_v2(interaction, f"Need {emoji('gem')}{cost}.", 0xE74C3C)
                return
 
            async with user_tribe_transaction(owner_id):
                # Re-check inside lock
                if not spend_gems(owner_id, cost, "tribe shop"):
                    pass  # spend_gems returns False if insufficient
                else:
                    tribe_data[tribe_nm][boost_key] = (
                        tribe_data[tribe_nm].get(boost_key, 0) + amount
                    )
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
                    async with user_tribe_transaction(owner_id):
                        if tribe_role_of(owner_id, tribe_nm) not in ("leader", "officer"):
                            pass
                        else:
                            td_r = tribe_data[tribe_nm]
                            if target == td_r["roles"].get("leader") or target == owner_id:
                                pass  # can't ban the leader or yourself
                            else:
                                for role in ("officer", "members"):
                                    if target in td_r["roles"][role]:
                                        td_r["roles"][role].remove(target)
                                if target in data:
                                    data[target]["tribe"] = None
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
                    async with user_tribe_transaction(owner_id):
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
                td_l    = tribe_data[tribe_nm]
                total_m = 1 + len(td_l["roles"]["officer"]) + len(td_l["roles"]["members"])
                is_ldr  = td_l["roles"]["leader"] == owner_id
                # is_ldr + total_m > 1 already sent modal above; handle remaining cases:
                async with user_tribe_transaction(owner_id):
                    if is_ldr and total_m == 1:
                        tribe_data.pop(tribe_nm, None)
                    else:
                        for role in ("officer", "members"):
                            if owner_id in td_l["roles"][role]:
                                td_l["roles"][role].remove(owner_id)
                    data[owner_id]["tribe"] = None
                await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
                return

            return

        if action == "kick_confirm":
            if not await _tribe_perm(interaction, owner_id, tribe_nm): return
            target = values[0] if values else None
            if target:
                async with user_tribe_transaction(owner_id):
                    td_r = tribe_data[tribe_nm]
                    if (tribe_role_of(owner_id, tribe_nm) in ("leader", "officer")
                            and target != td_r["roles"].get("leader") and target != owner_id):
                        for role in ("officer", "members"):
                            if target in td_r["roles"][role]:
                                td_r["roles"][role].remove(target)
                        if target in data:
                            data[target]["tribe"]     = None
                            data[target]["tribe_inv"] = None
                            mark_user_dirty(target)
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort))
            return

        if action == "promote_confirm":
            if not await _tribe_perm(interaction, owner_id, tribe_nm, ("leader",)): return
            target = values[0] if values else None
            if target:
                async with user_tribe_transaction(owner_id):
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
                async with user_tribe_transaction(owner_id):
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
                async with user_tribe_transaction(owner_id):
                    if tribe_role_of(owner_id, tribe_nm) == "leader":
                        td_r = tribe_data[tribe_nm]
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
                total_m = 1 + len(td_l["roles"]["officer"]) + len(td_l["roles"]["members"])
                is_ldr  = td_l["roles"]["leader"] == owner_id
                async with user_tribe_transaction(owner_id):
                    if is_ldr and total_m == 1:
                        tribe_data.pop(tribe_nm, None)
                    else:
                        for role in ("officer", "members"):
                            if owner_id in td_l["roles"][role]:
                                td_l["roles"][role].remove(owner_id)
                    data[owner_id]["tribe"] = None
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
            total = 1 + len(td_a["roles"]["officer"]) + len(td_a["roles"]["members"])
            if total >= td_a["max_members"]:
                await send_ephemeral_v2(interaction, "Tribe is full.", 0xE74C3C)
                return
            td_a["roles"]["members"].append(owner_id)
            if owner_id in td_a.get("invites", []):
                td_a["invites"].remove(owner_id)
            data[owner_id]["tribe"]     = tribe_nm
            data[owner_id]["tribe_inv"] = None
            
            
            await send_ephemeral_v2(interaction, f"✅ Joined **{tribe_nm}**!", 0x2ECC71)
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
            await send_ephemeral_v2(interaction, "❌ No appeal chances left.", 0xE74C3C)
            return
        await interaction.response.send_modal(BanAppealModal(owner_id))
        return

    # ── BAN APPEAL REVIEW (admin channel) ─────
    if parts[0] == "appeal" and len(parts) >= 3:
        # custom_id: appeal:<accept|reject>:<target_id>:<appeal_id>
        if not is_admin(interaction):
            await send_ephemeral_v2(interaction, "❌ Admins only.", 0xE74C3C)
            return

        decision  = parts[1]
        target_id = parts[2]
        appeal_id = parts[3] if len(parts) > 3 else ""
        store     = _appeal_store.get(appeal_id, {})

        if decision not in ("accept", "reject"):
            return
        if store.get("handled"):
            await send_ephemeral_v2(interaction, "❌ This appeal was already handled.", 0xE67E22)
            return

        init_user(target_id)
        init_ban_record(target_id)
        ban = data[target_id]["ban"]

        if decision == "accept":
            async with user_transaction(target_id):
                ban["active"] = False
            dm_color = 0x2ECC71
            dm_body  = (
                "### ✅ Your ban appeal was accepted\n"
                "Your ban has been lifted — welcome back, hunter.\n"
                "-# Please keep it fair from here on out."
            )
            admin_note = "✅ Appeal accepted — ban lifted."
        else:
            remaining = max(0, ban.get("appeals_max", 2) - ban.get("appeals_used", 0))
            dm_color = 0xE74C3C
            dm_body  = (
                "### ❌ Your ban appeal was rejected\n"
                "The team reviewed your appeal and decided to keep the ban in place.\n"
                f"-# Appeals remaining: **{remaining}**"
            )
            admin_note = "❌ Appeal rejected."

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
                            f"### 📋 Ban Appeal — {admin_note}\n"
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

        no_cd_subs = {"back", "game_select", "menu", "warn"}
        if parts[1] not in no_cd_subs:
            now         = time.time()
            last_gamble = data[owner_id].get("last_gamble", 0)
            if now - last_gamble < GAMBLE_COOLDOWN:
                remaining = GAMBLE_COOLDOWN - (now - last_gamble)
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
                _bj_state.pop(owner_id, None)
                await smart_update_v2(interaction, build_blackjack_panel(owner_id))
            elif game == "roulette":
                await smart_update_v2(interaction, build_roulette_panel(owner_id))
            elif game == "rps":
                await smart_update_v2(interaction, build_rps_panel(owner_id))
            elif game == "dice":
                await smart_update_v2(interaction, build_dice_panel(owner_id))
            elif game == "highlow":
                data[owner_id].pop("_hl_n", None)
                await smart_update_v2(interaction, build_highlow_panel(owner_id))
            return

        if parts[1] == "menu":
            game = parts[2]
            if game == "coinflip":
                await smart_update_v2(interaction, build_coinflip_panel(owner_id))
            elif game == "slots":
                await smart_update_v2(interaction, build_slots_panel(owner_id))
            elif game == "blackjack":
                _bj_state.pop(owner_id, None)
                await smart_update_v2(interaction, build_blackjack_panel(owner_id))
            return

        if parts[1] == "cf":
            sub = parts[2]
            if sub == "setbet":
                await interaction.response.send_modal(SetBetModal(owner_id, "cf"))
                return
            bet = data[owner_id].get("_cf_bet", 0)
            if not bet:
                await send_ephemeral_v2(interaction, "❌ Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, "❌ Not enough ◈.", 0xE74C3C)
                return
 
            flip = random.choice(["heads", "tails"])
            won  = flip == sub
 
            async with user_transaction(owner_id):
                data[owner_id]["_cf_last_pick"] = sub
                data[owner_id]["last_gamble"]   = time.time()
                if won:
                    add_money(owner_id, bet, "coinflip")
                    data[owner_id]["total_money_earned"] = (
                        data[owner_id].get("total_money_earned", 0) + bet
                    )
                    data[owner_id]["stats"]["cf_wins"] = (
                        data[owner_id]["stats"].get("cf_wins", 0) + 1
                    )
                else:
                    spend_money(owner_id, bet, "coinflip loss")
 
            result = {"won": won, "bet": bet, "flip": flip, "pick": sub}
            await smart_update_v2(interaction, build_coinflip_panel(owner_id, "result", result))
            return

        if parts[1] == "slots":
            sub = parts[2]
            if sub == "biome":
                biome_key  = values[0] if values else None
                user_level = data[owner_id].get("level", 1)
                if biome_key:
                    lvl_req = next((lvl for k, lvl in BIOME_LEVELS if k == biome_key), 1)
                    if user_level < lvl_req:
                        await send_ephemeral_v2(interaction,
                            f"❌ {BIOME_NAMES.get(biome_key, biome_key)} unlocks at Level {lvl_req}.",
                            0xE74C3C)
                        return
                    data[owner_id]["biome"] = biome_key
                    
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
                    await send_ephemeral_v2(interaction, "❌ Set a bet first.", 0xE74C3C)
                    return
                if data[owner_id]["money"] < bet:
                    await send_ephemeral_v2(interaction, "❌ Not enough ◈.", 0xE74C3C)
                    return
                min_b, _, chance, mult = _slots_biome_config(owner_id)
                if bet < min_b:
                    await send_ephemeral_v2(interaction,
                        f"❌ Minimum bet in this biome is **◈ {min_b:,}** — raise your bet.", 0xE74C3C)
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
                    spend_money(owner_id, bet, "slots bet")
                    add_money(owner_id, payout, "slots")
                    if won:
                        data[owner_id]["total_money_earned"] = data[owner_id].get("total_money_earned", 0) + (payout - bet)
                        data[owner_id]["stats"]["slots_wins"] = data[owner_id]["stats"].get("slots_wins", 0) + 1
                    data[owner_id]["last_gamble"] = time.time()

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
                await send_ephemeral_v2(interaction, "❌ Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, "❌ Not enough ◈.", 0xE74C3C)
                return
            if sub not in ROULETTE_BET_TYPES:
                await send_ephemeral_v2(interaction, "❌ Unknown bet type.", 0xE74C3C)
                return
            color      = random.choices(ROULETTE_COLORS, weights=ROULETTE_WEIGHTS, k=1)[0]
            _, _, mult = ROULETTE_BET_TYPES[sub]
            won        = color == sub
            payout     = bet * mult if won else 0
            async with user_transaction(owner_id):
                data[owner_id]["_roulette_pick"] = sub
                spend_money(owner_id, bet, "roulette")
                if won:
                    add_money(owner_id, payout, "roulette win")
                    data[owner_id]["total_money_earned"] = data[owner_id].get("total_money_earned", 0) + (payout - bet)
                    data[owner_id]["stats"]["rl_wins"] = data[owner_id]["stats"].get("rl_wins", 0) + 1
                data[owner_id]["last_gamble"] = time.time()

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
                await send_ephemeral_v2(interaction, "❌ Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, "❌ Not enough ◈.", 0xE74C3C)
                return
            if sub not in RPS_CHOICES:
                await send_ephemeral_v2(interaction, "❌ Unknown choice.", 0xE74C3C)
                return
            bot_pick = random.choice(list(RPS_CHOICES.keys()))
            async with user_transaction(owner_id):
                data[owner_id]["_rps_last_pick"] = sub
                if sub == bot_pick:
                    outcome = "tie"
                elif RPS_BEATS[sub] == bot_pick:
                    outcome = "win"
                    add_money(owner_id, bet, "rps")
                    data[owner_id]["total_money_earned"] = data[owner_id].get("total_money_earned", 0) + bet
                    data[owner_id]["stats"]["rps_wins"] = data[owner_id]["stats"].get("rps_wins", 0) + 1
                else:
                    outcome = "lose"
                    spend_money(owner_id, bet, "rps loss")
                data[owner_id]["last_gamble"] = time.time()

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
                await send_ephemeral_v2(interaction, "❌ Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, "❌ Not enough ◈.", 0xE74C3C)
                return
            if sub not in DICE_BETS:
                await send_ephemeral_v2(interaction, "❌ Unknown bet.", 0xE74C3C)
                return
            d1, d2       = random.randint(1, 6), random.randint(1, 6)
            total        = d1 + d2
            _, pred, mlt = DICE_BETS[sub]
            won          = pred(total)
            payout       = int(bet * mlt) if won else 0
            async with user_transaction(owner_id):
                spend_money(owner_id, bet, "dice bet")
                if won:
                    add_money(owner_id, payout, "dice win")
                    data[owner_id]["total_money_earned"] = data[owner_id].get("total_money_earned", 0) + (payout - bet)
                data[owner_id]["last_gamble"] = time.time()
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
                await send_ephemeral_v2(interaction, "❌ Set a bet first.", 0xE74C3C)
                return
            if data[owner_id]["money"] < bet:
                await send_ephemeral_v2(interaction, "❌ Not enough ◈.", 0xE74C3C)
                return

            if sub == "draw":
                data[owner_id]["_hl_n"] = random.randint(1, 13)
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
                        "❌ That side isn't a valid bet on this card — re-deal or take the other side.", 0xE74C3C)
                    return
                m = random.randint(1, 13)
                if m == n:
                    outcome, payout = "push", bet          # refund
                elif (m > n) == (sub == "hi"):
                    outcome, payout = "win", int(bet * mlt)
                else:
                    outcome, payout = "lose", 0
                async with user_transaction(owner_id):
                    spend_money(owner_id, bet, "highlow bet")
                    if payout:
                        add_money(owner_id, payout, f"highlow {outcome}")
                        if outcome == "win":
                            data[owner_id]["total_money_earned"] = data[owner_id].get("total_money_earned", 0) + (payout - bet)
                    data[owner_id]["last_gamble"] = time.time()
                data[owner_id].pop("_hl_n", None)
                result = {"n": n, "m": m, "guess": sub, "outcome": outcome, "bet": bet, "payout": payout}
                await smart_update_v2(interaction, build_highlow_panel(owner_id, "result", result))
                return
            return

        if parts[1] == "bj":
            action = parts[2]
            if action == "deal":
                await interaction.response.send_modal(BlackjackBetModal(owner_id))
                return
            st = _bj_state.get(owner_id)
            if not st or st.get("done"):
                await smart_update_v2(interaction, build_blackjack_panel(owner_id))
                return
            if action == "hit":
                card = st["deck"].pop()
                st["player"].append(card)
                val  = _bj_hand_value(st["player"])
                if val > 21:
                    st.update({"done": True, "outcome": "💥 Bust!", "net": -st["bet"]})
                elif val == 21:
                    action = "stand"
                else:
                    
                    await smart_update_v2(interaction, build_blackjack_panel(owner_id))
                    return
            if action == "stand":
                async with user_transaction(owner_id):
                    while _bj_hand_value(st["dealer"]) < 17:
                        st["dealer"].append(st["deck"].pop())
                    p_val = _bj_hand_value(st["player"])
                    d_val = _bj_hand_value(st["dealer"])
                    bet   = st["bet"]
                    if d_val > 21 or p_val > d_val:
                        payout = bet * 2
                        add_money(owner_id, payout, "blackjack")
                        data[owner_id]["total_money_earned"] = (
                            data[owner_id].get("total_money_earned", 0) + bet
                        )
                        st.update({"done": True, "outcome": "✅ You win!", "net": bet})
                        data[owner_id]["stats"]["bj_wins"] = (
                            data[owner_id]["stats"].get("bj_wins", 0) + 1
                        )
                    elif p_val == d_val:
                        add_money(owner_id, bet, "blackjack: tie")
                        st.update({"done": True, "outcome": "🤝 Push!", "net": 0})
                    else:
                        st.update({"done": True, "outcome": "❌ Dealer wins.", "net": -bet})
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
            cands = (get_server_user_ids(state["guild"])
                     if state["scope"] == "server" else list(data.keys())) \
                    if state["mode"] == "hunter" else list(tribe_data.keys())
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
            await send_ephemeral_v2(interaction, "❌ Admins only.", 0xE74C3C)
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
                await send_ephemeral_v2(interaction, "❌ You submitted this report.", 0xE74C3C)
                return
            seen_set = entry.setdefault("seen", set())
            if clicker_id in seen_set:
                await send_ephemeral_v2(interaction, "✅ Already recorded your confirmation.", 0x95A5A6)
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
                                    {"type": 2, "style": 1, "label": f"👀 I've also seen this ({seen_n})",
                                     "custom_id": f"report_btn:also_seen:{submitter_id}:{msg_id}"},
                                    {"type": 2, "style": 3, "label": "✅ Resolved",
                                     "custom_id": f"report_btn:resolved:{submitter_id}:{msg_id}"},
                                ]},
                            ]}],
                        "allowed_mentions": {"parse": []},
                    })
                except Exception:
                    pass
            await send_ephemeral_v2(interaction, "✅ Noted — thanks for confirming!", 0x2ECC71)
            # DM the original reporter
            try:
                route = Route("POST", "/users/@me/channels")
                dm_ch = await bot.http.request(route, json={"recipient_id": submitter_id})
                dm_route = Route("POST", "/channels/{channel_id}/messages", channel_id=dm_ch["id"])
                await bot.http.request(dm_route, json={
                    "flags": V2_FLAGS,
                    "components": [{"type": 17, "accent_color": 0xF39C12, "spoiler": False,
                        "components": [{"type": 10, "content":
                            f"### 👀 Someone else has seen your report!\n"
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
                await send_ephemeral_v2(interaction, "❌ Admins only.", 0xE74C3C)
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
                            f"### ✅ Your report has been resolved!\n"
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
                                + f"\n\n✅ **Resolved** by <@{interaction.user.id}>"}]}],
                        "allowed_mentions": {"parse": []},
                    })
                except Exception:
                    pass

            _report_store.pop(msg_id, None)
            await send_ephemeral_v2(interaction,
                "✅ Report marked as resolved. The reporter has been notified.", 0x2ECC71)
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
                "⚠️ Something went wrong. Please try again.",
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
        parsed = parse_amount(self.bet_input.value)
        if not parsed or parsed <= 0:
            await send_ephemeral_v2(interaction, "❌ Invalid amount.", 0xE74C3C)
            return
        if parsed > data[self.user_id]["money"]:
            await send_ephemeral_v2(interaction, "❌ Not enough ◈.", 0xE74C3C)
            return
        if self.min_bet and parsed < self.min_bet:
            await send_ephemeral_v2(interaction, f"❌ Minimum bet is ◈ {self.min_bet:,}.", 0xE74C3C)
            return
        if self.max_bet and parsed > self.max_bet:
            await send_ephemeral_v2(interaction, f"❌ Maximum bet is ◈ {self.max_bet:,}.", 0xE74C3C)
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
        raw = self.qty_input.value.strip()
        qty = parse_amount(raw)
        if not qty or qty <= 0:
            await send_ephemeral_v2(interaction, "❌ Invalid amount.", 0xE74C3C)
            return

        crate = CRATE_TIERS[self.crate_name]
        total_cost = crate["price"] * qty

        if crate["currency"] == "money":
            if not spend_money(self.user_id, total_cost, "crate buy"):
                await send_ephemeral_v2(interaction, f"❌ Need ◈ {total_cost:,}.", 0xE74C3C)
                return
        else:
            if not spend_gems(self.user_id, total_cost, "crate buy"):
                await send_ephemeral_v2(interaction, f"❌ Need {emoji('gem')} {total_cost:,}.", 0xE74C3C)
                return

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
        raw = self.qty_input.value.strip()
        qty = parse_amount(raw)
        if not qty or qty <= 0:
            await send_ephemeral_v2(interaction, "❌ Invalid amount.", 0xE74C3C)
            return
        total_cost = qty * LOTTERY_TICKET_COST
        if data[self.user_id]["money"] < total_cost:
            await send_ephemeral_v2(interaction,
                f"❌ Need **◈ {total_cost:,}** for {qty:,} ticket(s).", 0xE74C3C)
            return
        spend_money(self.user_id, total_cost, "lottery tickets")
        
        ld = lottery_data
        ld["tickets"][self.user_id] = ld["tickets"].get(self.user_id, 0) + qty
        ld["pool"]                  = ld.get("pool", 0) + total_cost
        save_lottery(ld)
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
        raw = self.hex_input.value.strip().lstrip("#")
        if len(raw) != 6 or not all(c in string.hexdigits for c in raw):
            await send_ephemeral_v2(interaction, "Invalid hex. Use `#RRGGBB`.", 0xE74C3C)
            return
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
        raw = self.qty_input.value.strip()
        if not raw.isdigit() or int(raw) <= 0:
            await send_ephemeral_v2(interaction, "❌ Enter a positive whole number.", 0xE74C3C)
            return
        qty = int(raw)
        a   = AMMO.get(self.ammo_name)
        if not a:
            await send_ephemeral_v2(interaction, "❌ Unknown ammo.", 0xE74C3C)
            return
        current_owned = data[self.user_id].get("ammo_inv", {}).get(self.ammo_name, 0)
        can_buy       = AMMO_MAX_STACK - current_owned
        if can_buy <= 0:
            await send_ephemeral_v2(interaction,
                f"❌ Already at max stack ({AMMO_MAX_STACK:,}) for **{self.ammo_name}**.", 0xE74C3C)
            return
        if qty > can_buy:
            await send_ephemeral_v2(interaction,
                f"❌ Can only buy **{can_buy:,}** more (stack limit: {AMMO_MAX_STACK:,}).", 0xE74C3C)
            return
        total_cost = a["price"] * qty
        currency   = a["currency"]
        if currency == "money":
            if not spend_money(self.user_id, total_cost, "shop ammo"):
                await send_ephemeral_v2(interaction,
                    f"❌ Need ◈ {total_cost:,} to buy {qty:,}× {self.ammo_name}.", 0xE74C3C)
                return
        else:
            if not spend_gems(self.user_id, total_cost, "shop ammo"):
                await send_ephemeral_v2(interaction,
                    f"❌ Need {emoji('gem')} {total_cost:,} to buy {qty:,}× {self.ammo_name}.", 0xE74C3C)
                return
        inv = data[self.user_id].setdefault("ammo_inv", {})
        inv[self.ammo_name] = current_owned + qty
        
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
        if tribe_role_of(self.user_id, self.tribe_name) not in ("leader", "officer"):
            await send_ephemeral_v2(
                interaction, "❌ You no longer have permission to edit this tribe.", 0xE74C3C)
            return
        async with user_tribe_transaction(self.user_id):
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
        if tribe_role_of(self.user_id, self.tribe_name) != "leader":
            await send_ephemeral_v2(interaction, "❌ Only the leader can transfer leadership.", 0xE74C3C)
            return
        target = self.uid_input.value.strip()
        td     = tribe_data.get(self.tribe_name)
        if not td:
            await send_ephemeral_v2(interaction, "❌ Tribe no longer exists.", 0xE74C3C)
            return
        all_ids = td["roles"]["officer"] + td["roles"]["members"]
        if target not in all_ids:
            await send_ephemeral_v2(interaction, "❌ That user is not a tribe member.", 0xE74C3C)
            return
        async with user_tribe_transaction(self.user_id):
            if tribe_role_of(self.user_id, self.tribe_name) == "leader":
                for role in ("officer", "members"):
                    if target in td["roles"][role]:       td["roles"][role].remove(target)
                    if self.user_id in td["roles"][role]: td["roles"][role].remove(self.user_id)
                td["roles"]["leader"]       = target
                data[self.user_id]["tribe"] = None
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
        name = self.name_input.value.strip()
        if name in tribe_data:
            await send_ephemeral_v2(interaction, "❌ Tribe name taken.", 0xE74C3C)
            return
        init_tribe(name, self.user_id)
        tribe_data[name]["description"] = self.desc_input.value.strip()
        
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
            await send_ephemeral_v2(interaction, "❌ You have no appeal chances left.", 0xE74C3C)
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
            "✅ Your appeal has been submitted. Admins will review it shortly.", 0x2ECC71)

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
                            f"### 📋 Ban Appeal\n"
                            f"**User:** <@{self.user_id}> (`{self.user_id}`)\n"
                            f"**Reason for ban:** {b.get('reason', 'N/A')}\n"
                            f"**Ban expires:** {exp_str}\n"
                            f"**Appeals used:** {data[self.user_id]['ban']['appeals_used']}/{max_app}\n\n"
                            f"**Appeal message:**\n{self.reason_input.value}"
                        },
                        {"type": 14, "divider": True, "spacing": 1},
                        {"type": 1, "components": [
                            {"type": 2, "style": 3, "label": "✅ Accept",
                             "custom_id": f"appeal:accept:{self.user_id}:{appeal_id}"},
                            {"type": 2, "style": 4, "label": "❌ Reject",
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
        parsed = parse_amount(self.bet_input.value)
        if not parsed or parsed <= 0:
            await send_ephemeral_v2(interaction, "❌ Invalid amount.", 0xE74C3C)
            return
        if data[self.user_id]["money"] < parsed:
            await send_ephemeral_v2(interaction, "❌ Not enough ◈.", 0xE74C3C)
            return
 
        deck   = _bj_deck()
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]
 
        async with user_transaction(self.user_id):
            data[self.user_id]["money"]      -= parsed
            data[self.user_id]["last_gamble"] = time.time()
 
        _bj_state[self.user_id] = {
            "bet": parsed, "deck": deck,
            "player": player, "dealer": dealer,
            "done": False,
        }
 
        if _bj_hand_value(player) == 21:
            payout = int(parsed * 2.5)
            async with user_transaction(self.user_id):
                add_money(self.user_id, payout, "blackjack: 21")
                data[self.user_id]["total_money_earned"] = (
                    data[self.user_id].get("total_money_earned", 0) + (payout - parsed)
                )
            _bj_state[self.user_id].update({
                "done": True, "outcome": "🃏 Blackjack!", "net": payout - parsed,
            })
 
        await smart_update_v2(interaction, build_blackjack_panel(self.user_id))

_VERDICT_LABELS = {"agree": "✅ Agreed", "neutral": "➖ Neutral", "disagree": "❌ Disagreed"}
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
            f"-# Final tally — ✅ {a} · ➖ {n} · ❌ {d}"
        )
        accent = _VERDICT_COLORS.get(entry.get("verdict", ""), 0x95A5A6)
    else:
        header = (
            f"## Suggestion #{num}: {title}\n"
            f"-# Submitted by: <@{poster}> ({who})\n"
            f"{text}\n\n"
            f"✅ {a} | ➖ {n} | ❌ {d}"
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
            _btn(3, f"✅ Agree · {a}",    "agree"),
            _btn(2, f"➖ Neutral · {n}",  "neutral"),
            _btn(4, f"❌ Disagree · {d}", "disagree"),
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
            f"✅ **{verdict}** recorded and your reply was DM'd to <@{self.submitter_id}>. "
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
                        f"### 💡 Your Suggestion Got a Response!\n"
                        f"**Verdict:** {verdict}\n\n"
                        f"{title_line}"
                        f"{reply_text}\n\n"
                        f"-# From the dev team.\n"
                        f"-# Tally — ✅ {agree_n} · ➖ {neutral_n} · ❌ {disagree_n}"
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
    
    # ✅ SIMPLE RATE LIMIT CHECK - Just add this block
    can_hunt, remaining = await RateLimiter.can_hunt(user_id, HUNT_COOLDOWN)
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
    
    if result.get("verify"):
        await send_v2_followup(interaction, build_verify_v2(user_id))
        return
    
    if result.get("tool_locked"):
        await send_ephemeral_v2(interaction,
            f"❌ **{result['biome_name']}** needs Tier {result['req_tier']}+. "
            f"Use </shop:{COMMAND_ID.get('shop','0')}> or </equip:{COMMAND_ID.get('equip','0')}>.",
            0xE74C3C)
        return
    
    if result.get("no_ammo"):
        ran_out = result.get("ran_out", False)
        atype = result.get("ammo_type", "ammo")
        msg = (f"💥 You ran out of {atype}! Your ammo was unequipped." if ran_out else
               f"⚠️ **{result['tool_name']}** needs {atype} equipped. "
               f"Buy some in </shop:{COMMAND_ID.get('shop','0')}> → Ammo!")
        await send_ephemeral_v2(interaction, msg, 0xE67E22)
        return
    
    if not result["ok"]:
        remaining = result.get("remaining", 3)
        await send_ephemeral_v2(interaction,
            f"{emoji('cooldown')} Hunt again <t:{result.get('cooldown_ts', int(time.time()+remaining))}:R>.",
            0xE67E22)
        return
    data[user_id]["_display_name"] = interaction.user.display_name
    await send_v2_followup(interaction, build_hunt_components(user_id, result))
    await check_everything(interaction, user_id)

@bot.tree.command(name="progression", description="View your achievements, badges, and titles")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def achievements_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    _ach_page[user_id] = 0
    await send_v2_followup(interaction, build_progression_hub(user_id))

@bot.tree.command(name="events", description="View ongoing global events")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def events_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, [{"type": 17, "accent_color": _accent(user_id),
        "spoiler": False, "components": [
            {"type": 10, "content":
                "### 🌍 Global Events\n\n"
                "-# No events are currently active.\n"
                "-# Check back later — events will appear here when they go live!"},
            {"type": 14, "divider": True, "spacing": 1},
            _back_row(user_id),
        ]}])

@bot.tree.command(name="shop", description="Buy boosts, tools and ammo")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def shop_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_shop_components(user_id, "boosts"))
    await check_everything(interaction, user_id)

@bot.tree.command(name="biome", description="Choose your hunting biome")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def biome_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_biome_panel_components(user_id))
    await check_everything(interaction, user_id)

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

@bot.tree.command(name="quests", description="View and claim your daily quests")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def quests_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id:
        return
    init_user(user_id)
    quest_daily_roll_if_needed(user_id)
    _quest_page[user_id] = 0
    await send_v2_followup(interaction, build_quests_components(user_id, 0))

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
                    {"type": 2, "style": 1, "label": "🏕️ Create Tribe",
                     "custom_id": f"tribe_create:{user_id}"},
                ]},
            ]}])
        return
    await send_v2_followup(interaction, build_tribe_components(user_id, tribe_nm, "main"))

def _tribe_info_text(tribe_name: str) -> str:
    td = tribe_data[tribe_name]
    r  = td["roles"]
    total   = 1 + len(r["officer"]) + len(r["members"])
    roster  = ([(r["leader"], TRIBE_EMOJIS["leader"])]
               + [(o, TRIBE_EMOJIS["officer"]) for o in r["officer"]]
               + [(m, "🧑") for m in r["members"]])
    mlist   = "\n".join(
        f"{ic} `{get_username(uid)}` — Lv. {data.get(uid, {}).get('level', '?')}"
        for uid, ic in roster[:25]
    )
    desc = f"\n📝 *{td['description']}*\n" if td.get("description") else ""
    return (
        f"### {TRIBE_EMOJIS['tribe']} {tribe_name}{desc}\n"
        f"{USER_EMOJIS['levels']} Lv. **{td['level']}** · {USER_EMOJIS['xp']} **{td['xp']} XP**\n"
        f"{TRIBE_EMOJIS['members']} **{total}/{td['max_members']}** members\n"
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
        return False, "❌ Invalid user ID."
    if target_id == inviter_id:
        return False, "❌ You can't invite yourself."
    if tribe_name not in tribe_data:
        return False, "❌ Tribe not found."
    td = tribe_data[tribe_name]
    if td["roles"]["leader"] != inviter_id and inviter_id not in td["roles"].get("officer", []):
        return False, "❌ Only the leader or officers can invite."
    init_user(target_id)
    if data[target_id].get("tribe"):
        return False, "❌ That player is already in a tribe."
    if data[target_id].get("tribe_inv"):
        return False, "❌ That player already has a pending invite."
    if 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"]) >= td["max_members"]:
        return False, "❌ Your tribe is full."
    td.setdefault("invites", []).append(target_id)
    async with user_tribe_transaction(inviter_id):
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
    return True, f"✅ Invite sent to <@{target_id}>."

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
        await send_ephemeral_v2(interaction, "❌ You're already in a tribe.", 0xE74C3C)
        return
    if data[user_id].get("tribe_inv"):
        await send_ephemeral_v2(interaction,
            f"❌ Resolve your pending invite first — </mail:{COMMAND_ID.get('mail','0')}>.", 0xF1C40F)
        return
    name = name.strip()
    if not 2 <= len(name) <= 32:
        await send_ephemeral_v2(interaction, "❌ Tribe name must be 2–32 characters.", 0xE74C3C)
        return
    if name in tribe_data:
        await send_ephemeral_v2(interaction, "❌ That tribe name is already taken.", 0xE74C3C)
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
        await send_ephemeral_v2(interaction, "❌ You're not in a tribe.", 0xE74C3C)
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
        await send_ephemeral_v2(interaction, "❌ You're not in a tribe.", 0xE74C3C)
        return
    td      = tribe_data[tribe_nm]
    total_m = 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"])
    is_ldr  = td["roles"]["leader"] == user_id

    if is_ldr and total_m > 1:
        if new_leader is None:
            await send_ephemeral_v2(interaction,
                "❌ You lead this tribe. Re-run `/tribe leave` with `new_leader` set to an existing "
                "member, or hand it off from `/tribe menu` → Actions.", 0xE74C3C)
            return
        nl = str(new_leader.id)
        if nl not in td["roles"]["officer"] + td["roles"]["members"]:
            await send_ephemeral_v2(interaction, "❌ That player isn't in your tribe.", 0xE74C3C)
            return
        async with user_tribe_transaction(user_id):
            for role in ("officer", "members"):
                if nl in td["roles"][role]:      td["roles"][role].remove(nl)
                if user_id in td["roles"][role]: td["roles"][role].remove(user_id)
            td["roles"]["leader"]  = nl
            data[user_id]["tribe"] = None
        await send_ephemeral_v2(interaction,
            f"✅ You left **{tribe_nm}**. <@{nl}> is now the leader.", 0x2ECC71)
        return

    async with user_tribe_transaction(user_id):
        if is_ldr and total_m == 1:
            tribe_data.pop(tribe_nm, None)
        else:
            for role in ("officer", "members"):
                if user_id in td["roles"][role]:
                    td["roles"][role].remove(user_id)
        data[user_id]["tribe"] = None
    await send_ephemeral_v2(interaction, f"✅ You left **{tribe_nm}**.", 0x2ECC71)

@tribe_group.command(name="info", description="View info about a tribe")
@app_commands.describe(name="Tribe name (defaults to your own tribe)")
async def tribe_info_cmd(interaction: discord.Interaction, name: str = None):
    user_id = await _common_init(interaction)
    if not user_id: return
    target = name or data[user_id].get("tribe")
    if not target or target not in tribe_data:
        await send_ephemeral_v2(interaction, "❌ Tribe not found.", 0xE74C3C)
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
    app_commands.Choice(name="Gems (💎)", value="gems"),
])
async def gift_cmd(interaction: discord.Interaction,
                   user: discord.User, format: str,
                   amount: str, sent_message: str = "No message."):
    sender_id = await _common_init(interaction)
    if not sender_id: return
    parsed = parse_amount(amount)
    if parsed is None or parsed <= 0:
        await send_ephemeral_v2(interaction, "❌ Invalid amount.", 0xE74C3C)
        return
    receiver_id = str(user.id)
    if receiver_id == sender_id:
        await send_ephemeral_v2(interaction, "❌ You can't gift yourself.", 0xE74C3C)
        return
    init_user(receiver_id)
    icon = "◈" if format == "money" else emoji("gem")
    if data[sender_id][format] < parsed:
        await send_ephemeral_v2(interaction, f"❌ Not enough {icon}!", 0xE74C3C)
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
        await send_ephemeral_v2(interaction, "✅ You don't need to verify right now!", 0x2ECC71)
        return
    if code.upper() == v["code"].upper():
        async with user_transaction(user_id):
            v["needed"] = False
            v["time"]   = 250
            v["code"]   = generate_verify_code()
        await send_ephemeral_v2(interaction, "### ✅ Verified!\nHappy hunting!", 0x2ECC71)
    else:
        await send_ephemeral_v2(interaction, "### ❌ Wrong Code\nTry again.", 0xE74C3C)

@bot.tree.command(name="invite", description="Invite Idle Hunter to your server!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def invite_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    init_user(user_id)
    url1 = (f"https://discord.com/oauth2/authorize?client_id={bot.user.id}"
            f"&permissions=8&scope=bot%20applications.commands")
    url2 = "https://discord.gg/X9JzdxeS8p"
    await interaction.response.defer(ephemeral=True)
    route = Route("POST", "/webhooks/{application_id}/{token}",
                  application_id=interaction.application_id,
                  token=interaction.token)
    await bot.http.request(route, json={
        "flags": V2_FLAGS,
        "components": [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
            "components": [{"type": 10, "content":
                f"### 🔗 Invite Idle Hunter\n"
                f"[Click here to invite the bot!]({url1})\n"
                f"[Join the support server]({url2})"
            }]}],
        "allowed_mentions": {"parse": []},
    })

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

@bot.tree.command(name="help", description="View all available commands")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def help_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    init_user(user_id)
    await interaction.response.defer()
    await send_v2_followup(interaction, build_help_components(user_id))
    await check_everything(interaction, user_id)

@bot.tree.command(name="crate", description="Buy and open Hunting Crates for rewards")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def crate_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_crate_shop_components(user_id))
    await check_everything(interaction, user_id)

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
        "components": build_rules_components(user_id, 0),
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
        await send_ephemeral_v2(interaction, "❌ You must be at least **Level 5** to send suggestions.", 0xE74C3C)
        return
    now          = time.time()
    last_suggest = data[user_id].get("last_suggest", 0)
    cooldown     = 3600
    if not is_admin(interaction):
        if now - last_suggest < cooldown:
            remaining = int(cooldown - (now - last_suggest))
            mins, secs = remaining // 60, remaining % 60
            await send_ephemeral_v2(interaction,
                f"❌ You can suggest again in **{mins}m {secs}s**.", 0xE74C3C)
            return
        if len(suggestion.strip()) < 20:
            await send_ephemeral_v2(interaction,
                "❌ Suggestion must be at least **20 characters**.", 0xE74C3C)
            return
        if len(title.strip()) < 3:
            await send_ephemeral_v2(interaction,
                "❌ Title must be at least **3 characters**.", 0xE74C3C)
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
                        f"### 💡 New Suggestion\n"
                        f"**From:** {interaction.user.display_name} (`{user_id}`)\n"
                        f"**Level:** {data[user_id]['level']} · "
                        f"**Prestige:** {data[user_id].get('prestige', 0)} · "
                        f"**Caught:** {data[user_id].get('total_caught', 0):,}\n"
                        f"### {title.strip()}\n"
                        f"{suggestion.strip()}"
                    },
                    {"type": 14, "divider": True, "spacing": 1},
                    {"type": 1, "components": [
                        {"type": 2, "style": 3, "label": "✅ Agree (0)",
                         "custom_id": f"suggestion:agree:{user_id}:{msg_id}"},
                        {"type": 2, "style": 2, "label": "➖ Neutral (0)",
                         "custom_id": f"suggestion:neutral:{user_id}:{msg_id}"},
                        {"type": 2, "style": 4, "label": "❌ Disagree (0)",
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
        "### 💡 Suggestion Sent!\nYour suggestion has been forwarded to the developers. Thank you!", 0x2ECC71)

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
        await send_ephemeral_v2(interaction, "❌ Please specify a user to report.", 0xE74C3C)
        return
    if type == "user" and str(target_user.id) == user_id:
        await send_ephemeral_v2(interaction, "❌ You can't report yourself.", 0xE74C3C)
        return
    now         = time.time()
    last_report = data[user_id].get("last_report", 0)
    cooldown    = 1800
    if is_admin(interaction) == False:
        if now - last_report < cooldown:
            remaining = int(cooldown - (now - last_report))
            mins, secs = remaining // 60, remaining % 60
            await send_ephemeral_v2(interaction,
                f"❌ You can submit another report in **{mins}m {secs}s**.", 0xE74C3C)
            return
        if len(description.strip()) < 20:
            await send_ephemeral_v2(interaction,
                "❌ Description must be at least **20 characters**.", 0xE74C3C)
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
                    f"### 🚨 User Report: {title.strip()}\n"
                    f"-# Submitted by: <@{user_id}> ({interaction.user.name})\n"
                    f"**Reported user:** {target_user.display_name} (`{target_user.id}`)\n\n"
                    f"{description.strip()}"
                )
                color = 0xE74C3C
            else:
                content = (
                    f"### 🐛 Bug Report: {title.strip()}\n"
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
                            {"type": 2, "style": 1, "label": "👀 I've also seen this (0)",
                             "custom_id": f"report_btn:also_seen:{user_id}:{msg_id}"},
                            {"type": 2, "style": 3, "label": "✅ Resolved",
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
        "### ✅ Report Submitted\n"
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
update_group = app_commands.Group(
    name="update",
    description="Developer update log",
    allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
)

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
    global UPDATE, LATEST_UPDATE
    await interaction.response.defer(ephemeral=True)

    UPDATE.append({
        "title":     title,
        "message":   message,
        "moderator": str(interaction.user.id),
        "date":      int(time.time()),
        "id":        len(UPDATE) + 1,   # newest = highest ID
    })
    LATEST_UPDATE = UPDATE[-1]
    save_config()

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
            await send_ephemeral_v2(interaction, "❌ Both title and message required for adding.", 0xE74C3C)
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
            await send_ephemeral_v2(interaction, "❌ Queue is empty!", 0xE74C3C)
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
            await send_ephemeral_v2(interaction, "❌ Queue is empty!", 0xE74C3C)
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
        await send_ephemeral_v2(interaction, f"❌ ID must be between 1 and {len(UPDATE)}", 0xE74C3C)
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
                "❌ Both title and message required for changing an update.",
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


@bot.tree.command(name="bot_shutdown", description="Shuts down the bot for maintenance")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(time_min="Minutes until maintenance starts", message="Reason")
async def bot_shutdown_cmd(interaction: discord.Interaction, time_min: int, message: str):
    global maintenance_mode, maintenance_warning, maintenance_channels, maintenance_message, maintenance_time
    maintenance_warning = True
    maintenance_message = message
    maintenance_time    = time_min
    save_config()
    UNIX_TIME = int(time.time()) + (time_min * 60)
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### 🔧 Maintenance Starting <t:{UNIX_TIME}:R>\n"
        f"**Reason:** {message}", 0xE67E22)

    async def start_maintenance():
        await asyncio.sleep(time_min * 60)
        global maintenance_mode
        maintenance_mode = True
        save_config()
        content = (
            f"### 🔧 Bot Maintenance Started\n"
            f"**Idle Hunter is now in maintenance mode.**\n\n"
            f"Reason: {message}\n"
            "All commands are disabled. Data is safe.\n\n"
            "-# Thanks for your patience 🏕️"
        )
        for channel_id in list(maintenance_channels):
            channel = bot.get_channel(channel_id)
            if channel:
                try:
                    route = Route("POST", "/channels/{channel_id}/messages",
                                  channel_id=channel_id)
                    await bot.http.request(route, json={
                        "flags": V2_FLAGS,
                        "components": [{"type": 17, "accent_color": 0xE74C3C, "spoiler": False,
                            "components": [{"type": 10, "content": content}]}],
                        "allowed_mentions": {"parse": []},
                    })
                except Exception:
                    pass

    bot.loop.create_task(start_maintenance())

@bot.tree.command(name="bot_resume", description="Resumes the bot after maintenance")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
async def bot_resume_cmd(interaction: discord.Interaction):
    global maintenance_mode, maintenance_channels, maintenance_warning, maintenance_message, _maintenance_warned
    maintenance_mode    = False
    maintenance_warning = False
    maintenance_message = ""
    _maintenance_warned.clear()
    save_config()
    content = (
        "### ✅ Bot Back Online\n"
        "**Idle Hunter is back online!**\n\n"
        "All commands are now available again.\nHappy hunting! 🏹"
    )
    for channel_id in list(maintenance_channels):
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                route = Route("POST", "/channels/{channel_id}/messages",
                              channel_id=channel_id)
                await bot.http.request(route, json={
                    "flags": V2_FLAGS,
                    "components": [{"type": 17, "accent_color": 0x2ECC71, "spoiler": False,
                        "components": [{"type": 10, "content": content}]}],
                    "allowed_mentions": {"parse": []},
                })
            except Exception:
                pass
    maintenance_channels.clear()
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction, content, 0x2ECC71)

@bot.tree.command(name="check_maintenance", description="Checks the current maintenance status")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
async def check_maintenance(interaction: discord.Interaction):
    if maintenance_mode:
        status = "🔴 **Active** — bot is in maintenance mode."
    elif maintenance_warning:
        UNIX_TIME = int(time.time()) + (maintenance_time * 60)
        status = f"🟡 **Warning active** — maintenance starts <t:{UNIX_TIME}:R>."
    else:
        status = "🟢 **None** — bot is running normally."
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### 🔧 Maintenance Status\n"
        f"**Status:** {status}\n"
        f"**Reason:** {maintenance_message or 'N/A'}\n"
        f"**Users warned:** {len(_maintenance_warned)}\n"
        f"**Channels:** {len(maintenance_channels)}",
        0xE67E22 if (maintenance_mode or maintenance_warning) else 0x2ECC71)

@bot.tree.command(name="setdevmail", description="Sets the developer mail message")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
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
        f"### 📢 Dev Mail Set\n{DEV_MAIL if DEV_MAIL else 'Dev mail cleared.'}", 0x2ECC71)

@bot.tree.command(name="ban", description="Ban a user from using the bot")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(
    user_id="Discord user ID to ban",
    days="Duration in days (0 = permanent)",
    reason="Reason for the ban",
)
async def ban_cmd(interaction: discord.Interaction, user_id: str, days: int, reason: str):
    if not user_id.isdigit():
        await interaction.response.defer(ephemeral=True)
        await send_ephemeral_v2(interaction, "❌ Invalid user ID.", 0xE74C3C)
        return
    await _apply_ban(user_id, days, reason.strip(), by=interaction.user.id)
    duration_str = f"**{days} days**" if days > 0 else "**Permanent**"
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### 🔨 User Banned\n"
        f"<@{user_id}> has been banned.\n"
        f"Duration: {duration_str}\nReason: {reason}", 0xE74C3C)

@bot.tree.command(name="unban", description="Unban a user")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(user_id="Discord user ID to unban")
async def unban_cmd(interaction: discord.Interaction, user_id: str):
    if not user_id.isdigit() or user_id not in data:
        await interaction.response.defer(ephemeral=True)
        await send_ephemeral_v2(interaction, "❌ User not found.", 0xE74C3C)
        return
    async with user_transaction(user_id):
        data[user_id]["ban"]["active"] = False
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### ✅ User Unbanned\n<@{user_id}> has been unbanned.", 0x2ECC71)

@bot.tree.command(name="warn", description="Warn a user")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(user_id="Discord user ID to warn", reason="Reason for the warning")
async def warn_cmd(interaction: discord.Interaction, user_id: str, reason: str):
    if not user_id.isdigit():
        await interaction.response.defer(ephemeral=True)
        await send_ephemeral_v2(interaction, "❌ Invalid user ID.", 0xE74C3C)
        return
    warn_count = await _apply_warn(user_id, reason.strip(), by=interaction.user.id)
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### ⚠️ User Warned\n"
        f"<@{user_id}> has been warned.\n"
        f"Reason: {reason}\nTotal warnings: **{warn_count}**", 0xF1C40F)

def _economy_dashboard_text() -> str:
    all_balances = sorted(d.get("money", 0) for d in data.values())
    n = len(all_balances)
    total_money = sum(all_balances)
    median = all_balances[n // 2] if n else 0
    p90    = all_balances[int(n * 0.9)]  if n else 0
    p99    = all_balances[int(n * 0.99)] if n else 0
    top_holder = max(data.items(), key=lambda x: x[1].get("money", 0), default=(None, {}))

    minted_24h = burned_24h = 0
    cutoff = int(time.time()) - 86400
    try:
        with open(ECONOMY_LOG, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if int(row["ts"]) < cutoff:
                    continue
                delta = int(row["delta"])
                if delta > 0:
                    minted_24h += delta
                else:
                    burned_24h += abs(delta)
    except (FileNotFoundError, OSError, KeyError, ValueError):
        pass

    return (
        f"### 📊 Economy Dashboard\n\n"
        f"**Players:** {n:,}\n"
        f"**Total money in circulation:** ◈ {total_money:,}\n"
        f"**Median balance:** ◈ {median:,}\n"
        f"**P90 balance:** ◈ {p90:,}\n"
        f"**P99 balance:** ◈ {p99:,}\n"
        f"**Top holder:** `{top_holder[1].get('username', '?')}` — ◈ {top_holder[1].get('money', 0):,}\n\n"
        f"**Last 24h:**\n"
        f"-# 🟢 Minted: ◈ {minted_24h:,}\n"
        f"-# 🔴 Burned: ◈ {burned_24h:,}\n"
        f"-# Net: ◈ {minted_24h - burned_24h:,}"
    )

@bot.tree.command(name="economy", description="Economy diagnostics")
@app_commands.check(is_admin)
async def economy_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction, _economy_dashboard_text(), 0x3498DB)

# ─────────────────────────────────────────────
# ADMIN CONTROL PANEL  (/admin)
# ─────────────────────────────────────────────

ADMIN_ACCENT = 0x5865F2

def _maint_status_line() -> str:
    if maintenance_mode:
        return "🔴 **Active** — all non-admin commands are blocked."
    if maintenance_warning:
        ts = int(time.time()) + (maintenance_time * 60)
        return f"🟡 **Warning** — maintenance scheduled <t:{ts}:R>."
    return "🟢 **Normal** — bot is running for everyone."

def _admin_row(*buttons: dict) -> dict:
    return {"type": 1, "components": list(buttons)}

def _admin_btn(label: str, cid: str, style: int = 2) -> dict:
    return {"type": 2, "style": style, "label": label, "custom_id": cid}

# Sections shown in the "jump to a section" dropdown on every admin screen.
_ADMIN_SECTIONS = [
    ("home",     "🏠 Overview",       "Dashboard & maintenance status"),
    ("economy",  "💰 Economy",        "Money & gems — give / take / set"),
    ("progress", "📈 Progression",    "Level, prestige, XP, catches, streak"),
    ("items",    "🎒 Items & Perks",  "Tools, ammo, crates, boosts, premium, titles"),
    ("world",    "🌍 World & State",  "Biome, cooldowns, verify lock, idle"),
    ("player",   "🛡️ Moderation",     "Lookup, ban, unban, warn, clear warnings"),
    ("danger",   "☠️ Danger Zone",    "Reset or delete an entire account"),
    ("maint",    "🔧 Maintenance",    "Maintenance mode & warnings"),
    ("info",     "📊 Server Info",    "Economy dashboard & roster counts"),
]
_ADMIN_SECTION_LABEL = {v: l for v, l, _ in _ADMIN_SECTIONS}

# section -> [(op, dropdown label)]  — the action picker inside each section.
_ADMIN_SECTION_ACTIONS: dict[str, list[tuple[str, str]]] = {
    "economy": [
        ("give_money", "💵 Give money"),
        ("take_money", "💸 Take money"),
        ("set_money",  "🟰 Set money to an exact amount"),
        ("give_gems",  "💎 Give gems"),
        ("take_gems",  "💎 Take gems"),
        ("set_gems",   "🟰 Set gems to an exact amount"),
    ],
    "progress": [
        ("set_level",    "📈 Set level"),
        ("set_prestige", "⭐ Set prestige"),
        ("set_xp",       "✨ Set XP into current level"),
        ("set_caught",   "🎯 Set total animals caught"),
        ("set_streak",   "🔥 Set daily streak"),
    ],
    "items": [
        ("grant_tool",      "🔧 Grant a tool"),
        ("grant_all_tools", "🧰 Grant every tool"),
        ("set_vehicle",     "🚙 Set vehicle"),
        ("give_item",       "🐾 Give animal(s) to inventory"),
        ("clear_inventory", "🗑️ Clear the animal inventory"),
        ("give_ammo",       "🔫 Give ammo"),
        ("give_crate",      "📦 Give crate(s)"),
        ("set_luck",        "🍀 Set personal luck boost %"),
        ("set_sell",        "💲 Set personal sell boost %"),
        ("set_xpb",         "📚 Set personal XP boost %"),
        ("max_boosts",      "🚀 Max all personal boosts"),
        ("toggle_premium",  "⭐ Toggle premium"),
        ("grant_title",     "🏷️ Grant a title"),
    ],
    "world": [
        ("set_biome",       "🌍 Set current biome"),
        ("clear_cooldowns", "⏱️ Clear hunt & daily cooldowns"),
        ("clearverify",     "🔓 Clear verify lock"),
        ("clear_idle",      "💤 Stop idle session"),
    ],
    "player": [
        ("lookup",     "🔍 Look up a player"),
        ("ban",        "🔨 Ban a player"),
        ("unban",      "✅ Unban a player"),
        ("warn",       "⚠️ Warn a player"),
        ("clearwarns", "🧹 Clear all warnings"),
    ],
    "danger": [
        ("reset_account",  "♻️ Reset account to a fresh start"),
        ("delete_account", "🗑️ Delete account (erase all data)"),
    ],
}

_ADMIN_SECTION_HINT = {
    "economy":  "Amounts accept shorthand — `1k`, `2.5m`, `1b`.",
    "progress": "Whole numbers only. Setting the level also zeroes current-level XP.",
    "items":    "Names must match the game exactly (case-insensitive). Animals / ammo / "
                "crates also ask for a quantity.",
    "world":    "Biome accepts the id or the display name (e.g. `rainbow` or `Rainbow Realm`).",
    "player":   "Every action takes a Discord user ID.",
    "danger":   "⚠️ Irreversible. A confirmation step is always shown first.",
}


def _admin_navsel(a: str, current: str) -> dict:
    return {"type": 1, "components": [{
        "type": 3, "custom_id": f"admin:navsel:{a}",
        "placeholder": "📂 Jump to a section…",
        "options": [
            {"label": lbl, "value": val, "description": desc, "default": (val == current)}
            for val, lbl, desc in _ADMIN_SECTIONS
        ],
    }]}


def _admin_actsel(a: str, section: str):
    acts = _ADMIN_SECTION_ACTIONS.get(section)
    if not acts:
        return None
    return {"type": 1, "components": [{
        "type": 3, "custom_id": f"admin:act:{section}:{a}",
        "placeholder": "⚙️ Pick an action…",
        "options": [{"label": lbl, "value": op} for op, lbl in acts],
    }]}


def build_admin_panel(admin_id: str, section: str = "home", note: str = "") -> list:
    a = admin_id
    if section not in _ADMIN_SECTION_LABEL:
        section = "home"

    blocks: list = [
        {"type": 10, "content": f"## 🛠️ Admin Panel — {_ADMIN_SECTION_LABEL[section]}"},
        _admin_navsel(a, section),
    ]
    if note:
        blocks.append({"type": 14, "divider": True, "spacing": 1})
        blocks.append({"type": 10, "content": note})
    blocks.append({"type": 14, "divider": True, "spacing": 1})

    accent = ADMIN_ACCENT

    if section == "home":
        banned = sum(1 for d in data.values() if d.get("ban", {}).get("active"))
        blocks.append({"type": 10, "content":
            f"-# Signed in as <@{a}> · this panel is private to you\n"
            f"**Maintenance:** {_maint_status_line()}\n"
            f"-# 👥 {len(data):,} users · 🏕️ {len(tribe_data):,} tribes · 🔨 {banned:,} banned\n\n"
            "Pick a section from **Jump to a section** above, then choose an action from that "
            "section's menu. Every action asks for a target Discord user ID; economy, progression "
            "and destructive actions show a confirm step."})
        blocks.append(_admin_row(
            _admin_btn("🔧 Maintenance", f"admin:nav:maint:{a}", 1),
            _admin_btn("📊 Server Info", f"admin:nav:info:{a}", 1),
            _admin_btn("🔄 Refresh", f"admin:home:{a}"),
        ))

    elif section == "maint":
        blocks.append({"type": 10, "content":
            f"### 🔧 Maintenance\n"
            f"**Status:** {_maint_status_line()}\n"
            f"**Reason:** {maintenance_message or '—'}\n"
            f"-# Warned users: {len(_maintenance_warned)}"})
        blocks.append(_admin_row(
            _admin_btn("🟢 Disable" if maintenance_mode else "🔴 Enable Now",
                       f"admin:do:maint_toggle:{a}", 3 if maintenance_mode else 4),
            _admin_btn("🟡 Toggle Warning", f"admin:do:maint_warn_toggle:{a}"),
        ))
        blocks.append(_admin_row(
            _admin_btn("✏️ Set Reason", f"admin:modal:maint_msg:{a}"),
            _admin_btn("◀ Overview", f"admin:home:{a}"),
        ))

    elif section == "info":
        banned  = sum(1 for d in data.values() if d.get("ban", {}).get("active"))
        premium = sum(1 for d in data.values() if d.get("premium"))
        blocks.append({"type": 10, "content":
            f"{_economy_dashboard_text()}\n\n"
            f"**Roster:**\n"
            f"-# 👥 Users: {len(data):,}  ·  🏕️ Tribes: {len(tribe_data):,}\n"
            f"-# 🔨 Banned: {banned:,}  ·  {emoji('vip')} Premium: {premium:,}"})
        blocks.append(_admin_row(
            _admin_btn("🔄 Refresh", f"admin:nav:info:{a}"),
            _admin_btn("◀ Overview", f"admin:home:{a}"),
        ))

    else:  # economy / progress / items / world / player / danger
        if section == "danger":
            accent = 0xE74C3C
        blocks.append({"type": 10, "content": f"-# {_ADMIN_SECTION_HINT.get(section, '')}"})
        actsel = _admin_actsel(a, section)
        if actsel:
            blocks.append(actsel)
        blocks.append(_admin_row(_admin_btn("◀ Overview", f"admin:home:{a}")))

    return [{"type": 17, "accent_color": accent, "spoiler": False, "components": blocks}]

# ── Admin action model: modal → validate → confirm (ephemeral) → apply ──

# op -> (modal title, number-field label). Each takes "target user id + one number".
_ADMIN_AMOUNT_OPS = {
    "give_money":   ("💵 Give Money",      "Amount (◈)"),
    "take_money":   ("💸 Take Money",      "Amount (◈)"),
    "set_money":    ("🟰 Set Money",       "New balance (◈)"),
    "give_gems":    ("💎 Give Gems",       "Amount (💎)"),
    "take_gems":    ("💎 Take Gems",       "Amount (💎)"),
    "set_gems":     ("🟰 Set Gems",        "New balance (💎)"),
    "set_level":    ("📈 Set Level",       "New level"),
    "set_prestige": ("⭐ Set Prestige",    "New prestige"),
    "set_xp":       ("✨ Set XP",           "XP into current level"),
    "set_caught":   ("🎯 Set Total Caught", "New total caught"),
    "set_streak":   ("🔥 Set Daily Streak", "New streak"),
    "set_luck":     ("🍀 Set Luck Boost",  "Luck boost %"),
    "set_sell":     ("💲 Set Sell Boost",  "Sell boost %"),
    "set_xpb":      ("📚 Set XP Boost",    "XP boost %"),
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
    "set_biome":   ("🌍 Set Biome",    "Biome id or name",     "e.g. forest / Rainbow Realm", False),
    "grant_tool":  ("🔧 Grant Tool",   "Exact tool name",      "e.g. Longbow",                False),
    "set_vehicle": ("🚙 Set Vehicle",  "Vehicle name or None", "e.g. Helicopter",            False),
    "grant_title": ("🏷️ Grant Title",  "Title text",           "e.g. Beta Tester",           False),
    "give_item":   ("🐾 Give Animals", "Exact animal name",     "e.g. Golden Deer",           True),
    "give_ammo":   ("🔫 Give Ammo",    "Exact ammo name",       "e.g. Silver Bullet",         True),
    "give_crate":  ("📦 Give Crates",  "Exact crate name",      "e.g. Mythic Crate",          True),
}

# op -> modal title. Takes only a target user id.
_ADMIN_UID_OPS = {
    "lookup":          "🔍 Player Lookup",
    "unban":           "✅ Unban Player",
    "clearwarns":      "🧹 Clear Warnings",
    "clearverify":     "🔓 Clear Verify Lock",
    "clear_cooldowns": "⏱️ Clear Cooldowns",
    "clear_inventory": "🗑️ Clear Inventory",
    "clear_idle":      "💤 Stop Idle Session",
    "grant_all_tools": "🧰 Grant All Tools",
    "max_boosts":      "🚀 Max Personal Boosts",
    "toggle_premium":  "⭐ Toggle Premium",
    "reset_account":   "♻️ Reset Account",
    "delete_account":  "🗑️ Delete Account",
}

ADMIN_MAX_MONEY    = 1_000_000_000_000   # per single give/take/set action
ADMIN_MAX_LEVEL    = 100_000
ADMIN_MAX_PRESTIGE = 100_000
ADMIN_MAX_BOOST    = 100_000
ADMIN_MAX_BAN_DAYS = 3650
ADMIN_MAX_GIVE_QTY = 100_000

# op -> section, so a result banner lands back on the right screen.
_ADMIN_OP_SECTION = {op: sec for sec, acts in _ADMIN_SECTION_ACTIONS.items() for op, _ in acts}

# Important actions: an "are you sure?" step is inserted before they run.
_ADMIN_CONFIRM_OPS = {
    "give_money", "take_money", "set_money", "give_gems", "take_gems", "set_gems",
    "set_level", "set_prestige", "set_xp", "set_caught", "set_streak",
    "set_luck", "set_sell", "set_xpb", "max_boosts",
    "grant_all_tools", "clear_inventory", "toggle_premium",
    "ban", "warn", "unban", "clearwarns", "maint_toggle",
    "reset_account", "delete_account",
}

_admin_pending: dict[str, dict] = {}

async def _refresh_admin(interaction: discord.Interaction, admin_id: str, section: str, note: str = ""):
    await smart_update_v2(interaction, build_admin_panel(admin_id, section, note))

def _admin_section_for(op: str) -> str:
    if op in ("maint_toggle", "maint_warn_toggle", "maint_msg"):
        return "maint"
    if op in ("ban", "warn", "unban", "clearwarns", "lookup"):
        return "player"
    return _ADMIN_OP_SECTION.get(op, "home")

def _build_admin_confirm(admin_id: str, token: str, summary: str) -> list:
    return [{"type": 17, "accent_color": 0xE67E22, "spoiler": False, "components": [
        {"type": 10, "content":
            f"### ⚠️ Confirm admin action\n{summary}\n\n-# This is not auto-undoable."},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 4, "label": "✅ Confirm",
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
    if enabled:
        content = ("### 🔧 Maintenance Started\n**Idle Hunter is now in maintenance mode.**\n\n"
                   f"Reason: {maintenance_message or '—'}\n-# Your data is safe. Back soon 🏕️")
        color = 0xE74C3C
    else:
        content = "### ✅ Bot Back Online\n**Idle Hunter is back!** All commands work again. 🏹"
        color = 0x2ECC71
    for cid in list(maintenance_channels):
        try:
            await bot.http.request(
                Route("POST", "/channels/{channel_id}/messages", channel_id=cid),
                json={"flags": V2_FLAGS,
                      "components": [{"type": 17, "accent_color": color, "spoiler": False,
                                      "components": [{"type": 10, "content": content}]}],
                      "allowed_mentions": {"parse": []}})
        except Exception:
            pass
    if not enabled:
        maintenance_channels.clear()
        save_config()

def _amount_summary(op: str, target: str, val: int) -> str:
    return {
        "give_money":   f"Give **◈ {val:,}** to <@{target}>.",
        "take_money":   f"Take **◈ {val:,}** from <@{target}>.",
        "set_money":    f"Set <@{target}>'s money to **◈ {val:,}**.",
        "give_gems":    f"Give **💎 {val:,}** to <@{target}>.",
        "take_gems":    f"Take **💎 {val:,}** from <@{target}>.",
        "set_gems":     f"Set <@{target}>'s gems to **💎 {val:,}**.",
        "set_level":    f"Set <@{target}> to **Level {val:,}** (current-level XP reset to 0).",
        "set_prestige": f"Set <@{target}> to **Prestige {val:,}**.",
        "set_xp":       f"Set <@{target}>'s current-level XP to **{val:,}**.",
        "set_caught":   f"Set <@{target}>'s total caught to **{val:,}**.",
        "set_streak":   f"Set <@{target}>'s daily streak to **{val:,}**.",
        "set_luck":     f"Set <@{target}>'s personal luck boost to **{val:,}%**.",
        "set_sell":     f"Set <@{target}>'s personal sell boost to **{val:,}%**.",
        "set_xpb":      f"Set <@{target}>'s personal XP boost to **{val:,}%**.",
    }.get(op, f"{op}: {val:,} on <@{target}>")


_ADMIN_TEXT_POOL = {
    "grant_tool":  TOOLS,
    "set_vehicle": VEHICLES,
    "give_item":   ANIMAL_DATA,
    "give_ammo":   AMMO,
    "give_crate":  CRATE_TIERS,
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
    pool = _ADMIN_TEXT_POOL.get(op)
    if pool:
        for k in pool:
            if k.lower() == value.lower():
                return k
    return value

def _admin_validate_text(op: str, value: str) -> str | None:
    if op == "set_biome":
        ok = value.lower() in BIOME_NAMES or value.lower() in {v.lower() for v in BIOME_NAMES.values()}
        if not ok:
            return f"❌ Unknown biome `{value}`. Ids: {', '.join(list(BIOME_NAMES)[:6])}…"
        return None
    if op == "grant_title":
        return None if value else "❌ Enter a title."
    if op == "set_vehicle" and value.lower() in ("none", "-", "remove", "clear"):
        return None
    pool = _ADMIN_TEXT_POOL.get(op)
    if pool and not any(k.lower() == value.lower() for k in pool):
        kind = {"grant_tool": "tool", "set_vehicle": "vehicle", "give_item": "animal",
                "give_ammo": "ammo", "give_crate": "crate"}[op]
        sample = ", ".join(list(pool)[:6])
        return f"❌ Unknown {kind} `{value}`. e.g. {sample}…"
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
                note = f"💵 Gave **◈ {amount:,}** to <@{target}> (now ◈ {d['money']:,})."
            elif op == "take_money":
                taken = min(amount, d.get("money", 0))
                add_money(target, -taken, "admin remove")
                note = f"💸 Took **◈ {taken:,}** from <@{target}> (now ◈ {d['money']:,})."
            elif op == "set_money":
                add_money(target, amount - d.get("money", 0), "admin set")
                note = f"🟰 <@{target}>'s money is now **◈ {amount:,}**."
            elif op == "give_gems":
                add_gems(target, amount, "admin grant")
                note = f"💎 Gave **{amount:,}** gems to <@{target}> (now {d['gems']:,})."
            elif op == "take_gems":
                taken = min(amount, d.get("gems", 0))
                add_gems(target, -taken, "admin remove")
                note = f"💎 Took **{taken:,}** gems from <@{target}> (now {d['gems']:,})."
            else:  # set_gems
                add_gems(target, amount - d.get("gems", 0), "admin set")
                note = f"🟰 <@{target}>'s gems are now **{amount:,}**."
        admin_audit(admin_id, op, f"{target} {amount}")
        return "economy", note

    # ── integer stats: level / prestige / xp / caught / streak / boosts ──
    if op in _ADMIN_INT_OPS:
        val = params["value"]
        async with user_transaction(target):
            d = data[target]
            if op == "set_level":
                d["level"], d["xp"] = val, 0
                note = f"📈 <@{target}> is now **Level {val:,}**."
            elif op == "set_prestige":
                d["prestige"] = val
                note = f"⭐ <@{target}> is now **Prestige {val:,}**."
            elif op == "set_xp":
                d["xp"] = val
                note = f"✨ Set <@{target}>'s current-level XP to **{val:,}**."
            elif op == "set_caught":
                d["total_caught"] = val
                note = f"🎯 Set <@{target}>'s total caught to **{val:,}**."
            elif op == "set_streak":
                d["daily_streak"] = val
                d["best_daily_streak"] = max(d.get("best_daily_streak", 0), val)
                note = f"🔥 Set <@{target}>'s daily streak to **{val:,}**."
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
                note = f"🌍 Moved <@{target}> to **{BIOME_NAMES.get(value, value)}**."
            elif op == "grant_tool":
                d.setdefault("owned_tools", [])
                if value not in d["owned_tools"]:
                    d["owned_tools"].append(value)
                note = f"🔧 Granted **{value}** to <@{target}>."
            elif op == "set_vehicle":
                d["vehicle"] = value
                if value != "None":
                    d.setdefault("owned_vehicles", [])
                    if value not in d["owned_vehicles"]:
                        d["owned_vehicles"].append(value)
                note = f"🚙 <@{target}>'s vehicle is now **{value}**."
            elif op == "grant_title":
                d.setdefault("earned_titles", [])
                if value not in d["earned_titles"]:
                    d["earned_titles"].append(value)
                note = f"🏷️ Granted the title **{value}** to <@{target}>."
            elif op == "give_item":
                tool = d.get("tool", "Bare Hands")
                for _ in range(qty):
                    d.setdefault("inv", []).append(value)
                    record_catch(target, value, tool, 0)
                note = f"🐾 Added **{qty:,}× {value}** to <@{target}>'s inventory."
            elif op == "give_ammo":
                inv = d.setdefault("ammo_inv", {})
                inv[value] = min(AMMO_MAX_STACK, inv.get(value, 0) + qty)
                note = f"🔫 <@{target}> now holds **{inv[value]:,}× {value}**."
            elif op == "give_crate":
                inv = d.setdefault("crate_inv", {})
                inv[value] = inv.get(value, 0) + qty
                note = f"📦 Gave **{qty:,}× {value}** to <@{target}> (now {inv[value]:,})."
        admin_audit(admin_id, op, f"{target} {value} x{qty}")
        return sec, note

    # ── uid-only maintenance / state actions ──
    if op == "clearverify":
        async with user_transaction(target):
            v = data[target].setdefault("verify", {})
            v["needed"], v["time"] = False, 250
        admin_audit(admin_id, "clearverify", target)
        return sec, f"🔓 Cleared the verify lock for <@{target}>."
    if op == "clear_cooldowns":
        async with user_transaction(target):
            data[target]["hunt_cd"] = 0
            data[target]["daily_cd"] = 0
        admin_audit(admin_id, "clear_cooldowns", target)
        return sec, f"⏱️ Cleared hunt & daily cooldowns for <@{target}>."
    if op == "clear_inventory":
        async with user_transaction(target):
            data[target]["inv"] = []
        admin_audit(admin_id, "clear_inventory", target)
        return sec, f"🗑️ Cleared <@{target}>'s animal inventory."
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
        return sec, f"🧰 Gave <@{target}> every tool in the game."
    if op == "max_boosts":
        async with user_transaction(target):
            data[target].setdefault("boosts", {}).update(
                {"luck": ADMIN_MAX_BOOST, "sell": ADMIN_MAX_BOOST, "xp": ADMIN_MAX_BOOST})
        admin_audit(admin_id, "max_boosts", target)
        return sec, f"🚀 Maxed <@{target}>'s personal luck / sell / XP boosts."
    if op == "toggle_premium":
        async with user_transaction(target):
            new = not data[target].get("premium", False)
            data[target]["premium"] = new
        admin_audit(admin_id, "toggle_premium", f"{target}={new}")
        return sec, f"{emoji('vip')} Premium for <@{target}> is now **{'ON' if new else 'OFF'}**."
    if op == "reset_account":
        uname = data.get(target, {}).get("username", "")
        async with user_transaction(target):
            data[target] = {}
            init_user(target)
            if uname:
                data[target]["username"] = uname
        admin_audit(admin_id, "reset_account", target)
        return "danger", f"♻️ Reset <@{target}> — brand-new account, username kept."
    if op == "delete_account":
        data.pop(target, None)
        _dirty_users.discard(target)
        try:
            await _backend_delete_user(target)
        except Exception as e:
            logger.exception("delete_account backend delete failed")
            return "danger", f"⚠️ Dropped <@{target}> from memory, but the DB delete failed: {e}"
        admin_audit(admin_id, "delete_account", target)
        return "danger", f"🗑️ Deleted all stored data for `{target}`. They start fresh if they play again."

    if op == "ban":
        days, reason = params["days"], params["reason"]
        await _apply_ban(target, days, reason, by=admin_id)
        admin_audit(admin_id, "ban", f"{target} days={days} reason={reason!r}")
        dur = f"{days} day(s)" if days > 0 else "permanent"
        return "player", f"🔨 Banned <@{target}> ({dur})."
    if op == "warn":
        count = await _apply_warn(target, params["reason"], by=admin_id)
        admin_audit(admin_id, "warn", f"{target} reason={params['reason']!r}")
        return "player", f"⚠️ Warned <@{target}> — now on **{count}** warning(s)."
    if op == "unban":
        async with user_transaction(target):
            data[target].setdefault("ban", {})["active"] = False
        admin_audit(admin_id, "unban", target)
        return "player", f"✅ Unbanned <@{target}>."
    if op == "clearwarns":
        async with user_transaction(target):
            data[target]["warnings"] = []
        admin_audit(admin_id, "clearwarns", target)
        return "player", f"🧹 Cleared all warnings for <@{target}>."
    if op == "maint_toggle":
        global maintenance_mode, maintenance_warning
        maintenance_mode = not maintenance_mode
        if maintenance_mode:
            maintenance_warning = False
            if params.get("channel_id"):
                maintenance_channels.add(int(params["channel_id"]))
            note = "🔴 Maintenance mode **enabled** — non-admins are now blocked."
        else:
            note = "🟢 Maintenance mode **disabled** — the bot is open again."
        save_config()
        admin_audit(admin_id, "maint_toggle", f"mode={maintenance_mode}")
        bot.loop.create_task(_broadcast_maintenance(maintenance_mode))
        return "maint", note

    return _admin_section_for(op), "❌ Unknown action."

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
            await _refresh_admin(interaction, self.admin_id, section, "❌ Invalid user ID.")
            return

        if self.op in _ADMIN_INT_OPS:
            raw = self.amt_in.value.strip().replace(",", "")
            if not raw.isdigit():
                await _refresh_admin(interaction, self.admin_id, section, "❌ Enter a whole number.")
                return
            val    = int(raw)
            lo, hi = _ADMIN_INT_RANGE[self.op]
            if not lo <= val <= hi:
                await _refresh_admin(interaction, self.admin_id, section,
                                     f"❌ Value must be between {lo:,} and {hi:,}.")
                return
            await _admin_stage(interaction, self.admin_id, self.op,
                               {"target": target, "value": val},
                               _amount_summary(self.op, target, val))
            return

        amount = parse_amount(self.amt_in.value.strip())
        if amount is None or amount < 0:
            await _refresh_admin(interaction, self.admin_id, section, "❌ Invalid amount.")
            return
        if self.op in ("give_money", "take_money", "give_gems", "take_gems") and amount <= 0:
            await _refresh_admin(interaction, self.admin_id, section, "❌ Amount must be positive.")
            return
        if amount > ADMIN_MAX_MONEY:
            await _refresh_admin(interaction, self.admin_id, section,
                                 f"❌ Above the per-action cap of **{ADMIN_MAX_MONEY:,}**.")
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
            await _refresh_admin(interaction, self.admin_id, section, "❌ Invalid user ID.")
            return
        value = self.val_in.value.strip()
        if not value:
            await _refresh_admin(interaction, self.admin_id, section, "❌ Enter a value.")
            return
        qty = 1
        if self.wants_qty:
            raw = (self.qty_in.value or "1").strip().replace(",", "")
            if not raw.isdigit() or not (1 <= int(raw) <= ADMIN_MAX_GIVE_QTY):
                await _refresh_admin(interaction, self.admin_id, section,
                                     f"❌ Quantity must be a whole number 1–{ADMIN_MAX_GIVE_QTY:,}.")
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
            await _refresh_admin(interaction, self.admin_id, "player", "❌ Invalid user ID.")
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
            await _refresh_admin(interaction, self.admin_id, "player", "❌ Invalid user ID.")
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
            await _refresh_admin(interaction, self.admin_id, section, "❌ Invalid user ID.")
            return

        if self.op == "lookup":
            init_user(target)
            init_ban_record(target)
            d = data[target]
            b = d.get("ban", {})
            ban_line = ("🔨 Banned" + (f" (until <t:{b['expires_ts']}:R>)" if b.get("expires_ts") else " (permanent)")) \
                       if b.get("active") else "✅ Not banned"
            boosts = d.get("boosts", {})
            note = (
                f"### 🔍 {get_username(target)} (`{target}`)\n"
                f"-# {ban_line}  ·  {(emoji('vip') + ' Premium') if d.get('premium') else 'Free'}\n"
                f"**Level:** {d.get('level', 1):,} (xp {d.get('xp', 0):,})  ·  **Prestige:** {d.get('prestige', 0)}\n"
                f"**Money:** ◈ {d.get('money', 0):,}  ·  **Gems:** 💎 {d.get('gems', 0):,}\n"
                f"**Caught:** {d.get('total_caught', 0):,}  ·  **Streak:** {d.get('daily_streak', 0)}  ·  "
                f"**Biome:** {BIOME_NAMES.get(d.get('biome'), d.get('biome', '—'))}\n"
                f"**Tool:** {d.get('tool', '—')}  ·  **Vehicle:** {d.get('vehicle', '—')}  ·  "
                f"**Tribe:** {d.get('tribe') or '—'}\n"
                f"**Boosts:** 🍀 {boosts.get('luck', 0)}% · 💲 {boosts.get('sell', 0)}% · 📚 {boosts.get('xp', 0)}%\n"
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
            "clear_idle":      f"Stop <@{target}>'s idle session.",
            "grant_all_tools": f"Give <@{target}> **every tool** in the game.",
            "max_boosts":      f"Set <@{target}>'s personal luck / sell / XP boosts to the max.",
            "toggle_premium":  f"Toggle premium status for <@{target}>.",
            "reset_account":   (f"♻️ **RESET <@{target}>** — wipes money, level, XP, prestige, items, "
                                f"tools, boosts, stats and cooldowns back to a brand-new account. "
                                f"Username is kept. Cannot be undone."),
            "delete_account":  (f"🗑️ **DELETE <@{target}>** — erases their row from the database "
                                f"entirely. If they use the bot again they start from zero. "
                                f"Cannot be undone."),
        }
        await _admin_stage(interaction, self.admin_id, self.op,
                           {"target": target}, summaries.get(self.op, "…"))

class AdminMaintMsgModal(_V2Modal, title="✏️ Maintenance Reason"):
    msg_in = discord.ui.TextInput(label="Reason shown to players", style=discord.TextStyle.paragraph, max_length=400)

    def __init__(self, admin_id: str):
        super().__init__()
        self.admin_id = str(admin_id)

    async def on_submit(self, interaction: discord.Interaction):
        global maintenance_message
        maintenance_message = self.msg_in.value.strip()
        save_config()
        admin_audit(self.admin_id, "maint_msg", maintenance_message)
        await _refresh_admin(interaction, self.admin_id, "maint", "✏️ Maintenance reason updated.")

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
    if op == "maint_msg":
        return AdminMaintMsgModal(admin_id)
    return None

# ── Shared ban / warn helpers (also used by the /ban and /warn commands) ──

async def _dm_user_v2(target_id: str, container: list, label: str) -> None:
    """Best-effort DM of a v2 container. Never raises."""
    try:
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
        f"### ⚠️ You have been warned!\n\n"
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

@bot.tree.command(name="admin", description="Open the admin control panel")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
async def admin_cmd(interaction: discord.Interaction):
    admin_id = str(interaction.user.id)
    init_user(admin_id)
    await interaction.response.defer(ephemeral=True)
    await send_v2_followup(interaction, build_admin_panel(admin_id, "home"), ephemeral=True)

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

async def _dm_user(uid: str, content: str) -> bool:
    """Best-effort DM. Returns False (silently) on closed DMs, unknown user,
    rate limits, etc. — notifications are a nice-to-have, never worth a crash."""
    try:
        user = bot.get_user(int(uid)) or await bot.fetch_user(int(uid))
        if not user:
            return False
        await user.send(content)
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
            f"### {emoji('daily')} Your daily reward is ready!\n"
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
            ranked = sorted(data.keys(), key=lambda u: fn(u), reverse=True)
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
                f"### {emoji('leaderboard')} You fell out of the Top 3!\n"
                f"You're no longer in the global Top 3 for **{stat}**.\n"
                "-# Use `/leaderboard` to check your rank, or turn this off in "
                "`/menu` → Settings.")
        _lb_top3_cache[stat] = top3_now

@leaderboard_rank_watch_task.error
async def _lrwte(error): print("Leaderboard rank watch task error:", error)

# ─────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────

_ready_once = False

@bot.event
async def on_ready():
    global _ready_once
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

    await migrate_json_to_sqlite()

    try:
        await load_all_data()
        print("✅ Data loaded")
    except Exception as e:
        _ready_once = False
        print(f"❌ Data load failed: {e}")
        return

    load_runtime_state()

    # Transaction flushes now write only the users changed since the last flush.
    def _flush_dirty_users():
        if not _dirty_users:
            return
        batch_ids = [uid for uid in list(_dirty_users) if uid in data]
        _dirty_users.clear()
        if not batch_ids:
            return
        batch = {uid: data[uid] for uid in batch_ids}

        async def _save_batch():
            try:
                await bulk_save_users(batch)
            except Exception as e:
                # The write failed — put the markers back so the next flush (or
                # the 20s full autosave) retries instead of silently dropping them.
                for uid in batch_ids:
                    _dirty_users.add(uid)
                print(f"incremental user save failed, re-queued {len(batch_ids)}: {e}")

        asyncio.create_task(_save_batch())

    register_save_callbacks(
        _flush_dirty_users,
        lambda: asyncio.create_task(bulk_save_tribes(tribe_data)),
    )

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands  [INSTANCE_ID={INSTANCE_ID}]")
    except Exception as e:
        print("Sync failed:", e)

    await asyncio.to_thread(test_token, BOT_TOKEN, "Main bot")

    await bot.change_presence(activity=discord.Game(name="/menu | Idle Hunter"))

    if not autosave_users.is_running():         autosave_users.start()
    if not autosave_tribes.is_running():        autosave_tribes.start()
    if not autosave_runtime_state.is_running(): autosave_runtime_state.start()
    if not lottery_tick.is_running():           lottery_tick.start()
    if not daily_reminder_task.is_running():    daily_reminder_task.start()
    if not leaderboard_rank_watch_task.is_running(): leaderboard_rank_watch_task.start()

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
        msg = "⚠️ Something went wrong running that command. Please try again."
    try:
        if interaction.response.is_done():
            await send_ephemeral_v2(interaction, msg, 0xE74C3C)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
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
        if data:
            await bulk_save_users(data)
        if tribe_data:
            await bulk_save_tribes(tribe_data)
        _dirty_users.clear()
    except Exception as e:
        print(f"  final user/tribe save failed: {e}")
    try:
        text = json.dumps(_encode_runtime_state(), indent=4, default=str)
        await _locked_write(RUNTIME_STATE_FILE, text)
    except Exception as e:
        print(f"  runtime-state save failed: {e}")
    try:
        await backend._flush_economy_buffer()
    except Exception as e:
        print(f"  economy-buffer flush failed: {e}")
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
