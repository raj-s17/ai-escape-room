"""
Shared game-style UI for Version 1 and Version 2 (presentation only, no game rules).

Layout ("Option B"), one screen, no scrolling, dark theme only:
  top           version badge + title ............................ 💡 hint  ↻ restart
  left          the room (clickable); actions float next to the clicked object
  right         the story log (newest line at the bottom, older lines fade)
  bottom        inventory slots + command box

Built with Streamlit's own elements (keyed containers, buttons, popover, toast,
chat input, Material icons), following Streamlit's bundled
`developing-with-streamlit` skill. CSS only sizes and positions the keyed
containers (.st-key-<key>), which is the pattern that skill recommends.
"""

from __future__ import annotations

import html
import re

import streamlit as st

GOLD = "217, 163, 91"
BADGE = {1: ("V1", "rgba(192,102,28,.92)", "LLM only"), 2: ("V2", "rgba(46,160,90,.92)", "Reliable"),
         3: ("V3", "rgba(64,112,196,.92)", "Multiplayer")}
IMG_W, IMG_H = 960, 600                     # room_renderer size (16:10)
# Scene height: as tall as the window allows (minus header + bottom row), but leave >= 360px for the story.
SCENE_H = "min(calc(100vh - 190px), calc((100vw - 460px) / 1.6))"
SLOTS = 4

CSS = f"""
<style>
header[data-testid="stHeader"], header[data-testid="stHeader"] div {{background: transparent; pointer-events: none;}}
header[data-testid="stHeader"] button {{pointer-events: auto;}}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{overflow: hidden !important;}}
.block-container {{padding: 14px 28px 0 !important; max-width: 100% !important; height: 100vh; overflow: hidden;}}
iframe {{display: block; border-radius: 14px;}}

/* header row */
.st-key-head {{align-items: center; min-height: 46px; padding: 0 44px 0 36px;}}
.st-key-head button {{width: 44px; height: 44px; border-radius: 12px; border: 1px solid rgba({GOLD}, .5);}}
.ll-badge {{display: flex; gap: 10px; align-items: center;}}
.ll-badge b {{font: 700 12px/1 sans-serif; letter-spacing: .15em; padding: 7px 10px; border-radius: 8px; color: #fff;}}
.ll-badge span {{font: 22px Georgia, serif;}}
.ll-badge i {{font: 12px sans-serif; opacity: .7; font-style: normal;}}

/* room (left) + story (right) */
.st-key-main {{gap: 22px; flex-wrap: nowrap; align-items: flex-start;}}
[data-testid="stLayoutWrapper"]:has(> .st-key-scene) {{flex: none !important; width: calc({SCENE_H} * 1.6) !important;}}
[data-testid="stLayoutWrapper"]:has(> .st-key-log) {{flex: 1 1 0 !important; min-width: 0 !important;
    height: {SCENE_H} !important; align-self: flex-start;}}
.st-key-scene {{position: relative; width: 100% !important; gap: 0;}}
.st-key-log {{min-width: 0; height: 100% !important; max-height: none !important; overflow-y: auto; display: flex;
    flex-direction: column-reverse; justify-content: flex-start; gap: 12px; padding: 16px 18px;
    border-radius: 14px; background: rgba({GOLD}, .06); border: 1px solid rgba({GOLD}, .25);}}
.ll-line {{font: 16px/1.55 Georgia, serif;}}
.ll-cmd {{color: rgb({GOLD}); font: 15px/1.4 Georgia, serif;}}

/* actions floating next to the clicked object (inside the scene) */
.st-key-hud_actions {{position: absolute; z-index: 20; gap: 8px; width: auto !important; transform: translateX(-50%);
    flex-wrap: nowrap;}}
.st-key-hud_actions button {{background: rgba(14, 11, 8, .78) !important; border: 1px solid rgba({GOLD}, .6) !important;
    border-radius: 10px !important; padding: 4px 14px; min-height: 2.2rem; white-space: nowrap;}}
.st-key-hud_actions button[kind="primary"] {{background: rgb({GOLD}) !important; color: #1a120a !important;}}

/* bottom row: inventory slots + command box */
.st-key-bottom {{align-items: center; gap: 10px; margin-top: 4px; flex-wrap: nowrap;}}
.st-key-bottom .stButton button {{width: 60px; height: 60px; border-radius: 12px; border: 1px solid rgba({GOLD}, .4);}}
.st-key-bottom .stButton button p {{font-size: 1.7rem !important; line-height: 1;}}
.st-key-bottom .stButton button[kind="primary"] {{border: 2px solid rgb({GOLD}); box-shadow: 0 0 14px rgba({GOLD}, .6);
    background: rgba({GOLD}, .15);}}
.st-key-bottom [data-testid="stChatInput"] {{flex: 1;}}
button {{transition: transform .1s, box-shadow .15s;}}
button:hover {{box-shadow: 0 0 12px rgba({GOLD}, .45);}}

.ll-pad {{font: 700 1.2rem/1 'Courier New', monospace; letter-spacing: .4em; text-align: center; color: #7dff9a;
    background: #000; border: 2px solid rgba({GOLD}, .6); border-radius: 8px; padding: 8px 0 8px .4em;}}
</style>
"""


def apply_style() -> None:
    st.html(CSS)


def badge(version: int, title: str = "🗝️ The Locked Library") -> None:
    tag, colour, word = BADGE[version]
    st.html(f'<div class="ll-badge"><b style="background:{colour}">{tag}</b>'
            f'<span>{html.escape(title)}</span><i>{word}</i></div>')


def place_actions(box: tuple[int, int, int, int]) -> None:
    """Float the action buttons just below the clicked object (box in room-image pixels)."""
    x = (box[0] + box[2]) / 2 / IMG_W * 100
    y = min(box[3] / IMG_H, 0.86) * 100
    x = min(max(x, 18), 82)                     # keep the buttons inside the scene
    st.html(f"<style>.st-key-hud_actions {{left: {x:.2f}%; top: calc({y:.2f}% + 8px);}}</style>")


def story_log(messages: list[dict]) -> None:
    """Story panel: newest line at the bottom (column-reverse), older lines fade out."""
    with st.container(key="log"):
        for age, msg in enumerate(reversed(messages)):
            text = html.escape(re.sub(r"\*+", "", msg["content"]).strip()).replace("\n", "<br>")
            opacity = max(1 - age * 0.12, 0.38)
            cls, prefix = ("ll-cmd", "› ") if msg["role"] == "user" else ("ll-line", "")
            st.html(f'<div class="{cls}" style="opacity:{opacity:.2f}">{prefix}{text}</div>')


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
