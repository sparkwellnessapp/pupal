"""VERIFICATION PROBE v2 — answers the review's objections to probe v1 with evidence.

Probe v1 measured the teacher's KEY, not a student, and called a consistent notation rewrite
(the drawing says 1/e, the spec said e^-1) "exact". This run fixes the instrument:

  * STUDENT pages only (math4 p07 p09 p10 p11 p12, math3 p07 p08).
  * PRODUCTION settings BY CONSTRUCTION: model, reasoning effort, image size and the P1 prompt
    are read from PROD_CONFIG and built by the real `p1_system`, not retyped.
  * k=5 per arm.
  * Notation drift is measured separately from correctness.

E1  EQUATIONS — the real P1 prompt with today's LINEAR math fragment vs a LATEX fragment.
    Measures whether each notation keeps the student's form (√e stays √e, 1/e stays 1/e).
E2  FIGURES — a revised figure prompt ("copy the label from the DRAWING, never from the
    computation"), with a page anchor, an ink-colour tag and a completeness flag per figure.
    Arms: production model at production effort; gemini-3.1-pro; and the v1 prompt on p11,
    which is the page that writes BOTH forms and so catches copying from the computation.
"""
from __future__ import annotations

import asyncio, dataclasses, io, json, os, re, sys, time
from collections import defaultdict
from dotenv import load_dotenv; load_dotenv(".env")
from PIL import Image

OUT = sys.argv[1]
PAGES_DIR = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
K = 5

from app.services.transcription.two_phase.pipeline import _ENCODE_POOL, _encode_pages_sync
from app.services.transcription.two_phase_engine import (
    PROD_CONFIG, _shared_infra, _MODELS, _make_provider,
)
from app.services.transcription.two_phase.pipeline import alias
from app.services.transcription.two_phase.prompts import (
    p1_system, p1_user_prompt, P1_SCHEMA_WITH_INSTRUCTIONS, P1_SCHEMA,
)
from app.services.transcription.two_phase.instrument import cost_usd
from app.subjects import get_profile

MATH = get_profile("mathematics")

# ---------------------------------------------------------------- E1: the LaTeX fragment
# Same five duties as today's fragment; ONLY the notation line changes, plus the two
# conventions the RTL render test forced (Hebrew outside spans) and the as-written rule.
LATEX_FRAGMENT = """\
- Transcribe EXACTLY what the student wrote. Preserve every student error: \
wrong values, wrong signs, wrong steps.
- Crossed-out text is omitted entirely — no strikethrough, no marker of any kind.
- Write every piece of mathematics in LaTeX between \\( and \\), in the student's OWN form: \
√e is \\sqrt{e}, e^½ is e^{1/2}, 1/e is \\frac{1}{e}, e^-1 is e^{-1}. Never rewrite one \
form as another. Never solve, simplify, or correct.
- Hebrew words and units stay OUTSIDE the \\( \\) spans. A system with a brace is \
\\begin{cases} ... \\end{cases}.
- At a drawing or graph, write one line `[איור: <what is drawn, labels verbatim>]` at its position.
- Include the student's handwritten answer content and substantive margin notes or messages.
"""
MATH_LATEX = dataclasses.replace(MATH, p1_fragment=LATEX_FRAGMENT)

E1_PAGES = ["math4_p07", "math4_p09", "math4_p11", "math4_p12", "math3_p08"]

# ---------------------------------------------------------------- E2: the figure prompt v2
FEATURE_KINDS = ["vertical_asymptote", "horizontal_asymptote", "minimum", "maximum",
                 "x_intercept", "y_intercept", "point", "shaded_region",
                 "vertex", "side_label", "angle_label", "segment_label", "right_angle_mark",
                 "axis_label", "other_label"]

FIG_SCHEMA_V2 = {
    "type": "object",
    "properties": {"figures": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["function_sketch", "geometry", "other"]},
            "caption_he": {"type": "string"},
            "box_2d": {"type": "array", "items": {"type": "number"}},
            "completeness": {"type": "string", "enum": ["complete", "partial"]},
            "features": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": FEATURE_KINDS},
                    "as_written": {"type": "string"},
                    "point": {"type": "array", "items": {"type": "number"}},
                    "ink": {"type": "string", "enum": ["primary", "other"]},
                    "uncertain": {"type": "boolean"},
                },
                "required": ["kind", "as_written", "point", "ink", "uncertain"],
            }},
        },
        "required": ["kind", "caption_he", "box_2d", "completeness", "features"],
    }}},
    "required": ["figures"],
}

