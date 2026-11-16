"""
Manual for the Bomb Squad theme (four modules). The Mute player reads this.
bomb4.py implements exactly these rules, and tests check them case by case.

Left/right and wire numbers are always from the BLIND player's point of view
(wire 1 = the Blind player's far left).
"""

WIRE_COLOURS = ["red", "blue", "yellow", "green", "white", "black"]
WIRE_LEDS = ["red", "green", "blue", "off"]
DPAD_LEDS = ["red", "green", "blue", "yellow"]
NUMPAD_LEDS = ["red", "green", "blue"]
SWITCH_LIGHTS = ["red", "green", "blue", "white"]
DIRECTIONS = ["up", "down", "left", "right"]

SECTIONS = {
    "wires": """### ✂️ Wires
Count the wires first: each count has its own rules. Wire 1 is the Blind player's far LEFT.
Follow the FIRST rule that applies.

**3 wires**
1. LED is red → cut the **last** wire.
2. No green wire → cut the **second** wire.
3. Otherwise → cut the **first** wire.

**4 wires**
1. More than one blue wire → cut the **last blue** wire.
2. LED is off → cut the **third** wire.
3. Last wire is yellow → cut the **first** wire.
4. Otherwise → cut the **second** wire.

**5 wires**
1. LED is green and exactly one black wire → cut the **fourth** wire.
2. No red wire → cut the **first** wire.
3. Last wire is white → cut the **last** wire.
4. Otherwise → cut the **third** wire.

**6 wires**
1. No yellow wire → cut the **third** wire.
2. LED is blue → cut the **fifth** wire.
3. More than one white wire → cut the **last white** wire.
4. Otherwise → cut the **fourth** wire.""",

    "dpad": """### 🎮 D-pad (2 stages)
The centre shows a number from 1 to 9, sometimes in **Braille** - only the Blind player can read
that by touch. Find the direction from the LED colour:

| LED | Rule |
|---|---|
| red | odd → **up**, even → **down** |
| green | below 5 → **left**, 5 or more → **right** |
| blue | 3, 6 or 9 → **down**, otherwise **up** |
| yellow | 4 or less → **right**, otherwise **left** |

After each correct input the module shows a NEW LED and number - call it again.
A wrong input is a strike and also changes the module.""",

    "numpad": """### 🔢 Maths keypad
The screen shows a sum. Work out the result **R**, then:
1. LED is blue → press the **last digit** of R.
2. R is odd and greater than 20 → press the **first digit** of R.
3. R is even → press **R ÷ 7's remainder** (R mod 7).
4. Otherwise → press **9 minus the last digit** of R.

The keys are **jumbled**: press the digit wherever it is on the keypad.""",

    "switches": """### 🎚️ Switch panel (5 switches)
Above each switch is a coloured light, and the panel shows a 5-digit code (one digit per switch).
Set each switch, then press **ENTER**:

| Light | Switch should be |
|---|---|
| red | **up** if its digit is odd, else **down** |
| green | **up** if its digit is 5 or more, else **down** |
| blue | always **down** |
| white | the **same** as the switch to its left (first switch: **up**) |

Don't press ENTER until every switch is confirmed.""",
}

MANUAL_TEXT = ("## 📕 Bomb Squad Manual\nDefuse all four modules before the timer runs out. "
               "Three strikes and it explodes. Any order.\n\n" + "\n\n".join(SECTIONS.values()))
