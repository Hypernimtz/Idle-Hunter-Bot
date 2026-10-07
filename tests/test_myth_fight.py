"""
Mythic boss fight difficulty (2026-10-04 "make it hard"): kick/punch spam must not
win, a missed kick must cost HP, Defend can't be used to stall, and shooting still
carries a real chance to lose.

Runs without pytest:  python tests/test_myth_fight.py
"""
import asyncio
import json
import os
import random
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_mythfight_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import discord.ext.commands as _c  # noqa: E402
_c.Bot.run = lambda *a, **k: None

import app          # noqa: E402
import backend      # noqa: E402

_DB_READY = False


async def _ensure_db():
    global _DB_READY
    if not _DB_READY:
        await backend.init_databases()
        app.register_state_refs(app.data, app.tribe_data)
        _DB_READY = True


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mk(uid, biome="village", tool="Bare Hands", hp=100, **over):
    app.data.pop(uid, None)
    app.init_user(uid)
    d = app.data[uid]
    d["onboarding"] = {"version": 2, "completed": True, "step": "done", "starter_pack": None}
    d["verify"] = {"needed": False, "time": 10 ** 9, "code": "ABCD"}
    d["level"] = 300
    d["tool"] = tool
    d["health"]["hp"] = hp
    d["health"]["last_regen_ts"] = 2 * 10 ** 10      # no passive regen mid-test
    d.update(over)
    mhp = app._myth_monster_hp(biome)
    d["_boss"] = {"creature": "Bigfoot", "biome": biome, "eid": "e", "mhp": mhp, "mhp_max": mhp,
                  "turn": 1, "fallen": False, "guard": False, "enrage": False, "mdebuff": False, "log": []}
    return d


class _Dice:
    """Scripted random.randint: queued answers for the (1,100) percentile rolls, a
    fixed answer for everything else (damage ranges -> their low end)."""
    def __init__(self, percentiles):
        self.q = list(percentiles)
        self.real = random.randint

    def __call__(self, a, b):
        if (a, b) == (1, 100):
            return self.q.pop(0) if self.q else 100
        return a

    def __enter__(self):
        random.randint = self
        return self

    def __exit__(self, *e):
        random.randint = self.real


def _turn(uid, action):
    async def go():
        async with app.user_transaction(uid):
            return app.myth_fight_turn(uid, action)
    return run(go())


def test_missed_kick_always_costs_hp():
    d = _mk("k1")
    with _Dice([100, 100, 100]):          # kick misses, no fall, monster misses
        out = _turn("k1", "kick")
    assert out["kind"] == "ongoing"
    lo = app.FIGHT_KICK_RECOIL[0] + app.BIOME_TOOL_TIER["village"] // 2
    assert d["health"]["hp"] == 100 - lo, d["health"]["hp"]
    assert not d["_boss"]["fallen"]
    assert any("HP" in line for line in d["_boss"]["log"])


def test_missed_kick_can_knock_you_down_and_the_monster_gets_a_free_hit():
    d = _mk("k2")
    with _Dice([100, 1, 100]):            # kick misses, you fall; monster accuracy roll is irrelevant (fallen)
        _turn("k2", "kick")
    assert d["_boss"]["fallen"] is True
    assert d["health"]["hp"] < 100 - app.FIGHT_KICK_RECOIL[0]      # recoil AND a monster hit
    with _Dice([100]):
        _turn("k2", "punch")              # the scramble turn: no attack lands
    assert d["_boss"]["fallen"] is False
    assert d["_boss"]["mhp"] == d["_boss"]["mhp_max"]


def test_a_kick_that_lands_costs_nothing():
    d = _mk("k3")
    with _Dice([1, 100]):                 # lands; monster misses
        _turn("k3", "kick")
    assert d["health"]["hp"] == 100 and d["_boss"]["mhp"] < d["_boss"]["mhp_max"]


def test_defend_only_heals_a_few_times_per_fight():
    d = _mk("d1", hp=10)
    gains = []
    for _ in range(app.FIGHT_DEFEND_HEAL_CAP + 3):
        before = d["health"]["hp"]
        with _Dice([100]):                # monster always misses
            _turn("d1", "defend")
        gains.append(d["health"]["hp"] - before)
    assert all(g > 0 for g in gains[:app.FIGHT_DEFEND_HEAL_CAP]), gains
    assert all(g == 0 for g in gains[app.FIGHT_DEFEND_HEAL_CAP:]), gains


def test_shooting_leaves_you_exposed_and_can_still_lose():
    d = _mk("s1", biome="forest", tool="Shortbow", hp=30,
            equipped_ammo="Wooden Arrow", ammo_inv={"Wooden Arrow": 10_000})
    d["_boss"]["mhp"] = d["_boss"]["mhp_max"] = 500
    with _Dice([100, 100]):               # volley misses; monster misses
        _turn("s1", "shoot")
    assert "exposed" not in d["_boss"]                      # consumed by the monster's turn
    # a real fight: shooting at 30 HP loses a good share of the time
    random.seed(7)
    deaths = 0
    for i in range(120):
        u = f"s2_{i}"
        _mk(u, biome="forest", tool="Shortbow", hp=30,
            equipped_ammo="Wooden Arrow", ammo_inv={"Wooden Arrow": 10_000})
        for _ in range(60):
            out = _turn(u, "shoot")
            if out["kind"] != "ongoing":
                break
        deaths += out["kind"] == "death"
    assert deaths >= 30, f"shooting while hurt should often lose, only {deaths}/120 deaths"


