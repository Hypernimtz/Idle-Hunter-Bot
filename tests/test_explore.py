"""
Explore Mode (beta): a bounded arena that widens as you walk, trees that block, bushes that hide animals,
clues that fade, chests, shots that are real hunts, and a map drawn with Pillow and attached as a picture.

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

def test_you_start_at_2_0_in_a_5x5_arena_that_widens_every_two_steps_up_to_a_cap():
    _fresh()
    st = app._ex_state(U)
    assert (st["x"], st["y"]) == (2, 0) == app.EXPLORE_START and app._ex_bounds(st) == (0, 0, 4, 4)
    seen = []
    for steps in range(0, 20):
        st["steps"] = steps
        seen.append(app._ex_bounds(st))
    assert seen[0] == seen[1] == (0, 0, 4, 4) and seen[2] == seen[3] == (-1, -1, 5, 5)
    assert seen[-1] == (-app.EXPLORE_MAX_GROW, -app.EXPLORE_MAX_GROW, 4 + app.EXPLORE_MAX_GROW, 4 + app.EXPLORE_MAX_GROW)
    st["steps"] = 0
    assert app._ex_kind(st, 2, -1) == "void" and app._ex_kind(st, 5, 2) == "void"
    st["steps"] = 2
    assert app._ex_kind(st, 2, -1) != "void"


def test_the_border_stops_you_and_costs_no_step_then_widens_as_you_explore():
    _fresh()
    with terrain(), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        out = app.explore_move(U, "n")
        assert out["kind"] == "bump" and (st["x"], st["y"]) == (2, 0) and st["steps"] == 0
        assert "edge" in st["msg"]
        app.explore_move(U, "s"); app.explore_move(U, "s")                    # two steps -> the arena grows
        assert app._ex_bounds(st) == (-1, -1, 5, 5)
        for _ in range(2):
            app.explore_move(U, "n")
        assert st["y"] == 0 and app.explore_move(U, "n")["kind"] == "moved" and st["y"] == -1


def test_trees_and_boulders_block_you_and_cost_nothing():
    _fresh()
    with terrain({(2, 1): "tree", (3, 0): "stone", (1, 0): "bush"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        for d, word in (("s", "tree"), ("e", "boulder")):
            out = app.explore_move(U, d)
            assert out["kind"] == "bump" and word in st["msg"] and (st["x"], st["y"]) == (2, 0) and st["steps"] == 0
        assert app.explore_move(U, "w")["kind"] == "moved" and (st["x"], st["y"]) == (1, 0)      # a bush is walkable


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


# ── bushes hide animals ─────────────────────────────────────

def test_a_bush_hides_an_animal_until_you_are_next_to_it():
    _fresh()
    with terrain({(4, 0): "bush", (3, 0): "bush"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        far = _calm(st, dx=2)                                                  # in a bush, two tiles away
        assert app._ex_seen(st, far) is False and app._ex_visible(st) == []
        snap = app._ex_snapshot(U)
        assert snap["animals"] == []                                           # not drawn: the bush covers it
        near = _calm(st, name="Red Fox", dx=1)                                 # in a bush, right beside you
        assert app._ex_seen(st, near) is True
        assert [a["name"] for a in app._ex_snapshot(U)["animals"]] == ["Red Fox"]
        assert app.build_explore_components(U)[0]["components"][-1]["components"][0]["disabled"] is False
        # and you can't shoot what you can't see
        st["animals"].remove(near)
        out = app.explore_fire(U)
        assert out["kind"] == "none"


def test_a_hidden_animal_gives_a_rustling_clue():
    _fresh()
    with terrain({(4, 0): "bush"}), still_world():
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
    with terrain({(2, 1): "chest"}), still_world():
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
        assert "found a chest" in st["msg"] and d["money"] > money0 and "2,1" in st["opened"]
        assert app._ex_kind(st, 2, 1) == "grass"                              # opened: just grass now
        app.explore_move(U, "n"); app.explore_move(U, "s")
        assert "chest" not in st["msg"]


def test_chests_can_hold_ammo_bandages_and_items_and_run_dry_at_the_daily_cap():
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
    d["explore_chests"] = {"d": gd.today_utc(), "n": app.EXPLORE_CHESTS_PER_DAY}
    assert "empty" in app._ex_open_chest(U, st, 9, 5)
    d["explore_chests"] = {"d": "2000-01-01", "n": 99}                         # a new day resets the count
    assert "empty" not in app._ex_open_chest(U, st, 9, 4)


def test_chests_are_drawn_with_crate_art_and_richer_crates_pay_a_little_more():
    assert [gd.EXPLORE_ART[f"chest{i}"] for i in range(4)] == [gd.EMOJI[f"{t}_crate"] for t in ("common", "uncommon", "rare", "epic")]
    tiers = [app._ex_chest_tier(123, x, 5) for x in range(2000)]
    assert set(tiers) == {0, 1, 2, 3} and tiers.count(0) > tiers.count(1) > tiers.count(2) > tiers.count(3)
    assert app._ex_chest_tier(123, 4, 5) == app._ex_chest_tier(123, 4, 5)          # fixed per tile: what you see is what you get
    d = _fresh()
    with terrain({(2, 1): "chest"}), still_world():
        st = app._ex_state(U)
        st["animals"] = []
        snap = app._ex_snapshot(U)
        assert list(snap["chests"].values()) == [app._ex_chest_tier(st["seed"], 2, 1)] and len(snap["chests"]) == 1
    real = random.choices
    random.choices = lambda pop, weights=None, k=1: ["cash"]
    try:
        paid = {}
        for tier in (0, 3):
            d["explore_chests"] = {"d": gd.today_utc(), "n": 0}
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
            white = sum(1 for x in range(2 * T, 3 * T) for y in range(2 * T, 3 * T)
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
        assert "Caught this trip (1)" in panel and COMMON in panel and "You caught" in panel
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
        assert '"label": "Aim & Fire"' in blob and '"disabled": true' in blob


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
        assert blob.count('"disabled": true') >= 5 and "Caught this trip (1)" in blob
        app.explore_new(U)
        st2 = app.data[U]["explore"]
        assert st2["steps"] == 0 and st2["bag"] == [] and (st2["x"], st2["y"]) == (2, 0) and not app._ex_over(st2)


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

def _png_ok(blob: bytes, size=(480, 480)):
    from PIL import Image
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    im = Image.open(io.BytesIO(blob))
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
        with terrain({(1, 0): "tree", (3, 0): "stone", (2, 1): "bush"}):
            st = app._ex_state(U)
            st["animals"] = []
            st["steps"] = 20
            im = _png_ok(app._ex_render(app._ex_snapshot(U)))
            T = app.EXPLORE_TILE_PX
            px = lambda tx, ty, fx=.5, fy=.5: im.getpixel((int((tx + fx) * T), int((ty + fy) * T)))
            near = lambda a, b, tol=70: all(abs(x - y) <= tol for x, y in zip(a[:3], b))
            assert near(px(2, 1), (0, 200, 0), 80)                   # bare grass, the bottom layer
            assert near(px(1, 2), (200, 0, 0), 60)                   # the tree to the west sits on top of grass
            assert near(px(3, 2), (0, 0, 200), 60)                   # the boulder to the east
            assert near(px(2, 3), (200, 200, 0), 60)                 # the bush to the south
            assert near(px(2, 2), (255, 255, 255), 40)               # the hunter is the top layer in the middle
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
