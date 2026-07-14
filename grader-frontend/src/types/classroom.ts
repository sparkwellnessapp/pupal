// TypeScript mirrors of backend app/schemas/classroom.py response schemas.
// user_id is never present — ownership is implicit.

export interface StudentResponse {
  id: string;
  full_name: string;
  notes: string | null;
  created_at: string;
}

export interface StudentDetailResponse extends StudentResponse {
  classes: { id: string; name: string }[];
}

export interface ClassResponse {
  id: string;
  name: string;
  subject_matter_id: number | null;
  subject_matter_name: string | null;
  school_year: string | null;
  student_count: number;
  created_at: string;
}

export interface ClassDetailResponse extends ClassResponse {
  students: { id: string; full_name: string }[];
}

export interface SubjectMatterOption {
  id: number;
  code: string;
  name_he: string;
  name_en: string;
}

// Request bodies

export interface CreateStudentBody {
  full_name: string;
  notes?: string;
}

export interface UpdateStudentBody {
  full_name?: string;
  notes?: string;
}

export interface CreateClassBody {
  name: string;
  subject_matter_id?: number | null;
  school_year?: string;
}

export interface UpdateClassBody {
  name?: string;
  subject_matter_id?: number | null;
  school_year?: string;
}

// Error thrown when the backend returns 409 Conflict
export class ClassroomConflictError extends Error {
  constructor(public readonly detail: string) {
    super(detail);
    this.name = 'ClassroomConflictError';
  }
}
