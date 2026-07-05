#!/usr/bin/env python3
"""
book_config.py — shared configuration for the Book #1 production tools.

Both package.py (PDF) and make_listing_assets.py (Etsy/Pinterest images) import
from here, so per-volume settings live in ONE place. To start the next volume,
copy this file into its bookNN/ folder and edit the BOOK block.
"""

from __future__ import annotations
from pathlib import Path

# ---------------------------------------------------------------------------
# Per-volume settings  (the only block you edit per book)
# ---------------------------------------------------------------------------

BOOK = {
    "title": "The Enchanted Witch's Cottage",
    "subtitle": "A Cozy Coloring Journey",
    "series": "The Cozy Witch's Cottage Series",
    "volume": "Volume 1",
    "shop": "(Your Shop Name)",
    "cover_source_page": 48,          # which coloring page styles the cover
    "next_volume": "The Witch's Library",
    "etsy_or_payhip": "our shop",     # used in thank-you / cross-sell copy
    "tagline": "50 cozy printable pages to color your calm.",
    # Pages used as hero imagery for covers, pins, and showcases:
    "masterpiece_pages": [41, 42, 44, 48, 50],
}

# ---------------------------------------------------------------------------
# Font resolution (cross-platform; falls back gracefully)
# ---------------------------------------------------------------------------

_SERIF_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/Library/Fonts/Georgia Bold.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
    "C:/Windows/Fonts/timesbd.ttf",
]
_SERIF = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/Library/Fonts/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "C:/Windows/Fonts/georgia.ttf",
    "C:/Windows/Fonts/times.ttf",
]
_SANS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_SANS_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

_warned = False


def _resolve(candidates, size):
    from PIL import ImageFont
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    global _warned
    if not _warned:
        print("WARNING: no system TTF font found; using a low-res default. "
              "Install DejaVu/Liberation fonts for crisp text.")
        _warned = True
    return ImageFont.load_default()


def serif_bold(size): return _resolve(_SERIF_BOLD, size)
def serif(size): return _resolve(_SERIF, size)
def sans(size): return _resolve(_SANS, size)
def sans_bold(size): return _resolve(_SANS_BOLD, size)


# ---------------------------------------------------------------------------
# Brand palette (soft cozy tones used for listing graphics)
# ---------------------------------------------------------------------------

CREAM = (250, 246, 238)
INK = (40, 36, 33)
DUSK = (92, 79, 102)        # muted witchy purple
SAGE = (150, 168, 140)
TERRACOTTA = (196, 130, 96)
PASTELS = [(232, 213, 224), (213, 224, 232), (224, 232, 213),
           (245, 230, 210), (224, 216, 235)]
