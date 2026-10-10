"""
Onboarding redesign (2026-10-09) + the safeguards that must survive it.

A fresh account finishes the tutorial in four clicks — Start Hunting (a REAL hunt through run_hunt), Sell, buy the
Slingshot in the real Tools shop, pick a specialty — and lands in the normal game with one objective. Buttons only work
at their own step (stale clicks can't rewind or replay), rewards are one-time, skipping still offers a specialty, the old
Training Shortbow loan and forced Coyote fight are gone from the flow (the fight is an optional challenge), Rookie Goals and
Hunter's Path are one Beginner Track, and the three starter specialties are different but equal.

Runs without pytest:  python tests/test_onboarding_fixes.py
"""
import asyncio
import json
import os
import random
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_onb_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "8401"


def _fresh_player():
    """A genuinely brand-new account (init_user creates it with onboarding active and 150 coins)."""
    tt._reset()
    app.FEATURE_ONBOARDING_V2 = True
    app.FEATURE_HUNTERS_PATH = True
    app.data.pop(U, None)
    app.init_user(U)
    d = app.data[U]
    d["verify"] = {"needed": False, "time": 10 ** 9, "code": "ABCD"}
    d["_hunt_times"] = []
    d["hunt_cd"] = 0
    return d


def _new_player(step="intro"):
    d = _fresh_player()
    d["onboarding"] = {"version": 2, "completed": False, "step": step, "starter_pack": None}
    return d


def _cid(cid, uid=U):
    it = tr.FakeInteraction(uid, cid)
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    return h


def _click(action, *extra):
    return _cid(":".join(["onb", action, *extra, U]))


def _text(comps):
    return json.dumps(comps, ensure_ascii=False)


def _buttons(comps):
    out = []
    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == 2:
                out.append(n)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(comps)
    return out


# ── the new flow ─────────────────────────────────────────────────────────────

def test_welcome_screen_is_tiny_and_has_no_feature_catalog():
    d = _fresh_player()
    comps = app.build_onboarding_components(U)
    txt = _text(comps)
    labels = [b["label"] for b in _buttons(comps)]
    assert labels == ["Start Hunting", "Skip Tutorial"], labels
    for word in ("Tribes", "Mythical", "Crates", "Hunting Camp", "Quick Tour", "regions"):
        assert word not in txt, word
    assert len(comps[0]["components"][0]["content"]) < 500


def test_fresh_account_finishes_in_four_clicks_with_a_real_hunt_and_a_bought_slingshot():
    d = _fresh_player()
    assert app.onboarding_active(U) and d["money"] == 150
    lifetime_before = d["stats"].get("lifetime_hunts", 0)

    # click 1 — Start Hunting: the normal hunt path, shown with the normal hunt panel
    h = _click("hunt")
    assert d["onboarding"]["step"] == "sell"
    assert d["inv"] == [gd.ONBOARDING_FIRST_ANIMAL]
    assert d["stats"]["lifetime_hunts"] == lifetime_before + 1        # a real hunt, counted like any other
    assert d["record"][gd.ONBOARDING_FIRST_ANIMAL]["count"] == 1 and d["total_caught"] >= 1
    assert d["hunt_cd"] > 0 and d["level"] >= 1 and d["xp"] > 0 or d["level"] > 1
    assert "Sell Your Catch" in _text(h.panels[-1])

    # click 2 — Sell: lands straight in the Tools shop on the Slingshot, with enough to buy it
    h = _click("sell")
    assert d["onboarding"]["step"] == "upgrade" and d["inv"] == []
    price = gd.TOOLS["Slingshot"]["price"]
    assert d["money"] >= price
    shop = _text(h.panels[-1])
    assert "Slingshot" in shop and "Buy your first upgrade" in shop and "shop:tool_buy_acc:Slingshot" in shop

    # click 3 — Buy: the normal purchase; owned and equipped for good
    h = _cid(f"shop:tool_buy_acc:Slingshot:{U}")
    assert "Slingshot" in d["owned_tools"] and d["tool"] == "Slingshot"
    assert d["onboarding"]["step"] == "pack"
    assert [b["label"] for b in _buttons(h.panels[-1])] == [p["label"] for p in gd.STARTER_PACKS.values()]

    # click 4 — pick a specialty: tutorial over, normal game, ONE goal
    h = _click("pack", "trader")
    assert d["onboarding"]["completed"] and not app.onboarding_active(U)
    assert d["onboarding"]["starter_pack"] == "trader"
    done = _text(h.panels[-1])
    assert "Your goal" in done and "Hunt with your new tool" in done and done.count("Your goal") == 1
    assert [s for s in d["stats"]["tools_used"]] == ["Bare Hands"]    # the first hunt used the bare-hands path
    assert app.beginner_objective(U)["step"]["key"] == "hunt_with_tool"

    # and the normal game works right away: a real hunt with the new tool completes the next objective
    d["hunt_cd"] = 0
    random.seed(7)
    res = app.run_hunt(U)
    assert res.get("ok") or res.get("animal_fight_pending") or res.get("tracking_encounter") or res.get("myth_encounter")


