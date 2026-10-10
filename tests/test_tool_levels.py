"""
Tools have a level requirement to BUY: the shop shows it, both buy handlers refuse under the lock,
owned tools / the level-1 Slingshot / the Nuke Launcher are unaffected.

Runs without pytest:  python tests/test_tool_levels.py
"""
import asyncio
import json
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_toollv_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "8601"


def _buy(name, via="tool_buy_acc"):
    cid = f"shop:{via}:{name}:{U}" if via == "tool_buy_acc" else f"shop:tool_buy:{U}"
    it = tr.FakeInteraction(U, cid, values=[name]) if via != "tool_buy_acc" else tr.FakeInteraction(U, cid)
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    return h


def test_every_buyable_tool_has_a_sane_level():
    prev = 0
    for name, t in sorted(gd.TOOLS.items(), key=lambda kv: kv[1]["tier"]):
        if name in ("Bare Hands", "Nuke Launcher"):
            continue
        lv = gd.tool_min_level(name)
        assert lv >= prev and lv >= 1, (name, lv, prev)
        prev = lv
    assert gd.tool_min_level("Slingshot") == 1
    assert max(gd.TOOL_MIN_LEVEL.values()) < 900            # even the top weapon opens before Celestial Peaks
    # every tool a biome recommends is buyable BEFORE that biome unlocks, so it gets used in the biomes before it
    for biome, tier in gd.BIOME_TOOL_TIER.items():
        need = dict(gd.BIOME_LEVELS).get(biome)
        for name, tool in gd.TOOLS.items():
            if tool["tier"] <= tier and name in gd.TOOL_MIN_LEVEL:
                assert gd.tool_min_level(name) < need, (name, biome)


def test_a_low_level_player_cannot_buy_a_high_tool_by_either_button():
    tt._reset()
    d = tt._mk_user(U, level=10, money=10 ** 9, gems=10 ** 6)
    for via in ("tool_buy_acc", "tool_buy"):
        h = _buy("Shotgun", via)
        assert "Shotgun" not in d["owned_tools"] and d["money"] == 10 ** 9
        assert "level 300" in " ".join(h.ephemerals), h.ephemerals
    _buy("Cosmic RPG")
    assert "Cosmic RPG" not in d["owned_tools"] and d["gems"] == 10 ** 6


def test_buying_works_at_the_required_level_and_slingshot_at_level_one():
    tt._reset()
    d = tt._mk_user(U, level=300, money=10 ** 9)
    _buy("Shotgun")
    assert "Shotgun" in d["owned_tools"]
    d2 = tt._mk_user(U, level=1, money=10_000)
    _buy("Slingshot")
    assert "Slingshot" in d2["owned_tools"]


def test_the_shop_list_shows_the_level_instead_of_a_buy_button():
    tt._reset()
    d = tt._mk_user(U, level=10, money=10 ** 9)
    app._tool_shop_page[U] = 1                       # Shortbow..Crossbow-ish page
    txt = json.dumps(app.build_shop_components(U, "tools"), ensure_ascii=False)
    assert "Unlocks at **level" in txt and "Lv " in txt


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
