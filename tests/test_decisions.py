"""
Decisions that matter: tracking clues, region rules, story-run carry-over, gear roles.

  - the scene on the tracking screen changes which move is right (mud -> inspect, exposed clearing -> sneak,
    fading trail -> rush), but not perfectly: clues sometimes mislead
  - every region has a rule that changes what the right move is (noise, cold, ruins, mirage ...)
  - choices in a story-event run carry forward (a rope unlocks a crossing, a lantern reveals a place,
    abandoning supplies makes the next stretch harder)
  - tools have competing roles (quiet for tracking, power for fights, capture for collection)

Runs without pytest:  python tests/test_decisions.py
"""
import asyncio
import json
import os
import random
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_decisions_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402
import event_data as ED            # noqa: E402
import event_scenes as ES          # noqa: E402

run = tt.run
U = "9001"


def _fresh(**over):
    tt._reset()
    app.quest_rolls_if_needed = lambda uid: None          # tests set their own quests; don't let a hunt roll new ones
    app.stop_active_event()
    app._active_sighting = None
    app.FEATURE_TRACK_CLUES = app.FEATURE_BIOME_RULES = app.FEATURE_GEAR_ROLES = app.FEATURE_EVENT_CARRY = True
    over.setdefault("level", 1000)
    return tt._mk_user(U, **over)


def _tr(biome="village", scene="mud", tool="Bare Hands", **over):
    """A tracking sequence pinned to one scene whose clue is TRUE."""
    d = _fresh(biome=biome, tool=tool, owned_tools=list(gd.TOOLS))
    app._tracking_start(U, "Bigfoot", biome)
    t = d["tracking"]
    sc = app._tracking_scene(scene)
    t.update(need=4, goal=12, progress=0, step=0, scene=scene, misled=False, doubt=False, squall=False,
             eff_fav=sc["fav"], eff_bad=list(sc["bad"]), noise=0, probes=0, forgiven=0, mistakes=0, perfect=True,
             warmth=int(gd.biome_rule(biome).get("track", {}).get("warmth", 0)))
    t.update(over)
    return d, t


def _never_spooked():
    """randint that never spooks (the 1-100 roll) but leaves every other roll at its minimum."""
    return lambda a, b: 100 if (a, b) == (1, 100) else a


def _always_spooked():
    return lambda a, b: 1 if (a, b) == (1, 100) else a


def _score(st):
    """What a sensible tracker would maximise: expected trail gained, minus the cost of spooking it."""
    p = st["risk"] / 100
    return st["progress"] * (1 - p) - 4 * p


def _best(d, t):
    return max(gd.TRACKING_ACTIONS, key=lambda a: _score(app._track_action_stats(U, t, a)))


def _with_randint(fn, body):
    real = random.randint
    random.randint = fn
    try:
        return body()
    finally:
        random.randint = real


# ═══════════ tracking clues ═══════════

def test_the_three_scenes_the_players_asked_for_favour_the_obvious_move():
    for scene, want in (("mud", "observe"), ("clearing", "flank"), ("fading", "push")):
        d, t = _tr(scene=scene)
        assert _best(d, t) == want, (scene, {a: app._track_action_stats(U, t, a) for a in gd.TRACKING_ACTIONS})


def test_every_scene_has_a_best_move_and_every_move_is_best_somewhere():
    seen = {}
    for sc in gd.TRACKING_SCENES:
        d, t = _tr(scene=sc["key"])
        assert sc["fav"] in gd.TRACKING_ACTIONS and sc["bad"] and sc["fav"] not in sc["bad"]
        assert sc["text"] and sc["hint"]
        assert _best(d, t) == sc["fav"], sc["key"]
        seen.setdefault(sc["fav"], []).append(sc["key"])
    assert set(seen) == set(gd.TRACKING_ACTIONS) and all(len(v) >= 3 for v in seen.values())


def test_a_move_the_scene_punishes_is_riskier_and_gains_less():
    d, t = _tr(scene="mud")
    base = gd.TRACKING_ACTIONS["push"]
    st = app._track_action_stats(U, t, "push")
    assert st["risk"] > base["risk"] and st["progress"] < base["progress"]
    fav = app._track_action_stats(U, t, "observe")
    assert fav["risk"] <= gd.TRACKING_ACTIONS["observe"]["risk"] and fav["progress"] > gd.TRACKING_ACTIONS["observe"]["progress"]


def test_clues_are_trustworthy_most_of_the_time_but_not_always():
    d, t = _tr(biome="village")
    n = 3000
    misled = doubt_m = doubt_t = m_n = t_n = 0
    for _ in range(n):
        app._track_roll_scene(t)
        if t["misled"]:
            misled += 1; m_n += 1; doubt_m += t["doubt"]
        else:
            t_n += 1; doubt_t += t["doubt"]
    rate = misled / n
    assert 0.15 < rate < 0.25, rate                                  # TRACK_CLUE_RELIABILITY = 0.8
    assert doubt_m / m_n > 2 * (doubt_t / t_n)                      # the doubt line is a real, imperfect tell
    assert 0.03 < doubt_t / t_n < 0.30


def test_a_misleading_scene_gives_the_obvious_move_nothing_extra():
    d, t = _tr(scene="mud", misled=True, eff_fav="follow", eff_bad=["push"])
    shown = app._tracking_scene("mud")["fav"]
    assert shown == "observe"
    assert app._track_action_stats(U, t, "observe") == {"risk": 0, "progress": 1}      # the base numbers, no bonus
    assert app._track_action_stats(U, t, "follow")["progress"] == gd.TRACKING_ACTIONS["follow"]["progress"] + 1
    out = _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "observe"))
    assert "misleading" in out["line"]


