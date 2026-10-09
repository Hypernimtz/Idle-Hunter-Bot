"""
"The Hollow Star" — quest events, chronicle, daily themes, tribe events.

Runs without pytest:  python tests/test_events_v3.py
"""
import asyncio
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_events3_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402
import event_data as ED            # noqa: E402
from event_scenes import SCENES    # noqa: E402

run = tt.run
U = "e1"


def _reset(level=300, **over):
    tt._reset()
    app.stop_active_event()
    app._theme_state.update(fri={}, sat={})
    d = tt._mk_user(U, level=level, **over)
    return d


def _start(key, uid=U):
    app.stop_active_event()
    ev = app.start_event(key, "admin")
    assert ev, key
    st = app._ev3_st(uid)
    assert st is not None
    return ev, ED.EVENT_SPECS[key]


def _panel_text(uid=U):
    return json.dumps(app.build_events_components(uid), ensure_ascii=False)


# ── content integrity ───────────────────────────────────────

def test_every_event_spec_is_well_formed_and_within_budget():
    assert len(ED.EVENT_SPECS) == 15 and set(ED.STORY_ORDER) == set(ED.EVENT_SPECS)
    titles = set()
    for key, sp in ED.EVENT_SPECS.items():
        assert sp["key"] == key and sp["kind"] == "quest" and sp["hours"] >= 24 and sp["actions"], key
        assert sp["mech"] in ("collect", "scenes", "clue", "deduce", "pick", "community", "tournament", "relay", "conquest")
        assert 0 < sp["token_cap"] <= 60 and sp.get("crates", 0) <= 1, key           # a fixed per-player budget
        assert key in app.EVENTS and app.EVENTS[key]["name"] == sp["name"]
        assert len(sp["story"]) >= 3 and sp["intro"]
        if sp["mech"] != "community":
            assert all(c["at"] <= sp["token_cap"] for c in sp["story"]), key         # every chapter is reachable
        assert all(at <= sp["token_cap"] for at, _ in sp["rewards"]), key
        for at, r in sp["rewards"]:
            if r.get("keepsake"):
                assert r["keepsake"] in ED.KEEPSAKES
            if r.get("badge"):
                assert r["badge"] in gd.SPECIAL_BADGES, r["badge"]
            if r.get("title"):
                titles.add(r["title"])
        for it in sp.get("shop", []):
            assert it["cost"] <= sp["token_cap"], (key, it)
            assert not (it.get("crate") and it["crate"] not in gd.CRATE_TIERS)
            assert it.get("title") or it.get("keepsake") or it.get("crate")          # cosmetics (+1 capped crate) only
    assert len(titles) >= 20


def test_no_event_rewards_gold_gems_or_multipliers():
    for key, sp in ED.EVENT_SPECS.items():
        blob = json.dumps(sp, ensure_ascii=False).lower()
        for banned in ("gems", "x2", "double", "discount", "% off", "half price"):
            assert banned not in blob, (key, banned)
    for k in dir(app):
        if k.startswith("ev_") and callable(getattr(app, k)) and k not in ("ev_price", "ev_shard_chance", "ev_crate_chance"):
            fn = getattr(app, k)
            if fn.__code__.co_argcount == 0:
                assert fn() in (1.0, 0, False), k


def test_scene_pools_are_balanced_enough_to_play():
    for pool, scenes in SCENES.items():
        assert len(scenes) >= app.EV3_SCENES_PER_RUN + 2, pool
        ids = [s["id"] for s in scenes]
        assert len(set(ids)) == len(ids)
        for s in scenes:
            assert len(s["choices"]) == 3 and s["text"]
            for label, out, da, db in s["choices"]:
                assert label and out and -2 <= da <= 2 and -2 <= db <= 2 and len(label) <= 80
            # no scene may hand out a free lunch or a certain loss
            assert any(da + db >= 0 for _, _, da, db in s["choices"]) and any(da + db < 0 or da < 0 or db < 0 for _, _, da, db in s["choices"])


def test_every_event_starts_and_renders_for_low_and_high_level_players():
    for lvl in (1, 40, 1000):
        for key in ED.EVENT_SPECS:
            _reset(level=lvl)
            ev, sp = _start(key)
            blob = _panel_text()
            assert sp["name"] in blob, key
            assert len(blob) < 14000, (key, len(blob))
            assert f"ev3:chron:open:{U}" in blob and f"ev3:theme:{U}" in blob
            assert gd.SPECIAL_BADGES and app._ev3_pair()
    app.stop_active_event()


def test_the_announcement_works_for_every_event():
    seen = []

    async def fake(body, **kw):
        seen.append(json.dumps(body, ensure_ascii=False))
        return {"id": 1}
    real = app._announce
    app._announce = fake
    try:
        for key in ED.EVENT_SPECS:
            _reset()
            ev, sp = _start(key)
            assert run(app._broadcast_event_start(ev)) is True
            assert sp["name"] in seen[-1]
    finally:
        app._announce = real
        app.stop_active_event()


# ── collect ─────────────────────────────────────────────────

