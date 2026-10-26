import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowRight, Download } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { BatchStatusBadge, FindingStatusBadge, RowStatusBadge, SeverityBadge } from '@/components/domain'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Alert, EmptyState, ErrorState, LoadingBlock } from '@/components/ui/Feedback'
import { PageHeader, Pagination, SegmentedTabs } from '@/components/ui/Layout'
import { StatTile } from '@/components/ui/Stat'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { useToast } from '@/components/ui/Toast'
import { api, downloadFile } from '@/lib/api'
import { formatDateTime, formatNumber } from '@/lib/format'
import type { FindingSummaryItem, Page, UploadBatch, UploadRow } from '@/types/api'

type RowFilter = 'all' | 'rejected' | 'created' | 'updated' | 'unchanged'
const PAGE_SIZE = 25

export function UploadDetailPage() {
  const { id = '' } = useParams()
  const toast = useToast()
  const [filter, setFilter] = useState<RowFilter>('all')
  const [page, setPage] = useState(1)

  const batch = useQuery({ queryKey: ['upload', id], queryFn: () => api.get<UploadBatch>(`/uploads/${id}`) })
  const rows = useQuery({
    queryKey: ['upload-rows', id, filter, page],
    queryFn: () =>
      api.get<Page<UploadRow>>(`/uploads/${id}/rows`, {
        status: filter === 'all' ? undefined : filter,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })
  const findings = useQuery({
    queryKey: ['findings', 'batch', id],
    queryFn: () =>
      api.get<Page<FindingSummaryItem>>('/findings', { batch_id: id, status: 'all', page_size: 50 }),
  })

  if (batch.isPending) return <LoadingBlock />
  if (batch.isError) return <ErrorState error={batch.error} onRetry={() => batch.refetch()} />
  const b = batch.data
  const accepted = b.created_rows + b.updated_rows + b.unchanged_rows

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/uploads', label: 'Uploads' }}
        title={b.original_filename}
        meta={
          <>
            <BatchStatusBadge status={b.status} />
            <span className="text-[13px] text-ink-3">
              {b.institution.code} · uploaded {formatDateTime(b.created_at)} by {b.uploaded_by?.full_name ?? '—'}
              {b.processing_ms !== null && ` · processed in ${formatNumber(b.processing_ms)} ms`}
            </span>
          </>
        }
        actions={
          (b.rejected_rows > 0 || b.file_errors.length > 0) && (
            <Button
              variant="secondary"
              icon={<Download className="size-4" aria-hidden />}
              onClick={() => downloadFile(`/uploads/${id}/errors.csv`).catch((e) => toast.error(e.message))}
            >
              Download error report
            </Button>
          )
        }
      />

      {b.file_errors.map((e) => (
        <Alert key={e.code} tone="danger" title="The file was rejected">
          {e.message} <span className="font-mono text-xs opacity-75">({e.code})</span>
        </Alert>
      ))}
      {b.warnings.map((w) => (
        <Alert key={w.code} tone={w.code === 'REPEAT_UPLOAD' ? 'info' : 'warning'}>
          {w.message}
          {w.code === 'REPEAT_UPLOAD' && b.repeat_of_batch_id && (
            <>
              {' '}
              <Link to={`/uploads/${b.repeat_of_batch_id}`} className="font-medium underline">
                View earlier upload
              </Link>
            </>
          )}
        </Alert>
      ))}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatTile label="Rows processed" value={formatNumber(b.total_rows)} detail={`${b.skipped_blank_rows} blank rows skipped`} />
        <StatTile label="Accepted" value={formatNumber(accepted)} detail={`${b.created_rows} new · ${b.updated_rows} updated · ${b.unchanged_rows} unchanged`} />
        <StatTile label="Rejected" value={formatNumber(b.rejected_rows)} detail="Not saved — fix and re-upload" tone={b.rejected_rows ? 'attention' : 'default'} />
        <StatTile label="New findings" value={formatNumber(b.findings_opened)} detail="Raised for human review" />
        <StatTile
          label="Acceptance rate"
          value={b.total_rows ? `${Math.round((accepted / b.total_rows) * 100)}%` : '—'}
          detail="Accepted rows / rows processed"
        />
      </div>

      {(findings.data?.items.length ?? 0) > 0 && (
        <Card>
          <CardHeader
            title="Findings raised by this upload"
            description="Rules ran on the saved records after the upload. Each finding explains its evidence."
          />
          <ul className="divide-y divide-line">
            {findings.data!.items.map((f) => (
              <li key={f.id}>
                <Link to={`/exceptions/${f.id}`} className="flex flex-wrap items-center gap-3 px-5 py-3 hover:bg-slate-50">
                  <SeverityBadge value={f.severity} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-ink">{f.title}</p>
                    <p className="truncate text-xs text-ink-3">{f.reason}</p>
                  </div>
                  <FindingStatusBadge status={f.status} />
                  <ArrowRight className="size-4 text-ink-3" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {b.total_rows > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
            <h2 className="text-[15px] font-semibold">Row results</h2>
            <SegmentedTabs<RowFilter>
              label="Filter rows"
              value={filter}
              onChange={(v) => {
                setFilter(v)
                setPage(1)
              }}
              items={[
                { value: 'all', label: 'All', count: b.total_rows },
                { value: 'rejected', label: 'Rejected', count: b.rejected_rows },
                { value: 'created', label: 'Created', count: b.created_rows },
                { value: 'updated', label: 'Updated', count: b.updated_rows },
                { value: 'unchanged', label: 'Unchanged', count: b.unchanged_rows },
              ]}
            />
          </div>
          {rows.isPending ? (
            <LoadingBlock />
          ) : rows.isError ? (
            <ErrorState error={rows.error} onRetry={() => rows.refetch()} />
          ) : rows.data.items.length === 0 ? (
            <EmptyState title="No rows in this category" />
          ) : (
            <div className={rows.isFetching ? 'opacity-70' : undefined}>
              <TableWrap>
                <Table>
                  <THead>
                    <tr>
                      <TH className="w-20">Line</TH>
                      <TH>Student ID</TH>
                      <TH>Result</TH>
                      <TH>Reason</TH>
                    </tr>
                  </THead>
                  <tbody>
                    {rows.data.items.map((r) => (
                      <TR key={r.row_number}>
                        <TD className="font-mono text-xs text-ink-2">{r.row_number}</TD>
                        <TD className="font-mono text-xs">
                          {r.student_id ? (
                            <Link to={`/students/${r.student_id}`} className="text-brand-600 hover:underline">
                              {r.row_label}
                            </Link>
                          ) : (
                            (r.row_label ?? '—')
                          )}
                        </TD>
                        <TD>
                          <RowStatusBadge status={r.status} />
                        </TD>
                        <TD>
                          {r.errors.length === 0 ? (
                            <span className="text-ink-3">—</span>
                          ) : (
                            <ul className="space-y-1">
                              {r.errors.map((e, i) => (
                                <li key={i} className="text-[13px]">
                                  {e.field && <span className="font-mono text-xs text-ink-2">{e.field}: </span>}
                                  {e.message}{' '}
                                  <span className="font-mono text-[11px] text-ink-3">{e.code}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
              <Pagination page={page} pageSize={PAGE_SIZE} total={rows.data.total} onPage={setPage} />
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
