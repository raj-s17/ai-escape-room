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

import html
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
# Page: one screen, no scrolling
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Locked Library - V2", page_icon="🗝️", layout="wide",
                   initial_sidebar_state="collapsed")
ui.apply_style()
if "engine" not in st.session_state:
    reset_game()
engine: EscapeRoomEngine = st.session_state.engine
state = engine.state
client = get_client()

# ----- header: version, live state, hint, restart -----------------------------
head, b_hint, b_restart = st.columns([12, 1, 1], vertical_alignment="center")
with head:
    ui.header(2, "Python decides, the LLM describes" + ("" if client else " · offline"),
              [f"🎒 {len(state['inventory'])}", "🚪 " + ("open" if state["escaped"] else "locked"),
               f"🔢 {state['code_attempts']} tries", f"⛔ {state['rule_violations']} blocked"])
b_hint.button("💡", help="Hint", width="stretch", on_click=run_action, args=(Action("hint"), "💡 Hint please"),
              disabled=state["escaped"])
if b_restart.button("↻", help="Restart", width="stretch"):
    reset_game()
    st.rerun()

room_col, story_col = st.columns([1.3, 1], gap="medium")

with room_col:
    img = rr.render(state, st.session_state.selected, True, NAMES, CONFIG["season_numbers"])
    click = streamlit_image_coordinates(img, key="room", use_column_width="always",
                                        image_format="JPEG", jpeg_quality=88, cursor="pointer")
    if click and click.get("unix_time") != st.session_state.last_click:
        st.session_state.last_click = click.get("unix_time")
        x = click["x"] * rr.W / click["width"]
        y = click["y"] * rr.H / click["height"]
        st.session_state.selected = rr.hit_test(x, y, state)
        st.rerun()

    sel, held = st.session_state.selected, st.session_state.held
    if state["escaped"]:
        st.success(ui.ESCAPED)
        if not st.session_state.get("celebrated"):
            st.balloons()
            st.session_state.celebrated = True
    elif sel is None:
        st.caption("👆 Click an object in the room" + (f" to use the {NAMES[held]} on it." if held else "."))
    else:
        st.session_state.celebrated = False
        name = NAMES[sel]
        buttons = [("🔍 Examine", Action("examine", sel), f"🔍 Examine the {name}")]
        if sel == "painting" and not state["flags"]["painting_moved"]:
            buttons.append(("🖼️ Look behind", Action("move", sel), "🖼️ Look behind the painting"))
        if CONFIG["objects"][sel]["takeable"] and sel not in state["inventory"]:
            buttons.append(("✋ Take", Action("take", sel), f"✋ Take the {name}"))
        if sel == "drawer":
            buttons.append(("🔓 Open", Action("open", sel), f"🔓 Open the {name}"))
        if sel == "globe":
            buttons.append(("🌍 Spin", Action("move", sel), "🌍 Spin the globe"))
        if held and held != sel:
            buttons.append((f"{ITEM_ICONS.get(held, '')} Use {NAMES[held]}", Action("use", held, sel),
                            f"{ITEM_ICONS.get(held, '')} Use the {NAMES[held]} on the {name}"))
        cols = st.columns([1.2] + [1] * len(buttons), vertical_alignment="center")
        cols[0].markdown(f"#### {name.capitalize()}")
        for col, (label, action, text) in zip(cols[1:], buttons):
            col.button(label, key=f"act_{sel}_{label}", width="stretch", on_click=run_action, args=(action, text))
        if sel == "door":
            ui.keypad(on_enter=enter_code)

    # inventory: click an item to hold it, then click where to use it
    if state["inventory"]:
        cols = st.columns([0.5] + [1] * len(state["inventory"]), vertical_alignment="center")
        cols[0].markdown("🎒")
        for col, item in zip(cols[1:], state["inventory"]):
            col.button(("✅ " if held == item else ITEM_ICONS.get(item, "") + " ") + NAMES[item],
                       key=f"inv_{item}", width="stretch", on_click=hold, args=(item,),
                       type="primary" if held == item else "secondary",
                       help="Holding - click an object to use it there" if held == item else "Click to hold it")

with story_col:
    last = st.session_state.debug[-1] if st.session_state.debug else None
    if last is None:
        ui.check(2, "🛡️ <b>Engine check</b> · every action is validated by Python before Gemini narrates.")
    else:
        res, act = last["result"], last["action"]
        args = html.escape(", ".join(f"{k}={v}" for k, v in act.items() if v and k != "verb"))
        ui.check(2, f"🛡️ <b>Engine check</b> · <code>{act['verb']}({args})</code> → "
                    + ("✅ <b>allowed</b>" if res["success"] else "❌ <b>refused</b>")
                    + f" · <code>{res['event']}</code>" + (" · 🧹 guard" if last.get("guard_triggered") else ""))
    ui.story(st.session_state.messages)

with st.sidebar:                                  # collapsed by default: for developers / the report
    st.subheader("Under the hood")
    with st.expander("Game state (JSON)", expanded=True):
        st.json({k: v for k, v in state.items() if k != "history"})
    with st.expander("Last action (debug)"):
        st.json(st.session_state.debug[-1] if st.session_state.debug else {})

if typed := st.chat_input(ui.CHAT_PLACEHOLDER, disabled=state["escaped"]):
    with st.spinner("The Game Master is thinking..."):
        run_text(typed)
    st.rerun()
