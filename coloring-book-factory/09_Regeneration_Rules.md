# 09 — Regeneration Rules

When a page is classified **Rejected** or **Needs Review** in
`08_Quality_Checklist.md`, it does not get quietly dropped or shipped anyway. It
goes through this loop until it passes — **without breaking consistency with the
rest of the book.**

For every failed page, produce three things:

1. **Failure Reason** — which QC check failed and why
2. **Correction Strategy** — what to change in the prompt or approach
3. **Regeneration Prompt** — the revised prompt, ready to run

---

## The Regeneration Loop

```
Failed page → Diagnose (which check?) → Pick fix from playbook below
   → Rewrite prompt → Regenerate → Re-run QC
   → Pass? ship. Fail again? escalate after 3 attempts.
```

**Escalation rule:** if a page fails 3 regeneration attempts, swap the *scene*
(use an alternate from the same chapter) rather than burning more cycles. The
journey matters more than any single composition. Never ship a 4th-attempt
compromise.

---

## Diagnosis → Fix Playbook

| Failure (QC check) | Likely cause | Correction strategy | Prompt change |
| --- | --- | --- | --- |
| A1 Text artifacts | Model added labels/letters | Remove text-bearing objects or force-blank them | Add to negative: `text, words, letters, labels, typography`; in positive say "blank label" |
| A2/A3 Watermark/signature | Model artifact | Re-roll; strengthen negatives | Add: `watermark, signature, artist mark, initials` |
| A4 Frame/border | Model framed the art | Explicitly forbid framing | Add: `frame, border, vignette edge`; positive: "full bleed, no border" |
| A5 Grayscale/shading | Model shaded it | Force pure line art | Add: `grayscale, shading, gray tones, hatching, gradient`; positive: "pure black outline line art, no shading" |
| A6 Broken anatomy | Animal pose too complex | Simplify pose; make creature sleeping/curled/static | Positive: "simple curled sleeping [animal], clear correct anatomy"; negative: `deformed, extra limbs, fused, malformed` |
| A7 Excessive black | Filled night sky/fur/shadows | Convert masses to outlines | Add: `solid black fill, dark fill, black background, filled shadows`; positive: "rendered as outlines only, white interior" |
| A8 Wrong format | Wrong aspect/res | Regenerate at correct spec | Positive: "8.5x11 portrait ratio, 300 DPI, high resolution" |
| B1 No coloring space | Over-detailed | Reduce element count; enlarge subjects | Positive: "large open coloring spaces, fewer larger elements, minimal background" |
| B2 Unbalanced detail | All-dense or all-empty | Rebalance | Positive: "balanced detail, intricate focal area with open surrounding space" |
| B3 Broken outlines | Lines don't close | Re-roll; request closed shapes | Positive: "clean closed continuous outlines, enclosed colorable regions" |
| B4 Duplicate composition | Too similar to neighbor | Change composition type / angle | Positive: switch to a different composition type from `05` (e.g. vignette→hero object); change viewing angle |
| B5 Theme inconsistency | Too dark/scary | Re-cozy it | Positive: "cozy, warm, whimsical, friendly, Ghibli cottagecore"; negative: `scary, horror, dark, creepy, gothic, gore` |
| B6 Style inconsistency | Line weight off | Match the book bible | Positive: "even confident medium line weight, slightly heavier outer contours, consistent coloring-book style" |
| B7 Missing motifs | Recurring element absent | Add the motif back | Positive: add the page's required motif(s) from the CSV "Consistency Notes" |
| B8 Visual imbalance | Lopsided | Recompose | Positive: "balanced composition, clear central focal point" |
| B9 Difficulty mismatch | Too hard/easy for chapter | Adjust density | Positive: tune element count to match chapter (Ch1 simple ↔ Ch4 intricate) |
| B10 Print issues | Muddy at print size | Reduce fine clutter | Positive: "bold clean lines that hold at print size, avoid hairline detail" |

---

## Worked Examples

### Example 1 — Page 21 "Moonlit Windowpane" (Rejected: A7 + A5)

- **Failure Reason:** The night sky behind the window was generated as a solid
  black fill (A7), with gray gradient toward the edges (A5). A coloring page can't
  have a black sky — there's nothing to color and it floods the printer.
- **Correction Strategy:** Render night as a *white* sky with an outlined crescent
  moon and outlined star shapes only. Forbid all dark/gradient fills explicitly.
- **Regeneration Prompt (positive):** "black and white line art coloring page for
  adults, a cottage window at night, white sky shown only through an outlined
  crescent moon and small outlined five-point stars, framed by curtains and a
  potted plant on the sill, pure black outline line art, no shading, large open
  white areas, white background, 8.5x11 portrait"
- **Negative:** "grayscale, shading, gray tones, gradient, solid black fill, dark
  night fill, black background, color, text, watermark, signature, frame"

### Example 2 — Page 30 "The Potion in Progress" (Needs Review: B1)

- **Failure Reason:** The cauldron, ingredients, scrolls, and bottles were packed
  edge-to-edge — almost no open coloring space (B1). Fails the "balanced detail"
  promise.
- **Correction Strategy:** Keep the cauldron as the hero but thin the surrounding
  clutter by ~40%; open up the worktable surface and the area around the steam.
- **Regeneration Prompt (positive):** "black and white line art coloring page for
  adults, a bubbling cauldron as the clear focal point on a worktable with
  decorative steam swirls, a few select ingredients and two bottles, one open
  blank book, generous open table surface and background, balanced detail, clean
  outlines, white background, 8.5x11 portrait"
- **Negative:** "grayscale, shading, color, text, watermark, signature, frame,
  solid black fill, cluttered, wall-to-wall detail, no open space"

### Example 3 — Page 32 "The Familiar Trio" (Rejected: A6)

- **Failure Reason:** The raven had a fused/extra wing and the owl's eyes were
  malformed (A6). Multi-animal scenes strain anatomy.
- **Correction Strategy:** Pose all three familiars static and simple (sitting/
  perched/curled), give each clear separation, reduce overlap.
- **Regeneration Prompt (positive):** "black and white line art coloring page for
  adults, a sitting cat, a perched round owl, and a perched raven arranged with
  clear space between them, simple correct anatomy, among books candles and potion
  bottles, outlines only no black fill, clean line art, white background, 8.5x11
  portrait"
- **Negative:** "deformed, extra limbs, fused wings, malformed eyes, mutated,
  grayscale, shading, color, solid black fill, text, watermark, signature, frame"

---

## Consistency Guard (the rule behind every regeneration)

A regenerated page must still look like it belongs in *this* book:

- Same **line weight** and coloring-book style as approved pages.
- Same **cozy-witch tone** (never drift dark to "fix" a problem).
- Its **assigned recurring motifs** survive the fix (check the CSV).
- Its **difficulty** still fits its chapter.

If a fix would require breaking consistency, change the *scene*, not the *style*.
