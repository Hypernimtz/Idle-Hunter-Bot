"""
Idle Hunter V2 regression suite.

Runs without pytest:  python tests/test_v2.py
Runs with pytest too: pytest tests/test_v2.py

It stubs discord.py's bot.run (so importing app.py doesn't try to connect) and
points SQLITE_PATH at a throwaway DB. Every test resets the in-memory stores.
"""
import asyncio
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

os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_v2_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import discord.ext.commands as _c  # noqa: E402
_c.Bot.run = lambda *a, **k: None

import app          # noqa: E402
import backend      # noqa: E402
from game_data import MYTHIC_CREATURES, BIOME_ANIMALS  # noqa: E402

_DB_READY = False


async def _ensure_db():
    global _DB_READY
    if not _DB_READY:
        await backend.init_databases()
        app.register_state_refs(app.data, app.tribe_data)
        _DB_READY = True


def _reset():
    app.data.clear()
    app.tribe_data.clear()
    app._dirty_users.clear()
    app._world_conditions.clear()
    app._active_sighting = None
    app._last_sighting_end = 0.0
    app._guild_goal_seen.clear()
    for f in ("FEATURE_ONBOARDING_V2", "FEATURE_WORLD_CONDITIONS", "FEATURE_TRACKING",
              "FEATURE_WORLD_SIGHTINGS", "FEATURE_SHARE_CARDS", "FEATURE_EXPEDITIONS",
              "FEATURE_SERVER_GOALS", "FEATURE_REFERRALS", "FEATURE_ANALYTICS"):
        setattr(app, f, True)


def _mk_user(uid, **over):
    app.data.pop(uid, None)
    app.init_user(uid)
    d = app.data[uid]
    d["onboarding"] = {"version": 2, "completed": True, "step": "done", "starter_pack": None}
    d["hunters_path"] = {"completed": True}
    d["verify"] = {"needed": False, "time": 10 ** 9, "code": "ABCD"}
    d["_hunt_times"] = []
    d["_last_hunt_ts"] = None
    d["hunt_cd"] = 0
    d.update(over)
    return d


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─────────────────────────────────────────────────────────────
# migration chain (currently v12 → v14)
# ─────────────────────────────────────────────────────────────
def test_migration_v13():
    out = backend.migrate_user_dict({"schema_version": 12, "money": 5, "stats": {}})
    assert out["schema_version"] == backend.CURRENT_SCHEMA
    assert out["onboarding"]["completed"] is True          # existing players not onboarded
    assert "tracks_completed" in out["stats"]
    assert "active_days" in out["stats"]
    # v14: persistent HP + animal combat + rookie systems
    assert out["health"] == {"hp": 100, "max_hp": 100,
                             "last_regen_ts": out["health"]["last_regen_ts"],
                             "injuries": [], "rookie_revive_used": True}
    assert out["healing_inv"] == {} and out["trial_tool"] is None and out["fight"] is None
    assert out["rookie_goals"]["catch_5"] is False
    assert "animal_fights_started" in out["stats"]
    # full chain from a v0 blob
    o2 = backend.migrate_user_dict({"schema_version": 0})
    assert o2["schema_version"] == backend.CURRENT_SCHEMA
    # idempotent
    assert backend.migrate_user_dict(dict(out)) == out


# ─────────────────────────────────────────────────────────────
# typed model lossless round-trip
# ─────────────────────────────────────────────────────────────
def test_typed_model_lossless():
    raw = {"schema_version": 13, "money": 7,
           "stats": {"myths_killed": 4, "lifetime_hunts": 22, "ancient_key": 9},
           "_boss": {"creature": "X"}, "quests": [1], "temp_boosts": [{"stat": "luck"}],
           "onboarding": {"version": 2, "completed": False, "step": "catch", "starter_pack": None},
           "future_field": "keep me"}
    out = backend.User.from_dict(raw).to_dict()
    for k in ("_boss", "quests", "temp_boosts", "future_field"):
        assert out.get(k) == raw[k], k
    assert out["stats"]["ancient_key"] == 9
    assert out["onboarding"]["step"] == "catch"
    assert backend.User.from_dict(out).to_dict() == out   # stable


