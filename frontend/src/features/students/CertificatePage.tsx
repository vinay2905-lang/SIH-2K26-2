import { useQuery } from '@tanstack/react-query'
import { GraduationCap, Printer } from 'lucide-react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Alert, ErrorState, LoadingBlock } from '@/components/ui/Feedback'
import { PageHeader } from '@/components/ui/Layout'
import { api } from '@/lib/api'
import { formatDate, formatDateTime, humanize } from '@/lib/format'
import type { Certificate } from '@/types/api'

/**
 * Printable admission record showing the APAAR ID alongside the institution student ID
 * (REQ-10). Generating it is idempotent and audited; the full identifier appears only here.
 */
export function CertificatePage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const query = useQuery({
    queryKey: ['certificate', id],
    queryFn: () => api.post<Certificate>(`/admissions/${id}/certificate`),
    staleTime: Infinity,
    retry: false,
  })

  if (query.isPending) return <LoadingBlock label="Preparing record…" />
  if (query.isError) return <ErrorState error={query.error} />
  const c = query.data

  const rows: [string, ReactNode][] = [
    ['Student name', c.student.full_name],
    ['Institution student ID', <span className="font-mono">{c.student.institution_student_id}</span>],
    [
      'APAAR ID',
      <span className="font-mono font-semibold tracking-wide">{c.student.apaar_id ?? 'Unavailable'}</span>,
    ],
    ['Date of birth', formatDate(c.student.date_of_birth)],
    ['Programme', `${c.programme.name} (${c.programme.code})`],
    ['Level', c.programme.level],
    ['Academic year of admission', c.academic_year],
    ['Admission date', formatDate(c.admission_date)],
    ['Enrolment status', humanize(c.enrolment_status)],
  ]

  return (
    <div>
      <div className="no-print">
        <PageHeader
          title="Student admission record"
          description="Printable record showing the APAAR ID alongside the institution’s student ID."
          actions={
            <>
              <Button variant="secondary" onClick={() => navigate(-1)}>
                Back
              </Button>
              <Button icon={<Printer className="size-4" aria-hidden />} onClick={() => window.print()}>
                Print
              </Button>
            </>
          }
        />
        <Alert tone="warning" className="mb-6" title="Contains the full APAAR ID">
          Viewing this record was written to the audit trail. Share printed copies only with the student or
          authorised parties.
        </Alert>
      </div>

      <article className="print-sheet relative mx-auto max-w-3xl overflow-hidden rounded-xl border border-line bg-white p-10 shadow-sm">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 flex items-center justify-center text-[64px] font-black tracking-widest text-slate-900/[0.04] select-none"
          style={{ transform: 'rotate(-24deg)' }}
        >
          DEMO · SYNTHETIC
        </div>

        <header className="relative flex items-start justify-between gap-6 border-b-2 border-brand-900 pb-5">
          <div className="flex items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-lg bg-brand-900 text-white">
              <GraduationCap className="size-6" aria-hidden />
            </div>
            <div>
              <p className="text-lg font-semibold text-ink">{c.institution.name}</p>
              <p className="text-xs text-ink-3">
                {c.institution.code} · {c.institution.state}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Record reference</p>
            <p className="font-mono text-lg font-semibold tracking-wide text-brand-900">{c.reference_code}</p>
          </div>
        </header>

        <h2 className="relative mt-6 text-center text-xl font-semibold tracking-tight">Student Admission Record</h2>
        <p className="relative mt-1 text-center text-xs font-semibold tracking-widest text-critical-ink uppercase">
          {c.demo_notice}
        </p>

        <dl className="relative mt-6 divide-y divide-line rounded-lg border border-line">
          {rows.map(([label, value]) => (
            <div key={label} className="grid grid-cols-[200px_1fr] gap-4 px-4 py-2.5 text-sm">
              <dt className="text-ink-3">{label}</dt>
              <dd className="text-ink">{value}</dd>
            </div>
          ))}
        </dl>

        <footer className="relative mt-6 grid gap-4 text-xs text-ink-2 sm:grid-cols-2">
          <div>
            <p>
              <span className="font-semibold">Issued:</span> {formatDateTime(c.issued_at)}
            </p>
            <p>
              <span className="font-semibold">Integrity digest:</span>{' '}
              <span className="font-mono">{c.digest_short}</span>
            </p>
          </div>
          <div className="sm:text-right">
            <p>Authorised verifiers can confirm this record with its reference code on the platform.</p>
          </div>
          <p className="border-t border-line pt-3 text-[11px] leading-relaxed text-ink-3 sm:col-span-2">
            {c.disclaimer}
          </p>
        </footer>
      </article>
    </div>
  )
}
