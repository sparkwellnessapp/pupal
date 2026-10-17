import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { priceV6 } from '@/lib/pricing-v6';
import { loadV6Fixture } from '@/mocks/grade_review/v6Fixture';
import {
    blockersV6, buildV6ReviewModel, chooseOption, clearPin, criterionDescriptions,
    emptyOverlayV6, feedbackPatch, isV6Draft, overlayFromWire, overlayPatch,
    pricingOverlayOf, setComment, setPin, touchedTerminals, undecidedChecks, viewOf,
    withdrawOption, type OverlayV6,
} from './grade-review-v6-model';

/**
 * The v6 review model against the SERVER's own output (no mocks).
 *
 * The fixture is a real v6 grade and the exact `GradedTestV6Response`s the
 * endpoints built for it — Vivi's record alone, after a flip, after a pin, and
 * a grade with unanswered checks (see `mocks/grade_review/v6Fixture.ts`). The
 * load-bearing claim is the first block: the view this client builds from
 * `content`, priced by the TS pricer under the overlay the server stored,
 * equals the server's `priced` BYTE FOR BYTE — so the number she reviews is
 * the number that freezes.
 */

const fx = loadV6Fixture();
const view = viewOf(fx.base.content);
const terminalOf = new Map(fx.base.content.checks.map(
    (c) => [c.plan.check_id, c.plan.priced_terminal_id]));
const aiResolved = (checkId: string) =>
    priceV6(view).checks.find((c) => c.check_id === checkId) as NonNullable<
        ReturnType<typeof priceV6>['checks'][number]>;

describe('content → view → priceV6 equals the server`s priced', () => {
    it('Vivi`s record alone', () => {
        expect(priceV6(view, pricingOverlayOf(overlayFromWire(fx.base.overlay))))
            .toStrictEqual(fx.base.priced);
        expect(priceV6(view).total_score).toBe(fx.base.ai_total_score);
    });

    it('after the flip (a PATCH response)', () => {
        const priced = priceV6(view, pricingOverlayOf(overlayFromWire(fx.flip.response.overlay)));
        expect(priced).toStrictEqual(fx.flip.response.priced);
        expect(priced.total_score).not.toBe(fx.base.priced.total_score);
    });

    it('after the pin — and the group charge moved, as the server says', () => {
        const priced = priceV6(view, pricingOverlayOf(overlayFromWire(fx.pin.response.overlay)));
        expect(priced).toStrictEqual(fx.pin.response.priced);
        const moved = priced.terminals.flatMap((t) => t.charges).filter((c) => c.moved_by_pin);
        expect(moved).toHaveLength(1);
        expect(moved[0].moved_from_terminal_id).toBe(fx.pin.terminalId);
    });

    it('a grade with unanswered checks', () => {
        const content = fx.undecided.response.content;
        expect(priceV6(viewOf(content), pricingOverlayOf(overlayFromWire(fx.undecided.response.overlay))))
            .toStrictEqual(fx.undecided.response.priced);
    });
});

describe('her edits produce the overlay the server stored, and only her keys travel', () => {
    it('choosing the middle option = the flip; the patch carries that one record', () => {
        const mine = chooseOption(emptyOverlayV6(), fx.flip.checkId, fx.flip.optionId,
            aiResolved(fx.flip.checkId));
        expect(mine).toStrictEqual(overlayFromWire(fx.flip.response.overlay));
        expect(overlayPatch(emptyOverlayV6(), mine)).toStrictEqual({
            checks: { [fx.flip.checkId]: { option_id: fx.flip.optionId, comment: null } },
        });
        expect([...touchedTerminals(emptyOverlayV6(), mine, terminalOf)])
            .toStrictEqual([terminalOf.get(fx.flip.checkId)]);
    });

    it('choosing Vivi`s own standing pick withdraws hers; the patch withdraws with null', () => {
        const mine = chooseOption(emptyOverlayV6(), fx.flip.checkId, fx.flip.optionId,
            aiResolved(fx.flip.checkId));
        const vivi = aiResolved(fx.flip.checkId);
        expect(vivi.source).toBe('model');
        const back = chooseOption(mine, fx.flip.checkId, vivi.option_id as string, vivi);
        expect(back).toStrictEqual(emptyOverlayV6());
        expect(withdrawOption(mine, fx.flip.checkId)).toStrictEqual(emptyOverlayV6());
        expect(overlayPatch(mine, back)).toStrictEqual({ checks: { [fx.flip.checkId]: null } });
    });

    it('a comment keeps her option, travels with it, and touches no line', () => {
        const mine = chooseOption(emptyOverlayV6(), fx.flip.checkId, fx.flip.optionId,
            aiResolved(fx.flip.checkId));
        const noted = setComment(mine, fx.flip.checkId, 'חלקי בלבד');
        expect(overlayPatch(mine, noted)).toStrictEqual({
            checks: { [fx.flip.checkId]: { option_id: fx.flip.optionId, comment: 'חלקי בלבד' } },
        });
        expect(touchedTerminals(mine, noted, terminalOf).size).toBe(0);
        // a comment alone (no option) is still a record — Vivi's pick stands beside it
        const onlyNote = setComment(emptyOverlayV6(), fx.flip.checkId, 'הערה');
        expect(onlyNote.checks[fx.flip.checkId]).toStrictEqual({ option_id: null, comment: 'הערה' });
        expect(setComment(onlyNote, fx.flip.checkId, '   ')).toStrictEqual(emptyOverlayV6());
    });

    it('a pin = the pin response; clearing it sends null; an equal re-type sends nothing', () => {
        const pinned = setPin(emptyOverlayV6(), fx.pin.terminalId, fx.pin.amount);
        expect(pinned).toStrictEqual(overlayFromWire(fx.pin.response.overlay));
        expect(overlayPatch(emptyOverlayV6(), pinned))
            .toStrictEqual({ terminal_points: { [fx.pin.terminalId]: fx.pin.amount } });
        expect(overlayPatch(pinned, clearPin(pinned, fx.pin.terminalId)))
            .toStrictEqual({ terminal_points: { [fx.pin.terminalId]: null } });
        expect(overlayPatch(pinned, setPin(pinned, fx.pin.terminalId, '2.00'))).toBeNull();
        expect([...touchedTerminals(emptyOverlayV6(), pinned, terminalOf)]).toStrictEqual([fx.pin.terminalId]);
    });

    it('feedback: only the texts she changed', () => {
        expect(feedbackPatch({ summary: 'א' }, { summary: 'א', 'q1.א': 'ב' })).toStrictEqual({ 'q1.א': 'ב' });
        expect(feedbackPatch({ summary: 'א' }, {})).toStrictEqual({ summary: null });
    });
});

