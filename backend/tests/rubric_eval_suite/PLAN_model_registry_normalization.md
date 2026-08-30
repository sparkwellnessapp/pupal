# PLAN — Normalize the rubric eval suite's model interface onto the transcription suite's `models_registry` design

**Status:** ✅ IMPLEMENTED 2026-08-23, under these owner rulings (Noam, 2026-08-23):
- **D2 — moot:** the Vertex serving-surface A/B is shipped and closed; no sequencing hold.
- **D1 — approved:** shared home `tests/eval_common/`; transcription file → re-export shim.
- **D8 — amended:** $2.00 rejected as too high; **$1.00** for `prod_gpt55.json` **and the
  other gpt-5.5 configs** (`gpt-5.5.json`, `gpt-5.5-low.json`). Non-openai sweep configs
  keep $2.00 (the ruling named only the gpt-5.5 configs — flagged as an interpretation).
- All other decisions executed on their stated recommendations; D11 taken as the
  minimal repair (retarget `v0_p2_correct_spec.json` to `gpt-5.4-nano-2026-03-17` — the
  config was already broken: its old key would `KeyError` at use).
- **§9 added post-approval:** the fixture-base-expansion analysis the owner requested.

**Written:** 2026-08-21 · **Branch:** `perf/rubric-extraction-latency`
**Scope:** `backend/tests/rubric_eval_suite/` (adopter) + `backend/tests/transcription_eval_suit/models_registry.py` (donor) + a new shared home.
**Explicitly out of scope:** `app/services/docx_v3/pipeline.py` behaviour, `scoring.py`, `gates.py` thresholds, any ground truth, any prompt.

---

## 0. Executive summary

The transcription suite resolves a model through **one registry keyed by a stable
`model_key`**: `spec(key) -> ModelSpec(key, provider, model_id, price: PriceCard,
supports_logprobs, supports_json_schema, tier)`. Configs name only the key; the
registry owns identity + price + capability + tier; `AS_OF` stamps the price
vintage; an unknown key raises immediately with the known-key list.

The rubric suite has **no registry**. Each `configs/*.json` re-declares the model
string, the provider string, and its own two price scalars. That is one concept in
seven places (CLAUDE.md §0.4), and it has already produced four concrete defects
(§2). This plan replaces the rubric suite's per-config model/price block with a
single `model_key` resolved through the **same registry object** the transcription
suite uses, so a model's identity, price and tier are one fact across both suites
and every run of either suite stamps the same vocabulary.

**Net effect on the stated goal** — per-model metrics across suites: `model_key`
becomes a join key valid in both `results.json` families; cost is computed by one
function from one price card (cached-input included); `tier`, `provider`,
`model_id` and `registry_as_of` are stamped identically in both.

**Three things the reader must decide before implementation starts** — §4 D1
(where the shared registry lives), D2 (sequencing against the *currently open*
Vertex A/B in the transcription suite), D8 (`prod_gpt55.json` will start failing a
cost gate that has never once been enforced). Everything else has a recommendation
and can proceed on it.

---

## 1. The two designs, as they actually are

### 1.1 Transcription (the target design) — verified by reading

`tests/transcription_eval_suit/models_registry.py` (12 entries, `AS_OF = "2026-08-15"`):

| Property | Where it lives | Consequence |
|---|---|---|
| `key` | the registry key; also the string configs and `CallRecord.model_key` use | one vocabulary from config → call record → results.json |
| `provider` | adapter/scheduler name (`openai`\|`anthropic`\|`gemini`) | `make_default_pipeline` selects the adapter class by it |
| `model_id` | the string handed to the SDK — **deliberately allowed to differ from `key`** (`claude-haiku-4.5`→`claude-haiku-4-5`, `chatgpt-4o-mini`→`gpt-4o-mini`) | a vendor id rename never breaks a config or a historical comparison |
| `price: PriceCard` | `in_per_mtok`, `out_per_mtok`, `cached_in_per_mtok\|None` | `cost_usd(usage, card)` in `two_phase/instrument.py` is the ONE cost formula |
| `supports_logprobs`, `supports_json_schema` | capability facts | consumed by the pipeline/adapters |
| `tier` | `"cheap"` \| `"frontier"` | sweep role labelling |
| `AS_OF` | module constant | stamped into `results.json` as `registry_as_of` |
| `spec(key)` | raises `KeyError("Unknown model key …. Known: […]. Registry as of …")` | a typo fails before any API call |

Structural seam: `two_phase/pipeline.py` declares `class ResolvedModel(Protocol)`
needing only `key/provider/model_id/price/supports_json_schema`. `ModelSpec`
satisfies it structurally; production passes its own narrow `_Model` map. **The
registry is deliberately eval-side** — `app/services/transcription/two_phase/__init__.py`
states it in as many words: *"The eval-only pieces (ground truths, scoring, gate,
model registry/prices, runner) stay in the suite."* That ruling constrains D1.

