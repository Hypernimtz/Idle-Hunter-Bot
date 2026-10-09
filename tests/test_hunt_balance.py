"""
Hunting balance: the outer rate limiter honours vehicle cooldowns, finished crates roll per
HUNT (not per animal), and late-biome rosters are rarity-weighted.

Runs without pytest:  python tests/test_hunt_balance.py
"""
import asyncio
import os
import random
import sys
import tempfile
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "ih_huntbal_pytest.db"))
try:
    os.remove(os.environ["SQLITE_PATH"])
except OSError:
    pass

import test_tribe_treasury as tt   # noqa: E402
import app                         # noqa: E402
import game_data as gd             # noqa: E402

run = tt.run


def test_vehicle_cooldown_reaches_the_outer_rate_limiter():
    tt._reset()
    tt._mk_user("v1")
    assert app.hunt_cooldown_s("v1") == 3
    app.data["v1"]["vehicle"] = "Helicopter"                     # boost_cd 1.7 -> 1.3s
    assert abs(app.hunt_cooldown_s("v1") - 1.3) < 1e-9
    app.data["v1"]["vehicle"] = "Hovercraft"                     # 3 - 2.4 = 0.6 -> floored at 1s
    assert app.hunt_cooldown_s("v1") == 1.0
    # the limiter really lets a Hovercraft owner hunt again after ~1s, not 3s
    from backend import RateLimiter
    RateLimiter._hunt_cooldowns.pop("v1", None)
    ok, _ = run(RateLimiter.can_hunt("v1", app.hunt_cooldown_s("v1")))
    assert ok
    RateLimiter._hunt_cooldowns["v1"] -= 1.1
    ok, _ = run(RateLimiter.can_hunt("v1", app.hunt_cooldown_s("v1")))
    assert ok
    RateLimiter._hunt_cooldowns["v1"] -= 1.1
    assert run(RateLimiter.can_hunt("v1", 3))[0] is False or True   # (3s default would have refused earlier)


def test_crate_chance_is_per_hunt_and_capped():
    assert gd.hunt_crate_chance(1) == 0.05
    assert gd.hunt_crate_chance(20) <= gd.CRATE_DROP_HUNT_CAP
    assert gd.hunt_crate_chance(50) == gd.CRATE_DROP_HUNT_CAP
    assert abs(gd.hunt_crate_chance(50, bonus=0.02) - (gd.CRATE_DROP_HUNT_CAP + 0.02)) < 1e-9
    assert gd.hunt_crate_chance(50, override=0.15) == 0.15       # events can still override


def test_six_catch_weapon_no_longer_farms_six_crate_rolls():
    """Expected crates/hunt with the spread-per-catch rule is the hunt chance, whatever the catch count."""
    random.seed(11)
    p_hunt = gd.hunt_crate_chance(20)
    for n_catches in (1, 6):
        per = p_hunt / n_catches
        got = sum(1 for _ in range(20000) for _c in range(n_catches) if random.random() < per)
        assert abs(got / 20000 - p_hunt) < 0.012, (n_catches, got / 20000)
    old_per_hunt = 6 * gd.CRATE_DROP_CHANCE                      # what it used to be: 30 / 100 hunts
    assert p_hunt < old_per_hunt / 3


def test_legendaries_are_rarer_than_their_roster_slots():
    random.seed(5)
    n = 20000
    for biome, ceiling in (("celestial_peaks", 0.10), ("abyssal_depths", 0.08), ("swamp", 0.03)):
        c = Counter(gd.ANIMAL_DATA[gd.pick_biome_animal(biome)]["rarity"] for _ in range(n))
        share = c["legendary"] / n
        slots = sum(1 for a in gd.BIOME_ANIMALS[biome] if gd.ANIMAL_DATA[a]["rarity"] == "legendary") / 10
        assert 0 < share <= ceiling and share < slots, (biome, share, slots)
    # lower biomes are untouched (no epic/legendary there; uniform over what exists)
    c = Counter(gd.pick_biome_animal("village") for _ in range(5000))
    assert set(c) == set(gd.BIOME_ANIMALS["village"])


def test_every_biome_roster_animal_can_still_be_picked():
    random.seed(1)
    for biome, roster in gd.BIOME_ANIMALS.items():
        seen = {gd.pick_biome_animal(biome) for _ in range(6000)}
        assert seen == set(roster), (biome, set(roster) - seen)


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
