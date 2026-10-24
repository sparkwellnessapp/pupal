# Brief: build the marketing-demo data bundle (product repo)

**For:** a Claude Code session working in `vivi-codebase/`.
**Consumer:** the website PR, `C:\Users\ariel\Desktop\ViviWebsite\PR_interactive_demo.md`. Read its §0, §1 and §3 first. The website reads ONLY what this script writes.

**Owner rulings (2026-10-23):**
- Pseudonyms only, no consent process: dan_basiuk → «איתי כהן» (bundle id `student-a`), yonatan_basiuk → «יואב מזרחי» (`student-b`).
- The proposed grades = the teacher's GT grades.
- Hebrew.

Default taken (Noam may veto): blank the handwritten names, the school logo/name, the teacher's circled marks on Dan p1, Dan's thank-you note on p6, and the CamScanner footer. A pseudonym beside a handwritten real name would defeat the ruling.

Plan before code (CLAUDE.md §0.1): post your plan, wait for approval.

---

## 1. What you are building

`backend/scripts/build_marketing_demo_bundle.py` is a deterministic, offline, **zero-API-spend** script. It turns the two real `hobby_tvshow` exams (dan_basiuk, yonatan_basiuk) into a **redacted, teacher-perfect, verified** bundle that the marketing site's demo renders.

