"""
Original artwork for the Bomb Squad theme, drawn with Pillow from the game
state: an open briefcase bomb with four module panels, and three cartoon
crew portraits (blindfold, earmuffs, taped mouth).
"""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from . import bomb4 as B

W, H = 1000, 660
WIRE_RGB = {"red": (222, 58, 58), "blue": (58, 116, 226), "yellow": (246, 204, 48), "green": (60, 178, 92),
            "white": (240, 240, 240), "black": (34, 34, 34)}
LED_RGB = {"red": (255, 70, 60), "green": (70, 230, 110), "blue": (80, 150, 255), "yellow": (255, 215, 60),
           "white": (245, 245, 245), "off": (60, 60, 60)}
PANEL, EDGE, METAL = (62, 66, 76), (30, 32, 38), (138, 144, 156)


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _led(d, x, y, colour, r=11):
    d.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3], fill=(20, 20, 22))
    d.ellipse([x - r, y - r, x + r, y + r], fill=LED_RGB[colour])


def _panel(d, box, title, solved):
    d.rounded_rectangle(box, 16, fill=PANEL, outline=EDGE, width=4)
    d.text((box[0] + 16, box[1] + 18), title, fill=(220, 222, 230), font=font(17), anchor="lm")
    x = box[2] - 22
    d.ellipse([x - 10, box[1] + 8, x + 10, box[1] + 28], fill=(70, 230, 110) if solved else (85, 85, 90),
              outline=(20, 20, 20))


