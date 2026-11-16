"""
Theme: 💣 Bomb Squad - a co-op defusal game where each player is missing a sense.

    🕶️ BLIND - holds the tools; can't see the bomb (feels it: wire slots,
               D-pad, unlabeled keys, switch positions, Braille).
    🎧 DEAF  - sees the whole bomb and the hand signals; can't hear anyone.
    🤐 MUTE  - has the manual and hears everything; can't speak, only signal.

The senses force the chain used by co-op games like BOMBANANA:
    Deaf calls out a module -> Mute finds the rule and signals the answer ->
    Deaf sees the signal and tells Blind -> Blind repeats it back and acts.

Python enforces every sense: perceives() decides which events each seat gets
(on screen AND in its AI prompt), only Blind can touch the bomb, only Mute
signals, Mute can't speak. Chaos events (power cut, radio static) are applied
the same way. Empty seats are played by Gemini Flash; without an API key a
rule-based fallback plays them.
"""

from __future__ import annotations

import hashlib
import re

import hub
import llm
from defuse_core import bomb4 as B
from defuse_core.squad_manual import (DIRECTIONS, DPAD_LEDS, MANUAL_TEXT, NUMPAD_LEDS, SWITCH_LIGHTS,
                                      WIRE_COLOURS, WIRE_LEDS)

SEATS = {
    "blind": {"icon": "🕶️", "title": "Blind", "colour": "#f28c28", "see": False, "hear": True, "speak": True,
              "can": "holds the tools and feels the bomb", "cannot": "can't see the bomb or hand signals"},
    "deaf": {"icon": "🎧", "title": "Deaf", "colour": "#2bb3a3", "see": True, "hear": False, "speak": True,
             "can": "sees the whole bomb and the hand signals", "cannot": "can't hear anyone"},
    "mute": {"icon": "🤐", "title": "Mute", "colour": "#8e6ad8", "see": False, "hear": True, "speak": False,
             "can": "has the manual and hears everything", "cannot": "can't speak (hand signals only), can't see the bomb"},
}
AI_TURN_CAP = 140
MODULE_TITLES = {"wires": "✂️ Wires", "dpad": "🎮 D-pad", "numpad": "🔢 Maths keypad", "switches": "🎚️ Switches"}

GESTURES = {
    "m_wires": ("✂️", "wires"), "m_dpad": ("🎮", "D-pad"), "m_numpad": ("🔢", "keypad"),
    "m_switches": ("🎚️", "switches"),
    "up": ("⬆️", "up"), "down": ("⬇️", "down"), "left": ("⬅️", "left"), "right": ("➡️", "right"),
    "yes": ("👍", "yes"), "no": ("👎", "no"), "wait": ("✋", "wait"), "repeat": ("🔁", "say again"),
    "back": ("↩️", "go back"),
    **{f"n{i}": (f"{i}️⃣", str(i)) for i in range(10)},
}


def seat_title(seat):
    return "spectator" if seat is None else f"{SEATS[seat]['icon']} {SEATS[seat]['title']}"


def new_state(seed=None, seconds=B.DEFAULT_SECONDS, chaos=True, **_):
    return {"bomb": B.new_bomb(seed=seed, seconds=seconds, chaos=chaos), "seconds": seconds, "chaos": chaos,
            "round": 1, "ai_seen": {s: -1 for s in SEATS}, "ai_turns": 0, "mute_last": None,
            "chaos_announced": []}


def crew_problem(room) -> str | None:
    if not any(p["seat"] in SEATS for p in room["players"].values()) and not room["opts"].get("watch"):
        return "Nobody has a seat yet."
    return None


# ---------------------------------------------------------------------------
# Perception
# ---------------------------------------------------------------------------
def perceives(seat, ev) -> bool:
    if seat is None or ev["kind"] in ("system", "action"):
        return True
    if ev.get("seat") == seat:
        return True
    if ev["kind"] == "speech":
        return SEATS[seat]["hear"]
    if ev["kind"] == "gesture":
        if seat == "deaf" and ev.get("dark"):
            return False                          # signalled during a power cut: nobody saw it
        return seat in ("deaf", "mute")
    return False


def garble(text: str, salt: str) -> str:
    """Radio static: deterministically replace most letters with noise."""
    out = []
    for i, ch in enumerate(text):
        h = int(hashlib.md5(f"{salt}{i}".encode()).hexdigest(), 16)
        out.append(ch if not ch.isalnum() or h % 10 < 3 else "*#~%"[h % 4])
    return "".join(out)


def event_view(ev, seat):
    if perceives(seat, ev):
        if ev["kind"] == "gesture":
            return {**ev, "text": gesture_text(ev["tokens"])}
        if ev["kind"] == "speech" and ev.get("static") and ev.get("seat") != seat and seat is not None:
            return {**ev, "text": "📻 " + garble(ev["text"], str(ev["i"])), "garbled": True}
        return ev
    if ev["kind"] == "speech" and seat == "deaf":
        return {**ev, "text": "🔇 *…is talking - you can't hear it.*", "muffled": True}
    return None


