"""
Shared look for Version 1 and Version 2 (presentation only, no game rules).

Both apps use the same theme (.streamlit/config.toml), the same header, the
same status row and the same panels, so the only differences on screen are
the real ones: V1 has no game state and no validation, V2 has both.
"""

from __future__ import annotations

import html

import streamlit as st

ACCENT = {1: ("#c0661c", "#fbeedd"), 2: ("#2e7d4f", "#e6f3ea")}   # V1 orange, V2 green

CSS = """
<style>
h1, h2, h3, h4 {font-family: Georgia, 'Times New Roman', serif !important;}
section[data-testid="stSidebar"] {border-right: 1px solid #e2d3b8;}
div[data-testid="stMetric"] {background: #f6eddc; border: 1px solid #e2d3b8; border-radius: 10px;
    padding: 8px 14px;}
div[data-testid="stMetricLabel"] p {font-size: .85rem;}
div[data-testid="stMetricValue"] {font-size: 1.6rem;}
.stButton > button {border-radius: 8px;}
div[data-testid="stChatMessage"] {background: #fffaf2; border: 1px solid #eadcc3; border-radius: 10px;}
iframe {border-radius: 10px;}
</style>
"""


def apply_style() -> None:
    st.html(CSS)


def header(version: int, subtitle: str, mode: str) -> None:
    """The same banner in both versions; only colour and wording differ."""
    colour, bg = ACCENT[version]
    name = "INTERACTIVE AI ESCAPE ROOM" if version == 1 else "RELIABLE AI ESCAPE ROOM"
    st.html(f"""<div style="border-left:6px solid {colour};background:{bg};border-radius:10px;padding:12px 18px;
      margin-bottom:6px"><div style="font-size:.78rem;letter-spacing:.15em;color:{colour};font-weight:700;
      font-family:sans-serif">VERSION {version} · {name}</div>
      <div style="font-size:1.9rem;font-weight:700;font-family:Georgia,serif">🗝️ The Locked Library</div>
      <div style="color:#4a3f33">{html.escape(subtitle)}</div>
      <div style="color:#7a6a58;font-size:.82rem;margin-top:2px">{html.escape(mode)}</div></div>""")


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


HOW_TO_PLAY = ("Click an object in the room, or type what you do, e.g. *examine the desk*, *look behind the "
               "painting*, *use the key on the drawer*, *enter 1234 on the door*.")
CHAT_PLACEHOLDER = "...or type what you do, e.g. 'look behind the painting'"
ESCAPED = "🎉 You escaped the Locked Library! Press **Restart** to play again."
