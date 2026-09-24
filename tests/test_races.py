"""
Regression tests for the double-click / stale-panel race class and the related
economy, tribe and data-safety fixes.

Runs without pytest:  python tests/test_races.py
"""
import asyncio
import itertools
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

os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_races_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import discord                  # noqa: E402
import discord.ext.commands as _c  # noqa: E402
_c.Bot.run = lambda *a, **k: None

import app          # noqa: E402
import backend      # noqa: E402
import game_data    # noqa: E402

_DB_READY = False
_ids = itertools.count(9_000_000_000_000)


async def _ensure_db():
    global _DB_READY
    if not _DB_READY:
        await backend.init_databases()
        app.register_state_refs(app.data, app.tribe_data)
        _DB_READY = True


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _reset():
    app.data.clear()
    app.tribe_data.clear()
    app._dirty_users.clear()
    app._active_event = None
    app._bj_state.clear()
    backend.SAVES_DISABLED = False


def _mk_user(uid, **over):
    app.data.pop(uid, None)
    app.init_user(uid)
    d = app.data[uid]
    d["onboarding"] = {"version": 2, "completed": True, "step": "done", "starter_pack": None}
    d["hunters_path"] = {"completed": True}
    d["verify"] = {"needed": False, "time": 10 ** 9, "code": "ABCD"}
    d.update(over)
    return d


def _mk_tribe(name, leader, officers=(), members=(), recruits=()):
    td = {"roles": {"leader": leader, "officer": list(officers), "members": list(members),
                    "recruits": list(recruits)},
          "invites": [], "banned": [], "luck_boost": 0, "sell_price_boost": 0, "xp_boost": 0,
          "max_members": 10, "level": 1, "xp": 0, "description": ""}
    app._ensure_tribe_fields(td)
    app.tribe_data[name] = td
    for u in [leader, *officers, *members, *recruits]:
        if u not in app.data:
            _mk_user(u)
        app.data[u]["tribe"] = name
    return td


# ── fake Discord plumbing ─────────────────────────────────────
class _Resp:
    def __init__(self):
        self.done = False

    def is_done(self):
        return self.done

    async def defer(self, **k):
        self.done = True
        await asyncio.sleep(0)

    async def send_modal(self, m):
        self.done = True


class _User:
    def __init__(self, uid):
        self.id = int(uid)
        self.display_name = f"user{uid}"


class FakeInteraction:
    def __init__(self, uid, cid, values=None):
        self.type = discord.InteractionType.component
        self.id = next(_ids)
        self.data = {"custom_id": cid, "values": values or []}
        self.user = _User(uid)
        self.response = _Resp()
        self.guild = None
        self.guild_id = None
        self.channel = None
        self.channel_id = None
        self.application_id = 1
        self.token = "t"


class Harness:
    """Patches the Discord-facing helpers so handlers run offline and records
    every ephemeral / panel reply."""
    NAMES = ("_common_init", "smart_update_v2", "send_ephemeral_v2", "send_v2_followup",
             "_hunters_path_notify", "check_everything", "check_achievements_and_badges",
             "_modal_gate")

    def __enter__(self):
        self.saved = {n: getattr(app, n) for n in self.NAMES}
        self.ephemerals, self.panels = [], []

        async def common_init(interaction, **k):
            return str(interaction.user.id)

        async def smart(interaction, comps):
            self.panels.append(comps)

        async def eph(interaction, msg, color=0):
            self.ephemerals.append(msg)

        async def noop(*a, **k):
            return None

        async def gate(interaction, uid=None):
            return True

        app._common_init = common_init
        app.smart_update_v2 = smart
        app.send_ephemeral_v2 = eph
        app.send_v2_followup = noop
        app._hunters_path_notify = noop
        app.check_everything = noop
        app.check_achievements_and_badges = noop
        app._modal_gate = gate
        return self

    def __exit__(self, *a):
        for n, f in self.saved.items():
            setattr(app, n, f)


async def _click(uid, cid, values=None):
    await app._dispatch_component(FakeInteraction(uid, cid, values))


