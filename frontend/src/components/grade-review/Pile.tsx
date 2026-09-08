'use client';

import { formatPoints } from '@/utils/points-display';
import {
    pileCardState, pileCardTarget, type GradedItem, type PileCardState,
} from '@/utils/grade-dashboard';
import {
    DASH_CARD_ALT, DASH_CARD_APPROVED, DASH_CARD_DRAFT, DASH_CARD_FAILED,
    DASH_CARD_GRADING, DASH_CARD_GRADING_CAPTION, DASH_CARD_LANDED, DASH_CARD_MARKED,
    DASH_CARD_NO_NAME, DASH_CARD_PENDING, DASH_CARD_RETRIED, DASH_CARD_RETRY,
    DASH_CARD_STALE_VERSION, DASH_PILE_EMPTY,
} from '@/copy/grade-review';
import { StampSvg } from './StampSvg';
import { usePageThumbnails } from './usePageThumbnails';

/**
 * The Pile (D6) — one page-1 thumbnail per test, in FROZEN landing order.
 *
 * It is the batch made physical: a stack of papers on a desk, each showing
 * enough of itself to be recognised. The ink grammar does the rest — a grey
 * number is Vivi's proposal, a red stamp is the teacher's signature, and
 * nothing else on the card is ever red.
 *
 * ── THE STATE GRAMMAR IS THE CAPTION ─────────────────────────────────────
 * Each state says a different KIND of thing, not a different degree:
 *   pending / grading   nothing to do yet — dimmed, no number
 *   landed              a grade exists and is clean
 *   landed_marked       …and k things want her eye
 *   draft               she has been in it; her work is saved
 *   approved            signed — the stamp, and only here
 *   failed              dashed red and a way to try again
 *
 * ── WHAT IS NOT HERE ─────────────────────────────────────────────────────
 * A `look_count` of `null` renders NO number. It means the draft would not
 * parse, so the count is not computable — and "0" would read as "nothing to
 * check" about precisely the test that most needs her (CLAUDE.md §3.5a).
 */

const TONE: Record<PileCardState, string> = {
    pending: 'opacity-40 bg-grade-bar',
    grading: 'opacity-60',
    landed: '',
    landed_marked: '',
    draft: '',
    approved: '',
    failed: 'border-dashed border-grade-red',
};

export interface PileProps {
    items: readonly GradedItem[];
    /** Failed tests already sent back to grading this session — their card
     *  says so and stops offering the same click (see DASH_CARD_RETRIED). */
    retriedIds?: ReadonlySet<string>;
    onOpenReview: (item: GradedItem) => void;
    onOpenPreview: (item: GradedItem) => void;
    onRetry: (item: GradedItem) => void;
}

export function Pile({ items, retriedIds, onOpenReview, onOpenPreview, onRetry }: PileProps) {
    const { register, urlFor } = usePageThumbnails();

    if (items.length === 0) {
        return (
            <p className="rounded-grade border border-dashed border-grade-line
                bg-grade-card px-6 py-8 text-center text-gr-body text-grade-pencil">
                {DASH_PILE_EMPTY}
            </p>
        );
    }

    return (
        <div
            data-pile
            className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3
                lg:grid-cols-[repeat(auto-fill,minmax(150px,1fr))]"
        >
            {items.map((item) => {
                const state = pileCardState(item);
                const target = pileCardTarget(item);
                const name = item.student_name || DASH_CARD_NO_NAME;
                const thumb = urlFor(item.page1_image_url);
                const markers = item.look_count;
                const retried = retriedIds?.has(item.graded_test_id) ?? false;

                const open = () => {
                    if (target === 'review') onOpenReview(item);
                    else if (target === 'preview') onOpenPreview(item);
                    else if (target === 'retry' && !retried) onRetry(item);
                };

                return (
                    <div
                        key={item.graded_test_id}
                        data-pile-card={item.graded_test_id}
                        data-card-state={state}
                    >
                        <button
                            type="button"
                            disabled={target === null || (target === 'retry' && retried)}
                            onClick={open}
                            aria-label={`${name} — ${captionText(state, markers, item.version, retried)}`}
                            className="block w-full rounded-grade-sm text-start outline-none
                                focus-visible:ring-decided focus-visible:ring-primary-600
                                disabled:cursor-default"
                        >
                            <div
                                ref={(el) => register(el, item.page1_image_url ?? null)}
                                className={[
                                    'relative aspect-[1/1.32] overflow-hidden rounded-grade-sm',
                                    'border border-grade-line bg-grade-paper shadow-grade',
                                    'transition-transform',
                                    target ? 'hover:-translate-y-0.5' : '',
                                    TONE[state],
                                ].join(' ')}
                            >
                                {thumb ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                        src={thumb}
                                        alt={DASH_CARD_ALT(name)}
                                        className="absolute inset-0 h-full w-full object-cover
                                            object-top"
                                    />
                                ) : null}

                                {state === 'approved' ? (
                                    <span className="absolute left-0.5 top-0.5">
                                        <StampSvg
                                            score={formatPoints(item.total_awarded ?? '')}
                                            size={64}
                                        />
                                    </span>
                                ) : item.total_awarded != null
                                    && state !== 'pending' && state !== 'grading' ? (
                                        <span
                                            dir="ltr"
                                            data-card-score
                                            /* The scrim is not decoration. The
                                               number sits on a PHOTOGRAPH of
                                               handwriting, and a real scan has
                                               ink everywhere — without it the
                                               grade is legible only where the
                                               page happens to be blank. The
                                               mockup got away with none because
                                               its strokes are generated. */
                                            className="absolute left-1.5 top-1.5 rounded-grade-sm
                                                bg-grade-paper/85 px-1.5 py-0.5 text-gr-score
                                                text-grade-pencil backdrop-blur-scrim
                                                [font-variant-numeric:tabular-nums]
                                                [unicode-bidi:isolate]"
                                        >
                                            {formatPoints(item.total_awarded)}
                                        </span>
                                    ) : null}

                                {state === 'grading' ? (
                                    <span className="absolute inset-x-0 bottom-2 text-center
                                        text-gr-label font-medium text-primary-700">
                                        {DASH_CARD_GRADING}
                                        <i className="ms-1.5 inline-block h-0.5 w-5 rounded-sm
                                            bg-primary-600 align-middle
                                            motion-safe:animate-pencil-line
                                            [transform-origin:right]" />
                                    </span>
                                ) : null}
                            </div>

                            <div className="mt-2 text-gr-body font-semibold leading-tight">
                                {name}
                            </div>
                            <Caption
                                state={state}
                                markers={markers}
                                version={item.version}
                                retried={retried}
                                onRetry={() => onRetry(item)}
                            />
                        </button>
                    </div>
                );
            })}
        </div>
    );
}

