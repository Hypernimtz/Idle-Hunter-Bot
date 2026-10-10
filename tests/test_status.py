"""
Connection-status notifier: online / reconnected / connection lost / website down / shutdown,
plus /inspect status and the website publishers' `connected` flag.

Runs without pytest:  python tests/test_status.py
"""
import asyncio
import json
import os
import sys
import tempfile
import time
from types import SimpleNamespace

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_status_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr   # noqa: E402
import app                # noqa: E402
import backend            # noqa: E402
import leaderboard_push   # noqa: E402

run = tr.run
SENT = []


async def _fake_request(route, **kw):
    if getattr(route, "method", "") == "POST":
        SENT.append((getattr(route, "channel_id", None), kw.get("json", {})))
    return {"id": "1"}


app.bot.http.request = _fake_request


def _reset(**state):
    SENT.clear()
    app._status_last.clear()
    app._conn.update({"down_since": 0.0, "warned": False, "site_warned": False, "events": []})
    app._boot_info["down_secs"] = 0
    app.STATUS_NOTIFY = True
    app.STATUS_NOTIFY_BOOT = True          # the boot/shutdown tests below opt in; see the silent-by-default test
    app.STATUS_NOTIFY_WEBSITE = True       # the website tests opt in; see the off-by-default test
    app.STATUS_CHANNEL_ID = state.get("channel", 4242)
    app._lb_publisher = state.get("lb")
    app._cl_publisher = state.get("cl")


def _text():
    return json.dumps([p for _c, p in SENT], ensure_ascii=False)


def _pub(connected, task=True, fail_since=0.0, unsupported=0):
    return SimpleNamespace(connected=connected, task=object() if task else None, fail_since=fail_since,
                           unsupported=unsupported)


def test_a_site_without_the_changelog_endpoint_is_not_shown_as_broken():
    _reset(cl=_pub(False, unsupported=405))
    r = app.status_report()
    assert "no endpoint for it yet (HTTP 405)" in r and "**not connected**" not in r.split("Website changelog")[1].split("\n")[0]


def test_online_notice_reports_what_is_connected_and_the_downtime():
    _reset(lb=_pub(True), cl=_pub(False))
    app._boot_info["down_secs"] = 7 * 60
    run(app.status_online())
    assert len(SENT) == 1 and SENT[0][0] == 4242                                   # the status channel
    t = _text()
    assert "Idle Hunter is online" in t and "Back after about **7 min** offline" in t
    assert "Website leaderboard: connected" in t and "Website changelog: **not connected**" in t
    assert "Database" in t and "Admin commands" in t and "latest update" in t
    assert SENT[0][1]["allowed_mentions"] == {"parse": []}                           # a status post never pings
    SENT.clear()
    _reset()
    run(app.status_online())
    assert "Back after" not in _text()                                              # a normal boot says nothing about downtime


def test_ordinary_boots_and_shutdowns_are_silent_by_default():
    _reset()
    app.STATUS_NOTIFY_BOOT = False
    try:
        run(app.status_online())
        run(app.status_shutdown())
        assert not SENT                                                              # a deploy restart sends nothing
        app._boot_info["down_secs"] = 3 * 60
        run(app.status_online())
        assert not SENT                                                              # a short outage is still routine
        app._boot_info["down_secs"] = 45 * 60
        run(app.status_online())
        assert len(SENT) == 1 and "Back after about **45 min** offline" in _text()   # a long outage is not
        SENT.clear()
        run(app.status_watch_once(time.time()))
        app._conn["down_since"] = time.time() - 180
        assert run(app.status_watch_once()) == ["lost"] and SENT                    # problems still get through
    finally:
        app.STATUS_NOTIFY_BOOT = True


def test_report_marks_unconfigured_failing_and_staff_states():
    _reset(lb=None, cl=_pub(False, task=False))
    r = app.status_report()
    assert "Website leaderboard: not configured" in r and "Website changelog: not configured" in r
    _reset(lb=_pub(False))
    assert "Website leaderboard: **not connected**" in app.status_report()
    old = app._staff_state
    try:
        for state, needle in (("off", "global"), ("synced", "staff server"), ("fallback", "registered globally")):
            app._staff_state = state
            assert needle in app.status_report(), state
    finally:
        app._staff_state = old


def test_short_blips_are_logged_but_long_drops_are_announced_once():
    _reset()
    # a 5 s blip: remembered, not announced
    app._conn["down_since"] = time.time() - 5
    run(app.status_recovered())
    assert not SENT and app._conn["down_since"] == 0 and any("reconnected" in e[1] for e in app._conn["events"])
    # a 3 minute drop: the watchdog speaks up once, recovery follows
    app._conn["down_since"] = time.time() - 180
    assert run(app.status_watch_once()) == ["lost"]
    assert run(app.status_watch_once()) == []                                      # not again while it's still down
    assert "Discord connection lost" in _text() and "cut off from Discord for **3 min**" in _text()
    run(app.status_recovered())
    assert "Reconnected" in _text() and app._conn["down_since"] == 0 and not app._conn["warned"]
    # a 45 s drop that never tripped the 90 s watchdog still gets a "reconnected"
    SENT.clear()
    app._status_last.clear()
    app._conn["down_since"] = time.time() - 45
    run(app.status_recovered())
    assert len(SENT) == 1 and "45s" in _text()
    # recovery with no recorded drop (resume right after boot) is silent
    SENT.clear()
    run(app.status_recovered())
    assert not SENT


