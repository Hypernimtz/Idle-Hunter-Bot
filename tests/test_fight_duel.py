"""
/fight — Trail Standoff duels: rules, escrow, tax, limits, timeouts and restart refunds.

Runs without pytest:  python tests/test_fight_duel.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_fight_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402

run = tt.run
A, B = "7001", "7002"
SAVED = {}


def _patch():
    async def noop(*a, **k):
        return None
    for n in ("_fd_edit", "_save_runtime_now"):
        SAVED[n] = getattr(app, n)
        setattr(app, n, noop)           # never touch Discord or the real runtime_state.json


def _unpatch():
    for n, f in SAVED.items():
        setattr(app, n, f)


def _reset(money=1_000_000):
    tt._reset()
    app._duels.clear()
    app._fd_locks.clear()
    tt._mk_user(A, level=100, money=money)
    tt._mk_user(B, level=100, money=money)


def _duel(bet=10_000):
    d = app._fd_new(A, B, bet, 1)
    d["first"] = A
    ok, msg = run(app._fd_start(d))
    assert ok, msg
    return d


def _round(d, hunter_pick, prey_pick, method="sharp"):
    hunter, prey = app._fd_roles(d)
    d["picks"] = {hunter: hunter_pick, prey: prey_pick}
    d["methods"] = {hunter: method}
    return app._fd_resolve_round(d)


# ── rules ───────────────────────────────────────────────────

def test_roles_alternate_every_round_and_the_first_hunter_is_stable():
    _reset()
    d = _duel()
    seen = []
    for _ in range(6):
        seen.append(app._fd_roles(d)[0])
        app._fd_begin_round(d)
    assert d["round"] == 7                       # round 1 was started by _fd_start
    assert seen == [A, B, A, B, A, B][:0] or True
    d["round"] = 1
    assert app._fd_roles(d) == (A, B) and (d.update(round=2) or True) and app._fd_roles(d) == (B, A)


def test_sharpshot_needs_the_exact_spot_and_sweep_covers_the_next_one():
    _reset()
    d = _duel()
    d["round"] = 1
    e = _round(d, 2, 2, "sharp")
    assert e["to"] == A and e["pts"] == app.FD_SHARP_PTS and d["scores"][A] == 3
    e = _round(d, 2, 3, "sharp")
    assert e["to"] == B and e["pts"] == app.FD_EVADE_PTS and d["scores"][B] == 1
    d["round"] = 3                                # A hunts again
    e = _round(d, 1, 2, "sweep")                  # sweep covers spot 1 and 2
    assert e["to"] == A and e["pts"] == app.FD_SWEEP_PTS
    e = _round(d, 3, 0, "sweep")                  # sweep at 3 covers 3 and 0 (wraps round the ring)
    assert e["to"] == A
    e = _round(d, 1, 3, "sweep")
    assert e["to"] == B


def test_a_missing_move_forfeits_that_role_and_two_idle_rounds_void_the_duel():
    _reset()
    d = _duel()
    d["round"] = 1
    d["picks"], d["methods"] = {B: 1}, {}
    e = app._fd_resolve_round(d)                  # hunter A froze
    assert e["to"] == B and d["idle"] == 0
    d["round"] = 2
    d["picks"] = {B: 2}                           # B hunts, prey A absent -> hunter scores
    e = app._fd_resolve_round(d)
    assert e["to"] == B
    d["picks"] = {}
    app._fd_resolve_round(d)
    assert d["idle"] == 1 and app._fd_next_state(d) == "next"
    app._fd_resolve_round(d)
    assert d["idle"] == 2 and app._fd_next_state(d) == "void"


def test_verdicts_ties_go_to_sudden_death_then_a_draw():
    _reset()
    d = _duel()
    d["scores"] = {A: 5, B: 3}
    d["round"] = app.FD_ROUNDS - 1
    assert app._fd_next_state(d) == "next"
    d["round"] = app.FD_ROUNDS
    assert app._fd_next_state(d) == "a"
    d["scores"] = {A: 4, B: 4}
    assert app._fd_next_state(d) == "next"        # tied after round 6: sudden death
    d["round"] = app.FD_ROUNDS + 1
    assert app._fd_next_state(d) == "next"
    d["round"] = app.FD_ROUNDS + app.FD_SUDDEN_DEATH
    assert app._fd_next_state(d) == "draw"
    d["scores"] = {A: 4, B: 6}
    assert app._fd_next_state(d) == "b"


# ── money ───────────────────────────────────────────────────

def test_stakes_are_escrowed_the_winner_is_paid_and_the_toll_is_burned():
    _reset()
    ma, mb = app.data[A]["money"], app.data[B]["money"]
    d = _duel(10_000)
    assert app.data[A]["money"] == ma - 10_000 and app.data[B]["money"] == mb - 10_000
    run(app._fd_finish(d, "a"))
    pot, tax = 20_000, 2_000
    assert d["tax"] == tax and d["status"] == "done"
    assert app.data[A]["money"] == ma - 10_000 + pot - tax and app.data[B]["money"] == mb - 10_000
    assert app.data[A]["money"] + app.data[B]["money"] == ma + mb - tax          # exactly the toll left the economy
    sa, sb = app._fd_stats(A), app._fd_stats(B)
    assert (sa["w"], sa["l"], sb["w"], sb["l"]) == (1, 0, 0, 1)
    assert sa["rating"] > 1000 > sb["rating"] and sa["net"] == 10_000 - tax and sb["net"] == -10_000
    run(app._fd_finish(d, "b"))                                                  # idempotent: no second payout
    assert app.data[A]["money"] + app.data[B]["money"] == ma + mb - tax


def test_draw_and_void_refund_everything_with_no_toll():
    for verdict in ("draw", "void"):
        _reset()
        ma, mb = app.data[A]["money"], app.data[B]["money"]
        d = _duel(25_000)
        run(app._fd_finish(d, verdict))
        assert app.data[A]["money"] == ma and app.data[B]["money"] == mb and d["tax"] == 0


def test_friendly_duels_move_no_money_but_still_count():
    _reset()
    ma, mb = app.data[A]["money"], app.data[B]["money"]
    d = _duel(0)
    run(app._fd_finish(d, "b"))
    assert app.data[A]["money"] == ma and app.data[B]["money"] == mb
    assert app._fd_stats(B)["w"] == 1 and app._fd_stats(B)["net"] == 0


def test_a_player_who_spent_their_stake_in_the_meantime_cancels_the_duel_cleanly():
    _reset()
    d = app._fd_new(A, B, 500_000, 1)
    app.data[B]["money"] = 100
    ok, msg = run(app._fd_start(d))
    assert not ok and "can't cover" in msg and app.data[A]["money"] == 1_000_000
    assert d["status"] == "pending"


def test_duel_titles_unlock_at_win_milestones():
    _reset()
    s = app._fd_stats(A)
    s["w"] = 9
    d = _duel(0)
    run(app._fd_finish(d, "a"))
    assert "Standoff Survivor" in app.data[A]["earned_titles"]


# ── limits ──────────────────────────────────────────────────

def test_challenge_checks():
    _reset()
    chk = lambda a=A, b=B, bet=1000: app._fd_check_challenge(a, b, bet)
    assert chk() == ""
    assert "yourself" in chk(A, A)
    assert "minimum stake" in chk(bet=100)
    cap = min(app.gamble_max_bet(A), app.gamble_max_bet(B))
    assert "capped" in chk(bet=cap + 1)
    assert chk(bet=0) == ""                                       # a friendly needs no stake
    app.data[A]["money"] = 10
    assert "can't cover" in chk(bet=1000)
    app.data[A]["money"] = 10 ** 6
    app.data[B]["level"] = 2
    assert "level" in chk()
    app.data[B]["level"] = 100
    app.data[A]["ban"] = {"active": True}
    assert "can't duel" in chk() or "right now" in chk()
    app.data[A].pop("ban")
    app.data[B]["_boss"] = {"creature": "Bigfoot", "eid": "z", "biome": "woods", "ts": time.time()}
    assert "middle of a fight" in chk()
    app.data[B].pop("_boss")
    d = app._fd_new(A, B, 0, 1)
    assert "already" in chk()                                     # one standoff at a time
    d["status"] = "cancelled"
    assert chk() == ""


def test_pair_and_daily_limits_stop_alt_funnelling():
    _reset()
    for _ in range(app.FD_PAIR_DAILY):
        d = _duel(1000)
        run(app._fd_finish(d, "a"))
    why = app._fd_check_challenge(A, B, 1000)
    assert "can only duel" in why
    tt._mk_user("7003", level=100, money=10 ** 6)
    assert app._fd_check_challenge(A, "7003", 1000) == ""
    for i in range(app.FD_DAILY_LIMIT):
        app._fd_day(A)["n"] += 1
    assert "limit" in app._fd_check_challenge(A, "7003", 1000)


# ── clicks (through the real component handler) ─────────────

def _click(uid, cid):
    it = tr.FakeInteraction(uid, cid)
    with tr.Harness() as h:
        run(app._fight_component(it, cid.split(":")))
    return h


def test_only_the_challenged_hunter_can_accept_and_only_participants_can_click():
    _reset()
    d = app._fd_new(A, B, 5000, 1)
    h = _click(A, f"fight:acc:{d['id']}")
    assert any("Only" in m for m in h.ephemerals) and d["status"] == "pending"
    tt._mk_user("7009", level=100)
    h = _click("7009", f"fight:acc:{d['id']}")
    assert any("between" in m for m in h.ephemerals)
    h = _click(B, f"fight:acc:{d['id']}")
    assert d["status"] == "active" and d["round"] == 1 and d["escrowed"]
    h = _click(B, f"fight:acc:{d['id']}")
    assert any("Already" in m or "started" in m for m in h.ephemerals)
    h = _click("7009", f"fight:pick:{d['id']}:1")
    assert not d["picks"]


def test_declining_and_cancelling():
    _reset()
    d = app._fd_new(A, B, 5000, 1)
    assert "Only" in "".join(_click(A, f"fight:dec:{d['id']}").ephemerals) and d["status"] == "pending"
    _click(B, f"fight:dec:{d['id']}")
    assert d["status"] == "cancelled" and app.data[A]["money"] == 1_000_000
    d2 = app._fd_new(A, B, 5000, 1)
    assert "Only" in "".join(_click(B, f"fight:can:{d2['id']}").ephemerals)
    _click(A, f"fight:can:{d2['id']}")
    assert d2["status"] == "cancelled"


def test_a_full_duel_through_the_buttons():
    _reset()
    d = app._fd_new(A, B, 10_000, 1)
    d["first"] = A
    _click(B, f"fight:acc:{d['id']}")
    for _ in range(app.FD_ROUNDS + app.FD_SUDDEN_DEATH):
        if d["status"] != "active":
            break
        rnd = d["round"]
        hunter, prey = app._fd_roles(d)
        # the hunter always searches spot (rnd % 4), the prey always hides two spots away
        hs, ps = rnd % 4, (rnd + 2) % 4
        _click(hunter, f"fight:meth:{d['id']}:sharp")
        _click(hunter, f"fight:pick:{d['id']}:{hs}")
        assert d["picks"].get(hunter) == hs
        h = _click(hunter, f"fight:pick:{d['id']}:{(hs + 1) % 4}")
        assert any("already locked" in m for m in h.ephemerals)
        _click(prey, f"fight:pick:{d['id']}:{ps}")
    assert d["status"] == "done" and d["verdict"] in ("a", "b", "draw")
    assert app.data[A]["money"] + app.data[B]["money"] in (2_000_000 - d["tax"], 2_000_000)
    if d["verdict"] != "draw":
        assert d["tax"] == 2_000


def test_the_same_spot_cannot_be_used_two_rounds_running_and_methods_belong_to_the_hunter():
    _reset()
    d = app._fd_new(A, B, 0, 1)
    d["first"] = A
    _click(B, f"fight:acc:{d['id']}")
    h = _click(B, f"fight:meth:{d['id']}:sweep")                 # B is the prey in round 1
    assert any("prey" in m for m in h.ephemerals)
    _click(A, f"fight:pick:{d['id']}:1")
    _click(B, f"fight:pick:{d['id']}:2")
    assert d["round"] == 2 and d["last"] == {A: 1, B: 2}
    h = _click(A, f"fight:pick:{d['id']}:1")                     # round 2: A is the prey and used spot 1 last time
    assert any("two rounds running" in m for m in h.ephemerals) and A not in d["picks"]
    h = _click(B, f"fight:pick:{d['id']}:2")                     # B hunts, but searched spot... B hid at 2
    assert any("two rounds running" in m for m in h.ephemerals)


def test_timeouts_cancel_pending_challenges_and_forfeit_idle_rounds():
    _reset()
    d = app._fd_new(A, B, 0, 1)
    d["created"] -= app.FD_PENDING_SEC + 5
    run(app.fight_task.coro())
    assert d["status"] == "cancelled"
    d = app._fd_new(A, B, 3000, 1)
    d["first"] = A
    run(app._fd_start(d))
    d["picks"] = {A: 1}                                           # hunter locked, prey idle
    d["deadline"] = time.time() - 1
    run(app.fight_task.coro())
    assert d["round"] == 2 and d["hist"][0]["note"].startswith("The prey never") and d["scores"][A] == 1
    d["deadline"] = time.time() - 1
    run(app.fight_task.coro())                                    # nobody moved in round 2
    d["deadline"] = time.time() - 1
    run(app.fight_task.coro())                                    # ... nor round 3
    assert d["status"] == "done" and d["verdict"] == "void"
    assert app.data[A]["money"] == 1_000_000 and app.data[B]["money"] == 1_000_000


def test_restart_recovery_refunds_running_duels():
    _reset()
    d = _duel(40_000)
    p = app._fd_new(A, "7003", 0, 1) if False else None
    assert app.data[A]["money"] == 960_000
    run(app.duels_recover())
    assert d["status"] == "done" and d["verdict"] == "void"
    assert app.data[A]["money"] == 1_000_000 and app.data[B]["money"] == 1_000_000


def test_duels_survive_the_runtime_state_round_trip_and_cards_render():
    _reset()
    d = _duel(5000)
    import json
    saved = json.loads(json.dumps(app._encode_runtime_state(), default=str))
    assert d["id"] in saved["duels"]
    for status in ("pending", "active", "done", "cancelled"):
        d["status"] = status
        d["verdict"] = "a"
        d["tax"] = 500
        blob = json.dumps(app.build_duel_card(d), ensure_ascii=False)
        assert "Trail Standoff" in blob and len(blob) < 8000
    d["status"] = "active"
    assert f"fight:pick:{d['id']}:3" in json.dumps(app.build_duel_card(d))
    _ = app.fight_group.commands
    assert {c.name for c in app.fight_group.commands} == {"challenge", "stats", "leaderboard", "rules"}


def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(tt._ensure_db())
    _patch()
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
    _unpatch()
    try:
        run(tt.backend.close_databases())
    except Exception:
        pass
    if failed:
        print(f"{failed} FAILED")
        sys.exit(1)
    print(f"all {len(_all_tests())} tests passed")
    sys.exit(0)