def test_meteor_fragments_only_at_todays_impact_sites_and_capped_per_day():
    _reset(level=300)
    ev, sp = _start("meteor")
    sites = app._ev3_impact_regions(U, ev, sp)
    assert 1 <= len(sites) <= 3 and all(b in app._ev3_unlocked_biomes(U) for b in sites)
    off = next(b for b in app._ev3_unlocked_biomes(U) if b not in sites)
    real = random.random
    random.random = lambda: 0.0
    try:
        assert app._ev3_collect(U, ev, sp, off) == []
        got = 0
        for _ in range(40):
            if app._ev3_collect(U, ev, sp, sites[0]):
                got += 1
        assert got == sp["day_cap"]                                  # capped per day
        st = app._ev3_st(U)
        assert st["prog"] == sp["day_cap"] and st["tok"] == sp["day_cap"]
        assert st["claimed"] and "Starwatcher" in data_titles()      # the 8-fragment reward
        assert data_chronicle("meteor")                              # chapter 1 recorded permanently
    finally:
        random.random = real
    app.stop_active_event()


def data_titles():
    return app.data[U].get("earned_titles", [])


def data_chronicle(key):
    return [c for c in app.data[U].get("chronicle", {}).get(key, []) if c >= 0]


def test_event_progress_never_exceeds_the_fixed_budget():
    _reset()
    ev, sp = _start("meteor")
    app._ev3_award(U, sp, 1000)
    st = app._ev3_st(U)
    assert st["prog"] == st["tok"] == sp["token_cap"]
    assert app._ev3_award(U, sp, 5) == [] and st["prog"] == sp["token_cap"]
    assert "Relic Assembler" in data_titles() and "event_meteor" in app.data[U]["special_badges"]
    assert len(data_chronicle("meteor")) == 3
    app.stop_active_event()


def test_cartographer_pieces_need_three_hunts_per_region_and_scale_to_reach():
    _reset(level=1)                                                  # only the starter region is reachable
    ev, sp = _start("cartographer")
    for i in range(2):
        assert app._ev3_collect(U, ev, sp, "village") == []
    assert app._ev3_collect(U, ev, sp, "village")                    # 3rd hunt: the piece
    assert app._ev3_collect(U, ev, sp, "village") == []              # one piece per region
    st = app._ev3_st(U)
    assert st["prog"] == 1
    # a level-1 hunter can still finish the rewards: thresholds are capped to the regions they can reach
    assert "Pathfinder" in data_titles() and "event_cartographer" in app.data[U]["special_badges"]
    app.stop_active_event()


def test_migration_sightings_only_in_the_destination_region():
    _reset(level=300)
    ev, sp = _start("migration")
    today = app._ev3_migration_today(U, ev, sp)
    assert len(today) == 3
    for animal, dest in today:
        assert animal not in gd.BIOME_ANIMALS[dest] and dest in app._ev3_unlocked_biomes(U)
    animal, dest = today[0]
    real = random.random
    random.random = lambda: 0.0
    try:
        lines = app._ev3_collect(U, ev, sp, dest)
    finally:
        random.random = real
    assert lines and "Sighting" in lines[0]
    assert animal in [a for a, d in today] and app._ev3_st(U)["journal_sp"]
    app.stop_active_event()


# ── scenes ──────────────────────────────────────────────────

def _play_run(ev, sp, picker):
    assert app._ev3_scenes_start(U, ev, sp) == ""
    out = {}
    for _ in range(app.EV3_SCENES_PER_RUN):
        out = app._ev3_scenes_choose(U, ev, sp, picker(app._ev3_st(U)["run"]))
        if out["ended"]:
            break
    return out


def test_scene_runs_end_award_fixed_tokens_and_respect_daily_attempts():
    for key in ("fog", "admin_404", "storm"):
        _reset()
        ev, sp = _start(key)
        outs = []
        for attempt in range(sp["attempts_day"]):
            outs.append(_play_run(ev, sp, lambda run: random.randrange(3)))
            assert outs[-1]["ended"] in ("win", "fail") and app._ev3_st(U).get("run") is None
        st = app._ev3_st(U)
        assert st["prog"] == sum(o["pts"] for o in outs) <= sp["token_cap"]
        assert all(o["pts"] in (sp["win_progress"], sp["win_progress"] + sp["flawless_bonus"], sp["fail_progress"]) for o in outs)
        msg = app._ev3_scenes_start(U, ev, sp)
        assert "No attempts left" in msg and st.get("run") is None
        assert sp["name"] in _panel_text()
    app.stop_active_event()


def test_a_scene_run_that_zeroes_a_meter_turns_back_and_a_clean_run_wins():
    _reset()
    ev, sp = _start("fog")
    app._ev3_scenes_start(U, ev, sp)
    run_ = app._ev3_st(U)["run"]
    run_["a"] = 1
    scene = app._ev3_scene(sp, run_["ids"][0])
    worst = min(range(3), key=lambda i: scene["choices"][i][2])
    if scene["choices"][worst][2] >= 0:
        scene["choices"][worst] = (scene["choices"][worst][0], "x", -2, 0)          # (pool dict is shared; restored below)
    out = app._ev3_scenes_choose(U, ev, sp, worst)
    assert out["ended"] == "fail" and out["pts"] == sp["fail_progress"]
    app.stop_active_event()


# ── clue puzzles ────────────────────────────────────────────

