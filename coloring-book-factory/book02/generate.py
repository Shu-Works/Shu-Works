#!/usr/bin/env python3
"""
generate.py — Coloring Book Factory · DALL·E 3 batch runner
============================================================

Reads the per-page prompts CSV and generates all 50 coloring-book pages via the
OpenAI Images API (DALL·E 3), saving clean line-art PNGs and a QC tracking sheet.

Designed for the weekly factory loop:
  - Resumable: skips pages already generated (use --force to overwrite).
  - Regeneration-aware: --regen reads a regen prompts file and saves _v2, _v3 ...
  - Self-documenting: writes generation_log.csv and seeds qc_tracker.csv.

DALL·E 3 quirks handled here (see README.md):
  1. No native negative prompts -> folded into the positive text as exclusions.
  2. Auto prompt-rewriting -> suppressed with an anti-embellishment preamble.
  3. Only 3 sizes -> we use the tallest (1024x1792) and letter-fit at packaging.

Usage
-----
  python generate.py                       # generate all pending pages
  python generate.py --only 21,30,32       # (re)generate specific pages
  python generate.py --force               # overwrite existing outputs
  python generate.py --regen               # use regen_prompts.csv, save _vN
  python generate.py --dry-run             # build prompts, call nothing
  python generate.py --quality standard    # cheaper test pass

Requires:  pip install -r requirements.txt   and   OPENAI_API_KEY in env/.env
"""

from __future__ import annotations

import argparse
import base64
import csv
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
# Prefer a book-local CSV (self-contained per-volume folder); fall back to parent.
_local_prompts = HERE / "07_Generation_Prompts.csv"
PROMPTS_CSV = _local_prompts if _local_prompts.exists() else HERE.parent / "07_Generation_Prompts.csv"
REGEN_CSV = HERE / "regen_prompts.csv"                     # failed-page fixes
RAW_DIR = HERE / "raw"                                     # PNG output
QC_TRACKER = HERE / "qc_tracker.csv"                       # QC review sheet
LOG_CSV = HERE / "generation_log.csv"                      # run audit log

MODEL = "dall-e-3"
SIZE = "1024x1792"        # tallest DALL·E 3 size; letter-fit at packaging stage
DEFAULT_QUALITY = "hd"    # "hd" for finals, "standard" for cheap test passes
STYLE = "natural"         # "natural" avoids over-stylization vs. "vivid"

# Approx USD per image (1024x1792). Used only for the pre-run cost estimate.
PRICE = {"hd": 0.120, "standard": 0.080}

MAX_RETRIES = 4
BACKOFF_BASE_S = 2        # 2s, 4s, 8s, 16s

# Suppress DALL·E 3's habit of "improving" (= embellishing) our prompts.
ANTI_REWRITE = (
    "I NEED to test how the tool works with extremely simple prompts. "
    "DO NOT add any detail, just use the description AS-IS: "
)

# Folded-in exclusions (DALL·E 3 has no negative-prompt field).
HARD_EXCLUSIONS = (
    "Strictly clean black-and-white line art on a pure white background. "
    "Do NOT include any of the following: color, grayscale, gray tones, "
    "shading, hatching, gradients, solid black fills, dark/black backgrounds, "
    "text, words, letters, numbers, labels, watermark, signature, artist mark, "
    "frame, or border."
)

