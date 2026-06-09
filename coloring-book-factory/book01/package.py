#!/usr/bin/env python3
"""
package.py — Coloring Book Factory · print-ready PDF assembler
=============================================================

Assembles the generated coloring pages in `raw/` into a single, print-ready PDF
at US Letter (8.5 x 11 in), 300 DPI, single-sided — with full front/back matter
per 05_Book_Concept.md:

  cover -> title -> welcome -> how-to -> 50 coloring pages -> index -> thank-you

It also (optionally) cleans each line-art image: upscales toward 300 DPI and
binarizes to pure black/white, which sharpens lines for print and removes any
stray grayscale (a free fix for minor shading QC flags).

Image source per page: picks the highest-numbered version in `raw/`
(p21_..._v3.png beats p21_..._v2.png beats p21_....png), so regenerated pages
win automatically.

Usage
-----
  python package.py                      # build the full book from raw/
  python package.py --clean              # binarize + upscale pages (recommended)
  python package.py --approved-only      # include only pages marked Approved in qc_tracker.csv
  python package.py --matter-only        # build just the front/back matter (preview, no pages)
  python package.py --no-page-numbers    # omit the small footer page numbers

Requires:  pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import tempfile
from pathlib import Path

from reportlab.lib.pagesizes import letter          # (612, 792) pt = 8.5x11 in
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

# ---------------------------------------------------------------------------
# Book configuration  (shared with make_listing_assets.py via book_config.py)
# ---------------------------------------------------------------------------

try:
    from book_config import BOOK
except ImportError:                                  # standalone fallback
    BOOK = {
        "title": "The Enchanted Witch's Cottage",
        "subtitle": "A Cozy Coloring Journey",
        "series": "The Cozy Witch's Cottage Series",
        "volume": "Volume 1",
        "shop": "(Your Shop Name)",
        "cover_source_page": 48,
        "next_volume": "The Witch's Library",
        "etsy_or_payhip": "our shop",
    }

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
OUT_DIR = HERE / "output"
STRUCTURE_CSV = HERE.parent / "06_Page_Structure.csv"
QC_TRACKER = HERE / "qc_tracker.csv"

PAGE_W, PAGE_H = letter
N_PAGES = 50

# Margins for coloring pages (maximize coloring area; leave room for footer).
M_SIDE = 0.5 * inch
M_TOP = 0.5 * inch
M_BOTTOM = 0.65 * inch

TARGET_DPI = 300
TARGET_PX = (int(8.5 * TARGET_DPI), int(11 * TARGET_DPI))  # 2550 x 3300

TITLE_FONT = "Times-Bold"
BODY_FONT = "Times-Roman"
ACCENT_FONT = "Helvetica"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def best_version(page: int) -> Path | None:
    """Return the highest-version PNG for a page, or None if missing."""
    best, best_v = None, -1
    for p in RAW_DIR.glob(f"p{page:02d}_*.png"):
        m = re.search(r"_v(\d+)\.png$", p.name)
        v = int(m.group(1)) if m else 1
        if v > best_v:
            best, best_v = p, v
    return best


def read_titles() -> dict[int, str]:
    titles = {}
    if STRUCTURE_CSV.exists():
        with STRUCTURE_CSV.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                titles[int(r["Page Number"])] = r["Page Title"]
    return titles


def approved_pages() -> set[int] | None:
    """Pages marked 'Approved' in qc_tracker.csv, or None if no tracker."""
    if not QC_TRACKER.exists():
        return None
    ok = set()
    with QC_TRACKER.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if (r.get("class", "") or "").strip().lower() == "approved":
                ok.add(int(r["page"]))
    return ok


def clean_image(src: Path, tmp: Path) -> Path:
    """Upscale toward 300 DPI and binarize to pure B/W. Returns new path."""
    from PIL import Image
    img = Image.open(src).convert("L")               # grayscale
    if img.width < TARGET_PX[0]:                     # upscale if below target
        ratio = TARGET_PX[0] / img.width
        img = img.resize((TARGET_PX[0], int(img.height * ratio)),
                         Image.LANCZOS)
    bw = img.point(lambda x: 255 if x > 128 else 0, mode="1")  # threshold
    dest = tmp / src.name
    bw.save(dest, dpi=(TARGET_DPI, TARGET_DPI))
    return dest


# ---------------------------------------------------------------------------
# Text-page rendering
# ---------------------------------------------------------------------------

def centered(c, text, font, size, y, gray=0.0):
    c.setFont(font, size)
    c.setFillGray(gray)
    c.drawCentredString(PAGE_W / 2, y, text)


def wrapped(c, text, font, size, x, y, width, leading):
    c.setFont(font, size)
    c.setFillGray(0.15)
    for line in simpleSplit(text, font, size, width):
        c.drawString(x, y, line)
        y -= leading
    return y


def page_cover(c, cover_img: Path | None):
    if cover_img and cover_img.exists():
        c.drawImage(str(cover_img), 0, 0, PAGE_W, PAGE_H,
                    preserveAspectRatio=True, anchor="c", mask="auto")
    # translucent band for legible title over art
    c.setFillColorRGB(1, 1, 1)
    c.setFillAlpha(0.78)
    c.rect(0, PAGE_H * 0.60, PAGE_W, PAGE_H * 0.22, fill=1, stroke=0)
    c.setFillAlpha(1)
    centered(c, BOOK["title"], TITLE_FONT, 34, PAGE_H * 0.73)
    centered(c, BOOK["subtitle"], BODY_FONT, 17, PAGE_H * 0.685, gray=0.25)
    centered(c, f"{BOOK['series']}  ·  {BOOK['volume']}",
             ACCENT_FONT, 11, PAGE_H * 0.635, gray=0.35)
    c.showPage()


def page_title(c):
    centered(c, BOOK["title"], TITLE_FONT, 30, PAGE_H * 0.62)
    centered(c, BOOK["subtitle"], BODY_FONT, 16, PAGE_H * 0.57, gray=0.25)
    centered(c, "50 Printable Coloring Pages", ACCENT_FONT, 12,
             PAGE_H * 0.50, gray=0.35)
    centered(c, f"{BOOK['series']}  ·  {BOOK['volume']}",
             ACCENT_FONT, 11, PAGE_H * 0.45, gray=0.4)
    centered(c, f"© {BOOK['shop']} · All rights reserved · Personal use only",
             ACCENT_FONT, 9, 0.6 * inch, gray=0.5)
    c.showPage()


def page_welcome(c):
    centered(c, "Welcome", TITLE_FONT, 24, PAGE_H - 1.4 * inch)
    text = (
        "Pour a cup of tea, light a candle, and step inside. "
        "Beyond this page waits a witch's cozy cottage — fifty rooms, corners, "
        "and quiet moments, all waiting for your color. "
        "Begin at the garden gate and wander at your own pace; the pages grow "
        "richer as you go, ending with ten pages made to be framed. "
        "There is no rush here. This is your hour. Welcome home."
    )
    wrapped(c, text, BODY_FONT, 14, 1.1 * inch, PAGE_H - 2.2 * inch,
            PAGE_W - 2.2 * inch, 22)
    c.showPage()


def page_howto(c):
    centered(c, "Before You Begin", TITLE_FONT, 22, PAGE_H - 1.4 * inch)
    tips = [
        "Print on the heaviest paper your printer allows (90-120 gsm is ideal; "
        "use cardstock for markers).",
        "Set your printer to \"Actual size\" or 100% — never \"Fit to page\" — "
        "so the proportions stay true.",
        "Pages are single-sided, so you can remove and frame your favorites and "
        "avoid bleed-through.",
        "Colored pencils and gel pens shine here. If you use markers, slip a "
        "spare sheet behind the page.",
        "Start with the gentle early pages to warm up; save the masterpiece "
        "finale for when you're in the flow.",
        "Most of all: relax. There is no wrong way to color.",
    ]
    y = PAGE_H - 2.1 * inch
    c.setFillGray(0.15)
    for t in tips:
        c.setFont(ACCENT_FONT, 13)
        c.drawString(1.0 * inch, y, "•")
        y = wrapped(c, t, BODY_FONT, 13, 1.3 * inch, y,
                    PAGE_W - 2.5 * inch, 19) - 8
    c.showPage()


def page_coloring(c, img: Path, footer: str | None):
    box_w = PAGE_W - 2 * M_SIDE
    box_h = PAGE_H - M_TOP - M_BOTTOM
    c.drawImage(str(img), M_SIDE, M_BOTTOM, box_w, box_h,
                preserveAspectRatio=True, anchor="c", mask="auto")
    if footer:
        centered(c, footer, ACCENT_FONT, 9, 0.35 * inch, gray=0.55)
    c.showPage()


def page_index(c, titles: dict[int, str], page_map: dict[int, int]):
    centered(c, "Index", TITLE_FONT, 24, PAGE_H - 1.2 * inch)
    col_x = [1.0 * inch, PAGE_W / 2 + 0.2 * inch]
    col_w = PAGE_W / 2 - 1.2 * inch
    top = PAGE_H - 1.9 * inch
    rows_per_col = 25
    c.setFillGray(0.15)
    for i in range(1, N_PAGES + 1):
        col = 0 if i <= rows_per_col else 1
        row = (i - 1) % rows_per_col
        y = top - row * 0.32 * inch
        title = titles.get(i, f"Page {i}")
        label = f"{i}.  {title}"
        c.setFont(BODY_FONT, 10.5)
        # truncate overly long titles to keep the column clean
        for line in simpleSplit(label, BODY_FONT, 10.5, col_w - 0.4 * inch)[:1]:
            c.drawString(col_x[col], y, line)
        c.setFont(ACCENT_FONT, 10.5)
        c.setFillGray(0.45)
        c.drawRightString(col_x[col] + col_w, y, str(page_map.get(i, "")))
        c.setFillGray(0.15)
    c.showPage()


def page_thankyou(c):
    centered(c, "Thank You", TITLE_FONT, 24, PAGE_H * 0.66)
    text = (
        f"I hope this little cottage gave you a quiet, happy hour. "
        f"If you loved it, the journey continues in \"{BOOK['next_volume']}\" — "
        f"the next volume of {BOOK['series']}. Look for it, and for our money-"
        f"saving bundles, in {BOOK['etsy_or_payhip']}. "
        f"Happy coloring. — {BOOK['shop']}"
    )
    wrapped(c, text, BODY_FONT, 14, 1.1 * inch, PAGE_H * 0.56,
            PAGE_W - 2.2 * inch, 22)
    centered(c, "Personal use only · Please do not resell or redistribute "
             "the files.", ACCENT_FONT, 9, 0.7 * inch, gray=0.5)
    c.showPage()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Assemble the print-ready coloring PDF")
    p.add_argument("--clean", action="store_true",
                   help="upscale to 300 DPI and binarize pages (recommended)")
    p.add_argument("--approved-only", action="store_true",
                   help="include only pages marked Approved in qc_tracker.csv")
    p.add_argument("--matter-only", action="store_true",
                   help="build only front/back matter (preview, no coloring pages)")
    p.add_argument("--no-page-numbers", action="store_true",
                   help="omit the small footer page numbers")
    return p.parse_args()


def main():
    args = parse_args()
    OUT_DIR.mkdir(exist_ok=True)
    titles = read_titles()

    # Decide which pages to include.
    include = list(range(1, N_PAGES + 1))
    if args.approved_only:
        ok = approved_pages()
        if ok is None:
            sys.exit("ERROR: --approved-only but qc_tracker.csv not found. "
                     "Run generate.py and review pages first.")
        include = [i for i in include if i in ok]

    found, missing = {}, []
    if not args.matter_only:
        for i in include:
            img = best_version(i)
            (found.__setitem__(i, img) if img else missing.append(i))
        if missing:
            print(f"WARNING: {len(missing)} page(s) missing in raw/: "
                  f"{', '.join(map(str, missing))}")
        if not found:
            sys.exit("ERROR: no page images found in raw/. Run generate.py first "
                     "(or use --matter-only to preview the matter).")

    # Optional clean/upscale pass into a temp dir.
    tmpdir = None
    if args.clean and found:
        tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(tmpdir.name)
        print(f"Cleaning {len(found)} pages (upscale -> 300 DPI, binarize)…")
        found = {i: clean_image(p, tmp) for i, p in found.items()}

    out_pdf = OUT_DIR / (re.sub(r"[^\w]+", "-",
                                BOOK["title"]).strip("-") + ".pdf")
    c = canvas.Canvas(str(out_pdf), pagesize=letter)
    c.setTitle(BOOK["title"])

    # Front matter.
    cover_src = (found.get(BOOK["cover_source_page"])
                 or best_version(BOOK["cover_source_page"]))
    page_cover(c, cover_src)
    page_title(c)
    page_welcome(c)
    page_howto(c)

    # Coloring pages + build the index page-number map.
    FRONT_MATTER = 4                       # cover, title, welcome, how-to
    page_map = {}
    if not args.matter_only:
        seq = 0
        for i in include:
            if i not in found:
                continue
            seq += 1
            page_map[i] = seq              # colorist-facing page number
            footer = None if args.no_page_numbers else str(seq)
            page_coloring(c, found[i], footer)

    # Back matter.
    page_index(c, titles, page_map)
    page_thankyou(c)

    c.save()
    if tmpdir:
        tmpdir.cleanup()

    n_color = len(page_map)
    print(f"\n✓ Built {out_pdf.relative_to(HERE.parent)}")
    print(f"  {n_color} coloring pages + 6 matter pages = {n_color + 6} total")
    if missing:
        print(f"  (note: {len(missing)} page(s) still missing — re-run generate.py)")
    print("  Next: open the PDF, spot-check at 100%, then upload to Etsy/Payhip.")


if __name__ == "__main__":
    main()
