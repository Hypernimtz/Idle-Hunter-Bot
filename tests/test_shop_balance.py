"""
Shop balance: Ammo Pouch can't conjure gem ammo and respects the stack cap, Gift Box is no longer a
coin printer, timed boosts stop at MAX_TEMP_BOOST (and the items that would be wasted aren't
consumed), Haul Wagon isn't burned on a full haul, a maxed permanent boost isn't charged for, and
healing items have a purchase cap.

Runs without pytest:  python tests/test_shop_balance.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_shop_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "7401"


def _use(item):
    it = tr.FakeInteraction(U, "x")
    with tr.Harness() as h:
        run(app._use_generic_item_and_show(it, U, item))
    return " ".join(h.ephemerals)


def test_ammo_pouch_never_refills_gem_ammo_and_picks_basic_coin_ammo():
    tt._reset()
    d = tt._mk_user(U, level=300, tool="Longbow")
    for eq in ("Phantom Arrow", "Enchanted Arrow", None):
        d["equipped_ammo"], d["ammo_inv"] = eq, {"Phantom Arrow": 5}
        app.add_item(U, "Ammo Pouch", 1)
        _use("Ammo Pouch")
        assert d["ammo_inv"].get("Phantom Arrow") == 5          # never touched
        assert d["ammo_inv"].get("Wooden Arrow") == gd.AMMO_POUCH_QTY, d["ammo_inv"]


def test_ammo_pouch_is_refused_for_a_nuke_launcher_and_not_consumed():
    tt._reset()
    d = tt._mk_user(U, level=300, tool="Nuke Launcher")
    d["equipped_ammo"], d["ammo_inv"] = "Nuke", {"Nuke": 3}
    app.add_item(U, "Ammo Pouch", 1)
    out = _use("Ammo Pouch")
    assert "no basic coin ammo" in out and d["ammo_inv"] == {"Nuke": 3} and app.item_count(U, "Ammo Pouch") == 1


def test_ammo_pouch_respects_the_stack_cap():
    tt._reset()
    d = tt._mk_user(U, level=300, tool="Longbow")
    d["ammo_inv"] = {"Wooden Arrow": gd.AMMO_MAX_STACK - 5}
    app.add_item(U, "Ammo Pouch", 2)
    _use("Ammo Pouch")
    assert d["ammo_inv"]["Wooden Arrow"] == gd.AMMO_MAX_STACK
    assert "max stack" in _use("Ammo Pouch") and d["ammo_inv"]["Wooden Arrow"] == gd.AMMO_MAX_STACK
    assert app.item_count(U, "Ammo Pouch") == 1               # the second was refused, not eaten


def test_gift_box_expected_coin_return_is_below_its_price():
    lo, hi = gd.GIFT_BOX_COIN_X
    price_x = gd.ITEM_GOLD_SHOP["Gift Box"]["price_x"]
    assert gd.GIFT_BOX_COIN_CHANCE * (lo + hi) / 2 < 0.9 * price_x
    # and a simulated batch really does lose coins on average
    tt._reset()
    d = tt._mk_user(U, level=300)
    random.seed(7)
    spent = app.item_shop_price(price_x, d["level"]) * 400
    d["money"] = 0
    app.add_item(U, "Gift Box", 1)
    for _ in range(400):
        d["items"]["Gift Box"] = 1
        _use("Gift Box")
    assert d["money"] < spent, (d["money"], spent)


def test_timed_boosts_are_capped_and_items_arent_wasted_at_the_cap():
    tt._reset()
    d = tt._mk_user(U, level=300)
    d["temp_boosts"] = [{"stat": "luck", "amount": 150, "expires_at": time.time() + 600}] * 3   # 450 raw
    assert app.get_active_temp_boosts(U)["luck"] == gd.MAX_TEMP_BOOST
    app.add_item(U, "Signal Flare", 2)
    assert "maxed" in _use("Signal Flare") and app.item_count(U, "Signal Flare") == 2
    d["temp_boosts"] = []
    _use("Signal Flare")
    assert app.item_count(U, "Signal Flare") == 1 and app.get_active_temp_boosts(U)["luck"] == gd.SIGNAL_FLARE_LUCK


def test_haul_wagon_is_not_wasted_on_a_full_haul():
    tt._reset()
    d = tt._mk_user(U, level=300)
    d["idle"] = {"active": True, "stacks": 12, "started_at": time.time(), "haul": ["Red Fox"] * 15,
                 "capacity_upgrades": 0, "camp_biome": "village"}
    app.add_item(U, "Haul Wagon", 2)
    out = _use("Haul Wagon")
    assert "too full" in out and app.item_count(U, "Haul Wagon") == 2
    d["idle"]["haul"] = []
    _use("Haul Wagon")
    assert app.item_count(U, "Haul Wagon") == 1 and len(d["idle"]["haul"]) == app.idle_capacity(U)


def _click(cid):
    it = tr.FakeInteraction(U, cid)
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    return " ".join(h.ephemerals)


def test_shop_buy_is_refused_before_charging_when_the_boost_is_maxed():
    tt._reset()
    d = tt._mk_user(U, level=300, gems=500)
    d["boosts"]["luck"] = gd.MAX_PERSONAL_BOOST
    out = _click(f"shop:buy:Lucky Charm:{U}")
    assert "cap" in out and d["gems"] == 500, (out, d["gems"])
    d["boosts"]["luck"] = 0
    _click(f"shop:buy:Lucky Charm:{U}")
    assert d["gems"] < 500 and d["boosts"]["luck"] > 0


def test_healing_items_stop_selling_at_the_carry_cap():
    tt._reset()
    d = tt._mk_user(U, level=1, money=10 ** 9)
    d["healing_inv"] = {"Bandage": gd.HEALING_BUY_CAP}
    out = _click(f"shop:heal_buy:Bandage:{U}")
    assert "max" in out and d["healing_inv"]["Bandage"] == gd.HEALING_BUY_CAP and d["money"] == 10 ** 9


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
