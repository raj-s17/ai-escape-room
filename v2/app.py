"""
AI Escape Room - Version 2 (Reliable AI Escape Room)

Pipeline for every player message:

    player text --> Parser --> Action --> GameEngine (validates, updates state)
                                              |
                                              v
                    Narrator (Gemini) <-- Result + public state
                         |
                         v
                  output guard --> chat reply

Python decides; the LLM only describes. Runs without an API key too
("offline mode"), in which case the engine's own text is shown.

Run:  streamlit run v2/app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from game_engine import EscapeRoomEngine, load_config  # noqa: E402
from narrator import Narrator  # noqa: E402
from action_parser import RuleParser, llm_parse  # noqa: E402

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
CONFIG = load_config()


@st.cache_resource
def get_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key or key.startswith("your-"):
        return None
    from google import genai
    return genai.Client(api_key=key)


def reset_game():
    st.session_state.engine = EscapeRoomEngine(CONFIG)
    st.session_state.messages = [{"role": "assistant", "content": CONFIG["intro"]}]
    st.session_state.debug = []


def process(message: str) -> str:
    engine: EscapeRoomEngine = st.session_state.engine
    client = get_client()
    action = RuleParser(CONFIG).parse(message)
    used_llm_parser = False
    if action.verb == "unknown" and not action.raw_noun and client is not None:
        llm_action = llm_parse(client, MODEL, message, list(CONFIG["objects"].keys()))
        if llm_action is not None:
            action, used_llm_parser = llm_action, True

    result = engine.handle(action)
    narrator = Narrator(engine, client, MODEL)
    reply = narrator.narrate(message, result, st.session_state.messages)

    st.session_state.debug.append({
        "message": message,
        "action": action.to_dict(),
        "parser": "llm" if used_llm_parser else "rules",
        "result": result.to_dict(),
        "guard_triggered": narrator.last_guard_triggered,
    })
    return reply


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Escape Room - V2", page_icon="🔐", layout="wide")
if "engine" not in st.session_state:
    reset_game()
engine: EscapeRoomEngine = st.session_state.engine
state = engine.state

st.title("🔐 The Locked Library")
mode = "Gemini narrator" if get_client() else "offline mode (no API key - engine text only)"
st.caption(f"Version 2 - Python validates every action, the LLM narrates · {mode}")

with st.sidebar:
    st.header("How to play")
    st.markdown(
        "Type actions in plain English, e.g. *examine the desk*, *look behind the painting*, "
        "*take the key*, *use the key on the drawer*, *enter 1234 on the door*. "
        "Type **hint** if you are stuck or **help** for commands."
    )
    if st.button("🔄 Restart game", use_container_width=True):
        reset_game()
        st.rerun()

    st.divider()
    st.subheader("🎒 Inventory")
    st.write(", ".join(engine.name(o) for o in state["inventory"]) or "_empty_")

    st.subheader("🧩 Puzzles")
    st.markdown("\n".join(
        f"- {'✅' if pid in state['solved_puzzles'] else '⬜'} {desc}"
        for pid, desc in CONFIG["puzzles"].items()))
    st.progress(len(state["solved_puzzles"]) / len(CONFIG["puzzles"]))

    st.subheader("🚪 Door")
    st.write("🟢 Open - you escaped!" if state["escaped"] else "🔴 Locked")
    c1, c2, c3 = st.columns(3)
    c1.metric("Turn", state["turn"])
    c2.metric("Code tries", state["code_attempts"])
    c3.metric("Rule breaks", state["rule_violations"])

    with st.expander("🛠 Game state (JSON)"):
        st.json({k: v for k, v in state.items() if k != "history"})
    with st.expander("🔍 Last action (debug)"):
        st.json(st.session_state.debug[-1] if st.session_state.debug else {})

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "🧑"):
        st.markdown(msg["content"])

if state["escaped"]:
    st.success(f"🎉 You escaped the Locked Library in {state['turn']} turns! Press *Restart game* to play again.")
    if not st.session_state.get("celebrated"):
        st.balloons()
        st.session_state.celebrated = True
else:
    st.session_state.celebrated = False

if prompt := st.chat_input("What do you do?", disabled=state["escaped"]):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("The Game Master is thinking..."):
        reply = process(prompt)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
