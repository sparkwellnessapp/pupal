import { chromium } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';

/**
 * Build the hash-labeled review gallery (Design Recovery protocol): capture the
 * committed mirror states as compact JPEGs, embed them + the iter-0 "before" PNG
 * as data URIs, emit a self-contained, theme-aware HTML page.
 *   node scripts/build-gallery.mjs <shortHash> <outPath>
 */
const HASH = process.argv[2] ?? 'unknown';
const OUT = process.argv[3] ?? 'design/gallery.html';
const BASE = process.env.SNAP_BASE_URL ?? 'http://localhost:3100';

const AFTERS = [
    ['markers_demo — after', 'synthetic production markers: real table · LTR code block · markers stripped · Check(arr, 6) correct', 'markers_demo', 'at-rest'],
    ['bagrut — nested (depth-2)', 'q1 → סעיף א → תת-סעיף; the depth-2 case that white-screened', 'bagrut_899371', 'at-rest'],
    ['csharp — code-heavy', 'signatures + trace table; bidi carries code embedded in prose', 'csharp_plane_combine', 'at-rest'],
    ['employee — selection', 'header states the choose-k structure; achievable 50, code as LTR blocks', 'employee_course_select1', 'at-rest'],
    ['foundations — clean', 'zero findings → the reassurance line', 'foundations_cs', 'at-rest'],
    ['hobby', 'short-answer criteria tables', 'hobby_tvshow', 'at-rest'],
    ['bagrut — findings state', 'relocated summary banner + inline annotations at their anchors', 'bagrut_899371', 'findings'],
];

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1240, height: 900 } });
for (let i = 0; i < 40; i++) {
    try { const r = await p.goto(`${BASE}/design-lab?fixture=markers_demo&state=at-rest`, { waitUntil: 'networkidle', timeout: 6000 }); if (r && r.ok()) break; } catch { /* wait */ }
    await p.waitForTimeout(1000);
}

const items = [];
// BEFORE (iter-0 raw markers) — the PNG we captured on the broken build.
items.push({
    kind: 'before', label: 'markers_demo — before', filename: 'iter-0/markers_demo_at-rest_1440.png',
    note: 'raw [TABLE 1: 3x4] · pipe rows · [[color]] · [IMAGE] · bidi-mangled code',
    uri: 'data:image/png;base64,' + readFileSync('design/shots/iter-0/markers_demo_at-rest_1440.png').toString('base64'),
});
for (const [label, note, fx, st] of AFTERS) {
    await p.goto(`${BASE}/design-lab?fixture=${fx}&state=${st}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(450);
    const buf = await p.screenshot({ fullPage: true, type: 'jpeg', quality: 55 });
    items.push({ kind: st === 'findings' ? 'findings' : 'after', label, note, filename: `${fx}_${st}_1240`, uri: 'data:image/jpeg;base64,' + buf.toString('base64') });
}
await b.close();

const card = (it) => `
  <figure class="shot">
    <figcaption>
      <span class="shot-label">${it.label}</span>
      <span class="shot-file">${it.filename}</span>
    </figcaption>
    <p class="shot-note">${it.note}</p>
    <div class="shot-frame"><img loading="lazy" alt="${it.label}" src="${it.uri}" /></div>
  </figure>`;

const before = items.find((x) => x.kind === 'before');
const after0 = items.find((x) => x.label === 'markers_demo — after');
const rest = items.filter((x) => x !== before && x !== after0);

const html = `<style>
  :root{
    --bg:#FBF7EF; --card:#FFFFFF; --ink:#1C1917; --muted:#78716C; --faint:#A8A29E;
    --line:#E7E5E4; --accent:#0D9488; --accent-soft:#CCFBF1; --frame:#F5F5F4;
  }
  @media (prefers-color-scheme:dark){:root{
    --bg:#171310; --card:#221E19; --ink:#F3EEE6; --muted:#A8A29E; --faint:#78716C;
    --line:#37312B; --accent:#2DD4BF; --accent-soft:#0f3b36; --frame:#1B1712;
  }}
  :root[data-theme="dark"]{--bg:#171310;--card:#221E19;--ink:#F3EEE6;--muted:#A8A29E;--faint:#78716C;--line:#37312B;--accent:#2DD4BF;--accent-soft:#0f3b36;--frame:#1B1712;}
  :root[data-theme="light"]{--bg:#FBF7EF;--card:#FFFFFF;--ink:#1C1917;--muted:#78716C;--faint:#A8A29E;--line:#E7E5E4;--accent:#0D9488;--accent-soft:#CCFBF1;--frame:#F5F5F4;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:'Rubik',system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.55;
    -webkit-font-smoothing:antialiased;}
  .wrap{max-width:1080px;margin:0 auto;padding:40px 24px 80px;}
  header{border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:8px;}
  .eyebrow{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;
    letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:0 0 10px;}
  h1{font-size:28px;font-weight:600;line-height:1.2;margin:0 0 6px;text-wrap:balance;}
  .sub{color:var(--muted);max-width:64ch;margin:0 0 18px;}
  .meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;}
  .chip{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;
    background:var(--accent-soft);color:var(--accent);border:1px solid color-mix(in srgb,var(--accent) 25%,transparent);
    padding:3px 9px;border-radius:6px;}
  .chip.plain{background:transparent;color:var(--muted);border-color:var(--line);}
  h2{font-size:16px;font-weight:600;margin:44px 0 4px;letter-spacing:-.01em;}
  .sec-note{color:var(--muted);font-size:14px;margin:0 0 18px;}
  .shot{margin:0 0 30px;}
  figcaption{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
    border-bottom:1px solid var(--line);padding-bottom:6px;}
  .shot-label{font-weight:600;font-size:15px;}
  .shot-file{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;
    letter-spacing:.04em;color:var(--faint);white-space:nowrap;}
  .shot-note{color:var(--muted);font-size:13.5px;margin:8px 0 12px;}
  .shot-frame{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--frame);}
  .shot-frame img{display:block;width:100%;height:auto;}
  .ba{display:grid;grid-template-columns:1fr 1fr;gap:20px;}
  @media (max-width:820px){.ba{grid-template-columns:1fr;}}
  .ba .shot-frame{max-height:520px;overflow:auto;}
  footer{margin-top:56px;border-top:1px solid var(--line);padding-top:20px;color:var(--muted);font-size:14px;}
  footer code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--frame);
    border:1px solid var(--line);border-radius:5px;padding:1px 6px;font-size:12.5px;color:var(--ink);}
  footer b{color:var(--ink);font-weight:600;}
  a{color:var(--accent);}
