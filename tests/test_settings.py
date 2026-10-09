"""
"New Message Per Hunt" setting: the Hunt button either updates its own message in
place (default) or posts a fresh one every time.

Runs without pytest:  python tests/test_settings.py
"""
import asyncio
import os
import sys
import tempfile
from types import SimpleNamespace

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_settings_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr   # noqa: E402  (reuses its Harness / FakeInteraction)
import app                # noqa: E402
import backend            # noqa: E402

run = tr.run


def _hunt(uid, *, ephemeral_source=False):
    """Click Hunt for `uid` and return ('edit'|'new', ephemeral_flag_or_None)."""
    seen = []

    async def edit(interaction, comps):
        seen.append(("edit", None))

    async def new(interaction, comps, *, ephemeral=False):
        seen.append(("new", ephemeral))

    with tr.Harness():
        app.smart_update_v2, app.send_v2_followup = edit, new
        it = tr.FakeInteraction(uid, f"hunt:again:{uid}")
        it.message = SimpleNamespace(flags=SimpleNamespace(ephemeral=ephemeral_source))
        run(app._dispatch_component(it))
    return seen[0] if seen else None


def _fresh(uid, **over):
    tr._reset()
    d = tr._mk_user(uid, **over)
    d["tool"] = "Bare Hands"
    return d


def test_default_is_update_in_place():
    _fresh("1")
    assert app.hunt_new_message("1") is False
    assert _hunt("1") == ("edit", None)


def test_new_message_mode_posts_fresh_messages():
    _fresh("2", hunt_new_message=True)
    assert _hunt("2") == ("new", False)
    _fresh("3", hunt_new_message=True)
    assert _hunt("3", ephemeral_source=True) == ("new", True)   # a private panel stays private


def test_stranger_clicking_your_button_still_gets_their_own_new_message():
    _fresh("4")
    tr._mk_user("5")
    seen = []

    async def edit(interaction, comps):
        seen.append("edit")

    async def new(interaction, comps, *, ephemeral=False):
        seen.append(("new", ephemeral))

    with tr.Harness():
        app.smart_update_v2, app.send_v2_followup = edit, new
        it = tr.FakeInteraction("5", "hunt:again:4")
        it.message = SimpleNamespace(flags=SimpleNamespace(ephemeral=True))
        run(app._dispatch_component(it))
    assert seen and seen[0] == ("new", False), seen          # never edits the owner's message


def test_toggle_flips_and_shows_in_settings_panel():
    d = _fresh("6")
    with tr.Harness() as h:
        run(tr._click("6", "settings:toggle:hunt_new_message:6"))
        assert d["hunt_new_message"] is True and app.hunt_new_message("6")
        run(tr._click("6", "settings:toggle:hunt_new_message:6"))
        assert d["hunt_new_message"] is False
        assert h.panels, "settings panel should re-render after a toggle"
    import json
    assert "New Message Per Hunt" in json.dumps(app.build_settings_components("6"), ensure_ascii=False)
    assert "6" in app._dirty_users


def test_auto_opened_crate_is_a_bullet_list():
    import json
    d = _fresh("7", auto_open_crates=True)
    real = app.roll_catch_drops
    app.roll_catch_drops = lambda *a, **k: {"shard": None, "crate": "Epic Crate"}
    try:
        async def go():
            async with app.user_transaction("7"):
                return app.run_hunt("7")
        result = run(go())
    finally:
        app.roll_catch_drops = real
    assert result.get("ok") and result["catches"], result
    assert result["auto_opened"] and not result["crate_drops"]
    comps = app.build_hunt_components("7", result)
    blocks = [c["content"] for c in comps[0]["components"] if c.get("type") == 10]
    block = next(b for b in blocks if "Auto-opened:" in b)
    # one block per crate: "Auto-opened: <crate name>" then a "* " bullet per thing it gave
    first, *bullets = block.split("\n")[:3]
    assert first.endswith("Epic Crate"), first
    assert bullets and bullets[0].startswith("* "), block
    assert "→" not in block and " · " not in block.split("Auto-opened:")[1].split("\n")[0]
    n = len(result["catches"])
    assert block.count("Auto-opened:") == n and n == len(result["auto_opened"])


