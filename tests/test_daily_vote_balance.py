"""
Daily rewards & voting: no vote is ever paid without verification, a vote must be recent even for a
first claim, the first vote claim of a day pays an Epic Crate and a repeat a Rare, the streak payout
bonus tapers after 100 days, the level-1200 jump is smoothed, and the daily preview shows the real payout.

Runs without pytest:  python tests/test_daily_vote_balance.py
"""
import asyncio
import json
import os
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_dailyvote_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "7801"


def _click(cid):
    it = tr.FakeInteraction(U, cid)
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    return " ".join(h.ephemerals)


class _Patch:
    """Temporarily set DBL_TOKEN and a fake vote checker; records the since_ts it was asked about."""
    def __init__(self, token, result):
        self.token, self.result, self.since = token, result, []

    def __enter__(self):
        self.old = (app.DBL_TOKEN, app.check_dbl_recent_vote)
        app.DBL_TOKEN = self.token

        async def fake(uid, since_ts, bot_id=None):
            self.since.append(since_ts)
            return self.result
        app.check_dbl_recent_vote = fake
        return self

    def __exit__(self, *a):
        app.DBL_TOKEN, app.check_dbl_recent_vote = self.old


def test_votes_are_never_paid_without_a_token():
    tt._reset()
    d = tt._mk_user(U, level=100, money=0, gems=0)
    with _Patch("", True):
        out = _click(f"vote:claim:{U}")
    assert "paused" in out
    assert d["money"] == 0 and d["gems"] == 0 and not d.get("crate_inv") and d["vote_cd"] <= time.time()
    with _Patch("", True):
        txt = json.dumps(app.build_vote_components(U), ensure_ascii=False)
        daily = json.dumps(app.build_daily_components(U), ensure_ascii=False)
    assert "paused" in txt and "vote:claim" not in txt and "vote:claim" not in daily


def test_first_vote_each_day_pays_epic_then_rare_and_only_recent_votes_count():
    tt._reset()
    d = tt._mk_user(U, level=100, money=0, gems=0)
    with _Patch("tok", True) as p:
        _click(f"vote:claim:{U}")
        assert d["crate_inv"].get(gd.VOTE_REWARD_CRATE) == 1 and not d["crate_inv"].get(gd.VOTE_REWARD_CRATE_REPEAT)
        # a first claim never accepts a vote older than the claim window
        assert p.since[0] >= time.time() - gd.VOTE_CLAIM_WINDOW_HOURS * 3600 - 5
        d["vote_cd"] = 0                                             # 12h later, same UTC day
        _click(f"vote:claim:{U}")
        assert d["crate_inv"].get(gd.VOTE_REWARD_CRATE) == 1 and d["crate_inv"].get(gd.VOTE_REWARD_CRATE_REPEAT) == 1
        # a later claim only counts votes since the previous claim
        assert p.since[1] >= time.time() - gd.VOTE_CLAIM_WINDOW_HOURS * 3600 - 5
        d["vote_cd"] = 0
        d["vote_day"] = {"tag": "1999-01-01", "n": 9}                # a new day: Epic again
        _click(f"vote:claim:{U}")
        assert d["crate_inv"].get(gd.VOTE_REWARD_CRATE) == 2


def test_an_unverified_vote_pays_nothing():
    tt._reset()
    d = tt._mk_user(U, level=100, money=0)
    with _Patch("tok", False):
        out = _click(f"vote:claim:{U}")
    assert "haven't seen your vote" in out and d["money"] == 0 and not d.get("crate_inv")
    with _Patch("tok", None):
        assert "Couldn't reach" in _click(f"vote:claim:{U}")


def test_streak_payout_bonus_tapers_but_the_streak_still_counts():
    assert app.daily_streak_bonus(0) == 0
    assert app.daily_streak_bonus(30) == 0.30 and app.daily_streak_bonus(100) == 1.0
    assert 1.0 < app.daily_streak_bonus(200) < app.daily_streak_bonus(365) < 1.75 + 1e-9   # still grows, slowly
    assert app.daily_streak_bonus(365) < 3.65                                              # was +365%
    assert app.daily_streak_bonus(10_000) == gd.DAILY_STREAK_MAX_BONUS
    assert app.daily_multiplier(365, 10) < 1 + 3.65 + 1.0                                  # was 5.65x
    assert app.daily_multiplier(0, 40) == 1 + app.PRESTIGE_DAILY_MAX * 0.1


def test_the_level_1200_daily_jump_is_smoothed():
    a, b = gd.get_daily_tier(1000), gd.get_daily_tier(1200)
    avg = lambda t: (t["money_min"] + t["money_max"]) / 2
    assert avg(b) / avg(a) < 3 and b["money_max"] <= 20_000_000 and b["gems_max"] <= 80


def test_daily_preview_shows_the_real_multiplier_and_payout():
    tt._reset()
    d = tt._mk_user(U, level=300, prestige=2)
    d["daily_streak"], d["last_daily_date"] = 49, ""
    txt = json.dumps(app.build_daily_components(U), ensure_ascii=False)
    mult = app.daily_multiplier(1, 2)             # last date empty -> a fresh streak of 1
    assert f"x{mult:.2f}" in txt and "prestige +20%" in txt
    tier = gd.get_daily_tier(300)
    assert f"{int(tier['money_max'] * mult):,}" in txt


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
