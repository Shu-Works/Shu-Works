# 02 — Market Research

## Objective

Identify evergreen, series-capable, Pinterest-native coloring book niches with
high perceived value and AI-generation stability — then rank them objectively so
niche selection is repeatable, not a matter of taste.

---

## Market Context (the landscape we're entering)

The printable adult coloring book category on Etsy and Payhip is large, mature,
and crowded — but the crowd is mostly **low-effort, generic, and single-product**.
Typical competitor weaknesses we exploit:

- One-off books with no series identity (no Volume 2, no bundle).
- Flat, random page order — no journey, no progressive difficulty.
- Mixed-style pages (clearly different AI generations stitched together).
- Weak covers that don't read as a thumbnail on Etsy mobile.
- Generic themes ("flowers," "mandalas") with no story or world.

**Our opening:** combine *cozy* + *fantasy* + *storytelling* into cohesive worlds
that beg to be collected. Cozy/cottagecore + fantasy is the highest-engagement
intersection on Pinterest, has evergreen (non-trend) demand, and is dominated by
*scenes and objects* rather than human figures — which is exactly what AI line-art
generation does most reliably.

---

## Why Cozy + Fantasy Wins (strategic thesis)

1. **Evergreen, not trendy.** Witches, fairy gardens, mushrooms, tea houses, and
   enchanted libraries don't expire in 3 months like a meme. Demand is seasonal at
   most (Halloween, winter), never a fad.
2. **Pinterest-native.** Cozy aesthetics are the single most-pinned lifestyle
   category. A vertical, atmospheric line-art scene is a perfect pin.
3. **AI-stable subject matter.** Interiors, plants, objects, architecture, and
   creatures-as-scenery generate clean line art reliably. We deliberately avoid
   niches that depend on consistent human faces/hands (AI's weakest output).
4. **Infinite series expansion.** A "world" can be revisited by season, by room,
   by character, by region — Volume 2 writes itself.
5. **High perceived value.** A *world* feels like a book. A pile of unrelated
   images feels like a clip-art dump.

---

## Scoring Methodology

Every candidate niche is scored 1–5 on eight dimensions. **Max score = 40.**

| # | Dimension | What a 5 looks like |
| --- | --- | --- |
| 1 | Visual Appeal | Inherently beautiful as line art; rich detail without clutter |
| 2 | Cover Appeal | Produces an instantly compelling thumbnail at mobile size |
| 3 | Pinterest Appeal | Vertical, cozy, aspirational — begs to be pinned & saved |
| 4 | Coloring Enjoyment | Varied shapes, open spaces + detail, satisfying to color |
| 5 | Series Potential | Easily yields 10+ themed volumes |
| 6 | Expansion Potential | Spawns sub-themes, seasons, spin-offs, bundles |
| 7 | Competition Opportunity | Demand is high but quality competition is thin |
| 8 | AI Generation Stability | Subject matter generates clean line art consistently |

Scoring is deliberately conservative: AI Generation Stability and Coloring
Enjoyment act as filters — a gorgeous niche that generates broken anatomy or
produces "nothing to color" pages is downgraded hard.

---

## Candidate Pool (12 evaluated → Top 10 reported)

The full scored shortlist lives in `03_Top10_Niches.csv`. Summary of findings:

- **Tier S (36–40):** Cozy Witch's Cottage, Moonlit Tea House, Enchanted Library
- **Tier A (32–35):** Cozy Fantasy Village, Fairy Garden World, Magical Greenhouse,
  Mushroom Village, Enchanted Terrarium
- **Tier B (28–31):** Japanese Fantasy Shrine, Cozy Dragon Sanctuary

Two candidates were cut before the Top 10:
- **Cozy Winter Cabin** — strong but *seasonal*, not fully evergreen (cut for now,
  revisited as a Q4 seasonal release).
- **Celestial/Zodiac** — high competition and AI tends toward large black areas
  (poor coloring space). Cut.

---

## Key Insight Driving Selection

The winning niche must score 5 on **both** *Series Potential* and *AI Generation
Stability*, because those are the two pillars of a *factory* (not a product).
A niche can be slightly less beautiful and still win if it scales reliably.

By that filter, **Cozy Witch's Cottage** is the flagship: it is a single coherent
*world* (cottage → library → apothecary → kitchen → garden → familiars), every
sub-area is a future volume, and 95% of its subject matter is objects/interiors/
plants that AI renders as clean line art. See `04_Selected_Niche.md`.

---

## Repeatable Research Loop (run weekly)

1. List 8–12 candidate cozy/fantasy/storytelling worlds.
2. Score each on the 8 dimensions (1–5).
3. Cut anything scoring <3 on AI Stability or Coloring Enjoyment.
4. Pick the highest total that we don't already have in production.
5. If two tie, pick the one with the stronger *series* runway.
6. Log results to a dated copy of `03_Top10_Niches.csv`.

This loop guarantees niche selection is data-driven and identical every week —
the hallmark of a factory, not a hobby.
