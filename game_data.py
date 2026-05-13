import discord

BIOME_LEVELS = [
    ("village", 1), 
    ("forest", 10), 
    ("woods", 25), 
    ("small_desert", 50),
    ("large_desert", 100), 
    ("tundra", 150), 
    ("jungle", 200), 
    ("swamp", 275),
    ("volcanic_highlands", 350),
    ("cursed_ruins", 450), 
    ("rainbow", 600),
    ("abyssal_depths", 800), 
    ("celestial_peaks", 1000),
]

BIOME_EMOJIS = {
    "village": "<:Village:1499198420387369090>", 
    "forest": "<:Forest:1499200283593674975>",
    "woods": "<:Woods:1499201326142455938>", 
    "small_desert": "<:Small_Desert:1499201560473763850>",
    "large_desert": "<:Large_Desert:1499204067929620543>", 
    "tundra": "<:Tundra:1499230188389797888>",
    "jungle": "<:Jungle:1499230354362470490>", 
    "swamp": "<:Swamp:1499230538056335460>",
    "volcanic_highlands": "<:Volcanic_Highlands:1499230604825202871>",
    "cursed_ruins": "<:Cursed_Ruins:1499230731376005223>", 
    "rainbow": "<:Rainbow:1499943967620599979>",
    "abyssal_depths": "<:Abyssal_Depths:1499230862250610748>",
    "celestial_peaks": "<:Celestial_Peaks:1499230958295973929>",
}

BIOME_NAMES = {
    "village": "Village", 
    "forest": "Forest", 
    "woods": "Woods",
    "small_desert": "Small Desert", 
    "large_desert": "Large Desert",
    "tundra": "Tundra", 
    "jungle": "Jungle", 
    "swamp": "Swamp",
    "volcanic_highlands": "Volcanic Highlands", 
    "cursed_ruins": "Cursed Ruins",
    "rainbow": "Rainbow Realm", 
    "abyssal_depths": "Abyssal Depths",
    "celestial_peaks": "Celestial Peaks",
}

BIOME_ANIMALS = {
    "village": [
        "Rat", "Mouse", "Stray Cat", "Pigeon", "Crow", "Rabbit", "Fox",
        "Stray Dog", "Squirrel", "Sparrow"
    ],
    "forest": [
        "Deer", "Wild Boar", "Wolf", "Bear", "Elk", "Lynx", "Badger",
        "Pheasant", "Owl", "Hare"
    ],
    "woods": [
        "Moose", "Timber Wolf", "Black Bear", "Wild Turkey", "Coyote",
        "Raccoon", "Porcupine", "Snapping Turtle", "Grouse", "Mink"
    ],
    "small_desert": [
        "Scorpion", "Sand Viper", "Vulture", "Fennec Fox", "Armadillo",
        "Roadrunner", "Lizard", "Camel Spider", "Jerboa", "Coyote"
    ],
    "large_desert": [
        "Sandstorm Serpent", "Desert Lion", "Giant Scorpion", "Dust Hyena",
        "Sand Golem Crab", "Camel", "Dune Stalker Wolf", "Golden Eagle",
        "Desert Lynx", "Mirage Phantom"
    ],
    "tundra": [
        "Arctic Wolf", "Polar Bear", "Snowy Owl", "Reindeer", "Arctic Fox",
        "Musk Ox", "Wolverine", "Seal", "Walrus", "Snow Leopard"
    ],
    "jungle": [
        "Jaguar", "Anaconda", "Poison Dart Frog", "Toucan", "Panther",
        "Wild Boar", "Silverback Gorilla", "Komodo Dragon", "Piranha",
        "Giant Centipede"
    ],
    "swamp": [
        "Alligator", "Snapping Turtle", "Giant Frog", "Swamp Viper",
        "Mudskipper", "Black Panther", "Leech Hydra", "Bog Bear",
        "Marsh Hawk", "Will-o-Wisp Serpent"
    ],
    "volcanic_highlands": [
        "Lava Lizard", "Magma Boar", "Ember Wolf", "Ash Vulture",
        "Cinder Crab", "Obsidian Serpent", "Flame Lynx", "Molten Golem",
        "Fire Hawk", "Inferno Bear"
    ],
    "cursed_ruins": [
        "Skeleton Archer", "Shadow Wolf", "Bone Drake", "Cursed Knight",
        "Wraith Stag", "Plague Rat", "Stone Golem", "Phantom Lynx",
        "Soul Serpent", "Ancient Guardian"
    ],
    "rainbow": [
        "Prismatic Butterfly", "Chromatic Fox", "Rainbow Serpent",
        "Aurora Deer", "Spectrum Wolf", "Iridescent Hawk", "Prism Panther",
        "Hue Shifter Frog", "Kaleidoscope Crab", "The Living Rainbow"
    ],
    "abyssal_depths": [
        "Deep Sea Kraken", "Abyss Shark", "Shadow Eel", "Void Manta",
        "Leviathan Crab", "Bioluminescent Jellyfish", "Depth Stalker",
        "Abyssal Serpent", "Trench Golem", "Darkness Whale"
    ],
    "celestial_peaks": [
        "Storm Eagle", "Cloud Serpent", "Thunder Elk", "Sky Leviathan",
        "Divine Wolf", "Astral Panther", "Heavenly Dragon", "Celestial Bear",
        "Void Phoenix", "The Eternal Hunter"
    ],
}

