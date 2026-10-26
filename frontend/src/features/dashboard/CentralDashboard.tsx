import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Building2, Download, GitCompareArrows, ShieldAlert, Users } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { ReviewSignalNote } from '@/components/domain'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { ErrorState, LoadingBlock } from '@/components/ui/Feedback'
import { PageHeader } from '@/components/ui/Layout'
import { Meter, StatTile } from '@/components/ui/Stat'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { useToast } from '@/components/ui/Toast'
import { api, downloadFile } from '@/lib/api'
import { formatNumber, formatPercent, formatRelative } from '@/lib/format'
import type { CentralDashboard as Data } from '@/types/api'
import { CategoryBars, UploadQualityChart } from './charts'
import { Definitions, UtilisationCell, YearSelect } from './shared'

export function CentralDashboard() {
  const toast = useToast()
  const [year, setYear] = useState<string>()
  const query = useQuery({
    queryKey: ['dashboard', 'central', year],
    queryFn: () => api.get<Data>('/dashboard/central', { academic_year: year }),
    placeholderData: (previous) => previous,
  })

  if (query.isPending) return <LoadingBlock label="Loading dashboard…" />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const data = query.data
  const k = data.kpis

  return (
    <div className={query.isFetching ? 'opacity-70 transition-opacity' : undefined}>
      <PageHeader
        title="Central monitoring"
        description={`Admissions, intake compliance and data quality across institutions for ${data.academic_year}.`}
        actions={
          <>
            <YearSelect value={year ?? data.academic_year} onChange={setYear} />
            <Button
              variant="secondary"
              icon={<Download className="size-4" aria-hidden />}
              onClick={() =>
                downloadFile('/reports/enrolment.csv', { academic_year: data.academic_year }).catch((e) =>
                  toast.error(e.message),
                )
              }
            >
              Export CSV
            </Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Institutions reporting"
          value={
            <>
              {formatNumber(k.institutions_reporting)}
              <span className="text-base font-medium text-ink-3"> / {formatNumber(k.institutions_total)}</span>
            </>
          }
          detail="With at least one active enrolment this year"
          icon={<Building2 className="size-4" />}
        />
        <StatTile
          label="Active enrolments"
          value={formatNumber(k.active_enrolments)}
          detail={`${formatPercent(k.utilisation_pct)} of ${formatNumber(k.approved_intake)} approved seats used`}
          icon={<Users className="size-4" />}
        />
        <StatTile
          label="Open findings"
          value={formatNumber(k.open_findings)}
          detail={`${formatNumber(k.high_severity_open)} high severity · ${formatNumber(k.escalated)} escalated to you`}
          icon={<ShieldAlert className="size-4" />}
          tone={k.escalated ? 'attention' : 'default'}
        />
        <StatTile
          label="Cross-institution matches"
          value={formatNumber(k.cross_institution_flags)}
          detail={`${formatNumber(k.programmes_over_intake)} programmes over intake`}
          icon={<GitCompareArrows className="size-4" />}
          tone={k.cross_institution_flags ? 'attention' : 'default'}
        />
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Institutions"
          description="Sorted by institution code. Utilisation counts regular-seat admissions against approved intake."
        />
        <TableWrap>
          <Table>
            <THead>
              <tr>
                <TH>Institution</TH>
                <TH className="text-right">Enrolments</TH>
                <TH>Utilisation</TH>
                <TH className="text-right">Over intake</TH>
                <TH className="text-right">Open findings</TH>
                <TH className="text-right">Row acceptance</TH>
                <TH>Last upload</TH>
              </tr>
            </THead>
            <tbody>
              {data.institutions.map((inst) => (
                <TR key={inst.id}>
                  <TD>
                    <p className="font-medium">{inst.name}</p>
                    <p className="text-xs text-ink-3">
                      <span className="font-mono">{inst.code}</span> · {inst.state} · {inst.institution_type}
                    </p>
                  </TD>
                  <TD className="text-right tabular">
                    {inst.reporting ? (
                      formatNumber(inst.active_enrolments)
                    ) : (
                      <Badge tone="outline">Not reported</Badge>
                    )}
                  </TD>
                  <TD>
                    <UtilisationCell
                      used={inst.regular_enrolled}
                      limit={inst.approved_intake || null}
                      pct={inst.utilisation_pct}
                      status={inst.regular_enrolled > inst.approved_intake ? 'exceeded' : 'within'}
                    />
                  </TD>
                  <TD className="text-right tabular">
                    {inst.programmes_over_intake ? (
                      <span className="font-semibold text-critical-ink">{inst.programmes_over_intake}</span>
                    ) : (
                      <span className="text-ink-3">0</span>
                    )}
                  </TD>
                  <TD className="text-right tabular">
                    <Link
                      to={`/exceptions?institution_id=${inst.id}`}
                      className="font-medium text-brand-600 hover:underline"
                    >
                      {formatNumber(inst.open_findings)}
                    </Link>
                    {inst.high_severity_open > 0 && (
                      <span className="ml-1 text-xs text-critical-ink">({inst.high_severity_open} high)</span>
                    )}
                  </TD>
                  <TD className="text-right tabular">{formatPercent(inst.acceptance_rate_pct)}</TD>
                  <TD className="text-ink-2">{inst.last_upload_at ? formatRelative(inst.last_upload_at) : '—'}</TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      </Card>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Upload data quality"
            description="Rows accepted and rejected per day across all institutions, last 30 days"
          />
          <CardBody>
            <UploadQualityChart data={data.upload_quality} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader
            title="Open findings by category"
            actions={
              <Link
                to="/exceptions?status=escalated"
                className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-600 hover:text-brand-700"
              >
                Escalated <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            }
          />
          <CardBody className="space-y-5">
            <CategoryBars data={data.findings_by_category} emptyLabel="No open findings." />
            <div className="border-t border-line pt-4">
              <p className="mb-2 text-xs font-medium text-ink-3">Overall intake utilisation</p>
              <Meter
                value={k.regular_enrolled}
                max={k.approved_intake}
                label="Regular seats used across institutions"
                status={k.regular_enrolled > k.approved_intake ? 'exceeded' : 'within'}
              />
              <p className="mt-1.5 text-xs text-ink-3 tabular">
                {formatNumber(k.regular_enrolled)} of {formatNumber(k.approved_intake)} approved regular seats
              </p>
            </div>
            <ReviewSignalNote />
          </CardBody>
        </Card>
      </div>

      <Definitions definitions={data.definitions} generatedAt={data.generated_at} />
    </div>
  )
}
