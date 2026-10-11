"""
Tool level requirements were removed 2026-10-11: any tool can be bought at any level for its price.

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


def test_no_tool_has_a_level_requirement():
    for name in gd.TOOLS:
        assert gd.tool_min_level(name) == 1, name


def test_a_low_level_player_can_buy_any_tool_they_can_afford():
    tt._reset()
    d = tt._mk_user(U, level=10, money=10 ** 9, gems=10 ** 6)
    _buy("Shotgun")
    assert "Shotgun" in d["owned_tools"] and d["money"] == 10 ** 9 - gd.TOOLS["Shotgun"]["price"]
    _buy("Hunting Rifle", "tool_buy")
    assert "Hunting Rifle" in d["owned_tools"]
    _buy("Cosmic RPG")
    assert "Cosmic RPG" in d["owned_tools"]


def test_the_shop_list_shows_buy_buttons_not_level_locks():
    tt._reset()
    tt._mk_user(U, level=10, money=10 ** 9)
    app._tool_shop_page[U] = 1
    txt = json.dumps(app.build_shop_components(U, "tools"), ensure_ascii=False)
    assert "Unlocks at **level" not in txt and '"Buy"' in txt


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
