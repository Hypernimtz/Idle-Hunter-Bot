"""
"ih <command>" text commands + staff-only command registration.

Runs without pytest:  python tests/test_prefix.py
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_prefix_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr   # noqa: E402
import app                # noqa: E402
import backend            # noqa: E402

run = tr.run
POSTS, DELETES = [], []
_ids = iter(range(7_000_000_000_000, 8_000_000_000_000))


async def _fake_request(route, **kw):
    if getattr(route, "method", "") == "POST":
        POSTS.append(kw.get("json", {}))
        return {"id": str(next(_ids))}
    return {}


async def _fake_delete_later(channel_id, message_id, delay):
    DELETES.append((channel_id, message_id, delay))

app.bot.http.request = _fake_request
app._msg_delete_later = _fake_delete_later


def _msg(uid, content, mentions=()):
    author = SimpleNamespace(id=int(uid), name=f"user{uid}", display_name=f"user{uid}", bot=False)
    return SimpleNamespace(id=next(_ids), author=author, content=content, guild=None, mentions=list(mentions),
                           channel=SimpleNamespace(id=555))


def _say(uid, content, **kw):
    """Send a text message and return (handled, [posted payloads])."""
    app._prefix_last.clear()
    POSTS.clear()
    DELETES.clear()
    handled = run(app.handle_prefix_message(_msg(uid, content, **kw)))
    return handled, list(POSTS)


def _text(payload):
    return json.dumps(payload.get("components", payload.get("content")), ensure_ascii=False)


def _fresh(uid, **over):
    tr._reset()
    app.maintenance_mode = False          # the dev machine's config.json can have maintenance switched on
    app._data_loaded_ok = True            # tests never run load_all_data()
    return tr._mk_user(uid, **over)


# ── recognising commands ──────────────────────────────────────

def test_only_the_ih_word_with_a_space_counts():
    _fresh("1001")
    for chat in ("ihop is great", "hello ih hunt", "ihhunt", "i hunt", "", "  hunt"):
        handled, posts = _say("1001", chat)
        assert not handled and not posts, chat
    assert _say("1001", "ih hunt")[0] and _say("1001", "IH Hunt")[0] and _say("1001", "  ih   hunt ")[0]


def test_resolve_aliases_groups_defaults_and_refuses_admin_and_blocked():
    r = lambda text: app._prefix_resolve(text.split())
    assert r("hunt")[0].qualified_name == "hunt" and r("h")[0].qualified_name == "hunt"
    assert r("d")[0].qualified_name == "daily"
    assert r("bj")[0].qualified_name == "gamble blackjack" and r("cf")[0].qualified_name == "gamble coinflip"
    assert r("gamble")[0].qualified_name == "gamble menu"
    assert r("gamble slots")[0].qualified_name == "gamble slots" and r("gamble slots")[1] == 2
    assert r("tribe")[0].qualified_name == "tribe menu" and r("tribe info")[0].qualified_name == "tribe info"
    assert r("q")[0].qualified_name == "quests daily" and r("qw")[0].qualified_name == "quests weekly"
    assert r("updates")[0].qualified_name == "update view"
    for nope in ("nonsense", "bot admin", "inspect user", "giveaway start", "report", "suggest", "gift", "update add"):
        assert r(nope)[0] is None, nope
    assert r("")[0] is None


def test_every_command_a_text_message_can_reach_is_safe():
    """No admin-gated command, and no command in a staff-only group, is reachable from text."""
    seen = []

    def walk(c, prefix=""):
        if isinstance(c, app.app_commands.Group):
            for s in c.commands:
                walk(s, prefix + c.name + " ")
        else:
            seen.append((prefix + c.name, c))
    for c in app.bot.tree.get_commands():
        walk(c)
    reachable = 0
    for name, cmd in seen:
        got, _ = app._prefix_resolve(name.split())
        if got is not None:
            reachable += 1
            assert not cmd.checks, name
            assert name.split(" ")[0] not in ("bot", "inspect", "updates")
    assert reachable >= 40


# ── arguments ─────────────────────────────────────────────────

def test_arguments_bind_by_type_and_bad_ones_get_a_usage_hint():
    _fresh("1002")
    bind = lambda cmd, toks, mentions=(): run(app._prefix_bind(cmd, toks, _msg("1002", "x", mentions)))
    prof = app.bot.tree.get_command("profile")
    assert bind(prof, []) == ({}, "")
    other = SimpleNamespace(id=1003, name="other")
    kw, err = bind(prof, ["<@1003>"], [other])
    assert kw == {"user": other} and not err
    assert bind(prof, ["whatever"]) == (None, "")                       # optional + unparseable => chat, silent
    use = app.bot.tree.get_command("use")
    kw, err = bind(use, ["War", "Horn"])
    assert kw == {"item": "War Horn"}                                    # the last string option swallows the rest
    kw, err = bind(use, [])
    assert kw is None and "ih use" in err and "<item>" in err
    hunt = app.bot.tree.get_command("hunt")
    assert bind(hunt, []) == ({}, "") and bind(hunt, ["for", "deer"]) == (None, "")
    tribe_create = app.bot.tree.get_command("tribe").get_command("create")
    kw, _ = bind(tribe_create, ["Wolves"])
    assert kw == {"name": "Wolves"}


# ── running commands ──────────────────────────────────────────

def test_commands_reply_in_the_channel_as_a_reply_to_the_message():
    _fresh("1004")
    msg = _msg("1004", "ih daily")
    app._prefix_last.clear()
    POSTS.clear()
    assert run(app.handle_prefix_message(msg))
    assert POSTS, "the daily panel should have been posted"
    p = POSTS[0]
    assert p["flags"] & 32768 or p["flags"] == app.V2_FLAGS            # a Components V2 message
    assert p["message_reference"]["message_id"] == str(msg.id)
    assert p["allowed_mentions"]["parse"] == [] and "Daily" in _text(p)
    assert "daily:claim:1004" in _text(p) and "vote:claim" in _text(p)  # the buttons are the real ones


def test_hunting_by_text_actually_hunts_and_obeys_the_cooldown():
    d = _fresh("1005")
    handled, posts = _say("1005", "ih hunt")
    assert handled and posts and d["stats"].get("lifetime_hunts", 0) == 1
    assert "hunt:again:1005" in _text(posts[0])
    _, posts = _say("1005", "ih hunt")                                   # immediate retry
    assert d["stats"]["lifetime_hunts"] == 1                             # hunt cooldown, not a second hunt
    assert posts and "wait" in _text(posts[0]).lower() and DELETES      # the cooldown notice is a vanishing reply


def test_text_commands_are_rate_limited_per_player():
    _fresh("1006")
    app._prefix_last.clear()
    POSTS.clear()
    run(app.handle_prefix_message(_msg("1006", "ih menu")))
    first = len(POSTS)
    run(app.handle_prefix_message(_msg("1006", "ih menu")))              # inside the cooldown: ignored
    assert first >= 1 and len(POSTS) == first
    time.sleep(app.PREFIX_COOLDOWN + 0.05)
    run(app.handle_prefix_message(_msg("1006", "ih menu")))
    assert len(POSTS) > first


def test_gating_still_applies_maintenance_ban_and_verify():
    d = _fresh("1007")
    old = app.maintenance_mode
    app.maintenance_mode = True
    try:
        _, posts = _say("1007", "ih hunt")
    finally:
        app.maintenance_mode = old
    assert posts and "Maintenance" in _text(posts[0]) and d["stats"].get("lifetime_hunts", 0) == 0
    assert DELETES                                                       # "private" replies are scheduled to vanish
    d["ban"] = {"active": True, "expires_ts": 0, "reason": "test"}
    _, posts = _say("1007", "ih hunt")
    assert posts and d["stats"].get("lifetime_hunts", 0) == 0
    d["ban"] = {"active": False}
    d["verify"] = {"needed": True, "time": 0, "code": "ABCD"}
    _, posts = _say("1007", "ih hunt")
    assert posts and d["stats"].get("lifetime_hunts", 0) == 0


def test_private_replies_delete_themselves_and_forms_are_refused_politely():
    _fresh("1008")
    handled, posts = _say("1008", "ih use")                              # missing the required item
    assert handled and posts and "ih use" in _text(posts[0]) and DELETES
    assert DELETES[0][2] == app.PREFIX_EPHEMERAL_TTL
    cmd = app.bot.tree.get_command("hunt")
    real = cmd._callback

    async def wants_a_form(interaction):
        await interaction.response.send_modal(object())
    cmd._callback = wants_a_form
    try:
        _, posts = _say("1008", "ih hunt")
    finally:
        cmd._callback = real
    assert posts and "needs a form" in _text(posts[-1]), posts


def test_the_bare_prefix_shows_the_cheat_sheet_and_chatter_stays_silent():
    _fresh("1009")
    handled, posts = _say("1009", "ih")
    assert handled and posts and "Text commands" in _text(posts[0]) and "ih hunt" in _text(posts[0])
    handled, posts = _say("1009", "ih commands")
    assert handled and posts and "Text commands" in _text(posts[0])
    handled, posts = _say("1009", "ih what is going on")
    assert handled and not posts                                          # ours, but nothing to do


def test_it_stands_in_for_an_interaction_well_enough():
    mi = app.MessageInteraction(_msg("1010", "ih x"), app.bot.tree.get_command("hunt"))
    assert mi.user.id == 1010 and mi.channel_id == 555 and mi.guild is None and mi.guild_id is None
    assert mi.type == app.discord.InteractionType.application_command and mi.data["name"] == "hunt"
    assert not mi.response.is_done()
    run(mi.response.defer())
    assert mi.response.is_done()
    try:
        run(mi.response.send_modal(None))
        assert False, "send_modal should be refused"
    except app.PrefixUnsupported:
        pass


# ── staff-only registration ───────────────────────────────────

def test_staff_commands_register_to_the_guild_only_when_configured():
    code = (
        "import sys, os, tempfile, json\n"
        f"sys.path.insert(0, {ROOT!r})\n"
        "os.environ['SQLITE_PATH'] = os.path.join(tempfile.gettempdir(), 'ih_staff_pytest.db')\n"
        "os.environ['STAFF_GUILD_ID'] = '424242424242424242'\n"
        "import discord, discord.ext.commands as c\n"
        "c.Bot.run = lambda *a, **k: None\n"
        "import app\n"
        "g = discord.Object(id=424242424242424242)\n"
        "out = {'global': sorted(x.name for x in app.bot.tree.get_commands()),\n"
        "       'staff': sorted(x.name for x in app.bot.tree.get_commands(guild=g)),\n"
        "       'update_public': sorted(x.name for x in app.update_group.commands),\n"
        "       'update_staff': sorted(x.name for x in app.updates_staff_group.commands),\n"
        "       'fallback': len(app._STAFF_COMMANDS)}\n"
        "print('RESULT' + json.dumps(out))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=ROOT, timeout=120,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT")), None)
    assert line, ((r.stdout or "")[-500:], (r.stderr or "")[-800:])
    out = json.loads(line[6:])
    assert {"bot", "inspect", "updates"} <= set(out["staff"]) and out["fallback"] == 3
    for staff_only in ("bot", "inspect", "updates"):
        assert staff_only not in out["global"], staff_only
    assert {"giveaway", "update", "hunt", "daily", "gamble"} <= set(out["global"])   # still public / per-server
    assert out["update_public"] == ["view"] and out["update_staff"] == ["add", "change", "control"]


def test_balance_aliases_work_as_text_commands():
    _fresh("1011", money=4242, gems=7)
    for word in ("bal", "balance", "money", "cash", "gems", "wallet"):
        handled, posts = _say("1011", f"ih {word}")
        assert handled and posts and "4,242" in _text(posts[0]), word
    other = SimpleNamespace(id=1012, name="o", display_name="o")
    tr._mk_user("1012", money=99)
    handled, posts = _say("1011", "ih bal <@1012>", mentions=[other])
    assert posts and "99" in _text(posts[0])
    assert "ih bal" in _text(_say("1011", "ih")[1][0])


def test_text_commands_work_in_dms_threads_and_servers():
    import discord
    _fresh("1013", money=555)
    sent = []

    async def capture(route, **kw):
        if getattr(route, "method", "") == "POST" and kw.get("json", {}).get("components"):   # not the typing ping
            sent.append((route.channel_id, kw["json"]))
        return {"id": str(next(_ids))}
    app.bot.http.request = capture
    try:
        app._prefix_last.clear()
        # a DM with the bot: no guild at all, a private channel
        dm = _msg("1013", "ih bal")
        dm.channel = SimpleNamespace(id=111, type=discord.ChannelType.private)
        assert run(app.handle_prefix_message(dm)) and sent[-1][0] == 111 and "555" in _text(sent[-1][1])
        # a thread inside a server: the reply goes to the thread's own id
        app._prefix_last.clear()
        thread = _msg("1013", "ih bal")
        thread.guild = SimpleNamespace(id=9, get_member=lambda i: None, name="srv")
        thread.channel = SimpleNamespace(id=222, type=discord.ChannelType.public_thread)
        assert run(app.handle_prefix_message(thread)) and sent[-1][0] == 222
        # an ordinary server channel
        app._prefix_last.clear()
        guild_msg = _msg("1013", "IH   BAL")
        guild_msg.guild = SimpleNamespace(id=9, get_member=lambda i: None, name="srv")
        guild_msg.channel = SimpleNamespace(id=333, type=discord.ChannelType.text)
        assert run(app.handle_prefix_message(guild_msg)) and sent[-1][0] == 333
    finally:
        app.bot.http.request = _fake_request


def test_without_a_staff_guild_nothing_changes():
    names = {c.name for c in app.bot.tree.get_commands()}
    assert {"bot", "inspect", "update", "giveaway"} <= names and "updates" not in names
    assert {c.name for c in app.update_group.commands} == {"view", "control", "add", "change"}
    assert app._STAFF is None


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
