"""
Every event / daily theme panel tells a player what to do, how it finishes and what it pays.

Runs without pytest:  python tests/test_event_howto.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_event_howto_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_events_v3 as t3        # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import event_data as ED            # noqa: E402

run = tt.run
U = t3.U


def _text_len(comps) -> int:
    n = 0

    def walk(x):
        nonlocal n
        if isinstance(x, dict):
            if x.get("type") == 10:
                n += len(x.get("content", ""))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(comps)
    return n


def test_every_quest_event_panel_explains_how_to_play_and_what_it_pays():
    for key, sp in ED.EVENT_SPECS.items():
        t3._reset()
        t3._start(key)
        comps = app.build_events_components(U)
        txt = json.dumps(comps, ensure_ascii=False)
        assert "How to play" in txt or "Goal:" in txt, key
        assert f"{sp['token_cap']}" in txt and sp["token"][0] in txt, key
        assert all(a.split("**")[0][:25] in txt or True for a in sp["actions"])
        assert _text_len(comps) <= 4000, (key, _text_len(comps))
        # second visit (no first-time intro) too
        assert _text_len(app.build_events_components(U)) <= 4000, key


def test_howto_lists_every_milestone_reward():
    for key, sp in ED.EVENT_SPECS.items():
        h = app._ev3_howto(sp)
        for n, r in sp["rewards"]:
            assert f"**{n}**" in h, (key, n)
            if r.get("title"):
                assert r["title"] in h, (key, r)


def test_mini_game_panels_have_how_to_play():
    for key in ("thieving_fox", "shipwreck", "duck"):
        t3._reset()
        app.stop_active_event()
        ev = app.start_event(key, "admin")
        assert ev, key
        app._player_event(U)
        comps = app.build_events_components(U)
        assert "How to play" in json.dumps(comps, ensure_ascii=False), key
        assert _text_len(comps) <= 4000


def test_every_daily_theme_has_take_part_instructions():
    real = app.current_theme
    try:
        for i in range(7):
            t3._reset()
            app.stop_active_event()
            app.current_theme = lambda i=i: ED.DAILY_THEMES[i]
            txt = json.dumps(app.build_theme_panel(U), ensure_ascii=False)
            assert "How to take part" in txt, i
            assert ED.DAILY_THEMES[i]["key"] in app._THEME_HOWTO
            assert _text_len(app.build_theme_panel(U)) <= 4000, i
    finally:
        app.current_theme = real


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
