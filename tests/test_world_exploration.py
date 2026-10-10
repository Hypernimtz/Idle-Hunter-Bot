"""
World & exploration: the Hippogriff's instant-trip chance is rolled once per journey, travel is blocked
mid-fight / mid-track, tracking needs real progress (watching and waiting alone cannot find a long trail),
global sightings give a small participation reward, cap one player's clue share, make repeat encounters
rarer, favour regions active hunters can reach, and let ordinary Mythicals appear while one is hidden.

Runs without pytest:  python tests/test_world_exploration.py
"""
import asyncio
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_world_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "8001"


def _fresh(**over):
    tt._reset()
    app._active_sighting = None
    app._last_sighting_end = 0.0
    return tt._mk_user(U, level=1000, **over)


def _equip(d, trophy):
    d["trophy_active"] = {trophy: time.time() + 3600}


# ───────── travel ─────────
def test_instant_travel_is_rolled_once_per_journey_not_per_reroute():
    d = _fresh(biome="village")
    _equip(d, "Primary Flight Quill")
    rolls = []
    real = app.trophy_proc
    app.trophy_proc = lambda uid, key: (rolls.append(key) or False) if key == "travel_instant_pct" else real(uid, key)
    try:
        t1 = app.start_travel(U, "forest")
        assert t1["mins"] > 0 and rolls == ["travel_instant_pct"]
        for dest in ("woods", "small_desert", "forest", "tundra", "jungle"):      # re-route again and again
            app.start_travel(U, dest)
        assert rolls == ["travel_instant_pct"]                                      # still just the one roll
        # a brand-new journey (after arriving) gets its own roll
        d["travel"], d["biome"] = None, "forest"
        app.start_travel(U, "woods")
        assert len(rolls) == 2
    finally:
        app.trophy_proc = real


def test_travel_is_blocked_during_a_fight_or_a_track():
    d = _fresh(biome="village")
    d["fight"] = {"kind": "animal", "animal": "Wolf", "ts": time.time()}
    it = tr.FakeInteraction(U, f"travel:confirm:forest:{U}")
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    assert "fighting or tracking" in " ".join(h.ephemerals) and d["travel"] is None and d["biome"] == "village"
    d["fight"] = None
    d["tracking"] = {"id": "t", "creature": "Bigfoot", "biome": "village", "step": 0, "need": 3, "progress": 0,
                     "goal": 9, "mistakes": 0, "perfect": True, "scene": "prints", "expires_ts": time.time() + 600}
    it = tr.FakeInteraction(U, f"travel:confirm:forest:{U}")
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    assert "fighting or tracking" in " ".join(h.ephemerals) and d["travel"] is None
    d["tracking"] = None
    it = tr.FakeInteraction(U, f"travel:confirm:forest:{U}")
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    assert d["travel"] is not None or d["biome"] == "forest"                       # allowed again


# ───────── tracking ─────────
def _track(need):
    d = _fresh(biome="village")
    app._tracking_start(U, "Bigfoot", "village")
    tr_ = d["tracking"]
    tr_["need"], tr_["goal"], tr_["progress"], tr_["step"] = need, need * 3, 0, 0
    return d, tr_


def test_watching_and_waiting_alone_cannot_find_a_long_trail():
    d, t = _track(4)                                    # goal 12, needs 8
    real = random.randint
    random.randint = lambda a, b: 100                   # never spooked
    try:
        kind = "ongoing"
        for _ in range(12):
            out = app.tracking_choice(U, "observe")
            kind = out["kind"]
            if kind != "ongoing":
                break
    finally:
        random.randint = real
    assert kind == "lost" and d.get("_boss") is None and "cold" in out["line"]


def test_a_short_trail_can_still_be_found_slowly_but_a_bold_mix_is_faster():
    d, t = _track(2)                                    # goal 6, needs 4
    real = random.randint
    random.randint = lambda a, b: 100
    try:
        steps = 0
        while True:
            out = app.tracking_choice(U, "observe")
            steps += 1
            if out["kind"] != "ongoing":
                break
    finally:
        random.randint = real
    assert out["kind"] == "located" and steps == 4      # slow and steady: four steps, not two
    d2, t2 = _track(2)
    random.randint = lambda a, b: 100
    try:
        out = app.tracking_choice(U, "flank")
        out = app.tracking_choice(U, "flank")           # +3 +3 = 6
    finally:
        random.randint = real
    assert out["kind"] == "located"                     # two bold steps still work


