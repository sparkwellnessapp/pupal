'use client';

/**
 * §5.1A/B — the stepper and the turn line, the two things on the page that are
 * always true and always visible.
 *
 * ── WHY THE OWNER TAG ─────────────────────────────────────────────────────
 * The flow alternates between her and Vivi six times, and nothing on the old
 * screens said so. A teacher who cannot tell whose turn it is either waits for
 * a machine that is waiting for her, or starts work that is not ready. Each
 * step therefore carries `ויוי` or `את` under its name — it costs one line and
 * it answers the question the whole PR is about.
 *
 * Purely presentational: every value comes from `deriveBatchStage`, so this
 * component cannot hold an opinion of its own about what stage the batch is in.
 * Subject-agnostic by construction — it knows steps, not content (§3.3).
 */

import { BATCH_STEPS, stepStates, type BatchStage } from '@/utils/batch-stage';
import { STEP_LABELS } from '@/copy/batch';

const TONE: Record<string, string> = {
    blue: 'bg-batch-blue-soft text-batch-blue-ink',
    amber: 'bg-batch-amber-soft text-batch-amber-ink',
    green: 'bg-batch-green-soft text-batch-green-ink',
    red: 'bg-batch-red-soft text-batch-red-ink',
};

export function StageStepper({ stage }: { stage: BatchStage }) {
    const states = stepStates(stage.step);

    return (
        <div data-testid="stage-stepper">
            <ol className="flex flex-wrap items-start gap-x-1.5 gap-y-2">
                {BATCH_STEPS.map((step, i) => {
                    const state = states[step];
                    const { label, owner } = STEP_LABELS[step];
                    return (
                        <li key={step} className="flex items-start gap-1.5">
                            {i > 0 && (
                                <span
                                    aria-hidden="true"
                                    className="mt-3 h-px w-4 bg-batch-line sm:w-6"
                                />
                            )}
                            {/* `data-stage-step`, NOT `data-step`: the grading
                                dashboard further down the page has its own
                                two-step line on `data-step`, and one attribute
                                for two different steppers makes every query
                                over either of them ambiguous. */}
                            <div
                                data-stage-step={step}
                                data-stage-step-state={state}
                                className="flex flex-col items-center gap-0.5 px-0.5"
                            >
                                <span
                                    className={[
                                        'grid h-5 w-5 place-items-center rounded-full text-[11px] font-bold',
                                        state === 'done'
                                            ? 'bg-batch-green text-white'
                                            : state === 'active'
                                                ? 'bg-primary-500 text-white'
                                                : 'border border-batch-line bg-white text-batch-faint',
                                    ].join(' ')}
                                >
                                    {state === 'done' ? '✓' : i + 1}
                                </span>
                                <span
                                    className={[
                                        'whitespace-nowrap text-[12.5px] leading-tight',
                                        state === 'active'
                                            ? 'font-semibold text-batch-ink'
                                            : state === 'done'
                                                ? 'text-batch-muted'
                                                : 'text-batch-faint',
                                    ].join(' ')}
                                >
                                    {label}
                                </span>
                                <span className="whitespace-nowrap text-[11px] leading-tight text-batch-faint">
                                    {owner}
                                </span>
                            </div>
                        </li>
                    );
                })}
            </ol>

            {stage.turnLine && (
                <p
                    data-testid="turn-line"
                    className="mt-3.5 text-[18.5px] font-semibold tracking-tight text-batch-ink"
                >
                    {stage.turnLine}
                </p>
            )}
        </div>
    );
}

/** The header chip, wearing the stage's own tone. One label, one source. */
export function StageChipView({ stage, className = '' }: {
    stage: BatchStage;
    className?: string;
}) {
    return (
        <span
            data-testid="batch-status-chip"
            data-chip={stage.chip.key}
            className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${TONE[stage.chip.tone]} ${className}`}
        >
            {stage.chip.label}
        </span>
    );
}