ANIMAL_DATA = {
    "Rat": {"value": 30, "rarity": "common", "emoji": ""},
    "Mouse": {"value": 25, "rarity": "common", "emoji": ""},
    "Stray Cat": {"value": 60, "rarity": "uncommon", "emoji": ""},
    "Pigeon": {"value": 20, "rarity": "common", "emoji": ""},
    "Crow": {"value": 35, "rarity": "common", "emoji": ""},
    "Rabbit": {"value": 80, "rarity": "uncommon", "emoji": ""},
    "Fox": {"value": 120, "rarity": "rare", "emoji": ""},
    "Stray Dog": {"value": 55, "rarity": "common", "emoji": ""},
    "Squirrel": {"value": 40, "rarity": "common", "emoji": ""},
    "Sparrow": {"value": 18, "rarity": "common", "emoji": ""},
    "Deer": {"value": 150, "rarity": "common", "emoji": ""},
    "Wild Boar": {"value": 180, "rarity": "common", "emoji": ""},
    "Wolf": {"value": 300, "rarity": "uncommon", "emoji": ""},
    "Bear": {"value": 400, "rarity": "rare", "emoji": ""},
    "Elk": {"value": 200, "rarity": "common", "emoji": ""},
    "Lynx": {"value": 350, "rarity": "rare", "emoji": ""},
    "Badger": {"value": 130, "rarity": "common", "emoji": ""},
    "Pheasant": {"value": 110, "rarity": "common", "emoji": ""},
    "Owl": {"value": 220, "rarity": "uncommon", "emoji": ""},
    "Hare": {"value": 90, "rarity": "common", "emoji": ""},
    "Moose": {"value": 500, "rarity": "uncommon", "emoji": ""},
    "Timber Wolf": {"value": 450, "rarity": "uncommon", "emoji": ""},
    "Black Bear": {"value": 600, "rarity": "rare", "emoji": ""},
    "Wild Turkey": {"value": 250, "rarity": "common", "emoji": ""},
    "Coyote": {"value": 300, "rarity": "common", "emoji": ""},
    "Raccoon": {"value": 200, "rarity": "common", "emoji": ""},
    "Porcupine": {"value": 220, "rarity": "common", "emoji": ""},
    "Snapping Turtle": {"value": 350, "rarity": "uncommon", "emoji": ""},
    "Grouse": {"value": 210, "rarity": "common", "emoji": ""},
    "Mink": {"value": 400, "rarity": "uncommon", "emoji": ""},
    "Scorpion": {"value": 500, "rarity": "common", "emoji": ""},
    "Sand Viper": {"value": 700, "rarity": "uncommon", "emoji": ""},
    "Vulture": {"value": 600, "rarity": "common", "emoji": ""},
    "Fennec Fox": {"value": 800, "rarity": "uncommon", "emoji": ""},
    "Armadillo": {"value": 550, "rarity": "common", "emoji": ""},
    "Roadrunner": {"value": 450, "rarity": "common", "emoji": ""},
    "Lizard": {"value": 400, "rarity": "common", "emoji": ""},
    "Camel Spider": {"value": 750, "rarity": "uncommon", "emoji": ""},
    "Jerboa": {"value": 500, "rarity": "common", "emoji": ""},
    "Sandstorm Serpent": {"value": 1200, "rarity": "rare", "emoji": ""},
    "Desert Lion": {"value": 1500, "rarity": "rare", "emoji": ""},
    "Giant Scorpion": {"value": 1000, "rarity": "uncommon", "emoji": ""},
    "Dust Hyena": {"value": 900, "rarity": "uncommon", "emoji": ""},
    "Sand Golem Crab": {"value": 1100, "rarity": "rare", "emoji": ""},
    "Camel": {"value": 700, "rarity": "common", "emoji": ""},
    "Dune Stalker Wolf": {"value": 1300, "rarity": "rare", "emoji": ""},
    "Golden Eagle": {"value": 1000, "rarity": "uncommon", "emoji": ""},
    "Desert Lynx": {"value": 1100, "rarity": "rare", "emoji": ""},
    "Mirage Phantom": {"value": 2000, "rarity": "epic", "emoji": ""},
    "Arctic Wolf": {"value": 1500, "rarity": "uncommon", "emoji": ""},
    "Polar Bear": {"value": 2000, "rarity": "rare", "emoji": ""},
    "Snowy Owl": {"value": 1200, "rarity": "uncommon", "emoji": ""},
    "Reindeer": {"value": 1000, "rarity": "common", "emoji": ""},
    "Arctic Fox": {"value": 1300, "rarity": "uncommon", "emoji": ""},
    "Musk Ox": {"value": 900, "rarity": "common", "emoji": ""},
    "Wolverine": {"value": 1600, "rarity": "rare", "emoji": ""},
    "Seal": {"value": 800, "rarity": "common", "emoji": ""},
    "Walrus": {"value": 1100, "rarity": "uncommon", "emoji": ""},
    "Snow Leopard": {"value": 2500, "rarity": "epic", "emoji": ""},
    "Jaguar": {"value": 2500, "rarity": "rare", "emoji": ""},
    "Anaconda": {"value": 2000, "rarity": "rare", "emoji": ""},
    "Poison Dart Frog": {"value": 1500, "rarity": "uncommon", "emoji": ""},
    "Toucan": {"value": 1200, "rarity": "common", "emoji": ""},
    "Panther": {"value": 3000, "rarity": "epic", "emoji": ""},
    "Silverback Gorilla": {"value": 3500, "rarity": "epic", "emoji": ""},
    "Komodo Dragon": {"value": 2800, "rarity": "rare", "emoji": ""},
    "Piranha": {"value": 1800, "rarity": "uncommon", "emoji": ""},
    "Giant Centipede": {"value": 2200, "rarity": "rare", "emoji": ""},
    "Alligator": {"value": 3000, "rarity": "rare", "emoji": ""},
    "Giant Frog": {"value": 2000, "rarity": "uncommon", "emoji": ""},
    "Swamp Viper": {"value": 2500, "rarity": "rare", "emoji": ""},
    "Mudskipper": {"value": 1500, "rarity": "common", "emoji": ""},
    "Black Panther": {"value": 4000, "rarity": "epic", "emoji": ""},
    "Leech Hydra": {"value": 5000, "rarity": "epic", "emoji": ""},
    "Bog Bear": {"value": 3500, "rarity": "rare", "emoji": ""},
    "Marsh Hawk": {"value": 2200, "rarity": "uncommon", "emoji": ""},
    "Will-o-Wisp Serpent": {"value": 6000, "rarity": "legendary", "emoji": ""},
    "Lava Lizard": {"value": 4000, "rarity": "uncommon", "emoji": ""},
    "Magma Boar": {"value": 4500, "rarity": "rare", "emoji": ""},
    "Ember Wolf": {"value": 5000, "rarity": "rare", "emoji": ""},
    "Ash Vulture": {"value": 3500, "rarity": "uncommon", "emoji": ""},
    "Cinder Crab": {"value": 4000, "rarity": "uncommon", "emoji": ""},
    "Obsidian Serpent": {"value": 6000, "rarity": "epic", "emoji": ""},
    "Flame Lynx": {"value": 5500, "rarity": "epic", "emoji": ""},
    "Molten Golem": {"value": 8000, "rarity": "legendary", "emoji": ""},
    "Fire Hawk": {"value": 5000, "rarity": "rare", "emoji": ""},
    "Inferno Bear": {"value": 7000, "rarity": "epic", "emoji": ""},
    "Skeleton Archer": {"value": 6000, "rarity": "uncommon", "emoji": ""},
    "Shadow Wolf": {"value": 7000, "rarity": "rare", "emoji": ""},
    "Bone Drake": {"value": 10000, "rarity": "epic", "emoji": ""},
    "Cursed Knight": {"value": 8000, "rarity": "rare", "emoji": ""},
    "Wraith Stag": {"value": 9000, "rarity": "epic", "emoji": ""},
    "Plague Rat": {"value": 5000, "rarity": "uncommon", "emoji": ""},
    "Stone Golem": {"value": 8500, "rarity": "rare", "emoji": ""},
    "Phantom Lynx": {"value": 11000, "rarity": "epic", "emoji": ""},
    "Soul Serpent": {"value": 12000, "rarity": "legendary", "emoji": ""},
    "Ancient Guardian": {"value": 15000, "rarity": "legendary", "emoji": ""},
    "Prismatic Butterfly": {"value": 12000, "rarity": "rare", "emoji": ""},
    "Chromatic Fox": {"value": 15000, "rarity": "rare", "emoji": ""},
    "Rainbow Serpent": {"value": 18000, "rarity": "epic", "emoji": ""},
    "Aurora Deer": {"value": 14000, "rarity": "rare", "emoji": ""},
    "Spectrum Wolf": {"value": 20000, "rarity": "epic", "emoji": ""},
    "Iridescent Hawk": {"value": 13000, "rarity": "rare", "emoji": ""},
    "Prism Panther": {"value": 22000, "rarity": "epic", "emoji": ""},
    "Hue Shifter Frog": {"value": 16000, "rarity": "rare", "emoji": ""},
    "Kaleidoscope Crab": {"value": 25000, "rarity": "legendary", "emoji": ""},
    "The Living Rainbow": {"value": 50000, "rarity": "mythic", "emoji": ""},
    "Deep Sea Kraken": {"value": 25000, "rarity": "epic", "emoji": ""},
    "Abyss Shark": {"value": 20000, "rarity": "rare", "emoji": ""},
    "Shadow Eel": {"value": 18000, "rarity": "rare", "emoji": ""},
    "Void Manta": {"value": 22000, "rarity": "epic", "emoji": ""},
    "Leviathan Crab": {"value": 28000, "rarity": "epic", "emoji": ""},
    "Bioluminescent Jellyfish": {"value": 15000, "rarity": "rare", "emoji": ""},
    "Depth Stalker": {"value": 24000, "rarity": "epic", "emoji": ""},
    "Abyssal Serpent": {"value": 30000, "rarity": "legendary", "emoji": ""},
    "Trench Golem": {"value": 35000, "rarity": "legendary", "emoji": ""},
    "Darkness Whale": {"value": 50000, "rarity": "mythic", "emoji": ""},
    "Storm Eagle": {"value": 40000, "rarity": "epic", "emoji": ""},
    "Cloud Serpent": {"value": 45000, "rarity": "epic", "emoji": ""},
    "Thunder Elk": {"value": 35000, "rarity": "rare", "emoji": ""},
    "Sky Leviathan": {"value": 60000, "rarity": "legendary", "emoji": ""},
    "Divine Wolf": {"value": 55000, "rarity": "legendary", "emoji": ""},
    "Astral Panther": {"value": 65000, "rarity": "legendary", "emoji": ""},
    "Heavenly Dragon": {"value": 80000, "rarity": "mythic", "emoji": ""},
    "Celestial Bear": {"value": 50000, "rarity": "legendary", "emoji": ""},
    "Void Phoenix": {"value": 90000, "rarity": "mythic", "emoji": ""},
    "The Eternal Hunter": {"value": 150000, "rarity": "mythic", "emoji": ""},
}

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

