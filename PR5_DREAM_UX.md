# PR-5 — The Extraction Flow Dream UX (design source of truth)

Locked via structured interview, 2026-07-18. Every PR-5 sprint spec cites this
document; deviations require an explicit ruling, not improvisation.

---

## 1. The teacher (persona laws — every screen is judged against these)

She is 50–60, low tech comfort (has tried ChatGPT, warily), **skeptical but
desperate**. It is evening, at home, days before grades are due, and she has
not started. She works solo — nobody onboards her. She will do this ~monthly.

**Law 1 — Design for the tired skeptic, not the median.** Every screen must
visibly pay for itself in saved effort.
**Law 2 — Permanently near-first-use.** Monthly frequency at low tech comfort
⇒ no design may rely on memory of a previous session. Everything
self-explains, every time.
**Law 3 — The competitor is manual grading.** Her fear is not AI; it is
net-negative time ("overcomplicated to verify ⇒ I wasted an evening I could
have spent grading the old safe way"). The flow's continuous job is proving
"this is faster than doing it yourself."
**Law 4 — Her document is the north star.** The quit condition is getting
lost in an editor that doesn't resemble her DOCX. The review surface must
read as *her rubric, annotated by Vivi* — never as a form-builder that
happens to contain her content.

## 2. Voice & framing laws (apply to every string)

- **Findings are about the document, never about her.** "במסמך מצוין 3 נק',
  אך הקריטריונים מסתכמים ב-2" — the paper has a discrepancy; nobody is accused.
- **Tone: factual + one warmth beat maximum.** State the discrepancy, propose
  the fix, allow one human touch ("כנראה טעות חישוב קטנה"). Never chummy,
  never deferential-questioning.
- **Never lie about state.** No fake progress, no stale assertions, no
  estimate the p50 breaks. Resolution TRANSITIONS state; it never vanishes and
  never leaves a false claim on screen.
- **Consistent feminine address** (העלי/גררי/המשיכי) everywhere; correct Hebrew
  pluralization (שגיאה אחת / 2 שגיאות).
- **A finding is a distinct node-level event, counted once.** The extraction
  annotation and the live validator entry for the same discrepancy are ONE
  finding: the live entry is its recomputable blocker, the extraction text its
  document-framed residual. Counts dedup by node; no number on screen may
  double-report one event.
- **One naming system.** שאלה 1 · סעיף א · תת-סעיף 2 — in labels, findings,
  summaries, save gates. Technical ids (q1.א.2) never reach her eyes.

## 3. The journey (the new narrative)

**Upload.** One action: drop the DOCX. No language dropdown, no purpose
interstitial (deleted), no name field. The job submits on drop with zero
parameters. (Language/title are inferable; anything she doesn't provide, the
extraction infers.)

**The wait (4–6 min), in two movements.**
*Movement 1 — productive capture (~first minute):* while extraction runs, a
calm card offers the two optional decisions: rubric name (pre-filled
suggestion when derivable) and programming language (default from inference,
correctable). These patch job METADATA only — extraction never depends on
them. She finishes setup inside time she was going to spend anyway.
*Movement 2 — calm honest waiting:* elapsed time; the promise "עלול לקחת 4–5
דקות"; live stage lines as they truly change (קוראת את המסמך → מנתחת את
המחוון → …). Threshold reassurances that acknowledge time rather than fake
progress: 3:00 "עדיין עובדת — מחוונים מפורטים לוקחים יותר"; 6:00 "כמעט שם —
המחוון שלך עשיר במיוחד". Designed for staying; leaving is quietly supported
(state is server-side; tab title flips to "✓ המחוון מוכן" + a gentle chime on
completion).
*Failure:* an honest screen, correctly-placed blame ("תקלה אצלנו — לא בקובץ
שלך" when true), exactly two one-click buttons: «לנסות מחדש» (file already
stored; no re-upload) and «דיווח תקלה». No silent auto-retry — failures are
always visible.

**Arrival.** Before the document: one summary card. "סיימתי לקרוא את המחוון ✓
· **מבחן בחירה: 4 מתוך 6 שאלות** · 100 נקודות · 61 קריטריונים · **ממצא אחד מחכה לאישורך**" — selection structure is first-class, never again hidden
behind raw counts. Finding preview with the one-click recommended fix
available right there. One button: «עברי על המחוון».

**Review — the document-mirror.** The rubric renders as a clean document in
her DOCX's shape: questions flowing top-down; parts under their real
identities (the naming law); **criteria as a table** — the dominant DOCX
rubric pattern — points in a column, rows expandable ONLY where a
points-breakdown exists; her solution blocks present, collapsed, code LTR;
question-embedded data tables rendered as actual mini-tables (never digit
soup). Structurally-empty parents show identity + points + children — no
empty text boxes; add-text affordance appears on edit intent only.
Everything reads first, edits second — with clear editability signals
(hover/focus states turning values into fields).
A minimal guided tracker floats quietly: "ממצאים: 1/2 טופלו", jump-to-next.
The document remains freely scrollable for the teacher who wants to verify
everything.

