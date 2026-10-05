"""
Tribe treasury (deposit / vote / upgrades), emblems, the weekly tribe boss, and the
versioned update log + website changelog payload.

Runs without pytest:  python tests/test_tribe_treasury.py
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

os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_treasury_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import discord.ext.commands as _c  # noqa: E402
_c.Bot.run = lambda *a, **k: None

import app          # noqa: E402
import backend      # noqa: E402
import game_data    # noqa: E402
import leaderboard_push  # noqa: E402

_DB_READY = False


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


def _mk_tribe(name, leader, officers=(), members=(), recruits=(), level=5):
    td = {"roles": {"leader": leader, "officer": list(officers), "members": list(members),
                    "recruits": list(recruits)},
          "invites": [], "banned": [], "luck_boost": 0, "sell_price_boost": 0, "xp_boost": 0,
          "max_members": 10, "level": level, "xp": 0, "description": ""}
    app._ensure_tribe_fields(td)
    app.tribe_data[name] = td
    for u in [leader, *officers, *members, *recruits]:
        if u not in app.data:
            _mk_user(u)
        app.data[u]["tribe"] = name
    return td


def _in_tx(tname, fn, uid="L"):
    async def go():
        async with app.user_tribe_transaction(uid, tname):
            return fn()
    return run(go())


# ── treasury ──────────────────────────────────────────────────

def test_deposit_is_one_way_and_validated():
    _reset()
    td = _mk_tribe("T", "L", members=["M1"], recruits=["R1"])
    app.data["M1"].update(money=50_000, gems=30)
    ok, _ = run(app._treasury_deposit("M1", 20_000, 10))
    assert ok and td["treasury"]["money"] == 20_000 and td["treasury"]["gems"] == 10
    assert app.data["M1"]["money"] == 30_000 and app.data["M1"]["gems"] == 20
    assert td["treasury"]["deposited"]["M1"] == {"money": 20_000, "gems": 10}
    # below the minimum, broke, empty, and non-member are all refused without charging
    assert not run(app._treasury_deposit("M1", 10, 0))[0]
    assert not run(app._treasury_deposit("M1", 999_999_999, 0))[0]
    assert not run(app._treasury_deposit("M1", 0, 0))[0]
    assert not run(app._treasury_deposit("M1", 0, 999))[0]
    _mk_user("X", money=10_000_000)
    assert not run(app._treasury_deposit("X", 5_000, 0))[0]
    assert app.data["M1"]["money"] == 30_000 and td["treasury"]["money"] == 20_000
    # locked below the unlock level
    td["level"] = 2
    assert not run(app._treasury_deposit("M1", 5_000, 0))[0]


def test_proposal_majority_buys_upgrade_and_recruits_cannot_vote():
    _reset()
    td = _mk_tribe("T", "L", officers=["O"], members=["M1", "M2"], recruits=["R1"])
    td["treasury"]["money"] = 120_000
    # voters = L, O, M1, M2 (recruit excluded) -> need 3
    ok, msg = _in_tx("T", lambda: app._prop_create("T", "L", "luck_boost"))
    assert ok, msg
    assert td["treasury"]["proposal"]["yes"] == ["L"]
    assert not app._prop_vote("T", "R1", True)[0]               # recruit
    assert not _in_tx("T", lambda: app._prop_create("T", "O", "xp_boost"))[0]   # one at a time
    _in_tx("T", lambda: app._prop_vote("T", "M1", True))
    assert td["luck_boost"] == 0                                 # 2/3 yes: not yet
    ok, msg = _in_tx("T", lambda: app._prop_vote("T", "O", True))
    assert ok and td["luck_boost"] == 5 and td["treasury"]["money"] == 70_000
    assert td["treasury"]["proposal"] is None
    assert td["treasury"]["history"][-1]["outcome"] == "passed"


def test_proposal_rejected_expired_and_underfunded():
    _reset()
    td = _mk_tribe("T", "L", officers=["O"], members=["M1", "M2"])
    assert not _in_tx("T", lambda: app._prop_create("T", "L", "luck_boost"))[0]   # pool empty
    td["treasury"]["money"] = 500_000
    assert not _in_tx("T", lambda: app._prop_create("T", "M1", "luck_boost"))[0]  # members can't propose
    assert not _in_tx("T", lambda: app._prop_create("T", "L", "trophy_hall"))[0]  # needs tribe lvl 10
    _in_tx("T", lambda: app._prop_create("T", "L", "xp_boost"))
    _in_tx("T", lambda: app._prop_vote("T", "M1", False))
    assert td["treasury"]["proposal"]
    _in_tx("T", lambda: app._prop_vote("T", "M2", False))        # 2 no of 4 voters -> can't reach 3
    assert td["treasury"]["proposal"] is None and td["xp_boost"] == 0
    assert td["treasury"]["history"][-1]["outcome"] == "rejected"
    # expiry
    _in_tx("T", lambda: app._prop_create("T", "L", "xp_boost"))
    td["treasury"]["proposal"]["ends_ts"] = int(time.time()) - 1
    assert _in_tx("T", lambda: app._prop_check("T"))
    assert td["treasury"]["history"][-1]["outcome"] == "expired"
    # funds drained between proposal and the deciding vote -> fails cleanly, nothing bought
    _in_tx("T", lambda: app._prop_create("T", "L", "xp_boost"))
    td["treasury"]["money"] = 0
    _in_tx("T", lambda: app._prop_vote("T", "O", True))
    _in_tx("T", lambda: app._prop_vote("T", "M1", True))
    assert td["xp_boost"] == 0 and td["treasury"]["history"][-1]["outcome"] == "failed"


def test_upgrade_costs_and_caps():
    assert game_data.tribe_upgrade_cost("luck_boost", 0) == 50_000
    assert game_data.tribe_upgrade_cost("luck_boost", 15) == 200_000
    assert game_data.tribe_upgrade_cost("luck_boost", game_data.MAX_TRIBE_BOOST) == 0
    assert game_data.tribe_upgrade_cost("war_banner", 0) == 500_000
    assert game_data.tribe_upgrade_cost("war_banner", 3) == 0
    assert game_data.tribe_upgrade_cost("nope", 0) == 0
    _reset()
    td = _mk_tribe("T", "L", level=4)
    td["treasury"]["gems"] = 1000
    _in_tx("T", lambda: app._prop_create("T", "L", "contract_board"))   # solo council: passes at once
    assert td["upgrades"]["contract_board"] == 1 and td["treasury"]["gems"] == 850
    assert app._rerolls_left(td) == 2
    td["treasury"]["gems"] = 0


def test_emblem_and_banner_purchase():
    _reset()
    td = _mk_tribe("T", "L", officers=["O"], members=["M1"], level=5)
    td["treasury"]["money"] = 400_000
    assert not _in_tx("T", lambda: app._cosmetic_buy("T", "M1", "emblem", "wolf"))[0]
    assert not _in_tx("T", lambda: app._cosmetic_buy("T", "L", "emblem", "dragon"))[0]    # locked (lvl 15)
    assert _in_tx("T", lambda: app._cosmetic_buy("T", "O", "emblem", "wolf"))[0]
    assert td["emblem"] == "wolf" and td["treasury"]["money"] == 300_000
    assert app._tribe_emblem(td) == "🐺"
    assert not _in_tx("T", lambda: app._cosmetic_buy("T", "L", "emblem", "wolf"))[0]      # already set
    assert _in_tx("T", lambda: app._cosmetic_buy("T", "L", "banner", "azure"))[0]
    assert app._tribe_accent("L", td) == game_data.TRIBE_BANNER_COLORS["azure"][1]
    assert _in_tx("T", lambda: app._cosmetic_buy("T", "L", "emblem", ""))[0]
    assert td["emblem"] == ""


# ── tribe XP bonus + boss ─────────────────────────────────────

def test_war_banner_boosts_tribe_xp():
    _reset()
    td = _mk_tribe("T", "L", level=5)
    base = td["xp"]
    run(app.award_tribe_xp("L", "daily"))
    plain = td["xp"] - base
    assert plain == game_data.TRIBE_XP_DAILY
    td["upgrades"]["war_banner"] = 2
    td["xp"] = 0
    app.data["L"]["tribe_day"] = {}
    run(app.award_tribe_xp("L", "daily"))
    assert td["xp"] == game_data.TRIBE_XP_DAILY + int(game_data.TRIBE_XP_DAILY * 0.2)


def test_boss_spawns_only_from_unlock_level_and_scales():
    _reset()
    low = _mk_tribe("Low", "A", level=game_data.TRIBE_UNLOCK_BOSS - 1)
    assert not low.get("boss")
    hi = _mk_tribe("Hi", "B", level=game_data.TRIBE_UNLOCK_BOSS)
    b = hi["boss"]
    assert b["stage"] == "active" and b["dealt"] == 0 and b["tag"] == app._week_tag()
    spec = app._boss_spec(b["key"])
    scale = max(game_data.TRIBE_CONTRACT_MIN_GROUP, hi["week"]["scale_group"])
    assert b["max_hp"] == int(game_data.TRIBE_BOSS_HP_PER_SCALE * scale * spec["hp_mult"])
    # leveling up mid-week spawns it on the next touch
    low["level"] = game_data.TRIBE_UNLOCK_BOSS
    app._ensure_tribe_fields(low)
    assert low["boss"]["stage"] == "active"


def test_boss_defeat_pays_once_and_rewards_top_damage():
    _reset()
    td = _mk_tribe("T", "L", members=["M1", "M2"], level=game_data.TRIBE_UNLOCK_BOSS)
    td["upgrades"]["trophy_hall"] = 1
    b = td["boss"]
    xp0, money0 = td["xp"], td["treasury"]["money"]
    assert not app._boss_feed(td, "M1", "hunt", 3)               # 4 dmg
    assert b["damage"]["M1"] == 4
    b["damage"]["L"] = 3_000
    b["damage"]["M2"] = 500                                      # a real contributor
    b["dealt"] = b["max_hp"] - 2                                 # next hit finishes it
    assert not app._boss_feed(td, "M2", "hunt", 0)               # 1 dmg ... still alive
    assert app._boss_feed(td, "M2", "hunt", 5)                   # overkill is clamped
    assert b["dealt"] == b["max_hp"] and b["stage"] == "rewarding"
    assert not app._boss_feed(td, "M1", "hunt", 3)               # no damage after death
    mult = 1.2
    assert td["xp"] - xp0 == int(game_data.TRIBE_XP_BOSS * mult)
    scale = max(game_data.TRIBE_CONTRACT_MIN_GROUP, td["week"]["scale_group"])
    assert td["treasury"]["money"] - money0 == int(game_data.TRIBE_BOSS_TREASURY_PER_SCALE * scale * mult)
    assert b["top"] == "L"
    run(app._boss_pay_out("T"))
    run(app._boss_pay_out("T"))                                  # idempotent
    assert app.data["L"]["crate_inv"].get("Epic Crate") == 1
    assert app._boss_spec(b["key"])["title"] in app.data["L"]["earned_titles"]
    assert app.data["M2"]["crate_inv"].get("Rare Crate") == 1
    assert not app.data["M1"].get("crate_inv", {}).get("Rare Crate")     # 4 damage: under the share cutoff
    assert b["stage"] == "done"
    # a new boss is not spawned over a finished one in the same week
    app._boss_ensure(td)
    assert td["boss"] is b


def test_boss_pay_out_survives_unpaid_rollover():
    _reset()
    td = _mk_tribe("T", "L", level=game_data.TRIBE_UNLOCK_BOSS)
    b = td["boss"]
    b["damage"]["L"] = 10
    b["dealt"] = b["max_hp"] - 1
    assert app._boss_feed(td, "L", "hunt", 0)
    b["tag"] = "1999-W01"                                        # week rolled before payout ran
    app._boss_ensure(td)
    assert td["boss"] is b and b["stage"] == "rewarding"          # not replaced while unpaid
    run(app._boss_pay_out("T"))
    assert app.data["L"]["crate_inv"].get("Epic Crate") == 1
    app._boss_ensure(td)
    assert td["boss"] is not b and td["boss"]["tag"] == app._week_tag()


# ── panels ────────────────────────────────────────────────────

def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def test_every_tribe_page_renders_for_every_role():
    _reset()
    td = _mk_tribe("T", "L", officers=["O"], members=["M1"], recruits=["R1"],
                   level=game_data.TRIBE_UNLOCK_BOSS)
    td["treasury"]["money"] = 5_000_000
    td["treasury"]["deposited"]["M1"] = {"money": 1000, "gems": 2}
    _in_tx("T", lambda: app._prop_create("T", "L", "luck_boost"))
    td["emblem"] = "wolf"
    for uid in ("L", "O", "M1", "R1"):
        for page in ("main", "treasury", "boss", "emblem", "contracts", "shop"):
            comps = app.build_tribe_components(uid, "T", page)
            for c in _walk(comps):
                cid = c.get("custom_id")
                if cid:
                    assert len(cid) <= 100, cid
                if c.get("type") == 3:
                    assert 1 <= len(c["options"]) <= 25
                    for o in c["options"]:
                        assert len(o["label"]) <= 100 and len(o.get("description", "")) <= 100, o
    # low-level tribe sees lock messages, not crashes
    low = _mk_tribe("Low", "A", level=1)
    for page in ("treasury", "boss", "emblem"):
        assert "Level" in json.dumps(app.build_tribe_components("A", "Low", page))
    assert "🐺" in json.dumps(app.build_tribe_components("L", "T", "main"), ensure_ascii=False)


# ── real button/select handlers ───────────────────────────────

def test_treasury_handlers_enforce_roles_and_ownership():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_races import Harness, _click
    _reset()
    td = _mk_tribe("T", "10", members=["11", "12"], level=5)
    td["treasury"]["money"] = 200_000
    with Harness() as h:
        # a plain member can't propose; a forged click on someone else's panel is refused
        run(_click("11", "tribe:propose:11", ["luck_boost"]))
        assert td["treasury"]["proposal"] is None and h.ephemerals
        h.ephemerals.clear()
        run(_click("11", "tribe:emblemsel:10", ["wolf"]))
        assert td["emblem"] == "" and h.ephemerals
        run(_click("11", "tribe:emblemsel:11", ["wolf"]))             # own panel, but not an officer
        assert td["emblem"] == ""
        # leader proposes; members vote; the majority (2 of 3) buys it
        n = len(h.panels)
        run(_click("10", "tribe:propose:10", ["luck_boost"]))
        assert td["treasury"]["proposal"] and len(h.panels) == n + 1
        run(_click("11", "tribe:vote:yes:11"))
        assert td["luck_boost"] == 5 and td["treasury"]["money"] == 150_000
        # voting with nothing open is a polite refusal, not a crash
        h.ephemerals.clear()
        run(_click("12", "tribe:vote:no:12"))
        assert h.ephemerals
        # leader buys an emblem; the deposit button opens a modal
        run(_click("10", "tribe:emblemsel:10", ["wolf"]))
        assert td["emblem"] == "wolf" and td["treasury"]["money"] == 50_000
        run(_click("10", "tribe:emblemsel:10", ["none"]))
        assert td["emblem"] == ""
        it = None
        async def deposit_click():
            from test_races import FakeInteraction
            nonlocal it
            it = FakeInteraction("12", "tribe:deposit:12")
            await app._dispatch_component(it)
        run(deposit_click())
        assert it.response.is_done()
        # the nav select reaches every new page
        for page in ("treasury", "boss", "emblem"):
            k = len(h.panels)
            run(_click("10", "tribe:navsel:10", [page]))
            assert len(h.panels) == k + 1


# ── versioned update log + website changelog ──────────────────

def _ts(y, mo, d, h=12):
    import calendar
    return calendar.timegm((y, mo, d, h, 0, 0))


def test_update_versions_backfill_and_stay_stable():
    saved = list(app.UPDATE)
    try:
        app.UPDATE[:] = [
            {"title": "c", "message": "x", "date": _ts(2026, 10, 4, 18)},
            {"title": "a", "message": "x", "date": _ts(2026, 9, 28, 9)},
            {"title": "b", "message": "x", "date": _ts(2026, 10, 4, 8)},
        ]
        assert app._ensure_update_versions()
        assert [u["version"] for u in app.UPDATE] == ["26.10.04.2", "26.09.28.1", "26.10.04.1"]
        assert not app._ensure_update_versions()                 # idempotent
        gone = app.UPDATE.pop(2)                                  # deleting .1 must not renumber .2
        assert gone["version"] == "26.10.04.1"
        assert app.UPDATE[0]["version"] == "26.10.04.2"
        app.UPDATE.append({"title": "d", "message": "x", "date": _ts(2026, 10, 4, 20)})
        app._ensure_update_versions()
        assert app.UPDATE[-1]["version"] == "26.10.04.3"         # continues after the highest
        app.UPDATE.append({"title": "e", "message": "x", "date": _ts(2026, 10, 5, 1)})
        app._ensure_update_versions()
        assert app.UPDATE[-1]["version"] == "26.10.05.1"
        # an edit keeps its version
        app.UPDATE[:] = [{"title": "t", "message": "m", "date": _ts(2026, 10, 4), "moderator": "1", "id": 1}]
        app._ensure_update_versions()
        v = app.UPDATE[0]["version"]
        app._apply_update_edit("1", 0, "t2", "m2")
        assert app.UPDATE[0]["version"] == v and app.UPDATE[0]["title"] == "t2"
    finally:
        app.UPDATE[:] = saved


def test_pending_updates_post_once_per_key():
    saved, old_file = list(app.UPDATE), app.PENDING_UPDATES_FILE
    posted_to_channel = []
    async def fake_broadcast(u):
        posted_to_channel.append(u["key"])
    old_bc, old_save = app._broadcast_update, app.save_config
    tmp = os.path.join(tempfile.gettempdir(), "ih_pending_updates_test.json")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([{"key": "k1", "title": "T1", "message": "M1"},
                       {"key": "k2", "title": "", "message": "no title -> skipped"},
                       {"title": "no key", "message": "skipped"}], f)
        app.PENDING_UPDATES_FILE = tmp
        app.UPDATE[:] = []
        app._broadcast_update, app.save_config = fake_broadcast, lambda: app._ensure_update_versions()
        async def go():
            first = app.post_pending_updates()
            await asyncio.sleep(0)
            second = app.post_pending_updates()      # a restart / reconnect
            await asyncio.sleep(0)
            return first, second
        first, second = run(go())
        assert [u["key"] for u in first] == ["k1"] and second == []
        assert len(app.UPDATE) == 1 and app.UPDATE[0]["version"].count(".") == 3
        assert posted_to_channel == ["k1"]
        app.PENDING_UPDATES_FILE = os.path.join(tempfile.gettempdir(), "does_not_exist.json")
        assert app.post_pending_updates() == []
    finally:
        app.UPDATE[:] = saved
        app.PENDING_UPDATES_FILE = old_file
        app._broadcast_update, app.save_config = old_bc, old_save
        try:
            os.remove(tmp)
        except OSError:
            pass


def test_changelog_payload_is_public_sorted_and_sanitised():
    entries = [
        {"title": "Old", "message": "m", "date": _ts(2026, 9, 28), "version": "26.09.28.1", "moderator": "123456789"},
        {"title": "New B", "message": "Thanks <@12345> <:gem:999> see <t:1790000000:F>", "date": _ts(2026, 10, 4, 18),
         "version": "26.10.04.2", "moderator": "123456789"},
        {"title": "New A", "message": "m", "date": _ts(2026, 10, 4, 8), "version": "26.10.04.1"},
        {"title": "", "message": "", "version": "26.10.04.9"},        # empty -> skipped
        {"title": "No version", "message": "m"},                      # unstamped -> skipped
    ]
    out = leaderboard_push.build_changelog_payload(entries)["changelog"]
    assert [e["version"] for e in out] == ["26.10.04.2", "26.10.04.1", "26.09.28.1"]
    blob = json.dumps(out)
    assert "123456789" not in blob and "moderator" not in blob and "<@" not in blob and "<:" not in blob
    assert "@someone" in out[0]["message"] and ":gem:" in out[0]["message"]
    assert out[0]["date_iso"].startswith("2026-10-04T18:00:00")


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
