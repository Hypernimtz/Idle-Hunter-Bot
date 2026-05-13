import asyncio, discord, random, time, json, string
from discord.http import Route
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from collections import Counter
from game_data import *

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

SUGGESTION_CHANNEL_ID = 1503581602234765322 # replace with your channel ID
BAN_APPEAL_CHANNEL_ID = 0  # replace with your channel ID

# ─────────────────────────────────────────────
# DEV MAIL
# ─────────────────────────────────────────────

DEV_MAIL      = ""

# ─────────────────────────────────────────────
# TIPS
# ─────────────────────────────────────────────

TIP_CHANCE = 10

# ─────────────────────────────────────────────
# COSTS / RATES / GLOBAL VARS
# ─────────────────────────────────────────────

IDLE_COST             = 5_000
IDLE_STACK_MULTIPLIER = 2
HUNT_COOLDOWN         = 3
PRESTIGE_MIN_LEVEL    = 1200
PRESTIGE_MIN_MONEY    = 100_000_000_000
MAX_LOG_ENTRIES       = 50
INV_DISPLAY_MAX       = 10
AMMO_MAX_STACK        = 9_999   # hard cap per ammo type

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
# HELPER — fire a tutorial tip as ephemeral followup
# Call this after save_data_users() in each relevant command.
# ─────────────────────────────────────────────
 
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

    # Check if all steps are now complete
    all_done = all(tutorial_seen(user_id, s) for s in TUTORIAL_STEPS if s != "hunt")
    if all_done:
        data[user_id]["tutorial"]["enabled"] = False

    save_data_users()

    try:
        route = Route(
            "POST", "/webhooks/{application_id}/{token}",
            application_id=interaction.application_id,
            token=interaction.token,
        )
        await interaction.client.http.request(route, json={
            "flags": V2_FLAGS | 64,
            "components": comps,
            "allowed_mentions": {"parse": []},
        })

        # Fire the all-done message on the NEXT command after the last step
        if all_done:
            help_cmd_id = COMMAND_ID.get("help", "")
            done_comps = [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
                "components": [{"type": 10, "content":
                    "### 🎉 You're all set!\n"
                    "You've covered all the basics — happy hunting!\n\n"
                    f"-# Check out all commands in </help:{help_cmd_id}> whenever you'd like."
                }]}]
            await interaction.client.http.request(route, json={
                "flags": V2_FLAGS | 64,
                "components": done_comps,
                "allowed_mentions": {"parse": []},
            })
    except Exception as e:
        print(f"Tutorial tip error ({step}):", e)
 
 
async def maybe_tutorial_optin(interaction: discord.Interaction, user_id: str):
    """
    Fires the opt-in prompt the very first time the user hunts,
    before any step tips are shown.
    """
    init_tutorial(user_id)
    if tutorial_prompted(user_id):
        return
 
    data[user_id]["tutorial"]["prompted"] = True
    save_data_users()
 
    try:
        route = Route(
            "POST", "/webhooks/{application_id}/{token}",
            application_id=interaction.application_id,
            token=interaction.token,
        )
        await interaction.client.http.request(route, json={
            "flags": V2_FLAGS | 64,
            "components": build_tutorial_optin(user_id),
            "allowed_mentions": {"parse": []},
        })
    except Exception as e:
        print("Tutorial opt-in error:", e)

# ─────────────────────────────────────────────
# AMMO HELPERS
# ─────────────────────────────────────────────

def get_equipped_ammo(user_id: str) -> str | None:
    """Returns name of currently equipped ammo, or None."""
    return data[user_id].get("equipped_ammo")

def get_ammo_count(user_id: str, ammo_name: str) -> int:
    return data[user_id].get("ammo_inv", {}).get(ammo_name, 0)

def get_ammo_for_tool(tool_name: str) -> list[str]:
    """Returns list of ammo names compatible with the given tool."""
    atype = get_tool_ammo_type(tool_name)
    if not atype:
        return []
    return [name for name, a in AMMO.items() if a["ammo_type"] == atype]

def ammo_compatible_with_tool(ammo_name: str, tool_name: str) -> bool:
    a_type = AMMO.get(ammo_name, {}).get("ammo_type")
    t_type = TOOLS.get(tool_name, {}).get("ammo_type")
    return a_type is not None and a_type == t_type

def consume_ammo(user_id: str, ammo_name: str, count: int) -> bool:
    """Deducts `count` ammo. Returns False if not enough, True on success."""
    inv = data[user_id].setdefault("ammo_inv", {})
    current = inv.get(ammo_name, 0)
    if current < count:
        return False
    inv[ammo_name] = current - count
    if inv[ammo_name] == 0:
        del inv[ammo_name]
    return True

def get_ammo_boosts(user_id: str) -> dict:
    """Returns the ammo boost dict for equipped ammo, or zeros."""
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
# XP FORMULA
# ─────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    return 1000 + (level - 1) * 10

# ─────────────────────────────────────────────
# SHORTHAND AMOUNT PARSER
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

def save_data_users():
    with open("users_info.json", "w") as f:
        json.dump(data, f, indent=4)

def load_data_users():
    try:
        with open("users_info.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

data = load_data_users()

def save_data_tribe():
    with open("tribe_info.json", "w") as f:
        json.dump(tribe_data, f, indent=4)

def load_data_tribe():
    try:
        with open("tribe_info.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

tribe_data = load_data_tribe()

CONFIG_FILE = "config.json"

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "dev_mail": DEV_MAIL,
            "update": UPDATE_MSG,
            "maintenance": {
                "mode": maintenance_mode,
                "warning": maintenance_warning,
                "message": maintenance_message,
                "channels": list(maintenance_channels),
                "warned": list(_maintenance_warned),
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
                "mode": False,
                "warning": False,
                "message": "",
                "channels": [],
                "warned": [],
            }
        }
    
_cfg                = load_config()
DEV_MAIL            = _cfg["dev_mail"]
UPDATE_MSG          = _cfg["update"]
_m                  = _cfg["maintenance"]
maintenance_mode    = _m["mode"]
maintenance_warning = _m["warning"]
maintenance_message = _m["message"]
maintenance_channels: set[int] = set(_m["channels"])
_maintenance_warned: set[str]  = set(_m["warned"])

# ─────────────────────────────────────────────
# VERIFY HELPERS
# ─────────────────────────────────────────────

def generate_verify_code() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=4))

def init_verify(_: str):
    return {"needed": False, "time": 250, "code": generate_verify_code()}

# ─────────────────────────────────────────────
# USER / TRIBE INIT
# ─────────────────────────────────────────────

def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def init_user(user_id: str):
    user_id = str(user_id)
    today   = today_utc()
    defaults = {
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
        # Ammo system
        "ammo_inv": {},       # {ammo_name: quantity}
        "equipped_ammo": None,
        "vehicle": "None",
        "owned_vehicles": [],
    }
    if user_id not in data:
        data[user_id] = dict(defaults)
    else:
        for k, v in defaults.items():
            if k not in data[user_id]:
                data[user_id][k] = v

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
        t_luck = td.get("luck_boost", 0); t_sell = td.get("sell_price_boost", 0); t_xp = td.get("xp_boost", 0)
    tool_info = TOOLS.get(data[user_id].get("tool", "Bare Hands"), {})
    tool_luck = tool_info.get("boost_luck", 0); tool_xp = tool_info.get("boost_xp", 0)
    ammo_b    = get_ammo_boosts(user_id)
    vehicle_info = VEHICLES.get(data[user_id].get("vehicle"), {})
    vehicle_cd   = vehicle_info.get("boost_cd", 0)
    vehicle_luck = vehicle_info.get("boost_luck", 0)
    return {
        "luck": personal.get("luck", 0) + t_luck + prestige_b + tool_luck + ammo_b["luck"],
        "sell": personal.get("sell", 0) + t_sell + prestige_b + ammo_b["sell"],
        "xp":   personal.get("xp",   0) + t_xp   + prestige_b + tool_xp + ammo_b["xp"],
        "p_luck": personal.get("luck", 0), "p_sell": personal.get("sell", 0), "p_xp": personal.get("xp", 0),
        "t_luck": t_luck, "t_sell": t_sell, "t_xp": t_xp,
        "prestige_b": prestige_b, "tool_luck": tool_luck, "tool_xp": tool_xp,
        "ammo_luck": ammo_b["luck"], "ammo_sell": ammo_b["sell"], "ammo_xp": ammo_b["xp"],
        "luck": personal.get("luck", 0) + t_luck + prestige_b + tool_luck + ammo_b["luck"] + vehicle_luck,
        # add vehicle_cd to return too:
        "cd": vehicle_cd,
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

_lb_state: dict[str, dict] = {}
_log_state: dict[str, int] = {}
_record_state: dict[str, dict] = {}
_profile_log_page: dict[str, int] = {}
_profile_record_page: dict[str, int] = {}
_ammo_shop_page: dict[str, int] = {}
_vehicle_shop_page: dict[str, int] = {}
_tool_shop_page: dict[str, int] = {}

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
    data[user_id]["money"] += earned
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

def get_daily_tier(level: int) -> dict:
    tier = DAILY_TIERS[0]
    for t in DAILY_TIERS:
        if level >= t[0]:
            tier = t
    return {"money_min": tier[1], "money_max": tier[2], "gems_min": tier[3], "gems_max": tier[4]}

def next_midnight_ts() -> int:
    now = datetime.now(timezone.utc)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(nxt.timestamp())

def calc_streak(last_date_str: str, current_streak: int) -> int:
    if not last_date_str:
        return 0
    try:
        last  = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
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
    if (
        DEV_MAIL
        and d.get("mail_dev_content_read", "") != DEV_MAIL
        and d.get("mail_dev_notice_seen", "") != DEV_MAIL
    ):
        return True
    tribe_inv = d.get("tribe_inv")
    if (
        tribe_inv
        and not d.get("tribe_inv_read", False)
        and d.get("tribe_inv_notice_seen", "") != tribe_inv
    ):
        return True
    gifts = d.get("gift_mails", [])
    unread_gifts = [g for g in gifts if not g.get("read", False)]
    if unread_gifts:
        gift_notice_key = str(max(g.get("ts", 0) for g in unread_gifts))
        if d.get("gift_mail_notice_seen", "") != gift_notice_key:
            return True
    return False

def mail_tab_style(user_id: str, tab: str) -> int:
    d = data[user_id]
    has_unread = False
    if tab == "tribe":
        has_unread = bool(d.get("tribe_inv") and not d.get("tribe_inv_read", False))
    elif tab == "gifts":
        gifts = d.get("gift_mails", [])
        has_unread = any(not g.get("read", False) for g in gifts)
    elif tab == "dev":
        has_unread = bool(DEV_MAIL and d.get("mail_dev_content_read", "") != DEV_MAIL)
    return 4 if has_unread else 1

# ─────────────────────────────────────────────
# BAN HELPERS  (add after MAIL HELPERS section)
# ─────────────────────────────────────────────
 
def init_ban_record(user_id: str):
    """Ensure ban sub-dict exists."""
    data[user_id].setdefault("ban", {
        "active":       False,
        "reason":       "",
        "expires_ts":   0,      # 0 = permanent
        "issued_ts":    0,
        "appeals_used": 0,
        "appeals_max":  2,
    })
 
def is_banned(user_id: str) -> bool:
    b = data.get(user_id, {}).get("ban", {})
    if not b.get("active"):
        return False
    exp = b.get("expires_ts", 0)
    if exp != 0 and time.time() > exp:
        # auto-expire
        data[user_id]["ban"]["active"] = False
        save_data_users()
        return False
    return True
 
def get_ban(user_id: str) -> dict:
    return data.get(user_id, {}).get("ban", {})

# Tutorial HELPERS

 
TUTORIAL_STEPS = [
    "hunt",
    "sell",
    "biome",
    "shop_tools",
    "shop_ammo",
    "equip",
    "daily",
    "idle",
    "tribe",
    "prestige",
]
 
def init_tutorial(user_id: str):
    data[user_id].setdefault("tutorial", {
        "prompted": False,
        "enabled":  False,
        "seen":     [],
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
# VERIFY EMBED
# ─────────────────────────────────────────────

def verify_needed_embed(user_id: str) -> discord.Embed:
    code   = data[user_id]["verify"]["code"]
    cmd_id = COMMAND_ID["verify"]
    return discord.Embed(
        title="🔒 Verification Required",
        description=(
            f"Use </verify:{cmd_id}> to continue.\n"
            f"We're preventing autoclickers.\n"
            f"Your code: `{code}`"
        ),
        color=discord.Color.orange(),
    )

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
        remaining = cd - now
        return {"ok": False, "cooldown_ts": int(cd), "remaining": remaining, "verify": False}

    biome     = data[user_id]["biome"]
    tool_name = data[user_id].get("tool", "Bare Hands")

    if not can_hunt_biome(tool_name, biome):
        return {"ok": False, "verify": False, "tool_locked": True,
                "biome_name": BIOME_NAMES[biome],
                "req_tier":   BIOME_TOOL_TIER.get(biome, 1),
                "tool_name":  tool_name}

    # ── Ammo check ───────────────────────────
    needs_ammo  = tool_needs_ammo(tool_name)
    multi       = TOOLS.get(tool_name, {}).get("multi_catch", 1)
    ammo_name   = get_equipped_ammo(user_id)
    ammo_cost   = multi  # consume multi shots per hunt

    if needs_ammo:
        if not ammo_name or not ammo_compatible_with_tool(ammo_name, tool_name):
            return {"ok": False, "verify": False, "no_ammo": True,
                    "ammo_type": AMMO_TYPE_LABELS.get(get_tool_ammo_type(tool_name), "ammo"),
                    "tool_name": tool_name}
        if get_ammo_count(user_id, ammo_name) < ammo_cost:
            # Auto-unequip and block
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
        catches.append({"animal": animal, "sell_value": sell_value, "xp_earned": xp_earned, "is_rare": is_rare})
        total_xp  += xp_earned
        total_val += sell_value
        data[user_id]["inv"].append(animal)
        record_catch(user_id, animal, tool_name, sell_value)

    # Consume ammo after successful hunt
    if needs_ammo and ammo_name:
        consume_ammo(user_id, ammo_name, ammo_cost)
        remaining_ammo = get_ammo_count(user_id, ammo_name)
        if remaining_ammo == 0:
            data[user_id]["equipped_ammo"] = None
            ammo_name = None
    else:
        remaining_ammo = None

    effective_cd = max(1.0, HUNT_COOLDOWN - boosts.get("cd", 0))
    data[user_id]["hunt_cd"]           = now + effective_cd
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
        "tool": tool_name,
        "ammo": ammo_name,
        "remaining_ammo": remaining_ammo,
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
    data[user_id]["inv"]   = []
    data[user_id]["money"] += total
    data[user_id]["total_money_earned"] = data[user_id].get("total_money_earned", 0) + total
    return {"total": total, "count": count}

# ─────────────────────────────────────────────
# RAW PAYLOAD HELPERS
# ─────────────────────────────────────────────

V2_FLAGS = 32768

async def _raw(interaction: discord.Interaction, payload: dict):
    route = Route(
        "POST", "/interactions/{interaction_id}/{interaction_token}/callback",
        interaction_id=interaction.id, interaction_token=interaction.token,
    )
    await interaction.client.http.request(route, json=payload)

async def send_v2(interaction: discord.Interaction, components: list):
    await _raw(interaction, {"type": 4, "data": {"flags": V2_FLAGS, "components": components, "allowed_mentions": {"parse": []}}})

async def update_v2(interaction: discord.Interaction, components: list):
    await _raw(interaction, {"type": 7, "data": {"flags": V2_FLAGS, "components": components, "allowed_mentions": {"parse": []}}})

async def send_ephemeral_embed(interaction, description, color):
    embed = discord.Embed(description=description, color=color)

    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
# MAIL NOTIFICATION HELPER
# ─────────────────────────────────────────────

async def maybe_send_mail_notification(interaction: discord.Interaction, user_id: str):
    init_user(user_id)
    if not has_new_mail_notice(user_id):
        return
    mail_cmd_id = COMMAND_ID["mail"]
    embed = discord.Embed(
        title="📬 You have new mail!",
        description=f"Use </mail:{mail_cmd_id}> to check your mailbox.",
        color=discord.Color.yellow(),
    )
    try:
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print("Mail notification error:", e)
        return
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
# BACK-STACK
# ─────────────────────────────────────────────

_nav_stack: dict[str, list[str]] = {}

def nav_push(user_id: str, panel: str):
    stack = _nav_stack.setdefault(user_id, [])
    if not stack or stack[-1] != panel:
        stack.append(panel)

def nav_pop(user_id: str) -> str:
    stack = _nav_stack.get(user_id, ["menu"])
    if len(stack) > 1:
        stack.pop()
        return stack[-1] if stack else "menu"
    return "menu"

# ─────────────────────────────────────────────
# ── V2 PANEL BUILDERS ──────────────────────
# ─────────────────────────────────────────────

def _back_row(user_id: str) -> dict:
    return {"type": 1, "components": [
        {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"nav:menu:{user_id}", }
    ]}

# ── MENU (dropdown) ───────────────────────────
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

    inv_lines = inv_summary_lines(user_id, INV_DISPLAY_MAX)
    mail_indicator = " 📬" if has_unread_mail(user_id) else ""

    # Ammo line
    ammo_name   = d.get("equipped_ammo")
    ammo_count  = get_ammo_count(user_id, ammo_name) if ammo_name else 0
    a_info      = AMMO.get(ammo_name, {})
    ammo_line   = f"{a_info.get('emoji','🔸')} **{ammo_name}** ×{ammo_count}" if ammo_name else "None"

    vehicle_name = d.get("vehicle", "None")
    v_info       = VEHICLES.get(vehicle_name, {})
    vehicle_line = f"{v_info.get('emoji','🚗')} **{vehicle_name}**" if vehicle_name and vehicle_name != "None" else "None"

    stats = (
        f"### {USER_EMOJIS['profile']} {display_name}'s Menu\n"
        f"{USER_EMOJIS['levels']} Lv.**{d['level']}** ({d['xp']:,}/{xp_for_level(d['level']):,} XP) · "
        f"⭐ Prestige **{prestige}**\n"
        f"**◈ {d['money']:,}** · 💎 **{d['gems']}**\n\n"
        f"{BIOME_EMOJIS[biome]} **{BIOME_NAMES[biome]}** · "
        f"{TOOLS[tool_name]['emoji']} **{tool_name}** (T{get_tool_tier(tool_name)})\n"
        f"🔸 Ammo: {ammo_line}\n"    
        f"🚗 Vehicle: {vehicle_line}\n" 
        f"Tribe: {TRIBE_EMOJIS['tribe']} {tribe_line}\n\n"
        f"💤 Idle stacks: **{stacks}** · Pending: **◈ {pending:,}**\n\n"
        f"🎒 Inventory ({len(inv)} items · ◈ {sell_val:,}):\n"
        f"{inv_lines}"
    )

    dropdown = {"type": 1, "components": [{
        "type": 3,
        "custom_id": f"menu:nav:{user_id}",
        "placeholder": "📋 Navigate...",
        "min_values": 1, "max_values": 1,
        "flows": {},
        "options": [
            {"label": "Hunt",     "emoji": {"name": "🏹"},  "value": "hunt",     "description": "Go hunting in your current biome"},
            {"label": "Shop",     "emoji": {"name": "🏪"},  "value": "shop",     "description": "Buy boosts, tools and ammo"},
            {"label": "Biome",    "emoji": {"name": "🗺️"},  "value": "biome",    "description": "Change your hunting biome"},
            {"label": "Color",    "emoji": {"name": "🎨"},  "value": "color",    "description": "Change your embed color"},
            {"label": "Daily",    "emoji": {"name": "📅"},  "value": "daily",    "description": "Claim your daily reward"},
            {"label": "Prestige", "emoji": {"name": "⭐"},  "value": "prestige", "description": "Prestige for permanent boosts"},
            {"label": "Idle",     "emoji": {"name": "💤"},  "value": "idle",     "description": "Manage your idle income"},
            {"label": "Equip", "emoji": {"name": "🔧"}, "value": "equip", "description": "Equip tools, ammo and vehicles"},
            {"label": f"Mail{mail_indicator}", "emoji": {"name": "📬"}, "value": "mail", "description": "Check your mailbox"},
            {"label": "Tribe", "emoji": {"id": "1500237653591851080", "name": "Bot_Tribe"}, "value": "tribe", "description": "View your tribe"},
            {"label": "Profile",  "emoji": {"id": "1500237646121930863", "name": "User_Profile"}, "value": "profile", "description": "View your profile"},
            {"label": "Update", "emoji": {"name": "📋"}, "value": "update", "description": "View the latest update from the developers"},
        ]
    }]}

    row2 = {"type": 1, "components": [
        {"type": 2, "style": 5, "label": "🔗 Invite Bot",
         "url": f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"},
        {"type": 2, "style": 1, "label": "📖 Help", "custom_id": f"menu:help:{user_id}", },
    ]}

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
             "components": [
                 {"type": 10, "content": stats},
                 {"type": 14, "divider": True, "spacing": 2},
                 dropdown,
                 row2,
             ]}]

# ── PROFILE ───────────────────────────────────
def build_profile_components(user_id: str, display_name: str, active_panel: str = "main", viewer_id: str = None) -> list:
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

    inv_lines   = inv_summary_lines(user_id, INV_DISPLAY_MAX)

    ammo_name   = d.get("equipped_ammo")
    ammo_count  = get_ammo_count(user_id, ammo_name) if ammo_name else 0
    a_info      = AMMO.get(ammo_name, {})
    ammo_line   = f"{a_info.get('emoji','🔸')} **{ammo_name}** ×{ammo_count}" if ammo_name else "None"

    vehicle_name = d.get("vehicle", "None")
    v_info       = VEHICLES.get(vehicle_name, {})
    vehicle_line = f"{v_info.get('emoji','🚗')} **{vehicle_name}**" if vehicle_name and vehicle_name != "None" else "None"
    

    stats = (
        f"### {USER_EMOJIS['profile']} {display_name}'s Profile\n"
        f"{USER_EMOJIS['levels']} Lv.**{d['level']}** ({d['xp']:,}/{xp_for_level(d['level']):,} XP) · "
        f"⭐ Prestige **{prestige}**\n"
        f"**◈ {d['money']:,}** · 💎 **{d['gems']}**\n"
        f"{BIOME_EMOJIS[biome]} **{BIOME_NAMES[biome]}** · "
        f"{TOOLS[tool_name]['emoji']} **{tool_name}** (T{get_tool_tier(tool_name)})\n"
        f"🔸 Ammo: {ammo_line}\n"
        f"🚗 Vehicle: {vehicle_line}\n"
        f"{TRIBE_EMOJIS['tribe']} {tribe_line}\n"
        f"{color_label}\n\n"
        f"{USER_EMOJIS['luck_boost']} Luck **{boosts['luck']}%** · "
        f"{USER_EMOJIS['sell_boost']} Sell **{boosts['sell']}%** · "
        f"{USER_EMOJIS['xp_boost']} XP **{boosts['xp']}%**\n\n"
        f"💤 Idle stacks: **{stacks}** · Pending: **◈ {pending:,}**\n\n"
        f"🎒 Inventory ({len(inv)} items · ◈ {sell_val:,}):\n"
        f"{inv_lines}"
    )

    row_1 = {"type": 1, "components":[
        {"type": 2, "style": 3 if active_panel == "main" else 1, "label": "Main Profile",
         "custom_id": f"profile:main:{user_id}", },
        {"type": 2, "style": 3 if active_panel == "inventory" else 1, "label": "Inventory",
         "custom_id": f"profile:inventory:{user_id}", },
        {"type": 2, "style": 3 if active_panel == "statistics" else 1, "label": "Statistics",
         "custom_id": f"profile:statistics:{user_id}", },
    ]}
    row_2 = {"type": 1, "components":[
        {"type": 2, "style": 3 if active_panel == "leaderboard" else 1, "label": "Rankings",
         "custom_id": f"profile:leaderboard:{user_id}", },
        {"type": 2, "style": 3 if active_panel == "log" else 1, "label": "Hunting Log",
         "custom_id": f"profile:log:{user_id}", },
        {"type": 2, "style": 2, "label": "◀ Menu",
         "custom_id": f"nav:menu:{nav_id}", },
    ]}

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
             "components": [
                 {"type": 10, "content": stats},
                 {"type": 14, "divider": True, "spacing": 1},
                 row_1, row_2
             ]}]

