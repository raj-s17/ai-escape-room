"""
Draws the 2D library room with Pillow, based on the current game state.

The picture is generated in Python on every turn, so it always matches the
engine's state: the painting comes off the wall, the drawer slides open,
picked-up items disappear, numbers glow on the books under UV light and
the door opens on escape. HOTSPOTS maps clickable rectangles to object ids.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 960, 600
FLOOR_Y = 430

# Clickable areas: object id -> (x0, y0, x1, y1). Checked in this order, so
# small objects lying on top of bigger ones come first.
HOTSPOTS = {
    "brass_key":     (204, 506, 264, 540),
    "uv_flashlight": (300, 386, 352, 410),
    "torn_page":     (362, 384, 410, 412),
    "note":          (330, 266, 392, 288),
    "season_books":  (560, 168, 668, 236),
    "drawer":        (288, 318, 422, 362),
    "painting":      (228, 66, 404, 196),
    "desk":          (196, 214, 478, 440),
    "globe":         (712, 286, 806, 430),
    "door":          (818, 106, 944, 430),
    "bookshelf":     (514, 56, 706, 430),
}
PAINTING_ON_FLOOR = (30, 446, 190, 556)
OPEN_DRAWER = (288, 362, 422, 414)

SEASON_COLOURS = {"Spring": (92, 160, 92), "Summer": (214, 168, 52),
                  "Autumn": (184, 92, 44), "Winter": (96, 140, 196)}


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def _vgradient(img, box, top, bottom):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        d.line([(x0, y), (x1, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))


def hit_test(x: float, y: float, state: dict) -> str | None:
    """Return the object id at (x, y), skipping objects the player can't see."""
    flags = state["flags"]
    for oid, (x0, y0, x1, y1) in _current_hotspots(flags).items():
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            continue
        if oid not in state["visible"] or oid in state["inventory"]:
            continue
        return oid
    return None


def _current_hotspots(flags: dict) -> dict:
    spots = dict(HOTSPOTS)
    if flags["painting_moved"]:
        spots["painting"] = PAINTING_ON_FLOOR
        spots = {"brass_key": spots.pop("brass_key"), "painting": spots.pop("painting"), **spots}
    if flags["drawer_unlocked"]:
        spots["drawer"] = (288, 318, 422, 414)
    return spots


