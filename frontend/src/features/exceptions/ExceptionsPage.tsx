import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { FindingStatusBadge, ReviewSignalNote, SeverityBadge } from '@/components/domain'
import { Card } from '@/components/ui/Card'
import { EmptyState, ErrorState, LoadingBlock } from '@/components/ui/Feedback'
import { Select } from '@/components/ui/Form'
import { PageHeader, Pagination, SegmentedTabs } from '@/components/ui/Layout'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { formatRelative } from '@/lib/format'
import { useAppConfig, useRules } from '@/lib/queries'
import type { FindingSummaryItem, FindingsSummary, Page } from '@/types/api'

type StatusTab = 'active' | 'open' | 'in_review' | 'escalated' | 'closed' | 'all'
const PAGE_SIZE = 20

export function ExceptionsPage() {
  const { user } = useAuth()
  const config = useAppConfig()
  const rules = useRules()
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') as StatusTab) ?? 'active'
  const page = Number(params.get('page') ?? '1')
  const filters = {
    status,
    category: params.get('category') ?? '',
    severity: params.get('severity') ?? '',
    rule_code: params.get('rule_code') ?? '',
    institution_id: params.get('institution_id') ?? '',
  }

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in changes)) next.delete('page')
    setParams(next, { replace: true })
  }

  const summary = useQuery({
    queryKey: ['findings', 'summary', filters.institution_id],
    queryFn: () =>
      api.get<FindingsSummary>('/findings/summary', { institution_id: filters.institution_id || undefined }),
  })
  const query = useQuery({
    queryKey: ['findings', 'list', filters, page],
    queryFn: () => api.get<Page<FindingSummaryItem>>('/findings', { ...filters, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })

  const counts = summary.data?.by_status
  const central = !user?.institution

  return (
    <div>
      <PageHeader
        title="Exception queue"
        description="Records and programmes flagged by validation rules, with the evidence behind each flag. Highest severity first."
      />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <SegmentedTabs<StatusTab>
          label="Finding status"
          value={status}
          onChange={(value) => update({ status: value === 'active' ? '' : value })}
          items={[
            { value: 'active', label: 'Needs attention', count: summary.data?.active_total },
            { value: 'open', label: 'Open', count: counts?.open },
            { value: 'in_review', label: 'In review', count: counts?.in_review },
            { value: 'escalated', label: 'Escalated', count: counts?.escalated },
            { value: 'closed', label: 'Closed', count: counts ? counts.resolved + counts.dismissed : undefined },
            { value: 'all', label: 'All' },
          ]}
        />
        <ReviewSignalNote />
      </div>

      <Card>
        <div className="flex flex-wrap gap-3 border-b border-line px-4 py-3">
          <Select
            aria-label="Category"
            className="w-56"
            value={filters.category}
            onChange={(e) => update({ category: e.target.value })}
          >
            <option value="">All categories</option>
            {Object.entries(config.data?.finding_categories ?? {}).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Severity"
            className="w-40"
            value={filters.severity}
            onChange={(e) => update({ severity: e.target.value })}
          >
            <option value="">Any severity</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </Select>
          <Select
            aria-label="Rule"
            className="w-72"
            value={filters.rule_code}
            onChange={(e) => update({ rule_code: e.target.value })}
          >
            <option value="">All rules</option>
            {(rules.data ?? []).map((r) => (
              <option key={r.code} value={r.code}>
                {r.title}
              </option>
            ))}
          </Select>
          {filters.institution_id && (
            <button
              type="button"
              onClick={() => update({ institution_id: '' })}
              className="text-[13px] font-medium text-brand-600 hover:underline"
            >
              Clear institution filter
            </button>
          )}
        </div>

        {query.isPending ? (
          <LoadingBlock />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState
            icon={<ShieldCheck className="size-5" aria-hidden />}
            title="Nothing here"
            description="No findings match these filters."
          />
        ) : (
          <div className={query.isFetching ? 'opacity-70' : undefined}>
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <TH>Severity</TH>
                    <TH>Finding</TH>
                    <TH>Subject</TH>
                    {central && <TH>Institution</TH>}
                    <TH>Year</TH>
                    <TH>Status</TH>
                    <TH>Raised</TH>
                  </tr>
                </THead>
                <tbody>
                  {query.data.items.map((f) => (
                    <TR key={f.id}>
                      <TD>
                        <SeverityBadge value={f.severity} />
                      </TD>
                      <TD className="max-w-xl">
                        <Link to={`/exceptions/${f.id}`} className="font-medium text-brand-600 hover:underline">
                          {f.title}
                        </Link>
                        <p className="mt-0.5 line-clamp-2 text-xs text-ink-3">{f.reason}</p>
                        <p className="mt-1 text-[11px] text-ink-3">{f.category_label}</p>
                      </TD>
                      <TD className="text-[13px]">
                        {f.student ? (
                          <>
                            <p>{f.student.full_name}</p>
                            <p className="font-mono text-xs text-ink-3">{f.student.institution_student_id}</p>
                          </>
                        ) : f.programme ? (
                          <>
                            <p>{f.programme.code}</p>
                            <p className="text-xs text-ink-3">Programme intake</p>
                          </>
                        ) : (
                          '—'
                        )}
                      </TD>
                      {central && <TD className="font-mono text-xs">{f.institution.code}</TD>}
                      <TD className="tabular">{f.academic_year ?? '—'}</TD>
                      <TD>
                        <FindingStatusBadge status={f.status} />
                      </TD>
                      <TD className="whitespace-nowrap text-ink-2">{formatRelative(f.created_at)}</TD>
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
