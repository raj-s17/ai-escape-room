"""
AI Escape Room - Version 1 (Interactive AI Escape Room)

In this version the LLM does everything: it holds the room description,
the puzzle solutions and the rules in its system prompt, keeps track of the
story through the chat history, and decides on its own when the player has
escaped. This makes the game quick to build and fun to play, but it also
means the game is only as reliable as the model (see docs/test_cases.md).

Run:  streamlit run v1/app.py
"""

import os

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
ESCAPE_TAG = "[ESCAPED]"

# ---------------------------------------------------------------------------
# Game design - in Version 1 this lives only inside the prompt.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = f"""
You are the Game Master of a text-based escape room called "The Locked Library".
Stay in character, write in second person ("you"), and keep each reply to
2-5 sentences so the game moves quickly. Never break character.

SETTING
The player wakes up in a dusty private library at night. A single window is
barred. The only exit is a heavy oak door with a 4-digit keypad lock.

INTERACTIVE OBJECTS
1. Desk - an old writing desk with a green banker's lamp. On top lies a note:
   "Time hides behind the setting sun." The desk has one locked drawer.
2. Painting - an oil painting of a sunset over the sea, hanging on the wall.
   If the player looks behind it or takes it down, they find a small BRASS KEY
   taped to the back.
3. Drawer - the desk drawer is locked with a keyhole. It opens only with the
   brass key. Inside: a UV FLASHLIGHT and a TORN PAGE that reads:
   "Read the seasons as the poet does: Autumn, Winter, Spring, Summer."
4. Bookshelf - tall shelves. Four books stand out, titled "Spring", "Summer",
   "Autumn" and "Winter". Under normal light their first pages look blank.
   Shining the UV flashlight on them reveals one glowing number in each book:
   Spring = 2, Summer = 7, Autumn = 4, Winter = 9.
5. Globe - an antique globe engraved "Not all who wander are lost." It is a
   red herring: it can be spun and examined but holds no clue.
6. Door - the exit. The keypad accepts a 4-digit code. The correct code is
   the season numbers in the poet's order: 4927.

PUZZLES (in order)
- Puzzle 1: Decode the desk note and find the brass key behind the painting.
- Puzzle 2: Unlock the drawer with the brass key to get the UV flashlight
  and the torn page.
- Puzzle 3: Use the UV flashlight on the season books to reveal the numbers,
  then order them with the torn page.
- Final challenge: Enter 4927 on the door keypad.

RULES
- Describe only the objects listed above. React to what the player does.
- Give gentle hints if the player seems stuck, but do not give away answers.
- Keep track of the items the player has picked up.
- When (and only when) the player enters the correct code 4927 on the door,
  describe the door opening and the player escaping, and end that message
  with the exact tag {ESCAPE_TAG}
"""

INTRO = (
    "You wake up on a cold wooden floor. Candlelight flickers across rows of "
    "old books. The door is locked, and a small keypad glows next to the "
    "handle. Somewhere in this library is the way out..."
)


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------
@st.cache_resource
def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def ask_game_master(client, history):
    """Send the whole conversation to Gemini and return the Game Master reply."""
    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in history
    ]
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.8,
        ),
    )
    return response.text or "(The Game Master stays silent. Try again.)"


def reset_game():
    st.session_state.messages = [{"role": "assistant", "content": INTRO}]
    st.session_state.escaped = False


# ---------------------------------------------------------------------------
# User interface
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Escape Room - V1", page_icon="🗝️")
st.title("🗝️ The Locked Library")
st.caption("Version 1 - the LLM is the whole game")

with st.sidebar:
    st.header("How to play")
    st.markdown(
        "- Type what you want to do in plain English.\n"
        "- Examples: *examine the desk*, *look behind the painting*, "
        "*open the drawer with the key*, *enter 1234 on the door*.\n"
        "- Find the clues, solve the puzzles and unlock the door."
    )
    if st.button("🔄 Restart game", use_container_width=True):
        reset_game()
        st.rerun()

client = get_client()
if client is None:
    st.error(
        "No GEMINI_API_KEY found. Copy `.env.example` to `.env` and add your "
        "free key from Google AI Studio."
    )
    st.stop()

if "messages" not in st.session_state:
    reset_game()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "🧑"):
        st.markdown(msg["content"])

if st.session_state.escaped:
    st.success("🎉 You escaped the Locked Library! Press *Restart game* to play again.")
    st.stop()

if prompt := st.chat_input("What do you do?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🧙"):
        with st.spinner("The Game Master is thinking..."):
            try:
                reply = ask_game_master(client, st.session_state.messages)
            except Exception as exc:  # network / quota errors
                reply = f"⚠️ Could not reach Gemini: {exc}"
        # In V1 the LLM alone decides whether the player escaped.
        if ESCAPE_TAG in reply:
            st.session_state.escaped = True
            reply = reply.replace(ESCAPE_TAG, "").strip()
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    if st.session_state.escaped:
        st.rerun()