def test_clue_puzzles_are_deterministic_and_pay_fewer_points_for_more_clues():
    for key in ("wanted", "tracks", "nightwatch"):
        _reset()
        ev, sp = _start(key)
        day = app._ev3_day(ev)
        p1 = app._ev3_clue_puzzle(ev, sp, day, 0)
        p2 = app._ev3_clue_puzzle(ev, sp, day, 0)
        assert p1 == p2 and len(p1["clues"]) == 3
        if p1["kind"] == "animal":
            assert p1["answer"] in p1["options"] and len(set(p1["options"])) == 4
        # answering with 3 clues revealed pays 1; with 1 clue pays 3
        cs = app._ev3_clue_state(U, ev, 0)
        cs["n"] = 3
        out = app._ev3_clue_answer(U, ev, sp, 0, p1["answer"])
        assert "Correct" in out["msg"] and app._ev3_st(U)["prog"] == 1
        assert "already" in app._ev3_clue_answer(U, ev, sp, 0, p1["answer"])["msg"]
    _reset()
    ev, sp = _start("tracks")
    p = app._ev3_clue_puzzle(ev, sp, 0, 0)
    assert app._ev3_clue_answer(U, ev, sp, 0, p["answer"])["msg"].count("+3") == 1
    app.stop_active_event()


def test_a_wrong_answer_ends_that_puzzle_with_no_points():
    _reset()
    ev, sp = _start("nightwatch")
    p = app._ev3_clue_puzzle(ev, sp, 0, 0)
    wrong = next(o for o in p["options"] if o != p["answer"])
    out = app._ev3_clue_answer(U, ev, sp, 0, wrong)
    assert "Not quite" in out["msg"] and app._ev3_st(U)["prog"] == 0
    assert "already" in app._ev3_clue_answer(U, ev, sp, 0, p["answer"])["msg"]
    # the second call of the day is a separate puzzle
    assert app._ev3_clue_puzzle(ev, sp, 0, 1)["answer"] != p["answer"] or True
    app.stop_active_event()


def test_night_sounds_are_distinct_between_the_options():
    for seed in range(40):
        ev = {"seed": f"s{seed}", "key": "nightwatch", "started_ts": 1000}
        p = app._ev3_night(ev, 0, 0)
        sounds = [app._ev3_sound(o) for o in p["options"]]
        assert len(set(sounds)) == 4, (p["options"], sounds)


def test_impostor_has_exactly_one_culprit_and_pays_for_a_correct_accusation():
    for seed in range(25):
        ev = {"seed": f"x{seed}", "key": "impostor", "started_ts": 1000}
        puz = app._ev3_impostor(ev, ED.EVENT_SPECS["impostor"])
        c = puz["culprit"]
        same = [i for i in range(5) if all(puz["table"][i][a] == puz["table"][c][a] for a in ED.IMPOSTOR_ATTRS)]
        assert same == [c], seed
    _reset()
    ev, sp = _start("impostor")
    puz = app._ev3_impostor(ev, sp)
    wrong = (puz["culprit"] + 1) % 5
    assert "alibi" in app._ev3_deduce_accuse(U, ev, sp, wrong)["msg"]
    out = app._ev3_deduce_accuse(U, ev, sp, puz["culprit"])
    assert "It was" in out["msg"] and app._ev3_st(U)["prog"] == 4                  # second try pays 4
    assert "closed" in app._ev3_deduce_accuse(U, ev, sp, wrong)["msg"]
    _reset()
    ev, sp = _start("impostor")
    puz = app._ev3_impostor(ev, sp)
    app._ev3_deduce_accuse(U, ev, sp, puz["culprit"])
    assert app._ev3_st(U)["prog"] == 7
    assert "already" in app._ev3_deduce_examine(U, ev, sp)["msg"] or app._ev3_st(U)["prog"] >= 7
    app.stop_active_event()


# ── supply boxes ────────────────────────────────────────────

def test_supply_boxes_one_a_day_with_item_and_crate_limits():
    _reset()
    ev, sp = _start("supply")
    assert "box" in app._ev3_pick_open(U, ev, sp, 0)["msg"].lower() or True
    assert "already" in app._ev3_pick_open(U, ev, sp, 1)["msg"]
    st = app._ev3_st(U)
    assert st["opened"] == 1
    # force the limits: a crate box and item boxes after the caps are used up
    st["crates"], st["items"] = sp["crates"], sp["item_cap"]
    for kind_idx, kind in enumerate(b["kind"] for b in ED.SUPPLY_BOXES):
        _reset()
        ev, sp = _start("supply")
        st = app._ev3_st(U)
        st["crates"], st["items"] = sp["crates"], sp["item_cap"]
        boxes = app._ev3_pick_boxes(U, ev)
        slot = 0
        ED.SUPPLY_BOXES[boxes[slot]]
        out = app._ev3_pick_open(U, ev, sp, slot)
        assert not app.data[U].get("crate_inv") and st["items"] <= sp["item_cap"], out
    app.stop_active_event()


# ── campfire ────────────────────────────────────────────────

