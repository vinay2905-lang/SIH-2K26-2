import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { EmptyState, ErrorState, LoadingBlock } from '@/components/ui/Feedback'
import { PageHeader } from '@/components/ui/Layout'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { useToast } from '@/components/ui/Toast'
import { api, downloadFile } from '@/lib/api'
import { formatDateTime, formatNumber, formatPercent } from '@/lib/format'
import type { DataQualityReport, EnrolmentReport } from '@/types/api'
import { IntakeStatusBadge, YearSelect } from '../dashboard/shared'

export function ReportsPage() {
  const toast = useToast()
  const [year, setYear] = useState<string>()
  const enrolment = useQuery({
    queryKey: ['report', 'enrolment', year],
    queryFn: () => api.get<EnrolmentReport>('/reports/enrolment', { academic_year: year }),
  })
  const quality = useQuery({
    queryKey: ['report', 'quality'],
    queryFn: () => api.get<DataQualityReport>('/reports/data-quality'),
  })
  const download = (path: string, query?: Record<string, string | undefined>) =>
    downloadFile(path, query).then(
      () => toast.success('Report downloaded. The export was recorded in the audit trail.'),
      (error) => toast.error(error.message),
    )

  const showInstitution = new Set(enrolment.data?.rows.map((r) => r.institution_code)).size > 1

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Exports for monitoring, accreditation and policy work. CSV files include the report period, generation time and metric definitions."
        actions={<YearSelect value={year ?? enrolment.data?.academic_year} onChange={setYear} />}
      />

      <Card>
        <CardHeader
          title="Enrolment versus approved intake"
          description={
            enrolment.data
              ? `${enrolment.data.scope} · ${enrolment.data.academic_year} · generated ${formatDateTime(enrolment.data.generated_at)}`
              : undefined
          }
          actions={
            <Button
              size="sm"
              icon={<Download className="size-4" aria-hidden />}
              onClick={() => download('/reports/enrolment.csv', { academic_year: enrolment.data?.academic_year })}
            >
              Download CSV
            </Button>
          }
        />
        {enrolment.isPending ? (
          <LoadingBlock />
        ) : enrolment.isError ? (
          <ErrorState error={enrolment.error} onRetry={() => enrolment.refetch()} />
        ) : enrolment.data.rows.length === 0 ? (
          <EmptyState title="No programmes in scope" />
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  {showInstitution && <TH>Institution</TH>}
                  <TH>Programme</TH>
                  <TH className="text-right">Approved</TH>
                  <TH className="text-right">Regular</TH>
                  <TH className="text-right">Supernum.</TH>
                  <TH className="text-right">Total</TH>
                  <TH className="text-right">Utilisation</TH>
                  <TH className="text-right">NRI / OCI / FN</TH>
                  <TH>Status</TH>
                </tr>
              </THead>
              <tbody>
                {enrolment.data.rows.map((r) => (
                  <TR key={r.programme_id}>
                    {showInstitution && <TD className="font-mono text-xs">{r.institution_code}</TD>}
                    <TD>
                      <p className="font-medium">{r.code}</p>
                      <p className="text-xs text-ink-3">{r.name}</p>
                    </TD>
                    <TD className="text-right tabular">{formatNumber(r.approved_intake)}</TD>
                    <TD className="text-right tabular">{formatNumber(r.regular_enrolled)}</TD>
                    <TD className="text-right tabular">
                      {formatNumber(r.supernumerary_enrolled)} / {formatNumber(r.supernumerary_seats)}
                    </TD>
                    <TD className="text-right font-medium tabular">{formatNumber(r.total_enrolled)}</TD>
                    <TD className="text-right tabular">{formatPercent(r.utilisation_pct)}</TD>
                    <TD className="text-right text-ink-2 tabular">
                      {r.nri} / {r.oci} / {r.foreign_national}
                    </TD>
                    <TD>
                      <IntakeStatusBadge status={r.status} />
                    </TD>
                  </TR>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-line bg-slate-50/70 text-sm font-semibold">
                <tr>
                  <TD colSpan={showInstitution ? 2 : 1}>Total</TD>
                  <TD className="text-right tabular">{formatNumber(enrolment.data.totals.approved_intake)}</TD>
                  <TD className="text-right tabular">{formatNumber(enrolment.data.totals.regular_enrolled)}</TD>
                  <TD className="text-right tabular">{formatNumber(enrolment.data.totals.supernumerary_enrolled)}</TD>
                  <TD className="text-right tabular">{formatNumber(enrolment.data.totals.total_enrolled)}</TD>
                  <TD colSpan={2} />
                  <TD>{formatNumber(enrolment.data.totals.programmes_over_intake)} over intake</TD>
                </tr>
              </tfoot>
            </Table>
          </TableWrap>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Data quality and findings"
          description={quality.data ? `${quality.data.scope} · ${quality.data.note}` : undefined}
          actions={
            <Button
              size="sm"
              variant="secondary"
              icon={<Download className="size-4" aria-hidden />}
              onClick={() => download('/reports/data-quality.csv')}
            >
              Download CSV
            </Button>
          }
        />
        {quality.isPending ? (
          <LoadingBlock />
        ) : quality.isError ? (
          <ErrorState error={quality.error} onRetry={() => quality.refetch()} />
        ) : (
          <div className="grid gap-0 xl:grid-cols-2">
            <div className="border-b border-line xl:border-r xl:border-b-0">
              <p className="px-4 pt-3 text-xs font-semibold text-ink-3 uppercase">Uploads</p>
              <TableWrap>
                <Table>
                  <THead>
                    <tr>
                      <TH>Institution</TH>
                      <TH className="text-right">Files</TH>
                      <TH className="text-right">Rows</TH>
                      <TH className="text-right">Rejected</TH>
                      <TH className="text-right">Acceptance</TH>
                    </tr>
                  </THead>
                  <tbody>
                    {quality.data.uploads.map((u) => (
                      <TR key={u.institution_code}>
                        <TD className="font-mono text-xs">{u.institution_code}</TD>
                        <TD className="text-right tabular">{u.uploads}</TD>
                        <TD className="text-right tabular">{formatNumber(u.rows_processed)}</TD>
                        <TD className="text-right tabular">{formatNumber(u.rows_rejected)}</TD>
                        <TD className="text-right tabular">{formatPercent(u.acceptance_rate_pct)}</TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            </div>
            <div>
              <p className="px-4 pt-3 text-xs font-semibold text-ink-3 uppercase">Findings by rule</p>
              <TableWrap>
                <Table>
                  <THead>
                    <tr>
                      <TH>Rule</TH>
                      <TH className="text-right">Open</TH>
                      <TH className="text-right">Review / esc.</TH>
                      <TH className="text-right">Closed</TH>
                    </tr>
                  </THead>
                  <tbody>
                    {quality.data.findings.map((r) => (
                      <TR key={`${r.institution_code}-${r.rule_code}`}>
                        <TD>
                          <p className="text-[13px] font-medium">{r.rule_title}</p>
                          <p className="font-mono text-[11px] text-ink-3">{r.institution_code}</p>
                        </TD>
                        <TD className="text-right tabular">{r.open}</TD>
                        <TD className="text-right tabular">{r.in_review + r.escalated}</TD>
                        <TD className="text-right tabular">{r.resolved + r.dismissed}</TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
