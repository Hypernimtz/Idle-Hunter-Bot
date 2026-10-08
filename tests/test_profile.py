"""
Profile bio + Profile Editor (off by default) + choose-what-shows multi-select.

Runs without pytest:  python tests/test_profile.py
"""
import asyncio
import json
import os
import sys
import tempfile
from types import SimpleNamespace

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_profile_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr   # noqa: E402
import app                # noqa: E402
import backend            # noqa: E402

run = tr.run


def _fresh(uid="1", **over):
    tr._reset()
    app.maintenance_mode = False
    app._data_loaded_ok = True
    d = tr._mk_user(uid, **over)
    d["money"] = 123456
    return d


def _view(uid="1", viewer=None):
    return json.dumps(app.build_profile_components(uid, "Hunter", "main", viewer_id=viewer), ensure_ascii=False)


def _modal(uid):
    async def make():                       # discord.ui views need a running loop
        return app.ProfileBioModal(uid)
    return run(make())


def _walk(comps):
    for c in comps:
        yield c
        yield from _walk(c.get("components", []) or [])


def _select(comps):
    return next((c for c in _walk(comps) if c.get("custom_id", "").startswith("profile:sections:")), None)


# ── defaults ────────────────────────────────────────────────────────────────

def test_editor_is_off_by_default_even_for_admins_and_nothing_changes():
    d = _fresh("1")
    assert app.profile_editor_on("1") is False and "profile_editor" not in d
    comps = app.build_profile_components("1", "Hunter", "main")
    assert _select(comps) is None
    blob = json.dumps(comps, ensure_ascii=False)
    assert "123,456" in blob and "Bare Hands" in blob and "Profile Editor" in blob       # all sections + the settings hint
    app.BOT_ADMIN_ID.append("1")
    try:
        assert app.profile_editor_on("1") is False                                        # admins get no special case
        assert _select(app.build_profile_components("1", "Hunter", "main")) is None
    finally:
        app.BOT_ADMIN_ID.remove("1")


def test_settings_page_has_the_toggle_and_it_flips():
    _fresh("2")
    assert "profile_editor" in json.dumps(app.build_settings_components("2"))
    seen = []

    async def upd(interaction, comps):
        seen.append(comps)
    with tr.Harness():
        app.smart_update_v2 = upd
        run(app._dispatch_component(tr.FakeInteraction("2", "settings:toggle:profile_editor:2")))
    assert app.profile_editor_on("2") is True and seen
    assert _select(app.build_profile_components("2", "Hunter", "main")) is not None


# ── editor controls ─────────────────────────────────────────────────────────

def test_editor_shows_multiselect_and_edit_bio_only_on_your_own_profile():
    _fresh("3", profile_editor=True)
    comps = app.build_profile_components("3", "Hunter", "main")
    sel = _select(comps)
    assert sel and sel["min_values"] == 0 and sel["max_values"] == len(app.PROFILE_SECTIONS)
    assert all(o["default"] for o in sel["options"]) and len(sel["options"]) == len(app.PROFILE_SECTIONS) <= 25
    assert all(len(o["description"]) <= 100 and len(o["label"]) <= 100 for o in sel["options"])
    assert any(c.get("custom_id") == "profile:bio:3" for c in _walk(comps))
    assert "Turn on **Profile Editor**" not in json.dumps(comps)                          # no hint once it's on
    tr._mk_user("4")
    other = app.build_profile_components("3", "Hunter", "main", viewer_id="4")           # someone else looking
    assert _select(other) is None and not any(c.get("custom_id") == "profile:bio:3" for c in _walk(other))


# ── choosing what shows ─────────────────────────────────────────────────────

def test_choosing_sections_hides_the_rest_for_everyone():
    d = _fresh("5", profile_editor=True)
    d["bio"] = "I hunt dragons"
    seen = []

    async def upd(interaction, comps):
        seen.append(json.dumps(comps, ensure_ascii=False))
    with tr.Harness():
        app.smart_update_v2 = upd
        run(app._dispatch_component(tr.FakeInteraction("5", "profile:sections:5", values=["bio", "tribe", "bogus"])))
    assert d["profile_show"] == ["bio", "tribe"]                                         # unknown keys dropped, canonical order
    page = seen[0]
    assert "I hunt dragons" in page and "123,456" not in page and "Bare Hands" not in page and "Luck:" not in page
    assert "Lv." in page                                                                 # name / level always show
    # a stranger sees the same trimmed profile
    tr._mk_user("6")
    other = _view("5", viewer="6")
    assert "I hunt dragons" in other and "123,456" not in other and "Bare Hands" not in other
    # the picker reflects the choice
    sel = _select(app.build_profile_components("5", "Hunter", "main"))
    assert {o["value"] for o in sel["options"] if o["default"]} == {"bio", "tribe"}


