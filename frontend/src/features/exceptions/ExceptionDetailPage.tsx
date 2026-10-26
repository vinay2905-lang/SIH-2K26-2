import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, EyeOff, Lightbulb, Lock, Scale } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { FindingStatusBadge, ReviewSignalNote, SeverityBadge } from '@/components/domain'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert, ErrorState, LoadingBlock, errorMessage } from '@/components/ui/Feedback'
import { Field, Textarea } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/Layout'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { formatDateTime, formatNumber, humanize } from '@/lib/format'
import type { Fact, FindingDetail } from '@/types/api'

const ACTIONS: Record<string, { label: string; variant: 'primary' | 'secondary' | 'danger' | 'subtle'; needsComment: boolean; help: string }> = {
  start_review: { label: 'Start review', variant: 'secondary', needsComment: false, help: 'Mark that you are looking into this.' },
  resolve: { label: 'Resolve', variant: 'primary', needsComment: true, help: 'The issue was corrected or is explained.' },
  dismiss: { label: 'Dismiss', variant: 'secondary', needsComment: true, help: 'Not an issue (for example a legitimate case).' },
  escalate: { label: 'Escalate to central review', variant: 'subtle', needsComment: true, help: 'Needs a central reviewer’s decision.' },
  reopen: { label: 'Reopen', variant: 'secondary', needsComment: true, help: 'Return the finding to the open queue.' },
  comment: { label: 'Add comment', variant: 'secondary', needsComment: true, help: 'Note without changing status.' },
}