def gesture_text(tokens):
    return "  ".join(f"{GESTURES[t][0]} {GESTURES[t][1]}" for t in tokens if t in GESTURES)


# ---------------------------------------------------------------------------
# Callouts (what the Deaf player can say about what they see)
# ---------------------------------------------------------------------------
def key_position_words(p: int) -> str:
    row = "top" if p < 5 else "bottom"
    col = p % 5 + 1
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(col, "th")
    return f"{row} row, {col}{suffix} from your left"


def callout(b, module: str) -> str:
    if module == "wires":
        w = b["wires"]
        return (f"Wires: {len(w['colours'])} wires, left to right: {', '.join(w['colours'])}. "
                f"LED {w['led']}.")
    if module == "dpad":
        d = b["dpad"]
        if d["braille"]:
            return f"D-pad: LED {d['led']}, centre is Braille - Blind, feel it!"
        return f"D-pad: LED {d['led']}, centre {d['value']}."
    if module == "numpad":
        s = b["numpad"]
        return f"Keypad sum: {s['a']} {s['op']} {s['b']}. LED {s['led']}."
    sw = b["switches"]
    return (f"Switches: lights {', '.join(sw['lights'])}. Digits {' '.join(map(str, sw['digits']))}.")


def callout_all(b) -> str:
    return " ".join(callout(b, m) for m in B.MODULES if not b["solved"][m])


def touch_view(b) -> dict:
    """What the Blind player can feel."""
    d = b["dpad"]
    return {"wire_slots": len(b["wires"]["colours"]), "cut": [i + 1 for i in b["wires"]["cut"]],
            "braille": d["value"] if d["braille"] else None,
            "switches": ["up" if u else "down" for u in b["switches"]["up"]],
            "solved": [m for m, ok in b["solved"].items() if ok]}


def status_line(b):
    B.refresh(b)
    return (f"status={b['status']}, time left={int(B.time_left(b))}s, strikes={b['strikes']}/3, "
            f"defused={[m for m, ok in b['solved'].items() if ok] or 'none'}")


# ---------------------------------------------------------------------------
# Player actions (validated here, whatever the UI shows)
# ---------------------------------------------------------------------------
def start(store, code, sid) -> str:
    with store["lock"]:
        room = hub.get_room(store, code)
        if hub.player(room, sid) is None:
            return "not in room"
        result = B.start(room["state"]["bomb"])
        if result == "started":
            hub.post(room, "system", "⏱️ The timer is running!", start=True)
    hub.kick_ai(store, code)
    return result


def speak(store, code, sid, text) -> tuple[bool, str]:
    text = (text or "").strip()[:300]
    with store["lock"]:
        room = hub.get_room(store, code)
        p = hub.player(room, sid)
        if p is None or not text:
            return False, "Nothing to say."
        if p["seat"] is None:
            return False, "Spectators can't talk to the crew."
        if not SEATS[p["seat"]]["speak"]:
            return False, "🤐 You can't speak - use hand signals!"
        _post_speech(room, text, p["name"], p["seat"])
    hub.kick_ai(store, code)
    return True, ""


def _post_speech(room, text, by, seat, **meta):
    static = B.chaos_now(room["state"]["bomb"]) == "static"
    hub.post(room, "speech", text, by, seat, static=static, **meta)


def signal(store, code, sid, tokens) -> tuple[bool, str]:
    tokens = [t for t in tokens if t in GESTURES][:8]
    with store["lock"]:
        room = hub.get_room(store, code)
        p = hub.player(room, sid)
        if p is None or p["seat"] != "mute":
            return False, "Only the Mute player uses hand signals."
        if not tokens:
            return False, "Pick some signals first."
        _post_signal(room, tokens, p["name"])
    hub.kick_ai(store, code)
    return True, ""


_SIGN_WORDS = {
    "wires": "m_wires", "wire": "m_wires", "dpad": "m_dpad", "pad": "m_dpad", "arrows": "m_dpad",
    "keypad": "m_numpad", "keys": "m_numpad", "key": "m_numpad", "numpad": "m_numpad", "maths": "m_numpad",
    "math": "m_numpad", "switches": "m_switches", "switch": "m_switches",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "yes": "yes", "yeah": "yes", "yep": "yes", "correct": "yes", "ok": "yes", "okay": "yes",
    "no": "no", "nope": "no", "wrong": "no", "wait": "wait", "stop": "wait", "hold": "wait",
    "repeat": "repeat", "again": "repeat", "back": "back", "undo": "back",
    **{w: f"n{i}" for i, w in enumerate("zero one two three four five six seven eight nine".split())},
}
_SIGN_FILLER = set("the a an to is it and then please now cut press flip set turn signal sign show "
                   "go say number from your my on of in".split())