/**
 * D6: a REVISION (`version > 1`) of a signed test carries «גרסה n · לא נחתם» —
 * APPENDED to the state caption, as the mockup's `card()` appends `extra`, so a
 * marked revision keeps its «k לבדוק» and its amber dot. Approved and failed
 * keep their own captions; pending and grading have no signature to have lost.
 * (The feed sends `version: 1` for every row today — reported — so this is the
 * frontend's half of a contract the wire does not yet honour.)
 */
function revisionSuffix(state: PileCardState, version: number | undefined): string | null {
    const v = version ?? 1;
    if (v <= 1) return null;
    if (state === 'approved' || state === 'failed'
        || state === 'pending' || state === 'grading') return null;
    return DASH_CARD_STALE_VERSION(v);
}

function stateCaption(state: PileCardState, markers: number | null | undefined): string {
    switch (state) {
        case 'pending': return DASH_CARD_PENDING;
        // The thumb already says «ויוי מנקדת»; the caption says what is
        // happening to THIS test, as the mockup's card does.
        case 'grading': return DASH_CARD_GRADING_CAPTION;
        case 'draft': return DASH_CARD_DRAFT;
        case 'approved': return DASH_CARD_APPROVED;
        case 'failed': return DASH_CARD_FAILED;
        case 'landed_marked': return DASH_CARD_MARKED(markers ?? 0);
        default: return DASH_CARD_LANDED;
    }
}

function captionText(
    state: PileCardState, markers: number | null | undefined, version?: number, retried = false,
): string {
    if (state === 'failed' && retried) return DASH_CARD_RETRIED;
    const suffix = revisionSuffix(state, version);
    const base = stateCaption(state, markers);
    return suffix ? `${base} · ${suffix}` : base;
}

function Caption({
    state, markers, version, retried, onRetry,
}: {
    state: PileCardState;
    markers: number | null | undefined;
    version?: number;
    retried: boolean;
    onRetry: () => void;
}) {
    const base = 'mt-0.5 text-gr-meta';
    const suffix = revisionSuffix(state, version);
    const tail = suffix ? (
        <span data-card-revision className="text-grade-pencil"> · {suffix}</span>
    ) : null;

    if (state === 'failed') {
        if (retried) {
            return (
                <div data-card-retried className={`${base} text-grade-pencil`}>
                    {DASH_CARD_RETRIED}
                </div>
            );
        }
        return (
            <div className={`${base} text-grade-red`}>
                {DASH_CARD_FAILED} ·{' '}
                <span
                    role="link"
                    tabIndex={-1}
                    onClick={(e) => { e.stopPropagation(); onRetry(); }}
                    className="cursor-pointer underline underline-offset-link"
                >
                    {DASH_CARD_RETRY}
                </span>
            </div>
        );
    }
    if (state === 'landed_marked') {
        return (
            <div className={`${base} text-grade-amber`}>
                <span aria-hidden="true" className="me-1.5 inline-block h-dot w-dot
                    rounded-full bg-grade-amber-dot relative top-px" />
                {DASH_CARD_MARKED(markers ?? 0)}
                {tail}
            </div>
        );
    }
    if (state === 'approved') {
        return <div className={`${base} text-primary-700`}>{DASH_CARD_APPROVED}</div>;
    }
    return (
        <div className={`${base} text-grade-pencil`}>
            {stateCaption(state, markers)}
            {tail}
        </div>
    );
}