### 1.2 Rubric (the current design) — verified by reading

There is no registry. `configs/<name>.json` carries `model`, `provider`,
`price_per_1m_input`, `price_per_1m_output` alongside the genuine experiment knobs
(`max_output_tokens`, `reasoning_effort`, `cost_ceiling`, `notes`).
`runner._config_env_overrides` maps four config fields onto four `EXTRACTION_LLM_*`
env vars; `app/services/docx_v3/pipeline._get_llm_config()` reads them back.
`runner.produce_predicted` multiplies raw token counts by the two config scalars.

The env hop is **not** an accident to be removed: the docx_v3 pipeline resolves its
model from process env, where the two-phase pipeline takes an injected
`resolve_model`. So the rubric analogue of `make_default_pipeline` is "resolve the
key, then set `EXTRACTION_LLM_MODEL=spec.model_id` / `EXTRACTION_LLM_PROVIDER=spec.provider`."
The registry replaces *where the identity comes from*, not *how it is delivered*.

Every config's model already resolves against the existing registry — verified:

```
claude-sonnet-4-6.json       -> claude-sonnet-4-6        anthropic  3.00/15.00   (config: 3.0/15.0)   MATCH
default.json                 -> gpt-4o                   openai     2.50/10.00   (config: no prices)
gemini-3.1-pro-preview.json  -> gemini-3.1-pro-preview   gemini     2.00/12.00   (config: 2.0/12.0)   MATCH
gpt-5.5.json / -low / prod   -> gpt-5.5                  openai     5.00/30.00   (config: 5.0/30.0)   MATCH
grok-4.6.json                -> (ABSENT — provider 'xai' is not in the registry)
```

Only one model must be added (`grok-4.6`) and only one provider name is new (`xai`).
Where both sides declare a price, **they already agree exactly** — so the migration
is price-neutral by construction for those four configs.

---

## 2. The defects this removes (evidence, not speculation)

**F1 — The cost gate is silently disabled for any config without prices.**
`gates.py:43` runs the cost check only `if rs.cost_usd is not None`, and
`runner.py:200` produces `None` when either price scalar is absent. `default.json`
and `prod_gpt55.json` carry no prices, so their `cost_ceiling: 0.40` has **never
been enforced**. A registry gives every model a price, so a completed extraction
always has a cost, and the `None` branch is reachable only for a crashed trial —
which `valid=False` already fails.

**F2 — `provider` is optional, so identity can leak from ambient env.**
`default.json` has no `provider` key; `_config_env_overrides` skips absent fields
(correctly — it must not clobber ambient env with `"None"`), so
`EXTRACTION_LLM_PROVIDER` keeps whatever the process had.
`_get_llm_config()` then defaults to `"openai"`. Benign *today* only because
`backend/.env` sets no `EXTRACTION_LLM_*` at all (verified). It nonetheless
contradicts the suite's own stated rule (`runner.py:142-145`: *"every experimental
variable travels through [the config] — never ambient environment"*). Registry
resolution makes provider always explicit.

**F3 — A model typo is discovered by a provider 4xx, not by the harness.**
`config["model"]` is passed through verbatim as the SDK id; nothing validates it.
The transcription registry's loud `KeyError` is exactly the property to import.
The same gap already bit the *donor* suite: `configs/v0_p2_correct_spec.json` pins
`"gpt-5.4-nano"`, which is not a registry key (the real key is
`gpt-5.4-nano-2026-03-17`). It would `KeyError` on use — see D11.

**F4 — Cached input tokens are measured and then thrown away.**
`ExtractionMetrics.cached_tokens` is populated from
`usage.input_token_details.cache_read` (`pipeline.py:1060`) and never used; the
rubric cost formula bills 100% of input at the uncached rate. `PriceCard` +
`cost_usd()` handle it correctly. **Measured impact today: zero** — the one
persisted trace (`results/20260725-152851_gpt-5.5/traces/csharp_plane_combine_r0.jsonl`)
records `cached_tokens: 0`, so historical cost numbers stay comparable (§6.3).
Future runs get honest cost when caching does engage.

**F5 (found, NOT fixed here) — Tier-B pedagogical adjudication is invisible to cost.**
`_make_adjudicator` builds `….with_structured_output(QuestionAdjudication)` with
**no `include_raw=True`** (`pipeline.py:1023`), where Step 1 uses
`include_raw=True` (`pipeline.py:1111`). Usage metadata is discarded at the
LangChain boundary, so every rubric cost number in every historical run
under-reports by the whole Tier-B spend. This is a **pipeline** defect, not a
registry defect. It is recorded here because it is the strongest argument for the
follow-up in §7.1 (per-call `CallRecord` parity), and because anyone comparing
rubric $/doc against transcription $/doc must know the rubric number is a lower bound.

