#!/usr/bin/env bash
# =============================================================================
# check_goal.sh  —  the TRUSTWORTHY stop condition for the /goal loop.
#
# Place at:  vivi-codebase/backend/tests/transcription_eval_suit/check_goal.sh
# Make executable:  chmod +x tests/transcription_eval_suit/check_goal.sh
# =============================================================================
#
# WHAT "DONE" MEANS (and why each clause exists):
#
#   - mode = per_doc (END-TO-END / the SHIP GATE). Not a p2_only proxy. P1
#     perception is the dominant wall, so ONLY an end-to-end pass proves "done";
#     a p2_only pass says nothing about whether the real pipeline ships.
#   - k >= 5 repeats, and EVERY fixture passes the conjunctive gate on EVERY
#     repeat. The cheap P2 model is non-deterministic at temp 0 (it has produced
#     a swap on one run, a merge the next, a refusal the next, on identical
#     input). A single green run is NOISE. Stability across repeats is the
#     difference between "the fix worked" and "the model landed a lucky guess."
#   - VALIDITY BEFORE ACCURACY. Zero parse failures, zero truncation, coverage
#     1.0 everywhere. An INVALID doc (a MAX_TOKENS truncation, a parse failure,
#     a coverage<1.0 drop/merge) is NOT a passing doc — it is excluded, and an
#     excluded doc means the benchmark is not met. We do not average invalid
#     docs into a pass.
#   - THE INSTRUMENT IS THE PRIME SUSPECT. This script reads the per-record
#     gate results INDEPENDENTLY and then cross-checks the runner's own
#     aggregate. If they disagree, that is a measurement bug, not a result:
#     it halts with a distinct code so a human looks, rather than silently
#     trusting either number.
#
# This is the AUTHORITATIVE, EXPENSIVE gate. It runs a full k=5 end-to-end eval
# (~5 fixtures x 5 repeats of the P1+P2 pipeline; P1 is the slow, image-heavy,
# costly call). DO NOT spend it every iteration. Iterate with cheap p2_only
# diagnostics (per the playbooks); invoke this only when your cheap signal says
# the gate will likely pass, and as the FINAL WORD on whether the loop may stop.
#
# EXIT CODES:
#   0  TRUSTWORTHY PASS          -> the loop may stop. Benchmark genuinely met.
#   1  FAIL (validity OR accuracy)-> reasons printed; keep iterating (or surface).
#   2  INSTRUMENT DISAGREEMENT    -> HALT and surface to a human. Do not trust
#                                   the number until the harness is reconciled.
#   3  RUNNER / SETUP ERROR       -> the eval did not produce parseable output.
#
# OVERRIDABLE (env):
#   GOAL_REPEATS   (default 5)         minimum repeats; the stability bar
#   GOAL_CONFIG    (default v0)        runner config name
#   GOAL_EXAM_SPEC (default draft.json) exam spec passed to --exam-spec
#   GOAL_FIXTURES  (default: all)      comma-separated doc_ids; default = whole
#                                      benchmark. The STOP gate is the FULL
#                                      partition — you cannot "pass" by fixing a
#                                      subset while breaking the rest.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_DIR="$SCRIPT_DIR"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

REPEATS="${GOAL_REPEATS:-5}"
CONFIG="${GOAL_CONFIG:-v0}"
EXAM_SPEC="${GOAL_EXAM_SPEC:-draft.json}"
FIXTURES="${GOAL_FIXTURES:-}"

cd "$BACKEND_DIR"
export PYTHONPATH=.

echo "=============================================================="
echo " check_goal — authoritative end-to-end stop gate"
echo "   config=$CONFIG  mode=per_doc  repeats=$REPEATS  exam_spec=$EXAM_SPEC"
echo "   fixtures=${FIXTURES:-<all>}"
echo "   (this is the expensive, authoritative confirmation run)"
echo "=============================================================="

FIXTURE_ARG=()
if [ -n "$FIXTURES" ]; then
  FIXTURE_ARG=(--fixtures "$FIXTURES")
fi

# --- run the canonical k=N end-to-end eval; capture stdout to recover the dir ---
set +e
RUN_OUT="$(python -m tests.transcription_eval_suit.runner \
    --config "$CONFIG" --mode per_doc --exam-spec "$EXAM_SPEC" \
    --repeats "$REPEATS" "${FIXTURE_ARG[@]}" 2>&1)"
RUN_RC=$?
set -e
printf '%s\n' "$RUN_OUT"

if [ $RUN_RC -ne 0 ]; then
  echo "GOAL: FAIL (runner exited $RUN_RC — setup/runtime error, not a result)"
  exit 3
fi