# ── STATISTICS ────────────────────────────────
def build_statistics_components(user_id: str, display_name: str) -> list:
    d = data[user_id]
    joined_str   = d.get("joined_date", today_utc())
    joined_fmt   = format_joined_date(joined_str)
    duration_str = hunting_duration_str(joined_str)
    streak       = d.get("daily_streak", 0)
    best_streak  = d.get("best_daily_streak", 0)
    nw           = net_worth(user_id)
    total_caught = d.get("total_caught", 0)
    total_earned = d.get("total_money_earned", 0)
    record       = d.get("record", {})
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
        f"📦 Total ◈ earned (all time): **◈ {total_earned:,}**\n"
        f"🎯 Total animals caught: **{total_caught:,}**\n\n"
        f"**Animals Caught:**\n{animal_block}"
    )
    row_1 = {"type": 1, "components":[
        {"type": 2, "style": 1, "label": "Main Profile",
         "custom_id": f"profile:main:{user_id}", },
        {"type": 2, "style": 1, "label": "Inventory",
         "custom_id": f"profile:inventory:{user_id}", },
        {"type": 2, "style": 3, "label": "Statistics",
         "custom_id": f"profile:statistics:{user_id}", },
    ]}
    row_2 = {"type": 1, "components":[
        {"type": 2, "style": 1, "label": "Rankings",
         "custom_id": f"profile:leaderboard:{user_id}", },
        {"type": 2, "style": 1, "label": "Hunting Log",
         "custom_id": f"profile:log:{user_id}", },
        {"type": 2, "style": 2, "label": "◀ Menu",
         "custom_id": f"nav:menu:{user_id}", },
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
             "components": [
                 {"type": 10, "content": content},
                 {"type": 14, "divider": True, "spacing": 1},
                 row_1, row_2
             ]}]

# ── INVENTORY ─────────────────────────────────
def build_inventory_components(user_id: str, display_name: str, active_panel: str = "inventory") -> list:
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
    row_1 = {"type": 1, "components":[
        {"type": 2, "style": 1, "label": "Main Profile",
         "custom_id": f"profile:main:{user_id}", },
        {"type": 2, "style": 3, "label": "Inventory",
         "custom_id": f"profile:inventory:{user_id}", },
        {"type": 2, "style": 1, "label": "Statistics",
         "custom_id": f"profile:statistics:{user_id}", },
    ]}
    row_2 = {"type": 1, "components":[
        {"type": 2, "style": 1, "label": "Rankings",
         "custom_id": f"profile:leaderboard:{user_id}", },
        {"type": 2, "style": 1, "label": "Hunting Log",
         "custom_id": f"profile:log:{user_id}", },
        {"type": 2, "style": 2, "label": "◀ Menu",
         "custom_id": f"nav:menu:{user_id}", },
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
             "components": [
                 {"type": 10, "content": content},
                 {"type": 14, "divider": True, "spacing": 1},
                 row_1, row_2
             ]}]

# ── HUNT ──────────────────────────────────────
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

    # Ammo line
    ammo_name = result.get("ammo")
    if ammo_name:
        remaining = result.get("remaining_ammo", 0)
        a_info    = AMMO.get(ammo_name, {})
        ammo_line = f"\n-# 🔸 {a_info.get('emoji','')} **{ammo_name}** — {remaining} left"
    else:
        ammo_line = ""

    title = (
        f"### {result['biome_emoji']} {d.get('_display_name', 'Hunter')}'s Hunting in {result['biome_name']}\n"
    )

    stats_block = (
        f"-# **◈ {result['balance']:,}**\n"
        f"-# {USER_EMOJIS['xp']} **+{result['total_xp']:,} XP**\n"
        f"-# {USER_EMOJIS['levels']} Lv.**{result['level']:,}** "
        f"({result['xp']:,}/{result['xp_needed']:,})\n"
        f"-# {BIOME_EMOJIS[result['biome']]} {result['biome_name']}\n"
        f"-# 🎒 Inventory: **{inv_count}** · Total sell value: **◈ {sell_val:,}**"
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

    catches_content = "\n\n".join(catch_parts)

    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 3, "label": "Hunt",     "custom_id": f"hunt:again:{user_id}",    },
        {"type": 2, "style": 1, "label": "Sell All", "custom_id": f"hunt:sell_all:{user_id}", },
        {"type": 2, "style": 2, "label": "◀ Back",  "custom_id": f"hunt:back:{user_id}",     },
    ]}

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": title + stats_block},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": catches_content},
        {"type": 14, "divider": False, "spacing": 1},
        btn_row,
    ]}]

def build_hunt_sold_components(user_id: str, sold: dict) -> list:
    if sold["count"] == 0:
        body = f"### Inventory Sold\nYour inventory is empty.\n-# Nothing to sell."
    else:
        body = (
            f"### Inventory Sold\n"
            f"Sold **{sold['count']}** animals.\n"
            f"-# Earned **◈ {sold['total']:,}** · Balance: **◈ {data[user_id]['money']:,}**"
        )
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 3, "label": "Hunt",     "custom_id": f"hunt:again:{user_id}",    },
        {"type": 2, "style": 1, "label": "Sell All", "custom_id": f"hunt:sell_all:{user_id}", "disabled": True, },
        {"type": 2, "style": 2, "label": "◀ Back",  "custom_id": f"hunt:back:{user_id}",     },
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

# ── COLOR ─────────────────────────────────────
def build_color_panel_components(user_id: str) -> list:
    current    = data[user_id].get("color", "green")
    user_level = data[user_id].get("level", 1)
    custom_line = "Available now." if user_level >= 1200 else f"Unlocks at Level 1200 (you: {user_level})."
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": f"### 🎨 Choose Your Color\nCurrent: **{color_display_name(current)}**\n-# Cosmetic only."},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "**Standard Colors**"},
        {"type": 1, "components": [{"type": 3, "custom_id": f"hunter_color_select:{user_id}",
            "placeholder": "Select a color...", "min_values": 1, "max_values": 1, "flows": {},
            "options": [{"label": COLOR_LABELS[k], "value": k, "description": COLOR_DESCRIPTIONS[k],
                          "default": k == current} for k in COLORS.keys()]}]},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 9,
         "components": [{"type": 10, "content": f"**Custom Hex**\n{custom_line}"}],
         "accessory": {"type": 2, "style": 2, "label": "Set Custom Hex",
                        "custom_id": f"hunter_color_hex:{user_id}", }},
        _back_row(user_id),
    ]}]

# ── BIOME ─────────────────────────────────────
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
        {"type": 1, "components": [{"type": 3, "custom_id": f"biome:select:{user_id}",
            "placeholder": "Select a biome...", "min_values": 1, "max_values": 1, "flows": {},
            "options": options}]},
        _back_row(user_id),
    ]}]

