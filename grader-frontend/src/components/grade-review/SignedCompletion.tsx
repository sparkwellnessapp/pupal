'use client';

/**
 * §5.6 — the END STATE, and the flow's ONE celebration.
 *
 * Everything about this screen is peak-end: it is the last thing she sees after
 * an evening of work, and it is the moment she decides whether to do this again
 * next week. Four things, in this order:
 *
 *   1. the ✓ card — the only green check in the whole flow (the mid-flow twin
 *      after transcription approval is deleted; two endings taught her the
 *      first one was the end);
 *   2. the HERO — a real page of a real signed exam, large, with the stamp on
 *      it. Not an illustration: the thing she made;
 *   3. the download, named for what it gives her;
 *   4. the referral, which is the only thing the product ever asks of her, at
 *      the one moment she has a reason to say yes.
 *
 * ── THE DURATION IS OMITTED, NEVER ESTIMATED ──────────────────────────────
 * `durationMinutes` is frozen by the page when it WATCHED the last signature
 * land. On a revisit it is null and the line simply does not render — a teacher
 * opening a week-old batch must not read «10080 דקות» here (C2 / §3.5a).
 *
 * ── THE REFERRAL LINK CARRIES NO ATTRIBUTION ──────────────────────────────
 * There is none in this codebase (R10). A tracked-looking link that tracks
 * nothing is worse than a plain one, so this is the plain signup URL and
 * attribution is its own PR.
 */

import { useState } from 'react';

import {
    DASH_DONE_BANNER, DONE_DURATION, DONE_HERO_ALT, DONE_HERO_OPEN, DONE_PREVIEW,
    DONE_REFERRAL, DONE_REFERRAL_COPIED, DONE_REFERRAL_COPY, DONE_REFERRAL_FAILED,
    DONE_TITLE, DASH_DOWNLOAD, DASH_CARD_NO_NAME,
} from '@/copy/grade-review';
import type { GradedItem } from '@/utils/grade-dashboard';
import { usePageThumbnails } from './usePageThumbnails';

export interface SignedCompletionProps {
    approved: number;
    failed: number;
    durationMinutes: number | null;
    /** The first signed test — the page the hero shows. Null when the feed
     *  carries no approved row with an image; the hero is then omitted rather
     *  than framed empty. */
    heroItem: GradedItem | null;
    onOpenPreview: (item: GradedItem) => void;
    onDownload: () => void;
    /** «N מבחנים נכשלו בבדיקה…» — stated, never folded into the celebration. */
    failuresLine: string | null;
}

export function SignedCompletion({
    approved, durationMinutes, heroItem, onOpenPreview, onDownload, failuresLine,
}: SignedCompletionProps) {
    const { register, urlFor } = usePageThumbnails();
    const [copied, setCopied] = useState<'idle' | 'done' | 'failed'>('idle');
    const heroUrl = urlFor(heroItem?.page1_image_url);
    const heroName = heroItem?.student_name || DASH_CARD_NO_NAME;

    const signupUrl = typeof window === 'undefined'
        ? '' : `${window.location.origin}/signup`;

    const copyLink = async () => {
        try {
            // `navigator.clipboard` is undefined outside a secure context, so
            // optional-chaining it is not defensiveness — a plain call THROWS
            // a TypeError there, which this catch would swallow into the same
            // branch anyway; being explicit says which failure we expect.
            await navigator.clipboard?.writeText(signupUrl);
            if (!navigator.clipboard) throw new Error('no clipboard');
            setCopied('done');
            // The confirmation is a receipt, not a state. Left latched it
            // still reads «הועתק» ten minutes later, so a second click looks
            // like it did nothing.
            window.setTimeout(() => setCopied('idle'), 4000);
        } catch {
            // Denied in plenty of ordinary situations — an insecure origin, a
            // locked-down school browser. The failure message tells her to copy
            // the address, so the address has to APPEAR (below); saying that
            // while showing nothing is an instruction she cannot follow.
            setCopied('failed');
        }
    };

    return (
        <section
            data-testid="completion-hero"
            data-attention="done"
            className="mb-5 rounded-grade border border-grade-teal-line bg-primary-50 px-6 py-6
                text-center"
        >
            <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-full
                bg-batch-green text-3xl text-white motion-safe:animate-check-pop">
                ✓
            </div>
            <h3 className="text-gr-h1 text-grade-ink">{DONE_TITLE(approved)}</h3>
            {durationMinutes !== null && (
                <p className="mt-1 text-gr-body text-grade-pencil" data-testid="done-duration">
                    {DONE_DURATION(durationMinutes)}
                </p>
            )}
            <p className="mt-1 text-gr-body text-primary-700">{DASH_DONE_BANNER}</p>
            {failuresLine && (
                <p className="mt-1 text-gr-meta text-grade-amber-ink" data-testid="done-failures">
                    {failuresLine}
                </p>
            )}

            {/* The hero — what she actually made, at a size worth looking at.
                Gated on the URL, not just the item: without one the frame is a
                large empty rectangle in the middle of the celebration, which
                reads as a failed image rather than as a missing one. Degrade by
                omission (§3.5a) — the pile below still shows every stamp. */}
            {heroItem?.page1_image_url && (
                <div className="mt-5 flex flex-col items-center">
                    <button
                        type="button"
                        onClick={() => onOpenPreview(heroItem)}
                        title={DONE_HERO_OPEN}
                        data-testid="done-hero"
                        className="block w-full max-w-hero-page overflow-hidden rounded-grade-sm
                            border border-grade-line bg-grade-paper shadow-grade
                            transition-transform hover:-translate-y-0.5"
                    >
                        <span
                            ref={(el) => register(el, heroItem.page1_image_url ?? null)}
                            className="relative block aspect-[1/1.32] w-full"
                        >
                            {heroUrl ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                    src={heroUrl}
                                    alt={DONE_HERO_ALT(heroName)}
                                    className="absolute inset-0 h-full w-full object-cover object-top"
                                />
                            ) : null}
                        </span>
                    </button>
                    <button
                        type="button"
                        onClick={() => onOpenPreview(heroItem)}
                        className="mt-1.5 text-gr-meta text-primary-700 underline underline-offset-link"
                    >
                        {DONE_PREVIEW}
                    </button>
                </div>
            )}

            <div className="mt-5">
                <button
                    type="button"
                    data-download
                    onClick={onDownload}
                    className="inline-flex items-center gap-2 rounded-grade-ctl border
                        border-primary-600 bg-primary-600 px-5 py-2.5 text-gr-body
                        font-medium text-white hover:bg-primary-700"
                >
                    {DASH_DOWNLOAD}
                </button>
            </div>

            <p className="mt-4 text-gr-meta text-grade-pencil" data-testid="done-referral">
                {DONE_REFERRAL}{' '}
                <button
                    type="button"
                    onClick={() => { void copyLink(); }}
                    className="text-primary-700 underline underline-offset-link"
                >
                    {copied === 'done' ? DONE_REFERRAL_COPIED
                        : copied === 'failed' ? DONE_REFERRAL_FAILED
                            : DONE_REFERRAL_COPY}
                </button>
            </p>
            {/* The address itself, only when the copy failed — so «אפשר להעתיק
                מהכתובת» names something she can actually select. LTR-isolated:
                a URL inside an RTL paragraph reorders around its slashes. */}
            {copied === 'failed' && (
                <p
                    dir="ltr"
                    data-testid="done-referral-url"
                    className="mt-1 select-all text-gr-meta text-grade-pencil
                        [unicode-bidi:isolate]"
                >
                    {signupUrl}
                </p>
            )}
        </section>
    );
}
