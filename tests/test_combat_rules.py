"""
Combat rules: no free healing/regen mid-fight, idle fights expire, risky escapes,
tougher dangerous animals in harder biomes, 4.5x fight payout, KO cooldown.

Runs without pytest:  python tests/test_combat_rules.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_combat_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "c1"


def _setup(**over):
    tt._reset()
    tt._mk_user(U, **over)
    app.refresh_health(U)
    return app.data[U]


def _animal_fight(animal="British Grey Wolf", biome="forest", mhp=None):
    d = app.data[U]
    st = gd.animal_combat_stats(animal, biome)
    d["fight"] = {"kind": "animal", "animal": animal, "biome": biome, "eid": "e1",
                  "mhp": mhp or st["hp"], "mhp_max": st["hp"], "turn": 1, "guard": False,
                  "log": [], "bonus": "normal", "ts": time.time()}
    return d["fight"]


def test_regen_is_paused_while_a_fight_is_live():
    d = _setup()
    d["health"]["hp"] = 30
    d["health"]["last_regen_ts"] = time.time() - 3600           # an hour of "waiting"
    _animal_fight()
    assert app.refresh_health(U) == 0 and d["health"]["hp"] == 30
    d["fight"] = None
    d["health"]["last_regen_ts"] = time.time() - 600
    assert app.refresh_health(U) > 0                            # normal regen is back once it is over


def test_idle_fights_expire_without_reward_or_penalty():
    d = _setup()
    f = _animal_fight()
    f["ts"] = time.time() - gd.COMBAT_IDLE_TIMEOUT_SEC - 5
    money = d["money"]
    assert not app.player_in_combat(U) and d["fight"] is None and d["money"] == money
    d["_boss"] = {"creature": "Bigfoot", "eid": "b1", "biome": "woods"}
    assert app.player_in_combat(U)
    d["_boss"]["ts"] = time.time() - gd.COMBAT_IDLE_TIMEOUT_SEC - 5
    assert not app.player_in_combat(U) and not d["_boss"]


def test_healing_is_a_combat_turn_not_a_free_action():
    d = _setup()
    d["healing_inv"] = {"Bandage": 2, "Field Medkit": 1}
    d["health"]["hp"] = 50
    f = _animal_fight("Western Coyote", "village")
    before_mhp = f["mhp"]
    random.seed(3)
    out = app.animal_fight_turn(U, "heal")
    assert out["kind"] in ("ongoing", "ko")
    assert d["health"]["hp"] != 50 or out["kind"] == "ko"
    assert f["turn"] == 2 or out["kind"] == "ko"                # the turn advanced: the animal acted
    assert f["mhp"] == before_mhp                               # healing deals no damage
    assert d["healing_inv"].get("Bandage", 0) + d["healing_inv"].get("Field Medkit", 0) == 2
    assert app.player_in_combat(U) or d["fight"] is None


def test_combat_heal_picks_the_smallest_item_that_covers_the_gap():
    d = _setup()
    d["healing_inv"] = {"Bandage": 1, "First Aid Kit": 1, "Field Medkit": 1}
    d["health"]["hp"] = d["health"]["max_hp"] - 55
    app.combat_heal(U)
    assert "First Aid Kit" not in d["healing_inv"] and "Bandage" in d["healing_inv"] and "Field Medkit" in d["healing_inv"]
    d["healing_inv"] = {"Bandage": 1, "Field Medkit": 1}
    d["health"]["hp"] = 1
    app.combat_heal(U)
    assert "Field Medkit" not in d["healing_inv"]               # nothing covers it: use the biggest


def test_animal_flee_can_cost_hp_but_never_knocks_you_out():
    d = _setup()
    hurt_seen = False
    orig = random.random
    try:
        for roll in (0.0, 0.99):
            random.random = lambda r=roll: r
            d["health"]["hp"] = 3
            _animal_fight("British Grey Wolf", "forest")
            out = app.animal_fight_turn(U, "flee")
            assert out["kind"] == "escape" and d["fight"] is None and d["health"]["hp"] >= 1
            if roll == 0.0:
                assert out["hurt"] >= 1 and d["health"]["hp"] == 1
                hurt_seen = True
            else:
                assert out["hurt"] == 0
    finally:
        random.random = orig
    assert hurt_seen


def test_mythic_flee_costs_hp_only_when_the_escape_is_messy():
    d = _setup()
    d["_boss"] = {"creature": "Bigfoot", "eid": "b1", "biome": "woods", "ts": time.time()}
    d["health"]["hp"] = 60
    orig = random.randint
    try:
        random.randint = lambda a, b: 100                       # clean roll fails (needs <= chance)
        out = app.myth_fight_turn(U, "flee")
        assert out["kind"] == "escape" and not out["clean"] and out["hurt"] > 0
        assert d["health"]["hp"] == 60 - out["hurt"] and d["health"]["hp"] >= 1
        d["_boss"] = {"creature": "Bigfoot", "eid": "b2", "biome": "woods", "ts": time.time()}
        random.randint = lambda a, b: 1                         # clean getaway
        d["health"]["hp"] = 60
        out = app.myth_fight_turn(U, "flee")
        assert out["clean"] and out["hurt"] == 0 and d["health"]["hp"] == 60
    finally:
        random.randint = orig


def test_mythic_fights_have_a_heal_action_that_uses_a_turn():
    d = _setup()
    d["_boss"] = {"creature": "Bigfoot", "eid": "b1", "biome": "woods", "ts": time.time()}
    d["healing_inv"] = {"Bandage": 1}
    d["health"]["hp"] = 40
    out = app.myth_fight_turn(U, "heal")
    assert out["kind"] in ("ongoing", "death")
    assert "Bandage" not in d["healing_inv"]
    if out["kind"] == "ongoing":
        assert d["_boss"]["turn"] == 2


def test_dangerous_animals_scale_with_biome_difficulty():
    easy = gd.animal_combat_stats("British Grey Wolf", "village")
    hard = gd.animal_combat_stats("British Grey Wolf", "celestial_peaks")
    assert hard["hp"] > easy["hp"] * 1.8 and hard["hp"] <= 70 * gd.BIOME_DANGER_HP_CAP + 1
    assert hard["damage"][1] > easy["damage"][1]
    base = gd.animal_combat_stats("British Grey Wolf")
    assert base["hp"] == 70                                     # no biome: the authored numbers


def test_rare_predators_can_start_a_fight_but_ordinary_rares_cannot():
    assert gd.animal_encounter_chance("British Grey Wolf") == gd.RARE_PREDATOR_ENCOUNTER_CHANCE
    rare_gentle = next(a for a, v in gd.ANIMAL_DATA.items()
                       if v["rarity"] == "rare" and gd.animal_combat_stats(a)["behavior"] in ("passive", "skittish", "defensive"))
    assert gd.animal_encounter_chance(rare_gentle) == 0.0
    assert gd.animal_encounter_chance(next(a for a, v in gd.ANIMAL_DATA.items() if v["rarity"] == "legendary")) == 0.12


def test_fight_payout_is_modest_and_healing_costs_a_little_more():
    assert gd.ANIMAL_ENCOUNTER_REWARD_MULT == 4.5
    assert [gd.HEALING_ITEMS[n]["price_x"] for n in ("Bandage", "First Aid Kit", "Field Medkit", "Regen Tonic")] == [1.5, 3.5, 6.0, 2.5]
    d = _setup()
    d["health"]["hp"] = 40                                      # no 'healthy' bonus
    out = app._animal_fight_win(U, "Western Coyote", "village")
    value = gd.ANIMAL_DATA["Western Coyote"]["value"]
    assert out["sell_value"] <= int(value * 4.6 * (1 + 0.01 * max(0, app.get_total_boosts(U).get("sell", 0))) * 1.01) + 1


def test_ko_starts_a_short_cooldown_on_dangerous_encounters():
    d = _setup()
    assert app.ko_cooldown_left(U) == 0
    app.apply_ko_recovery(U)
    left = app.ko_cooldown_left(U)
    assert 0 < left <= gd.KO_COOLDOWN_SEC
    d["health"]["ko_until"] = time.time() - 1
    assert app.ko_cooldown_left(U) == 0


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
