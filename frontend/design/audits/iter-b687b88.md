# Design Recovery — Audit iter-b687b88 (PR-6b: the findings lifecycle, on the steps wire)

**Apparatus:** `/design-lab?fixture=&state=` + `node scripts/snap.mjs b687b88` →
`design/shots/iter-b687b88/` — **60 shots**: 6 fixtures × 4 states × 2 viewports (48)
+ the 8 named/interactive captures + **4 new lifecycle captures** (hobby
`cards-resolved` / `cards-dismissed` × 2 viewports). Commit `b687b88`.
Every claim below was read off the named PNG.

**What's new in the apparatus itself:** the `cards-*` states compose findings through
the PRODUCTION module (`composeFindings`) from each fixture's **own GT pedagogical
canon** — no staged copy. `cards-resolved` additionally applies every proposal through
the real `applyEditSteps` interpreter, so the resolved shots show what one click
actually produces, not a hand-arranged tree. (`LabFrame.tsx`; `snap.mjs` gains
`cards-open` in the matrix + the hobby lifecycle pair. The Round-2 rail drive regex
is now `^`-anchored — PR-6's collapse toggles named «הרחיבי/כווצי שאלה N» collided
with the unanchored match.)

## Directives — evidence

| Claim | Result | Evidence (named PNG) |
|---|---|---|
| **Root-cause trio composes as designed** — one teal advisory root + two amber shadows | **MET** | `hobby_tvshow_cards-open_1440` — header counts «2 ממצאים לתיקון · המלצה אחת»; at שאלה 2 the amber shadow (44 מול 60) and the teal root card; at סעיף ב the second amber shadow (45 מול 29). |
| **The steps proposal is ONE button, machine steps never leak** | **MET** | same shot — the root card offers «העבירי את רכיב PrintLowRatingChannel לסעיף ג'» + «השאירי כך»; no op names, no scope ids in visible text. |
| **Shadows point at the root and offer NO local fix and NO dismiss** | **MET** | same shot — both amber cards carry the «נובע כנראה מטעות אחרת… עברי לממצא המקורי» line, no fix button, no «השאירי כך» (they are live INV violations; the compiler would reject a dismissal). |
| **One click settles ALL of q2** (D3 in pixels) | **MET** | `hobby_tvshow_cards-resolved_1440` — **סעיף ג exists** (16 נק', the carved PrintLowRatingChannel text + its 16-pt criterion), סעיף ב back to 29 with 6 criteria, all three cards collapsed to «✓ תוקן במחוון · בטלי», the header counts line gone. Applied by the real interpreter, not staged. |
| **Dismissal is her recorded decision, reversible, not a deletion** | **MET** | `hobby_tvshow_cards-dismissed_1440` — collapsed rows «נשאר כפי שהוא — לבחירתך · החזירי את הממצא»; document content unchanged. |
| **Legacy drafts still get the one-click** (params→steps translation arm) | **MET** | `bagrut_899371_cards-open_1440` @y≈1019 — the q1.א.2 trinity card: live present-tense claim, hedged explanation, «בקובץ המקורי מצוין 3» residual, orange «עדכני את הניקוד המוצהר ל-2» button + the manual route. Its GT fix was probe-re-transcribed to the steps shape this iter; the 3.5.0-params arm is exercised by the findings suite. |

## Regression sweep

`at-rest` / `findings` / `solutions-expanded` re-captured for all six fixtures at both
viewports — no visual drift observed against iter-01af1ef in the header band, tables,
code blocks, or rail (the rail now carries PR-6's finding dots + collapse toggles, as
shipped).

## Residual notes

- Null controls verified live: `csharp_plane_combine` and `foundations_cs` render
  `cards-open` with **zero** cards (clean GT canons — composition invents nothing);
  `employee_course_select1` renders exactly one **document-level**
  `selection_normalization` info card (D8: deliberately fix-less), anchored in the
  advisory strip, not on a node.
- The gallery (`design/gallery-b687b88.html`, self-contained base64) curates the
  four story shots above; the full 60 live in the gitignored shots folder.
