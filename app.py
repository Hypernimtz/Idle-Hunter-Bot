import asyncio, discord, random, time, json, string, requests, secrets
from discord.http import Route
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from collections import Counter
from backend import _flush_users
from game_data import *
from backend import *
from economy import *
from dotenv import load_dotenv
import os, csv
load_dotenv("token.env")

BOT_TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

data       = {}
tribe_data = {}

# ─────────────────────────────────────────────
# ADMINS
# ─────────────────────────────────────────────

BOT_ADMIN_ID = [
    "1286458710146940980",
    "922684194377850911",
]

def is_admin(interaction: discord.Interaction) -> bool:
    return str(interaction.user.id) in BOT_ADMIN_ID

SUGGESTION_CHANNEL_ID = 1503581602234765322
BAN_APPEAL_CHANNEL_ID = 1503975028570718298
REPORTS_CHANNEL_ID    = 1503975073797771284
LOTTERY_CHANNEL_ID    = 1505064052391673958

# ─────────────────────────────────────────────
# GLOBALS
# ─────────────────────────────────────────────

DEV_MAIL              = ""
UPDATE_MSG            = ""
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

def show_incorrect_user_message(user_id: str):
    return (
        f"This panel is controlled by <@{user_id}>.\n"
        "If you want to view it, you will have to run the original command yourself."
    )

# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

def get_tool_tier(tool_name: str) -> int:
    return TOOLS.get(tool_name, {}).get("tier", 1)

def can_hunt_biome(tool_name: str, biome: str) -> bool:
    return get_tool_tier(tool_name) >= BIOME_TOOL_TIER.get(biome, 1)

def get_all_tools_sorted():
    return sorted(TOOLS.items(), key=lambda x: x[1]["tier"])

def tool_needs_ammo(tool_name: str) -> bool:
    return TOOLS.get(tool_name, {}).get("ammo_type") is not None

def get_tool_ammo_type(tool_name: str) -> str | None:
    return TOOLS.get(tool_name, {}).get("ammo_type")

# ─────────────────────────────────────────────
# TUTORIAL HELPERS
# ─────────────────────────────────────────────

TUTORIAL_STEPS = [
    "hunt", "sell", "biome", "shop_tools", "shop_ammo",
    "equip", "daily", "idle", "tribe", "prestige",
]

def init_tutorial(user_id: str):
    data[user_id].setdefault("tutorial", {
        "prompted": False, "enabled": False, "seen": [],
    })
    t = data[user_id]["tutorial"]
    t.setdefault("prompted", False)
    t.setdefault("enabled",  False)
    t.setdefault("seen",     [])

def tutorial_seen(user_id: str, step: str) -> bool:
    return step in data[user_id].get("tutorial", {}).get("seen", [])

def tutorial_mark(user_id: str, step: str):
    t = data[user_id].setdefault("tutorial", {"prompted": False, "enabled": False, "seen": []})
    if step not in t["seen"]:
        t["seen"].append(step)

def tutorial_enabled(user_id: str) -> bool:
    return data[user_id].get("tutorial", {}).get("enabled", False)

def tutorial_prompted(user_id: str) -> bool:
    return data[user_id].get("tutorial", {}).get("prompted", False)

# ─────────────────────────────────────────────
# AMMO HELPERS
# ─────────────────────────────────────────────

def get_equipped_ammo(user_id: str) -> str | None:
    return data[user_id].get("equipped_ammo")

def get_ammo_count(user_id: str, ammo_name: str) -> int:
    return data[user_id].get("ammo_inv", {}).get(ammo_name, 0)

def get_ammo_for_tool(tool_name: str) -> list[str]:
    atype = get_tool_ammo_type(tool_name)
    if not atype:
        return []
    return [name for name, a in AMMO.items() if a["ammo_type"] == atype]

def ammo_compatible_with_tool(ammo_name: str, tool_name: str) -> bool:
    a_type = AMMO.get(ammo_name, {}).get("ammo_type")
    t_type = TOOLS.get(tool_name, {}).get("ammo_type")
    return a_type is not None and a_type == t_type

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
# ANIMALS
# ─────────────────────────────────────────────

def animal_emoji(animal: str) -> str:
    e = ANIMAL_DATA.get(animal, {}).get("emoji", "")
    return e if e else ANIMAL_EMOJI

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

def color_display_name(color_key: str) -> str:
    if color_key.startswith("#"):
        return color_key.upper()
    return COLOR_LABELS.get(color_key, color_key.title())

def _accent(user_id: str) -> int:
    return int(v2_color(user_id)) or 0x2ECC71


# ─────────────────────────────────────────────
# AMOUNT PARSER
# ─────────────────────────────────────────────

def parse_amount(raw: str) -> int | None:
    raw = raw.strip().upper().replace(",", "").replace("_", "")
    for suffix, mult in [("T", 1_000_000_000_000), ("B", 1_000_000_000),
                          ("M", 1_000_000), ("K", 1_000)]:
        if raw.endswith(suffix):
            try:
                return int(float(raw[:-1]) * mult)
            except ValueError:
                return None
    try:
        return int(float(raw))
    except ValueError:
        return None

# ─────────────────────────────────────────────
# PERSISTENCE
# ─────────────────────────────────────────────

def backup_all_runtime_files() -> None:
    for path in (USERS_FILE, TRIBE_FILE, CONFIG_FILE, LOTTERY_FILE):
        backup_json_file(path, BACKUP_DIR)
        prune_backups(path, BACKUP_DIR, MAX_BACKUPS_PER_FILE)


def save_data_users() -> None:
    save_with_retries(USERS_FILE, data)


def save_data_tribe() -> None:
    save_with_retries(TRIBE_FILE, tribe_data)


def load_data_users() -> dict:
    payload = load_json_file(USERS_FILE, {})
    return payload if isinstance(payload, dict) else {}


def load_data_tribe() -> dict:
    payload = load_json_file(TRIBE_FILE, {})
    if not isinstance(payload, dict):
        return {}
    defaults = {
        "description": None, "creator": "0",
        "roles": {"leader": "0", "officer": [], "members": []},
        "banned": [], "level": 1, "xp": 0, "invites": [],
        "premium": False, "max_members": 5,
        "luck_boost": 0, "sell_price_boost": 0, "xp_boost": 0,
    }
    for _, tribe in list(payload.items()):
        if isinstance(tribe, dict):
            for k, v in defaults.items():
                tribe.setdefault(k, v)
            roles = tribe.setdefault("roles", {})
            roles.setdefault("leader", tribe.get("creator", "0"))
            roles.setdefault("officer", [])
            roles.setdefault("members", [])
    return payload


def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "dev_mail": DEV_MAIL,
            "update":   UPDATE_MSG,
            "maintenance": {
                "mode":     maintenance_mode,
                "warning":  maintenance_warning,
                "message":  maintenance_message,
                "channels": list(maintenance_channels),
                "warned":   list(_maintenance_warned),
            }
        }, f, indent=4)

def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "dev_mail": "",
            "update": "",
            "maintenance": {
                "mode": False, "warning": False,
                "message": "", "channels": [], "warned": [],
            }
        }

register_save_callbacks(save_data_users, save_data_tribe)

# Load everything in the correct order
data       = load_data_users()
data = migrate_all_users(data)
tribe_data = load_data_tribe()

_cfg                = load_config()
DEV_MAIL            = _cfg["dev_mail"]
UPDATE_MSG          = _cfg["update"]
_m                  = _cfg["maintenance"]
maintenance_mode    = _m["mode"]
maintenance_warning = _m["warning"]
maintenance_message = _m["message"]
maintenance_channels: set[int] = set(_m["channels"])
_maintenance_warned: set[str]  = set(_m["warned"])
maintenance_time = 0

# ─────────────────────────────────────────────
# VERIFY HELPERS
# ─────────────────────────────────────────────

def generate_verify_code() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=4))

def init_verify(_: str):
    return {"needed": False, "time": 250, "code": generate_verify_code()}

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
        for i, (threshold, rtype, amount) in enumerate(tiers):
            if i <= claimed_up_to:
                title_str = ACHIEVEMENT_TITLES.get(ach_key, {}).get(str(threshold))
                if title_str and title_str not in titles:
                    titles.append(title_str)
    return titles

def get_equipped_title(user_id: str) -> str | None:
    return data[user_id].get("equipped_title")

def sync_earned_titles(user_id: str):
    """Rebuild earned_titles from achievements so nothing is lost on reload."""
    data[user_id]["earned_titles"] = get_earned_titles(user_id)

# ─────────────────────────────────────────────
# USER / TRIBE INIT
# ─────────────────────────────────────────────

def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def init_user(user_id: str):
    user_id = str(user_id)
    today   = today_utc()
    defaults = {
        "schema_version": CURRENT_SCHEMA,"username": get_username(user_id),
        "money": 10000, "level": 1, "xp": 0, "inv": [],
        "gems": 100, "premium": False, "hunt_cd": 0, "daily_cd": 0,
        "color": "green", "biome": "village", "tribe": None, "tribe_inv": None,
        "verify": init_verify(user_id),
        "boosts": {"luck": 0, "sell": 0, "xp": 0},
        "idle": {"active": False, "stacks": 0, "started_at": 0},
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
        },
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

    for k, v in {
        "ammo_used": 0, "lottery_wins": 0, "tools_used": [], "events_completed": 0,
        "total_xp_earned": 0, "bj_wins": 0, "cf_wins": 0, "rl_wins": 0,
        "rps_wins": 0, "slots_wins": 0,
    }.items():
        data[user_id]["stats"].setdefault(k, v)

    v = data[user_id].setdefault("verify", {})
    v.setdefault("needed", False); v.setdefault("time", 250); v.setdefault("code", generate_verify_code())
    b = data[user_id].setdefault("boosts", {})
    b.setdefault("luck", 0); b.setdefault("sell", 0); b.setdefault("xp", 0)
    idle = data[user_id].setdefault("idle", {})
    idle.setdefault("active", False); idle.setdefault("stacks", 0); idle.setdefault("started_at", 0)
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

def add_money(user_id: str, amount: int, source: str) -> None:
    data[user_id]["money"] += amount
    if amount != 0:
        log_economy_event(user_id, source, amount, data[user_id]["money"])

def spend_money(user_id: str, amount: int, source: str) -> bool:
    if data[user_id]["money"] < amount:
        return False
    data[user_id]["money"] -= amount
    log_economy_event(user_id, source, -amount, data[user_id]["money"])
    return True

def spend_gems(user_id: str, amount: int, source: str) -> bool:
    if data[user_id]["gems"] < amount:
        return False
    data[user_id]["gems"] -= amount
    log_economy_event(user_id, source, -amount, data[user_id]["gems"], currency="gems")
    return True