def test_the_first_hunt_goes_through_the_real_run_hunt():
    d = _new_player("intro")
    seen = []
    orig = app.run_hunt
    def spy(uid, guided=False):
        seen.append(guided)
        return orig(uid, guided=guided)
    app.run_hunt = spy
    try:
        _click("hunt")
    finally:
        app.run_hunt = orig
    assert seen == [True]


def test_the_first_hunt_is_beginner_safe_whatever_the_dice_say():
    d = _new_player("intro")
    orig_random, orig_chance, orig_enc = random.random, app.animal_encounter_chance, app.MYTH_ENCOUNTER_BASE
    random.random = lambda: 0.0                  # every roll succeeds: tips, mythics, dangerous encounters, drops
    app.animal_encounter_chance = lambda a: 1.0
    try:
        res = app.run_hunt(U, guided=True)
    finally:
        random.random, app.animal_encounter_chance = orig_random, orig_chance
    assert res["ok"] and [c["animal"] for c in res["catches"]] == [gd.ONBOARDING_FIRST_ANIMAL]
    assert res["catches"][0]["is_rare"]                                  # beginner's luck: a Perfect Catch
    assert not d.get("fight") and not d.get("_boss") and not app.tracking_active(U)
    assert not res.get("shard_drops") and not res.get("crate_drops") and not res.get("tip")
    assert res["animal_encounter"] is None and not res.get("myth_encounter")
    value = res["catches"][0]["sell_value"]
    assert value >= gd.TOOLS["Slingshot"]["price"] - 150               # the sale alone nearly always covers the upgrade


def test_selling_always_leaves_enough_for_the_slingshot():
    d = _new_player("sell")
    d["money"] = 0
    d["inv"] = ["House Sparrow"]
    d["_pending_sell"] = 45                                            # a tiny sale, e.g. under a nasty sell modifier
    _click("sell")
    price = gd.TOOLS["Slingshot"]["price"]
    assert d["money"] >= price and d["onboarding"]["step"] == "upgrade"
    # the top-up is capped at one tool's price over the account's lifetime — it can't be farmed
    d["onboarding"]["step"] = "sell"
    d["money"] = 0
    d["inv"] = ["House Sparrow"]
    d["_pending_sell"] = 45
    _click("sell")
    assert d["_onb_topup"] <= price


def test_the_shop_banner_only_shows_during_the_upgrade_step():
    d = _new_player("upgrade")
    assert "Buy your first upgrade" in _text(app.build_shop_components(U, "tools"))
    assert "Buy your first upgrade" in _text(app.build_shop_components(U, "boosts"))
    d["onboarding"] = {"version": 2, "completed": True, "step": "done", "starter_pack": None}
    assert "Buy your first upgrade" not in _text(app.build_shop_components(U, "tools"))


