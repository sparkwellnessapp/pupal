# H1-A2 ADDENDUM — embedded model solutions (supersede #2) + dan_basiuk GT (2026-08-25)

**Zero spend · zero `app/` changes · zero Gemini.**

## 0. Prerequisite gate

**M1 was already landed** (PR-G1 v2, commit `71305dc`): the loader accepts
`gt_source: teacher_validated` with `blind: false` + `proposed_by` +
`validated_by` — dan's GT loads under it (proof in §4).

## 1. Reds (verbatim)

```
E   ImportError: cannot import name 'load_model_solutions' from
    'grading_eval_suite.tools.f0_hobby_correction'
E   GTValidationError: dan_basiuk: GT hash pin failed — gt.rubric_contract_hash
    does not match the snapshot file (D5). Re-authoring against a changed
    contract is an OWNER decision, never silent.
```
Both new pins red (parser absent; all six fields verified `NONE` pre-change),
**plus the D5 guard already refusing dan's placeholder-hashed GT mid-supersede
— the guard doing exactly its designed job.**

## 2. The supersede (mirrors H1-A1 mechanics)

- Source artifact committed: `benchmarks/contracts/_sources/model_solutions_transcription.md`
  (T-1/T-2/T-3 ratified with the content; one in-review correction — the
  `minChannel` comment).
- Tool embeds the six fenced blocks **verbatim, fences stripped, zero
  normalization** — pinned byte-equal per field plus literal spot-pins for the
  ruled hazards: the stray `//` after `new int[101];`, the multiline
  `if (   sumRates…` formatting, `internal class Hobby`, Hebrew comments;
  q2.א pinned = constructor block then UpdateRate block.
- Prior snapshot + provenance **deleted in the supersede commit**; `--ratify`
  re-run; provenance chain records **H1 + A1 + A2** (source line + ratifier +
  date + the in-review correction).
- The tool's template regen **did recur** — H1 doc restored-from-HEAD first,
  then the A2 Amendment appended; original + A1 text byte-untouched.

**New rubric sha256:** `480c15cff2face1ee4a2eb9536f3d2b9907a124ae9c6e86654b3100abd314007`

## 3. Downstream + universe assertion

- 5 manifests re-pinned to the new rubric hash (programmatically asserted).
- Transcription snapshots **byte-unchanged 5/5** (`b15cddc8… / 634066f3… /
  ee2cbe0f… / 0d604c07… / 19c0be81…`).
- 4 remaining skeletons (din/moran/omer/yonatan) regenerated **with M1
  headers** (`teacher_validated`, `blind: false`, both attributions);
  dan's obsolete skeleton retired (superseded by the real GT — disclosed).
- **Delta proof (old → new contract):** changed paths = exactly
  `6 × example_solution` + `contract_version` — nothing else. Universe:
  38 terminals/fixture, ids-only-unchanged; path-honesty guard green.

## 4. dan_basiuk GT — loader guard pass (verbatim)

sha256 stamped mechanically; `authored_at` left as `FILL_AT_COMMIT_ISO8601`
for the owner's commit; **zero judgment fields altered**.

```
loaded: fixture=dan_basiuk gt_source=teacher_validated blind=False
proposed_by='claude-fable-5 (design-partner session)' validated_by='Noam'
totality: 38/38 terminals (guard-verified exactly-once)
hash pin: gt.rubric_contract_hash == snapshot sha256 -> True
bounds + 0.25 grid: guard-verified on load (no exception raised)
gt_total via real selection_scoring:
  dan_basiuk: 83.5 / 100
GUARDS: ALL GREEN
```

Note: grade mode stays refused for dan until `authored_at` is stamped (the R1
sequencing check raises on the placeholder) — correct behavior, not a bug.

## 5. Pin re-anchors (deliberate, ruled-change class)

The H1-A2 content amendment legitimately moved the live-fixture render, so the
off-path byte pin was **split**: `RENDERER_SHA256` on a solution-stripped scope
— **reproduces the pre-seam hash `c575112f…` exactly, proving the renderer
never drifted** — plus `A2_CONTENT_SHA256 = 5b5d72a2…` on the live scope
(renderer + ratified content). Skeleton pin updated to the M1 header form.
Re-anchor protocol documented in the test: only on version-bumped renderer
changes or ratified content amendments, both RUNLOG-entried.

## 6. Batteries + ledger

Suite + eval_common + agents: **83 passed, 1 xfailed** · collect 84 · `import
app.main` clean · path-honesty guard green.

| Commit | Carries |
|---|---|
| `530fd7c` | the supersede: source artifact, new snapshot + H1+A1+A2 provenance, dan GT (sha256 stamped), dan skeleton retired, 4 M1 skeletons, 5 manifests, tool + suite pins, H1-A2 amendment, ONBOARDING §5b + RUNLOG |
| `50d348a` | the byte-pin re-anchor (renderer pin + content pin, `tests/agents/`) |

**Provenance note (item 6, in ONBOARDING §5b + RUNLOG):** from H1-A2 onward,
compiled scopes carry model solutions — the baseline measures the grader
**with EXAMPLE SOLUTION rendered** (production-realistic; referent and SUT
symmetric). E4/prior_parts unaffected — flag off for baseline.

**State:** dan_basiuk needs only the owner's `authored_at` stamp; four
fixtures remain at [STOP] F5.
