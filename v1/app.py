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
# Page (same layout as V2; the differences are the real ones)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Locked Library - V1", page_icon="🗝️", layout="wide")
ui.apply_style()
if "messages" not in st.session_state:
    reset_game()
client = get_client()

with st.sidebar:
    st.caption(ui.HOW_TO_PLAY)
    st.header("🎒 Inventory")
    st.caption("Not tracked in Version 1. Only Gemini \"remembers\" what you carry, in the chat.")
    st.divider()
    ui.quick_commands(ui.EXAMPLES, on_pick=send, disabled=client is None or st.session_state.escaped)
    st.divider()
    show_labels = st.toggle("Show object labels", value=True)
    c1, c2 = st.columns(2)
    hint = c1.button("💡 Hint", width="stretch", disabled=client is None)
    if c2.button("🔄 Restart", width="stretch"):
        reset_game()
        st.rerun()
    st.warning("Version 1: Gemini is the whole game. No inventory, no state, no validation, and the room picture "
            "never changes. Version 2 fixes that.")
    st.caption(ui.THEME_TIP)

if client is None:
    ui.header(1, "🤖 The LLM is the whole game: story, rules, solutions and progress live only in the chat.",
              "No GEMINI_API_KEY found")
    st.error("No GEMINI_API_KEY found. Copy `.env.example` to `.env` and add your free key from Google AI "
             "Studio. (Version 2 also runs offline.)")
    st.stop()

from gemini_model import resolve_model  # noqa: E402

ui.header(1, "🤖 The LLM is the whole game: story, rules, solutions and progress live only in the chat.",
          f"Gemini game master: {resolve_model(client)} · no game engine, no state, no validation")
ui.status_row("?", "?", "-", "-", notes={
    "🎒 Items": "No inventory: Gemini may forget or invent items",
    "🚪 Door": "Decided only by Gemini writing the [ESCAPED] tag",
    "🔢 Code tries": "Not counted in V1",
    "⛔ Rule breaks blocked": "Nothing blocks them in V1: Gemini decides on its own"})

if hint:
    with st.spinner("The Game Master is thinking..."):
        send("I'm stuck. Can you give me a hint?")
    st.rerun()

room_col, story_col = st.columns([1.5, 1], gap="large")

with room_col:
    img = rr.render(START_STATE, st.session_state.selected, show_labels, NAMES)
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
        st.caption("👆 Click an object in the room. ⚠️ In V1 this picture never changes: nothing tracks the game.")
    else:
        st.markdown(f"#### 🔎 {NAMES[sel].capitalize()}")
        commands = COMMANDS.get(sel, [f"Examine the {NAMES[sel]}"])
        cols = st.columns(len(commands))
        for col, text in zip(cols, commands):
            if col.button(text, key=f"cmd_{sel}_{text}", width="stretch"):
                with st.spinner("The Game Master is thinking..."):
                    send(text)
                st.rerun()
        if sel == "door":
            _, pad, _ = st.columns([1, 1.4, 1])
            with pad:
                ui.keypad(on_enter=lambda code: send(f"I enter {code} on the door keypad."),
                          disabled=st.session_state.escaped)

with story_col:
    last = st.session_state.get("last_turn")
    with st.container(border=True):
        st.markdown("**🤖 Who decided · last action**")
        if last is None:
            st.caption("In V1 nothing checks your actions: Gemini alone decides what happens.")
        else:
            st.markdown("Gemini alone · **no validation**" + (" · ended the game with `[ESCAPED]`"
                                                              if last["escaped"] else ""))
            st.caption(f"Input: {last['input']}")
    ui.story(st.session_state.messages)

if typed := st.chat_input(ui.CHAT_PLACEHOLDER, disabled=st.session_state.escaped):
    with st.spinner("The Game Master is thinking..."):
        send(typed)
    st.rerun()