def parse_signal_text(text: str) -> tuple[list[str], list[str]]:
    """Typed words -> hand-signal tokens (the Mute player can't speak, so typing signs).
    Returns (tokens, words that aren't signs)."""
    t = text.lower().replace("d-pad", "dpad").replace("d pad", "dpad")
    t = t.replace("say again", "repeat").replace("go back", "back")
    tokens, unknown = [], []
    for w in re.findall(r"[a-z]+|\d", t):
        if w.isdigit():
            tokens.append(f"n{w}")
        elif w in _SIGN_WORDS:
            tokens.append(_SIGN_WORDS[w])
        elif w not in _SIGN_FILLER:
            unknown.append(w)
    return tokens[:8], unknown


def mute_typed(store, code, sid, text) -> tuple[bool, str, list[str], list[str]]:
    """The Mute player typed: sign it (validated like the signal buttons).
    Returns (ok, error, tokens, unknown words)."""
    tokens, unknown = parse_signal_text(text)
    if not tokens:
        return False, "No hand signals in that.", tokens, unknown
    ok, err = signal(store, code, sid, tokens)
    return ok, err, tokens, unknown


def _post_signal(room, tokens, by, **meta):
    dark = B.chaos_now(room["state"]["bomb"]) == "power"
    hub.post(room, "gesture", "", by, "mute", tokens=tokens, dark=dark, **meta)


def touch(store, code, sid, kind, value=None) -> str:
    """kind: cut | dpad | key | flip | enter."""
    with store["lock"]:
        room = hub.get_room(store, code)
        p = hub.player(room, sid)
        if p is None or p["seat"] != "blind":
            return "only the Blind player holds the tools"
        result = _apply_touch(room, p["name"], kind, value)
    hub.kick_ai(store, code)
    return result


def _apply_touch(room, actor, kind, value) -> str:
    b = room["state"]["bomb"]
    if kind == "cut":
        result, what, module = B.cut_wire(b, int(value)), f"✂️ snip - {actor} cut wire {value}", "wires"
    elif kind == "dpad":
        result, what, module = B.press_dpad(b, value), f"🎮 {actor} pressed D-pad {value}", "dpad"
    elif kind == "key":
        result, what, module = B.press_key(b, int(value)), f"🔢 {actor} pressed a key ({key_position_words(int(value))})", "numpad"
    elif kind == "flip":
        result, what, module = B.flip_switch(b, int(value)), f"🎚️ {actor} flipped switch {int(value) + 1}", "switches"
    elif kind == "enter":
        result, what, module = B.press_enter(b), f"⏎ {actor} pressed ENTER", "switches"
    else:
        return "invalid"
    if result == "not_started":
        hub.post(room, "system", "Nothing happens - start the timer first.")
    elif result not in ("invalid", "game_over", "already_solved"):
        hub.post(room, "action", f"{what}. {B.RESULT_TEXT.get(result, '')}".strip(), actor, "blind",
                 result=result, module=module)
    return result


def new_round(store, code):
    with store["lock"]:
        room = hub.get_room(store, code)
        st = room["state"]
        st["bomb"] = B.new_bomb(seconds=st["seconds"], chaos=st["chaos"])
        st["round"] += 1
        st.update(ai_turns=0, mute_last=None, chaos_announced=[])
        st["ai_seen"] = {s: len(room["events"]) for s in SEATS}
        hub.post(room, "system", f"🔁 Round {st['round']}: a new bomb!")


def tick(store, code):
    """Called by the UI every second: timer, chaos announcements, wake the AI."""
    with store["lock"]:
        room = hub.get_room(store, code)
        if room is None:
            return
        st, b = room["state"], room["state"]["bomb"]
        B.refresh(b)
        for i, ev in enumerate(b["chaos"]):
            t = B.elapsed(b)
            if b["status"] == "armed" and ev["at"] <= t and (i, "on") not in st["chaos_announced"]:
                st["chaos_announced"].append((i, "on"))
                hub.post(room, "system", "⚡ POWER CUT! The Deaf player can't see anything." if ev["kind"] == "power"
                         else "📻 RADIO STATIC! Speech is garbled.", chaos=ev["kind"])
            if b["status"] == "armed" and t >= ev["at"] + B.CHAOS_LENGTH and (i, "off") not in st["chaos_announced"]:
                st["chaos_announced"].append((i, "off"))
                hub.post(room, "system", "💡 Power is back." if ev["kind"] == "power" else "📻 The static clears.",
                         chaos_end=ev["kind"])
    hub.kick_ai(store, code)


# ---------------------------------------------------------------------------
# AI players
# ---------------------------------------------------------------------------
def _is_trigger(seat, e) -> bool:
    if seat == "deaf":
        return e["kind"] == "gesture" or e.get("start") or e.get("chaos_end") == "static"
    if seat == "mute":
        return e["kind"] == "speech" or (e["kind"] == "action" and e.get("result") in ("solved", "strike", "progress")) \
            or e.get("chaos_end") == "power"
    return e["kind"] == "speech"                     # blind