ANIMAL_EMOJI = ""

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
        "tier": 3, "price": 2000, "currency": "money",
        "boost_luck": 2, "boost_xp": 2,
        "emoji": "🔪",
        "multi_catch": 1,
        "ammo_type": None,
    },
    "Spear": {
        "description": "A wooden spear with a bone tip.",
        "tier": 4, "price": 8000, "currency": "money",
        "boost_luck": 3, "boost_xp": 3,
        "emoji": "🗡️",
        "multi_catch": 1,
        "ammo_type": None,
    },
    "Shortbow": {
        "description": "A basic bow for forest hunting.",
        "tier": 5, "price": 25000, "currency": "money",
        "boost_luck": 4, "boost_xp": 5,
        "emoji": "🏹",
        "multi_catch": 2,
        "ammo_type": "arrow",
    },
    "Longbow": {
        "description": "Greater range and precision.",
        "tier": 6, "price": 80000, "currency": "money",
        "boost_luck": 5, "boost_xp": 6,
        "emoji": "🏹",
        "multi_catch": 2,
        "ammo_type": "arrow",
    },
    "Crossbow": {
        "description": "Mechanical precision for tough prey.",
        "tier": 7, "price": 250000, "currency": "money",
        "boost_luck": 6, "boost_xp": 8,
        "emoji": "🎯",
        "multi_catch": 2,
        "ammo_type": "bolt",
    },
    "Musket": {
        "description": "A flintlock for serious hunters.",
        "tier": 8, "price": 750000, "currency": "money",
        "boost_luck": 7, "boost_xp": 10,
        "emoji": "🔫",
        "multi_catch": 2,
        "ammo_type": "bullet",
    },
    "Hunting Rifle": {
        "description": "A bolt-action rifle for big game.",
        "tier": 9, "price": 2000000, "currency": "money",
        "boost_luck": 9, "boost_xp": 12,
        "emoji": "🔫",
        "multi_catch": 3,
        "ammo_type": "bullet",
    },
    "Shotgun": {
        "description": "Devastating at close range.",
        "tier": 10, "price": 5000000, "currency": "money",
        "boost_luck": 10, "boost_xp": 14,
        "emoji": "🔫",
        "multi_catch": 3,
        "ammo_type": "bullet",
    },
    "Sniper Rifle": {
        "description": "Long-range precision firearm.",
        "tier": 11, "price": 50, "currency": "gems",
        "boost_luck": 12, "boost_xp": 16,
        "emoji": "🎯",
        "multi_catch": 3,
        "ammo_type": "bullet",
    },
    "Tranq Gun": {
        "description": "Sedates prey, raising rare catch chance.",
        "tier": 12, "price": 80, "currency": "gems",
        "boost_luck": 15, "boost_xp": 18,
        "emoji": "💉",
        "multi_catch": 3,
        "ammo_type": "tranq_dart",
    },
    "Plasma Caster": {
        "description": "Energy weapon from a distant future.",
        "tier": 13, "price": 120, "currency": "gems",
        "boost_luck": 18, "boost_xp": 22,
        "emoji": "⚡",
        "multi_catch": 4,
        "ammo_type": "energy_cell",
    },
    "Gravity Trap": {
        "description": "A field device that bends space to capture prey.",
        "tier": 14, "price": 180, "currency": "gems",
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
        "tier": 19, "price": 1000, "currency": "gems",
        "boost_luck": 46, "boost_xp": 52,
        "emoji": "🐉",
        "multi_catch": 5,
        "ammo_type": "cosmic_round",
    },
    "Cosmic RPG": {
        "description": "The ultimate weapon — fires concentrated star energy.",
        "tier": 20, "price": 1500, "currency": "gems",
        "boost_luck": 55, "boost_xp": 60,
        "emoji": "🚀",
        "multi_catch": 6,
        "ammo_type": "cosmic_round",
    },
}

