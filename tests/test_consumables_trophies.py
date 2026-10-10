"""
Consumables & trophies: Loch Silt Sample is a small crate nudge, the Phoenix really saves you mid-fight,
self-healing trophies are rate-limited, repeated timed boosts extend instead of stacking, one-shot items
cannot be wasted, Forge Coal moves the whole queue, Smoke Bomb escapes a Mythical, an unfinished Scratch Pad
can be resumed, and combat trophies say they are Mythical-fight effects.

Runs without pytest:  python tests/test_consumables_trophies.py
"""
import asyncio
import os
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_consum_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import test_myth_fight as tm       # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "7901"


def _use(item, uid=U):
    it = tr.FakeInteraction(uid, "x")
    with tr.Harness() as h:
        run(app._use_generic_item_and_show(it, uid, item))
    return " ".join(h.ephemerals)


def _equip(d, trophy):
    d["trophy_active"] = {trophy: time.time() + 3600}


def test_loch_silt_sample_is_a_small_nudge_not_a_triple():
    pp = gd.TROPHY_EFFECTS["Loch Silt Sample"]["value"]
    assert pp <= 2
    base = gd.hunt_crate_chance(19)
    assert gd.hunt_crate_chance(19, bonus=pp / 100) <= base * 1.4


def test_phoenix_saves_you_mid_fight_once_a_day():
    d = tm._mk("7912", hp=1)
    _equip(d, "Everburning Ember")
    with tm._Dice([1, 1]):                                    # your punch lands, and so does the monster's attack
        out = tm._turn("7912", "punch")
    assert out["kind"] == "ongoing", out
    assert d["health"]["hp"] == 30 and d["_boss"] is not None
    assert any("rise from the ashes" in line for line in d["_boss"]["log"])
    d["health"]["hp"] = 1
    with tm._Dice([1, 1]):
        out2 = tm._turn("7912", "punch")
    assert out2["kind"] == "death"                            # once per day only


def test_hydra_tooth_still_works():
    d = tm._mk("7913", hp=1)
    _equip(d, "Immortal Head Tooth")
    with tm._Dice([1, 1]):
        out = tm._turn("7913", "punch")
    assert out["kind"] == "ongoing" and d["health"]["hp"] == 1


def test_trophy_healing_is_rate_limited():
    tt._reset()
    d = tt._mk_user(U, level=100)
    d["health"].update(hp=10, max_hp=100)
    _equip(d, "Coffin Nail")
    assert app.trophy_heal(U, "hunt_hp_restore") == 3 and d["health"]["hp"] == 13
    assert app.trophy_heal(U, "hunt_hp_restore") == 0 and d["health"]["hp"] == 13      # same instant: no
    d["_trophy_heal_ts"]["hunt_hp_restore"] -= gd.TROPHY_HEAL_COOLDOWN_S["hunt_hp_restore"] + 1
    assert app.trophy_heal(U, "hunt_hp_restore") == 3
    d["health"]["hp"] = d["health"]["max_hp"]
    d["_trophy_heal_ts"]["hunt_hp_restore"] = 0
    assert app.trophy_heal(U, "hunt_hp_restore") == 0                                   # nothing to heal: no cooldown burned
    assert d["_trophy_heal_ts"]["hunt_hp_restore"] == 0


def test_repeating_a_timed_boost_extends_it_instead_of_stacking():
    tt._reset()
    d = tt._mk_user(U, level=100)
    for _ in range(5):
        app._append_temp_boost(d, "luck", 30, 30)            # five Bloodhound Scents
    assert len(d["temp_boosts"]) == 1 and app.get_active_temp_boosts(U)["luck"] == 30
    left = d["temp_boosts"][0]["expires_at"] - time.time()
    assert 140 * 60 < left <= 150 * 60                         # about 5 x 30 min
    for _ in range(40):
        app._append_temp_boost(d, "luck", 30, 30)
    assert d["temp_boosts"][0]["expires_at"] - time.time() <= gd.TEMP_BOOST_MAX_MINUTES * 60 + 1
    app._append_temp_boost(d, "luck", 15, 20)                  # a different item still combines (up to the cap)
    assert app.get_active_temp_boosts(U)["luck"] == 45


def test_a_second_war_horn_extends_the_tribe_buff():
    tribe = {}
    app._append_temp_boost(tribe, "luck", 10, 120)
    app._append_temp_boost(tribe, "luck", 10, 120)
    assert len(tribe["temp_boosts"]) == 1 and app._sum_active_boosts(tribe["temp_boosts"])["luck"] == 10


def test_one_shot_items_are_not_wasted_when_already_primed():
    tt._reset()
    d = tt._mk_user(U, level=100)
    for item, flag in (("Lucky Hammer", "_lucky_hammer_active"), ("Danger Whistle", "_danger_whistle_active")):
        app.add_item(U, item, 3)
        _use(item)
        assert d[flag] and app.item_count(U, item) == 2
        assert "already" in _use(item) and app.item_count(U, item) == 2


def test_forge_coal_moves_the_whole_queue_up():
    tt._reset()
    d = tt._mk_user(U, level=100)
    now = time.time()
    d["craft_queue"] = [{"rarity": "common", "done_ts": now + 300}, {"rarity": "common", "done_ts": now + 600},
                        {"rarity": "common", "done_ts": now + 900}]
    app.add_item(U, "Forge Coal", 1)
    _use("Forge Coal")
    assert len(d["craft_queue"]) == 2
    assert 295 < d["craft_queue"][0]["done_ts"] - now < 305
    assert 595 < d["craft_queue"][1]["done_ts"] - now < 605           # was 900, 300 sooner than before


def test_smoke_bomb_escapes_a_mythical_cleanly():
    d = tm._mk("7911", hp=40)
    app.add_item("7911", "Smoke Bomb", 1)
    _use("Smoke Bomb", "7911")
    assert d["_boss"] is None and d["health"]["hp"] == 40 and app.item_count("7911", "Smoke Bomb") == 0
    app.add_item("7911", "Smoke Bomb", 1)
    out = _use("Smoke Bomb", "7911")
    assert "no danger encounter" in out and app.item_count("7911", "Smoke Bomb") == 1


def test_an_unfinished_scratch_pad_can_be_resumed_without_another_pad():
    tt._reset()
    d = tt._mk_user(U, level=100)
    app.add_item(U, "Scratch Pad", 1)
    it = tr.FakeInteraction(U, "x")
    with tr.Harness() as h:
        run(app._start_scratch_pad_and_show(it, U))
    assert d["scratch_pad"] and app.item_count(U, "Scratch Pad") == 0
    it = tr.FakeInteraction(U, "x")
    with tr.Harness() as h:
        run(app._start_scratch_pad_and_show(it, U))
    assert "don't have" not in " ".join(h.ephemerals) and d["scratch_pad"]


def test_combat_trophies_say_they_are_mythical_fight_effects():
    keys = ("combat_accuracy_pct", "incoming_dmg_pct", "first_hit_bonus_dmg", "enemy_skip_pct",
            "double_hit_pct", "first_enemy_hit_reduction_pct", "burn_on_hit",
            "punch_kick_accuracy_pct", "hydra_survive_daily", "phoenix_revive_daily")
    for name, eff in gd.TROPHY_EFFECTS.items():
        if eff["effect_key"] in keys:
            assert "Mythical" in eff["desc"], name


def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(tt._ensure_db())
    run(tm._ensure_db())
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
