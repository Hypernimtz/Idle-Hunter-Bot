"""
"New Message Per Hunt" setting: the Hunt button either updates its own message in
place (default) or posts a fresh one every time.

Runs without pytest:  python tests/test_settings.py
"""
import asyncio
import os
import sys
import tempfile
from types import SimpleNamespace

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_settings_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr   # noqa: E402  (reuses its Harness / FakeInteraction)
import app                # noqa: E402
import backend            # noqa: E402

run = tr.run


def _hunt(uid, *, ephemeral_source=False):
    """Click Hunt for `uid` and return ('edit'|'new', ephemeral_flag_or_None)."""
    seen = []

    async def edit(interaction, comps):
        seen.append(("edit", None))

    async def new(interaction, comps, *, ephemeral=False):
        seen.append(("new", ephemeral))

    with tr.Harness():
        app.smart_update_v2, app.send_v2_followup = edit, new
        it = tr.FakeInteraction(uid, f"hunt:again:{uid}")
        it.message = SimpleNamespace(flags=SimpleNamespace(ephemeral=ephemeral_source))
        run(app._dispatch_component(it))
    return seen[0] if seen else None


def _fresh(uid, **over):
    tr._reset()
    d = tr._mk_user(uid, **over)
    d["tool"] = "Bare Hands"
    return d


def test_default_is_update_in_place():
    _fresh("1")
    assert app.hunt_new_message("1") is False
    assert _hunt("1") == ("edit", None)


def test_new_message_mode_posts_fresh_messages():
    _fresh("2", hunt_new_message=True)
    assert _hunt("2") == ("new", False)
    _fresh("3", hunt_new_message=True)
    assert _hunt("3", ephemeral_source=True) == ("new", True)   # a private panel stays private


def test_stranger_clicking_your_button_still_gets_their_own_new_message():
    _fresh("4")
    tr._mk_user("5")
    seen = []

    async def edit(interaction, comps):
        seen.append("edit")

    async def new(interaction, comps, *, ephemeral=False):
        seen.append(("new", ephemeral))

    with tr.Harness():
        app.smart_update_v2, app.send_v2_followup = edit, new
        it = tr.FakeInteraction("5", "hunt:again:4")
        it.message = SimpleNamespace(flags=SimpleNamespace(ephemeral=True))
        run(app._dispatch_component(it))
    assert seen and seen[0] == ("new", False), seen          # never edits the owner's message


def test_toggle_flips_and_shows_in_settings_panel():
    d = _fresh("6")
    with tr.Harness() as h:
        run(tr._click("6", "settings:toggle:hunt_new_message:6"))
        assert d["hunt_new_message"] is True and app.hunt_new_message("6")
        run(tr._click("6", "settings:toggle:hunt_new_message:6"))
        assert d["hunt_new_message"] is False
        assert h.panels, "settings panel should re-render after a toggle"
    import json
    assert "New Message Per Hunt" in json.dumps(app.build_settings_components("6"), ensure_ascii=False)
    assert "6" in app._dirty_users


def test_auto_opened_crate_is_a_bullet_list():
    import json
    d = _fresh("7", auto_open_crates=True)
    real = app.roll_catch_drops
    app.roll_catch_drops = lambda *a, **k: {"shard": None, "crate": "Epic Crate"}
    try:
        async def go():
            async with app.user_transaction("7"):
                return app.run_hunt("7")
        result = run(go())
    finally:
        app.roll_catch_drops = real
    assert result.get("ok") and result["catches"], result
    assert result["auto_opened"] and not result["crate_drops"]
    comps = app.build_hunt_components("7", result)
    blocks = [c["content"] for c in comps[0]["components"] if c.get("type") == 10]
    block = next(b for b in blocks if "Auto-opened:" in b)
    # one block per crate: "Auto-opened: <crate name>" then a "* " bullet per thing it gave
    first, *bullets = block.split("\n")[:3]
    assert first.endswith("Epic Crate"), first
    assert bullets and bullets[0].startswith("* "), block
    assert "→" not in block and " · " not in block.split("Auto-opened:")[1].split("\n")[0]
    n = len(result["catches"])
    assert block.count("Auto-opened:") == n and n == len(result["auto_opened"])