FIG_SYSTEM_V2 = """\
You read ONE page of a student's handwritten mathematics exam and list the marks on every \
DRAWING (a graph, a sketch, a geometric figure). Equations, text and tables are not drawings.

For each drawing, list what is drawn and labelled ON it:
- `as_written`: copy each label EXACTLY as it is written ON OR BESIDE THE DRAWING, in LaTeX. \
Never take a value from the surrounding computation, even when it is the same number written \
another way: \\sqrt{e} and e^{1/2} are different, \\frac{1}{e} and e^{-1} are different.
- Report a feature only if it is DRAWN: an asymptote only if a line is drawn, an extremum or \
intercept only if it is marked or labelled.
- `point`: [y, x] on a 0-1000 grid of the WHOLE page, at the mark the label belongs to.
- `ink`: "other" when the mark or its label is in a different colour from the student's main \
pen (for example pink or red); otherwise "primary".
- `uncertain`: true when you cannot read the label with confidence.
- `box_2d`: [ymin, xmin, ymax, xmax] of the drawing on the same 0-1000 grid.
- `completeness`: "partial" if part of the drawing could not be read.
- `caption_he`: one Hebrew line naming what is drawn.
If there is no drawing, return an empty list. Output JSON only."""

E2_PAGES = ["math4_p10", "math4_p11", "math4_p12", "math3_p07", "math3_p08"]
E2_PRO_PAGES = ["math4_p10", "math4_p11", "math4_p12"]

# probe v1's prompt, verbatim, for the baseline arm on p11
import ast  # noqa: E402
_v1_src = open(os.path.join(os.path.dirname(__file__), "probe.py"), encoding="utf-8").read()
_v1 = {}
for _node in ast.parse(_v1_src).body:      # take the two constants only; never run probe v1
    if isinstance(_node, ast.Assign) and any(getattr(t, "id", "") in ("FIGURE_SYSTEM", "FIGURE_SCHEMA", "NUM")
                                             for t in _node.targets):
        exec(compile(ast.Module([_node], []), "probe_v1", "exec"), _v1)
FIG_SYSTEM_V1, FIG_SCHEMA_V1 = _v1["FIGURE_SYSTEM"], _v1["FIGURE_SCHEMA"]


def page_path(name: str) -> str:
    for ext in (".jpeg", ".png", ".jpg"):
        p = os.path.join(PAGES_DIR, name + ext)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