def test_an_upgrade_step_player_who_already_owns_a_tool_moves_on():
    d = _new_player("upgrade")
    d["owned_tools"] = ["Bare Hands", "Slingshot"]
    app.build_onboarding_components(U)
    assert d["onboarding"]["step"] == "pack"


# ── safeguards: steps, replays, rewards ──────────────────────────────────────

def test_a_stale_button_cannot_rewind_or_skip_ahead():
    d = _new_player("sell")
    d["inv"] = [gd.ONBOARDING_FIRST_ANIMAL]
    _click("hunt")                                           # the welcome screen's button, from an older panel
    assert d["onboarding"]["step"] == "sell" and d["inv"] == [gd.ONBOARDING_FIRST_ANIMAL]
    _click("pack", "scout")                                  # a specialty button, long before the pick
    assert d["onboarding"]["step"] == "sell" and not d["onboarding"]["starter_pack"]
    _click("shop")
    assert d["onboarding"]["step"] == "sell"
    _click("sell")                                           # the right one for this step
    assert d["onboarding"]["step"] == "upgrade"


def test_the_first_hunt_cannot_be_replayed():
    d = _new_player("intro")
    _click("hunt")
    assert d["onboarding"]["step"] == "sell"
    animals = list(d["inv"])
    hunts = d["stats"]["lifetime_hunts"]
    _click("hunt")                                           # double click / old panel
    assert d["inv"] == animals and d["stats"]["lifetime_hunts"] == hunts


def test_buttons_from_before_the_redesign_still_do_something_sensible():
    d = _new_player("intro")
    _click("track")                                          # the old 'Track It' → now Start Hunting
    assert d["onboarding"]["step"] == "sell" and d["inv"]
    d2 = _new_player("upgrade")
    _click("trial_hunt")                                     # the old 'Hunt With It' → the shop, not a loaner weapon
    assert d2["onboarding"]["step"] == "upgrade" and not d2.get("trial_tool")
    d3 = _new_player("trial")                                # a player saved mid-flow on a retired step
    app.build_onboarding_components(U)
    assert d3["onboarding"]["step"] == "upgrade"
    d4 = _new_player("danger")
    app.build_onboarding_components(U)
    assert d4["onboarding"]["step"] == "upgrade"
    d5 = _new_player("catch")
    app.build_onboarding_components(U)
    assert d5["onboarding"]["step"] == "intro"


def test_no_loan_weapon_remains():
    for name in ("TRIAL_TOOL", "TRIAL_TOOL_MIN"):
        assert not hasattr(gd, name) and not hasattr(app, name)
    assert not hasattr(app, "_onb_grant_trial_and_catches") and not hasattr(app, "trial_tool_active")
    d = _fresh_player()
    _click("hunt"); _click("sell")
    assert not d.get("trial_tool")


def test_skipping_still_offers_the_starter_specialty():
    d = _new_player("intro")
    _click("skip")
    assert d["onboarding"]["step"] == "pack" and not d["onboarding"]["completed"]
    _click("pack", "hunter")
    assert d["onboarding"]["completed"] and d["onboarding"]["starter_pack"] == "hunter"
    assert any(b["stat"] == "xp" for b in d.get("temp_boosts", []))                 # the specialty's boost really granted


def test_skipping_after_picking_a_pack_just_finishes():
    d = _new_player("intro")
    d["onboarding"]["starter_pack"] = "scout"
    _click("skip")
    assert d["onboarding"]["completed"]


def test_a_specialty_is_paid_once_and_a_bad_key_does_nothing():
    d = _new_player("pack")
    _click("pack", "nonsense")
    assert d["onboarding"]["step"] == "pack" and not d["onboarding"]["starter_pack"]
    _click("pack", "scout")
    items = dict(d.get("items", {}))
    boosts = len(d["temp_boosts"])
    assert app._onb_grant_pack(U, "trader") is False
    d["onboarding"].update(step="pack", completed=False)
    _click("pack", "hunter")                                  # a second pick can't stack another specialty
    assert d["onboarding"]["starter_pack"] == "scout" and len(d["temp_boosts"]) == boosts and dict(d.get("items", {})) == items