BIOME_TOOL_TIER = {
    "village": 1, 
    "forest": 2, 
    "woods": 3, 
    "small_desert": 4,
    "large_desert": 5, 
    "tundra": 6, 
    "jungle": 7, 
    "swamp": 8,
    "volcanic_highlands": 10, 
    "cursed_ruins": 13, 
    "rainbow": 15,
    "abyssal_depths": 17, 
    "celestial_peaks": 19,
}

# ─────────────────────────────────────────────
# AMMO SYSTEM
# ─────────────────────────────────────────────
# ammo_type groups: arrow, bolt, bullet, tranq_dart, energy_cell, soul_shard, cosmic_round
# Each type has multiple tiers: one money-bought (weak), one gems-bought (strong)
# Boosts are per-hunt percentages applied on top of tool boosts.
# Stat focus per type:
#   arrow        → luck + xp
#   bolt         → luck + sell
#   bullet       → sell + xp
#   tranq_dart   → luck only (big)
#   energy_cell  → xp + sell
#   soul_shard   → all three (moderate)
#   cosmic_round → all three (large)

AMMO = {
    # ── ARROWS (Shortbow, Longbow) ────────────
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

    # ── BOLTS (Crossbow) ──────────────────────
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

    # ── BULLETS (Musket, Hunting Rifle, Shotgun, Sniper Rifle) ───
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

    # ── TRANQ DARTS (Tranq Gun) ───────────────
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

    # ── ENERGY CELLS (Plasma Caster, Gravity Trap) ───
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

    # ── SOUL SHARDS (Soul Snare, Void Bow) ────
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

    # ── COSMIC ROUNDS (Celestial Lance, Mythic Net, Dragon Cannon, Cosmic RPG) ───
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
}