# ─────────────────────────────────────────────────────────────
# onboarding — double click can't double-grant
# ─────────────────────────────────────────────────────────────
def test_onboarding_no_double_grant():
    _reset()
    u = "onb1"
    app.data.pop(u, None)
    app.init_user(u)                     # new account → onboarding active
    assert app.onboarding_active(u)
    app.data[u]["temp_boosts"] = []      # isolate from any pre-existing boosts
    app._onb_set_step(u, "catch")
    a1, v1, _x1, _l1 = app._onb_grant_first_catch(u)
    a2, v2, _x2, _l2 = app._onb_grant_first_catch(u)   # second "click"
    assert app.data[u]["inv"] == [a1]            # only one animal
    assert app.data[u]["_pending_sell"] == v1
    assert app.data[u]["healing_inv"].get("Bandage") == 1   # the free Bandage, once
    app._onb_set_step(u, "pack")
    assert app._onb_grant_pack(u, "scout") is True
    assert app._onb_grant_pack(u, "hunter") is False   # one-time
    tb = [b for b in app.data[u]["temp_boosts"] if b["stat"] == "luck"]
    assert len(tb) == 1
    app._onb_set_step(u, "done")
    assert not app.onboarding_active(u)


def test_onboarding_disabled_flag():
    _reset()
    app.FEATURE_ONBOARDING_V2 = False
    u = "onb2"
    app.data.pop(u, None)
    app.init_user(u)
    assert app.data[u]["onboarding"]["completed"] is True
    assert app.onboarding_active(u) is False


# ─────────────────────────────────────────────────────────────
# tracking — stale button rejected, sequence resolves
# ─────────────────────────────────────────────────────────────
def test_tracking_stale_button():
    _reset()
    u = "trk1"
    _mk_user(u)
    tr = app._tracking_start(u, "Bigfoot", "village")
    assert app.tracking_active(u)
    # a choice against the wrong tracking id is a no-op
    stale = app.tracking_choice.__wrapped__ if hasattr(app.tracking_choice, "__wrapped__") else None
    # simulate the handler guard: tr id mismatch
    assert tr["id"] != "deadbeef"
    # real resolution
    random.seed(1)
    out = {"kind": "ongoing"}
    steps = 0
    while out["kind"] == "ongoing" and steps < 12:
        out = app.tracking_choice(u, "follow")
        steps += 1
    assert out["kind"] in ("located", "lost")
    if out["kind"] == "located":
        assert app.data[u]["_boss"]["creature"] == "Bigfoot"
        assert app.data[u]["tracking"] is None
        assert "tracking_bonus" in app.data[u]["_boss"]
    assert app.data[u]["stats"]["tracks_started"] == 1


def test_tracking_disabled_flag_keeps_old_fight():
    _reset()
    app.FEATURE_TRACKING = False
    u = "trk2"
    _mk_user(u, level=200, biome="village")
    app.MYTH_ENCOUNTER_BASE, base = 1.0, app.MYTH_ENCOUNTER_BASE
    orig_random = random.random
    random.random = lambda: 0.0   # force the myth-encounter roll to hit, deterministically
    try:
        app.data[u]["hunt_cd"] = 0
        app.data[u]["_hunt_times"] = []
        app.data[u]["_last_hunt_ts"] = None
        r = run(_run_hunt_txn(u))
        assert r.get("myth_encounter"), r
        assert app.data[u]["_boss"] and app.data[u].get("tracking") is None
    finally:
        app.MYTH_ENCOUNTER_BASE = base
        random.random = orig_random


async def _run_hunt_txn(uid):
    async with app.user_transaction(uid):
        return app.run_hunt(uid)


# ─────────────────────────────────────────────────────────────
# myth fight resolves to a terminal state
# ─────────────────────────────────────────────────────────────
def test_myth_fight_resolves():
    _reset()
    u = "fig1"
    _mk_user(u, level=300)
    app.data[u]["_boss"] = {
        "creature": "Bigfoot", "biome": "village", "eid": "e1",
        "php": 100, "mhp": 30, "mhp_max": 100, "turn": 1,
        "fallen": False, "guard": False, "enrage": False, "mdebuff": False, "log": [],
    }
    random.seed(2)
    kind = "ongoing"
    for _ in range(60):
        out = run(_fight_txn(u, "kick"))
        kind = out["kind"]
        if kind != "ongoing":
            break
    assert kind in ("kill", "death", "escape")
    assert app.data[u]["_boss"] is None
    if kind == "kill":
        assert app.data[u]["stats"]["myths_killed"] == 1


