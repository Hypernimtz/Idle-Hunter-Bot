"""
game_data.py — All static game content: biomes, animals, tools, ammo,
vehicles, boosts, colours, achievements, badges, tips, and command IDs.

Does NOT import from bot.py or backend.py.
Discord is imported only for Color constants.
"""

import discord, random, string, datetime, re
from datetime import datetime, timezone

def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ═════════════════════════════════════════════════════════════════════════
# EMOJI  ·  SINGLE SOURCE OF TRUTH
# ═════════════════════════════════════════════════════════════════════════
# Every custom emoji the bot uses is defined ONCE here. To change an emoji
# (new id, point it elsewhere, or swap to a plain-unicode fallback), edit its
# value in this dict and nowhere else — BIOME_EMOJIS, RARITY_ICONS,
# TRIBE_EMOJIS, USER_EMOJIS, UPGRADE_EMOJI and the /menu options
# are all built from it further down.
#
# Format: "<:name:id>" for a custom emoji, or just "🐾" for plain unicode.

EMOJI = {
    # ── Biomes ────────────────────────────────────────────────
    "village":            "<:village:1545568997565800529>",
    "forest":             "<:forest:1545568996005249205>",
    "woods":              "<:woods:1545568994529120416>",
    "small_desert":       "<:small_desert:1545568992826236939>",
    "sunken_coast":       "<:sunken_coast:1546352080770564246>",
    "tundra":             "<:tundra:1545568990657519676>",
    "jungle":             "<:jungle:1545568989323731084>",
    "swamp":              "<:swamp:1545568987914575983>",
    "volcanic_highlands": "<:volcanic_highlands:1545569995688255618>",
    "cursed_ruins":       "<:cursed_ruins:1545568986865999963>",
    "rainbow":            "<:rainbow:1545568985465225327>",
    "abyssal_depths":     "<:abyssal_depths:1545568984131178506>",
    "celestial_peaks":    "<:celestial_peaks:1545568982629883986>",

    # ── Rarity ────────────────────────────────────────────────
    "rarity_common":      "<:Common_Rarity:1499983185105387590>",
    "rarity_uncommon":    "<:Uncommon_Rarity:1499983588236460032>",
    "rarity_rare":        "<:Rare_Rarity:1499983646973497344>",
    "rarity_epic":        "<:Epic_Rarity:1499983688304431266>",
    "rarity_legendary":   "<:Legendary_Rarity:1499983727936147547>",
    "rarity_mythic":      "<:Mythic_Rarity:1499983777923993732>",

    # ── Crafting crystals (shards use the rarity icons above) ──
    "crystal_common":     "<:common_crystal:1546362605214371881>",
    "crystal_uncommon":   "<:uncommon_crystal:1546362604044292116>",
    "crystal_rare":       "<:rare_crystal:1546362602849050634>",
    "crystal_epic":       "<:epic_crystal:1546362601590628452>",
    "crystal_legendary":  "<:legendary_crystal:1546362600030212148>",
    "crystal_mythic":     "<:mythic_crystal:1546362599095013376>",

    # ── Bot / stat icons ──────────────────────────────────────
    "upgrade":            "<:Upgrades:1545300062853402746>",
    "xp":                 "<:XP:1544879141156028558>",
    "levels":             "<:lvl:1545569013105426493>",
    "stats":              "<:Stats:1545295849448276041>",
    "luck":               "<:Luck:1544879017755418634>",
    "biome":              "<:Biome:1545295450712834118>",
    "cooldown":           "<:cooldown:1545569008072523847>",
    "level_up":           "<:Level_Up:1545300418525929552>",
    "profile":            "<:Profile:1544881489164902480>",
    "sell_boost":         "<:sell_boost:1545569009414705233>",
    "xp_boost":           "<:xp_boost:1545569010886774784>",
    "luck_boost":         "<:luck_boost:1545569011906125915>",

    # ── Currency ──────────────────────────────────────────────
    "gem":                "<:Gem:1544879711400890398>",
    "coin_sample":        "<:Currency_SAMPLE:1544879593599803402>",

    # ── Feature icons (menu / screen headers) ────────────────
    "settings":           "<:Settings:1545295653922537522>",
    "daily":              "<:Daily:1545296051739828234>",
    "quests":             "<:Quests:1545296208434561054>",
    "leaderboard":        "<:Leaderboard:1545296515092713493>",
    "new_notif":          "<:New_Notif:1545296680373452882>",
    "achievements":       "<:Achievement:1545299593758244864>",
    "bow":                "<:Bow:1545299720052678737>",
    "collection":         "<:Collection:1545300017819164722>",
    "equipment":          "<:Equipment:1545300191618269184>",
    "inventory":          "<:Inventory:1545300256139247707>",
    "key":                "<:Key:1545300311147675688>",
    "lock":               "<:Lock:1545300385248452638>",
    "mail":               "<:Mail:1545300476856373298>",
    "vip":                "<:VIP:1545301018412195850>",
    "list":               "<:List:1545301191515176971>",
    "prestige":           "<:Prestige:1545301302756778024>",
    "season_pass":        "<:Season_Pass:1545301442489880668>",
    "clock":              "<:Clock:1544880382988517376>",
    "crate_sample":       "<:crate_sample:1545568981547491368>",  # generic crate (fallback art)
    "idle_camp":          "<:idle_camp:1545578488197546086>",

    # ── Vehicles (key = "vehicle_" + name.lower().replace(" ","_")) ──
    "vehicle_trail_boots":   "<:boots:1552151667854540877>",
    "vehicle_bicycle":       "<:bicycle:1552151666772672542>",
    "vehicle_dirt_bike":     "<:motorcycle:1552151665497612348>",
    "vehicle_pickup_truck":  "<:pickup_truck:1552152598713475193>",
    "vehicle_4x4_offroader": "<:4x4_offroader:1552160131397980220>",
    "vehicle_rowboat":       "<:rowboat:1552152597215977512>",
    "vehicle_helicopter":    "<:helicopter:1552152595647438849>",
    "vehicle_horse":         "<:horse:1552152593877307413>",
    "vehicle_military_jeep": "<:jeep:1549918393015214270>",
    "vehicle_hovercraft":    "<:hovercraft:1552152592375742535>",
    "potion_bottle":         "<:potion_bottle:1552151589299429497>",

    # ── Trophy materials (key = "trophy_" + _slug(drop name)) ──
    "trophy_gold_threaded_feather":   "<:gold_threaded_feather:1549967955939295322>",
    "trophy_frost_matted_pelt":       "<:frost_matted_pelt:1549967954806833223>",
    "trophy_fire_gland_sac":          "<:fire_gland_sac:1549967953737425036>",
    "trophy_everburning_ember":       "<:everburning_ember:1549967952735117392>",
    "trophy_ember_eye_coal":          "<:ember_eye_coal:1549967951585607690>",
    "trophy_dripping_bridle":         "<:dripping_bridle:1549967950386045018>",
    "trophy_coffin_nail":             "<:coffin_nail:1549967949266157688>",
    "trophy_coarse_yowie_hair":       "<:coarse_yowie_hair:1549967947907473488>",
    "trophy_bronze_nose_ring":        "<:bronze_nose_ring:1549967946690863254>",
    "trophy_broken_hel_chain_link":   "<:broken_hel_chain_link:1549967945642287245>",
    "trophy_bottle_of_dragon_breath": "<:bottle_of_dragon_breath:1549967944442708060>",
    "trophy_bone_reef_lyre_string":   "<:bone_reef_lyre_string:1549967943289274529>",
    "trophy_black_cloud_wisp":        "<:black_cloud_wisp:1549967942119067708>",
    "trophy_billabong_tusk":          "<:billabong_tusk:1549967940798119996>",
    "trophy_barrel_thick_scale":      "<:barrel_thick_scale:1549967939321729174>",
    "trophy_barbed_tail_spine":       "<:barbed_tail_spine:1549967938084147210>",
    "trophy_grapnel_talon":           "<:grapnel_talon:1549967915120459886>",
    "trophy_hollow_fang":             "<:hollow_fang:1549967917523669053>",
    "trophy_immortal_head_tooth":     "<:immortal_head_tooth:1549967918761119844>",
    "trophy_jar_of_closet_shadow":    "<:jar_of_closet_shadow:1549967920057294930>",
    "trophy_kraken_ink_vial":         "<:kraken_ink_vial:1549967921046884402>",
    "trophy_loch_silt_sample":        "<:loch_silt_sample:1549967922250653696>",
    "trophy_matted_fur_tuft":         "<:matted_fur_tuft:1549967923471450174>",
    "trophy_petrified_troll_nose":    "<:petrified_troll_nose:1549967924817694751>",
    "trophy_petrifying_eye":          "<:petrifying_eye:1549967925933383721>",
    "trophy_primary_flight_quill":    "<:primary_flight_quill:1549967927103721623>",
    "trophy_reeking_wing_feather":    "<:reeking_wing_feather:1549967928282054667>",
    "trophy_silver_burned_fang":      "<:silver_burned_fang:1549967929607725106>",
    "trophy_six_fanged_collar":       "<:six_fanged_collar:1549967930719076372>",
    "trophy_snake_mane_scale":        "<:snake_mane_scale:1549967931985629224>",
    "trophy_stone_gaze_lens":         "<:stone_gaze_lens:1549967933147586642>",
    "trophy_vial_of_grave_dust":      "<:vial_of_grave_dust:1549967934330511360>",
    "trophy_webbed_claw":             "<:webbed_claw:1549967935655641168>",
    "trophy_weighing_scale_feather":  "<:weighing_scale_feather:1549967936788103219>",

    # ── Tribe ─────────────────────────────────────────────────
    "tribe":              "<:Tribe:1544881569792135198>",
    "tribe_members":      "<:Members:1545301250784886885>",
    "tribe_kick":         "<:tribe_kick:1545569000204013578>",
    "tribe_invite":       "<:tribe_invite:1545569006944133160>",
    "tribe_ban":          "<:tribe_ban:1545569001273303130>",
    "tribe_leave":        "<:tribe_leave:1545571276150542366>",
    "tribe_leader":       "<:Leader:1545300347617280120>",
    "tribe_officer":      "<:Officer:1545300510108688414>",
    "tribe_demote":       "<:tribe_demote:1545569003374645288>",
    "tribe_set_desc":     "<:tribe_set_desc:1545569004524015656>",
    "tribe_promote":      "<:tribe_promote:1545569002372202587>",
    "tribe_transfer":     "<:tribe_transfer:1545569005874708500>",


    # ── Animals ───────────────────────────────────────────────
    "animal_fallback":    "🐾",   # used for any animal with no emoji of its own

    # ── Tools ─────────────────────────────────────────────────
    # Keys are "tool_" + tool name lower-cased with spaces → underscores.
    "tool_bare_hands":      "<:barehands:1546251150368448623>",
    "tool_slingshot":       "<:slingshot:1546251170903892080>",
    "tool_hunting_knife":   "<:huntingknife:1546251158904119307>",
    "tool_spear":           "<:spear:1546251174733283348>",
    "tool_shortbow":        "<:shortbow:1546251168341303457>",
    "tool_longbow":         "<:longbow:1546251161353326772>",
    "tool_crossbow":        "<:crossbow:1546251153900183663>",
    "tool_musket":          "<:musket:1546251162620268614>",
    "tool_hunting_rifle":   "<:huntingrifle:1546251160141430946>",
    "tool_shotgun":         "<:shotgun:1546251169544802345>",
    "tool_sniper_rifle":    "<:sniperrifle:1546251172040679424>",
    "tool_tranq_gun":       "<:tranqgun:1546251176079655103>",
    "tool_plasma_caster":   "<:plasmacaster:1546251167045259294>",
    "tool_gravity_trap":    "<:gravitytrap:1546251156387405925>",
    "tool_soul_snare":      "<:soulsnare:1546251173529657514>",
    "tool_void_bow":        "<:voidbow:1546251178340257944>",
    "tool_celestial_lance": "<:celestiallance:1546251151408893982>",
    "tool_mythic_net":      "<:mythicnet:1546251164377686228>",
    "tool_dragon_cannon":   "<:dragoncannon:1546251155213000804>",
    "tool_cosmic_rpg":      "<:cosmicrpg:1546251152113532979>",
    "tool_nuke_launcher":   "<:nukelauncher:1546251165803483236>",

    # ── Ammo ──────────────────────────────────────────────────
    # Keys are "ammo_" + ammo name lower-cased with spaces → underscores.
    "ammo_wooden_arrow":     "<:woodenarrow:1546251096647794738>",
    "ammo_iron_arrow":       "<:ironarrow:1546251075831468112>",
    "ammo_enchanted_arrow":  "<:enchantedarrow:1546251067346526248>",
    "ammo_phantom_arrow":    "<:phantomarrow:1546251081510686860>",
    "ammo_crude_bolt":       "<:crudebolt:1546251065521868931>",
    "ammo_steel_bolt":       "<:steelbolt:1546251090322784307>",
    "ammo_gilded_bolt":      "<:gildedbolt:1546251073440714942>",
    "ammo_venom_bolt":       "<:venombolt:1546251092201832578>",
    "ammo_lead_ball":        "<:leadball:1546251077052145816>",
    "ammo_hollow_point":     "<:hollowpoint:1546251074808062052>",
    "ammo_silver_bullet":    "<:silverbullet:1546251086430470236>",
    "ammo_void_round":       "<:voidround:1546251093498138706>",
    "ammo_basic_tranq":      "<:basictranq:1546251061839536280>",
    "ammo_potent_tranq":     "<:potenttranq:1546251083868012584>",
    "ammo_exotic_serum":     "<:exoticserum:1546251070437724190>",
    "ammo_void_serum":       "<:voidserum:1546251094550642728>",
    "ammo_charged_cell":     "<:chargedcell:1546251063999336579>",
    "ammo_overcharged_cell": "<:overchargedcell:1546251080416108686>",
    "ammo_plasma_core":      "<:plasmacore:1546251082563457084>",
    "ammo_singularity_cell": "<:singularitycell:1546251087474856019>",
    "ammo_fractured_shard":  "<:fracturedshard:1546251071461269537>",
    "ammo_pure_shard":       "<:pureshard:1546251085180571699>",
    "ammo_void_shard":       "<:voidshard:1546251095603544235>",
    "ammo_eternal_shard":    "<:eternalshard:1546251069401862295>",
    "ammo_star_slug":        "<:starslug:1546251088565379164>",
    "ammo_nebula_round":     "<:nebularound:1546251078243455016>",
    "ammo_celestial_core":   "<:celestialcore:1546251063034912798>",
    "ammo_eternal_cosmos":   "<:eternalcosmos:1546251068055224412>",
    "ammo_nuke":             "<:nuke:1546251079354945577>",

    # ── Badges (gold / platinum tiers) ────────────────────────
    # Keyed "badge_<BADGES[key]['icon']>_gold" / "_plat".
    "badge_ammo_master_gold":         "<:ammo_master_gold:1546342864726925402>",
    "badge_ammo_master_plat":         "<:ammo_master_plat:1546342768245219328>",
    "badge_ammo_variety_gold":        "<:ammo_variety_gold:1546342865985081344>",
    "badge_blackjack_dealer_gold":    "<:blackjack_dealer_gold:1546342867268673576>",
    "badge_blackjack_dealer_plat":    "<:blackjack_dealer_plat:1546342769394712576>",
    "badge_coinflip_tosser_gold":     "<:coinflip_tosser_gold:1546342868577161276>",
    "badge_coinflip_tosser_plat":     "<:coinflip_tosser_plat:1546342770803744838>",
    "badge_crate_master_gold":        "<:crate_master_gold:1546342869583794227>",
    "badge_crate_master_plat":        "<:crate_master_plat:1546342772078805033>",
    "badge_daily_daily_gold":         "<:daily_daily_gold:1546342870766845982>",
    "badge_daily_daily_plat":         "<:daily_daily_plat:1546342773710528543>",
    "badge_events_completer_gold":    "<:events_completer_gold:1546342871852912780>",
    "badge_events_completer_plat":    "<:events_completer_plat:1546342775614869544>",
    "badge_game_master_gold":         "<:game_master_gold:1546342873312657408>",
    "badge_game_master_plat":         "<:game_master_plat:1546342776835285032>",
    "badge_legendary_hunter_gold":    "<:legendary_hunter_gold:1546342874478805032>",
    "badge_legendary_hunter_plat":    "<:legendary_hunter_plat:1546342777846104134>",
    "badge_leveler_gold":             "<:leveler_gold:1546342875569070131>",
    "badge_leveler_plat":             "<:leveler_plat:1546342779037421609>",
    "badge_lottery_winner_gold":      "<:lottery_winner_gold:1546342876789743656>",
    "badge_lottery_winner_plat":      "<:lottery_winner_plat:1546342781021192213>",
    "badge_prestige_master_gold":     "<:prestige_master_gold:1546342879213916200>",
    "badge_prestige_master_plat":     "<:prestige_master_plat:1546342782166237266>",
    "badge_roulette_spinner_gold":    "<:roulette_spinner_gold:1546342880732385340>",
    "badge_roulette_spinner_plat":    "<:roulette_spinner_plat:1546342783047041126>",
    "badge_rps_npc_gold":             "<:rps_npc_gold:1546342881801936956>",
    "badge_rps_npc_plat":             "<:rps_npc_plat:1546342784074653717>",
    "badge_slots_human_machine_gold": "<:slots_human_machine_gold:1546342882573688933>",
    "badge_slots_human_machine_plat": "<:slots_human_machine_plat:1546342785626542161>",
    "badge_xp_explosion_gold":        "<:xp_explosion_gold:1546342884020723774>",
    "badge_xp_explosion_plat":        "<:xp_explosion_plat:1546342787321167952>",
    # Special badges — admin-granted, no tiers.
    "badge_special_recon":            "<:special_recon_badge:1547379036769099778>",
    "badge_tester":                   "<:tester_badge:1547379022680563812>",
    "badge_bug_hunter":               "<:bug_hunter_badge:1547379006020657232>",

    # ── UI / status icons (replace bare unicode across the bot) ───
    "red_ball":            "<:red_ball:1547385227226259586>",       # 🔴  off / active-maintenance / burned
    "yellow_ball":         "<:yellow_ball:1547385226169425970>",    # 🟡  warning
    "green_ball":          "<:green_ball:1547384987618254938>",     # 🟢  on / normal / minted
    "dice":               "<:dice:1547384990554136738>",           # 🎲  gamble / dice
    "target":             "<:shot_on_target:1547384989031596183>", # 🎯  caught / catches-per-hunt
    "location_pin":       "<:destination_pin:1547384986297171978>",# 📍  you-are-here / region
    "refresh":            "<:refresh_button:1547384984934031432>", # 🔄  refresh buttons
    "announcement":       "<:annoucement:1547384983440728097>",    # 📢  dev mail / updates
    "link":               "<:links:1547384981989359730>",          # 🔗  invite links
    "plane":              "<:plane:1547384980294869102>",           # ✈️  travel / transit
    "tip":                "<:tip:1547384978336120882>",             # 💡  tips / suggestions
    "trash":              "<:trash:1547384976683565116>",           # 🗑️  delete / clear
    "fire":               "<:fire:1547384975261704203>",            # 🔥  daily streak
    "gift":               "<:gift:1547384972778930216>",            # 🎁  gift mail
    "earth":              "<:earth:1549917823189516479>",           # 🌍  global / world events
    "check_mark":         "<:check_mark:1549917883809792172>",      # ✅  success / confirm
    "cross_mark":         "<:cross_mark:1549918397914157166>",      # ❌  error / deny
    "warning":            "<:warning:1549918396705935450>",         # ⚠️  warning / caution
    "jeep":               "<:jeep:1549918393015214270>",            # 🚙  vehicle
    "palette":            "<:palette:1545568998954111018>",         # 🎨  color picker
    "home":               "<:Home:1544949741211885568>",            # 🏠  menu / home nav

    # -- Awaiting custom art (2026-09-16 sweep) --------------------
    # Bare-unicode placeholders for every remaining inline emoji in the
    # bot. Design/upload real art and swap each value for "<:name:id>" --
    # nothing else needs to change, ph()/emoji()/emoji_partial() all pick
    # up the new art automatically. Ordered by how often each is used.
    "camping":                          "🏕",   # x25
    "package":                          "📦",   # x19
    "wrench":                           "🔧",   # x15
    "sparkles":                         "✨",   # x14
    "wolf":                             "🐺",   # x14
    "hammer":                           "🔨",   # x13
    "world_map":                        "🗺",   # x13
    "eagle":                            "🦅",   # x12
    "first_place_medal":                "🥇",   # x11
    "label":                            "🏷",   # x11
    "party_popper":                     "🎉",   # x10
    "minus":                            "➖",   # x10
    "bar_chart":                        "📊",   # x10
    "star":                             "★",   # x10
    "military_medal":                   "🎖",   # x10
    "impact":                           "💥",   # x9
    "test_tube":                        "🧪",   # x9
    "deer":                             "🦌",   # x9
    "snake":                            "🐍",   # x9
    "pistol":                           "🔫",   # x8
    "heart":                            "❤",   # x8
    "handshake":                        "🤝",   # x8
    "shield":                           "🛡",   # x8
    "siren":                            "🚨",   # x7
    "diamond_small":                    "🔸",   # x7
    "eyes":                             "👀",   # x7
    "raised_fist":                      "✊",   # x7
    "leopard":                          "🐆",   # x7
    "gear":                             "⚙",   # x6
    "chart_with_upwards_trend":         "📈",   # x6
    "triangle_up":                      "🔼",   # x6
    "equals":                           "🟰",   # x6
    "bear":                             "🐻",   # x6
    "fish":                             "🐟",   # x6
    "goat":                             "🐐",   # x6
    "ogre":                             "👹",   # x5
    "fox":                              "🦊",   # x5
    "diamond_blue":                     "🔷",   # x5
    "adhesive_bandage":                 "🩹",   # x5
    "scroll":                           "📜",   # x5
    "person":                           "👤",   # x5
    "slot_machine":                     "🎰",   # x5
    "weather_showers":                  "🌦",   # x5
    "rocket":                           "🚀",   # x5
    "chipmunk":                         "🐿",   # x5
    "dollar":                           "💲",   # x4
    "duck":                             "🦆",   # x4
    "sports_medal":                     "🏅",   # x4
    "upwards_black_arrow":              "⬆",   # x4
    "stopwatch":                        "⏱",   # x4
    "glowing_star":                     "🌟",   # x4
    "adult":                            "🧑",   # x4
    "hammer_and_wrench":                "🛠",   # x4
    "firecracker":                      "🧨",   # x4
    "toolbox":                          "🧰",   # x4
    "four_leaf_clover":                 "🍀",   # x4
    "books":                            "📚",   # x4
    "broom":                            "🧹",   # x4
    "recycle":                          "♻",   # x4
    "bird":                             "🐦",   # x4
    "rooster":                          "🐓",   # x4
    "lizard":                           "🦎",   # x4
    "seal":                             "🦭",   # x4
    "shark":                            "🦈",   # x4
    "skull_and_crossbones":             "☠",   # x3
    "bank":                             "🏦",   # x3
    "bread":                            "🍞",   # x3
    "second_place_medal":               "🥈",   # x3
    "third_place_medal":                "🥉",   # x3
    "cheering_megaphone":               "📣",   # x3
    "runner":                           "🏃",   # x3
    "dash":                             "💨",   # x3
    "anger":                            "💢",   # x3
    "square_white":                     "⬜",   # x3
    "globe_with_meridians":             "🌐",   # x3
    "circle_black":                     "⚫",   # x3
    "group":                            "👥",   # x3
    "hourglass_with_flowing_sand":      "⏳",   # x3
    "clipboard":                        "📋",   # x3
    "banknote_with_dollar_sign":        "💵",   # x3
    "money_with_wings":                 "💸",   # x3
    "search":                           "🔍",   # x3
    "badger":                           "🦡",   # x3
    "boar":                             "🐗",   # x3
    "turtle":                           "🐢",   # x3
    "crocodile":                        "🐊",   # x3
    "squid":                            "🦑",   # x3
    "high_voltage_sign":                "⚡",   # x3
    "milky_way":                        "🌌",   # x3
    "calendar":                         "📅",   # x2
    "waving_black_flag":                "🏴",   # x2
    "ballot_box":                       "🗳",   # x2
    "anchor":                           "⚓",   # x2
    "compass":                          "🧭",   # x2
    "wilted_flower":                    "🥀",   # x2
    "plus":                             "➕",   # x2
    "telescope":                        "🔭",   # x2
    "skull":                            "💀",   # x2
    "mailbox":                          "📬",   # x2
    "triangle_down":                    "🔽",   # x2
    "circle_white":                     "⚪",   # x2
    "raised_hand_with_fingers_splayed": "🖐",   # x2
    "victory_hand":                     "✌",   # x2
    "seedling":                         "🌱",   # x2
    "memo":                             "📝",   # x2
    "crossed_swords":                   "⚔",   # x2
    "stop_square":                      "⏹",   # x2
    "x_mark":                           "✖",   # x2
    "sleeping_symbol":                  "💤",   # x2
    "black_question_mark_ornament":     "❓",   # x2
    "rabbit":                           "🐇",   # x2
    "owl":                              "🦉",   # x2
    "cat":                              "🐈",   # x2
    "scorpion":                         "🦂",   # x2
    "whale":                            "🐋",   # x2
    "bison":                            "🦬",   # x2
    "monkey":                           "🐒",   # x2
    "orangutan":                        "🦧",   # x2
    "dodo":                             "🦤",   # x2
    "dog":                              "🐕",   # x2
    "flamingo":                         "🦩",   # x2
    "blowfish":                         "🐡",   # x2
    "ox":                               "🐂",   # x2
    "cyclone":                          "🌀",   # x2
    "spider_web":                       "🕸",   # x2
    "moon_new":                         "🌑",   # x2
    "dragon":                           "🐉",   # x2
    "wood":                             "🪵",   # x2
    "statue":                           "🗿",   # x2
    "horse_head":                       "🐴",   # x2
    "shooting_star":                    "🌠",   # x2
    "baguette_bread":                   "🥖",   # x1
    "notebook":                         "📓",   # x1
    "diving_mask":                      "🤿",   # x1
    "clapper_board":                    "🎬",   # x1
    "face_sweat":                       "😰",   # x1
    "fist_punch":                       "👊",   # x1
    "leg":                              "🦵",   # x1
    "face_triumph":                     "😤",   # x1
    "cherries":                         "🍒",   # x1
    "lemon":                            "🍋",   # x1
    "bell":                             "🔔",   # x1
    "video_game":                       "🎮",   # x1
    "robot_face":                       "🤖",   # x1
    "bug":                              "🐛",   # x1
    "search_alt":                       "🔎",   # x1
    "chart_with_downwards_trend":       "📉",   # x1
    "open_file_folder":                 "📂",   # x1
    "square_black":                     "⬛",   # x1
    "rat":                              "🐀",   # x1
    "skunk":                            "🦨",   # x1
    "raccoon":                          "🦝",   # x1
    "otter":                            "🦦",   # x1
    "moose":                            "🫎",   # x1
    "mouse":                            "🐭",   # x1
    "lobster":                          "🦞",   # x1
    "dolphin":                          "🐬",   # x1
    "pig":                              "🐖",   # x1
    "hedgehog":                         "🦔",   # x1
    "tiger":                            "🐅",   # x1
    "kangaroo":                         "🦘",   # x1
    "spiral_shell":                     "🐚",   # x1
    "shrimp":                           "🦐",   # x1
    "peacock":                          "🦚",   # x1
    "panda":                            "🐼",   # x1
    "palms_up":                         "🤲",   # x1
    "boomerang":                        "🪃",   # x1
    "knife":                            "🔪",   # x1
    "dagger":                           "🗡",   # x1
    "syringe":                          "💉",   # x1
    "rain_cloud":                       "🌧",   # x1
    "sun":                              "☀",   # x1
    "evergreen_tree":                   "🌲",   # x1
    "herb":                             "🌿",   # x1
    "national_park":                    "🏞",   # x1
    "drop_of_blood":                    "🩸",   # x1
    "speaker":                          "🔊",   # x1
    "tent":                             "⛺",   # x1
    "feather":                          "🪶",   # x1
    "door":                             "🚪",   # x1
    "water_wave":                       "🌊",   # x1
    "person_climbing":                  "🧗",   # x1
    "footprints":                       "👣",   # x1
    "levitate":                         "🕴",   # x1
    "safety_vest":                      "🦺",   # x1
    "palm_down":                        "🫳",   # x1
    "sauropod":                         "🦕",   # x1
    "horse":                            "🐎",   # x1
    "vampire":                          "🧛",   # x1
    "lion":                             "🦁",   # x1
    "dog_alt":                          "🐶",   # x1
    "octopus":                          "🐙",   # x1
    "merperson":                        "🧜",   # x1
    "female":                           "♀",   # x1
    "snowflake":                        "❄",   # x1
    "dragon_head":                      "🐲",   # x1
    "zombie":                           "🧟",   # x1
    "crystal_ball":                     "🔮",   # x1
    "ghost":                            "👻",   # x1
    "pushpin":                          "📌",   # x1
    "nut_and_bolt":                     "🔩",   # x1
    "yellow_heart":                     "💛",   # x1
    "radio_button":                     "🔘",   # x1
    "moon_full":                        "🌕",   # x1
    "pill":                             "💊",   # x1
    "microscope":                       "🔬",   # x1
    "battery":                          "🔋",   # x1
    "hole":                             "🕳",   # x1
    "circle_purple":                    "🟣",   # x1
    "bomb":                             "💣",   # x1
    "hiking_boot":                      "🥾",   # x1
    "bicycle":                          "🚲",   # x1
    "racing_motorcycle":                "🏍",   # x1
    "canoe":                            "🛶",   # x1
    "helicopter":                       "🚁",   # x1
    "pickup_truck":                     "🛻",   # x1
    "alarm_clock":                      "⏰",   # x1
    "helmet":                           "⛑",   # x1

    # ── Playing cards (blackjack / high-low) — key = "<suit>_<rank>" ──
    # rank: 2..10 | jack | queen | king | ace   ·   NOTE: clubs_queen not yet uploaded.
    "spades_2":     "<:spades_2:1547399097521283112>",
    "spades_3":     "<:spades_3:1547399101186973716>",
    "spades_4":     "<:spades_4:1547399103229730867>",
    "spades_5":     "<:spades_5:1547399104508854392>",
    "spades_6":     "<:spades_6:1547399105884463200>",
    "spades_7":     "<:spades_7:1547399109114069062>",
    "spades_8":     "<:spades_8:1547399110187950191>",
    "spades_9":     "<:spades_9:1547399112394145912>",
    "spades_10":    "<:spades_10:1547399115069988884>",
    "spades_jack":  "<:spades_jack:1547399000540586014>",
    "spades_queen": "<:spades_queen:1547399002994245703>",
    "spades_king":  "<:spades_king:1547399001865986160>",
    "spades_ace":   "<:spades_ace:1547398999332356116>",
    "hearts_2":     "<:hearts_2:1547399075660431450>",
    "hearts_3":     "<:hearts_3:1547399078218834021>",
    "hearts_4":     "<:hearts_4:1547399079775047761>",
    "hearts_5":     "<:hearts_5:1547399080869888010>",
    "hearts_6":     "<:hearts_6:1547399083516371014>",
    "hearts_7":     "<:hearts_7:1547399085361995867>",
    "hearts_8":     "<:hearts_8:1547399086951374928>",
    "hearts_9":     "<:hearts_9:1547399088318713986>",
    "hearts_10":    "<:hearts_10:1547399089371619388>",
    "hearts_jack":  "<:hearts_jack:1547399091556843581>",
    "hearts_queen": "<:hearts_queen:1547399094790656070>",
    "hearts_king":  "<:hearts_king:1547399093125517392>",
    "hearts_ace":   "<:hearts_ace:1547399090550214666>",
    "diamonds_2":     "<:diamonds_2:1547399044140240998>",
    "diamonds_3":     "<:diamonds_3:1547399045394341941>",
    "diamonds_4":     "<:diamonds_4:1547399058442813501>",
    "diamonds_5":     "<:diamonds_5:1547399059617095680>",
    "diamonds_6":     "<:diamonds_6:1547399062628737044>",
    "diamonds_7":     "<:diamonds_7:1547399063614267465>",
    "diamonds_8":     "<:diamonds_8:1547399064600182787>",
    "diamonds_9":     "<:diamonds_9:1547399065875124285>",
    "diamonds_10":    "<:diamonds_10:1547399066827235349>",
    "diamonds_jack":  "<:diamonds_jack:1547399069587079198>",
    "diamonds_queen": "<:diamonds_queen:1547399074372657245>",
    "diamonds_king":  "<:diamonds_king:1547399072292540416>",
    "diamonds_ace":   "<:diamonds_ace:1547399068257489018>",
    "clubs_2":     "<:clubs_2:1547399017841958933>",
    "clubs_3":     "<:clubs_3:1547399020622913566>",
    "clubs_4":     "<:clubs_4:1547399021902037043>",
    "clubs_5":     "<:clubs_5:1547399024703963206>",
    "clubs_6":     "<:clubs_6:1547399026398339173>",
    "clubs_7":     "<:clubs_7:1547399027824394250>",
    "clubs_8":     "<:clubs_8:1547399035369951282>",
    "clubs_9":     "<:clubs_9:1547399036540289146>",
    "clubs_10":    "<:clubs_10:1547399037916028938>",
    "clubs_jack":  "<:clubs_jack:1547399040281608203>",
    "clubs_queen": "<:clubs_queen:1547399042924027904>",
    "clubs_king":  "<:clubs_king:1547399041690894336>",
    "clubs_ace":   "<:clubs_ace:1547399038947688499>",
    "card_back":   "<:cards_back:1547402118879772835>",   # 🂠 blackjack hole card

    # ── Misc feature icons ───────────────────────────────────
    "shop":        "<:shop:1547402777909788813>",           # 🏪 / 🛒 shop headers & menu

    # ── Crate tiers (auto-wired into CRATE_TIERS[*]["emoji"]; no rare art yet) ──
    "common_crate":     "<:common_crate:1547405242046484520>",
    "uncommon_crate":   "<:uncommon_crate:1547405240687525898>",
    "rare_crate":       "<:rare_crate:1547407260043452447>",
    "epic_crate":       "<:epic_crate:1547405239542358036>",
    "legendary_crate":  "<:legendary_crate:1547405238422736998>",
    "mythic_crate":     "<:mythic_crate:1547405236925239366>",

    # ── Gemstones (decorative crate-open bonus, per rarity) ──
    "common_gemstone":    "<:common_gemstone:1547405235679395880>",
    "uncommon_gemstone":  "<:uncommon_gemstone:1547405234161057885>",
    "rare_gemstone":      "<:rare_gemstone:1547405232550453329>",
    "epic_gemstone":      "<:epic_gemstone:1547405230818459728>",
    "legendary_gemstone": "<:legendary_gemstone:1547405228050087986>",
    "mythic_gemstone":    "<:mythic_gemstone:1547405226242474014>",

    # ── Green percentage bar (10 slots · 5% resolution) ────────
    # left/middle/right join full 10%-slots into one seamless pill;
    # whole = a single full 10% slot standing alone; half_whole = a
    # single 5% slot standing alone; half_right = +5% capping off a
    # bar that already has full slots before it. See _pct_bar().
    "green_bar_left":       "<:green_bar_left:1548098249825583184>",
    "green_bar_middle":     "<:green_bar_middle:1548098251478011904>",
    "green_bar_right":      "<:green_bar_right:1548098247619387505>",
    "green_bar_whole":      "<:green_bar_whole:1548100716164419766>",
    "green_bar_half_right": "<:green_bar_half_right:1548101134294581380>",
    "blank_icon":           "<:blank_icon:1549564556555194438>",
    "green_bar_half_whole": "<:green_bar_half_whole:1548101786127306914>",
}

