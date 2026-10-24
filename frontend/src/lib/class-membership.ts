/**
 * Adding several students to a class — ONE implementation, used by the
 * classes tab («הוספת כל התלמידים») and the capture link's new-class step
 * («שיוך כל התלמידים»).
 *
 * The add endpoint is idempotent per student, so a few in flight at once is
 * safe; bounded so a large roster is not 40 simultaneous requests. Never
 * throws: it reports how many adds failed, and the caller says so.
 */
import { addStudentToClass } from './api'

export const ADD_CONCURRENCY = 4

export async function addStudentsToClass(
  classId: string,
  studentIds: readonly string[],
  add: (classId: string, studentId: string) => Promise<void> = addStudentToClass,
): Promise<{ failed: number }> {
  const queue = [...studentIds]
  let failed = 0
  const worker = async () => {
    for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
      try {
        await add(classId, id)
      } catch {
        failed += 1
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(ADD_CONCURRENCY, queue.length) }, worker))
  return { failed }
}