def add_gems(user_id: str, amount: int, source: str) -> None:
    data[user_id]["gems"] += amount
    if amount != 0:
        log_economy_event(user_id, source, amount, data[user_id]["gems"], currency="gems")

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
    vehicle_cd   = vehicle_info.get("boost_cd", 0)
    vehicle_luck = vehicle_info.get("boost_luck", 0)
    total_luck   = personal.get("luck", 0) + t_luck + prestige_b + tool_luck + ammo_b["luck"] + vehicle_luck
    return {
        "luck":       total_luck,
        "sell":       personal.get("sell", 0) + t_sell + prestige_b + ammo_b["sell"],
        "xp":         personal.get("xp",   0) + t_xp   + prestige_b + tool_xp + ammo_b["xp"],
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
    # save_data_users() ← DELETE this line
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
        return {"tickets": {}, "last_winner": None, "next_ts": 0, "pool": 0}

def save_lottery(ld: dict):
    with open("lottery.json", "w") as f:
        json.dump(ld, f, indent=4)

def lottery_next_midnight() -> int:
    now = datetime.now(timezone.utc)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(nxt.timestamp())

lottery_data = load_lottery()
if lottery_data["next_ts"] == 0:
    lottery_data["next_ts"] = lottery_next_midnight()
    save_lottery(lottery_data)

# ─────────────────────────────────────────────
# IDLE HELPERS
# ─────────────────────────────────────────────

def biome_level(biome: str) -> int:
    return next((lvl for k, lvl in BIOME_LEVELS if k == biome), 1)

def idle_rate_per_hour(user_id: str) -> int:
    biome = data[user_id].get("biome", "village")
    return (biome_level(biome) + data[user_id]["level"]) * 100

def idle_cost_for_stack(current_stacks: int) -> int:
    return IDLE_COST * (IDLE_STACK_MULTIPLIER ** current_stacks)

def collect_idle(user_id: str) -> int:
    idle = data[user_id]["idle"]
    if not idle["active"] or idle["stacks"] <= 0 or idle.get("started_at", 0) == 0:
        return 0
    now    = time.time()
    earned = int(((now - idle["started_at"]) / 3600) * idle_rate_per_hour(user_id) * idle["stacks"])
    add_money(user_id, earned, "idle")
    data[user_id]["total_money_earned"] = data[user_id].get("total_money_earned", 0) + earned
    idle["started_at"] = now
    return earned

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
        save_data_users()
        return False
    return True

def get_ban(user_id: str) -> dict:
    return data.get(user_id, {}).get("ban", {})

# ─────────────────────────────────────────────
# USERNAME HELPERS
# ─────────────────────────────────────────────

def get_username(user_id: int) -> str:
    global BOT_TOKEN
    if user_id not in data or data[user_id].get("username", "") == "":
        url     = f"https://discord.com/api/v10/users/{user_id}"
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        response = requests.get(url, headers=headers)
        get = response.json()
        if "username" not in get:
            return "Unknown User"
        username = get["username"]
        if user_id in data:
            data[user_id]["username"] = username
        return username
    else:
        return data[user_id]["username"]

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

async def send_v2(interaction: discord.Interaction, components: list):
    await _raw(interaction, {
        "type": 4,
        "data": {"flags": V2_FLAGS, "components": components, "allowed_mentions": {"parse": []}}
    })

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
    if interaction.response.is_done():
        await edit_v2(interaction, components)
    else:
        await update_v2(interaction, components)

async def send_v2_followup(interaction: discord.Interaction, components: list):
    route = Route(
        "POST", "/webhooks/{application_id}/{token}",
        application_id=interaction.application_id,
        token=interaction.token,
    )
    await interaction.client.http.request(
        route,
        json={"flags": V2_FLAGS, "components": components, "allowed_mentions": {"parse": []}}
    )

async def send_ephemeral_v2(interaction: discord.Interaction, content: str, color: int = 0xE74C3C):
    """Send a quick ephemeral v2 container. Works after defer via followup route."""
    route = Route(
        "POST", "/webhooks/{application_id}/{token}",
        application_id=interaction.application_id,
        token=interaction.token,
    )
    await interaction.client.http.request(route, json={
        "flags": V2_FLAGS | 64,
        "components": [{"type": 17, "accent_color": color, "spoiler": False,
            "components": [{"type": 10, "content": content}]}],
        "allowed_mentions": {"parse": []},
    })

async def send_ephemeral_embed(interaction, description, color):
    """Legacy compat — redirects to v2 ephemeral."""
    color_int = int(color) if not isinstance(color, int) else color
    await send_ephemeral_v2(interaction, description, color_int)

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
        f"### 📬 You have new mail!\nUse </mail:{mail_cmd_id}> to check your mailbox.",
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
    save_data_users()

# ─────────────────────────────────────────────
# VERIFY EMBED (v2)
# ─────────────────────────────────────────────

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
                    "## 🔒 Verification Required\n"
                    f"Hey, <@{user_id}>! Just checking if all is well!\n\n"
                    f"Use </verify:{COMMAND_ID.get('verify','0')}> "
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
    cmd_id  = COMMAND_ID.get("verify", "0")
    content = (
        f"### 🔒 Verification Required\n"
        f"Use </verify:{cmd_id}> to continue.\n"
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
    init_user(user_id)
    tick_verify(user_id)
    if data[user_id]["verify"]["needed"]:
        return {"ok": False, "verify": True}

    now = time.time()
    cd  = data[user_id]["hunt_cd"]
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
        xp_earned    = int(random.randint(10, 50) * (1 + xp_boost / 100))
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

    level_ups = 0
    while data[user_id]["xp"] >= xp_for_level(data[user_id]["level"]):
        data[user_id]["xp"]    -= xp_for_level(data[user_id]["level"])
        data[user_id]["level"] += 1
        level_ups += 1

    tip = random.choice(TIPS) if random.randint(1, TIP_CHANCE) == 1 else None

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
        "level_ups": level_ups, "tip": tip,
        "verify": False,
        "next_hunt_ts": int(now + HUNT_COOLDOWN),
        "tool": tool_name, "ammo": ammo_name, "remaining_ammo": remaining_ammo,
    }

# ─────────────────────────────────────────────
# SELL ALL
# ─────────────────────────────────────────────

def sell_all_inv(user_id: str) -> dict:
    inv = data[user_id]["inv"]
    if not inv:
        return {"total": 0, "count": 0}
    sell_boost = get_total_boosts(user_id)["sell"]
    total      = sum(int(ANIMAL_DATA.get(a, {}).get("value", 0) * (1 + sell_boost / 100)) for a in inv)
    count      = len(inv)
    data[user_id]["inv"]    = []
    add_money(user_id, total, "sell all")
    data[user_id]["total_money_earned"] = data[user_id].get("total_money_earned", 0) + total
    return {"total": total, "count": count}

# ─────────────────────────────────────────────
# PROGRESS BAR / FORMAT HELPERS
# ─────────────────────────────────────────────

def _progress_bar(current: int, maximum: int, width: int = 32) -> str:
    if maximum <= 0:
        return f"[{'█' * width}] 100%"
    pct    = min(current / maximum, 1.0)
    filled = int(pct * width)
    empty  = width - filled
    return f"[{'█' * filled}{'░' * empty}] {pct*100:.1f}%"

def _fmt(n: int) -> str:
    return f"{n:,}"

def _reward_str(rtype: str, amount: int) -> str:
    icon = "◈" if rtype == "money" else "💎"
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
    }

    for ach_key, tiers in ACHIEVEMENTS.items():
        label         = ACH_LABELS.get(ach_key, ach_key.replace("_", " ").title())
        claimed_up_to = d["achievements"].get(ach_key, {}).get("claimed_up_to", -1)
        current_val   = ACH_SOURCES.get(ach_key, 0)

        # Each achievement group starts on its own page
        if cur_lines > 0:
            flush()

        cur_page.append(f"### 🏅 {label}")
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
                cur_page.append(f"### 🏅 {label} (cont.)")
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
        f"### 🏅 Achievements & Badges\n\n"
        f"{title_line}"
        f"🏅 Achievements: **{total_ach}/{total_possible}**\n"
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
    content = f"### 🏅 Achievements — Page {page+1}/{total}\n\n{pages[page]}"
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
    content = f"### 🎖️ Badges — Page {page+1}/{total}\n\n{pages[page]}"
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

    idle    = d.get("idle", {})
    stacks  = idle.get("stacks", 0)
    pending = 0
    if idle.get("active") and stacks > 0:
        elapsed = (time.time() - idle.get("started_at", time.time())) / 3600
        pending = int(elapsed * idle_rate_per_hour(user_id) * stacks)

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
        f"{USER_EMOJIS['levels']} Lv. **{d['level']}** ({d['xp']:,}/{xp_for_level(d['level']):,} XP) · "
        f"⭐ Prestige **{prestige}**\n"
        f"**◈ {d['money']:,}** · 💎 **{d['gems']}**\n\n"
        f"{BIOME_EMOJIS[biome]} **{BIOME_NAMES[biome]}** · "
        f"{TOOLS[tool_name]['emoji']} **{tool_name}** (T{get_tool_tier(tool_name)})\n"
        f"🔸 Ammo: {ammo_line}\n"
        f"🚗 Vehicle: {vehicle_line}\n"
        f"Tribe: {TRIBE_EMOJIS['tribe']} {tribe_line}\n\n"
        f"{USER_EMOJIS['luck_boost']} **{boosts['luck']}%** · "
        f"{USER_EMOJIS['sell_boost']} **{boosts['sell']}%** · "
        f"{USER_EMOJIS['xp_boost']} **{boosts['xp']}%**\n\n"
        f"💤 Idle stacks: **{stacks}** · Pending: **◈ {pending:,}**\n\n"
        f"🎒 Inventory ({len(inv)} items · ◈ {sell_val:,}):\n"
        f"{inv_lines}"
    )

    dropdown = {"type": 1, "components": [{"type": 3,
        "custom_id": f"menu:nav:{user_id}",
        "placeholder": "📋 Navigate...",
        "min_values": 1, "max_values": 1, "flows": {},
        "options": [
            {"label": "Hunt",         "emoji": {"name": "🏹"},  "value": "hunt",         "description": "Go hunting in your current biome"},
            {"label": "Shop",         "emoji": {"name": "🏪"},  "value": "shop",         "description": "Buy boosts, tools and ammo"},
            {"label": "Biome",        "emoji": {"name": "🗺️"},  "value": "biome",        "description": "Change your hunting biome"},
            {"label": "Color",        "emoji": {"name": "🎨"},  "value": "color",        "description": "Change your embed color"},
            {"label": "Daily",        "emoji": {"name": "📅"},  "value": "daily",        "description": "Claim your daily reward"},
            {"label": "Prestige",     "emoji": {"name": "⭐"},  "value": "prestige",     "description": "Prestige for permanent boosts"},
            {"label": "Idle",         "emoji": {"name": "💤"},  "value": "idle",         "description": "Manage your idle income"},
            {"label": "Equip",        "emoji": {"name": "🔧"},  "value": "equip",        "description": "Equip tools, ammo and vehicles"},
            {"label": f"Mail{mail_indicator}", "emoji": {"name": "📬"}, "value": "mail", "description": "Check your mailbox"},
            {"label": "Tribe",        "emoji": {"id": "1500237653591851080", "name": "Bot_Tribe"}, "value": "tribe", "description": "View your tribe"},
            {"label": "Profile",      "emoji": {"id": "1500237646121930863", "name": "User_Profile"}, "value": "profile", "description": "View your profile"},
            {"label": "Leaderboard",  "emoji": {"name": "🏆"},  "value": "leaderboard", "description": "View global leaderboards"},
            {"label": "Lottery",      "emoji": {"name": "🎰"},  "value": "lottery",      "description": "Buy tickets for the daily lottery"},
            {"label": "Gamble",       "emoji": {"name": "🎲"},  "value": "gamble",       "description": "Try your luck at mini-games"},
            {"label": "Progression",  "emoji": {"name": "🏅"},  "value": "progression",  "description": "View your achievements, badges, and titles"},
            {"label": "Events",       "emoji": {"name": "🌍"},  "value": "events",       "description": "View ongoing global events"},
            {"label": "Update",       "emoji": {"name": "📋"},  "value": "update",       "description": "View the latest update"},
        ]
    }]}

    row2 = {"type": 1, "components": [
        {"type": 2, "style": 5, "label": "🔗 Invite Bot",
         "url": f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"},
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

def build_profile_components(user_id: str, display_name: str,
                              active_panel: str = "main", viewer_id: str = None) -> list:
    nav_id    = viewer_id or user_id
    d         = data[user_id]
    boosts    = get_total_boosts(user_id)
    biome     = d.get("biome", "village")
    tool_name = d.get("tool", "Bare Hands")
    tribe_nm  = d.get("tribe")
    tribe_inv = d.get("tribe_inv")
    prestige  = d.get("prestige", 0)
    inv       = d.get("inv", [])
    sell_val  = inv_sell_value(user_id)

    idle    = d.get("idle", {})
    stacks  = idle.get("stacks", 0)
    pending = 0
    if idle.get("active") and stacks > 0:
        elapsed = (time.time() - idle.get("started_at", time.time())) / 3600
        pending = int(elapsed * idle_rate_per_hour(user_id) * stacks)

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

    stats = (
        f"### {USER_EMOJIS['profile']} {display_name}'s Profile\n"
        f"{title_line}"
        f"{USER_EMOJIS['levels']} Lv. **{d['level']}** ({d['xp']:,}/{xp_for_level(d['level']):,} XP) · "
        f"⭐ Prestige **{prestige}**\n"
        f"**◈ {d['money']:,}** · 💎 **{d['gems']}**\n"
        f"{BIOME_EMOJIS[biome]} **{BIOME_NAMES[biome]}** · "
        f"{TOOLS[tool_name]['emoji']} **{tool_name}** (T{get_tool_tier(tool_name)})\n"
        f"🔸 Ammo: {ammo_line}\n"
        f"🚗 Vehicle: {vehicle_line}\n"
        f"{TRIBE_EMOJIS['tribe']} {tribe_line}\n"
        f"{color_label}\n\n"
        f"{badge_line}"
        f"{USER_EMOJIS['luck_boost']} Luck **{boosts['luck']}%** · "
        f"{USER_EMOJIS['sell_boost']} Sell **{boosts['sell']}%** · "
        f"{USER_EMOJIS['xp_boost']} XP **{boosts['xp']}%**\n\n"
        f"💤 Idle stacks: **{stacks}** · Pending: **◈ {pending:,}**\n\n"
        f"🎒 Inventory ({len(inv)} items · ◈ {sell_val:,}):\n"
    )
    row_1 = {"type": 1, "components": [
        {"type": 2, "style": 3 if active_panel == "main" else 1,
         "label": "Main Profile", "custom_id": f"profile:main:{user_id}"},
        {"type": 2, "style": 3 if active_panel == "inventory" else 1,
         "label": "Inventory", "custom_id": f"profile:inventory:{user_id}"},
        {"type": 2, "style": 3 if active_panel == "statistics" else 1,
         "label": "Statistics", "custom_id": f"profile:statistics:{user_id}"},
    ]}
    row_2 = {"type": 1, "components": [
        {"type": 2, "style": 3 if active_panel == "leaderboard" else 1,
         "label": "Rankings", "custom_id": f"profile:leaderboard:{user_id}"},
        {"type": 2, "style": 3 if active_panel == "log" else 1,
         "label": "Hunting Log", "custom_id": f"profile:log:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Menu",
         "custom_id": f"nav:menu:{nav_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": stats},
        {"type": 14, "divider": True, "spacing": 1},
        row_1, row_2,
    ]}]

# ─────────────────────────────────────────────
# STATISTICS PANEL
# ─────────────────────────────────────────────

def build_statistics_components(user_id: str, display_name: str) -> list:
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
        f"### {USER_EMOJIS['stats']} {display_name}'s Statistics\n\n"
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
    row_1 = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "Main Profile",  "custom_id": f"profile:main:{user_id}"},
        {"type": 2, "style": 1, "label": "Inventory",     "custom_id": f"profile:inventory:{user_id}"},
        {"type": 2, "style": 3, "label": "Statistics",    "custom_id": f"profile:statistics:{user_id}"},
    ]}
    row_2 = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "Rankings",      "custom_id": f"profile:leaderboard:{user_id}"},
        {"type": 2, "style": 1, "label": "Hunting Log",   "custom_id": f"profile:log:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Menu",        "custom_id": f"nav:menu:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        row_1, row_2,
    ]}]

