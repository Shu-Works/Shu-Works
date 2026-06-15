# Book #2 — *The Witch's Library* (Production Folder)

**This folder is the proof that the factory scales.** It was created by copying
`book01/` and changing only:

1. `book_config.py` — title, volume, cover page, next-volume cross-sell.
2. `06_Page_Structure.csv` — the new 50-page plan (library theme).
3. `07_Generation_Prompts.csv` — the 50 matching prompts.

Everything else (`generate.py`, `package.py`, `make_listing_assets.py`,
`requirements.txt`, `.env.example`, `.gitignore`) is **identical** to Book #1.
The scripts read the **book-local** `06`/`07` CSVs automatically, so each volume
is self-contained.

## Run it

```bash
cd coloring-book-factory/book02
pip install -r requirements.txt
cp .env.example .env        # paste your OPENAI_API_KEY

python generate.py --dry-run             # check the 50 library prompts
python generate.py                       # generate all 50 pages (~$6 hd)
# review vs ../08_Quality_Checklist.md → fill qc_tracker.csv → fix via regen_prompts.csv
python package.py --clean                # print-ready PDF
python make_listing_assets.py            # Etsy images + Pinterest pins
```

## Tool docs

The full usage notes, flags, DALL·E 3 caveats, and the weekly loop are documented
once in **`../book01/README.md`** — they apply identically here. This README only
records what differs for Volume 2.

## To start Book #3

Copy this folder to `book03/`, edit `book_config.py`, and write its `06`/`07`
CSVs (next room in the series: *The Witch's Apothecary*). That's the whole
process — the factory is a copy-and-edit operation.