def test_the_feedback_line_teaches_the_ground():
    d, t = _tr(scene="clearing")
    out = _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "flank"))
    assert "read the ground right" in out["line"]
    d, t = _tr(scene="clearing")
    out = _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "follow"))
    assert "wrong move" in out["line"]


def test_reading_the_scene_beats_guessing():
    """Always choose what the scene on screen suggests vs choose at random — over many full tracks."""
    app.FEATURE_BIOME_RULES = False

    def play(policy, n=500):
        found = missteps = 0
        for _ in range(n):
            d, t = _tr(scene="prints")
            app.FEATURE_BIOME_RULES = False
            t.update(need=random.choice([2, 3, 4]))
            t["goal"] = t["need"] * 3
            while True:
                act = policy(t)
                if act == "closein":
                    pass
                out = app.tracking_choice(U, act)
                if out["kind"] != "ongoing":
                    found += out["kind"] == "located"
                    break
                if d["tracking"]["progress"] >= d["tracking"]["goal"]:
                    out = app.tracking_choice(U, "closein")
                    found += out["kind"] == "located"
                    break
            missteps += t["mistakes"]
        return found / n, missteps / n

    random.seed(7)
    read = play(lambda t: app._tracking_scene(t["scene"])["fav"])
    guess = play(lambda t: random.choice(list(gd.TRACKING_ACTIONS)))
    assert read[0] > guess[0] + 0.05 and read[1] < guess[1], (read, guess)
    # ...and reading beats the best fixed habit too: one move for every scene is not good enough
    for habit in gd.TRACKING_ACTIONS:
        fixed = play(lambda t, habit=habit: habit)
        assert read[1] < fixed[1] and read[0] >= fixed[0], (habit, read, fixed)


def test_the_tracking_panel_shows_the_clue_and_the_hint():
    d, t = _tr(scene="fading", biome="village")
    blob = json.dumps(app.build_tracking_components(U), ensure_ascii=False)
    sc = app._tracking_scene("fading")
    assert sc["title"] in blob and sc["hint"] in blob and "Rush in" in blob and "Inspect the sign" in blob
    assert "Sneak around" in blob


# ═══════════ biome rules ═══════════

_TRACK_KEYS = {"risk", "progress", "extra_steps", "step_hp", "mistake_hp", "forgive", "misread", "observe_steadies",
               "noise", "warmth", "warmth_cost", "frost_hp", "investigate", "squall"}
_FIGHT_KEYS = {"ambush", "flee_strike", "turn_hp", "loud_hit"}


def test_every_region_has_a_rule_players_can_read_and_the_engine_understands():
    assert set(gd.BIOME_RULES) == set(gd.BIOME_TOOL_TIER)
    for b, r in gd.BIOME_RULES.items():
        assert r["name"] and len(r["blurb"]) > 40 and r.get("track"), b
        assert set(r["track"]) <= _TRACK_KEYS, (b, set(r["track"]) - _TRACK_KEYS)
        assert set(r.get("fight", {})) <= _FIGHT_KEYS, b
        assert not r.get("fight") or r.get("fight_blurb"), b
        assert gd.biome_rule_line(b).startswith("**")
    assert len({r["name"] for r in gd.BIOME_RULES.values()}) == len(gd.BIOME_RULES)       # no two regions share a rule


def test_every_region_rule_is_played_through_a_whole_track_without_breaking():
    for b in gd.BIOME_TOOL_TIER:
        for tool in ("Bare Hands", "Spear", "Longbow"):
            random.seed(sum(map(ord, b + tool)))
            for _ in range(20):
                d, t = _tr(biome=b, scene="prints", tool=tool)
                app._tracking_start(U, "Bigfoot", b)               # a real start, real first scene
                out = {"kind": "ongoing"}
                n = 0
                while out["kind"] == "ongoing" and n < 20:
                    act = random.choice(list(gd.TRACKING_ACTIONS) + (["investigate"] if gd.biome_rule(b)["track"].get("investigate") else []))
                    out = app.tracking_choice(U, act)
                    n += 1
                    assert d["health"]["hp"] >= 1                  # the trail never kills
                    blob = json.dumps(app.build_tracking_components(U), ensure_ascii=False) if out["kind"] == "ongoing" else ""
                    assert len(blob) < 9000
                assert out["kind"] in ("located", "lost")


def test_the_region_rule_is_on_the_tracking_panel():
    for b in gd.BIOME_TOOL_TIER:
        _tr(biome=b)
        blob = json.dumps(app.build_tracking_components(U), ensure_ascii=False)
        assert gd.BIOME_RULES[b]["name"] in blob, b


def test_swamp_noise_draws_a_predator_and_gear_changes_how_fast():
    # a rush adds 2 noise; a power tool adds 1 more -> 3 -> something bites on the first rush
    d, t = _tr(biome="swamp", scene="fading", tool="Spear")
    hp0 = d["health"]["hp"]
    out = _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "push"))
    assert d["health"]["hp"] < hp0 and "bite" in out["line"] and d["tracking"]["noise"] == 1
    # a quiet tool following never raises the noise
    d, t = _tr(biome="swamp", scene="prints", tool="Longbow")
    for _ in range(3):
        _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "follow"))
        if d.get("tracking") is None:
            break
        assert d["tracking"]["noise"] == 0
    # Inspecting lets the water settle
    d, t = _tr(biome="swamp", scene="mud", noise=2)
    _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "observe"))
    assert d["tracking"]["noise"] == 1


