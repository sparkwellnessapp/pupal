#!/usr/bin/env bash
#
# [028 §7] The 14-day re-ask digest, as a Cloud Run Job on a daily schedule.
#
# COMMITTED RATHER THAN CLICKED. A schedule that exists only as a console
# action nobody recorded is a schedule nobody can reproduce, review, or move to
# another project — and the one thing worse than an unscheduled digest is a
# scheduled one that silently stopped.
#
# WHY A JOB AND NOT AN ENDPOINT. There is no reason to expose a timer-driven
# query to the internet. A Cloud Run JOB has no URL, no shared secret to leak,
# and no /internal handler to authenticate — the trigger is IAM.
#
# IT REUSES THE SERVICE'S IMAGE AND SERVICE ACCOUNT. No new credentials are
# introduced: the same container already has DATABASE_URL, the Resend key and
# ADC, so the job inherits exactly the access the service has and nothing more.
#
# Run it from `backend/`:
#     bash deploy/onboarding_reask_job.sh
#
# Idempotent: `create` is retried as `update` when the resource already exists,
# so re-running this after a redeploy is always the answer.

set -euo pipefail

PROJECT="${PROJECT:-gen-lang-client-0438328890}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-gradervision-backend}"
JOB="${JOB:-onboarding-reask}"
SCHEDULER_JOB="${SCHEDULER_JOB:-onboarding-reask-daily}"
# 08:00 Asia/Jerusalem — a working hour in the recipient's own timezone, and
# named as a zone rather than an offset so it follows Israeli DST by itself.
SCHEDULE="${SCHEDULE:-0 8 * * *}"
TIMEZONE="${TIMEZONE:-Asia/Jerusalem}"

echo "==> Resolving the image the service is currently running"
# The job must run the SAME code as the service. Reading the live image (rather
# than rebuilding) means the digest can never be a version behind or ahead of
# the endpoint that wrote the rows it reads.
IMAGE="$(gcloud run services describe "$SERVICE" \
    --project "$PROJECT" --region "$REGION" \
    --format 'value(spec.template.spec.containers[0].image)')"
echo "    image: $IMAGE"

echo "==> Resolving the service account the service runs as"
SERVICE_ACCOUNT="$(gcloud run services describe "$SERVICE" \
    --project "$PROJECT" --region "$REGION" \
    --format 'value(spec.template.spec.serviceAccountName)')"
echo "    service account: ${SERVICE_ACCOUNT:-<project default>}"

SA_FLAG=()
if [[ -n "${SERVICE_ACCOUNT}" ]]; then
    SA_FLAG=(--service-account "$SERVICE_ACCOUNT")
fi

echo "==> Creating (or updating) the Cloud Run job"
#
# ⚠️ A JOB INHERITS NOTHING FROM THE SERVICE. They are separate Cloud Run
# resources: sharing an image shares the CODE, not the configuration. A job
# created with `--image` alone starts with an EMPTY environment — no
# DATABASE_URL, no OPENAI_API_KEY (which `config.py` declares without a
# default, so the process dies at import, before any of this PR's code runs).
# So every variable the script actually needs is restated here, explicitly.
#
# ALERT_EMAIL is set HERE and not on the service, because the digest is the
# only consumer and the service has never needed it.
#
# --max-retries 1: the script is self-healing by design — a failed send stamps
# nothing, so the NEXT DAY's run picks up everyone it missed. Cloud Run's own
# retry would only re-attempt the same failing provider minutes apart.
# --task-timeout 15m: a digest is one query and one HTTP call; anything past
# this is stuck, not slow.
ALERT_EMAIL="${ALERT_EMAIL:-tapicer.business@gmail.com}"

