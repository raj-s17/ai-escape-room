"""
AI Escape Room - Version 3 (Multiplayer)

Built on top of Version 2: the same engine, rules, room and look, now shared
by a whole crew, plus a second theme.
  * a lobby with room codes: friends join from their own browser,
  * 🗝️ The Locked Library, multiplayer - one V2 engine for everyone, the same
    clickable room, a shared team inventory, a team chat,
  * 💣 Bomb Squad - co-op defusal where each player is missing a sense:
    🕶️ Blind holds the tools, 🎧 Deaf sees the bomb, 🤐 Mute has the manual
    and can only use hand signals.
Empty seats are played by Gemini Flash; Python validates every action and
decides what each player can perceive (themes/). Runs without an API key
(offline mode: rule-based teammates and engine narration).

Run:  streamlit run v3/app.py
"""

import base64
import importlib
import io
import os
import re
import sys
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import ImageOps
from streamlit_image_coordinates import streamlit_image_coordinates

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "v2", ROOT / "v3", ROOT):        # V2 engine, V3 modules, shared files
    sys.path.insert(0, str(p))
load_dotenv(ROOT / ".env")

import hub  # noqa: E402
import llm  # noqa: E402
import room_renderer as rr  # noqa: E402
import ui  # noqa: E402
import ui_style  # noqa: E402
from defuse_core import bomb4 as B  # noqa: E402
from defuse_core import squad_art as ART  # noqa: E402
from defuse_core.squad_manual import SECTIONS  # noqa: E402
from game_engine import Action  # noqa: E402
from themes import THEME_INFO, THEMES  # noqa: E402
from themes import bomb_squad as S  # noqa: E402
from themes import library_mp as L  # noqa: E402

# Shared files outside this folder aren't hot-reloaded by Streamlit (same as V1/V2).
rr = importlib.reload(rr)
ui_style = importlib.reload(ui_style)

ITEM_ICONS = {"note": "📜", "brass_key": "🗝️", "uv_flashlight": "🔦", "torn_page": "📄"}
DEMO_SEED = int(os.environ["DEFUSE_SEED"]) if os.getenv("DEFUSE_SEED", "").isdigit() else None  # testing/demos
st.set_page_config(page_title="Locked Library - V3", page_icon="🗝️", layout="wide",
                   initial_sidebar_state="collapsed")
ui_style.apply_style()
ui.inject()


@st.cache_resource
def get_store():
    return hub.new_store()


store = get_store()
client = llm.get_client()
ss = st.session_state
if "sid" not in ss:
    ss.sid = uuid.uuid4().hex
sid = ss.sid


@st.cache_data
def thumbnail(theme: str):
    """Both themes get the same thumbnail size so the cards line up."""
    if theme == "library":
        img = rr.render(L.new_state()["engine"].state)
    else:
        img = ART.render_bomb(B.new_bomb(seed=7))
    return ImageOps.fit(img, (800, 520))


@st.cache_data
def portrait_b64(seat: str, active: bool) -> str:
    buf = io.BytesIO()
    ART.portrait(seat, 92, active=active).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Header (same pattern as V1/V2: badge + title on the left, icon buttons right)
# ---------------------------------------------------------------------------
def header(title: str, chips: list[str], room=None, hint=None, labels: bool = False, again=None):
    with st.container(key="head", horizontal=True):
        ui_style.badge(3, title)
        ui.chips(chips)
        st.space("stretch")
        if room is None:
            return
        if labels:
            st.button("", icon=":material/label:", key="hdr_labels", help="Show object labels",
                      type="primary" if ss.get("labels") else "secondary",
                      on_click=lambda: ss.update(labels=not ss.get("labels")))
        if hint:
            st.button("", icon=":material/lightbulb:", key="hdr_hint", help="Hint", on_click=hint)
        if again:
            st.button("", icon=":material/restart_alt:", key="hdr_again", help="Play again", on_click=again)
        open_ = ss.get("chat_open", True)
        st.button("", icon=":material/chat:" if open_ else ":material/speaker_notes_off:", key="hdr_chat",
                  help="Hide the chat box (play with clicks only)" if open_ else "Show the chat box",
                  on_click=lambda: ss.update(chat_open=not ss.get("chat_open", True)))
        if st.button("", icon=":material/logout:", key="hdr_leave", help="Leave the room"):
            hub.leave_room(store, room["code"], sid)
            ss.pop("code", None)
            st.rerun()


def room_chip(room) -> str:
    return f"Room <b>{room['code']}</b>"


# ---------------------------------------------------------------------------
# Lobby
# ---------------------------------------------------------------------------
SEAT_CHOICES = ["blind", "deaf", "mute", "watch"]


