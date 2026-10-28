"""Score probe v3 (the `latex1` variant through production's perception path).

    python analyze3.py <out_dir> <frontend_dir>

Every measure here is DETERMINISTIC over the raw output; none of them is correctness against
ground truth (that waits for the teacher-ratified files, OD-M11). What it can say:

  * renderability  — every span parsed by the renderer's own parser (KaTeX, the frontend's pin)
  * conventions    — the validator's findings; forbidden environments; Hebrew in spans
  * notation       — on math4 p11 the student writes BOTH forms of two values (√e and e^½,
                     1/e and e^-1); a draw that changes either count rewrote his notation
  * cancellations  — `\\cancel` emitted, and whether the strike check deleted any line that
                     carries one (plan §2: a cancellation is mathematics)
  * figures        — numbered `[איור N:` lines per page
  * stability      — identical page text across draws
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
from app.services.math_notation import check_math_answer, split_math  # noqa: E402

OUT, WEB = sys.argv[1], sys.argv[2]
raw = json.load(open(os.path.join(OUT, "raw.json"), encoding="utf-8"))
HEB = re.compile(r"[\u0590-\u05FF]")
NAMES = {"math4": [f"math4_p{n:02d}" for n in range(7, 13)],
         "math3": [f"math3_p{n:02d}" for n in range(7, 11)]}

FORMS = {
    "sqrt_e": [r"\\sqrt\s*\{\s*e\s*\}", r"\\sqrt\s+e\b"],
    "e_half": [r"e\s*\^\s*\{\s*1\s*/\s*2\s*\}", r"e\s*\^\s*\{\s*\\[dt]?frac\s*\{?1\}?\s*\{?2\}?\s*\}"],
    "one_over_e": [r"\\[dt]?frac\s*\{\s*1\s*\}\s*\{\s*e\s*\}"],
    "e_minus1": [r"e\s*\^\s*\{\s*-\s*1\s*\}"],
}
INK_P11 = {"sqrt_e": 8, "e_half": 1, "one_over_e": 3, "e_minus1": 1}   # probe-v2 draft key, unratified


def count(text, form):
    return sum(len(re.findall(p, text)) for p in FORMS[form])


def spans(text):
    res = split_math(text)
    return [text[s.body_start:s.body_end] for s in res.segments if s.kind == "math"]


lines_out = []
P = lines_out.append
all_spans = []
cost_total = 0.0
NAMES = raw.get("_pages", NAMES)
for doc, draws in raw.items():
    if doc.startswith("_"):
        continue
    ok = [d for d in draws if d.get("ok")]
    P(f"=== {doc}: {len(ok)}/{len(draws)} draws ok")
    for d in draws:
        if not d.get("ok"):
            P(f"   FAILED: {d.get('err')}")
    for d in ok:
        cost_total += sum(c.get("cost_usd", 0) for c in d.get("calls", []) if isinstance(c, dict))
    for i, name in enumerate(NAMES[doc], start=1):
        texts = [d["after_strike"].get(str(i), "") for d in ok]
        p1s = [d["p1"].get(str(i), "") for d in ok]
        sp = [s for t in texts for s in spans(t)]
        all_spans += [(doc, name, s) for s in sp]
        issues = Counter(iss.code for t in texts for iss in check_math_answer(t))
        heb = sum(1 for s in sp if HEB.search(s))
        cancels = [t.count("\\cancel") for t in texts]
        boxed = [t.count("\\boxed") for t in texts]
        figs = [re.findall(r"\[איור\s*(\d+)\s*:", t) for t in texts]
        cases = [t.count("\\begin{cases}") for t in texts]
        # strike-check deletions: lines in P1 that are gone after the pass
        deleted = []
        for a, b in zip(p1s, texts):
            gone = [ln for ln in a.splitlines() if ln.strip() and ln not in b.splitlines()]
            deleted.append(gone)
        P(f"--- {name}  spans/draw={[len(spans(t)) for t in texts]}  issues={dict(issues)}  "
          f"heb_in_span={heb}  cases={cases}  cancel={cancels}  boxed={boxed}  figs={figs}")
        P(f"    stable text: {Counter(texts).most_common(1)[0][1]}/{len(texts)}"
          f"   strike-deleted lines/draw: {[len(g) for g in deleted]}")
        for g in deleted:
            for ln in g:
                tag = "  <-- CANCEL" if "\\cancel" in ln else ("  <-- math" if "\\(" in ln else "")
                P(f"      deleted: {ln[:110]}{tag}")
        if name == "math4_p07":
            # The ink beside d = -10 reads «התשלום החודשי קטן ב-10 ש"ח» (probe v2: 10/10 draws
            # of production pro, one page per call, read exactly that).
            after = [re.search(r"d\s*=\s*-\s*10(?:\\\))?\s*(.{0,45})", t) for t in texts]
            P("    after d=-10: " + " | ".join((m.group(1).strip() if m else "?") for m in after))
            P(f"    faithful «התשלום החודשי»: {sum('התשלום החודשי' in t for t in texts)}/{len(texts)}")
        if name == "math4_p09":
            # The student writes lower-case p (probe v2: 10/10 lower-case).
            P(f"    title: {[t.splitlines()[0][:28] if t else '' for t in texts]}")
            P(f"    (p, P) counts: {[(len(re.findall(r'(?<![A-Za-z])p(?![A-Za-z])', t)), len(re.findall(r'(?<![A-Za-z])P(?![A-Za-z])', t))) for t in texts]}")
        if name == "math4_p11":
            for form, truth in INK_P11.items():
                P(f"    {form}: {[count(t, form) for t in texts]}  [ink {truth}]")

# KaTeX parse with the frontend's own pinned KaTeX
payload = [s for _, _, s in all_spans]
js = r"""
const katex=require('katex'); const xs=JSON.parse(require('fs').readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(xs.map(s=>{try{katex.renderToString(s,{throwOnError:true,strict:'ignore'});return null}catch(e){return String(e.message).slice(0,100)}})));"""
r = subprocess.run(["node", "-e", js], input=json.dumps(payload), capture_output=True, text=True,
                   cwd=WEB, encoding="utf-8")
errs = json.loads(r.stdout or "[]")
fails = [(d, n, s, e) for (d, n, s), e in zip(all_spans, errs) if e]
P(f"\nKaTeX {json.loads(subprocess.run(['node','-e','process.stdout.write(JSON.stringify(require(\"katex/package.json\").version))'], capture_output=True, text=True, cwd=WEB).stdout)}: "
  f"{len(all_spans) - len(fails)}/{len(all_spans)} spans parse")
for d, n, s, e in fails[:15]:
    P(f"   FAIL {n}: {s[:70]!r} -> {e}")
P(f"\nspend: ${cost_total:.3f}")
text = "\n".join(lines_out)
print(text)
open(os.path.join(OUT, "scores.txt"), "w", encoding="utf-8").write(text + "\n")
