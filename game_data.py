"""
game_data.py — All static game content: biomes, animals, tools, ammo,
vehicles, boosts, colours, achievements, badges, tips, and command IDs.

Does NOT import from bot.py or backend.py.
Discord is imported only for Color constants.
"""

import discord, random, string, datetime
from datetime import datetime, timezone

def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

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
# AMMO
# ─────────────────────────────────────────────

def get_ammo_for_tool(tool_name: str) -> list[str]:
    atype = get_tool_ammo_type(tool_name)
    if not atype:
        return []
    return [name for name, a in AMMO.items() if a["ammo_type"] == atype]

def ammo_compatible_with_tool(ammo_name: str, tool_name: str) -> bool:
    a_type = AMMO.get(ammo_name, {}).get("ammo_type")
    t_type = TOOLS.get(tool_name, {}).get("ammo_type")
    return a_type is not None and a_type == t_type



# ─────────────────────────────────────────────
# XP CURVE  (canonical formulas — mirrors curves.py)
# ─────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    """XP required to advance FROM ``level`` to ``level + 1``."""
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


# ─────────────────────────────────────────────
# BIOMES
# ─────────────────────────────────────────────

BIOME_LEVELS = [
    ("village",             1),
    ("forest",             10),
    ("woods",              25),
    ("small_desert",       50),
    ("large_desert",      100),
    ("tundra",            150),
    ("jungle",            200),
    ("swamp",             275),
    ("volcanic_highlands",350),
    ("cursed_ruins",      450),
    ("rainbow",           600),
    ("abyssal_depths",    800),
    ("celestial_peaks",  1000),
]

BIOME_EMOJIS = {
    "village":             "<:Village:1499198420387369090>",
    "forest":              "<:Forest:1499200283593674975>",
    "woods":               "<:Woods:1499201326142455938>",
    "small_desert":        "<:Small_Desert:1499201560473763850>",
    "large_desert":        "<:Large_Desert:1499204067929620543>",
    "tundra":              "<:Tundra:1499230188389797888>",
    "jungle":              "<:Jungle:1499230354362470490>",
    "swamp":               "<:Swamp:1499230538056335460>",
    "volcanic_highlands":  "<:Volcanic_Highlands:1499230604825202871>",
    "cursed_ruins":        "<:Cursed_Ruins:1499230731376005223>",
    "rainbow":             "<:Rainbow:1499943967620599979>",
    "abyssal_depths":      "<:Abyssal_Depths:1499230862250610748>",
    "celestial_peaks":     "<:Celestial_Peaks:1499230958295973929>",
}

BIOME_NAMES = {
    "village":             "Village",
    "forest":              "Forest",
    "woods":               "Woods",
    "small_desert":        "Small Desert",
    "large_desert":        "Large Desert",
    "tundra":              "Tundra",
    "jungle":              "Jungle",
    "swamp":               "Swamp",
    "volcanic_highlands":  "Volcanic Highlands",
    "cursed_ruins":        "Cursed Ruins",
    "rainbow":             "Rainbow Realm",
    "abyssal_depths":      "Abyssal Depths",
    "celestial_peaks":     "Celestial Peaks",
}

BIOME_ANIMALS = {
    "village": [
        "Rat", "Mouse", "Stray Cat", "Pigeon", "Crow", "Rabbit", "Fox",
        "Stray Dog", "Squirrel", "Sparrow",
    ],
    "forest": [
        "Deer", "Wild Boar", "Wolf", "Bear", "Elk", "Lynx", "Badger",
        "Pheasant", "Owl", "Hare",
    ],
    "woods": [
        "Moose", "Timber Wolf", "Black Bear", "Wild Turkey", "Coyote",
        "Raccoon", "Porcupine", "Snapping Turtle", "Grouse", "Mink",
    ],
    "small_desert": [
        "Scorpion", "Sand Viper", "Vulture", "Fennec Fox", "Armadillo",
        "Roadrunner", "Lizard", "Camel Spider", "Jerboa", "Coyote",
    ],
    "large_desert": [
        "Sandstorm Serpent", "Desert Lion", "Giant Scorpion", "Dust Hyena",
        "Sand Golem Crab", "Camel", "Dune Stalker Wolf", "Golden Eagle",
        "Desert Lynx", "Mirage Phantom",
    ],
    "tundra": [
        "Arctic Wolf", "Polar Bear", "Snowy Owl", "Reindeer", "Arctic Fox",
        "Musk Ox", "Wolverine", "Seal", "Walrus", "Snow Leopard",
    ],
    "jungle": [
        "Jaguar", "Anaconda", "Poison Dart Frog", "Toucan", "Panther",
        "Wild Boar", "Silverback Gorilla", "Komodo Dragon", "Piranha",
        "Giant Centipede",
    ],
    "swamp": [
        "Alligator", "Snapping Turtle", "Giant Frog", "Swamp Viper",
        "Mudskipper", "Black Panther", "Leech Hydra", "Bog Bear",
        "Marsh Hawk", "Will-o-Wisp Serpent",
    ],
    "volcanic_highlands": [
        "Lava Lizard", "Magma Boar", "Ember Wolf", "Ash Vulture",
        "Cinder Crab", "Obsidian Serpent", "Flame Lynx", "Molten Golem",
        "Fire Hawk", "Inferno Bear",
    ],
    "cursed_ruins": [
        "Skeleton Archer", "Shadow Wolf", "Bone Drake", "Cursed Knight",
        "Wraith Stag", "Plague Rat", "Stone Golem", "Phantom Lynx",
        "Soul Serpent", "Ancient Guardian",
    ],
    "rainbow": [
        "Prismatic Butterfly", "Chromatic Fox", "Rainbow Serpent",
        "Aurora Deer", "Spectrum Wolf", "Iridescent Hawk", "Prism Panther",
        "Hue Shifter Frog", "Kaleidoscope Crab", "The Living Rainbow",
    ],
    "abyssal_depths": [
        "Deep Sea Kraken", "Abyss Shark", "Shadow Eel", "Void Manta",
        "Leviathan Crab", "Bioluminescent Jellyfish", "Depth Stalker",
        "Abyssal Serpent", "Trench Golem", "Darkness Whale",
    ],
    "celestial_peaks": [
        "Storm Eagle", "Cloud Serpent", "Thunder Elk", "Sky Leviathan",
        "Divine Wolf", "Astral Panther", "Heavenly Dragon", "Celestial Bear",
        "Void Phoenix", "The Eternal Hunter",
    ],
}


# ─────────────────────────────────────────────
# ANIMALS
# ─────────────────────────────────────────────

