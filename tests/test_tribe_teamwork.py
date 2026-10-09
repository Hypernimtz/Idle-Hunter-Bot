"""
Tribe teamwork: hunting parties, territory control, the weekly reward chest, personal
contract rewards, and the small-tribe tuning.

Runs without pytest:  python tests/test_tribe_teamwork.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_teamwork_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402  (shared fixtures; also stubs Bot.run)
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
FOREST = "forest"
WOODS = "woods"


def _reset():
    tt._reset()
    app._territory.update(tag=app._week_tag(), influence={}, owners={}, pending=[])


def _team(name="T", n=3, level=5):
    """A tribe of `n` members named M0..M{n-1} (M0 leads) plus their users."""
    uids = [f"{name}{i}" for i in range(n)]
    for u in uids:
        tt._mk_user(u)
        app.data[u]["tribe"] = name
    td = tt._mk_tribe(name, uids[0], members=uids[1:], level=level)
    return app.tribe_data[name], uids


def _hunt(uid, biome=FOREST, catches=1):
    return run(app.award_tribe_xp(uid, "hunt", catches=catches, biome=biome))


# ── hunting party ─────────────────────────────────────────────

def test_party_tiers_scale_with_distinct_members_in_window():
    _reset()
    td, (a, b, c) = _team("P")
    assert app.tribe_hunt_modifiers(a, FOREST)["party"] == ""            # alone: nothing
    _hunt(a)
    m = app.tribe_hunt_modifiers(b, FOREST)                              # b would be the 2nd hunter
    assert m["party"] == "Duo" and m["party_n"] == 2 and m["rare_mult"] == 1.06 and m["myth_mult"] == 1.0
    _hunt(b)
    m = app.tribe_hunt_modifiers(c, FOREST)                              # 3rd hunter: a real party
    assert m["party"] == "Hunting Party" and m["rare_mult"] == 1.12 and m["myth_mult"] == 1.08
    assert app.tribe_hunt_modifiers(c, WOODS)["party"] == ""             # a different biome does not count
    # the same member hunting twice is still one hunter
    _hunt(a)
    assert app.tribe_hunt_modifiers(a, FOREST)["party_n"] == 2


def test_party_expires_and_ignores_former_members():
    _reset()
    td, (a, b, c) = _team("Q")
    _hunt(a)
    _hunt(b)
    td["party"][FOREST][a] = time.time() - (gd.TRIBE_PARTY_WINDOW_MIN * 60 + 5)   # a hunted too long ago
    assert app.tribe_hunt_modifiers(c, FOREST)["party_n"] == 2
    td["roles"]["members"].remove(b)                                     # b left the tribe
    assert app.tribe_hunt_modifiers(c, FOREST)["party"] == ""
    td["upgrades"]["scout_network"] = 2                                  # +20 min window
    td["roles"]["members"].append(b)
    td["party"][FOREST][a] = time.time() - (gd.TRIBE_PARTY_WINDOW_MIN * 60 + 5)
    assert app.tribe_hunt_modifiers(c, FOREST)["party_n"] == 3


def test_three_hunters_are_enough_for_a_full_tier():
    """The doc's design rule: a tribe of three active members must reach a real bonus."""
    assert any(need <= 3 and sp["rare"] > 1.1 for need, sp in gd.TRIBE_PARTY_TIERS)
    assert gd.TRIBE_EXPEDITION_MIN_MEMBERS == 2
    assert gd.TRIBE_CONTRACT_MIN_GROUP == 3
    assert gd.TRIBE_UNLOCK_BOSS <= 5 and gd.TRIBE_UNLOCK_EXPEDITIONS <= 4


def test_hunt_shows_party_line_and_never_breaks_a_solo_hunt():
    _reset()
    td, (a, b, c) = _team("R")
    app.data[a]["biome"] = "village"                                     # the starter biome needs no better tool
    res = run_hunt_safe(a)
    assert res.get("ok") and res.get("party_line") == ""                 # solo: no line
    _hunt(b, biome="village")
    app.data[a]["hunt_cd"] = 0
    res = run_hunt_safe(a)
    assert res.get("ok") and "Duo" in res["party_line"]
    tt._mk_user("S0")                                                    # no tribe at all
    app.data["S0"]["biome"] = "village"
    assert run_hunt_safe("S0").get("ok")


