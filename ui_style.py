"""
Shared game-style HUD for Version 1 and Version 2 (presentation only, no game rules).

Layout ("Option A"): the room fills the screen like a point-and-click game.
Everything else floats on top of it:
  top-left      version badge + title
  top-right     📜 story (popover with the whole conversation), 💡 hint, ↻ restart
  on the object the actions for the clicked object (next to it)
  bottom        latest story line as a subtitle, inventory slots, command box

Built only with Streamlit's own pieces: keyed containers (st.container(key=...)
gets the CSS class .st-key-<key>, which is positioned here), st.popover,
st.toast and st.chat_input. The app always uses the dark theme from
.streamlit/config.toml.
"""

from __future__ import annotations

import html
import re

import streamlit as st

GOLD = "217, 163, 91"
BADGE = {1: ("V1", "rgba(192,102,28,.92)", "LLM only"), 2: ("V2", "rgba(46,160,90,.92)", "Reliable")}
IMG_W, IMG_H = 960, 600                 # room_renderer size (16:10)
SCENE_W = "min(100vw, 160vh)"           # the scene is as large as fits the window (16:10)
SCENE_H = f"calc({SCENE_W} / 1.6)"

CSS = f"""
<style>
header[data-testid="stHeader"], header[data-testid="stHeader"] div {{background: transparent; pointer-events: none;}}
header[data-testid="stHeader"] button {{pointer-events: auto;}}
.stApp {{background: #0d0a07;}}
.block-container {{padding: 0 !important; max-width: {SCENE_W} !important; margin: 0 auto;}}
[data-testid="stMainBlockContainer"] > div {{gap: 0;}}
iframe {{display: block;}}
.st-key-hud_top, .st-key-hud_actions, .st-key-hud_inv {{position: fixed; z-index: 1000001; gap: 8px;
    width: auto !important;}}
.st-key-hud_top {{top: 14px; right: max(calc((100vw - {SCENE_W}) / 2 + 16px), 56px);}}
.st-key-hud_inv {{bottom: 76px; left: 50%; transform: translateX(-50%);}}
.st-key-hud_top button, .st-key-hud_inv button, .st-key-hud_actions button {{
    background: rgba(14, 11, 8, .72) !important; color: #efe4d2 !important;
    border: 1px solid rgba({GOLD}, .5) !important; border-radius: 12px !important; backdrop-filter: blur(4px);
    transition: transform .1s, box-shadow .15s;}}
.st-key-hud_top button:hover, .st-key-hud_inv button:hover, .st-key-hud_actions button:hover {{
    transform: translateY(-1px); box-shadow: 0 0 14px rgba({GOLD}, .55);}}
.st-key-hud_top button {{width: 46px; height: 46px; font-size: 1.15rem;}}
.st-key-hud_inv button {{width: 64px; height: 64px;}}
.st-key-hud_inv button p {{font-size: 1.9rem !important; line-height: 1;}}
.st-key-hud_inv button[kind="primary"] {{border: 2px solid rgb({GOLD}) !important;
    box-shadow: 0 0 16px rgba({GOLD}, .7);}}
.st-key-hud_actions button {{padding: 4px 14px; min-height: 2.2rem;}}
.st-key-hud_actions button[kind="primary"] {{background: rgb({GOLD}) !important; color: #1a120a !important;}}
.ll-badge {{position: fixed; top: 16px; left: max(calc((100vw - {SCENE_W}) / 2 + 18px), 64px); z-index: 50;
    display: flex; gap: 10px; align-items: center; pointer-events: none;}}
.ll-badge b {{font: 700 12px/1 sans-serif; letter-spacing: .15em; padding: 7px 10px; border-radius: 8px; color: #fff;}}
.ll-badge span {{font: 20px Georgia, serif; color: #f4ead8; text-shadow: 0 2px 6px #000;}}
.ll-badge i {{font: 12px sans-serif; color: #f4ead8; opacity: .8; text-shadow: 0 1px 4px #000; font-style: normal;}}
.ll-sub {{position: fixed; z-index: 40; left: 50%; transform: translateX(-50%); bottom: 152px;
    width: min(820px, 80vw); padding: 12px 20px; border-radius: 14px; background: rgba(10, 8, 6, .8);
    border: 1px solid rgba({GOLD}, .3); color: #f4ead8; font: 17px/1.5 Georgia, serif; text-align: center;
    pointer-events: none;}}
.ll-vignette {{position: fixed; inset: 0; z-index: 1; pointer-events: none;
    background: radial-gradient(ellipse at center, transparent 58%, rgba(0, 0, 0, .55));}}
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] {{background: transparent !important;}}
[data-testid="stBottomBlockContainer"] {{max-width: min(820px, 80vw) !important; padding: 0 0 14px !important;}}
[data-testid="stChatInput"] {{background: rgba(14, 11, 8, .78) !important; border: 1px solid rgba({GOLD}, .45) !important;
    border-radius: 12px !important;}}
[data-testid="stChatInput"] * {{background: transparent !important;}}
[data-testid="stChatInput"] textarea {{color: #efe4d2 !important;}}
[data-testid="stChatInput"] textarea::placeholder {{color: rgba(239, 228, 210, .55) !important;}}
/* one screen: the scene fills the window, nothing scrolls */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{overflow: hidden !important;}}
[data-testid="stMain"] {{padding-bottom: 0 !important;}}
.block-container {{height: 100vh !important; max-height: 100vh; overflow: hidden !important;}}
.ll-pad {{font: 700 1.2rem/1 'Courier New', monospace; letter-spacing: .4em; text-align: center; color: #7dff9a;
    background: #000; border: 2px solid rgba({GOLD}, .6); border-radius: 8px; padding: 8px 0 8px .4em;}}
</style>
"""