ANIMAL_DATA = {
    # Village
    "Rat":              {"value":     30, "xp": 9,   "rarity": "common",    "emoji": ""},
    "Mouse":            {"value":     25, "xp": 7,   "rarity": "common",    "emoji": ""},
    "Stray Cat":        {"value":     60, "xp": 18,  "rarity": "uncommon",  "emoji": ""},
    "Pigeon":           {"value":     20, "xp": 6,   "rarity": "common",    "emoji": ""},
    "Crow":             {"value":     35, "xp": 10,  "rarity": "common",    "emoji": ""},
    "Rabbit":           {"value":     80, "xp": 24,  "rarity": "uncommon",  "emoji": ""},
    "Fox":              {"value":    120, "xp": 36,  "rarity": "rare",      "emoji": ""},
    "Stray Dog":        {"value":     55, "xp": 16,  "rarity": "common",    "emoji": ""},
    "Squirrel":         {"value":     40, "xp": 12,  "rarity": "common",    "emoji": ""},
    "Sparrow":          {"value":     18, "xp": 5,   "rarity": "common",    "emoji": ""},
    # Forest
    "Deer":             {"value":    150, "xp": 45,  "rarity": "common",    "emoji": ""},
    "Wild Boar":        {"value":    180, "xp": 54,  "rarity": "common",    "emoji": ""},
    "Wolf":             {"value":    300, "xp": 90,  "rarity": "uncommon",  "emoji": ""},
    "Bear":             {"value":    400, "xp": 120, "rarity": "rare",      "emoji": ""},
    "Elk":              {"value":    200, "xp": 60,  "rarity": "common",    "emoji": ""},
    "Lynx":             {"value":    350, "xp": 105, "rarity": "rare",      "emoji": ""},
    "Badger":           {"value":    130, "xp": 39,  "rarity": "common",    "emoji": ""},
    "Pheasant":         {"value":    110, "xp": 33,  "rarity": "common",    "emoji": ""},
    "Owl":              {"value":    220, "xp": 66,  "rarity": "uncommon",  "emoji": ""},
    "Hare":             {"value":     90, "xp": 27,  "rarity": "common",    "emoji": ""},
    # Woods
    "Moose":            {"value":    500, "xp": 150, "rarity": "uncommon",  "emoji": ""},
    "Timber Wolf":      {"value":    450, "xp": 135, "rarity": "uncommon",  "emoji": ""},
    "Black Bear":       {"value":    600, "xp": 180, "rarity": "rare",      "emoji": ""},
    "Wild Turkey":      {"value":    250, "xp": 75,  "rarity": "common",    "emoji": ""},
    "Coyote":           {"value":    300, "xp": 90,  "rarity": "common",    "emoji": ""},
    "Raccoon":          {"value":    200, "xp": 60,  "rarity": "common",    "emoji": ""},
    "Porcupine":        {"value":    220, "xp": 66,  "rarity": "common",    "emoji": ""},
    "Snapping Turtle":  {"value":    350, "xp": 105, "rarity": "uncommon",  "emoji": ""},
    "Grouse":           {"value":    210, "xp": 63,  "rarity": "common",    "emoji": ""},
    "Mink":             {"value":    400, "xp": 120, "rarity": "uncommon",  "emoji": ""},
    # Small Desert
    "Scorpion":         {"value":    500, "xp": 150, "rarity": "common",    "emoji": ""},
    "Sand Viper":       {"value":    700, "xp": 210, "rarity": "uncommon",  "emoji": ""},
    "Vulture":          {"value":    600, "xp": 180, "rarity": "common",    "emoji": ""},
    "Fennec Fox":       {"value":    800, "xp": 240, "rarity": "uncommon",  "emoji": ""},
    "Armadillo":        {"value":    550, "xp": 165, "rarity": "common",    "emoji": ""},
    "Roadrunner":       {"value":    450, "xp": 135, "rarity": "common",    "emoji": ""},
    "Lizard":           {"value":    400, "xp": 120, "rarity": "common",    "emoji": ""},
    "Camel Spider":     {"value":    750, "xp": 225, "rarity": "uncommon",  "emoji": ""},
    "Jerboa":           {"value":    500, "xp": 150, "rarity": "common",    "emoji": ""},
    # Large Desert
    "Sandstorm Serpent":{"value":  1_200, "xp": 360, "rarity": "rare",      "emoji": ""},
    "Desert Lion":      {"value":  1_500, "xp": 450, "rarity": "rare",      "emoji": ""},
    "Giant Scorpion":   {"value":  1_000, "xp": 300, "rarity": "uncommon",  "emoji": ""},
    "Dust Hyena":       {"value":    900, "xp": 270, "rarity": "uncommon",  "emoji": ""},
    "Sand Golem Crab":  {"value":  1_100, "xp": 330, "rarity": "rare",      "emoji": ""},
    "Camel":            {"value":    700, "xp": 210, "rarity": "common",    "emoji": ""},
    "Dune Stalker Wolf":{"value":  1_300, "xp": 390, "rarity": "rare",      "emoji": ""},
    "Golden Eagle":     {"value":  1_000, "xp": 300, "rarity": "uncommon",  "emoji": ""},
    "Desert Lynx":      {"value":  1_100, "xp": 330, "rarity": "rare",      "emoji": ""},
    "Mirage Phantom":   {"value":  2_000, "xp": 600, "rarity": "epic",      "emoji": ""},
    # Tundra
    "Arctic Wolf":      {"value":  1_500, "xp": 450, "rarity": "uncommon",  "emoji": ""},
    "Polar Bear":       {"value":  2_000, "xp": 600, "rarity": "rare",      "emoji": ""},
    "Snowy Owl":        {"value":  1_200, "xp": 360, "rarity": "uncommon",  "emoji": ""},
    "Reindeer":         {"value":  1_000, "xp": 300, "rarity": "common",    "emoji": ""},
    "Arctic Fox":       {"value":  1_300, "xp": 390, "rarity": "uncommon",  "emoji": ""},
    "Musk Ox":          {"value":    900, "xp": 270, "rarity": "common",    "emoji": ""},
    "Wolverine":        {"value":  1_600, "xp": 480, "rarity": "rare",      "emoji": ""},
    "Seal":             {"value":    800, "xp": 240, "rarity": "common",    "emoji": ""},
    "Walrus":           {"value":  1_100, "xp": 330, "rarity": "uncommon",  "emoji": ""},
    "Snow Leopard":     {"value":  2_500, "xp": 750, "rarity": "epic",      "emoji": ""},
    # Jungle
    "Jaguar":           {"value":  2_500, "xp": 750, "rarity": "rare",      "emoji": ""},
    "Anaconda":         {"value":  2_000, "xp": 600, "rarity": "rare",      "emoji": ""},
    "Poison Dart Frog": {"value":  1_500, "xp": 450, "rarity": "uncommon",  "emoji": ""},
    "Toucan":           {"value":  1_200, "xp": 360, "rarity": "common",    "emoji": ""},
    "Panther":          {"value":  3_000, "xp": 900, "rarity": "epic",      "emoji": ""},
    "Silverback Gorilla":{"value": 3_500, "xp": 1050, "rarity": "epic",     "emoji": ""},
    "Komodo Dragon":    {"value":  2_800, "xp": 840, "rarity": "rare",      "emoji": ""},
    "Piranha":          {"value":  1_800, "xp": 540, "rarity": "uncommon",  "emoji": ""},
    "Giant Centipede":  {"value":  2_200, "xp": 660, "rarity": "rare",      "emoji": ""},
    # Swamp
    "Alligator":        {"value":  3_000, "xp": 900, "rarity": "rare",      "emoji": ""},
    "Giant Frog":       {"value":  2_000, "xp": 600, "rarity": "uncommon",  "emoji": ""},
    "Swamp Viper":      {"value":  2_500, "xp": 750, "rarity": "rare",      "emoji": ""},
    "Mudskipper":       {"value":  1_500, "xp": 450, "rarity": "common",    "emoji": ""},
    "Black Panther":    {"value":  4_000, "xp": 1200, "rarity": "epic",     "emoji": ""},
    "Leech Hydra":      {"value":  5_000, "xp": 1500, "rarity": "epic",     "emoji": ""},
    "Bog Bear":         {"value":  3_500, "xp": 1050, "rarity": "rare",     "emoji": ""},
    "Marsh Hawk":       {"value":  2_200, "xp": 660, "rarity": "uncommon",  "emoji": ""},
    "Will-o-Wisp Serpent":{"value":6_000, "xp": 1800, "rarity": "legendary","emoji": ""},
    # Volcanic Highlands
    "Lava Lizard":      {"value":  4_000, "xp": 1200, "rarity": "uncommon", "emoji": ""},
    "Magma Boar":       {"value":  4_500, "xp": 1350, "rarity": "rare",     "emoji": ""},
    "Ember Wolf":       {"value":  5_000, "xp": 1500, "rarity": "rare",     "emoji": ""},
    "Ash Vulture":      {"value":  3_500, "xp": 1050, "rarity": "uncommon", "emoji": ""},
    "Cinder Crab":      {"value":  4_000, "xp": 1200, "rarity": "uncommon", "emoji": ""},
    "Obsidian Serpent": {"value":  6_000, "xp": 1800, "rarity": "epic",     "emoji": ""},
    "Flame Lynx":       {"value":  5_500, "xp": 1650, "rarity": "epic",     "emoji": ""},
    "Molten Golem":     {"value":  8_000, "xp": 2400, "rarity": "legendary","emoji": ""},
    "Fire Hawk":        {"value":  5_000, "xp": 1500, "rarity": "rare",     "emoji": ""},
    "Inferno Bear":     {"value":  7_000, "xp": 2100, "rarity": "epic",     "emoji": ""},
    # Cursed Ruins
    "Skeleton Archer":  {"value":  6_000, "xp": 1800, "rarity": "uncommon", "emoji": ""},
    "Shadow Wolf":      {"value":  7_000, "xp": 2100, "rarity": "rare",     "emoji": ""},
    "Bone Drake":       {"value": 10_000, "xp": 3000, "rarity": "epic",     "emoji": ""},
    "Cursed Knight":    {"value":  8_000, "xp": 2400, "rarity": "rare",     "emoji": ""},
    "Wraith Stag":      {"value":  9_000, "xp": 2700, "rarity": "epic",     "emoji": ""},
    "Plague Rat":       {"value":  5_000, "xp": 1500, "rarity": "uncommon", "emoji": ""},
    "Stone Golem":      {"value":  8_500, "xp": 2550, "rarity": "rare",     "emoji": ""},
    "Phantom Lynx":     {"value": 11_000, "xp": 3300, "rarity": "epic",     "emoji": ""},
    "Soul Serpent":     {"value": 12_000, "xp": 3600, "rarity": "legendary","emoji": ""},
    "Ancient Guardian": {"value": 15_000, "xp": 4500, "rarity": "legendary","emoji": ""},
    # Rainbow
    "Prismatic Butterfly":{"value":12_000, "xp": 3600, "rarity": "rare",    "emoji": ""},
    "Chromatic Fox":    {"value": 15_000, "xp": 4500, "rarity": "rare",     "emoji": ""},
    "Rainbow Serpent":  {"value": 18_000, "xp": 5400, "rarity": "epic",     "emoji": ""},
    "Aurora Deer":      {"value": 14_000, "xp": 4200, "rarity": "rare",     "emoji": ""},
    "Spectrum Wolf":    {"value": 20_000, "xp": 6000, "rarity": "epic",     "emoji": ""},
    "Iridescent Hawk":  {"value": 13_000, "xp": 3900, "rarity": "rare",     "emoji": ""},
    "Prism Panther":    {"value": 22_000, "xp": 6600, "rarity": "epic",     "emoji": ""},
    "Hue Shifter Frog": {"value": 16_000, "xp": 4800, "rarity": "rare",     "emoji": ""},
    "Kaleidoscope Crab":{"value": 25_000, "xp": 7500, "rarity": "legendary","emoji": ""},
    "The Living Rainbow":{"value":50_000, "xp": 15000, "rarity": "mythic",  "emoji": ""},
    # Abyssal Depths
    "Deep Sea Kraken":  {"value": 25_000, "xp": 7500, "rarity": "epic",     "emoji": ""},
    "Abyss Shark":      {"value": 20_000, "xp": 6000, "rarity": "rare",     "emoji": ""},
    "Shadow Eel":       {"value": 18_000, "xp": 5400, "rarity": "rare",     "emoji": ""},
    "Void Manta":       {"value": 22_000, "xp": 6600, "rarity": "epic",     "emoji": ""},
    "Leviathan Crab":   {"value": 28_000, "xp": 8400, "rarity": "epic",     "emoji": ""},
    "Bioluminescent Jellyfish":{"value":15_000,"xp":4500,"rarity":"rare",   "emoji": ""},
    "Depth Stalker":    {"value": 24_000, "xp": 7200, "rarity": "epic",     "emoji": ""},
    "Abyssal Serpent":  {"value": 30_000, "xp": 9000, "rarity": "legendary","emoji": ""},
    "Trench Golem":     {"value": 35_000, "xp": 10500, "rarity": "legendary","emoji": ""},
    "Darkness Whale":   {"value": 50_000, "xp": 15000, "rarity": "mythic",  "emoji": ""},
    # Celestial Peaks
    "Storm Eagle":      {"value": 40_000, "xp": 12000, "rarity": "epic",    "emoji": ""},
    "Cloud Serpent":    {"value": 45_000, "xp": 13500, "rarity": "epic",    "emoji": ""},
    "Thunder Elk":      {"value": 35_000, "xp": 10500, "rarity": "rare",    "emoji": ""},
    "Sky Leviathan":    {"value": 60_000, "xp": 18000, "rarity": "legendary","emoji": ""},
    "Divine Wolf":      {"value": 55_000, "xp": 16500, "rarity": "legendary","emoji": ""},
    "Astral Panther":   {"value": 65_000, "xp": 19500, "rarity": "legendary","emoji": ""},
    "Heavenly Dragon":  {"value": 80_000, "xp": 24000, "rarity": "mythic",  "emoji": ""},
    "Celestial Bear":   {"value": 50_000, "xp": 15000, "rarity": "legendary","emoji": ""},
    "Void Phoenix":     {"value": 90_000, "xp": 27000, "rarity": "mythic",  "emoji": ""},
    "The Eternal Hunter":{"value":150_000,"xp": 45000, "rarity": "mythic",  "emoji": ""},
}

ANIMAL_EMOJI = ""


# ─────────────────────────────────────────────
# EMOJIS / ICONS
# ─────────────────────────────────────────────

UPGRADE_EMOJI = "<:Bot_Upgrade:1500237654891958394>"

