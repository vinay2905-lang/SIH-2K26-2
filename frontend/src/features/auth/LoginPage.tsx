import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  BadgeCheck,
  ChartColumn,
  FileCheck2,
  GraduationCap,
  ShieldCheck,
  Upload,
} from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Alert, errorMessage } from '@/components/ui/Feedback'
import { Field, Input } from '@/components/ui/Form'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { roleLabel } from '@/lib/format'
import type { PublicMeta } from '@/types/api'

const schema = z.object({
  email: z.string().trim().min(3, 'Enter your email address').max(254),
  password: z.string().min(1, 'Enter your password').max(256),
})
type FormValues = z.infer<typeof schema>

const FLOW = [
  { icon: Upload, title: 'Institution upload', text: 'Student-level admission records keyed by APAAR ID' },
  { icon: ShieldCheck, title: 'Explainable validation', text: 'Every flag states its rule and evidence' },
  { icon: FileCheck2, title: 'Human review', text: 'Authorised reviewers resolve or escalate' },
  { icon: ChartColumn, title: 'Monitoring & reports', text: 'Intake compliance and data quality' },
  { icon: BadgeCheck, title: 'Consent-based verification', text: 'Minimum data, only with consent' },
]

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const meta = useQuery({
    queryKey: ['public-meta'],
    queryFn: () => api.get<PublicMeta>('/meta/public'),
    staleTime: Infinity,
  })

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: '', password: '' } })

  if (user) return <Navigate to={from} replace />

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login(values.email, values.password)
      navigate(from, { replace: true })
    } catch (error) {
      setError('root', { message: errorMessage(error) })
    }
  })

  const accounts = meta.data?.demo_accounts ?? []

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-brand-900 px-12 py-12 text-white lg:flex lg:flex-col">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 -right-40 size-[520px] rounded-full bg-brand-600/25 blur-3xl"
        />
        <div className="relative flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/20">
            <GraduationCap className="size-5" aria-hidden />
          </div>
          <div className="leading-tight">
            <p className="font-semibold">APAAR Student Data Platform</p>
            <p className="text-xs text-slate-300">Smart India Hackathon 2026 · Problem statement SIH26263</p>
          </div>
        </div>

        <div className="relative mt-auto max-w-xl">
          <h1 className="text-[34px] leading-[1.15] font-semibold tracking-tight">
            Authentic, verifiable student records — linked to academic identity.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-slate-300">
            A prototype for AICTE-approved institutions to submit student-level admission data, with
            explainable validation, intake monitoring and consent-based verification.
          </p>
          <ol className="mt-8 space-y-4">
            {FLOW.map((step, index) => (
              <li key={step.title} className="flex items-start gap-3">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15">
                  <step.icon className="size-4" aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-medium">
                    <span className="mr-1.5 text-slate-400 tabular">{index + 1}.</span>
                    {step.title}
                  </p>
                  <p className="text-[13px] text-slate-400">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <p className="relative mt-auto pt-10 text-xs text-slate-400">
          Prototype using synthetic data. Not affiliated with or endorsed by AICTE. APAAR identity checks are
          simulated.
        </p>
      </section>

      <section className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2 text-brand-900">
              <GraduationCap className="size-6" aria-hidden />
              <span className="font-semibold">APAAR Student Data Platform</span>
            </div>
            <p className="mt-1 text-xs text-ink-3">SIH 2026 · SIH26263 prototype · synthetic data</p>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-1 text-sm text-ink-2">Use your platform account to continue.</p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4" noValidate>
            {errors.root?.message && <Alert tone="danger">{errors.root.message}</Alert>}
            <Field label="Email" htmlFor="email" error={errors.email?.message}>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                aria-invalid={Boolean(errors.email)}
                {...register('email')}
              />
            </Field>
            <Field label="Password" htmlFor="password" error={errors.password?.message}>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={Boolean(errors.password)}
                {...register('password')}
              />
            </Field>
            <Button type="submit" className="w-full" loading={isSubmitting}>
              Sign in
            </Button>
          </form>

          {accounts.length > 0 && (
            <div className="mt-8 rounded-xl border border-line bg-white">
              <div className="border-b border-line px-4 py-3">
                <p className="text-[13px] font-semibold">Demo accounts</p>
                <p className="text-xs text-ink-3">
                  Local demo only. Password for all:{' '}
                  <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[11.5px] text-ink">
                    {meta.data?.demo_password}
                  </code>
                </p>
              </div>
              <ul className="max-h-72 divide-y divide-line overflow-y-auto">
                {accounts.map((account) => (
                  <li key={account.email}>
                    <button
                      type="button"
                      className="group flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-slate-50"
                      onClick={() => {
                        setValue('email', account.email, { shouldValidate: true })
                        setValue('password', meta.data?.demo_password ?? '', { shouldValidate: true })
                      }}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium">{roleLabel(account.role)}</p>
                        <p className="truncate text-xs text-ink-3">
                          {account.institution ?? 'All institutions'} · {account.email}
                        </p>
                      </div>
                      <ArrowRight
                        className="size-4 text-ink-3 opacity-0 transition-opacity group-hover:opacity-100"
                        aria-hidden
                      />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
