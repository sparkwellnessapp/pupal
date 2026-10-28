"""Probe v3 — the `latex1` P1 variant, run through PRODUCTION's perception path.

Not a re-implementation: this calls `Pipeline.perceive`'s two halves exactly as production
does — `_transcribe_pages` (P1, PROD_CONFIG: gemini-3.1-pro, 3 pages per call) then
`_strike_check_pages` (the crossed-out-ink pass) — with `subject_key="mathematics"` and
`p1_variant="latex1"`. Both halves are recorded, so a line the strike check deletes is
visible (plan §2: a cancellation slash is mathematics, not crossed-out work).

    python probe3.py <out_dir> <pages_dir> [k]

Student pages only (math4 p07–p12, math3 p07–p10), k draws per document.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
import time
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(".env")
from PIL import Image  # noqa: E402

from app.services.transcription.budget import Budget  # noqa: E402
from app.services.transcription.two_phase.instrument import Trace  # noqa: E402
from app.services.transcription.two_phase_engine import PROD_CONFIG, _build_pipeline_multi  # noqa: E402

OUT, PAGES = sys.argv[1], sys.argv[2]
K = int(sys.argv[3]) if len(sys.argv) > 3 else 5
DOCS = {
    "math4": [f"math4_p{n:02d}" for n in range(7, 13)],
    "math3": [f"math3_p{n:02d}" for n in range(7, 11)],
}
# One variable per arm (CLAUDE.md §17.3): PROBE_VARIANT ("" = the live linear fragment),
# PROBE_PAGES_PER_CALL (production packs 3), PROBE_STRIKE ("0" skips the strike check),
# PROBE_DOCS (comma list).
CFG = dataclasses.replace(
    PROD_CONFIG, subject_key="mathematics",
    p1_variant=os.environ.get("PROBE_VARIANT", "latex1"),
    p1_pages_per_call=int(os.environ.get("PROBE_PAGES_PER_CALL", PROD_CONFIG.p1_pages_per_call)))
STRIKE = os.environ.get("PROBE_STRIKE", "1") == "1"
if os.environ.get("PROBE_PAGES"):        # e.g. "math4_p07" — restrict pages within the docs
    keep = set(os.environ["PROBE_PAGES"].split(","))
    DOCS = {k: [p for p in v if p in keep] for k, v in DOCS.items()}
    DOCS = {k: v for k, v in DOCS.items() if v}
if os.environ.get("PROBE_DOCS"):
    DOCS = {k: v for k, v in DOCS.items() if k in os.environ["PROBE_DOCS"].split(",")}


def page_path(name: str) -> str:
    for ext in (".jpeg", ".png", ".jpg"):
        p = os.path.join(PAGES, name + ext)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


async def one(doc: str, draw: int) -> dict:
    images = [Image.open(page_path(n)).convert("RGB") for n in DOCS[doc]]
    pipeline = _build_pipeline_multi(CFG, Budget(None))
    trace = Trace(doc_id=f"{doc}-d{draw}")
    t0 = time.monotonic()
    try:
        p1 = await pipeline._transcribe_pages(images, trace.doc_id, draw, trace)
        struck = (await pipeline._strike_check_pages(images, dict(p1), trace.doc_id, draw, trace)
                  if STRIKE else dict(p1))
        return {"ok": True, "s": round(time.monotonic() - t0, 1),
                "p1": {str(k): v for k, v in p1.items()},
                "after_strike": {str(k): v for k, v in struck.items()},
                "calls": [dataclasses.asdict(c) if dataclasses.is_dataclass(c) else str(c)
                          for c in getattr(trace, "calls", [])]}
    except Exception as e:  # noqa: BLE001 — a failed draw is data
        return {"ok": False, "err": f"{type(e).__name__}: {e}"[:400]}


async def main():
    os.makedirs(OUT, exist_ok=True)
    print(f"P1 model={CFG.p1_model_key} variant={CFG.p1_variant} pages/call={CFG.p1_pages_per_call} "
          f"strike={CFG.p1_strike_check_model_key} k={K}", flush=True)
    jobs = [(doc, i) for doc in DOCS for i in range(K)]
    results = await asyncio.gather(*(one(d, i) for d, i in jobs))
    raw = defaultdict(list)
    for (doc, _), r in zip(jobs, results):
        raw[doc].append(r)
    raw["_pages"] = DOCS
    raw["_config"] = {"variant": CFG.p1_variant, "pages_per_call_config": CFG.p1_pages_per_call,
                      "strike": STRIKE, "model": CFG.p1_model_key}
    with open(os.path.join(OUT, "raw.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)
    for doc, rs in raw.items():
        if doc.startswith("_"):
            continue
        print(doc, [("ok" if r["ok"] else r["err"][:80]) for r in rs], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
