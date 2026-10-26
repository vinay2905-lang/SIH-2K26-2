import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Pencil } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Alert, EmptyState, ErrorState, LoadingBlock, errorMessage } from '@/components/ui/Feedback'
import { Field, Input, Select, Textarea } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/Layout'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { PERMISSIONS, useAuth } from '@/lib/auth'
import { formatDateTime, formatNumber } from '@/lib/format'
import { useAppConfig, useProgrammes } from '@/lib/queries'
import type { Programme } from '@/types/api'

interface Editing {
  programme: Programme
  year: string
}

function IntakeDialog({ editing, onClose }: { editing: Editing; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const current = editing.programme.intake_configurations.find((c) => c.academic_year === editing.year)
  const [form, setForm] = useState({
    approved_intake: String(current?.approved_intake ?? ''),
    supernumerary_seats: String(current?.supernumerary_seats ?? 0),
    source: current?.source ?? 'synthetic-demo',
    notes: current?.notes ?? '',
  })
  const mutation = useMutation({
    mutationFn: () =>
      api.put<Programme>(`/programmes/${editing.programme.id}/intake/${editing.year}`, {
        approved_intake: Number(form.approved_intake),
        supernumerary_seats: Number(form.supernumerary_seats),
        source: form.source,
        notes: form.notes || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success('Intake saved. Intake rules were re-run for this institution.')
      onClose()
    },
  })
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Approved intake · ${editing.programme.code} ${editing.year}`}
      description={editing.programme.institution.name}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="intake-form" loading={mutation.isPending}>
            Save intake
          </Button>
        </>
      }
    >
      <form
        id="intake-form"
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        {mutation.isError && (
          <Alert tone="danger" className="sm:col-span-2">
            {errorMessage(mutation.error)}
          </Alert>
        )}
        <Field label="Approved intake" htmlFor="i-intake" required>
          <Input
            id="i-intake"
            type="number"
            min={0}
            max={10000}
            required
            value={form.approved_intake}
            onChange={(e) => setForm((f) => ({ ...f, approved_intake: e.target.value }))}
          />
        </Field>
        <Field label="Supernumerary seats" htmlFor="i-super" required>
          <Input
            id="i-super"
            type="number"
            min={0}
            max={1000}
            required
            value={form.supernumerary_seats}
            onChange={(e) => setForm((f) => ({ ...f, supernumerary_seats: e.target.value }))}
          />
        </Field>
        <Field label="Source of figure" htmlFor="i-source" hint="Where this figure came from" className="sm:col-span-2">
          <Input id="i-source" value={form.source} onChange={(e) => setForm((f) => ({ ...f, source: e.target.value }))} />
        </Field>
        <Field label="Notes" htmlFor="i-notes" className="sm:col-span-2">
          <Textarea id="i-notes" value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
        </Field>
      </form>
    </Dialog>
  )
}

export function ProgrammesPage() {
  const { can, user } = useAuth()
  const config = useAppConfig()
  const years = config.data?.academic_years ?? []
  const [year, setYear] = useState<string>()
  const selectedYear = year ?? years[0]
  const programmes = useProgrammes()
  const [editing, setEditing] = useState<Editing | null>(null)
  const canEdit = can(PERMISSIONS.intakeManage)
  const central = !user?.institution

  return (
    <div>
      <PageHeader
        title="Programmes & approved intake"
        description={
          canEdit
            ? 'Approved intake and supernumerary seats per programme and year. Changes re-run intake rules immediately.'
            : 'Approved intake configured for your programmes. Contact the central team to correct a figure.'
        }
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor="p-year" className="text-[13px] font-medium whitespace-nowrap text-ink-2">
              Academic year
            </label>
            <Select id="p-year" className="h-9 w-32" value={selectedYear ?? ''} onChange={(e) => setYear(e.target.value)}>
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>
        }
      />
      <Alert tone="info" className="mb-4">
        Intake figures in this prototype are synthetic. In production they would come from AICTE approval records.
      </Alert>
      <Card>
        <CardHeader title={`Programmes (${programmes.data?.length ?? 0})`} />
        {programmes.isPending ? (
          <LoadingBlock />
        ) : programmes.isError ? (
          <ErrorState error={programmes.error} onRetry={() => programmes.refetch()} />
        ) : programmes.data.length === 0 ? (
          <EmptyState title="No programmes configured" />
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <tr>
                  {central && <TH>Institution</TH>}
                  <TH>Programme</TH>
                  <TH>Level</TH>
                  <TH className="text-right">Approved intake</TH>
                  <TH className="text-right">Supernumerary</TH>
                  <TH>Source</TH>
                  <TH>Last updated</TH>
                  {canEdit && <TH className="text-right">Edit</TH>}
                </tr>
              </THead>
              <tbody>
                {programmes.data.map((p) => {
                  const intake = p.intake_configurations.find((c) => c.academic_year === selectedYear)
                  return (
                    <TR key={p.id}>
                      {central && (
                        <TD>
                          <p className="font-mono text-xs">{p.institution.code}</p>
                          <p className="text-xs text-ink-3">{p.institution.name}</p>
                        </TD>
                      )}
                      <TD>
                        <p className="font-medium">{p.name}</p>
                        <p className="font-mono text-xs text-ink-3">{p.code}</p>
                      </TD>
                      <TD>{p.level}</TD>
                      <TD className="text-right font-medium tabular">
                        {intake ? formatNumber(intake.approved_intake) : <Badge tone="warning">Not set</Badge>}
                      </TD>
                      <TD className="text-right tabular">{intake ? formatNumber(intake.supernumerary_seats) : '—'}</TD>
                      <TD className="text-xs text-ink-2">{intake?.source ?? '—'}</TD>
                      <TD className="whitespace-nowrap text-xs text-ink-2">
                        {intake ? formatDateTime(intake.updated_at) : '—'}
                      </TD>
                      {canEdit && (
                        <TD className="text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<Pencil className="size-3.5" aria-hidden />}
                            onClick={() => selectedYear && setEditing({ programme: p, year: selectedYear })}
                          >
                            {intake ? 'Edit' : 'Set'}
                          </Button>
                        </TD>
                      )}
                    </TR>
                  )
                })}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Card>
      {editing && <IntakeDialog editing={editing} onClose={() => setEditing(null)} />}
    </div>
  )
}