RARITY_ICONS = {
    "common":    "<:Common_Rarity:1499983185105387590>",
    "uncommon":  "<:Uncommon_Rarity:1499983588236460032>",
    "rare":      "<:Rare_Rarity:1499983646973497344>",
    "epic":      "<:Epic_Rarity:1499983688304431266>",
    "legendary": "<:Legendary_Rarity:1499983727936147547>",
    "mythic":    "<:Mythic_Rarity:1499983777923993732>",
}

TRIBE_EMOJIS = {
    "members":    "<:Tribe_Members:1500224532022296586>",
    "kick":       "<:Tribe_Kick:1500224528985620663>",
    "invite":     "<:Tribe_Invite:1500224530348638329>",
    "ban":        "<:Tribe_Ban:1500224527756558497>",
    "leave":      "<:Tribe_Leave:1500224526699597864>",
    "leader":     "<:Tribe_Leader:1500237652740538388>",
    "officer":    "<:Tribe_Officer:1500240066801569994>",
    "tribe":      "<:Bot_Tribe:1500237653591851080>",
    "demote":     "<:Tribe_Demote:1500237650366304378>",
    "set_desc":   "<:Tribe_Set_Desc:1500237649112338592>",
    "xp":         "<:Bot_XP:1500237661422485514>",
    "levels":     "<:Bot_Levels:1500237660181233735>",
    "sell_boost": "<:Sell_Boost:1500237659275001856>",
    "xp_boost":   "<:XP_Boost:1500237658037944400>",
    "luck_boost": "<:Luck_Boost:1500237656292855839>",
    "stats":      "<:Bot_Stats:1500242977501483228>",
    "luck":       "<:Bot_Luck:1500239746570522685>",
}

USER_EMOJIS = {
    "profile":    "<:User_Profile:1500237646121930863>",
    "stats":      "<:Bot_Stats:1500242977501483228>",
    "xp":         "<:Bot_XP:1500237661422485514>",
    "levels":     "<:Bot_Levels:1500237660181233735>",
    "sell_boost": "<:Sell_Boost:1500237659275001856>",
    "xp_boost":   "<:XP_Boost:1500237658037944400>",
    "luck_boost": "<:Luck_Boost:1500237656292855839>",
    "luck":       "<:Bot_Luck:1500239746570522685>",
    "biome":      "<:Bot_Biome:1500237641998799050>",
    "cooldown":   "<:Bot_Cooldown:1500237640962670764>",
    "level_up":   "<:XP_Level_Up:1500239747744792606>",
}


# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

TOOLS = {
    "Bare Hands": {
        "description": "No tool. Everyone starts here.",
        "tier": 1, "price": 0, "currency": "money",
        "boost_luck": 0, "boost_xp": 0,
        "emoji": "🤲",
        "multi_catch": 1,
        "ammo_type": None,
    },
    "Slingshot": {
        "description": "A crude sling for small game.",
        "tier": 2, "price": 500, "currency": "money",
        "boost_luck": 1, "boost_xp": 1,
        "emoji": "🪃",
        "multi_catch": 1,
        "ammo_type": None,
    },
    "Hunting Knife": {
        "description": "A sharp blade for close encounters.",
        "tier": 3, "price": 2_000, "currency": "money",
        "boost_luck": 2, "boost_xp": 2,
        "emoji": "🔪",
        "multi_catch": 1,
        "ammo_type": None,
    },
    "Spear": {
        "description": "A wooden spear with a bone tip.",
        "tier": 4, "price": 8_000, "currency": "money",
        "boost_luck": 3, "boost_xp": 3,
        "emoji": "🗡️",
        "multi_catch": 1,
        "ammo_type": None,
    },
    "Shortbow": {
        "description": "A basic bow for forest hunting.",
        "tier": 5, "price": 25_000, "currency": "money",
        "boost_luck": 4, "boost_xp": 5,
        "emoji": "🏹",
        "multi_catch": 2,
        "ammo_type": "arrow",
    },
    "Longbow": {
        "description": "Greater range and precision.",
        "tier": 6, "price": 80_000, "currency": "money",
        "boost_luck": 5, "boost_xp": 6,
        "emoji": "🏹",
        "multi_catch": 2,
        "ammo_type": "arrow",
    },
    "Crossbow": {
        "description": "Mechanical precision for tough prey.",
        "tier": 7, "price": 250_000, "currency": "money",
        "boost_luck": 6, "boost_xp": 8,
        "emoji": "🎯",
        "multi_catch": 2,
        "ammo_type": "bolt",
    },
    "Musket": {
        "description": "A flintlock for serious hunters.",
        "tier": 8, "price": 750_000, "currency": "money",
        "boost_luck": 7, "boost_xp": 10,
        "emoji": "🔫",
        "multi_catch": 2,
        "ammo_type": "bullet",
    },
    "Hunting Rifle": {
        "description": "A bolt-action rifle for big game.",
        "tier": 9, "price": 2_000_000, "currency": "money",
        "boost_luck": 9, "boost_xp": 12,
        "emoji": "🔫",
        "multi_catch": 3,
        "ammo_type": "bullet",
    },
    "Shotgun": {
        "description": "Devastating at close range.",
        "tier": 10, "price": 5_000_000, "currency": "money",
        "boost_luck": 10, "boost_xp": 14,
        "emoji": "🔫",
        "multi_catch": 3,
        "ammo_type": "bullet",
    },
    "Sniper Rifle": {
        "description": "Long-range precision firearm.",
        "tier": 11, "price": 10_000_000, "currency": "money",
        "boost_luck": 12, "boost_xp": 16,
        "emoji": "🎯",
        "multi_catch": 3,
        "ammo_type": "bullet",
    },
    "Tranq Gun": {
        "description": "Sedates prey, raising rare catch chance.",
        "tier": 12, "price": 25_000_000, "currency": "money",
        "boost_luck": 15, "boost_xp": 18,
        "emoji": "💉",
        "multi_catch": 3,
        "ammo_type": "tranq_dart",
    },
    "Plasma Caster": {
        "description": "Energy weapon from a distant future.",
        "tier": 13, "price": 50_000_000, "currency": "money",
        "boost_luck": 18, "boost_xp": 22,
        "emoji": "⚡",
        "multi_catch": 4,
        "ammo_type": "energy_cell",
    },
    "Gravity Trap": {
        "description": "A field device that bends space to capture prey.",
        "tier": 14, "price": 100_000_000, "currency": "money",
        "boost_luck": 22, "boost_xp": 26,
        "emoji": "🌀",
        "multi_catch": 4,
        "ammo_type": "energy_cell",
    },
    "Soul Snare": {
        "description": "Ethereal chains that bind cursed beasts.",
        "tier": 15, "price": 250, "currency": "gems",
        "boost_luck": 26, "boost_xp": 30,
        "emoji": "🕸️",
        "multi_catch": 4,
        "ammo_type": "soul_shard",
    },
    "Void Bow": {
        "description": "An abyssal bow that fires arrows of darkness.",
        "tier": 16, "price": 350, "currency": "gems",
        "boost_luck": 30, "boost_xp": 35,
        "emoji": "🌑",
        "multi_catch": 4,
        "ammo_type": "soul_shard",
    },
    "Celestial Lance": {
        "description": "Forged from starlight and ancient prayers.",
        "tier": 17, "price": 500, "currency": "gems",
        "boost_luck": 35, "boost_xp": 40,
        "emoji": "✨",
        "multi_catch": 5,
        "ammo_type": "cosmic_round",
    },
    "Mythic Net": {
        "description": "A legendary net woven from mythic threads.",
        "tier": 18, "price": 700, "currency": "gems",
        "boost_luck": 40, "boost_xp": 46,
        "emoji": "🕸️",
        "multi_catch": 5,
        "ammo_type": "cosmic_round",
    },
    "Dragon Cannon": {
        "description": "A cannon powered by dragonfire.",
        "tier": 19, "price": 1_000, "currency": "gems",
        "boost_luck": 46, "boost_xp": 52,
        "emoji": "🐉",
        "multi_catch": 5,
        "ammo_type": "cosmic_round",
    },
    "Cosmic RPG": {
        "description": "The ultimate weapon — fires concentrated star energy.",
        "tier": 20, "price": 1_500, "currency": "gems",
        "boost_luck": 55, "boost_xp": 60,
        "emoji": "🚀",
        "multi_catch": 6,
        "ammo_type": "cosmic_round",
    },
    "Nuke Launcher": {
        "description": "LAUNCHES NUKES — BADA-BOOM!",
        "tier": 100, "price": 10_000, "currency": "gems",
        "boost_luck": 1_000, "boost_xp": 1_000,
        "emoji": "💥",
        "multi_catch": 10,
        "ammo_type": "nuke_only",
    },
}

BIOME_TOOL_TIER = {
    "village":             1,
    "forest":              2,
    "woods":               3,
    "small_desert":        4,
    "large_desert":        5,
    "tundra":              6,
    "jungle":              7,
    "swamp":               8,
    "volcanic_highlands": 10,
    "cursed_ruins":       13,
    "rainbow":            15,
    "abyssal_depths":     17,
    "celestial_peaks":    19,
}


# ─────────────────────────────────────────────
# AMMO
# ─────────────────────────────────────────────