```
python scripts/build_marketing_demo_bundle.py --out "C:/Users/ariel/Desktop/ViviWebsite-demo/public/demo/v1" [--check]
```
(`ViviWebsite-demo` is the website's `demo` worktree, created by the website PR's §2. If it doesn't exist yet, write to a scratch dir and copy it in later.)

- `--out` writes **directly into the website folder**. Nothing generated is ever written inside `vivi-codebase/`. The public remotes must never carry the bundle (CLAUDE.md §10: both remotes are PUBLIC).
- `--check` rebuilds into a temp dir, runs every verification in §5 and diffs the result against `--out`. It exits non-zero on any difference. This is what proves the bundle in the website is the one this script produces.
- Hand-authored inputs live in `backend/scripts/marketing_demo/` (committed):
  - `pseudonyms.json`
  - `redactions.json`
  - `corrections/<slug>.json`
  - `copy_cleanup.json`
  - `feedback/<slug>.json`

  They contain no real names (the slugs are the existing fixture ids already in the repo).

## 2. Inputs (all exist today)

| Input | Path |
|---|---|
| Rubric contract | `backend/tests/grading_eval_suite/benchmarks/contracts/hobby_tvshow_corrected.contract.json` |
| Scans (git-ignored, local only) | `backend/tests/transcription_eval_suit/pdfs/hobby_tvshow.<slug>.pdf` (dan 6 pp, yonatan 4 pp) |
| Transcription GT, answer-keyed | `backend/tests/grading_eval_suite/benchmarks/transcriptions/<slug>.contract.json` |
| Transcription GT, page-keyed | `backend/tests/transcription_eval_suit/raw_benchmarks/hobby_tvshow.<slug>.md` (`=== PAGE n ===` sections) |
| Grading GT (teacher-validated) | `backend/tests/grading_eval_suite/benchmarks/gt/<slug>.gt.json` (Dan 84, Yonatan 92.5) |
| Base drafts (real reasoning, quotes, feedback) | `backend/tests/fixtures/grade_review/draft_<slug>.json` |
| Precedents to copy, not reinvent | `scripts/gen_returned_exam_fixtures.py` (compile via the real gate, pin clock and UUID); `frontend/e2e/gradeReviewFixtures.ts::withGradedAnswers` (the `student_answer` backfill) |

## 3. Pipeline steps

1. **Redact the scans.**
   - Open each PDF with PyMuPDF and paint `redactions.json` rectangles (normalized 0–1 page coords, paper color sampled from the page) over:
     - the student-name field;
     - the school logo and name block (מוסינזון);
     - the teacher's circled marks on Dan p1;
     - Dan's thank-you note on p6;
     - the CamScanner footer.
   - Use real redaction (`add_redact_annot` + `apply_redactions`), so the pixels are gone, not covered. Clear the metadata: `set_metadata({})`, strip XMP.
   - Write `scan-redacted.pdf` to a temp dir (it feeds step 6) and the page images to the bundle:
     - `students/<id>/scan/page-<n>.webp` (long edge 1600 px, q≈80)
     - `page-<n>.thumb.webp` (long edge 320 px)
   - Write `_contact_sheet_<id>.png` to the temp dir for the owner's eye review. Never write it to the bundle.
2. **Transcription draft.**
   - Build a `TranscriptionDraft` exactly as `frontend/src/types/transcription.ts` defines it:
     - `schema_version`
     - `student_name_suggestion` = the pseudonym
     - `page_count`
     - `answers[]` = `{question_number, sub_question_id, answer_text, confidence: 1.0, page_numbers}`
     - `annotations: []`
     - `model_version: "demo"`
     - `transcription_duration_ms: null`
   - `answer_text` = the answer-keyed GT, **byte for byte** (student errors included: FC).
   - `page_numbers` are derived by locating each answer's lines in the page-keyed GT.
   - Refuse if any answer cannot be located, or if Dan's p6 note text appears in any answer.
3. **Perfect graded draft.** Start from `draft_<slug>.json`, then:
   - a. **Apply `corrections/<slug>.json`.** These are hand-authored per-check verdict changes plus new `basis_he` / `reasoning` text in plain Hebrew, for the 11 terminals that disagree with GT:
     - **dan:** q1.ב.c2 (1.5), q1.ב.c4 (3), q1.ג.c3 (2), q1.ג.c6 (0.5), q1.ג.c7 (0.5), q2.ב.c3.s0 (2), q2.ב.c4.s0 (1)
     - **yonatan:** q1.א.c1 (4), q1.ג.c1 (1), q1.ג.c7 (0.5), q2.ב.c4.s5 (1)

     Rules:
     - Write each reason from the GT `note`, in teacher language. No plan codes and no English rule names.
     - For a credited check, the quote must be a verbatim span of the answer.
     - **Never** set `points_awarded` directly. Change verdicts only, then re-price.
   - b. **Re-price every scope with the real pricer** (`app/services/pricing.py`, the same calls `compile_graded_test` uses). Write the priced `points_awarded` back at criterion and scope level.
   - c. **Clean visible strings via `copy_cleanup.json`:**
     - Every check `text` / `basis_he`, criterion `reasoning` and annotation `message` must match none of `\[(PL|A|R|AUDIT)-[^\]]*\]`, `R-α`, `R-β`, `PL-\d`.
     - Check texts that embed plan rule text (e.g. «[PL-9] רכיב תקף במונחי עצמו …») are replaced by their plain first clause.
   - d. **Backfill `student_answer`** on every scope from the transcription GT (`withGradedAnswers` precedent), and set every scope's `graded_by = "llm"`.
   - e. **Annotations:**
     - Drop `evidence_unverified` (the corrected draft does not earn it; verify none remains true).
     - Keep `note_only` only if its message reads cleanly after step c.
     - Assert no `error` annotation exists.
   - f. **Feedback:** replace the per-scope `feedback.scopes[<scope>].text` for every scope whose priced score changed, from `feedback/<slug>.json` (hand-written Hebrew, owner-reviewed). Also replace any summary text that names a real student. Recompute each `basis_hash` with the same function the product uses so the UI does not mark it stale. Find it via `feedback_hash` / `feedback-staleness`; refuse if the mirror disagrees.
   - g. Pin `transcription_id`, `rubric_contract_version` (must equal the contract's) and the ids from `pseudonyms.json`, so `scope.student_answer` and the page joins resolve.
4. **Approve.** Run the **real** `compile_graded_test(draft, GradedTestOverrides(), rubric)`. Pin `approved_at` to a fixed demo instant and `contract_version` to a fixed UUID (the `gen_returned_exam_fixtures.py` pattern). Write the `approved` payload in that script's exact shape.
5. **Dan's scripted-override variant** (the demo's control moment).
   - Build `overrides` = Dan's q1.א.c1 changed the way the demo's chapter-3 moment changes it: the check that carries the −0.5 is set to `met`. Determine which check that is; refuse if the result is not 4 / 4 and a total of **84.5**.
   - Compile it the same way into `approved.variant-q1a.json`.
6. **Signed PDFs.**
   - Render with `app/services/returned_exam.py::render_returned_exam` from the **redacted** PDF, using:
     - `scopes_for_render(contract, include_criteria=True)` and `summary_for_render(contract)`;
     - `auto_stamp_position`;
     - score and possible taken from the contract.
   - Name files with `zip_entry_name(<batch name>, <pseudonym>)` (keeps the real `_חתום.pdf` suffix).
   - Also rasterize every page of each signed PDF to `signed/page-<n>.webp` for the in-browser preview.
   - Produce `signed-exams.zip` with both proposed-version PDFs, and Dan's variant PDF alongside.
7. **Manifest.** Write `manifest.json`: `bundle_version: "v1"`, source git commit, generated-at (pinned), per-file sha256 and size, per-student `{id, display_name, pages, total_score, total_possible}`, and the variant's total. Also write `bundle.schema.json` (JSON Schema of `manifest.json` + the per-student file list) so the website validates without importing product types.

## 4. Output layout (as built — the contract with the website)

```
public/demo/v1/
  manifest.json                bundle.schema.json
  rubric.contract.json         # GradingRubricContract (extractQuestions + the rubric peek)
  rubric/page-<n>.webp         # the teacher's rubric DOCX, redacted, rendered by Word (owner ruling
                               # 2026-10-23); listed in manifest.rubric_document.pages[{path,width,height}]
  signed-exams.zip             # both signed exams, as proposed
  signed-exams.variant-q1a.zip # Itai with the scripted change + Yoav
  students/student-a|student-b/
    scan/page-<n>.webp   scan/page-<n>.thumb.webp   # redacted
    transcription.draft.json                         # TranscriptionDraft
    graded.draft.json                                # GradedTestDraftResponse-shaped (feeds GradeReviewSurface)
    graded.approved.json                             # approved payload (feeds ReturnedExamPreview)
    signed/exam.pdf      signed/page-<n>.webp
    graded.approved.variant-q1a.json                 # student-a only
    signed-variant-q1a/exam.pdf  signed-variant-q1a/page-<n>.webp
```

The signed PDF has no per-criterion breakdown (`appendix_include_criteria: false`, the product default).

The rubric pages come from `tests/rubric_eval_suite/fixtures/hobby_tvshow.docx` via a temp copy: header images
blanked (the school logo), «ויויאנה / נעמה» → «ויויאנה», all comments and their parts dropped, author metadata
blanked. Only page images ship. Rendering needs Microsoft Word on Windows (two exports rasterize pixel-identically,
so `--check` holds). Images cannot be grepped, so the privacy rules run on the redacted copy's text before rendering,
and `contact_sheet_rubric.png` goes to the owner's eye.

## 5. Verifications (all run on every build; any failure exits non-zero)

1. Every GT terminal: `points_awarded == awarded` (Decimal). Scope sums priced, not summed by hand. Totals: Dan **84**, Yonatan **92.5**, variant **84.5**, all `/100`.
2. Every quote on a credited check: `quote_match_status(quote, student_answer) == exact`.
3. `compile_graded_test` succeeds for all three, with no unresolved `error` annotation.
4. No plan code (regex in 3c) in any string of any JSON output.
5. **Privacy grep:** none of `basiuk`, `בסיוק`, `דן`, `יונתן`, `מוסינזון`, `Mosinzon`, `Mosenson` (the logo's own spelling), `הוד השרון`, `580024966`, `CamScanner`, `Tapicer`, `טפיסר`, `נעמה`, `ארבל`, `נוימן`, `מגלית` appears in any output file. This covers JSON, PDF text (`page.get_text()`), PDF metadata and ZIP entry names, and the redacted rubric copy's text before it is rendered. Hebrew names match as whole words. «ויויאנה» is allowed (owner ruling 2026-10-23).
6. Every file is under budget: scan webp ≤ 350 KB, thumb ≤ 40 KB, signed-page webp ≤ 400 KB, whole bundle ≤ 14 MB. The whole-bundle figure was 8 MB until the first build measured 12.7 MB; most of that is downloads (two ZIPs at 2.4 MB, three PDFs at 1.1–1.3 MB, with scans embedded at 1,800 px) that load only when the visitor clicks download. The page itself loads page images one at a time, so the page-weight bars belong to the website (Lighthouse), not to this total.
7. Deterministic: two consecutive builds are byte-identical (`--check`).

Write a pytest at `tests/scripts/test_marketing_demo_bundle.py` that runs the build into `tmp_path` and asserts §5. It must skip with a clear reason when the git-ignored scans are absent (CI has none).

## 6. Hand back

- The script, its inputs, the test, and one line in `CLAUDE.md` §8 (Services & agents → scripts) naming the bundle and its "never write into this repo" rule.
- Paths to the contact sheets, for the owner to eyeball **every** redacted page. The bundle is not done until the owner says the redactions are clean.
- A short list of every Hebrew string you authored (corrections, cleaned check texts, feedback), side by side with the original, for the owner's review.

## 7. Do NOT

- Call any model or API. If you think feedback needs regenerating with a model, stop and ask.
- Edit any GT file, fixture, the rubric contract, `pricing.py`, the compiler or the renderer to make a verification pass. A failing check means your corrections are wrong (CLAUDE.md §0.5).
- Write unredacted pages anywhere outside a temp dir, or write anything generated into `vivi-codebase/`.
- Commit the bundle to this repo.
