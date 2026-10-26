/** Response shapes of the FastAPI backend (/api/v1). Keep in sync with docs/api-contract.md. */

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface InstitutionRef {
  id: string
  code: string
  name: string
}

export interface ProgrammeRef {
  id: string
  code: string
  name: string
}

export interface CurrentUser {
  id: string
  email: string
  full_name: string
  role: string
  institution: InstitutionRef | null
  permissions: string[]
}

export interface SessionInfo {
  user: CurrentUser
  csrf_token: string
}

export interface PublicMeta {
  app_name: string
  problem_statement: string
  demo_mode: boolean
  demo_accounts: { email: string; role: string; institution: string | null; description: string }[]
  demo_password: string | null
}

export interface ColumnSpec {
  name: string
  required: boolean
  description: string
  example: string
}

export interface AppConfig {
  identifier_format: { label: string; example: string }
  columns: ColumnSpec[]
  seat_types: string[]
  enrolment_statuses: string[]
  genders: string[]
  counted_statuses: string[]
  academic_years: string[]
  verification_provider: { name: string; simulated: boolean }
  demo_mode: boolean
  upload_limits: { max_bytes: number; max_rows: number }
  finding_categories: Record<string, string>
}

export interface RuleInfo {
  code: string
  category: string
  category_label: string
  severity: string
  title: string
  checks: string
  rationale: string
  recommended_action: string
  assumption: string | null
  central_resolution: boolean
  enabled: boolean
}

export interface Fact {
  label: string
  value: string | number
}

export interface FindingSummaryItem {
  id: string
  rule_code: string
  category: string
  category_label: string
  severity: 'high' | 'medium' | 'low'
  status: FindingStatus
  title: string
  reason: string
  institution: InstitutionRef
  student: { id: string; institution_student_id: string; full_name: string } | null
  programme: ProgrammeRef | null
  academic_year: string | null
  created_at: string
  updated_at: string
}

export type FindingStatus = 'open' | 'in_review' | 'escalated' | 'resolved' | 'dismissed'

export interface FindingDetail extends FindingSummaryItem {
  evidence: Fact[]
  restricted_evidence: Fact[] | null
  restricted_evidence_hidden: boolean
  recommended_action: string
  rule: { checks: string; rationale: string; assumption: string | null; central_resolution: boolean } | null
  history: {
    action: string
    from_status: string | null
    to_status: string | null
    comment: string | null
    actor_name: string
    created_at: string
  }[]
  allowed_actions: string[]
  source_batch_id: string | null
  resolved_at: string | null
}

export interface FindingsSummary {
  by_status: Record<FindingStatus, number>
  active_by_category: { category: string; label: string; count: number }[]
  active_by_severity: Record<'high' | 'medium' | 'low', number>
  active_total: number
}

export interface UploadBatch {
  id: string
  institution: InstitutionRef
  original_filename: string
  status: 'completed' | 'partial' | 'rejected' | 'failed' | 'processing'
  total_rows: number
  created_rows: number
  updated_rows: number
  unchanged_rows: number
  rejected_rows: number
  skipped_blank_rows: number
  findings_opened: number
  file_errors: { code: string; message: string }[]
  warnings: { code: string; message: string }[]
  repeat_of_batch_id: string | null
  processing_ms: number | null
  uploaded_by: { full_name: string; email: string } | null
  created_at: string
  completed_at: string | null
}

export interface UploadRow {
  row_number: number
  status: 'created' | 'updated' | 'unchanged' | 'rejected'
  row_label: string | null
  errors: { field: string | null; code: string; message: string }[]
  student_id: string | null
}

export interface StudentListItem {
  id: string
  institution_student_id: string
  full_name: string
  apaar_masked: string
  institution: InstitutionRef
  latest_admission: {
    programme_code: string
    programme_name: string
    academic_year: string
    enrolment_status: string
    seat_type: string
  } | null
  open_findings: number
  consent_status: string | null
  updated_at: string
}

export interface Admission {
  id: string
  programme: ProgrammeRef
  academic_year: string
  admission_date: string
  seat_type: string
  nri_category: boolean
  oci_status: boolean
  foreign_national_status: boolean
  enrolment_status: string
  created_at: string
  updated_at: string
  issued_record: { reference_code: string; issued_at: string } | null
}

export interface Consent {
  status: string
  purpose: string
  method: string
  note: string | null
  created_at: string
}

export interface VerificationResult {
  id: string
  kind: string
  provider: string
  simulated: boolean
  outcome: string
  message: string | null
  created_at: string
}

export interface StudentDetail {
  id: string
  institution_student_id: string
  full_name: string
  date_of_birth: string
  gender: string | null
  nationality: string
  apaar_masked: string
  institution: InstitutionRef
  admissions: Admission[]
  consent: Consent | null
  consent_history: Consent[]
  verifications: VerificationResult[]
  findings: {
    id: string
    rule_code: string
    title: string
    severity: string
    status: string
    academic_year: string | null
    created_at: string
  }[]
  created_at: string
  updated_at: string
}

export interface IntakeConfig {
  id: string
  academic_year: string
  approved_intake: number
  supernumerary_seats: number
  source: string
  notes: string | null
  updated_at: string
}

export interface Programme {
  id: string
  code: string
  name: string
  level: string
  duration_years: number
  status: string
  institution: InstitutionRef
  intake_configurations: IntakeConfig[]
}

export interface InstitutionRow {
  id: string
  code: string
  name: string
  state: string
  institution_type: string
  status: string
  programme_count: number
  student_admissions: number
  last_upload_at: string | null
}

