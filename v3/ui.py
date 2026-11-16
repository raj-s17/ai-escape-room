"""
Version 3 look: the same dark old library as Version 1 and 2, extended for
multiplayer (presentation only, no game rules).

The page frame, header row, room scene, floating actions, story log,
inventory slots and keypad come from the shared ui_style.py, so V3 reads as
the next version of V2. This file only adds what V3 needs on top: the lobby,
the Bomb Squad status bar, crew cards, the event log and win / lose banners,
all in the same wood-and-brass palette (.streamlit/config.toml) and Georgia
serif type. On a desktop window every screen fits without scrolling.
"""

from __future__ import annotations

import html

import streamlit as st

from ui_style import GOLD

CSS = f"""
<style>
:root {{ --gold: rgb({GOLD}); --line: rgba({GOLD}, .25); --soft: rgba({GOLD}, .06); --text: #efe4d2;
         --muted: rgba(239, 228, 210, .62); --red: #e0634f; --green: #7dff9a; }}
.block-container {{ padding-bottom: 10px !important; }}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {{ gap: .5rem; }}

/* header extras: chips next to the badge */
.st-key-head [data-testid="stElementContainer"]:has(.ll-badge),
.st-key-head [data-testid="stElementContainer"]:has(.v3-chips) {{ flex: 0 0 auto !important; width: auto !important; }}
.st-key-head {{ gap: 14px; }}
.v3-chips {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
.v3-chip {{ font: 13px/1 Georgia, serif; padding: 7px 10px; border-radius: 9px; border: 1px solid var(--line);
            background: var(--soft); color: var(--text); white-space: nowrap; }}
.v3-chip b {{ color: var(--gold); letter-spacing: .12em; }}
.v3-pips {{ display: inline-flex; gap: 4px; vertical-align: middle; margin-left: 6px; }}
.v3-pips i {{ width: 18px; height: 9px; border-radius: 3px; border: 1px solid var(--line); background: rgba(0,0,0,.35); }}
.v3-pips i.on {{ background: var(--gold); box-shadow: 0 0 8px rgba({GOLD}, .7); border-color: var(--gold); }}

/* panels (keyed containers) share V2's story-log look */
div[class*="st-key-fit_"], div[class*="st-key-panel"], div[class*="st-key-card_"] {{
  background: var(--soft); border: 1px solid var(--line) !important; border-radius: 14px; padding: 12px 14px; }}
.v3-title {{ font: 600 12px/1.2 sans-serif; letter-spacing: .16em; text-transform: uppercase; color: var(--gold);
             margin: 2px 0 4px; }}

/* Bomb Squad status bar */
.v3-hud {{ display: flex; gap: 10px; align-items: stretch; flex-wrap: wrap; }}
.v3-cell {{ display: flex; flex-direction: column; justify-content: center; gap: 4px; padding: 6px 12px;
            border-radius: 12px; border: 1px solid var(--line); background: var(--soft); min-width: 96px; }}
.v3-label {{ font: 600 10px/1 sans-serif; letter-spacing: .2em; text-transform: uppercase; color: var(--muted); }}
.v3-timer {{ font: 700 1.55rem/1 'Courier New', monospace; letter-spacing: .12em; color: var(--green);
             background: #000; border: 2px solid rgba({GOLD}, .6); border-radius: 8px; padding: 5px 10px; text-align: center; }}
.v3-timer.low {{ color: #ff6a55; animation: v3pulse 1s infinite; }}
.v3-timer.idle {{ color: var(--gold); }}
.v3-lamps {{ display: flex; gap: 6px; }}
.v3-lamps i {{ width: 18px; height: 18px; border-radius: 50%; background: #2a1611; border: 1px solid #5a3426; }}
.v3-lamps i.on {{ background: radial-gradient(circle at 35% 35%, #ffb19f, var(--red)); box-shadow: 0 0 10px var(--red); }}
.v3-mods {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.v3-mods span {{ font: 13px/1 Georgia, serif; padding: 4px 8px; border-radius: 8px; border: 1px solid var(--line);
                 color: var(--muted); background: rgba(0,0,0,.25); }}
.v3-mods span.on {{ color: #1a120a; background: var(--gold); border-color: var(--gold); box-shadow: 0 0 8px rgba({GOLD}, .6); }}
.v3-mods b {{ font-weight: 400; margin-left: 4px; }}
.v3-chaos {{ border-color: #e8a33a !important; background: rgba(232, 163, 58, .14) !important; animation: v3pulse .9s infinite; }}
.v3-chaos .v3-val {{ font: 700 15px/1.1 Georgia, serif; color: #f2b45a; }}
.v3-role {{ flex: 1; min-width: 160px; flex-direction: row; align-items: center; gap: 10px; }}
.v3-role .ic {{ font-size: 1.7rem; }}
.v3-role .nm {{ font: 20px/1.1 Georgia, serif; }}
.v3-role .sub {{ font: 13px/1.3 Georgia, serif; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.v3-role > div {{ min-width: 0; }}
.v3-status {{ font: 18px/1.2 Georgia, serif; text-align: center; margin-bottom: 4px; }}
.v3-status.win {{ color: var(--gold); text-shadow: 0 0 10px rgba({GOLD}, .6); }}
.v3-status.lose {{ color: var(--red); }}
.v3-status.run {{ font: 600 11px/1 sans-serif; letter-spacing: .2em; color: var(--muted); }}
div.st-key-start_btn button {{ min-height: 3.4rem !important; font-size: 1.05rem !important; }}
@media (max-width: 1560px) {{ .v3-mods b {{ display: none; }} }}

/* crew cards */
.v3-crew {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
.v3-card {{ display: flex; gap: 10px; align-items: center; padding: 6px 10px; border-radius: 12px; min-width: 0;
            border: 1px solid var(--line); background: var(--soft); }}
.v3-card.me {{ border: 2px solid var(--gold); box-shadow: 0 0 14px rgba({GOLD}, .4); }}
.v3-card img {{ width: 44px; height: 44px; border-radius: 10px; flex: none; }}
.v3-card .info {{ flex: 1; min-width: 0; }}
.v3-card .top {{ font: 15px/1.2 Georgia, serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.v3-card .tag {{ font: 600 10px/1 sans-serif; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin-left: 6px; }}
.v3-card .tag.you {{ color: var(--gold); }} .v3-card .tag.think {{ color: #b8a3ff; animation: v3pulse 1.2s infinite; }}
.v3-bubble {{ margin-top: 4px; padding: 3px 9px; border-radius: 10px; background: #efe4d2; color: #2a2012 !important;
              font: 14px/1.35 Georgia, serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.v3-bubble.sign {{ background: #e7f3ec; font-size: 15px; }}
.v3-bubble.muted {{ color: #7d6f5c !important; font-style: italic; background: #d9ccb6; }}

/* event log: V2's story lines (newest at the bottom, older lines fade) */
.ll-who {{ color: var(--gold); font: 600 14px/1.4 Georgia, serif; }}
.v3-sys {{ color: var(--muted); font: italic 14px/1.45 Georgia, serif; }}
.v3-sign {{ font-size: 1.2rem; letter-spacing: .08rem; }}
.v3-latest {{ border: 1px solid rgba({GOLD}, .6); border-radius: 12px; padding: 8px 12px; background: rgba({GOLD}, .1);
              font: 16px/1.45 Georgia, serif; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
.v3-latest .v3-label {{ display: block; margin-bottom: 3px; color: var(--gold); }}
.v3-think {{ color: #b8a3ff; font: italic 14px Georgia, serif; animation: v3pulse 1.4s infinite; }}

/* seat panels */
.v3-blind {{ border-radius: 14px; padding: 16px; text-align: center; background: radial-gradient(circle at 50% 40%, #1d1712, #000 78%);
             border: 1px solid var(--line); font: 16px/1.5 Georgia, serif; color: #cfc2ad; }}
.v3-blind .ic {{ font-size: 2.2rem; display: block; margin-bottom: 4px; }}
div[class*="st-key-manual_"] {{ background: #efe4d2 !important; border: 3px solid #6b5631 !important; border-radius: 10px; }}
div[class*="st-key-manual_"] * {{ color: #2a2012 !important; font-family: Georgia, serif; }}
.v3-signal {{ font: 700 1.1rem/1.3 'Courier New', monospace; color: var(--green); background: #000;
              border: 2px solid rgba({GOLD}, .6); border-radius: 8px; padding: 8px 12px; min-height: 2.6rem; }}
.v3-signal .v3-label {{ display: block; margin-bottom: 4px; }}

/* lobby */
.v3-tagline {{ font: 15px/1.4 Georgia, serif; color: var(--muted); }}
.v3-step {{ font: 600 12px/1 sans-serif; letter-spacing: .2em; text-transform: uppercase; color: var(--gold); margin: 6px 0 2px; }}
.v3-card-title {{ font: 22px/1.2 Georgia, serif; margin: 0 0 4px; }}
.v3-tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }}
.v3-tags span {{ font: 12px/1 sans-serif; padding: 4px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--muted); }}
.v3-blurb {{ font: 14px/1.4 Georgia, serif; color: var(--muted); margin-bottom: 6px;
             display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.v3-roles {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
.v3-rolecard {{ border-radius: 12px; border: 1px solid var(--line); background: var(--soft); padding: 8px 12px; }}
.v3-rolecard .h {{ font: 18px/1.2 Georgia, serif; }}
.v3-rolecard .t {{ font: 600 10px/1 sans-serif; letter-spacing: .16em; text-transform: uppercase; color: var(--gold); }}
.v3-rolecard p {{ font: 13px/1.35 Georgia, serif; color: var(--muted); margin: 4px 0 0; }}

.v3-picked {{ font: 600 11px/1 sans-serif; letter-spacing: .14em; text-transform: uppercase; color: #1a120a;
              background: var(--gold); border-radius: 999px; padding: 4px 9px; margin-left: 10px; vertical-align: middle; }}
.v3-panel-title {{ font: 24px/1.2 Georgia, serif; margin: 0 0 2px; }}
.v3-steps {{ display: flex; gap: 8px; margin: 2px 0 4px; }}
.v3-steps div {{ flex: 1; display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 10px;
                 border: 1px dashed var(--line); font: 14px/1.25 Georgia, serif; color: var(--muted); }}
.v3-steps b {{ flex: none; width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center;
               background: rgba({GOLD}, .18); color: var(--gold); font: 700 12px/1 sans-serif; }}
.v3-tiles {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
.v3-tile {{ border-radius: 12px; border: 1px solid var(--line); background: var(--soft); padding: 10px 12px; }}
.v3-tile .h {{ font: 18px/1.2 Georgia, serif; margin-bottom: 4px; }}
.v3-tile p {{ font: 13px/1.4 Georgia, serif; color: var(--muted); margin: 0; }}
div[class*="st-key-pick_"] button {{ border-color: rgba({GOLD}, .5) !important; }}

/* win / lose banner: pops over the screen and fades, so nothing moves */
.v3-banner {{ position: fixed; left: 50%; top: 42%; transform: translate(-50%, -50%); z-index: 1000; pointer-events: none;
              width: min(560px, 88vw); text-align: center; padding: 22px 26px; border-radius: 18px; background: #1d150e;
              border: 2px solid var(--gold); box-shadow: 0 0 40px rgba({GOLD}, .45); font: 34px/1.2 Georgia, serif;
              animation: v3pop .45s ease, v3fade .8s ease 4s forwards; }}
.v3-banner small {{ display: block; font-size: 16px; color: var(--muted); margin-top: 6px; }}
.v3-banner.lose {{ border-color: var(--red); box-shadow: 0 0 40px rgba(224, 99, 79, .5); }}

/* one-screen layout (desktop) */
@media (min-width: 1000px) and (min-height: 600px) {{
  div[class*="st-key-fit_"] {{ height: calc(100vh - var(--fit-top, 240px)) !important; flex: none !important;
                              overflow-y: auto; overflow-x: hidden; flex-wrap: nowrap; }}
  div.st-key-feed {{ height: calc(100vh - var(--fit-top, 240px) - var(--feed-extra, 250px)) !important;
                     flex: none !important; min-height: 110px; }}
  [data-testid="stLayoutWrapper"]:has(> .st-key-feed) {{ height: auto !important; min-height: 0 !important; flex: none !important; }}
  div[class*="st-key-manual_"] {{ height: calc(100vh - var(--fit-top, 240px) - 92px) !important; flex: none !important; }}
  div.st-key-fit_a [data-testid="stImage"] img {{ max-height: calc(100vh - var(--fit-top, 240px) - 60px); object-fit: contain; }}
}}
div.st-key-feed {{ background: rgba(0,0,0,.18); border: 1px solid var(--line) !important; border-radius: 12px; }}

@keyframes v3pulse {{ 50% {{ opacity: .45; }} }}
@keyframes v3pop {{ from {{ transform: translate(-50%, -50%) scale(.7); opacity: 0; }} }}
@keyframes v3fade {{ to {{ opacity: 0; visibility: hidden; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style>
"""


