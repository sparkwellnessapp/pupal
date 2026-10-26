import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { CriterionRowV6, signedPoints } from './CriterionRowV6';
import { loadV6Fixture } from '@/mocks/grade_review/v6Fixture';
import {
    buildV6ReviewModel, criterionQuoteSpans, overlayFromWire, setPin, emptyOverlayV6, type V6Criterion,
    type GradedTestV6Response,
} from '@/utils/grade-review-v6-model';
import type { NumericPolicy } from '@/lib/pricing';
import {
    V6_CHARGE_CAPPED, V6_CHARGE_MOVED, V6_CHIP, V6_COMMENT_ADD, V6_COMMENT_MINE, V6_HER_TAG,
    V6_LINE_UPDATING,
    V6_MANUAL_GRADE, V6_QUOTE_BUTTON, V6_QUOTE_NONE, V6_QUOTE_TITLE, V6_UNDECIDED, V6_VIVI_TAG,
} from '@/copy/grade-review-v6';

/**
 * The RENDER half of the v6 criterion row: SSR, no DOM, no mocks — the rows
 * are built by the real view model from the captured server responses.
 */

const fx = loadV6Fixture();
const POLICY: NumericPolicy = { precision: fx.base.content.precision, rounding_mode: 'half_up' };

function criteriaOf(response: GradedTestV6Response, options: {
    pendingLines?: Set<string>; saving?: boolean; overlay?: ReturnType<typeof overlayFromWire>;
} = {}): Map<string, V6Criterion> {
    const model = buildV6ReviewModel({
        review: response, draft: fx.draft,
        overlay: options.overlay ?? overlayFromWire(response.overlay),
        pendingLines: options.pendingLines, saving: options.saving,
    });
    return new Map(model.scopes.flatMap((s) => s.criteria).map((c) => [c.terminalId, c]));
}

function render(criterion: V6Criterion, open = true, readOnly = false): string {
    return renderToStaticMarkup(
        <CriterionRowV6
            criterion={criterion}
            policy={POLICY}
            open={open}
            onToggle={() => undefined}
            readOnly={readOnly}
        />,
    );
}

/** The visible text: tags dropped, the entities SSR escapes decoded. */
const text = (html: string) => html.replace(/<[^>]+>/g, '')
    .replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&amp;/g, '&');

describe('CriterionRowV6 — the closed row', () => {
    const base = criteriaOf(fx.base);

    it('shows HER criterion text verbatim, the grade, and the chip', () => {
        for (const c of base.values()) {
            const html = render(c, false);
            expect(text(html)).toContain(c.description);
            expect(html).toContain(`data-chip-label="${c.chip}"`);
            expect(text(html)).toContain(V6_CHIP[c.chip]);
        }
        // the fixture carries all three chips
        expect(new Set([...base.values()].map((c) => c.chip))).toStrictEqual(
            new Set(['full', 'partial', 'zero']));
    });

    it('shows the server`s reasoning line and the verified primary quote', () => {
        const withQuote = [...base.values()].find((c) => c.primaryQuote && c.line)!;
        const html = render(withQuote, false);
        expect(html).toContain('data-line-state="ready"');
        expect(text(html)).toContain(withQuote.line!.text);
        expect(html).toContain('data-primary-quote');
        expect(text(html)).toContain(withQuote.primaryQuote!);
        expect(text(html)).not.toContain(V6_MANUAL_GRADE);
    });

    it('«הציון נקבע ידנית» when she set the criterion`s grade by hand', () => {
        const pinned = criteriaOf(fx.pin.response).get(fx.pin.terminalId)!;
        const html = render(pinned, false);
        expect(html).toContain('data-pinned="true"');
        expect(text(html)).toContain(V6_MANUAL_GRADE);
        expect(html).toContain('data-clear-manual-grade');
        // the server's line for a pinned criterion IS that sentence — said once, not twice
        expect(pinned.line?.text).toBe(V6_MANUAL_GRADE);
        expect(text(html).split(V6_MANUAL_GRADE).length - 1).toBe(1);
        // read-only (an approved test): the fact stays, the way to undo it goes
        const ro = render(pinned, false, true);
        expect(text(ro)).toContain(V6_MANUAL_GRADE);
        expect(ro).not.toContain('data-clear-manual-grade');
    });

    it('«ההסבר מתעדכן…» in place of the line while her edit is saving', () => {
        const live = setPin(emptyOverlayV6(), fx.pin.terminalId, fx.pin.amount);
        const pending = criteriaOf(fx.base, {
            overlay: live, pendingLines: new Set([fx.pin.terminalId]), saving: true,
        }).get(fx.pin.terminalId)!;
        const html = render(pending, false);
        expect(html).toContain('data-line-state="updating"');
        expect(text(html)).toContain(V6_LINE_UPDATING);
        // the stale line is NOT shown beside it
        expect(text(html)).not.toContain(fx.base.lines.find((l) => l.terminal_id === fx.pin.terminalId)!.text_he);
    });
});