---

## 3. Target design

### 3.1 One registry, one key vocabulary

```
tests/eval_common/models_registry.py      # THE registry (moved, +grok-4.6)
    AS_OF, ModelSpec, MODELS, spec()
tests/transcription_eval_suit/models_registry.py
    -> re-export shim (the suite's own established idiom: instrument.py,
       keys.py, prompts.py, parsing.py, corrector.py are all exactly this)
tests/rubric_eval_suite/runner.py
    -> from tests.eval_common.models_registry import AS_OF, spec
```

`ModelSpec` is **unchanged in shape**. Only the `tier` docstring is rewritten
(D3) and one entry is added (D4).

### 3.2 The rubric config schema, after

```jsonc
{
  "model_key": "gpt-5.5",           // THE registry handle — identity+price+tier live there
  "max_output_tokens": 40000,       // experiment knob
  "reasoning_effort": "medium",     // experiment knob (designated sweep variable)
  "cost_ceiling": 2.0,              // this suite's economics
  "notes": "…"                      // the experiment record
}
```

Removed: `model`, `provider`, `price_per_1m_input`, `price_per_1m_output`
(now registry-owned) and `temperature`, `pipeline_version` (dead — D7).

**Division of responsibility, restated** (this replaces the sentence in
`ONBOARDING.md` §7 and `RUBRIC_EVAL_PLAYBOOK.md` ~line 205):

> the PIPELINE measures tokens; the **REGISTRY** owns identity and the price card;
> the RUNNER converts tokens → dollars through the one shared `cost_usd`; the GATE
> judges dollars against the config's `cost_ceiling`.

### 3.3 Cost: one formula, zero new arithmetic

The rubric runner does **not** get its own cost function. It adapts at the edge
(CLAUDE.md §14 "convert at the edges only") and calls the shared one:

```python
from app.services.transcription.vlm_provider import Usage
from app.services.transcription.two_phase.instrument import cost_usd

usage = Usage(input_tokens=m.input_tokens,
              output_tokens=m.output_tokens,
              cached_input_tokens=m.cached_tokens or None)
cost = cost_usd(usage, spec.price)
```

`Usage` is a frozen 3-int dataclass; importing it pulls **no heavy dependency** —
measured: importing the registry chain takes 0.116 s and drags in no
`langchain`/`openai`/`PIL`/`pydantic`/`sqlalchemy`, so `score_only` stays
provider-free exactly as its docstring promises.

### 3.4 Provenance, after (what makes cross-suite tracking work)

`results.json.provenance` gains, mirroring the transcription runner's block:

```json
"model_key": "gpt-5.5",
"registry_as_of": "2026-08-15",
"models": { "gpt-5.5": { "model_id": "gpt-5.5", "provider": "openai",
                         "tier": "frontier",
                         "price": {"in_per_mtok": 5.0, "out_per_mtok": 30.0,
                                   "cached_in_per_mtok": 0.5} } }
```

This is what makes a run **self-describing after its config file is edited** — today
a config rewrite silently orphans every prior RUNLOG entry that names it.

Per-record (`RubricScore`, additive Optional fields, defaults `None`, the exact
pattern the Phase-0 latency instrument used): `model_key`, `tier`,
`cached_tokens`, `reasoning_tokens`.

> ⚠️ These are attached by the **RUNNER after scoring**, never by `scoring.py`.
> `scoring.py` is the immutable ruler (see the runner's own comment at
> `runner.py:321-325`); the latency instrument set that precedent and this follows it.

---

## 4. Open decisions — surface, don't decide (CLAUDE.md §0.2)

### D1 — Where does the shared registry live? **[decide before Phase 1]**

| Option | For | Against |
|---|---|---|
| **A (recommended)** `tests/eval_common/models_registry.py`; transcription's file becomes a re-export shim | one definition; neutral ownership; the shim idiom is already this repo's own (5 precedents in the donor suite); rubric-only models don't land in the transcription namespace | touches one transcription file (see D2) |
| B rubric imports `tests.transcription_eval_suit.models_registry` directly | zero new files | inverts ownership — the shared thing is owned by one consumer; every rubric-only model must be added to the *transcription* suite |
| C copy the registry into the rubric suite | zero coupling | recreates the split brain this plan exists to remove ✗ |
| D move it into `app/services/` | would also collapse the third copy (`two_phase_engine._MODELS`) | contradicts the explicit ruling in `two_phase/__init__.py` that the registry stays eval-side; puts eval-only models on a production import surface. **Filed as the §7.2 follow-up, not bundled.** |

**Recommendation: A.**

