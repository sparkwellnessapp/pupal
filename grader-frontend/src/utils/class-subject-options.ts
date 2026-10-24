import { SUBJECT_KEYS } from '@/lib/subjects';
import type { SubjectMatterOption } from '@/types/classroom';

/**
 * The subjects a class may be assigned — HER subjects, the ones on her
 * profile (onboarding's subject step). A teacher with none yet gets the
 * registry's launch set (`SUBJECT_KEYS`: מדעי המחשב, אנגלית, מתמטיקה), never
 * the whole seeded table.
 *
 * One exception, so an edit never silently clears what is stored: when the
 * class ALREADY carries a subject outside that list (she dropped it from her
 * profile later), it stays offered. Hiding it would render the select as
 * «ללא מקצוע» and the next Save would write that.
 *
 * Pure; the order is her profile's (or the server's list order for the
 * fallback), with the kept-current subject last.
 */
export function classSubjectOptions(
    all: readonly SubjectMatterOption[],
    mine: readonly SubjectMatterOption[],
    currentId: number | null = null,
): SubjectMatterOption[] {
    const base = mine.length > 0
        ? [...mine]
        : all.filter(sm => (SUBJECT_KEYS as readonly string[]).includes(sm.code));
    if (currentId !== null && !base.some(sm => sm.id === currentId)) {
        const current = all.find(sm => sm.id === currentId);
        if (current) base.push(current);
    }
    return base;
}
