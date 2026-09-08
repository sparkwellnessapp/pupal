"""Render-only, real provider: the 4-unit Math DOCX through rubric-read/rr1.0 (the exact
product stage), saved so (a) P-14 weight fidelity can be measured page by page and (b) the
extraction re-run reuses THIS output byte-identically instead of paying for the read twice."""
import asyncio, json, os, sys, time, logging
from dotenv import load_dotenv; load_dotenv(".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
from app.services.docx_v3.image_render import render_source
SRC = "tests/rubric_eval_suite/fixtures/Math_rubrics/4 יחל מבחן ומחוון.docx"
async def main():
    data = open(SRC, "rb").read()
    t0 = time.time()
    rendered, report = await render_source(data, os.path.basename(SRC), deadline_s=None)
    wall = time.time() - t0
    open(os.path.join(OUT, "render.md"), "w", encoding="utf-8").write(rendered)
    rep = report.as_dict(); rep["wall_s"] = round(wall, 1); rep["chars"] = len(rendered)
    json.dump(rep, open(os.path.join(OUT, "render_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(rep, ensure_ascii=False, default=str))
asyncio.run(main())