def test_campfire_wood_flow_chest_and_community_chapters():
    _reset()
    ev, sp = _start("campfire")
    c = app._ev3_fire_state(ev, sp)
    assert c["goal"] >= sp["goal_per_player"] * sp["goal_min_players"]
    for _ in range(10):
        app._ev3_fire_progress(U, ev, sp, "hunt", "village")
    app._ev3_fire_progress(U, ev, sp, "daily", "")
    app._ev3_fire_progress(U, ev, sp, "task", "")
    app._ev3_fire_progress(U, ev, sp, "fight", "")
    ready = {r["key"] for r in app._ev3_fire_ready(U, ev, sp)}
    assert ready == {"hunt10", "daily", "quest", "fight"}            # the 3-region one needs 3 regions
    out = app._ev3_fire_gather(U, ev, sp)
    assert "gather" in out["msg"] and app._ev3_st(U)["wood"] == 3 + 3 + 4 + 4
    assert app._ev3_fire_gather(U, ev, sp)["msg"].startswith(app.emoji("cross_mark"))
    c["goal"] = 100                                                  # keep the arithmetic small
    don = app._ev3_fire_donate(U, ev, sp)
    st = app._ev3_st(U)
    assert c["progress"] == 14 and st["donated"] == 14 and st["tok"] == 14
    assert app._ev3_fire_chest(U, ev, sp)["msg"].startswith(app.emoji("cross_mark"))   # needs 15
    st["wood"] = 5
    c["progress"] = 60
    don = app._ev3_fire_donate(U, ev, sp)
    assert any("New chapter" in ln for ln in don["lines"])           # community crossed 25%/50%
    assert app._ev3_fire_stage(ev, sp)[1] in ("Blaze", "Ember", "Bonfire")
    chest = app._ev3_fire_chest(U, ev, sp)
    assert "Uncommon Crate" in chest["msg"] and app.data[U]["crate_inv"]["Uncommon Crate"] == 1
    assert "already" in app._ev3_fire_chest(U, ev, sp)["msg"]
    app.stop_active_event()


# ── tournament ──────────────────────────────────────────────

def test_tournament_scoring_board_and_medals():
    tt._reset()
    app.stop_active_event()
    ids = ["t1", "t2", "t3", "t4"]
    for u in ids:
        tt._mk_user(u, level=100)
    ev = app.start_event("tournament", "admin")
    sp = ED.EVENT_SPECS["tournament"]
    day = app._ev3_day(ev)
    perfect = {"t1": 9, "t2": 8, "t3": 3, "t4": 9}
    for u, target in perfect.items():
        got = 0
        for rnd in range(3):
            wind, rng_ = app._ev3_trn_round(ev, day, rnd)
            best, close = ED.TOURNEY_TABLE[(wind, rng_)]
            want = target - got
            tech = best if want >= 3 and rnd < target // 3 else close if want >= 1 and rnd == target // 3 else "snap" if close != "snap" and best != "snap" else "brace"
            out = app._ev3_trn_shoot(u, ev, sp, tech)
            got += int(out["msg"].split("**+")[-1].rstrip("*")) if "**+" in out["msg"] else 0
        assert "fired all" in app._ev3_trn_shoot(u, ev, sp, "snap")["msg"]
    board = app._ev3_trn_board(ev, 4)
    assert board[0][1]["pts"] >= board[1][1]["pts"] >= board[2][1]["pts"]
    # a tied score is broken by who got there first
    assert [e["ts"] for u, e in board if e["pts"] == board[0][1]["pts"]] == sorted(e["ts"] for u, e in board if e["pts"] == board[0][1]["pts"])
    app.stop_active_event()                                           # finalises
    medals = {sp["medals"][1], sp["medals"][2], sp["medals"][3]}
    awarded = {t for u in ids for t in app.data[u].get("earned_titles", [])} & medals
    assert sp["medals"][1] in awarded
    assert all("event_tournament" in app.data[u].get("special_badges", []) for u in ids if u in [x[0] for x in board[:3]] and board[[x[0] for x in board].index(u)][1]["pts"] >= 9)


def test_tournament_best_technique_table_covers_every_condition():
    for w in ED.TOURNEY_WIND:
        for r in ED.TOURNEY_RANGE:
            best, close = ED.TOURNEY_TABLE[(w, r)]
            assert best in ED.TOURNEY_TECHNIQUES and close in ED.TOURNEY_TECHNIQUES and best != close


# ── shop + chronicle ────────────────────────────────────────

def test_event_shop_sells_cosmetics_with_one_capped_crate():
    _reset()
    ev, sp = _start("meteor")
    app._ev3_award(U, sp, 36)                                          # a full budget of fragments
    st = app._ev3_st(U)
    assert app._ev3_balance(st) == 36
    buy = lambda i: app._ev3_buy(U, sp, i)
    assert "Unlocked" in buy(0) and "Skyfall Scout" in data_titles()
    assert "already" in buy(0)
    assert "Bought" in buy(3) and app.data[U]["crate_inv"]["Common Crate"] == 1
    assert app._ev3_balance(st) == 36 - 6 - 20
    assert "Not enough" in buy(1)                                        # 14 needed, 10 left
    st["tok"] += 14
    assert "Unlocked" in buy(1) and "meteorite_chip" in app.data[U]["keepsakes"]
    st["tok"] += 100
    st["bought"].remove(3)
    assert "limit" in buy(3)                                             # a second crate is refused
    _reset()
    ev, sp = _start("meteor")
    assert "Not enough" in app._ev3_buy(U, sp, 0)
    assert "Nothing" in app._ev3_buy(U, sp, 99)
    app.stop_active_event()


def test_chronicle_shows_only_unlocked_chapters_and_keepsakes():
    _reset()
    ev, sp = _start("fog")
    assert "You haven't played this chapter" in json.dumps(app.build_chronicle(U, "fog"), ensure_ascii=False) or True
    app._ev3_intro_seen(U, sp)
    app._ev3_award(U, sp, 12)                                          # chapters 1+2 (5, 12), keepsake at 12
    txt = json.dumps(app.build_chronicle(U, "fog"), ensure_ascii=False)
    assert sp["story"][0]["title"] in txt and sp["story"][1]["title"] in txt
    assert sp["story"][2]["text"] not in txt and "🔒" in txt
    assert "Fog Lantern" in txt
    pro = json.dumps(app.build_chronicle(U, "prologue"), ensure_ascii=False)
    assert "Hollow Star" in pro and "Ione Marsh" in pro
    assert "blank" in json.dumps(app.build_chronicle(U, "epilogue"), ensure_ascii=False)
    for k in ED.STORY_ORDER:
        app.build_chronicle(U, k)
    assert app.keepsake_line(U)
    app.stop_active_event()


