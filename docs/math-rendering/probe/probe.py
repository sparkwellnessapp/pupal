"""FEASIBILITY PROBE — can the production P1 model emit a FAITHFUL and CONSISTENT
structured figure spec from a real handwritten page?

This is the one assumption the whole math-figure plan rests on. It is tested before the
plan is written, on the owner's real documents, at k=3, with the production provider and
the production model.

Measured: (1) does every draw parse against the schema; (2) are the SEMANTIC FACTS stable
across draws (asymptote, extremum, intercepts, labelled sides) — because an unstable spec
renders a different picture every time the teacher opens the page.
"""
from __future__ import annotations

import asyncio, json, os, sys, time
from collections import Counter
from dotenv import load_dotenv; load_dotenv(".env")
from PIL import Image

OUT = sys.argv[1]
PAGES = sys.argv[2:]
os.makedirs(OUT, exist_ok=True)

from app.services.transcription.two_phase.pipeline import _ENCODE_POOL, _encode_pages_sync
from app.services.transcription.two_phase_engine import PROD_CONFIG, _shared_infra
from app.services.transcription.two_phase.instrument import cost_usd

K = 3

# --------------------------------------------------------------------------------------
# The candidate IR, as a provider JSON schema. Deliberately NARROW: the figure kinds that
# actually occur in these two exams, nothing speculative. A sketch is QUALITATIVE — the
# student did not plot the function, she drew its shape and marked its features — so the
# curve is described by its FEATURES, never by sampled coordinates.
# --------------------------------------------------------------------------------------
NUM = {"type": "string"}          # exact as written: "e^4", "-e/2", "sqrt(e)", "2", "1/e"

FIGURE_SCHEMA = {
    "type": "object",
    "properties": {
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string",
                             "enum": ["function_plot", "plane_geometry", "solid_sketch",
                                      "number_line", "other"]},
                    "caption_he": {"type": "string"},
                    "axes": {
                        "type": "object",
                        "properties": {
                            "x_label": {"type": "string"},
                            "y_label": {"type": "string"},
                        },
                        "required": ["x_label", "y_label"],
                    },
                    "curves": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "vertical_asymptotes": {"type": "array", "items": NUM},
                                "horizontal_asymptotes": {"type": "array", "items": NUM},
                                "points": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "x": NUM, "y": NUM,
                                            "role": {"type": "string",
                                                     "enum": ["minimum", "maximum", "x_intercept",
                                                              "y_intercept", "inflection", "marked"]},
                                            "label": {"type": "string"},
                                        },
                                        "required": ["x", "y", "role", "label"],
                                    },
                                },
                                "trend": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "from_x": NUM, "to_x": NUM,
                                            "direction": {"type": "string",
                                                          "enum": ["increasing", "decreasing"]},
                                        },
                                        "required": ["from_x", "to_x", "direction"],
                                    },
                                },
                            },
                            "required": ["label", "vertical_asymptotes", "horizontal_asymptotes",
                                         "points", "trend"],
                        },
                    },
                    "shaded": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"from_x": NUM, "to_x": NUM, "label": {"type": "string"}},
                            "required": ["from_x", "to_x", "label"],
                        },
                    },
                    "shapes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "shape": {"type": "string",
                                          "enum": ["rectangle", "triangle", "circle", "polygon",
                                                   "segment", "vector", "other"]},
                                "vertex_labels": {"type": "array", "items": {"type": "string"}},
                                "side_labels": {"type": "array", "items": {"type": "string"}},
                                "marks": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["shape", "vertex_labels", "side_labels", "marks"],
                        },
                    },
                },
                "required": ["kind", "caption_he"],
            },
        },
    },
    "required": ["figures"],
}

