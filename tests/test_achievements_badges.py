"""
Achievements & badges: Game Master is built from the five gambling badges (and never from itself), Ammo
Variety and Events Completer are earnable, lifetime hunting badges survive prestige, early money
achievements are starter-sized, the Nuke Launcher doesn't block "Buy All Tools", and the empty Gamble
track is hidden.

Runs without pytest:  python tests/test_achievements_badges.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_ach_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import test_events_v3 as t3        # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "8201"


class _Http:
    async def request(self, *a, **k):
        return {}


class _Client:
    http = _Http()


class _It:
    application_id = 1
    token = "t"
    client = _Client()


def _check(uid=U):
    run(app.check_achievements_and_badges(_It(), uid))     # (the shared Harness stubs this function out)


def _set_gamble(d, stat_value):
    for badge in gd.GAMBLING_BADGES:
        d["stats"][gd.BADGES[badge]["stat"]] = stat_value


def test_game_master_gold_needs_all_five_gambling_badges_at_gold():
    tt._reset()
    d = tt._mk_user(U, level=100)
    _set_gamble(d, gd.BADGES["bj_dealer"]["gold"])
    d["stats"]["slots_wins"] = 0                                  # one badge missing
    _check()
    assert d["badges"]["game_master"]["tier"] == 0
    d["stats"]["slots_wins"] = gd.BADGES["slots_machine"]["gold"]
    _check()
    assert d["badges"]["game_master"]["tier"] == 1 and app.get_badge_stat(U, "game_master") == 1


def test_game_master_platinum_is_reachable_and_not_circular():
    tt._reset()
    d = tt._mk_user(U, level=100)
    _set_gamble(d, gd.BADGES["bj_dealer"]["plat"])
    _check()
    assert all(d["badges"][k]["tier"] == 2 for k in gd.GAMBLING_BADGES)
    assert d["badges"]["game_master"]["tier"] == 2                 # with every OTHER badge still at zero
    assert app.get_badge_stat(U, "game_master") == 2               # progress shows real progress, not a constant 0


def test_game_master_does_not_come_from_finishing_every_achievement():
    tt._reset()
    d = tt._mk_user(U, level=100)
    for k, tiers in gd.ACHIEVEMENTS.items():
        if tiers:
            d["achievements"][k] = {"claimed_up_to": len(tiers) - 1}
    _check()
    assert d["badges"].get("game_master", {}).get("tier", 0) == 0


def test_ammo_variety_is_earned_by_firing_every_family():
    tt._reset()
    d = tt._mk_user(U, level=100)
    fams = list(gd.AMMO_VARIETY_TYPES)
    assert "nuke_only" not in fams and len(fams) == 7
    for fam in fams[:-1]:
        name = next(n for n, a in gd.AMMO.items() if a["ammo_type"] == fam)
        app._note_ammo_type(U, name)
    _check()
    assert d["badges"]["ammo_variety"]["tier"] == 0
    last = next(n for n, a in gd.AMMO.items() if a["ammo_type"] == fams[-1])
    app._note_ammo_type(U, last)
    _check()
    assert d["badges"]["ammo_variety"]["tier"] == 1


def test_events_completed_counts_a_finished_event_once():
    t3._reset()
    d = app.data[t3.U]
    ev, spec = t3._start("meteor")
    before = d["stats"].get("events_completed", 0)
    app._ev3_award(t3.U, spec, spec["token_cap"] - 1)
    assert d["stats"].get("events_completed", 0) == before            # not yet
    app._ev3_award(t3.U, spec, 5)
    assert d["stats"]["events_completed"] == before + 1
    app._ev3_award(t3.U, spec, 5)
    assert d["stats"]["events_completed"] == before + 1               # only once
    d["stats"]["events_completed"] = gd.BADGES["events_completer"]["gold"] - 1
    d["stats"]["events_completed"] += 1
    tt._mk_user  # (badge itself is awarded by the checker)
    _check(t3.U)
    assert d["badges"]["events_completer"]["tier"] == 1


def test_legendary_hunter_uses_lifetime_catches_so_prestige_cannot_erase_progress():
    tt._reset()
    d = tt._mk_user(U, level=1000, money=2_000_000_000)
    d["total_caught"] = 0
    d["stats"]["lifetime_caught"] = gd.BADGES["legendary_hunter"]["gold"]
    _check()
    assert d["badges"]["legendary_hunter"]["tier"] == 1
    assert app.achievement_sources(U)["animals_caught"] == gd.BADGES["legendary_hunter"]["gold"]


def test_early_money_achievements_are_starter_sized():
    first = {k: gd.ACHIEVEMENTS[k][0] for k in ("daily_streak", "crates_opened", "animals_caught", "ammo_used")}
    for k, (thr, rewards) in first.items():
        money = sum(a for t, a in rewards if t == "money")
        assert money <= 10_000, (k, money)                            # was 10k / 100k / 50k / 100k
    assert gd.ACHIEVEMENTS["daily_streak"][0][1][0][1] <= 1_000
    assert gd.ACHIEVEMENTS["crates_opened"][0][1][0][1] <= 5_000
    # big late milestones are untouched
    assert gd.ACHIEVEMENTS["crates_opened"][-1][1][0][1] >= 10_000_000_000


def test_nuke_launcher_does_not_block_buy_all_tools():
    tt._reset()
    d = tt._mk_user(U, level=100)
    tools = app._ach_tools()
    assert "Nuke Launcher" not in tools and len(tools) == len(gd.TOOLS) - 1
    d["owned_tools"] = list(tools)
    d["stats"]["tools_used"] = list(tools)
    src = app.achievement_sources(U)
    assert src["tools_bought_all"] == 1 and src["tools_used_all"] == 1


def test_badge_targets_are_reachable_and_empty_gamble_track_is_hidden():
    for k in ("legendary_hunter", "ammo_master"):
        assert gd.BADGES[k]["plat"] <= 1_000_000
    assert all(gd.BADGES[k]["plat"] <= 10_000 for k in gd.GAMBLING_BADGES)
    assert gd.BADGES["lottery_winner"]["plat"] <= 50
    tt._reset()
    tt._mk_user(U, level=100)
    pages = "\n".join(app.build_achievements_pages(U))
    assert "Coming soon" not in pages and "Gamble" not in pages


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