async def _double_click(uid, cid, values=None):
    """Two identical clicks that both arrive while the player's lock is busy —
    the exact condition that used to let both pass the pre-lock check."""
    lock = backend.get_user_lock(uid)
    await lock.acquire()
    t1 = asyncio.ensure_future(_click(uid, cid, values))
    t2 = asyncio.ensure_future(_click(uid, cid, values))
    await asyncio.sleep(0.05)
    lock.release()
    await asyncio.gather(t1, t2)


# ── daily / prestige / camp / shop races ──────────────────────
def test_double_click_daily_pays_once():
    _reset()
    uid = "1001"
    d = _mk_user(uid, money=0, gems=0, last_daily_date="", daily_streak=0)
    with Harness():
        run(_double_click(uid, f"daily:claim:{uid}"))
    assert d["daily_streak"] == 1, d["daily_streak"]
    assert (d["money"] > 0) != (d["gems"] > 0), "exactly one reward, not two"


def test_double_click_prestige_once():
    _reset()
    uid = "1002"
    d = _mk_user(uid, level=app.PRESTIGE_MIN_LEVEL, money=app.PRESTIGE_MIN_MONEY * 3, prestige=0)
    with Harness():
        run(_double_click(uid, f"prestige:confirm:{uid}"))
    assert d["prestige"] == 1, d["prestige"]


def test_double_click_hire_hunter_once():
    _reset()
    uid = "1003"
    cost = app.idle_cost_for_stack(0)
    d = _mk_user(uid, money=cost)          # exactly enough for ONE hunter
    d["idle"]["stacks"] = 0
    with Harness() as h:
        run(_double_click(uid, f"idle:hire:{uid}"))
    assert d["idle"]["stacks"] == 1, d["idle"]["stacks"]
    assert d["money"] == 0, d["money"]
    assert any("need" in m.lower() for m in h.ephemerals)


def test_double_click_storage_upgrade_once():
    _reset()
    uid = "1004"
    cost = app.idle_capacity_upgrade_cost(0)
    d = _mk_user(uid, money=cost)
    d["idle"]["capacity_upgrades"] = 0
    with Harness():
        run(_double_click(uid, f"idle:upgrade:{uid}"))
    assert d["idle"]["capacity_upgrades"] == 1
    assert d["money"] == 0


def test_double_click_buy_tool_once():
    _reset()
    uid = "1005"
    price = game_data.TOOLS["Slingshot"]["price"]
    d = _mk_user(uid, money=price * 2)
    with Harness():
        run(_double_click(uid, f"shop:tool_buy_acc:Slingshot:{uid}"))
    assert d["owned_tools"].count("Slingshot") == 1, d["owned_tools"]
    assert d["money"] == price, d["money"]       # charged once


def test_shop_boost_count_ignores_crate_boosts():
    _reset()
    uid = "1006"
    d = _mk_user(uid, gems=500)
    d["boosts"]["luck"] = 40          # won from crates, never bought
    d["shop_bought"] = {}
    assert app.shop_bought_count(d, "Lucky Charm") == 0
    with Harness():
        run(_click(uid, f"shop:buy:Lucky Charm:{uid}"))
    assert d["shop_bought"]["Lucky Charm"] == 1
    assert d["gems"] == 500 - game_data.shop_boost_price("Lucky Charm", 0)


def test_shop_bought_legacy_account_migrates_once():
    _reset()
    uid = "1009"
    d = _mk_user(uid, gems=500)
    d.pop("shop_bought", None)                   # pre-tracker account
    d["boosts"].update({"luck": 25, "sell": 10})
    assert app.shop_bought_count(d, "Lucky Charm") == 5
    assert app.shop_bought_count(d, "Sellmaster Scroll") == 2
    with Harness():
        run(_click(uid, f"shop:buy:Lucky Charm:{uid}"))
    assert d["shop_bought"]["Lucky Charm"] == 6
    assert d["shop_bought"]["Sellmaster Scroll"] == 2, "other items must keep their seeded count"