# ── the specialties ──────────────────────────────────────────────────────────

def test_the_three_specialties_are_different_but_equal():
    packs = gd.STARTER_PACKS
    assert set(packs) == {"scout", "hunter", "trader"}
    focus = {k: tuple(p["boosts"]) for k, p in packs.items()}
    assert len(set(focus.values())) == 3 and focus == {"scout": ("luck",), "hunter": ("xp",), "trader": ("sell",)}
    strengths = {sum(p["boosts"].values()) for p in packs.values()}
    assert len(strengths) == 1                                   # same size boost — no 'inferior' pick
    assert len({p["duration"] for p in packs.values()}) == 1
    assert max(packs[k]["duration"] for k in packs) <= 1800
    for p in packs.values():
        assert p.get("kit")                                      # each has a small playstyle kit


def test_each_specialty_grants_its_kit():
    for key, check in (("scout", lambda d: d["items"].get("Smoke Bomb", 0) == 1),
                       ("hunter", lambda d: d["healing_inv"].get("Bandage", 0) == 1),
                       ("trader", lambda d: d["money"] == 150 + 100)):
        d = _new_player("pack")
        d["items"] = {}; d["healing_inv"] = {}
        assert app._onb_grant_pack(U, key) is True and check(d), key
        stat = next(iter(gd.STARTER_PACKS[key]["boosts"]))
        assert any(b["stat"] == stat for b in d["temp_boosts"])


# ── Beginner Track: one list, one objective, one set of payouts ─────────────

def test_rookie_goals_and_hunters_path_are_one_track():
    assert not hasattr(gd, "ROOKIE_GOALS") and not hasattr(app, "ROOKIE_GOALS")
    assert not hasattr(app, "rookie_goals_block") and not hasattr(app, "_rookie_goal_progress")
    assert [s["key"] for s in gd.HUNTERS_PATH_STEPS][:2] == ["buy_tool", "hunt_with_tool"]
    d = tt._mk_user(U, level=1, money=0)
    d["hunters_path"] = {"completed": False, "rewarded": []}
    d["owned_tools"] = ["Bare Hands", "Slingshot"]               # step 1 is a live check on owning a tool
    assert app.hunters_path_current_step(U) == 1


def test_the_menu_shows_a_single_objective_and_the_full_list_is_behind_a_button():
    d = tt._mk_user(U, level=1, money=0)
    d["hunters_path"] = {"completed": False, "rewarded": []}
    comps = app.build_menu_components(U, "Tester")
    txt = _text(comps)
    assert txt.count("NEXT GOAL") == 1 and "Buy your first real tool" in txt
    assert "Discover 5 species" not in txt                       # the rest of the list is not on the menu
    labels = [b["label"] for b in _buttons(comps)]
    assert "Beginner Track" in labels
    full = _text(app.build_hunters_path_components(U))
    assert "Beginner Track" in full and "Discover 5 species" in full and "Hunter's Path" not in full
    d["hunters_path"]["completed"] = True
    assert "Beginner Track" not in [b.get("label") for b in _buttons(app.build_menu_components(U, "Tester"))]