# QC columns mirror 08_Quality_Checklist.md (A1-A8 hard-fail, B1-B10 quality).
QC_A = [f"A{i}" for i in range(1, 9)]
QC_B = [f"B{i}" for i in range(1, 11)]
QC_HEADER = (
    ["page", "title", "file"] + QC_A + QC_B + ["class", "notes"]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_prompts(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"ERROR: prompts file not found: {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit(f"ERROR: prompts file is empty: {path}")
    return rows


def build_prompt(positive: str, negative: str) -> str:
    """Assemble the final DALL·E 3 text prompt from the CSV fields."""
    neg = negative.strip()
    neg_clause = ""
    if neg:
        # The CSV negative is a comma list; phrase it as an explicit ban.
        neg_clause = f" Also avoid: {neg}."
    return f"{ANTI_REWRITE}{positive.strip()} {HARD_EXCLUSIONS}{neg_clause}"


def out_path(page: int, title: str, attempt: int) -> Path:
    base = f"p{page:02d}_{slugify(title)}"
    if attempt > 1:
        base += f"_v{attempt}"
    return RAW_DIR / f"{base}.png"


def existing_attempts(page: int, title: str) -> int:
    """How many versions of this page already exist (for regen versioning)."""
    pattern = re.compile(rf"^p{page:02d}_{re.escape(slugify(title))}(_v\d+)?\.png$")
    return sum(1 for p in RAW_DIR.glob(f"p{page:02d}_*.png") if pattern.match(p.name))


def append_log(row: dict) -> None:
    new = not LOG_CSV.exists()
    with LOG_CSV.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["timestamp", "page", "title", "file",
                                           "status", "quality", "detail"])
        if new:
            w.writeheader()
        w.writerow(row)


def seed_qc_tracker(rows: list[dict]) -> None:
    """Create qc_tracker.csv with one blank-to-fill row per page (if absent)."""
    if QC_TRACKER.exists():
        return
    with QC_TRACKER.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(QC_HEADER)
        for r in rows:
            page = int(r["Page Number"])
            title = r["Page Title"]
            blanks = [""] * (len(QC_A) + len(QC_B))
            w.writerow([page, title, out_path(page, title, 1).name, *blanks,
                        "PENDING", ""])
    print(f"  seeded QC tracker -> {QC_TRACKER.name}")


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def make_client():
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("ERROR: openai SDK missing. Run: pip install -r requirements.txt")
    # Load .env if python-dotenv is available (optional convenience).
    try:
        from dotenv import load_dotenv
        load_dotenv(HERE / ".env")
    except ImportError:
        pass
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("ERROR: OPENAI_API_KEY not set. Copy .env.example -> .env and fill it.")
    return OpenAI(api_key=key)


def generate_one(client, prompt: str, quality: str) -> bytes:
    """Call DALL·E 3 with retry + exponential backoff. Returns PNG bytes."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.images.generate(
                model=MODEL,
                prompt=prompt,
                size=SIZE,
                quality=quality,
                style=STYLE,
                n=1,                       # DALL·E 3 supports only n=1
                response_format="b64_json",
            )
            return base64.b64decode(resp.data[0].b64_json)
        except Exception as e:  # noqa: BLE001 - surface and back off on any API error
            last_err = e
            if attempt == MAX_RETRIES:
                break
            wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
            print(f"    ! attempt {attempt} failed ({e}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"giving up after {MAX_RETRIES} attempts: {last_err}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DALL·E 3 coloring-book batch runner")
    p.add_argument("--only", help="comma-separated page numbers, e.g. 21,30,32")
    p.add_argument("--force", action="store_true", help="overwrite existing PNGs")
    p.add_argument("--regen", action="store_true",
                   help="use regen_prompts.csv; save as next _vN")
    p.add_argument("--dry-run", action="store_true",
                   help="build prompts and print plan; call no API")
    p.add_argument("--quality", choices=["hd", "standard"], default=DEFAULT_QUALITY)
    return p.parse_args()


def select_rows(rows: list[dict], only: str | None) -> list[dict]:
    if not only:
        return rows
    wanted = {int(x) for x in only.split(",") if x.strip()}
    return [r for r in rows if int(r["Page Number"]) in wanted]


def load_regen_map() -> dict[int, dict]:
    """page -> {positive, negative} overrides from regen_prompts.csv."""
    if not REGEN_CSV.exists():
        sys.exit(f"ERROR: --regen requested but {REGEN_CSV.name} not found.")
    out = {}
    with REGEN_CSV.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r.get("Page Number"):
                continue
            out[int(r["Page Number"])] = {
                "positive": r.get("Positive Prompt", ""),
                "negative": r.get("Negative Prompt", ""),
            }
    if not out:
        sys.exit(f"ERROR: {REGEN_CSV.name} has no rows to regenerate.")
    return out


def main() -> None:
    args = parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_prompts(PROMPTS_CSV)
    seed_qc_tracker(rows)

    regen_map = load_regen_map() if args.regen else {}
    if args.regen:
        rows = [r for r in rows if int(r["Page Number"]) in regen_map]

    rows = select_rows(rows, args.only)

    # Plan the work (skip already-done unless --force / --regen).
    plan = []
    for r in rows:
        page = int(r["Page Number"])
        title = r["Page Title"]
        if args.regen:
            attempt = existing_attempts(page, title) + 1
            pos = regen_map[page]["positive"] or r["Positive Prompt"]
            neg = regen_map[page]["negative"] or r["Negative Prompt"]
        else:
            attempt = 1
            pos, neg = r["Positive Prompt"], r["Negative Prompt"]
        dest = out_path(page, title, attempt)
        if dest.exists() and not args.force and not args.regen:
            continue
        plan.append((page, title, dest, build_prompt(pos, neg)))

    if not plan:
        print("Nothing to do — all selected pages already generated. "
              "(Use --force to overwrite or --regen to fix failures.)")
        return

    est = len(plan) * PRICE.get(args.quality, 0.12)
    print(f"Coloring Book Factory · DALL·E 3 batch")
    print(f"  model={MODEL} size={SIZE} quality={args.quality} style={STYLE}")
    print(f"  pages to generate: {len(plan)}   est. cost: ~${est:.2f}")
    print(f"  output dir: {RAW_DIR}")
    if args.dry_run:
        print("\n--dry-run: showing assembled prompts, calling nothing.\n")
        for page, title, dest, prompt in plan:
            print(f"[{page:02d}] {title} -> {dest.name}")
            print(f"     {prompt}\n")
        return

    client = make_client()
    ok = fail = 0
    for page, title, dest, prompt in plan:
        print(f"[{page:02d}] {title} -> {dest.name}")
        try:
            png = generate_one(client, prompt, args.quality)
            dest.write_bytes(png)
            ok += 1
            append_log({"timestamp": now_iso(), "page": page, "title": title,
                        "file": dest.name, "status": "OK",
                        "quality": args.quality, "detail": ""})
            print(f"     ✓ saved ({len(png)//1024} KB)")
        except Exception as e:  # noqa: BLE001
            fail += 1
            append_log({"timestamp": now_iso(), "page": page, "title": title,
                        "file": dest.name, "status": "FAILED",
                        "quality": args.quality, "detail": str(e)})
            print(f"     ✗ FAILED: {e}")

    print(f"\nDone. {ok} succeeded, {fail} failed.")
    print(f"Next: review every page against 08_Quality_Checklist.md, "
          f"mark {QC_TRACKER.name}, then re-run failures with --regen.")


if __name__ == "__main__":
    main()
