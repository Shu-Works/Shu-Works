# Book #1 — Production Tools (Generate → Package → List)

Three scripts take *The Enchanted Witch's Cottage* from prompts to a sellable
product **and** its full set of shop graphics:

1. **`generate.py`** — produces the 50 coloring-page PNGs via the OpenAI Images
   API (DALL·E 3) from `../07_Generation_Prompts.csv`.
2. **`package.py`** — assembles the approved PNGs into a print-ready, US-Letter,
   300-DPI PDF with cover, front matter, index, and back matter.
3. **`make_listing_assets.py`** — turns the pages into Etsy listing images and
   Pinterest pins, per `../10_Etsy_Listing.md`.

Per-volume settings (title, series, shop name, cover page, masterpiece pages)
live in one place: **`book_config.py`**, shared by `package.py` and
`make_listing_assets.py`. All scripts run on your own machine and are re-runnable.

---

## Quick start

```bash
cd coloring-book-factory/book01

python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env        # then edit .env and paste your OPENAI_API_KEY

python generate.py --dry-run    # sanity check: prints the 50 assembled prompts
python generate.py              # generate all 50 pages (~$6 at hd quality)
```

Output PNGs land in `raw/` as `p01_the-garden-gate.png`, `p02_...`, etc.
A QC sheet is seeded at `qc_tracker.csv` and an audit log at `generation_log.csv`.

---

## Commands

| Command | What it does |
| --- | --- |
| `python generate.py` | Generate all *pending* pages (skips ones already in `raw/`) |
| `python generate.py --dry-run` | Build & print prompts, call no API (free) |
| `python generate.py --quality standard` | Cheaper test pass (~$4 for 50) |
| `python generate.py --only 21,30,32` | (Re)generate just these page numbers |
| `python generate.py --force` | Overwrite existing PNGs |
| `python generate.py --regen` | Regenerate pages listed in `regen_prompts.csv`, saved as `_v2`, `_v3` … |

---

## Packaging the PDF (`package.py`)

Once pages are generated and reviewed, assemble the book:

```bash
python package.py --matter-only        # preview cover + front/back matter (no pages)
python package.py --clean              # full book; upscale->300 DPI + binarize (recommended)
python package.py --clean --approved-only   # include only pages marked Approved in qc_tracker.csv
```

Output lands in `output/<Book-Title>.pdf` — a single-sided, US-Letter (8.5×11),
300-DPI PDF in this order: **cover → title → welcome → how-to → 50 coloring
pages → index → thank-you/cross-sell** (per `../05_Book_Concept.md`).

Notes:
- `--clean` upscales each image toward 300 DPI and **binarizes** it to pure
  black/white — this sharpens lines for print and silently fixes minor grayscale/
  shading (DALL·E 3's most common flaw). Strongly recommended for finals.
- It auto-picks the **highest version** of each page (`_v3` beats `_v2` beats
  base), so regenerated pages win without renaming anything.
- Small footer page numbers are added by default (`--no-page-numbers` to omit);
  the index references them.
- Edit the `BOOK = {…}` config block at the top of `package.py` per volume
  (title, series, volume, shop name, cover source page, next-volume cross-sell).

## Generating shop graphics (`make_listing_assets.py`)

```bash
python make_listing_assets.py                  # build everything available
python make_listing_assets.py --etsy-only
python make_listing_assets.py --pinterest-only
```

Output lands in `listing/`:
- `etsy/` — ten **2000×2000** images: cover mockup, 50-page grid, before/after,
  lifestyle, masterpiece showcase, difficulty journey, sample collage,
  what-you-get, series teaser, how-it-works.
- `pinterest/` — one **1000×1500** (2:3) pin per masterpiece page.

Notes:
- Image assets whose source page is missing are skipped (with a warning), so you
  can run this before all 50 pages exist.
- The **before/after** right panel is a *stylized pastel wash* (an honest "what it
  could become"), not a real color-in. For the strongest listing, swap it with
  your own colored sample.
- Pair these images with the **copy** in `../10_Etsy_Listing.md` (titles, tags,
  Pinterest captions) and `../11_Payhip_Product.md`.

## The weekly loop (how this fits the factory)

```
1. python generate.py                 # produce 50 raw pages
2. Review each page vs ../08_Quality_Checklist.md; fill qc_tracker.csv
3. For every Rejected/Needs-Review page, write a fix row in regen_prompts.csv
   (use ../09_Regeneration_Rules.md as the playbook)
4. python generate.py --regen         # produce fixed _vN versions
5. Repeat 2-4 until all 50 are Approved
6. python package.py --clean          # assemble the print-ready PDF
7. python make_listing_assets.py      # build Etsy images + Pinterest pins
8. Upload PDF + images; paste copy from ../10 and ../11; schedule the pins
```

`regen_prompts.csv` ships with 3 example fix-rows (pages 21, 30, 32) that match
the worked examples in `09`. **Before a real run, clear it and add only the pages
that actually failed QC.**

---

## DALL·E 3 — what you need to know (handled in the script)

- **No negative-prompt field.** DALL·E 3 ignores a separate negative prompt, so
  the script folds the CSV negatives into the positive text as explicit
  "do NOT include …" bans. This is the single biggest cause of bad coloring
  pages (color/shading/text leaking in), and it's why we ban hard.
- **Auto prompt-rewriting.** DALL·E 3 silently "improves" prompts, which breaks
  our deliberate compositions. The script prepends an anti-embellishment preamble
  to keep the prompt close to ours. It helps but isn't perfect — if a page drifts,
  simplify the prompt and re-run that page with `--only`.
- **Only 3 sizes.** There is no true 8.5×11 (0.77) ratio. We generate at the
  tallest option, `1024×1792` (0.57, taller than Letter). **The packaging step**
  centers/letter-fits each image onto an 8.5×11, 300 DPI page — do not print the
  raw PNG directly.
- **One image per call.** DALL·E 3 forces `n=1`, so this is 50 sequential calls.
- **Cost.** ~\$0.12/image at `hd`, ~\$0.08 at `standard`. Full book ≈ \$6 (hd).
  Always do a `--dry-run` first (free), and a `--quality standard` test pass
  before committing to an `hd` run.

---

## Important: DALL·E 3 is not a true coloring-book engine

DALL·E 3 was your chosen backend for speed and a stable API — good for getting
Book #1 shipped. But it produces uneven line weights and occasional shading more
often than a dedicated line-art model. Expect a **higher QC reject rate** than
Ideogram or an SD line-art LoRA, and budget extra `--regen` cycles.

When the factory scales, the recommended migration is to swap the `generate_one()`
function for an Ideogram or Stable-Diffusion call — everything else (CSV input,
QC tracker, regen loop, packaging) stays identical. The runner is engine-agnostic
by design; only that one function is provider-specific.

---

## Files

| File | Role |
| --- | --- |
| `generate.py` | The image-generation batch runner |
| `package.py` | The print-ready PDF assembler |
| `make_listing_assets.py` | The Etsy/Pinterest graphics generator |
| `book_config.py` | Shared per-volume settings (title, series, fonts, palette) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for your API key (copy to `.env`) |
| `regen_prompts.csv` | Queue of failed pages to fix & regenerate |
| `raw/` | Generated PNGs *(git-ignored)* |
| `output/` | Assembled PDF(s) *(git-ignored)* |
| `listing/` | Generated Etsy images + Pinterest pins *(git-ignored)* |
| `qc_tracker.csv` | QC review sheet, auto-seeded *(git-ignored)* |
| `generation_log.csv` | Per-call audit log *(git-ignored)* |
