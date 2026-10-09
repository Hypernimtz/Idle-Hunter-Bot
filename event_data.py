"""
Idle Hunter — event content: the storyline, the 15 quest events, the daily themes,
cosmetic rewards and the puzzle tables.

Pure data. Nothing in here imports the bot, game_data or discord, so it can be read,
tested and tweaked in isolation. The engine that runs it lives in app.py ("EVENTS V3").

DESIGN RULES (every event follows them):
  * Events change WHAT players do, not what things cost. No price cuts, no doubled income,
    no zero-cooldown, no free ammo.
  * Every event has a fixed per-player reward budget: `token_cap` event tokens, and at most
    `crates` finished crates. Event tokens are not tradable and only buy cosmetics (plus the
    one capped crate).
  * Rewards are titles, badges, keepsakes (profile decorations) and story chapters.
"""

# ════════════════════════════════════════════════════════════════
#  THE STORY  ·  "The Hollow Star"
# ════════════════════════════════════════════════════════════════
SEASON = {
    "title": "The Hollow Star",
    "tagline": "A star fell on the Wilds. It didn't go out.",
    "prologue": (
        "Eleven nights ago a star fell on the Wilds. It did not burn out. It's still down there in the "
        "crater, humming — and everything the hunters thought they knew about the land is slowly going wrong.\n\n"
        "Warden **Ione Marsh** keeps the camp's ledger, and she has a theory: the star is *hollow*. "
        "Something is inside it, and it is waking up. The Wardens call it **the Hollow Star**.\n\n"
        "Every event that visits the Wilds is another page of the same story — hunt, solve, and carry "
        "the camp through it. Your **Chronicle** keeps every page you've unlocked."),
    "epilogue": (
        "The Colossus fell, and the Star went quiet — for now. Ione closes the ledger on a long, strange "
        "season and writes one line on the last page: *the Wilds remember who showed up.*\n\n"
        "Every Saturday the Star's pulse still wakes a husk of the Colossus somewhere in the Wilds. "
        "Somebody has to be there."),
}

CAST = {
    "Ione Marsh": "Warden of the camp. Dry, tired, usually right.",
    "Odalys Venn": "A cartographer who walked into the fog and hasn't been seen since.",
    "The Quartermaster": "Never seen. Supplies simply turn up, labelled in handwriting nobody recognises.",
    "Pip": "The camp's youngest hand. Talks to the animals. They sometimes answer.",
    "The Hollow Stag": "Whatever lives in the Star has borrowed this shape.",
}

# ════════════════════════════════════════════════════════════════
#  COSMETICS  ·  keepsakes are profile decorations
# ════════════════════════════════════════════════════════════════
KEEPSAKES = {
    "cracked_starheart": ("💫", "Cracked Starheart",   "A fragment of the relic. It's warm."),
    "meteorite_chip":    ("🪨", "Meteorite Chip",      "Heavier than it looks."),
    "fog_lantern":       ("🏮", "Fog Lantern",         "Burns blue, and only in the dark."),
    "glitch_cube":       ("🧊", "Glitch Cube",         "Rotates in directions that aren't."),
    "torn_map":          ("🗺️", "Torn Map",            "Half of Odalys Venn's survey."),
    "storm_in_a_jar":    ("🫙", "Storm in a Jar",      "Rattles when you lie."),
    "migration_feather": ("🪶", "Migration Feather",   "Picked up three regions from where it was dropped."),
    "owl_pellet":        ("🦉", "Night Watch Pin",     "For those who stayed up."),
    "plaster_cast":      ("🐾", "Plaster Cast",        "A perfect print of something that shouldn't exist."),
    "bounty_poster":     ("📜", "Bounty Poster",       "Still smells of wet ink."),
    "magnifier":         ("🔍", "Detective's Loupe",   "Everyone looked guilty through it."),
    "ember_bundle":      ("🔥", "Festival Ember",      "Never quite goes out."),
    "arrow_trophy":      ("🏹", "Tournament Arrow",    "Gold-tipped. Entirely ceremonial."),
    "sealed_tag":        ("🏷️", "Quartermaster's Tag", "Handwriting nobody recognises."),
    "baton":             ("🚩", "Relay Baton",         "Passed hand to hand, still warm."),
    "banner_scrap":      ("🏴", "Conquest Banner",     "A scrap from an outpost you held."),
    "husk_horn":         ("📯", "Colossus Horn",       "Hollow. Do not blow."),
    "camp_blanket":      ("🛏️", "Recovery Blanket",    "The camp's own. Very soft."),
}

# Special badges added to game_data.SPECIAL_BADGES: key -> (label, abbr, glyph, blurb)
EVENT_BADGES = {
    "event_meteor":      ("Relic Assembler",  "STR", "☄️", "Assembled the Starheart from the meteor shower."),
    "event_fog":         ("Seer of the Fog",  "FOG", "🌫️", "Saw through the Great Fog."),
    "event_404":         ("Glitch Hunter",    "404", "🐞", "Survived Admin Error 404."),
    "event_cartographer":("Cartographer's Heir","MAP","🗺️", "Finished Odalys Venn's survey."),
    "event_storm":       ("Stormproof",       "STM", "⚡", "Brought the expedition through the storm."),
    "event_migration":   ("Herdkeeper",       "MIG", "🦌", "Filled the migration journal."),
    "event_nightwatch":  ("Night Owl",        "OWL", "🦉", "Kept the Night Watch."),
    "event_tracks":      ("Print Reader",     "TRK", "🐾", "Solved the Tracks of the Unknown."),
    "event_wanted":      ("Bounty Hunter",    "BNT", "📜", "Collected on the Wanted bounty."),
    "event_impostor":    ("Camp Detective",   "DET", "🔍", "Unmasked the saboteur."),
    "event_campfire":    ("Fire Tender",      "FIR", "🔥", "Kept the Festival fire lit."),
    "event_tournament":  ("Tournament Medalist","TRN","🏹", "Placed in the Hunter's Tournament."),
    "event_supply":      ("Quartermaster's Pick","QM","🎲", "Opened every sealed box."),
    "event_relay":       ("Baton Bearer",     "RLY", "🚩", "Carried the beacon for the tribe."),
    "event_conquest":    ("Banner Bearer",    "CON", "🏴", "Fought for the outposts."),
    "event_rampage":     ("Colossus Breaker", "COL", "📯", "Helped bring down a Colossus husk."),
}

# ════════════════════════════════════════════════════════════════
#  THE EVENTS
# ════════════════════════════════════════════════════════════════
# mech:
#   collect   — hunting fills the event journal (impact / survey / migrate sub-modes)
#   scenes    — a short choose-your-path run with two meters
#   clue      — a puzzle with progressive clues (wanted / tracks / night)
#   deduce    — impostor deduction across several days
#   pick      — one sealed box a day
#   community — shared goal with a participation chest
#   tournament— skill rounds, ranked
#   relay / conquest — tribe events
#
# Common fields: key, name, emoji, kind="quest", hours, chapter, blurb, actions (bullets shown on
# the announcement), token (name, singular), token_cap, story [(at, title, text)],
# rewards [(at, {title|badge|keepsake})], shop [{label, cost, title|keepsake|crate}], crates.

