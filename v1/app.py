"""
AI Escape Room - Version 1 (Interactive AI Escape Room)

In this version the LLM does everything: it holds the room description,
the puzzle solutions and the rules in its system prompt, keeps track of the
story through the chat history, and decides on its own when the player has
escaped. This makes the game quick to build and fun to play, but it also
means the game is only as reliable as the model (see docs/test_cases.md).

Run:  streamlit run v1/app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai

sys.path.insert(0, str(Path(__file__).parent))
from game_master import ESCAPE_TAG, INTRO, ask_game_master  # noqa: E402

load_dotenv()


@st.cache_resource
def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("your-"):
        return None
    return genai.Client(api_key=api_key)


def reset_game():
    st.session_state.messages = [{"role": "assistant", "content": INTRO}]
    st.session_state.escaped = False


# ---------------------------------------------------------------------------
# User interface
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Escape Room - V1", page_icon="🗝️")
st.title("🗝️ The Locked Library")
st.caption("Version 1 - the LLM is the whole game")

with st.sidebar:
    st.header("How to play")
    st.markdown(
        "- Type what you want to do in plain English.\n"
        "- Examples: *examine the desk*, *look behind the painting*, "
        "*open the drawer with the key*, *enter 1234 on the door*.\n"
        "- Find the clues, solve the puzzles and unlock the door."
    )
    if st.button("🔄 Restart game", use_container_width=True):
        reset_game()
        st.rerun()

client = get_client()
if client is None:
    st.error(
        "No GEMINI_API_KEY found. Copy `.env.example` to `.env` and add your "
        "free key from Google AI Studio."
    )
    st.stop()

if "messages" not in st.session_state:
    reset_game()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "🧑"):
        st.markdown(msg["content"])

if st.session_state.escaped:
    st.success("🎉 You escaped the Locked Library! Press *Restart game* to play again.")
    st.stop()

if prompt := st.chat_input("What do you do?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🧙"):
        with st.spinner("The Game Master is thinking..."):
            try:
                reply = ask_game_master(client, st.session_state.messages)
            except Exception as exc:  # network / quota errors
                reply = f"⚠️ Could not reach Gemini: {exc}"
        # In V1 the LLM alone decides whether the player escaped.
        if ESCAPE_TAG in reply:
            st.session_state.escaped = True
            reply = reply.replace(ESCAPE_TAG, "").strip()
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    if st.session_state.escaped:
        st.rerun()