def test_double_click_open_crate_once():
    _reset()
    uid = "1007"
    d = _mk_user(uid, money=0, gems=0)
    d["crate_inv"] = {"Common Crate": 1}
    opened = []
    real = app._resolve_crate_reward

    def counting(u, c):
        opened.append(c)
        return real(u, c)

    app._resolve_crate_reward = counting
    try:
        with Harness() as h:
            async def two():
                lock = backend.get_user_lock(uid)
                await lock.acquire()
                a = asyncio.ensure_future(app._open_crate_and_show(FakeInteraction(uid, "x"), uid, "Common Crate"))
                b = asyncio.ensure_future(app._open_crate_and_show(FakeInteraction(uid, "x"), uid, "Common Crate"))
                await asyncio.sleep(0.05)
                lock.release()
                await asyncio.gather(a, b)
            run(two())
    finally:
        app._resolve_crate_reward = real
    assert len(opened) == 1, opened
    assert "Common Crate" not in d["crate_inv"]


def test_blackjack_second_bet_rejected():
    _reset()
    uid = "1008"
    d = _mk_user(uid, money=5000)
    with Harness() as h:
        async def two():
            m1, m2 = app.BlackjackBetModal(uid), app.BlackjackBetModal(uid)
            m1.bet_input._value = m2.bet_input._value = "1000"
            lock = backend.get_user_lock(uid)
            await lock.acquire()
            a = asyncio.ensure_future(m1.on_submit(FakeInteraction(uid, "x")))
            b = asyncio.ensure_future(m2.on_submit(FakeInteraction(uid, "x")))
            await asyncio.sleep(0.05)
            lock.release()
            await asyncio.gather(a, b)
        run(two())
    st = app._bj_state.get(uid)
    assert st is not None
    # Only ONE bet may have been taken (a natural blackjack could refund/pay it).
    if not st.get("done"):
        assert d["money"] == 4000, d["money"]
    assert any("Finish your current hand" in m for m in h.ephemerals) or st.get("done")


# ── tribes ────────────────────────────────────────────────────
def test_tribe_dropdown_leave_matches_button_leave():
    _reset()
    _mk_tribe("Pack", "10", members=["11"], recruits=["12"])
    with Harness():
        run(_click("12", "tribe:action_select:12", ["leave"]))
    td = app.tribe_data["Pack"]
    assert "12" not in td["roles"]["recruits"], "recruit must actually leave the roster"
    assert app.data["12"]["tribe"] is None
    assert app.data["12"].get("tribe_left_ts", 0) > 0, "rejoin cooldown must be stamped"


def test_tribe_leader_leave_counts_recruits():
    _reset()
    _mk_tribe("Pack", "10", recruits=["12"])        # leader + ONLY a recruit
    with Harness() as h:
        run(_click("10", "tribe:action_select:10", ["leave"]))
    assert "Pack" in app.tribe_data, "tribe must not be deleted out from under the recruit"
    assert app.data["12"]["tribe"] == "Pack"


def test_tribe_ban_blocks_invite_and_dm_accept():
    _reset()
    td = _mk_tribe("Pack", "10")
    _mk_user("20")
    td["banned"].append("20")
    ok, msg = run(app._tribe_do_invite("10", "Pack", "20", "x"))
    assert not ok and "banned" in msg.lower()
    # A stale DM invite button must not let a banned user in either.
    td["invites"].append("20")
    app.data["20"]["tribe_inv"] = "Pack"
    with Harness():
        run(_click("20", f"tribe_invite_accept:20:Pack"))
    assert app.data["20"]["tribe"] is None
    assert "20" not in td["roles"]["recruits"]


def test_tribe_dm_accept_requires_real_invite():
    _reset()
    _mk_tribe("Pack", "10")
    _mk_user("21")
    with Harness():                                   # never invited
        run(_click("21", "tribe_invite_accept:21:Pack"))
    assert app.data["21"]["tribe"] is None


def test_tribe_transfer_requires_current_officer():
    _reset()
    td = _mk_tribe("Pack", "10", members=["11"])
    with Harness():
        run(_click("10", "tribe:transfer_confirm:10", ["11"]))    # 11 is a plain member
    assert td["roles"]["leader"] == "10"
    assert "11" not in td["roles"]["officer"]


def test_tribe_officer_cannot_ban_officer():
    _reset()
    td = _mk_tribe("Pack", "10", officers=["11", "12"])
    with Harness():
        run(_click("11", "tribe:ban_action:11", ["ban:12"]))
    assert "12" in td["roles"]["officer"] and "12" not in td["banned"]


