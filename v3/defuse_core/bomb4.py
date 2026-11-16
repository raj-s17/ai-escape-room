"""
Bomb Squad engine: four modules inspired by the logic of co-op bomb-defusal
games (wires with count/LED rules, a two-stage D-pad that can use Braille, a
maths keypad with jumbled keys and a switch panel), plus optional "chaos"
events. Plain JSON-serialisable dict; every action is validated here.
"""

from __future__ import annotations

import random
import time

from .squad_manual import DIRECTIONS, DPAD_LEDS, NUMPAD_LEDS, SWITCH_LIGHTS, WIRE_COLOURS, WIRE_LEDS

MAX_STRIKES = 3
DEFAULT_SECONDS = 300
MODULES = ("wires", "dpad", "numpad", "switches")
DPAD_STAGES = 2
CHAOS_LENGTH = 7          # seconds a chaos event lasts


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def new_bomb(seed=None, seconds=DEFAULT_SECONDS, chaos=True) -> dict:
    rng = random.Random(seed)
    n = rng.randint(3, 6)
    b = {
        "seed": rng.randrange(10 ** 9),
        "wires": {"colours": [rng.choice(WIRE_COLOURS) for _ in range(n)], "led": rng.choice(WIRE_LEDS), "cut": []},
        "dpad": {"stage": 0, "rolls": 0},
        "numpad": _new_sum(rng),
        "switches": {"lights": [rng.choice(SWITCH_LIGHTS) for _ in range(5)],
                     "digits": [rng.randint(0, 9) for _ in range(5)],
                     "up": [rng.random() < 0.5 for _ in range(5)]},
        "solved": {m: False for m in MODULES},
        "strikes": 0, "seconds": seconds, "started_at": None, "ended_at": None,
        "status": "waiting", "end_reason": None, "chaos": [], "chaos_on": chaos, "log": [],
    }
    _reroll_dpad(b)
    if chaos:
        # three disruptions spread over the round: power cuts and radio static
        for lo, hi in ((35, 60), (95, 130), (160, 210)):
            if hi < seconds:
                b["chaos"].append({"kind": rng.choice(["power", "static"]), "at": rng.randint(lo, hi)})
    return b


def _new_sum(rng):
    op = rng.choice(["+", "-", "×"])
    a, c = rng.randint(2, 12), rng.randint(2, 12)
    if op == "-" and c > a:
        a, c = c, a
    layout = list(range(10))
    rng.shuffle(layout)
    return {"a": a, "op": op, "b": c, "led": rng.choice(NUMPAD_LEDS), "layout": layout}


def _reroll_dpad(b):
    rng = random.Random(f"{b['seed']}-dpad-{b['dpad']['rolls']}")
    b["dpad"].update(led=rng.choice(DPAD_LEDS), value=rng.randint(1, 9), braille=rng.random() < 0.5)
    b["dpad"]["rolls"] += 1


# ---------------------------------------------------------------------------
# The real rules (must match squad_manual.py)
# ---------------------------------------------------------------------------
def correct_wire(w: dict) -> int:
    """0-based index of the wire to cut. Works on any {"colours", "led"} dict."""
    c, led, n = w["colours"], w["led"], len(w["colours"])
    if n == 3:
        if led == "red":
            return 2
        if "green" not in c:
            return 1
        return 0
    if n == 4:
        if c.count("blue") > 1:
            return max(i for i, x in enumerate(c) if x == "blue")
        if led == "off":
            return 2
        if c[-1] == "yellow":
            return 0
        return 1
    if n == 5:
        if led == "green" and c.count("black") == 1:
            return 3
        if "red" not in c:
            return 0
        if c[-1] == "white":
            return 4
        return 2
    if "yellow" not in c:
        return 2
    if led == "blue":
        return 4
    if c.count("white") > 1:
        return max(i for i, x in enumerate(c) if x == "white")
    return 3


def correct_direction(led: str, value: int) -> str:
    if led == "red":
        return "up" if value % 2 else "down"
    if led == "green":
        return "left" if value < 5 else "right"
    if led == "blue":
        return "down" if value in (3, 6, 9) else "up"
    return "right" if value <= 4 else "left"


def sum_result(s: dict) -> int:
    return {"+": s["a"] + s["b"], "-": s["a"] - s["b"], "×": s["a"] * s["b"]}[s["op"]]


def correct_digit(result: int, led: str) -> int:
    if led == "blue":
        return result % 10
    if result % 2 == 1 and result > 20:
        return int(str(result)[0])
    if result % 2 == 0:
        return result % 7
    return 9 - result % 10


def switch_targets(lights: list[str], digits: list[int]) -> list[bool]:
    out = []
    for light, d in zip(lights, digits):
        if light == "red":
            out.append(d % 2 == 1)
        elif light == "green":
            out.append(d >= 5)
        elif light == "blue":
            out.append(False)
        else:
            out.append(out[-1] if out else True)
    return out


