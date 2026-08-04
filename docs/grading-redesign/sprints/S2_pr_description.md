# PR: S2 — Auth infrastructure and ownership-scoping pattern

**Sprint:** S2
**Depends on:** S1 (ORM models, merged)
**Foundation refs:** `phase_0a_architecture.md` §6 (Actors and Permission Model), §6.3 (Auth implementation)
**Frontend lockstep:** yes — verify the API client attaches the bearer token to all now-protected endpoints

---

## 1. Scope note — read this first

The original sprint plan titled S2 "auth on grading endpoints." **There are no grading endpoints right now** — S0 deleted all of them, and the new ones land in S4/S8/S9. So S2's actual job is reframed:

> Establish the auth + ownership-scoping infrastructure once, apply it to every user-data endpoint that exists today (the rubric endpoints), and document the canonical pattern that S3–S9 must follow when they add new endpoints.

This is the right sequencing: the new schema makes `user_id NOT NULL` on every table, so auth is a hard prerequisite for S3 (you cannot insert a `students` row without an authenticated `user_id`). Establishing the pattern now means S3 — the first sprint to build new endpoints — inherits a clean, tested convention instead of inventing its own.

**What S2 is NOT:** it is not the place to build `/transcribe`, `/grade`, or any new endpoint. Those belong to their own sprints and will apply this PR's pattern.

---

## 2. Context

Per `phase_0a_architecture.md` §6.2: *"The teacher owns all artifacts created by their actions, and can read/write only their own artifacts."* And §6.3: *"Every grading-related endpoint adds `Depends(get_current_user)`. No grading endpoint is anonymous."*

