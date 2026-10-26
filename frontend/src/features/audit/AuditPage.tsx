import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ScrollText } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { EmptyState, ErrorState, LoadingBlock } from '@/components/ui/Feedback'
import { Select } from '@/components/ui/Form'
import { PageHeader, Pagination } from '@/components/ui/Layout'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { api } from '@/lib/api'
import { formatDateTime, roleLabel } from '@/lib/format'
import type { AuditEvent, Page } from '@/types/api'

const PAGE_SIZE = 25

const ACTION_GROUPS = [
  ['', 'All actions'],
  ['auth.', 'Sign-in and sign-out'],
  ['upload.', 'Uploads'],
  ['student.', 'Student records'],
  ['admission.', 'Admissions'],
  ['finding.', 'Finding reviews'],
  ['verification.', 'Verification'],
  ['consent.', 'Consent'],
  ['record.', 'Record certificates'],
  ['report.', 'Report exports'],
  ['intake.', 'Intake changes'],
  ['settings.', 'Settings'],
  ['access.', 'Access denied'],
]

function Details({ details }: { details: Record<string, unknown> }) {
  const entries = Object.entries(details).filter(([, value]) => value !== null && value !== undefined)
  if (!entries.length) return <span className="text-ink-3">—</span>
  return (
    <ul className="space-y-0.5 text-xs">
      {entries.slice(0, 5).map(([key, value]) => (
        <li key={key} className="truncate">
          <span className="text-ink-3">{key.replace(/_/g, ' ')}:</span>{' '}
          <span className="text-ink-2">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
        </li>
      ))}
    </ul>
  )
}

export function AuditPage() {
  const [action, setAction] = useState('')
  const [outcome, setOutcome] = useState('')
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['audit', action, outcome, page],
    queryFn: () => api.get<Page<AuditEvent>>('/audit-events', { action, outcome, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <PageHeader
        title="Audit trail"
        description="Append-only record of sign-ins, data changes, reviews, exports and verification requests. Full identifiers, passwords and tokens are never logged."
      />
      <Card>
        <div className="flex flex-wrap gap-3 border-b border-line px-4 py-3">
          <Select
            aria-label="Action"
            className="w-60"
            value={action}
            onChange={(e) => {
              setAction(e.target.value)
              setPage(1)
            }}
          >
            {ACTION_GROUPS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Outcome"
            className="w-40"
            value={outcome}
            onChange={(e) => {
              setOutcome(e.target.value)
              setPage(1)
            }}
          >
            <option value="">Any outcome</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="denied">Denied</option>
            <option value="blocked">Blocked</option>
          </Select>
        </div>
        {query.isPending ? (
          <LoadingBlock />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState icon={<ScrollText className="size-5" aria-hidden />} title="No events match" />
        ) : (
          <div className={query.isFetching ? 'opacity-70' : undefined}>
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <TH>When</TH>
                    <TH>Action</TH>
                    <TH>Actor</TH>
                    <TH>Institution</TH>
                    <TH>Details</TH>
                    <TH>Outcome</TH>
                  </tr>
                </THead>
                <tbody>
                  {query.data.items.map((e) => (
                    <TR key={e.id}>
                      <TD className="whitespace-nowrap text-xs text-ink-2">{formatDateTime(e.created_at)}</TD>
                      <TD className="font-mono text-xs">{e.action}</TD>
                      <TD className="text-[13px]">
                        <p className="truncate">{e.actor_email ?? 'System'}</p>
                        {e.actor_role && <p className="text-xs text-ink-3">{roleLabel(e.actor_role)}</p>}
                      </TD>
                      <TD className="font-mono text-xs">{e.institution_code ?? '—'}</TD>
                      <TD className="max-w-sm">
                        <Details details={e.details} />
                      </TD>
                      <TD>
                        <Badge tone={e.outcome === 'success' ? 'success' : e.outcome === 'denied' || e.outcome === 'failure' ? 'danger' : 'warning'}>
                          {e.outcome}
                        </Badge>
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} />
          </div>
        )}
      </Card>
    </div>
  )
}