def seat_label(s):
    return "👀 Watch the AI play" if s == "watch" else f"{S.SEATS[s]['icon']} {S.SEATS[s]['title']}"


def seat_caption(s):
    return "All three seats are AI; you watch everything." if s == "watch" else \
        f"{S.SEATS[s]['can'].capitalize()} · {S.SEATS[s]['cannot']}"


def lobby():
    ai = (f"<span title='Gemini model: {ui.esc(llm.flash_model(client))}'>🤖 AI teammates on</span>" if client
          else "<span title='Add GEMINI_API_KEY to .env for Gemini'>🤖 AI teammates offline (rules)</span>")
    header("🗝️ AI Escape Room", [ai])
    ui.html_block("<div class='v3-tagline'>Pick a mission, grab a seat, and get out together - "
                  "with friends on their own browsers or with AI teammates.</div>")
    ss.setdefault("theme", "library")
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        ui.step("① Choose your mission")
        for tid, info in THEME_INFO.items():
            chosen = ss.theme == tid
            with st.container(border=True, key=f"card_{tid}"):
                c1, c2 = st.columns([0.85, 1.6], vertical_alignment="center")
                c1.image(thumbnail(tid), width="stretch")
                with c2:
                    tags = "".join(f"<span>{ui.esc(t.strip())}</span>" for t in info["players"].split("·"))
                    picked = "<span class='v3-picked'>✓ Selected</span>" if chosen else ""
                    ui.html_block(f"<div class='v3-card-title'>{info['icon']} {ui.esc(info['title'])}{picked}</div>"
                                  f"<div class='v3-tags'>{tags}</div><div class='v3-blurb'>{ui.esc(info['blurb'])}</div>")
                    if not chosen:      # one gold button on the page: "Create room"
                        st.button("Choose this mission", key=f"pick_{tid}", icon=":material/arrow_forward:",
                                  on_click=lambda t=tid: ss.update(theme=t))
            if chosen:
                ui.selected_card_glow(f"card_{tid}")
        if ss.theme == "bomb":
            ui.step("② Meet the squad: everyone is missing a sense")
            ui.role_cards(S.SEATS)
        else:
            ui.step("② What's inside")
            ui.feature_tiles([
                ("🖱️", "Click anything", "The room is drawn from the game; actions appear next to what you click."),
                ("🎒", "One team inventory", "Anyone can pick things up; hold an item, then click where to use it."),
                ("🧙", "AI Game Master", "Gemini narrates every move for the whole crew; Python keeps the rules."),
            ])
    theme = ss.theme
    info = THEME_INFO[theme]
    with right:
        ui.step("③ Start playing")
        with st.container(key="panel_lobby"):
            ui.html_block(f"<div class='v3-panel-title'>Play {info['icon']} {ui.esc(info['title'])}</div>")
            lobby_forms(theme)


def lobby_forms(theme):
    create_tab, join_tab = st.tabs(["🆕 Create a room", "🤝 Join with a code"])
    with create_tab:
        name = st.text_input("Your name", value=ss.get("name", ""), max_chars=20, key="create_name",
                             placeholder="Player 1")
        opts = {}
        seat = None
        if theme == "bomb":
            choice = st.radio("Your seat (see the squad cards for what each one can do)", SEAT_CHOICES,
                              format_func=seat_label, horizontal=True)
            seat = None if choice == "watch" else choice
            c1, c2 = st.columns(2, vertical_alignment="bottom")
            opts["seconds"] = c1.select_slider("Timer", [180, 300, 480], value=300,
                                               format_func=lambda s: f"{s // 60} min")
            opts["chaos"] = c2.toggle("⚡ Chaos mode", value=True, help="Power cuts and radio static")
            opts["watch"] = choice == "watch"
            st.caption("Empty seats are played by AI teammates.")
        else:
            st.caption("Everyone explores the same room together.")
        ui.how_it_works([("1", "Create a room"), ("2", "Share the 4-letter code"), ("3", "Play together")])
        if st.button("Create room", icon=":material/add_circle:", type="primary", width="stretch", key="create_btn"):
            if not name.strip():
                st.error("Please enter a name.")
            else:
                ss.name = name.strip()
                ss.code = hub.create_room(store, sid, ss.name, theme, seat, seed=DEMO_SEED, **opts)
                st.rerun()
    with join_tab:
        code = st.text_input("Room code", value=st.query_params.get("room", ""), max_chars=4,
                             key="join_code", placeholder="ABCD").strip().upper()
        room = hub.get_room(store, code) if len(code) == 4 else None
        if len(code) == 4 and room is None:
            st.warning("No room with that code.")
        if room:
            rinfo = THEME_INFO[room["theme"]]
            names = ", ".join(p["name"] for p in room["players"].values()) or "nobody yet"
            st.info(f"{rinfo['icon']} **{rinfo['title']}** room · players: {names}")
            name = st.text_input("Name", value=ss.get("name", ""), max_chars=20, key="join_name")
            seat = None
            if THEMES[room["theme"]].SEATS:
                free = [s for s in S.SEATS if hub.seat_holder(room, s) is None]
                if not free:
                    st.error("All three seats are taken.")
                    return
                seat = st.radio("Pick a free seat (it replaces the AI player)", free, format_func=seat_label,
                                horizontal=True, captions=[seat_caption(s) for s in free])
            if st.button("Join room", icon=":material/login:", type="primary", width="stretch", key="join_btn"):
                ok, msg = hub.join_room(store, code, sid, name.strip() or "Friend", seat)
                if ok:
                    ss.name, ss.code = name.strip() or "Friend", msg
                    st.rerun()
                st.error(msg)