def ai_step(store, room) -> bool:
    with store["lock"]:
        st, b = room["state"], room["state"]["bomb"]
        B.refresh(b)
        if st["ai_turns"] >= AI_TURN_CAP or b["status"] != "armed":
            return False
        power_cut = B.chaos_now(b) == "power"
        for seat in ("deaf", "blind", "mute"):
            if hub.seat_holder(room, seat) is not None:
                continue
            if seat == "deaf" and power_cut:
                continue                              # can't see a thing: react when the light is back
            seen = st["ai_seen"][seat]
            new = [e for e in room["events"][seen + 1:]
                   if e.get("seat") != seat and perceives(seat, e) and _is_trigger(seat, e)]
            st["ai_seen"][seat] = len(room["events"]) - 1
            if not new:
                continue
            st["ai_turns"] += 1
            room["thinking"] = [seat]
            heard = [e for e in room["events"] if perceives(seat, e)][-30:]
            snapshot = _snapshot(b)
            break
        else:
            return False
    client = llm.get_client()
    try:
        {"deaf": _deaf_turn, "mute": _mute_turn, "blind": _blind_turn}[seat](store, room, snapshot, heard, new, client)
    finally:
        with store["lock"]:
            room["thinking"] = []
    return True


def _snapshot(b):
    import copy
    return copy.deepcopy(b)


def _log_text(events, seat):
    lines = []
    for e in events:
        v = event_view(e, seat)
        if v is None or v.get("muffled"):
            continue
        who = SEATS[e["seat"]]["title"] if e.get("seat") in SEATS else "sound"
        lines.append(f"[{e['kind']}] {who}: {v['text']}")
    return "\n".join(lines) or "(nothing yet)"


def _ai_name(seat):
    return f"{SEATS[seat]['icon']} {SEATS[seat]['title']} (AI)"


# --- Deaf ------------------------------------------------------------------------
DEAF_PROMPT = """You are the DEAF member of a bomb squad. You SEE the whole bomb and the Mute player's hand
signals, but you CANNOT hear. You have NO manual. The Mute player (manual) signals the answers; the
BLIND player holds the tools and only hears you. Turn the newest signals into ONE short, exact spoken
instruction for the Blind player, always from the Blind player's point of view:
- wires: "Cut wire N (from your left)!"
- D-pad: "Press D-pad up/down/left/right!"
- keypad: signals give a DIGIT; tell the Blind player WHERE that digit is: "Press the key in the
  top/bottom row, Nth from your left!"
- switches: "Switches, left to right: up, down, ... - then ENTER!"
- a module card with "say again" means: call that module out again (exact callout below).
Exact callouts you can use: {callouts}
Reply ONLY with JSON: {{"say": "<max 2 short sentences>"}}"""


def _deaf_turn(store, room, b, heard, new, client):
    if any(e.get("start") for e in new):
        say = "Here's the bomb. " + callout_all(b)
        if client is not None:
            try:
                intro = llm.generate(client, "In at most 8 words, say a tense line as a bomb-squad member "
                                     "about to describe a bomb to the team. Do NOT give any instruction and do "
                                     "not mention wires, colours, numbers, buttons or switches.",
                                     temperature=0.9, max_tokens=30).strip().strip('"')
                # Flavour only: drop it if it still sounds like an order the Blind player might follow.
                if intro and not re.search(r"\b(cut|press|flip|turn|push|enter|wire|red|blue|green|white|black|"
                                           r"yellow|switch|key|button|\d)", intro, re.I):
                    say = f"{intro} {callout_all(b)}"
            except Exception:
                pass
    elif any(e.get("chaos_end") == "static" for e in new):
        last = next((e["text"] for e in reversed(room["events"]) if e["kind"] == "speech" and e.get("seat") == "deaf"), "")
        say = f"Static's gone - again: {last}" if last else ""
    else:
        signals = [e for e in new if e["kind"] == "gesture"]
        say = None
        if client is not None and signals:
            try:
                prompt = (f"WHAT YOU SEE: {_deaf_view(b)}\nSTATUS: {status_line(b)}\n"
                          f"NEW SIGNALS: {[gesture_text(e['tokens']) for e in signals]}\nWhat do you say?")
                data = llm.generate_json(client, prompt, DEAF_PROMPT.format(
                    callouts=" | ".join(callout(b, m) for m in B.MODULES)))
                say = str(data.get("say", "")).strip()[:300] or None
            except Exception:
                say = None
        if say is None:
            say = " ".join(filter(None, (offline_deaf_translate(e["tokens"], b) for e in signals)))
    if say:
        with store["lock"]:
            _post_speech(room, say, _ai_name("deaf"), "deaf", ai=True)