# ─────────────────────────────────────────────
# INVENTORY PANEL
# ─────────────────────────────────────────────

def build_inventory_components(user_id: str, display_name: str) -> list:
    d           = data[user_id]
    inv         = d.get("inv", [])
    sell_value  = inv_sell_value(user_id)
    total_items = len(inv)
    if not inv:
        inventory_text = "-# Inventory is empty."
    else:
        counts = Counter(inv)
        inventory_text = "\n".join(
            f"-# {animal_emoji(a)} **{a}** ×{c}" for a, c in counts.most_common()
        )
    content = (
        f"### {USER_EMOJIS['profile']} {display_name}'s Inventory\n"
        f"🎒 Total items: **{total_items}** · Worth: **◈ {sell_value:,}**\n\n"
        f"{inventory_text}"
    )
    row_1 = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "Main Profile",  "custom_id": f"profile:main:{user_id}"},
        {"type": 2, "style": 3, "label": "Inventory",     "custom_id": f"profile:inventory:{user_id}"},
        {"type": 2, "style": 1, "label": "Statistics",    "custom_id": f"profile:statistics:{user_id}"},
    ]}
    row_2 = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "Rankings",      "custom_id": f"profile:leaderboard:{user_id}"},
        {"type": 2, "style": 1, "label": "Hunting Log",   "custom_id": f"profile:log:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Menu",        "custom_id": f"nav:menu:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        row_1, row_2,
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

    tip_line = f"\n-# 💡 {result['tip']}" if result.get("tip") else ""

    ammo_name = result.get("ammo")
    if ammo_name:
        remaining = result.get("remaining_ammo", 0)
        a_info    = AMMO.get(ammo_name, {})
        ammo_line = f"\n-# 🔸 {a_info.get('emoji','')} **{ammo_name}** — {remaining} left"
    else:
        ammo_line = ""

    title_line = ""
    equipped_title = d.get("equipped_title")
    if equipped_title:
        title_line = f'-# 🏷️ *"{equipped_title}"*\n'

    stats_block = (
        f"{title_line}"
        f"-# **◈ {result['balance']:,}**\n"
        f"-# {USER_EMOJIS['xp']} **+{result['total_xp']:,} XP**\n"
        f"-# {USER_EMOJIS['levels']} Lv. **{result['level']:,}** "
        f"({result['xp']:,}/{result['xp_needed']:,})\n"
        f"-# {BIOME_EMOJIS[result['biome']]} {result['biome_name']}\n"
        f"-# 🎒 Inventory: **{inv_count}** · Sell value: **◈ {sell_val:,}**"
        f"{ammo_line}{level_line}{tip_line}"
    )

    catch_parts = []
    for c in result["catches"]:
        animal      = c["animal"]
        rarity      = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
        rarity_icon = RARITY_ICONS.get(rarity, "")
        rare_tag    = " · ✨ **Rare Catch!**" if c["is_rare"] else ""
        a_em        = animal_emoji(animal)
        catch_parts.append(
            f"You caught a **{a_em} {animal}**!\n"
            f"-# {rarity_icon} {rarity.title()}{rare_tag}\n"
            f"-# +{c['xp_earned']:,} XP · ◈ {c['sell_value']:,}"
        )

    title_content = (
        f"### {result['biome_emoji']} {d.get('_display_name', 'Hunter')}'s "
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
        {"type": 10, "content": "\n\n".join(catch_parts)},
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
            f"-# Cosmetic only."
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
            ps        = (f"💎{item['price']}" if item["currency"] == "gems"
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
        header = f"### 🏪 Shop — Boosts\n**◈ {d['money']:,}** · 💎 **{d['gems']}**"
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
        header     = f"### 🏪 Shop — Tools\n**◈ {d['money']:,}** · 💎 **{d['gems']}**"
        item_sections = []
        for name, t in page_tools:
            already = name in owned
            ps      = ("✅ Owned" if already
                       else (f"◈ {t['price']:,}" if t["currency"] == "money" else f"💎{t['price']}"))
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
            f"**◈ {d['money']:,}** · 💎 **{d['gems']}**\n"
            f"**— {AMMO_TYPE_LABELS[current_type]} —** *(for: {compat_tools})*"
        )
        item_sections = []
        for name in ammo_names:
            a         = AMMO[name]
            owned_qty = d.get("ammo_inv", {}).get(name, 0)
            ps        = (f"◈ {a['price']:,}/shot" if a["currency"] == "money"
                         else f"💎{a['price']}/shot")
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
        header        = f"### 🏪 Shop — Vehicles\n**◈ {d['money']:,}** · 💎 **{d['gems']}**"
        item_sections = []
        for name, v in page_vehicles:
            already  = name in owned_v
            is_equip = name == equipped_v
            ps       = ("✅ Equipped" if is_equip else
                        ("📦 Owned" if already else
                         (f"◈ {v['price']:,}" if v["currency"] == "money" else f"💎{v['price']}")))
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

def build_tutorial_optin(user_id: str) -> list:
    content = (
        "### 👋 Hey, first time hunting?\n"
        "I can guide you through the basics as you play — "
        "short tips will pop up after each new thing you try.\n\n"
        "-# You can turn this off any time with `/tutorial off`."
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "Yes, guide me!",
             "custom_id": f"tutorial:optin:yes:{user_id}"},
            {"type": 2, "style": 2, "label": "No thanks",
             "custom_id": f"tutorial:optin:no:{user_id}"},
        ]},
    ]}]

def build_tutorial_step(user_id: str, step: str) -> list | None:
    tips = {
        "sell": (
            "### 💰 Nice catch! Now sell it.\n"
            "Hit **Sell All** on the hunt screen to cash everything in.\n"
            "-# Sell boost increases how much ◈ you get per animal."
        ),
        "biome": (
            "### 🗺️ Try a new biome!\n"
            "Better biomes have rarer animals and higher payouts.\n"
            "Use `/biome` to switch once you level up.\n"
            "-# Each biome has a minimum level and tool tier requirement."
        ),
        "shop_tools": (
            "### 🔧 Upgrade your tool!\n"
            "Better tools catch more animals per hunt and boost XP.\n"
            "Open `/shop` → Tools to see what's available.\n"
            "-# Higher tier tools unlock higher tier biomes."
        ),
        "shop_ammo": (
            "### 🔸 Some tools need ammo!\n"
            "Buy ammo in `/shop` → Ammo, then equip via `/equip`.\n"
            "-# Running out of ammo mid-hunt will block hunting."
        ),
        "equip": (
            "### ⚙️ Equip your gear!\n"
            "Purchases don't auto-equip — use `/equip` to switch tools and load ammo.\n"
            "-# Vehicles reduce your hunt cooldown."
        ),
        "daily": (
            "### 📅 Claim your daily!\n"
            "Free ◈ or 💎 every day — use `/daily`.\n"
            "-# Keep a streak for a bonus multiplier!"
        ),
        "idle": (
            "### 💤 Earn while you're away!\n"
            "Use `/idle` to hire stacks that earn ◈ passively.\n"
            "-# Each stack costs more but adds up fast."
        ),
        "tribe": (
            "### 🏕️ Join a tribe!\n"
            "Tribes share Luck, Sell, and XP boosts across all members.\n"
            "-# Use `/id` to get a friend's user ID."
        ),
        "prestige": (
            "### ⭐ Prestige is the endgame!\n"
            "Hit Level 1,000 and ◈ 1B? You can `/prestige` for a "
            "**permanent +20% to all boosts**.\n"
            "-# Gems, tools, tribe and ammo are kept on prestige."
        ),
    }
    text = tips.get(step)
    if not text:
        return None
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": text},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "Got it 👍",
             "custom_id": f"tutorial:dismiss:{user_id}"},
            {"type": 2, "style": 4, "label": "Stop tips",
             "custom_id": f"tutorial:stop:{user_id}"},
        ]},
    ]}]

async def maybe_tutorial_tip(interaction: discord.Interaction, user_id: str, step: str):
    init_tutorial(user_id)
    if not tutorial_enabled(user_id):
        return
    if tutorial_seen(user_id, step):
        return
    comps = build_tutorial_step(user_id, step)
    if not comps:
        return
    tutorial_mark(user_id, step)
    all_done = all(tutorial_seen(user_id, s) for s in TUTORIAL_STEPS if s != "hunt")
    if all_done:
        data[user_id]["tutorial"]["enabled"] = False
    save_data_users()
    try:
        route = Route("POST", "/webhooks/{application_id}/{token}",
                      application_id=interaction.application_id, token=interaction.token)
        await interaction.client.http.request(route, json={
            "flags": V2_FLAGS | 64, "components": comps, "allowed_mentions": {"parse": []},
        })
        if all_done:
            help_cmd_id = COMMAND_ID.get("help", "")
            done_comps = [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
                "components": [{"type": 10, "content":
                    f"### 🎉 You're all set!\nYou've covered all the basics — happy hunting!\n\n"
                    f"-# Check out all commands in </help:{help_cmd_id}>."
                }]}]
            await interaction.client.http.request(route, json={
                "flags": V2_FLAGS | 64, "components": done_comps, "allowed_mentions": {"parse": []},
            })
    except Exception as e:
        print(f"Tutorial tip error ({step}):", e)

async def maybe_tutorial_optin(interaction: discord.Interaction, user_id: str):
    init_tutorial(user_id)
    if tutorial_prompted(user_id):
        return
    data[user_id]["tutorial"]["prompted"] = True
    save_data_users()
    try:
        route = Route("POST", "/webhooks/{application_id}/{token}",
                      application_id=interaction.application_id, token=interaction.token)
        await interaction.client.http.request(route, json={
            "flags": V2_FLAGS | 64,
            "components": build_tutorial_optin(user_id),
            "allowed_mentions": {"parse": []},
        })
    except Exception as e:
        print("Tutorial opt-in error:", e)

# ─────────────────────────────────────────────
# REMAINING PANELS (idle, daily, prestige, update, lottery, gamble, etc.)
# ─────────────────────────────────────────────

def build_update_components(user_id: str) -> list:
    content = (
        f"### 📋 Latest Update\n\n"
        f"{UPDATE_MSG if UPDATE_MSG else '-# No update posted yet.'}"
    )
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        _back_row(user_id),
    ]}]

def build_idle_components(user_id: str) -> list:
    idle   = data[user_id]["idle"]
    rate   = idle_rate_per_hour(user_id)
    stacks = idle["stacks"]
    if idle["active"] and stacks > 0:
        elapsed = (time.time() - idle["started_at"]) / 3600
        pending = int(elapsed * rate * stacks)
        status  = f"🟢 Active · **{stacks}** stack(s) · Pending: **◈ {pending:,}**"
    else:
        status = "🔴 Inactive"
    next_cost = idle_cost_for_stack(stacks)
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": (
            f"### 💤 Idle Manager\n"
            f"{status}\n\n"
            f"-# 📈 Rate: **◈ {rate:,}/hr** per stack\n"
            f"-# Balance: **◈ {data[user_id]['money']:,}**\n"
            f"-# Next stack cost: **◈ {next_cost:,}** (×{IDLE_STACK_MULTIPLIER} each)"
        )},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "📥 Collect",    "custom_id": f"idle:collect:{user_id}"},
            {"type": 2, "style": 1, "label": "👷 Hire Stack", "custom_id": f"idle:hire:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",        "custom_id": f"nav:back:{user_id}"},
        ]},
    ]}]

