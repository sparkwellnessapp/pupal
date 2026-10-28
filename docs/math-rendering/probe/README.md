# Feasibility evidence for `../../MATH_RENDERING_PLAN.md`

Measured 2026-10-28, before the plan was written, on the owner's real documents.

## What was run

`probe.py` — three pages of handwritten marking scheme through the PRODUCTION transcription
model and provider (`gemini-3.5-flash`, the shared scheduler), k=3, asking for a structured
figure description against a candidate schema.

| page | what is drawn on it |
|---|---|
| `math4_p15` | two function sketches: vertical asymptote, minimum, y-intercept |
| `math4_p16` | an f(x) sketch, its derivative, and a shaded area |
| `math3_p07` | two rectangles with labelled sides |

## Result

**9 of 9 draws valid. 100% agreement across draws on all three pages.** $0.1134 total,
8–22 s per page. Facts captured exactly as written and never evaluated: `x=2`, `(3, e^4)`,
`(0, -e/2)`, `e^-1`, `e^2`, `(e^(1/2), -2.25)`, the shaded span `e^(1/2)`→`e^2`, and
`a = 3.6 מ'` / `b = 4.8 מ'`.

The raw draws are the `*.jpeg.json` files — three draws per page, as returned.

## The renderer prototype

`render_proto.py` draws a spec back as SVG using rank-based (not to-scale) placement, which
is the plan's §4.

* `rendered_fig1_GOOD.png` — the f(x) sketch: a U-curve crossing the axis twice with its
  minimum labelled. Recognisably the student's drawing. Label collisions visible, and noted
  as risk 3 in the plan.
* `rendered_fig3_UNDERDETERMINED.png` — **the useful failure.** The spec gave two points both
  on the x-axis and no shape, so the renderer drew a flat line and shaded a box. That is not
  what the student drew. This is why the plan mandates a drawability gate (§5d): a spec that
  does not determine a shape must draw NOTHING and fall back to the caption.

Both scripts are throwaway research code, not production: `read_value` uses `eval` behind a
character allowlist, which a real implementation must replace with a parser.