def _deaf_view(b):
    s, sw = b["numpad"], b["switches"]
    return {"wires_left_to_right": b["wires"]["colours"], "wire_led": b["wires"]["led"],
            "cut_wires": [i + 1 for i in b["wires"]["cut"]],
            "dpad": {"led": b["dpad"]["led"], "centre": "Braille (you can't read it)" if b["dpad"]["braille"]
                     else b["dpad"]["value"], "stage": f"{b['dpad']['stage'] + 1}/{B.DPAD_STAGES}"},
            "keypad": {"sum": f"{s['a']} {s['op']} {s['b']}", "led": s["led"],
                       "digit_positions": {d: key_position_words(p) for p, d in enumerate(s["layout"])}},
            "switches": {"lights": sw["lights"], "digits": sw["digits"],
                         "current": ["up" if u else "down" for u in sw["up"]]},
            "solved": b["solved"]}


def offline_deaf_translate(tokens, b) -> str:
    nums = [int(t[1]) for t in tokens if re.fullmatch(r"n\d", t)]
    dirs = [t for t in tokens if t in DIRECTIONS]
    module = next((t[2:] for t in tokens if t.startswith("m_")), None)
    if "repeat" in tokens:
        return callout(b, module) if module else callout_all(b)
    if module == "wires" and nums:
        return f"Cut wire {nums[0]} (from your left)!"
    if module == "dpad" and dirs:
        return f"Press D-pad {dirs[0]}!"
    if module == "numpad" and nums:
        p = b["numpad"]["layout"].index(nums[0])
        return f"Press the key in the {key_position_words(p)}!"
    if module == "switches" and len([d for d in dirs if d in ("up", "down")]) == 5:
        return "Switches, left to right: " + ", ".join(d for d in dirs if d in ("up", "down")) + " - then ENTER!"
    for t, word in (("yes", "Yes!"), ("no", "No!"), ("wait", "Wait!"), ("back", "Go back!")):
        if t in tokens:
            return word
    return ""


# --- Mute ------------------------------------------------------------------------
MUTE_PROMPT = """You are the MUTE member of a bomb squad. You have the manual and you can HEAR the team,
but you CANNOT speak and CANNOT see the bomb. You answer only with hand-signal tokens:
m_wires, m_dpad, m_numpad, m_switches (which module), up, down, left, right, n0..n9 (numbers),
yes, no, wait, repeat (say again), back (go back).
Examples: ["m_wires","n3"] = cut wire 3.  ["m_dpad","left"].  ["m_numpad","n7"] = press digit 7.
["m_switches","up","down","down","up","down"] = switch states left to right.
["m_dpad","repeat"] = "call the D-pad out again" (do this after any D-pad press: it changes).
Work on ONE unsolved module at a time, using only details you actually heard. If you need the Blind
player to read Braille, send [] and wait. Reply ONLY with JSON: {"signals": [...]}.

""" + MANUAL_TEXT


def _mute_turn(store, room, b, heard, new, client):
    if any(e.get("chaos_end") == "power" for e in new):
        with store["lock"]:
            room["state"]["mute_last"] = None      # the Deaf player missed it in the dark: signal again
    tokens = None
    if client is not None:
        try:
            prompt = (f"WHAT YOU HEARD (oldest first):\n{_log_text(heard, 'mute')}\n\nSTATUS: {status_line(b)}\n"
                      "Which signals do you make now?")
            data = llm.generate_json(client, prompt, MUTE_PROMPT)
            tokens = [t for t in data.get("signals", []) if t in GESTURES][:8]
        except Exception:
            tokens = None
    if not tokens:
        # No reply, or Gemini chose to sign nothing: use the manual rules. They only return
        # nothing when the team really has to wait (e.g. for the Braille), so the game can't stall.
        tokens = offline_mute_solve(heard, b["solved"])
    with store["lock"]:
        st = room["state"]
        key = (tuple(tokens), b["strikes"], tuple(b["solved"].values()), b["dpad"]["rolls"])
        if not tokens or key == st["mute_last"]:
            return
        st["mute_last"] = key
        _post_signal(room, tokens, _ai_name("mute"), ai=True)


