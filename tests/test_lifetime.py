"""
Lifetime animals-caught leaderboard (survives prestige / reset) and the admin
"maintenance is ON" reminder (every 10 commands).

Runs without pytest:  python tests/test_lifetime.py
"""
import asyncio
import json
import os
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_lifetime_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr   # noqa: E402
import app                # noqa: E402
import backend            # noqa: E402

run = tr.run


def _fresh():
    tr._reset()
    app.maintenance_mode = False
    app._data_loaded_ok = True
    app._admin_maint_count.clear()


# ── lifetime animals ────────────────────────────────────────────────────────

def test_every_catch_advances_both_counts():
    _fresh()
    tr._mk_user("1")
    for _ in range(3):
        app.record_catch("1", "Rabbit", "Bare Hands", 10)
    d = app.data["1"]
    assert d["total_caught"] == 3 and d["stats"]["lifetime_caught"] == 3
    app.bump_caught("1")                                  # the mythic-kill path
    assert d["total_caught"] == 4 and app.lifetime_caught("1") == 4


def test_accounts_that_predate_the_counter_start_from_their_current_run():
    _fresh()
    d = tr._mk_user("2", total_caught=250)
    d["stats"].pop("lifetime_caught", None)
    assert app.lifetime_caught("2") == 250                # read-time fallback
    app.record_catch("2", "Rabbit", "Bare Hands", 1)
    assert d["total_caught"] == 251 and d["stats"]["lifetime_caught"] == 251   # no off-by-one on first bump


def test_prestige_wipes_the_run_but_keeps_lifetime():
    _fresh()
    d = tr._mk_user("3", total_caught=400)
    d["stats"]["lifetime_caught"] = 900                   # 500 from earlier runs
    app.apply_account_reset("3", prestige=True)
    assert d["total_caught"] == 0 and d["stats"]["lifetime_caught"] == 900
    app.record_catch("3", "Rabbit", "Bare Hands", 1)
    assert d["total_caught"] == 1 and app.lifetime_caught("3") == 901
    # an admin reset (no prestige) behaves the same, and an old account loses nothing
    e = tr._mk_user("4", total_caught=70)
    e["stats"].pop("lifetime_caught", None)
    app.apply_account_reset("4", prestige=False)
    assert e["total_caught"] == 0 and app.lifetime_caught("4") == 70


def test_both_boards_exist_and_rank_differently():
    _fresh()
    a = tr._mk_user("5", total_caught=10)                 # prestiged a lot: big lifetime, tiny run
    a["stats"]["lifetime_caught"] = 5000
    b = tr._mk_user("6", total_caught=300)                # never prestiged
    b["stats"]["lifetime_caught"] = 300
    assert "Total Animals Caught" in app.HUNTER_LB_STATS and "Lifetime Animals Caught" in app.HUNTER_LB_STATS
    run_board = app._lb_period_value("5", "Total Animals Caught", "all"), app._lb_period_value("6", "Total Animals Caught", "all")
    life_board = app._lb_period_value("5", "Lifetime Animals Caught", "all"), app._lb_period_value("6", "Lifetime Animals Caught", "all")
    assert run_board == (10, 300) and life_board == (5000, 300)


def test_leaderboard_panel_renders_the_lifetime_board_with_hints():
    _fresh()
    a = tr._mk_user("7", total_caught=1)
    a["stats"]["lifetime_caught"] = 1234
    app._LB_CACHE.clear()
    comps = app.build_leaderboard_v2_components("7", None, "hunter", "global", "Lifetime Animals Caught", 0, "all")
    blob = json.dumps(comps, ensure_ascii=False)
    assert "Lifetime Animals Caught" in blob and "1,234" in blob
    assert "Whole account, never resets" in blob and "Since your last prestige" in blob
    # every option description stays inside Discord's 100-character limit
    for row in comps[0]["components"]:
        for c in row.get("components", []):
            for o in c.get("options", []) if isinstance(c, dict) else []:
                assert len(o.get("description", "")) <= 100


def test_daily_lifetime_gain_starts_at_zero_and_counts_new_catches():
    _fresh()
    a = tr._mk_user("8", total_caught=50)
    a["stats"]["lifetime_caught"] = 500
    a["joined_date"] = "2000-01-01"
    assert app._lb_period_value("8", "Lifetime Animals Caught", "daily") == 0
    app.bump_caught("8", 4)
    assert app._lb_period_value("8", "Lifetime Animals Caught", "daily") == 4