def test_crate_charm_is_now_shard_charm_and_old_purchases_carry_over():
    import game_data
    assert "Shard Charm" in game_data.SHOP_BOOST_ITEMS and "Crate Charm" not in game_data.SHOP_BOOST_ITEMS
    d = _fresh("8", gems=1000, shop_bought={"Crate Charm": 3, "Lucky Charm": 1}, boosts={"luck": 5, "sell": 0, "xp": 0, "crate_luck": 3})
    assert app.shop_bought_count(d, "Shard Charm") == 3 and "Crate Charm" not in d["shop_bought"]
    assert d["shop_bought"]["Lucky Charm"] == 1
    with tr.Harness():
        run(tr._click("8", "shop:buy:Crate Charm:8"))      # a button from before the rename still works
    assert d["shop_bought"]["Shard Charm"] == 4 and d["boosts"]["crate_luck"] == 4
    import json
    assert "Shard Charm" in json.dumps(app.build_shop_components("8", "boosts"), ensure_ascii=False)


def test_daily_panel_reminds_you_to_vote():
    import json
    d = _fresh("9")
    d["vote_cd"] = 0
    ready = app.build_daily_components("9")
    blob = json.dumps(ready, ensure_ascii=False)
    assert "Vote reward ready" in blob and "vote:claim:9" in blob and app.VOTE_URL in blob
    row = next(c for c in ready[0]["components"] if c.get("type") == 1)["components"]
    assert len(row) <= 5 and sum(1 for b in row if b["style"] == 5) == 1
    d["vote_cd"] = __import__("time").time() + 3600       # already claimed -> just a countdown, no buttons
    waiting = app.build_daily_components("9")
    blob = json.dumps(waiting, ensure_ascii=False)
    assert "Next vote reward" in blob and "vote:claim" not in blob and app.VOTE_URL not in blob
    claimed = app.build_daily_components("9", claimed=True, reward_type="money", reward_amt=5, streak=2)
    assert "Daily Claimed" in json.dumps(claimed, ensure_ascii=False)


def test_intro_explains_the_bot_and_the_tour_walks_through_it():
    import json
    d = _fresh("12", onboarding={"version": 2, "completed": False, "step": "intro", "starter_pack": None})
    intro = json.dumps(app.build_onboarding_components("12"), ensure_ascii=False)
    for needle in ("hunting RPG", "regions", "Mythical creatures", "Hunting Camp", "Tribes", "Quick Tour", "Track It"):
        assert needle in intro, needle
    assert f"{len(app.MYTHIC_CREATURES)} legendary" in intro
    pages = app._onb_tour_pages()
    assert len(pages) == 4 and all(len(p) < 1800 for p in pages)
    with tr.Harness() as h:
        seen = []

        async def grab(interaction, comps):
            seen.append(json.dumps(comps, ensure_ascii=False))
        app.smart_update_v2 = grab
        run(tr._click("12", "onb:tour:0:12".rsplit(":", 1)[0] + ":12"))
        run(tr._click("12", "onb:tour:2:12"))
        assert "Quick tour · 3/4" in seen[-1] and "Hunting Camp" in seen[-1]
        run(tr._click("12", "onb:tour:exit:12"))
        assert "Quick Tour" in seen[-1] and "IDLE HUNTER" in seen[-1]
        assert d["onboarding"]["step"] == "intro"          # browsing the tour doesn't advance the flow
        run(tr._click("12", "onb:track:12"))
        assert d["onboarding"]["step"] == "catch"


def test_gamble_is_a_group_with_a_command_per_game():
    import json
    names = {c.name for c in app.gamble_group.commands}
    assert names == {"menu", "blackjack", "coinflip", "slots", "roulette", "rps", "dice", "highlow"}
    assert app.gamble_group in app.bot.tree.get_commands()
    assert not any(c.name == "gamble" and not hasattr(c, "commands") for c in app.bot.tree.get_commands())
    _fresh("13")
    expect = {"coinflip": "gamble:cf:", "slots": "gamble:slots:", "blackjack": "gamble:bj:",
              "roulette": "gamble:rl:", "rps": "gamble:rps:", "dice": "gamble:dice:", "highlow": "gamble:hl:"}
    for cmd in app.gamble_group.commands:
        if cmd.name == "menu":
            continue
        seen = []

        async def follow(interaction, comps, *, ephemeral=False):
            seen.append(json.dumps(comps, ensure_ascii=False))
        with tr.Harness():
            app.send_v2_followup = follow
            run(cmd.callback(tr.FakeInteraction("13", "x")))
        assert seen and expect[cmd.name] in seen[0], (cmd.name, seen[:1])
    seen = []
    with tr.Harness():
        async def follow2(interaction, comps, *, ephemeral=False):
            seen.append(json.dumps(comps, ensure_ascii=False))
        app.send_v2_followup = follow2
        menu = next(c for c in app.gamble_group.commands if c.name == "menu")
        run(menu.callback(tr.FakeInteraction("13", "x")))
    assert "gamble:game_select:13" in seen[0]


