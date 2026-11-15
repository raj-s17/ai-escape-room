"""
Game engine for AI Escape Room - Version 2.

Python, not the LLM, is the single source of truth:
  * the game state is a plain JSON-serialisable dictionary,
  * every action is validated here against that state and the rules in
    game_config.json,
  * puzzle solutions never leave this module (the narrator LLM only ever
    receives the *result* of an action, never the answer).

The engine is deterministic and has no network dependencies, so it can be
unit-tested on its own (see tests/test_engine.py).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("game_config.json")

VERBS = {
    "look", "examine", "take", "move", "open", "use",
    "enter_code", "inventory", "hint", "help", "meta", "unknown",
}


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class Action:
    """A structured player action produced by the parser."""
    verb: str
    obj: str | None = None       # object id from the config, if recognised
    target: str | None = None    # second object id ("use key ON drawer")
    code: str | None = None      # digits typed for enter_code
    raw_noun: str | None = None  # unrecognised noun ("use the crowbar")

    def to_dict(self) -> dict:
        return {"verb": self.verb, "object": self.obj, "target": self.target,
                "code": self.code, "raw_noun": self.raw_noun}


@dataclass
class Result:
    """Outcome of an action, decided by Python. The LLM only narrates it."""
    success: bool
    event: str                      # machine-readable outcome, e.g. "drawer_unlocked"
    facts: str                      # plain-English facts the narrator must stick to
    new_items: list[str] = field(default_factory=list)
    solved: str | None = None       # puzzle id solved by this action, if any

    def to_dict(self) -> dict:
        return {"success": self.success, "event": self.event, "facts": self.facts,
                "new_items": self.new_items, "solved": self.solved}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EscapeRoomEngine:
    def __init__(self, config: dict | None = None, state: dict | None = None):
        self.config = config or load_config()
        self.objects = self.config["objects"]
        self.state = state if state is not None else self.new_state()

    # ----- state -----------------------------------------------------------
    def new_state(self) -> dict:
        return {
            "visible": [oid for oid, o in self.objects.items() if o["visible"]],
            "inventory": [],
            "examined": [],
            "flags": {
                "painting_moved": False,
                "drawer_unlocked": False,
                "books_revealed": False,
                "door_unlocked": False,
            },
            "solved_puzzles": [],
            "code_attempts": 0,
            "rule_violations": 0,
            "escaped": False,
            "turn": 0,
            "history": [],          # compact log of every action and outcome
        }

    def reset(self) -> None:
        self.state = self.new_state()

    def public_state(self) -> dict:
        """What the narrator / UI may see. Contains no solutions."""
        s = self.state
        return {
            "visible_objects": [self.name(o) for o in s["visible"]],
            "inventory": [self.name(o) for o in s["inventory"]],
            "solved_puzzles": [self.config["puzzles"][p] for p in s["solved_puzzles"]],
            "door": "open" if s["escaped"] else "locked",
            "escaped": s["escaped"],
            "turn": s["turn"],
        }

    # ----- helpers ---------------------------------------------------------
    def name(self, oid: str) -> str:
        return self.objects[oid]["name"]

    def is_visible(self, oid: str) -> bool:
        return oid in self.state["visible"]

    def has(self, oid: str) -> bool:
        return oid in self.state["inventory"]

    def _reveal(self, *oids: str) -> list[str]:
        newly = [o for o in oids if o not in self.state["visible"]]
        self.state["visible"].extend(newly)
        return newly

    def _solve(self, puzzle: str) -> str | None:
        if puzzle in self.state["solved_puzzles"]:
            return None
        self.state["solved_puzzles"].append(puzzle)
        return puzzle

    def code_discovered(self) -> bool:
        """The player can only know the code after finding both halves of it."""
        f = self.state["flags"]
        return f["books_revealed"] and (self.has("torn_page") or "torn_page" in self.state["examined"])

    # ----- main entry point --------------------------------------------------
    def handle(self, action: Action) -> Result:
        if self.state["escaped"] and action.verb not in {"help", "inventory", "look"}:
            return Result(True, "already_escaped",
                          "The player has already escaped. The game is over; they can restart.")

        if action.verb not in VERBS:
            action = Action("unknown")

        # An object that exists in the config but has not been discovered yet
        # is treated exactly like an object that does not exist, so hidden
        # items cannot be "guessed" into existence.
        for oid in (action.obj, action.target):
            if oid is not None and (oid not in self.objects or not self.is_visible(oid)):
                if action.verb == "use" and oid == action.obj:
                    result = Result(False, "item_not_in_inventory",
                                    "The player is not carrying any such item and has not found one yet.")
                else:
                    result = Result(False, "object_not_here",
                                    "The player has not found anything like that in this room.")
                return self._record(action, result)

        handler = getattr(self, f"_do_{action.verb}")
        result = handler(action)
        return self._record(action, result)

    def _record(self, action: Action, result: Result) -> Result:
        self.state["turn"] += 1
        if result.event == "rule_violation":
            self.state["rule_violations"] += 1
        self.state["history"].append({
            "turn": self.state["turn"],
            "action": action.to_dict(),
            "event": result.event,
            "success": result.success,
        })
        return result

    # ----- verb handlers ---------------------------------------------------
    def _do_look(self, a: Action) -> Result:
        names = ", ".join(self.name(o) for o in self.state["visible"])
        return Result(True, "look",
                      f"{self.config['room_description']} Things the player has noticed so far: {names}.")

    def _do_help(self, a: Action) -> Result:
        return Result(True, "help",
                      "Commands: look around, examine <object>, take <item>, "
                      "move/look behind <object>, open <object>, use <item> on <object>, "
                      "enter <code> on the door, inventory, hint.")

    def _do_inventory(self, a: Action) -> Result:
        if not self.state["inventory"]:
            return Result(True, "inventory", "The player is not carrying anything.")
        items = ", ".join(self.name(o) for o in self.state["inventory"])
        return Result(True, "inventory", f"The player is carrying: {items}.")

    def _do_meta(self, a: Action) -> Result:
        return Result(False, "rule_violation",
                      "The player tried to change the rules, claim progress they have not made, "
                      "or obtain secret answers. This is refused. Nothing in the room changes and "
                      "no progress is granted. Stay in character and encourage them to keep exploring.")

    def _do_unknown(self, a: Action) -> Result:
        if a.raw_noun:
            return Result(False, "object_not_here",
                          f"There is no '{a.raw_noun}' in this room.")
        return Result(False, "not_understood",
                      "That action isn't possible here, or it wasn't understood. "
                      "Try examining an object in the room, or type 'help'.")

    def _do_hint(self, a: Action) -> Result:
        h, f = self.config["hints"], self.state["flags"]
        if not f["painting_moved"]:
            key = "find_key" if "note" in self.state["examined"] else "explore"
        elif not f["drawer_unlocked"]:
            key = "open_drawer" if self.has("brass_key") else "find_key"
            if key == "find_key":
                return Result(True, "hint", "Hint: something small was hidden behind the painting. Did you pick it up?")
        elif not self.has("uv_flashlight"):
            key = "get_light"
        elif not f["books_revealed"]:
            key = "reveal_numbers"
        else:
            key = "order_code"
        return Result(True, "hint", f"Hint: {h[key]}")

    def _do_examine(self, a: Action) -> Result:
        if a.obj is None:
            return self._do_look(a)
        oid, f = a.obj, self.state["flags"]
        if oid not in self.state["examined"]:
            self.state["examined"].append(oid)
        desc = self.objects[oid]["description"]
        new = []

        if oid == "painting" and f["painting_moved"]:
            desc = "The sunset painting, now set down against the wall. Its back is bare where the key was taped."
        elif oid == "drawer":
            if f["drawer_unlocked"]:
                inside = [self.name(o) for o in ("uv_flashlight", "torn_page") if not self.has(o)]
                desc = "The drawer is unlocked and open. " + (
                    f"Inside: {', '.join(inside)}." if inside else "It is now empty.")
            else:
                desc += " It is locked."
        elif oid == "bookshelf":
            new = self._reveal("season_books")
        elif oid == "season_books" and f["books_revealed"]:
            n = self.config["season_numbers"]
            desc = ("Under the UV light, a glowing number shows on the first page of each book: "
                    + ", ".join(f"{s} = {v}" for s, v in n.items()) + ".")
        elif oid == "door":
            desc += f" Code attempts so far: {self.state['code_attempts']}."
        return Result(True, f"examine_{oid}", desc, new_items=[self.name(o) for o in new])

    def _do_move(self, a: Action) -> Result:
        if a.obj == "drawer":                       # "pull the drawer"
            return self._do_open(a)
        if a.obj != "painting":
            what = self.name(a.obj) if a.obj else "that"
            return Result(False, "cannot_move", f"Moving the {what} reveals nothing new.")
        if self.state["flags"]["painting_moved"]:
            return Result(True, "already_done", "The painting has already been taken down; nothing else is behind it.")
        self.state["flags"]["painting_moved"] = True
        new = self._reveal("brass_key")
        solved = self._solve("find_key")
        return Result(True, "painting_moved",
                      "The player lifts the sunset painting off the wall. Taped to the back is a small brass key.",
                      new_items=[self.name(o) for o in new], solved=solved)

    def _do_take(self, a: Action) -> Result:
        if a.obj is None:
            return Result(False, "not_understood", "The player did not say what to take.")
        if a.obj == "painting":                     # "take the painting down"
            return self._do_move(a)
        if self.has(a.obj):
            return Result(False, "already_have", f"The player already has the {self.name(a.obj)}.")
        if not self.objects[a.obj]["takeable"]:
            return Result(False, "not_takeable", f"The {self.name(a.obj)} cannot be picked up.")
        self.state["inventory"].append(a.obj)
        return Result(True, f"took_{a.obj}", f"The player picks up the {self.name(a.obj)}.")

    def _do_open(self, a: Action) -> Result:
        if a.obj == "drawer":
            if self.state["flags"]["drawer_unlocked"]:
                return self._do_examine(Action("examine", "drawer"))
            if a.target == "brass_key" or self.has("brass_key"):
                return self._do_use(Action("use", "brass_key", "drawer"))
            return Result(False, "drawer_locked",
                          "The drawer is locked. It has a small brass keyhole; the player has no key.")
        if a.obj == "door":
            if self.state["flags"]["door_unlocked"]:
                return Result(True, "door_open", "The door is already unlocked.")
            return Result(False, "door_locked",
                          "The door is locked. It will only open when the correct 4-digit code is entered on the keypad.")
        if a.obj in ("note", "torn_page", "season_books"):
            return self._do_examine(Action("examine", a.obj))
        what = self.name(a.obj) if a.obj else "that"
        return Result(False, "cannot_open", f"The {what} cannot be opened.")

    def _do_use(self, a: Action) -> Result:
        item, target, f = a.obj, a.target, self.state["flags"]
        if item is None:
            return Result(False, "not_understood", "The player did not say what to use.")
        if self.objects[item]["takeable"] and not self.has(item):
            return Result(False, "item_not_in_inventory",
                          f"The player does not have the {self.name(item)}. They need to pick it up first.")
        if not self.objects[item]["takeable"]:
            return Result(False, "cannot_use", f"The {self.name(item)} is not something the player can use on things.")

        if item == "brass_key":
            if target in (None, "drawer", "desk"):
                if f["drawer_unlocked"]:
                    return Result(True, "already_done", "The drawer is already unlocked.")
                f["drawer_unlocked"] = True
                new = self._reveal("uv_flashlight", "torn_page")
                solved = self._solve("open_drawer")
                return Result(True, "drawer_unlocked",
                              "The brass key turns with a click and the drawer slides open. "
                              "Inside are a UV flashlight and a torn page.",
                              new_items=[self.name(o) for o in new], solved=solved)
            if target == "door":
                return Result(False, "wrong_target", "The door has no keyhole, only a keypad. The key does not help here.")
            return Result(False, "nothing_happens", f"The key does not fit the {self.name(target)}.")

        if item == "uv_flashlight":
            if target in ("season_books", "bookshelf"):
                self._reveal("season_books")
                if f["books_revealed"]:
                    return self._do_examine(Action("examine", "season_books"))
                f["books_revealed"] = True
                solved = self._solve("reveal_numbers")
                n = self.config["season_numbers"]
                return Result(True, "numbers_revealed",
                              "The violet light makes glowing numbers appear on the first page of each season book: "
                              + ", ".join(f"{s} = {v}" for s, v in n.items()) + ".", solved=solved)
            what = self.name(target) if target else "the room"
            return Result(False, "nothing_happens",
                          f"The player shines the UV flashlight at {what}. Nothing unusual glows.")

        if item in ("note", "torn_page"):
            return self._do_examine(Action("examine", item))

        what = self.name(target) if target else "anything"
        return Result(False, "nothing_happens", f"Using the {self.name(item)} on {what} does nothing.")

    def _do_enter_code(self, a: Action) -> Result:
        sol = self.config["solution"]
        if a.obj not in (None, "door"):
            return Result(False, "wrong_target",
                          f"The {self.name(a.obj)} has no keypad. Only the door accepts a code.")
        code = (a.code or "").strip()
        if not code.isdigit() or len(code) != sol["code_length"]:
            return Result(False, "invalid_code_format",
                          f"The keypad only accepts exactly {sol['code_length']} digits. Nothing happens.")

        self.state["code_attempts"] += 1
        # The code only works once the player has actually discovered it.
        # This stops brute-force guessing and codes leaked from outside the game.
        if code == sol["door_code"] and self.code_discovered():
            self.state["flags"]["door_unlocked"] = True
            self.state["escaped"] = True
            solved = self._solve("unlock_door")
            return Result(True, "escaped",
                          f"The keypad beeps and turns green. The lock clicks and the heavy door swings open. "
                          f"The player has escaped after {self.state['turn'] + 1} turns!", solved=solved)

        facts = f"The player enters {code}. The keypad flashes red and buzzes: wrong code. The door stays locked."
        if self.state["flags"]["books_revealed"] and sorted(code) == sorted(sol["door_code"]):
            facts += " The digits seem right, but maybe the order is wrong."
        elif self.state["code_attempts"] >= self.config["max_code_attempts_before_hint"]:
            facts += " After several failed attempts, the player should look for more clues in the room."
        return Result(False, "wrong_code", facts)

    # ----- convenience -----------------------------------------------------
    def snapshot(self) -> dict:
        return copy.deepcopy(self.state)