**Judgment.** Each finding is ONE card (the error/warning duplication is
dead), anchored in the margin at its node, speaking the voice law, carrying
Vivi's recommended fix as the primary button (recommendation: align criteria
to the declared total — the declared came from her exam header) with the
alternative one click deeper, and an inline «בטלי» undo for a few seconds
after apply. Lifecycle: `פתוח (חוסם)` → fixed (by apply or manual edit) →
`טופל ✓` — collapsed, checkmarked, with the honest residual where true:
"✓ תוקן במחוון · שימי לב: בקובץ המקורי עדיין מצוין 3". The tracker counts up.
No stale assertion can survive a fix — state is recomputed, not narrated.

**Save.** The survivor gate: only findings she deliberately left open get one
final ask ("ממצא אחד נשאר פתוח — לשמור בכל זאת?" with jump-back links);
resolved findings never re-ask. Compile (~15s) runs behind an honest light
overlay ("בודקת עקביות… מרכיבה את חוזה הניקוד…"). Then the completion card:
her rubric's NAME (the UUID is dead), the facts line, the earned-partnership
beat — "המחוון מוכן — עברת על הכל ואישרת. מכאן ויוי בודקת לפיו." — and the
primary CTA «המשיכי לבדיקת מבחנים» that CARRIES the rubric: she lands on
upload-tests with this rubric pre-selected. The RubricSelection screen is
deleted from this journey. A navigation guard protects unsaved review work
("יש שינויים שלא נשמרו — לצאת בכל זאת?").

**Return.** A finished-but-unsaved extraction greets her as a closeable
home-page banner ("המחוון 'בגרות תשפ"ו' מוכן לסקירה" → deep-link into review)
AND as a "טיוטה — ממתינה לאישור" entry in מחוונים שלי. The page otherwise
stays as-is for MVP.

## 4. Backend delta (deliberately small — verified against existing machinery)

1. **Zero-param submit**: job accepts file-only; request_params optional.
2. **Metadata patch endpoint**: name/language onto a running job —
   metadata-only by contract; the runner never reads them; they merge at
   result/save time. (Extraction quality never depends on captured params —
   they are inferable, per ruling.)
3. **Nothing else.** The arrival summary is client-computed from the result
   JSON (selection groups, counts, findings — all present). The one-click fix
   applies the existing `suggested_fix` (operation/params, Tier-A-populated)
   to local state + client re-validation. Draft-status and the banner read
   the existing jobs list. Stage events already persist. Phrasing is Hebrew
   templates at MVP; an LLM-phrasing pass is a flagged later option, not a
   dependency.

## 5. Sprint decomposition (all in MVP, per ruling; each independently shippable)

**Sprint 1 — The session spine** (flow mechanics; no rebuild):
kill the purpose interstitial; zero-param submit + metadata-patch capture
card; wait redesign (promise copy, stages, 3:00/6:00 reassurances, tab-title
+ chime); failure screen (two buttons); arrival summary card (informational
version); save overlay + completion card + partnership beat; carry-through
handoff (upload-tests pre-selected; RubricSelection bypassed); navigation
guard; the full copy pass (voice law, gender, pluralization).
*Covers B, D, E, H + summary shell of C. Backend items 1–2 land here.*

**Sprint 2 — The document-mirror** (the rebuild; biggest item):
the review surface as §3 describes — document layout, naming law everywhere,
criteria-as-table with conditional expanders, mini-tables in question text,
empty-parent rendering, solution blocks, in-place editability signals.
Golden round-trip suite and client-validator parity stay green throughout —
the mirror is a new VIEW over the same state/transform layer, not a new data
path.
*Covers A + F.*

**Sprint 3 — Findings & judgment** (on the mirror):
single-card findings with the state machine; margin anchoring; guided
tracker; recommended fix + undo (from summary card and in-document); the
stale-warning class killed by recompute-on-change; survivor-only save gate
(reworks the PR-4 ack modal).
*Covers C fully + the lifecycle. Depends on Sprint 2.*

**Sprint 4 — Continuity & return** (smallest):
home banner (closeable, deep-link), "טיוטה — ממתינה לאישור" in מחוונים שלי,
resume-into-review path hardened.
*Covers G-as-ruled.*

## 6. The session test (PR-5's definition of done)

A tired, skeptical, first-time teacher uploads her real selection Bagrut at
21:30, in one sitting and without help: drops the file, names it during the
wait, watches honest progress, meets "ממצא אחד" as a discovery about her
document, fixes it in two clicks with the state visibly resolving, saves
through the honest ceremony, reads her rubric's name and the partnership
line, clicks once, and is standing in front of the tests-upload screen with
her rubric already chosen — never having seen a UUID, a technical id, an
empty box, a stale warning, or a screen that asked her where she was.