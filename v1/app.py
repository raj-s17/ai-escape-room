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
                                  + "\n\n*Click anything in the room, or type what you do.*"}]
    st.session_state.escaped = False
    st.session_state.selected = None
    st.session_state.last_click = None


def send(text: str):
    """V1: the whole chat goes to Gemini, which alone decides what happens."""
    st.session_state.messages.append({"role": "user", "content": text})
    try:
        reply = ask_game_master(get_client(), st.session_state.messages)
    except Exception as exc:  # network / quota errors
        reply = f"⚠️ Could not reach Gemini: {exc}"
    if ESCAPE_TAG in reply:   # the LLM's own tag ends the game
        st.session_state.escaped = True
        reply = reply.replace(ESCAPE_TAG, "").strip()
    st.session_state.messages.append({"role": "assistant", "content": reply})


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Escape Room - V1", page_icon="🗝️", layout="wide")
if "messages" not in st.session_state:
    reset_game()

st.title("🗝️ The Locked Library")
client = get_client()

with st.sidebar:
    st.header("How to play")
    st.markdown(
        "- Click an object in the room for suggested commands, or type in plain English.\n"
        "- Examples: *examine the desk*, *look behind the painting*, "
        "*open the drawer with the key*, *enter 1234 on the door*.\n"
        "- Find the clues, solve the puzzles and unlock the door."
    )
    st.info("Version 1: Gemini is the whole game. There is no inventory or puzzle tracker, and the room picture "
            "never changes, because nothing outside the LLM keeps track of the game. Version 2 fixes that.")
    show_labels = st.toggle("Show object labels", value=True)
    if st.button("🔄 Restart game", width="stretch"):
        reset_game()
        st.rerun()

if client is None:
    st.error("No GEMINI_API_KEY found. Copy `.env.example` to `.env` and add your free key from Google AI "
             "Studio. (Version 2 also runs offline.)")
    st.stop()

from gemini_model import resolve_model  # noqa: E402

st.caption(f"Version 1 - the LLM is the whole game · model `{resolve_model(client)}`")

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
        st.success("🎉 You escaped the Locked Library! Press *Restart game* to play again.")
    elif sel is None:
        st.caption("👆 Click an object in the room for suggested commands.")
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
            k1, k2 = st.columns([3, 1])
            code = k1.text_input("Keypad", key="keypad", max_chars=4, placeholder="4-digit code",
                                 label_visibility="collapsed")
            if k2.button("🔢 Enter", width="stretch") and code.strip():
                with st.spinner("The Game Master is thinking..."):
                    send(f"I enter {code.strip()} on the door keypad.")
                st.rerun()

with story_col:
    st.markdown("#### 📖 Story")
    with st.container(height=520):
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "🧑"):
                st.markdown(msg["content"])

if typed := st.chat_input("...or type what you do, e.g. 'look behind the painting'",
                          disabled=st.session_state.escaped):
    with st.spinner("The Game Master is thinking..."):
        send(typed)
    st.rerun()