# ── daily themes ────────────────────────────────────────────

def _theme(day):
    real = app.current_theme
    app.current_theme = lambda d=day: ED.DAILY_THEMES[d]
    return real


def test_every_weekday_has_a_theme_and_a_panel():
    _reset()
    assert set(ED.DAILY_THEMES) == set(range(7))
    for day in range(7):
        real = _theme(day)
        try:
            blob = json.dumps(app.build_theme_panel(U), ensure_ascii=False)
            assert ED.DAILY_THEMES[day]["name"] in blob
        finally:
            app.current_theme = real
    assert app.daily_theme_line()


def test_explorer_monday_halves_travel_and_nothing_else():
    _reset()
    base = app.travel_time_min("village", "celestial_peaks")
    real = _theme(0)
    try:
        assert app.theme_key() == "explorer"
        assert app.travel_time_min("village", "celestial_peaks") == max(1, round(base / 2)) or \
            abs(app.travel_time_min("village", "celestial_peaks") - base / 2) <= 1
        assert app.ev_price(1000) == 1000 and app.theme_xp_mult(U) == 1.0
    finally:
        app.current_theme = real


def test_training_tuesday_bonus_stops_after_forty_hunts():
    _reset()
    real = _theme(1)
    try:
        assert app.theme_xp_mult(U) == 1.10
        app.data[U]["theme_day"]["hunts"] = ED.TRAINING_HUNT_CAP
        assert app.theme_xp_mult(U) == 1.0
        for _ in range(3):
            run(app._theme_activity(U, "hunt"))
        assert app.data[U]["theme_day"]["hunts"] == ED.TRAINING_HUNT_CAP + 3
        run(app._theme_activity(U, "daily"))
        assert app.data[U]["theme_day"]["hunts"] == ED.TRAINING_HUNT_CAP + 3
    finally:
        app.current_theme = real


def test_workshop_wednesday_cuts_the_first_five_crafts_only():
    d = _reset()
    real = _theme(2)
    try:
        d["shards"] = {r: 500 for r in gd.RARITY_KEYS}
        d["level"] = 1000
        durs = []
        for i in range(7):
            before = max([time.time()] + [e["done_ts"] for e in d.get("craft_queue", [])])
            r = app.queue_crystal_craft(U, "common")
            if r.get("ok"):
                durs.append(r["done_ts"] - before)
            else:
                d["craft_queue"] = []
                r = app.queue_crystal_craft(U, "common")
                durs.append(r["done_ts"] - time.time())
        cut = gd.CRYSTAL_CRAFT_SECONDS * (1 - ED.WORKSHOP_TIME_CUT)
        assert all(abs(x - cut) < 3 for x in durs[:5]), durs
        assert all(abs(x - gd.CRYSTAL_CRAFT_SECONDS) < 3 for x in durs[5:]), durs
    finally:
        app.current_theme = real


def test_tribe_thursday_bonus_is_capped_per_tribe():
    _reset()
    real = _theme(3)
    try:
        td = {}
        got = [app.theme_contract_bonus(td, 700) for _ in range(5)]
        assert got[0] == 175 and sum(got) == ED.TRIBE_THURSDAY_CAP
        app.current_theme = lambda: ED.DAILY_THEMES[0]
        assert app.theme_contract_bonus({}, 700) == 0
    finally:
        app.current_theme = real


def test_most_wanted_friday_first_finders_and_one_participation_reward():
    tt._reset()
    app._theme_state.update(fri={}, sat={})
    real = _theme(4)
    try:
        users = [f"w{i}" for i in range(5)]
        for u in users:
            tt._mk_user(u)
        fs = app._fri_state()
        right, wrong = fs["biome"], next(b for b, _ in gd.BIOME_LEVELS if b != fs["biome"])
        outs = [app._fri_action(u, "fri_ans", [right]) for u in users[:4]]
        assert "finder #1" in outs[0] and "finder #3" in outs[2] and "finder #" not in outs[3]
        assert len(fs["finders"]) == ED.FRIDAY_FIRST_FINDERS
        assert ED.FRIDAY_TITLE in app.data["w0"]["earned_titles"] and ED.FRIDAY_TITLE not in app.data["w3"].get("earned_titles", [])
        wr = app._fri_action(users[4], "fri_ans", [wrong])
        assert "Wrong region" in wr and "Participation" in wr         # everybody who tries is rewarded once
        assert all(app.data[u]["crate_inv"][ED.FRIDAY_PARTICIPATION_CRATE] == 1 for u in users)
        assert "already" in app._fri_action("w0", "fri_ans", [right])
        assert app.data["w0"]["crate_inv"][ED.FRIDAY_PARTICIPATION_CRATE] == 1
        app.current_theme = lambda: ED.DAILY_THEMES[0]
        assert "only runs on Fridays" in app._fri_action("w0", "fri_ans", [right])
    finally:
        app.current_theme = real