AMMO = {
    # ── ARROWS (Shortbow, Longbow) ──────────────────────────────
    "Wooden Arrow": {
        "ammo_type": "arrow",
        "description": "Basic fletched arrow. Steady but unremarkable.",
        "emoji": "🪵",
        "price": 8, "currency": "money",
        "boost_luck": 5, "boost_sell": 0, "boost_xp": 8,
    },
    "Iron Arrow": {
        "ammo_type": "arrow",
        "description": "Reinforced iron tip for better accuracy.",
        "emoji": "⚙️",
        "price": 25, "currency": "money",
        "boost_luck": 12, "boost_sell": 0, "boost_xp": 18,
    },
    "Enchanted Arrow": {
        "ammo_type": "arrow",
        "description": "Magically guided — rarely misses its mark.",
        "emoji": "✨",
        "price": 15, "currency": "gems",
        "boost_luck": 30, "boost_sell": 0, "boost_xp": 40,
    },
    "Phantom Arrow": {
        "ammo_type": "arrow",
        "description": "Passes through walls and seeks rare prey.",
        "emoji": "👻",
        "price": 35, "currency": "gems",
        "boost_luck": 50, "boost_sell": 0, "boost_xp": 50,
    },
    # ── BOLTS (Crossbow) ────────────────────────────────────────
    "Crude Bolt": {
        "ammo_type": "bolt",
        "description": "Hastily carved bolt. Functional at best.",
        "emoji": "📌",
        "price": 10, "currency": "money",
        "boost_luck": 5, "boost_sell": 8, "boost_xp": 0,
    },
    "Steel Bolt": {
        "ammo_type": "bolt",
        "description": "Hardened steel tip for piercing tough hides.",
        "emoji": "🔩",
        "price": 30, "currency": "money",
        "boost_luck": 15, "boost_sell": 20, "boost_xp": 0,
    },
    "Gilded Bolt": {
        "ammo_type": "bolt",
        "description": "Gold-tipped bolt — prey fetches a higher price.",
        "emoji": "💛",
        "price": 18, "currency": "gems",
        "boost_luck": 32, "boost_sell": 40, "boost_xp": 0,
    },
    "Venom Bolt": {
        "ammo_type": "bolt",
        "description": "Coated in rare venom that preserves pelt quality.",
        "emoji": "🐍",
        "price": 40, "currency": "gems",
        "boost_luck": 50, "boost_sell": 50, "boost_xp": 0,
    },
    # ── BULLETS (Musket, Hunting Rifle, Shotgun, Sniper Rifle) ──
    "Lead Ball": {
        "ammo_type": "bullet",
        "description": "Old-fashioned lead round. Gets the job done.",
        "emoji": "⚫",
        "price": 12, "currency": "money",
        "boost_luck": 0, "boost_sell": 8, "boost_xp": 5,
    },
    "Hollow Point": {
        "ammo_type": "bullet",
        "description": "Expands on impact — maximises sell yield.",
        "emoji": "🔘",
        "price": 35, "currency": "money",
        "boost_luck": 0, "boost_sell": 22, "boost_xp": 12,
    },
    "Silver Bullet": {
        "ammo_type": "bullet",
        "description": "Mythically potent — effective against rare prey.",
        "emoji": "🌕",
        "price": 20, "currency": "gems",
        "boost_luck": 10, "boost_sell": 38, "boost_xp": 30,
    },
    "Void Round": {
        "ammo_type": "bullet",
        "description": "Infused with dark matter — hunters fear nothing.",
        "emoji": "🌑",
        "price": 45, "currency": "gems",
        "boost_luck": 20, "boost_sell": 50, "boost_xp": 45,
    },
    # ── TRANQ DARTS (Tranq Gun) ─────────────────────────────────
    "Basic Tranq": {
        "ammo_type": "tranq_dart",
        "description": "Standard sedative — increases rare catch chance.",
        "emoji": "💊",
        "price": 18, "currency": "money",
        "boost_luck": 20, "boost_sell": 0, "boost_xp": 0,
    },
    "Potent Tranq": {
        "ammo_type": "tranq_dart",
        "description": "Heavy sedative — prey stays calm and valuable.",
        "emoji": "🧪",
        "price": 45, "currency": "money",
        "boost_luck": 30, "boost_sell": 0, "boost_xp": 0,
    },
    "Exotic Serum": {
        "ammo_type": "tranq_dart",
        "description": "Rare compound that draws out legendary creatures.",
        "emoji": "🔬",
        "price": 25, "currency": "gems",
        "boost_luck": 40, "boost_sell": 0, "boost_xp": 0,
    },
    "Void Serum": {
        "ammo_type": "tranq_dart",
        "description": "Cosmic formula — almost guarantees rare catches.",
        "emoji": "🌌",
        "price": 50, "currency": "gems",
        "boost_luck": 50, "boost_sell": 0, "boost_xp": 0,
    },
    # ── ENERGY CELLS (Plasma Caster, Gravity Trap) ──────────────
    "Charged Cell": {
        "ammo_type": "energy_cell",
        "description": "Standard power cell. Efficient energy output.",
        "emoji": "🔋",
        "price": 20, "currency": "money",
        "boost_luck": 0, "boost_sell": 10, "boost_xp": 15,
    },
    "Overcharged Cell": {
        "ammo_type": "energy_cell",
        "description": "Overloaded cell — boosts scan range and XP gain.",
        "emoji": "⚡",
        "price": 50, "currency": "money",
        "boost_luck": 0, "boost_sell": 22, "boost_xp": 28,
    },
    "Plasma Core": {
        "ammo_type": "energy_cell",
        "description": "Condensed plasma — dramatically amplifies output.",
        "emoji": "🌟",
        "price": 28, "currency": "gems",
        "boost_luck": 5, "boost_sell": 35, "boost_xp": 40,
    },
    "Singularity Cell": {
        "ammo_type": "energy_cell",
        "description": "A micro black hole — warps reality around prey.",
        "emoji": "🕳️",
        "price": 55, "currency": "gems",
        "boost_luck": 10, "boost_sell": 50, "boost_xp": 50,
    },
    # ── SOUL SHARDS (Soul Snare, Void Bow) ──────────────────────
    "Fractured Shard": {
        "ammo_type": "soul_shard",
        "description": "A cracked soul fragment — modest all-round boost.",
        "emoji": "💎",
        "price": 22, "currency": "money",
        "boost_luck": 8, "boost_sell": 8, "boost_xp": 8,
    },
    "Pure Shard": {
        "ammo_type": "soul_shard",
        "description": "A cleansed shard — balanced enhancement.",
        "emoji": "🔷",
        "price": 55, "currency": "money",
        "boost_luck": 18, "boost_sell": 18, "boost_xp": 18,
    },
    "Void Shard": {
        "ammo_type": "soul_shard",
        "description": "Dark matter crystallised — powerful all-round.",
        "emoji": "🟣",
        "price": 32, "currency": "gems",
        "boost_luck": 32, "boost_sell": 32, "boost_xp": 32,
    },
    "Eternal Shard": {
        "ammo_type": "soul_shard",
        "description": "A shard from beyond — near-mythical enhancement.",
        "emoji": "🌠",
        "price": 60, "currency": "gems",
        "boost_luck": 48, "boost_sell": 48, "boost_xp": 48,
    },
    # ── COSMIC ROUNDS (Celestial Lance, Mythic Net, Dragon Cannon, Cosmic RPG) ──
    "Star Slug": {
        "ammo_type": "cosmic_round",
        "description": "Forged from meteorite — exceptional all-round power.",
        "emoji": "🌠",
        "price": 30, "currency": "money",
        "boost_luck": 10, "boost_sell": 10, "boost_xp": 10,
    },
    "Nebula Round": {
        "ammo_type": "cosmic_round",
        "description": "Compressed nebula gas — hunter becomes unstoppable.",
        "emoji": "🌌",
        "price": 75, "currency": "money",
        "boost_luck": 22, "boost_sell": 22, "boost_xp": 22,
    },
    "Celestial Core": {
        "ammo_type": "cosmic_round",
        "description": "Pure divine energy — bends fate in the hunter's favour.",
        "emoji": "✨",
        "price": 40, "currency": "gems",
        "boost_luck": 38, "boost_sell": 38, "boost_xp": 38,
    },
    "Eternal Cosmos": {
        "ammo_type": "cosmic_round",
        "description": "The universe condensed — absolute peak performance.",
        "emoji": "🌀",
        "price": 65, "currency": "gems",
        "boost_luck": 50, "boost_sell": 50, "boost_xp": 50,
    },
    # ── NUKES (Nuke Launcher) ────────────────────────────────────
    "Nuke": {
        "ammo_type": "nuke_only",
        "description": "NUKE goes BADA-BOOM",
        "emoji": "💣",
        "price": 500, "currency": "gems",
        "boost_luck": 0, "boost_sell": 1_000, "boost_xp": 0,
    },
}

# Map ammo_type → compatible tool names (for shop display)
AMMO_TYPE_TOOLS: dict[str, list[str]] = {}
for _tname, _tdata in TOOLS.items():
    _at = _tdata.get("ammo_type")
    if _at:
        AMMO_TYPE_TOOLS.setdefault(_at, []).append(_tname)

AMMO_TYPE_LABELS = {
    "arrow":        "Arrows",
    "bolt":         "Bolts",
    "bullet":       "Bullets",
    "tranq_dart":   "Tranq Darts",
    "energy_cell":  "Energy Cells",
    "soul_shard":   "Soul Shards",
    "cosmic_round": "Cosmic Rounds",
    "nuke_only":    "Nukes",
}

AMMO_MAX_STACK = 9_999


# ─────────────────────────────────────────────
# VEHICLES
# ─────────────────────────────────────────────

VEHICLES = {
    "Trail Boots":   {"emoji": "🥾", "tier":  1, "boost_cd": 0.3, "boost_luck":  0, "price":      500, "currency": "money", "description": "A reliable pair of boots. Slightly faster."},
    "Bicycle":       {"emoji": "🚲", "tier":  2, "boost_cd": 0.5, "boost_luck":  0, "price":    5_000, "currency": "money", "description": "Pedal your way to prey."},
    "Dirt Bike":     {"emoji": "🏍️", "tier":  3, "boost_cd": 0.7, "boost_luck":  0, "price":   25_000, "currency": "money", "description": "Off-road and fast."},
    "Pickup Truck":  {"emoji": "🚗", "tier":  4, "boost_cd": 1.0, "boost_luck":  0, "price":  100_000, "currency": "money", "description": "Reliable workhorse."},
    "4x4 Offroader": {"emoji": "🚙", "tier":  5, "boost_cd": 1.3, "boost_luck":  5, "price":  500_000, "currency": "money", "description": "Conquers any terrain."},
    "Rowboat":       {"emoji": "🛶", "tier":  6, "boost_cd": 1.5, "boost_luck":  5, "price":1_000_000, "currency": "money", "description": "Silent on the water."},
    "Helicopter":    {"emoji": "🚁", "tier":  7, "boost_cd": 1.7, "boost_luck":  0, "price":5_000_000, "currency": "money", "description": "Scout from above."},
    "Horse":         {"emoji": "🐴", "tier":  8, "boost_cd": 1.9, "boost_luck": 10, "price":10_000_000,"currency": "money", "description": "A hunter's best friend."},
    "Military Jeep": {"emoji": "🛻", "tier":  9, "boost_cd": 2.1, "boost_luck":  0, "price":      500, "currency": "gems",  "description": "Built for the toughest hunts."},
    "Hovercraft":    {"emoji": "🚀", "tier": 10, "boost_cd": 2.4, "boost_luck": 15, "price":    2_000, "currency": "gems",  "description": "Endgame speed machine."},
}


# ─────────────────────────────────────────────
# HUNTING CRATES
# ─────────────────────────────────────────────

import random as _random

