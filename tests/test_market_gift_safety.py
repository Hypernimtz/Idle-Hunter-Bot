"""
Marketplace & gifting safety: a listing can't be bought (and its DB row deleted) before its own save
lands, tiny sales still burn 1 coin, a reset deletes persisted listings before the wipe, money gifts
need a mature account and respect sender- AND receiver-side daily caps (so a prestiged level-1 alt can't
take a fortune back), and unconfirmed gifts expire.

Runs without pytest:  python tests/test_market_gift_safety.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_mkt_safety_pytest.db"))
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
S, B = "7701", "7702"


def _setup():
    tr._market_reset()
    s = tr._seller(S, money=0, crate_inv={"Rare Crate": 3})
    b = tr._mk_user(B, money=10_000, level=300, joined_date="2020-01-01")
    return s, b


def test_a_listing_cant_be_bought_before_its_save_lands():
    s, b = _setup()
    real_save = backend.market_save
    seen = {}

    async def slow_save(listing):
        # while the INSERT is "in flight" the listing exists in memory but must not be buyable
        lid = listing["id"]
        seen["live"] = [l["id"] for l in app._market_live()]
        seen["buy"] = await app.market_buy(B, lid, 1)
        seen["cancel"] = await app.market_return(lid, requester=S)
        await real_save(listing)

    async def body():
        await tr._ensure_db()
        backend.market_save = slow_save
        try:
            ok, lid = await app.market_create_listing(S, "rare", 2, 100)
        finally:
            backend.market_save = real_save
        assert ok
        assert seen["live"] == [] and seen["buy"][0] is False and seen["cancel"][0] is False
        assert "pending" not in app._market[lid]
        assert lid in await backend.market_load()                   # persisted exactly once, still there
        assert (await app.market_buy(B, lid, 1))[0] is True         # buyable afterwards
        assert "pending" not in (await backend.market_load())[lid]
    run(body())


def test_tiny_sales_still_burn_one_coin():
    s, b = _setup()
    b["money"] = 100

    async def body():
        await tr._ensure_db()
        ok, lid = await app.market_create_listing(S, "rare", 1, 5)
        assert ok and (await app.market_buy(B, lid, 1))[0]
        assert s["money"] == 4                                      # 5 - 1 burned (was 5 untaxed)
    run(body())


def test_reset_purges_persisted_listings_before_the_wipe():
    s, b = _setup()

    async def body():
        await tr._ensure_db()
        ok, lid = await app.market_create_listing(S, "rare", 2, 100)
        assert ok and lid in await backend.market_load()
        await app.market_purge_for_reset(S)
        assert lid not in app._market and lid not in await backend.market_load()
    run(body())


def _gift(sender, receiver, fmt, amount):
    return app._gift_block(sender, receiver, fmt, amount)


def test_money_gifts_need_level_and_age_and_respect_the_sender_cap():
    tt._reset()
    tt._mk_user(S, level=300, joined_date="2020-01-01", money=10 ** 12)
    tt._mk_user(B, level=300, joined_date="2020-01-01")
    cap = app._gift_money_cap(S)
    assert cap == gd.crate_value_scale(300) * app.GIFT_MONEY_DAILY_X
    assert _gift(S, B, "money", cap) is None
    assert "per day" in _gift(S, B, "money", cap + 1)
    app.data[S]["money_gift_day"] = {"tag": app.today_utc(), "sent": cap - 5}
    assert _gift(S, B, "money", 6) and _gift(S, B, "money", 5) is None
    app.data[S]["money_gift_day"] = {"tag": "1999-01-01", "sent": 10 ** 12}
    assert _gift(S, B, "money", cap) is None                        # a new day resets it
    app.data[S]["level"] = 5
    assert "level" in _gift(S, B, "money", 10)
    app.data[S]["level"] = 300
    app.data[S]["joined_date"] = time.strftime("%Y-%m-%d", time.gmtime())
    assert "days old" in _gift(S, B, "money", 10)


def test_a_freshly_prestiged_receiver_cant_take_back_a_fortune():
    tt._reset()
    tt._mk_user(S, level=1000, joined_date="2020-01-01", money=10 ** 12)
    tt._mk_user(B, level=1, joined_date="2020-01-01")                # just prestiged
    assert "can only receive" in _gift(S, B, "money", app._gift_money_cap(B) + 1)   # a level-1 account's limit
    assert _gift(S, B, "money", 1_000) is None
    app.data[B]["gift_recv_day"] = {"tag": app.today_utc(), "money": app._gift_money_cap(B) - 10, "gems": 0}
    assert "can only receive" in _gift(S, B, "money", 11)


def test_gem_gifts_also_respect_a_receiver_daily_cap():
    tt._reset()
    tt._mk_user(S, level=300, joined_date="2020-01-01", gems=5000)
    tt._mk_user(B, level=300, joined_date="2020-01-01")
    app.data[B]["gift_recv_day"] = {"tag": app.today_utc(), "money": 0, "gems": app.GIFT_GEMS_DAILY_CAP - 10}
    assert "can only receive" in _gift(S, B, "gems", 11) and _gift(S, B, "gems", 10) is None


def test_unconfirmed_gifts_expire():
    tt._reset()
    tt._mk_user(S, level=300, joined_date="2020-01-01", money=10 ** 9)
    tt._mk_user(B, level=300, joined_date="2020-01-01")

    class _U:
        id = int(B)
        mention = "<@x>"
    app.gift_cache.clear()
    app.build_gift_confirm_components(S, _U(), "money", 100, "hi")
    (gid, g), = app.gift_cache.items()
    g["ts"] -= app.GIFT_CONFIRM_TTL_S + 5
    app.build_gift_confirm_components(S, _U(), "money", 100, "hi")      # next gift prunes the stale one
    assert gid not in app.gift_cache and len(app.gift_cache) == 1
    cid = f"gift:confirm:{next(iter(app.gift_cache))}"
    app.gift_cache[next(iter(app.gift_cache))]["ts"] -= app.GIFT_CONFIRM_TTL_S + 5
    before = (app.data[S]["money"], app.data[B]["money"])
    it = tr.FakeInteraction(S, cid)
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    assert "expired" in " ".join(h.ephemerals)
    assert (app.data[S]["money"], app.data[B]["money"]) == before            # nothing moved


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
