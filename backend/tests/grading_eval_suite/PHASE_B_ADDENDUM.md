# PHASE B ADDENDUM — the three follow-up rulings executed (2026-08-24)

**Rulings D1/D2/D3 from the owner's Phase-B follow-up message; text applied
verbatim where mandated. Spend: $0. Zero `app/`. Zero Gemini — unchanged.**
**State after this addendum: [STOP] F5 — owner blind grading.**

---

## D1 — the H1-A1 supersede (DL-7), per-item DONE

### 1. Red-first, both outputs verbatim

**(a) F0 pin test extended** (new sub-id assertion) — red vs the pre-fix tool:
```
>  assert gimel_children == ["q2.ג.c0.s0", "q2.ג.c0.s1", "q2.ג.c0.s2", "q2.ג.c0.s3"], gimel_children
E  AssertionError: ['q2.ב.c6.s0', 'q2.ב.c6.s1', 'q2.ב.c6.s2', 'q2.ב.c6.s3']
```

**(b) class-closing path-honesty structural guard**
(`test_terminal_ids_are_path_honest_in_all_bundles`: every terminal id prefixed
by its full ancestor chain — sub-criterion by criterion, criterion by scope
target — across ALL FIVE loaded bundles) — red vs the first ratified snapshot,
naming exactly the DL-7 class, 4 offenders × 5 bundles:
```
E  AssertionError: path-dishonest ids (child not prefixed by parent):
   [('dan_basiuk', 'q2.ג.c0', 'q2.ב.c6.s0'), ... ('yonatan_basiuk', 'q2.ג.c0', 'q2.ב.c6.s3')]
1 failed in 0.80s
```
This guard would have caught DL-7 at birth; it now runs in `pytest -q` forever.

### 2. Tool extended
`apply_recorded_fix`: a moved criterion renames its children with it — prefix
swap preserving each child's own suffix (`q2.ב.c6.s2 → q2.ג.c0.s2`), asserted
against the old prefix before swapping. `ratify()` provenance now records
DL-5 + DL-6 + DL-7 plus an `amendments: [H1-A1]` block
(`ratified_by: Noam, 2026-08-24`).

### 3. Supersede mechanics (not overwrite)
Prior ratified snapshot + provenance **deleted in the supersede commit** (git
history is the archive — no `_superseded/` folder); `--ratify` re-run (its
exists-refusal untouched — deletion IS the supersede path). The tool's
`build_proposal` regenerates the H1 doc from its template, which would have
rewritten the original text — **restored from HEAD, then the Amendment section
APPENDED** (one-line diff + ratification line); the original proposal text is
byte-untouched.

### 4. Downstream regenerated — universe unchanged, ids-only delta

| Proof | Value |
|---|---|
| Former reds now green | `test_fixture_tools.py` **5 passed** (incl. the structural guard vs the NEW snapshot) |
| New rubric sha256 | **`c988eb7d1856f041`** (was `3b208a84e573734f`) |
| Manifests ×5 | all pin the new rubric hash (asserted programmatically) |
| Transcription snapshots | **byte-identical 5/5** (deterministic converter; hashes `b15cddc8…/634066f3…/ee2cbe0f…/0d604c07…/19c0be81…` unchanged) |
| Skeletons ×5 | regenerated; **38 terminals/fixture, 190 total, judgments all null**; each pins the new rubric hash |
| ids-only delta, per fixture | `− [q2.ב.c6.s0..s3] + [q2.ג.c0.s0..s3]` — nothing else moved |

### 5. Supersede commit
**`9697e7b`** — deletion + new snapshot/provenance + tool + both tests +
H1 Amendment + manifests ×5 + skeletons ×5 + RUNLOG/PLAYBOOK/TRACKER
(23 files). RUNLOG CHANGE entry appended; suite_hash shift noted (harmless —
no baseline exists).

---

## D2 — DL-8 bookkeeping (ratification recorded; norm restated in RUNLOG)

