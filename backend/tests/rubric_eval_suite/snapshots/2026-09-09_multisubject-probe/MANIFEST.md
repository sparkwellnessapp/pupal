# REAL-PROVIDER SNAPSHOT — the OMML + bands probe (Phase 4a's pinned benchmark)

**A snapshot, not ground truth.** The recorded run that turns the probe's band table into three
criteria, kept so `tests/subjects/test_omml_bands_probe.py` can assert against it without calling a
provider. Hand-ratified goldens live in `../../benchmarks/`; this is not one.

## The fixture

`tests/rubric_eval_suite/fixtures/probes/omml_bands_probe.docx` — a small synthetic probe carrying
the two things the plan wanted pinned together:

* **an OMML equation** (a limit, «חשבו את הגבול»), for P-3: an equation in a typed rubric must
  never be silently dropped;
* **a three-row band table** whose top bands are **10 / 6 / 4** (each row reads `מלא / חלקי / חסר`
  against `10 / 5 / 0`, `6 / 3 / 0`, `4 / 2 / 0`).

## The run

`gpt-5.6-terra` / high, subject **english**, prompt `3.10.0-fixsource+english`, render stage
`docx_text`, **0 retries**.

| claim | result |
|---|---|
| each ladder flattens to ONE criterion at its top band | **10 / 6 / 4** — three criteria, not nine |
| the rubric total is the document's own | **20**, `compile OK total=20.0` |
| the question type is the profile default, never CS | `short_answer` |
| an equation is never dropped (P-3) | `omml_seen == omml_rendered == 1` |
| the ladder stays legible to the teacher | every description keeps `מלא / חלקי / חסר` |

## Why this is pinned in two halves

A provider result cannot be asserted inside a unit test. So the DETERMINISTIC half — the DOCX
renders with its equation intact and its band table present — is checked live against the fixture
on every run, and the PROVIDER half is asserted against this recorded summary. A change in the
flattening rule then shows up as a diff against a stored artefact rather than as somebody's memory
of what the extraction used to do.

Note what the probe does NOT show: its points cell is a single `10 / 5 / 0` string rather than a
column per band, so the criterion description keeps the band NAMES but not a per-band number. The
per-band numbers are exercised by the ministry rubric
(`../2026-09-09_multisubject-ministry-fg/`), where each band has its own column.