# Uploaded 2026-09-23 (application emoji, named exactly like the key).
EMOJI.update({
    "wrench":            "<:wrench:1552532678497275994>",
    "sparkles":          "<:sparkles:1552532677297705092>",
    "slot_machine":      "<:slot_machine:1552532676169441450>",
    "siren":             "<:siren:1552532674474942474>",
    "shield":            "<:shield:1552532672923046010>",
    "party_popper":      "<:party_popper:1552532671849177148>",
    "package":           "<:package:1552532670658121808>",
    "military_medal":    "<:military_medal:1552532668825079908>",
    "label":             "<:label:1552532667314995210>",
    "impact":            "<:impact:1552532665486540861>",
    "heart":             "<:heart:1552532664072802354>",
    "handshake":         "<:handshake:1552532662764314724>",
    "first_place_medal": "<:first_place_medal:1552532661409677342>",
    "eyes":              "<:eyes:1552532660331749376>",
    "diamond_small":     "<:diamond_small:1552532659203481751>",
})

# Aliases — reuse existing art for icons without dedicated emoji yet.
EMOJI["world_map"]      = EMOJI["biome"]         # 🗺 the global-map globe (<:Biome:…>)
EMOJI["lottery_ticket"] = EMOJI["season_pass"]   # 🎟 lottery
EMOJI["coinflip"]       = EMOJI["coin_sample"]   # 🪙 coinflip / "sell all"
EMOJI["money_bag"]      = EMOJI["coin_sample"]   # 💰 was a bare-unicode placeholder (2026-09-22)
EMOJI["trophy"]         = EMOJI["leaderboard"]   # 🏆 trophies / records
EMOJI["book"]           = EMOJI["collection"]    # 📖 help / tutorial / stats
_EMOJI_ALIASES = {"hp": "heart"}   # alias -> source, re-pointed by adopt_named_emojis()
EMOJI["hp"]             = EMOJI["heart"]         # ❤️ player/animal HP — was genuinely undefined, unlike
                                                  # the four above (this key never existed at all, so
                                                  # every `emoji("hp")` call was silently falling back to
                                                  # its own hardcoded "❤️" default every time)

# Single-codepoint glyphs whose DEFAULT presentation is text, not emoji (❤ ⚙ 🛡 …).
# Without U+FE0F Discord renders these as a small monochrome symbol — the registry
# stored them bare, which is why the HP heart looked like plain unicode text.
_TEXT_DEFAULT_GLYPHS = set("🏕🗺🏷🎖🛡⚙❤⬆⏱⏹⛑🖐✌♀☠☀❄♻⚔✖🏞🌦🌧🕸🕴🕳🗡🛠🗳🏍🐿")
for _k, _v in list(EMOJI.items()):
    if len(_v) == 1 and _v in _TEXT_DEFAULT_GLYPHS:
        EMOJI[_k] = _v + "️"

_EMOJI_RE = re.compile(r"^<(a?):([A-Za-z0-9_]+):(\d+)>$")

def adopt_named_emojis(available: dict[str, str]) -> list[str]:
    """Auto-activate art by NAME. ``available`` maps an uploaded emoji's name to its
    ``<:name:id>`` string (application + server emojis). Any registry key that is
    still a plain-unicode placeholder and has an uploaded emoji of the same name is
    switched to it — so finishing an icon is just "upload it named like the key",
    then restart; no id copy-paste. Returns the keys adopted."""
    adopted = []
    for key, val in list(EMOJI.items()):
        if val.startswith("<"):
            continue
        cand = available.get(key)
        if cand and _EMOJI_RE.match(cand):
            EMOJI[key] = cand
            adopted.append(key)
    # aliases that were copied by value at import time
    for alias, src in _EMOJI_ALIASES.items():
        if not EMOJI.get(alias, "<").startswith("<") and EMOJI.get(src, "").startswith("<"):
            EMOJI[alias] = EMOJI[src]
            adopted.append(alias)
    return adopted

def emoji(key: str) -> str:
    """The `<:name:id>` / unicode string for a registry key (or '' if unknown)."""
    return EMOJI.get(key, "")

def emoji_partial(key: str) -> dict:
    """The `{'name', 'id', 'animated'}` form for a component payload's `emoji`
    field. Accepts a registry key OR a raw `<:name:id>` / unicode string."""
    s = EMOJI.get(key, key) or ""
    m = _EMOJI_RE.match(s)
    if m:
        return {"name": m.group(2), "id": m.group(3), "animated": bool(m.group(1))}
    # A single unicode emoji is a valid component `emoji` field; anything longer
    # (a leftover registry key, a whole label) is not — omit it.
    if s and len(s) <= 8 and not s.isascii():
        return {"name": s}
    return {}

_CARD_SUITS = {"♠": "spades", "♥": "hearts", "♦": "diamonds", "♣": "clubs"}
_CARD_RANKS = {"A": "ace", "J": "jack", "Q": "queen", "K": "king"}

def card_emoji(card: str) -> str:
    """Custom emoji for a card string like 'A♠' / '10♥' / 'K♣'. Falls back to the
    plain text card when the emoji isn't in the registry (e.g. the Queen of Clubs,
    not yet uploaded)."""
    if not card:
        return ""
    suit = _CARD_SUITS.get(card[-1])
    rank = _CARD_RANKS.get(card[:-1], card[:-1])
    if suit:
        e = EMOJI.get(f"{suit}_{rank}")
        if e:
            return e
    return card

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

def tool_emoji(tool_name: str) -> str:
    """The registered custom `tool_<slug>` art if it exists, else the plain
    unicode icon baked into TOOLS[tool_name] — every tool has real custom
    art uploaded, but most display code never looked it up."""
    key = "tool_" + tool_name.lower().replace(" ", "_")
    return emoji(key) or TOOLS.get(tool_name, {}).get("emoji", "🏹")

def ammo_emoji(ammo_name: str) -> str:
    """Same idea as tool_emoji() for AMMO."""
    key = "ammo_" + ammo_name.lower().replace(" ", "_")
    return emoji(key) or AMMO.get(ammo_name, {}).get("emoji", "🔸")


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
    ("sunken_coast",      100),
    ("tundra",            150),
    ("jungle",            200),
    ("swamp",             275),
    ("volcanic_highlands",350),
    ("cursed_ruins",      450),
    ("rainbow",           600),
    ("abyssal_depths",    800),
    ("celestial_peaks",  1000),
]

# Built from the EMOJI registry at the top of this file — edit ids there.
BIOME_EMOJIS = {k: EMOJI[k] for k in (
    "village", "forest", "woods", "small_desert", "sunken_coast", "tundra",
    "jungle", "swamp", "volcanic_highlands", "cursed_ruins", "rainbow",
    "abyssal_depths", "celestial_peaks",
)}

BIOME_NAMES = {
    "village":             "Village",
    "forest":              "Forest",
    "woods":               "Woods",
    "small_desert":        "Small Desert",
    "sunken_coast":        "Sunken Coast",
    "tundra":              "Tundra",
    "jungle":              "Jungle",
    "swamp":               "Swamp",
    "volcanic_highlands":  "Volcanic Highlands",
    "cursed_ruins":        "Cursed Ruins",
    "rainbow":             "Rainbow Realm",
    "abyssal_depths":      "Abyssal Depths",
    "celestial_peaks":     "Celestial Peaks",
}

# ── Biomes re-themed as real places on Earth (see BIOME_REGION below). ──
# The huntable roster of each biome is region-appropriate wildlife. Old rosters
# were retired here but their ANIMAL_DATA rows are kept (orphans) so existing
# inventories / record books still price and never KeyError. The `mythic` tier
# is no longer ordinary animals — it is the MYTHIC_CREATURES boss roster.
BIOME_ANIMALS = {
    # Pacific Northwest, North America
    "village": [
        "House Sparrow", "American Crow", "Douglas Squirrel", "Cottontail Rabbit",
        "Virginia Opossum", "Striped Skunk", "Common Raccoon", "Black-Tailed Deer",
        "Red Fox", "Western Coyote",
    ],
    # The British Isles, Europe
    "forest": [
        "European Hare", "Ring-Necked Pheasant", "Eurasian Badger", "Red Deer",
        "Eurasian Boar", "Roe Deer", "Tawny Owl", "Red Kite",
        "British Grey Wolf", "Eurasian Lynx",
    ],
    # Scandinavia, Europe
    "woods": [
        "Capercaillie", "Willow Ptarmigan", "Nordic Red Squirrel", "Mountain Reindeer",
        "Pine Marten", "Eurasian Elk", "Scandinavian Wolf", "Nordic Wolverine",
        "Boreal Lynx", "Nordic Brown Bear",
    ],
    # Egypt & the Sahara, Africa
    "small_desert": [
        "Desert Jerboa", "Rüppell's Fox", "Sand Cat", "Deathstalker Scorpion",
        "Saharan Horned Viper", "Egyptian Vulture", "Dorcas Gazelle", "Desert Monitor",
        "Addax Antelope", "Striped Hyena",
    ],
    # The North Atlantic (off Cape Ann) — WATER
    "sunken_coast": [
        "Atlantic Herring", "Harbor Seal", "Atlantic Cod", "Blue Lobster",
        "Striped Bass", "Harbor Porpoise", "Atlantic Bluefin Tuna", "Blue Shark",
        "Leatherback Turtle", "North Atlantic Humpback",
    ],
    # The Carpathians, Eastern Europe
    "tundra": [
        "Alpine Marmot", "Black Grouse", "Carpathian Red Deer", "Carpathian Boar",
        "Carpathian Lynx", "Carpathian Wolf", "Carpathian Bear", "European Bison",
        "Golden Jackal", "Ural Owl",
    ],
    # Southeast Asia & Japan
    "jungle": [
        "Crab-Eating Macaque", "Reticulated Python", "Malayan Tapir", "Sun Bear",
        "Clouded Leopard", "Japanese Serow", "King Cobra", "Bornean Orangutan",
        "Sunda Pangolin", "Indochinese Tiger",
    ],
    # The Australian Outback, Oceania
    "swamp": [
        "Red Kangaroo", "Emu", "Dingo", "Frilled Lizard",
        "Saltwater Crocodile", "Perentie", "Southern Cassowary", "Wedge-Tailed Eagle",
        "Common Wombat", "Inland Taipan",
    ],
    # Anatolia, Turkey
    "volcanic_highlands": [
        "Anatolian Ground Squirrel", "Chukar Partridge", "Bezoar Ibex", "Anatolian Leopard",
        "Anatolian Wolf", "Anatolian Hyena", "Caracal", "Syrian Brown Bear",
        "Griffon Vulture", "Anatolian Golden Eagle",
    ],
    # Ancient Greece, Europe
    "cursed_ruins": [
        "Kri-Kri Goat", "Hermann's Tortoise", "Grecian Jackal", "Grecian Boar",
        "Balkan Lynx", "Grecian Wolf", "Pindos Bear", "Aegean Vulture",
        "Mediterranean Monk Seal", "Olympian Eagle",
    ],
    # The Caribbean
    "rainbow": [
        "Scarlet Ibis", "Green Iguana", "Caribbean Flamingo", "Hawksbill Turtle",
        "Jamaican Boa", "West Indian Manatee", "Cuban Crocodile", "Caribbean Reef Shark",
        "Queen Conch", "Blue Marlin",
    ],
    # The Mediterranean Deep
    "abyssal_depths": [
        "Lanternfish", "Blackmouth Catshark", "Giant Red Shrimp", "Deep-Sea Anglerfish",
        "Gulper Eel", "Mediterranean Sperm Whale", "Giant Squid", "Bluntnose Sixgill Shark",
        "Common Fangtooth", "Colossal Squid",
    ],
    # Roof of the World — the Himalayas, Asia
    "celestial_peaks": [
        "Himalayan Marmot", "Bharal", "Himalayan Tahr", "Himalayan Monal",
        "Himalayan Griffon", "Red Panda", "Wild Yak", "Bearded Vulture",
        "Himalayan Snow Leopard", "Tibetan Brown Bear",
    ],
}