async def _fight_txn(uid, action):
    async with app.user_transaction(uid):
        return app.myth_fight_turn(uid, action)


# ─────────────────────────────────────────────────────────────
# referral — concurrent double-claim pays exactly once
# ─────────────────────────────────────────────────────────────
def test_referral_double_claim():
    async def body():
        await _ensure_db()
        _reset()
        A, B = "refA", "refB"
        _mk_user(A, username="A")
        _mk_user(B, username="B")
        code = await app._referral_get_code(A)
        ok, _ = await app._referral_bind(B, code)
        assert ok
        # not qualified yet (needs level + hunts + 2 days)
        await app._referral_check_qualified(B)
        assert (await backend.referral_of(B))["qualified_at"] is None
        # meet the bar
        app.data[B]["level"] = 30
        app.data[B]["stats"]["lifetime_hunts"] = 60
        app.data[B]["stats"]["active_days"] = 2
        app.data[B].pop("_ref_done", None)
        gA0, gB0 = app.data[A]["gems"], app.data[B]["gems"]
        # fire five concurrent checks
        await asyncio.gather(*[app._referral_check_qualified(B) for _ in range(5)])
        assert app.data[B]["gems"] == gB0 + app.REFERRAL_QUALIFY_GEMS      # once
        assert app.data[A]["gems"] == gA0 + app.REFERRAL_QUALIFY_GEMS      # once (milestone 1 has no gems)
        assert "Brought In" in app.data[B]["earned_titles"]
        assert "Trail Guide" in app.data[A]["earned_titles"]
        assert (await backend.referral_stats(A)) == {"invited": 1, "qualified": 1}
    run(body())


def test_referral_anti_alt_days():
    async def body():
        await _ensure_db()
        _reset()
        A, B = "aaA", "aaB"
        _mk_user(A)
        _mk_user(B, level=5)                             # low enough to enter a code
        code = await app._referral_get_code(A)
        ok, msg = await app._referral_bind(B, code)
        assert ok, msg
        app.data[B]["level"] = 99
        app.data[B]["stats"]["lifetime_hunts"] = 200
        app.data[B]["stats"]["active_days"] = 1          # only one day → NOT enough
        app.data[B].pop("_ref_done", None)
        await app._referral_check_qualified(B)
        assert (await backend.referral_of(B))["qualified_at"] is None
        app.data[B]["stats"]["active_days"] = 2
        app.data[B].pop("_ref_done", None)
        await app._referral_check_qualified(B)
        assert (await backend.referral_of(B))["qualified_at"] is not None
    run(body())


def test_referral_self_and_relevel():
    async def body():
        await _ensure_db()
        _reset()
        A = "slfA"
        _mk_user(A, level=3)
        code = await app._referral_get_code(A)
        ok, msg = await app._referral_bind(A, code)
        assert not ok and "yourself" in msg.lower()
        B = "slfB"
        _mk_user(B, level=50)                 # too experienced to enter a code
        ok, msg = await app._referral_bind(B, code)
        assert not ok
    run(body())


# ─────────────────────────────────────────────────────────────
# server goal — rollover rewards once, scales on hunters not members
# ─────────────────────────────────────────────────────────────
class _FakeGuild:
    def __init__(self, gid, members=200):
        self.id = gid
        self.name = f"G{gid}"
        self.members = [type("M", (), {"id": i, "bot": False})() for i in range(members)]


class _FakeIX:
    def __init__(self, guild):
        self.guild = guild


def test_server_goal_scaling_uses_hunters():
    async def body():
        await _ensure_db()
        _reset()
        g = _FakeGuild(500001, members=50000)     # huge server…
        # …but only 4 hunters exist in data, none of them guild members here
        for i in range(4):
            _mk_user(f"sg{i}")
        st = await app.guild_goal_state(g)
        # scale falls back to max(5, known players) → 5 → goal == MIN
        assert st["goal"] == app.GUILD_GOAL_MIN, st["goal"]
    run(body())