CRATE_TIERS = {
    "Common Crate": {
        "emoji": "📦",
        "price": 50_000,
        "currency": "money",
        "description": "A basic crate. Contains modest rewards.",
        "color": 0x95A5A6,
    },
    "Rare Crate": {
        "emoji": "🎁",
        "price": 200_000,
        "currency": "money",
        "description": "A rarer crate with better loot.",
        "color": 0x3498DB,
    },
    "Epic Crate": {
        "emoji": "💠",
        "price": 500,
        "currency": "gems",
        "description": "An epic crate. Rare boosts and big rewards.",
        "color": 0x9B59B6,
    },
    "Legendary Crate": {
        "emoji": "🌟",
        "price": 2_000,
        "currency": "gems",
        "description": "A legendary crate. Permanent boosts possible.",
        "color": 0xF39C12,
    },
    "Mythic Crate": {
        "emoji": "🌀",
        "price": 5_000,
        "currency": "gems",
        "description": "The rarest crate. Exclusive titles and massive rewards.",
        "color": 0xE74C3C,
    },
}

# Reward pool definitions
# Each reward: (weight, type, data)
# types: money, gems, perm_boost, temp_boost, title
# perm_boost data: {"stat": "luck"|"sell"|"xp", "amount": N}
# temp_boost data: {"stat": "luck"|"sell"|"xp", "amount": N, "minutes": M}
# title data: {"title": "..."}

CRATE_REWARDS = {
    "Common Crate": [
        (40, "money",      {"min": 50_000,       "max": 500_000}),
        (30, "money",      {"min": 100_000,      "max": 1_000_000}),
        (15, "gems",       {"min": 50,           "max": 150}),
        (10, "temp_boost", {"stat": "luck",  "amount": 10, "minutes": 1}),
        (10, "temp_boost", {"stat": "sell",  "amount": 10, "minutes": 1}),
        (10, "temp_boost", {"stat": "xp",    "amount": 10, "minutes": 1}),
        (5,  "temp_boost", {"stat": "luck",  "amount": 15, "minutes": 2}),
        (5,  "temp_boost", {"stat": "sell",  "amount": 15, "minutes": 2}),
        (3,  "perm_boost", {"stat": "luck",  "amount": 1}),
        (2,  "perm_boost", {"stat": "sell",  "amount": 1}),
        (2,  "perm_boost", {"stat": "xp",    "amount": 1}),
    ],
    "Rare Crate": [
        (30, "money",      {"min": 500_000,      "max": 5_000_000}),
        (20, "gems",       {"min": 100,          "max": 300}),
        (15, "temp_boost", {"stat": "luck",  "amount": 20, "minutes": 3}),
        (15, "temp_boost", {"stat": "sell",  "amount": 20, "minutes": 3}),
        (10, "temp_boost", {"stat": "luck",  "amount": 30, "minutes": 5}),
        (10, "temp_boost", {"stat": "sell",  "amount": 30, "minutes": 5}),
        (8,  "temp_boost", {"stat": "xp",    "amount": 30, "minutes": 5}),
        (5,  "perm_boost", {"stat": "luck",  "amount": 2}),
        (5,  "perm_boost", {"stat": "sell",  "amount": 2}),
        (5,  "perm_boost", {"stat": "xp",    "amount": 2}),
        (3,  "title",      {"title": "Lucky Find"}),
        (2,  "title",      {"title": "The Collector"}),
    ],
    "Epic Crate": [
        (25, "money",      {"min": 5_000_000,    "max": 50_000_000}),
        (20, "gems",       {"min": 200,          "max": 600}),
        (15, "temp_boost", {"stat": "luck",  "amount": 40, "minutes": 5}),
        (15, "temp_boost", {"stat": "sell",  "amount": 40, "minutes": 5}),
        (10, "temp_boost", {"stat": "luck",  "amount": 50, "minutes": 7}),
        (10, "temp_boost", {"stat": "sell",  "amount": 50, "minutes": 7}),
        (10, "temp_boost", {"stat": "xp",    "amount": 50, "minutes": 7}),
        (8,  "perm_boost", {"stat": "luck",  "amount": 3}),
        (8,  "perm_boost", {"stat": "sell",  "amount": 3}),
        (8,  "perm_boost", {"stat": "xp",    "amount": 3}),
        (5,  "title",      {"title": "Epic Opener"}),
        (3,  "title",      {"title": "Gear Hoarder"}),
        (2,  "title",      {"title": "The Fortunate"}),
    ],
    "Legendary Crate": [
        (20, "money",      {"min": 50_000_000,   "max": 500_000_000}),
        (15, "gems",       {"min": 500,          "max": 1_500}),
        (10, "temp_boost", {"stat": "luck",  "amount": 60, "minutes": 7}),
        (10, "temp_boost", {"stat": "sell",  "amount": 60, "minutes": 7}),
        (10, "temp_boost", {"stat": "luck",  "amount": 75, "minutes": 10}),
        (10, "temp_boost", {"stat": "sell",  "amount": 75, "minutes": 10}),
        (10, "temp_boost", {"stat": "xp",    "amount": 75, "minutes": 10}),
        (10, "perm_boost", {"stat": "luck",  "amount": 5}),
        (10, "perm_boost", {"stat": "sell",  "amount": 5}),
        (10, "perm_boost", {"stat": "xp",    "amount": 5}),
        (5,  "title",      {"title": "Crate Addict"}),
        (5,  "title",      {"title": "Legend in the Making"}),
        (3,  "title",      {"title": "The Privileged"}),
        (2,  "title",      {"title": "Legendary Opener"}),
    ],
    "Mythic Crate": [
        (15, "money",      {"min": 500_000_000,  "max": 5_000_000_000}),
        (15, "gems",       {"min": 1_000,        "max": 5_000}),
        (10, "temp_boost", {"stat": "luck",  "amount": 100, "minutes": 10}),
        (10, "temp_boost", {"stat": "sell",  "amount": 100, "minutes": 10}),
        (10, "temp_boost", {"stat": "luck",  "amount": 100, "minutes": 10}),
        (10, "temp_boost", {"stat": "sell",  "amount": 100, "minutes": 10}),
        (10, "temp_boost", {"stat": "xp",    "amount": 100, "minutes": 10}),
        (10, "perm_boost", {"stat": "luck",  "amount": 8}),
        (10, "perm_boost", {"stat": "sell",  "amount": 8}),
        (10, "perm_boost", {"stat": "xp",    "amount": 8}),
        (5,  "title",      {"title": "Mythic Chaser"}),
        (5,  "title",      {"title": "Beyond Lucky"}),
        (3,  "title",      {"title": "The Anointed"}),
        (2,  "title",      {"title": "Mythic Opener"}),
        (1,  "title",      {"title": "The One Who Has Everything"}),
    ],
}


def open_crate(crate_name: str) -> dict:
    """Roll a reward from the given crate. Returns reward dict."""
    pool = CRATE_REWARDS.get(crate_name, [])
    if not pool:
        return {"type": "money", "amount": 0}

    weights = [w for w, *_ in pool]
    chosen  = _random.choices(pool, weights=weights, k=1)[0]
    _, rtype, rdata = chosen

    if rtype == "money":
        return {"type": "money", "amount": _random.randint(rdata["min"], rdata["max"])}
    if rtype == "gems":
        return {"type": "gems", "amount": _random.randint(rdata["min"], rdata["max"])}
    if rtype == "perm_boost":
        return {"type": "perm_boost", "stat": rdata["stat"], "amount": rdata["amount"]}
    if rtype == "temp_boost":
        return {"type": "temp_boost", "stat": rdata["stat"],
                "amount": rdata["amount"], "minutes": rdata["minutes"]}
    if rtype == "title":
        return {"type": "title", "title": rdata["title"]}
    return {"type": "money", "amount": 0}


# ─────────────────────────────────────────────
# HUNT CRATE DROP
# ─────────────────────────────────────────────
# Each entry: (weight, crate_name_or_None)
# Base drop chance per hunt (before crate_luck boost):
#   Common  ~5.5%  |  Rare ~1.8%  |  Epic ~0.5%  |  Legendary ~0.18%
# Each point of crate_luck boost adds +0.5% to the non-None pool weight.

HUNT_CRATE_DROP_TABLE = [
    (500, None),
    (30,  "Common Crate"),
    (10,  "Rare Crate"),
    (3,   "Epic Crate"),
    (1,   "Legendary Crate"),
    # Mythic Crate intentionally excluded — shop/gem only
]

def roll_hunt_crate_drop(crate_luck_boost: int = 0) -> str | None:
    """
    Roll for a crate drop on a hunt.
    crate_luck_boost: the player's crate_luck stat (each point adds +0.5 to drop weight).
    Returns a crate name string, or None for no drop.
    """
    bonus = crate_luck_boost * 0.5
    pool = [
        (w + bonus if name is not None else w, name)
        for w, name in HUNT_CRATE_DROP_TABLE
    ]
    weights = [w for w, _ in pool]
    chosen  = _random.choices(pool, weights=weights, k=1)[0]
    return chosen[1]


# ─────────────────────────────────────────────
# SHOP BOOST ITEMS
# ─────────────────────────────────────────────

SHOP_BOOST_ITEMS = {
    "Lucky Charm": {
        "description": "Increases your personal luck by 5%.",
        "price": 20, "currency": "gems",
        "max_qty": 10,
        "boost_key": "luck", "boost_amt": 5,
    },
    "Sellmaster Scroll": {
        "description": "Increases your personal sell price by 5%.",
        "price": 20, "currency": "gems",
        "max_qty": 10,
        "boost_key": "sell", "boost_amt": 5,
    },
    "XP Tome": {
        "description": "Increases your personal XP gain by 5%.",
        "price": 20, "currency": "gems",
        "max_qty": 10,
        "boost_key": "xp", "boost_amt": 5,
    },
    "Crate Charm": {
        "description": "Increases your crate drop chance while hunting by +0.5% per level.",
        "price": 30, "currency": "gems",
        "max_qty": 10,
        "boost_key": "crate_luck", "boost_amt": 1,
    },
}


# ─────────────────────────────────────────────
# DAILY TIERS
# ─────────────────────────────────────────────
# Each entry is a dict so bot.py can access tier["money_min"] etc.
# get_daily_tier(level) returns the correct tier dict.

DAILY_TIERS: list[dict] = [
    {"min_level":    1, "money_min":         500, "money_max":         2_000, "gems_min":   5, "gems_max":   15},
    {"min_level":   50, "money_min":       2_000, "money_max":        10_000, "gems_min":  10, "gems_max":   30},
    {"min_level":  100, "money_min":      10_000, "money_max":        50_000, "gems_min":  20, "gems_max":   60},
    {"min_level":  250, "money_min":      50_000, "money_max":       200_000, "gems_min":  40, "gems_max":  100},
    {"min_level":  500, "money_min":     200_000, "money_max":     1_000_000, "gems_min":  80, "gems_max":  200},
    {"min_level": 1000, "money_min":   1_000_000, "money_max":    10_000_000, "gems_min": 150, "gems_max":  400},
    {"min_level": 1200, "money_min":  10_000_000, "money_max":   100_000_000, "gems_min": 300, "gems_max":  800},
]


