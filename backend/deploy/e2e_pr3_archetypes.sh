#!/usr/bin/env bash
# PR-3 post-merge E2E — the two archetypes PR-3 unlocked, driven through the REAL
# deployed path (async extraction job -> poll -> save_ontology_draft), not a unit test.
#
#   employee_course_select1  a "choose k of N" exam. Before PR-3 this was a hard
#                            dead-end: extraction succeeded, then INV-4 rejected it
#                            forever because the compiler summed OFFERED points (100)
#                            against an achievable declared total (50).
#                            EXPECT: SAVED + COMPILED, stats.total_points == 50.
#
#   bagrut_899371            a depth-2 nested rubric carrying a REAL teacher error one
#                            level down. Before PR-3 the flat INV-2 rejected it at the
#                            wrong node (a parent whose criteria live on its children)
#                            and stayed silent at the node that was actually wrong.
#                            EXPECT: REJECTED with INV-2 at q1.א.2 — the true offender —
#                            plus location + expected/actual + genuine Hebrew.
#
# This is the acceptance evidence for PR-3, so it asserts on the CONTENT of the
# rejection, not merely that one occurred. A rejection at the wrong node would be
# the pre-PR-3 behaviour passing itself off as success.
#
#   EMAIL='you@example.com' PASSWORD='...' bash deploy/e2e_pr3_archetypes.sh
set -uo pipefail
export PYTHONUTF8=1

API="${API_BASE:-https://gradervision-backend-588558139818.europe-west1.run.app}"
EMAIL="${EMAIL:?set EMAIL to your teacher account email}"
PASSWORD="${PASSWORD:?set PASSWORD}"
FIX="$(cd "$(dirname "$0")/.." && pwd)/tests/rubric_eval_suite/fixtures"
WORK="$(mktemp -d)"
STAMP="$(date +%s)"
PY="${PYTHON:-python}"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()  { printf '  \033[32mPASS\033[0m %s\n' "$*"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; FAILED=1; }
FAILED=0

say "AUTH  ($API)"
TOKEN=$(curl -sS -X POST "$API/api/v0/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$($PY -c "import json,os;print(json.dumps({'email':os.environ['EMAIL'],'password':os.environ['PASSWORD']}))")" \
  | $PY -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))')
[ -n "$TOKEN" ] || { bad "no token"; exit 1; }
ok "authenticated"

# submit -> poll -> write the JobResultResponse to $1
extract() {
  local docx="$1" out="$2" job status
  # NOTE the trailing slash: the route is @router.post("/") under the
  # /api/v0/rubrics/extraction-jobs prefix. Without it Starlette 307s and curl
  # (no -L) silently hands you the redirect body instead of the job.
  job=$(curl -sS -X POST "$API/api/v0/rubrics/extraction-jobs/" \
        -H "Authorization: Bearer $TOKEN" -F "file=@$docx" \
        | $PY -c 'import sys,json;print(json.load(sys.stdin).get("job_id",""))')
  [ -n "$job" ] || { echo "    submit failed"; return 1; }
  echo "    job $job — polling"
  for _ in $(seq 1 90); do
    status=$(curl -sS "$API/api/v0/rubrics/extraction-jobs/$job" -H "Authorization: Bearer $TOKEN" \
             | $PY -c 'import sys,json;print(json.load(sys.stdin).get("status",""))')
    case "$status" in
      completed)
        curl -sS "$API/api/v0/rubrics/extraction-jobs/$job/result" -H "Authorization: Bearer $TOKEN" > "$out"
        echo "    extracted"; echo "$job" > "$out.jobid"; return 0 ;;
      failed) echo "    extraction FAILED"; return 1 ;;
    esac
    sleep 10
  done
  echo "    timeout"; return 1
}

# The save body is {name, draft: <the whole ExtractRubricResponse>, ...}. The draft
# carries selection_groups natively — the PR-3 E2E prep bug was the WIZARD building
# a partial draft object that dropped them, starving a correct compiler of the one
# field that made it correct. Here we post the extraction result verbatim.
save() {
  local result="$1" name="$2"
  $PY - "$result" "$name" <<'PY' > "$result.payload"
import json, sys
r = json.load(open(sys.argv[1], encoding='utf-8'))
print(json.dumps({
    "name": sys.argv[2],
    "draft": r["result"],
    "acknowledged_warning_ids": [],
    "extraction_job_id": r["job_id"],
}, ensure_ascii=False))
PY
  curl -sS -w '\n%{http_code}' -X POST "$API/api/v0/rubrics/save_ontology_draft" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json; charset=utf-8' \
    --data-binary "@$result.payload"
}

