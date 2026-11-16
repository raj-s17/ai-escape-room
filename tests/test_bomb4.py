"""Bomb Squad engine: every manual rule, strikes, D-pad stages, chaos events."""

import pytest

from defuse_core import bomb4 as B


@pytest.mark.parametrize("colours,led,expected", [
    (["blue", "blue", "red"], "red", 2),                       # 3: LED red -> last
    (["blue", "red", "white"], "off", 1),                      # 3: no green -> second
    (["green", "red", "white"], "blue", 0),                    # 3: otherwise first
    (["blue", "red", "blue", "white"], "red", 2),              # 4: >1 blue -> last blue
    (["red", "green", "white", "black"], "off", 2),            # 4: LED off -> third
    (["red", "green", "white", "yellow"], "red", 0),           # 4: last yellow -> first
    (["red", "green", "white", "black"], "red", 1),            # 4: otherwise second
    (["red", "black", "white", "green", "blue"], "green", 3),  # 5: green LED + one black -> fourth
    (["blue", "black", "black", "green", "white"], "red", 0),  # 5: no red -> first
    (["red", "black", "black", "green", "white"], "red", 4),   # 5: last white -> last
    (["red", "black", "black", "green", "blue"], "red", 2),    # 5: otherwise third
    (["red", "blue", "green", "white", "black", "red"], "off", 2),     # 6: no yellow -> third
    (["yellow", "blue", "green", "white", "black", "red"], "blue", 4),  # 6: LED blue -> fifth
    (["yellow", "white", "green", "white", "black", "red"], "red", 3),  # 6: >1 white -> last white
    (["yellow", "blue", "green", "white", "black", "red"], "red", 3),   # 6: otherwise fourth
])
def test_wire_rules(colours, led, expected):
    assert B.correct_wire({"colours": colours, "led": led}) == expected


@pytest.mark.parametrize("led,value,expected", [
    ("red", 3, "up"), ("red", 4, "down"), ("green", 4, "left"), ("green", 5, "right"),
    ("blue", 6, "down"), ("blue", 7, "up"), ("yellow", 4, "right"), ("yellow", 5, "left")])
def test_dpad_rules(led, value, expected):
    assert B.correct_direction(led, value) == expected


@pytest.mark.parametrize("result,led,expected", [
    (36, "blue", 6), (27, "red", 2), (16, "green", 2), (9, "red", 0), (13, "green", 6)])
def test_numpad_rules(result, led, expected):
    assert B.correct_digit(result, led) == expected


def test_switch_rules():
    assert B.switch_targets(["red", "green", "blue", "white", "white"], [3, 4, 9, 0, 0]) == \
        [True, False, False, False, False]
    assert B.switch_targets(["white", "red", "white", "green", "blue"], [0, 2, 0, 7, 9]) == \
        [True, False, False, True, False]


def armed(seed=1, chaos=False):
    b = B.new_bomb(seed=seed, chaos=chaos)
    B.start(b, now=1000)
    return b


def test_full_defuse_and_strikes():
    b = armed()
    wrong = (B.correct_wire(b["wires"]) + 1) % len(b["wires"]["colours"])
    assert B.cut_wire(b, wrong + 1, now=1001) == "strike"
    assert B.cut_wire(b, B.correct_wire(b["wires"]) + 1, now=1002) == "solved"
    for _ in range(B.DPAD_STAGES):
        d = b["dpad"]
        B.press_dpad(b, B.correct_direction(d["led"], d["value"]), now=1003)
    assert b["solved"]["dpad"]
    s = b["numpad"]
    B.press_key(b, s["layout"].index(B.correct_digit(B.sum_result(s), s["led"])), now=1004)
    sw = b["switches"]
    for i, want in enumerate(B.switch_targets(sw["lights"], sw["digits"])):
        if sw["up"][i] != want:
            B.flip_switch(b, i, now=1005)
    assert B.press_enter(b, now=1006) == "defused" and b["status"] == "defused"


def test_wrong_dpad_is_a_strike_and_changes_the_module():
    b = armed(seed=3)
    d = b["dpad"]
    before = (d["led"], d["value"], d["rolls"])
    wrong = next(x for x in ("up", "down", "left", "right") if x != B.correct_direction(d["led"], d["value"]))
    assert B.press_dpad(b, wrong, now=1001) == "strike"
    assert d["rolls"] == before[2] + 1 and d["stage"] == 0


def test_three_strikes_and_timer():
    b = armed()
    for _ in range(3):
        B.press_enter(b, now=1001) if b["status"] == "armed" else None
        b["switches"]["up"] = [not x for x in B.switch_targets(b["switches"]["lights"], b["switches"]["digits"])]
    assert b["status"] == "exploded"
    b2 = armed()
    B.refresh(b2, now=1000 + b2["seconds"] + 1)
    assert b2["end_reason"] == "time ran out"


def test_chaos_events_happen_only_while_armed():
    b = B.new_bomb(seed=5, chaos=True)
    assert b["chaos"] and B.chaos_now(b) is None
    B.start(b, now=0)
    ev = b["chaos"][0]
    assert B.chaos_now(b, now=ev["at"] + 1) == ev["kind"]
    assert B.chaos_now(b, now=ev["at"] + B.CHAOS_LENGTH + 1) in (None, "power", "static")
    assert not B.new_bomb(seed=5, chaos=False)["chaos"]