def build_daily_components(user_id: str, claimed: bool = False,
                            reward_type: str = "", reward_amt: int = 0, streak: int = 0) -> list:
    last_date  = data[user_id].get("last_daily_date", "")
    already    = last_date == today_utc()
    cur_streak = data[user_id].get("daily_streak", 0)
    nxt_ts     = next_midnight_ts()
    if claimed:
        icon = "◈ " if reward_type == "money" else "💎"
        body = (
            f"### 📅 Daily Claimed!\n"
            f"You received **{icon}{reward_amt:,}**!\n"
            f"-# 🔥 Streak: **{streak}** days · +{streak}% bonus\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    elif already:
        body = (
            f"### 📅 Daily\nAlready claimed today!\n"
            f"-# 🔥 Streak: **{cur_streak}** days\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    else:
        tier = get_daily_tier(data[user_id]["level"])
        body = (
            f"### 📅 Daily Reward\nClaim your daily reward!\n"
            f"-# 🔥 Streak: **{cur_streak}** days · +{cur_streak}% bonus\n"
            f"-# 💰 Possible: ◈ {tier['money_min']:,}–{tier['money_max']:,} "
            f"or 💎{tier['gems_min']}–{tier['gems_max']}\n"
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
        f"### ⭐ Prestige {next_p}\n"
        f"Current: **Prestige {current}** (+{current * 20}% all boosts)\n\n"
        f"**Requirements:**\n"
        f"-# {'✅' if lvl_ok else '❌'} Level **{PRESTIGE_MIN_LEVEL:,}** (you: {level:,})\n"
        f"-# {'✅' if money_ok else '❌'} **◈ {PRESTIGE_MIN_MONEY:,}** (you: ◈ {money:,})\n\n"
        f"**Reward:** +**{boost}%** permanent Luck, Sell & XP\n"
        f"-# Resets: Level, Money, Inventory, Biome, Record\n"
        f"-# Kept: Gems, Tools, Tribe, Log, Ammo"
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
            f"### ⭐ Prestige {new_prestige}!\n"
            f"All progress reset. Welcome back, hunter.\n"
            f"-# Permanent bonus: +**{new_prestige * 20}%** to all boosts"
        )},
        {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Menu", "custom_id": f"nav:menu:{user_id}"}
        ]},
    ]}]

def build_lottery_components(user_id: str) -> list:
    ld         = lottery_data
    pool       = ld.get("pool", 0)
    tickets    = ld.get("tickets", {})
    total_t    = sum(tickets.values())
    my_tickets = tickets.get(user_id, 0)
    my_chance  = (my_tickets / total_t * 100) if total_t > 0 else 0.0
    next_ts    = ld.get("next_ts", 0)
    last_w     = ld.get("last_winner")
    last_line  = (f"Last win: **◈ {last_w['won']:,}** by `{last_w['username']}`"
                  if last_w else "Last win: *None yet*")
    sorted_buyers = sorted(tickets.items(), key=lambda x: x[1], reverse=True)
    medals    = {0: "🥇", 1: "🥈", 2: "🥉"}
    top_lines = []
    for i, (uid, tc) in enumerate(sorted_buyers[:5]):
        chance = (tc / total_t * 100) if total_t > 0 else 0.0
        name   = get_username(uid)
        medal  = medals.get(i, f"**#{i+1}**")
        you    = " ← you" if uid == user_id else ""
        top_lines.append(f"{medal} `{chance:.1f}%`: `{name}`{you}")
    top_block = "\n".join(top_lines) if top_lines else "-# No participants yet."
    content = (
        f"### 🎰 Lottery\n{last_line}\n\n"
        f"**Pool: ◈ {pool:,}** · Tickets: **{total_t:,}**\n"
        f"Your tickets: **{my_tickets}** · Chance: **{my_chance:.2f}%**\n\n"
        f"Tickets cost: **◈ {LOTTERY_TICKET_COST:,}** each\n"
        f"-# More tickets = better chance\n\n"
        f"**Top Spenders:**\n{top_block}\n\n"
        f"-# Next lottery <t:{next_ts}:R>"
    )
    return [{"type": 17, "accent_color": 0xF1C40F, "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": [
            {"type": 2, "style": 3, "label": "🎟️ Buy Tickets",
             "custom_id": f"lottery:buy:{user_id}"},
            {"type": 2, "style": 2, "label": "🔄 Refresh",
             "custom_id": f"lottery:refresh:{user_id}"},
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"nav:menu:{user_id}"},
        ]},
    ]}]

# ─────────────────────────────────────────────
# GAMBLE PANELS
# ─────────────────────────────────────────────

SLOT_SYMBOLS = (
    [animal_emoji(a) for a in list(ANIMAL_DATA.keys())[:8]]
    if ANIMAL_DATA else list(BIOME_EMOJIS.values())[:8]
)
_seen_syms = []
for _s in SLOT_SYMBOLS:
    if _s not in _seen_syms:
        _seen_syms.append(_s)
SLOT_SYMBOLS = _seen_syms[:6]

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
            {"type": 2, "style": 2, "label": "◀ Back",
             "custom_id": f"nav:menu:{user_id}"},
        ]},
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
        lock_str = " 🔒" if locked else ""
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
    row_colors = {"type": 1, "components": [
        {"type": 2, "style": 4, "label": "🔴 Red (×2)",
         "custom_id": f"gamble:rl:red:{user_id}",   "disabled": no_bet},
        {"type": 2, "style": 2, "label": "⚫ Black (×2)",
         "custom_id": f"gamble:rl:black:{user_id}", "disabled": no_bet},
        {"type": 2, "style": 3, "label": "🟢 Green (×5)",
         "custom_id": f"gamble:rl:green:{user_id}", "disabled": no_bet},
    ]}
    row_util = {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "Change Bet", "custom_id": f"gamble:rl:setbet:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Back",     "custom_id": f"gamble:back:{user_id}"},
    ]}
    if state == "bet":
        content = (
            f"### 🔴 Roulette\n{last_line}\n{bet_line}\n\n"
            f"Each color has equal **1/3 chance**!\n"
            f"-# 🔴 Red · ⚫ Black → ×2  ·  🟢 Green → ×5"
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
             "custom_id": f"gamble:game_select:{user_id}"},
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
    lines = "\n".join(
        f"</{c.name}:{COMMAND_ID.get(c.name,'0')}> — {c.description or 'No description'}"
        for c in cmds
    )
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
            unread_tag = "" if d.get("tribe_inv_read", False) else " 🔴"
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
            unread_dot = "" if read else " 🔴"
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
        unread_tag  = "" if is_read else " 🔴"
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
    amt_str = f"◈ {parsed:,}" if format == "money" else f"💎 {parsed:,}"
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
            f"💎 Your Gems: **{data[user_id]['gems']}**\n\n"
            f"{TRIBE_EMOJIS['luck_boost']} Luck Boost: **{td['luck_boost']}%** — 50 💎\n"
            f"{TRIBE_EMOJIS['sell_boost']} Sell Boost: **{td['sell_price_boost']}%** — 50 💎\n"
            f"{TRIBE_EMOJIS['xp_boost']} XP Boost: **{td['xp_boost']}%** — 50 💎\n"
            f"{TRIBE_EMOJIS['members']} +1 Slot: **{td['max_members']}** — 100 💎"
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
        action_opts = [{"label": "Leave Tribe", "value": "leave",
                        "description": "Leave your current tribe."}]
        if is_leader or is_officer:
            action_opts += [
                {"label": "Invite Player",   "value": "invite",   "description": "Send a tribe invite."},
                {"label": "Kick Member",     "value": "kick",     "description": "Remove a member."},
                {"label": "Ban List",        "value": "banlist",  "description": "View and manage bans."},
                {"label": "Set Description", "value": "set_desc", "description": "Set tribe description."},
            ]
        if is_leader:
            action_opts += [
                {"label": "Promote Member",      "value": "promote",  "description": "Promote to officer."},
                {"label": "Demote Officer",      "value": "demote",   "description": "Demote to member."},
                {"label": "Transfer Leadership", "value": "transfer", "description": "Transfer leader role."},
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

def get_server_user_ids(guild) -> list:
    if guild is None:
        return list(data.keys())
    member_ids = {str(m.id) for m in guild.members}
    return [uid for uid in data if uid in member_ids]

def build_leaderboard_v2_components(user_id: str, guild, mode: str = "hunter",
                                     scope: str = "global", stat: str = "Level",
                                     page: int = 0) -> list:
    PS     = 10
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    if mode == "hunter":
        fn     = HUNTER_LB_STATS.get(stat, HUNTER_LB_STATS["Level"])
        cands  = get_server_user_ids(guild) if scope == "server" else list(data.keys())
        ranked = sorted(cands, key=lambda u: fn(u), reverse=True)
        total  = len(ranked)
        items  = ranked[page * PS:(page + 1) * PS]
        lines  = []
        for i, uid in enumerate(items):
            pos     = page * PS + i
            val     = fn(uid)
            val_str = f"◈ {val:,}" if stat == "Money" else f"**{val:,}**"
            you     = " ← you" if uid == user_id else ""
            lines.append(f"{medals.get(pos, f'**#{pos+1}**')} `{get_username(uid)}` — {val_str}{you}")
        vpos   = next((i for i, u in enumerate(ranked) if u == user_id), None)
        footer = f"-# Your rank: **#{vpos+1}**" if vpos is not None else "-# Not ranked."
        scope_label = f"{guild.name} Server" if scope == "server" and guild else "Global"
        content = (
            f"### 🏆 {scope_label} Leaderboard — {stat}\n\n"
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
            f"### 🏆 {scope_label} Tribe Leaderboard\n\n"
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
            f"🔒 **Locked**\n-# Unlocks at Level **{biome_req}**."
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
            f"🔒 **Locked**"
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

def build_log_v2_components(user_id: str, page: int = 0) -> list:
    log   = data[user_id].get("log", [])
    total = len(log)
    if not log or page >= total:
        content = "### 📋 Hunt Log\nNo hunts recorded yet."
        btn_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Back to Profile",
             "custom_id": f"profile:main:{user_id}"}
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
        f"### 📋 Hunt Log — Entry {page+1}/{total}\n"
        f"-# <t:{ts}:F> · {TOOLS.get(tool,{}).get('emoji','🔧')} **{tool}**{ammo_line} · "
        f"{BIOME_NAMES.get(biome, biome)}\n\n"
        + "\n\n".join(catch_lines) + footer
    )
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Newer",
         "custom_id": f"log:prev:{user_id}", "disabled": (page == 0)},
        {"type": 2, "style": 1, "label": "Older ▶",
         "custom_id": f"log:next:{user_id}", "disabled": (page >= total - 1)},
        {"type": 2, "style": 2, "label": "◀ Back to Profile",
         "custom_id": f"profile:main:{user_id}"},
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
            {"type": 10, "content": "### 📋 Hunt Log\nNo hunts recorded yet."},
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
        f"### 📋 Hunt Log — Entry {page+1}/{total}\n"
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

def build_personal_leaderboard_components(user_id: str) -> list:
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
    content = (
        f"### 🏆 Your Rankings\n\n"
        f"### 🌍 Global\n"
        f"💰 **Balance:** #{money_rank:,}/{total_players:,}\n"
        f"{USER_EMOJIS['levels']} **Level:** #{level_rank:,}/{total_players:,}\n"
        f"🎯 **Animals:** #{caught_rank:,}/{total_players:,}"
        f"{tribe_section}\n\n"
        f"-# ◈ {d['money']:,} · Lv. {d['level']} · {d.get('total_caught', 0):,} caught"
    )
    row_1 = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "Main Profile",  "custom_id": f"profile:main:{user_id}"},
        {"type": 2, "style": 1, "label": "Inventory",     "custom_id": f"profile:inventory:{user_id}"},
        {"type": 2, "style": 1, "label": "Statistics",    "custom_id": f"profile:statistics:{user_id}"},
    ]}
    row_2 = {"type": 1, "components": [
        {"type": 2, "style": 3, "label": "Rankings",      "custom_id": f"profile:leaderboard:{user_id}"},
        {"type": 2, "style": 1, "label": "Hunting Log",   "custom_id": f"profile:log:{user_id}"},
        {"type": 2, "style": 2, "label": "◀ Menu",        "custom_id": f"nav:menu:{user_id}"},
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        row_1, row_2,
    ]}]

# ─────────────────────────────────────────────
# ACHIEVEMENT + BADGE CHECKER
# ─────────────────────────────────────────────