describe('undecided checks and the blockers mirror the server', () => {
    const content = fx.undecided.response.content;
    const ai = priceV6(viewOf(content));

    it('undecidedChecks = the server`s undecided_check_ids', () => {
        const mine = undecidedChecks(content, ai, overlayFromWire(fx.undecided.response.overlay));
        expect(mine).toStrictEqual(fx.undecided.response.undecided_check_ids);
        expect(mine.length).toBe(fx.undecided.missingCheckIds.length);
        expect(undecidedChecks(fx.base.content, priceV6(view), emptyOverlayV6()))
            .toStrictEqual(fx.base.undecided_check_ids);
    });

    it('one blocker per question, counting its open checks; deciding them all clears it', () => {
        const open = undecidedChecks(content, ai, emptyOverlayV6());
        const blockers = blockersV6(fx.draft, content, emptyOverlayV6(), open);
        expect(blockers.length).toBeGreaterThan(0);
        expect(blockers.every((b) => b.scopeId !== null)).toBe(true);

        let decided: OverlayV6 = emptyOverlayV6();
        for (const id of open) {
            const r = ai.checks.find((c) => c.check_id === id)!;
            decided = chooseOption(decided, id, r.option_id as string, r);   // her zero is a decision
        }
        const left = undecidedChecks(content, ai, decided);
        expect(left).toStrictEqual([]);
        expect(blockersV6(fx.draft, content, decided, left)).toStrictEqual([]);
    });

    it('a criterion set by hand decides its checks', () => {
        const open = undecidedChecks(content, ai, emptyOverlayV6());
        const tid = terminalOf.get(open[0]) as string;
        const pinned = setPin(emptyOverlayV6(), tid, '0');
        expect(undecidedChecks(content, ai, pinned)).not.toContain(open[0]);
    });
});