**The `.gitignore` diff (commit `3edbf15`):**
```diff
 !tests/rubric_eval_suite/benchmarks/*.json
+# Grading eval suite (mission v0, same precedent): configs, per-fixture
+# manifests, frozen contract snapshots and GT files are SOURCE — hash-pinned
+# provenance the runner validates against committed state. NOT eval output.
+!tests/grading_eval_suite/configs/*.json
+!tests/grading_eval_suite/fixtures/*.json
+!tests/grading_eval_suite/benchmarks/**/*.json
+# ...except the F0 staging area (superseded by the ratified snapshot):
+tests/grading_eval_suite/benchmarks/contracts/_proposed/
 # eval RUN OUTPUTS are regenerable artifacts — never commit them (repo bloat).
```

**The `.gitattributes` diff (commit `624337f`, new file):**
```diff
+# Grading eval suite: hash-pinned artifacts (D5) — byte-stable across checkouts.
+# The loader validates sha256 of these files; EOL normalization would break
+# every GT hash pin on a fresh clone. No text conversion, ever.
+backend/tests/grading_eval_suite/benchmarks/** -text
+backend/tests/grading_eval_suite/fixtures/*.json -text
```

**Corrected commit ledger** (the Phase-B report's table omitted `68fef8b`):

| Hash | Carries |
|---|---|
| `6337fbc` | the two owner GT edits (`din_ezra.md`, `yonatan_basiuk.md`) — committed FIRST per ruling 2 |
| `3f675db` | Phase A instrument + Phase B code/tools/docs (28 files — **zero JSON artifacts**: silently dropped by the `*.json` net, the DL-8 trigger) |
| `3edbf15` | the `.gitignore` un-ignore + the 18 recovered JSON artifacts (configs/manifests/snapshots/skeletons/provenance) |
| `624337f` | `.gitattributes` `-text` pins for the hash-covered artifacts |
| `68fef8b` | Phase B docs: PHASE_B_REPORT + TRACKER/RUNLOG/ONBOARDING/PLAYBOOK/GT_CONVENTIONS state |
| `9697e7b` | the H1-A1 supersede (this addendum §D1.5) |

## D3 — calibration exclusion RATIFIED

PLAYBOOK §4 C-2 note now carries `RATIFIED 2026-08-24, reviewer verdict +
owner approval — Phase-B ruling D3`. RUNLOG: append-only discipline honored —
the ratification is recorded in the new CHANGE entry, which explicitly marks
the prior entry's flagged judgment RATIFIED; the prior entry itself is
untouched. No code change (as ruled).

---

## Batteries at close

| Battery | Result |
|---|---|
| Suite + eval_common | **49 passed, 1 xfailed** (48 + the new structural guard; xfail = the D5 sonnet sentinel) |
| Transcription | **134 passed / 1 skipped — baseline-identical** |
| Rubric | 30 passed / **17 failed = 8 known Family-D + 9 NEW, attributed to a CONCURRENT session's in-flight work** — the failures sit in `test_scoring.py`/`test_fp123.py`, and `scoring.py`/`schemas.py`/`runner.py` are Modified in the working tree by that session's fix-effect feature (its `fix_effect_consistent` fields appeared mid-phase). Zero rubric files appear in any of this suite's six commits; not ours to fix, recorded for the reviewer |

---

## [STOP] F5 — owner handoff (verbatim-required content included)

Grade only against the **regenerated skeletons** — the loader's hash guard
will refuse anything authored against superseded ids, and that refusal is
correct, not a bug. 190 judgments ≈ ~3 hours; splitting across sittings is
fine, but each fixture is completed and `authored_at`-stamped as a single
unit (blindness lives at the fixture level). `[C1-TABLE]` notes and
`ungradable_scopes` per ratified C-1/C-2. After all five `<name>.gt.json`
files are committed, P2 (owner + reviewer pre-baseline prediction) unlocks
the Phase C k=5 baseline.