def test_tundra_burns_warmth_on_long_routes_and_then_bites():
    d, t = _tr(biome="tundra", scene="prints")
    assert t["warmth"] == 4
    _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "flank"))           # the long way: -2
    assert d["tracking"]["warmth"] == 2
    _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "follow"))          # -1
    _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "follow"))          # -1 -> 0
    assert d["tracking"] is None or d["tracking"]["warmth"] == 0
    d, t = _tr(biome="tundra", scene="prints", warmth=0, need=4, goal=12)
    hp0 = d["health"]["hp"]
    out = _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "follow"))
    assert d["health"]["hp"] == hp0 - 6 and "Frostbite" in out["line"]


def test_ruins_investigation_is_a_shortcut_nothing_or_a_trap_and_limited():
    real = random.random
    d, t = _tr(biome="cursed_ruins", scene="prints")
    random.random = lambda: 0.1                                           # shortcut
    try:
        app.tracking_choice(U, "investigate")
    finally:
        random.random = real
    assert d["tracking"]["progress"] == app.TRACK_INVESTIGATE_BONUS and d["tracking"]["probes"] == 1
    d, t = _tr(biome="cursed_ruins", scene="prints")
    hp0 = d["health"]["hp"]
    random.random = lambda: 0.95                                           # trap
    try:
        out = app.tracking_choice(U, "investigate")
    finally:
        random.random = real
    assert d["health"]["hp"] < hp0 and d["tracking"]["progress"] == 0 and "trigger" in out["line"]
    d, t = _tr(biome="cursed_ruins", scene="prints", probes=app.TRACK_INVESTIGATE_MAX)
    out = app.tracking_choice(U, "investigate")
    assert out["kind"] == "ongoing" and "every marking" in out["line"]
    # only ruins have markings
    d, t = _tr(biome="forest", scene="prints")
    assert app.tracking_choice(U, "investigate")["kind"] == "none"
    # and the button only exists there
    _tr(biome="cursed_ruins")
    assert "Investigate" in json.dumps(app.build_tracking_components(U))
    _tr(biome="forest")
    assert "Investigate" not in json.dumps(app.build_tracking_components(U))


def test_village_forgives_the_first_slip_only():
    d, t = _tr(biome="village", scene="prints")
    out = _with_randint(_always_spooked(), lambda: app.tracking_choice(U, "follow"))
    assert d["tracking"]["mistakes"] == 0 and "this once" in out["line"]
    _with_randint(_always_spooked(), lambda: app.tracking_choice(U, "follow"))
    assert d["tracking"]["mistakes"] == 1


def test_region_rules_move_the_numbers_they_say_they_do():
    d, t = _tr(biome="forest", scene="prints")
    assert app._track_action_stats(U, t, "flank")["risk"] == gd.TRACKING_ACTIONS["flank"]["risk"] - 10
    assert app._track_action_stats(U, t, "push")["risk"] == gd.TRACKING_ACTIONS["push"]["risk"] + 6
    d, t = _tr(biome="woods", scene="sound")
    assert app._track_action_stats(U, t, "observe")["progress"] == 2
    d, t = _tr(biome="jungle", scene="mud")
    assert app._track_action_stats(U, t, "follow")["progress"] == gd.TRACKING_ACTIONS["follow"]["progress"] + 1
    d, t = _tr(biome="rainbow", scene="sound", squall=True)
    assert app._track_action_stats(U, t, "push")["risk"] == gd.TRACKING_ACTIONS["push"]["risk"] + app.TRACK_SQUALL_RISK
    assert app._track_action_stats(U, t, "observe")["risk"] == 0
    assert "squall" in json.dumps(app.build_tracking_components(U)).lower()
    d, t = _tr(biome="abyssal_depths", scene="prints")
    hp0 = d["health"]["hp"]
    _with_randint(_always_spooked(), lambda: app.tracking_choice(U, "follow"))
    assert d["health"]["hp"] == hp0 - 10
    d, t = _tr(biome="volcanic_highlands", scene="prints")
    hp0 = d["health"]["hp"]
    _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "observe"))
    assert d["health"]["hp"] == hp0 - 7
    d, t = _tr(biome="celestial_peaks", scene="prints")
    hp0 = d["health"]["hp"]
    _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "push"))
    assert d["health"]["hp"] == hp0 - 8


def test_the_tide_cuts_the_trail_one_step_sooner():
    d, t = _tr(biome="sunken_coast", scene="mud", need=2, goal=6)
    assert app._track_extra_steps(t) == app.TRACK_EXTRA_STEPS - 1
    d, t = _tr(biome="village", scene="mud")
    assert app._track_extra_steps(t) == app.TRACK_EXTRA_STEPS


def test_desert_clues_mislead_more_and_inspecting_clears_the_haze():
    d, t = _tr(biome="small_desert")
    n = 3000
    mis = sum((app._track_roll_scene(t), t["misled"])[1] for _ in range(n)) / n
    assert 0.34 < mis < 0.46, mis
    clear = 0
    for _ in range(300):
        t["steady"] = True
        app._track_roll_scene(t)
        clear += not t["misled"]
    assert clear == 300
    d, t = _tr(biome="small_desert", scene="mud")
    _with_randint(_never_spooked(), lambda: app.tracking_choice(U, "observe"))
    assert d["tracking"] is None or d["tracking"].get("misled") is False
    d, t = _tr(biome="celestial_peaks")
    assert all(not (app._track_roll_scene(t) or t["misled"]) for _ in range(500))