# ---------------------------------------------------------------------------
# Sidebar (collapsed by default, as in V2): room code and crew
# ---------------------------------------------------------------------------
def sidebar(room):
    info = THEME_INFO[room["theme"]]
    with st.sidebar:
        st.subheader(f"{info['icon']} Room {room['code']}")
        st.caption(f"{info['title']} · friends join from the lobby with this code")
        crew_list(room["code"])


@st.fragment(run_every=2)
def crew_list(code):
    room = hub.get_room(store, code)
    me = hub.player(room, sid) if room else None
    if me is None:
        return
    st.markdown("**Crew**")
    if THEMES[room["theme"]].SEATS:
        for seat, s in S.SEATS.items():
            holder = hub.seat_holder(room, seat)
            who = room["players"][holder]["name"] if holder else "🤖 AI"
            st.markdown(f"{s['icon']} **{s['title']}**: {who}" + (" *(you)*" if me["seat"] == seat else ""))
        watchers = [p["name"] for p in room["players"].values() if p["seat"] is None]
        if watchers:
            st.caption("👀 Watching: " + ", ".join(watchers))
    else:
        for p in room["players"].values():
            st.markdown(f"🧭 {p['name']}" + (" *(you)*" if p is me else ""))


# ---------------------------------------------------------------------------
# Event log in V2's story style
# ---------------------------------------------------------------------------
def event_lines(room, seat):
    view = THEMES[room["theme"]].event_view
    return [v for e in room["events"][-90:] if (v := view(e, seat)) is not None]


def line_html(e) -> str:
    text = ui.esc(e["text"])
    if e["kind"] == "system":
        return f"<div class='v3-sys'>{text}</div>"
    if e["kind"] == "action":
        return f"<div class='ll-cmd'>› {text}</div>"
    if e["kind"] == "narration":
        return f"<div class='ll-line'>{text}</div>"
    body = f"<span class='v3-sign'>{text}</span>" if e["kind"] == "gesture" else text
    return f"<div class='ll-line'><span class='ll-who'>{ui.esc(e['by'])}</span>: {body}</div>"


def thinking_names(room):
    return [S.SEATS[t]["title"] if t in S.SEATS else "Game Master" for t in room.get("thinking", [])]


def story_log(room, seat=None):
    """Library: V2's story panel (newest at the bottom, older lines fade)."""
    lines = [line_html(e) for e in event_lines(room, seat)]
    with st.container(key="log"):
        for name in thinking_names(room):
            ui.html_block(f"<div class='v3-think'>⏳ {ui.esc(name)} is thinking…</div>")
        for age, h in enumerate(reversed(lines)):
            ui.html_block(f"<div style='opacity:{max(1 - age * 0.12, 0.38):.2f}'>{h}</div>")


def log_container():
    """Scrolling log that stays on the newest message (autoscroll needs a newer Streamlit;
    on older versions it's a plain scrolling box)."""
    try:
        return st.container(height=330, key="feed", autoscroll=True)
    except TypeError:
        return st.container(height=330, key="feed")