function FactList({ facts }: { facts: Fact[] }) {
  return (
    <dl className="divide-y divide-line rounded-lg border border-line">
      {facts.map((fact) => (
        <div key={fact.label} className="grid gap-1 px-4 py-2.5 text-sm sm:grid-cols-[240px_1fr] sm:gap-4">
          <dt className="text-ink-3">{fact.label}</dt>
          <dd className="font-medium break-words text-ink tabular">
            {typeof fact.value === 'number' ? formatNumber(fact.value) : fact.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function ReviewPanel({ finding }: { finding: FindingDetail }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [comment, setComment] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: (action: string) =>
      api.post<FindingDetail>(`/findings/${finding.id}/actions`, { action, comment: comment.trim() || null }),
    onSuccess: (data, action) => {
      queryClient.setQueryData(['finding', finding.id], data)
      queryClient.invalidateQueries({ queryKey: ['findings'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      setComment('')
      toast.success(`${ACTIONS[action]?.label ?? 'Action'} recorded.`)
    },
    onSettled: () => setPending(null),
  })

  if (finding.allowed_actions.length === 0) {
    return (
      <Alert tone="info" title="View only">
        Your role can view findings but not act on them. An institution administrator or central reviewer
        reviews this queue.
      </Alert>
    )
  }

  const tooShort = comment.trim().length < 5
  return (
    <div className="space-y-3">
      <Field
        label="Reviewer comment"
        htmlFor="review-comment"
        hint="Required for every action except starting a review. Saved in the finding history and audit trail."
      >
        <Textarea
          id="review-comment"
          value={comment}
          maxLength={1000}
          onChange={(event) => setComment(event.target.value)}
          placeholder="What did you check, and what did you decide?"
        />
      </Field>
      {mutation.isError && <Alert tone="danger">{errorMessage(mutation.error)}</Alert>}
      <div className="flex flex-wrap gap-2">
        {finding.allowed_actions.map((action) => {
          const meta = ACTIONS[action]
          if (!meta) return null
          return (
            <Button
              key={action}
              variant={meta.variant}
              size="sm"
              title={meta.help}
              loading={pending === action}
              disabled={(meta.needsComment && tooShort) || mutation.isPending}
              onClick={() => {
                setPending(action)
                mutation.mutate(action)
              }}
            >
              {meta.label}
            </Button>
          )
        })}
      </div>
      {finding.rule?.central_resolution && !finding.allowed_actions.includes('resolve') && finding.status !== 'resolved' && (
        <p className="flex items-start gap-1.5 text-xs text-ink-3">
          <Lock className="mt-px size-3.5 shrink-0" aria-hidden />
          This type of finding is resolved by a central reviewer. You can comment or escalate it.
        </p>
      )}
    </div>
  )
}

export function ExceptionDetailPage() {
  const { id = '' } = useParams()
  const query = useQuery({ queryKey: ['finding', id], queryFn: () => api.get<FindingDetail>(`/findings/${id}`) })

  if (query.isPending) return <LoadingBlock />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const f = query.data

  return (
    <div>
      <PageHeader
        back={{ to: '/exceptions', label: 'Exception queue' }}
        title={f.title}
        meta={
          <>
            <SeverityBadge value={f.severity} />
            <FindingStatusBadge status={f.status} />
            <Badge tone="outline">{f.category_label}</Badge>
            <span className="font-mono text-xs text-ink-3">{f.rule_code}</span>
          </>
        }
      />

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader title="What was flagged" />
            <CardBody className="space-y-4">
              <p className="text-[15px] leading-relaxed text-ink">{f.reason}</p>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-[13px] text-ink-2">
                <span>
                  Institution: <span className="font-medium text-ink">{f.institution.name}</span>
                </span>
                {f.student && (
                  <span>
                    Student:{' '}
                    <Link to={`/students/${f.student.id}`} className="font-medium text-brand-600 hover:underline">
                      {f.student.full_name} ({f.student.institution_student_id})
                    </Link>
                  </span>
                )}
                {f.academic_year && <span>Academic year: {f.academic_year}</span>}
                {f.source_batch_id && (
                  <Link to={`/uploads/${f.source_batch_id}`} className="font-medium text-brand-600 hover:underline">
                    Source upload
                  </Link>
                )}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Evidence" description="The values the rule compared. Identifiers are masked." />
            <CardBody className="space-y-4">
              <FactList facts={f.evidence} />
              {f.restricted_evidence && f.restricted_evidence.length > 0 && (
                <div>
                  <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-violet-700">
                    <Lock className="size-3.5" aria-hidden /> Visible to central reviewers only
                  </p>
                  <FactList facts={f.restricted_evidence} />
                </div>
              )}
              {f.restricted_evidence_hidden && (
                <p className="flex items-start gap-1.5 text-xs text-ink-3">
                  <EyeOff className="mt-px size-3.5 shrink-0" aria-hidden />
                  Details about other institutions involved are visible only to central reviewers.
                </p>
              )}
            </CardBody>
          </Card>

          {f.rule && (
            <Card>
              <CardHeader title="About this rule" />
              <CardBody className="grid gap-5 sm:grid-cols-2">
                <div>
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-ink-2">
                    <BookOpen className="size-3.5" aria-hidden /> What it checks
                  </p>
                  <p className="text-[13px] text-ink">{f.rule.checks}</p>
                </div>
                <div>
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-ink-2">
                    <Lightbulb className="size-3.5" aria-hidden /> Why it matters
                  </p>
                  <p className="text-[13px] text-ink">{f.rule.rationale}</p>
                </div>
                {f.rule.assumption && (
                  <div className="sm:col-span-2">
                    <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-ink-2">
                      <Scale className="size-3.5" aria-hidden /> Policy assumption (configurable)
                    </p>
                    <p className="text-[13px] text-ink">{f.rule.assumption}</p>
                  </div>
                )}
              </CardBody>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Recommended action" />
            <CardBody className="space-y-4">
              <p className="text-[13px] leading-relaxed text-ink">{f.recommended_action}</p>
              <ReviewPanel finding={f} />
              <ReviewSignalNote />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="History" />
            <CardBody>
              <ol className="relative space-y-4 border-l border-line pl-5">
                {f.history.map((h, index) => (
                  <li key={index} className="relative">
                    <span
                      className="absolute top-1.5 -left-[25px] size-2.5 rounded-full border-2 border-white bg-brand-500 ring-1 ring-line"
                      aria-hidden
                    />
                    <p className="text-[13px]">
                      <span className="font-medium text-ink">{humanize(h.action)}</span>
                      {h.to_status && h.from_status !== h.to_status && (
                        <span className="text-ink-3"> → {humanize(h.to_status)}</span>
                      )}
                    </p>
                    <p className="text-xs text-ink-3">
                      {h.actor_name} · {formatDateTime(h.created_at)}
                    </p>
                    {h.comment && (
                      <p className="mt-1 rounded-md bg-slate-50 px-2.5 py-1.5 text-[13px] text-ink-2">{h.comment}</p>
                    )}
                  </li>
                ))}
              </ol>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  )
}