# ── EQUIP (tools + ammo + vehicles) ──────────────────────
def build_equip_components(user_id: str) -> list:
    owned    = data[user_id].get("owned_tools", ["Bare Hands"])
    equipped = data[user_id].get("tool", "Bare Hands")
    t_info   = TOOLS[equipped]
    ammo_type = t_info.get("ammo_type")

    # Tool equip dropdown
    equip_opts = [
        {
            "label": f"{TOOLS[n]['emoji']} {n} (T{TOOLS[n]['tier']})",
            "value": n,
            "description": TOOLS[n]["description"],
            "default": n == equipped,
        }
        for n in owned
    ]

    equipped_ammo = data[user_id].get("equipped_ammo")
    ammo_count    = get_ammo_count(user_id, equipped_ammo) if equipped_ammo else 0
    a_info_eq     = AMMO.get(equipped_ammo, {})

    if ammo_type:
        # Build ammo equip dropdown — only ammo the user owns that matches this tool
        user_ammo_inv = data[user_id].get("ammo_inv", {})
        compatible    = [
            name for name, a in AMMO.items()
            if a["ammo_type"] == ammo_type and user_ammo_inv.get(name, 0) > 0
        ]
        if equipped_ammo and equipped_ammo not in compatible and ammo_count == 0:
            # Ammo ran out, already unequipped
            pass

        if compatible:
            ammo_opts = [
                {
                    "label": f"{AMMO[n]['emoji']} {n}",
                    "value": n,
                    "description": f"{AMMO[n]['description']} · Amount: {user_ammo_inv.get(n, 0)}",
                    "default": n == equipped_ammo,
                }
                for n in compatible
            ]
            ammo_dropdown = {"type": 1, "components": [{"type": 3,
                "custom_id": f"tools:ammo_equip:{user_id}",
                "placeholder": f"Select {AMMO_TYPE_LABELS.get(ammo_type, 'ammo')} to equip...",
                "min_values": 1, "max_values": 1, "flows": {},
                "options": ammo_opts[:25],
            }]}
        else:
            ammo_dropdown = {"type": 10, "content": f"-# No {AMMO_TYPE_LABELS.get(ammo_type, 'ammo')} in your inventory. Buy some in /shop → Ammo!"}

        if equipped_ammo and ammo_compatible_with_tool(equipped_ammo, equipped):
            ammo_status = (
                f"-# 🔸 Equipped: {a_info_eq.get('emoji','🔸')} **{equipped_ammo}** ×{ammo_count}\n"
                f"-# {USER_EMOJIS['luck_boost']} +{a_info_eq.get('boost_luck',0)}% Luck · "
                f"{USER_EMOJIS['sell_boost']} +{a_info_eq.get('boost_sell',0)}% Sell · "
                f"{USER_EMOJIS['xp_boost']} +{a_info_eq.get('boost_xp',0)}% XP"
            )
        else:
            ammo_status = f"-# ⚠️ No {AMMO_TYPE_LABELS.get(ammo_type,'ammo')} equipped — hunting is **blocked** until you equip some!"
    else:
        ammo_dropdown = None
        ammo_status   = "-# This tool requires no ammo."

    tool_desc = (
        f"### {UPGRADE_EMOJI} Tools\n"
        f"Equipped: {t_info['emoji']} **{equipped}** (Tier {get_tool_tier(equipped)})\n"
        f"-# {USER_EMOJIS['luck_boost']} +{t_info['boost_luck']}% Luck · "
        f"{USER_EMOJIS['xp_boost']} +{t_info['boost_xp']}% XP · "
        f"🎯 Catches **{t_info['multi_catch']}** per hunt\n\n"
        f"**Ammo:**\n{ammo_status}\n\n"
        f"-# To buy new tools, visit /shop → Tools Shop."
    )

    comps = [
        {"type": 10, "content": tool_desc},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 10, "content": "**Select Tool to Equip**"},
        {"type": 1, "components": [{"type": 3, "custom_id": f"tools:equip:{user_id}",
            "placeholder": "Select tool to equip...", "min_values": 1, "max_values": 1,
            "flows": {}, "options": equip_opts}]},
    ]
    if ammo_dropdown:
        comps.append({"type": 14, "divider": True, "spacing": 1})
        comps.append({"type": 10, "content": f"**Select {AMMO_TYPE_LABELS.get(ammo_type,'Ammo')} to Equip**"})
        if isinstance(ammo_dropdown, dict) and ammo_dropdown.get("type") == 1:
            comps.append(ammo_dropdown)
        else:
            comps.append(ammo_dropdown)
    elif ammo_type:
        comps.append({"type": 14, "divider": True, "spacing": 1})
        comps.append(ammo_dropdown if ammo_dropdown else {"type": 10, "content": f"-# No {AMMO_TYPE_LABELS.get(ammo_type,'ammo')} owned."})

    # Vehicle equip section
    equipped_vehicle = data[user_id].get("vehicle", "None")
    owned_vehicles   = data[user_id].get("owned_vehicles", [])
    v_info_eq        = VEHICLES.get(equipped_vehicle, {})

    if owned_vehicles:
        vehicle_opts = [
            {
                "label": f"{VEHICLES[n]['emoji']} {n}",
                "value": n,
                "description": f"-{VEHICLES[n]['boost_cd']}s cooldown · T{VEHICLES[n]['tier']}",
                "default": n == equipped_vehicle,
            }
            for n in owned_vehicles
        ]
        vehicle_section = [
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": (
                f"**Vehicle:**\n"
                f"-# {v_info_eq.get('emoji','🚗')} **{equipped_vehicle}** — -{v_info_eq.get('boost_cd',0)}s cooldown"
                if equipped_vehicle and equipped_vehicle != "None"
                else "**Vehicle:**\n-# None equipped."
            )},
            {"type": 10, "content": "**Select Vehicle to Equip**"},
            {"type": 1, "components": [{"type": 3, "custom_id": f"tools:vehicle_equip:{user_id}",
                "placeholder": "Select vehicle to equip...", "min_values": 1, "max_values": 1,
                "flows": {}, "options": vehicle_opts[:25]}]},
        ]
    else:
        vehicle_section = [
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": "**Vehicle:**\n-# No vehicles owned. Buy one in /shop → Vehicles!"},
        ]

    comps += vehicle_section
    comps.append(_back_row(user_id))

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ── SHOP (tabbed: Boosts / Tools / Ammo) ──────
def build_shop_components(user_id: str, tab: str = "boosts") -> list:
    d = data[user_id]
 
    # ── shared tab-nav dropdown ────────────────
    tab_options = [
        {"label": "🧪 Boosts",   "value": "boosts",   "default": tab == "boosts"},
        {"label": "🔧 Tools",    "value": "tools",    "default": tab == "tools"},
        {"label": "🔸 Ammo",     "value": "ammo",     "default": tab == "ammo"},
        {"label": "🚗 Vehicles", "value": "vehicles", "default": tab == "vehicles"},
    ]
    tab_dropdown = {"type": 1, "components": [{
        "type": 3,
        "custom_id": f"shop:tab_dd:{user_id}",
        "placeholder": "📋 Browse shop...",
        "min_values": 1, "max_values": 1,
        "flows": {},
        "options": tab_options,
    }]}
 
    # ── BOOSTS ────────────────────────────────
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
                "accessory": {
                    "type": 2,
                    "style": 3,
                    "label": "Buy" if not maxed else "Maxed",
                    "custom_id": f"shop:buy:{name}:{user_id}",
                    "disabled": maxed,
                },
            })
 
        header = (
            f"### 🏪 Shop — Boosts\n"
            f"**◈ {d['money']:,}** · 💎 **{d['gems']}**"
        )
        comps = [
            {"type": 10, "content": header},
            {"type": 14, "divider": True, "spacing": 1},
            tab_dropdown,
            {"type": 14, "divider": True, "spacing": 1},
            *item_sections,
            _back_row(user_id),
        ]
 
    # ── TOOLS ─────────────────────────────────
    elif tab == "tools":
        owned      = d.get("owned_tools", ["Bare Hands"])
        all_tools  = get_all_tools_sorted()
        page       = _tool_shop_page.get(user_id, 0)
        per_page   = 5
        total_pages = max(1, (len(all_tools) + per_page - 1) // per_page)
        page       = max(0, min(page, total_pages - 1))
        page_tools = all_tools[page * per_page:(page + 1) * per_page]
 
        header = (
            f"### 🏪 Shop — Tools\n"
            f"**◈ {d['money']:,}** · 💎 **{d['gems']}**"
        )
        item_sections = []
        for name, t in page_tools:
            already = name in owned
            ps      = ("✅ Owned" if already
                       else (f"◈ {t['price']:,}" if t["currency"] == "money"
                             else f"💎{t['price']}"))
            content = (
                f"{t['emoji']} **{name}** (T{t['tier']}) — {ps}\n"
                f"-# {t['description']}"
            )
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": {
                    "type": 2,
                    "style": 1 if not already else 2,
                    "label": "Buy" if not already else "Owned",
                    "custom_id": f"shop:tool_buy_acc:{name}:{user_id}",
                    "disabled": already,
                },
            })
 
        page_nav_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev",
             "custom_id": f"shop:tool_prev:{user_id}", "disabled": page == 0},
            {"type": 2, "style": 2, "label": f"Page {page+1}/{total_pages}",
             "custom_id": f"shop:tool_noop:{user_id}", "disabled": True},
            {"type": 2, "style": 2, "label": "Next ▶",
             "custom_id": f"shop:tool_next:{user_id}", "disabled": page >= total_pages - 1},
        ]}
 
        comps = [
            {"type": 10, "content": header},
            {"type": 14, "divider": True, "spacing": 1},
            tab_dropdown,
            {"type": 14, "divider": True, "spacing": 1},
            *item_sections,
            {"type": 14, "divider": True, "spacing": 1},
            page_nav_row,
            _back_row(user_id),
        ]
 
    # ── AMMO ──────────────────────────────────
    elif tab == "ammo":
        grouped: dict[str, list[str]] = {}
        for name, a in AMMO.items():
            grouped.setdefault(a["ammo_type"], []).append(name)
 
        ammo_types   = list(grouped.keys())
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
                "accessory": {
                    "type": 2,
                    "style": 1,
                    "label": "Buy",
                    "custom_id": f"shop:ammo_buy_acc:{name}:{user_id}",
                },
            })
 
        type_nav_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev Type",
             "custom_id": f"shop:ammo_prev:{user_id}", "disabled": ammo_tab_page == 0},
            {"type": 2, "style": 2, "label": "Next Type ▶",
             "custom_id": f"shop:ammo_next:{user_id}",
             "disabled": ammo_tab_page >= len(ammo_types) - 1},
        ]}
 
        comps = [
            {"type": 10, "content": header},
            {"type": 14, "divider": True, "spacing": 1},
            tab_dropdown,
            {"type": 14, "divider": True, "spacing": 1},
            *item_sections,
            {"type": 14, "divider": True, "spacing": 1},
            type_nav_row,
            _back_row(user_id),
        ]
 
    # ── VEHICLES ──────────────────────────────
    else:
        owned_v   = data[user_id].get("owned_vehicles", [])
        equipped  = data[user_id].get("vehicle", "None")
 
        all_vehicles  = list(VEHICLES.items())
        page          = _vehicle_shop_page.get(user_id, 0)
        per_page      = 5
        total_pages   = max(1, (len(all_vehicles) + per_page - 1) // per_page)
        page          = max(0, min(page, total_pages - 1))
        page_vehicles = all_vehicles[page * per_page:(page + 1) * per_page]
 
        header = (
            f"### 🏪 Shop — Vehicles\n"
            f"**◈ {d['money']:,}** · 💎 **{d['gems']}**"
        )
 
        item_sections = []
        for name, v in page_vehicles:
            already  = name in owned_v
            is_equip = name == equipped
            ps       = ("✅ Equipped" if is_equip
                        else ("📦 Owned" if already
                              else (f"◈ {v['price']:,}" if v["currency"] == "money"
                                    else f"💎{v['price']}")))
            cd_str   = f"-{v['boost_cd']}s cooldown"
            luck_str = f" · +{v['boost_luck']}% Luck" if v["boost_luck"] else ""
            content  = (
                f"{v['emoji']} **{name}** (T{v['tier']}) — {ps}\n"
                f"-# {v['description']}\n"
                f"-# {cd_str}{luck_str}"
            )
            if not already:
                acc_label, acc_style, acc_dis = "Buy",   1, False
                acc_cid = f"shop:vehicle_buy_acc:{name}:{user_id}"
            elif not is_equip:
                acc_label, acc_style, acc_dis = "Equip", 3, False
                acc_cid = f"shop:vehicle_equip_acc:{name}:{user_id}"
            else:
                acc_label, acc_style, acc_dis = "Equipped", 2, True
                acc_cid = f"shop:vehicle_noop:{user_id}"
 
            item_sections.append({
                "type": 9,
                "components": [{"type": 10, "content": content}],
                "accessory": {
                    "type": 2,
                    "style": acc_style,
                    "label": acc_label,
                    "custom_id": acc_cid,
                    "disabled": acc_dis,
                },
            })
 
        page_nav_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Prev",
             "custom_id": f"shop:vehicle_prev:{user_id}", "disabled": page == 0},
            {"type": 2, "style": 2, "label": "Next ▶",
             "custom_id": f"shop:vehicle_next:{user_id}", "disabled": page >= total_pages - 1},
        ]}
 
        comps = [
            {"type": 10, "content": header},
            {"type": 14, "divider": True, "spacing": 1},
            tab_dropdown,
            {"type": 14, "divider": True, "spacing": 1},
            *item_sections,
            {"type": 14, "divider": True, "spacing": 1},
            page_nav_row,
            _back_row(user_id),
        ]
 
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

# ─────────────────────────────────────────────
# OPT-IN PANEL
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
 
 
# ─────────────────────────────────────────────
# STEP TIP PANELS
# ─────────────────────────────────────────────
 
def build_tutorial_step(user_id: str, step: str) -> list | None:
    """Returns a v2 component list for the given step, or None if step unknown."""
 
    tips = {
        "sell": (
            "### 💰 Nice catch! Now sell it.\n"
            "Your inventory fills up fast. Hit **Sell All** on the hunt screen, "
            "or use the button in `/menu` to cash everything in at once.\n"
            "-# Sell boost increases how much ◈ you get per animal."
        ),
        "biome": (
            "### 🗺️ Try a new biome!\n"
            "You're hunting in the **Village** right now — but better biomes "
            "have rarer animals and higher payouts.\n"
            "Use `/biome` to switch once you level up enough.\n"
            "-# Each biome has a minimum level and tool tier requirement."
        ),
        "shop_tools": (
            "### 🔧 Upgrade your tool!\n"
            "Better tools catch more animals per hunt and boost your XP.\n"
            "Open `/shop` → Tools to see what's available.\n"
            "-# Higher tier tools also unlock higher tier biomes."
        ),
        "shop_ammo": (
            "### 🔸 Some tools need ammo!\n"
            "Once you get a ranged tool, you'll need to stock up on ammo.\n"
            "Buy it in `/shop` → Ammo, then equip it via `/equip`.\n"
            "-# Running out of ammo mid-hunt will block hunting until you restock."
        ),
        "equip": (
            "### ⚙️ Equip your gear!\n"
            "Bought a new tool or ammo? Don't forget to equip it — "
            "purchases don't auto-equip.\n"
            "Use `/equip` to switch tools, load ammo, and equip vehicles.\n"
            "-# Vehicles reduce your hunt cooldown — very handy later on."
        ),
        "daily": (
            "### 📅 Claim your daily!\n"
            "Free ◈ or 💎 every single day — just use `/daily`.\n"
            "Keep a streak going for a bonus multiplier on top.\n"
            "-# Missing a day decays your streak, so try to log in daily!"
        ),
        "idle": (
            "### 💤 Earn while you're away!\n"
            "Can't hunt all day? Use `/idle` to hire stacks that earn ◈ passively.\n"
            "Collect whenever you're back — no hunting required.\n"
            "-# Each stack costs more than the last, but the rate adds up."
        ),
        "tribe": (
            "### 🏕️ Join a tribe!\n"
            "Tribes share Luck, Sell, and XP boosts across all members — "
            "everyone benefits from upgrades.\n"
            "Use `/tribe` to create one or wait for an invite via `/mail`.\n"
            "-# Get a friend's user ID with `/id`."
        ),
        "prestige": (
            "### ⭐ Prestige is the endgame!\n"
            "Hit Level 1,200 and ◈ 100B? You can `/prestige` — "
            "reset your progress for a **permanent +20% to all boosts**.\n"
            "Each prestige stacks, so the grind is always worth it.\n"
            "-# Gems, tools, tribe, ammo and log are kept on prestige."
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
 

# Update
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

# ── IDLE ──────────────────────────────────────
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
            {"type": 2, "style": 3, "label": "📥 Collect",    "custom_id": f"idle:collect:{user_id}", },
            {"type": 2, "style": 1, "label": "👷 Hire Stack", "custom_id": f"idle:hire:{user_id}",    },
            {"type": 2, "style": 2, "label": "◀ Back",       "custom_id": f"nav:back:{user_id}",     },
        ]},
    ]}]

# ── DAILY ─────────────────────────────────────
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
            f"-# 🔥 Streak: **{streak}** days · +{streak}% Reward bonus\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    elif already:
        body = (
            f"### 📅 Daily\n"
            f"Already claimed today!\n"
            f"-# 🔥 Streak: **{cur_streak}** days\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    else:
        tier = get_daily_tier(data[user_id]["level"])
        body = (
            f"### 📅 Daily Reward\n"
            f"Claim your daily reward!\n"
            f"-# 🔥 Streak: **{cur_streak}** days · +{cur_streak}% Reward bonus\n"
            f"-# 💰 Possible: ◈ {tier['money_min']:,}–◈ {tier['money_max']:,} "
            f"or 💎{tier['gems_min']}–{tier['gems_max']}\n"
            f"-# Resets <t:{nxt_ts}:R>"
        )
    btns = []
    if not already and not claimed:
        btns.append({"type": 2, "style": 3, "label": "Claim Daily",
                     "custom_id": f"daily:claim:{user_id}", })
    btns.append({"type": 2, "style": 2, "label": "◀ Back",
                 "custom_id": f"nav:back:{user_id}", })
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        {"type": 1, "components": btns},
    ]}]

# ── PRESTIGE ──────────────────────────────────
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
                     "custom_id": f"prestige:confirm:{user_id}", })
    btns.append({"type": 2, "style": 2, "label": "◀ Back",
                 "custom_id": f"nav:back:{user_id}", })
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
            {"type": 2, "style": 2, "label": "◀ Menu",
             "custom_id": f"nav:menu:{user_id}", }
        ]},
    ]}]

# ── HELP ──────────────────────────────────────
def build_help_components(user_id: str) -> list:
    cmds = sorted(bot.tree.get_commands(), key=lambda c: c.name)
    lines = "\n".join(
        f"</{c.name}:{COMMAND_ID.get(c.name)}> — {c.description or 'No description'}"
        for c in cmds
    )
    content = f"### 📖 Commands\n{lines}\n-# Use /verify if blocked from commands."
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
             "components": [
                 {"type": 10, "content": content},
                 _back_row(user_id),
             ]}]

# ── MAIL ──────────────────────────────────────
def build_mail_components(user_id: str, tab: str = "tribe") -> list:
    d = data[user_id]
    tribe_style = mail_tab_style(user_id, "tribe")
    gifts_style = mail_tab_style(user_id, "gifts")
    dev_style   = mail_tab_style(user_id, "dev")
    if tab == "tribe":    tribe_style = 3
    elif tab == "gifts":  gifts_style = 3
    elif tab == "dev":    dev_style   = 3
    tab_row = {"type": 1, "components": [
        {"type": 2, "style": tribe_style, "label": "🏕️ Tribe Invites",
         "custom_id": f"mail:tab:tribe:{user_id}", },
        {"type": 2, "style": gifts_style, "label": "🎁 Gifts",
         "custom_id": f"mail:tab:gifts:{user_id}", },
        {"type": 2, "style": dev_style,   "label": "📢 Dev Mail",
         "custom_id": f"mail:tab:dev:{user_id}",   },
    ]}
    if tab == "tribe":
        tribe_inv = d.get("tribe_inv")
        if tribe_inv and tribe_inv in tribe_data:
            td    = tribe_data[tribe_inv]
            total = 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"])
            is_read   = d.get("tribe_inv_read", False)
            unread_tag = "" if is_read else " 🔴"
            content = (
                f"### 🏕️ Tribe Invites{unread_tag}\n\n"
                f"You have a pending invite to **{tribe_inv}**!\n\n"
                f"-# {TRIBE_EMOJIS['members']} {total}/{td['max_members']} members\n"
                f"-# {TRIBE_EMOJIS['luck_boost']} {td['luck_boost']}% · "
                f"{TRIBE_EMOJIS['sell_boost']} {td['sell_price_boost']}% · "
                f"{TRIBE_EMOJIS['xp_boost']} {td['xp_boost']}%"
            )
            btns = [
                {"type": 2, "style": 3, "label": "✅ Accept",
                 "custom_id": f"mail:tribe:accept:{user_id}", },
                {"type": 2, "style": 4, "label": "❌ Decline",
                 "custom_id": f"mail:tribe:decline:{user_id}", },
            ]
            d["tribe_inv_read"] = True
        else:
            content = "### 🏕️ Tribe Invites\n\n-# No pending tribe invites."
            btns = []
        btns.append({"type": 2, "style": 2, "label": "◀ Menu",
                     "custom_id": f"nav:menu:{user_id}", })
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            tab_row,
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": btns},
        ]}]
    elif tab == "gifts":
        gifts = d.get("gift_mails", [])
        if not gifts:
            content = "### 🎁 Gift Mail\n\n-# No gift mail."
            btns = [{"type": 2, "style": 2, "label": "◀ Menu",
                     "custom_id": f"nav:menu:{user_id}", }]
        else:
            lines = []
            for i, g in enumerate(gifts):
                read_tag = "" if g.get("read") else " 🔴"
                sender   = g.get("sender_name", "Unknown")
                amt_str  = g.get("amt_str", "")
                msg      = g.get("message", "")
                ts       = g.get("ts", 0)
                lines.append(
                    f"**Gift {i+1}{read_tag}** — from **{sender}**\n"
                    f"-# {amt_str} · <t:{ts}:R>\n"
                    f"-# _{msg}_"
                )
                g["read"] = True
            content = "### 🎁 Gift Mail\n\n" + "\n\n".join(lines)
            btns = [{"type": 2, "style": 4, "label": "🗑️ Clear All",
                     "custom_id": f"mail:gifts:clear:{user_id}", },
                    {"type": 2, "style": 2, "label": "◀ Menu",
                     "custom_id": f"nav:menu:{user_id}", }]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            tab_row,
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": btns},
        ]}]
    else:  # dev tab
        is_read = (d.get("mail_dev_content_read", "") == DEV_MAIL)
        if not DEV_MAIL:
            content = "### 📢 Dev Mail\n\n-# No messages from the dev team."
            btns = [{"type": 2, "style": 2, "label": "◀ Menu",
                     "custom_id": f"nav:menu:{user_id}", }]
        else:
            unread_tag = "" if is_read else " 🔴"
            content    = f"### 📢 Dev Mail{unread_tag}\n\n{DEV_MAIL}"
            btns_list  = [{"type": 2, "style": 2, "label": "◀ Menu",
                           "custom_id": f"nav:menu:{user_id}", }]
            if not is_read:
                btns_list.insert(0, {"type": 2, "style": 3, "label": "✅ Mark as Read",
                                      "custom_id": f"mail:dev:read:{user_id}", })
            btns = btns_list
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            tab_row,
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": btns},
        ]}]