def get_daily_tier(level: int) -> dict:
    """Return the daily reward tier dict for the given player level."""
    result = DAILY_TIERS[0]
    for tier in DAILY_TIERS:
        if level >= tier["min_level"]:
            result = tier
    return result


# ─────────────────────────────────────────────
# COLORS
# ─────────────────────────────────────────────

COLORS = {
    "green":       discord.Color(0x2ECC71),
    "dark green":  discord.Color(0x1E8449),
    "brown":       discord.Color(0x8B4513),
    "yellow":      discord.Color(0xF4D03F),
    "dark yellow": discord.Color(0xB7950B),
    "light blue":  discord.Color(0xAED6F1),
    "lime green":  discord.Color(0x39D353),
    "dark brown":  discord.Color(0x4A2C0A),
    "orange":      discord.Color(0xE67E22),
    "purple":      discord.Color(0x8E44AD),
    "dark blue":   discord.Color(0x1A237E),
    "rainbow":     discord.Color(0xFFB9FF),
    "platinum":    discord.Color(0xE5E4E2),
    "colorless":   discord.Color(0x000000),
}

COLOR_EMOJIS = {
    "green":       "<:Village_Green:1499985282785743041>",
    "dark green":  "<:Forest_Dark_Green:1499985281410138204>",
    "brown":       "<:Woods_Brown:1499985653847425074>",
    "yellow":      "<:Desert_Yellow:1499985279103008838>",
    "dark yellow": "<:Desert_Dark_Yellow:1499985277727408169>",
    "light blue":  "<:Tundra_Light_Blue:1499985276989341777>",
    "lime green":  "<:Jungle_Lime_Green:1499985275835908106>",
    "dark brown":  "<:Swamp_Dark_Brown:1499985272690053191>",
    "orange":      "<:Volcanic_Highlands_Orange:1499985274413776946>",
    "purple":      "<:Cursed_Ruins_Purple:1499985271637147678>",
    "dark blue":   "<:Abyssal_Depths_Blue:1499985270471397518>",
    "rainbow":     "<:Rainbow_Pink:1499985269313634387>",
    "platinum":    "<:Celestial_Peaks_Platinum:1499985268114198618>",
    "colorless":   "<:None_Colorless:1499985266889330708>",
}

COLOR_LABELS = {
    "green":       "Green",
    "dark green":  "Dark Green",
    "brown":       "Brown",
    "yellow":      "Yellow",
    "dark yellow": "Dark Yellow",
    "light blue":  "Light Blue",
    "lime green":  "Lime Green",
    "dark brown":  "Dark Brown",
    "orange":      "Orange",
    "purple":      "Purple",
    "dark blue":   "Dark Blue",
    "rainbow":     "Rainbow",
    "platinum":    "Platinum",
    "colorless":   "Colorless",
}

COLOR_DESCRIPTIONS = {
    "green":       "Apply a village-inspired green tone, reflecting early life and simplicity.",
    "dark green":  "Apply a forest-green tone, inspired by deep woodland environments.",
    "brown":       "Apply an earthy brown tone, grounded in natural survival landscapes.",
    "dark brown":  "Apply a deep woods tone, reflecting dense forest and ancient timber regions.",
    "yellow":      "Apply a bright village sunlight tone, representing open fields and early progress.",
    "dark yellow": "Apply a muted forest-edge glow, inspired by aged woodlands and dusk light.",
    "light blue":  "Apply a calm tundra sky tone, reflecting cold and open environments.",
    "dark blue":   "Apply a deep oceanic abyss tone, inspired by abyssal depths and pressure zones.",
    "lime green":  "Apply a vibrant jungle energy tone, reflecting dense and thriving ecosystems.",
    "orange":      "Apply a volcanic highlands tone, inspired by heat, lava fields, and eruption zones.",
    "purple":      "Apply a cursed ruins tone, reflecting corrupted and ancient forgotten lands.",
    "rainbow":     "Apply a rare spectrum tone, inspired by chaotic rainbow biome energy.",
    "platinum":    "Apply a celestial peaks tone, representing divine elevation and endgame mastery.",
    "colorless":   "Remove biome influence and return to neutral default state.",
}


# ─────────────────────────────────────────────
# GAMBLE
# ─────────────────────────────────────────────

ROULETTE_COLORS    = ["red", "black", "green"]   # equal 1/3 each

ROULETTE_BET_TYPES = {
    "red":   ("🔴 Red",   4, 2),
    "black": ("⚫ Black", 8, 2),
    "green": ("🟢 Green", 3, 5),
}

RPS_CHOICES = {"rock": "✊", "paper": "🖐️", "scissors": "✌️"}
RPS_BEATS   = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

# (min_bet, max_bet, win_chance_pct, win_multiplier)
SLOT_BIOME_CONFIG = {
    "village":             (        100,         10_000, 45, 2.0),
    "forest":              (        500,         50_000, 42, 2.2),
    "woods":               (      1_000,        100_000, 40, 2.5),
    "small_desert":        (      2_500,        250_000, 37, 2.8),
    "large_desert":        (      5_000,        500_000, 35, 3.0),
    "tundra":              (     10_000,      1_000_000, 32, 3.5),
    "jungle":              (     25_000,      2_500_000, 30, 3.8),
    "swamp":               (     50_000,      5_000_000, 28, 4.0),
    "volcanic_highlands":  (    100_000,     10_000_000, 25, 4.5),
    "cursed_ruins":        (    250_000,     25_000_000, 22, 5.0),
    "rainbow":             (    500_000,     50_000_000, 18, 6.0),
    "abyssal_depths":      (  1_000_000,    100_000_000, 15, 7.0),
    "celestial_peaks":     (  2_500_000,    250_000_000, 12, 8.0),
}


# ─────────────────────────────────────────────
# TIPS
# ─────────────────────────────────────────────

TIPS = [
    "Join a tribe to get Luck, Sell, and XP boosts!",
    "Higher biomes give bigger money rewards per hunt!",
    "Rare catches triple your money and double your XP!",
    "Use /idle to earn ◈ while you're away!",
    "Stack idle hours for massive passive income!",
    "Unlock new biomes as you level up with /biome!",
    "Your color is purely cosmetic — change it any time with /color!",
    "Buy boosts from /shop to improve your hunting!",
    "Upgrade your tools to unlock higher biomes!",
    "Prestige at level 1000 for permanent boost multipliers!",
    "Check /record to track every animal you've ever caught!",
    "Use /leaderboard to see how you rank globally!",
    "Higher tier tools let you catch multiple animals per hunt!",
    "Check /log to review your recent hunt history!",
    "Use /daily every day to build up your streak bonus!",
    "Equip ammo in /equip for extra Luck, Sell, and XP boosts!",
    "Ammo is consumed per hunt — stock up before long sessions!",
    "Gem-bought ammo gives up to 50% boosts on top of your tool!",
    "Running out of ammo? Head to /shop → Ammo tab!",
    "Some ammo types focus on specific stats — pick what you need!",
]


# ─────────────────────────────────────────────
# COMMAND IDs
# ─────────────────────────────────────────────

COMMAND_ID = {
    "biome":        "1499948413608001698",
    "color":        "1498883355079344158",
    "daily":        "1501740931840344116",
    "equip":        "1503563684704944223",
    "gift":         "1499960573864050721",
    "help":         "1499960573864050723",
    "hunt":         "1499563402585182289",
    "id":           "1499963837401530520",
    "idle":         "1499948413608001699",
    "invite":       "1501740931840344121",
    "leaderboard":  "1500335302601084959",
    "log":          "1501740931840344117",
    "mail":         "1502518159855321138",
    "menu":         "1501740931840344115",
    "prestige":     "1500335302601084961",
    "profile":      "1499960573864050720",
    "record":       "1500335302601084960",
    "shop":         "1499960573864050719",
    "tools":        "1500335302601084958",
    "tribe":        "1499962495341953184",
    "tutorial":     "1503916432134639697",
    "verify":       "1499948413608001696",
    "bot_shutdown": "1502786816036704372",
    "bot_resume":   "1502786816036704373",
    "setdevmail":   "1502786816036704374",
}


# ─────────────────────────────────────────────
# BADGES
# ─────────────────────────────────────────────

BADGES = {
    "ammo_master":      {"label": "Ammo Master",          "abbr": "AM", "stat": "ammo_used",        "gold": 1_000_000,  "plat": 5_000_000},
    "ammo_variety":     {"label": "Ammo Variety",         "abbr": "AV", "stat": "ammo_variety",     "gold": 1,          "plat": None},
    "daily_daily_g":    {"label": "Daily Daily",          "abbr": "DD", "stat": "daily_streak",     "gold": 730,        "plat": 1825},
    "legendary_hunter": {"label": "Legendary Hunter",     "abbr": "LH", "stat": "animals_caught",   "gold": 1_000_000,  "plat": 5_000_000},
    "game_master":      {"label": "Game Master",          "abbr": "GM", "stat": "game_master",      "gold": 1,          "plat": 2},
    "bj_dealer":        {"label": "Blackjack Dealer",     "abbr": "BD", "stat": "bj_wins",          "gold": 10_000,     "plat": 100_000},
    "cf_tosser":        {"label": "Coinflip Tosser",      "abbr": "CT", "stat": "cf_wins",          "gold": 10_000,     "plat": 100_000},
    "rl_spinner":       {"label": "Roulette Spinner",     "abbr": "RS", "stat": "rl_wins",          "gold": 10_000,     "plat": 100_000},
    "slots_machine":    {"label": "Slots Human-Machine",  "abbr": "SH", "stat": "slots_wins",       "gold": 10_000,     "plat": 100_000},
    "rps_npc":          {"label": "RPS NPC",              "abbr": "RN", "stat": "rps_wins",         "gold": 10_000,     "plat": 100_000},
    "lottery_winner":   {"label": "Lottery Winner",       "abbr": "LW", "stat": "lottery_wins",     "gold": 100,        "plat": 1_000},
    "prestige_master":  {"label": "Prestige Master",      "abbr": "PM", "stat": "prestige",         "gold": 10,         "plat": 50},
    "xp_explosion":     {"label": "XP Explosion",         "abbr": "XE", "stat": "total_xp_earned",  "gold": 100_000,    "plat": 500_000},
    "events_completer": {"label": "Events Completer",     "abbr": "EC", "stat": "events_completed", "gold": 10,         "plat": 20},
    "leveler":          {"label": "Leveler",              "abbr": "LV", "stat": "level",            "gold": 1_000,      "plat": 10_000},
    "crate_master":     {"label": "Crate Master",   "abbr": "CM", "stat": "crates_opened", "gold": 100,    "plat": 1_000},
}


