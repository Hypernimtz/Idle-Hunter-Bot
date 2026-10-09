"""
Crates & crafting: crafting is a real alternative to drops, the forge gets faster with level, rewards
that would do nothing (duplicate title, capped permanent boost) pay coins instead, and the Mythic
Crate no longer promises a trophy it can't give.

Runs without pytest:  python tests/test_crate_balance.py
"""
import asyncio
import os
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_crate_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "7501"


def test_a_crafted_crate_costs_a_sane_number_of_shards():
    shards = gd.CRYSTAL_SHARD_COST * gd.CRATE_CRYSTAL_COST
    assert shards == 20 < 81
    # a drop is ~1 per 13-20 hunts; 20 shards at 10%/catch is ~200 catches of that rarity: slower, but reachable
    assert shards / gd.SHARD_DROP_CHANCE < 400


def test_the_forge_gets_faster_with_level_but_never_below_the_floor():
    assert gd.crystal_craft_seconds(1) == gd.CRYSTAL_CRAFT_SECONDS == 300
    assert gd.crystal_craft_seconds(500) < gd.crystal_craft_seconds(100) < 300
    assert gd.crystal_craft_seconds(1000) == gd.crystal_craft_seconds(5000) == gd.CRYSTAL_CRAFT_SECONDS_MIN
    tt._reset()
    d = tt._mk_user(U, level=1000)
    d["shards"] = {"common": 10}
    r = app.queue_crystal_craft(U, "common")
    assert r["ok"]
    import time
    assert abs((r["done_ts"] - time.time()) - gd.CRYSTAL_CRAFT_SECONDS_MIN) < 3


def test_duplicate_title_pays_coins_instead_of_nothing():
    tt._reset()
    d = tt._mk_user(U, level=300)
    d["earned_titles"] = ["Mythic Opener"]
    before = d["money"]
    rw = {"type": "title", "title": "Mythic Opener"}
    app._apply_reward_simple(U, rw, "crate")
    assert rw["type"] == "money" and rw["amount"] == gd.CRATE_DUPLICATE_PAYOUT_X * gd.crate_value_scale(300)
    assert d["money"] - before == rw["amount"] and "already own" in app._fmt_reward(rw)
    assert d["earned_titles"] == ["Mythic Opener"]
    rw2 = {"type": "title", "title": "Brand New"}
    app._apply_reward_simple(U, rw2, "crate")
    assert rw2["type"] == "title" and "Brand New" in d["earned_titles"]


def test_a_permanent_boost_at_the_cap_pays_coins_but_one_below_it_still_applies():
    tt._reset()
    d = tt._mk_user(U, level=300)
    d["boosts"]["sell"] = gd.MAX_PERSONAL_BOOST
    before = d["money"]
    rw = {"type": "perm_boost", "stat": "sell", "amount": 8}
    app._apply_reward_simple(U, rw, "crate")
    assert rw["type"] == "money" and d["money"] > before and d["boosts"]["sell"] == gd.MAX_PERSONAL_BOOST
    d["boosts"]["luck"] = gd.MAX_PERSONAL_BOOST - 3
    rw2 = {"type": "perm_boost", "stat": "luck", "amount": 8}
    app._apply_reward_simple(U, rw2, "crate")
    assert rw2["type"] == "perm_boost" and d["boosts"]["luck"] == gd.MAX_PERSONAL_BOOST


def test_mythic_crate_no_longer_promises_a_trophy():
    assert "trophy" not in gd.CRATE_TIERS["Mythic Crate"]["description"].lower()


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