# Map ammo_type → compatible tool names (for shop display filtering)
AMMO_TYPE_TOOLS: dict[str, list[str]] = {}
for _tname, _tdata in TOOLS.items():
    _at = _tdata.get("ammo_type")
    if _at:
        AMMO_TYPE_TOOLS.setdefault(_at, []).append(_tname)

# Map ammo_type → display label
AMMO_TYPE_LABELS = {
    "arrow":        "Arrows",
    "bolt":         "Bolts",
    "bullet":       "Bullets",
    "tranq_dart":   "Tranq Darts",
    "energy_cell":  "Energy Cells",
    "soul_shard":   "Soul Shards",
    "cosmic_round": "Cosmic Rounds",
}

AMMO_MAX_STACK = 9999

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
    "Prestige at level 1200 for permanent boost multipliers!",
    "Check /record to track every animal you've ever caught!",
    "Use /leaderboard to see how you rank globally!",
    "Higher tier tools let you catch multiple animals per hunt!",
    "Check /log to review your recent hunt history!",
    "Use /daily every day to build up your streak bonus!",
    "Equip ammo in /tools for extra Luck, Sell, and XP boosts!",
    "Ammo is consumed per hunt — stock up before long sessions!",
    "Gem-bought ammo gives up to 50% boosts on top of your tool!",
    "Running out of ammo? Head to /shop → Ammo tab!",
    "Some ammo types focus on specific stats — pick what you need!",
]