# The runner prints 'Run complete -> <dir>'. Prefer that; fall back to newest dir.
RESULTS_DIR="$(printf '%s\n' "$RUN_OUT" | sed -n 's/^Run complete -> //p' | tail -1 || true)"
if [ -z "${RESULTS_DIR:-}" ] || [ ! -d "$RESULTS_DIR" ]; then
  RESULTS_DIR="$(ls -dt "$SUITE_DIR"/results/*/ 2>/dev/null | head -1 || true)"
fi
if [ -z "${RESULTS_DIR:-}" ] || [ ! -f "${RESULTS_DIR%/}/results.json" ]; then
  echo "GOAL: FAIL (no results.json produced — cannot verify)"
  exit 3
fi
echo "Verifying: ${RESULTS_DIR%/}/results.json"
echo "--------------------------------------------------------------"

# --- independent verification (validity-first, then accuracy, then cross-check) ---
set +e
python - "${RESULTS_DIR%/}" "$REPEATS" <<'PY'
import json, os, sys

results_dir = sys.argv[1]
min_repeats = int(sys.argv[2])
with open(os.path.join(results_dir, "results.json"), encoding="utf-8") as f:
    data = json.load(f)

records = data.get("records", [])
agg = data.get("aggregates", {})
mode = data.get("mode")

validity = []   # an INVALID doc/run cannot be part of a pass (prime directive #2)
accuracy = []   # a VALID doc/run that missed the conjunctive gate

if mode != "per_doc":
    validity.append(f"wrong mode '{mode}' — the stop gate must be per_doc (end-to-end)")
if not records:
    validity.append("no records — nothing ran")

by_doc = {}
for r in records:
    by_doc.setdefault(r["doc_id"], []).append(r)

# global validity
pf_total = agg.get("parse_failure_total")
if pf_total is None:
    validity.append("aggregates.parse_failure_total missing — cannot establish validity")
elif pf_total != 0:
    validity.append(f"parse_failure_total={pf_total} (truncation/parse failure present)")

# per-doc / per-repeat validity + accuracy
for doc, runs in sorted(by_doc.items()):
    if len(runs) < min_repeats:
        validity.append(
            f"{doc}: only {len(runs)} repeats (<{min_repeats}) — a single run is noise "
            f"under temp-0 non-determinism"
        )
    for r in runs:
        rep = r.get("repeat")
        e2e = r.get("e2e")
        if r.get("parse_failures"):
            validity.append(f"{doc} rep{rep}: parse_failures={r['parse_failures']}")
        if e2e is None:
            validity.append(f"{doc} rep{rep}: no e2e score (invalid)")
            continue
        cov = e2e.get("coverage")
        if cov is not None and cov < 1.0:
            # coverage<1.0 is the truncation/merge/drop signature — invalid as a pass.
            validity.append(f"{doc} rep{rep}: coverage={cov} < 1.0 (dropped/merged/truncated answer)")
        gate = e2e.get("gate", {}) or {}
        if not gate.get("passed", False):
            accuracy.append(f"{doc} rep{rep}: GATE FAIL {gate.get('reasons', [])}")

valid_clean = (len(validity) == 0)
accuracy_clean = (len(accuracy) == 0)

def emit(reasons, header):
    print(header)
    for x in reasons:
        print(f"  - {x}")

# Validity gates everything: if any doc is invalid, we do not even claim accuracy.
if not valid_clean:
    emit(validity, "VALIDITY FAILURES (these are excluded — an excluded doc is not a pass):")
    if accuracy:
        emit(accuracy, "ACCURACY FAILURES (secondary — validity already blocks the pass):")
    print("VERDICT: GOAL: FAIL")
    sys.exit(1)

if not accuracy_clean:
    emit(accuracy, "ACCURACY FAILURES (valid docs that missed the conjunctive gate):")
    print("VERDICT: GOAL: FAIL")
    sys.exit(1)

# Both clean by our INDEPENDENT read. Now demand the runner's own aggregate agrees.
agg_pass = agg.get("accuracy_gate_pass_all_docs")
if agg_pass is not True:
    print("INSTRUMENT DISAGREEMENT:")
    print(f"  - independent per-record read = PASS")
    print(f"  - runner aggregate accuracy_gate_pass_all_docs = {agg_pass!r}")
    print("  This is a measurement bug, not a result. Halt and surface to a human")
    print("  before trusting any number from this harness.")
    print("VERDICT: GOAL: INSTRUMENT-DISAGREEMENT")
    sys.exit(2)

n_docs = len(by_doc)
print(f"All {n_docs} fixtures pass the conjunctive end-to-end gate on all {min_repeats} repeats.")
print("Validity clean: 0 parse failures, coverage 1.0 everywhere, no truncation.")
print("Independent read and runner aggregate AGREE.")
print("VERDICT: GOAL: PASS")
sys.exit(0)
PY
VERDICT_RC=$?
set -e
exit $VERDICT_RC
