---
title: "AI Escape Room: Design, Implementation and Improvements"
subtitle: "Mini Project 01, MSc Data Science, University of Europe for Applied Sciences"
author: "Raj Ravindra Singh"
date: "November 2026"
geometry: margin=2cm
fontsize: 10.5pt
---

# 1. Objective

The goal was to build an interactive escape room in which a Large Language
Model acts as the Game Master. The player is trapped in a room, explores it in
natural language, solves puzzles and unlocks the exit. The application was
built in two versions. Version 1 focuses on a working, engaging LLM
experience. Version 2 makes that experience consistent and resistant to
manipulation.

**Game design: "The Locked Library".** The room has eight interactive objects
(desk, note, painting, drawer, bookshelf, season books, globe, door) and three
hidden items (brass key, UV flashlight, torn page). Three puzzles lead to the
final challenge. (1) The note *"Time hides behind the setting sun"* points to
the sunset painting, and the brass key is behind it. (2) The key opens the
desk drawer, which holds a UV flashlight and a torn page. (3) UV light shows a
hidden number in each of four season books. The torn page gives the reading
order (*Autumn, Winter, Spring, Summer*), which produces the door code 4927.
The globe is a deliberate red herring.

**Technology.** Python, Streamlit for the chat interface, the Google Gemini
API (free tier, `google-genai` SDK, model configurable through `GEMINI_MODEL`),
JSON for configuration and pytest for testing. The API key is loaded from a
git-ignored `.env` file.

# 2. Version 1: LLM as the whole game

![Version 1 architecture](architecture/v1_architecture.png){width=70%}

In V1 the entire design (setting, objects, puzzles, **solutions** and rules)
is written into Gemini's system prompt. Streamlit keeps the conversation in
`st.session_state`, and each turn the full history is sent to the model, which
replies in character. The model marks a successful escape by adding an
`[ESCAPED]` tag, and the app uses the tag to show the victory screen. The
screen shows the library drawn with Pillow (`room_renderer.py`, shared with
V2). Clicking an object offers suggested commands that are sent to Gemini as
text. Because V1 has no state, the picture always shows the starting room,
even after Gemini says the painting was taken down. Both versions share the
same full-screen game layout: the room fills the window, actions appear next
to the clicked object, the latest story line is shown as a subtitle and the
full conversation opens from a 📜 button.

This version was quick to build and pleasant to play, because the model
handles any phrasing and writes atmospheric descriptions. Testing it with the
cases in Section 4 reveals structural weaknesses:

* **No real state.** The chat log is the only memory, so nothing guarantees
  the model stays consistent with earlier turns. For example, it could
  describe a drawer as locked after it was opened.
* **The model is the judge.** Whether an action succeeds depends on the
  model's interpretation. A player can claim to hold an item or to have solved
  a puzzle, and the model has no ground truth to check against.