# ---------------------------------------------------------------------------
say "ARCHETYPE 1 — employee_course_select1 (selection exam)  ->  expect SAVED, total=50"
# ---------------------------------------------------------------------------
if extract "$FIX/employee_course_select1.docx" "$WORK/employee.json"; then
  RESP=$(save "$WORK/employee.json" "E2E PR-3 selection $STAMP")
  CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | sed '$d')
  printf '%s' "$BODY" > "$WORK/employee.save.json"
  $PY -m json.tool --no-ensure-ascii < "$WORK/employee.save.json" 2>/dev/null | head -25

  if [ "$CODE" = "201" ] || [ "$CODE" = "200" ]; then
    $PY - "$WORK/employee.save.json" <<'PY'
import sys, json
d = json.load(open(sys.argv[1], encoding='utf-8'))
if d.get("status") == "warnings_require_acknowledgment":
    print("  \033[31mFAIL\033[0m HTTP 200 warnings gate — expected a clean 201 compile"); sys.exit(1)
tp = (d.get("stats") or {}).get("total_points")
if float(tp) == 50.0:
    print(f"  \033[32mPASS\033[0m saved + compiled; total_points = {tp}  (ACHIEVABLE, not the 100 offered)")
    sys.exit(0)
print(f"  \033[31mFAIL\033[0m total_points = {tp} — expected 50. The denominator is wrong."); sys.exit(1)
PY
    [ $? -eq 0 ] || FAILED=1
  else
    bad "expected 201 SAVED, got HTTP $CODE — the selection exam is still a dead end"
  fi
else
  bad "extraction did not complete"
fi

# ---------------------------------------------------------------------------
say "ARCHETYPE 2 — bagrut_899371 (depth-2 nesting)  ->  expect REJECTED at q1.א.2"
# ---------------------------------------------------------------------------
if extract "$FIX/bagrut_899371.docx" "$WORK/bagrut.json"; then
  RESP=$(save "$WORK/bagrut.json" "E2E PR-3 bagrut $STAMP")
  CODE=$(echo "$RESP" | tail -1); BODY=$(echo "$RESP" | sed '$d')

  printf '%s' "$BODY" > "$WORK/bagrut.save.json"
  say "  What the teacher's screen actually receives (the PR-4 anchor question):"
  $PY -m json.tool --no-ensure-ascii < "$WORK/bagrut.save.json" 2>/dev/null

  if [ "$CODE" = "400" ]; then
    ok "rejected (HTTP 400) — the rubric gate held"
    $PY - "$WORK/bagrut.save.json" <<'PY'
import sys, json
d = json.load(open(sys.argv[1], encoding='utf-8'))
d = d.get("detail", d)   # FastAPI HTTPException nests the payload under `detail`
errs = d.get("errors") or []
if not errs:
    print("  \033[31mFAIL\033[0m payload carries NO errors list — teacher sees a bare banner"); sys.exit(1)
if len(errs) != 1:
    print(f"  \033[33mNOTE\033[0m {len(errs)} errors returned (expected exactly 1)")
e = errs[0]
def chk(cond, msg):
    print(("  \033[32mPASS\033[0m " if cond else "  \033[31mFAIL\033[0m ") + msg)
    return cond
allok  = chk(e.get("location") == "q1.א.2", f"location = {e.get('location')!r}  (the TRUE offender, one level down)")
allok &= chk(e.get("invariant") == "INV-2", f"invariant = {e.get('invariant')!r}")
allok &= chk(e.get("expected") is not None and e.get("actual") is not None,
             f"expected={e.get('expected')!r} actual={e.get('actual')!r}  (the numbers, not just a verdict)")
mh, m = e.get("message_he") or "", e.get("message") or ""
allok &= chk(mh != m and any('֐' <= c <= '׿' for c in mh),
             f"message_he is genuinely Hebrew, not the English duplicated: {mh!r}")
sys.exit(0 if allok else 1)
PY
    [ $? -eq 0 ] || FAILED=1
  else
    bad "expected 400 REJECTED, got HTTP $CODE — INV-2 did not fire on a rubric that IS wrong"
  fi
else
  bad "extraction did not complete"
fi

say "RESULT"
if [ "$FAILED" = "0" ]; then ok "both archetypes behaved as PR-3 predicts"; else bad "see above"; fi
echo "  artifacts: $WORK"
exit $FAILED
