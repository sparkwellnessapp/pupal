"""Score probe v2. Notation DRIFT is counted separately from correctness (review §1): a
value that is equal but written in another form (√e -> e^{1/2}) is a defect of its own."""
import json, os, re, subprocess, sys
from collections import Counter, defaultdict

OUT = sys.argv[1]
KEY = json.load(open(sys.argv[2], encoding="utf-8"))
WEB = sys.argv[3]                       # node workspace with katex installed
raw = json.load(open(os.path.join(OUT, "raw.json"), encoding="utf-8"))

HEB = re.compile(r"[\u0590-\u05FF]")


def page_text(d):
    pages = (d.get("data") or {}).get("pages") or []
    return "\n".join(p.get("text", "") for p in pages)


# ------------------------------------------------------------------ E1 — equations
# Ink counts read off the student's p11 and p12 (agent draft, unratified):
#   p11: √e x8 (incl. the graph label), e^½ x1, 1/e x3 (incl. graph label + boxed), e^-1 x1
#   p12: √e x4, e^½ x0
FORMS = {
    "sqrt_e":     [r"\\sqrt\s*\{\s*e\s*\}", r"\\sqrt\s+e\b", r"sqrt\(\s*e\s*\)", r"√\s*e"],
    "e_half":     [r"e\s*\^\s*\{\s*1\s*/\s*2\s*\}", r"e\s*\^\s*\{\s*\\[dt]?frac\s*\{?1\}?\s*\{?2\}?\s*\}",
                   r"e\s*\^\s*\(\s*1\s*/\s*2\s*\)", r"e\s*\^\s*1/2", r"e\s*\^\s*½", r"e½"],
    "one_over_e": [r"\\[dt]?frac\s*\{\s*1\s*\}\s*\{\s*e\s*\}", r"(?<![\^\w])1\s*/\s*e\b", r"\(1\)/\(e\)"],
    "e_minus1":   [r"e\s*\^\s*\{\s*-\s*1\s*\}", r"e\s*\^\s*\(\s*-\s*1\s*\)", r"e\s*\^\s*-\s*1"],
}
INK = {"math4_p11": {"sqrt_e": 8, "e_half": 1, "one_over_e": 3, "e_minus1": 1},
       "math4_p12": {"sqrt_e": 4, "e_half": 0}}


def count(text, form):
    return sum(len(re.findall(p, text)) for p in FORMS[form])


def spans(text):
    return re.findall(r"\\\((.+?)\\\)", text, flags=re.S)


print("=" * 100)
print("E1  EQUATIONS — form counts per draw (ink truth in brackets).  drift = form changed")
print("=" * 100)
all_spans = []
for arm in ("prod-linear", "prod-latex", "wip-linear", "wip-latex"):
    for page in ("math4_p11", "math4_p12", "math4_p07", "math4_p09", "math3_p08"):
        draws = raw.get(f"E1|{arm}|{page}", [])
        ok = [d for d in draws if d.get("ok")]
        line = f"{arm:12s} {page:10s} ok={len(ok)}/{len(draws)} "
        if page in INK:
            parts = []
            for form, truth in INK[page].items():
                vals = [count(page_text(d), form) for d in ok]
                parts.append(f"{form}={vals}[{truth}]")
            line += " ".join(parts)
        if page == "math4_p07":
            line += " cases=" + str([int(bool(re.search(r"\\begin\{cases\}|\\left\\\{|^\s*\{", page_text(d), re.M))) for d in ok])
        if page == "math4_p09":
            line += " log_base=" + str([int(bool(re.search(r"\\log_\{|log_\{|log_\(|\\log_", page_text(d)))) for d in ok])
        if page == "math3_p08":
            line += " 23.25=" + str([int("23.25" in page_text(d)) for d in ok]) + " 23.259=" + str([int("23.259" in page_text(d)) for d in ok])
        if "latex" in arm:
            sp = [s for d in ok for s in spans(page_text(d))]
            heb = sum(1 for s in sp if HEB.search(s))
            dollars = sum(page_text(d).count("$") for d in ok)
            boxed_br = sum(len(re.findall(r"\[\s*\\\(|\\\)\s*\]", page_text(d))) for d in ok)
            line += f" | spans={len(sp)} heb_in_span={heb} dollars={dollars} bracket_box={boxed_br}"
            all_spans += [(arm, page, s) for s in sp]
        print(line)
    print()

