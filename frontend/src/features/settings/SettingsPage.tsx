import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert, ErrorState, LoadingBlock, errorMessage } from '@/components/ui/Feedback'
import { Checkbox, Field, Input, Select } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/Layout'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { humanize } from '@/lib/format'
import type { PolicySettings, SettingsView } from '@/types/api'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const STATUSES = ['ENROLLED', 'CANCELLED', 'WITHDRAWN']

export function SettingsPage() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['settings'], queryFn: () => api.get<SettingsView>('/settings') })
  const [policy, setPolicy] = useState<PolicySettings | null>(null)
  useEffect(() => {
    if (query.data && !policy) setPolicy(query.data.policy)
  }, [query.data, policy])

  const save = useMutation({
    mutationFn: (value: PolicySettings) => api.put<SettingsView>('/settings', value),
    onSuccess: (data) => {
      queryClient.setQueryData(['settings'], data)
      setPolicy(data.policy)
      queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'settings' })
      toast.success('Policy saved. All records were re-validated against the new settings.')
    },
  })

  if (query.isPending || !policy) return <LoadingBlock />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const view = query.data
  const preset = view.identifier_presets.find((p) => p.pattern === policy.identifier_format.pattern)?.key ?? 'custom'
  const dirty = JSON.stringify(policy) !== JSON.stringify(view.policy)

  const update = <K extends keyof PolicySettings>(key: K, value: PolicySettings[K]) =>
    setPolicy((p) => (p ? { ...p, [key]: value } : p))

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader
        title="Validation policy"
        description="Configurable assumptions used by the validation rules. None of these are official AICTE or APAAR rules; set them from authoritative documentation before any real use."
        actions={
          <Button icon={<Save className="size-4" aria-hidden />} disabled={!dirty} loading={save.isPending} onClick={() => save.mutate(policy)}>
            Save and re-validate
          </Button>
        }
      />
      {save.isError && <Alert tone="danger">{errorMessage(save.error)}</Alert>}

      <Card>
        <CardHeader title="APAAR identifier format" description="Used to check presence and shape only. A format check never proves an identifier is authentic." />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Field label="Preset" htmlFor="s-preset" className="sm:col-span-2">
            <Select
              id="s-preset"
              value={preset}
              onChange={(e) => {
                const next = view.identifier_presets.find((p) => p.key === e.target.value)
                if (next) update('identifier_format', { pattern: next.pattern, label: next.label, example: next.example })
              }}
            >
              {view.identifier_presets.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
              {preset === 'custom' && <option value="custom">Custom pattern</option>}
            </Select>
          </Field>
          <Field label="Pattern (regular expression, whole value)" htmlFor="s-pattern">
            <Input
              id="s-pattern"
              className="font-mono"
              value={policy.identifier_format.pattern}
              onChange={(e) => update('identifier_format', { ...policy.identifier_format, pattern: e.target.value })}
            />
          </Field>
          <Field label="Description shown to users" htmlFor="s-label">
            <Input
              id="s-label"
              value={policy.identifier_format.label}
              onChange={(e) => update('identifier_format', { ...policy.identifier_format, label: e.target.value })}
            />
          </Field>
          <p className="text-xs text-ink-3 sm:col-span-2">
            {view.identifier_presets.find((p) => p.key === preset)?.note}
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Intake counting" description="Which enrolment statuses count toward approved intake." />
        <CardBody className="flex flex-wrap gap-6">
          {STATUSES.map((status) => (
            <Checkbox
              key={status}
              id={`s-count-${status}`}
              label={humanize(status)}
              checked={policy.intake_policy.count_statuses.includes(status)}
              onChange={(e) => {
                const set = new Set(policy.intake_policy.count_statuses)
                if (e.target.checked) set.add(status)
                else set.delete(status)
                update('intake_policy', { count_statuses: STATUSES.filter((s) => set.has(s)) })
              }}
            />
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Consistency thresholds" />
        <CardBody className="grid gap-4 sm:grid-cols-3">
          <Field label="Minimum age at admission" htmlFor="s-min">
            <Input
              id="s-min"
              type="number"
              min={0}
              max={100}
              value={policy.consistency.min_age_at_admission}
              onChange={(e) => update('consistency', { ...policy.consistency, min_age_at_admission: Number(e.target.value) })}
            />
          </Field>
          <Field label="Maximum age at admission" htmlFor="s-max">
            <Input
              id="s-max"
              type="number"
              min={1}
              max={120}
              value={policy.consistency.max_age_at_admission}
              onChange={(e) => update('consistency', { ...policy.consistency, max_age_at_admission: Number(e.target.value) })}
            />
          </Field>
          <Field label="Academic year starts in" htmlFor="s-month">
            <Select
              id="s-month"
              value={policy.consistency.academic_year_start_month}
              onChange={(e) =>
                update('consistency', { ...policy.consistency, academic_year_start_month: Number(e.target.value) })
              }
            >
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>
                  {m}
                </option>
              ))}
            </Select>
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Validation rules"
          description="Switching a rule off stops new findings from it. Existing findings stay in the queue for review."
        />
        <ul className="divide-y divide-line">
          {view.rules.map((rule) => {
            const enabled = policy.rules_enabled[rule.code] ?? true
            return (
              <li key={rule.code} className="flex items-start gap-4 px-5 py-3">
                <Checkbox
                  id={`rule-${rule.code}`}
                  checked={enabled}
                  onChange={(e) => update('rules_enabled', { ...policy.rules_enabled, [rule.code]: e.target.checked })}
                  label={
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{rule.title}</span>
                      <Badge tone="outline">{rule.category_label}</Badge>
                      <span className="font-mono text-[11px] text-ink-3">{rule.code}</span>
                    </span>
                  }
                  description={rule.assumption ?? undefined}
                />
              </li>
            )
          })}
        </ul>
      </Card>
    </div>
  )
}