def test_track_payouts_are_rebalanced_together_and_paid_once():
    steps = gd.HUNTERS_PATH_STEPS
    step_gems = sum(s["reward"].get("gems", 0) for s in steps)
    total = step_gems + gd.HUNTERS_PATH_REWARD_GEMS
    assert gd.HUNTERS_PATH_REWARD_GEMS == 80 and total == 150        # was 85 + 100 + the Rookie Chest's 50
    d = tt._mk_user(U, level=1, money=0)
    d["gems"] = 0
    d["hunters_path"] = {"completed": False, "rewarded": [s["key"] for s in steps]}
    d["rookie_chest_claimed"] = False
    app.hunters_path_maybe_complete(U)                               # (flags are live; force them all true)
    orig = app._hunters_path_done_flags
    app._hunters_path_done_flags = lambda uid: [True] * len(steps)
    try:
        r = app.hunters_path_maybe_complete(U)
        again = app.hunters_path_maybe_complete(U)
    finally:
        app._hunters_path_done_flags = orig
    assert r["all_done"] and not again["all_done"]
    assert d["gems"] == gd.HUNTERS_PATH_REWARD_GEMS
    assert d["crate_inv"].get("Rare Crate", 0) == 1 and d["rookie_chest_claimed"]
    assert {"Path Walker", "Rookie Hunter"} <= set(d["earned_titles"])


def test_a_player_who_already_took_the_old_rookie_chest_does_not_get_a_second_crate():
    d = tt._mk_user(U, level=1, money=0)
    d["gems"] = 0
    d["rookie_chest_claimed"] = True
    d["hunters_path"] = {"completed": False, "rewarded": [s["key"] for s in gd.HUNTERS_PATH_STEPS]}
    orig = app._hunters_path_done_flags
    app._hunters_path_done_flags = lambda uid: [True] * len(gd.HUNTERS_PATH_STEPS)
    try:
        app.hunters_path_maybe_complete(U)
    finally:
        app._hunters_path_done_flags = orig
    assert d["crate_inv"].get("Rare Crate", 0) == 0


def test_hunters_path_first_step_opens_the_tools_tab():
    step = gd.HUNTERS_PATH_STEPS[0]
    assert step["key"] == "buy_tool" and step["panel"] == "shop_tools"
    d = tt._mk_user(U, level=1, money=150)
    txt = _text(app.build_shop_components(U, "tools"))
    assert "Slingshot" in txt


def test_mythicals_are_not_held_back_forever_by_the_tutorial_path():
    d = tt._mk_user(U, level=1, money=150)
    d["hunters_path"] = {"completed": False, "rewarded": []}
    d["level"] = 5
    assert app.hunters_path_active(U) and not app.hunters_path_myths_allowed(U)
    d["level"] = app.HUNTERS_PATH_MYTH_LEVEL
    assert app.hunters_path_myths_allowed(U)


# ── the optional Coyote challenge ────────────────────────────────────────────

def test_the_coyote_fight_is_not_part_of_onboarding_any_more():
    d = _fresh_player()
    _click("hunt"); _click("sell"); _cid(f"shop:tool_buy_acc:Slingshot:{U}"); _click("pack", "scout")
    assert not d.get("fight") and not d["stats"].get("animal_fights_started")
    assert not d.get("_onb_danger_rewarded") and "Rookie Hunter" not in d["earned_titles"]


def test_the_coyote_challenge_is_optional_unlocked_later_and_pays_once():
    d = tt._mk_user(U, level=3, money=0)
    d["hunters_path"] = {"completed": False, "rewarded": []}
    assert app.beginner_challenge_status(U) == "locked"                 # needs the first tool + a hunt with it
    d["owned_tools"] = ["Bare Hands", "Slingshot"]
    assert app.beginner_challenge_status(U) == "locked"
    d["stats"]["tools_used"] = ["Slingshot"]
    assert app.beginner_challenge_status(U) == ""
    assert "Coyote Challenge" in [b["label"] for b in _buttons(app.build_hunters_path_components(U))]

    h = _cid(f"hpath:challenge:{U}")
    f = d["fight"]
    assert f["animal"] == gd.BEGINNER_CHALLENGE_ANIMAL and f["challenge"] and f["mhp"] < f["mhp_max"]
    assert app.beginner_challenge_status(U) == "busy"
    # win it through the real handler
    random.seed(3)
    for _ in range(25):
        if not d.get("fight"):
            break
        _cid(f"hunt:afight:attack:{d['fight']['eid']}:{U}")
    if d.get("_onb_danger_rewarded"):                                   # the fight is winnable but not guaranteed
        assert d["money"] >= gd.BEGINNER_CHALLENGE_REWARD["money"]
        assert "Rookie Hunter" in d["earned_titles"] and d["healing_inv"].get("First Aid Kit", 0) == 1
    # the reward helper itself is strictly one-time
    d["_onb_danger_rewarded"] = False
    money = d["money"]
    assert app._grant_beginner_challenge_reward(U) and app._grant_beginner_challenge_reward(U) == ""
    assert d["money"] == money + gd.BEGINNER_CHALLENGE_REWARD["money"]
    assert app.beginner_challenge_status(U) == "claimed"


