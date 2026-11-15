"""Tests for the Version 3 point-and-click layer (no API key needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v3"))

import room_renderer as rr  # noqa: E402
from action_parser import RuleParser  # noqa: E402
from game_engine import EscapeRoomEngine, load_config  # noqa: E402

CONFIG = load_config()


def centre(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def test_click_maps_to_visible_objects():
    e = EscapeRoomEngine(CONFIG)
    assert rr.hit_test(*centre(rr.HOTSPOTS["painting"]), e.state) == "painting"
    assert rr.hit_test(*centre(rr.HOTSPOTS["door"]), e.state) == "door"
    assert rr.hit_test(5, 590, e.state) is None                      # empty floor


def test_hidden_objects_are_not_clickable():
    e = EscapeRoomEngine(CONFIG)
    # The key is hidden until the painting is moved: clicking there hits nothing.
    assert rr.hit_test(*centre(rr.HOTSPOTS["brass_key"]), e.state) is None
    # Season books are not discovered yet, so a click falls through to the bookshelf.
    assert rr.hit_test(*centre(rr.HOTSPOTS["season_books"]), e.state) == "bookshelf"


def test_items_disappear_from_room_once_taken():
    e, p = EscapeRoomEngine(CONFIG), RuleParser(CONFIG)
    e.handle(p.parse("look behind the painting"))
    assert rr.hit_test(*centre(rr.HOTSPOTS["brass_key"]), e.state) == "brass_key"
    e.handle(p.parse("take the key"))
    assert rr.hit_test(*centre(rr.HOTSPOTS["brass_key"]), e.state) is None


def test_renders_every_stage_of_the_game():
    e, p = EscapeRoomEngine(CONFIG), RuleParser(CONFIG)
    steps = ["look behind the painting", "take the key", "use the key on the drawer",
             "take the flashlight", "take the torn page", "examine the bookshelf",
             "shine the flashlight on the books", "enter 4927 on the door"]
    for step in steps:
        e.handle(p.parse(step))
        img = rr.render(e.state, "door", True, None, CONFIG["season_numbers"])
        assert img.size == (rr.W, rr.H)
    assert e.state["escaped"]