# ─────────────────────────────────────────────
# ANIMALS
# ─────────────────────────────────────────────

ANIMAL_DATA = {
    # Village (2026-09-13 modest early-game bump, ~2.5x)
    "Rat":              {"value":     75, "xp": 9,   "rarity": "common",    "emoji": ""},
    "Mouse":            {"value":     60, "xp": 7,   "rarity": "common",    "emoji": ""},
    "Stray Cat":        {"value":    150, "xp": 18,  "rarity": "uncommon",  "emoji": ""},
    "Pigeon":           {"value":     50, "xp": 6,   "rarity": "common",    "emoji": ""},
    "Crow":             {"value":     90, "xp": 10,  "rarity": "common",    "emoji": ""},
    "Rabbit":           {"value":    200, "xp": 24,  "rarity": "uncommon",  "emoji": ""},
    "Fox":              {"value":    300, "xp": 36,  "rarity": "rare",      "emoji": ""},
    "Stray Dog":        {"value":    140, "xp": 16,  "rarity": "common",    "emoji": ""},
    "Squirrel":         {"value":    100, "xp": 12,  "rarity": "common",    "emoji": ""},
    "Sparrow":          {"value":     45, "xp": 5,   "rarity": "common",    "emoji": ""},
    # Forest (2026-09-13 modest early-game bump, ~1.8x)
    "Deer":             {"value":    270, "xp": 45,  "rarity": "common",    "emoji": ""},
    "Wild Boar":        {"value":    325, "xp": 54,  "rarity": "common",    "emoji": ""},
    "Wolf":             {"value":    540, "xp": 90,  "rarity": "uncommon",  "emoji": ""},
    "Bear":             {"value":    720, "xp": 120, "rarity": "rare",      "emoji": ""},
    "Elk":              {"value":    360, "xp": 60,  "rarity": "common",    "emoji": ""},
    "Lynx":             {"value":    630, "xp": 105, "rarity": "rare",      "emoji": ""},
    "Badger":           {"value":    235, "xp": 39,  "rarity": "common",    "emoji": ""},
    "Pheasant":         {"value":    200, "xp": 33,  "rarity": "common",    "emoji": ""},
    "Owl":              {"value":    400, "xp": 66,  "rarity": "uncommon",  "emoji": ""},
    "Hare":             {"value":    160, "xp": 27,  "rarity": "common",    "emoji": ""},
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

    # ═══════════════════════════════════════════════════════════════════
    # EARTH ROSTERS — region-appropriate wildlife for the re-themed biomes.
    # (The blocks above are retired but kept so old saves still price.)
    # ═══════════════════════════════════════════════════════════════════
    # Pacific Northwest · village (2026-09-15 modest bump, ~2.5x — the actual
    # roster BIOME_ANIMALS["village"] draws from; the "retired" generic-named
    # block far above was never hit by real hunts, so an earlier pass at
    # this same rebalance landed on dead entries and had zero live effect)
    "House Sparrow":        {"value":     45, "xp": 5,   "rarity": "common",    "emoji": "🐦"},
    "American Crow":        {"value":     90, "xp": 10,  "rarity": "common",    "emoji": "🐦‍⬛"},
    "Douglas Squirrel":     {"value":    100, "xp": 12,  "rarity": "common",    "emoji": "🐿️"},
    "Cottontail Rabbit":    {"value":    140, "xp": 16,  "rarity": "common",    "emoji": "🐇"},
    "Virginia Opossum":     {"value":    120, "xp": 14,  "rarity": "common",    "emoji": "🐀"},
    "Striped Skunk":        {"value":    165, "xp": 19,  "rarity": "common",    "emoji": "🦨"},
    "Common Raccoon":       {"value":    215, "xp": 25,  "rarity": "uncommon",  "emoji": "🦝"},
    "Black-Tailed Deer":    {"value":    250, "xp": 30,  "rarity": "common",    "emoji": "🦌"},
    "Red Fox":              {"value":    290, "xp": 34,  "rarity": "uncommon",  "emoji": "🦊"},
    "Western Coyote":       {"value":    325, "xp": 39,  "rarity": "rare",      "emoji": "🐺"},
    # The British Isles · forest (2026-09-15 modest bump, ~1.8x)
    "European Hare":        {"value":    160, "xp": 27,  "rarity": "common",    "emoji": "🐇"},
    "Ring-Necked Pheasant": {"value":    200, "xp": 33,  "rarity": "common",    "emoji": "🐓"},
    "Eurasian Badger":      {"value":    245, "xp": 40,  "rarity": "common",    "emoji": "🦡"},
    "Red Deer":             {"value":    290, "xp": 48,  "rarity": "common",    "emoji": "🦌"},
    "Eurasian Boar":        {"value":    335, "xp": 55,  "rarity": "common",    "emoji": "🐗"},
    "Roe Deer":             {"value":    360, "xp": 60,  "rarity": "common",    "emoji": "🦌"},
    "Tawny Owl":            {"value":    415, "xp": 69,  "rarity": "uncommon",  "emoji": "🦉"},
    "Red Kite":             {"value":    505, "xp": 84,  "rarity": "uncommon",  "emoji": "🦅"},
    "British Grey Wolf":    {"value":    610, "xp": 102, "rarity": "rare",      "emoji": "🐺"},
    "Eurasian Lynx":        {"value":    720, "xp": 120, "rarity": "rare",      "emoji": "🐆"},
    # Scandinavia · woods
    "Capercaillie":         {"value":    210, "xp": 63,  "rarity": "common",    "emoji": "🐓"},
    "Willow Ptarmigan":     {"value":    240, "xp": 72,  "rarity": "common",    "emoji": "🐦"},
    "Nordic Red Squirrel":  {"value":    220, "xp": 66,  "rarity": "common",    "emoji": "🐿️"},
    "Mountain Reindeer":    {"value":    300, "xp": 90,  "rarity": "common",    "emoji": "🦌"},
    "Pine Marten":          {"value":    400, "xp": 120, "rarity": "uncommon",  "emoji": "🦦"},
    "Eurasian Elk":         {"value":    520, "xp": 156, "rarity": "uncommon",  "emoji": "🫎"},
    "Scandinavian Wolf":    {"value":    380, "xp": 114, "rarity": "uncommon",  "emoji": "🐺"},
    "Nordic Wolverine":     {"value":    460, "xp": 138, "rarity": "uncommon",  "emoji": "🦡"},
    "Boreal Lynx":          {"value":    430, "xp": 129, "rarity": "rare",      "emoji": "🐆"},
    "Nordic Brown Bear":    {"value":    600, "xp": 180, "rarity": "rare",      "emoji": "🐻"},
    # Egypt & the Sahara · small_desert
    "Desert Jerboa":        {"value":    400, "xp": 120, "rarity": "common",    "emoji": "🐭"},
    "Rüppell's Fox":        {"value":    460, "xp": 138, "rarity": "common",    "emoji": "🦊"},
    "Sand Cat":             {"value":    560, "xp": 168, "rarity": "uncommon",  "emoji": "🐈"},
    "Deathstalker Scorpion":{"value":    520, "xp": 156, "rarity": "common",    "emoji": "🦂"},
    "Saharan Horned Viper": {"value":    640, "xp": 192, "rarity": "uncommon",  "emoji": "🐍"},
    "Egyptian Vulture":     {"value":    600, "xp": 180, "rarity": "common",    "emoji": "🦅"},
    "Dorcas Gazelle":       {"value":    560, "xp": 168, "rarity": "common",    "emoji": "🦌"},
    "Desert Monitor":       {"value":    720, "xp": 216, "rarity": "uncommon",  "emoji": "🦎"},
    "Addax Antelope":       {"value":    680, "xp": 204, "rarity": "uncommon",  "emoji": "🦌"},
    "Striped Hyena":        {"value":    800, "xp": 240, "rarity": "rare",      "emoji": "🐺"},
    # The North Atlantic (Sunken Coast) · sunken_coast — WATER
    "Atlantic Herring":     {"value":    700, "xp": 210, "rarity": "common",    "emoji": "🐟"},
    "Harbor Seal":          {"value":    900, "xp": 270, "rarity": "common",    "emoji": "🦭"},
    "Atlantic Cod":         {"value":    820, "xp": 246, "rarity": "common",    "emoji": "🐟"},
    "Blue Lobster":         {"value":  1_100, "xp": 330, "rarity": "uncommon",  "emoji": "🦞"},
    "Striped Bass":         {"value":  1_000, "xp": 300, "rarity": "common",    "emoji": "🐟"},
    "Harbor Porpoise":      {"value":  1_300, "xp": 390, "rarity": "uncommon",  "emoji": "🐬"},
    "Atlantic Bluefin Tuna":{"value":  1_600, "xp": 480, "rarity": "rare",      "emoji": "🐟"},
    "Blue Shark":           {"value":  1_400, "xp": 420, "rarity": "uncommon",  "emoji": "🦈"},
    "Leatherback Turtle":   {"value":  1_500, "xp": 450, "rarity": "rare",      "emoji": "🐢"},
    "North Atlantic Humpback":{"value":2_000, "xp": 600, "rarity": "epic",      "emoji": "🐋"},
    # The Carpathians · tundra
    "Alpine Marmot":        {"value":    900, "xp": 270, "rarity": "common",    "emoji": "🐿️"},
    "Black Grouse":         {"value":  1_000, "xp": 300, "rarity": "common",    "emoji": "🐓"},
    "Carpathian Red Deer":  {"value":  1_200, "xp": 360, "rarity": "common",    "emoji": "🦌"},
    "Carpathian Boar":      {"value":  1_100, "xp": 330, "rarity": "common",    "emoji": "🐗"},
    "Carpathian Lynx":      {"value":  1_600, "xp": 480, "rarity": "rare",      "emoji": "🐆"},
    "Carpathian Wolf":      {"value":  1_500, "xp": 450, "rarity": "uncommon",  "emoji": "🐺"},
    "Carpathian Bear":      {"value":  2_000, "xp": 600, "rarity": "rare",      "emoji": "🐻"},
    "European Bison":       {"value":  2_500, "xp": 750, "rarity": "epic",      "emoji": "🦬"},
    "Golden Jackal":        {"value":  1_000, "xp": 300, "rarity": "common",    "emoji": "🐺"},
    "Ural Owl":             {"value":  1_300, "xp": 390, "rarity": "uncommon",  "emoji": "🦉"},
    # Southeast Asia & Japan · jungle
    "Crab-Eating Macaque":  {"value":  1_200, "xp": 360, "rarity": "common",    "emoji": "🐒"},
    "Reticulated Python":   {"value":  2_000, "xp": 600, "rarity": "rare",      "emoji": "🐍"},
    "Malayan Tapir":        {"value":  1_800, "xp": 540, "rarity": "uncommon",  "emoji": "🐖"},
    "Sun Bear":             {"value":  2_200, "xp": 660, "rarity": "rare",      "emoji": "🐻"},
    "Clouded Leopard":      {"value":  2_800, "xp": 840, "rarity": "rare",      "emoji": "🐆"},
    "Japanese Serow":       {"value":  1_500, "xp": 450, "rarity": "common",    "emoji": "🐐"},
    "King Cobra":           {"value":  2_400, "xp": 720, "rarity": "rare",      "emoji": "🐍"},
    "Bornean Orangutan":    {"value":  3_200, "xp": 960, "rarity": "epic",      "emoji": "🦧"},
    "Sunda Pangolin":       {"value":  1_600, "xp": 480, "rarity": "uncommon",  "emoji": "🦔"},
    "Indochinese Tiger":    {"value":  3_500, "xp": 1050, "rarity": "epic",     "emoji": "🐅"},
    # The Australian Outback · swamp
    "Red Kangaroo":         {"value":  1_600, "xp": 480, "rarity": "common",    "emoji": "🦘"},
    "Emu":                  {"value":  1_800, "xp": 540, "rarity": "common",    "emoji": "🦤"},
    "Dingo":                {"value":  2_200, "xp": 660, "rarity": "uncommon",  "emoji": "🐕"},
    "Frilled Lizard":       {"value":  1_500, "xp": 450, "rarity": "common",    "emoji": "🦎"},
    "Saltwater Crocodile":  {"value":  4_500, "xp": 1350, "rarity": "epic",     "emoji": "🐊"},
    "Perentie":             {"value":  2_800, "xp": 840, "rarity": "rare",      "emoji": "🦎"},
    "Southern Cassowary":   {"value":  3_500, "xp": 1050, "rarity": "rare",     "emoji": "🦤"},
    "Wedge-Tailed Eagle":   {"value":  3_000, "xp": 900, "rarity": "rare",      "emoji": "🦅"},
    "Common Wombat":        {"value":  2_000, "xp": 600, "rarity": "uncommon",  "emoji": "🦡"},
    "Inland Taipan":        {"value":  6_000, "xp": 1800, "rarity": "legendary","emoji": "🐍"},
    # Anatolia, Turkey · volcanic_highlands   (values ×0.9 — 2026-09-07 economy pass)
    "Anatolian Ground Squirrel":{"value":  3_150, "xp": 945, "rarity": "common",    "emoji": "🐿️"},
    "Chukar Partridge":     {"value":  3_420, "xp": 1026, "rarity": "common",    "emoji": "🐦"},
    "Bezoar Ibex":          {"value":  4_050, "xp": 1215, "rarity": "uncommon",  "emoji": "🐐"},
    "Anatolian Leopard":    {"value":  6_300, "xp": 1890, "rarity": "epic",      "emoji": "🐆"},
    "Anatolian Wolf":       {"value":  4_500, "xp": 1350, "rarity": "rare",      "emoji": "🐺"},
    "Anatolian Hyena":      {"value":  4_320, "xp": 1296, "rarity": "uncommon",  "emoji": "🐺"},
    "Caracal":              {"value":  4_950, "xp": 1485, "rarity": "rare",      "emoji": "🐈"},
    "Syrian Brown Bear":    {"value":  5_850, "xp": 1755, "rarity": "epic",      "emoji": "🐻"},
    "Griffon Vulture":      {"value":  4_680, "xp": 1404, "rarity": "rare",      "emoji": "🦅"},
    "Anatolian Golden Eagle":{"value": 7_200, "xp": 2160, "rarity": "legendary", "emoji": "🦅"},
    # Ancient Greece · cursed_ruins   (values ×0.8 — 2026-09-07 economy pass)
    "Kri-Kri Goat":         {"value":  4_000, "xp": 1200, "rarity": "common",    "emoji": "🐐"},
    "Hermann's Tortoise":   {"value":  4_400, "xp": 1320, "rarity": "common",    "emoji": "🐢"},
    "Grecian Jackal":       {"value":  4_800, "xp": 1440, "rarity": "uncommon",  "emoji": "🐺"},
    "Grecian Boar":         {"value":  5_600, "xp": 1680, "rarity": "uncommon",  "emoji": "🐗"},
    "Balkan Lynx":          {"value":  9_600, "xp": 2880, "rarity": "epic",      "emoji": "🐆"},
    "Grecian Wolf":         {"value":  7_200, "xp": 2160, "rarity": "rare",      "emoji": "🐺"},
    "Pindos Bear":          {"value":  8_800, "xp": 2640, "rarity": "epic",      "emoji": "🐻"},
    "Aegean Vulture":       {"value":  6_400, "xp": 1920, "rarity": "rare",      "emoji": "🦅"},
    "Mediterranean Monk Seal":{"value": 8_000,"xp": 2400, "rarity": "rare",      "emoji": "🦭"},
    "Olympian Eagle":       {"value": 12_000, "xp": 3600, "rarity": "legendary", "emoji": "🦅"},
    # The Caribbean · rainbow   (values ×0.7 — 2026-09-07 economy pass)
    "Scarlet Ibis":         {"value":  8_400, "xp": 2520, "rarity": "rare",      "emoji": "🦩"},
    "Green Iguana":         {"value":  9_100, "xp": 2730, "rarity": "rare",      "emoji": "🦎"},
    "Caribbean Flamingo":   {"value":  9_800, "xp": 2940, "rarity": "rare",      "emoji": "🦩"},
    "Hawksbill Turtle":     {"value": 12_600, "xp": 3780, "rarity": "epic",      "emoji": "🐢"},
    "Jamaican Boa":         {"value": 11_200, "xp": 3360, "rarity": "rare",      "emoji": "🐍"},
    "West Indian Manatee":  {"value": 15_400, "xp": 4620, "rarity": "epic",      "emoji": "🦭"},
    "Cuban Crocodile":      {"value": 17_500, "xp": 5250, "rarity": "legendary", "emoji": "🐊"},
    "Caribbean Reef Shark": {"value": 14_000, "xp": 4200, "rarity": "epic",      "emoji": "🦈"},
    "Queen Conch":          {"value": 10_500, "xp": 3150, "rarity": "rare",      "emoji": "🐚"},
    "Blue Marlin":          {"value": 35_000, "xp": 10500, "rarity": "legendary","emoji": "🐟"},
    # The Mediterranean Deep · abyssal_depths   (values ×0.7 — 2026-09-07 economy pass)
    "Lanternfish":          {"value": 10_500, "xp": 3150, "rarity": "rare",      "emoji": "🐟"},
    "Blackmouth Catshark":  {"value": 12_600, "xp": 3780, "rarity": "rare",      "emoji": "🦈"},
    "Giant Red Shrimp":     {"value": 11_200, "xp": 3360, "rarity": "rare",      "emoji": "🦐"},
    "Deep-Sea Anglerfish":  {"value": 15_400, "xp": 4620, "rarity": "epic",      "emoji": "🐡"},
    "Gulper Eel":           {"value": 16_800, "xp": 5040, "rarity": "epic",      "emoji": "🐍"},
    "Mediterranean Sperm Whale":{"value":24_500,"xp": 7350,"rarity":"legendary", "emoji": "🐋"},
    "Giant Squid":          {"value": 28_000, "xp": 8400, "rarity": "legendary","emoji": "🦑"},
    "Bluntnose Sixgill Shark":{"value":19_600,"xp": 5880, "rarity": "epic",      "emoji": "🦈"},
    "Common Fangtooth":     {"value": 14_000, "xp": 4200, "rarity": "epic",      "emoji": "🐡"},
    "Colossal Squid":       {"value": 35_000, "xp": 10500, "rarity": "legendary","emoji": "🦑"},
    # Roof of the World — the Himalayas · celestial_peaks   (values ×0.5 — 2026-09-07 economy pass)
    "Himalayan Marmot":     {"value": 17_500, "xp": 5250, "rarity": "rare",     "emoji": "🐿️"},
    "Bharal":               {"value": 20_000, "xp": 6000, "rarity": "rare",     "emoji": "🐐"},
    "Himalayan Tahr":       {"value": 22_500, "xp": 6750, "rarity": "epic",     "emoji": "🐐"},
    "Himalayan Monal":      {"value": 21_000, "xp": 6300, "rarity": "epic",     "emoji": "🦚"},
    "Himalayan Griffon":    {"value": 25_000, "xp": 7500, "rarity": "epic",     "emoji": "🦅"},
    "Red Panda":            {"value": 24_000, "xp": 7200, "rarity": "epic",     "emoji": "🐼"},
    "Wild Yak":             {"value": 30_000, "xp": 9000, "rarity": "legendary","emoji": "🐂"},
    "Bearded Vulture":      {"value": 27_500, "xp": 8250, "rarity": "legendary","emoji": "🦅"},
    "Himalayan Snow Leopard":{"value":45_000, "xp": 13500, "rarity": "legendary","emoji": "🐆"},
    "Tibetan Brown Bear":   {"value": 75_000, "xp": 22500, "rarity": "legendary","emoji": "🐻"},
}

# Fallback icon for any animal whose own "emoji" is blank (currently all of them),
# so inventory / profile / record lines don't render a gap where an icon belongs.
ANIMAL_EMOJI = EMOJI["animal_fallback"]


# ─────────────────────────────────────────────
# EMOJIS / ICONS
# ─────────────────────────────────────────────

# All built from the EMOJI registry at the top of this file — edit ids there.
UPGRADE_EMOJI = EMOJI["upgrade"]

RARITY_KEYS = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
RARITY_ICONS = {r: EMOJI[f"rarity_{r}"] for r in RARITY_KEYS}
# A "shard" is just the rarity icon; a "crystal" has its own art.
SHARD_ICONS   = dict(RARITY_ICONS)
CRYSTAL_ICONS = {r: EMOJI[f"crystal_{r}"] for r in RARITY_KEYS}

TRIBE_EMOJIS = {
    "members":  EMOJI["tribe_members"], "kick":     EMOJI["tribe_kick"],
    "invite":   EMOJI["tribe_invite"],  "ban":      EMOJI["tribe_ban"],
    "leave":    EMOJI["tribe_leave"],   "leader":   EMOJI["tribe_leader"],
    "officer":  EMOJI["tribe_officer"], "tribe":    EMOJI["tribe"],
    "demote":   EMOJI["tribe_demote"],  "set_desc": EMOJI["tribe_set_desc"],
    "xp":       EMOJI["xp"],            "levels":   EMOJI["levels"],
    "sell_boost": EMOJI["sell_boost"],  "xp_boost": EMOJI["xp_boost"],
    "luck_boost": EMOJI["luck_boost"],  "stats":    EMOJI["stats"],
    "luck":     EMOJI["luck"],
}