# KaTeX parse check, with the renderer's own parser
if all_spans:
    payload = [s for _, _, s in all_spans]
    js = r"""
const katex=require('katex'); const xs=JSON.parse(require('fs').readFileSync(0,'utf8'));
const out=xs.map(s=>{try{katex.renderToString(s,{throwOnError:true,strict:'ignore'});return null}catch(e){return String(e.message).slice(0,90)}});
process.stdout.write(JSON.stringify(out));"""
    r = subprocess.run(["node", "-e", js], input=json.dumps(payload), capture_output=True,
                       text=True, cwd=WEB, encoding="utf-8")
    errs = json.loads(r.stdout or "[]")
    by_arm = defaultdict(lambda: [0, 0])
    examples = []
    for (arm, page, s), e in zip(all_spans, errs):
        by_arm[arm][0] += 1
        if e:
            by_arm[arm][1] += 1
            if len(examples) < 8:
                examples.append((arm, page, s[:70], e))
    print("KaTeX parse:", {a: f"{v[1]} fail / {v[0]} spans" for a, v in by_arm.items()})
    for ex in examples:
        print("   FAIL", ex)
print()

# ------------------------------------------------------------------ E2 — figures
def norm(s):
    s = s or ""
    s = s.replace("\\left", "").replace("\\right", "").replace("\\,", "").replace("\\!", "")
    s = re.sub(r"\\[dt]frac", r"\\frac", s)
    s = re.sub(r"\\sqrt\s*\{\s*e\s*\}", "√e", s)
    s = re.sub(r"\\frac\s*\{\s*1\s*\}\s*\{\s*e\s*\}", "1/e", s)
    s = re.sub(r"\\frac\s*\{\s*-?\s*e\s*\}\s*\{\s*2\s*\}", lambda m: m.group(0), s)
    s = re.sub(r"e\s*\^\s*\{\s*-\s*1\s*\}|e\s*\^\s*\(-1\)", "e^-1", s)
    s = re.sub(r"e\s*\^\s*\{\s*(1\s*/\s*2|\\frac\{1\}\{2\})\s*\}|e\s*\^\s*\(1/2\)|e\^½", "e^(1/2)", s)
    s = re.sub(r"\^\{(\w)\}", r"^\1", s)
    s = re.sub(r"\s+", "", s)
    return s


EQUIV = {"√e": "e^(1/2)", "e^(1/2)": "√e", "1/e": "e^-1", "e^-1": "1/e"}


def key_norm(s):
    return re.sub(r"\s+", "", s or "")


print("=" * 100)
print("E2  FIGURES — per key feature: found-as-written / drifted-form / missing, over 5 draws")
print("=" * 100)
for arm in ("v1-flash", "v2-flash", "v2-pro"):
    for page, spec in KEY["pages"].items():
        draws = raw.get(f"E2|{arm}|{page}", [])
        if not draws:
            continue
        ok = [d for d in draws if d.get("ok")]
        print(f"--- {arm} {page}  ok={len(ok)}/{len(draws)}")
        for fig in spec["figures"]:
            for kf in fig["features"]:
                want = kf.get("as_written")
                if not want:
                    continue
                w = key_norm(want)
                found = drift = 0
                for d in ok:
                    feats = []
                    for f in (d["data"].get("figures") or []):
                        feats += f.get("features") or []
                        for c in f.get("curves") or []:            # v1 schema
                            for p in c.get("points") or []:
                                feats.append({"as_written": p.get("label") or f'({p.get("x")},{p.get("y")})'})
                            for a in c.get("vertical_asymptotes") or []:
                                feats.append({"as_written": f"x={a}"})
                        for s in f.get("shapes") or []:
                            for lab in s.get("side_labels") or []:
                                feats.append({"as_written": lab})
                    texts = [norm(f.get("as_written")) for f in feats]
                    if any(w in t or t == w for t in texts):
                        found += 1
                    else:
                        alt = None
                        for a, b in EQUIV.items():
                            if a in w:
                                alt = w.replace(a, b)
                        if alt and any(alt in t for t in texts):
                            drift += 1
                print(f"     {want:22s} found {found}/{len(ok)}  drifted {drift}/{len(ok)}"
                      + (f"   <- trap: {kf['trap']}" if kf.get("trap") else ""))
        # ink tag for the pink asymptote
        if page == "math4_p10" and arm != "v1-flash":
            tags = []
            for d in ok:
                inks = [f.get("ink") for fig in (d["data"].get("figures") or []) for f in (fig.get("features") or [])
                        if f.get("kind") == "vertical_asymptote"]
                tags.append(inks)
            print(f"     vertical asymptote ink tags per draw: {tags}")
        # stability: identical feature signature across draws
        sigs = []
        for d in ok:
            sig = tuple(sorted((f.get("kind", ""), norm(f.get("as_written")))
                               for fig in (d["data"].get("figures") or []) for f in (fig.get("features") or [])))
            sigs.append(sig)
        if sigs and arm != "v1-flash":
            top = Counter(sigs).most_common(1)[0][1]
            print(f"     stability: {top}/{len(sigs)} draws share the modal feature set")
    print()

cost = json.load(open(os.path.join(OUT, "cost.json")))
print("COST:", cost)
