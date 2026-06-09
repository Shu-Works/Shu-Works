# 01 — Project Summary

## The Coloring Book Factory

**This is not a coloring book. This is a factory.**

We are building a repeatable, scalable digital publishing system that produces
high-perceived-value printable adult coloring books and sells them on **Etsy**
and **Payhip**. Every week the asset library grows. Every book is designed to
become a *series*. Every series is designed to become a *bundle*.

---

## North Star

> Build a digital asset library that compounds — where each book makes the next
> book cheaper to produce and the whole catalog more valuable than the sum of
> its parts.

A single coloring book is a product. A factory is an asset that prints money
while we sleep, every weekend, forever. We optimize for the second thing.

---

## Production Targets

| Metric | Target |
| --- | --- |
| New books per week | 2 |
| Pages per book | 50 unique pages |
| Books per month | ~8 |
| Books per quarter | ~24 |
| First bundle launch | After Book #3 in a series |
| Mega-collection launch | After Book #10 |

---

## The Three Things (what makes this work)

Following the "Three Things" rule — everything reduces to three pillars:

1. **High perceived value** — 50 pages, journey structure, progressive difficulty,
   a stunning final 10 pages. The buyer feels they got a *book*, not a PDF.
2. **Series-first design** — every niche is chosen because it can spawn 10+ books.
   We never design a one-off. The cover, the title, the theme all assume Volume 2.
3. **Pinterest-native visuals** — vertical, cozy, share-worthy. Pinterest is the
   free traffic engine; if a page isn't pinnable, it isn't in the book.

---

## What We Sell (the dream, not the spec)

We do not sell "50 black and white PDF pages."

We sell **a quiet evening, a cup of tea, and a doorway into a cozy world** — a
ritual of calm that the buyer returns to again and again. The product is stress
relief, escape, and the small pride of a finished page. The spec is just the
delivery mechanism.

---

## Core Principles (non-negotiable)

- **Quality is the moat.** The moment "good enough" feels acceptable, the product
  becomes second-rate. Every page passes QC or it does not ship.
- **Simplicity in the catalog.** Three flagship series, deeply developed — not 30
  shallow themes. Depth beats breadth.
- **No trademarked, copyrighted, franchised, or celebrity content. Ever.** This is
  a legal and brand red line, not a guideline.
- **Repeatability over heroics.** If a step can't be done the same way next week,
  it isn't part of the factory.

---

## Asset Flow (one book, start to finish)

```
Niche Research → Niche Selection → Book Concept → 50-Page Structure
   → Prompt Generation → Image Generation → Quality Control
   → Regeneration (failed pages) → PDF Packaging → Cover & Previews
   → Etsy Listing → Payhip Listing → Pinterest Pins → Bundle (later)
```

Each stage has a dedicated file in this repository (02–12) so the workflow is
documented, auditable, and handed off identically every single week.

---

## File Map

| File | Purpose |
| --- | --- |
| `01_Project_Summary.md` | This document — the factory's mission & overview |
| `02_Market_Research.md` | Niche research methodology & findings |
| `03_Top10_Niches.csv` | Scored niche shortlist (data) |
| `04_Selected_Niche.md` | The chosen flagship niche + rationale |
| `05_Book_Concept.md` | Concept for the first book |
| `06_Page_Structure.csv` | All 50 pages, fully specified (data) |
| `07_Generation_Prompts.csv` | A positive/negative prompt per page (data) |
| `08_Quality_Checklist.md` | The QC review system |
| `09_Regeneration_Rules.md` | How to fix & re-prompt failed pages |
| `10_Etsy_Listing.md` | Etsy listing assets (SEO, tags, previews) |
| `11_Payhip_Product.md` | Payhip listing assets |
| `12_Bundle_Strategy.md` | Bundles & long-term catalog strategy |

---

## Definition of Success

The factory is working when:

- [x] A profitable, series-capable niche is selected
- [x] A complete, journey-structured 50-page outline exists
- [x] Every page has a generation prompt
- [x] A quality-control standard exists and is enforced
- [x] Etsy listing assets are prepared
- [x] Payhip listing assets are prepared
- [x] Future bundle opportunities are mapped
- [x] **The entire workflow can be repeated next week by following these files**

The last bullet is the whole point. A blueprint that only works once is a
project. A blueprint that works every week is a *business*.
