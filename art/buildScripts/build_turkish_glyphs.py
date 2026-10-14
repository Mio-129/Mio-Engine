#!/usr/bin/env python3
# Generates Turkish glyphs (ı, İ, ğ, Ğ, ş, Ş) for Psych Engine's alphabet atlas
# by composing existing glyph art (s+cedilla from ç, g+breve from inverted circumflex of â,
# i minus dot = ı, i uppercase + dot from ï = İ). ı bold reuses i bold art directly.
import re
from PIL import Image

ATLAS_PNG = 'assets/shared/images/alphabet.png'
ATLAS_XML = 'assets/shared/images/alphabet.xml'
ATLAS_JSON = 'assets/shared/images/alphabet.json'

img = Image.open(ATLAS_PNG).convert('RGBA')
src = open(ATLAS_XML, encoding='utf-8').read()
frames = {}
order = []
for m in re.finditer(r'<SubTexture ([^/]+)/>', src):
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    d = {k: int(attrs[k]) for k in ('x', 'y', 'width', 'height')}
    d['frameX'] = int(attrs.get('frameX', 0))
    d['frameY'] = int(attrs.get('frameY', 0))
    d['frameWidth'] = int(attrs.get('frameWidth', d['width']))
    d['frameHeight'] = int(attrs.get('frameHeight', d['height']))
    frames[attrs['name']] = d
    order.append(attrs['name'])


def logical(name):
    f = frames[name]
    art = img.crop((f['x'], f['y'], f['x'] + f['width'], f['y'] + f['height']))
    canvas = Image.new('RGBA', (f['frameWidth'], f['frameHeight']), (0, 0, 0, 0))
    canvas.paste(art, (-f['frameX'], -f['frameY']))
    return canvas


def body_bbox(im):
    return im.getbbox()  # alpha bbox


def crop_accent_down(donor, base_h):
    """Cedilla-like accent living below the base letter's canvas height."""
    return donor.crop((0, base_h, donor.size[0], donor.size[1]))


def crop_accent_up(donor, base_h):
    """Breve-like accent living above the base letter (body bottom-aligned)."""
    extra = donor.size[1] - base_h
    return donor.crop((0, 0, donor.size[0], extra))


def trim(im):
    bb = im.getbbox()
    if bb is None:
        return im, (0, 0)
    return im.crop(bb), (bb[0], bb[1])


def compose_down(base, accent_full, donor_base, donor_accent_canvas):
    """Attach accent below the letter (position preserved relative to body bottom/center)."""
    bw, bh = base.size
    aw, ah = accent_full.size
    out = Image.new('RGBA', (bw, bh + ah), (0, 0, 0, 0))
    out.paste(base, (0, 0))
    d_bb = body_bbox(donor_base)
    t_bb = body_bbox(base)
    donor_cx = (d_bb[0] + d_bb[2]) / 2
    target_cx = (t_bb[0] + t_bb[2]) / 2
    dx = int(round(target_cx - donor_cx))
    out.paste(accent_full, (dx, bh), accent_full)
    return out


def compose_up(base, accent_full, donor_base_canvas_h, donor_base, donor_accent_canvas, gap=0):
    """Attach accent above the letter (body stays bottom-aligned)."""
    bw, bh = base.size
    aw, ah = accent_full.size
    extra = ah + gap
    out = Image.new('RGBA', (bw, bh + extra), (0, 0, 0, 0))
    out.paste(base, (0, extra))
    d_bb = body_bbox(donor_base)
    t_bb = body_bbox(base)
    donor_cx = (d_bb[0] + d_bb[2]) / 2
    target_cx = (t_bb[0] + t_bb[2]) / 2
    dx = int(round(target_cx - donor_cx))
    # donor canvas: accent top at y=0, body bottom-aligned (body top = ah + d_bb[1])
    donor_body_top_full = d_bb[1] + ah
    target_body_top = t_bb[1] + extra
    y = target_body_top - donor_body_top_full  # keeps same visual gap as donor
    out.paste(accent_full, (dx, max(0, y)), accent_full)
    return out