def _s(at, title, text):
    return {"at": at, "title": title, "text": text}


EVENT_SPECS = {

# ───────────────────────── 1 ─────────────────────────
"meteor": {
    "key": "meteor", "name": "Meteor Shower", "emoji": "☄️", "icon": "shooting_star", "kind": "quest", "mech": "collect",
    "mode": "impact", "hours": 72, "chapter": 1,
    "blurb": "The sky is falling in pieces. Meteors are hitting different regions — find the impact sites "
             "and gather the fragments of the Starheart before they go cold.",
    "actions": ["Each day three regions are struck. Hunt there to find **Star Fragments**.",
                "Fragments can't be sold or traded — they assemble the relic.",
                "Rewards are a title, a badge and a keepsake. No cash, no multipliers."],
    "token": ("Star Fragments", "star fragment"), "token_cap": 36, "day_cap": 12, "crates": 1,
    "params": {"regions_per_day": 3, "chance": 0.35},
    "intro": ("It started as a streak across the evening sky. Then another. By midnight the Wilds were "
              "being stitched with light, and Ione Marsh was standing on the camp wall with a bucket of water "
              "she'd forgotten to put down.\n\n\"Don't touch anything that's still glowing,\" she says. "
              "\"And bring me every piece you find.\""),
    "story": [
        _s(8, "Warm to the Touch", "The first fragments are warm and faintly *humming*. Ione holds one to her ear "
                                    "and goes very quiet. \"It's the same note,\" she says. \"Every piece. The same note.\""),
        _s(20, "The Pieces Fit", "Laid out on the ledger table, the fragments slide toward each other like iron to a "
                                  "magnet. They're not meteorites. They're a *relic* — shattered, and trying to reassemble."),
        _s(32, "The Starheart", "The last piece clicks home and the relic flares. For one breath, every hunter in the "
                                 "camp sees the same thing: a vast, hollow shape under the crater, turning over in its sleep."),
    ],
    "rewards": [(8, {"title": "Starwatcher"}), (20, {"keepsake": "cracked_starheart"}),
                (32, {"title": "Relic Assembler", "badge": "event_meteor"})],
    "shop": [{"label": "Title: Skyfall Scout", "cost": 6, "title": "Skyfall Scout"},
             {"label": "Keepsake: Meteorite Chip", "cost": 14, "keepsake": "meteorite_chip"},
             {"label": "Title: Crater Walker", "cost": 24, "title": "Crater Walker"},
             {"label": "1× Common Crate (once)", "cost": 20, "crate": "Common Crate"}],
},

# ───────────────────────── 2 ─────────────────────────
"fog": {
    "key": "fog", "name": "The Great Fog", "emoji": "🌫️", "icon": "cyclone", "kind": "quest", "mech": "scenes",
    "hours": 72, "chapter": 2,
    "blurb": "A fog has rolled off the crater and swallowed the Wilds. Lead a short expedition through it — every "
             "turning is a choice, and the fog remembers.",
    "actions": ["Start an **Expedition** (2 a day) and pick your way through five scenes.",
                "Keep both **Clarity** and **Nerve** above zero. Flawless runs earn extra Clues.",
                "Clues unlock the event story and cosmetics. No gold, no boosts."],
    "meters": ("Clarity", "Nerve"), "attempts_day": 2, "scene_pool": "fog",
    "token": ("Clues", "clue"), "token_cap": 24, "crates": 1, "win_progress": 3, "flawless_bonus": 1, "fail_progress": 1,
    "intro": ("The fog arrives all at once, a white wall rolling off the crater, and the first thing it swallows is the "
              "sound. Hunters walk in; hunters walk out *eventually*, quieter than they went.\n\nIone ties a rope to "
              "the camp gate and hands the other end to you. \"If it goes slack,\" she says, \"don't follow it.\""),
    "story": [
        _s(5, "It Breathes", "In the thickest part of the fog the air rises and falls, slow and even. You press your "
                              "palm to a tree and feel it: the fog isn't weather. It's *exhaled*."),
        _s(12, "Footprints in Reverse", "Your own prints lead the wrong way. Someone — something — is walking the trails "
                                         "backwards behind you, wearing your boots. It doesn't hurry."),
        _s(20, "The Source", "At the heart of the fog the crater opens, and the Star looks back. Not an eye. A *hollow*, "
                              "the shape of an eye. The fog begins to thin the moment you stop being afraid of it."),
    ],
    "rewards": [(5, {"title": "Fogwalker"}), (12, {"keepsake": "fog_lantern"}),
                (20, {"title": "Seer of the Fog", "badge": "event_fog"})],
    "shop": [{"label": "Title: Lantern Bearer", "cost": 6, "title": "Lantern Bearer"},
             {"label": "Keepsake: Fog Lantern", "cost": 12, "keepsake": "fog_lantern"},
             {"label": "1× Common Crate (once)", "cost": 18, "crate": "Common Crate"}],
},

# ───────────────────────── 3 ─────────────────────────
"admin_404": {
    "key": "admin_404", "name": "Admin Error 404", "emoji": "🐞", "kind": "quest", "mech": "scenes",
    "hours": 24, "chapter": 3,
    "blurb": "The Star's hum has gotten into the Admin's console. Reality is buffering, the ammo counter says "
             "*banana*, and nothing is where you left it. Report the bugs. Do not trust the loading bar.",
    "actions": ["Run **Debug Sessions** (3 a day): five absurd objectives each.",
                "Keep **Stability** and **Sanity** above zero. Flawless sessions file extra Bug Reports.",
                "Nothing costs less and nothing pays more — this is pure chaos with cosmetics."],
    "meters": ("Stability", "Sanity"), "attempts_day": 3, "scene_pool": "404",
    "token": ("Bug Reports", "bug report"), "token_cap": 12, "crates": 0, "win_progress": 3, "flawless_bonus": 1, "fail_progress": 1,
    "glitch_lines": [
        "`ERROR 404` · hunt not found. Found it anyway.",
        "`WARN` · the ammo counter reads *banana*. It is wrong. Probably.",
        "`NullReferenceException` · you are standing in a place that doesn't exist yet.",
        "`SYSTEM.STAR = NULL` · somebody has been editing the world's settings.",
        "`LOADING…` 99% · 99% · 99% · 99%",
        "`DEBUG` · an animal just looked at the camera.",
        "`ADMIN` · \"Have you tried turning the wilderness off and on again?\"",
        "`PATCH NOTES` · fixed a bug that was keeping a different bug company.",
    ],
    "intro": ("The Admin's console in the Warden's hut has started printing things nobody typed. Ione has covered it with "
              "a blanket. The blanket is printing things too.\n\n\"The Star's hum is in the wiring,\" she says. "
              "\"Go through it and write down everything that's wrong. *Everything.* Even the things that are right."
              "\""),
    "story": [
        _s(3, "Tooltip Says No", "Every tooltip in the camp now ends with *'(this is fine)'*. It is not fine. One of "
                                  "them was a door."),
        _s(7, "The Admin's Last Log", "A log, recovered from the console: *'day 11 — star is writing to my config files. "
                                        "Set SYSTEM.STAR = NULL. It set it back. It did it politely.'*"),
        _s(11, "Patch Applied", "Your bug reports stack up and the console blinks once. The blanket stops printing. "
                                 "Somewhere, a very tired Admin pushes a fix. The Star — briefly — loses a round."),
    ],
    "rewards": [(3, {"title": "Bug Reporter"}), (7, {"keepsake": "glitch_cube"}),
                (11, {"title": "Glitch Hunter", "badge": "event_404"})],
    "shop": [{"label": "Title: Works On My Machine", "cost": 4, "title": "Works On My Machine"},
             {"label": "Keepsake: Glitch Cube", "cost": 8, "keepsake": "glitch_cube"},
             {"label": "Title: Have You Tried Rebooting", "cost": 12, "title": "Have You Tried Rebooting"}],
},

# ───────────────────────── 4 ─────────────────────────
"cartographer": {
    "key": "cartographer", "name": "The Lost Cartographer", "emoji": "🗺️", "icon": "world_map", "kind": "quest", "mech": "collect",
    "mode": "survey", "hours": 96, "chapter": 4,
    "blurb": "Odalys Venn mapped the fog before it swallowed her. Her survey tore into pieces and the wind dealt them "
             "across every region. Hunt each region to find its piece.",
    "actions": ["Hunt in a region **3 times** to recover its **Map Piece**.",
                "One piece per region — event-only, untradable, never sold.",
                "Finish the survey for a title, a badge and a keepsake."],
    "token": ("Map Pieces", "map piece"), "token_cap": 13, "crates": 1, "params": {"hunts_per_piece": 3},
    "intro": ("Ione unrolls a single sheet on the ledger table. It is a map of the crater's rim in a neat, steady hand, "
              "and then, halfway down, the ink starts to shake.\n\n\"Odalys Venn,\" Ione says. \"The best cartographer "
              "I ever knew. She went into the fog to draw it. This is all that came back.\""),
    "story": [
        _s(3, "The First Margin", "A note in the margin, in Odalys's handwriting: *'The fog has a shape. It is the same shape "
                                   "as the star. I think it is tracing itself.'*"),
        _s(6, "Where the Ink Runs Out", "Four regions in, the survey stops describing land and starts describing a "
                                         "*route* — one that leads in, in a spiral, and doesn't have an exit marked."),
        _s(10, "The Last Piece", "The final fragment is a self-portrait: Odalys, waving, at the centre of the map. "
                                  "The ink is still wet. She's alive down there. She's still drawing."),
    ],
    "rewards": [(4, {"title": "Pathfinder"}), (7, {"keepsake": "torn_map"}),
                (11, {"title": "Cartographer's Heir", "badge": "event_cartographer"})],
    "shop": [{"label": "Title: Margin Scribbler", "cost": 3, "title": "Margin Scribbler"},
             {"label": "1× Common Crate (once)", "cost": 6, "crate": "Common Crate"}],
},

# ───────────────────────── 5 ─────────────────────────
"storm": {
    "key": "storm", "name": "Thunderstorm Survival", "emoji": "⚡", "icon": "high_voltage_sign", "kind": "quest", "mech": "scenes",
    "hours": 48, "chapter": 5,
    "blurb": "A storm wall has formed around the crater and it is walking toward the camp. Lead an expedition "
             "through it — the right call at the right moment is the difference between a story and a funeral.",
    "actions": ["Run **Storm Crossings** (2 a day): five scenes of hard calls.",
                "Keep **Supplies** and **Morale** above zero to bring everyone through.",
                "Fixed attempts, fixed rewards — cosmetics and story only."],
    "meters": ("Supplies", "Morale"), "attempts_day": 2, "scene_pool": "storm",
    "token": ("Storm Tokens", "storm token"), "token_cap": 16, "crates": 1, "win_progress": 3, "flawless_bonus": 1, "fail_progress": 1,
    "intro": ("The storm doesn't move like weather. It moves like it's looking for something. By afternoon the wall of cloud "
              "has eaten the horizon and the first bolt hits the camp's flagpole and *sings*.\n\nIone hands out ponchos. "
              "\"Nobody dies on my watch,\" she says. \"It's bad for the paperwork.\""),
    "story": [
        _s(4, "Lightning Has a Voice", "Between the thunderclaps there are words. Short ones. Always the same three, "
                                        "repeated with the patience of something that has all the time in the world: *'Bring it back.'*"),
        _s(9, "The Eye Doesn't Blink", "The storm has an eye, and the eye is the crater. Whatever is down there is "
                                         "*pulling* the clouds in the way a drain pulls water."),
        _s(14, "Through", "You walk out of the last wall of rain into dry air and a perfectly clear sky. Behind you the "
                           "storm is already folding itself away. It wasn't trying to stop you. It was trying to *find* you."),
    ],
    "rewards": [(4, {"title": "Stormchaser"}), (9, {"keepsake": "storm_in_a_jar"}),
                (14, {"title": "Stormproof", "badge": "event_storm"})],
    "shop": [{"label": "Title: Struck Twice", "cost": 5, "title": "Struck Twice"},
             {"label": "Keepsake: Storm in a Jar", "cost": 10, "keepsake": "storm_in_a_jar"},
             {"label": "1× Common Crate (once)", "cost": 14, "crate": "Common Crate"}],
},

# ───────────────────────── 6 ─────────────────────────
"migration": {
    "key": "migration", "name": "Great Migration", "emoji": "🦌", "icon": "feather", "kind": "quest", "mech": "collect",
    "mode": "migrate", "hours": 72, "chapter": 6,
    "blurb": "The herds are leaving the crater's shadow. Certain species are turning up in regions they have no business "
             "in. Hunt there and log the sightings in your migration journal.",
    "actions": ["Each day three species migrate into unusual regions. Hunt there to **sight** them.",
                "Sightings fill your journal — they don't change what you catch or earn.",
                "Collection milestones give titles and a keepsake. No extra money or rare-drop odds."],
    "token": ("Sightings", "sighting"), "token_cap": 18, "day_cap": 6, "crates": 1,
    "params": {"species_per_day": 3, "chance": 0.30},
    "intro": ("Pip finds the first one: a red deer standing in a swamp, entirely unbothered and entirely wrong. Then a seal "
              "in a canyon. Then a flock of vultures roosting on a lighthouse.\n\n\"They're not lost,\" Pip says. \"They're "
              "*leaving*.\""),
    "story": [
        _s(5, "All Facing the Same Way", "Every migrating herd stops at dusk and turns, together, to look back at the "
                                          "crater. Then they carry on walking. None of them eat."),
        _s(10, "The Journal Fills", "Ione reads your journal twice. \"These are old routes,\" she says. \"Older than the "
                                     "camp. They only open when the herds are afraid.\""),
        _s(16, "Where They're Going", "Plotted on a map the sightings form a long, bending line — straight toward the "
                                       "sea. The animals aren't fleeing the Star. They're *evacuating* the Wilds."),
    ],
    "rewards": [(5, {"title": "Herd Watcher"}), (10, {"keepsake": "migration_feather"}),
                (16, {"title": "Herdkeeper", "badge": "event_migration"})],
    "shop": [{"label": "Title: Wanderer's Companion", "cost": 5, "title": "Wanderer's Companion"},
             {"label": "Keepsake: Migration Feather", "cost": 10, "keepsake": "migration_feather"},
             {"label": "1× Common Crate (once)", "cost": 14, "crate": "Common Crate"}],
},

# ───────────────────────── 7 ─────────────────────────
"nightwatch": {
    "key": "nightwatch", "name": "Night Watch", "emoji": "🦉", "kind": "quest", "mech": "clue",
    "mode": "night", "hours": 48, "chapter": 7,
    "blurb": "The nights have been wrong since the fall. Take the watch, listen to what's calling out of the dark, "
             "and name it before it gets closer.",
    "actions": ["Two **calls** a day: read the sound and pick the animal.",
                "Name it right for **Watch Marks**; more clues cost marks.",
                "Fixed attempts, collection rewards."],
    "token": ("Watch Marks", "watch mark"), "token_cap": 12, "puzzles_day": 2, "crates": 1,
    "intro": ("\"Somebody has to sit up,\" Ione says, and puts a lantern in your hand. \"Listen. Name what you hear. If it "
              "answers back, stop naming things and come get me.\""),
    "story": [
        _s(3, "Too Many Owls", "All of the owls are awake, all of the time, and all of them are saying the same thing at "
                                "the same pitch. Pip says they aren't hooting. They're *counting*."),
        _s(7, "The Stillness", "At the third hour every animal in the Wilds goes quiet for exactly nine seconds. When the "
                                 "sound comes back it is a little closer to the crater."),
        _s(11, "Dawn Watch", "When the sun comes up, nothing is wrong. That's what bothers you. Everything that called in "
                              "the night has simply... *gone home*, and left the door open behind it."),
    ],
    "rewards": [(3, {"title": "Night Watcher"}), (7, {"keepsake": "owl_pellet"}),
                (11, {"title": "Night Owl", "badge": "event_nightwatch"})],
    "shop": [{"label": "Title: Lantern Keeper", "cost": 4, "title": "Lantern Keeper"},
             {"label": "Keepsake: Night Watch Pin", "cost": 8, "keepsake": "owl_pellet"},
             {"label": "1× Common Crate (once)", "cost": 11, "crate": "Common Crate"}],
},

# ───────────────────────── 8 ─────────────────────────
"tracks": {
    "key": "tracks", "name": "Tracks of the Unknown", "emoji": "🐾", "kind": "quest", "mech": "clue",
    "mode": "tracks", "hours": 72, "chapter": 8,
    "blurb": "There are prints at the crater's edge that shouldn't exist. Each day there is a new set to read — "
             "work out what left them.",
    "actions": ["One **track mystery** a day, with clues you can reveal one at a time.",
                "The fewer clues you need, the more **Casebook Pages** you earn.",
                "Cosmetic rewards only. One puzzle per day."],
    "token": ("Casebook Pages", "casebook page"), "token_cap": 9, "puzzles_day": 1, "crates": 0,
    "intro": ("There are prints in the ash at the crater's rim. Not deep. Not fresh. Ione plaster-casts one and sets it on "
              "the table without a word. \"Same as yesterday's,\" she says. \"But yesterday's was in a different place. "
              "And a different size.\""),
    "story": [
        _s(3, "The Same Print", "Compare the casts side by side and they're the *same print* — just worn down differently, "
                                 "as though one creature were wearing a hundred different feet."),
        _s(6, "It Learns", "Each day's print is closer to something that actually exists. Whatever is making them is "
                            "studying the Wilds and getting better at it."),
        _s(9, "A Perfect Fox", "Today's print is a perfect red fox. Except there's no animal at the end of it — just a "
                                 "hollow where the fox ought to be. It's practising."),
    ],
    "rewards": [(3, {"title": "Track Reader"}), (6, {"keepsake": "plaster_cast"}),
                (9, {"title": "Print Reader", "badge": "event_tracks"})],
    "shop": [{"label": "Title: Nose to the Ground", "cost": 3, "title": "Nose to the Ground"},
             {"label": "Keepsake: Plaster Cast", "cost": 6, "keepsake": "plaster_cast"}],
},

# ───────────────────────── 9 ─────────────────────────
"wanted": {
    "key": "wanted", "name": "Wanted: Dead or Alive", "emoji": "📜", "icon": "scroll", "kind": "quest", "mech": "clue",
    "mode": "wanted", "hours": 72, "chapter": 9,
    "blurb": "Something walked out of the fog wearing an animal's shape, and it's loose in the Wilds. Each day it hides "
             "in a new region. Read the clues, stake out the right one, collect the bounty.",
    "actions": ["One **stake-out** a day: name the region the fugitive is hiding in.",
                "Fewer clues revealed = more **Bounty Points**. One claim per day.",
                "Points buy cosmetics from the Bounty Board."],
    "token": ("Bounty Points", "bounty point"), "token_cap": 9, "puzzles_day": 1, "crates": 0,
    "intro": ("The poster goes up on the camp gate before sunrise. The drawing is of a stag, but the face is wrong — too "
              "many teeth, and eyes like lanterns left on. *WANTED,* it says. And underneath, in Ione's hand: *'Do not "
              "approach. Do not feed. Do not make eye contact.'*"),
    "story": [
        _s(3, "Sighted", "A trapper swears he saw it eating the fog. \"Didn't chew,\" he says. \"Just... inhaled the whole thing.\""),
        _s(6, "Not Alone", "A second set of prints runs beside the Stag's. Smaller. Neat. Someone in boots. Ione files the "
                            "page in a drawer marked 'later' and then, quietly, locks the drawer."),
        _s(9, "Cornered", "You find the Stag — and it lets you. It looks at you for a long time, then bows its head. Not "
                           "afraid. *Apologising.* Then the fog closes round it again."),
    ],
    "rewards": [(3, {"title": "Deputy"}), (6, {"keepsake": "bounty_poster"}),
                (9, {"title": "Bounty Hunter", "badge": "event_wanted"})],
    "shop": [{"label": "Title: Dead or Alive", "cost": 3, "title": "Dead or Alive"},
             {"label": "Keepsake: Bounty Poster", "cost": 6, "keepsake": "bounty_poster"}],
},

# ───────────────────────── 10 ─────────────────────────
"impostor": {
    "key": "impostor", "name": "The Impostor Hunter", "emoji": "🎭", "icon": "search_alt", "kind": "quest", "mech": "deduce",
    "hours": 72, "chapter": 10,
    "blurb": "Somebody in camp has been feeding the Star: lamp oil missing, snares tripped, the night watch asleep. "
             "Five suspects. New testimony each day. One accusation.",
    "actions": ["New **testimony** arrives each day — each statement rules suspects out.",
                "Accuse once you're sure (two tries per event).",
                "Clue Points and a title for the detective. No gold at stake."],
    "token": ("Clue Points", "clue point"), "token_cap": 10, "crates": 0,
    "intro": ("The lamp oil is down by half. Three snares were sprung from the inside. Brann was found asleep on the north "
              "wall with a full cup of coffee in each hand.\n\nIone puts five names on the table and her pen on top of "
              "them. \"One of these people is helping it,\" she says. \"I'd like to know which before supper.\""),
    "story": [
        _s(3, "The First Statement", "Four of the five suspects tell the truth. The fifth tells it *beautifully* — rehearsed, "
                                      "warm, a little too quick. Ione makes a note of how good it was."),
        _s(6, "Second Thoughts", "A scrap of red cloth on the fence, a smear of oil on the stable latch, and a lantern "
                                  "that was lit at an hour nobody was awake. The picture gets smaller, and sharper."),
        _s(10, "The Saboteur", "The saboteur doesn't deny it. \"It was so *lonely* in there,\" they say. \"It only wanted "
                                "company.\" Ione writes it down without comment, then asks for the key to the oil store."),
    ],
    "rewards": [(3, {"title": "Sharp Eyes"}), (6, {"keepsake": "magnifier"}),
                (10, {"title": "Camp Detective", "badge": "event_impostor"})],
    "shop": [{"label": "Title: Case Closed", "cost": 4, "title": "Case Closed"},
             {"label": "Keepsake: Detective's Loupe", "cost": 8, "keepsake": "magnifier"}],
    "suspects": ["Brann", "Tilly", "Corvin", "Sable", "Wick"],
},

# ───────────────────────── 11 ─────────────────────────
"campfire": {
    "key": "campfire", "name": "Campfire Festival", "emoji": "🏕️", "icon": "idle_camp", "kind": "quest", "mech": "community",
    "hours": 72, "chapter": 11,
    "blurb": "The Star went dark and the camp fire went out with it. The whole community is relighting it — "
             "gather firewood through daily challenges and feed the fire together.",
    "actions": ["Daily **challenges** give Firewood: hunt, claim your daily, finish a quest, win a fight.",
                "Donate wood to the shared fire. The community unlocks a new stage as it grows.",
                "Chip in 20+ and you get a **participation chest** (fixed, one per player)."],
    "token": ("Firewood", "firewood"), "token_cap": 51, "crates": 1,
    "intro": ("On the first night after the fog, the great camp fire coughs, hisses and goes out. It has burned continuously for "
              "nine years. Ione stares at the ashes for a long time and then says, quietly: \"Right. Everybody bring wood.\""),
    "story": [
        _s(25, "A Spark", "One ember catches. Cheering — real, ragged cheering, from forty tired hunters who didn't know "
                           "they'd been waiting for it."),
        _s(50, "The Fire Remembers", "The flames burn strange colours for a moment, and each colour is a name. The names of "
                                      "everyone who ever sat here. It's a long list. It's getting longer."),
        _s(75, "The Great Fire", "The fire stands as tall as the gate, and in its light the fog on the horizon *recoils*. "
                                  "Pip, very seriously: \"It doesn't like us being happy.\" Ione, very seriously: \"Good.\""),
        _s(100, "Bonfire Night", "The whole Wilds can see it. Far out toward the crater, something answers — one slow, "
                                  "enormous heartbeat of light. Then another. The Star is learning what a fire is."),
    ],
    "rewards": [(15, {"title": "Fire Tender"}), (30, {"keepsake": "ember_bundle"}),
                (45, {"badge": "event_campfire"})],
    "shop": [{"label": "Title: Keeper of the Flame", "cost": 10, "title": "Keeper of the Flame"},
             {"label": "Keepsake: Festival Ember", "cost": 20, "keepsake": "ember_bundle"}],
    "challenges": [
        {"key": "hunt10",   "label": "Hunt 10 times today",             "need": 10, "wood": 3, "src": "hunt"},
        {"key": "daily",    "label": "Claim your daily reward",         "need": 1,  "wood": 3, "src": "daily"},
        {"key": "quest",    "label": "Complete a daily quest",          "need": 1,  "wood": 4, "src": "task"},
        {"key": "fight",    "label": "Win a fight (animal or mythic)",  "need": 1,  "wood": 4, "src": "fight"},
        {"key": "biomes3",  "label": "Hunt in 3 different regions",     "need": 3,  "wood": 3, "src": "biome"},
    ],
    "stages": [(0, "Cold Ashes"), (25, "Spark"), (50, "Ember"), (75, "Blaze"), (100, "Bonfire")],
    "goal_per_player": 28, "goal_min_players": 6, "contrib_min": 15, "wood_cap_day": 17,
},

# ───────────────────────── 12 ─────────────────────────
"tournament": {
    "key": "tournament", "name": "Hunter's Tournament", "emoji": "🏹", "icon": "bow", "kind": "quest", "mech": "tournament",
    "hours": 72, "chapter": 12,
    "blurb": "The Wardens are choosing who ventures into the crater. Everyone shoots with the same standard-issue bow — "
             "the only edge is reading the wind and range correctly.",
    "actions": ["Fire **3 rounds a day** with standardized equipment. Read the conditions, pick the technique.",
                "Perfect reads score 3, close calls 1. Your total ranks you on the board.",
                "Top three earn medals; every finisher gets a trophy. Titles and trophies only."],
    "token": ("Tournament Points", "tournament point"), "token_cap": 27, "rounds_day": 3, "crates": 0,
    "intro": ("\"Standard bows,\" Ione announces, holding up a plain wooden recurve, \"standard arrows, standard targets. "
              "I'd like to find out who's actually *good*, rather than who bought something expensive.\"\n\nA rope goes "
              "up around the range. Someone makes a book on it. Ione confiscates the book."),
    "story": [
        _s(6, "Qualifiers", "The range is a blur of fletching and muttering. A teenager from the east tents hits three "
                             "bullseyes in the rain and then, shaking, asks if it counts if she closed her eyes."),
        _s(15, "Semifinals", "The wind turns on the second day and a quarter of the field goes home. Ione watches the crater "
                              "instead of the targets. \"Interesting,\" she says. \"It's cheering for someone.\""),
        _s(27, "The Trial of Arrows", "The final round is shot at dusk. The last arrow lands dead centre, and the crater "
                                       "*hums* in approval. Whoever wins will be going in. Nobody wants to ask who wants to."),
    ],
    "rewards": [(9, {"title": "Quarterfinalist"}), (18, {"keepsake": "arrow_trophy"}),
                (27, {"title": "Tournament Veteran"})],
    "shop": [{"label": "Title: Dead Eye (Standard Issue)", "cost": 10, "title": "Dead Eye (Standard Issue)"}],
    "medals": {1: "Tournament Champion", 2: "Tournament Silver", 3: "Tournament Bronze"},
},

# ───────────────────────── 13 ─────────────────────────
"supply": {
    "key": "supply", "name": "Mysterious Supply Crate", "emoji": "🎲", "icon": "dice", "kind": "quest", "mech": "pick",
    "hours": 96, "chapter": 13,
    "blurb": "Sealed boxes keep arriving at the gate, labelled in a hand nobody recognises. Each day three are left out. "
             "You may take one. Choose by the hints on the tags.",
    "actions": ["Each day, pick **one of three** sealed boxes using the tag hints.",
                "Boxes hold Supply Tokens, cosmetics, and the occasional small item — with strict per-event limits.",
                "Open every box across the event for a unique badge."],
    "token": ("Supply Tokens", "supply token"), "token_cap": 40, "crates": 1, "item_cap": 3,
    "intro": ("There's a box at the camp gate. Then another, and another, stacked in threes, each one tied with the same "
              "waxed twine and labelled in the same careful handwriting.\n\n\"Don't open them yet,\" Ione says. "
              "\"I want to talk to whoever's sending them.\" Pip: \"What if it's a nice person?\" Ione: \"Then I'll be *extremely* "
              "suspicious.\""),
    "story": [
        _s(10, "Handwriting", "The tags are all signed with the same shaky initial: *Q.* Nobody in camp has a name that starts "
                               "with Q. Pip suggests it's the Quartermaster. Ione says they don't have one. Pip says: \"Not any more.\""),
        _s(22, "The Quartermaster", "Inside the latest box: a note. *'I'm on your side. I've been on your side for a long time. "
                                     "The Star is not what you think. Keep opening boxes. — Q.'*"),
        _s(36, "Fine Print", "At the very bottom of the last box, a sealed tag that reads, in full: *'Proceed to the crater. "
                              "Bring the whole camp. Bring a fire. — Q.'* Ione folds it twice and pockets it."),
    ],
    "rewards": [(10, {"title": "Box Opener"}), (22, {"keepsake": "sealed_tag"}),
                (36, {"title": "Quartermaster's Pick"})],
    "shop": [{"label": "Title: Sealed for Your Protection", "cost": 10, "title": "Sealed for Your Protection"}],
},

# ───────────────────────── 14 ─────────────────────────
"relay": {
    "key": "relay", "name": "Tribe Relay", "emoji": "🚩", "kind": "quest", "mech": "relay",
    "hours": 72, "chapter": 14,
    "blurb": "Carry the Star-fire to the crater. Your tribe must pass the beacon hand to hand: each leg is run by a "
             "DIFFERENT member, and each runner has to hunt their stretch before they can pass it on.",
    "actions": ["The tribe holds the **baton**. Whoever has it must make their leg's hunts, then **pass** it to a tribemate.",
                "No member may carry two legs in a row — everyone has a job.",
                "Each completed lap gives the tribe XP and each runner a Relay Token (capped). Works for any tribe of 2+."],
    "token": ("Relay Tokens", "relay token"), "token_cap": 20, "crates": 0,
    "leg_hunts": 8, "lap_xp": 400, "token_per_leg": 2,
    "intro": ("\"The fire has to get to the crater,\" Ione says, \"and it can't be carried by one person. It's too heavy and it's "
              "too lonely.\" She hands each tribe a baton wrapped in oiled cloth. \"Pass it on. Don't drop it. Don't *run off* "
              "with it, Corvin.\""),
    "story": [
        _s(4, "First Leg", "The first runner feels it before the hand-off: a warmth in the baton that isn't from the fire. "
                            "It is listening."),
        _s(10, "Hand to Hand", "By the third leg the baton has begun to glow whenever it changes hands. Runners say it *prefers* "
                                "the hand-off to the run."),
        _s(20, "The Light Arrives", "The last runner stops on the crater's edge. Below them, an enormous, hollow shape opens "
                                     "one eye. The fire flares in the baton. It is not afraid. Behind the runner, the whole tribe is waiting."),
    ],
    "rewards": [(4, {"title": "Baton Bearer"}), (10, {"keepsake": "baton"}),
                (20, {"badge": "event_relay"})],
    "shop": [{"label": "Title: Torch Passer", "cost": 6, "title": "Torch Passer"},
             {"label": "Keepsake: Relay Baton", "cost": 14, "keepsake": "baton"}],
},

# ───────────────────────── 15 ─────────────────────────
"conquest": {
    "key": "conquest", "name": "Biome Conquest", "emoji": "🏴", "kind": "quest", "mech": "conquest",
    "hours": 96, "chapter": 15,
    "blurb": "A ring of beacons will keep the fog out — one per region. Tribes race to light them: every region has a "
             "challenge, and every beacon you light is a Conquest Point.",
    "actions": ["Each region has a tribe **challenge** (catches in that region). Finish it to light the beacon: +1 point.",
                "Targets scale to your tribe's active hunters, so a small tribe can win.",
                "Top three tribes earn banner colours and member titles. Trophies, not income."],
    "token": ("Conquest Points", "conquest point"), "token_cap": 13, "crates": 0,
    "per_hunter_catches": 6, "min_hunters": 3,
    "intro": ("Ione lays thirteen unlit beacons on the map, one per region, and a thin line of chalk between them. \"If we light "
              "all of these,\" she says, \"the fog can't cross the ring. I don't need *all* of them. I need *most* of them, and "
              "I need them lit by people who'll defend them.\""),
    "story": [
        _s(2, "First Light", "The first beacon catches and a pillar of pale gold fire stands over the treeline. Far out in the "
                              "fog, something turns to look."),
        _s(6, "A Line of Fire", "Half the ring burns. From the air it is a necklace of lights around the crater, and the fog "
                                 "pools against it like water against glass."),
        _s(10, "The Ring Holds", "The ring closes. For the first time since the fall the Wilds are quiet — no hum, no fog, no "
                                  "footprints in reverse. Then, from under the crater, one low, pleased note. *Finally,* it seems to say."),
    ],
    "rewards": [(3, {"title": "Beacon Lighter"}), (7, {"keepsake": "banner_scrap"}),
                (13, {"badge": "event_conquest"})],
    "shop": [{"label": "Title: Wall of Fire", "cost": 5, "title": "Wall of Fire"}],
    "placements": {1: "Conqueror", 2: "Warlord", 3: "Vanguard"},
    "banners": {1: "conquest_gold", 2: "conquest_silver", 3: "conquest_bronze"},
},
}

