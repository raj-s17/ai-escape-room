# Changelog

## Game-style full-screen UI ("Option A")
- Both versions: the room fills the window; actions float next to the clicked object; latest story line as a subtitle; 📜 popover with the whole conversation; 💡 / ↻ buttons; inventory slots; keypad in a popover; no scrolling at 1366x768, 1440x900, 1920x1080.
- Dark theme only (locked in `.streamlit/config.toml`).
- V2 flashes the engine check (✅/❌) as a toast; V1 flashes "Gemini decided alone - no validation".
- Built with Streamlit's own elements (popover, toast, keyed containers, chat input, Material icons) following Streamlit's bundled `developing-with-streamlit` skill; CSS only positions the keyed HUD containers over the scene.

## Minimal one-screen UI
- Both versions fit on one screen without scrolling (checked at 1366×768, 1440×900, 1920×1080, light and dark).
- One-line header with state chips and 💡 / ↻ buttons; compact keypad; V2 inventory row (click to hold); the "Try a command" list, status cards, theme tip and labels toggle were removed; V2's JSON/debug moved to the collapsed sidebar.

## Light/dark theme and more interaction
- `.streamlit/config.toml` defines a light and a dark library palette; custom styles use theme-independent tints, so both versions look the same in either mode.
- Clickable door keypad (digits, delete, enter) in V1 and V2 instead of a text box.
- "Try a command" buttons in the sidebar of both versions; hover/press feedback on buttons and status cards.

## UI polish (final)
- Puzzle checklist and puzzle counter removed (they spoiled the solutions); progress is still tracked in the V2 JSON state.
- One shared library theme for V1 and V2 (`.streamlit/config.toml`, `ui_style.py`): same header, status row, sidebar order, buttons (Hint, Restart), labels, story panel and chat placeholder.
- V1 shows "?" / "-" in the status row and a "Who decided" card (Gemini alone, no validation); V2 shows live state and the engine check.

## Point-and-click room in V1 and V2 (final)
- The point-and-click interface now lives in the two required versions; the separate `v3/` folder is removed.
- `room_renderer.py` (repo root, shared) draws the library with Pillow and maps clicks to objects.
- V2 (`v2/app.py`): the room is redrawn from the game state every turn; context buttons and "hold an item, then click where to use it" send structured actions straight to the engine; typed commands still go through the parser.
- V1 (`v1/app.py`): the same picture, but static (V1 has no state); clicking an object offers suggested commands that are sent to Gemini as text.
- Tests `tests/test_room.py` (click mapping, hidden objects, item removal, rendering every stage); README, report, diagrams and screenshots updated.

## Version 2 - Reliable AI Escape Room
- Game state is now a structured, JSON-serialisable dict: visible objects, inventory, flags, solved puzzles, code attempts, rule violations, history.
- Room, objects, hints and the door code moved out of the prompt into `v2/game_config.json`.
- New `game_engine.py`: Python validates every action. The LLM only narrates the result.
- New `action_parser.py`: rule-based parser with a Gemini JSON parser as fallback; detects admin impersonation, prompt injection, requests for secrets and false progress claims.
- New `narrator.py`: Gemini never sees the solution. An output guard replaces narration that claims a false escape or leaks the code.
- Door code only works after the clues have been discovered, so guessing or leaking it is not enough.
- Offline mode: game and tests run without an API key.
- Sidebar shows inventory, puzzle checklist, door status, counters, JSON state and a debug view of the last action.
- 20 pytest tests plus `scripts/run_test_cases.py` to compare V1 and V2.

## Version 1 - Interactive AI Escape Room
- Streamlit chat UI with Gemini as Game Master.
- Room, five+ interactive objects, three puzzles and a final door code, all defined in the system prompt.
- Conversation memory through the chat history in `st.session_state`.
- Escape detected by an `[ESCAPED]` tag from the model; restart button and instructions in the sidebar.

## Fix - model selection
- `gemini-flash-latest` returned `404 NOT_FOUND` for the v1 API. Default changed to `gemini-2.5-flash`, and the new `gemini_model.py` lists the models available for the key and falls back to the newest Flash model if the configured one does not exist. The UI shows which model is in use.
