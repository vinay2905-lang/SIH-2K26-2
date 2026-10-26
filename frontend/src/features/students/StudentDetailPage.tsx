import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileBadge, Fingerprint, Pencil, ShieldAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  ConsentBadge,
  EnrolmentBadge,
  FindingStatusBadge,
  MaskedId,
  OutcomeBadge,
  SeverityBadge,
  SimulatedTag,
  YesNo,
} from '@/components/domain'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Alert, EmptyState, ErrorState, LoadingBlock, errorMessage } from '@/components/ui/Feedback'
import { Checkbox, Field, Input, Select, Textarea } from '@/components/ui/Form'
import { DescriptionList, PageHeader } from '@/components/ui/Layout'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { useToast } from '@/components/ui/Toast'
import { ApiError, api } from '@/lib/api'
import { PERMISSIONS, useAuth } from '@/lib/auth'
import { formatDate, formatDateTime, humanize } from '@/lib/format'
import { useAppConfig } from '@/lib/queries'
import type { Admission, StudentDetail, VerificationResult } from '@/types/api'

function useStudent(id: string) {
  return useQuery({ queryKey: ['student', id], queryFn: () => api.get<StudentDetail>(`/students/${id}`) })
}

function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError ? error.fieldErrors : {}
}

function EditIdentityDialog({ student, open, onClose }: { student: StudentDetail; open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({
    full_name: student.full_name,
    institution_student_id: student.institution_student_id,
    date_of_birth: student.date_of_birth,
    gender: student.gender ?? '',
    nationality: student.nationality,
    reason: '',
  })
  const mutation = useMutation({
    mutationFn: () => {
      const changes: Record<string, string> = { reason: form.reason }
      for (const key of ['full_name', 'institution_student_id', 'date_of_birth', 'gender', 'nationality'] as const) {
        const current = key === 'gender' ? (student.gender ?? '') : student[key]
        if (form[key] !== current) changes[key] = form[key]
      }
      return api.patch<StudentDetail>(`/students/${student.id}`, changes)
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['student', student.id], data)
      queryClient.invalidateQueries({ queryKey: ['students'] })
      queryClient.invalidateQueries({ queryKey: ['findings'] })
      toast.success('Details updated and re-validated.')
      onClose()
    },
  })
  const errors = fieldErrors(mutation.error)
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: event.target.value }))

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Edit identity details"
      description="Changes are audited with your reason. The APAAR ID cannot be changed here."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="identity-form" loading={mutation.isPending}>
            Save changes
          </Button>
        </>
      }
    >
      <form
        id="identity-form"
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        {mutation.isError && !Object.keys(errors).length && (
          <Alert tone="danger" className="sm:col-span-2">
            {errorMessage(mutation.error)}
          </Alert>
        )}
        <Field label="Full name" htmlFor="e-name" error={errors.full_name} className="sm:col-span-2">
          <Input id="e-name" value={form.full_name} onChange={set('full_name')} />
        </Field>
        <Field label="Institution student ID" htmlFor="e-sid" error={errors.institution_student_id}>
          <Input id="e-sid" className="font-mono" value={form.institution_student_id} onChange={set('institution_student_id')} />
        </Field>
        <Field label="Date of birth" htmlFor="e-dob" error={errors.date_of_birth}>
          <Input id="e-dob" type="date" value={form.date_of_birth} onChange={set('date_of_birth')} />
        </Field>
        <Field label="Gender" htmlFor="e-gender" error={errors.gender}>
          <Select id="e-gender" value={form.gender} onChange={set('gender')}>
            <option value="">Not stated</option>
            <option value="F">Female</option>
            <option value="M">Male</option>
            <option value="O">Other</option>
          </Select>
        </Field>
        <Field label="Nationality" htmlFor="e-nat" error={errors.nationality}>
          <Input id="e-nat" maxLength={2} className="uppercase" value={form.nationality} onChange={set('nationality')} />
        </Field>
        <Field label="Reason for change" htmlFor="e-reason" required error={errors.reason} className="sm:col-span-2">
          <Textarea
            id="e-reason"
            required
            minLength={3}
            placeholder="e.g. Name corrected as per admission documents"
            value={form.reason}
            onChange={set('reason')}
          />
        </Field>
      </form>
    </Dialog>
  )
}

