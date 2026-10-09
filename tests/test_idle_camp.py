"""
Idle Camp: fractional production is kept, Camp Rations cover a fixed number of catches (and stack
instead of being wasted), the bonus-item chance scales with haul size, passive hunting gets no
free ammo bonuses, the camp biome keeps its tool-tier gate, and the camp only speeds HP regen
while the player has actually stopped hunting.

Runs without pytest:  python tests/test_idle_camp.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_camp_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "7101"


def _camp(hunters=1, haul=0, **over):
    tt._reset()
    d = tt._mk_user(U, level=300, **over)
    d["idle"] = {"active": True, "stacks": hunters, "started_at": time.time(), "haul": ["Red Fox"] * haul,
                 "capacity_upgrades": 0, "camp_biome": "village"}
    return d


def test_fractional_production_is_kept_between_ticks():
    d = _camp()
    rate = app.idle_catches_per_hour(U)
    d["idle"]["started_at"] = time.time() - 3600 * (2.5 / rate)       # 2.5 catches worth of time
    assert app.idle_tick(U) == 2
    left = (time.time() - d["idle"]["started_at"]) / 3600 * rate
    assert 0.45 < left < 0.6, left                                      # the half catch is still owed
    d["idle"]["started_at"] -= 3600 * (0.5 / rate)                      # ...and completes later
    assert app.idle_tick(U) == 1
    # checking constantly doesn't change the total
    d2_total = 0
    d["idle"]["haul"] = []
    d["idle"]["started_at"] = time.time() - 3600 * (10 / rate)
    for _ in range(50):
        d["idle"]["started_at"] -= 3600 * (0.0 / rate)
        d2_total += app.idle_tick(U)
    assert d2_total == 10


def test_a_full_haul_freezes_then_restarts_the_clock_on_collect():
    d = _camp(haul=0)
    cap = app.idle_capacity(U)
    d["idle"]["haul"] = ["Red Fox"] * cap
    d["idle"]["started_at"] = time.time() - 36000
    assert app.idle_tick(U) == 0                                        # full: nothing added
    random.seed(2)
    res = app.collect_idle_haul(U)
    assert res["count"] == cap
    assert time.time() - d["idle"]["started_at"] < 5                   # clock restarted, no 10-hour backlog
    assert app.idle_tick(U) == 0


def test_a_partial_collect_keeps_the_leftover_fraction():
    d = _camp()
    rate = app.idle_catches_per_hour(U)
    d["idle"]["started_at"] = time.time() - 3600 * (3.5 / rate)
    app.collect_idle_haul(U)
    left = (time.time() - d["idle"]["started_at"]) / 3600 * rate
    assert 0.4 < left < 0.65, left


def _value_of_collect(haul):
    d = _camp(haul=0)
    d["idle"]["haul"] = list(haul)
    real = random.random
    random.random = lambda: 0.99                                        # no perfect catches, no item drop
    try:
        return app.collect_idle_haul(U)
    finally:
        random.random = real


def test_camp_rations_cover_only_the_next_fifteen_catches():
    base = _value_of_collect(["Red Fox"] * 40)["total_val"]
    d = _camp()
    d["_camp_rations"] = gd.CAMP_RATIONS_CATCHES
    d["idle"]["haul"] = ["Red Fox"] * 40
    real = random.random
    random.random = lambda: 0.99
    try:
        res = app.collect_idle_haul(U)
    finally:
        random.random = real
    one = base / 40
    expect = one * 25 + one * 15 * (1 + gd.CAMP_RATIONS_BONUS)
    assert abs(res["total_val"] - expect) <= 40, (res["total_val"], expect)      # not the whole haul
    assert res["ration_bonus"] == 15 and d["_camp_rations"] == 0


def test_rations_carry_over_when_the_haul_is_smaller_than_the_bonus():
    d = _camp()
    d["_camp_rations"] = 30
    d["idle"]["haul"] = ["Red Fox"] * 10
    real = random.random
    random.random = lambda: 0.99
    try:
        res = app.collect_idle_haul(U)
    finally:
        random.random = real
    assert res["ration_bonus"] == 10 and d["_camp_rations"] == 20


def test_using_rations_stacks_never_wastes_and_stops_at_the_cap():
    d = _camp()
    app.add_item(U, "Camp Rations", 5)
    msgs = []
    for _ in range(4):
        it = tr.FakeInteraction(U, "x")
        with tr.Harness() as h:
            run(app._use_generic_item_and_show(it, U, "Camp Rations"))
        msgs += h.ephemerals
    assert d["_camp_rations"] == gd.CAMP_RATIONS_STACK_CAP == 45       # three rations fill it
    assert app.item_count(U, "Camp Rations") == 2                       # the 4th was refused, not consumed
    assert any("stuffed" in m for m in msgs)
    d["idle"]["active"] = False
    it = tr.FakeInteraction(U, "x")
    with tr.Harness() as h:
        run(app._use_generic_item_and_show(it, U, "Camp Rations"))
    assert any("active Hunting Camp" in m for m in h.ephemerals) and app.item_count(U, "Camp Rations") == 2


def test_ration_drop_chance_scales_with_haul_size_not_with_clicks():
    def drops(n, roll):
        d = _camp(haul=0)
        d["idle"]["haul"] = ["Red Fox"] * n
        calls = {"n": 0}
        real = random.random

        def fake():
            calls["n"] += 1
            return roll if calls["n"] > n else 0.99                     # only the item roll sees `roll`
        random.random = fake
        try:
            return app.collect_idle_haul(U)["item_dropped"]
        finally:
            random.random = real
    assert drops(1, 0.01) is None                                       # 1 animal: ~0.1%
    assert drops(100, 0.05) == "Camp Rations"                           # 100 animals: ~10%
    assert drops(150, 0.11) == "Camp Rations"                           # capped at 12%
    assert drops(195, 0.13) is None
    assert gd.CAMP_RATIONS_PER_CATCH * 195 > gd.CAMP_RATIONS_COLLECT_CAP


def test_passive_hunting_ignores_equipped_ammo_bonuses():
    d = _camp()
    real = app.get_total_boosts
    app.get_total_boosts = lambda uid: {"luck": 50, "sell": 100, "xp": 100, "ammo_luck": 20, "ammo_sell": 60,
                                         "ammo_xp": 40, "crate_luck": 0}
    try:
        d["idle"]["haul"] = ["Red Fox"]
        assert app.idle_haul_sell_value(U) == int(gd.ANIMAL_DATA["Red Fox"]["value"] * (1 + 40 / 100))
        r = random.random
        random.random = lambda: 0.99
        try:
            res = app.collect_idle_haul(U)
        finally:
            random.random = r
        assert res["total_val"] == int(gd.ANIMAL_DATA["Red Fox"]["value"] * 1.40)
    finally:
        app.get_total_boosts = real


def test_camp_biome_keeps_its_tool_tier_gate():
    d = _camp()
    d["idle"]["camp_biome"] = "forest"
    d["tool"] = "Bare Hands"
    assert app.idle_camp_biome(U) == "village"
    tool = next(n for n, t in gd.TOOLS.items() if t["tier"] >= gd.BIOME_TOOL_TIER["forest"])
    d["tool"] = tool
    assert app.idle_camp_biome(U) == "forest"


def test_the_camp_only_speeds_regen_when_you_have_stopped_hunting():
    d = _camp()
    d["_last_hunt_ts"] = time.time()
    assert not app.player_is_resting(U)
    d["_last_hunt_ts"] = time.time() - gd.CAMP_REST_IDLE_SEC - 5
    assert app.player_is_resting(U)
    d["idle"]["active"] = False
    assert not app.player_is_resting(U)


def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))

def test_production_trophy_is_not_retroactive_and_lapses_mid_window():
    d = _camp()
    d["myth_items"] = {"Coarse Yowie Hair": 1}
    d["idle"]["started_at"] = time.time() - 3600 * 3
    app.trophy_slots_unlocked = lambda uid: 3
    base = app.idle_catches_per_hour(U)
    d["trophy_active"] = {}
    # using the trophy banks the 3h already earned at the base rate
    n_before = len(d["idle"]["haul"])
    res = app.use_trophy(U, "Coarse Yowie Hair")
    assert res.get("ok"), res
    assert len(d["idle"]["haul"]) - n_before == int(3 * base), (len(d["idle"]["haul"]), base)
    # a boost that lapsed 1h ago only counted for the 1h..2h slice it was running
    d["idle"]["haul"] = []
    d["idle"]["started_at"] = time.time() - 3600 * 3
    d["trophy_active"] = {"Coarse Yowie Hair": time.time() - 3600 * 2}     # expired 2h ago, ran the first hour
    got = app.idle_tick(U)
    assert got == int(base * 1.10 * 1 + base * 2), (got, base)



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
