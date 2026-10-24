/**
 * In-house scanning — the wire types (backend/app/schemas/capture.py).
 *
 * Consumed from the GENERATED api-types (PR-4 R-B: new wire types never get a
 * hand-written mirror), re-exported under short names for the capture surfaces.
 */
import type { components } from '@/lib/api-types'

type S = components['schemas']

export type LinkState = S['CaptureLinkResponse']['state']
export type CaptureLink = S['CaptureLinkResponse']
export type CaptureHandoff = S['CaptureHandoffResponse']
export type PageView = S['PageView']
export type PageCreateResponse = S['PageCreateResponse']
export type SubmissionView = S['SubmissionView']
/** The student's own view: no student state, ever (D1). */
export type StudentSubmissionView = S['StudentSubmissionView']
/** What both views share — all CaptureFlow reads. */
export type SubmissionPages = Pick<SubmissionView,
  'submission_id' | 'status' | 'pages' | 'version_no' | 'saved_at' | 'updated_at'>
export type SaveResponse = S['SaveResponse']
export type TeacherCaptureState = S['TeacherCaptureState']
export type RosterStudent = S['RosterStudent']
export type StudentLinkInfo = S['StudentLinkInfo']
export type IdentifyResponse = S['IdentifyResponse']
export type CaptureSubmissionRow = S['CaptureSubmissionRow']
export type CaptureSubmissionsResponse = S['CaptureSubmissionsResponse']
export type NameSuggestResponse = S['NameSuggestResponse']
export type CaptureContentType = S['PageCreateRequest']['content_type']
export type Rotation = 0 | 90 | 180 | 270
/** [[x, y] × 4], normalized 0..1, TL, TR, BR, BL. */
export type Quad = number[][]