def test_region_rules_apply_to_animal_fights_too():
    d = _fresh(biome="swamp", tool="Spear", owned_tools=["Spear"])
    d["health"].update(hp=100, max_hp=100)
    stats = gd.animal_combat_stats("British Grey Wolf", "swamp")
    d["fight"] = {"kind": "animal", "animal": "British Grey Wolf", "biome": "swamp", "eid": "e1", "mhp": 9999,
                  "mhp_max": 9999, "turn": 1, "guard": False, "log": [], "bonus": "normal", "ts": time.time()}
    real = random.random
    random.random = lambda: 0.0                      # every proc fires: the power attack lands, so does the second hunter
    try:
        out = app.animal_fight_turn(U, "power")
    finally:
        random.random = real
    assert "second hunter" in " ".join(d["fight"]["log"]), d["fight"]["log"]
    # tundra: long fights chill you
    d = _fresh(biome="tundra", tool="Spear", owned_tools=["Spear"])
    d["health"].update(hp=100, max_hp=100)
    d["fight"] = {"kind": "animal", "animal": "Eurasian Badger", "biome": "tundra", "eid": "e2", "mhp": 9999,
                  "mhp_max": 9999, "turn": 1, "guard": False, "log": [], "bonus": "normal", "ts": time.time()}
    random.random = lambda: 0.99                     # nothing procs, nobody hits
    try:
        app.animal_fight_turn(U, "defend")
        hp1 = d["health"]["hp"]
        app.animal_fight_turn(U, "defend")
    finally:
        random.random = real
    assert hp1 == 100 and d["health"]["hp"] == 100 - 3                       # starts biting from round 2
    # forest cover and quiet gear raise the odds of an ambush
    d = _fresh(biome="forest", tool="Longbow", owned_tools=["Longbow", "Spear"])
    st = {"attack_chance": 0.5}
    random.seed(3)
    quiet_forest = sum(app._animal_encounter_roll(U, st, "forest") == "ambush" for _ in range(4000))
    d["tool"] = "Longbow"
    quiet_village = sum(app._animal_encounter_roll(U, st, "village") == "ambush" for _ in range(4000))
    d["tool"] = "Spear"
    power_village = sum(app._animal_encounter_roll(U, st, "village") == "ambush" for _ in range(4000))
    assert quiet_forest > quiet_village > power_village


def test_rule_is_shown_on_the_info_page_and_in_a_fight():
    for b in gd.BIOME_TOOL_TIER:
        head, sub, body, thumb = app._info_render_biome(b)
        assert gd.BIOME_RULES[b]["name"] in body, b
    d = _fresh(biome="tundra", tool="Spear", owned_tools=["Spear", "Longbow"])
    d["fight"] = {"kind": "animal", "animal": "British Grey Wolf", "biome": "tundra", "eid": "e3", "mhp": 50,
                  "mhp_max": 50, "turn": 1, "guard": False, "log": [], "bonus": "normal", "ts": time.time()}
    blob = json.dumps(app.build_animal_fight_components(U), ensure_ascii=False)
    assert "Bitter Cold" in blob and "Swap gear" in blob and "hunt:gear:afight:e3" in blob


# ═══════════ events: choices carry forward ═══════════

def _run(key, ids):
    app.stop_active_event()
    ev = app.start_event(key, "admin")
    sp = ED.EVENT_SPECS[key]
    assert app._ev3_scenes_start(U, ev, sp) == ""
    run_ = app._ev3_st(U)["run"]
    run_["ids"] = list(ids)
    return ev, sp, run_


def _choose(ev, sp, ci):
    return app._ev3_scenes_choose(U, ev, sp, ci)


def test_follow_up_scenes_only_exist_behind_a_flag_and_every_flag_has_a_payoff():
    for pool, scenes in ES.SCENES.items():
        needs = {s["needs"] for s in scenes if s.get("needs")}
        gained = {fx["gain"] for s in scenes for fx in (s.get("fx") or {}).values() if fx.get("gain")}
        assert needs and needs == gained, (pool, needs, gained)
        assert all(n in ES.FLAGS[pool] for n in needs)
        assert sum(1 for s in scenes if not s.get("needs")) >= app.EV3_SCENES_PER_RUN + 2


def test_keeping_the_lantern_reveals_a_place_in_one_of_the_next_two_scenes():
    for _ in range(30):
        _fresh()
        ev, sp, r = _run("fog", ["f1", "f2", "f3", "f4", "f6"])
        out = _choose(ev, sp, 0)                                           # follow the light
        assert "lantern" in r["flags"] and "Followed the lantern" in r["trail"]
        assert "now carry" in r["last"]
        assert "fx1" in r["ids"][1:3] and r["ids"].count("fx1") == 1 and len(r["ids"]) == 5
        nxt = r["ids"][1] if "fx1" == r["ids"][1] else r["ids"][2]
    app.stop_active_event()