def bomb_feed(room, seat, title="📻 What you notice"):
    """Bomb Squad: latest message on top, then the log (as this seat perceives it)."""
    events = event_lines(room, seat)
    latest = next((e for e in reversed(events) if e["kind"] in ("speech", "gesture", "narration")
                   and e.get("seat") != seat and not e.get("muffled")), None)
    if latest:
        tag = {"speech": "Incoming voice", "gesture": "Hand signal", "narration": "Game master"}[latest["kind"]]
        text = ui.esc(latest["text"])
        ui.latest(tag, latest["by"], f"<span class='v3-sign'>{text}</span>" if latest["kind"] == "gesture" else text)
    else:                                            # always shown, so the column layout never jumps
        ui.html_block("<div class='v3-latest'><span class='v3-label'>Incoming</span>"
                      "<span class='v3-sys'>Nothing heard yet…</span></div>")
    if not ss.get("chat_open", True):
        for name in thinking_names(room):
            ui.html_block(f"<div class='v3-think'>⏳ {ui.esc(name)} is thinking…</div>")
        return
    ui.title(title)
    with log_container():
        lines = [line_html(e) for e in events]
        for age, h in enumerate(lines):
            ui.html_block(f"<div style='opacity:{max(1 - (len(lines) - 1 - age) * 0.1, 0.45):.2f}'>{h}</div>")
        for name in thinking_names(room):
            ui.html_block(f"<div class='v3-think'>⏳ {ui.esc(name)} is thinking…</div>")


# ---------------------------------------------------------------------------
# 💣 Bomb Squad
# ---------------------------------------------------------------------------
BOMB_COLS = {"deaf": [1.3, 1, 0.95], "blind": [1, 1, 0.95], "mute": [1.15, 1, 0.95]}


@st.fragment(run_every=1)
def bomb_screen(code):
    show_toasts()
    S.tick(store, code)
    room = hub.get_room(store, code)
    if room is None:
        st.warning("Room closed.")
        return
    me = hub.player(room, sid)
    if me is None:          # left the room while this fragment was refreshing
        return
    seat = me["seat"]
    b = room["state"]["bomb"]
    chaos = B.chaos_now(b)

    # End-of-game banner pops over the screen and fades, so the layout never moves.
    if b["status"] == "defused":
        ui.banner("win", "🎉 Bomb defused!", "The van door unlocks. Your squad escaped!")
    elif b["status"] == "exploded":
        ui.banner("lose", "💥 BOOM!", b["end_reason"] or "")
    ui.fit(262, feed_extra_px=264)

    watchers = [p["name"] for p in room["players"].values() if p["seat"] is None]
    header(f"{THEME_INFO['bomb']['icon']} {THEME_INFO['bomb']['title']}",
           [room_chip(room)] + ([f"👀 {len(watchers)} watching"] if watchers else []), room=room)

    hud, slot = st.columns([5.2, 1], vertical_alignment="center")
    with hud:
        ui.bomb_hud(int(B.time_left(b)), b["seconds"], b["status"], b["strikes"], B.MAX_STRIKES,
                    [(S.MODULE_TITLES[m], b["solved"][m]) for m in B.MODULES], chaos, S.SEATS.get(seat))
    with slot, st.container(key="action_slot"):
        if b["status"] == "waiting":
            st.button("Start", icon=":material/play_arrow:", type="primary", width="stretch", key="start_btn",
                      help="Start the timer when your squad is ready", on_click=lambda: S.start(store, code, sid))
        elif b["status"] == "armed":
            ui.slot_status("run", "💣 DEFUSING…")
        else:
            ui.slot_status("win" if b["status"] == "defused" else "lose",
                           "🎉 Defused" if b["status"] == "defused" else "💥 Boom")
            st.button("Play again", icon=":material/restart_alt:", type="primary", width="stretch",
                      key="again_btn", on_click=lambda: S.new_round(store, code))

    # crew cards: what each player said, as YOU perceive it
    cards = []
    for s_id, s in S.SEATS.items():
        holder = hub.seat_holder(room, s_id)
        you = holder == sid
        thinking = s_id in room.get("thinking", [])
        last = next((v for e in reversed(room["events"])
                     if e.get("seat") == s_id and e["kind"] in ("speech", "gesture")
                     and (v := S.event_view(e, seat)) is not None), None)
        if last is None and s_id == "mute" and any(e.get("seat") == "mute" for e in room["events"]):
            text, cls = "🙌 (signing - you can't see it)", "muted"
        elif last is None:
            text, cls = "…", "muted"
        else:
            text = last["text"]
            cls = "sign" if last["kind"] == "gesture" else "muted" if last.get("muffled") else ""
        tag = ("<span class='tag think'>⏳ thinking</span>" if thinking
               else "<span class='tag you'>you</span>" if you
               else f"<span class='tag'>{'🤖 AI' if not holder else '🧑 player'}</span>")
        cards.append({"icon": s["icon"], "title": s["title"], "me": you, "tag": tag, "text": text, "cls": cls,
                      "full": text, "img": portrait_b64(s_id, you or thinking),
                      "name": room["players"][holder]["name"] if holder else "AI player"})
    ui.crew_strip(cards)

    if seat is None:
        c1, c3 = st.columns([1.9, 1], gap="medium")
        c2 = None
    else:
        c1, c2, c3 = st.columns(BOMB_COLS[seat], gap="medium")
    {"blind": blind_panel, "deaf": deaf_panel, "mute": mute_panel, None: watch_panel}[seat](code, b, chaos, c1, c2)
    with c3, st.container(key="fit_c"):
        bomb_feed(room, seat)
        if ss.get("chat_open", True) and seat in ("blind", "deaf"):
            st.chat_input("Type an action (e.g. cut wire 1) or speak…" if seat == "blind" else
                          "Speak to your squad…", key="bomb_chat",
                          on_submit=lambda: _chat(code, seat, ss.get("bomb_chat") or ""))
        elif ss.get("chat_open", True) and seat == "mute":
            st.chat_input("🤐 Type signs: wires 4, up, yes…", key="mute_chat",
                          on_submit=lambda: _mute_chat(code, ss.get("mute_chat") or ""))

    if b["status"] == "defused" and not ss.get(f"party_{room['state']['round']}"):
        st.balloons()
        ss[f"party_{room['state']['round']}"] = True