# Events that hit every region at once get the full 13; this is the canonical region order.
STORY_ORDER = ["meteor", "fog", "admin_404", "cartographer", "storm", "migration", "nightwatch",
               "tracks", "wanted", "impostor", "campfire", "tournament", "supply", "relay", "conquest"]

# Conquest banner colours (merged into the tribe banner table at import)
CONQUEST_BANNERS = {"conquest_gold": ("Conquest Gold", 0xFFD166), "conquest_silver": ("Conquest Silver", 0xC0C8D4),
                    "conquest_bronze": ("Conquest Bronze", 0xCD7F32)}

# ════════════════════════════════════════════════════════════════
#  DAILY THEMES  ·  small, capped, never stacked on prices
# ════════════════════════════════════════════════════════════════
DAILY_THEMES = {
    0: {"key": "explorer",  "icon": "compass", "name": "Explorer's Monday",  "emoji": "🧭",
        "blurb": "Warden scouts have cleared the roads. **Travel takes half the time** today.",
        "limit": "Travel time only. No effect on money, XP or drops.",
        "lore": "Monday's scouts walk the roads before dawn. Ione calls it 'the only honest hour'."},
    1: {"key": "training",  "icon": "target", "name": "Training Tuesday",   "emoji": "🎯",
        "blurb": "The Wardens run drills. **+10% hunting XP** on your first **40 successful hunts** today.",
        "limit": "40 hunts per player per day; normal XP afterwards. Quest and prestige rewards unaffected.",
        "lore": "Tuesday is drills. Nobody likes drills. Everyone is better for them."},
    2: {"key": "workshop",  "icon": "hammer_and_wrench", "name": "Workshop Wednesday", "emoji": "⚒️",
        "blurb": "The forge is running hot. **Crafting takes 20% less time** for your first **5 crafts** today.",
        "limit": "Costs unchanged. 5 crafts per player per day.",
        "lore": "Wednesday, the camp's smith sings while she works. The anvil sings back."},
    3: {"key": "tribe",     "icon": "handshake", "name": "Tribe Thursday",     "emoji": "🤝",
        "blurb": "Contract rewards pay **+25% tribe XP** — up to **250 bonus XP per tribe** today.",
        "limit": "Tribe XP only; 250 bonus per tribe per day. No money multipliers.",
        "lore": "Thursday evenings the tribes eat together. They argue about contracts. It's a tradition."},
    4: {"key": "wanted",    "icon": "target", "name": "Most Wanted Friday", "emoji": "🎯",
        "blurb": "A dangerous animal has slipped into a hidden region. Read the clues, name the region, and the first "
                 "three hunters to find it are remembered. Everyone who tries gets one participation reward.",
        "limit": "One event reward per player, no bounty payouts.",
        "lore": "Friday nights somebody always escapes. It's become a camp tradition, to Ione's horror."},
    5: {"key": "rampage",   "icon": "ogre", "name": "Saturday Monster Rampage", "emoji": "👹",
        "blurb": "A husk of the **Hollow Colossus** crashes into one region. It summons minions — clear them, then bring "
                 "it down. Everyone can help all day.",
        "limit": "Capped engagements per player; the reward is a cosmetic plus one capped crate for real contributors.",
        "lore": "Every Saturday the Star's pulse wakes a husk of the Colossus. Somebody has to be there."},
    6: {"key": "recovery",  "icon": "idle_camp", "name": "Recovery Sunday",    "emoji": "🏕️",
        "blurb": "The camp rests. **HP regenerates twice as fast** today, and you can claim **one free full heal**.",
        "limit": "HP only. No extra idle-camp income or storage.",
        "lore": "Sunday the camp rests. Ione insists. She is, privately, the worst at it."},
}

