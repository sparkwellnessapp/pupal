# Evidence for plan v2 (`../../MATH_RENDERING_PLAN.md`)

Measured 2026-10-28, after the review, to answer its objections to probe v1. Spend: $1.45.

## What was run

`probe2.py`, 145 calls, k=5 per arm, **student pages only**.

| arm | what it is |
|---|---|
| `E1 prod-linear` | **production's exact P1**: `origin/main`'s `prompts.py` loaded verbatim from git, `gemini-3.1-pro-preview`, today's linear math fragment |
| `E1 prod-latex` | the same, with the LaTeX fragment in `probe2.py` |
| `E1 wip-linear` / `wip-latex` | the pending flash pin on the WIP branch (`gemini-3.5-flash` @ minimal, plus its three prompt variants) |
| `E2 v2-flash` / `v2-pro` | the revised figure prompt: labels copied from the drawing, `[y, x]` anchors, ink colour, completeness |
| `E2 v1-flash` | probe v1's figure prompt on p11, as a baseline |

Two calls failed on rate limits (`wip-linear`, p07). `raw.json` holds every draw as returned.
`scores.txt` is `analyze2.py`'s output.

## How to read `scores.txt`

**The matcher is cruder than the model.** Three `found 0/5` rows are matcher failures, checked
by hand:

* `-e/2` and `(0,13-e/2)`: the model wrote `-\frac{e}{2}`, which is correct.
* `√e..e^2`: the hatched area carries no label; the key's string was invented by the agent.
* v1's `(√e,-2.25)`: the old prompt wrote `(sqrt(e),-2.25)`, which keeps the student's form.

**The draft key is unratified and partly wrong.** `draft_key.json` was authored by the agent
from the ink. Its p12 count of `√e` (4) was wrong; every arm found 7 or 8, and the arms are
right. That is why the plan requires a math teacher to ratify ground truth.

## The one real figure miss

On p10 the second sketch, g(x), has its own pink dashed asymptote with no label. Both models
missed it in all 10 draws, and both reported that figure as `complete`.

## Overlays

`overlay_v2-pro_math4_p10.jpg` and `overlay_v2-flash_math4_p11.jpg` draw each feature's anchor
on the ink with its `as_written` text, and each figure's box. Anchors land on or beside the
label they name, within one or two grid squares.

## Render test (`../render-test/`)

`build.cjs` renders the student's own lines in an RTL Hebrew page five ways; `shot.cjs`
screenshots it in the frontend's Playwright Chromium (`rtl_test.png`). `mathlive_test.html`
tests MathLive over HTTP and an edit round-trip (`mathlive_test.png`). Libraries were installed
in the session scratchpad: KaTeX 0.19.1, Temml 0.14.0, MathLive 0.111.1.