describe('buildV6ReviewModel', () => {
    const model = buildV6ReviewModel({
        review: fx.base, draft: fx.draft, overlay: overlayFromWire(fx.base.overlay),
    });
    const criteria = model.scopes.flatMap((s) => s.criteria);
    const described = criterionDescriptions(fx.draft);

    it('totals are the pricer`s, never a re-sum', () => {
        expect(model.total).toBe(fx.base.priced.total_score);
        expect(model.possible).toBe(fx.base.priced.total_possible);
        expect(model.anyOverride).toBe(false);
        expect(model.blockers).toStrictEqual([]);
    });

    it('every criterion appears exactly once, with HER text verbatim, the chip and the line', () => {
        expect(criteria.map((c) => c.terminalId).sort())
            .toStrictEqual(fx.base.content.view_terminals.map((t) => t.terminal_id).sort());
        const lines = new Map(fx.base.lines.map((l) => [l.terminal_id, l]));
        const priced = new Map(fx.base.priced.terminals.map((t) => [t.terminal_id, t]));
        for (const c of criteria) {
            expect(c.description).toBe(described.get(c.terminalId)?.description);
            expect(c.description).not.toBe('');
            expect(c.chip).toBe(priced.get(c.terminalId)?.chip);
            expect(c.awarded).toBe(priced.get(c.terminalId)?.awarded);
            expect(c.line?.text).toBe(lines.get(c.terminalId)?.text_he);
            expect(c.linePending).toBe(false);
            expect(c.pinned).toBe(false);
        }
    });

    it('the primary quote is the primary credit check`s, only when verified', () => {
        const records = new Map(fx.base.content.checks.map((c) => [c.plan.check_id, c]));
        for (const t of fx.base.priced.terminals) {
            const c = criteria.find((x) => x.terminalId === t.terminal_id)!;
            const primary = t.primary_check_id ? records.get(t.primary_check_id) : undefined;
            const verified = primary && ['exact', 'fuzzy'].includes(primary.quote_status ?? '');
            expect(c.primaryQuote).toBe(verified && primary?.evidence_quote ? primary.evidence_quote : null);
        }
        expect(criteria.some((c) => c.primaryQuote !== null)).toBe(true);
    });

    it('Vivi`s pick vs hers, after the flip', () => {
        const flipped = buildV6ReviewModel({
            review: fx.flip.response, draft: fx.draft,
            overlay: overlayFromWire(fx.flip.response.overlay),
        });
        const check = flipped.scopes.flatMap((s) => s.criteria).flatMap((c) => c.checks)
            .find((c) => c.checkId === fx.flip.checkId)!;
        const vivi = check.options.find((o) => o.vivi)!;
        const hers = check.options.find((o) => o.hers)!;
        expect(hers.optionId).toBe(fx.flip.optionId);
        expect(vivi.optionId).not.toBe(hers.optionId);
        expect(hers.effective).toBe(true);
        expect(vivi.effective).toBe(false);
        expect(flipped.total).toBe(fx.flip.response.priced.total_score);
        expect(flipped.anyOverride).toBe(true);
    });

    it('the moved charge names the OTHER criterion by her own words', () => {
        const pinned = buildV6ReviewModel({
            review: fx.pin.response, draft: fx.draft,
            overlay: overlayFromWire(fx.pin.response.overlay),
        });
        const all = pinned.scopes.flatMap((s) => s.criteria);
        expect(all.find((c) => c.terminalId === fx.pin.terminalId)?.pinned).toBe(true);
        const moved = all.flatMap((c) => c.checks).find((c) => c.charge?.movedFrom);
        expect(moved?.charge?.movedFrom).toStrictEqual({
            terminalId: fx.pin.terminalId,
            description: described.get(fx.pin.terminalId)?.description,
        });
    });

    it('a line is «updating» for the criterion she touched, and for one whose grade moved under a pending save', () => {
        const live = setPin(emptyOverlayV6(), fx.pin.terminalId, fx.pin.amount);
        const pending = buildV6ReviewModel({
            review: fx.base, draft: fx.draft, overlay: live,
            pendingLines: new Set([fx.pin.terminalId]), saving: true,
        });
        const byId = new Map(pending.scopes.flatMap((s) => s.criteria).map((c) => [c.terminalId, c]));
        expect(byId.get(fx.pin.terminalId)?.linePending).toBe(true);
        const movedTo = fx.pin.response.priced.terminals.find((t) => t.charges.some((c) => c.moved_by_pin))!;
        expect(byId.get(movedTo.terminal_id)?.linePending).toBe(true);
        // …and once the PATCH response is in, both show the server's lines
        const landed = buildV6ReviewModel({ review: fx.pin.response, draft: fx.draft, overlay: live });
        const after = new Map(landed.scopes.flatMap((s) => s.criteria).map((c) => [c.terminalId, c]));
        expect(after.get(fx.pin.terminalId)?.linePending).toBe(false);
        expect(after.get(fx.pin.terminalId)?.line?.source).toBe('teacher_override');
        expect(after.get(movedTo.terminal_id)?.line?.text)
            .toBe(fx.pin.response.lines.find((l) => l.terminal_id === movedTo.terminal_id)?.text_he);
    });
});

describe('routing predicate', () => {
    it('a v6 draft routes to v6', () => {
        expect(isV6Draft(fx.draft)).toBe(true);
    });

    it('every published v5 draft (and a v6 block of another schema) does not', () => {
        const here = path.dirname(fileURLToPath(import.meta.url));
        const dir = path.resolve(here, '../../../backend/tests/fixtures/grade_review');
        const drafts = readdirSync(dir).filter((f) => /^(draft|approved)_.*\.json$/.test(f));
        expect(drafts.length).toBeGreaterThan(5);
        for (const name of drafts) {
            const json = JSON.parse(readFileSync(path.join(dir, name), 'utf-8'));
            expect(isV6Draft(json.draft ?? json), name).toBe(false);
        }
        expect(isV6Draft({ v6: null })).toBe(false);
        expect(isV6Draft({ v6: { plan_schema: 'plan/v7' } })).toBe(false);
        expect(isV6Draft(null)).toBe(false);
    });
});