# Tuesday / Wednesday / Thursday numbers
TRAINING_XP_BONUS = 0.10
TRAINING_HUNT_CAP = 40
WORKSHOP_TIME_CUT = 0.20
WORKSHOP_CRAFT_CAP = 5
TRIBE_THURSDAY_BONUS = 0.25
TRIBE_THURSDAY_CAP = 250
EXPLORER_TRAVEL_MULT = 0.5
RECOVERY_REGEN_MULT = 2.0

# Friday: Most Wanted
FRIDAY_FIRST_FINDERS = 3
FRIDAY_TITLE = "Most Wanted Tracker"
FRIDAY_PARTICIPATION_CRATE = "Common Crate"

# Saturday: Monster Rampage
RAMPAGE = {
    "boss": "Hollow Colossus (Husk)", "minion": "Star Husk",
    "engagements_day": 12, "cooldown_s": 45,
    "minion_hp": 40, "minion_dmg": (4, 9), "boss_hp_per_player": 90, "boss_hp_min": 900,
    "boss_dmg": (7, 14), "summon_at": (0.75, 0.50, 0.25), "summon_per_wave": 4,
    "min_engagements_reward": 3, "reward_crate": "Uncommon Crate",
    "first_kill_title": "Colossus Breaker", "badge": "event_rampage",
    "keepsake": "husk_horn", "keepsake_at": 25,
}