def render(state: dict, selected: str | None = None, show_labels: bool = False,
           names: dict | None = None, season_numbers: dict | None = None) -> Image.Image:
    f = state["flags"]
    inv = set(state["inventory"])
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)

    # --- wall and floor ---------------------------------------------------
    _vgradient(img, (0, 0, W, FLOOR_Y), (58, 44, 62), (92, 70, 78))
    for x in range(0, W, 48):                      # wallpaper stripes
        d.line([(x, 0), (x, FLOOR_Y)], fill=(84, 64, 74), width=2)
    d.rectangle([0, FLOOR_Y - 14, W, FLOOR_Y], fill=(70, 46, 34))      # skirting board
    _vgradient(img, (0, FLOOR_Y, W, H), (110, 74, 48), (64, 40, 26))
    for i, y in enumerate(range(FLOOR_Y + 22, H, 26)):                  # floor planks
        d.line([(0, y), (W, y)], fill=(58, 36, 24), width=2)
        for x in range((i % 2) * 70, W, 140):
            d.line([(x, y - 26), (x, y)], fill=(58, 36, 24), width=1)

    # --- barred window with moon -------------------------------------------
    d.rectangle([36, 56, 172, 226], fill=(40, 30, 26))
    _vgradient(img, (46, 66, 162, 216), (18, 26, 58), (40, 56, 98))
    d.ellipse([110, 82, 146, 118], fill=(236, 232, 200))
    for x in range(64, 162, 22):
        d.line([(x, 66), (x, 216)], fill=(30, 30, 34), width=5)
    moon = Image.new("L", (W, H), 0)                                      # moonlight on floor
    ImageDraw.Draw(moon).polygon([(46, 216), (162, 216), (260, 560), (40, 560)], fill=38)
    img.paste((190, 200, 240), (0, 0), moon.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)

    # --- painting -----------------------------------------------------------
    def draw_painting(box):
        x0, y0, x1, y1 = box
        d.rectangle(box, fill=(150, 112, 40))
        inner = (x0 + 10, y0 + 10, x1 - 10, y1 - 10)
        mid = (inner[1] + inner[3]) // 2
        _vgradient(img, (inner[0], inner[1], inner[2], mid), (250, 150, 70), (240, 96, 70))
        _vgradient(img, (inner[0], mid, inner[2], inner[3]), (40, 70, 120), (20, 40, 80))
        cx = (inner[0] + inner[2]) // 2
        r = (inner[2] - inner[0]) // 7
        d.pieslice([cx - r, mid - r, cx + r, mid + r], 180, 360, fill=(255, 210, 90))

    if f["painting_moved"]:
        d.rectangle(HOTSPOTS["painting"], fill=(102, 80, 88))               # pale patch on wall
        d.ellipse([312, 58, 320, 66], fill=(40, 40, 40))                     # nail
        draw_painting(PAINTING_ON_FLOOR)
        if "brass_key" not in inv:
            x0, y0, _, _ = HOTSPOTS["brass_key"]
            d.ellipse([x0 + 4, y0 + 6, x0 + 26, y0 + 28], outline=(222, 180, 60), width=5)
            d.rectangle([x0 + 24, y0 + 14, x0 + 56, y0 + 20], fill=(222, 180, 60))
            d.rectangle([x0 + 44, y0 + 20, x0 + 50, y0 + 28], fill=(222, 180, 60))
    else:
        d.line([(316, 62), (238, 76)], fill=(40, 40, 40), width=2)
        d.line([(316, 62), (394, 76)], fill=(40, 40, 40), width=2)
        draw_painting(HOTSPOTS["painting"])

    # --- desk, lamp, note, drawer -------------------------------------------
    d.rectangle([196, 290, 478, 312], fill=(112, 70, 40))                  # desk top
    d.rectangle([206, 312, 468, 380], fill=(92, 56, 32))                   # desk body
    d.rectangle([212, 380, 236, 440], fill=(80, 48, 28))                   # legs
    d.rectangle([438, 380, 462, 440], fill=(80, 48, 28))
    d.rectangle([236, 274, 246, 290], fill=(180, 150, 70))                 # lamp
    d.line([(241, 274), (241, 238)], fill=(180, 150, 70), width=4)
    d.chord([212, 214, 282, 258], 180, 360, fill=(40, 120, 70))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([180, 220, 320, 320], fill=70)
    img.paste((255, 220, 140), (0, 0), glow.filter(ImageFilter.GaussianBlur(25)))
    d = ImageDraw.Draw(img)
    if "note" not in inv:
        d.polygon([(332, 272), (390, 268), (392, 286), (334, 290)], fill=(236, 226, 196))
        for i in range(3):
            d.line([(340, 276 + 4 * i), (382, 274 + 4 * i)], fill=(150, 140, 120), width=1)

    if f["drawer_unlocked"]:
        d.rectangle([288, 318, 422, 362], fill=(40, 24, 14))               # dark slot
        d.rectangle(OPEN_DRAWER, fill=(136, 90, 52), outline=(70, 42, 24), width=3)
        d.rectangle([296, 370, 414, 408], fill=(96, 62, 36))               # inside of drawer
        if "uv_flashlight" not in inv:
            d.rounded_rectangle([302, 388, 346, 404], 5, fill=(50, 50, 60))
            d.rectangle([340, 386, 350, 406], fill=(150, 110, 220))
        if "torn_page" not in inv:
            d.polygon([(366, 386), (406, 386), (402, 398), (408, 410), (364, 410)], fill=(232, 222, 190))
    else:
        d.rectangle([288, 318, 422, 362], fill=(120, 78, 44), outline=(70, 42, 24), width=3)
        d.ellipse([348, 332, 362, 346], fill=(200, 160, 60))               # brass keyhole
        d.rectangle([353, 340, 357, 348], fill=(40, 24, 14))

    # --- bookshelf and season books -----------------------------------------
    x0, y0, x1, y1 = HOTSPOTS["bookshelf"]
    d.rectangle([x0, y0, x1, y1], fill=(76, 46, 28))
    shelf_ys = [y0 + 10 + i * 90 for i in range(5)]
    for sy in shelf_ys:
        d.rectangle([x0 + 8, sy, x1 - 8, sy + 8], fill=(104, 66, 38))
    palette = [(120, 40, 40), (50, 70, 110), (60, 90, 60), (130, 100, 50), (80, 50, 90), (110, 110, 100)]
    for row, sy in enumerate(shelf_ys[:4]):
        bx, i = x0 + 14, row
        while bx < x1 - 22:
            if row == 1 and 556 <= bx <= 668:
                bx = 672
                continue
            w = 12 + (i * 7) % 10
            h = 58 + (i * 13) % 22
            d.rectangle([bx, sy + 8 + 82 - h, bx + w, sy + 90], fill=palette[i % len(palette)])
            bx += w + 3
            i += 1
    sx = 562
    for name, colour in SEASON_COLOURS.items():
        d.rectangle([sx, 172, sx + 22, 190 + 46], fill=colour, outline=(30, 20, 10))
        d.text((sx + 11, 208), name[0], fill=(250, 240, 210), font=_font(14), anchor="mm")
        if f["books_revealed"]:
            halo = Image.new("L", (W, H), 0)
            ImageDraw.Draw(halo).ellipse([sx - 10, 132, sx + 32, 172], fill=150)
            img.paste((190, 120, 255), (0, 0), halo.filter(ImageFilter.GaussianBlur(8)))
            d = ImageDraw.Draw(img)
        sx += 27
    if f["books_revealed"]:
        sx = 562
        for name in SEASON_COLOURS:
            n = (season_numbers or {}).get(name, "?")
            d.text((sx + 11, 152), str(n), fill=(250, 235, 255), font=_font(26), anchor="mm")
            sx += 27

    # --- globe ---------------------------------------------------------------
    d.polygon([(736, 430), (782, 430), (766, 400), (752, 400)], fill=(90, 58, 34))
    d.line([(759, 400), (759, 376)], fill=(90, 58, 34), width=5)
    d.arc([712, 286, 806, 380], 200, 520, fill=(170, 130, 60), width=4)
    d.ellipse([720, 294, 798, 372], fill=(60, 110, 150))
    d.polygon([(736, 316), (756, 306), (764, 330), (746, 344)], fill=(150, 160, 90))
    d.polygon([(770, 340), (786, 332), (790, 356), (772, 360)], fill=(150, 160, 90))

    # --- door ----------------------------------------------------------------
    dx0, dy0, dx1, dy1 = HOTSPOTS["door"]
    d.rectangle([dx0 - 8, dy0 - 8, dx1 + 8, dy1], fill=(60, 38, 24))       # frame
    if state["escaped"]:
        _vgradient(img, (dx0, dy0, dx1, dy1), (250, 240, 200), (200, 180, 130))
        d.polygon([(dx0, dy0), (dx0 + 34, dy0 + 16), (dx0 + 34, dy1 - 6), (dx0, dy1)], fill=(110, 70, 40))
    else:
        d.rectangle([dx0, dy0, dx1, dy1], fill=(110, 70, 40))
        for py in (dy0 + 20, dy0 + 170):
            d.rectangle([dx0 + 16, py, dx1 - 16, py + 120], outline=(84, 52, 30), width=4)
        d.ellipse([dx0 + 12, 268, dx0 + 26, 282], fill=(210, 170, 70))     # handle
    kp = (dx1 - 34, 236, dx1 - 8, 290)
    d.rectangle(kp, fill=(30, 30, 34))
    led = (60, 220, 90) if state["escaped"] else (220, 60, 50)
    d.ellipse([kp[0] + 9, kp[1] + 4, kp[0] + 17, kp[1] + 12], fill=led)
    for r in range(3):
        for c in range(3):
            d.rectangle([kp[0] + 4 + c * 7, kp[1] + 18 + r * 10, kp[0] + 8 + c * 7, kp[1] + 24 + r * 10],
                        fill=(170, 170, 170))

    # --- selection highlight and labels --------------------------------------
    spots = _current_hotspots(f)
    names = names or {}
    if show_labels:
        for oid, box in spots.items():
            if oid in state["visible"] and oid not in inv:
                _label(d, box, names.get(oid, oid), (255, 255, 255))
    if selected and selected in spots:
        d.rounded_rectangle(spots[selected], 6, outline=(255, 214, 80), width=4)
        _label(d, spots[selected], names.get(selected, selected), (255, 214, 80))
    return img


def _label(d, box, text, colour):
    x = (box[0] + box[2]) // 2
    y = max(12, box[1] - 12)
    if text in ("desk", "season books"):    # label underneath, so it does not cover the painting or the glowing numbers
        y = box[3] + 12
    font = _font(15)
    tb = d.textbbox((x, y), text, font=font, anchor="mm")
    d.rounded_rectangle([tb[0] - 6, tb[1] - 3, tb[2] + 6, tb[3] + 3], 5, fill=(20, 16, 24))
    d.text((x, y), text, fill=colour, font=font, anchor="mm")
