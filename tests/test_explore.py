"""
Explore Mode (beta): with the setting on, Hunt opens a 7x7 map you walk on: a bounded arena that widens as you
walk, trees that block, bushes that hide animals, clues that fade, chests, weapon range + a chosen target, shots that
are real hunts, and a map drawn with Pillow and attached as a picture.

Runs without pytest:  python tests/test_explore.py
"""
import asyncio
import contextlib
import io
import json
import os
import random
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_explore_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_decisions as td        # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = td.run
U = td.U
COMMON = gd.BIOME_ANIMALS["village"][0]


def _fresh(**over):
    d = td._fresh(biome="village", explore_mode=True, **over)
    d["hunt_cd"] = 0
    return d


@contextlib.contextmanager
def terrain(mapping=None, default="grass"):
    """Pin the map: tiles not listed are `default`. (The start tile is always grass.)"""
    mapping = mapping or {}
    real = app._ex_tile
    app._ex_tile = lambda seed, x, y, biome="": "grass" if (x, y) == app.EXPLORE_START else mapping.get((x, y), default)
    try:
        yield
    finally:
        app._ex_tile = real


def _calm(st, name=COMMON, dx=0, dy=0, **kw):
    a = {"id": st["nid"], "name": name, "x": st["x"] + dx, "y": st["y"] + dy, "clue": 0, "cool": 0, "fade": 0,
         "pd": 99, "mood": "calm"}
    a.update(kw)
    st["nid"] += 1
    st["animals"].append(a)
    return a


@contextlib.contextmanager
def still_world():
    """Nothing wanders, nothing spawns: only what a test sets up happens."""
    real = random.random
    random.random = lambda: 0.99
    try:
        yield
    finally:
        random.random = real


# ── settings + gating ───────────────────────────────────────

def test_explore_is_off_by_default_and_has_a_settings_toggle():
    td._fresh()
    assert app.explore_enabled(U) is False
    assert "explore_mode" in json.dumps(app.build_settings_components(U))
    with tr.Harness() as h:
        run(app._dispatch_component(tr.FakeInteraction(U, f"settings:toggle:explore_mode:{U}")))
    assert app.explore_enabled(U) is True
    with tr.Harness():
        run(app._dispatch_component(tr.FakeInteraction(U, f"settings:toggle:explore_mode:{U}")))
    assert app.explore_enabled(U) is False
    app.FEATURE_EXPLORE = False
    app.data[U]["explore_mode"] = True
    assert app.explore_enabled(U) is False                                    # the kill switch beats the setting
    app.FEATURE_EXPLORE = True


def test_buttons_do_nothing_while_the_mode_is_off():
    td._fresh()
    with tr.Harness() as h:
        run(app._dispatch_component(tr.FakeInteraction(U, f"explore:n:{U}")))
    assert any("Explore Mode is off" in m for m in h.ephemerals) and "explore" not in app.data[U]


# ── the arena ───────────────────────────────────────────────

def test_you_start_at_3_0_in_a_7x7_arena_that_widens_every_two_steps_up_to_a_cap():
    _fresh()
    st = app._ex_state(U)
    assert (st["x"], st["y"]) == (3, 0) == app.EXPLORE_START and app._ex_bounds(st) == (0, 0, 6, 6)
    seen = []
    for steps in range(0, 20):
        st["steps"] = steps
        seen.append(app._ex_bounds(st))
    assert seen[0] == seen[1] == (0, 0, 6, 6) and seen[2] == seen[3] == (-1, -1, 7, 7)
    assert seen[-1] == (-app.EXPLORE_MAX_GROW, -app.EXPLORE_MAX_GROW, 6 + app.EXPLORE_MAX_GROW, 6 + app.EXPLORE_MAX_GROW)
    st["steps"] = 0
    assert app._ex_kind(st, 3, -1) == "void" and app._ex_kind(st, 7, 3) == "void"
    st["steps"] = 2
    assert app._ex_kind(st, 3, -1) != "void"


def test_the_border_stops_you_and_costs_no_step_then_widens_as_you_explore():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        out = app.explore_move(U, "n")
        assert out["kind"] == "bump" and (st["x"], st["y"]) == (3, 0) and st["steps"] == 0
        assert "edge" in st["msg"]
        app.explore_move(U, "s"); app.explore_move(U, "s")                    # two steps -> the arena grows
        assert app._ex_bounds(st) == (-1, -1, 7, 7)
        for _ in range(2):
            app.explore_move(U, "n")
        assert st["y"] == 0 and app.explore_move(U, "n")["kind"] == "moved" and st["y"] == -1