COMMAND_ID = {
    "biome": "1499948413608001698",
    "color": "1498883355079344158",
    "daily": "1501740931840344116",
    "equip": "1503563684704944223",
    "gift": "1499960573864050721",
    "help": "1499960573864050723",
    "hunt": "1499563402585182289",
    "id": "1499963837401530520",
    "idle": "1499948413608001699",
    "invite": "1501740931840344121",
    "leaderboard": "1500335302601084959",
    "log": "1501740931840344117",
    "mail": "1502518159855321138",
    "menu": "1501740931840344115",
    "prestige": "1500335302601084961",
    "profile": "1499960573864050720",
    "record": "1500335302601084960",
    "shop": "1499960573864050719",
    "tools": "1500335302601084958",
    "tribe": "1499962495341953184",
    "tutorials": "1503916432134639697",
    "verify": "1499948413608001696",
    "bot_shutdown": "1502786816036704372",
    "bot_resume": "1502786816036704373",
    "setdevmail": "1502786816036704374",
}

DAILY_TIERS = [
    (    1,        500,        2_000,      5,       15),
    (   50,      2_000,       10_000,     10,       30),
    (  100,     10_000,       50_000,     20,       60),
    (  250,     50_000,      200_000,     40,      100),
    (  500,    200_000,    1_000_000,     80,      200),
    ( 1000,  1_000_000,   10_000_000,    150,      400),
    ( 1200, 10_000_000,  100_000_000,    300,      800),
]

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
    "colorless":   discord.Color(0x2F3136),
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
    "green": "Green", 
    "dark green": "Dark Green", 
    "brown": "Brown",
    "yellow": "Yellow",
    "dark yellow": "Dark Yellow", 
    "light blue": "Light Blue",
    "lime green": "Lime Green", 
    "dark brown": "Dark Brown", 
    "orange": "Orange",
    "purple": "Purple", 
    "dark blue": "Dark Blue", 
    "rainbow": "Rainbow",
    "platinum": "Platinum", 
    "colorless": "Colorless",
}