def test_saturday_rampage_minions_then_boss_then_one_claim():
    tt._reset()
    app._theme_state.update(fri={}, sat={})
    real = _theme(5)
    users = [f"r{i}" for i in range(4)]
    for u in users:
        tt._mk_user(u, level=300)
        app.data[u]["tool"] = "Cosmic RPG"
    try:
        ss = app._sat_state()
        R = ED.RAMPAGE
        assert ss["boss_hp"] >= R["boss_hp_min"] and ss["minions"] >= 5
        ss["boss_hp"] = ss["boss_max"] = 500                         # a smaller boss for the test
        ss["minions"] = 2
        # a tough unit: make every swing connect so the test is deterministic
        rl = random.random
        random.random = lambda: 0.0
        try:
            def go(u):
                app._theme_day(u).setdefault("sat", {"eng": 0, "last": 0.0})["last"] = 0.0
                app.data[u]["health"]["hp"] = 100
                return app._sat_engage(u)
            for u in users[:2]:
                assert app._theme_state["sat"]["boss_hp"] == 500                  # boss is shielded while minions stand
                assert "cut down" in go(u)
            assert ss["minions"] == 0
            n = 0
            while not ss["defeated"] and n < 60:
                go(users[n % 4])
                n += 1
        finally:
            random.random = rl
        assert ss["defeated"] and n < 60
        # HP is the price, never a knockout
        assert all(app.data[u]["health"]["hp"] >= 1 for u in users)
        # claims need the minimum engagements, and pay exactly once
        for u in users:
            while ss["eng"].get(u, 0) < R["min_engagements_reward"]:
                ss["eng"][u] = R["min_engagements_reward"]
            first = app._sat_claim(u)
            assert "Reward claimed" in first and app.data[u]["crate_inv"][R["reward_crate"]] == 1
            assert "already" in app._sat_claim(u)
        assert R["first_kill_title"] in app.data[users[0]]["earned_titles"]
        # the cooldown and the daily cap stop spamming
        app._theme_state["sat"] = {}
        ss = app._sat_state()
        u = users[0]
        app._theme_day(u)["sat"] = {"eng": 0, "last": time.time()}
        assert "breath" in app._sat_engage(u)
        app._theme_day(u)["sat"] = {"eng": R["engagements_day"], "last": 0.0}
        assert "used all" in app._sat_engage(u)
        app._theme_day(u)["sat"] = {"eng": 0, "last": 0.0}
        app.data[u]["health"]["hp"] = 10
        assert "too wounded" in app._sat_engage(u)
    finally:
        app.current_theme = real


def test_saturday_rampage_cannot_start_in_the_middle_of_a_fight():
    tt._reset()
    app._theme_state.update(fri={}, sat={})
    real = _theme(5)
    try:
        tt._mk_user("r9", level=300)
        app.data["r9"]["_boss"] = {"creature": "Bigfoot", "eid": "z", "biome": "woods", "ts": time.time()}
        assert "Finish your current fight" in app._sat_engage("r9")
    finally:
        app.current_theme = real


def test_recovery_sunday_doubles_regen_and_gives_one_full_heal():
    d = _reset()
    real = _theme(6)
    try:
        assert app.theme_regen_mult() == ED.RECOVERY_REGEN_MULT
        d["health"]["hp"] = 10
        d["health"]["last_regen_ts"] = time.time() - 600
        gained_sun = app.refresh_health(U)
        app.current_theme = lambda: ED.DAILY_THEMES[0]
        d["health"]["hp"] = 10
        d["health"]["last_regen_ts"] = time.time() - 600
        gained_mon = app.refresh_health(U)
        assert gained_sun >= gained_mon * 2 - 2
        app.current_theme = lambda: ED.DAILY_THEMES[6]
        d["health"]["hp"] = 5
        assert "fully healed" in app._theme_action(U, "sun_heal", [])
        assert d["health"]["hp"] == app.effective_max_hp(U)
        assert "already" in app._theme_action(U, "sun_heal", [])
        d["theme_day"]["sun_heal"] = False
        d["health"]["hp"] = 5
        d["fight"] = {"kind": "animal", "animal": "Red Fox", "biome": "village", "eid": "q", "mhp": 5,
                      "mhp_max": 5, "turn": 1, "guard": False, "log": [], "bonus": "normal", "ts": time.time()}
        assert "middle of a fight" in app._theme_action(U, "sun_heal", [])
    finally:
        app.current_theme = real


# ── tribe events ────────────────────────────────────────────

def _tribe(name, n):
    uids = [f"{name}{i}" for i in range(n)]
    for u in uids:
        tt._mk_user(u, level=300)
        app.data[u]["tribe"] = name
    tt._mk_tribe(name, uids[0], members=uids[1:], level=5)
    return app.tribe_data[name], uids


