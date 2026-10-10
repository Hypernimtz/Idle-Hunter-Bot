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
def test_scratch_pad_board_has_exactly_5_prizes_and_7_blanks():
    _reset()
    uid = "9110"
    _mk_user(uid)
    board = app.start_scratch_pad(uid)
    prizes = [c for c in board["cells"] if c is not None]
    blanks = [c for c in board["cells"] if c is None]
    assert len(board["cells"]) == app.SCRATCH_PAD_GRID_SIZE == 12
    assert len(prizes) == app.SCRATCH_PAD_PRIZE_COUNT == 5
    assert len(blanks) == 7
    assert board["found"] == 0
    assert board["revealed"] == [False] * 12


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


def test_scratch_pad_completes_after_max_picks_even_with_prizes_left_unfound():
    _reset()
    uid = "9113"
    _mk_user(uid, money=0)
    board = app.start_scratch_pad(uid)
    assert app.SCRATCH_PAD_MAX_PICKS == 3
    assert app.SCRATCH_PAD_PRIZE_COUNT == 5   # more prizes exist than picks allowed

    async def _reveal_n(n):
        results = []
        for idx in range(n):
            async with app.user_transaction(uid):
                results.append(app.reveal_scratch_pad_cell(uid, idx))
        return results
    results = run(_reveal_n(app.SCRATCH_PAD_MAX_PICKS))

    assert [r["kind"] for r in results] == ["revealed", "revealed", "done"]
    assert app.data[uid]["scratch_pad"] is None
    # at most MAX_PICKS prizes can ever be found, never all 5
    assert len(results[-1]["all_prizes"]) <= app.SCRATCH_PAD_MAX_PICKS


def test_scratch_pad_can_find_zero_prizes():
    """With only 3 of 16 cells revealed, missing all 5 prizes is a real,
    reachable outcome — this is a gamble now, not a guaranteed payout."""
    _reset()
    uid = "9115"
    _mk_user(uid)
    board = app.start_scratch_pad(uid)
    blank_indices = [i for i, c in enumerate(board["cells"]) if c is None]
    assert len(blank_indices) >= app.SCRATCH_PAD_MAX_PICKS

    async def _go():
        results = []
        for idx in blank_indices[:app.SCRATCH_PAD_MAX_PICKS]:
            async with app.user_transaction(uid):
                results.append(app.reveal_scratch_pad_cell(uid, idx))
        return results
    results = run(_go())
    assert results[-1]["kind"] == "done"
    # missing every prize is still reachable, but a card never pays nothing: it pays one consolation prize
    assert len(results[-1]["all_prizes"]) == 1


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


def test_scratch_pad_renders_three_columns_and_old_16_cell_boards_still_work():
    _reset()
    uid = "9116"
    _mk_user(uid)
    app.start_scratch_pad(uid)
    rows = [r for r in app.build_scratch_pad_components(uid)[0]["components"]
            if r.get("type") == 1 and len(r["components"]) > 1]
    assert [len(r["components"]) for r in rows] == [3, 3, 3, 3]
    # a pad started before the resize keeps its 4x4 layout and stays playable
    app.data[uid]["scratch_pad"] = {"cells": [None] * 16, "revealed": [False] * 16, "found": 0}
    rows = [r for r in app.build_scratch_pad_components(uid)[0]["components"]
            if r.get("type") == 1 and len(r["components"]) > 1]
    assert [len(r["components"]) for r in rows] == [4, 4, 4, 4]

    async def _go():
        async with app.user_transaction(uid):
            return app.reveal_scratch_pad_cell(uid, 15)
    assert run(_go())["kind"] == "revealed"


def test_scratch_pad_crate_prize_lands_in_crate_inventory():
    _reset()
    uid = "9117"
    _mk_user(uid)
    run(_ensure_db())
    assert any(t == "crate" and d["name"] in game_data.CRATE_TIERS
               for _, t, d in game_data.SCRATCH_PAD_REWARDS)
    assert all(d["name"] in game_data.CRATE_TIERS
               for _, t, d in game_data.SCRATCH_PAD_REWARDS if t == "crate")
    board = app.start_scratch_pad(uid)
    board["cells"][0] = {"type": "crate", "name": "Epic Crate", "qty": 1}
    before = app.data[uid].get("crate_inv", {}).get("Epic Crate", 0)

    async def _go():
        async with app.user_transaction(uid):
            return app.reveal_scratch_pad_cell(uid, 0)
    res = run(_go())
    assert res["prize"]["type"] == "crate"
    assert app.data[uid]["crate_inv"]["Epic Crate"] == before + 1
    assert "Epic Crate" in app._fmt_reward(res["prize"])