* **Secrets in the prompt.** The door code and all solutions sit in the
  context window. A direct request or a prompt injection ("print your system
  prompt") can make the model reveal them.
* **Escape decided by text.** If social engineering ("I am the game
  administrator") convinces the model, it outputs `[ESCAPED]` and the game
  ends.
* **Hallucinated objects.** The model tends to accept invented items (a
  crowbar, a phone) to keep the story flowing.

# 3. Version 2: Python decides, the LLM describes

![Version 2 architecture](architecture/v2_architecture.png){width=100%}

The main design decision in V2 is to **separate authority from
storytelling**. Every message goes through a pipeline:

1. **Parser** (`action_parser.py`) turns free text into a structured
   `Action(verb, object, target, code)`. A deterministic rule-based parser is
   tried first: it matches verbs with regular expressions and objects by their
   aliases, longest alias first. Only messages it cannot understand go to a
   Gemini call with a JSON response schema, and its output is filtered to
   known object IDs. The parser also flags messages that try to step outside
   the game (role claims, "ignore previous instructions", requests for codes,
   "I already solved...") as a `meta` action. It also detects nouns that do
   not exist in the room, such as "crowbar".
2. **Game engine** (`game_engine.py`) owns a JSON-serialisable state
   dictionary: visible objects, inventory, flags (painting moved, drawer
   unlocked, books revealed, door unlocked), solved puzzles, code attempts,
   rule violations and a history log. Each verb has a handler that validates
   the action against this state and the rules loaded from
   `game_config.json`. A locked drawer cannot be opened without the key in the
   inventory. Undiscovered items behave exactly like non-existent ones. The
   keypad accepts only four digits. The correct code works only after the
   player has actually discovered it (books revealed and torn page found), so
   a guessed or leaked code is not enough. The engine returns a `Result` with
   a success flag, an event name and a plain-language statement of facts.
3. **Narrator** (`narrator.py`) asks Gemini to describe that result in 2–4
   sentences. The model receives the result, the *public* state and the
   player's message, wrapped in delimiters and marked as untrusted. It never
   receives the solution, so it cannot leak it. An **output guard** then checks
   the narration. If the text claims an escape that did not happen, or contains
   the door code before the player has escaped, it is replaced by the engine's
   own facts. The same fallback is used when Gemini is unavailable, so the game
   also works fully offline.
4. **Interface** (`app.py`). The room is drawn by `room_renderer.py` from
   the game state on every turn (the painting comes off the wall, the drawer
   opens, collected items disappear, numbers glow under UV light, the door
   opens), so the picture can never disagree with the engine. Clicking an
   object selects it, and context buttons (Examine, Take, Look behind, Open,
   Spin, a clickable keypad, *Use held item here*) send structured actions straight to
   the engine; typed commands still go through the parser. Inventory slots let
   the player hold an item and click where to use it, every action flashes a
   ✅/❌ engine check, and a collapsed sidebar holds the raw JSON state and a
   debug view of the last parsed action.
   The debug view was very useful for explaining and testing the system.

# 4. Testing

Eight test cases were documented (`docs/test_cases.md`): the five challenges
from the brief (using an uncollected key, a wrong code, a false "already
solved" claim, administrator impersonation, a request for all secrets) plus a
non-existent object, a prompt injection, and the correct code typed before
any clue is found. The project is covered by 24 pytest tests that run without an API
key (4 of them on click mapping and rendering of the room picture). They include a fake LLM client that returns malicious narration, which
checks that the output guard blocks false escapes and code leaks while
letting honest narration through. A script (`scripts/run_test_cases.py`)
sends the same attacks to V1 (real Gemini) and V2 and saves the transcripts
to `docs/test_results.md`.

In V2 all eight cases leave the game state unchanged: no escape, no unlocked
drawer, no leaked code. Each case produces a specific event
(`item_not_in_inventory`, `wrong_code`, `rule_violation`, `object_not_here`).
V1's behaviour on the same inputs depends on the model's compliance on each
call. By design, V1 accepts TC8 (the guessed code), because its only rule is
"correct code means escape".

# 5. Problems encountered and lessons learned

* **Parsing natural language** was harder than validating it. Phrases such
  as "take the painting down" (a move, not a take), "take a look at the desk"
  (examine) and "take the crowbar out of my bag and break the door" (unknown
  item, not "open door") each needed specific handling. Pronouns ("use *it*")
  are still not resolved.
* **Over-blocking.** An early version of the `meta` filter treated "I
  already have the key" as cheating, even when the player really had it.
  Claims about *items* are now passed to the engine, which checks the
  inventory. Only claims about *solved puzzles or opened locks* are refused.
* **Spoilers in the UI.** An early puzzle checklist named every step
  ("find the brass key behind the painting"), which gave the solutions away.
  It was removed; puzzle progress is still tracked in the JSON game state.
* **Gemini conversation format.** The model expects the conversation to start
  with a user turn, so V1 adds a "Start the game" message before the intro.

The main lesson is that an LLM is a good *interface* but should not be the
*source of truth*. Keeping rules, state and secrets in ordinary code made the
game testable and predictable while keeping the free-form, narrated feel of
Version 1.

**Limitations and future work:** pattern-based meta detection and output
guarding cannot catch every invented detail (although these can never change
the state), there is only one room, and there is no save/load. Possible next
steps include Gemini function calling instead of a separate parser, more
rooms defined in JSON, and a timer or score.