export interface ProgrammeStat {
  programme_id: string
  code: string
  name: string
  level: string
  approved_intake: number | null
  supernumerary_seats: number | null
  regular_enrolled: number
  supernumerary_enrolled: number
  total_enrolled: number
  utilisation_pct: number | null
  nri: number
  oci: number
  foreign_national: number
  status: 'within' | 'exceeded' | 'not_configured' | 'no_intake'
}

export interface CategoryCount {
  category: string
  label: string
  count: number
}

interface BaseKpis {
  active_enrolments: number
  distinct_students: number
  regular_enrolled: number
  supernumerary_enrolled: number
  approved_intake: number
  supernumerary_seats: number
  utilisation_pct: number | null
  programmes_over_intake: number
  programmes_not_configured: number
  nri: number
  oci: number
  foreign_national: number
  open_findings: number
  high_severity_open: number
  escalated: number
  acceptance_rate_pct: number | null
}

export interface InstitutionDashboard {
  academic_year: string
  institution: InstitutionRef
  kpis: BaseKpis & {
    rows_accepted: number
    rows_rejected: number
    consent_granted: number
    consent_coverage_pct: number | null
  }
  programmes: ProgrammeStat[]
  findings_by_category: CategoryCount[]
  findings_by_severity: Record<string, number>
  recent_uploads: {
    id: string
    filename: string
    status: string
    total_rows: number
    rejected_rows: number
    findings_opened: number
    created_at: string
  }[]
  counted_statuses: string[]
  definitions: Record<string, string>
  generated_at: string
}

export interface CentralDashboard {
  academic_year: string
  kpis: BaseKpis & {
    institutions_total: number
    institutions_reporting: number
    cross_institution_flags: number
  }
  institutions: {
    id: string
    code: string
    name: string
    state: string
    institution_type: string
    active_enrolments: number
    approved_intake: number
    regular_enrolled: number
    utilisation_pct: number | null
    programmes_over_intake: number
    open_findings: number
    high_severity_open: number
    acceptance_rate_pct: number | null
    last_upload_at: string | null
    uploads: number
    reporting: boolean
  }[]
  findings_by_category: CategoryCount[]
  findings_by_severity: Record<string, number>
  upload_quality: { date: string; accepted: number; rejected: number }[]
  counted_statuses: string[]
  definitions: Record<string, string>
  generated_at: string
}

export interface EnrolmentReport {
  report: string
  academic_year: string
  scope: string
  generated_at: string
  counted_statuses: string[]
  rows: (ProgrammeStat & { institution_code: string; institution_name: string; state: string })[]
  totals: {
    approved_intake: number
    regular_enrolled: number
    supernumerary_enrolled: number
    total_enrolled: number
    programmes_over_intake: number
  }
  definitions: Record<string, string>
}

export interface DataQualityReport {
  report: string
  scope: string
  generated_at: string
  findings: ({
    institution_code: string
    institution_name: string
    rule_code: string
    rule_title: string
    severity: string
    total: number
  } & Record<FindingStatus, number>)[]
  uploads: {
    institution_code: string
    institution_name: string
    uploads: number
    rows_processed: number
    rows_rejected: number
    acceptance_rate_pct: number | null
  }[]
  note: string
}

export interface IdentifierLookupResult {
  attempt_id: string
  checked_at: string
  format_check: { passed: boolean; rule: string; note: string }
  repository: {
    status: 'records_disclosed' | 'consent_not_on_record' | 'no_records'
    records: {
      student_name: string
      institution_code: string
      institution_name: string
      programme: string
      academic_year: string
      enrolment_status: string
      admission_date: string
    }[]
    withheld_count: number
    note: string
  }
  identity_provider: {
    provider: string
    simulated: boolean
    label: string
    outcome: string
    message: string
  } | null
}

export interface ReferenceLookupResult {
  attempt_id: string
  checked_at: string
  status: 'valid' | 'changed_since_issue' | 'superseded' | 'not_found'
  message: string
  consent_on_record: boolean
  record: {
    student_name: string
    issued_at: string
    institution_code: string
    institution_name: string
    programme: string
    academic_year: string
    enrolment_status: string
    admission_date: string
  } | null
  note: string
}

export interface VerificationAttempt {
  id: string
  kind: string
  purpose: string
  provider: string
  simulated: boolean
  outcome: string
  details: Record<string, unknown>
  requested_by: string | null
  requester_role: string
  created_at: string
}

export interface AuditEvent {
  id: string
  action: string
  outcome: string
  actor_email: string | null
  actor_role: string | null
  institution_code: string | null
  target_type: string | null
  target_id: string | null
  details: Record<string, unknown>
  ip_address: string | null
  request_id: string | null
  created_at: string
}

export interface PolicySettings {
  identifier_format: { pattern: string; label: string; example: string }
  intake_policy: { count_statuses: string[] }
  consistency: {
    min_age_at_admission: number
    max_age_at_admission: number
    academic_year_start_month: number
  }
  rules_enabled: Record<string, boolean>
}

export interface SettingsView {
  policy: PolicySettings
  identifier_presets: { key: string; pattern: string; label: string; example: string; note: string }[]
  rules: {
    code: string
    title: string
    category: string
    category_label: string
    severity: string
    assumption: string | null
    enabled: boolean
  }[]
}

export interface Certificate {
  reference_code: string
  issued_at: string
  newly_issued: boolean
  digest_short: string
  institution: { code: string; name: string; state: string }
  student: {
    full_name: string
    institution_student_id: string
    date_of_birth: string
    apaar_id: string | null
  }
  programme: { code: string; name: string; level: string }
  academic_year: string
  admission_date: string
  enrolment_status: string
  demo_notice: string
  disclaimer: string
}