def run_hunt_safe(uid):
    async def go():
        async with app.user_transaction(uid):
            return app.run_hunt(uid)
    return run(go())


# ── contribution + weekly chest ───────────────────────────────

def test_contribution_points_and_party_bonus():
    _reset()
    td, (a, b, c) = _team("C")
    _hunt(a)
    assert td["week"]["cp"][a] == 1                                      # solo hunt: 1
    _hunt(b)                                                             # b is the 2nd hunter -> party
    assert td["week"]["cp"][b] == 1 + gd.TRIBE_PARTY_CP_BONUS
    assert td["week"]["party_hunts"] == 1
    run(app.award_tribe_xp(a, "daily"))
    assert td["week"]["cp"][a] == 1 + gd.TRIBE_CP_DAILY
    run(app.award_tribe_xp(a, "daily"))                                  # once a day
    assert td["week"]["cp"][a] == 1 + gd.TRIBE_CP_DAILY
    for _ in range(gd.TRIBE_CP_MYTH_CAP_DAY + 2):
        run(app.award_tribe_xp(c, "myth_kill", biome=FOREST))
    assert td["week"]["cp"][c] == gd.TRIBE_CP_MYTH * gd.TRIBE_CP_MYTH_CAP_DAY


def _roll_week(td):
    td["week"]["tag"] = "2000-W01"                                       # next ensure rolls it
    return app._ensure_tribe_fields(td)


def test_weekly_chest_tiers_milestones_and_single_payout():
    _reset()
    td, (a, b, c, d) = _team("W", n=4)
    td["week"]["cp"] = {a: 700, b: 160, c: 40, d: 2000}
    td["roles"]["members"].remove(d)                                     # d left: no chest
    # two milestones (a contract + party hunts) lift every chest one rung
    td["week"]["contracts"][0]["done"] = True
    td["week"]["party_hunts"] = gd.TRIBE_CHEST_PARTY_HUNTS
    _roll_week(td)
    pays = {p["uid"]: p for p in td["payouts"] if p["id"].startswith("chest:")}
    assert set(pays) == {a, b}, pays                                     # c is under the line, d is gone
    assert pays[a]["crate"] == "Epic Crate"                              # Silver (Rare) + 1 rung
    assert pays[b]["crate"] == "Rare Crate"                              # Bronze (Uncommon) + 1 rung
    assert td["last_chest"]["tag"] == "2000-W01" and td["last_chest"]["steps"] == 1
    assert td["week"]["cp"] == {}                                        # fresh week
    _roll_week(td)                                                       # rolling again must not re-queue
    assert len([p for p in td["payouts"] if p["id"].startswith("chest:")]) == 2
    run(app._tribe_pay_queue("W"))
    run(app._tribe_pay_queue("W"))                                       # idempotent
    assert app.data[a]["crate_inv"].get("Epic Crate") == 1
    assert app.data[b]["crate_inv"].get("Rare Crate") == 1
    assert not app.data[c].get("crate_inv")
    assert td["payouts"] == []
    _roll_week(td)
    assert td["payouts"] == []                                           # paid ids stop re-queues


def test_chest_ladder_is_capped_and_no_milestone_means_base_crate():
    assert app._chest_crate("Epic Crate", 2) == "Legendary Crate"
    assert app._chest_crate("Epic Crate", 9) == gd.TRIBE_CHEST_CRATE_LADDER[-1]
    assert app._chest_crate("Uncommon Crate", 0) == "Uncommon Crate"
    assert [app._chest_steps(n) for n in (0, 1, 2, 3, 4, 7)] == [0, 0, 1, 1, 2, 2]
    assert app._chest_tier(149) is None and app._chest_tier(150)[0] == "Bronze"
    assert app._chest_tier(1500)[0] == "Gold"


