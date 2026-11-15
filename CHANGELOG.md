# Changelog

## Version 3 - Point-and-click room
- New `v3/` front end on top of the unchanged V2 backend (engine, parser, narrator).
- `room_renderer.py` draws the library with Pillow from the game state every turn, so the picture always matches the state.
- Clicks are mapped to objects with `hit_test()`; hidden or collected objects are not clickable.
- Context action buttons, a door keypad and "hold an item, then click where to use it" interaction. Buttons send structured actions directly to the engine.
- Typed natural-language commands still work through the V2 parser.
- 4 new tests (click mapping, hidden objects, item removal, rendering every stage).

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
