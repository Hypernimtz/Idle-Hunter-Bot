"""
Gambling limits: wealth/level-scaled bet cap, capped profit per wager, house edge on coinflip & RPS.

Runs without pytest:  python tests/test_gamble_limits.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_gamble_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "g1"


def test_coinflip_and_rps_have_a_house_edge():
    assert gd.COINFLIP_PAYOUT == 2.0 and gd.RPS_PAYOUT == 2.0       # payouts untouched: the edge is in the odds
    assert abs(gd.COINFLIP_WIN_CHANCE * gd.COINFLIP_PAYOUT - 0.95) < 1e-9
    w, t, l = gd.RPS_ODDS
    assert w + t + l == 100
    rps_rtp = (w * gd.RPS_PAYOUT + t * 1.0) / 100               # win pays 2x, tie refunds, loss pays 0
    assert abs(rps_rtp - 0.95) < 1e-9, rps_rtp


def test_the_rolls_follow_the_published_odds():
    import random
    random.seed(7)
    n = 40000
    wins = sum(1 for _ in range(n) if random.random() < gd.COINFLIP_WIN_CHANCE)
    assert abs(wins / n - 0.475) < 0.01
    from collections import Counter
    c = Counter(random.choices(["win", "tie", "lose"], weights=gd.RPS_ODDS, k=n))
    assert abs(c["win"] / n - 0.31) < 0.01 and abs(c["tie"] / n - 0.33) < 0.01


def test_profit_per_wager_is_capped():
    tt._reset()
    tt._mk_user(U, money=1_000_000_000)
    cap = app.gamble_max_bet(U)
    assert cap == 20_000_000                                     # 2% of a billion
    bet = cap
    assert app.gamble_cap_payout(U, bet, bet * 2) == bet * 2     # ordinary wins are untouched
    jackpot = app.gamble_cap_payout(U, bet, bet * 15)            # a Green hit at max bet
    assert jackpot == bet + app.gamble_max_win(U) and jackpot < bet * 15
    assert app.gamble_max_win(U) == cap * gd.GAMBLE_MAX_WIN_MULT


def test_all_in_on_green_is_no_longer_possible():
    tt._reset()
    tt._mk_user(U, money=1_000_000_000)
    async def modal():
        return app.SetBetModal(U, "rl")
    m = run(modal())
    assert m.max_bet < 1_000_000_000 and m.max_bet == app.gamble_max_bet(U)


def test_small_accounts_keep_a_playable_floor():
    tt._reset()
    tt._mk_user(U, money=300)
    assert app.gamble_max_bet(U) >= gd.GAMBLE_BET_FLOOR


def test_result_panels_show_the_real_profit():
    tt._reset()
    tt._mk_user(U, money=100_000)
    import json
    cf = json.dumps(app.build_coinflip_panel(U, "result",
        {"won": True, "bet": 1000, "flip": "heads", "pick": "heads", "payout": 2000}), ensure_ascii=False)
    assert "+◈ 1,000" in cf
    rps = json.dumps(app.build_rps_panel(U, "result",
        {"pick": "rock", "bot_pick": "scissors", "bet": 1000, "outcome": "win", "payout": 2000}), ensure_ascii=False)
    assert "+◈ 1,000" in rps
    assert "47.5%" in json.dumps(app.build_coinflip_panel(U), ensure_ascii=False)


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