async def main():
    providers, aliased, scheduler = _shared_infra()
    p1_key = PROD_CONFIG.p1_model_key
    pro_key = "gemini-3.1-pro-preview"
    if pro_key not in providers:
        providers[pro_key] = _make_provider(_MODELS[pro_key])
        aliased[pro_key] = alias(_MODELS[pro_key])
    from app.services.transcription.scheduler import ProviderLimit, _AdaptiveLimiter
    # the pro provider rides its own scheduler slot (the shared infra registers only the
    # keys this branch's PROD_CONFIG dispatches to)
    name = aliased[pro_key].provider
    if name not in scheduler._limiters:
        scheduler._limiters[name] = _AdaptiveLimiter(ProviderLimit(max_concurrent=5))

    loop = asyncio.get_running_loop()
    enc = {}
    for name in sorted(set(E1_PAGES + E2_PAGES)):
        img = Image.open(page_path(name))
        enc[name] = (await loop.run_in_executor(
            _ENCODE_POOL, _encode_pages_sync, [img], PROD_CONFIG.image_max_px,
            PROD_CONFIG.image_format, PROD_CONFIG.image_jpeg_quality, False))[0]

    cost = defaultdict(float)
    print(f"P1 model={_MODELS[p1_key].model_id} effort={PROD_CONFIG.p1_reasoning_effort} "
          f"table_rows={PROD_CONFIG.p1_table_rows} instructions={PROD_CONFIG.p1_instructions} "
          f"boxed={PROD_CONFIG.p1_boxed_values} max_px={PROD_CONFIG.image_max_px}  k={K}\n")

    async def call(key, system, user, b64, schema, max_tokens, effort, tag):
        prov, ms = providers[key], aliased[key]

        def go():
            return prov.complete(system=system, user=user, images_b64=[b64],
                                 max_tokens=max_tokens, temperature=PROD_CONFIG.temperature,
                                 json_schema=schema, timeout_s=180.0, reasoning_effort=effort)
        t0 = time.monotonic()
        try:
            r = await scheduler.submit(ms.provider, 0, go)
            try:
                cost[tag] += cost_usd(r.response.usage, ms.price)
            except Exception:
                pass
            return {"ok": True, "s": round(time.monotonic() - t0, 1), "data": json.loads(r.response.text or "{}")}
        except Exception as e:
            return {"ok": False, "err": f"{type(e).__name__}: {e}"[:300]}

    jobs = []
    # E1-PROD — the EXACT production P1: origin/main's prompts.py loaded verbatim from git,
    # gemini-3.1-pro, no reasoning effort, main's plain P1_SCHEMA. (This working tree is a WIP
    # branch whose P1 pin — flash@minimal plus three prompt variants — is not deployed.)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "main_prompts", os.path.join(os.path.dirname(__file__), "main_prompts.py"))
    mp = importlib.util.module_from_spec(spec); spec.loader.exec_module(mp)
    for variant, prof in (("prod-linear", MATH), ("prod-latex", MATH_LATEX)):
        system = mp.p1_system(prof)
        user = mp.p1_user_prompt([1], "multi_image")
        for name in E1_PAGES:
            for i in range(K):
                jobs.append(("E1", variant, name, i, call(
                    pro_key, system, user, enc[name], mp.P1_SCHEMA, 5000,
                    None, f"E1-{variant}")))
    # E1-WIP — this branch's pending P1 pin (flash@minimal + its prompt variants)
    for variant, prof in (("wip-linear", MATH), ("wip-latex", MATH_LATEX)):
        system = p1_system(prof, instructions=PROD_CONFIG.p1_instructions,
                           table_rows=PROD_CONFIG.p1_table_rows,
                           boxed_values=PROD_CONFIG.p1_boxed_values)
        schema = P1_SCHEMA_WITH_INSTRUCTIONS if PROD_CONFIG.p1_instructions else P1_SCHEMA
        user = p1_user_prompt([1], PROD_CONFIG.p1_image_packing)
        for name in E1_PAGES:
            for i in range(K):
                jobs.append(("E1", variant, name, i, call(
                    p1_key, system, user, enc[name], schema, PROD_CONFIG.p1_max_tokens,
                    PROD_CONFIG.p1_reasoning_effort, f"E1-{variant}")))
    # E2 — figures v2 on production model + pro, and the v1 baseline on p11
    for name in E2_PAGES:
        for i in range(K):
            jobs.append(("E2", "v2-flash", name, i, call(
                p1_key, FIG_SYSTEM_V2, "List every drawing on this page.", enc[name],
                FIG_SCHEMA_V2, 6000, PROD_CONFIG.p1_reasoning_effort, "E2-v2-flash")))
    for name in E2_PRO_PAGES:
        for i in range(K):
            jobs.append(("E2", "v2-pro", name, i, call(
                pro_key, FIG_SYSTEM_V2, "List every drawing on this page.", enc[name],
                FIG_SCHEMA_V2, 6000, None, "E2-v2-pro")))
    for i in range(K):
        jobs.append(("E2", "v1-flash", "math4_p11", i, call(
            p1_key, FIG_SYSTEM_V1, "Describe every drawn figure on this page.", enc["math4_p11"],
            FIG_SCHEMA_V1, 4000, PROD_CONFIG.p1_reasoning_effort, "E2-v1-flash")))

    t0 = time.monotonic()
    results = await asyncio.gather(*(j[4] for j in jobs))
    print(f"{len(jobs)} calls in {time.monotonic()-t0:.0f}s\n")

    store = defaultdict(list)
    for (exp, variant, name, i, _), r in zip(jobs, results):
        store[f"{exp}|{variant}|{name}"].append(r)
    json.dump(store, open(os.path.join(OUT, "raw.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump({k: round(v, 4) for k, v in cost.items()} | {"total": round(sum(cost.values()), 4)},
              open(os.path.join(OUT, "cost.json"), "w"), indent=1)
    fails = sum(1 for r in results if not r["ok"])
    print("failed calls:", fails)
    for (exp, variant, name, i, _), r in zip(jobs, results):
        if not r["ok"]:
            print("  FAIL", exp, variant, name, i, r["err"][:160])
    print("cost:", json.dumps({k: round(v, 3) for k, v in cost.items()}), "total", round(sum(cost.values()), 3))

asyncio.run(main())