def test_playing_the_follow_up_spends_the_flag_and_is_remembered():
    _fresh()
    ev, sp, r = _run("fog", ["f1", "fx1", "f3", "f4", "f6"])
    r["flags"] = ["lantern"]
    _choose(ev, sp, 0)                                                      # f1 again: lantern already carried
    assert r["flags"] == ["lantern"]
    txt = json.dumps(app.build_events_components(U), ensure_ascii=False)
    assert "The Standing Stone" in txt and "lantern" in txt and "Carrying" in txt
    _choose(ev, sp, 0)
    assert "lantern" not in r["flags"] and "The Standing Stone" in r["trail"]
    app.stop_active_event()


def test_keeping_the_rope_unlocks_a_crossing_and_abandoning_it_does_not():
    _fresh()
    ev, sp, r = _run("storm", ["s1", "s5", "s6", "s7", "s8"])
    _choose(ev, sp, 1)                                                      # strike everything: keep the rope
    assert "rope" in r["flags"] and "sx1" in r["ids"][1:3]
    # drop the rope again before the crossing: the crossing goes back to an ordinary scene
    r["flags"].remove("rope")
    app._ev3_followup_sync(r, sp, None)
    assert "sx1" not in r["ids"] and len(set(r["ids"])) == 5
    _fresh()
    ev, sp, r = _run("storm", ["s1", "s5", "s6", "s7", "s8"])
    _choose(ev, sp, 0)                                                      # pack light: abandon the tents
    assert "rope" not in r["flags"] and "sx1" not in r["ids"] and r["strain"] is True
    app.stop_active_event()


def test_abandoning_supplies_makes_the_next_stretch_harder():
    _fresh()
    ev, sp, r = _run("storm", ["s1", "s5", "s6", "s7", "s8"])
    _choose(ev, sp, 0)
    assert r["strain"] is True
    assert "harder" in json.dumps(app.build_events_components(U), ensure_ascii=False)
    scene = app._ev3_scene(sp, r["ids"][1])                                 # s5: Sing (0,+2)
    a0, b0 = r["a"], r["b"]
    da, db = scene["choices"][0][2], scene["choices"][0][3]
    _choose(ev, sp, 0)
    assert r["b"] == min(app.EV3_METER_MAX, b0 + (db - 1 if db > 0 else db)) and r["a"] == min(app.EV3_METER_MAX, a0 + (da - 1 if da > 0 else da))
    assert r["strain"] is False                                             # it only lasts one stretch
    app.stop_active_event()


def test_an_unstrained_choice_pays_in_full():
    _fresh()
    ev, sp, r = _run("storm", ["s5", "s6", "s7", "s8", "s2"])
    scene = app._ev3_scene(sp, "s5")
    b0 = r["b"]
    _choose(ev, sp, 0)
    assert r["b"] == min(app.EV3_METER_MAX, b0 + scene["choices"][0][3])
    app.stop_active_event()


def test_a_whole_run_never_shows_a_follow_up_without_its_flag_and_still_ends_in_five_scenes():
    for key in ("fog", "admin_404", "storm"):
        sp = ED.EVENT_SPECS[key]
        shown_followups = 0
        for n in range(150):
            _fresh()
            ev = app.start_event(key, "admin")
            st = app._ev3_st(U)
            st["run"] = None
            app._ev3_daily(U, ev)["runs"] = 0
            assert app._ev3_scenes_start(U, ev, sp) == ""
            r = st["run"]
            count = 0
            while st.get("run"):
                sc = app._ev3_scene(sp, r["ids"][r["i"]])
                if sc.get("needs"):
                    shown_followups += 1
                    assert sc["needs"] in r["flags"], (key, sc["id"], r["flags"])
                body = json.dumps(app._ev3_scenes_body(U, ev, sp, st), ensure_ascii=False)
                assert sc["text"][:30] in body
                out = _choose(ev, sp, random.randrange(3))
                count += 1
                if out["ended"]:
                    break
            assert 1 <= count <= app.EV3_SCENES_PER_RUN
            assert len(set(r["ids"])) == len(r["ids"])
        assert shown_followups > 0, key
    app.stop_active_event()


def test_the_run_result_remembers_what_happened():
    _fresh()
    ev, sp, r = _run("fog", ["f1", "f3", "f4", "f6", "f7"])
    _choose(ev, sp, 0)                                                      # lantern
    out = {"ended": None}
    for _ in range(4):
        out = _choose(ev, sp, 1)
        if out["ended"]:
            break
    if out["ended"]:
        assert "Followed the lantern" in out["journey"]
    app.stop_active_event()


def test_carry_over_can_be_switched_off():
    _fresh()
    app.FEATURE_EVENT_CARRY = False
    ev, sp, r = _run("fog", ["f1", "f2", "f3", "f4", "f6"])
    _choose(ev, sp, 0)
    assert not r["flags"] and r["strain"] is False and r["ids"] == ["f1", "f2", "f3", "f4", "f6"]
    app.FEATURE_EVENT_CARRY = True
    app.stop_active_event()


# ═══════════ gear roles ═══════════

def test_every_tool_has_a_role_and_every_stage_of_the_game_has_a_choice():
    assert set(gd.TOOL_ROLES) == set(gd.TOOLS) and set(gd.TOOL_ROLES.values()) <= set(gd.ROLE_INFO)
    for biome, need in gd.BIOME_TOOL_TIER.items():
        roles = {gd.tool_role(n) for n, t in gd.TOOLS.items() if t["tier"] >= need}
        assert len(roles) >= 2, (biome, roles)
    for role in ("quiet", "power", "capture", "hauler", "slayer"):
        assert sum(1 for r in gd.TOOL_ROLES.values() if r == role) >= 3, role