FIGURE_SYSTEM = """\
You read ONE page of a student's handwritten mathematics exam and describe every DRAWN \
FIGURE on it as structured data. Text, equations and tables are NOT figures — skip them.

A hand-drawn graph is a SKETCH, not a plot: the student drew the shape and marked the \
features that matter. Describe exactly those features and never invent coordinates she \
did not mark.

Rules:
- Record every number EXACTLY as written, as a string: `e^4`, `-e/2`, `sqrt(e)`, `1/e`, `2`.
  Never evaluate, round, or convert.
- `vertical_asymptotes` / `horizontal_asymptotes`: only lines she actually drew (usually dashed).
- `points`: only points she MARKED or labelled — extrema, intercepts. Use her own label text.
- `trend`: the intervals where the curve rises or falls, if her sketch makes that clear.
- `shaded`: a hatched or shaded region under or between curves, with its bounds.
- `shapes`: for plane or solid geometry — the shape, its vertex letters, and its side labels
  exactly as written (`a=4.8`, `b=3.6`, `6 ס"מ`).
- `caption_he`: ONE Hebrew line naming what is drawn, as a fallback for a reader that
  cannot render the figure.
- If the page has no drawn figure, return an empty list.
Output JSON only."""


async def main():
    providers, aliased, scheduler = _shared_infra()
    key = PROD_CONFIG.p1_model_key
    provider, ms = providers[key], aliased[key]
    loop = asyncio.get_running_loop()
    print(f"model={ms.model_id} k={K} pages={[os.path.basename(p) for p in PAGES]}\n")
    total_cost = 0.0
    report = {}

    for path in PAGES:
        name = os.path.basename(path)
        img = Image.open(path)
        b64 = (await loop.run_in_executor(
            _ENCODE_POOL, _encode_pages_sync, [img], PROD_CONFIG.image_max_px,
            PROD_CONFIG.image_format, PROD_CONFIG.image_jpeg_quality, False))[0]

        draws = []
        for i in range(K):
            def call():
                return provider.complete(
                    system=FIGURE_SYSTEM,
                    user="Describe every drawn figure on this page.",
                    images_b64=[b64], max_tokens=4000, temperature=0.0,
                    json_schema=FIGURE_SCHEMA, timeout_s=120.0,
                )
            t0 = time.monotonic()
            try:
                res = await scheduler.submit(ms.provider, 0, call)
                raw = res.response.text or ""
                try:
                    total_cost += cost_usd(res.response.usage, ms.price)
                except Exception:
                    pass
                data = json.loads(raw)
                draws.append({"ok": True, "s": round(time.monotonic() - t0, 1), "data": data})
            except Exception as e:
                draws.append({"ok": False, "err": f"{type(e).__name__}: {e}"[:200]})
        report[name] = draws
        json.dump(draws, open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

        # ---- consistency: the semantic facts, as a multiset per draw ----
        print(f"=== {name} ===")
        sigs = []
        for d in draws:
            if not d["ok"]:
                print("   DRAW FAILED:", d["err"]); sigs.append(None); continue
            figs = d["data"].get("figures", [])
            facts = []
            for f in figs:
                facts.append(("kind", f.get("kind")))
                for c in f.get("curves") or []:
                    for a in c.get("vertical_asymptotes") or []: facts.append(("vasym", a))
                    for a in c.get("horizontal_asymptotes") or []: facts.append(("hasym", a))
                    for p in c.get("points") or []: facts.append(("pt", p.get("role"), p.get("x"), p.get("y")))
                for s in f.get("shaded") or []: facts.append(("shade", s.get("from_x"), s.get("to_x")))
                for s in f.get("shapes") or []:
                    facts.append(("shape", s.get("shape"), tuple(s.get("side_labels") or [])))
            sigs.append(Counter(facts))
            print(f"   draw {len(sigs)}: {len(figs)} figure(s), {len(facts)} facts, {d['s']}s")
        good = [s for s in sigs if s is not None]
        if len(good) >= 2:
            common = set.intersection(*[set(s) for s in good])
            union = set.union(*[set(s) for s in good])
            print(f"   STABLE facts (in every draw): {len(common)}/{len(union)}"
                  f"  ->  {100*len(common)/max(1,len(union)):.0f}% agreement")
            for f in sorted(common, key=str)[:14]:
                print("      =", f)
            unstable = sorted(union - common, key=str)
            if unstable:
                print(f"   UNSTABLE ({len(unstable)}):")
                for f in unstable[:10]:
                    print("      ~", f)
        print()

    print(f"TOTAL COST ${total_cost:.4f}")
    json.dump({"cost_usd": round(total_cost, 4)},
              open(os.path.join(OUT, "_cost.json"), "w"), indent=1)

asyncio.run(main())