def heard_knowledge(events) -> dict:
    """What the Mute player has learned from (un-garbled) speech, in time order.
    Understands the Deaf player's callout buttons exactly, and everyday typed
    descriptions ("5 wires: green black red red white, the light is red")."""
    k = {}
    for e in events:
        if e["kind"] == "action" and e.get("module") == "dpad":
            k.pop("dpad", None)                    # the D-pad changes after every press
        if e["kind"] != "speech" or e.get("static"):
            continue
        t = e["text"]
        exact = set()
        if m := re.search(r"Wires: \d wires, left to right: ([a-z, ]+)\. LED (\w+)", t):
            k["wires"] = {"colours": [c.strip() for c in m.group(1).split(",")], "led": m.group(2)}
            exact.add("wires")
        if m := re.search(r"D-pad: LED (\w+), centre (\d|is Braille)", t):
            k["dpad"] = {"led": m.group(1), "value": int(m.group(2)) if m.group(2).isdigit() else None}
            exact.add("dpad")
        if m := re.search(r"Keypad sum: (\d+) ([+\-×]) (\d+)\. LED (\w+)", t):
            k["numpad"] = {"a": int(m.group(1)), "op": m.group(2), "b": int(m.group(3)), "led": m.group(4)}
            exact.add("numpad")
        if m := re.search(r"Switches: lights ([a-z, ]+)\. Digits ([\d ]+)", t):
            k["switches"] = {"lights": [c.strip() for c in m.group(1).split(",")],
                             "digits": [int(x) for x in m.group(2).split()]}
            exact.add("switches")
        for module, info in describe_free_text(t).items():
            if module not in exact:
                k[module] = info
        if (m := re.search(r"braille\W+(?:says|reads|is|shows|=)?\W*(\d)", t, re.I)) and "dpad" in k:
            k["dpad"]["value"] = int(m.group(1))
    return k


# --- everyday descriptions typed by a human Deaf player ------------------------------
_MODULE_WORDS = {
    "wires": r"\bwires?\b",
    "dpad": r"\bd-?\s?pad\b|\bdpad\b|\barrows?\b|\bdirection pad\b",
    "numpad": r"\bkeypad\b|\bsum\b|\bmaths?\b|\bequation\b|\bcalculation\b|\bnumber pad\b",
    "switches": r"\bswitch(?:es)?\b",
}
_LED = r"\b(?:led|light|lamp|bulb|indicator)s?\b"
_OPS = {"+": "+", "plus": "+", "-": "-", "−": "-", "minus": "-", "x": "×", "×": "×", "*": "×",
        "times": "×", "multiplied by": "×"}


def _segments(t: str) -> dict:
    """Split a message into the parts that talk about each module."""
    hits = sorted((m.start(), mod) for mod, rx in _MODULE_WORDS.items() for m in re.finditer(rx, t))
    out = {}
    for i, (pos, mod) in enumerate(hits):
        if i and hits[i - 1][1] == mod:
            continue                       # same module mentioned again ("Wires: 5 wires"): already covered
        end = next((p for p, m2 in hits[i + 1:] if m2 != mod), len(t))
        out[mod] = out.get(mod, "") + " " + t[pos:end]
    return out


def _led(seg: str, allowed: list[str]) -> tuple[str | None, str]:
    """Find the light colour ("LED red", "the light is off", "red LED", "no light") and
    return it with the text that's left (so the LED colour isn't read as a wire)."""
    if m := re.search(r"\bno\s+(?:led|light|lamp)\b|" + _LED + r"\s+(?:is\s+)?(?:off|out|dark)\b", seg):
        return ("off" if "off" in allowed else None), seg[:m.start()] + seg[m.end():]
    colours = "|".join(c for c in allowed if c != "off")
    for rx in (_LED + r"(?:\s+(?:is|=|shows|colou?r|is\s+lit))*\W*(" + colours + r")\b",
               r"\b(" + colours + r")\s+(?:led|light|lamp|bulb)\b"):
        if m := re.search(rx, seg):
            return m.group(1), seg[:m.start()] + seg[m.end():]
    return None, seg


def describe_free_text(text: str) -> dict:
    """Read a free-form description into the same facts the callout buttons give."""
    t = text.lower().replace("colour", "color")
    k = {}
    for mod, seg in _segments(t).items():
        if mod == "wires":
            led, rest = _led(seg, WIRE_LEDS)
            colours = re.findall(r"\b(" + "|".join(WIRE_COLOURS) + r")\b", rest)
            if 3 <= len(colours) <= 6:
                k["wires"] = {"colours": colours, "led": led}
        elif mod == "dpad":
            led, rest = _led(seg, DPAD_LEDS)
            if "braille" in rest:
                value = None
            elif m := re.search(r"\b(?:centre|center|middle|number|shows?|says|display\w*)\b\D{0,15}?(\d)\b", rest) \
                    or re.search(r"\b(\d)\b", rest):
                value = int(m.group(1))
            else:
                continue
            if led:
                k["dpad"] = {"led": led, "value": value}
        elif mod == "numpad":
            m = re.search(r"(\d+)\s*(\+|plus|-|−|minus|x|×|\*|times|multiplied by)\s*(\d+)", seg)
            if m:
                led, _ = _led(seg[:m.start()] + seg[m.end():], NUMPAD_LEDS)
                k["numpad"] = {"a": int(m.group(1)), "op": _OPS[m.group(2)], "b": int(m.group(3)), "led": led}
        else:
            lights = re.findall(r"\b(" + "|".join(SWITCH_LIGHTS) + r")\b", seg)
            digits = [int(d) for d in re.findall(r"\d", seg)]
            if len(lights) == 5 and len(digits) == 5:
                k["switches"] = {"lights": lights, "digits": digits}
    return k


