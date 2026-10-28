"""RENDERER PROTOTYPE — the second half of the feasibility question.

Can a DETERMINISTIC, pure function turn the probed figure spec back into a picture a
teacher recognises as her student's sketch? If not, the whole approach is dead and the
plan must say so.

THE CENTRAL IDEA — QUALITATIVE, RANK-BASED PLACEMENT.
A hand-drawn graph is not a plot. The student drew a SHAPE and marked the features that
matter; she did not place e^4 (54.6) and -e/2 (-1.36) to scale, and a renderer that did
would produce a picture she would not recognise — a vertical spike with everything else
flat on the axis. So marked values are placed by their ORDER, evenly spaced, exactly as a
schematic does. Numeric evaluation is used ONLY to sort; if it fails the array order
stands. The LABEL always shows what she wrote (`e^(1/2)`), never the evaluated number.

Curves are Hermite splines through the marked points with zero tangents at extrema, which
is what makes a minimum look like a minimum.
"""
from __future__ import annotations

import json, math, os, re, sys
from typing import Optional

W, H = 420, 300
PAD_L, PAD_R, PAD_T, PAD_B = 46, 24, 20, 38


# ---------------------------------------------------------------------------
# Reading a WRITTEN value: used only for ORDER. Never for placement, never shown.
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r"\s+")


def read_value(s: str) -> Optional[float]:
    """Best-effort numeric reading of a value as the student wrote it. None when it
    cannot be read — the caller then keeps the order it was given."""
    if s is None:
        return None
    t = _TOKEN.sub("", str(s)).lower()
    if t in ("inf", "+inf", "infinity"):
        return math.inf
    if t in ("-inf", "-infinity"):
        return -math.inf
    t = t.replace("^", "**").replace("sqrt", "math.sqrt").replace("ln", "math.log")
    t = re.sub(r"(?<![a-z_.])e(?![a-z_])", "math.e", t)
    t = re.sub(r"(?<![a-z_.])pi(?![a-z_])", "math.pi", t)
    if not re.fullmatch(r"[0-9a-z_.+\-*/()\s]*", t):
        return None
    try:
        v = eval(t, {"__builtins__": {}}, {"math": math})  # probe only; the real one parses
        return float(v)
    except Exception:
        return None


def rank_positions(values: list[str]) -> dict[str, float]:
    """Written value -> position in [0,1], by ORDER. Ties share a slot."""
    uniq = list(dict.fromkeys(values))
    keyed = []
    for i, v in enumerate(uniq):
        n = read_value(v)
        keyed.append((n if n is not None and math.isfinite(n) else None, i, v))
    unreadable = [k for k in keyed if k[0] is None]
    readable = sorted([k for k in keyed if k[0] is not None], key=lambda k: k[0])
    ordered = readable + unreadable          # unreadable keep their emitted order, at the end
    n = max(1, len(ordered) - 1)
    return {v: (i / n if len(ordered) > 1 else 0.5) for i, (_, _, v) in enumerate(ordered)}


