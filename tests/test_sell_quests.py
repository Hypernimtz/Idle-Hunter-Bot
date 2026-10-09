"""Selling animals advances the sell/earn-money quests (daily + weekly).

Runs without pytest:  python tests/test_sell_quests.py
"""
import os
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_sell_quests_pytest.db"))

import discord.ext.commands as _c  # noqa: E402
_c.Bot.run = lambda *a, **k: None

import app  # noqa: E402


def test_sell_all_advances_sell_quests():
    uid = "sellquest1"
    app.init_user(uid)
    d = app.data[uid]
    d.setdefault("money", 0)
    d["inv"] = ["Rabbit", "Rabbit", "Rabbit"]
    d["_pending_sell"] = 900
    mk = lambda stat, target: {"stat": stat, "target": target, "progress": 0, "template": "catch_any",
                               "completed": False, "claimed": False, "requires": {}}
    d["quests"] = [mk("animals_sold_quest", 3), mk("money_earned_quest", 1000)]
    d["weekly_quests"] = [mk("money_earned_quest", 5000)]
    d["quests_last_roll"] = app.today_utc()          # quests already rolled — progress must not re-roll them
    d["weekly_quests_last_roll"] = app.time.time()
    app.sell_all_inv(uid)
    assert d["quests"][0]["completed"], d["quests"][0]
    assert d["quests"][1]["progress"] == 900 and not d["quests"][1]["completed"]
    assert d["weekly_quests"][0]["progress"] == 900


if __name__ == "__main__":
    test_sell_all_advances_sell_quests()
    print("ok")
