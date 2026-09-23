'use client';

/**
 * The student profile — /my-classroom/students/[studentId]
 * (PR_student_profile.md §6.2; the «Profile» and «Empty» artboards).
 *
 * A QUIET LEDGER. Name, classes, count; then one row per approved test — the
 * stamped page 1, the exam event, «בדיקה אושרה ב…», the grade — and one click
 * to the returned exam. Nothing here is computed across tests except the
 * count (UI-1 NoAggregates): Vivi proposes elsewhere; on this page she does
 * not even propose.
 *
 * Two requests, deliberately: the student (header) and `signed-tests` (rows).
 * The rows carry everything a row draws — the resolved stamp position rides
 * the payload — so there is no per-row detail call, and the thumbnails load
 * lazily through the SAME cache the batch dashboard's pile uses (FA-4, M-A8):
 * thirty rows must not fire thirty fetches on paint.
 */

import { ChevronLeft, Pencil, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog, InlineError } from '@/components/classroom/ConfirmDialog';
import { StudentAvatar } from '@/components/classroom/StudentAvatar';
import { StudentNameDialog } from '@/components/classroom/StudentNameDialog';
import { StampedPage } from '@/components/grade-review/StampedPage';
import { usePageThumbnails } from '@/components/grade-review/usePageThumbnails';
import { SidebarLayout } from '@/components/SidebarLayout';
import {
    CL_APPROVED_AT, CL_BREADCRUMB_ROOT, CL_BREADCRUMB_SEP, CL_DELETE_BLOCKED,
    CL_DELETE_STUDENT, CL_EDIT_NAME, CL_EMPTY_BODY, CL_EMPTY_TITLE, CL_GRADE_OF,
    CL_LOAD_FAILED, CL_NOT_FOUND, CL_SIGNED_COUNT, CL_SIGNED_SECTION, CL_THUMB_ALT,
    CL_TRUNCATED,
} from '@/copy/classroom';
import {
    ApiError, ClassroomConflictError, STUDENT_HAS_DATA, deleteStudent, getStudent,
    getStudentSignedTests, updateStudent, type SignedTestItem, type SignedTestsResponse,
} from '@/lib/api';
import type { StudentDetailResponse } from '@/types/classroom';
import { examEventTitle } from '@/utils/exam-event';
import { formatPoints } from '@/utils/points-display';
import { returnedExamHref } from '@/utils/return-context';
import { formatSignedAt } from '@/utils/returned-exam';

const ROSTER = '/my-classroom';

function decimalText(value: string | number | null | undefined): string {
    return formatPoints(value == null ? null : String(value));
}