# ---------------------------------------------------------------------------
# Hermite spline with zero tangents at extrema
# ---------------------------------------------------------------------------
def hermite(p0, p1, m0, m1, steps=24):
    out = []
    for i in range(steps + 1):
        t = i / steps
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2
        h11 = t ** 3 - t ** 2
        x = h00 * p0[0] + h10 * m0[0] + h01 * p1[0] + h11 * m1[0]
        y = h00 * p0[1] + h10 * m0[1] + h01 * p1[1] + h11 * m1[1]
        out.append((x, y))
    return out


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_function_plot(fig: dict) -> str:
    curves = fig.get("curves") or []
    pts_all = [p for c in curves for p in (c.get("points") or [])]
    vasym = [a for c in curves for a in (c.get("vertical_asymptotes") or [])]
    if not pts_all and not vasym:
        return ""                                   # nothing drawable -> caller falls back

    xs = [p["x"] for p in pts_all] + list(vasym)
    ys = [p["y"] for p in pts_all]
    xpos = rank_positions(xs)
    ypos = rank_positions(ys + (["0"] if "0" not in ys else []))

    def X(v):   # [0,1] -> svg
        return PAD_L + xpos.get(v, 0.5) * (W - PAD_L - PAD_R)

    def Y(v):
        return H - PAD_B - ypos.get(v, 0.5) * (H - PAD_T - PAD_B)

    y0 = Y("0")
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="system-ui,sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#fff"/>']
    # axes
    parts.append(f'<line x1="{PAD_L-14}" y1="{y0:.1f}" x2="{W-8}" y2="{y0:.1f}" stroke="#334" stroke-width="1.2"/>')
    x_axis_x = PAD_L - 14
    parts.append(f'<line x1="{x_axis_x}" y1="{PAD_T-8}" x2="{x_axis_x}" y2="{H-PAD_B+14}" stroke="#334" stroke-width="1.2"/>')
    ax = fig.get("axes") or {}
    parts.append(f'<text x="{W-6}" y="{y0-6:.1f}" font-size="12" text-anchor="end" fill="#334">{esc(ax.get("x_label","x"))}</text>')
    parts.append(f'<text x="{x_axis_x+5}" y="{PAD_T-10}" font-size="12" fill="#334">{esc(ax.get("y_label","y"))}</text>')

    # vertical asymptotes (dashed)
    for a in dict.fromkeys(vasym):
        parts.append(f'<line x1="{X(a):.1f}" y1="{PAD_T-6}" x2="{X(a):.1f}" y2="{H-PAD_B+8}" '
                     f'stroke="#c33" stroke-width="1.1" stroke-dasharray="5 4"/>')
        parts.append(f'<text x="{X(a)+4:.1f}" y="{PAD_T+2}" font-size="11" fill="#c33">x={esc(a)}</text>')

    # shaded regions, behind the curve
    for sh in fig.get("shaded") or []:
        a, b = X(sh.get("from_x")), X(sh.get("to_x"))
        parts.append(f'<rect x="{min(a,b):.1f}" y="{PAD_T}" width="{abs(b-a):.1f}" '
                     f'height="{y0-PAD_T:.1f}" fill="#2a9d8f" opacity="0.14"/>')
        if sh.get("label"):
            parts.append(f'<text x="{(a+b)/2:.1f}" y="{(y0+PAD_T)/2:.1f}" font-size="12" '
                         f'text-anchor="middle" fill="#1d7a6e">{esc(sh["label"])}</text>')

    # curves
    for c in curves:
        knots = sorted((c.get("points") or []), key=lambda p: xpos.get(p["x"], .5))
        if len(knots) < 2:
            continue
        path = []
        for i in range(len(knots) - 1):
            a, b = knots[i], knots[i + 1]
            p0, p1 = (X(a["x"]), Y(a["y"])), (X(b["x"]), Y(b["y"]))
            span = (p1[0] - p0[0])
            # zero tangent at an extremum, secant-ish elsewhere
            m0 = (span, 0.0) if a.get("role") in ("minimum", "maximum") else (span, (p1[1] - p0[1]))
            m1 = (span, 0.0) if b.get("role") in ("minimum", "maximum") else (span, (p1[1] - p0[1]))
            seg = hermite(p0, p1, m0, m1)
            path += seg if not path else seg[1:]
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in path)
        parts.append(f'<path d="{d}" fill="none" stroke="#1b4965" stroke-width="2.1" stroke-linecap="round"/>')
        if c.get("label"):
            lx, ly = path[-1]
            parts.append(f'<text x="{lx-4:.1f}" y="{ly-8:.1f}" font-size="12" text-anchor="end" fill="#1b4965">{esc(c["label"])}</text>')

        # marked points + their labels, AS WRITTEN
        for p in knots:
            px, py = X(p["x"]), Y(p["y"])
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.1" fill="#1b4965"/>')
            label = p.get("label") or f'({p["x"]}, {p["y"]})'
            below = p.get("role") == "minimum"
            parts.append(f'<text x="{px:.1f}" y="{py + (16 if below else -9):.1f}" font-size="11" '
                         f'text-anchor="middle" fill="#1b4965">{esc(label)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def render(fig: dict) -> str:
    if fig.get("kind") == "function_plot":
        return render_function_plot(fig)
    return ""


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    data = json.load(open(src, encoding="utf-8"))[0]["data"]
    import fitz
    for i, fig in enumerate(data.get("figures", []), 1):
        svg = render(fig)
        if not svg:
            print(f"figure {i}: NOT DRAWABLE -> falls back to caption: {fig.get('caption_he','')[:70]}")
            continue
        open(os.path.join(out, f"fig{i}.svg"), "w", encoding="utf-8").write(svg)
        d = fitz.open("svg", svg.encode())
        d.convert_to_pdf()
        pix = fitz.open("pdf", d.convert_to_pdf())[0].get_pixmap(dpi=140)
        pix.save(os.path.join(out, f"fig{i}.png"))
        print(f"figure {i}: rendered -> fig{i}.png   ({fig.get('caption_he','')[:60]})")
