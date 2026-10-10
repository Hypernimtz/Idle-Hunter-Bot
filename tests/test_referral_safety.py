"""
Referral payouts are crash-safe and milestone-exact: a crash between steps can neither lose a reward (it is
retried) nor pay it twice (a marker saved with the reward stops the retry), simultaneous qualifications get
their own milestones, and a referred account must be old enough as well as active on two UTC dates.

Runs without pytest:  python tests/test_referral_safety.py
"""
import asyncio
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_refsafe_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import backend                     # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
GEMS = gd.REFERRAL_QUALIFY_GEMS


async def _pair(a, b, joined="2020-01-01"):
    tt._mk_user(a, level=50, joined_date="2020-01-01")
    tt._mk_user(b, level=5, joined_date=joined)
    code = await app._referral_get_code(a)
    ok, msg = await app._referral_bind(b, code)
    assert ok, msg
    d = app.data[b]
    d["level"] = 30
    d["stats"].update(lifetime_hunts=80, active_days=3)
    d.pop("_ref_done", None)


def test_a_crash_after_the_reward_is_saved_does_not_pay_twice():
    async def body():
        await tt._ensure_db()
        tt._reset()
        A, B = "9101", "9102"
        await _pair(A, B)
        g0 = (app.data[A]["gems"], app.data[B]["gems"])
        await app._referral_check_qualified(B)
        assert (app.data[A]["gems"], app.data[B]["gems"]) == (g0[0] + GEMS, g0[1] + GEMS)
        # simulate: the process died after saving both rewards but before the DB flags were written
        await backend._pool.execute("UPDATE referrals SET referred_paid = 0, referrer_paid = 0 WHERE referred_id = ?", (B,))
        await backend._pool.commit()
        assert await app._referral_recover() >= 1
        assert (app.data[A]["gems"], app.data[B]["gems"]) == (g0[0] + GEMS, g0[1] + GEMS)      # not paid again
        row = await backend.referral_delivery(B)
        assert row["referred_paid"] and row["referrer_paid"]
    run(body())


def test_a_crash_before_the_reward_is_saved_is_retried_once():
    async def body():
        await tt._ensure_db()
        tt._reset()
        A, B = "9111", "9112"
        await _pair(A, B)
        g0 = (app.data[A]["gems"], app.data[B]["gems"])
        # qualification was recorded, then the process died before anything was paid
        claim = await backend.referral_qualify(B)
        assert claim and claim["qual_seq"] == 1
        assert app.data[B]["gems"] == g0[1]
        assert await app._referral_recover() >= 1
        assert (app.data[A]["gems"], app.data[B]["gems"]) == (g0[0] + GEMS, g0[1] + GEMS)
        await app._referral_recover()                                                           # a second restart: nothing more
        assert (app.data[A]["gems"], app.data[B]["gems"]) == (g0[0] + GEMS, g0[1] + GEMS)
    run(body())


def test_simultaneous_qualifications_each_get_their_own_milestone():
    async def body():
        await tt._ensure_db()
        tt._reset()
        A = "9121"
        tt._mk_user(A, level=50, joined_date="2020-01-01")
        kids = [f"913{i}" for i in range(5)]
        code = await app._referral_get_code(A)
        for k in kids:
            tt._mk_user(k, level=5, joined_date="2020-01-01")
            assert (await app._referral_bind(k, code))[0]
            app.data[k]["level"] = 30
            app.data[k]["stats"].update(lifetime_hunts=80, active_days=3)
            app.data[k].pop("_ref_done", None)
        g0 = app.data[A]["gems"]
        await asyncio.gather(*[app._referral_check_qualified(k) for k in kids])
        seqs = sorted([(await backend.referral_delivery(k))["qual_seq"] for k in kids])
        assert seqs == [1, 2, 3, 4, 5]                                                          # no duplicates, no gaps
        expect = 5 * GEMS + sum(m.get("gems", 0) for n, m in gd.REFERRAL_MILESTONES.items() if n <= 5)
        assert app.data[A]["gems"] - g0 == expect, (app.data[A]["gems"] - g0, expect)           # each milestone exactly once
        assert "recruiter" in app.data[A].get("special_badges", [])
    run(body())


def test_a_brand_new_account_cannot_qualify_even_with_two_dates_and_50_hunts():
    tt._reset()
    d = tt._mk_user("9141", level=30, joined_date=time.strftime("%Y-%m-%d", time.gmtime()))
    d["stats"].update(lifetime_hunts=80, active_days=3)
    assert not app._referral_qualifies(d)
    d["joined_date"] = "2020-01-01"
    assert app._referral_qualifies(d)


def test_legacy_paid_referrals_are_not_paid_again():
    async def body():
        await tt._ensure_db()
        tt._reset()
        A, B = "9151", "9152"
        await _pair(A, B)
        # an old-style row: claimed under the previous scheme, no sequence number
        await backend._pool.execute(
            "UPDATE referrals SET reward_claimed = 1, qualified_at = datetime('now'), qual_seq = NULL, "
            "referred_paid = 1, referrer_paid = 1 WHERE referred_id = ?", (B,))
        await backend._pool.commit()
        g0 = (app.data[A]["gems"], app.data[B]["gems"])
        await app._referral_check_qualified(B)
        await app._referral_recover()
        assert (app.data[A]["gems"], app.data[B]["gems"]) == g0
    run(body())


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