# ─────────────────────────────────────────────
# ACHIEVEMENTS
#
# Canonical format: dict[str, list[tuple[int, list[tuple[str, int]]]]]
#   key  → achievement name
#   list → [(threshold, [(reward_type, reward_amount), ...]), ...]
#
# Every tier is (threshold, [(rtype, amount), ...]).
# The achievement checker in bot.py unpacks this single format only.
# The "gamble" key is intentionally an empty dict — bot.py skips it via
# the `if not isinstance(tiers, list): continue` guard.
# ─────────────────────────────────────────────

ACHIEVEMENTS: dict[str, list | dict] = {

    # ── Daily Streak ──────────────────────────────────────────────
    "daily_streak": [
        (       1,  [("money",              10_000)]),
        (      20,  [("money",              20_000)]),
        (      50,  [("money",              50_000)]),
        (      67,  [("money",              67_000)]),
        (     100,  [("money",           1_000_000), ("gems",                  100)]),
        (     183,  [("money",           5_000_000)]),
        (     365,  [("money",          10_000_000), ("gems",                  334)]),
        (     500,  [("money",         100_000_000), ("gems",                  500)]),
        (     666,  [("money",         666_666_666), ("gems",                  666)]),
        (     730,  [("money",                   0)]),   # title-only tier
        (   1_000,  [("money",       1_000_000_000)]),
        (   1_827,  [("money",      10_000_000_000), ("gems",                1_000)]),
        (   2_557,  [("money",     100_000_000_000)]),
        (   3_652,  [("money",   1_000_000_000_000), ("gems",               10_000)]),
    ],

    # ── Animals Caught ────────────────────────────────────────────
    "animals_caught": [
        (       100, [("money",              50_000)]),
        (       250, [("money",             100_000)]),
        (       500, [("money",             500_000)]),
        (     1_000, [("gems",                  250)]),
        (     1_500, [("money",           1_000_000)]),
        (     2_000, [("money",           2_000_000)]),
        (     3_000, [("money",           5_000_000)]),
        (     5_000, [("money",          10_000_000)]),
        (     7_500, [("money",          50_000_000)]),
        (    10_000, [("money",         100_000_000)]),
        (    20_000, [("money",         500_000_000)]),
        (    35_000, [("money",       1_000_000_000)]),
        (    50_000, [("money",       5_000_000_000)]),
        (    75_000, [("money",      20_000_000_000)]),
        (   100_000, [("money",      50_000_000_000)]),
        (   300_000, [("money",     100_000_000_000)]),
        (   650_000, [("money",     500_000_000_000)]),
        ( 1_000_000, [("money",   1_000_000_000_000)]),
        (10_000_000, [("gems",               10_000)]),
    ],

    # ── Ammo Used ─────────────────────────────────────────────────
    "ammo_used": [
        (       100, [("money",             100_000)]),
        (       250, [("money",             500_000)]),
        (       500, [("money",           1_000_000)]),
        (     1_000, [("money",           5_000_000)]),
        (     5_000, [("money",          40_000_000)]),
        (    10_000, [("money",         100_000_000)]),
        (    50_000, [("money",       1_000_000_000)]),
        (   100_000, [("money",      10_000_000_000)]),
    ],

    # ── Buy All Tools ─────────────────────────────────────────────
    "tools_bought_all": [
        (1, [("money", 100_000_000)]),
    ],

    # ── Use All Tools ─────────────────────────────────────────────
    "tools_used_all": [
        (1, [("money", 250_000_000)]),
    ],

    # ── Crates Opened ─────────────────────────────────────────────
    "crates_opened": [
        (      1, [("money",           100_000)]),
        (     10, [("money",         1_000_000)]),
        (     50, [("money",        10_000_000)]),
        (    100, [("gems",                500)]),
        (    250, [("money",       100_000_000)]),
        (    500, [("money",       500_000_000)]),
        (  1_000, [("money",     1_000_000_000), ("gems",              1_000)]),
        ( 10_000, [("money",    10_000_000_000)]),
    ],

    # ── Gamble — skipped by achievement checker ───────────────────
    "gamble": {},
}


# ─────────────────────────────────────────────
# ACHIEVEMENT TITLES
# ─────────────────────────────────────────────

ACHIEVEMENT_TITLES: dict[str, dict[str, str]] = {

    "daily_streak": {
        "1":     "I have claimed a daily!",
        "50":    "I'm on fire!",
        "100":   "100 Days of Hunting",
        "365":   "Year-Long Hunter",
        "666":   "Satan",
        "730":   "2 years now...",
        "1827":  "5 Year Veteran",
        "2557":  "Still Going Strong... Continue!",
        "3652":  "A Decade of Hunts... Nothing is impossible for you!",
    },

    "animals_caught": {
        "500":       "HUNT",
        "1000":      "Still Hunting...",
        "5000":      "HUNT HUNT",
        "10000":     "Can't Stop (Hunting)",
        "50000":     "HUNT HUNT HUNT",
        "100000":    "Never Touch Grass",
        "1000000":   "Legendary Hunter",
        "10000000":  "God of Hunters",
    },

    "ammo_used": {
        "100":    "I See Shells on the Ground",
        "1000":   "This Place is Covered in Shells",
        "10000":  "Moving HQ, too much shells",
        "100000": "Shells Are the New Dirt",
    },

    "tools_bought_all": {
        "1": "Ultimate Blacksmith",
    },

    "tools_used_all": {
        "1": "Tool Consumer",
    },

    "crates_opened": {
        "1":      "My First Crate",
        "10":     "Crate Curious",
        "100":    "Crate Opener",
        "500":    "Crate Fiend",
        "1000":   "Crate Addict (Legit)",
        "10000":  "The Crate Dimension",
    },
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

def color_display_name(color_key: str) -> str:
    if color_key.startswith("#"):
        return color_key.upper()
    return COLOR_LABELS.get(color_key, color_key.title())

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
# VERIFY HELPERS
# ─────────────────────────────────────────────

def generate_verify_code() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=4))

def init_verify(_: str):
    return {"needed": False, "time": 250, "code": generate_verify_code()}


# ─────────────────────────────────────────────
# QUESTS
# ─────────────────────────────────────────────
 
# How many quests drop per daily reset
QUESTS_PER_DAY = 3
 
# Hard cap on stored quests (5 pages × 3 quests each)
QUESTS_MAX     = 15
 
# Quest difficulty tiers — controls target counts and XP rewards.
# scale_level: player level used to pick a tier.
QUEST_TIERS = [
    {"name": "Easy",   "min_level":    1, "count_mult": 1.0, "xp_mult": 1.0,  "color": 0x2ECC71},
    {"name": "Medium", "min_level":   50, "count_mult": 2.5, "xp_mult": 2.0,  "color": 0x3498DB},
    {"name": "Hard",   "min_level":  200, "count_mult": 6.0, "xp_mult": 4.0,  "color": 0x9B59B6},
    {"name": "Expert", "min_level":  500, "count_mult": 15.0, "xp_mult": 8.0, "color": 0xF39C12},
    {"name": "Legend", "min_level": 1000, "count_mult": 35.0, "xp_mult": 18.0,"color": 0xE74C3C},
]
 
 
def get_quest_tier(level: int) -> dict:
    """Return the difficulty tier dict for a given player level."""
    result = QUEST_TIERS[0]
    for t in QUEST_TIERS:
        if level >= t["min_level"]:
            result = t
    return result
 
 
# Quest type templates.
# Each entry defines how to generate one quest.
#
# Fields:
#   id          – unique snake_case key
#   description – f-string template (substitutions applied in generate_quest)
#   icon        – emoji shown in the UI
#   stat        – what field in user data or context tracks progress
#   base_count  – target at tier multiplier 1.0 (scaled by tier count_mult)
#   base_xp     – XP reward at tier multiplier 1.0 (scaled by tier xp_mult)
#   requires    – optional dict with extra constraints
#                   "biome": specific biome key
#                   "rarity": animal rarity
#                   "tool_tier_min": minimum tool tier required
#                   "animal": specific animal name
#                   "crate_tier": specific crate name
#
QUEST_TEMPLATES = [
    # ── Hunting ───────────────────────────────
    {
        "id":          "hunt_any",
        "description": "Go on **{count}** hunts.",
        "icon":        "🏹",
        "stat":        "hunts_done",
        "base_count":  10,
        "base_xp":     400,
    },
    {
        "id":          "hunt_biome",
        "description": "Hunt **{count}** times in the **{biome_name}** biome.",
        "icon":        "🌍",
        "stat":        "hunts_in_biome",
        "base_count":  8,
        "base_xp":     550,
        "requires":    {"biome": True},   # True = pick a random biome at gen time
    },
    {
        "id":          "catch_any",
        "description": "Catch **{count}** animals (any kind).",
        "icon":        "🐾",
        "stat":        "animals_caught",
        "base_count":  15,
        "base_xp":     500,
    },
    {
        "id":          "catch_specific",
        "description": "Catch **{count}** **{animal}**.",
        "icon":        "🦌",
        "stat":        "animal_caught_specific",
        "base_count":  5,
        "base_xp":     700,
        "requires":    {"animal": True},   # True = pick a random animal at gen time
    },
    {
        "id":          "catch_rarity",
        "description": "Catch **{count}** animals of **{rarity}** rarity or higher.",
        "icon":        "⭐",
        "stat":        "rarity_caught",
        "base_count":  8,
        "base_xp":     800,
        "requires":    {"rarity": True},
    },
    {
        "id":          "perfect_catch",
        "description": "Land **{count}** Perfect Catches (rare bonus).",
        "icon":        "✨",
        "stat":        "perfect_catches",
        "base_count":  3,
        "base_xp":     900,
    },
    # ── Tools ─────────────────────────────────
    {
        "id":          "use_tool_tier",
        "description": "Hunt **{count}** times using a Tier **{tier}**+ tool.",
        "icon":        "🔧",
        "stat":        "tool_tier_hunts",
        "base_count":  10,
        "base_xp":     600,
        "requires":    {"tool_tier_min": True},
    },
    {
        "id":          "use_ammo",
        "description": "Use **{count}** ammo rounds while hunting.",
        "icon":        "🎯",
        "stat":        "ammo_used_quest",
        "base_count":  20,
        "base_xp":     500,
    },
    # ── Crates ────────────────────────────────
    {
        "id":          "open_crate_any",
        "description": "Open **{count}** crates (any tier).",
        "icon":        "📦",
        "stat":        "crates_opened_quest",
        "base_count":  3,
        "base_xp":     1200,
    },
    {
        "id":          "open_crate_tier",
        "description": "Open **{count}** **{crate_tier}**.",
        "icon":        "🌟",
        "stat":        "crate_tier_opened",
        "base_count":  2,
        "base_xp":     1500,
        "requires":    {"crate_tier": True},
    },
    {
        "id":          "drop_crate",
        "description": "Earn **{count}** crate drop(s) while hunting.",
        "icon":        "🎁",
        "stat":        "crate_drops_earned",
        "base_count":  2,
        "base_xp":     1000,
    },
    # ── Economy ───────────────────────────────
    {
        "id":          "earn_money",
        "description": "Earn **◈ {money_fmt}** from selling animals.",
        "icon":        "💰",
        "stat":        "money_earned_quest",
        "base_count":  100_000,
        "base_xp":     600,
    },
    {
        "id":          "sell_animals",
        "description": "Sell **{count}** animals from your inventory.",
        "icon":        "🏪",
        "stat":        "animals_sold_quest",
        "base_count":  30,
        "base_xp":     450,
    },
    # ── XP / Level ────────────────────────────
    {
        "id":          "earn_xp",
        "description": "Earn **{xp_fmt} XP** from any activity.",
        "icon":        "📚",
        "stat":        "xp_earned_quest",
        "base_count":  5_000,
        "base_xp":     700,
    },
    {
        "id":          "level_up",
        "description": "Level up **{count}** time(s).",
        "icon":        "⬆️",
        "stat":        "levels_gained_quest",
        "base_count":  1,
        "base_xp":     1000,
    },
    # ── Daily / Streak ────────────────────────
    {
        "id":          "claim_daily",
        "description": "Claim your daily reward **{count}** time(s).",
        "icon":        "📅",
        "stat":        "dailies_claimed_quest",
        "base_count":  1,
        "base_xp":     500,
    },
    {
        "id":          "maintain_streak",
        "description": "Reach a daily streak of **{count}** days.",
        "icon":        "🔥",
        "stat":        "daily_streak_reached",
        "base_count":  3,
        "base_xp":     800,
    },
    # ── Idle ──────────────────────────────────
    {
        "id":          "collect_idle",
        "description": "Collect from your idle worker **{count}** time(s).",
        "icon":        "⏰",
        "stat":        "idle_collections_quest",
        "base_count":  3,
        "base_xp":     400,
    },
    # ── Meta quests ───────────────────────────
    {
        "id":          "complete_quests",
        "description": "Complete **{count}** other quest(s) today.",
        "icon":        "📋",
        "stat":        "quests_completed_today",
        "base_count":  2,
        "base_xp":     1500,
    },
]
 
