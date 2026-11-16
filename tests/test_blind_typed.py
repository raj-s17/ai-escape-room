"""Bomb Squad: typed chat - Blind instructions become actions, Mute words become hand signals (no API key needed)."""

import pytest

import hub
import llm
from defuse_core import bomb4 as B
from themes import bomb_squad as S


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original = hub.kick_ai
    monkeypatch.setattr(hub, "kick_ai", lambda s, c, background=True: original(s, c, background=False))
    monkeypatch.setattr(llm, "get_client", lambda: None)


@pytest.mark.parametrize("text,expected", [
    ("cutting wire 1", [("cut", 1)]),
    ("cut wire 1", [("cut", 1)]),
    ("Cut wire 4 from your left!", [("cut", 4)]),
    ("cut the first wire", [("cut", 1)]),
    ("snip wire one", [("cut", 1)]),
    ("cut 3", [("cut", 3)]),
    ("I'm cutting wire number 5", [("cut", 5)]),
    ("press up", [("dpad", "up")]),
    ("d pad left", [("dpad", "left")]),
    ("press the right arrow", [("dpad", "right")]),
    ("top row key 2", [("key", 1)]),
    ("Press the key in the top row, 2nd from your left!", [("key", 1)]),
    ("the 3rd key on the bottom row", [("key", 7)]),
    ("flip switch 1 and then flip switch 3", [("flip", 0), ("flip", 2)]),
    ("hit enter", [("enter", None)]),
    ("cut wire 2, then press up", [("cut", 2), ("dpad", "up")]),
])
def test_everyday_phrasing_is_understood(text, expected):
    assert S.parse_blind_instructions(text, B.new_bomb(seed=7)) == expected


@pytest.mark.parametrize("text", ["don't cut wire 1", "do not press up", "never cut the red wire",
                                  "Which wire do I cut?", "hello team", "Ready!"])
def test_warnings_questions_and_chatter_do_nothing(text):
    assert S.parse_blind_instructions(text, B.new_bomb(seed=7)) == []


def test_deaf_switch_callout_still_works():
    b = B.new_bomb(seed=7)
    acts = S.parse_blind_instructions("Switches, left to right: up, down, up, up, down - then ENTER!", b)
    assert acts[-1] == ("enter", None)
    assert all(k == "flip" for k, _ in acts[:-1])


def test_human_blind_typing_cuts_the_wire():
    store = hub.new_store()
    code = hub.create_room(store, "me", "Raj", "bomb", "blind", seed=7, chaos=False)
    S.start(store, code, "me")
    done = S.blind_typed(store, code, "me", "cutting wire 1")
    b = hub.get_room(store, code)["state"]["bomb"]
    assert done and done[0][0] == ("cut", 1)
    assert 0 in b["wires"]["cut"]                     # wire 1 really was cut


def test_only_the_blind_player_can_act_by_typing():
    store = hub.new_store()
    code = hub.create_room(store, "me", "Raj", "bomb", "deaf", seed=7, chaos=False)
    S.start(store, code, "me")
    assert S.blind_typed(store, code, "me", "cut wire 1") == []
    assert hub.get_room(store, code)["state"]["bomb"]["wires"]["cut"] in ([], [0])   # only the AI Blind may cut


# --- Mute: typed words become hand signals -------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("wires 4", ["m_wires", "n4"]),
    ("wires five", ["m_wires", "n5"]),
    ("d-pad up", ["m_dpad", "up"]),
    ("switches up up down down up", ["m_switches", "up", "up", "down", "down", "up"]),
    ("say again", ["repeat"]),
    ("go back", ["back"]),
    ("yes", ["yes"]),
])
def test_mute_typing_becomes_signs(text, expected):
    assert S.parse_signal_text(text) == (expected, [])


def test_mute_typing_reports_words_that_are_not_signs():
    assert S.parse_signal_text("wires 4 banana") == (["m_wires", "n4"], ["banana"])
    assert S.parse_signal_text("hello there") == ([], ["hello", "there"])


def test_human_mute_typing_is_signed_not_spoken():
    store = hub.new_store()
    code = hub.create_room(store, "me", "Raj", "bomb", "mute", seed=7, chaos=False)
    S.start(store, code, "me")
    ok, err, tokens, unknown = S.mute_typed(store, code, "me", "wires 5")
    room = hub.get_room(store, code)
    mine = [e for e in room["events"] if e.get("by") == "Raj"]
    assert ok and tokens == ["m_wires", "n5"]
    assert [e["kind"] for e in mine] == ["gesture"]             # a hand signal, never speech
    assert S.event_view(mine[0], "blind") is None                # Blind can't see it
    assert S.event_view(mine[0], "deaf") is not None             # Deaf can


def test_only_the_mute_player_can_sign_by_typing():
    store = hub.new_store()
    code = hub.create_room(store, "me", "Raj", "bomb", "deaf", seed=7, chaos=False)
    S.start(store, code, "me")
    ok, *_ = S.mute_typed(store, code, "me", "wires 5")
    assert not ok


# --- Gemini Blind player: a plain order is never ignored ------------------------------------
def test_ai_blind_uses_the_rules_when_gemini_does_nothing(monkeypatch):
    monkeypatch.setattr(llm, "get_client", lambda: object())
    monkeypatch.setattr(llm, "generate_json", lambda *a, **k: {"say": "Hmm?", "actions": []})
    store = hub.new_store()
    code = hub.create_room(store, "me", "Raj", "bomb", "deaf", seed=7, chaos=False)
    S.start(store, code, "me")
    S.speak(store, code, "me", "cut wire 5 now")
    b = hub.get_room(store, code)["state"]["bomb"]
    assert 4 in b["wires"]["cut"]                                 # wire 5 was cut
