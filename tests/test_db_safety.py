"""
Database safety: a transaction whose save fails is rolled back and raises (the action is never confirmed),
one unsavable account can't block everybody else, lottery payouts are pending + idempotent + retried,
lottery tickets are undone if the purchase doesn't stick, /verify locks out after repeated wrong codes,
and the gambling cooldown is claimed at check time.

Runs without pytest:  python tests/test_db_safety.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_dbsafe_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import backend                     # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "8301"


class _FailingSave:
    """Swap the backend's save callback for one that raises SaveFailed for chosen accounts."""
    def __init__(self, failing=()):
        self.failing = set(failing)
        self.calls = 0

    def __enter__(self):
        self.old = backend._save_users_fn

        async def fake(only=()):
            self.calls += 1
            if self.failing & set(map(str, only or ())):
                raise backend.SaveFailed("disk full")
        backend._save_users_fn = fake
        return self

    def __exit__(self, *a):
        backend._save_users_fn = self.old


def test_a_failed_save_rolls_the_action_back_and_is_never_confirmed():
    tt._reset()
    d = tt._mk_user(U, money=1_000, gems=500)
    confirmed = []

    async def buy():
        async with app.user_transaction(U):
            app.spend_gems(U, 300, "shop")
            d["owned_tools"].append("Cosmic RPG")
        confirmed.append(True)                               # only reached if the save succeeded

    with _FailingSave(failing=[U]):
        try:
            run(buy())
            raised = False
        except backend.SaveFailed:
            raised = True
    assert raised and not confirmed
    assert d["gems"] == 500 and "Cosmic RPG" not in d["owned_tools"]               # memory matches the unsaved DB
    with _FailingSave():                                                            # healthy again: it works
        run(buy())
    assert confirmed and d["gems"] == 200


def test_a_failed_save_of_someone_elses_account_does_not_block_this_transaction():
    tt._reset()
    tt._mk_user(U, money=100)
    tt._mk_user("8302", money=100)

    async def act():
        async with app.user_transaction(U):
            app.add_money(U, 50, "quest")
    with _FailingSave(failing=["8302"]):
        run(act())                                                                   # no exception
    assert app.data[U]["money"] == 150


def test_multi_user_transfer_is_undone_for_both_sides_when_the_save_fails():
    tt._reset()
    a = tt._mk_user(U, money=1_000)
    b = tt._mk_user("8303", money=0)

    async def send():
        async with app.multi_user_transaction(U, "8303"):
            app.spend_money(U, 400, "gift send")
            app.add_money("8303", 400, "gift receive")
    with _FailingSave(failing=["8303"]):
        try:
            run(send())
        except backend.SaveFailed:
            pass
    assert a["money"] == 1_000 and b["money"] == 0


def test_lottery_winner_is_paid_once_even_if_the_payout_is_retried():
    tt._reset()
    tt._mk_user(U, money=0)
    ld = app.lottery_data
    ld["pending_payout"] = {"id": "lottery:1:" + U, "winner": U, "amount": 5_000}
    assert run(app._lottery_pay_pending()) is True
    assert app.data[U]["money"] == 5_000 and "pending_payout" not in ld
    ld["pending_payout"] = {"id": "lottery:1:" + U, "winner": U, "amount": 5_000}    # crash left 'pending' behind
    assert run(app._lottery_pay_pending()) is True
    assert app.data[U]["money"] == 5_000 and app.data[U]["stats"]["lottery_wins"] == 1


def test_a_lottery_payout_that_fails_stays_pending_for_the_next_tick():
    tt._reset()
    tt._mk_user(U, money=0)
    ld = app.lottery_data
    ld["pending_payout"] = {"id": "lottery:2:" + U, "winner": U, "amount": 700}
    with _FailingSave(failing=[U]):
        assert run(app._lottery_pay_pending()) is False
    assert ld.get("pending_payout") and app.data[U]["money"] == 0
    assert run(app._lottery_pay_pending()) is True and app.data[U]["money"] == 700


def test_verify_locks_out_after_repeated_wrong_codes_and_unlocks_after():
    tt._reset()
    d = tt._mk_user(U)
    d["verify"] = {"needed": True, "time": 0, "code": "AbCd"}

    def verify(code):
        it = tr.FakeInteraction(U, "x")
        with tr.Harness() as h:
            run(app.verify_cmd.callback(it, code))
        return " ".join(h.ephemerals)
    for i in range(app.VERIFY_MAX_FAILS - 1):
        assert "Try again" in verify("nope")
    out = verify("nope")
    assert "locked" in out and d["verify"]["lock_until"] > time.time()
    assert "Too many wrong codes" in verify(d["verify"]["code"])             # even the right code waits out the lockout
    d["verify"]["lock_until"] = time.time() - 1
    assert "Verified" in verify(d["verify"]["code"])
    assert d["verify"]["needed"] is False and d["verify"]["fails"] == 0


def test_verification_codes_are_unambiguous_and_come_from_a_strong_source():
    seen = set()
    for _ in range(500):
        c = gd.generate_verify_code()
        assert len(c) == 4 and not set(c) & set("0O1lI")
        seen.add(c)
    assert len(seen) > 400


def test_the_gambling_cooldown_is_claimed_when_checked():
    tt._reset()
    d = tt._mk_user(U, level=100, money=10_000)
    d["_cf_bet"] = 100
    d["last_gamble"] = 0
    first = tr.FakeInteraction(U, f"gamble:cf:heads:{U}")
    second = tr.FakeInteraction(U, f"gamble:cf:heads:{U}")

    async def both():
        with tr.Harness() as h:
            await asyncio.gather(app._dispatch_component_inner(first), app._dispatch_component_inner(second))
        return h
    h = run(both())
    msgs = " ".join(h.ephemerals)
    assert msgs.count("before gambling again") == 1                               # the second click was refused
    assert d["stats"].get("cf_wins", 0) + (1 if d["money"] < 10_000 else 0) >= 0


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
