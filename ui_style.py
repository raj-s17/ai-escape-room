"""
Shared look and shared interactive widgets for Version 1 and Version 2
(presentation only, no game rules).

* Works in the light AND the dark theme (.streamlit/config.toml defines both):
  custom colours are semi-transparent tints of the accent colours and text
  colours are inherited, so nothing is hard-coded to a light background.
* Both versions use the same header, status row, story panel, on-screen
  keypad and clickable example commands, so the only differences on screen
  are the real ones: V1 has no game state and no validation, V2 has both.
"""

from __future__ import annotations

import html

import streamlit as st

ACCENT = {1: "192, 102, 28", 2: "46, 160, 90"}      # V1 orange, V2 green (RGB for rgba())
BRASS = "176, 122, 52"

CSS = f"""
<style>
h1, h2, h3, h4 {{font-family: Georgia, 'Times New Roman', serif !important;}}
section[data-testid="stSidebar"] {{border-right: 1px solid rgba({BRASS}, .25);}}
div[data-testid="stMetric"] {{background: rgba({BRASS}, .08); border: 1px solid rgba({BRASS}, .28);
    border-radius: 10px; padding: 8px 14px; transition: transform .15s, box-shadow .15s;}}
div[data-testid="stMetric"]:hover {{transform: translateY(-2px); box-shadow: 0 4px 14px rgba({BRASS}, .25);}}
div[data-testid="stMetricLabel"] p {{font-size: .85rem;}}
div[data-testid="stMetricValue"] {{font-size: 1.6rem;}}
.stButton > button {{border-radius: 8px; transition: transform .1s, box-shadow .15s;}}
.stButton > button:hover {{transform: translateY(-1px); box-shadow: 0 3px 10px rgba({BRASS}, .3);}}
.stButton > button:active {{transform: translateY(1px);}}
div[data-testid="stChatMessage"] {{background: rgba({BRASS}, .06); border: 1px solid rgba({BRASS}, .22);
    border-radius: 10px;}}
iframe {{border-radius: 10px;}}
.ll-header {{border-left: 6px solid rgb(var(--acc)); background: rgba(var(--acc), .12); border-radius: 10px;
    padding: 12px 18px; margin-bottom: 6px;}}
.ll-tag {{font: 700 .78rem/1.4 sans-serif; letter-spacing: .15em; color: rgb(var(--acc));}}
.ll-title {{font: 700 1.9rem/1.25 Georgia, serif;}}
.ll-sub {{opacity: .85;}}
.ll-mode {{opacity: .6; font-size: .82rem; margin-top: 2px;}}
.ll-display {{font: 700 1.6rem/1 'Courier New', monospace; letter-spacing: .5em; text-align: center;
    padding: 10px 0 10px .5em; border-radius: 8px; background: rgba(0, 0, 0, .78); color: #7dff9a;
    border: 2px solid rgba({BRASS}, .5); margin-bottom: 6px;}}
</style>
"""


def apply_style() -> None:
    st.html(CSS)


def is_dark() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def header(version: int, subtitle: str, mode: str) -> None:
    """The same banner in both versions; only colour and wording differ."""
    name = "INTERACTIVE AI ESCAPE ROOM" if version == 1 else "RELIABLE AI ESCAPE ROOM"
    st.html(f"""<div class="ll-header" style="--acc:{ACCENT[version]}">
      <div class="ll-tag">VERSION {version} · {name}</div>
      <div class="ll-title">🗝️ The Locked Library</div>
      <div class="ll-sub">{html.escape(subtitle)}</div>
      <div class="ll-mode">{html.escape(mode)}</div></div>""")


def status_row(items, door, code_tries, rule_breaks, notes: dict | None = None) -> None:
    """Same four metrics in both versions. V1 passes '?' / '-' because it tracks nothing."""
    notes = notes or {}
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("🎒 Items", items), ("🚪 Door", door),
                                          ("🔢 Code tries", code_tries), ("⛔ Rule breaks blocked", rule_breaks)]):
        col.metric(label, value, help=notes.get(label))


def story(messages: list[dict], height: int = 400) -> None:
    st.markdown("#### 📖 Story")
    with st.container(height=height):        # Streamlit keeps this scrolled to the newest message
        for msg in messages:
            with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "🧑"):
                st.markdown(msg["content"])


def keypad(on_enter, disabled: bool = False) -> None:
    """Clickable door keypad (0-9, delete, enter). Calls on_enter(code) with the typed digits."""
    code = st.session_state.setdefault("pad_code", "")
    st.html(f'<div class="ll-display">{html.escape(code.ljust(4, "_"))}</div>')

    def press(key):
        cur = st.session_state.pad_code
        if key == "⌫":
            st.session_state.pad_code = cur[:-1]
        elif key == "✔":
            st.session_state.pad_code = ""
            on_enter(cur)
        elif len(cur) < 4:
            st.session_state.pad_code = cur + key

    for row in (["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["⌫", "0", "✔"]):
        cols = st.columns(3)
        for col, key in zip(cols, row):
            col.button(key, key=f"pad_{key}", width="stretch", on_click=press, args=(key,),
                       disabled=disabled or (key == "✔" and not code),
                       type="primary" if key == "✔" else "secondary")


def quick_commands(commands: list[str], on_pick, disabled: bool = False) -> None:
    """Clickable example commands (sidebar). Each one is sent as if the player typed it."""
    st.markdown("**▶ Try a command**")
    for cmd in commands:
        st.button(cmd, key=f"try_{cmd}", width="stretch", on_click=on_pick, args=(cmd,), disabled=disabled)


THEME_TIP = "🌗 Light or dark: open the ⋮ menu (top right) → Settings → Theme."
HOW_TO_PLAY = ("Click an object in the room, click a command below, or type what you do, e.g. *look behind the "
               "painting*, *use the key on the drawer*, *enter 1234 on the door*.")
EXAMPLES = ["Look around", "Examine the desk", "Read the note", "Look behind the painting", "Hint"]
CHAT_PLACEHOLDER = "...or type what you do, e.g. 'look behind the painting'"
ESCAPED = "🎉 You escaped the Locked Library! Press **Restart** to play again."
