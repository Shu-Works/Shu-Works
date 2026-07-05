#!/usr/bin/env python3
"""
make_listing_assets.py — Coloring Book Factory · sales-asset generator
======================================================================

Turns the generated coloring pages in `raw/` into the listing imagery a shop
needs, per 10_Etsy_Listing.md — so the bottleneck stops being image-making.

Outputs (into `listing/`):
  etsy/      ten 2000x2000 listing images (cover, 50-page grid, before/after,
             lifestyle, showcase, difficulty journey, samples, what-you-get,
             series teaser, how-it-works)
  pinterest/ one 1000x1500 (2:3) pin per masterpiece page

Image-dependent assets are skipped (with a warning) if their source page is
missing from raw/, so you can run it before all 50 pages exist.

Usage
-----
  python make_listing_assets.py                 # build everything available
  python make_listing_assets.py --etsy-only
  python make_listing_assets.py --pinterest-only

Requires:  pip install -r requirements.txt   (Pillow)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageChops, ImageOps

import book_config as cfg
from book_config import BOOK

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
OUT = HERE / "listing"
ETSY = OUT / "etsy"
PINS = OUT / "pinterest"

ETSY_SIZE = (2000, 2000)
PIN_SIZE = (1000, 1500)
N_PAGES = 50


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def best_version(page: int) -> Path | None:
    best, best_v = None, -1
    for p in RAW_DIR.glob(f"p{page:02d}_*.png"):
        m = re.search(r"_v(\d+)\.png$", p.name)
        v = int(m.group(1)) if m else 1
        if v > best_v:
            best, best_v = p, v
    return best


def available_pages() -> list[int]:
    return [i for i in range(1, N_PAGES + 1) if best_version(i)]


def load(page: int) -> Image.Image | None:
    p = best_version(page)
    return Image.open(p).convert("RGB") if p else None


def canvas(size, bg=cfg.CREAM) -> Image.Image:
    return Image.new("RGB", size, bg)


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_center(draw, cx, y, text, font, fill=cfg.INK, max_w=None, leading=1.25):
    lines = wrap(draw, text, font, max_w) if max_w else [text]
    h = (font.getbbox("Ay")[3] - font.getbbox("Ay")[1])
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text((cx - w / 2, y), line, font=font, fill=fill)
        y += int(h * leading)
    return y


def paste_fit(base, img, box):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    iw, ih = img.size
    s = min(bw / iw, bh / ih)
    nw, nh = max(1, int(iw * s)), max(1, int(ih * s))
    img2 = img.resize((nw, nh), Image.LANCZOS)
    px, py = x0 + (bw - nw) // 2, y0 + (bh - nh) // 2
    base.paste(img2, (px, py))
    return (px, py, px + nw, py + nh)


def framed(base, img, box, border=cfg.INK, bw=6, shadow=True):
    region = paste_fit(base, img, box)
    d = ImageDraw.Draw(base)
    if shadow:
        d.rectangle([region[0] + 10, region[1] + 10, region[2] + 10,
                     region[3] + 10], outline=(210, 204, 194), width=bw)
    d.rectangle(region, outline=border, width=bw)
    return region


def pastel_wash(line_img, pastel):
    """Tint a line-art page with a soft pastel wash (stylized, not a real color-in)."""
    la = ImageOps.grayscale(line_img)
    w, h = la.size
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    r0, g0, b0 = pastel
    r1, g1, b1 = (min(255, r0 + 18), min(255, g0 + 18), min(255, b0 + 18))
    for y in range(h):
        t = y / max(1, h - 1)
        gd.line([(0, y), (w, y)],
                fill=(int(r0 + (r1 - r0) * t),
                      int(g0 + (g1 - g0) * t),
                      int(b0 + (b1 - b0) * t)))
    line_rgb = ImageOps.colorize(la, black=cfg.INK, white=(255, 255, 255))
    return ImageChops.multiply(grad, line_rgb)


def pill(draw, box, text, font, fill=cfg.DUSK, tcol=(255, 255, 255)):
    x0, y0, x1, y1 = box
    pad = (y1 - y0) * 0.9                              # keep text off the rounded ends
    # auto-shrink the font so the label always fits inside the pill
    while draw.textlength(text, font=font) > (x1 - x0) - pad and font.size > 12:
        try:
            font = font.font_variant(size=font.size - 2)
        except (AttributeError, OSError):
            break
    draw.rounded_rectangle(box, radius=(y1 - y0) // 2, fill=fill)
    tw = draw.textlength(text, font=font)
    th = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
    draw.text(((x0 + x1) / 2 - tw / 2, (y0 + y1) / 2 - th / 2 - 4),
              text, font=font, fill=tcol)


# ---------------------------------------------------------------------------
# Etsy assets
# ---------------------------------------------------------------------------

def etsy_cover():
    src = load(BOOK["cover_source_page"]) or load(available_pages()[0])
    if not src:
        return None
    im = canvas(ETSY_SIZE)
    framed(im, src, (300, 120, 1700, 1180))
    d = ImageDraw.Draw(im)
    text_center(d, 1000, 1260, BOOK["title"], cfg.serif_bold(96),
                cfg.INK, max_w=1700)
    text_center(d, 1000, 1470, BOOK["subtitle"], cfg.serif(56), cfg.DUSK)
    pill(d, (560, 1620, 1440, 1730), "50 PRINTABLE PAGES · INSTANT DOWNLOAD",
         cfg.sans_bold(40))
    text_center(d, 1000, 1820, f"{BOOK['series']} · {BOOK['volume']}",
                cfg.sans(38), (120, 110, 120))
    return im


def etsy_grid():
    pages = available_pages()
    if not pages:
        return None
    im = canvas(ETSY_SIZE)
    d = ImageDraw.Draw(im)
    text_center(d, 1000, 70, "50 Unique Coloring Pages", cfg.serif_bold(84))
    cols, rows = 10, 5                                  # portrait-friendly cells
    m, top, gap = 90, 300, 18
    cw = (ETSY_SIZE[0] - 2 * m - (cols - 1) * gap) // cols
    ch = (ETSY_SIZE[1] - top - 120 - (rows - 1) * gap) // rows
    for idx in range(N_PAGES):
        r, c = divmod(idx, cols)
        x0 = m + c * (cw + gap)
        y0 = top + r * (ch + gap)
        img = load(idx + 1)
        if img:
            paste_fit(im, img, (x0, y0, x0 + cw, y0 + ch))
            d.rectangle([x0, y0, x0 + cw, y0 + ch], outline=(200, 194, 184),
                        width=2)
        else:
            d.rectangle([x0, y0, x0 + cw, y0 + ch], outline=(220, 214, 204),
                        width=2)
    pill(d, (700, 1900, 1300, 1985), "NO REPEATS · NO FILLER", cfg.sans_bold(36),
         fill=cfg.SAGE)
    return im


def etsy_before_after():
    page = next((p for p in BOOK["masterpiece_pages"] if best_version(p)), None)
    page = page or (available_pages()[-1] if available_pages() else None)
    if not page:
        return None
    src = load(page)
    im = canvas(ETSY_SIZE)
    d = ImageDraw.Draw(im)
    text_center(d, 1000, 80, "Print it black & white — color it your way",
                cfg.serif_bold(64), max_w=1840)
    framed(im, src, (110, 320, 980, 1640))
    framed(im, pastel_wash(src, cfg.PASTELS[0]), (1020, 320, 1890, 1640))
    text_center(d, 545, 1690, "The pages you get", cfg.sans_bold(40), cfg.INK)
    text_center(d, 1455, 1690, "What they can become", cfg.sans_bold(40),
                cfg.DUSK)
    return im


def etsy_lifestyle():
    page = next((p for p in BOOK["masterpiece_pages"] if best_version(p)), None)
    if not page:
        return None
    im = canvas(ETSY_SIZE, (236, 228, 216))      # warm "desk" tone
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([250, 250, 1750, 1620], radius=24, fill=(252, 250, 245),
                        outline=(205, 198, 186), width=4)
    framed(im, load(page), (330, 330, 1670, 1540), shadow=False)
    text_center(d, 1000, 1700, "A quiet evening, a cup of tea, and a page to color",
                cfg.serif(54), cfg.INK, max_w=1760)
    return im


def etsy_showcase():
    page = (BOOK["masterpiece_pages"][-1]
            if best_version(BOOK["masterpiece_pages"][-1]) else None)
    page = page or (available_pages()[-1] if available_pages() else None)
    if not page:
        return None
    im = canvas(ETSY_SIZE)
    d = ImageDraw.Draw(im)
    text_center(d, 1000, 80, "Finish with a Masterpiece", cfg.serif_bold(80))
    framed(im, load(page), (260, 300, 1740, 1740))
    text_center(d, 1000, 1820, "The final 10 pages are made to be framed",
                cfg.sans(42), cfg.DUSK)
    return im


def etsy_difficulty():
    im = canvas(ETSY_SIZE)
    d = ImageDraw.Draw(im)
    text_center(d, 1000, 80, "A Journey, Not a Pile of Pages",
                cfg.serif_bold(76))
    chapters = [("1 · Arrival", "Gentle, open pages", [1, 3]),
                ("2 · Exploration", "Cozy corners & vignettes", [13, 15]),
                ("3 · Discovery", "Rich, layered scenes", [27, 31]),
                ("4 · Masterpiece", "The stunning finale", [41, 50])]
    top = 320
    for i, (name, desc, samples) in enumerate(chapters):
        y0 = top + i * 400
        d.rounded_rectangle([90, y0, 1910, y0 + 360], radius=20,
                            fill=(255, 252, 246), outline=(210, 204, 194),
                            width=3)
        d.text((140, y0 + 60), name, font=cfg.serif_bold(64), fill=cfg.DUSK)
        d.text((140, y0 + 170), desc, font=cfg.sans(44), fill=cfg.INK)
        sx = 1180
        for s in samples:
            img = load(s)
            if img:
                paste_fit(im, img, (sx, y0 + 30, sx + 300, y0 + 330))
                d.rectangle([sx, y0 + 30, sx + 300, y0 + 330],
                            outline=(200, 194, 184), width=2)
            sx += 330
    return im


def etsy_samples():
    pages = available_pages()
    if not pages:
        return None
    picks = [p for p in [5, 14, 27, 44] if p in pages] or pages[:4]
    im = canvas(ETSY_SIZE)
    d = ImageDraw.Draw(im)
    text_center(d, 1000, 80, "A Peek Inside", cfg.serif_bold(84))
    boxes = [(130, 300, 980, 1130), (1020, 300, 1870, 1130),
             (130, 1170, 980, 2000 - 30), (1020, 1170, 1870, 2000 - 30)]
    for p, b in zip(picks, boxes):
        framed(im, load(p), b)
    return im


def etsy_what_you_get():
    im = canvas(ETSY_SIZE, cfg.DUSK)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([90, 90, 1910, 1910], radius=30, fill=cfg.CREAM)
    text_center(d, 1000, 180, "What You Get", cfg.serif_bold(96), cfg.DUSK)
    items = [
        "50 unique coloring pages — no repeats, no filler",
        "A guided journey from gentle to intricate",
        "10 stunning masterpiece finale pages",
        "Recurring cozy characters & motifs",
        "Single-sided — remove & frame favorites",
        "Bonus: welcome, tips & full page index",
        "Print-ready PDF · 8.5 × 11 in · 300 DPI",
        "Instant download · print as often as you like",
    ]
    y = 420
    for it in items:
        d.ellipse([200, y + 16, 232, y + 48], fill=cfg.TERRACOTTA)
        d.text((280, y), it, font=cfg.sans(50), fill=cfg.INK)
        y += 175
    return im


def etsy_series():
    im = canvas(ETSY_SIZE, cfg.SAGE)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([90, 90, 1910, 1910], radius=30, fill=cfg.CREAM)
    text_center(d, 1000, 200, "Part of a Series", cfg.serif_bold(92), cfg.SAGE)
    text_center(d, 1000, 380, BOOK["series"], cfg.serif(58), cfg.INK, max_w=1700)
    upcoming = ["Vol. 1 · The Enchanted Witch's Cottage  (this book)",
                "Vol. 2 · The Witch's Library",
                "Vol. 3 · The Witch's Apothecary",
                "Vol. 4 · The Witch's Kitchen",
                "Vol. 5 · The Witch's Garden",
                "… and money-saving bundles as the series grows"]
    y = 620
    for u in upcoming:
        d.text((230, y), u, font=cfg.sans(46), fill=cfg.INK)
        y += 180
    return im


def etsy_how():
    im = canvas(ETSY_SIZE)
    d = ImageDraw.Draw(im)
    text_center(d, 1000, 120, "How It Works", cfg.serif_bold(92))
    steps = [("1", "Download", "Get your PDF instantly after checkout"),
             ("2", "Print", "At home or a print shop · 8.5×11 · 100% size"),
             ("3", "Color", "Pencils, gel pens & fine-liners shine")]
    top = 420
    for i, (n, t, desc) in enumerate(steps):
        y0 = top + i * 470
        d.ellipse([150, y0, 360, y0 + 210], fill=cfg.DUSK)
        nb = cfg.serif_bold(120)
        nw = d.textlength(n, font=nb)
        d.text((255 - nw / 2, y0 + 30), n, font=nb, fill=(255, 255, 255))
        d.text((430, y0 + 20), t, font=cfg.serif_bold(70), fill=cfg.INK)
        d.text((430, y0 + 120), desc, font=cfg.sans(44), fill=(90, 84, 80))
    return im


ETSY_ASSETS = [
    ("01_cover_mockup", etsy_cover),
    ("02_grid_50_pages", etsy_grid),
    ("03_before_after", etsy_before_after),
    ("04_lifestyle", etsy_lifestyle),
    ("05_masterpiece_showcase", etsy_showcase),
    ("06_difficulty_journey", etsy_difficulty),
    ("07_sample_collage", etsy_samples),
    ("08_what_you_get", etsy_what_you_get),
    ("09_series_teaser", etsy_series),
    ("10_how_it_works", etsy_how),
]


# ---------------------------------------------------------------------------
# Pinterest pins
# ---------------------------------------------------------------------------

def pin_for(page: int):
    src = load(page)
    if not src:
        return None
    im = canvas(PIN_SIZE)
    d = ImageDraw.Draw(im)
    framed(im, src, (60, 60, 940, 1080))
    d.rounded_rectangle([0, 1110, 1000, 1500], radius=0, fill=cfg.DUSK)
    text_center(d, 500, 1160, BOOK["title"], cfg.serif_bold(58),
                (255, 255, 255), max_w=900)
    text_center(d, 500, 1300, BOOK["tagline"], cfg.sans(40),
                (242, 236, 246), max_w=900)
    pill(d, (250, 1410, 750, 1470), "PRINTABLE PDF", cfg.sans_bold(34),
         fill=cfg.TERRACOTTA)
    return im


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Generate Etsy & Pinterest assets")
    p.add_argument("--etsy-only", action="store_true")
    p.add_argument("--pinterest-only", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    if not available_pages():
        print("WARNING: no page images in raw/. Text-only assets will still "
              "build; image assets will be skipped. Run generate.py first.")

    made = skipped = 0
    if not args.pinterest_only:
        ETSY.mkdir(parents=True, exist_ok=True)
        print("Building Etsy listing images (2000x2000)…")
        for name, fn in ETSY_ASSETS:
            img = fn()
            if img is None:
                print(f"  - {name}: skipped (source page missing)")
                skipped += 1
                continue
            img.save(ETSY / f"{name}.png")
            print(f"  ✓ {name}.png")
            made += 1

    if not args.etsy_only:
        PINS.mkdir(parents=True, exist_ok=True)
        print("Building Pinterest pins (1000x1500)…")
        for page in BOOK["masterpiece_pages"]:
            img = pin_for(page)
            if img is None:
                print(f"  - pin p{page:02d}: skipped (page missing)")
                skipped += 1
                continue
            img.save(PINS / f"pin_p{page:02d}.png")
            print(f"  ✓ pin_p{page:02d}.png")
            made += 1

    print(f"\nDone. {made} asset(s) built, {skipped} skipped -> {OUT}")
    print("Tip: pair these with the copy in ../10_Etsy_Listing.md (titles, tags, "
          "Pinterest captions). Swap the before/after right panel with your own "
          "colored sample for the strongest listing.")


if __name__ == "__main__":
    main()
