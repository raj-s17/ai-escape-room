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

import importlib
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

# The shared files live outside this folder, so Streamlit doesn't hot-reload them.
# Reload them on every run so a running server never shows an outdated layout.
rr = importlib.reload(rr)
ui = importlib.reload(ui)

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
    # V1's "check": nothing validated the action - Gemini alone decided (flashed as a toast)
    st.session_state.toast = ("Gemini decided alone - no validation" + (" - [ESCAPED]" if escaped else ""),
                              ":material/smart_toy:")


# ---------------------------------------------------------------------------
# Page: the same layout as V2 (see ui_style.py). The differences are the real
# ones: the room never changes, the inventory slots stay empty, and nothing
# validates what Gemini decides.
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Locked Library - V1", page_icon="🗝️", layout="wide",
                   initial_sidebar_state="collapsed")
ui.apply_style()
if "messages" not in st.session_state:
    reset_game()
client = get_client()
if st.session_state.get("toast"):
    msg, icon = st.session_state.pop("toast")
    st.toast(msg, icon=icon)

with st.container(key="head", horizontal=True):
    ui.badge(1)
    st.space("stretch")
    st.button("", icon=":material/lightbulb:", help="Hint", on_click=send,
              args=("I'm stuck. Can you give me a hint?",), disabled=client is None or st.session_state.escaped)
    if st.button("", icon=":material/restart_alt:", help="Restart"):
        reset_game()
        st.rerun()

with st.container(key="main", horizontal=True):
    # ----- the room: always the starting room (V1 keeps no state) -------------------
    with st.container(key="scene"):
        img = rr.render(START_STATE, st.session_state.selected, False, NAMES)
        click = streamlit_image_coordinates(img, key="room", use_column_width="always",
                                            image_format="JPEG", jpeg_quality=90, cursor="pointer")
        if click and click.get("unix_time") != st.session_state.last_click:
            st.session_state.last_click = click.get("unix_time")
            x = click["x"] * rr.W / click["width"]
            y = click["y"] * rr.H / click["height"]
            st.session_state.selected = rr.hit_test(x, y, START_STATE)
            st.rerun()

        # suggested commands next to the clicked object (sent to Gemini as text)
        sel = st.session_state.selected
        if client is not None and sel and not st.session_state.escaped:
            ui.place_actions(rr.HOTSPOTS[sel])
            with st.container(key="hud_actions", horizontal=True):
                for text in COMMANDS.get(sel, [f"Examine the {NAMES[sel]}"]):
                    st.button(text, key=f"cmd_{sel}_{text}", on_click=send, args=(text,))
                if sel == "door":
                    with st.popover("🔢 Keypad"):
                        ui.keypad(on_enter=lambda code: send(f"I enter {code} on the door keypad."))

    # ----- the story -----------------------------------------------------------------
    messages = list(st.session_state.messages)
    if client is None:
        messages.append({"role": "assistant", "content": "No GEMINI_API_KEY found. Add your key to .env - Version 1 "
                                                         "needs Gemini (Version 2 also runs offline)."})
    elif st.session_state.escaped:
        messages.append({"role": "assistant", "content": "🎉 You escaped the Locked Library! Press ↻ to play again."})
    ui.story_log(messages)

# ----- bottom: empty inventory slots + command box --------------------------------
with st.container(key="bottom", horizontal=True):
    for i in range(ui.SLOTS):
        st.button(" ", key=f"slot_{i}", disabled=True, help="Version 1 keeps no inventory - only Gemini 'remembers'")
    typed = st.chat_input(ui.CHAT_PLACEHOLDER, disabled=client is None or st.session_state.escaped)

if typed:
    with st.spinner("The Game Master is thinking..."):
        send(typed)
    st.rerun()
