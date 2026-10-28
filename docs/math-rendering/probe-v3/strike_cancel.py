"""Does the strike check delete a CANCELLATION? (MATH_RENDERING_PLAN §2: a slash through
the same term on both sides is mathematics, not crossed-out work.)

Production's strike-check prompt and model, on the p07 `latex1` transcription (which carries
four `\\cancel{…}`), sequentially, k draws, with a generous timeout — the in-pipeline pass
timed out on this page in 10/10 draws from this machine, so it measured nothing.

    python strike_cancel.py <raw.json from a latex1 run> <pages_dir> [k] [timeout_s]
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env")
from PIL import Image  # noqa: E402

from app.services.transcription.two_phase.pipeline import _encode_pages_sync  # noqa: E402
from app.services.transcription.two_phase.strike_check import (  # noqa: E402
    STRIKE_CHECK_SCHEMA, STRIKE_CHECK_SYSTEM, apply_struck_ranges, strike_check_user_prompt,
)
from app.services.transcription.two_phase_engine import PROD_CONFIG, _MODELS, _make_provider  # noqa: E402

RAW, PAGES = sys.argv[1], sys.argv[2]
K = int(sys.argv[3]) if len(sys.argv) > 3 else 5
TIMEOUT = float(sys.argv[4]) if len(sys.argv) > 4 else 180.0


async def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    text = raw["math4"][0]["after_strike"]["1"]          # math4 p07, a latex1 draw
    key = PROD_CONFIG.p1_strike_check_model_key
    prov = _make_provider(_MODELS[key])
    img = Image.open(os.path.join(PAGES, "math4_p07.jpeg")).convert("RGB")
    b64 = _encode_pages_sync([img], PROD_CONFIG.p1_strike_check_image_max_px or PROD_CONFIG.image_max_px,
                             PROD_CONFIG.image_format, PROD_CONFIG.image_jpeg_quality, False)[0]
    print(f"model={key} cancels in text={text.count(chr(92) + 'cancel')}")
    for i in range(K):
        try:
            r = await prov.complete(system=STRIKE_CHECK_SYSTEM, user=strike_check_user_prompt(1, text),
                                    images_b64=[b64], max_tokens=PROD_CONFIG.p1_strike_check_max_tokens,
                                    temperature=PROD_CONFIG.temperature, json_schema=STRIKE_CHECK_SCHEMA,
                                    timeout_s=TIMEOUT)
            ranges = json.loads(r.text or "{}").get("struck_line_ranges", [])
            _, removed = apply_struck_ranges(text, ranges,
                                             min_block_lines=PROD_CONFIG.p1_strike_check_min_block_lines)
            print(f"draw {i}: {r.total_ms/1000:.0f}s ranges={ranges} removed={len(removed)} "
                  f"cancel_lines_removed={sum(1 for ln in removed if 'cancel' in ln)}")
            for ln in removed:
                print("     removed:", ln[:120])
        except Exception as e:  # noqa: BLE001
            print(f"draw {i}: FAILED {type(e).__name__}: {str(e)[:160]}")


asyncio.run(main())