# ─────────────────────────────────────────────
# BAN EMBED BUILDER  (DM / on-command display)
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
        unban_line    = ""
    else:
        duration_line = f"-# You will be unbanned <t:{exp_ts}:R> (if no appeal is submitted)."
        unban_line    = f"-# You will be unbanned (with an approved appeal) <t:{exp_ts}:R>"
 
    body = (
        f"### 🔨 You have been banned"
        + (f" for <t:{exp_ts}:R>" if exp_ts != 0 else "")
        + "!\n\n"
        f"Reason: {reason}\n\n"
        f"You can appeal **{max_app}** times using the button below. "
        f"Use your appeal chances **wisely**.\n"
        f"{unban_line}\n"
        f"{duration_line}"
    )
 
    appeal_disabled = remaining <= 0
    btn_row = {"type": 1, "components": [
        {
            "type": 2,
            "style": 2,                          # grey / no colour
            "label": f"Appeal ({remaining} left)",
            "custom_id": f"ban:appeal:{user_id}",
            "disabled": appeal_disabled,
        }
    ]}
 
    return [{"type": 17, "accent_color": 0xE74C3C, "spoiler": False, "components": [
        {"type": 10, "content": body},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

# ── TRIBE ─────────────────────────────────────
def build_tribe_components(user_id: str, tribe_name: str, page: str = "main", sort_mode: str = "rank") -> list:
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
        return "\n".join(f"{icons[r]} <@{uid}> — Lv.**{data.get(uid,{}).get('level','?')}**" for uid, r in all_m)

    total_m = 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"])

    if page == "main":
        desc_line = f"\n📝 *{td['description']}*\n" if td.get("description") else ""
        content   = (
            f"### {TRIBE_EMOJIS['tribe']} {tribe_name}{desc_line}\n"
            f"{USER_EMOJIS['levels']} Lv.**{td['level']}** · {USER_EMOJIS['xp']} **{td['xp']} XP**\n"
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
                {"type": 2, "style": 1, "label": "Members",   "custom_id": f"tribe:nav:members:{user_id}",  },
                {"type": 2, "style": 1, "label": "Perk Shop", "custom_id": f"tribe:nav:shop:{user_id}",     },
                {"type": 2, "style": 1, "label": "Actions",   "custom_id": f"tribe:nav:actions:{user_id}",  },
                {"type": 2, "style": 2, "label": sort_lbl,    "custom_id": f"tribe:sort:{user_id}",         },
            ]},
            _back_row(user_id),
        ]}]

    elif page == "members":
        content = (
            f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Members\n"
            f"{TRIBE_EMOJIS['members']} **{total_m}/{td['max_members']}**\n\n{_member_list()}"
        )
        sort_lbl = "Sort: Level" if sort_mode == "rank" else "Sort: Rank"
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": sort_lbl, "custom_id": f"tribe:sort:{user_id}",     },
                {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"tribe:nav:main:{user_id}", },
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
                 "emoji": {"id": "1500237656292855839"}, "custom_id": f"tribe:shop:luck_boost:50:5:{user_id}", },
                {"type": 2, "style": 3, "label": "Sell +5%",
                 "emoji": {"id": "1500237659275001856"}, "custom_id": f"tribe:shop:sell_price_boost:50:5:{user_id}", },
                {"type": 2, "style": 3, "label": "XP +5%",
                 "emoji": {"id": "1500237658037944400"}, "custom_id": f"tribe:shop:xp_boost:50:5:{user_id}", },
                {"type": 2, "style": 3, "label": "+1 Slot",
                 "emoji": {"id": "1500224532022296586"}, "custom_id": f"tribe:shop:max_members:100:1:{user_id}", },
            ]
        btns.append({"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"tribe:nav:main:{user_id}", })
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": btns},
        ]}]

    elif page == "actions":
        # ── ONE BIG ACTIONS DROPDOWN ──────────
        content = (
            f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Actions\n"
            f"-# Select an action from the dropdown below."
        )

        action_opts = []

        # Everyone can leave
        action_opts.append({"label": "Leave Tribe", "value": "leave",
                             "description": "Leave your current tribe."})

        if is_leader or is_officer:
            action_opts.append({"label": "Invite Player", "value": "invite",
                                 "description": "Send a tribe invite to a player."})
            action_opts.append({"label": "Kick Member", "value": "kick",
                                 "description": "Remove a member from the tribe."})
            action_opts.append({"label": "Ban List", "value": "banlist",
                                 "description": "View and manage the ban list."})
            action_opts.append({"label": "Set Description", "value": "set_desc",
                                 "description": "Set the tribe's description."})

        if is_leader:
            action_opts.append({"label": "Promote Member", "value": "promote",
                                 "description": "Promote a member to officer."})
            action_opts.append({"label": "Demote Officer", "value": "demote",
                                 "description": "Demote an officer to member."})
            action_opts.append({"label": "Transfer Leadership", "value": "transfer",
                                 "description": "Transfer leader role to an officer."})

        comps = [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:action_select:{user_id}",
                "placeholder": "Select an action...",
                "min_values": 1, "max_values": 1,
                "flows": {},
                "options": action_opts,
            }]},
            {"type": 1, "components": [
                {"type": 2, "style": 2, "label": "◀ Back", "custom_id": f"tribe:nav:main:{user_id}", },
            ]},
        ]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": comps}]

    elif page == "kick_picker":
        # Member picker for kick (all non-leaders)
        td_r    = tribe_data[tribe_name]
        targets = td_r["roles"]["officer"] + td_r["roles"]["members"]
        if not targets:
            content = f"### Kick Member\n-# No members to kick."
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": content},
                {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                    "custom_id": f"tribe:nav:actions:{user_id}", }]},
            ]}]
        opts = [{"label": f"Kick @{data.get(uid,{}).get('_display_name', uid)} (Lv.{data.get(uid,{}).get('level','?')})",
                 "value": uid, "description": f"User ID: {uid}"} for uid in targets[:25]]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {TRIBE_EMOJIS['kick']} Kick Member\n-# Select the member to kick."},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:kick_confirm:{user_id}",
                "placeholder": "Select member to kick...",
                "min_values": 1, "max_values": 1, "flows": {},
                "options": opts,
            }]},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                "custom_id": f"tribe:nav:actions:{user_id}", }]},
        ]}]

    elif page == "promote_picker":
        td_r    = tribe_data[tribe_name]
        targets = td_r["roles"]["members"]
        if not targets:
            content = f"### Promote Member\n-# No members eligible for promotion."
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": content},
                {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                    "custom_id": f"tribe:nav:actions:{user_id}", }]},
            ]}]
        opts = [{"label": f"Promote @{data.get(uid,{}).get('_display_name', uid)} (Lv.{data.get(uid,{}).get('level','?')})",
                 "value": uid, "description": f"User ID: {uid}"} for uid in targets[:25]]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {TRIBE_EMOJIS['officer']} Promote Member\n-# Select a member to promote to Officer."},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:promote_confirm:{user_id}",
                "placeholder": "Select member to promote...",
                "min_values": 1, "max_values": 1, "flows": {},
                "options": opts,
            }]},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                "custom_id": f"tribe:nav:actions:{user_id}", }]},
        ]}]

    elif page == "demote_picker":
        td_r    = tribe_data[tribe_name]
        targets = td_r["roles"]["officer"]
        if not targets:
            content = f"### Demote Officer\n-# No officers to demote."
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": content},
                {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                    "custom_id": f"tribe:nav:actions:{user_id}", }]},
            ]}]
        opts = [{"label": f"Demote @{data.get(uid,{}).get('_display_name', uid)} (Lv.{data.get(uid,{}).get('level','?')})",
                 "value": uid, "description": f"User ID: {uid}"} for uid in targets[:25]]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {TRIBE_EMOJIS['demote']} Demote Officer\n-# Select an officer to demote to Member."},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:demote_confirm:{user_id}",
                "placeholder": "Select officer to demote...",
                "min_values": 1, "max_values": 1, "flows": {},
                "options": opts,
            }]},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                "custom_id": f"tribe:nav:actions:{user_id}", }]},
        ]}]

    elif page == "transfer_picker":
        td_r    = tribe_data[tribe_name]
        targets = td_r["roles"]["officer"]
        if not targets:
            content = f"### Transfer Leadership\n-# No officers to transfer to. Promote a member first."
            return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
                {"type": 10, "content": content},
                {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                    "custom_id": f"tribe:nav:actions:{user_id}", }]},
            ]}]
        opts = [{"label": f"Transfer to @{data.get(uid,{}).get('_display_name', uid)} (Lv.{data.get(uid,{}).get('level','?')})",
                 "value": uid, "description": f"Officer — ID: {uid}"} for uid in targets[:25]]
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {TRIBE_EMOJIS['leader']} Transfer Leadership\n-# Select an officer to become the new leader."},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3,
                "custom_id": f"tribe:transfer_confirm:{user_id}",
                "placeholder": "Select new leader...",
                "min_values": 1, "max_values": 1, "flows": {},
                "options": opts,
            }]},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                "custom_id": f"tribe:nav:actions:{user_id}", }]},
        ]}]

    elif page == "banlist":
        banned  = td.get("banned", [])
        members = td["roles"]["officer"] + td["roles"]["members"]
        ban_text  = "\n".join(f"{TRIBE_EMOJIS['ban']} <@{u}>" for u in banned) or "*(none)*"
        mem_text  = "\n".join(f"🧑 <@{u}>" for u in members) or "*(none)*"
        ban_opts  = ([{"label": f"Ban {u}", "value": f"ban:{u}",
                       "description": f"Level {data.get(u,{}).get('level','?')}"} for u in members] or
                     [{"label": "No bannable members", "value": "none"}])
        unban_opts= ([{"label": f"Unban {u}", "value": f"unban:{u}"} for u in banned] or
                     [{"label": "No banned players", "value": "none"}])
        return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
            {"type": 10, "content": f"### {TRIBE_EMOJIS['tribe']} {tribe_name} — Ban List\n**Members:**\n{mem_text}\n\n**Banned:**\n{ban_text}"},
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 1, "components": [{"type": 3, "custom_id": f"tribe:ban_action:{user_id}",
                "placeholder": "Ban a member...", "min_values": 1, "max_values": 1,
                "flows": {}, "options": ban_opts[:25]}]},
            {"type": 1, "components": [{"type": 3, "custom_id": f"tribe:unban_action:{user_id}",
                "placeholder": "Unban a player...", "min_values": 1, "max_values": 1,
                "flows": {}, "options": unban_opts[:25]}]},
            {"type": 1, "components": [{"type": 2, "style": 2, "label": "◀ Back",
                                         "custom_id": f"tribe:nav:actions:{user_id}", }]},
        ]}]

    return build_tribe_components(user_id, tribe_name, "main", sort_mode)

# ── LEADERBOARD ───────────────────────────────
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
    PS = 10
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    if mode == "hunter":
        fn       = HUNTER_LB_STATS.get(stat, HUNTER_LB_STATS["Level"])
        cands    = get_server_user_ids(guild) if scope == "server" else list(data.keys())
        ranked   = sorted(cands, key=lambda u: fn(u), reverse=True)
        total    = len(ranked)
        items    = ranked[page * PS:(page + 1) * PS]
        lines    = []
        for i, uid in enumerate(items):
            pos     = page * PS + i
            val     = fn(uid)
            val_str = f"◈ {val:,}" if stat == "Money" else f"**{val:,}**"
            you     = " ← you" if uid == user_id else ""
            lines.append(f"{medals.get(pos, f'**#{pos+1}**')} <@{uid}> — {val_str}{you}")
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
        ranked   = sorted(vt, key=lambda t: tribe_data[t].get("level", 1), reverse=True)
        total    = len(ranked)
        items    = ranked[page * PS:(page + 1) * PS]
        vtribe   = data.get(user_id, {}).get("tribe")
        lines    = []
        for i, tname in enumerate(items):
            pos = page * PS + i
            lv  = tribe_data[tname].get("level", 1)
            cnt = 1 + len(tribe_data[tname]["roles"]["officer"]) + len(tribe_data[tname]["roles"]["members"])
            you = " ← your tribe" if tname == vtribe else ""
            lines.append(f"{medals.get(pos, f'**#{pos+1}**')} **{tname}** — Lv.{lv} · {cnt} members{you}")
        vpos   = next((i for i, t in enumerate(ranked) if t == vtribe), None)
        footer = f"-# Your tribe rank: **#{vpos+1}**" if vpos is not None else "-# Not ranked."
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
        components.append({"type": 1, "components": [{
            "type": 3, "custom_id": f"lb:stat:{user_id}",
            "placeholder": "Sort by stat...", "options": stat_options
        }]})

    mode_row = {"type": 1, "components": [
        {"type": 2, "style": 3 if mode == "hunter" else 1, "label": "👤 Hunters",
         "custom_id": f"lb:mode:hunter:{user_id}", },
        {"type": 2, "style": 3 if mode == "tribe" else 1,
         "label": "Tribes", "emoji": {"id": "1500237653591851080", "name": "Bot_Tribe"},
         "custom_id": f"lb:mode:tribe:{user_id}", },
    ]}
    components.append(mode_row)

    scope_label_btn = "🌐 Global" if scope == "server" else "🏠 Server"
    components.append({"type": 1, "components": [
        {"type": 2, "style": 1, "label": scope_label_btn,
         "custom_id": f"lb:scope:{user_id}", },
    ]})

    cands_len = len(get_server_user_ids(guild) if scope == "server" else list(data.keys())) \
                if mode == "hunter" else len(list(tribe_data.keys()))
    total_pages = max(1, (cands_len + PS - 1) // PS)

    components.append({"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Prev",
         "custom_id": f"lb:prev:{user_id}", "disabled": (page == 0), },
        {"type": 2, "style": 1, "label": "Next ▶",
         "custom_id": f"lb:next:{user_id}", "disabled": (page >= total_pages - 1), },
    ]})

    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        *components
    ]}]

# ── RECORD ────────────────────────────────────
def build_record_v2_components(user_id: str, biome_idx: int = 0) -> list:
    total_biomes = len(BIOME_LEVELS)
    biome_key    = BIOME_LEVELS[biome_idx][0]
    biome_req    = BIOME_LEVELS[biome_idx][1]
    user_level   = data[user_id].get("level", 1)
    if user_level < biome_req:
        content = (
            f"### {BIOME_EMOJIS[biome_key]} {BIOME_NAMES[biome_key]} — Record Book\n"
            f"🔒 **Locked**\n-# Unlocks at Level **{biome_req}**. (You: Lv.{user_level})"
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
                    f"-# ×{entry['count']} caught · ◈ {entry['total_earned']:,} earned · 🔧 {top_tool}"
                )
            else:
                lines.append(f"{ANIMAL_EMOJI} {rarity_ico} **{animal}**\n-# Not caught yet")
        content = f"### {BIOME_EMOJIS[biome_key]} {BIOME_NAMES[biome_key]} — Record Book\n\n" + "\n\n".join(lines)
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Prev Biome", "custom_id": f"record:prev:{user_id}",
         "disabled": (biome_idx == 0), },
        {"type": 2, "style": 1, "label": "Next Biome ▶", "custom_id": f"record:next:{user_id}",
         "disabled": (biome_idx >= total_biomes - 1), },
        {"type": 2, "style": 2, "label": "◀ Back to Profile", "custom_id": f"profile:main:{user_id}",
         },
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
            f"🔒 **Locked**\n-# Unlocks at Level **{biome_req}**. (Current: Lv.{user_level})"
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
                    f"-# ×{entry['count']} caught · ◈ {entry['total_earned']:,} earned · 🔧 {top_tool}"
                )
            else:
                lines.append(f"{ANIMAL_EMOJI} {rarity_ico} **{animal}**\n-# Not caught yet")
        content = f"### {BIOME_EMOJIS[biome_key]} {BIOME_NAMES[biome_key]} — {target_name}'s Record\n\n" + "\n\n".join(lines)
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Prev Biome",
         "custom_id": f"record_cmd:prev:{viewer_id}:{target_id}",
         "disabled": (biome_idx == 0), },
        {"type": 2, "style": 1, "label": "Next Biome ▶",
         "custom_id": f"record_cmd:next:{viewer_id}:{target_id}",
         "disabled": (biome_idx >= total_biomes - 1), },
    ]}
    return [{"type": 17, "accent_color": _accent(viewer_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

# ── LOG ───────────────────────────────────────
def build_log_v2_components(user_id: str, page: int = 0) -> list:
    log   = data[user_id].get("log", [])
    total = len(log)
    if not log or page >= total:
        content = "### 📋 Hunt Log\nNo hunts recorded yet.\n-# Start hunting with the Hunt button!"
        btn_row = {"type": 1, "components": [
            {"type": 2, "style": 2, "label": "◀ Back to Profile", "custom_id": f"profile:main:{user_id}", }
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
    footer = f"\n\n-# Total XP: **+{total_xp:,}**"
    if lv_ups:
        footer += f"\n-# {USER_EMOJIS['level_up']} Leveled up **×{lv_ups}**"
    ammo_line = f" · 🔸 {AMMO.get(ammo_log,{}).get('emoji','')} {ammo_log}" if ammo_log else ""
    content = (
        f"### 📋 Hunt Log — Entry {page+1}/{total}\n"
        f"-# <t:{ts}:F> · {TOOLS.get(tool,{}).get('emoji','🔧')} **{tool}**{ammo_line} · {BIOME_NAMES.get(biome, biome)}\n\n"
        + "\n\n".join(catch_lines) + footer
    )
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Newer", "custom_id": f"log:prev:{user_id}",
         "disabled": (page == 0), },
        {"type": 2, "style": 1, "label": "Older ▶", "custom_id": f"log:next:{user_id}",
         "disabled": (page >= total - 1), },
        {"type": 2, "style": 2, "label": "◀ Back to Profile", "custom_id": f"profile:main:{user_id}",
         },
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
            {"type": 10, "content": "### 📋 Hunt Log\nNo hunts recorded yet.\n-# Start hunting to build your log!"},
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
    footer = f"\n\n-# Total XP: **+{total_xp:,}**"
    if lv_ups:
        footer += f"\n-# {USER_EMOJIS['level_up']} Leveled up **×{lv_ups}**"
    ammo_line = f" · 🔸 {AMMO.get(ammo_log,{}).get('emoji','')} {ammo_log}" if ammo_log else ""
    content = (
        f"### 📋 Hunt Log — Entry {page+1}/{total}\n"
        f"-# <t:{ts}:F> · {TOOLS.get(tool,{}).get('emoji','🔧')} **{tool}**{ammo_line} · {BIOME_NAMES.get(biome, biome)}\n\n"
        + "\n\n".join(catch_lines) + footer
    )
    btn_row = {"type": 1, "components": [
        {"type": 2, "style": 1, "label": "◀ Newer", "custom_id": f"log_cmd:prev:{user_id}",
         "disabled": (page == 0), },
        {"type": 2, "style": 1, "label": "Older ▶", "custom_id": f"log_cmd:next:{user_id}",
         "disabled": (page >= total - 1), },
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        btn_row,
    ]}]

# ── PERSONAL LEADERBOARD ──────────────────────
def build_personal_leaderboard_components(user_id: str) -> list:
    d         = data[user_id]
    all_users = list(data.items())
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
        f"### 🌍 Global Rankings\n"
        f"💰 **Balance:** #{money_rank:,}/{total_players:,}\n"
        f"{USER_EMOJIS['levels']} **Level:** #{level_rank:,}/{total_players:,}\n"
        f"🎯 **Animals Caught:** #{caught_rank:,}/{total_players:,}"
        f"{tribe_section}\n\n"
        f"-# ◈ {d['money']:,} · Lv.{d['level']} · {d.get('total_caught', 0):,} caught"
    )
    row_1 = {"type": 1, "components":[
        {"type": 2, "style": 1, "label": "Main Profile",
         "custom_id": f"profile:main:{user_id}", },
        {"type": 2, "style": 1, "label": "Inventory",
         "custom_id": f"profile:inventory:{user_id}", },
        {"type": 2, "style": 1, "label": "Statistics",
         "custom_id": f"profile:statistics:{user_id}", },
    ]}
    row_2 = {"type": 1, "components":[
        {"type": 2, "style": 3, "label": "Rankings",
         "custom_id": f"profile:leaderboard:{user_id}", },
        {"type": 2, "style": 1, "label": "Hunting Log",
         "custom_id": f"profile:log:{user_id}", },
        {"type": 2, "style": 2, "label": "◀ Menu",
         "custom_id": f"nav:menu:{user_id}", },
    ]}
    return [{"type": 17, "accent_color": _accent(user_id), "spoiler": False, "components": [
        {"type": 10, "content": content},
        {"type": 14, "divider": True, "spacing": 1},
        row_1, row_2
    ]}]

# ── GIFT COMPONENTS ───────────────────────────
import secrets
gift_cache = {}

def build_gift_confirm_components(sender_id: str, recipient: discord.User, format: str, parsed: int, message: str) -> list:
    gift_id = secrets.token_hex(4)  # short safe ID

    amt_str = f"◈ {parsed:,}" if format == "money" else f"💎 {parsed:,}"

    gift_cache[gift_id] = {
        "sender_id": sender_id,
        "recipient_id": recipient.id,
        "format": format,
        "parsed": parsed,
        "message": message
    }

    content = (
        f"### 🎁 Confirm Gift\n"
        f"Send **{amt_str}** to {recipient.mention}?\n\n"
        f"> {message}\n\n"
        f"-# This action cannot be undone."
    )

    return [{
        "type": 17,
        "accent_color": _accent(sender_id),
        "spoiler": False,
        "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 3,
                        "label": "✅ Confirm",
                        "custom_id": f"gift:confirm:{gift_id}",
                        
                    },
                    {
                        "type": 2,
                        "style": 4,
                        "label": "❌ Cancel",
                        "custom_id": f"gift:cancel:{gift_id}",
                        
                    },
                ]
            },
        ]
    }]