def test_stats_field_round_trips_through_the_backend():
    s = backend.Stats.from_dict({"lifetime_caught": 77, "mystery": 1})
    out = s.to_dict()
    assert out["lifetime_caught"] == 77 and out["mystery"] == 1


def test_profile_stats_page_shows_both_counts():
    _fresh()
    d = tr._mk_user("9", total_caught=12)
    d["stats"]["lifetime_caught"] = 345
    blob = json.dumps(app.build_stats_components("9", "Hunter", "9"), ensure_ascii=False) \
        if hasattr(app, "build_stats_components") else ""
    if blob:
        assert "this run" in blob and "345" in blob


# ── admin maintenance reminder ──────────────────────────────────────────────

class _Resp:
    def __init__(self, done=True):
        self.done = done

    def is_done(self):
        return self.done


def _nudges(uid, commands, *, maint=True, done=True):
    """Run `commands` admin commands, return how many reminders were shown and their text."""
    shown = []

    async def eph(interaction, text, color=0):
        shown.append(text)
    real = app.send_ephemeral_v2
    app.send_ephemeral_v2 = eph
    app.maintenance_mode = maint
    try:
        for _ in range(commands):
            it = tr.FakeInteraction(uid, "x")
            it.response = _Resp(done)
            run(app._admin_maintenance_nudge(it, uid))
    finally:
        app.send_ephemeral_v2 = real
        app.maintenance_mode = False
    return shown


def test_admin_is_reminded_every_tenth_command_during_maintenance():
    _fresh()
    shown = _nudges("100", 9)
    assert shown == []                                            # nothing for the first 9
    _fresh()
    shown = _nudges("100", 10)
    assert len(shown) == 1 and "Maintenance mode is ON" in shown[0] and "10 commands" in shown[0]
    _fresh()
    assert len(_nudges("100", 30)) == 3
    _fresh()
    assert len(_nudges("100", 25)) == 2


def test_no_reminder_when_maintenance_is_off_and_the_count_resets():
    _fresh()
    assert _nudges("101", 30, maint=False) == []
    _nudges("101", 7)                                             # 7 into the cycle ...
    _nudges("101", 5, maint=False)                                # ... maintenance ends: count cleared
    assert len(_nudges("101", 9)) == 0                            # a fresh cycle, not 7+9
    assert len(_nudges("101", 1)) == 1


def test_reminder_waits_for_an_acknowledged_interaction_and_counts_per_admin():
    _fresh()
    assert _nudges("102", 12, done=False) == []                   # can't send yet (no ack) ...
    assert len(_nudges("102", 1)) == 1                            # ... so it fires on the next acked command
    assert _nudges("103", 5) == []                                # another admin has their own count


def test_common_init_sends_it_for_admins_but_never_for_players():
    _fresh()
    admin, player = "104", "105"
    app.BOT_ADMIN_ID.append(admin)
    tr._mk_user(admin)
    tr._mk_user(player)
    shown = []

    async def eph(interaction, text, color=0):
        shown.append(text)

    async def noop(*a, **k):
        return None
    saved = (app.send_ephemeral_v2, app.update_user_servers)
    app.send_ephemeral_v2, app.update_user_servers = eph, noop
    app.maintenance_mode = True
    try:
        for _ in range(10):
            it = tr.FakeInteraction(admin, "x")
            it.user.name = "adm"
            it.type = app.discord.InteractionType.application_command
            assert run(app._common_init(it)) == admin
        assert len([t for t in shown if "Maintenance mode is ON" in t]) == 1
        shown.clear()
        # a normal player is simply refused by maintenance — no admin reminder text
        for _ in range(10):
            it = tr.FakeInteraction(player, "x")
            it.user.name = "plr"
            it.type = app.discord.InteractionType.application_command
            sent = []

            async def fu(interaction, comps, *, ephemeral=False):
                sent.append(json.dumps(comps))
            sv = app.send_v2_followup
            app.send_v2_followup = fu
            try:
                assert run(app._common_init(it)) is None
            finally:
                app.send_v2_followup = sv
            assert "under maintenance" in sent[0]
        assert shown == []
    finally:
        app.send_ephemeral_v2, app.update_user_servers = saved
        app.maintenance_mode = False
        app.BOT_ADMIN_ID.remove(admin)


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