# ════════════════════════════════════════════════════════════════
#  PUZZLE TABLES
# ════════════════════════════════════════════════════════════════

# Three progressive clues per region (wanted / region-guess).
BIOME_CLUES = {
    "village": ["Cold rain, evergreen smoke, and the sea somewhere beyond the trees.",
                "Salmon runs, cedar and moss; the Pacific Northwest.", "Home turf — the camp's own back garden."],
    "forest": ["Hedgerows, stone walls and very old oaks.", "Moors, mist and a thousand years of footpaths; the British Isles.",
               "Wolves here are a memory; this one doesn't know that."],
    "woods": ["Pine as far as you can see, and snow in the shade.", "Elk, bear and wolverine; boreal Scandinavia.",
              "Midnight sun in summer, none in winter."],
    "small_desert": ["Sand, heat and sudden cold at dusk.", "Scorpions, vipers and jackals along an old river.",
                     "Pyramids on one horizon, nothing on the other."],
    "sunken_coast": ["Grey water, gulls and a lighthouse.", "Cod, seals and whales off Cape Ann.",
                     "The sea here has been taking things for centuries."],
    "tundra": ["Treeless ridges and thin air.", "The high alpine summits of the Carpathians.",
               "Under the stars here the vampires are not a joke."],
    "jungle": ["Steam, vines and rain you can drink.", "Tigers, macaques and pangolins; Southeast Asia and Japan.",
               "Everything here is green, and most of it is watching."],
    "swamp": ["Still water, black mud and a million insects.", "Billabongs and backwaters of southeastern Australia.",
              "Crocodiles that don't bother to hide."],
    "volcanic_highlands": ["Hot ground, ash and grudging grass.", "The volcanic highlands of Anatolia.",
                           "Eagles ride the thermals off the vents."],
    "cursed_ruins": ["Marble, shadows and old stories.", "Ruined temples and mountains of Ancient Greece.",
                     "Don't look at statues for too long."],
    "rainbow": ["Reefs, parrots and colours that don't seem real.", "Caribbean rainforest and coral.",
                "Even the weather here looks painted."],
    "abyssal_depths": ["Black water, pressure and glowing things.", "The lightless deep of the Mediterranean.",
                       "Nothing here has ever seen the sun."],
    "celestial_peaks": ["Thin air, endless white, and the world falling away.", "The highest ridges of the Himalayas.",
                        "The roof of the world — and the Star's crater is in sight."],
}