USER_EMOJIS = {
    "profile":  EMOJI["profile"],   "stats":      EMOJI["stats"],
    "xp":       EMOJI["xp"],        "levels":     EMOJI["levels"],
    "sell_boost": EMOJI["sell_boost"], "xp_boost": EMOJI["xp_boost"],
    "luck_boost": EMOJI["luck_boost"], "luck":     EMOJI["luck"],
    "biome":    EMOJI["biome"],     "cooldown":   EMOJI["cooldown"],
    "level_up": EMOJI["level_up"],
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
        "tier": 100, "price": 25_000, "currency": "gems",
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
    "sunken_coast":        5,
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
# BIOMES ON EARTH  ·  location + world-map position
# ─────────────────────────────────────────────
# Biomes keep their fantasy names; each is also a real place on Earth.
# map_x is 0–100, left→right on the world map, and drives travel time
# (opposite edges ≈ TRAVEL_MAX_MIN apart). map_image is a hosted URL,
# empty until the art is uploaded.  WORLD_MAP_URL is the overview image.
#
# WORLD_MAP_URL is only a seed: app.py keeps a fresh copy at runtime (the
# Discord CDN signature expires) via the /attachments/refresh-urls endpoint
# and persists it in runtime_state.json — see world_map_url() there.

WORLD_MAP_URL = "https://cdn.discordapp.com/attachments/1505452596834467850/1546352341635039262/world_map.png?ex=6a9f7858&is=6a9e26d8&hm=8b111466048d8655881cdc959377a45b8cae8fc56914c75173d0587394767003"

BIOME_REGION = {
    "village":            {"region": "The Pacific Northwest",  "continent": "North America", "map_x":  6, "map_image": ""},
    "forest":             {"region": "The British Isles",      "continent": "Europe",        "map_x": 43, "map_image": ""},
    "woods":              {"region": "Scandinavia",            "continent": "Europe",        "map_x": 50, "map_image": ""},
    "small_desert":       {"region": "Egypt & the Sahara",     "continent": "Africa",        "map_x": 54, "map_image": ""},
    "sunken_coast":       {"region": "The North Atlantic",     "continent": "Atlantic Ocean","map_x": 27, "map_image": ""},
    "tundra":             {"region": "The Transylvanian Alps",       "continent": "Europe",        "map_x": 57, "map_image": ""},
    "jungle":             {"region": "Southeast Asia & Japan",       "continent": "Asia",          "map_x": 85, "map_image": ""},
    "swamp":              {"region": "Southeast Australian Wetlands", "continent": "Oceania",       "map_x": 92, "map_image": ""},
    "volcanic_highlands": {"region": "Anatolia",               "continent": "Asia",          "map_x": 58, "map_image": ""},
    "cursed_ruins":       {"region": "Ancient Greece",         "continent": "Europe",        "map_x": 55, "map_image": ""},
    "rainbow":            {"region": "The Caribbean",          "continent": "North America", "map_x": 20, "map_image": ""},
    "abyssal_depths":     {"region": "The Mediterranean Deep", "continent": "Europe",        "map_x": 53, "map_image": ""},
    "celestial_peaks":    {"region": "The Himalayas",          "continent": "Asia",          "map_x": 70, "map_image": ""},
}

def biome_region(biome: str) -> dict:
    return BIOME_REGION.get(biome, {"region": BIOME_NAMES.get(biome, biome),
                                    "continent": "", "map_x": 50, "map_image": ""})

def biome_location_line(biome: str) -> str:
    r = biome_region(biome)
    tail = f", {r['continent']}" if r.get("continent") else ""
    return f"{r['region']}{tail}"


# ─────────────────────────────────────────────
# GLOBAL SIGHHTING — clue flavor
# ─────────────────────────────────────────────
# One of these is picked at random each time the tracker's clue count updates,
# so the in-progress announcement reads like an unfolding investigation
# instead of a bare counter ticking up.
SIGHTING_CLUE_FLAVORS = [
    "Massive claw marks were found beside the river.",
    "A hunter's trail camera caught only a blur and two glowing eyes.",
    "Something dragged a full-grown animal carcass a hundred yards uphill.",
    "Trees at head height show fresh gouges no known animal could leave.",
    "Local hunters report an unfamiliar call echoing after dark.",
    "A patch of undergrowth was flattened as if something enormous rested there.",
    "Footprints were found, then vanished mid-stride.",
    "Something knocked over a supply cache and left no other trace.",
    "A low growl was picked up on someone's voice memo. Nobody wants to share it.",
    "Fresh tracks circle back on themselves — whatever it is, it's watching.",
]

# ─────────────────────────────────────────────
# WORLD CONDITIONS  ·  Idle Hunter V2, Phase 6
# ─────────────────────────────────────────────
# A rotating per-region weather/wildlife state. A few biomes are "enhanced" at
# any moment (see the rotation task in app.py); the rest are Normal. Every
# multiplier defaults to 1.0 — only list the ones a condition actually changes.
# Kept deliberately small; grow it once the loop is proven.
WORLD_CONDITIONS = {
    "heavy_rain": {
        "name": "Heavy Rain", "emoji": "🌧️", "duration": 4 * 3600,
        "rare_mult": 1.15, "myth_mult": 1.05,
        "blurb": "Tracks set deep in the mud and scent hangs low. Rare wildlife is easier to close on.",
    },
    "migration": {
        "name": "Migration", "emoji": "🦌", "duration": 4 * 3600,
        "rare_mult": 1.30,
        "blurb": "The herds are moving through in numbers. Prize animals everywhere you look.",
    },
    "strange_tracks": {
        "name": "Strange Tracks", "emoji": "🐾", "duration": 3 * 3600,
        "myth_mult": 1.35,
        "blurb": "Prints that don't match anything in the guide. Something legendary is nearby.",
    },
    "trading_boom": {
        "name": "Trading Boom", "emoji": EMOJI["coin_sample"], "duration": 3 * 3600,
        "sell_mult": 1.15,
        "blurb": "Buyers are paying over the odds this week. Sell where the money is.",
    },
    "clear_skies": {
        "name": "Clear Skies", "emoji": "☀️", "duration": 3 * 3600,
        "xp_mult": 1.15,
        "blurb": "Perfect visibility and easy going. Every hunt teaches you a little more.",
    },
    "predators_stirring": {
        "name": "Predators Stirring", "emoji": "🐺", "duration": 3 * 3600,
        "myth_mult": 1.20, "rare_mult": 1.08,
        "blurb": "The big animals are restless and bold. Higher stakes, better rewards.",
    },
    "aurora": {
        "name": "Aurora", "emoji": "🌌", "duration": 3 * 3600,
        "rare_mult": 1.12, "xp_mult": 1.10,
        "blurb": "Lights in the sky and animals acting strange beneath them.",
    },
}

# How many regions carry a (non-Normal) condition at once.
WORLD_CONDITION_SLOTS = 3
# Post-world-condition hard caps so stacking luck + event + condition can't
# trivialise rarity.
MYTH_ENCOUNTER_MAX_WORLD = 0.075
RARE_CATCH_MAX_WORLD     = 0.45


# ─────────────────────────────────────────────
# TRACKING  ·  Idle Hunter V2, Phase 11-15
# ─────────────────────────────────────────────
# A mythic roll no longer drops you straight into the fight — first you TRACK the
# creature over 2-4 decisions. `risk` is the % chance the creature spooks (a
# mistake); `progress` is trail points gained on a clean choice. Two mistakes and
# it's gone. A clean track buys you an edge in the fight that follows.
TRACKING_ACTIONS = {
    "follow":  {"label": "Follow the trail", "emoji": "🐾", "risk": 12, "progress": 2},
    "observe": {"label": "Watch and wait",   "emoji": "🔭", "risk": 0,  "progress": 1},
    "flank":   {"label": "Circle around",    "emoji": "🌲", "risk": 22, "progress": 3},
    "push":    {"label": "Push hard",        "emoji": "⚡", "risk": 40, "progress": 4},
}

TRACKING_SCENES = [
    {"key": "prints",   "title": "🐾 Deep Prints",
     "text": "The tracks press deep and fresh into the ground, spaced wide. It was moving, and not long ago."},
    {"key": "branches", "title": "🌿 Broken Branches",
     "text": "Green wood snapped at shoulder height. Whatever came through was tall and in no hurry to go around."},
    {"key": "river",    "title": "🏞️ A River Crossing",
     "text": "The trail meets fast water and picks up again on the far bank. It waded straight across."},
    {"key": "blood",    "title": "🩸 A Blood Trail",
     "text": "Dark spots on the leaves — not yours, not fresh prey. Something is hurt, or something ate well."},
    {"key": "sound",    "title": "🔊 Movement Ahead",
     "text": "Brush shifts a hundred metres out. No wind. It knows the woods better than you do."},
    {"key": "camp",     "title": "⛺ A Wrecked Camp",
     "text": "A tent torn open, a cold fire, gear thrown wide. The tracks lead away from it, unbothered."},
    {"key": "feathers", "title": "🪶 Scattered Feathers",
     "text": "A kill site, picked clean and abandoned. The trail continues, heavier now."},
    {"key": "scratches","title": "🪵 Claw Marks",
     "text": "Gouges in the bark, far higher than they have any right to be. You're close."},
]

# minutes a tracking sequence stays open before it's abandoned
TRACKING_EXPIRE_MIN = 20


# ─────────────────────────────────────────────
# SHARE CARDS  ·  Idle Hunter V2, Phase 19-23
# ─────────────────────────────────────────────
# What is worth showing off in the channel. Common/uncommon never gets a Share
# button; rare only on a personal first; epic+ always.
SHARE_RARITY_MIN = ("epic", "legendary", "mythic")
SHARE_STORE_TTL  = 3600   # seconds a pending share stays claimable


# ─────────────────────────────────────────────
# REFERRALS  ·  Idle Hunter V2, Phase 35-39
# ─────────────────────────────────────────────
# A referred player only counts once they actually play: Level >= 25 AND
# 50 lifetime hunts. Rewards lean on cosmetics + a little gem — never big cash.
REFERRAL_QUALIFY_LEVEL = 25
REFERRAL_QUALIFY_HUNTS = 50
REFERRAL_QUALIFY_DAYS  = 2     # played on >= this many distinct UTC days (anti-alt)
REFERRAL_CODE_MAX_LEVEL = 20   # you can only enter a code while still this low

# gems both sides get the first time one of your referrals qualifies
REFERRAL_QUALIFY_GEMS = 60

# referrer's running total of QUALIFIED referrals -> milestone reward
REFERRAL_MILESTONES = {
    1:  {"title": "Trail Guide"},
    3:  {"badge": "recruiter", "gems": 50},
    5:  {"gems": 150},
    10: {"title": "Expedition Leader"},
    25: {"badge": "master_recruiter", "gems": 500},
}


# ─────────────────────────────────────────────
# SERVER-WIDE WEEKLY GOALS  ·  Idle Hunter V2, Phase 33-34
# ─────────────────────────────────────────────
GUILD_GOAL_PER_MEMBER  = 120     # target catches per non-bot member
GUILD_GOAL_MIN         = 1500
GUILD_GOAL_MAX         = 250_000
GUILD_GOAL_CONTRIB_MIN = 25      # personal catches needed to earn the reward


# ─────────────────────────────────────────────
# TRIBE EXPEDITIONS  ·  Idle Hunter V2, Phase 28-32
# ─────────────────────────────────────────────
# Built ON TOP of tribe XP. A leader/officer opens one; members vote a route;
# then normal play (hunts, myth kills, dailies) fills a shared progress bar.
# Rewards are tribe XP + cosmetics + a crate each — never a cash flood.
TRIBE_EXPEDITION_MIN_MEMBERS = 3
TRIBE_EXPEDITION_VOTE_MIN    = 15 * 60      # seconds before a route can be force-locked
TRIBE_EXPEDITION_COOLDOWN_H  = 18          # hours after one finishes before the next
TRIBE_EXPEDITIONS = {
    "abandoned_temple": {
        "name": "The Abandoned Temple", "emoji": "🗿", "hours": 8,
        "blurb": "A temple swallowed by jungle. Nobody who mapped it came back with the map.",
        "routes": {
            "gate":    {"label": "The Front Gate", "emoji": "🚪",
                        "desc": "Direct and defended. Steady progress, fair reward.",
                        "goal_mult": 1.00, "xp": 900, "crate": "Rare Crate",
                        "title": "Temple-Breaker"},
            "tunnels": {"label": "The Flooded Tunnels", "emoji": "🌊",
                        "desc": "Longer, nastier, richer. Best rewards if you finish.",
                        "goal_mult": 1.35, "xp": 1500, "crate": "Epic Crate",
                        "title": "Deep Delver"},
            "cliffs":  {"label": "The Cliff Path", "emoji": "🧗",
                        "desc": "Exposed and slow, but you see everything coming.",
                        "goal_mult": 1.15, "xp": 1100, "crate": "Rare Crate",
                        "badge": "recruiter"},
        },
    },
    "great_migration": {
        "name": "Follow the Great Migration", "emoji": "🦬", "hours": 6,
        "blurb": "The herds are crossing three regions. Shadow them and take what the land gives.",
        "routes": {
            "front":  {"label": "Run With the Front", "emoji": "🏃",
                       "desc": "Fast and first to everything. Standard haul.",
                       "goal_mult": 1.00, "xp": 800, "crate": "Rare Crate",
                       "title": "Herd-Runner"},
            "flank":  {"label": "Work the Flanks", "emoji": "🐺",
                       "desc": "Where the predators are — and the prizes.",
                       "goal_mult": 1.25, "xp": 1300, "crate": "Epic Crate",
                       "title": "Flankmaster"},
            "rear":   {"label": "Sweep the Rear", "emoji": "🧹",
                       "desc": "Slow going, but nothing gets past you.",
                       "goal_mult": 1.10, "xp": 1000, "crate": "Rare Crate"},
        },
    },
}
# shared-progress goal = base * members * route goal_mult
TRIBE_EXPEDITION_GOAL_PER_MEMBER = 60
# what each kind of action adds to expedition progress
TRIBE_EXPEDITION_POINTS = {"hunt": 1, "catch": 1, "myth_kill": 25, "daily": 8, "quest": 5}


# ─────────────────────────────────────────────
# MYTHICAL CREATURES  ·  the mythic tier / boss roster
# ─────────────────────────────────────────────
# These REPLACE ordinary mythic-rarity animals. They are never caught by a
# normal hunt or the idle camp — they appear only as a rare boss encounter in
# run_hunt (KILL or RUN). A kill pays the bounty + xp and drops the unique
# `drop` item; a failed kill costs the hunter 40% of their cash. They can be
# met and killed again; drops stack.
#
# Card fields mirror a field-guide entry (see /info):
#   aka · height · description · call · diet · behavior · blurb (funny one-liner)
# `fallback_emoji` shows until a custom "creature_<slug>" emoji is uploaded.

MYTHIC_CREATURES = {
    # ── The Pacific Northwest (village) ──────────────────────────
    "Bigfoot": {
        "aka": "Sasquatch", "biome": "village", "rarity": "mythic",
        "height": "6–10 ft (1.8–3 m)",
        "description": "Cone-headed, russet-furred, built like a linebacker",
        "call": "Wood-knocks and long echoing whoops",
        "diet": "Berries, roots and salmon — and coolers left unattended",
        "behavior": "Painfully shy; lobs rocks and logs when cornered",
        "blurb": "Four hundred kilos of forest recluse that has never once held still for a camera.",
        "value": 553, "xp": 415, "drop": "Matted Fur Tuft", "drop_value": 829,
        "fallback_emoji": "👣",
    },
    "Bogeyman": {
        "aka": "The Boogeyman", "biome": "village", "rarity": "mythic",
        "height": "Whatever fits under the bed",
        "description": "No fixed shape — shadow, draught, and bad intent",
        "call": "The creak of a closet door at 3 a.m.",
        "diet": "Fear, mostly; the occasional misbehaving child",
        "behavior": "Hides in the dark; gone the instant the light comes on",
        "blurb": "Legally distinct in every country, structurally identical everywhere: it's the thing in the closet.",
        "value": 553, "xp": 415, "drop": "Jar of Closet Shadow", "drop_value": 829,
        "fallback_emoji": "🕴️",
    },
    # ── The British Isles (forest) ──────────────────────────────
    "Black Dog": {
        "aka": "Black Shuck", "biome": "forest", "rarity": "mythic",
        "height": "Calf-sized, pony-sized on a bad night",
        "description": "Shaggy black hound with a single saucer eye of fire",
        "call": "Padding footsteps with no dog attached",
        "diet": "Doesn't seem to need to eat — which is worse",
        "behavior": "Haunts lonely roads and churchyards; to see it is a death omen",
        "blurb": "England's least reassuring stray. Do not whistle for it.",
        "value": 1704, "xp": 1278, "drop": "Ember-Eye Coal", "drop_value": 2556,
        "fallback_emoji": "🐕‍🦺",
    },
    "Grindylow": {
        "aka": "The Bog Bogie", "biome": "forest", "rarity": "mythic",
        "height": "Child-sized and horribly long-armed",
        "description": "Green, scaly, clawed, with fingers that go on forever",
        "call": "A gurgle from just under the surface",
        "diet": "Anything that leans too far over the water — children preferred",
        "behavior": "Cannot leave its pond; its reach is exactly the length of its arms",
        "blurb": "Yorkshire's reason not to play near the fen. Still works on kids today.",
        "value": 1704, "xp": 1278, "drop": "Webbed Claw", "drop_value": 2556,
        "fallback_emoji": "🫳",
    },
    "Loch Ness Monster": {
        "aka": "Nessie", "biome": "forest", "rarity": "mythic",
        "height": "20–40 ft, long-necked",
        "description": "Small head, long neck, humped back — a plesiosaur that missed the memo",
        "call": "A ripple, a wake, and nothing else",
        "diet": "Salmon, presumably; nobody has watched it eat",
        "behavior": "Surfaces for a photo just blurry enough, then gone for a decade",
        "blurb": "Scotland's most bankable tourist. Employed since 1933, never once clocked in properly.",
        "value": 1704, "xp": 1278, "drop": "Loch Silt Sample", "drop_value": 2556,
        "fallback_emoji": "🦕",
    },
    "Kelpie": {
        "aka": "The Water Horse", "biome": "forest", "rarity": "mythic",
        "height": "A tall, handsome black stallion",
        "description": "A perfect pony by the riverbank — weeds in its mane, hide like glue",
        "call": "A whinny that carries too far",
        "diet": "Riders — it drowns them and keeps what's left",
        "behavior": "Offers a ride; once you're on, you cannot get off",
        "blurb": "Scotland's warning about accepting lifts from strangers, even four-legged ones.",
        "value": 1704, "xp": 1278, "drop": "Dripping Bridle", "drop_value": 2556,
        "fallback_emoji": "🐎",
    },
    # ── Scandinavia (woods) ────────────────────────────────────
    "Troll": {
        "aka": "The Rock-Dweller", "biome": "woods", "rarity": "mythic",
        "height": "8–20 ft of lumpy granite",
        "description": "Big, ugly, mossy, with a nose you could hang a coat on",
        "call": "A slow booming grumble",
        "diet": "Goats, travellers, the odd lost knight",
        "behavior": "Guards bridges and caves; loses track of time and turns to stone at sunrise",
        "blurb": "Scandinavia's original bridge toll. Slow, strong, and allergic to dawn.",
        "value": 3008, "xp": 2256, "drop": "Petrified Troll Nose", "drop_value": 4512,
        "fallback_emoji": "🗿",
    },
    "Garm": {
        "aka": "The Hound of Hel", "biome": "woods", "rarity": "mythic",
        "height": "Bear-sized, blood-caked",
        "description": "A monstrous hound, chest matted red, chained at a cave mouth",
        "call": "A baying that means the world is ending",
        "diet": "The dead — and anyone who arrives early",
        "behavior": "Bound at Gnipahellir until Ragnarök, then slips the chain and takes a god with it",
        "blurb": "Norse mythology's guard dog. Fights the god of war to a double knockout, on schedule.",
        "value": 3008, "xp": 2256, "drop": "Broken Hel-Chain Link", "drop_value": 4512,
        "fallback_emoji": "🐺",
    },
    # ── Egypt & the Sahara (small_desert) ──────────────────────
    "Ammut": {
        "aka": "Devourer of the Dead", "biome": "small_desert", "rarity": "mythic",
        "height": "Lion-shouldered, hippo-hipped",
        "description": "Crocodile head, lion forequarters, hippo hindquarters — Egypt's three worst bites on one body",
        "call": "The click of the scales tipping",
        "diet": "The hearts of the unworthy, weighed and found wanting",
        "behavior": "Waits by the scales of Ma'at; never hunts — the guilty are brought to her",
        "blurb": "Ancient Egypt's answer to 'what if the afterlife had a woodchipper.'",
        "value": 4752, "xp": 3564, "drop": "Weighing-Scale Feather", "drop_value": 7128,
        "fallback_emoji": "🐊",
    },
    "Roc": {
        "aka": "The Elephant Bird", "biome": "small_desert", "rarity": "mythic",
        "height": "Wingspan measured in ships",
        "description": "A bird of prey so large it blots the sun; talons like grapnels",
        "call": "A scream heard a valley away",
        "diet": "Elephants, carried off two at a time to feed the chicks",
        "behavior": "Nests on desert crags; dive-bombs anything snack-sized, i.e. you",
        "blurb": "Sinbad's ride, Marco Polo's tall tale, and the reason you don't picnic in the open.",
        "value": 4752, "xp": 3564, "drop": "Grapnel Talon", "drop_value": 7128,
        "fallback_emoji": "🦅",
    },
    # ── The North Atlantic — Sunken Coast (sunken_coast) ───────
    "Sea Serpent of Cape Ann": {
        "aka": "The Gloucester Serpent", "biome": "sunken_coast", "rarity": "mythic",
        "height": "60–100 ft, thick as a barrel",
        "description": "Dark humped coils like a string of buoys; a horse-like head held high",
        "call": "The slap of coils on a flat sea",
        "diet": "Herring and mackerel, whole schools at a gulp",
        "behavior": "Surfaces in summer, tolerates crowds of gawkers, dives without warning",
        "blurb": "Seen every day off Gloucester in August 1817. The town has awaited a rematch ever since.",
        "value": 9856, "xp": 7392, "drop": "Barrel-Thick Scale", "drop_value": 14784,
        "fallback_emoji": "🐍",
    },
    "Kraken": {
        "aka": "The Island-That-Isn't", "biome": "sunken_coast", "rarity": "mythic",
        "height": "A mile of arms, they say",
        "description": "A cephalopod the size of a headland; its back mistaken for an island",
        "call": "A groan felt in the hull before it's heard",
        "diet": "Whales, ships, entire crews",
        "behavior": "Rises to feed, then sinks — and the whirlpool it leaves finishes the job",
        "blurb": "Norwegian sailors' worst day at the office, scaled up until it stopped being funny.",
        "value": 9856, "xp": 7392, "drop": "Kraken Ink Vial", "drop_value": 14784,
        "fallback_emoji": "🦑",
    },
    # ── The Carpathians (tundra) ──────────────────────────────
    "Vampires": {
        "aka": "The Nosferatu", "biome": "tundra", "rarity": "mythic",
        "height": "Human, unnaturally still",
        "description": "Pale, cold, immaculate, with a smile that shows too much tooth",
        "call": "No footsteps, no reflection, no warning",
        "diet": "Blood, fresh, from the neck",
        "behavior": "Sleeps by day in its own soil; charming until it isn't; hates garlic, mirrors and stakes",
        "blurb": "Transylvania's most successful export. Undead, well-dressed, still doing dinner parties.",
        "value": 11280, "xp": 8460, "drop": "Coffin Nail", "drop_value": 16920,
        "fallback_emoji": "🧛",
    },
    "Werewolf": {
        "aka": "The Lycanthrope", "biome": "tundra", "rarity": "mythic",
        "height": "7 ft on the hind legs",
        "description": "A man-shaped wolf, or a wolf-shaped man, depending on the moon",
        "call": "A howl that starts human and doesn't finish that way",
        "diet": "Livestock, then people, then regret in the morning",
        "behavior": "Transforms at the full moon, keeps no memory; only silver stops it",
        "blurb": "Russia's countryside problem three nights a month. The other 27, he's fine, probably.",
        "value": 11280, "xp": 8460, "drop": "Silver-Burned Fang", "drop_value": 16920,
        "fallback_emoji": "🐺",
    },
    # ── Southeast Asia & Japan (jungle) ───────────────────────
    "Manticore": {
        "aka": "The Man-Eater", "biome": "jungle", "rarity": "mythic",
        "height": "Lion-sized, tail extra",
        "description": "A blood-red lion's body, a man's face with three rows of teeth, a scorpion tail that fires spines",
        "call": "A voice like a trumpet crossed with a pan-pipe",
        "diet": "People, whole — it leaves no bones, no clothes, nothing",
        "behavior": "Stalks jungle trails; looses a volley of tail-spines, then closes in",
        "blurb": "The Persian bestiary's overachiever: it eats the evidence.",
        "value": 17760, "xp": 13320, "drop": "Barbed Tail-Spine", "drop_value": 26640,
        "fallback_emoji": "🦂",
    },
    "Nue": {
        "aka": "The Night Chimera", "biome": "jungle", "rarity": "mythic",
        "height": "Small, wrong in every proportion",
        "description": "A monkey's face, a tanuki's body, a tiger's legs and a snake for a tail",
        "call": "An eerie 'hyoo-hyoo' whistle like a scaly thrush",
        "diet": "Bad dreams and the health of emperors",
        "behavior": "Arrives as a black cloud over the palace at night; brings sickness and dread until shot down",
        "blurb": "The Tale of the Heike's boss fight. Ugly, unlucky, and gone by morning.",
        "value": 17760, "xp": 13320, "drop": "Black-Cloud Wisp", "drop_value": 26640,
        "fallback_emoji": "🐒",
    },
    # ── The Australian Outback (swamp) ────────────────────────
    "Bunyip": {
        "aka": "The Waterhole Devil", "biome": "swamp", "rarity": "mythic",
        "height": "Seal-to-bullock, depending who ran",
        "description": "Shaggy or scaled, with flippers, tusks, sometimes a dog's face, sometimes horns",
        "call": "A booming roar rolling out of the billabong at night",
        "diet": "Anything that comes to the water to drink",
        "behavior": "Lurks in swamps, creeks and waterholes; drags prey under",
        "blurb": "Aboriginal Australia's very good reason not to camp by that particular billabong.",
        "value": 23120, "xp": 17340, "drop": "Billabong Tusk", "drop_value": 34680,
        "fallback_emoji": "🦭",
    },
    "Yowie": {
        "aka": "The Great Hairy Man", "biome": "swamp", "rarity": "mythic",
        "height": "5 ft, or a towering 10 ft — two sizes reported",
        "description": "Ape-shaped, black or brown fur, big fangs, and a smell that arrives first",
        "call": "A guttural roar and heavy footfalls in the scrub",
        "diet": "Roots, fruit and small game; raids camps for the rest",
        "behavior": "Shadows bushwalkers, keeps to ridgelines and thick timber, melts away when watched",
        "blurb": "Australia's Bigfoot, with worse PR and better camouflage.",
        "value": 23120, "xp": 17340, "drop": "Coarse Yowie Hair", "drop_value": 34680,
        "fallback_emoji": "🦧",
    },
    # ── Anatolia (volcanic_highlands) ─────────────────────────
    "Chimera": {
        "aka": "The Lycian Terror", "biome": "volcanic_highlands", "rarity": "mythic",
        "height": "Lion-sized and then some",
        "description": "A lion in front, a goat rising from the spine, a live serpent for a tail — all breathing fire",
        "call": "Three throats, one roar",
        "diet": "Livestock and villages, scorched then eaten",
        "behavior": "Ravages the highlands from the air; brought down only from horseback, from above",
        "blurb": "The monster so strange its name became the word for 'monster made of other monsters.'",
        "value": 38736, "xp": 29052, "drop": "Fire-Gland Sac", "drop_value": 58104,
        "fallback_emoji": "🦁",
    },
    "Cockatrice": {
        "aka": "The Basilisk's Cousin", "biome": "volcanic_highlands", "rarity": "mythic",
        "height": "Rooster-sized, all attitude",
        "description": "A cockerel's body, a dragon's tail, and a stare that kills",
        "call": "A crow that is the last thing you hear",
        "diet": "Small game; mostly it kills for the room",
        "behavior": "Hatched from a cock's egg; slays with a glance or a touch; a weasel or a cock's crow undoes it",
        "blurb": "Medieval Europe's proof that you should never let a rooster near an egg.",
        "value": 38736, "xp": 29052, "drop": "Petrifying Eye", "drop_value": 58104,
        "fallback_emoji": "🐓",
    },
    # ── Ancient Greece (cursed_ruins) ─────────────────────────
    "Minotaur": {
        "aka": "The Bull of Minos", "biome": "cursed_ruins", "rarity": "mythic",
        "height": "7 ft, all shoulders",
        "description": "A man's body under a bull's head, and a temper to match",
        "call": "A bellow that echoes down stone corridors",
        "diet": "Athenian tribute, seven youths and seven maidens at a time",
        "behavior": "Prowls the Labyrinth; cannot find its own way out, and neither can you",
        "blurb": "Crete's home-improvement disaster: they built a maze so good the monster got lost in it too.",
        "value": 56640, "xp": 42480, "drop": "Bronze Nose-Ring", "drop_value": 84960,
        "fallback_emoji": "🐂",
    },
    "Hydra": {
        "aka": "The Lernaean Serpent", "biome": "cursed_ruins", "rarity": "mythic",
        "height": "Nine heads on nine necks, low and wide",
        "description": "A swamp serpent whose stumps sprout two heads for every one you take",
        "call": "Nine hisses, slightly out of sync",
        "diet": "Cattle, travellers, whole search parties",
        "behavior": "Guards the spring at Lerna; cut a head, get two back; only fire seals the stump",
        "blurb": "The reason 'just deal with it directly' is bad advice. Bring a torch.",
        "value": 56640, "xp": 42480, "drop": "Immortal Head Tooth", "drop_value": 84960,
        "fallback_emoji": "🐉",
    },
    "Cerberus": {
        "aka": "The Hound of Hades", "biome": "cursed_ruins", "rarity": "mythic",
        "height": "Three heads at chest height",
        "description": "A giant three-headed dog with a serpent tail and a mane of snakes",
        "call": "Three-part howling, no harmony",
        "diet": "The living who try to leave; the dead who try to sneak back",
        "behavior": "Guards the gate of the Underworld — everyone in, no one out, unless you know the trick with honey-cakes",
        "blurb": "The only dog where 'who's a good boy' has to be answered three times.",
        "value": 56640, "xp": 42480, "drop": "Snake-Mane Scale", "drop_value": 84960,
        "fallback_emoji": "🐶",
    },
    "Gorgon": {
        "aka": "Medusa", "biome": "cursed_ruins", "rarity": "mythic",
        "height": "Human, with a very bad hair day",
        "description": "A woman with living snakes for hair and a gaze that turns flesh to stone",
        "call": "The dry rustle of a hundred small snakes",
        "diet": "Doesn't need to; her garden of statues never complains",
        "behavior": "Lairs in a ruined temple ringed by stone figures; only a mirrored shield lets you look",
        "blurb": "Greek myth's argument for good eye-contact etiquette. Look away. Look away NOW.",
        "value": 56640, "xp": 42480, "drop": "Stone-Gaze Lens", "drop_value": 84960,
        "fallback_emoji": "🐍",
    },
    "Harpies": {
        "aka": "The Snatchers", "biome": "cursed_ruins", "rarity": "mythic",
        "height": "Human-sized, mostly wing",
        "description": "Vulture bodies with the faces of starving women; filthy, fast, foul-smelling",
        "call": "A shriek and a downdraft",
        "diet": "Your dinner, snatched mid-bite; whatever they leave, they spoil",
        "behavior": "Swoop in packs, steal the food, ruin the table, and are gone",
        "blurb": "The reason Phineus never finished a meal. Bring more sandwiches than you need.",
        "value": 56640, "xp": 42480, "drop": "Reeking Wing-Feather", "drop_value": 84960,
        "fallback_emoji": "🦅",
    },
    # ── The Mediterranean Deep (abyssal_depths) ───────────────
    "Scylla": {
        "aka": "The Rock of Messina", "biome": "abyssal_depths", "rarity": "mythic",
        "height": "Six necks, each ending badly",
        "description": "A woman to the waist, then six long-necked dog-headed serpents and twelve groping feet",
        "call": "Barking, from six mouths, echoing off the cliff",
        "diet": "Six sailors per passing ship — one per head",
        "behavior": "Wedged in a cliff cave opposite the whirlpool Charybdis; you steer toward her to dodge something worse",
        "blurb": "Half of the original rock-and-a-hard-place. The hard place has teeth.",
        "value": 150080, "xp": 112560, "drop": "Six-Fanged Collar", "drop_value": 225120,
        "fallback_emoji": "🐙",
    },
    "Sirens": {
        "aka": "The Singers", "biome": "abyssal_depths", "rarity": "mythic",
        "height": "Bird-bodied, woman-voiced",
        "description": "Feathered from the waist down, perched on a reef of old shipwrecks and older bones",
        "call": "A song you will steer straight into the rocks to hear more of",
        "diet": "Sailors — once the ships have done the hard part",
        "behavior": "Sing from island rocks; the only defence is wax in the ears or ropes on the mast",
        "blurb": "The Mediterranean's original earworm. Ten out of ten, would not survive again.",
        "value": 150080, "xp": 112560, "drop": "Bone-Reef Lyre String", "drop_value": 225120,
        "fallback_emoji": "🧜‍♀️",
    },
    # ── Roof of the World — the Himalayas (celestial_peaks) ────
    "Yeti": {
        "aka": "The Abominable Snowman", "biome": "celestial_peaks", "rarity": "mythic",
        "height": "7–10 ft, hunched",
        "description": "White-to-rust shaggy fur, a conical skull, feet that leave craters in the snow",
        "call": "A high whistling cry carried on the wind",
        "diet": "Blue sheep, yak and marmots — and it is said to hold a grudge against yaks",
        "behavior": "Keeps above the tree line; crosses glaciers at dusk; leaves the only evidence anyone agrees on — the tracks",
        "blurb": "The Himalayas' worst-kept secret, best-kept footprint.",
        "value": 246000, "xp": 184500, "drop": "Frost-Matted Pelt", "drop_value": 369000,
        "fallback_emoji": "❄️",
    },
    "Dragon": {
        "aka": "The Great Wyrm", "biome": "celestial_peaks", "rarity": "mythic",
        "height": "Wings that shade a village",
        "description": "Armoured scales, a furnace throat, and eyes that have watched dynasties rise and fall",
        "call": "A roar, then a rising heat you feel before you hear",
        "diet": "Cattle by the herd, knights by the lance-load, gold by the hoard (it doesn't eat the gold, it just likes it)",
        "behavior": "Sleeps for centuries on its treasure; wakes furious; negotiates poorly",
        "blurb": "Europe hunts it, Asia prays to it, everyone agrees you don't want it annoyed.",
        "value": 246000, "xp": 184500, "drop": "Bottle of Dragon Breath", "drop_value": 369000,
        "fallback_emoji": "🐲",
    },
    "Phoenix": {
        "aka": "The Firebird", "biome": "celestial_peaks", "rarity": "mythic",
        "height": "Eagle-sized, sun-bright",
        "description": "Plumage of red and gold lit from within; trails embers",
        "call": "A song the old accounts say the sun-god himself stops to hear",
        "diet": "Frankincense, cardamom and sunlight — nothing that bleeds",
        "behavior": "Every five centuries builds a nest of spice, burns, and climbs newborn from its own ash",
        "blurb": "The only creature on this list with a retirement plan that actually works.",
        "value": 246000, "xp": 184500, "drop": "Everburning Ember", "drop_value": 369000,
        "fallback_emoji": "🔥",
    },
    "Griffin": {
        "aka": "The Gold-Guardian", "biome": "celestial_peaks", "rarity": "mythic",
        "height": "Lion-bodied, eagle-winged, bigger than either",
        "description": "An eagle's head, wings and foretalons on the body of a lion",
        "call": "A scream that opens like an eagle's and closes like a lion's",
        "diet": "Wild horses — it has a famous, ancient grudge against them",
        "behavior": "Nests on peaks lined with gold it has dug up; attacks anything near the hoard",
        "blurb": "Half eagle, half lion, entirely done with you touching its stuff.",
        "value": 246000, "xp": 184500, "drop": "Gold-Threaded Feather", "drop_value": 369000,
        "fallback_emoji": "🦅",
    },
    "Hippogriff": {
        "aka": "The Tamed Impossible", "biome": "celestial_peaks", "rarity": "mythic",
        "height": "Horse-bodied, with an eight-foot wingspan",
        "description": "An eagle's head and wings on the hindquarters of a horse — foal of a griffin and a mare",
        "call": "A whinny that breaks into a shriek",
        "diet": "Grazes like a horse; hunts like a raptor when hungry",
        "behavior": "Wary but tameable — the rarest mount in the world, if you can get a saddle on one",
        "blurb": "Proof that a griffin and a horse, against all odds and all instinct, once got along.",
        "value": 246000, "xp": 184500, "drop": "Primary Flight Quill", "drop_value": 369000,
        "fallback_emoji": "🐴",
    },
    # ── The Caribbean (rainbow) ──────────────────────────────
    "Zombie": {
        "aka": "The Undying", "biome": "rainbow", "rarity": "mythic",
        "height": "Human, give or take a slouch",
        "description": "Grey-skinned, hollow-eyed, moving like it forgot how joints work",
        "call": "A low, wet groan",
        "diet": "Whatever's still moving",
        "behavior": "Shambles toward warmth and noise; does not tire, does not stop",
        "blurb": "Haiti's original, since heavily franchised. Still the market leader in slow-motion menace.",
        "value": 114800, "xp": 86100, "drop": "Vial of Grave Dust", "drop_value": 172200,
        "fallback_emoji": "🧟",
    },
    "Chupacabra": {
        "aka": "The Goat-Sucker", "biome": "rainbow", "rarity": "mythic",
        "height": "3–4 ft at the shoulder",
        "description": "Spiny-backed dog-reptile with glowing red eyes",
        "call": "A hiss that raises every hair you own",
        "diet": "Livestock blood, drained through two neat punctures",
        "behavior": "Strikes at night, leaves the carcass, takes only the blood",
        "blurb": "A 1990s Puerto Rican folk panic that landed a merch deal and never left.",
        "value": 114800, "xp": 86100, "drop": "Hollow Fang", "drop_value": 172200,
        "fallback_emoji": "🐐",
    },
}

# ── Cash-bounty rescale (2026-09-09) ────────────────────────────
# `value` (the cash paid on a fight win) is retuned so the Celestial Peaks
# roster pays a 10M base; every other biome keeps its relative shape, scaled by
# the same factor. `xp` and `drop_value` (the sellable trophy) are untouched.
MYTH_BOUNTY_PEAKS_BASE = 10_000_000
_myth_top_value = max(c["value"] for c in MYTHIC_CREATURES.values())   # celestial_peaks
_myth_bounty_scale = MYTH_BOUNTY_PEAKS_BASE / _myth_top_value
for _c in MYTHIC_CREATURES.values():
    _c["value"] = int(round(_c["value"] * _myth_bounty_scale / 100.0)) * 100

# biome key -> [creature names]  (every biome key present, each list ≥ 1)
BIOME_MYTHS: dict[str, list[str]] = {}
for _cname, _cdata in MYTHIC_CREATURES.items():
    BIOME_MYTHS.setdefault(_cdata["biome"], []).append(_cname)

# drop item name -> (creature name, drop_value)  — for trophy pricing / lookups
# NOTE: drop_value now only feeds flavor text (e.g. "from X") — trophies stopped
# being sellable in the 2026-09-16 Collection rework; see TROPHY_EFFECTS below.
MYTH_DROPS = {c["drop"]: (n, c["drop_value"]) for n, c in MYTHIC_CREATURES.items()}

# ─────────────────────────────────────────────
# TROPHY EFFECTS  ·  Trophy Cabinet (2026-09-16 Collection rework)
# ─────────────────────────────────────────────
# One passive effect per mythic creature's trophy. Equipping a trophy (up to
# TROPHY_SLOT_THRESHOLDS-many at once, unlocked by unique-trophy count) grants
# its effect via app.py's trophy_effect_value()/trophy_proc() helpers — this
# dict is pure data, the actual mechanical hooks live at each relevant system
# (combat, tracking, travel, idle camp, hunt) in app.py.
# `value` is either a percentage / percentage-point / flat amount depending on
# `effect_key` — see the matching hook site in app.py for exactly how it's used.
TROPHY_SLOT_THRESHOLDS = [1, 5, 15]   # unique trophies needed to unlock slot 1/2/3

TROPHY_EFFECTS = {
    "Matted Fur Tuft":         {"creature": "Bigfoot",                  "effect_key": "tracking_success_pct",         "value": 8,
                                 "desc": "+8% success on Mythical tracking choices"},
    "Jar of Closet Shadow":    {"creature": "Bogeyman",                 "effect_key": "tracking_mistake_ignore_pct",  "value": 20,
                                 "desc": "20% chance a tracking mistake is ignored"},
    "Ember-Eye Coal":          {"creature": "Black Dog",                "effect_key": "xp_low_hp_pct",                "value": 6,
                                 "desc": "+6% XP while below 50% HP"},
    "Webbed Claw":             {"creature": "Grindylow",                "effect_key": "perfect_catch_pp",             "value": 3,
                                 "desc": "+3 percentage points to Perfect Catch chance"},
    "Loch Silt Sample":        {"creature": "Loch Ness Monster",        "effect_key": "crate_drop_pp",                "value": 12,
                                 "desc": "+12% chance to receive hunt crate drops"},
    "Dripping Bridle":         {"creature": "Kelpie",                   "effect_key": "travel_time_pct",              "value": 12,
                                 "desc": "Travel time -12%"},
    "Petrified Troll Nose":    {"creature": "Troll",                    "effect_key": "hp_regen_pct",                 "value": 20,
                                 "desc": "HP regeneration +20%"},
    "Broken Hel-Chain Link":   {"creature": "Garm",                     "effect_key": "myth_loss_pct",                "value": 25,
                                 "desc": "Mythical KO money loss -25%"},
    "Weighing-Scale Feather":  {"creature": "Ammut",                    "effect_key": "sell_pct",                     "value": 6,
                                 "desc": "Sell value +6%"},
    "Grapnel Talon":           {"creature": "Roc",                      "effect_key": "combat_accuracy_pct",          "value": 6,
                                 "desc": "Combat accuracy +6%"},
    "Barrel-Thick Scale":      {"creature": "Sea Serpent of Cape Ann",  "effect_key": "incoming_dmg_pct",             "value": 8,
                                 "desc": "Incoming combat damage -8%"},
    "Kraken Ink Vial":         {"creature": "Kraken",                   "effect_key": "sighting_double_clue_pct",     "value": 15,
                                 "desc": "15% chance a Global Sighting clue counts twice"},
    "Coffin Nail":             {"creature": "Vampires",                 "effect_key": "hunt_hp_restore",              "value": 3,
                                 "desc": "Restore 3 HP after a successful hunt"},
    "Silver-Burned Fang":      {"creature": "Werewolf",                 "effect_key": "myth_dmg_pct",                 "value": 10,
                                 "desc": "Damage against Mythicals +10%"},
    "Barbed Tail-Spine":       {"creature": "Manticore",                "effect_key": "punch_kick_accuracy_pct",      "value": 10,
                                 "desc": "Punch/Kick attack accuracy +10%"},
    "Black-Cloud Wisp":        {"creature": "Nue",                      "effect_key": "luck_world_condition_pct",     "value": 8,
                                 "desc": "+8% Luck during world conditions"},
    "Billabong Tusk":          {"creature": "Bunyip",                   "effect_key": "camp_capacity_pct",            "value": 20,
                                 "desc": "Hunting Camp capacity +20%"},
    "Coarse Yowie Hair":       {"creature": "Yowie",                    "effect_key": "camp_production_pct",          "value": 10,
                                 "desc": "Hunting Camp production +10%"},
    "Fire-Gland Sac":          {"creature": "Chimera",                  "effect_key": "first_hit_bonus_dmg",          "value": 10,
                                 "desc": "First successful hit in a fight deals +10 bonus damage"},
    "Petrifying Eye":          {"creature": "Cockatrice",               "effect_key": "enemy_skip_pct",               "value": 8,
                                 "desc": "8% chance an enemy skips its next attack"},
    "Bronze Nose-Ring":        {"creature": "Minotaur",                 "effect_key": "tracking_extra_mistake",       "value": 1,
                                 "desc": "+1 allowed mistake during Mythical tracking"},
    "Immortal Head Tooth":     {"creature": "Hydra",                    "effect_key": "hydra_survive_daily",          "value": 1,
                                 "desc": "Once/day, a lethal hit leaves you at 1 HP instead"},
    "Snake-Mane Scale":        {"creature": "Cerberus",                 "effect_key": "max_hp_bonus",                 "value": 15,
                                 "desc": "Maximum HP +15"},
    "Stone-Gaze Lens":         {"creature": "Gorgon",                   "effect_key": "tracking_reveal_risk",         "value": 1,
                                 "desc": "Marks the riskiest choice during each tracking step"},
    "Reeking Wing-Feather":    {"creature": "Harpies",                  "effect_key": "hunt_cooldown_reduction",      "value": 0.35,
                                 "desc": "Hunt cooldown -0.35 sec"},
    "Six-Fanged Collar":       {"creature": "Scylla",                   "effect_key": "double_hit_pct",               "value": 8,
                                 "desc": "8% chance a successful combat attack hits twice"},
    "Bone-Reef Lyre String":   {"creature": "Sirens",                   "effect_key": "myth_flee_pct",                "value": 20,
                                 "desc": "Flee success against Mythicals +20%"},
    "Frost-Matted Pelt":       {"creature": "Yeti",                     "effect_key": "first_enemy_hit_reduction_pct","value": 50,
                                 "desc": "First enemy hit each fight deals 50% less damage"},
    "Bottle of Dragon Breath": {"creature": "Dragon",                   "effect_key": "burn_on_hit",                  "value": 1,
                                 "desc": "First hit applies burn for bonus damage over 3 turns"},
    "Everburning Ember":       {"creature": "Phoenix",                  "effect_key": "phoenix_revive_daily",         "value": 30,
                                 "desc": "Once/day, a KO restores you to 30 HP after the fight"},
    "Gold-Threaded Feather":   {"creature": "Griffin",                  "effect_key": "luck_pct",                     "value": 6,
                                 "desc": "+6% Luck"},
    "Primary Flight Quill":    {"creature": "Hippogriff",               "effect_key": "travel_instant_pct",           "value": 10,
                                 "desc": "10% chance travel completes instantly"},
    "Vial of Grave Dust":      {"creature": "Zombie",                   "effect_key": "ammo_save_pct",                "value": 12,
                                 "desc": "12% chance ammunition isn't consumed on a hunt"},
    "Hollow Fang":             {"creature": "Chupacabra",               "effect_key": "perfect_catch_hp_restore",     "value": 6,
                                 "desc": "Perfect Catches restore 6 HP"},
}

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

def creature_emoji(name: str) -> str:
    c = MYTHIC_CREATURES.get(name, {})
    return EMOJI.get(f"creature_{_slug(name)}") or c.get("fallback_emoji", "🔮")

def trophy_emoji(name: str) -> str:
    """Custom emoji for a trophy/drop item name (see TROPHY_EFFECTS), falling
    back to the generic trophy icon when no dedicated art exists yet."""
    return EMOJI.get(f"trophy_{_slug(name)}") or EMOJI["trophy"]


# ─────────────────────────────────────────────
# AMMO
# ─────────────────────────────────────────────

AMMO = {
    # ── ARROWS (Shortbow, Longbow) ──────────────────────────────
    "Wooden Arrow": {
        "ammo_type": "arrow",
        "description": "Basic fletched arrow. Steady but unremarkable.",
        "emoji": "🪵",
        "price": 10, "currency": "money",
        "boost_luck": 5, "boost_sell": 0, "boost_xp": 8,
    },
    "Iron Arrow": {
        "ammo_type": "arrow",
        "description": "Reinforced iron tip for better accuracy.",
        "emoji": "⚙️",
        "price": 30, "currency": "money",
        "boost_luck": 12, "boost_sell": 0, "boost_xp": 18,
    },
    "Enchanted Arrow": {
        "ammo_type": "arrow",
        "description": "Magically guided — rarely misses its mark.",
        "emoji": "✨",
        "price": 100, "currency": "money",
        "boost_luck": 30, "boost_sell": 0, "boost_xp": 40,
    },
    "Phantom Arrow": {
        "ammo_type": "arrow",
        "description": "Passes through walls and seeks rare prey.",
        "emoji": "👻",
        "price": 10, "currency": "gems",
        "boost_luck": 50, "boost_sell": 0, "boost_xp": 50,
    },
    # ── BOLTS (Crossbow) ────────────────────────────────────────
    "Crude Bolt": {
        "ammo_type": "bolt",
        "description": "Hastily carved bolt. Functional at best.",
        "emoji": "📌",
        "price": 25, "currency": "money",
        "boost_luck": 5, "boost_sell": 8, "boost_xp": 0,
    },
    "Steel Bolt": {
        "ammo_type": "bolt",
        "description": "Hardened steel tip for piercing tough hides.",
        "emoji": "🔩",
        "price": 75, "currency": "money",
        "boost_luck": 15, "boost_sell": 20, "boost_xp": 0,
    },
    "Gilded Bolt": {
        "ammo_type": "bolt",
        "description": "Gold-tipped bolt — prey fetches a higher price.",
        "emoji": "💛",
        "price": 200, "currency": "money",
        "boost_luck": 32, "boost_sell": 40, "boost_xp": 0,
    },
    "Venom Bolt": {
        "ammo_type": "bolt",
        "description": "Coated in rare venom that preserves pelt quality.",
        "emoji": "🐍",
        "price": 16, "currency": "gems",
        "boost_luck": 50, "boost_sell": 50, "boost_xp": 0,
    },
    # ── BULLETS (Musket, Hunting Rifle, Shotgun, Sniper Rifle) ──
    "Lead Ball": {
        "ammo_type": "bullet",
        "description": "Old-fashioned lead round. Gets the job done.",
        "emoji": "⚫",
        "price": 50, "currency": "money",
        "boost_luck": 0, "boost_sell": 8, "boost_xp": 5,
    },
    "Hollow Point": {
        "ammo_type": "bullet",
        "description": "Expands on impact — maximises sell yield.",
        "emoji": "🔘",
        "price": 150, "currency": "money",
        "boost_luck": 0, "boost_sell": 22, "boost_xp": 12,
    },
    "Silver Bullet": {
        "ammo_type": "bullet",
        "description": "Mythically potent — effective against rare prey.",
        "emoji": "🌕",
        "price": 400, "currency": "money",
        "boost_luck": 10, "boost_sell": 38, "boost_xp": 30,
    },
    "Void Round": {
        "ammo_type": "bullet",
        "description": "Infused with dark matter — hunters fear nothing.",
        "emoji": "🌑",
        "price": 24, "currency": "gems",
        "boost_luck": 20, "boost_sell": 50, "boost_xp": 45,
    },
    # ── TRANQ DARTS (Tranq Gun) ─────────────────────────────────
    "Basic Tranq": {
        "ammo_type": "tranq_dart",
        "description": "Standard sedative — increases rare catch chance.",
        "emoji": "💊",
        "price": 95, "currency": "money",
        "boost_luck": 20, "boost_sell": 0, "boost_xp": 0,
    },
    "Potent Tranq": {
        "ammo_type": "tranq_dart",
        "description": "Heavy sedative — prey stays calm and valuable.",
        "emoji": "🧪",
        "price": 240, "currency": "money",
        "boost_luck": 30, "boost_sell": 0, "boost_xp": 0,
    },
    "Exotic Serum": {
        "ammo_type": "tranq_dart",
        "description": "Rare compound that draws out legendary creatures.",
        "emoji": "🔬",
        "price": 485, "currency": "money",
        "boost_luck": 40, "boost_sell": 0, "boost_xp": 0,
    },
    "Void Serum": {
        "ammo_type": "tranq_dart",
        "description": "Cosmic formula — almost guarantees rare catches.",
        "emoji": "🌌",
        "price": 32, "currency": "gems",
        "boost_luck": 50, "boost_sell": 0, "boost_xp": 0,
    },
    # ── ENERGY CELLS (Plasma Caster, Gravity Trap) ──────────────
    "Charged Cell": {
        "ammo_type": "energy_cell",
        "description": "Standard power cell. Efficient energy output.",
        "emoji": "🔋",
        "price": 140, "currency": "money",
        "boost_luck": 0, "boost_sell": 10, "boost_xp": 15,
    },
    "Overcharged Cell": {
        "ammo_type": "energy_cell",
        "description": "Overloaded cell — boosts scan range and XP gain.",
        "emoji": "⚡",
        "price": 355, "currency": "money",
        "boost_luck": 0, "boost_sell": 22, "boost_xp": 28,
    },
    "Plasma Core": {
        "ammo_type": "energy_cell",
        "description": "Condensed plasma — dramatically amplifies output.",
        "emoji": "🌟",
        "price": 710, "currency": "money",
        "boost_luck": 5, "boost_sell": 35, "boost_xp": 40,
    },
    "Singularity Cell": {
        "ammo_type": "energy_cell",
        "description": "A micro black hole — warps reality around prey.",
        "emoji": "🕳️",
        "price": 44, "currency": "gems",
        "boost_luck": 10, "boost_sell": 50, "boost_xp": 50,
    },
    # ── SOUL SHARDS (Soul Snare, Void Bow) ──────────────────────
    "Fractured Shard": {
        "ammo_type": "soul_shard",
        "description": "A cracked soul fragment — modest all-round boost.",
        "emoji": "💎",
        "price": 285, "currency": "money",
        "boost_luck": 8, "boost_sell": 8, "boost_xp": 8,
    },
    "Pure Shard": {
        "ammo_type": "soul_shard",
        "description": "A cleansed shard — balanced enhancement.",
        "emoji": "🔷",
        "price": 720, "currency": "money",
        "boost_luck": 18, "boost_sell": 18, "boost_xp": 18,
    },
    "Void Shard": {
        "ammo_type": "soul_shard",
        "description": "Dark matter crystallised — powerful all-round.",
        "emoji": "🟣",
        "price": 1_435, "currency": "money",
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
        "price": 375, "currency": "money",
        "boost_luck": 10, "boost_sell": 10, "boost_xp": 10,
    },
    "Nebula Round": {
        "ammo_type": "cosmic_round",
        "description": "Compressed nebula gas — hunter becomes unstoppable.",
        "emoji": "🌌",
        "price": 940, "currency": "money",
        "boost_luck": 22, "boost_sell": 22, "boost_xp": 22,
    },
    "Celestial Core": {
        "ammo_type": "cosmic_round",
        "description": "Pure divine energy — bends fate in the hunter's favour.",
        "emoji": "✨",
        "price": 1_875, "currency": "money",
        "boost_luck": 38, "boost_sell": 38, "boost_xp": 38,
    },
    "Eternal Cosmos": {
        "ammo_type": "cosmic_round",
        "description": "The universe condensed — absolute peak performance.",
        "emoji": "🌀",
        "price": 80, "currency": "gems",
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


# ── Wire tool / ammo icons from the EMOJI registry (single source of truth) ──
# TOOLS and AMMO carry an inline unicode "emoji" as a fallback; when a matching
# custom emoji exists in EMOJI (key = "tool_"/"ammo_" + name, spaces→underscores)
# it wins. Edit the id in the EMOJI dict at the top of this file, nowhere else.
for _tname in TOOLS:
    _ekey = "tool_" + _tname.lower().replace(" ", "_")
    if EMOJI.get(_ekey):
        TOOLS[_tname]["emoji"] = EMOJI[_ekey]

for _aname in AMMO:
    _ekey = "ammo_" + _aname.lower().replace(" ", "_")
    if EMOJI.get(_ekey):
        AMMO[_aname]["emoji"] = EMOJI[_ekey]


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
    "Military Jeep": {"emoji": "🛻", "tier":  9, "boost_cd": 2.1, "boost_luck":  0, "price": 25_000_000, "currency": "money", "description": "Built for the toughest hunts."},
    "Hovercraft":    {"emoji": "🚀", "tier": 10, "boost_cd": 2.4, "boost_luck": 15, "price": 60_000_000, "currency": "money", "description": "Endgame speed machine."},
}

# Same wiring convention as TOOLS/AMMO above — a matching EMOJI["vehicle_<name>"]
# key wins over the inline unicode fallback.
for _vname in VEHICLES:
    _ekey = "vehicle_" + _vname.lower().replace(" ", "_")
    if EMOJI.get(_ekey):
        VEHICLES[_vname]["emoji"] = EMOJI[_ekey]


# ─────────────────────────────────────────────
# HUNTING CRATES
# ─────────────────────────────────────────────

import random as _random

# Crafting / material economy
# ── Hunt catch → materials (rolled per catch, of the caught animal's rarity) ──
SHARD_DROP_CHANCE      = 0.10   # +1 shard of that rarity
CRATE_DROP_CHANCE      = 0.05   # +1 finished crate of that rarity, straight up
MYTH_SHARD_KILL_CHANCE = 0.20   # a mythic KILL → +1 mythic shard (no mythic catches exist)
# ── Crafting chain ──
CRYSTAL_SHARD_COST     = 9      # shards fused into one crystal (timed, via /craft)
CRYSTAL_CRAFT_SECONDS  = 300    # 5 min per crystal, queued serially
CRAFT_QUEUE_MAX        = 20
CRATE_CRYSTAL_COST     = 9      # crystals spent for one crate (instant, in the /craft crate shop)
# ── Crate open extras ──
CRATE_GEMSTONE_CHANCE      = 0.05   # any crate → a decorative gemstone of its rarity

_CRATE_PLACEHOLDER_EMOJI = emoji("crate_sample")   # generic crate art — fallback per tier

CRATE_TIERS = {
    "Common Crate": {
        "rarity": "common", "emoji": _CRATE_PLACEHOLDER_EMOJI, "crystal_cost": CRATE_CRYSTAL_COST,
        "description": "A basic crate. Contains modest rewards.",
        "color": 0x95A5A6,
    },
    "Uncommon Crate": {
        "rarity": "uncommon", "emoji": _CRATE_PLACEHOLDER_EMOJI, "crystal_cost": CRATE_CRYSTAL_COST,
        "description": "A step up. Better odds on boosts and gems.",
        "color": 0x2ECC71,
    },
    "Rare Crate": {
        "rarity": "rare", "emoji": _CRATE_PLACEHOLDER_EMOJI, "crystal_cost": CRATE_CRYSTAL_COST,
        "description": "A rarer crate with better loot.",
        "color": 0x3498DB,
    },
    "Epic Crate": {
        "rarity": "epic", "emoji": _CRATE_PLACEHOLDER_EMOJI, "crystal_cost": CRATE_CRYSTAL_COST,
        "description": "An epic crate. Rare boosts and big rewards.",
        "color": 0x9B59B6,
    },
    "Legendary Crate": {
        "rarity": "legendary", "emoji": _CRATE_PLACEHOLDER_EMOJI, "crystal_cost": CRATE_CRYSTAL_COST,
        "description": "A legendary crate. Permanent boosts possible.",
        "color": 0xF39C12,
    },
    "Mythic Crate": {
        "rarity": "mythic", "emoji": _CRATE_PLACEHOLDER_EMOJI, "crystal_cost": CRATE_CRYSTAL_COST,
        "description": "The rarest crate. Exclusive titles, massive rewards, and sometimes a cryptid trophy.",
        "color": 0xE74C3C,
    },
}

# Per-tier crate art: picks up EMOJI["<rarity>_crate"] when uploaded, otherwise
# the generic `crate_sample` placeholder (currently the Rare tier has no art).
for _cn, _cd in CRATE_TIERS.items():
    _cd["emoji"] = EMOJI.get(f"{_cd['rarity']}_crate", _CRATE_PLACEHOLDER_EMOJI)

# Per-rarity gemstone icons — fall back to the matching crystal icon until art exists.
GEMSTONE_ICONS = {r: EMOJI.get(f"{r}_gemstone", CRYSTAL_ICONS[r]) for r in RARITY_KEYS}

# rarity key → crate name, and the reverse
RARITY_CRATE = {v["rarity"]: k for k, v in CRATE_TIERS.items()}
CRATE_RARITY = {k: v["rarity"] for k, v in CRATE_TIERS.items()}

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
        (15, "gems",       {"min": 8,            "max": 20}),
        (10, "temp_boost", {"stat": "luck",  "amount": 10, "minutes": 15}),
        (10, "temp_boost", {"stat": "sell",  "amount": 10, "minutes": 15}),
        (10, "temp_boost", {"stat": "xp",    "amount": 10, "minutes": 15}),
        (5,  "temp_boost", {"stat": "luck",  "amount": 15, "minutes": 30}),
        (5,  "temp_boost", {"stat": "sell",  "amount": 15, "minutes": 30}),
        (3,  "perm_boost", {"stat": "luck",  "amount": 1}),
        (2,  "perm_boost", {"stat": "sell",  "amount": 1}),
        (2,  "perm_boost", {"stat": "xp",    "amount": 1}),
    ],
    "Uncommon Crate": [
        (38, "money",      {"min": 150_000,      "max": 1_500_000}),
        (25, "money",      {"min": 300_000,      "max": 3_000_000}),
        (15, "gems",       {"min": 12,           "max": 30}),
        (12, "temp_boost", {"stat": "luck",  "amount": 15, "minutes": 30}),
        (12, "temp_boost", {"stat": "sell",  "amount": 15, "minutes": 30}),
        (10, "temp_boost", {"stat": "xp",    "amount": 15, "minutes": 30}),
        (6,  "temp_boost", {"stat": "luck",  "amount": 20, "minutes": 45}),
        (6,  "temp_boost", {"stat": "sell",  "amount": 20, "minutes": 45}),
        (4,  "perm_boost", {"stat": "luck",  "amount": 1}),
        (3,  "perm_boost", {"stat": "sell",  "amount": 1}),
        (3,  "perm_boost", {"stat": "xp",    "amount": 1}),
    ],
    "Rare Crate": [
        (30, "money",      {"min": 500_000,      "max": 5_000_000}),
        (20, "gems",       {"min": 18,           "max": 45}),
        (15, "temp_boost", {"stat": "luck",  "amount": 20, "minutes": 45}),
        (15, "temp_boost", {"stat": "sell",  "amount": 20, "minutes": 45}),
        (10, "temp_boost", {"stat": "luck",  "amount": 30, "minutes": 90}),
        (10, "temp_boost", {"stat": "sell",  "amount": 30, "minutes": 90}),
        (8,  "temp_boost", {"stat": "xp",    "amount": 30, "minutes": 90}),
        (5,  "perm_boost", {"stat": "luck",  "amount": 2}),
        (5,  "perm_boost", {"stat": "sell",  "amount": 2}),
        (5,  "perm_boost", {"stat": "xp",    "amount": 2}),
        (3,  "title",      {"title": "Lucky Find"}),
        (2,  "title",      {"title": "The Collector"}),
    ],
    "Epic Crate": [
        (36, "money",      {"min": 2_000_000,    "max": 20_000_000}),
        (26, "gems",       {"min": 35,           "max": 80}),
        (15, "temp_boost", {"stat": "luck",  "amount": 40, "minutes": 90}),
        (15, "temp_boost", {"stat": "sell",  "amount": 40, "minutes": 90}),
        (10, "temp_boost", {"stat": "luck",  "amount": 50, "minutes": 120}),
        (10, "temp_boost", {"stat": "sell",  "amount": 50, "minutes": 120}),
        (10, "temp_boost", {"stat": "xp",    "amount": 50, "minutes": 120}),
        (8,  "perm_boost", {"stat": "luck",  "amount": 3}),
        (8,  "perm_boost", {"stat": "sell",  "amount": 3}),
        (8,  "perm_boost", {"stat": "xp",    "amount": 3}),
        (5,  "title",      {"title": "Epic Opener"}),
        (3,  "title",      {"title": "Gear Hoarder"}),
        (2,  "title",      {"title": "The Fortunate"}),
    ],
    "Legendary Crate": [
        (38, "money",      {"min": 10_000_000,   "max": 100_000_000}),
        (26, "gems",       {"min": 60,           "max": 140}),
        (10, "temp_boost", {"stat": "luck",  "amount": 60, "minutes": 120}),
        (10, "temp_boost", {"stat": "sell",  "amount": 60, "minutes": 120}),
        (10, "temp_boost", {"stat": "luck",  "amount": 75, "minutes": 180}),
        (10, "temp_boost", {"stat": "sell",  "amount": 75, "minutes": 180}),
        (10, "temp_boost", {"stat": "xp",    "amount": 75, "minutes": 180}),
        (10, "perm_boost", {"stat": "luck",  "amount": 5}),
        (10, "perm_boost", {"stat": "sell",  "amount": 5}),
        (10, "perm_boost", {"stat": "xp",    "amount": 5}),
        (5,  "title",      {"title": "Crate Addict"}),
        (5,  "title",      {"title": "Legend in the Making"}),
        (3,  "title",      {"title": "The Privileged"}),
        (2,  "title",      {"title": "Legendary Opener"}),
    ],
    "Mythic Crate": [
        (30, "money",      {"min": 50_000_000,   "max": 500_000_000}),
        (30, "gems",       {"min": 120,          "max": 300}),
        (10, "temp_boost", {"stat": "luck",  "amount": 100, "minutes": 180}),
        (10, "temp_boost", {"stat": "sell",  "amount": 100, "minutes": 180}),
        (10, "temp_boost", {"stat": "luck",  "amount": 100, "minutes": 180}),
        (10, "temp_boost", {"stat": "sell",  "amount": 100, "minutes": 180}),
        (10, "temp_boost", {"stat": "xp",    "amount": 100, "minutes": 180}),
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
# HUNT CATCH → MATERIALS
# ─────────────────────────────────────────────
# Rolled once per catch. The SHARD rarity still mirrors the caught animal's
# rarity; the CRATE rarity is instead chosen from a biome-tiered weight table
# (roll_crate_rarity) so early biomes never yield legendary/mythic crates and
# the top biomes yield only epic+. Mythic shards never come from here (no mythic
# catches) — a mythic KILL rolls MYTH_SHARD_KILL_CHANCE separately in resolve_myth.

# Hunt-crate rarity by biome tool-tier (see BIOME_TOOL_TIER). Weights are
# relative, not percentages; tune freely. Rules kept: common is never more than
# ~10% of a tier's distribution, legendary/mythic stay tiny, and the very top
# biomes drop epic-or-better only. Announce every change via the /update log.
CRATE_TIER_WEIGHTS: dict[int, dict[str, float]] = {
    1: {"common": 10, "uncommon": 46, "rare": 30, "epic": 13, "legendary": 1,   "mythic": 0},    # tool tier 1–4
    2: {"common": 8,  "uncommon": 30, "rare": 37, "epic": 20, "legendary": 4.5, "mythic": 0.5},  # tool tier 5–9
    3: {"common": 3,  "uncommon": 14, "rare": 31, "epic": 37, "legendary": 13,  "mythic": 2},    # tool tier 10–16
    4: {"common": 0,  "uncommon": 0,  "rare": 0,  "epic": 88, "legendary": 10,  "mythic": 2},    # tool tier 17+
}

def _crate_tier_for_biome(biome: str) -> int:
    t = BIOME_TOOL_TIER.get(biome, 1)
    return 1 if t <= 4 else 2 if t <= 9 else 3 if t <= 16 else 4

def roll_crate_rarity(biome: str) -> str:
    """Pick a crate rarity for a drop in ``biome`` from the tiered weight table."""
    w    = CRATE_TIER_WEIGHTS[_crate_tier_for_biome(biome)]
    keys = [k for k in w if w[k] > 0]
    return _random.choices(keys, weights=[w[k] for k in keys], k=1)[0]

def roll_catch_drops(rarity: str, crate_luck_boost: int = 0,
                     shard_chance: float | None = None,
                     crate_chance: float | None = None,
                     biome: str = "village",
                     crate_chance_bonus: float = 0.0) -> dict:
    """Returns {'shard': rarity|None, 'crate': crate_name|None} for one catch.
    Each point of crate_luck adds +0.5% to the shard chance. `shard_chance` /
    `crate_chance` override the base rates (used by the buff event).
    `crate_chance_bonus` is an additive 0-1 probability bump (Loch Silt Sample
    trophy). The crate's rarity comes from the biome-tiered table, not the
    animal's rarity."""
    if rarity not in RARITY_KEYS or rarity == "mythic":
        rarity = "common"
    base_shard = SHARD_DROP_CHANCE if shard_chance is None else shard_chance
    base_crate = (CRATE_DROP_CHANCE if crate_chance is None else crate_chance) + max(0.0, crate_chance_bonus)
    shard_p = base_shard + max(0, crate_luck_boost) * 0.005
    return {
        "shard": rarity if _random.random() < shard_p else None,
        "crate": RARITY_CRATE[roll_crate_rarity(biome)] if _random.random() < base_crate else None,
    }


# ─────────────────────────────────────────────
# SHOP BOOST ITEMS
# ─────────────────────────────────────────────

# Hard ceilings a *regular* player can reach through normal play. Enforced only
# on new gains (shop, tribe shop, crate perm-boosts) — never retroactively, and
# admin set_*/max_boosts stay uncapped so tester accounts can still be maxed.
MAX_PERSONAL_BOOST = 500   # each of data[uid]["boosts"] luck / sell / xp
MAX_TRIBE_BOOST    = 200   # each of a tribe's luck_boost / sell_price_boost / xp_boost

# Price escalates per successive upgrade: 5, 10, 15 … 50 gems (see shop_boost_price).
# "price" is the 1st-upgrade cost, kept for any generic consumer.
SHOP_BOOST_ITEMS = {
    "Lucky Charm": {
        "description": "Increases your personal luck by 5%.",
        "price": 5, "price_step": 5, "currency": "gems",
        "max_qty": 10,
        "boost_key": "luck", "boost_amt": 5,
    },
    "Sellmaster Scroll": {
        "description": "Increases your personal sell price by 5%.",
        "price": 5, "price_step": 5, "currency": "gems",
        "max_qty": 10,
        "boost_key": "sell", "boost_amt": 5,
    },
    "XP Tome": {
        "description": "Increases your personal XP gain by 5%.",
        "price": 5, "price_step": 5, "currency": "gems",
        "max_qty": 10,
        "boost_key": "xp", "boost_amt": 5,
    },
    "Crate Charm": {
        "description": "Increases your shard drop chance while hunting by +0.5% per level.",
        "price": 5, "price_step": 5, "currency": "gems",
        "max_qty": 10,
        "boost_key": "crate_luck", "boost_amt": 1,
    },
}


def shop_boost_price(item_name: str, bought: int) -> int:
    """Gem cost of the NEXT (``bought`` + 1-th) upgrade of a shop boost.
    Escalates in ``price_step`` increments: 5, 10, 15 … step × max_qty."""
    item = SHOP_BOOST_ITEMS.get(item_name, {})
    step = item.get("price_step")
    if not step:
        return int(item.get("price", 0))
    n = max(0, min(int(bought), item.get("max_qty", 10) - 1))
    return step * (n + 1)


# ─────────────────────────────────────────────
# TRIBE PROGRESSION  (Phase 1 — all values are starting points to tune)
# ─────────────────────────────────────────────
# Tribe XP is separate from player XP and only earned by post-join activity.
# Never awarded for gambling / purchases / trades / deposits.
TRIBE_XP_HUNT           = 1        # per successful hunt
TRIBE_XP_HUNT_CAP_DAY   = 100      # per member per day
TRIBE_XP_DAILY          = 25       # claiming the daily reward — once/member/day
TRIBE_XP_TASK           = 50       # claiming a /quests daily quest
TRIBE_XP_TASK_CAP_DAY   = 2        # per member per day
TRIBE_XP_CONTRACT       = (500, 400, 700)   # Hunting / Exploration / Teamwork — tribe-wide
TRIBE_XP_BOSS           = 1000     # once/tribe/week (boss fight — not built yet)

TRIBE_LEVEL_CAP         = 30
def tribe_xp_to_next(level: int) -> int:
    """XP to go from `level` to `level + 1`. 1000 for L1→2, +400 per level."""
    return 1000 + 400 * (max(1, level) - 1)

# tribe level → base member cap (highest key ≤ level wins). The Perk-Shop "+1 Slot"
# purchase still stacks on top of this floor.
TRIBE_MEMBER_CAP        = {1: 10, 5: 12, 10: 15, 15: 18, 20: 20}

def tribe_member_cap(level: int) -> int:
    return max(v for k, v in TRIBE_MEMBER_CAP.items() if k <= max(1, level))

# feature unlocks by tribe level (Phase 1 wires member cap + contracts; the rest are
# gated placeholders until their systems ship)
TRIBE_UNLOCK_CONTRACTS   = 2
TRIBE_UNLOCK_TREASURY    = 3
TRIBE_UNLOCK_EXPEDITIONS = 8
TRIBE_UNLOCK_BOSS        = 10

TRIBE_RECRUIT_PROBATION_H = 24     # recruit → member auto-promote
TRIBE_REJOIN_COOLDOWN_H   = 48     # after leaving/kick, wait before joining another
TRIBE_CONTRACT_MIN_GROUP  = 5      # minimum scaling group so a 1-player tribe can't farm
TRIBE_LOG_MAX             = 50

# Weekly shared contracts. `target` is computed from the frozen scaling group.
TRIBE_CONTRACTS = [
    {"kind": "hunting",     "label": "Combined Haul",
     "desc": "Catch {target} animals as a tribe this week.",
     "per_scale": 300, "min_target": 300},
    {"kind": "exploration", "label": "Spread Out",
     "desc": "Hunt in {target} different biomes this week.",
     "per_scale": 0, "min_target": 3, "max_target": 5},
    {"kind": "teamwork",    "label": "All Hands",
     "desc": "{target} members each complete 2 personal tasks this week.",
     "per_scale": 1, "min_target": 3},
]


# ─────────────────────────────────────────────
# GLOBAL EVENTS — activity mini-games  (Phase 1: Fox / Shipwreck / Duck)
# ─────────────────────────────────────────────
# Registry + `ev_*` buff wiring live in app.py; this is just the tunable data.
# Economy rule: cosmetics + per-event resources only — no money/gems/inventory risk.
EVENT_HOURS = 72          # activity/community events run this long

# ── 🦊 Thieving Fox ──
FOX_ATTEMPTS_DAY   = 5
FOX_LEAD_START     = 7
FOX_TITLE_AT       = 3    # perfect parcel recoveries → "Outfoxed"
FOX_ROUTES = {           # key → (lead delta on success, safe%, on-fail lead delta)
    "shortcut": {"label": "Shortcut", "lo": 3, "hi": 5, "safe": 60, "fail_lead": 2, "breaks_perfect": True},
    "steady":   {"label": "Steady",   "lo": 2, "hi": 2, "safe": 90, "fail_lead": 1, "breaks_perfect": True},
    "wait":     {"label": "Lie Low",  "lo": 1, "hi": 1, "safe": 100, "fail_lead": 0, "breaks_perfect": False},
}
FOX_SHOP = [   # cost in parcels → reward
    {"label": "Rare Crate",      "cost": 2, "crate": "Rare Crate"},
    {"label": "Epic Crate",      "cost": 4, "crate": "Epic Crate"},
    {"label": "Legendary Crate", "cost": 9, "crate": "Legendary Crate"},
]

# ── 🏴‍☠️ Shipwreck Scramble ──
SHIP_DIVES_DAY = 6
SHIP_SPOTS = {   # key → (salvage lo, hi, wipe% of unbanked, fraction lost)
    "deck":   {"label": "Search the Deck",  "lo": 2, "hi": 4,  "risk": 0,  "loss": 0.0},
    "cabins": {"label": "Ransack Cabins",   "lo": 4, "hi": 8,  "risk": 15, "loss": 0.25},
    "hold":   {"label": "Dive the Hold",    "lo": 8, "hi": 15, "risk": 35, "loss": 0.5},
}
SHIP_SHOP = [
    {"label": "Rare Crate",         "cost": 20,  "crate": "Rare Crate"},
    {"label": "Epic Crate",         "cost": 45,  "crate": "Epic Crate"},
    {"label": "Mythic Crate",       "cost": 120, "crate": "Mythic Crate"},
    {"label": "Title: Wreck Diver",  "cost": 50,  "title": "Wreck Diver"},
    {"label": "Title: Salvage Baron","cost": 250, "title": "Salvage Baron"},
]

# ── 🦆 Duck Takeover ──
DUCK_BREAD_DAY   = 60          # bread crumbs a player can bank per day
DUCK_FEED_CHUNK  = 25          # bread moved per "Feed the Ducks" press
DUCK_GOAL_BASE   = 400         # community goal = base * max(5, recent-active)
DUCK_CONTRIB_MIN = 30          # bread contributed to qualify for the ending reward
DUCK_ENDINGS = {
    "negotiate": {"label": "Negotiate", "title": "Duck Diplomat",
                  "text": "A treaty is signed in breadcrumbs. The ducks return the shop, mostly intact."},
    "distract":  {"label": "Distract",  "title": "Master of Distraction",
                  "text": "Someone throws a whole loaf into the sea. The ducks give chase. Shop reclaimed."},
    "challenge": {"label": "Challenge",  "title": "Duck Slayer",
                  "text": "You challenge the Duck King to single combat. It goes about how you'd expect, but the shop is yours again."},
}


# ─────────────────────────────────────────────
# STARTER SPECIALTIES  ·  chosen once, at the end of onboarding (Idle Hunter V2)
# ─────────────────────────────────────────────
# Grants a single 30-minute temp boost (data[uid]["temp_boosts"] entry). Purely
# a first-session nudge — never repeatable (onboarding["starter_pack"] guards it).
STARTER_PACKS = {
    "scout":  {"label": "Scout",  "emoji": "🐾",
               "boosts": {"luck": 20, "xp": 10, "sell": 5},
               "duration": 1800,
               "blurb": "+20% Luck, +10% XP, +5% Sell for 30 minutes — find rare catches sooner."},
    "hunter": {"label": "Hunter", "emoji": "🎯",
               "boosts": {"xp": 35, "luck": 5, "sell": 5},
               "duration": 1800,
               "blurb": "+35% XP, +5% Luck, +5% Sell for 30 minutes — level up fast out of the gate."},
    "trader": {"label": "Trader", "emoji": "💰",
               "boosts": {"sell": 25, "xp": 10, "luck": 5},
               "duration": 1800,
               "blurb": "+25% Sell Value, +10% XP, +5% Luck for 30 minutes — build a bankroll early."},
}


# ─────────────────────────────────────────────
# DAILY TIERS
# ─────────────────────────────────────────────
# Each entry is a dict so bot.py can access tier["money_min"] etc.
# get_daily_tier(level) returns the correct tier dict.

DAILY_TIERS: list[dict] = [
    {"min_level":    1, "money_min":         500, "money_max":         2_000, "gems_min":   3, "gems_max":    8},
    {"min_level":   50, "money_min":       2_000, "money_max":        10_000, "gems_min":   5, "gems_max":   12},
    {"min_level":  100, "money_min":      10_000, "money_max":        50_000, "gems_min":   8, "gems_max":   18},
    {"min_level":  250, "money_min":      50_000, "money_max":       200_000, "gems_min":  12, "gems_max":   25},
    {"min_level":  500, "money_min":     200_000, "money_max":     1_000_000, "gems_min":  18, "gems_max":   40},
    {"min_level": 1000, "money_min":   1_000_000, "money_max":    10_000_000, "gems_min":  30, "gems_max":   65},
    {"min_level": 1200, "money_min":  10_000_000, "money_max":   100_000_000, "gems_min":  50, "gems_max":  110},
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

# Weighted wheel — mirrors real roulette (red/black common, green rare).
# ROULETTE_BET_TYPES: name -> (label, wheel_weight_pct, payout_multiplier)
ROULETTE_BET_TYPES = {
    "red":   ("🔴 Red",   47, 2),
    "black": ("⚫ Black", 47, 2),
    "green": ("🟢 Green",  6, 15),
}
ROULETTE_COLORS  = list(ROULETTE_BET_TYPES.keys())
ROULETTE_WEIGHTS = [v[1] for v in ROULETTE_BET_TYPES.values()]

RPS_CHOICES = {"rock": "✊", "paper": "🖐️", "scissors": "✌️"}
RPS_BEATS   = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

# (min_bet, max_bet, win_chance_pct, win_multiplier)
# Multipliers tuned so every biome pays back ~0.92 per ◈ staked (a small,
# consistent house edge — no biome is a money printer).
SLOT_BIOME_CONFIG = {
    "village":             (        100,         10_000, 45, 2.0),
    "forest":              (        500,         50_000, 42, 2.2),
    "woods":               (      1_000,        100_000, 40, 2.3),
    "small_desert":        (      2_500,        250_000, 37, 2.5),
    "sunken_coast":        (      5_000,        500_000, 35, 2.6),
    "tundra":              (     10_000,      1_000_000, 32, 2.9),
    "jungle":              (     25_000,      2_500_000, 30, 3.1),
    "swamp":               (     50_000,      5_000_000, 28, 3.3),
    "volcanic_highlands":  (    100_000,     10_000_000, 25, 3.7),
    "cursed_ruins":        (    250_000,     25_000_000, 22, 4.2),
    "rainbow":             (    500_000,     50_000_000, 18, 5.1),
    "abyssal_depths":      (  1_000_000,    100_000_000, 15, 6.2),
    "celestial_peaks":     (  2_500_000,    250_000_000, 12, 7.7),
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
    "Unlock new biomes as you level up, then travel there with /world!",
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
}


# ─────────────────────────────────────────────
# BADGES
# ─────────────────────────────────────────────

# `icon` → EMOJI keys "badge_<icon>_gold" / "badge_<icon>_plat".
# `tracks` → plain-English description of the stat (shown in /info).
# `blurb`  → a funny one-liner (shown in /info).
BADGES = {
    "ammo_master":      {"label": "Ammo Master",         "abbr": "AM", "stat": "ammo_used",        "gold": 1_000_000, "plat": 5_000_000, "icon": "ammo_master",
                         "tracks": "Total ammo rounds fired while hunting",
                         "blurb": "You have personally littered the wilderness with enough shell casings to qualify as a landfill."},
    "ammo_variety":     {"label": "Ammo Variety",        "abbr": "AV", "stat": "ammo_variety",     "gold": 1,         "plat": None,      "icon": "ammo_variety",
                         "tracks": "Fire at least one of every ammo type",
                         "blurb": "Tried every kind of ammo at least once. Commitment issues, but make it tactical."},
    "daily_daily_g":    {"label": "Daily Daily",         "abbr": "DD", "stat": "daily_streak",     "gold": 730,       "plat": 1825,      "icon": "daily_daily",
                         "tracks": "Consecutive days claiming your daily reward",
                         "blurb": "Two straight years of pressing one button every single day. Streaks like this end marriages."},
    "legendary_hunter": {"label": "Legendary Hunter",    "abbr": "LH", "stat": "animals_caught",   "gold": 1_000_000, "plat": 5_000_000, "icon": "legendary_hunter",
                         "tracks": "Total animals and creatures caught",
                         "blurb": "A million kills. The local wildlife has started filing restraining orders."},
    "game_master":      {"label": "Game Master",         "abbr": "GM", "stat": "game_master",      "gold": 1,         "plat": 2,         "icon": "game_master",
                         "tracks": "Reach Platinum on every gambling badge",
                         "blurb": "Platinumed every game in the casino. The house would like a word — and its money back."},
    "bj_dealer":        {"label": "Blackjack Dealer",    "abbr": "BD", "stat": "bj_wins",          "gold": 10_000,    "plat": 100_000,   "icon": "blackjack_dealer",
                         "tracks": "Blackjack hands won",
                         "blurb": "So many blackjack wins the dealer leaves the table when you sit down."},
    "cf_tosser":        {"label": "Coinflip Tosser",     "abbr": "CT", "stat": "cf_wins",          "gold": 10_000,    "plat": 100_000,   "icon": "coinflip_tosser",
                         "tracks": "Coinflips won",
                         "blurb": "Ten thousand coin flips. That coin has seen things."},
    "rl_spinner":       {"label": "Roulette Spinner",    "abbr": "RS", "stat": "rl_wins",          "gold": 10_000,    "plat": 100_000,   "icon": "roulette_spinner",
                         "tracks": "Roulette rounds won",
                         "blurb": "You spin that wheel like rent is due. It usually is."},
    "slots_machine":    {"label": "Slots Human-Machine", "abbr": "SH", "stat": "slots_wins",       "gold": 10_000,    "plat": 100_000,   "icon": "slots_human_machine",
                         "tracks": "Slots spins won",
                         "blurb": "At this point you and the slot machine share a bank account."},
    "rps_npc":          {"label": "RPS NPC",             "abbr": "RN", "stat": "rps_wins",         "gold": 10_000,    "plat": 100_000,   "icon": "rps_npc",
                         "tracks": "Rock-Paper-Scissors rounds won",
                         "blurb": "Beat a random number generator at rock-paper-scissors ten thousand times. Somehow."},
    "lottery_winner":   {"label": "Lottery Winner",      "abbr": "LW", "stat": "lottery_wins",     "gold": 100,       "plat": 1_000,     "icon": "lottery_winner",
                         "tracks": "Lottery draws won",
                         "blurb": "Won the lottery more times than statistics technically permits. We're watching you."},
    "prestige_master":  {"label": "Prestige Master",     "abbr": "PM", "stat": "prestige",         "gold": 10,        "plat": 50,        "icon": "prestige_master",
                         "tracks": "Times you have prestiged",
                         "blurb": "Threw away everything you built, on purpose, dozens of times. Very healthy."},
    "xp_explosion":     {"label": "XP Explosion",        "abbr": "XE", "stat": "total_xp_earned",  "gold": 100_000,   "plat": 500_000,   "icon": "xp_explosion",
                         "tracks": "Lifetime XP earned",
                         "blurb": "Earned so much XP the number briefly became a fire hazard."},
    "events_completer": {"label": "Events Completer",    "abbr": "EC", "stat": "events_completed", "gold": 10,        "plat": 20,        "icon": "events_completer",
                         "tracks": "Global events completed",
                         "blurb": "Showed up to every event. The only one who did. Every time."},
    "leveler":          {"label": "Leveler",             "abbr": "LV", "stat": "level",            "gold": 1_000,     "plat": 10_000,    "icon": "leveler",
                         "tracks": "Your hunter level",
                         "blurb": "Level ten thousand. There is no biome left for you. There is only the grind."},
    "crate_master":     {"label": "Crate Master",        "abbr": "CM", "stat": "crates_opened",    "gold": 100,       "plat": 1_000,     "icon": "crate_master",
                         "tracks": "Hunting crates opened",
                         "blurb": "Opened a thousand crates chasing a feeling. The feeling was cardboard."},
    "myth_hunter":      {"label": "Myth Hunter",         "abbr": "MH", "stat": "myths_killed",     "gold": 25,        "plat": 250,       "icon": "myth_hunter",
                         "tracks": "Mythical creatures slain",
                         "blurb": "Put down enough cryptids that Bigfoot now hunts YOU for sport."},
}

# ── SPECIAL BADGES — handed out by admins, not earned by a stat ──────────────
# Deliberately NOT part of BADGES: the achievement checker and the "all badges
# platinum → Game Master" logic both iterate BADGES and must never see these.
# Stored on the player as data[uid]["special_badges"] = [key, ...].
SPECIAL_BADGES = {
    "special_recon": {"label": "Special Recon", "abbr": "SR", "emoji": "badge_special_recon",
                      "blurb": "Handed out by the devs for reconnaissance above and beyond."},
    "tester_badge":  {"label": "Tester",        "abbr": "TS", "emoji": "badge_tester",
                      "blurb": "Broke the game on purpose so you don't have to."},
    "bug_hunter":    {"label": "Bug Hunter",    "abbr": "BH", "emoji": "badge_bug_hunter",
                      "blurb": "Found the bugs the QA testers missed."},
    # ── Event cosmetic badges (earned by playing global events, not admin-granted) ──
    "event_fox":     {"label": "Outfoxed",      "abbr": "FOX", "emoji": "badge_event_fox",
                      "blurb": "Ran the Thieving Fox down without losing the trail once."},
    "event_anchor":  {"label": "Wreck Diver",   "abbr": "WRK", "emoji": "badge_event_anchor",
                      "blurb": "Hauled salvage out of the Shipwreck Scramble."},
    "event_duck":    {"label": "Bread Winner",  "abbr": "DUK", "emoji": "badge_event_duck",
                      "blurb": "Helped settle the Great Duck Takeover."},
    # ── Referral cosmetic badges (earned by bringing hunters in, Phase 39) ──
    "recruiter":        {"label": "Recruiter",        "abbr": "RCR", "emoji": "badge_recruiter",
                         "blurb": "Brought three hunters into the world — and they stayed."},
    "master_recruiter": {"label": "Master Recruiter", "abbr": "MRC", "emoji": "badge_master_recruiter",
                         "blurb": "Twenty-five hunters owe their first shot to you."},
}

def badge_emoji(badge_key: str, tier: int) -> str:
    """Custom emoji for a badge tier — tier 1 = gold, 2 = platinum. '' if unset.
    Special (admin-granted) badges have no tiers and resolve to a single emoji."""
    if badge_key in SPECIAL_BADGES:
        return EMOJI.get(SPECIAL_BADGES[badge_key]["emoji"], "")
    icon = BADGES.get(badge_key, {}).get("icon", badge_key)
    return EMOJI.get(f"badge_{icon}_{'plat' if tier >= 2 else 'gold'}", "")

def badge_meta(badge_key: str) -> dict:
    """The definition for a badge key from either registry ({} if unknown)."""
    return BADGES.get(badge_key) or SPECIAL_BADGES.get(badge_key, {})


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
        (     100,  [("money",           1_000_000), ("gems",                   40)]),
        (     183,  [("money",           5_000_000)]),
        (     365,  [("money",          10_000_000), ("gems",                  110)]),
        (     500,  [("money",         100_000_000), ("gems",                  160)]),
        (     666,  [("money",         666_666_666), ("gems",                  220)]),
        (     730,  [("money",                   0)]),   # title-only tier
        (   1_000,  [("money",       1_000_000_000)]),
        (   1_827,  [("money",      10_000_000_000), ("gems",                  350)]),
        (   2_557,  [("money",     100_000_000_000)]),
        (   3_652,  [("money",   1_000_000_000_000), ("gems",                2_500)]),
    ],

    # ── Animals Caught ────────────────────────────────────────────
    "animals_caught": [
        (       100, [("money",              50_000)]),
        (       250, [("money",             100_000)]),
        (       500, [("money",             500_000)]),
        (     1_000, [("gems",                   80)]),
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
        (10_000_000, [("gems",                2_500)]),
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
        (    100, [("gems",                120)]),
        (    250, [("money",       100_000_000)]),
        (    500, [("money",       500_000_000)]),
        (  1_000, [("money",     1_000_000_000), ("gems",                300)]),
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
            except (ValueError, OverflowError):   # "1e999", "inf", "nan"
                return None
    try:
        return int(float(raw))
    except (ValueError, OverflowError):
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
#   max_count   – optional hard ceiling on the tier-scaled count. Without this,
#                 a single global count_mult (1x -> 35x across tiers) turns a
#                 10-hunt quest into 350 hunts at Legend, or a "catch one
#                 specific animal" quest into 175 attempts at pure RNG. Each
#                 repeated-action template gets its own ceiling instead so
#                 high tiers stay completable in a session — the bigger XP
#                 payoff (xp_mult still climbs to 18x) is what makes a
#                 high-tier quest better, not a bigger grind. Pure currency/XP
#                 thresholds (earn_money, earn_xp) have no cap: those scale
#                 with the player's actual power level, not click-count.
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
        "icon":        emoji('bow'),
        "stat":        "hunts_done",
        "base_count":  10,
        "base_xp":     400,
        "base_money":  5_000,
        "max_count":   60,
    },
    {
        "id":          "hunt_biome",
        "description": "Hunt **{count}** times in the **{biome_name}** biome.",
        "icon":        emoji('earth'),
        "stat":        "hunts_in_biome",
        "base_count":  8,
        "base_xp":     550,
        "base_money":  6_000,
        "max_count":   48,
        "requires":    {"biome": True},   # True = pick a random biome at gen time
    },
    {
        "id":          "catch_any",
        "description": "Catch **{count}** animals (any kind).",
        "icon":        "🐾",
        "stat":        "animals_caught",
        "base_count":  15,
        "base_xp":     500,
        "base_money":  6_000,
        "max_count":   90,
    },
    {
        "id":          "catch_specific",
        "description": "Catch **{count}** **{animal}**.",
        "icon":        "🦌",
        "stat":        "animal_caught_specific",
        "base_count":  5,
        "base_xp":     700,
        "base_money":  8_000,
        "max_count":   15,   # a single named species is narrow RNG — 35x would be ~175
        "requires":    {"animal": True},   # True = pick a random animal at gen time
    },
    {
        "id":          "catch_rarity",
        "description": "Catch **{count}** animals of **{rarity}** rarity or higher.",
        "icon":        "⭐",
        "stat":        "rarity_caught",
        "base_count":  8,
        "base_xp":     800,
        "base_money":  10_000,
        "bonus_gems":  2, "bonus_chance": 0.3,   # rare+ catches deserve a shot at gems
        "max_count":   20,   # rare+ catches are inherently scarce
        "requires":    {"rarity": True},
    },
    {
        "id":          "perfect_catch",
        "description": "Land **{count}** Perfect Catches (rare bonus).",
        "icon":        "✨",
        "stat":        "perfect_catches",
        "base_count":  3,
        "base_xp":     900,
        "base_money":  12_000,
        "bonus_gems":  3, "bonus_chance": 0.4,   # already a low-probability bonus catch
        "max_count":   8,
    },
    # ── Tools ─────────────────────────────────
    {
        "id":          "use_tool_tier",
        "description": "Hunt **{count}** times using a Tier **{tier}**+ tool.",
        "icon":        emoji('equipment'),
        "stat":        "tool_tier_hunts",
        "base_count":  10,
        "base_xp":     600,
        "base_money":  7_000,
        "max_count":   60,
        "requires":    {"tool_tier_min": True},
    },
    {
        "id":          "use_ammo",
        "description": "Use **{count}** ammo rounds while hunting.",
        "icon":        emoji('target'),
        "stat":        "ammo_used_quest",
        "base_count":  20,
        "base_xp":     500,
        "base_money":  6_000,
        "max_count":   120,
    },
    # ── Crates ────────────────────────────────
    {
        "id":          "open_crate_any",
        "description": "Open **{count}** crates (any tier).",
        "icon":        emoji('crate_sample'),
        "stat":        "crates_opened_quest",
        "base_count":  3,
        "base_xp":     1200,
        "base_money":  15_000,
        "max_count":   18,
    },
    {
        "id":          "open_crate_tier",
        "description": "Open **{count}** **{crate_tier}**.",
        "icon":        emoji('crate_sample'),
        "stat":        "crate_tier_opened",
        "base_count":  2,
        "base_xp":     1500,
        "base_money":  18_000,
        "bonus_crate": "Rare Crate", "bonus_chance": 0.5,
        "max_count":   6,    # a SPECIFIC tier (e.g. Legendary Crate) is scarcer than "any"
        "requires":    {"crate_tier": True},
    },
    {
        "id":          "drop_crate",
        "description": "Find **{count}** shard/crate drop(s) while hunting.",
        "icon":        emoji('gift'),
        "stat":        "crate_drops_earned",
        "base_count":  4,
        "base_xp":     1000,
        "base_money":  12_000,
        "max_count":   24,
    },
    # ── Economy ───────────────────────────────
    {
        "id":          "earn_money",
        "description": "Earn **◈ {money_fmt}** from selling animals.",
        "icon":        emoji('money_bag'),
        "stat":        "money_earned_quest",
        "base_count":  100_000,
        "base_xp":     600,
        "base_money":  8_000,
        # No max_count: a currency threshold scales with the player's actual
        # earning power at that tier, unlike a repeated-action count.
    },
    {
        "id":          "sell_animals",
        "description": "Sell **{count}** animals from your inventory.",
        "icon":        "🏪",
        "stat":        "animals_sold_quest",
        "base_count":  30,
        "base_xp":     450,
        "base_money":  5_000,
        "max_count":   120,
    },
    # ── XP / Level ────────────────────────────
    {
        "id":          "earn_xp",
        "description": "Earn **{xp_fmt} XP** from any activity.",
        "icon":        emoji('xp'),
        "stat":        "xp_earned_quest",
        "base_count":  5_000,
        "base_xp":     700,
        "base_money":  7_000,
        # No max_count — see earn_money.
    },
    {
        "id":          "level_up",
        "description": "Level up **{count}** time(s).",
        "icon":        emoji('level_up'),
        "stat":        "levels_gained_quest",
        "base_count":  1,
        "base_xp":     1000,
        "base_money":  10_000,
        "max_count":   3,    # the XP curve makes each level cost far more at high tiers
    },
    # ── Daily / Streak ────────────────────────
    {
        "id":          "claim_daily",
        "description": "Claim your daily reward **{count}** time(s).",
        "icon":        emoji('daily'),
        "stat":        "dailies_claimed_quest",
        "base_count":  1,
        "base_xp":     500,
        "base_money":  5_000,
        "max_count":   3,    # a "daily" quest spanning weeks defeats the point
    },
    # ── Idle ──────────────────────────────────
    {
        "id":          "collect_idle",
        "description": "Collect from your idle worker **{count}** time(s).",
        "icon":        emoji('idle_camp'),
        "stat":        "idle_collections_quest",
        "base_count":  3,
        "base_xp":     400,
        "base_money":  5_000,
        "max_count":   18,
    },
    # ── Meta quests ───────────────────────────
    {
        "id":          "complete_quests",
        "description": "Complete **{count}** other quest(s) today.",
        "icon":        emoji('list'),
        "stat":        "quests_completed_today",
        "base_count":  2,
        "base_xp":     1500,
        "base_money":  20_000,
        "bonus_gems":  5, "bonus_chance": 1.0,   # the capstone quest — always pays gems
        "max_count":   4,    # QUESTS_PER_DAY=3 — this must stay reachable at all
    },
]

# ─────────────────────────────────────────────
# WEEKLY QUESTS  ·  same engine as dailies (generate_quest), bigger targets,
# a 7-day window, and rewards that lean harder into gems/crates so the
# weekly panel feels like the "big" payout, not just a scaled-up daily.
# `maintain_streak` lives here, not in the daily pool — a streak inherently
# takes multiple real days to build, which never made sense as a quest that
# resets every 24h.
# ─────────────────────────────────────────────
QUESTS_PER_WEEK = 2
WEEKLY_QUESTS_MAX = 6   # 3 weeks' worth before rolls stop piling up unclaimed

# Lifetime "daily quests claimed" milestones — a cumulative track alongside
# the daily/weekly queues, since a single completion count that never resets
# is the one shape a per-day or per-week reward can't cover: something that
# rewards long-term grinding at quests specifically. (threshold, gem_reward).
DAILY_QUEST_MILESTONES = [
    (10,  50),
    (20,  100),
    (40,  250),
    (75,  500),
    (150, 1000),
    (300, 2000),
    (500, 4000),
]
WEEKLY_QUEST_TEMPLATES = [
    {
        "id":          "maintain_streak",
        "description": "Reach a daily streak of **{count}** days.",
        "icon":        emoji('fire'),
        "stat":        "daily_streak_reached",
        "base_count":  5,
        "base_xp":     3000,
        "base_money":  30_000,
        "bonus_gems":  4, "bonus_chance": 0.6,
        "max_count":   7,    # a full week — matches the quest's own window
    },
    {
        "id":          "weekly_hunts",
        "description": "Go on **{count}** hunts this week.",
        "icon":        emoji('bow'),
        "stat":        "hunts_done",
        "base_count":  120,
        "base_xp":     4000,
        "base_money":  40_000,
        "bonus_gems":  4, "bonus_chance": 0.5,
        "max_count":   600,
    },
    {
        "id":          "weekly_money",
        "description": "Earn **◈ {money_fmt}** from selling animals this week.",
        "icon":        emoji('money_bag'),
        "stat":        "money_earned_quest",
        "base_count":  1_000_000,
        "base_xp":     3500,
        "base_money":  35_000,
        "bonus_gems":  5, "bonus_chance": 0.5,
        # No max_count — see earn_money's daily equivalent.
    },
    {
        "id":          "weekly_crates",
        "description": "Open **{count}** crates (any tier) this week.",
        "icon":        emoji('crate_sample'),
        "stat":        "crates_opened_quest",
        "base_count":  15,
        "base_xp":     4500,
        "base_money":  45_000,
        "bonus_crate": "Epic Crate", "bonus_chance": 0.5,
        "max_count":   80,
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

    # Money scales continuously with the player's own level on top of the
    # tier step, not just the 5-rung tier ladder — a level 49 hitting the
    # ceiling of the Easy bracket got the exact same payout as a level 2
    # before this, which felt stale. +2% per level, so it's a real curve
    # across a whole tier band instead of 5 flat plateaus.
    level_mult   = 1 + max(0, level) * 0.02
    money_reward = int(t.get("base_money", 0) * tier["xp_mult"] * level_mult)

    # Harder templates get a shot at a gems or crate bonus on top of the
    # money/XP — rolled once at generation time (not claim time) so the
    # quest panel can show the full reward up front instead of surprising
    # the player after they've already put the work in.
    gems_reward  = 0
    crate_reward = None
    if rng.random() < t.get("bonus_chance", 0):
        if t.get("bonus_gems"):
            gems_reward = max(1, int(t["bonus_gems"] * max(1.0, tier["xp_mult"] ** 0.5)))
        if t.get("bonus_crate"):
            crate_reward = t["bonus_crate"]

    # Clamp count to a reasonable minimum, and to this template's own ceiling
    # (if any) — see the "max_count" note above QUEST_TEMPLATES. XP keeps
    # scaling with the full tier multiplier either way.
    raw_count = max(1, raw_count)
    if "max_count" in t:
        raw_count = min(raw_count, t["max_count"])
 
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
        resolved["crate_tier"] = rng.choice(
            ["Common Crate", "Uncommon Crate", "Rare Crate", "Epic Crate", "Legendary Crate"])
 
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
        "money_reward": money_reward,
        "gems_reward":  gems_reward,
        "crate_reward": crate_reward,
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


def roll_weekly_quests(level: int, existing_templates: list[str]) -> list[dict]:
    """Same engine as roll_daily_quests, drawing from WEEKLY_QUEST_TEMPLATES."""
    import random as _r, time as _t

    pool = [t for t in WEEKLY_QUEST_TEMPLATES if t["id"] not in existing_templates]
    if not pool:
        pool = list(WEEKLY_QUEST_TEMPLATES)

    chosen = _r.sample(pool, min(QUESTS_PER_WEEK, len(pool)))
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


# ═══════════════════════════════════════════════════════════════
# PLAYER HEALTH & ANIMAL COMBAT  ·  Idle Hunter V2.1
# ═══════════════════════════════════════════════════════════════
# HP is a real persistent player stat (data[uid]["health"]) — the SAME pool
# both normal dangerous-animal fights and mythic boss fights draw from and
# damage. Regeneration is computed lazily (see app.refresh_health), never a
# background loop.

PLAYER_BASE_HP        = 100
HP_REGEN_PER_MIN      = 4
CAMP_HP_REGEN_PER_MIN = 8    # idle camp active, or Rookie Rush window
KO_RECOVERY_HP        = 40   # HP you wake up with after a normal-animal KO
ROOKIE_KO_RECOVERY_HP = 50   # ...the first time, before rookie protection is spent

# Per-encounter behavior. `attack_chance` is the animal's odds of landing a hit
# on its turn; `flee_chance` is the odds it just bolts before any fight starts
# (rolled once, the moment it's picked as the encounter).
ANIMAL_BEHAVIORS = {
    "passive":    {"attack_chance": 0.00, "flee_chance": 0.15},
    "skittish":   {"attack_chance": 0.00, "flee_chance": 0.35},
    "defensive":  {"attack_chance": 0.20, "flee_chance": 0.05},
    "aggressive": {"attack_chance": 0.50, "flee_chance": 0.00},
    "predator":   {"attack_chance": 0.65, "flee_chance": 0.00},
}

# Rarity is the fallback signal for any animal without a hand-authored entry
# below — NOT the only signal (a legendary butterfly shouldn't maul anyone).
RARITY_DEFAULT_BEHAVIOR = {
    "common": "passive", "uncommon": "skittish", "rare": "defensive",
    "epic": "aggressive", "legendary": "predator",
}
RARITY_HP = {"common": 12, "uncommon": 22, "rare": 40, "epic": 60, "legendary": 110}
RARITY_DAMAGE = {
    "common": (0, 0), "uncommon": (1, 3), "rare": (3, 7),
    "epic": (6, 13), "legendary": (10, 20),
}
# Odds a single rolled animal of this rarity becomes THIS hunt's one
# interactive encounter (checked per-animal; only the highest-priority
# eligible one is actually used — see encounter_priority()). Common/uncommon/
# rare never fight back — normal hunting stays fast; only epic and legendary
# are rare bonus moments. Mythic isn't in this table at all — it's a fully
# separate, always-guaranteed encounter (see MYTH_ENCOUNTER_* in app.py).
RARITY_ENCOUNTER_CHANCE = {
    "common": 0.0, "uncommon": 0.0, "rare": 0.0, "epic": 0.03, "legendary": 0.12,
}
RARITY_PRIORITY   = {"common": 0, "uncommon": 5, "rare": 15, "epic": 30, "legendary": 50}
BEHAVIOR_PRIORITY = {"passive": 0, "skittish": 2, "defensive": 5, "aggressive": 15, "predator": 20}
# After an epic/legendary encounter resolves (win/lose/leave), this many
# hunts pass with encounters disabled before the roll resumes — keeps a run
# of bad luck from chaining several fights back to back. Mythic ignores this.
MIN_ENCOUNTER_HUNTS_GAP = 6
# Payout multiplier on an animal-encounter win, applied to the animal's
# normal sell value (replaces the old flat 25% "danger premium" — a real
# fight is now worth fighting for). +HEALTHY_BONUS on top if you finish the
# fight above 75% HP. XP uses its own, much smaller multiplier below — at
# 10x, a single win on a high-XP animal could out-earn a mythic kill.
ANIMAL_ENCOUNTER_REWARD_MULT   = 10.0
ANIMAL_ENCOUNTER_XP_MULT       = 2.0
ANIMAL_ENCOUNTER_HEALTHY_BONUS = 0.10
# Power Attack: a single-turn, higher-risk swing (vs. the reliable Attack).
POWER_ATTACK_ACCURACY     = 0.70
POWER_ATTACK_DAMAGE_MULT  = 1.6

# Hand-authored overrides for animals that should feel distinctly themselves.
# Anything not listed here derives hp/damage/behavior from its rarity via
# animal_combat_stats() below.
ANIMAL_COMBAT = {
    # Pacific Northwest (village) — where onboarding happens
    "Western Coyote":    {"behavior": "defensive",  "hp": 40, "damage": (4, 9)},
    "Red Fox":           {"behavior": "skittish",   "hp": 25, "damage": (2, 5)},
    "Striped Skunk":     {"behavior": "defensive",  "hp": 20, "damage": (2, 6)},
    "Common Raccoon":    {"behavior": "defensive",  "hp": 22, "damage": (2, 6)},
    # The British Isles / Scandinavia (forest / woods)
    "British Grey Wolf": {"behavior": "predator",   "hp": 70, "damage": (8, 16)},
    "Eurasian Lynx":     {"behavior": "predator",   "hp": 65, "damage": (9, 17)},
    "Eurasian Boar":     {"behavior": "aggressive", "hp": 55, "damage": (6, 13)},
    "Eurasian Badger":   {"behavior": "defensive",  "hp": 30, "damage": (3, 8)},
}


def animal_combat_stats(animal: str) -> dict:
    """Resolved combat profile for one animal — override first, rarity fallback."""
    ov = ANIMAL_COMBAT.get(animal, {})
    rarity = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
    behavior = ov.get("behavior") or RARITY_DEFAULT_BEHAVIOR.get(rarity, "passive")
    hp  = ov.get("hp")  or RARITY_HP.get(rarity, 12)
    dmg = ov.get("damage") or RARITY_DAMAGE.get(rarity, (0, 0))
    beh = ANIMAL_BEHAVIORS.get(behavior, ANIMAL_BEHAVIORS["passive"])
    return {
        "behavior": behavior, "hp": int(hp), "damage": tuple(dmg), "rarity": rarity,
        "attack_chance": beh["attack_chance"], "flee_chance": beh["flee_chance"],
    }


def animal_encounter_chance(animal: str) -> float:
    rarity = ANIMAL_DATA.get(animal, {}).get("rarity", "common")
    return RARITY_ENCOUNTER_CHANCE.get(rarity, 0.0)


def encounter_priority(animal: str) -> int:
    """Which rolled animal becomes THE encounter when more than one qualifies."""
    st = animal_combat_stats(animal)
    return RARITY_PRIORITY.get(st["rarity"], 0) + BEHAVIOR_PRIORITY.get(st["behavior"], 0)


# ── Weapon combat damage — derives from tool tier, a few weapons overridden ──
TOOL_COMBAT_OVERRIDES = {
    "Shotgun":       {"damage_mult": 1.35, "accuracy": 0.75},
    "Sniper Rifle":  {"damage_mult": 1.50, "accuracy": 0.95},
    "Hunting Knife": {"damage_mult": 0.85, "accuracy": 0.95},
}
TOOL_COMBAT_BASE_ACCURACY  = 0.85
TOOL_COMBAT_MAX_TIER       = 20   # clamp so an outlier tier (e.g. 100) stays sane


def tool_combat_damage(tool_name: str) -> tuple[int, int]:
    tier = min(TOOLS.get(tool_name, {}).get("tier", 1), TOOL_COMBAT_MAX_TIER)
    lo, hi = 5 + tier * 4, 10 + tier * 6
    mult = TOOL_COMBAT_OVERRIDES.get(tool_name, {}).get("damage_mult", 1.0)
    return max(1, int(lo * mult)), max(1, int(hi * mult))


def tool_combat_accuracy(tool_name: str) -> float:
    return TOOL_COMBAT_OVERRIDES.get(tool_name, {}).get("accuracy", TOOL_COMBAT_BASE_ACCURACY)


# ── Healing items ─────────────────────────────────────────────
# ~10,000 gold per HP — deliberately steep now that animal encounters are a
# rare, high-value bonus (10x payout, mostly Legendary): healing should cost
# a real slice of what you just won, not be pocket change off ambient hunting.
HEALING_ITEMS = {
    "Bandage":       {"heal": 25,  "price": 250_000,  "emoji": "🩹"},
    "First Aid Kit": {"heal": 60,  "price": 600_000,  "emoji": "🧰"},
    "Field Medkit":  {"heal": 100, "price": 1_000_000, "emoji": "⛑️"},
}
HEALING_ITEMS["Field Medkit"]["emoji"] = EMOJI.get("potion_bottle") or HEALING_ITEMS["Field Medkit"]["emoji"]

# ── The trial weapon (first-session onboarding, Plan B) ──
# Rookie Rush (a separate 15-min auto-granted xp/luck/sell boost) was folded
# into the chosen Starter Pack above — new players used to see two welcome
# boosts ticking down side by side, which was confusing for no real benefit.
TRIAL_TOOL_MIN      = 5
TRIAL_TOOL          = "Shortbow"

ROOKIE_GOALS = {
    "catch_5":       {"label": "Catch 5 animals",           "emoji": "🐾"},
    "reach_level_5": {"label": "Reach Level 5",              "emoji": "⭐"},
    "discover_5":    {"label": "Discover 5 species",         "emoji": "📖"},
    "buy_tool":      {"label": "Buy your first tool",        "emoji": "🛠️"},
    "view_world":    {"label": "Check the World screen",     "emoji": "🌎"},
}

# ── Hunter's Path — the first-hour progression spine (2026-09-15) ───────────
# Originally a 4-step post-onboarding checklist; expanded per design review
# into the actual backbone of the first hour, since the real problem was
# never "too much tutorial" — it was a beginner finishing onboarding with
# only /hunt and no reason to touch anything else. Onboarding V2 still owns
# the very first hunt/sell/trial-tool beat; this picks up right after it and
# walks through every system in the game once, in order, each step paying
# out something real (money, gems, or a crate) instead of just checking a
# box, so nothing in the first hour is a dead end.
# Every completion is a LIVE check against state the game already tracks
# (rookie_goals.buy_tool, tools_used, last_daily_date, a lifetime quest-claim
# marker, guide_seen length, idle stack count, etc.) — never a separately
# stored progress counter, so it can't desync from what actually happened.
# "Equip your tool" is deliberately not its own step: buying a tool already
# auto-equips it in this game, so a standalone equip step would just be
# busywork with no real action behind it.
HUNTERS_PATH_STEPS = [
    {"key": "buy_tool",         "label": "Buy your first real tool",
     "emoji": "🛠️", "panel": "shop",
     "hint": "Open `/shop` and buy a tool — it equips automatically.",
     "reward": {"gems": 10}},
    {"key": "hunt_with_tool",   "label": "Hunt with your new tool",
     "emoji": "🏹", "panel": "menu",
     "hint": "Use `/hunt` now that you're properly equipped.",
     "reward": {"money": 500}},
    {"key": "claim_daily",      "label": "Claim your daily reward",
     "emoji": "🎁", "panel": "daily",
     "hint": "Open `/daily` and claim it — free money and XP, once a day.",
     "reward": {"gems": 5}},
    {"key": "complete_quest",   "label": "Complete a quest",
     "emoji": "📜", "panel": "quests",
     "hint": "Open `/quests` and claim one you've already finished.",
     "reward": {"money": 750}},
    {"key": "discover_5",       "label": "Discover 5 species",
     "emoji": "📖", "panel": "guide",
     "hint": "Keep hunting — check `/guide` to see how many you've found.",
     "reward": {"crate": "Common Crate"}},
    {"key": "open_crate",       "label": "Open your first crate",
     "emoji": "📦", "panel": "craft",
     "hint": "Open `/craft` and use a crate you've picked up from hunting.",
     "reward": {"gems": 10}},
    {"key": "travel",           "label": "Travel to a new region",
     "emoji": "🌍", "panel": "world",
     "hint": "Open `/world` and travel somewhere new.",
     "reward": {"money": 1000}},
    {"key": "catch_new_region", "label": "Catch something new there",
     "emoji": "🐾", "panel": "menu",
     "hint": "Hunt in your new region — its animals aren't found in the Village.",
     "reward": {"crate": "Uncommon Crate"}},
    {"key": "start_camp",       "label": "Station a Hunting Camp",
     "emoji": "🏕️", "panel": "idle",
     "hint": "Open `/idle` and station a hunter — they catch while you're away.",
     "reward": {"gems": 10}},
    {"key": "check_camp",       "label": "Check in on your camp",
     "emoji": "🎒", "panel": "idle",
     "hint": "Open `/idle` again and collect what your camp caught.",
     "reward": {"money": 1000}},
    {"key": "first_rare",       "label": "Land a Rare or Epic catch",
     "emoji": "🌟", "panel": "menu",
     "hint": "Keep hunting — a rarer catch pays out a lot more.",
     "reward": {"gems": 20}},
    {"key": "myth_lead",        "label": "Find your first Mythical lead",
     "emoji": "👹", "panel": "menu",
     "hint": "Keep hunting — cryptid sightings start showing up from here.",
     "reward": {"gems": 30}},
]
HUNTERS_PATH_REWARD_GEMS = 100
HUNTERS_PATH_REWARD_TITLE = "Path Walker"
# Mythics stay suppressed only through the earlier stretch of the Path
# (current_step below this index), so the final "myth_lead" step is actually
# reachable instead of permanently gated — see hunters_path_myths_allowed()
# in app.py. current_step reaches 7 only once step 6 ("travel") is DONE.
HUNTERS_PATH_MYTH_UNLOCK_STEP = 7
