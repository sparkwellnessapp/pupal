#!/usr/bin/env bash
#
# PR-1 deployed-prod-path E2E smoke test.
#
# Drives the DEPLOYED backend directly (no browser → no CORS): login →
# submit a real DOCX → poll the job → print result + provenance. This is the
# one path no unit test can cover: real Cloud Tasks enqueue → OIDC → the
# service's /internal/run handler → extraction on Cloud Run.
#
# Run from the backend dir so the default fixture path resolves:
#   cd vivi-codebase/backend
#   EMAIL='you@example.com' PASSWORD='...' bash deploy/e2e_extraction_smoke.sh
#
# Optional overrides: BASE, DOCX, POLL_SECONDS, MAX_WAIT.
set -euo pipefail

BASE="${BASE:-https://gradervision-backend-588558139818.europe-west1.run.app}"
EMAIL="${EMAIL:?set EMAIL to your teacher account email}"
PASSWORD="${PASSWORD:?set PASSWORD}"
DOCX="${DOCX:-tests/rubric_eval_suite/fixtures/csharp_plane_combine.docx}"
POLL_SECONDS="${POLL_SECONDS:-5}"
MAX_WAIT="${MAX_WAIT:-960}"   # 16 min — covers a worst-case ~8 min gpt-5.5 job
DOCX_CT="application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# python is the JSON tool (jq may be absent on Git Bash). `python` on Windows.
PY="${PY:-python}"
jval() { "$PY" -c "import sys,json;print(json.load(sys.stdin)$1)"; }

[ -f "$DOCX" ] || { echo "DOCX not found: $DOCX (run from the backend dir)"; exit 1; }

echo "==> Deployed backend: $BASE"
curl -fsS "$BASE/health" >/dev/null && echo "    health: OK"

echo "==> Login as $EMAIL"
LOGIN_BODY=$("$PY" -c "import json,os;print(json.dumps({'email':os.environ['EMAIL'],'password':os.environ['PASSWORD']}))")
TOKEN=$(curl -fsS -X POST "$BASE/api/v0/auth/login" \
          -H "Content-Type: application/json" -d "$LOGIN_BODY" | jval "['access_token']")
[ -n "$TOKEN" ] && echo "    token: acquired"

echo "==> Submit $DOCX"
SUBMIT=$(curl -fsS -X POST "$BASE/api/v0/rubrics/extraction-jobs/" \
           -H "Authorization: Bearer $TOKEN" \
           -F "file=@${DOCX};type=${DOCX_CT}" \
           -F "name=E2E smoke" -F "subject=computer_science" -F "locale=he-IL")
echo "    $SUBMIT"
JOB_ID=$(echo "$SUBMIT" | jval "['job_id']")
REUSED=$(echo "$SUBMIT" | jval "['reused']")
echo "    job_id=$JOB_ID reused=$REUSED"
[ "$REUSED" = "True" ] && echo "    (an active job for this exact file already existed — ADR-3 idempotent reuse)"

echo "==> Poll (extraction runs on Cloud Run; typically 1-8 min)"
elapsed=0
while :; do
  ST=$(curl -fsS "$BASE/api/v0/rubrics/extraction-jobs/$JOB_ID" -H "Authorization: Bearer $TOKEN")
  status=$(echo "$ST" | jval "['status']")
  stage=$(echo "$ST"  | jval "['progress_stage']")
  stale=$(echo "$ST"  | jval "['stale']")
  el=$(echo "$ST"     | jval "['elapsed_seconds']")
  printf '    [%4ds] status=%-10s stage=%-12s stale=%s elapsed=%s\n' "$elapsed" "$status" "$stage" "$stale" "$el"
  case "$status" in
    completed) break ;;
    failed)    echo "    FAILED: $(echo "$ST" | jval "['error_message']")"; exit 1 ;;
  esac
  if [ "$stale" = "True" ]; then echo "    STALE — instance died mid-job (retry via POST .../$JOB_ID/retry)"; exit 1; fi
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then echo "    TIMEOUT after ${MAX_WAIT}s"; exit 1; fi
  sleep "$POLL_SECONDS"; elapsed=$((elapsed + POLL_SECONDS))
done

echo "==> Result + provenance (the deploy-verification artifact)"
curl -fsS "$BASE/api/v0/rubrics/extraction-jobs/$JOB_ID/result" -H "Authorization: Bearer $TOKEN" \
  | "$PY" -c "
import sys, json

# The expected versions are READ FROM THE LOCAL TREE, never hardcoded. This check
# answers the question that actually matters — 'is prod running the code I have?' —
# rather than 'does prod match a string someone typed during an earlier PR?'.
# (A hardcoded '3.2.0' is precisely how this tripwire cried wolf after PR-2 bumped
#  PIPELINE_VERSION to 3.3.0: the deploy was correct and the assertion was stale.)
sys.path.insert(0, '.')
from app.services.docx_v3.pipeline import EXTRACTION_PROMPT_VERSION, PIPELINE_VERSION

d = json.load(sys.stdin); p = d['provenance']; cfg = p.get('llm_config') or {}
print('    questions       :', len(d['result'].get('questions', [])))
print('    warnings        :', d['warnings'])
print('    requires_review :', d['requires_review'])
print('    prompt_version  :', p['prompt_version'])
print('    pipeline_version:', p['pipeline_version'])
print('    llm_model       :', p['llm_model'])
print('    llm_config      :', cfg)
print('    tokens in/out   :', p['input_tokens'], '/', p['output_tokens'])
print('    duration_ms     :', p['duration_ms'])

checks = {
    # prod image == local tree
    'prompt_version':    (p['prompt_version'],        EXTRACTION_PROMPT_VERSION),
    'pipeline_version':  (p['pipeline_version'],      PIPELINE_VERSION),
    # D-2 model pin (the config the 5/5 eval gate was earned at)
    'model':             (cfg.get('model'),           'gpt-5.5'),
    'reasoning_effort':  (cfg.get('reasoning_effort'),'medium'),
    # PR-2 transport policy must be LIVE, not merely merged
    'timeout_s':         (cfg.get('timeout_s'),        360.0),
    'transport_retries': (cfg.get('transport_retries'),1),
    'task_budget_s':     (cfg.get('task_budget_s'),    840.0),
}
bad = {k: v for k, v in checks.items() if v[0] != v[1]}
if bad:
    print('    DEPLOY VERIFY   : MISMATCH')
    for k, (got, want) in bad.items():
        print(f'      - {k}: prod={got!r} expected={want!r}')
    print('      (if pipeline/prompt differ, prod is running a DIFFERENT TREE — redeploy)')
    sys.exit(1)
print('    DEPLOY VERIFY   : PASS (prod == local tree; D-2 pin + PR-2 transport policy live)')
"
echo "==> Done."