describe('CriterionRowV6 — opened: the choices, the charges, the notes', () => {
    it('marks Vivi`s pick and HER pick, when they differ', () => {
        const flipped = criteriaOf(fx.flip.response);
        const tid = fx.base.content.checks.find((c) => c.plan.check_id === fx.flip.checkId)!
            .plan.priced_terminal_id;
        const html = render(flipped.get(tid)!);
        const check = html.split(`data-v6-check="${fx.flip.checkId}"`)[1].split('data-v6-check=')[0];
        expect(check).toMatch(new RegExp(`data-option="${fx.flip.optionId}"[^>]*data-vivi="false"[^>]*data-hers="true"[^>]*data-effective="true"`));
        expect(check).toMatch(/data-vivi="true"[^>]*data-hers="false"[^>]*data-effective="false"/);
        expect(text(check)).toContain(V6_VIVI_TAG);
        expect(text(check)).toContain(V6_HER_TAG);
        expect(check).toContain('data-back-to-vivi');
        // the unflipped base shows Vivi's pick only
        const before = render(criteriaOf(fx.base).get(tid)!);
        const baseCheck = before.split(`data-v6-check="${fx.flip.checkId}"`)[1].split('data-v6-check=')[0];
        expect(baseCheck).not.toContain('data-her-tag');
        expect(baseCheck).toMatch(/data-vivi="true"[^>]*data-hers="false"[^>]*data-effective="true"/);
    });

    it('names the other criterion when the repeated mistake was charged here because of her pin', () => {
        const pinned = criteriaOf(fx.pin.response);
        const movedTo = fx.pin.response.priced.terminals.find((t) => t.charges.some((c) => c.moved_by_pin))!;
        const html = render(pinned.get(movedTo.terminal_id)!);
        const other = pinned.get(fx.pin.terminalId)!.description;
        expect(text(html)).toContain(V6_CHARGE_MOVED(other));
        expect(html).toContain(`data-charge-moved="${fx.pin.terminalId}"`);
    });

    it('states a capped charge with what was charged and what it would have been', () => {
        const base = criteriaOf(fx.base);
        const withFault = [...base.values()].find((c) => c.checks.some((k) => k.charge?.status === 'applied'))!;
        const capped: V6Criterion = {
            ...withFault,
            checks: withFault.checks.map((k) => (k.charge?.status === 'applied'
                ? { ...k, charge: { ...k.charge, status: 'capped' as const, charged: '-0.25' } } : k)),
        };
        const html = render(capped);
        const fault = capped.checks.find((k) => k.charge?.status === 'capped')!;
        expect(html).toContain('data-charge="capped"');
        expect(text(html)).toContain(V6_CHARGE_CAPPED(signedPoints('-0.25'), signedPoints(fault.charge!.amount)));
    });

    it('shows an observed note with «הערה:»', () => {
        const withNote = [...criteriaOf(fx.base).values()].find((c) => c.checks.some((k) => k.noteObserved))!;
        const html = render(withNote);
        expect(html).toContain('data-note-observed');
        expect(text(html)).toContain('הערה:');
    });

    it('an unanswered check wears the empty amber ring and selects nothing', () => {
        const undecided = criteriaOf(fx.undecided.response);
        const crit = [...undecided.values()].find((c) => c.undecidedCount > 0)!;
        const html = render(crit);
        expect(html).toContain('data-undecided-ring');
        expect(text(html)).toContain(V6_UNDECIDED);
        const open = html.split('data-undecided="true"')[1].split('data-v6-check=')[0];
        expect(open).not.toContain('data-effective="true"');
        expect(open).not.toContain('data-vivi="true"');
        // closed, the row says how many wait for her
        expect(render(crit, false)).toContain(`data-waiting="${crit.undecidedCount}"`);
    });

    it('her note for the student lives on the CLOSED row: add it, or read it', () => {
        const crit = [...criteriaOf(fx.base).values()][0];
        const closed = (c: V6Criterion, readOnly = false) => renderToStaticMarkup(
            <CriterionRowV6 criterion={c} policy={POLICY} open={false}
                onToggle={() => undefined} readOnly={readOnly} onNote={() => undefined} />);
        expect(closed(crit)).toContain('data-comment-add');
        expect(text(closed(crit))).toContain(V6_COMMENT_ADD);
        const noted = { ...crit, note: 'הבנת את הרעיון' };
        expect(text(closed(noted))).toContain(`${V6_COMMENT_MINE} הבנת את הרעיון`);
        expect(closed(noted)).not.toContain('data-comment-add');
        // signed: she reads it, she cannot change it
        expect(closed(crit, true)).not.toContain('data-comment-add');
        expect(text(closed(noted, true))).toContain('הבנת את הרעיון');
    });

    it('read-only: every choice is disabled and no comment can be added', () => {
        const html = render(criteriaOf(fx.flip.response).get(
            fx.base.content.checks.find((c) => c.plan.check_id === fx.flip.checkId)!.plan.priced_terminal_id)!,
        true, true);
        expect(html).toMatch(/role="radio"[^>]*disabled=""/);
        expect(html).not.toContain('data-comment-add');
        expect(html).not.toContain('data-back-to-vivi');
    });
});

