"""
Theme: 🗝️ The Locked Library, multiplayer.

The whole crew shares one Version 2 game engine (same rules, same puzzles,
same validation). Anyone in the room can click objects or type commands;
every action is validated by the engine and then narrated by Gemini Flash
for everyone. Typed commands go through the V2 rule parser first and Gemini
Flash only when the rules don't understand them (rule-breaking never reaches it).
"""

from __future__ import annotations

import hub
import llm
from action_parser import RuleParser, llm_parse
from game_engine import Action, EscapeRoomEngine, load_config
from narrator import Narrator

SEATS = None          # no roles: everyone is an explorer
CONFIG = load_config()
NAMES = {oid: o["name"] for oid, o in CONFIG["objects"].items()}


def seat_title(seat):
    return "explorer"


def new_state(**_):
    return {"engine": EscapeRoomEngine(CONFIG), "pending": []}


def perceives(seat, ev) -> bool:
    return True


def event_view(ev, seat):
    return ev


def do_action(store, code, sid, action: Action, label: str) -> None:
    """A click or a parsed command: the engine decides now, Gemini narrates in the background."""
    with store["lock"]:
        room = hub.get_room(store, code)
        p = hub.player(room, sid)
        if p is None:
            return
        engine: EscapeRoomEngine = room["state"]["engine"]
        result = engine.handle(action)
        shown = f"{p['name']}: {label[2:]}" if label.startswith("💬") else f"{p['name']} {label}"
        hub.post(room, "action", shown, p["name"], None, event=result.event, success=result.success)
        room["state"]["pending"].append((label, result))
        if llm.get_client() is None:          # offline: narrate immediately with the engine's facts
            _narrate_pending(store, room)
    hub.kick_ai(store, code)


def do_text(store, code, sid, text: str) -> None:
    """Typed command: rule parser first (as in V2), Gemini Flash interprets anything the
    rules don't understand, the engine validates, and Gemini narrates the result for
    everyone - even a message that isn't an action gets an in-character reply.
    Rule-breaking ("meta") never reaches the parser LLM."""
    action = RuleParser(CONFIG).parse(text)
    client = llm.get_client()
    if client is not None and action.verb == "unknown" and not action.raw_noun:
        llm_action = llm_parse(client, llm.flash_model(client), text, list(CONFIG["objects"]))
        if llm_action is not None and llm_action.verb != "unknown":
            action = llm_action
    do_action(store, code, sid, action, f"💬 {text}")


def chat(store, code, sid, text: str) -> None:
    with store["lock"]:
        room = hub.get_room(store, code)
        p = hub.player(room, sid)
        if p and text.strip():
            hub.post(room, "speech", text.strip()[:300], p["name"], None)


def ai_step(store, room) -> bool:
    """Background: narrate the next engine result with Gemini Flash."""
    with store["lock"]:
        if not room["state"]["pending"]:
            return False
        room["thinking"] = ["narrator"]
    _narrate_pending(store, room)
    return True


def _narrate_pending(store, room):
    with store["lock"]:
        if not room["state"]["pending"]:
            return
        label, result = room["state"]["pending"].pop(0)
        engine = room["state"]["engine"]
        recent = [{"role": "user" if e["kind"] == "action" else "assistant", "content": e["text"]}
                  for e in room["events"][-8:] if e["kind"] in ("action", "narration")]
    client = llm.get_client()
    narrator = Narrator(engine, client, llm.flash_model(client) if client else None)
    text = narrator.narrate(label, result, recent)
    with store["lock"]:
        hub.post(room, "narration", text, "🧙 Game Master", None, guard=narrator.last_guard_triggered,
                 escaped=engine.state["escaped"])
        room["thinking"] = []


def new_round(store, code):
    with store["lock"]:
        room = hub.get_room(store, code)
        room["state"] = new_state()
        hub.post(room, "system", "🔁 A new game in the Locked Library!")