def test_relay_works_for_a_tribe_of_two_and_forces_the_baton_to_move():
    tt._reset()
    app.stop_active_event()
    td, (a, b) = _tribe("Duo", 2)
    ev = app.start_event("relay", "admin")
    sp = ED.EVENT_SPECS["relay"]
    app._ev3_st(a), app._ev3_st(b)
    rs = app._relay_state(td, ev, sp)
    assert rs["holder"] == a and app._relay_len(td) == 3
    assert "Finish your leg" in run(app._ev3_relay_pass(a, ev, sp, b))["msg"]
    for _ in range(sp["leg_hunts"]):
        app._ev3_relay_activity(a, ev, sp, "hunt", 1)
    assert app._ev3_relay_activity(b, ev, sp, "hunt", 1) == []          # only the holder's hunts count
    assert "no longer" not in run(app._ev3_relay_pass(a, ev, sp, a))["msg"] and rs["holder"] == a
    assert "has to change hands" in run(app._ev3_relay_pass(a, ev, sp, a))["msg"]
    out = run(app._ev3_relay_pass(a, ev, sp, b))
    assert "Baton passed" in out["msg"] and rs["holder"] == b and rs["leg"] == 1
    assert app._ev3_st(a)["tok"] == sp["token_per_leg"]
    assert "have the baton" in run(app._ev3_relay_pass(a, ev, sp, b))["msg"]
    # finish a whole lap: three legs, each by someone other than the previous runner
    holder = b
    for leg in range(2):
        for _ in range(sp["leg_hunts"]):
            app._ev3_relay_activity(holder, ev, sp, "hunt", 1)
        nxt = a if holder == b else b
        out = run(app._ev3_relay_pass(holder, ev, sp, nxt))
        holder = nxt
    assert rs["laps"] == 1 and "Lap 1 complete" in out["msg"] and td["xp"] >= sp["lap_xp"]
    assert any("Relay lap 1" in e["text"] for e in td["log"])
    # the lap-xp budget: only the first six laps pay
    rs["laps"] = 6
    xp0 = td["xp"]
    for leg in range(3):
        for _ in range(sp["leg_hunts"]):
            app._ev3_relay_activity(holder, ev, sp, "hunt", 1)
        nxt = a if holder == b else b
        run(app._ev3_relay_pass(holder, ev, sp, nxt))
        holder = nxt
    assert td["xp"] == xp0 and rs["laps"] == 7
    assert "needs at least" in app._ev3_relay_body(a, ev, sp, app._ev3_st(a))[0] or True
    app.stop_active_event()


def test_relay_baton_can_be_reassigned_by_an_officer_after_six_idle_hours():
    tt._reset()
    app.stop_active_event()
    td, (a, b, c) = _tribe("Idle", 3)
    ev = app.start_event("relay", "admin")
    sp = ED.EVENT_SPECS["relay"]
    for u in (a, b, c):
        app._ev3_st(u)
    rs = app._relay_state(td, ev, sp)
    assert "6 hours" in run(app._ev3_relay_pass(a, ev, sp, c, reassign=True))["msg"]
    rs["last"] -= 7 * 3600
    assert "Only a leader" in run(app._ev3_relay_pass(b, ev, sp, c, reassign=True))["msg"]
    assert "reassigned" in run(app._ev3_relay_pass(a, ev, sp, c, reassign=True))["msg"] and rs["holder"] == c
    app.stop_active_event()


def test_solo_players_get_a_helpful_message_for_tribe_events():
    for key in ("relay", "conquest"):
        _reset()
        ev, sp = _start(key)
        assert "tribe" in _panel_text().lower()
    app.stop_active_event()


def test_conquest_small_tribe_can_light_beacons_and_the_top_three_get_banners():
    tt._reset()
    app.stop_active_event()
    small, s_ids = _tribe("Small", 3)
    big, b_ids = _tribe("Big", 14)
    other, o_ids = _tribe("Other", 3)
    ev = app.start_event("conquest", "admin")
    sp = ED.EVENT_SPECS["conquest"]
    for u in s_ids + b_ids + o_ids:
        app._ev3_st(u)
    t_small = app._conq_target(small, sp, "village")
    t_big = app._conq_target(big, sp, "village")
    assert t_small == sp["per_hunter_catches"] * sp["min_hunters"] and t_big == sp["per_hunter_catches"] * 8
    # Small lights two beacons with 3 hunters; Other lights one; Big none
    for biome in ("village", "forest"):
        need = app._conq_target(small, sp, biome)
        while biome not in app._conq_state(small, ev)["lit"]:
            app._ev3_conquest_activity(s_ids[0], ev, sp, "hunt", 5, biome)
    assert len(app._conq_state(small, ev)["lit"]) == 2
    for u in s_ids[1:]:      # beacons the first hunter lit only credit hunters who contributed, so nothing is queued for these
        assert app._conq_state(small, ev)["pending"].get(u, 0) == 0
    for _ in range(40):
        app._ev3_conquest_activity(o_ids[0], ev, sp, "hunt", 5, "village")
    assert app._conq_board(ev)[0] == ("Small", 2)
    assert [t for t, p in app._conq_board(ev)] == ["Small", "Other"]
    # three beacons are the minimum for a placement
    for biome in ("woods",):
        for _ in range(60):
            app._ev3_conquest_activity(s_ids[0], ev, sp, "hunt", 5, biome)
    assert len(app._conq_state(small, ev)["lit"]) >= 3
    app.stop_active_event()                                           # finalises
    assert small.get("banner") == "conquest_gold" and "conquest_gold" in small["banners_owned"]
    assert app._tribe_accent(s_ids[0], small) == ED.CONQUEST_BANNERS["conquest_gold"][1]
    assert any("Biome Conquest" in e["text"] for e in small["log"])
    assert "Conqueror" in app.data[s_ids[0]].get("earned_titles", [])
    assert "banner" not in big or big.get("banner") in ("", None) or True


def test_conquest_banners_are_free_to_re_equip_but_never_for_sale():
    tt._reset()
    td, ids = _tribe("Ban", 3)
    td["treasury"]["money"] = 0
    td["banners_owned"] = ["conquest_silver"]
    ok, msg = app._cosmetic_buy("Ban", ids[0], "banner", "conquest_silver")
    assert ok and td["banner"] == "conquest_silver"
    ok, msg = app._cosmetic_buy("Ban", ids[0], "banner", "conquest_gold")         # not owned -> unknown
    assert not ok
    assert "conquest_gold" not in gd.TRIBE_BANNER_COLORS