# ---------------------------------------------------------------------------
# Time, status, chaos
# ---------------------------------------------------------------------------
def _now(now):
    return time.time() if now is None else now


def time_left(b, now=None) -> float:
    if b["started_at"] is None:
        return float(b["seconds"])
    end = b["ended_at"] or _now(now)
    return max(0.0, b["seconds"] - (end - b["started_at"]))


def elapsed(b, now=None) -> float:
    return 0.0 if b["started_at"] is None else b["seconds"] - time_left(b, now)


def refresh(b, now=None):
    if b["status"] == "armed" and time_left(b, now) <= 0:
        _finish(b, "exploded", "time ran out", now)
    return b


def chaos_now(b, now=None) -> str | None:
    """'power' or 'static' while a chaos event is happening, else None."""
    if b["status"] != "armed":
        return None
    t = elapsed(b, now)
    for ev in b["chaos"]:
        if ev["at"] <= t < ev["at"] + CHAOS_LENGTH:
            return ev["kind"]
    return None


def start(b, now=None) -> str:
    if b["status"] != "waiting":
        return "already_started"
    b["started_at"], b["status"] = _now(now), "armed"
    return "started"


def _finish(b, status, reason, now=None):
    b.update(status=status, end_reason=reason, ended_at=_now(now))


def _strike(b, why, now=None) -> str:
    b["strikes"] += 1
    b["log"].append(f"strike: {why}")
    if b["strikes"] >= MAX_STRIKES:
        _finish(b, "exploded", "three strikes", now)
        return "exploded"
    return "strike"


def _solve(b, module, now=None) -> str:
    b["solved"][module] = True
    if all(b["solved"].values()):
        _finish(b, "defused", "all modules defused", now)
        return "defused"
    return "solved"


def _blocked(b, module, now=None):
    refresh(b, now)
    if b["status"] == "waiting":
        return "not_started"
    if b["status"] != "armed":
        return "game_over"
    if b["solved"][module]:
        return "already_solved"
    return None


# ---------------------------------------------------------------------------
# Actions (only the Blind player has the tools)
# ---------------------------------------------------------------------------
def cut_wire(b, number: int, now=None) -> str:
    """number is 1-based from the Blind player's left."""
    if (x := _blocked(b, "wires", now)):
        return x
    w = b["wires"]
    i = number - 1
    if not 0 <= i < len(w["colours"]) or i in w["cut"]:
        return "invalid"
    w["cut"].append(i)
    return _solve(b, "wires", now) if i == correct_wire(w) else _strike(b, f"wrong wire {number}", now)


def press_dpad(b, direction: str, now=None) -> str:
    if (x := _blocked(b, "dpad", now)):
        return x
    if direction not in DIRECTIONS:
        return "invalid"
    d = b["dpad"]
    ok = direction == correct_direction(d["led"], d["value"])
    if ok:
        d["stage"] += 1
        if d["stage"] >= DPAD_STAGES:
            return _solve(b, "dpad", now)
        _reroll_dpad(b)
        return "progress"
    _reroll_dpad(b)
    return _strike(b, f"wrong D-pad direction {direction}", now)


def press_key(b, position: int, now=None) -> str:
    """position 0-9 on the jumbled keypad (row-major, 2 rows of 5)."""
    if (x := _blocked(b, "numpad", now)):
        return x
    s = b["numpad"]
    if not 0 <= position <= 9:
        return "invalid"
    digit = s["layout"][position]
    if digit == correct_digit(sum_result(s), s["led"]):
        return _solve(b, "numpad", now)
    return _strike(b, f"wrong key {digit}", now)


def flip_switch(b, index: int, now=None) -> str:
    if (x := _blocked(b, "switches", now)):
        return x
    if not 0 <= index < 5:
        return "invalid"
    b["switches"]["up"][index] = not b["switches"]["up"][index]
    return "flipped"


def press_enter(b, now=None) -> str:
    if (x := _blocked(b, "switches", now)):
        return x
    sw = b["switches"]
    if sw["up"] == switch_targets(sw["lights"], sw["digits"]):
        return _solve(b, "switches", now)
    return _strike(b, "switches wrong on ENTER", now)


RESULT_TEXT = {
    "solved": "✅ Module defused!", "progress": "🟢 Correct! The D-pad changes.",
    "strike": "❌ STRIKE!", "exploded": "💥 BOOM!", "defused": "🎉 Bomb defused - the van door unlocks!",
    "flipped": "", "invalid": "That isn't possible.", "already_solved": "Already defused.",
    "not_started": "Start the timer first.", "game_over": "The game is over.",
}