FUGITIVES = [
    ("the Hollow Stag", "antlers like dead trees, eyes like lanterns"),
    ("the Ash Wolf", "a grey wolf with fog where its shadow should be"),
    ("the Borrowed Fox", "a fox wearing a fox"),
    ("the Mirror Bear", "a bear that moves one beat behind its reflection"),
    ("the Lantern Heron", "a heron whose reflection is glowing the wrong colour"),
    ("the Quiet Boar", "a boar that doesn't make a sound, ever"),
]

# animal-name keyword -> sound (first match wins); fallbacks by rarity
SOUND_BY_KEYWORD = [
    ("wolf", "a long, rising howl"), ("jackal", "a yipping, laughing chorus"), ("fox", "a sharp, barking scream"),
    ("owl", "a soft, double hoot"), ("bear", "a low, rumbling growl"), ("lynx", "a ragged, cat-like yowl"),
    ("leopard", "a rasping, sawing cough"), ("tiger", "a chest-deep roar"), ("lion", "a thunderous roar"),
    ("cat", "a thin, rising yowl"), ("deer", "a hoarse, bellowing groan"), ("elk", "a bugling bellow"),
    ("reindeer", "a clicking of hooves and a grunt"), ("boar", "a grunting, snuffling snort"),
    ("seal", "a bark that echoes off the water"), ("whale", "a long, mournful song"),
    ("porpoise", "a quick, clicking chatter"), ("eagle", "a thin, piercing scream"), ("vulture", "a hissing rasp"),
    ("kite", "a mewing whistle"), ("crow", "a harsh caw"), ("snake", "a long, dry hiss"), ("viper", "a sudden hiss"),
    ("cobra", "a deep, rattling hiss"), ("python", "a heavy, slithering hush"), ("boa", "a slow, wet hiss"),
    ("crocodile", "a deep, guttural bellow"), ("squirrel", "a scolding chatter"), ("marmot", "a shrill whistle"),
    ("hare", "a startled thump of hind legs"), ("rabbit", "a sudden thump"), ("otter", "a high, chirping whistle"),
    ("macaque", "a screeching chatter"), ("orangutan", "a long, bubbling call"), ("pheasant", "a rusty crow"),
    ("grouse", "a bubbling, popping call"), ("ptarmigan", "a croaking cackle"), ("partridge", "a grating chuckle"),
    ("eel", "a wet, popping click"), ("shark", "an utterly terrible silence"), ("squid", "a faint rhythmic clicking"),
    ("manatee", "a gentle squeak"), ("tapir", "a shrill whistle"), ("yak", "a deep, grunting groan"),
    ("goat", "a wavering bleat"), ("ibex", "a sharp whistling snort"), ("kangaroo", "a heavy, double thump"),
    ("emu", "a booming drum"), ("cassowary", "a deep, rolling boom"), ("dingo", "a mournful, wavering howl"),
]
SOUND_FALLBACK = {"common": "a small, nervous rustle", "uncommon": "a steady, careful padding",
                  "rare": "a deep, unhurried breathing", "epic": "a low, heavy growl", "legendary": "a sound that has no name"}