def offline_mute_solve(events, solved) -> list[str]:
    """Apply the manual to what was heard - the reasoning a human Mute player does."""
    k = heard_knowledge(events)
    for module in B.MODULES:
        if solved[module]:
            continue
        if module not in k:
            return [f"m_{module}", "repeat"]
        info = k[module]
        if info.get("led", "") is None:
            return [f"m_{module}", "repeat"]       # heard the module, but not its light colour
        if module == "wires":
            return ["m_wires", f"n{B.correct_wire(info) + 1}"]
        if module == "dpad":
            if info["value"] is None:
                return []                          # waiting for the Blind player to read the Braille
            return ["m_dpad", B.correct_direction(info["led"], info["value"])]
        if module == "numpad":
            return ["m_numpad", f"n{B.correct_digit(B.sum_result(info), info['led'])}"]
        targets = B.switch_targets(info["lights"], info["digits"])
        return ["m_switches"] + ["up" if t else "down" for t in targets]
    return []


# --- Blind -----------------------------------------------------------------------
BLIND_PROMPT = """You are the BLIND member of a bomb squad. You hold the tools but CANNOT see; you can hear.
You can feel: wire slots (numbered from YOUR left), a D-pad (up/down/left/right) whose centre may be in
Braille (you can read it by touch), a keypad of 10 unlabeled keys in two rows of five (top/bottom row,
column 1-5 from your left), five switches (you feel whether each is up or down) and an ENTER button.
Only act on a clear instruction from a teammate; repeat it back in "say". Never guess.
If the Deaf player asks you to feel the Braille, say "The Braille says N." with the number you feel.
Reply ONLY with JSON: {"say": "<short>", "actions": [...]} with actions from:
{"do":"cut","wire":N} {"do":"dpad","dir":"up|down|left|right"} {"do":"key","row":"top|bottom","col":1-5}
{"do":"switches","states":["up"|"down" x5]} {"do":"enter"}"""


def _blind_turn(store, room, b, heard, new, client):
    instructions = " ".join(e["text"] for e in new if e["kind"] == "speech" and not e.get("static"))
    touch_info = touch_view(b)
    actions, say = None, ""
    if client is not None and instructions:
        try:
            prompt = (f"WHAT YOU FEEL: {touch_info}\nSTATUS: {status_line(b)}\n"
                      f"RECENTLY HEARD:\n{_log_text(heard, 'blind')}\n\nNEW: {instructions}\nWhat do you do?")
            data = llm.generate_json(client, prompt, BLIND_PROMPT)
            actions = validate_blind_actions(data.get("actions", []), b)
            say = str(data.get("say", "")).strip()[:200]
        except Exception:
            actions = None
        if actions == [] and parse_blind_instructions(instructions, b):
            actions = None          # Gemini did nothing, but the order is plain ("cut wire 5"): use the rules
    if actions is None:
        actions = parse_blind_instructions(instructions, b)
        say = ""
        if "braille" in instructions.lower() and touch_info["braille"] is not None and not b["solved"]["dpad"]:
            say = f"The Braille says {touch_info['braille']}."
        elif actions:
            say = "Repeating back: " + "; ".join(_action_words(a) for a in actions) + ". Doing it!"
    with store["lock"]:
        if say:
            _post_speech(room, say, _ai_name("blind"), "blind", ai=True)
        for kind, value in actions:
            if room["state"]["bomb"]["status"] != "armed":
                break
            result = _apply_touch(room, _ai_name("blind"), kind, value)
            if result in ("strike", "exploded"):
                break


def _action_words(a):
    kind, v = a
    return {"cut": lambda: f"cut wire {v}", "dpad": lambda: f"D-pad {v}",
            "key": lambda: f"key {key_position_words(v)}", "flip": lambda: f"flip switch {v + 1}",
            "enter": lambda: "ENTER"}[kind]()


def _switch_actions(b, states):
    acts = [("flip", i) for i, want in enumerate(states) if b["switches"]["up"][i] != (want == "up")]
    return acts + [("enter", None)]


def validate_blind_actions(raw, b) -> list[tuple]:
    out = []
    for a in raw if isinstance(raw, list) else []:
        do = a.get("do") if isinstance(a, dict) else None
        if do == "cut" and isinstance(a.get("wire"), int) and 1 <= a["wire"] <= len(b["wires"]["colours"]):
            out.append(("cut", a["wire"]))
        elif do == "dpad" and a.get("dir") in DIRECTIONS:
            out.append(("dpad", a["dir"]))
        elif do == "key" and a.get("row") in ("top", "bottom") and isinstance(a.get("col"), int) and 1 <= a["col"] <= 5:
            out.append(("key", (0 if a["row"] == "top" else 5) + a["col"] - 1))
        elif do == "switches" and isinstance(a.get("states"), list) and len(a["states"]) == 5 \
                and all(s in ("up", "down") for s in a["states"]):
            out += _switch_actions(b, a["states"])[:-1]
        elif do == "enter":
            out.append(("enter", None))
    return out[:10]


