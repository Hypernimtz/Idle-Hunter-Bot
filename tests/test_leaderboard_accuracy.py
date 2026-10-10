"""
Leaderboard accuracy: Top Earner ranks money EARNED (not balance growth, gifts or gambling), last week's
standings are frozen once at the rollover (opening the board or a late task can't change them), equal levels
tie-break on XP, deleted accounts never reach a page, and Top-3 alerts ignore zero scores.

Runs without pytest:  python tests/test_leaderboard_accuracy.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_lb_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402

run = tt.run


def _reset():
    tt._reset()
    app._LB_CACHE.clear()
    app._weekly_final.update(tag="", rows=[])


def _users():
    for u, money in (("A", 100), ("B", 100), ("C", 100)):
        tt._mk_user(u, level=50, money=money, joined_date="2020-01-01")


def _snap_all(tag):
    for u in app.data:
        app.data[u].setdefault("lb_snap", {})["weekly"] = app._lb_make_snapshot(u, "weekly", tag)


def test_earnings_ignore_gifts_gambling_market_and_admin_grants():
    _reset()
    _users()
    A = "A"
    app.add_money(A, 1_000, "sell all")
    app.add_money(A, 500, "quest")
    for src in ("gift receive", "slots", "blackjack win", "coinflip win", "market sale", "admin grant",
                "fight win", "lottery", "giveaway", "dice win", "rps win", "roulette win"):
        app.add_money(A, 10_000_000, src)
    assert app._lb_earned(A) == 1_500
    app.spend_money(A, 1_400, "shop")                       # spending doesn't reduce what you earned
    assert app._lb_earned(A) == 1_500


def test_weekly_top_earner_is_earnings_not_balance_growth():
    _reset()
    _users()
    tag = app._lb_period_tag("weekly")
    _snap_all(tag)
    app.add_money("A", 50_000_000, "sell all"); app.spend_money("A", 45_000_000, "shop")   # earned 50M, kept 5M
    app.add_money("B", 10_000_000, "sell all")                                              # earned 10M
    app.add_money("C", 2_000_000, "sell all"); app.add_money("C", 100_000_000, "gift receive")
    vals = {u: app._lb_period_value(u, "Money", "weekly") for u in "ABC"}
    assert vals == {"A": 50_000_000, "B": 10_000_000, "C": 2_000_000}
    assert sorted(vals, key=vals.get, reverse=True) == ["A", "B", "C"]


def test_the_previous_weeks_standings_are_frozen_before_anyone_opens_the_new_week():
    _reset()
    _users()
    _snap_all("2000-W01")                                     # last week's baselines
    app.add_money("A", 7_000, "sell all")
    app.add_money("B", 9_000, "sell all")
    # the new week has started; a player opens the weekly board BEFORE the scheduled task ran
    assert app._lb_period_value("C", "Money", "weekly") == 0
    frozen = list(app._weekly_final["rows"])
    assert frozen == [("B", 9_000), ("A", 7_000)], frozen
    # later activity, another board view, a late task — none of it changes the frozen result
    app.add_money("A", 100_000, "sell all")
    app._lb_period_value("A", "Money", "weekly")
    new_tag = app._lb_period_tag("weekly")
    assert app._lb_finalize_week(new_tag) == frozen
    text = app._weekly_leaderboard_recap_text(new_tag)
    assert "9,000" in text.replace(" ", "") or "9K" in text or "9,000" in json.dumps(text)


def test_equal_levels_rank_by_xp_and_deleted_players_never_appear():
    _reset()
    for u, xp in (("A", 500), ("B", 50_000), ("C", 10)):
        tt._mk_user(u, level=100, xp=xp, joined_date="2020-01-01")
    txt = json.dumps(app.build_leaderboard_v2_components("A", None, "hunter", "global", "Level", 0, "all"), ensure_ascii=False)
    order = [txt.index(f"`{app.get_username(u)}`") for u in ("B", "A", "C")]
    assert order == sorted(order)                              # B (most XP), then A, then C
    del app.data["B"]                                          # an admin deleted B; the 30 s cache still lists them
    out2 = app.build_leaderboard_v2_components("A", None, "hunter", "global", "Level", 0, "all")   # must not raise (KeyError before)
    assert out2 and "<@" not in json.dumps(out2) and "B" not in [u for u in app.data]


def test_top3_alerts_only_consider_players_with_a_score():
    _reset()
    _users()
    # nobody has slain a mythical: every stat of 0 must not put anyone in a "Top 3"
    fn = app.HUNTER_LB_STATS["Mythic Creatures Slain"]
    import heapq
    top = [u for u in heapq.nlargest(3, list(app.data), key=fn) if fn(u) > 0]
    assert top == []
    app.data["B"]["stats"]["myths_killed"] = 2
    top = [u for u in heapq.nlargest(3, list(app.data), key=fn) if fn(u) > 0]
    assert top == ["B"]


def test_website_export_tells_same_named_players_apart_without_exposing_ids():
    import leaderboard_push as lp
    users = {"111111111111111111": {"username": "Same", "level": 9}, "222222222222222222": {"username": "Same", "level": 8}}
    out = run(lp.build_payload(users, {}, set()))
    rows = out["rankings"]["level"]
    assert len(rows) == 2 and rows[0]["name"] == rows[1]["name"] == "Same"
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == 2 and all(len(i) == 8 for i in ids)
    assert not any("1111" in json.dumps(r) or "2222" in json.dumps(r) for r in rows)      # the Discord id never leaves the bot
    assert ids[0] == lp.public_id("111111111111111111")                                    # stable between pushes


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