describe('signedPoints', () => {
    it('a real minus sign, trimmed zeros, plain zero', () => {
        expect(signedPoints('-0.50')).toBe('−0.5');
        expect(signedPoints('1.00')).toBe('1');
        expect(signedPoints('0')).toBe('0');
        expect(signedPoints('-0')).toBe('0');
    });
});

describe('CriterionRowV6 — «ציטוט מהתשובה» (owner 2026-10-21)', () => {
    const base = criteriaOf(fx.base);
    const button = (html: string) => html.match(/<button[^>]*data-quote-button[^>]*>[^<]*<\/button>/)?.[0];
    const renderLit = (c: V6Criterion, lit = false) => renderToStaticMarkup(
        <CriterionRowV6 criterion={c} policy={POLICY} open={false} onToggle={() => undefined}
            lit={lit} onToggleLit={() => undefined} />,
    );

    it('is on every criterion, enabled where there is a verified quote, pressed when lit', () => {
        for (const c of base.values()) {
            const b = button(renderLit(c));
            expect(b, c.terminalId).toBeDefined();
            expect(text(b!)).toBe(V6_QUOTE_BUTTON);
            expect(b).toContain(criterionQuoteSpans(c).length ? V6_QUOTE_TITLE : V6_QUOTE_NONE);
        }
        const quoted = [...base.values()].find((c) => criterionQuoteSpans(c).length)!;
        expect(button(renderLit(quoted))).not.toContain('disabled');
        expect(button(renderLit(quoted, true))).toContain('aria-pressed="true"');
    });

    it('is disabled, with the reason, when the criterion has no verified quote', () => {
        const some = [...base.values()][0];
        const none: V6Criterion = { ...some, primaryQuote: null,
            checks: some.checks.map((k) => ({ ...k, quote: null, quoteKind: null })) };
        const b = button(renderLit(none))!;
        expect(b).toContain('disabled=""');
        expect(b).toContain(`title="${V6_QUOTE_NONE}"`);
        expect(b).not.toContain('aria-pressed');
    });

    it('lights ALL the criterion`s verified quotes, not only the main one', () => {
        const multi = [...base.values()].find((c) =>
            c.checks.filter((k) => k.quote && k.quoteKind).length > 1);
        if (!multi) return;          // the fixture decides; the model test pins the rule
        expect(criterionQuoteSpans(multi).length).toBe(
            multi.checks.filter((k) => k.quote && k.quoteKind).length);
    });
});
