"""
/giveaway — giveaways, loot drops, number guesses and hunt races.

Runs without pytest:  python tests/test_giveaway.py
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
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_giveaway_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_races as tr   # noqa: E402  (its Harness / FakeInteraction / helpers)
import app                # noqa: E402
import backend            # noqa: E402

run = tr.run
POSTS, EDITS = [], []


async def _fake_post(channel_id, components, mentions=None, reply_to=None):
    POSTS.append({"channel": channel_id, "components": components, "mentions": mentions})
    return {"id": str(1000 + len(POSTS))}


async def _fake_edit(g):
    EDITS.append(g["id"])
    return True


app._gw_post, app._gw_edit_card = _fake_post, _fake_edit


def _reset():
    tr._reset()
    app._giveaways.clear()
    app._gw_locks.clear()
    app._gw_dirty.clear()
    POSTS.clear()
    EDITS.clear()


def _users(*ids, **over):
    for u in ids:
        tr._mk_user(u, **over)


def _mk(kind="giveaway", prize=None, winners=1, **extra):
    g = {"id": f"t{len(app._giveaways):05d}", "kind": kind, "guild_id": 1, "channel_id": 2, "message_id": 3,
         "host": "H", "created_ts": int(time.time()), "ends_ts": time.time() + 600, "status": "active",
         "prize": prize or {"type": "money", "amount": 1000, "name": ""}, "winners_n": winners,
         "min_level": 1, "entrants": {}, "winners": [], "paid": []}
    g.update(extra)
    app._giveaways[g["id"]] = g
    return g


# ── parsing ───────────────────────────────────────────────────

def test_duration_parsing():
    p = app._gw_parse_duration
    assert p("30m") == 1800 and p("2h") == 7200 and p("1d") == 86400 and p("1h30m") == 5400 and p("90s") == 90
    assert p(" 5 m ") == 300
    for bad in ("", "abc", "10", "m5", "1x", "-5m", None):
        assert p(bad) is None, bad


def test_prize_parsing():
    P = app._gw_parse_prize
    assert P("money", "50k", None)[0] == {"type": "money", "amount": 50_000, "name": ""}
    assert P("gems", "25", None)[0]["amount"] == 25
    assert P("crate", "1", "epic")[0]["name"] == "Epic Crate"
    assert P("crate", "2", "Epic Crate")[0]["amount"] == 2
    assert P("custom", "", "Discord Nitro")[0] == {"type": "custom", "amount": 1, "name": "Discord Nitro"}
    item = next(iter(app.ITEMS))
    assert P("item", "3", item)[0] == {"type": "item", "amount": 3, "name": item}
    for args in (("money", "0", None), ("money", "abc", None), ("money", str(10 ** 13), None),
                 ("gems", "999999", None), ("crate", "1", "nope"), ("crate", "99", "epic"),
                 ("item", "1", "zzzz-not-an-item"), ("custom", "", ""), ("bogus", "1", None)):
        prize, why = P(*args)
        assert prize is None and why, args


# ── giveaway ──────────────────────────────────────────────────

def test_enter_toggles_and_respects_min_level():
    _reset()
    _users("A", "B")
    app.data["B"]["level"] = 3
    g = _mk(min_level=10)
    assert run(app.gw_enter(g["id"], "B")) == (False, "You need to be **Level 10+** to take part.")
    app.data["B"]["level"] = 10
    ok, _ = run(app.gw_enter(g["id"], "B"))
    assert ok and "B" in g["entrants"] and g["id"] in app._gw_dirty
    ok, msg = run(app.gw_enter(g["id"], "B"))
    assert ok and "B" not in g["entrants"] and "left" in msg


def test_finish_pays_each_winner_exactly_once_even_when_raced():
    _reset()
    _users("A", "B", "C", "D")
    g = _mk(winners=2, prize={"type": "money", "amount": 5000, "name": ""})
    for u in "ABCD":
        run(app.gw_enter(g["id"], u))
    before = {u: app.data[u]["money"] for u in "ABCD"}

    async def go():
        await asyncio.gather(*[app.gw_finish(g["id"]) for _ in range(5)])
    run(go())
    assert g["status"] == "ended" and len(g["winners"]) == 2 and set(g["paid"]) == set(g["winners"])
    for u in "ABCD":
        gain = app.data[u]["money"] - before[u]
        assert gain == (5000 if u in g["winners"] else 0), (u, gain)
        assert app.data[u]["stats"].get("giveaways_won", 0) == (1 if u in g["winners"] else 0)
    assert len(POSTS) == 1 and set(POSTS[0]["mentions"]) == set(g["winners"])      # announced once, pinging winners
    assert EDITS.count(g["id"]) == 1


def test_all_prize_types_are_granted():
    _reset()
    _users("A")
    item = next(iter(app.ITEMS))
    for prize in ({"type": "gems", "amount": 40, "name": ""},
                  {"type": "crate", "amount": 2, "name": "Epic Crate"},
                  {"type": "item", "amount": 3, "name": item}):
        g = _mk(prize=prize)
        run(app.gw_enter(g["id"], "A"))
        run(app.gw_finish(g["id"]))
    d = app.data["A"]
    assert d["gems"] == 100 + 40
    assert d["crate_inv"]["Epic Crate"] == 2
    assert app.item_count("A", item) == 3


def test_custom_prize_pays_nothing_but_pings_and_names_the_host():
    _reset()
    _users("A")
    g = _mk(prize={"type": "custom", "amount": 1, "name": "Discord Nitro"})
    run(app.gw_enter(g["id"], "A"))
    money = app.data["A"]["money"]
    run(app.gw_finish(g["id"]))
    assert app.data["A"]["money"] == money and g["status"] == "ended" and g["winners"] == ["A"]
    body = json.dumps(POSTS[0]["components"], ensure_ascii=False)
    assert "Discord Nitro" in body and "<@H>" in body and "<@A>" in body


def test_banned_and_missing_entrants_never_win_and_empty_giveaway_ends_cleanly():
    _reset()
    _users("A", "B")
    app.data["B"]["ban"] = {"active": True, "expires_ts": 0}
    g = _mk(winners=3)
    run(app.gw_enter(g["id"], "A"))
    g["entrants"]["B"] = {"ts": 1}
    g["entrants"]["ghost"] = {"ts": 1}
    run(app.gw_finish(g["id"]))
    assert g["winners"] == ["A"]
    empty = _mk()
    run(app.gw_finish(empty["id"]))
    assert empty["status"] == "ended" and empty["winners"] == []
    assert "Nobody won" in json.dumps(POSTS[-1]["components"], ensure_ascii=False)


def test_cannot_act_after_the_end_and_late_entries_are_refused():
    _reset()
    _users("A")
    g = _mk(ends_ts=time.time() - 1)
    ok, msg = run(app.gw_enter(g["id"], "A"))
    assert not ok and "ended" in msg
    assert run(app.gw_enter("nope", "A"))[0] is False


def test_crash_mid_payout_resumes_without_double_paying():
    _reset()
    _users("A", "B")
    g = _mk(winners=2)
    for u in "AB":
        run(app.gw_enter(g["id"], u))
    real = app._gw_grant
    calls = []

    async def flaky(uid, prize, gid=""):
        calls.append(uid)
        if uid == "B" and calls.count("B") == 1:
            raise RuntimeError("db hiccup")
        return await real(uid, prize, gid)
    app._gw_grant = flaky
    try:
        run(app.gw_finish(g["id"]))
        assert g["status"] == "ending" and len(g["paid"]) == 1          # one paid, one pending
        run(app.gw_finish(g["id"]))                                      # the ticker retries
    finally:
        app._gw_grant = real
    assert g["status"] == "ended" and sorted(g["paid"]) == ["A", "B"]
    assert calls.count("A") == 1                                         # A was not paid twice
    assert app.data["A"]["money"] == 150 + 1000 and app.data["B"]["money"] == 150 + 1000


def test_reroll_excludes_previous_winners_and_pays_the_new_ones():
    _reset()
    _users("A", "B", "C")
    g = _mk(winners=1)
    for u in "ABC":
        run(app.gw_enter(g["id"], u))
    run(app.gw_finish(g["id"]))
    first = g["winners"][0]
    ok, msg = run(app.gw_reroll(g["id"], 2))
    assert ok and len(g["winners"]) == 3 and len(set(g["winners"])) == 3 and g["winners"][0] == first
    assert sum(app.data[u]["money"] - 150 for u in "ABC") == 3000
    assert run(app.gw_reroll(g["id"], 1))[0] is False                    # nobody left
    assert run(app.gw_reroll(_mk("drop")["id"], 1))[0] is False          # wrong status/kind


def test_cancel_pays_nobody():
    _reset()
    _users("A")
    g = _mk()
    run(app.gw_enter(g["id"], "A"))
    assert run(app.gw_cancel(g["id"]))[0]
    assert g["status"] == "cancelled" and app.data["A"]["money"] == 150
    assert run(app.gw_cancel(g["id"]))[0] is False
    run(app.gw_finish(g["id"]))
    assert app.data["A"]["money"] == 150


# ── loot drop ─────────────────────────────────────────────────

def test_loot_drop_exactly_n_grabs_win_under_a_stampede():
    _reset()
    ids = [f"u{i}" for i in range(12)]
    _users(*ids)
    g = _mk("drop", winners=3, prize={"type": "money", "amount": 777, "name": ""}, ends_ts=time.time() + 600)

    async def go():
        return await asyncio.gather(*[app.gw_grab(g["id"], u) for u in ids])
    res = run(go())
    assert sum(1 for ok, _m, _f in res if ok) == 3
    assert sum(1 for _ok, _m, filled in res if filled) == 1
    assert len(g["winners"]) == 3 and sorted(g["paid"]) == sorted(g["winners"])
    assert sum(app.data[u]["money"] - 150 for u in ids) == 3 * 777
    run(app.gw_finish(g["id"]))
    run(app.gw_finish(g["id"]))
    assert g["status"] == "ended" and len(POSTS) == 1
    assert run(app.gw_grab(g["id"], "u0"))[0] is False                   # all gone


def test_loot_drop_nobody_grabs_it_expires():
    _reset()
    g = _mk("drop", ends_ts=time.time() - 1)
    run(app.gw_finish(g["id"]))
    assert g["status"] == "ended" and g["winners"] == []
    assert "Nobody grabbed it" in json.dumps(app._gw_card(g), ensure_ascii=False)


def test_cannot_grab_twice():
    _reset()
    _users("A")
    g = _mk("drop", winners=2)
    assert run(app.gw_grab(g["id"], "A"))[0] is True
    ok, msg, _ = run(app.gw_grab(g["id"], "A"))
    assert not ok and "already" in msg and app.data["A"]["money"] == 150 + 1000


# ── number guess ──────────────────────────────────────────────

def test_guess_closest_wins_ties_go_to_the_earlier_guess_and_range_is_enforced():
    _reset()
    _users("A", "B", "C", "D")
    g = _mk("guess", winners=2, range=[1, 100], secret=50)
    assert run(app.gw_guess(g["id"], "A", 0))[0] is False and run(app.gw_guess(g["id"], "A", 101))[0] is False
    assert run(app.gw_guess(g["id"], "A", 45))[0]       # off by 5, first
    assert run(app.gw_guess(g["id"], "B", 55))[0]       # off by 5, later  -> loses the tie
    assert run(app.gw_guess(g["id"], "C", 52))[0]       # off by 2
    assert run(app.gw_guess(g["id"], "D", 10))[0]
    ok, msg = run(app.gw_guess(g["id"], "D", 49))       # changing a guess is allowed -> off by 1
    assert ok and "updated" in msg
    run(app.gw_finish(g["id"]))
    assert g["winners"] == ["D", "C"], g["winners"]
    card = json.dumps(app._gw_card(g), ensure_ascii=False)
    assert "The number was **50**" in card and "guessed 49" in card


def test_guess_secret_is_random_in_range_and_hidden_while_running():
    _reset()
    g = _mk("guess", range=[1, 100], secret=37)
    assert "37" not in json.dumps(app._gw_card(g), ensure_ascii=False).replace("`", "")
    seen = {random.randint(1, 100) for _ in range(50)}
    assert len(seen) > 5


# ── hunt race ─────────────────────────────────────────────────

def _set_caught(u, total):
    """Pretend the player HUNTED up to `total` animals (bumps the race counter as run_hunt does)."""
    d = app.data[u]
    d.setdefault("stats", {})["race_catches"] = d["stats"].get("race_catches", 0) + (total - d.get("total_caught", 0))
    d["total_caught"] = total


def test_idle_camp_collections_do_not_count_in_a_hunt_race():
    _reset()
    _users("A", "B")
    g = _mk("race", winners=1)
    for u in "AB":
        run(app.gw_join(g["id"], u))
    app.data["A"]["total_caught"] += 195                 # a full camp haul collected right after joining
    assert app._gw_score(g, "A") == 0
    _set_caught("B", app.data["B"]["total_caught"] + 7)  # seven real hunted catches
    assert app._gw_score(g, "B") == 7
    run(app.gw_finish(g["id"]))
    assert g["winners"] == ["B"]


def test_payout_marker_stops_a_double_payment_after_a_crash():
    _reset()
    _users("A")
    prize = {"type": "money", "amount": 1000, "name": ""}
    run(app._gw_grant("A", prize, "gwX"))
    run(app._gw_grant("A", prize, "gwX"))                # retried after a crash that lost the 'paid' record
    assert app.data["A"]["money"] == 150 + 1000
    run(app._gw_grant("A", prize, "gwY"))                # a different giveaway still pays
    assert app.data["A"]["money"] == 150 + 2000


def test_race_counts_only_catches_after_joining_and_needs_at_least_one():
    _reset()
    _users("A", "B", "C")
    for u in "ABC":
        app.data[u]["total_caught"] = 100
    g = _mk("race", winners=1)
    for u in "ABC":
        assert run(app.gw_join(g["id"], u))[0]
    assert g["entrants"]["A"]["base"] == 100
    _set_caught("A", 130)      # +30
    _set_caught("B", 150)      # +50 -> winner
    run(app.gw_finish(g["id"]))
    assert g["winners"] == ["B"] and g["scores"] == {"B": 50, "A": 30}
    assert "50 catches" in json.dumps(app._gw_card(g), ensure_ascii=False)
    nobody = _mk("race")
    run(app.gw_join(nobody["id"], "C"))
    run(app.gw_finish(nobody["id"]))
    assert nobody["winners"] == [] and nobody["status"] == "ended"


def test_race_joining_twice_does_not_reset_your_baseline():
    _reset()
    _users("A")
    app.data["A"]["total_caught"] = 10
    g = _mk("race")
    run(app.gw_join(g["id"], "A"))
    _set_caught("A", 25)
    ok, msg = run(app.gw_join(g["id"], "A"))
    assert ok and "15" in msg and g["entrants"]["A"]["base"] == 10


# ── persistence, cards, outages ───────────────────────────────

def test_save_load_roundtrip_and_resume_after_restart():
    _reset()
    _users("A")
    g = _mk(winners=1)
    run(app.gw_enter(g["id"], "A"))
    run(backend.giveaway_save(g))
    loaded = run(backend.giveaways_load())
    assert loaded[g["id"]]["entrants"]["A"] and loaded[g["id"]]["prize"] == g["prize"]
    app._giveaways.clear()
    app._giveaways.update(loaded)
    app._giveaways[g["id"]]["ends_ts"] = time.time() - 1
    run(app.giveaway_task.coro())                # the ticker ends it
    assert app._giveaways[g["id"]]["status"] == "ended" and app._giveaways[g["id"]]["winners"] == ["A"]
    run(backend.giveaway_delete(g["id"]))
    assert g["id"] not in run(backend.giveaways_load())


def test_ticker_edits_dirty_cards_and_prunes_old_ones():
    _reset()
    g = _mk()
    app._gw_dirty.add(g["id"])
    run(app.giveaway_task.coro())
    assert EDITS == [g["id"]] and not app._gw_dirty
    old = _mk()
    old.update(status="ended", ended_ts=time.time() - (app.GW_KEEP_ENDED_DAYS + 1) * 86400)
    run(app.giveaway_task.coro())
    assert old["id"] not in app._giveaways


def test_outage_pause_pushes_running_giveaways_back():
    _reset()
    g = _mk(ends_ts=time.time() + 100)
    done = _mk(ends_ts=time.time() - 50)
    done_before = done["ends_ts"]
    since = time.time() - 30
    before = g["ends_ts"]
    run(app.pause_running_timers(since, 600))
    assert abs(g["ends_ts"] - (before + 600)) < 1
    assert done["ends_ts"] == done_before                                  # already over -> untouched


def test_every_card_renders_in_every_state():
    _reset()
    _users("A", "B")
    for kind, extra in (("giveaway", {}), ("drop", {}), ("guess", {"range": [1, 50], "secret": 7}), ("race", {})):
        for status, winners in (("active", []), ("ended", ["A"]), ("ended", []), ("cancelled", [])):
            g = _mk(kind, status=status, winners=winners, winners_n=2, min_level=5, **extra)
            g["entrants"] = {"A": {"ts": 1, "guess": 9, "base": 0}, "B": {"ts": 2, "guess": 8, "base": 0}}
            g["scores"] = {"A": 3}
            for prize in ({"type": "money", "amount": 5, "name": ""}, {"type": "crate", "amount": 1, "name": "Epic Crate"},
                          {"type": "custom", "amount": 1, "name": "Nitro"}):
                g["prize"] = prize
                comps = app._gw_card(g)
                blob = json.dumps(comps, ensure_ascii=False)
                assert f"`{g['id']}`" in blob
                for c in tr_walk(comps):
                    if c.get("custom_id"):
                        assert len(c["custom_id"]) <= 100 and c["custom_id"].startswith("gw:")


def tr_walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from tr_walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from tr_walk(v)


# ── the real click path ───────────────────────────────────────

def test_buttons_go_through_the_dispatcher():
    _reset()
    _users("10", "11")
    g = _mk()
    gid = g["id"]
    with tr.Harness() as h:
        run(tr._click("10", f"gw:enter:{gid}"))
        run(tr._click("11", f"gw:enter:{gid}"))
        assert set(g["entrants"]) == {"10", "11"} and len(h.ephemerals) == 2
        run(tr._click("10", f"gw:enter:{gid}"))                      # toggle off
        assert set(g["entrants"]) == {"11"}
        run(tr._click("10", "gw:enter:deadbe"))                      # unknown id -> polite refusal
        assert "doesn't exist" in h.ephemerals[-1]
        r = _mk("race")
        run(tr._click("10", f"gw:join:{r['id']}"))
        run(tr._click("10", f"gw:board:{r['id']}"))
        assert "Hunt Race standings" in h.ephemerals[-1]
        d = _mk("drop", winners=1)
        run(tr._click("10", f"gw:grab:{d['id']}"))
        run(tr._click("11", f"gw:grab:{d['id']}"))
        assert d["winners"] == ["10"] and "Too slow" in h.ephemerals[-1]
        gs = _mk("guess", range=[1, 10], secret=4)
        from types import SimpleNamespace

        it = tr.FakeInteraction("11", f"gw:guess:{gs['id']}")
        run(app._dispatch_component(it))
        assert it.response.is_done()                                  # a modal was sent, not deferred
    assert app._cid_opens_modal(["gw", "enter", "abc"], [])


def test_command_group_shape_and_admin_gate():
    cmds = {c.name for c in app.giveaway_group.commands}
    assert cmds == {"start", "drop", "guess", "race", "end", "cancel", "reroll", "list"}
    for c in app.giveaway_group.commands:
        assert (c.name == "list") != bool(c.checks), c.name       # every management command is admin-gated


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
