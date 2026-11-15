# Changelog

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