def build_gift_sent_components(sender_id: str, recipient: discord.User, amt_str: str, bal_str: str, sent_message: str) -> list:
    content = (
        f"### 🎁 Gift Sent!\n"
        f"**{recipient.mention}** received **{amt_str}**!\n"
        f"Your balance: **{bal_str}**\n\n"
        f"Your sent message:\n> {sent_message}"
    )

    return [{
        "type": 17,
        "accent_color": _accent(sender_id),
        "spoiler": False,
        "components": [
            {"type": 10, "content": content},
            {"type": 14, "divider": True, "spacing": 1},
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 2,
                        "label": "◀ Menu",
                        "custom_id": f"nav:menu:{sender_id}",
                        
                    }
                ]
            },
        ]
    }]

# ─────────────────────────────────────────────
# NAVIGATION DISPATCHER
# ─────────────────────────────────────────────

_tribe_sort: dict[str, str] = {}

async def _navigate(interaction: discord.Interaction, user_id: str, panel: str, display_name: str = ""):
    dn = display_name or interaction.user.display_name
    nav_push(user_id, panel)
    if panel == "menu":
        await update_v2(interaction, build_menu_components(user_id, dn))
    elif panel == "shop":
        await update_v2(interaction, build_shop_components(user_id, "boosts"))
    elif panel == "biome":
        await update_v2(interaction, build_biome_panel_components(user_id))
    elif panel == "color":
        await update_v2(interaction, build_color_panel_components(user_id))
    elif panel == "equip":
        await update_v2(interaction, build_equip_components(user_id))
    elif panel == "idle":
        await update_v2(interaction, build_idle_components(user_id))
    elif panel == "daily":
        await update_v2(interaction, build_daily_components(user_id))
    elif panel == "prestige":
        await update_v2(interaction, build_prestige_components(user_id))
    elif panel == "mail":
        await update_v2(interaction, build_mail_components(user_id, "tribe"))
    elif panel == "help":
        await update_v2(interaction, build_help_components(user_id))
    elif panel == "update":
        await update_v2(interaction, build_update_components(user_id))
    elif panel == "tribe":
        tribe_nm = data[user_id].get("tribe")
        if tribe_nm and tribe_nm in tribe_data:
            await update_v2(interaction, build_tribe_components(user_id, tribe_nm, "main"))
        else:
            await update_v2(interaction, build_menu_components(user_id, dn))
    elif panel == "profile":
        await update_v2(interaction, build_profile_components(user_id, dn, active_panel="main"))
    else:
        await update_v2(interaction, build_menu_components(user_id, dn))