BEHAVIOR_PHRASE = {
    "passive": "keeps to itself and bolts at a sound", "skittish": "is jumpy and rarely holds its ground",
    "defensive": "will stand and defend its patch", "aggressive": "picks fights it doesn't have to",
    "predator": "hunts anything that moves",
}
RARITY_PHRASE = {"common": "a common sight", "uncommon": "an uncommon one", "rare": "properly rare",
                 "epic": "an epic find", "legendary": "legendary"}

# Tournament: wind x range -> best, close
TOURNEY_WIND = {"calm": "Dead calm", "cross": "A stiff crosswind", "head": "A hard headwind"}
TOURNEY_RANGE = {"short": "short range", "mid": "mid range", "long": "long range"}
TOURNEY_TECHNIQUES = {"snap": "Quick snap", "steady": "Steady draw", "lead": "Lead the wind", "brace": "Brace and breathe"}
TOURNEY_TABLE = {   # (wind, range): (best, close)
    ("calm", "short"): ("snap", "steady"),   ("calm", "mid"): ("steady", "snap"),   ("calm", "long"): ("steady", "brace"),
    ("cross", "short"): ("lead", "snap"),    ("cross", "mid"): ("lead", "steady"),  ("cross", "long"): ("lead", "brace"),
    ("head", "short"): ("brace", "snap"),    ("head", "mid"): ("brace", "steady"),  ("head", "long"): ("brace", "lead"),
}
TOURNEY_TIPS = [
    "Wardens' tip: *Crosswind? Lead it.*", "Wardens' tip: *Headwind? Brace and breathe.*",
    "Wardens' tip: *Dead calm and close — don't overthink it.*", "Wardens' tip: *At long range, a steady hand beats a quick one.*",
]