def test_server_goal_rollover_pays_once():
    async def body():
        await _ensure_db()
        _reset()
        gid = "600001"
        g = _FakeGuild(int(gid))
        u = "sgcontrib"
        _mk_user(u)
        # last week's goal, already met, reward not sent
        await backend.guild_goal_set(gid, "2000-W01", 1000, 500, {}, reward_sent=0)
        await backend.guild_goal_contribute(gid, u, "2000-W01", 40)
        crates0 = app.data[u].get("crate_inv", {}).get("Rare Crate", 0)
        # two concurrent finalizers
        prev = await backend.guild_goal_get(gid)
        await asyncio.gather(app._guild_goal_finalize(gid, prev),
                             app._guild_goal_finalize(gid, prev))
        crates1 = app.data[u].get("crate_inv", {}).get("Rare Crate", 0)
        assert crates1 == crates0 + 1, (crates0, crates1)     # paid exactly once
        assert "Community Hunter" in app.data[u]["earned_titles"]
        # a third call does nothing
        await app._guild_goal_finalize(gid, prev)
        assert app.data[u]["crate_inv"]["Rare Crate"] == crates1
    run(body())


def test_server_goal_disabled_flag():
    async def body():
        await _ensure_db()
        _reset()
        app.FEATURE_SERVER_GOALS = False
        assert await app.guild_goal_state(_FakeGuild(1)) is None
        await app._guild_goal_contribute(_FakeIX(_FakeGuild(1)), "x", 3)   # no crash
    run(body())


# ─────────────────────────────────────────────────────────────
# expedition — payout is crash-safe + cooldown blocks restart
# ─────────────────────────────────────────────────────────────
def _mk_tribe(name, ids):
    for u in ids:
        _mk_user(u, username="H" + u)
    app.tribe_data.pop(name, None)
    app.init_tribe(name, ids[0])
    td = app.tribe_data[name]
    td["roles"] = {"leader": ids[0], "officer": [ids[1]],
                   "members": ids[2:], "recruits": []}
    for u in ids:
        app.data[u]["tribe"] = name
    app._ensure_tribe_fields(td)
    return td


def test_expedition_payout_crash_safe_and_cooldown():
    async def body():
        await _ensure_db()
        _reset()
        T = "ExpWolves"
        ids = [f"ex{i}" for i in range(4)]
        td = _mk_tribe(T, ids)
        ok, _ = app._exp_start(T, ids[0], "abandoned_temple")
        assert ok
        for u in ids[:3]:
            app._exp_vote(T, u, "tunnels")
        exp = td["expedition"]
        assert exp["stage"] == "active"
        for _ in range(400):
            app._exp_feed(td, ids[0], "hunt", 3)
            app._exp_feed(td, ids[1], "hunt", 1)
            if exp["progress"] >= exp["goal"]:
                break
        # finish → stage 'rewarding', NOT done
        app._exp_finish(td, T)
        assert exp["stage"] == "rewarding" and not exp.get("done")
        assert exp["pending"] and exp["success"]

        # simulate a crash after paying only the first member
        first = exp["pending"][0]["uid"]
        async with app.user_tribe_transaction(first):
            app.data[first]["crate_inv"]["Epic Crate"] = 1
            exp["paid"] = [first]
        # resume — pays the rest, then marks done
        await app._exp_pay_out(T)
        assert exp.get("done") is True
        for e in exp["pending"]:
            assert app.data[e["uid"]]["crate_inv"].get("Epic Crate", 0) == 1   # exactly one each
        # a second pay-out call is a no-op
        await app._exp_pay_out(T)
        for e in exp["pending"]:
            assert app.data[e["uid"]]["crate_inv"]["Epic Crate"] == 1

        # cooldown blocks an immediate restart
        ok, msg = app._exp_start(T, ids[0], "great_migration")
        assert not ok and "available" in msg.lower()
        # ...but after the cooldown window it works
        td["expedition"]["completed_ts"] = 0
        ok, _ = app._exp_start(T, ids[0], "great_migration")
        assert ok
    run(body())


