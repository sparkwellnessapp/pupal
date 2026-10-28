"""Build the ground-truth ratification packet for a math teacher (OD-M11).

The agent PRE-FILLS; the teacher RATIFIES. The pre-fill is the modal `latex1` draw per page
(1 page per call, production model). The packet is one self-contained HTML file: each page's
scan beside its pre-filled transcription, typeset and as editable source, with the conventions
in Hebrew at the top. The teacher's corrected source IS the ground truth.

It contains the student's scans, so it is written OUTSIDE the repository.

    python gt_packet.py <raw.json of a latex1 run> <pages_dir> <out.html>
"""
from __future__ import annotations

import base64
import html
import io
import json
import os
import sys
from collections import Counter

from PIL import Image

RAW, PAGES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
raw = json.load(open(RAW, encoding="utf-8"))
names = raw.get("_pages")

RULES_HE = [
    "כל ערך, סימן, חזקה, שבר ושורש — בדיוק כפי שהתלמיד כתב, כולל טעויות. לא מתקנים.",
    "הצורה היא חלק מהתשובה: √e אינו e^½, ו-1/e אינו e^-1.",
    "מתמטיקה בתוך \\( … \\), מילים בעברית מחוץ להן.",
    "שורה כתובה אחת = שורה מתומללת אחת. מערכת עם סוגר מסולסל: \\begin{cases}.",
    "תשובה ממוסגרת: \\boxed{…}. צמצום (אותו איבר מחוק משני הצדדים): \\cancel{…}. עבודה שנמחקה ונזנחה — לא נכתבת.",
    "ספרה שנכתבה מעל ספרה אחרת: הספרה האחרונה שנכתבה. אם לא ניתן להכריע — [?].",
    "שרטוט: שורה אחת [איור N: …] במקומו, והתוויות כפי שהן כתובות על השרטוט.",
]


def modal(texts):
    top, n = Counter(texts).most_common(1)[0]
    return top, n


def img_data(name):
    for ext in (".jpeg", ".jpg", ".png"):
        p = os.path.join(PAGES, name + ext)
        if os.path.exists(p):
            im = Image.open(p).convert("RGB")
            im.thumbnail((1400, 1400))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    raise FileNotFoundError(name)


sections = []
for doc, draws in raw.items():
    if doc.startswith("_"):
        continue
    ok = [d for d in draws if d.get("ok")]
    for i, name in enumerate(names[doc], start=1):
        texts = [d["after_strike"].get(str(i), "") for d in ok]
        text, agree = modal(texts)
        sections.append(f"""
<section class="page" id="{name}">
  <h2>{html.escape(name)} <span class="agree">{agree}/{len(texts)} קריאות זהות</span></h2>
  <div class="cols">
    <img src="{img_data(name)}" alt="{html.escape(name)}">
    <div class="right">
      <div class="rendered" data-src="{html.escape(text, quote=True)}"></div>
      <label>מקור לעריכה (זהו הנוסח שיישמר)</label>
      <textarea data-page="{html.escape(name)}" dir="rtl" spellcheck="false">{html.escape(text)}</textarea>
      <label class="ok"><input type="checkbox" data-ok="{html.escape(name)}"> אישרתי את העמוד שורה אחר שורה</label>
    </div>
  </div>
</section>""")

page = f"""<!doctype html>
<html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>אישור תמלול — מתמטיקה</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<style>
:root {{ --ink:#1b1d22; --muted:#5b616b; --line:#d9dce1; --bg:#fafafa; --card:#fff; --accent:#0f766e; }}
body {{ margin:0; font-family: system-ui, "Segoe UI", Arial, sans-serif; color:var(--ink); background:var(--bg); }}
header {{ padding:20px 16px; max-width:1500px; margin:auto; }}
h1 {{ font-size:22px; margin:0 0 8px; }}
ol {{ line-height:1.7; }}
.page {{ max-width:1500px; margin:16px auto; background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
h2 {{ font-size:16px; margin:0 0 10px; }} .agree {{ color:var(--muted); font-weight:400; font-size:13px; }}
.cols {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
@media (max-width:900px) {{ .cols {{ grid-template-columns:1fr; }} }}
img {{ width:100%; border:1px solid var(--line); border-radius:6px; }}
.rendered {{ line-height:2; padding:8px; border:1px solid var(--line); border-radius:6px; min-height:80px; }}
.rendered bdi {{ unicode-bidi:isolate; }}
textarea {{ width:100%; min-height:260px; font-family:Consolas, monospace; font-size:13px; direction:ltr; text-align:left; box-sizing:border-box; }}
label {{ display:block; margin:10px 0 4px; color:var(--muted); font-size:13px; }} .ok {{ color:var(--accent); font-weight:600; }}
button {{ background:var(--accent); color:#fff; border:0; border-radius:6px; padding:8px 14px; font-size:14px; cursor:pointer; }}
</style></head><body>
<header>
  <h1>אישור תמלול — עבודות מתמטיקה</h1>
  <p>ויוי מילאה מראש את התמלול של כל עמוד. אנא השווי כל שורה מול הסריקה ותקני במקור (התיבה שמתחת לתצוגה). הנוסח המתוקן הוא האמת שלפיה נמדוד את ויוי. כללים:</p>
  <ol>{''.join(f'<li>{html.escape(r)}</li>' for r in RULES_HE)}</ol>
  <p><button id="dl">הורדת כל העמודים המאושרים (JSON)</button></p>
</header>
{''.join(sections)}
<script>
function render(el, src) {{
  el.innerHTML = '';
  for (const line of src.split('\\n')) {{
    const row = document.createElement('div');
    const parts = line.split(/(\\\\\\(.*?\\\\\\))/);
    for (const p of parts) {{
      if (p.startsWith('\\\\(') && p.endsWith('\\\\)')) {{
        const b = document.createElement('bdi'); b.dir = 'ltr';
        try {{ katex.render(p.slice(2, -2), b, {{ throwOnError: true }}); }} catch (e) {{ b.textContent = p; b.style.color = '#b45309'; }}
        row.appendChild(b);
      }} else row.appendChild(document.createTextNode(p));
    }}
    el.appendChild(row);
  }}
}}
window.addEventListener('load', () => {{
  document.querySelectorAll('.page').forEach((sec) => {{
    const r = sec.querySelector('.rendered'), t = sec.querySelector('textarea');
    render(r, t.value);
    t.addEventListener('input', () => render(r, t.value));
  }});
  document.getElementById('dl').onclick = () => {{
    const out = {{}};
    document.querySelectorAll('textarea').forEach((t) => {{
      out[t.dataset.page] = {{ text: t.value, ratified: document.querySelector(`[data-ok="${{t.dataset.page}}"]`).checked }};
    }});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {{ type: 'application/json' }}));
    a.download = 'math_gt_ratified.json'; a.click();
  }};
}});
</script>
</body></html>"""
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(page)
print("wrote", OUT, f"({len(sections)} pages)")
