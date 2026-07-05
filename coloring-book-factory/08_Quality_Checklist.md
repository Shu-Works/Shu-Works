# 08 — Quality Control Checklist

> Quality is the moat. The moment "good enough" feels acceptable, the product
> becomes second-rate. **Every page passes QC or it does not ship.**

This is the gate between generation and packaging. Each of the 50 pages is
reviewed against the checklist below and classified **Approved**, **Needs
Review**, or **Rejected**. Rejected/Needs-Review pages go to
`09_Regeneration_Rules.md`.

---

## How to Use

For each page, run the **Hard-Fail checks** first (any failure = automatic
Reject). Then run the **Quality checks** (failures = Needs Review). A page with
zero failures across both sections = Approved.

---

## Section A — Hard-Fail Checks (any ✗ = REJECT)

| # | Check | Why it matters |
| --- | --- | --- |
| A1 | **No text artifacts** — no words, gibberish letters, or labels with text | AI text is broken; instantly looks unprofessional |
| A2 | **No watermark** — no stock-site or model watermark anywhere | Legal + credibility killer |
| A3 | **No signature** — no fake artist signature or initials | Implies false authorship |
| A4 | **No frame/border** (unless page is an intentional border page) | We sell borderless coloring pages |
| A5 | **No grayscale or shading fills** — pure black line on white only | Grayscale ruins printable coloring pages |
| A6 | **No broken anatomy** — animals/familiars have correct limbs, eyes, shape | Broken cats/owls look amateur |
| A7 | **No excessive solid black areas** — black is line work only, not filled mass | Solid black = wasted ink + nothing to color |
| A8 | **Correct format** — 8.5×11 portrait ratio, print-resolution (≥300 DPI) | Wrong ratio crops on print |

---

## Section B — Quality Checks (any ✗ = NEEDS REVIEW)

| # | Check | Standard |
| --- | --- | --- |
| B1 | **Adequate coloring space** | Has large open areas, not wall-to-wall tiny lines |
| B2 | **Balanced detail** | Both intricate zones AND breathable spaces present |
| B3 | **Clean, closed outlines** | Lines connect; colorable regions are enclosed |
| B4 | **No duplicate composition** | Distinct from its neighbors and from earlier pages |
| B5 | **Theme consistency** | Cozy-witch tone; not dark/scary; fits the cottage world |
| B6 | **Style consistency** | Line weight & rendering match the rest of the book |
| B7 | **Recurring motifs present** | At least the page's intended motifs appear (see col. "Consistency Notes") |
| B8 | **Visual balance** | Composition isn't lopsided; focal point is clear |
| B9 | **Difficulty fit** | Matches the page's chapter (easy pages stay easy) |
| B10 | **Print test** | Prints cleanly at 8.5×11 with no muddy/lost detail |

---

## Section C — Book-Level Checks (run once, on the assembled 50)

| # | Check | Standard |
| --- | --- | --- |
| C1 | **Difficulty curve holds** | Rises Ch1 → Ch4; finale pages are clearly the most impressive |
| C2 | **Composition variety** | No composition type repeats >2× in a row (per `05`) |
| C3 | **Motif continuity** | Cat/owl/raven/moon/teacup recur and feel like one world |
| C4 | **No duplicate scenes across the 50** | Every page is unique |
| C5 | **Front/back matter present** | Cover, title, welcome, how-to, index, thank-you/cross-sell |
| C6 | **Finale delivers** | Pages 41–50 are genuinely screenshot-worthy |

---

## Classification

| Class | Meaning | Action |
| --- | --- | --- |
| **Approved** | 0 failures in A, B, and C | Send to packaging |
| **Needs Review** | 0 hard-fails (A), but ≥1 quality flag (B) | Human judgment: accept, minor fix, or regenerate |
| **Rejected** | ≥1 hard-fail (A) | Regenerate per `09_Regeneration_Rules.md` |

---

## QC Log Template (one row per page — copy into a tracking sheet)

```
Page | A1 A2 A3 A4 A5 A6 A7 A8 | B1..B10 | Class | Notes / Action
```

Example:
```
07 | ✓ ✓ ✓ ✓ ✓ ✓ ✓ ✓ | all ✓ | Approved | clean
21 | ✓ ✓ ✓ ✓ ✗ ✓ ✗ ✓ | B-... | Rejected | night sky filled black -> regen
30 | ✓ ✓ ✓ ✓ ✓ ✓ ✓ ✓ | B1 ✗ | Needs Review | cauldron area too dense -> simplify
```

---

## The Yardstick Rule

The reviewer is the quality yardstick. The standard isn't "would a buyer
tolerate this" — it's **"would I pay money for this and be delighted."** If a page
makes you hesitate, it is a Needs Review at minimum. Hesitation is a signal, not
noise.