def flip_v(im):
    return im.transpose(Image.FLIP_TOP_BOTTOM)


# ---------- build per-style composites ----------
new_anims = {}  # anim_prefix -> {'A': canvas, 'B': canvas}

def add_composed(anim, style, base_letter, donor_letter, kind):
    baseA = logical(f'{base_letter} {style} instance 10000')
    baseB = logical(f'{base_letter} {style} instance 10002')
    donorA = logical(f'{donor_letter} {style} instance 10000')
    donor_base_h = logical(f'{base_letter} {style} instance 10000').size[1]
    # donor accent uses donor's paired base letter (c for ç, a for â, i for ï)
    donor_base_letter = {'ç': 'c', 'â': 'a', 'ï': 'i'}[donor_letter]
    donor_baseA = logical(f'{donor_base_letter} {style} instance 10000')
    if kind == 'down':
        accent_full = crop_accent_down(donorA, donor_baseA.size[1])
        def comp(base):
            return compose_down(base, accent_full, donor_baseA, accent_full)
        new_anims[anim] = {'A': comp(baseA), 'B': comp(baseB)}
    elif kind == 'up':
        accent_full = crop_accent_up(donorA, donor_baseA.size[1])
        accent_full_flip = flip_v(accent_full)
        def comp(base):
            return compose_up(base, accent_full_flip, donor_baseA.size[1], donor_baseA, accent_full_flip, gap=0)
        new_anims[anim] = {'A': comp(baseA), 'B': comp(baseB)}
    else:
        raise ValueError(kind)


add_composed('ş lowercase', 'lowercase', 's', 'ç', 'down')
add_composed('ş uppercase', 'uppercase', 's', 'ç', 'down')
add_composed('ş bold', 'bold', 's', 'ç', 'down')
add_composed('ğ lowercase', 'lowercase', 'g', 'â', 'up')
add_composed('ğ uppercase', 'uppercase', 'g', 'â', 'up')
add_composed('ğ bold', 'bold', 'g', 'â', 'up')

# ı lowercase: i lowercase minus dot (clear everything above the stem)
def make_dotless(style_base_name):
    out = {}
    for inst in ('10000', '10002'):
        c = logical(f'{style_base_name} instance {inst}')
        px = c.load()
        w, h = c.size
        # find first empty row band after topmost content (dot then gap then stem)
        rows = [sum(1 for x in range(w) if px[x, y][3] > 0) for y in range(h)]
        top = next(y for y in range(h) if rows[y] > 0)
        gap_start = next(y for y in range(top, h) if rows[y] == 0)
        stem_top = next(y for y in range(gap_start, h) if rows[y] > 0)
        for y in range(0, stem_top):
            for x in range(w):
                px[x, y] = (0, 0, 0, 0)
        out[inst] = c
    return out

dotless = make_dotless('i lowercase')
new_anims['ı lowercase'] = {'A': dotless['10000'], 'B': dotless['10002']}