function EditAdmissionDialog({
  studentId,
  admission,
  onClose,
}: {
  studentId: string
  admission: Admission | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const config = useAppConfig()
  const [form, setForm] = useState(() => ({
    admission_date: admission?.admission_date ?? '',
    seat_type: admission?.seat_type ?? 'REGULAR',
    enrolment_status: admission?.enrolment_status ?? 'ENROLLED',
    nri_category: admission?.nri_category ?? false,
    oci_status: admission?.oci_status ?? false,
    foreign_national_status: admission?.foreign_national_status ?? false,
    reason: '',
  }))
  const mutation = useMutation({
    mutationFn: () => api.patch<StudentDetail>(`/admissions/${admission?.id}`, form),
    onSuccess: (data) => {
      queryClient.setQueryData(['student', studentId], data)
      queryClient.invalidateQueries({ queryKey: ['findings'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      toast.success('Admission updated and re-validated.')
      onClose()
    },
  })
  const errors = fieldErrors(mutation.error)
  if (!admission) return null

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Edit admission · ${admission.programme.code} ${admission.academic_year}`}
      description="Validation re-runs after saving; findings that no longer apply are resolved automatically."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="admission-form" loading={mutation.isPending}>
            Save changes
          </Button>
        </>
      }
    >
      <form
        id="admission-form"
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        {mutation.isError && !Object.keys(errors).length && (
          <Alert tone="danger" className="sm:col-span-2">
            {errorMessage(mutation.error)}
          </Alert>
        )}
        <Field label="Admission date" htmlFor="a-date" error={errors.admission_date}>
          <Input
            id="a-date"
            type="date"
            value={form.admission_date}
            onChange={(e) => setForm((f) => ({ ...f, admission_date: e.target.value }))}
          />
        </Field>
        <Field label="Seat type" htmlFor="a-seat">
          <Select id="a-seat" value={form.seat_type} onChange={(e) => setForm((f) => ({ ...f, seat_type: e.target.value }))}>
            {(config.data?.seat_types ?? []).map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Enrolment status" htmlFor="a-status">
          <Select
            id="a-status"
            value={form.enrolment_status}
            onChange={(e) => setForm((f) => ({ ...f, enrolment_status: e.target.value }))}
          >
            {(config.data?.enrolment_statuses ?? []).map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </Select>
        </Field>
        <div className="space-y-2 sm:col-span-2">
          <Checkbox
            id="a-nri"
            label="NRI category"
            checked={form.nri_category}
            onChange={(e) => setForm((f) => ({ ...f, nri_category: e.target.checked }))}
          />
          <Checkbox
            id="a-oci"
            label="OCI status"
            checked={form.oci_status}
            onChange={(e) => setForm((f) => ({ ...f, oci_status: e.target.checked }))}
          />
          <Checkbox
            id="a-fn"
            label="Foreign National (FN)"
            checked={form.foreign_national_status}
            onChange={(e) => setForm((f) => ({ ...f, foreign_national_status: e.target.checked }))}
          />
        </div>
        <Field label="Reason for change" htmlFor="a-reason" required error={errors.reason} className="sm:col-span-2">
          <Textarea
            id="a-reason"
            required
            minLength={3}
            value={form.reason}
            onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
          />
        </Field>
      </form>
    </Dialog>
  )
}

function ConsentCard({ student }: { student: StudentDetail }) {
  const { can } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const next = student.consent?.status === 'granted' ? 'withdrawn' : 'granted'
  const mutation = useMutation({
    mutationFn: () => api.post<StudentDetail>(`/students/${student.id}/consent`, { status: next }),
    onSuccess: (data) => {
      queryClient.setQueryData(['student', student.id], data)
      toast.success(next === 'granted' ? 'Consent recorded.' : 'Consent withdrawal recorded.')
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <Card>
      <CardHeader
        title="Verification consent"
        description="Third-party verification shares details only while consent is on record."
        actions={
          can(PERMISSIONS.consentManage) && (
            <Button
              size="sm"
              variant={next === 'granted' ? 'subtle' : 'secondary'}
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {next === 'granted' ? 'Record consent' : 'Record withdrawal'}
            </Button>
          )
        }
      />
      <CardBody>
        <ConsentBadge status={student.consent?.status} />
        {student.consent_history.length > 0 ? (
          <ol className="mt-4 space-y-2 border-l border-line pl-4">
            {student.consent_history.map((c, i) => (
              <li key={i} className="text-[13px]">
                <span className="font-medium">{humanize(c.status)}</span>
                <span className="text-ink-3"> · {formatDateTime(c.created_at)}</span>
                {c.note && <p className="text-xs text-ink-3">{c.note}</p>}
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-3 text-[13px] text-ink-3">No consent has been recorded.</p>
        )}
        <p className="mt-4 text-xs text-ink-3">
          Prototype: the institution records consent on the student’s behalf. A production system would capture it
          from the student directly.
        </p>
      </CardBody>
    </Card>
  )
}

function IdentityChecks({ student }: { student: StudentDetail }) {
  const { can } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const mutation = useMutation({
    mutationFn: () => api.post<VerificationResult>(`/students/${student.id}/identity-check`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['student', student.id] }),
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <Card>
      <CardHeader
        title="APAAR identity checks"
        description="Through the verification adapter. No authorised APAAR integration is connected."
        actions={
          can(PERMISSIONS.identityCheck) && (
            <Button
              size="sm"
              variant="secondary"
              icon={<Fingerprint className="size-4" aria-hidden />}
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              Run check
            </Button>
          )
        }
      />
      <CardBody className="space-y-3">
        <SimulatedTag />
        {student.verifications.length === 0 ? (
          <p className="text-[13px] text-ink-3">No checks have been run for this record.</p>
        ) : (
          <ul className="divide-y divide-line">
            {student.verifications.map((v) => (
              <li key={v.id} className="py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <OutcomeBadge outcome={v.outcome} />
                  <span className="text-xs text-ink-3">{formatDateTime(v.created_at)}</span>
                </div>
                {v.message && <p className="mt-1 text-xs text-ink-2">{v.message}</p>}
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}

export function StudentDetailPage() {
  const { id = '' } = useParams()
  const { can } = useAuth()
  const navigate = useNavigate()
  const query = useStudent(id)
  const [editing, setEditing] = useState(false)
  const [editingAdmission, setEditingAdmission] = useState<Admission | null>(null)

  if (query.isPending) return <LoadingBlock />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const s = query.data

  return (
    <div>
      <PageHeader
        back={{ to: '/students', label: 'Students' }}
        title={s.full_name}
        meta={
          <>
            <span className="font-mono text-[13px] text-ink-2">{s.institution_student_id}</span>
            <span className="text-ink-3">·</span>
            <MaskedId value={s.apaar_masked} />
            <span className="text-ink-3">·</span>
            <span className="text-[13px] text-ink-2">{s.institution.name}</span>
          </>
        }
        actions={
          can(PERMISSIONS.studentsWrite) && (
            <Button variant="secondary" icon={<Pencil className="size-4" aria-hidden />} onClick={() => setEditing(true)}>
              Edit details
            </Button>
          )
        }
      />

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader title="Identity" />
            <CardBody>
              <DescriptionList
                items={[
                  { label: 'Full name', value: s.full_name },
                  { label: 'Institution student ID', value: <span className="font-mono">{s.institution_student_id}</span> },
                  { label: 'APAAR ID', value: <MaskedId value={s.apaar_masked} /> },
                  { label: 'Date of birth', value: formatDate(s.date_of_birth) },
                  { label: 'Gender', value: s.gender ? { F: 'Female', M: 'Male', O: 'Other' }[s.gender] : 'Not stated' },
                  { label: 'Nationality', value: s.nationality },
                  { label: 'Record created', value: formatDateTime(s.created_at) },
                  { label: 'Last updated', value: formatDateTime(s.updated_at) },
                ]}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Admissions" description="One row per programme and academic year." />
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <TH>Programme</TH>
                    <TH>Year</TH>
                    <TH>Seat</TH>
                    <TH>NRI</TH>
                    <TH>OCI</TH>
                    <TH>FN</TH>
                    <TH>Status</TH>
                    <TH className="text-right">Actions</TH>
                  </tr>
                </THead>
                <tbody>
                  {s.admissions.map((a) => (
                    <TR key={a.id}>
                      <TD>
                        <p className="font-medium">{a.programme.code}</p>
                        <p className="text-xs text-ink-3">Admitted {formatDate(a.admission_date)}</p>
                      </TD>
                      <TD className="tabular">{a.academic_year}</TD>
                      <TD>{humanize(a.seat_type)}</TD>
                      <TD>
                        <YesNo value={a.nri_category} />
                      </TD>
                      <TD>
                        <YesNo value={a.oci_status} />
                      </TD>
                      <TD>
                        <YesNo value={a.foreign_national_status} />
                      </TD>
                      <TD>
                        <EnrolmentBadge status={a.enrolment_status} />
                      </TD>
                      <TD className="text-right whitespace-nowrap">
                        {can(PERMISSIONS.studentsWrite) && (
                          <Button size="sm" variant="ghost" onClick={() => setEditingAdmission(a)}>
                            Edit
                          </Button>
                        )}
                        {can(PERMISSIONS.recordsIssue) && (
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<FileBadge className="size-4" aria-hidden />}
                            onClick={() => navigate(`/admissions/${a.id}/certificate`)}
                          >
                            Record
                          </Button>
                        )}
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          </Card>

          <Card>
            <CardHeader title="Findings for this student" />
            {s.findings.length === 0 ? (
              <EmptyState
                icon={<ShieldAlert className="size-5" aria-hidden />}
                title="No findings"
                description="No validation rule has flagged this record."
              />
            ) : (
              <ul className="divide-y divide-line">
                {s.findings.map((f) => (
                  <li key={f.id}>
                    <Link
                      to={`/exceptions/${f.id}`}
                      className="flex flex-wrap items-center gap-3 px-5 py-3 hover:bg-slate-50"
                    >
                      <SeverityBadge value={f.severity} />
                      <span className="flex-1 text-sm font-medium text-ink">{f.title}</span>
                      {f.academic_year && <span className="text-xs text-ink-3">{f.academic_year}</span>}
                      <FindingStatusBadge status={f.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <ConsentCard student={s} />
          <IdentityChecks student={s} />
        </div>
      </div>

      {editing && <EditIdentityDialog student={s} open={editing} onClose={() => setEditing(false)} />}
      {editingAdmission && (
        <EditAdmissionDialog studentId={s.id} admission={editingAdmission} onClose={() => setEditingAdmission(null)} />
      )}
    </div>
  )
}
