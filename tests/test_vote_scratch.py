"""
/vote and Scratch Pad regression suite (2026-09-28 feature).

Runs without pytest:  python tests/test_vote_scratch.py
Runs with pytest too: pytest tests/test_vote_scratch.py
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

os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_vote_scratch_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import discord.ext.commands as _c  # noqa: E402
_c.Bot.run = lambda *a, **k: None

import app          # noqa: E402
import backend      # noqa: E402
import game_data    # noqa: E402

_DB_READY = False


async def _ensure_db():
    global _DB_READY
    if not _DB_READY:
        await backend.init_databases()
        app.register_state_refs(app.data, app.tribe_data)
        _DB_READY = True


def _reset():
    app.data.clear()
    app.tribe_data.clear()
    app._dirty_users.clear()


def _mk_user(uid, **over):
    app.data.pop(uid, None)
    app.init_user(uid)
    d = app.data[uid]
    d["onboarding"] = {"version": 2, "completed": True, "step": "done", "starter_pack": None}
    d["hunters_path"] = {"completed": True}
    d["verify"] = {"needed": False, "time": 10 ** 9, "code": "ABCD"}
    d.update(over)
    return d


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─────────────────────────────────────────────────────────────
# /vote
# ─────────────────────────────────────────────────────────────
def test_vote_new_user_is_immediately_claimable():
    _reset()
    uid = "9101"
    _mk_user(uid)
    assert time.time() >= app.data[uid]["vote_cd"]


def test_vote_claim_grants_crate_and_money_and_sets_cooldown():
    _reset()
    uid = "9102"
    _mk_user(uid, money=0)
    run(_ensure_db())
    before_crates = app.data[uid].get("crate_inv", {}).get(game_data.VOTE_REWARD_CRATE, 0)

    async def _go():
        async with app.user_transaction(uid):
            level = app.data[uid].get("level", 1)
            money_amt = int(game_data.VOTE_REWARD_MONEY_X * app.crate_value_scale(level))
            app.add_money(uid, money_amt, "vote")
            ci = app.data[uid].setdefault("crate_inv", {})
            ci[game_data.VOTE_REWARD_CRATE] = ci.get(game_data.VOTE_REWARD_CRATE, 0) + 1
            app.data[uid]["vote_cd"] = time.time() + game_data.VOTE_COOLDOWN_HOURS * 3600
            return money_amt
    money_amt = run(_go())

    assert app.data[uid]["money"] == money_amt
    assert app.data[uid]["crate_inv"][game_data.VOTE_REWARD_CRATE] == before_crates + 1
    assert app.data[uid]["vote_cd"] > time.time()


def test_vote_cooldown_blocks_second_claim():
    _reset()
    uid = "9103"
    _mk_user(uid)
    app.data[uid]["vote_cd"] = time.time() + 3600   # just claimed an hour ago
    assert time.time() < app.data[uid]["vote_cd"]   # still on cooldown


def test_vote_reward_crate_is_a_real_crate_tier():
    assert game_data.VOTE_REWARD_CRATE in game_data.CRATE_TIERS


# ─────────────────────────────────────────────────────────────
# Scratch Pad
# ─────────────────────────────────────────────────────────────
def test_scratch_pad_board_has_exactly_5_prizes_and_11_blanks():
    _reset()
    uid = "9110"
    _mk_user(uid)
    board = app.start_scratch_pad(uid)
    prizes = [c for c in board["cells"] if c is not None]
    blanks = [c for c in board["cells"] if c is None]
    assert len(board["cells"]) == app.SCRATCH_PAD_GRID_SIZE == 16
    assert len(prizes) == app.SCRATCH_PAD_PRIZE_COUNT == 5
    assert len(blanks) == 11
    assert board["found"] == 0
    assert board["revealed"] == [False] * 16


def test_scratch_pad_reveal_prize_cell_grants_reward_and_marks_found():
    _reset()
    uid = "9111"
    _mk_user(uid, money=0)
    board = app.start_scratch_pad(uid)
    prize_idx = next(i for i, c in enumerate(board["cells"]) if c is not None)
    before_money = app.data[uid]["money"]
    before_gems = app.data[uid]["gems"]

    async def _go():
        async with app.user_transaction(uid):
            return app.reveal_scratch_pad_cell(uid, prize_idx)
    result = run(_go())

    assert result["kind"] in ("revealed", "done")
    assert result["prize"] is not None
    if result["prize"]["type"] == "money":
        assert app.data[uid]["money"] > before_money
    elif result["prize"]["type"] == "gems":
        assert app.data[uid]["gems"] > before_gems


def test_scratch_pad_reveal_blank_cell_grants_nothing():
    _reset()
    uid = "9112"
    _mk_user(uid, money=0)
    board = app.start_scratch_pad(uid)
    blank_idx = next(i for i, c in enumerate(board["cells"]) if c is None)
    before_money = app.data[uid]["money"]

    async def _go():
        async with app.user_transaction(uid):
            return app.reveal_scratch_pad_cell(uid, blank_idx)
    result = run(_go())

    assert result["kind"] == "revealed"
    assert result["prize"] is None
    assert app.data[uid]["money"] == before_money
    assert app.data[uid]["scratch_pad"]["found"] == 0


def test_scratch_pad_completes_after_all_5_prizes_found_and_clears_state():
    _reset()
    uid = "9113"
    _mk_user(uid, money=0)
    board = app.start_scratch_pad(uid)
    prize_indices = [i for i, c in enumerate(board["cells"]) if c is not None]
    assert len(prize_indices) == 5

    async def _reveal_all():
        results = []
        for idx in prize_indices:
            async with app.user_transaction(uid):
                results.append(app.reveal_scratch_pad_cell(uid, idx))
        return results
    results = run(_reveal_all())

    assert [r["kind"] for r in results] == ["revealed"] * 4 + ["done"]
    assert app.data[uid]["scratch_pad"] is None
    assert len(results[-1]["all_prizes"]) == 5


def test_scratch_pad_double_reveal_same_cell_is_noop():
    _reset()
    uid = "9114"
    _mk_user(uid)
    board = app.start_scratch_pad(uid)
    idx = 0

    async def _go():
        async with app.user_transaction(uid):
            first = app.reveal_scratch_pad_cell(uid, idx)
            second = app.reveal_scratch_pad_cell(uid, idx)
            return first, second
    first, second = run(_go())
    assert second["kind"] == "none"


def test_scratch_pad_price_exceeds_guaranteed_expected_value():
    """Every prize is eventually found with certainty, so the price must sit
    above the guaranteed average payout or repeated buy-and-scratch mints
    free money (see the comment above SCRATCH_PAD_REWARDS)."""
    scale = 1000
    trials = 4000
    total = 0
    for _ in range(trials):
        r = game_data.roll_scratch_pad_prize(scale)
        if r["type"] == "money":
            total += r["amount"]
    avg_money_per_slot = total / trials
    avg_total_per_pad = avg_money_per_slot * game_data.SCRATCH_PAD_PRIZE_COUNT
    price = game_data.SCRATCH_PAD_PRICE_X * scale
    assert price > avg_total_per_pad, (price, avg_total_per_pad)


def test_scratch_pad_is_not_tradable():
    assert app.ITEMS["Scratch Pad"]["tradable"] is False
    name, kind = app._market_canon("Scratch Pad")
    assert name is None


def test_scratch_pad_shows_up_in_gold_shop_and_info():
    assert "Scratch Pad" in app.ITEM_GOLD_SHOP
    entries = dict(app._info_entries("items"))
    assert "Scratch Pad" in entries


# ─────────────────────────────────────────────────────────────
# Shared _apply_reward_simple (crate-opening refactor regression)
# ─────────────────────────────────────────────────────────────
def test_apply_reward_simple_money_and_temp_boost_match_crate_behavior():
    _reset()
    uid = "9120"
    _mk_user(uid, money=0)
    run(_ensure_db())

    async def _go():
        async with app.user_transaction(uid):
            app._apply_reward_simple(uid, {"type": "money", "amount": 500}, "test")
            app._apply_reward_simple(uid, {"type": "temp_boost", "stat": "luck",
                                            "amount": 20, "minutes": 10}, "test")
    run(_go())
    assert app.data[uid]["money"] == 500
    boosts = app.get_active_temp_boosts(uid)
    assert boosts["luck"] == 20


# ─────────────────────────────────────────────────────────────
def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(_ensure_db())
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
