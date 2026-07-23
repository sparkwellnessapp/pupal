import { notFound } from 'next/navigation';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { hydrateAnyQuestions } from '@/utils/rubric-transform';
import { validateAllQuestions } from '@/utils/rubric-validation';
import type { Annotation, SelectionGroup } from '@/lib/api';
import type { RubricQuestion } from '@/types/rubric';
import { LabFrame } from './LabFrame';

/**
 * A SYNTHETIC production-format fixture: the benchmark JSONs are hand-derived and
 * carry NO pipeline markers, so they cannot exercise the marker bug. This one
 * carries the real markers `parser_render.py` emits — `[TABLE N: RxC]` + pipe
 * rows, `[IMAGE: ...]`, `[[color:...]]...[[/color]]` — plus embedded C# code and a
 * mixed Hebrew/Latin line, so the marker/code/bidi fixes are VISIBLE.
 */
function markersDemoQuestions(): RubricQuestion[] {
    const question_text = [
        'לפניכם הפעולה Check בשפת #C:',
        'public static bool Check(int[] arr, int target)',
        '{',
        '    int sum = 0;',
        '    for (int i = 0; i < arr.Length; i++)',
        '        sum += arr[i];',
        '    return sum == target;',
        '}',
        'הטבלה הבאה מתארת את הקלט והפלט של הפעולה:',
        '[TABLE 1: 3x4]',
        '| קלט | פלט | תוצאה | הערה |',
        '|---|---|---|---|',
        '| 5 | 3 | 8 | תקין |',
        '| -2 | 4 | 2 | תקין |',
        'הערה [[color:EE0000]]חשובה[[/color]]: הפעולה Check(arr, 6) מחזירה true עבור המערך הנתון.',
        '[IMAGE: diagram_plane.png]',
    ].join('\n');
    return [{
        question_id: 'q1', question_type: 'coding_task', question_text,
        total_points: 10, sub_questions: [],
        criteria: [
            { criterion_id: 'c1', index: 0, description: 'הפעולה מחזירה את הערך הנכון', points: 6 },
            { criterion_id: 'c2', index: 1, description: 'קוד תקין וקריא, שמות משתנים משמעותיים', points: 4 },
        ],
    }];
}

/**
 * /design-lab — the DESIGN RECOVERY SUITE's "eyes" (Phase 0). Renders
 * RubricDocument deterministically for one fixture × one state, driven by
 * ?fixture=&state= query params, so `npm run snap` can capture named PNGs of
 * every combination. NO polling, NO API mocks — the golden fixtures are read
 * straight from the backend eval suite (server-side) and hydrated.
 *
 * DEV-ONLY: env-gated to notFound() in production (Next App Router can't exclude
 * a route from the bundle, but this makes it a 404 in prod). Never linked.
 */

const FIXTURES = ['bagrut_899371', 'csharp_plane_combine', 'employee_course_select1', 'foundations_cs', 'hobby_tvshow'] as const;

function loadFixture(name: string) {
    const file = path.join(process.cwd(), '..', 'backend', 'tests', 'rubric_eval_suite', 'benchmarks', `${name}.json`);
    const raw = JSON.parse(readFileSync(file, 'utf-8'));
    return {
        questions: hydrateAnyQuestions(raw.questions),
        selectionGroups: (raw.selection_groups ?? []) as SelectionGroup[],
        name: (raw.name as string | undefined) ?? name,
    };
}

export default function DesignLab({ searchParams }: { searchParams: { fixture?: string; state?: string } }) {
    if (process.env.NODE_ENV === 'production') notFound();

    const fixture = searchParams.fixture === 'markers_demo'
        ? 'markers_demo'
        : FIXTURES.includes(searchParams.fixture as typeof FIXTURES[number])
            ? (searchParams.fixture as string)
            : 'bagrut_899371';
    const state = searchParams.state ?? 'at-rest';

    const { questions, selectionGroups, name } = fixture === 'markers_demo'
        ? { questions: markersDemoQuestions(), selectionGroups: [] as SelectionGroup[], name: 'markers_demo (synthetic)' }
        : loadFixture(fixture);

    // "findings" state surfaces the REAL client-validator output (authentic anchors).
    let annotations: Annotation[] = [];
    if (state === 'findings') {
        const issues = Array.from(validateAllQuestions(questions).values()).flat();
        annotations = issues.map((iss) => ({
            id: iss.key,
            annotation_type: 'invariant_violation',
            severity: iss.severity,
            message: iss.message,
            target_id: iss.target_id === 'rubric' ? null : iss.target_id,
        }));
        // Guarantee at least one visible finding for fixtures that validate clean.
        if (annotations.length === 0 && questions[0]) {
            annotations = [{ id: 'demo', annotation_type: 'rubric_mismatch', severity: 'warning', message: 'לדוגמה: אי-התאמה בניקוד — בדקי את הסעיף', target_id: questions[0].question_id }];
        }
    }

    return (
        <LabFrame
            questions={questions}
            annotations={annotations}
            selectionGroups={selectionGroups}
            rubricName={name}
            fixture={fixture}
            state={state}
        />
    );
}
