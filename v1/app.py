"""
AI Escape Room - Version 1 (Interactive AI Escape Room)

In this version the LLM does everything: it holds the room description,
the puzzle solutions and the rules in its system prompt, keeps track of the
story through the chat history, and decides on its own when the player has
escaped. This makes the game quick to build and fun to play, but it also
means the game is only as reliable as the model (see docs/test_cases.md).

The room picture is the same one V2 uses (room_renderer.py), but here it can
only show the room as it was at the start: V1 has no game state to draw from.
Clicking an object just writes a command for you - Gemini still decides what
happens.

Run:  streamlit run v1/app.py
"""

import html
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai
from streamlit_image_coordinates import streamlit_image_coordinates

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT))  # gemini_model.py, room_renderer.py (shared with V2)
from game_master import ESCAPE_TAG, INTRO, ask_game_master  # noqa: E402
import room_renderer as rr  # noqa: E402
import ui_style as ui  # noqa: E402

load_dotenv(ROOT / ".env")

# The room as it looks at the start. V1 never updates this: nothing outside
# the LLM keeps track of what has happened (a known V1 limitation).
START_STATE = {
    "visible": ["desk", "note", "painting", "drawer", "bookshelf", "globe", "door"],
    "inventory": [],
    "flags": {"painting_moved": False, "drawer_unlocked": False, "books_revealed": False},
    "escaped": False,
}
NAMES = {"desk": "desk", "note": "note", "painting": "painting", "drawer": "drawer",
         "bookshelf": "bookshelf", "globe": "globe", "door": "door"}
COMMANDS = {
    "desk": ["Examine the desk", "Read the note on the desk"],
    "note": ["Read the note", "Take the note"],
    "painting": ["Examine the painting", "Look behind the painting"],
    "drawer": ["Open the drawer", "Use the brass key on the drawer"],
    "bookshelf": ["Examine the bookshelf", "Shine the UV flashlight on the books"],
    "globe": ["Examine the globe", "Spin the globe"],
    "door": ["Examine the door", "Open the door"],
}


@st.cache_resource
def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("your-"):
        return None
    return genai.Client(api_key=api_key)


def reset_game():
    st.session_state.messages = [{"role": "assistant", "content": INTRO
                                  + "\n\n*Click anything in the room to interact with it.*"}]
    st.session_state.escaped = False
    st.session_state.selected = None
    st.session_state.last_click = None
    st.session_state.pad_code = ""


def send(text: str):
    """V1: the whole chat goes to Gemini, which alone decides what happens."""
    st.session_state.messages.append({"role": "user", "content": text})
    try:
        reply = ask_game_master(get_client(), st.session_state.messages)
    except Exception as exc:  # network / quota errors
        reply = f"⚠️ Could not reach Gemini: {exc}"
    escaped = ESCAPE_TAG in reply      # the LLM's own tag ends the game
    if escaped:
        st.session_state.escaped = True
        reply = reply.replace(ESCAPE_TAG, "").strip()
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.last_turn = {"input": text, "escaped": escaped}


# ---------------------------------------------------------------------------
# Page: same minimal layout as V2; the differences are the real ones
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Locked Library - V1", page_icon="🗝️", layout="wide",
                   initial_sidebar_state="collapsed")
ui.apply_style()
if "messages" not in st.session_state:
    reset_game()
client = get_client()

head, b_hint, b_restart = st.columns([12, 1, 1], vertical_alignment="center")
with head:
    ui.header(1, "Gemini is the whole game", ["🎒 ?", "🚪 ?", "no state tracked"])
hint = b_hint.button("💡", help="Hint", width="stretch", disabled=client is None or st.session_state.escaped)
if b_restart.button("↻", help="Restart", width="stretch"):
    reset_game()
    st.rerun()

if client is None:
    st.error("No GEMINI_API_KEY found. Copy `.env.example` to `.env` and add your free key from Google AI "
             "Studio. (Version 2 also runs offline.)")
    st.stop()
if hint:
    with st.spinner("The Game Master is thinking..."):
        send("I'm stuck. Can you give me a hint?")
    st.rerun()

room_col, story_col = st.columns([1.3, 1], gap="medium")

with room_col:
    img = rr.render(START_STATE, st.session_state.selected, True, NAMES)
    click = streamlit_image_coordinates(img, key="room", use_column_width="always",
                                        image_format="JPEG", jpeg_quality=88, cursor="pointer")
    if click and click.get("unix_time") != st.session_state.last_click:
        st.session_state.last_click = click.get("unix_time")
        x = click["x"] * rr.W / click["width"]
        y = click["y"] * rr.H / click["height"]
        st.session_state.selected = rr.hit_test(x, y, START_STATE)
        st.rerun()

    sel = st.session_state.selected
    if st.session_state.escaped:
        st.success(ui.ESCAPED)
    elif sel is None:
        st.caption("👆 Click an object in the room. (In V1 this picture never changes: nothing tracks the game.)")
    else:
        commands = COMMANDS.get(sel, [f"Examine the {NAMES[sel]}"])
        cols = st.columns([1.2] + [1.6] * len(commands), vertical_alignment="center")
        cols[0].markdown(f"#### {NAMES[sel].capitalize()}")
        for col, text in zip(cols[1:], commands):
            col.button(text, key=f"cmd_{sel}_{text}", width="stretch", on_click=send, args=(text,))
        if sel == "door":
            ui.keypad(on_enter=lambda code: send(f"I enter {code} on the door keypad."))

with story_col:
    last = st.session_state.get("last_turn")
    ui.check(1, "🤖 <b>Who decided</b> · Gemini alone, <b>no validation</b>"
                + (f" · <i>{html.escape(last['input'])}</i>" if last else "")
                + (" · ended the game with <code>[ESCAPED]</code>" if last and last["escaped"] else ""))
    ui.story(st.session_state.messages)

if typed := st.chat_input(ui.CHAT_PLACEHOLDER, disabled=st.session_state.escaped):
    with st.spinner("The Game Master is thinking..."):
        send(typed)
    st.rerun()
