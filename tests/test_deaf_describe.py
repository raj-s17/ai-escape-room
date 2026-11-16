"""Bomb Squad: a human Deaf player's everyday descriptions are understood by the rule-based
(offline / fallback) Mute player, the same as the callout buttons (no API key needed)."""

import pytest

import hub
import llm
from defuse_core import bomb4 as B
from themes import bomb_squad as S

WIRES = {"colours": ["green", "black", "red", "red", "white"], "led": "red"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original = hub.kick_ai
    monkeypatch.setattr(hub, "kick_ai", lambda s, c, background=True: original(s, c, background=False))
    monkeypatch.setattr(llm, "get_client", lambda: None)


@pytest.mark.parametrize("text", [
    "5 wires: green black red red white, the light is red",
    "wires are green, black, red, red, white and the LED is red",
    "there are 5 wires green black red red white. red led",
    "Wires: 5 wires, left to right: green, black, red, red, white. LED red.",
])
def test_wire_descriptions(text):
    assert S.describe_free_text(text)["wires"] == WIRES


@pytest.mark.parametrize("text,expected", [
    ("wires green black red red white, no light", {"colours": WIRES["colours"], "led": "off"}),
    ("wires red blue yellow", {"colours": ["red", "blue", "yellow"], "led": None}),
    ("d-pad led is green, centre shows 4", {"led": "green", "value": 4}),
    ("the dpad light is red and the middle is braille", {"led": "red", "value": None}),
    ("keypad: 11 minus 2, light blue", {"a": 11, "op": "-", "b": 2, "led": "blue"}),
    ("keypad sum 7 x 3 LED red", {"a": 7, "op": "×", "b": 3, "led": "red"}),
    ("switch lights are white, red, red, green, red and the numbers 99603",
     {"lights": ["white", "red", "red", "green", "red"], "digits": [9, 9, 6, 0, 3]}),
])
def test_other_descriptions(text, expected):
    assert list(S.describe_free_text(text).values()) == [expected]


def test_orders_are_not_mistaken_for_descriptions():
    assert S.describe_free_text("Cut wire 5 now") == {}


def test_callout_buttons_read_the_same_both_ways():
    b = B.new_bomb(seed=7)
    for m in B.MODULES:
        assert S.describe_free_text(S.callout(b, m))[m] == S.heard_knowledge([{"kind": "speech",
                                                                               "text": S.callout(b, m)}])[m]


def test_missing_light_colour_makes_mute_ask_again():
    events = [{"kind": "speech", "text": "wires red blue yellow"}]
    assert S.offline_mute_solve(events, {m: False for m in B.MODULES}) == ["m_wires", "repeat"]


def test_human_deaf_description_reaches_the_ai_mute():
    store = hub.new_store()
    code = hub.create_room(store, "me", "Raj", "bomb", "deaf", seed=7, chaos=False)
    S.start(store, code, "me")
    room = hub.get_room(store, code)
    n = len(room["events"])
    S.speak(store, code, "me", "5 wires: green black red red white, the light is red")
    signs = [e["tokens"] for e in room["events"][n:] if e["kind"] == "gesture"]
    correct = B.correct_wire(room["state"]["bomb"]["wires"]) + 1
    assert signs and signs[-1] == ["m_wires", f"n{correct}"]