def toast_later(msg, icon):
    """Callbacks must not draw; queue the toast and show it on the next refresh."""
    ss.setdefault("toasts", []).append((msg, icon))


def show_toasts():
    for msg, icon in ss.pop("toasts", []):
        st.toast(msg, icon=icon)


def _say(code, text):
    if not text.strip():
        return
    ok, err = S.speak(store, code, sid, text)
    if not ok:
        toast_later(err, "🚫")


SIGN_HELP = ("You can sign: wires, d-pad, keypad, switches, up, down, left, right, 0-9, "
             "yes, no, wait, say again, go back.")


def _mute_chat(code, text):
    """The Mute player can't speak: typed words become hand signals (Deaf sees them, Blind can't)."""
    if not text.strip():
        return
    ok, err, tokens, unknown = S.mute_typed(store, code, sid, text)
    if not tokens:
        toast_later("🤐 You can't speak - those aren't hand signals. " + SIGN_HELP, "🙌")
    elif not ok:
        toast_later(err, "🚫")
    elif unknown:
        toast_later(f"Signed {S.gesture_text(tokens)} (skipped: {', '.join(unknown)}). " + SIGN_HELP, "🙌")


ACTION_HINT = re.compile(r"\b(cut|cutting|snip|clip|press|push|hit|tap|flip|toggle|enter)\b", re.I)


def _chat(code, seat, text):
    """Typed chat. Always said aloud; for the Blind player, typed instructions are also
    carried out (validated on the server exactly like the buttons)."""
    if not text.strip():
        return
    _say(code, text)
    if seat != "blind":
        return
    done = S.blind_typed(store, code, sid, text)
    if not done and ACTION_HINT.search(text):
        toast_later("Couldn't tell what to do - try “cut wire 2”, “press up”, “top row key 3”, "
                    "“flip switch 4” or “enter”.", "🤔")
    for _, r in done:
        if r in ("strike", "exploded"):
            toast_later(B.RESULT_TEXT[r], "💥")
        elif r in ("solved", "defused", "progress"):
            toast_later(B.RESULT_TEXT[r], "✅")
        elif r == "not_started":
            toast_later("Start the timer first.", "⏱️")
        elif r in ("invalid", "already_solved", "game_over"):
            toast_later("That isn't possible right now.", "🚫")


def _touch(code, kind, value=None):
    r = S.touch(store, code, sid, kind, value)
    if r in ("strike", "exploded"):
        toast_later(B.RESULT_TEXT[r], "💥")
    elif r in ("solved", "defused", "progress"):
        toast_later(B.RESULT_TEXT[r], "✅")


def say_buttons(code, phrases, cols=4, prefix="say"):
    for i in range(0, len(phrases), cols):
        for col, (label, text) in zip(st.columns(cols), phrases[i:i + cols]):
            col.button(label, key=f"{prefix}_{label}", width="stretch", on_click=_say, args=(code, text))