# ───────── sightings ─────────
def _sighting(**over):
    sg = {"id": "s1", "biome": "jungle", "creature": gd.BIOME_MYTHS["jungle"][0], "started_ts": time.time(),
          "ends_ts": time.time() + 3600, "revealed": False, "clues": 0, "contributors": []}
    sg.update(over)
    app._active_sighting = sg
    return sg


def test_one_player_cannot_supply_more_than_their_share_of_clues():
    d = _fresh(biome="jungle")
    sg = _sighting()
    for _ in range(200):
        app._sighting_add_clues(U, "jungle")
    assert sg["player_clues"][U] == app.SIGHTING_CLUES_PER_PLAYER_MAX < app.SIGHTING_CLUE_GOAL
    assert not sg["revealed"] and sg["clues"] == app.SIGHTING_CLUES_PER_PLAYER_MAX
    tt._mk_user("8002", level=1000, biome="jungle")
    for _ in range(200):
        app._sighting_add_clues("8002", "jungle")
        if sg["revealed"]:
            break
    assert sg["revealed"]                                   # a second hunter finishes it


def test_contributors_get_a_small_participation_reward_once():
    d = _fresh(biome="jungle")
    sg = _sighting(hunts={U: 5}, revealed=True, clues=50, revealed_ts=time.time())
    app._sighting_add_clues(U, "jungle")
    assert app.item_count(U, app.SIGHTING_REWARD_ITEM) == 1 and U in sg["rewarded"]
    app._sighting_add_clues(U, "jungle")
    assert app.item_count(U, app.SIGHTING_REWARD_ITEM) == 1                    # once per sighting
    tt._mk_user("8003", level=1000, biome="jungle")
    app._sighting_add_clues("8003", "jungle")                                  # arrived after the reveal, never helped
    assert app.item_count("8003", app.SIGHTING_REWARD_ITEM) == 0


def test_repeat_encounters_in_one_sighting_are_much_rarer():
    d = _fresh(biome="jungle")
    sg = _sighting(revealed=True)
    chance, creature = app._sighting_encounter_roll(U, "jungle")
    assert chance == app.SIGHTING_ENCOUNTER_CHANCE and creature == sg["creature"]
    d["_myth_pity"]["enc_n"] = 1                                                # you have met it once already
    chance2, _ = app._sighting_encounter_roll(U, "jungle")
    assert chance2 == app.SIGHTING_REPEAT_CHANCE < app.SIGHTING_ENCOUNTER_CHANCE
    for _ in range(40):                                                         # and no pity ladder on repeats
        assert app._sighting_encounter_roll(U, "jungle")[0] == app.SIGHTING_REPEAT_CHANCE


def test_a_hidden_sighting_no_longer_silences_every_other_mythical():
    _fresh(biome="jungle")
    _sighting(revealed=False)
    chance, forced = app._sighting_encounter_roll(U, "jungle")
    assert chance > 0 and forced == ""


def test_sighting_regions_favour_biomes_active_hunters_can_reach():
    tt._reset()
    app._active_sighting = None
    now = time.time()
    for i in range(30):                                  # thirty active level-300 hunters with decent tools
        tt._mk_user(str(8100 + i), level=300, tool="Gravity Trap", hunt_cd=now + 5)
    pool = ["jungle", "celestial_peaks"]
    picks = [app._sighting_pick_biome(pool) for _ in range(400)]
    assert picks.count("jungle") > picks.count("celestial_peaks") * 5           # endgame-only one is rare, not impossible
    assert app._sighting_pick_biome(["celestial_peaks"]) == "celestial_peaks"


def test_world_condition_blurbs_describe_what_they_really_do():
    wc = gd.WORLD_CONDITIONS
    assert "Perfect Catch" in wc["migration"]["blurb"] and "species" in wc["migration"]["blurb"]
    assert "Idle Camp" in wc["trading_boom"]["blurb"] and "hunting" in wc["trading_boom"]["blurb"]
    assert "XP" in wc["clear_skies"]["blurb"] and "Perfect Catch" in wc["aurora"]["blurb"]


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
