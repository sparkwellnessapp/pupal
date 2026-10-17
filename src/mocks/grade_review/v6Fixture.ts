/**
 * The grader-v6 review fixture (`v6_review_hobby.json`) as the tests read it.
 *
 * The JSON is CAPTURED, not written: the v6 grader graded the hobby bundle on
 * the scripted fake model the backend's own tests use
 * (`tests/services/test_v6_review_mvc.py::_grade`), and the server's own
 * `review()` + `undecided_checks()` built each `GradedTestV6Response` — the
 * exact shape `GET /v6` and `PATCH /v6/draft` return. Regenerate it with
 * `backend/scripts/gen_v6_review_fixture.py` (byte-identical on a re-run);
 * never hand-edit it.
 *
 * Vivi's record (`content`) is stored ONCE, because it never changes between
 * responses ("only teacher_overrides is rewritten"); each variant carries only
 * the fields that move. This reader puts the full responses back together:
 *
 *   base       no decision of hers
 *   flip       q2.א.c1.c2 moved to its middle choice
 *   pin        q1.ג.c6 set by hand — the group charge moves to q1.ג.c7 (AM-G15)
 *   undecided  a grade in which no ladder check was answered; `content` is
 *              base's with `model_option_id` null on exactly those checks (the
 *              generator asserts that is the ONLY difference that prices)
 *
 * Test-only (it reads the file system); nothing in the app imports it.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import type { GradedTestV6Response } from '@/utils/grade-review-v6-model';
import type { WireDraft } from '@/utils/grade-review-model';

type Moving = Pick<GradedTestV6Response,
    'status' | 'overrides' | 'overlay' | 'priced' | 'ai_total_score' | 'lines'
    | 'undecided_check_ids'>;

interface RawFixture {
    graded_test: {
        id: string;
        status: string;
        student_name: string;
        transcription_id: string;
        total_possible: string;
        numeric_policy: { precision: string; rounding_mode: string; sum_tolerance: string };
        draft: WireDraft & { v6: unknown };
    };
    base: GradedTestV6Response;
    flip: { check_id: string; option_id: string; response: Moving };
    pin: { terminal_id: string; amount: string; response: Moving };
    undecided: { missing_check_ids: string[]; response: Moving };
}

export const V6_FIXTURE_PATH = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)), 'v6_review_hobby.json');

export interface V6Fixture {
    /** The envelope as `GET /graded_test/{id}` serves it — `draft.v6` re-attached. */
    gradedTest: RawFixture['graded_test'];
    draft: WireDraft & { v6: unknown };
    base: GradedTestV6Response;
    flip: { checkId: string; optionId: string; response: GradedTestV6Response };
    pin: { terminalId: string; amount: string; response: GradedTestV6Response };
    undecided: { missingCheckIds: string[]; response: GradedTestV6Response };
}

export function loadV6Fixture(): V6Fixture {
    const raw = JSON.parse(readFileSync(V6_FIXTURE_PATH, 'utf-8')) as RawFixture;
    const draft = { ...raw.graded_test.draft, v6: raw.base.content };
    const missing = new Set(raw.undecided.missing_check_ids);
    const undecidedContent = {
        ...raw.base.content,
        checks: raw.base.content.checks.map((c) => (missing.has(c.plan.check_id)
            ? { ...c, model_option_id: null } : c)),
    };
    return {
        gradedTest: { ...raw.graded_test, draft },
        draft,
        base: raw.base,
        flip: {
            checkId: raw.flip.check_id,
            optionId: raw.flip.option_id,
            response: { ...raw.base, ...raw.flip.response },
        },
        pin: {
            terminalId: raw.pin.terminal_id,
            amount: raw.pin.amount,
            response: { ...raw.base, ...raw.pin.response },
        },
        undecided: {
            missingCheckIds: raw.undecided.missing_check_ids,
            response: { ...raw.base, ...raw.undecided.response, content: undecidedContent },
        },
    };
}