Today (per the codebase research, Q47):
- `get_current_user` and `get_current_user_optional` both exist in `app/api/v0/auth.py`. The required variant raises 401 on a missing/invalid token; the optional variant returns `None`.
- The rubric management endpoints use the **optional** variant — anonymous rubric creation is allowed, and `rubrics.user_id` is set only when a token happens to be present.
- No grading endpoint reads `current_user` at all (they're deleted now anyway).

S2 makes ownership enforcement real: required auth on every user-data endpoint, `user_id` always sourced from the token, every query scoped to the authenticated user.

---

## 3. The pattern S2 establishes

This is the deliverable that matters most — the convention every later sprint copies.

### 3.1 Required auth dependency

Every endpoint that reads or writes user-owned domain data declares:

```python
current_user: User = Depends(get_current_user)
```

`get_current_user` already exists and raises 401 on missing/invalid token. S2 does not rewrite it; S2 makes it the standard and removes the optional variant from domain endpoints.

Public endpoints that legitimately stay anonymous: login, signup, token refresh, health check. These do NOT get the dependency. S2 must not touch them.

### 3.2 `user_id` comes from the token, never the request body

**Critical security rule.** The owning `user_id` on any write is `current_user.id`, sourced from the authenticated token. It is NEVER read from the request body, query param, or any client-supplied field. A client must not be able to create a resource owned by another user by passing a `user_id`.

If any existing request schema has a `user_id` / `teacher_id` field, remove it — ownership is implicit from the token.

### 3.3 Ownership-scoped reads

Every list query filters on the authenticated user:

```python
result = await db.execute(
    select(Rubric).where(Rubric.user_id == current_user.id)
)
```

Every detail/update/delete fetches with ownership in the same query, and 404s if no row matches:

```python
async def get_owned_or_404(db, model, obj_id, user_id):
    """Fetch a row by id that the user owns, else 404."""
    result = await db.execute(
        select(model).where(model.id == obj_id, model.user_id == user_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
```

This helper is the canonical "fetch a resource I own" primitive. Put it somewhere shared (e.g. `app/api/deps.py` or `app/api/ownership.py`) so S3–S9 import it rather than reimplementing.

### 3.4 404, not 403, for other users' resources

When user A requests user B's resource, return **404 Not Found**, not 403 Forbidden. Rationale: 403 leaks the existence of the resource. In a per-tenant system where teachers must not know about each other's data, "as far as you're concerned, this doesn't exist" is the correct and privacy-preserving response. The `get_owned_or_404` helper above encodes this — a non-owned resource is indistinguishable from a non-existent one.

---

## 4. Files

### Modify — rubric endpoints (the retrofit)
| File | Change |
|---|---|
| `app/api/v0/rubric_management.py` | Replace every `Depends(get_current_user_optional)` with `Depends(get_current_user)`. Remove the `user_id if current_user else None` conditionals — `user_id` is now always `current_user.id`. Scope every read query by `user_id`. Use `get_owned_or_404` for detail/update/delete. |
| Any other file with rubric read/write endpoints | Same treatment. Audit for `get_current_user_optional` usage. |

### Create — the shared ownership helper
| File | Contents |
|---|---|
| `app/api/deps.py` (or `app/api/ownership.py` — pick one, document it) | `get_owned_or_404` helper from §3.3. If `app/api/deps.py` already exists, add it there. |

### Stub — the two broken grading read endpoints (decision locked, see §5)
| File | Action |
|---|---|
| `app/api/v0/grading.py` — `GET /graded_tests`, `GET /graded_test/{id}` | These reference the old `graded_json` shape and are runtime-broken after S1. **Stub both with `raise HTTPException(501, "Rebuilt in S8")` + `# TODO(S8)` marker.** Add the `Depends(get_current_user)` dependency so the signature matches the pattern, but do not implement the body. See §5. |

### Modify — frontend (lockstep)
| File | Change |
|---|---|
| `frontend/src/lib/api.ts` | Audit: confirm the bearer token is attached to every request hitting a now-protected rubric endpoint. (Likely already the case — there's a login system. Verify, don't assume.) |
| Frontend rubric flows | Confirm there is no anonymous rubric-creation path in the UI. If one exists, it must now require login. |

---

## 5. Decision (LOCKED) — stub the two broken grading read endpoints

`GET /graded_tests` and `GET /graded_test/{id}` survived S0 (the manifest kept them, intending S8 to rewrite them for the new schema). But they reference `graded_json`, `total_score` from the old response shape, and the old `GradedTest` columns — all of which changed in S1. They are runtime-broken now: `import app.main` succeeds (the column refs are in function bodies, not import-time), but calling them 500s.

**Decision: stub both with 501 + `TODO(S8)`.**

```python
@router.get("/graded_tests")
async def get_graded_tests(
    current_user: User = Depends(get_current_user),  # pattern applied even though stubbed
):
    # TODO(S8): rebuild against new graded_tests schema + GradedTestContract response shape
    raise HTTPException(status_code=501, detail="Rebuilt in S8")
```

This keeps the tree clean (no 500-ing endpoint sitting around), puts the auth dependency in place so the signature matches the pattern uniformly, and defers the real implementation to S8 — the sprint that owns the new `GradedTestDraft` / `GradedTestContract` response shapes. S8 replaces the 501 stub with the real implementation.

Rejected alternatives, for the record: rewriting them now (would force inventing the S8 response shape out of sequence) and leaving them broken with auth bolted on (a 500-ing endpoint is still broken).

---

## 6. Critical implementation notes

### Note 1 — `user_id` from token is non-negotiable
Re-stating §3.2 because it's the security crux: the owning `user_id` is always `current_user.id`. If you find any code path that reads `user_id` from a request body or query param and uses it as the owner, that is a privilege-escalation bug — remove it. Ownership is implicit from authentication.

### Note 2 — don't break the public endpoints
Login, signup, token refresh, health check, and any webhook receivers stay anonymous. Adding `Depends(get_current_user)` to a login endpoint would make login impossible (chicken-and-egg). Audit which endpoints are legitimately public before applying the dependency broadly.

### Note 3 — 404 over 403, consistently
Use `get_owned_or_404` everywhere. Do not hand-roll a `if obj.user_id != current_user.id: raise 403` check anywhere — that both leaks existence and creates an inconsistent convention. One helper, one behavior.

### Note 4 — the rubric endpoints are the reference implementation
After this PR, the rubric endpoints are how S3–S9 learn the pattern. Make them clean. If a reviewer reads `rubric_management.py` and copies its auth+ownership style verbatim into a new students endpoint, the result should be correct. Treat the rubric endpoints as the worked example.

### Note 5 — `get_current_user_optional` is not deleted, just unused on domain endpoints
There may be a legitimate future use for optional auth (e.g. a public-share-link view of a rubric, which already exists via `rubric_share_tokens`). Don't delete the optional variant outright — just stop using it on endpoints that should require ownership. Audit each current usage and decide: does this endpoint serve owned data (→ required) or genuinely-public data (→ keep optional)? The share-token endpoints are the likely legitimate optional-auth cases.

---

## 7. Frontend lockstep requirements

Per the T1 lockstep decision, S2 ships with its frontend changes. The frontend work here is mostly verification, possibly a small fix:

1. **Confirm the bearer token is attached** to every request hitting a now-required-auth rubric endpoint. If the API client has a central fetch wrapper that injects the token, this is likely already handled — verify it covers the rubric calls.
2. **Confirm no anonymous rubric flow exists.** If the UI ever created or read a rubric without a logged-in user, that path now 401s. Find it (if it exists) and gate it behind login.
3. **Handle 401 gracefully.** Confirm the frontend has a 401 handler (redirect to login / refresh token). If the rubric endpoints were previously optional-auth, a 401 may be a new response they need to handle.

If all three are already true (likely, given there's an established login system), the frontend change is a no-op verification documented in the PR description. If any is false, it's a small fix in the same PR.

---

## 8. Testing requirements

Tests go in `tests/api/` (or wherever API tests live). These establish the auth test harness that S3–S9 will copy.

### Required tests (against the rubric endpoints, as the reference)
1. **Unauthenticated → 401.** A request to a protected rubric endpoint with no token returns 401.
2. **Invalid token → 401.** A request with a malformed/expired token returns 401.
3. **Own resource → 200.** An authenticated user reading their own rubric succeeds.
4. **Other user's resource → 404.** User A authenticated, requesting user B's rubric by id, returns 404 (not 403, not 200).
5. **List is scoped.** User A's list endpoint returns only A's rubrics, never B's — even when B has rubrics in the DB.
6. **Ownership can't be spoofed.** A create request with a `user_id`/`teacher_id` in the body (if the schema even allows it) results in a resource owned by the *authenticated* user, not the body-supplied one. (If the schema correctly has no such field, assert the created resource's `user_id` equals the token's user.)
7. **Stubbed grading endpoints return 501** — `GET /graded_tests` and `GET /graded_test/{id}` return 501 with the `TODO(S8)` marker, not 500.

Tests 4, 5, and 6 are the security-critical ones. They prove cross-tenant isolation holds.

---

## 9. Acceptance criteria

- [ ] `get_owned_or_404` helper exists in a shared location, documented.
- [ ] Every rubric domain endpoint uses `Depends(get_current_user)` (required, not optional).
- [ ] No domain endpoint reads `user_id`/`teacher_id` from client input as the owner.
- [ ] Every rubric read query is scoped by `user_id == current_user.id`.
- [ ] Detail/update/delete use `get_owned_or_404`; cross-user access returns 404.
- [ ] Public endpoints (login, signup, refresh, health, share-token views) remain anonymous.
- [ ] The two broken grading read endpoints are stubbed with 501 + `TODO(S8)` and carry the `Depends(get_current_user)` dependency (per §5).
- [ ] Frontend attaches the bearer token to all protected requests; no anonymous rubric flow remains; 401 is handled.
- [ ] All seven tests in §8 pass; tests 4/5/6 (cross-tenant isolation) explicitly verified.
- [ ] `import app.main` succeeds; `pytest --collect-only` succeeds.

---

## 10. Known follow-ups (do NOT do in this PR)

- **S3** builds the students + classes endpoints — the first to *use* this pattern on new tables. It imports `get_owned_or_404` and copies the rubric endpoints' auth+ownership style.
- **S4** builds `/transcribe` and `/grade` — applies the pattern to transcriptions.
- **S8** rebuilds the grading read endpoints (the ones stubbed in §5) against the new schema, with the new `GradedTestDraft`/`GradedTestContract` response shapes — and applies this pattern.
- **The multi-owner inflection point** (Phase 0a §11.2): when sharing of graded tests / classes lands, the single-`user_id` ownership model here is replaced by an ownership join table, and `get_owned_or_404` becomes a join query. Not now — but every use of the helper is a future touch point, so keeping ownership checks funneled through the single helper (rather than scattered inline) is what makes that future migration tractable.

If during implementation you find an endpoint whose correct auth treatment is ambiguous (genuinely-public vs owned), **flag it** rather than guessing. The share-token endpoints are the known ambiguous case (§6 Note 5); there may be others.