def test_power_tools_hit_harder_and_quiet_and_capture_tools_hit_lighter():
    for name in gd.TOOLS:
        base = gd.tool_combat_damage(name, roles=False)
        with_role = gd.tool_combat_damage(name)
        r = gd.tool_role(name)
        if r == "power":
            assert with_role[1] >= base[1] * 1.45, name
        elif r in ("quiet", "capture", "hauler"):
            assert with_role[1] <= base[1] * 0.8, name
        elif r == "slayer":
            assert with_role[1] < base[1], name
    # a stronger-tier quiet tool falls behind a cheaper power tool in a fight
    assert gd.tool_combat_damage("Musket")[1] > gd.tool_combat_damage("Hunting Rifle")[1]      # tier 8 power beats tier 9 quiet


def test_quiet_gear_tracks_better_and_power_gear_fights_better():
    d, t = _tr(biome="village", scene="camp", tool="Longbow")
    q = {a: app._track_action_stats(U, t, a) for a in gd.TRACKING_ACTIONS}
    d, t = _tr(biome="village", scene="camp", tool="Musket")
    p = {a: app._track_action_stats(U, t, a) for a in gd.TRACKING_ACTIONS}
    for a in ("follow", "flank", "push"):
        assert q[a]["risk"] < p[a]["risk"], a
    assert q["observe"] == p["observe"]                                    # sitting still is silent either way
    assert p["follow"]["risk"] - q["follow"]["risk"] >= 20                 # the gap is big, not a rounding error
    # ...and the strong power weapon is clearly the better fighter
    assert gd.tool_combat_damage("Musket")[1] > gd.tool_combat_damage("Longbow")[1] * 1.5


def test_swapping_to_a_quiet_tool_beats_the_stronger_weapon_on_the_trail_for_real():
    """The reason to switch after buying a stronger weapon: over many tracks the quiet tool finds more creatures."""
    def found(tool, n=400):
        got = 0
        random.seed(11)
        for _ in range(n):
            d, t = _tr(biome="village", scene="prints", tool=tool)
            app.FEATURE_BIOME_RULES = False
            app.FEATURE_TRACK_CLUES = False
            t["need"], t["goal"] = 3, 9
            out = {"kind": "ongoing"}
            while out["kind"] == "ongoing":
                act = "flank" if d["tracking"]["progress"] < d["tracking"]["goal"] else "closein"
                out = app.tracking_choice(U, act)
            got += out["kind"] == "located"
        app.FEATURE_BIOME_RULES = app.FEATURE_TRACK_CLUES = True
        return got / n
    assert found("Longbow") > found("Musket") + 0.04


def test_capture_gear_finds_more_for_collection_goals():
    d = _fresh(tool="Crossbow")
    cap = app._gear(U)
    d["tool"] = "Musket"
    pw = app._gear(U)
    assert cap["capture_pp"] > pw["capture_pp"] and cap["find_mult"] > pw["find_mult"]
    # event finds: a roll that a capture tool wins and a power tool misses
    _fresh(level=300)
    ev = app.start_event("meteor", "admin")
    sp = ED.EVENT_SPECS["meteor"]
    sites = app._ev3_impact_regions(U, ev, sp)
    chance = sp["params"]["chance"]
    probe = chance * 1.1
    real = random.random
    try:
        random.random = lambda: probe
        app.data[U]["tool"] = "Crossbow"
        assert app._ev3_collect(U, ev, sp, sites[0])
        _fresh(level=300)
        ev = app.start_event("meteor", "admin")
        sites = app._ev3_impact_regions(U, ev, sp)
        app.data[U]["tool"] = "Musket"
        assert app._ev3_collect(U, ev, sp, sites[0]) == []
    finally:
        random.random = real
        app.stop_active_event()


def _quest(stat, **requires):
    return {"id": stat, "stat": stat, "requires": requires, "progress": 0, "target": 10 ** 6,
            "completed": False, "claimed": False}


def _hunt_catches(d, n):
    out = []
    for _ in range(n):
        d["hunt_cd"] = 0
        d["_hunt_times"] = []
        d["_last_hunt_ts"] = None
        d["health"].update(hp=100)
        d["fight"] = d["_boss"] = d["tracking"] = None
        r = app.run_hunt(U)
        out += r.get("catches", [])
    return out


def _with_ammo(d, tool):
    if gd.tool_needs_ammo(tool):
        ammo = gd.get_ammo_for_tool(tool)[0]
        d["ammo_inv"] = {ammo: 50000}
        d["equipped_ammo"] = ammo


def test_capture_gear_helps_a_perfect_catch_quest_and_does_nothing_without_one():
    """Pin the base chance to zero so only the tool's own, objective-gated bonus can make a catch Perfect."""
    real_rc, real_random = app.rare_catch_chance, random.random
    app.rare_catch_chance = lambda luck: 0.0
    random.random = lambda: 0.031
    try:
        d = _fresh(biome="village", tool="Crossbow", owned_tools=["Crossbow", "Spear"])
        _with_ammo(d, "Crossbow")
        d["quests"] = []
        assert not any(c["is_rare"] for c in _hunt_catches(d, 30))                 # no quest open: no bonus, no extra income
        d["quests"] = [_quest("perfect_catches")]
        got = _hunt_catches(d, 30)
        assert got and all(c["is_rare"] for c in got)                              # quest open: +8pp beats the 3.1% roll
        d["tool"] = "Spear"
        assert not any(c["is_rare"] for c in _hunt_catches(d, 30))                 # a power tool gets nothing from it
    finally:
        app.rare_catch_chance, random.random = real_rc, real_random