def esc(text) -> str:
    return html.escape(str(text))


def inject() -> None:
    st.html(CSS)


def html_block(markup: str) -> None:
    st.html(markup)


def title(text: str) -> None:
    html_block(f"<div class='v3-title'>{text}</div>")


def fit(top_px: int, feed_extra_px: int = 250) -> None:
    """Size the st-key-fit_* columns to the window: top_px is the height used above them."""
    html_block(f"<style>:root {{ --fit-top: {top_px}px; --feed-extra: {feed_extra_px}px; }}</style>")


def chips(items: list[str]) -> None:
    html_block("<div class='v3-chips'>" + "".join(f"<span class='v3-chip'>{i}</span>" for i in items) + "</div>")


def pips(done: int, total: int) -> str:
    return "<span class='v3-pips'>" + "".join(f"<i class='{'on' if i < done else ''}'></i>" for i in range(total)) + "</span>"


# ---------------------------------------------------------------------------
# Bomb Squad status bar, crew, banners
# ---------------------------------------------------------------------------
def _cell(label: str, inner: str, extra: str = "") -> str:
    return f"<div class='v3-cell {extra}'><span class='v3-label'>{label}</span>{inner}</div>"


def bomb_hud(seconds_left: int, total: int, status: str, strikes: int, max_strikes: int,
             modules: list[tuple[str, bool]], chaos: str | None, seat_info: dict | None) -> None:
    mm, sec = divmod(max(0, seconds_left), 60)
    cls = "idle" if status in ("waiting", "defused") else "low" if status == "armed" and seconds_left <= 60 else ""
    cells = _cell("Time", f"<span class='v3-timer {cls}'>{mm:02d}:{sec:02d}</span>")
    cells += _cell("Strikes", "<div class='v3-lamps'>" + "".join(
        f"<i class='{'on' if i < strikes else ''}'></i>" for i in range(max_strikes)) + "</div>")
    cells += _cell("Modules", "<div class='v3-mods'>" + "".join(
        f"<span class='{'on' if done else ''}' title='{esc(t)}'>{esc(t.split(' ', 1)[0])}<b>{esc(t.split(' ', 1)[-1])}</b></span>"
        for t, done in modules) + "</div>")
    alert = {"power": "⚡ Power cut", "static": "📻 Radio static"}.get(chaos)
    if alert:
        cells += _cell("Chaos", f"<span class='v3-val'>{alert}</span>", "v3-chaos")
    if seat_info:
        tip = f"✓ {esc(seat_info['can'])} · ✗ {esc(seat_info['cannot'])}"
        cells += (f"<div class='v3-cell v3-role' title='{tip}'><span class='ic'>{seat_info['icon']}</span><div>"
                  f"<div class='nm'>{esc(seat_info['title'])}</div><div class='sub'>{tip}</div></div></div>")
    else:
        cells += ("<div class='v3-cell v3-role'><span class='ic'>👀</span><div><div class='nm'>Spectator</div>"
                  "<div class='sub'>You see and hear everything. The squad doesn't.</div></div></div>")
    html_block("<div class='v3-hud'>" + cells + "</div>")