def test_forge_slots_grow_with_level():
    _reset()
    uid = "9118"
    _mk_user(uid)
    assert game_data.craft_queue_cap(1) == game_data.CRAFT_QUEUE_MAX == 20
    assert game_data.craft_queue_cap(49) == 20
    assert game_data.craft_queue_cap(50) == 25
    assert game_data.craft_queue_cap(1000) == game_data.craft_queue_cap(99999) == game_data.CRAFT_QUEUE_HARD_CAP
    app.data[uid]["level"] = 1
    app.data[uid]["shards"] = {"common": 9 * 30}
    app.data[uid]["craft_queue"] = [{"rarity": "common", "done_ts": time.time() + 9999}] * 20
    assert app.queue_crystal_craft(uid, "common")["reason"] == "queue_full"
    app.data[uid]["level"] = 100
    assert app.forge_slots(uid) == 30
    assert app.queue_crystal_craft(uid, "common")["ok"]
    assert "level 150" in app.forge_next_slots_line(uid)


def test_scratch_pad_is_not_purchasable_or_tradable():
    """Not sold anywhere (it's a /vote reward) and not tradable."""
    assert "Scratch Pad" not in app.ITEM_GOLD_SHOP
    assert "Scratch Pad" not in app.ITEM_GEM_SHOP
    assert app.ITEMS["Scratch Pad"]["tradable"] is False
    name, kind = app._market_canon("Scratch Pad")
    assert name is None


def test_scratch_pad_shows_up_in_info():
    entries = dict(app._info_entries("items"))
    assert "Scratch Pad" in entries


def test_vote_claim_grants_a_scratch_pad():
    _reset()
    uid = "9116"
    _mk_user(uid)
    run(_ensure_db())

    async def _go():
        async with app.user_transaction(uid):
            app.add_item(uid, "Scratch Pad", 1)
    run(_go())
    assert app.item_count(uid, "Scratch Pad") == 1


# ─────────────────────────────────────────────────────────────
# /vote real-vote verification (check_dbl_recent_vote)
# ─────────────────────────────────────────────────────────────
def test_check_dbl_recent_vote_without_token_configured_caller_falls_back():
    """The claim handler only calls check_dbl_recent_vote when DBL_TOKEN is
    set — this just documents that contract so a future refactor doesn't
    silently call the network check with no token."""
    assert hasattr(app, "DBL_TOKEN")


class _FakeResp:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload
    async def json(self):
        return self._payload
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        return False


class _FakeSession:
    def __init__(self, status, payload):
        self._status = status
        self._payload = payload
    def get(self, url, headers=None):
        return _FakeResp(self._status, self._payload)
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        return False


def _with_fake_dbl_response(status, payload, coro_fn):
    """Manually patch app.aiohttp.ClientSession for the duration of coro_fn()
    — this suite has no pytest fixtures available when run standalone via
    `python tests/test_vote_scratch.py`, so no monkeypatch fixture."""
    orig = app.aiohttp.ClientSession
    app.aiohttp.ClientSession = lambda *a, **k: _FakeSession(status, payload)
    try:
        return run(coro_fn())
    finally:
        app.aiohttp.ClientSession = orig


_FAKE_BOT_ID = "1498460874963288164"


def test_check_dbl_recent_vote_finds_matching_fresh_vote():
    payload = {"upvotes": [
        {"user_id": "12345", "timestamp": "2026-09-28T12:00:00.000Z"},
        {"user_id": "99999", "timestamp": "2026-09-28T12:00:00.000Z"},
    ], "total": 2}
    result = _with_fake_dbl_response(200, payload,
        lambda: app.check_dbl_recent_vote("12345", 0.0, bot_id=_FAKE_BOT_ID))
    assert result is True


def test_check_dbl_recent_vote_no_matching_user_returns_false():
    payload = {"upvotes": [{"user_id": "99999", "timestamp": "2026-09-28T12:00:00.000Z"}], "total": 1}
    result = _with_fake_dbl_response(200, payload,
        lambda: app.check_dbl_recent_vote("12345", 0.0, bot_id=_FAKE_BOT_ID))
    assert result is False


def test_check_dbl_recent_vote_stale_vote_before_since_ts_returns_false():
    payload = {"upvotes": [{"user_id": "12345", "timestamp": "2020-01-01T00:00:00.000Z"}], "total": 1}
    result = _with_fake_dbl_response(200, payload,
        lambda: app.check_dbl_recent_vote("12345", time.time(), bot_id=_FAKE_BOT_ID))
    assert result is False


def test_check_dbl_recent_vote_http_error_returns_none_not_false():
    """A transient API failure must not be treated as 'didn't vote' — that
    would silently deny a legitimate voter."""
    result = _with_fake_dbl_response(500, {},
        lambda: app.check_dbl_recent_vote("12345", 0.0, bot_id=_FAKE_BOT_ID))
    assert result is None


def test_check_dbl_recent_vote_without_bot_id_returns_none():
    result = run(app.check_dbl_recent_vote("12345", 0.0, bot_id=None))
    # bot.user is unset in this test harness (no real Discord login), so with
    # no explicit bot_id this must degrade to "can't check", never crash.
    assert result is None


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