# ─────────────────────────────────────────────
# COMPONENT INTERACTION ROUTER
# ─────────────────────────────────────────────

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    raw    = getattr(interaction, "data", {}) or {}
    cid    = raw.get("custom_id", "")
    values = raw.get("values", [])
    parts  = cid.split(":")

    if parts[0] == "tutorial":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return

        init_tutorial(owner_id)

        if parts[1] == "optin":
            choice = parts[2]   # "yes" or "no"
            data[owner_id]["tutorial"]["enabled"] = (choice == "yes")
            save_data_users()
            if choice == "yes":
                # swap the panel for a confirmation
                await update_v2(interaction, [{"type": 17, "accent_color": _accent(owner_id),
                    "spoiler": False, "components": [{"type": 10, "content":
                        "### ✅ Tutorial tips on!\n"
                        "I'll send you a short tip each time you try something new.\n"
                        "-# Use `/tutorial off` any time to stop."
                    }]}])
            else:
                await update_v2(interaction, [{"type": 17, "accent_color": _accent(owner_id),
                    "spoiler": False, "components": [{"type": 10, "content":
                        "### 👍 No problem!\n"
                        "-# If you change your mind, use `/tutorial on`."
                    }]}])
            return

        if parts[1] == "dismiss":
            await interaction.response.defer()   # just close the interaction
            return

        if parts[1] == "stop":
            data[owner_id]["tutorial"]["enabled"] = False
            save_data_users()
            await update_v2(interaction, [{"type": 17, "accent_color": _accent(owner_id),
                "spoiler": False, "components": [{"type": 10, "content":
                    "### 🔕 Tips turned off.\n"
                    "-# Use `/tutorial on` to turn them back on any time."
                }]}])
            return

    # ── HUNT ──────────────────────────────────
    if parts[0] == "hunt":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "This panel is not yours.", discord.Color.red()); return

        if parts[1] == "again":
            init_user(owner_id)
            result = run_hunt(owner_id)
            if result.get("verify"):
                await interaction.response.send_message(embed=verify_needed_embed(owner_id), ephemeral=True); return
            if result.get("tool_locked"):
                await send_ephemeral_embed(interaction,
                    f"❌ **{result['biome_name']}** needs Tier {result['req_tier']}+. Use `/tools`.",
                    discord.Color.red()); return
            if result.get("no_ammo"):
                ran_out = result.get("ran_out", False)
                atype   = result.get("ammo_type", "ammo")
                msg     = (f"💥 You ran out of {atype}! Your ammo was unequipped.\n"
                           if ran_out else
                           f"⚠️ **{result['tool_name']}** needs {atype} equipped. Buy some in /shop → Ammo!")
                await send_ephemeral_embed(interaction, msg, discord.Color.orange()); return
            if not result["ok"]:
                remaining = result.get("remaining", 3)
                await send_ephemeral_embed(interaction,
                    f"⏳ Hunt again in **{remaining:.1f}s**.", discord.Color.orange()); return
            save_data_users()
            data[owner_id]["_display_name"] = interaction.user.display_name
            await update_v2(interaction, build_hunt_components(owner_id, result)); return

        if parts[1] == "sell_all":
            init_user(owner_id)
            sold = sell_all_inv(owner_id)
            save_data_users()
            await maybe_tutorial_tip(interaction, owner_id, "biome")
            await update_v2(interaction, build_hunt_sold_components(owner_id, sold)); return

        if parts[1] == "back":
            prev = nav_pop(owner_id)
            await _navigate(interaction, owner_id, prev, interaction.user.display_name); return

    # ── MENU NAV (dropdown) ───────────────────
    if parts[0] == "menu":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        if parts[1] == "nav":
            panel = values[0] if values else "menu"
            nav_push(owner_id, "menu")
            if panel == "hunt":
                init_user(owner_id)
                result = run_hunt(owner_id)
                if result.get("verify"):
                    await interaction.response.send_message(embed=verify_needed_embed(owner_id), ephemeral=True); return
                if result.get("tool_locked"):
                    await send_ephemeral_embed(interaction,
                        f"❌ **{result['biome_name']}** needs Tier {result['req_tier']}+.",
                        discord.Color.red()); return
                if result.get("no_ammo"):
                    ran_out = result.get("ran_out", False)
                    atype   = result.get("ammo_type", "ammo")
                    msg     = (f"💥 You ran out of {atype}! Your ammo was unequipped.\n"
                               if ran_out else
                               f"⚠️ **{result['tool_name']}** needs {atype} equipped. Buy some in /shop → Ammo!")
                    await send_ephemeral_embed(interaction, msg, discord.Color.orange()); return
                if not result["ok"]:
                    remaining = result.get("remaining", 3)
                    await send_ephemeral_embed(interaction,
                        f"⏳ Hunt again in **{remaining:.1f}s**.", discord.Color.orange()); return
                save_data_users()
                data[owner_id]["_display_name"] = interaction.user.display_name
                nav_push(owner_id, "hunt")
                await update_v2(interaction, build_hunt_components(owner_id, result)); return
            else:
                await _navigate(interaction, owner_id, panel, interaction.user.display_name); return
        if parts[1] == "help":
            nav_push(owner_id, "menu")
            await update_v2(interaction, build_help_components(owner_id)); return
        return

    # ── GENERIC NAV ───────────────────────────
    if parts[0] == "nav":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        action = parts[1]
        if action == "back":
            _nav_stack[owner_id] = ["menu"]
            await update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
        elif action == "menu":
            _nav_stack[owner_id] = ["menu"]
            await update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name))
        return

    # ── COLOR ─────────────────────────────────
    if parts[0] == "hunter_color_select":
        owner_id = parts[1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        color_key = values[0] if values else None
        if not color_key or color_key not in COLORS:
            await send_ephemeral_embed(interaction, "Invalid color.", discord.Color.red()); return
        data[owner_id]["color"] = color_key
        save_data_users()
        await update_v2(interaction, build_color_panel_components(owner_id)); return

    if parts[0] == "hunter_color_hex":
        owner_id = parts[1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        if data[owner_id]["level"] < 1200:
            await send_ephemeral_embed(interaction, f"Unlocks at Level 1200.", discord.Color.red()); return
        await interaction.response.send_modal(CustomColorModal(owner_id)); return

    # ── BIOME ─────────────────────────────────
    if parts[0] == "biome" and parts[1] == "select":
        owner_id  = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        biome_key = values[0] if values else None
        if not biome_key:
            return
        lvl_req = next((lvl for k, lvl in BIOME_LEVELS if k == biome_key), 1)
        if data[owner_id]["level"] < lvl_req:
            await send_ephemeral_embed(interaction,
                f"❌ {BIOME_NAMES[biome_key]} unlocks at Level {lvl_req}.", discord.Color.red()); return
        data[owner_id]["biome"] = biome_key
        save_data_users()
        await update_v2(interaction, build_biome_panel_components(owner_id)); return

    # ── TOOLS (equip tool or ammo) ────────────
    if parts[0] == "tools":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return

        if parts[1] == "equip":
            tool_name = values[0] if values else None
            if tool_name and tool_name in data[owner_id].get("owned_tools", []):
                old_tool = data[owner_id].get("tool", "Bare Hands")
                data[owner_id]["tool"] = tool_name
                # If switching to a different ammo-type tool, unequip incompatible ammo
                if get_tool_ammo_type(tool_name) != get_tool_ammo_type(old_tool):
                    data[owner_id]["equipped_ammo"] = None
                save_data_users()
            await update_v2(interaction, build_equip_components(owner_id)); return

        if parts[1] == "ammo_equip":
            ammo_name = values[0] if values else None
            tool_name = data[owner_id].get("tool", "Bare Hands")
            if ammo_name and ammo_name in AMMO and ammo_compatible_with_tool(ammo_name, tool_name):
                if get_ammo_count(owner_id, ammo_name) > 0:
                    data[owner_id]["equipped_ammo"] = ammo_name
                    save_data_users()
                else:
                    await send_ephemeral_embed(interaction, "❌ You don't own that ammo.", discord.Color.red()); return
            await update_v2(interaction, build_equip_components(owner_id)); return

    # ── SHOP ──────────────────────────────────
    if parts[0] == "shop":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
 
        # ── tab navigation (new dropdown) ──────
        if parts[1] == "tab_dd":
            tab = values[0] if values else "boosts"
            await update_v2(interaction, build_shop_components(owner_id, tab)); return
 
        # legacy tab buttons (kept for backward compat if any stale messages exist)
        if parts[1] == "tab":
            tab = parts[2]
            await update_v2(interaction, build_shop_components(owner_id, tab)); return
 
        # ── boosts: accessory buy button ───────
        if parts[1] == "buy":
            # custom_id format: shop:buy:{item_name}:{user_id}
            # parts[2] = item_name, parts[-1] already = owner_id
            item_name = parts[2]
            if item_name not in SHOP_BOOST_ITEMS:
                await send_ephemeral_embed(interaction, "Unknown item.", discord.Color.red()); return
            item      = SHOP_BOOST_ITEMS[item_name]
            boost_key = item.get("boost_key")
            boost_amt = item.get("boost_amt", 0)
            current   = data[owner_id]["boosts"].get(boost_key, 0) if boost_key else 0
            if boost_key and current >= boost_amt * item["max_qty"]:
                await send_ephemeral_embed(interaction, f"Max {item_name} already owned.", discord.Color.red()); return
            if item["currency"] == "gems":
                if data[owner_id]["gems"] < item["price"]:
                    await send_ephemeral_embed(interaction, f"Need 💎{item['price']}.", discord.Color.red()); return
                data[owner_id]["gems"] -= item["price"]
            else:
                if data[owner_id]["money"] < item["price"]:
                    await send_ephemeral_embed(interaction, f"Need ◈ {item['price']:,}.", discord.Color.red()); return
                data[owner_id]["money"] -= item["price"]
            if boost_key:
                data[owner_id]["boosts"][boost_key] = current + boost_amt
            save_data_users()
            await update_v2(interaction, build_shop_components(owner_id, "boosts")); return
 
        # ── tools page nav ─────────────────────
        if parts[1] == "tool_prev":
            _tool_shop_page[owner_id] = max(0, _tool_shop_page.get(owner_id, 0) - 1)
            await update_v2(interaction, build_shop_components(owner_id, "tools")); return
 
        if parts[1] == "tool_next":
            _tool_shop_page[owner_id] = _tool_shop_page.get(owner_id, 0) + 1
            await update_v2(interaction, build_shop_components(owner_id, "tools")); return
 
        if parts[1] == "tool_noop":
            await interaction.response.defer(); return
 
        # ── tools: accessory buy button ─────────
        if parts[1] == "tool_buy_acc":
            # custom_id: shop:tool_buy_acc:{tool_name}:{user_id}
            tool_name = parts[2]
            if tool_name not in TOOLS:
                await send_ephemeral_embed(interaction, "Unknown tool.", discord.Color.red()); return
            if tool_name in data[owner_id].get("owned_tools", []):
                await send_ephemeral_embed(interaction, "Already owned.", discord.Color.red()); return
            t = TOOLS[tool_name]
            if t["currency"] == "gems":
                if data[owner_id]["gems"] < t["price"]:
                    await send_ephemeral_embed(interaction, f"Need 💎{t['price']}.", discord.Color.red()); return
                data[owner_id]["gems"] -= t["price"]
            else:
                if data[owner_id]["money"] < t["price"]:
                    await send_ephemeral_embed(interaction, f"Need ◈ {t['price']:,}.", discord.Color.red()); return
                data[owner_id]["money"] -= t["price"]
            data[owner_id]["owned_tools"].append(tool_name)
            data[owner_id]["tool"] = tool_name
            save_data_users()
            await update_v2(interaction, build_shop_components(owner_id, "tools")); return
 
        # ── legacy dropdown tool buy (kept for old messages) ──
        if parts[1] == "tool_buy":
            tool_name = values[0] if values else None
            if not tool_name or tool_name not in TOOLS:
                await send_ephemeral_embed(interaction, "Unknown tool.", discord.Color.red()); return
            if tool_name in data[owner_id].get("owned_tools", []):
                await send_ephemeral_embed(interaction, "Already owned.", discord.Color.red()); return
            t = TOOLS[tool_name]
            if t["currency"] == "gems":
                if data[owner_id]["gems"] < t["price"]:
                    await send_ephemeral_embed(interaction, f"Need 💎{t['price']}.", discord.Color.red()); return
                data[owner_id]["gems"] -= t["price"]
            else:
                if data[owner_id]["money"] < t["price"]:
                    await send_ephemeral_embed(interaction, f"Need ◈ {t['price']:,}.", discord.Color.red()); return
                data[owner_id]["money"] -= t["price"]
            data[owner_id]["owned_tools"].append(tool_name)
            data[owner_id]["tool"] = tool_name
            save_data_users()
            await update_v2(interaction, build_shop_components(owner_id, "tools")); return
 
        # ── ammo: accessory buy button → modal ──
        if parts[1] == "ammo_buy_acc":
            # custom_id: shop:ammo_buy_acc:{ammo_name}:{user_id}
            ammo_name = parts[2]
            if ammo_name not in AMMO:
                await send_ephemeral_embed(interaction, "Unknown ammo.", discord.Color.red()); return
            await interaction.response.send_modal(AmmoBuyModal(owner_id, ammo_name)); return
 
        # legacy ammo dropdown buy (kept for old messages)
        if parts[1] == "ammo_buy":
            ammo_name = values[0] if values else None
            if not ammo_name or ammo_name not in AMMO:
                await send_ephemeral_embed(interaction, "Unknown ammo.", discord.Color.red()); return
            await interaction.response.send_modal(AmmoBuyModal(owner_id, ammo_name)); return
 
        if parts[1] == "ammo_prev":
            _ammo_shop_page[owner_id] = max(0, _ammo_shop_page.get(owner_id, 0) - 1)
            await update_v2(interaction, build_shop_components(owner_id, "ammo")); return
 
        if parts[1] == "ammo_next":
            _ammo_shop_page[owner_id] = _ammo_shop_page.get(owner_id, 0) + 1
            await update_v2(interaction, build_shop_components(owner_id, "ammo")); return
 
        if parts[1] == "ammo_noop":
            await interaction.response.defer(); return
 
        # ── vehicles page nav ───────────────────
        if parts[1] == "vehicle_prev":
            _vehicle_shop_page[owner_id] = max(0, _vehicle_shop_page.get(owner_id, 0) - 1)
            await update_v2(interaction, build_shop_components(owner_id, "vehicles")); return
 
        if parts[1] == "vehicle_next":
            _vehicle_shop_page[owner_id] = _vehicle_shop_page.get(owner_id, 0) + 1
            await update_v2(interaction, build_shop_components(owner_id, "vehicles")); return
 
        if parts[1] == "vehicle_noop":
            await interaction.response.defer(); return
 
        # ── vehicles: accessory buy button ──────
        if parts[1] == "vehicle_buy_acc":
            # custom_id: shop:vehicle_buy_acc:{vehicle_name}:{user_id}
            vehicle_name = parts[2]
            if vehicle_name not in VEHICLES:
                await send_ephemeral_embed(interaction, "Unknown vehicle.", discord.Color.red()); return
            if vehicle_name in data[owner_id].get("owned_vehicles", []):
                await send_ephemeral_embed(interaction, "Already owned.", discord.Color.red()); return
            v = VEHICLES[vehicle_name]
            if v["currency"] == "gems":
                if data[owner_id]["gems"] < v["price"]:
                    await send_ephemeral_embed(interaction, f"Need 💎{v['price']}.", discord.Color.red()); return
                data[owner_id]["gems"] -= v["price"]
            else:
                if data[owner_id]["money"] < v["price"]:
                    await send_ephemeral_embed(interaction, f"Need ◈ {v['price']:,}.", discord.Color.red()); return
                data[owner_id]["money"] -= v["price"]
            data[owner_id].setdefault("owned_vehicles", []).append(vehicle_name)
            data[owner_id]["vehicle"] = vehicle_name
            save_data_users()
            await update_v2(interaction, build_shop_components(owner_id, "vehicles")); return
 
        # ── vehicles: accessory equip button ────
        if parts[1] == "vehicle_equip_acc":
            vehicle_name = parts[2]
            if vehicle_name in data[owner_id].get("owned_vehicles", []):
                data[owner_id]["vehicle"] = vehicle_name
                save_data_users()
            await update_v2(interaction, build_shop_components(owner_id, "vehicles")); return
 
        # legacy dropdown vehicle buy/equip (kept for old messages)
        if parts[1] == "vehicle_buy":
            vehicle_name = values[0] if values else None
            if not vehicle_name or vehicle_name not in VEHICLES:
                await send_ephemeral_embed(interaction, "Unknown vehicle.", discord.Color.red()); return
            if vehicle_name in data[owner_id].get("owned_vehicles", []):
                await send_ephemeral_embed(interaction, "Already owned.", discord.Color.red()); return
            v = VEHICLES[vehicle_name]
            if v["currency"] == "gems":
                if data[owner_id]["gems"] < v["price"]:
                    await send_ephemeral_embed(interaction, f"Need 💎{v['price']}.", discord.Color.red()); return
                data[owner_id]["gems"] -= v["price"]
            else:
                if data[owner_id]["money"] < v["price"]:
                    await send_ephemeral_embed(interaction, f"Need ◈ {v['price']:,}.", discord.Color.red()); return
                data[owner_id]["money"] -= v["price"]
            data[owner_id].setdefault("owned_vehicles", []).append(vehicle_name)
            data[owner_id]["vehicle"] = vehicle_name
            save_data_users()
            await update_v2(interaction, build_shop_components(owner_id, "vehicles")); return
 
        if parts[1] == "vehicle_equip":
            vehicle_name = values[0] if values else None
            if vehicle_name and vehicle_name in data[owner_id].get("owned_vehicles", []):
                data[owner_id]["vehicle"] = vehicle_name
                save_data_users()
            await update_v2(interaction, build_equip_components(owner_id)); return

    # ── IDLE ──────────────────────────────────
    if parts[0] == "idle":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        if parts[1] == "collect":
            collect_idle(owner_id)
            save_data_users()
            await update_v2(interaction, build_idle_components(owner_id)); return
        if parts[1] == "hire":
            idle = data[owner_id]["idle"]
            cost = idle_cost_for_stack(idle["stacks"])
            if data[owner_id]["money"] < cost:
                await send_ephemeral_embed(interaction, f"Need ◈ {cost:,}.", discord.Color.red()); return
            collect_idle(owner_id)
            data[owner_id]["money"] -= cost
            idle["stacks"] += 1; idle["active"] = True; idle["started_at"] = time.time()
            save_data_users()
            await update_v2(interaction, build_idle_components(owner_id)); return

    # ── DAILY ─────────────────────────────────
    if parts[0] == "daily" and parts[1] == "claim":
        owner_id  = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        today_str = today_utc()
        last_date = data[owner_id].get("last_daily_date", "")
        if last_date == today_str:
            await update_v2(interaction, build_daily_components(owner_id)); return
        streak = calc_streak(last_date, data[owner_id].get("daily_streak", 0)) + 1
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
            data[owner_id]["money"] += amt
            data[owner_id]["total_money_earned"] = data[owner_id].get("total_money_earned", 0) + amt
        else:
            base = random.randint(tier["gems_min"], tier["gems_max"])
            amt  = int(base * bonus)
            data[owner_id]["gems"] += amt
        save_data_users()
        await update_v2(interaction, build_daily_components(owner_id, claimed=True, reward_type=rtype, reward_amt=amt, streak=streak)); return

    # ── PRESTIGE ──────────────────────────────
    if parts[0] == "prestige" and parts[1] == "confirm":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        if data[owner_id]["level"] < PRESTIGE_MIN_LEVEL or data[owner_id]["money"] < PRESTIGE_MIN_MONEY:
            await send_ephemeral_embed(interaction, "Requirements not met.", discord.Color.red()); return
        new_p = data[owner_id].get("prestige", 0) + 1
        data[owner_id].update({"prestige": new_p, "level": 1, "xp": 0, "money": 0,
                                "inv": [], "biome": "village", "record": {}, "total_caught": 0})
        save_data_users()
        await update_v2(interaction, build_prestige_done_components(owner_id, new_p)); return

    # ── MAIL ──────────────────────────────────
    if parts[0] == "mail":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return

        if parts[1] == "tab":
            tab = parts[2]
            if tab == "dev" and DEV_MAIL:
                data[owner_id]["mail_dev_content_read"] = DEV_MAIL
            await update_v2(interaction, build_mail_components(owner_id, tab))
            save_data_users()
            return

        if parts[1] == "tribe":
            sub       = parts[2]
            tribe_inv = data[owner_id].get("tribe_inv")
            if sub == "accept":
                if not tribe_inv or tribe_inv not in tribe_data:
                    await send_ephemeral_embed(interaction, "Tribe no longer exists.", discord.Color.red()); return
                if data[owner_id].get("tribe"):
                    await send_ephemeral_embed(interaction, "Already in a tribe.", discord.Color.red()); return
                td_a  = tribe_data[tribe_inv]
                total = 1 + len(td_a["roles"]["officer"]) + len(td_a["roles"]["members"])
                if total >= td_a["max_members"]:
                    await send_ephemeral_embed(interaction, "Tribe is full.", discord.Color.red()); return
                td_a["roles"]["members"].append(owner_id)
                if owner_id in td_a.get("invites", []): td_a["invites"].remove(owner_id)
                data[owner_id]["tribe"]         = tribe_inv
                data[owner_id]["tribe_inv"]     = None
                data[owner_id]["tribe_inv_read"] = False
                save_data_users(); save_data_tribe()
                await update_v2(interaction, build_mail_components(owner_id, "tribe")); return
            elif sub == "decline":
                if tribe_inv and tribe_inv in tribe_data:
                    if owner_id in tribe_data[tribe_inv].get("invites", []):
                        tribe_data[tribe_inv]["invites"].remove(owner_id)
                data[owner_id]["tribe_inv"]      = None
                data[owner_id]["tribe_inv_read"]  = False
                save_data_users(); save_data_tribe()
                await update_v2(interaction, build_mail_components(owner_id, "tribe")); return

        if parts[1] == "gifts" and parts[2] == "clear":
            data[owner_id]["gift_mails"] = []
            save_data_users()
            await update_v2(interaction, build_mail_components(owner_id, "gifts")); return

        if parts[1] == "dev" and parts[2] == "read":
            data[owner_id]["mail_dev_content_read"] = DEV_MAIL
            save_data_users()
            await update_v2(interaction, build_mail_components(owner_id, "dev")); return

        return

    # ── GIFT CONFIRM ──────────────────────────
    if parts[0] == "gift":
        action = parts[1]
        gift_id = parts[2]

        gift_data = gift_cache.get(gift_id)

        if not gift_data:
            await send_ephemeral_embed(
                interaction,
                "❌ This gift confirmation expired.",
                discord.Color.red()
            )
            return

        owner_id = gift_data["sender_id"]

        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(
                interaction,
                "Not yours.",
                discord.Color.red()
            )
            return

        if action == "cancel":
            gift_cache.pop(gift_id, None)
            await update_v2(
                interaction,
                build_menu_components(owner_id, interaction.user.display_name)
            )
            return
        if action == "confirm":
            recipient_id = str(gift_data["recipient_id"])
            fmt          = gift_data["format"]
            parsed       = int(gift_data["parsed"])
            message      = gift_data["message"]
            init_user(recipient_id)
            icon = "◈" if fmt == "money" else "💎"
            if data[owner_id][fmt] < parsed:
                await send_ephemeral_embed(
                    interaction,
                    f"❌ Not enough {icon}!",
                    discord.Color.red()
                )
                return
            data[owner_id][fmt]     -= parsed
            data[recipient_id][fmt] += parsed
            amt_str = (
                f"◈ {parsed:,}"
                if fmt == "money"
                else f"💎 {parsed:,}"
            )
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
            save_data_users()
            try:
                recipient_user = await bot.fetch_user(int(recipient_id))
                try:
                    await recipient_user.send(
                        embed=discord.Embed(
                            title="🎁 You received a gift!",
                            description=(
                                f"**{interaction.user.display_name}** sent you **{amt_str}**!\n\n"
                                f"> {message}\n\n"
                                f"-# Use `/mail` to view your gift mail."
                            ),
                            color=discord.Color.green()
                        )
                    )
                except Exception:
                    pass

                gift_cache.pop(gift_id, None)

                await update_v2(
                    interaction,
                    build_gift_sent_components(
                        owner_id,
                        recipient_user,
                        amt_str,
                        bal_str,
                        message
                    )
                )
            except Exception:
                gift_cache.pop(gift_id, None)
                await send_ephemeral_embed(interaction, f"✅ Gift sent! ({amt_str})", discord.Color.green())
            return

    # ── TRIBE NAVIGATION ──────────────────────
    if parts[0] == "tribe":
        action   = parts[1]
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        tribe_nm = data[owner_id].get("tribe")
        if not tribe_nm or tribe_nm not in tribe_data:
            await send_ephemeral_embed(interaction, "You're not in a tribe.", discord.Color.red()); return
        sort = _tribe_sort.get(owner_id, "rank")

        if action == "nav":
            page = parts[2]
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, page, sort)); return

        if action == "sort":
            new_sort = "level" if sort == "rank" else "rank"
            _tribe_sort[owner_id] = new_sort
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "main", new_sort)); return

        if action == "shop":
            boost_key = parts[2]; cost = int(parts[3]); amount = int(parts[4])
            if data[owner_id]["gems"] < cost:
                await send_ephemeral_embed(interaction, f"Need 💎{cost}.", discord.Color.red()); return
            data[owner_id]["gems"] -= cost
            tribe_data[tribe_nm][boost_key] = tribe_data[tribe_nm].get(boost_key, 0) + amount
            save_data_tribe(); save_data_users()
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "shop", sort)); return

        if action == "ban_action":
            val = values[0] if values else "none"
            if val != "none":
                a, target = val.split(":", 1)
                if a == "ban":
                    td_r = tribe_data[tribe_nm]
                    for role in ("officer", "members"):
                        if target in td_r["roles"][role]: td_r["roles"][role].remove(target)
                    if target in data: data[target]["tribe"] = None
                    blist = td_r.setdefault("banned", [])
                    if target not in blist: blist.append(target)
                    save_data_tribe(); save_data_users()
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort)); return

        if action == "unban_action":
            val = values[0] if values else "none"
            if val != "none":
                a, target = val.split(":", 1)
                if a == "unban":
                    blist = tribe_data[tribe_nm].get("banned", [])
                    if target in blist: blist.remove(target)
                    save_data_tribe()
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort)); return

        # ── NEW: ACTIONS DROPDOWN HANDLER ──────
        if action == "action_select":
            sub = values[0] if values else None
            if not sub:
                return

            if sub == "leave":
                td_l      = tribe_data[tribe_nm]
                total_m   = 1 + len(td_l["roles"]["officer"]) + len(td_l["roles"]["members"])
                is_leader = td_l["roles"]["leader"] == owner_id
                if is_leader and total_m > 1:
                    await interaction.response.send_modal(TribeLeaveLeaderModal(owner_id, tribe_nm)); return
                if is_leader and total_m == 1:
                    del tribe_data[tribe_nm]
                    data[owner_id]["tribe"] = None
                    save_data_users(); save_data_tribe()
                    await update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name)); return
                for role in ("officer", "members"):
                    if owner_id in td_l["roles"][role]: td_l["roles"][role].remove(owner_id)
                data[owner_id]["tribe"] = None
                save_data_users(); save_data_tribe()
                await update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name)); return

            if sub == "invite":
                await interaction.response.send_modal(TribeInviteModal(owner_id, tribe_nm)); return

            if sub == "kick":
                await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "kick_picker", sort)); return

            if sub == "banlist":
                await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort)); return

            if sub == "set_desc":
                await interaction.response.send_modal(TribeSetDescModal(owner_id, tribe_nm)); return

            if sub == "promote":
                await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "promote_picker", sort)); return

            if sub == "demote":
                await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "demote_picker", sort)); return

            if sub == "transfer":
                await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "transfer_picker", sort)); return

            return

        # ── PICKER CONFIRM HANDLERS ──────────
        if action == "kick_confirm":
            target = values[0] if values else None
            if target:
                td_r = tribe_data[tribe_nm]
                for role in ("officer", "members"):
                    if target in td_r["roles"][role]: td_r["roles"][role].remove(target)
                if target in data: data[target]["tribe"] = None; data[target]["tribe_inv"] = None
                save_data_users(); save_data_tribe()
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort)); return

        if action == "promote_confirm":
            target = values[0] if values else None
            if target:
                td_r = tribe_data[tribe_nm]
                if target in td_r["roles"]["members"]:
                    td_r["roles"]["members"].remove(target)
                    td_r["roles"]["officer"].append(target)
                save_data_tribe()
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort)); return

        if action == "demote_confirm":
            target = values[0] if values else None
            if target:
                td_r = tribe_data[tribe_nm]
                if target in td_r["roles"]["officer"]:
                    td_r["roles"]["officer"].remove(target)
                    td_r["roles"]["members"].append(target)
                save_data_tribe()
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "actions", sort)); return

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
            await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "main", sort)); return

        # Legacy action handler (kept for backward compat with old modal flows)
        if action == "action":
            sub = parts[2]
            if sub == "invite":
                await interaction.response.send_modal(TribeInviteModal(owner_id, tribe_nm)); return
            if sub == "set_desc":
                await interaction.response.send_modal(TribeSetDescModal(owner_id, tribe_nm)); return
            if sub == "banlist":
                await update_v2(interaction, build_tribe_components(owner_id, tribe_nm, "banlist", sort)); return
            if sub == "leave":
                td_l      = tribe_data[tribe_nm]
                total_m   = 1 + len(td_l["roles"]["officer"]) + len(td_l["roles"]["members"])
                is_leader = td_l["roles"]["leader"] == owner_id
                if is_leader and total_m > 1:
                    await interaction.response.send_modal(TribeLeaveLeaderModal(owner_id, tribe_nm)); return
                if is_leader and total_m == 1:
                    del tribe_data[tribe_nm]
                    data[owner_id]["tribe"] = None
                    save_data_users(); save_data_tribe()
                    await update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name)); return
                for role in ("officer", "members"):
                    if owner_id in td_l["roles"][role]: td_l["roles"][role].remove(owner_id)
                data[owner_id]["tribe"] = None
                save_data_users(); save_data_tribe()
                await update_v2(interaction, build_menu_components(owner_id, interaction.user.display_name)); return

    # ── TRIBE INVITE ACCEPT/DECLINE (DM method) ──
    if cid.startswith("tribe_invite_accept:") or cid.startswith("tribe_invite_decline:"):
        action_str, owner_id, tribe_nm = cid.split(":", 2)
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        if action_str.endswith("accept"):
            if data[owner_id].get("tribe"):
                await send_ephemeral_embed(interaction, "Already in a tribe.", discord.Color.red()); return
            if tribe_nm not in tribe_data:
                await send_ephemeral_embed(interaction, "Tribe no longer exists.", discord.Color.red()); return
            td_a  = tribe_data[tribe_nm]
            total = 1 + len(td_a["roles"]["officer"]) + len(td_a["roles"]["members"])
            if total >= td_a["max_members"]:
                await send_ephemeral_embed(interaction, "Tribe is full.", discord.Color.red()); return
            td_a["roles"]["members"].append(owner_id)
            if owner_id in td_a.get("invites", []): td_a["invites"].remove(owner_id)
            data[owner_id]["tribe"] = tribe_nm; data[owner_id]["tribe_inv"] = None
            save_data_users(); save_data_tribe()
            await send_ephemeral_embed(interaction, f"✅ Joined **{tribe_nm}**!", discord.Color.green())
        else:
            if tribe_nm in tribe_data and owner_id in tribe_data[tribe_nm].get("invites", []):
                tribe_data[tribe_nm]["invites"].remove(owner_id)
            data[owner_id]["tribe_inv"] = None
            save_data_users()
            await send_ephemeral_embed(interaction, "Invite declined.", discord.Color.red())
        return
    
    # ── BAN APPEAL BUTTON ─────────────────────────
    if parts[0] == "ban":
        owner_id = parts[2]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        if parts[1] == "appeal":
            b = get_ban(owner_id)
            if b.get("appeals_used", 0) >= b.get("appeals_max", 2):
                await send_ephemeral_embed(interaction, "❌ No appeal chances left.", discord.Color.red()); return
            await interaction.response.send_modal(BanAppealModal(owner_id)); return

    # ── PROFILE ───────────────────────────────
    if parts[0] == "profile":
        owner_id = parts[-1]
        panel = parts[1]
        if panel == "main":
            nav_push(owner_id, "profile")
            await update_v2(interaction, build_profile_components(owner_id, interaction.user.display_name, "main")); return
        if panel == "inventory":
            nav_push(owner_id, "profile:inventory")
            await update_v2(interaction, build_inventory_components(owner_id, interaction.user.display_name)); return
        if panel == "statistics":
            nav_push(owner_id, "profile:statistics")
            await update_v2(interaction, build_statistics_components(owner_id, interaction.user.display_name)); return
        if panel == "leaderboard":
            nav_push(owner_id, "profile:leaderboard")
            await update_v2(interaction, build_personal_leaderboard_components(owner_id)); return
        if panel == "log":
            nav_push(owner_id, "profile:log")
            log_page = _profile_log_page.get(owner_id, 0)
            await update_v2(interaction, build_log_v2_components(owner_id, log_page)); return
        nav_push(owner_id, "profile")
        await _navigate(interaction, owner_id, panel, interaction.user.display_name); return

    # ── LOG PROFILE ───────────────────────────
    if parts[0] == "log":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        current_page = _profile_log_page.get(owner_id, 0)
        total        = len(data[owner_id].get("log", []))
        if parts[1] == "prev":
            _profile_log_page[owner_id] = max(0, current_page - 1)
        elif parts[1] == "next":
            _profile_log_page[owner_id] = min(total - 1, current_page + 1)
        await update_v2(interaction, build_log_v2_components(owner_id, _profile_log_page[owner_id])); return

    # ── RECORD PROFILE ────────────────────────
    if parts[0] == "record":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        current_page = _profile_record_page.get(owner_id, 0)
        total        = len(BIOME_LEVELS)
        if parts[1] == "prev":
            _profile_record_page[owner_id] = max(0, current_page - 1)
        elif parts[1] == "next":
            _profile_record_page[owner_id] = min(total - 1, current_page + 1)
        await update_v2(interaction, build_record_v2_components(owner_id, _profile_record_page[owner_id])); return

    # ── LOG CMD ───────────────────────────────
    if parts[0] == "log_cmd":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        current_page = _log_state.get(owner_id, 0)
        total        = len(data[owner_id].get("log", []))
        if parts[1] == "prev":
            _log_state[owner_id] = max(0, current_page - 1)
        elif parts[1] == "next":
            _log_state[owner_id] = min(total - 1, current_page + 1)
        await update_v2(interaction, build_log_standalone_v2_components(owner_id, _log_state[owner_id])); return

    # ── RECORD CMD ────────────────────────────
    if parts[0] == "record_cmd":
        action    = parts[1]
        viewer_id = parts[2]
        target_id = parts[3]
        if str(interaction.user.id) != viewer_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        state        = _record_state.get(viewer_id, {"target_id": target_id, "biome_idx": 0})
        current_page = state["biome_idx"]
        total        = len(BIOME_LEVELS)
        if action == "prev":
            state["biome_idx"] = max(0, current_page - 1)
        elif action == "next":
            state["biome_idx"] = min(total - 1, current_page + 1)
        _record_state[viewer_id] = state
        await update_v2(interaction, build_record_standalone_v2_components(viewer_id, target_id, state["biome_idx"])); return

    # ── LEADERBOARD ───────────────────────────
    if parts[0] == "lb":
        owner_id = parts[-1]
        if str(interaction.user.id) != owner_id:
            await send_ephemeral_embed(interaction, "Not yours.", discord.Color.red()); return
        state  = _lb_state.get(owner_id, {"mode": "hunter", "scope": "global", "stat": "Level", "page": 0, "guild": interaction.guild})
        action = parts[1]
        if action == "stat":
            state["stat"] = values[0] if values else "Level"; state["page"] = 0
        elif action == "mode":
            state["mode"] = parts[2]; state["stat"] = "Level"; state["page"] = 0
        elif action == "scope":
            state["scope"] = "global" if state["scope"] == "server" else "server"; state["page"] = 0
        elif action == "prev":
            state["page"] = max(0, state["page"] - 1)
        elif action == "next":
            PS = 10
            cands = (get_server_user_ids(state["guild"]) if state["scope"] == "server" else list(data.keys())) \
                    if state["mode"] == "hunter" else list(tribe_data.keys())
            total_pages = max(1, (len(cands) + PS - 1) // PS)
            state["page"] = min(total_pages - 1, state["page"] + 1)
        _lb_state[owner_id] = state
        await update_v2(interaction, build_leaderboard_v2_components(
            owner_id, state["guild"], state["mode"], state["scope"], state["stat"], state["page"])); return

# ─────────────────────────────────────────────
# MODALS
# ─────────────────────────────────────────────

class CustomColorModal(discord.ui.Modal, title="Custom Embed Color"):
    hex_input = discord.ui.TextInput(label="Hex Color Code", placeholder="#FF69B4", required=True, max_length=7)
    def __init__(self, user_id):
        super().__init__(); self.user_id = str(user_id)
    async def on_submit(self, interaction: discord.Interaction):
        raw = self.hex_input.value.strip().lstrip("#")
        if len(raw) != 6 or not all(c in string.hexdigits for c in raw):
            await interaction.response.send_message(
                embed=discord.Embed(description="Invalid hex. Use `#RRGGBB`.", color=discord.Color.red()), ephemeral=True); return
        data[self.user_id]["color"] = f"#{raw.upper()}"
        save_data_users()
        await update_v2(interaction, build_color_panel_components(self.user_id))

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
        raw = self.qty_input.value.strip()
        if not raw.isdigit() or int(raw) <= 0:
            await send_ephemeral_embed(interaction, "❌ Enter a positive whole number.", discord.Color.red())
            return
 
        qty = int(raw)
        a   = AMMO.get(self.ammo_name)
        if not a:
            await send_ephemeral_embed(interaction, "❌ Unknown ammo.", discord.Color.red())
            return
 
        # How many can still fit in the stack?
        current_owned = data[self.user_id].get("ammo_inv", {}).get(self.ammo_name, 0)
        can_buy       = AMMO_MAX_STACK - current_owned
 
        if can_buy <= 0:
            await send_ephemeral_embed(
                interaction,
                f"❌ You already own the maximum amount of **{self.ammo_name}** "
                f"({AMMO_MAX_STACK:,} shots). Sell or use some first.",
                discord.Color.red(),
            )
            return
 
        if qty > can_buy:
            await send_ephemeral_embed(
                interaction,
                f"❌ You can only buy **{can_buy:,}** more {self.ammo_name} "
                f"(stack limit: {AMMO_MAX_STACK:,}, you own: {current_owned:,}).",
                discord.Color.red(),
            )
            return
 
        total_cost = a["price"] * qty
        currency   = a["currency"]
        icon       = "◈" if currency == "money" else "💎"
 
        if data[self.user_id][currency] < total_cost:
            await send_ephemeral_embed(
                interaction,
                f"❌ Need {icon} {total_cost:,} to buy {qty:,}× {self.ammo_name}.",
                discord.Color.red(),
            )
            return
 
        data[self.user_id][currency]                     -= total_cost
        inv                                               = data[self.user_id].setdefault("ammo_inv", {})
        inv[self.ammo_name]                               = current_owned + qty
        save_data_users()
 
        await update_v2(interaction, build_shop_components(self.user_id, "ammo"))


class TribeInviteModal(discord.ui.Modal, title="Invite a Player"):
    uid_input = discord.ui.TextInput(label="User ID", placeholder="123456789012345678", required=True, max_length=100)
    def __init__(self, user_id, tribe_name):
        super().__init__(); self.user_id = str(user_id); self.tribe_name = tribe_name
    async def on_submit(self, interaction: discord.Interaction):
        raw = self.uid_input.value.strip()
        if raw.startswith("<@") and raw.endswith(">"):
            raw = raw.replace("<@", "").replace("!", "").replace(">", "").strip()
        if not raw.isdigit():
            await send_ephemeral_embed(interaction, "❌ Invalid user ID.", discord.Color.red()); return
        if raw == self.user_id:
            await send_ephemeral_embed(interaction, "❌ Can't invite yourself.", discord.Color.red()); return
        init_user(raw)
        if data[raw].get("tribe"):
            await send_ephemeral_embed(interaction, "❌ Already in a tribe.", discord.Color.red()); return
        if data[raw].get("tribe_inv"):
            await send_ephemeral_embed(interaction, "❌ Already has a pending invite.", discord.Color.red()); return
        td    = tribe_data[self.tribe_name]
        total = 1 + len(td["roles"]["officer"]) + len(td["roles"]["members"])
        if total >= td["max_members"]:
            await send_ephemeral_embed(interaction, "❌ Tribe is full.", discord.Color.red()); return
        td.setdefault("invites", []).append(raw)
        data[raw]["tribe_inv"]      = self.tribe_name
        data[raw]["tribe_inv_read"] = False
        save_data_users(); save_data_tribe()
        try:
            target_user = await bot.fetch_user(int(raw))
            await target_user.send(embed=discord.Embed(
                title=f"{TRIBE_EMOJIS['invite']} Tribe Invite",
                description=(
                    f"You've been invited to **{self.tribe_name}** by **{interaction.user.display_name}**!\n\n"
                    f"Use `/mail` to accept or decline."
                ),
                color=v2_color(self.user_id)))
        except Exception:
            pass
        await send_ephemeral_embed(interaction, f"✅ Invite sent to <@{raw}>.", discord.Color.green())


class TribeSetDescModal(discord.ui.Modal, title="Set Tribe Description"):
    desc_input = discord.ui.TextInput(label="Description", placeholder="Enter a description...",
                                       required=True, max_length=200, style=discord.TextStyle.paragraph)
    def __init__(self, user_id, tribe_name):
        super().__init__(); self.user_id = str(user_id); self.tribe_name = tribe_name
    async def on_submit(self, interaction: discord.Interaction):
        tribe_data[self.tribe_name]["description"] = self.desc_input.value
        save_data_tribe()
        sort = _tribe_sort.get(self.user_id, "rank")
        await update_v2(interaction, build_tribe_components(self.user_id, self.tribe_name, "actions", sort))


class TribeLeaveLeaderModal(discord.ui.Modal, title="Assign New Leader Before Leaving"):
    uid_input = discord.ui.TextInput(label="New Leader User ID", placeholder="123456789012345678", required=True, max_length=20)
    def __init__(self, user_id, tribe_name):
        super().__init__(); self.user_id = str(user_id); self.tribe_name = tribe_name
    async def on_submit(self, interaction: discord.Interaction):
        target  = self.uid_input.value.strip()
        td      = tribe_data[self.tribe_name]
        all_ids = td["roles"]["officer"] + td["roles"]["members"]
        if target not in all_ids:
            await send_ephemeral_embed(interaction, "❌ That user is not a tribe member.", discord.Color.red()); return
        for role in ("officer", "members"):
            if target in td["roles"][role]:        td["roles"][role].remove(target)
            if self.user_id in td["roles"][role]:  td["roles"][role].remove(self.user_id)
        td["roles"]["leader"] = target
        data[self.user_id]["tribe"] = None
        save_data_users(); save_data_tribe()
        await update_v2(interaction, build_menu_components(self.user_id, interaction.user.display_name))


class TribeCreateModal(discord.ui.Modal, title="Create a Tribe"):
    name_input = discord.ui.TextInput(label="Tribe Name", placeholder="Enter your tribe name...", required=True, max_length=32)
    desc_input = discord.ui.TextInput(label="Description", placeholder="Optional...", required=False, max_length=200, style=discord.TextStyle.paragraph)
    def __init__(self, user_id):
        super().__init__(); self.user_id = str(user_id)
    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()
        if name in tribe_data:
            await send_ephemeral_embed(interaction, "❌ Tribe name taken.", discord.Color.red()); return
        init_tribe(name, self.user_id)
        tribe_data[name]["description"] = self.desc_input.value.strip()
        save_data_tribe()
        await update_v2(interaction, build_tribe_components(self.user_id, name, "main"))

# ─────────────────────────────────────────────
# BAN APPEAL MODAL
# ─────────────────────────────────────────────
 
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
        b = get_ban(self.user_id)
        used    = b.get("appeals_used", 0)
        max_app = b.get("appeals_max", 2)
 
        if used >= max_app:
            await send_ephemeral_embed(interaction, "❌ You have no appeal chances left.", discord.Color.red())
            return
 
        # Deduct one appeal chance
        data[self.user_id]["ban"]["appeals_used"] = used + 1
        save_data_users()
 
        channel = bot.get_channel(BAN_APPEAL_CHANNEL_ID)
        exp_ts  = b.get("expires_ts", 0)
        exp_str = f"<t:{exp_ts}:R>" if exp_ts != 0 else "Permanent"
 
        if channel:
            try:
                await channel.send(embed=discord.Embed(
                    title="📋 Ban Appeal",
                    description=(
                        f"**User:** <@{self.user_id}> (`{self.user_id}`)\n"
                        f"**Reason for ban:** {b.get('reason', 'N/A')}\n"
                        f"**Ban expires:** {exp_str}\n"
                        f"**Appeals used:** {data[self.user_id]['ban']['appeals_used']}/{max_app}\n\n"
                        f"**Appeal message:**\n{self.reason_input.value}"
                    ),
                    color=discord.Color.blurple(),
                ))
            except Exception as e:
                print("Appeal channel send error:", e)
 
        await send_ephemeral_embed(
            interaction,
            "✅ Your appeal has been submitted. Admins will review it shortly.",
            discord.Color.green(),
        )

# ─────────────────────────────────────────────
# SLASH COMMANDS
# ─────────────────────────────────────────────

async def _common_init(interaction: discord.Interaction) -> str | None:
    global maintenance_mode, maintenance_warning, maintenance_message, _maintenance_warned
    
    if is_banned(user_id):
        await _raw(interaction, {
            "type": 4,
            "data": {
                "flags": V2_FLAGS | 64,
                "components": build_ban_components(user_id),
                "allowed_mentions": {"parse": []},
            }
        })
        return None

    await interaction.response.defer()
 
    if interaction.channel_id:
        maintenance_channels.add(interaction.channel_id)
        save_config()
 
    # Admin bypass — always let admins through
    if str(interaction.user.id) in BOT_ADMIN_ID:
        user_id = str(interaction.user.id)
        init_user(user_id)
        await update_user_servers(user_id, interaction.guild)
        return user_id
 
    # Full maintenance — block entirely
    if maintenance_mode:
        await interaction.followup.send(
            embed=discord.Embed(
                title="🔧 Bot Maintenance",
                description=(
                    "**Idle Hunter is currently under maintenance.**\n\n"
                    f"Reason: {maintenance_message}\n"
                    "Our team is working hard to improve your hunting experience.\n"
                    "Please be patient — we'll be back shortly!\n\n"
                    "-# All your data is safe. See you soon, hunter. 🏕️"
                ),
                color=discord.Color.orange(),
            ),
            ephemeral=True,
        )
        return None
 
    user_id = str(interaction.user.id)
    init_user(user_id)
    init_ban_record(user_id)
    await update_user_servers(user_id, interaction.guild)
    tick_verify(user_id)
    
    # ─────────────────────────────────────────
 
    if data[user_id]["verify"]["needed"]:
        await interaction.followup.send(embed=verify_needed_embed(user_id), ephemeral=True)
        return None
 
    if maintenance_warning and user_id not in _maintenance_warned:
        _maintenance_warned.add(user_id)
        try:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚠️ Maintenance Soon",
                    description=(
                        "**Idle Hunter will enter maintenance shortly.**\n\n"
                        f"Reason: {maintenance_message}\n\n"
                        "Please finish any important actions before the bot goes offline.\n"
                        "-# You will only see this message once."
                    ),
                    color=discord.Color.yellow(),
                ),
                ephemeral=True,
            )
        except Exception:
            pass
 
    return user_id