def test_unselecting_everything_still_renders_and_unselecting_bio_hides_it():
    d = _fresh("7", profile_editor=True)
    d["bio"] = "secret plan"
    d["profile_show"] = []
    page = _view("7")
    assert "secret plan" not in page and "Lv." in page and "123,456" not in page
    d["profile_show"] = ["wealth", "gear"]
    page = _view("7")
    assert "123,456" in page and "Bare Hands" in page and "secret plan" not in page


def test_only_the_owner_with_the_editor_on_can_use_the_controls():
    d = _fresh("8")                                                                      # editor OFF
    tr._mk_user("9", profile_editor=True)
    errs = []

    async def eph(interaction, text, color=0):
        errs.append(text)
    for clicker, cid in (("8", "profile:sections:8"), ("8", "profile:bio:8"), ("9", "profile:sections:8:9")):
        with tr.Harness():
            app.send_ephemeral_v2 = eph
            run(app._dispatch_component(tr.FakeInteraction(clicker, cid, values=["bio"])))
    assert "profile_show" not in d and d.get("bio") is None
    assert len(errs) == 3


def test_bio_button_opens_the_modal_unacknowledged_and_prefills():
    _fresh("10", profile_editor=True)["bio"] = "hello"
    assert app._cid_opens_modal(["profile", "bio", "10"], []) is True
    assert app._cid_opens_modal(["profile", "main", "10"], []) is False
    opened = []
    it = tr.FakeInteraction("10", "profile:bio:10")

    async def send_modal(m):
        opened.append(m)
        it.response.done = True
    it.response.send_modal = send_modal
    with tr.Harness():
        run(app._dispatch_component(it))
    assert opened and isinstance(opened[0], app.ProfileBioModal)
    assert opened[0].bio_input.default == "hello"
    _fresh("11", profile_editor=True)
    assert _modal("11").bio_input.default is None                           # one player's bio never leaks into another's form


def test_modal_submit_saves_a_cleaned_bio_and_blank_clears_it():
    d = _fresh("12", profile_editor=True)
    shown = []

    async def upd(interaction, comps):
        shown.append(json.dumps(comps, ensure_ascii=False))

    async def gate(interaction, uid=None):
        return True
    saved = (app.smart_update_v2, app._modal_gate)
    app.smart_update_v2, app._modal_gate = upd, gate
    try:
        m = _modal("12")
        m.bio_input._value = "hi @everyone https://evil.example join discord.gg/abc"
        it = tr.FakeInteraction("12", "x")
        it.user.display_name = "Hunter"
        run(m.on_submit(it))
        assert "everyone" in d["bio"] and "@everyone" not in d["bio"] and "evil.example" not in d["bio"]
        assert "discord.gg" not in d["bio"] and d["bio"].count("[link removed]") == 2
        assert shown and "hi @" in shown[-1]
        m2 = _modal("12")
        m2.bio_input._value = "   "
        run(m2.on_submit(it))
        assert d["bio"] == ""
    finally:
        app.smart_update_v2, app._modal_gate = saved


def test_clean_bio_rules():
    c = app.clean_bio
    assert c("") == "" and c(None) == ""
    assert "@everyone" not in c("@everyone @here") and "<@123>" not in c("<@123> hi")
    assert c("a\n\n\nb\nc\nd\ne") == "a\nb\nc"                                           # 3 lines max, blanks dropped
    assert len(c("x" * 500)) <= app.PROFILE_BIO_MAX
    assert "```" not in c("```code```") and "](" not in c("[click](javascript:alert)")
    assert c("www.spam.com and http://x.y/z") == "[link removed] and [link removed]"
    assert "‮" not in c("evil‮text") and "\x00" not in c("a\x00b")
    assert c("héllo 🐺 wörld") == "héllo 🐺 wörld"                                       # normal text is untouched


def test_bio_is_a_blockquote_so_it_cannot_fake_panel_headings():
    d = _fresh("13")
    d["bio"] = "# BIG\nline two"
    page = _view("13")
    assert "> # BIG" in page and "> line two" in page


# ── staff ───────────────────────────────────────────────────────────────────

def test_inspect_bio_reads_and_clears():
    d = _fresh("14")
    d["bio"] = "rude words"
    cmd = next(c for c in app.inspect_group.commands if c.name == "bio")
    assert cmd.checks
    out = []

    async def eph(interaction, text, color=0):
        out.append(text)

    async def opened(interaction, user):
        return "14"
    saved = (app.send_ephemeral_v2, app._insp_open)
    app.send_ephemeral_v2, app._insp_open = eph, opened
    try:
        run(cmd.callback(tr.FakeInteraction("99", "x"), "14", False))
        assert "rude words" in out[-1] and d["bio"] == "rude words"
        run(cmd.callback(tr.FakeInteraction("99", "x"), "14", True))
        assert d["bio"] == "" and "Removed" in out[-1] and "rude words" in out[-1]
    finally:
        app.send_ephemeral_v2, app._insp_open = saved


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