def test_contracts_pay_each_participant_a_crate():
    _reset()
    td, (a, b, c) = _team("K")
    td["week"]["contrib"] = {b: 5}                                       # b already took part; c did not
    ct = td["week"]["contracts"][0]
    ct["target"], ct["progress"] = 3, 0
    run(app.award_tribe_xp(a, "hunt", catches=3, biome=FOREST))          # a finishes it
    assert ct["done"]
    queued = {p["uid"] for p in td["payouts"] if p["id"].startswith("contract:")}
    assert queued in ({a, b}, set()), queued                             # (award already kicked the payout off)
    run(app._tribe_pay_queue("K"))
    run(asyncio.sleep(0.05))
    assert app.data[a]["crate_inv"].get(gd.TRIBE_CONTRACT_CRATES[0]) == 1
    assert app.data[b]["crate_inv"].get(gd.TRIBE_CONTRACT_CRATES[0]) == 1
    assert not app.data[c].get("crate_inv")
    run(app.award_tribe_xp(a, "hunt", catches=3, biome=FOREST))          # already done: no second payout
    run(asyncio.sleep(0.05))
    assert td["payouts"] == []
    assert app.data[a]["crate_inv"].get(gd.TRIBE_CONTRACT_CRATES[0]) == 1


# ── territory ─────────────────────────────────────────────────

def _influence(tname, biome, per_hunter):
    """Seed influence for `tname` in `biome`: {uid: points}."""
    pts = sum(per_hunter.values())
    app._territory["influence"].setdefault(biome, {})[tname] = {"pts": float(pts), "hunters": dict(per_hunter)}


def _settle():
    app._territory["tag"] = "2000-W01"
    app._territory_settle()


def test_small_active_tribe_beats_large_casual_one():
    _reset()
    small, s_ids = _team("Small", n=3)
    big, b_ids = _team("Big", n=12)
    # same total influence; Small spread it over 3 active hunters, Big over 12 who each barely played
    _influence("Small", FOREST, {u: 200 for u in s_ids})                 # 600 / 3 = 200 each
    _influence("Big", FOREST, {u: 60 for u in b_ids})                    # 720 / 12 = 60 each
    _settle()
    assert app._territory_holder(FOREST) == "Small"
    assert app._tribe_outposts("Small") == [FOREST] and app._tribe_outposts("Big") == []


def test_outpost_needs_a_minimum_and_ignores_drive_by_members():
    _reset()
    td, ids = _team("Lone", n=3)
    _influence("Lone", FOREST, {ids[0]: 40})                             # one hunter, too little
    _influence("Lone", WOODS, {ids[0]: 400, ids[1]: 5, ids[2]: 5})       # only ONE active hunter, floor divisor 3
    _settle()
    assert app._territory_holder(FOREST) == ""
    assert app._territory_holder(WOODS) == "Lone"                        # 410/3 = 136 >= min score


def test_settlement_pays_tribute_logs_and_expires():
    _reset()
    td, ids = _team("Ox", n=3)
    other, o_ids = _team("Fox", n=3)
    _influence("Ox", FOREST, {u: 200 for u in ids})
    _settle()
    app._territory["owners"][WOODS] = {"tribe": "Fox", "until_ts": time.time() + 1000, "score": 150}
    xp0 = td["xp"] + app.tribe_xp_to_next(1) * (td["level"] - 1)
    app._territory_apply_pending()
    assert any("outpost" in e["text"].lower() for e in td["log"])
    assert td["xp"] + sum(app.tribe_xp_to_next(l) for l in range(1, td["level"])) >= xp0 + gd.TRIBE_TERRITORY_TRIBUTE_XP
    # an expired claim is no longer held; a vanished tribe cannot hold one either
    app._territory["owners"][FOREST]["until_ts"] = time.time() - 1
    assert app._territory_holder(FOREST) == ""
    del app.tribe_data["Fox"]
    assert app._territory_holder(WOODS) == ""
    # second settle in the same week is a no-op
    before = json.dumps(app._territory, sort_keys=True, default=str)
    app._territory_settle()
    assert json.dumps(app._territory, sort_keys=True, default=str) == before


def test_holder_members_get_the_outpost_edge_in_that_biome_only():
    _reset()
    td, ids = _team("Hold", n=3)
    _influence("Hold", FOREST, {u: 300 for u in ids})
    _settle()
    m = app.tribe_hunt_modifiers(ids[0], FOREST)
    assert m["outpost"] and abs(m["rare_mult"] - gd.TRIBE_TERRITORY_RARE_MULT) < 1e-9
    assert not app.tribe_hunt_modifiers(ids[0], WOODS)["outpost"]
    _hunt(ids[1])
    m = app.tribe_hunt_modifiers(ids[0], FOREST)                         # party stacks with the outpost
    assert abs(m["rare_mult"] - 1.06 * gd.TRIBE_TERRITORY_RARE_MULT) < 1e-9