# Because we now defer in _common_init, send_v2 / update_v2 won't work for
# the *initial* panel (the interaction is already deferred, not a fresh one).
# We use interaction.followup.send with the v2 flags instead.

async def send_v2_followup(interaction: discord.Interaction, components: list):
    """Send the initial panel after a defer via raw HTTP (flags=32768)."""
    route = Route(
        "POST", "/webhooks/{application_id}/{token}",
        application_id=interaction.application_id,
        token=interaction.token,
    )
    await interaction.client.http.request(
        route,
        json={"flags": V2_FLAGS, "components": components, "allowed_mentions": {"parse": []}}
    )


@bot.tree.command(name="menu", description="Open the main hunter menu")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def menu_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    _nav_stack[user_id] = ["menu"]
    await send_v2_followup(interaction, build_menu_components(user_id, interaction.user.display_name))
    await maybe_send_mail_notification(interaction, user_id)


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
    nav_push(viewer_id, "profile")
    await send_v2_followup(interaction, build_profile_components(target_id, target.display_name, viewer_id=viewer_id))
    await maybe_send_mail_notification(interaction, viewer_id)


@bot.tree.command(name="hunt", description="Go hunting in your current biome!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def hunt_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    result = run_hunt(user_id)
    if result.get("verify"):
        await interaction.followup.send(embed=verify_needed_embed(user_id), ephemeral=True); return
    if result.get("tool_locked"):
        await interaction.followup.send(embed=discord.Embed(
            description=f"❌ **{result['biome_name']}** needs Tier {result['req_tier']}+. Use `/tools`.",
            color=discord.Color.red()), ephemeral=True); return
    if result.get("no_ammo"):
        ran_out = result.get("ran_out", False)
        atype   = result.get("ammo_type", "ammo")
        msg     = (f"💥 You ran out of {atype}! Your ammo was unequipped.\n"
                   if ran_out else
                   f"⚠️ **{result['tool_name']}** needs {atype} equipped. Buy some in /shop → Ammo!")
        await interaction.followup.send(embed=discord.Embed(description=msg, color=discord.Color.orange()), ephemeral=True); return
    if not result["ok"]:
        remaining = result.get("remaining", 3)
        await interaction.followup.send(embed=discord.Embed(
            description=f"⏳ Hunt again in **{remaining:.1f}s**.",
            color=discord.Color.orange()), ephemeral=True); return
    save_data_users()
    await maybe_tutorial_optin(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "sell")
    data[user_id]["_display_name"] = interaction.user.display_name
    nav_push(user_id, "hunt")
    await send_v2_followup(interaction, build_hunt_components(user_id, result))
    await maybe_send_mail_notification(interaction, user_id)


@bot.tree.command(name="shop", description="Buy boosts, tools and ammo")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def shop_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "shop")
    await send_v2_followup(interaction, build_shop_components(user_id, "boosts"))
    await maybe_send_mail_notification(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "shop_ammo")


@bot.tree.command(name="biome", description="Choose your hunting biome")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def biome_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "biome")
    await send_v2_followup(interaction, build_biome_panel_components(user_id))
    await maybe_send_mail_notification(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "shop_tools")


@bot.tree.command(name="color", description="Change your embed color (cosmetic only)")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def color_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "color")
    await send_v2_followup(interaction, build_color_panel_components(user_id))
    await maybe_send_mail_notification(interaction, user_id)