</style>

<div class="wrap">
  <header>
    <p class="eyebrow">Design Recovery · Pass 1 gallery</p>
    <h1>RubricDocument mirror — fresh snap</h1>
    <p class="sub">Every state rendered deterministically from <code style="font-family:ui-monospace">/design-lab</code>
      at the committed tree, captured full-page at 1240px. Read, then reviewed — not shipped blind.</p>
    <div class="meta">
      <span class="chip">commit ${HASH}</span>
      <span class="chip plain">branch perf/rubric-extraction-latency</span>
      <span class="chip plain">tsc · 191 vitest · next build · token-gate green</span>
    </div>
  </header>

  <h2>The headline: markers rendered raw → fixed</h2>
  <p class="sec-note">The Sprint-2 defect the suite exists to kill. Left is the broken build (iter-0); right is ${HASH}.</p>
  <div class="ba">
    ${card(before)}
    ${card(after0)}
  </div>

  <h2>Fixtures &amp; states @ ${HASH}</h2>
  <p class="sec-note">The five golden fixtures + the findings state. Full 36-shot set lives in <code style="font-family:ui-monospace">design/shots/iter-${HASH}/</code>.</p>
  ${rest.map(card).join('\n')}

  <footer>
    <p><b>Review protocol.</b> This gallery is the static first-look from <code>${HASH}</code>. For the interactive
      round (hover affordances, cascade feel, undo): <code>git pull</code> the branch, then <code>npm run dev</code>
      and open <code>/design-lab</code> — same tree, provably.</p>
    <p style="margin-top:12px"><b>Still needed before the craft fixed-point.</b> §1c reference targets
      (2–3 screenshots + one paragraph of "the feel"), and the <b>F3</b> ruling: chrome-on-intent (shipped —
      points/name plain until hover) vs "buttons look like buttons at rest" (§1b). They conflict; the craft
      loop is blocked on which bar wins.</p>
  </footer>
</div>`;

writeFileSync(OUT, html);
console.log(`gallery → ${OUT} (${(Buffer.byteLength(html) / 1e6).toFixed(2)} MB)`);
