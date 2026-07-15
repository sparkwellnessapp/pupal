import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { hydrateAnyQuestions, dehydrateQuestions } from './rubric-transform';

/**
 * B-11 — the frontend's permanent GOLDEN ROUND-TRIP self-pass.
 *
 * The acceptance bar for B-11 is a codec property, not a render property:
 *
 *     dehydrate(hydrate(fixture.questions))  ≡  fixture.questions
 *
 * for every golden rubric, where ≡ is STRUCTURAL IDENTITY: same tree shape,
 * same ids, same field presence, point values Decimal-equal, opaque fields
 * preserved. If this holds, the frontend is a faithful codec and everything
 * downstream (recursive render, recursive validation) rests on a model that
 * already tells the truth.
 *
 * The five goldens are read IN PLACE from the backend eval suite — the canonical
 * owner of these fixtures. Copying them into the frontend would duplicate ground
 * truth and invite drift (CLAUDE.md §0.4).
 *
 * PRE-FIX (depth-1 codec) this suite is RED on exactly the fixtures that carry
 * data the codec drops:
 *   - bagrut_899371     — nested sub_questions dropped + example_solution dropped
 *   - csharp_plane_combine — example_solution dropped
 *   - foundations_cs    — example_solution dropped
 * and GREEN on employee_course_select1 and hobby_tvshow (nothing to drop).
 * POST-FIX (recursive codec + _carry + example_solution first-class) all five green.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCHMARKS = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');

const GOLDEN_FIXTURES = [
    'bagrut_899371',           // depth-2 + selection + example_solution — the hard case
    'csharp_plane_combine',    // depth-1 + example_solution
    'employee_course_select1', // depth-1 + selection
    'foundations_cs',          // depth-1 + example_solution + mixed structure
    'hobby_tvshow',            // depth-1 + sub_criteria
] as const;

function loadGolden(name: string): { questions: unknown[] } {
    return JSON.parse(readFileSync(path.join(BENCHMARKS, `${name}.json`), 'utf-8'));
}

// ---------------------------------------------------------------------------
// normalizeForCompare — the Decimal-aware structural-identity relation.
// ---------------------------------------------------------------------------
//
// The goldens are hand-derived, so a value like "12.0", 12, and "12" all mean
// the same Decimal, and dehydrate canonicalizes number → String(). So identity
// is defined MODULO:
//   1. Point canonicalization: every `points`/`total_points` collapses to
//      Number(x).toString() ("12.0" → "12", 1.5 → "1.5"). Teacher points are
//      exact quarter-values; no arithmetic runs, so parse-equality is exact.
//   2. Empty-list ≡ absent ≡ null: an optional list is information-free whether
//      it is [], null, or missing (criteria on a parent node, empty skill_targets).
//   3. Null scalar ≡ absent: a null title and a missing title carry the same info.
//
// It deliberately does NOT forgive a VALUE-BEARING drop: example_solution:"code"
// on one side and absent on the other are NOT equal — that is exactly the class
// of corruption this suite exists to catch. Do not "fix" a red by loosening this.
// Array ORDER is structural and never sorted.

const POINT_KEYS: ReadonlySet<string> = new Set(['points', 'total_points']);

function canonicalizePoint(v: unknown): string {
    const n = typeof v === 'number' ? v : parseFloat(String(v));
    return Number.isFinite(n) ? String(n) : String(v);
}

function normalizeForCompare(value: unknown): unknown {
    if (Array.isArray(value)) {
        return value.map(normalizeForCompare);
    }
    if (value !== null && typeof value === 'object') {
        const out: Record<string, unknown> = {};
        for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
            if (raw === null || raw === undefined) continue;          // null/absent scalar
            if (Array.isArray(raw) && raw.length === 0) continue;     // empty list ≡ absent
            if (POINT_KEYS.has(key)) { out[key] = canonicalizePoint(raw); continue; }
            out[key] = normalizeForCompare(raw);
        }
        return out;
    }
    return value;
}

describe('B4 — golden round-trip: dehydrate ∘ hydrate is a structural identity', () => {
    for (const name of GOLDEN_FIXTURES) {
        it(`${name} round-trips (structural identity, Decimal-equal points)`, () => {
            const golden = loadGolden(name);
            const roundTripped = dehydrateQuestions(hydrateAnyQuestions(golden.questions));
            expect(normalizeForCompare(roundTripped)).toEqual(normalizeForCompare(golden.questions));
        });
    }
});

// ---------------------------------------------------------------------------
// Layer B — the document ENVELOPE, deferred to B-11b, witnessed here so the
// leak is tracked rather than silently accepted.
// ---------------------------------------------------------------------------
//
// The questions-array codec above is Layer A (B-11). Separately, the re-edit
// pages (my-rubrics, rubric-generator) assemble a save payload that DROPS
// selection_groups and re-sums total_points as Σ offered — corrupting a saved
// selection rubric's achievable total on re-edit — and every page drops
// programming_language. That is payload assembly, not this codec, so it is a
// separate ticket. This TODO keeps it on the board.
describe('B-11b (deferred) — document-envelope preservation', () => {
    it.todo(
        'selection_groups + programming_language + achievable total survive a ' +
        're-edit save through my-rubrics / rubric-generator',
    );
});