# ı uppercase (İ): i uppercase + single dot (left dot of ï uppercase) centered above
def make_dotted_capital():
    out = {}
    for inst in ('10000', '10002'):
        base = logical(f'i uppercase instance {inst}')
        donor = logical(f'ï uppercase instance {inst}')
        dbase = logical(f'i uppercase instance {inst}')  # body ref same size as base
        dd, _ = trim(donor)
        # dot region: everything above donor body (donor is 12px taller, dots in top 10 rows)
        extra = donor.size[1] - base.size[1]
        dot_region = donor.crop((0, 0, donor.size[0], extra))
        # split two blobs: find column occupancy gap
        px = dot_region.load()
        w, h = dot_region.size
        cols = [any(px[x, y][3] > 0 for y in range(h)) for x in range(w)]
        # find gap column band between blobs
        gaps = []
        x = 0
        while x < w:
            if not cols[x]:
                x0 = x
                while x < w and not cols[x]:
                    x += 1
                gaps.append((x0, x))
            else:
                x += 1
        # blob split: take columns before the widest interior gap
        interior = [g for g in gaps if g[0] > 0 and g[1] < w]
        split = max(interior, key=lambda g: g[1] - g[0]) if interior else None
        left = dot_region.crop((0, 0, split[0], h)) if split else dot_region
        lbb = left.getbbox()
        dot = left.crop(lbb)
        bw, bh = base.size
        extra_h = extra
        canvas = Image.new('RGBA', (bw, bh + extra_h), (0, 0, 0, 0))
        canvas.paste(base, (0, extra_h))
        t_bb = base.getbbox()
        # donor: dots rows 0.., body top at extra+base_body_top; keep same gap (2 empty rows)
        donor_body_top = dbase.getbbox()[1] + extra_h
        dot_bottom = lbb[3]  # exclusive
        # place dot so that (body_top - dot_bottom) matches donor
        donor_dot_bottom = lbb[3]
        donor_gap = (dbase.getbbox()[1] + extra_h) - donor_dot_bottom
        target_body_top = t_bb[1] + extra_h
        y = target_body_top - donor_gap - dot.size[1]
        x = (bw - dot.size[0]) // 2
        canvas.paste(dot, (x, y), dot)
        out[inst] = canvas
    return out

dotted = make_dotted_capital()
new_anims['ı uppercase'] = {'A': dotted['10000'], 'B': dotted['10002']}

# ---------- pack new art into atlas ----------
PADDING = 6
shelf_y = img.size[1] + PADDING
shelf_x = 0
shelf_h = 0
placements = []  # (anim, inst_kind, rect)

def place(canvas):
    global shelf_x, shelf_y, shelf_h
    w, h = canvas.size
    if shelf_x + w + PADDING > img.size[0]:
        shelf_y += shelf_h + PADDING
        shelf_x = 0
        shelf_h = 0
    x, y = shelf_x, shelf_y
    shelf_x += w + PADDING
    shelf_h = max(shelf_h, h)
    return x, y

new_h = img.size[1]
canvases_to_paste = []
for anim, pair in new_anims.items():
    for kind, canvas in (('A', pair['A']), ('B', pair['B'])):
        canvases_to_paste.append((anim, kind, canvas))

coords = {}
for anim, kind, canvas in canvases_to_paste:
    x, y = place(canvas)
    coords[(anim, kind)] = (x, y, canvas)
    new_h = max(new_h, y + canvas.size[1] + PADDING)

out_img = Image.new('RGBA', (img.size[0], new_h), (0, 0, 0, 0))
out_img.paste(img, (0, 0))
for (anim, kind), (x, y, canvas) in coords.items():
    out_img.paste(canvas, (x, y))

def emit(name, anim, kind):
    x, y, canvas = coords[(anim, kind)]
    bb = canvas.getbbox()
    trimmed = canvas.crop(bb)
    w, h = trimmed.size
    a = f'<SubTexture name="{name}" x="{x + bb[0]}" y="{y + bb[1]}" width="{w}" height="{h}"'
    fw, fh = canvas.size
    fx, fy = -bb[0], -bb[1]
    if fx or fy or fw != w or fh != h:
        a += f' frameX="{fx}" frameY="{fy}" frameWidth="{fw}" frameHeight="{fh}"'
    a += '/>'
    return '\t' + a

lines = []
# ı bold: clone i bold rects (already dotless slab-I art)
for inst in ('10000', '10001', '10002', '10003'):
    f = frames[f'i bold instance {inst}']
    attrs = ' '.join(f'{k}="{f[k]}"' for k in ('frameX', 'frameY', 'frameWidth', 'frameHeight')
                     if (f[k] != 0 if k.startswith('frameX') or k.startswith('frameY') else f[k] != f['width' if k == 'frameWidth' else 'height']))
    # simpler: replicate full original attr set
    orig = re.search(r'<SubTexture name="i bold instance %s"[^/]*/>' % inst, src).group(0)
    d = frames[f'i bold instance {inst}']
    a = f'<SubTexture name="ı bold instance {inst}" x="{d["x"]}" y="{d["y"]}" width="{d["width"]}" height="{d["height"]}"'
    if d['frameX'] or d['frameY'] or d['frameWidth'] != d['width'] or d['frameHeight'] != d['height']:
        a += f' frameX="{d["frameX"]}" frameY="{d["frameY"]}" frameWidth="{d["frameWidth"]}" frameHeight="{d["frameHeight"]}"'
    a += '/>'
    lines.append('\t' + a)

