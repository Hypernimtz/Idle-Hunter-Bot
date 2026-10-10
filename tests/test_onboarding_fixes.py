"""
Onboarding & scratch pads: onboarding buttons only work at their own step (stale clicks can't rewind the
flow or restart the scripted fight), skipping the story still offers the starter specialty, the scripted
fight's reward is one-time, Hunter's Path points at the Tools tab and doesn't hold Mythicals back past
level 15, the tour no longer claims selling gives XP, and a scratch card never pays nothing.

Runs without pytest:  python tests/test_onboarding_fixes.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_onb_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "8401"


def _new_player(step="intro"):
    tt._reset()
    app.FEATURE_ONBOARDING_V2 = True
    d = tt._mk_user(U, level=1, money=150)
    d["onboarding"] = {"version": 2, "completed": False, "step": step, "starter_pack": None}
    return d


def _click(action, *extra):
    cid = ":".join(["onb", action, *extra, U])
    it = tr.FakeInteraction(U, cid)
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    return h


def test_a_stale_button_cannot_rewind_or_skip_ahead():
    d = _new_player("sell")
    inv_before = list(d.get("inv", []))
    _click("shoot")                                          # the 'take the shot' button from an older panel
    assert d["onboarding"]["step"] == "sell" and d.get("inv", []) == inv_before     # nothing happened
    _click("track")                                          # the first screen's button
    assert d["onboarding"]["step"] == "sell"
    _click("sell")                                           # the right one for this step
    assert d["onboarding"]["step"] == "trial"


def test_the_scripted_fight_cannot_be_restarted_by_an_old_trial_button():
    d = _new_player("danger")
    d["fight"] = None
    _click("trial_hunt")
    assert d["fight"] is None and not d.get("_onb_trial_caught") and not d.get("trial_tool")   # nothing was granted or started
    assert d["onboarding"]["step"] in ("danger", "pack")                                        # the stale redraw may self-heal forward


def test_skipping_the_story_still_offers_the_starter_specialty():
    d = _new_player("intro")
    _click("skip")
    assert d["onboarding"]["step"] == "pack" and not d["onboarding"]["completed"]
    _click("pack", "hunter")
    assert d["onboarding"]["completed"] and d["onboarding"]["starter_pack"] == "hunter"
    assert any(b["stat"] == "xp" for b in d.get("temp_boosts", []))                 # the specialty's boost really granted


def test_skipping_after_picking_a_pack_just_finishes():
    d = _new_player("intro")
    d["onboarding"]["starter_pack"] = "scout"
    _click("skip")
    assert d["onboarding"]["completed"]


def test_the_scripted_fight_reward_is_paid_once():
    d = _new_player("danger")
    app._onb_after_scripted_danger(U, {"kind": "win"})
    first = d["healing_inv"].get("First Aid Kit", 0)
    d["onboarding"].update(step="danger", completed=False)
    app._onb_after_scripted_danger(U, {"kind": "win"})
    assert d["healing_inv"].get("First Aid Kit", 0) == first == 1


def test_hunters_path_first_step_opens_the_tools_tab():
    step = gd.HUNTERS_PATH_STEPS[0]
    assert step["key"] == "buy_tool" and step["panel"] == "shop_tools"
    d = _new_player("done")
    d["onboarding"]["completed"] = True
    txt = json.dumps(app.build_shop_components(U, "tools"), ensure_ascii=False)
    assert "Slingshot" in txt


def test_mythicals_are_not_held_back_forever_by_the_tutorial_path():
    d = _new_player("done")
    d["onboarding"]["completed"] = True
    d["hunters_path"] = {"completed": False, "rewarded": []}
    d["level"] = 5
    assert app.hunters_path_active(U) and not app.hunters_path_myths_allowed(U)
    d["level"] = app.HUNTERS_PATH_MYTH_LEVEL
    assert app.hunters_path_myths_allowed(U)


def test_the_tour_no_longer_says_selling_gives_xp():
    pages = "\n".join(app._onb_tour_pages())
    assert "turns the bag into ◈ money and XP" not in pages and "XP the moment you catch" in pages


def test_a_scratch_card_never_pays_nothing():
    tt._reset()
    d = tt._mk_user(U, level=100, money=0)
    d["scratch_pad"] = {"cells": [None] * gd.SCRATCH_PAD_GRID_SIZE, "revealed": [False] * gd.SCRATCH_PAD_GRID_SIZE, "found": 0}
    last = None
    for i in range(gd.SCRATCH_PAD_MAX_PICKS):
        last = app.reveal_scratch_pad_cell(U, i)
    assert last["kind"] == "done" and len(last["all_prizes"]) == 1
    assert d["money"] == int(app.SCRATCH_PAD_CONSOLATION_X * app.crate_value_scale(100))
    # a card that DID find something gets no extra consolation
    d["money"] = 0
    cells = [None] * gd.SCRATCH_PAD_GRID_SIZE
    cells[0] = {"type": "money", "amount": 1_000}
    d["scratch_pad"] = {"cells": cells, "revealed": [False] * gd.SCRATCH_PAD_GRID_SIZE, "found": 0}
    for i in range(gd.SCRATCH_PAD_MAX_PICKS):
        last = app.reveal_scratch_pad_cell(U, i)
    assert d["money"] == 1_000 and len(last["all_prizes"]) == 1


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