COLOR_DESCRIPTIONS = {
    "green": "Apply a village-inspired green tone, reflecting early life and simplicity.",
    "dark green": "Apply a forest-green tone, inspired by deep woodland environments.",
    "brown": "Apply an earthy brown tone, grounded in natural survival landscapes.",
    "dark brown": "Apply a deep woods tone, reflecting dense forest and ancient timber regions.",
    "yellow": "Apply a bright village sunlight tone, representing open fields and early progress.",
    "dark yellow": "Apply a muted forest-edge glow, inspired by aged woodlands and dusk light.",
    "light blue": "Apply a calm tundra sky tone, reflecting cold and open environments.",
    "dark blue": "Apply a deep oceanic abyss tone, inspired by abyssal depths and pressure zones.",
    "lime green": "Apply a vibrant jungle energy tone, reflecting dense and thriving ecosystems.",
    "orange": "Apply a volcanic highlands tone, inspired by heat, lava fields, and eruption zones.",
    "purple": "Apply a cursed ruins tone, reflecting corrupted and ancient forgotten lands.",
    "rainbow": "Apply a rare spectrum tone, inspired by chaotic rainbow biome energy.",
    "platinum": "Apply a celestial peaks tone, representing divine elevation and endgame mastery.",
    "colorless": "Remove biome influence and return to neutral default state.",
}

SHOP_BOOST_ITEMS = {
    "Lucky Charm": {
        "description": "Increases your personal luck by 5%.",
        "price": 20, "currency": "gems",
        "max_qty": 10,
        "boost_key": "luck", "boost_amt": 5
    },
    "Sellmaster Scroll": {
        "description": "Increases your personal sell price by 5%.",
        "price": 20, "currency": "gems",
        "max_qty": 10,
        "boost_key": "sell", "boost_amt": 5
    },
    "XP Tome": {
        "description": "Increases your personal XP gain by 5%.",
        "price": 20, "currency": "gems",
        "max_qty": 10,
        "boost_key": "xp", "boost_amt": 5
    },
}

VEHICLES = {
    "Trail Boots":    {"emoji": "🥾", "tier": 1,  "boost_cd": 0.3, "boost_luck": 0,  "price": 500,          "currency": "money", "description": "A reliable pair of boots. Slightly faster."},
    "Bicycle":        {"emoji": "🚲", "tier": 2,  "boost_cd": 0.5, "boost_luck": 0,  "price": 5_000,        "currency": "money", "description": "Pedal your way to prey."},
    "Dirt Bike":      {"emoji": "🏍️", "tier": 3,  "boost_cd": 0.7, "boost_luck": 0,  "price": 25_000,       "currency": "money", "description": "Off-road and fast."},
    "Pickup Truck":   {"emoji": "🚗", "tier": 4,  "boost_cd": 1.0, "boost_luck": 0,  "price": 100_000,      "currency": "money", "description": "Reliable workhorse."},
    "4x4 Offroader":  {"emoji": "🚙", "tier": 5,  "boost_cd": 1.3, "boost_luck": 5,  "price": 500_000,      "currency": "money", "description": "Conquers any terrain."},
    "Rowboat":        {"emoji": "🛶", "tier": 6,  "boost_cd": 1.5, "boost_luck": 5,  "price": 1_000_000,    "currency": "money", "description": "Silent on the water."},
    "Helicopter":     {"emoji": "🚁", "tier": 7,  "boost_cd": 1.7, "boost_luck": 0,  "price": 5_000_000,    "currency": "money", "description": "Scout from above."},
    "Horse":          {"emoji": "🐴", "tier": 8,  "boost_cd": 1.9, "boost_luck": 10, "price": 10_000_000,   "currency": "money", "description": "A hunter's best friend."},
    "Military Jeep":  {"emoji": "🛻", "tier": 9,  "boost_cd": 2.1, "boost_luck": 0,  "price": 500,          "currency": "gems",  "description": "Built for the toughest hunts."},
    "Hovercraft":     {"emoji": "🚀", "tier": 10, "boost_cd": 2.4, "boost_luck": 15, "price": 2_000,        "currency": "gems",  "description": "Endgame speed machine."},
}
