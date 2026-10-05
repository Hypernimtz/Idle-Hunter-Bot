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