async def check_achievements_and_badges(interaction: discord.Interaction, user_id: str):
    init_user(user_id)
    d      = data[user_id]
    notifs = []

    all_tools_owned = all(t in d.get("owned_tools", []) for t in TOOLS)
    all_tools_used  = all(t in d.get("stats", {}).get("tools_used", []) for t in TOOLS)

    ACH_SOURCES = {
        "daily_streak":    d.get("daily_streak", 0),
        "animals_caught":  d.get("total_caught", 0),
        "ammo_used":       d.get("stats", {}).get("ammo_used", 0),
        "tools_bought_all":1 if all_tools_owned else 0,
        "tools_used_all":  1 if all_tools_used  else 0,
    }

    for ach_key, tiers in ACHIEVEMENTS.items():
        if not tiers:
            continue
        current_val = ACH_SOURCES.get(ach_key, 0)
        ach_data    = d["achievements"].setdefault(ach_key, {"claimed_up_to": -1})
        claimed_idx = ach_data.get("claimed_up_to", -1)

        for i, tier_entry in enumerate(tiers):
            if i <= claimed_idx:
                continue

            # Support both formats:
            # New: (threshold, [(rtype, amount), ...])
            # Old: (threshold, rtype, amount)
            if len(tier_entry) == 2:
                threshold, rewards = tier_entry
                if not isinstance(rewards, (list, tuple)) or (
                    len(rewards) == 2 and isinstance(rewards[0], str)
                ):
                    # It's actually (threshold, (rtype, amount)) or flat — normalize
                    rewards = [rewards]
            elif len(tier_entry) == 3:
                threshold, rtype, amount = tier_entry
                rewards = [(rtype, amount)]
            else:
                continue

            if current_val < threshold:
                break

            reward_strs = []
            for rtype, amount in rewards:
                d[rtype] = d.get(rtype, 0) + amount
                if rtype == "money":
                    d["total_money_earned"] = d.get("total_money_earned", 0) + amount
                icon = "◈" if rtype == "money" else "💎"
                reward_strs.append(f"{icon} {amount:,}")

            d["achievements"][ach_key]["claimed_up_to"] = i
            reward_text = " + ".join(reward_strs)
            label = ACH_LABELS.get(ach_key, ach_key.replace("_", " ").title())
            notifs.append((
                "🏅 Achievement Unlocked!",
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
        for k in ACHIEVEMENTS if ACHIEVEMENTS.get(k)
    )

    for badge_key, bdef in BADGES.items():
        stat    = bdef["stat"]
        gold_t  = bdef["gold"]
        plat_t  = bdef["plat"]
        abbr    = bdef["abbr"]
        label   = bdef["label"]
        cur     = 1 if (stat == "game_master" and all_ach_done) else get_badge_stat(user_id, stat)
        bstate  = d["badges"].setdefault(badge_key, {"tier": 0, "notified_gold": False, "notified_plat": False})
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
            gm["tier"] = 2; gm["notified_plat"] = True
            notifs.append(("🏆 Platinum Badge Earned!",
                "**Game Master** `[GM🏆]`\nYou've completed everything. Legendary.", 0xE8E8E8))

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
        await smart_update_v2(interaction, build_idle_components(user_id))
    elif panel == "daily":
        await smart_update_v2(interaction, build_daily_components(user_id))
    elif panel == "prestige":
        await smart_update_v2(interaction, build_prestige_components(user_id))
    elif panel == "mail":
        await smart_update_v2(interaction, build_mail_components(user_id, "tribe"))
    elif panel == "help":
        await smart_update_v2(interaction, build_help_components(user_id))
    elif panel == "update":
        await smart_update_v2(interaction, build_update_components(user_id))
    elif panel == "lottery":
        await smart_update_v2(interaction, build_lottery_components(user_id))
    elif panel == "gamble":
        await smart_update_v2(interaction, build_gamble_menu(user_id))
    elif panel == "leaderboard":
        _lb_state[user_id] = {"mode": "hunter", "scope": "global", "stat": "Level",
                               "page": 0, "guild": interaction.guild}
        await smart_update_v2(interaction, build_leaderboard_v2_components(
            user_id, interaction.guild, "hunter", "global", "Level", 0))
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
    else:
        await smart_update_v2(interaction, build_menu_components(user_id, dn))

# ─────────────────────────────────────────────
# COMMON INIT
# ─────────────────────────────────────────────

async def _common_init(interaction: discord.Interaction) -> str | None:
    global maintenance_mode, maintenance_warning, maintenance_message, _maintenance_warned

    user_id = str(interaction.user.id)

    # Admin bypass — defer immediately
    if user_id in BOT_ADMIN_ID:
        init_user(user_id)
        await update_user_servers(user_id, interaction.guild)
        await interaction.response.defer()
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
    init_ban_record(user_id)
    await update_user_servers(user_id, interaction.guild)

    # Ban — type 4 immediate
    if is_banned(user_id):
        await _raw(interaction, {"type": 4, "data": {
            "flags": V2_FLAGS | 64,
            "components": build_ban_components(user_id),
            "allowed_mentions": {"parse": []},
        }})
        return None

    # Defer immediately — all subsequent sends use followup route
    await interaction.response.defer()

    tick_verify(user_id)
    if data[user_id]["verify"]["needed"]:
        await send_v2_followup(interaction, verify_needed_components(user_id))
        return None

    if maintenance_warning and user_id not in _maintenance_warned:
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

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    raw    = getattr(interaction, "data", {}) or {}
    cid    = raw.get("custom_id", "")
    values = raw.get("values", [])
    parts  = cid.split(":")

    # ── TUTORIAL ──────────────────────────────
    if parts[0] == "tutorial":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        init_tutorial(owner_id)

        if parts[1] == "optin":
            await interaction.response.defer()
            choice = parts[2]
            data[owner_id]["tutorial"]["enabled"] = (choice == "yes")
            save_data_users()
            if choice == "yes":
                await smart_update_v2(interaction, [{"type": 17, "accent_color": _accent(owner_id),
                    "spoiler": False, "components": [{"type": 10, "content":
                        "### ✅ Tutorial tips on!\n"
                        "I'll send you a short tip each time you try something new.\n"
                        "-# Use `/tutorial off` any time to stop."
                    }]}])
            else:
                await smart_update_v2(interaction, [{"type": 17, "accent_color": _accent(owner_id),
                    "spoiler": False, "components": [{"type": 10, "content":
                        "### 👍 No problem!\n"
                        "-# If you change your mind, use `/tutorial on`."
                    }]}])
            return

        if parts[1] == "dismiss":
            await interaction.response.defer()
            return

        if parts[1] == "stop":
            await interaction.response.defer()
            data[owner_id]["tutorial"]["enabled"] = False
            save_data_users()
            await smart_update_v2(interaction, [{"type": 17, "accent_color": _accent(owner_id),
                "spoiler": False, "components": [{"type": 10, "content":
                    "### 🔕 Tips turned off.\n"
                    f"-# Use </tutorial:{COMMAND_ID.get('tutorial','0')}> to turn them back on any time."
                }]}])
            return

    # ── HUNT ──────────────────────────────────
    if parts[0] == "hunt":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "again":
            await interaction.response.defer()
            init_user(owner_id)
            async with get_user_lock(owner_id):
                result = run_hunt(owner_id)
            if result.get("verify"):
                await send_ephemeral_v2(interaction,
                    f"🔒 **Verification Required**\nUse </verify:{COMMAND_ID.get('verify','0')}> with code `{data[owner_id]['verify']['code']}`",
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
                    f"⏳ Hunt again <t:{result.get('cooldown_ts', int(time.time()+3))}:R>.",
                    0xE67E22)
                return
            data[owner_id]["_display_name"] = interaction.user.display_name
            await smart_update_v2(interaction, build_hunt_components(owner_id, result))
            return

        if parts[1] == "sell_all":
            await interaction.response.defer()
            init_user(owner_id)
            async with user_transaction(owner_id):
                sold = sell_all_inv(owner_id)
            await maybe_tutorial_tip(interaction, owner_id, "biome")
            await smart_update_v2(interaction, build_hunt_sold_components(owner_id, sold))
            return

        if parts[1] == "back":
            await interaction.response.defer()
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
            return

    # ── MENU NAV ──────────────────────────────
    if parts[0] == "menu":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        if parts[1] == "nav":
            await interaction.response.defer()
            panel = values[0] if values else "menu"
            if panel == "hunt":
                init_user(owner_id)
                async with user_transaction(owner_id):
                    result = run_hunt(owner_id)
                if result.get("verify"):
                    await send_ephemeral_v2(interaction,
                        f"🔒 **Verification Required**\nUse </verify:{COMMAND_ID.get('verify','0')}> with code `{data[owner_id]['verify']['code']}`",
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
                        f"⏳ Hunt again <t:{result.get('cooldown_ts', int(time.time()+3))}:R>.",
                        0xE67E22)
                    return
                save_data_users()
                data[owner_id]["_display_name"] = interaction.user.display_name
                await smart_update_v2(interaction, build_hunt_components(owner_id, result))
                return
            else:
                await _navigate(interaction, owner_id, panel, interaction.user.display_name)
                return

        if parts[1] == "help":
            await interaction.response.defer()
            await smart_update_v2(interaction, build_help_components(owner_id))
            return
        return

    # ── GENERIC NAV ───────────────────────────
    if parts[0] == "nav":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()
        action = parts[1]
        if action in ("back", "menu"):
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
        return

    # ── COLOR ─────────────────────────────────
    if parts[0] == "hunter_color_select":
        owner_id = parts[1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()
        color_key = values[0] if values else None
        if not color_key or color_key not in COLORS:
            await send_ephemeral_v2(interaction, "Invalid color.", 0xE74C3C)
            return
        data[owner_id]["color"] = color_key
        save_data_users()
        await smart_update_v2(interaction, build_color_panel_components(owner_id))
        return

    if parts[0] == "hunter_color_hex":
        owner_id = parts[1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        if data[owner_id]["level"] < 1200:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, "Unlocks at Level 1200.", 0xE74C3C)
            return
        await interaction.response.send_modal(CustomColorModal(owner_id))
        return

    # ── BIOME ─────────────────────────────────
    if parts[0] == "biome" and parts[1] == "select":
        owner_id  = parts[2]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()
        biome_key = values[0] if values else None
        if not biome_key:
            return
        lvl_req = next((lvl for k, lvl in BIOME_LEVELS if k == biome_key), 1)
        if data[owner_id]["level"] < lvl_req:
            await send_ephemeral_v2(interaction,
                f"❌ {BIOME_NAMES[biome_key]} unlocks at Level {lvl_req}.", 0xE74C3C)
            return
        data[owner_id]["biome"] = biome_key
        save_data_users()
        await smart_update_v2(interaction, build_biome_panel_components(owner_id))
        return

    # ── TOOLS ─────────────────────────────────
    if parts[0] == "tools":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

        if parts[1] == "equip":
            tool_name = values[0] if values else None
            if tool_name and tool_name in data[owner_id].get("owned_tools", []):
                old_tool = data[owner_id].get("tool", "Bare Hands")
                data[owner_id]["tool"] = tool_name
                if get_tool_ammo_type(tool_name) != get_tool_ammo_type(old_tool):
                    data[owner_id]["equipped_ammo"] = None
                save_data_users()
            await smart_update_v2(interaction, build_equip_components(owner_id))
            return

        if parts[1] == "ammo_equip":
            ammo_name = values[0] if values else None
            tool_name = data[owner_id].get("tool", "Bare Hands")
            if ammo_name and ammo_name in AMMO and ammo_compatible_with_tool(ammo_name, tool_name):
                if get_ammo_count(owner_id, ammo_name) > 0:
                    data[owner_id]["equipped_ammo"] = ammo_name
                    save_data_users()
                else:
                    await send_ephemeral_v2(interaction, "❌ You don't own that ammo.", 0xE74C3C)
                    return
            await smart_update_v2(interaction, build_equip_components(owner_id))
            return

        if parts[1] == "vehicle_equip":
            vehicle_name = values[0] if values else None
            if vehicle_name and vehicle_name in data[owner_id].get("owned_vehicles", []):
                data[owner_id]["vehicle"] = vehicle_name
                save_data_users()
            await smart_update_v2(interaction, build_equip_components(owner_id))
            return

    # ── SHOP ──────────────────────────────────
    if parts[0] == "shop":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        # Modals must be the initial response — handle before defer
        if parts[1] == "ammo_buy_acc":
            ammo_name = parts[2]
            if ammo_name not in AMMO:
                await interaction.response.defer()
                await send_ephemeral_v2(interaction, "Unknown ammo.", 0xE74C3C)
                return
            await interaction.response.send_modal(AmmoBuyModal(owner_id, ammo_name))
            return

        if parts[1] == "ammo_buy":
            ammo_name = values[0] if values else None
            if not ammo_name or ammo_name not in AMMO:
                await interaction.response.defer()
                await send_ephemeral_v2(interaction, "Unknown ammo.", 0xE74C3C)
                return
            await interaction.response.send_modal(AmmoBuyModal(owner_id, ammo_name))
            return

        await interaction.response.defer()

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
            if item["currency"] == "gems":
                if not spend_gems(owner_id, item["price"], "shop boost"):
                    await send_ephemeral_v2(interaction, f"Need 💎{item['price']}.", 0xE74C3C)
                    return
            else:
                if not spend_money(owner_id, item["price"], "shop boost"):
                    await send_ephemeral_v2(interaction, f"Need ◈ {item['price']:,}.", 0xE74C3C)
                    return
            if boost_key:
                data[owner_id]["boosts"][boost_key] = current + boost_amt
            save_data_users()
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
            # Pre-check
            if t["currency"] == "gems" and data[owner_id]["gems"] < t["price"]:
                await send_ephemeral_v2(interaction, f"Need 💎{t['price']}.", 0xE74C3C)
                return
            if t["currency"] == "money" and data[owner_id]["money"] < t["price"]:
                await send_ephemeral_v2(interaction, f"Need ◈ {t['price']:,}.", 0xE74C3C)
                return
 
            async with user_transaction(owner_id):
                if t["currency"] == "gems":
                    spend_gems(owner_id, t["price"], "shop tool")
                else:
                    spend_money(owner_id, t["price"], "shop tool")
                data[owner_id]["owned_tools"].append(tool_name)
                data[owner_id]["tool"] = tool_name
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
            if t["currency"] == "gems":
                if data[owner_id]["gems"] < t["price"]:
                    await send_ephemeral_v2(interaction, f"Need 💎{t['price']}.", 0xE74C3C)
                    return
                spend_money(owner_id, t["price"], "tool shop")
            else:
                if data[owner_id]["money"] < t["price"]:
                    await send_ephemeral_v2(interaction, f"Need ◈ {t['price']:,}.", 0xE74C3C)
                    return
                spend_money(owner_id, t["price"], "tool shop")
            data[owner_id]["owned_tools"].append(tool_name)
            data[owner_id]["tool"] = tool_name
            save_data_users()
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
            if v["currency"] == "gems":
                if data[owner_id]["gems"] < v["price"]:
                    await send_ephemeral_v2(interaction, f"Need 💎{v['price']}.", 0xE74C3C)
                    return
                spend_money(owner_id, v["price"], "vehicle shop")
            else:
                if data[owner_id]["money"] < v["price"]:
                    await send_ephemeral_v2(interaction, f"Need ◈ {v['price']:,}.", 0xE74C3C)
                    return
                spend_money(owner_id, v["price"], "vehicle shop")
            data[owner_id].setdefault("owned_vehicles", []).append(vehicle_name)
            data[owner_id]["vehicle"] = vehicle_name
            save_data_users()
            await smart_update_v2(interaction, build_shop_components(owner_id, "vehicles"))
            return

        if parts[1] == "vehicle_equip_acc":
            vehicle_name = parts[2]
            if vehicle_name in data[owner_id].get("owned_vehicles", []):
                data[owner_id]["vehicle"] = vehicle_name
                save_data_users()
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
            if v["currency"] == "gems":
                if data[owner_id]["gems"] < v["price"]:
                    await send_ephemeral_v2(interaction, f"Need 💎{v['price']}.", 0xE74C3C)
                    return
                spend_money(owner_id, v["price"], "vehicle shop")
            else:
                if data[owner_id]["money"] < v["price"]:
                    await send_ephemeral_v2(interaction, f"Need ◈ {v['price']:,}.", 0xE74C3C)
                    return
                spend_money(owner_id, v["price"], "vehicle shop")
            data[owner_id].setdefault("owned_vehicles", []).append(vehicle_name)
            data[owner_id]["vehicle"] = vehicle_name
            save_data_users()
            await smart_update_v2(interaction, build_shop_components(owner_id, "vehicles"))
            return

        if parts[1] == "vehicle_equip":
            vehicle_name = values[0] if values else None
            if vehicle_name and vehicle_name in data[owner_id].get("owned_vehicles", []):
                data[owner_id]["vehicle"] = vehicle_name
                save_data_users()
            await smart_update_v2(interaction, build_equip_components(owner_id))
            return

    # ── IDLE ──────────────────────────────────
    if parts[0] == "idle":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

        if parts[1] == "collect":
            async with user_transaction(owner_id):
                collect_idle(owner_id)
            await smart_update_v2(interaction, build_idle_components(owner_id))
            return

        if parts[1] == "hire":
            idle = data[owner_id]["idle"]
            cost = idle_cost_for_stack(idle["stacks"])
            if data[owner_id]["money"] < cost:
                await send_ephemeral_v2(interaction, f"Need ◈ {cost:,}.", 0xE74C3C)
                return
            async with user_transaction(owner_id):
                collect_idle(owner_id)
                spend_money(owner_id, cost, "idle hiring")
                idle["stacks"]      += 1
                idle["active"]       = True
                idle["started_at"]   = time.time()
            await smart_update_v2(interaction, build_idle_components(owner_id))
            return

    # ── DAILY ─────────────────────────────────
    if parts[0] == "daily" and parts[1] == "claim":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()
 
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
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

        if data[owner_id]["level"] < PRESTIGE_MIN_LEVEL or data[owner_id]["money"] < PRESTIGE_MIN_MONEY:
            await send_ephemeral_v2(interaction, "Requirements not met.", 0xE74C3C)
            return
        new_p = data[owner_id].get("prestige", 0) + 1
        async with user_transaction(owner_id):
            data[owner_id].update({
                "prestige": new_p, "level": 1, "xp": 0, "money": 0,
                "inv": [], "biome": "village", "record": {}, "total_caught": 0,
            })
        await smart_update_v2(interaction, build_prestige_done_components(owner_id, new_p))
        return

    # ── MAIL ──────────────────────────────────
    if parts[0] == "mail":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

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
            sub       = parts[2]
            tribe_inv = data[owner_id].get("tribe_inv")
            if sub == "accept":
                if not tribe_inv or tribe_inv not in tribe_data:
                    await send_ephemeral_v2(interaction, "Tribe no longer exists.", 0xE74C3C)
                    return
                if data[owner_id].get("tribe"):
                    await send_ephemeral_v2(interaction, "Already in a tribe.", 0xE74C3C)
                    return
                async with user_tribe_transaction(owner_id):
                    td_a["roles"]["members"].append(owner_id)
                    if owner_id in td_a.get("invites", []):
                        td_a["invites"].remove(owner_id)
                    data[owner_id]["tribe"]          = tribe_inv
                    data[owner_id]["tribe_inv"]      = None
                    data[owner_id]["tribe_inv_read"] = False
                await smart_update_v2(interaction, build_mail_components(owner_id, "tribe"))
                return
            elif sub == "decline":
                async with user_tribe_transaction(owner_id):
                    if tribe_inv and tribe_inv in tribe_data:
                        if owner_id in tribe_data[tribe_inv].get("invites", []):
                            tribe_data[tribe_inv]["invites"].remove(owner_id)
                    data[owner_id]["tribe_inv"]      = None
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
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, "❌ This gift confirmation expired.", 0xE74C3C)
            return

        owner_id = str(gdata["sender_id"])
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

        if action == "cancel":
            gift_cache.pop(gift_id, None)
            await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
            return

        if action == "confirm":
            recipient_id = str(gdata["recipient_id"])
            fmt          = gdata["format"]
            parsed       = int(gdata["parsed"])
            message      = gdata["message"]
            init_user(recipient_id)
            icon = "◈" if fmt == "money" else "💎"
 
            # Pre-check without locks (fast path for obvious failures)
            if data[owner_id][fmt] < parsed:
                await send_ephemeral_v2(interaction, f"❌ Not enough {icon}!", 0xE74C3C)
                return
 
            # Acquire both user locks in a consistent order (sorted) to
            # prevent deadlock when two gifts cross simultaneously.
            uid_a, uid_b = sorted([owner_id, recipient_id])
            lock_a = get_user_lock(uid_a)
            lock_b = get_user_lock(uid_b)
 
            async with lock_a:
                async with lock_b:
                    # Re-check inside lock — balance may have changed
                    if data[owner_id][fmt] < parsed:
                        await send_ephemeral_v2(interaction, f"❌ Not enough {icon}!", 0xE74C3C)
                        return
 
                    if fmt == "money":
                        spend_money(owner_id, parsed, "gift send")
                        add_money(recipient_id, parsed, "gift receive")
                    else:
                        data[owner_id]["gems"]    -= parsed
                        data[recipient_id]["gems"] += parsed
 
                    amt_str = f"◈ {parsed:,}" if fmt == "money" else f"💎 {parsed:,}"
                    bal_str = (
                        f"◈ {data[owner_id][fmt]:,}"
                        if fmt == "money"
                        else f"💎 {data[owner_id][fmt]:,}"
                    )
 
                    gift_entry = {
                        "sender_id":   owner_id,
                        "sender_name": interaction.user.display_name,
                        "fmt":         fmt,
                        "amt_str":     amt_str,
                        "message":     message,
                        "ts":          int(time.time()),
                        "read":        False,
                    }
                    data[recipient_id].setdefault("gift_mails", []).insert(0, gift_entry)
                    data[recipient_id]["gift_mails"] = data[recipient_id]["gift_mails"][:20]
 
                    _flush_users()  # single flush covers both users
 
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
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        tribe_nm = data[owner_id].get("tribe")
        if not tribe_nm or tribe_nm not in tribe_data:
            await interaction.response.defer()
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

        await interaction.response.defer()

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
                await send_ephemeral_v2(interaction, f"Need 💎{cost}.", 0xE74C3C)
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
            val = values[0] if values else "none"
            if val != "none":
                a, target = val.split(":", 1)
                if a == "ban":
                    td_r = tribe_data[tribe_nm]
                    for role in ("officer", "members"):
                        if target in td_r["roles"][role]:
                            td_r["roles"][role].remove(target)
                    if target in data:
                        data[target]["tribe"] = None
                    blist = td_r.setdefault("banned", [])
                    if target not in blist:
                        blist.append(target)
                    save_data_tribe()
                    save_data_users()
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort))
            return

        if action == "unban_action":
            val = values[0] if values else "none"
            if val != "none":
                a, target = val.split(":", 1)
                if a == "unban":
                    blist = tribe_data[tribe_nm].get("banned", [])
                    if target in blist:
                        blist.remove(target)
                    save_data_tribe()
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
                if is_ldr and total_m == 1:
                    del tribe_data[tribe_nm]
                    data[owner_id]["tribe"] = None
                    save_data_users()
                    save_data_tribe()
                    await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
                    return
                for role in ("officer", "members"):
                    if owner_id in td_l["roles"][role]:
                        td_l["roles"][role].remove(owner_id)
                data[owner_id]["tribe"] = None
                save_data_users()
                save_data_tribe()
                await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
                return

            return

        if action == "kick_confirm":
            target = values[0] if values else None
            if target:
                td_r = tribe_data[tribe_nm]
                for role in ("officer", "members"):
                    if target in td_r["roles"][role]:
                        td_r["roles"][role].remove(target)
                if target in data:
                    data[target]["tribe"]     = None
                    data[target]["tribe_inv"] = None
                save_data_users()
                save_data_tribe()
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort))
            return

        if action == "promote_confirm":
            target = values[0] if values else None
            if target:
                td_r = tribe_data[tribe_nm]
                if target in td_r["roles"]["members"]:
                    td_r["roles"]["members"].remove(target)
                    td_r["roles"]["officer"].append(target)
                save_data_tribe()
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort))
            return

        if action == "demote_confirm":
            target = values[0] if values else None
            if target:
                td_r = tribe_data[tribe_nm]
                if target in td_r["roles"]["officer"]:
                    td_r["roles"]["officer"].remove(target)
                    td_r["roles"]["members"].append(target)
                save_data_tribe()
            await smart_update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort))
            return

        if action == "transfer_confirm":
            target = values[0] if values else None
            if target:
                td_r = tribe_data[tribe_nm]
                if target in td_r["roles"]["officer"]:
                    td_r["roles"]["officer"].remove(target)
                td_r["roles"]["leader"] = target
                if owner_id not in td_r["roles"]["officer"]:
                    td_r["roles"]["officer"].append(owner_id)
                save_data_tribe()
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
                if is_ldr and total_m == 1:
                    del tribe_data[tribe_nm]
                    data[owner_id]["tribe"] = None
                    save_data_users()
                    save_data_tribe()
                    await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
                    return
                for role in ("officer", "members"):
                    if owner_id in td_l["roles"][role]:
                        td_l["roles"][role].remove(owner_id)
                data[owner_id]["tribe"] = None
                save_data_users()
                save_data_tribe()
                await smart_update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
                return

    # ── TRIBE INVITE ACCEPT/DECLINE (DM) ──────
    if cid.startswith("tribe_invite_accept:") or cid.startswith("tribe_invite_decline:"):
        await interaction.response.defer()
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
            save_data_users()
            save_data_tribe()
            await send_ephemeral_v2(interaction, f"✅ Joined **{tribe_nm}**!", 0x2ECC71)
        else:
            if tribe_nm in tribe_data and owner_id in tribe_data[tribe_nm].get("invites", []):
                tribe_data[tribe_nm]["invites"].remove(owner_id)
            data[owner_id]["tribe_inv"] = None
            save_data_users()
            await send_ephemeral_v2(interaction, "Invite declined.", 0xE74C3C)
        return

    # ── BAN APPEAL ────────────────────────────
    if parts[0] == "ban" and parts[1] == "appeal":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        b = get_ban(owner_id)
        if b.get("appeals_used", 0) >= b.get("appeals_max", 2):
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, "❌ No appeal chances left.", 0xE74C3C)
            return
        await interaction.response.send_modal(BanAppealModal(owner_id))
        return

    # ── ACHIEVEMENTS / BADGES / TITLES ────────
    if parts[0] == "ach":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

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
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

        if parts[1] == "equip":
            chosen = values[0] if values else None
            if chosen == "__none__":
                data[owner_id]["equipped_title"] = None
            elif chosen and chosen in data[owner_id].get("earned_titles", []):
                data[owner_id]["equipped_title"] = chosen
            save_data_users()
            await smart_update_v2(interaction, build_title_components(owner_id))
            return

    if parts[0] == "badge":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

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
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return

        no_defer_subs = {"bj_deal", "cf_setbet", "slots_setbet", "rl_setbet", "rps_setbet", "bj_deal"}
        sub_key = f"{parts[1]}_{parts[2]}" if len(parts) > 2 else parts[1]

        if sub_key in no_defer_subs or (len(parts) > 2 and parts[2] in ("setbet", "deal")):
            pass  # modal responses handle their own response
        else:
            await interaction.response.defer()

        init_user(owner_id)

        no_cd_subs = {"back", "game_select", "menu"}
        if parts[1] not in no_cd_subs:
            now         = time.time()
            last_gamble = data[owner_id].get("last_gamble", 0)
            if now - last_gamble < GAMBLE_COOLDOWN:
                remaining = GAMBLE_COOLDOWN - (now - last_gamble)
                await send_ephemeral_v2(interaction,
                    f"⏳ Wait **{remaining:.1f}s** before gambling again.", 0xE67E22)
                return

        if parts[1] == "back":
            await smart_update_v2(interaction, build_gamble_menu(owner_id))
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
                    save_data_users()
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
                cfg              = _slots_biome_config(owner_id)
                _, _, chance, mult = cfg
                reels            = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
                won              = random.randint(1, 100) <= chance
                payout           = int(bet * mult) if won else 0
                spend_money(owner_id, bet, "slots bet")
                add_money(owner_id, payout, "slots")
                if won:
                    data[owner_id]["total_money_earned"] = data[owner_id].get("total_money_earned", 0) + (payout - bet)
                    data[owner_id]["stats"]["slots_wins"] = data[owner_id]["stats"].get("slots_wins", 0) + 1
                data[owner_id]["last_gamble"] = time.time()
                save_data_users()
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
            color      = random.choice(ROULETTE_COLORS)
            _, _, mult = ROULETTE_BET_TYPES[sub]
            won        = color == sub
            payout     = bet * mult if won else 0
            data[owner_id]["_roulette_pick"] = sub
            spend_money(owner_id, bet, "roulette")
            if won:
                add_money(owner_id, payout, "roulette win")
                data[owner_id]["total_money_earned"] = data[owner_id].get("total_money_earned", 0) + (payout - bet)
                data[owner_id]["stats"]["rl_wins"] = data[owner_id]["stats"].get("rl_wins", 0) + 1
            data[owner_id]["last_gamble"] = time.time()
            save_data_users()
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
            save_data_users()
            result = {"pick": sub, "bot_pick": bot_pick, "bet": bet, "outcome": outcome}
            await smart_update_v2(interaction, build_rps_panel(owner_id, "result", result))
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
                    save_data_users()
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
            # save_data_users() ← DELETE
            await smart_update_v2(interaction, build_blackjack_panel(owner_id))
            return

    # ── LOTTERY ───────────────────────────────
    if parts[0] == "lottery":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        init_user(owner_id)

        if parts[1] == "buy":
            await interaction.response.send_modal(LotteryBuyModal(owner_id))
            return

        await interaction.response.defer()
        if parts[1] == "refresh":
            await smart_update_v2(interaction, build_lottery_components(owner_id))
            return

    # ── PROFILE ───────────────────────────────
    if parts[0] == "profile":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

        panel = parts[1]
        if panel == "main":
            await smart_update_v2(interaction, build_profile_components(owner_id, interaction.user.display_name, "main"))
            return
        if panel == "inventory":
            await smart_update_v2(interaction, build_inventory_components(owner_id, interaction.user.display_name))
            return
        if panel == "statistics":
            await smart_update_v2(interaction, build_statistics_components(owner_id, interaction.user.display_name))
            return
        if panel == "leaderboard":
            await smart_update_v2(interaction, build_personal_leaderboard_components(owner_id))
            return
        if panel == "log":
            log_page = _profile_log_page.get(owner_id, 0)
            await smart_update_v2(interaction, build_log_v2_components(owner_id, log_page))
            return
        await _navigate(interaction, owner_id, panel, interaction.user.display_name)
        return

    # ── VERIFY REFRESH ────────────────────────────
    if parts[0] == "verify":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()
        if parts[1] == "refresh":
            await smart_update_v2(interaction, build_verify_v2(owner_id))
        return

    # ── LOG PROFILE ───────────────────────────
    if parts[0] == "log":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

        current_page = _profile_log_page.get(owner_id, 0)
        total        = len(data[owner_id].get("log", []))
        if parts[1] == "prev":
            _profile_log_page[owner_id] = max(0, current_page - 1)
        elif parts[1] == "next":
            _profile_log_page[owner_id] = min(total - 1, current_page + 1)
        await smart_update_v2(interaction, build_log_v2_components(owner_id, _profile_log_page[owner_id]))
        return

    # ── RECORD PROFILE ────────────────────────
    if parts[0] == "record":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

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
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

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
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

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
            await interaction.response.defer()
            await send_ephemeral_v2(interaction, show_incorrect_user_message(owner_id), 0xE74C3C)
            return
        await interaction.response.defer()

        state  = _lb_state.get(owner_id, {
            "mode": "hunter", "scope": "global",
            "stat": "Level", "page": 0,
            "guild": interaction.guild,
        })
        action = parts[1]
        if action == "stat":
            state["stat"] = values[0] if values else "Level"
            state["page"] = 0
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
            state["scope"], state["stat"], state["page"]))
        return