export default function StudentProfilePage() {
    const params = useParams<{ studentId: string }>();
    const router = useRouter();

    const [student, setStudent] = useState<StudentDetailResponse | null>(null);
    const [signed, setSigned] = useState<SignedTestsResponse | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);

    const [editing, setEditing] = useState(false);
    const [editLoading, setEditLoading] = useState(false);
    const [editError, setEditError] = useState<string | null>(null);

    const [confirmDelete, setConfirmDelete] = useState(false);
    const [deleteLoading, setDeleteLoading] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    /** §5.4 — the interim refusal, shown in place instead of a dialog. */
    const [deleteBlocked, setDeleteBlocked] = useState(false);

    const { register, urlFor } = usePageThumbnails();

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const [detail, tests] = await Promise.all([
                    getStudent(params.studentId),
                    getStudentSignedTests(params.studentId),
                ]);
                if (cancelled) return;
                setStudent(detail);
                setSigned(tests);
            } catch (err) {
                if (cancelled) return;
                // A deleted or foreign student is a 404 (LST-5): back to the
                // roster with a word, never a blank page or a crash.
                if (err instanceof ApiError && err.status === 404) {
                    toast.error(CL_NOT_FOUND);
                    router.replace(ROSTER);
                    return;
                }
                setLoadError(CL_LOAD_FAILED);
            }
        })();
        return () => { cancelled = true; };
    }, [params.studentId, router]);

    const onRename = useCallback(async (fullName: string) => {
        if (!student) return;
        setEditLoading(true);
        setEditError(null);
        try {
            const updated = await updateStudent(student.id, { full_name: fullName });
            setStudent((prev) => (prev ? { ...prev, full_name: updated.full_name } : prev));
            setEditing(false);
        } catch (err) {
            setEditError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה בעדכון התלמיד/ה');
        } finally {
            setEditLoading(false);
        }
    }, [student]);

    const onDeleteClick = useCallback(() => {
        // Interim (§5.4, M-A2): a student with signed tests cannot be deleted
        // yet. The trash says so in place rather than opening a dialog that
        // can only end in a refusal.
        if ((signed?.signed_tests_count ?? 0) > 0) {
            setDeleteBlocked(true);
            return;
        }
        setDeleteError(null);
        setConfirmDelete(true);
    }, [signed]);

    const onDelete = useCallback(async () => {
        if (!student) return;
        setDeleteLoading(true);
        setDeleteError(null);
        try {
            await deleteStudent(student.id);
            toast.success('המחיקה הושלמה');
            router.replace(ROSTER);
        } catch (err) {
            // Drafts and scans exist without a signed test: the server is the
            // one that knows, and its code maps to the same sentence.
            if (err instanceof ClassroomConflictError && err.detail === STUDENT_HAS_DATA) {
                setConfirmDelete(false);
                setDeleteBlocked(true);
            } else {
                setDeleteError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה במחיקת התלמיד/ה');
            }
        } finally {
            setDeleteLoading(false);
        }
    }, [router, student]);

    const countText = signed ? CL_SIGNED_COUNT(signed.signed_tests_count) : null;

    return (
        <SidebarLayout>
            <div className="max-w-4xl mx-auto" dir="rtl" data-student-profile>
                {/* Breadcrumb */}
                <nav aria-label="ניווט" className="mb-6 flex items-center gap-2 text-sm text-gray-500">
                    <Link href={ROSTER} className="text-primary-700 hover:underline">
                        {CL_BREADCRUMB_ROOT}
                    </Link>
                    <span aria-hidden="true">{CL_BREADCRUMB_SEP}</span>
                    <span className="truncate text-gray-700">{student?.full_name ?? ''}</span>
                </nav>

                {loadError ? <InlineError message={loadError} /> : null}

                {!student || !signed ? (
                    !loadError ? <ProfileSkeleton /> : null
                ) : (
                    <>
                        {/* Header */}
                        <header className="flex items-start gap-5" data-profile-header>
                            <StudentAvatar size="lg" />
                            <div className="min-w-0 flex-1">
                                <h1 className="break-words text-3xl font-bold leading-tight text-gray-900">
                                    {student.full_name}
                                </h1>
                                <div className="mt-2 flex flex-wrap items-center gap-3">
                                    {student.classes.map((c) => (
                                        <span
                                            key={c.id}
                                            data-class-chip
                                            className="rounded-full border border-primary-200 bg-white px-3 py-1
                                                text-sm text-primary-700"
                                        >
                                            {c.name}
                                        </span>
                                    ))}
                                    {countText ? (
                                        <span data-signed-count className="whitespace-nowrap text-sm text-gray-500">
                                            {countText}
                                        </span>
                                    ) : null}
                                </div>
                            </div>
                            <div className="flex items-center gap-1">
                                <button
                                    type="button"
                                    aria-label={CL_EDIT_NAME}
                                    title={CL_EDIT_NAME}
                                    onClick={() => { setEditError(null); setEditing(true); }}
                                    className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                                >
                                    <Pencil size={18} />
                                </button>
                                <button
                                    type="button"
                                    aria-label={CL_DELETE_STUDENT}
                                    title={signed.signed_tests_count > 0 ? CL_DELETE_BLOCKED : CL_DELETE_STUDENT}
                                    data-blocked={signed.signed_tests_count > 0 ? 'true' : undefined}
                                    aria-describedby={deleteBlocked ? 'delete-blocked' : undefined}
                                    data-delete-student
                                    onClick={onDeleteClick}
                                    className={[
                                        'p-2 rounded-lg transition-colors',
                                        signed.signed_tests_count > 0
                                            ? 'text-gray-300 hover:text-gray-400 cursor-not-allowed'
                                            : 'text-gray-400 hover:text-red-600 hover:bg-red-50',
                                    ].join(' ')}
                                >
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        </header>

                        {deleteBlocked ? (
                            <p
                                id="delete-blocked"
                                role="status"
                                data-delete-blocked
                                className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800"
                            >
                                {CL_DELETE_BLOCKED}
                            </p>
                        ) : null}

                        {/* Rows */}
                        <section aria-label={CL_SIGNED_SECTION} className="mt-8">
                            {signed.signed_tests.length === 0 ? (
                                <div
                                    data-profile-empty
                                    className="flex flex-col items-center gap-2 rounded-xl border border-dashed
                                        border-surface-300 bg-white px-6 py-14 text-center"
                                >
                                    <EmptyPaperGlyph />
                                    <p className="text-lg font-semibold text-gray-900">
                                        {CL_EMPTY_TITLE(student.full_name)}
                                    </p>
                                    <p className="text-sm text-gray-500">{CL_EMPTY_BODY}</p>
                                </div>
                            ) : (
                                <ul className="flex flex-col gap-3">
                                    {signed.signed_tests.map((t) => (
                                        <SignedTestRow
                                            key={t.graded_test_id}
                                            test={t}
                                            studentId={student.id}
                                            register={register}
                                            imageUrl={urlFor(t.thumbnail.page1_image_url)}
                                        />
                                    ))}
                                </ul>
                            )}
                            {signed.truncated ? (
                                <p className="mt-3 text-center text-sm text-gray-500" data-truncated>
                                    {CL_TRUNCATED(signed.signed_tests.length, signed.signed_tests_count)}
                                </p>
                            ) : null}
                        </section>
                    </>
                )}

                {editing && student ? (
                    <StudentNameDialog
                        title="עריכת תלמיד/ה"
                        submitLabel="שמירה"
                        initialName={student.full_name}
                        loading={editLoading}
                        error={editError}
                        onSubmit={onRename}
                        onClose={() => setEditing(false)}
                        onClearError={() => setEditError(null)}
                    />
                ) : null}

                {confirmDelete && student ? (
                    <ConfirmDialog
                        title="מחיקת תלמיד/ה"
                        body={`למחוק את "${student.full_name}"? הפעולה אינה הפיכה.`}
                        confirmLabel="מחיקה"
                        onConfirm={onDelete}
                        onCancel={() => setConfirmDelete(false)}
                        loading={deleteLoading}
                        error={deleteError}
                    />
                ) : null}
            </div>
        </SidebarLayout>
    );
}