def blind_panel(code, b, chaos, c1, c2):
    armed = b["status"] == "armed"
    feel = S.touch_view(b)
    room = hub.get_room(store, code)
    last_heard = next((e["text"] for e in reversed(room["events"]) if e["kind"] == "speech"
                       and e.get("seat") != "blind" and not e.get("static")), "")
    with c1, st.container(key="fit_a"):
        ui.html_block("<div class='v3-blind'><span class='ic'>🕶️</span><b>You can't see.</b><br>"
                      "Listen to the Deaf player and feel the bomb. Repeat every instruction back before you act.</div>")
        ui.title("🗣️ Say")
        say_buttons(code, [("🔁 Repeat back", f"Repeating: {last_heard}" if last_heard else "Say that again?"),
                           ("👍 Ready", "Ready!"), ("❓ Say again?", "Say that again?"), ("✅ Done", "Done! What next?")],
                    cols=2, prefix="bsay")
    with c2, st.container(key="fit_b"):
        ui.title("✋ Feel the bomb")
        tabs = st.tabs(["✂️ Wires", "🎮 D-pad", "🔢 Keypad", "🎚️ Switches"])
        with tabs[0]:
            st.caption(f"You feel **{feel['wire_slots']} wires**, numbered from your left.")
            for col, n in zip(st.columns(feel["wire_slots"]), range(1, feel["wire_slots"] + 1)):
                col.button(f"✂️ {n}", key=f"cut{n}", width="stretch",
                           disabled=not armed or b["solved"]["wires"] or n in feel["cut"],
                           on_click=_touch, args=(code, "cut", n))
        with tabs[1]:
            off = not armed or b["solved"]["dpad"]
            _, up, _ = st.columns(3)
            up.button("⬆️", key="dp_up", width="stretch", disabled=off, on_click=_touch, args=(code, "dpad", "up"))
            lft, mid, rgt = st.columns(3)
            lft.button("⬅️", key="dp_left", width="stretch", disabled=off, on_click=_touch, args=(code, "dpad", "left"))
            if mid.button("✋ feel", key="dp_feel", width="stretch", disabled=off, help="Feel the centre for Braille"):
                ss.felt = (b["dpad"]["rolls"], feel["braille"])
            rgt.button("➡️", key="dp_right", width="stretch", disabled=off, on_click=_touch, args=(code, "dpad", "right"))
            _, dn, _ = st.columns(3)
            dn.button("⬇️", key="dp_down", width="stretch", disabled=off, on_click=_touch, args=(code, "dpad", "down"))
            felt = ss.get("felt")
            if felt and felt[0] == b["dpad"]["rolls"] and not off:      # only valid until the D-pad changes
                if felt[1] is not None:
                    st.info(f"Your fingers read the Braille: **{felt[1]}**")
                    st.button(f"🗣️ Say: The Braille says {felt[1]}", width="stretch",
                              on_click=_say, args=(code, f"The Braille says {felt[1]}."))
                else:
                    st.caption("The centre feels flat - no Braille. The Deaf player can read it.")
        with tabs[2]:
            st.caption("Ten unlabeled keys in two rows. The Deaf player tells you which one.")
            off = not armed or b["solved"]["numpad"]
            for row in range(2):
                for col, p in zip(st.columns(5), range(row * 5, row * 5 + 5)):
                    col.button("●", key=f"key{p}", width="stretch", disabled=off,
                               help=S.key_position_words(p), on_click=_touch, args=(code, "key", p))
        with tabs[3]:
            st.caption("You feel each switch's position. Click to flip, then ENTER.")
            off = not armed or b["solved"]["switches"]
            for i, (col, state) in enumerate(zip(st.columns(5), feel["switches"])):
                col.button(f"{i + 1} {'⬆️' if state == 'up' else '⬇️'}", key=f"sw{i}", width="stretch",
                           help=f"Switch {i + 1} is {state}", disabled=off, on_click=_touch, args=(code, "flip", i))
            st.button("⏎ ENTER", key="enter", type="primary", width="stretch", disabled=off,
                      on_click=_touch, args=(code, "enter"))