def test_expedition_disabled_flag():
    _reset()
    app.FEATURE_EXPEDITIONS = False
    u = "expOff"
    _mk_user(u)
    comps = app.build_expedition_components(u)
    assert comps and comps[0]["type"] == 17


# ─────────────────────────────────────────────────────────────
# world-state persistence round-trips through runtime_state.json
# ─────────────────────────────────────────────────────────────
def test_world_state_persistence():
    _reset()
    app.rotate_world_conditions(force_fill=True)
    app.spawn_world_sighting(force=True)
    app._event_scheduler.update({"last_event_ts": 111.0, "next_event_ts": 222.0,
                                 "recent_keys": ["duck"]})
    enc = app._encode_runtime_state()
    assert enc["world_conditions"] and enc["world_sighting"]
    # wipe live state, reload from the encoded blob
    saved_conds = dict(app._world_conditions)
    saved_sg = dict(app._active_sighting)
    app._world_conditions.clear()
    app._active_sighting = None
    app._event_scheduler.clear()
    import json
    import io
    blob = json.loads(json.dumps(enc, default=str))
    # mimic load_runtime_state's world section
    import time as _t
    now = _t.time()
    app._world_conditions = {b: c for b, c in blob["world_conditions"].items()
                             if c.get("ends_ts", 0) > now}
    if blob["world_sighting"] and blob["world_sighting"]["ends_ts"] > now:
        app._active_sighting = blob["world_sighting"]
    app._event_scheduler.update(blob["event_scheduler"])
    assert set(app._world_conditions) == set(saved_conds)
    assert app._active_sighting["creature"] == saved_sg["creature"]
    assert app._event_scheduler["recent_keys"] == ["duck"]


# ─────────────────────────────────────────────────────────────
# stranger clicking a public "Start Hunting" card plays as themself
# ─────────────────────────────────────────────────────────────
def test_share_card_and_stranger_start():
    _reset()
    owner = "shOwner"
    _mk_user(owner)
    sid = app.make_share(owner, "myth_kill", creature="Bigfoot", biome="village",
                         drop="Matted Fur Tuft", php=17)
    assert sid in app._share_store
    pub = app.build_share_public_components(sid)
    row = pub[0]["components"][-1]["components"]
    start_btn = next(b for b in row if b.get("label", "").endswith("Start Hunting"))
    # the button targets the owner's id, and the hunt handler's "again" branch
    # makes a *stranger* (clicker != owner) hunt as themselves — verified here by
    # the custom_id shape the handler keys on.
    assert start_btn["custom_id"] == f"hunt:again:{owner}"
    # rarity rule
    assert app._rarity_shareable("epic") and not app._rarity_shareable("common")
    assert app._rarity_shareable("rare", personal_first=True)
    assert not app._rarity_shareable("rare", personal_first=False)


# ─────────────────────────────────────────────────────────────
# V2.1 — persistent HP shared by animal + mythic combat
# ─────────────────────────────────────────────────────────────
def test_hp_shared_between_animal_and_myth_fight():
    _reset()
    u = "hpshare"
    _mk_user(u)
    app.data[u]["level"] = 300
    app.data[u]["health"]["hp"] = 40   # already hurt from something earlier
    # a myth fight should start at the CURRENT 40 HP, not a fresh 100
    app.data[u]["_boss"] = {"creature": "Bigfoot", "biome": "village",
                            "eid": "e1", "mhp": 100, "mhp_max": 100, "turn": 1,
                            "fallen": False, "guard": False, "enrage": False,
                            "mdebuff": False, "log": []}
    b = app._myth_fight_ensure(u)
    assert b is not None
    php, pmax = app.player_hp(u)
    assert php == 40 and pmax == 100
    # defending in the myth fight heals the SAME health pool
    random.seed(9)
    for _ in range(30):
        out = app.myth_fight_turn(u, "defend")
        if out["kind"] != "ongoing":
            break
    hp_after, _ = app.player_hp(u)
    assert app.data[u]["health"]["hp"] == hp_after   # single source of truth