def test_capture_gear_lures_the_species_a_quest_is_waiting_on_and_never_epic_or_legendary():
    d = _fresh(biome="village", tool="Crossbow", owned_tools=["Crossbow", "Spear"])
    roster = gd.BIOME_ANIMALS["village"]
    target = roster[-1]
    d["quests"] = [_quest("animal_caught_specific", animal=target)]
    real = random.random
    random.random = lambda: 0.0                                                    # every lure roll fires
    try:
        lured = app._capture_lure(U, "village", ["Red Fox", "Red Fox", "Red Fox"])
        assert lured == [target] * 3
        d["tool"] = "Spear"
        assert app._capture_lure(U, "village", ["Red Fox"] * 3) == ["Red Fox"] * 3   # no role, no lure
        d["tool"] = "Crossbow"
        # no quest: it lures a species you have never caught — and only common/uncommon/rare ones
        d["quests"] = []
        d["record"] = {a: {"best": 1} for a in roster[:-2]}
        pool = [a for a in roster[-2:] if gd.ANIMAL_DATA[a]["rarity"] in ("common", "uncommon", "rare")]
        out = app._capture_lure(U, "village", ["Red Fox"] * 4)
        assert all(a in pool for a in out) if pool else out == ["Red Fox"] * 4
        d["record"] = {a: {"best": 1} for a in roster}                              # journal complete: nothing to lure
        assert app._capture_lure(U, "village", ["Red Fox"] * 4) == ["Red Fox"] * 4
    finally:
        random.random = real
    # and a quest target outside this region is ignored
    d["quests"] = [_quest("animal_caught_specific", animal=gd.BIOME_ANIMALS["forest"][0])]
    d["record"] = {a: {"best": 1} for a in roster}
    random.random = lambda: 0.0
    try:
        assert app._capture_lure(U, "village", ["Red Fox"]) == ["Red Fox"]
    finally:
        random.random = real


def test_capture_gear_is_income_neutral_for_ordinary_hunting():
    """With nothing to collect, a capture tool gets no hunting edge over any other role."""
    for tool in ("Crossbow", "Spear", "Longbow"):
        d = _fresh(biome="village", tool=tool, owned_tools=[tool])
        d["quests"] = []
        d["record"] = {a: {"best": 1} for a in gd.BIOME_ANIMALS["village"]}
        assert app._capture_pp(U) == 0.0
        assert app._capture_lure(U, "village", ["Red Fox"] * 3) == ["Red Fox"] * 3


def test_hauler_gear_drops_far_more_crates_than_other_roles():
    def crates(tool, n=1500):
        d = _fresh(biome="village", tool=tool, owned_tools=[tool])
        _with_ammo(d, tool)
        d["quests"] = []
        got = 0
        random.seed(21)
        real = app.hunt_crate_chance
        app.hunt_crate_chance = lambda tier, override=None, bonus=0.0: 0.10      # same base chance for every tool
        try:
            for _ in range(n):
                d["hunt_cd"] = 0
                d["_hunt_times"] = []
                d["_last_hunt_ts"] = None
                d["health"].update(hp=100)
                d["fight"] = d["_boss"] = d["tracking"] = None
                d["crate_inv"] = {}
                d["auto_open_crates"] = False
                r = app.run_hunt(U)
                got += sum((r.get("crate_drops") or {}).values())
        finally:
            app.hunt_crate_chance = real
        return got / n
    hauler, plain = crates("Shortbow"), crates("Longbow")
    assert hauler > plain * 1.35, (hauler, plain)
    assert gd.ROLE_INFO["hauler"]["crate"] >= 1.5
    # the price of hauling: weak in a fight and clumsy on a trail
    assert gd.tool_combat_damage("Shortbow")[1] < gd.tool_combat_damage("Musket")[1] * 0.6


def test_slayer_gear_meets_mythicals_more_and_hits_them_far_harder():
    d = _fresh(biome="village", tool="Mythic Net", owned_tools=["Mythic Net", "Musket", "Longbow"])
    assert app._gear(U)["myth_enc"] >= 1.3 and app._gear(U)["myth_dmg"] >= 1.8
    # encounter chance through the real hunt roll: pin the dice between the plain and the boosted chance
    def meets(tool, n=12):
        d = _fresh(biome="village", tool=tool, owned_tools=[tool])
        _with_ammo(d, tool)
        d["boosts"] = {"luck": 0, "sell": 0, "xp": 0}
        got = 0
        real_r, real_b = random.random, app.MYTH_ENCOUNTER_BASE
        app.MYTH_ENCOUNTER_BASE = 0.02
        random.random = lambda: 0.026                      # plain tools meet one at 2.0%, a slayer at 2.8%
        try:
            for _ in range(n):
                d["hunt_cd"] = 0
                d["_hunt_times"] = []
                d["_last_hunt_ts"] = None
                d["health"].update(hp=100)
                d["fight"] = d["_boss"] = d["tracking"] = None
                r = app.run_hunt(U)
                got += bool(r.get("tracking_encounter") or r.get("myth_encounter"))
        finally:
            random.random, app.MYTH_ENCOUNTER_BASE = real_r, real_b
        return got
    assert meets("Spear") > 0 and meets("Slingshot") == 0

    def myth_damage(tool):
        total = 0
        random.seed(2)
        for _ in range(150):
            d = _fresh(biome="village", tool=tool, owned_tools=[tool])
            d["health"].update(hp=100, max_hp=100)
            d["_boss"] = {"creature": "Bigfoot", "biome": "village", "ts": int(time.time()), "eid": "m2", "mhp": 9000,
                          "mhp_max": 9000, "turn": 1, "fallen": False, "guard": False, "enrage": False,
                          "mdebuff": True, "log": []}
            real = random.randint
            random.randint = lambda a, b: a if (a, b) != (1, 100) else 1
            try:
                app.myth_fight_turn(U, "punch")
            finally:
                random.randint = real
            total += 9000 - d["_boss"]["mhp"]
        return total / 150
    # same tier-ish: a slayer out-hits a power tool against a mythical but not against an ordinary animal
    assert myth_damage("Spear") > myth_damage("Slingshot") * 1.8
    assert gd.tool_combat_damage("Mythic Net")[1] < gd.tool_combat_damage("Celestial Lance")[1]