def test_crate_charm_is_now_shard_charm_and_old_purchases_carry_over():
    import game_data
    assert "Shard Charm" in game_data.SHOP_BOOST_ITEMS and "Crate Charm" not in game_data.SHOP_BOOST_ITEMS
    d = _fresh("8", gems=1000, shop_bought={"Crate Charm": 3, "Lucky Charm": 1}, boosts={"luck": 5, "sell": 0, "xp": 0, "crate_luck": 3})
    assert app.shop_bought_count(d, "Shard Charm") == 3 and "Crate Charm" not in d["shop_bought"]
    assert d["shop_bought"]["Lucky Charm"] == 1
    with tr.Harness():
        run(tr._click("8", "shop:buy:Crate Charm:8"))      # a button from before the rename still works
    assert d["shop_bought"]["Shard Charm"] == 4 and d["boosts"]["crate_luck"] == 4
    import json
    assert "Shard Charm" in json.dumps(app.build_shop_components("8", "boosts"), ensure_ascii=False)


def test_daily_panel_reminds_you_to_vote():
    import json
    d = _fresh("9")
    d["vote_cd"] = 0
    ready = app.build_daily_components("9")
    blob = json.dumps(ready, ensure_ascii=False)
    assert "Vote reward ready" in blob and "vote:claim:9" in blob and app.VOTE_URL in blob
    row = next(c for c in ready[0]["components"] if c.get("type") == 1)["components"]
    assert len(row) <= 5 and sum(1 for b in row if b["style"] == 5) == 1
    d["vote_cd"] = __import__("time").time() + 3600       # already claimed -> just a countdown, no buttons
    waiting = app.build_daily_components("9")
    blob = json.dumps(waiting, ensure_ascii=False)
    assert "Next vote reward" in blob and "vote:claim" not in blob and app.VOTE_URL not in blob
    claimed = app.build_daily_components("9", claimed=True, reward_type="money", reward_amt=5, streak=2)
    assert "Daily Claimed" in json.dumps(claimed, ensure_ascii=False)


def test_intro_explains_the_bot_and_the_tour_walks_through_it():
    import json
    d = _fresh("12", onboarding={"version": 2, "completed": False, "step": "intro", "starter_pack": None})
    intro = json.dumps(app.build_onboarding_components("12"), ensure_ascii=False)
    for needle in ("hunting RPG", "regions", "Mythical creatures", "Hunting Camp", "Tribes", "Quick Tour", "Track It"):
        assert needle in intro, needle
    assert f"{len(app.MYTHIC_CREATURES)} legendary" in intro
    pages = app._onb_tour_pages()
    assert len(pages) == 4 and all(len(p) < 1800 for p in pages)
    with tr.Harness() as h:
        seen = []

        async def grab(interaction, comps):
            seen.append(json.dumps(comps, ensure_ascii=False))
        app.smart_update_v2 = grab
        run(tr._click("12", "onb:tour:0:12".rsplit(":", 1)[0] + ":12"))
        run(tr._click("12", "onb:tour:2:12"))
        assert "Quick tour · 3/4" in seen[-1] and "Hunting Camp" in seen[-1]
        run(tr._click("12", "onb:tour:exit:12"))
        assert "Quick Tour" in seen[-1] and "IDLE HUNTER" in seen[-1]
        assert d["onboarding"]["step"] == "intro"          # browsing the tour doesn't advance the flow
        run(tr._click("12", "onb:track:12"))
        assert d["onboarding"]["step"] == "catch"


def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(tr._ensure_db())
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
        run(backend.close_databases())
    except Exception:
        pass
    if failed:
        print(f"{failed} FAILED")
        sys.exit(1)
    print(f"all {len(_all_tests())} tests passed")
    sys.exit(0)
