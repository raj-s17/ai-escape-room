"""
Room hub for Version 3: multiplayer rooms for every theme.

All rooms live in one shared store (created once per server with
st.cache_resource) protected by a lock. A room has a theme ("library" or
"bomb"), players, a theme-specific game state and an event log (speech,
gestures, actions, narration, system messages). Each theme decides who may
perceive which event, so filtering happens on the server, not in the UI.

AI work (Gemini calls) runs in background threads, one worker per room, so
no player ever waits for the AI and slow replies never block the lock.
"""

from __future__ import annotations

import random
import string
import threading
import time

ROOM_TTL = 3 * 60 * 60


def new_store() -> dict:
    return {"rooms": {}, "lock": threading.RLock()}


def create_room(store, sid: str, name: str, theme: str, seat: str | None = None, **opts) -> str:
    from themes import THEMES
    with store["lock"]:
        _cleanup(store)
        code = _new_code(store)
        room = {"code": code, "theme": theme, "created_at": time.time(), "players": {},
                "events": [], "thinking": [], "ai_busy": False, "opts": opts}
        room["state"] = THEMES[theme].new_state(**opts)
        store["rooms"][code] = room
        room["players"][sid] = {"name": name, "seat": seat}
        post(room, "system", f"{name} created the room" + (f" as {THEMES[theme].seat_title(seat)}." if seat else "."))
        return code


def join_room(store, code: str, sid: str, name: str, seat: str | None = None) -> tuple[bool, str]:
    from themes import THEMES
    code = (code or "").strip().upper()
    with store["lock"]:
        room = store["rooms"].get(code)
        if room is None:
            return False, "No room with that code."
        theme = THEMES[room["theme"]]
        if theme.SEATS:
            if seat not in theme.SEATS:
                return False, "Pick a seat."
            holder = seat_holder(room, seat)
            if holder and holder != sid:
                return False, f"The {theme.seat_title(seat)} seat is already taken."
        room["players"][sid] = {"name": name, "seat": seat if theme.SEATS else None}
        post(room, "system", f"{name} joined" + (f" as {theme.seat_title(seat)}." if theme.SEATS else "."))
        return True, code


def leave_room(store, code: str, sid: str) -> None:
    with store["lock"]:
        room = store["rooms"].get(code)
        if room and sid in room["players"]:
            p = room["players"].pop(sid)
            post(room, "system", f"{p['name']} left.")


def get_room(store, code):
    return store["rooms"].get(code)


def seat_holder(room: dict, seat: str) -> str | None:
    return next((sid for sid, p in room["players"].items() if p.get("seat") == seat), None)


def player(room: dict, sid: str) -> dict | None:
    return room["players"].get(sid)


def post(room: dict, kind: str, text: str = "", by: str = "", seat: str | None = None, **meta) -> dict:
    """kind: system | speech | gesture | action | narration."""
    ev = {"i": len(room["events"]), "kind": kind, "text": text, "by": by, "seat": seat, "ts": time.time(), **meta}
    room["events"].append(ev)
    return ev


# ---------------------------------------------------------------------------
# Background AI worker
# ---------------------------------------------------------------------------
def kick_ai(store, code: str, background: bool = True) -> None:
    """Ask the room's theme to let its AI players react to new events.

    Only one worker runs per room. The theme's ai_step() does one unit of AI
    work and returns True if it did something; the worker repeats until the
    AI has nothing left to react to (or the theme's turn cap is reached).
    """
    from themes import THEMES
    with store["lock"]:
        room = store["rooms"].get(code)
        if room is None or room["ai_busy"]:
            if room is not None:
                room["ai_again"] = True
            return
        room["ai_busy"] = True
        room["ai_again"] = False

    def work():
        try:
            for _ in range(200):                       # hard safety limit
                did = THEMES[room["theme"]].ai_step(store, room)
                with store["lock"]:
                    if not did and not room.get("ai_again"):
                        break
                    room["ai_again"] = False
        finally:
            with store["lock"]:
                room["ai_busy"] = False
                room["thinking"] = []

    if background:
        threading.Thread(target=work, daemon=True).start()
    else:
        work()


# ---------------------------------------------------------------------------
def _new_code(store) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(random.choices(alphabet, k=4))
        if code not in store["rooms"]:
            return code


def _cleanup(store):
    now = time.time()
    for code in [c for c, r in store["rooms"].items() if now - r["created_at"] > ROOM_TTL]:
        del store["rooms"][code]
