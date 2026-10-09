"""
Quest balance: claimed/unfinished quests can't clog the queue, quests roll on a player's first
action (no panel visit needed), generated quests only use biomes / rarities / crates / tool tiers the
player can reach, money tracks the player's biome earning power, and the weekly goal is reachable.

Runs without pytest:  python tests/test_quest_balance.py
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_quest_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run
U = "7301"


def _age_one_day(d):
    """Pretend a day passed: every quest looks a day older and the daily roll is due again."""
    for q in d["quests"]:
        q["created_date"] = (datetime.strptime(q["created_date"], "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    d["quests_last_roll"] = "1970-01-01"


def _finish_and_claim_all(uid):
    d = app.data[uid]
    for q in list(d["quests"]):
        if not q["claimed"]:
            q["completed"], q["progress"] = True, q["target"]
            assert app.quest_claim(uid, q["id"])["ok"]


def test_claimed_quests_never_block_new_ones_so_the_weekly_goal_is_reachable():
    tt._reset()
    d = tt._mk_user(U, level=300)
    claims = 0
    for day in range(8):
        app.quest_daily_roll_if_needed(U)
        fresh = [q for q in d["quests"] if not q["claimed"]]
        assert len(fresh) == gd.QUESTS_PER_DAY, (day, len(fresh), len(d["quests"]))   # always 3 new ones
        claims += len(fresh)
        _finish_and_claim_all(U)
        _age_one_day(d)
    assert len(d["quests"]) <= gd.QUESTS_MAX
    assert claims >= 21 > app.DAILY_QUEST_WEEKLY_TARGET


def test_unfinished_daily_quests_expire_after_a_day_or_two():
    tt._reset()
    d = tt._mk_user(U, level=300)
    app.quest_daily_roll_if_needed(U)
    for q in d["quests"]:
        q["_first"] = True                                    # (ids repeat inside one second, so tag them)
    _age_one_day(d)
    app.quest_daily_roll_if_needed(U)
    assert sum(1 for q in d["quests"] if q.get("_first")) == gd.QUESTS_PER_DAY     # yesterday's still around
    _age_one_day(d)
    app.quest_daily_roll_if_needed(U)
    assert not any(q.get("_first") for q in d["quests"])      # two days old: expired unpaid
    assert len(d["quests"]) <= 2 * gd.QUESTS_PER_DAY + gd.QUESTS_PER_DAY


def test_a_finished_but_unclaimed_quest_survives_the_expiry():
    tt._reset()
    d = tt._mk_user(U, level=300)
    app.quest_daily_roll_if_needed(U)
    q = d["quests"][0]
    q["completed"], q["progress"] = True, q["target"]
    for _ in range(3):
        _age_one_day(d)
        app.quest_daily_roll_if_needed(U)
    assert q["id"] in {x["id"] for x in d["quests"]}
    assert app.quest_claim(U, q["id"])["ok"]


def test_weekly_roll_expires_unfinished_and_clears_claimed():
    tt._reset()
    d = tt._mk_user(U, level=300)
    app.quest_weekly_roll_if_needed(U)
    for q in d["weekly_quests"]:
        q["_old"] = True
    assert len(d["weekly_quests"]) == gd.QUESTS_PER_WEEK
    d["weekly_quests"][0]["completed"] = True
    d["weekly_quests"][0]["claimed"] = True
    d["weekly_quests_last_roll"] -= app.WEEK_SECONDS + 5
    app.quest_weekly_roll_if_needed(U)
    assert not any(q.get("_old") for q in d["weekly_quests"]) and len(d["weekly_quests"]) == gd.QUESTS_PER_WEEK


def test_quests_roll_on_the_first_action_without_opening_the_panel():
    tt._reset()
    d = tt._mk_user(U, level=1)
    d["quests"], d["weekly_quests"] = [], []
    d.pop("quests_last_roll", None)
    d.pop("weekly_quests_last_roll", None)
    app.quest_progress(U, "hunts_done", 1)
    assert len(d["quests"]) == gd.QUESTS_PER_DAY and len(d["weekly_quests"]) == gd.QUESTS_PER_WEEK


def test_low_level_players_only_get_reachable_rarities_crates_and_tools():
    assert set(gd._quest_rarity_options(1, 1)) <= {"uncommon", "rare"}           # Village has no epic/legendary
    assert "epic" in gd._quest_rarity_options(100, 5)
    assert "legendary" not in gd._quest_rarity_options(200, 7)
    assert "legendary" in gd._quest_rarity_options(300, 8)
    low = gd._quest_crate_options(1, 1)
    assert "Legendary Crate" not in low and "Epic Crate" not in low
    assert "Legendary Crate" in gd._quest_crate_options(1000, 19)
    for _ in range(40):
        q = gd.generate_quest(next(t for t in gd.QUEST_TEMPLATES if t["id"] == "use_tool_tier"), 400, tool_tier=2)
        assert q["requires"]["tier"] <= 2
        q = gd.generate_quest(next(t for t in gd.QUEST_TEMPLATES if t["id"] == "hunt_biome"), 400, tool_tier=2)
        assert gd.BIOME_TOOL_TIER[q["requires"]["biome"]] <= 2


def test_meta_and_daily_claim_targets_are_reachable():
    for lvl in (1, 50, 200, 500, 1000):
        by_id = {t["id"]: gd.generate_quest(t, lvl, tool_tier=19) for t in gd.QUEST_TEMPLATES}
        assert by_id["claim_daily"]["target"] == 1
        assert by_id["complete_quests"]["target"] <= gd.QUESTS_PER_DAY - 1


def test_meta_quest_only_counts_claims_of_todays_quests():
    tt._reset()
    d = tt._mk_user(U, level=300)
    mk = lambda i, day: {"id": f"q{i}", "template": "catch_any", "stat": "animals_caught", "target": 1,
                         "progress": 1, "completed": True, "claimed": False, "xp_reward": 1, "money_reward": 0,
                         "created_date": day, "requires": {}, "description": "d", "icon": "x"}
    meta = {"id": "meta", "template": "complete_quests", "stat": "quests_completed_today", "target": 2,
            "progress": 0, "completed": False, "claimed": False, "xp_reward": 1, "money_reward": 0,
            "created_date": app.today_utc(), "requires": {}, "description": "d", "icon": "x"}
    d["quests"] = [meta, mk(1, "2000-01-01"), mk(2, app.today_utc())]
    d["quests_last_roll"] = app.today_utc()
    app.quest_claim(U, "q1")
    assert meta["progress"] == 0
    app.quest_claim(U, "q2")
    assert meta["progress"] == 1


def test_quest_money_tracks_biome_earning_power_not_raw_level():
    hunt = next(t for t in gd.QUEST_TEMPLATES if t["id"] == "hunt_any")
    money = {lvl: gd.generate_quest(hunt, lvl, tool_tier=19)["money_reward"] for lvl in (1, 50, 200, 500, 1000)}
    assert money[1] < 1_000                                   # was 5,100 on a 150-coin start
    assert money[1000] < 600_000                              # was 1.89M
    assert list(money.values()) == sorted(money.values())     # still grows as the player does
    # 60 hunts at the top biome earns >= 3x what the quest pays on top
    assert 60 * gd.crate_value_scale(1000) > 3 * money[1000]


def test_sell_quest_targets_are_sized_in_catches_of_the_players_biome():
    for tid, pool in (("earn_money", gd.QUEST_TEMPLATES), ("weekly_money", gd.WEEKLY_QUEST_TEMPLATES)):
        t = next(x for x in pool if x["id"] == tid)
        q1 = gd.generate_quest(t, 1)
        assert q1["target"] <= t["money_catches"] * gd.crate_value_scale(1) * 1.05
        assert q1["target"] < 100_000
        q1000 = gd.generate_quest(t, 1000)
        assert q1000["target"] > 50 * q1["target"]


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