def apply_style() -> None:
    st.html(CSS + '<div class="ll-vignette"></div>')


def badge(version: int) -> None:
    tag, colour, word = BADGE[version]
    st.html(f'<div class="ll-badge"><b style="background:{colour}">{tag}</b>'
            f'<span>🗝️ The Locked Library</span><i>{word}</i></div>')


def subtitle(text: str) -> None:
    """The latest line of the story, like a game subtitle."""
    text = re.sub(r"\*+", "", text).strip()
    st.html(f'<div class="ll-sub">{html.escape(text)}</div>')


def place_actions(box: tuple[int, int, int, int]) -> None:
    """Float the action buttons just below the clicked object (box in room-image pixels)."""
    x = (box[0] + box[2]) / 2 / IMG_W
    y = min(box[3] / IMG_H, 0.78)
    st.html(f"""<style>.st-key-hud_actions {{
        left: calc((100vw - {SCENE_W}) / 2 + {SCENE_W} * {x:.4f}); transform: translateX(-50%);
        top: calc({SCENE_H} * {y:.4f} + 10px);}}</style>""")


def story(messages: list[dict]) -> None:
    """The whole conversation, inside the 📜 popover."""
    with st.container(height=480):
        for msg in messages:
            if msg["role"] == "user":
                st.markdown(f":orange[› {msg['content']}]")
            else:
                st.markdown(msg["content"])


def keypad(on_enter, disabled: bool = False) -> None:
    """Clickable door keypad (inside the 🔢 popover)."""
    code = st.session_state.setdefault("pad_code", "")

    def press(key):
        cur = st.session_state.pad_code
        if key == "⌫":
            st.session_state.pad_code = cur[:-1]
        elif key == "✔":
            st.session_state.pad_code = ""
            on_enter(cur)
        elif len(cur) < 4:
            st.session_state.pad_code = cur + key

    st.html(f'<div class="ll-pad">{html.escape(code.ljust(4, "_"))}</div>')
    for row in (["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["⌫", "0", "✔"]):
        cols = st.columns(3)
        for col, key in zip(cols, row):
            col.button(key, key=f"pad_{key}", width="stretch", on_click=press, args=(key,),
                       disabled=disabled or (key == "✔" and not code),
                       type="primary" if key == "✔" else "secondary")


CHAT_PLACEHOLDER = "Type what you do…"
SLOTS = 4