def test_tribe_shop_ignores_client_price():
    _reset()
    td = _mk_tribe("Pack", "10")
    app.data["10"]["gems"] = 100
    with Harness():
        run(_click("10", "tribe:shop:luck_boost:0:500:10"))   # forged cost 0 / amount 500
    assert app.data["10"]["gems"] == 50, app.data["10"]["gems"]
    assert td["luck_boost"] == 5, td["luck_boost"]


def test_tribe_shop_requires_officer():
    _reset()
    td = _mk_tribe("Pack", "10", members=["11"])
    app.data["11"]["gems"] = 100
    with Harness():
        run(_click("11", "tribe:shop:luck_boost:50:5:11"))
    assert app.data["11"]["gems"] == 100 and td["luck_boost"] == 0


# ── events / mail / parsing ───────────────────────────────────
def test_fox_over_cap_run_is_inert():
    _reset()
    uid = "1101"
    _mk_user(uid)
    app.start_event("thieving_fox")
    st = app._player_event(uid)
    st.update({"lead": 5, "perfect": True, "parcels": 0, "recovered": 0})
    app.data[uid]["event_day"] = {"tag": app.today_utc(), "n": game_data.FOX_ATTEMPTS_DAY}
    for _ in range(50):
        app.fox_route(uid, "wait")            # 100%-safe route, spammed past the cap
    assert st["lead"] == 5 and st["parcels"] == 0
    assert "Outfoxed" not in app.data[uid].get("earned_titles", [])


def test_event_shop_title_not_rebought():
    _reset()
    uid = "1102"
    _mk_user(uid)
    app.start_event("shipwreck")
    st = app._player_event(uid)
    st["banked"] = 1000
    idx = next(i for i, it in enumerate(game_data.SHIP_SHOP) if it.get("title"))
    title = game_data.SHIP_SHOP[idx]["title"]
    app.data[uid]["earned_titles"] = [title]
    msg = app.event_shop_buy(uid, "shipwreck", idx)
    assert "already own" in msg and st["banked"] == 1000


def test_mail_mark_unread_sticks():
    _reset()
    uid = "1103"
    d = _mk_user(uid)
    d["gift_mails"] = [{"sender_name": "a", "amt_str": "x", "message": "m", "ts": 1, "read": True}]
    with Harness():
        run(_click(uid, f"mail:gift_toggle:0:{uid}"))
    assert d["gift_mails"][0]["read"] is False


def test_parse_amount_rejects_non_finite():
    for bad in ("1e999", "inf", "nan", "-inf", "1e999k", "abc", ""):
        assert game_data.parse_amount(bad) is None, bad
    assert game_data.parse_amount("2.5M") == 2_500_000


# ── gifting / lookups ─────────────────────────────────────────
def test_gem_gift_limits():
    _reset()
    uid = "1201"
    d = _mk_user(uid, level=1, gems=1000)
    assert app._gem_gift_block(uid, 10)                       # level gate
    d["level"] = 50
    d["joined_date"] = app.today_utc()
    assert app._gem_gift_block(uid, 10)                       # account-age gate
    d["joined_date"] = "2020-01-01"
    assert app._gem_gift_block(uid, 10) is None
    d["gem_gift_day"] = {"tag": app.today_utc(), "sent": app.GIFT_GEMS_DAILY_CAP - 5}
    assert app._gem_gift_block(uid, 10)                       # daily cap
    d["gem_gift_day"] = {"tag": "1999-01-01", "sent": 10 ** 6}
    assert app._gem_gift_block(uid, 10) is None               # stale day resets


def test_tribe_invite_does_not_create_accounts():
    _reset()
    _mk_tribe("Pack", "10")
    ok, msg = run(app._tribe_do_invite("10", "Pack", "777777", "x"))
    assert not ok and "777777" not in app.data


# ── economy ledger ────────────────────────────────────────────
def _capture_ledger():
    calls = []
    real = app.log_economy_event

    def cap(uid, source, delta, bal, currency="money"):
        calls.append((uid, source, delta, bal, currency))

    app.log_economy_event = cap
    return calls, real


