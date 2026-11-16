"""Game themes for Version 3. Each theme module provides:
SEATS, seat_title(), new_state(), perceives(), event_view(), ai_step(), new_round()."""

from . import bomb_squad, library_mp

THEMES = {
    "library": library_mp,
    "bomb": bomb_squad,
}

THEME_INFO = {
    "library": {"icon": "🗝️", "title": "The Locked Library", "players": "1-6 players · everyone explores",
                "blurb": "Explore a locked library together: find the hidden key, reveal secret numbers "
                         "with UV light and crack the door code."},
    "bomb": {"icon": "💣", "title": "Bomb Squad", "players": "1-3 players · 🕶️ Blind · 🎧 Deaf · 🤐 Mute",
             "blurb": "Defuse four modules as a team where everyone is missing a sense. "
                      "Empty seats are played by AI teammates."},
}
