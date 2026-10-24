#!/usr/bin/env bash
# In-house scanning — infrastructure (PR_in_house_scanning.md §9, as amended
# by ruling OD-1: there is NO scan-compile queue and NO Cloud Scheduler sweep —
# compiling is step 0 of the transcription job, on the existing
# transcription-jobs queue).
#
# Idempotent: every step re-runs safely. Run from the repo root:
#     bash scan-service/deploy/deploy.sh            # everything below
#     SKIP_DEPLOY=1 bash scan-service/deploy/deploy.sh   # IAM + CORS only
#
# What it does, in order:
#   1. a service account for scan-service, with object read/write on the bucket
#   2. deploy scan-service: private, 2 vCPU / 2 GiB, concurrency 4,
#      min-instances 1 (D13), max 20, 300 s
#   3. the backend's service account may INVOKE it (roles/run.invoker)
#   4. the backend's service account may sign URLs as itself (already granted
#      on 2026-10-24 — verified, re-applied idempotently)
#   5. bucket CORS: MERGED with the existing entry, adding the production
#      origins and the signed-PUT header (the existing entry is kept intact)
#   6. prints the backend + Vercel env to set — it does NOT set them: turning
#      the feature on is a separate, deliberate flip (CAPTURE_ENABLED).
#
# Least privilege, stated: uniform bucket-level access is OFF on this bucket,
# so an IAM condition cannot narrow scan-service to captures/*. Its role is
# object read/write on the bucket. Narrowing it means enabling UBLA bucket-wide
# — a security change of its own, deliberately not made here.
set -euo pipefail

PROJECT="${PROJECT:-gen-lang-client-0438328890}"
REGION="${REGION:-europe-west1}"
BUCKET="${BUCKET:-grader-vision-pdfs-0438328890}"
SERVICE="${SERVICE:-scan-service}"
SCAN_SA_NAME="${SCAN_SA_NAME:-scan-service}"
SCAN_SA="${SCAN_SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
BACKEND_SA="${BACKEND_SA:-588558139818-compute@developer.gserviceaccount.com}"
ORIGINS="${ORIGINS:-https://vivi-assistant.com,https://www.vivi-assistant.com}"

say() { printf '\n== %s\n' "$*"; }

say "1. service account ${SCAN_SA}"
gcloud iam service-accounts describe "$SCAN_SA" --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "$SCAN_SA_NAME" --project "$PROJECT" \
       --display-name "scan-service (in-house scanning)"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member "serviceAccount:${SCAN_SA}" --role roles/storage.objectAdmin >/dev/null

if [[ -z "${SKIP_DEPLOY:-}" ]]; then
  say "2. deploy ${SERVICE}"
  gcloud run deploy "$SERVICE" --source scan-service --project "$PROJECT" --region "$REGION" \
    --no-allow-unauthenticated --service-account "$SCAN_SA" \
    --cpu 2 --memory 2Gi --concurrency 4 --min-instances 1 --max-instances 20 --timeout 300
fi

say "3. the backend may invoke ${SERVICE}"
gcloud run services add-iam-policy-binding "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:${BACKEND_SA}" --role roles/run.invoker >/dev/null

say "4. the backend signs URLs as itself (V4 signed PUT / GET)"
gcloud iam service-accounts add-iam-policy-binding "$BACKEND_SA" --project "$PROJECT" \
  --member "serviceAccount:${BACKEND_SA}" --role roles/iam.serviceAccountTokenCreator >/dev/null

say "5. bucket CORS (merged)"
CORS_FILE="$(mktemp)"
gcloud storage buckets describe "gs://${BUCKET}" --format=json \
  | python3 - "$ORIGINS" > "$CORS_FILE" <<'PY'
import json, sys
current = json.load(sys.stdin).get("cors_config") or []
wanted = {
    "origin": sys.argv[1].split(","),
    "method": ["PUT", "GET"],
    # The signed PUT carries both; the preflight must allow them.
    "responseHeader": ["Content-Type", "x-goog-content-length-range"],
    "maxAgeSeconds": 3600,
}
merged = [c for c in current if sorted(c.get("origin", [])) != sorted(wanted["origin"])] + [wanted]
json.dump(merged, sys.stdout, indent=1)
PY
cat "$CORS_FILE"
gcloud storage buckets update "gs://${BUCKET}" --cors-file "$CORS_FILE"

SCAN_URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --format 'value(status.url)' 2>/dev/null || true)"

say "6. to turn the feature ON (not done by this script)"
cat <<EOF
  Secret (once):   printf '%s' "\$(openssl rand -base64 32)" | \\
                     gcloud secrets create capture-token-secret --data-file=- --project ${PROJECT}
  Backend env:     gcloud run services update gradervision-backend --project ${PROJECT} --region ${REGION} \\
                     --update-env-vars CAPTURE_ENABLED=true,SCAN_SERVICE_URL=${SCAN_URL:-<scan-service url>} \\
                     --update-secrets CAPTURE_TOKEN_SECRET=capture-token-secret:latest
  Vercel env:      NEXT_PUBLIC_CAPTURE_ENABLED=true   (inlined at build — redeploy the frontend)
  ORDER: apply backend/migrations/036_capture.sql BEFORE deploying the backend
                   that ships with it — that backend reads transcription_jobs.withdrawn_at and
                   .capture_version_id on every batch read. 036 is purely ADDITIVE (new tables,
                   two nullable columns), so the backend running today is unaffected by it.
EOF
