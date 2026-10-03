"""Players are told once about a running event on their first interaction.

Runs without pytest:  python tests/test_event_notify.py
"""
import asyncio
import os
import sys
import tempfile
import types

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_event_notify_pytest.db"))

import discord.ext.commands as _c  # noqa: E402
_c.Bot.run = lambda *a, **k: None

import app  # noqa: E402


def test_notified_once_per_event():
    uid = "evnotify1"
    app.init_user(uid)
    sent = []

    async def fake_send(interaction, text, color=0):
        sent.append(text)

    app.send_ephemeral_v2 = fake_send
    itx = types.SimpleNamespace(response=types.SimpleNamespace(is_done=lambda: True))

    app.stop_active_event()
    asyncio.run(app.maybe_notify_event_start(itx, uid))
    assert not sent                                   # no event, no notice

    ev = app.start_event("duck", "x")
    asyncio.run(app.maybe_notify_event_start(itx, uid))
    asyncio.run(app.maybe_notify_event_start(itx, uid))
    assert len(sent) == 1 and ev["name"] in sent[0]   # once, not twice

    app.stop_active_event()
    ev2 = app.start_event("shipwreck", "x")
    ev2["started_ts"] += 1                            # a distinct event run
    asyncio.run(app.maybe_notify_event_start(itx, uid))
    assert len(sent) == 2                             # a new event notifies again

    app.stop_active_event()
    app.start_event("admin_buff", "x")
    asyncio.run(app.maybe_notify_event_start(
        types.SimpleNamespace(response=types.SimpleNamespace(is_done=lambda: True)), uid))
    assert len(sent) == 2                             # buff has its own welcome card


if __name__ == "__main__":
    test_notified_once_per_event()
    print("ok")