# Rarity ladder used for rarity-based quest generation
_QUEST_RARITY_POOL = ["uncommon", "rare", "epic", "legendary"]
 
 
def generate_quest(quest_id_or_template: dict, level: int, seed: int | None = None) -> dict:
    """
    Build a single quest dict from a template + player level.
 
    Returns:
        {
            "id":          str,          # unique instance id (template_id + seed)
            "template":    str,          # template id
            "description": str,          # rendered description string
            "icon":        str,          # emoji
            "stat":        str,          # which stat key to track progress on
            "target":      int,          # how much is needed
            "progress":    int,          # always starts at 0
            "xp_reward":   int,          # XP given on completion
            "completed":   bool,         # False until claimed
            "claimed":     bool,         # True once XP has been granted
            "created_date":str,          # ISO date string
            "requires":    dict,         # snapshot of resolved requires (for tracking)
        }
    """
    import random as _r
    rng = _r.Random(seed) if seed is not None else _r
 
    t     = quest_id_or_template
    tier  = get_quest_tier(level)
 
    # Resolve target count and XP, scaled by difficulty tier
    raw_count = int(t["base_count"] * tier["count_mult"])
    xp_reward = int(t["base_xp"]    * tier["xp_mult"])
 
    # Clamp count to a reasonable minimum
    raw_count = max(1, raw_count)
 
    # Resolve 'requires' placeholders
    resolved = {}
    req = t.get("requires", {})
 
    if req.get("biome"):
        # Pick a random biome the player can reach
        reachable = [(k, lvl) for k, lvl in BIOME_LEVELS if lvl <= max(level, 1)]
        chosen_biome = rng.choice(reachable)
        resolved["biome"]      = chosen_biome[0]
        resolved["biome_name"] = BIOME_NAMES.get(chosen_biome[0], chosen_biome[0].replace("_", " ").title())
 
    if req.get("animal"):
        # Pick an animal from any unlocked biome
        all_unlocked = [a for k, lvl in BIOME_LEVELS if lvl <= max(level, 1)
                          for a in BIOME_ANIMALS.get(k, [])]
        resolved["animal"] = rng.choice(all_unlocked) if all_unlocked else "Deer"
 
    if req.get("rarity"):
        resolved["rarity"] = rng.choice(_QUEST_RARITY_POOL)
 
    if req.get("tool_tier_min"):
        # Pick a random valid tier from 1 to a sensible max for the player
        max_tier = min(5, max(1, level // 100 + 1))
        resolved["tier"] = rng.randint(1, max_tier)
 
    if req.get("crate_tier"):
        resolved["crate_tier"] = rng.choice(["Common Crate", "Rare Crate", "Epic Crate", "Legendary Crate"])
 
    # Render description
    fmt_vars = dict(resolved)
    fmt_vars["count"]     = f"{raw_count:,}"
    fmt_vars["money_fmt"] = f"{raw_count:,}"
    fmt_vars["xp_fmt"]    = f"{raw_count:,}"
    try:
        description = t["description"].format(**fmt_vars)
    except KeyError:
        description = t["description"]
 
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
 
    uid = f"{t['id']}_{seed or _r.randint(0, 999999)}"
 
    return {
        "id":           uid,
        "template":     t["id"],
        "description":  description,
        "icon":         t["icon"],
        "stat":         t["stat"],
        "target":       raw_count,
        "progress":     0,
        "xp_reward":    xp_reward,
        "completed":    False,
        "claimed":      False,
        "created_date": today,
        "requires":     resolved,
    }
 
 
def roll_daily_quests(level: int, existing_templates: list[str]) -> list[dict]:
    """
    Generate QUESTS_PER_DAY new quest dicts, avoiding template repeats
    already in the player's active queue.
 
    existing_templates: list of template ids currently active (to avoid dups).
    """
    import random as _r, time as _t
 
    pool = [t for t in QUEST_TEMPLATES if t["id"] not in existing_templates]
    if not pool:
        pool = list(QUEST_TEMPLATES)   # fallback: allow repeats if all used
 
    chosen = _r.sample(pool, min(QUESTS_PER_DAY, len(pool)))
    seed_base = int(_t.time())
    return [generate_quest(t, level, seed=seed_base + i) for i, t in enumerate(chosen)]
 


RULES = [
    ("1", "Play Fair", "Do not use any bots, scripts, autoclickers, or macros to automate gameplay. Idle Hunter is designed to be played by humans. Automation of any kind will result in a permanent ban."),
    ("2", "No Exploiting", "Exploiting bugs, glitches, or unintended game mechanics for personal gain is strictly prohibited. If you discover a bug, report it via /report. Abuse of exploits will result in account resets or bans."),
    ("3", "No Account Sharing", "Each account must belong to one person. Sharing your account or playing on someone else's account is not allowed. We are not responsible for any losses that occur from account sharing."),
    ("4", "Respect Other Players", "Harassment, threats, hate speech, or targeted abuse toward other players will not be tolerated. This includes slurs, discrimination, and any form of bullying — in DMs, tribes, or public spaces."),
    ("5", "No Spam", "Spamming commands, buttons, or messages excessively disrupts the experience for everyone. Repeated spam after a warning may result in a temporary or permanent ban."),
    ("6", "No Scamming", "Scamming other players out of money, gems, or items through deception is prohibited. All trades and gifts are final — we do not reverse transactions, so be careful who you trust."),
    ("7", "Tribe Conduct", "Tribe leaders and officers are responsible for their tribe's behaviour. Abusing tribe tools such as repeated invite spam, mass kicking, or using tribe chat to harass is not allowed."),
    ("8", "No Real Money Trading", "Selling, buying, or trading in-game currency, items, or accounts for real money is strictly forbidden. Any accounts involved will be permanently banned with no appeal accepted."),
    ("9", "Use Commands Responsibly", "Commands like /suggest and /report exist to improve the game. Abusing them to spam developers or file false reports is not allowed and will result in a cooldown or ban."),
    ("10", "No Impersonation", "Do not impersonate developers, admins, or other players. Claiming to have special permissions or lying about your identity to manipulate others will result in a ban."),
    ("11", "English Only in Reports", "All reports, appeals, and suggestions must be written in English so our team can review them properly. Non-English submissions may be ignored or closed without response."),
    ("12", "Ban Appeals", "You are allowed up to 2 ban appeals. Appeals must be honest and respectful. Spamming appeals, submitting false information, or being rude to staff will result in your appeal being denied permanently."),
    ("13", "Data Accuracy", "Do not attempt to manipulate, corrupt, or inject data into your account or others. Any tampering with game data is treated as cheating and results in an immediate permanent ban."),
    ("14", "Respect the Economy", "Intentionally crashing the economy, distributing duped currency, or coordinating unfair market manipulation is not allowed and may result in economy resets and bans for all involved."),
    ("15", "Prestige Integrity", "Prestige is an endgame milestone. Attempting to prestige using exploited money or levels will result in a prestige rollback and a warning or ban."),
    ("16", "No Threats to the Service", "Any attempts to DDoS, hack, or otherwise disrupt the bot or its infrastructure will be reported to Discord and relevant authorities. This is a zero-tolerance rule."),
    ("17", "Follow Discord ToS", "All players must comply with Discord's Terms of Service at all times. Violations of Discord ToS while using Idle Hunter may result in a report to Discord and a permanent ban from the bot."),
    ("18", "No Admin Abuse", "If any admin abuses his/her position by accepting permanent bans with no accepted appeals (, etc. ) will be also demoted and permanently banned with no accepted appeals."),
    ("19", "Developer Decisions are Final", "The development team reserves the right to ban, reset, or modify any account at any time for any reason. Decisions made by the team are final and not subject to community vote."),
    ("20", "Rules May Change", "These rules may be updated at any time. It is your responsibility to stay informed. Continued use of Idle Hunter after a rules update constitutes acceptance of the new rules."),
    ("21", "Have Fun", "Idle Hunter is meant to be enjoyed. If something feels wrong or unfair, use the proper channels to report it. We want this to be a fun, fair experience for everyone. Happy hunting! 🏹"),
]