def deaf_panel(code, b, chaos, c1, c2):
    with c1, st.container(key="fit_a"):
        ui.title("💣 The bomb")
        st.image(ART.render_bomb(b, dark=chaos == "power"), width="stretch")
        if chaos == "power":
            st.caption("⚡ The lights are out - you can't see a thing until the power comes back.")
    with c2, st.container(key="fit_b"):
        if chaos == "power":
            ui.title("⚡ Power cut")
            st.caption("Wait for the lights. You can still say yes / no / wait.")
        else:
            ui.title("📢 Call out a module")
            short = {**S.MODULE_TITLES, "numpad": "🔢 Keypad"}
            say_buttons(code, [(short[m], S.callout(b, m)) for m in B.MODULES if not b["solved"][m]]
                        + [("📢 Everything", S.callout_all(b)), ("🎧 Use signs!", "I can't hear you - use signs!")],
                        cols=2, prefix="call")
            ui.title("🗣️ Tell the Blind player · from their left")
            t1, t2, t3, t4 = st.tabs(["✂️ Wires", "🎮 D-pad", "🔢 Keypad", "🎚️ Switches"])
            with t1:
                n = len(b["wires"]["colours"])
                st.caption("Say: cut wire …")
                say_buttons(code, [(str(i), f"Cut wire {i} (from your left)!") for i in range(1, n + 1)],
                            cols=n, prefix="dw")
            with t2:
                say_buttons(code, [(a, f"Press D-pad {d}!") for a, d in
                                   (("⬆️", "up"), ("⬇️", "down"), ("⬅️", "left"), ("➡️", "right"))], prefix="dd")
            with t3:
                st.caption("Pick the DIGIT the Mute player signalled - you'll say where it is.")
                layout = b["numpad"]["layout"]
                say_buttons(code, [(str(dg), f"Press the key in the {S.key_position_words(layout.index(dg))}!")
                                   for dg in range(10)], cols=5, prefix="dk")
            with t4:
                states = []
                for i, col in enumerate(st.columns(5)):
                    states.append("up" if col.toggle(f"{i + 1}↑", key=f"dsw{i}", value=True) else "down")
                st.button("📨 Say switch positions", width="stretch", on_click=_say,
                          args=(code, "Switches, left to right: " + ", ".join(states) + " - then ENTER!"))
        ui.title("💬 Quick replies")
        say_buttons(code, [("👍", "Yes!"), ("👎", "No!"), ("✋", "Wait!"), ("↩️", "Go back!")], prefix="dy")


def mute_panel(code, b, chaos, c1, c2):
    with c1, st.container(key="fit_a"):
        tabs = st.tabs(["📕 " + t for t in ("Wires", "D-pad", "Keypad", "Switches")])
        for tab, m in zip(tabs, B.MODULES):
            with tab, st.container(height=270, key=f"manual_{m}"):
                st.markdown(SECTIONS[m])
    with c2, st.container(key="fit_b"):
        ui.title("🙌 Hand signals · Deaf sees them, Blind can't")
        seq = ss.setdefault("mute_seq", [])

        def add(tok):
            if len(seq) < 8:
                seq.append(tok)

        rows = [["m_wires", "m_dpad", "m_numpad", "m_switches"], ["up", "down", "left", "right"],
                [f"n{i}" for i in range(5)], [f"n{i}" for i in range(5, 10)], ["yes", "no", "wait", "repeat", "back"]]
        for toks in rows:
            for col, tok in zip(st.columns(len(toks)), toks):
                emoji, word = S.GESTURES[tok]
                col.button(word if tok.startswith("n") else emoji, key=f"g_{tok}",
                           width="stretch", on_click=add, args=(tok,), help=word)
        ui.html_block(f"<div class='v3-signal'><span class='v3-label'>Your signal</span>"
                      f"{ui.esc(S.gesture_text(seq)) or '…'}</div>")

        def show():
            ok, err = S.signal(store, code, sid, list(seq))
            if not ok:
                toast_later(err, "🚫")
            seq.clear()
        k1, k2 = st.columns([3, 1])
        k1.button("🙌 Show signal", type="primary", width="stretch", disabled=not seq, on_click=show)
        k2.button("Clear", key="mclear", width="stretch", disabled=not seq, on_click=seq.clear)


def watch_panel(code, b, chaos, c1, c2):
    with c1, st.container(key="fit_a"):
        ui.title("👀 Spectator view · each player only gets what their senses allow")
        st.image(ART.render_bomb(b), width="stretch")