### D2 — Sequencing vs. the open Vertex A/B **[BLOCKING — owner call]**

`tests/transcription_eval_suit/PREREG_vertex_migration_2026-08-20.md` (written
**yesterday**) pre-registers an AI-Studio→Vertex A/B whose protocol says *"Source
code: **zero lines changed**"* and *"§5: No instrument change."* Evidence it is
**still open**: two `v0_p1_only` result dirs exist (`20260820_183006` and
`20260821_115501`, i.e. today) and `RUNLOG.md` has not been appended since
2026-08-19 — the arms are run, the verdict is unwritten.

Mitigating facts: the transcription suite computes **no `suite_hash`** (verified —
nothing to confound); `MODELS` is a key lookup, so *adding* an entry cannot change
any existing key's resolution; `models_registry.py` is not on the §17.7 STOP list
(that list names `scoring.py`, `critical_tokens.py`, `normalize.py`, the thresholds
and `check_goal.sh`). But PREREG sub-prediction #3 is about `cost_avg_per_doc_usd`,
which the registry's prices produce.

**Options:** (a) hold Phase 1 until the Vertex verdict is in RUNLOG — cleanest,
costs a day; (b) proceed, proving inertness with a byte-identity snapshot test over
the pre-existing entries plus the full green battery. **Recommendation: (a) hold
Phase 1 until the A/B is written up**; if work must start immediately, run Phase 2
against option D1-B as a documented, time-boxed bridge and do the move afterwards.

### D3 — What does `tier` mean once two suites share it? **[decide before Phase 1]**

Today's docstring defines it in transcription economics: *cheap* = the v0 default
conjecture under a **$0.05–$0.08/doc** gate; *frontier* = accuracy ceiling
reference. The rubric suite's ceilings are **$0.40–$2.00/doc**. One label cannot
carry both economics.

**Recommendation:** redefine `tier` as **vendor positioning** — `"cheap"` = the
vendor's small/economy line, `"frontier"` = the vendor's flagship line — which
every current entry already satisfies, and state that *each suite's economics live
in its own cost ceiling, never in `tier`*. The transcription-specific seed-set
rationale moves down into a comment on the seed entries.

### D4 — The `grok-4.6` entry **[decide before Phase 1]**

Proposed, sourced from `configs/grok-4.6.json`'s own notes (xAI pricing page,
2026-08-15 — the same date as `AS_OF`, so **`AS_OF` does not move**):

```python
"grok-4.6": ModelSpec(
    key="grok-4.6", provider="xai", model_id="grok-4.6",
    price=PriceCard(in_per_mtok=2.00, out_per_mtok=6.00),   # <=200K-context tier
    supports_logprobs=False,        # UNVERIFIED -> recorded conservatively
    supports_json_schema=True,      # verified: 10/10 valid records, run 20260815-185359
    tier="frontier",                # xAI's flagship reasoning line (D3 semantics)
),
```

`cached_in_per_mtok` is deliberately **omitted** (`None` ⇒ falls back to the
uncached rate). xAI lists a $0.50 cached-input rate, but whether LangChain
populates `input_token_details.cache_read` for the streamed x.ai path is
unverified, and the config's own note already frames its cost as *"a conservative
upper bound."* Omitting cannot under-report. **Convention to add to the module
docstring: an unverified capability is recorded in the direction that cannot cause
a bad call.**

### D5 — `claude-sonnet-4-6` has `cached_in_per_mtok=3.75 > in_per_mtok=3.00`

That is the shape of a cache **write** rate (1.25× input), not a cache **read**
rate, and `cost_usd()` applies it to `cached_input_tokens`, i.e. reads. If correct
as written, a cached read costs 25% *more* than an uncached one — which no vendor
prices. **Do not silently "fix" a price** (that is the §17.7 class of change).
**Recommendation:** owner verifies against the Anthropic pricing page; the
registry test `cached_in <= in_per_mtok` (§5.9) ships **only after** it is resolved,
and until then is marked `xfail` carrying this decision id in the reason string.
Blast radius today: sonnet is a frontier reference in the transcription suite and
a *rubric* sweep config whose runs record `cached_tokens=0` — so no historical
number moves either way.

### D6 — Config migration: hard cutover or dual-read?

**Recommendation: hard cutover with a loud failure.** `model_key` required;
presence of any of `model` / `provider` / `price_per_1m_input` /
`price_per_1m_output` raises with a one-line migration message. A silent fallback
to config-owned prices would rebuild the split brain the moment someone copies an
old config. Seven files, all in-repo, all rewritten in the same commit; no external
consumer reads these files (verified by grep across `backend/`).

### D7 — Dead config fields: `temperature`, `pipeline_version`

