import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { CloudUpload, Download, FileSpreadsheet, FlaskConical, Inbox } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { BatchStatusBadge } from '@/components/domain'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert, EmptyState, ErrorState, LoadingBlock, errorMessage } from '@/components/ui/Feedback'
import { PageHeader, Pagination } from '@/components/ui/Layout'
import { Table, TableWrap, TD, TH, THead, TR } from '@/components/ui/Table'
import { useToast } from '@/components/ui/Toast'
import { api, downloadFile } from '@/lib/api'
import { PERMISSIONS, useAuth } from '@/lib/auth'
import { formatDateTime, formatNumber } from '@/lib/format'
import { useAppConfig } from '@/lib/queries'
import type { Page, UploadBatch } from '@/types/api'

const PAGE_SIZE = 15

function UploadCard() {
  const config = useAppConfig()
  const toast = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const maxBytes = config.data?.upload_limits.max_bytes ?? 5 * 1024 * 1024

  const upload = useMutation({
    mutationFn: (selected: File) => {
      const form = new FormData()
      form.append('file', selected)
      return api.upload<UploadBatch>('/uploads/students', form)
    },
    onSuccess: (batch) => {
      queryClient.invalidateQueries()
      toast.success(`Upload processed: ${batch.rejected_rows} of ${batch.total_rows} rows rejected.`)
      navigate(`/uploads/${batch.id}`)
    },
  })

  function choose(selected: File | undefined | null) {
    upload.reset()
    if (!selected) return
    if (!selected.name.toLowerCase().endsWith('.csv')) {
      toast.error('Choose a .csv file.')
      return
    }
    if (selected.size > maxBytes) {
      toast.error(`File is larger than ${Math.round(maxBytes / 1024 / 1024)} MB.`)
      return
    }
    setFile(selected)
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    choose(event.dataTransfer.files?.[0])
  }

  return (
    <Card>
      <CardHeader
        title="Submit student admission records"
        description="CSV, UTF-8, one row per admission. Valid rows are saved; invalid rows are reported with reasons."
        actions={
          <>
            <Button
              size="sm"
              variant="secondary"
              icon={<Download className="size-4" aria-hidden />}
              onClick={() => downloadFile('/uploads/template.csv').catch((e) => toast.error(e.message))}
            >
              CSV template
            </Button>
            {config.data?.demo_mode && (
              <Button
                size="sm"
                variant="subtle"
                icon={<FlaskConical className="size-4" aria-hidden />}
                onClick={() => downloadFile('/demo/sample-upload.csv').catch((e) => toast.error(e.message))}
              >
                Demo sample file
              </Button>
            )}
          </>
        }
      />
      <CardBody className="space-y-4">
        <div
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={clsx(
            'flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
            dragging ? 'border-brand-500 bg-brand-50' : 'border-line-strong bg-slate-50/60',
          )}
        >
          <div className="mb-3 flex size-11 items-center justify-center rounded-full bg-white text-brand-600 shadow-xs ring-1 ring-line">
            <CloudUpload className="size-5" aria-hidden />
          </div>
          {file ? (
            <div className="flex items-center gap-2 text-sm">
              <FileSpreadsheet className="size-4 text-good" aria-hidden />
              <span className="font-medium">{file.name}</span>
              <span className="text-ink-3">({formatNumber(Math.ceil(file.size / 1024))} KB)</span>
            </div>
          ) : (
            <>
              <p className="text-sm font-medium">Drag and drop a CSV file here</p>
              <p className="mt-1 text-xs text-ink-3">
                Up to {Math.round(maxBytes / 1024 / 1024)} MB and{' '}
                {formatNumber(config.data?.upload_limits.max_rows ?? 5000)} rows
              </p>
            </>
          )}
          <div className="mt-4 flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => input.current?.click()}>
              {file ? 'Choose another file' : 'Browse files'}
            </Button>
            {file && (
              <Button size="sm" loading={upload.isPending} onClick={() => upload.mutate(file)}>
                Upload and validate
              </Button>
            )}
          </div>
          <input
            ref={input}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            aria-label="Choose CSV file"
            onChange={(event) => {
              choose(event.target.files?.[0])
              event.target.value = ''
            }}
          />
        </div>
        {upload.isError && (
          <Alert tone="danger" title="Upload failed">
            {errorMessage(upload.error)}
          </Alert>
        )}
        <details className="text-[13px]">
          <summary className="cursor-pointer font-medium text-ink-2 hover:text-ink">Expected columns</summary>
          <div className="mt-3 overflow-x-auto rounded-lg border border-line">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-ink-3">
                <tr>
                  <th className="px-3 py-2 font-medium">Column</th>
                  <th className="px-3 py-2 font-medium">Required</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2 font-medium">Example</th>
                </tr>
              </thead>
              <tbody>
                {(config.data?.columns ?? []).map((c) => (
                  <tr key={c.name} className="border-t border-line">
                    <td className="px-3 py-1.5 font-mono">{c.name}</td>
                    <td className="px-3 py-1.5">{c.required ? 'Yes' : 'Optional'}</td>
                    <td className="px-3 py-1.5 text-ink-2">{c.description}</td>
                    <td className="px-3 py-1.5 font-mono text-ink-3">{c.example}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </CardBody>
    </Card>
  )
}

export function UploadsPage() {
  const { can, user } = useAuth()
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['uploads', page],
    queryFn: () => api.get<Page<UploadBatch>>('/uploads', { page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })
  const central = !user?.institution

  return (
    <div className="space-y-6">
      <PageHeader
        title="Uploads"
        description={
          central
            ? 'Submissions from all institutions, newest first.'
            : 'Submit admission records and review how each file was processed.'
        }
      />
      {can(PERMISSIONS.uploadsCreate) && <UploadCard />}

      <Card>
        <CardHeader title="Upload history" />
        {query.isPending ? (
          <LoadingBlock />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState icon={<Inbox className="size-5" aria-hidden />} title="No uploads yet" />
        ) : (
          <>
            <TableWrap>
              <Table>
                <THead>
                  <tr>
                    <TH>File</TH>
                    {central && <TH>Institution</TH>}
                    <TH>Status</TH>
                    <TH className="text-right">Rows</TH>
                    <TH className="text-right">Created</TH>
                    <TH className="text-right">Updated</TH>
                    <TH className="text-right">Rejected</TH>
                    <TH className="text-right">New findings</TH>
                    <TH>Uploaded</TH>
                  </tr>
                </THead>
                <tbody>
                  {query.data.items.map((b) => (
                    <TR key={b.id}>
                      <TD>
                        <Link to={`/uploads/${b.id}`} className="font-medium text-brand-600 hover:underline">
                          {b.original_filename}
                        </Link>
                        <p className="text-xs text-ink-3">{b.uploaded_by?.full_name ?? '—'}</p>
                      </TD>
                      {central && <TD className="font-mono text-xs">{b.institution.code}</TD>}
                      <TD>
                        <BatchStatusBadge status={b.status} />
                      </TD>
                      <TD className="text-right tabular">{formatNumber(b.total_rows)}</TD>
                      <TD className="text-right tabular">{formatNumber(b.created_rows)}</TD>
                      <TD className="text-right tabular">{formatNumber(b.updated_rows)}</TD>
                      <TD className={clsx('text-right tabular', b.rejected_rows > 0 && 'font-semibold text-critical-ink')}>
                        {formatNumber(b.rejected_rows)}
                      </TD>
                      <TD className="text-right tabular">{formatNumber(b.findings_opened)}</TD>
                      <TD className="whitespace-nowrap text-ink-2">{formatDateTime(b.created_at)}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  )
}
