# SCALING_ROADMAP.md — batch pipeline capacity, by tier

> Owner analysis 2026-08-22 (Cloud Tasks migration deployment). CLAUDE.md §15
> points here; keep this file the single home for capacity math and the
> per-tier dial ladder. When a dial changes in prod, update the "DEPLOYED"
> column — this doc claiming one thing while the queue runs another is a bug.

## Workload model (the numbers everything derives from)

- Class batch ≈ 30–40 tests; test ≈ 5–7 pages; **~2 P1 calls + 1 P2 + 1
  identity ≈ 4 LLM calls, ~60–75s wall per document** (healthy network).
- **Drain rate ≈ 0.86 × C docs/min** where C = the transcription queue's
  `maxConcurrentDispatches`. C=25 → ~1,290 docs/hr ≈ 37 class batches/hr.
- Grading: ~8–15 scope calls per test — grading LLM volume EXCEEDS
  transcription; its queue concurrency is a spend governor as much as a
  throughput dial.
- **TTL↔backlog law:** the 90-min dispatch backstop falsely fails honest
  queued work when queue depth > drain × 90min. At C=25 the cliff is ~1,900
  queued docs. Rule: `dispatch TTL > max expected backlog ÷ drain rate`.

## Deployed configuration (launch, 2026-08-22) — sized for 100 users/evening

| Dial | DEPLOYED | Why |
|---|---|---|
| `transcription-jobs` maxConcurrentDispatches | 25 | 100 users/evening ≈ 3,500 docs; C=5 drains 260/hr (13 hrs — fails); C=25 ≈ 1,290/hr with peak-hour headroom |
| `grading-jobs` maxConcurrentDispatches | 20 | matches accept-wave bursts; bounds spend |
| both queues maxAttempts / min-backoff | 3 / 10s | CAS claims make redelivery a provable no-op; redelivery is the only healer for dispatch-level failures |
| Cloud Run `--concurrency` | 5 | (8→5, 2026-08-23) pins docs/instance to the density measured safe at 85% of 2 GiB — under ANY fixed/per-doc memory split, 8 could OOM-kill a container mid-batch; still forces scale-OUT (25÷5 = 5 instances) so the per-instance provider cap doesn't head-of-line-block against the 900s dispatch deadline |
| Cloud Run `--memory` / `--max-instances` | 2Gi / 40 | ~8 concurrent docs/instance hold rendered page images (~70MB+/doc peaks); 1Gi was the old single-fan-out sizing |

## Tier ladder — what changes, and the trigger to change it

**→ ~300 active users** (trigger: p95 evening t_first > 3 min, or queue depth
alert at ~1,000): raise C to ~40–50 + max-instances to ~60; raise
`TRANSCRIPTION_JOB_DISPATCH_TTL_MINUTES` per the TTL law; fix the
`list_batches` N+1 (two queries per batch row).

**→ 1000s of users** (structural work, design before need):
1. **Tenant fairness** — single FIFO queue = head-of-line blocking across
   teachers (B's 5 docs wait behind A's 50). Shard K queues by user-hash
   (cheap, coarse) or app-level fair dispatcher (real).
2. **Global provider rate limiter** — the per-instance scheduler cap stops
   protecting project quota once instance count floats (50 × 5 = 250
   concurrent calls). Shared token bucket (Redis) or provisioned-throughput
   contracts; key/project sharding if needed.
3. **Read path** — detail endpoint re-validates every draft_json per poll;
   move rollups to SQL aggregates + SSE/push instead of polling (~10× read
   cut). PR-7 (grader call bounding) becomes MANDATORY here: one hung grading
   task holds a global dispatch slot up to 15 min.

## Standing observations

- Provider quota is the true ceiling at every tier; queue concurrency is the
  blast shield and spend governor. Gemini RPD cap: solved (see
  MISSION_gemini_quota_launch_blocker.md); OpenAI quota: in progress.
- Cloud Tasks itself is never the bottleneck (500 dispatch/s/queue, millions
  of tasks). The architecture (durable rows, CAS idempotency, stateless
  workers, set-based liveness) needs NO rework at any tier above.
- Monitoring to add at first trigger: Cloud Monitoring alert on queue depth
  (transcription-jobs > ~1,000), and p95 t_first per batch.