# `^|^` is gcloud's custom-delimiter form. The default delimiter is a COMMA,
# which would split EMAIL_FROM and any future multi-origin value down the
# middle. The delimiter must also not occur INSIDE a value — `^@^` was the
# obvious pick and is wrong, because every address here contains an `@`
# (gcloud rejected `vivi-assistant.com>` as a malformed pair). A pipe cannot
# appear in an email address, a project id, or a provider name.
ENV_VARS="^|^APP_ENV=production"
ENV_VARS="${ENV_VARS}|GOOGLE_CLOUD_PROJECT=${PROJECT}"
ENV_VARS="${ENV_VARS}|EMAIL_PROVIDER=resend"
ENV_VARS="${ENV_VARS}|EMAIL_FROM=Vivi <noreply@vivi-assistant.com>"
ENV_VARS="${ENV_VARS}|ALERT_EMAIL=${ALERT_EMAIL}"
# ONBOARDING_SHEET_ID is deliberately ABSENT: unset only costs the digest its
# "full queue" footer link, and inventing an id would be worse than no link.
if [[ -n "${ONBOARDING_SHEET_ID:-}" ]]; then
    ENV_VARS="${ENV_VARS}|ONBOARDING_SHEET_ID=${ONBOARDING_SHEET_ID}"
fi

# Same Secret Manager secrets the service reads — no new credentials (§7).
SECRETS="DATABASE_URL=database-url:latest"
SECRETS="${SECRETS},OPENAI_API_KEY=openai-api-key:latest"
SECRETS="${SECRETS},RESEND_API_KEY=resend-api-key:latest"

JOB_ARGS=(
    --project "$PROJECT"
    --region "$REGION"
    --image "$IMAGE"
    --command python
    --args=-m,app.scripts.onboarding_reask
    --max-retries 1
    --task-timeout 15m
    --set-env-vars "$ENV_VARS"
    --set-secrets "$SECRETS"
    "${SA_FLAG[@]}"
)

if gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" >/dev/null 2>&1; then
    echo "    job exists — updating"
    gcloud run jobs update "$JOB" "${JOB_ARGS[@]}"
else
    gcloud run jobs create "$JOB" "${JOB_ARGS[@]}"
fi
echo

echo "==> Ensuring the Cloud Scheduler API is enabled"
# It was NOT enabled on this project (2026-09-09) — nothing had ever needed a
# timer before. Enabling is idempotent and takes ~1 minute the first time.
gcloud services enable cloudscheduler.googleapis.com --project "$PROJECT"

echo "==> Creating (or updating) the Cloud Scheduler trigger"
SCHEDULER_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB}:run"

SCHED_ARGS=(
    --project "$PROJECT"
    --location "$REGION"
    --schedule "$SCHEDULE"
    --time-zone "$TIMEZONE"
    --uri "$SCHEDULER_URI"
    --http-method POST
    --oauth-service-account-email "${SERVICE_ACCOUNT:-$(gcloud projects describe "$PROJECT" --format 'value(projectNumber)')-compute@developer.gserviceaccount.com}"
    # Retry on failure: a transient provider or cold-start error should not
    # cost a whole day's digest.
    --max-retry-attempts 3
    --min-backoff 60s
)

if gcloud scheduler jobs describe "$SCHEDULER_JOB" \
        --project "$PROJECT" --location "$REGION" >/dev/null 2>&1; then
    echo "    scheduler job exists — updating"
    gcloud scheduler jobs update http "$SCHEDULER_JOB" "${SCHED_ARGS[@]}"
else
    gcloud scheduler jobs create http "$SCHEDULER_JOB" "${SCHED_ARGS[@]}"
fi

echo
echo "==> Done."
echo "    Run it once by hand:  gcloud run jobs execute $JOB --project $PROJECT --region $REGION --wait"
echo "    Read the logs:        gcloud beta run jobs logs tail $JOB --project $PROJECT --region $REGION"
echo
echo "    IDEMPOTENCY CHECK (§7 requires it before declaring this done): execute"
echo "    the job twice in a row against seeded data. The second run must report"
echo "    '0 teacher(s) in today's digest' — the stamp written by the first run"
echo "    is what excludes them, and only a NEW answer re-arms a teacher."
