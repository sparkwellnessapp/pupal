# PHASE B CLOSEOUT — five GTs verified · HOLD at P2 (2026-08-26)

**Zero spend · zero `app/` changes · zero Gemini · §13 read as context only, nothing built · E5 not implemented (deferred per ruling).**

---

## 1. dan_basiuk version check — GREEN

| Check | Result |
|---|---|
| `q2.ב.c3.s2` awarded | **`"2"`** (AUDIT-2 correction present; note cites the revised PL-10) |
| Total via real `selection_scoring` | **84.0 / 100** — not the pre-audit 83.5 |

**The corrected file is in place.** No STOP on item 1.

## 2. Five-fixture guard suite — ALL GREEN

Every fixture loaded through `load_bundle(..., require_gt=True)`, which raises on any guard failure:

| fixture | totality | bounds | 0.25 grid | D5 hash pin | M1 provenance | `_instructions` |
|---|---|---|---|---|---|---|
| din_ezra | 38/38 | OK | OK | OK | OK | removed |
| dan_basiuk | 38/38 | OK | OK | OK | OK | removed |
| omer_gelber | 38/38 | OK | OK | OK | OK | removed |
| moran_aharon | 38/38 | OK | OK | OK | OK | removed |
| yonatan_basiuk | 38/38 | OK | OK | OK | OK | removed |

D5 pin is against `480c15cff2face1e…` (the H1-A2 ratified snapshot).
M1 = `teacher_validated` + `blind: false` + `proposed_by` + `validated_by`, all five.
**Terminal-id universes identical across all five** — a single 38-id universe.

> **One mechanical fix was required to get here, disclosed.** `dan_basiuk` and
> `din_ezra` still carried the literal `FILL_AT_COMMIT_H1A2_SHA256` placeholder
> (dan's stamped value was replaced when the AUDIT-2 correction was placed), so
> the D5 guard was **refusing both**. I stamped the live ratified hash into
> those two — precedented by the H1-A2 ruling (*"stamp the sha256 … (mechanical);
> leave authored_at for the owner"*) — and only after positive evidence each was
> authored against the A2 contract: both carry the H1-A1 path-honest
> `q2.ג.c0.s*` ids, and din's notes cite the model solutions (R-β, PL-*).
> moran/omer/yonatan already carried the correct hash. **No judgment field was
> touched in any file.**

## 3. Corpus totals — via real `selection_scoring`, all match

| fixture | total | expected | verdict | `evidence_exists=false` | `ungradable_scopes` |
|---|---|---|---|---|---|
| din_ezra | **55.5** / 100 | 55.5 | MATCH | 8 | 0 |
| dan_basiuk | **84.0** / 100 | 84.0 | MATCH | 3 | 0 |
| omer_gelber | **89.0** / 100 | 89 | MATCH | 2 | 0 |
| moran_aharon | **92** / 100 | 92 | MATCH | 1 | 0 |
| yonatan_basiuk | **92.5** / 100 | 92.5 | MATCH | 1 | 0 |

Compared under **Decimal equality** — `89.0` and `89` differ only in Decimal
string form and are numerically equal (my first pass compared strings and
falsely flagged omer; corrected). Denominator is `contract.total_points = 100`
throughout, never re-derived. **`ungradable_scopes` is empty in all five** —
C-2 unexercised in this exam (registered as a gap, §5).

## 4. R1 mechanics — **STOP: Phase-B exit condition NOT met**

`authored_at` is **`"FILL_AT_COMMIT_ISO8601"` in all five GT files**, so
`assert_blind_sequencing` refuses grade mode for every fixture:

```
dan_basiuk       R1 sequencing: REFUSED -> GTValidationError: GT authored_at
                 'FILL_AT_COMMIT_ISO8601' is not ISO-8601
din_ezra         REFUSED (same)   moran_aharon  REFUSED (same)
omer_gelber      REFUSED (same)   yonatan_basiuk REFUSED (same)
cached draft runs on disk: results/ does not exist (no drafts)
```

**This is not a blindness violation** — zero cached drafts exist, so the
sequencing check has nothing adverse to find. It is purely the unstamped
anchor. **The stamp is yours by ruling:** `authored_at` is the R1 provenance
claim about when you authored, and an agent-invented timestamp would fabricate
provenance. I did not stamp it. **One owner commit stamping `authored_at`
across the five files flips grade mode from refused to permitted for all
five** — that is the Phase-B exit condition, and it is the only thing standing
between here and C2.

## 5. Corpus gaps registered (item 6 — findings, no action)

Added to ONBOARDING's seed-gap register:

| Gap | Consequence | First expansion |
|---|---|---|
| **No tabular answer** | **C-1's ratified table-interpretation clause ships UNTESTED** — zero `[C1-TABLE]` coverage | expansion must include a **trace-table answer** |
| **No illegible scope** | **C-2's ratified `ungradable` path ships UNTESTED** — reason vocabulary, totals-only participation, and the Tier-1 ungradable tripwire have synthetic-guard coverage only | expansion must include one **genuinely illegible scope** |

## 6. New: corpus pin (disclosed addition)

`test_corpus_totals_via_real_selection_scoring` makes this closeout permanent —
it loads all five through the guards, asserts the five totals through the real
`selection_scoring`, asserts the 38-id universe identity and M1 provenance.
Any silent GT edit now moves a total and reds. Re-anchor only on an
owner-ratified GT amendment, RUNLOG-entried — never to make a number pass
(same discipline as the byte pins).

## 7. Batteries + ledger

| Gate | Result |
|---|---|
| grading suite + eval_common + agents | **84 passed, 1 xfailed** (the D5 sonnet sentinel) |
| collect-only | 85 collected |
| transcription | 134 passed / 1 skipped — baseline-identical |
| `import app.main` | clean |

Commit: **`e1e8010`** — two hash stamps, corpus pin, ONBOARDING gaps, RUNLOG.

---

## HOLDING AT P2

No spend. The pre-baseline prediction (owner + reviewer) must land in
`PREDICTIONS.md` before C2. When it does — and once `authored_at` is stamped —
C2 runs unchanged: **k=5 × 5 fixtures, deployed pin, `prior_context` OFF, ~$1**,
doubling as the U2/G-21 multi-scope smoke. The baseline report will lead with
**validity**, then **worst test**, then **≥2 hand-read terminal tables**, then
**Tier-2 distributions**, then the **R6 escalation check**.