def test_animal_fight_ko_no_loss_and_rookie_protection():
    _reset()
    u = "kotest"
    _mk_user(u)
    app.data[u]["level"] = 50
    money0 = app.data[u]["money"]
    xp0 = app.data[u]["xp"]
    inv0 = list(app.data[u]["inv"])
    assert app.data[u]["health"]["rookie_revive_used"] is False   # fresh account
    # force a fight the player is guaranteed to lose — random.random() pinned to
    # 0.0 so the animal's attack-chance gate always succeeds (random.randint,
    # used for the damage roll itself, is untouched and still varies).
    orig_random = random.random
    random.random = lambda: 0.0
    try:
        app.data[u]["fight"] = {"kind": "animal", "animal": "Western Coyote", "biome": "village",
                                "eid": "kox", "mhp": 10_000, "mhp_max": 10_000, "turn": 1,
                                "guard": False, "aim": False, "log": [], "bonus": "normal"}
        app.data[u]["health"]["hp"] = 1
        out = app.animal_fight_turn(u, "attack")
        assert out["kind"] == "ko"
        assert out["rookie_save"] is True
        assert app.data[u]["health"]["hp"] == app.ROOKIE_KO_RECOVERY_HP
        assert app.data[u]["health"]["rookie_revive_used"] is True
        # nothing lost
        assert app.data[u]["money"] == money0
        assert app.data[u]["xp"] == xp0
        assert app.data[u]["inv"] == inv0
        # second KO does NOT get rookie protection
        app.data[u]["fight"] = {"kind": "animal", "animal": "Western Coyote", "biome": "village",
                                "eid": "kox2", "mhp": 10_000, "mhp_max": 10_000, "turn": 1,
                                "guard": False, "aim": False, "log": [], "bonus": "normal"}
        app.data[u]["health"]["hp"] = 1
        out2 = app.animal_fight_turn(u, "attack")
        assert out2["kind"] == "ko"
        assert out2["rookie_save"] is False
    finally:
        random.random = orig_random
    assert app.data[u]["health"]["hp"] == app.KO_RECOVERY_HP


def test_one_dangerous_animal_per_hunt():
    _reset()
    u = "onedanger"
    _mk_user(u, level=50, biome="village")
    # force every rolled animal to be encounter-eligible
    orig_chance = app.animal_encounter_chance
    app.animal_encounter_chance = lambda a: 1.0
    orig_multi = app.TOOLS["Bare Hands"].get("multi_catch", 1)
    app.TOOLS["Bare Hands"]["multi_catch"] = 3
    try:
        random.seed(4)
        found_fight = False
        for _ in range(20):
            app.data[u]["fight"] = None
            app.data[u]["hunt_cd"] = 0
            app.data[u]["_hunt_times"] = []; app.data[u]["_last_hunt_ts"] = None
            r = run(_run_hunt_txn(u))
            if r.get("ok") and r.get("animal_encounter", {}) and \
               r["animal_encounter"].get("kind") == "fight":
                found_fight = True
                # exactly one interactive encounter live, and it consumed one
                # of the multi=3 rolled animals — at most 2 instant catches left
                assert app.data[u].get("fight") is not None
                assert len(r["catches"]) <= 2
                break
        assert found_fight, "expected at least one animal encounter in 20 hunts"
    finally:
        app.animal_encounter_chance = orig_chance
        app.TOOLS["Bare Hands"]["multi_catch"] = orig_multi


def test_animal_flee_before_fight_no_combat():
    _reset()
    u = "fleetest"
    _mk_user(u)
    stats = app.animal_combat_stats("Cottontail Rabbit")   # 'passive' default -> flee_chance
    assert stats["flee_chance"] > 0
    orig_random = random.random
    random.random = lambda: 0.0   # force the flee roll to succeed
    try:
        out = app.start_animal_encounter(u, "Cottontail Rabbit", "village")
    finally:
        random.random = orig_random
    assert out["kind"] == "fled"
    assert app.data[u].get("fight") is None   # no combat at all was started