_NUM_WORDS = {w: i + 1 for i, w in enumerate(
    "one two three four five six seven eight nine ten".split())}
_NUM_WORDS.update({w: i + 1 for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth".split())})
_NUM = r"(\d+|" + "|".join(_NUM_WORDS) + r")(?:st|nd|rd|th)?"
_NEGATED = re.compile(r"\b(?:don'?t|do not|never|not|no)\s+(?:\w+\s+){0,2}$")


def _num(s: str) -> int:
    return int(s) if s.isdigit() else _NUM_WORDS[s]


def _clauses(t: str) -> list[str]:
    """Split into instructions ("cut wire 2, then press up") and drop negated ones
    ("don't cut wire 1") so a warning is never acted on."""
    parts = re.split(r"[.;!?]|,?\s*\b(?:then|and then|after that|next)\b|,\s*(?=(?:cut|snip|press|push|hit|"
                     r"tap|flip|set|go|now)\b)", t)
    keep = []
    for p in (x.strip() for x in parts if x and x.strip()):
        verb = re.search(r"\b(cut|cutting|snip|clip|sever|press|push|hit|tap|flip|toggle|set|go)\w*", p)
        if verb and _NEGATED.search(p[:verb.start()]):
            continue
        keep.append(p)
    return keep


def parse_blind_instructions(text, b) -> list[tuple]:
    """Rule-based reading of spoken instructions into tool actions, used by the AI Blind
    player without Gemini and for what a human Blind player types. Accepts everyday
    phrasing: "cutting wire 1", "cut the first wire", "snip wire one", "cut 3",
    "press up" / "d pad up", "top row key 2", "flip switch 4", "hit enter", and the
    Deaf callouts ("Switches, left to right: up, down, ... - then ENTER!")."""
    t = text.lower().replace("d-pad", "dpad").replace("d pad", "dpad")
    out = []
    if m := re.search(r"switches,? left to right:? ((?:up|down)(?:,? (?:up|down)){4})", t):
        return _switch_actions(b, re.findall(r"up|down", m.group(1)))
    for c in _clauses(t):
        if re.search(r"\b(cut|cutting|snip|snipping|clip|sever)\w*", c):
            m = (re.search(r"\bwires?\s*(?:number|no\.?|#)?\s*" + _NUM, c)
                 or re.search(_NUM + r"\s+wire", c)
                 or re.search(r"\b(?:cut|cutting|snip|snipping|clip|sever)\w*\s+(?:the\s+)?(?:number\s+)?" + _NUM + r"\b", c))
            if m:
                out.append(("cut", _num(m.group(1))))
            continue
        if m := re.search(r"\b(top|bottom|upper|lower)\s+row\W+(?:the\s+)?(?:key|button|one)?\s*(?:number\s*)?" + _NUM, c) \
                or re.search(_NUM + r"\s+(?:key|button)\s+(?:on|in|of)\s+the\s+(top|bottom|upper|lower)\s+row", c):
            row, n = (m.group(1), m.group(2)) if m.group(1) in ("top", "bottom", "upper", "lower") else (m.group(2), m.group(1))
            col = _num(n)
            if 1 <= col <= 5:
                out.append(("key", (0 if row in ("top", "upper") else 5) + col - 1))
            continue
        if m := re.search(r"\b(?:dpad|press|push|hit|tap|go|arrow)\b\W*(?:the\s+)?(?:dpad\s+)?(up|down|left|right)\b", c) \
                or re.search(r"\b(up|down|left|right)\s+(?:on\s+the\s+)?(?:dpad|arrow)", c):
            out.append(("dpad", m.group(1)))
            continue
        flips = re.findall(r"\b(?:flip|toggle|switch)\w*\s+(?:switch\s+)?(?:number\s+)?" + _NUM, c)
        out += [("flip", _num(n) - 1) for n in flips]
        if re.search(r"\b(?:press|push|hit|tap)?\s*(?:the\s+)?enter\b", c):
            out.append(("enter", None))
    return out


def blind_typed(store, code, sid, text) -> list[tuple[tuple, str]]:
    """A human Blind player typed something: carry out any instructions in it, through
    the same validated path as the buttons. Returns [(action, result), ...]."""
    with store["lock"]:
        room = hub.get_room(store, code)
        p = hub.player(room, sid) if room else None
        if p is None or p["seat"] != "blind":
            return []
        actions = parse_blind_instructions(text, room["state"]["bomb"])
    done = []
    for kind, value in actions:
        r = touch(store, code, sid, kind, value)
        done.append(((kind, value), r))
        if r in ("strike", "exploded", "not_started", "game_over"):
            break
    return done
