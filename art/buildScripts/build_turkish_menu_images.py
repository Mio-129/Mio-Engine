#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_turkish_menu_images.py
============================

Builds the Turkish (tr-TR) menu artwork for Psych Engine.

Nothing is drawn from scratch: every letter is harvested from the original
Friday Night Funkin' menu art that already ships with the game, so the Turkish
strings keep the exact shapes and the stroke weight of the vanilla logo font.

Sources
-------
``assets/shared/images/mainmenu/menu_*.png``
    The big graffiti menu font (solid letters with a thick outline).  Its four
    words - ``STORY MODE``, ``FREEPLAY``, ``CREDITS`` and ``MODS`` - provide the
    letter pool for the main menu entries.

``assets/shared/images/Menu_Tracks.png`` and
``assets/shared/images/menudifficulties/*.png``
    The lighter story menu font, solid in ``TRACKS`` and hollow in
    ``EASY``/``NORMAL``/``HARD``.

``assets/fonts/pixel-latin.ttf``
    The pixel font the title screen prompt is drawn with.

Letters the English art does not contain (B, H, K, L, U, P, Z, ...) are
re-composed from other letters of the very same word art, and the Turkish
diacritics are added on top of the harvested shapes.

Usage
-----
    pip install pillow
    python3 art/buildScripts/build_turkish_menu_images.py

Output
------
Everything lands in ``assets/translations/shared/images/tr-TR/``:

    mainmenu/menu_story_mode.png (+ .xml)
    mainmenu/menu_freeplay.png  (+ .xml)
    mainmenu/menu_credits.png   (+ .xml)
    mainmenu/menu_mods.png      (+ .xml)
    Menu_Tracks.png
    menudifficulties/easy.png
    menudifficulties/normal.png
    menudifficulties/hard.png
    titleEnter.png (+ .xml)
"""

import os
import re
import sys
from collections import deque

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    sys.exit('Pillow is required.  Install it with:  pip install pillow')

# --------------------------------------------------------------------------- #
# paths and text
# --------------------------------------------------------------------------- #

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
SHARED = os.path.join(ROOT, 'assets', 'shared', 'images')
OUT = os.path.join(ROOT, 'assets', 'translations', 'shared', 'images', 'tr-TR')

# the four main menu entries: (asset name, vanilla word, turkish word)
MENU_ITEMS = [
    ('menu_story_mode', 'STORY MODE', u'H\u0130K\u00c2YE MODU'),
    ('menu_freeplay', 'FREEPLAY', 'SERBEST MOD'),
    ('menu_credits', 'CREDITS', 'EMEKLER'),
    ('menu_mods', 'MODS', 'MODLAR'),
]

# the story menu labels: (asset path, vanilla word, turkish word, style)
STORY_LABELS = [
    ('Menu_Tracks', u'PAR\u00c7ALAR', 'tracks'),
    ('menudifficulties/easy', 'KOLAY', 'difficulty'),
    ('menudifficulties/normal', 'NORMAL', 'difficulty'),
    ('menudifficulties/hard', 'ZOR', 'difficulty'),
]

# the title screen prompt
TITLE_TEXT = u"Ba\u015flamak \u0130\u00e7in Enter'a Bas"
TITLE_MAX_WIDTH = 1011

# how tightly the prompt is packed; the alphabet font has no tracking of its
# own because the letters touch each other in the vanilla art
TITLE_TRACKING = 0.022

# --------------------------------------------------------------------------- #
# mask helpers
# --------------------------------------------------------------------------- #


def read_sparrow(png_path, xml_path):
    """Return ``(image, frames)`` of a sparrow atlas."""
    image = Image.open(png_path).convert('RGBA')
    with open(xml_path, encoding='utf-8-sig') as handle:
        source = handle.read()
    frames = []
    for match in re.finditer(r'<SubTexture ([^/]+)/>', source):
        frames.append(dict(re.findall(r'(\w+)="([^"]*)"', match.group(1))))
    return image, frames


def frame_rect(frame):
    return (int(frame['x']), int(frame['y']),
            int(frame['width']), int(frame['height']))


def crop_frame(image, frame):
    x, y, w, h = frame_rect(frame)
    return image.crop((x, y, x + w, y + h))


def new_mask(size):
    return Image.new('L', size, 0)


def solid_mask(frame, colour, tolerance=60):
    """Mask of the pixels matching the body colour of the letters."""
    mask = new_mask(frame.size)
    src = frame.load()
    dst = mask.load()
    for y in range(frame.size[1]):
        for x in range(frame.size[0]):
            r, g, b, a = src[x, y]
            if (a > 128 and abs(r - colour[0]) < tolerance
                    and abs(g - colour[1]) < tolerance
                    and abs(b - colour[2]) < tolerance):
                dst[x, y] = 255
    return mask


def art_mask(frame, threshold=96):
    """Mask of every pixel that is not transparent."""
    mask = new_mask(frame.size)
    src = frame.load()
    dst = mask.load()
    for y in range(frame.size[1]):
        for x in range(frame.size[0]):
            if src[x, y][3] > threshold:
                dst[x, y] = 255
    return mask


def fill_holes(mask):
    """Fill the enclosed transparent areas (the counters of the letters)."""
    width, height = mask.size
    inner = mask.load()
    outside = bytearray(width * height)
    queue = deque()
    for x in range(width):
        for y in (0, height - 1):
            index = y * width + x
            if not inner[x, y] and not outside[index]:
                outside[index] = 1
                queue.append(index)
    for y in range(height):
        for x in (0, width - 1):
            index = y * width + x
            if not inner[x, y] and not outside[index]:
                outside[index] = 1
                queue.append(index)
    while queue:
        index = queue.popleft()
        cy, cx = divmod(index, width)
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                nindex = ny * width + nx
                if not inner[nx, ny] and not outside[nindex]:
                    outside[nindex] = 1
                    queue.append(nindex)
    filled = mask.copy()
    dst = filled.load()
    for index in range(width * height):
        if not outside[index]:
            y, x = divmod(index, width)
            dst[x, y] = 255
    return filled


def components(mask, min_pixels=8):
    """4 connected components -> list of (x0, y0, x1, y1, pixels)."""
    width, height = mask.size
    data = mask.load()
    seen = bytearray(width * height)
    found = []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if not data[x, y] or seen[index]:
                continue
            seen[index] = 1
            stack = [index]
            pixels = []
            min_x = max_x = x
            min_y = max_y = y
            while stack:
                current = stack.pop()
                pixels.append(current)
                cy, cx = divmod(current, width)
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        nindex = ny * width + nx
                        if data[nx, ny] and not seen[nindex]:
                            seen[nindex] = 1
                            stack.append(nindex)
            if len(pixels) >= min_pixels:
                found.append((min_x, min_y, max_x, max_y, pixels))
    return found


def split_letters(mask, letter_count):
    """Cut a word mask into `letter_count` letter masks.

    Neighbouring letters of the logo font touch each other, so the mask is
    eroded until the letters fall apart; the untouched pixels are then flooded
    back from those seeds.  Using the original (un-eroded) pixels keeps every
    letter at its exact original size.

    Returns a list of ``(mask, quality)``; the quality is how much of the
    eroded letter survived the flood, which is high for letters that really
    stand apart and low for letters that were tangled up in a neighbour.
    """
    radius = 0
    seeds = None
    while radius <= 14:
        eroded = erode(mask, radius) if radius else mask
        found = components(eroded)
        if len(found) >= letter_count:
            seeds = found
            break
        radius += 1
    if seeds is None:
        raise ValueError('cannot split a word into %d letters' % letter_count)

    # an erosion step can cut one letter in two: glue the closest pieces back
    while len(seeds) > letter_count:
        seeds.sort(key=lambda component: component[0])
        gaps = sorted((seeds[i + 1][0] - seeds[i][2], i) for i in range(len(seeds) - 1))
        index = gaps[0][1]
        first, second = seeds[index], seeds[index + 1]
        seeds = seeds[:index] + [(
            min(first[0], second[0]), min(first[1], second[1]),
            max(first[2], second[2]), max(first[3], second[3]),
            first[4] + second[4])] + seeds[index + 2:]

    width, height = mask.size
    data = mask.load()
    owner = [-1] * (width * height)
    queue = deque()
    for index, seed in enumerate(seeds):
        for pixel in seed[4]:
            owner[pixel] = index
            queue.append(pixel)
    while queue:
        current = queue.popleft()
        cy, cx = divmod(current, width)
        label = owner[current]
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                nindex = ny * width + nx
                if data[nx, ny] and owner[nindex] < 0:
                    owner[nindex] = label
                    queue.append(nindex)

    letters = []
    for index, seed in enumerate(seeds):
        pixels = [(pixel % width, pixel // width)
                  for pixel, label in enumerate(owner) if label == index]
        letters.append((mask_from_pixels(mask.size, pixels), float(len(seed[4]))))
    letters.sort(key=lambda item: (item[0].getbbox() or (0, 0, 0, 0))[0])
    return letters


def mask_from_pixels(size, pixels):
    mask = new_mask(size)
    data = mask.load()
    for x, y in pixels:
        data[x, y] = 255
    return mask


def trim(mask):
    box = mask.getbbox()
    return mask if box is None else mask.crop(box)


def solidify(mask, threshold=48):
    """Snap a mask back to hard edges.

    Resizing and pasting leave soft grey pixels behind; the game art has none,
    so anything above `threshold` becomes fully solid.
    """
    return mask.point(lambda value: 255 if value > threshold else 0)


def dilate(mask, radius):
    return mask if radius <= 0 else mask.filter(ImageFilter.MaxFilter(radius * 2 + 1))


def erode(mask, radius):
    return mask if radius <= 0 else mask.filter(ImageFilter.MinFilter(radius * 2 + 1))


def band_of(mask, radius):
    """The outline band sitting on the border of a mask."""
    band = new_mask(mask.size)
    band.paste(dilate(mask, radius), (0, 0))
    band.paste(new_mask(mask.size), (0, 0), erode(mask, radius))
    return band


def render_mask(mask, colour):
    """An RGBA image, `colour` where the mask is set."""
    image = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    image.paste(tuple(colour) + (255,), (0, 0), mask)
    return image


def paste_into(base, mask, x, y):
    """OR `mask` into `base` at (x, y), clipping whatever falls outside."""
    width, height = base.size
    source = mask.load()
    target = base.load()
    for source_y in range(mask.size[1]):
        for source_x in range(mask.size[0]):
            px, py = x + source_x, y + source_y
            if 0 <= px < width and 0 <= py < height and source[source_x, source_y]:
                target[px, py] = 255
    return base


def mask_rows(mask):
    """Per row list of the horizontal runs: ``[[(x0, x1), ...], ...]``."""
    width, height = mask.size
    data = mask.load()
    rows = []
    for y in range(height):
        runs = []
        start = None
        for x in range(width + 1):
            on = x < width and data[x, y] > 128
            if on and start is None:
                start = x
            elif not on and start is not None:
                runs.append((start, x - 1))
                start = None
        rows.append(runs)
    return rows


def median_run_length(mask):
    """Median length of the set runs of a row -> the stroke width."""
    runs = []
    for row in mask_rows(mask):
        for start, end in row:
            runs.append(end - start + 1)
    if not runs:
        return 0
    runs.sort()
    return runs[len(runs) // 2]


def capped_line(mask, start, end, width):
    """A straight bar with round caps, drawn on an existing mask."""
    draw = ImageDraw.Draw(mask)
    draw.line([start, end], fill=255, width=int(width))
    radius = width / 2.0
    for x, y in (start, end):
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=255)
    return mask


def rounded_bar(width, height, radius):
    """A rounded rectangle, drawn oversampled so the corners stay smooth."""
    scale = 4
    big = Image.new('L', (width * scale, height * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        [0, 0, width * scale - 1, height * scale - 1], radius=radius * scale, fill=255)
    return big.resize((width, height), Image.LANCZOS)


def dominant_colour(image):
    """The most used opaque colour of an image."""
    counts = {}
    for pixel in image.convert('RGBA').getdata():
        if pixel[3] > 200:
            counts[pixel[:3]] = counts.get(pixel[:3], 0) + 1
    if not counts:
        return (255, 255, 255)
    return max(counts, key=counts.get)


# --------------------------------------------------------------------------- #
# glyphs and fonts
# --------------------------------------------------------------------------- #


class Glyph(object):
    """A letter, stored as a mask that is already cropped to its ink."""

    def __init__(self, mask, cap, gap=None, dy=0):
        if mask.mode != 'L':
            mask = art_mask(mask)
        self.mask = solidify(mask)
        self.cap = cap
        self.width, self.height = self.mask.size
        # some letters of the alphabet font sit a little lower or higher than
        # the rest, which the atlas json carries as a per letter nudge
        self.dy = dy
        # distance from the right edge of this letter to the left edge of the
        # letter that followed it in the source word; negative when they touch
        self.gap = gap

    def scaled(self, height):
        """The same letter, drawn `height` pixels tall."""
        if height == self.height:
            return self
        scale = height / float(self.height)
        width = max(1, int(round(self.width * scale)))
        gap = None if self.gap is None else int(round(self.gap * scale))
        return Glyph(self.mask.resize((width, height), Image.LANCZOS),
                     self.cap, gap, int(round(self.dy * scale)))


class Font(object):
    """A pool of letters plus the metrics used to lay them out again."""

    def __init__(self, name):
        self.name = name
        self.glyphs = {}
        self.fallback_gap = 0.02  # used for letters without a measured gap
        self.space_ratio = 0.32   # word space, relative to the cap height
        self.cap = 0              # reference cap height of the pool
        self.outline = 0          # outline thickness of the source art

    def add(self, letter, glyph):
        self.glyphs.setdefault(letter, glyph)
        self.cap = max(self.cap, glyph.height)

    def override(self, letter, glyph):
        self.glyphs[letter] = glyph
        self.cap = max(self.cap, glyph.height)

    def get(self, letter):
        return self.glyphs[letter]

    def has(self, letter):
        return letter in self.glyphs

    def gap_after(self, glyph):
        """Advance from this glyph to the next one.

        The vanilla words are set very tightly and the letters run into each
        other on purpose, which works for the four English words but not for
        Turkish.  A slice of the cap height is added to every advance and the
        result is never allowed to go negative, so the letters stay readable
        while keeping the tight, hand drawn look.
        """
        if glyph.gap is None:
            return int(round(self.fallback_gap * glyph.cap))
        return max(0, glyph.gap) + int(round(self.fallback_gap * glyph.cap))


def word_glyphs(text, font, cap=None):
    """Turn a string into glyphs (``None`` for a space)."""
    return [None if char == ' ' else font.get(char).scaled(cap or font.cap)
            for char in text]


def compose_word(glyphs, font):
    """Lay glyphs out left to right, all of them sitting on one baseline."""
    height = max((glyph.height for glyph in glyphs if glyph is not None), default=1)
    placements = []
    x = 0
    for glyph in glyphs:
        if glyph is None:
            x += max(1, int(round(height * font.space_ratio)))
            continue
        placements.append((x, glyph))
        x += glyph.width + font.gap_after(glyph)
    canvas = new_mask((max(1, x), height + 16))
    for offset, glyph in placements:
        paste_into(canvas, glyph.mask, offset, height - glyph.height + 8 + glyph.dy)
    return canvas


# --------------------------------------------------------------------------- #
# the big graffiti menu font
# --------------------------------------------------------------------------- #

GRAFFITI_DONORS = [
    ('mainmenu/menu_story_mode', 'STORY MODE'),
    ('mainmenu/menu_freeplay', 'FREEPLAY'),
    ('mainmenu/menu_credits', 'CREDITS'),
    ('mainmenu/menu_mods', 'MODS'),
]

# donors that are a single, evenly spaced word - used to measure the tracking
GRAFFITI_METRIC_DONORS = ('mainmenu/menu_credits', 'mainmenu/menu_mods')


def word_glyphs_from_letters(text, letters, cap):
    """Turn the split letters of a word into glyphs, keeping their advances."""
    boxes = [letter.getbbox() for letter, _ in letters]
    glyphs = []
    for index, (char, (letter, quality)) in enumerate(zip(text.replace(' ', ''), letters)):
        gap = None
        if index + 1 < len(boxes):
            gap = boxes[index + 1][0] - boxes[index][2]
        glyphs.append((char, quality, Glyph(trim(letter), cap, gap)))
    return glyphs


def normalised(mask, cap, width):
    """Scale a letter into a fixed box so letters can be compared."""
    glyph = trim(mask)
    scale = cap / float(glyph.height)
    resized = glyph.resize((max(1, int(round(glyph.width * scale))), cap), Image.LANCZOS)
    box = new_mask((width, cap))
    box.paste(resized, (max(0, (width - resized.width) // 2), 0))
    return box


def choose_glyph(entries):
    """Pick the letter that looks most like the other copies of itself.

    The same letter appears in several words, so the copy closest to the
    consensus of all of them is the cleanest one - it avoids the copies that
    were tangled up in a neighbouring letter when the word was split.
    """
    if len(entries) == 1:
        return entries[0][1]
    cap = 48
    widths = []
    scaled = []
    for _, glyph in entries:
        scale = cap / float(glyph.height)
        widths.append(max(1, int(round(glyph.width * scale))))
        scaled.append(glyph.mask)
    width = max(widths) + 8
    boxes = [normalised(mask, cap, width) for mask in scaled]

    total = [0] * (width * cap)
    for box in boxes:
        data = box.load()
        for y in range(cap):
            for x in range(width):
                if data[x, y] > 128:
                    total[y * width + x] += 1
    consensus = new_mask((width, cap))
    data = consensus.load()
    half = len(boxes) / 2.0
    for y in range(cap):
        for x in range(width):
            if total[y * width + x] >= half:
                data[x, y] = 255

    best = None
    for (quality, glyph), box in zip(entries, boxes):
        first = box.load()
        second = consensus.load()
        inter = union = 0
        for y in range(cap):
            for x in range(width):
                a, b = first[x, y] > 128, second[x, y] > 128
                if a or b:
                    union += 1
                    if a and b:
                        inter += 1
        score = inter / float(union or 1)
        if best is None or score > best[0]:
            best = (score, glyph)
    return best[1]


def harvest_graffiti():
    """Harvest the graffiti menu font out of the four main menu atlases."""
    font = Font('graffiti')
    candidates = {}
    gaps = []
    outlines = []

    for name, text in GRAFFITI_DONORS:
        image, frames = read_sparrow(os.path.join(SHARED, name + '.png'),
                                     os.path.join(SHARED, name + '.xml'))
        idle = [frame for frame in frames if ' idle' in frame['name']][0]
        frame = crop_frame(image, idle)
        body = solid_mask(frame, (0, 0, 0))
        art = art_mask(frame)

        body_box = body.getbbox()
        art_box = art.getbbox()
        cap = body_box[3] - body_box[1]
        outlines.append(min(body_box[0] - art_box[0], body_box[1] - art_box[1],
                            art_box[2] - body_box[2], art_box[3] - body_box[3]))

        letters = split_letters(body, len(text.replace(' ', '')))
        for char, quality, glyph in word_glyphs_from_letters(text, letters, cap):
            candidates.setdefault(char, []).append((quality, glyph))
            if glyph.gap is not None:
                gaps.append(glyph.gap / float(cap))

    # a letter that shows up in several words: keep the cleanest copy
    for char, entries in candidates.items():
        font.add(char, choose_glyph(entries))

    font.outline = int(round(sum(outlines) / float(len(outlines))))
    # the hand drawn letters of the vanilla words differ in size, so a letter
    # that came out much smaller than the rest of the pool is grown back to the
    # common cap height
    for letter, glyph in list(font.glyphs.items()):
        if glyph.height != font.cap:
            font.override(letter, glyph.scaled(font.cap))
    # the hand drawn letters of the logo are set very tight; a single tracking
    # value for the whole pool keeps that look without letters crashing
    font.fallback_gap = 0.035
    add_synthetic_graffiti(font)
    return font


def stem_of(glyph, ratio=0.30):
    """The vertical bar on the left hand side of a letter."""
    width = max(4, int(round(glyph.width * ratio)))
    return glyph.mask.crop((0, 0, width, glyph.height))


def arm_rows(glyph):
    """The rows of the lower right diagonal of a letter (the leg of an R)."""
    rows = mask_rows(glyph.mask)
    found = []
    for y in range(int(glyph.height * 0.5), glyph.height):
        runs = rows[y]
        if len(runs) >= 2 and runs[-1][0] - runs[0][1] > 2:
            found.append((y, runs[0][1], runs[-1]))
    return found


def without_leg(glyph):
    """The letter with its lower right leg erased."""
    rows = mask_rows(glyph.mask)
    found = arm_rows(glyph)
    result = glyph.mask.copy()
    data = result.load()
    if not found:
        return trim(result)
    start = found[0][0]
    for y in range(start, glyph.height):
        runs = rows[y]
        if len(runs) >= 2:
            for x in range(runs[0][1] + 1, glyph.width):
                data[x, y] = 0
    return trim(result)


def add_synthetic_graffiti(font):
    """Build the letters the English main menu art does not contain.

    Every shape comes from a harvested letter, so the stroke weight and the
    corners stay inside the style of the original logo.
    """
    d = font.get('D')
    o = font.get('O')
    p = font.get('P')
    r = font.get('R')
    y = font.get('Y')
    i = font.get('I')
    a = font.get('A')

    stroke = max(3, int(round(d.height * 0.235)))
    stem = stem_of(d, 0.30)

    # U <- the O with its top sliced off
    cut = int(round(o.height * 0.28))
    font.override('U', Glyph(trim(o.mask.crop((0, cut, o.width, o.height))), o.cap))

    # B <- the P with the same bowl repeated lower down, which gives the two
    # lobes of the B, and a bite taken out on the right to make the waist
    bowl = trim(p.mask.crop((int(round(p.width * 0.30)), 0, p.width, p.height)))
    upper = bowl.resize((max(1, int(round(bowl.width * 0.86))),
                         int(round(p.height * 0.52))), Image.LANCZOS)
    lower = bowl.resize((bowl.width, int(round(p.height * 0.58))), Image.LANCZOS)
    width = int(round(p.width * 0.30)) + max(upper.width, lower.width)
    glyph = new_mask((width, p.height))
    paste_into(glyph, p.mask, 0, 0)
    paste_into(glyph, upper, int(round(p.width * 0.30)) - 2, 0)
    paste_into(glyph, lower, int(round(p.width * 0.30)) - 2, p.height - lower.height)
    bite = max(4, int(round(p.height * 0.09)))
    ImageDraw.Draw(glyph).ellipse(
        [width - bite, int(p.height * 0.5) - bite, width + bite, int(p.height * 0.5) + bite],
        fill=0)
    font.override('B', Glyph(trim(glyph), p.cap))

    # L <- a stem of the D with the bottom bar of the E as its foot
    e = font.get('E')
    bar_height = max(4, int(round(e.height * 0.2)))
    bar = trim(e.mask.crop((0, e.height - bar_height, e.width, e.height)))
    width = max(stem.size[0], bar.width)
    glyph = new_mask((width, d.height))
    paste_into(glyph, stem, 0, 0)
    paste_into(glyph, bar, 0, d.height - bar.height)
    font.override('L', Glyph(trim(glyph), d.cap))

    # H <- two stems of the D joined by a crossbar
    width = int(round(d.width * 0.98))
    glyph = new_mask((width, d.height))
    paste_into(glyph, stem, 0, 0)
    paste_into(glyph, stem.transpose(Image.FLIP_LEFT_RIGHT), width - stem.size[0], 0)
    bar = rounded_bar(width - stem.size[0] + 2, stroke, int(stroke / 2.5))
    paste_into(glyph, bar, stem.size[0] - 1, int((d.height - stroke) / 2.0))
    font.override('H', Glyph(trim(glyph), d.cap))

    # K <- the stem of the D plus two arms.  The arms are drawn as capped
    # diagonals so they keep the stroke weight of the rest of the font.
    glyph = new_mask((int(round(d.width * 1.05)), d.height))
    paste_into(glyph, stem, 0, 0)
    junction_x = stem.size[0] - int(round(stem.size[0] * 0.4))
    junction_y = d.height / 2.0
    reach = int(round(d.height * 0.5))
    capped_line(glyph, (junction_x, junction_y), (junction_x + reach, d.height * 0.04), stroke)
    capped_line(glyph, (junction_x, junction_y), (junction_x + reach, d.height * 0.96), stroke)
    font.override('K', Glyph(trim(glyph), d.cap))

    # Turkish letters
    font.override(u'\u0130', Glyph(dotted(i), i.cap))
    font.override(u'\u00c2', Glyph(circumflexed(a), a.cap))


def add_synthetic_difficulty(font):
    """The letters the squared difficulty labels do not contain."""
    r = font.get('R')
    n = font.get('N')
    c = font.get('C') if font.has('C') else None

    # the stroke weight of this typeface
    stroke = max(2, int(round(median_run_length(r.mask) * 0.8)))

    # P <- the R without its leg
    font.override('P', Glyph(without_leg(r), r.cap))

    # K <- the stem of the R plus two capped diagonals
    stem_width = max(3, int(round(r.width * 0.3)))
    glyph = new_mask((r.width, r.height))
    paste_into(glyph, r.mask.crop((0, 0, stem_width, r.height)), 0, 0)
    junction_x = stem_width - max(1, int(round(stem_width * 0.35)))
    junction_y = r.height / 2.0
    reach = r.width - stem_width * 0.6
    capped_line(glyph, (junction_x, junction_y), (junction_x + reach, r.height * 0.06), stroke)
    capped_line(glyph, (junction_x, junction_y), (junction_x + reach, r.height * 0.94), stroke)
    font.override('K', Glyph(trim(glyph), r.cap))

    # Z <- a top bar, a bottom bar and the diagonal of the N between them
    width = int(round(n.width * 1.05))
    glyph = new_mask((width, n.height))
    capped_line(glyph, (stroke / 2.0, stroke / 2.0), (width - stroke / 2.0, stroke / 2.0), stroke)
    capped_line(glyph, (stroke / 2.0, n.height - stroke / 2.0),
                (width - stroke / 2.0, n.height - stroke / 2.0), stroke)
    capped_line(glyph, (width - stroke / 2.0, stroke / 2.0),
                (stroke / 2.0, n.height - stroke / 2.0), stroke)
    font.override('Z', Glyph(trim(glyph), n.cap))

    # Turkish letters
    if c is not None:
        font.override(u'\u00c7', Glyph(cedilla(c), c.cap))


def add_synthetic_tracks(font):
    """The letters the rounded TRACKS label does not contain."""
    r = font.get('R')
    k = font.get('K')
    t = font.get('T')
    c = font.get('C')

    # P <- the R without its leg
    font.override('P', Glyph(without_leg(r), r.cap))

    # L <- the stem of the K plus the bar of the T
    stem = k.mask.crop((0, 0, int(round(k.width * 0.3)), k.height))
    bar = t.mask.crop((0, 0, t.width, int(round(t.height * 0.42))))
    width = int(round(bar.size[0] * 0.95))
    height = max(stem.size[1], bar.size[1])
    glyph = new_mask((max(width, stem.size[0]), r.height))
    paste_into(glyph, stem, 0, 0)
    paste_into(glyph, bar, 0, r.height - bar.size[1])
    font.override('L', Glyph(trim(glyph), r.cap))

    # Turkish letters
    font.override(u'\u00c7', Glyph(cedilla(c), c.cap))


def dotted(glyph):
    """The letter with a round dot above it (Turkish capital dotted I)."""
    dot = max(3, int(round(glyph.height * 0.13)))
    gap = max(3, int(round(glyph.height * 0.13)))
    width = max(glyph.width, dot)
    mask = new_mask((width, glyph.height + gap + dot))
    paste_into(mask, glyph.mask, (width - glyph.width) // 2, 0)
    ImageDraw.Draw(mask).ellipse(
        [width / 2.0 - dot / 2.0, glyph.height + gap,
         width / 2.0 + dot / 2.0, glyph.height + gap + dot], fill=255)
    return trim(mask)


def circumflexed(glyph):
    """The letter with a circumflex above it (Turkish capital A with a hat)."""
    height = max(4, int(round(glyph.height * 0.17)))
    gap = max(3, int(round(glyph.height * 0.12)))
    width = max(glyph.width, int(round(glyph.height * 0.55)))
    mask = new_mask((width, glyph.height + gap + height))
    paste_into(mask, glyph.mask, (width - glyph.width) // 2, 0)
    # a chevron drawn with two strokes, so the hat keeps the stroke weight of
    # the letters underneath it
    thickness = max(4, int(round(glyph.height * 0.16)))
    draw = ImageDraw.Draw(mask)
    top = glyph.height + gap
    draw.line([(0, top + height), (width / 2.0, top + thickness / 2.0)],
              fill=255, width=thickness)
    draw.line([(width / 2.0, top + thickness / 2.0), (width, top + height)],
              fill=255, width=thickness)
    return trim(mask)


def cedilla(glyph):
    """The letter with a cedilla tail underneath (Turkish capital C cedilla)."""
    hook = max(3, int(round(glyph.height * 0.2)))
    width = max(glyph.width, int(round(glyph.height * 0.3)))
    mask = new_mask((width, glyph.height + hook))
    paste_into(mask, glyph.mask, (width - glyph.width) // 2, 0)
    draw = ImageDraw.Draw(mask)
    centre = width / 2.0
    draw.ellipse([centre - hook * 0.45, glyph.height - hook * 0.2,
                  centre + hook * 0.45, glyph.height + hook * 0.8], fill=255)
    draw.polygon([(centre - hook * 0.45, glyph.height - hook * 0.2),
                  (centre + hook * 0.45, glyph.height - hook * 0.2),
                  (centre + hook * 0.1, glyph.height + hook),
                  (centre - hook * 0.45, glyph.height + hook)], fill=255)
    return trim(mask)


# --------------------------------------------------------------------------- #
# the light story menu fonts
# --------------------------------------------------------------------------- #

# the story menu uses two typefaces: the rounded one of the TRACKS label and
# the squared one of the difficulty labels, so each gets its own letter pool
STORY_DONORS = {
    'tracks': [
        ('Menu_Tracks', 'TRACKS', 'solid'),
    ],
    'difficulty': [
        ('menudifficulties/easy', 'EASY', 'hollow'),
        ('menudifficulties/normal', 'NORMAL', 'hollow'),
        ('menudifficulties/hard', 'HARD', 'hollow'),
    ],
}


def harvest_story_font(pool='difficulty'):
    """Harvest one of the two light story menu typefaces."""
    font = Font('story-' + pool)
    candidates = {}
    gaps = []
    strokes = []

    for name, text, style in STORY_DONORS[pool]:
        source = Image.open(os.path.join(SHARED, name + '.png')).convert('RGBA')
        art = art_mask(source)
        body = fill_holes(art) if style == 'hollow' else art
        cap = body.getbbox()[3] - body.getbbox()[1]
        if style == 'hollow':
            strokes.append(median_run_length(art))

        letters = split_letters(body, len(text.replace(' ', '')))
        for char, quality, glyph in word_glyphs_from_letters(text, letters, cap):
            candidates.setdefault(char, []).append((quality, glyph))
            if glyph.gap is not None:
                gaps.append(glyph.gap / float(cap))

    for char, entries in candidates.items():
        font.add(char, choose_glyph(entries))

    font.fallback_gap = (sum(gaps) / len(gaps)) if gaps else 0.04
    # the hollow art is a band centred on the edge of the letters, so its
    # thickness is half of the stroke of the vanilla labels, rounded down: a
    # thicker band would swallow the thin strokes of this typeface
    if strokes:
        font.outline = max(1, int(round(sum(strokes) / float(len(strokes)) / 2.0)))
        add_synthetic_difficulty(font)
    else:
        font.outline = 0
        add_synthetic_tracks(font)
    return font


# --------------------------------------------------------------------------- #
# writing sparrow atlases
# --------------------------------------------------------------------------- #


def write_sparrow_xml(xml_path, image_path, entries):
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<TextureAtlas imagePath="%s">' % image_path]
    for frame_name, x, y, width, height in entries:
        lines.append('\t<SubTexture name="%s" x="%d" y="%d" width="%d" height="%d"/>'
                     % (frame_name, x, y, width, height))
    lines.append('</TextureAtlas>')
    with open(xml_path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')


def styled_solid(body, fill, outline, thickness):
    """Solid letters with an outline drawn around them."""
    image = Image.new('RGBA', body.size, (0, 0, 0, 0))
    if thickness > 0:
        image.paste(tuple(outline) + (255,), (0, 0), dilate(body, thickness))
    image.paste(tuple(fill) + (255,), (0, 0), body)
    return image


# --------------------------------------------------------------------------- #
# main menu entries
# --------------------------------------------------------------------------- #


def build_menu_items(font):
    """The four main menu buttons, as idle + selected atlases."""
    for name, english, turkish in MENU_ITEMS:
        image, frames = read_sparrow(os.path.join(SHARED, 'mainmenu', name + '.png'),
                                     os.path.join(SHARED, 'mainmenu', name + '.xml'))
        idle_frame = crop_frame(image, [f for f in frames if ' idle' in f['name']][0])
        selected_frame = crop_frame(image, [f for f in frames if ' selected' in f['name']][0])

        idle_box = solid_mask(idle_frame, (0, 0, 0)).getbbox()
        idle_cap = idle_box[3] - idle_box[1]
        selected_box = solid_mask(selected_frame, (255, 255, 255)).getbbox()
        selected_cap = selected_box[3] - selected_box[1]

        # the selected art of the vanilla atlas is the same word, drawn a bit
        # bigger and inverted (white letters, dark outline)
        selected_cap = max(selected_cap, int(round(idle_cap * SELECTED_RATIO)))
        idle_body = compose_word(word_glyphs(turkish, font, idle_cap), font)
        selected_body = compose_word(word_glyphs(turkish, font, selected_cap), font)

        idle_art = styled_solid(idle_body, (0, 0, 0), (255, 255, 255),
                                max(1, int(round(idle_cap * OUTLINE_RATIO))))
        selected_art = styled_solid(selected_body, (255, 255, 255), (0, 0, 0),
                                    max(1, int(round(selected_cap * OUTLINE_RATIO))))

        write_menu_atlas(os.path.join(OUT, 'mainmenu', name + '.png'),
                         os.path.join(OUT, 'mainmenu', name + '.xml'),
                         name, frames, idle_art, selected_art)
        print('  mainmenu/%s -> %s' % (name, turkish))


OUTLINE_RATIO = 0.115
SELECTED_RATIO = 1.25


def write_menu_atlas(png_path, xml_path, name, frames, idle_art, selected_art):
    """Pack the idle and the selected art into one sparrow atlas."""
    padding = 2
    width = max(idle_art.size[0], selected_art.size[0]) + padding * 2
    height = idle_art.size[1] + selected_art.size[1] + padding * 3
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    idle_pos = ((width - idle_art.size[0]) // 2, padding)
    selected_pos = ((width - selected_art.size[0]) // 2,
                    padding * 2 + idle_art.size[1])
    canvas.alpha_composite(selected_art, selected_pos)
    canvas.alpha_composite(idle_art, idle_pos)

    entries = []
    for frame in frames:
        if ' idle' in frame['name']:
            entries.append((frame['name'], idle_pos[0], idle_pos[1],
                            idle_art.size[0], idle_art.size[1]))
        elif ' selected' in frame['name']:
            entries.append((frame['name'], selected_pos[0], selected_pos[1],
                            selected_art.size[0], selected_art.size[1]))
    write_sparrow_xml(xml_path, name + '.png', entries)
    canvas.save(png_path)


# --------------------------------------------------------------------------- #
# story menu labels
# --------------------------------------------------------------------------- #


def build_story_labels(pools):
    """The story menu labels, each drawn with its own typeface."""
    for name, turkish, pool in STORY_LABELS:
        font = pools[pool]
        source = Image.open(os.path.join(SHARED, name + '.png')).convert('RGBA')
        art = art_mask(source)
        body = fill_holes(art) if pool == 'difficulty' else art
        box = body.getbbox()
        cap = box[3] - box[1]
        ink = dominant_colour(source)

        composed = compose_word(word_glyphs(turkish, font, cap), font)
        if pool == 'difficulty':
            # the difficulty art is a hollow band, so draw the band only
            output = render_mask(band_of(composed, font.outline), ink)
        else:
            output = render_mask(composed, ink)

        target = os.path.join(OUT, name + '.png')
        os.makedirs(os.path.dirname(target), exist_ok=True)
        output.save(target)
        print('  %-27s -> %s' % (name, turkish))


# --------------------------------------------------------------------------- #
# title screen prompt
# --------------------------------------------------------------------------- #


def alphabet_style(char, info):
    """The animation suffix the alphabet atlas uses for a character."""
    if char.isalpha():
        return 'lowercase' if char == char.lower() else 'uppercase'
    # symbols are drawn as "normal" when the atlas has them, and only the
    # rounded bold set carries a few of them
    return 'normal' if 'normal' in info else 'bold'


def alphabet_glyphs(text):
    """Harvest a string out of the game's own alphabet atlas.

    That atlas carries the rounded "press enter to begin" typeface the vanilla
    title screen uses, and - unlike the pixel font that ships as a ttf - it has
    the Turkish letters, so the Turkish prompt can be spelled out with it.

    Returns the outline art of the letters, which is what the idle frame of the
    vanilla prompt shows.
    """
    import json

    with open(os.path.join(SHARED, 'alphabet.json'), encoding='utf-8-sig') as handle:
        data = json.load(handle)
    letters = data.get('characters', {})
    image, frames = read_sparrow(os.path.join(SHARED, 'alphabet.png'),
                                 os.path.join(SHARED, 'alphabet.xml'))
    by_name = dict((frame['name'], frame) for frame in frames)

    found = []
    for char in text:
        if char == ' ':
            found.append(None)
            continue
        key = TURKISH_KEYS.get(char, char.lower())
        info = letters.get(key, {})
        animation = info.get('animation', key)
        style = alphabet_style(char, info)
        name = '%s %s instance 10000' % (animation, style)
        if name not in by_name:
            raise ValueError('%r (%s) is missing from the alphabet atlas' % (char, name))
        frame = by_name[name]
        art = art_mask(crop_frame(image, frame))
        offsets = info.get(style, info.get('bold', [0, 0]))
        found.append(Glyph(trim(art), int(frame['height']), gap=0, dy=int(offsets[1])))
    return found


TURKISH_KEYS = {u'\u0130': u'\u0131', u'\u011e': u'\u011f', u'\u015e': u'\u015f'}


def build_title():
    """Build the Turkish prompt and cut it into the title screen frames.

    The frame names are the ones the empty sprites in the vanilla atlas carry,
    so the title screen picks them up exactly like it did before.  Like the
    vanilla art, the prompt is a thin outline that turns into solid letters
    while the enter key is held down.
    """
    outline = alphabet_glyphs(TITLE_TEXT)

    cap = max(glyph.height for glyph in outline if glyph is not None)
    limit = TITLE_MAX_WIDTH

    def layout(glyphs, scale):
        scaled = [None if glyph is None
                  else glyph.scaled(max(1, int(round(glyph.height * scale))))
                  for glyph in glyphs]
        return compose_word(scaled, title_metrics())

    scale = min(1.0, TITLE_HEIGHT_TARGET / float(cap))
    body = layout(outline, scale)
    if body.size[0] > limit:
        scale *= limit / float(body.size[0])
        body = layout(outline, scale)

    pixels = layout(outline, scale)
    filled = layout([None if glyph is None
                     else Glyph(fill_holes(glyph.mask), glyph.cap, dy=glyph.dy)
                     for glyph in outline], scale)

    # the same order the vanilla atlas lists its frames in
    rows = [('ENTER FREEZE0000', solid_title_row(filled)),
            ('ENTER IDLE0000', outline_title_row(pixels, TITLE_EDGE)),
            ('ENTER PRESSED0000', solid_title_row(filled)),
            ('ENTER PRESSED0001', solid_title_row(filled))]
    write_title(rows)
    print('  titleEnter -> %s' % TITLE_TEXT)


TITLE_HEIGHT_TARGET = 70.0
TITLE_EDGE = 1


def title_metrics():
    """The layout settings of the alphabet (title screen) typeface."""
    metrics = Font('alphabet')
    metrics.fallback_gap = TITLE_TRACKING
    metrics.space_ratio = 0.32
    return metrics


def solid_title_row(mask):
    """One frame of the prompt: the letters filled out in white."""
    row = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    row.paste((255, 255, 255, 255), (0, 0), mask)
    return row


def outline_title_row(mask, edge):
    """One frame of the prompt: the letters as a glowing outline."""
    row = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    edge_mask = band_of(mask, edge)
    row.paste((255, 255, 255, 90), (0, 0), erode(mask, edge))
    row.paste((255, 255, 255, 255), (0, 0), edge_mask)
    return row


def write_title(rows):
    """Write the prompt art and the sparrow atlas that goes with it."""
    padding = 6
    width = max(row.size[0] for _, row in rows) + padding * 2
    height = sum(row.size[1] + padding for _, row in rows) + padding
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    entries = []
    y = padding
    for name, row in rows:
        x = (width - row.size[0]) // 2
        canvas.alpha_composite(row, (x, y))
        entries.append((name, x, y, row.size[0], row.size[1]))
        y += row.size[1] + padding

    canvas.save(os.path.join(OUT, 'titleEnter.png'))
    write_sparrow_xml(os.path.join(OUT, 'titleEnter.xml'), 'titleEnter.png', entries)


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def main():
    if not os.path.isdir(SHARED):
        sys.exit('the shared art is missing at %s' % SHARED)
    os.makedirs(os.path.join(OUT, 'mainmenu'), exist_ok=True)
    os.makedirs(os.path.join(OUT, 'menudifficulties'), exist_ok=True)

    print('harvesting the graffiti menu font ...')
    graffiti = harvest_graffiti()
    print('  %d letters, cap %d, outline %d, gap %.3f'
          % (len(graffiti.glyphs), graffiti.cap, graffiti.outline, graffiti.fallback_gap))

    print('harvesting the story menu fonts ...')
    pools = {}
    for pool in STORY_DONORS:
        pools[pool] = harvest_story_font(pool)
        font = pools[pool]
        print('  %-11s %d letters, cap %d, band %d, gap %.3f'
              % (pool, len(font.glyphs), font.cap, font.outline, font.fallback_gap))

    print('building the main menu entries ...')
    build_menu_items(graffiti)
    print('building the story menu labels ...')
    build_story_labels(pools)
    print('building the title prompt ...')
    build_title()

    print('done -> %s' % os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()
