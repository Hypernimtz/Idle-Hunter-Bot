"""Retuning tool for EXPLORE_REWARD_MULT (not a test, not run by CI): run it from the repo root with
    python tests/sim_explore_income.py     (env: SECONDS, RUNS, LEVEL, TOOLS, T_ACT, T_CLASSIC)
Compare what an Explore session earns per minute with what a Classic session earns, with the real Explore payout.

Time model (seconds): every Explore button press costs T_ACT; a Fire also waits out the hunt cooldown.
A Classic hunt costs T_CLASSIC (cooldown + a click). Value = what the hunts pay (the real Explore bonus is ON)."""
import sys, os, asyncio, random, traceback, statistics
sys.path.insert(0, 'tests'); sys.path.insert(0, '.')
import test_explore as te

app, gd = te.app, te.gd
asyncio.set_event_loop(asyncio.new_event_loop())
app.tick_verify = lambda uid: None          # the anti-autoclicker gate is not what is being measured
te.run(te.td.tt._ensure_db())

T_ACT = float(os.environ.get("T_ACT", "2.0"))
T_CLASSIC = float(os.environ.get("T_CLASSIC", "3.5"))
CD = 3.0
SECONDS = int(os.environ.get("SECONDS", "1800"))
RUNS = int(os.environ.get("RUNS", "5"))
LEVEL = int(os.environ.get("LEVEL", "300"))


def setup(tool, biome="village"):
    d = te._fresh(tool=tool, owned_tools=[tool], level=LEVEL)
    d["biome"] = biome
    d["health"]["hp"] = d["health"]["max_hp"] = 100000
    if gd.tool_needs_ammo(tool):
        a = gd.get_ammo_for_tool(tool)[0]
        d["ammo_inv"], d["equipped_ammo"] = {a: 9999}, a
    d["hunt_cd"] = 0
    return d


def bfs_step(st, goals):
    """First step of the shortest walk to any goal tile, or None."""
    from collections import deque
    start = (st["x"], st["y"])
    if start in goals:
        return None
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        for key, (dx, dy) in app._EX_DIRS.items():
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in prev or not app._ex_walkable(st, *nxt) or app._ex_animal_at(st, *nxt) or not app._ex_animal_safe(st, *nxt):
                continue
            prev[nxt] = (cur, key)
            if nxt in goals:
                while prev[nxt][0] != start:
                    nxt = prev[nxt][0]
                return prev[nxt][1]
            q.append(nxt)
    return None


def explore_session(tool):
    d = setup(tool)
    st = app._ex_state(te.U)
    t = 0.0
    last_fire = -99.0
    money = xp = 0
    catches = 0
    shots = 0
    clicks = 0
    reach = gd.shape_reach(tool)
    while t < SECONDS:
        d["health"]["hp"] = d["health"]["max_hp"]
        st = app._ex_state(te.U)
        if app._ex_over(st):
            app.explore_new(te.U); t += T_ACT; clicks += 1
            continue
        tgt = app._ex_target(st, tool)
        if tgt is not None:
            wait = max(0.0, last_fire + CD - t)
            t += wait
            d["hunt_cd"] = 0
            out = app.explore_fire(te.U)
            t += T_ACT; clicks += 1
            last_fire = t
            shots += 1
            res = out.get("result") or {}
            for c in res.get("catches", []):
                money += c["sell_value"]; xp += c["xp_earned"]; catches += 1
            continue
        # walk: toward a visible animal, else toward a clue / any animal, else wander
        goals = set()
        vis = app._ex_visible(st)
        cand = vis or [a for a in st["animals"] if a["clue"] > 0] or []
        for a in cand:
            for p in app._ex_reach(st):
                if (a["x"] - p[0], a["y"] - p[1]) in reach:
                    goals.add(p)
        key = bfs_step(st, goals) if goals else None
        if key is None:
            opts = [k for k, (dx, dy) in app._EX_DIRS.items() if app._ex_walkable(st, st["x"] + dx, st["y"] + dy)
                    and app._ex_animal_safe(st, st["x"] + dx, st["y"] + dy) and not app._ex_animal_at(st, st["x"] + dx, st["y"] + dy)]
            key = random.choice(opts) if opts else "wait"
        app.explore_move(te.U, key)
        t += T_ACT; clicks += 1
    return money / t * 60, xp / t * 60, catches / t * 60, clicks


def classic_session(tool):
    d = setup(tool)
    t = 0.0
    money = xp = 0
    n = 0
    while t < SECONDS:
        d["hunt_cd"] = 0
        d["health"]["hp"] = d["health"]["max_hp"]
        res = app.run_hunt(te.U)
        t += T_CLASSIC
        for key in ("fight", "_boss", "tracking"):
            d[key] = None
        if res.get("ok"):
            for c in res["catches"]:
                money += c["sell_value"]; xp += c["xp_earned"]; n += 1
    return money / t * 60, xp / t * 60, n / t * 60


def avg(f, tool):
    rows = []
    for i in range(RUNS):
        random.seed(100 + i)
        rows.append(f(tool))
    return [statistics.mean(r[j] for r in rows) for j in range(3)]


try:
    tools = os.environ.get("TOOLS", "Bare Hands,Slingshot,Hunting Knife,Spear,Longbow,Shotgun,Plasma Caster,Gravity Trap,Cosmic RPG,Nuke Launcher").split(",")
    print(f"{'tool':16} {'multi':>5} | classic $/min  catches/min | explore $/min catches/min | explore/classic")
    for tool in tools:
        c = avg(classic_session, tool)
        x = avg(explore_session, tool)
        print(f"{tool:16} {gd.TOOLS[tool].get('multi_catch', 1):>5} | {c[0]:>12,.0f} {c[2]:>8.1f} | {x[0]:>12,.0f} {x[2]:>8.2f} | {x[0] / max(1, c[0]):.3f}  (xp {x[1] / max(1, c[1]):.3f})", flush=True)
except Exception:
    traceback.print_exc()
sys.stdout.flush()
os._exit(0)