`temperature` is read by **nothing** — `_config_env_overrides` does not map it and
`_llm_params` hardcodes the per-family policy. `gpt-5.5.json`'s `"temperature": null`
documents the *policy*, not a knob. `pipeline_version` is `null` in every config and
serves only as a legacy fallback behind the run-stamped value.
**Recommendation: delete both**; a config field that does nothing is a false entry
in the experiment record. (Anyone wanting a real temperature knob must add it to
`_llm_params` — a production policy change with its own exact-dict test.)

### D8 — Two configs get a cost gate they have never had **[decide before Phase 2]**

| config | ceiling | measured worst-doc cost at registry prices | verdict after migration |
|---|---|---|---|
| `default.json` (gpt-4o, 2.50/10.00) | $0.40 | ≈$0.19 upper bound from the largest observed token counts (18,968 in / 13,546 out); gpt-4o emits no reasoning tokens, so realistically far lower | **safe**, ~2× headroom |
| `prod_gpt55.json` (gpt-5.5, 5.00/30.00) | $0.40 | **$0.50122** — a real record from `20260726-144104_gpt-5.5` (bagrut_899371) | **would FAIL the cost gate** |

`prod_gpt55.json`'s `0.40` was inherited from the gpt-4o baseline and, because that
file has no prices, was never once evaluated. **Recommendation:** raise it to
`2.00` to match the other gpt-5.5 configs (the sweep-phase pathology ceiling), and
record it in RUNLOG as a ceiling correction, not a gate weakening — the alternative
(leave `0.40` and accept a permanent cost failure on every bagrut trial) trains
exactly the click-through reflex CLAUDE.md §5 warns about.
**This is a gate-semantics change and must not be made silently.**

### D9 — A `reasoning_family` capability field: CONSIDERED, DEFERRED

`_llm_params` detects the reasoning family by string prefix
(`gpt-5`/`o1`/`o3`/`o4`), which is why `grok-4.6` needed a whole separate `xai`
branch to get the same temperature-omission behaviour. A registry `family` fact
would be the better encoding. **Deferred**, because: (a) no current config sets
`reasoning_effort` on a non-reasoning model, so the validation it would enable has
no work to do (YAGNI); (b) it duplicates a *production* policy pinned by an
exact-dict test — changing it belongs in its own PR. Filed as §7.3.

### D10 — The Windows `charmap` bug in the file we are rewriting

`test_llm_policy.py:103` calls `gt_path.read_text()` with no `encoding=`, so
`test_truncation_guard_per_provider` fails on Windows (cp1252). It is BACKLOG
**Family D** (9 tests: 8 in `test_pedagogical.py` + this one).
**Recommendation:** fix this one line as part of Phase 3 (we are rewriting its
neighbours anyway) and leave `test_pedagogical.py`'s 8 to a separate Family-D
commit — bundling an unrelated file violates one-change-per-commit. The same file
also uses CWD-relative `Path("tests/rubric_eval_suite/...")`; switch to
`Path(__file__).parent` while there.

### D11 — The donor suite's stale config key

`transcription_eval_suit/configs/v0_p2_correct_spec.json` pins `"gpt-5.4-nano"`,
absent from `MODELS`. The §5.9 "every config key resolves" test will red-line it on
day one. **Recommendation:** owner picks — retarget to
`gpt-5.4-nano-2026-03-17`, or delete the config (its `correction_policy: "spec"`
experiment is historical). Do not let the new test ship without this resolved; a
knowingly-red test is worse than no test.

---

## 5. Implementation — phase by phase, file by file

### Phase 1 — the shared registry (gated on D1, D2, D3, D4)

1. **NEW** `backend/tests/eval_common/__init__.py` — docstring only: *"Code shared
   by the eval suites (transcription + rubric). One definition of a model's
   identity, price, capability and tier."*
2. **NEW** `backend/tests/eval_common/models_registry.py` — the current module
   content **moved verbatim** (`AS_OF`, `ModelSpec`, `MODELS`, `spec`), with
   exactly three edits: the `tier` docstring per D3; the `grok-4.6` entry per D4;
   the unverified-capability convention sentence. `PriceCard` keeps coming from
   `app.services.transcription.two_phase.instrument` (verified light: no heavy
   imports).
3. **MODIFY** `backend/tests/transcription_eval_suit/models_registry.py` → a
   6-line re-export shim in the identical style as `instrument.py`/`keys.py`.
   `from .models_registry import AS_OF, spec as model_spec` in `runner.py` is
   untouched.
4. **MODIFY** `backend/tests/transcription_eval_suit/test_providers_and_scheduler.py::test_models_registry`
   — the assertion *"every provider has a cheap and a frontier entry"* becomes
   *"every **seed** provider (openai/anthropic/gemini) has both"*, with a comment
   that this is a transcription-suite v0 seed-set statement, not a registry
   invariant (xai has one entry; inventing a second xai model to satisfy a test
   would mean fabricating a price card).