def test_reset_logs_wipe():
    _reset()
    uid = "1301"
    _mk_user(uid, money=2_000_000_000, gems=6000)
    calls, real = _capture_ledger()
    try:
        app.apply_account_reset(uid)
    finally:
        app.log_economy_event = real
    assert (uid, "reset wipe", -2_000_000_000, 0, "money") in calls
    assert (uid, "reset wipe", -5900, 100, "gems") in calls


def test_new_user_logs_starting_balance():
    _reset()
    calls, real = _capture_ledger()
    try:
        app.data.pop("1302", None)
        app.init_user("1302")
    finally:
        app.log_economy_event = real
    assert ("1302", "starting balance", 100, 100, "gems") in calls
    assert any(c[1] == "starting balance" and c[4] == "money" for c in calls)


def test_crate_money_ladder_monotonic():
    def avg(c):
        pool = game_data.CRATE_REWARDS[c]
        t = sum(w for w, *_ in pool)
        return sum(w * (d["min"] + d["max"]) / 2 for w, k, d in pool if k == "money") / t
    names = ["Rare Crate", "Epic Crate", "Legendary Crate", "Mythic Crate"]
    vals = [avg(n) for n in names]
    assert vals == sorted(vals), dict(zip(names, vals))
    assert vals[-1] < 100_000_000, "Mythic average money must stay bounded"


# ── emoji ─────────────────────────────────────────────────────
def test_menu_uses_registry_icons_not_literals():
    _reset()
    uid = "1501"
    _mk_user(uid, level=24, money=166_902, gems=75)
    import json
    blob = json.dumps(app.build_menu_components(uid, "Tester"), ensure_ascii=False)
    # 🏹 / 🎯 / 📬 have custom art in the registry; the menu must use it.
    for glyph in ("🏹", "🎯", "📬", "📦"):
        assert glyph not in blob or glyph in game_data.EMOJI.values(), glyph
    assert game_data.EMOJI["bow"] in blob and game_data.EMOJI["target"] in blob


def test_text_default_glyphs_get_emoji_presentation():
    assert game_data.EMOJI["hp"].endswith("️")        # ❤ renders as an emoji, not a text glyph
    assert game_data.EMOJI["gear"].endswith("️")


def test_adopt_named_emojis_switches_placeholders():
    saved = dict(game_data.EMOJI)
    try:
        got = game_data.adopt_named_emojis({"heart": "<:heart:123456789012345678>",
                                            "bow": "<:bow:1>",             # already custom: untouched
                                            "wolf": "garbage"})            # invalid: ignored
        assert "heart" in got and "hp" in got            # alias follows its source
        assert game_data.EMOJI["hp"] == "<:heart:123456789012345678>"
        assert game_data.EMOJI["bow"] == saved["bow"]
        assert game_data.EMOJI["wolf"] == saved["wolf"]
    finally:
        game_data.EMOJI.clear()
        game_data.EMOJI.update(saved)


# ── data safety ───────────────────────────────────────────────
def test_saves_disabled_after_lock_loss():
    _reset()
    run(_ensure_db())
    uid = "1401"
    _mk_user(uid)
    backend.disable_saves()
    try:
        run(backend.bulk_save_users({uid: app.data[uid]}))
        async def count():
            async with backend._pool.execute("SELECT COUNT(*) FROM users WHERE user_id=?", (uid,)) as c:
                return (await c.fetchone())[0]
        assert run(count()) == 0, "a stale instance must not write"
    finally:
        backend.SAVES_DISABLED = False
    run(backend.bulk_save_users({uid: app.data[uid]}))
    assert run(count()) == 1


def test_atomic_write_leaves_no_temp_file():
    path = os.path.join(tempfile.gettempdir(), "ih_atomic_test.json")
    app._write_text(path, '{"a": 1}')
    app._write_text(path, '{"a": 2}')
    assert open(path, encoding="utf-8").read() == '{"a": 2}'
    assert not os.path.exists(path + ".tmp")
    os.remove(path)


def test_db_backup_roundtrip():
    run(_ensure_db())
    d = tempfile.mkdtemp()
    p = run(backend.backup_database(d, keep=2))
    assert p and os.path.getsize(p) > 0
    for _ in range(3):
        time.sleep(1.1)
        run(backend.backup_database(d, keep=2))
    assert len([f for f in os.listdir(d) if f.endswith(".db")]) == 2


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