def test_hunts_earn_capped_influence_and_garrison_boosts_it():
    _reset()
    td, (a, b, c) = _team("G")
    _hunt(a, catches=2)
    rec = app._territory["influence"][FOREST]["G"]
    assert rec["pts"] == gd.TRIBE_TERRITORY_HUNT_PTS + 2 * gd.TRIBE_TERRITORY_CATCH_PTS
    td["upgrades"]["garrison"] = 2
    before = rec["pts"]
    _hunt(a, catches=0)
    assert abs(rec["pts"] - before - 1.30) < 0.02
    app.data[a]["tribe_day"]["terr"] = gd.TRIBE_TERRITORY_DAY_CAP        # daily cap reached
    before = rec["pts"]
    _hunt(a, catches=5)
    assert rec["pts"] == before
    low = app._team = None
    td["level"] = 1                                                      # below the unlock: no influence
    _hunt(b, catches=3)
    assert b not in rec["hunters"]


def test_week_rollover_of_territory_is_lazy_and_does_not_lose_the_hunt():
    _reset()
    td, ids = _team("Lazy", n=3)
    _influence("Lazy", FOREST, {u: 250 for u in ids})
    app._territory["tag"] = "2000-W01"                                   # stale: nobody ran the maintenance task
    _hunt(ids[0])
    assert app._territory["tag"] == app._week_tag()
    assert app._territory_holder(FOREST) == "Lazy"
    assert app._territory["influence"][FOREST]["Lazy"]["pts"] == 2       # the new week's first hunt is counted


def test_territory_survives_the_runtime_state_roundtrip():
    _reset()
    td, ids = _team("Rt", n=3)
    _influence("Rt", FOREST, {u: 250 for u in ids})
    _settle()
    saved = json.loads(json.dumps(app._encode_runtime_state(), default=str))
    assert saved["territory"]["owners"][FOREST]["tribe"] == "Rt"
    app._territory.update(tag="", influence={}, owners={}, pending=[])
    try:
        os.replace  # noqa: B018
        path = os.path.join(tempfile.gettempdir(), "ih_teamwork_state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(saved, f)
        old = app.RUNTIME_STATE_FILE
        app.RUNTIME_STATE_FILE = path
        try:
            app.load_runtime_state()
        finally:
            app.RUNTIME_STATE_FILE = old
    finally:
        pass
    assert app._territory["owners"][FOREST]["tribe"] == "Rt" and app._territory["tag"] == app._week_tag()


# ── panel pages ───────────────────────────────────────────────

def test_teamwork_pages_render_and_are_reachable_from_the_nav():
    _reset()
    td, (a, b, c) = _team("UI")
    _hunt(a)
    _hunt(b)
    _influence("UI", FOREST, {a: 200, b: 200, c: 200})
    _settle()
    td["last_chest"] = {"tag": "2026-W01", "milestones": ["x"], "steps": 0,
                        "rows": [{"uid": a, "cp": 200, "tier": "Bronze", "crate": "Uncommon Crate"}]}
    for page in ("party", "territory", "chest", "main", "boss"):
        comps = app.build_tribe_components(a, "UI", page)
        blob = json.dumps(comps, ensure_ascii=False)
        assert "UI" in blob or page in ("main", "boss"), page
        assert len(blob) < 12000, (page, len(blob))
        opts = [o["value"] for row in comps[0]["components"] if row.get("type") == 1
                for comp in row["components"] if comp.get("type") == 3 for o in comp["options"]]
        assert {"party", "territory", "chest"} <= set(opts), page
    chest = json.dumps(app.build_tribe_components(a, "UI", "chest"), ensure_ascii=False)
    assert "Weekly Reward Chest" in chest and "Bronze" in chest and "Last week" in chest
    terr = json.dumps(app.build_tribe_components(a, "UI", "territory"), ensure_ascii=False)
    assert "(you)" in terr
    party = json.dumps(app.build_tribe_components(a, "UI", "party"), ensure_ascii=False)
    assert "hunting" in party


def test_new_treasury_upgrades_are_purchasable():
    _reset()
    td, ids = _team("Tre", n=3, level=5)
    for key in ("scout_network", "garrison"):
        assert app._upgrade_blocked(td, key) == "", key
        td["treasury"]["money"] = 10_000_000
        app._upgrade_apply(td, key)
        assert td["upgrades"][key] == 1


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