# ---------------------------------------------------------------------------
# 🗝️ The Locked Library, multiplayer: V2's screen, shared by the crew
# ---------------------------------------------------------------------------
@st.fragment(run_every=1)
def library_screen(code):
    show_toasts()
    room = hub.get_room(store, code)
    if room is None:
        st.warning("Room closed.")
        return
    state = room["state"]["engine"].state
    names = L.NAMES
    held = ss.get("held") if ss.get("held") in state["inventory"] else None

    def act(action, label):
        L.do_action(store, code, sid, action, label)

    if state["escaped"]:
        ui.banner("win", "🎉 You escaped!", "The door swings open. The Locked Library is behind you.")
    players = ", ".join(p["name"] for p in room["players"].values())
    header("🗝️ The Locked Library",
           [room_chip(room), f"Puzzles {ui.pips(len(state['solved_puzzles']), 4)}",
            f"Code tries <b>{state['code_attempts']}</b>", "🚪 <b>OPEN</b>" if state["escaped"] else "🔒 Locked",
            f"🧭 {ui.esc(players)}"],
           room=room, labels=True,
           hint=None if state["escaped"] else lambda: act(Action("hint"), "💡 asked for a hint"),
           again=(lambda: (L.new_round(store, code), ss.update(lib_party=False))) if state["escaped"] else None)

    with st.container(key="main", horizontal=True):
        # ----- the room (drawn from the shared game state, clickable) ---------------
        with st.container(key="scene"):
            img = rr.render(state, ss.get("sel"), ss.get("labels", False), names, L.CONFIG["season_numbers"])
            click = streamlit_image_coordinates(img, key="libroom", use_column_width="always",
                                                image_format="JPEG", jpeg_quality=90, cursor="pointer")
            if click and click.get("unix_time") != ss.get("last_click"):
                ss.last_click = click["unix_time"]
                ss.sel = rr.hit_test(click["x"] * rr.W / click["width"], click["y"] * rr.H / click["height"], state)
                st.rerun(scope="fragment")
            sel = ss.get("sel") if ss.get("sel") in state["visible"] and ss.get("sel") not in state["inventory"] else None
            if sel and not state["escaped"]:
                ui_style.place_actions(rr._current_hotspots(state["flags"])[sel])
                n = names[sel]
                with st.container(key="hud_actions", horizontal=True):
                    st.button("🔍 Examine", key=f"la_{sel}_x", on_click=act,
                              args=(Action("examine", sel), f"🔍 examined the {n}"))
                    if sel == "painting" and not state["flags"]["painting_moved"]:
                        st.button("🖼️ Look behind", key="la_painting_m", on_click=act,
                                  args=(Action("move", sel), "🖼️ looked behind the painting"))
                    if L.CONFIG["objects"][sel]["takeable"]:
                        st.button("✋ Take", key=f"la_{sel}_t", on_click=act, args=(Action("take", sel), f"✋ took the {n}"))
                    if sel in ("drawer", "door"):
                        st.button("🔓 Open", key=f"la_{sel}_o", on_click=act,
                                  args=(Action("open", sel), f"🔓 tried to open the {n}"))
                    if sel == "globe":
                        st.button("🌍 Spin", key="la_globe_s", on_click=act, args=(Action("move", sel), "🌍 spun the globe"))
                    if sel == "door":
                        with st.popover("🔢 Keypad"):
                            ui_style.keypad(on_enter=lambda c: act(Action("enter_code", "door", code=c),
                                                                   f"🔢 entered {c} on the keypad"))
                    if held and held != sel:
                        st.button(f"{ITEM_ICONS.get(held, '')} Use {names[held]}", key=f"la_{sel}_u", type="primary",
                                  on_click=act, args=(Action("use", held, sel), f"used the {names[held]} on the {n}"))

        # ----- the story (everyone's actions and the Game Master's narration) --------
        story_log(room)

    # ----- bottom: shared inventory slots + command box ------------------------------
    with st.container(key="bottom", horizontal=True):
        items = state["inventory"]
        for i in range(max(ui_style.SLOTS, len(items))):
            if i < len(items):
                item = items[i]
                st.button(ITEM_ICONS.get(item, "•"), key=f"inv_{item}",
                          on_click=lambda it=item: ss.update(held=None if ss.get("held") == it else it),
                          type="primary" if held == item else "secondary",
                          help=f"{names[item]} (team inventory): " + ("holding - click an object to use it"
                                                                      if held == item else "click to hold it"))
            else:
                st.button(" ", key=f"slot_{i}", disabled=True)
        if held:
            st.button("🔍", key="inv_examine", help=f"Examine the {names[held]}",
                      on_click=act, args=(Action("examine", held), f"🔍 examined the {names[held]}"))
        if ss.get("chat_open", True):
            mode = st.segmented_control("Typing sends", ["🎮 Action", "💬 Team chat"], default="🎮 Action",
                                        key="lib_mode", label_visibility="collapsed", width="content")

            def send():
                text = (ss.get("lib_chat") or "").strip()
                if not text:
                    return
                if mode == "💬 Team chat":
                    L.chat(store, code, sid, text)
                else:
                    L.do_text(store, code, sid, text)
            st.chat_input(ui_style.CHAT_PLACEHOLDER if mode != "💬 Team chat" else "Message your team…",
                          key="lib_chat", on_submit=send, disabled=state["escaped"])

    if state["escaped"] and not ss.get("lib_party"):
        st.balloons()
        ss.lib_party = True


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
code = ss.get("code")
room = hub.get_room(store, code) if code else None
me = hub.player(room, sid) if room else None
if not me:
    ss.pop("code", None)
    lobby()
else:
    sidebar(room)
    if room["theme"] == "bomb":
        bomb_screen(code)
    else:
        library_screen(code)
