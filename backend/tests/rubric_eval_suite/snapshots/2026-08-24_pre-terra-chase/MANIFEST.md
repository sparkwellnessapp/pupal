# Rollback snapshot — 2026-08-24, taken BEFORE the terra-high chase

Owner-ordered (Noam, 2026-08-24): before iterating on terra-high, freeze a complete,
restorable picture of the configuration that produced the P-M56 sweep, so any change
made during the chase can be reverted in one step.

## What this pins

| Item | Value at snapshot time |
|---|---|
| `EXTRACTION_PROMPT_VERSION` | **3.7.0-tabledir** |
| `PIPELINE_VERSION` | **3.6.2** |
| prompt length | 22,890 chars (`EXTRACTION_SYSTEM_PROMPT.txt`, verbatim) |
| `suite_hash` | **19607f69e6bc3432** (every P-M56 run, baseline included) |
| registry `AS_OF` | 2026-08-15 (+ gpt-5.6-terra/-sol added 2026-08-23) |
| prod pin (CLAUDE.md D-2) | openai / gpt-5.5 / medium / 32000 |
| git HEAD | see `git_head.txt` (the eval tree is working-tree state; `backend/.gitignore` line 164 ignores `*.json`, so configs and benchmarks are UNTRACKED — that is why they are copied here in full) |

## Reference runs this configuration produced

- `results/20260823-191643_prod_gpt55` — gpt-5.5 @ medium, k=3 — **12/15**,
  headline 183.8s, $0.2069/doc like-for-like. THE baseline.
- `results/20260823-201145_gpt-5.6-terra-high` — terra @ high, k=3 — **10/15**
  (bagrut 1/3, hobby 0/3). The chase's starting point.

## Files

- `EXTRACTION_SYSTEM_PROMPT.txt` — the exact prompt string, extracted from the live
  module (not hand-copied). Diff a future prompt against THIS to see one change.
- `pipeline.py.snapshot` / `parser_render.py.snapshot` / `models_registry.py.snapshot`
  — full file copies. **`.snapshot` suffix is deliberate**: `_suite_hash` globs
  `suite_dir.rglob("*.py")`, so a `.py` here would silently shift the suite hash and
  make the chase incomparable to its own baseline; it also keeps pytest from
  collecting them and keeps greps for "the pipeline" honest.
- `configs/*.json` — all 16 configs as they stood.
- `pipeline_vs_HEAD.patch` — working tree vs git HEAD for pipeline.py.

## Restore (one step)

```bash
cd backend
cp tests/rubric_eval_suite/snapshots/2026-08-24_pre-terra-chase/pipeline.py.snapshot \
   app/services/docx_v3/pipeline.py
cp tests/rubric_eval_suite/snapshots/2026-08-24_pre-terra-chase/parser_render.py.snapshot \
   app/services/docx_v3/parser_render.py
cp tests/rubric_eval_suite/snapshots/2026-08-24_pre-terra-chase/models_registry.py.snapshot \
   tests/eval_common/models_registry.py
cp tests/rubric_eval_suite/snapshots/2026-08-24_pre-terra-chase/configs/*.json \
   tests/rubric_eval_suite/configs/
# verify: prompt version back to 3.7.0-tabledir, suite_hash back to 19607f69e6bc3432
PYTHONUTF8=1 PYTHONPATH=. python -c "import app.services.docx_v3.pipeline as p; print(p.EXTRACTION_PROMPT_VERSION, p.PIPELINE_VERSION)"
PYTHONUTF8=1 PYTHONPATH=. python -c "from tests.rubric_eval_suite.runner import _suite_hash,SUITE_DIR; print(_suite_hash(SUITE_DIR))"
PYTHONUTF8=1 PYTHONPATH=. python -m pytest tests/rubric_eval_suite/ tests/eval_common/ -q
```

Restoring the prompt restores `EXTRACTION_PROMPT_VERSION` with it — the version constant
lives next to the prompt text by design, so a rollback can never leave a stale stamp.