def test_events_no_longer_discount_or_boost_anything():
    """Admin's Day Off (25% off + x2 income + free ammo) is retired: no event touches prices or income."""
    app.stop_active_event()
    app.start_event("admin_404", "x")
    try:
        assert app.ev_price(1000) == 1000 and app.ev_price(1500, currency="gems") == 1500
        assert app.ev_price(5_000_000, gear=True) == 5_000_000
        assert (app.ev_sell_mult(), app.ev_xp_mult(), app.ev_daily_mult(), app.ev_idle_rate_mult(),
                app.ev_idle_cap_mult(), app.ev_hunt_cd_mult(), app.ev_myth_encounter_mult()) == (1.0,) * 7
        assert app.ev_myth_kill_bonus() == 0 and app.ev_shard_chance() is None and app.ev_crate_chance() is None
        assert not app.ev_ammo_free() and not app.ev_travel_free() and not app.ev_craft_instant()
        assert not app.admin_buff_active()
        # the real purchase path charges the full price
        _fresh("40", gems=5000, money=10 ** 9)
        d = app.data["40"]

        async def buy(currency, price, source):
            async with app.user_transaction("40"):
                return app._shop_purchase("40", currency, price, source)
        m1 = d["money"]
        assert run(buy("money", 1000, "shop ammo"))[0] and m1 - d["money"] == 1000
    finally:
        app.stop_active_event()


def test_animal_fights_show_the_animal_art_top_right():
    import json
    d = _fresh("41")
    d["fight"] = {"kind": "animal", "animal": "Inland Taipan", "eid": "e1", "mhp": 82, "mhp_max": 110,
                  "bonus": "ambush", "log": [], "turn": 1}
    comps = app.build_animal_fight_components("41")
    flat = json.dumps(comps, ensure_ascii=False)
    ico = app.animal_emoji("Inland Taipan")
    if ico.startswith("<"):
        assert '"type": 11' in flat and "cdn.discordapp.com/emojis/" in flat
        assert "ITS HP" in flat and "WILD INLAND TAIPAN" in flat
    else:                                                  # unicode-only animal: plain layout, no thumbnail
        assert '"type": 11' not in flat
    assert "hunt:afight:attack:e1:41" in flat
    out = app.build_animal_fight_outcome_components("41", {"kind": "escape", "animal": "Inland Taipan"})
    assert ('"type": 11' in json.dumps(out, ensure_ascii=False)) == ico.startswith("<")


def test_announcement_hunt_is_public_but_the_other_buttons_stay_private():
    _fresh("42")
    app.maintenance_mode = False
    app._data_loaded_ok = True
    app.data["42"]["tool"] = "Bare Hands"
    seen = []

    async def follow(interaction, comps, *, ephemeral=False):
        seen.append(("public" if not ephemeral else "private", json.dumps(comps, ensure_ascii=False)))
    import json
    with tr.Harness() as h:
        app.send_v2_followup = follow
        run(tr._click("42", "announce:hunt"))
        hunted = [x for x in seen if "hunt:again:42" in x[1]]
        assert hunted and hunted[0][0] == "public", seen
        seen.clear()
        run(tr._click("42", "announce:events"))
        run(tr._click("42", "announce:leaderboard"))
        assert seen and all(kind == "private" for kind, _ in seen), seen


def _components(o):
    """Every Components-V2 component in a payload (anything with a numeric `type`)."""
    if isinstance(o, dict):
        if isinstance(o.get("type"), int):
            yield o
        for v in o.values():
            yield from _components(v)
    elif isinstance(o, list):
        for v in o:
            yield from _components(v)


