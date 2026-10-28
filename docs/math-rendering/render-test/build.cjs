// Builds an RTL Hebrew test page rendering the STUDENT'S OWN lines (math4 p07/p09/p11/p12,
// math3 p07) three ways, so the RTL claims in the review are checked in a real browser:
//   A  KaTeX inline, inheriting rtl              (the review says: garbled)
//   B  KaTeX inline inside <bdi dir="ltr">       (the review's fix)
//   C  Temml -> native MathML, inheriting rtl    (the modern alternative)
//   D  Temml -> native MathML inside <bdi dir="ltr">
//   E  MathLive <math-field>, read-only, rtl page
const fs = require("fs");
const path = require("path");
const katex = require("katex");
const temml = require("temml");

const NM = path.join(__dirname, "node_modules").replace(/\\/g, "/");

// [hebrew-before, tex, hebrew-after]  — every line is from the student's pages
const LINES = [
  ["לכן", "x=e^{1/2}=\\sqrt{e}", "היא נקודת הקיצון"],
  ["שטח", "S=4.8\\cdot 3.6=17.28", 'מ"ר'],
  ["מינימום", "\\boxed{\\min(\\sqrt{e},\\,-2.25)}", ""],
  ["חיתוך", "\\left(\\tfrac{1}{e},0\\right),\\ (e^2,0)", "עם ציר x"],
  ["", "t=\\log_{\\frac{0.98}{0.95}}\\frac{235080}{92500}", "שנים"],
  ["השטח", "\\int_{\\sqrt{e}}^{e^2} f'(x)\\,dx=f(x)\\Big|_{\\sqrt{e}}^{e^2}=2.25", 'יח"ר'],
];
const DISPLAY = [
  "\\begin{cases} a_{10}=a_1-90 \\\\ a_{10}=a_1+9d \\end{cases}",
  "S_{10}=1.875\\,S_5",
];
const HEB_IN_TEXT = 'S=17.28\\,\\text{מ"ר}';

const k = (tex, display = false) =>
  katex.renderToString(tex, { throwOnError: false, displayMode: display, output: "html" });
const t = (tex, display = false) =>
  temml.renderToString(tex, { displayMode: display, throwOnError: false });

function row(label, render, wrap) {
  const lines = LINES.map(([a, tex, b]) => {
    const m = render(tex);
    const w = wrap ? `<bdi dir="ltr" class="iso">${m}</bdi>` : m;
    return `<div class="line">${a} ${w} ${b}</div>`;
  }).join("\n");
  const disp = DISPLAY.map((tex) => {
    const m = render(tex, true);
    return `<div class="line">${wrap ? `<div dir="ltr" class="iso">${m}</div>` : m}</div>`;
  }).join("\n");
  const heb = render(HEB_IN_TEXT);
  return `<section><h2>${label}</h2>${lines}${disp}
    <div class="line">עברית בתוך \\text: ${wrap ? `<bdi dir="ltr" class="iso">${heb}</bdi>` : heb}</div></section>`;
}

const mathlive = LINES.slice(0, 4).map(([a, tex, b]) =>
  `<div class="line">${a} <math-field read-only style="display:inline-block">${tex}</math-field> ${b}</div>`
).join("\n");

const html = `<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<link rel="stylesheet" href="file:///${NM}/katex/dist/katex.min.css">
<style>
 body{font-family:Arial,sans-serif;font-size:19px;margin:16px;background:#fff;width:1500px}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
 section{border:1px solid #ccc;padding:10px;border-radius:6px}
 h2{font-size:15px;margin:0 0 8px;color:#a00;font-family:monospace;direction:ltr;text-align:left}
 .line{margin:7px 0;line-height:1.9}
 .iso{unicode-bidi:isolate}
 math-field{font-size:19px;border:none;background:transparent}
</style>
<script type="module" src="file:///${NM}/mathlive/mathlive.min.mjs"></script>
</head><body>
<div class="grid">
${row("A  KaTeX, inherits rtl (no isolation)", k, false)}
${row("B  KaTeX inside <bdi dir=ltr>", k, true)}
${row("C  Temml MathML, inherits rtl", t, false)}
${row("D  Temml MathML inside <bdi dir=ltr>", t, true)}
<section><h2>E  MathLive math-field (read-only) in rtl page</h2>${mathlive}</section>
</div></body></html>`;

fs.writeFileSync(path.join(__dirname, "rtl_test.html"), html);
console.log("written rtl_test.html");