# ─────────────────────────────────────────────
# MODALS
# ─────────────────────────────────────────────

class SetBetModal(discord.ui.Modal, title="Set Your Bet"):
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
        await interaction.response.defer()
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
        key_map = {"cf": "_cf_bet", "slots": "_slots_bet", "rl": "_roulette_bet", "rps": "_rps_bet"}
        data[self.user_id][key_map[self.game]] = parsed
        builders = {
            "cf":    lambda: build_coinflip_panel(self.user_id),
            "slots": lambda: build_slots_panel(self.user_id),
            "rl":    lambda: build_roulette_panel(self.user_id),
            "rps":   lambda: build_rps_panel(self.user_id),
        }
        await smart_update_v2(interaction, builders[self.game]())

class LotteryBuyModal(discord.ui.Modal, title="Buy Lottery Tickets"):
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
        await interaction.response.defer()
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
        save_data_users()
        ld = lottery_data
        ld["tickets"][self.user_id] = ld["tickets"].get(self.user_id, 0) + qty
        ld["pool"]                  = ld.get("pool", 0) + total_cost
        save_lottery(ld)
        await smart_update_v2(interaction, build_lottery_components(self.user_id))

class CustomColorModal(discord.ui.Modal, title="Custom Embed Color"):
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
        await interaction.response.defer()
        raw = self.hex_input.value.strip().lstrip("#")
        if len(raw) != 6 or not all(c in string.hexdigits for c in raw):
            await send_ephemeral_v2(interaction, "Invalid hex. Use `#RRGGBB`.", 0xE74C3C)
            return
        data[self.user_id]["color"] = f"#{raw.upper()}"
        save_data_users()
        await smart_update_v2(interaction, build_color_panel_components(self.user_id))