def test_craft_screen_is_one_focused_section_per_tab():
    import json, time as _t
    d = _fresh("50")
    d["shards"] = {"common": 12, "rare": 5, "epic": 2}
    d["crystals"] = {"common": 3, "rare": 1}
    d["craft_queue"] = [{"rarity": "rare", "done_ts": _t.time() + 300}, {"rarity": "common", "done_ts": _t.time() + 600}]
    seen = {}
    for tab in app.CRAFT_TABS:
        comps = app.build_craft_components("50", tab=tab, notice="NOTICE-LINE")
        flat = json.dumps(comps, ensure_ascii=False)
        seen[tab] = flat
        assert len(list(_components(comps))) <= 40, (tab, len(list(_components(comps))))     # Discord's component cap
        ids = [c["custom_id"] for c in _components(comps) if c.get("custom_id")]
        assert len(ids) == len(set(ids)), (tab, ids)
        assert all(len(i) <= 100 for i in ids)
        assert "NOTICE-LINE" in flat and f"craft:tab:50" in flat and "craft:open:50" in flat
        assert "shards" in flat and "forge" in flat                                 # the one-line summary is always there
        sel = next(c for c in _components(comps) if c.get("custom_id") == "craft:tab:50")
        assert [o["value"] for o in sel["options"] if o.get("default")] == [tab]
    # the tab's own content, and nothing from the other tabs
    assert "craft:queue:50" in seen["crystals"] and "In the forge (2/" in seen["crystals"]
    assert "Common** — 12 shards" in seen["crystals"]
    assert seen["crates"].count("crate:buy:") == len(app.CRATE_TIERS) and "craft:queue" not in seen["crates"]
    assert "Your crystals:" in seen["crates"]
    assert "craft:queue" not in seen["items"] and "crate:buy" not in seen["items"] and "Instant" in seen["items"]
    # nothing owned: friendly, not empty
    d["shards"], d["crystals"], d["craft_queue"] = {}, {}, []
    empty = json.dumps(app.build_craft_components("50", tab="crystals"), ensure_ascii=False)
    assert "No shards or crystals yet" in empty


def test_invite_offers_server_account_and_support_links():
    import json
    _fresh("51")
    url = app.user_install_url()
    assert url.startswith("https://discord.com/oauth2/authorize?client_id=") and "integration_type=1" in url
    assert "scope=applications.commands" in url and "permissions" not in url
    posts = []

    async def fake_request(route, **kw):
        posts.append(kw.get("json"))
        return {}
    real = app.bot.http.request
    app.bot.http.request = fake_request
    try:
        it = tr.FakeInteraction("51", "x")
        it.user.display_name = "tester"
        run(app.invite_cmd.callback(it))
    finally:
        app.bot.http.request = real
    blob = json.dumps(posts[-1], ensure_ascii=False)
    assert "Add to Server" in blob and "Add to Account" in blob and "Support Server" in blob
    assert "integration_type=1" in blob and "scope=bot" in blob.replace("%20", " ").replace("+", " ")
    row = next(c for c in _components(posts[-1]) if c.get("type") == 1)["components"]
    assert len(row) == 3 and all(b["style"] == 5 for b in row)


def test_balance_command_for_yourself_and_for_others():
    import json
    d = _fresh("52", money=1_234_567, gems=89)
    d["inv"] = ["Deer", "Deer", "Rabbit"]
    d["shards"], d["crystals"], d["crate_inv"] = {"common": 4}, {"rare": 2}, {"Epic Crate": 3}
    mine = json.dumps(app.build_balance_components("52", "me"), ensure_ascii=False)
    assert "1,234,567" in mine and "89" in mine and "Bag: **3** animals" in mine
    assert "4 shards" in mine and "2 crystals" in mine and "3 crates" in mine
    assert "hunt:sell_all:52" in mine and "nav:daily:52" in mine and "nav:shop:52" in mine
    tr._mk_user("53", money=777, gems=5)
    theirs = json.dumps(app.build_balance_components("53", "Other", viewer_id="52"), ensure_ascii=False)
    assert "Other's balance" in theirs and "777" in theirs and "Bag:" not in theirs and "hunt:sell_all" not in theirs
    d["inv"] = []
    assert '"disabled": true' in json.dumps(app.build_balance_components("52", "me"))      # nothing to sell
    out = []

    async def follow(interaction, comps, *, ephemeral=False):
        out.append(json.dumps(comps, ensure_ascii=False))

    async def eph(interaction, msg, color=0):
        out.append(msg)
    app.maintenance_mode = False
    app._data_loaded_ok = True
    with tr.Harness():
        app.send_v2_followup, app.send_ephemeral_v2 = follow, eph
        run(app.balance_cmd.callback(tr.FakeInteraction("52", "x")))
        assert "1,234,567" in out[-1]
        other = type("U", (), {"id": 53, "display_name": "Other"})()
        run(app.balance_cmd.callback(tr.FakeInteraction("52", "x"), other))
        assert "Other's balance" in out[-1]
        stranger = type("U", (), {"id": 999, "display_name": "Nobody"})()
        run(app.balance_cmd.callback(tr.FakeInteraction("52", "x"), stranger))
        assert "hasn't started" in out[-1]


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
