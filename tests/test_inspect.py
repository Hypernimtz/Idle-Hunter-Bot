"""
Item ledger + /inspect admin tools.

Runs without pytest:  python tests/test_inspect.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_inspect_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr   # noqa: E402
import app                # noqa: E402
import backend            # noqa: E402

run = tr.run
ADMIN = "900"


def _reset():
    tr._reset()
    app._inv_touched.clear()
    app._inv_shadow.clear()
    app._insp_state.clear()
    backend._item_buffer.clear()
    run(backend._pool.execute("DELETE FROM item_log"))
    run(backend._pool.execute("DELETE FROM economy_log"))
    run(backend._pool.commit())
    if ADMIN not in app.BOT_ADMIN_ID:
        app.BOT_ADMIN_ID.append(ADMIN) if isinstance(app.BOT_ADMIN_ID, list) else app.BOT_ADMIN_ID.add(ADMIN)


def _baseline(uid):
    app._inv_shadow[uid] = app._inv_snapshot(app.data[uid])


def _change(uid, src, fn):
    with app.inv_source(src):
        fn()
        app.mark_user_dirty(uid)
    return app.inv_flush_touched()


def _log(uid, **kw):
    rows, total = run(backend.ledger_query(uid, **kw))
    return rows, total


# ── the ledger ────────────────────────────────────────────────

def test_gains_are_logged_with_the_source_and_first_sight_is_just_a_baseline():
    _reset()
    tr._mk_user("1")
    app.data["1"].setdefault("ammo_inv", {})["Silver Bullet"] = 5
    app.mark_user_dirty("1")
    assert app.inv_flush_touched() == 0                      # never seen before -> baseline, no row
    n = _change("1", "btn:shop:ammo_buy", lambda: app.data["1"]["ammo_inv"].__setitem__("Silver Bullet", 55))
    assert n == 1
    rows, total = _log("1")
    assert total == 1 and rows[0]["kind"] == "ammo" and rows[0]["name"] == "Silver Bullet"
    assert rows[0]["delta"] == 50 and rows[0]["balance_after"] == 55 and rows[0]["source"] == "btn:shop:ammo_buy"


def test_every_tracked_kind_and_tools_are_covered_and_losses_are_logged():
    _reset()
    tr._mk_user("2")
    _baseline("2")

    def grant():
        d = app.data["2"]
        d.setdefault("crate_inv", {})["Epic Crate"] = 2
        d.setdefault("items", {})["War Horn"] = 1
        d.setdefault("myth_items", {})["Bigfoot Hair"] = 1
        d.setdefault("shards", {})["epic"] = 3
        d.setdefault("healing_inv", {})["Bandage"] = 4
        d.setdefault("owned_tools", []).append("Shortbow")
    _change("2", "admin grant", grant)
    kinds = {r["kind"] for r in _log("2")[0]}
    assert {"crate", "item", "trophy", "shard", "heal", "tool"} <= kinds
    _change("2", "btn:market:buy", lambda: app.data["2"]["crate_inv"].__setitem__("Epic Crate", 0))
    spent = _log("2", kinds=["crate"])[0][0]
    assert spent["delta"] == -2 and spent["source"] == "btn:market:buy"


def test_hunting_spend_is_not_logged_but_hunting_gains_are():
    _reset()
    tr._mk_user("3")
    app.data["3"].setdefault("ammo_inv", {})["Wooden Arrow"] = 100
    app.data["3"].setdefault("shards", {})["common"] = 0
    _baseline("3")
    _change("3", "btn:hunt:again", lambda: app.data["3"]["ammo_inv"].__setitem__("Wooden Arrow", 99))
    assert _log("3")[1] == 0                                    # one arrow burned: no row
    _change("3", "btn:hunt:again", lambda: app.data["3"]["shards"].__setitem__("common", 1))
    rows = _log("3")[0]
    assert len(rows) == 1 and rows[0]["kind"] == "shard" and rows[0]["source"] == "btn:hunt:again"


def test_clicks_are_tagged_with_their_button_automatically():
    _reset()
    tr._mk_user("4", money=10 ** 7)
    _baseline("4")
    with tr.Harness():
        run(tr._click("4", "shop:heal_buy:Bandage:4"))
    assert app.data["4"].get("healing_inv", {}).get("Bandage", 0) == 1
    rows = _log("4", kinds=["heal"])[0]
    assert rows and rows[0]["source"] == "btn:shop:heal_buy" and rows[0]["delta"] == 1
    money = _log("4", kinds=["money"])[0]
    assert money and money[0]["delta"] < 0                       # the ◈ side comes from economy_log, merged in


def test_payouts_carry_their_own_source():
    _reset()
    tr._mk_user("5")
    _baseline("5")
    g = {"id": "ledg01", "kind": "giveaway", "guild_id": 1, "channel_id": 2, "message_id": 3, "host": "H",
         "created_ts": time.time(), "ends_ts": time.time() + 60, "status": "active",
         "prize": {"type": "crate", "amount": 2, "name": "Epic Crate"}, "winners_n": 1, "min_level": 1,
         "entrants": {"5": {"ts": 1}}, "winners": [], "paid": []}
    app._giveaways[g["id"]] = g

    async def _noop(*a, **k):
        return {"id": "1"}
    app._gw_post = app._gw_edit_card = _noop
    run(app.gw_finish("ledg01"))
    app.inv_flush_touched()
    rows = _log("5", kinds=["crate"])[0]
    assert rows and rows[0]["source"] == "giveaway" and rows[0]["delta"] == 2
    app._giveaways.pop("ledg01", None)


def test_log_filters_search_pagination_and_provenance():
    _reset()
    tr._mk_user("6")
    _baseline("6")
    inv = app.data["6"].setdefault("ammo_inv", {})
    for i, src in enumerate(["btn:shop:ammo_buy", "giveaway", "btn:shop:ammo_buy", "modal:AmmoBuyModal"], 1):
        _change("6", src, lambda i=i: inv.__setitem__("Hollow Point", inv.get("Hollow Point", 0) + 10 * i))
    _change("6", "btn:market:sell", lambda: inv.__setitem__("Hollow Point", inv["Hollow Point"] - 5))
    assert _log("6", kinds=["ammo"])[1] == 5
    assert _log("6", search="giveaway")[1] == 1
    assert _log("6", search="hollow")[1] == 5                    # matches the item name too
    page1, total = _log("6", limit=2, offset=0)
    page3, _ = _log("6", limit=2, offset=4)
    assert total == 5 and len(page1) == 2 and len(page3) == 1
    assert page1[0]["source"] == "btn:market:sell"               # newest first
    prov = run(backend.item_provenance("6", "hollow point"))     # case-insensitive
    by_src = {r["source"]: r["total"] for r in prov["gained"]}
    assert by_src == {"btn:shop:ammo_buy": 40, "giveaway": 20, "modal:AmmoBuyModal": 40}, by_src
    assert prov["spent"][0]["source"] == "btn:market:sell" and prov["spent"][0]["total"] == -5
    assert len(prov["recent"]) == 5


def test_who_ranks_by_gain_and_names_the_main_source():
    _reset()
    for u in ("7", "8"):
        tr._mk_user(u)
        _baseline(u)
    _change("7", "giveaway", lambda: app.data["7"].setdefault("ammo_inv", {}).__setitem__("Void Round", 900))
    _change("8", "btn:shop:ammo_buy", lambda: app.data["8"].setdefault("ammo_inv", {}).__setitem__("Void Round", 40))
    rows = run(backend.item_who("void round", 7))
    assert [r["user_id"] for r in rows] == ["7", "8"]
    assert rows[0]["top_source"] == "giveaway" and rows[0]["gained"] == 900


# ── the /inspect panels and commands ──────────────────────────

def test_resolve_by_id_mention_name_and_fragment():
    _reset()
    tr._mk_user("11")
    tr._mk_user("12")
    app.data["11"]["username"] = "Alpha Hunter"
    app.data["12"]["username"] = "Beta Hunter"
    assert app._insp_resolve("11") == ("11", "")
    assert app._insp_resolve("<@!12>") == ("12", "")
    assert app._insp_resolve("alpha hunter")[0] == "11"
    assert app._insp_resolve("alph")[0] == "11"
    uid, why = app._insp_resolve("hunter")
    assert uid is None and "2" in why
    assert app._insp_resolve("nobody-here")[0] is None and app._insp_resolve("")[0] is None


def test_panels_render_and_stay_within_discord_limits():
    _reset()
    tr._mk_user("13")
    d = app.data["13"]
    d["username"] = "Whale"
    d["ammo_inv"] = {f"Ammo{i}": i + 1 for i in range(30)}
    d["tribe"] = None
    d["is_tester"] = True
    _baseline("13")
    _change("13", "giveaway", lambda: d["ammo_inv"].__setitem__("Ammo1", 99))
    user = run(app.build_inspect_user_components(ADMIN, "13"))
    blob = json.dumps(user, ensure_ascii=False)
    assert "Whale" in blob and "TESTER" in blob and f"insp:log:open:13:{ADMIN}" in blob
    app._insp_state[ADMIN] = {"target": "13", "kinds": None, "search": "", "days": None, "page": 0}
    log = run(app.build_inspect_log_components(ADMIN))
    assert "giveaway" in json.dumps(log, ensure_ascii=False) and "Ammo1" in json.dumps(log, ensure_ascii=False)
    item = run(app.build_inspect_item_components("13", "Ammo1", None))
    assert "How they got it" in json.dumps(item, ensure_ascii=False)
    for comps in (user, log, item):
        for c in tr_walk(comps):
            if c.get("type") == 10:
                assert len(c["content"]) <= 4000
            if c.get("custom_id"):
                assert len(c["custom_id"]) <= 100


def tr_walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from tr_walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from tr_walk(v)


def test_buttons_are_admin_only_and_paginate():
    _reset()
    tr._mk_user("14")
    tr._mk_user("15")
    d = app.data["14"]
    _baseline("14")
    for i in range(20):
        _change("14", f"src{i}", lambda i=i: d.setdefault("items", {}).__setitem__("War Horn", i + 1))
    seen = []

    async def grab(interaction, comps):
        seen.append(json.dumps(comps, ensure_ascii=False))
    with tr.Harness() as h:
        app.smart_update_v2 = grab
        run(tr._click(ADMIN, f"insp:log:open:14:{ADMIN}"))
        assert "page 1/3" in seen[-1]
        run(tr._click(ADMIN, f"insp:log:next:14:{ADMIN}"))
        assert "page 2/3" in seen[-1]
        run(tr._click(ADMIN, f"insp:log:prev:14:{ADMIN}"))
        assert "page 1/3" in seen[-1]
        run(tr._click(ADMIN, f"insp:log:cash:14:{ADMIN}"))
        assert app._insp_state[ADMIN]["kinds"] == ["money", "gems"]
        run(tr._click(ADMIN, f"insp:user:14:{ADMIN}"))
        assert "Level" in seen[-1]
        n = len(seen)
        run(tr._click("15", f"insp:log:open:14:{ADMIN}"))        # someone else's panel
        assert len(seen) == n and "Admins only" in h.ephemerals[-1]


def test_commands_run_end_to_end_and_are_admin_gated():
    _reset()
    tr._mk_user("16")
    app.data["16"]["username"] = "Findme"
    _baseline("16")
    _change("16", "giveaway", lambda: app.data["16"].setdefault("ammo_inv", {}).__setitem__("Lead Ball", 77))
    cmds = {c.name: c for c in app.inspect_group.commands}
    assert set(cmds) == {"user", "log", "item", "who", "search", "export", "actions", "economy", "status", "bio"}
    assert all(c.checks for c in cmds.values())                  # every one is admin-gated
    out = []

    async def follow(interaction, comps, *, ephemeral=False):
        out.append(json.dumps(comps, ensure_ascii=False))

    async def eph(interaction, msg, color=0):
        out.append(msg)
    with tr.Harness():
        app.send_v2_followup, app.send_ephemeral_v2 = follow, eph
        it = lambda: tr.FakeInteraction(ADMIN, "x")
        run(cmds["user"].callback(it(), "Findme"))
        assert "Findme" in out[-1]
        run(cmds["log"].callback(it(), "16", "ammo", "give", 7))
        assert "Lead Ball" in out[-1]
        run(cmds["item"].callback(it(), "16", "lead ball"))
        assert "How they got it" in out[-1] and "giveaway" in out[-1]
        run(cmds["who"].callback(it(), "Lead Ball", 7))
        assert "Findme" in out[-1] and "giveaway" in out[-1]
        run(cmds["who"].callback(it(), "Nothing Ever", 7))
        assert "No recorded changes" in out[-1]
        run(cmds["search"].callback(it(), "find", "level"))
        assert "Findme" in out[-1]
        run(cmds["search"].callback(it(), "zzzz", "level"))
        assert "No players match" in out[-1]
        run(cmds["user"].callback(it(), "no such person"))
        assert "No player found" in out[-1]
        run(cmds["actions"].callback(it(), "", 5))
        assert out[-1]
    line = app._insp_export_line(_log("16")[0][0])
    assert "ammo:Lead Ball" in line and "+77" in line and "giveaway" in line


def test_export_sends_the_whole_log_as_a_text_file():
    from types import SimpleNamespace
    _reset()
    tr._mk_user("17")
    _baseline("17")
    for i in range(3):
        _change("17", f"src{i}", lambda i=i: app.data["17"].setdefault("ammo_inv", {}).__setitem__("Iron Arrow", (i + 1) * 5))
    sent = {}

    async def send(**kw):
        sent.update(kw)
    it = tr.FakeInteraction(ADMIN, "x")
    it.followup = SimpleNamespace(send=send)
    cmd = next(c for c in app.inspect_group.commands if c.name == "export")
    with tr.Harness():
        run(cmd.callback(it, "17", 7))
    text = sent["file"].fp.read().decode("utf-8")
    assert sent["ephemeral"] is True and sent["file"].filename == "ledger_17.txt"
    assert text.count("ammo:Iron Arrow") == 3 and "src0" in text and "src2" in text


def test_shop_purchases_record_which_item_and_which_button():
    _reset()
    tr._mk_user("30", gems=5000, level=900)
    app.maintenance_mode = False
    app._data_loaded_ok = True
    _baseline("30")
    with tr.Harness():
        run(tr._click("30", "shop:tool_buy:30", ["Cosmic RPG"]))
    assert "Cosmic RPG" in app.data["30"]["owned_tools"]
    gems = _log("30", kinds=["gems"])[0]
    assert gems and gems[0]["source"] == "shop tool" and gems[0]["detail"] == "Cosmic RPG"
    assert gems[0]["ctx"] == "btn:shop:tool_buy"
    tool = _log("30", kinds=["tool"])[0]
    assert tool and tool[0]["name"] == "Cosmic RPG"
    line = app._insp_line(gems[0])
    assert "Cosmic RPG" in line and "shop tool" in line and "btn:shop:tool_buy" in line
    assert "Cosmic RPG" in app._insp_export_line(gems[0])
    # the detail is searchable
    assert _log("30", search="cosmic")[1] >= 2
    assert _log("30", search="nonexistent-thing")[1] == 0


def test_gifts_and_market_name_the_other_player():
    _reset()
    tr._mk_user("31", money=1000)
    tr._mk_user("32")
    async def go():
        app.spend_money("31", 500, "gift send", "to 32")       # economy events are logged from inside the loop
        app.add_money("32", 500, "gift receive", "from 31")
        await asyncio.sleep(0.05)
        await backend.flush_economy_buffer()
    run(go())
    sent = _log("31", kinds=["money"])[0][0]
    got = _log("32", kinds=["money"])[0][0]
    assert sent["detail"] == "to 32" and got["detail"] == "from 31"


def test_economy_dashboard_skips_testers_and_admin_sources():
    _reset()
    tr._mk_user("41", money=1000)
    tr._mk_user("42", money=1000)
    app.data["42"]["is_tester"] = True
    async def go():
        app.add_money("41", 700, "hunt sale")
        app.add_money("41", 5_000_000, "admin grant")           # admin source -> excluded
        app.add_money("42", 900, "coinflip win")                # tester account -> excluded
        app.spend_money("41", 200, "shop tool")
        app.spend_money("42", 300, "coinflip bet")              # tester account -> excluded
        await asyncio.sleep(0.05)
        return await backend.economy_summary("money", exclude_users=["42"])
    s = run(go())
    assert s["minted_all"] == 700 and s["burned_all"] == 200, s
    assert [r[0] for r in s["top_earn"]] == ["hunt sale"]
    assert [r[0] for r in s["top_spend"]] == ["shop tool"]
    # exclusions are opt-out, so raw figures stay reachable
    raw = run(backend.economy_summary("money", exclude_admin=False))
    assert raw["minted_all"] > 5_000_000
    text = run(app._economy_dashboard_text())
    assert "admin grant" not in text and "coinflip" not in text and "Excludes tester" in text


def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(tr._ensure_db())
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