for anim in ('ş lowercase', 'ş uppercase', 'ş bold', 'ğ lowercase', 'ğ uppercase', 'ğ bold',
             'ı lowercase', 'ı uppercase'):
    lines.append(emit(f'{anim} instance 10000', anim, 'A'))
    lines.append(emit(f'{anim} instance 10001', anim, 'A'))
    lines.append(emit(f'{anim} instance 10002', anim, 'B'))
    lines.append(emit(f'{anim} instance 10003', anim, 'B'))

new_xml = src.replace('</TextureAtlas>', '\n'.join(lines) + '\n</TextureAtlas>')
open(ATLAS_XML, 'w', encoding='utf-8').write(new_xml)
out_img.save(ATLAS_PNG)

# update JSON allowed
js = open(ATLAS_JSON, encoding='utf-8').read()
if "'ğ'" not in js and 'ğ' not in js:
    js = js.replace("ñçšžýÿß", "ñçšžýÿßığş")
    open(ATLAS_JSON, 'w', encoding='utf-8').write(js)

print('atlas now', out_img.size)
print('added', len(lines), 'SubTextures')

# ---------- verification render: simulated bold menu text ----------
def render_text(text, bold=True):
    # simulate Alphabet layout: bottom-aligned letters, bold advance ~ letter width + 4
    letters = []
    x = 0
    for ch in text:
        if ch == ' ':
            x += 28
            continue
        lookup = {'İ': 'ı', 'Ğ': 'ğ', 'Ş': 'ş'}.get(ch, ch.lower())
        case = 'bold' if bold else ('uppercase' if ch.lower() != ch and ch.isalpha() else 'lowercase')
        if not ch.isalpha():
            case = 'bold' if bold else 'normal'
        anim = f'{lookup} {case}'
        try:
            c = logical(f'{anim} instance 10000')
        except KeyError:
            try:
                c = logical(f'{anim} instance 10000')
            except KeyError:
                print('MISSING', anim, 'for', ch)
                continue
        letters.append((x, c))
        x += c.size[0] + 4
    W = x + 20
    H = max(c.size[1] for _, c in letters) + 20
    sheet = Image.new('RGBA', (W, H), (240, 240, 255, 255))
    for lx, c in letters:
        sheet.paste(c, (lx + 10, H - 10 - c.size[1]), c)
    return sheet

# The renderer above uses OLD atlas frames for old glyphs and NEW ones need reloading:
# reload frames from updated files
img = out_img
src = new_xml
frames = {}
for m in re.finditer(r'<SubTexture ([^/]+)/>', src):
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    d = {k: int(attrs[k]) for k in ('x', 'y', 'width', 'height')}
    d['frameX'] = int(attrs.get('frameX', 0))
    d['frameY'] = int(attrs.get('frameY', 0))
    d['frameWidth'] = int(attrs.get('frameWidth', d['width']))
    d['frameHeight'] = int(attrs.get('frameHeight', d['height']))
    frames[attrs['name']] = d

t1 = render_text('Oynanış Ayarları', True)
t2 = render_text('Görseller', True)
t3 = render_text('İstatistikler Şifre Ğıl', True)
t4 = render_text('Oynanış Ayarları', False)
t5 = render_text('İşlem ışık', False)
W = max(t.size[0] for t in (t1, t2, t3, t4, t5)) + 20
H = sum(t.size[1] for t in (t1, t2, t3, t4, t5)) + 60
sheet = Image.new('RGBA', (W, H), (240, 240, 255, 255))
y = 10
for t in (t1, t2, t3, t4, t5):
    sheet.paste(t, (10, y), t)
    y += t.size[1] + 10
sheet.save('.glyphwork/verify_text.png')
print('verification sheet saved')
