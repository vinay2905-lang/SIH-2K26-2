import { useQuery } from '@tanstack/react-query'
import { ArrowRight, BadgeCheck, ShieldAlert, Upload, UserCheck, Users } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { BatchStatusBadge, ReviewSignalNote } from '@/components/domain'
import { ButtonLink } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState, ErrorState, LoadingBlock } from '@/components/ui/Feedback'
import { PageHeader } from '@/components/ui/Layout'
import { Meter, StatTile } from '@/components/ui/Stat'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { api } from '@/lib/api'
import { PERMISSIONS, useAuth } from '@/lib/auth'
import { formatNumber, formatPercent, formatRelative } from '@/lib/format'
import type { InstitutionDashboard as Data } from '@/types/api'
import { CategoryBars } from './charts'
import { Definitions, IntakeStatusBadge, UtilisationCell, YearSelect } from './shared'

export function InstitutionDashboard() {
  const { can } = useAuth()
  const [year, setYear] = useState<string>()
  const query = useQuery({
    queryKey: ['dashboard', 'institution', year],
    queryFn: () => api.get<Data>('/dashboard/institution', { academic_year: year }),
    placeholderData: (previous) => previous,
  })

  if (query.isPending) return <LoadingBlock label="Loading dashboard…" />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const data = query.data
  const k = data.kpis
  const hasData = k.active_enrolments > 0

  return (
    <div className={query.isFetching ? 'opacity-70 transition-opacity' : undefined}>
      <PageHeader
        title={data.institution.name}
        description={`Admissions and record quality for academic year ${data.academic_year}.`}
        meta={<span className="font-mono text-xs text-ink-3">{data.institution.code}</span>}
        actions={
          <>
            <YearSelect value={year ?? data.academic_year} onChange={setYear} />
            {can(PERMISSIONS.uploadsCreate) && (
              <ButtonLink to="/uploads" variant="primary" icon={<Upload className="size-4" aria-hidden />}>
                Upload records
              </ButtonLink>
            )}
          </>
        }
      />

      {!hasData && (
        <Card className="mb-6">
          <EmptyState
            icon={<Upload className="size-5" aria-hidden />}
            title={`No admissions submitted for ${data.academic_year} yet`}
            description="Upload your student admission records after admissions close. Validation runs automatically and findings appear here."
            action={
              can(PERMISSIONS.uploadsCreate) && (
                <ButtonLink to="/uploads" variant="primary">
                  Go to uploads
                </ButtonLink>
              )
            }
          />
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Active enrolments"
          value={formatNumber(k.active_enrolments)}
          detail={`${formatNumber(k.distinct_students)} distinct students · status ${data.counted_statuses.join(', ')}`}
          icon={<Users className="size-4" />}
        />
        <StatTile
          label="Intake utilisation"
          value={formatPercent(k.utilisation_pct)}
          detail={
            <span className="block">
              <Meter
                className="mb-1.5"
                value={k.regular_enrolled}
                max={k.approved_intake}
                label="Regular seats used of approved intake"
                status={k.regular_enrolled > k.approved_intake ? 'exceeded' : 'within'}
              />
              {formatNumber(k.regular_enrolled)} of {formatNumber(k.approved_intake)} approved seats
              {k.programmes_over_intake > 0 && (
                <span className="font-medium text-critical-ink">
                  {' '}
                  · {k.programmes_over_intake} over intake
                </span>
              )}
            </span>
          }
        />
        <StatTile
          label="Open findings"
          value={formatNumber(k.open_findings)}
          detail={`${formatNumber(k.high_severity_open)} high severity · ${formatNumber(k.escalated)} escalated`}
          icon={<ShieldAlert className="size-4" />}
          tone={k.high_severity_open ? 'attention' : 'default'}
        />
        <StatTile
          label="Upload acceptance"
          value={formatPercent(k.acceptance_rate_pct)}
          detail={`${formatNumber(k.rows_accepted)} rows accepted · ${formatNumber(k.rows_rejected)} rejected`}
          icon={<BadgeCheck className="size-4" />}
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Intake compliance by programme"
            description="Regular-seat admissions against approved intake; supernumerary seats counted separately."
          />
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  <TH>Programme</TH>
                  <TH>Regular seats</TH>
                  <TH className="text-right">Supernumerary</TH>
                  <TH className="text-right">NRI / OCI / FN</TH>
                  <TH>Status</TH>
                </tr>
              </THead>
              <tbody>
                {data.programmes.map((p) => (
                  <TR key={p.programme_id}>
                    <TD>
                      <p className="font-medium">{p.name}</p>
                      <p className="font-mono text-xs text-ink-3">{p.code}</p>
                    </TD>
                    <TD>
                      <UtilisationCell
                        used={p.regular_enrolled}
                        limit={p.approved_intake}
                        pct={p.utilisation_pct}
                        status={p.status}
                      />
                    </TD>
                    <TD className="text-right tabular">
                      {formatNumber(p.supernumerary_enrolled)}
                      <span className="text-ink-3"> / {formatNumber(p.supernumerary_seats ?? 0)}</span>
                    </TD>
                    <TD className="text-right text-ink-2 tabular">
                      {p.nri} / {p.oci} / {p.foreign_national}
                    </TD>
                    <TD>
                      <IntakeStatusBadge status={p.status} />
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </Card>

        <Card>
          <CardHeader
            title="Open findings"
            description="By category, all academic years"
            actions={
              <Link
                to="/exceptions"
                className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-600 hover:text-brand-700"
              >
                Review queue <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            }
          />
          <CardBody className="space-y-5">
            <CategoryBars data={data.findings_by_category} emptyLabel="No open findings. Nice work." />
            <div className="grid grid-cols-3 gap-2 border-t border-line pt-4 text-center">
              {(['high', 'medium', 'low'] as const).map((s) => (
                <Link
                  key={s}
                  to={`/exceptions?severity=${s}`}
                  className="rounded-lg px-2 py-1.5 hover:bg-slate-50"
                >
                  <p className="text-lg font-semibold tabular">{formatNumber(data.findings_by_severity[s] ?? 0)}</p>
                  <p className="text-xs text-ink-3 capitalize">{s}</p>
                </Link>
              ))}
            </div>
            <ReviewSignalNote />
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card>
          <CardHeader title="Admission categories" description={`Active enrolments, ${data.academic_year}`} />
          <CardBody>
            <dl className="grid grid-cols-2 gap-3">
              {[
                ['NRI category', k.nri],
                ['OCI status', k.oci],
                ['Foreign nationals', k.foreign_national],
                ['Supernumerary seats used', k.supernumerary_enrolled],
              ].map(([label, value]) => (
                <div key={label as string} className="rounded-lg bg-slate-50 px-3 py-2.5">
                  <dt className="text-xs text-ink-3">{label}</dt>
                  <dd className="mt-0.5 text-lg font-semibold tabular">{formatNumber(value as number)}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-line px-3 py-2.5 text-[13px]">
              <UserCheck className="size-4 text-brand-600" aria-hidden />
              {k.consent_coverage_pct === null ? (
                <span className="text-ink-3">Consent coverage appears once records are submitted.</span>
              ) : (
                <span>
                  Verification consent on record for{' '}
                  <span className="font-semibold tabular">{formatPercent(k.consent_coverage_pct, 0)}</span> of
                  students ({formatNumber(k.consent_granted)})
                </span>
              )}
            </div>
          </CardBody>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader
            title="Recent uploads"
            actions={
              <Link
                to="/uploads"
                className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-600 hover:text-brand-700"
              >
                All uploads <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            }
          />
          {data.recent_uploads.length === 0 ? (
            <EmptyState title="No uploads yet" description="Your first CSV upload will appear here." />
          ) : (
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <TH>File</TH>
                    <TH>Status</TH>
                    <TH className="text-right">Rows</TH>
                    <TH className="text-right">Rejected</TH>
                    <TH className="text-right">New findings</TH>
                    <TH>Uploaded</TH>
                  </tr>
                </THead>
                <tbody>
                  {data.recent_uploads.map((u) => (
                    <TR key={u.id}>
                      <TD>
                        <Link to={`/uploads/${u.id}`} className="font-medium text-brand-600 hover:underline">
                          {u.filename}
                        </Link>
                      </TD>
                      <TD>
                        <BatchStatusBadge status={u.status} />
                      </TD>
                      <TD className="text-right tabular">{formatNumber(u.total_rows)}</TD>
                      <TD className="text-right tabular">{formatNumber(u.rejected_rows)}</TD>
                      <TD className="text-right tabular">{formatNumber(u.findings_opened)}</TD>
                      <TD className="text-ink-2">{formatRelative(u.created_at)}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </Card>
      </div>

      <Definitions definitions={data.definitions} generatedAt={data.generated_at} />
    </div>
  )
}