def slot_status(kind: str, text: str) -> None:
    html_block(f"<div class='v3-status {kind}'>{text}</div>")


def crew_strip(cards: list[dict]) -> None:
    out = []
    for c in cards:
        out.append(
            f"<div class='v3-card {'me' if c['me'] else ''}' title='{esc(c['full'])}'>"
            f"<img src='data:image/png;base64,{c['img']}' alt=''><div class='info'>"
            f"<div class='top'>{c['icon']} {esc(c['title'])} · {esc(c['name'])}{c['tag']}</div>"
            f"<div class='v3-bubble {c['cls']}'>{esc(c['text'])}</div></div></div>")
    html_block("<div class='v3-crew'>" + "".join(out) + "</div>")


def banner(kind: str, text: str, sub: str = "") -> None:
    html_block(f"<div class='v3-banner {kind}'>{text}" + (f"<small>{esc(sub)}</small>" if sub else "") + "</div>")


def latest(tag: str, who: str, text_html: str) -> None:
    html_block(f"<div class='v3-latest'><span class='v3-label'>{tag}</span>"
               f"<span class='ll-who'>{esc(who)}</span>: {text_html}</div>")


# ---------------------------------------------------------------------------
# Lobby
# ---------------------------------------------------------------------------
def step(text: str) -> None:
    html_block(f"<div class='v3-step'>{text}</div>")


def role_cards(seats: dict) -> None:
    html_block("<div class='v3-roles'>" + "".join(
        f"<div class='v3-rolecard'><div class='h'>{s['icon']} {esc(s['title'])}</div>"
        f"<div class='t'>{'speaks' if s['speak'] else 'hand signals only'}</div>"
        f"<p>✓ {esc(s['can'])}<br>✗ {esc(s['cannot'])}</p></div>" for s in seats.values()) + "</div>")


def selected_card_glow(key: str) -> None:
    html_block(f"<style>div.st-key-{key} {{ border: 2px solid var(--gold) !important;"
               f" box-shadow: 0 0 22px rgba({GOLD}, .35) !important; }}</style>")


def feature_tiles(tiles: list[tuple[str, str, str]]) -> None:
    html_block("<div class='v3-tiles'>" + "".join(
        f"<div class='v3-tile'><div class='h'>{icon} {esc(title)}</div><p>{esc(text)}</p></div>"
        for icon, title, text in tiles) + "</div>")


def how_it_works(steps: list[tuple[str, str]]) -> None:
    html_block("<div class='v3-steps'>" + "".join(f"<div><b>{n}</b>{esc(t)}</div>" for n, t in steps) + "</div>")
