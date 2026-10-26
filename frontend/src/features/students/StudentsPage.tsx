import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { Fingerprint, Plus, Search, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { ConsentBadge, EnrolmentBadge, MaskedId } from '@/components/domain'
import { Badge } from '@/components/ui/Badge'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Alert, EmptyState, ErrorState, LoadingBlock, errorMessage } from '@/components/ui/Feedback'
import { Field, Input, Select } from '@/components/ui/Form'
import { PageHeader, Pagination } from '@/components/ui/Layout'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { api } from '@/lib/api'
import { PERMISSIONS, useAuth } from '@/lib/auth'
import { formatRelative, humanize } from '@/lib/format'
import { useAppConfig, useProgrammes } from '@/lib/queries'
import type { Page, StudentListItem } from '@/types/api'

const PAGE_SIZE = 20

function FindByIdentifier() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  const lookup = useMutation({
    mutationFn: (apaar_id: string) =>
      api.post<{ id: string; institution: { code: string }; full_name: string }[]>('/students/lookup', {
        apaar_id,
      }),
    onSuccess: (matches) => {
      if (matches.length === 1) {
        setOpen(false)
        navigate(`/students/${matches[0].id}`)
      }
    },
  })
  const matches = lookup.data ?? []

  return (
    <>
      <Button variant="secondary" icon={<Fingerprint className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Find by APAAR ID
      </Button>
      <Dialog
        open={open}
        onClose={() => {
          setOpen(false)
          lookup.reset()
          setValue('')
        }}
        title="Find a record by APAAR ID"
        description="The full identifier is sent in the request body, never in the page address, and the lookup is audited."
        footer={
          <Button
            onClick={() => lookup.mutate(value)}
            loading={lookup.isPending}
            disabled={!value.trim()}
            form="lookup-form"
            type="submit"
          >
            Search
          </Button>
        }
      >
        <form
          id="lookup-form"
          onSubmit={(event) => {
            event.preventDefault()
            if (value.trim()) lookup.mutate(value)
          }}
          className="space-y-3"
        >
          <Field label="APAAR ID" htmlFor="apaar-lookup">
            <Input
              id="apaar-lookup"
              autoComplete="off"
              spellCheck={false}
              placeholder="DEMO-APAAR-000000"
              className="font-mono"
              value={value}
              onChange={(event) => setValue(event.target.value)}
            />
          </Field>
          {lookup.isError && <Alert tone="danger">{errorMessage(lookup.error)}</Alert>}
          {lookup.isSuccess && matches.length === 0 && (
            <Alert tone="info">No record with this APAAR ID is visible to you.</Alert>
          )}
          {matches.length > 1 && (
            <ul className="divide-y divide-line rounded-lg border border-line">
              {matches.map((m) => (
                <li key={m.id}>
                  <Link to={`/students/${m.id}`} className="block px-3 py-2 text-sm hover:bg-slate-50">
                    {m.full_name} <span className="text-ink-3">· {m.institution.code}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </form>
      </Dialog>
    </>
  )
}

export function StudentsPage() {
  const { can, user } = useAuth()
  const config = useAppConfig()
  const programmes = useProgrammes()
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get('q') ?? '')
  const page = Number(params.get('page') ?? '1')
  const filters = {
    q: params.get('q') ?? '',
    programme_id: params.get('programme_id') ?? '',
    academic_year: params.get('academic_year') ?? '',
    enrolment_status: params.get('enrolment_status') ?? '',
    has_open_findings: params.get('has_open_findings') ?? '',
  }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (search !== filters.q) update({ q: search })
    }, 350)
    return () => window.clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in changes)) next.delete('page')
    setParams(next, { replace: true })
  }

  const query = useQuery({
    queryKey: ['students', filters, page],
    queryFn: () => api.get<Page<StudentListItem>>('/students', { ...filters, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })

  const central = !user?.institution
  return (
    <div>
      <PageHeader
        title="Students"
        description="Student records and admissions. APAAR IDs are masked in all lists."
        actions={
          <>
            <FindByIdentifier />
            {can(PERMISSIONS.studentsWrite) && (
              <ButtonLink to="/students/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                Add record
              </ButtonLink>
            )}
          </>
        }
      />

      <Card>
        <div className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3">
          <div className="relative min-w-60 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
            <Input
              aria-label="Search by name or student ID"
              placeholder="Search by name or institution student ID"
              className="pl-9"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Select
            aria-label="Programme"
            className="w-56"
            value={filters.programme_id}
            onChange={(event) => update({ programme_id: event.target.value })}
          >
            <option value="">All programmes</option>
            {(programmes.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {central ? `${p.institution.code} · ` : ''}
                {p.code}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Academic year"
            className="w-32"
            value={filters.academic_year}
            onChange={(event) => update({ academic_year: event.target.value })}
          >
            <option value="">All years</option>
            {(config.data?.academic_years ?? []).map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Enrolment status"
            className="w-36"
            value={filters.enrolment_status}
            onChange={(event) => update({ enrolment_status: event.target.value })}
          >
            <option value="">Any status</option>
            {(config.data?.enrolment_statuses ?? []).map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Findings"
            className="w-44"
            value={filters.has_open_findings}
            onChange={(event) => update({ has_open_findings: event.target.value })}
          >
            <option value="">All records</option>
            <option value="true">With open findings</option>
            <option value="false">Without open findings</option>
          </Select>
        </div>

        {query.isPending ? (
          <LoadingBlock />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState
            icon={<Users className="size-5" aria-hidden />}
            title="No students match these filters"
            description="Try clearing filters, or upload records to get started."
          />
        ) : (
          <div className={query.isFetching ? 'opacity-70' : undefined}>
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <TH>Student</TH>
                    <TH>APAAR ID</TH>
                    {central && <TH>Institution</TH>}
                    <TH>Latest admission</TH>
                    <TH>Status</TH>
                    <TH>Consent</TH>
                    <TH className="text-right">Open findings</TH>
                    <TH>Updated</TH>
                  </tr>
                </THead>
                <tbody>
                  {query.data.items.map((s) => (
                    <TR key={s.id}>
                      <TD>
                        <Link to={`/students/${s.id}`} className="font-medium text-brand-600 hover:underline">
                          {s.full_name}
                        </Link>
                        <p className="font-mono text-xs text-ink-3">{s.institution_student_id}</p>
                      </TD>
                      <TD>
                        <MaskedId value={s.apaar_masked} />
                      </TD>
                      {central && <TD className="font-mono text-xs">{s.institution.code}</TD>}
                      <TD>
                        {s.latest_admission ? (
                          <>
                            <p>{s.latest_admission.programme_code}</p>
                            <p className="text-xs text-ink-3">
                              {s.latest_admission.academic_year} · {humanize(s.latest_admission.seat_type)}
                            </p>
                          </>
                        ) : (
                          '—'
                        )}
                      </TD>
                      <TD>{s.latest_admission && <EnrolmentBadge status={s.latest_admission.enrolment_status} />}</TD>
                      <TD>
                        <ConsentBadge status={s.consent_status} />
                      </TD>
                      <TD className="text-right">
                        {s.open_findings ? <Badge tone="warning">{s.open_findings}</Badge> : <span className="text-ink-3">0</span>}
                      </TD>
                      <TD className="whitespace-nowrap text-ink-2">{formatRelative(s.updated_at)}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={query.data.total}
              onPage={(p) => update({ page: String(p) })}
            />
          </div>
        )}
      </Card>
    </div>
  )
}