**Phase-1 acceptance:** `pytest tests/transcription_eval_suit -q` returns exactly
the baseline **133 passed, 1 skipped**; plus a byte-identity snapshot assertion
that every pre-existing key resolves to an identical `ModelSpec` after the move.

### Phase 2 — the rubric suite adopts it

5. **MODIFY** all 7 `backend/tests/rubric_eval_suite/configs/*.json` to the §3.2
   schema. `notes` is preserved verbatim except for the now-false sentence
   *"Prices from the transcription-suite model registry, snapshotted here (config
   owns pricing)"* → *"Prices are registry-owned (`tests/eval_common/models_registry.py`)."*
   `prod_gpt55.json` ceiling per D8.
6. **MODIFY** `backend/tests/rubric_eval_suite/runner.py`:
   - `_load_config(name) -> dict` gains validation: require `model_key`; raise
     `SystemExit` naming the legacy keys if any are present (D6).
   - **NEW** `_resolve_model(config) -> ModelSpec` = `spec(config["model_key"])`;
     called once in `run()` so an unknown key fails **before** the fixture loop and
     before any spend.
   - `_config_env_overrides(config, spec) -> dict` — identity from the spec
     (`EXTRACTION_LLM_MODEL = spec.model_id`, `EXTRACTION_LLM_PROVIDER = spec.provider`,
     both **always** set — F2), knobs from the config (still skipping `None`/`""`
     so ambient values are never clobbered with `"None"`).
   - `produce_predicted(docx, config, spec, tracer=…)` — cost via §3.3.
     `meta` gains `model_key`, `tier`, `cached_tokens`, `reasoning_tokens`.
     `model_version` keeps its meaning (`m.llm_model or spec.model_id` — the
     provider-facing id), matching `CallRecord`'s "model_key is the registry key,
     not the provider-reported id".
   - `run()` — attach the four new fields to `rs` **after** `score_rubric`, in the
     block that already attaches the latency fields.
   - `provenance` — add `model_key`, `registry_as_of`, `models` (§3.4).
   - `_suite_hash()` — extend the hashed file list with the shared registry's path,
     with a comment: *the registry is now part of the instrument even though it
     lives outside `suite_dir`; without this a price change would be invisible to
     the drift signal.* **This flips `suite_hash` for every future run** — expected,
     announced in RUNLOG (§5.15).
7. **MODIFY** `backend/tests/rubric_eval_suite/schemas.py` — four additive Optional
   fields on `RubricScore` (`model_key`, `tier`, `cached_tokens`,
   `reasoning_tokens`), documented as runner-attached and `score_only`-absent.
   `slots=True` means a typo is an `AttributeError`, which is exactly why they must
   be declared rather than stuffed into a dict.
8. **UNCHANGED, deliberately:** `scoring.py`, `gates.py`, `reporting.py` logic,
   `normalize.py`, every benchmark, every fixture, and all of
   `app/services/docx_v3/`. The gate's arithmetic and thresholds do not move; only
   the *inputs* to `cost_usd` become registry-sourced.

### Phase 3 — tests