# Impostor deduction attributes
IMPOSTOR_ATTRS = {
    "tool":  ["a bow", "a spear", "a snare"],
    "place": ["the stables", "the north wall", "the forge"],
    "item":  ["a red scarf", "a brass key", "a lamp-oil can"],
}
IMPOSTOR_PHRASE = {
    "tool":  "was carrying {v}",
    "place": "was last seen near {v}",
    "item":  "had {v} on them",
}

# Mysterious supply boxes: (hint, kind, amount range)
SUPPLY_BOXES = [
    {"hint": "Heavy. Something rattles inside.",        "kind": "tokens", "lo": 10, "hi": 16},
    {"hint": "Light. Faintly humming.",                 "kind": "tokens", "lo": 4,  "hi": 8},
    {"hint": "Smells of oiled leather and iron.",       "kind": "item",   "pool": ["Bandage", "Camp Rations"]},
    {"hint": "Wrapped in a ribbon that wasn't tied by hand.", "kind": "cosmetic"},
    {"hint": "Sealed with a very official wax stamp.",  "kind": "crate"},
    {"hint": "Warm to the touch. Do not shake.",        "kind": "tokens", "lo": 6,  "hi": 12},
]
SUPPLY_BOX_FLAVOR = [
    "You cut the twine. Inside, wrapped in oilcloth:", "The tag says 'FRAGILE'. The box says 'NOT FRAGILE'. You open it.",
    "A faint smell of cedar and ink. Inside:", "It opens easily. Suspiciously easily. Inside:",
]
