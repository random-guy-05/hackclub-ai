#!/usr/bin/env python3
"""Render a crisp 1024x1024 HackClub AI app icon (gradient squircle + chat glyph)."""

import os

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
SS = 4  # supersample factor
S = SIZE * SS


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def diagonal_gradient(size, top, bottom):
    base = Image.new("RGB", (size, size))
    px = base.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = lerp(top, bottom, t)
    return base


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "assets", "AppIcon-1024.png")

    # macOS icon grid: tile occupies ~80% with transparent margin
    margin = int(S * 0.085)
    tile = S - 2 * margin
    radius = int(tile * 0.225)

    top = (0xFD, 0x73, 0x36)
    bottom = (0xE5, 0x3A, 0x12)

    grad = diagonal_gradient(tile, top, bottom)

    # subtle top highlight
    hi = Image.new("L", (tile, tile), 0)
    hd = ImageDraw.Draw(hi)
    hd.ellipse([-tile * 0.3, -tile * 0.75, tile * 1.3, tile * 0.55], fill=70)
    hi = hi.filter(ImageFilter.GaussianBlur(tile * 0.08))
    white = Image.new("RGB", (tile, tile), (255, 255, 255))
    grad = Image.composite(white, grad, hi.point(lambda v: int(v * 0.35)))

    mask = rounded_mask(tile, radius)

    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # soft drop shadow under the tile
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [margin, margin + int(S * 0.012), margin + tile, margin + tile + int(S * 0.012)],
        radius=radius, fill=(0, 0, 0, 90),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.02))
    canvas = Image.alpha_composite(canvas, shadow)

    tile_rgba = grad.convert("RGBA")
    tile_rgba.putalpha(mask)
    canvas.alpha_composite(tile_rgba, (margin, margin))

    # chat bubble glyph
    glyph = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph)
    cx0 = int(S * 0.275)
    cy0 = int(S * 0.30)
    cx1 = int(S * 0.725)
    cy1 = int(S * 0.62)
    stroke = int(S * 0.030)
    br = int(S * 0.085)
    gd.rounded_rectangle([cx0, cy0, cx1, cy1], radius=br, outline=(255, 255, 255, 255), width=stroke)

    # tail (bottom-left): a clean solid pointer that merges into the bubble's bottom border
    tail = [
        (cx0 + int(S * 0.055), cy1 - stroke),
        (cx0 + int(S * 0.055), cy1 + int(S * 0.095)),
        (cx0 + int(S * 0.175), cy1 - stroke),
    ]
    gd.polygon(tail, fill=(255, 255, 255, 255))

    # three dots
    cy = (cy0 + cy1) // 2
    dot_r = int(S * 0.028)
    for fx in (0.42, 0.5, 0.58):
        dx = int(S * fx)
        gd.ellipse([dx - dot_r, cy - dot_r, dx + dot_r, cy + dot_r], fill=(255, 255, 255, 255))

    # clip glyph to tile mask so nothing spills outside corners
    full_mask = Image.new("L", (S, S), 0)
    full_mask.paste(mask, (margin, margin))
    glyph.putalpha(Image.composite(glyph.getchannel("A"), Image.new("L", (S, S), 0), full_mask))

    canvas = Image.alpha_composite(canvas, glyph)

    canvas = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    canvas.save(out)
    print("wrote", os.path.abspath(out))


if __name__ == "__main__":
    main()