# ---------------------------------------------------------------------------
def render_bomb(b: dict, dark: bool = False) -> Image.Image:
    B.refresh(b)
    img = Image.new("RGB", (W, H), (36, 52, 60))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 50):                                   # van wall ribs
        d.line([(x, 0), (x, H)], fill=(42, 60, 70), width=3)
    d.rectangle([0, H - 40, W, H], fill=(28, 38, 44))           # workbench edge

    # briefcase lid
    d.rounded_rectangle([40, 12, W - 40, 150], 22, fill=(52, 40, 34), outline=(24, 18, 14), width=6)
    d.rounded_rectangle([60, 28, W - 60, 136], 14, fill=(30, 30, 34))
    t = int(B.time_left(b))
    colour = (80, 235, 120) if b["status"] == "defused" else (255, 72, 60)
    d.rounded_rectangle([370, 44, 630, 120], 10, fill=(8, 8, 8), outline=(90, 90, 90), width=3)
    d.text((500, 82), f"{t // 60:02d}:{t % 60:02d}", fill=colour, font=font(52), anchor="mm")
    d.text((110, 64), "STRIKES", fill=(200, 200, 210), font=font(15), anchor="lm")
    for i in range(B.MAX_STRIKES):
        x = 120 + i * 44
        on = i < b["strikes"]
        d.rounded_rectangle([x - 12, 82, x + 22, 116], 8, fill=(120, 20, 20) if on else (45, 45, 50))
        d.text((x + 5, 99), "X", fill=(255, 90, 80) if on else (80, 80, 86), font=font(26), anchor="mm")
    d.text((890, 64), "MODULES", fill=(200, 200, 210), font=font(15), anchor="rm")
    for i, m in enumerate(B.MODULES):
        x = 760 + i * 36
        d.ellipse([x, 86, x + 22, 108], fill=(70, 230, 110) if b["solved"][m] else (85, 85, 90), outline=(15, 15, 15))

    # briefcase body
    d.rounded_rectangle([40, 160, W - 40, H - 50], 22, fill=(52, 40, 34), outline=(24, 18, 14), width=6)
    boxes = {"wires": (60, 178, 492, 392), "dpad": (508, 178, 940, 392),
             "numpad": (60, 404, 492, 600), "switches": (508, 404, 940, 600)}
    _wires(d, boxes["wires"], b)
    _dpad(d, boxes["dpad"], b)
    _numpad(d, boxes["numpad"], b)
    _switches(d, boxes["switches"], b)

    if dark:
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 245))
        img.paste(overlay, (0, 0), overlay)
        d = ImageDraw.Draw(img)
        d.text((W // 2, H // 2), "⚡ POWER CUT ⚡", fill=(255, 220, 90), font=font(54), anchor="mm")
        d.text((W // 2, H // 2 + 60), "you can't see anything for a few seconds", fill=(200, 200, 200),
               font=font(22), anchor="mm")
    elif b["status"] in ("defused", "exploded"):
        good = b["status"] == "defused"
        d.rounded_rectangle([230, 250, 770, 400], 24, fill=(20, 120, 55) if good else (160, 24, 24),
                            outline=(200, 255, 210) if good else (255, 205, 70), width=8)
        d.text((500, 325), "DEFUSED!" if good else "BOOM!", fill=(255, 245, 210), font=font(84), anchor="mm")
    return img


def _wires(d, box, b):
    w = b["wires"]
    _panel(d, box, "WIRES", b["solved"]["wires"])
    _led(d, box[2] - 60, box[1] + 18, w["led"], 9)
    n = len(w["colours"])
    x0, x1 = box[0] + 40, box[2] - 40
    for i, c in enumerate(w["colours"]):
        x = x0 + (x1 - x0) * (i + 0.5) / n
        top, bot = box[1] + 48, box[3] - 40
        for y in (top, bot):
            d.rectangle([x - 10, y - 8, x + 10, y + 8], fill=METAL, outline=EDGE)
        rgb, outline = WIRE_RGB[c], (12, 12, 12) if c != "black" else (110, 110, 110)
        if i in w["cut"]:
            for a, z in ((top + 8, top + 60), (bot - 60, bot - 8)):
                d.line([(x, a), (x + 8, z)], fill=outline, width=16)
                d.line([(x, a), (x + 8, z)], fill=rgb, width=11)
        else:
            pts = [(x + 9 * math.sin(t / 18 + i), t) for t in range(top + 8, bot - 7, 4)]
            d.line(pts, fill=outline, width=16)
            d.line(pts, fill=rgb, width=11)
        d.text((x, box[3] - 16), str(i + 1), fill=(225, 225, 225), font=font(17), anchor="mm")


def _dpad(d, box, b):
    p = b["dpad"]
    _panel(d, box, f"D-PAD  stage {min(p['stage'] + 1, B.DPAD_STAGES)}/{B.DPAD_STAGES}", b["solved"]["dpad"])
    _led(d, box[2] - 60, box[1] + 18, p["led"], 9)
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2 + 14
    arm = 58
    for dx, dy, ang in ((0, -1, 90), (0, 1, 270), (-1, 0, 180), (1, 0, 0)):
        x, y = cx + dx * arm, cy + dy * arm
        d.rounded_rectangle([x - 26, y - 26, x + 26, y + 26], 9, fill=(40, 40, 46), outline=EDGE, width=3)
        a = math.radians(ang)
        tip = (x + 18 * math.cos(a), y - 18 * math.sin(a))
        left = (x + 14 * math.cos(a + 2.3), y - 14 * math.sin(a + 2.3))
        right = (x + 14 * math.cos(a - 2.3), y - 14 * math.sin(a - 2.3))
        d.polygon([tip, left, right], fill=(225, 225, 230))
    d.rounded_rectangle([cx - 30, cy - 30, cx + 30, cy + 30], 9, fill=(232, 228, 214), outline=EDGE, width=3)
    if b["solved"]["dpad"]:
        d.text((cx, cy), "✓", fill=(30, 150, 60), font=font(44), anchor="mm")
    elif p["braille"]:
        _braille(d, cx, cy, p["value"])
    else:
        d.text((cx, cy), str(p["value"]), fill=(20, 20, 20), font=font(44), anchor="mm")


BRAILLE = {1: (1,), 2: (1, 2), 3: (1, 4), 4: (1, 4, 5), 5: (1, 5), 6: (1, 2, 4), 7: (1, 2, 4, 5), 8: (1, 2, 5), 9: (2, 4)}


def _braille(d, cx, cy, value):
    pos = {1: (-1, -1), 2: (-1, 0), 3: (-1, 1), 4: (1, -1), 5: (1, 0), 6: (1, 1)}
    for k, (px, py) in pos.items():
        x, y = cx + px * 11, cy + py * 16
        on = k in BRAILLE[value]
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(30, 30, 30) if on else (205, 200, 186))


def _numpad(d, box, b):
    s = b["numpad"]
    _panel(d, box, "MATHS KEYPAD", b["solved"]["numpad"])
    _led(d, box[2] - 60, box[1] + 18, s["led"], 9)
    d.rounded_rectangle([box[0] + 120, box[1] + 34, box[2] - 120, box[1] + 74], 8, fill=(18, 34, 22))
    op = {"×": "x"}.get(s["op"], s["op"])
    d.text(((box[0] + box[2]) // 2, box[1] + 54), f"{s['a']} {op} {s['b']} = ?", fill=(120, 255, 150),
           font=font(28), anchor="mm")
    for p, digit in enumerate(s["layout"]):
        x = box[0] + 56 + (p % 5) * 80
        y = box[1] + 106 + (p // 5) * 52
        d.rounded_rectangle([x - 30, y - 20, x + 30, y + 20], 10, fill=(225, 222, 210), outline=EDGE, width=3)
        d.text((x, y), str(digit), fill=(20, 20, 20), font=font(26), anchor="mm")


def _switches(d, box, b):
    sw = b["switches"]
    _panel(d, box, "SWITCHES", b["solved"]["switches"])
    d.rounded_rectangle([box[0] + 120, box[1] + 38, box[2] - 120, box[1] + 76], 8, fill=(30, 18, 18))
    d.text(((box[0] + box[2]) // 2, box[1] + 57), "  ".join(map(str, sw["digits"])), fill=(255, 150, 120),
           font=font(26), anchor="mm")
    for i in range(5):
        x = box[0] + 46 + i * 66
        _led(d, x, box[1] + 100, sw["lights"][i], 10)
        d.rounded_rectangle([x - 18, box[1] + 120, x + 18, box[1] + 182], 8, fill=(26, 26, 30), outline=EDGE, width=3)
        y = box[1] + 136 if sw["up"][i] else box[1] + 166
        d.rounded_rectangle([x - 14, y - 12, x + 14, y + 12], 6, fill=(230, 230, 236))
        d.text((x, box[3] - 12), str(i + 1), fill=(225, 225, 225), font=font(15), anchor="mm")
    d.rounded_rectangle([box[2] - 78, box[3] - 74, box[2] - 16, box[3] - 30], 10, fill=(200, 60, 60), outline=EDGE, width=3)
    d.text((box[2] - 47, box[3] - 52), "ENTER", fill="white", font=font(15), anchor="mm")


# ---------------------------------------------------------------------------
# Crew portraits (original cartoon characters)
# ---------------------------------------------------------------------------
COLOURS = {"blind": (242, 140, 40), "deaf": (43, 179, 163), "mute": (142, 106, 216)}


@lru_cache(maxsize=16)
def portrait(seat: str, size: int = 150, active: bool = False) -> Image.Image:
    s = 300
    img = Image.new("RGB", (s, s), COLOURS[seat])
    d = ImageDraw.Draw(img)
    d.ellipse([20, 20, 280, 280], fill=tuple(min(255, c + 40) for c in COLOURS[seat]))
    skin, dark = (255, 214, 170), (40, 34, 30)
    d.ellipse([70, 70, 230, 250], fill=skin, outline=dark, width=5)          # head
    d.pieslice([66, 56, 234, 200], 180, 360, fill=(90, 60, 40))                # hair
    if seat == "blind":
        d.rounded_rectangle([58, 130, 242, 168], 12, fill=(30, 30, 34))       # blindfold
        d.line([(242, 150), (268, 178)], fill=(30, 30, 34), width=10)
    else:
        for x in (118, 182):                                                   # eyes
            d.ellipse([x - 12, 138, x + 12, 162], fill="white", outline=dark, width=3)
            d.ellipse([x - 5, 145, x + 5, 157], fill=dark)
    if seat == "deaf":
        d.arc([52, 40, 248, 230], 200, 340, fill=(40, 40, 46), width=14)       # headband
        for x in (64, 236):                                                    # ear muffs
            d.ellipse([x - 30, 140, x + 30, 210], fill=(230, 70, 70), outline=dark, width=5)
    if seat == "mute":
        d.line([(120, 196), (180, 226)], fill=(235, 235, 225), width=18)        # taped mouth
        d.line([(120, 226), (180, 196)], fill=(235, 235, 225), width=18)
    else:
        d.arc([122, 190, 178, 226], 10, 170, fill=dark, width=6)              # mouth
    if active:
        d.rounded_rectangle([4, 4, s - 4, s - 4], 30, outline=(255, 215, 60), width=12)
    return img.resize((size, size))
