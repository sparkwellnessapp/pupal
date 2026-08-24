# PHASE B REPORT — fixtures + GT pipeline (owner-ruled 2026-08-24)

**Executed strictly in the ruled order (item 7). Spend: $0. Zero files under
`app/`. Zero Gemini. Ruling text pasted verbatim where mandated.**
**Current [STOP]: F5 — owner blind-grades the five tests.** Phase C stays gated
on P2 (pre-baseline prediction).

---

## Per-item DONE + proofs

### 1. Sibling commit → ratify → snapshots (ruling items 1/2, order kept)

| Step | Proof |
|---|---|
| Commit siblings FIRST | **`6337fbc`** — exactly `din_ezra.md` + `yonatan_basiuk.md` (2 files, +4/−4), message attributes owner GT edits. `hobby_tvshow.json` verified clean at HEAD beforehand |
| F1 parity re-run POST-commit | `test_converter_parity_on_all_five_docs` → **1 passed** (5/5 byte-identical; logged in RUNLOG as evidence hygiene) |
| H1 `--ratify` | `[H1] ratified snapshot written: benchmarks/contracts/hobby_tvshow_corrected.contract.json` + `.provenance.json`: `ratified_by: Noam`, `date: 2026-08-24`, DL-5 + DL-6 recorded |
| F2 snapshots | 5 transcription contracts, 6 answers each. sha256 (first 16): rubric `3b208a84e573734f` · dan `b15cddc85f376499` · din `634066f3e66b2e7f` · moran `ee2cbe0fffeb8c4d` · omer `0d604c07ed8005d3` · yonatan `19c0be811220d6b2` |
| B3 manifests ×5 | committed; **post-commit verification: all five bundles load with hash pins verifying** (38 terminals each) |

### 2. C-rulings encoded (items 3/4/5 — verbatim paste)

- **C-1 / C-2 / C-4** ruling text pasted verbatim into `GRADING_GT_CONVENTIONS.md`
  (status now RATIFIED; F5 unblocked). C-1's step-3 model-side line mirrored in
  ONBOARDING **§6 Design inputs for step 3**; no new gate added, as ruled.
- **C-2 instrument change — failing test FIRST** (red output):
  ```
  FAILED test_scoring.py::test_ungradable_scope_terminals_excluded_from_agreement
  FAILED test_scoring.py::test_gt_note_travels_to_terminal_rows
  FAILED test_reporting.py::test_fixture_report_displays_gt_note_and_totals_mark
  FAILED test_reporting.py::test_aggregate_counts_c1_table_and_ungradable_terminals
  4 failed in 0.53s
  ```
  Then: `TerminalScore` + `ungradable_scope`/`gt_note`; scorer excludes
  ungradable-scope terminals from MAE/within-precision/exact/edit_burden/
  compensating input while totals keep the best-guess (pinned: gt_total 9 /
  ai_total 5 with the |Δ|=4 ungradable disagreement invisible to Tier-2);
  Tier-1 ungradable-guess tripwire unchanged (existing guard still green).
  **Agent judgment flagged for review:** the exclusion is extended to the
  calibration input (correctness vs a best-guess GT is noise by construction) —
  documented in PLAYBOOK §4 and the RUNLOG CHANGE entry.
- **Item 6 reporting**: GT-note column in the fixture table ([C1-TABLE] visible
  to the read-by-hand ritual), the "total includes N ungradable-scope
  terminal(s)" mark, per-fixture Tier-3 counts `c1_table_terminals` +
  `ungradable_terminals` — all pinned by the two reporting tests.
- suite_hash shift noted in RUNLOG (harmless pre-baseline, as ruled).

### 3. B4 — skeletons emitted

Five files `benchmarks/gt/<name>.gt.skeleton.json`, **38 terminals each**
(spot-checked: judgments all null, `blind: true`, hashes pre-filled, document
order). **190 total judgments — above the mission's ~120–150 estimate** (the
corrected rubric's terminal count at sub-criterion depth); flagged, not a blocker.

### 4. Batteries + sanity gates

| Gate | Result |
|---|---|
| Suite + eval_common | **48 passed, 1 xfailed** (the pre-existing D5 sonnet sentinel) |
| Transcription | 134 passed / 1 skipped (unchanged) |
| Rubric | 33 passed / 8 failed = **exactly** the known Family-D set (unchanged) |
| `import app.main` / collect-only | OK / OK |

### 5. Commits

| Hash | Content |
|---|---|
| `6337fbc` | the two owner GT edits (first, per ruling 2) |
| `3f675db` | Phase A instrument + Phase B code/docs (28 files) |
| `3edbf15` | **DL-8**: gitignore un-ignore + the 18 fixture artifacts |
| `624337f` | `.gitattributes` `-text` pins for hash-covered artifacts |

---

## Two findings surfaced (not decided)

**DL-7 — sub-criterion ids under the new ג.** `q2.ג.c0` is a *branch*
criterion: its four sub-criteria are the actual terminals and still carry the
pre-move ids **`q2.ב.c6.s0..s3`** — DL-5 renamed the criterion id exactly as
ratified, and sub-criterion ids were never in the proposal. Everything is
internally consistent (the GT universe is compiler-derived, so skeletons/GT/
scoring all use these ids), but the `ב` prefix lies about the path and will
appear in your blind-grading skeletons and every report. **Option, cheap only
NOW (before GT lands):** I re-stage with `q2.ג.c0.s0..s3`, you re-ratify (one
diff line), skeletons regenerate. Proceeding as ratified unless you rule
otherwise — say the word before starting F5.

**DL-8 — the fence deviation, already executed.** `backend/.gitignore`'s broad
`*.json` credential net silently dropped every fixture artifact from the first
commit (configs, manifests, snapshots, skeletons — commit `3f675db` carried
zero of them). Extended the un-ignore exactly on the rubric suite's PR-4
precedent, scoped to this suite's source paths (`_proposed/` staging stays
ignored; `results/` stay ignored), plus root `.gitattributes` `-text` so EOL
normalization can never silently break the D5 sha256 guards on a fresh clone
(verified post-commit: all five bundles load, pins green). Without this the
ruling's "snapshots and provenance must point at committed state" was
unsatisfiable. Two files outside the literal fence (`backend/.gitignore`,
`.gitattributes`), zero production code.

---

## The F5 handoff (owner)

For each of the five fixtures: open `benchmarks/gt/<name>.gt.skeleton.json`,
grade blind from the corrected rubric + the transcription text only [R1],
fill `awarded` (Decimal string, 0.25 grid) + `evidence_exists` per terminal,
add `ungradable_scopes` per C-2 (best-guess awards stay in), `[C1-TABLE]`
notes per C-1 where used, stamp `authored_at` (ISO-8601), delete
`_instructions`, save as `benchmarks/gt/<name>.gt.json`, commit. The loader
refuses partial or off-grid files — that is the completion check. Then P2
(pre-baseline prediction, owner + reviewer) unlocks Phase C.