9. **NEW** `backend/tests/eval_common/test_models_registry.py` — the shared
   invariants, deliberately only the ones true for *any* consumer:
   - `MODELS[k].key == k` for every k (a self-consistency trap the current file
     could violate silently);
   - `spec("nope")` raises `KeyError` matching `"Unknown model key"`;
   - every price is `> 0`;
   - `cached_in_per_mtok <= in_per_mtok` where set — **ships `xfail` until D5**;
   - **every model key named by every config of BOTH suites resolves** (the
     F3/D11 tripwire; it reads both suites' config dirs);
   - the transcription shim re-exports the *same objects* (`is` identity), so the
     move cannot silently fork.
10. **MODIFY** `backend/tests/rubric_eval_suite/test_llm_policy.py`:
    - `test_sweep_configs_load_and_pair_prices` → **`test_sweep_configs_resolve_through_registry`**:
      each sweep config carries `model_key`; the key resolves; `provider`/prices
      come from the spec and match the pinned expectations
      (`gpt-5.5`→openai 5/30, `claude-sonnet-4-6`→anthropic 3/15,
      `gemini-3.1-pro-preview`→gemini 2/12, `grok-4.6`→xai 2/6); the legacy keys
      are **absent** (the anti-regression guard for the split brain);
      `reasoning_effort` stays shape-only, with its existing comment intact — it is
      a designated sweep variable and pinning its value would red the battery on
      every legitimate sweep.
    - `test_config_env_round_trip` → new two-argument signature; asserts identity
      comes from the spec — use a key whose `model_id` differs from the key
      (`chatgpt-4o-mini`→`gpt-4o-mini`) to prove we send the **id**, not the key.
    - **NEW `test_cost_parity_with_legacy_formula`** — the comparability proof, on a
      real historical record: `Usage(18968, 13546, None)` × `gpt-5.5`'s card must
      equal `0.50122`, the value `results/20260726-144104_gpt-5.5` recorded under
      the old formula. With `cached_input_tokens=0` the two formulas are
      algebraically identical; this pins it against future price/formula drift.
    - D10 encoding + `Path(__file__)` fixes.
11. Both suites' batteries green (§6).

### Phase 4 — documentation (non-optional; CLAUDE.md §16)

12. `ONBOARDING.md` — §5 tree line (`configs/` no longer holds prices), §6 variable
    table row (identity/prices move to the registry; the config keeps knobs +
    ceiling; drift signal = `registry_as_of` + `suite_hash`), §6 "Config knobs
    available", §7 cost division-of-responsibility (§3.2's restatement).
13. `RUBRIC_EVAL_PLAYBOOK.md` ~line 205 — same restatement.
14. `runner.py` docstrings at lines 111-128 and 141-151 — same.
15. `RUNLOG.md` — a `## CHANGE 2026-08-2x` entry in the established
    what/why/by/affects form, stating explicitly: instrument change (not a model
    variable); **`suite_hash` WILL shift** — this change announcing itself, not
    drift; the `prod_gpt55.json` ceiling correction (D8) and its rationale; the cost
    formula is now cached-aware but **numerically identical while `cached_tokens=0`**,
    with the parity test as the receipt; and F5 recorded as a known lower-bound on
    every rubric cost number, past and present.
16. `CLAUDE.md` — **no change required.** It does not describe the rubric suite's
    config schema. (§17 governs the transcription `/goal` loop only and is untouched.)
17. `BACKLOG.md` — add the §7 follow-ups; note Family D shrinks by one test.

---

## 6. Verification — what "done" means

### 6.1 Free, offline, and mandatory

| Gate | Baseline (measured 2026-08-21) | Required after |
|---|---|---|
| `pytest tests/transcription_eval_suit -q` | **133 passed, 1 skipped** | identical |
| `pytest tests/rubric_eval_suite -q` | **31 passed, 9 failed** (all 9 = BACKLOG Family D charmap) | ≥31 passed, **0 new** failures; 8 failed if D10 is taken |
| `python -c "import app.main"` | ok | ok (nothing under `app/` is touched) |
| `pytest --collect-only -q` | ok | ok |

### 6.2 The dry-resolve gate (free)

The §5.9 "every config key of both suites resolves" test *is* the dry run: it proves
all 7 rubric configs and all 9 transcription configs resolve, with zero API calls.
It replaces "run it and see."

### 6.3 The comparability proof (free)

`cost_usd(Usage(18968, 13546, None), gpt-5.5.price) == 0.50122` — the exact value
the legacy formula wrote for `bagrut_899371` in `20260726-144104_gpt-5.5`. Cached
tokens are 0 in the one persisted trace, so no historical cost number moves. **Cost
comparability across the migration is therefore proven, not assumed.**

### 6.4 The paid acceptance smoke (~$0.10, one run)

```
python -m tests.rubric_eval_suite.runner --config default --repeats 1 --only csharp_plane_combine
```

Confirms end-to-end that the env hop still delivers the right model
(`results.json.provenance.model_version == "gpt-4o"`), the new provenance block is
populated, `cost_usd` is non-null (F1 — for the first time on this config), and
`gate_pass` is unchanged versus a pre-migration `score_only` re-score of the same
prediction. **No k≥5 run is required**: this change moves no model, no prompt and
no scorer, so it has nothing to re-baseline.

### 6.5 What would falsify the plan

Any of these means stop and re-plan: `cost_usd` differs from the legacy value on a
`cached_tokens=0` record; a transcription test outside the D3-rescoped one changes
status; `suite_hash` fails to shift (meaning the registry was not actually hashed);
a rubric config resolves to a different `model_id` than the string it used to send.

---

## 7. Deliberately NOT in this plan (filed, not done)

1. **Per-call `CallRecord` parity for the rubric suite.** The transcription suite
   attributes cost per call, per phase, per model; the rubric suite has one
   cumulative `ExtractionMetrics`. Closing the gap requires instrumenting
   `app/services/docx_v3/pipeline.py` — including fixing **F5** (`include_raw=True`
   on the Tier-B adjudicator, `pipeline.py:1023`) so its tokens exist at all. This
   is the single highest-value follow-up for "per-model metrics", and it is a
   production change owed its own review.
2. **Collapsing `two_phase_engine._MODELS` (the third copy) into one registry.**
   Contradicts the standing ruling in `two_phase/__init__.py`; needs an owner
   decision about eval-only models on a production import surface (D1-D).
3. **A registry `family`/reasoning capability field** replacing
   `_is_openai_reasoning`'s prefix sniffing (D9).
4. **A cross-suite per-model rollup CLI** (`tests/eval_common/model_metrics.py`:
   scan both `results/` trees, group by `model_key`, emit cost/latency/gate rates).
   This is the *pay-off* of the shared key vocabulary and is genuinely useful — but
   it is a new capability, not a normalization, and belongs in its own change once
   both suites are stamping `model_key`.
5. **BACKLOG Family D's remaining 8 charmap tests** (`test_pedagogical.py`).

---

## 8. Rollback

Every phase is independently revertable and nothing is persisted outside the repo.
Phase 1 is a file move + a shim (revert = restore the file, delete `eval_common/`);
Phase 2 is confined to `configs/`, `runner.py` and `schemas.py` in one suite; no
database, no deployed service and no production code path is touched, and
`results/` history is append-only and read by nothing in this change.

---

## 9. Fixture-base expansion (owner P.S., 2026-08-23) — analysis + proposal

**Question asked:** does anything in this design make it harder to add fixtures —
in particular transcription fixtures graded under a *different* rubric?

**Answer: no — verified, not assumed.** This design touches model identity, price
and provenance only. Neither suite's fixture discovery moved a line:

- **Rubric suite:** `_discover` pairs `fixtures/<name>.docx` ↔ `benchmarks/<name>.json`
  by basename. Adding a fixture = drop two files, zero config, zero code. Unchanged.
- **Transcription suite:** fixtures resolve by basename from `raw_benchmarks/`,
  `draft_benchmarks/`, `pdfs/`. Unchanged (the only donor-suite diffs are the
  registry move, one test's seed-set rescope, and the D11 key repair).
- The registry itself is fixture-agnostic: a new fixture never touches it, and a
  new *model* never touches a fixture.

**The real constraint is pre-existing, and the P.S. names it exactly.** The
transcription runner binds ONE exam to the whole run, in two places:

1. **One global exam spec per run** — `RunPlan.exam_spec_path` → `load_spec()`
   ([runner.py:174-184](../transcription_eval_suit/runner.py#L174)) loads a single
   spec and passes it to *every* fixture; `check_goal.sh` hardcodes
   `GOAL_EXAM_SPEC=draft.json`. A fixture answering a different exam would be
   segmented against the wrong question skeleton.
2. **One hardcoded subject profile** — `JAVA_BAGRUT` is imported once and passed at
   all four scoring sites (runner.py:253/262/278/279). The critical-token metric
   for a different exam (different method names, different language) is meaningless
   under another exam's profile.

**Proposed design (B-30f — filed, not implemented; it edits the §17-governed /goal
suite, so it is plan-first and owner-gated):** extend the suite's own
convention-over-configuration idiom — the basename pairing that already resolves
three artifacts per `doc_id` — to the two exam-bound artifacts:

```
transcription_eval_suit/
  specs/<doc_id>.json         # per-fixture exam spec (canonical or rubric draft_json)
  raw_benchmarks/<doc_id>.md  # (existing)
  draft_benchmarks/<doc_id>.md
  pdfs/<doc_id>.pdf
```

- `resolve_fixtures` gains `exam_spec` on `Fixture`, resolved per doc_id:
  `specs/<doc_id>.json` if present, else the run-level `--exam-spec` (which becomes
  a *fallback/override*, preserving every existing invocation — `check_goal.sh`,
  the RUNLOG history, and all current fixtures work byte-identically with zero new
  files, because the fallback IS today's behavior).
- The subject profile becomes a property of the spec, not the runner: a small
  `profiles` registry in `critical_tokens.py` (`{"java_bagrut": JAVA_BAGRUT, ...}`)
  keyed by an optional `"profile"` field in the spec JSON, defaulting to
  `java_bagrut`. Same shape as the model registry: one place that rots, loud
  failure on an unknown key.
- Aggregation honesty: `results.json` records per-fixture `spec` + `profile` so a
  mixed-exam run self-describes; the conjunctive gate is already per-fixture, so
  no gate arithmetic changes.

Why this shape and not a manifest file: the suites' standing idiom is *basename
convention + loud failure on absence* (`resolve_fixtures` raises per-mode on any
missing artifact today). A central manifest would be a second registry of facts the
directory tree already states, and would need editing on every fixture add — the
exact friction the request is about removing.

**Cost of NOT doing it now:** zero for same-exam fixture adds (drop 3 files, as
today). It becomes due the day the first non-bagrut transcription fixture is
authored — which also requires new GT and possibly new critical-token rules, so it
lands naturally with that (owner-gated) work.
