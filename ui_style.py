"""
Shared minimal look for Version 1 and Version 2 (presentation only, no game rules).

* One screen, no page scrolling: a one-line header, the room with its actions
  on the left, the story on the right, the command box at the bottom.
* Works in the light and the dark theme (.streamlit/config.toml defines both):
  colours are semi-transparent tints and text colours are inherited.
* The only differences between the versions are the real ones: V1 has no game
  state and no validation, V2 has both.
"""

from __future__ import annotations

import html

import streamlit as st

ACCENT = {1: "192, 102, 28", 2: "46, 160, 90"}      # V1 orange, V2 green (RGB for rgba())
BRASS = "176, 122, 52"
STORY_HEIGHT = 430

CSS = f"""
<style>
.block-container {{padding-top: 3.2rem; padding-bottom: 0; max-width: 1200px;}}
header[data-testid="stHeader"] {{background: transparent;}}
h4 {{font-family: Georgia, 'Times New Roman', serif !important; margin: 0 !important;}}
.stButton > button {{border-radius: 8px; transition: transform .1s, box-shadow .15s; min-height: 2.1rem;
    padding: .15rem .6rem;}}
.stButton > button:hover {{transform: translateY(-1px); box-shadow: 0 3px 10px rgba({BRASS}, .3);}}
.stButton > button:active {{transform: translateY(1px);}}
div[data-testid="stChatMessage"] {{background: rgba({BRASS}, .06); border: 1px solid rgba({BRASS}, .2);
    border-radius: 10px; padding: .55rem .8rem;}}
iframe {{border-radius: 10px;}}
.ll-bar {{display: flex; align-items: center; gap: 14px; border-left: 5px solid rgb(var(--acc));
    background: rgba(var(--acc), .12); border-radius: 10px; padding: 6px 14px; min-height: 2.6rem; overflow: hidden;}}
.ll-tag {{font: 700 .72rem/1.2 sans-serif; letter-spacing: .14em; color: rgb(var(--acc)); white-space: nowrap;}}
.ll-title {{font: 700 1.35rem/1.2 Georgia, serif; white-space: nowrap;}}
.ll-sub {{opacity: .75; font-size: .85rem; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis;}}
.ll-chip {{font-size: .82rem; border: 1px solid rgba({BRASS}, .35); border-radius: 999px; padding: 2px 10px;
    white-space: nowrap; background: rgba({BRASS}, .07);}}
.ll-check {{font-size: .85rem; border: 1px solid rgba(var(--acc), .45); background: rgba(var(--acc), .08);
    border-radius: 8px; padding: 6px 10px; margin-bottom: 6px; line-height: 1.45;}}
.ll-check code {{font-size: .78rem;}}
.ll-display {{font: 700 1.25rem/1 'Courier New', monospace; letter-spacing: .4em; text-align: center;
    padding: 7px 0 7px .4em; border-radius: 8px; background: rgba(0, 0, 0, .8); color: #7dff9a;
    border: 2px solid rgba({BRASS}, .5);}}
@media (max-height: 820px) {{
  .block-container {{max-width: 980px; padding-top: 2.9rem;}}
  .ll-title {{font-size: 1.15rem;}}
}}
@media (max-width: 1250px) {{ .ll-sub {{display: none;}} }}
</style>
"""


def apply_style() -> None:
    st.html(CSS)


def header(version: int, subtitle: str, chips: list[str]) -> None:
    """One-line banner: version, title, what this version is, and its state chips."""
    name = "VERSION 1 · LLM ONLY" if version == 1 else "VERSION 2 · RELIABLE"
    chip_html = "".join(f'<span class="ll-chip">{html.escape(c)}</span>' for c in chips)
    st.html(f"""<div class="ll-bar" style="--acc:{ACCENT[version]}"><span class="ll-tag">{name}</span>
      <span class="ll-title">🗝️ The Locked Library</span><span class="ll-sub" title="{html.escape(subtitle)}"></span>
      {chip_html}</div>""")


def check(version: int, body_html: str) -> None:
    """Small 'who decided' box above the story (V1: Gemini alone, V2: the engine check)."""
    st.html(f'<div class="ll-check" style="--acc:{ACCENT[version]}">{body_html}</div>')


def story(messages: list[dict], height: int = STORY_HEIGHT) -> None:
    with st.container(height=height):        # Streamlit keeps this scrolled to the newest message
        for msg in messages:
            with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "🧑"):
                st.markdown(msg["content"])


def keypad(on_enter, disabled: bool = False) -> None:
    """Compact clickable door keypad: display + two rows (1-5, 6-0) + delete / enter."""
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

    disp, *keys = st.columns([2.2, 1, 1, 1, 1, 1, 1], gap="small")
    disp.html(f'<div class="ll-display">{html.escape(code.ljust(4, "_"))}</div>')
    for col, key in zip(keys, ["1", "2", "3", "4", "5", "⌫"]):
        col.button(key, key=f"pad_{key}", width="stretch", on_click=press, args=(key,), disabled=disabled)
    _, *keys = st.columns([2.2, 1, 1, 1, 1, 1, 1], gap="small")
    for col, key in zip(keys, ["6", "7", "8", "9", "0", "✔"]):
        col.button(key, key=f"pad_{key}", width="stretch", on_click=press, args=(key,),
                   disabled=disabled or (key == "✔" and not code), type="primary" if key == "✔" else "secondary")


CHAT_PLACEHOLDER = "Type what you do, e.g. 'look behind the painting'"
ESCAPED = "🎉 You escaped! Press ↻ to play again."