class AmmoBuyModal(discord.ui.Modal, title="Buy Ammo"):
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
        await interaction.response.defer()
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
                    f"❌ Need 💎 {total_cost:,} to buy {qty:,}× {self.ammo_name}.", 0xE74C3C)
                return
        inv = data[self.user_id].setdefault("ammo_inv", {})
        inv[self.ammo_name] = current_owned + qty
        save_data_users()
        await smart_update_v2(interaction, build_shop_components(self.user_id, "ammo"))

class TribeInviteModal(discord.ui.Modal, title="Invite a Player"):
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
        await interaction.response.defer()
        raw = self.uid_input.value.strip()
        if raw.startswith("<@") and raw.endswith(">"):
            raw = raw.replace("<@", "").replace("!", "").replace(">", "").strip()
        if not raw.isdigit():
            await send_ephemeral_v2(interaction, "❌ Invalid user ID.", 0xE74C3C)
            return
        if raw == self.user_id:
            await send_ephemeral_v2(interaction, "❌ Can't invite yourself.", 0xE74C3C)
            return
        init_user(raw)
        if data[raw].get("tribe"):
            await send_ephemeral_v2(interaction, "❌ Already in a tribe.", 0xE74C3C)
            return
        if data[raw].get("tribe_inv"):
            await send_ephemeral_v2(interaction, "❌ Already has a pending invite.", 0xE74C3C)
            return
        td    = tribe_data[self.tribe_name]
        total = 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"])
        if total >= td["max_members"]:
            await send_ephemeral_v2(interaction, "❌ Tribe is full.", 0xE74C3C)
            return
        td.setdefault("invites", []).append(raw)
        async with user_tribe_transaction(self.user_id):
            data[raw]["tribe_inv"]      = self.tribe_name
            data[raw]["tribe_inv_read"] = False
        try:
            target_user = await bot.fetch_user(int(raw))
            route = Route("POST", "/users/@me/channels")
            dm_ch = await bot.http.request(route, json={"recipient_id": raw})
            dm_route = Route("POST", "/channels/{channel_id}/messages",
                             channel_id=dm_ch["id"])
            await bot.http.request(dm_route, json={
                "flags": V2_FLAGS,
                "components": [{"type": 17, "accent_color": _accent(self.user_id),
                    "spoiler": False, "components": [{"type": 10, "content":
                        f"### {TRIBE_EMOJIS['invite']} Tribe Invite\n"
                        f"You've been invited to **{self.tribe_name}** by "
                        f"**{interaction.user.display_name}**!\n\n"
                        f"-# Use </mail:{COMMAND_ID.get('mail','0')}> to accept or decline."
                    }]}],
                "allowed_mentions": {"parse": []},
            })
        except Exception:
            pass
        await send_ephemeral_v2(interaction, f"✅ Invite sent to <@{raw}>.", 0x2ECC71)

class TribeSetDescModal(discord.ui.Modal, title="Set Tribe Description"):
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
        await interaction.response.defer()
        tribe_data[self.tribe_name]["description"] = self.desc_input.value
        save_data_tribe()
        sort = _tribe_sort.get(self.user_id, "rank")
        await smart_update_v2(interaction, build_tribe_components(self.user_id, self.tribe_name, "actions", sort))

class TribeLeaveLeaderModal(discord.ui.Modal, title="Assign New Leader Before Leaving"):
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
        await interaction.response.defer()
        target = self.uid_input.value.strip()
        td     = tribe_data[self.tribe_name]
        all_ids = td["roles"]["officer"] + td["roles"]["members"]
        if target not in all_ids:
            await send_ephemeral_v2(interaction, "❌ That user is not a tribe member.", 0xE74C3C)
            return
        async with user_tribe_transaction(self.user_id):
            for role in ("officer", "members"):
                if target in td["roles"][role]:       td["roles"][role].remove(target)
                if self.user_id in td["roles"][role]: td["roles"][role].remove(self.user_id)
            td["roles"]["leader"]       = target
            data[self.user_id]["tribe"] = None
        await smart_update_v2(interaction, build_menu_components(self.user_id, interaction.user.display_name))

class TribeCreateModal(discord.ui.Modal, title="Create a Tribe"):
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
        await interaction.response.defer()
        name = self.name_input.value.strip()
        if name in tribe_data:
            await send_ephemeral_v2(interaction, "❌ Tribe name taken.", 0xE74C3C)
            return
        init_tribe(name, self.user_id)
        tribe_data[name]["description"] = self.desc_input.value.strip()
        save_data_tribe()
        await smart_update_v2(interaction, build_tribe_components(self.user_id, name, "main"))

class BanAppealModal(discord.ui.Modal, title="Submit a Ban Appeal"):
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
        await interaction.response.defer()
        b       = get_ban(self.user_id)
        used    = b.get("appeals_used", 0)
        max_app = b.get("appeals_max", 2)
        if used >= max_app:
            await send_ephemeral_v2(interaction, "❌ You have no appeal chances left.", 0xE74C3C)
            return
        data[self.user_id]["ban"]["appeals_used"] = used + 1
        save_data_users()
        channel = bot.get_channel(BAN_APPEAL_CHANNEL_ID)
        exp_ts  = b.get("expires_ts", 0)
        exp_str = f"<t:{exp_ts}:R>" if exp_ts != 0 else "Permanent"
        if channel:
            try:
                route = Route("POST", "/channels/{channel_id}/messages",
                              channel_id=BAN_APPEAL_CHANNEL_ID)
                await bot.http.request(route, json={
                    "flags": V2_FLAGS,
                    "components": [{"type": 17, "accent_color": 0x3498DB, "spoiler": False,
                        "components": [{"type": 10, "content":
                            f"### 📋 Ban Appeal\n"
                            f"**User:** <@{self.user_id}> (`{self.user_id}`)\n"
                            f"**Reason for ban:** {b.get('reason', 'N/A')}\n"
                            f"**Ban expires:** {exp_str}\n"
                            f"**Appeals used:** {data[self.user_id]['ban']['appeals_used']}/{max_app}\n\n"
                            f"**Appeal message:**\n{self.reason_input.value}"
                        }]}],
                    "allowed_mentions": {"parse": []},
                })
            except Exception as e:
                print("Appeal channel send error:", e)
        await send_ephemeral_v2(interaction,
            "✅ Your appeal has been submitted. Admins will review it shortly.", 0x2ECC71)

class BlackjackBetModal(discord.ui.Modal, title="Blackjack — Place Your Bet"):
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
        await interaction.response.defer()
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
        
# ─────────────────────────────────────────────
# SLASH COMMANDS
# ─────────────────────────────────────────────

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
    await send_v2_followup(interaction,
        build_profile_components(target_id, target.display_name, viewer_id=viewer_id))
    await check_everything(interaction, viewer_id)