def test_gear_roles_can_be_switched_off():
    d, t = _tr(biome="village", scene="prints", tool="Spear")
    on = app._track_action_stats(U, t, "push")["risk"]
    app.FEATURE_GEAR_ROLES = False
    off = app._track_action_stats(U, t, "push")["risk"]
    app.FEATURE_GEAR_ROLES = True
    assert on == off + gd.ROLE_INFO["slayer"]["track_risk"]
    assert app._gear(U)["dmg"] == gd.ROLE_INFO["slayer"]["dmg"]
    app.FEATURE_GEAR_ROLES = False
    assert app._gear(U)["dmg"] == 1.0 and app._gear_select_row(U, "track", "x") is None
    app.FEATURE_GEAR_ROLES = True


def test_gear_roles_show_in_the_equip_panel_shop_and_info_page():
    d = _fresh(tool="Longbow", owned_tools=["Bare Hands", "Longbow", "Musket"], money=10 ** 9)
    blob = json.dumps(app.build_equip_components(U), ensure_ascii=False)
    assert "Quiet" in blob and "Power" in blob
    app._tool_shop_page[U] = 1
    shop = json.dumps(app.build_shop_components(U, "tools"), ensure_ascii=False)
    assert any(gd.tool_role_info(n)["label"] in shop for n in gd.TOOLS)
    head, sub, body, thumb = app._info_render_tool("Tranq Gun")
    assert "Capture" in body
    assert "Slayer" in app._info_render_tool("Mythic Net")[2] and "Hauler" in app._info_render_tool("Shortbow")[2]


def test_you_can_swap_gear_from_the_tracking_and_fight_panels():
    d, t = _tr(biome="village", scene="prints", tool="Sniper Rifle")
    blob = json.dumps(app.build_tracking_components(U), ensure_ascii=False)
    assert f"hunt:gear:track:{t['id']}:{U}" in blob and "Swap gear" in blob and "Longbow" in blob
    it = tr.FakeInteraction(U, f"hunt:gear:track:{t['id']}:{U}", values=["Longbow"])
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    assert d["tool"] == "Longbow" and h.panels
    # a stale menu is ignored
    it = tr.FakeInteraction(U, f"hunt:gear:track:deadbeef:{U}", values=["Spear"])
    with tr.Harness():
        run(app._dispatch_component_inner(it))
    assert d["tool"] == "Longbow"
    # the same menu works inside a mythic fight and a tool you don't own is refused
    d["tracking"] = None
    d["_boss"] = {"creature": "Bigfoot", "biome": "village", "ts": int(time.time()), "eid": "ab12", "mhp": 100,
                  "mhp_max": 100, "turn": 1, "fallen": False, "guard": False, "enrage": False, "mdebuff": False, "log": []}
    assert "hunt:gear:myth:ab12" in json.dumps(app.build_myth_fight_components(U), ensure_ascii=False)
    d["owned_tools"] = ["Bare Hands", "Longbow", "Sniper Rifle"]
    it = tr.FakeInteraction(U, f"hunt:gear:myth:ab12:{U}", values=["Nuke Launcher"])
    with tr.Harness():
        run(app._dispatch_component_inner(it))
    assert d["tool"] == "Longbow"
    it = tr.FakeInteraction(U, f"hunt:gear:myth:ab12:{U}", values=["Sniper Rifle"])
    with tr.Harness():
        run(app._dispatch_component_inner(it))
    assert d["tool"] == "Sniper Rifle"


def test_mythic_fight_damage_follows_the_role():
    def avg_damage(tool):
        total = 0
        random.seed(2)
        for _ in range(200):
            d = _fresh(biome="village", tool=tool, owned_tools=[tool])
            d["health"].update(hp=100, max_hp=100)
            d["_boss"] = {"creature": "Bigfoot", "biome": "village", "ts": int(time.time()), "eid": "m1", "mhp": 5000,
                          "mhp_max": 5000, "turn": 1, "fallen": False, "guard": False, "enrage": False,
                          "mdebuff": True, "log": []}
            real = random.randint
            random.randint = lambda a, b: a if (a, b) != (1, 100) else 1       # always land the punch
            try:
                app.myth_fight_turn(U, "punch")
            finally:
                random.randint = real
            total += 5000 - d["_boss"]["mhp"] if d.get("_boss") else 0
        return total / 200
    assert avg_damage("Spear") > avg_damage("Slingshot")


def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(tt._ensure_db())
    failed = 0
    only = sys.argv[1:]
    for name in _all_tests():
        if only and name not in only:
            continue
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