@bot.tree.command(name="equip", description="Equip your tools, ammo and vehicles")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def equip_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "equip")
    await send_v2_followup(interaction, build_equip_components(user_id))
    await maybe_send_mail_notification(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "equip")


@bot.tree.command(name="idle", description="Manage idle income stacks")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def idle_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "idle")
    await send_v2_followup(interaction, build_idle_components(user_id))
    await maybe_send_mail_notification(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "idle")


@bot.tree.command(name="daily", description="Claim your daily reward")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def daily_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "daily")
    await send_v2_followup(interaction, build_daily_components(user_id))
    await maybe_send_mail_notification(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "daily")


@bot.tree.command(name="prestige", description="Reset for a permanent boost multiplier")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def prestige_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "prestige")
    await send_v2_followup(interaction, build_prestige_components(user_id))
    await maybe_send_mail_notification(interaction, user_id)
    await maybe_tutorial_tip(interaction, user_id, "prestige")


@bot.tree.command(name="mail", description="Check your mailbox (tribe invites, gifts, dev mail)")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def mail_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "mail")
    await send_v2_followup(interaction, build_mail_components(user_id, "tribe"))


@bot.tree.command(name="tribe", description="View your current tribe and options")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def tribe_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    nav_push(user_id, "tribe")

    tribe_nm  = data[user_id].get("tribe")
    tribe_inv = data[user_id].get("tribe_inv")

    if not tribe_nm and tribe_inv and tribe_inv in tribe_data:
        await interaction.followup.send(embed=discord.Embed(
            description="You have a pending tribe invite! Use `/mail` to accept or decline.",
            color=discord.Color.yellow()), ephemeral=True)
        return

    if not tribe_nm or tribe_nm not in tribe_data:
        view = discord.ui.View(timeout=60)
        btn  = discord.ui.Button(label="🏕️ Create Tribe", style=discord.ButtonStyle.primary)
        async def create_cb(i: discord.Interaction):
            if str(i.user.id) != user_id:
                await send_ephemeral_embed(i, "Not yours.", discord.Color.red()); return
            await i.response.send_modal(TribeCreateModal(user_id))
        btn.callback = create_cb; view.add_item(btn)
        await interaction.followup.send(embed=discord.Embed(
            title=f"{TRIBE_EMOJIS['tribe']} No Tribe",
            description="You are not in a tribe! Create one or wait for an invite.",
            color=v2_color(user_id)), view=view, ephemeral=True)
        return

    await send_v2_followup(interaction, build_tribe_components(user_id, tribe_nm, "main"))
    await maybe_tutorial_tip(interaction, user_id, "tribe")

@bot.tree.command(name="leaderboard", description="View hunter and tribe leaderboards")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def leaderboard_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    _lb_state[user_id] = {"mode": "hunter", "scope": "global", "stat": "Level", "page": 0, "guild": interaction.guild}
    await send_v2_followup(interaction, build_leaderboard_v2_components(user_id, interaction.guild, "hunter", "global", "Level", 0))
    await maybe_send_mail_notification(interaction, user_id)


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
    await send_v2_followup(interaction, build_record_standalone_v2_components(viewer_id, target_id, 0))
    await maybe_send_mail_notification(interaction, viewer_id)


@bot.tree.command(name="log", description="View your recent hunt log")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def log_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    _log_state[user_id] = 0
    await send_v2_followup(interaction, build_log_standalone_v2_components(user_id, 0))
    await maybe_send_mail_notification(interaction, user_id)


@bot.tree.command(name="gift", description="Gift money or gems to another player")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(
    user="Who to gift",
    format="money or gems",
    amount="Amount (e.g. 1000, 2.5M, 1B)",
    sent_message="Message to include with the gift"
)
@app_commands.choices(format=[
    app_commands.Choice(name="Money (◈)", value="money"),
    app_commands.Choice(name="Gems (💎)", value="gems"),
])
async def gift_cmd(interaction: discord.Interaction, user: discord.User, format: str, amount: str, sent_message: str):
    sender_id = await _common_init(interaction)
    if not sender_id: return
    parsed = parse_amount(amount)
    if parsed is None or parsed <= 0:
        await interaction.followup.send(
            embed=discord.Embed(description="❌ Invalid amount.", color=discord.Color.red()), ephemeral=True); return
    receiver_id = str(user.id)
    if receiver_id == sender_id:
        await interaction.followup.send(
            embed=discord.Embed(description="❌ You can't gift yourself.", color=discord.Color.red()), ephemeral=True); return
    init_user(receiver_id)
    icon = "◈" if format == "money" else "💎"
    if data[sender_id][format] < parsed:
        await interaction.followup.send(
            embed=discord.Embed(description=f"❌ Not enough {icon}!", color=discord.Color.red()), ephemeral=True); return
    nav_push(sender_id, "gift")
    await send_v2_followup(interaction, build_gift_confirm_components(sender_id, user, format, parsed, sent_message))
    await maybe_send_mail_notification(interaction, sender_id)


@bot.tree.command(name="verify", description="Verify you're not an autoclicker!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(code="Your 4-character verification code")
async def verify_cmd(interaction: discord.Interaction, code: str):
    user_id = str(interaction.user.id)
    init_user(user_id)
    v = data[user_id]["verify"]
    if not v["needed"]:
        await interaction.response.send_message(embed=discord.Embed(
            description="✅ You don't need to verify right now!", color=discord.Color.green()), ephemeral=True); return
    if code.upper() == v["code"].upper():
        v["needed"] = False; v["time"] = 250; v["code"] = generate_verify_code()
        save_data_users()
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Verified!", description="Happy hunting!", color=discord.Color.green()), ephemeral=True)
    else:
        await interaction.response.send_message(embed=discord.Embed(
            title="❌ Wrong Code", description="Try again.", color=discord.Color.red()), ephemeral=True)


@bot.tree.command(name="invite", description="Invite Idle Hunter to your server!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def invite_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    init_user(user_id)
    url1 = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    url2 = "https://discord.gg/X9JzdxeS8p"
    await interaction.response.send_message(embed=discord.Embed(
        title="🔗 Invite Idle Hunter",
        description=f"[Click here to invite the bot!]({url1})\nJoin the support server: {url2}",
        color=v2_color(user_id)), ephemeral=True)


@bot.tree.command(name="id", description="Get a user's Discord ID")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(user="User to look up")
async def id_cmd(interaction: discord.Interaction, user: discord.User = None):
    viewer_id = str(interaction.user.id)
    init_user(viewer_id)
    target = user or interaction.user
    await interaction.response.send_message(embed=discord.Embed(
        title=f"{target.name}'s ID",
        description=f"`{target.id}`\n-# Use this to invite players to your tribe.",
        color=v2_color(viewer_id)), ephemeral=True)


@bot.tree.command(name="help", description="View all available commands")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def help_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    init_user(user_id)
    nav_push(user_id, "help")
    await interaction.response.defer()
    await send_v2_followup(interaction, build_help_components(user_id))
    await maybe_send_mail_notification(interaction, user_id)

@bot.tree.command(name="update", description="View the latest update from the developers.")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def update_cmd(interaction: discord.Interaction):
    user_id = await _common_init(interaction)
    if not user_id: return
    await send_v2_followup(interaction, build_update_components(user_id))
    await maybe_send_mail_notification(interaction, user_id)

@bot.tree.command(name="suggest", description="Send a suggestion to the developers.")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(suggestion="Your suggestion")
async def suggest_cmd(interaction: discord.Interaction, suggestion: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Anti-troll: minimum level gate
    if data[user_id]["level"] < 5:
        await interaction.response.send_message(
            embed=discord.Embed(
                description="❌ You must be at least **Level 5** to send suggestions.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return

    # Anti-troll: cooldown (1 suggestion per hour)
    now = time.time()
    last_suggest = data[user_id].get("last_suggest", 0)
    cooldown = 3600  # 1 hour
    if now - last_suggest < cooldown:
        remaining = int(cooldown - (now - last_suggest))
        mins = remaining // 60
        secs = remaining % 60
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"❌ You can suggest again in **{mins}m {secs}s**.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return

    # Anti-troll: minimum length
    if len(suggestion.strip()) < 20:
        await interaction.response.send_message(
            embed=discord.Embed(
                description="❌ Suggestion must be at least **20 characters**.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return

    data[user_id]["last_suggest"] = now
    save_data_users()

    # Store in config
    entry = {
        "user_id": user_id,
        "username": interaction.user.display_name,
        "suggestion": suggestion.strip(),
        "ts": int(now),
    }
    _cfg_suggestions = load_config().get("suggestions", [])
    _cfg_suggestions.insert(0, entry)

    # Save — load full config, update suggestions key, save
    cfg = load_config()
    cfg["suggestions"] = _cfg_suggestions[:200]  # cap at 200
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

    # Send to suggestion channel
    channel = bot.get_channel(SUGGESTION_CHANNEL_ID)
    if channel:
        try:
            await channel.send(
                embed=discord.Embed(
                    title="💡 New Suggestion",
                    description=(
                        f"**From:** {interaction.user.display_name} (`{user_id}`)\n"
                        f"**Level:** {data[user_id]['level']} · "
                        f"**Prestige:** {data[user_id].get('prestige', 0)} · "
                        f"**Caught:** {data[user_id].get('total_caught', 0):,}\n\n"
                        f"{suggestion.strip()}"
                    ),
                    color=discord.Color.blurple()
                )
            )
        except Exception:
            pass

    await interaction.response.send_message(
        embed=discord.Embed(
            title="💡 Suggestion Sent!",
            description="Your suggestion has been sent to the developers. Thank you!",
            color=discord.Color.green()
        ),
        ephemeral=True
    )

# ─────────────────────────────────────────────
# /tutorial COMMAND
# ─────────────────────────────────────────────
 
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
 
    data[user_id]["tutorial"]["enabled"]  = (toggle == "on")
    data[user_id]["tutorial"]["prompted"] = True   # suppress auto opt-in
    if toggle == "on":
        # reset seen steps so they get all tips fresh
        data[user_id]["tutorial"]["seen"] = []
    save_data_users()
 
    msg = ("### ✅ Tutorial tips on!\nI'll guide you through each new step as you play."
           if toggle == "on" else
           "### 🔕 Tutorial tips off.\n-# Use `/tutorial on` to turn them back on.")
 
    await interaction.response.defer()
    route = Route(
        "POST", "/webhooks/{application_id}/{token}",
        application_id=interaction.application_id,
        token=interaction.token,
    )
    await interaction.client.http.request(route, json={
        "flags": V2_FLAGS | 64,
        "components": [{"type": 17, "accent_color": _accent(user_id), "spoiler": False,
                        "components": [{"type": 10, "content": msg}]}],
        "allowed_mentions": {"parse": []},
    })
 

# ─────────────────────────────────────────────
# ADMIN COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="change_update", description="Set the latest update message.")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(message="The update message to display.")
async def change_update_cmd(interaction: discord.Interaction, message: str = ""):
    global UPDATE_MSG
    UPDATE_MSG = message.strip()
    save_config()
    await interaction.response.send_message(
        embed=discord.Embed(
            title="📋 Update Set",
            description=UPDATE_MSG if UPDATE_MSG else "Update cleared.",
            color=discord.Color.green()
        ),
        ephemeral=True
    )

@bot.tree.command(name="bot_shutdown", description="Shuts down the bot for maintenance")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(
    time="Minutes until maintenance starts",
    message="Reason for maintenance"
)
async def bot_shutdown_cmd(interaction: discord.Interaction, time: int, message: str):
    global maintenance_mode, maintenance_warning, maintenance_channels, maintenance_message

    maintenance_warning = True
    maintenance_message = message
    save_config()

    start_embed = discord.Embed(
        title=f"🔧 Maintenance Starting in {time} minutes",
        description=(
            "**Idle Hunter will enter maintenance soon.**\n\n"
            f"Reason: {message}\n"
            "Please finish your actions."
        ),
        color=discord.Color.orange()
    )

    await interaction.response.send_message(embed=start_embed)

    async def start_maintenance():
        await asyncio.sleep(time * 60)
        global maintenance_mode
        maintenance_mode = True
        save_config()

        started_embed = discord.Embed(
            title="🔧 Bot Maintenance Started",
            description=(
                "**Idle Hunter is now in maintenance mode.**\n\n"
                f"Reason: {message}\n\n"
                "All commands are disabled.\n"
                "Data is safe.\n\n"
                "-# Thanks for your patience 🏕️"
            ),
            color=discord.Color.red()
        )
        for channel_id in list(maintenance_channels):
            channel = bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=started_embed)
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
    maintenance_channels.clear()
    save_config()

    announcement = discord.Embed(
        title="✅ Bot Back Online",
        description=(
            "**Idle Hunter is back online!**\n\n"
            "All commands are now available again.\n"
            "Happy hunting! 🏹"
        ),
        color=discord.Color.green()
    )

    for channel_id in list(maintenance_channels):
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=announcement)
            except Exception:
                pass

    maintenance_channels.clear()

    try:
        await interaction.response.send_message(embed=announcement)
    except Exception:
        pass


@bot.tree.command(name="setdevmail", description="Sets the developer mail message")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(message="The developer mail message")
async def setdevmail_cmd(interaction: discord.Interaction, message: str = ""):
    global DEV_MAIL

    user_id = str(interaction.user.id)
    init_user(user_id)

    new_mail = message.strip()
    old_mail = DEV_MAIL
    changed  = new_mail != old_mail

    DEV_MAIL = new_mail
    save_config()

    if changed or not DEV_MAIL:
        for uid in data:
            data[uid]["mail_dev_content_read"] = ""
            data[uid]["mail_dev_notice_seen"]  = ""

    save_data_users()

    embed = discord.Embed(
        title="📢 Dev Mail Set",
        description=(
            f"Message set to:\n\n{DEV_MAIL}"
            if DEV_MAIL else
            "Dev mail cleared."
        ),
        color=discord.Color.green()
    )

    try:
        await interaction.user.send(embed=embed)
    except Exception:
        pass

    try:
        await interaction.response.send_message("✅ Developer mail updated.", ephemeral=True)
    except Exception:
        pass

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
        await interaction.response.send_message(
            embed=discord.Embed(description="❌ Invalid user ID.", color=discord.Color.red()),
            ephemeral=True,
        )
        return
 
    init_user(user_id)
    init_ban_record(user_id)
 
    now    = int(time.time())
    exp_ts = (now + days * 86400) if days > 0 else 0
 
    data[user_id]["ban"] = {
        "active":       True,
        "reason":       reason.strip(),
        "expires_ts":   exp_ts,
        "issued_ts":    now,
        "appeals_used": 0,
        "appeals_max":  2,
    }
    save_data_users()
 
    # Compose DM
    b_block = build_ban_components(user_id)
 
    # DM the user
    try:
        target_user = await bot.fetch_user(int(user_id))
        route = discord.http.Route(
            "POST", "/users/@me/channels",
        )
        dm_channel_data = await bot.http.request(route, json={"recipient_id": user_id})
        dm_channel_id   = dm_channel_data["id"]
 
        dm_route = discord.http.Route(
            "POST", "/channels/{channel_id}/messages",
            channel_id=dm_channel_id,
        )
        await bot.http.request(dm_route, json={
            "flags": V2_FLAGS,
            "components": b_block,
            "allowed_mentions": {"parse": []},
        })
    except Exception as e:
        print(f"Ban DM error for {user_id}:", e)
 
    duration_str = f"**{days} days**" if days > 0 else "**Permanent**"
    await interaction.response.send_message(
        embed=discord.Embed(
            title="🔨 User Banned",
            description=(
                f"<@{user_id}> (`{user_id}`) has been banned.\n"
                f"Duration: {duration_str}\n"
                f"Reason: {reason}"
            ),
            color=discord.Color.red(),
        ),
        ephemeral=True,
    )
 
 
@bot.tree.command(name="unban", description="Unban a user")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(user_id="Discord user ID to unban")
async def unban_cmd(interaction: discord.Interaction, user_id: str):
    if not user_id.isdigit() or user_id not in data:
        await interaction.response.send_message(
            embed=discord.Embed(description="❌ User not found.", color=discord.Color.red()),
            ephemeral=True,
        )
        return
 
    data[user_id]["ban"]["active"] = False
    save_data_users()
 
    await interaction.response.send_message(
        embed=discord.Embed(
            title="✅ User Unbanned",
            description=f"<@{user_id}> has been unbanned.",
            color=discord.Color.green(),
        ),
        ephemeral=True,
    )
 
 
@bot.tree.command(name="warn", description="Warn a user")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.check(is_admin)
@app_commands.describe(
    user_id="Discord user ID to warn",
    reason="Reason for the warning",
)
async def warn_cmd(interaction: discord.Interaction, user_id: str, reason: str):
    if not user_id.isdigit():
        await interaction.response.send_message(
            embed=discord.Embed(description="❌ Invalid user ID.", color=discord.Color.red()),
            ephemeral=True,
        )
        return
 
    init_user(user_id)
 
    warn_entry = {
        "reason": reason.strip(),
        "ts":     int(time.time()),
        "by":     str(interaction.user.id),
    }
    data[user_id].setdefault("warnings", []).append(warn_entry)
    save_data_users()
 
    warn_count = len(data[user_id]["warnings"])
 
    # DM the user using raw HTTP (same pattern as ban)
    body = (
        f"### ⚠️ You have been warned!\n\n"
        f"Reason: {reason.strip()}\n\n"
        f"-# This is warning **#{warn_count}**. "
        f"Next time you may receive a ban, which will restrict your access to Idle Hunter "
        f"and all its features.\n"
        f"-# Admins will never warn or ban you for no reason."
    )
    dm_components = [{"type": 17, "accent_color": 0xF39C12, "spoiler": False, "components": [
        {"type": 10, "content": body},
    ]}]
 
    try:
        route = discord.http.Route("POST", "/users/@me/channels")
        dm_channel_data = await bot.http.request(route, json={"recipient_id": user_id})
        dm_channel_id   = dm_channel_data["id"]
 
        dm_route = discord.http.Route(
            "POST", "/channels/{channel_id}/messages",
            channel_id=dm_channel_id,
        )
        await bot.http.request(dm_route, json={
            "flags": V2_FLAGS,
            "components": dm_components,
            "allowed_mentions": {"parse": []},
        })
    except Exception as e:
        print(f"Warn DM error for {user_id}:", e)
 
    await interaction.response.send_message(
        embed=discord.Embed(
            title="⚠️ User Warned",
            description=(
                f"<@{user_id}> has been warned.\n"
                f"Reason: {reason}\n"
                f"Total warnings: **{warn_count}**"
            ),
            color=discord.Color.yellow(),
        ),
        ephemeral=True,
    )

# ─────────────────────────────────────────────
# AUTOSAVE
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
    print("Autosave started.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

from dotenv import load_dotenv
import os
load_dotenv("token.env")
bot.run(os.getenv("TOKEN"))