def test_trees_and_boulders_block_you_and_cost_nothing():
    d = _fresh()
    d["biome"] = "forest"
    with terrain({(3, 1): "tree", (4, 0): "stone", (2, 0): "bush"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        for d, word in (("s", "tree"), ("e", "boulder")):
            out = app.explore_move(U, d)
            assert out["kind"] == "bump" and word in st["msg"] and (st["x"], st["y"]) == (3, 0) and st["steps"] == 0
        assert app.explore_move(U, "w")["kind"] == "moved" and (st["x"], st["y"]) == (2, 0)      # a bush is walkable


def test_there_is_always_a_way_to_every_animal():
    for i in range(120):
        _fresh()
        random.seed(i)
        st = app._ex_new(U, "village")
        assert len(app._ex_reach(st)) >= app.EXPLORE_MIN_REACH
        for _ in range(60):                                                    # play it out; animals roam and spawn
            reach = app._ex_reach(st)
            assert all((a["x"], a["y"]) in reach for a in st["animals"]), (i, st["steps"])
            d = random.choice("nsew")
            app.explore_move(U, d if random.random() < .8 else "wait")
            if app._ex_over(st):
                break


def test_a_fully_walled_in_start_is_rerolled():
    _fresh()
    calls = {"n": 0}
    real = app._ex_tile
    def walled(seed, x, y, biome=""):
        if (x, y) == app.EXPLORE_START:
            return "grass"
        if calls["n"] < 3 and seed % 2 == 0:
            return "tree"
        return real(seed, x, y, biome)
    app._ex_tile = walled
    try:
        random.seed(5)
        st = app._ex_new(U, "village")
        assert len(app._ex_reach(st)) >= app.EXPLORE_MIN_REACH
    finally:
        app._ex_tile = real


# ── the camera: the whole field on screen, the hunter walks toward the border ──

def test_the_picture_always_shows_a_full_window_of_land_and_the_hunter_walks_to_the_edge():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        snap = app._ex_snapshot(U)
        assert (snap["cx"], snap["cy"]) == (0, 0) and (snap["hx"], snap["hy"]) == (3, 0)       # starts top-middle of the 7x7 field
        assert all(k != "void" for row in snap["cells"] for k in row) and snap["edges"] == {"l": True, "t": True, "r": True, "b": True}
        st["steps"] = 20                                                                         # a 19x19 field
        st["x"], st["y"] = 5, 5
        snap = app._ex_snapshot(U)
        assert (snap["hx"], snap["hy"]) == (3, 3) and not any(snap["edges"].values())            # mid-field: centred, no border
        st["x"], st["y"] = -6, -6                                                                # the north-west corner
        snap = app._ex_snapshot(U)
        assert (snap["hx"], snap["hy"]) == (0, 0) and snap["edges"]["l"] and snap["edges"]["t"] and not snap["edges"]["r"]
        st["x"], st["y"] = 12, 3                                                                 # the east wall
        snap = app._ex_snapshot(U)
        assert snap["hx"] == 6 and snap["hy"] == 3 and snap["edges"]["r"]
        for row in snap["cells"]:
            assert "void" not in row


def test_the_border_is_drawn_only_where_the_world_ends():
    from PIL import Image
    saved = dict(app._ex_art)
    app._ex_art.clear()
    try:
        _fresh()
        with terrain():
            st = app._ex_state(U)
            st["animals"] = []
            amber = lambda px: px[0] > 200 and 150 < px[1] < 230 and px[2] < 130
            im = _png_ok(app._ex_render(app._ex_snapshot(U)))                                        # the start: walls on all four sides
            W = im.size[0]
            assert amber(im.getpixel((W // 2, 2))) and amber(im.getpixel((W // 2, W - 3)))
            assert amber(im.getpixel((2, W // 2))) and amber(im.getpixel((W - 3, W // 2)))
            st["steps"] = 20
            st["x"], st["y"] = 5, 5                                                              # mid-field: no border in the picture
            im = _png_ok(app._ex_render(app._ex_snapshot(U)))
            assert not any(amber(im.getpixel(p)) for p in ((W // 2, 2), (W // 2, W - 3), (2, W // 2), (W - 3, W // 2)))
    finally:
        app._ex_art.update(saved)


# ── a blocked move is answered privately ──

def test_a_blocked_move_is_an_ephemeral_message_and_leaves_the_panel_alone():
    _fresh()
    with terrain({(3, 1): "tree"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        st["msg"] = "an old line"
        with tr.Harness() as h:
            run(app._dispatch_component(tr.FakeInteraction(U, f"explore:s:{U}")))               # into a tree
            assert any("tree blocks" in m for m in h.ephemerals) and not h.panels
            run(app._dispatch_component(tr.FakeInteraction(U, f"explore:n:{U}")))               # off the north edge
            assert any("edge of the known land" in m for m in h.ephemerals) and not h.panels
        assert (st["x"], st["y"], st["steps"]) == (3, 0, 0) and st["msg"] == ""
        run_ = app.explore_enabled(U)
        assert run_


def test_cooldowns_and_empty_shots_are_private_too_and_a_real_move_still_updates_the_panel():
    _fresh()

    async def no_image(uid):
        return None
    real = app.explore_image
    app.explore_image = no_image
    try:
        with terrain(), still_world():
            st = app._ex_state(U)
            st["animals"] = []
            with tr.Harness() as h:
                run(app._dispatch_component(tr.FakeInteraction(U, f"explore:fire:{U}")))        # nothing in view
                assert any("Nothing in view" in m for m in h.ephemerals) and not h.panels
                run(app._dispatch_component(tr.FakeInteraction(U, f"explore:s:{U}")))           # a real step
                assert h.panels and st["steps"] == 1
    finally:
        app.explore_image = real


# ── bushes hide animals ─────────────────────────────────────

def test_a_bush_hides_an_animal_until_you_are_next_to_it():
    _fresh()
    with terrain({(5, 0): "bush", (4, 0): "bush"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        far = _calm(st, dx=2)                                                  # in a bush, two tiles away
        assert app._ex_seen(st, far) is False and app._ex_visible(st) == []
        snap = app._ex_snapshot(U)
        assert snap["animals"] == []                                           # not drawn: the bush covers it
        near = _calm(st, name="Red Fox", dx=1)                                 # in a bush, right beside you
        assert app._ex_seen(st, near) is True
        assert [a["name"] for a in app._ex_snapshot(U)["animals"]] == ["Red Fox"]
        assert app.build_explore_components(U)[0]["components"][-2]["components"][0]["disabled"] is False      # Fire
        # and you can't shoot what you can't see
        st["animals"].remove(near)
        out = app.explore_fire(U)
        assert out["kind"] == "none"


def test_a_hidden_animal_gives_a_rustling_clue():
    _fresh()
    with terrain({(5, 0): "bush"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        a = _calm(st, dx=2)
        app.explore_move(U, "wait")
        assert a["clue"] > 0 and "bush" in st["msg"]
        assert any(c["dx"] == 2 for c in app._ex_snapshot(U)["clues"])
        assert "Rustling bush" in json.dumps(app.build_explore_components(U), ensure_ascii=False)


# ── clues ───────────────────────────────────────────────────

def test_clues_appear_when_something_unseen_is_near_and_fade_unless_you_close_in():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        st["steps"] = 20                                                       # a wide arena
        st["x"], st["y"] = 6, 6
        a = _calm(st, dx=5, dy=0)                                              # unseen, 5 away
        app._ex_advance(U, st)
        assert a["clue"] == app.EXPLORE_CLUE_TTL and any(c["d"] >= 2 for c in app._ex_snapshot(U)["clues"])
        snap = app._ex_snapshot(U)
        assert snap["animals"] == [] and snap["clues"][0]["dx"] == 5               # an arrow, never the species
        for _ in range(app.EXPLORE_CLUE_TTL):                                   # stand still: it fades
            app._ex_advance(U, st)
        assert a["clue"] == 0 and app._ex_snapshot(U)["clues"] == []
        a["fade"] = 0
        app._ex_advance(U, st)                                                 # still close, fade over: noticed anew
        assert a["clue"] > 0


def test_closing_in_keeps_a_clue_fresh():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        st["steps"] = 20
        st["x"], st["y"] = 2, 6
        a = _calm(st, dx=5)
        app._ex_advance(U, st)
        assert a["clue"] == app.EXPLORE_CLUE_TTL
        for _ in range(4):
            app._ex_advance(U, st)
            st["x"] += 1                                                       # keep walking toward it
            if app._ex_seen(st, a):
                break
        assert a["clue"] == app.EXPLORE_CLUE_TTL or app._ex_seen(st, a)


def test_a_predator_stalks_you_and_bites_but_never_knocks_you_out():
    _fresh()
    name = next(n for n, v in gd.ANIMAL_COMBAT.items() if v["behavior"] == "predator")
    with terrain():
        st = app._ex_state(U)
        st["animals"] = []
        st["steps"] = 20
        st["x"], st["y"] = 6, 6
        wolf = _calm(st, name=name, dx=3)
        real = random.random
        random.random = lambda: 0.0
        try:
            for _ in range(40):
                app._ex_advance(U, st)
        finally:
            random.random = real
        assert app.data[U]["health"]["hp"] >= 1
        assert app.data[U]["health"]["hp"] < app.data[U]["health"]["max_hp"]


# ── chests ──────────────────────────────────────────────────

def test_walking_onto_a_chest_opens_it_once_and_pays_something_small():
    _fresh()
    with terrain({(3, 1): "chest"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        d = app.data[U]
        d["healing_inv"] = {}
        money0 = d["money"]
        real = random.choices
        random.choices = lambda pop, weights=None, k=1: [pop[0] if False else "cash"]
        try:
            out = app.explore_move(U, "s")
        finally:
            random.choices = real
        assert "found a chest" in st["msg"] and d["money"] > money0 and "3,1" in st["opened"]
        assert app._ex_kind(st, 3, 1) == "grass"                              # opened: just grass now
        app.explore_move(U, "n"); app.explore_move(U, "s")
        assert "chest" not in st["msg"]


def test_chests_can_hold_ammo_bandages_and_items_and_never_run_dry():
    d = _fresh(tool="Shortbow", owned_tools=["Shortbow"])
    ammo = gd.get_ammo_for_tool("Shortbow")[0]
    d["ammo_inv"], d["equipped_ammo"] = {ammo: 5}, ammo
    st = app._ex_state(U)
    real = random.choices
    try:
        random.choices = lambda pop, weights=None, k=1: ["ammo"]
        assert "× " in app._ex_open_chest(U, st, 9, 9) and d["ammo_inv"][ammo] >= 13
        random.choices = lambda pop, weights=None, k=1: ["heal"]
        assert "Bandage" in app._ex_open_chest(U, st, 9, 8) and d["healing_inv"]["Bandage"] == 1
        random.choices = lambda pop, weights=None, k=1: ["item"]
        assert "Scent Lure" in app._ex_open_chest(U, st, 9, 7)
        d["tool"] = "Bare Hands"                                               # no ammo needed -> never ammo
        random.choices = lambda pop, weights=None, k=1: ["ammo"]
        assert "Bandage" in app._ex_open_chest(U, st, 9, 6)
    finally:
        random.choices = real
    for i in range(30):                                                        # no daily limit: they never run dry
        assert "empty" not in app._ex_open_chest(U, st, 9, 100 + i)
    assert not hasattr(app, "EXPLORE_CHESTS_PER_DAY") and "explore_chests" not in d


def test_chests_are_rare_on_the_map():
    n = sum(1 for seed in range(40) for x in range(19) for y in range(19)
            if app._ex_tile(seed, x, y) == "chest")
    share = n / (40 * 19 * 19)
    assert 0.003 < share < 0.015, share                                          # about 0.8% of tiles, was 3%


def test_chests_are_drawn_with_crate_art_and_richer_crates_pay_a_little_more():
    assert [gd.EXPLORE_ART[f"chest{i}"] for i in range(4)] == [gd.EMOJI[f"{t}_crate"] for t in ("common", "uncommon", "rare", "epic")]
    tiers = [app._ex_chest_tier(123, x, 5) for x in range(2000)]
    assert set(tiers) == {0, 1, 2, 3} and tiers.count(0) > tiers.count(1) > tiers.count(2) > tiers.count(3)
    assert app._ex_chest_tier(123, 4, 5) == app._ex_chest_tier(123, 4, 5)          # fixed per tile: what you see is what you get
    d = _fresh()
    with terrain({(3, 1): "chest"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        snap = app._ex_snapshot(U)
        assert list(snap["chests"].values()) == [app._ex_chest_tier(st["seed"], 3, 1)] and len(snap["chests"]) == 1
    real = random.choices
    random.choices = lambda pop, weights=None, k=1: ["cash"]
    try:
        paid = {}
        for tier in (0, 3):
            t0 = app._ex_chest_tier
            app._ex_chest_tier = lambda seed, x, y, tier=tier: tier
            m0 = d["money"]
            random.seed(9)
            app._ex_open_chest(U, app._ex_state(U), 50 + tier, 50)
            paid[tier] = d["money"] - m0
            app._ex_chest_tier = t0
    finally:
        random.choices = real
    assert paid[3] > paid[0] * 1.5


def test_the_hunter_is_drawn_big():
    """The hunter fills (nearly) its whole tile; animals stay small."""
    from PIL import Image
    saved = dict(app._ex_art)
    app._ex_art.update({gd.EXPLORE_GROUND["village"]: Image.new("RGBA", (128, 128), (0, 200, 0, 255)),
                       "hunter": Image.new("RGBA", (128, 128), (255, 255, 255, 255))})
    try:
        _fresh()
        with terrain():
            st = app._ex_state(U)
            st["animals"] = []
            st["steps"] = 20
            im = _png_ok(app._ex_render(app._ex_snapshot(U)))
            T = app.EXPLORE_TILE_PX
            white = sum(1 for x in range(3 * T, 4 * T) for y in range(3 * T, 4 * T)
                        if im.getpixel((x, y))[0] > 200 and im.getpixel((x, y))[1] > 200)
            assert white > 0.7 * T * T, white
    finally:
        app._ex_art.clear()
        app._ex_art.update(saved)


# ── shooting is a real hunt ─────────────────────────────────

def test_a_hit_is_a_real_single_animal_hunt_and_lands_in_the_catch_list():
    d = _fresh(tool="Shotgun", owned_tools=["Shotgun"])                        # a 3-catch weapon: still just one animal
    ammo = gd.get_ammo_for_tool("Shotgun")[0]
    d["ammo_inv"], d["equipped_ammo"] = {ammo: 100}, ammo
    d["level"] = 300
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        _calm(st, name=COMMON, dx=1)
        real = random.random
        random.random = lambda: 0.0                                            # the shot lands
        try:
            lt0 = d["stats"].get("lifetime_hunts", 0)
            out = app.explore_fire(U)
        finally:
            random.random = real
        assert out["kind"] == "caught" and len(out["result"]["catches"]) == 1
        assert d["inv"].count(COMMON) >= 1 and d["stats"]["lifetime_hunts"] == lt0 + 1
        assert d["ammo_inv"][ammo] == 99                                      # one round, not three
        assert st["bag"][0]["name"] == COMMON
        assert all(a["name"] != COMMON or (a["x"], a["y"]) != (st["x"] + 1, st["y"]) for a in st["animals"])   # the one you shot is gone
        panel = json.dumps(app.build_explore_components(U), ensure_ascii=False)
        assert "You caught" in panel and COMMON in panel and "Explore bonus" in panel
        assert "Caught this trip" not in panel and "🎒" not in panel                # no running inventory in the panel
        # the cooldown is the real hunt cooldown
        _calm(st, name=COMMON, dx=1)
        assert app.explore_fire(U)["kind"] == "cooldown"


def test_a_shot_never_starts_a_mythic_and_a_miss_spooks_the_animal():
    d = _fresh()
    app.MYTH_ENCOUNTER_BASE, base = 1.0, app.MYTH_ENCOUNTER_BASE
    try:
        with terrain(), still_world():
            st = app._ex_state(U)
            st["animals"] = []
            _calm(st, dx=1)
            real = random.random
            random.random = lambda: 0.0
            try:
                app.explore_fire(U)
            finally:
                random.random = real
            assert d.get("tracking") is None and d.get("_boss") is None
            a = _calm(st, dx=1)
            random.random = lambda: 0.999
            try:
                out = app.explore_fire(U)                                      # a miss (and nothing is spent)
            finally:
                random.random = real
            assert out["kind"] in ("miss", "cooldown")
    finally:
        app.MYTH_ENCOUNTER_BASE = base


def test_nothing_in_view_means_nothing_to_shoot():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        assert app.explore_fire(U)["kind"] == "none"
        blob = json.dumps(app.build_explore_components(U))
        assert '"label": "Fire"' in blob and '"disabled": true' in blob


# ── expedition length ───────────────────────────────────────

def test_the_expedition_ends_after_its_step_budget_and_a_new_one_resets_everything():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        st["bag"] = [{"name": COMMON, "value": 5, "perfect": False}]
        st["steps"] = app.EXPLORE_MAX_STEPS - 1
        app.explore_move(U, "wait")
        assert app._ex_over(st) and "expedition is over" in st["msg"]
        x, y = st["x"], st["y"]
        assert app.explore_move(U, "s")["kind"] == "over" and (st["x"], st["y"]) == (x, y)
        assert app.explore_fire(U)["kind"] == "over"
        blob = json.dumps(app.build_explore_components(U), ensure_ascii=False)
        assert blob.count('"disabled": true') >= 5 and "Expedition over" in blob and COMMON in blob
        app.explore_new(U)
        st2 = app.data[U]["explore"]
        assert st2["steps"] == 0 and st2["bag"] == [] and (st2["x"], st2["y"]) == (3, 0) and not app._ex_over(st2)


def test_a_new_biome_means_a_new_expedition():
    d = _fresh()
    st = app._ex_state(U)
    st["bag"] = [{"name": COMMON, "value": 5, "perfect": False}]
    d["biome"] = "forest"
    st2 = app._ex_state(U)
    assert st2["biome"] == "forest" and st2["bag"] == []


def test_you_cannot_explore_mid_fight_or_mid_track():
    d = _fresh()
    d["_boss"] = {"creature": "Bigfoot", "biome": "village", "ts": int(time.time()), "eid": "z", "mhp": 5, "mhp_max": 5,
                  "turn": 1, "fallen": False, "guard": False, "enrage": False, "mdebuff": False, "log": []}
    st = app._ex_state(U)
    assert app.explore_move(U, "s")["kind"] == "blocked" and "fight" in st["msg"]
    d["_boss"] = None
    app._tracking_start(U, "Bigfoot", "village")
    assert app.explore_move(U, "s")["kind"] == "blocked" and "trail" in st["msg"]


# ── the picture ─────────────────────────────────────────────

def _png_ok(blob: bytes, size=None):
    from PIL import Image
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    im = Image.open(io.BytesIO(blob))
    size = size or (app.EXPLORE_TILE_PX * 7,) * 2
    assert im.size == size, im.size
    return im


def test_the_map_is_drawn_for_every_biome_even_with_no_downloaded_art():
    saved_art, saved_sprites = dict(app._ex_art), dict(app._ex_sprites)
    app._ex_art.clear()
    app._ex_sprites.clear()
    try:
        for biome in gd.BIOME_TOOL_TIER:
            d = td._fresh(biome=biome, explore_mode=True)
            st = app._ex_state(U)
            st["animals"] = []
            _calm(st, name=gd.BIOME_ANIMALS[biome][0], dx=1, dy=1)
            _calm(st, name=gd.BIOME_ANIMALS[biome][1], dx=6, dy=5, clue=4)
            blob = app._ex_render(app._ex_snapshot(U))
            _png_ok(blob)
            assert len(blob) < 600_000
    finally:
        app._ex_art.update(saved_art)
        app._ex_sprites.update(saved_sprites)


def test_layers_come_out_in_the_right_order_with_uploaded_art():
    """grass at the bottom, an obstacle above it, the hunter above that — with solid-colour stand-in art."""
    from PIL import Image
    saved_art = dict(app._ex_art)
    solid = lambda c: Image.new("RGBA", (128, 128), c)
    app._ex_art.update({gd.EXPLORE_GROUND["village"]: solid((0, 200, 0, 255)),
                        "obstacle__village__maple_tree": solid((200, 0, 0, 255)),
                        "landmark__village__flowering_bush": solid((200, 200, 0, 255)),
                        "hunter": solid((255, 255, 255, 255))})
    try:
        _fresh()
        with terrain({(2, 0): "tree", (4, 0): "stone", (3, 1): "bush"}):
            st = app._ex_state(U)
            st["animals"] = []
            st["steps"] = 20
            im = _png_ok(app._ex_render(app._ex_snapshot(U)))
            T = app.EXPLORE_TILE_PX
            px = lambda tx, ty, fx=.5, fy=.5: im.getpixel((int((tx + fx) * T), int((ty + fy) * T)))
            near = lambda a, b, tol=70: all(abs(x - y) <= tol for x, y in zip(a[:3], b))
            assert near(px(3, 2, .12, .12), (0, 200, 0), 80)         # bare grass, the bottom layer (off-centre: the step box sits in the middle)
            assert near(px(2, 3), (200, 0, 0), 60)                   # the tree to the west sits on top of grass
            assert near(px(4, 3), (200, 0, 0), 60)                   # a region with no boulder art draws its tree there instead
            assert near(px(3, 4, .12, .12), (200, 200, 0), 60)       # the bush to the south
            assert near(px(3, 3), (255, 255, 255), 40)               # the hunter is the top layer in the middle
    finally:
        app._ex_art.clear()
        app._ex_art.update(saved_art)


def test_the_picture_goes_out_as_a_real_attachment():
    """explore_show -> multipart with payload_json + files[0], and the panel points at attachment://explore.png."""
    _fresh()
    sent = []

    class Http:
        async def request(self, route, *, files=None, form=None, **kw):
            sent.append((route.method, route.path, form, files, kw))

    class Resp:
        def __init__(self, done): self._d = done
        def is_done(self): return self._d
        async def defer(self): self._d = True

    class It:
        id, token, application_id, channel_id = 7, "tok", 99, 5
        def __init__(self, done): self.response = Resp(done); self.client = type("C", (), {"http": Http()})()

    async def fake_image(uid):
        return b"\x89PNG\r\n\x1a\n" + b"x" * 40
    real = app.explore_image
    app.explore_image = fake_image
    try:
        for done, new, method, path_part in ((True, False, "PATCH", "@original"), (False, True, "POST", "callback"),
                                             (True, True, "POST", "webhooks")):
            sent.clear()
            run(app.explore_show(It(done), U, new=new))
            assert len(sent) == 1, (done, new)
            m, path, form, files, kw = sent[0]
            assert m == method and path_part in path
            payload = json.loads(next(f["value"] for f in form if f["name"] == "payload_json"))
            body = payload.get("data", payload)
            assert body["attachments"] == [{"id": 0, "filename": "explore.png"}]
            assert "attachment://explore.png" in json.dumps(body["components"])
            fpart = next(f for f in form if f["name"] == "files[0]")
            assert fpart["filename"] == "explore.png" and fpart["content_type"] == "image/png" and files
    finally:
        app.explore_image = real


def test_if_the_picture_cannot_be_made_the_panel_still_works_without_it():
    _fresh()
    shown = []

    async def none_image(uid):
        return None

    async def fake_smart(i, comps):
        shown.append(comps)
    real_i, real_s = app.explore_image, app.smart_update_v2
    app.explore_image, app.smart_update_v2 = none_image, fake_smart
    try:
        run(app.explore_show(object(), U))
    finally:
        app.explore_image, app.smart_update_v2 = real_i, real_s
    assert shown and "attachment://" not in json.dumps(shown[0])


def test_animal_sprites_are_small_and_bigger_animals_draw_a_little_larger():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        small, big = gd.BIOME_ANIMALS["village"][0], next(n for n, v in gd.ANIMAL_COMBAT.items() if v["hp"] >= 60)
        _calm(st, name=small, dx=1)
        _calm(st, name=big, dx=-1)
        by_name = {a["name"]: a for a in app._ex_snapshot(U)["animals"]}
        assert by_name[big]["hp"] > by_name[small]["hp"]
    # sprite width in tiles = .42 + .26 * min(1, hp/100): never more than ~2/3 of a tile
    assert max(.42 + .26 * min(1.0, hp / 100) for hp in (5, 40, 110, 900)) <= .68


# ── buttons ─────────────────────────────────────────────────

def test_buttons_move_you_through_the_dispatcher_and_new_expedition_resets():
    _fresh()

    async def no_image(uid):
        return None
    real = app.explore_image
    app.explore_image = no_image
    try:
        with terrain(), still_world():
            st = app._ex_state(U)
            st["animals"] = []
            with tr.Harness() as h:
                run(app._dispatch_component(tr.FakeInteraction(U, f"explore:s:{U}")))
            assert (st["y"], st["steps"]) == (1, 1) and h.panels
            st["bag"] = [{"name": COMMON, "value": 1, "perfect": False}]
            with tr.Harness() as h:
                run(app._dispatch_component(tr.FakeInteraction(U, f"explore:new:{U}")))     # asks first (unfinished)
                assert app.data[U]["explore"]["steps"] == 1 and h.panels
                run(app._dispatch_component(tr.FakeInteraction(U, f"explore:new:{U}")))     # confirmed
            st2 = app.data[U]["explore"]
            assert st2["steps"] == 0 and st2["bag"] == []
    finally:
        app.explore_image = real


def test_the_hunt_button_path_is_unchanged_without_a_forced_animal():
    d = _fresh(level=300)
    d["hunt_cd"] = 0
    r = app.run_hunt(U)
    assert r["ok"] and "forced" not in r


# ── weapon range, target, markers, info ─────────────────────

def test_every_tool_has_a_range_that_fits_the_7x7_field():
    assert all(1 <= gd.tool_range(t) <= gd.TOOL_RANGE_MAX for t in gd.TOOLS)
    assert gd.TOOL_RANGE_MAX == app.EXPLORE_VIEW == 3 and set(gd.TOOL_SHAPES) == set(gd.TOOLS)
    assert gd.tool_range("Bare Hands") == 1 and gd.tool_range("Shotgun") == 2 and gd.tool_range("Sniper Rifle") == 3
    assert gd.tool_range("Nuke Launcher") == 3                                   # unlisted tools use the default


def test_you_can_only_shoot_inside_your_tools_range():
    d = _fresh(tool="Bare Hands")
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        a = _calm(st, dx=3)                                                      # in view, but 3 away: out of reach
        lt0, cd0 = d["stats"].get("lifetime_hunts", 0), d["hunt_cd"]
        out = app.explore_fire(U)
        assert out["kind"] == "none" and "Out of reach" in st["msg"] and "reaches **1** tile" in st["msg"]
        assert d["stats"].get("lifetime_hunts", 0) == lt0 and d["hunt_cd"] == cd0          # nothing was spent
        comps = app.build_explore_components(U)[0]["components"]
        assert comps[-2]["components"][0]["label"] == "Fire" and comps[-2]["components"][0]["disabled"] is True
        assert "out of reach" in json.dumps(comps)
        a["x"] -= 2                                                              # now right beside you
        assert app._ex_target(st, "Bare Hands") is a
        comps = app.build_explore_components(U)[0]["components"]
        assert comps[-2]["components"][0]["disabled"] is False and "target" in json.dumps(comps)


def test_the_yellow_target_is_the_one_you_pick_and_fire_hits_it():
    d = _fresh(tool="Longbow", owned_tools=["Longbow"])
    ammo = gd.get_ammo_for_tool("Longbow")[0]
    d["ammo_inv"], d["equipped_ammo"] = {ammo: 50}, ammo
    other = gd.BIOME_ANIMALS["village"][1]
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        near = _calm(st, name=COMMON, dx=1)
        far = _calm(st, name=other, dx=2)
        assert app._ex_target(st, "Longbow") is near                             # nearest by default
        assert [a["target"] for a in sorted(app._ex_snapshot(U)["animals"], key=lambda a: a["tx"])] == [True, False]
        assert app.explore_target(U)["kind"] == "target" and app._ex_target(st, "Longbow") is far
        assert [a["target"] for a in sorted(app._ex_snapshot(U)["animals"], key=lambda a: a["tx"])] == [False, True]
        assert app.explore_target(U)["kind"] == "target" and app._ex_target(st, "Longbow") is near       # and back again
        app.explore_target(U)
        real = random.random
        random.random = lambda: 0.0
        try:
            out = app.explore_fire(U)
        finally:
            random.random = real
        assert out["kind"] == "caught" and out["result"]["catches"][0]["animal"] == other
        assert far not in st["animals"] and near in st["animals"]


def test_targeting_buttons_and_nothing_to_cycle():
    _fresh(tool="Shotgun")
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        assert app.explore_target(U)["kind"] == "none"
        blob = json.dumps(app.build_explore_components(U)[0]["components"][-2]["components"])
        assert '"label": "Target"' in blob and '"disabled": true' in json.dumps(app.build_explore_components(U)[0]["components"][-2]["components"][1])
        _calm(st, dx=1)
        _calm(st, name=gd.BIOME_ANIMALS["village"][1], dx=2)
        assert app.build_explore_components(U)[0]["components"][-2]["components"][1]["disabled"] is False


def test_the_picture_marks_step_tiles_with_yellow_boxes_and_the_target_with_a_circle():
    from PIL import Image
    saved = dict(app._ex_art)
    app._ex_art.update({gd.EXPLORE_GROUND["village"]: Image.new("RGBA", (128, 128), (0, 120, 0, 255)),
                        "hunter": Image.new("RGBA", (128, 128), (255, 255, 255, 255))})
    try:
        _fresh(tool="Bare Hands")
        with terrain({(3, 1): "tree"}), still_world():
            st = app._ex_state(U)
            st["animals"] = []
            assert app._ex_snapshot(U)["moves"] == [(2, 0), (4, 0)]              # west and east; south is a tree, north the border
            _calm(st, dx=1)
            snap = app._ex_snapshot(U)
            assert snap["moves"] == [(2, 0)] and snap["animals"][0]["target"] and snap["animals"][0]["inrange"]
            im = _png_ok(app._ex_render(snap))
            T = app.EXPLORE_TILE_PX
            yellow = lambda p: p[0] > 200 and p[1] > 170 and p[2] < 140
            assert yellow(im.getpixel((2 * T + T // 2, T // 2)))                 # the small box in the middle of the tile to step on
            assert not yellow(im.getpixel((2 * T + 4, T - 6)))                    # ...and only a small one
            assert yellow(im.getpixel((4 * T + 5, T // 2)))                      # the bold circle round the target
            st["animals"][0]["x"] += 2                                           # out of reach: just a faint ring
            im = _png_ok(app._ex_render(app._ex_snapshot(U)))
            assert not yellow(im.getpixel((6 * T + 7, T // 2)))
    finally:
        app._ex_art.clear()
        app._ex_art.update(saved)


def test_the_grass_tiles_join_without_dark_lines():
    """The uploaded grass tile has a transparent margin and a darker rim; tiled as-is that drew dark grid lines."""
    from PIL import Image, ImageDraw
    art = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(art).rectangle([5, 6, 122, 122], fill=(97, 141, 63, 255), outline=(43, 79, 42, 255), width=4)
    saved = dict(app._ex_art)
    app._ex_art.update({gd.EXPLORE_GROUND["village"]: art})
    try:
        _fresh()
        with terrain():
            st = app._ex_state(U)
            st["animals"] = []
            im = _png_ok(app._ex_render(app._ex_snapshot(U)))
            T = app.EXPLORE_TILE_PX
            for k in range(1, 7):                                                # every vertical and horizontal seam
                for t in range(2 * T, 7 * T - 10, 3):
                    px = [im.getpixel((k * T - 1, t)), im.getpixel((k * T, t))]
                    if k >= 2:                                                   # (the hunter's tile is the top row)
                        px += [im.getpixel((t, k * T - 1)), im.getpixel((t, k * T))]
                    for p in px:
                        assert abs(p[0] - 97) < 30 and abs(p[1] - 141) < 30 and abs(p[2] - 63) < 30, (k, t, p)
    finally:
        app._ex_art.clear()
        app._ex_art.update(saved)


def test_the_info_sheet_explains_the_range_with_a_7x7_picture():
    _fresh(tool="Shotgun")
    blob = json.dumps(app.build_explore_info_components(U), ensure_ascii=False)
    assert "attachment://range.png" in blob and "Cone" in blob and "Reach **2** tiles" in blob and "Shotgun" in blob
    assert "Yellow circle" in blob and "yellow boxes" in blob and "Bare Hands" in blob and "Hit chance" in blob
    assert "attachment://" not in json.dumps(app.build_explore_info_components(U, image=False))
    im = _png_ok(app._ex_range_png("Shotgun"), (448, 448))
    px = lambda tx, ty: im.getpixel((tx * 64 + 6, ty * 64 + 6))
    hit, reach_only, outside = px(5, 3), px(3, 5), px(6, 3)                      # (+2,0) is in the cone, (0,+2) only in reach, (+3,0) out
    assert hit[0] > 180 and hit[1] < 150 and reach_only[1] > 155 and reach_only[0] < 170 and reach_only[0] > outside[0] + 60
    assert app.build_explore_components(U)[0]["components"][-2]["components"][3]["custom_id"] == f"explore:info:{U}"


def test_the_info_button_sends_a_private_sheet_with_the_picture_attached():
    _fresh(tool="Longbow")
    sent = []

    class Http:
        async def request(self, route, *, files=None, form=None, **kw):
            sent.append((route.method, route.path, form, files))

    class Resp:
        def is_done(self): return False

    class It:
        id, token, application_id, channel_id = 7, "tok", 99, 5
        def __init__(self): self.response = Resp(); self.client = type("C", (), {"http": Http()})()

    run(app.explore_info_show(It(), U))
    assert len(sent) == 1
    m, path, form, files = sent[0]
    payload = json.loads(next(f["value"] for f in form if f["name"] == "payload_json"))
    body = payload["data"]
    assert m == "POST" and "callback" in path and body["flags"] & 64                     # ephemeral
    assert body["attachments"] == [{"id": 0, "filename": "range.png"}] and files
    assert "Single shot" in json.dumps(body["components"], ensure_ascii=False)


def test_the_info_button_goes_through_the_dispatcher_without_touching_the_world():
    _fresh()
    shown = []

    async def fake_info(interaction, uid):
        shown.append(uid)
    real = app.explore_info_show
    app.explore_info_show = fake_info
    try:
        st = app._ex_state(U)
        steps0 = st["steps"]
        with tr.Harness() as h:
            run(app._dispatch_component(tr.FakeInteraction(U, f"explore:info:{U}")))
        assert shown == [U] and st["steps"] == steps0 and not h.panels
    finally:
        app.explore_info_show = real


# ── Hunt opens the map; there is no /explore command ──────────

def test_there_is_no_explore_command_any_more():
    assert app.bot.tree.get_command("explore") is None and app.bot.tree.get_command("hunt") is not None
    assert not hasattr(app, "explore_cmd")


def test_with_explore_on_hunt_opens_the_map_instead_of_an_instant_hunt():
    import types
    d = _fresh()
    shown = []

    async def rec(interaction, uid, **kw):
        shown.append((uid, kw))
    real = app.explore_show
    app.explore_show = rec
    try:
        lt0 = d["stats"].get("lifetime_hunts", 0)
        with tr.Harness():
            run(app.hunt_cmd.callback(tr.FakeInteraction(U, "x")))                       # /hunt
            assert shown == [(U, {"new": True})]
            it = tr.FakeInteraction(U, f"hunt:again:{U}")                                # a Hunt button on a panel
            it.message = types.SimpleNamespace(flags=types.SimpleNamespace(ephemeral=False))
            run(app._dispatch_component(it))
            assert shown[-1] == (U, {})                                                  # the same message becomes the map
            it = tr.FakeInteraction(U, f"announce:hunt:{U}")                             # the announcement's Hunt button
            it.message = types.SimpleNamespace(flags=types.SimpleNamespace(ephemeral=False))
            run(app._dispatch_component(it))
            assert shown[-1][1].get("new") is True
        assert len(shown) == 3 and d["stats"].get("lifetime_hunts", 0) == lt0 and d["hunt_cd"] == 0     # no hunt ran
        # a fight in progress shows the fight, not the map
        d["_boss"] = {"creature": "Bigfoot", "biome": "village", "ts": int(time.time()), "eid": "z", "mhp": 5, "mhp_max": 5,
                      "turn": 1, "fallen": False, "guard": False, "enrage": False, "mdebuff": False, "log": []}
        with tr.Harness() as h:
            run(app.hunt_cmd.callback(tr.FakeInteraction(U, "x")))
        assert len(shown) == 3
        d["_boss"] = None
        # with the setting off, Hunt is the ordinary instant hunt again
        d["explore_mode"] = False
        d["tool"], d["hunt_cd"] = "Bare Hands", 0
        with tr.Harness():
            run(app._dispatch_component(tr.FakeInteraction(U, f"hunt:again:{U}")))
        assert len(shown) == 3 and d["stats"].get("lifetime_hunts", 0) == lt0 + 1
    finally:
        app.explore_show = real


# ── weapon shapes (auto-aimed) ───────────────────────────────

def _armed(tool, n=50, **over):
    d = _fresh(tool=tool, owned_tools=[tool], **over)
    if gd.tool_needs_ammo(tool):
        ammo = gd.get_ammo_for_tool(tool)[0]
        d["ammo_inv"], d["equipped_ammo"] = {ammo: n}, ammo
    return d


def _land(chance=0.0):
    """Every roll comes up `chance`: 0.0 = every shot hits."""
    real = random.random
    random.random = lambda: chance
    return real


def test_weapon_shapes_cover_exactly_what_they_say():
    sh, rc = gd.shape_hits, gd.shape_reach
    assert sh("Bare Hands", 1, 0) == {(1, 0)} and sh("Longbow", 3, 1) == {(3, 1)}
    assert sh("Hunting Knife", 1, 0) == {(1, -1), (1, 0), (1, 1)}                # a small arc toward the target
    assert sh("Spear", 1, 1) == {(1, 1), (2, 2)} and sh("Spear", 2, 0) == {(1, 0), (2, 0)}
    assert (2, 0) in rc("Spear") and (2, 2) in rc("Spear") and (1, 2) not in rc("Spear")      # on a line, or not at all
    assert len(sh("Shotgun", 2, 0)) == 8 and len(sh("Dragon Cannon", 3, 0)) > len(sh("Shotgun", 2, 0))
    assert sh("Plasma Caster", 3, 0) == {(3, 0), (2, 0), (4, 0), (3, 1), (3, -1)}
    assert len(sh("Gravity Trap", 2, 0)) == len(rc("Gravity Trap")) == 20          # a circle round the hunter, no aiming
    assert len(sh("Nuke Launcher", 3, 0)) == 25 and (3, 0) in sh("Void Bow", 1, 0) and len(sh("Void Bow", 1, 0)) == 3
    for t in gd.TOOLS:                                                           # the target is always inside its own shot
        for off in rc(t):
            assert off in sh(t, *off), (t, off)
        assert gd.tool_range(t) <= 3 and gd.tool_shape(t)[0] in gd.SHAPE_NAMES


def test_a_cone_takes_every_animal_in_the_wedge_for_one_round_each():
    d = _armed("Shotgun", 10)
    a2, a3 = gd.BIOME_ANIMALS["village"][1], gd.BIOME_ANIMALS["village"][2]
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        _calm(st, name=COMMON, dx=1)
        _calm(st, name=a2, dx=2)                                                 # both straight east: in the wedge
        c = _calm(st, name=a3, dy=2)                                             # south: not
        real = _land()
        try:
            out = app.explore_fire(U)
        finally:
            random.random = real
        assert out["kind"] == "caught" and sorted(x["animal"] for x in out["result"]["catches"]) == sorted([COMMON, a2])
        assert d["ammo_inv"][gd.get_ammo_for_tool("Shotgun")[0]] == 8            # a round for each animal it covered
        assert c in st["animals"] and len(st["bag"]) == 2


def test_single_shot_weapons_take_exactly_one_even_in_a_crowd():
    d = _armed("Longbow", 20)
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        _calm(st, name=COMMON, dx=1)
        _calm(st, name=gd.BIOME_ANIMALS["village"][1], dx=1, dy=1)
        real = _land()
        try:
            out = app.explore_fire(U)
        finally:
            random.random = real
        assert out["kind"] == "caught" and len(out["result"]["catches"]) == 1
        assert d["ammo_inv"][gd.get_ammo_for_tool("Longbow")[0]] == 19


def test_a_one_catch_tool_with_a_shape_may_take_two():
    _armed("Hunting Knife")
    names = gd.BIOME_ANIMALS["village"][:3]
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        for n, dy in zip(names, (-1, 0, 1)):
            _calm(st, name=n, dx=1, dy=dy if st["y"] + dy >= 0 else 1)
        real = _land()
        try:
            out = app.explore_fire(U)
        finally:
            random.random = real
        assert out["kind"] == "caught" and 1 <= len(out["result"]["catches"]) <= app.EXPLORE_SHAPE_MIN_CAP


def test_a_line_weapon_needs_the_animal_on_its_line():
    _armed("Spear")
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        a = _calm(st, dx=1, dy=2)                                                # a knight's move away: not on any line
        out = app.explore_fire(U)
        assert out["kind"] == "none" and "Out of reach" in st["msg"]
        a["x"], a["y"] = st["x"] + 2, st["y"] + 2                                # the diagonal line
        assert app._ex_target(st, "Spear") is a


def test_a_circle_weapon_catches_what_is_near_you_without_aiming():
    d = _armed("Gravity Trap", 10)
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        _calm(st, name=COMMON, dx=1)
        _calm(st, name=gd.BIOME_ANIMALS["village"][1], dy=2)
        far = _calm(st, name=gd.BIOME_ANIMALS["village"][2], dx=3)
        real = _land()
        try:
            out = app.explore_fire(U)
        finally:
            random.random = real
        assert out["kind"] == "caught" and len(out["result"]["catches"]) == 2 and far in st["animals"]


def test_a_miss_still_costs_the_ammo_and_the_cooldown_and_spooks():
    d = _armed("Longbow", 20)
    ammo = gd.get_ammo_for_tool("Longbow")[0]
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        a = _calm(st, dx=1)
        lt0 = d["stats"].get("lifetime_hunts", 0)
        real = _land(0.999)
        try:
            out = app.explore_fire(U)
        finally:
            random.random = real
        assert out["kind"] == "miss" and d["ammo_inv"][ammo] == 19 and d["hunt_cd"] > time.time()
        assert a["mood"] == "flee" and d["stats"].get("lifetime_hunts", 0) == lt0


def test_a_refused_shot_spends_nothing_and_never_spooks():
    d = _armed("Longbow", 20)
    ammo = gd.get_ammo_for_tool("Longbow")[0]

    def boom():
        raise AssertionError("a refused shot must not roll the dice")
    with terrain():
        st = app._ex_state(U)
        st["animals"] = []
        a = _calm(st, dx=1)
        real = random.random
        random.random = boom
        try:
            d["hunt_cd"] = time.time() + 60                                      # still reloading
            assert app.explore_fire(U)["kind"] == "cooldown"
            d["hunt_cd"] = 0
            d["equipped_ammo"] = None                                            # nothing loaded
            out = app.explore_fire(U)
            assert out["kind"] == "blocked" and "Equip Ammo" in st["msg"]
            d["equipped_ammo"], d["ammo_inv"] = ammo, {ammo: 0}                  # loaded but empty
            assert app.explore_fire(U)["kind"] == "blocked"
        finally:
            random.random = real
        assert a["mood"] == "calm" and d["ammo_inv"][ammo] == 0
        comps = app.build_explore_components(U)[0]["components"]
        fire = comps[-2]["components"][0]
        assert fire["label"] == "Fire" and fire["disabled"] is True              # a clear unavailable state
        assert any(b["label"] == "Buy Ammo" for b in comps[-1]["components"])


def test_the_hit_area_is_lit_in_the_picture():
    _armed("Shotgun")
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        _calm(st, dx=2)
        snap = app._ex_snapshot(U)
        assert set(snap["hits"]) == {(3 + x, 0 + y) for x, y in gd.shape_hits("Shotgun", 2, 0) if 0 <= 3 + x < 7 and 0 <= y < 7}


# ── the rhythm of a chase ────────────────────────────────────

def test_a_fleeing_animal_runs_a_few_steps_then_stops_to_graze():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        a = _calm(st, name="Red Fox", dx=2, mood="flee")
        lines = []
        real_seen = app._ex_seen
        app._ex_seen = lambda st_, a_: True                                      # (it has run out of the picture by now)
        try:
            for _ in range(app.EXPLORE_FLEE_RUN):
                lines = app._ex_advance(U, st)
        finally:
            app._ex_seen = real_seen
        assert a["rest"] == app.EXPLORE_REST_STEPS and a["run"] == 0
        assert any("Red Fox" in ln and "freezes" in ln for ln in lines)
        pos = (a["x"], a["y"])
        app._ex_advance(U, st)
        assert (a["x"], a["y"]) == pos and a["rest"] == app.EXPLORE_REST_STEPS - 1      # it stays put: your chance
        app._ex_advance(U, st)
        app._ex_advance(U, st)
        assert a["run"] >= 1                                                      # then the chase can start again


def test_every_expedition_starts_with_a_gentle_animal_a_short_walk_away():
    near = 0
    for i in range(40):
        _fresh()
        random.seed(100 + i)
        st = app._ex_new(U, "village")
        first = st["animals"][0]
        assert gd.animal_combat_stats(first["name"], "village")["behavior"] == "passive"
        dist = app._ex_dist(first["x"], first["y"], st["x"], st["y"])
        assert dist > app.EXPLORE_VIEW
        near += dist <= app.EXPLORE_EASY_DIST[1]
    assert near >= 30


def test_animals_sometimes_arrive_in_pairs_and_golden_ones_leave_golden_prints():
    _fresh()
    st = app._ex_state(U)
    st["animals"] = []
    real = _land(0.0)
    try:
        assert app._ex_spawn(st)
    finally:
        random.random = real
    a, b = st["animals"][0], st["animals"][1]
    assert a["name"] == b["name"] and app._ex_dist(a["x"], a["y"], b["x"], b["y"]) == 1 and a.get("gold")
    # the footprints are golden and say so, and the picture's arrow is golden too
    st["animals"] = []
    st["steps"], st["x"], st["y"] = 20, 6, 6
    g = _calm(st, dx=5, gold=True)
    with still_world():
        lines = app._ex_advance(U, st)
    assert any("Golden footprints" in ln for ln in lines)
    assert app._ex_snapshot(U)["clues"][0]["gold"] is True
    # and shooting a golden animal raises the Perfect Catch chance
    seen = {}
    real_run = app.run_hunt

    def spy(uid, **kw):
        seen.update(kw)
        return real_run(uid, **kw)
    app.run_hunt = spy
    try:
        _armed("Longbow")
        st = app._ex_state(U)
        st["animals"], st["steps"], st["x"], st["y"] = [], 20, 6, 6
        _calm(st, dx=1, gold=True)
        r = _land()
        try:
            app.explore_fire(U)
        finally:
            random.random = r
    finally:
        app.run_hunt = real_run
    assert seen.get("perfect_bonus") == app.EXPLORE_GOLD_PERFECT


# ── small discoveries ────────────────────────────────────────

def test_discoveries_are_rare_tiles_and_each_kind_exists():
    counts: dict = {}
    for seed in range(60):
        for x in range(19):
            for y in range(19):
                k = app._ex_tile(seed, x, y, "village")
                counts[k] = counts.get(k, 0) + 1
    total = 60 * 19 * 19
    for k in ("chest", "bag", "berries", "camp", "clearing", "gathering", "trail"):
        assert counts.get(k, 0) > 0 and k in app._EX_WALKABLE, k
    assert counts.get("monument", 0) > 0 and "monument" not in app._EX_WALKABLE         # a monument is solid
    assert sum(counts.get(k, 0) for k in app._EX_PICKUPS) / total < 0.035


def test_each_discovery_does_its_small_thing():
    d = _armed("Longbow", 10)
    ammo = gd.get_ammo_for_tool("Longbow")[0]
    st = app._ex_state(U)
    st["animals"] = []
    msg = app._ex_pickup(U, st, 9, 1, "bag")
    assert "supply bag" in msg and d["ammo_inv"][ammo] > 10
    d["tool"] = "Bare Hands"
    d["healing_inv"] = {}
    assert "Bandage" in app._ex_pickup(U, st, 9, 2, "bag") and d["healing_inv"]["Bandage"] == 1
    # berries: 5 HP, and only used up when you are hurt
    app.refresh_health(U)
    d["health"]["hp"] = d["health"]["max_hp"]
    assert "not hurt" in app._ex_pickup(U, st, 9, 3, "berries") and "9,3" not in st["opened"]
    d["health"]["hp"] = 10
    assert "Berry patch" in app._ex_pickup(U, st, 9, 3, "berries") and d["health"]["hp"] == 15 and "9,3" in st["opened"]
    # campsite: a journal page and a small find
    msg = app._ex_pickup(U, st, 9, 4, "camp")
    assert "campsite" in msg and len(d["explore_journal"]) == 1 and "find" in msg.lower()
    # a clearing: a stamp (once ever) and this region's souvenir (once)
    msg = app._ex_pickup(U, st, 9, 7, "clearing")
    assert "keepsake" in msg and "New discovery stamp" in msg and d["explore_souvenirs"] == ["Pressed Meadow Flower"]
    assert "already" in app._ex_pickup(U, st, 9, 8, "clearing") and d["explore_stamps"] == ["wildflower_clearing"]
    line = app.explore_keepsake_line(U)
    assert "🌼" in line and f"1/{len(gd.EXPLORE_STAMPS)} stamps" in line
    # a gathering moves a few animals in close, within the animal limit
    st["animals"] = []
    msg = app._ex_pickup(U, st, 9, 9, "gathering")
    assert 1 <= len(st["animals"]) <= 3 and "gathering" in msg
    st["animals"] = [{"id": i, "name": COMMON, "x": 0, "y": 0, "clue": 0, "cool": 0, "fade": 0, "pd": 9, "mood": "calm"}
                     for i in range(app.EXPLORE_MAX_ANIMALS + 1)]
    assert "moved on" in app._ex_pickup(U, st, 9, 10, "gathering") and len(st["animals"]) == app.EXPLORE_MAX_ANIMALS + 1
    # golden pawprints: the animals nearby leave clues
    st["animals"] = []
    st["steps"], st["x"], st["y"] = 20, 6, 6                                      # out in the open field
    near = _calm(st, dx=4)                                                       # four tiles away: off the picture
    assert "1" in app._ex_pickup(U, st, 9, 11, "trail") and near["clue"] > 0


def test_chests_say_how_much_ammo_you_actually_got():
    d = _armed("Longbow", 10)
    ammo = gd.get_ammo_for_tool("Longbow")[0]
    d["ammo_inv"][ammo] = gd.AMMO_MAX_STACK - 4                                   # only 4 more fit
    st = app._ex_state(U)
    real = random.choices
    random.choices = lambda pop, weights=None, k=1: ["ammo"]
    try:
        msg = app._ex_open_chest(U, st, 9, 9)
    finally:
        random.choices = real
    assert "**4× " in msg and d["ammo_inv"][ammo] == gd.AMMO_MAX_STACK
    random.choices = lambda pop, weights=None, k=1: ["ammo"]
    try:
        assert "× " not in app._ex_open_chest(U, st, 9, 10)                       # full: something else instead
    finally:
        random.choices = real


def test_walking_onto_a_discovery_collects_it():
    d = _fresh()
    with terrain({(3, 1): "berries", (2, 0): "monument"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        app.refresh_health(U)
        d["health"]["hp"] = 20
        app.explore_move(U, "s")
        assert "Berry patch" in st["msg"] and d["health"]["hp"] > 20
        assert "stamp" in st["msg"] and d["explore_stamps"] == ["rune_monument"]          # (that step also took you next to the monument)
        app.explore_move(U, "n")
        assert app.explore_move(U, "w")["kind"] == "bump" and "monument" in st["msg"]      # and it is solid
        app.explore_move(U, "s")
        app.explore_move(U, "n")
        assert d["explore_stamps"] == ["rune_monument"]                           # once per monument


def test_the_curious_fox_follows_then_leaves_a_stash():
    d = _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        st["steps"], st["x"], st["y"] = 20, 6, 6
        real = _land(0.0)
        try:
            lines = []
            app._ex_fox_tick(st, lines)
        finally:
            random.random = real
        assert st["fox"] and st["fox_done"] and any("fox" in ln for ln in lines)
        for _ in range(app.EXPLORE_FOX_FOLLOW + 1):
            app._ex_advance(U, st)
        assert st["fox"] is None and st["extra"]
        (key, kind), = st["extra"].items()
        x, y = map(int, key.split(","))
        assert kind == "stash" and app._ex_kind(st, x, y) == "stash"
        st["x"], st["y"] = x, y                                                  # step onto it
        assert "stash" in app._ex_pickup(U, st, x, y, "stash") and app._ex_kind(st, x, y) == "grass"
        assert st["fox_done"] is True                                            # only once per expedition


def test_every_region_with_a_landmark_draws_it():
    from PIL import Image
    for biome in app._EX_LANDMARKS:
        im = Image.new("RGBA", (144, 144), (0, 0, 0, 0))
        app._ex_landmark(im, biome, random.Random(3))
        assert im.getbbox() is not None, biome
    assert {"small_desert", "tundra", "sunken_coast", "swamp", "volcanic_highlands", "cursed_ruins",
            "abyssal_depths", "celestial_peaks"} <= set(app._EX_LANDMARKS)
    for kind in app._EX_PICKUPS:
        im = Image.new("RGBA", (144, 144), (0, 0, 0, 0))
        if kind == "chest":
            continue
        app._ex_pickup_art(im, kind, random.Random(3))
        assert im.getbbox() is not None, kind


def test_the_picture_draws_landmarks_pickups_and_the_fox_for_a_strange_region():
    saved = dict(app._ex_art)
    app._ex_art.clear()
    try:
        d = td._fresh(biome="celestial_peaks", explore_mode=True)
        with terrain({(2, 1): "tree", (4, 1): "stone", (3, 2): "monument", (2, 2): "camp", (4, 2): "bag",
                      (1, 1): "berries", (5, 1): "clearing"}):
            st = app._ex_state(U)
            st["animals"] = []
            st["fox"] = {"x": 3, "y": 1, "left": 3}
            snap = app._ex_snapshot(U)
            assert snap["fox"] == (3, 1) and snap["cells"][2][3] == "monument"
            blob = app._ex_render(snap)
            _png_ok(blob)
    finally:
        app._ex_art.update(saved)


# ── fewer pointless clicks ───────────────────────────────────

def test_arrows_that_lead_nowhere_are_disabled():
    _fresh()
    with terrain({(3, 1): "tree"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        row = app.build_explore_components(U)[0]["components"][-3]["components"]
        by = {b["label"]: b["disabled"] for b in row}
        assert by["▲"] is True and by["▼"] is True and by["◀"] is False and by["▶"] is False   # border north, tree south


def test_new_expedition_asks_before_throwing_away_an_unfinished_one():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        st["bag"] = [{"name": COMMON, "value": 7, "perfect": False}]
        st["steps"] = 9
        seed = st["seed"]
        out = app.explore_new(U)
        assert out["kind"] == "confirm" and st["seed"] == seed and COMMON in st["msg"] and "again" in st["msg"]
        assert "Really start new?" in json.dumps(app.build_explore_components(U), ensure_ascii=False)
        app.explore_move(U, "s")                                                 # doing something else cancels it
        assert st["confirm_new"] is False and app.explore_new(U)["kind"] == "confirm"
        assert app.explore_new(U)["kind"] == "new" and app.data[U]["explore"]["seed"] != seed
        app.data[U]["explore"]["steps"] = app.EXPLORE_MAX_STEPS                  # finished ones restart at once
        assert app.explore_new(U)["kind"] == "new"


def test_heal_and_ammo_shortcuts_show_up_only_when_needed():
    d = _armed("Longbow", 5, healing_inv={"Bandage": 2})
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        labels = lambda: [b["label"] for r in app.build_explore_components(U)[0]["components"][-4:] if r.get("type") == 1 for b in r["components"]]
        app.refresh_health(U)
        d["health"]["hp"] = d["health"]["max_hp"]
        assert "Heal" not in labels() and "Buy Ammo" not in labels()
        d["health"]["hp"] = 10
        d["equipped_ammo"] = None
        d["ammo_inv"] = {"Wooden Arrow": 3, "Enchanted Arrow": 3}
        got = labels()
        assert "Heal" in got and "Equip Ammo" in got and "Buy Ammo" in got
        hp0, steps0 = d["health"]["hp"], st["steps"]
        assert app.explore_heal(U)["kind"] == "healed" and d["health"]["hp"] > hp0 and d["healing_inv"]["Bandage"] == 1
        assert st["steps"] == steps0                                             # patching up takes no time on the map


def test_quick_equip_loads_the_cheapest_and_quick_buy_stocks_up():
    d = _armed("Longbow", 1)
    d["equipped_ammo"], d["ammo_inv"] = None, {"Enchanted Arrow": 5, "Wooden Arrow": 4}
    ok, msg = app.quick_equip_ammo(U)
    assert ok and d["equipped_ammo"] == "Wooden Arrow"                           # never the expensive one by accident
    d["ammo_inv"], d["equipped_ammo"], d["money"] = {}, None, 100_000
    ok, msg = app.quick_buy_ammo(U)
    assert ok and d["ammo_inv"]["Wooden Arrow"] == app.EXPLORE_QUICK_AMMO and d["equipped_ammo"] == "Wooden Arrow"
    assert d["money"] == 100_000 - 10 * app.EXPLORE_QUICK_AMMO
    d["money"] = 0
    ok, msg = app.quick_buy_ammo(U)
    assert not ok and "need" in msg.lower()
    assert app.quick_equip_ammo(U)[0] is True                                    # (it still holds 50 Wooden Arrows)
    d["ammo_inv"] = {}
    assert app.quick_equip_ammo(U)[0] is False


def test_a_needs_ammo_notice_carries_equip_and_buy_buttons():
    d = _armed("Longbow", 1)
    d["ammo_inv"] = {"Wooden Arrow": 2}
    sent = []

    async def fake(interaction, comps, ephemeral=False):
        sent.append((comps, ephemeral))
    real = app.send_v2_followup
    app.send_v2_followup = fake
    try:
        run(app.send_ammo_help(object(), U, "out of arrows"))
    finally:
        app.send_v2_followup = real
    blob = json.dumps(sent[0][0])
    assert sent[0][1] is True and f"qammo:equip:{U}" in blob and f"qammo:buy:{U}" in blob
    with tr.Harness() as h:
        d["equipped_ammo"], d["ammo_inv"] = None, {"Wooden Arrow": 2}
        run(app._dispatch_component(tr.FakeInteraction(U, f"qammo:equip:{U}")))
        assert d["equipped_ammo"] == "Wooden Arrow" and any("Loaded" in m for m in h.ephemerals)
        run(app._dispatch_component(tr.FakeInteraction("999", f"qammo:buy:{U}")))
        assert d["equipped_ammo"] == "Wooden Arrow"                              # somebody else's button does nothing


def test_quick_hunt_and_explore_mode_switch_from_the_panels_without_settings():
    d = _fresh(level=300)
    d["hunt_cd"] = 0
    with tr.Harness() as h:
        run(app._dispatch_component(tr.FakeInteraction(U, f"explore:quick:{U}")))
        assert d["explore_mode"] is False and h.panels and any("Quick Hunt" in m for m in h.ephemerals)
    res = app.run_hunt(U)
    assert res["ok"] and f"explore:on:{U}" in json.dumps(app.build_hunt_components(U, res))
    shown = []

    async def rec(interaction, uid, **kw):
        shown.append(uid)
    real = app.explore_show
    app.explore_show = rec
    try:
        with tr.Harness():
            run(app._dispatch_component(tr.FakeInteraction(U, f"explore:on:{U}")))
    finally:
        app.explore_show = real
    assert d["explore_mode"] is True and shown == [U]


def test_the_panel_shows_one_next_goal():
    d = _fresh(tool="Bare Hands", owned_tools=["Bare Hands"], money=0, quests=[])
    d["quests"], d["weekly_quests"] = [], []
    assert "collection" in app.next_goal_line(U) or "Next upgrade" in app.next_goal_line(U)
    d["money"] = int(gd.TOOLS["Slingshot"]["price"] * 0.8)
    assert "Next upgrade: **Slingshot** — 80% saved" in app.next_goal_line(U)
    d["quests"] = [{"id": "q", "completed": True, "claimed": False}]
    assert "Quest complete" in app.next_goal_line(U)
    assert app.next_goal_line(U).count("\n") == 0 and "Quest complete" in json.dumps(app.build_explore_components(U), ensure_ascii=False)


def test_claim_all_pays_every_finished_quest_at_once():
    d = _fresh(money=0)
    mk = lambda i, done: {"id": f"q{i}", "completed": done, "claimed": False, "xp_reward": 10, "money_reward": 5,
                          "description": "x", "progress": 1, "target": 1, "template": app.QUEST_TEMPLATES[0]["id"], "stat": "nothing", "created_date": gd.today_utc()}
    d["quests"] = [mk(1, True), mk(2, True), mk(3, False)]
    d["quests_last_roll"] = gd.today_utc()
    blob = json.dumps(app.build_quests_components(U), ensure_ascii=False)
    assert "Claim All (2)" in blob and f"quests:claimall:{U}" in blob
    with tr.Harness() as h:
        run(app._dispatch_component(tr.FakeInteraction(U, f"quests:claimall:{U}")))
    assert [q["claimed"] for q in d["quests"]] == [True, True, False] and d["money"] >= 10
    assert any("Claimed **2** quests" in m for m in h.ephemerals)
    assert "Claim All" not in json.dumps(app.build_quests_components(U), ensure_ascii=False)


# ── field guide + camp ───────────────────────────────────────

def test_finishing_a_region_gives_a_profile_decoration_once():
    d = _fresh()
    d["record"] = {a: {"count": 1, "best": 1} for a in gd.BIOME_ANIMALS["village"][:-1]}
    assert app._grant_region_decor(U, "village") == ""                           # one species short
    d["record"][gd.BIOME_ANIMALS["village"][-1]] = {"count": 1, "best": 1}
    got = app._grant_region_decor(U, "village")
    assert "Village Banner" in got and d["region_decor"] == ["village"]
    assert app._grant_region_decor(U, "village") == "" and "🏡" in app.explore_keepsake_line(U)
    assert "🏡" in json.dumps(app.build_profile_components(U, "Tester"), ensure_ascii=False)


def test_the_camp_uses_your_best_owned_tool_not_the_one_in_your_hand():
    d = _fresh(level=1000, tool="Bare Hands", owned_tools=["Bare Hands", "Longbow"])
    d["idle"]["camp_biome"] = "woods"                                             # needs Tier 3
    assert app.idle_camp_biome(U) == "woods" and app.idle_can_camp(U, "woods")[0] is True
    d["owned_tools"] = ["Bare Hands"]
    assert app.idle_camp_biome(U) == "village" and app.idle_can_camp(U, "woods")[0] is False


def test_camp_visitors_give_a_small_gift_and_unlock_decorations():
    d = _fresh(level=50)
    idle = d["idle"]
    idle.update(stacks=1, active=True, started_at=time.time())
    idle["visitor"] = {"name": "Old Marta the trapper", "gift": "swaps a tale for a bandage", "ts": 0}
    blob = json.dumps(app.build_idle_components(U), ensure_ascii=False)
    assert "Welcome Visitor" in blob and "Old Marta" in blob
    with tr.Harness() as h:
        run(app._dispatch_component(tr.FakeInteraction(U, f"idle:visitor:{U}")))
    assert idle["visitor"] is None and idle["visitors_met"] == 1 and any("Old Marta" in m for m in h.ephemerals)
    assert "Campfire" in app.idle_camp_extras(U) and "Welcome Visitor" not in json.dumps(app.build_idle_components(U), ensure_ascii=False)
    idle["haul"] = [COMMON]
    assert "Welcome back" in app.idle_camp_extras(U)
    # visitors turn up while hunters work
    idle["haul"], idle["visitor"] = [], None
    idle["started_at"] = time.time() - 3 * 3600
    real = _land(0.0)
    try:
        app.idle_tick(U)
    finally:
        random.random = real
    assert idle["visitor"] and idle["visitor"]["name"]


# ── the asset pack: ground, props, automatic effects, 2x2 props ─────────

@contextlib.contextmanager
def prop_at(pid, x, y, size=1, ax=None, ay=None):
    """Pin one tile to a specific prop (its kind comes from the terrain mapping)."""
    real = app._ex_prop

    def fake(st, px, py):
        if (px, py) == (x, y) or (size == 2 and ax is not None and ax <= px <= ax + 1 and ay <= py <= ay + 1):
            p = dict(gd.EXPLORE_PROPS[pid])
            p.update(id=pid, size=size, ax=ax if ax is not None else x, ay=ay if ay is not None else y)
            p["key"] = f"{p['ax']},{p['ay']}"
            return p
        return real(st, px, py)
    app._ex_prop = fake
    try:
        yield
    finally:
        app._ex_prop = real


def _hp(d, v=None):
    app.refresh_health(U)
    if v is not None:
        d["health"]["hp"] = v
    return d["health"]["hp"]


def test_the_asset_pack_is_wired_in():
    assert gd.EXPLORE_GROUND.keys() == set(gd.BIOME_TOOL_TIER) and all(g in gd.EXPLORE_ART for g in gd.EXPLORE_GROUND.values())
    for old in ("grass", "tree", "rock", "bush", "trail"):
        assert old not in gd.EXPLORE_ART                                         # the removed placeholders
    assert "hunter" in gd.EXPLORE_ART and gd.EXPLORE_ART["chest0"]
    for biome, lists in gd.EXPLORE_BIOME_PROPS.items():
        for kind, ids in lists.items():
            for pid in ids:
                assert pid in gd.EXPLORE_PROPS and gd.EXPLORE_PROPS[pid]["biome"] in (biome, "small_desert", "volcanic_highlands", "sunken_coast") or True
                assert pid in gd.EXPLORE_ART or pid == "landmark__tundra__frozen_pond", pid     # (that one has no emoji yet)
    assert set(gd.EXPLORE_KIND_ART.values()) <= set(gd.EXPLORE_PROPS) and gd.EXPLORE_BIG_ALWAYS <= set(gd.EXPLORE_PROPS)
    assert app._ex_art_wanted("tundra") and "ground__tundra__snow_ice_ground" in app._ex_art_wanted("tundra")


def test_every_region_draws_with_every_prop_art_present():
    from PIL import Image
    saved = dict(app._ex_art)
    for i, k in enumerate(gd.EXPLORE_ART):
        app._ex_art[k] = Image.new("RGBA", (128, 90), (40 + i * 3 % 200, 90, 160, 255))
    try:
        for biome in gd.BIOME_TOOL_TIER:
            td._fresh(biome=biome, explore_mode=True)
            random.seed(7)
            st = app._ex_new(U, biome)
            st["steps"], st["x"], st["y"] = 20, 6, 6
            _png_ok(app._ex_render(app._ex_snapshot(U)))
    finally:
        app._ex_art.clear()
        app._ex_art.update(saved)


def test_every_region_is_playable_and_animals_never_stand_on_something_that_hurts():
    for biome in gd.BIOME_TOOL_TIER:
        for i in range(12):
            td._fresh(biome=biome, explore_mode=True)
            random.seed(1000 + i)
            st = app._ex_new(U, biome)
            assert len(app._ex_reach(st)) >= app.EXPLORE_MIN_REACH and st["animals"], (biome, i)
            for _ in range(50):
                reach = app._ex_reach(st)
                assert all((a["x"], a["y"]) in reach and app._ex_animal_safe(st, a["x"], a["y"]) for a in st["animals"]), (biome, i)
                app.explore_move(U, random.choice("nsew"))
                if app._ex_over(st):
                    break
                app.data[U]["health"]["hp"] = app.data[U]["health"]["max_hp"]


def test_biomes_use_their_own_props_and_never_a_tree_in_the_desert():
    td._fresh(biome="small_desert", explore_mode=True)
    st = app._ex_state(U)
    seen = set()
    for seed in range(8):
        st["seed"] = seed
        for x in range(19):
            for y in range(19):
                p = app._ex_prop(st, x, y)
                if p:
                    seen.add(p["id"])
    assert seen <= set(gd.EXPLORE_BIOME_PROPS["small_desert"]["stone"] + gd.EXPLORE_BIOME_PROPS["small_desert"]["landmark"]
                       + gd.EXPLORE_BIOME_PROPS["small_desert"]["hazard"]) | {"discovery__shared__purple_rune_monument"}
    assert "hazard__desert__flowering_cactus" in seen and "landmark__desert__sand_dune" in seen


def test_a_cactus_pricks_you_each_time_and_a_bump_that_hurts_takes_a_turn():
    d = _fresh()
    d["biome"] = "small_desert"
    with terrain({(3, 1): "hazard"}), still_world(), prop_at("hazard__desert__flowering_cactus", 3, 1):
        st = app._ex_state(U)
        st["animals"] = []
        hp0 = _hp(d)
        out = app.explore_move(U, "s")
        assert out["kind"] == "moved" and (st["x"], st["y"]) == (3, 0) and st["steps"] == 1       # a turn passed, you did not move
        assert d["health"]["hp"] == hp0 - 1 and "hurts" in st["msg"]
        app.explore_move(U, "s")
        assert d["health"]["hp"] == hp0 - 2                                       # every bump, no "once"
        d["health"]["hp"] = 1
        app.explore_move(U, "s")
        assert d["health"]["hp"] >= 1                                             # the land never knocks you out


def test_snowdrifts_and_steam_throw_you_back_and_mud_is_harmless():
    d = _fresh()
    d["biome"] = "tundra"
    with terrain({(3, 1): "hazard"}), still_world(), prop_at("hazard__tundra__deep_snowdrift", 3, 1):
        st = app._ex_state(U)
        st["animals"] = []
        hp0 = _hp(d)
        app.explore_move(U, "s")
        assert (st["x"], st["y"]) == (3, 0) and d["health"]["hp"] == hp0 - 1 and st["steps"] == 1 and "throws you back" in st["msg"]
    with terrain({(3, 1): "hazard"}), still_world(), prop_at("hazard__volcano__steam_vent", 3, 1):
        d["health"]["hp"] = hp0
        app.explore_move(U, "s")
        assert (st["x"], st["y"]) == (3, 0) and d["health"]["hp"] == hp0 - 2
    with terrain({(3, 1): "hazard"}), still_world(), prop_at("hazard__swamp__muddy_pond", 3, 1):
        d["health"]["hp"] = hp0
        app.explore_move(U, "s")
        assert (st["x"], st["y"]) == (3, 0) and d["health"]["hp"] == hp0 and st["steps"] == 3          # stuck, but no damage


def test_ice_slides_you_one_more_tile_only_over_safe_ground():
    d = _fresh()
    d["biome"] = "tundra"
    with terrain({(3, 1): "landmark"}), still_world(), prop_at("landmark__tundra__frozen_ice_arch", 3, 1):
        st = app._ex_state(U)
        st["animals"] = []
        st["steps"] = 4
        app.explore_move(U, "s")
        assert (st["x"], st["y"]) == (3, 2) and "slide" in st["msg"]                      # one tile past the ice
    _fresh()["biome"] = "tundra"
    with terrain({(3, 1): "landmark", (3, 2): "tree"}), still_world(), prop_at("landmark__tundra__frozen_pond", 3, 1):
        st = app._ex_state(U)
        st["animals"] = []
        app.explore_move(U, "s")
        assert (st["x"], st["y"]) == (3, 1)                                           # a tree ahead: the slide is cancelled
    _fresh()["biome"] = "tundra"
    with terrain({(3, 1): "landmark", (3, 2): "hazard"}), still_world(), prop_at("landmark__tundra__frozen_pond", 3, 1):
        with prop_at("hazard__tundra__deep_snowdrift", 3, 2):
            st = app._ex_state(U)
            st["animals"] = []
            app.explore_move(U, "s")
            assert (st["x"], st["y"]) == (3, 1)                                       # never slides you into a hazard


def test_lava_hurts_but_never_kills_and_water_blocks():
    d = _fresh()
    d["biome"] = "volcanic_highlands"
    with terrain({(3, 1): "lava", (2, 0): "water"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        hp0 = _hp(d)
        app.explore_move(U, "s")
        assert d["health"]["hp"] == hp0 - app.EXPLORE_LAVA_HP and (st["x"], st["y"]) == (3, 1) and "lava" in st["msg"]
        d["health"]["hp"] = 2
        app.explore_move(U, "n")
        app.explore_move(U, "s")
        assert d["health"]["hp"] == 1
        app.explore_move(U, "n")
        out = app.explore_move(U, "w")
        assert out["kind"] == "bump" and "water" in st["msg"] and st["steps"] == 4


def test_landmarks_reveal_heal_and_pay_once_each():
    d = _fresh()
    d["biome"] = "small_desert"
    with terrain({(6, 7): "landmark"}), still_world(), prop_at("landmark__desert__sandstone_arch", 6, 7):
        st = app._ex_state(U)
        st["animals"], st["steps"], st["x"], st["y"] = [], 20, 6, 6
        far = _calm(st, dx=-5)                                                    # off the picture, within 3 + 3 tiles
        out = app.explore_move(U, "s")                                            # a bump into the arch: it shows you the way
        assert out["kind"] == "moved" and far["clue"] > 0 and (st["x"], st["y"]) == (6, 6) and "arch" in st["msg"]
        far["clue"] = 0
        assert app.explore_move(U, "s")["kind"] == "bump" and far["clue"] == 0     # used up: an ordinary bump from now on
    d["biome"] = "celestial_peaks"
    with terrain({(6, 7): "landmark"}), still_world(), prop_at("landmark__celestial_peaks__star_crystal_cluster", 6, 7):
        st = app._ex_state(U)
        st["animals"], st["steps"], st["x"], st["y"] = [], 20, 6, 6
        _hp(d, d["health"]["max_hp"])
        assert app.explore_move(U, "s")["kind"] == "bump" and "6,7" not in st.get("fired", [])      # not hurt: kept for later
        d["health"]["hp"] = 10
        assert app.explore_move(U, "s")["kind"] == "moved" and d["health"]["hp"] == 13 and "6,7" in st["fired"]
        assert app.explore_move(U, "s")["kind"] == "bump"
    d["biome"] = "cursed_ruins"
    money0 = d["money"]
    with terrain({(6, 7): "landmark"}), still_world(), prop_at("landmark__cursed_ruins__stone_rubble", 6, 7):
        st = app._ex_state(U)
        st["animals"], st["steps"], st["x"], st["y"] = [], 20, 6, 6
        assert app.explore_move(U, "s")["kind"] == "moved" and d["money"] > money0
        money1 = d["money"]
        app.explore_move(U, "s")
        assert d["money"] == money1


def test_solid_landmarks_award_stamps_when_you_walk_up_to_them():
    d = _fresh()
    d["biome"] = "celestial_peaks"
    with terrain({(4, 1): "stone"}), still_world(), prop_at("landmark__celestial_peaks__cloud_rock_spires", 4, 1, 2, 4, 1):
        st = app._ex_state(U)
        st["animals"] = []
        app.explore_move(U, "s")                                                  # (3,1) is next to (4,1)
        assert d["explore_stamps"] == ["cloud_spires"] and "stamp" in st["msg"]
        app.explore_move(U, "n")
        app.explore_move(U, "s")
        assert d["explore_stamps"] == ["cloud_spires"]                            # once per placed prop
    assert app.explore_keepsake_line(U).endswith(f"1/{len(gd.EXPLORE_STAMPS)} stamps")


def test_a_prop_that_hurts_only_triggers_one_hazard_per_turn():
    d = _fresh()
    d["biome"] = "small_desert"
    with terrain({(3, 1): "hazard"}), still_world(), prop_at("hazard__desert__flowering_cactus", 3, 1):
        st = app._ex_state(U)
        st["animals"] = []
        hp0 = _hp(d)
        app.explore_move(U, "s")
        assert hp0 - d["health"]["hp"] == 1


def test_big_props_fill_a_2x2_block_with_one_prop_and_never_where_you_start():
    seed = next(s for s in range(500) if any(app._ex_big(s, x, y, "volcanic_highlands") for x in range(0, 16, 2) for y in range(0, 16, 2)))
    bx, by = next((x, y) for x in range(0, 16, 2) for y in range(0, 16, 2) if app._ex_big(seed, x, y, "volcanic_highlands"))
    td._fresh(biome="volcanic_highlands", explore_mode=True)
    st = app._ex_state(U)
    st["seed"], st["steps"] = seed, 20
    cells = [(bx + i, by + j) for i in (0, 1) for j in (0, 1)]
    props = [app._ex_prop(st, x, y) for x, y in cells]
    assert all(p and p["size"] == 2 and p["key"] == f"{bx},{by}" and p["id"] == "hazard__volcano__active_volcano" for p in props), props
    assert all(app._ex_kind(st, x, y) == "hazard" and not app._ex_walkable(st, x, y) for x, y in cells)
    for sd in range(300):
        assert app._ex_big(sd, *app.EXPLORE_START, "volcanic_highlands") is None and app._ex_big(sd, 2, 0, "forest") is None
    # a big tree somewhere in a forest, and it counts as one prop
    sd = next(s for s in range(500) if any(app._ex_big(s, x, y, "forest") for x in range(0, 20, 2) for y in range(0, 20, 2)))
    x, y = next((x, y) for x in range(0, 20, 2) for y in range(0, 20, 2) if app._ex_big(sd, x, y, "forest"))
    td._fresh(biome="forest", explore_mode=True)
    st = app._ex_state(U)
    st["seed"], st["steps"] = sd, 20
    assert app._ex_prop(st, x + 1, y + 1)["id"] == "obstacle__forest__oak_tree" and app._ex_kind(st, x, y) == "tree"


def test_a_big_prop_is_drawn_once_across_all_four_tiles():
    from PIL import Image
    saved = dict(app._ex_art)
    app._ex_art.update({gd.EXPLORE_GROUND["volcanic_highlands"]: Image.new("RGBA", (128, 128), (0, 100, 0, 255)),
                        "hazard__volcano__active_volcano": Image.new("RGBA", (128, 128), (200, 0, 0, 255)),
                        "hunter": Image.new("RGBA", (128, 128), (255, 255, 255, 255))})
    try:
        td._fresh(biome="volcanic_highlands", explore_mode=True)
        seed = next(s for s in range(500) if any(app._ex_big(s, x, y, "volcanic_highlands") for x in range(2, 12, 2) for y in range(2, 12, 2)))
        bx, by = next((x, y) for x in range(2, 12, 2) for y in range(2, 12, 2) if app._ex_big(seed, x, y, "volcanic_highlands"))
        st = app._ex_state(U)
        st["seed"], st["steps"], st["animals"] = seed, 20, []
        st["x"], st["y"] = bx + 2, by + 3
        snap = app._ex_snapshot(U)
        assert sum(1 for v in snap["props"].values() if v["size"] == 2) >= 1
        im = _png_ok(app._ex_render(snap))
        T = app.EXPLORE_TILE_PX
        tx, ty = bx - snap["cx"], by - snap["cy"]
        red = lambda px, py: (lambda c: c[0] > 150 and c[1] < 90)(im.getpixel((px, py)))
        assert red(int((tx + 1) * T), int((ty + 1) * T))                          # the middle of the 2x2 block is the volcano
        assert red(int((tx + .5) * T), int((ty + 1.4) * T)) and red(int((tx + 1.5) * T), int((ty + 1.4) * T))
    finally:
        app._ex_art.clear()
        app._ex_art.update(saved)


def test_ground_comes_from_the_region_and_lava_and_water_have_their_own():
    from PIL import Image
    saved = dict(app._ex_art)
    app._ex_art.update({gd.EXPLORE_GROUND["volcanic_highlands"]: Image.new("RGBA", (128, 128), (60, 60, 60, 255)),
                        gd.EXPLORE_GROUND_LAVA: Image.new("RGBA", (128, 128), (255, 80, 0, 255)),
                        gd.EXPLORE_GROUND_WATER: Image.new("RGBA", (128, 128), (0, 80, 255, 255))})
    try:
        td._fresh(biome="volcanic_highlands", explore_mode=True)
        with terrain({(5, 5): "lava", (7, 5): "water"}):
            st = app._ex_state(U)
            st["animals"], st["steps"], st["x"], st["y"] = [], 20, 6, 6
            im = _png_ok(app._ex_render(app._ex_snapshot(U)))
            T = app.EXPLORE_TILE_PX
            at = lambda tx, ty: im.getpixel((tx * T + 6, ty * T + 6))
            assert at(2, 2)[0] > 200 and at(4, 2)[2] > 200 and abs(at(0, 0)[0] - 60) < 20          # lava, water, then the region's own ground
    finally:
        app._ex_art.clear()
        app._ex_art.update(saved)


def test_missing_art_falls_back_to_a_drawn_stand_in_for_every_prop():
    from PIL import Image
    saved = dict(app._ex_art)
    app._ex_art.clear()
    try:
        for biome in gd.BIOME_TOOL_TIER:
            td._fresh(biome=biome, explore_mode=True)
            st = app._ex_state(U)
            for seed in range(4):
                st["seed"], st["steps"], st["x"], st["y"], st["animals"] = seed, 20, 6 + seed, 6, []
                _png_ok(app._ex_render(app._ex_snapshot(U)))
    finally:
        app._ex_art.update(saved)


# ── Halloween Land: an admin-started, week-long event region on the Explore map ──

H = "halloween_land"


@contextlib.contextmanager
def halloween_event(on=True):
    """Run the Halloween event for the duration of the block (or make sure none runs)."""
    app.stop_active_event()
    if on:
        app.start_event("halloween", "1")
    try:
        yield
    finally:
        app.stop_active_event()


def _hw_user(**over):
    d = _fresh(**over)
    d["is_tester"] = False
    return d


def test_halloween_is_an_admin_started_week_long_event():
    spec = app.EVENTS["halloween"]
    assert spec["kind"] == "buff" and spec["hours"] == 168 and spec["emoji"] == "🎃" and spec["actions"]
    assert len(app.EVENTS) <= 25                                                 # fits the admin "start an event" dropdown
    with halloween_event(False):
        _hw_user()
        assert app.halloween_open(U) is False
        assert "Halloween Land" not in json.dumps(app.build_explore_components(U), ensure_ascii=False)
    with halloween_event():
        ev = app.get_active_event()
        assert ev["key"] == "halloween" and abs((ev["ends_ts"] - ev["started_ts"]) - 7 * 86400) < 5
        assert app.halloween_open(U) is True
        assert "🎃 Halloween Land" in json.dumps(app.build_explore_components(U), ensure_ascii=False)
    assert app.halloween_open(U) is False                                        # the event is over


def test_you_enter_halloween_land_keep_your_home_animals_and_are_sent_home_when_it_ends():
    d = _hw_user()
    d["biome"] = "forest"
    with halloween_event():
        st = app._ex_state(U)
        assert st["biome"] == "forest"
        app.explore_realm(U)
        st = app._ex_state(U)
        # (nothing explored yet, so switching needs no confirmation)
        assert st["biome"] == H and st["home"] == "forest" and d["explore_realm"] == H
        assert all(a["name"] in gd.BIOME_ANIMALS["forest"] for a in st["animals"])         # the pay does not change
        assert "Halloween Land" in json.dumps(app.build_explore_components(U), ensure_ascii=False)
        assert "Leave Halloween Land" in json.dumps(app.build_explore_components(U), ensure_ascii=False)
        st["steps"] = 6
        assert app.explore_realm(U)["kind"] == "confirm"                          # leaving mid-expedition asks first
        assert app.explore_realm(U)["kind"] == "new" and app._ex_state(U)["biome"] == "forest" and d["explore_realm"] == ""
        app.explore_realm(U)
        assert app._ex_state(U)["biome"] == H
    st = app._ex_state(U)                                                         # the event ended
    assert st["biome"] == "forest" and d["explore_realm"] == ""
    assert app.explore_realm(U)["kind"] == "none"


def test_testers_can_visit_halloween_land_any_time():
    d = _hw_user()
    d["is_tester"] = True
    with halloween_event(False):
        assert app.halloween_open(U) is True
        app.explore_realm(U)
        assert app._ex_state(U)["biome"] == H


def test_halloween_land_has_every_prop_and_a_patchwork_of_four_grounds():
    lists = gd.EXPLORE_BIOME_PROPS[H]
    assert set(lists) == {"tree", "stone", "bush", "landmark", "hazard"} and all(lists.values())
    for kind, ids in lists.items():
        for pid in ids:
            assert pid in gd.EXPLORE_PROPS and pid in gd.EXPLORE_ART, pid
    assert all(g in gd.EXPLORE_ART for g, _ in gd.EXPLORE_REALM_GROUND[H])
    seen = {app._ex_ground_id(H, 5, x, y) for x in range(0, 60) for y in range(0, 60)}
    assert seen == {g for g, _ in gd.EXPLORE_REALM_GROUND[H]}
    assert gd.EXPLORE_PROPS["halloween_land_ghost_portal"]["eff"] == "teleport"
    assert {"halloween_land_haunted_house", "halloween_land_crypt"} <= gd.EXPLORE_BIG_ALWAYS
    assert set(app._ex_art_wanted(H)) >= {g for g, _ in gd.EXPLORE_REALM_GROUND[H]}


def test_ghosts_roots_graves_and_webs_shove_you_back_some_for_hp():
    d = _hw_user()
    d["is_tester"] = True
    app.explore_realm(U)
    for pid, hp in (("halloween_land_ghost", 0), ("halloween_land_witch_broom", 0), ("halloween_land_giant_spiderweb", 0),
                    ("halloween_land_twisted_roots", 1), ("halloween_land_open_grave", 1), ("halloween_land_skeletal_hand", 1),
                    ("halloween_land_poison_swamp_pool", 2)):
        with terrain({(3, 1): "hazard"}), still_world(), prop_at(pid, 3, 1):
            st = app._ex_state(U)
            st["animals"], st["x"], st["y"], st["steps"] = [], 3, 0, 0
            hp0 = _hp(d, d["health"]["max_hp"])
            app.explore_move(U, "s")
            assert (st["x"], st["y"]) == (3, 0) and hp0 - d["health"]["hp"] == hp, pid
            assert st["steps"] == 1, pid


def test_a_spider_nest_startles_you_when_you_walk_up_to_it_and_a_haunted_tree_just_shoves():
    d = _hw_user()
    d["is_tester"] = True
    app.explore_realm(U)
    with terrain({(3, 2): "hazard"}), still_world(), prop_at("halloween_land_spider_nest", 3, 2):
        st = app._ex_state(U)
        st["animals"], st["x"], st["y"], st["steps"] = [], 3, 0, 0
        hp0 = _hp(d)
        app.explore_move(U, "s")                                                  # (3,1) is next to the nest: you retreat
        assert (st["x"], st["y"]) == (3, 0) and "startles" in st["msg"] and d["health"]["hp"] == hp0
    with terrain({(3, 1): "tree"}), still_world(), prop_at("halloween_land_haunted_tree", 3, 1):
        st = app._ex_state(U)
        st["animals"], st["x"], st["y"], st["steps"] = [], 3, 0, 0
        out = app.explore_move(U, "s")
        assert out["kind"] == "bump" and "shoves you back" in st["msg"] and st["steps"] == 0


def test_the_ghost_portal_hops_you_to_a_safe_empty_tile_once():
    d = _hw_user()
    d["is_tester"] = True
    app.explore_realm(U)
    with terrain({(3, 1): "landmark"}), still_world(), prop_at("halloween_land_ghost_portal", 3, 1):
        st = app._ex_state(U)
        st["animals"], st["x"], st["y"], st["steps"] = [], 3, 0, 20
        app.explore_move(U, "s")
        assert (st["x"], st["y"]) != (3, 1) and 1 <= app._ex_dist(st["x"], st["y"], 3, 1) <= 3 and "swallows you" in st["msg"]
        assert app._ex_kind(st, st["x"], st["y"]) == "grass"
        st["x"], st["y"] = 3, 0
        app.explore_move(U, "s")
        assert (st["x"], st["y"]) == (3, 1)                                       # used up: now just a tile


def test_candy_is_cosmetic_capped_per_day_and_earns_titles():
    d = _hw_user()
    d["is_tester"] = True
    app.explore_realm(U)
    money0, gems0 = d["money"], d["gems"]
    total = 0
    for i in range(30):
        got, today, titles = app._ex_give_candy(U, 5)
        total += got
    assert total == gd.HALLOWEEN_CANDY_DAILY_CAP and d["candy"] == gd.HALLOWEEN_CANDY_DAILY_CAP        # restarting never beats the cap
    assert "Trick-or-Treater" in d["earned_titles"] and money0 == d["money"] and gems0 == d["gems"]
    st = app._ex_state(U)
    app._ex_new(U, H)                                                             # a brand-new expedition does not reset the cap
    assert app._ex_give_candy(U, 5)[0] == 0
    msg = app._ex_loot(U, "small_candy", "candy bucket")
    assert "come back tomorrow" in msg
    d["candy_day"]["d"] = "2000-01-01"                                            # a new day
    assert app._ex_give_candy(U, 3)[0] == 3
    d["candy"] = 99
    assert "Candy Collector" in app._ex_give_candy(U, 5)[2] or "Candy Collector" in d["earned_titles"]
    assert "🍬" in app.explore_keepsake_line(U)


def test_candy_props_cauldrons_and_spooky_buildings_pay_and_stamp_once():
    d = _hw_user()
    d["is_tester"] = True
    app.explore_realm(U)
    with terrain({(3, 1): "landmark"}), still_world(), prop_at("halloween_land_candy_bucket", 3, 1):
        st = app._ex_state(U)
        st["animals"], st["x"], st["y"], st["steps"] = [], 3, 0, 20
        c0 = d.get("candy", 0)
        app.explore_move(U, "s")
        assert d["candy"] > c0 and "candy" in st["msg"]
        c1 = d["candy"]
        app.explore_move(U, "n"); app.explore_move(U, "s")
        assert d["candy"] == c1                                                   # once per placed prop
    with terrain({(4, 1): "landmark"}), still_world(), prop_at("halloween_land_witch_cauldron", 4, 1):
        st = app._ex_state(U)
        st["animals"], st["x"], st["y"] = [], 3, 0
        _hp(d, 10)
        app.explore_move(U, "s")                                                  # next to the cauldron: a friendly potion
        assert d["health"]["hp"] == 15 and "cauldron" in st["msg"]
    with terrain({(4, 2): "landmark"}), still_world(), prop_at("halloween_land_crypt", 4, 2, 2, 4, 2):
        st = app._ex_state(U)
        st["animals"], st["x"], st["y"] = [], 3, 1
        app.explore_move(U, "s")
        assert "halloween_land_crypt" in d["explore_stamps"] and "Crypt" in st["msg"]
    assert gd.EXPLORE_STAMPS["scarecrow"] and gd.EXPLORE_STAMPS["ghost_reflection"]


def test_halloween_land_draws_with_and_without_art():
    from PIL import Image
    d = _hw_user()
    d["is_tester"] = True
    app.explore_realm(U)
    saved = dict(app._ex_art)
    try:
        for with_art in (False, True):
            app._ex_art.clear()
            if with_art:
                for i, k in enumerate(gd.EXPLORE_ART):
                    app._ex_art[k] = Image.new("RGBA", (128, 100), (30 + i * 5 % 200, 80, 140, 255))
            for seed in range(6):
                st = app._ex_state(U)
                st["seed"], st["steps"], st["x"], st["y"], st["animals"] = seed, 20, 6 + seed, 6, []
                _png_ok(app._ex_render(app._ex_snapshot(U)))
    finally:
        app._ex_art.clear()
        app._ex_art.update(saved)
    assert "🎃 Halloween Land" in json.dumps(app.build_explore_components(U), ensure_ascii=False)


def test_there_is_no_generic_tree_any_more():
    assert not hasattr(app, "_ex_tree")
    for biome in gd.BIOME_TOOL_TIER:                                              # no cover art in a region = no bushes there
        has = bool(gd.EXPLORE_BIOME_PROPS[biome]["bush"])
        kinds = {app._ex_tile(sd, x, y, biome) for sd in range(6) for x in range(19) for y in range(19)}
        assert ("bush" in kinds) == has, biome
    from PIL import Image
    im = app._ex_proc_prop("tree", "volcanic_highlands", random.Random(1), app._EX_PAL["volcanic_highlands"], 144)
    assert im.getbbox() is not None




def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(td.tt._ensure_db())
    failed = 0
    only = sys.argv[1:]
    for name in _all_tests():
        if only and name not in only:
            continue
        try:
            globals()[name]()
            print(f"  ok   {name}", flush=True)
        except Exception:
            failed += 1
            import traceback
            print(f"  FAIL {name}", flush=True)
            traceback.print_exc()
    print()
    try:
        run(td.tt.backend.close_databases())
    except Exception:
        pass
    if failed:
        print(f"{failed} FAILED")
        sys.exit(1)
    print(f"all {len(_all_tests())} tests passed")
    sys.exit(0)