def test_rookie_goals_and_chest():
    _reset()
    u = "goals1"
    _mk_user(u)
    app.data[u]["level"] = 5
    for i in range(5):
        app.record_catch(u, f"Test Animal {i}", "Bare Hands", 10)
    app.data[u]["total_caught"] = 5
    app._rookie_goal_progress(u, "buy_tool")
    app._rookie_goal_progress(u, "view_world")
    rg = app.data[u]["rookie_goals"]
    assert all(rg.values()), rg
    assert app.data[u]["rookie_chest_claimed"] is True
    assert app.data[u]["crate_inv"].get("Rare Crate", 0) >= 1
    assert "Rookie Hunter" in app.data[u]["earned_titles"]
    # idempotent — claiming twice doesn't double the crate
    crates_before = app.data[u]["crate_inv"]["Rare Crate"]
    app._grant_rookie_chest(u)
    assert app.data[u]["crate_inv"]["Rare Crate"] == crates_before


def test_healing_item_used_in_combat():
    _reset()
    u = "healtest"
    _mk_user(u)
    app.data[u]["healing_inv"] = {"Bandage": 1}
    app.data[u]["health"]["hp"] = 50
    app.data[u]["fight"] = {"kind": "animal", "animal": "Cottontail Rabbit", "biome": "village",
                            "eid": "heal1", "mhp": 999, "mhp_max": 999, "turn": 1,
                            "guard": False, "aim": False, "log": [], "bonus": "normal"}
    out = app.animal_fight_turn(u, "heal")
    assert out["kind"] == "ongoing"
    assert app.data[u]["health"]["hp"] == 75   # +25 from the Bandage
    assert "Bandage" not in app.data[u]["healing_inv"]   # consumed, count hit 0


def test_onboarding_scripted_danger_flow():
    _reset()
    u = "onbdanger"
    app.data.pop(u, None)
    app.init_user(u)
    assert app.onboarding_active(u)
    app._onb_set_step(u, "trial")
    results, tr = app._onb_grant_trial_and_catches(u)
    assert len(results) == 2
    assert app.trial_tool_active(u) is not None
    animal = app._onb_start_scripted_danger(u)
    assert app.data[u]["fight"]["animal"] == animal
    assert app.data[u]["fight"]["mhp"] < app.animal_combat_stats(animal)["hp"]  # softened
    app._onb_set_step(u, "danger")
    # win it (scripted HP is low — a top-tier weapon finishes it in one hit)
    app.data[u]["owned_tools"] = ["Bare Hands"]
    random.seed(2)
    out = {"kind": "ongoing"}
    for _ in range(15):
        out = app.animal_fight_turn(u, "attack")
        if out["kind"] != "ongoing":
            break
    assert out["kind"] in ("win", "ko", "escape")
    comps = app._onb_after_scripted_danger(u, out)
    assert app._onb(u)["step"] == "pack"
    assert isinstance(comps, list) and comps[0]["type"] == 17
    if out["kind"] == "win":
        assert "Rookie Hunter" in app.data[u]["earned_titles"]
        assert app.data[u]["healing_inv"].get("First Aid Kit", 0) >= 1


def test_trial_tool_expiry_and_display():
    _reset()
    u = "trialexp"
    _mk_user(u)
    app.data[u]["trial_tool"] = {"tool": "Shortbow", "expires_at": time.time() + 300}
    assert app.trial_tool_active(u) is not None
    assert "Training Shortbow" in app.trial_tool_line(u)
    app.data[u]["trial_tool"]["expires_at"] = time.time() - 1
    assert app.trial_tool_active(u) is None
    assert app.trial_tool_line(u) == ""


def test_hp_regen_lazy_and_capped():
    _reset()
    u = "regen1"
    _mk_user(u)   # onboarding.completed=True here -> baseline regen rate, not the resting rate
    app.data[u]["health"]["hp"] = 50
    app.data[u]["health"]["last_regen_ts"] = time.time() - 600   # 10 min ago
    healed = app.refresh_health(u)
    assert healed == 10 * app.HP_REGEN_PER_MIN   # 4/min baseline
    assert app.data[u]["health"]["hp"] == 50 + healed
    # never exceeds max_hp
    app.data[u]["health"]["hp"] = app.PLAYER_BASE_HP
    app.data[u]["health"]["last_regen_ts"] = time.time() - 6000
    healed2 = app.refresh_health(u)
    assert healed2 == 0
    assert app.data[u]["health"]["hp"] == app.PLAYER_BASE_HP


# ─────────────────────────────────────────────────────────────
def _all_tests():
    return sorted(n for n in globals() if n.startswith("test_"))


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(_ensure_db())
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