@bot.tree.command(name="hunt", description="Go hunting in your current biome!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def hunt_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    async with user_transaction(user_id):
        result = run_hunt(user_id)
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
        atype   = result.get("ammo_type", "ammo")
        msg     = (f"💥 You ran out of {atype}! Your ammo was unequipped." if ran_out else
                   f"⚠️ **{result['tool_name']}** needs {atype} equipped. "
                   f"Buy some in </shop:{COMMAND_ID.get('shop','0')}> → Ammo!")
        await send_ephemeral_v2(interaction, msg, 0xE67E22)
        return
    if not result["ok"]:
        remaining = result.get("remaining", 3)
        await send_ephemeral_v2(interaction,
            f"⏳ Hunt again <t:{result.get('cooldown_ts', int(time.time()+remaining))}:R>.",
            0xE67E22)
        return
    save_data_users()
    await maybe_tutorial_optin(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "sell")
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
    await maybe_tutorial_tip(interaction, user_id, "shop_ammo")

@bot.tree.command(name="biome", description="Choose your hunting biome")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def biome_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_biome_panel_components(user_id))
    await check_everything(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "shop_tools")

@bot.tree.command(name="color", description="Change your embed color")
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
    await maybe_tutorial_tip(interaction, user_id, "equip")

@bot.tree.command(name="idle", description="Manage idle income stacks")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def idle_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_idle_components(user_id))
    await check_everything(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "idle")

@bot.tree.command(name="daily", description="Claim your daily reward")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def daily_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_daily_components(user_id))
    await check_everything(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "daily")

@bot.tree.command(name="prestige", description="Reset for a permanent boost multiplier")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def prestige_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_prestige_components(user_id))
    await check_everything(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "prestige")

@bot.tree.command(name="mail", description="Check your mailbox")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def mail_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_mail_components(user_id, "tribe"))

@bot.tree.command(name="tribe", description="View your current tribe and options")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def tribe_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    tribe_nm  = data[user_id].get("tribe")
    tribe_inv = data[user_id].get("tribe_inv")
    if not tribe_nm and tribe_inv and tribe_inv in tribe_data:
        await send_ephemeral_v2(interaction,
            f"You have a pending invite! Use </mail:{COMMAND_ID.get('mail','0')}> to accept.",
            0xF1C40F)
        return
    if not tribe_nm or tribe_nm not in tribe_data:
        view = discord.ui.View(timeout=60)
        btn  = discord.ui.Button(label="🏕️ Create Tribe", style=discord.ButtonStyle.primary)
        async def create_cb(i: discord.Interaction):
            if str(i.user.id) != user_id:
                await i.response.defer()
                await send_ephemeral_v2(i, show_incorrect_user_message(user_id), 0xE74C3C)
                return
            await i.response.send_modal(TribeCreateModal(user_id))
        btn.callback = create_cb
        view.add_item(btn)
        route = Route("POST", "/webhooks/{application_id}/{token}",
                      application_id=interaction.application_id,
                      token=interaction.token)
        await bot.http.request(route, json={
            "flags": V2_FLAGS,
            "components": [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
                "components": [{"type": 10, "content":
                    f"### {TRIBE_EMOJIS['tribe']} No Tribe\n"
                    "You are not in a tribe! Create one or wait for an invite."
                }]}],
            "allowed_mentions": {"parse": []},
        })
        return
    await send_v2_followup(interaction, build_tribe_components(user_id, tribe_nm, "main"))
    await maybe_tutorial_tip(interaction, user_id, "tribe")

@bot.tree.command(name="leaderboard", description="View hunter and tribe leaderboards")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def leaderboard_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    _lb_state[user_id] = {
        "mode": "hunter", "scope": "global",
        "stat": "Level", "page": 0,
        "guild": interaction.guild,
    }
    await send_v2_followup(interaction,
        build_leaderboard_v2_components(user_id, interaction.guild, "hunter", "global", "Level", 0))
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
    icon = "◈" if format == "money" else "💎"
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
        "flags": V2_FLAGS | 64,
        "components": [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
            "components": [{"type": 10, "content":
                f"### 🔗 Invite Idle Hunter\n"
                f"[Click here to invite the bot!]({url1})\n"
                f"Join the support server: {url2}"
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

@bot.tree.command(name="update", description="View the latest update from the developers")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def update_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_update_components(user_id))
    await check_everything(interaction, user_id)

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

@bot.tree.command(name="suggest", description="Send a suggestion to the developers")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(suggestion="Your suggestion")
async def suggest_cmd(interaction: discord.Interaction, suggestion: str):
    user_id = str(interaction.user.id)
    init_user(user_id)
    await interaction.response.defer(ephemeral=True)
    if data[user_id]["level"] < 5:
        await send_ephemeral_v2(interaction, "❌ You must be at least **Level 5** to send suggestions.", 0xE74C3C)
        return
    now          = time.time()
    last_suggest = data[user_id].get("last_suggest", 0)
    cooldown     = 3600
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
    async with user_transaction(user_id):
        data[user_id]["last_suggest"] = now
    channel = bot.get_channel(SUGGESTION_CHANNEL_ID)
    if channel:
        try:
            route = Route("POST", "/channels/{channel_id}/messages",
                          channel_id=SUGGESTION_CHANNEL_ID)
            await bot.http.request(route, json={
                "flags": V2_FLAGS,
                "components": [{"type": 17, "accent_color": 0x3498DB, "spoiler": False,
                    "components": [{"type": 10, "content":
                        f"### 💡 New Suggestion\n"
                        f"**From:** {interaction.user.display_name} (`{user_id}`)\n"
                        f"**Level:** {data[user_id]['level']} · "
                        f"**Prestige:** {data[user_id].get('prestige', 0)} · "
                        f"**Caught:** {data[user_id].get('total_caught', 0):,}\n\n"
                        f"{suggestion.strip()}"
                    }]}],
                "allowed_mentions": {"parse": []},
            })
        except Exception:
            pass
    await send_ephemeral_v2(interaction,
        "### 💡 Suggestion Sent!\nYour suggestion has been sent to the developers. Thank you!", 0x2ECC71)

@bot.tree.command(name="report", description="Report a user or a bug")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(
    type="What are you reporting?",
    target_user="User to report (leave empty for bug reports)",
    description="Describe the issue in detail",
)
@app_commands.choices(type=[
    app_commands.Choice(name="User", value="user"),
    app_commands.Choice(name="Bug",  value="bug"),
])
async def report_cmd(interaction: discord.Interaction, type: str,
                     description: str, target_user: discord.User = None):
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
            if type == "user":
                content = (
                    f"### 🚨 User Report\n"
                    f"**Reported by:** {interaction.user.display_name} (`{user_id}`)\n"
                    f"**Reported user:** {target_user.display_name} (`{target_user.id}`)\n\n"
                    f"**Description:**\n{description.strip()}"
                )
                color = 0xE74C3C
            else:
                content = (
                    f"### 🐛 Bug Report\n"
                    f"**Reported by:** {interaction.user.display_name} (`{user_id}`)\n"
                    f"**Level:** {data[user_id]['level']} · "
                    f"**Prestige:** {data[user_id].get('prestige', 0)}\n\n"
                    f"**Description:**\n{description.strip()}"
                )
                color = 0xE67E22
            route = Route("POST", "/channels/{channel_id}/messages",
                          channel_id=REPORTS_CHANNEL_ID)
            await bot.http.request(route, json={
                "flags": V2_FLAGS,
                "components": [{"type": 17, "accent_color": color, "spoiler": False,
                    "components": [{"type": 10, "content": content}]}],
                "allowed_mentions": {"parse": []},
            })
        except Exception as e:
            print("Report channel send error:", e)
    await send_ephemeral_v2(interaction,
        "### ✅ Report Submitted\n"
        "Your report has been sent to the moderation team. Thank you!\n"
        "-# Abuse of this system may result in a ban.", 0x2ECC71)

@bot.tree.command(name="tutorial", description="Turn tutorial tips on or off")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(toggle="on or off")
@app_commands.choices(toggle=[
    app_commands.Choice(name="on",  value="on"),
    app_commands.Choice(name="off", value="off"),
])
async def tutorial_cmd(interaction: discord.Interaction, toggle: str):
    user_id = str(interaction.user.id)
    init_user(user_id)
    init_tutorial(user_id)
    async with user_transaction(user_id):
        data[user_id]["tutorial"]["enabled"]  = (toggle == "on")
        data[user_id]["tutorial"]["prompted"] = True
        if toggle == "on":
            data[user_id]["tutorial"]["seen"] = []
    msg = ("### ✅ Tutorial tips on!\nI'll guide you through each new step as you play."
           if toggle == "on" else
           "### 🔕 Tutorial tips off.\n-# Use /tutorial on to turn them back on.")
    await interaction.response.defer()
    route = Route("POST", "/webhooks/{application_id}/{token}",
                  application_id=interaction.application_id,
                  token=interaction.token)
    await bot.http.request(route, json={
        "flags": V2_FLAGS | 64,
        "components": [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
            "components": [{"type": 10, "content": msg}]}],
        "allowed_mentions": {"parse": []},
    })

# ─────────────────────────────────────────────
# ADMIN COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="change_update", description="Set the latest update message")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(message="The update message to display")
async def change_update_cmd(interaction: discord.Interaction, message: str = ""):
    global UPDATE_MSG
    UPDATE_MSG = message.strip()
    save_config()
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### 📋 Update Set\n{UPDATE_MSG if UPDATE_MSG else 'Update cleared.'}", 0x2ECC71)

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
    init_user(user_id)
    init_ban_record(user_id)
    now    = int(time.time())
    exp_ts = (now + days * 86400) if days > 0 else 0
    async with user_transaction(user_id):
        data[user_id]["ban"] = {
            "active":       True,
            "reason":       reason.strip(),
            "expires_ts":   exp_ts,
            "issued_ts":    now,
            "appeals_used": 0,
            "appeals_max":  2,
        }
    try:
        route    = Route("POST", "/users/@me/channels")
        dm_ch    = await bot.http.request(route, json={"recipient_id": user_id})
        dm_route = Route("POST", "/channels/{channel_id}/messages",
                         channel_id=dm_ch["id"])
        await bot.http.request(dm_route, json={
            "flags": V2_FLAGS,
            "components": build_ban_components(user_id),
            "allowed_mentions": {"parse": []},
        })
    except Exception as e:
        print(f"Ban DM error for {user_id}:", e)
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
    init_user(user_id)
    warn_entry = {"reason": reason.strip(), "ts": int(time.time()), "by": str(interaction.user.id)}
    async with user_transaction(user_id):
        data[user_id].setdefault("warnings", []).append(warn_entry)
    warn_count = len(data[user_id]["warnings"])
    body = (
        f"### ⚠️ You have been warned!\n\n"
        f"Reason: {reason.strip()}\n\n"
        f"-# This is warning **#{warn_count}**. "
        f"Continued violations may result in a ban.\n"
        f"-# Admins will never warn or ban you for no reason."
    )
    try:
        route    = Route("POST", "/users/@me/channels")
        dm_ch    = await bot.http.request(route, json={"recipient_id": user_id})
        dm_route = Route("POST", "/channels/{channel_id}/messages",
                         channel_id=dm_ch["id"])
        await bot.http.request(dm_route, json={
            "flags": V2_FLAGS,
            "components": [{"type": 17, "accent_color": 0xF39C12, "spoiler": False,
                "components": [{"type": 10, "content": body}]}],
            "allowed_mentions": {"parse": []},
        })
    except Exception as e:
        print(f"Warn DM error for {user_id}:", e)
    await interaction.response.defer(ephemeral=True)
    await send_ephemeral_v2(interaction,
        f"### ⚠️ User Warned\n"
        f"<@{user_id}> has been warned.\n"
        f"Reason: {reason}\nTotal warnings: **{warn_count}**", 0xF1C40F)

@bot.tree.command(name="economy", description="Economy diagnostics")
@app_commands.check(is_admin)
async def economy_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    all_balances = [d.get("money", 0) for d in data.values()]
    all_balances.sort()
    n = len(all_balances)
    
    total_money = sum(all_balances)
    median = all_balances[n // 2] if n else 0
    p90 = all_balances[int(n * 0.9)] if n else 0
    p99 = all_balances[int(n * 0.99)] if n else 0
    top_holder = max(data.items(), key=lambda x: x[1].get("money", 0), default=(None, {}))
    
    # Read last 24h from economy log if it exists
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
    except (FileNotFoundError, OSError, KeyError):
        pass

    content = (
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
    await send_ephemeral_v2(interaction, content, 0x3498DB)

# ─────────────────────────────────────────────
# AUTOSAVE & TASKS
# ─────────────────────────────────────────────

@tasks.loop(seconds=5)
async def autosave_users():
    await asyncio.to_thread(save_data_users)

@tasks.loop(seconds=5)
async def autosave_tribes():
    await asyncio.to_thread(save_data_tribe)

@autosave_users.error
async def _aue(e): print("Autosave users error:", e)

@autosave_tribes.error
async def _ate(e): print("Autosave tribes error:", e)

@tasks.loop(seconds=30)
async def lottery_tick():
    global lottery_data
    if time.time() >= lottery_data.get("next_ts", 0):
        await run_lottery_draw()

@lottery_tick.error
async def _lte(error): print("Lottery tick error:", error)

# ─────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print("Sync failed:", e)
    await bot.change_presence(activity=discord.Game(name="/menu | Idle Hunter"))
    if not autosave_users.is_running():  autosave_users.start()
    if not autosave_tribes.is_running(): autosave_tribes.start()
    if not lottery_tick.is_running():    lottery_tick.start()
    print("Autosave started.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

bot.run(BOT_TOKEN)