def test_the_challenge_cannot_be_started_by_a_stale_button_while_busy_or_hurt():
    d = tt._mk_user(U, level=3, money=0)
    d["hunters_path"] = {"completed": False, "rewarded": []}
    d["owned_tools"] = ["Bare Hands", "Slingshot"]
    d["stats"]["tools_used"] = ["Slingshot"]
    d["health"]["hp"] = 10
    d["health"]["last_regen_ts"] = app.time.time() + 10 ** 6
    assert app.beginner_challenge_status(U) == "hurt"
    _cid(f"hpath:challenge:{U}")
    assert not d.get("fight")


def test_a_player_stranded_in_the_old_forced_fight_is_routed_forward_and_paid_once():
    d = _new_player("danger")
    d["fight"] = None
    app._onb_after_scripted_danger(U, {"kind": "win"})
    first = d["healing_inv"].get("First Aid Kit", 0)
    assert first == 1 and d["onboarding"]["step"] == "upgrade"
    d["onboarding"].update(step="danger", completed=False)
    app._onb_after_scripted_danger(U, {"kind": "win"})
    assert d["healing_inv"].get("First Aid Kit", 0) == 1


# ── the tour lives elsewhere now ─────────────────────────────────────────────

def test_the_quick_tour_is_available_from_tutorial_not_onboarding():
    d = tt._mk_user(U, level=1, money=150)
    assert "onb:tour:0" in _text(app.build_tutorial_guide_components(U, 0))
    h = _click("tour", "1")
    assert "Quick tour · 2/4" in _text(h.panels[-1])
    pages = "\n".join(app._onb_tour_pages())
    assert "turns the bag into ◈ money and XP" not in pages and "XP the moment you catch" in pages
    d2 = _fresh_player()
    assert "Quick Tour" not in _text(app.build_onboarding_components(U))


def test_a_scratch_card_never_pays_nothing():
    tt._reset()
    d = tt._mk_user(U, level=100, money=0)
    d["scratch_pad"] = {"cells": [None] * gd.SCRATCH_PAD_GRID_SIZE, "revealed": [False] * gd.SCRATCH_PAD_GRID_SIZE, "found": 0}
    last = None
    for i in range(gd.SCRATCH_PAD_MAX_PICKS):
        last = app.reveal_scratch_pad_cell(U, i)
    assert last["kind"] == "done" and len(last["all_prizes"]) == 1
    assert d["money"] == int(app.SCRATCH_PAD_CONSOLATION_X * app.crate_value_scale(100))
    # a card that DID find something gets no extra consolation
    d["money"] = 0
    cells = [None] * gd.SCRATCH_PAD_GRID_SIZE
    cells[0] = {"type": "money", "amount": 1_000}
    d["scratch_pad"] = {"cells": cells, "revealed": [False] * gd.SCRATCH_PAD_GRID_SIZE, "found": 0}
    for i in range(gd.SCRATCH_PAD_MAX_PICKS):
        last = app.reveal_scratch_pad_cell(U, i)
    assert d["money"] == 1_000 and len(last["all_prizes"]) == 1


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