def test_disconnect_handler_records_only_the_first_drop():
    _reset()
    run(app.on_disconnect())
    first = app._conn["down_since"]
    assert first > 0
    time.sleep(0.02)
    run(app.on_disconnect())
    assert app._conn["down_since"] == first


def test_website_outage_warns_once_and_announces_recovery():
    now = time.time()
    pub = _pub(False, fail_since=now - 30 * 60)
    _reset(lb=pub)
    assert run(app.status_watch_once(now)) == ["site"]
    assert "Website not connected" in _text() and "30 min" in _text()
    assert run(app.status_watch_once(now + 60)) == []                              # only once
    pub.connected, pub.fail_since = True, 0.0
    assert run(app.status_watch_once(now + 120)) == ["site_ok"]
    assert "Website connected again" in _text()
    assert run(app.status_watch_once(now + 180)) == []
    # a brand-new failure that is still inside the grace period stays quiet
    _reset(lb=_pub(False, fail_since=now - 60))
    assert run(app.status_watch_once(now)) == []


def test_website_notices_are_off_by_default_and_never_send():
    now = time.time()
    pub = _pub(False, fail_since=now - 30 * 60)
    _reset(lb=pub)
    app.STATUS_NOTIFY_WEBSITE = False
    try:
        assert run(app.status_watch_once(now)) == [] and not SENT
        assert run(app.status_watch_once(now + 3600)) == [] and not SENT
        assert "Website leaderboard" in app.status_report()                           # /inspect status still shows it
    finally:
        app.STATUS_NOTIFY_WEBSITE = True
    assert os.getenv("STATUS_NOTIFY_WEBSITE") is None and app.STATUS_NOTIFY_WEBSITE in (True, False)


def test_shutdown_notice_and_the_off_switch():
    _reset()
    run(app.status_shutdown())
    assert "shutting down" in _text() and "Restarting" in _text()
    SENT.clear()
    app.STATUS_NOTIFY = False
    run(app.status_shutdown())
    run(app.status_online())
    assert not SENT                                                                  # STATUS_NOTIFY=0 silences everything
    app.STATUS_NOTIFY = True


def test_notices_are_throttled_and_a_failing_send_never_raises():
    _reset()
    assert run(app.status_post("t", "b", 0x111111, key="k", min_gap=60)) is True
    assert run(app.status_post("t", "b", 0x111111, key="k", min_gap=60)) is False        # inside the gap
    real = app.bot.http.request

    async def boom(route, **kw):
        raise RuntimeError("discord is down too")
    app.bot.http.request = boom
    try:
        assert run(app.status_post("t", "b", 0x111111, key="other")) is False              # swallowed, not raised
    finally:
        app.bot.http.request = real


def test_without_a_status_channel_it_dms_the_owner():
    _reset(channel=0)
    app._owner_dm_cache.clear()

    async def fake_fetch(uid):
        return SimpleNamespace(create_dm=lambda: _dm())

    async def _dm():
        return SimpleNamespace(id=777)
    real = app.bot.fetch_user
    app.bot.fetch_user = fake_fetch
    try:
        run(app.status_shutdown())
    finally:
        app.bot.fetch_user = real
    assert SENT and SENT[0][0] == 777


def test_inspect_status_command_is_admin_only_and_shows_the_report():
    _reset(lb=_pub(True))
    cmd = next(c for c in app.inspect_group.commands if c.name == "status")
    assert cmd.checks
    out = []

    async def follow(interaction, comps, *, ephemeral=False):
        out.append(json.dumps(comps, ensure_ascii=False))
    app._conn_log("something happened")
    with tr.Harness():
        app.send_v2_followup = follow
        run(cmd.callback(tr.FakeInteraction("1", "x")))
    assert "Connection status" in out[0] and "Website leaderboard: connected" in out[0] and "something happened" in out[0]
    assert "<#4242>" in out[0]


def test_publishers_expose_a_connected_flag():
    lb = leaderboard_push.LeaderboardPublisher(lambda: {}, lambda: {})
    cl = leaderboard_push.ChangelogPublisher(lambda: [])
    assert lb.connected is False and cl.connected is False and lb.fail_since == 0.0
    # drive the real upload loop once with a fake HTTP layer
    async def go(status):
        lb2 = leaderboard_push.LeaderboardPublisher(lambda: {}, lambda: {})
        lb2._send = lambda payload: (status, "")
        t = asyncio.ensure_future(lb2._run())
        await asyncio.sleep(0.2)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        return lb2
    ok = run(go(200))
    assert ok.connected is True and ok.fail_since == 0.0
    bad = run(go(500))
    assert bad.connected is False and bad.fail_since > 0


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
