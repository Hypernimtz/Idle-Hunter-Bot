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
    app._ex_tile = lambda seed, x, y: "grass" if (x, y) == app.EXPLORE_START else mapping.get((x, y), default)
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
    _fresh()
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
    def walled(seed, x, y):
        if (x, y) == app.EXPLORE_START:
            return "grass"
        if calls["n"] < 3 and seed % 2 == 0:
            return "tree"
        return real(seed, x, y)
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
    app._ex_art.update(grass=Image.new("RGBA", (128, 128), (0, 200, 0, 255)),
                       hunter=Image.new("RGBA", (128, 128), (255, 255, 255, 255)))
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
    app._ex_art.update(grass=solid((0, 200, 0, 255)), tree=solid((200, 0, 0, 255)), rock=solid((0, 0, 200, 255)),
                       bush=solid((200, 200, 0, 255)), hunter=solid((255, 255, 255, 255)), trail=solid((90, 0, 90, 255)))
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
            assert near(px(4, 3), (0, 0, 200), 60)                   # the boulder to the east
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
                run(app._dispatch_component(tr.FakeInteraction(U, f"explore:new:{U}")))
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
    assert gd.TOOL_RANGE_MAX == app.EXPLORE_VIEW == 3 and set(gd.TOOL_RANGE) <= set(gd.TOOLS)
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
        assert out["kind"] == "none" and "Out of range" in st["msg"] and "reaches **1** tile" in st["msg"]
        assert d["stats"].get("lifetime_hunts", 0) == lt0 and d["hunt_cd"] == cd0          # nothing was spent
        comps = app.build_explore_components(U)[0]["components"]
        assert comps[-2]["components"][0]["label"] == "Fire" and comps[-2]["components"][0]["disabled"] is True
        assert "out of range" in json.dumps(comps)
        a["x"] -= 2                                                              # now right beside you
        assert app.explore_fire is not None and app._ex_target(st, 1) is a
        comps = app.build_explore_components(U)[0]["components"]
        assert comps[-2]["components"][0]["disabled"] is False and "target" in json.dumps(comps)


def test_the_yellow_target_is_the_one_you_pick_and_fire_hits_it():
    d = _fresh(tool="Shotgun", owned_tools=["Shotgun"])
    ammo = gd.get_ammo_for_tool("Shotgun")[0]
    d["ammo_inv"], d["equipped_ammo"] = {ammo: 50}, ammo
    other = gd.BIOME_ANIMALS["village"][1]
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        near = _calm(st, name=COMMON, dx=1)
        far = _calm(st, name=other, dx=2)
        rng = gd.tool_range("Shotgun")
        assert app._ex_target(st, rng) is near                                   # nearest by default
        assert [a["target"] for a in sorted(app._ex_snapshot(U)["animals"], key=lambda a: a["tx"])] == [True, False]
        assert app.explore_target(U)["kind"] == "target" and app._ex_target(st, rng) is far
        assert [a["target"] for a in sorted(app._ex_snapshot(U)["animals"], key=lambda a: a["tx"])] == [False, True]
        assert app.explore_target(U)["kind"] == "target" and app._ex_target(st, rng) is near       # and back again
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
    app._ex_art.update(grass=Image.new("RGBA", (128, 128), (0, 120, 0, 255)), hunter=Image.new("RGBA", (128, 128), (255, 255, 255, 255)))
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
    app._ex_art.update(grass=art)
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
    assert "attachment://range.png" in blob and "Range 2 tiles" in blob and "Shotgun" in blob
    assert "Yellow circle" in blob and "yellow boxes" in blob and "Bare Hands" in blob and "Hit chance" in blob
    assert "attachment://" not in json.dumps(app.build_explore_info_components(U, image=False))
    im = _png_ok(app._ex_range_png(2), (448, 448))
    lit, dim, mid = im.getpixel((5 * 64 + 6, 3 * 64 + 6)), im.getpixel((6 * 64 + 6, 3 * 64 + 6)), im.getpixel((3 * 64 + 6, 3 * 64 + 6))
    assert lit[0] > dim[0] + 40 and mid[0] > dim[0] + 40                         # the reach is lit, outside it is dimmed
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
    assert "Range 3 tiles" in json.dumps(body["components"], ensure_ascii=False)


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