def test_spamming_kick_or_punch_no_longer_wins():
    random.seed(11)
    for action, cap in (("kick", 0.12), ("punch", 0.06)):
        wins = 0
        n = 150
        for i in range(n):
            u = f"sp_{action}_{i}"
            _mk(u)
            for _ in range(120):
                out = _turn(u, action)
                if out["kind"] != "ongoing":
                    break
            wins += out["kind"] == "kill"
        assert wins / n <= cap, f"{action}-spam won {wins}/{n}"


def _find(o, pred):
    if isinstance(o, dict):
        if pred(o):
            yield o
        for v in o.values():
            yield from _find(v, pred)
    elif isinstance(o, list):
        for v in o:
            yield from _find(v, pred)


def test_fight_and_outcome_panels_show_the_creature_art_top_right():
    d = _mk("art1")
    thumbs = list(_find(app.build_myth_fight_components("art1"), lambda c: c.get("type") == 11))
    assert len(thumbs) == 1 and thumbs[0]["media"]["url"].startswith("https://cdn.discordapp.com/emojis/")
    assert thumbs[0]["media"]["url"].endswith("size=256")
    secs = list(_find(app.build_myth_fight_components("art1"), lambda c: c.get("type") == 9))
    assert secs and secs[0]["accessory"]["type"] == 11
    head = secs[0]["components"][0]["content"]
    assert "BIGFOOT" in head and "ITS HP" in head and "<:" not in head.splitlines()[0]   # art replaces the inline emoji
    for kind in ("kill", "death", "escape"):
        out = {"kind": kind, "creature": "Bigfoot", "bounty": 1, "gems": 1, "xp": 1, "balance": 1, "loss": 1,
               "php": 50, "level_ups": 0, "level": 5, "clean": True, "drop": "", "hp": 40}
        comps = app.build_myth_outcome_components("art1", out)
        assert list(_find(comps, lambda c: c.get("type") == 11)), kind


def test_creature_without_custom_art_keeps_the_plain_layout():
    _mk("art2")
    real = app.creature_emoji
    app.creature_emoji = lambda name: "🔮"
    try:
        comps = app.build_myth_fight_components("art2")
    finally:
        app.creature_emoji = real
    assert not list(_find(comps, lambda c: c.get("type") in (9, 11)))
    assert "🔮 BIGFOOT" in comps[0]["components"][0]["content"]


def test_a_volley_costs_ten_rounds_and_a_fight_is_cheap_next_to_its_payout():
    assert app.FIGHT_SHOOT_AMMO == 10
    d = _mk("am1", biome="forest", tool="Shortbow", equipped_ammo="Wooden Arrow", ammo_inv={"Wooden Arrow": 100})
    d["_boss"]["mhp"] = d["_boss"]["mhp_max"] = 5000
    with _Dice([100, 100, 100]):
        _turn("am1", "shoot")
    assert d["ammo_inv"]["Wooden Arrow"] == 90
    # a whole ~8-volley fight with the priciest money ammo of the weapon a player in that biome would use
    # is a sliver of the bounty at every depth (it used to cost MORE than the bounty)
    tool_for_tier = {t["tier"]: t["ammo_type"] for t in app.TOOLS.values() if t.get("ammo_type") and t["tier"] < 100}
    priciest = {}
    for n, am in app.AMMO.items():
        if am["currency"] == "money":
            priciest[am["ammo_type"]] = max(priciest.get(am["ammo_type"], 0), am["price"])
    for name, c in app.MYTHIC_CREATURES.items():
        tier = max([t for t in tool_for_tier if t <= max(app.BIOME_TOOL_TIER[c["biome"]], 5)] or [5])
        cost = 8 * app.FIGHT_SHOOT_AMMO * priciest[tool_for_tier[tier]]
        assert cost < 0.3 * c["value"] * app.MYTH_REPEAT_VALUE_RANGE[0], (name, cost)


def test_a_kill_pays_better_and_patches_you_up():
    assert app.MYTH_REPEAT_VALUE_RANGE[0] >= 1.5 and app.MYTH_XP_MULT >= 3
    d = _mk("win1", hp=20)
    d["stats"]["myths_killed"] = 3                       # not the first-ever kill
    d["_boss"]["mhp"] = 1                                # one hit finishes it
    with _Dice([1]):                                     # the punch lands
        out = _turn("win1", "punch")
    assert out["kind"] == "kill"
    mx = app.effective_max_hp("win1")
    assert out["healed"] == int(mx * app.MYTH_WIN_HEAL_PCT) and d["health"]["hp"] == 20 + out["healed"]
    assert out["php"] == 20                              # the panel still reports what the fight left you with
    lo, hi = app.myth_repeat_bounty_range("Bigfoot")
    assert lo >= 1.5 * app.MYTHIC_CREATURES["Bigfoot"]["value"] and lo <= out["bounty"] <= hi
    assert out["xp"] == int(app.MYTHIC_CREATURES["Bigfoot"]["xp"] * app.MYTH_XP_MULT)
    assert "patch up" in json.dumps(app.build_myth_outcome_components("win1", out), ensure_ascii=False)
    # never heals past full
    d2 = _mk("win2", hp=99)
    d2["stats"]["myths_killed"] = 3
    d2["_boss"]["mhp"] = 1
    with _Dice([1]):
        out2 = _turn("win2", "punch")
    assert d2["health"]["hp"] == app.effective_max_hp("win2") and out2["healed"] == 1


def test_fight_is_much_tougher_than_before():
    assert app._myth_monster_hp("village") >= 200
    assert app._myth_monster_hp("celestial_peaks") >= 280
    assert app.FIGHT_KICK_ACC < 64 and app.FIGHT_SHOOT_ACC < 88 and app.FIGHT_PUNCH_ACC < 92


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
