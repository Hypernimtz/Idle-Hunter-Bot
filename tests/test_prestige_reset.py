"""
Prestige / account reset: run-scoped state (quests, healing stock, live fights, HP, Field Guide,
one-shot item flags) is wiped so nothing from the old run carries over, prestige is blocked mid-fight,
the daily-reward prestige bonus is capped, the final biome unlocks before Prestige, and the panel
states the incremental reward.

Runs without pytest:  python tests/test_prestige_reset.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_prestige_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr            # noqa: E402
import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "7601"


def _veteran(**over):
    tt._reset()
    d = tt._mk_user(U, level=1000, money=2_000_000_000, gems=5000)
    d["quests"] = [{"id": "q1", "template": "catch_any", "stat": "animals_caught", "target": 1, "progress": 1,
                    "completed": True, "claimed": False, "xp_reward": 81_000, "money_reward": 17_000_000,
                    "created_date": app.today_utc(), "requires": {}}]
    d["weekly_quests"] = [dict(d["quests"][0], id="w1")]
    d["quests_last_roll"] = app.today_utc()
    d["healing_inv"] = {"Bandage": 9}
    d["fight"] = {"kind": "animal", "animal": "Wolf", "ts": time.time()}
    d["tracking"] = {"creature": "x", "expires_ts": time.time() + 999}
    d["health"] = {"hp": 3, "max_hp": 100, "last_regen_ts": time.time(), "injuries": ["broken_arm"],
                   "rookie_revive_used": True}
    d["guide_seen"] = ["village", "forest"]
    d["_camp_rations"] = 30
    d["_lucky_hammer_active"] = d["_danger_whistle_active"] = True
    d.update(over)
    return d


def test_reset_clears_quests_so_old_rewards_cant_cross_into_the_new_run():
    d = _veteran()
    xp_before = d["xp"]
    app.apply_account_reset(U, prestige=True)
    assert d["quests"] == [] and d["weekly_quests"] == [] and d["quests_last_roll"] == ""
    assert not app.quest_claim(U, "q1")["ok"] and not app.quest_claim(U, "w1", list_key="weekly_quests")["ok"]
    assert d["level"] == 1 and d["xp"] == 0 <= xp_before
    app.quest_daily_roll_if_needed(U)                       # a fresh, level-1 batch rolls
    assert len(d["quests"]) == gd.QUESTS_PER_DAY and all(q["xp_reward"] < 2_000 for q in d["quests"])


def test_reset_clears_healing_fight_tracking_hp_guide_and_item_flags():
    d = _veteran()
    app.apply_account_reset(U, prestige=True)
    assert d["healing_inv"] == {} and d["fight"] is None and d["tracking"] is None
    assert d["health"]["hp"] == d["health"]["max_hp"] and d["health"]["injuries"] == []
    assert d["guide_seen"] == [] and d["_camp_rations"] == 0
    assert "_lucky_hammer_active" not in d and "_danger_whistle_active" not in d
    assert d["prestige"] == 1 and d["gems"] == app.RESET_GEM_CAP


def test_admin_reset_keeps_the_prestige_count_but_still_clears_run_state():
    d = _veteran(prestige=3)
    app.apply_account_reset(U, prestige=False)
    assert d["prestige"] == 3 and d["quests"] == [] and d["fight"] is None


def test_prestige_is_blocked_during_a_fight():
    d = _veteran()
    it = tr.FakeInteraction(U, f"prestige:confirm:{U}")
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    assert "Finish your fight" in " ".join(h.ephemerals) and d["prestige"] == 0 and d["level"] == 1000
    d["fight"] = None
    it = tr.FakeInteraction(U, f"prestige:confirm:{U}")
    with tr.Harness() as h:
        run(app._dispatch_component_inner(it))
    assert d["prestige"] == 1 and d["level"] == 1


def test_panel_shows_incremental_reward_and_warns_about_unclaimed_quests():
    d = _veteran(prestige=1)
    d["fight"] = None
    txt = str(app.build_prestige_components(U))
    assert "gain **+20%**" in txt and "new total **+40%**" in txt
    assert "haven't claimed" in txt
    d["quests"], d["weekly_quests"] = [], []
    assert "haven't claimed" not in str(app.build_prestige_components(U))


def test_daily_prestige_bonus_is_capped_but_the_stat_boost_is_not():
    assert app.PRESTIGE_DAILY_MAX == 10
    tt._reset()
    d = tt._mk_user(U, prestige=40)
    assert app.get_prestige_boost(U) == 40 * app.PRESTIGE_BOOST_PER       # unchanged


def test_celestial_peaks_unlocks_before_prestige_level():
    lvl = dict(gd.BIOME_LEVELS)["celestial_peaks"]
    assert lvl < app.PRESTIGE_MIN_LEVEL


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
