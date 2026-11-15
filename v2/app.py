"""
AI Escape Room - Version 2 (Reliable AI Escape Room)

Python decides, the LLM describes:
  * the game state is a structured dict and every action is validated by
    game_engine.py against game_config.json (inventory, flags, puzzles, door),
  * the room is drawn with Pillow (room_renderer.py) from that state on every
    turn, so the picture can never disagree with the game,
  * clicking an object shows the actions that make sense for it; each button
    builds a structured Action that goes straight into the engine,
  * typed natural-language commands go through action_parser.py (rules first,
    Gemini JSON only as a fallback) into the same engine,
  * narrator.py lets Gemini describe the outcome; its output guard rejects any
    narration that contradicts the engine or leaks the code.
Runs without an API key (offline mode: engine text only).

Run:  streamlit run v2/app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit_image_coordinates import streamlit_image_coordinates

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT))                  # gemini_model.py, room_renderer.py (shared with V1)
from action_parser import RuleParser, llm_parse  # noqa: E402
from game_engine import Action, EscapeRoomEngine, load_config  # noqa: E402
from gemini_model import resolve_model  # noqa: E402
from narrator import Narrator  # noqa: E402
import room_renderer as rr  # noqa: E402
import ui_style as ui  # noqa: E402

load_dotenv(ROOT / ".env")
CONFIG = load_config()
NAMES = {oid: o["name"] for oid, o in CONFIG["objects"].items()}
ITEM_ICONS = {"note": "📜", "brass_key": "🗝️", "uv_flashlight": "🔦", "torn_page": "📄"}


@st.cache_resource
def get_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key or key.startswith("your-"):
        return None
    from google import genai
    return genai.Client(api_key=key)


# ---------------------------------------------------------------------------
# Game session helpers
# ---------------------------------------------------------------------------
def reset_game():
    st.session_state.engine = EscapeRoomEngine(CONFIG)
    st.session_state.messages = [{"role": "assistant", "content": CONFIG["intro"]
                                  + "\n\n*Click anything in the room to interact with it.*"}]
    st.session_state.debug = []
    st.session_state.selected = None
    st.session_state.held = None
    st.session_state.last_click = None
    st.session_state.pad_code = ""


def run_action(action: Action, player_text: str, source: str = "click"):
    """Send a structured action to the engine and narrate the result."""
    engine = st.session_state.engine
    client = get_client()
    model = resolve_model(client) if client else None
    result = engine.handle(action)
    narrator = Narrator(engine, client, model)
    reply = narrator.narrate(player_text, result, st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": player_text})
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.debug.append({"input": player_text, "source": source, "action": action.to_dict(),
                                   "result": result.to_dict(), "guard_triggered": narrator.last_guard_triggered})
    # engine check, flashed as a toast on the next run (toasts can't be shown from a callback)
    st.session_state.toast = (("✅ " if result.success else "❌ ") + f"{action.verb} → {result.event}",
                              "🛡️")
    # Drop the selection if the object just went into the inventory.
    if st.session_state.selected in engine.state["inventory"]:
        st.session_state.selected = None
    if st.session_state.held and st.session_state.held not in engine.state["inventory"]:
        st.session_state.held = None


def run_text(text: str):
    """Typed (or example) command: parsed first, then validated by the same engine."""
    client = get_client()
    action = RuleParser(CONFIG).parse(text)
    if action.verb == "unknown" and not action.raw_noun and client is not None:
        action = llm_parse(client, resolve_model(client), text, list(CONFIG["objects"])) or action
    run_action(action, text, source="typed")


def enter_code(code: str):
    run_action(Action("enter_code", "door", code=code), f"🔢 Enter {code} on the keypad")


def hold(item):
    st.session_state.held = None if st.session_state.held == item else item


# ---------------------------------------------------------------------------
# Page: full-screen game scene with a floating HUD (see ui_style.py)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Locked Library - V2", page_icon="🗝️", layout="wide",
                   initial_sidebar_state="collapsed")
ui.apply_style()
if "engine" not in st.session_state:
    reset_game()
engine: EscapeRoomEngine = st.session_state.engine
state = engine.state
if st.session_state.get("toast"):                 # engine check: was the last action allowed?
    msg, icon = st.session_state.pop("toast")
    st.toast(msg, icon=icon)

ui.badge(2)

# ----- the room (drawn from the game state, clickable) ------------------------
img = rr.render(state, st.session_state.selected, False, NAMES, CONFIG["season_numbers"])
click = streamlit_image_coordinates(img, key="room", use_column_width="always",
                                    image_format="JPEG", jpeg_quality=90, cursor="pointer")
if click and click.get("unix_time") != st.session_state.last_click:
    st.session_state.last_click = click.get("unix_time")
    x = click["x"] * rr.W / click["width"]
    y = click["y"] * rr.H / click["height"]
    st.session_state.selected = rr.hit_test(x, y, state)
    st.rerun()

# ----- top right: story, hint, restart ---------------------------------------
with st.container(key="hud_top", horizontal=True):
    with st.popover("", icon=":material/history_edu:", help="Story"):
        ui.story(st.session_state.messages)
    st.button("", icon=":material/lightbulb:", help="Hint", on_click=run_action, args=(Action("hint"), "💡 Hint please"),
              disabled=state["escaped"])
    if st.button("", icon=":material/restart_alt:", help="Restart"):
        reset_game()
        st.rerun()

# ----- actions next to the clicked object -------------------------------------
sel, held = st.session_state.selected, st.session_state.held
if sel and not state["escaped"]:
    ui.place_actions(rr._current_hotspots(state["flags"])[sel])
    name = NAMES[sel]
    with st.container(key="hud_actions", horizontal=True):
        st.button("🔍 Examine", on_click=run_action, args=(Action("examine", sel), f"🔍 Examine the {name}"))
        if sel == "painting" and not state["flags"]["painting_moved"]:
            st.button("🖼️ Look behind", on_click=run_action, args=(Action("move", sel), "🖼️ Look behind the painting"))
        if CONFIG["objects"][sel]["takeable"] and sel not in state["inventory"]:
            st.button("✋ Take", on_click=run_action, args=(Action("take", sel), f"✋ Take the {name}"))
        if sel == "drawer":
            st.button("🔓 Open", on_click=run_action, args=(Action("open", sel), "🔓 Open the drawer"))
        if sel == "globe":
            st.button("🌍 Spin", on_click=run_action, args=(Action("move", sel), "🌍 Spin the globe"))
        if sel == "door":
            with st.popover("🔢 Keypad"):
                ui.keypad(on_enter=enter_code)
        if held and held != sel:
            st.button(f"{ITEM_ICONS.get(held, '')} Use {NAMES[held]}", type="primary", on_click=run_action,
                      args=(Action("use", held, sel), f"{ITEM_ICONS.get(held, '')} Use the {NAMES[held]} on the {name}"))

# ----- bottom: latest story line, inventory slots ------------------------------
if state["escaped"]:
    ui.subtitle("🎉 You escaped the Locked Library! Press ↻ to play again.")
    if not st.session_state.get("celebrated"):
        st.balloons()
        st.session_state.celebrated = True
else:
    st.session_state.celebrated = False
    ui.subtitle(next(m["content"] for m in reversed(st.session_state.messages) if m["role"] == "assistant"))

with st.container(key="hud_inv", horizontal=True):
    items = state["inventory"]
    for i in range(max(ui.SLOTS, len(items))):
        if i < len(items):
            item = items[i]
            st.button(ITEM_ICONS.get(item, "•"), key=f"inv_{item}", on_click=hold, args=(item,),
                      type="primary" if held == item else "secondary",
                      help=f"{NAMES[item]}: " + ("holding - click an object to use it" if held == item
                                                 else "click to hold it, then click an object"))
        else:
            st.button(" ", key=f"slot_{i}", disabled=True)

with st.sidebar:                                  # collapsed by default: for developers / the report
    st.subheader("Under the hood")
    with st.expander("Last action (engine check)", expanded=True):
        st.json(st.session_state.debug[-1] if st.session_state.debug else {})
    with st.expander("Game state (JSON)"):
        st.json({k: v for k, v in state.items() if k != "history"})

if typed := st.chat_input(ui.CHAT_PLACEHOLDER, disabled=state["escaped"]):
    with st.spinner("The Game Master is thinking..."):
        run_text(typed)
    st.rerun()