function SignedTestRow({
    test, studentId, register, imageUrl,
}: {
    test: SignedTestItem;
    studentId: string;
    register: (element: Element | null, path: string | null) => void;
    imageUrl: string | null;
}) {
    const title = examEventTitle({
        batch_id: test.exam.batch_id, name: test.exam.name, rubric_name: test.exam.rubric_name,
    });
    const score = decimalText(test.total_score);
    const approvedAt = formatSignedAt(test.approved_at);
    return (
        <li>
            <Link
                href={returnedExamHref(test.graded_test_id, studentId, test.exam.batch_id)}
                data-signed-test={test.graded_test_id}
                className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-xl border border-surface-200
                    bg-white px-5 py-4 transition-colors hover:border-primary-300
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
            >
                {/* OD-8 / UI-2: the SAME component the returned page draws page 1
                    with, read-only, at ~100 px. The stamp lands on the same spot
                    of the page because its position is normalized (FA-3). */}
                <div
                    ref={(el) => register(el, test.thumbnail.page1_image_url ?? null)}
                    className="w-24 shrink-0"
                    data-thumb
                >
                    <StampedPage
                        imageUrl={imageUrl}
                        score={score}
                        stampPosition={test.thumbnail.stamp_position ?? null}
                        alt={CL_THUMB_ALT(title)}
                    />
                </div>
                <div className="min-w-0 flex-1 basis-40">
                    <p className="truncate text-lg font-semibold text-gray-900" data-exam-title>{title}</p>
                    {approvedAt ? (
                        <p className="mt-1 text-sm text-gray-500" data-approved-at>
                            {CL_APPROVED_AT(approvedAt)}
                        </p>
                    ) : null}
                </div>
                {/* OD-7: the row's own two numbers. Below ~640px the grade wraps
                    under the text (basis-full); the chevron then steps aside. */}
                <div className="flex basis-full items-baseline gap-2 sm:basis-auto" data-signed-grade>
                    <span
                        dir="ltr"
                        className="text-3xl font-light leading-none text-gray-900
                            [font-variant-numeric:tabular-nums] [unicode-bidi:isolate]"
                    >
                        {score}
                    </span>
                    <span className="text-sm text-gray-500">
                        {CL_GRADE_OF(decimalText(test.total_possible))}
                    </span>
                </div>
                <ChevronLeft size={20} aria-hidden="true" className="hidden shrink-0 text-gray-400 sm:block" />
            </Link>
        </li>
    );
}

/** Loading: skeleton rows — never a blank page (§6.2). */
function ProfileSkeleton() {
    return (
        <div data-profile-skeleton className="animate-pulse" aria-busy="true">
            <div className="flex items-center gap-5">
                <div className="h-16 w-16 rounded-full bg-surface-200" />
                <div className="flex-1">
                    <div className="h-7 w-48 rounded bg-surface-200" />
                    <div className="mt-3 h-4 w-32 rounded bg-surface-100" />
                </div>
            </div>
            <div className="mt-8 flex flex-col gap-3">
                {[0, 1, 2].map((i) => (
                    <div key={i} className="flex items-center gap-5 rounded-xl border border-surface-200 bg-white px-5 py-4">
                        <div className="aspect-[1/1.41] w-24 rounded bg-surface-100" />
                        <div className="flex-1">
                            <div className="h-5 w-56 rounded bg-surface-200" />
                            <div className="mt-2 h-4 w-40 rounded bg-surface-100" />
                        </div>
                        <div className="h-8 w-16 rounded bg-surface-100" />
                    </div>
                ))}
            </div>
        </div>
    );
}

function EmptyPaperGlyph() {
    return (
        <svg width="64" height="84" viewBox="0 0 64 84" aria-hidden="true" className="mb-2">
            <rect x="4" y="4" width="56" height="76" rx="6" className="fill-white stroke-surface-300" strokeWidth="1.6" />
            <path d="M16 26h32M16 38h32M16 50h20" className="stroke-surface-200" strokeWidth="2" strokeLinecap="round" />
            <circle cx="20" cy="18" r="8" fill="none" className="stroke-red-200" strokeWidth="1.6" strokeDasharray="2 2" />
        </svg>
    );
}