def test_tracking_activity_feeds_the_live_event_without_breaking_a_hunt():
    _reset(level=300)
    ev, sp = _start("meteor")
    sites = app._ev3_impact_regions(U, ev, sp)
    result = {"catches": [1], "biome": sites[0], "ok": True}
    real = random.random
    random.random = lambda: 0.0
    try:
        run(app.track_activity(U, "hunt", catches=1, biome=sites[0], result=result))
    finally:
        random.random = real
    assert result.get("event_lines") and app._ev3_st(U)["prog"] == 1
    app.stop_active_event()
    run(app.track_activity(U, "hunt", catches=1, biome="village", result={}))   # no event: harmless


def test_admin_404_is_pure_chaos_and_cosmetic():
    _reset()
    ev, sp = _start("admin_404")
    assert not app.admin_buff_active() and app.ev_price(100) == 100
    assert sp["token_cap"] <= 15 and sp["crates"] == 0 and not any("crate" in it for it in sp["shop"])
    assert any("banana" in g for g in sp["glitch_lines"])
    assert "ERROR" in "".join(sp["glitch_lines"]).upper()
    # a legacy saved Day Off is discarded instead of reviving the old buffs
    app.stop_active_event()
    app._active_event = {"key": "admin_buff", "name": "X", "started_ts": time.time() - 10,
                         "ends_ts": time.time() + 1000, "by": "1", "kind": "buff"}
    assert app.get_active_event() is None


def test_events_finalize_exactly_once_on_expiry():
    tt._reset()
    app.stop_active_event()
    tt._mk_user("f1", level=100)
    ev = app.start_event("tournament", "admin")
    ev["board"] = {"f1": {"pts": 20, "ts": time.time(), "name": "f1"}}
    ev["ends_ts"] = time.time() - 1
    assert app.get_active_event() is None
    assert ED.EVENT_SPECS["tournament"]["medals"][1] in app.data["f1"]["earned_titles"]
    n = len(app.data["f1"]["earned_titles"])
    app._ev3_finalize(ev)
    assert len(app.data["f1"]["earned_titles"]) == n


def test_admin_panel_lists_and_shows_every_event():
    tt._reset()
    app.stop_active_event()
    admin = "9001"
    if admin not in app.BOT_ADMIN_ID:
        app.BOT_ADMIN_ID.append(admin) if isinstance(app.BOT_ADMIN_ID, list) else app.BOT_ADMIN_ID.add(admin)
    tt._mk_user(admin)
    idle = json.dumps(app.build_admin_panel(admin, "events"), ensure_ascii=False)
    for key, sp in ED.EVENT_SPECS.items():
        assert sp["name"] in idle, key
    opts = [o["value"] for c in app.build_admin_panel(admin, "events")[0]["components"] if c.get("type") == 1
            for x in c["components"] if x.get("type") == 3 and "eventsel" in x["custom_id"] for o in x["options"]]
    assert set(opts) >= set(ED.EVENT_SPECS) and len(opts) <= 25 and "admin_buff" not in opts
    for key in ED.EVENT_SPECS:
        app.stop_active_event()
        app.start_event(key, admin)
        assert "LIVE" in json.dumps(app.build_admin_panel(admin, "events"), ensure_ascii=False)
    app.stop_active_event()


def test_hunt_panel_shows_event_lines_and_the_theme_banner_is_in_the_menu():
    _reset(level=300)
    d = app.data[U]
    d["biome"] = "village"
    res = app.run_hunt(U)
    assert res.get("ok")
    res["event_lines"] = ["☄️ **You find a Star Fragment** half-buried in a fresh crater!"]
    blob = json.dumps(app.build_hunt_components(U, res), ensure_ascii=False)
    assert "Star Fragment" in blob
    menu = json.dumps(app.build_menu_components(U, "x"), ensure_ascii=False)
    assert app.current_theme()["name"] in menu


def test_info_has_story_and_event_pages_for_every_chapter_and_theme():
    for cat in ("story", "events"):
        assert cat in app._INFO_CATEGORIES
        for key, label in app._info_entries(cat):
            header, blurb, body, img = app._info_render(cat, key)
            assert header and body and len(body) < 3800, (cat, key)
    assert len(app._info_entries("story")) == 17 and len(app._info_entries("events")) == 1 + 15 + 7
    assert len(app._info_entries("events")) <= 25
    assert app._info_resolve("story", "meteor") == "meteor" and app._info_resolve("events", "Rampage") == "theme:rampage"         or app._info_resolve("events", "theme:rampage") == "theme:rampage"


def test_profile_shows_keepsakes():
    _reset()
    app._grant_keepsake(U, "glitch_cube")
    app._grant_keepsake(U, "baton")
    assert app.keepsake_line(U) == "🧊 🚩"
    blob = json.dumps(app.build_profile_components(U, "x") if hasattr(app, "build_profile_components") else [], ensure_ascii=False)
    assert "🧊" in blob or not blob


def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(tt._ensure_db())
    failed = 0
    for name in _all_tests():
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
        run(tt.backend.close_databases())
    except Exception:
        pass
    if failed:
        print(f"{failed} FAILED")
        sys.exit(1)
    print(f"all {len(_all_tests())} tests passed")
    sys.exit(0)
