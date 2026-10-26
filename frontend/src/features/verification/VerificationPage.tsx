import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, FileSearch, Fingerprint, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { OutcomeBadge, SIMULATED_LABEL, SimulatedTag } from '@/components/domain'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert, EmptyState, ErrorState, LoadingBlock, errorMessage } from '@/components/ui/Feedback'
import { Field, Input } from '@/components/ui/Form'
import { PageHeader, Pagination, SegmentedTabs } from '@/components/ui/Layout'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { api } from '@/lib/api'
import { formatDate, formatDateTime, humanize, roleLabel } from '@/lib/format'
import type { IdentifierLookupResult, Page, ReferenceLookupResult, VerificationAttempt } from '@/types/api'

type Mode = 'identifier' | 'reference'

function RecordTable({ records }: { records: IdentifierLookupResult['repository']['records'] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full text-left text-[13px]">
        <thead className="bg-slate-50 text-xs text-ink-3">
          <tr>
            <th className="px-3 py-2 font-medium">Student</th>
            <th className="px-3 py-2 font-medium">Institution</th>
            <th className="px-3 py-2 font-medium">Programme</th>
            <th className="px-3 py-2 font-medium">Year</th>
            <th className="px-3 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r, i) => (
            <tr key={i} className="border-t border-line">
              <td className="px-3 py-2 font-medium">{r.student_name}</td>
              <td className="px-3 py-2">{r.institution_name}</td>
              <td className="px-3 py-2">{r.programme}</td>
              <td className="px-3 py-2 tabular">{r.academic_year}</td>
              <td className="px-3 py-2">{humanize(r.enrolment_status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function IdentifierResult({ result }: { result: IdentifierLookupResult }) {
  const repo = result.repository
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-xl border border-line p-4">
        <p className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <Database className="size-4 text-brand-600" aria-hidden /> Platform record check
        </p>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {result.format_check.passed ? (
            <Badge tone="success">Format check passed</Badge>
          ) : (
            <Badge tone="danger">Format check failed</Badge>
          )}
          {repo.status === 'records_disclosed' && <Badge tone="success">Records found · consent on record</Badge>}
          {repo.status === 'consent_not_on_record' && <Badge tone="warning">Record exists · no consent on record</Badge>}
          {repo.status === 'no_records' && <Badge tone="neutral">No records on this platform</Badge>}
        </div>
        {repo.records.length > 0 && <RecordTable records={repo.records} />}
        {repo.status === 'consent_not_on_record' && (
          <p className="text-[13px] text-ink-2">
            Details are withheld because the student’s consent for third-party verification is not on record. Ask
            the student to arrange consent with their institution.
          </p>
        )}
        <p className="mt-3 text-xs text-ink-3">{result.format_check.note}</p>
        <p className="mt-1 text-xs text-ink-3">{repo.note}</p>
      </div>

      <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50/40 p-4">
        <p className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <Fingerprint className="size-4 text-warning-ink" aria-hidden /> APAAR identity provider
        </p>
        <SimulatedTag />
        {result.identity_provider ? (
          <div className="mt-3 space-y-2">
            <OutcomeBadge outcome={result.identity_provider.outcome} />
            <p className="text-[13px] text-ink-2">{result.identity_provider.message}</p>
            <p className="text-xs text-ink-3">Provider: {result.identity_provider.provider}</p>
          </div>
        ) : (
          <p className="mt-3 text-[13px] text-ink-2">Not called: the identifier failed the format check.</p>
        )}
      </div>
      <p className="text-xs text-ink-3 lg:col-span-2">
        Checked {formatDateTime(result.checked_at)} · logged as attempt{' '}
        <span className="font-mono">{result.attempt_id.slice(0, 8)}</span>
      </p>
    </div>
  )
}

function ReferenceResult({ result }: { result: ReferenceLookupResult }) {
  const tone = result.status === 'valid' ? 'success' : result.status === 'not_found' ? 'info' : 'warning'
  return (
    <div className="space-y-4">
      <Alert tone={tone} title={<OutcomeBadge outcome={result.status} />}>
        {result.message}
      </Alert>
      {result.record ? (
        <dl className="grid gap-x-6 gap-y-3 rounded-xl border border-line p-4 sm:grid-cols-2">
          {[
            ['Student', result.record.student_name],
            ['Institution', result.record.institution_name],
            ['Programme', result.record.programme],
            ['Academic year', result.record.academic_year],
            ['Enrolment status', humanize(result.record.enrolment_status)],
            ['Admission date', formatDate(result.record.admission_date)],
            ['Reference issued', formatDateTime(result.record.issued_at)],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-ink-3">{label}</dt>
              <dd className="text-sm font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        result.status !== 'not_found' &&
        !result.consent_on_record && (
          <p className="text-[13px] text-ink-2">
            Record details are withheld because consent for third-party verification is not on record.
          </p>
        )
      )}
      <p className="text-xs text-ink-3">{result.note}</p>
    </div>
  )
}

function History() {
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['verification-attempts', page],
    queryFn: () => api.get<Page<VerificationAttempt>>('/verification/attempts', { page, page_size: 10 }),
    placeholderData: keepPreviousData,
  })
  return (
    <Card>
      <CardHeader title="Verification history" description="Every request is logged with its purpose. Raw identifiers are not stored." />
      {query.isPending ? (
        <LoadingBlock />
      ) : query.isError ? (
        <ErrorState error={query.error} />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="No verification requests yet" />
      ) : (
        <>
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <TH>When</TH>
                  <TH>Type</TH>
                  <TH>Purpose</TH>
                  <TH>Requested by</TH>
                  <TH>Result</TH>
                </tr>
              </THead>
              <tbody>
                {query.data.items.map((a) => (
                  <TR key={a.id}>
                    <TD className="whitespace-nowrap text-ink-2">{formatDateTime(a.created_at)}</TD>
                    <TD>{humanize(a.kind)}</TD>
                    <TD className="max-w-xs truncate">{a.purpose}</TD>
                    <TD className="text-[13px]">
                      {a.requested_by ?? '—'}
                      <p className="text-xs text-ink-3">{roleLabel(a.requester_role)}</p>
                    </TD>
                    <TD>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <OutcomeBadge outcome={a.outcome} />
                        {a.simulated && <SimulatedTag compact />}
                      </div>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          </TableWrap>
          <Pagination page={page} pageSize={10} total={query.data.total} onPage={setPage} />
        </>
      )}
    </Card>
  )
}

export function VerificationPage() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>('identifier')
  const [identifier, setIdentifier] = useState('')
  const [reference, setReference] = useState('')
  const [purpose, setPurpose] = useState('')

  const byIdentifier = useMutation({
    mutationFn: () =>
      api.post<IdentifierLookupResult>('/verification/lookup', { apaar_id: identifier, purpose }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['verification-attempts'] }),
  })
  const byReference = useMutation({
    mutationFn: () =>
      api.post<ReferenceLookupResult>('/verification/reference', { reference_code: reference, purpose }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['verification-attempts'] }),
  })
  const active = mode === 'identifier' ? byIdentifier : byReference

  function submit(event: FormEvent) {
    event.preventDefault()
    active.mutate()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Verify a student record"
        description="For authorised verifiers such as employers and regulators. Only the minimum record details are shared, and only with the student’s consent."
      />
      <Alert tone="warning" title={SIMULATED_LABEL}>
        No authorised APAAR or AICTE integration is connected. Identity-provider results come from a mock
        adapter for demonstration. Platform record checks use this prototype’s synthetic data.
      </Alert>

      <Card>
        <CardHeader
          title="New verification"
          actions={
            <SegmentedTabs<Mode>
              label="Verification method"
              value={mode}
              onChange={(value) => {
                setMode(value)
                byIdentifier.reset()
                byReference.reset()
              }}
              items={[
                { value: 'identifier', label: 'By APAAR ID' },
                { value: 'reference', label: 'By record reference' },
              ]}
            />
          }
        />
        <CardBody className="space-y-5">
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
            {mode === 'identifier' ? (
              <Field label="APAAR ID" htmlFor="v-id" hint="As provided by the student">
                <Input
                  id="v-id"
                  required
                  autoComplete="off"
                  spellCheck={false}
                  className="font-mono"
                  placeholder="DEMO-APAAR-000000"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                />
              </Field>
            ) : (
              <Field label="Record reference" htmlFor="v-ref" hint="Printed on the student’s admission record">
                <Input
                  id="v-ref"
                  required
                  autoComplete="off"
                  className="font-mono uppercase"
                  placeholder="VR-XXXX-XXXX-XXXX"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                />
              </Field>
            )}
            <Field label="Purpose of verification" htmlFor="v-purpose" hint="Recorded with the request">
              <Input
                id="v-purpose"
                required
                minLength={5}
                placeholder="e.g. Pre-employment background check"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
              />
            </Field>
            <Button
              type="submit"
              loading={active.isPending}
              icon={mode === 'identifier' ? <ShieldCheck className="size-4" aria-hidden /> : <FileSearch className="size-4" aria-hidden />}
              disabled={purpose.trim().length < 5}
            >
              Verify
            </Button>
          </form>
          {active.isError && <Alert tone="danger">{errorMessage(active.error)}</Alert>}
          {mode === 'identifier' && byIdentifier.data && <IdentifierResult result={byIdentifier.data} />}
          {mode === 'reference' && byReference.data && <ReferenceResult result={byReference.data} />}
        </CardBody>
      </Card>

      <History />
    </div>
  )
}
