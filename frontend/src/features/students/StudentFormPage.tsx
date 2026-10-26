import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { z } from 'zod'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert } from '@/components/ui/Feedback'
import { Checkbox, Field, Input, Select } from '@/components/ui/Form'
import { PageHeader } from '@/components/ui/Layout'
import { useToast } from '@/components/ui/Toast'
import { ApiError, api } from '@/lib/api'
import { humanize } from '@/lib/format'
import { useAppConfig, useProgrammes } from '@/lib/queries'

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Use YYYY-MM-DD')

const schema = z.object({
  programme_code: z.string().min(1, 'Choose a programme'),
  academic_year: z.string().regex(/^\d{4}-\d{2}$/, 'Choose an academic year'),
  institution_student_id: z
    .string()
    .trim()
    .min(1, 'Required')
    .max(64)
    .regex(/^[A-Za-z0-9/_-]+$/, 'Letters, digits, / _ - only'),
  apaar_id: z.string().trim().min(1, 'APAAR ID is required').max(64),
  full_name: z.string().trim().min(2, 'Enter the full name').max(160),
  date_of_birth: isoDate,
  gender: z.string().optional(),
  admission_date: isoDate,
  seat_type: z.string().min(1),
  nri_category: z.boolean(),
  oci_status: z.boolean(),
  foreign_national_status: z.boolean(),
  nationality: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{2}$/, 'Two-letter country code, e.g. IN'),
  enrolment_status: z.string().min(1),
})
type FormValues = z.infer<typeof schema>

interface SubmitResult {
  status: 'created' | 'updated' | 'unchanged'
  student_id: string
  changed_fields: string[]
}

export function StudentFormPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()
  const config = useAppConfig()
  const programmes = useProgrammes()
  const years = config.data?.academic_years ?? []

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: {
      programme_code: '',
      academic_year: years[0] ?? '',
      institution_student_id: '',
      apaar_id: '',
      full_name: '',
      date_of_birth: '',
      gender: '',
      admission_date: '',
      seat_type: 'REGULAR',
      nri_category: false,
      oci_status: false,
      foreign_national_status: false,
      nationality: 'IN',
      enrolment_status: 'ENROLLED',
    },
    resetOptions: { keepDirtyValues: true },
  })

  const submit = useMutation({
    mutationFn: (values: FormValues) =>
      api.post<SubmitResult>('/students', {
        ...values,
        gender: values.gender || null,
        nationality: values.nationality.toUpperCase(),
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries()
      toast.success(
        result.status === 'created'
          ? 'Record saved. Validation rules have run.'
          : result.status === 'updated'
            ? 'Existing admission updated.'
            : 'No changes — this admission already exists with the same details.',
      )
      navigate(`/students/${result.student_id}`)
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const fields = error.fieldErrors
        for (const [field, message] of Object.entries(fields)) {
          if (field in schema.shape) setError(field as keyof FormValues, { message })
        }
        setError('root', {
          message: Object.keys(fields).length ? 'Please correct the highlighted fields.' : error.message,
        })
      } else {
        setError('root', { message: 'Could not save the record.' })
      }
    },
  })

  const onSubmit = handleSubmit((values) => submit.mutateAsync(values).catch(() => undefined))
  const fieldProps = (name: keyof FormValues) => ({
    id: name,
    'aria-invalid': Boolean(errors[name]),
    'aria-describedby': errors[name] ? `${name}-error` : undefined,
    ...register(name),
  })

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Add student record"
        description="Records entered here go through exactly the same validation as CSV uploads."
        back={{ to: '/students', label: 'Students' }}
      />
      <form onSubmit={onSubmit} noValidate className="space-y-6">
        {errors.root?.message && <Alert tone="danger">{errors.root.message}</Alert>}

        <Card>
          <CardHeader title="Identity" description="Use synthetic data only in this demo environment." />
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name" htmlFor="full_name" required error={errors.full_name?.message}>
              <Input autoComplete="off" {...fieldProps('full_name')} />
            </Field>
            <Field
              label="APAAR ID"
              htmlFor="apaar_id"
              required
              error={errors.apaar_id?.message}
              hint={`Format: ${config.data?.identifier_format.label ?? '…'}. A format check does not prove an ID is authentic.`}
            >
              <Input
                autoComplete="off"
                spellCheck={false}
                className="font-mono"
                placeholder={config.data?.identifier_format.example}
                {...fieldProps('apaar_id')}
              />
            </Field>
            <Field
              label="Institution student ID"
              htmlFor="institution_student_id"
              required
              error={errors.institution_student_id?.message}
            >
              <Input className="font-mono" {...fieldProps('institution_student_id')} />
            </Field>
            <Field label="Date of birth" htmlFor="date_of_birth" required error={errors.date_of_birth?.message}>
              <Input type="date" {...fieldProps('date_of_birth')} />
            </Field>
            <Field label="Gender" htmlFor="gender" hint="Optional" error={errors.gender?.message}>
              <Select {...fieldProps('gender')}>
                <option value="">Not stated</option>
                <option value="F">Female</option>
                <option value="M">Male</option>
                <option value="O">Other</option>
              </Select>
            </Field>
            <Field
              label="Nationality"
              htmlFor="nationality"
              required
              hint="ISO two-letter country code"
              error={errors.nationality?.message}
            >
              <Input maxLength={2} className="uppercase" {...fieldProps('nationality')} />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Admission" />
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Programme" htmlFor="programme_code" required error={errors.programme_code?.message}>
              <Select {...fieldProps('programme_code')}>
                <option value="">Choose…</option>
                {(programmes.data ?? []).map((p) => (
                  <option key={p.id} value={p.code}>
                    {p.name} ({p.code})
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Academic year" htmlFor="academic_year" required error={errors.academic_year?.message}>
              <Select {...fieldProps('academic_year')}>
                {years.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Admission date" htmlFor="admission_date" required error={errors.admission_date?.message}>
              <Input type="date" {...fieldProps('admission_date')} />
            </Field>
            <Field label="Seat type" htmlFor="seat_type" required>
              <Select {...fieldProps('seat_type')}>
                {(config.data?.seat_types ?? ['REGULAR', 'SUPERNUMERARY']).map((s) => (
                  <option key={s} value={s}>
                    {humanize(s)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Enrolment status" htmlFor="enrolment_status" required>
              <Select {...fieldProps('enrolment_status')}>
                {(config.data?.enrolment_statuses ?? ['ENROLLED']).map((s) => (
                  <option key={s} value={s}>
                    {humanize(s)}
                  </option>
                ))}
              </Select>
            </Field>
            <fieldset className="space-y-2 sm:col-span-2">
              <legend className="mb-1 text-[13px] font-medium">Category and status</legend>
              <div className="grid gap-3 sm:grid-cols-3">
                <Checkbox id="nri_category" label="NRI category" {...register('nri_category')} />
                <Checkbox id="oci_status" label="OCI status" {...register('oci_status')} />
                <Checkbox
                  id="foreign_national_status"
                  label="Foreign National (FN)"
                  {...register('foreign_national_status')}
                />
              </div>
            </fieldset>
          </CardBody>
        </Card>

        <div className="flex justify-end gap-2">
          <ButtonLink to="/students">Cancel</ButtonLink>
          <Button type="submit" loading={isSubmitting}>
            Save and validate
          </Button>
        </div>
      </form>
    </div>
  )
}
